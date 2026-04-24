"""
Host Command Execution Helper

Native mode: Executes commands directly on the system.
Container mode: Uses SSH to connect to the host via the gateway IP.
"""

import asyncio
import subprocess
import os
from typing import Tuple


def is_running_in_container() -> bool:
    """Check if running inside a container."""
    if os.path.exists("/run/.containerenv"):
        return True
    try:
        with open("/proc/1/cgroup", "r") as f:
            return "container" in f.read()
    except Exception:
        return False


def run_native_command(command: str, timeout: int = 30) -> Tuple[str, str, int]:
    """Execute a command directly on the system."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", 124
    except Exception as e:
        return "", str(e), 1


def get_host_gateway() -> str:
    """Get the host gateway IP."""
    try:
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout:
            parts = result.stdout.split()
            if len(parts) >= 3:
                return parts[2]
    except Exception:
        pass
    return "host.internal"


def run_container_host_command(command: str, timeout: int = 30) -> Tuple[str, str, int]:
    """
    Execute a command on the host system via SSH (for container mode).

    Returns:
        Tuple of (stdout, stderr, returncode)
    """
    gateway = get_host_gateway()
    ssh_password = os.environ.get("SSH_HOST_PASSWORD", "1")
    ssh_user = os.environ.get("SSH_HOST_USER") or subprocess.run(
        ["whoami"], capture_output=True, text=True
    ).stdout.strip() or "pi"

    try:
        result = subprocess.run(
            [
                "sshpass",
                "-p",
                ssh_password,
                "ssh",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-o",
                "LogLevel=ERROR",
                "-o",
                f"ConnectTimeout={min(timeout, 10)}",
                f"{ssh_user}@{gateway}",
                command,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", 124
    except Exception as e:
        return "", str(e), 1


def run_host_command(command: str, timeout: int = 30) -> Tuple[str, str, int]:
    """
    Execute a command on the host system.

    Automatically detects if running in container or native mode.
    """
    if is_running_in_container():
        return run_container_host_command(command, timeout)
    return run_native_command(command, timeout)


def run_host_command_simple(command: str, timeout: int = 30) -> str:
    """Execute a command on host and return stdout only."""
    stdout, stderr, code = run_host_command(command, timeout)
    return stdout if code == 0 else ""


async def run_host_command_async(command: str, timeout: int = 30) -> str:
    """Execute a command on host asynchronously and return stdout only."""
    return await asyncio.to_thread(run_host_command_simple, command, timeout)
