"""
Error Message Utilities
Maps error codes to user - friendly, actionable messages.
"""

ERROR_MESSAGES = {
    # Permission errors
    "PERMISSION_DENIED": {
        "title": "Permission Denied",
        "message": "You don't have permission to perform this action",
        "action": "Contact an administrator to request role upgrade",
        "severity": "error"
    },
    
    # Confirmation errors
    "CONFIRMATION_REQUIRED": {
        "title": "Confirmation Required",
        "message": "This action requires explicit confirmation",
        "action": "Check the confirmation box and try again",
        "severity": "warning"
    },
    
    # Cooldown errors  
    "COOLDOWN_ACTIVE": {
        "title": "Please Wait",
        "message": "You must wait before performing this action again",
        "action": "Wait for the cooldown period to expire",
        "severity": "warning"
    },
    
    # Validation errors
    "INVALID_PARAMS": {
        "title": "Invalid Parameters",
        "message": "One or more parameters are invalid",
        "action": "Check the parameter requirements and try again",
        "severity": "error"
    },

    "INVALID_SERVICE_NAME": {
        "title": "Invalid Service",
        "message": "The specified service is not in the allowlist",
        "action": "Choose from the allowed services list",
        "severity": "error"
    },
    
    # Rollback errors
    "ROLLBACK_TIMEOUT": {
        "title": "Network Change Rolled Back",
        "message": "The network change was not confirmed and has been reverted",
        "action": "Make the change again and confirm it promptly",
        "severity": "warning"
    },
    
    # Handler errors
    "HANDLER_NOT_FOUND": {
        "title": "Action Unavailable",
        "message": "This action is not currently available",
        "action": "Contact support if this persists",
        "severity": "error"
    },
    
    # Internal errors
    "INTERNAL_ERROR": {
        "title": "System Error",
        "message": "An unexpected error occurred",
        "action": "Try again or contact support if this persists",
        "severity": "error"
    },

    "EXECUTION_FAILED": {
        "title": "Action Failed",
        "message": "The action could not be completed",
        "action": "Check the action logs for more details",
        "severity": "error"
    },
}


def get_error_message(error_code: str, custom_message: str = None, details: dict = None):
"""
    Get a user - friendly error message for an error code.

    Args:
    error_code: Error code(UPPERCASE_WITH_UNDERSCORES)
custom_message: Optional custom message to override default
details: Optional additional details(e.g., { "wait_seconds": 45 })

Returns:
        Dict with title, message, action, severity
    """
template = ERROR_MESSAGES.get(error_code, ERROR_MESSAGES["INTERNAL_ERROR"])

result = template.copy()

if custom_message:
    result["message"] = custom_message

if details:
        # Interpolate details into message if needed
        if "wait_seconds" in details:
        result["message"] = f"You must wait {details['wait_seconds']} seconds before retrying"

if "missing_roles" in details:
    result["message"] = f"This action requires one of these roles: {', '.join(details['missing_roles'])}"

if "allowed_values" in details:
    result["action"] = f"Choose from: {', '.join(details['allowed_values'])}"

return result


def format_http_exception_detail(exc_detail):
"""
    Format HTTPException detail into user - friendly message.

    Args:
exc_detail: Exception detail(dict or string)

Returns:
        Formatted error dict
"""
if isinstance(exc_detail, dict):
    error_code = exc_detail.get("error", "INTERNAL_ERROR")
message = exc_detail.get("message")
return get_error_message(error_code, custom_message = message)
    
    # Fallback for string details
    return get_error_message("INTERNAL_ERROR", custom_message = str(exc_detail))
