# PLAN.md — rasp_pi_webUI → Product-Grade Action Registry Platform (AR-First Refactor)
Repo: BGirginn/rasp_pi_webUI  
Goal: Convert existing working code into a **commercial-grade**, **secure-by-default**, **Action Registry (AR) driven** control plane.  
Language: This plan is written so Cursor/AI can execute **exactly** step-by-step.

---

## 0) ABSOLUTE RULES (NON-NEGOTIABLE)
These rules are enforced throughout refactor. If any existing feature violates them, it is removed or rewritten.

### R0.1 — No raw shell / no terminal
Remove **all** of these from product surface (API + UI):
- `panel/api/routers/terminal.py`
- `panel/api/services/host_exec.py`
- UI: `panel/ui/src/pages/Terminal.jsx`
- Any `pty`, `os.exec*`, `shell=True`, arbitrary command endpoints

### R0.2 — No command-based API
After refactor, **no endpoint** may accept a free-form command string (or similar).
All privileged operations must be called as:
- `action_id` + validated `params` (defined in AR)

### R0.3 — Allowlist everything that can mutate state
Targets must be allowlisted:
- systemd service names
- mount points
- network profiles
- docker operations (by container id only; never by arbitrary command)

### R0.4 — Timed rollback for network-changing actions
Any action that can cut connectivity MUST:
- auto-rollback if not confirmed
- never permanently lock users out

### R0.5 — Audit is mandatory and cannot be bypassed
Every action attempt is logged:
- who, role, what action, params (masked), result, duration

### R0.6 — No “invent new product”
You may create plumbing (AR/engine/adapters), but you may not add new product features.

---

## 1) CURRENT REPO FACTS (READ THIS BEFORE CHANGING ANYTHING)
### Backend (Panel API)
Paths:
- `panel/api/main.py` (FastAPI app)
- `panel/api/routers/*` (endpoints)
- `panel/api/services/agent_client.py` (agent RPC client)
- `panel/api/services/host_exec.py` (DANGEROUS: raw shell)
- `panel/api/routers/terminal.py` (DANGEROUS: PTY/exec)
- `panel/api/db/migrations.py` (SQLite schema, includes default admin migration)

### Agent
Paths:
- `agent/rpc/socket_server.py`
- `agent/providers/*` (systemd/network/docker/devices)
- `agent/telemetry/collector.py`

### UI
- React/Vite: `panel/ui/*`
- Pages: `panel/ui/src/pages/*` including `Terminal.jsx` (remove)

---

## 2) TARGET ARCHITECTURE (FINAL FILE TREE)
You will create these directories/files. Do NOT “approximate”; create exactly.

### 2.1 Panel API (new structure inside `panel/api/`)
Create new top-level packages:
- `panel/api/core/`
- `panel/api/adapters/`
- `panel/api/api/`

Final structure:

panel/api/
  core/
    actions/
      __init__.py
      registry.yaml
      loader.py
      validate.py
      guards.py
      engine.py
      handlers.py
    auth/
      __init__.py
      rbac.py
      masking.py
      first_run.py
    audit/
      __init__.py
      writer.py
      models.py
    rollback/
      __init__.py
      network.py
  adapters/
    __init__.py
    agent_rpc.py
    systemd.py
    network.py
    power.py
    logs.py
    docker.py
    storage.py
    devices.py
    jobs.py
  api/
    __init__.py
    deps.py
    routers/
      __init__.py
      actions.py
      observability.py
      audit.py
      auth.py
      health.py
  db/
    __init__.py
    migrations.py   (edited)
  main.py           (edited: app wiring)
  config.py         (edited if needed)
  tests/
    (new tests added; existing updated)

---

## 3) AR CONTENT — CREATE `panel/api/core/actions/registry.yaml` (EXACT)
Copy-paste this file exactly. This is the Product Constitution.

version: 1
defaults:
  audit: true
  cooldown_seconds: 2
  requires_confirmation: false
  rollback:
    supported: false
    auto: false
    timeout_seconds: null

roles:
  viewer:   { description: "Read-only" }
  operator: { description: "Safe operations" }
  admin:    { description: "Configuration + lifecycle" }
  owner:    { description: "Emergency recovery actions (still no raw shell)" }

targets:
  services_allowlist:
    - ssh
    - tailscaled
    - docker
    - mosquitto
    - pi-agent
    - caddy
    - panel-api

  network_profiles:
    - primary

  storage_mount_points:
    - /mnt/external

actions:

  # -------------------------
  # OBSERVABILITY (READ ONLY)
  # -------------------------
  - id: obs.get_system_status
    title: "System Status"
    category: observability
    risk: low
    roles_allowed: [viewer, operator, admin, owner]
    handler: handler.obs.get_system_status
    params_schema: {}

  - id: obs.get_metrics_snapshot
    title: "Metrics Snapshot"
    category: observability
    risk: low
    roles_allowed: [viewer, operator, admin, owner]
    handler: handler.obs.get_metrics_snapshot
    params_schema:
      include:
        type: array
        items: { type: string }
        default: ["cpu","mem","disk","net","temp"]

  - id: obs.get_logs
    title: "View Logs"
    category: observability
    risk: low
    roles_allowed: [viewer, operator, admin, owner]
    handler: handler.obs.get_logs
    params_schema:
      source:
        type: string
        enum: ["system","service","panel","agent"]
      service:
        type: string
        nullable: true
      limit:
        type: integer
        minimum: 50
        maximum: 2000
        default: 400

  # -------------------------
  # POWER
  # -------------------------
  - id: power.reboot_safe
    title: "Reboot"
    category: power
    risk: medium
    roles_allowed: [operator, admin, owner]
    handler: handler.power.reboot_safe
    requires_confirmation: true
    cooldown_seconds: 10
    params_schema: {}

  - id: power.shutdown_safe
    title: "Shutdown"
    category: power
    risk: medium
    roles_allowed: [operator, admin, owner]
    handler: handler.power.shutdown_safe
    requires_confirmation: true
    cooldown_seconds: 10
    params_schema: {}

  # -------------------------
  # SERVICES (SYSTEMD)
  # -------------------------
  - id: svc.restart
    title: "Restart Service"
    category: services
    risk: medium
    roles_allowed: [operator, admin, owner]
    handler: handler.svc.restart
    params_schema:
      service:
        type: string
        allowlist_ref: services_allowlist

  - id: svc.start
    title: "Start Service"
    category: services
    risk: medium
    roles_allowed: [admin, owner]
    handler: handler.svc.start
    params_schema:
      service:
        type: string
        allowlist_ref: services_allowlist

  - id: svc.stop
    title: "Stop Service"
    category: services
    risk: medium
    roles_allowed: [admin, owner]
    handler: handler.svc.stop
    params_schema:
      service:
        type: string
        allowlist_ref: services_allowlist
    requires_confirmation: true

  - id: svc.enable
    title: "Enable Service"
    category: services
    risk: medium
    roles_allowed: [admin, owner]
    handler: handler.svc.enable
    params_schema:
      service:
        type: string
        allowlist_ref: services_allowlist
    requires_confirmation: true

  - id: svc.disable
    title: "Disable Service"
    category: services
    risk: high
    roles_allowed: [owner]
    handler: handler.svc.disable
    params_schema:
      service:
        type: string
        allowlist_ref: services_allowlist
    requires_confirmation: true
    cooldown_seconds: 60

  # -------------------------
  # NETWORK (ROLLBACK REQUIRED)
  # -------------------------
  - id: net.toggle_wifi
    title: "Toggle Wi-Fi"
    category: network
    risk: medium
    roles_allowed: [admin, owner]
    handler: handler.net.toggle_wifi
    params_schema:
      enabled: { type: boolean }
    rollback:
      supported: true
      auto: true
      timeout_seconds: 30
    requires_confirmation: true

  - id: net.reset_safe
    title: "Safe Network Reset"
    category: network
    risk: high
    roles_allowed: [owner]
    handler: handler.net.reset_safe
    params_schema:
      profile: { type: string, enum: ["primary"] }
    rollback:
      supported: true
      auto: true
      timeout_seconds: 60
    requires_confirmation: true
    cooldown_seconds: 60

  - id: net.tailscale.enable
    title: "Enable Tailscale"
    category: network
    risk: medium
    roles_allowed: [admin, owner]
    handler: handler.net.tailscale_enable
    params_schema: {}

  - id: net.tailscale.disable
    title: "Disable Tailscale"
    category: network
    risk: high
    roles_allowed: [owner]
    handler: handler.net.tailscale_disable
    params_schema: {}
    requires_confirmation: true
    cooldown_seconds: 60

  # -------------------------
  # DOCKER
  # -------------------------
  - id: docker.list
    title: "List Containers"
    category: docker
    risk: low
    roles_allowed: [viewer, operator, admin, owner]
    handler: handler.docker.list
    params_schema: {}

  - id: docker.restart_container
    title: "Restart Container"
    category: docker
    risk: medium
    roles_allowed: [admin, owner]
    handler: handler.docker.restart_container
    params_schema:
      container_id: { type: string }

  - id: docker.stop_container
    title: "Stop Container"
    category: docker
    risk: medium
    roles_allowed: [admin, owner]
    handler: handler.docker.stop_container
    params_schema:
      container_id: { type: string }
    requires_confirmation: true

  # -------------------------
  # STORAGE (GUIDED ONLY)
  # -------------------------
  - id: storage.mount_external
    title: "Mount External Disk"
    category: storage
    risk: medium
    roles_allowed: [admin, owner]
    handler: handler.storage.mount_external
    params_schema:
      mount_point:
        type: string
        allowlist_ref: storage_mount_points
      device_hint:
        type: string
    requires_confirmation: true

  - id: storage.unmount_external
    title: "Unmount External Disk"
    category: storage
    risk: medium
    roles_allowed: [admin, owner]
    handler: handler.storage.unmount_external
    params_schema:
      mount_point:
        type: string
        allowlist_ref: storage_mount_points
    requires_confirmation: true

  # -------------------------
  # AUTH (PRODUCT HARDENING)
  # -------------------------
  - id: auth.create_user
    title: "Create User"
    category: auth
    risk: medium
    roles_allowed: [owner]
    handler: handler.auth.create_user
    params_schema:
      username: { type: string, minLength: 3, maxLength: 32 }
      role: { type: string, enum: ["viewer","operator","admin"] }
      temporary_password: { type: string, minLength: 12, maxLength: 128 }
    requires_confirmation: true

  - id: auth.rotate_jwt_secret
    title: "Rotate JWT Secret"
    category: auth
    risk: high
    roles_allowed: [owner]
    handler: handler.auth.rotate_jwt_secret
    params_schema: {}
    requires_confirmation: true
    cooldown_seconds: 300

  # -------------------------
  # UPDATES
  # -------------------------
  - id: update.check
    title: "Check Updates"
    category: updates
    risk: low
    roles_allowed: [admin, owner]
    handler: handler.update.check
    params_schema: {}

  - id: update.apply
    title: "Apply Update"
    category: updates
    risk: high
    roles_allowed: [owner]
    handler: handler.update.apply
    params_schema:
      channel: { type: string, enum: ["stable"] }
      backup_before: { type: boolean, default: true }
    requires_confirmation: true
    cooldown_seconds: 300

  # -------------------------
  # EMERGENCY
  # -------------------------
  - id: emergency.rollback_last_network_change
    title: "Rollback Last Network Change"
    category: emergency
    risk: high
    roles_allowed: [owner]
    handler: handler.emergency.rollback_last_network_change
    params_schema: {}
    requires_confirmation: true

  - id: emergency.safe_mode_enable
    title: "Enable Safe Mode"
    category: emergency
    risk: high
    roles_allowed: [owner]
    handler: handler.emergency.safe_mode_enable
    params_schema: {}
    requires_confirmation: true

---

## 4) TASK EXECUTION MODEL (HOW CURSOR MUST WORK)
Cursor must execute tasks strictly in order:
- Complete Task N fully (code + tests + manual run) before Task N+1.
- After each task: run exact checks listed in “Verification”.
- If tests fail: fix, rerun, until pass.

---

# TASK LIST (EXACT, NO GENERALITIES)
Each task includes: Files to create/modify/delete, exact code edits, and verification commands.

---

## TASK 01 — REMOVE TERMINAL + RAW EXEC (SAFETY FREEZE)
### Delete (remove files completely)
- `panel/api/routers/terminal.py`
- `panel/api/services/host_exec.py`

### Modify
1) `panel/api/routers/__init__.py`
- Remove `"terminal"` from `ROUTERS` list / exports if present.

2) `panel/api/main.py`
- Remove terminal router include.
- Remove any imports referencing terminal router.

3) `panel/ui/src/pages/Terminal.jsx`
- Delete the file.

4) `panel/ui/src/App.jsx` (or router file used by UI)
- Remove route/menu entry pointing to Terminal page.

### Add “hard failure” guard
Create file: `panel/api/core/auth/first_run.py` (empty stub for now) — required later.

### Verification (run all)
- `grep -R "shell=True" -n panel/api || true` → must output nothing
- `grep -R "pty.fork" -n panel/api || true` → must output nothing
- `grep -R "execvp" -n panel/api || true` → must output nothing
- `pytest -q panel/api/tests` → must pass
- `npm -C panel/ui install && npm -C panel/ui run build` → must succeed

---

## TASK 02 — CREATE NEW CORE DIRECTORY STRUCTURE (NO LOGIC YET)
### Create directories
- `panel/api/core/actions`
- `panel/api/core/auth`
- `panel/api/core/audit`
- `panel/api/core/rollback`
- `panel/api/adapters`
- `panel/api/api`
- `panel/api/api/routers`

### Create files (empty but importable)
Add `__init__.py` to each new package folder.

### Verification
- `python -c "import panel.api.core"` (or correct import root based on repo packaging) must not error
- `pytest -q panel/api/tests` must pass

---

## TASK 03 — ADD AR LOADER (registry.yaml → python object)
### Create files
1) `panel/api/core/actions/loader.py`
Implement:
- `load_registry(path: str) -> dict`
- Validate:
  - `version` exists and equals 1
  - action `id` unique
  - `roles_allowed` non-empty
  - `handler` is non-empty string
- Store parsed registry in module-level cache:
  - `_REGISTRY_CACHE: dict | None`

Add function:
- `get_registry() -> dict` (loads once, then returns cache)

2) `panel/api/core/actions/registry.yaml`
Use exact content from Section 3.

### Modify
`panel/api/main.py`
- On app startup, call `get_registry()` once.
- If invalid, raise exception and app refuses to start.

### Verification
- `python -c "from panel.api.core.actions.loader import get_registry; print(get_registry()['version'])"` prints `1`

---

## TASK 04 — RBAC GATE (ROLE vs ACTION)
### Create file
`panel/api/core/auth/rbac.py`
Implement:
- `is_role_allowed(registry: dict, role: str, action_id: str) -> bool`
- `assert_role_allowed(registry: dict, role: str, action_id: str) -> None` (raise HTTP 403)

Rules:
- Deny by default if unknown action_id or unknown role.

### Modify
`panel/api/routers/auth.py`
- Extend user roles to include `"owner"` in code paths (NOT DB yet).
- Keep current tokens, but allow `"owner"` as role string.

### Add tests
Create `panel/api/tests/test_rbac_actions.py`:
- Load registry
- Assert viewer cannot run `svc.start`
- Assert operator can run `svc.restart`
- Assert admin cannot run `svc.disable`
- Assert owner can run `svc.disable`

### Verification
- `pytest -q panel/api/tests/test_rbac_actions.py` passes

---

## TASK 05 — PARAM VALIDATION (NO HANDLERS YET)
### Create file
`panel/api/core/actions/validate.py`

Implement:
- `validate_params(registry: dict, action_id: str, params: dict) -> dict`
Returns sanitized/validated params.

Validation rules (must implement all):
- If schema is `{}`: params must be `{}` or `None` (normalize to `{}`).
- Supported schema keys:
  - `type`: string|integer|number|boolean|array
  - `enum`: allowed values
  - `default`: default value if param missing
  - `minimum`/`maximum`
  - `nullable`: allow null
  - `items` for arrays
  - `allowlist_ref` → resolve `registry['targets'][name]`
  - `minLength`/`maxLength` for strings
- Unknown param keys in request must raise 400.

### Add tests
Create `panel/api/tests/test_action_validation.py`:
- `svc.restart` with service not in allowlist → 400
- `obs.get_logs` with source not in enum → 400
- `obs.get_metrics_snapshot` with no include → defaults applied
- unknown param on any action → 400

### Verification
- `pytest -q panel/api/tests/test_action_validation.py` passes

---

## TASK 06 — AUDIT WRITER (DB INSERT, PARAM MASKING)
### Create files
1) `panel/api/core/auth/masking.py`
Implement:
- `mask_params(action_id: str, params: dict) -> dict`
Rules:
- If action_id starts with `auth.` then mask:
  - `temporary_password` → `"***"`
- If action_id == `auth.rotate_jwt_secret` → params empty anyway

2) `panel/api/core/audit/models.py`
Define typed dict / pydantic model:
- `AuditEvent` with fields:
  - user_id, username, role
  - action_id
  - params_masked
  - status ("success"/"fail")
  - error (nullable)
  - duration_ms (int)
  - created_at (UTC)

3) `panel/api/core/audit/writer.py`
Implement:
- `write_audit(db, event: AuditEvent) -> None`
Write to existing table `audit_log`:
- action text: use `action_id`
- details: JSON string of masked params + status + duration

### Modify DB access layer
Find existing `get_control_db()` usage (likely in `panel/api/db/__init__.py` or routers).
Expose a single import path: `from db import get_control_db` (keep current behavior).

### Verification
- Add minimal test that inserts audit row to in-memory db if tests use that pattern, or assert writer calls execute.

---

## TASK 07 — GUARDS (CONFIRMATION + COOLDOWN)
### Create file
`panel/api/core/actions/guards.py`

Implement:
- `requires_confirmation(registry, action_id) -> bool`
- `check_cooldown(db, user_id, action_id, cooldown_seconds) -> None`
  - Query `audit_log` for most recent same action by same user
  - If within cooldown → raise 429

Confirmation model (Phase 1 simple, exact):
- For now, accept request field: `confirm: bool`
- If `requires_confirmation==true` and confirm != true → raise 400

(Phase 2 can implement 2-step confirmation token, but not now.)

### Add tests
Create `panel/api/tests/test_guards.py`:
- action requiring confirmation without confirm flag → 400
- cooldown: insert audit row now, call again immediately → 429

---

## TASK 08 — ADAPTER LAYER (REUSE EXISTING agent_client, DO NOT BREAK IT)
### Create file
`panel/api/adapters/agent_rpc.py`

Implementation rule:
- DO NOT rewrite socket protocol.
- Import and reuse existing: `panel/api/services/agent_client.py`
- Provide a thin wrapper class `AgentRPC` exposing methods used by handlers:
  - `get_system_info()`
  - `get_snapshot()`
  - `get_network_interfaces()`
  - `toggle_wifi(enabled: bool)` (map to existing client method)
  - `resource_action(resource_id, action, params)`
  - docker listing if exists via resource actions or existing RPC methods

Instantiate singleton:
- `agent_rpc = AgentRPC()`

### Create these adapter files (thin wrappers)
- `panel/api/adapters/systemd.py`
- `panel/api/adapters/network.py`
- `panel/api/adapters/power.py`
- `panel/api/adapters/logs.py`
- `panel/api/adapters/docker.py`
- `panel/api/adapters/storage.py`

Each adapter must:
- accept only validated params (already validated by engine)
- call agent_rpc or existing safe router logic
- never call subprocess directly

---

## TASK 09 — HANDLERS (MAP AR handler strings → adapter calls)
### Create file
`panel/api/core/actions/handlers.py`

Implement handler functions grouped by namespace (exact names must match registry handler strings):
- class-like namespaces can be plain objects/dicts, but simplest: define functions and a dispatch map.

Required handler functions (exact):
- `handler.obs.get_system_status`
- `handler.obs.get_metrics_snapshot`
- `handler.obs.get_logs`
- `handler.power.reboot_safe`
- `handler.power.shutdown_safe`
- `handler.svc.restart`
- `handler.svc.start`
- `handler.svc.stop`
- `handler.svc.enable`
- `handler.svc.disable`
- `handler.net.toggle_wifi`
- `handler.net.reset_safe`
- `handler.net.tailscale_enable`
- `handler.net.tailscale_disable`
- `handler.docker.list`
- `handler.docker.restart_container`
- `handler.docker.stop_container`
- `handler.storage.mount_external`
- `handler.storage.unmount_external`
- `handler.auth.create_user`
- `handler.auth.rotate_jwt_secret`
- `handler.update.check`
- `handler.update.apply`
- `handler.emergency.rollback_last_network_change`
- `handler.emergency.safe_mode_enable`

Implementation rules:
- If an exact behavior does not exist in current code, create a TODO and return a safe failure response:
  - `{"success": false, "message": "TODO: not implemented yet"}`
- DO NOT invent risky behavior.

---

## TASK 10 — ACTION ENGINE (THE ONLY MUTATION ENTRYPOINT)
### Create file
`panel/api/core/actions/engine.py`

Implement:
`async def execute_action(*, db, user: dict, action_id: str, params: dict | None, confirm: bool=False) -> dict`

Exact execution order:
1) `registry = get_registry()`
2) `assert_role_allowed(registry, user["role"], action_id)`
3) `validated = validate_params(registry, action_id, params or {})`
4) guard checks:
   - confirmation
   - cooldown
5) dispatch handler:
   - use a static dict map `HANDLERS: dict[str, callable]`
   - key: registry action `handler` string
6) measure duration
7) write audit (success/fail)
8) return handler result (or standardized error)

Standard error response:
- `{"success": False, "error": "<code>", "message": "<human readable>"}`

---

## TASK 11 — NEW ACTIONS API (REPLACES MUTATION ROUTES)
### Create file
`panel/api/api/routers/actions.py`

Endpoints (exact):
1) `GET /api/actions`
Response:
- list of actions user is allowed to execute
- include fields: id, title, category, risk, requires_confirmation, params_schema (sanitized), cooldown_seconds

2) `POST /api/actions/execute`
Request JSON:
- `action_id: str`
- `params: dict` (optional)
- `confirm: bool` (optional)

Call `execute_action()` from engine.

### Create deps
`panel/api/api/deps.py`
- Import existing `get_current_user` from `panel/api/routers/auth.py`
- Expose dependency `current_user = Depends(get_current_user)`

### Modify `panel/api/main.py`
- Mount new router under `/api`
- Keep old routers for now (compat layer), but mutation endpoints will be redirected later.

---

## TASK 12 — COMPAT LAYER (OLD ENDPOINTS MUST CALL ENGINE OR BECOME READ-ONLY)
We will not break UI on day 1. We will gradually reroute.

### Modify these existing routers to call engine:
1) `panel/api/routers/system.py`
- `/reboot` → call `power.reboot_safe`
- `/shutdown` → call `power.shutdown_safe`
- `/update` → call `update.apply` (owner only; if current UI expects admin, temporarily return 403)

2) `panel/api/routers/network.py`
- `/wifi/toggle` → call `net.toggle_wifi`
- Any destructive network action must route to `net.reset_safe` or be removed.

3) `panel/api/routers/resources.py`
- `POST /{resource_id}/action` becomes:
  - translate known resource actions to AR actions when possible
  - otherwise return 400 "Deprecated: use /api/actions/execute"
- DO NOT call `agent_client.execute_action` (it doesn’t exist). Fix by routing through AR.

4) `panel/api/routers/admin_console.py`
- Remove risky enable/disable endpoints or make them owner-only actions (recommended: remove entirely, because they are policy bypass).

### Verification
- Existing UI pages (except Terminal) should still load
- `/api/actions` works
- `/api/actions/execute` works

---

## TASK 13 — DB MIGRATION: ADD OWNER ROLE + REMOVE DEFAULT ADMIN
You must edit `panel/api/db/migrations.py`.

### 13.1 Remove default admin migration behavior
- Delete or disable `migrate_002_default_admin` execution from migrations list.
- Do NOT create default credentials.

### 13.2 Add new migration `005_owner_role_and_settings`
Create a new migration function:
- `migrate_005_owner_role_and_settings(db)`

It must:
1) Update users role constraint to include owner
   - SQLite cannot alter CHECK easily:
   - Create new table `users_new` with CHECK including ('owner','admin','operator','viewer')
   - Copy rows from old `users` into `users_new`
   - Drop old `users`
   - Rename `users_new` to `users`

2) Create `settings` table if not exists:
   - key TEXT PRIMARY KEY
   - value TEXT
   Use keys:
   - `first_run_complete` ("true"/"false")
   - `jwt_secret_version` (int as string)

3) Set `first_run_complete` to "false" if missing

### Verification
- Fresh DB initializes without printing default admin password
- Existing DB migrates cleanly

---

## TASK 14 — FIRST-RUN OWNER CREATION (NO DEFAULT CREDS)
### Create file
`panel/api/core/auth/first_run.py`

Implement:
- `async def is_first_run(db) -> bool` (reads settings)
- `async def mark_first_run_complete(db) -> None`

### Modify `panel/api/routers/auth.py`
Add endpoint:
- `POST /api/auth/first-run/create-owner`
Request:
- username
- password
Behavior:
- if first_run_complete is true → 409
- else:
  - create user with role "owner"
  - mark first_run_complete true

Also modify existing user creation endpoint behavior:
- Only owner can create users (align with AR: auth.create_user)

---

## TASK 15 — JWT SECRET ROTATION ACTION
### Modify config handling
Find where JWT secret is stored (likely env or config).
Add support:
- secret version in settings table
- rotation increments version and regenerates secret (store in settings table OR env file; choose DB for now)

Implement handler:
- `handler.auth.rotate_jwt_secret`

Also update token verification to accept current secret only (Phase 1).
(Phase 2 could accept previous secret for grace period; not required now.)

---

## TASK 16 — NETWORK ROLLBACK ENGINE (MINIMUM VIABLE)
### Create file
`panel/api/core/rollback/network.py`

Implement:
- `async def schedule_network_rollback(db, user_id, action_id, timeout_seconds, rollback_action_id)`
- Store a rollback job record in DB table `jobs` or create a new `rollback_jobs` table (preferred: new table to avoid mixing semantics)

Minimal behavior:
- After executing `net.toggle_wifi` or `net.reset_safe`:
  - create rollback record with due_time = now + timeout
- Add a background task loop (FastAPI startup) that checks due rollback jobs:
  - if not confirmed, execute rollback action (or safe fallback)

Confirmation mechanism Phase 1:
- Use a new endpoint `POST /api/actions/confirm`
Request:
- `rollback_job_id`
Behavior:
- marks rollback job as confirmed so it won’t rollback

(Yes, this is explicit; implement it.)

---

## TASK 17 — UI: REMOVE TERMINAL, SWITCH MUTATIONS TO `/api/actions/execute`
### Modify UI pages (exact files)
- `panel/ui/src/pages/Services.jsx`
  - Replace direct calls to old endpoints for restart/start/stop with:
    - `POST /api/actions/execute` using action ids:
      - `svc.restart`, `svc.start`, `svc.stop`
  - Populate service dropdown with allowlist from `GET /api/actions` (find schema allowlist_ref and fetch from server OR hardcode list temporarily from backend endpoint `/api/actions` if it returns allowlist values)

- `panel/ui/src/pages/Network.jsx`
  - Replace wifi toggle/connect/disconnect flows:
    - Use `net.toggle_wifi`
    - Keep wifi scanning read-only via existing `/network/wifi/networks` until mapped later

- `panel/ui/src/pages/Dashboard.jsx`
  - Use `obs.get_metrics_snapshot` for snapshot display if feasible

- Delete any leftover references to Terminal menu.

### Verification
- `npm -C panel/ui run build` passes
- Manual: services restart action works via new API

---

## TASK 18 — TESTS: NO SHELL GUARANTEE + ACTION PATH GUARANTEE
### Add tests
Create `panel/api/tests/test_no_shell_surface.py`
- grep codebase during test:
  - assert "shell=True" not present in `panel/api/`
  - assert "pty.fork" not present
  - assert "routers/terminal.py" does not exist

Create `panel/api/tests/test_actions_api.py`
- login (or mock user)
- GET /api/actions returns list filtered by role
- POST /api/actions/execute rejects unknown action_id
- POST /api/actions/execute rejects allowlist violations

---

## TASK 19 — REMOVE / DEPRECATE OLD MUTATION ENDPOINTS (CLEAN PRODUCT SURFACE)
After UI is migrated:
- Remove mutation endpoints or make them wrappers that only call engine and return deprecation warnings:
  - `/system/reboot`, `/system/shutdown`, `/resources/*/action`, `/admin_console/*risky*`

Target end-state:
- Only mutation endpoint in product is:
  - `POST /api/actions/execute`
  - plus rollback confirm endpoint if implemented

---

## TASK 20 — RELEASE CHECKLIST (MUST PASS)
### Security invariants
- No terminal, no raw shell, no host_exec
- All state mutations go through AR+Engine
- RBAC enforced in engine (not UI)
- Audit always logs
- Network rollback exists for wifi toggle/reset

### Commands (must be green)
- `pytest -q panel/api/tests`
- `pytest -q agent/tests`
- `npm -C panel/ui run build`

---

# CURSOR PROMPTS (ONE PER TASK, EXACT)
Use these prompts exactly, in order. Do NOT ask extra questions. Do NOT do multiple tasks at once.

## Prompt for TASK 01
"Implement TASK 01 exactly as written in PLAN.md. Delete terminal and host_exec, remove UI terminal page and route, update imports, then run the verification commands. Fix failures until all checks pass. Do not do any other task."

## Prompt for TASK 02
"Implement TASK 02 exactly as written. Create the directory tree and __init__.py files. Do not add logic. Run verification."

## Prompt for TASK 03
"Implement TASK 03 exactly. Create registry.yaml with the exact content and implement loader.py with caching and validation, wire app startup to fail fast on invalid registry."

## Prompt for TASK 04
"Implement TASK 04 exactly. Add RBAC functions and tests. Ensure deny-by-default."

## Prompt for TASK 05
"Implement TASK 05 exactly. Create validate.py with all specified rules and tests."

## Prompt for TASK 06
"Implement TASK 06 exactly. Add masking and audit writer. Ensure auth params are masked."

## Prompt for TASK 07
"Implement TASK 07 exactly. Create guards.py with confirmation + cooldown and tests."

## Prompt for TASK 08
"Implement TASK 08 exactly. Create adapters that reuse existing services/agent_client without changing protocol."

## Prompt for TASK 09
"Implement TASK 09 exactly. Create handlers.py mapping AR handler strings to adapter calls, leaving TODO safe failures where needed."

## Prompt for TASK 10
"Implement TASK 10 exactly. Build engine.py with strict execution order and audit logging."

## Prompt for TASK 11
"Implement TASK 11 exactly. Create /api/actions and /api/actions/execute endpoints and deps."

## Prompt for TASK 12
"Implement TASK 12 exactly. Modify existing routers to call the action engine or become read-only/deprecated; remove policy bypass."

## Prompt for TASK 13
"Implement TASK 13 exactly. Modify migrations to remove default admin and add owner role + settings table migration."

## Prompt for TASK 14
"Implement TASK 14 exactly. Add first-run owner creation endpoint and logic."

## Prompt for TASK 15
"Implement TASK 15 exactly. Implement JWT secret rotation action and update token validation."

## Prompt for TASK 16
"Implement TASK 16 exactly. Implement minimal network rollback scheduling and confirm endpoint, plus background loop."

## Prompt for TASK 17
"Implement TASK 17 exactly. Update UI pages to use /api/actions/execute for mutations and remove Terminal references."

## Prompt for TASK 18
"Implement TASK 18 exactly. Add tests for no-shell surface and actions API behavior."

## Prompt for TASK 19
"Implement TASK 19 exactly. Remove or fully deprecate old mutation endpoints after UI migration."

## Prompt for TASK 20
"Run TASK 20 release checklist exactly. Fix anything failing until all commands pass."

---

END OF PLAN
