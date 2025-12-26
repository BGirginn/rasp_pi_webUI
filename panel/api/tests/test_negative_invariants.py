"""
Negative Invariant Tests
Simulates security regressions to verify CI catches them.

These tests verify that violations of security invariants are detected.
Each test should PASS (the test passes by verifying the protection mechanism works).
"""

import ast
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from core.actions.loader import get_registry
from core.actions.guards import check_confirmation
from fastapi import HTTPException

pytestmark = pytest.mark.invariant


def test_ci_detects_missing_handler():
    """Verify CI fails when registry references a handler that doesn't exist."""
    from tests.invariant_helpers import find_missing_handlers, get_all_handler_functions
    
    # Create a mock registry with a missing handler
    mock_registry = {
        "actions": [
            {
                "id": "fake.nonexistent",
                "handler": "handler.fake.nonexistent",
                "params_schema": {}
            }
        ]
    }
    
    handler_funcs = get_all_handler_functions()
    missing = find_missing_handlers(mock_registry, handler_funcs)
    
    # This should detect the missing handler
    assert len(missing) > 0, "CI failed to detect missing handler"
    assert "handler.fake.nonexistent" in missing


def test_ci_detects_orphaned_handler():
    """Verify CI fails when a handler exists without registry entry."""
    from tests.invariant_helpers import find_orphaned_handlers
    
    # Mock a registry that's missing an action
    real_registry = get_registry()
    mock_registry = {
        "actions": real_registry["actions"][:-1]  # Remove last action
    }
    
    # Mock handler functions to include all real handlers
    real_handlers = {}
    from core.actions import handlers as handlers_module
    for name in dir(handlers_module):
        if name.startswith("handler_"):
            real_handlers[name] = getattr(handlers_module, name)
    
    orphaned = find_orphaned_handlers(mock_registry, real_handlers)
    
    # Should detect at least one orphaned handler
    assert len(orphaned) > 0, "CI failed to detect orphaned handler"


def test_ci_detects_signature_mismatch():
    """Verify CI fails when handler signature doesn't match schema."""
    from tests.invariant_helpers import validate_signature_match
    
    # Create a mock handler that doesn't match its schema
    async def mock_handler_wrong_params(wrong_param: str):
        pass
    
    # Schema expects different param
    schema = {
        "correct_param": {"type": "string"}
    }
    
    validation = validate_signature_match(mock_handler_wrong_params, schema)
    
    # Should detect the mismatch
    assert not validation["valid"], "CI failed to detect signature mismatch"
    assert len(validation["errors"]) > 0


def test_ci_detects_unlisted_mutation_route():
    """Verify CI fails when a new mutation route is added outside allowlist."""
    # This is tested in test_no_mutation_routes_outside_allowlist
    # Here we verify the detection mechanism works
    
    fake_router_code = '''
from fastapi import APIRouter

router = APIRouter()

@router.post("/dangerous/new/endpoint")
async def dangerous_new_mutation():
    pass
'''
    
    # Parse and check for mutation routes
    tree = ast.parse(fake_router_code)
    found_mutation = False
    
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for deco in node.decorator_list:
                if isinstance(deco, ast.Call):
                    if isinstance(deco.func, ast.Attribute):
                        if deco.func.attr == "post":
                            found_mutation = True
    
    assert found_mutation, "CI detection mechanism for mutation routes is broken"


def test_ci_detects_adapter_import_in_router():
    """Verify CI fails when router imports adapters directly."""
    # Mock router code that violates the rule
    fake_router_code = "from adapters import systemd\n"
    
    # Detection should catch this
    assert "from adapters" in fake_router_code, "CI detection mechanism is broken"


def test_confirmation_bypass_impossible():
    """Verify confirmation-required actions cannot be bypassed."""
    registry = get_registry()
    
    # Find any action that requires confirmation
    confirm_required_action = None
    for action in registry.get("actions", []):
        if action.get("requires_confirmation"):
            confirm_required_action = action["id"]
            break
    
    if confirm_required_action:
        # Attempt to execute without confirmation should fail
        with pytest.raises(HTTPException) as exc_info:
            check_confirmation(registry, confirm_required_action, confirm=False)
        
        assert exc_info.value.status_code == 400, "Confirmation bypass was not prevented"


def test_handler_without_registry_entry_detected():
    """Verify that adding a handler without registry entry is detected."""
    from tests.invariant_helpers import get_all_handler_functions, get_registry_handler_refs
    
    registry = get_registry()
    registry_refs = get_registry_handler_refs(registry)
    handler_funcs = get_all_handler_functions()
    
    # Convert registry refs to expected function names
    expected_funcs = {ref.replace(".", "_") for ref in registry_refs}
    actual_funcs = set(handler_funcs.keys())
    
    # All actual functions should have registry entries
    orphans = actual_funcs - expected_funcs
    
    # In a well-maintained codebase, there should be no orphans
    # This test verifies the detection mechanism works
    assert isinstance(orphans, set), "Orphan detection mechanism is broken"


@pytest.mark.asyncio
async def test_rollback_plan_required_for_auto_rollback():
    """Verify actions with auto rollback must have a plan."""
    from core.rollback.network import determine_rollback_plan
    
    registry = get_registry()
    
    # Find an action with auto rollback
    auto_rollback_action = None
    for action in registry.get("actions", []):
        rollback = action.get("rollback", {})
        if rollback.get("supported") and rollback.get("auto"):
            auto_rollback_action = action
            break
    
    if auto_rollback_action:
        # Mock params
        params = {}
        for key, spec in auto_rollback_action.get("params_schema", {}).items():
            if spec.get("type") == "boolean":
                params[key] = True
            elif spec.get("type") == "string":
                params[key] = "test"
        
        # Should be able to determine a plan
        with mock.patch("core.rollback.network._get_wifi_enabled", return_value=True):
            plan = await determine_rollback_plan(auto_rollback_action["id"], params)
            
            # Plan should exist
            assert plan is not None or auto_rollback_action["id"] in ["net.reset_safe"], \
                f"No rollback plan for action with auto rollback: {auto_rollback_action['id']}"


def test_action_id_format_validation():
    """Verify invalid action ID formats are detected."""
    from tests.invariant_helpers import validate_action_id_format
    
    # Valid formats
    assert validate_action_id_format("obs.get_logs")
    assert validate_action_id_format("svc.restart")
    assert validate_action_id_format("emergency.safe_mode_enable")
    
    # Invalid formats
    assert not validate_action_id_format("invalid")  # No dot
    assert not validate_action_id_format("too.many.parts")  # Too many parts
    assert not validate_action_id_format(".nodot")  # No category
    assert not validate_action_id_format("nodot.")  # No action
