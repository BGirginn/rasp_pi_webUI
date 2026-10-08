"""
Pi Control Panel - Devices Router

Handles hardware device management (USB, serial, GPIO, ESP via MQTT).
"""

import asyncio
import json
from time import monotonic
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field

from db import get_control_db
from services.agent_client import agent_client
from services.sse import sse_manager, Channels
from .auth import get_current_user, require_role

router = APIRouter()

_DEVICE_CACHE_TTL_SECONDS = 3.0
_device_cache_expires_at = 0.0
_device_cache_data: Optional[List[Dict]] = None
_device_cache_lock = asyncio.Lock()


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
    storage: Optional[Dict] = None
    allowed_actions: List[str] = Field(default_factory=list)


class DeviceCommand(BaseModel):
    command: str
    payload: Optional[Dict] = None


class GPIOConfig(BaseModel):
    pin: int
    mode: str  # input, output
    pull: Optional[str] = None  # up, down, none
    value: Optional[int] = None  # 0 or 1 for output


class UsbMountRequest(BaseModel):
    volume_id: Optional[str] = None
    read_only: bool = False


class UsbFormatRequest(BaseModel):
    filesystem: str
    label: str = "PI-USB"
    confirmation: str


class UsbWriteTestRequest(BaseModel):
    volume_id: Optional[str] = None
    size_mb: int = Field(default=64, ge=1, le=1024)


# === Device Discovery ===

@router.get("", response_model=List[DeviceResponse])
async def list_devices(
    type: Optional[str] = Query(None, description="Filter by device type"),
    user: dict = Depends(get_current_user)
):
    """List all discovered devices."""
    devices = await _get_cached_devices()

    if type:
        devices = [d for d in devices if d.get("type") == type]

    return [DeviceResponse(**d) for d in devices]


def _model_to_dict(model_obj) -> Dict:
    if hasattr(model_obj, "model_dump"):
        return model_obj.model_dump()
    return model_obj.dict()


async def _fetch_devices_uncached() -> List[Dict]:
    """Fetch devices from agent with local fallback, no cache."""
    try:
        devices = await agent_client.get_devices()
        normalized = []
        for item in devices:
            device = dict(item)
            metadata = device.get("metadata") or {}
            device["storage"] = device.get("storage") or metadata.get("storage")
            device.setdefault("allowed_actions", [])
            normalized.append(device)
        return normalized
    except Exception:
        local_devices = await _local_device_discovery()
        return [_model_to_dict(d) for d in local_devices]


async def _get_cached_devices() -> List[Dict]:
    """Short-lived in-memory cache to avoid expensive discovery on bursts."""
    global _device_cache_expires_at, _device_cache_data

    now = monotonic()
    if _device_cache_data is not None and now < _device_cache_expires_at:
        return _device_cache_data

    async with _device_cache_lock:
        now = monotonic()
        if _device_cache_data is not None and now < _device_cache_expires_at:
            return _device_cache_data

        try:
            fresh_devices = await _fetch_devices_uncached()
            _device_cache_data = fresh_devices
            _device_cache_expires_at = monotonic() + _DEVICE_CACHE_TTL_SECONDS
            return _device_cache_data
        except Exception:
            # If refresh fails but we have stale data, serve stale instead of failing hard.
            if _device_cache_data is not None:
                return _device_cache_data
            raise


def _invalidate_device_cache() -> None:
    global _device_cache_expires_at
    _device_cache_expires_at = 0.0


async def _local_device_discovery() -> List[DeviceResponse]:
    """Discover devices from HOST system via SSH - OPTIMIZED single call."""
    from services.host_exec import run_host_command_simple
    import json as json_lib
    
    devices = []
    
    # Single SSH command to get all device info at once (much faster!)
    combined_cmd = "echo '===USB==='; lsusb 2>/dev/null; echo '===BLK==='; lsblk -J -o NAME,SIZE,TYPE,MODEL,TRAN 2>/dev/null; echo '===SER==='; ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null || true; echo '===END==='"
    
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
                        # Avoid double-listing the same physical USB drive both as
                        # a USB device and as a block device.
                        transport = str(dev.get("tran", "")).lower()
                        if transport == "usb":
                            continue
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
        devices = await _get_cached_devices()
        for device in devices:
            if device.get("id") == device_id:
                return DeviceResponse(**device)
        raise HTTPException(status_code=404, detail="Device not found")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Agent unavailable")


@router.post("/{device_id}/command")
async def send_device_command(
    device_id: str,
    command: DeviceCommand,
    user: dict = Depends(require_role("admin", "operator"))
):
    """
    Send command to a device.

    Currently only ESP/MQTT-style devices are commandable through this route.
    """
    db = await get_control_db()

    await db.execute(
        """INSERT INTO audit_log (user_id, action, resource_id, details)
           VALUES (?, ?, ?, ?)""",
        (user["id"], "device.command", device_id, command.command)
    )
    await db.commit()

    try:
        devices = await _get_cached_devices()
        target = next((d for d in devices if d.get("id") == device_id), None)

        if not target:
            raise HTTPException(status_code=404, detail="Device not found")

        if target.get("type") != "esp":
            raise HTTPException(
                status_code=400,
                detail="Direct command is supported only for ESP devices"
            )

        result = await agent_client.send_device_command(
            device_id, command.command, command.payload
        )

        if isinstance(result, dict) and result.get("error"):
            raise HTTPException(status_code=503, detail=result["error"])

        await sse_manager.broadcast(Channels.resource(device_id), "command_sent", {
            "device_id": device_id,
            "command": command.command
        })

        _invalidate_device_cache()

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Command failed: {str(e)}")


# === USB Devices ===

@router.get("/usb/list", response_model=List[DeviceResponse])
async def list_usb_devices(user: dict = Depends(get_current_user)):
    """List USB devices."""
    devices = await _get_cached_devices()
    return [
        DeviceResponse(**device)
        for device in devices
        if device.get("storage") or device.get("type") == "usb"
    ]


@router.post("/usb/{device_id}/eject")
async def eject_usb(
    device_id: str,
    user: dict = Depends(require_role("admin", "operator"))
):
    """Safely eject a USB device."""
    return await _execute_usb_action(device_id, "eject", {}, user)


@router.post("/usb/{device_id}/mount")
async def mount_usb(
    device_id: str,
    request: UsbMountRequest,
    user: dict = Depends(require_role("admin", "operator")),
):
    return await _execute_usb_action(device_id, "mount", request.model_dump(), user)


@router.post("/usb/{device_id}/unmount")
async def unmount_usb(
    device_id: str,
    user: dict = Depends(require_role("admin", "operator")),
):
    return await _execute_usb_action(device_id, "unmount", {}, user)


@router.post(
    "/usb/{device_id}/format",
    status_code=status.HTTP_202_ACCEPTED,
)
async def format_usb(
    device_id: str,
    request: UsbFormatRequest,
    user: dict = Depends(require_role("admin")),
):
    from .jobs import JobCreate, create_job

    job = JobCreate(
        name=f"Format USB {device_id}",
        type="usb_format",
        config={
            "device_id": device_id,
            "filesystem": request.filesystem,
            "label": request.label,
            "confirmation": request.confirmation,
        },
    )
    return await create_job(job, user)


@router.post(
    "/usb/{device_id}/write-test",
    status_code=status.HTTP_202_ACCEPTED,
)
async def write_test_usb(
    device_id: str,
    request: UsbWriteTestRequest,
    user: dict = Depends(require_role("admin", "operator")),
):
    from .jobs import JobCreate, create_job

    job = JobCreate(
        name=f"USB write test {device_id}",
        type="usb_write_test",
        config={
            "device_id": device_id,
            "volume_id": request.volume_id,
            "size_mb": request.size_mb,
        },
    )
    return await create_job(job, user)


async def prepare_usb_job_config(job_type: str, config: Dict) -> Dict:
    """Replace client block paths with the current agent-discovered identity."""
    device_id = str(config.get("device_id") or "")
    devices = await _get_cached_devices()
    target = next((item for item in devices if item.get("id") == device_id), None)
    storage = (target or {}).get("storage") or {}
    if not target or not storage:
        raise HTTPException(status_code=404, detail="USB storage device not found")
    if storage.get("transport") != "usb" or not storage.get("removable"):
        raise HTTPException(status_code=400, detail="Only removable USB disks are supported")

    sanitized = {
        key: value
        for key, value in config.items()
        if key not in {"device_path", "fingerprint"}
    }
    sanitized.update(
        {
            "device_id": device_id,
            "device_path": storage.get("device_path"),
            "fingerprint": storage.get("fingerprint"),
        }
    )
    if job_type == "usb_format":
        filesystem = str(sanitized.get("filesystem") or "").lower()
        if filesystem not in {"exfat", "fat32", "ext4"}:
            raise HTTPException(status_code=400, detail="Unsupported USB filesystem")
        if sanitized.get("confirmation") != f"ERASE {device_id}":
            raise HTTPException(status_code=400, detail=f"Type exactly: ERASE {device_id}")
    return sanitized


async def _execute_usb_action(
    device_id: str,
    action: str,
    params: Dict,
    user: dict,
):
    devices = await _get_cached_devices()
    target = next((item for item in devices if item.get("id") == device_id), None)
    if not target or not target.get("storage"):
        raise HTTPException(status_code=404, detail="USB storage device not found")
    if action not in (target.get("allowed_actions") or []):
        raise HTTPException(status_code=403, detail=f"USB action not allowed: {action}")
    try:
        result = await agent_client.execute_action(device_id, action, params)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Agent unavailable: {exc}") from exc
    if not result.get("success"):
        code = 409 if result.get("error") == "UNSAFE_DEVICE" else 500
        raise HTTPException(status_code=code, detail=result.get("message", "USB action failed"))

    db = await get_control_db()
    await db.execute(
        """INSERT INTO audit_log (user_id, action, resource_id, details)
           VALUES (?, ?, ?, ?)""",
        (user["id"], f"device.usb.{action}", device_id, json.dumps(params)),
    )
    await db.commit()
    _invalidate_device_cache()
    await sse_manager.broadcast(
        Channels.resource(device_id),
        "device_action",
        {"device_id": device_id, "action": action},
    )
    return result


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
    
    await db.execute(
        "INSERT INTO audit_log (user_id, action, details, ip_address) VALUES (?, 'device.gpio.configure', ?, '127.0.0.1')",
        (user["id"], json.dumps(config.model_dump()))
    )
    await db.commit()
    
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
