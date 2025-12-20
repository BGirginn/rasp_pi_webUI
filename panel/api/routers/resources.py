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
from services.host_exec import run_host_command_simple, run_host_command, is_running_in_docker
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

    # Get CPU core count for normalizing percentages
    cpu_cores = 1  # Default fallback
    try:
        cores_out = run_host_command_simple("nproc", timeout=2)
        if cores_out and cores_out.strip().isdigit():
            cpu_cores = int(cores_out.strip())
    except:
        cpu_cores = 1
    
    # Get Usage Data using systemd-cgtop for REAL-TIME metrics
    # Use 3 iterations to get accurate CPU measurements
    usage_map = {}
    try:
        # systemd-cgtop with 3 iterations gives accurate real-time CPU
        # -b: batch mode
        # -n 3: three iterations (needed for CPU calculation)
        # --delay=0.3: 300ms between iterations
        cgtop_out = run_host_command_simple(
            "systemd-cgtop -b -n 3 --delay=0.3 2>/dev/null | grep '\\.service' | tail -20 || echo ''", 
            timeout=2
        )
        
        if cgtop_out and len(cgtop_out.strip()) > 10:
            # Parse systemd-cgtop output
            # Format: Control Group    Tasks   %CPU   Memory  Input/s Output/s
            lines = cgtop_out.strip().splitlines()
            for line in lines:
                parts = line.split()
                if len(parts) >= 4 and '.service' in line:
                    # Extract service name from control group path
                    # Format: system.slice/servicename.service
                    cgroup = parts[0]
                    service_name = cgroup.split('/')[-1]  # Get last part (servicename.service)
                    
                    try:
                        cpu_str = parts[2] if len(parts) > 2 else '-'
                        mem_str = parts[3] if len(parts) > 3 else '-'
                        
                        # Parse CPU (real-time percentage)
                        cpu_val = 0.0
                        if cpu_str != '-' and cpu_str and cpu_str != '':
                            cpu_val = float(cpu_str.replace('%', ''))
                            # systemd-cgtop shows per-core percentage, normalize to 0-100%
                            # On 4-core system, service using all cores shows ~400%
                            if cpu_val > 100:
                                cpu_val = cpu_val / cpu_cores
                        
                        # Parse Memory
                        mem_pct = 0.0
                        if mem_str != '-' and mem_str and mem_str != '':
                            mem_val_str = mem_str.replace('%', '')
                            
                            if 'G' in mem_val_str:
                                mem_gb = float(mem_val_str.replace('G', ''))
                                mem_pct = (mem_gb / 8.0) * 100
                            elif 'M' in mem_val_str:
                                mem_mb = float(mem_val_str.replace('M', ''))
                                mem_pct = (mem_mb / 8000.0) * 100
                            elif 'K' in mem_val_str:
                                mem_kb = float(mem_val_str.replace('K', ''))
                                mem_pct = (mem_kb / 8000000.0) * 100
                            else:
                                mem_pct = float(mem_val_str)
                        
                        if service_name:
                            usage_map[service_name] = {
                                "cpu": round(cpu_val, 1),
                                "mem": round(mem_pct, 1)
                            }
                    except Exception as parse_err:
                        pass  # Skip malformed lines
                        
    except Exception as e:
        print(f"Discovery usage map error: {e}")




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
             
             # Get state information
             active_state = parts[2] if len(parts) > 2 else "unknown"
             sub_state = parts[3] if len(parts) > 3 else "unknown"
             
             # Determine if service is running
             is_running = active_state == "active"
             is_important = name in app_services or name in system_services or name in core_services
             
             # Filter logic:
             # - Always show important services (app/system/core lists) regardless of state
             # - For other services, only show if running (to avoid clutter)
             if not is_important and not is_running:
                 continue

             use_data = usage_map.get(unit_name, {"cpu": 0.0, "mem": 0.0})
             
             # Determine state string for display
             if active_state == "active":
                 state = "running"
             elif active_state == "failed":
                 state = "failed"
             elif active_state == "inactive" or active_state == "deactivating":
                 state = "stopped"
             else:
                 state = "unknown"
             
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
        
        # Try agent RPC first (Preferred: Agent runs as root)
        try:
            # Agent expects ID like "service.service"
            agent_resource_id = f"{service_name}.service"
            print(f"Attempting agent action on {agent_resource_id}")
            action_result = await agent_client.resource_action(agent_resource_id, request.action, request.params)
            
            # If agent returns explicit failure (but communication worked), respect it?
            # Or fall back if it says "Resource not found"?
            # For now, if communication works, we trust the result.
            if action_result and action_result.get("success"):
                pass  # Success!
            elif action_result and action_result.get("error") == "NOT_FOUND":
                # Agent doesn't know about it (maybe just created?), try local fallback
                print("Agent resource not found, falling back to local action")
                raise Exception("Agent resource not found")
                
        except Exception as e:
            print(f"Agent action failed ({e}), falling back to local execution")
            action_result = await _execute_systemd_action(service_name, request.action)
    else:
        # Try agent RPC for other providers
        try:
            action_result = await agent_client.resource_action(resource_id, request.action, request.params)
        except Exception:
            action_result = {"success": False, "message": "Agent unavailable", "error_type": "SYSTEM_ERROR"}
    
    # Audit log - record attempt regardless of success
    await db.execute(
        """INSERT INTO audit_log (user_id, action, resource_id, details)
           VALUES (?, ?, ?, ?)""",
        (user["id"], f"resource.{request.action}", resource_id, str(request.params))
    )
    await db.commit()
    
    # Handle action result and map to appropriate HTTP status codes
    if action_result and not action_result.get("success", True):
        error_type = action_result.get("error_type", "SYSTEM_ERROR")
        error_message = action_result.get("message", "Action failed")
        
        # Map error types to HTTP status codes
        if error_type == "NOT_FOUND":
            raise HTTPException(
                status_code=404,
                detail={
                    "message": error_message,
                    "error_code": error_type,
                    "service": resource_name,
                    "action": request.action
                }
            )
        elif error_type == "PERMISSION_DENIED":
            raise HTTPException(
                status_code=403,
                detail={
                    "message": error_message,
                    "error_code": error_type,
                    "service": resource_name,
                    "action": request.action
                }
            )
        elif error_type in ["INVALID_ACTION", "PROTECTED"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": error_message,
                    "error_code": error_type,
                    "service": resource_name,
                    "action": request.action
                }
            )
        else:
            # SYSTEM_ERROR or unknown errors
            raise HTTPException(
                status_code=500,
                detail={
                    "message": error_message,
                    "error_code": error_type,
                    "service": resource_name,
                    "action": request.action,
                    "error_details": action_result.get("error", "Unknown error")
                }
            )
    
    return ActionResponse(
        success=True,
        message=f"Action '{request.action}' executed on {resource_name}",
        data={"resource_id": resource_id, "action": request.action, "result": action_result}
    )


async def _check_service_exists(service_name: str) -> dict:
    """Check if a systemd service exists on the host.
    
    Returns:
        dict with 'exists' (bool), 'state' (str), and 'error' (str) if any
    """
    service_unit = f"{service_name}.service"
    
    try:
        # Use systemctl list-unit-files to check existence
        stdout, stderr, returncode = run_host_command(
            f"systemctl list-unit-files {service_unit} --no-legend",
            timeout=10
        )
        
        if returncode == 0 and stdout.strip():
            # Service file exists, now check its status
            status_out, _, status_code = run_host_command(
                f"systemctl is-active {service_unit}",
                timeout=10
            )
            state = status_out.strip() if status_code == 0 else "unknown"
            return {"exists": True, "state": state, "error": None}
        else:
            return {"exists": False, "state": None, "error": "Service not found"}
    except Exception as e:
        return {"exists": False, "state": None, "error": str(e)}


async def _execute_systemd_action(service_name: str, action: str) -> dict:
    """Execute a systemctl action on a service via host_exec.
    
    Tries multiple approaches in order:
    1. Direct systemctl (works if user has polkit permissions)
    2. sudo systemctl (passwordless sudo)
    3. sudo -S with password from environment
    
    Returns:
        dict with 'success', 'message', 'error_type', and optional 'output'
        error_type can be: 'NOT_FOUND', 'PERMISSION_DENIED', 'PROTECTED', 'INVALID_ACTION', 'SYSTEM_ERROR'
    """
    import os

    # Allowed actions
    allowed = ["start", "stop", "restart", "status"]
    if action not in allowed:
        return {
            "success": False,
            "message": f"Action '{action}' not allowed. Use: {allowed}",
            "error_type": "INVALID_ACTION"
        }
    
    # Protected services that cannot be stopped
    protected = ["sshd", "ssh", "pi-control", "systemd-journald", "dbus", "NetworkManager"]
    if action in ["stop"] and service_name in protected:
        return {
            "success": False,
            "message": f"Cannot stop protected service: {service_name}",
            "error_type": "PROTECTED"
        }
    
    # Check if service exists before attempting action
    service_check = await _check_service_exists(service_name)
    if not service_check["exists"]:
        print(f"Service {service_name} does not exist")
        return {
            "success": False,
            "message": f"Service '{service_name}' not found on the system",
            "error_type": "NOT_FOUND"
        }
    
    service_unit = f"{service_name}.service"
    
    # List of commands to try in order
    commands_to_try = []
    
    if is_running_in_docker():
        # Docker mode: use SSH to host
        password = os.environ.get("SUDO_PASSWORD") or os.environ.get("SSH_HOST_PASSWORD")
        if password:
            commands_to_try.append(f"echo '{password}' | sudo -S systemctl {action} {service_unit}")
        commands_to_try.append(f"sudo systemctl {action} {service_unit}")
    else:
        # Native mode: try multiple approaches
        # 1. Direct systemctl (works with polkit rules)
        commands_to_try.append(f"systemctl {action} {service_unit}")
        
        # 2. Passwordless sudo
        commands_to_try.append(f"sudo -n systemctl {action} {service_unit}")
        
        # 3. sudo with password from environment
        password = os.environ.get("SUDO_PASSWORD") or os.environ.get("SSH_HOST_PASSWORD")
        if password:
            commands_to_try.append(f"echo '{password}' | sudo -S systemctl {action} {service_unit}")
    
    last_error = ""
    last_error_type = "SYSTEM_ERROR"
    
    for command in commands_to_try:
        try:
            # Mask password in logs
            log_cmd = command
            for env_var in ["SUDO_PASSWORD", "SSH_HOST_PASSWORD"]:
                pwd = os.environ.get(env_var, "")
                if pwd and pwd in log_cmd:
                    log_cmd = log_cmd.replace(pwd, "***")
            
            print(f"Trying systemd command: {log_cmd}")
            
            stdout, stderr, returncode = run_host_command(command, timeout=30)
            
            if returncode == 0:
                print(f"Command succeeded: {log_cmd}")
                return {
                    "success": True,
                    "message": f"Service {service_name} {action} successful",
                    "output": stdout,
                    "error_type": None
                }
            else:
                last_error = stderr.strip() or f"Exit code {returncode}"
                
                # Classify error type based on stderr content
                if "permission denied" in last_error.lower() or "access denied" in last_error.lower():
                    last_error_type = "PERMISSION_DENIED"
                elif "not found" in last_error.lower() or "could not be found" in last_error.lower():
                    last_error_type = "NOT_FOUND"
                elif returncode == 5:  # systemctl returns 5 for unit not loaded
                    last_error_type = "NOT_FOUND"
                
                print(f"Command failed ({returncode}): {last_error}")
                # Continue to next command
                
        except Exception as e:
            last_error = str(e)
            last_error_type = "SYSTEM_ERROR"
            print(f"Command exception: {e}")
            # Continue to next command
    
    # All commands failed
    print(f"All systemd commands failed for {service_name} {action}. Error type: {last_error_type}")
    return {
        "success": False,
        "message": f"Failed to {action} {service_name}. Error: {last_error}",
        "error": last_error,
        "error_type": last_error_type
    }


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
