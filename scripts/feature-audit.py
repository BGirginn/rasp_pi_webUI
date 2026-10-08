#!/usr/bin/env python3
"""Read-only production feature matrix for Pi Control Panel."""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class Check:
    feature: str
    path: str
    status: str
    http_status: Optional[int]
    detail: str = ""


CHECKS = [
    ("Dashboard", "/api/telemetry/current"),
    ("Dashboard", "/api/resources"),
    ("Telemetry", "/api/telemetry/dashboard"),
    ("Alerts", "/api/alerts"),
    ("Alerts", "/api/alerts/rules"),
    ("Services", "/api/resources?refresh=true"),
    ("Devices", "/api/devices"),
    ("Devices", "/api/devices/gpio/pins"),
    ("IoT", "/api/iot/devices"),
    ("IoT", "/api/iot/mqtt/status"),
    ("Network", "/api/network/interfaces"),
    ("Network", "/api/network/connectivity"),
    ("Network", "/api/network/wifi/status"),
    ("Network", "/api/network/bluetooth/status"),
    ("AdGuard", "/api/dns-filter/status"),
    ("Projects", "/api/projects"),
    ("Jobs", "/api/jobs?limit=5"),
    ("Jobs", "/api/jobs/types"),
    ("Archive", "/api/archive/stats"),
    ("Archive", "/api/backup/status"),
    ("Terminal", "/api/terminal/breakglass/status"),
    ("Files", "/api/files/roots"),
    ("Settings", "/api/auth/me"),
    ("Settings", "/api/auth/sessions"),
    ("Settings", "/api/notifications/settings/telegram"),
]


def request(base_url: str, path: str, token: str, insecure: bool) -> tuple[int, str]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    req = urllib.request.Request(f"{base_url.rstrip('/')}{path}", headers=headers)
    context = ssl._create_unverified_context() if insecure else None
    try:
        with urllib.request.urlopen(req, timeout=20, context=context) as response:
            return response.status, response.read(4096).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(4096).decode("utf-8", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--token", default=os.environ.get("PI_CONTROL_TOKEN", ""))
    parser.add_argument("--insecure", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.token:
        parser.error("--token or PI_CONTROL_TOKEN is required")

    results = []
    for feature, path in CHECKS:
        try:
            status_code, body = request(args.base_url, path, args.token, args.insecure)
            if 200 <= status_code < 300:
                status = "PASS"
                detail = ""
            elif status_code in {424, 502, 503}:
                status = "BLOCKED_EXTERNAL"
                detail = body[:240]
            else:
                status = "FAIL"
                detail = body[:240]
        except Exception as exc:
            status_code = None
            status = "FAIL"
            detail = str(exc)
        results.append(Check(feature, path, status, status_code, detail))

    if args.json:
        print(json.dumps([asdict(item) for item in results], indent=2))
    else:
        for item in results:
            code = item.http_status if item.http_status is not None else "-"
            print(f"{item.status:16} {code!s:>3} {item.feature:12} {item.path}")
            if item.detail:
                print(f"{'':22}{item.detail}")

    failures = sum(item.status == "FAIL" for item in results)
    blocked = sum(item.status == "BLOCKED_EXTERNAL" for item in results)
    print(
        json.dumps(
            {"passed": len(results) - failures - blocked, "blocked": blocked, "failed": failures}
        ),
        file=sys.stderr,
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
