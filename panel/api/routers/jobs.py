"""
Pi Control Panel - Jobs Router

Handles job scheduling, execution, and history.
"""

import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from db import get_control_db
from services.agent_client import agent_client
from services.sse import sse_manager, Channels
from .auth import get_current_user, require_role

router = APIRouter()


class JobCreate(BaseModel):
    name: str
    type: str  # backup, restore, update, cleanup
    config: Optional[Dict] = None


class JobResponse(BaseModel):
    id: str
    name: str
    type: str
    state: str
    progress: int
    config: Optional[Dict]
    result: Optional[Dict]
    error: Optional[str]
    started_by: Optional[int]
    started_at: Optional[str]
    completed_at: Optional[str]
    created_at: str


class JobLogEntry(BaseModel):
    level: str
    message: str
    created_at: str


# Job type configurations
JOB_TYPES = {
    "backup": {
        "name": "System Backup",
        "description": "Backup configuration and data files",
        "config_schema": {
            "include_docker_volumes": {"type": "boolean", "default": True},
            "include_databases": {"type": "boolean", "default": True},
            "destination": {"type": "string", "default": "/backups"},
            "compression": {"type": "string", "default": "gzip", "enum": ["none", "gzip", "zstd"]},
        }
    },
    "restore": {
        "name": "System Restore",
        "description": "Restore from a backup archive",
        "config_schema": {
            "backup_path": {"type": "string", "required": True},
            "verify_checksum": {"type": "boolean", "default": True},
        }
    },
    "update": {
        "name": "System Update",
        "description": "Update containers and system packages",
        "config_schema": {
            "update_containers": {"type": "boolean", "default": True},
            "update_system": {"type": "boolean", "default": False},
            "auto_restart": {"type": "boolean", "default": True},
        }
    },
    "cleanup": {
        "name": "Disk Cleanup",
        "description": "Clean up old logs, images, and temporary files",
        "config_schema": {
            "prune_docker_images": {"type": "boolean", "default": True},
            "prune_docker_volumes": {"type": "boolean", "default": False},
            "clean_old_logs": {"type": "boolean", "default": True},
            "log_retention_days": {"type": "integer", "default": 30},
        }
    },
    "healthcheck": {
        "name": "Health Check",
        "description": "Run comprehensive system health check",
        "config_schema": {
            "check_containers": {"type": "boolean", "default": True},
            "check_services": {"type": "boolean", "default": True},
            "check_disk": {"type": "boolean", "default": True},
            "check_network": {"type": "boolean", "default": True},
        }
    }
}


@router.get("/types")
async def list_job_types(user: dict = Depends(get_current_user)):
    """List available job types and their configuration schemas."""
    return JOB_TYPES


@router.get("", response_model=List[JobResponse])
async def list_jobs(
    state: Optional[str] = Query(None, description="Filter by state"),
    type: Optional[str] = Query(None, description="Filter by type"),
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user)
):
    """List jobs with optional filters."""
    db = await get_control_db()
    
    query = """SELECT id, name, type, state, progress, config_json, result_json, 
                      error, started_by, started_at, completed_at, created_at
               FROM jobs WHERE 1=1"""
    params = []
    
    if state:
        query += " AND state = ?"
        params.append(state)
    
    if type:
        query += " AND type = ?"
        params.append(type)
    
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    
    return [
        JobResponse(
            id=row[0],
            name=row[1],
            type=row[2],
            state=row[3],
            progress=row[4] or 0,
            config=json.loads(row[5]) if row[5] else None,
            result=json.loads(row[6]) if row[6] else None,
            error=row[7],
            started_by=row[8],
            started_at=row[9],
            completed_at=row[10],
            created_at=row[11]
        )
        for row in rows
    ]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, user: dict = Depends(get_current_user)):
    """Get job details."""
    db = await get_control_db()
    
    cursor = await db.execute(
        """SELECT id, name, type, state, progress, config_json, result_json,
                  error, started_by, started_at, completed_at, created_at
           FROM jobs WHERE id = ?""",
        (job_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobResponse(
        id=row[0],
        name=row[1],
        type=row[2],
        state=row[3],
        progress=row[4] or 0,
        config=json.loads(row[5]) if row[5] else None,
        result=json.loads(row[6]) if row[6] else None,
        error=row[7],
        started_by=row[8],
        started_at=row[9],
        completed_at=row[10],
        created_at=row[11]
    )


@router.post("", response_model=JobResponse)
async def create_job(
    job: JobCreate,
    user: dict = Depends(require_role("admin", "operator"))
):
    """Create and queue a new job."""
    if job.type not in JOB_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown job type: {job.type}")
    
    db = await get_control_db()
    
    job_id = str(uuid.uuid4())[:8]
    config_json = json.dumps(job.config) if job.config else None
    now = datetime.utcnow().isoformat()
    
    await db.execute(
        """INSERT INTO jobs (id, name, type, state, config_json, started_by, created_at)
           VALUES (?, ?, ?, 'pending', ?, ?, ?)""",
        (job_id, job.name, job.type, config_json, user["id"], now)
    )
    
    # Audit log
    await db.execute(
        """INSERT INTO audit_log (user_id, action, details)
           VALUES (?, ?, ?)""",
        (user["id"], "job.create", f"job_id: {job_id}, type: {job.type}")
    )
    
    await db.commit()
    
    # Try to start job on agent
    try:
        await agent_client.run_job(job.type, job.name, job.config)
        
        # Update state to running
        await db.execute(
            "UPDATE jobs SET state = 'running', started_at = datetime('now') WHERE id = ?",
            (job_id,)
        )
        await db.commit()
    except Exception as e:
        pass  # Job will remain pending
    
    # Broadcast job creation
    await sse_manager.broadcast(Channels.JOBS, "job_created", {
        "job_id": job_id,
        "type": job.type,
        "name": job.name
    })
    
    return JobResponse(
        id=job_id,
        name=job.name,
        type=job.type,
        state="pending",
        progress=0,
        config=job.config,
        result=None,
        error=None,
        started_by=user["id"],
        started_at=None,
        completed_at=None,
        created_at=now
    )


@router.post("/{job_id}/run")
async def run_job(
    job_id: str,
    user: dict = Depends(require_role("admin", "operator"))
):
    """Start a pending job."""
    db = await get_control_db()
    
    cursor = await db.execute(
        "SELECT state, type, name, config_json FROM jobs WHERE id = ?",
        (job_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if row[0] != "pending":
        raise HTTPException(status_code=400, detail=f"Job is not pending (current: {row[0]})")
    
    # Start job on agent
    config = json.loads(row[3]) if row[3] else {}
    try:
        await agent_client.run_job(row[1], row[2], config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start job: {str(e)}")
    
    # Update state
    await db.execute(
        "UPDATE jobs SET state = 'running', started_at = datetime('now') WHERE id = ?",
        (job_id,)
    )
    
    # Audit log
    await db.execute(
        """INSERT INTO audit_log (user_id, action, details)
           VALUES (?, ?, ?)""",
        (user["id"], "job.run", f"job_id: {job_id}")
    )
    
    await db.commit()
    
    # Broadcast
    await sse_manager.broadcast(Channels.JOBS, "job_started", {"job_id": job_id})
    
    return {"message": f"Job {job_id} started"}


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    user: dict = Depends(require_role("admin"))
):
    """Cancel a running job."""
    db = await get_control_db()
    
    cursor = await db.execute(
        "SELECT state FROM jobs WHERE id = ?",
        (job_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if row[0] not in ("pending", "running"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel job in state: {row[0]}")
    
    # Cancel on agent
    try:
        await agent_client.cancel_job(job_id)
    except Exception:
        pass  # Agent may not be available
    
    # Update state
    await db.execute(
        "UPDATE jobs SET state = 'cancelled', completed_at = datetime('now') WHERE id = ?",
        (job_id,)
    )
    
    # Audit log
    await db.execute(
        """INSERT INTO audit_log (user_id, action, details)
           VALUES (?, ?, ?)""",
        (user["id"], "job.cancel", f"job_id: {job_id}")
    )
    
    await db.commit()
    
    # Broadcast
    await sse_manager.broadcast(Channels.JOBS, "job_cancelled", {"job_id": job_id})
    
    return {"message": f"Job {job_id} cancelled"}


@router.get("/{job_id}/logs", response_model=List[JobLogEntry])
async def get_job_logs(
    job_id: str,
    user: dict = Depends(get_current_user)
):
    """Get logs for a specific job."""
    db = await get_control_db()
    
    cursor = await db.execute(
        """SELECT level, message, created_at FROM job_logs
           WHERE job_id = ? ORDER BY created_at""",
        (job_id,)
    )
    rows = await cursor.fetchall()
    
    return [
        JobLogEntry(level=row[0], message=row[1], created_at=row[2])
        for row in rows
    ]


@router.delete("/{job_id}")
async def delete_job(
    job_id: str,
    user: dict = Depends(require_role("admin"))
):
    """Delete a completed/cancelled job."""
    db = await get_control_db()
    
    cursor = await db.execute(
        "SELECT state FROM jobs WHERE id = ?",
        (job_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if row[0] in ("pending", "running"):
        raise HTTPException(status_code=400, detail="Cannot delete active job")
    
    # Delete job logs first
    await db.execute("DELETE FROM job_logs WHERE job_id = ?", (job_id,))
    await db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    
    # Audit log
    await db.execute(
        """INSERT INTO audit_log (user_id, action, details)
           VALUES (?, ?, ?)""",
        (user["id"], "job.delete", f"job_id: {job_id}")
    )
    
    await db.commit()
    
    return {"message": f"Job {job_id} deleted"}
