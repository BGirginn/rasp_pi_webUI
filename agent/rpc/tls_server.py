"""
Pi Agent - TLS TCP RPC Server

Handles JSON-RPC requests from Panel API over mTLS.
"""

import asyncio
import json
from typing import Any, Callable, Dict, Optional

import structlog

from security.mtls import fingerprint_sha256

logger = structlog.get_logger(__name__)


class TLSSocketServer:
    """TCP TLS server for RPC communication."""

    def __init__(
        self,
        host: str,
        port: int,
        handler: Callable[[str, Dict, Optional[Dict]], Any],
        ssl_context,
        client_validator: Optional[Callable[[Dict, str], None]] = None,
    ):
        self.host = host
        self.port = port
        self.handler = handler
        self.ssl_context = ssl_context
        self.client_validator = client_validator

        self._server: Optional[asyncio.AbstractServer] = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client,
            host=self.host,
            port=self.port,
            ssl=self.ssl_context,
        )
        self._is_running = True
        logger.info("TLS RPC server started", host=self.host, port=self.port)

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        self._is_running = False
        logger.info("TLS RPC server stopped")

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        peer = writer.get_extra_info("peername") or "unknown"
        ssl_object = writer.get_extra_info("ssl_object")
        client_info = {
            "peer": peer,
            "transport": "tls",
            "mtls_authenticated": False,
        }

        try:
            if not ssl_object:
                logger.warning("TLS client missing ssl object", peer=peer)
                writer.close()
                await writer.wait_closed()
                return

            peer_cert = ssl_object.getpeercert()
            cert_der = ssl_object.getpeercert(binary_form=True)
            fingerprint = fingerprint_sha256(cert_der) if cert_der else ""

            if self.client_validator:
                self.client_validator(peer_cert, fingerprint)

            client_info.update(
                {
                    "mtls_authenticated": True,
                    "peer_cert": peer_cert,
                    "fingerprint": fingerprint,
                }
            )

            logger.debug("TLS client connected", peer=peer)

            while True:
                length_bytes = await reader.readexactly(4)
                length = int.from_bytes(length_bytes, byteorder="big")

                if length > 10 * 1024 * 1024:
                    logger.warning("Message too large", length=length, peer=peer)
                    break

                message_bytes = await reader.readexactly(length)
                message = message_bytes.decode("utf-8")

                try:
                    request = json.loads(message)
                except json.JSONDecodeError as e:
                    response = self._error_response(None, -32700, f"Parse error: {e}")
                else:
                    response = await self._process_request(request, client_info)

                response_bytes = json.dumps(response).encode("utf-8")
                writer.write(len(response_bytes).to_bytes(4, byteorder="big"))
                writer.write(response_bytes)
                await writer.drain()

        except asyncio.IncompleteReadError:
            logger.debug("TLS client disconnected", peer=peer)
        except Exception as e:
            logger.exception("TLS client handler error", peer=peer, error=str(e))
        finally:
            writer.close()
            await writer.wait_closed()

    async def _process_request(self, request: Dict, client_info: Optional[Dict]) -> Dict:
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

        try:
            result = await self.handler(method, params or {}, client_info)

            if isinstance(result, dict) and "error" in result:
                error = result["error"]
                if isinstance(error, dict):
                    data = error.get("data")
                    error_code = error.get("code")
                    if error_code:
                        data = data or {}
                        data["error_code"] = error_code
                    return self._error_response(
                        request_id,
                        -32000,
                        error.get("message", "RPC error"),
                        data=data,
                    )
                return self._error_response(request_id, -32000, str(error))

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result.get("result") if isinstance(result, dict) else result,
            }

        except Exception as e:
            logger.exception("Handler error", method=method, error=str(e))
            return self._error_response(request_id, -32603, "Internal error")

    def _error_response(
        self,
        request_id: Any,
        code: int,
        message: str,
        data: Optional[Dict] = None,
    ) -> Dict:
        error = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message,
            },
        }
        if data is not None:
            error["error"]["data"] = data
        return error
