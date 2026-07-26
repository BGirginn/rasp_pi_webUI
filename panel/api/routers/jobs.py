"""
Pi Control Panel - Jobs Router

Handles job scheduling, execution, and history.
"""

import json
import uuid
import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from db import get_control_db
from services.agent_client import agent_client
from services.sse import sse_manager, Channels
from services.job_scheduler import SAFE_SCHEDULED_TYPES, next_cron_run, parse_cron
from .auth import get_current_user, require_role, get_current_user_sse
from time_utils import utc_now

router = APIRouter()


async def _sync_job_status(db, job_id: str) -> None:
    """Sync job status from agent if available."""
    try:
        status = await agent_client.get_job_status(job_id)
    except Exception:
        return

    if not status:
        return

    state = status.get("state")
    result = status.get("result")
    error = status.get("error")
    completed_at = status.get("completed_at")
    started_at = status.get("started_at")

    progress = int(status.get("progress", 0))

    await db.execute(
        """UPDATE jobs SET state = ?, progress = ?, result_json = ?, error = ?,
                  phase = ?, cancellable = ?, checkpoint_json = ?, updated_at = datetime('now'),
                  started_at = COALESCE(?, started_at),
                  completed_at = COALESCE(?, completed_at)
           WHERE id = ?""",
        (
            state,
            progress,
            json.dumps(result) if result else None,
            error,
            status.get("phase"),
            int(status.get("cancellable", False)),
            json.dumps(status.get("checkpoint")) if status.get("checkpoint") is not None else None,
            started_at,
            completed_at,
            job_id,
        )
    )
    await db.commit()


async def _sync_agent_jobs(db) -> None:
    """Mirror durable agent job state without inventing fallback status."""
    try:
        statuses = await agent_client.list_jobs(limit=200)
    except Exception:
        return
    for status in statuses or []:
        await db.execute(
            """UPDATE jobs SET state = ?, progress = ?, result_json = ?, error = ?,
                      phase = ?, cancellable = ?, checkpoint_json = ?,
                      started_at = COALESCE(?, started_at),
                      completed_at = COALESCE(?, completed_at), updated_at = datetime('now')
               WHERE id = ?""",
            (
                status.get("state", "pending"),
                int(status.get("progress", 0)),
                json.dumps(status.get("result")) if status.get("result") is not None else None,
                status.get("error"),
                status.get("phase"),
                int(status.get("cancellable", False)),
                json.dumps(status.get("checkpoint")) if status.get("checkpoint") is not None else None,
                status.get("started_at"),
                status.get("completed_at"),
                status.get("id"),
            ),
        )
    await db.commit()


async def _sync_job_logs(db, job_id: str) -> None:
    """Sync job logs from agent if available."""
    try:
        logs = await agent_client.get_job_logs(job_id)
    except Exception:
        return

    if not logs:
        return

    cursor = await db.execute(
        "SELECT created_at FROM job_logs WHERE job_id = ? ORDER BY created_at DESC LIMIT 1",
        (job_id,)
    )
    row = await cursor.fetchone()
    last_ts = row[0] if row else None

    new_logs = []
    for entry in logs:
        created_at = entry.get("created_at")
        if last_ts and created_at and created_at <= last_ts:
            continue
        new_logs.append(entry)

    for entry in new_logs:
        await db.execute(
            "INSERT INTO job_logs (job_id, level, message, created_at) VALUES (?, ?, ?, ?)",
            (job_id, entry.get("level", "info"), entry.get("message", ""), entry.get("created_at"))
        )
    if new_logs:
        await db.commit()


class JobCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: str  # backup, restore, update, cleanup
    config: Optional[Dict] = None


class JobResponse(BaseModel):
    id: str
    name: str
    type: str
    state: str
    progress: int
    phase: Optional[str] = None
    cancellable: bool = False
    checkpoint: Optional[Dict] = None
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


class ScheduleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    job_type: str
    config: Dict = Field(default_factory=dict)
    cron_expression: str = Field(min_length=5, max_length=100)
    timezone: str = "Europe/Istanbul"
    enabled: bool = True


# Job type configurations
JOB_TYPES = {
    "backup": {
        "name": "System Backup",
        "description": "Backup configuration and data files",
        "config_schema": {
            "components": {"type": "array", "default": ["control_db", "telemetry_db", "app_config", "release"]},
        }
    },
    "restore": {
        "name": "System Restore",
        "description": "Restore from a backup archive",
        "config_schema": {
            "backup_path": {"type": "string", "required": True},
            "components": {"type": "array", "default": []},
            "dry_run": {"type": "boolean", "default": True},
            "confirmed": {"type": "boolean", "default": False},
        }
    },
    "update": {
        "name": "System Update",
        "description": "Update containers and system packages",
        "config_schema": {
            "scope": {"type": "string", "default": "application", "enum": ["application", "security"]},
            "branch": {"type": "string", "default": "main"},
            "approved_commit": {"type": "string", "default": ""},
            "dry_run": {"type": "boolean", "default": True},
            "confirmed": {"type": "boolean", "default": False},
        }
    },
    "cleanup": {
        "name": "Disk Cleanup",
        "description": "Clean up old logs, images, and temporary files",
        "config_schema": {
            "prune_unused_images": {"type": "boolean", "default": True},
            "retention_days": {"type": "integer", "default": 30},
            "dry_run": {"type": "boolean", "default": True},
            "confirmed": {"type": "boolean", "default": False},
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
    },
    "usb_format": {
        "name": "Format USB",
        "description": "Create a fresh filesystem on a removable USB disk",
        "config_schema": {
            "device_id": {"type": "string", "required": True},
            "filesystem": {"type": "string", "enum": ["exfat", "fat32", "ext4"]},
            "label": {"type": "string", "default": "PI-USB"},
            "confirmation": {"type": "string", "required": True},
        },
    },
    "usb_write_test": {
        "name": "USB Write Test",
        "description": "Verify removable storage with a temporary checksum file",
        "config_schema": {
            "device_id": {"type": "string", "required": True},
            "volume_id": {"type": "string"},
            "size_mb": {"type": "integer", "default": 64},
        },
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
    await _sync_agent_jobs(db)
    
    query = """SELECT id, name, type, state, progress, phase, cancellable, checkpoint_json,
                      config_json, result_json, error, started_by, started_at, completed_at, created_at
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
            phase=row[5],
            cancellable=bool(row[6]),
            checkpoint=json.loads(row[7]) if row[7] else None,
            config=json.loads(row[8]) if row[8] else None,
            result=json.loads(row[9]) if row[9] else None,
            error=row[10],
            started_by=row[11],
            started_at=row[12],
            completed_at=row[13],
            created_at=row[14]
        )
        for row in rows
    ]


@router.get("/schedules")
async def list_schedules(user: dict = Depends(get_current_user)):
    db = await get_control_db()
    cursor = await db.execute(
        """SELECT id, name, job_type, config_json, cron_expression, timezone, enabled,
                  next_run_at, last_run_at, created_by, created_at, updated_at
           FROM job_schedules ORDER BY name"""
    )
    return [
        {
            "id": row[0], "name": row[1], "job_type": row[2],
            "config": json.loads(row[3] or "{}"), "cron_expression": row[4],
            "timezone": row[5], "enabled": bool(row[6]), "next_run_at": row[7],
            "last_run_at": row[8], "created_by": row[9], "created_at": row[10],
            "updated_at": row[11],
        }
        for row in await cursor.fetchall()
    ]


@router.post("/schedules", status_code=201)
async def create_schedule(schedule: ScheduleCreate, user: dict = Depends(require_role("admin"))):
    if schedule.job_type not in SAFE_SCHEDULED_TYPES:
        raise HTTPException(status_code=400, detail="Only backup, cleanup, and healthcheck can be scheduled")
    try:
        parse_cron(schedule.cron_expression)
        next_run = next_cron_run(schedule.cron_expression, schedule.timezone).isoformat()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid schedule: {exc}")
    config = dict(schedule.config)
    if schedule.job_type == "cleanup":
        config.update({"dry_run": True, "confirmed": False})
    schedule_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    db = await get_control_db()
    await db.execute(
        """INSERT INTO job_schedules
               (id, name, job_type, config_json, cron_expression, timezone, enabled,
                next_run_at, created_by, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (schedule_id, schedule.name, schedule.job_type, json.dumps(config),
         schedule.cron_expression, schedule.timezone, int(schedule.enabled),
         next_run if schedule.enabled else None, user["id"], now, now),
    )
    await db.execute(
        "INSERT INTO audit_log (user_id, action, details) VALUES (?, 'job_schedule.create', ?)",
        (user["id"], json.dumps({"schedule_id": schedule_id, "job_type": schedule.job_type})),
    )
    await db.commit()
    return {"id": schedule_id, "next_run_at": next_run if schedule.enabled else None}


@router.put("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    schedule: ScheduleCreate,
    user: dict = Depends(require_role("admin")),
):
    if schedule.job_type not in SAFE_SCHEDULED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported scheduled job type")
    try:
        next_run = next_cron_run(schedule.cron_expression, schedule.timezone).isoformat()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid schedule: {exc}")
    config = dict(schedule.config)
    if schedule.job_type == "cleanup":
        config.update({"dry_run": True, "confirmed": False})
    db = await get_control_db()
    cursor = await db.execute(
        """UPDATE job_schedules SET name=?, job_type=?, config_json=?, cron_expression=?,
                  timezone=?, enabled=?, next_run_at=?, updated_at=datetime('now') WHERE id=?""",
        (schedule.name, schedule.job_type, json.dumps(config), schedule.cron_expression,
         schedule.timezone, int(schedule.enabled), next_run if schedule.enabled else None, schedule_id),
    )
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await db.commit()
    return {"id": schedule_id, "next_run_at": next_run if schedule.enabled else None}


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str, user: dict = Depends(require_role("admin"))):
    db = await get_control_db()
    cursor = await db.execute("DELETE FROM job_schedules WHERE id=?", (schedule_id,))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await db.execute(
        "INSERT INTO audit_log (user_id, action, details) VALUES (?, 'job_schedule.delete', ?)",
        (user["id"], schedule_id),
    )
    await db.commit()
    return {"deleted": True}


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, user: dict = Depends(get_current_user)):
    """Get job details."""
    db = await get_control_db()

    await _sync_job_status(db, job_id)
    await _sync_job_logs(db, job_id)
    
    cursor = await db.execute(
        """SELECT id, name, type, state, progress, phase, cancellable, checkpoint_json,
                  config_json, result_json, error, started_by, started_at, completed_at, created_at
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
        phase=row[5],
        cancellable=bool(row[6]),
        checkpoint=json.loads(row[7]) if row[7] else None,
        config=json.loads(row[8]) if row[8] else None,
        result=json.loads(row[9]) if row[9] else None,
        error=row[10],
        started_by=row[11],
        started_at=row[12],
        completed_at=row[13],
        created_at=row[14]
    )


@router.post("", response_model=JobResponse)
async def create_job(
    job: JobCreate,
    user: dict = Depends(require_role("admin", "operator"))
):
    """Create and queue a new job."""
    if job.type not in JOB_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown job type: {job.type}")
    if job.type in {"restore", "update", "usb_format"} and user["role"] != "admin":
        raise HTTPException(status_code=403, detail=f"Only admins can run {job.type} jobs")
    if job.type == "cleanup" and not (job.config or {}).get("dry_run", True) and user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can apply cleanup jobs")
    
    if job.type in {"usb_format", "usb_write_test"}:
        from .devices import prepare_usb_job_config
        job.config = await prepare_usb_job_config(job.type, dict(job.config or {}))

    db = await get_control_db()
    
    job_id = str(uuid.uuid4())[:8]
    config_json = json.dumps(job.config) if job.config else None
    now = utc_now().isoformat()
    
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
    agent_error = None
    try:
        config = dict(job.config or {})
        config["job_id"] = job_id
        agent_job = await agent_client.run_job(job.type, job.name, config)
        
        # Update state to running
        await db.execute(
            """UPDATE jobs SET state = ?, progress = ?, phase = ?, cancellable = ?,
                      started_at = COALESCE(?, datetime('now')), updated_at = datetime('now') WHERE id = ?""",
            (agent_job.get("state", "pending"), int(agent_job.get("progress", 0)),
             agent_job.get("phase", "queued"), int(agent_job.get("cancellable", True)),
             agent_job.get("started_at"), job_id)
        )
        await db.commit()
    except Exception as exc:
        agent_error = f"Agent unavailable; job remains pending: {exc}"
        await db.execute("UPDATE jobs SET error = ? WHERE id = ?", (agent_error, job_id))
        await db.commit()
    
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
        state=agent_job.get("state", "pending") if 'agent_job' in locals() else "pending",
        progress=int(agent_job.get("progress", 0)) if 'agent_job' in locals() else 0,
        phase=agent_job.get("phase", "queued") if 'agent_job' in locals() else "queued",
        cancellable=bool(agent_job.get("cancellable", True)) if 'agent_job' in locals() else True,
        checkpoint=None,
        config=job.config,
        result=None,
        error=agent_error,
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
    config["job_id"] = job_id
    try:
        agent_job = await agent_client.run_job(row[1], row[2], config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start job: {str(e)}")
    
    # Update state
    await db.execute(
        """UPDATE jobs SET state = ?, progress = ?, phase = ?, cancellable = ?,
                  error = NULL, started_at = COALESCE(?, datetime('now')), updated_at = datetime('now')
           WHERE id = ?""",
        (agent_job.get("state", "pending"), int(agent_job.get("progress", 0)),
         agent_job.get("phase", "queued"), int(agent_job.get("cancellable", True)),
         agent_job.get("started_at"), job_id)
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
        cancelled = await agent_client.cancel_job(job_id)
        if not cancelled.get("success"):
            raise HTTPException(status_code=409, detail=cancelled.get("error", "Job cannot be cancelled"))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Agent unavailable: {exc}")
    
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

    await _sync_job_logs(db, job_id)
    
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


@router.get("/{job_id}/stream")
async def stream_job(
    job_id: str,
    user: dict = Depends(get_current_user_sse)
):
    """Stream job updates and logs via SSE."""
    async def event_generator():
        while True:
            db = await get_control_db()
            await _sync_job_status(db, job_id)
            await _sync_job_logs(db, job_id)

            job_cursor = await db.execute(
                """SELECT id, name, type, state, progress, phase, cancellable, checkpoint_json,
                          config_json, result_json, error, started_by, started_at, completed_at, created_at
                   FROM jobs WHERE id = ?""",
                (job_id,)
            )
            job_row = await job_cursor.fetchone()
            if not job_row:
                yield "event: job_update\ndata: {}\n\n"
                await asyncio.sleep(2)
                continue

            logs_cursor = await db.execute(
                "SELECT level, message, created_at FROM job_logs WHERE job_id = ? ORDER BY created_at",
                (job_id,)
            )
            logs = [
                {"level": r[0], "message": r[1], "created_at": r[2]}
                for r in await logs_cursor.fetchall()
            ]

            job = {
                "id": job_row[0],
                "name": job_row[1],
                "type": job_row[2],
                "state": job_row[3],
                "progress": job_row[4] or 0,
                "phase": job_row[5],
                "cancellable": bool(job_row[6]),
                "checkpoint": json.loads(job_row[7]) if job_row[7] else None,
                "config": json.loads(job_row[8]) if job_row[8] else None,
                "result": json.loads(job_row[9]) if job_row[9] else None,
                "error": job_row[10],
                "started_by": job_row[11],
                "started_at": job_row[12],
                "completed_at": job_row[13],
                "created_at": job_row[14],
            }

            payload = json.dumps({"job": job, "logs": logs})
            yield f"event: job_update\ndata: {payload}\n\n"
            await asyncio.sleep(2)

    return EventSourceResponse(event_generator())


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
