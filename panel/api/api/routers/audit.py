"""
Audit API Router
Read-only endpoints for viewing audit logs.
"""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from api.deps import current_user
from db import get_control_db


router = APIRouter()


# -------------------------
# Response Models
# -------------------------

class AuditEntry(BaseModel):
    """Single audit log entry."""
    id: int
    created_at: str
    user_id: str
    username: str
    role: str
    action_id: str
    action_title: str  # Resolved from action_id
    params_masked: dict
    status: str  # "success" or "fail"
    error: Optional[str] = None
    duration_ms: int


class AuditListResponse(BaseModel):
    """Paginated audit log response."""
    total: int
    skip: int
    limit: int
    entries: list[AuditEntry]


# -------------------------
# Endpoints
# -------------------------

@router.get("", response_model=AuditListResponse)
async def list_audits(
    skip: int = Query(0, ge=0, description="Number of entries to skip"),
    limit: int = Query(50, ge=1, le=200, description="Number of entries to return"),
    action_id: Optional[str] = Query(None, description="Filter by action ID"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    username: Optional[str] = Query(None, description="Filter by username"),
    status: Optional[str] = Query(None, description="Filter by status (success/fail)"),
    user: dict = Depends(current_user)
):
    """
    List audit log entries with pagination and filtering.
    
    Requires: viewer role or higher
    Returns: Paginated list of audit entries with masked params
    """
    db = await get_control_db()
    
    # Build query
    query = "SELECT * FROM audit_log WHERE 1=1"
    params = []
    
    if action_id:
        query += " AND action LIKE ?"
        params.append(f"%{action_id}%")
    
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)
    
    if username:
        query += " AND details LIKE ?"
        params.append(f'%"username":"{username}"%')
    
    if status:
        query += " AND details LIKE ?"
        params.append(f'%"status":"{status}"%')
    
    # Get total count
    count_query = f"SELECT COUNT(*) as count FROM ({query})"
    cursor = await db.execute(count_query, params)
    total = (await cursor.fetchone())["count"]
    
    # Get paginated results
    query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, skip])
    
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    
    # Parse and format entries
    entries = []
    for row in rows:
        import json
        details = json.loads(row["details"]) if row["details"] else {}
        
        # Resolve action title from action_id
        action_title = row["action"].split(".")[-1].replace("_", " ").title() if row["action"] else "Unknown"
        
        entry = AuditEntry(
            id=row["id"],
            created_at=row["timestamp"],
            user_id=details.get("user_id", "unknown"),
            username=details.get("username", "unknown"),
            role=details.get("role", "unknown"),
            action_id=row["action"] or "unknown",
            action_title=action_title,
            params_masked=details.get("params_masked", {}),
            status=details.get("status", "unknown"),
            error=details.get("error"),
            duration_ms=details.get("duration_ms", 0)
        )
        entries.append(entry)
    
    return AuditListResponse(
        total=total,
        skip=skip,
        limit=limit,
        entries=entries
    )


@router.get("/{audit_id}")
async def get_audit_detail(
    audit_id: int,
    user: dict = Depends(current_user)
):
    """
    Get detailed information for a single audit entry.
    
    Requires: viewer role or higher
    """
    db = await get_control_db()
    
    cursor = await db.execute(
        "SELECT * FROM audit_log WHERE id = ?",
        (audit_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Audit entry not found")
    
    import json
    details = json.loads(row["details"]) if row["details"] else {}
    
    action_title = row["action"].split(".")[-1].replace("_", " ").title() if row["action"] else "Unknown"
    
    return AuditEntry(
        id=row["id"],
        created_at=row["timestamp"],
        user_id=details.get("user_id", "unknown"),
        username=details.get("username", "unknown"),
        role=details.get("role", "unknown"),
        action_id=row["action"] or "unknown",
        action_title=action_title,
        params_masked=details.get("params_masked", {}),
        status=details.get("status", "unknown"),
        error=details.get("error"),
        duration_ms=details.get("duration_ms", 0)
    )
