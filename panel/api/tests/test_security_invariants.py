"""
Security Invariants Tests
Validates AR-first invariants across registry, handlers, and rollback config.
"""

import inspect
import pytest

from core.actions.loader import get_registry
from core.actions.handlers import HANDLERS

pytestmark = pytest.mark.invariant


def _requires_confirmation(action: dict, defaults: dict) -> bool:
    return action.get("requires_confirmation", defaults.get("requires_confirmation", False))


def test_registry_handlers_complete():
    """Every registry handler must exist in the static handler map."""
    registry = get_registry()
    missing = []

    for action in registry.get("actions", []):
        handler_name = action.get("handler")
        if handler_name not in HANDLERS:
            missing.append(handler_name)

    assert not missing, f"Missing handlers for: {missing}"


def test_handlers_have_registry_entries():
    """Every handler in the static map must be referenced by the registry."""
    registry = get_registry()
    referenced = {action.get("handler") for action in registry.get("actions", [])}
    extra = set(HANDLERS.keys()) - referenced

    assert not extra, f"Handlers missing registry entries: {sorted(extra)}"


def test_handler_signature_matches_schema():
    """Schema keys must be accepted by handler signature."""
    registry = get_registry()

    for action in registry.get("actions", []):
        schema = action.get("params_schema") or {}
        schema_keys = set(schema.keys())
        handler = HANDLERS[action["handler"]]
        sig = inspect.signature(handler)

        params = [
            p
            for p in sig.parameters.values()
            if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
        ]
        param_names = {p.name for p in params}
        has_var_kw = any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())

        if not has_var_kw:
            missing = schema_keys - param_names
            assert not missing, f"{action['id']} missing params in handler: {missing}"

        required = {p.name for p in params if p.default is inspect._empty}
        assert required.issubset(schema_keys), (
            f"{action['id']} requires params not in schema: {required - schema_keys}"
        )


def test_allowlist_refs_exist():
    """Allowlist refs must point to defined, non-empty targets."""
    registry = get_registry()
    targets = registry.get("targets", {})

    for action in registry.get("actions", []):
        schema = action.get("params_schema") or {}
        for param_schema in schema.values():
            allowlist_ref = param_schema.get("allowlist_ref")
            if allowlist_ref:
                assert allowlist_ref in targets, f"Missing allowlist: {allowlist_ref}"
                assert isinstance(targets[allowlist_ref], list)
                assert targets[allowlist_ref], f"Empty allowlist: {allowlist_ref}"


def test_rollback_requires_confirmation_and_timeout():
    """Rollback actions must require confirmation and have a timeout."""
    registry = get_registry()
    defaults = registry.get("defaults", {})

    for action in registry.get("actions", []):
        rollback = action.get("rollback") or {}
        if rollback.get("supported") and rollback.get("auto"):
            timeout = rollback.get("timeout_seconds")
            assert isinstance(timeout, int) and timeout > 0
            assert _requires_confirmation(action, defaults) is True
