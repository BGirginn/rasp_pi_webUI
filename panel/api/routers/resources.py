"""
Pi Control Panel - Resources Router

Handles resource discovery, management, and actions.
"""

import asyncio
import time
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from db import get_control_db
from services.agent_client import agent_client
from services.host_exec import run_host_command_simple
from .auth import get_current_user, require_role
from time_utils import utc_now

router = APIRouter()

# Service cache to avoid repeated systemctl calls (OPT-004)
_services_cache: Tuple[List, float] = ([], 0)
_CACHE_TTL_SECONDS = 5

CORE_SERVICES = {
    "caddy", "dbus", "NetworkManager", "networking", "pi-agent", "pi-control",
    "polkit", "ssh", "sshd", "systemd-journald", "systemd-logind",
    "systemd-networkd", "systemd-resolved", "tailscaled", "wpa_supplicant",
}
SYSTEM_SERVICES = {
    "avahi-daemon", "bluetooth", "cron", "systemd-timesyncd", "systemd-udevd",
}


# Pydantic models
class ResourceResponse(BaseModel):
    id: str
    name: str
    type: str
    resource_class: str
    provider: str
    state: str
    health_score: int
    managed: bool
    updated_at: str
    cpu_usage: Optional[float] = 0.0
    memory_usage: Optional[float] = 0.0
    active_state: Optional[str] = None
    sub_state: Optional[str] = None
    unit_file_state: Optional[str] = None
    allowed_actions: List[str] = Field(default_factory=list)


class ActionRequest(BaseModel):
    action: str
    params: Optional[dict] = None


class ActionResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None


# Routes
@router.get("", response_model=List[ResourceResponse])
async def list_resources(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    resource_class: Optional[str] = Query(None, description="Filter by class"),
    managed: Optional[bool] = Query(None, description="Filter by managed status"),
    refresh: bool = Query(False, description="Bypass the short-lived service cache"),
    user: dict = Depends(get_current_user)
):
    """List resources with systemd state sourced from the live host."""
    live_services = await _get_live_systemd_services(force_refresh=refresh)
    if provider in (None, "systemd"):
        filtered = live_services
        if resource_class:
            filtered = [item for item in filtered if item.resource_class == resource_class]
        if managed is not None:
            filtered = [item for item in filtered if item.managed is managed]
        if provider == "systemd":
            return filtered

    db = await get_control_db()
    
    query = "SELECT id, name, type, class, provider, state, health_score, managed, updated_at FROM resources WHERE 1=1"
    params = []
    
    if provider:
        query += " AND provider = ?"
        params.append(provider)
    
    if resource_class:
        query += " AND class = ?"
        params.append(resource_class)
    
    if managed is not None:
        query += " AND managed = ?"
        params.append(1 if managed else 0)
    
    query += " ORDER BY name"
    
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    
    stored_resources = [
        ResourceResponse(
            id=row[0],
            name=row[1],
            type=row[2],
            resource_class=row[3],
            provider=row[4],
            state=row[5],
            health_score=row[6],
            managed=bool(row[7]),
            updated_at=row[8]
        )
        for row in rows
        if row[4] != "systemd"
    ]
    return live_services + stored_resources if provider is None else stored_resources


def _classify_service(name: str) -> str:
    if name in CORE_SERVICES or name.startswith("systemd-"):
        return "CORE" if name in CORE_SERVICES else "SYSTEM"
    if name in SYSTEM_SERVICES:
        return "SYSTEM"
    return "APP"


def _state_from_systemd(active_state: str, sub_state: str = "") -> str:
    if active_state == "activating":
        return "starting"
    if active_state == "deactivating":
        return "stopping"
    if active_state == "reloading":
        return "restarting"
    if active_state == "failed":
        return "failed"
    if active_state == "active":
        return "running"
    return "stopped"


def _allowed_service_actions(resource_class: str) -> List[str]:
    if resource_class == "CORE":
        return []
    return ["start", "stop", "restart"]


async def _get_live_systemd_services(force_refresh: bool = False) -> List[ResourceResponse]:
    """Get real systemd services from the HOST system via SSH."""
    global _services_cache
    
    # Check cache first (OPT-004: avoid repeated systemctl calls)
    cached_services, cache_time = _services_cache
    if not force_refresh and cached_services and (time.time() - cache_time) < _CACHE_TTL_SECONDS:
        return cached_services
    
    # Get Usage Data first (single ps command)
    usage_map = {}
    try:
        # ps -axo unit,pcpu,pmem --no-headers
        ps_out = run_host_command_simple("ps -axo unit,pcpu,pmem --no-headers", timeout=5)
        if ps_out:
            for line in ps_out.splitlines():
                parts = line.strip().split()
                if len(parts) >= 3:
                     unit = parts[0]
                     try:
                         usage_map[unit] = {
                             "cpu": float(parts[1]),
                             "mem": float(parts[2])
                         }
                     except ValueError:
                         pass
    except (OSError, TimeoutError) as e:
        print(f"Discovery usage map error: {e}")


    services = []
    
    try:
        # Get list of ALL loaded services (running, failed, exited, loaded)
        output = run_host_command_simple(
            "systemctl list-units --type=service --all --no-pager --plain --no-legend",
            timeout=15
        )
        
        if not output:
             output = ""

        now = utc_now().isoformat()
        unit_states = {}

        # Parse loaded services (active or inactive but loaded)
        for line in output.splitlines():
             parts = line.split()
             if len(parts) < 1: continue
             
             unit_name = parts[0]
             if not unit_name.endswith(".service"): continue
             
             name = unit_name.replace(".service", "")
             active_state = parts[2] if len(parts) > 2 else "unknown"
             sub_state = parts[3] if len(parts) > 3 else ""
             unit_states[name] = {
                 "state": _state_from_systemd(active_state, sub_state),
                 "active_state": active_state,
                 "sub_state": sub_state,
                 "unit_file_state": "unknown",
             }

        unit_files = run_host_command_simple(
            "systemctl list-unit-files --type=service --no-pager --no-legend",
            timeout=15,
        )
        for line in unit_files.splitlines():
            parts = line.split()
            if parts and parts[0].endswith(".service") and "@." not in parts[0]:
                name = parts[0].removesuffix(".service")
                unit_file_state = parts[1] if len(parts) > 1 else "unknown"
                details = unit_states.setdefault(
                    name,
                    {
                        "state": "stopped",
                        "active_state": "inactive",
                        "sub_state": "dead",
                        "unit_file_state": unit_file_state,
                    },
                )
                details["unit_file_state"] = unit_file_state

        for name, details in unit_states.items():
             unit_name = f"{name}.service"
             r_class = _classify_service(name)
             state = details["state"]

             use_data = usage_map.get(unit_name, {"cpu": 0.0, "mem": 0.0})
             
             services.append(ResourceResponse(
                 id=f"systemd-{name}",
                 name=name,
                 type="service",
                 resource_class=r_class,
                 provider="systemd",
                 state=state,
                 health_score=(
                     100 if state == "running"
                     else 70 if state in {"starting", "stopping", "restarting"}
                     else 0 if state == "failed"
                     else 50
                 ),
                 managed=True,
                 updated_at=now,
                 cpu_usage=use_data["cpu"],
                 memory_usage=use_data["mem"],
                 active_state=details["active_state"],
                 sub_state=details["sub_state"],
                 unit_file_state=details["unit_file_state"],
                 allowed_actions=_allowed_service_actions(r_class),
             ))
             
        # Update cache before returning (OPT-004)
        result = sorted(services, key=lambda s: (s.resource_class != "APP", s.name))
        _services_cache = (result, time.time())
        return result

    except (OSError, TimeoutError, ValueError) as e:
        print(f"Error fetching services: {e}")
        return []


@router.get("/unmanaged", response_model=List[ResourceResponse])
async def list_unmanaged_resources(user: dict = Depends(get_current_user)):
    """List unmanaged resources (discovery queue)."""
    db = await get_control_db()
    
    cursor = await db.execute(
        """SELECT id, name, type, class, provider, state, health_score, managed, updated_at
           FROM resources WHERE managed = 0 ORDER BY discovered_at DESC"""
    )
    rows = await cursor.fetchall()
    
    return [
        ResourceResponse(
            id=row[0],
            name=row[1],
            type=row[2],
            resource_class=row[3],
            provider=row[4],
            state=row[5],
            health_score=row[6],
            managed=bool(row[7]),
            updated_at=row[8]
        )
        for row in rows
    ]


@router.get("/{resource_id}/dependencies")
async def get_resource_dependencies(
    resource_id: str,
    user: dict = Depends(get_current_user),
):
    service_name = resource_id.removeprefix("systemd-")
    if not service_name.endswith(".service"):
        service_name = f"{service_name}.service"
    try:
        return await agent_client.call(
            "resource.dependencies", {"resource_id": service_name}
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Dependency graph unavailable: {exc}")


@router.get("/{resource_id}", response_model=ResourceResponse)
async def get_resource(resource_id: str, user: dict = Depends(get_current_user)):
    """Get a specific resource."""
    db = await get_control_db()
    
    cursor = await db.execute(
        """SELECT id, name, type, class, provider, state, health_score, managed, updated_at
           FROM resources WHERE id = ?""",
        (resource_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    return ResourceResponse(
        id=row[0],
        name=row[1],
        type=row[2],
        resource_class=row[3],
        provider=row[4],
        state=row[5],
        health_score=row[6],
        managed=bool(row[7]),
        updated_at=row[8]
    )


@router.post("/{resource_id}/action", response_model=ActionResponse)
async def execute_action(
    resource_id: str,
    request: ActionRequest,
    user: dict = Depends(require_role("admin", "operator"))
):
    """Execute an action on a resource."""
    global _services_cache

    db = await get_control_db()
    
    # Get resource from DB
    cursor = await db.execute(
        "SELECT id, name, class, provider FROM resources WHERE id = ?",
        (resource_id,)
    )
    row = await cursor.fetchone()
    
    # If not in DB but it's a systemd service, allow action
    if not row and resource_id.startswith("systemd-"):
        service_name = resource_id.replace("systemd-", "")
        resource_name = service_name
        resource_class = _classify_service(service_name)
        provider = "systemd"
    elif not row:
        raise HTTPException(status_code=404, detail="Resource not found")
    else:
        resource_name, resource_class, provider = row[1], row[2], row[3]
    
    # Check CORE protection
    if resource_class == "CORE":
        raise HTTPException(
            status_code=403,
            detail="Cannot modify CORE resources"
        )
    if request.action not in _allowed_service_actions(resource_class):
        raise HTTPException(
            status_code=403,
            detail=f"Action '{request.action}' is not allowed for this resource",
        )
    
    # Execute the action based on provider type
    action_result = None
    if provider == "systemd" and resource_id.startswith("systemd-"):
        service_name = resource_id.replace("systemd-", "")
        try:
            agent_resource_id = f"{service_name}.service"
            action_result = await agent_client.execute_action(agent_resource_id, request.action, request.params)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Agent unavailable: {exc}") from exc
    else:
        # Try agent RPC for other providers
        try:
            action_result = await agent_client.execute_action(resource_id, request.action, request.params)
        except Exception:
            action_result = {"success": False, "message": "Agent unavailable"}
    
    # Audit log
    await db.execute(
        """INSERT INTO audit_log (user_id, action, resource_id, details)
           VALUES (?, ?, ?, ?)""",
        (user["id"], f"resource.{request.action}", resource_id, str(request.params))
    )
    await db.commit()
    
    if not action_result:
        raise HTTPException(status_code=500, detail="Action failed: no result returned")

    if not action_result.get("success", True):
        error_code = action_result.get("error")
        status_code = 500
        if error_code in {"ACTION_NOT_ALLOWED", "PROTECTED_RESOURCE"}:
            status_code = 403
        elif error_code == "NOT_FOUND":
            status_code = 404
        raise HTTPException(status_code=status_code, detail=action_result.get("message", "Action failed"))

    # Invalidate caches and wait briefly for systemd to settle.
    _services_cache = ([], 0)
    expected_active_state = "inactive" if request.action == "stop" else "active"
    updated_resource = None
    for _ in range(20):
        services = await _get_live_systemd_services(force_refresh=True)
        updated_resource = next((item for item in services if item.id == resource_id), None)
        if updated_resource and updated_resource.active_state == expected_active_state:
            break
        await asyncio.sleep(0.25)

    if not updated_resource or updated_resource.active_state != expected_active_state:
        raise HTTPException(
            status_code=504,
            detail=f"Service action completed but did not reach {expected_active_state}",
        )
    
    return ActionResponse(
        success=True,
        message=f"Action '{request.action}' executed on {resource_name}",
        data={
            "resource_id": resource_id,
            "action": request.action,
            "result": action_result,
            "resource": updated_resource.model_dump() if updated_resource else None,
        }
    )


@router.post("/{resource_id}/manage")
async def manage_resource(
    resource_id: str,
    resource_class: str = Query(..., description="Resource class: CORE, SYSTEM, APP, DEVICE"),
    user: dict = Depends(require_role("admin"))
):
    """Move resource from unmanaged to managed."""
    db = await get_control_db()
    
    # Validate class
    if resource_class not in ("CORE", "SYSTEM", "APP", "DEVICE"):
        raise HTTPException(status_code=400, detail="Invalid resource class")
    
    # Update resource
    result = await db.execute(
        """UPDATE resources SET managed = 1, class = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (resource_class, resource_id)
    )
    await db.commit()
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    # Audit log
    await db.execute(
        """INSERT INTO audit_log (user_id, action, resource_id, details)
           VALUES (?, ?, ?, ?)""",
        (user["id"], "resource.manage", resource_id, f"class: {resource_class}")
    )
    await db.commit()
    
    return {"message": f"Resource {resource_id} is now managed as {resource_class}"}


@router.post("/{resource_id}/ignore")
async def ignore_resource(
    resource_id: str,
    user: dict = Depends(require_role("admin"))
):
    """Permanently ignore an unmanaged resource."""
    db = await get_control_db()
    
    # Delete from resources (will be re-discovered if still exists, but marked ignored)
    # For now, just delete
    result = await db.execute(
        "DELETE FROM resources WHERE id = ? AND managed = 0",
        (resource_id,)
    )
    await db.commit()
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Unmanaged resource not found")
    
    # Audit log
    await db.execute(
        """INSERT INTO audit_log (user_id, action, resource_id)
           VALUES (?, ?, ?)""",
        (user["id"], "resource.ignore", resource_id)
    )
    await db.commit()
    
    return {"message": f"Resource {resource_id} ignored"}
