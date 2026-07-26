from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from providers.base import ResourceClass, ResourceState
from providers.docker_provider import DockerException, DockerProvider, NotFound


def _provider() -> DockerProvider:
    return DockerProvider(
        {
            "classification": {
                "core": ["protected"],
                "system": ["infrastructure"],
            }
        }
    )


def _container(status: str = "running"):
    container = MagicMock()
    container.id = "1234567890abcdef"
    container.name = "web"
    container.status = status
    container.labels = {"pi-control.class": "app"}
    container.image.tags = ["example/web:latest"]
    container.attrs = {
        "Created": "2026-01-01T00:00:00Z",
        "Image": "sha256:abc",
        "RestartCount": 2,
        "State": {"StartedAt": "2026-01-01T00:01:00Z"},
        "NetworkSettings": {
            "Ports": {
                "8080/tcp": [{"HostPort": "8080"}],
                "9090/udp": None,
            }
        },
    }
    return container


@pytest.mark.asyncio
async def test_start_stop_and_unavailable_sdk(monkeypatch):
    provider = _provider()
    client = MagicMock()

    monkeypatch.setattr("providers.docker_provider.DOCKER_AVAILABLE", False)
    await provider.start()
    assert provider.is_healthy is False

    monkeypatch.setattr("providers.docker_provider.DOCKER_AVAILABLE", True)
    monkeypatch.setattr("providers.docker_provider.docker.from_env", lambda: client)
    await provider.start()
    assert provider.is_healthy is True
    client.ping.assert_called_once()

    await provider.stop()
    client.close.assert_called_once()
    assert provider._client is None


@pytest.mark.asyncio
async def test_start_marks_provider_unhealthy_on_docker_error(monkeypatch):
    provider = _provider()
    monkeypatch.setattr("providers.docker_provider.DOCKER_AVAILABLE", True)
    monkeypatch.setattr(
        "providers.docker_provider.docker.from_env",
        MagicMock(side_effect=DockerException("offline")),
    )

    await provider.start()

    assert provider.is_healthy is False


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("running", ResourceState.RUNNING),
        ("exited", ResourceState.STOPPED),
        ("paused", ResourceState.STOPPED),
        ("restarting", ResourceState.RESTARTING),
        ("dead", ResourceState.FAILED),
        ("unexpected", ResourceState.UNKNOWN),
    ],
)
def test_container_conversion(status, expected):
    resource = _provider()._container_to_resource(_container(status))

    assert resource.id == "1234567890ab"
    assert resource.state is expected
    assert resource.resource_class is ResourceClass.APP
    assert resource.image == "example/web:latest"
    assert resource.ports == [
        {"container": "8080/tcp", "host": "8080", "protocol": "tcp"}
    ]
    assert resource.metadata["restart_count"] == 2


@pytest.mark.asyncio
async def test_discover_updates_cache_and_handles_errors():
    provider = _provider()
    container = _container()
    provider._client = SimpleNamespace(
        containers=SimpleNamespace(list=MagicMock(return_value=[container]))
    )
    provider._is_healthy = True

    resources = await provider.discover()
    assert [resource.id for resource in resources] == ["1234567890ab"]
    assert provider._resources["1234567890ab"].name == "web"

    provider._client.containers.list.side_effect = DockerException("broken")
    assert await provider.discover() == []
    assert provider.is_healthy is False


@pytest.mark.asyncio
async def test_get_resource_not_found_and_success():
    provider = _provider()
    get = MagicMock(return_value=_container())
    provider._client = SimpleNamespace(containers=SimpleNamespace(get=get))

    assert (await provider.get_resource("web")).name == "web"

    get.side_effect = NotFound("missing")
    assert await provider.get_resource("missing") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["start", "stop", "restart", "pause", "unpause"])
async def test_container_actions(action):
    provider = _provider()
    container = _container()
    provider._client = SimpleNamespace(
        containers=SimpleNamespace(get=MagicMock(return_value=container))
    )

    result = await provider.execute_action("web", action, {"timeout": 3})

    assert result.success is True
    method = getattr(container, action)
    if action in {"stop", "restart"}:
        method.assert_called_once_with(timeout=3)
    else:
        method.assert_called_once_with()


@pytest.mark.asyncio
async def test_container_action_failures():
    provider = _provider()
    unavailable = await provider.execute_action("web", "start")
    assert unavailable.error == "NOT_AVAILABLE"

    get = MagicMock(return_value=_container())
    provider._client = SimpleNamespace(containers=SimpleNamespace(get=get))
    unknown = await provider.execute_action("web", "explode")
    assert unknown.error == "UNKNOWN_ACTION"

    get.side_effect = NotFound("missing")
    missing = await provider.execute_action("missing", "start")
    assert missing.error == "NOT_FOUND"

    get.side_effect = DockerException("broken")
    failed = await provider.execute_action("web", "start")
    assert failed.error == "DOCKER_ERROR"


@pytest.mark.asyncio
async def test_logs_decode_and_time_filters():
    provider = _provider()
    container = _container()
    container.logs.return_value = b"first\nsecond\n"
    provider._client = SimpleNamespace(
        containers=SimpleNamespace(get=MagicMock(return_value=container))
    )
    since = datetime(2026, 1, 1, tzinfo=timezone.utc)
    until = datetime(2026, 1, 2, tzinfo=timezone.utc)

    assert await provider.get_logs("web", tail=2, since=since, until=until) == [
        "first",
        "second",
    ]
    container.logs.assert_called_once_with(
        tail=2, timestamps=True, since=since, until=until
    )


@pytest.mark.asyncio
async def test_stats_calculation_and_invalid_payload():
    provider = _provider()
    container = _container()
    container.stats.return_value = {
        "precpu_stats": {
            "cpu_usage": {"total_usage": 100},
            "system_cpu_usage": 1000,
        },
        "cpu_stats": {
            "cpu_usage": {"total_usage": 300},
            "system_cpu_usage": 2000,
            "online_cpus": 2,
        },
        "memory_stats": {"usage": 64 * 1024 * 1024, "limit": 256 * 1024 * 1024},
        "networks": {
            "eth0": {"rx_bytes": 10, "tx_bytes": 20},
            "eth1": {"rx_bytes": 5, "tx_bytes": 7},
        },
    }
    provider._client = SimpleNamespace(
        containers=SimpleNamespace(get=MagicMock(return_value=container))
    )

    assert await provider.get_stats("web") == {
        "cpu_pct": 40.0,
        "memory_usage_mb": 64.0,
        "memory_limit_mb": 256.0,
        "memory_pct": 25.0,
        "network_rx_bytes": 15,
        "network_tx_bytes": 27,
    }

    container.stats.return_value = {}
    assert await provider.get_stats("web") is None
