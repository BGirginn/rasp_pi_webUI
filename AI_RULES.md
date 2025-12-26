# AI_RULES.md — NON-NEGOTIABLE RULESET (MUST OBEY)
This file is a **hard policy contract** for any AI agent (Cursor, Copilot, etc.) working on this repository.
These rules are **mandatory** and must be followed **exactly**. If a request conflicts with these rules, the AI must refuse and stop.

---

## 1) ABSOLUTE BEHAVIOR (YOU MUST DO THIS)
### R1.1 — Execute tasks strictly in order
- Implement **only one TASK at a time** from PLAN.md.
- Do not start TASK N+1 until TASK N is fully complete and verified.

### R1.2 — Do not ask questions unless a blocker exists
- If something is unclear but not blocking, add a `TODO:` comment and continue.
- Only ask when the task cannot proceed without a missing fact.

### R1.3 — Never invent product features
- You may create **plumbing** (AR loader, engine, adapters, tests, wiring).
- You may NOT add new capabilities beyond the Action Registry and PLAN.md.

### R1.4 — Prefer deletion over unsafe preservation
- If a piece of code violates the rules (terminal/shell/free-form execution), remove it.
- Do not “keep it for later”. Product rules have priority.

---

## 2) SECURITY HARD RULES (NEVER BREAK)
### R2.1 — NO raw shell execution (ever)
You must ensure the product contains **zero** of the following:
- `shell=True`
- `pty.*`
- any terminal endpoints
- arbitrary command execution endpoints
- `os.system(...)`
- `subprocess.run(...)` or `Popen(...)` with user-controlled input

If any of these exist, remove or rewrite to Action-based execution.

### R2.2 — NO command-based API
- No endpoint may accept a string like `"cmd"`, `"command"`, `"exec"`, `"script"`.
- All state-changing requests must be `action_id + params` where:
  - action_id exists in AR
  - params are validated by schema
  - RBAC is enforced in the engine

### R2.3 — NO arbitrary file system operations exposed
- Do not expose endpoints to:
  - browse filesystem
  - read arbitrary file paths
  - write arbitrary file paths
  - delete arbitrary file paths
- Storage features must be **guided actions only**.

### R2.4 — NO firmware/bootloader modifications in UI/API
- Do not implement:
  - EEPROM write
  - boot config rewrite
  - kernel flashing
  - device tree injection
from UI/API.

### R2.5 — Network-changing actions must be rollback-safe
- Any action that can break connectivity must:
  - be time-bounded
  - auto-rollback if not confirmed

---

## 3) ARCHITECTURE HARD RULES (NEVER BREAK)
### R3.1 — Single mutation entrypoint
After refactor:
- All mutations must flow through Action Engine.
- The only mutation endpoint should be:
  - `POST /api/actions/execute`
  (plus a confirm endpoint if PLAN requires it.)

### R3.2 — RBAC must be enforced server-side in engine
- UI is not trusted.
- A role check must happen **before** any handler runs.
- Deny-by-default if unknown role or action.

### R3.3 — Allowlist everything that can mutate state
- systemd services must come from allowlist
- mount points must come from allowlist
- network profiles must come from allowlist

### R3.4 — No dynamic imports or eval
- Handler dispatch must use a static mapping.
- No `eval`, no `importlib` tricks to run arbitrary code.

### R3.5 — Agent executes, Panel orchestrates
- Panel API must not execute host commands.
- Execution must be performed by agent providers via RPC.
- The panel is policy, validation, and audit.

---

## 4) AUDIT HARD RULES (NEVER BREAK)
### R4.1 — Every action attempt is audited
Audit must include:
- user_id / username
- role
- action_id
- masked params
- success/fail
- error (if any)
- duration_ms
- timestamp

### R4.2 — Sensitive params must be masked
At minimum:
- `temporary_password` must be `"***"` in logs
- secrets must never be stored in plaintext audit rows

### R4.3 — Audit cannot be disabled
- No flags, no config options to turn it off.

---

## 5) CODE CHANGE DISCIPLINE (YOU MUST DO THIS)
### R5.1 — Minimize unrelated edits
- Only edit files required by the current task.
- No formatting-only refactors. No drive-by cleanup.

### R5.2 — Update imports after moving files
- Ensure `pytest` and `npm build` pass after each task.

### R5.3 — Leave TODO when uncertain
- Do not guess behaviors that do not exist in current code.
- Return safe failures and leave TODO for later tasks.

---

## 6) VERIFICATION RULES (YOU MUST DO THIS)
### R6.1 — Run verification commands after each task
- Run the exact verification list for that task from PLAN.md.
- If any command fails:
  - fix the code
  - rerun until it passes

### R6.2 — Add tests when required
- If PLAN says “Add tests”, you must create them.
- Do not skip tests “temporarily”.

### R6.3 — Security grep checks are mandatory
After tasks that touch execution/mutation paths, run:
- grep for `shell=True`
- grep for `pty`
- grep for terminal routes
If any exist, remove them.

---

## 7) STOP CONDITIONS (WHEN YOU MUST HALT)
You must stop and refuse to proceed if:
- A task requires implementing raw shell/terminal execution
- A task requires exposing internet-facing UI without Tailscale model
- You are asked to bypass RBAC or audit
- You cannot proceed because the repository structure differs so much that plan steps cannot be mapped

When you stop:
- clearly state the blocker
- list the exact files/lines involved
- propose the smallest safe alternative within these rules

---

## 8) FINAL ASSERTION (MUST HOLD TRUE)
At the end of the refactor:
- No terminal feature exists in UI/API
- No free-form execution exists anywhere in product paths
- All mutations happen through Action Engine
- RBAC + validation + audit are always enforced
- Network mutations are rollback-safe

If any of the above is false, the work is incomplete and must be fixed.

---
END OF AI_RULES.md

