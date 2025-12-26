"""
Action Handlers
Maps registry handler strings to adapter function calls.
Contains all 25 handler functions referenced in registry.yaml.
"""

import bcrypt

from adapters import systemd, network, power, logs, docker, storage
from adapters.agent_rpc import agent_rpc
from core.auth.jwt import rotate_jwt_secret
from db import get_control_db


# -------------------------
# OBSERVABILITY HANDLERS
# -------------------------

async def handler_obs_get_system_status() -> dict:
    """Get overall system status."""
    result = await agent_rpc.get_system_info()
    if result.get("success") is False:
        return result
    return {"success": True, "data": result}


async def handler_obs_get_metrics_snapshot(include: list) -> dict:
    """Get metrics snapshot for specified categories."""
    result = await agent_rpc.get_snapshot()
    if result.get("success") is False:
        return result
    
    # Filter snapshot by included categories
    filtered = {}
    snapshot_data = result.get("data", {})
    for category in include:
        if category in snapshot_data:
            filtered[category] = snapshot_data[category]
    
    return {"success": True, "data": filtered}


async def handler_obs_get_logs(source: str, service: str = None, limit: int = 400) -> dict:
    """View logs from specified source."""
    result = await logs.get_logs(source, service, limit)
    return result


# -------------------------
# POWER HANDLERS
# -------------------------

async def handler_power_reboot_safe() -> dict:
    """Reboot the system safely."""
    result = await power.reboot_safe()
    return result


async def handler_power_shutdown_safe() -> dict:
    """Shutdown the system safely."""
    result = await power.shutdown_safe()
    return result


# -------------------------
# SERVICE (SYSTEMD) HANDLERS
# -------------------------

async def handler_svc_restart(service: str) -> dict:
    """Restart a systemd service."""
    result = await systemd.restart_service(service)
    return result


async def handler_svc_start(service: str) -> dict:
    """Start a systemd service."""
    result = await systemd.start_service(service)
    return result


async def handler_svc_stop(service: str) -> dict:
    """Stop a systemd service."""
    result = await systemd.stop_service(service)
    return result


async def handler_svc_enable(service: str) -> dict:
    """Enable a systemd service."""
    result = await systemd.enable_service(service)
    return result


async def handler_svc_disable(service: str) -> dict:
    """Disable a systemd service."""
    result = await systemd.disable_service(service)
    return result


# -------------------------
# NETWORK HANDLERS
# -------------------------

async def handler_net_toggle_wifi(enabled: bool) -> dict:
    """Toggle WiFi on/off."""
    result = await network.toggle_wifi(enabled)
    return result


async def handler_net_reset_safe(profile: str) -> dict:
    """Safe network reset to specified profile."""
    result = await network.reset_network_safe(profile)
    return result


async def handler_net_tailscale_enable() -> dict:
    """Enable Tailscale VPN."""
    result = await network.enable_tailscale()
    return result


async def handler_net_tailscale_disable() -> dict:
    """Disable Tailscale VPN."""
    result = await network.disable_tailscale()
    return result


# -------------------------
# DOCKER HANDLERS
# -------------------------

async def handler_docker_list() -> dict:
    """List all Docker containers."""
    result = await docker.list_containers()
    return result


async def handler_docker_restart_container(container_id: str) -> dict:
    """Restart a Docker container."""
    result = await docker.restart_container(container_id)
    return result


async def handler_docker_stop_container(container_id: str) -> dict:
    """Stop a Docker container."""
    result = await docker.stop_container(container_id)
    return result


# -------------------------
# STORAGE HANDLERS
# -------------------------

async def handler_storage_mount_external(mount_point: str, device_hint: str) -> dict:
    """Mount external storage."""
    result = await storage.mount_external(mount_point, device_hint)
    return result


async def handler_storage_unmount_external(mount_point: str) -> dict:
    """Unmount external storage."""
    result = await storage.unmount_external(mount_point)
    return result


# -------------------------
# AUTH HANDLERS
# -------------------------

async def handler_auth_create_user(username: str, role: str, temporary_password: str) -> dict:
    """Create a new user account."""
    if role not in ("viewer", "operator", "admin"):
        return {"success": False, "message": "Invalid role"}

    db = await get_control_db()
    cursor = await db.execute("SELECT id FROM users WHERE username = ?", (username,))
    if await cursor.fetchone():
        return {"success": False, "message": "Username already exists"}

    password_hash = bcrypt.hashpw(temporary_password.encode(), bcrypt.gensalt()).decode()
    await db.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, password_hash, role)
    )
    await db.commit()

    return {
        "success": True,
        "data": {"username": username, "role": role}
    }


async def handler_auth_rotate_jwt_secret() -> dict:
    """Rotate JWT secret for enhanced security."""
    db = await get_control_db()
    new_version = await rotate_jwt_secret(db)
    return {"success": True, "data": {"jwt_secret_version": new_version}}


# -------------------------
# UPDATE HANDLERS
# -------------------------

async def handler_update_check() -> dict:
    """Check for available updates."""
    return {
        "success": True,
        "data": {
            "current_version": "1.0.0",
            "available": False
        }
    }


async def handler_update_apply(channel: str, backup_before: bool) -> dict:
    """Apply available updates."""
    return {"success": False, "message": "Disabled in Phase-1"}


# -------------------------
# EMERGENCY HANDLERS
# -------------------------

async def handler_emergency_rollback_last_network_change() -> dict:
    """Rollback last network change (emergency use)."""
    return {"success": False, "message": "Disabled until snapshot support implemented"}


async def handler_emergency_safe_mode_enable() -> dict:
    """Enable safe mode (minimal services)."""
    return {"success": False, "message": "Disabled in Phase-1"}


# -------------------------
# HANDLER DISPATCH MAP
# -------------------------
# Maps registry handler strings to Python functions

HANDLERS = {
    # Observability
    "handler.obs.get_system_status": handler_obs_get_system_status,
    "handler.obs.get_metrics_snapshot": handler_obs_get_metrics_snapshot,
    "handler.obs.get_logs": handler_obs_get_logs,
    
    # Power
    "handler.power.reboot_safe": handler_power_reboot_safe,
    "handler.power.shutdown_safe": handler_power_shutdown_safe,
    
    # Services (systemd)
    "handler.svc.restart": handler_svc_restart,
    "handler.svc.start": handler_svc_start,
    "handler.svc.stop": handler_svc_stop,
    "handler.svc.enable": handler_svc_enable,
    "handler.svc.disable": handler_svc_disable,
    
    # Network
    "handler.net.toggle_wifi": handler_net_toggle_wifi,
    "handler.net.reset_safe": handler_net_reset_safe,
    "handler.net.tailscale_enable": handler_net_tailscale_enable,
    "handler.net.tailscale_disable": handler_net_tailscale_disable,
    
    # Docker
    "handler.docker.list": handler_docker_list,
    "handler.docker.restart_container": handler_docker_restart_container,
    "handler.docker.stop_container": handler_docker_stop_container,
    
    # Storage
    "handler.storage.mount_external": handler_storage_mount_external,
    "handler.storage.unmount_external": handler_storage_unmount_external,
    
    # Auth
    "handler.auth.create_user": handler_auth_create_user,
    "handler.auth.rotate_jwt_secret": handler_auth_rotate_jwt_secret,
    
    # Updates
    "handler.update.check": handler_update_check,
    "handler.update.apply": handler_update_apply,
    
    # Emergency
    "handler.emergency.rollback_last_network_change": handler_emergency_rollback_last_network_change,
    "handler.emergency.safe_mode_enable": handler_emergency_safe_mode_enable,
}
