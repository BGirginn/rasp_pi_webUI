"""
Network Adapter
Network operations via agent RPC.
"""

from adapters.agent_rpc import agent_rpc


async def toggle_wifi(enabled: bool) -> dict:
    """Toggle WiFi on/off."""
    result = await agent_rpc.toggle_wifi(enabled)
    return result


async def reset_network_safe(profile: str = "primary") -> dict:
    """
    Reset network to safe configuration.
    
    Args:
        profile: Network profile name (must be in allowlist)
        
    Returns:
        Result dict
    """
    # TODO: TASK 16 - Implement with rollback support
    return {"success": False, "message": "TODO: not implemented yet"}


async def enable_tailscale() -> dict:
    """Enable Tailscale VPN."""
    # Use systemd adapter for tailscaled service
    from adapters.systemd import start_service, enable_service
    
    # Start and enable tailscaled
    start_result = await start_service("tailscaled")
    if not start_result.get("success"):
        return start_result
    
    enable_result = await enable_service("tailscaled")
    return enable_result


async def disable_tailscale() -> dict:
    """Disable Tailscale VPN."""
    from adapters.systemd import stop_service, disable_service
    
    # Stop and disable tailscaled
    stop_result = await stop_service("tailscaled")
    if not stop_result.get("success"):
        return stop_result
    
    disable_result = await disable_service("tailscaled")
    return disable_result
