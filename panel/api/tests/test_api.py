"""
Pi Control Panel - API Tests

Pytest tests for the Panel API.
"""

import pytest
from fastapi.testclient import TestClient
from fastapi.routing import APIRoute

# Set up test environment before imports
import os
import tempfile
from pathlib import Path

TEST_ROOT = Path(tempfile.mkdtemp(prefix="pi-control-api-tests-"))
os.environ["JWT_SECRET"] = "test-secret-key-for-testing"
os.environ["DATABASE_PATH"] = ":memory:"
os.environ["TELEMETRY_DB_PATH"] = ":memory:"
os.environ["BACKUP_LOCAL_DIR"] = str(TEST_ROOT / "backups")
os.environ["BACKUP_CREDENTIALS_DIR"] = str(TEST_ROOT / "credentials")
os.environ["BACKUP_DAILY_EXPORT_ENABLED"] = "false"
os.environ["API_DEBUG"] = "true"


@pytest.fixture
def client():
    """Create test client."""
    from main import app
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client):
    """Get authenticated headers with admin token."""
    # Mock the authentication to return a valid admin user
    return {"Authorization": "Bearer test-token"}


class TestHealthEndpoint:
    """Test health check endpoint."""
    
    def test_health_check(self, client):
        """Test that health endpoint returns healthy status."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "1.0.0"


class TestApiRoot:
    """Test API root endpoint."""
    
    def test_api_root(self, client):
        """Test API root returns version info."""
        response = client.get("/api")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Pi Control Panel API"
        assert data["version"] == "1.0.0"

    @pytest.mark.parametrize(
        "path",
        [
            "/%2e%2e/package.json",
            "/%2e%2e%2fpackage.json",
            "/..%2fpackage.json",
        ],
    )
    def test_spa_fallback_cannot_read_files_outside_dist(self, client, path):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert '"name": "pi-control-ui"' not in response.text


class TestRouteInventory:
    """Keep every API operation visible and protected by default."""

    PUBLIC_PATHS = {
        "/api",
        "/api/health",
        "/api/auth/login",
        "/api/auth/refresh",
    }

    def test_all_api_operations_are_unique_and_accounted_for(self):
        from main import app

        routes = [route for route in app.routes if isinstance(route, APIRoute)]
        operations = [
            (method, route.path)
            for route in routes
            for method in route.methods
        ]

        assert len(routes) == 204
        assert len(operations) == len(set(operations))
        assert sum(path.startswith("/api") for _, path in operations) == 203

    def test_every_non_public_api_route_requires_authentication(self):
        from main import app

        unprotected = []
        for route in app.routes:
            if not isinstance(route, APIRoute):
                continue
            if not route.path.startswith("/api") or route.path in self.PUBLIC_PATHS:
                continue
            if not route.dependant.dependencies:
                unprotected.append((sorted(route.methods), route.path))

        assert unprotected == []


class TestAuthEndpoints:
    """Test authentication endpoints."""
    
    def test_login_missing_credentials(self, client):
        """Test login without credentials fails."""
        response = client.post("/api/auth/login", json={})
        assert response.status_code == 422  # Validation error
    
    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials fails."""
        response = client.post("/api/auth/login", json={
            "username": "invalid",
            "password": "invalid"
        })
        assert response.status_code == 401
    
    def test_me_without_auth(self, client):
        """Test /me endpoint without auth returns 401."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401


class TestResourcesEndpoints:
    """Test resources endpoints."""
    
    def test_list_resources_without_auth(self, client):
        """Test listing resources without auth fails."""
        response = client.get("/api/resources")
        assert response.status_code == 401


class TestTelemetryEndpoints:
    """Test telemetry endpoints."""
    
    def test_current_telemetry_without_auth(self, client):
        """Test current telemetry without auth fails."""
        response = client.get("/api/telemetry/current")
        assert response.status_code == 401


class TestJobsEndpoints:
    """Test jobs endpoints."""
    
    def test_list_jobs_without_auth(self, client):
        """Test listing jobs without auth fails."""
        response = client.get("/api/jobs")
        assert response.status_code == 401
    
    def test_job_types_without_auth(self, client):
        """Test job types without auth fails."""
        response = client.get("/api/jobs/types")
        assert response.status_code == 401


class TestAlertsEndpoints:
    """Test alerts endpoints."""
    
    def test_list_alerts_without_auth(self, client):
        """Test listing alerts without auth fails."""
        response = client.get("/api/alerts")
        assert response.status_code == 401
    
    def test_list_rules_without_auth(self, client):
        """Test listing rules without auth fails."""
        response = client.get("/api/alerts/rules")
        assert response.status_code == 401


class TestNetworkEndpoints:
    """Test network endpoints."""
    
    def test_list_interfaces_without_auth(self, client):
        """Test listing interfaces without auth fails."""
        response = client.get("/api/network/interfaces")
        assert response.status_code == 401


class TestDevicesEndpoints:
    """Test devices endpoints."""
    
    def test_list_devices_without_auth(self, client):
        """Test listing devices without auth fails."""
        response = client.get("/api/devices")
        assert response.status_code == 401


class TestAdminConsoleEndpoints:
    """Test admin console endpoints."""
    
    def test_console_without_auth(self, client):
        """Test console without auth fails."""
        response = client.post("/api/admin/console", json={
            "command": "ls",
            "mode": "safe"
        })
        assert response.status_code == 401
    
    def test_allowlist_without_auth(self, client):
        """Test allowlist without auth fails."""
        response = client.get("/api/admin/allowlist")
        assert response.status_code == 401


class TestSSEEndpoints:
    """Test SSE endpoints."""
    
    def test_stream_without_auth(self, client):
        """Test SSE stream without auth fails."""
        response = client.get("/api/sse/stream")
        assert response.status_code == 401


class TestAuditEndpoints:
    """Test audit endpoints."""
    
    def test_audit_logs_without_auth(self, client):
        """Test audit logs without auth fails."""
        response = client.get("/api/audit")
        assert response.status_code == 401


class TestManifestsEndpoints:
    """Test manifests endpoints."""
    
    def test_templates_without_auth(self, client):
        """Test templates without auth fails."""
        response = client.get("/api/manifests/templates")
        assert response.status_code == 401


# Integration tests with mocked auth

class TestAuthenticatedEndpoints:
    """Test endpoints with mocked authentication."""
    
    @pytest.fixture
    def mock_auth(self):
        """Mock authentication dependency."""
        
        async def mock_get_current_user():
            return {
                "id": 1,
                "username": "testadmin",
                "role": "admin",
                "has_totp": False
            }
        
        return mock_get_current_user


# Rate limiting tests

class TestRateLimiting:
    """Test rate limiting."""
    
    def test_health_endpoint_is_exempt_from_api_rate_limit(self, client):
        """Health probes remain available without authentication."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_client_ip_uses_last_proxy_hop_and_rejects_direct_spoof(self):
        from starlette.requests import Request
        from main import _client_ip

        proxied = Request({
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-forwarded-for", b"203.0.113.10, 192.0.2.25")],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 8080),
            "scheme": "http",
            "query_string": b"",
        })
        direct = Request({
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-forwarded-for", b"203.0.113.99")],
            "client": ("198.51.100.7", 12345),
            "server": ("127.0.0.1", 8080),
            "scheme": "http",
            "query_string": b"",
        })

        assert _client_ip(proxied) == "192.0.2.25"
        assert _client_ip(direct) == "198.51.100.7"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
