"""
Pi Agent - Unix Socket RPC Server

Handles JSON-RPC requests from Panel API over Unix domain socket.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)


class SocketServer:
    """Unix domain socket server for RPC communication."""
    
    def __init__(
        self,
        socket_path: str,
        handler: Callable[[str, Dict], Any],
        permissions: str = "0660",
        group: Optional[str] = None
    ):
        self.socket_path = socket_path
        self.handler = handler
        self.permissions = int(permissions, 8)
        self.group = group
        
        self._server: Optional[asyncio.Server] = None
        self._is_running = False
    
    @property
    def is_running(self) -> bool:
        return self._is_running
    
    async def start(self) -> None:
        """Start the socket server."""
        # Ensure socket directory exists
        socket_dir = Path(self.socket_path).parent
        socket_dir.mkdir(parents=True, exist_ok=True)
        
        # Remove existing socket file
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        # Start server
        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=self.socket_path
        )
        
        # Set ownership if group is specified
        if self.group:
            try:
                import grp
                gid = grp.getgrnam(self.group).gr_gid
                os.chown(self.socket_path, -1, gid)
                logger.debug("Socket group set", group=self.group, gid=gid)
            except Exception as e:
                logger.warning("Failed to set socket group", group=self.group, error=str(e))

        # Set permissions
        os.chmod(self.socket_path, self.permissions)
        
        self._is_running = True
        logger.info("Socket server started", path=self.socket_path)
    
    async def stop(self) -> None:
        """Stop the socket server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        
        # Cleanup socket file
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        self._is_running = False
        logger.info("Socket server stopped")
    
    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ) -> None:
        """Handle incoming client connection."""
        peer = writer.get_extra_info("peername") or "unknown"
        logger.debug("Client connected", peer=peer)
        
        try:
            while True:
                # Read message length (4 bytes, big-endian)
                length_bytes = await reader.readexactly(4)
                length = int.from_bytes(length_bytes, byteorder="big")
                
                if length > 10 * 1024 * 1024:  # 10MB limit
                    logger.warning("Message too large", length=length)
                    break
                
                # Read message
                message_bytes = await reader.readexactly(length)
                message = message_bytes.decode("utf-8")
                
                # Parse JSON-RPC request
                try:
                    request = json.loads(message)
                except json.JSONDecodeError as e:
                    response = self._error_response(None, -32700, f"Parse error: {e}")
                else:
                    response = await self._process_request(request)
                
                # Send response
                response_bytes = json.dumps(response).encode("utf-8")
                writer.write(len(response_bytes).to_bytes(4, byteorder="big"))
                writer.write(response_bytes)
                await writer.drain()
                
        except asyncio.IncompleteReadError:
            logger.debug("Client disconnected", peer=peer)
        except Exception as e:
            logger.exception("Client handler error", peer=peer, error=str(e))
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def _process_request(self, request: Dict) -> Dict:
        """Process a JSON-RPC request."""
        # Validate request
        if not isinstance(request, dict):
            return self._error_response(None, -32600, "Invalid Request")
        
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})
        
        if not method:
            return self._error_response(request_id, -32600, "Method required")
        
        if not isinstance(method, str):
            return self._error_response(request_id, -32600, "Method must be string")
        
        if params and not isinstance(params, dict):
            return self._error_response(request_id, -32602, "Params must be object")
        
        # Call handler
        try:
            result = await self.handler(method, params or {})
            
            if isinstance(result, dict) and "error" in result:
                return self._error_response(
                    request_id,
                    -32000,
                    result["error"]
                )
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result.get("result") if isinstance(result, dict) else result
            }
            
        except Exception as e:
            logger.exception("Handler error", method=method, error=str(e))
            return self._error_response(request_id, -32603, f"Internal error: {e}")
    
    def _error_response(self, request_id: Any, code: int, message: str) -> Dict:
        """Create JSON-RPC error response."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        }


class SocketClient:
    """Unix domain socket client for RPC communication."""
    
    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._request_id = 0
    
    async def connect(self) -> None:
        """Connect to the socket server."""
        self._reader, self._writer = await asyncio.open_unix_connection(
            self.socket_path
        )
        logger.debug("Connected to socket", path=self.socket_path)
    
    async def disconnect(self) -> None:
        """Disconnect from the socket server."""
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
        self._reader = None
        self._writer = None
    
    async def call(self, method: str, params: Optional[Dict] = None) -> Any:
        """Call a remote method."""
        if not self._writer or not self._reader:
            await self.connect()
        
        self._request_id += 1
        
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {}
        }
        
        # Send request
        request_bytes = json.dumps(request).encode("utf-8")
        self._writer.write(len(request_bytes).to_bytes(4, byteorder="big"))
        self._writer.write(request_bytes)
        await self._writer.drain()
        
        # Read response
        length_bytes = await self._reader.readexactly(4)
        length = int.from_bytes(length_bytes, byteorder="big")
        
        response_bytes = await self._reader.readexactly(length)
        response = json.loads(response_bytes.decode("utf-8"))
        
        if "error" in response:
            raise Exception(f"RPC error: {response['error']['message']}")
        
        return response.get("result")
