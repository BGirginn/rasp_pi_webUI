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
    
    services = []
    
    # === APP Services (user can start/stop/restart) ===
    app_services = [
        "tailscaled",      # Tailscale VPN
        "docker",          # Docker
        "minecraft-server", "minecraft",  # Minecraft
        "home-assistant",  # Home Assistant
        "zigbee2mqtt",     # Zigbee
        "node-red",        # Node-RED
        "grafana-server", "grafana",  # Grafana
        "prometheus",      # Prometheus
        "influxdb",        # InfluxDB
        "mosquitto",       # MQTT
        "nginx",           # Nginx
        "apache2", "httpd",  # Apache
        "postgresql", "postgres",  # PostgreSQL
        "mysql", "mariadb",  # MySQL/MariaDB
        "redis-server", "redis",  # Redis
        "pihole-FTL",      # Pi-hole
        "jellyfin",        # Jellyfin
        "plex",            # Plex
        "transmission-daemon",  # Transmission
        "cups",            # Printing
        "samba", "smbd",   # Samba
    ]
    
    # === SYSTEM Services (can restart, but be careful) ===
    system_services = [
        "ssh", "sshd",           # SSH
        "bluetooth",             # Bluetooth
        "NetworkManager",        # Network Manager
        "wpa_supplicant",        # WiFi
        "avahi-daemon",          # mDNS/Bonjour
        "cron", "cronie",        # Cron
        "rsyslog",               # Syslog
        "ntp", "systemd-timesyncd", "chrony",  # Time sync
        "udev", "systemd-udevd", # Device manager
        "dnsmasq",               # DNS
        "dhcpcd",                # DHCP
    ]
    
    # === CORE Services (read-only, never modify) ===
    core_services = [
        "systemd-journald",
        "systemd-logind",
        "dbus",
        "polkit",
        "systemd-resolved",
    ]
    
    try:
        # Get running services from HOST
        output = run_host_command_simple(
            "systemctl list-units --type=service --state=running --no-pager --plain",
            timeout=15
        )
        
        if not output:
            return []
        
        running_names = set()
        for line in output.strip().split("\n"):
            if not line.strip() or line.startswith("UNIT"):
                continue
            parts = line.split()
            if parts and parts[0].endswith(".service"):
                name = parts[0].replace(".service", "")
                running_names.add(name)
        
        # Get all important services status
        all_target_services = app_services + system_services + core_services
        
        for svc_name in all_target_services:
            # Check if service exists and get its status
            status_output = run_host_command_simple(
                f"systemctl is-active {svc_name}.service 2>/dev/null || echo inactive",
                timeout=5
            ).strip()
            
            # Filter: only show running services or explicitly listed important services
            if status_output == "inactive" and svc_name not in running_names:
                # Check if service even exists
                exists = run_host_command_simple(
                    f"systemctl cat {svc_name}.service >/dev/null 2>&1 && echo yes || echo no",
                    timeout=3
                ).strip()
                if exists != "yes":
                    continue
            
            # Map state
            if status_output == "active":
                state = "running"
            elif status_output == "inactive":
                state = "stopped"
            elif status_output == "failed":
                state = "failed"
            elif status_output == "activating":
                state = "restarting"
            else:
                state = "unknown"
            
            # Determine class
            if svc_name in core_services:
                resource_class = "CORE"
            elif svc_name in system_services:
                resource_class = "SYSTEM"
            else:
                resource_class = "APP"
            
            services.append(ResourceResponse(
                id=f"systemd-{svc_name}",
                name=svc_name,
                type="service",
                resource_class=resource_class,
                provider="systemd",
                state=state,
                health_score=100 if state == "running" else (50 if state == "stopped" else 0),
                managed=True,
                updated_at=datetime.utcnow().isoformat()
            ))
        
        # Also add any OTHER running services not in our lists (as APP)
        for svc_name in running_names:
            if svc_name not in all_target_services:
                # Skip internal systemd services
                if svc_name.startswith("systemd-") or svc_name.startswith("user@"):
                    continue
                if any(x in svc_name for x in ["getty", "init", "mount", "swap"]):
                    continue
                
                services.append(ResourceResponse(
                    id=f"systemd-{svc_name}",
                    name=svc_name,
                    type="service",
                    resource_class="APP",
                    provider="systemd",
                    state="running",
                    health_score=100,
                    managed=True,
                    updated_at=datetime.utcnow().isoformat()
                ))
        
    except Exception as e:
        print(f"Failed to get systemd services: {e}")
    
    # Sort by class then name
    class_order = {"APP": 0, "SYSTEM": 1, "CORE": 2}
    return sorted(services, key=lambda s: (class_order.get(s.resource_class, 3), s.name))


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
            ["sudo", "systemctl", action, f"{service_name}.service"],
            capture_output=True,
            text=True,
            timeout=30
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
