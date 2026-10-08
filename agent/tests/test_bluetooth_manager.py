import pytest


def test_bluetooth_address_validation():
    from bluetooth_manager import BluetoothManager

    assert BluetoothManager._validate_address("aa:bb:cc:dd:ee:ff") == "AA:BB:CC:DD:EE:FF"
    with pytest.raises(ValueError):
        BluetoothManager._validate_address("AA:BB; power off")


def test_bluetooth_device_parser():
    from bluetooth_manager import BluetoothManager

    devices = BluetoothManager._parse_devices("Device AA:BB:CC:DD:EE:FF Keyboard\n")
    assert devices == [{"address": "AA:BB:CC:DD:EE:FF", "name": "Keyboard"}]
