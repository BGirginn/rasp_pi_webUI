"""
Pi Control Panel - IoT Router

Handles IoT device listing, details, history, and simulation endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import List, Optional
from pydantic import BaseModel
from services.discovery import discovery_service, IoTDevice
from services.sse import sse_manager, Channels
from .auth import get_current_user
import time
import random
import asyncio
import json

router = APIRouter()

# Request models
class VirtualDeviceRequest(BaseModel):
    name: str
    ip: str = "192.168.1.100"
    port: int = 8080

class SensorReading(BaseModel):
    sensor_type: str
    value: float
    unit: str
    timestamp: int

# ==================== Device Listing ====================

@router.get("/devices")
async def get_devices(user: dict = Depends(get_current_user)):
    """Get list of all discovered IoT devices."""
    return discovery_service.get_devices()

@router.get("/devices/{device_id}")
async def get_device(device_id: str, user: dict = Depends(get_current_user)):
    """Get a single device by ID with current sensor data."""
    device = await discovery_service.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

# ==================== Device History ====================

@router.get("/devices/{device_id}/history")
async def get_device_history(
    device_id: str,
    hours: int = Query(24, ge=1, le=168, description="Hours of history to retrieve"),
    sensor_type: Optional[str] = Query(None, description="Filter by sensor type"),
    user: dict = Depends(get_current_user)
):
    """Get historical sensor readings for a device."""
    device = await discovery_service.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    history = await discovery_service.get_device_history(device_id, hours, sensor_type)
    
    # Group by sensor type for easier frontend consumption
    grouped = {}
    for reading in history:
        sensor = reading["sensor_type"]
        if sensor not in grouped:
            grouped[sensor] = {
                "sensor_type": sensor,
                "unit": reading["unit"],
                "readings": []
            }
        grouped[sensor]["readings"].append({
            "value": reading["value"],
            "timestamp": reading["timestamp"]
        })
    
    return {
        "device_id": device_id,
        "device_name": device["name"],
        "hours": hours,
        "sensor_type_filter": sensor_type,
        "sensors": list(grouped.values()),
        "total_readings": len(history)
    }

@router.get("/devices/{device_id}/sensors/{sensor_type}/history")
async def get_sensor_history(
    device_id: str,
    sensor_type: str,
    hours: int = Query(24, ge=1, le=168),
    user: dict = Depends(get_current_user)
):
    """Get historical readings for a specific sensor type."""
    device = await discovery_service.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    history = await discovery_service.get_device_history(device_id, hours, sensor_type)
    
    if not history:
        return {
            "device_id": device_id,
            "sensor_type": sensor_type,
            "readings": [],
            "stats": None
        }
    
    values = [r["value"] for r in history]
    
    return {
        "device_id": device_id,
        "sensor_type": sensor_type,
        "unit": history[0]["unit"] if history else "",
        "readings": [{"value": r["value"], "timestamp": r["timestamp"]} for r in history],
        "stats": {
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "count": len(values)
        }
    }

# ==================== SSE Streaming ====================

@router.get("/stream")
async def iot_stream(user: dict = Depends(get_current_user)):
    """Server-Sent Events stream for real-time IoT updates."""
    async def event_generator():
        # Send initial state
        devices = discovery_service.get_devices()
        yield f"event: iot_update\ndata: {json.dumps(devices)}\n\n"
        
        # Keep connection alive and send periodic updates
        while True:
            await asyncio.sleep(2)
            devices = discovery_service.get_devices()
            yield f"event: iot_update\ndata: {json.dumps(devices)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# ==================== Simulation / Testing ====================

@router.post("/devices/virtual")
async def add_virtual_device(request: VirtualDeviceRequest, user: dict = Depends(get_current_user)):
    """Add a virtual device for testing purposes."""
    device_id = request.name.lower().replace(' ', '-')
    
    # Generate random sensor data
    sensors = [
        {"type": "temperature", "value": round(random.uniform(20, 30), 1), "unit": "°C"},
        {"type": "humidity", "value": round(random.uniform(40, 60), 1), "unit": "%"},
        {"type": "light", "value": int(random.uniform(300, 800)), "unit": "lux"},
        {"type": "voltage", "value": round(random.uniform(3.2, 4.2), 2), "unit": "V"},
        {"type": "signal_strength", "value": int(random.uniform(-80, -40)), "unit": "dBm"}
    ]
    
    await discovery_service.add_device_manual(
        device_id=device_id,
        name=request.name,
        ip=request.ip,
        port=request.port,
        sensors=sensors
    )
    
    return {"message": f"Virtual device '{request.name}' added", "device_id": device_id}

@router.delete("/devices/virtual/{device_id}")
async def remove_virtual_device(device_id: str, user: dict = Depends(get_current_user)):
    """Remove a virtual device."""
    if device_id in discovery_service.devices:
        del discovery_service.devices[device_id]
        discovery_service._broadcast_update()
        return {"message": f"Device '{device_id}' removed"}
    raise HTTPException(status_code=404, detail="Device not found")

@router.post("/devices/simulate")
async def simulate_devices(user: dict = Depends(get_current_user)):
    """Add multiple simulated devices for testing with diverse sensor types."""
    
    # 4 rooms with unique sensor combinations - total 10 different sensor types
    simulated_devices = [
        {
            "name": "Living Room Sensor", 
            "ip": "192.168.1.101", 
            "port": 8080,
            "sensors": [
                {"type": "temperature", "value": round(random.uniform(20, 26), 1), "unit": "°C"},
                {"type": "humidity", "value": round(random.uniform(40, 60), 1), "unit": "%"},
                {"type": "co2", "value": int(random.uniform(400, 800)), "unit": "ppm"},
                {"type": "light", "value": int(random.uniform(200, 600)), "unit": "lux"},
                {"type": "noise", "value": int(random.uniform(30, 50)), "unit": "dB"},
            ]
        },
        {
            "name": "Kitchen Monitor", 
            "ip": "192.168.1.102", 
            "port": 8080,
            "sensors": [
                {"type": "temperature", "value": round(random.uniform(22, 30), 1), "unit": "°C"},
                {"type": "humidity", "value": round(random.uniform(50, 75), 1), "unit": "%"},
                {"type": "gas", "value": int(random.uniform(0, 100)), "unit": "ppm"},
                {"type": "smoke", "value": int(random.uniform(0, 50)), "unit": "ppm"},
            ]
        },
        {
            "name": "Bedroom Unit", 
            "ip": "192.168.1.103", 
            "port": 8080,
            "sensors": [
                {"type": "temperature", "value": round(random.uniform(18, 24), 1), "unit": "°C"},
                {"type": "humidity", "value": round(random.uniform(45, 65), 1), "unit": "%"},
                {"type": "light", "value": int(random.uniform(0, 200)), "unit": "lux"},
                {"type": "noise", "value": int(random.uniform(20, 40)), "unit": "dB"},
                {"type": "air_quality", "value": int(random.uniform(0, 100)), "unit": "AQI"},
            ]
        },
        {
            "name": "Garage Controller", 
            "ip": "192.168.1.104", 
            "port": 8080,
            "sensors": [
                {"type": "temperature", "value": round(random.uniform(10, 35), 1), "unit": "°C"},
                {"type": "humidity", "value": round(random.uniform(30, 80), 1), "unit": "%"},
                {"type": "motion", "value": int(random.uniform(0, 1)), "unit": ""},
                {"type": "voltage", "value": round(random.uniform(11.5, 13.5), 1), "unit": "V"},
                {"type": "pressure", "value": int(random.uniform(1000, 1025)), "unit": "hPa"},
            ]
        },
    ]
    
    added_devices = []
    for dev_info in simulated_devices:
        device_id = dev_info["name"].lower().replace(' ', '-')
        
        # Skip if already exists
        if device_id in discovery_service.devices:
            continue
        
        await discovery_service.add_device_manual(
            device_id=device_id,
            name=dev_info["name"],
            ip=dev_info["ip"],
            port=dev_info["port"],
            sensors=dev_info["sensors"]
        )
        added_devices.append(device_id)
    
    return {
        "message": f"Added {len(added_devices)} simulated devices",
        "devices": added_devices,
        "total_devices": len(discovery_service.devices)
    }

@router.post("/devices/clear")
async def clear_devices(user: dict = Depends(get_current_user)):
    """Clear all virtual/simulated devices from memory (not from database)."""
    count = len(discovery_service.devices)
    discovery_service.devices.clear()
    discovery_service._broadcast_update()
    return {"message": f"Cleared {count} devices from active list"}

@router.post("/devices/{device_id}/refresh-sensors")
async def refresh_device_sensors(device_id: str, user: dict = Depends(get_current_user)):
    """Refresh sensor data for a specific device with random values (for testing)."""
    if device_id not in discovery_service.devices:
        raise HTTPException(status_code=404, detail="Device not found")
    
    device = discovery_service.devices[device_id]
    device.last_seen = time.time()
    
    new_sensors = [
        {"type": "temperature", "value": round(random.uniform(18, 32), 1), "unit": "°C"},
        {"type": "humidity", "value": round(random.uniform(35, 70), 1), "unit": "%"},
        {"type": "light", "value": int(random.uniform(100, 1200)), "unit": "lux"},
        {"type": "voltage", "value": round(random.uniform(3.0, 4.5), 2), "unit": "V"},
        {"type": "signal_strength", "value": int(random.uniform(-90, -30)), "unit": "dBm"}
    ]
    
    device.sensors = new_sensors
    
    # Save to database
    await discovery_service._save_sensor_readings(device_id, new_sensors)
    
    discovery_service._broadcast_update()
    return {"message": f"Sensors refreshed for '{device_id}'", "sensors": new_sensors}
