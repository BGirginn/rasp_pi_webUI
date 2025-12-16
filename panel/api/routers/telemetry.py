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
    """Get real HOST system metrics by reading from mounted /host filesystem."""
    import platform
    import subprocess
    import os
    
    metrics = {}
    
    # Check if we have host access via /host mount
    host_root = "/host" if os.path.exists("/host/proc") else ""
    
    # ============ CPU Usage ============
    # ============ CPU Usage ============
    try:
        import psutil
        # This blocks for 0.5s to calculate accurate delta
        metrics["host.cpu.pct_total"] = psutil.cpu_percent(interval=0.5)
    except:
        try:
            # Manual fallback: Read /proc/stat twice
            def read_stat():
                with open(f"{host_root}/proc/stat", "r") as f:
                    line = f.readline()
                    parts = line.split()
                    if len(parts) >= 5:
                        idle = int(parts[4])
                        total = sum(int(p) for p in parts[1:])
                        return total, idle
                return 0, 0

            t1, i1 = read_stat()
            if t1 > 0:
                time.sleep(0.5)
                t2, i2 = read_stat()
                delta_total = t2 - t1
                delta_idle = i2 - i1
                if delta_total > 0:
                   metrics["host.cpu.pct_total"] = round(100 * (1 - delta_idle / delta_total), 1)
                else:
                   metrics["host.cpu.pct_total"] = 0
            else:
                metrics["host.cpu.pct_total"] = 0
        except Exception as e:
            print(f"CPU calc error: {e}")
            metrics["host.cpu.pct_total"] = 0
    
    # ============ Memory ============
    try:
        with open(f"{host_root}/proc/meminfo", "r") as f:
            meminfo = {}
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(":")
                    meminfo[key] = int(parts[1])  # in kB
            
            total = meminfo.get("MemTotal", 0)
            available = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
            used = total - available
            
            metrics["host.mem.total_mb"] = round(total / 1024, 1)
            metrics["host.mem.used_mb"] = round(used / 1024, 1)
            metrics["host.mem.available_mb"] = round(available / 1024, 1)
            metrics["host.mem.pct"] = round(100 * used / total, 1) if total > 0 else 0
    except:
        try:
            import psutil
            mem = psutil.virtual_memory()
            metrics["host.mem.pct"] = mem.percent
            metrics["host.mem.used_mb"] = mem.used / (1024 * 1024)
            metrics["host.mem.total_mb"] = mem.total / (1024 * 1024)
        except:
            pass
    
    # ============ Disk ============
    try:
        # Use df command for host disk
        result = subprocess.run(
            ["df", "-B1", f"{host_root}/" if host_root else "/"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 5:
                    total = int(parts[1])
                    used = int(parts[2])
                    pct = int(parts[4].rstrip("%"))
                    metrics["disk._root.total_gb"] = round(total / (1024**3), 1)
                    metrics["disk._root.used_gb"] = round(used / (1024**3), 1)
                    metrics["disk._root.pct"] = pct # Legacy key
                    metrics["disk._root.used_pct"] = pct
    except:
        try:
            import psutil
            disk = psutil.disk_usage("/")
            metrics["disk._root.pct"] = disk.percent
            metrics["disk._root.used_pct"] = disk.percent
            metrics["disk._root.used_gb"] = disk.used / (1024**3)
            metrics["disk._root.total_gb"] = disk.total / (1024**3)
        except:
            pass
    
    # ============ Load Average ============
    try:
        with open(f"{host_root}/proc/loadavg", "r") as f:
            parts = f.read().split()
            metrics["host.load.1m"] = float(parts[0])
            metrics["host.load.5m"] = float(parts[1])
            metrics["host.load.15m"] = float(parts[2])
    except:
        pass
    
    # ============ Temperature (Raspberry Pi specific) ============
    try:
        # Try Raspberry Pi thermal zone
        temp_path = f"{host_root}/sys/class/thermal/thermal_zone0/temp"
        if os.path.exists(temp_path):
            with open(temp_path, "r") as f:
                temp_millic = int(f.read().strip())
                metrics["host.temp.cpu_c"] = round(temp_millic / 1000, 1)
    except:
        pass
    
    # ============ Network ============
    try:
        with open(f"{host_root}/proc/net/dev", "r") as f:
            rx_total = tx_total = 0
            for line in f:
                if ":" in line and not line.strip().startswith("lo"):
                    parts = line.split(":")
                    if len(parts) >= 2:
                        values = parts[1].split()
                        if len(values) >= 9:
                            rx_total += int(values[0])
                            tx_total += int(values[8])
            metrics["host.net.rx_bytes"] = rx_total
            metrics["host.net.tx_bytes"] = tx_total
    except:
        pass
    
    # ============ Uptime ============
    try:
        with open(f"{host_root}/proc/uptime", "r") as f:
            uptime_seconds = int(float(f.read().split()[0]))
            metrics["host.uptime.seconds"] = uptime_seconds
    except:
        pass
    
    # ============ System Info (from HOST) ============
    hostname = "raspberrypi"
    os_info = "Linux"
    machine = "aarch64"
    
    try:
        with open(f"{host_root}/etc/hostname", "r") as f:
            hostname = f.read().strip()
    except:
        pass
    
    try:
        with open(f"{host_root}/proc/version", "r") as f:
            version_line = f.read().strip()
            # Extract kernel version
            parts = version_line.split()
            if len(parts) >= 3:
                os_info = f"Linux {parts[2]}"
    except:
        pass
    
    # Get CPU model and architecture (not Pi model name)
    cpu_model = "Unknown"
    arch = "unknown"
    
    try:
        # Get architecture
        with open(f"{host_root}/proc/cpuinfo", "r") as f:
            for line in f:
                # Look for CPU implementer/part for ARM chips
                if line.startswith("CPU implementer"):
                    implementer = line.split(":")[1].strip()
                elif line.startswith("CPU part"):
                    part = line.split(":")[1].strip()
                    # Decode common ARM CPU parts
                    cpu_parts = {
                        "0xd0b": "ARM Cortex-A76",
                        "0xd07": "ARM Cortex-A57", 
                        "0xd08": "ARM Cortex-A72",
                        "0xd03": "ARM Cortex-A53",
                        "0xd04": "ARM Cortex-A35",
                    }
                    cpu_model = cpu_parts.get(part, f"ARM ({part})")
                    break
                elif line.startswith("model name"):
                    cpu_model = line.split(":")[1].strip()
                    break
    except:
        pass
    
    try:
        # Get architecture from uname
        import subprocess
        result = subprocess.run(["uname", "-m"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            arch = result.stdout.strip()  # e.g., aarch64, x86_64
    except:
        pass
    
    machine = f"{cpu_model} ({arch})"
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "degrade_mode": False,
        "source": "host" if host_root else "container",
        "system": {
            "hostname": hostname,
            "os": os_info,
            "machine": machine,
        },
        "metrics": metrics
    }


@router.get("/dashboard", response_model=DashboardData)
async def get_dashboard_data(user: dict = Depends(get_current_user)):
    """Get aggregated dashboard data."""
    from db import get_control_db
    
    # Try to get live telemetry (either from agent or local system)
    try:
        telemetry = await agent_client.get_current_telemetry()
        metrics = telemetry.get("metrics", {})
    except Exception:
        # Fallback: Get local system metrics
        local_data = await _get_local_system_metrics()
        metrics = local_data.get("metrics", {})
    
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
            memory_total_mb=metrics.get("host.mem.total_mb", 0),
            disk_pct=metrics.get("disk._root.used_pct", 0),
            disk_used_gb=metrics.get("disk._root.used_gb", 0),
            disk_total_gb=metrics.get("disk._root.total_gb", 0),
            temperature_c=metrics.get("host.temp.cpu_c"),
            load_1m=metrics.get("host.load.1m", 0),
            load_5m=metrics.get("host.load.5m", 0),
            load_15m=metrics.get("host.load.15m", 0),
            network_rx_bytes=int(metrics.get("host.net.rx_bytes", 0)),
            network_tx_bytes=int(metrics.get("host.net.tx_bytes", 0)),
            uptime_seconds=int(metrics.get("host.uptime.seconds", 0)),
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
