# Task Report (First-Run Lockdown + Legacy Removal + Agent Trust Model)

## Task 3: First-run endpoint network lockdown
- Added localhost/Tailscale-only gate for the first-run owner creation endpoint.
- Implemented IP allow check (loopback + Tailscale CIDR) with explicit 403 on other sources.
- Kept the existing first-run completion guard intact.
- Files: panel/api/api/routers/auth.py

## Task 2: Legacy endpoint removal (410 shims removed)
- Removed deprecated mutation endpoints that were returning 410 from legacy routers.
- Cleaned related unused helpers/models where they only served those endpoints.
- Routers affected:
  - Authentication: removed legacy user create/delete endpoints.
  - System: removed reboot/shutdown/update endpoints.
  - Network: removed interface action + WiFi/Bluetooth mutation endpoints.
  - Resources: removed resource action/manage/ignore endpoints and legacy mappers.
  - Jobs: removed create/run/cancel/delete endpoints.
  - Manifests: removed create/approve/delete endpoints.
  - Alerts: removed rule CRUD + alert acknowledge/resolve endpoints.
  - Devices: removed USB eject, ESP command/mute, GPIO configure/write endpoints.
  - Telemetry: removed retention cleanup endpoint.
- Files: panel/api/routers/auth.py, panel/api/routers/system.py, panel/api/routers/network.py,
  panel/api/routers/resources.py, panel/api/routers/jobs.py, panel/api/routers/manifests.py,
  panel/api/routers/alerts.py, panel/api/routers/devices.py, panel/api/routers/telemetry.py

## Task 1: Agent-side policy enforcement + Panel↔Agent auth
- Added agent policy registry and schema validation:
  - New registry at agent/policy/registry.yaml with allowlisted RPC actions and params.
  - Validation helper enforces deny-by-default, unknown param rejection, and type checks.
- Added agent-side auth and replay protection:
  - HMAC signature verification with canonical JSON.
  - Issued-at skew checks and nonce replay cache.
- Enforced chain in RPC entrypoint:
  - Envelope parsing + size caps → signature → replay → policy validation → handler dispatch.
  - Structured error codes mapped into JSON-RPC error data.
- Updated Panel→Agent requests:
  - All RPC calls now send signed envelope (action_id, params, requested_by, request_id, issued_at, nonce, signature).
  - Added shared key config in panel settings.
  - Added requested_by propagation in all panel router calls.
- Tests:
  - Added stable signature test on panel side.
  - Added agent security tests for invalid signature, replay, unknown action, invalid params, confirm-required.
- Files: agent/policy/registry.yaml, agent/policy/loader.py, agent/policy/validate.py,
  agent/security/auth.py, agent/security/replay.py, agent/rpc/socket_server.py,
  agent/pi-agent.py, agent/config.yaml, panel/api/services/agent_client.py,
  panel/api/config.py, panel/api/tests/test_agent_signature.py, agent/tests/test_security.py,
  panel/api/routers/* (agent_client call sites updated)

## Tests run
- python3 -m pytest -q panel/api/tests
- python3 -m pytest -q agent/tests
