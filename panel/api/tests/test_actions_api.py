"""
Test Actions API
Integration tests for /api/actions endpoints.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_actions_requires_auth():
    """GET /api/actions requires authentication."""
    # This would need proper test client setup
    # For now, just a placeholder showing structure
    pass


@pytest.mark.asyncio
async def test_execute_action_enforces_rbac():
    """POST /api/actions/execute enforces RBAC."""
    # Viewer should not be able to execute svc.start
    pass


@pytest.mark.asyncio
async def test_execute_action_validates_params():
    """POST /api/actions/execute validates params against schema."""
    # Invalid params should return 400
    pass


@pytest.mark.asyncio
async def test_execute_action_audits():
    """POST /api/actions/execute always writes audit log."""
    # Check audit_log table after execution
    pass


@pytest.mark.asyncio
async def test_confirmation_required():
    """Actions requiring confirmation should fail without confirm=true."""
    # svc.stop requires confirmation
    pass
