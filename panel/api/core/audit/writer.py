"""
Audit Writer
Writes audit events to database.
"""

import json
from datetime import datetime
from core.audit.models import AuditEvent


async def write_audit(db, event: AuditEvent) -> None:
    """
    Write audit event to audit_log table.
    
    Args:
        db: Database connection
        event: AuditEvent instance to write
        
    Note:
        Uses existing audit_log table schema.
        Stores structured data in 'details' column as JSON.
    """
    # Prepare details JSON
    details = {
        "action_id": event.action_id,
        "params": event.params_masked,
        "status": event.status,
        "duration_ms": event.duration_ms,
        "role": event.role
    }
    
    if event.error:
        details["error"] = event.error
    
    details_json = json.dumps(details)
    
    # Write to audit_log table
    # Schema: user_id, username, action, resource_id, details, created_at
    # We use 'action' for action_id, resource_id can be NULL for non-resource actions
    await db.execute(
        """INSERT INTO audit_log (user_id, username, action, resource_id, details, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            event.user_id,
            event.username,
            event.action_id,  # Store in 'action' column
            None,  # resource_id not needed for AR actions
            details_json,
            event.created_at.isoformat()
        )
    )
    await db.commit()
