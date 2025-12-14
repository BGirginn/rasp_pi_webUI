#!/usr/bin/env python3
"""
Remote Deploy Script - Deploy theme changes to Raspberry Pi
Uses the /terminal/exec API endpoint to run commands remotely.
"""

import urllib.request
import urllib.parse
import json
import ssl
import time

# Configuration
BASE_URL = "http://100.80.90.68:8080/api"
HEADERS = {"Content-Type": "application/json"}

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

TOKEN = None

def log(msg, status="INFO"):
    colors = { "PASS": "\033[92m", "FAIL": "\033[91m", "WARN": "\033[93m", "INFO": "\033[94m", "RESET": "\033[0m" }
    print(f"{colors.get(status, colors['RESET'])}[{status}] {msg}{colors['RESET']}")

def api_request(method, endpoint, data=None):
    try:
        url = f"{BASE_URL}{endpoint}"
        req_headers = HEADERS.copy()
        if TOKEN:
            req_headers["Authorization"] = f"Bearer {TOKEN}"
        
        req_data = json.dumps(data).encode('utf-8') if data else None
        req = urllib.request.Request(url, data=req_data, headers=req_headers, method=method)
        
        with urllib.request.urlopen(req, context=ctx, timeout=60) as response:
            if response.status == 204: return 204, {}
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode())
        except: return e.code, e.reason
    except Exception as e: return 0, str(e)

def login():
    global TOKEN
    log("Logging in as admin...", "INFO")
    code, resp = api_request("POST", "/auth/login", {"username": "admin", "password": "admin123"})
    if code == 200 and "access_token" in resp:
        TOKEN = resp["access_token"]
        log("Login successful", "PASS")
        return True
    else:
        log(f"Login failed: {resp}", "FAIL")
        return False

def exec_command(cmd, description):
    log(f"Running: {description}", "INFO")
    code, resp = api_request("POST", "/terminal/exec", {"command": cmd})
    if code == 200:
        output = resp.get("output", "")
        exit_code = resp.get("exit_code", -1)
        if exit_code == 0:
            log(f"Success: {description}", "PASS")
        else:
            log(f"Warning (exit {exit_code}): {description}", "WARN")
        if output:
            print(f"  Output: {output[:200]}...")
        return True
    else:
        log(f"Failed: {resp}", "FAIL")
        return False

def main():
    log("=" * 50, "INFO")
    log("REMOTE DEPLOY - Cyberpunk Theme", "INFO")
    log("=" * 50, "INFO")
    
    if not login():
        return
    
    # Step 1: Git pull
    exec_command("cd /home/pi/panel && git pull", "Git Pull")
    
    # Step 2: Install UI dependencies (if needed)
    exec_command("cd /home/pi/panel/ui && npm install --silent 2>/dev/null || true", "NPM Install (if needed)")
    
    # Step 3: Build UI
    exec_command("cd /home/pi/panel/ui && npm run build 2>&1 | tail -5", "Build UI")
    
    # Step 4: Restart service
    exec_command("sudo systemctl restart picontrol || sudo systemctl restart panel || echo 'Service restart skipped'", "Restart Service")
    
    log("=" * 50, "INFO")
    log("DEPLOY COMPLETE - Refresh your browser!", "PASS")
    log("=" * 50, "INFO")

if __name__ == "__main__":
    main()
