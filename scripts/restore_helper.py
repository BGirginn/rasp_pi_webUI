#!/usr/bin/env python3
"""Out-of-process restore helper that can safely stop the panel and agent."""

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def update_job(db_path: Path, state: str, phase: str, progress: int, error: str | None = None) -> None:
    connection = sqlite3.connect(db_path, timeout=10)
    try:
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute(
            """UPDATE jobs SET state = ?, phase = ?, progress = ?, cancellable = 0,
                      error = ?, completed_at = CASE WHEN ? IN ('completed', 'failed', 'rolled_back')
                          THEN ? ELSE completed_at END, updated_at = ? WHERE id = ?""",
            (state, phase, progress, error, state, now(), now(), PLAN["job_id"]),
        )
        connection.execute(
            "INSERT INTO job_logs (job_id, level, message, created_at) VALUES (?, ?, ?, ?)",
            (PLAN["job_id"], "error" if error else "info", f"Restore phase: {phase}", now()),
        )
        connection.commit()
    finally:
        connection.close()


def service(action: str, name: str, check: bool = True) -> None:
    subprocess.run(["systemctl", action, name], check=check, timeout=60)


def copy_atomic(source: Path, target: Path, rollback_dir: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    rollback = rollback_dir / target.name
    if target.exists():
        shutil.copy2(target, rollback)
        original_stat = target.stat()
    else:
        original_stat = None
    temporary = target.with_name(f".{target.name}.restore-{PLAN['job_id']}")
    shutil.copy2(source, temporary)
    if original_stat:
        os.chown(temporary, original_stat.st_uid, original_stat.st_gid)
        os.chmod(temporary, original_stat.st_mode)
    os.replace(temporary, target)


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
    raise RuntimeError("Panel API did not recover after restore")


def apply_restore() -> None:
    payload = Path(PLAN["payload_path"]).resolve()
    components = set(PLAN["components"])
    rollback_dir = payload.parent / "rollback"
    rollback_dir.mkdir(parents=True, exist_ok=True)
    data_dir = Path("/var/lib/pi-control")
    config_dir = Path(PLAN["config_dir"])
    install_dir = Path(PLAN["install_dir"])

    config_rollback = rollback_dir / "config"
    release_before = None
    if "app_config" in components and config_dir.exists():
        shutil.copytree(config_dir, config_rollback, symlinks=False)
    current = install_dir / "current"
    if current.is_symlink():
        release_before = os.readlink(current)

    update_job(Path(PLAN["jobs_db"]), "running", "maintenance-stop", 96)
    service("stop", "pi-control", check=False)
    service("stop", "pi-agent", check=False)

    try:
        if "control_db" in components:
            copy_atomic(payload / "databases" / "control.db", data_dir / "control.db", rollback_dir)
        if "telemetry_db" in components:
            copy_atomic(payload / "databases" / "telemetry.db", data_dir / "telemetry.db", rollback_dir)
        if "app_config" in components and (payload / "config").exists():
            shutil.copytree(payload / "config", config_dir, dirs_exist_ok=True, symlinks=False)
        if "release" in components:
            if not current.is_symlink():
                raise RuntimeError("Release restore requires the atomic current symlink layout")
            release = install_dir / "releases" / f"restore-{PLAN['job_id']}"
            shutil.rmtree(release, ignore_errors=True)
            shutil.copytree(payload / "release", release, symlinks=False)
            temporary_link = install_dir / f".current-{PLAN['job_id']}"
            temporary_link.unlink(missing_ok=True)
            temporary_link.symlink_to(release)
            os.replace(temporary_link, current)

        update_job(Path(PLAN["jobs_db"]), "completed", "maintenance-verifying", 99)
        subprocess.run(["systemctl", "daemon-reload"], check=False, timeout=30)
        service("start", "pi-agent")
        service("start", "pi-control")
        service("reload", "caddy", check=False)
        wait_for_health()
        update_job(Path(PLAN["jobs_db"]), "completed", "completed", 100)
    except Exception as exc:
        service("stop", "pi-control", check=False)
        service("stop", "pi-agent", check=False)
        for name in ("control.db", "telemetry.db"):
            rollback = rollback_dir / name
            if rollback.exists():
                shutil.copy2(rollback, data_dir / name)
        if config_rollback.exists():
            shutil.copytree(config_rollback, config_dir, dirs_exist_ok=True, symlinks=False)
        if release_before and current.is_symlink():
            temporary_link = install_dir / f".current-rollback-{PLAN['job_id']}"
            temporary_link.unlink(missing_ok=True)
            temporary_link.symlink_to(release_before)
            os.replace(temporary_link, current)
        update_job(Path(PLAN["jobs_db"]), "rolled_back", "rolled_back", 100, str(exc))
        service("start", "pi-agent", check=False)
        service("start", "pi-control", check=False)
        raise


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: restore_helper.py RESTORE_PLAN.json")
    PLAN = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    time.sleep(2)
    apply_restore()
