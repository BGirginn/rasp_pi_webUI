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
from services.agent_client import agent_client
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
    cpu_usage: Optional[float] = 0.0
    memory_usage: Optional[float] = 0.0


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
    """Get real systemd services from the HOST system via SSH."""
    from datetime import datetime
    from services.host_exec import run_host_command_simple
    
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
                     except: pass
    except Exception:
        pass

    services = []
    
    # === APP Services ===
    app_services = [
        "tailscaled", "docker", "minecraft-server", "minecraft", "home-assistant", 
        "zigbee2mqtt", "node-red", "grafana-server", "grafana", "prometheus", 
        "influxdb", "mosquitto", "nginx", "apache2", "httpd", "postgresql", 
        "postgres", "mysql", "mariadb", "redis-server", "redis", "pihole-FTL", 
        "jellyfin", "plex", "transmission-daemon", "cups", "samba", "smbd"
    ]
    
    # === SYSTEM Services ===
    system_services = [
        "ssh", "sshd", "bluetooth", "NetworkManager", "wpa_supplicant", 
        "avahi-daemon", "cron", "cronie", "rsyslog", "ntp", 
        "systemd-timesyncd", "chrony", "udev", "systemd-udevd", "dnsmasq", "dhcpcd"
    ]
    
    # === CORE Services ===
    core_services = [
        "systemd-journald", "systemd-logind", "dbus", "polkit", "systemd-resolved"
    ]
    
    try:
        # Get list of ALL loaded services (running, failed, exited, loaded)
        output = run_host_command_simple(
            "systemctl list-units --type=service --all --no-pager --plain --no-legend",
            timeout=15
        )
        
        if not output:
             output = ""

        now = datetime.utcnow().isoformat()
        processed_units = set()

        # Parse loaded services (active or inactive but loaded)
        for line in output.splitlines():
             parts = line.split()
             if len(parts) < 1: continue
             
             unit_name = parts[0]
             if not unit_name.endswith(".service"): continue
             
             name = unit_name.replace(".service", "")
             processed_units.add(name)
             
             # Determine category
             r_class = "APP" 
             if name in app_services: r_class = "APP"
             elif name in system_services: r_class = "SYSTEM"
             elif name in core_services: r_class = "CORE"
             # If not in lists but starts with systemd-, classify as SYSTEM or CORE
             elif name.startswith("systemd-"): r_class = "SYSTEM"
             
             # Filter noisy kernel/system ones if needed. 
             # If it's not in our lists and it's NOT running, we probably don't care about it (clutter).
             # If it IS running, we show it (discovery).
             active_state = parts[2] if len(parts) > 2 else "unknown"
             sub_state = parts[3] if len(parts) > 3 else "unknown"
             
             is_running = active_state == "active"
             
             if not is_running and name not in app_services and name not in system_services and name not in core_services:
                 continue

             use_data = usage_map.get(unit_name, {"cpu": 0.0, "mem": 0.0})
             
             state = "running" if is_running else "stopped"
             if active_state == "failed": state = "failed"
             
             services.append(ResourceResponse(
                 id=f"systemd-{name}",
                 name=name,
                 type="service",
                 resource_class=r_class,
                 provider="systemd",
                 state=state,
                 health_score=100 if state == "running" else (0 if state == "failed" else 50),
                 managed=True,
                 updated_at=now,
                 cpu_usage=use_data["cpu"],
                 memory_usage=use_data["mem"]
             ))
             
        # Check for important services that were NOT loaded (completely stopped/disabled)
        all_important = app_services + system_services
        missing_services = [s for s in all_important if s not in processed_units]
        
        if missing_services:
            # Check existence in batch
            check_cmd = "systemctl list-unit-files " + " ".join([f"{s}.service" for s in missing_services]) + " --no-legend"
            check_out = run_host_command_simple(check_cmd, timeout=10)
            
            if check_out:
                for line in check_out.splitlines():
                    parts = line.split()
                    if len(parts) < 1: continue
                    unit_file = parts[0]
                    if not unit_file.endswith(".service"): continue
                    
                    name = unit_file.replace(".service", "")
                    
                    # Determine category
                    r_class = "APP"
                    if name in app_services: r_class = "APP"
                    elif name in system_services: r_class = "SYSTEM"
                    
                    services.append(ResourceResponse(
                        id=f"systemd-{name}",
                        name=name,
                        type="service",
                        resource_class=r_class,
                        provider="systemd",
                        state="stopped",
                        health_score=50,
                        managed=True,
                        updated_at=now
                    ))

        return sorted(services, key=lambda s: (s.resource_class != "APP", s.name))

    except Exception as e:
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
        resource_class = "APP"
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
    
    # Check operator permissions on SYSTEM resources
    if resource_class == "SYSTEM" and user["role"] == "operator":
        allowed_actions = ["restart", "logs", "stats"]
        if request.action not in allowed_actions:
            raise HTTPException(
                status_code=403,
                detail=f"Operators can only {allowed_actions} on SYSTEM resources"
            )
    
    # Execute the action based on provider type
    action_result = None
    if provider == "systemd" and resource_id.startswith("systemd-"):
        service_name = resource_id.replace("systemd-", "")
        action_result = await _execute_systemd_action(service_name, request.action)
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
    
    if action_result and not action_result.get("success", True):
        raise HTTPException(status_code=500, detail=action_result.get("message", "Action failed"))
    
    return ActionResponse(
        success=True,
        message=f"Action '{request.action}' executed on {resource_name}",
        data={"resource_id": resource_id, "action": request.action, "result": action_result}
    )


async def _execute_systemd_action(service_name: str, action: str) -> dict:
    """Execute a systemctl action on a service."""
    import subprocess
    
    # Allowed actions
    allowed = ["start", "stop", "restart", "status"]
    if action not in allowed:
        return {"success": False, "message": f"Action '{action}' not allowed. Use: {allowed}"}
    
    # Protected services that cannot be stopped
    protected = ["sshd", "ssh", "pi-control", "systemd-journald", "dbus", "NetworkManager"]
    if action in ["stop"] and service_name in protected:
        return {"success": False, "message": f"Cannot stop protected service: {service_name}"}
    
    try:
        result = subprocess.run(
            ["/usr/bin/sudo", "/usr/bin/systemctl", action, f"{service_name}.service"],
            capture_output=True,
            text=True,
            timeout=30,
            env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin"}
        )
        
        if result.returncode == 0:
            return {
                "success": True,
                "message": f"Service {service_name} {action} successful",
                "output": result.stdout
            }
        else:
            return {
                "success": False,
                "message": f"Failed to {action} {service_name}",
                "error": result.stderr
            }
    except subprocess.TimeoutExpired:
        return {"success": False, "message": f"Timeout executing {action} on {service_name}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


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
