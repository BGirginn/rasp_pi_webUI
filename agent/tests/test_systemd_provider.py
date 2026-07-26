from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from providers.base import ResourceState
from providers.systemd_provider import SystemdProvider


def _result(stdout: str = "", returncode: int = 0, stderr: str = "") -> dict:
    return {"returncode": returncode, "stdout": stdout, "stderr": stderr}


@pytest.mark.asyncio
async def test_start_health_and_discovery_parsing():
    provider = SystemdProvider({})
    provider._run_command = AsyncMock(return_value=_result("systemd 259"))
    await provider.start()
    assert provider.is_healthy is True

    provider._run_command = AsyncMock(
        return_value=_result(
            "ssh.service loaded active running OpenSSH\n"
            "bad malformed\n"
            "failed.service loaded failed failed Broken\n"
        )
    )
    resources = await provider.discover()
    assert [(item.id, item.state) for item in resources] == [
        ("ssh.service", ResourceState.RUNNING),
        ("failed.service", ResourceState.FAILED),
    ]


@pytest.mark.asyncio
async def test_start_and_discover_fail_closed():
    provider = SystemdProvider({})
    provider._run_command = AsyncMock(return_value=_result(returncode=1))
    await provider.start()
    assert provider.is_healthy is False
    assert await provider.discover() == []


@pytest.mark.asyncio
async def test_get_resource_properties_and_missing():
    provider = SystemdProvider({})
    provider._run_command = AsyncMock(
        return_value=_result(
            "LoadState=loaded\nActiveState=active\nSubState=exited\n"
            "UnitFileState=enabled\nDescription=One shot\n"
        )
    )
    resource = await provider.get_resource("task.service")
    assert resource.state is ResourceState.RUNNING
    assert resource.metadata["unit_file_state"] == "enabled"
    assert resource.metadata["description"] == "One shot"

    provider._run_command.return_value = _result(returncode=1)
    assert await provider.get_resource("missing.service") is None


@pytest.mark.asyncio
async def test_actions_success_unknown_and_systemctl_failure():
    provider = SystemdProvider({})
    provider.get_resource = AsyncMock(
        return_value=provider._parse_service(
            "app.service", "loaded", "active", "running"
        )
    )
    provider._run_command = AsyncMock(return_value=_result())

    assert (await provider.execute_action("app.service", "restart")).success is True
    assert (await provider.execute_action("app.service", "explode")).error == "UNKNOWN_ACTION"

    provider._run_command.return_value = _result(returncode=1, stderr="denied")
    assert (
        await provider.execute_action("app.service", "stop")
    ).error == "SYSTEMCTL_ERROR"

    provider.get_resource.return_value = None
    assert (await provider.execute_action("missing.service", "start")).error == "NOT_FOUND"


@pytest.mark.asyncio
async def test_logs_stats_and_dependency_graph():
    provider = SystemdProvider({})
    provider._run_command = AsyncMock(
        side_effect=[
            _result("line one\nline two\n"),
            _result("MainPID=123\nMemoryCurrent=10485760\nCPUUsageNSec=2500000000\n"),
            _result(
                "Id=app.service\nRequires=network.target\n"
                "After=network.target sysinit.target ignored.txt\n"
                "Wants=timer.timer\n"
            ),
        ]
    )
    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    until = datetime(2026, 1, 2, tzinfo=timezone.utc)

    assert await provider.get_logs(
        "app.service", tail=2, since=since, until=until
    ) == ["line one", "line two"]
    assert await provider.get_stats("app.service") == {
        "main_pid": 123,
        "memory_mb": 10.0,
        "cpu_time_seconds": 2.5,
    }
    graph = await provider.get_dependency_graph("app.service")
    assert graph["root"] == "app.service"
    assert "ignored.txt" not in graph["nodes"]
    assert len(graph["edges"]) == 4


@pytest.mark.asyncio
async def test_logs_stats_and_dependencies_report_command_failure():
    provider = SystemdProvider({})
    provider._run_command = AsyncMock(
        return_value=_result(returncode=1, stderr="missing")
    )
    assert await provider.get_logs("missing.service") == []
    assert await provider.get_stats("missing.service") is None
    with pytest.raises(RuntimeError, match="missing"):
        await provider.get_dependency_graph("missing.service")
