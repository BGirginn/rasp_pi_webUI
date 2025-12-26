"""
Invariant Test Helpers
Reusable utilities for validating Action Registry invariants.
"""

import ast
import inspect
from pathlib import Path
from typing import Dict, List, Set, Callable, Any

import yaml


def get_registry_handler_refs(registry: dict) -> Set[str]:
    """
    Extract all handler references from the registry.
    
    Returns:
        Set of handler strings like "handler.obs.get_system_status"
    """
    handlers = set()
    for action in registry.get("actions", []):
        handler = action.get("handler")
        if handler:
            handlers.add(handler)
    return handlers


def get_all_handler_functions() -> Dict[str, Callable]:
    """
    Discover all handler functions in handlers.py.
    
    Returns:
        Dict mapping function names to function objects
    """
    from core.actions import handlers
    
    handler_funcs = {}
    for name in dir(handlers):
        if name.startswith("handler_"):
            obj = getattr(handlers, name)
            if callable(obj):
                handler_funcs[name] = obj
    
    return handler_funcs


def get_handler_map() -> Dict[str, Callable]:
    """
    Get the HANDLERS map from handlers.py.
    
    Returns:
        Dict mapping handler strings to functions
    """
    from core.actions.handlers import HANDLERS
    return HANDLERS


def extract_function_signature(func: Callable) -> Dict[str, Any]:
    """
    Extract parameter information from a function signature.
    
    Returns:
        Dict with 'required' and 'optional' param lists
    """
    sig = inspect.signature(func)
    required = []
    optional = []
    
    for name, param in sig.parameters.items():
        if param.default == inspect.Parameter.empty:
            required.append(name)
        else:
            optional.append(name)
    
    return {
        "required": required,
        "optional": optional,
        "all": list(sig.parameters.keys())
    }


def extract_schema_params(params_schema: dict) -> Dict[str, Any]:
    """
    Extract parameter information from a schema definition.
    
    Returns:
        Dict with 'required' and 'optional' param lists
    """
    if not params_schema:
        return {"required": [], "optional": [], "all": []}
    
    required = []
    optional = []
    
    for name, spec in params_schema.items():
        if "default" in spec or spec.get("nullable"):
            optional.append(name)
        else:
            required.append(name)
    
    return {
        "required": required,
        "optional": optional,
        "all": list(params_schema.keys())
    }


def validate_signature_match(handler_func: Callable, params_schema: dict) -> Dict[str, Any]:
    """
    Validate that handler signature matches schema definition.
    
    Returns:
        Dict with 'valid' bool and 'errors' list
    """
    sig_params = extract_function_signature(handler_func)
    schema_params = extract_schema_params(params_schema)
    
    errors = []
    
    # Handler required params must be in schema
    for param in sig_params["required"]:
        if param not in schema_params["all"]:
            errors.append(f"Handler requires '{param}' but schema doesn't define it")
    
    # Schema required params must be in handler signature
    for param in schema_params["required"]:
        if param not in sig_params["all"]:
            errors.append(f"Schema requires '{param}' but handler doesn't accept it")
    
    # Schema params should be accepted by handler
    for param in schema_params["all"]:
        if param not in sig_params["all"]:
            # Check if handler accepts **kwargs
            handler_source = inspect.getsource(handler_func)
            if "**kwargs" not in handler_source and "**params" not in handler_source:
                errors.append(f"Schema defines '{param}' but handler doesn't accept it (and no **kwargs)")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "handler_params": sig_params,
        "schema_params": schema_params
    }


def find_orphaned_handlers(registry: dict, handler_funcs: Dict[str, Callable]) -> List[str]:
    """
    Find handler functions that are not referenced in the registry.
    
    Returns:
        List of orphaned handler function names
    """
    registry_refs = get_registry_handler_refs(registry)
    
    # Convert registry refs to function names
    # "handler.obs.get_system_status" -> "handler_obs_get_system_status"
    expected_func_names = set()
    for ref in registry_refs:
        func_name = ref.replace(".", "_")
        expected_func_names.add(func_name)
    
    # Find handlers that exist but aren't referenced
    orphaned = []
    for func_name in handler_funcs.keys():
        if func_name not in expected_func_names:
            orphaned.append(func_name)
    
    return orphaned


def find_missing_handlers(registry: dict, handler_funcs: Dict[str, Callable]) -> List[str]:
    """
    Find registry handler references that don't have corresponding functions.
    
    Returns:
        List of missing handler references
    """
    registry_refs = get_registry_handler_refs(registry)
    
    missing = []
    for ref in registry_refs:
        func_name = ref.replace(".", "_")
        if func_name not in handler_funcs:
            missing.append(ref)
    
    return missing


def validate_action_id_format(action_id: str) -> bool:
    """
    Validate action ID follows category.action_name or category.subcategory.action_name format.
    
    Returns:
        True if format is valid
    """
    parts = action_id.split(".")
    if len(parts) < 2 or len(parts) > 3:
        return False
    
    # All parts should be lowercase alphanumeric with underscores
    for part in parts:
        if not part or not part.replace("_", "").isalnum():
            return False
    
    return True
