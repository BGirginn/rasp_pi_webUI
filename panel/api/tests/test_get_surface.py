import asyncio
import os
import re
import tempfile
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

TEST_ROOT = Path(tempfile.mkdtemp(prefix="pi-control-get-surface-"))
os.environ.setdefault("JWT_SECRET", "get-surface-test-secret-with-32-bytes")
os.environ["DATABASE_PATH"] = str(TEST_ROOT / "control.db")
os.environ["TELEMETRY_DB_PATH"] = str(TEST_ROOT / "telemetry.db")
os.environ.setdefault("BACKUP_LOCAL_DIR", str(TEST_ROOT / "backups"))
os.environ.setdefault("BACKUP_CREDENTIALS_DIR", str(TEST_ROOT / "credentials"))
os.environ.setdefault("BACKUP_DAILY_EXPORT_ENABLED", "false")

from main import app, settings  # noqa: E402
from db import close_db, init_db  # noqa: E402
from db.migrations import run_migrations  # noqa: E402
from routers.auth import get_current_user, get_current_user_sse  # noqa: E402


def authenticated_user():
    return {
        "id": 1,
        "username": "surface-admin",
        "role": "admin",
        "has_totp": False,
    }


PATH_VALUES = {
    "pin": "17",
    "user_id": "999999",
    "metric_name": "host.cpu.pct_total",
    "interface_name": "lo",
    "data_type": "telemetry",
    "filename": "missing-backup.tar.gz",
}

QUERY_VALUES = {
    "metrics": "host.cpu.pct_total",
    "query": "surface-test",
    "service": "pi-control",
    "path": "/tmp/pi-control-surface-missing",
}


def concrete_path(route_path):
    return re.sub(
        r"{([^}:]+)(?::[^}]+)?}",
        lambda match: PATH_VALUES.get(match.group(1), "surface-missing"),
        route_path,
    )


GET_ROUTES = [
    route
    for route in app.routes
    if isinstance(route, APIRoute)
    and "GET" in route.methods
    and route.path.startswith("/api")
    and "/stream" not in route.path
    and not route.path.startswith("/api/sse/")
]


@pytest.fixture(scope="module")
def authenticated_client():
    settings.rate_limit_per_minute = 10_000
    settings.database_path = str(TEST_ROOT / "control.db")
    settings.telemetry_db_path = str(TEST_ROOT / "telemetry.db")
    asyncio.run(run_migrations(settings.database_path))
    asyncio.run(init_db())
    app.dependency_overrides[get_current_user] = authenticated_user
    app.dependency_overrides[get_current_user_sse] = authenticated_user
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/auth/users",
        json={
            "username": "surface-admin",
            "password": "surface-test-password",
            "role": "admin",
        },
    )
    assert response.status_code in {200, 400}
    yield client
    client.close()
    app.dependency_overrides.clear()
    asyncio.run(close_db())


@pytest.mark.parametrize("route", GET_ROUTES, ids=lambda route: route.path)
def test_every_non_streaming_get_route_avoids_internal_errors(authenticated_client, route):
    query = {
        field.name: QUERY_VALUES.get(field.name, "surface-test")
        for field in route.dependant.query_params
        if field.required
    }
    response = authenticated_client.get(concrete_path(route.path), params=query)

    assert response.status_code != 500, (
        f"GET {route.path} raised an internal error: {response.text[:500]}"
    )
