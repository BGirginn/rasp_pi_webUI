"""
Actions API Router
New AR-driven API endpoints for action execution.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import current_user
from db import get_control_db
from core.actions.loader import get_registry
from core.auth.rbac import is_role_allowed
from core.actions.engine import execute_action


router = APIRouter()


# -------------------------
# Request/Response Models
# -------------------------

class ActionInfo(BaseModel):
    """Action information for UI display."""
    id: str
    title: str
    category: str
    risk: str
    requires_confirmation: bool
    cooldown_seconds: int
    params_schema: dict


class ExecuteActionRequest(BaseModel):
    """Request to execute an action."""
    action_id: str
    params: Optional[dict] = None
    confirm: bool = False


class ExecuteActionResponse(BaseModel):
    """Response from action execution."""
    success: bool
    message: Optional[str] = None
    data: Optional[dict] = None
    error: Optional[str] = None
    rollback: Optional[dict] = None


class ConfirmRollbackRequest(BaseModel):
    """Request to confirm (cancel) a rollback job."""
    rollback_job_id: str


# -------------------------
# Endpoints
# -------------------------

@router.get("", response_model=List[ActionInfo])
async def list_actions(user: dict = Depends(current_user)):
    """
    List all actions the current user is allowed to execute.
    
    Filters actions based on user's role per RBAC rules.
    """
    registry = get_registry()
    actions = registry.get("actions", [])
    defaults = registry.get("defaults", {})
    
    allowed_actions = []
    
    for action in actions:
        action_id = action.get("id")
        
        # Check if user's role is allowed
        if not is_role_allowed(registry, user["role"], action_id):
            continue
        
        # Build ActionInfo
        info = ActionInfo(
            id=action_id,
            title=action.get("title", action_id),
            category=action.get("category", "unknown"),
            risk=action.get("risk", "unknown"),
            requires_confirmation=action.get("requires_confirmation", defaults.get("requires_confirmation", False)),
            cooldown_seconds=action.get("cooldown_seconds", defaults.get("cooldown_seconds", 0)),
            params_schema=action.get("params_schema", {})
        )
        
        allowed_actions.append(info)
    
    return allowed_actions


@router.post("/execute", response_model=ExecuteActionResponse)
async def execute_action_endpoint(
    request: ExecuteActionRequest,
    user: dict = Depends(current_user)
):
    """
    Execute an action.
    
    This is the ONLY mutation endpoint in the product per AI_RULES.md R3.1.
    """
    db = await get_control_db()
    
    try:
        result = await execute_action(
            db=db,
            user=user,
            action_id=request.action_id,
            params=request.params,
            confirm=request.confirm
        )
        
        # Standardize response
        if isinstance(result, dict):
            return ExecuteActionResponse(
                success=result.get("success", True),
                message=result.get("message"),
                data=result.get("data"),
                error=result.get("error"),
                rollback=result.get("rollback")
            )
        else:
            # Handler returned non-dict (shouldn't happen)
            return ExecuteActionResponse(
                success=True,
                data={"raw_result": result}
            )
    
    except HTTPException:
        # Re-raise HTTP exceptions (they have proper status codes)
        raise
    
    except Exception as e:
        # Unexpected errors
        raise HTTPException(
            status_code=500,
            detail={
                "error": "EXECUTION_FAILED",
                "message": str(e)
            }
        )


@router.post("/confirm")
async def confirm_rollback(
    request: ConfirmRollbackRequest,
    user: dict = Depends(current_user)
):
    """Confirm a rollback job to prevent auto-rollback."""
    from core.audit.models import AuditEvent
    from core.audit.writer import write_audit
    from core.rollback.jobs import get_job, mark_job_confirmed
    from datetime import datetime
    import time

    db = await get_control_db()
    job = await get_job(db, request.rollback_job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Rollback job not found")

    if job["status"] != "pending":
        raise HTTPException(status_code=409, detail="Rollback job not pending")

    now_ts = int(time.time())
    await mark_job_confirmed(db, request.rollback_job_id, now_ts)

    audit_event = AuditEvent(
        user_id=user["id"],
        username=user["username"],
        role=user["role"],
        action_id="rollback.confirm",
        params_masked={"rollback_job_id": request.rollback_job_id},
        status="success",
        error=None,
        duration_ms=0,
        created_at=datetime.utcnow()
    )
    await write_audit(db, audit_event)

    return {"success": True, "rollback_job_id": request.rollback_job_id}
