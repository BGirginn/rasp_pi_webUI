from unittest.mock import AsyncMock, MagicMock

import pytest

from providers.base import ActionResult, Resource, ResourceClass, ResourceState
from providers.manager import ProviderManager


def _resource(
    resource_id: str = "svc.service",
    provider: str = "systemd",
    resource_class: ResourceClass = ResourceClass.SYSTEM,
    metadata: dict | None = None,
) -> Resource:
    return Resource(
        id=resource_id,
        name=resource_id,
        type="service",
        provider=provider,
        resource_class=resource_class,
        state=ResourceState.RUNNING,
        metadata=metadata or {},
    )


def _provider(resources=None):
    provider = MagicMock()
    provider.is_healthy = True
    provider.start = AsyncMock()
    provider.stop = AsyncMock()
    provider.discover = AsyncMock(return_value=resources or [])
    provider.get_resource = AsyncMock()
    provider.execute_action = AsyncMock(
        return_value=ActionResult(success=True, message="ok", data={})
    )
    provider.get_logs = AsyncMock(return_value=["line"])
    provider.get_stats = AsyncMock(return_value={"cpu": 1})
    provider.get_allowed_actions = MagicMock(
        return_value=["start", "stop", "restart", "mount", "command"]
    )
    return provider


@pytest.mark.asyncio
async def test_start_discover_snapshot_and_stop(monkeypatch):
    resource = _resource()
    provider = _provider([resource])
    manager = ProviderManager({"discovery": {"providers": ["systemd", "unknown"]}})
    monkeypatch.setattr(
        manager,
        "_create_provider",
        lambda name: provider if name == "systemd" else None,
    )

    await manager.start()
    first = await manager.get_snapshot()
    second = await manager.get_snapshot()

    assert manager.is_healthy is True
    assert first["changed"] is True
    assert second["changed"] is False
    assert first["counts"]["by_provider"] == {"systemd": 1}
    assert first["counts"]["by_state"] == {"running": 1}
    assert first["counts"]["by_class"] == {"SYSTEM": 1}

    await manager.stop()
    provider.stop.assert_awaited_once()
    assert manager.is_healthy is False


@pytest.mark.asyncio
async def test_discovery_failure_does_not_hide_other_providers():
    good_resource = _resource()
    good = _provider([good_resource])
    bad = _provider()
    bad.discover.side_effect = RuntimeError("failed")
    manager = ProviderManager({})
    manager._providers = {"good": good, "bad": bad}

    assert await manager.discover() == [good_resource]


@pytest.mark.asyncio
async def test_execute_action_validates_resource_provider_and_permissions():
    manager = ProviderManager({})
    missing = await manager.execute_action("missing", "start")
    assert missing.error == "NOT_FOUND"

    resource = _resource()
    manager._resources[resource.id] = resource
    unavailable = await manager.execute_action(resource.id, "start")
    assert unavailable.error == "PROVIDER_UNAVAILABLE"

    provider = _provider()
    provider.get_allowed_actions.return_value = ["restart"]
    manager._providers["systemd"] = provider
    denied = await manager.execute_action(resource.id, "stop")
    assert denied.error == "ACTION_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_execute_action_resolves_uncached_systemd_and_refreshes_state():
    old = _resource()
    refreshed = _resource()
    refreshed.state = ResourceState.STOPPED
    provider = _provider()
    provider.get_resource = AsyncMock(side_effect=[old, refreshed])
    manager = ProviderManager({})
    manager._providers["systemd"] = provider

    result = await manager.execute_action(old.id, "restart")

    assert result.success is True
    assert manager._resources[old.id].state is ResourceState.STOPPED


@pytest.mark.asyncio
async def test_logs_stats_and_dependencies_delegate_to_owner():
    resource = _resource()
    provider = _provider()
    provider.get_dependency_graph = AsyncMock(return_value={"nodes": []})
    manager = ProviderManager({})
    manager._resources[resource.id] = resource
    manager._providers["systemd"] = provider

    assert await manager.get_logs(resource.id) == ["line"]
    assert await manager.get_stats(resource.id) == {"cpu": 1}
    assert await manager.get_service_dependencies(resource.id) == {"nodes": []}
    assert await manager.get_logs("missing") == []
    assert await manager.get_stats("missing") is None


@pytest.mark.asyncio
async def test_network_operations_and_cached_interface_mapping():
    metadata = {
        "interface_type": "wifi",
        "status": "connected",
        "mac": "aa:bb",
        "ip": "100.64.0.1",
        "rx_bytes": 10,
        "tx_bytes": 20,
    }
    interface = _resource("wlan0", "network", metadata=metadata)
    provider = _provider([interface])
    provider.execute_action.side_effect = [
        ActionResult(True, "ok"),
        ActionResult(True, "ok"),
        ActionResult(True, "ok"),
        ActionResult(True, "ok"),
        ActionResult(True, "ok", data={"connected": True}),
        ActionResult(True, "ok"),
        ActionResult(True, "ok"),
        ActionResult(True, "ok", data={"networks": [{"ssid": "lab"}]}),
    ]
    manager = ProviderManager({})
    manager._providers["network"] = provider
    manager._resources[interface.id] = interface

    assert (await manager.toggle_interface("wlan0", False, 30))["success"] is True
    assert (await manager.restart_interface("wlan0"))["success"] is True
    assert (await manager.confirm_network_checkpoint("c1"))["success"] is True
    assert (await manager.rollback_network_checkpoint("c1"))["success"] is True
    assert await manager.wifi_status() == {"connected": True}
    assert (await manager.wifi_connect("lab", "secret"))["success"] is True
    assert (await manager.wifi_disconnect())["success"] is True
    assert await manager.scan_wifi() == [{"ssid": "lab"}]
    assert (await manager.get_network_interfaces())[0]["type"] == "wifi"
    provider.discover.assert_not_awaited()


@pytest.mark.asyncio
async def test_device_cache_and_action_invalidation():
    storage = _resource(
        "usb-sda1",
        "devices",
        ResourceClass.DEVICE,
        {"is_storage": True, "storage": {"writable": True}},
    )
    provider = _provider([storage])
    provider._invalidate_discovery_cache = MagicMock()
    manager = ProviderManager({"discovery": {"devices_cache_ttl": 60}})
    manager._providers["devices"] = provider

    first = await manager.get_devices()
    second = await manager.get_devices()

    assert first == second
    assert first[0]["storage"]["writable"] is True
    assert first[0]["allowed_actions"] == ["mount", "unmount", "eject"]
    provider.discover.assert_awaited_once()

    manager._resources[storage.id] = storage
    result = await manager.execute_action(storage.id, "mount")
    assert result.success is True
    assert manager._devices_snapshot_ready is False
    provider._invalidate_discovery_cache.assert_called_once()


def test_provider_factory_and_unavailable_fallbacks():
    manager = ProviderManager({})

    assert manager._create_provider("systemd").name == "systemd"
    assert manager._create_provider("network").name == "network"
    assert manager._create_provider("devices").name == "devices"
    assert manager._create_provider("unknown") is None
