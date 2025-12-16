"""
Host Command Execution Helper

Native mode: Executes commands directly on the system.
Docker mode: Uses SSH to connect to the host via the gateway IP.
"""

import subprocess
import os
from typing import Tuple


def is_running_in_docker() -> bool:
    """Check if running inside a Docker container."""
    # Check for Docker-specific files
    if os.path.exists("/.dockerenv"):
        return True
    # Check cgroup
    try:
        with open("/proc/1/cgroup", "r") as f:
            return "docker" in f.read()
    except:
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
    """Get the Docker host gateway IP."""
    try:
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout:
            # Parse: default via 172.19.0.1 dev eth0
            parts = result.stdout.split()
            if len(parts) >= 3:
                return parts[2]
    except:
        pass
    return "host.docker.internal"


def run_docker_host_command(command: str, timeout: int = 30) -> Tuple[str, str, int]:
    """
    Execute a command on the host system via SSH (for Docker mode).
    
    Returns:
        Tuple of (stdout, stderr, returncode)
    """
    gateway = get_host_gateway()
    ssh_password = os.environ.get("SSH_HOST_PASSWORD", "1")
    ssh_user = os.environ.get("SSH_HOST_USER", "bgirgin")
    
    try:
        result = subprocess.run(
            [
                "sshpass", "-p", ssh_password,
                "ssh",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "LogLevel=ERROR",
                "-o", f"ConnectTimeout={min(timeout, 10)}",
                f"{ssh_user}@{gateway}",
                command
            ],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", 124
    except Exception as e:
        return "", str(e), 1


def run_host_command(command: str, timeout: int = 30) -> Tuple[str, str, int]:
    """
    Execute a command on the host system.
    
    Automatically detects if running in Docker or native mode.
    """
    if is_running_in_docker():
        return run_docker_host_command(command, timeout)
    else:
        return run_native_command(command, timeout)


def run_host_command_simple(command: str, timeout: int = 30) -> str:
    """Execute a command on host and return stdout only."""
    stdout, stderr, code = run_host_command(command, timeout)
    return stdout if code == 0 else ""
