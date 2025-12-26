"""
Pi Control Panel - Agent RPC Client

Communicates with Pi Agent via Unix domain socket.
"""

import asyncio
import hashlib
import hmac
import json
import secrets
import ssl
import time
import uuid
from typing import Any, Dict, Optional

import structlog

from config import settings
from services.agent_tls import fingerprint_sha256, validate_server_certificate, TLSValidationError

logger = structlog.get_logger(__name__)


def canonical_json(payload: Dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sign_envelope(secret: str, envelope: Dict) -> str:
    digest = hmac.new(secret.encode("utf-8"), canonical_json(envelope).encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()


class AgentClient:
    """RPC client for communicating with Pi Agent."""
    
    def __init__(self, socket_path: str = None):
        self.socket_path = socket_path or settings.agent_socket
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._request_id = 0
        self._lock = asyncio.Lock()
        self._connected = False
        self._shared_key = None
        self._using_tls = False

    def _get_shared_key(self) -> str:
        if self._shared_key is None:
            self._shared_key = settings.get_panel_agent_shared_key()
        return self._shared_key

    def _normalize_requested_by(self, requested_by: Optional[Dict]) -> Dict:
        if not requested_by:
            return {"user_id": "system", "username": "system", "role": "system"}

        user_id = requested_by.get("user_id", requested_by.get("id", "unknown"))
        username = requested_by.get("username", "unknown")
        role = requested_by.get("role", "unknown")
        return {"user_id": user_id, "username": username, "role": role}

    def _build_envelope(self, action_id: str, params: Dict, requested_by: Optional[Dict]) -> Dict:
        envelope = {
            "action_id": action_id,
            "params": params or {},
            "requested_by": self._normalize_requested_by(requested_by),
            "request_id": str(uuid.uuid4()),
            "issued_at": int(time.time()),
            "nonce": secrets.token_hex(16),
        }
        signature = sign_envelope(self._get_shared_key(), envelope)
        envelope["signature"] = signature
        return envelope
    
    async def connect(self) -> bool:
        """Connect to the agent socket."""
        try:
            if settings.agent_rpc_host:
                if not settings.agent_rpc_use_tls:
                    raise ConnectionError("TLS required for TCP agent connections")
                await self._connect_tcp()
            else:
                if settings.agent_rpc_use_tls:
                    raise ConnectionError("AGENT_RPC_HOST required for TLS connections")
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_unix_connection(self.socket_path),
                    timeout=5.0
                )
                self._using_tls = False
            self._connected = True
            logger.info(
                "Connected to agent",
                socket=self.socket_path if not self._using_tls else None,
                host=settings.agent_rpc_host if self._using_tls else None,
                port=settings.agent_rpc_port if self._using_tls else None,
            )
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
        self._using_tls = False

    async def _connect_tcp(self) -> None:
        host = settings.agent_rpc_host
        port = settings.agent_rpc_port
        expected_fingerprints = settings.agent_tls_expected_fingerprints_list()

        if not settings.agent_tls_ca_file:
            raise ConnectionError("AGENT_TLS_CA_FILE required for TLS connections")
        if not settings.agent_tls_client_cert or not settings.agent_tls_client_key:
            raise ConnectionError("AGENT_TLS_CLIENT_CERT and AGENT_TLS_CLIENT_KEY required")

        ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=settings.agent_tls_ca_file)
        ssl_context.check_hostname = True

        ssl_context.load_cert_chain(
            certfile=settings.agent_tls_client_cert,
            keyfile=settings.agent_tls_client_key,
        )

        server_hostname = settings.agent_tls_server_name or host

        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=ssl_context, server_hostname=server_hostname),
            timeout=5.0,
        )

        ssl_object = self._writer.get_extra_info("ssl_object")
        if not ssl_object:
            raise ConnectionError("TLS connection missing ssl object")

        peer_cert = ssl_object.getpeercert()
        cert_der = ssl_object.getpeercert(binary_form=True)
        fingerprint = fingerprint_sha256(cert_der) if cert_der else ""
        try:
            validate_server_certificate(
                peer_cert,
                fingerprint,
                expected_identities=settings.agent_tls_expected_identities_list(),
                expected_fingerprints=expected_fingerprints,
            )
        except TLSValidationError as e:
            if self._writer:
                self._writer.close()
                await self._writer.wait_closed()
            raise ConnectionError(str(e))

        self._using_tls = True
    
    async def call(
        self,
        method: str,
        params: Optional[Dict] = None,
        *,
        requested_by: Optional[Dict] = None,
        timeout: float = 30.0,
    ) -> Any:
        """Call an RPC method on the agent."""
        async with self._lock:
            if not self._connected:
                if not await self.connect():
                    raise ConnectionError("Cannot connect to agent")
            
            self._request_id += 1
            envelope = self._build_envelope(method, params or {}, requested_by)

            request = {
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": method,
                "params": envelope
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
                    error = response["error"]
                    message = error.get("message", "RPC error") if isinstance(error, dict) else str(error)
                    data = error.get("data") if isinstance(error, dict) else None
                    if isinstance(data, dict) and data.get("error_code"):
                        message = f"{data['error_code']}: {message}"
                    raise Exception(f"RPC error: {message}")
                
                return response.get("result")
                
            except (asyncio.TimeoutError, asyncio.IncompleteReadError, ConnectionError) as e:
                logger.error("RPC call failed", method=method, error=str(e))
                self._connected = False
                raise
    
    # Discovery methods
    async def get_snapshot(self, requested_by: Optional[Dict] = None) -> Dict:
        """Get current resource snapshot."""
        return await self.call("discovery.snapshot", requested_by=requested_by)
    
    async def refresh_discovery(self, requested_by: Optional[Dict] = None) -> Dict:
        """Force refresh discovery and return snapshot."""
        return await self.call("discovery.refresh", requested_by=requested_by)
    
    # Resource methods
    async def resource_action(
        self,
        resource_id: str,
        action: str,
        params: Dict = None,
        requested_by: Optional[Dict] = None,
    ) -> Dict:
        """Execute action on a resource."""
        return await self.call("resource.action", {
            "resource_id": resource_id,
            "action": action,
            "params": params or {}
        }, requested_by=requested_by)
    
    async def get_resource_logs(
        self,
        resource_id: str,
        tail: int = 100,
        requested_by: Optional[Dict] = None,
    ) -> list:
        """Get logs for a resource."""
        return await self.call("resource.logs", {
            "resource_id": resource_id,
            "tail": tail
        }, requested_by=requested_by)
    
    async def get_resource_stats(
        self,
        resource_id: str,
        requested_by: Optional[Dict] = None,
    ) -> Dict:
        """Get stats for a resource."""
        return await self.call("resource.stats", {"resource_id": resource_id}, requested_by=requested_by)
    
    # Telemetry methods
    async def get_current_telemetry(self, requested_by: Optional[Dict] = None) -> Dict:
        """Get current telemetry snapshot."""
        return await self.call("telemetry.current", requested_by=requested_by)

    async def get_telemetry(self, requested_by: Optional[Dict] = None) -> Dict:
        """Backward-compatible alias for current telemetry."""
        return await self.get_current_telemetry(requested_by=requested_by)
    
    async def query_telemetry(
        self,
        metric: str,
        start: int,
        end: int,
        requested_by: Optional[Dict] = None,
    ) -> list:
        """Query historical telemetry."""
        return await self.call("telemetry.query", {
            "metric": metric,
            "start": start,
            "end": end
        }, requested_by=requested_by)
    
    # Job methods
    async def run_job(
        self,
        job_type: str,
        name: str,
        config: Dict = None,
        requested_by: Optional[Dict] = None,
    ) -> Dict:
        """Run a job on the agent."""
        return await self.call("job.run", {
            "job_type": job_type,
            "name": name,
            "config": config or {}
        }, requested_by=requested_by)
    
    async def get_job_status(self, job_id: str, requested_by: Optional[Dict] = None) -> Dict:
        """Get job status."""
        return await self.call("job.status", {"job_id": job_id}, requested_by=requested_by)
    
    async def cancel_job(self, job_id: str, requested_by: Optional[Dict] = None) -> Dict:
        """Cancel a running job."""
        return await self.call("job.cancel", {"job_id": job_id}, requested_by=requested_by)
    
    # System methods
    async def get_system_info(self, requested_by: Optional[Dict] = None) -> Dict:
        """Get system information."""
        return await self.call("system.info", requested_by=requested_by)
    
    async def get_health(self, requested_by: Optional[Dict] = None) -> Dict:
        """Get agent health status."""
        return await self.call("system.health", requested_by=requested_by)
    
    # Network methods
    async def get_network_interfaces(self, requested_by: Optional[Dict] = None) -> list:
        """Get network interfaces."""
        return await self.call("network.interfaces", requested_by=requested_by)
    
    async def toggle_wifi(self, enable: bool, requested_by: Optional[Dict] = None) -> Dict:
        """Toggle WiFi."""
        return await self.call("network.wifi.toggle", {"enable": enable}, requested_by=requested_by)
    
    async def scan_wifi(self, requested_by: Optional[Dict] = None) -> list:
        """Scan for WiFi networks."""
        return await self.call("network.wifi.scan", requested_by=requested_by)
    
    # Device methods
    async def get_devices(self, requested_by: Optional[Dict] = None) -> list:
        """Get hardware devices."""
        return await self.call("devices.list", requested_by=requested_by)
    
    async def send_device_command(
        self,
        device_id: str,
        command: str,
        payload: Dict = None,
        requested_by: Optional[Dict] = None,
    ) -> Dict:
        """Send command to device."""
        return await self.call("devices.command", {
            "device_id": device_id,
            "command": command,
            "payload": payload or {}
        }, requested_by=requested_by)


# Global agent client instance
agent_client = AgentClient()
