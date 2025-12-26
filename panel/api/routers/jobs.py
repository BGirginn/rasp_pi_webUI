"""
Pi Control Panel - Jobs Router

Handles job scheduling, execution, and history.
"""

import json
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from db import get_control_db
from .auth import get_current_user

router = APIRouter()


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
