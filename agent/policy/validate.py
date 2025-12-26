"""
Validate agent request params against the policy registry.
"""

from typing import Any, Dict, Optional


class PolicyError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def get_action(registry: dict, action_id: str) -> dict:
    for action in registry.get("actions", []):
        if action.get("id") == action_id:
            return action
    raise PolicyError("unknown_action", f"Unknown action '{action_id}'")


def enforce_action(
    registry: dict,
    action_id: str,
    params: Optional[dict],
    confirm_token: Optional[str] = None,
) -> Dict[str, Any]:
    action = get_action(registry, action_id)

    if action.get("disabled"):
        raise PolicyError("action_disabled", f"Action '{action_id}' is disabled")

    if action.get("confirm_required") and not confirm_token:
        raise PolicyError("unauthorized", f"Action '{action_id}' requires confirmation")

    validated = validate_params(registry, action_id, params)
    return {"action": action, "params": validated}


def validate_params(registry: dict, action_id: str, params: Optional[dict]) -> dict:
    action = get_action(registry, action_id)
    schema = action.get("params_schema", {})

    if not schema:
        if params:
            raise PolicyError("invalid_params", f"Action '{action_id}' does not accept parameters")
        return {}

    if params is None:
        params = {}

    if not isinstance(params, dict):
        raise PolicyError("invalid_params", "Params must be an object")

    for key in params.keys():
        if key not in schema:
            raise PolicyError("invalid_params", f"Unknown parameter '{key}' for action '{action_id}'")

    validated = {}
    for param_name, param_schema in schema.items():
        if param_name not in params:
            if param_schema.get("optional"):
                continue
            if "default" in param_schema:
                validated[param_name] = param_schema["default"]
                continue
            if param_schema.get("nullable"):
                validated[param_name] = None
                continue
            raise PolicyError("invalid_params", f"Missing required parameter '{param_name}'")

        value = params.get(param_name)
        if value is None:
            if param_schema.get("nullable"):
                validated[param_name] = None
                continue
            raise PolicyError("invalid_params", f"Parameter '{param_name}' cannot be null")

        validated[param_name] = _validate_value(
            registry=registry,
            param_name=param_name,
            value=value,
            schema=param_schema,
        )

    return validated


def _validate_value(registry: dict, param_name: str, value: Any, schema: dict) -> Any:
    param_type = schema.get("type")
    if not param_type:
        raise PolicyError("invalid_params", f"Schema for '{param_name}' missing type")

    if param_type == "string":
        if not isinstance(value, str):
            raise PolicyError("invalid_params", f"Parameter '{param_name}' must be a string")
        if "enum" in schema and value not in schema["enum"]:
            raise PolicyError("invalid_params", f"Parameter '{param_name}' must be one of {schema['enum']}")
        if "allowlist_ref" in schema:
            allowlist = registry.get("targets", {}).get(schema["allowlist_ref"], [])
            if value not in allowlist:
                raise PolicyError("invalid_params", f"Parameter '{param_name}' not in allowlist")
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise PolicyError("invalid_params", f"Parameter '{param_name}' too short")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise PolicyError("invalid_params", f"Parameter '{param_name}' too long")
        return value

    if param_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise PolicyError("invalid_params", f"Parameter '{param_name}' must be an integer")
        if "minimum" in schema and value < schema["minimum"]:
            raise PolicyError("invalid_params", f"Parameter '{param_name}' below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            raise PolicyError("invalid_params", f"Parameter '{param_name}' above maximum")
        return value

    if param_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise PolicyError("invalid_params", f"Parameter '{param_name}' must be a number")
        if "minimum" in schema and value < schema["minimum"]:
            raise PolicyError("invalid_params", f"Parameter '{param_name}' below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            raise PolicyError("invalid_params", f"Parameter '{param_name}' above maximum")
        return value

    if param_type == "boolean":
        if not isinstance(value, bool):
            raise PolicyError("invalid_params", f"Parameter '{param_name}' must be a boolean")
        return value

    if param_type == "array":
        if not isinstance(value, list):
            raise PolicyError("invalid_params", f"Parameter '{param_name}' must be an array")
        items_schema = schema.get("items")
        if items_schema:
            for idx, item in enumerate(value):
                _validate_value(registry, f"{param_name}[{idx}]", item, items_schema)
        return value

    if param_type == "object":
        if not isinstance(value, dict):
            raise PolicyError("invalid_params", f"Parameter '{param_name}' must be an object")
        properties = schema.get("properties")
        allow_additional = schema.get("additional_properties", True if not properties else False)
        if properties:
            for key in value.keys():
                if key not in properties and not allow_additional:
                    raise PolicyError("invalid_params", f"Unknown field '{param_name}.{key}'")
            for prop_name, prop_schema in properties.items():
                if prop_name not in value:
                    if prop_schema.get("optional"):
                        continue
                    if "default" in prop_schema:
                        value[prop_name] = prop_schema["default"]
                        continue
                    if prop_schema.get("nullable"):
                        value[prop_name] = None
                        continue
                    raise PolicyError("invalid_params", f"Missing field '{param_name}.{prop_name}'")
                prop_value = value.get(prop_name)
                if prop_value is None:
                    if prop_schema.get("nullable"):
                        continue
                    raise PolicyError("invalid_params", f"Field '{param_name}.{prop_name}' cannot be null")
                _validate_value(registry, f"{param_name}.{prop_name}", prop_value, prop_schema)
        return value

    raise PolicyError("invalid_params", f"Unsupported type '{param_type}' for '{param_name}'")
