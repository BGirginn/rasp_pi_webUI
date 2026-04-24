"""
Pi Control Panel - Devices Tests

Unit tests for device models and endpoint logic.
"""

import pytest
from unittest.mock import patch

import os
os.environ["JWT_SECRET"] = "test-secret-key-for-testing"
os.environ["DATABASE_PATH"] = ":memory:"
os.environ["TELEMETRY_DB_PATH"] = ":memory:"


class TestDeviceResponseModel:
    """Test DeviceResponse Pydantic model."""

    def test_minimal(self):
        from routers.devices import DeviceResponse
        d = DeviceResponse(id="usb-1234", name="Test USB", type="usb", state="connected")
        assert d.id == "usb-1234"
        assert d.vendor is None
        assert d.capabilities is None

    def test_full(self):
        from routers.devices import DeviceResponse
        d = DeviceResponse(
            id="esp-001", name="ESP32 Sensor", type="esp", state="online",
            vendor="Espressif", product="ESP32",
            capabilities=["temperature", "humidity"],
            telemetry={"temp": 25.5},
            last_seen="2025-01-01T00:00:00",
            metadata={"ip": "192.168.1.100"},
        )
        assert d.type == "esp"
        assert "temperature" in d.capabilities
        assert d.telemetry["temp"] == 25.5
        assert d.last_seen == "2025-01-01T00:00:00"

    def test_all_device_types(self):
        from routers.devices import DeviceResponse
        for dtype in ["usb", "serial", "gpio", "esp", "bluetooth"]:
            d = DeviceResponse(id=f"{dtype}-1", name=f"Test {dtype}", type=dtype, state="connected")
            assert d.type == dtype

    def test_all_states(self):
        from routers.devices import DeviceResponse
        for state in ["online", "offline", "connected", "disconnected"]:
            d = DeviceResponse(id="dev-1", name="Test", type="usb", state=state)
            assert d.state == state


class TestGPIOConfigModel:
    """Test GPIOConfig Pydantic model."""

    def test_output_pin(self):
        from routers.devices import GPIOConfig
        config = GPIOConfig(pin=17, mode="output", value=1)
        assert config.pin == 17
        assert config.mode == "output"
        assert config.value == 1
        assert config.pull is None

    def test_input_pin_with_pull(self):
        from routers.devices import GPIOConfig
        config = GPIOConfig(pin=27, mode="input", pull="up")
        assert config.pin == 27
        assert config.mode == "input"
        assert config.pull == "up"
        assert config.value is None

    def test_pull_down(self):
        from routers.devices import GPIOConfig
        config = GPIOConfig(pin=22, mode="input", pull="down")
        assert config.pull == "down"


class TestDeviceCommandModel:
    """Test DeviceCommand Pydantic model."""

    def test_with_payload(self):
        from routers.devices import DeviceCommand
        cmd = DeviceCommand(command="led_on", payload={"brightness": 100})
        assert cmd.command == "led_on"
        assert cmd.payload["brightness"] == 100

    def test_without_payload(self):
        from routers.devices import DeviceCommand
        cmd = DeviceCommand(command="reset")
        assert cmd.command == "reset"
        assert cmd.payload is None


class TestLocalDeviceDiscovery:
    """Test local device discovery parsing."""

    @pytest.mark.asyncio
    async def test_empty_output(self):
        """Test discovery returns empty list when host command returns nothing."""
        from routers.devices import _local_device_discovery
        with patch("services.host_exec.run_host_command_simple", return_value=""):
            result = await _local_device_discovery()
            assert result == []

    @pytest.mark.asyncio
    async def test_usb_parsing(self):
        """Test USB device parsing from lsusb output."""
        from routers.devices import _local_device_discovery
        fake_output = (
            "===USB===\n"
            "Bus 001 Device 003: ID 046d:c52b Logitech, Inc. Unifying Receiver\n"
            "Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub\n"
            "===BLK===\n"
            "===SER===\n"
            "===END===\n"
        )
        with patch("services.host_exec.run_host_command_simple", return_value=fake_output):
            result = await _local_device_discovery()
            # Should have 1 device (root hub is skipped)
            assert len(result) == 1
            assert "Logitech" in result[0].name

    @pytest.mark.asyncio
    async def test_serial_parsing(self):
        """Test serial port parsing."""
        from routers.devices import _local_device_discovery
        fake_output = (
            "===USB===\n"
            "===BLK===\n"
            "===SER===\n"
            "/dev/ttyUSB0\n"
            "/dev/ttyACM0\n"
            "===END===\n"
        )
        with patch("services.host_exec.run_host_command_simple", return_value=fake_output):
            result = await _local_device_discovery()
            serial_devs = [d for d in result if d.type == "serial"]
            assert len(serial_devs) == 2

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        """Test discovery handles exceptions gracefully."""
        from routers.devices import _local_device_discovery
        with patch("services.host_exec.run_host_command_simple", side_effect=Exception("SSH failed")):
            result = await _local_device_discovery()
            assert result == []


class TestMacOSUSBParsing:
    """Test macOS USB tree parsing."""

    def test_parse_usb_devices(self):
        from routers.devices import _parse_macos_usb
        devices = []
        node = {
            "_items": [
                {
                    "_name": "USB Mouse",
                    "manufacturer": "Logitech",
                    "vendor_id": "0x046d",
                    "product_id": "0xc077",
                },
                {
                    "_name": "USB Hub",
                    "manufacturer": "Generic",
                    "vendor_id": "0x0000",
                    "product_id": "0x0000",
                },
            ]
        }
        _parse_macos_usb(node, devices)
        # Hub should be skipped
        assert len(devices) == 1
        assert devices[0].name == "USB Mouse"

    def test_skip_apple_internal(self):
        from routers.devices import _parse_macos_usb
        devices = []
        node = {
            "_items": [
                {
                    "_name": "Internal Camera",
                    "manufacturer": "Apple Inc.",
                    "vendor_id": "0x05ac",
                    "product_id": "0x1234",
                },
            ]
        }
        _parse_macos_usb(node, devices, depth=0)
        assert len(devices) == 0


class TestGPIOLocalStatus:
    """Test local GPIO status reading."""

    @pytest.mark.asyncio
    async def test_raspi_gpio_not_found(self):
        """Test GPIO returns empty when raspi-gpio not found."""
        from routers.devices import _get_local_gpio_status
        with patch("services.host_exec.run_host_command_simple", return_value="command not found"):
            result = await _get_local_gpio_status()
            assert "pins" in result

    @pytest.mark.asyncio
    async def test_raspi_gpio_output(self):
        """Test GPIO parses raspi-gpio output."""
        from routers.devices import _get_local_gpio_status
        fake_output = (
            "GPIO 2: level=1 fsel=1 func=OUTPUT pull=UP\n"
            "GPIO 3: level=0 fsel=0 func=INPUT pull=DOWN\n"
            "GPIO 40: level=0 fsel=0 func=INPUT pull=NONE\n"
        )
        with patch("services.host_exec.run_host_command_simple", return_value=fake_output):
            result = await _get_local_gpio_status()
            pins = result["pins"]
            # GPIO 40 > 27 should be filtered out
            assert len(pins) == 2
            assert pins[0]["pin"] == 2
            assert pins[0]["mode"] == "output"
            assert pins[0]["pull"] == "up"
            assert pins[1]["pin"] == 3
            assert pins[1]["mode"] == "input"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
