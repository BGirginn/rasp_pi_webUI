# CI_INVARIANTS.md
Version: 1.0
Scope: Hard CI gates enforcing security invariants and drift detection.

## Enforced Invariants (Fail CI)
1) Registry ↔ handler bijection (Panel)
   - Every registry action must reference a handler in `HANDLERS`.
   - Every handler in `HANDLERS` must be referenced by the registry.
   - Failure mode: CI fails with missing/extra handler list.

2) Panel registry ⊆ Agent registry
   - All panel action IDs must exist in `agent/policy/registry.yaml`.
   - Prevents panel-only actions from bypassing agent policy.
   - Failure mode: CI lists missing action IDs.

3) Schema ↔ handler signature compatibility
   - Handler must accept all schema keys (or **kwargs).
   - Handler must not require params not present in schema.
   - Failure mode: CI lists missing or extra parameters.

4) Confirm-required actions cannot bypass confirmation
   - Any action with `requires_confirmation: true` must raise when `confirm=false`.
   - Failure mode: CI fails if guard does not raise.

5) Rollback-required actions must have a rollback plan
   - Any action with `rollback.supported: true` and `rollback.auto: true` must return a rollback plan.
   - Failure mode: CI lists missing rollback plan action IDs.

6) Mutation surface does not drift
   - Only an explicit allowlist of mutation routes is permitted.
   - No new `POST/PUT/PATCH/DELETE` routes outside the allowlist.
   - Failure mode: CI lists unexpected routes with file/line.

7) Router code must not call adapters directly
   - Prevents bypassing the Actions API.
   - Failure mode: CI lists router files importing adapters.

## Test Files (Source of Truth)
- `panel/api/tests/test_security_invariants.py`
- `panel/api/tests/test_ci_invariants.py`
- `panel/api/tests/test_no_shell_surface.py`
- `agent/tests/test_security.py`
- `agent/tests/test_mtls.py`

## CI Jobs
- Unit tests: `pytest -m "not invariant"`
- Invariants: `pytest -m invariant`

## Why This Is Strict
The system is designed with deny‑by‑default and single‑entrypoint mutation.
Any accidental widening is a security regression and must fail CI immediately.
