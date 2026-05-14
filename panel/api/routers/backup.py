"""
Pi Control Panel - Backup Router

Provides API endpoints for local backup management.
"""

from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import FileResponse
from db import get_control_db
from .auth import get_current_user, require_role
from services.gdrive_backup import backup_service

# Admin check dependency
require_admin = require_role("admin")

router = APIRouter()


async def _audit(user: dict, action: str, details: str = "") -> None:
    db = await get_control_db()
    await db.execute(
        "INSERT INTO audit_log (user_id, action, resource_id, details) VALUES (?, ?, ?, ?)",
        (user["id"], action, "backup", details),
    )
    await db.commit()

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


@router.post("/encrypted")
async def trigger_encrypted_backup(user: dict = Depends(require_admin)):
    """Create an encrypted DB/export backup and upload it to Drive when authenticated."""
    result = await backup_service.run_encrypted_backup(trigger="manual")
    await _audit(user, "backup.encrypted.create", f"status={result.get('status')}, uploaded={result.get('uploaded')}")
    return result


@router.post("/gdrive/client")
async def upload_gdrive_client(
    file: UploadFile = File(...),
    user: dict = Depends(require_admin),
):
    """Upload Google OAuth client JSON for device authorization."""
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="OAuth client file must be JSON")
    try:
        result = await backup_service.upload_oauth_client(await file.read())
        await _audit(user, "backup.gdrive.client_upload", f"filename={file.filename}")
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/gdrive/auth/start")
async def start_gdrive_auth(user: dict = Depends(require_admin)):
    """Start Google OAuth device-code flow."""
    try:
        result = await backup_service.start_device_authorization()
        await _audit(user, "backup.gdrive.auth_start")
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/gdrive/auth/status")
async def get_gdrive_auth_status(user: dict = Depends(require_admin)):
    """Poll Google OAuth device-code flow status."""
    try:
        return await backup_service.poll_device_authorization()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/gdrive/disconnect")
async def disconnect_gdrive(user: dict = Depends(require_admin)):
    """Disconnect Google Drive by deleting the stored OAuth token."""
    result = await backup_service.disconnect_gdrive()
    await _audit(user, "backup.gdrive.disconnect")
    return result


@router.delete("/gdrive/files/{file_id}")
async def delete_gdrive_backup(file_id: str, user: dict = Depends(require_admin)):
    """Delete a Pi Control backup file from Google Drive."""
    try:
        result = backup_service.delete_drive_backup(file_id)
        await _audit(user, "backup.gdrive.remote_delete", f"file_id={file_id}")
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

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
