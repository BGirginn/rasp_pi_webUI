"""
Docker Adapter
Docker container operations via agent RPC.
"""

from adapters.agent_rpc import agent_rpc


async def list_containers() -> dict:
    """
    List all Docker containers.
    
    Returns:
        Result dict with container list
    """
    result = await agent_rpc.resource_action("docker", "list", {})
    return result


async def restart_container(container_id: str) -> dict:
    """
    Restart a Docker container.
    
    Args:
        container_id: Container ID or name
        
    Returns:
        Result dict
    """
    result = await agent_rpc.resource_action(container_id, "restart", {})
    return result


async def stop_container(container_id: str) -> dict:
    """
    Stop a Docker container.
    
    Args:
        container_id: Container ID or name
        
    Returns:
        Result dict
    """
    result = await agent_rpc.resource_action(container_id, "stop", {})
    return result
