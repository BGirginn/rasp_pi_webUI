"""
Rollback Job Manager
Creates and manages rollback jobs for network actions per A4.2.
"""

import json
import time
import uuid
from typing import Optional


async def create_rollback_job(
    db,
    action_id: str,
    rollback_action_id: str,
    payload: dict,
    user_id: int,
    timeout_seconds: int
) -> str:
    """
    Create a rollback job for a network action.
    
    Args:
        db: Database connection
        action_id: Original action that was executed
        rollback_action_id: Action to execute for rollback
        payload: Parameters for rollback action
        user_id: User who executed original action
        timeout_seconds: Seconds until auto-rollback
        
    Returns:
        Rollback job ID
        
    Per A4.2: Called after network action succeeds
    """
    job_id = str(uuid.uuid4())
    now = int(time.time())
    due_at = now + timeout_seconds
    
    payload_json = json.dumps(payload)
    
    await db.execute(
        """INSERT INTO rollback_jobs 
           (id, action_id, rollback_action_id, payload_json, 
            created_by_user_id, due_at, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            job_id,
            action_id,
            rollback_action_id,
            payload_json,
            user_id,
            due_at,
            'pending',
            now
        )
    )
    await db.commit()
    
    return job_id


async def get_current_wifi_state() -> bool:
    """
    Get current WiFi state from agent.
    
    Returns:
        True if WiFi enabled, False if disabled
        
    Per A4.2.2: Real state must come from agent
    """
    # TODO: Get from agent_rpc
    # For now, assume we can infer from action params
    # This will be improved when agent provides state query
    return True  # Placeholder


def determine_rollback_payload(action_id: str, original_params: dict) -> Optional[dict]:
    """
    Determine rollback payload for network actions.
    
    Args:
        action_id: Action that was executed
        original_params: Original action parameters
        
    Returns:
        Rollback payload dict, or None if no rollback needed
        
    Per A4.2.2: Rollback = opposite of what was done
    """
    if action_id == "net.toggle_wifi":
        # If enabled=true was sent, rollback=false (and vice versa)
        original_enabled = original_params.get("enabled")
        if original_enabled is not None:
            return {"enabled": not original_enabled}
    
    elif action_id == "net.reset_safe":
        # Reset always rolls back to "primary" profile
        # (Rollback of reset = another reset to primary)
        return {"profile": "primary"}
    
    return None
