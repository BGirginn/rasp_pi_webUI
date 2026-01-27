"""
Pi Control Panel - Terminal Router

WebSocket-based terminal with two modes:
- Restricted: Execute allowlisted commands only (default)
- Full PTY: Interactive shell (requires break-glass elevation)

Security features:
- Break-glass flow with password reauth + optional TOTP
- Short-lived elevation tokens (10 min default)
- Comprehensive audit logging
- Idle timeout enforcement
- Docker SSH disabled by default
"""

import asyncio
import os
import pty
import select
import signal
import struct
import fcntl
import termios
import time
import re
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request
from pydantic import BaseModel

from config import settings
from db import get_control_db
from .auth import _validate_token, require_role, get_current_user, verify_password_async

router = APIRouter()


# ============================================================================
# Pydantic Models
# ============================================================================

class BreakGlassStartRequest(BaseModel):
    password: str
    totp_code: Optional[str] = None


class BreakGlassStartResponse(BaseModel):
    breakglass_token: str
    expires_at: str
    ttl_seconds: int


class BreakGlassStatusResponse(BaseModel):
    active: bool
    expires_at: Optional[str] = None
    remaining_seconds: Optional[int] = None
    session_id: Optional[str] = None


class BreakGlassStopRequest(BaseModel):
    reason: Optional[str] = "manual_close"


class RestrictedCommandRequest(BaseModel):
    command: str


class RestrictedCommandResponse(BaseModel):
    output: str
    exit_code: int
    command: str


class CommandRequest(BaseModel):
    command: str


class CommandResponse(BaseModel):
    output: str
    exit_code: int


# ============================================================================
# Audit Logging Helper
# ============================================================================

async def log_terminal_event(
    event_type: str,
    user_id: int,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[str] = None,
    resource_id: Optional[str] = None
):
    """Log terminal-related events to audit log."""
    db = await get_control_db()
    await db.execute(
        """INSERT INTO audit_log (user_id, action, resource_id, details, ip_address)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, event_type, resource_id, details, ip_address)
    )
    await db.commit()


# ============================================================================
# Break-Glass Token Management
# ============================================================================

def generate_breakglass_token() -> str:
    """Generate a cryptographically secure break-glass token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a token for storage."""
    return hashlib.sha256(token.encode()).hexdigest()


async def validate_breakglass_token(token: str, user_id: int) -> bool:
    """Validate a break-glass token for a user."""
    if not token:
        return False
    
    db = await get_control_db()
    token_hash = hash_token(token)
    
    cursor = await db.execute(
        """SELECT id, expires_at, closed_at FROM breakglass_sessions 
           WHERE token_hash = ? AND user_id = ? AND closed_at IS NULL""",
        (token_hash, user_id)
    )
    row = await cursor.fetchone()
    
    if not row:
        return False
    
    session_id, expires_at_str, closed_at = row
    
    # Check expiration
    expires_at = datetime.fromisoformat(expires_at_str)
    if datetime.utcnow() > expires_at:
        # Auto-close expired session
        await db.execute(
            "UPDATE breakglass_sessions SET closed_at = ?, close_reason = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), "expired", session_id)
        )
        await db.commit()
        return False
    
    return True


async def close_breakglass_session(user_id: int, reason: str = "manual_close"):
    """Close all active break-glass sessions for a user."""
    db = await get_control_db()
    await db.execute(
        """UPDATE breakglass_sessions 
           SET closed_at = ?, close_reason = ? 
           WHERE user_id = ? AND closed_at IS NULL""",
        (datetime.utcnow().isoformat(), reason, user_id)
    )
    await db.commit()


# ============================================================================
# Break-Glass API Endpoints
# ============================================================================

@router.post("/breakglass/start", response_model=BreakGlassStartResponse)
async def start_breakglass(
    request: BreakGlassStartRequest,
    req: Request,
    user: dict = Depends(get_current_user)
):
    """
    Start a break-glass session for full terminal access.
    
    Requires:
    - Valid current session (access_token)
    - Password re-authentication
    - TOTP code if 2FA is enabled for the user
    
    Returns a short-lived break-glass token.
    """
    db = await get_control_db()
    
    # Get user's password hash and TOTP status
    cursor = await db.execute(
        "SELECT password_hash, totp_secret FROM users WHERE id = ?",
        (user["id"],)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=401, detail="User not found")
    
    password_hash, totp_secret = row
    
    # Verify password
    if not await verify_password_async(request.password, password_hash):
        await log_terminal_event(
            "breakglass_failed",
            user["id"],
            ip_address=req.client.host if req.client else None,
            details="Invalid password"
        )
        raise HTTPException(status_code=401, detail="Invalid password")
    
    # Verify TOTP if enabled
    if totp_secret:
        if not request.totp_code:
            raise HTTPException(status_code=401, detail="TOTP code required")
        
        import pyotp
        totp = pyotp.TOTP(totp_secret)
        if not totp.verify(request.totp_code):
            await log_terminal_event(
                "breakglass_failed",
                user["id"],
                ip_address=req.client.host if req.client else None,
                details="Invalid TOTP code"
            )
            raise HTTPException(status_code=401, detail="Invalid TOTP code")
    
    # Close any existing sessions
    await close_breakglass_session(user["id"], "new_session")
    
    # Generate new token
    token = generate_breakglass_token()
    token_hash = hash_token(token)
    
    # Calculate expiration
    ttl_minutes = min(settings.terminal_breakglass_ttl_min, 30)  # Cap at 30 min
    issued_at = datetime.utcnow()
    expires_at = issued_at + timedelta(minutes=ttl_minutes)
    
    # Store session
    import uuid
    session_id = str(uuid.uuid4())
    
    await db.execute(
        """INSERT INTO breakglass_sessions 
           (id, user_id, token_hash, issued_at, expires_at, ip_address, user_agent)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            user["id"],
            token_hash,
            issued_at.isoformat(),
            expires_at.isoformat(),
            req.client.host if req.client else None,
            req.headers.get("User-Agent", "")
        )
    )
    await db.commit()
    
    # Audit log
    await log_terminal_event(
        "breakglass_open",
        user["id"],
        ip_address=req.client.host if req.client else None,
        user_agent=req.headers.get("User-Agent", ""),
        resource_id=session_id,
        details=f"TTL: {ttl_minutes} minutes"
    )
    
    return BreakGlassStartResponse(
        breakglass_token=token,
        expires_at=expires_at.isoformat(),
        ttl_seconds=ttl_minutes * 60
    )


@router.get("/breakglass/status", response_model=BreakGlassStatusResponse)
async def get_breakglass_status(user: dict = Depends(get_current_user)):
    """Get the status of active break-glass session."""
    db = await get_control_db()
    
    cursor = await db.execute(
        """SELECT id, expires_at FROM breakglass_sessions 
           WHERE user_id = ? AND closed_at IS NULL
           ORDER BY issued_at DESC LIMIT 1""",
        (user["id"],)
    )
    row = await cursor.fetchone()
    
    if not row:
        return BreakGlassStatusResponse(active=False)
    
    session_id, expires_at_str = row
    expires_at = datetime.fromisoformat(expires_at_str)
    
    if datetime.utcnow() > expires_at:
        # Session expired, close it
        await close_breakglass_session(user["id"], "expired")
        return BreakGlassStatusResponse(active=False)
    
    remaining = int((expires_at - datetime.utcnow()).total_seconds())
    
    return BreakGlassStatusResponse(
        active=True,
        expires_at=expires_at_str,
        remaining_seconds=remaining,
        session_id=session_id
    )


@router.post("/breakglass/stop")
async def stop_breakglass(
    request: BreakGlassStopRequest,
    req: Request,
    user: dict = Depends(get_current_user)
):
    """Stop the active break-glass session."""
    await close_breakglass_session(user["id"], request.reason or "manual_close")
    
    # Audit log
    await log_terminal_event(
        "breakglass_close",
        user["id"],
        ip_address=req.client.host if req.client else None,
        details=f"Reason: {request.reason or 'manual_close'}"
    )
    
    return {"message": "Break-glass session closed"}


# ============================================================================
# Restricted Command Execution
# ============================================================================

# Command validation patterns
BLOCKED_PATTERNS = [";", "|", "&", "`", "$(", ">", "<", ">>", "<<", "\n", "\r"]
SERVICE_REGEX = re.compile(r'^[a-zA-Z0-9_.-]+$')
CONTAINER_REGEX = re.compile(r'^[a-zA-Z0-9_.-]+$')


def validate_restricted_command(command: str) -> tuple[bool, str]:
    """
    Validate a command against the restricted allowlist.
    Returns (is_valid, error_message).
    """
    # Check for blocked patterns (shell metacharacters)
    for pattern in BLOCKED_PATTERNS:
        if pattern in command:
            return False, f"Blocked pattern detected: {pattern}"
    
    # Get allowed commands from settings
    allowed = settings.terminal_allowed_commands_list
    if not allowed:
        # Default allowlist
        allowed = [
            "whoami", "uptime", "uname -a", "df -h", "free -h",
            "ip a", "ip r", "docker ps"
        ]
    
    # Check exact matches first
    cmd_base = command.strip()
    if cmd_base in allowed:
        return True, ""
    
    # Check parameterized commands
    parts = cmd_base.split()
    if not parts:
        return False, "Empty command"
    
    # systemctl status/restart <service>
    if len(parts) >= 3 and parts[0] == "systemctl":
        if parts[1] in ("status", "restart"):
            service = parts[2]
            if SERVICE_REGEX.match(service):
                return True, ""
            return False, f"Invalid service name: {service}"
        return False, f"Only systemctl status/restart allowed"
    
    # journalctl -u <service>
    if len(parts) >= 3 and parts[0] == "journalctl" and parts[1] == "-u":
        service = parts[2]
        if SERVICE_REGEX.match(service):
            return True, ""
        return False, f"Invalid service name: {service}"
    
    # docker logs <container>
    if len(parts) >= 3 and parts[0] == "docker" and parts[1] == "logs":
        container = parts[2]
        if CONTAINER_REGEX.match(container):
            return True, ""
        return False, f"Invalid container name: {container}"
    
    return False, f"Command not in allowlist: {cmd_base}"


@router.post("/restricted/exec", response_model=RestrictedCommandResponse)
async def execute_restricted_command(
    request: RestrictedCommandRequest,
    req: Request,
    user: dict = Depends(require_role("admin", "operator"))
):
    """Execute a command in restricted mode (allowlisted commands only)."""
    import subprocess
    
    # Validate command
    is_valid, error = validate_restricted_command(request.command)
    if not is_valid:
        await log_terminal_event(
            "restricted_command_blocked",
            user["id"],
            ip_address=req.client.host if req.client else None,
            details=f"Command: {request.command[:100]}, Error: {error}"
        )
        raise HTTPException(status_code=403, detail=error)
    
    try:
        result = subprocess.run(
            request.command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        output = result.stdout + result.stderr
        exit_code = result.returncode
        
        # Audit log (truncate output)
        await log_terminal_event(
            "restricted_command_exec",
            user["id"],
            ip_address=req.client.host if req.client else None,
            details=f"Command: {request.command}, RC: {exit_code}"
        )
        
        return RestrictedCommandResponse(
            output=output[:10000] or "(no output)",  # Truncate large output
            exit_code=exit_code,
            command=request.command
        )
        
    except subprocess.TimeoutExpired:
        return RestrictedCommandResponse(
            output="Command timed out (30s limit)",
            exit_code=124,
            command=request.command
        )
    except Exception as e:
        return RestrictedCommandResponse(
            output=str(e),
            exit_code=1,
            command=request.command
        )


# ============================================================================
# Full PTY Terminal Session (Break-Glass Required)
# ============================================================================

class TerminalSession:
    """Manages a persistent PTY terminal session."""
    
    def __init__(self, session_id: str, user_id: int, user_name: str):
        self.session_id = session_id
        self.user_id = user_id
        self.user_name = user_name
        self.fd: Optional[int] = None
        self.pid: Optional[int] = None
        self.running = False
        self.websockets: List[WebSocket] = []
        # Circular buffer for history (store last ~100KB of output)
        from collections import deque
        self.history = deque(maxlen=100)
        self.history_bytes = 0
        self.max_history_bytes = 100 * 1024  # 100KB
        self.read_task: Optional[asyncio.Task] = None
        self.last_activity = time.time()
        self.idle_timeout = settings.terminal_idle_timeout_sec
    
    def _is_running_in_docker(self) -> bool:
        """Check if running inside a Docker container."""
        if os.path.exists("/.dockerenv"):
            return True
        try:
            with open("/proc/1/cgroup", "r") as f:
                return "docker" in f.read()
        except:
            return False
    
    async def start(self, cols: int = 80, rows: int = 24):
        """Start a new terminal session - native bash only (Docker SSH disabled by default)."""
        if self.running:
            return

        # Check if Docker SSH is enabled
        in_docker = self._is_running_in_docker()
        
        if in_docker and not settings.terminal_docker_ssh_enabled:
            raise RuntimeError(
                "Terminal not available in Docker mode. "
                "Set TERMINAL_DOCKER_SSH_ENABLED=true and configure SSH key auth."
            )

        # Fork a pseudo-terminal
        self.pid, self.fd = pty.fork()
        
        if self.pid == 0:
            # Child process
            os.environ["TERM"] = "xterm-256color"
            os.environ["COLORTERM"] = "truecolor"
            
            if in_docker and settings.terminal_docker_ssh_enabled:
                # Docker mode: SSH to host (SSH key auth required)
                import subprocess
                try:
                    result = subprocess.run(
                        ["ip", "route", "show", "default"],
                        capture_output=True, text=True
                    )
                    gateway = result.stdout.split()[2] if result.stdout else "host.docker.internal"
                except:
                    gateway = "host.docker.internal"
                
                # Get SSH credentials from environment - NO DEFAULTS
                ssh_user = os.environ.get("SSH_HOST_USER")
                ssh_key_path = os.environ.get("SSH_HOST_KEY_PATH")
                
                if not ssh_user:
                    # Write error and exit
                    os.write(1, b"Error: SSH_HOST_USER not configured\r\n")
                    os._exit(1)
                
                ssh_args = ["ssh"]
                
                if ssh_key_path and os.path.exists(ssh_key_path):
                    ssh_args.extend(["-i", ssh_key_path])
                
                # Do NOT disable host key checking - use proper known_hosts
                ssh_args.extend([
                    "-o", "LogLevel=ERROR",
                    f"{ssh_user}@{gateway}"
                ])
                
                os.execvp("ssh", ssh_args)
            else:
                # Native mode: Direct bash shell
                os.execvp("/bin/bash", ["/bin/bash", "-l"])
        else:
            # Parent process
            self.running = True
            
            # Set terminal size
            self.resize(cols, rows)
            
            # Set non-blocking
            flags = fcntl.fcntl(self.fd, fcntl.F_GETFL)
            fcntl.fcntl(self.fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            # Start background reader task
            self.read_task = asyncio.create_task(self._read_loop())
    
    async def connect(self, websocket: WebSocket):
        """Connect a new WebSocket to this session."""
        self.websockets.append(websocket)
        # Replay history
        try:
            for chunk in self.history:
                await websocket.send_bytes(chunk)
        except Exception as e:
            print(f"Error replaying history: {e}")
            
    def disconnect(self, websocket: WebSocket):
        """Disconnect a WebSocket."""
        if websocket in self.websockets:
            self.websockets.remove(websocket)
            
    def resize(self, cols: int, rows: int):
        """Resize the terminal."""
        if self.fd:
            try:
                winsize = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)
            except OSError:
                pass
    
    def is_idle_timeout(self) -> bool:
        """Check if session has exceeded idle timeout."""
        return (time.time() - self.last_activity) > self.idle_timeout
    
    async def _read_loop(self):
        """Read output from PTY and broadcast to WebSockets."""
        while self.running:
            try:
                # Check idle timeout
                if self.is_idle_timeout():
                    # Send timeout message
                    timeout_msg = b"\r\n\x1b[33m[Session timed out due to inactivity]\x1b[0m\r\n"
                    for ws in self.websockets:
                        try:
                            await ws.send_bytes(timeout_msg)
                        except:
                            pass
                    break
                
                # Check if data available
                r, _, _ = select.select([self.fd], [], [], 0.1)
                
                if self.fd in r:
                    try:
                        output = os.read(self.fd, 4096)
                        if output:
                            # Update activity
                            self.last_activity = time.time()
                            
                            # Add to buffer (with size limit)
                            if self.history_bytes < self.max_history_bytes:
                                self.history.append(output)
                                self.history_bytes += len(output)
                            
                            # Broadcast to all connected clients
                            disconnected = []
                            for ws in self.websockets:
                                try:
                                    await ws.send_bytes(output)
                                except Exception:
                                    disconnected.append(ws)
                            
                            # Cleanup disconnected
                            for ws in disconnected:
                                self.disconnect(ws)
                        else:
                            # EOF (Shell exited)
                            break
                    except OSError:
                        break
                
                await asyncio.sleep(0.01)
                
            except Exception as e:
                print(f"Terminal read error: {e}")
                break
        
        # Cleanup when shell exits
        self.stop()
    
    async def write_input(self, data: bytes):
        """Write input to PTY with size limit."""
        if self.fd and self.running:
            # Enforce message size limit
            if len(data) > settings.terminal_max_message_size:
                data = data[:settings.terminal_max_message_size]
            try:
                self.last_activity = time.time()
                os.write(self.fd, data)
            except OSError as e:
                print(f"Terminal write error: {e}")
    
    def stop(self):
        """Stop the terminal session."""
        self.running = False
        
        # Close all websockets
        self.websockets.clear()
        
        # Kill process
        if self.pid:
            try:
                os.kill(self.pid, signal.SIGTERM)
                os.waitpid(self.pid, 0)
            except (OSError, ChildProcessError):
                pass
            self.pid = None
        
        # Close FD
        if self.fd:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None
            
        # Remove from global sessions
        if self.session_id in active_sessions:
            del active_sessions[self.session_id]


# Store active sessions: session_id -> TerminalSession
active_sessions: Dict[str, TerminalSession] = {}


@router.websocket("/ws")
async def terminal_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for terminal access.
    
    Handshake must include:
    - token: access_token (required)
    - mode: "restricted" or "full" (default: settings.terminal_mode_default)
    - breakglass_token: required if mode="full"
    - cols, rows: terminal size
    """
    await websocket.accept()
    
    session: Optional[TerminalSession] = None
    user_info = None
    
    try:
        # Wait for handshake
        auth_data = await websocket.receive_json()
        token = auth_data.get("token")
        mode = auth_data.get("mode", settings.terminal_mode_default)
        breakglass_token = auth_data.get("breakglass_token")
        
        # Validate access token
        if not token:
            await websocket.send_json({"error": "No token provided"})
            await websocket.close()
            return
        
        # Verify token and role
        try:
            user_info = await _validate_token(token)
            if user_info["role"] not in ("admin", "operator"):
                await websocket.send_json({"error": "Unauthorized: Admin or Operator role required"})
                await websocket.close()
                return
        except Exception as e:
            await websocket.send_json({"error": str(e)})
            await websocket.close()
            return
        
        # Check mode
        if mode == "full":
            # Full PTY mode requires break-glass token
            if not breakglass_token:
                await websocket.send_json({
                    "error": "Break-glass token required for full shell access",
                    "code": "BREAKGLASS_REQUIRED"
                })
                await websocket.close()
                return
            
            # Validate break-glass token
            if not await validate_breakglass_token(breakglass_token, user_info["id"]):
                await websocket.send_json({
                    "error": "Invalid or expired break-glass token",
                    "code": "BREAKGLASS_INVALID"
                })
                await websocket.close()
                return
            
            # Log connection
            await log_terminal_event(
                "terminal_connect_full",
                user_info["id"],
                details="Full PTY mode"
            )
            
            # Get terminal size
            cols = auth_data.get("cols", 80)
            rows = auth_data.get("rows", 24)
            requested_session_id = auth_data.get("session_id")
            
            # Determine session ID
            if requested_session_id and requested_session_id in active_sessions:
                # Reattach to existing session
                session = active_sessions[requested_session_id]
                session.resize(cols, rows)
            else:
                # Create new session
                import uuid
                new_session_id = requested_session_id or str(uuid.uuid4())
                session = TerminalSession(new_session_id, user_info["id"], user_info["username"])
                active_sessions[new_session_id] = session
                await session.start(cols, rows)
            
            # Connect this websocket to the session
            await session.connect(websocket)
            
            # Send ready signal
            await websocket.send_json({
                "status": "connected",
                "mode": "full",
                "session_id": session.session_id
            })
            
            # Handle incoming data
            while True:
                try:
                    message = await asyncio.wait_for(
                        websocket.receive(),
                        timeout=60.0
                    )
                    
                    if message["type"] == "websocket.receive":
                        if "bytes" in message:
                            await session.write_input(message["bytes"])
                        elif "text" in message:
                            data = message["text"]
                            # Check for resize command
                            if data.startswith('{"resize":'):
                                import json
                                try:
                                    resize_data = json.loads(data)
                                    if "resize" in resize_data:
                                        session.resize(
                                            resize_data["resize"]["cols"],
                                            resize_data["resize"]["rows"]
                                        )
                                except:
                                    pass
                            else:
                                await session.write_input(data.encode())
                                
                except asyncio.TimeoutError:
                    pass
                except WebSocketDisconnect:
                    break
        
        elif mode == "restricted":
            # Restricted mode - command execution only (no PTY)
            await log_terminal_event(
                "terminal_connect_restricted",
                user_info["id"],
                details="Restricted mode"
            )
            
            await websocket.send_json({
                "status": "connected",
                "mode": "restricted",
                "allowed_commands": settings.terminal_allowed_commands_list
            })
            
            # Handle restricted commands via WebSocket
            while True:
                try:
                    message = await websocket.receive_json()
                    
                    if message.get("type") == "command":
                        command = message.get("command", "")
                        
                        # Validate and execute
                        is_valid, error = validate_restricted_command(command)
                        
                        if not is_valid:
                            await websocket.send_json({
                                "type": "error",
                                "error": error
                            })
                            continue
                        
                        import subprocess
                        try:
                            result = subprocess.run(
                                command,
                                shell=True,
                                capture_output=True,
                                text=True,
                                timeout=30
                            )
                            await websocket.send_json({
                                "type": "output",
                                "command": command,
                                "output": result.stdout + result.stderr,
                                "exit_code": result.returncode
                            })
                        except subprocess.TimeoutExpired:
                            await websocket.send_json({
                                "type": "output",
                                "command": command,
                                "output": "Command timed out",
                                "exit_code": 124
                            })
                        
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    await websocket.send_json({"type": "error", "error": str(e)})
        
        else:
            await websocket.send_json({"error": f"Invalid mode: {mode}"})
            await websocket.close()
            return
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Terminal WebSocket error: {e}")
    finally:
        # Log disconnect
        if user_info:
            await log_terminal_event(
                "terminal_disconnect",
                user_info["id"],
                details=f"Mode: {mode if 'mode' in dir() else 'unknown'}"
            )
        
        if session:
            session.disconnect(websocket)


# ============================================================================
# Legacy Command Execution (for mobile app / scripts)
# ============================================================================

@router.post("/exec", response_model=CommandResponse)
async def execute_command(
    request: CommandRequest,
    user: dict = Depends(require_role("admin"))
):
    """Execute a simple command and return output (for mobile app)."""
    import subprocess
    
    # Security: Block dangerous commands
    dangerous = ['rm -rf', ':(){', '> /dev', 'mkfs']
    for d in dangerous:
        if d in request.command:
            return CommandResponse(output=f"Command blocked: {d}", exit_code=1)
    
    try:
        result = subprocess.run(
            request.command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        output = result.stdout + result.stderr
        return CommandResponse(output=output or "(no output)", exit_code=result.returncode)
    except subprocess.TimeoutExpired:
        return CommandResponse(output="Command timed out (30s limit)", exit_code=124)
    except Exception as e:
        return CommandResponse(output=str(e), exit_code=1)
