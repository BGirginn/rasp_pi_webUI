"""
Updates Adapter
Phase-1 placeholder for update checks and apply.
"""


async def check_updates() -> dict:
    """Return current version and update availability (Phase-1 disabled)."""
    return {
        "success": True,
        "data": {
            "current_version": "1.0.0",
            "available": False
        }
    }


async def apply_update(channel: str, backup_before: bool) -> dict:
    """Apply updates (disabled in Phase-1)."""
    return {"success": False, "message": "Disabled in Phase-1"}
