#!/usr/bin/env python3
"""Atomically activate a staged Pi Control release and roll back on failure."""

import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def update_job(state: str, phase: str, progress: int, error: str | None = None) -> None:
    connection = sqlite3.connect(PLAN["jobs_db"], timeout=10)
    try:
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute(
            """UPDATE jobs SET state=?, phase=?, progress=?, cancellable=0, error=?,
                      completed_at=CASE WHEN ? IN ('completed','failed','rolled_back') THEN ? ELSE completed_at END,
                      updated_at=? WHERE id=?""",
            (state, phase, progress, error, state, now(), now(), PLAN["job_id"]),
        )
        connection.execute(
            "INSERT INTO job_logs (job_id, level, message, created_at) VALUES (?, ?, ?, ?)",
            (PLAN["job_id"], "error" if error else "info", f"Update phase: {phase}", now()),
        )
        connection.commit()
    finally:
        connection.close()


def systemctl(action: str, service: str | None = None, check: bool = True) -> None:
    command = ["systemctl", action]
    if service:
        command.append(service)
    subprocess.run(command, check=check, timeout=60)


def wait_for_health(timeout: int = 90) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:8080/api/health", timeout=3) as response:
                if response.status == 200:
                    return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError("Updated API failed its health check")


def switch_link(current: Path, release: Path) -> None:
    temporary = current.parent / f".current-{PLAN['job_id']}"
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(release)
    os.replace(temporary, current)


def activate() -> None:
    current = Path(PLAN["current"])
    release = Path(PLAN["release"])
    if not current.is_symlink():
        raise RuntimeError("Atomic release layout is not initialized")
    previous = current.resolve()
    if not (release / "venv" / "bin" / "uvicorn").is_file():
        raise RuntimeError("Staged release has no runnable API environment")
    if not (release / "panel" / "ui" / "dist" / "index.html").is_file():
        raise RuntimeError("Staged release has no UI build")

    update_job("running", "maintenance-stop", 96)
    systemctl("stop", "pi-control", check=False)
    systemctl("stop", "pi-agent", check=False)
    try:
        switch_link(current, release)
        if (release / "caddy" / "Caddyfile").is_file():
            subprocess.run(["cp", str(release / "caddy" / "Caddyfile"), "/etc/caddy/Caddyfile"], check=True)
        systemctl("daemon-reload")
        update_job("completed", "maintenance-verifying", 99)
        systemctl("start", "pi-agent")
        systemctl("start", "pi-control")
        systemctl("reload", "caddy", check=False)
        wait_for_health()
        update_job("completed", "completed", 100)
    except Exception as exc:
        systemctl("stop", "pi-control", check=False)
        systemctl("stop", "pi-agent", check=False)
        switch_link(current, previous)
        if (previous / "caddy" / "Caddyfile").is_file():
            subprocess.run(["cp", str(previous / "caddy" / "Caddyfile"), "/etc/caddy/Caddyfile"], check=False)
        systemctl("daemon-reload", check=False)
        systemctl("start", "pi-agent", check=False)
        systemctl("start", "pi-control", check=False)
        update_job("rolled_back", "rolled_back", 100, str(exc))
        raise


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: update_helper.py UPDATE_PLAN.json")
    PLAN = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    time.sleep(2)
    activate()
