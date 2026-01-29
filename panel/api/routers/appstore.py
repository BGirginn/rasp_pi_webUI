"""
App Store Router

API endpoints for Docker application store.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel

from services.appstore_service import appstore_service

router = APIRouter(prefix="/appstore", tags=["appstore"])


class InstallRequest(BaseModel):
    """Request model for app installation."""
    app_id: str
    config: Optional[dict] = None


class ActionRequest(BaseModel):
    """Request model for app actions."""
    app_id: str


# ============================================================================
# Catalog Endpoints
# ============================================================================

@router.get("/catalog")
async def get_catalog():
    """Get the full application catalog."""
    return appstore_service.get_catalog()


@router.get("/categories")
async def get_categories():
    """Get all app categories."""
    return appstore_service.get_categories()


@router.get("/apps")
async def get_apps(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search apps by name, description, or tags"),
):
    """Get available apps with optional filtering."""
    return appstore_service.get_apps(category=category, search=search)


@router.get("/apps/{app_id}")
async def get_app(app_id: str):
    """Get details of a specific app."""
    app = appstore_service.get_app(app_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"App not found: {app_id}")
    return app


# ============================================================================
# Installed Apps Endpoints
# ============================================================================

@router.get("/installed")
async def get_installed_apps():
    """Get all installed apps."""
    return appstore_service.get_installed_apps()


@router.post("/install")
async def install_app(request: InstallRequest):
    """Install an application."""
    result = await appstore_service.install_app(
        app_id=request.app_id,
        custom_config=request.config
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.post("/uninstall")
async def uninstall_app(
    request: ActionRequest,
    remove_data: bool = Query(False, description="Remove app data volumes")
):
    """Uninstall an application."""
    result = await appstore_service.uninstall_app(
        app_id=request.app_id,
        remove_data=remove_data
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


# ============================================================================
# App Control Endpoints
# ============================================================================

@router.post("/start")
async def start_app(request: ActionRequest):
    """Start an installed application."""
    result = await appstore_service.start_app(request.app_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.post("/stop")
async def stop_app(request: ActionRequest):
    """Stop an installed application."""
    result = await appstore_service.stop_app(request.app_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.post("/restart")
async def restart_app(request: ActionRequest):
    """Restart an installed application."""
    result = await appstore_service.restart_app(request.app_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


# ============================================================================
# Logs & Stats Endpoints
# ============================================================================

@router.get("/logs/{app_id}")
async def get_app_logs(
    app_id: str,
    tail: int = Query(100, ge=1, le=1000, description="Number of log lines")
):
    """Get logs for an installed application."""
    result = await appstore_service.get_app_logs(app_id, tail=tail)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.get("/stats/{app_id}")
async def get_app_stats(app_id: str):
    """Get resource stats for an installed application."""
    result = await appstore_service.get_app_stats(app_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result
