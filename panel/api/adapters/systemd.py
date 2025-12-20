"""
Systemd Service Adapter
Manages systemd services via agent RPC (no direct subprocess calls).
"""

from adapters.agent_rpc import agent_rpc


async def restart_service(service_name: str) -> dict:
    """
    Restart a systemd service.
    
    Args:
        service_name: Service name (without .service suffix)
        
    Returns:
        Result dict with success/error
    """
    resource_id = f"{service_name}.service"
    return await agent_rpc.resource_action(resource_id, "restart", {})


async def start_service(service_name: str) -> dict:
    """Start a systemd service."""
    resource_id = f"{service_name}.service"
    return await agent_rpc.resource_action(resource_id, "start", {})


async def stop_service(service_name: str) -> dict:
    """Stop a systemd service."""
    resource_id = f"{service_name}.service"
    return await agent_rpc.resource_action(resource_id, "stop", {})


async def enable_service(service_name: str) -> dict:
    """Enable a systemd service."""
    resource_id = f"{service_name}.service"
    return await agent_rpc.resource_action(resource_id, "enable", {})


async def disable_service(service_name: str) -> dict:
    """Disable a systemd service."""
    resource_id = f"{service_name}.service"
    return await agent_rpc.resource_action(resource_id, "disable", {})
