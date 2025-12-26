"""
Pi Control Panel - Devices Router

Handles hardware device management (USB, serial, GPIO, ESP via MQTT).
"""

from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from services.agent_client import agent_client
from .auth import get_current_user

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



# === Device Discovery ===

@router.get("", response_model=List[DeviceResponse])
async def list_devices(
    type: Optional[str] = Query(None, description="Filter by device type"),
    user: dict = Depends(get_current_user)
):
    """List all discovered devices."""
    try:
        # Try to get devices from agent
        devices = await agent_client.get_devices(requested_by=user)
        
        if type:
            devices = [d for d in devices if d.get("type") == type]
        
        return [DeviceResponse(**d) for d in devices]
    except Exception:
        return []




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
        devices = await agent_client.get_devices(requested_by=user)
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
        result = await agent_client.call("devices.usb.list", requested_by=user)
        return [DeviceResponse(**d) for d in result]
    except Exception:
        return []


# === ESP Devices (MQTT) ===

@router.get("/esp/list", response_model=List[DeviceResponse])
async def list_esp_devices(user: dict = Depends(get_current_user)):
    """List ESP devices connected via MQTT or HTTP."""
    try:
        result = await agent_client.call("devices.esp.list", requested_by=user)
        return [DeviceResponse(**d) for d in result]
    except Exception:
        # No ESP devices available when agent is unavailable
        # ESP devices require network discovery which needs the agent
        return []


# === GPIO ===

@router.get("/gpio/pins")
async def list_gpio_pins(user: dict = Depends(get_current_user)):
    """List GPIO pins and their current states."""
    try:
        # Try agent first
        return await agent_client.call("devices.gpio.list", requested_by=user)
    except Exception:
        return {"pins": []}


@router.get("/gpio/{pin}/read")
async def read_gpio(pin: int, user: dict = Depends(get_current_user)):
    """Read value from a GPIO pin."""
    try:
        result = await agent_client.call("devices.gpio.read", {"pin": pin}, requested_by=user)
        return result
    except Exception:
        raise HTTPException(status_code=503, detail="Agent unavailable")


# === Serial Ports ===

@router.get("/serial/ports")
async def list_serial_ports(user: dict = Depends(get_current_user)):
    """List available serial ports."""
    try:
        result = await agent_client.call("devices.serial.list", requested_by=user)
        return result
    except Exception:
        return {
            "ports": [
                {"port": "/dev/ttyUSB0", "description": "USB-Serial Adapter", "hwid": "USB VID:PID=0403:6001"},
                {"port": "/dev/ttyAMA0", "description": "Raspberry Pi UART", "hwid": "N/A"},
            ]
        }
