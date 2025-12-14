"""
Pi Control Panel - Telemetry Router

Handles metrics queries, live telemetry streaming, and dashboard data.
"""

import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from db import get_telemetry_db
from services.sse import sse_manager, Channels
from services.agent_client import agent_client
from .auth import get_current_user

router = APIRouter()


class MetricPoint(BaseModel):
    ts: int
    value: float


class MetricsResponse(BaseModel):
    metric: str
    points: List[MetricPoint]


class MetricsSummary(BaseModel):
    metric: str
    avg: float
    min: float
    max: float
    count: int


class SystemMetrics(BaseModel):
    cpu_pct: float
    memory_pct: float
    memory_used_mb: float
    memory_total_mb: float
    disk_pct: float
    disk_used_gb: float
    disk_total_gb: float
    temperature_c: Optional[float]
    load_1m: float
    load_5m: float
    load_15m: float
    network_rx_bytes: int
    network_tx_bytes: int
    uptime_seconds: int


class DashboardData(BaseModel):
    system: SystemMetrics
    resource_counts: Dict[str, int]
    alert_counts: Dict[str, int]
    timestamp: str


@router.get("/current", response_model=Dict)
async def get_current_metrics(user: dict = Depends(get_current_user)):
    """Get current metrics snapshot from agent or local system."""
    try:
        telemetry = await agent_client.get_current_telemetry()
        return telemetry
    except Exception:
        # Fallback: Get real metrics from local system
        return await _get_local_system_metrics()


async def _get_local_system_metrics() -> Dict:
    """Get real system metrics using psutil."""
    import platform
    
    try:
        import psutil
    except ImportError:
        # psutil not available, return minimal data
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "degrade_mode": True,
            "error": "psutil not installed",
            "metrics": {}
        }
    
    metrics = {}
    
    # CPU
    cpu_percent = psutil.cpu_percent(interval=0.1)
    metrics["host.cpu.pct_total"] = cpu_percent
    
    # Memory
    mem = psutil.virtual_memory()
    metrics["host.mem.pct"] = mem.percent
    metrics["host.mem.used_mb"] = mem.used / (1024 * 1024)
    metrics["host.mem.available_mb"] = mem.available / (1024 * 1024)
    metrics["host.mem.total_mb"] = mem.total / (1024 * 1024)
    
    # Disk
    disk = psutil.disk_usage("/")
    metrics["disk._root.used_pct"] = disk.percent
    metrics["disk._root.used_gb"] = disk.used / (1024 ** 3)
    metrics["disk._root.total_gb"] = disk.total / (1024 ** 3)
    
    # Load average (Unix only)
    if hasattr(psutil, "getloadavg"):
        load = psutil.getloadavg()
        metrics["host.load.1m"] = load[0]
        metrics["host.load.5m"] = load[1]
        metrics["host.load.15m"] = load[2]
    
    # Temperature (platform specific)
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            # Try common sensor names
            for key in ["cpu_thermal", "coretemp", "cpu-thermal", "k10temp"]:
                if key in temps and temps[key]:
                    metrics["host.temp.cpu_c"] = temps[key][0].current
                    break
    except (AttributeError, KeyError):
        pass
    
    # macOS specific temperature (if available)
    if platform.system() == "Darwin" and "host.temp.cpu_c" not in metrics:
        try:
            import subprocess
            # Try to get CPU temp on macOS using powermetrics (requires sudo) or osx-cpu-temp
            result = subprocess.run(
                ["osx-cpu-temp"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                temp_str = result.stdout.strip().replace("°C", "")
                metrics["host.temp.cpu_c"] = float(temp_str)
        except Exception:
            pass
    
    # Network
    net = psutil.net_io_counters()
    metrics["host.net.rx_bytes"] = net.bytes_recv
    metrics["host.net.tx_bytes"] = net.bytes_sent
    
    # Uptime
    boot_time = psutil.boot_time()
    uptime_seconds = int(time.time() - boot_time)
    metrics["host.uptime.seconds"] = uptime_seconds
    
    # System info
    uname = platform.uname()
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "degrade_mode": False,
        "source": "local",
        "system": {
            "hostname": uname.node,
            "os": f"{uname.system} {uname.release}",
            "machine": uname.machine,
            "python": platform.python_version(),
        },
        "metrics": metrics
    }


@router.get("/dashboard", response_model=DashboardData)
async def get_dashboard_data(user: dict = Depends(get_current_user)):
    """Get aggregated dashboard data."""
    from db import get_control_db
    
    # Try to get live telemetry
    try:
        telemetry = await agent_client.get_current_telemetry()
        metrics = telemetry.get("metrics", {})
    except Exception:
        metrics = {}
    
    # Get resource counts from DB
    db = await get_control_db()
    cursor = await db.execute(
        """SELECT class, COUNT(*) FROM resources 
           WHERE managed = 1 GROUP BY class"""
    )
    resource_counts = {row[0]: row[1] for row in await cursor.fetchall()}
    
    # Get alert counts
    cursor = await db.execute(
        """SELECT severity, COUNT(*) FROM alerts 
           WHERE state IN ('pending', 'firing') GROUP BY severity"""
    )
    alert_counts = {row[0]: row[1] for row in await cursor.fetchall()}
    
    return DashboardData(
        system=SystemMetrics(
            cpu_pct=metrics.get("host.cpu.pct_total", 0),
            memory_pct=metrics.get("host.mem.pct", 0),
            memory_used_mb=metrics.get("host.mem.used_mb", 0),
            memory_total_mb=metrics.get("host.mem.available_mb", 0) + metrics.get("host.mem.used_mb", 0),
            disk_pct=metrics.get("disk._root.used_pct", 0),
            disk_used_gb=metrics.get("disk._root.used_gb", 0),
            disk_total_gb=0,
            temperature_c=metrics.get("host.temp.cpu_c"),
            load_1m=metrics.get("host.load.1m", 0),
            load_5m=metrics.get("host.load.5m", 0),
            load_15m=metrics.get("host.load.15m", 0),
            network_rx_bytes=int(metrics.get("net.eth0.rx_bytes", 0)),
            network_tx_bytes=int(metrics.get("net.eth0.tx_bytes", 0)),
            uptime_seconds=0,
        ),
        resource_counts=resource_counts,
        alert_counts=alert_counts,
        timestamp=datetime.utcnow().isoformat()
    )


@router.get("/metrics", response_model=List[MetricsResponse])
async def query_metrics(
    metrics: str = Query(..., description="Comma-separated metric names"),
    start: Optional[int] = Query(None, description="Start timestamp (epoch)"),
    end: Optional[int] = Query(None, description="End timestamp (epoch)"),
    step: int = Query(60, description="Step size in seconds"),
    user: dict = Depends(get_current_user)
):
    """Query historical metrics."""
    db = await get_telemetry_db()
    
    now = int(time.time())
    start = start or (now - 3600)  # Default 1 hour
    end = end or now
    
    metric_names = [m.strip() for m in metrics.split(",")]
    results = []
    
    for metric_name in metric_names:
        cursor = await db.execute(
            """SELECT ts, value FROM metrics_raw 
               WHERE metric = ? AND ts BETWEEN ? AND ?
               ORDER BY ts""",
            (metric_name, start, end)
        )
        rows = await cursor.fetchall()
        
        points = [MetricPoint(ts=row[0], value=row[1]) for row in rows]
        results.append(MetricsResponse(metric=metric_name, points=points))
    
    return results


@router.get("/metrics/{metric_name}/summary", response_model=MetricsSummary)
async def get_metric_summary(
    metric_name: str,
    hours: int = Query(24, ge=1, le=168),
    user: dict = Depends(get_current_user)
):
    """Get summary statistics for a metric."""
    db = await get_telemetry_db()
    
    start = int(time.time()) - (hours * 3600)
    
    cursor = await db.execute(
        """SELECT AVG(value), MIN(value), MAX(value), COUNT(*)
           FROM metrics_raw
           WHERE metric = ? AND ts >= ?""",
        (metric_name, start)
    )
    row = await cursor.fetchone()
    
    if not row or row[3] == 0:
        raise HTTPException(status_code=404, detail="No data found for metric")
    
    return MetricsSummary(
        metric=metric_name,
        avg=row[0] or 0,
        min=row[1] or 0,
        max=row[2] or 0,
        count=row[3]
    )


@router.get("/metrics/available")
async def list_available_metrics(user: dict = Depends(get_current_user)):
    """List all available metric names."""
    db = await get_telemetry_db()
    
    cursor = await db.execute(
        "SELECT DISTINCT metric FROM metrics_raw ORDER BY metric"
    )
    rows = await cursor.fetchall()
    
    # Group by category
    categories = {}
    for (metric,) in rows:
        parts = metric.split(".")
        category = parts[0] if len(parts) > 1 else "other"
        
        if category not in categories:
            categories[category] = []
        categories[category].append(metric)
    
    return {
        "total": len(rows),
        "categories": categories
    }


@router.get("/history/{resource_id}")
async def get_resource_history(
    resource_id: str,
    hours: int = Query(24, ge=1, le=168),
    user: dict = Depends(get_current_user)
):
    """Get telemetry history for a specific resource."""
    db = await get_telemetry_db()
    
    start = int(time.time()) - (hours * 3600)
    
    # Get metrics that match the resource
    cursor = await db.execute(
        """SELECT metric, ts, value FROM metrics_raw
           WHERE metric LIKE ? AND ts >= ?
           ORDER BY ts""",
        (f"%{resource_id}%", start)
    )
    rows = await cursor.fetchall()
    
    # Group by metric
    metrics = {}
    for metric, ts, value in rows:
        if metric not in metrics:
            metrics[metric] = []
        metrics[metric].append({"ts": ts, "value": value})
    
    return {
        "resource_id": resource_id,
        "hours": hours,
        "metrics": metrics
    }


@router.post("/retention/cleanup")
async def cleanup_old_data(
    user: dict = Depends(get_current_user)
):
    """Manually trigger data cleanup based on retention policies."""
    from config import settings
    
    db = await get_telemetry_db()
    
    now = int(time.time())
    raw_cutoff = now - (settings.telemetry_raw_retention_hours * 3600)
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
    
    return {
        "raw_deleted": raw_deleted,
        "summary_deleted": summary_deleted,
        "raw_cutoff": datetime.fromtimestamp(raw_cutoff).isoformat(),
        "summary_cutoff": datetime.fromtimestamp(summary_cutoff).isoformat()
    }
