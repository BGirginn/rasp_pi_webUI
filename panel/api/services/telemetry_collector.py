"""
Pi Control Panel - Telemetry Collector Service

Background service that periodically collects system metrics and stores them in the database.
Handles data aggregation and retention policy enforcement.
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Optional

import structlog

from config import settings
from db import get_telemetry_db
from services.sse import sse_manager, Channels

logger = structlog.get_logger(__name__)


class TelemetryCollector:
    """
    Background service that:
    1. Collects system metrics every 30 seconds
    2. Stores raw metrics in telemetry database
    3. Aggregates metrics into summaries every 5 minutes
    4. Cleans up old data based on retention policy
    
    Retention Policy (optimized for Raspberry Pi storage):
    - Raw data: 15 days (configurable)
    - Summary data: 30 days (configurable)
    """
    
    COLLECTION_INTERVAL = 30  # seconds
    AGGREGATION_INTERVAL = 300  # 5 minutes
    CLEANUP_INTERVAL = 3600  # 1 hour
    
    def __init__(self):
        self._running = False
        self._collect_task: Optional[asyncio.Task] = None
        self._aggregate_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._last_metrics: Dict = {}
    
    async def start(self):
        """Start the telemetry collector background tasks."""
        if self._running:
            return
        
        self._running = True
        self._collect_task = asyncio.create_task(self._collection_loop())
        self._aggregate_task = asyncio.create_task(self._aggregation_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info(
            "Telemetry collector started",
            collection_interval=self.COLLECTION_INTERVAL,
            raw_retention_days=settings.telemetry_raw_retention_days,
            summary_retention_days=settings.telemetry_summary_retention_days
        )
    
    async def stop(self):
        """Stop the telemetry collector."""
        self._running = False
        
        for task in [self._collect_task, self._aggregate_task, self._cleanup_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        logger.info("Telemetry collector stopped")
    
    async def _collection_loop(self):
        """Main collection loop - runs every 30 seconds."""
        while self._running:
            try:
                await self._collect_and_store_metrics()
            except Exception as e:
                logger.error("Error collecting metrics", error=str(e))
            
            await asyncio.sleep(self.COLLECTION_INTERVAL)
    
    async def _aggregation_loop(self):
        """Aggregation loop - runs every 5 minutes."""
        # Wait a bit before first aggregation
        await asyncio.sleep(60)
        
        while self._running:
            try:
                await self._aggregate_metrics()
            except Exception as e:
                logger.error("Error aggregating metrics", error=str(e))
            
            await asyncio.sleep(self.AGGREGATION_INTERVAL)
    
    async def _cleanup_loop(self):
        """Cleanup loop - runs every hour."""
        # Wait before first cleanup
        await asyncio.sleep(300)
        
        while self._running:
            try:
                await self._cleanup_old_data()
            except Exception as e:
                logger.error("Error cleaning up old data", error=str(e))
            
            await asyncio.sleep(self.CLEANUP_INTERVAL)
    
    async def _collect_and_store_metrics(self):
        """Collect current system metrics and store in database."""
        from routers.telemetry import _get_local_system_metrics
        
        # Get current metrics
        data = await _get_local_system_metrics()
        metrics = data.get("metrics", {})
        
        if not metrics:
            return
        
        self._last_metrics = metrics
        
        # Store in database
        db = await get_telemetry_db()
        ts = int(time.time())
        
        # Insert all metrics
        for metric_name, value in metrics.items():
            if isinstance(value, (int, float)):
                await db.execute(
                    "INSERT INTO metrics_raw (ts, metric, labels_json, value) VALUES (?, ?, ?, ?)",
                    (ts, metric_name, None, float(value))
                )
        
        await db.commit()
        
        # Broadcast to SSE clients for real-time updates
        await sse_manager.broadcast(
            Channels.TELEMETRY,
            "telemetry_update",
            {
                "metrics": metrics,
                "system": data.get("system", {}),
                "timestamp": ts
            }
        )
        
        logger.debug(
            "Metrics collected and stored",
            count=len(metrics),
            timestamp=ts
        )
    
    async def _aggregate_metrics(self):
        """Aggregate raw metrics into summary statistics."""
        db = await get_telemetry_db()
        now = int(time.time())
        
        # Aggregate last 5 minutes of data
        window_start = now - self.AGGREGATION_INTERVAL
        
        # Get distinct metrics
        cursor = await db.execute(
            "SELECT DISTINCT metric FROM metrics_raw WHERE ts >= ?",
            (window_start,)
        )
        metrics = [row[0] for row in await cursor.fetchall()]
        
        for metric_name in metrics:
            # Calculate statistics
            cursor = await db.execute(
                """SELECT 
                    AVG(value) as avg,
                    MIN(value) as min,
                    MAX(value) as max,
                    COUNT(*) as count
                FROM metrics_raw
                WHERE metric = ? AND ts >= ?""",
                (metric_name, window_start)
            )
            row = await cursor.fetchone()
            
            if row and row[3] > 0:
                # Calculate percentiles (approximate using sorted values)
                cursor = await db.execute(
                    "SELECT value FROM metrics_raw WHERE metric = ? AND ts >= ? ORDER BY value",
                    (metric_name, window_start)
                )
                values = [r[0] for r in await cursor.fetchall()]
                
                p50 = values[len(values) // 2] if values else 0
                p95 = values[int(len(values) * 0.95)] if len(values) > 1 else (values[0] if values else 0)
                p99 = values[int(len(values) * 0.99)] if len(values) > 1 else (values[0] if values else 0)
                
                # Insert summary
                await db.execute(
                    """INSERT INTO metrics_summary 
                       (ts, metric, labels_json, avg, min, max, p50, p95, p99, count)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (now, metric_name, None, row[0], row[1], row[2], p50, p95, p99, row[3])
                )
        
        await db.commit()
        
        logger.debug(
            "Metrics aggregated",
            metric_count=len(metrics),
            window_seconds=self.AGGREGATION_INTERVAL
        )
    
    async def _cleanup_old_data(self):
        """Remove data older than retention policy."""
        db = await get_telemetry_db()
        now = int(time.time())
        
        # Calculate cutoffs
        raw_cutoff = now - (settings.telemetry_raw_retention_days * 24 * 3600)
        summary_cutoff = now - (settings.telemetry_summary_retention_days * 24 * 3600)
        
        # Delete old raw metrics
        cursor = await db.execute(
            "DELETE FROM metrics_raw WHERE ts < ?",
            (raw_cutoff,)
        )
        raw_deleted = cursor.rowcount
        
        # Delete old summaries
        cursor = await db.execute(
            "DELETE FROM metrics_summary WHERE ts < ?",
            (summary_cutoff,)
        )
        summary_deleted = cursor.rowcount
        
        await db.commit()
        
        # Vacuum if significant deletions
        if raw_deleted > 1000 or summary_deleted > 100:
            await db.execute("VACUUM")
        
        logger.info(
            "Old telemetry data cleaned up",
            raw_deleted=raw_deleted,
            summary_deleted=summary_deleted,
            raw_cutoff=datetime.fromtimestamp(raw_cutoff).isoformat(),
            summary_cutoff=datetime.fromtimestamp(summary_cutoff).isoformat()
        )
    
    def get_last_metrics(self) -> Dict:
        """Get the last collected metrics (for cache)."""
        return self._last_metrics


# Global instance
telemetry_collector = TelemetryCollector()
