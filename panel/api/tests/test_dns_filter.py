"""
Tests for DNS filtering router and AdGuard Home integration boundaries.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

TEST_ROOT = Path(tempfile.mkdtemp(prefix="pi-control-dns-filter-tests-"))
os.environ["JWT_SECRET"] = "test-secret-key-for-testing"
os.environ["DATABASE_PATH"] = ":memory:"
os.environ["TELEMETRY_DB_PATH"] = ":memory:"
os.environ["BACKUP_LOCAL_DIR"] = str(TEST_ROOT / "backups")
os.environ["BACKUP_CREDENTIALS_DIR"] = str(TEST_ROOT / "credentials")
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


def test_dns_filter_status_not_installed(monkeypatch, app_with_admin):
    from routers import dns_filter

    monkeypatch.setattr(
        dns_filter.adguard_home_client,
        "status",
        AsyncMock(return_value={"installed": False, "managed": False, "error": "not configured"}),
    )

    with TestClient(app_with_admin) as client:
        response = client.get("/api/dns-filter/status")

    assert response.status_code == 200
    assert response.json()["installed"] is False


def test_dns_filter_protection_toggle(monkeypatch, app_with_admin):
    from routers import dns_filter

    monkeypatch.setattr(
        dns_filter.adguard_home_client,
        "set_protection",
        AsyncMock(return_value={"installed": True, "protection_enabled": True}),
    )

    with TestClient(app_with_admin) as client:
        response = client.post("/api/dns-filter/protection", json={"enabled": True})

    assert response.status_code == 200
    assert response.json()["protection_enabled"] is True
    dns_filter.adguard_home_client.set_protection.assert_awaited_once_with(True)


def test_dns_filter_rules_replace(monkeypatch, app_with_admin):
    from routers import dns_filter

    monkeypatch.setattr(
        dns_filter.adguard_home_client,
        "set_rules",
        AsyncMock(return_value={
            "blocked_domains": ["ads.example.com"],
            "allowed_domains": ["safe.example.com"],
        }),
    )

    with TestClient(app_with_admin) as client:
        response = client.put(
            "/api/dns-filter/rules",
            json={
                "blocked_domains": ["ads.example.com"],
                "allowed_domains": ["safe.example.com"],
            },
        )

    assert response.status_code == 200
    assert response.json()["blocked_domains"] == ["ads.example.com"]


def test_dns_filter_check_domain(monkeypatch, app_with_admin):
    from routers import dns_filter

    monkeypatch.setattr(
        dns_filter.adguard_home_client,
        "check",
        AsyncMock(return_value={
            "domain": "doubleclick.net",
            "blocked": True,
            "reason": "FilteredBlackList",
        }),
    )

    with TestClient(app_with_admin) as client:
        response = client.post("/api/dns-filter/check", json={"domain": "doubleclick.net"})

    assert response.status_code == 200
    assert response.json()["blocked"] is True


def test_dns_filter_mutation_requires_admin(app_with_viewer):
    with TestClient(app_with_viewer) as client:
        response = client.post("/api/dns-filter/protection", json={"enabled": False})

    assert response.status_code == 403


def test_dns_filter_querylog_requires_admin(app_with_viewer):
    with TestClient(app_with_viewer) as client:
        response = client.get("/api/dns-filter/querylog")

    assert response.status_code == 403


def test_dns_filter_coverage_requires_admin(app_with_viewer):
    with TestClient(app_with_viewer) as client:
        response = client.get("/api/dns-filter/coverage")

    assert response.status_code == 403


def test_dns_filter_coverage(monkeypatch, app_with_admin):
    from routers import dns_filter

    monkeypatch.setattr(
        dns_filter.adguard_home_client,
        "coverage",
        AsyncMock(return_value={
            "clients": [{"client": "192.168.0.10", "queries": 4, "blocked": 1}],
            "client_count": 1,
            "sample_size": 4,
        }),
    )

    with TestClient(app_with_admin) as client:
        response = client.get("/api/dns-filter/coverage")

    assert response.status_code == 200
    assert response.json()["client_count"] == 1


def test_managed_rules_preserve_external_rules():
    from services.adguard_home import _merge_managed_rules, _parse_managed_rules

    rules = [
        "||external.example^",
        "# pi-control-managed-start",
        "||old.example^",
        "# pi-control-managed-end",
    ]

    merged = _merge_managed_rules(rules, ["ads.example.com"], ["safe.example.com"])
    parsed = _parse_managed_rules(merged)

    assert "||external.example^" in merged
    assert parsed == {
        "blocked_domains": ["ads.example.com"],
        "allowed_domains": ["safe.example.com"],
    }
