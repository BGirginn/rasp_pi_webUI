"""Persistent in-app and Telegram notification delivery."""

import asyncio
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import httpx
import structlog

from db import get_control_db
from services.sse import Channels, sse_manager


logger = structlog.get_logger(__name__)
SECRET_DIR = Path(os.getenv("PI_CONTROL_SECRET_DIR", "/var/lib/pi-control/secrets"))
TOKEN_FILE = SECRET_DIR / "telegram_bot_token"
CHAT_FILE = SECRET_DIR / "telegram_chat_id"


class NotificationService:
    def __init__(self):
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self._delivery_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def create(
        self,
        kind: str,
        severity: str,
        title: str,
        message: str,
        channels: Optional[List[str]] = None,
        dedupe_key: Optional[str] = None,
        resource_id: Optional[str] = None,
    ) -> str:
        db = await get_control_db()
        if dedupe_key:
            cursor = await db.execute(
                "SELECT id FROM notifications WHERE dedupe_key = ? AND resolved_at IS NULL LIMIT 1",
                (dedupe_key,),
            )
            existing = await cursor.fetchone()
            if existing:
                return existing[0]

        notification_id = str(uuid.uuid4())
        await db.execute(
            """INSERT INTO notifications
               (id, kind, severity, title, message, dedupe_key, resource_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (notification_id, kind, severity, title, message, dedupe_key, resource_id),
        )
        for channel in set(channels or ["in_app"]):
            if channel == "in_app":
                continue
            if channel not in {"telegram"}:
                continue
            await db.execute(
                """INSERT INTO notification_deliveries
                   (notification_id, channel, state, next_attempt_at)
                   VALUES (?, ?, 'pending', datetime('now'))""",
                (notification_id, channel),
            )
        await db.commit()
        await sse_manager.broadcast(Channels.ALERTS, "notification.created", {
            "id": notification_id,
            "severity": severity,
            "title": title,
            "message": message,
        })
        return notification_id

    async def resolve_dedupe(self, dedupe_key: str) -> None:
        db = await get_control_db()
        await db.execute(
            "UPDATE notifications SET resolved_at = datetime('now') WHERE dedupe_key = ? AND resolved_at IS NULL",
            (dedupe_key,),
        )
        await db.commit()

    async def configure_telegram(self, token: str, chat_id: str) -> None:
        if not token.strip() or not chat_id.strip():
            raise ValueError("Telegram token and chat ID are required")
        SECRET_DIR.mkdir(parents=True, exist_ok=True)
        os.chmod(SECRET_DIR, 0o700)
        for path, value in ((TOKEN_FILE, token.strip()), (CHAT_FILE, chat_id.strip())):
            temporary = path.with_suffix(".tmp")
            temporary.write_text(value, encoding="utf-8")
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)

    def telegram_configured(self) -> bool:
        return TOKEN_FILE.is_file() and CHAT_FILE.is_file()

    async def test_telegram(self) -> None:
        await self._send_telegram("Pi Control Telegram notification test")

    async def _delivery_loop(self) -> None:
        while True:
            try:
                await self._deliver_pending()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Notification delivery cycle failed", error=str(exc))
            await asyncio.sleep(5)

    async def _deliver_pending(self) -> None:
        db = await get_control_db()
        cursor = await db.execute(
            """SELECT d.id, d.notification_id, d.channel, d.attempts,
                      n.severity, n.title, n.message
               FROM notification_deliveries d
               JOIN notifications n ON n.id = d.notification_id
               WHERE d.state IN ('pending', 'retry')
                 AND (d.next_attempt_at IS NULL OR d.next_attempt_at <= datetime('now'))
               ORDER BY d.id LIMIT 20"""
        )
        for row in await cursor.fetchall():
            delivery_id, _, channel, attempts, severity, title, message = row
            try:
                if channel == "telegram":
                    await self._send_telegram(f"[{severity.upper()}] {title}\n{message}")
                await db.execute(
                    "UPDATE notification_deliveries SET state='delivered', attempts=attempts+1, delivered_at=datetime('now'), last_error=NULL WHERE id=?",
                    (delivery_id,),
                )
            except Exception as exc:
                attempts += 1
                delay_minutes = min(60, 2 ** min(attempts, 5))
                next_attempt = (datetime.utcnow() + timedelta(minutes=delay_minutes)).isoformat()
                state = "failed" if attempts >= 8 else "retry"
                await db.execute(
                    "UPDATE notification_deliveries SET state=?, attempts=?, last_error=?, next_attempt_at=? WHERE id=?",
                    (state, attempts, str(exc)[:500], next_attempt, delivery_id),
                )
            await db.commit()

    async def _send_telegram(self, text: str) -> None:
        if not self.telegram_configured():
            raise RuntimeError("Telegram is not configured")
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        chat_id = CHAT_FILE.read_text(encoding="utf-8").strip()
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text[:4096]},
            )
            response.raise_for_status()
            payload = response.json()
            if not payload.get("ok"):
                raise RuntimeError(payload.get("description", "Telegram delivery failed"))


notification_service = NotificationService()
