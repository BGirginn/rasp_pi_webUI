"""
Pi Agent - Telemetry Collector

Collects system metrics at configured intervals and stores them in SQLite.
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import aiosqlite
    AIOSQLITE_AVAILABLE = True
except ImportError:
    AIOSQLITE_AVAILABLE = False

logger = structlog.get_logger(__name__)


class TelemetryCollector:
    """Collects and stores system telemetry."""
    
    def __init__(self, config: dict):
        self.config = config.get("telemetry", {})
        self._db_path = self.config.get("db_path", "/data/telemetry.db")
        self._interval = self.config.get("interval", 2)
        self._batch_size = self.config.get("batch_size", 500)
        
        self._running = False
        self._collection_task: Optional[asyncio.Task] = None
        self._rollup_task: Optional[asyncio.Task] = None
        self._batch: List[Dict] = []
        self._lock = asyncio.Lock()
        
        # Degrade mode thresholds
        self._degrade_config = self.config.get("degrade", {})
        self._degrade_mode = False
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    async def start(self) -> None:
        """Start telemetry collection."""
        if not PSUTIL_AVAILABLE:
            logger.warning("psutil not available, telemetry disabled")
            return
        
        if not AIOSQLITE_AVAILABLE:
            logger.warning("aiosqlite not available, telemetry disabled")
            return
        
        # Initialize database
        await self._init_db()
        
        self._running = True
        self._collection_task = asyncio.create_task(self._collection_loop())
        self._rollup_task = asyncio.create_task(self._rollup_loop())
        
        logger.info("Telemetry collector started", interval=self._interval)
    
    async def stop(self) -> None:
        """Stop telemetry collection."""
        self._running = False
        
        if self._collection_task:
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass
        
        if self._rollup_task:
            self._rollup_task.cancel()
            try:
                await self._rollup_task
            except asyncio.CancelledError:
                pass
        
        # Flush remaining batch
        if self._batch:
            await self._flush_batch()
        
        logger.info("Telemetry collector stopped")
    
    async def _init_db(self) -> None:
        """Initialize SQLite database."""
        async with aiosqlite.connect(self._db_path) as db:
            # Enable WAL mode for better performance
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            
            # Create metrics_raw table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS metrics_raw (
                    ts INTEGER NOT NULL,
                    metric TEXT NOT NULL,
                    labels_json TEXT,
                    value REAL NOT NULL
                )
            """)
            
            # Create indexes
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_raw_lookup
                ON metrics_raw(metric, ts)
            """)
            
            # Create metrics_summary table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS metrics_summary (
                    ts INTEGER NOT NULL,
                    metric TEXT NOT NULL,
                    labels_json TEXT,
                    avg REAL,
                    min REAL,
                    max REAL,
                    count INTEGER
                )
            """)
            
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_summary_lookup
                ON metrics_summary(metric, ts)
            """)
            
            await db.commit()
            logger.info("Telemetry database initialized", path=self._db_path)
    
    async def _collection_loop(self) -> None:
        """Main collection loop."""
        while self._running:
            try:
                start_time = time.time()
                
                # Collect metrics
                metrics = await self._collect_metrics()
                
                # Add to batch
                async with self._lock:
                    self._batch.extend(metrics)
                    
                    # Flush if batch is full
                    if len(self._batch) >= self._batch_size:
                        await self._flush_batch()
                
                # Check for degrade mode
                await self._check_degrade_mode()
                
                # Calculate sleep time
                elapsed = time.time() - start_time
                interval = self._interval * 2.5 if self._degrade_mode else self._interval
                sleep_time = max(0, interval - elapsed)
                
                await asyncio.sleep(sleep_time)
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception("Collection error", error=str(e))
                await asyncio.sleep(self._interval)
    
    async def _collect_metrics(self) -> List[Dict]:
        """Collect current system metrics."""
        metrics = []
        ts = int(time.time())
        
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=None, percpu=True)
        for i, pct in enumerate(cpu_percent):
            metrics.append({
                "ts": ts,
                "metric": "host.cpu.pct",
                "labels": {"core": str(i)},
                "value": pct
            })
        
        # Overall CPU
        metrics.append({
            "ts": ts,
            "metric": "host.cpu.pct_total",
            "labels": None,
            "value": sum(cpu_percent) / len(cpu_percent)
        })
        
        # Load average
        load1, load5, load15 = psutil.getloadavg()
        metrics.extend([
            {"ts": ts, "metric": "host.load.1m", "labels": None, "value": load1},
            {"ts": ts, "metric": "host.load.5m", "labels": None, "value": load5},
            {"ts": ts, "metric": "host.load.15m", "labels": None, "value": load15},
        ])
        
        # Memory metrics
        mem = psutil.virtual_memory()
        metrics.extend([
            {"ts": ts, "metric": "host.mem.used_mb", "labels": None, "value": mem.used / (1024 * 1024)},
            {"ts": ts, "metric": "host.mem.available_mb", "labels": None, "value": mem.available / (1024 * 1024)},
            {"ts": ts, "metric": "host.mem.pct", "labels": None, "value": mem.percent},
        ])
        
        # Swap
        swap = psutil.swap_memory()
        metrics.append({
            "ts": ts,
            "metric": "host.swap.used_mb",
            "labels": None,
            "value": swap.used / (1024 * 1024)
        })
        
        # Disk metrics
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                mount = partition.mountpoint.replace("/", "_") or "root"
                metrics.extend([
                    {"ts": ts, "metric": f"disk.{mount}.used_pct", "labels": {"mount": partition.mountpoint}, "value": usage.percent},
                    {"ts": ts, "metric": f"disk.{mount}.used_gb", "labels": {"mount": partition.mountpoint}, "value": usage.used / (1024**3)},
                ])
            except (PermissionError, OSError):
                continue
        
        # Network metrics
        net_io = psutil.net_io_counters(pernic=True)
        for iface, counters in net_io.items():
            if iface == "lo":
                continue
            metrics.extend([
                {"ts": ts, "metric": f"net.{iface}.rx_bytes", "labels": {"iface": iface}, "value": counters.bytes_recv},
                {"ts": ts, "metric": f"net.{iface}.tx_bytes", "labels": {"iface": iface}, "value": counters.bytes_sent},
            ])
        
        # Temperature (Raspberry Pi specific)
        try:
            temps = psutil.sensors_temperatures()
            if "cpu_thermal" in temps or "coretemp" in temps:
                temp_readings = temps.get("cpu_thermal", temps.get("coretemp", []))
                if temp_readings:
                    metrics.append({
                        "ts": ts,
                        "metric": "host.temp.cpu_c",
                        "labels": None,
                        "value": temp_readings[0].current
                    })
        except (AttributeError, KeyError):
            pass
        
        return metrics
    
    async def _flush_batch(self) -> None:
        """Write batch to database."""
        if not self._batch:
            return
        
        batch_to_write = self._batch
        self._batch = []
        
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.executemany(
                    "INSERT INTO metrics_raw (ts, metric, labels_json, value) VALUES (?, ?, ?, ?)",
                    [
                        (m["ts"], m["metric"], str(m["labels"]) if m["labels"] else None, m["value"])
                        for m in batch_to_write
                    ]
                )
                await db.commit()
            
            logger.debug("Flushed metrics batch", count=len(batch_to_write))
            
        except Exception as e:
            logger.exception("Failed to flush batch", error=str(e))
            # Re-add failed batch (but don't exceed max size)
            async with self._lock:
                self._batch = batch_to_write[:self._batch_size // 2] + self._batch
    
    async def _rollup_loop(self) -> None:
        """Rollup raw metrics to summary periodically."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Run every minute
                await self._perform_rollup()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception("Rollup error", error=str(e))
    
    async def _perform_rollup(self) -> None:
        """Aggregate raw metrics into summary."""
        now = int(time.time())
        window_start = now - 60  # Last minute
        
        async with aiosqlite.connect(self._db_path) as db:
            # Get distinct metrics from last minute
            cursor = await db.execute(
                "SELECT DISTINCT metric FROM metrics_raw WHERE ts >= ?",
                (window_start,)
            )
            metrics = await cursor.fetchall()
            
            for (metric,) in metrics:
                # Calculate aggregates
                cursor = await db.execute(
                    """
                    SELECT AVG(value), MIN(value), MAX(value), COUNT(*)
                    FROM metrics_raw
                    WHERE metric = ? AND ts >= ?
                    """,
                    (metric, window_start)
                )
                row = await cursor.fetchone()
                
                if row and row[3] > 0:
                    await db.execute(
                        """
                        INSERT INTO metrics_summary (ts, metric, labels_json, avg, min, max, count)
                        VALUES (?, ?, NULL, ?, ?, ?, ?)
                        """,
                        (now, metric, row[0], row[1], row[2], row[3])
                    )
            
            await db.commit()
    
    async def _check_degrade_mode(self) -> None:
        """Check if we should enter degrade mode."""
        cpu_threshold = self._degrade_config.get("cpu_percent", 90)
        queue_threshold = self._degrade_config.get("queue_size", 10000)
        
        cpu_pct = psutil.cpu_percent(interval=None)
        queue_size = len(self._batch)
        
        should_degrade = cpu_pct > cpu_threshold or queue_size > queue_threshold
        
        if should_degrade and not self._degrade_mode:
            self._degrade_mode = True
            logger.warning("Entering degrade mode", cpu=cpu_pct, queue=queue_size)
        elif not should_degrade and self._degrade_mode:
            self._degrade_mode = False
            logger.info("Exiting degrade mode", cpu=cpu_pct, queue=queue_size)
    
    async def get_current(self) -> Dict[str, Any]:
        """Get current metrics snapshot."""
        metrics = await self._collect_metrics()
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "degrade_mode": self._degrade_mode,
            "metrics": {m["metric"]: m["value"] for m in metrics}
        }
    
    async def query(
        self,
        metric: str,
        start: Optional[int] = None,
        end: Optional[int] = None,
        use_summary: bool = False
    ) -> List[Dict]:
        """Query metrics from database."""
        if not AIOSQLITE_AVAILABLE:
            return []
        
        now = int(time.time())
        start = start or (now - 3600)  # Default 1 hour
        end = end or now
        
        table = "metrics_summary" if use_summary else "metrics_raw"
        
        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                f"SELECT ts, value FROM {table} WHERE metric = ? AND ts BETWEEN ? AND ? ORDER BY ts",
                (metric, start, end)
            )
            rows = await cursor.fetchall()
        
        return [{"ts": row[0], "value": row[1]} for row in rows]
