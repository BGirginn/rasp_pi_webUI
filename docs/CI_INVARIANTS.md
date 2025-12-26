# CI_INVARIANTS.md

**Version:** 2.0  
**Scope:** Hard CI gates enforcing security invariants and drift detection  
**Last Updated:** 2025-12-20

## Overview

This document defines the mandatory security invariants enforced at CI time to prevent regressions in the Action Registry control plane. All invariants are fail-fast - violations block merges.

---

## Enforced Invariants (CI Must Pass All)

### 1. Registry ↔ Handler Bijection (Panel)

**Rule:** Every registry action must reference exactly one handler, and every handler must be referenced by exactly one action.

**Implementation:**
- Test: `test_registry_handler_bijection()`
- Checks: Missing handlers, orphaned handlers

**Failure Mode:**
```
Registry references handlers that don't exist:
  handler.fake.missing_action

Handler functions not referenced in registry:
  handler_orphaned_function
```

**Fix:** Add missing handlers to `panel/api/core/actions/handlers.py` or remove orphaned functions.

---

### 2. Panel Registry ⊆ Agent Registry

**Rule:** All panel action IDs must exist in `agent/policy/registry.yaml`.

**Implementation:**
- Test: `test_panel_registry_subset_of_agent_registry()`

**Failure Mode:**
```
Panel actions missing from agent registry:
  dangerous.panel_only_action
```

**Fix:** Add action to `agent/policy/registry.yaml`.

---

### 3. Schema ↔ Handler Signature Compatibility

**Rule:** Handler function signatures must match their `params_schema` definitions.

**Implementation:**
- Test: `test_schema_handler_signature_match()`
- Validates: Required params, optional params, **kwargs usage

**Failure Mode:**
```
Schema-signature mismatches:
  svc.restart (handler.svc.restart):
    Schema requires 'service' but handler doesn't accept it
```

**Fix:** Update handler signature in `handlers.py`.

---

### 4. HANDLERS Dict Completeness

**Rule:** `HANDLERS` dict in `handlers.py` must contain all registry-referenced handlers.

**Implementation:**
- Test: `test_handler_map_complete()`

**Failure Mode:**
```
Handlers missing from HANDLERS dict in engine:
  handler.new.action
```

**Fix:** Add entry to `HANDLERS` dict.

---

### 5. No Orphaned Handlers

**Rule:** Handler functions must not exist without registry entries.

**Implementation:**
- Test: `test_no_orphaned_handlers()`

**Failure Mode:**
```
Orphaned handler functions (not in registry):
  handler_unused_function

Remove these handlers or add them to registry.yaml
```

**Fix:** Either add to registry or delete the function.

---

### 6. Action ID Format Consistency

**Rule:** Action IDs must follow `category.action_name` or `category.subcategory.action_name` format.

**Implementation:**
- Test: `test_action_ids_consistent_naming()`

**Failure Mode:**
```
Invalid action ID format (must be category.action_name):
  invalid_no_dot
  too.many.parts.here
```

**Fix:** Rename action IDs to follow the pattern.

---

### 7. Confirmation Guards Active

**Rule:** Actions with `requires_confirmation: true` must enforce confirmation.

**Implementation:**
- Test: `test_confirm_required_actions_guarded()`

**Failure Mode:**
```
Confirmation not enforced for: power.shutdown_safe
```

**Fix:** Ensure `check_confirmation()` is called in engine.

---

### 8. Rollback Plans Exist

**Rule:** Actions with `rollback.supported: true` and `rollback.auto: true` must return a rollback plan.

**Implementation:**
- Test: `test_rollback_actions_have_plan()`

**Failure Mode:**
```
Missing rollback plan for: net.toggle_wifi
```

**Fix:** Implement rollback plan in `core/rollback/network.py`.

---

### 9. Mutation Surface Locked

**Rule:** Only explicitly allowlisted mutation routes are permitted.

**Allowed Routes:**
- `/api/actions/execute`
- `/api/actions/confirm`
- `/api/auth/first-run/create-owner`
- `/api/auth/login`, `/api/auth/refresh`, `/api/auth/logout`
- `/api/auth/password/change`

**Implementation:**
- Test: `test_no_mutation_routes_outside_allowlist()`

**Failure Mode:**
```
Unexpected mutation routes:
  panel/api/routers/dangerous.py:42 POST /api/dangerous/action
```

**Fix:** Remove route or use Actions API.

---

### 10. No Adapter Direct Imports in Routers

**Rule:** Routers must not import `adapters.*` directly (bypasses Actions API).

**Implementation:**
- Test: `test_no_adapter_imports_in_routers()`

**Failure Mode:**
```
Adapters imported in routers:
  /panel/api/routers/bad_router.py
```

**Fix:** Remove adapter imports, use Actions API.

---

## Negative Regression Tests

These tests **simulate** security violations to verify CI catches them:

- `test_ci_detects_missing_handler()` - Verifies detection of missing handlers
- `test_ci_detects_orphaned_handler()` - Verifies orphan detection
- `test_ci_detects_signature_mismatch()` - Verifies signature validation
- `test_ci_detects_unlisted_mutation_route()` - Verifies route allowlist
- `test_confirmation_bypass_impossible()` - Verifies confirmation enforcement

All negative tests should **PASS** (the test passes by verifying the protection works).

---

## Shell Ban Enforcement

**Forbidden Patterns:**
- `shell=True`
- `import pty`
- `os.system`
- `os.exec*`

**CI Checks:**
```bash
grep -r "shell=True" panel/ agent/ || exit 0
grep -r "import pty" panel/ agent/ || exit 0
```

Any match causes CI failure.

---

## Test Files (Source of Truth)

| File | Purpose |
|------|---------|
| `panel/api/tests/test_ci_invariants.py` | 10 invariant tests |
| `panel/api/tests/test_negative_invariants.py` | 11 regression simulation tests |
| `panel/api/tests/test_security_invariants.py` | Additional security rules |
| `panel/api/tests/test_no_shell_surface.py` | Shell ban verification |
| `panel/api/tests/invariant_helpers.py` | Reusable validation utilities |
| `agent/tests/test_security.py` | Agent-side policy enforcement |

---

## CI Jobs (GitHub Actions)

1. **unit-tests** - Fast tests (`-m "not invariant"`)
2. **security-invariants** - Invariant tests (`-m invariant`) + shell ban
3. **agent-tests** - Agent security tests
4. **negative-tests** - Regression simulation tests
5. **docs-sync** - Documentation completeness check

**All jobs must pass before merge.**

---

## How to Run Locally

```bash
# All invariant tests
cd panel/api
python -m pytest -m invariant -v

# Negative tests
python -m pytest tests/test_negative_invariants.py -v

# Shell ban check
grep -r "shell=True" panel/ agent/ && echo "FAIL" || echo "PASS"

# Agent tests
cd agent
python -m pytest tests/ -v
```

---

## Why This Is Strict

The system is designed with:
- **Deny-by-default** - Unknown actions/handlers/params are rejected
- **Single entrypoint** - All mutations through Actions API
- **Zero trust** - Future contributors assumed careless

Any accidental widening is a **security regression** and must fail CI immediately.

---

## Failure Remediation Guide

| Error | Root Cause | Fix |
|-------|-----------|-----|
| Missing handler | Registry references non-existent function | Add function to `handlers.py` |
| Orphaned handler | Function exists without registry entry | Add to registry or delete function |
| Signature mismatch | Handler params don't match schema | Update handler signature |
| Unlisted mutation route | New POST/PUT/DELETE outside allowlist | Use Actions API or update allowlist |
| Adapter in router | Router imports adapters directly | Remove import, use Actions API |
| Missing from agent | Panel action not in agent registry | Add to `agent/policy/registry.yaml` |

---

## Version History

- **v2.0** (2025-12-20): Added bijection tests, signature validation, negative tests, GitHub Actions
- **v1.0** (Initial): Basic invariant enforcement
