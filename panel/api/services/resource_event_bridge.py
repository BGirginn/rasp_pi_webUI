"""Publish agent resource snapshot changes to connected SSE clients."""

import asyncio
from typing import Optional

import structlog

from services.agent_client import agent_client
from services.sse import Channels, sse_manager


logger = structlog.get_logger(__name__)


class ResourceEventBridge:
    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self._task: Optional[asyncio.Task] = None
        self._last_hash: Optional[str] = None

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                snapshot = await agent_client.call("discovery.snapshot")
                snapshot_hash = snapshot.get("hash") if isinstance(snapshot, dict) else None
                if snapshot_hash and snapshot_hash != self._last_hash:
                    initial = self._last_hash is None
                    self._last_hash = snapshot_hash
                    if not initial:
                        await sse_manager.broadcast(Channels.RESOURCES, "resources.changed", snapshot)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.debug("Resource event bridge waiting for agent", error=str(exc))
            await asyncio.sleep(self.interval)


resource_event_bridge = ResourceEventBridge()
