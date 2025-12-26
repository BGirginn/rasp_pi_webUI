"""
Replay protection for panel → agent requests.
"""

import asyncio
import time
from typing import Optional


class ReplayError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class ReplayCache:
    def __init__(self, ttl_seconds: int = 300):
        self._ttl_seconds = ttl_seconds
        self._nonces = {}
        self._lock = asyncio.Lock()

    async def check_and_store(self, nonce: str, now: Optional[float] = None) -> None:
        if not nonce:
            raise ReplayError("invalid_params", "nonce is required")

        now_ts = time.time() if now is None else now
        async with self._lock:
            self._prune(now_ts)
            if nonce in self._nonces:
                raise ReplayError("replay_detected", "Nonce already seen")
            self._nonces[nonce] = now_ts

    def _prune(self, now_ts: float) -> None:
        cutoff = now_ts - self._ttl_seconds
        expired = [nonce for nonce, ts in self._nonces.items() if ts < cutoff]
        for nonce in expired:
            self._nonces.pop(nonce, None)
