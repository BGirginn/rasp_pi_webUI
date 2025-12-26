"""
Jobs API Router
Read-only endpoints for viewing action jobs and rollback jobs.
"""

from typing import Optional, Literal
from datetime import datetime
import time
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from api.deps import current_user
from db import get_control_db


router = APIRouter()


# -------------------------
# Response Models
# -------------------------

class Job(BaseModel):
    """Unified job model for action and rollback jobs."""
    id: str
    type: Literal["action", "rollback"]
    action_id: str
    action_title: str
    created_at: str
    created_by_user_id: str
    created_by_username: str
    
    # States
    status: Literal["pending", "running", "confirmed", "rolled_back", "failed", "expired"]
    
    # Timeline
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    confirmed_at: Optional[str] = None
    
    # Rollback specific
    rollback_action_id: Optional[str] = None
    due_at: Optional[int] = None  # Unix timestamp
    time_remaining: Optional[int] = None  # Seconds
    
    # Results
    result: Optional[dict] = None
    error: Optional[str] = None


class JobsListResponse(BaseModel):
    """Paginated jobs list."""
    total: int
    skip: int
    limit: int
    jobs: list[Job]


# -------------------------
# Endpoints
# -------------------------

@router.get("", response_model=JobsListResponse)
async def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    job_type: Optional[Literal["action", "rollback"]] = Query(None, description="Filter by job type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    user: dict = Depends(current_user)
):
    """
    List all jobs (action + rollback) with pagination and filtering.
    
    Requires: operator role or higher
    """
    db = await get_control_db()
    
    # Query rollback jobs
    rollback_query = """
        SELECT 
            id,
            'rollback' as type,
            action_id,
            rollback_action_id,
            created_by_user_id,
            created_at,
            due_at,
            confirmed_at,
            status,
            payload_json
        FROM rollback_jobs
        WHERE 1=1
    """
    rollback_params = []
    
    if status:
        rollback_query += " AND status = ?"
        rollback_params.append(status)
    
    rollback_query += " ORDER BY created_at DESC"
    
    cursor = await db.execute(rollback_query, rollback_params)
    rollback_rows = await cursor.fetchall()
    
    # Build jobs list
    jobs = []
    now = int(time.time())
    
    for row in rollback_rows:
        import json
        
        # Get username from user_id
        user_cursor = await db.execute(
            "SELECT username FROM users WHERE id = ?",
            (row["created_by_user_id"],)
        )
        user_row = await user_cursor.fetchone()
        username = user_row["username"] if user_row else "unknown"
        
        # Calculate time remaining
        time_remaining = None
        if row["due_at"] and row["status"] == "pending":
            time_remaining = max(0, row["due_at"] - now)
        
        action_title = row["action_id"].split(".")[-1].replace("_", " ").title()
        
        job = Job(
            id=row["id"],
            type="rollback",
            action_id=row["action_id"],
            action_title=action_title,
            created_at=datetime.fromtimestamp(row["created_at"]).isoformat() if row["created_at"] else None,
            created_by_user_id=row["created_by_user_id"],
            created_by_username=username,
            status=row["status"],
            rollback_action_id=row["rollback_action_id"],
            due_at=row["due_at"],
            time_remaining=time_remaining,
            confirmed_at=datetime.fromtimestamp(row["confirmed_at"]).isoformat() if row["confirmed_at"] else None
        )
        jobs.append(job)
    
    # Filter by type if specified
    if job_type:
        jobs = [j for j in jobs if j.type == job_type]
    
    # Apply pagination
    total = len(jobs)
    jobs = jobs[skip:skip + limit]
    
    return JobsListResponse(
        total=total,
        skip=skip,
        limit=limit,
        jobs=jobs
    )


@router.get("/{job_id}")
async def get_job_detail(
    job_id: str,
    user: dict = Depends(current_user)
):
    """
    Get detailed information for a single job.
    
    Requires: operator role or higher
    """
    db = await get_control_db()
    
    # Try rollback jobs first
    cursor = await db.execute(
        "SELECT * FROM rollback_jobs WHERE id = ?",
        (job_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get username
    user_cursor = await db.execute(
        "SELECT username FROM users WHERE id = ?",
        (row["created_by_user_id"],)
    )
    user_row = await user_cursor.fetchone()
    username = user_row["username"] if user_row else "unknown"
    
    # Calculate time remaining
    now = int(time.time())
    time_remaining = None
    if row["due_at"] and row["status"] == "pending":
        time_remaining = max(0, row["due_at"] - now)
    
    action_title = row["action_id"].split(".")[-1].replace("_", " ").title()
    
    return Job(
        id=row["id"],
        type="rollback",
        action_id=row["action_id"],
        action_title=action_title,
        created_at=datetime.fromtimestamp(row["created_at"]).isoformat() if row["created_at"] else None,
        created_by_user_id=row["created_by_user_id"],
        created_by_username=username,
        status=row["status"],
        rollback_action_id=row["rollback_action_id"],
        due_at=row["due_at"],
        time_remaining=time_remaining,
        confirmed_at=datetime.fromtimestamp(row["confirmed_at"]).isoformat() if row["confirmed_at"] else None
    )
