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

def test_user_management():
    global TOKEN
    log("Testing User Management...", "INFO")
    
    # login as admin first
    TOKEN = test_login("admin", "admin123")
    if not TOKEN: return False

    # 1. Create User
    new_user = {"username": "apitestuser", "password": "password123", "role": "viewer"}
    log("Creating User 'apitestuser'...", "INFO")
    code, resp = api_request("POST", "/auth/users", new_user)
    if code != 200:
        if "already exists" in str(resp):
             log("User already exists, continuing...", "WARN")
             # Find ID to cleanup first? No, we will delete by ID later testing list loop.
        else:
            log(f"Create User Failed: {resp}", "FAIL")
            return False
    else:
        log("User Created", "PASS")

    # 2. List Users
    log("Listing Users...", "INFO")
    code, resp = api_request("GET", "/auth/users")
    if code == 200 and isinstance(resp, list):
        target_user = next((u for u in resp if u["username"] == "apitestuser"), None)
        if target_user:
            log("User 'apitestuser' found in list", "PASS")
            user_id = target_user["id"]
        else:
            log("User 'apitestuser' NOT found in list", "FAIL")
            return False
    else:
        log(f"List Users Failed: {resp}", "FAIL")
        return False

    # 3. Login as New User
    user_token = test_login("apitestuser", "password123", "NewUser")
    if not user_token: return False

    # 4. Change Password
    log("Changing Password for 'apitestuser'...", "INFO")
    code, resp = api_request("POST", "/auth/password/change", 
                            {"current_password": "password123", "new_password": "newpass123"}, 
                            token=user_token)
    if code == 200:
        log("Password Changed Successfully", "PASS")
    else:
        log(f"Change Password Failed: {resp}", "FAIL")
        return False

    # 5. Verify New Password
    if test_login("apitestuser", "newpass123", "NewUser with New Password"):
        log("New Password Verification Successful", "PASS")
    else:
        return False

    # 6. Delete User (as Admin)
    log("Deleting User 'apitestuser'...", "INFO")
    code, resp = api_request("DELETE", f"/auth/users/{user_id}")
    if code == 200:
        log("User Deleted", "PASS")
    else:
        log(f"Delete User Failed: {resp}", "FAIL")
        return False

    # 7. Verify Deletion
    code, resp = api_request("GET", "/auth/users")
    if code == 200:
        if not any(u["username"] == "apitestuser" for u in resp):
            log("Deletion Verified (User gone from list)", "PASS")
            return True
        else:
            log("User still exists in list!", "FAIL")
            return False
    return False

def test_websocket():
    # Only if simple test passes
    return True

def run_all():
    print("==========================================")
    print("    PI CONTROL PANEL - SYSTEM VERIFICATION v2")
    print("==========================================")
    
    success = True
    if not test_user_management(): success = False
    
    # Run other tests briefly
    if not test_telemetry(): success = False

    print("\nVerification Complete.")
    if success:
        print("\033[92mALL TESTS PASSED\033[0m")
    else:
        print("\033[91mSOME TESTS FAILED\033[0m")

if __name__ == "__main__":
    run_all()
