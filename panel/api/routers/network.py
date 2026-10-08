"""
Pi Control Panel - Network Router

Handles network interface management, WiFi configuration, and connectivity.
"""

import re
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field

from db import get_control_db
from services.agent_client import agent_client
from .auth import get_current_user, require_role

router = APIRouter()


class InterfaceResponse(BaseModel):
    name: str
    type: str  # ethernet, wifi, bluetooth, loopback
    status: str
    mac: Optional[str]
    ip: Optional[str]
    subnet_mask: Optional[str]
    gateway: Optional[str]
    rx_bytes: int = 0
    tx_bytes: int = 0
    speed_mbps: Optional[int] = None


class WifiNetwork(BaseModel):
    ssid: str
    bssid: str
    signal_strength: int  # dBm
    signal_quality: int  # percentage
    channel: int
    frequency: str  # 2.4GHz or 5GHz
    security: str  # open, wep, wpa, wpa2, wpa3
    connected: bool = False


class WifiConfig(BaseModel):
    ssid: str
    password: Optional[str] = None
    hidden: bool = False


class NetworkAction(BaseModel):
    action: str  # enable, disable, restart
    rollback_seconds: int = Field(default=0, ge=0, le=300)  # Auto-rollback timer


class CheckpointAction(BaseModel):
    checkpoint_id: str


class BluetoothDeviceAction(BaseModel):
    address: str


INTERFACE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]*$")


def _validate_interface_name(interface_name: str) -> None:
    if not INTERFACE_NAME_RE.fullmatch(interface_name):
        raise HTTPException(status_code=400, detail="Invalid interface name")


def _require_agent_success(result: object, operation: str) -> dict:
    if not isinstance(result, dict) or not result.get("success"):
        message = result.get("message") if isinstance(result, dict) else None
        error = result.get("error") if isinstance(result, dict) else None
        raise HTTPException(
            status_code=502,
            detail=message or error or f"Agent failed to {operation}",
        )
    return result


@router.get("/interfaces", response_model=List[InterfaceResponse])
async def list_interfaces(user: dict = Depends(get_current_user)):
    """List all network interfaces."""
    try:
        interfaces = await agent_client.get_network_interfaces()
        if interfaces:
            return interfaces
    except Exception:
        pass
    # Fallback: Get real network interfaces from local system
    return await _get_local_interfaces()


async def _get_local_interfaces() -> List[InterfaceResponse]:
    """Get network interfaces using psutil."""
    try:
        import psutil
        import socket
    except ImportError:
        return []
    
    interfaces = []
    
    # Get interface addresses
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    io_counters = psutil.net_io_counters(pernic=True)
    
    for iface_name, addr_list in addrs.items():
        # Skip loopback
        if iface_name == "lo":
            continue
        
        ip_address = None
        mac_address = None
        subnet_mask = None
        
        for addr in addr_list:
            if addr.family == socket.AF_INET:  # IPv4
                ip_address = addr.address
                subnet_mask = addr.netmask
            elif addr.family == psutil.AF_LINK:  # MAC
                mac_address = addr.address
        
        # Get interface stats
        iface_stats = stats.get(iface_name)
        is_up = iface_stats.isup if iface_stats else False
        speed = iface_stats.speed if iface_stats else None
        
        # Get IO counters
        io = io_counters.get(iface_name)
        rx_bytes = io.bytes_recv if io and is_up else 0
        tx_bytes = io.bytes_sent if io and is_up else 0
        
        # Determine interface type
        iface_type = "ethernet"
        if iface_name.startswith("wlan") or iface_name.startswith("wl"):
            iface_type = "wifi"
        elif iface_name.startswith("tailscale") or iface_name.startswith("ts"):
            iface_type = "vpn"
        elif iface_name.startswith("br-"):
            iface_type = "bridge"
        elif iface_name.startswith("veth"):
            iface_type = "virtual"
        
        # Try to get gateway for main interfaces
        gateway = None
        if ip_address:
            try:
                import subprocess
                result = subprocess.run(
                    ["ip", "route", "show", "default"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        if iface_name in line and "via" in line:
                            parts = line.split()
                            gateway = parts[parts.index("via") + 1] if "via" in parts else None
                            break
            except Exception:
                pass
        
        interfaces.append(InterfaceResponse(
            name=iface_name,
            type=iface_type,
            status="up" if is_up else "down",
            mac=mac_address,
            ip=ip_address,
            subnet_mask=subnet_mask,
            gateway=gateway,
            rx_bytes=rx_bytes,
            tx_bytes=tx_bytes,
            speed_mbps=speed if speed and speed > 0 else None
        ))
    
    # Sort: eth first, then wlan, then others
    def sort_key(iface):
        if iface.name.startswith("eth"):
            return (0, iface.name)
        elif iface.name.startswith("wlan"):
            return (1, iface.name)
        elif iface.name.startswith("tailscale"):
            return (2, iface.name)
        else:
            return (3, iface.name)
    
    return sorted(interfaces, key=sort_key)


@router.get("/interfaces/{interface_name}", response_model=InterfaceResponse)
async def get_interface(interface_name: str, user: dict = Depends(get_current_user)):
    """Get details for a specific interface."""
    _validate_interface_name(interface_name)
    interfaces = await list_interfaces(user)
    for iface in interfaces:
        candidate = iface if isinstance(iface, InterfaceResponse) else InterfaceResponse(**iface)
        if candidate.name == interface_name:
            return candidate
    raise HTTPException(status_code=404, detail="Interface not found")


@router.post("/interfaces/{interface_name}/action")
async def interface_action(
    interface_name: str,
    action: NetworkAction,
    user: dict = Depends(require_role("admin"))
):
    """Execute action on a network interface (enable/disable/restart)."""
    _validate_interface_name(interface_name)
    db = await get_control_db()
    
    if action.action not in ("enable", "disable", "restart"):
        raise HTTPException(status_code=400, detail="Invalid action")
    
    if action.action == "disable" and action.rollback_seconds <= 0:
        raise HTTPException(
            status_code=400,
            detail="Disabling an interface requires a rollback timer"
        )
    
    # Audit log
    await db.execute(
        """INSERT INTO audit_log (user_id, action, resource_id, details)
           VALUES (?, ?, ?, ?)""",
        (user["id"], f"network.{action.action}", interface_name,
         f"rollback: {action.rollback_seconds}s" if action.rollback_seconds > 0 else None)
    )
    await db.commit()
    
    # Execute action
    try:
        if action.action == "enable":
            result = await agent_client.call("network.interface.enable", {"interface": interface_name})
        elif action.action == "disable":
            result = await agent_client.call("network.interface.disable", {
                "interface": interface_name,
                "rollback_seconds": action.rollback_seconds
            })
        else:
            result = await agent_client.call("network.interface.restart", {"interface": interface_name})

        _require_agent_success(result, f"{action.action} interface {interface_name}")
        
        response = {
            "message": f"Interface {interface_name} {action.action}d",
            "rollback": action.rollback_seconds if action.action == "disable" else 0
        }
        if isinstance(result.get("data"), dict):
            response.update(result["data"])
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === WiFi ===

@router.get("/wifi/networks", response_model=List[WifiNetwork])
async def scan_wifi_networks(user: dict = Depends(get_current_user)):
    """Scan for available WiFi networks."""
    try:
        networks = await agent_client.scan_wifi()
        return [WifiNetwork(**n) for n in networks]
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"WiFi scan unavailable: {exc}")


@router.get("/wifi/status")
async def wifi_status(user: dict = Depends(get_current_user)):
    """Get current WiFi connection status."""
    try:
        result = await agent_client.call("network.wifi.status")
        return result
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"WiFi status unavailable: {exc}")


@router.post("/wifi/connect")
async def connect_wifi(
    config: WifiConfig,
    user: dict = Depends(require_role("admin"))
):
    """Connect to a WiFi network."""
    db = await get_control_db()
    
    # Audit log
    await db.execute(
        """INSERT INTO audit_log (user_id, action, details)
           VALUES (?, ?, ?)""",
        (user["id"], "network.wifi.connect", f"ssid: {config.ssid}")
    )
    await db.commit()
    
    try:
        result = await agent_client.call("network.wifi.connect", {
            "ssid": config.ssid,
            "password": config.password,
            "hidden": config.hidden
        })
        _require_agent_success(result, f"connect to WiFi {config.ssid}")
        return {"message": f"Connected to {config.ssid}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/wifi/disconnect")
async def disconnect_wifi(user: dict = Depends(require_role("admin"))):
    """Disconnect from current WiFi network."""
    db = await get_control_db()
    
    # Audit log
    await db.execute(
        """INSERT INTO audit_log (user_id, action)
           VALUES (?, ?)""",
        (user["id"], "network.wifi.disconnect")
    )
    await db.commit()
    
    try:
        result = await agent_client.call("network.wifi.disconnect")
        _require_agent_success(result, "disconnect WiFi")
        return {"message": "WiFi disconnected"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/wifi/toggle")
async def toggle_wifi(
    enable: bool = Query(...),
    rollback_seconds: int = Query(0, ge=0, le=300),
    user: dict = Depends(require_role("admin"))
):
    """Toggle WiFi with optional rollback timer."""
    if not enable and rollback_seconds <= 0:
        raise HTTPException(status_code=400, detail="Disabling WiFi requires a rollback timer")
    db = await get_control_db()
    
    action = "enable" if enable else "disable"
    
    # Audit log
    await db.execute(
        """INSERT INTO audit_log (user_id, action, details)
           VALUES (?, ?, ?)""",
        (user["id"], f"network.wifi.{action}",
         f"rollback: {rollback_seconds}s" if rollback_seconds > 0 else None)
    )
    await db.commit()
    
    try:
        result = await agent_client.toggle_wifi(enable, rollback_seconds)
        _require_agent_success(result, f"{action} WiFi")
        return {
            "message": f"WiFi {action}d",
            "rollback_in": rollback_seconds if not enable else 0,
            **(result.get("data") or {}),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Bluetooth ===

@router.get("/bluetooth/status")
async def bluetooth_status(user: dict = Depends(get_current_user)):
    """Get Bluetooth status."""
    try:
        result = await agent_client.call("network.bluetooth.status")
        return result
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Bluetooth status unavailable: {exc}")


@router.post("/bluetooth/toggle")
async def toggle_bluetooth(
    enable: bool,
    user: dict = Depends(require_role("admin"))
):
    """Toggle Bluetooth."""
    db = await get_control_db()
    
    action = "enable" if enable else "disable"
    
    await db.execute(
        """INSERT INTO audit_log (user_id, action)
           VALUES (?, ?)""",
        (user["id"], f"network.bluetooth.{action}")
    )
    await db.commit()
    
    try:
        result = await agent_client.call(f"network.bluetooth.{action}")
        _require_agent_success(result, f"{action} Bluetooth")
        return {"message": f"Bluetooth {action}d"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/bluetooth/scan")
async def scan_bluetooth(
    seconds: int = Query(8, ge=2, le=30),
    user: dict = Depends(require_role("admin")),
):
    try:
        result = await agent_client.call("network.bluetooth.scan", {"seconds": seconds})
        _require_agent_success(result, "scan Bluetooth devices")
        return result.get("data") or {"devices": []}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/bluetooth/{action}")
async def bluetooth_device_action(
    action: str,
    request: BluetoothDeviceAction,
    user: dict = Depends(require_role("admin")),
):
    if action not in {"pair", "trust", "connect", "disconnect", "remove"}:
        raise HTTPException(status_code=400, detail="Invalid Bluetooth action")
    if not re.fullmatch(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", request.address):
        raise HTTPException(status_code=400, detail="Invalid Bluetooth address")
    try:
        result = await agent_client.call(
            f"network.bluetooth.{action}", {"address": request.address.upper()}
        )
        _require_agent_success(result, f"{action} Bluetooth device")
        return {"message": result.get("message", "Bluetooth operation completed")}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.post("/checkpoints/confirm")
async def confirm_checkpoint(
    request: CheckpointAction,
    user: dict = Depends(require_role("admin")),
):
    result = await agent_client.call(
        "network.checkpoint.confirm", {"checkpoint_id": request.checkpoint_id}
    )
    _require_agent_success(result, "confirm network checkpoint")
    return {"message": result.get("message")}


@router.post("/checkpoints/rollback")
async def rollback_checkpoint(
    request: CheckpointAction,
    user: dict = Depends(require_role("admin")),
):
    result = await agent_client.call(
        "network.checkpoint.rollback", {"checkpoint_id": request.checkpoint_id}
    )
    _require_agent_success(result, "rollback network checkpoint")
    return {"message": result.get("message")}


# === Connectivity ===

@router.get("/connectivity")
async def check_connectivity(user: dict = Depends(get_current_user)):
    """Check internet and LAN connectivity."""
    try:
        result = await agent_client.call("network.connectivity.check")
        return result
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Connectivity check unavailable: {exc}")


@router.get("/dns")
async def get_dns_config(user: dict = Depends(get_current_user)):
    """Get DNS configuration."""
    try:
        result = await agent_client.call("network.dns.get")
        return result
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"DNS configuration unavailable: {exc}")
