"""
Parameter Masking for Audit Logs
Masks sensitive parameters before writing to audit log.
"""

def mask_params(action_id: str, params: dict) -> dict:
    """
    Mask sensitive parameters for audit logging.
    
    Args:
        action_id: Action ID (e.g. "auth.create_user")
        params: Original params dict
        
    Returns:
        Params dict with sensitive values masked
    """
    if not params:
        return {}
    
    # Create a copy to avoid mutating original
    masked = params.copy()
    
    # Mask auth action sensitive params
    if action_id.startswith("auth."):
        # Mask temporary_password
        if "temporary_password" in masked:
            masked["temporary_password"] = "***"
        
        # Mask password if present
        if "password" in masked:
            masked["password"] = "***"
        
        # Mask old_password / new_password if present
        if "old_password" in masked:
            masked["old_password"] = "***"
        
        if "new_password" in masked:
            masked["new_password"] = "***"
    
    # Mask any key containing "secret", "token", "key"
    for key in list(masked.keys()):
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in ["secret", "token", "key", "password"]):
            masked[key] = "***"
    
    return masked
