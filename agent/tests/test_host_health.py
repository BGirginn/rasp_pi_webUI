"""Power readings, reachability, and durable telemetry regression checks."""

import asyncio
import subprocess
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from telemetry import host_health


@pytest.mark.asyncio
async def test_agent_persists_health_with_existing_metrics(monkeypatch, tmp_path):
    from types import SimpleNamespace

    import aiosqlite

    import telemetry.collector as collector_module
    from telemetry.collector import TelemetryCollector

    monkeypatch.setattr(collector_module.psutil, "net_io_counters", Mock(return_value={
        "lo": SimpleNamespace(bytes_recv=999, bytes_sent=999),
        "eth0": SimpleNamespace(bytes_recv=100, bytes_sent=30),
        "wlan0": SimpleNamespace(bytes_recv=200, bytes_sent=50),
    }))
    health = {
        "host.net.internet_connected": 0.0,
        "host.power.on": 1.0,
        "host.power.input_voltage_v": 4.97,
        "host.power.pmic.vdd_core.current_a": 0.53,
    }
    monkeypatch.setattr(
        host_health.host_health_collector, "collect", AsyncMock(return_value=health)
    )
    db_path = tmp_path / "telemetry.db"
    collector = TelemetryCollector({"telemetry": {"db_path": str(db_path)}})
    await collector._init_db()
    readings = await collector._collect_metrics()
    values = {reading["metric"]: reading["value"] for reading in readings}
    assert values["host.net.rx_bytes"] == 300
    assert values["host.net.tx_bytes"] == 80
    collector._batch = readings
    await collector._flush_batch()
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT metric, value FROM metrics_raw WHERE metric LIKE 'host.power.%' OR metric = 'host.net.internet_connected'"
        )
        assert dict(await cursor.fetchall()) == health


def test_pmic_units_and_rails_are_kept_separate():
    readings = host_health.parse_pmic_readings(
        " EXT5V_V volt(24)=4.96738000V\n"
        " VDD_CORE_A current(7)=0.53580000A\n"
        " VDD_CORE_V volt(15)=0.75106150V\n"
        " DDR_VDDQ_A current(4)=0.00000000A\n"
        " BATT_V volt(25)=nanV\n"
        " BAD_A volt(1)=3.0A\n"
        " BAD_V volt(1)=1.2.3V\n"
    )
    assert readings == {
        "host.power.input_voltage_v": 4.96738,
        "host.power.pmic.ext5v.voltage_v": 4.96738,
        "host.power.pmic.vdd_core.current_a": 0.5358,
        "host.power.pmic.vdd_core.voltage_v": 0.7510615,
        "host.power.pmic.ddr_vddq.current_a": 0.0,
    }
    assert "host.power.input_current_a" not in readings


@pytest.mark.parametrize(
    "failure", [FileNotFoundError(), subprocess.TimeoutExpired("vcgencmd", 3)]
)
def test_missing_sensor_does_not_create_zero_voltage(monkeypatch, failure):
    monkeypatch.setattr(host_health.subprocess, "run", Mock(side_effect=failure))
    assert host_health.read_pmic_metrics() == {"host.power.pmic.available": 0.0}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "responses, connected",
    [
        ([httpx.Response(204)], 1),
        ([httpx.ConnectError("offline"), httpx.Response(200, text="ip=1.2.3.4\n")], 1),
        ([httpx.Response(200, text="login"), httpx.Response(302)], 0),
        ([httpx.ConnectTimeout("offline"), httpx.ConnectError("offline")], 0),
    ],
)
async def test_reachability_failover_and_captive_portal(
    monkeypatch, responses, connected
):
    client = AsyncMock()
    client.get.side_effect = responses
    context = AsyncMock()
    context.__aenter__.return_value = client
    monkeypatch.setattr(host_health.httpx, "AsyncClient", Mock(return_value=context))
    result = await host_health.probe_internet()
    assert result["host.net.internet_connected"] == connected
    assert ("host.net.internet_latency_ms" in result) == bool(connected)


@pytest.mark.asyncio
async def test_concurrent_requests_share_probe_and_drop_old_readings(monkeypatch):
    probe = AsyncMock(
        side_effect=[
            {"host.net.internet_connected": 1.0},
            {"host.net.internet_connected": 0.0},
        ]
    )
    power = Mock(
        side_effect=[
            {"host.power.input_voltage_v": 5.1},
            {"host.power.pmic.available": 0.0},
        ]
    )
    monkeypatch.setattr(host_health, "probe_internet", probe)
    monkeypatch.setattr(host_health, "read_pmic_metrics", power)
    collector = host_health.HostHealthCollector()
    results = await asyncio.gather(collector.collect(), collector.collect())
    assert results[0] == results[1]
    assert results[0]["host.power.on"] == 1.0
    assert results[0]["host.boot.timestamp"] > 0
    assert probe.await_count == 1
    collector._expires_at = 0
    result = await collector.collect()
    assert "host.power.input_voltage_v" not in result
    assert result["host.net.internet_connected"] == 0.0
