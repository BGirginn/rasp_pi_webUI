"""
Pi Control Panel - Terminal Router

WebSocket-based terminal for browser access to shell.
Uses PTY for real terminal experience.
"""

import asyncio
import os
import pty
import select
import signal
import struct
import fcntl
import termios
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

router = APIRouter()


class TerminalSession:
    """Manages a PTY terminal session."""
    
    def __init__(self, websocket: WebSocket, user: str):
        self.websocket = websocket
        self.user = user
        self.fd: Optional[int] = None
        self.pid: Optional[int] = None
        self.running = False
    
    async def start(self, cols: int = 80, rows: int = 24):
        """Start a new terminal session."""
        # Fork a pseudo-terminal
        self.pid, self.fd = pty.fork()
        
        if self.pid == 0:
            # Child process - execute shell
            os.environ["TERM"] = "xterm-256color"
            os.environ["COLORTERM"] = "truecolor"
            
            # Execute bash or sh
            shell = os.environ.get("SHELL", "/bin/bash")
            os.execvp(shell, [shell, "-l"])
        else:
            # Parent process
            self.running = True
            
            # Set terminal size
            self.resize(cols, rows)
            
            # Set non-blocking
            flags = fcntl.fcntl(self.fd, fcntl.F_GETFL)
            fcntl.fcntl(self.fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    
    def resize(self, cols: int, rows: int):
        """Resize the terminal."""
        if self.fd:
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)
    
    async def read_output(self):
        """Read output from PTY and send to WebSocket."""
        while self.running:
            try:
                # Check if data available
                r, _, _ = select.select([self.fd], [], [], 0.1)
                
                if self.fd in r:
                    output = os.read(self.fd, 4096)
                    if output:
                        await self.websocket.send_bytes(output)
                    else:
                        # EOF
                        break
                
                await asyncio.sleep(0.01)
                
            except OSError:
                break
            except Exception as e:
                print(f"Terminal read error: {e}")
                break
        
        self.running = False
    
    async def write_input(self, data: bytes):
        """Write input to PTY."""
        if self.fd and self.running:
            try:
                os.write(self.fd, data)
            except OSError as e:
                print(f"Terminal write error: {e}")
    
    def stop(self):
        """Stop the terminal session."""
        self.running = False
        
        if self.pid:
            try:
                os.kill(self.pid, signal.SIGTERM)
                os.waitpid(self.pid, 0)
            except (OSError, ChildProcessError):
                pass
        
        if self.fd:
            try:
                os.close(self.fd)
            except OSError:
                pass


# Store active sessions
active_sessions: dict = {}


@router.websocket("/ws")
async def terminal_websocket(websocket: WebSocket):
    """WebSocket endpoint for terminal access."""
    await websocket.accept()
    
    session = None
    
    try:
        # Wait for auth token
        auth_data = await websocket.receive_json()
        token = auth_data.get("token")
        
        if not token:
            await websocket.send_json({"error": "No token provided"})
            await websocket.close()
            return
        
        # Verify token (simplified - in production use proper JWT verification)
        # For now, accept any token that was provided
        user = auth_data.get("user", "terminal")
        
        # Get terminal size
        cols = auth_data.get("cols", 80)
        rows = auth_data.get("rows", 24)
        
        # Create session
        session = TerminalSession(websocket, user)
        await session.start(cols, rows)
        
        # Send success
        await websocket.send_json({"status": "connected"})
        
        # Start reading output in background
        read_task = asyncio.create_task(session.read_output())
        
        # Handle incoming data
        while session.running:
            try:
                message = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=0.1
                )
                
                if message["type"] == "websocket.receive":
                    if "bytes" in message:
                        await session.write_input(message["bytes"])
                    elif "text" in message:
                        data = message["text"]
                        # Check for resize command
                        if data.startswith('{"resize":'):
                            import json
                            resize_data = json.loads(data)
                            if "resize" in resize_data:
                                session.resize(
                                    resize_data["resize"]["cols"],
                                    resize_data["resize"]["rows"]
                                )
                        else:
                            await session.write_input(data.encode())
                            
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                break
        
        read_task.cancel()
        
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Terminal WebSocket error: {e}")
        try:
            await websocket.send_json({"error": str(e)})
        except:
            pass
        if session:
            session.stop()
        try:
            await websocket.close()
        except:
            pass


# Simple command execution for mobile app
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
    dangerous = ['rm -rf', 'mkfs', 'dd if=', ':(){', 'chmod 777', '> /dev']
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

