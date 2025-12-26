"""
Rollback Worker
Background loop to execute rollback jobs when due.
"""

import asyncio
import time

from core.actions.engine import execute_action
from core.rollback.jobs import get_due_jobs, mark_job_status
from db import get_control_db

SYSTEM_USER = {
    "id": "__system__",
    "username": "__rollback_worker__",
    "role": "owner",
}


async def process_due_jobs() -> None:
    """Process all due rollback jobs once."""
    db = await get_control_db()
    now_ts = int(time.time())
    jobs = await get_due_jobs(db, now_ts)

    for job in jobs:
        status = "expired"
        try:
            result = await execute_action(
                db=db,
                user=SYSTEM_USER,
                action_id=job["rollback_action_id"],
                params=job["payload"],
                confirm=True,
            )
            if isinstance(result, dict) and result.get("success") is False:
                status = "expired"
            else:
                status = "rolled_back"
        except Exception:
            status = "expired"

        await mark_job_status(db, job["id"], status)


async def rollback_worker(stop_event: asyncio.Event) -> None:
    """Run rollback worker loop until stop_event is set."""
    while not stop_event.is_set():
        await process_due_jobs()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=5)
        except asyncio.TimeoutError:
            continue
