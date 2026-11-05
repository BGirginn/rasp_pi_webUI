"""
Pi Control Panel - File System Router

Handles file browsing, management, and transfer operations.
"""

import os
import asyncio
import ctypes
import errno
import stat
import sys
from contextlib import contextmanager
from pathlib import Path
import shutil
import mimetypes
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .auth import get_current_user
from services.project_service import ensure_registered_path, registered_roots


router = APIRouter()

ROOT_DIR = "/"
FILE_MUTATION_LOCK = asyncio.Lock()
PROTECTED_PATHS = {
    "/",
    "/bin",
    "/boot",
    "/dev",
    "/etc",
    "/lib",
    "/lib64",
    "/opt/pi-control",
    "/proc",
    "/root",
    "/run",
    "/sbin",
    "/sys",
    "/usr",
    "/var",
    "/var/lib/pi-control",
}

class FileItem(BaseModel):
    name: str
    path: str
    type: str  # 'file' or 'directory'
    size: int
    modified: str
    mime_type: Optional[str] = None
    permissions: str
    is_hidden: bool

class FileAction(BaseModel):
    action: str  # 'move', 'copy', 'delete', 'rename', 'mkdir'
    path: str
    destination: Optional[str] = None  # For move/copy/rename
    new_name: Optional[str] = None     # For rename


def normalize_path(path: str) -> str:
    if not path or not os.path.isabs(path):
        raise HTTPException(status_code=400, detail="Absolute path required")
    return os.path.realpath(path)


def ensure_not_protected(path: str) -> None:
    normalized = normalize_path(path)
    if normalized == "/" or any(
        normalized == os.path.realpath(protected)
        or normalized.startswith(f"{os.path.realpath(protected)}{os.sep}")
        for protected in PROTECTED_PATHS
        if protected != "/"
    ):
        raise HTTPException(status_code=403, detail=f"Protected path cannot be modified: {normalized}")

def get_file_info(path: str) -> FileItem:
    try:
        stat = os.stat(path)
        is_dir = os.path.isdir(path)
        mime_type, _ = mimetypes.guess_type(path) if not is_dir else (None, None)
        
        return FileItem(
            name=os.path.basename(path),
            path=path,
            type="directory" if is_dir else "file",
            size=stat.st_size,
            modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            mime_type=mime_type,
            permissions=oct(stat.st_mode)[-3:],
            is_hidden=os.path.basename(path).startswith(".")
        )
    except Exception as e:
        # If we can't read it, return a minimal error placeholder or raise
        # For listing, we might want to skip or show partial info
        raise HTTPException(status_code=500, detail=f"Error accessing file {path}: {str(e)}")

@router.get("/list", response_model=List[FileItem])
async def list_files(
    path: str = Query(ROOT_DIR, description="Absolute path to list"),
    user: dict = Depends(get_current_user)
):
    """List contents of a directory."""
    path = normalize_path(path)
    try:
        path = str(await ensure_registered_path(path))
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail="Path is not a directory")

    # Security check: Prevent traversing above ROOT_DIR if we were sandboxing
    # if not os.path.commonpath([ROOT_DIR, os.path.abspath(path)]) == ROOT_DIR:
    #    raise HTTPException(status_code=403, detail="Access denied")

    if user['role'] == 'viewer':
         raise HTTPException(status_code=403, detail="Access denied")

    try:
        items = []
        with os.scandir(path) as it:
            for entry in it:
                try:
                    stat = entry.stat()
                    is_dir = entry.is_dir()
                    mime_type, _ = mimetypes.guess_type(entry.path) if not is_dir else (None, None)
                    
                    items.append(FileItem(
                        name=entry.name,
                        path=entry.path,
                        type="directory" if is_dir else "file",
                        size=stat.st_size,
                        modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        mime_type=mime_type,
                        permissions=oct(stat.st_mode)[-3:],
                        is_hidden=entry.name.startswith(".")
                    ))
                except PermissionError:
                    continue # Skip items we can't read
        
        # Sort: Directories first, then files (alphabetical)
        items.sort(key=lambda x: (x.type != "directory", x.name.lower()))
        return items
    except PermissionError:
         raise HTTPException(status_code=403, detail="Permission denied to access this directory")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def validate_filename(name: str) -> None:
    if not name or name in {".", ".."} or os.path.basename(name) != name or "\0" in name:
        raise HTTPException(status_code=400, detail="A valid filename without path separators is required")


@contextmanager
def directory_fd(path: str):
    # Anchor every component without following a link changed after path validation.
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open("/", flags)
    try:
        for part in Path(path).parts[1:]:
            next_descriptor = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        yield descriptor
    finally:
        os.close(descriptor)


def write_new_file(parent: str, name: str, source) -> None:
    with directory_fd(parent) as directory:
        descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        complete = False
        try:
            with os.fdopen(descriptor, "wb") as output:
                shutil.copyfileobj(source, output)
                output.flush()
                os.fsync(output.fileno())
            complete = True
        finally:
            if not complete:
                os.unlink(name, dir_fd=directory)


def rename_exclusive(source_fd: int, source: str, target_fd: int, target: str) -> None:
    # Standard os.rename replaces existing data; require the OS no-replace operation.
    libc = ctypes.CDLL(None, use_errno=True)
    function_name, flag = ("renameatx_np", 4) if sys.platform == "darwin" else ("renameat2", 1)
    function = getattr(libc, function_name, None)
    if function is None:
        raise OSError(errno.ENOTSUP, "Exclusive move is unsupported on this host")
    function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    function.restype = ctypes.c_int
    if function(source_fd, os.fsencode(source), target_fd, os.fsencode(target), flag):
        error = ctypes.get_errno()
        if error == errno.EXDEV:
            raise OSError(error, "Move across filesystems is unsupported; copy first, then delete the source explicitly")
        raise OSError(error, os.strerror(error))


def copy_entry(source_fd: int, name: str, target_fd: int, target: str) -> None:
    info = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
    if stat.S_ISDIR(info.st_mode):
        source = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=source_fd)
        try:
            os.mkdir(target, mode=0o700, dir_fd=target_fd)
            try:
                destination = os.open(target, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=target_fd)
                try:
                    for child in os.listdir(source):
                        copy_entry(source, child, destination, child)
                finally:
                    os.close(destination)
            except BaseException:
                shutil.rmtree(target, dir_fd=target_fd)
                raise
        finally:
            os.close(source)
    elif stat.S_ISREG(info.st_mode):
        source = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=source_fd)
        with os.fdopen(source, "rb") as input_file:
            if not stat.S_ISREG(os.fstat(input_file.fileno()).st_mode):
                raise PermissionError("Only regular files and directories can be copied")
            target_handle = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=target_fd)
            complete = False
            try:
                with os.fdopen(target_handle, "wb") as output:
                    shutil.copyfileobj(input_file, output)
                    output.flush()
                    os.fsync(output.fileno())
                complete = True
            finally:
                if not complete:
                    os.unlink(target, dir_fd=target_fd)
    else:
        raise PermissionError("Only regular files and directories can be copied; symbolic links are not allowed")


def perform_file_action(action: str, source: str, destination: Optional[str]) -> None:
    if destination and os.path.lexists(destination):
        raise FileExistsError(destination)
    with directory_fd(os.path.dirname(source)) as source_fd:
        name = os.path.basename(source)
        if action == "mkdir":
            os.mkdir(name, dir_fd=source_fd)
        elif action == "delete":
            info = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode):
                raise PermissionError("Modifying symbolic links is not allowed")
            if stat.S_ISDIR(info.st_mode):
                shutil.rmtree(name, dir_fd=source_fd)
            else:
                os.unlink(name, dir_fd=source_fd)
        else:
            with directory_fd(os.path.dirname(destination)) as target_fd:
                target = os.path.basename(destination)
                if action in {"move", "rename"}:
                    rename_exclusive(source_fd, name, target_fd, target)
                elif action == "copy":
                    copy_entry(source_fd, name, target_fd, target)


@router.post("/action")
async def file_action(action: FileAction, user: dict = Depends(get_current_user)):
    """Manage files inside registered roots without overwriting existing entries."""
    if user["role"] == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot modify files")
    if action.action not in {"copy", "move", "rename", "delete", "mkdir"}:
        raise HTTPException(status_code=400, detail="Invalid action")
    try:
        if os.path.islink(action.path):
            raise PermissionError("Modifying symbolic links is not allowed")
        source = normalize_path(action.path)
        await ensure_registered_path(source)
        if action.action != "copy":
            ensure_not_protected(source)
        destination = None
        if action.action == "rename":
            validate_filename(action.new_name or "")
            destination = os.path.join(os.path.dirname(source), action.new_name)
        elif action.action in {"copy", "move"}:
            if not action.destination:
                raise HTTPException(status_code=400, detail="Destination required")
            destination = os.path.normpath(action.destination)
        if destination:
            if os.path.lexists(destination):
                raise FileExistsError(destination)
            destination = normalize_path(destination)
            await ensure_registered_path(destination)
            ensure_not_protected(destination)
            if os.path.isdir(source) and os.path.commonpath([source, destination]) == source:
                raise HTTPException(status_code=400, detail="Destination cannot be inside the source directory")
        async with FILE_MUTATION_LOCK:
            await asyncio.to_thread(perform_file_action, action.action, source, destination)
        return {"message": "File operation completed"}
    except HTTPException:
        raise
    except FileExistsError:
        raise HTTPException(status_code=409, detail="Destination already exists; choose another name")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File or destination directory not found")
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"File operation failed: {exc.strerror or str(exc)}")


@router.post("/upload")
async def upload_file(path: str = Form(...), files: List[UploadFile] = File(...), user: dict = Depends(get_current_user)):
    """Create new files; conflicting names and symlinks are never overwritten."""
    if user["role"] == "viewer":
        raise HTTPException(status_code=403, detail="Viewers cannot upload files")
    try:
        path = str(await ensure_registered_path(normalize_path(path)))
        ensure_not_protected(path)
        if not os.path.isdir(path):
            raise FileNotFoundError(path)
        for file in files:
            validate_filename(file.filename or "")
        uploaded = 0
        async with FILE_MUTATION_LOCK:
            for file in files:
                await asyncio.to_thread(write_new_file, path, file.filename, file.file)
                uploaded += 1
        return {"message": f"Successfully uploaded {uploaded} files"}
    except HTTPException:
        raise
    except FileExistsError:
        raise HTTPException(status_code=409, detail="A file with that name already exists; existing files were preserved")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Target directory not found")
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc.strerror or str(exc)}")

@router.get("/download")
async def download_file(
    path: str = Query(..., description="Absolute path to file"),
    user: dict = Depends(get_current_user)
):
    """Download a file."""
    path = normalize_path(path)
    try:
        path = str(await ensure_registered_path(path))
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    
    if os.path.isdir(path):
        raise HTTPException(status_code=400, detail="Cannot download a directory directly")
        
    if user['role'] == 'viewer':
         raise HTTPException(status_code=403, detail="Access denied")
        
    return FileResponse(
        path=path, 
        filename=os.path.basename(path),
        media_type='application/octet-stream'
    )


@router.get("/roots")
async def file_roots(user: dict = Depends(get_current_user)):
    return {"roots": [str(path) for path in await registered_roots()]}
