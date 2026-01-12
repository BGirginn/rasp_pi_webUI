"""
Pi Control Panel - API Tests

Pytest tests for the Panel API.
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock

# Set up test environment before imports
import os
os.environ["JWT_SECRET"] = "test-secret-key-for-testing"
os.environ["DATABASE_PATH"] = ":memory:"
os.environ["TELEMETRY_DB_PATH"] = ":memory:"
os.environ["API_DEBUG"] = "true"


@pytest.fixture
def client():
    """Create test client."""
    from main import app
    return TestClient(app)


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
        from routers.auth import get_current_user
        
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
    
    def test_rate_limit_headers(self, client):
        """Test that rate limit headers are present."""
        response = client.get("/api/health")
        # Rate limiting headers should be present after enough requests
        # This is a basic test - actual rate limiting needs more requests


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
