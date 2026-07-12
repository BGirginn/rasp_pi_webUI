"""
Archive and backup integration tests.
"""

import os
import sqlite3
import tempfile
import time
import base64
import tarfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


TEST_ROOT = Path(tempfile.mkdtemp(prefix="pi-control-archive-tests-"))
CONTROL_DB = TEST_ROOT / "control.db"
TELEMETRY_DB = TEST_ROOT / "telemetry.db"
BACKUP_DIR = TEST_ROOT / "backups"
CREDENTIALS_DIR = TEST_ROOT / "credentials"

os.environ["JWT_SECRET"] = "test-secret-key-for-testing"
os.environ["DATABASE_PATH"] = str(CONTROL_DB)
os.environ["TELEMETRY_DB_PATH"] = str(TELEMETRY_DB)
os.environ["BACKUP_LOCAL_DIR"] = str(BACKUP_DIR)
os.environ["BACKUP_CREDENTIALS_DIR"] = str(CREDENTIALS_DIR)
os.environ["BACKUP_GDRIVE_CLIENT_FILE"] = str(CREDENTIALS_DIR / "gdrive_oauth_client.json")
os.environ["BACKUP_GDRIVE_TOKEN_FILE"] = str(CREDENTIALS_DIR / "gdrive_token.json")
os.environ["BACKUP_ENCRYPTION_KEY_FILE"] = str(CREDENTIALS_DIR / "backup_encryption.key")
os.environ["BACKUP_DAILY_EXPORT_ENABLED"] = "false"
os.environ["API_DEBUG"] = "true"


def _reset_databases():
    for db_path in (CONTROL_DB, TELEMETRY_DB):
        if db_path.exists():
            db_path.unlink()

    if BACKUP_DIR.exists():
        for path in BACKUP_DIR.iterdir():
            path.unlink()


def _insert_telemetry_rows():
    now = int(time.time())
    old_ts = now - (120 * 24 * 3600)

    conn = sqlite3.connect(TELEMETRY_DB)
    conn.execute(
        "INSERT INTO metrics_raw (ts, metric, labels_json, value) VALUES (?, ?, ?, ?)",
        (now, "host.cpu.pct_total", None, 42.5),
    )
    conn.execute(
        "INSERT INTO metrics_raw (ts, metric, labels_json, value) VALUES (?, ?, ?, ?)",
        (old_ts, "host.mem.pct", None, 61.0),
    )
    conn.execute(
        "INSERT INTO iot_devices (id, name, ip, port, status) VALUES (?, ?, ?, ?, ?)",
        ("sensor-1", "Sensor 1", "192.168.1.20", 80, "online"),
    )
    conn.execute(
        "INSERT INTO iot_sensor_readings (device_id, sensor_type, value, unit, timestamp) VALUES (?, ?, ?, ?, ?)",
        ("sensor-1", "temperature", 24.1, "C", now),
    )
    conn.execute(
        "INSERT INTO iot_sensor_readings (device_id, sensor_type, value, unit, timestamp) VALUES (?, ?, ?, ?, ?)",
        ("sensor-1", "temperature", 20.5, "C", old_ts),
    )
    conn.commit()
    conn.close()
    return old_ts


@pytest.fixture
def admin_client():
    _reset_databases()

    from main import app
    from config import settings
    from routers.auth import get_current_user
    from services.gdrive_backup import backup_service

    os.environ["DATABASE_PATH"] = str(CONTROL_DB)
    os.environ["TELEMETRY_DB_PATH"] = str(TELEMETRY_DB)
    os.environ["BACKUP_LOCAL_DIR"] = str(BACKUP_DIR)
    os.environ["BACKUP_CREDENTIALS_DIR"] = str(CREDENTIALS_DIR)
    os.environ["BACKUP_GDRIVE_CLIENT_FILE"] = str(CREDENTIALS_DIR / "gdrive_oauth_client.json")
    os.environ["BACKUP_GDRIVE_TOKEN_FILE"] = str(CREDENTIALS_DIR / "gdrive_token.json")
    os.environ["BACKUP_ENCRYPTION_KEY_FILE"] = str(CREDENTIALS_DIR / "backup_encryption.key")
    os.environ["BACKUP_DAILY_EXPORT_ENABLED"] = "false"

    settings.database_path = str(CONTROL_DB)
    settings.telemetry_db_path = str(TELEMETRY_DB)
    settings.backup_local_dir = str(BACKUP_DIR)
    settings.backup_retention_days = 90
    settings.backup_encryption_key_file = str(CREDENTIALS_DIR / "backup_encryption.key")
    settings.backup_gdrive_client_file = str(CREDENTIALS_DIR / "gdrive_oauth_client.json")
    settings.backup_gdrive_token_file = str(CREDENTIALS_DIR / "gdrive_token.json")

    backup_service.backup_dir = BACKUP_DIR
    backup_service.credentials_file = CREDENTIALS_DIR / "gdrive_credentials.json"
    backup_service.token_file = CREDENTIALS_DIR / "gdrive_token.json"
    backup_service.encryption_key_file = CREDENTIALS_DIR / "backup_encryption.key"
    backup_service.folder_id = None
    backup_service._running = False
    backup_service._task = None
    backup_service._initialized = False
    backup_service._folder_cache.clear()
    backup_service.last_backup = None
    backup_service.backup_history = []
    backup_service.last_daily_export_date = None

    async def _admin_user():
        return {"id": 1, "username": "testadmin", "role": "admin", "has_totp": False}

    app.dependency_overrides[get_current_user] = _admin_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_archive_endpoints_return_rows(admin_client):
    _insert_telemetry_rows()

    telemetry_resp = admin_client.get("/api/archive/telemetry")
    iot_resp = admin_client.get("/api/archive/iot")
    stats_resp = admin_client.get("/api/archive/stats")

    assert telemetry_resp.status_code == 200
    assert iot_resp.status_code == 200
    assert stats_resp.status_code == 200

    telemetry_data = telemetry_resp.json()
    iot_data = iot_resp.json()
    stats_data = stats_resp.json()

    assert telemetry_data["total"] >= 2
    assert telemetry_data["data"][0]["metric"]
    assert iot_data["total"] >= 2
    assert iot_data["data"][0]["device_id"] == "sensor-1"
    assert stats_data["telemetry"]["total_records"] >= 2
    assert stats_data["iot_sensors"]["total_records"] >= 2


def test_retention_cleanup_archives_and_deletes_old_rows(admin_client):
    old_ts = _insert_telemetry_rows()

    cleanup_resp = admin_client.post("/api/telemetry/retention/cleanup")
    assert cleanup_resp.status_code == 200

    payload = cleanup_resp.json()
    assert payload["raw_deleted"] >= 1
    assert payload["iot_deleted"] >= 1
    assert payload["retention_status"] == "completed"

    conn = sqlite3.connect(TELEMETRY_DB)
    raw_old_count = conn.execute("SELECT COUNT(*) FROM metrics_raw WHERE ts = ?", (old_ts,)).fetchone()[0]
    iot_old_count = conn.execute(
        "SELECT COUNT(*) FROM iot_sensor_readings WHERE timestamp = ?",
        (old_ts,),
    ).fetchone()[0]
    raw_recent_count = conn.execute("SELECT COUNT(*) FROM metrics_raw").fetchone()[0]
    iot_recent_count = conn.execute("SELECT COUNT(*) FROM iot_sensor_readings").fetchone()[0]
    conn.close()

    assert raw_old_count == 0
    assert iot_old_count == 0
    assert raw_recent_count >= 1
    assert iot_recent_count >= 1

    archived_files = {path.name for path in BACKUP_DIR.iterdir() if path.is_file()}
    old_day = time.strftime("%Y-%m-%d", time.localtime(old_ts))
    assert f"archive_{old_day}_telemetry.json" in archived_files
    assert f"archive_{old_day}_iot.json" in archived_files


def test_encrypted_backup_contains_db_snapshots_and_manifest(admin_client):
    _insert_telemetry_rows()

    response = admin_client.post("/api/backup/encrypted")
    assert response.status_code == 200

    payload = response.json()
    assert payload["status"] == "completed_local_only"
    encrypted_path = Path(payload["path"])
    assert encrypted_path.exists()
    assert encrypted_path.name.startswith("pi-control_backup_")
    assert encrypted_path.name.endswith(".tar.gz.enc")

    key = base64.urlsafe_b64decode((CREDENTIALS_DIR / "backup_encryption.key").read_text().strip().encode())
    encrypted = encrypted_path.read_bytes()
    assert encrypted.startswith(b"PCBACKUP1")
    plaintext = AESGCM(key).decrypt(encrypted[9:21], encrypted[21:], None)

    tar_path = TEST_ROOT / "decrypted.tar.gz"
    tar_path.write_bytes(plaintext)
    with tarfile.open(tar_path, "r:gz") as archive:
        names = set(archive.getnames())

    assert "pi-control-backup/manifest.json" in names
    assert "pi-control-backup/databases/control.db" in names
    assert "pi-control-backup/databases/telemetry.db" in names


def test_backup_file_retention_deletes_older_than_90_days(admin_client):
    from services.gdrive_backup import backup_service

    old_file = BACKUP_DIR / "pi-control_backup_2026-01-01_000000.tar.gz.enc"
    fresh_file = BACKUP_DIR / "pi-control_backup_2026-05-01_000000.tar.gz.enc"
    old_file.write_bytes(b"old")
    fresh_file.write_bytes(b"fresh")
    old_ts = time.time() - (91 * 24 * 3600)
    os.utime(old_file, (old_ts, old_ts))

    import asyncio
    result = asyncio.run(backup_service.enforce_backup_file_retention())

    assert result["status"] == "completed"
    assert old_file.name in result["local_deleted"]
    assert not old_file.exists()
    assert fresh_file.exists()
