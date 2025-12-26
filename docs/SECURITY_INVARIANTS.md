# Security Invariants - Pi Control Panel (AR-First)

These are non-negotiable security rules for the product.

## Product Surface

1) No terminal, no raw shell, no free-form command execution.
2) All mutations go through `POST /api/actions/execute`.
3) The only additional mutation endpoint allowed is
   `POST /api/actions/confirm` for rollback confirmation.

## Action Registry

1) The registry is the single source of truth for actions.
2) Unknown actions and roles are denied by default.
3) Params are validated strictly; unknown keys are rejected.
4) All allowlist references must exist and be non-empty.

## Guards and Audit

1) Confirmation is required for high-risk actions.
2) Cooldowns are enforced per action and user.
3) Audit logging is mandatory and masks sensitive fields.

## Network Safety

1) Network-changing actions must schedule rollback jobs.
2) Rollback jobs auto-run if not confirmed before timeout.

## First-Run and Updates

1) No default credentials; first-run owner creation is required.
2) Update apply is disabled until a signed update chain exists.
