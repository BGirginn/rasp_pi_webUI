"""
Pi Control Panel - Devices Router

Handles hardware device management (USB, serial, GPIO, ESP via MQTT).
"""

import json
from datetime import datetime
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from db import get_control_db
from services.agent_client import agent_client
from services.sse import sse_manager, Channels
from .auth import get_current_user, require_role

router = APIRouter()


class DeviceResponse(BaseModel):
    id: str
    name: str
    type: str  # usb, serial, gpio, esp, bluetooth
    state: str  # online, offline, connected, disconnected
    vendor: Optional[str] = None
    product: Optional[str] = None
    capabilities: Optional[List[str]] = None
    telemetry: Optional[Dict] = None
    last_seen: Optional[str] = None
    metadata: Optional[Dict] = None


class DeviceCommand(BaseModel):
    command: str
    payload: Optional[Dict] = None


class GPIOConfig(BaseModel):
    pin: int
    mode: str  # input, output
    pull: Optional[str] = None  # up, down, none
    value: Optional[int] = None  # 0 or 1 for output


# === Device Discovery ===

@router.get("", response_model=List[DeviceResponse])
async def list_devices(
    type: Optional[str] = Query(None, description="Filter by device type"),
    user: dict = Depends(get_current_user)
):
    """List all discovered devices."""
    try:
        # Try to get devices from agent
        devices = await agent_client.get_devices()
        
        if type:
            devices = [d for d in devices if d.get("type") == type]
        
        return [DeviceResponse(**d) for d in devices]
    except Exception:
        # When agent is unavailable, try local discovery
        devices = await _local_device_discovery()
        
        if type:
            devices = [d for d in devices if d.type == type]
        
        return devices


async def _local_device_discovery() -> List[DeviceResponse]:
    """Fallback local device discovery when agent is unavailable."""
    import platform
    import subprocess
    import json as json_lib
    
    devices = []
    system = platform.system()
    
    # Discover USB devices locally
    if system == "Darwin":  # macOS
        try:
            result = subprocess.run(
                ["system_profiler", "SPUSBDataType", "-json"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                data = json_lib.loads(result.stdout)
                for bus in data.get("SPUSBDataType", []):
                    _parse_macos_usb(bus, devices)
        except Exception:
            pass
    
    elif system == "Linux":
        # Use lsusb for better product names
        try:
            result = subprocess.run(
                ["lsusb"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    # Parse: Bus 001 Device 002: ID 0951:1666 Kingston Technology DataTraveler 100 G3/G4/SE9 G2/50 Kyson
                    if "ID" not in line:
                        continue
                    
                    parts = line.split("ID ")
                    if len(parts) < 2:
                        continue
                    
                    id_and_name = parts[1]
                    id_parts = id_and_name.split(" ", 1)
                    if len(id_parts) < 2:
                        continue
                    
                    usb_id = id_parts[0]  # e.g., "0951:1666"
                    name = id_parts[1].strip()  # e.g., "Kingston Technology DataTraveler 100..."
                    
                    # Skip root hubs and Linux Foundation devices
                    if "root hub" in name.lower() or "Linux Foundation" in name:
                        continue
                    
                    # Extract vendor and product from name
                    vendor = name.split()[0] if name else "Unknown"
                    
                    # Check if it's a storage device
                    is_storage = any(word in name.lower() for word in ["disk", "storage", "stick", "flash", "traveler", "cruzer", "kyson"])
                    
                    devices.append(DeviceResponse(
                        id=f"usb-{usb_id.replace(':', '-')}",
                        name=name,
                        type="usb",
                        state="connected",
                        vendor=vendor,
                        capabilities=["storage", "read", "write", "eject"] if is_storage else ["read"]
                    ))
        except Exception:
            pass
    
    # Check for serial ports
    import glob
    serial_patterns = ["/dev/ttyUSB*", "/dev/ttyACM*", "/dev/cu.usbserial*", "/dev/cu.usbmodem*"]
    for pattern in serial_patterns:
        for port in glob.glob(pattern):
            port_name = port.split("/")[-1]
            devices.append(DeviceResponse(
                id=f"serial-{port_name}",
                name=f"Serial Port ({port_name})",
                type="serial",
                state="connected",
                capabilities=["serial", "read", "write"],
                metadata={"path": port}
            ))
    
    return devices


def _parse_macos_usb(node: dict, devices: list, depth: int = 0):
    """Recursively parse macOS USB tree."""
    for item in node.get("_items", []):
        name = item.get("_name", "Unknown")
        manufacturer = item.get("manufacturer", "Unknown")
        vendor_id = item.get("vendor_id", "").replace("0x", "")
        product_id = item.get("product_id", "").replace("0x", "")
        
        # Skip Apple internal devices
        if "Apple" in manufacturer and depth == 0:
            if "_items" in item:
                _parse_macos_usb(item, devices, depth + 1)
            continue
        
        # Skip hubs
        if "Hub" in name:
            if "_items" in item:
                _parse_macos_usb(item, devices, depth + 1)
            continue
        
        is_storage = any(m.get("bsd_name") for m in item.get("Media", []))
        mount_point = None
        
        if is_storage:
            for media in item.get("Media", []):
                for volume in media.get("volumes", []):
                    mount_point = volume.get("mount_point")
                    if mount_point:
                        break
        
        devices.append(DeviceResponse(
            id=f"usb-{vendor_id}-{product_id}",
            name=name,
            type="usb",
            state="connected",
            vendor=manufacturer,
            capabilities=["storage", "read", "write", "eject"] if is_storage else ["read"],
            metadata={"mount_point": mount_point} if mount_point else None
        ))
        
        if "_items" in item:
            _parse_macos_usb(item, devices, depth + 1)


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(device_id: str, user: dict = Depends(get_current_user)):
    """Get details for a specific device."""
    try:
        devices = await agent_client.get_devices()
        for device in devices:
            if device.get("id") == device_id:
                return DeviceResponse(**device)
        raise HTTPException(status_code=404, detail="Device not found")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Agent unavailable")


# === USB Devices ===

@router.get("/usb/list", response_model=List[DeviceResponse])
async def list_usb_devices(user: dict = Depends(get_current_user)):
    """List USB devices."""
    try:
        result = await agent_client.call("devices.usb.list")
        return [DeviceResponse(**d) for d in result]
    except Exception:
        # Fallback to local discovery
        all_devices = await _local_device_discovery()
        return [d for d in all_devices if d.type == "usb"]


@router.post("/usb/{device_id}/eject")
async def eject_usb(
    device_id: str,
    user: dict = Depends(require_role("admin", "operator"))
):
    """Safely eject a USB device."""
    db = await get_control_db()
    
    await db.execute(
        """INSERT INTO audit_log (user_id, action, resource_id)
           VALUES (?, ?, ?)""",
        (user["id"], "device.usb.eject", device_id)
    )
    await db.commit()
    
    try:
        await agent_client.call("devices.usb.eject", {"device_id": device_id})
        return {"message": f"USB device {device_id} ejected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === ESP Devices (MQTT) ===

@router.get("/esp/list", response_model=List[DeviceResponse])
async def list_esp_devices(user: dict = Depends(get_current_user)):
    """List ESP devices connected via MQTT or HTTP."""
    try:
        result = await agent_client.call("devices.esp.list")
        return [DeviceResponse(**d) for d in result]
    except Exception:
        # No ESP devices available when agent is unavailable
        # ESP devices require network discovery which needs the agent
        return []


@router.post("/esp/{device_id}/command")
async def send_esp_command(
    device_id: str,
    command: DeviceCommand,
    user: dict = Depends(require_role("admin", "operator"))
):
    """Send command to an ESP device."""
    db = await get_control_db()
    
    # Audit log
    await db.execute(
        """INSERT INTO audit_log (user_id, action, resource_id, details)
           VALUES (?, ?, ?, ?)""",
        (user["id"], "device.esp.command", device_id, command.command)
    )
    await db.commit()
    
    try:
        result = await agent_client.send_device_command(
            device_id, command.command, command.payload
        )
        
        # Broadcast update
        await sse_manager.broadcast(Channels.resource(device_id), "command_sent", {
            "device_id": device_id,
            "command": command.command
        })
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/esp/{device_id}/mute")
async def mute_esp_device(
    device_id: str,
    duration_minutes: int = Query(60, ge=1, le=1440),
    user: dict = Depends(require_role("admin", "operator"))
):
    """Mute telemetry from an ESP device temporarily."""
    db = await get_control_db()
    
    await db.execute(
        """INSERT INTO audit_log (user_id, action, resource_id, details)
           VALUES (?, ?, ?, ?)""",
        (user["id"], "device.esp.mute", device_id, f"{duration_minutes} minutes")
    )
    await db.commit()
    
    try:
        await agent_client.call("devices.esp.mute", {
            "device_id": device_id,
            "duration_minutes": duration_minutes
        })
        return {"message": f"Device {device_id} muted for {duration_minutes} minutes"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === GPIO ===

@router.get("/gpio/pins")
async def list_gpio_pins(user: dict = Depends(get_current_user)):
    """List GPIO pins and their current states."""
    try:
        result = await agent_client.call("devices.gpio.list")
        return result
    except Exception:
        # Return Raspberry Pi 4 GPIO layout
        return {
            "pins": [
                {"pin": 2, "mode": "output", "value": 0, "name": "LED Green"},
                {"pin": 3, "mode": "output", "value": 1, "name": "LED Red"},
                {"pin": 4, "mode": "input", "value": 0, "pull": "up", "name": "Button 1"},
                {"pin": 17, "mode": "input", "value": 0, "pull": "up", "name": "Motion Sensor"},
            ],
            "available_pins": [2, 3, 4, 5, 6, 12, 13, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]
        }


@router.post("/gpio/configure")
async def configure_gpio(
    config: GPIOConfig,
    user: dict = Depends(require_role("admin"))
):
    """Configure a GPIO pin."""
    db = await get_control_db()
    
    await db.execute(
        """INSERT INTO audit_log (user_id, action, details)
           VALUES (?, ?, ?)""",
        (user["id"], "device.gpio.configure", json.dumps(config.dict()))
    )
    await db.commit()
    
    try:
        await agent_client.call("devices.gpio.configure", config.dict())
        return {"message": f"GPIO pin {config.pin} configured"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gpio/{pin}/write")
async def write_gpio(
    pin: int,
    value: int = Query(..., ge=0, le=1),
    user: dict = Depends(require_role("admin", "operator"))
):
    """Write value to a GPIO output pin."""
    try:
        await agent_client.call("devices.gpio.write", {"pin": pin, "value": value})
        return {"message": f"GPIO {pin} set to {value}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gpio/{pin}/read")
async def read_gpio(pin: int, user: dict = Depends(get_current_user)):
    """Read value from a GPIO pin."""
    try:
        result = await agent_client.call("devices.gpio.read", {"pin": pin})
        return result
    except Exception:
        return {"pin": pin, "value": 0}


# === Serial Ports ===

@router.get("/serial/ports")
async def list_serial_ports(user: dict = Depends(get_current_user)):
    """List available serial ports."""
    try:
        result = await agent_client.call("devices.serial.list")
        return result
    except Exception:
        return {
            "ports": [
                {"port": "/dev/ttyUSB0", "description": "USB-Serial Adapter", "hwid": "USB VID:PID=0403:6001"},
                {"port": "/dev/ttyAMA0", "description": "Raspberry Pi UART", "hwid": "N/A"},
            ]
        }
