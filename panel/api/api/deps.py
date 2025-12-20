"""
FastAPI Dependencies
Shared dependencies for API routers.
"""

from routers.auth import get_current_user

# Re-export as dependency
current_user = get_current_user
