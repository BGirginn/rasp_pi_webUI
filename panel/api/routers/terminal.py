"""
Pi Control Panel - Terminal Router

WebSocket-based terminal for browser access to shell.
Uses PTY for real terminal experience with session persistence.
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
from typing import Optional, List, Dict
from collections import deque

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

router = APIRouter()


class TerminalSession:
    """Manages a persistent PTY terminal session."""
    
    def __init__(self, session_id: str, user: str):
        self.session_id = session_id
        self.user = user
        self.fd: Optional[int] = None
        self.pid: Optional[int] = None
        self.running = False
        self.websockets: List[WebSocket] = []
        # Circular buffer for history (store last ~1MB of output)
        self.history = deque(maxlen=200) 
        self.read_task: Optional[asyncio.Task] = None
        self.last_activity = time.time()
    
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
        """Start a new terminal session - native bash or SSH via Docker."""
        if self.running:
            return

        # Fork a pseudo-terminal
        self.pid, self.fd = pty.fork()
        
        if self.pid == 0:
            # Child process
            os.environ["TERM"] = "xterm-256color"
            os.environ["COLORTERM"] = "truecolor"
            
            # Check if running in Docker or native mode
            in_docker = self._is_running_in_docker()
            
            if in_docker:
                # Docker mode: SSH to host via gateway
                import subprocess
                try:
                    result = subprocess.run(
                        ["ip", "route", "show", "default"],
                        capture_output=True, text=True
                    )
                    gateway = result.stdout.split()[2] if result.stdout else "host.docker.internal"
                except:
                    gateway = "host.docker.internal"
                
                ssh_password = os.environ.get("SSH_HOST_PASSWORD", "1")
                # Get SSH user from environment or detect dynamically
                import subprocess as sp
                ssh_user = os.environ.get("SSH_HOST_USER") or sp.run(
                    ["whoami"], capture_output=True, text=True
                ).stdout.strip() or "pi"
                # Use sshpass to auto-login
                os.execvp("sshpass", [
                    "sshpass", "-p", ssh_password,
                    "ssh",
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null",
                    "-o", "LogLevel=ERROR",
                    f"{ssh_user}@{gateway}",
                ])
            else:
                # Native mode: Direct bash shell
                # Use bash -l for login shell behavior
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
    
    async def _read_loop(self):
        """Read output from PTY and broadcast to WebSockets."""
        while self.running:
            try:
                # Check if data available
                r, _, _ = select.select([self.fd], [], [], 0.1)
                
                if self.fd in r:
                    try:
                        output = os.read(self.fd, 4096)
                        if output:
                            # Update activity
                            self.last_activity = time.time()
                            
                            # Add to buffer
                            self.history.append(output)
                            
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
        """Write input to PTY."""
        if self.fd and self.running:
            try:
                self.last_activity = time.time()
                os.write(self.fd, data)
            except OSError as e:
                print(f"Terminal write error: {e}")
    
    def stop(self):
        """Stop the terminal session."""
        self.running = False
        
        # Close all websockets
        # Note: We can't await here easily if called from sync context, 
        # but the task will be cancelled.
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
    """WebSocket endpoint for terminal access."""
    await websocket.accept()
    
    session: Optional[TerminalSession] = None
    
    try:
        # Wait for handshake (includes token and session_id)
        auth_data = await websocket.receive_json()
        token = auth_data.get("token")
        requested_session_id = auth_data.get("session_id")
        
        # In a real app, verify JWT here. 
        # For now we trust the client has a token (even if dummy)
        if not token:
            await websocket.send_json({"error": "No token provided"})
            await websocket.close()
            return
            
        # Get terminal size
        cols = auth_data.get("cols", 80)
        rows = auth_data.get("rows", 24)
        user = auth_data.get("user", "terminal")
        
        # Determine session ID
        if requested_session_id and requested_session_id in active_sessions:
            # Reattach to existing session
            session = active_sessions[requested_session_id]
            # Resize to match new client
            session.resize(cols, rows)
            print(f"Reattaching to session {requested_session_id}")
        else:
            # Create new session
            # If no ID provided, generate one
            import uuid
            new_session_id = requested_session_id or str(uuid.uuid4())
            session = TerminalSession(new_session_id, user)
            active_sessions[new_session_id] = session
            await session.start(cols, rows)
            print(f"Created new session {new_session_id}")
        
        # Connect this websocket to the session
        await session.connect(websocket)
        
        # Send ready signal
        await websocket.send_json({
            "status": "connected", 
            "session_id": session.session_id
        })
        
        # Handle incoming data from this client
        while True:
            try:
                message = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=60.0 # Keep-alive check
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
                # Send keepalive ping? Or just loop. 
                # Actually browser might close if idle.
                 # Just sending a ping frame is handled by protocol usually.
                 pass
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Terminal WebSocket error: {e}")
    finally:
        if session:
            session.disconnect(websocket)
            # We DO NOT stop the session here. That's the whole point.
            # It stops only if the shell process exits (handled in _read_loop).


# Simple command execution for mobile app / scripts
class CommandRequest(BaseModel):
    command: str


class CommandResponse(BaseModel):
    output: str
    exit_code: int


@router.post("/exec", response_model=CommandResponse)
async def execute_command(request: CommandRequest):
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
