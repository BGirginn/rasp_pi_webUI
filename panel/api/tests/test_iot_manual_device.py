import os

import pytest
from fastapi.testclient import TestClient

# Ensure test environment before importing app
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing")
os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("TELEMETRY_DB_PATH", ":memory:")
os.environ.setdefault("API_DEBUG", "true")


@pytest.fixture
def admin_client():
    from main import app
    from routers.auth import get_current_user

    async def _admin_user():
        return {"id": 1, "username": "testadmin", "role": "admin", "has_totp": False}

    app.dependency_overrides[get_current_user] = _admin_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_manual_device_add_requires_auth():
    from main import app
    with TestClient(app) as client:
        resp = client.post("/api/iot/devices/manual", json={"ip": "192.168.0.104", "probe": False})
        assert resp.status_code in (401, 403)


def test_manual_device_add_success(admin_client):
    resp = admin_client.post("/api/iot/devices/manual", json={"ip": "192.168.0.104", "port": 80, "probe": False})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "device_id" in data
    assert "device" in data
