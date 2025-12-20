"""
Test Rollback Job Creation (A4.1, A4.2)
Validates rollback_jobs table and automatic job creation after network actions.
"""

import pytest
import time
import json
from core.rollback.manager import create_rollback_job, determine_rollback_payload
import aiosqlite


@pytest.mark.asyncio
async def test_rollback_jobs_table_schema():
    """Verify rollback_jobs table exists with correct schema."""
    db = await aiosqlite.connect(":memory:")
    
    # Create table (from migration)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS rollback_jobs (
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
    """)
    await db.commit()
    
    # Verify schema
    cursor = await db.execute("PRAGMA table_info(rollback_jobs)")
    columns = await cursor.fetchall()
    column_names = [col[1] for col in columns]
    
    assert "id" in column_names
    assert "action_id" in column_names
    assert "rollback_action_id" in column_names
    assert "payload_json" in column_names
    assert "due_at" in column_names
    assert "status" in column_names
    
    await db.close()


@pytest.mark.asyncio
async def test_create_rollback_job():
    """Test rollback job creation (A4.2)."""
    db = await aiosqlite.connect(":memory:")
    
    # Create table
    await db.execute("""
        CREATE TABLE IF NOT EXISTS rollback_jobs (
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
    """)
    await db.commit()
    
    # Create job
    now = int(time.time())
    job_id = await create_rollback_job(
        db=db,
        action_id="net.toggle_wifi",
        rollback_action_id="net.toggle_wifi",
        payload={"enabled": False},
        user_id=1,
        timeout_seconds=30
    )
    
    # Verify job created
    cursor = await db.execute("SELECT * FROM rollback_jobs WHERE id = ?", (job_id,))
    row = await cursor.fetchone()
    
    assert row is not None
    assert row[1] == "net.toggle_wifi"  # action_id
    assert row[2] == "net.toggle_wifi"  # rollback_action_id
    assert json.loads(row[3]) == {"enabled": False}  # payload_json
    assert row[4] == 1  # created_by_user_id
    assert row[5] >= now + 29  # due_at
    assert row[7] == "pending"  # status
    
    await db.close()


def test_determine_rollback_payload_wifi_toggle():
    """Test rollback payload determination for WiFi toggle (A4.2.2)."""
    # If enabled=true, rollback=false
    payload = determine_rollback_payload("net.toggle_wifi", {"enabled": True})
    assert payload == {"enabled": False}
    
    # If enabled=false, rollback=true
    payload = determine_rollback_payload("net.toggle_wifi", {"enabled": False})
    assert payload == {"enabled": True}


def test_determine_rollback_payload_reset():
    """Test rollback payload determination for network reset."""
    payload = determine_rollback_payload("net.reset_safe", {"profile": "backup"})
    assert payload == {"profile": "primary"}


def test_determine_rollback_payload_non_network():
    """Non-network actions should not have rollback payload."""
    payload = determine_rollback_payload("svc.restart", {"service": "ssh"})
    assert payload is None
