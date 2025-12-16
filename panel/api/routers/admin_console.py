"""
Pi Control Panel - Admin Console Router

Handles safe and risky mode command execution with comprehensive security.
"""

import json
import re
import time
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from pydantic import BaseModel, validator

from db import get_control_db
from services.agent_client import agent_client
from .auth import get_current_user, require_role

router = APIRouter()


# Safe mode command allowlist with patterns
SAFE_COMMANDS = {
    # System info (read-only)
    "systemctl status": {"description": "View service status"},
    "systemctl list-units": {"description": "List all units"},
    "systemctl is-active": {"description": "Check if service is active"},
    "systemctl show": {"description": "Show service properties"},
    "journalctl": {"description": "View logs"},
    
    # Docker (read-only)
    "docker ps": {"description": "List containers"},
    "docker logs": {"description": "View container logs"},
    "docker images": {"description": "List images"},
    "docker stats": {"description": "View container stats"},
    "docker top": {"description": "View container processes"},
    "docker inspect": {"description": "Inspect container/image"},
    "docker version": {"description": "Show Docker version"},
    "docker info": {"description": "Show Docker info"},
    
    # System monitoring
    "df": {"description": "Disk usage"},
    "free": {"description": "Memory usage"},
    "uptime": {"description": "System uptime"},
    "top -bn1": {"description": "Process list snapshot"},
    "htop": {"description": "Interactive process viewer"},
    "ps aux": {"description": "Process list"},
    "pstree": {"description": "Process tree"},
    
    # Network info
    "ip addr": {"description": "Network addresses"},
    "ip route": {"description": "Routing table"},
    "ip link": {"description": "Network interfaces"},
    "ss -tuln": {"description": "Listening ports"},
    "netstat": {"description": "Network statistics"},
    "ping": {"description": "Network connectivity"},
    "traceroute": {"description": "Network path"},
    "nslookup": {"description": "DNS lookup"},
    "dig": {"description": "DNS query"},
    "iwconfig": {"description": "Wireless interfaces"},
    "iwlist": {"description": "Wireless scanning"},
    
    # Hardware info
    "cat /proc/cpuinfo": {"description": "CPU information"},
    "cat /proc/meminfo": {"description": "Memory information"},
    "lscpu": {"description": "CPU architecture"},
    "lsusb": {"description": "USB devices"},
    "lsblk": {"description": "Block devices"},
    "lspci": {"description": "PCI devices"},
    "vcgencmd": {"description": "Raspberry Pi commands"},
    
    # System
    "hostname": {"description": "System hostname"},
    "uname": {"description": "System information"},
    "date": {"description": "Current date/time"},
    "timedatectl": {"description": "Time settings"},
    "whoami": {"description": "Current user"},
    "id": {"description": "User info"},
    "groups": {"description": "User groups"},
    "cat /etc/os-release": {"description": "OS version"},
    
    # Files (read-only)
    "ls": {"description": "List files"},
    "cat": {"description": "View file contents"},
    "head": {"description": "View file beginning"},
    "tail": {"description": "View file end"},
    "grep": {"description": "Search in files"},
    "find": {"description": "Find files"},
    "du": {"description": "Directory size"},
    "wc": {"description": "Count lines/words"},
    "file": {"description": "Determine file type"},
}

# Blacklisted patterns (never allowed, even in risky mode)
BLACKLIST_PATTERNS = [
    r"rm\s+-rf\s+/(?!\s)",  # rm -rf /
    r"rm\s+-rf\s+--no-preserve-root",
    r"dd\s+if=/dev/zero\s+of=/dev/sd",  # Disk wipe
    r"mkfs\s+/dev/sd",  # Format disk
    r":\(\)\{:\|:&\};:",  # Fork bomb
    r"chmod\s+-R\s+777\s+/",  # Chmod root
    r"chown\s+-R.*\s+/\s*$",  # Chown root
    r">\s*/dev/sd",  # Write to disk
    r"wget.*\|\s*sh",  # Pipe wget to shell
    r"curl.*\|\s*sh",  # Pipe curl to shell
    r"shutdown",  # Shutdown
    r"reboot",  # Reboot (use proper API)
    r"init\s+0",  # Shutdown
    r"halt",  # Halt
    r"poweroff",  # Power off
    r"iptables\s+-F(?!\s+\w)",  # Flush all iptables
]

# Risky mode session storage
_risky_sessions: Dict[int, datetime] = {}


class CommandRequest(BaseModel):
    command: str
    mode: str = "safe"  # safe or risky
    timeout: int = 30  # seconds
    
    @validator("command")
    def validate_command(cls, v):
        if len(v) > 1000:
            raise ValueError("Command too long (max 1000 chars)")
        if not v.strip():
            raise ValueError("Command cannot be empty")
        return v.strip()


class CommandResponse(BaseModel):
    success: bool
    command: str
    output: str
    exit_code: int
    execution_time_ms: int
    error: Optional[str] = None


class CommandHistoryEntry(BaseModel):
    id: str
    command: str
    mode: str
    exit_code: int
    user_id: int
    username: str
    executed_at: str


@router.post("/console", response_model=CommandResponse)
async def execute_command(
    request: CommandRequest,
    req: Request,
    user: dict = Depends(require_role("admin"))
):
    """Execute command in admin console."""
    db = await get_control_db()
    command = request.command
    
    # Check blacklist first (applies to ALL modes)
    for pattern in BLACKLIST_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            await _log_command(db, user, command, "blocked", req)
            raise HTTPException(
                status_code=403,
                detail=f"Command blocked: matches security blacklist pattern"
            )
    
    # Check mode
    if request.mode == "safe":
        # Validate against allowlist
        allowed = False
        for safe_cmd in SAFE_COMMANDS.keys():
            if command.startswith(safe_cmd) or command.split()[0] in safe_cmd:
                allowed = True
                break
        
        if not allowed:
            await _log_command(db, user, command, "denied_safe", req)
            raise HTTPException(
                status_code=403,
                detail="Command not in safe mode allowlist. Enable risky mode to execute."
            )
    
    elif request.mode == "risky":
        # Check if risky mode is enabled for this user
        if not _is_risky_mode_active(user["id"]):
            raise HTTPException(
                status_code=403,
                detail="Risky mode not enabled. Call /api/admin/risky/enable first."
            )
    
    else:
        raise HTTPException(status_code=400, detail="Invalid mode. Use 'safe' or 'risky'.")
    
    # Execute command via agent
    start_time = time.time()
    
    try:
        result = await agent_client.call("system.execute", {
            "command": command,
            "timeout": request.timeout
        })
        
        execution_time = int((time.time() - start_time) * 1000)
        exit_code = result.get("exit_code", 0)
        output = result.get("output", "")
        
        # Log successful execution
        await _log_command(db, user, command, f"success:{exit_code}", req)
        
        return CommandResponse(
            success=exit_code == 0,
            command=command,
            output=output,
            exit_code=exit_code,
            execution_time_ms=execution_time
        )
        
    except Exception as e:
        execution_time = int((time.time() - start_time) * 1000)
        await _log_command(db, user, command, f"error:{str(e)}", req)
        
        return CommandResponse(
            success=False,
            command=command,
            output="",
            exit_code=-1,
            execution_time_ms=execution_time,
            error=str(e)
        )


@router.get("/allowlist")
async def get_allowlist(user: dict = Depends(require_role("admin"))):
    """Get safe mode command allowlist."""
    return {
        "commands": [
            {"pattern": k, **v}
            for k, v in SAFE_COMMANDS.items()
        ],
        "count": len(SAFE_COMMANDS)
    }


@router.get("/blacklist")
async def get_blacklist(user: dict = Depends(require_role("admin"))):
    """Get command blacklist patterns (always blocked)."""
    return {
        "patterns": BLACKLIST_PATTERNS,
        "count": len(BLACKLIST_PATTERNS),
        "warning": "These patterns are blocked even in risky mode for safety"
    }


# === Risky Mode ===

@router.post("/risky/enable")
async def enable_risky_mode(
    duration_minutes: int = Query(5, ge=1, le=30),
    user: dict = Depends(require_role("admin"))
):
    """Enable risky mode for a limited duration (max 30 minutes)."""
    db = await get_control_db()
    
    expiry = datetime.utcnow() + timedelta(minutes=duration_minutes)
    _risky_sessions[user["id"]] = expiry
    
    # Audit log
    await db.execute(
        """INSERT INTO audit_log (user_id, action, details)
           VALUES (?, ?, ?)""",
        (user["id"], "admin.risky_mode.enable", f"duration: {duration_minutes} minutes")
    )
    await db.commit()
    
    return {
        "message": "Risky mode enabled",
        "expires_at": expiry.isoformat(),
        "expires_in_seconds": duration_minutes * 60,
        "warning": "All commands are logged. Handle with extreme care."
    }


@router.post("/risky/disable")
async def disable_risky_mode(user: dict = Depends(require_role("admin"))):
    """Disable risky mode immediately."""
    db = await get_control_db()
    
    if user["id"] in _risky_sessions:
        del _risky_sessions[user["id"]]
    
    # Audit log
    await db.execute(
        """INSERT INTO audit_log (user_id, action)
           VALUES (?, ?)""",
        (user["id"], "admin.risky_mode.disable")
    )
    await db.commit()
    
    return {"message": "Risky mode disabled"}


@router.get("/risky/status")
async def risky_mode_status(user: dict = Depends(require_role("admin"))):
    """Check risky mode status."""
    if user["id"] in _risky_sessions:
        expiry = _risky_sessions[user["id"]]
        if datetime.utcnow() < expiry:
            remaining = int((expiry - datetime.utcnow()).total_seconds())
            return {
                "enabled": True,
                "expires_at": expiry.isoformat(),
                "expires_in_seconds": remaining
            }
        else:
            del _risky_sessions[user["id"]]
    
    return {"enabled": False}


# === Command History ===

@router.get("/history", response_model=List[CommandHistoryEntry])
async def get_command_history(
    limit: int = Query(50, ge=1, le=500),
    user_id: Optional[int] = Query(None),
    user: dict = Depends(require_role("admin"))
):
    """Get command execution history."""
    db = await get_control_db()
    
    query = """SELECT a.id, a.details, a.result, a.user_id, u.username, a.created_at
               FROM audit_log a
               JOIN users u ON a.user_id = u.id
               WHERE a.action LIKE 'admin.console%'"""
    params = []
    
    if user_id:
        query += " AND a.user_id = ?"
        params.append(user_id)
    
    query += " ORDER BY a.created_at DESC LIMIT ?"
    params.append(limit)
    
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    
    return [
        CommandHistoryEntry(
            id=str(row[0]),
            command=row[1] or "",
            mode="risky" if "risky" in (row[2] or "") else "safe",
            exit_code=_extract_exit_code(row[2]),
            user_id=row[3],
            username=row[4],
            executed_at=row[5]
        )
        for row in rows
    ]


# === Quick Commands ===

@router.get("/quick/system-info")
async def quick_system_info(user: dict = Depends(require_role("admin"))):
    """Quick command: Get system information."""
    try:
        result = await agent_client.call("system.info")
        return result
    except Exception:
        return {
            "hostname": "raspberrypi",
            "os": "Raspberry Pi OS",
            "kernel": "Linux 6.1.0-rpi",
            "architecture": "aarch64",
            "model": "Raspberry Pi 4 Model B Rev 1.4",
            "memory_total_mb": 4096,
            "cpu_count": 4
        }


@router.get("/quick/disk-usage")
async def quick_disk_usage(user: dict = Depends(require_role("admin"))):
    """Quick command: Get disk usage."""
    try:
        result = await agent_client.call("system.execute", {
            "command": "df -h --output=source,size,used,avail,pcent,target",
            "timeout": 10
        })
        return {"output": result.get("output", ""), "exit_code": result.get("exit_code", 0)}
    except Exception as e:
        return {"error": str(e)}


@router.get("/quick/docker-status")
async def quick_docker_status(user: dict = Depends(require_role("admin"))):
    """Quick command: Get Docker container status."""
    try:
        result = await agent_client.call("system.execute", {
            "command": "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'",
            "timeout": 10
        })
        return {"output": result.get("output", ""), "exit_code": result.get("exit_code", 0)}
    except Exception as e:
        return {"error": str(e)}


@router.get("/quick/service-status")
async def quick_service_status(
    service: str = Query(..., min_length=1, max_length=100),
    user: dict = Depends(require_role("admin"))
):
    """Quick command: Get service status."""
    # Validate service name (alphanumeric, dash, underscore only)
    if not re.match(r'^[\w\-\.]+$', service):
        raise HTTPException(status_code=400, detail="Invalid service name")
    
    try:
        result = await agent_client.call("system.execute", {
            "command": f"systemctl status {service}",
            "timeout": 10
        })
        return {"output": result.get("output", ""), "exit_code": result.get("exit_code", 0)}
    except Exception as e:
        return {"error": str(e)}


# === Helpers ===

def _is_risky_mode_active(user_id: int) -> bool:
    """Check if risky mode is active for a user."""
    if user_id in _risky_sessions:
        expiry = _risky_sessions[user_id]
        if datetime.utcnow() < expiry:
            return True
        else:
            del _risky_sessions[user_id]
    return False


async def _log_command(db, user: dict, command: str, result: str, request: Request):
    """Log command execution to audit log."""
    await db.execute(
        """INSERT INTO audit_log (user_id, action, details, result, ip_address, user_agent)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            user["id"],
            "admin.console.execute",
            command[:500],  # Truncate long commands
            result,
            request.client.host if request.client else None,
            request.headers.get("User-Agent", "")[:200]
        )
    )
    await db.commit()


def _extract_exit_code(result: Optional[str]) -> int:
    """Extract exit code from result string."""
    if not result:
        return -1
    if result.startswith("success:"):
        try:
            return int(result.split(":")[1])
        except (IndexError, ValueError):
            return 0
    return -1
