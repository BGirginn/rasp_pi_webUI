import os

import pytest
import aiosqlite
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


def test_viewer_cannot_create_simulation():
    from main import app
    from routers.auth import get_current_user

    async def viewer_user():
        return {"id": 2, "username": "viewer", "role": "viewer", "has_totp": False}

    app.dependency_overrides[get_current_user] = viewer_user
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/iot/devices/virtual",
                json={"name": "unauthorized-device"},
            )
            assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_remove_device_deletes_persistent_device_and_history(tmp_path):
    from services.discovery import DeviceDiscoveryService

    db = await aiosqlite.connect(tmp_path / "iot.db")
    await db.executescript(
        """
        CREATE TABLE iot_devices (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, ip TEXT NOT NULL,
            port INTEGER NOT NULL, status TEXT, last_seen TEXT
        );
        CREATE TABLE iot_sensor_readings (
            id INTEGER PRIMARY KEY, device_id TEXT NOT NULL,
            sensor_type TEXT NOT NULL, value REAL NOT NULL,
            unit TEXT, timestamp INTEGER NOT NULL
        );
        """
    )
    service = DeviceDiscoveryService()
    service._db = db
    await service.add_device_manual(
        "test-device",
        "Test Device",
        "127.0.0.1",
        18080,
        [{"type": "temperature", "value": 22.5, "unit": "C"}],
    )

    assert await service.remove_device("test-device") is True
    device_count = await (await db.execute("SELECT COUNT(*) FROM iot_devices")).fetchone()
    reading_count = await (
        await db.execute("SELECT COUNT(*) FROM iot_sensor_readings")
    ).fetchone()

    assert device_count[0] == 0
    assert reading_count[0] == 0
    assert "test-device" not in service.devices
    await db.close()


@pytest.mark.asyncio
async def test_mdns_thread_callback_is_forwarded_to_api_loop():
    import asyncio
    from unittest.mock import AsyncMock, Mock

    from services.discovery import DeviceDiscoveryService
    from zeroconf import ServiceStateChange

    service = DeviceDiscoveryService()
    service._loop = asyncio.get_running_loop()
    service._add_or_update_device_async = AsyncMock()
    info = Mock()
    zeroconf = Mock()
    zeroconf.get_service_info.return_value = info

    service._on_service_state_change(
        zeroconf,
        "_iot-device._tcp.local.",
        "test._iot-device._tcp.local.",
        ServiceStateChange.Added,
    )
    await asyncio.sleep(0.01)

    service._add_or_update_device_async.assert_awaited_once_with(info)
