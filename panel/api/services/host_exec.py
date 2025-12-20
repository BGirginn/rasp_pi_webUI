"""
DEPRECATED: host_exec module removed per AI_RULES.md R2.1.
This stub exists temporarily for import compatibility.
Will be fully replaced by Action Registry adapters in TASK 08/12.
"""


def run_host_command_simple(command: str, timeout: int = 10) -> str:
    """STUB: Will be replaced by agent RPC calls."""
    # TODO: TASK 08 - Replace with agent adapter
    return ""


def run_host_command(command: str, timeout: int = 10) -> tuple:
    """STUB: Will be replaced by agent RPC calls."""
    # TODO: TASK 08 - Replace with agent adapter
    return ("", "", 1)


def is_running_in_docker() -> bool:
    """STUB: Will be replaced by config/detection logic."""
    # TODO: TASK 08 - Move to config
    import os
    return os.path.exists("/.dockerenv")
