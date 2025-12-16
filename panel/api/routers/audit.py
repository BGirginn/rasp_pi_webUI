"""
Pi Control Panel - Audit Log Router

Audit log viewing and management.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from db import get_control_db
from .auth import get_current_user, require_role

router = APIRouter()


class AuditLogEntry(BaseModel):
    id: int
    user_id: Optional[int]
    username: Optional[str]
    action: str
    resource_id: Optional[str]
    resource_type: Optional[str]
    details: Optional[str]
    result: Optional[str]
    ip_address: Optional[str]
    created_at: str


class AuditLogResponse(BaseModel):
    entries: List[AuditLogEntry]
    total: int
    page: int
    page_size: int


@router.get("", response_model=AuditLogResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=200),
    action: Optional[str] = Query(None, description="Filter by action"),
    user_id: Optional[int] = Query(None, description="Filter by user"),
    resource_id: Optional[str] = Query(None, description="Filter by resource"),
    since: Optional[str] = Query(None, description="Filter since (ISO timestamp)"),
    until: Optional[str] = Query(None, description="Filter until (ISO timestamp)"),
    user: dict = Depends(require_role("admin"))
):
    """List audit log entries with pagination and filters."""
    db = await get_control_db()
    
    # Build query
    where_clauses = []
    params = []
    
    if action:
        where_clauses.append("a.action LIKE ?")
        params.append(f"%{action}%")
    
    if user_id:
        where_clauses.append("a.user_id = ?")
        params.append(user_id)
    
    if resource_id:
        where_clauses.append("a.resource_id = ?")
        params.append(resource_id)
    
    if since:
        where_clauses.append("a.created_at >= ?")
        params.append(since)
    
    if until:
        where_clauses.append("a.created_at <= ?")
        params.append(until)
    
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    # Count total
    cursor = await db.execute(
        f"SELECT COUNT(*) FROM audit_log a WHERE {where_sql}",
        params
    )
    total = (await cursor.fetchone())[0]
    
    # Get page
    offset = (page - 1) * page_size
    cursor = await db.execute(
        f"""SELECT a.id, a.user_id, u.username, a.action, a.resource_id, 
                   a.resource_type, a.details, a.result, a.ip_address, a.created_at
            FROM audit_log a
            LEFT JOIN users u ON a.user_id = u.id
            WHERE {where_sql}
            ORDER BY a.created_at DESC
            LIMIT ? OFFSET ?""",
        params + [page_size, offset]
    )
    rows = await cursor.fetchall()
    
    entries = [
        AuditLogEntry(
            id=row[0],
            user_id=row[1],
            username=row[2],
            action=row[3],
            resource_id=row[4],
            resource_type=row[5],
            details=row[6],
            result=row[7],
            ip_address=row[8],
            created_at=row[9]
        )
        for row in rows
    ]
    
    return AuditLogResponse(
        entries=entries,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/actions")
async def list_actions(user: dict = Depends(require_role("admin"))):
    """Get list of unique actions in audit log."""
    db = await get_control_db()
    
    cursor = await db.execute(
        "SELECT DISTINCT action FROM audit_log ORDER BY action"
    )
    rows = await cursor.fetchall()
    
    return {"actions": [row[0] for row in rows]}


@router.get("/summary")
async def audit_summary(
    days: int = Query(7, ge=1, le=90),
    user: dict = Depends(require_role("admin"))
):
    """Get audit log summary for the last N days."""
    db = await get_control_db()
    
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    
    # Actions by type
    cursor = await db.execute(
        """SELECT action, COUNT(*) as count
           FROM audit_log
           WHERE created_at >= ?
           GROUP BY action
           ORDER BY count DESC
           LIMIT 10""",
        (since,)
    )
    actions = [{"action": row[0], "count": row[1]} for row in await cursor.fetchall()]
    
    # Actions by user
    cursor = await db.execute(
        """SELECT u.username, COUNT(*) as count
           FROM audit_log a
           JOIN users u ON a.user_id = u.id
           WHERE a.created_at >= ?
           GROUP BY a.user_id
           ORDER BY count DESC
           LIMIT 10""",
        (since,)
    )
    users = [{"username": row[0], "count": row[1]} for row in await cursor.fetchall()]
    
    # Actions per day
    cursor = await db.execute(
        """SELECT date(created_at) as day, COUNT(*) as count
           FROM audit_log
           WHERE created_at >= ?
           GROUP BY day
           ORDER BY day""",
        (since,)
    )
    daily = [{"day": row[0], "count": row[1]} for row in await cursor.fetchall()]
    
    return {
        "period_days": days,
        "top_actions": actions,
        "top_users": users,
        "daily_counts": daily
    }
