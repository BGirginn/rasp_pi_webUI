"""
Test No Shell Surface
Validates that no shell/pty/terminal/subprocess exists in codebase per AI_RULES.md R2.1
"""

import subprocess
import pytest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

pytestmark = pytest.mark.invariant


def test_no_shell_true_in_panel_api():
    """Verify no shell execution flag in panel/api codebase."""
    pattern = "shell" + "=True"
    result = subprocess.run(
        ["grep", "-r", pattern, "panel/api", "--include=*.py", "--exclude-dir=tests"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT)
    )
    
    # grep returns 1 if no matches (which is what we want)
    assert result.returncode == 1, f"Found {pattern} in codebase:\n{result.stdout}"


def test_no_pty_in_panel_api():
    """Verify no pty fork usage in panel/api codebase."""
    pattern = "pty" + ".fork"
    result = subprocess.run(
        ["grep", "-r", pattern, "panel/api", "--include=*.py", "--exclude-dir=tests"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT)
    )
    
    assert result.returncode == 1, f"Found {pattern} in codebase:\n{result.stdout}"


def test_no_execvp_in_panel_api():
    """Verify no execvp in panel/api codebase."""
    pattern = "exec" + "vp"
    result = subprocess.run(
        ["grep", "-r", pattern, "panel/api", "--include=*.py", "--exclude-dir=tests"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT)
    )
    
    assert result.returncode == 1, f"Found {pattern} in codebase:\n{result.stdout}"


def test_no_terminal_router():
    """Verify terminal router does not exist."""
    import os
    terminal_path = REPO_ROOT / "panel/api/routers/terminal.py"
    assert not os.path.exists(terminal_path), "terminal.py should not exist"


def test_no_host_exec_direct():
    """Verify host_exec module is removed."""
    import os
    host_exec_path = REPO_ROOT / "panel/api/services/host_exec.py"
    assert not os.path.exists(host_exec_path), "host_exec.py should not exist"
