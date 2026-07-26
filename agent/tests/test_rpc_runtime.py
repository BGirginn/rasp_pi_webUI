import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from event_monitor import EventMonitor
from rpc.socket_server import SocketClient, SocketServer


def load_agent_module():
    path = Path(__file__).parents[1] / "pi-agent.py"
    spec = importlib.util.spec_from_file_location("pi_agent_runtime", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


RPC_METHODS = {
    "discovery.snapshot",
    "discovery.refresh",
    "resource.action",
    "resource.logs",
    "resource.stats",
    "resource.dependencies",
    "telemetry.current",
    "telemetry.query",
    "job.run",
    "job.status",
    "job.list",
    "job.cancel",
    "job.logs",
    "backup.inspect",
    "backup.key.export",
    "backup.key.import",
    "mqtt.status",
    "mqtt.ensure",
    "mqtt.provision",
    "mqtt.rotate",
    "mqtt.revoke",
    "system.info",
    "system.health",
    "network.interfaces",
    "network.wifi.toggle",
    "network.wifi.scan",
    "network.wifi.status",
    "network.wifi.connect",
    "network.wifi.disconnect",
    "network.interface.enable",
    "network.interface.disable",
    "network.interface.restart",
    "network.checkpoint.confirm",
    "network.checkpoint.rollback",
    "network.bluetooth.status",
    "network.bluetooth.scan",
    "network.bluetooth.enable",
    "network.bluetooth.disable",
    "network.bluetooth.pair",
    "network.bluetooth.trust",
    "network.bluetooth.connect",
    "network.bluetooth.disconnect",
    "network.bluetooth.remove",
    "network.connectivity.check",
    "network.dns.get",
    "system.execute",
    "devices.list",
    "devices.command",
}


@pytest.fixture
def rpc_agent():
    module = load_agent_module()
    agent = module.PiAgent.__new__(module.PiAgent)

    def namespace(*names):
        return SimpleNamespace(**{name: AsyncMock(return_value={"handler": name}) for name in names})

    agent.provider_manager = namespace(
        "get_snapshot", "refresh", "execute_action", "get_logs", "get_stats",
        "get_service_dependencies", "get_network_interfaces", "toggle_wifi",
        "scan_wifi", "wifi_status", "wifi_connect", "wifi_disconnect",
        "toggle_interface", "restart_interface", "confirm_network_checkpoint",
        "rollback_network_checkpoint", "get_devices",
    )
    agent.telemetry_collector = namespace("get_current", "query")
    agent.job_runner = namespace("run_job", "get_status", "list_jobs", "cancel_job", "get_logs")
    agent.bluetooth_manager = namespace(
        "status", "scan", "pair", "trust", "connect", "disconnect", "remove", "power",
    )

    private_handlers = {
        "_inspect_backup", "_export_backup_key", "_import_backup_key", "_mqtt_status",
        "_mqtt_ensure", "_mqtt_provision", "_mqtt_rotate", "_mqtt_revoke",
        "_get_system_info", "_get_health", "_interface_enable", "_interface_disable",
        "_interface_restart", "_bluetooth_enable", "_bluetooth_disable",
        "_check_connectivity", "_get_dns_config", "_execute_command", "_send_device_command",
    }
    for name in private_handlers:
        setattr(agent, name, AsyncMock(return_value={"handler": name}))
    return agent


@pytest.mark.parametrize("method", sorted(RPC_METHODS))
async def test_every_rpc_method_dispatches_to_a_real_handler(rpc_agent, method):
    response = await rpc_agent._handle_rpc(method, {})
    assert "result" in response
    assert "error" not in response


async def test_unknown_rpc_method_is_rejected(rpc_agent):
    assert await rpc_agent._handle_rpc("unknown.method", {}) == {
        "error": "Unknown method: unknown.method"
    }


async def test_rpc_handler_errors_are_serialized(rpc_agent):
    rpc_agent.provider_manager.get_snapshot.side_effect = RuntimeError("discovery failed")
    assert await rpc_agent._handle_rpc("discovery.snapshot", {}) == {
        "error": "discovery failed"
    }


async def test_socket_server_round_trip_and_error(tmp_path):
    socket_path = tmp_path / "agent.sock"

    async def handler(method, params):
        if method == "explode":
            return {"error": "boom"}
        return {"result": {"method": method, "params": params}}

    server = SocketServer(str(socket_path), handler, permissions="0600")
    client = SocketClient(str(socket_path))
    await server.start()
    try:
        result = await client.call("echo", {"value": 42})
        assert result == {"method": "echo", "params": {"value": 42}}
        with pytest.raises(Exception, match="boom"):
            await client.call("explode")
    finally:
        await client.disconnect()
        await server.stop()

    assert not socket_path.exists()
    assert server.is_running is False


async def test_event_monitor_debounces_refreshes():
    refresh = AsyncMock()
    monitor = EventMonitor(refresh, debounce_seconds=0.01)

    monitor._signal_refresh()
    monitor._signal_refresh()
    monitor._signal_refresh()
    await asyncio.sleep(0.03)
    await monitor.stop()

    refresh.assert_awaited_once()
