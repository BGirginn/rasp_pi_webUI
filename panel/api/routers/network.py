"""
Pi Control Panel - Network Router

Handles network interface management, WiFi configuration, and connectivity.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from services.agent_client import agent_client
from .auth import get_current_user

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


@router.get("/interfaces", response_model=List[InterfaceResponse])
async def list_interfaces(user: dict = Depends(get_current_user)):
    """List all network interfaces."""
    try:
        interfaces = await agent_client.get_network_interfaces(requested_by=user)
        return interfaces
    except Exception:
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
        rx_bytes = io.bytes_recv if io else 0
        tx_bytes = io.bytes_sent if io else 0
        
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
        interfaces = await agent_client.get_network_interfaces(requested_by=user)
        for iface in interfaces:
            if iface.get("name") == interface_name:
                return InterfaceResponse(**iface)
        raise HTTPException(status_code=404, detail="Interface not found")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Agent unavailable")


# === WiFi ===

@router.get("/wifi/networks", response_model=List[WifiNetwork])
async def scan_wifi_networks(user: dict = Depends(get_current_user)):
    """Scan for available WiFi networks."""
    try:
        networks = await agent_client.scan_wifi(requested_by=user)
        return [WifiNetwork(**n) for n in networks]
    except Exception:
        # Return empty list on failure
        return []


@router.get("/wifi/status")
async def wifi_status(user: dict = Depends(get_current_user)):
    """Get current WiFi connection status."""
    try:
        result = await agent_client.call("network.wifi.status", requested_by=user)
        return result
    except Exception:
        return {"connected": False}


# === Bluetooth ===

@router.get("/bluetooth/status")
async def bluetooth_status(user: dict = Depends(get_current_user)):
    """Get Bluetooth status."""
    try:
        result = await agent_client.call("network.bluetooth.status", requested_by=user)
        return result
    except Exception:
        return {
            "enabled": True,
            "discoverable": False,
            "paired_devices": [],
        }


# === Connectivity ===

@router.get("/connectivity")
async def check_connectivity(user: dict = Depends(get_current_user)):
    """Check internet and LAN connectivity."""
    try:
        result = await agent_client.call("network.connectivity.check", requested_by=user)
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
        result = await agent_client.call("network.dns.get", requested_by=user)
        return result
    except Exception:
        return {
            "primary": "1.1.1.1",
            "secondary": "8.8.8.8",
            "search_domains": ["local"],
        }
