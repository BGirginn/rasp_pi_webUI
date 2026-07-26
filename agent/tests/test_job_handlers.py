import sqlite3
import tarfile
from pathlib import Path

import pytest

from jobs import handlers
from jobs.handlers import BackupBundle, CleanupJobHandler
from jobs.runner import Job


def create_db(path: Path, value: str) -> None:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE sample (value TEXT)")
    connection.execute("INSERT INTO sample VALUES (?)", (value,))
    connection.commit()
    connection.close()


def test_backup_bundle_round_trip_and_integrity(tmp_path, monkeypatch):
    control = tmp_path / "control.db"
    telemetry = tmp_path / "telemetry.db"
    create_db(control, "control")
    create_db(telemetry, "telemetry")
    monkeypatch.setattr(
        handlers,
        "DEFAULT_DATABASES",
        {"control_db": control, "telemetry_db": telemetry},
    )
    install = tmp_path / "install"
    install.mkdir()
    (install / "install.sh").write_text("#!/bin/sh\n", encoding="ascii")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "panel.env").write_text("SAFE=value\n", encoding="ascii")
    key_file = config_dir / "backup_encryption.key"
    config = {
        "jobs": {
            "backup_dir": str(tmp_path / "backups"),
            "backup_key_file": str(key_file),
            "install_dir": str(install),
            "config_dir": str(config_dir),
        }
    }

    bundle = BackupBundle(config)
    result = bundle.create(["control_db", "telemetry_db", "app_config", "release"])
    inspected = bundle.inspect(Path(result["path"]), tmp_path / "staging")

    assert inspected["valid"] is True
    assert set(inspected["components"]) == {
        "control_db",
        "telemetry_db",
        "app_config",
        "release",
    }
    assert not (tmp_path / "staging" / "pi-control-backup" / "config" / key_file.name).exists()


def test_safe_extract_rejects_parent_traversal(tmp_path):
    archive_path = tmp_path / "bad.tar"
    source = tmp_path / "source"
    source.write_text("bad", encoding="ascii")
    with tarfile.open(archive_path, "w") as archive:
        archive.add(source, arcname="../outside")
    with tarfile.open(archive_path) as archive:
        with pytest.raises(ValueError, match="Unsafe archive member"):
            handlers._safe_extract(archive, tmp_path / "target")


@pytest.mark.asyncio
async def test_cleanup_is_dry_run_by_default(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    candidate = backup_dir / "archive_old.json"
    candidate.write_text("old", encoding="ascii")
    candidate.touch()
    handler = CleanupJobHandler({"jobs": {"backup_dir": str(backup_dir)}})
    job = Job(id="cleanup1", name="Cleanup", type="cleanup", config={"retention_days": 1})
    result = await handler.execute(job)
    assert result["dry_run"] is True
    assert candidate.exists()


def test_usb_write_test_verifies_and_removes_temporary_file(tmp_path, monkeypatch):
    from jobs.handlers import UsbWriteTestJobHandler

    device = {
        "device_path": "/dev/sdz",
        "fingerprint": "fingerprint",
        "partitions": [{
            "id": "sdz1",
            "path": "/dev/sdz1",
            "mount_points": [str(tmp_path)],
            "read_only": False,
        }],
    }
    monkeypatch.setattr("jobs.handlers.get_safe_usb_device", lambda *_args: device)
    job = Job(
        id="usbtest",
        name="USB write",
        type="usb_write_test",
        config={
            "device_path": "/dev/sdz",
            "fingerprint": "fingerprint",
            "volume_id": "sdz1",
            "size_mb": 1,
        },
    )

    result = UsbWriteTestJobHandler()._write_test(job)

    assert result["bytes_tested"] == 1024 * 1024
    assert result["temporary_file_removed"] is True
    assert list(tmp_path.iterdir()) == []
