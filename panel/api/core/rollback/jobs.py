"""
Rollback Jobs
Database helpers for rollback scheduling and state transitions.
"""

import json
import time
import uuid
from typing import Optional


async def create_rollback_job(
    *,
    db,
    action_id: str,
    rollback_action_id: str,
    payload: dict,
    user_id: str,
    timeout_seconds: int
) -> str:
    """Create a rollback job and return the job ID."""
    job_id = str(uuid.uuid4())
    now = int(time.time())
    due_at = now + timeout_seconds

    await db.execute(
        """
        INSERT INTO rollback_jobs (
            id, action_id, rollback_action_id, payload_json,
            created_by_user_id, due_at, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            action_id,
            rollback_action_id,
            json.dumps(payload),
            str(user_id),
            due_at,
            "pending",
            now,
        ),
    )
    await db.commit()

    return job_id


async def get_job(db, job_id: str) -> Optional[dict]:
    """Fetch a rollback job by id."""
    cursor = await db.execute(
        """
        SELECT id, action_id, rollback_action_id, payload_json, created_by_user_id,
               due_at, confirmed_at, status, created_at
        FROM rollback_jobs WHERE id = ?
        """,
        (job_id,),
    )
    row = await cursor.fetchone()
    if not row:
        return None

    return {
        "id": row[0],
        "action_id": row[1],
        "rollback_action_id": row[2],
        "payload": json.loads(row[3]),
        "created_by_user_id": row[4],
        "due_at": row[5],
        "confirmed_at": row[6],
        "status": row[7],
        "created_at": row[8],
    }


async def get_due_jobs(db, now_ts: int) -> list[dict]:
    """Return pending rollback jobs due at or before now."""
    cursor = await db.execute(
        """
        SELECT id, action_id, rollback_action_id, payload_json, created_by_user_id,
               due_at, confirmed_at, status, created_at
        FROM rollback_jobs
        WHERE status = 'pending' AND due_at <= ?
        """,
        (now_ts,),
    )
    rows = await cursor.fetchall()

    jobs = []
    for row in rows:
        jobs.append({
            "id": row[0],
            "action_id": row[1],
            "rollback_action_id": row[2],
            "payload": json.loads(row[3]),
            "created_by_user_id": row[4],
            "due_at": row[5],
            "confirmed_at": row[6],
            "status": row[7],
            "created_at": row[8],
        })

    return jobs


async def mark_job_confirmed(db, job_id: str, confirmed_at: int) -> None:
    """Mark rollback job as confirmed."""
    await db.execute(
        """
        UPDATE rollback_jobs
        SET status = 'confirmed', confirmed_at = ?
        WHERE id = ?
        """,
        (confirmed_at, job_id),
    )
    await db.commit()


async def mark_job_status(db, job_id: str, status: str) -> None:
    """Update rollback job status."""
    await db.execute(
        "UPDATE rollback_jobs SET status = ? WHERE id = ?",
        (status, job_id),
    )
    await db.commit()
