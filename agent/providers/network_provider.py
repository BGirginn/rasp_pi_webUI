"""
Pi Agent - Network Provider (nmcli based)

Discovers and manages network interfaces (eth, wifi, bluetooth).
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional

import structlog

from .base import BaseProvider, Resource, ResourceClass, ResourceState, ActionResult

logger = structlog.get_logger(__name__)


class NetworkProvider(BaseProvider):
    """Provider for network interfaces using NetworkManager (nmcli)."""
    
    @property
    def name(self) -> str:
        return "network"
    
    async def start(self) -> None:
        """Initialize network provider."""
        self._is_healthy = True
        logger.info("Network provider initialized (nmcli)")
    
    async def stop(self) -> None:
        """Cleanup network provider."""
        pass
    
    async def discover(self) -> List[Resource]:
        """Discover network interfaces."""
        # Using simple discovery for now (stub-ish, but listing interfaces via /sys/class/net could be better)
        # For now, let's keep it minimal as API router falls back to local discovery if this returns empty.
        # But we should really implement this if we want full agent power.
        # Let's rely on the API router's fallback for interface listing for now, 
        # as the user asked for WiFi Scanning specifically.
        
        resources = []
        logger.debug("Network discovery (stub)", interfaces=len(resources))
        return resources
    
    async def get_resource(self, resource_id: str) -> Optional[Resource]:
        """Get a specific interface."""
        return self._resources.get(resource_id)
    
    async def execute_action(
        self,
        resource_id: str,
        action: str,
        params: Optional[Dict] = None
    ) -> ActionResult:
        """Execute an action on a network interface."""
        params = params or {}
        
        # WiFi-specific actions
        if action == "scan" and resource_id.startswith("wlan"):
            return await self._scan_wifi(resource_id)
        elif action == "enable":
            return await self._enable_wifi()
        elif action == "disable":
            return await self._disable_wifi()
        elif action == "status":
            return await self._get_wifi_status()
        elif action == "connect":
            return await self._connect_wifi(params.get("ssid"), params.get("password"), params.get("hidden", False))
        elif action == "disconnect":
            return await self._disconnect_wifi()
            
        return ActionResult(
            success=False,
            message=f"Action '{action}' not implemented for {resource_id}",
            error="NOT_IMPLEMENTED"
        )

    async def _run_nmcli(self, args: List[str]) -> tuple:
        """Helper to run nmcli commands."""
        cmd = ["nmcli"] + args
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode("utf-8"), stderr.decode("utf-8")

    async def _enable_wifi(self) -> ActionResult:
        """Enable WiFi radio."""
        try:
            rc, out, err = await self._run_nmcli(["radio", "wifi", "on"])
            if rc != 0:
                return ActionResult(False, f"Failed to enable WiFi: {err}", error=err)
            logger.info("WiFi enabled")
            return ActionResult(True, "WiFi enabled")
        except Exception as e:
            return ActionResult(False, str(e), error=str(e))

    async def _disable_wifi(self) -> ActionResult:
        """Disable WiFi radio."""
        try:
            rc, out, err = await self._run_nmcli(["radio", "wifi", "off"])
            if rc != 0:
                return ActionResult(False, f"Failed to disable WiFi: {err}", error=err)
            logger.info("WiFi disabled")
            return ActionResult(True, "WiFi disabled")
        except Exception as e:
            return ActionResult(False, str(e), error=str(e))

    async def _get_wifi_status(self) -> ActionResult:
        """Get WiFi status including current connection."""
        try:
            # Check radio status
            rc, out, _ = await self._run_nmcli(["radio", "wifi"])
            radio_enabled = out.strip().lower() == "enabled"
            
            # Get active connection
            rc2, out2, _ = await self._run_nmcli(["-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"])
            
            connected = False
            ssid = None
            ip = None
            
            for line in out2.strip().split("\n"):
                parts = line.split(":")
                if len(parts) >= 4 and parts[0].startswith("wlan"):
                    if parts[2] == "connected":
                        connected = True
                        ssid = parts[3]
                        # Get IP
                        rc3, out3, _ = await self._run_nmcli(["-t", "-f", "IP4.ADDRESS", "device", "show", parts[0]])
                        for ipline in out3.strip().split("\n"):
                            if ipline.startswith("IP4.ADDRESS"):
                                ip = ipline.split(":")[1].split("/")[0] if ":" in ipline else None
                        break
            
            return ActionResult(True, "Status retrieved", data={
                "radio_enabled": radio_enabled,
                "connected": connected,
                "ssid": ssid,
                "ip": ip
            })
        except Exception as e:
            return ActionResult(False, str(e), error=str(e))

    async def _connect_wifi(self, ssid: str, password: Optional[str], hidden: bool = False) -> ActionResult:
        """Connect to a WiFi network."""
        if not ssid:
            return ActionResult(False, "SSID is required", error="MISSING_SSID")
        
        try:
            # Check if connection profile exists
            rc, out, _ = await self._run_nmcli(["-t", "-f", "NAME", "connection", "show"])
            profiles = [p.strip() for p in out.strip().split("\n") if p.strip()]
            
            # If profile exists and password is provided, delete old profile to allow new credentials
            if ssid in profiles and password:
                logger.info("Deleting old profile to apply new credentials", ssid=ssid)
                await self._run_nmcli(["connection", "delete", ssid])
            elif ssid in profiles:
                # Profile exists and no new password, just activate
                rc, out, err = await self._run_nmcli(["connection", "up", ssid])
                if rc != 0:
                    return ActionResult(False, f"Activation failed: {err}", error=err)
                logger.info("WiFi activated from existing profile", ssid=ssid)
                return ActionResult(True, f"Connected to {ssid}")
            
            # Create new connection using device wifi connect
            args = ["device", "wifi", "connect", ssid]
            if password:
                args += ["password", password]
            if hidden:
                args += ["hidden", "yes"]
            rc, out, err = await self._run_nmcli(args)
            
            if rc != 0:
                return ActionResult(False, f"Connection failed: {err}", error=err)
            
            logger.info("WiFi connected", ssid=ssid)
            return ActionResult(True, f"Connected to {ssid}")
        except Exception as e:
            return ActionResult(False, str(e), error=str(e))

    async def _disconnect_wifi(self) -> ActionResult:
        """Disconnect from current WiFi."""
        try:
            # Find active WiFi device
            rc, out, _ = await self._run_nmcli(["-t", "-f", "DEVICE,TYPE,STATE", "device", "status"])
            
            wlan_device = None
            for line in out.strip().split("\n"):
                parts = line.split(":")
                if len(parts) >= 3 and parts[1] == "wifi" and parts[2] == "connected":
                    wlan_device = parts[0]
                    break
            
            if not wlan_device:
                return ActionResult(True, "No active WiFi connection")
            
            rc, out, err = await self._run_nmcli(["device", "disconnect", wlan_device])
            if rc != 0:
                return ActionResult(False, f"Disconnect failed: {err}", error=err)
            
            logger.info("WiFi disconnected", device=wlan_device)
            return ActionResult(True, "WiFi disconnected")
        except Exception as e:
            return ActionResult(False, str(e), error=str(e))
        
    async def _scan_wifi(self, interface: str) -> ActionResult:
        """Scan for WiFi networks using nmcli."""
        try:
            # nmcli -t -f SSID,BSSID,SIGNAL,BARS,SECURITY,CHAN,FREQ device wifi list
            cmd = ["nmcli", "-t", "-f", "SSID,BSSID,SIGNAL,BARS,SECURITY,CHAN,FREQ", "device", "wifi", "list"]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                err_msg = stderr.decode().strip()
                logger.error("nmcli scan failed", error=err_msg)
                return ActionResult(False, "WiFi scan failed", error=err_msg)
            
            networks = []
            output = stdout.decode("utf-8")
            
            for line in output.split("\n"):
                if not line.strip():
                    continue
                
                clean_line = line.replace("\\:", "__COLON__")
                parts = clean_line.split(":")
                
                if len(parts) < 7:
                    continue
                    
                parts = [p.replace("__COLON__", ":") for p in parts]
                
                ssid = parts[0]
                bssid = parts[1]
                try:
                    signal = int(parts[2])
                except:
                    signal = 0
                
                quality = signal
                dbm = (quality / 2) - 100
                
                networks.append({
                    "ssid": ssid,
                    "bssid": bssid,
                    "signal_strength": int(dbm),
                    "signal_quality": quality,
                    "channel": int(parts[5]) if parts[5].isdigit() else 0,
                    "frequency": parts[6],
                    "security": parts[4],
                    "connected": False
                })

            return ActionResult(True, "Scan completed", data={"networks": networks})
            
        except Exception as e:
            logger.exception("WiFi scan exception", error=str(e))
            return ActionResult(False, f"Scan failed: {str(e)}", error=str(e))
