"""
Pi Control Panel - SSE (Server-Sent Events) Service

Provides real-time updates for telemetry, logs, and resource changes.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Set
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class SSEClient:
    """Represents a connected SSE client."""
    client_id: str
    user_id: int
    subscriptions: Set[str] = field(default_factory=set)
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)


class SSEManager:
    """Manages SSE connections and broadcasts."""
    
    def __init__(self):
        self._clients: Dict[str, SSEClient] = {}
        self._channels: Dict[str, Set[str]] = {}  # channel -> client_ids
        self._lock = asyncio.Lock()
    
    async def connect(self, client_id: str, user_id: int) -> SSEClient:
        """Register a new SSE client."""
        async with self._lock:
            client = SSEClient(client_id=client_id, user_id=user_id)
            self._clients[client_id] = client
            logger.info("SSE client connected", client_id=client_id, user_id=user_id)
            return client
    
    async def disconnect(self, client_id: str):
        """Unregister an SSE client."""
        async with self._lock:
            client = self._clients.pop(client_id, None)
            if client:
                # Remove from all channels
                for channel in client.subscriptions:
                    if channel in self._channels:
                        self._channels[channel].discard(client_id)
                logger.info("SSE client disconnected", client_id=client_id)
    
    async def subscribe(self, client_id: str, channel: str):
        """Subscribe client to a channel."""
        async with self._lock:
            if client_id not in self._clients:
                return
            
            self._clients[client_id].subscriptions.add(channel)
            
            if channel not in self._channels:
                self._channels[channel] = set()
            self._channels[channel].add(client_id)
            
            logger.debug("Client subscribed", client_id=client_id, channel=channel)
    
    async def unsubscribe(self, client_id: str, channel: str):
        """Unsubscribe client from a channel."""
        async with self._lock:
            if client_id in self._clients:
                self._clients[client_id].subscriptions.discard(channel)
            
            if channel in self._channels:
                self._channels[channel].discard(client_id)
    
    async def broadcast(self, channel: str, event: str, data: Any):
        """Broadcast message to all clients on a channel."""
        message = {
            "event": event,
            "channel": channel,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        async with self._lock:
            client_ids = self._channels.get(channel, set()).copy()
        
        for client_id in client_ids:
            client = self._clients.get(client_id)
            if client:
                try:
                    await client.queue.put(message)
                except asyncio.QueueFull:
                    logger.warning("SSE queue full", client_id=client_id)
    
    async def send_to_client(self, client_id: str, event: str, data: Any):
        """Send message to specific client."""
        client = self._clients.get(client_id)
        if client:
            message = {
                "event": event,
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            }
            await client.queue.put(message)
    
    async def event_generator(self, client: SSEClient) -> AsyncGenerator[str, None]:
        """Generate SSE events for a client."""
        try:
            while True:
                try:
                    # Wait for message with timeout
                    message = await asyncio.wait_for(client.queue.get(), timeout=30)
                    yield self._format_sse(message["event"], message["data"])
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
    
    def _format_sse(self, event: str, data: Any) -> str:
        """Format message as SSE."""
        lines = [f"event: {event}"]
        
        if isinstance(data, (dict, list)):
            lines.append(f"data: {json.dumps(data)}")
        else:
            lines.append(f"data: {data}")
        
        return "\n".join(lines) + "\n\n"
    
    @property
    def client_count(self) -> int:
        """Get number of connected clients."""
        return len(self._clients)
    
    def get_channel_clients(self, channel: str) -> int:
        """Get number of clients on a channel."""
        return len(self._channels.get(channel, set()))


# Global SSE manager instance
sse_manager = SSEManager()


# Channel constants
class Channels:
    """SSE channel names."""
    TELEMETRY = "telemetry"
    RESOURCES = "resources"
    ALERTS = "alerts"
    JOBS = "jobs"
    LOGS = "logs"
    SYSTEM = "system"
    
    @staticmethod
    def resource(resource_id: str) -> str:
        return f"resource:{resource_id}"
    
    @staticmethod
    def logs(resource_id: str) -> str:
        return f"logs:{resource_id}"
    
    @staticmethod
    def job(job_id: str) -> str:
        return f"job:{job_id}"
