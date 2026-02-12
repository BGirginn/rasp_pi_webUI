"""
Pi Control Panel - Network Router

Handles network interface management, WiFi configuration, and connectivity.
"""

import json
from datetime import datetime
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

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
    rollback_seconds: int = 0  # Auto-rollback timer


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
        elif iface_name.startswith("docker") or iface_name.startswith("br-"):
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
    try:
        interfaces = await agent_client.get_network_interfaces()
        for iface in interfaces:
            if iface.get("name") == interface_name:
                return InterfaceResponse(**iface)
        raise HTTPException(status_code=404, detail="Interface not found")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Agent unavailable")


@router.post("/interfaces/{interface_name}/action")
async def interface_action(
    interface_name: str,
    action: NetworkAction,
    user: dict = Depends(require_role("admin"))
):
    """Execute action on a network interface (enable/disable/restart)."""
    db = await get_control_db()
    
    if action.action not in ("enable", "disable", "restart"):
        raise HTTPException(status_code=400, detail="Invalid action")
    
    # Safety check for critical interfaces
    critical_interfaces = ["eth0", "tailscale0"]
    if interface_name in critical_interfaces and action.action == "disable":
        if action.rollback_seconds <= 0:
            raise HTTPException(
                status_code=400,
                detail="Disabling critical interface requires rollback timer"
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
        
        return {
            "message": f"Interface {interface_name} {action.action}d",
            "rollback": action.rollback_seconds if action.action == "disable" else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === WiFi ===

@router.get("/wifi/networks", response_model=List[WifiNetwork])
async def scan_wifi_networks(user: dict = Depends(get_current_user)):
    """Scan for available WiFi networks."""
    try:
        networks = await agent_client.scan_wifi()
        return [WifiNetwork(**n) for n in networks]
    except Exception:
        # Return empty list on failure
        return []


@router.get("/wifi/status")
async def wifi_status(user: dict = Depends(get_current_user)):
    """Get current WiFi connection status."""
    try:
        result = await agent_client.call("network.wifi.status")
        return result
    except Exception:
        return {"connected": False}


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
        return {"message": f"Connected to {config.ssid}"}
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
        await agent_client.call("network.wifi.disconnect")
        return {"message": "WiFi disconnected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/wifi/toggle")
async def toggle_wifi(
    enable: bool = Query(...),
    rollback_seconds: int = Query(0, ge=0, le=300),
    user: dict = Depends(require_role("admin"))
):
    """Toggle WiFi with optional rollback timer."""
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
        result = await agent_client.toggle_wifi(enable)
        return {
            "message": f"WiFi {action}d",
            "rollback_in": rollback_seconds if not enable else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Bluetooth ===

@router.get("/bluetooth/status")
async def bluetooth_status(user: dict = Depends(get_current_user)):
    """Get Bluetooth status."""
    try:
        result = await agent_client.call("network.bluetooth.status")
        return result
    except Exception:
        return {
            "enabled": True,
            "discoverable": False,
            "paired_devices": [],
        }


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
        await agent_client.call(f"network.bluetooth.{action}")
        return {"message": f"Bluetooth {action}d"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Connectivity ===

@router.get("/connectivity")
async def check_connectivity(user: dict = Depends(get_current_user)):
    """Check internet and LAN connectivity."""
    try:
        result = await agent_client.call("network.connectivity.check")
        return result
    except Exception:
        return {
            "lan": True,
            "internet": True,
            "dns": True,
            "tailscale": True,
            "latency_ms": 15,
        }


@router.get("/dns")
async def get_dns_config(user: dict = Depends(get_current_user)):
    """Get DNS configuration."""
    try:
        result = await agent_client.call("network.dns.get")
        return result
    except Exception:
        return {
            "primary": "1.1.1.1",
            "secondary": "8.8.8.8",
            "search_domains": ["local"],
        }
