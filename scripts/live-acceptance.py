#!/usr/bin/env python3
"""Authenticated read-only feature audit plus reversible systemd canary actions."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt


API_BASE = "http://127.0.0.1:8080"
CANARY_NAME = "pi-control-canary"
CANARY_ID = f"systemd-{CANARY_NAME}"
CANARY_PATH = Path(f"/run/systemd/system/{CANARY_NAME}.service")


def checked(*command: str) -> str:
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"{command[0]} failed")
    return result.stdout.strip()


def admin_token() -> str:
    database = sqlite3.connect("/var/lib/pi-control/control.db")
    try:
        row = database.execute(
            "SELECT id, username, role FROM users WHERE role = 'admin' ORDER BY id LIMIT 1"
        ).fetchone()
    finally:
        database.close()
    if not row:
        raise RuntimeError("No admin account is available for live acceptance")
    secret = Path("/etc/pi-control/jwt_secret").read_text(encoding="utf-8").strip()
    payload = {
        "sub": str(row[0]),
        "username": row[1],
        "role": row[2],
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def api(method: str, path: str, token: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        f"{API_BASE}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"{method} {path}: HTTP {exc.code}: {detail}") from exc


def wait_for_state(token: str, expected: str) -> dict:
    for _ in range(30):
        resources = api("GET", "/api/resources?refresh=true", token)
        resource = next((item for item in resources if item["id"] == CANARY_ID), None)
        if resource and resource["state"] == expected:
            return resource
        time.sleep(0.2)
    raise RuntimeError(f"Canary did not reach {expected}")


def run_canary(token: str) -> list[dict]:
    CANARY_PATH.write_text(
        """[Unit]
Description=Pi Control acceptance canary

[Service]
Type=oneshot
ExecStart=/usr/bin/true
RemainAfterExit=yes
""",
        encoding="ascii",
    )
    checked("systemctl", "daemon-reload")
    results = []
    try:
        for action, expected in (("start", "running"), ("restart", "running"), ("stop", "stopped")):
            response = api(
                "POST",
                f"/api/resources/{CANARY_ID}/action",
                token,
                {"action": action},
            )
            resource = wait_for_state(token, expected)
            results.append(
                {
                    "action": action,
                    "state": resource["state"],
                    "active_state": resource["active_state"],
                    "sub_state": resource["sub_state"],
                    "success": response.get("success", False),
                }
            )
    finally:
        subprocess.run(["systemctl", "stop", f"{CANARY_NAME}.service"], capture_output=True)
        CANARY_PATH.unlink(missing_ok=True)
        subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
        subprocess.run(["systemctl", "reset-failed"], capture_output=True)
    return results


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("Live acceptance must run as root")
    token = admin_token()
    canary = run_canary(token)
    audit = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("feature-audit.py")),
            "--base-url",
            API_BASE,
            "--token",
            token,
            "--json",
        ],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if audit.returncode != 0:
        raise RuntimeError(f"Feature audit failed:\n{audit.stdout}\n{audit.stderr}")
    print(json.dumps({"canary": canary, "features": json.loads(audit.stdout)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
