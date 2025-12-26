"""
CI Invariants
Hard gates to prevent mutation surface drift and registry divergence.
"""

import ast
from pathlib import Path

import pytest
import yaml
from fastapi import HTTPException

from core.actions.loader import get_registry
from core.actions.guards import check_confirmation
from core.rollback.network import determine_rollback_plan

pytestmark = pytest.mark.invariant

REPO_ROOT = Path(__file__).resolve().parents[3]
PANEL_REGISTRY_PATH = REPO_ROOT / "panel" / "api" / "core" / "actions" / "registry.yaml"
AGENT_REGISTRY_PATH = REPO_ROOT / "agent" / "policy" / "registry.yaml"


def _requires_confirmation(action: dict, defaults: dict) -> bool:
    return action.get("requires_confirmation", defaults.get("requires_confirmation", False))


def _load_agent_registry() -> dict:
    return yaml.safe_load(AGENT_REGISTRY_PATH.read_text())


def _build_params(schema: dict) -> dict:
    params = {}
    for name, spec in schema.items():
        if "default" in spec:
            params[name] = spec["default"]
            continue
        if "enum" in spec and spec["enum"]:
            params[name] = spec["enum"][0]
            continue
        param_type = spec.get("type")
        if param_type == "boolean":
            params[name] = False
        elif param_type == "integer":
            params[name] = spec.get("minimum", 0)
        elif param_type == "number":
            params[name] = spec.get("minimum", 0)
        elif param_type == "array":
            params[name] = spec.get("default", [])
        elif param_type == "object":
            params[name] = {}
        elif param_type == "string":
            params[name] = "placeholder"
    return params


def _iter_mutation_routes(path: Path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for deco in node.decorator_list:
                if not isinstance(deco, ast.Call):
                    continue
                if not isinstance(deco.func, ast.Attribute):
                    continue
                if not isinstance(deco.func.value, ast.Name):
                    continue
                if deco.func.value.id != "router":
                    continue
                method = deco.func.attr
                if method not in {"post", "put", "delete", "patch"}:
                    continue
                path_arg = None
                if deco.args:
                    if isinstance(deco.args[0], ast.Constant) and isinstance(deco.args[0].value, str):
                        path_arg = deco.args[0].value
                yield method, path_arg, node.lineno


def test_panel_registry_subset_of_agent_registry():
    """Every panel action must be present in the agent registry."""
    panel_registry = get_registry()
    agent_registry = _load_agent_registry()

    panel_ids = {action["id"] for action in panel_registry.get("actions", [])}
    agent_ids = {action["id"] for action in agent_registry.get("actions", [])}

    missing = panel_ids - agent_ids
    assert not missing, f"Panel actions missing from agent registry: {sorted(missing)}"


def test_confirm_required_actions_guarded():
    """Actions requiring confirmation must fail without confirm."""
    registry = get_registry()
    defaults = registry.get("defaults", {})

    for action in registry.get("actions", []):
        if not _requires_confirmation(action, defaults):
            continue
        with pytest.raises(HTTPException):
            check_confirmation(registry, action["id"], confirm=False)


@pytest.mark.asyncio
async def test_rollback_actions_have_plan(monkeypatch):
    """Rollback-required actions must yield a rollback plan."""
    registry = get_registry()

    async def fake_wifi_state():
        return True

    monkeypatch.setattr("core.rollback.network._get_wifi_enabled", fake_wifi_state)

    for action in registry.get("actions", []):
        rollback = action.get("rollback") or {}
        if rollback.get("supported") and rollback.get("auto"):
            params = _build_params(action.get("params_schema") or {})
            plan = await determine_rollback_plan(action["id"], params)
            assert plan is not None, f"Missing rollback plan for: {action['id']}"


def test_no_mutation_routes_outside_allowlist():
    """Only explicitly allowlisted mutation routes are permitted."""
    allowed = {
        ("post", "/execute"),
        ("post", "/confirm"),
        ("post", "/first-run/create-owner"),
        ("post", "/login"),
        ("post", "/refresh"),
        ("post", "/logout"),
        ("post", "/password/change"),
        ("post", "/{manifest_id}/diff"),
    }

    router_dirs = [
        REPO_ROOT / "panel" / "api" / "routers",
        REPO_ROOT / "panel" / "api" / "api" / "routers",
    ]

    violations = []
    for root in router_dirs:
        for path in root.rglob("*.py"):
            for method, route_path, line in _iter_mutation_routes(path):
                if (method, route_path) not in allowed:
                    violations.append(f"{path}:{line} {method.upper()} {route_path}")

    assert not violations, "Unexpected mutation routes:\n" + "\n".join(sorted(violations))


def test_no_adapter_imports_in_routers():
    """Routers must not import adapters directly (bypass Actions API)."""
    router_dirs = [
        REPO_ROOT / "panel" / "api" / "routers",
        REPO_ROOT / "panel" / "api" / "api" / "routers",
    ]

    violations = []
    for root in router_dirs:
        for path in root.rglob("*.py"):
            content = path.read_text()
            if "from adapters" in content or "import adapters" in content:
                violations.append(str(path))

    assert not violations, "Adapters imported in routers:\n" + "\n".join(sorted(violations))


def test_registry_handler_bijection():
    """Registry ↔ Handler bijection: every action has exactly one handler and vice versa."""
    from tests.invariant_helpers import (
        get_registry_handler_refs,
        get_all_handler_functions,
        find_missing_handlers,
        find_orphaned_handlers
    )
    
    registry = get_registry()
    handler_funcs = get_all_handler_functions()
    
    # Check for missing handlers
    missing = find_missing_handlers(registry, handler_funcs)
    assert not missing, f"Registry references handlers that don't exist:\n" + "\n".join(sorted(missing))
    
    # Check for orphaned handlers
    orphaned = find_orphaned_handlers(registry, handler_funcs)
    assert not orphaned, f"Handler functions not referenced in registry:\n" + "\n".join(sorted(orphaned))


def test_schema_handler_signature_match():
    """Schema ↔ Handler signature compatibility: handler must accept all schema params."""
    from tests.invariant_helpers import get_all_handler_functions, validate_signature_match
    
    registry = get_registry()
    handler_funcs = get_all_handler_functions()
    
    violations = []
    
    for action in registry.get("actions", []):
        action_id = action.get("id")
        handler_ref = action.get("handler")
        params_schema = action.get("params_schema", {})
        
        if not handler_ref:
            continue
        
        # Convert handler ref to function name
        func_name = handler_ref.replace(".", "_")
        
        if func_name not in handler_funcs:
            # Already caught by bijection test
            continue
        
        handler_func = handler_funcs[func_name]
        validation = validate_signature_match(handler_func, params_schema)
        
        if not validation["valid"]:
            errors_str = "\n    ".join(validation["errors"])
            violations.append(f"{action_id} ({handler_ref}):\n    {errors_str}")
    
    assert not violations, "Schema-signature mismatches:\n" + "\n".join(violations)


def test_handler_map_complete():
    """HANDLERS dict in engine.py must contain all registry-referenced handlers."""
    from tests.invariant_helpers import get_registry_handler_refs, get_handler_map
    
    registry = get_registry()
    registry_refs = get_registry_handler_refs(registry)
    handler_map = get_handler_map()
    
    missing = []
    for ref in registry_refs:
        if ref not in handler_map:
            missing.append(ref)
    
    assert not missing, f"Handlers missing from HANDLERS dict in engine:\n" + "\n".join(sorted(missing))


def test_no_orphaned_handlers():
    """Handler functions must not exist without registry entries."""
    from tests.invariant_helpers import find_orphaned_handlers, get_all_handler_functions
    
    registry = get_registry()
    handler_funcs = get_all_handler_functions()
    
    orphaned = find_orphaned_handlers(registry, handler_funcs)
    
    assert not orphaned, (
        f"Orphaned handler functions (not in registry):\n" +
        "\n".join(sorted(orphaned)) +
        "\n\nRemove these handlers or add them to registry.yaml"
    )


def test_action_ids_consistent_naming():
    """Action IDs must follow category.action_name format."""
    from tests.invariant_helpers import validate_action_id_format
    
    registry = get_registry()
    
    invalid = []
    for action in registry.get("actions", []):
        action_id = action.get("id")
        if not validate_action_id_format(action_id):
            invalid.append(action_id)
    
    assert not invalid, (
        f"Invalid action ID format (must be category.action_name):\n" +
        "\n".join(sorted(invalid))
    )
