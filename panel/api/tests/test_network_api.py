import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing")
os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("TELEMETRY_DB_PATH", ":memory:")
os.environ.setdefault("API_DEBUG", "true")


@pytest.fixture
def admin_client():
    from main import app
    from routers.auth import get_current_user

    async def admin_user():
        return {"id": 1, "username": "admin", "role": "admin", "has_totp": False}

    app.dependency_overrides[get_current_user] = admin_user
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_agent_action_failure_is_not_reported_as_success():
    from routers.network import _require_agent_success

    with pytest.raises(HTTPException) as exc_info:
        _require_agent_success(
            {"success": False, "message": "nmcli failed", "error": "exit 10"},
            "restart interface",
        )

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "nmcli failed"


def test_interface_disable_requires_rollback(admin_client):
    response = admin_client.post(
        "/api/network/interfaces/eth0/action",
        json={"action": "disable", "rollback_seconds": 0},
    )

    assert response.status_code == 400
    assert "rollback" in response.json()["detail"].lower()


def test_invalid_interface_name_is_rejected(admin_client):
    response = admin_client.post(
        "/api/network/interfaces/--help/action",
        json={"action": "enable"},
    )

    assert response.status_code == 400


def test_agent_failure_propagates_to_interface_action(admin_client):
    with patch(
        "routers.network.agent_client.call",
        new=AsyncMock(return_value={"success": False, "message": "device missing"}),
    ):
        response = admin_client.post(
            "/api/network/interfaces/missing0/action",
            json={"action": "enable"},
        )

    assert response.status_code == 502
    assert response.json()["detail"] == "device missing"
