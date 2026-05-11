"""
Pi Control Panel - DNS filtering router.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from db import get_control_db
from services.adguard_home import AdGuardHomeError, adguard_home_client
from .auth import get_current_user, require_role

router = APIRouter()


class ToggleRequest(BaseModel):
    enabled: bool


class RulesRequest(BaseModel):
    blocked_domains: List[str] = Field(default_factory=list)
    allowed_domains: List[str] = Field(default_factory=list)


class DomainCheckRequest(BaseModel):
    domain: str


async def _audit(user: dict, action: str, details: str = "") -> None:
    db = await get_control_db()
    await db.execute(
        "INSERT INTO audit_log (user_id, action, resource_id, details) VALUES (?, ?, ?, ?)",
        (user["id"], action, "adguard-home", details),
    )
    await db.commit()


def _adguard_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, AdGuardHomeError):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@router.get("/status")
async def get_status(user: dict = Depends(get_current_user)):
    """Get AdGuard Home DNS filtering status."""
    return await adguard_home_client.status()


@router.post("/protection")
async def set_protection(
    request: ToggleRequest,
    user: dict = Depends(require_role("admin")),
):
    """Enable or disable global DNS protection."""
    try:
        result = await adguard_home_client.set_protection(request.enabled)
        await _audit(user, "dns_filter.protection", f"enabled={request.enabled}")
        return result
    except Exception as exc:
        raise _adguard_error(exc)


@router.post("/safebrowsing")
async def set_safebrowsing(
    request: ToggleRequest,
    user: dict = Depends(require_role("admin")),
):
    """Enable or disable safe browsing protection."""
    try:
        result = await adguard_home_client.set_safebrowsing(request.enabled)
        await _audit(user, "dns_filter.safebrowsing", f"enabled={request.enabled}")
        return result
    except Exception as exc:
        raise _adguard_error(exc)


@router.post("/parental")
async def set_parental(
    request: ToggleRequest,
    user: dict = Depends(require_role("admin")),
):
    """Enable or disable adult content filtering."""
    try:
        result = await adguard_home_client.set_parental(request.enabled)
        await _audit(user, "dns_filter.parental", f"enabled={request.enabled}")
        return result
    except Exception as exc:
        raise _adguard_error(exc)


@router.get("/rules")
async def get_rules(user: dict = Depends(get_current_user)):
    """Get panel-managed block and allow domain rules."""
    try:
        return await adguard_home_client.get_rules()
    except Exception as exc:
        raise _adguard_error(exc)


@router.put("/rules")
async def set_rules(
    request: RulesRequest,
    user: dict = Depends(require_role("admin")),
):
    """Replace panel-managed block and allow domain rules."""
    try:
        result = await adguard_home_client.set_rules(
            blocked_domains=request.blocked_domains,
            allowed_domains=request.allowed_domains,
        )
        await _audit(
            user,
            "dns_filter.rules",
            f"blocked={len(result['blocked_domains'])}; allowed={len(result['allowed_domains'])}",
        )
        return result
    except Exception as exc:
        raise _adguard_error(exc)


@router.get("/querylog")
async def get_querylog(
    limit: int = Query(50, ge=1, le=200),
    blocked_only: bool = Query(False),
    user: dict = Depends(require_role("admin")),
):
    """Get recent DNS query log entries. Query logs are browsing metadata and admin-only."""
    try:
        return await adguard_home_client.querylog(limit=limit, blocked_only=blocked_only)
    except Exception as exc:
        raise _adguard_error(exc)


@router.get("/coverage")
async def get_coverage(
    limit: int = Query(200, ge=1, le=200),
    user: dict = Depends(require_role("admin")),
):
    """Summarize recent DNS clients seen by AdGuard Home."""
    try:
        return await adguard_home_client.coverage(limit=limit)
    except Exception as exc:
        raise _adguard_error(exc)


@router.post("/check")
async def check_domain(
    request: DomainCheckRequest,
    user: dict = Depends(get_current_user),
):
    """Check whether a domain would be blocked."""
    try:
        return await adguard_home_client.check(request.domain)
    except Exception as exc:
        raise _adguard_error(exc)


@router.post("/cache/clear")
async def clear_cache(user: dict = Depends(require_role("admin"))):
    """Clear the AdGuard Home DNS cache."""
    try:
        result = await adguard_home_client.clear_cache()
        await _audit(user, "dns_filter.cache_clear")
        return result
    except Exception as exc:
        raise _adguard_error(exc)
