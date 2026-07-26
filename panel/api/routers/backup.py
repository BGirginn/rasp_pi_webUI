"""
Pi Control Panel - Backup Router

Provides API endpoints for local backup management.
"""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from db import get_control_db
from services.agent_client import agent_client
from .auth import get_current_user, require_role
from services.gdrive_backup import backup_service

# Admin check dependency
require_admin = require_role("admin")

router = APIRouter()


class RestoreRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    components: list[str] = Field(default_factory=list)
    confirmation: str = ""


class RecoveryKeyImport(BaseModel):
    key: str = Field(min_length=40, max_length=128)
    replace: bool = False


def _resolve_local_backup(filename: str):
    """Resolve one backup filename without allowing traversal or sibling prefixes."""
    if not filename or filename != backup_service.backup_dir.joinpath(filename).name:
        raise HTTPException(status_code=403, detail="Access denied")
    base_dir = backup_service.backup_dir.resolve()
    filepath = (base_dir / filename).resolve()
    if not filepath.is_relative_to(base_dir):
        raise HTTPException(status_code=403, detail="Access denied")
    return filepath


async def _inspect_and_record(filename: str, user: dict) -> dict:
    filepath = _resolve_local_backup(filename)
    if not filepath.is_file():
        raise HTTPException(status_code=404, detail="Backup file not found")
    try:
        result = await agent_client.inspect_backup(str(filepath))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Backup validation failed: {exc}")
    restore_id = result["checksum"][:16]
    db = await get_control_db()
    await db.execute(
        """INSERT INTO restore_points
               (id, filename, source, manifest_json, checksum, size_bytes, status, created_by)
           VALUES (?, ?, 'local', ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET manifest_json=excluded.manifest_json,
               size_bytes=excluded.size_bytes, status=excluded.status""",
        (
            restore_id,
            filename,
            json.dumps(result.get("manifest", {})),
            result["checksum"],
            int(result.get("size_bytes", 0)),
            "valid" if result.get("valid") else "invalid",
            user["id"],
        ),
    )
    await db.commit()
    return {**result, "restore_point_id": restore_id}

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
    return await backup_service.run_encrypted_backup(trigger="manual")


@router.post("/validate")
async def validate_backup(request: RestoreRequest, user: dict = Depends(require_admin)):
    """Decrypt and validate a local backup without changing the host."""
    return await _inspect_and_record(request.filename, user)


@router.post("/restore-preview")
async def preview_restore(request: RestoreRequest, user: dict = Depends(require_admin)):
    """Return the exact restore component set and compatibility result."""
    result = await _inspect_and_record(request.filename, user)
    available = set(result.get("components", []))
    selected = set(request.components or available)
    unknown = selected - available
    if unknown:
        raise HTTPException(status_code=400, detail=f"Backup does not contain: {', '.join(sorted(unknown))}")
    return {
        **result,
        "selected_components": sorted(selected),
        "requires_maintenance": bool(selected),
        "confirmation_text": request.filename,
    }


@router.post("/restore", status_code=202)
async def restore_backup(request: RestoreRequest, user: dict = Depends(require_admin)):
    """Queue a confirmed maintenance restore using the durable agent runner."""
    if request.confirmation != request.filename:
        raise HTTPException(status_code=400, detail="Type the backup filename to confirm restore")
    inspected = await _inspect_and_record(request.filename, user)
    available = set(inspected.get("components", []))
    selected = set(request.components or available)
    if not selected:
        raise HTTPException(status_code=400, detail="No restorable components were found")
    if not selected <= available:
        raise HTTPException(status_code=400, detail=f"Backup does not contain: {', '.join(sorted(selected - available))}")

    filepath = _resolve_local_backup(request.filename)
    job_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    config = {
        "backup_path": str(filepath),
        "components": sorted(selected),
        "dry_run": False,
        "confirmed": True,
    }
    db = await get_control_db()
    await db.execute(
        """INSERT INTO jobs
               (id, name, type, state, config_json, phase, progress, cancellable,
                started_by, created_at, updated_at)
           VALUES (?, ?, 'restore', 'pending', ?, 'queued', 0, 1, ?, ?, ?)""",
        (job_id, f"Restore {request.filename}", json.dumps(config), user["id"], now, now),
    )
    await db.execute(
        "INSERT INTO audit_log (user_id, action, details) VALUES (?, 'backup.restore.queued', ?)",
        (user["id"], json.dumps({"job_id": job_id, "filename": request.filename, "components": sorted(selected)})),
    )
    await db.commit()
    try:
        agent_job = await agent_client.run_job(
            "restore", f"Restore {request.filename}", {**config, "job_id": job_id}
        )
    except Exception as exc:
        await db.execute(
            "UPDATE jobs SET state='failed', error=?, completed_at=datetime('now') WHERE id=?",
            (f"Agent unavailable: {exc}", job_id),
        )
        await db.commit()
        raise HTTPException(status_code=503, detail=f"Restore could not be queued: {exc}")
    return agent_job


@router.get("/recovery-key")
async def export_recovery_key(user: dict = Depends(require_admin)):
    """Export the backup recovery key as a no-cache attachment."""
    try:
        key = await agent_client.export_backup_key()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Recovery key unavailable: {exc}")
    db = await get_control_db()
    await db.execute(
        "INSERT INTO audit_log (user_id, action) VALUES (?, 'backup.recovery_key.export')",
        (user["id"],),
    )
    await db.commit()
    return Response(
        content=f"{key}\n",
        media_type="text/plain",
        headers={
            "Content-Disposition": "attachment; filename=pi-control-recovery-key.txt",
            "Cache-Control": "no-store",
        },
    )


@router.post("/recovery-key/import")
async def import_recovery_key(request: RecoveryKeyImport, user: dict = Depends(require_admin)):
    try:
        result = await agent_client.import_backup_key(request.key, replace=request.replace)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Recovery key import failed: {exc}")
    db = await get_control_db()
    await db.execute(
        "INSERT INTO audit_log (user_id, action, details) VALUES (?, 'backup.recovery_key.import', ?)",
        (user["id"], json.dumps({"replaced": request.replace})),
    )
    await db.commit()
    return result


@router.post("/gdrive/client")
async def upload_gdrive_client(
    file: UploadFile = File(...),
    user: dict = Depends(require_admin),
):
    """Upload Google OAuth client JSON for device authorization."""
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="OAuth client file must be JSON")
    try:
        return await backup_service.upload_oauth_client(await file.read())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/gdrive/auth/start")
async def start_gdrive_auth(user: dict = Depends(require_admin)):
    """Start Google OAuth device-code flow."""
    try:
        return await backup_service.start_device_authorization()
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
    return await backup_service.disconnect_gdrive()


@router.delete("/gdrive/files/{file_id}")
async def delete_gdrive_backup(file_id: str, user: dict = Depends(require_admin)):
    """Delete a Pi Control backup file from Google Drive."""
    try:
        return backup_service.delete_drive_backup(file_id)
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
    filepath = _resolve_local_backup(filename)
    
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Backup file not found")
    
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
    filepath = _resolve_local_backup(filename)
    
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Backup file not found")
    
    filepath.unlink()
    return {"message": f"Deleted {filename}"}
