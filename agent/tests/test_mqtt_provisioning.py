from pathlib import Path

import pytest

from mqtt.provisioning import MQTTProvisioner


def provisioner(tmp_path: Path) -> MQTTProvisioner:
    return MQTTProvisioner({
        "mqtt": {
            "provisioning_dir": str(tmp_path / "mqtt"),
            "secrets_dir": str(tmp_path / "secrets"),
            "mosquitto_conf": str(tmp_path / "mosquitto.conf"),
            "mosquitto_password_file": str(tmp_path / "passwd"),
            "mosquitto_acl_file": str(tmp_path / "acl"),
            "advertised_host": "raspberrypi.local",
            "port": 8883,
        }
    })


def test_per_device_acl_and_one_time_password(tmp_path, monkeypatch):
    manager = provisioner(tmp_path)
    manager.base_dir.mkdir(parents=True)
    manager.ca_cert.write_text("TEST CA", encoding="ascii")
    monkeypatch.setattr(manager, "ensure_broker", lambda: {"configured": True})
    captured = {}
    monkeypatch.setattr(manager, "_set_password", lambda username, password: captured.update({username: password}))
    monkeypatch.setattr(manager, "_reload", lambda: None)

    result = manager.provision("kitchen-esp", "Kitchen")

    assert result["username"] == "device_kitchen-esp"
    assert result["password"] == captured["device_kitchen-esp"]
    acl = manager.acl_file.read_text(encoding="utf-8")
    assert "topic read pi-control/v1/devices/kitchen-esp/command" in acl
    assert "topic write pi-control/v1/devices/kitchen-esp/telemetry" in acl
    registry = manager.registry_file.read_text(encoding="utf-8")
    assert result["password"] not in registry


def test_duplicate_device_requires_rotation(tmp_path, monkeypatch):
    manager = provisioner(tmp_path)
    manager.base_dir.mkdir(parents=True)
    manager.ca_cert.write_text("TEST CA", encoding="ascii")
    monkeypatch.setattr(manager, "ensure_broker", lambda: {"configured": True})
    monkeypatch.setattr(manager, "_set_password", lambda *_: None)
    monkeypatch.setattr(manager, "_reload", lambda: None)
    manager.provision("device1")
    with pytest.raises(ValueError, match="already provisioned"):
        manager.provision("device1")


@pytest.mark.parametrize("device_id", ["../bad", "with space", "", "x" * 65])
def test_invalid_device_ids_are_rejected(tmp_path, device_id):
    with pytest.raises(ValueError):
        provisioner(tmp_path)._validate_id(device_id)
