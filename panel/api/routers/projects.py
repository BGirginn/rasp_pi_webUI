"""Registered project roots and local snapshot operations."""

import json
import re
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from db import get_control_db
from services.project_service import allowed_parents, ensure_within, project_service
from .auth import get_current_user, require_role


router = APIRouter()
PROJECT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    root_path: str
    project_type: str = Field(default="directory", max_length=30)
    excludes: List[str] = Field(default_factory=lambda: [".git", "node_modules", ".venv", "dist"])


class RestoreRequest(BaseModel):
    confirmation: str


@router.get("")
async def list_projects(user: dict = Depends(get_current_user)):
    db = await get_control_db()
    cursor = await db.execute(
        "SELECT id, name, root_path, project_type, excludes_json, enabled, created_at, updated_at FROM projects ORDER BY name"
    )
    return [{
        "id": row[0], "name": row[1], "root_path": row[2], "project_type": row[3],
        "excludes": json.loads(row[4] or "[]"), "enabled": bool(row[5]),
        "created_at": row[6], "updated_at": row[7],
    } for row in await cursor.fetchall()]


@router.post("")
async def register_project(
    request: ProjectCreate,
    user: dict = Depends(require_role("admin")),
):
    try:
        root = ensure_within(Path(request.root_path), allowed_parents())
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not root.is_dir():
        raise HTTPException(status_code=400, detail="Project root must be an existing directory")
    project_id = re.sub(r"[^a-z0-9_-]+", "-", request.name.lower()).strip("-")[:48]
    if not PROJECT_ID_RE.fullmatch(project_id):
        project_id = f"project-{uuid.uuid4().hex[:8]}"
    clean_excludes = []
    for item in request.excludes:
        normalized = item.strip().strip("/")
        if normalized and ".." not in Path(normalized).parts:
            clean_excludes.append(normalized)
    db = await get_control_db()
    try:
        await db.execute(
            """INSERT INTO projects (id, name, root_path, project_type, excludes_json, created_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (project_id, request.name, str(root), request.project_type, json.dumps(clean_excludes), user["id"]),
        )
        await db.commit()
    except Exception as exc:
        raise HTTPException(status_code=409, detail=f"Project already registered: {exc}")
    return {"id": project_id, "name": request.name, "root_path": str(root), "excludes": clean_excludes}


@router.delete("/{project_id}")
async def unregister_project(project_id: str, user: dict = Depends(require_role("admin"))):
    db = await get_control_db()
    result = await db.execute("UPDATE projects SET enabled=0, updated_at=datetime('now') WHERE id=?", (project_id,))
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"disabled": True}


@router.get("/{project_id}/snapshots")
async def list_snapshots(project_id: str, user: dict = Depends(get_current_user)):
    db = await get_control_db()
    cursor = await db.execute(
        "SELECT id, filename, checksum, size_bytes, manifest_json, created_at FROM project_snapshots WHERE project_id=? ORDER BY created_at DESC",
        (project_id,),
    )
    return [{"id": row[0], "filename": row[1], "checksum": row[2], "size_bytes": row[3], "manifest": json.loads(row[4]), "created_at": row[5]} for row in await cursor.fetchall()]


@router.post("/{project_id}/snapshots")
async def create_snapshot(project_id: str, user: dict = Depends(require_role("admin", "operator"))):
    try:
        return await project_service.create_snapshot(project_id, user["id"])
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{project_id}/snapshots/{snapshot_id}/restore")
async def restore_snapshot(
    project_id: str,
    snapshot_id: str,
    request: RestoreRequest,
    user: dict = Depends(require_role("admin")),
):
    try:
        return await project_service.restore_snapshot(project_id, snapshot_id, request.confirmation, user["id"])
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
