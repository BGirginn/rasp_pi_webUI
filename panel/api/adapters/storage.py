"""
Storage Adapter
Storage mount/unmount operations via agent RPC.
"""

from adapters.agent_rpc import agent_rpc


async def mount_external(mount_point: str, device_hint: str) -> dict:
    """
    Mount external storage.
    
    Args:
        mount_point: Mount point path (must be in allowlist)
        device_hint: Device identifier hint
        
    Returns:
        Result dict
    """
    # TODO: TASK 09 - Implement when agent supports storage operations
    return {"success": False, "message": "TODO: not implemented yet"}


async def unmount_external(mount_point: str) -> dict:
    """
    Unmount external storage.
    
    Args:
        mount_point: Mount point path (must be in allowlist)
        
    Returns:
        Result dict
    """
    # TODO: TASK 09 - Implement when agent supports storage operations
    return {"success": False, "message": "TODO: not implemented yet"}
