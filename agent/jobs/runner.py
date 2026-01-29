"""
Pi Agent - Job Runner

Executes scheduled and manual jobs with precheck, snapshot, verify, and rollback.
Full implementation in Sprint 5.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

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
    config: Dict = field(default_factory=dict)
    result: Optional[Dict] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict:
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


class JobRunner:
    """Manages job queue and execution."""
    
    def __init__(self, config: dict):
        self.config = config.get("jobs", {})
        self._max_concurrent = self.config.get("max_concurrent", 2)
        self._default_timeout = self.config.get("default_timeout", 600)
        
        self._jobs: Dict[str, Job] = {}
        self._running_jobs: Dict[str, asyncio.Task] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._workers: List[asyncio.Task] = []
        self._running = False
            self._job_logs: Dict[str, List[Dict]] = {}
    
    @property
    def is_healthy(self) -> bool:
        """Check if job runner is healthy."""
        return self._running and len(self._running_jobs) <= self._max_concurrent
    
    async def start(self) -> None:
        """Start job runner workers."""
        self._running = True
        
        # Start worker tasks
        for i in range(self._max_concurrent):
            worker = asyncio.create_task(self._worker_loop(i))
            self._workers.append(worker)
        
        logger.info("Job runner started", workers=self._max_concurrent)
    
    async def stop(self) -> None:
        """Stop job runner."""
        self._running = False
        
        # Cancel all workers
        for worker in self._workers:
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass
        
        self._workers.clear()
        
        # Cancel running jobs
        for job_id, task in self._running_jobs.items():
            task.cancel()
            if job_id in self._jobs:
                self._jobs[job_id].state = JobState.CANCELLED
        
        self._running_jobs.clear()
        logger.info("Job runner stopped")
    
    async def _worker_loop(self, worker_id: int) -> None:
        """Worker loop that processes jobs from queue."""
        while self._running:
            try:
                # Wait for job with timeout
                try:
                    job_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                job = self._jobs.get(job_id)
                if not job:
                    continue
                
                logger.info("Worker processing job", worker=worker_id, job_id=job_id, type=job.type)
                
                # Execute job
                await self._execute_job(job)
                
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
            # Get job handler
            handler = self._get_handler(job.type)
            if not handler:
                raise ValueError(f"Unknown job type: {job.type}")
            
            # 1. Precheck
            precheck_result = await self._run_with_timeout(
                handler.precheck(job),
                timeout=60,
                name="precheck"
            )
            if not precheck_result.get("passed", False):
                    self._append_log(job.id, "error", f"Precheck failed: {precheck_result.get('reason', 'Unknown')}")
                raise ValueError(f"Precheck failed: {precheck_result.get('reason', 'Unknown')}")
                self._append_log(job.id, "info", "Precheck passed")
            
            # 2. Snapshot (optional)
            snapshot = None
            if hasattr(handler, "snapshot"):
                snapshot = await self._run_with_timeout(
                    handler.snapshot(job),
                    timeout=300,
                    name="snapshot"
                )
            
            # 3. Execute
            result = await self._run_with_timeout(
                handler.execute(job),
                timeout=job.config.get("timeout", self._default_timeout),
                name="execute"
            )
            if isinstance(result, dict) and result.get("output"):
                self._append_log(job.id, "info", result.get("output"))
            
            # 4. Verify
            if hasattr(handler, "verify"):
                verify_result = await self._run_with_timeout(
                    handler.verify(job, result),
                    timeout=60,
                    name="verify"
                )
                if not verify_result.get("passed", True):
                    # Rollback if verify fails
                    if snapshot and hasattr(handler, "rollback"):
                        await handler.rollback(job, snapshot)
                        job.state = JobState.ROLLED_BACK
                        job.error = f"Verification failed: {verify_result.get('reason', 'Unknown')}"
                        return
            
            # Success
            job.state = JobState.COMPLETED
            job.result = result
                self._append_log(job.id, "info", "Job completed")
            
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
            if job.id in self._running_jobs:
                del self._running_jobs[job.id]
    
    async def _run_with_timeout(self, coro, timeout: int, name: str) -> Any:
        """Run coroutine with timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(f"Job {name} timed out", timeout=timeout)
            raise
    
    def _get_handler(self, job_type: str):
        """Get handler for job type. Stub - full implementation in Sprint 5."""
        # TODO: Implement job handlers
        # - backup: BackupJobHandler
        # - restore: RestoreJobHandler
        # - update: UpdateJobHandler
        # - cleanup: CleanupJobHandler
        return None
    
    async def run_job(
        self,
        job_type: str,
        name: str,
        config: Optional[Dict] = None
    ) -> Dict:
        """Queue a job for execution."""
        job_id = None
        if config and isinstance(config, dict):
            job_id = config.get("job_id")
        job_id = job_id or str(uuid.uuid4())[:8]
        
        job = Job(
            id=job_id,
            name=name,
            type=job_type,
            config=config or {}
        )
        
        self._jobs[job_id] = job
        await self._queue.put(job_id)
        
            self._append_log(job_id, "info", f"Job queued: {name} ({job_type})")
        logger.info("Job queued", job_id=job_id, type=job_type, name=name)
        
        return job.to_dict()
            """Get logs for a job."""
            return self._job_logs.get(job_id, [])

        def _append_log(self, job_id: str, level: str, message: str) -> None:
            """Append log entry for a job."""
            self._job_logs.setdefault(job_id, []).append({
                "level": level,
                "message": message,
                "created_at": datetime.utcnow().isoformat()
            })
    
    async def get_status(self, job_id: str) -> Optional[Dict]:
        """Get job status."""
        job = self._jobs.get(job_id)
        return job.to_dict() if job else None
    
    async def cancel_job(self, job_id: str) -> Dict:
        """Cancel a running or queued job."""
        job = self._jobs.get(job_id)
        if not job:
            return {"success": False, "error": "Job not found"}
        
        if job.state == JobState.RUNNING:
            task = self._running_jobs.get(job_id)
            if task:
                task.cancel()
        
        job.state = JobState.CANCELLED
        job.completed_at = datetime.utcnow()
        
        return {"success": True, "message": f"Job {job_id} cancelled"}
    
    async def list_jobs(
        self,
        state: Optional[JobState] = None,
        limit: int = 50
    ) -> List[Dict]:
        """List jobs, optionally filtered by state."""
        jobs = list(self._jobs.values())
        
        if state:
            jobs = [j for j in jobs if j.state == state]
        
        # Sort by created_at descending
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        
        return [j.to_dict() for j in jobs[:limit]]
