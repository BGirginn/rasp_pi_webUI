from unittest.mock import MagicMock, patch

import pytest

from mqtt.bridge import MQTTBridge


@pytest.mark.asyncio
async def test_mqtt_bridge_starts_and_stops_client_in_safe_order():
    client = MagicMock()
    events = []
    client.disconnect.side_effect = lambda: events.append("disconnect")
    client.loop_stop.side_effect = lambda: events.append("loop_stop")

    with patch("mqtt.bridge.mqtt.Client", return_value=client):
        bridge = MQTTBridge({"mqtt": {"host": "127.0.0.1", "port": 1883}})
        await bridge.start()
        await bridge.stop()

    client.connect_async.assert_called_once_with("127.0.0.1", 1883, keepalive=60)
    client.loop_start.assert_called_once()
    assert events == ["disconnect", "loop_stop"]


@pytest.mark.asyncio
async def test_mqtt_command_fails_cleanly_without_connection():
    bridge = MQTTBridge({"mqtt": {}})

    result = await bridge.send_command("device-1", "set_power", {"on": True})

    assert result == {"success": False, "error": "MQTT not connected"}
