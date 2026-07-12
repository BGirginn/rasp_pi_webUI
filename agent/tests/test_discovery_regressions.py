import pytest


class TestUsbFunctionDiscovery:
    def test_wifi_adapter_uses_network_capabilities(self, tmp_path):
        from providers.devices_provider import DevicesProvider

        net = tmp_path / "1-1:1.0" / "net"
        net.mkdir(parents=True)
        (net / "wlan1").mkdir()

        capabilities, device_type, endpoints = DevicesProvider({})._get_usb_functions(tmp_path)
        assert device_type == "network"
        assert capabilities == ["network", "wifi"]
        assert endpoints["network"] == ["wlan1"]

    def test_storage_adapter_is_writable(self, tmp_path):
        from providers.devices_provider import DevicesProvider

        block = tmp_path / "1-1:1.0" / "host0" / "block"
        block.mkdir(parents=True)
        (block / "sda").mkdir()

        capabilities, device_type, endpoints = DevicesProvider({})._get_usb_functions(tmp_path)
        assert device_type == "storage"
        assert capabilities == ["storage", "read", "write"]
        assert endpoints["storage"] == ["sda"]


@pytest.mark.asyncio
async def test_telemetry_includes_capacity_limits():
    from telemetry.collector import TelemetryCollector

    metrics = await TelemetryCollector({"telemetry": {}})._collect_metrics()
    values = {item["metric"]: item["value"] for item in metrics}
    assert values["host.mem.total_mb"] > 0
    assert values["disk.root.total_gb"] > 0
