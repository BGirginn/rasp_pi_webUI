"""
Pi Control Panel - Archive Router

Provides access to historical data from telemetry and IoT databases.
Supports filtering by date range and exporting to JSON/CSV.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional, List
from datetime import datetime, timedelta
from .auth import get_current_user
from db import get_telemetry_db, get_control_db
from config import settings
import json
import csv
import io
import time

router = APIRouter()

# ==================== Telemetry Archive ====================

@router.get("/telemetry")
async def get_telemetry_archive(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    metric: Optional[str] = Query(None, description="Filter by metric name"),
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user)
):
    """Get historical telemetry data with optional date filtering."""
    db = await get_telemetry_db()
    
    # Build query
    query = "SELECT ts, metric, labels_json, value FROM metrics_raw WHERE 1=1"
    params = []
    
    if start_date:
        try:
            start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
            query += " AND ts >= ?"
            params.append(start_ts)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD")
    
    if end_date:
        try:
            end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp()) + 86400  # Include full day
            query += " AND ts < ?"
            params.append(end_ts)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD")
    
    if metric:
        query += " AND metric LIKE ?"
        params.append(f"%{metric}%")
    
    # Get total count
    count_query = query.replace("SELECT ts, metric, labels_json, value", "SELECT COUNT(*)")
    cursor = await db.execute(count_query, params)
    total = (await cursor.fetchone())[0]
    
    # Get data with pagination
    query += " ORDER BY ts DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    
    data = []
    for row in rows:
        data.append({
            "timestamp": row[0],
            "datetime": datetime.fromtimestamp(row[0]).isoformat(),
            "metric": row[1],
            "labels": json.loads(row[2]) if row[2] else {},
            "value": row[3]
        })
    
    return {
        "data": data,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(data) < total
    }

# ==================== IoT Archive ====================

@router.get("/iot")
async def get_iot_archive(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
    sensor_type: Optional[str] = Query(None, description="Filter by sensor type"),
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user)
):
    """Get historical IoT sensor readings with optional filtering."""
    db = await get_telemetry_db()
    
    query = "SELECT device_id, sensor_type, value, unit, timestamp FROM iot_sensor_readings WHERE 1=1"
    params = []
    
    if start_date:
        try:
            start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
            query += " AND timestamp >= ?"
            params.append(start_ts)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")
    
    if end_date:
        try:
            end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp()) + 86400
            query += " AND timestamp < ?"
            params.append(end_ts)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")
    
    if device_id:
        query += " AND device_id = ?"
        params.append(device_id)
    
    if sensor_type:
        query += " AND sensor_type = ?"
        params.append(sensor_type)
    
    # Get total count
    count_query = query.replace("SELECT device_id, sensor_type, value, unit, timestamp", "SELECT COUNT(*)")
    cursor = await db.execute(count_query, params)
    total = (await cursor.fetchone())[0]
    
    # Get data
    query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    
    data = []
    for row in rows:
        data.append({
            "device_id": row[0],
            "sensor_type": row[1],
            "value": row[2],
            "unit": row[3],
            "timestamp": row[4],
            "datetime": datetime.fromtimestamp(row[4]).isoformat()
        })
    
    return {
        "data": data,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(data) < total
    }

# ==================== Statistics ====================

@router.get("/stats")
async def get_archive_stats(user: dict = Depends(get_current_user)):
    """Get statistics about archived data."""
    db = await get_telemetry_db()
    
    stats = {}
    
    # Telemetry stats
    cursor = await db.execute("SELECT COUNT(*), MIN(ts), MAX(ts) FROM metrics_raw")
    row = await cursor.fetchone()
    stats["telemetry"] = {
        "total_records": row[0],
        "oldest": datetime.fromtimestamp(row[1]).isoformat() if row[1] else None,
        "newest": datetime.fromtimestamp(row[2]).isoformat() if row[2] else None
    }
    
    # IoT stats
    cursor = await db.execute("SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM iot_sensor_readings")
    row = await cursor.fetchone()
    stats["iot_sensors"] = {
        "total_records": row[0],
        "oldest": datetime.fromtimestamp(row[1]).isoformat() if row[1] else None,
        "newest": datetime.fromtimestamp(row[2]).isoformat() if row[2] else None
    }
    
    # IoT devices
    cursor = await db.execute("SELECT COUNT(*) FROM iot_devices")
    stats["iot_devices"] = {"total": (await cursor.fetchone())[0]}
    
    # Unique metrics
    cursor = await db.execute("SELECT COUNT(DISTINCT metric) FROM metrics_raw")
    stats["unique_metrics"] = (await cursor.fetchone())[0]
    
    # Unique sensor types
    cursor = await db.execute("SELECT COUNT(DISTINCT sensor_type) FROM iot_sensor_readings")
    stats["unique_sensor_types"] = (await cursor.fetchone())[0]
    
    # Database size (approximate)
    cursor = await db.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
    row = await cursor.fetchone()
    stats["database_size_bytes"] = row[0] if row else 0
    stats["database_size_mb"] = round(stats["database_size_bytes"] / (1024 * 1024), 2)
    
    return stats

# ==================== Export ====================

@router.get("/export/{data_type}")
async def export_data(
    data_type: str,
    format: str = Query("json", enum=["json", "csv"]),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    user: dict = Depends(get_current_user)
):
    """Export archive data as JSON or CSV."""
    db = await get_telemetry_db()
    
    if data_type == "telemetry":
        query = "SELECT ts, metric, labels_json, value FROM metrics_raw WHERE 1=1"
        columns = ["timestamp", "metric", "labels", "value"]
    elif data_type == "iot":
        query = "SELECT device_id, sensor_type, value, unit, timestamp FROM iot_sensor_readings WHERE 1=1"
        columns = ["device_id", "sensor_type", "value", "unit", "timestamp"]
    else:
        raise HTTPException(status_code=400, detail="Invalid data_type. Use 'telemetry' or 'iot'")
    
    params = []
    ts_column = "ts" if data_type == "telemetry" else "timestamp"
    
    if start_date:
        start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())
        query += f" AND {ts_column} >= ?"
        params.append(start_ts)
    
    if end_date:
        end_ts = int(datetime.strptime(end_date, "%Y-%m-%d").timestamp()) + 86400
        query += f" AND {ts_column} < ?"
        params.append(end_ts)
    
    query += f" ORDER BY {ts_column} DESC LIMIT 50000"  # Max 50k records per export
    
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    
    filename = f"export_{data_type}_{start_date or 'all'}_{end_date or 'now'}.{format}"
    
    if format == "json":
        data = []
        for row in rows:
            item = dict(zip(columns, row))
            if data_type == "telemetry" and item.get("labels"):
                item["labels"] = json.loads(item["labels"])
            if "timestamp" in item or "ts" in item:
                ts = item.get("timestamp") or item.get("ts")
                item["datetime"] = datetime.fromtimestamp(ts).isoformat()
            data.append(item)
        
        content = json.dumps(data, indent=2, ensure_ascii=False)
        media_type = "application/json"
    else:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns + ["datetime"])
        
        for row in rows:
            ts = row[0] if data_type == "telemetry" else row[4]
            dt = datetime.fromtimestamp(ts).isoformat()
            writer.writerow(list(row) + [dt])
        
        content = output.getvalue()
        media_type = "text/csv"
    
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ==================== Devices List ====================

@router.get("/devices")
async def get_archived_devices(user: dict = Depends(get_current_user)):
    """Get list of all devices that have historical data."""
    db = await get_telemetry_db()
    
    cursor = await db.execute("""
        SELECT DISTINCT device_id FROM iot_sensor_readings
        ORDER BY device_id
    """)
    rows = await cursor.fetchall()
    
    return {"devices": [row[0] for row in rows]}

@router.get("/sensor-types")
async def get_sensor_types(user: dict = Depends(get_current_user)):
    """Get list of all sensor types in archive."""
    db = await get_telemetry_db()
    
    cursor = await db.execute("""
        SELECT DISTINCT sensor_type FROM iot_sensor_readings
        ORDER BY sensor_type
    """)
    rows = await cursor.fetchall()
    
    return {"sensor_types": [row[0] for row in rows]}

@router.get("/metrics")
async def get_metrics_list(user: dict = Depends(get_current_user)):
    """Get list of all metric names in archive."""
    db = await get_telemetry_db()
    
    cursor = await db.execute("""
        SELECT DISTINCT metric FROM metrics_raw
        ORDER BY metric
    """)
    rows = await cursor.fetchall()
    
    return {"metrics": [row[0] for row in rows]}
