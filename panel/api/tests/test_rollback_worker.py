"""
Test Rollback Worker
Validates background rollback execution.
"""

import time

import aiosqlite
import pytest

from core.rollback.worker import process_due_jobs


@pytest.mark.asyncio
async def test_process_due_jobs(monkeypatch):
    db = await aiosqlite.connect(":memory:")

    await db.execute(
        """
        CREATE TABLE rollback_jobs (
            id TEXT PRIMARY KEY,
            action_id TEXT NOT NULL,
            rollback_action_id TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_by_user_id TEXT NOT NULL,
            due_at INTEGER NOT NULL,
            confirmed_at INTEGER,
            status TEXT NOT NULL CHECK (status IN ('pending','confirmed','rolled_back','expired')),
            created_at INTEGER NOT NULL
        )
        """
    )
    await db.execute(
        """
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            username TEXT,
            action TEXT NOT NULL,
            resource_id TEXT,
            details TEXT,
            created_at TEXT
        )
        """
    )
    await db.commit()

    job_id = "job-1"
    now = int(time.time())
    await db.execute(
        """
        INSERT INTO rollback_jobs (
            id, action_id, rollback_action_id, payload_json,
            created_by_user_id, due_at, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job_id,
            "net.reset_safe",
            "emergency.rollback_last_network_change",
            "{}",
            "1",
            now - 1,
            "pending",
            now,
        ),
    )
    await db.commit()

    async def fake_get_control_db():
        return db

    monkeypatch.setattr("core.rollback.worker.get_control_db", fake_get_control_db)

    await process_due_jobs()

    cursor = await db.execute("SELECT status FROM rollback_jobs WHERE id = ?", (job_id,))
    row = await cursor.fetchone()
    assert row[0] in {"rolled_back", "expired"}

    await db.close()
