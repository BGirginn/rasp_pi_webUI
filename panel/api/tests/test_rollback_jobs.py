"""
Test Rollback Job Creation
Validates rollback_jobs helpers and payload planning.
"""

import json
import time

import aiosqlite
import pytest

from core.rollback.jobs import create_rollback_job
from core.rollback.network import determine_rollback_plan


@pytest.mark.asyncio
async def test_create_rollback_job():
    """Test rollback job creation."""
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
    await db.commit()

    now = int(time.time())
    job_id = await create_rollback_job(
        db=db,
        action_id="net.toggle_wifi",
        rollback_action_id="net.toggle_wifi",
        payload={"enabled": False},
        user_id="1",
        timeout_seconds=30
    )

    cursor = await db.execute("SELECT * FROM rollback_jobs WHERE id = ?", (job_id,))
    row = await cursor.fetchone()

    assert row is not None
    assert row[1] == "net.toggle_wifi"
    assert row[2] == "net.toggle_wifi"
    assert json.loads(row[3]) == {"enabled": False}
    assert row[4] == "1"
    assert row[5] >= now + 29
    assert row[7] == "pending"

    await db.close()


@pytest.mark.asyncio
async def test_determine_rollback_plan_wifi_toggle(monkeypatch):
    """WiFi rollback plan should invert actual state."""
    async def fake_interfaces():
        return [{"name": "wlan0", "type": "wifi", "state": "running"}]

    monkeypatch.setattr(
        "core.rollback.network.agent_rpc.get_network_interfaces",
        fake_interfaces,
    )

    plan = await determine_rollback_plan("net.toggle_wifi", {"enabled": True})
    assert plan == ("net.toggle_wifi", {"enabled": False})


@pytest.mark.asyncio
async def test_determine_rollback_plan_reset_safe():
    """net.reset_safe should map to emergency rollback action."""
    plan = await determine_rollback_plan("net.reset_safe", {"profile": "primary"})
    assert plan == ("emergency.rollback_last_network_change", {})
