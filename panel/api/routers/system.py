"""
Pi Control Panel - System Router

Handles system-level operations like reboot, shutdown, and updates.
"""

import asyncio
import subprocess
from datetime import datetime
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel

from db import get_control_db
from .auth import require_role, get_current_user

router = APIRouter()

class SystemInfo(BaseModel):
    hostname: str
    os_info: str
    kernel: str
    architecture: str
    model: str
    time: str
    uptime_seconds: int

class UpdateStatus(BaseModel):
    available: bool
    current_version: str
    latest_version: str
    last_check: str

async def execute_power_command(command_args: list):
    """Execute power command with a small delay to allow response to return."""
    await asyncio.sleep(2)
    # We use systemctl as it is whitelisted in sudoers
    subprocess.run(["sudo"] + command_args, check=False)

@router.get("/info", response_model=SystemInfo)
async def get_system_info(user: dict = Depends(get_current_user)):
    """Get detailed system information."""
    import platform
    import time
    
    # Get hostname
    try:
        with open("/etc/hostname", "r") as f:
            hostname = f.read().strip()
    except:
        hostname = platform.node()
        
    # Get OS info
    try:
        with open("/etc/os-release", "r") as f:
            os_info = "Linux"
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    os_info = line.split("=")[1].strip().strip('"')
                    break
    except:
        os_info = f"{platform.system()} {platform.release()}"
        
    # Get uptime
    try:
        with open("/proc/uptime", "r") as f:
            uptime = int(float(f.read().split()[0]))
    except:
        uptime = 0
        
    # Get model (Pi specific)
    model = "Generic Linux System"
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if line.startswith("Model"):
                    model = line.split(":")[1].strip()
                    break
    except:
        pass

    return SystemInfo(
        hostname=hostname,
        os_info=os_info,
        kernel=platform.release(),
        architecture=platform.machine(),
        model=model,
        time=datetime.now().isoformat(),
        uptime_seconds=uptime
    )

@router.post("/reboot")
async def reboot_system(
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_role("admin"))
):
    """Reboot the system."""
    db = await get_control_db()
    
    # Audit log
    await db.execute(
        "INSERT INTO audit_log (user_id, action, details) VALUES (?, ?, ?)",
        (user["id"], "system.reboot", "System reboot initiated via API")
    )
    await db.commit()
    
    # Schedule reboot
    background_tasks.add_task(execute_power_command, ["systemctl", "reboot"])
    
    return {"message": "System is rebooting..."}

@router.post("/shutdown")
async def shutdown_system(
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_role("admin"))
):
    """Shutdown the system."""
    db = await get_control_db()
    
    # Audit log
    await db.run(
        "INSERT INTO audit_logs (user_id, action, details, ip_address) VALUES (:uid, 'power.shutdown', 'System shutdown initiated', '127.0.0.1')",
        {"uid": user["id"]}
    )
    
    background_tasks.add_task(execute_power_command, ["systemctl", "poweroff"])
    return {"message": "System is shutting down..."}

@router.get("/processes")
async def get_processes(user: dict = Depends(get_current_user)):
    """Get top running processes."""
    import psutil
    
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'username']):
        try:
            # Use onshot to get info efficiently
            with p.oneshot():
                # cpu_percent(interval=None) returns 0.0 on first call, but subsequent calls work.
                # Since we can't persist process objects easily across requests in stateless HTTP, 
                # we might accept that CPU is 0 or try a small trick.
                # However, memory is accurate.
                cpu = p.cpu_percent(interval=None)
                mem = p.memory_info().rss / (1024 * 1024) # MB
                
                procs.append({
                    "pid": p.pid,
                    "name": p.name(),
                    "cpu": round(cpu, 1),
                    "memory": round(mem, 1)
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
            
    # Sort by memory usage descending (since CPU might be 0 often without persistent tracking)
    # Or sort by CPU if non-zero
    procs.sort(key=lambda x: x['memory'], reverse=True)
    
    return procs[:10] # Return top 10

@router.post("/update")
async def update_system(
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_role("admin"))
):
    """Trigger system update (git pull)."""
    # This assumes we are running in the repo and have permissions
    # Ideally this should trigger a properly defined job
    
    db = await get_control_db()
    
    await db.execute(
        "INSERT INTO audit_log (user_id, action, details) VALUES (?, ?, ?)",
        (user["id"], "system.update", "Update triggered via API")
    )
    await db.commit()
    
    return {"message": "Update check initiated (feature pending)"}
