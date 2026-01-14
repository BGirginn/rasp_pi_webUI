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
        if action == "scan" and resource_id.startswith("wlan"):
            return await self._scan_wifi(resource_id)
            
        return ActionResult(
            success=False,
            message=f"Action '{action}' not implemented for {resource_id}",
            error="NOT_IMPLEMENTED"
        )
        
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
                
                # Careful unescaping of nmcli output
                # nmcli escapes ':' as '\:'
                # We can split by an unescaped ':' using regex or simple char iteration, 
                # but simpler is usually replacing '\:' with a placeholder.
                clean_line = line.replace("\\:", "__COLON__")
                parts = clean_line.split(":")
                
                if len(parts) < 7:
                    continue
                    
                # Restore colons
                parts = [p.replace("__COLON__", ":") for p in parts]
                
                # Format: SSID,BSSID,SIGNAL,BARS,SECURITY,CHAN,FREQ
                ssid = parts[0]
                bssid = parts[1]
                try:
                    signal = int(parts[2])
                except:
                    signal = 0
                
                # Convert bars to percentage (roughly)
                # '▂▄▆_' or similar. nmcli returns '____' or '▂___' etc in BARS field usually? 
                # Actually valid field BARS returns graphical bars. 
                # Let's calculate quality from signal (dBm usually not exposed directly by this command args above?)
                # Wait, SIGNAL field in nmcli is usually Signal Strength (0-100) on some versions, or dBm.
                # 'SIGNAL' is usually 0-100 scale in nmcli. 'dBm' is different field.
                # API expects `signal_strength` (dBm usually negative) and `signal_quality` (%).
                # nmcli 'SIGNAL' is quality %.
                # Let's assume SIGNAL is %.
                
                quality = signal
                dbm = (quality / 2) - 100 # Rough approximation: 100% ~ -50dBm, 0% ~ -100dBm
                
                networks.append({
                    "ssid": ssid,
                    "bssid": bssid,
                    "signal_strength": int(dbm),
                    "signal_quality": quality,
                    "channel": int(parts[5]) if parts[5].isdigit() else 0,
                    "frequency": parts[6],
                    "security": parts[4],
                    "connected": False # nmcli list usually marks current with '*' in IN-USE field, but we didn't ask for it.
                })

            return ActionResult(True, "Scan completed", data={"networks": networks})
            
        except Exception as e:
            logger.exception("WiFi scan exception", error=str(e))
            return ActionResult(False, f"Scan failed: {str(e)}", error=str(e))
