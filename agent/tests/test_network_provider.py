import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from providers.base import ActionResult, ResourceState
from providers.network_provider import NetworkProvider


def _address(family, address, netmask=None):
    return SimpleNamespace(family=family, address=address, netmask=netmask)


@pytest.mark.asyncio
async def test_discovery_maps_interfaces_and_counters(monkeypatch):
    provider = NetworkProvider({})
    monkeypatch.setattr(
        "providers.network_provider.psutil.net_if_addrs",
        lambda: {
            "lo": [],
            "wlan0": [
                _address(socket.AF_INET, "192.168.1.2", "255.255.255.0"),
                _address(
                    __import__("psutil").AF_LINK,
                    "aa:bb:cc:dd:ee:ff",
                ),
            ],
        },
    )
    monkeypatch.setattr(
        "providers.network_provider.psutil.net_if_stats",
        lambda: {"wlan0": SimpleNamespace(isup=True, speed=433)},
    )
    monkeypatch.setattr(
        "providers.network_provider.psutil.net_io_counters",
        lambda pernic: {"wlan0": SimpleNamespace(bytes_recv=10, bytes_sent=20)},
    )
    provider._default_gateways = AsyncMock(return_value={"wlan0": "192.168.1.1"})

    resources = await provider.discover()

    assert len(resources) == 1
    assert resources[0].state is ResourceState.RUNNING
    assert resources[0].metadata == {
        "interface_type": "wifi",
        "status": "up",
        "mac": "aa:bb:cc:dd:ee:ff",
        "ip": "192.168.1.2",
        "subnet_mask": "255.255.255.0",
        "gateway": "192.168.1.1",
        "rx_bytes": 10,
        "tx_bytes": 20,
        "speed_mbps": 433,
    }


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("wlan0", "wifi"),
        ("tailscale0", "vpn"),
        ("docker0", "bridge"),
        ("veth123", "virtual"),
        ("eth0", "ethernet"),
    ],
)
def test_interface_classification(name, expected):
    assert NetworkProvider._interface_type(name) == expected


@pytest.mark.asyncio
async def test_wifi_status_parses_connection_and_ip():
    provider = NetworkProvider({})
    provider._run_nmcli = AsyncMock(
        side_effect=[
            (0, "enabled\n", ""),
            (0, "wlan0:wifi:connected:Lab WiFi\neth0:ethernet:connected:Wired\n", ""),
            (0, "IP4.ADDRESS[1]:192.168.1.5/24\n", ""),
            (0, "*:78:5180 MHz\n:50:2412 MHz\n", ""),
        ]
    )

    result = await provider.execute_action("wlan0", "status")

    assert result.success is True
    assert result.data == {
        "radio_enabled": True,
        "connected": True,
        "ssid": "Lab WiFi",
        "ip": "192.168.1.5",
        "ip_address": "192.168.1.5",
        "signal_quality": 78,
        "frequency": "5180 MHz",
    }


@pytest.mark.asyncio
async def test_wifi_connect_existing_new_and_missing_ssid():
    provider = NetworkProvider({})
    provider._run_nmcli = AsyncMock(
        side_effect=[
            (0, "Lab\n", ""),
            (0, "", ""),
            (0, "Other\n", ""),
            (0, "", ""),
        ]
    )

    assert (await provider._connect_wifi("", None)).error == "MISSING_SSID"
    assert (await provider._connect_wifi("Lab", None)).success is True
    assert (await provider._connect_wifi("New", "secret", hidden=True)).success is True
    assert provider._run_nmcli.await_args_list[-1].args[0] == [
        "device",
        "wifi",
        "connect",
        "New",
        "password",
        "secret",
        "hidden",
        "yes",
    ]


@pytest.mark.asyncio
async def test_wifi_disconnect_and_enable_failures():
    provider = NetworkProvider({})
    provider._run_nmcli = AsyncMock(return_value=(0, "eth0:ethernet:connected\n", ""))
    assert (await provider._disconnect_wifi()).message == "No active WiFi connection"

    provider._run_nmcli = AsyncMock(return_value=(1, "", "radio blocked"))
    assert (await provider._enable_wifi()).success is False
    assert (await provider._enable_interface("eth9")).success is False


@pytest.mark.asyncio
async def test_disable_interface_rolls_back_on_command_failure():
    provider = NetworkProvider({})
    provider._create_checkpoint = AsyncMock(
        return_value="/org/freedesktop/NetworkManager/Checkpoint/1"
    )
    provider._run_nmcli = AsyncMock(return_value=(1, "", "denied"))
    provider.rollback_checkpoint = AsyncMock(return_value=ActionResult(True, "rolled back"))

    result = await provider._disable_interface("eth9", 30)

    assert result.success is False
    provider.rollback_checkpoint.assert_awaited_once()


@pytest.mark.asyncio
async def test_checkpoint_rejects_invalid_identifier():
    provider = NetworkProvider({})
    result = await provider.confirm_checkpoint("not-a-checkpoint")
    assert result.error == "INVALID_CHECKPOINT"


@pytest.mark.asyncio
async def test_execute_action_routes_and_unknown(monkeypatch):
    provider = NetworkProvider({})
    provider._scan_wifi = AsyncMock(return_value=ActionResult(True, "scan"))
    provider._enable_wifi = AsyncMock(return_value=ActionResult(True, "enabled"))
    provider._disconnect_wifi = AsyncMock(
        return_value=ActionResult(True, "disconnected")
    )
    provider.confirm_checkpoint = AsyncMock(return_value=ActionResult(True, "confirmed"))

    assert (await provider.execute_action("wlan0", "scan")).success is True
    assert (await provider.execute_action("wlan0", "enable")).success is True
    assert (await provider.execute_action("wlan0", "disconnect")).success is True
    assert (
        await provider.execute_action(
            "wlan0", "checkpoint_confirm", {"checkpoint_id": "checkpoint"}
        )
    ).success is True
    assert (await provider.execute_action("wlan0", "unknown")).error == "NOT_IMPLEMENTED"
