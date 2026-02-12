"""
Pi Control Panel - IoT Router

Handles IoT device listing, details, history, and simulation endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Optional
from pydantic import BaseModel, Field
from services.discovery import discovery_service
from services.agent_client import agent_client
from .auth import get_current_user, require_role
import time
import random
import asyncio
import json
import aiohttp
import urllib.parse

router = APIRouter()

# In-memory cache of last color per device, used to restore state on power-on
# for simple HTTP devices that don't support a dedicated "power on" API.
_LAST_LED_COLOR: dict = {}
# Request models
class VirtualDeviceRequest(BaseModel):
    name: str
    ip: str = "192.168.1.100"
    port: int = 8080

class ManualDeviceRequest(BaseModel):
    ip: str
    port: int = Field(80, ge=1, le=65535)
    name: Optional[str] = None
    device_id: Optional[str] = None
    probe: bool = True

class SensorReading(BaseModel):
    sensor_type: str
    value: float
    unit: str
    timestamp: int


class LedColorRequest(BaseModel):
    red: int = Field(..., ge=0, le=255)
    green: int = Field(..., ge=0, le=255)
    blue: int = Field(..., ge=0, le=255)
    power: bool = True
    persist: bool = True


class LedPowerRequest(BaseModel):
    on: bool
    persist: bool = True


LED_HTTP_COMMAND_ENDPOINTS = [
    "/api/led/command",
    "/led/command",
    "/command",
]

LED_HTTP_STATUS_ENDPOINTS = [
    "/status",
]

LED_HTTP_QUERY_SET_ENDPOINTS = [
    "/set",  # e.g. GET /set?r=255&g=0&b=0
]

def _sanitize_device_id(raw: str) -> str:
    # Keep it URL-safe and stable. (letters/digits/_/- only)
    if not raw:
        return ""
    out = []
    for ch in raw.strip():
        if ch.isalnum() or ch in ("-", "_"):
            out.append(ch)
        elif ch in (" ", ".", ":", "/"):
            out.append("-")
    cleaned = "".join(out).strip("-")
    return cleaned[:64] if cleaned else ""

async def _probe_device_http(ip: str, port: int) -> dict:
    """
    Probe a device to see if it exposes `/info` or an LED command endpoint.
    Returns a best-effort dict containing {id, name, sensors, led_http}.
    """
    result: dict = {"ip": ip, "port": port, "led_http": False}
    timeout = aiohttp.ClientTimeout(total=2.0)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        # 1) Try /info
        try:
            async with session.get(f"http://{ip}:{port}/info") as resp:
                if 200 <= resp.status < 300:
                    data = await resp.json()
                    if isinstance(data, dict):
                        if data.get("id"):
                            result["id"] = str(data.get("id"))
                        if data.get("name"):
                            result["name"] = str(data.get("name"))
                        if isinstance(data.get("sensors"), list):
                            result["sensors"] = data.get("sensors")
                    return result
        except Exception:
            pass

        # 2) Try status endpoint (common on simple RGB controllers)
        for endpoint in LED_HTTP_STATUS_ENDPOINTS:
            try:
                async with session.get(f"http://{ip}:{port}{endpoint}") as resp:
                    if 200 <= resp.status < 300:
                        data = await resp.json()
                        if isinstance(data, dict):
                            dev_name = data.get("device") or data.get("name")
                            if dev_name:
                                result["name"] = str(dev_name)
                                result["id"] = str(dev_name)
                            # If r/g/b present, expose minimal sensors for UI.
                            if all(k in data for k in ("r", "g", "b")):
                                try:
                                    result["sensors"] = [
                                        {"type": "led_r", "value": int(data.get("r", 0)), "unit": ""},
                                        {"type": "led_g", "value": int(data.get("g", 0)), "unit": ""},
                                        {"type": "led_b", "value": int(data.get("b", 0)), "unit": ""},
                                    ]
                                except Exception:
                                    pass
                        result["led_http"] = True
                        result["led_transport"] = "query"
                        result["status_endpoint"] = endpoint
                        return result
            except Exception:
                continue

        # 2) Try LED command endpoints with a lightweight ping
        request_body = {"command": "ping", "payload": {}}
        for endpoint in LED_HTTP_COMMAND_ENDPOINTS:
            try:
                async with session.post(f"http://{ip}:{port}{endpoint}", json=request_body) as resp:
                    if 200 <= resp.status < 300:
                        result["led_http"] = True
                        result["led_transport"] = "json"
                        return result
            except Exception:
                continue

    return result


def _success_result(result) -> bool:
    return isinstance(result, dict) and bool(result.get("success"))


async def _send_led_command_mqtt(device_id: str, command: str, payload: dict) -> dict:
    """Try sending LED command via agent MQTT bridge."""
    try:
        result = await agent_client.send_device_command(device_id, command, payload)
        if _success_result(result):
            return {"success": True, "transport": "mqtt", "result": result}
        if isinstance(result, dict):
            return {"success": False, "transport": "mqtt", "error": result.get("error") or result.get("message") or "Unknown error"}
        return {"success": False, "transport": "mqtt", "error": str(result)}
    except Exception as e:
        return {"success": False, "transport": "mqtt", "error": str(e)}


async def _send_led_command_http(device: Optional[dict], command: str, payload: dict) -> dict:
    """
    Fallback for devices exposing a local HTTP command endpoint.
    Expected payload shape:
    {"command":"set_color","payload":{"r":255,"g":0,"b":0,...}}
    """
    if not device:
        return {"success": False, "transport": "http", "error": "Device not found for HTTP fallback"}

    ip = device.get("ip")
    port_raw = device.get("port") or 80
    try:
        port = int(port_raw)
    except (TypeError, ValueError):
        port = 80
    if not ip:
        return {"success": False, "transport": "http", "error": "Device IP not available"}

    request_body = {"command": command, "payload": payload}
    errors = []

    timeout = aiohttp.ClientTimeout(total=3.0)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for endpoint in LED_HTTP_COMMAND_ENDPOINTS:
            url = f"http://{ip}:{port}{endpoint}"
            try:
                async with session.post(url, json=request_body) as resp:
                    raw = await resp.text()
                    if 200 <= resp.status < 300:
                        try:
                            data = json.loads(raw) if raw else {}
                        except json.JSONDecodeError:
                            data = {"raw": raw}
                        return {
                            "success": True,
                            "transport": "http",
                            "endpoint": endpoint,
                            "status": resp.status,
                            "result": data,
                        }
                    errors.append(f"{endpoint} -> HTTP {resp.status}")
            except Exception as e:
                errors.append(f"{endpoint} -> {str(e)}")

        # Fallback 2: Simple RGB controllers using query-string endpoints:
        #   GET /set?r=255&g=0&b=0
        #   GET /status
        try:
            if command == "set_color":
                r = int(payload.get("r", 0) or 0)
                g = int(payload.get("g", 0) or 0)
                b = int(payload.get("b", 0) or 0)
                power = bool(payload.get("power", True))

                # Send raw RGB + power so the ESP can implement "true power off"
                # by setting pins INPUT (high impedance) or by inverting PWM for common-anode LEDs.
                # For backward compatibility, devices can ignore unknown params.
                qs = urllib.parse.urlencode({
                    "r": r,
                    "g": g,
                    "b": b,
                    "power": 1 if power else 0,
                })
                for endpoint in LED_HTTP_QUERY_SET_ENDPOINTS:
                    url = f"http://{ip}:{port}{endpoint}?{qs}"
                    try:
                        async with session.get(url) as resp:
                            raw = await resp.text()
                            if 200 <= resp.status < 300:
                                try:
                                    data = json.loads(raw) if raw else {}
                                except json.JSONDecodeError:
                                    data = {"raw": raw}
                                return {
                                    "success": True,
                                    "transport": "http",
                                    "endpoint": endpoint,
                                    "status": resp.status,
                                    "result": data,
                                }
                            errors.append(f"{endpoint} (GET query) -> HTTP {resp.status}")
                    except Exception as e:
                        errors.append(f"{endpoint} (GET query) -> {str(e)}")

            if command == "set_power":
                on = bool(payload.get("on", True))
                # Preferred: explicit power param (lets firmware truly cut output by changing pinMode).
                qs = urllib.parse.urlencode({"power": 1 if on else 0})
                for endpoint in LED_HTTP_QUERY_SET_ENDPOINTS:
                    url = f"http://{ip}:{port}{endpoint}?{qs}"
                    try:
                        async with session.get(url) as resp:
                            raw = await resp.text()
                            if 200 <= resp.status < 300:
                                try:
                                    data = json.loads(raw) if raw else {}
                                except json.JSONDecodeError:
                                    data = {"raw": raw}
                                # Best-effort capability hint: older sketches ignore the `power` param
                                # (and don't report it in /status). Surface a warning to help users
                                # understand why "true power off" may not work.
                                warning = None
                                if not (isinstance(data, dict) and "power" in data):
                                    for s_ep in LED_HTTP_STATUS_ENDPOINTS:
                                        try:
                                            async with session.get(f"http://{ip}:{port}{s_ep}") as s_resp:
                                                if 200 <= s_resp.status < 300:
                                                    s_raw = await s_resp.text()
                                                    try:
                                                        s_data = json.loads(s_raw) if s_raw else {}
                                                    except json.JSONDecodeError:
                                                        s_data = {}
                                                    if isinstance(s_data, dict) and "power" in s_data:
                                                        warning = None
                                                        break
                                                    warning = {
                                                        "message": "Device firmware does not report/support `power` state; true GPIO cut-off may not work. Flash the project ESP firmware (esp32_rgb_minimal_common_anode)."
                                                    }
                                        except Exception:
                                            warning = {
                                                "message": "Unable to verify `power` support via /status; if on/off doesn't work, flash the project ESP firmware (esp32_rgb_minimal_common_anode)."
                                            }
                                return {
                                    "success": True,
                                    "transport": "http",
                                    "endpoint": endpoint,
                                    "status": resp.status,
                                    "result": data,
                                    **({"warning": warning} if warning else {}),
                                }
                            errors.append(f"{endpoint} (power={int(on)}) -> HTTP {resp.status}")
                    except Exception as e:
                        errors.append(f"{endpoint} (power={int(on)}) -> {str(e)}")

                # Backward compatibility: if power param isn't supported, "off" falls back to RGB=0.
                if not on:
                    qs0 = urllib.parse.urlencode({"r": 0, "g": 0, "b": 0})
                    for endpoint in LED_HTTP_QUERY_SET_ENDPOINTS:
                        url = f"http://{ip}:{port}{endpoint}?{qs0}"
                        try:
                            async with session.get(url) as resp:
                                raw = await resp.text()
                                if 200 <= resp.status < 300:
                                    try:
                                        data = json.loads(raw) if raw else {}
                                    except json.JSONDecodeError:
                                        data = {"raw": raw}
                                    return {
                                        "success": True,
                                        "transport": "http",
                                        "endpoint": endpoint,
                                        "status": resp.status,
                                        "result": data,
                                    }
                                errors.append(f"{endpoint} (compat off) -> HTTP {resp.status}")
                        except Exception as e:
                            errors.append(f"{endpoint} (compat off) -> {str(e)}")
                else:
                    # If we don't know the last color, treat "on" as a no-op success.
                    return {"success": True, "transport": "http", "endpoint": None, "status": 200, "result": {"noop": True}}
        except Exception as e:
            errors.append(f"query-fallback -> {str(e)}")

    return {
        "success": False,
        "transport": "http",
        "error": "; ".join(errors) if errors else "No HTTP LED endpoint responded",
    }

# ==================== Device Listing ====================

@router.get("/devices")
async def get_devices(user: dict = Depends(get_current_user)):
    """Get list of all discovered IoT devices."""
    return discovery_service.get_devices()

@router.post("/devices/manual")
async def add_manual_device(
    request: ManualDeviceRequest,
    user: dict = Depends(require_role("admin", "operator"))
):
    """
    Manually add a device by IP (useful when mDNS is not available).
    If `probe` is true, tries `/info` first, then LED HTTP ping to validate reachability.
    """
    ip = request.ip.strip()
    port = int(request.port)

    probe_data: dict = {}
    if request.probe:
        probe_data = await _probe_device_http(ip, port)

    suggested_id = _sanitize_device_id(request.device_id or probe_data.get("id") or f"esp-{ip.replace('.', '-')}")
    device_id = suggested_id or f"esp-{ip.replace('.', '-')}"
    name = (request.name or probe_data.get("name") or device_id).strip()

    sensors = probe_data.get("sensors") if isinstance(probe_data.get("sensors"), list) else None
    await discovery_service.add_device_manual(
        device_id=device_id,
        name=name,
        ip=ip,
        port=port,
        sensors=sensors,
    )

    device = await discovery_service.get_device(device_id)
    return {
        "success": True,
        "device_id": device_id,
        "device": device,
        "probe": probe_data if request.probe else None,
    }

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


# ==================== LED Control ====================

@router.post("/devices/{device_id}/led/color")
async def set_led_color(
    device_id: str,
    request: LedColorRequest,
    user: dict = Depends(require_role("admin", "operator"))
):
    """
    Set RGB color for an ESP LED strip/device from Pi.
    Tries MQTT first, then falls back to direct HTTP command endpoint.
    """
    payload = {
        "r": request.red,
        "g": request.green,
        "b": request.blue,
        "power": request.power,
        "persist": request.persist,
    }
    _LAST_LED_COLOR[device_id] = payload.copy()

    device = await discovery_service.get_device(device_id)

    mqtt_result = await _send_led_command_mqtt(device_id, "set_color", payload)
    if mqtt_result.get("success"):
        return mqtt_result

    http_result = await _send_led_command_http(device, "set_color", payload)
    if http_result.get("success"):
        return http_result

    raise HTTPException(
        status_code=502,
        detail={
            "message": "Failed to send LED color command",
            "mqtt_error": mqtt_result.get("error"),
            "http_error": http_result.get("error"),
        },
    )


@router.post("/devices/{device_id}/led/power")
async def set_led_power(
    device_id: str,
    request: LedPowerRequest,
    user: dict = Depends(require_role("admin", "operator"))
):
    """
    Turn LED output on/off for the device.
    Tries MQTT first, then direct HTTP fallback.
    """
    payload = {"on": request.on, "persist": request.persist}
    device = await discovery_service.get_device(device_id)

    mqtt_result = await _send_led_command_mqtt(device_id, "set_power", payload)
    if mqtt_result.get("success"):
        return mqtt_result

    # Always send explicit power command for HTTP devices.
    # Requirement: "off" must cut output drive (GPIO -> INPUT/high impedance) where supported by firmware.
    http_power = await _send_led_command_http(device, "set_power", payload)
    if not http_power.get("success"):
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Failed to send LED power command",
                "mqtt_error": mqtt_result.get("error"),
                "http_error": http_power.get("error"),
            },
        )

    # Best-effort: on power-on, restore last selected RGB (without introducing a brightness layer).
    if request.on and device_id in _LAST_LED_COLOR:
        restore_payload = _LAST_LED_COLOR[device_id].copy()
        restore_payload["power"] = True
        http_restore = await _send_led_command_http(device, "set_color", restore_payload)
        if http_restore.get("success"):
            return http_restore

        # Power-on succeeded, but restore failed; still return power result so UI can show something useful.
        http_power["warning"] = {"message": "Power-on succeeded but color restore failed", "error": http_restore.get("error")}
    return http_power

    # (No trailing raise: we return above for success, and raise earlier for failure.)
