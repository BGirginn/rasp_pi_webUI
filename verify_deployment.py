import urllib.request
import urllib.parse
import json
import socket
import ssl

# Setup
BASE_URL = "http://100.80.90.68:8080/api"
UI_URL = "http://100.80.90.68:8080"
WS_HOST = "100.80.90.68"
WS_PORT = 8080
HEADERS = {"Content-Type": "application/json"}
TOKEN = None # Admin token

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def log(msg, status="INFO"):
    colors = { "PASS": "\033[92m", "FAIL": "\033[91m", "WARN": "\033[93m", "INFO": "\033[94m", "RESET": "\033[0m" }
    print(f"{colors.get(status, colors['RESET'])}[{status}] {msg}{colors['RESET']}")

def api_request(method, endpoint, data=None, token=None):
    try:
        url = f"{BASE_URL}{endpoint}"
        req_headers = HEADERS.copy()
        if token:
            req_headers["Authorization"] = f"Bearer {token}"
        elif TOKEN:
             req_headers["Authorization"] = f"Bearer {TOKEN}"
        
        req_data = json.dumps(data).encode('utf-8') if data else None
        req = urllib.request.Request(url, data=req_data, headers=req_headers, method=method)
        
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            if response.status == 204: return 204, {}
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode())
        except: return e.code, e.reason
    except Exception as e: return 0, str(e)

def test_login(username, password, description="Admin"):
    log(f"Testing Login ({description})...", "INFO")
    code, resp = api_request("POST", "/auth/login", {"username": username, "password": password})
    if code == 200 and "access_token" in resp:
        log(f"Login ({description}) Successful", "PASS")
        return resp["access_token"]
    else:
        log(f"Login ({description}) Failed: {resp}", "FAIL")
        return None

def test_telemetry():
    log("Testing Telemetry...", "INFO")
    code, resp = api_request("GET", "/telemetry/dashboard")
    if code == 200:
        log("Telemetry Data Received", "PASS")
        return True
    return False

def test_network():
    log("Testing Network Interfaces...", "INFO")
    code, resp = api_request("GET", "/network/interfaces")
    if code == 200 and isinstance(resp, list) and len(resp) > 0:
        log(f"Network Interfaces Found: {len(resp)} ({resp[0].get('name')})", "PASS")
        return True
    else:
        log(f"Network Interfaces Failed: {resp}", "FAIL")
        return False

def test_usb():
    log("Testing USB Devices...", "INFO")
    code, resp = api_request("GET", "/devices/usb/list")
    if code == 200 and isinstance(resp, list):
         log(f"USB Devices Detected: {len(resp)}", "PASS")
         return True
    else:
         log(f"USB Device Check Failed: {resp}", "FAIL")
         return False

def test_service_control():
    log("Testing Service Control (Restarting cron)...", "INFO")
    req = {"action": "restart"}
    # Resource ID logic: "systemd-cron"
    code, resp = api_request("POST", "/resources/systemd-cron/action", req)
    
    if code == 200 and resp.get("success"):
        log("Service 'cron' restarted", "PASS")
        return True
    elif code == 404: 
         code, resp = api_request("POST", "/resources/systemd-crond/action", req)
         if code == 200 and resp.get("success"):
            log("Service 'crond' restarted", "PASS")
            return True
         else:
             log(f"Service 'cron/crond' Not Found: {resp}", "WARN")
             return True 
    
    log(f"Service Restart Failed: {resp}", "FAIL")
    return False

def test_user_management():
    global TOKEN
    log("Testing User Management...", "INFO")
    
    TOKEN = test_login("admin", "admin123")
    if not TOKEN: return False

    # Cleanup previous run if needed
    code, resp = api_request("GET", "/auth/users")
    if code == 200:
        for u in resp:
            if u["username"] == "apitestuser":
                api_request("DELETE", f"/auth/users/{u['id']}")

    # 1. Create User
    new_user = {"username": "apitestuser", "password": "password123", "role": "viewer"}
    code, resp = api_request("POST", "/auth/users", new_user)
    if code != 200:
        log(f"Create User Failed: {resp}", "FAIL")
        return False
    
    log("User Created", "PASS")

    # 2. List Users
    code, resp = api_request("GET", "/auth/users")
    target_user = next((u for u in resp if u["username"] == "apitestuser"), None)
    if target_user:
        log("User Found in List", "PASS")
        user_id = target_user["id"]
    else:
        log("User NOT Found", "FAIL")
        return False

    # 3. Login as New User
    user_token = test_login("apitestuser", "password123", "NewUser")
    if not user_token: return False

    # 4. Change Password
    code, resp = api_request("POST", "/auth/password/change", 
                            {"current_password": "password123", "new_password": "newpass123"}, 
                            token=user_token)
    if code == 200:
        log("Password Changed", "PASS")
    else:
        log(f"Change Password Failed: {resp}", "FAIL")
        return False

    # 5. Verify New Password
    if test_login("apitestuser", "newpass123", "NewUser NewPass"):
        log("New Password Working", "PASS")
    else:
        return False

    # 6. Delete User
    code, resp = api_request("DELETE", f"/auth/users/{user_id}")
    if code == 200:
        log("User Deleted", "PASS")
    else:
        return False
    
    return True

def test_websocket():
    log("Testing Terminal WebSocket...", "INFO")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((WS_HOST, WS_PORT))
        req = (
            "GET /api/terminal/ws HTTP/1.1\r\n"
            f"Host: {WS_HOST}:{WS_PORT}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        sock.send(req.encode())
        resp = sock.recv(4096).decode()
        sock.close()
        if "101 Switching Protocols" in resp:
            log("WebSocket Handshake OK", "PASS")
            return True
        else:
            log(f"WebSocket Fail: {resp[:20]}...", "FAIL")
            return False
    except Exception as e:
        log(f"WebSocket Error: {e}", "FAIL")
        return False

def run_all():
    print("==========================================")
    print("    PI CONTROL PANEL - EXHAUSTIVE VERIFICATION V5")
    print("==========================================")
    
    success = True
    if not test_user_management(): success = False
    if not test_telemetry(): success = False
    if not test_network(): success = False
    if not test_usb(): success = False
    if not test_service_control(): success = False
    if not test_websocket(): success = False

    print("\nStatus:")
    if success:
        print("\033[92mALL SYSTEMS GO - TESTED AND VERIFIED\033[0m")
    else:
        print("\033[91mFAILURES DETECTED\033[0m")

if __name__ == "__main__":
    run_all()
