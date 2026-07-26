import asyncio
import os
import re
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

TEST_ROOT = Path(tempfile.mkdtemp(prefix="pi-control-mutation-surface-"))
os.environ.setdefault("JWT_SECRET", "mutation-surface-test-secret-32-bytes")
os.environ["DATABASE_PATH"] = str(TEST_ROOT / "control.db")
os.environ["TELEMETRY_DB_PATH"] = str(TEST_ROOT / "telemetry.db")
os.environ.setdefault("BACKUP_LOCAL_DIR", str(TEST_ROOT / "backups"))
os.environ.setdefault("BACKUP_CREDENTIALS_DIR", str(TEST_ROOT / "credentials"))
os.environ.setdefault("BACKUP_DAILY_EXPORT_ENABLED", "false")

from main import app, settings  # noqa: E402
from db import close_db, init_db  # noqa: E402
from db.migrations import run_migrations  # noqa: E402
from routers import system as system_router  # noqa: E402
from routers.auth import get_current_user, get_current_user_sse  # noqa: E402
from services.agent_client import agent_client  # noqa: E402
from services import host_exec, notification_service as notification_module  # noqa: E402


def authenticated_user():
    return {
        "id": 1,
        "username": "mutation-admin",
        "role": "admin",
        "has_totp": False,
    }


PATH_VALUES = {
    "pin": "17",
    "user_id": "999999",
    "schedule_id": "999999",
    "interface_name": "surface-missing",
    "action": "status",
    "data_type": "telemetry",
    "filename": "surface-missing.tar.gz",
}

SPECIAL_VALUES = {
    "username": "surface-user",
    "password": "surface-password-123",
    "current_password": "wrong-current-password",
    "new_password": "new-surface-password-123",
    "role": "viewer",
    "command": "status",
    "path": "/tmp/pi-control-surface-missing",
    "source": "/tmp/pi-control-surface-missing",
    "destination": "/tmp/pi-control-surface-destination",
    "metric": "host.cpu.pct_total",
    "condition": "gt",
    "severity": "warning",
    "name": "surface-test",
    "device_id": "surface-missing",
    "resource_id": "surface-missing",
    "job_type": "healthcheck",
    "type": "healthcheck",
    "cron": "0 3 * * *",
    "code": "000000",
    "token": "surface-token",
    "chat_id": "surface-chat",
}


def concrete_path(route_path):
    return re.sub(
        r"{([^}:]+)(?::[^}]+)?}",
        lambda match: PATH_VALUES.get(match.group(1), "surface-missing"),
        route_path,
    )


def sample_for_schema(schema, components, name=""):
    if "$ref" in schema:
        schema = components[schema["$ref"].rsplit("/", 1)[-1]]
    if "default" in schema:
        return schema["default"]
    if "enum" in schema:
        return schema["enum"][0]
    if "const" in schema:
        return schema["const"]
    for union_key in ("anyOf", "oneOf"):
        if union_key in schema:
            options = [item for item in schema[union_key] if item.get("type") != "null"]
            return sample_for_schema(options[0] if options else schema[union_key][0], components, name)

    schema_type = schema.get("type")
    if schema_type == "object" or "properties" in schema:
        required = set(schema.get("required", []))
        return {
            key: sample_for_schema(value, components, key)
            for key, value in schema.get("properties", {}).items()
            if key in required or "default" in value
        }
    if schema_type == "array":
        return []
    if schema_type == "boolean":
        return False
    if schema_type in {"integer", "number"}:
        return max(schema.get("minimum", 1), 1)
    if name in SPECIAL_VALUES:
        return SPECIAL_VALUES[name]
    if schema.get("format") == "date-time":
        return "2026-01-01T00:00:00Z"
    return "surface-test"


OPENAPI = app.openapi()
COMPONENTS = OPENAPI.get("components", {}).get("schemas", {})
MUTATION_CASES = []
for path, path_item in OPENAPI["paths"].items():
    for method in ("post", "put", "patch", "delete"):
        operation = path_item.get(method)
        if not operation:
            continue
        parameters = path_item.get("parameters", []) + operation.get("parameters", [])
        query = {}
        for parameter in parameters:
            if parameter.get("in") == "query" and parameter.get("required"):
                query[parameter["name"]] = sample_for_schema(
                    parameter.get("schema", {}),
                    COMPONENTS,
                    parameter["name"],
                )
        body = None
        content = operation.get("requestBody", {}).get("content", {})
        if "application/json" in content:
            body = sample_for_schema(content["application/json"]["schema"], COMPONENTS)
        MUTATION_CASES.append((method, path, query, body))


@pytest.fixture(scope="module")
def mutation_client():
    settings.rate_limit_per_minute = 10_000
    settings.database_path = str(TEST_ROOT / "control.db")
    settings.telemetry_db_path = str(TEST_ROOT / "telemetry.db")
    asyncio.run(run_migrations(settings.database_path))
    asyncio.run(init_db())
    app.dependency_overrides[get_current_user] = authenticated_user
    app.dependency_overrides[get_current_user_sse] = authenticated_user
    with ExitStack() as stack:
        stack.enter_context(patch.object(agent_client, "call", new=AsyncMock(return_value={})))
        stack.enter_context(
            patch.object(system_router, "execute_power_command", new=AsyncMock(return_value=None))
        )
        stack.enter_context(
            patch.object(
                host_exec,
                "run_host_command_simple",
                new=Mock(return_value=""),
            )
        )
        stack.enter_context(
            patch.object(notification_module, "TOKEN_FILE", TEST_ROOT / "telegram-token")
        )
        stack.enter_context(
            patch.object(notification_module, "CHAT_FILE", TEST_ROOT / "telegram-chat")
        )
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/auth/users",
            json={
                "username": "mutation-admin",
                "password": "surface-test-password",
                "role": "admin",
            },
        )
        assert response.status_code in {200, 400}
        yield client
        client.close()
    app.dependency_overrides.clear()
    asyncio.run(close_db())


@pytest.mark.parametrize(
    ("method", "path", "query", "body"),
    MUTATION_CASES,
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_every_http_mutation_avoids_internal_errors(mutation_client, method, path, query, body):
    kwargs = {"params": query}
    if body is not None:
        kwargs["json"] = body
    response = mutation_client.request(method.upper(), concrete_path(path), **kwargs)

    assert response.status_code != 500, (
        f"{method.upper()} {path} raised an internal error: {response.text[:500]}"
    )
