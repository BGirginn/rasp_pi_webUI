# CONTRIBUTING.md
Security‑grade contribution rules for the Action Registry control plane.

## Non‑Negotiables
- Do not add new mutation endpoints. All mutations must go through the Actions API.
- Do not add raw shell/exec/terminal functionality.
- Do not bypass RBAC, guards, schema validation, or audit.
- Do not weaken agent deny‑by‑default enforcement.

## Adding or Changing an Action (Required Steps)
1) **Panel registry**
   - Add/modify the action in `panel/api/core/actions/registry.yaml`.
2) **Panel handler**
   - Add/modify handler in `panel/api/core/actions/handlers.py`.
   - Ensure handler signature matches `params_schema`.
3) **Agent registry**
   - Mirror action ID in `agent/policy/registry.yaml` (CI enforced).
4) **Rollback**
   - If `rollback.supported + auto`, ensure a rollback plan exists in `core/rollback/*`.
5) **Tests**
   - Update/extend invariant tests if action adds new schema or behavior.
   - Run `pytest -m invariant` before opening a PR.

## Mutation Endpoint Rules
Mutation routes are strictly allowlisted in `panel/api/tests/test_ci_invariants.py`.
If you add a new mutation route, CI will fail. The correct fix is to use the Actions API.

## Adapter Usage Rules
Routers must not import or call `adapters.*` directly. This is enforced by CI.
Only Action handlers and rollback logic may use adapters.

## CI Expectations
- Unit tests: `python -m pytest -m "not invariant"`
- Invariants: `python -m pytest -m invariant`
- CI must be green before merge.

---

## How to Add an Action Safely

### Step-by-Step Guide

#### 1. Update Panel Registry
**File:** `panel/api/core/actions/registry.yaml`

Add your action:
```yaml
- id: category.action_name
  title: "Human Readable Title"
  category: category
  risk: low|medium|high
  roles_allowed: [viewer, operator, admin, owner]
  handler: handler.category.action_name
  params_schema:
    param_name:
      type: string|integer|boolean|array
      # Add validation as needed
  requires_confirmation: false  # Set true for dangerous actions
  cooldown_seconds: 0  # Time between executions
```

#### 2. Create Handler Function
**File:** `panel/api/core/actions/handlers.py`

```python
async def handler_category_action_name(param_name: str) -> dict:
    """Brief description."""
    # Call adapter, never call subprocess directly
    result = await adapter_module.function(param_name)
    return result
```

**CRITICAL:** Handler function name MUST match registry handler string with dots replaced by underscores.

#### 3. Add to HANDLERS Dict
**File:** `panel/api/core/actions/handlers.py` (bottom of file)

```python
HANDLERS = {
   ...
    "handler.category.action_name": handler_category_action_name,
}
```

#### 4. Update Agent Registry
**File:** `agent/policy/registry.yaml`

Mirror the action (CI enforced):
```yaml
- id: category.action_name
  params_schema:
    param_name:
      type: string
  confirm_required: false  # Match panel if applicable
```

#### 5. Add Rollback Plan (if needed)
If `rollback.supported: true` and `rollback.auto: true`:

**File:** `panel/api/core/rollback/network.py` or create new module

Implement rollback logic in `determine_rollback_plan()`.

#### 6. Run Tests
```bash
# Run all invariant tests
cd panel/api
python -m pytest -m invariant -v

# Run agent tests
cd ../../agent
python -m pytest tests/ -v
```

**Expected:** All tests pass, no new failures.

#### 7. Verify No Orphans
```bash
cd panel/api
python -m pytest tests/test_ci_invariants.py::test_no_orphaned_handlers -v
python -m pytest tests/test_ci_invariants.py::test_handler_map_complete -v
```

---

## Handler Signature Requirements

### Match Schema Exactly

**Registry Schema:**
```yaml
params_schema:
  service: { type: string }
  force: { type: boolean, default: false }
```

**Handler Signature:**
```python
async def handler_svc_action(service: str, force: bool = False) -> dict:
    pass
```

### Required vs Optional

- Schema params without `default` → Handler required params
- Schema params with `default` → Handler optional params (with default)

### Type Mapping

| Schema Type | Python Type |
|-------------|-------------|
| string      | str         |
| integer     | int         |
| number      | float       |
| boolean     | bool        |
| array       | list        |
| object      | dict        |

---

## Common CI Failures and Fixes

### "Handler not in HANDLERS dict"
**Fix:** Add entry to `HANDLERS` dict at bottom of `handlers.py`.

### "Orphaned handler function"
**Fix:** Either add action to registry or delete the function.

### "Panel action missing from agent registry"
**Fix:** Add action to `agent/policy/registry.yaml` with same ID.

### "Signature mismatch"
**Fix:** Update handler function signature to match `params_schema`.

### "Unlisted mutation route"
**Fix:** Don't create new mutation endpoints. Use `/api/actions/execute`.

---

## Pre-Commit Checklist

Before opening a PR:

- [ ] Handler function name matches registry (dots → underscores)
- [ ] Handler in `HANDLERS` dict
- [ ] Action in agent registry
- [ ] Signature matches schema
- [ ] All invariant tests pass locally
- [ ] No `shell=True` or direct subprocess calls
- [ ] Rollback plan if `rollback.auto: true`
- [ ] Documentation updated if adding new category
