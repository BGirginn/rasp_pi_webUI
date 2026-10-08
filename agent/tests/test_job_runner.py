import asyncio

import pytest

from jobs.runner import JobRunner, JobState


class SuccessfulHandler:
    async def precheck(self, job):
        return {"passed": True}

    async def snapshot(self, job):
        return {"marker": "before"}

    async def execute(self, job):
        return {"ok": True}

    async def verify(self, job, result):
        return {"passed": result["ok"]}

    async def rollback(self, job, snapshot):
        return {"restored": snapshot["marker"]}


@pytest.mark.asyncio
async def test_job_state_and_logs_survive_runner_restart(tmp_path):
    config = {"jobs": {"db_path": str(tmp_path / "jobs.db"), "max_concurrent": 1}}
    runner = JobRunner(config)
    runner.register_handler("healthcheck", SuccessfulHandler())
    await runner.start()
    created = await runner.run_job("healthcheck", "Health", {"job_id": "durable1"})
    assert created["state"] == "pending"

    for _ in range(50):
        status = await runner.get_status("durable1")
        if status["state"] == "completed":
            break
        await asyncio.sleep(0.01)

    assert status["state"] == "completed"
    assert status["phase"] == "completed"
    assert status["progress"] == 100
    assert (await runner.get_logs("durable1"))[-1]["message"] == "Job completed"
    await runner.stop()

    restarted = JobRunner(config)
    await restarted.start()
    restored = await restarted.get_status("durable1")
    assert restored["state"] == "completed"
    assert restored["checkpoint"] == {"marker": "before"}
    await restarted.stop()


@pytest.mark.asyncio
async def test_running_job_is_failed_after_unclean_restart(tmp_path):
    config = {"jobs": {"db_path": str(tmp_path / "jobs.db")}}
    runner = JobRunner(config)
    runner._open_db()
    await runner.run_job("healthcheck", "Interrupted", {"job_id": "interrupted1"})
    job = runner._jobs["interrupted1"]
    job.state = JobState.RUNNING
    runner._save_job(job)
    runner._db.close()
    runner._db = None

    restarted = JobRunner(config)
    await restarted.start()
    status = await restarted.get_status("interrupted1")
    assert status["state"] == "failed"
    assert status["phase"] == "interrupted"
    await restarted.stop()
