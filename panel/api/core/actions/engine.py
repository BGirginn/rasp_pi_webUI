"""
Action Engine
Single mutation entrypoint enforcing all AR rules.
"""

import time
from datetime import datetime
from typing import Optional
from fastapi import HTTPException

from core.actions.loader import get_registry
from core.auth.rbac import assert_role_allowed
from core.actions.validate import validate_params
from core.actions.guards import check_confirmation, check_cooldown
from core.actions.handlers import HANDLERS
from core.auth.masking import mask_params
from core.audit.models import AuditEvent
from core.audit.writer import write_audit


async def execute_action(
    *,
    db,
    user: dict,
    action_id: str,
    params: Optional[dict] = None,
    confirm: bool = False
) -> dict:
    """
    Execute an action with full AR enforcement.
    
    This is the ONLY entry point for all mutations per AI_RULES.md R3.1.
    
    Args:
        db: Database connection
        user: User dict with id, username, role
        action_id: Action ID from registry (e.g. "svc.restart")
        params: Action parameters (will be validated)
        confirm: User confirmation flag (for actions requiring confirmation)
        
    Returns:
        Standardized result dict with success/error
        
    Execution order (strict):
        1. Load registry
        2. RBAC check (deny if not allowed)
        3. Validate params (deny if invalid)
        4. Guard checks (confirmation, cooldown)
        5. Dispatch handler
        6. Measure duration
        7. Write audit (always, success or fail)
        8. Return result
    """
    start_time = time.time()
    audit_status = "fail"
    audit_error = None
    result = None
    
    try:
        # 1. Load registry
        registry = get_registry()
        
        # 2. RBAC check - raises 403 if not allowed
        assert_role_allowed(registry, user["role"], action_id)
        
        # 3. Validate params - raises 400 if invalid
        validated_params = validate_params(registry, action_id, params)
        
        # 4. Guard checks
        # 4a. Confirmation check
        check_confirmation(registry, action_id, confirm)
        
        # 4b. Cooldown check - raises 429 if within cooldown
        # Find action's cooldown setting
        action_def = None
        for action in registry.get("actions", []):
            if action.get("id") == action_id:
                action_def = action
                break
        
        if action_def:
            cooldown_seconds = action_def.get("cooldown_seconds")
            if cooldown_seconds is None:
                # Use default
                defaults = registry.get("defaults", {})
                cooldown_seconds = defaults.get("cooldown_seconds", 0)
            
            if cooldown_seconds > 0:
                await check_cooldown(db, user["id"], action_id, cooldown_seconds)
        
        # 5. Dispatch handler
        handler_name = action_def.get("handler") if action_def else None
        
        if not handler_name or handler_name not in HANDLERS:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "HANDLER_NOT_FOUND",
                    "message": f"Handler for action '{action_id}' not found"
                }
            )
        
        handler_func = HANDLERS[handler_name]
        
        # Call handler with validated params
        # Handlers are async and accept params as kwargs
        if validated_params:
            result = await handler_func(**validated_params)
        else:
            result = await handler_func()
        
        # Handler should return dict with success field
        if isinstance(result, dict) and result.get("success") is not False:
            audit_status = "success"
            
            # A4.2: Create rollback job if action supports it
            rollback_config = action_def.get("rollback") if action_def else None
            if (
                rollback_config
                and rollback_config.get("supported")
                and rollback_config.get("auto")
                and user.get("username") != "__rollback_worker__"
            ):
                from core.rollback.jobs import create_rollback_job
                from core.rollback.network import determine_rollback_plan

                timeout_seconds = rollback_config.get("timeout_seconds")
                if timeout_seconds:
                    rollback_plan = await determine_rollback_plan(action_id, validated_params)
                    if rollback_plan:
                        rollback_action_id, rollback_payload = rollback_plan
                        rollback_job_id = await create_rollback_job(
                            db=db,
                            action_id=action_id,
                            rollback_action_id=rollback_action_id,
                            payload=rollback_payload,
                            user_id=user["id"],
                            timeout_seconds=timeout_seconds
                        )

                        if isinstance(result, dict):
                            result["rollback"] = {
                                "job_id": rollback_job_id,
                                "due_in_seconds": timeout_seconds
                            }
        else:
            audit_status = "fail"
            audit_error = result.get("message") or result.get("error") or "Handler returned failure"
        
    except HTTPException as e:
        # Known HTTP errors (RBAC, validation, guards, etc.)
        audit_status = "fail"
        audit_error = str(e.detail)
        raise  # Re-raise to return proper HTTP response
    
    except Exception as e:
        # Unexpected errors
        audit_status = "fail"
        audit_error = str(e)
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNAL_ERROR",
                "message": f"Action execution failed: {str(e)}"
            }
        )
    
    finally:
        # 7. Write audit (ALWAYS, even on failure)
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Mask sensitive params
        params_masked = mask_params(action_id, params or {})
        
        audit_event = AuditEvent(
            user_id=user["id"],
            username=user["username"],
            role=user["role"],
            action_id=action_id,
            params_masked=params_masked,
            status=audit_status,
            error=audit_error,
            duration_ms=duration_ms,
            created_at=datetime.utcnow()
        )
        
        try:
            await write_audit(db, audit_event)
        except Exception as audit_err:
            # Log audit failure but don't fail the entire request
            # (In production, this should be logged to monitoring)
            print(f"WARNING: Audit write failed: {audit_err}")
    
    # 8. Return result
    return result


def standardize_error(error_code: str, message: str) -> dict:
    """
    Create standardized error response.
    
    Args:
        error_code: Error code (UPPERCASE_WITH_UNDERSCORES)
        message: Human-readable error message
        
    Returns:
        Standardized error dict
    """
    return {
        "success": False,
        "error": error_code,
        "message": message
    }
