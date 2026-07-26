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
