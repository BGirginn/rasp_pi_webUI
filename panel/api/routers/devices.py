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
    """Discover devices from HOST system via SSH - OPTIMIZED single call."""
    from services.host_exec import run_host_command_simple
    import json as json_lib
    
    devices = []
    
    # Single SSH command to get all device info at once (much faster!)
    combined_cmd = "echo '===USB==='; lsusb 2>/dev/null; echo '===BLK==='; lsblk -J -o NAME,SIZE,TYPE,MODEL 2>/dev/null; echo '===SER==='; ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true; echo '===END==='"
    
    try:
        output = run_host_command_simple(combined_cmd, timeout=10)
        if not output:
            return []
        
        # Parse sections
        usb_section = ""
        blk_section = ""
        ser_section = ""
        
        if "===USB===" in output and "===BLK===" in output:
            usb_section = output.split("===USB===")[1].split("===BLK===")[0]
        if "===BLK===" in output and "===SER===" in output:
            blk_section = output.split("===BLK===")[1].split("===SER===")[0]
        if "===SER===" in output and "===END===" in output:
            ser_section = output.split("===SER===")[1].split("===END===")[0]
        
        # === Parse USB ===
        for line in usb_section.strip().split("\n"):
            if "ID" not in line or not line.strip():
                continue
            parts = line.split("ID ")
            if len(parts) < 2:
                continue
            id_and_name = parts[1]
            id_parts = id_and_name.split(" ", 1)
            if len(id_parts) < 2:
                continue
            usb_id = id_parts[0]
            name = id_parts[1].strip()
            if "root hub" in name.lower() or "Linux Foundation" in name:
                continue
            
            vendor = name.split()[0] if name else "Unknown"
            name_lower = name.lower()
            
            # Detect type
            if any(w in name_lower for w in ["keyboard", "kbd"]):
                dev_type, caps = "keyboard", ["input"]
            elif any(w in name_lower for w in ["mouse", "pointing"]):
                dev_type, caps = "mouse", ["input"]
            elif any(w in name_lower for w in ["disk", "storage", "flash", "traveler", "usb3", "mass"]):
                dev_type, caps = "storage", ["storage", "read", "write", "eject"]
            elif any(w in name_lower for w in ["camera", "webcam", "video"]):
                dev_type, caps = "camera", ["video"]
            elif any(w in name_lower for w in ["audio", "sound"]):
                dev_type, caps = "audio", ["audio"]
            elif "hub" in name_lower:
                dev_type, caps = "hub", ["hub"]
            else:
                dev_type, caps = "usb", ["read"]
            
            devices.append(DeviceResponse(
                id=f"usb-{usb_id.replace(':', '-')}", name=name, type=dev_type,
                state="connected", vendor=vendor, product=usb_id, capabilities=caps
            ))
        
        # === Parse Block Devices ===
        try:
            json_start = blk_section.find("{")
            if json_start >= 0:
                data = json_lib.loads(blk_section[json_start:])
                for dev in data.get("blockdevices", []):
                    if dev.get("type") == "disk":
                        name = dev.get("name", "")
                        if name.startswith("loop") or name.startswith("zram"):
                            continue
                        model = dev.get("model", "") or "Storage"
                        size = dev.get("size", "")
                        devices.append(DeviceResponse(
                            id=f"block-{name}", name=f"{model.strip()} ({size})",
                            type="disk", state="connected", capabilities=["storage", "read", "write"],
                            metadata={"path": f"/dev/{name}", "size": size}
                        ))
        except:
            pass
        
        # === Parse Serial ===
        for port in ser_section.strip().split("\n"):
            if port and port.startswith("/dev/"):
                port_name = port.split("/")[-1]
                devices.append(DeviceResponse(
                    id=f"serial-{port_name}", name=f"Serial Port ({port_name})",
                    type="serial", state="connected", capabilities=["serial", "read", "write"],
                    metadata={"path": port}
                ))
                
    except Exception as e:
        print(f"Device discovery error: {e}")
    
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

async def _get_local_gpio_status():
    """Get status of all GPIO pins using raspi-gpio."""
    from services.host_exec import run_host_command_simple
    import re
    
    # Try raspi-gpio first (common on Pi OS)
    # If not available, we return empty list to avoid crashing or lying
    try:
        output = run_host_command_simple("raspi-gpio get", timeout=2)
        if not output or "command not found" in output:
             # Fallback to reading /sys/class/gpio or pinctrl if needed
             # For now, return empty or a minimal set if tool missing
             return {"pins": [], "msg": "raspi-gpio not found"}
    except:
        return {"pins": []}

    pins = []
    # Parse output: "GPIO 2: level=1 fsel=1 func=OUTPUT pull=UP"
    # Regex might need adjustment depending on version
    for line in output.splitlines():
        match = re.search(r'GPIO (\d+): level=(\d) fsel=\d+ func=(\w+)', line)
        if match:
            pin = int(match.group(1))
            val = int(match.group(2))
            func = match.group(3)
            
            # Filter for user accessible pins (BCM 0-27 usually)
            if pin > 27: continue

            mode = "output" if func == "OUTPUT" else "input"
            # Try to grab pull if present
            pull = None
            if "pull=UP" in line: pull = "up"
            elif "pull=DOWN" in line: pull = "down"

            pins.append({
                "pin": pin,
                "mode": mode,
                "value": val,
                "pull": pull,
                "name": f"GPIO {pin}" # Default name, maybe user can alias later
            })
            
    return {"pins": pins}

@router.get("/gpio/pins")
async def list_gpio_pins(user: dict = Depends(get_current_user)):
    """List GPIO pins and their current states."""
    try:
        # Try agent first
        return await agent_client.call("devices.gpio.list")
    except Exception:
        # Fallback to local execution
        return await _get_local_gpio_status()


@router.post("/gpio/configure")
async def configure_gpio(
    config: GPIOConfig,
    user: dict = Depends(require_role("admin"))
):
    """Configure a GPIO pin."""
    from services.host_exec import run_host_command_simple
    
    db = await get_control_db()
    
    await db.run(
        "INSERT INTO audit_logs (user_id, action, details, ip_address) VALUES (:uid, 'device.gpio.configure', :details, '127.0.0.1')",
        {"uid": user["id"], "details": json.dumps(config.dict())}
    )
    
    # Execute change
    # raspi-gpio set <pin> [ip|op] [pu|pd|pn] [dh|dl]
    cmd = f"raspi-gpio set {config.pin}"
    if config.mode == "input":
        cmd += " ip"
    elif config.mode == "output":
         cmd += " op"
         
    if config.pull == "up":
        cmd += " pu"
    elif config.pull == "down":
        cmd += " pd"
        
    run_host_command_simple(cmd)
    
    return {"message": f"GPIO pin {config.pin} configured"}


@router.post("/gpio/{pin}/write")
async def write_gpio(
    pin: int,
    value: int = Query(..., ge=0, le=1),
    user: dict = Depends(require_role("admin", "operator"))
):
    """Write value to a GPIO output pin."""
    from services.host_exec import run_host_command_simple
    
    # raspi-gpio set <pin> dh (high) or dl (low)
    state = "dh" if value == 1 else "dl"
    run_host_command_simple(f"raspi-gpio set {pin} {state}")
    
    return {"message": f"GPIO {pin} set to {value}"}


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
