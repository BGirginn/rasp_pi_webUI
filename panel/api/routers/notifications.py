"""In-app notification and Telegram configuration endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from db import get_control_db
from services.notification_service import notification_service
from services.audit_chain import row_dict
from .auth import get_current_user, require_role


router = APIRouter()


class TelegramConfig(BaseModel):
    token: str = Field(min_length=10)
    chat_id: str = Field(min_length=1, max_length=100)


@router.get("")
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    db = await get_control_db()
    where = "WHERE read_at IS NULL" if unread_only else ""
    cursor = await db.execute(
        f"""SELECT id, kind, severity, title, message, resource_id, read_at,
                   resolved_at, created_at FROM notifications {where}
            ORDER BY created_at DESC LIMIT ?""",
        (limit,),
    )
    fields = ("id", "kind", "severity", "title", "message", "resource_id", "read_at", "resolved_at", "created_at")
    return [row_dict(row, fields) for row in await cursor.fetchall()]


@router.post("/{notification_id}/read")
async def mark_read(notification_id: str, user: dict = Depends(get_current_user)):
    db = await get_control_db()
    result = await db.execute(
        "UPDATE notifications SET read_at=datetime('now') WHERE id=?", (notification_id,)
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"read": True}


@router.get("/settings/telegram")
async def telegram_status(user: dict = Depends(require_role("admin"))):
    return {"configured": notification_service.telegram_configured()}


@router.put("/settings/telegram")
async def configure_telegram(
    config: TelegramConfig,
    user: dict = Depends(require_role("admin")),
):
    await notification_service.configure_telegram(config.token, config.chat_id)
    return {"configured": True}


@router.post("/settings/telegram/test")
async def test_telegram(user: dict = Depends(require_role("admin"))):
    try:
        await notification_service.test_telegram()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"delivered": True}
