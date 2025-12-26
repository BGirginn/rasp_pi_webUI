# Threat Model - Pi Control Panel (AR-First)

## Overview

This system is an Action Registry (AR)-first control plane. All state mutation
flows through the Action Engine using `action_id + params`. Terminal/raw shell
execution is not part of the product surface.

## System Architecture (High-Level)

```
Browser/UI
   |
   v
Panel API (FastAPI)
   |
   v
Action Engine -> Registry -> Handlers -> Adapters -> Agent RPC
   |
   v
SQLite (audit, rollback_jobs, settings)
```

## Threat Categories and Mitigations

### 1) Authentication and Authorization
- Threat: brute force logins.
  Mitigation: rate limits, short access token TTL, refresh tokens.
- Threat: privilege escalation.
  Mitigation: RBAC enforced in Action Engine (deny-by-default).

### 2) Action Registry Integrity
- Threat: registry tampering to allow unsafe actions.
  Mitigation: registry is loaded at startup and must validate; static handler map.
- Threat: handler string mismatch.
  Mitigation: tests enforce registry-to-handler coverage.

### 3) Parameter Validation and Allowlists
- Threat: unknown or unsafe params.
  Mitigation: strict schema validation with allowlist_ref resolution.
- Threat: hidden mutation parameters.
  Mitigation: unknown params rejected; handler signatures checked in tests.

### 4) Network Lockout
- Threat: network changes cut off access.
  Mitigation: rollback job scheduling; confirm endpoint cancels rollback.

### 5) Audit and Masking
- Threat: loss of forensic trace or secret leakage.
  Mitigation: audit log is mandatory; sensitive fields are masked.

### 6) Legacy Endpoint Surface
- Threat: bypassing the Action Engine via older routes.
  Mitigation: legacy mutation endpoints return 410 and are slated for removal.

### 7) Panel -> Agent Trust Boundary
- Threat: if panel is compromised, agent may execute unsafe calls.
  Mitigation (planned): add agent-side allowlists and request authentication.

## Incident Response (Operational)

If compromise is suspected:
1) Rotate JWT secret (invalidates sessions).
2) Review audit logs for suspicious actions.
3) Disable network mutations until verified.

## Review Schedule

- Quarterly threat model review
- Post-incident review within 48 hours

Last Updated: 2025-02-15
