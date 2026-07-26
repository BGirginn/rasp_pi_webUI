"""Durable Pi Agent job queue and execution lifecycle."""

import asyncio
import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

import structlog

logger = structlog.get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


TERMINAL_STATES = {
    JobState.COMPLETED,
    JobState.FAILED,
    JobState.ROLLED_BACK,
    JobState.CANCELLED,
}


@dataclass
class Job:
    id: str
    name: str
    type: str
    state: JobState = JobState.PENDING
    config: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    phase: str = "queued"
    progress: int = 0
    cancellable: bool = True
    checkpoint: Optional[Dict[str, Any]] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "state": self.state.value,
            "config": self.config,
            "result": self.result,
            "error": self.error,
            "phase": self.phase,
            "progress": self.progress,
            "cancellable": self.cancellable,
            "checkpoint": self.checkpoint,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class JobHandler(Protocol):
    async def precheck(self, job: Job) -> Dict[str, Any]: ...
    async def execute(self, job: Job) -> Dict[str, Any]: ...
    async def snapshot(self, job: Job) -> Dict[str, Any]: ...
    async def verify(self, job: Job, result: Dict[str, Any]) -> Dict[str, Any]: ...
    async def rollback(self, job: Job, snapshot: Dict[str, Any]) -> Dict[str, Any]: ...


class UnsupportedJobHandler:
    def __init__(self, job_type: str):
        self.job_type = job_type

    async def precheck(self, job: Job) -> Dict[str, Any]:
        return {"passed": False, "reason": f"Job type '{self.job_type}' is not implemented"}

    async def execute(self, job: Job) -> Dict[str, Any]:
        raise RuntimeError(f"Job type '{self.job_type}' is not implemented")


class JobRunner:
    """Runs jobs while persisting state independently from the panel database."""

    def __init__(self, config: dict):
        self.config = config.get("jobs", {})
        self._max_concurrent = max(1, int(self.config.get("max_concurrent", 2)))
        self._default_timeout = max(30, int(self.config.get("default_timeout", 600)))
        self._db_path = Path(self.config.get("db_path", "/var/lib/pi-control/jobs.db"))
        self._jobs: Dict[str, Job] = {}
        self._running_jobs: Dict[str, asyncio.Task] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._workers: List[asyncio.Task] = []
        self._handlers: Dict[str, JobHandler] = {}
        self._db: Optional[sqlite3.Connection] = None
        self._running = False

        for job_type in ("backup", "restore", "update", "cleanup", "healthcheck"):
            self.register_handler(job_type, UnsupportedJobHandler(job_type))

    @property
    def is_healthy(self) -> bool:
        return self._running and len(self._running_jobs) <= self._max_concurrent

    def register_handler(self, job_type: str, handler: JobHandler) -> None:
        self._handlers[job_type] = handler

    def _open_db(self) -> None:
        if self._db:
            return
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self._db_path, timeout=5, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.execute("PRAGMA busy_timeout=5000")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                state TEXT NOT NULL,
                config_json TEXT NOT NULL,
                result_json TEXT,
                error TEXT,
                phase TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                cancellable INTEGER NOT NULL DEFAULT 1,
                checkpoint_json TEXT,
                started_at TEXT,
                completed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS job_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_agent_jobs_state ON jobs(state, created_at);
            CREATE INDEX IF NOT EXISTS idx_agent_job_logs_job ON job_logs(job_id, id);
            """
        )
        self._db.commit()

    def _load_jobs(self) -> List[str]:
        assert self._db
        rows = self._db.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 500").fetchall()
        pending: List[str] = []
        for row in rows:
            job = self._row_to_job(row)
            if job.state == JobState.RUNNING:
                job.state = JobState.FAILED
                job.phase = "interrupted"
                job.error = "Agent restarted while the job was running"
                job.cancellable = False
                job.completed_at = _now()
                self._save_job(job)
                self._append_log(job.id, "error", job.error)
            elif job.state == JobState.PENDING:
                pending.append(job.id)
            self._jobs[job.id] = job
        return list(reversed(pending))

    async def start(self) -> None:
        if self._running:
            return
        self._open_db()
        pending = self._load_jobs()
        self._running = True
        for job_id in pending:
            await self._queue.put(job_id)
        for worker_id in range(self._max_concurrent):
            self._workers.append(asyncio.create_task(self._worker_loop(worker_id)))
        logger.info("Durable job runner started", workers=self._max_concurrent, db=str(self._db_path))

    async def stop(self) -> None:
        self._running = False
        for task in list(self._running_jobs.values()):
            task.cancel()
        for worker in self._workers:
            worker.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        self._running_jobs.clear()
        if self._db:
            self._db.commit()
            self._db.close()
            self._db = None
        logger.info("Durable job runner stopped")

    async def _worker_loop(self, worker_id: int) -> None:
        while self._running:
            try:
                job_id = await self._queue.get()
                job = self._jobs.get(job_id)
                if not job or job.state != JobState.PENDING:
                    self._queue.task_done()
                    continue
                task = asyncio.create_task(self._execute_job(job))
                self._running_jobs[job.id] = task
                try:
                    await task
                finally:
                    self._running_jobs.pop(job.id, None)
                    self._queue.task_done()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Job worker failed", worker=worker_id, error=str(exc))

    def _transition(self, job: Job, phase: str, progress: int, cancellable: bool = True) -> None:
        job.phase = phase
        job.progress = max(0, min(100, progress))
        job.cancellable = cancellable
        job.updated_at = _now()
        self._save_job(job)

    async def _execute_job(self, job: Job) -> None:
        job.state = JobState.RUNNING
        job.started_at = _now()
        self._transition(job, "precheck", 2)
        self._append_log(job.id, "info", f"Job started: {job.name} ({job.type})")
        snapshot: Optional[Dict[str, Any]] = None
        try:
            handler = self._handlers.get(job.type)
            if not handler:
                raise ValueError(f"Unknown job type: {job.type}")
            precheck = await self._run_with_timeout(handler.precheck(job), 60, "precheck")
            if not precheck.get("passed", False):
                raise ValueError(f"Precheck failed: {precheck.get('reason', 'Unknown')}")
            self._append_log(job.id, "info", "Precheck passed")

            if hasattr(handler, "snapshot"):
                self._transition(job, "snapshot", 10)
                snapshot = await self._run_with_timeout(handler.snapshot(job), 300, "snapshot")
                job.checkpoint = snapshot
                self._save_job(job)

            self._transition(job, "execute", 25)
            result = await self._run_with_timeout(
                handler.execute(job),
                int(job.config.get("timeout", self._default_timeout)),
                "execute",
            )
            if isinstance(result, dict) and result.get("output"):
                self._append_log(job.id, "info", str(result["output"]))

            if hasattr(handler, "verify"):
                self._transition(job, "verify", 90, cancellable=False)
                verification = await self._run_with_timeout(handler.verify(job, result), 120, "verify")
                if not verification.get("passed", True):
                    raise RuntimeError(f"Verification failed: {verification.get('reason', 'Unknown')}")

            job.state = JobState.COMPLETED
            job.result = result
            job.error = None
            self._transition(job, "completed", 100, cancellable=False)
            self._append_log(job.id, "info", "Job completed")
        except asyncio.CancelledError:
            job.state = JobState.CANCELLED
            job.error = "Job cancelled"
            self._transition(job, "cancelled", job.progress, cancellable=False)
            self._append_log(job.id, "warning", job.error)
            raise
        except Exception as exc:
            original_error = str(exc)
            if snapshot and hasattr(self._handlers.get(job.type), "rollback"):
                try:
                    self._transition(job, "rollback", 95, cancellable=False)
                    await self._run_with_timeout(
                        self._handlers[job.type].rollback(job, snapshot), 300, "rollback"
                    )
                    job.state = JobState.ROLLED_BACK
                except Exception as rollback_exc:
                    job.state = JobState.FAILED
                    original_error = f"{original_error}; rollback failed: {rollback_exc}"
            else:
                job.state = JobState.FAILED
            job.error = original_error
            self._transition(job, job.state.value, job.progress, cancellable=False)
            self._append_log(job.id, "error", original_error)
            logger.exception("Job failed", job_id=job.id, error=original_error)
        finally:
            job.completed_at = _now()
            job.updated_at = job.completed_at
            self._save_job(job)

    async def _run_with_timeout(self, coro, timeout: int, name: str) -> Any:
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            logger.error("Job phase timed out", phase=name, timeout=timeout)
            raise

    async def run_job(self, job_type: str, name: str, config: Optional[Dict] = None) -> Dict[str, Any]:
        if not self._db:
            self._open_db()
        config = dict(config or {})
        job_id = str(config.pop("job_id", "") or str(uuid.uuid4())[:8])
        existing = self._jobs.get(job_id)
        if existing and existing.state not in TERMINAL_STATES:
            return existing.to_dict()
        job = Job(id=job_id, name=name.strip() or job_type, type=job_type, config=config)
        self._jobs[job_id] = job
        self._save_job(job)
        self._append_log(job_id, "info", f"Job queued: {job.name} ({job.type})")
        await self._queue.put(job_id)
        return job.to_dict()

    async def get_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        if not self._db:
            self._open_db()
        job = self._jobs.get(job_id)
        if not job and self._db:
            row = self._db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            job = self._row_to_job(row) if row else None
        return job.to_dict() if job else None

    async def cancel_job(self, job_id: str) -> Dict[str, Any]:
        job = self._jobs.get(job_id)
        if not job:
            return {"success": False, "error": "Job not found"}
        if job.state in TERMINAL_STATES:
            return {"success": False, "error": f"Job already finished: {job.state.value}"}
        if not job.cancellable:
            return {"success": False, "error": f"Job cannot be cancelled during phase: {job.phase}"}
        task = self._running_jobs.get(job_id)
        if task:
            task.cancel()
        else:
            job.state = JobState.CANCELLED
            job.error = "Job cancelled before execution"
            job.completed_at = _now()
            self._transition(job, "cancelled", job.progress, cancellable=False)
        return {"success": True, "message": f"Job {job_id} cancelled"}

    async def list_jobs(self, state: Optional[JobState] = None, limit: int = 50) -> List[Dict[str, Any]]:
        if not self._db:
            self._open_db()
        query = "SELECT * FROM jobs"
        params: List[Any] = []
        if state:
            query += " WHERE state = ?"
            params.append(state.value)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 500)))
        rows = self._db.execute(query, params).fetchall()
        return [self._row_to_job(row).to_dict() for row in rows]

    async def get_logs(self, job_id: str) -> List[Dict[str, Any]]:
        if not self._db:
            self._open_db()
        rows = self._db.execute(
            "SELECT level, message, created_at FROM job_logs WHERE job_id = ? ORDER BY id LIMIT 1000",
            (job_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def _append_log(self, job_id: str, level: str, message: str) -> None:
        assert self._db
        self._db.execute(
            "INSERT INTO job_logs (job_id, level, message, created_at) VALUES (?, ?, ?, ?)",
            (job_id, level, message[:4000], _now()),
        )
        self._db.commit()

    def _save_job(self, job: Job) -> None:
        assert self._db
        job.updated_at = _now()
        self._db.execute(
            """
            INSERT INTO jobs (
                id, name, type, state, config_json, result_json, error, phase, progress,
                cancellable, checkpoint_json, started_at, completed_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, type=excluded.type, state=excluded.state,
                config_json=excluded.config_json, result_json=excluded.result_json,
                error=excluded.error, phase=excluded.phase, progress=excluded.progress,
                cancellable=excluded.cancellable, checkpoint_json=excluded.checkpoint_json,
                started_at=excluded.started_at, completed_at=excluded.completed_at,
                updated_at=excluded.updated_at
            """,
            (
                job.id, job.name, job.type, job.state.value, json.dumps(job.config),
                json.dumps(job.result) if job.result is not None else None, job.error,
                job.phase, job.progress, int(job.cancellable),
                json.dumps(job.checkpoint) if job.checkpoint is not None else None,
                job.started_at, job.completed_at, job.created_at, job.updated_at,
            ),
        )
        self._db.commit()

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> Job:
        return Job(
            id=row["id"], name=row["name"], type=row["type"], state=JobState(row["state"]),
            config=json.loads(row["config_json"] or "{}"),
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            error=row["error"], phase=row["phase"], progress=row["progress"],
            cancellable=bool(row["cancellable"]),
            checkpoint=json.loads(row["checkpoint_json"]) if row["checkpoint_json"] else None,
            started_at=row["started_at"], completed_at=row["completed_at"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )
