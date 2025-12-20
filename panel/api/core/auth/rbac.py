"""
RBAC (Role-Based Access Control) for Action Registry
Enforces role permissions before action execution.
"""

from fastapi import HTTPException


def is_role_allowed(registry: dict, role: str, action_id: str) -> bool:
    """
    Check if a role is allowed to execute an action.
    
    Args:
        registry: The Action Registry dict
        role: User's role (viewer, operator, admin, owner)
        action_id: Action ID to check (e.g. "svc.restart")
        
    Returns:
        True if role is allowed, False otherwise
        
    Note:
        Deny-by-default: Unknown action_id or unknown role returns False
    """
    # Validate role exists in registry
    if 'roles' not in registry or role not in registry['roles']:
        return False
    
    # Find action in registry
    actions = registry.get('actions', [])
    action = None
    for a in actions:
        if a.get('id') == action_id:
            action = a
            break
    
    if action is None:
        # Unknown action_id - deny
        return False
    
    # Check if role is in roles_allowed list
    roles_allowed = action.get('roles_allowed', [])
    return role in roles_allowed


def assert_role_allowed(registry: dict, role: str, action_id: str) -> None:
    """
    Assert that a role is allowed to execute an action.
    Raises HTTP 403 if not allowed.
    
    Args:
        registry: The Action Registry dict
        role: User's role (viewer, operator, admin, owner)
        action_id: Action ID to check (e.g. "svc.restart")
        
    Raises:
        HTTPException(403): If role is not allowed
    """
    if not is_role_allowed(registry, role, action_id):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "PERMISSION_DENIED",
                "message": f"Role '{role}' is not allowed to execute action '{action_id}'"
            }
        )
