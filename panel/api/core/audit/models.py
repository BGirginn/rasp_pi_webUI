"""
Audit Event Models
Type definitions for audit logging.
"""

from typing import Optional, Union
from datetime import datetime
from pydantic import BaseModel


class AuditEvent(BaseModel):
    """
    Audit event record for action execution attempts.
    
    All fields are required except error (only populated on failure).
    """
    user_id: Union[int, str]
    username: str
    role: str
    action_id: str
    params_masked: dict
    status: str  # "success" or "fail"
    error: Optional[str] = None  # Error message if status="fail"
    duration_ms: int
    created_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
