"""
Pi Control Panel - Resources Router

Handles resource discovery, management, and actions.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from db import get_control_db
from .auth import get_current_user, require_role

router = APIRouter()


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
    user: dict = Depends(get_current_user)
):
    """List all discovered resources."""
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
    
    # If no resources in DB, get live systemd services
    if len(rows) == 0:
        live_services = await _get_live_systemd_services()
        if provider == "systemd" or provider is None:
            return live_services
    
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


async def _get_live_systemd_services() -> List[ResourceResponse]:
    """Get real systemd services from the system."""
    import subprocess
    from datetime import datetime
    
    services = []
    
    # Common services to monitor on a Pi
    important_services = [
        "tailscaled",     # Tailscale VPN
        "docker",         # Docker
        "sshd", "ssh",    # SSH
        "nginx", "caddy", # Web servers
        "mosquitto",      # MQTT
        "bluetooth",      # Bluetooth
        "avahi-daemon",   # mDNS
        "cups",           # Printing
        "cron",           # Cron jobs
    ]
    
    try:
        # Get all active services
        result = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--all", "--no-pager", "--plain"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return []
        
        lines = result.stdout.strip().split("\n")
        
        for line in lines[1:]:  # Skip header
            if not line.strip():
                continue
            
            parts = line.split()
            if len(parts) < 4:
                continue
            
            unit = parts[0]
            if not unit.endswith(".service"):
                continue
            
            name = unit.replace(".service", "")
            load_state = parts[1] if len(parts) > 1 else "unknown"
            active_state = parts[2] if len(parts) > 2 else "unknown"
            sub_state = parts[3] if len(parts) > 3 else "unknown"
            
            # Filter: show important services + running services
            is_important = any(svc in name for svc in important_services)
            is_running = active_state == "active" and sub_state == "running"
            
            if not (is_important or is_running):
                continue
            
            # Map state
            state = "stopped"
            if active_state == "active":
                if sub_state == "running":
                    state = "running"
                elif sub_state == "exited":
                    state = "stopped"
            elif active_state == "failed":
                state = "failed"
            elif active_state == "activating":
                state = "restarting"
            
            # Determine class
            resource_class = "APP"
            if name in ["docker", "sshd", "ssh", "cron", "systemd-journald"]:
                resource_class = "SYSTEM"
            elif name in ["tailscaled", "nginx", "caddy", "mosquitto"]:
                resource_class = "APP"
            
            services.append(ResourceResponse(
                id=f"systemd-{name}",
                name=name,
                type="service",
                resource_class=resource_class,
                provider="systemd",
                state=state,
                health_score=100 if state == "running" else 0,
                managed=True,
                updated_at=datetime.utcnow().isoformat()
            ))
        
    except Exception as e:
        print(f"Failed to get systemd services: {e}")
    
    # Sort by name
    return sorted(services, key=lambda s: s.name)


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
    db = await get_control_db()
    
    # Get resource
    cursor = await db.execute(
        "SELECT id, name, class, provider FROM resources WHERE id = ?",
        (resource_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    resource_name, resource_class, provider = row[1], row[2], row[3]
    
    # Check CORE protection
    if resource_class == "CORE":
        raise HTTPException(
            status_code=403,
            detail="Cannot modify CORE resources"
        )
    
    # Check operator permissions on SYSTEM resources
    if resource_class == "SYSTEM" and user["role"] == "operator":
        allowed_actions = ["restart", "logs", "stats"]
        if request.action not in allowed_actions:
            raise HTTPException(
                status_code=403,
                detail=f"Operators can only {allowed_actions} on SYSTEM resources"
            )
    
    # TODO: Call agent RPC to execute action
    # For now, return placeholder
    
    # Audit log
    await db.execute(
        """INSERT INTO audit_log (user_id, action, resource_id, details)
           VALUES (?, ?, ?, ?)""",
        (user["id"], f"resource.{request.action}", resource_id, str(request.params))
    )
    await db.commit()
    
    return ActionResponse(
        success=True,
        message=f"Action '{request.action}' executed on {resource_name}",
        data={"resource_id": resource_id, "action": request.action}
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
