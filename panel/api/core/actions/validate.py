"""
Parameter Validation for Action Registry
Validates and sanitizes parameters according to action schema definitions.
"""

from typing import Any, Dict, Optional
from fastapi import HTTPException


def validate_params(registry: dict, action_id: str, params: Optional[dict]) -> dict:
    """
    Validate and sanitize parameters against action's params_schema.
    
    Args:
        registry: The Action Registry dict
        action_id: Action ID (e.g. "svc.restart")
        params: Parameters dict provided by user (can be None)
        
    Returns:
        Validated and sanitized params dict
        
    Raises:
        HTTPException(400): If validation fails
        HTTPException(404): If action_id not found
    """
    # Find action in registry
    actions = registry.get('actions', [])
    action = None
    for a in actions:
        if a.get('id') == action_id:
            action = a
            break
    
    if action is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "ACTION_NOT_FOUND", "message": f"Action '{action_id}' not found"}
        )
    
    schema = action.get('params_schema', {})
    
    # If schema is empty, params must be empty or None
    if not schema or schema == {}:
        if params and params != {}:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_PARAMS",
                    "message": f"Action '{action_id}' does not accept parameters"
                }
            )
        return {}
    
    # Normalize params
    if params is None:
        params = {}
    
    validated = {}
    
    # Check for unknown params
    for key in params.keys():
        if key not in schema:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "UNKNOWN_PARAM",
                    "message": f"Unknown parameter '{key}' for action '{action_id}'"
                }
            )
    
    # Validate each schema field
    for param_name, param_schema in schema.items():
        value = params.get(param_name)
        
        # Handle nullable
        if value is None:
            nullable = param_schema.get('nullable', False)
            if nullable:
                validated[param_name] = None
                continue
            
            # Check for default
            if 'default' in param_schema:
                validated[param_name] = param_schema['default']
                continue
            
            # Required param missing
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "MISSING_PARAM",
                    "message": f"Required parameter '{param_name}' missing for action '{action_id}'"
                }
            )
        
        # Validate type
        param_type = param_schema.get('type')
        if not param_type:
            raise ValueError(f"Schema for '{param_name}' missing 'type' field")
        
        if param_type == 'string':
            if not isinstance(value, str):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "INVALID_TYPE",
                        "message": f"Parameter '{param_name}' must be a string"
                    }
                )
            
            # Validate enum
            if 'enum' in param_schema:
                if value not in param_schema['enum']:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": "INVALID_ENUM",
                            "message": f"Parameter '{param_name}' must be one of {param_schema['enum']}"
                        }
                    )
            
            # Validate allowlist_ref
            if 'allowlist_ref' in param_schema:
                allowlist_name = param_schema['allowlist_ref']
                targets = registry.get('targets', {})
                allowlist = targets.get(allowlist_name, [])
                
                if value not in allowlist:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": "ALLOWLIST_VIOLATION",
                            "message": f"Parameter '{param_name}' value '{value}' not in allowlist '{allowlist_name}'"
                        }
                    )
            
            # Validate minLength/maxLength
            if 'minLength' in param_schema and len(value) < param_schema['minLength']:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "STRING_TOO_SHORT",
                        "message": f"Parameter '{param_name}' must be at least {param_schema['minLength']} characters"
                    }
                )
            
            if 'maxLength' in param_schema and len(value) > param_schema['maxLength']:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "STRING_TOO_LONG",
                        "message": f"Parameter '{param_name}' must be at most {param_schema['maxLength']} characters"
                    }
                )
            
            validated[param_name] = value
        
        elif param_type == 'integer':
            if not isinstance(value, int) or isinstance(value, bool):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "INVALID_TYPE",
                        "message": f"Parameter '{param_name}' must be an integer"
                    }
                )
            
            # Validate minimum/maximum
            if 'minimum' in param_schema and value < param_schema['minimum']:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "VALUE_TOO_SMALL",
                        "message": f"Parameter '{param_name}' must be at least {param_schema['minimum']}"
                    }
                )
            
            if 'maximum' in param_schema and value > param_schema['maximum']:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "VALUE_TOO_LARGE",
                        "message": f"Parameter '{param_name}' must be at most {param_schema['maximum']}"
                    }
                )
            
            validated[param_name] = value
        
        elif param_type == 'number':
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "INVALID_TYPE",
                        "message": f"Parameter '{param_name}' must be a number"
                    }
                )
            
            # Validate minimum/maximum
            if 'minimum' in param_schema and value < param_schema['minimum']:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "VALUE_TOO_SMALL",
                        "message": f"Parameter '{param_name}' must be at least {param_schema['minimum']}"
                    }
                )
            
            if 'maximum' in param_schema and value > param_schema['maximum']:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "VALUE_TOO_LARGE",
                        "message": f"Parameter '{param_name}' must be at most {param_schema['maximum']}"
                    }
                )
            
            validated[param_name] = value
        
        elif param_type == 'boolean':
            if not isinstance(value, bool):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "INVALID_TYPE",
                        "message": f"Parameter '{param_name}' must be a boolean"
                    }
                )
            
            validated[param_name] = value
        
        elif param_type == 'array':
            if not isinstance(value, list):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "INVALID_TYPE",
                        "message": f"Parameter '{param_name}' must be an array"
                    }
                )
            
            # Validate items if specified
            if 'items' in param_schema:
                items_schema = param_schema['items']
                items_type = items_schema.get('type')
                
                for idx, item in enumerate(value):
                    if items_type == 'string' and not isinstance(item, str):
                        raise HTTPException(
                            status_code=400,
                            detail={
                                "error": "INVALID_ARRAY_ITEM",
                                "message": f"Parameter '{param_name}[{idx}]' must be a string"
                            }
                        )
                    elif items_type == 'integer' and (not isinstance(item, int) or isinstance(item, bool)):
                        raise HTTPException(
                            status_code=400,
                            detail={
                                "error": "INVALID_ARRAY_ITEM",
                                "message": f"Parameter '{param_name}[{idx}]' must be an integer"
                            }
                        )
                    elif items_type == 'number' and (not isinstance(item, (int, float)) or isinstance(item, bool)):
                        raise HTTPException(
                            status_code=400,
                            detail={
                                "error": "INVALID_ARRAY_ITEM",
                                "message": f"Parameter '{param_name}[{idx}]' must be a number"
                            }
                        )
                    elif items_type == 'boolean' and not isinstance(item, bool):
                        raise HTTPException(
                            status_code=400,
                            detail={
                                "error": "INVALID_ARRAY_ITEM",
                                "message": f"Parameter '{param_name}[{idx}]' must be a boolean"
                            }
                        )
            
            validated[param_name] = value
        
        else:
            raise ValueError(f"Unsupported param type: {param_type}")
    
    return validated
