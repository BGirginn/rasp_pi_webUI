"""
Pi Control Panel - Agent RPC Client

Communicates with Pi Agent via Unix domain socket.
"""

import asyncio
import json
from typing import Any, Dict, Optional

import structlog

from config import settings

logger = structlog.get_logger(__name__)


class AgentClient:
    """RPC client for communicating with Pi Agent."""
    
    def __init__(self, socket_path: str = None):
        self.socket_path = socket_path or settings.agent_socket
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._request_id = 0
        self._lock = asyncio.Lock()
        self._connected = False
    
    async def connect(self) -> bool:
        """Connect to the agent socket."""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_unix_connection(self.socket_path),
                timeout=5.0
            )
            self._connected = True
            logger.info("Connected to agent", socket=self.socket_path)
            return True
        except FileNotFoundError:
            logger.warning("Agent socket not found", socket=self.socket_path)
            return False
        except asyncio.TimeoutError:
            logger.error("Agent connection timeout")
            return False
        except Exception as e:
            logger.error("Agent connection failed", error=str(e))
            return False
    
    async def disconnect(self):
        """Disconnect from the agent."""
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
        self._reader = None
        self._writer = None
        self._connected = False
    
    async def call(self, method: str, params: Optional[Dict] = None, timeout: float = 30.0) -> Any:
        """Call an RPC method on the agent."""
        async with self._lock:
            if not self._connected:
                if not await self.connect():
                    raise ConnectionError("Cannot connect to agent")
            
            self._request_id += 1
            
            request = {
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": method,
                "params": params or {}
            }
            
            try:
                # Send request
                request_bytes = json.dumps(request).encode("utf-8")
                self._writer.write(len(request_bytes).to_bytes(4, byteorder="big"))
                self._writer.write(request_bytes)
                await self._writer.drain()
                
                # Read response
                length_bytes = await asyncio.wait_for(
                    self._reader.readexactly(4),
                    timeout=timeout
                )
                length = int.from_bytes(length_bytes, byteorder="big")
                
                response_bytes = await asyncio.wait_for(
                    self._reader.readexactly(length),
                    timeout=timeout
                )
                response = json.loads(response_bytes.decode("utf-8"))
                
                if "error" in response:
                    raise Exception(f"RPC error: {response['error']}")
                
                return response.get("result")
                
            except (asyncio.TimeoutError, asyncio.IncompleteReadError, ConnectionError) as e:
                logger.error("RPC call failed", method=method, error=str(e))
                self._connected = False
                raise
    
    # Discovery methods
    async def get_snapshot(self) -> Dict:
        """Get current resource snapshot."""
        return await self.call("discovery.snapshot")
    
    async def refresh_discovery(self) -> Dict:
        """Force refresh discovery and return snapshot."""
        return await self.call("discovery.refresh")
    
    # Resource methods
    async def resource_action(self, resource_id: str, action: str, params: Dict = None) -> Dict:
        """Execute action on a resource."""
        return await self.call("resource.action", {
            "resource_id": resource_id,
            "action": action,
            "params": params or {}
        })
    
    async def get_resource_logs(self, resource_id: str, tail: int = 100) -> list:
        """Get logs for a resource."""
        return await self.call("resource.logs", {
            "resource_id": resource_id,
            "tail": tail
        })
    
    async def get_resource_stats(self, resource_id: str) -> Dict:
        """Get stats for a resource."""
        return await self.call("resource.stats", {"resource_id": resource_id})
    
    # Telemetry methods
    async def get_current_telemetry(self) -> Dict:
        """Get current telemetry snapshot."""
        return await self.call("telemetry.current")
    
    async def query_telemetry(self, metric: str, start: int, end: int) -> list:
        """Query historical telemetry."""
        return await self.call("telemetry.query", {
            "metric": metric,
            "start": start,
            "end": end
        })
    
    # Job methods
    async def run_job(self, job_type: str, name: str, config: Dict = None) -> Dict:
        """Run a job on the agent."""
        return await self.call("job.run", {
            "job_type": job_type,
            "name": name,
            "config": config or {}
        })
    
    async def get_job_status(self, job_id: str) -> Dict:
        """Get job status."""
        return await self.call("job.status", {"job_id": job_id})
    
    async def cancel_job(self, job_id: str) -> Dict:
        """Cancel a running job."""
        return await self.call("job.cancel", {"job_id": job_id})
    
    # System methods
    async def get_system_info(self) -> Dict:
        """Get system information."""
        return await self.call("system.info")
    
    async def get_health(self) -> Dict:
        """Get agent health status."""
        return await self.call("system.health")
    
    # Network methods
    async def get_network_interfaces(self) -> list:
        """Get network interfaces."""
        return await self.call("network.interfaces")
    
    async def toggle_wifi(self, enable: bool) -> Dict:
        """Toggle WiFi."""
        return await self.call("network.wifi.toggle", {"enable": enable})
    
    async def scan_wifi(self) -> list:
        """Scan for WiFi networks."""
        return await self.call("network.wifi.scan")
    
    # Device methods
    async def get_devices(self) -> list:
        """Get hardware devices."""
        return await self.call("devices.list")
    
    async def send_device_command(self, device_id: str, command: str, payload: Dict = None) -> Dict:
        """Send command to device."""
        return await self.call("devices.command", {
            "device_id": device_id,
            "command": command,
            "payload": payload or {}
        })


# Global agent client instance
agent_client = AgentClient()
