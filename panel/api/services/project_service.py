"""Allowlisted project registry with local verified snapshots."""

import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Iterable, List

from db import get_control_db


SNAPSHOT_DIR = Path(os.getenv("PROJECT_SNAPSHOT_DIR", "/opt/pi-control/project-snapshots"))
DEFAULT_ALLOWED_PARENTS = "/home,/srv,/opt/projects"


def allowed_parents() -> List[Path]:
    configured = os.getenv("PROJECT_ALLOWED_ROOTS", DEFAULT_ALLOWED_PARENTS)
    return [Path(item.strip()).resolve() for item in configured.split(",") if item.strip()]


def ensure_within(path: Path, roots: Iterable[Path]) -> Path:
    resolved = path.resolve()
    if not any(resolved == root or root in resolved.parents for root in roots):
        raise ValueError(f"Path is outside allowed project parents: {resolved}")
    return resolved


async def registered_roots() -> List[Path]:
    db = await get_control_db()
    cursor = await db.execute("SELECT root_path FROM projects WHERE enabled=1")
    return [Path(row[0]).resolve() for row in await cursor.fetchall()]


async def ensure_registered_path(path: str) -> Path:
    roots = await registered_roots()
    if not roots:
        raise PermissionError("No project roots are registered")
    try:
        return ensure_within(Path(path), roots)
    except ValueError as exc:
        raise PermissionError(str(exc)) from exc


class ProjectService:
    async def create_snapshot(self, project_id: str, user_id: int) -> Dict:
        project = await self._project(project_id)
        root = Path(project["root_path"])
        if not root.is_dir():
            raise FileNotFoundError(f"Project root not found: {root}")
        excludes = set(project["excludes"])
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        snapshot_id = str(uuid.uuid4())
        filename = f"{project_id}-{snapshot_id}.tar.gz"
        target = SNAPSHOT_DIR / filename
        temporary = target.with_suffix(".tmp")

        def excluded(tar_info: tarfile.TarInfo):
            relative = tar_info.name.removeprefix("./")
            if any(relative == item or relative.startswith(f"{item}/") for item in excludes):
                return None
            if tar_info.issym() or tar_info.islnk():
                return None
            return tar_info

        with tarfile.open(temporary, "w:gz") as archive:
            archive.add(root, arcname=".", recursive=True, filter=excluded)
        checksum = self._checksum(temporary)
        os.replace(temporary, target)
        manifest = {
            "version": 1,
            "project_id": project_id,
            "project_name": project["name"],
            "root_path": str(root),
            "excludes": sorted(excludes),
        }
        db = await get_control_db()
        await db.execute(
            """INSERT INTO project_snapshots
               (id, project_id, filename, checksum, size_bytes, manifest_json, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (snapshot_id, project_id, filename, checksum, target.stat().st_size, json.dumps(manifest), user_id),
        )
        await db.commit()
        return {"id": snapshot_id, "filename": filename, "checksum": checksum, "size_bytes": target.stat().st_size, "manifest": manifest}

    async def restore_snapshot(self, project_id: str, snapshot_id: str, confirmation: str, user_id: int) -> Dict:
        project = await self._project(project_id)
        if confirmation != project["name"]:
            raise ValueError("Confirmation must exactly match the project name")
        db = await get_control_db()
        cursor = await db.execute(
            "SELECT filename, checksum FROM project_snapshots WHERE id=? AND project_id=?",
            (snapshot_id, project_id),
        )
        row = await cursor.fetchone()
        if not row:
            raise FileNotFoundError("Snapshot not found")
        archive_path = SNAPSHOT_DIR / row[0]
        if not archive_path.is_file() or self._checksum(archive_path) != row[1]:
            raise ValueError("Snapshot checksum validation failed")

        pre_restore = await self.create_snapshot(project_id, user_id)
        root = Path(project["root_path"])
        parent = root.parent
        staging = Path(tempfile.mkdtemp(prefix=f".{root.name}.restore-", dir=parent))
        previous = parent / f".{root.name}.previous-{uuid.uuid4().hex[:8]}"
        try:
            with tarfile.open(archive_path, "r:gz") as archive:
                self._safe_extract(archive, staging)
            if root.exists():
                os.replace(root, previous)
            os.replace(staging, root)
            if previous.exists():
                shutil.rmtree(previous)
        except Exception:
            if not root.exists() and previous.exists():
                os.replace(previous, root)
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return {"restored": True, "snapshot_id": snapshot_id, "pre_restore_snapshot_id": pre_restore["id"]}

    async def _project(self, project_id: str) -> Dict:
        db = await get_control_db()
        cursor = await db.execute(
            "SELECT id, name, root_path, excludes_json FROM projects WHERE id=? AND enabled=1",
            (project_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise FileNotFoundError("Project not found")
        return {"id": row[0], "name": row[1], "root_path": row[2], "excludes": json.loads(row[3] or "[]")}

    @staticmethod
    def _checksum(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _safe_extract(archive: tarfile.TarFile, target: Path) -> None:
        target_resolved = target.resolve()
        for member in archive.getmembers():
            member_path = (target / member.name).resolve()
            if member_path != target_resolved and target_resolved not in member_path.parents:
                raise ValueError("Unsafe path in project snapshot")
            if member.issym() or member.islnk():
                raise ValueError("Links are not allowed in project snapshots")
        archive.extractall(target, filter="data")


project_service = ProjectService()
