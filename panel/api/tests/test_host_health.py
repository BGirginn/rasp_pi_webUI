"""Agent health forwarding and periodic persistence checks."""

from unittest.mock import AsyncMock

import aiosqlite
import pytest


@pytest.mark.asyncio
async def test_current_agent_snapshot_includes_health_metrics(monkeypatch):
    from routers import telemetry

    monkeypatch.setattr(
        telemetry, "_current_metrics_cache", {"data": None, "expires_at": 0.0}
    )
    monkeypatch.setattr(
        telemetry.agent_client,
        "get_current_telemetry",
        AsyncMock(
            return_value={
                "metrics": {
                    "host.cpu.pct_total": 20,
                    "host.net.internet_connected": 0.0,
                    "host.power.input_voltage_v": 5.05,
                }
            }
        ),
    )
    result = await telemetry.get_current_metrics(user={})
    assert result["metrics"]["host.cpu.pct_total"] == 20
    assert result["metrics"]["host.net.internet_connected"] == 0
    assert result["metrics"]["host.power.input_voltage_v"] == 5.05


@pytest.mark.asyncio
async def test_periodic_collection_broadcasts_agent_health(monkeypatch, tmp_path):
    from services import telemetry_collector

    metrics = {
        "host.net.internet_connected": 0.0,
        "host.power.on": 1.0,
        "host.power.input_voltage_v": 4.97,
        "host.power.pmic.vdd_core.current_a": 0.53,
    }
    monkeypatch.setattr(
        telemetry_collector.agent_client,
        "get_current_telemetry",
        AsyncMock(return_value={"metrics": metrics}),
    )
    monkeypatch.setattr(telemetry_collector.sse_manager, "broadcast", AsyncMock())
    async with aiosqlite.connect(tmp_path / "telemetry.db") as db:
        await db.execute(
            "CREATE TABLE metrics_raw (ts INTEGER, metric TEXT, labels_json TEXT, value REAL)"
        )
        monkeypatch.setattr(
            telemetry_collector, "get_telemetry_db", AsyncMock(return_value=db)
        )
        collector = telemetry_collector.TelemetryCollector()
        await collector._collect_and_store_metrics()
        assert collector.get_last_metrics() == metrics
        assert (
            telemetry_collector.sse_manager.broadcast.await_args.args[2]["metrics"]
            == metrics
        )
