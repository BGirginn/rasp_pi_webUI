import pytest
from unittest.mock import AsyncMock


class TestUsbFunctionDiscovery:
    def test_wifi_adapter_uses_network_capabilities(self, tmp_path):
        from providers.devices_provider import DevicesProvider

        device = tmp_path / "1-1"
        net = device / "1-1:1.0" / "net"
        net.mkdir(parents=True)
        (net / "wlan1").mkdir()

        capabilities, device_type, endpoints = DevicesProvider({})._get_usb_functions(device)
        assert device_type == "network"
        assert capabilities == ["network", "wifi"]
        assert endpoints["network"] == ["wlan1"]

    def test_storage_adapter_is_writable(self, tmp_path):
        from providers.devices_provider import DevicesProvider

        device = tmp_path / "1-1"
        block = device / "1-1:1.0" / "host0" / "block"
        block.mkdir(parents=True)
        (block / "sda").mkdir()

        capabilities, device_type, endpoints = DevicesProvider({})._get_usb_functions(device)
        assert device_type == "storage"
        assert capabilities == ["storage", "read", "write"]
        assert endpoints["storage"] == ["sda"]

    def test_usb_controller_does_not_inherit_child_device_functions(self, tmp_path):
        from providers.devices_provider import DevicesProvider

        controller = tmp_path / "usb3"
        net = controller / "3-1" / "3-1:1.0" / "net"
        net.mkdir(parents=True)
        (net / "wlan1").mkdir()

        capabilities, device_type, endpoints = DevicesProvider({})._get_usb_functions(controller)

        assert capabilities == ["device"]
        assert device_type == "usb"
        assert endpoints == {}


def test_systemd_active_exited_is_running():
    from providers.base import ResourceState
    from providers.systemd_provider import SystemdProvider

    resource = SystemdProvider({})._parse_service(
        "oneshot.service", "loaded", "active", "exited"
    )

    assert resource.state == ResourceState.RUNNING
    assert resource.metadata["sub_state"] == "exited"


@pytest.mark.asyncio
async def test_systemd_core_action_is_protected_when_cache_is_empty():
    from providers.systemd_provider import SystemdProvider

    provider = SystemdProvider({"classification": {"core": ["critical.service"]}})
    provider._run_command = AsyncMock(
        return_value={
            "returncode": 0,
            "stdout": (
                "LoadState=loaded\nActiveState=active\nSubState=running\n"
                "UnitFileState=enabled\nDescription=Critical\n"
            ),
            "stderr": "",
        }
    )

    result = await provider.execute_action("critical.service", "stop")

    assert result.success is False
    assert result.error == "PROTECTED_RESOURCE"


def test_storage_discovery_reports_capacity_rw_and_partitions(monkeypatch):
    import json
    from types import SimpleNamespace

    import storage

    payload = {
        "blockdevices": [{
            "name": "sda", "kname": "sda", "path": "/dev/sda", "type": "disk",
            "size": 32000000000, "model": "Flash Drive", "vendor": "Test",
            "serial": "ABC123", "tran": "usb", "rm": True, "ro": False,
            "hotplug": True, "maj:min": "8:0",
            "children": [{
                "name": "sda1", "kname": "sda1", "path": "/dev/sda1",
                "type": "part", "size": 31900000000, "fstype": "exfat",
                "label": "DATA", "uuid": "uuid", "ro": False,
                "mountpoints": ["/media/data"], "fsavail": 20000000000,
                "fsused": 11900000000, "fsuse%": "37%",
            }],
        }]
    }
    monkeypatch.setattr(
        storage,
        "_run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout=json.dumps(payload), stderr=""
        ),
    )

    device = storage.discover_usb_storage()[0]

    assert device["size_bytes"] == 32000000000
    assert device["read_only"] is False
    assert device["mounted"] is True
    assert device["partitions"][0]["filesystem"] == "exfat"
    assert device["partitions"][0]["available_bytes"] == 20000000000


def test_storage_safety_rejects_non_removable_device(monkeypatch):
    import storage

    monkeypatch.setattr(
        storage,
        "discover_block_devices",
        lambda: [{
            "device_path": "/dev/sda", "fingerprint": "same",
            "transport": "usb", "removable": False, "read_only": False,
        }],
    )

    with pytest.raises(storage.StorageSafetyError, match="removable"):
        storage.get_safe_usb_device("/dev/sda", "same")


@pytest.mark.asyncio
async def test_telemetry_includes_capacity_limits():
    from telemetry.collector import TelemetryCollector

    metrics = await TelemetryCollector({"telemetry": {}})._collect_metrics()
    values = {item["metric"]: item["value"] for item in metrics}
    assert values["host.mem.total_mb"] > 0
    assert values["disk.root.total_gb"] > 0


@pytest.mark.asyncio
async def test_telemetry_database_is_shared_with_data_directory_group(tmp_path):
    from telemetry.collector import TelemetryCollector

    db_path = tmp_path / "telemetry.db"
    collector = TelemetryCollector(
        {"telemetry": {"db_path": str(db_path), "interval": 2}}
    )

    await collector._init_db()

    assert collector._interval == 30
    assert db_path.stat().st_gid == tmp_path.stat().st_gid
    assert db_path.stat().st_mode & 0o060 == 0o060


@pytest.mark.asyncio
async def test_network_disable_schedules_real_rollback():
    import asyncio
    from unittest.mock import AsyncMock

    from providers.network_provider import NetworkProvider

    provider = NetworkProvider({})
    restore = AsyncMock()
    provider._schedule_rollback("test0", 0.01, restore)

    await asyncio.sleep(0.03)

    restore.assert_awaited_once()
    assert "test0" not in provider._rollback_tasks


@pytest.mark.asyncio
async def test_network_restart_reports_reconnect_failure(monkeypatch):
    from unittest.mock import AsyncMock

    from providers.network_provider import NetworkProvider

    provider = NetworkProvider({})
    provider._run_nmcli = AsyncMock(
        side_effect=[(0, "", ""), (10, "", "reconnect failed")]
    )
    provider._create_checkpoint = AsyncMock(return_value="/org/freedesktop/NetworkManager/Checkpoint/1")
    provider.rollback_checkpoint = AsyncMock()
    monkeypatch.setattr("providers.network_provider.asyncio.sleep", AsyncMock())

    result = await provider.execute_action("eth9", "restart")

    assert result.success is False
    assert "reconnect failed" in result.message
