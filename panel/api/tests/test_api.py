"""
Pi Control Panel - API Tests

Pytest tests for the Panel API.
"""

import os

import pytest
from httpx import AsyncClient, ASGITransport

from config import settings

os.environ["JWT_SECRET"] = "test-secret-key-for-testing"
os.environ["DATABASE_PATH"] = ":memory:"
os.environ["TELEMETRY_DB_PATH"] = ":memory:"
os.environ["API_DEBUG"] = "true"

settings.database_path = ":memory:"
settings.telemetry_db_path = ":memory:"
settings.jwt_secret = "test-secret-key-for-testing"

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def client():
    """Create async test client without running lifespan."""
    from main import app
    from db import init_db, close_db
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    await close_db()


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    async def test_health_check(self, client):
        """Test that health endpoint returns healthy status."""
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "1.0.0"


class TestApiRoot:
    """Test API root endpoint."""
    
    async def test_api_root(self, client):
        """Test API root returns version info."""
        response = await client.get("/api")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Pi Control Panel API"
        assert data["version"] == "1.0.0"


class TestAuthEndpoints:
    """Test authentication endpoints."""
    
    async def test_login_missing_credentials(self, client):
        """Test login without credentials fails."""
        response = await client.post("/api/auth/login", json={})
        assert response.status_code == 422  # Validation error
    
    async def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials fails."""
        response = await client.post("/api/auth/login", json={
            "username": "invalid",
            "password": "invalid"
        })
        assert response.status_code == 401
    
    async def test_me_without_auth(self, client):
        """Test /me endpoint without auth returns 401."""
        response = await client.get("/api/auth/me")
        assert response.status_code in (401, 403)


class TestResourcesEndpoints:
    """Test resources endpoints."""
    
    async def test_list_resources_without_auth(self, client):
        """Test listing resources without auth fails."""
        response = await client.get("/api/resources")
        assert response.status_code in (401, 403)


class TestTelemetryEndpoints:
    """Test telemetry endpoints."""
    
    async def test_current_telemetry_without_auth(self, client):
        """Test current telemetry without auth fails."""
        response = await client.get("/api/telemetry/current")
        assert response.status_code in (401, 403)


class TestJobsEndpoints:
    """Test jobs endpoints."""
    
    async def test_list_jobs_without_auth(self, client):
        """Test listing jobs without auth fails."""
        response = await client.get("/api/jobs")
        assert response.status_code in (401, 403)
    
    async def test_job_types_without_auth(self, client):
        """Test job types without auth fails."""
        response = await client.get("/api/jobs/types")
        assert response.status_code in (401, 403)


class TestAlertsEndpoints:
    """Test alerts endpoints."""
    
    async def test_list_alerts_without_auth(self, client):
        """Test listing alerts without auth fails."""
        response = await client.get("/api/alerts")
        assert response.status_code in (401, 403)
    
    async def test_list_rules_without_auth(self, client):
        """Test listing rules without auth fails."""
        response = await client.get("/api/alerts/rules")
        assert response.status_code in (401, 403)


class TestNetworkEndpoints:
    """Test network endpoints."""
    
    async def test_list_interfaces_without_auth(self, client):
        """Test listing interfaces without auth fails."""
        response = await client.get("/api/network/interfaces")
        assert response.status_code in (401, 403)


class TestDevicesEndpoints:
    """Test devices endpoints."""
    
    async def test_list_devices_without_auth(self, client):
        """Test listing devices without auth fails."""
        response = await client.get("/api/devices")
        assert response.status_code in (401, 403)


class TestSSEEndpoints:
    """Test SSE endpoints."""
    
    async def test_stream_without_auth(self, client):
        """Test SSE stream without auth fails."""
        response = await client.get("/api/sse/stream")
        assert response.status_code in (401, 403)


class TestAuditEndpoints:
    """Test audit endpoints."""
    
    async def test_audit_logs_without_auth(self, client):
        """Test audit logs without auth fails."""
        response = await client.get("/api/audit")
        assert response.status_code in (401, 403)


class TestManifestsEndpoints:
    """Test manifests endpoints."""
    
    async def test_templates_without_auth(self, client):
        """Test templates without auth fails."""
        response = await client.get("/api/manifests/templates")
        assert response.status_code in (401, 403)
