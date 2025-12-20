"""
Test No Shell Surface
Validates that no shell/pty/terminal/subprocess exists in codebase per AI_RULES.md R2.1
"""

import pytest
import subprocess
import re


def test_no_shell_true_in_panel_api():
    """Verify no shell=True in panel/api codebase."""
    result = subprocess.run(
        ["grep", "-r", "shell=True", "panel/api", "--include=*.py"],
        capture_output=True,
        text=True,
        cwd="/Users/bgirginn/Desktop/Rasp_pi_webui"
    )
    
    # grep returns 1 if no matches (which is what we want)
    assert result.returncode == 1, f"Found shell=True in codebase:\n{result.stdout}"


def test_no_pty_in_panel_api():
    """Verify no pty usage in panel/api codebase."""
    result = subprocess.run(
        ["grep", "-r", "import pty", "panel/api", "--include=*.py"],
        capture_output=True,
        text=True,
        cwd="/Users/bgirginn/Desktop/Rasp_pi_webui"
    )
    
    assert result.returncode == 1, f"Found pty import in codebase:\n{result.stdout}"


def test_no_execvp_in_panel_api():
    """Verify no execvp in panel/api codebase."""
    result = subprocess.run(
        ["grep", "-r", "execvp", "panel/api", "--include=*.py"],
        capture_output=True,
        text=True,
        cwd="/Users/bgirginn/Desktop/Rasp_pi_webui"
    )
    
    assert result.returncode == 1, f"Found execvp in codebase:\n{result.stdout}"


def test_no_terminal_router():
    """Verify terminal router does not exist."""
    import os
    terminal_path = "/Users/bgirginn/Desktop/Rasp_pi_webui/panel/api/routers/terminal.py"
    assert not os.path.exists(terminal_path), "terminal.py should not exist"


def test_no_host_exec_direct():
    """Verify host_exec is only a stub."""
    import os
    host_exec_path = "/Users/bgirginn/Desktop/Rasp_pi_webui/panel/api/services/host_exec.py"
    
    if os.path.exists(host_exec_path):
        with open(host_exec_path, 'r') as f:
            content = f.read()
        
        # Should only be a stub
        assert "DEPRECATED" in content or "STUB" in content, "host_exec should be deprecated/stub only"
        assert "subprocess" not in content.lower(), "host_exec stub should not use subprocess"
