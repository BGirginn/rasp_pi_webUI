"""
Logs Adapter
Log viewing operations.
"""

from adapters.agent_rpc import agent_rpc


async def get_logs(source: str, service: str = None, limit: int = 400) -> dict:
    """
    Get logs from specified source.
    
    Args:
        source: Log source ("system", "service", "panel", "agent")
        service: Service name (required if source="service")
        limit: Maximum number of log lines
        
    Returns:
        Result dict with logs
    """
    if source == "service" and not service:
        return {"success": False, "message": "Service name required for service logs"}
    
    # Map to agent RPC call or existing log fetching logic
    if source == "service":
        # Get service logs via journalctl through agent
        result = await agent_rpc.resource_action(f"{service}.service", "logs", {"limit": limit})
        return result
    elif source == "system":
        # Get system logs
        result = await agent_rpc.resource_action("system", "logs", {"limit": limit})
        return result
    elif source == "panel":
        # TODO: Read panel API logs from local file
        return {"success": False, "message": "TODO: panel logs not implemented yet"}
    elif source == "agent":
        # TODO: Read agent logs via RPC
        return {"success": False, "message": "TODO: agent logs not implemented yet"}
    else:
        return {"success": False, "message": f"Unknown log source: {source}"}
