"""Removed integrations must not remain accessible through the API."""

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient


@pytest.mark.parametrize("path", ["status", "rules", "querylog", "coverage"])
def test_dns_filter_endpoints_are_removed(path):
    from main import app

    client = TestClient(app, raise_server_exceptions=False)
    try:
        assert client.get(f"/api/dns-filter/{path}").status_code == 404
    finally:
        client.close()


def test_dns_filter_operations_are_not_registered():
    from main import app

    assert not any(
        isinstance(route, APIRoute) and route.path.startswith("/api/dns-filter")
        for route in app.routes
    )
