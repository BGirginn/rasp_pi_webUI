"""
Test Actions API
Integration tests for /api/actions endpoints.
"""

import os

import pytest
from httpx import AsyncClient, ASGITransport

os.environ["JWT_SECRET"] = "test-secret-key-for-testing"
os.environ["DATABASE_PATH"] = ":memory:"
os.environ["TELEMETRY_DB_PATH"] = ":memory:"
os.environ["API_DEBUG"] = "true"


@pytest.fixture
async def client():
    from main import app
    from config import settings
    from db import init_db, close_db

    settings.database_path = ":memory:"
    settings.telemetry_db_path = ":memory:"
    settings.jwt_secret = "test-secret-key-for-testing"

    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client, app
    app.dependency_overrides.clear()
    await close_db()


@pytest.mark.asyncio
async def test_list_actions_requires_auth(client):
    """GET /api/actions requires authentication."""
    http_client, _app = client
    response = await http_client.get("/api/actions")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_actions_filtered_by_role(client):
    """GET /api/actions filters by role."""
    http_client, app = client
    from api.deps import current_user

    app.dependency_overrides[current_user] = lambda: {
        "id": 1,
        "username": "viewer",
        "role": "viewer",
        "has_totp": False,
    }

    response = await http_client.get("/api/actions")
    assert response.status_code == 200
    action_ids = {action["id"] for action in response.json()}

    assert "obs.get_system_status" in action_ids
    assert "svc.start" not in action_ids


@pytest.mark.asyncio
async def test_execute_action_enforces_rbac(client):
    """POST /api/actions/execute enforces RBAC."""
    http_client, app = client
    from api.deps import current_user

    app.dependency_overrides[current_user] = lambda: {
        "id": 1,
        "username": "viewer",
        "role": "viewer",
        "has_totp": False,
    }

    response = await http_client.post(
        "/api/actions/execute",
        json={"action_id": "svc.start", "params": {"service": "ssh"}},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_execute_action_validates_params(client):
    """POST /api/actions/execute validates params against schema."""
    http_client, app = client
    from api.deps import current_user

    app.dependency_overrides[current_user] = lambda: {
        "id": 1,
        "username": "admin",
        "role": "admin",
        "has_totp": False,
    }

    response = await http_client.post(
        "/api/actions/execute",
        json={"action_id": "svc.restart", "params": {"service": "not-allowed"}},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_execute_action_rejects_unknown_action(client):
    """POST /api/actions/execute rejects unknown action_id."""
    http_client, app = client
    from api.deps import current_user

    app.dependency_overrides[current_user] = lambda: {
        "id": 1,
        "username": "admin",
        "role": "admin",
        "has_totp": False,
    }

    response = await http_client.post(
        "/api/actions/execute",
        json={"action_id": "unknown.action", "params": {}},
    )
    assert response.status_code in (403, 404)


@pytest.mark.asyncio
async def test_execute_action_audits(client):
    """POST /api/actions/execute writes audit log."""
    http_client, app = client
    from api.deps import current_user
    from db import get_control_db

    app.dependency_overrides[current_user] = lambda: {
        "id": 1,
        "username": "admin",
        "role": "admin",
        "has_totp": False,
    }

    response = await http_client.post(
        "/api/actions/execute",
        json={"action_id": "update.check"},
    )
    assert response.status_code == 200

    db = await get_control_db()
    cursor = await db.execute(
        "SELECT COUNT(*) FROM audit_log WHERE action = ?",
        ("update.check",),
    )
    count = (await cursor.fetchone())[0]
    assert count >= 1


@pytest.mark.asyncio
async def test_confirmation_required(client):
    """Actions requiring confirmation should fail without confirm=true."""
    http_client, app = client
    from api.deps import current_user

    app.dependency_overrides[current_user] = lambda: {
        "id": 1,
        "username": "admin",
        "role": "admin",
        "has_totp": False,
    }

    response = await http_client.post(
        "/api/actions/execute",
        json={"action_id": "svc.stop", "params": {"service": "ssh"}},
    )
    assert response.status_code == 400
