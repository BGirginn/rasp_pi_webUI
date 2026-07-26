"""Persistent minute-resolution scheduler for safe maintenance jobs."""

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import structlog

from db import get_control_db
from services.agent_client import agent_client
from services.sse import Channels, sse_manager

logger = structlog.get_logger(__name__)

SAFE_SCHEDULED_TYPES = {"backup", "healthcheck", "cleanup"}
FIELD_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))


def _expand_field(value: str, minimum: int, maximum: int) -> set[int]:
    result: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            raise ValueError("Empty cron field")
        step = 1
        if "/" in part:
            part, raw_step = part.split("/", 1)
            step = int(raw_step)
            if step < 1:
                raise ValueError("Cron step must be positive")
        if part == "*":
            start, end = minimum, maximum
        elif "-" in part:
            raw_start, raw_end = part.split("-", 1)
            start, end = int(raw_start), int(raw_end)
        else:
            start = end = int(part)
        if start < minimum or end > maximum or start > end:
            raise ValueError(f"Cron value must be between {minimum} and {maximum}")
        result.update(range(start, end + 1, step))
    return result


def parse_cron(expression: str) -> tuple[set[int], ...]:
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError("Cron expression must have five fields")
    return tuple(_expand_field(value, *bounds) for value, bounds in zip(fields, FIELD_RANGES))


def next_cron_run(expression: str, timezone_name: str, after: datetime | None = None) -> datetime:
    minutes, hours, days, months, weekdays = parse_cron(expression)
    zone = ZoneInfo(timezone_name)
    cursor = (after or datetime.now(timezone.utc)).astimezone(zone)
    cursor = cursor.replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = cursor + timedelta(days=366)
    while cursor <= limit:
        cron_weekday = (cursor.weekday() + 1) % 7
        if (
            cursor.minute in minutes
            and cursor.hour in hours
            and cursor.day in days
            and cursor.month in months
            and cron_weekday in weekdays
        ):
            return cursor.astimezone(timezone.utc)
        cursor += timedelta(minutes=1)
    raise ValueError("Cron expression has no run time within one year")


class JobScheduler:
    def __init__(self):
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Job scheduler started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def _loop(self) -> None:
        while self._running:
            try:
                await self.run_due()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Scheduled job scan failed", error=str(exc))
            await asyncio.sleep(30)

    async def run_due(self) -> None:
        db = await get_control_db()
        now = datetime.now(timezone.utc)
        cursor = await db.execute(
            """SELECT id, name, job_type, config_json, cron_expression, timezone, created_by
               FROM job_schedules
               WHERE enabled = 1 AND next_run_at IS NOT NULL AND next_run_at <= ?""",
            (now.isoformat(),),
        )
        for row in await cursor.fetchall():
            schedule_id, name, job_type, config_json, expression, timezone_name, user_id = row
            if job_type not in SAFE_SCHEDULED_TYPES:
                continue
            config = json.loads(config_json or "{}")
            if job_type == "cleanup":
                config["dry_run"] = True
                config["confirmed"] = False
            job_id = str(uuid.uuid4())[:8]
            config["job_id"] = job_id
            next_run = next_cron_run(expression, timezone_name, now).isoformat()
            await db.execute(
                """INSERT INTO jobs
                       (id, name, type, state, config_json, phase, progress, cancellable,
                        started_by, created_at, updated_at)
                   VALUES (?, ?, ?, 'pending', ?, 'queued', 0, 1, ?, ?, ?)""",
                (job_id, name, job_type, json.dumps(config), user_id, now.isoformat(), now.isoformat()),
            )
            await db.execute(
                """UPDATE job_schedules SET last_run_at=?, next_run_at=?, updated_at=? WHERE id=?""",
                (now.isoformat(), next_run, now.isoformat(), schedule_id),
            )
            await db.commit()
            try:
                await agent_client.run_job(job_type, name, config)
            except Exception as exc:
                await db.execute("UPDATE jobs SET error=? WHERE id=?", (f"Agent unavailable: {exc}", job_id))
                await db.commit()
            await sse_manager.broadcast(Channels.JOBS, "job_created", {"job_id": job_id, "type": job_type})


job_scheduler = JobScheduler()
