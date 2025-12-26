"""
Load the agent policy registry from disk.
"""

from pathlib import Path
from typing import Optional

import structlog
import yaml

logger = structlog.get_logger(__name__)

_REGISTRY_CACHE = None


def _default_registry_path() -> Path:
    return Path(__file__).resolve().parent / "registry.yaml"


def load_registry(path: Optional[str] = None) -> dict:
    registry_path = Path(path) if path else _default_registry_path()
    if not registry_path.exists():
        raise FileNotFoundError(f"Agent registry not found: {registry_path}")

    registry = yaml.safe_load(registry_path.read_text())
    if not isinstance(registry, dict):
        raise ValueError("Agent registry must be a mapping")

    if "actions" not in registry:
        raise ValueError("Agent registry missing 'actions'")

    logger.info("Agent registry loaded", path=str(registry_path))
    return registry


def get_registry(path: Optional[str] = None) -> dict:
    global _REGISTRY_CACHE
    if _REGISTRY_CACHE is None or path:
        _REGISTRY_CACHE = load_registry(path)
    return _REGISTRY_CACHE
