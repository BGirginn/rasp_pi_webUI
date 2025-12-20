"""
Action Registry Loader
Loads and validates registry.yaml, provides singleton access.
"""

import yaml
from pathlib import Path
from typing import Optional

# Module-level cache
_REGISTRY_CACHE: Optional[dict] = None


def load_registry(path: str) -> dict:
    """
    Load Action Registry from YAML file with validation.
    
    Args:
        path: Absolute path to registry.yaml
        
    Returns:
        Parsed and validated registry dict
        
    Raises:
        ValueError: If registry is invalid
        FileNotFoundError: If registry file doesn't exist
    """
    registry_path = Path(path)
    
    if not registry_path.exists():
        raise FileNotFoundError(f"Registry file not found: {path}")
    
    with open(registry_path, 'r') as f:
        registry = yaml.safe_load(f)
    
    # Validate version
    if 'version' not in registry:
        raise ValueError("Registry missing 'version' field")
    
    if registry['version'] != 1:
        raise ValueError(f"Unsupported registry version: {registry['version']}. Expected: 1")
    
    # Validate actions
    if 'actions' not in registry or not isinstance(registry['actions'], list):
        raise ValueError("Registry missing 'actions' list")
    
    action_ids = set()
    for idx, action in enumerate(registry['actions']):
        # Validate required fields
        if 'id' not in action:
            raise ValueError(f"Action at index {idx} missing 'id'")
        
        action_id = action['id']
        
        # Check uniqueness
        if action_id in action_ids:
            raise ValueError(f"Duplicate action ID: {action_id}")
        action_ids.add(action_id)
        
        # Validate roles_allowed
        if 'roles_allowed' not in action:
            raise ValueError(f"Action '{action_id}' missing 'roles_allowed'")
        
        if not isinstance(action['roles_allowed'], list) or len(action['roles_allowed']) == 0:
            raise ValueError(f"Action '{action_id}' has empty or invalid 'roles_allowed'")
        
        # Validate handler
        if 'handler' not in action or not action['handler']:
            raise ValueError(f"Action '{action_id}' missing 'handler'")
        
        if not isinstance(action['handler'], str) or not action['handler'].strip():
            raise ValueError(f"Action '{action_id}' has empty handler")
    
    # Validate roles exist
    if 'roles' not in registry or not isinstance(registry['roles'], dict):
        raise ValueError("Registry missing 'roles' definition")
    
    # Validate defaults exist
    if 'defaults' not in registry:
        raise ValueError("Registry missing 'defaults'")
    
    # Validate targets exist
    if 'targets' not in registry:
        raise ValueError("Registry missing 'targets' (allowlists)")
    
    return registry


def get_registry() -> dict:
    """
    Get the Action Registry (singleton, lazy-loaded).
    
    Returns:
        Registry dict
        
    Raises:
        ValueError: If registry is invalid
        FileNotFoundError: If registry file doesn't exist
    """
    global _REGISTRY_CACHE
    
    if _REGISTRY_CACHE is None:
        # Determine registry path relative to this file
        current_dir = Path(__file__).parent
        registry_path = current_dir / "registry.yaml"
        
        _REGISTRY_CACHE = load_registry(str(registry_path))
    
    return _REGISTRY_CACHE


def reload_registry() -> dict:
    """
    Force reload of registry (for testing or hot-reload scenarios).
    
    Returns:
        Freshly loaded registry dict
    """
    global _REGISTRY_CACHE
    _REGISTRY_CACHE = None
    return get_registry()
