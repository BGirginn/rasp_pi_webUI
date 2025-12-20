"""
Power Adapter
System power operations via agent RPC.
"""

from adapters.agent_rpc import agent_rpc


async def reboot_safe() -> dict:
    """
    Reboot the system safely.
    
    Returns:
        Result dict
    """
    # Use agent RPC to execute reboot
    result = await agent_rpc.resource_action("system", "reboot", {})
    return result


async def shutdown_safe() -> dict:
    """
    Shutdown the system safely.
    
    Returns:
        Result dict
    """
    # Use agent RPC to execute shutdown
    result = await agent_rpc.resource_action("system", "shutdown", {})
    return result
