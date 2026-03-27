"""
Pi Agent - Job Runner

Executes scheduled and manual jobs with precheck, snapshot, verify, and rollback.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

import structlog

logger = structlog.get_logger(__name__)


class JobState(str, Enum):
    """Job execution state."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Job definition and state."""

    id: str
    name: str
    type: str
    state: JobState = JobState.PENDING
    config: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "state": self.state.value,
            "config": self.config,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
        }


class JobHandler(Protocol):
    """Job handler contract."""

    async def precheck(self, job: Job) -> Dict[str, Any]:
        ...

    async def execute(self, job: Job) -> Dict[str, Any]:
        ...

    async def snapshot(self, job: Job) -> Dict[str, Any]:
        ...

    async def verify(self, job: Job, result: Dict[str, Any]) -> Dict[str, Any]:
        ...

    async def rollback(self, job: Job, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        ...


class UnsupportedJobHandler:
    """Fallback handler for job types that are not implemented yet."""

    def __init__(self, job_type: str):
        self.job_type = job_type

    async def precheck(self, job: Job) -> Dict[str, Any]:
        return {
            "passed": False,
            "reason": f"Job type '{self.job_type}' is not implemented on the agent yet",
        }

    async def execute(self, job: Job) -> Dict[str, Any]:
        raise RuntimeError(f"Job type '{self.job_type}' is not implemented on the agent yet")


class JobRunner:
    """Manages job queue and execution."""

    def __init__(self, config: dict):
        self.config = config.get("jobs", {})
        self._max_concurrent = self.config.get("max_concurrent", 2)
        self._default_timeout = self.config.get("default_timeout", 600)

        self._jobs: Dict[str, Job] = {}
        self._running_jobs: Dict[str, asyncio.Task] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._workers: List[asyncio.Task] = []
        self._running = False
        self._job_logs: Dict[str, List[Dict[str, Any]]] = {}
        self._handlers: Dict[str, JobHandler] = {}

        # Known API job types are registered as explicit unsupported handlers
        # until concrete implementations land.
        for job_type in ("backup", "restore", "update", "cleanup", "healthcheck"):
            self.register_handler(job_type, UnsupportedJobHandler(job_type))

    @property
    def is_healthy(self) -> bool:
        """Check if job runner is healthy."""
        return self._running and len(self._running_jobs) <= self._max_concurrent

    def register_handler(self, job_type: str, handler: JobHandler) -> None:
        """Register a job handler."""
        self._handlers[job_type] = handler

    async def start(self) -> None:
        """Start job runner workers."""
        if self._running:
            return

        self._running = True
        for i in range(self._max_concurrent):
            self._workers.append(asyncio.create_task(self._worker_loop(i)))

        logger.info("Job runner started", workers=self._max_concurrent)

    async def stop(self) -> None:
        """Stop job runner."""
        if not self._running and not self._workers:
            return

        self._running = False

        # Cancel running jobs first so worker tasks exit cleanly.
        for job_id, task in list(self._running_jobs.items()):
            task.cancel()
            job = self._jobs.get(job_id)
            if job and job.state not in (JobState.COMPLETED, JobState.FAILED, JobState.ROLLED_BACK):
                job.state = JobState.CANCELLED
                job.error = job.error or "Job cancelled"
                job.completed_at = datetime.utcnow()

        for worker in self._workers:
            worker.cancel()
        for worker in self._workers:
            try:
                await worker
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Worker shutdown error")

        self._workers.clear()
        self._running_jobs.clear()
        logger.info("Job runner stopped")

    async def _worker_loop(self, worker_id: int) -> None:
        """Worker loop that processes jobs from queue."""
        while self._running:
            try:
                try:
                    job_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                job = self._jobs.get(job_id)
                if not job:
                    continue
                if job.state == JobState.CANCELLED:
                    self._append_log(job_id, "info", "Queued job was cancelled before execution")
                    continue
                if job.state != JobState.PENDING:
                    continue

                logger.info("Worker processing job", worker=worker_id, job_id=job_id, type=job.type)

                job_task = asyncio.create_task(self._execute_job(job))
                self._running_jobs[job.id] = job_task
                try:
                    await job_task
                except asyncio.CancelledError:
                    if self._running:
                        # Job task was cancelled by an operator.
                        continue
                    raise
                finally:
                    self._running_jobs.pop(job.id, None)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception("Worker error", worker=worker_id, error=str(e))

    async def _execute_job(self, job: Job) -> None:
        """Execute a job with full lifecycle."""
        job.state = JobState.RUNNING
        job.started_at = datetime.utcnow()
        self._append_log(job.id, "info", f"Job started: {job.name} ({job.type})")

        try:
            handler = self._get_handler(job.type)
            if not handler:
                raise ValueError(f"Unknown job type: {job.type}")

            precheck_result = await self._run_with_timeout(
                handler.precheck(job),
                timeout=60,
                name="precheck",
            )
            if not precheck_result.get("passed", False):
                reason = precheck_result.get("reason", "Unknown")
                self._append_log(job.id, "error", f"Precheck failed: {reason}")
                raise ValueError(f"Precheck failed: {reason}")
            self._append_log(job.id, "info", "Precheck passed")

            snapshot = None
            if hasattr(handler, "snapshot"):
                snapshot = await self._run_with_timeout(
                    handler.snapshot(job),
                    timeout=300,
                    name="snapshot",
                )

            result = await self._run_with_timeout(
                handler.execute(job),
                timeout=job.config.get("timeout", self._default_timeout),
                name="execute",
            )
            if isinstance(result, dict) and result.get("output"):
                self._append_log(job.id, "info", str(result.get("output")))

            if hasattr(handler, "verify"):
                verify_result = await self._run_with_timeout(
                    handler.verify(job, result),
                    timeout=60,
                    name="verify",
                )
                if not verify_result.get("passed", True):
                    reason = verify_result.get("reason", "Unknown")
                    if snapshot and hasattr(handler, "rollback"):
                        await handler.rollback(job, snapshot)
                        job.state = JobState.ROLLED_BACK
                        job.error = f"Verification failed: {reason}"
                        self._append_log(job.id, "error", job.error)
                        return
                    raise ValueError(f"Verification failed: {reason}")

            job.state = JobState.COMPLETED
            job.result = result
            self._append_log(job.id, "info", "Job completed")

        except asyncio.CancelledError:
            job.state = JobState.CANCELLED
            job.error = "Job cancelled"
            self._append_log(job.id, "info", job.error)
            raise
        except asyncio.TimeoutError:
            job.state = JobState.FAILED
            job.error = "Job timed out"
            self._append_log(job.id, "error", job.error)
            logger.error("Job timed out", job_id=job.id)
        except Exception as e:
            job.state = JobState.FAILED
            job.error = str(e)
            self._append_log(job.id, "error", job.error)
            logger.exception("Job failed", job_id=job.id, error=str(e))
        finally:
            job.completed_at = datetime.utcnow()
            self._append_log(job.id, "info", f"Job finished with state: {job.state.value}")

    async def _run_with_timeout(self, coro, timeout: int, name: str) -> Any:
        """Run coroutine with timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            logger.error("Job step timed out", step=name, timeout=timeout)
            raise

    def _get_handler(self, job_type: str):
        """Get handler for job type."""
        return self._handlers.get(job_type)

    async def run_job(
        self,
        job_type: str,
        name: str,
        config: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Queue a job for execution."""
        job_id = None
        if config and isinstance(config, dict):
            job_id = config.get("job_id")
        job_id = job_id or str(uuid.uuid4())[:8]

        existing = self._jobs.get(job_id)
        if existing and existing.state in (JobState.PENDING, JobState.RUNNING):
            self._append_log(job_id, "warning", f"Job already queued: {name} ({job_type})")
            return existing.to_dict()

        job = Job(
            id=job_id,
            name=name,
            type=job_type,
            config=config or {},
        )

        self._jobs[job_id] = job
        await self._queue.put(job_id)
        self._append_log(job_id, "info", f"Job queued: {name} ({job_type})")
        logger.info("Job queued", job_id=job_id, type=job_type, name=name)

        return job.to_dict()

    async def get_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status."""
        job = self._jobs.get(job_id)
        return job.to_dict() if job else None

    async def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a running or queued job."""
        job = self._jobs.get(job_id)
        if not job:
            return {"success": False, "error": "Job not found"}

        if job.state in (JobState.COMPLETED, JobState.FAILED, JobState.ROLLED_BACK, JobState.CANCELLED):
            return {"success": False, "error": f"Job already finished: {job.state.value}"}

        task = self._running_jobs.get(job_id)
        if task:
            task.cancel()

        job.state = JobState.CANCELLED
        job.error = "Job cancelled"
        job.completed_at = datetime.utcnow()
        self._append_log(job_id, "info", job.error)

        return {"success": True, "message": f"Job {job_id} cancelled"}

    async def list_jobs(
        self,
        state: Optional[JobState] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List jobs, optionally filtered by state."""
        jobs = list(self._jobs.values())
        if state:
            jobs = [job for job in jobs if job.state == state]

        jobs.sort(key=lambda job: job.created_at, reverse=True)
        return [job.to_dict() for job in jobs[:limit]]

    async def get_logs(self, job_id: str) -> List[Dict[str, Any]]:
        """Get logs for a job."""
        return self._job_logs.get(job_id, [])

    def _append_log(self, job_id: str, level: str, message: str) -> None:
        """Append log entry for a job."""
        logs = self._job_logs.setdefault(job_id, [])
        logs.append(
            {
                "level": level,
                "message": message,
                "created_at": datetime.utcnow().isoformat(),
            }
        )
        # Keep logs bounded in memory.
        if len(logs) > 500:
            del logs[:-500]
