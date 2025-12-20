"""
Action Guards
Implements confirmation and cooldown checks before action execution.
"""

from datetime import datetime, timedelta
from fastapi import HTTPException


def requires_confirmation(registry: dict, action_id: str) -> bool:
    """
    Check if an action requires user confirmation.
    
    Args:
        registry: The Action Registry dict
        action_id: Action ID to check
        
    Returns:
        True if action requires confirmation, False otherwise
    """
    # Find action in registry
    actions = registry.get('actions', [])
    for action in actions:
        if action.get('id') == action_id:
            # Check action-level requires_confirmation first
            if 'requires_confirmation' in action:
                return action['requires_confirmation']
            
            # Otherwise use default
            defaults = registry.get('defaults', {})
            return defaults.get('requires_confirmation', False)
    
    # Unknown action - deny by returning True (safer)
    return True


async def check_cooldown(db, user_id: int, action_id: str, cooldown_seconds: int) -> None:
    """
    Check if action is within cooldown period based on recent audit log.
    Raises 429 if within cooldown.
    
    Args:
        db: Database connection
        user_id: User ID executing the action
        action_id: Action ID to check
        cooldown_seconds: Cooldown period in seconds
        
    Raises:
        HTTPException(429): If action was recently executed within cooldown period
    """
    if cooldown_seconds <= 0:
        return  # No cooldown
    
    # Calculate cooldown threshold time
    now = datetime.utcnow()
    threshold = now - timedelta(seconds=cooldown_seconds)
    
    # Query audit_log for most recent execution of this action by this user
    cursor = await db.execute(
        """SELECT created_at FROM audit_log
           WHERE user_id = ? AND action = ?
           ORDER BY created_at DESC
           LIMIT 1""",
        (user_id, action_id)
    )
    row = await cursor.fetchone()
    
    if row:
        # Parse created_at (stored as ISO string)
        last_execution_str = row[0]
        try:
            last_execution = datetime.fromisoformat(last_execution_str.replace('Z', '+00:00'))
        except:
            # Fallback for different datetime formats
            last_execution = datetime.strptime(last_execution_str, "%Y-%m-%d %H:%M:%S.%f")
        
        if last_execution > threshold:
            # Within cooldown period
            seconds_remaining = cooldown_seconds - (now - last_execution).total_seconds()
            
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "COOLDOWN_ACTIVE",
                    "message": f"Action '{action_id}' is on cooldown. Please wait {int(seconds_remaining)} seconds.",
                    "cooldown_seconds": cooldown_seconds,
                    "seconds_remaining": int(seconds_remaining)
                }
            )
