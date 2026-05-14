"""
Google Drive backup API boundary tests.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient


TEST_ROOT = Path(tempfile.mkdtemp(prefix="pi-control-gdrive-tests-"))
os.environ["JWT_SECRET"] = "test-secret-key-for-testing"
os.environ["DATABASE_PATH"] = ":memory:"
os.environ["TELEMETRY_DB_PATH"] = ":memory:"
os.environ["BACKUP_LOCAL_DIR"] = str(TEST_ROOT / "backups")
os.environ["BACKUP_GDRIVE_CLIENT_FILE"] = str(TEST_ROOT / "gdrive_oauth_client.json")
os.environ["BACKUP_GDRIVE_TOKEN_FILE"] = str(TEST_ROOT / "gdrive_token.json")
os.environ["BACKUP_ENCRYPTION_KEY_FILE"] = str(TEST_ROOT / "backup_encryption.key")
os.environ["BACKUP_DAILY_EXPORT_ENABLED"] = "false"
os.environ["API_DEBUG"] = "true"


@pytest.fixture
def app_with_admin():
    from main import app
    from routers.auth import get_current_user

    async def mock_admin():
        return {"id": 1, "username": "admin", "role": "admin", "has_totp": False}

    app.dependency_overrides[get_current_user] = mock_admin
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def app_with_viewer():
    from main import app
    from routers.auth import get_current_user

    async def mock_viewer():
        return {"id": 2, "username": "viewer", "role": "viewer", "has_totp": False}

    app.dependency_overrides[get_current_user] = mock_viewer
    yield app
    app.dependency_overrides.clear()


def test_gdrive_client_upload(monkeypatch, app_with_admin):
    from routers import backup

    monkeypatch.setattr(
        backup.backup_service,
        "upload_oauth_client",
        AsyncMock(return_value={"configured": True, "client_id": "abc...xyz"}),
    )

    with TestClient(app_with_admin) as client:
        response = client.post(
            "/api/backup/gdrive/client",
            files={"file": ("client.json", b'{"installed":{"client_id":"abc","client_secret":"xyz"}}', "application/json")},
        )

    assert response.status_code == 200
    assert response.json()["configured"] is True


def test_gdrive_auth_start_and_status(monkeypatch, app_with_admin):
    from routers import backup

    monkeypatch.setattr(
        backup.backup_service,
        "start_device_authorization",
        AsyncMock(return_value={"status": "pending", "user_code": "ABCD-EFGH", "verification_url": "https://www.google.com/device"}),
    )
    monkeypatch.setattr(
        backup.backup_service,
        "poll_device_authorization",
        AsyncMock(return_value={"status": "authenticated", "authenticated": True}),
    )

    with TestClient(app_with_admin) as client:
        start = client.post("/api/backup/gdrive/auth/start")
        status = client.get("/api/backup/gdrive/auth/status")

    assert start.status_code == 200
    assert start.json()["user_code"] == "ABCD-EFGH"
    assert status.status_code == 200
    assert status.json()["authenticated"] is True


def test_encrypted_backup_endpoint(monkeypatch, app_with_admin):
    from routers import backup

    monkeypatch.setattr(
        backup.backup_service,
        "run_encrypted_backup",
        AsyncMock(return_value={"status": "completed", "uploaded": True}),
    )

    with TestClient(app_with_admin) as client:
        response = client.post("/api/backup/encrypted")
        actions = client.get("/api/audit/actions")

    assert response.status_code == 200
    assert response.json()["uploaded"] is True
    backup.backup_service.run_encrypted_backup.assert_awaited_once_with(trigger="manual")
    assert actions.status_code == 200
    assert "backup.encrypted.create" in actions.json()["actions"]


def test_remote_delete_endpoint(monkeypatch, app_with_admin):
    from routers import backup

    monkeypatch.setattr(
        backup.backup_service,
        "delete_drive_backup",
        Mock(return_value={"deleted": True, "id": "file-1"}),
    )

    with TestClient(app_with_admin) as client:
        response = client.delete("/api/backup/gdrive/files/file-1")
        actions = client.get("/api/audit/actions")

    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert actions.status_code == 200
    assert "backup.gdrive.remote_delete" in actions.json()["actions"]


def test_gdrive_mutations_require_admin(app_with_viewer):
    with TestClient(app_with_viewer) as client:
        assert client.post("/api/backup/encrypted").status_code == 403
        assert client.post("/api/backup/gdrive/auth/start").status_code == 403
        assert client.delete("/api/backup/gdrive/files/file-1").status_code == 403
