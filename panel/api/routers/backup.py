"""
Pi Control Panel - Backup Router

Provides API endpoints for local backup management.
"""

from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from .auth import get_current_user, require_role
from services.gdrive_backup import backup_service

# Admin check dependency
require_admin = require_role("admin")

router = APIRouter()

# ==================== Status ====================

@router.get("/status")
async def get_backup_status(user: dict = Depends(get_current_user)):
    """Get current backup service status."""
    return backup_service.get_status()

# ==================== Manual Backup ====================

@router.post("/trigger")
async def trigger_backup(
    background_tasks: BackgroundTasks,
    format: str = Query("json", enum=["json", "csv"]),
    user: dict = Depends(require_admin)
):
    """Manually trigger a backup."""
    
    async def run_backup():
        await backup_service.run_backup(format=format)
    
    background_tasks.add_task(run_backup)
    
    return {
        "message": "Backup started",
        "format": format,
        "status": "running"
    }

# ==================== Backup History ====================

@router.get("/history")
async def get_backup_history(user: dict = Depends(get_current_user)):
    """Get backup history."""
    return {
        "history": backup_service.backup_history,
        "last_backup": backup_service.last_backup
    }

# ==================== Download Backup ====================

@router.get("/download/{filename}")
async def download_backup(
    filename: str,
    user: dict = Depends(require_admin)
):
    """Download a local backup file."""
    filepath = backup_service.backup_dir / filename
    
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Backup file not found")
    
    # Security check - ensure file is in backup directory
    if not str(filepath.resolve()).startswith(str(backup_service.backup_dir.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/octet-stream"
    )

# ==================== List Local Backups ====================

@router.get("/files")
async def list_backup_files(user: dict = Depends(get_current_user)):
    """List all local backup files."""
    return {
        "files": backup_service._get_local_backups(),
        "directory": str(backup_service.backup_dir)
    }

# ==================== Delete Backup ====================

@router.delete("/files/{filename}")
async def delete_backup_file(
    filename: str,
    user: dict = Depends(require_admin)
):
    """Delete a local backup file."""
    filepath = backup_service.backup_dir / filename
    
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Backup file not found")
    
    # Security check
    if not str(filepath.resolve()).startswith(str(backup_service.backup_dir.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")
    
    filepath.unlink()
    return {"message": f"Deleted {filename}"}

# NOTE: Google Drive backup endpoints are intentionally removed for now.
# TODO: Re-introduce cloud backup endpoints once the new GDrive flow is finalized.
