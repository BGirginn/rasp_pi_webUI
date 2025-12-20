"""
Test RBAC (Role-Based Access Control)
Validates that role permissions are correctly enforced.
"""

import pytest
from core.actions.loader import get_registry
from core.auth.rbac import is_role_allowed, assert_role_allowed
from fastapi import HTTPException


def test_rbac_viewer_cannot_start_service():
    """Viewer role should NOT be able to start services."""
    registry = get_registry()
    
    # Viewer is not in roles_allowed for svc.start
    assert is_role_allowed(registry, "viewer", "svc.start") is False
    
    # Should raise 403
    with pytest.raises(HTTPException) as exc_info:
        assert_role_allowed(registry, "viewer", "svc.start")
    assert exc_info.value.status_code == 403


def test_rbac_operator_can_restart_service():
    """Operator role SHOULD be able to restart services."""
    registry = get_registry()
    
    # Operator is in roles_allowed for svc.restart
    assert is_role_allowed(registry, "operator", "svc.restart") is True
    
    # Should NOT raise exception
    assert_role_allowed(registry, "operator", "svc.restart")


def test_rbac_admin_cannot_disable_service():
    """Admin role should NOT be able to disable services (only owner can)."""
    registry = get_registry()
    
    # Admin is NOT in roles_allowed for svc.disable (only owner)
    assert is_role_allowed(registry, "admin", "svc.disable") is False
    
    # Should raise 403
    with pytest.raises(HTTPException) as exc_info:
        assert_role_allowed(registry, "admin", "svc.disable")
    assert exc_info.value.status_code == 403


def test_rbac_owner_can_disable_service():
    """Owner role SHOULD be able to disable services."""
    registry = get_registry()
    
    # Owner is in roles_allowed for svc.disable
    assert is_role_allowed(registry, "owner", "svc.disable") is True
    
    # Should NOT raise exception
    assert_role_allowed(registry, "owner", "svc.disable")


def test_rbac_unknown_action_denies():
    """Unknown action_id should always deny (deny-by-default)."""
    registry = get_registry()
    
    # Non-existent action should deny for all roles
    assert is_role_allowed(registry, "owner", "nonexistent.action") is False
    assert is_role_allowed(registry, "admin", "nonexistent.action") is False
    assert is_role_allowed(registry, "operator", "nonexistent.action") is False
    assert is_role_allowed(registry, "viewer", "nonexistent.action") is False


def test_rbac_unknown_role_denies():
    """Unknown role should always deny (deny-by-default)."""
    registry = get_registry()
    
    # Non-existent role should deny
    assert is_role_allowed(registry, "hacker", "svc.restart") is False
    assert is_role_allowed(registry, "guest", "obs.get_system_status") is False
    
    # Should raise 403
    with pytest.raises(HTTPException) as exc_info:
        assert_role_allowed(registry, "hacker", "svc.restart")
    assert exc_info.value.status_code == 403


def test_rbac_viewer_can_observe():
    """Viewer role SHOULD be able to access observability actions."""
    registry = get_registry()
    
    # Viewer should have access to all observability actions
    assert is_role_allowed(registry, "viewer", "obs.get_system_status") is True
    assert is_role_allowed(registry, "viewer", "obs.get_metrics_snapshot") is True
    assert is_role_allowed(registry, "viewer", "obs.get_logs") is True
