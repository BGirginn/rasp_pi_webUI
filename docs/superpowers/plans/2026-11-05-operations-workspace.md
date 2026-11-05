# Pi operations workspace implementation plan

> **For agentic workers:** Use superpowers:executing-plans for inline implementation, with a fresh whole-change reviewer at the end.

**Goal:** Deliver a coherent daily-management workspace with reliable navigation, useful service details and safe, complete basic file operations.

**Architecture:** Preserve React/Vite, FastAPI, SQLite and the privileged agent. Reuse existing resources/logs/files/projects endpoints. Use hash navigation instead of adding a router, and shared CSS variables instead of another UI framework. API failures remain visible; user data is never replaced by fabricated output.

**Tech Stack:** React 18 / Vite 8; Python/FastAPI; existing pytest/Vitest.

**Spec:** `docs/IMPROVE_UPGRADE_REPORT.md`, narrowed to its first daily-management package. User delegated product decisions and authorized the preceding GitHub working-baseline checkpoint.

## Global constraints

- Raspberry Pi 5, aarch64, Debian 13 and Python 3.13 observed on the live host; no production dependencies added.
- NAS and third-party app store remain future work; no formatting, account/password reset or new public exposure.
- Existing CORE protection, allowed file roots and terminal break-glass remain enforced.
- No silent overwrite, misleading progress percentage, fake logs or swallowed operation errors.
- Build UI before API SPA tests, never concurrently against the same `dist`.

## Design

Use a restrained operations console: compact navigation, subdued surfaces, one page title, explicit status badges, searchable tables and an adjacent detail pane. Theme preferences remain available. Services show actual state and log errors; Files starts at allowed roots, provides sorting/search, inline creation/rename and copy/move destination selection. Native browser prompts and the frontend-only sudo lock are replaced with explicit forms and existing server role enforcement. Destructive delete retains explicit confirmation and is never executed as a live test on user files.

## Review focus

- A symlink or traversal filename must never permit writes beyond an allowed root.
- A failed/partial upload or conflicting destination must preserve the old file.
- Fast navigation must not display stale listings/logs from an earlier selection.
- Viewers cannot gain mutations; CORE/SYSTEM actions obey the server policy.
- Browser back/forward/reload and an unknown hash must resolve predictably.

## Tasks

### 1. Persistent navigation and common shell

Files: `NavigationContext.jsx`, `App.jsx`, `Sidebar.jsx`, `Dashboard.jsx`, `index.css`; new navigation tests.

- [ ] RED: direct hash, unknown hash, back/forward and per-page restoration tests.
- [ ] GREEN: whitelist hash pages with native history; do not erase an authenticated URL in App. Replace the unverified sidebar Connected claim with account role. Remove duplicate headers only from redesigned pages; reuse existing appearance controls.
- [ ] Verify full UI suite and commit this independently usable task.

### 2. Safe file and truthful service API boundaries

Files: `routers/files.py`, `routers/logs.py`, `routers/resources.py`, related tests.

- [ ] RED: uploads reject symlinks and existing files, interrupted writes preserve targets, copy/rename/move conflicts reject, invalid names reject; logs report agent failure, filters apply without provider, SYSTEM actions reject operators.
- [ ] GREEN: use exclusive file creation/no-follow with cleanup, guarded destinations, reject directory links during copy; offload blocking file work to a thread. Reuse existing payloads and return clear 409/403 errors. Resolve systemd IDs for real logs and remove mock fallback. Enforce role/action bounds.
- [ ] Verify API suite after UI build; commit.

### 3. Services and file-management workspace

Files: `ServicesPage.jsx`, `FilesPage.jsx`, `index.css`; new page behavior tests and existing screen smoke tests.

- [ ] RED: service selection/log errors and successful action verification; allowed file roots, folder navigation, search, copy/move/rename, upload errors and role controls.
- [ ] GREEN: dense service table with actionable details/log pane; actual operation stages. Files uses allowed roots, breadcrumbs, accessible rows and explicit forms. No OS-password UI gate; backend remains authoritative. Keep last good data on refresh errors, guard stale responses and show errors in place.
- [ ] Verify full UI + API suites and build; commit.

### 4. Review and user-visible acceptance

- [ ] Fresh reviewer inspects the entire branch and the Review focus conditions. Fix important findings with regression tests.
- [ ] Exercise actual navigation and core flows in Brave; use a dedicated temporary root for live file tests, never user data.
- [ ] Keep checkpoint tag unchanged; record exact deployed/source scope and remaining limits.

## Execution ledger

- Baseline `f364db7`: pushed and tag independently verified. UI 61, API 354 and agent 149 tests passed. Initial concurrent build/API test race was resolved by rerunning sequentially.
- Ruling: execute in `/tmp/pi-control-operations-20261105` on `improve/operations-ui` — keep the saved main checkout intact during development; cost is a later reviewed fast-forward.
