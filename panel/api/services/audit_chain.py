"""Tamper-evident hash chain for audit log rows."""

import asyncio
import hashlib
import json
from typing import Dict, Optional

from db import get_control_db


FIELDS = (
    "id", "user_id", "action", "resource_id", "resource_type", "details",
    "result", "ip_address", "user_agent", "created_at",
)


def row_dict(row, fields=FIELDS) -> Dict:
    if hasattr(row, "keys"):
        return dict(row)
    return dict(zip(fields, row))


def event_hash(row: Dict, previous_hash: str) -> str:
    payload = {field: row.get(field) for field in FIELDS}
    payload["previous_hash"] = previous_hash
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AuditChainService:
    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        await self.seal_pending()
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(1)
            await self.seal_pending()

    async def seal_pending(self) -> int:
        async with self._lock:
            db = await get_control_db()
            cursor = await db.execute(
                "SELECT event_hash FROM audit_log WHERE event_hash IS NOT NULL ORDER BY id DESC LIMIT 1"
            )
            last = await cursor.fetchone()
            previous = last[0] if last else "0" * 64
            cursor = await db.execute(
                """SELECT id, user_id, action, resource_id, resource_type, details,
                          result, ip_address, user_agent, created_at
                   FROM audit_log WHERE event_hash IS NULL ORDER BY id"""
            )
            rows = await cursor.fetchall()
            for raw in rows:
                row = row_dict(raw)
                digest = event_hash(row, previous)
                await db.execute(
                    "UPDATE audit_log SET previous_hash=?, event_hash=? WHERE id=? AND event_hash IS NULL",
                    (previous, digest, row["id"]),
                )
                previous = digest
            if rows:
                await db.commit()
            return len(rows)

    async def verify(self) -> Dict:
        await self.seal_pending()
        db = await get_control_db()
        cursor = await db.execute(
            """SELECT id, user_id, action, resource_id, resource_type, details,
                      result, ip_address, user_agent, created_at, previous_hash, event_hash
               FROM audit_log ORDER BY id"""
        )
        previous = None
        count = 0
        for raw in await cursor.fetchall():
            row = row_dict(raw, (*FIELDS, "previous_hash", "event_hash"))
            if previous is None:
                previous = row["previous_hash"] or "0" * 64
            if row["previous_hash"] != previous or row["event_hash"] != event_hash(row, previous):
                return {"valid": False, "count": count, "broken_at_id": row["id"]}
            previous = row["event_hash"]
            count += 1
        return {"valid": True, "count": count, "head_hash": previous}


audit_chain_service = AuditChainService()
