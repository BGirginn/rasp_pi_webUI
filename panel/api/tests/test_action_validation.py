"""
Test Parameter Validation
Validates that parameter validation correctly enforces all schema rules.
"""

import pytest
from core.actions.loader import get_registry
from core.actions.validate import validate_params
from fastapi import HTTPException


def test_validate_service_not_in_allowlist():
    """svc.restart with service not in allowlist should raise 400."""
    registry = get_registry()
    
    # services_allowlist = ["ssh", "tailscaled", "docker", "mosquitto", "pi-agent", "caddy", "panel-api"]
    # Try with a service NOT in the allowlist
    with pytest.raises(HTTPException) as exc_info:
        validate_params(registry, "svc.restart", {"service": "forbidden-service"})
    
    assert exc_info.value.status_code == 400
    assert "ALLOWLIST_VIOLATION" in str(exc_info.value.detail)


def test_validate_service_in_allowlist():
    """svc.restart with service in allowlist should pass."""
    registry = get_registry()
    
    # "ssh" is in services_allowlist
    result = validate_params(registry, "svc.restart", {"service": "ssh"})
    assert result == {"service": "ssh"}


def test_validate_invalid_enum():
    """obs.get_logs with source not in enum should raise 400."""
    registry = get_registry()
    
    # source enum: ["system","service","panel","agent"]
    with pytest.raises(HTTPException) as exc_info:
        validate_params(registry, "obs.get_logs", {"source": "invalid_source"})
    
    assert exc_info.value.status_code == 400
    assert "INVALID_ENUM" in str(exc_info.value.detail)


def test_validate_valid_enum():
    """obs.get_logs with valid source enum should pass."""
    registry = get_registry()
    
    result = validate_params(registry, "obs.get_logs", {"source": "system"})
    # Should have defaults applied for limit
    assert result["source"] == "system"
    assert result["limit"] == 400  # default value


def test_validate_defaults_applied():
    """obs.get_metrics_snapshot with no include param should apply default."""
    registry = get_registry()
    
    result = validate_params(registry, "obs.get_metrics_snapshot", {})
    # Default: ["cpu","mem","disk","net","temp"]
    assert result["include"] == ["cpu", "mem", "disk", "net", "temp"]


def test_validate_unknown_param():
    """Action with unknown param should raise 400."""
    registry = get_registry()
    
    with pytest.raises(HTTPException) as exc_info:
        validate_params(registry, "svc.restart", {"service": "ssh", "unknown_key": "value"})
    
    assert exc_info.value.status_code == 400
    assert "UNKNOWN_PARAM" in str(exc_info.value.detail)


def test_validate_empty_schema_rejects_params():
    """Action with empty params_schema should reject any params."""
    registry = get_registry()
    
    # power.reboot_safe has params_schema: {}
    # Should succeed with no params
    result = validate_params(registry, "power.reboot_safe", None)
    assert result == {}
    
    # Should fail with params
    with pytest.raises(HTTPException) as exc_info:
        validate_params(registry, "power.reboot_safe", {"foo": "bar"})
    
    assert exc_info.value.status_code == 400
    assert "INVALID_PARAMS" in str(exc_info.value.detail)


def test_validate_integer_min_max():
    """obs.get_logs with limit outside min/max should raise 400."""
    registry = get_registry()
    
    # limit: minimum: 50, maximum: 2000
    # Too small
    with pytest.raises(HTTPException) as exc_info:
        validate_params(registry, "obs.get_logs", {"source": "system", "limit": 10})
    
    assert exc_info.value.status_code == 400
    assert "VALUE_TOO_SMALL" in str(exc_info.value.detail)
    
    # Too large
    with pytest.raises(HTTPException) as exc_info:
        validate_params(registry, "obs.get_logs", {"source": "system", "limit": 3000})
    
    assert exc_info.value.status_code == 400
    assert "VALUE_TOO_LARGE" in str(exc_info.value.detail)
    
    # Valid
    result = validate_params(registry, "obs.get_logs", {"source": "system", "limit": 100})
    assert result["limit"] == 100


def test_validate_string_min_max_length():
    """auth.create_user with username outside minLength/maxLength should raise 400."""
    registry = get_registry()
    
    # username: minLength: 3, maxLength: 32
    # Too short
    with pytest.raises(HTTPException) as exc_info:
        validate_params(registry, "auth.create_user", {
            "username": "ab",
            "role": "viewer",
            "temporary_password": "password123456"
        })
    
    assert exc_info.value.status_code == 400
    assert "STRING_TOO_SHORT" in str(exc_info.value.detail)
    
    # Too long
    with pytest.raises(HTTPException) as exc_info:
        validate_params(registry, "auth.create_user", {
            "username": "a" * 40,
            "role": "viewer",
            "temporary_password": "password123456"
        })
    
    assert exc_info.value.status_code == 400
    assert "STRING_TOO_LONG" in str(exc_info.value.detail)


def test_validate_boolean_type():
    """net.toggle_wifi with non-boolean enabled should raise 400."""
    registry = get_registry()
    
    # enabled: { type: boolean }
    with pytest.raises(HTTPException) as exc_info:
        validate_params(registry, "net.toggle_wifi", {"enabled": "true"})  # string instead of bool
    
    assert exc_info.value.status_code == 400
    assert "INVALID_TYPE" in str(exc_info.value.detail)
    
    # Valid
    result = validate_params(registry, "net.toggle_wifi", {"enabled": True})
    assert result["enabled"] is True


def test_validate_array_type():
    """obs.get_metrics_snapshot with include as non-array should raise 400."""
    registry = get_registry()
    
    # include: { type: array, items: { type: string } }
    with pytest.raises(HTTPException) as exc_info:
        validate_params(registry, "obs.get_metrics_snapshot", {"include": "cpu"})  # string instead of array
    
    assert exc_info.value.status_code == 400
    assert "INVALID_TYPE" in str(exc_info.value.detail)
    
    # Valid
    result = validate_params(registry, "obs.get_metrics_snapshot", {"include": ["cpu", "mem"]})
    assert result["include"] == ["cpu", "mem"]


def test_validate_nullable_param():
    """obs.get_logs with nullable service=None should pass."""
    registry = get_registry()
    
    # service: nullable: true
    result = validate_params(registry, "obs.get_logs", {"source": "service", "service": None})
    assert result["service"] is None
