"""
First-Run Auth Router
Owner creation flow for initial setup.
"""

import bcrypt
import ipaddress
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from config import settings
from core.auth.first_run import is_first_run, mark_first_run_complete
from db import get_control_db

router = APIRouter()


class CreateOwnerRequest(BaseModel):
    username: str
    password: str


@router.post("/first-run/create-owner")
async def create_owner(request: CreateOwnerRequest, req: Request):
    """Create the initial owner account (first-run only)."""
    db = await get_control_db()

    if not _is_allowed_first_run_client(req):
        raise HTTPException(
            status_code=403,
            detail="First-run setup only allowed from localhost or Tailscale"
        )

    if not await is_first_run(db):
        raise HTTPException(status_code=409, detail="First-run already completed")

    cursor = await db.execute(
        "SELECT id FROM users WHERE username = ?",
        (request.username,)
    )
    if await cursor.fetchone():
        raise HTTPException(status_code=400, detail="Username already exists")

    password_hash = bcrypt.hashpw(request.password.encode(), bcrypt.gensalt()).decode()
    await db.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (request.username, password_hash, "owner")
    )
    await mark_first_run_complete(db)

    return {"success": True, "username": request.username, "role": "owner"}


def _is_allowed_first_run_client(request: Request) -> bool:
    if not request.client:
        return False

    host = request.client.host
    if host in ("localhost", "testclient"):
        return True

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False

    if ip.is_loopback:
        return True

    try:
        tailscale_net = ipaddress.ip_network(settings.tailscale_cidr)
    except ValueError:
        return False

    return ip in tailscale_net
