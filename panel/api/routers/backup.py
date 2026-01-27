"""
Pi Control Panel - Backup Router

Provides API endpoints for backup management and Google Drive integration.
"""

from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from typing import Optional
from pathlib import Path
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

# ==================== Google Drive Auth ====================

@router.get("/gdrive/auth-url")
async def get_gdrive_auth_url(user: dict = Depends(require_admin)):
    """Get Google Drive authorization URL for setup."""
    if not backup_service.credentials_file.exists():
        raise HTTPException(
            status_code=400, 
            detail="Google Drive credentials not configured. Upload credentials.json first."
        )
    
    # For headless setup, provide instructions
    return {
        "message": "Google Drive authentication is done via command line on the Raspberry Pi",
        "instructions": [
            "1. SSH into your Raspberry Pi",
            "2. Run: cd /opt/pi-control && python scripts/gdrive_auth.py",
            "3. Follow the browser link to authorize",
            "4. Paste the authorization code",
            "5. Restart pi-control service"
        ]
    }

@router.post("/gdrive/set-folder")
async def set_gdrive_folder(
    folder_id: str,
    user: dict = Depends(require_admin)
):
    """Set the Google Drive folder ID for backups."""
    backup_service.folder_id = folder_id
    return {"message": f"Backup folder set to {folder_id}"}
