import sqlite3

import pytest

from db.migrations import run_migrations


@pytest.mark.asyncio
async def test_fresh_migrations_are_secure_complete_and_idempotent(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "control.db"
    monkeypatch.setenv("DEFAULT_ADMIN_PASSWORD", "test-only-strong-password")

    await run_migrations(str(database_path))
    await run_migrations(str(database_path))

    database = sqlite3.connect(database_path)
    try:
        assert database.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert database.execute("SELECT COUNT(*) FROM migrations").fetchone()[0] == 7
        assert database.execute(
            "SELECT username, role FROM users ORDER BY username"
        ).fetchall() == [("admin", "admin")]

        tables = {
            row[0]
            for row in database.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert {
            "audit_log",
            "jobs",
            "job_schedules",
            "mqtt_devices",
            "notifications",
            "projects",
            "project_snapshots",
            "restore_points",
            "sessions",
            "users",
        } <= tables

        job_columns = {
            row[1] for row in database.execute("PRAGMA table_info(jobs)").fetchall()
        }
        assert {"phase", "cancellable", "checkpoint_json", "updated_at"} <= job_columns
    finally:
        database.close()


@pytest.mark.asyncio
async def test_initial_admin_migration_requires_explicit_password(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("DEFAULT_ADMIN_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="DEFAULT_ADMIN_PASSWORD is required"):
        await run_migrations(str(tmp_path / "control.db"))
