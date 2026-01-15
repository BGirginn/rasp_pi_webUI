"""
Pi Control Panel - File System Router

Handles file browsing, management, and transfer operations.
"""

import os
import shutil
import mimetypes
from datetime import datetime
from typing import List, Optional, Union
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .auth import get_current_user


router = APIRouter()

# Root directory restriction (optional security measure)
# For this "Control Panel", we likely want full root access, but be careful.
# If we wanted to sandbox, we'd set this to e.g., "/home/pi"
ROOT_DIR = "/" 

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

@router.post("/action")
async def file_action(
    action: FileAction,
    user: dict = Depends(get_current_user)
):
    """Perform file operations (Move, Copy, Rename, Delete, Mkdir)."""
    
    # Restrict destructive actions to Admin/Operator
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail="Viewers cannot modify files")
        
    src = action.path
    
    try:
        if action.action == "delete":
            if os.path.isdir(src):
                shutil.rmtree(src)
            else:
                os.remove(src)
            return {"message": "Deleted successfully"}
            
        elif action.action == "mkdir":
            os.makedirs(src, exist_ok=True)
            return {"message": "Directory created"}
            
        elif action.action == "rename":
            if not action.new_name:
                raise HTTPException(status_code=400, detail="New name required")
            
            parent = os.path.dirname(src)
            dst = os.path.join(parent, action.new_name)
            os.rename(src, dst)
            return {"message": "Renamed successfully"}
            
        elif action.action == "move":
            if not action.destination:
                raise HTTPException(status_code=400, detail="Destination required")
            shutil.move(src, action.destination)
            return {"message": "Moved successfully"}
            
        elif action.action == "copy":
            if not action.destination:
                raise HTTPException(status_code=400, detail="Destination required")
            if os.path.isdir(src):
                shutil.copytree(src, action.destination)
            else:
                shutil.copy2(src, action.destination)
            return {"message": "Copied successfully"}
            
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
            
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload")
async def upload_file(
    path: str = Form(...),
    files: List[UploadFile] = File(...),
    user: dict = Depends(get_current_user)
):
    """Upload files to a specific directory."""
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail="Viewers cannot upload files")
        
    if not os.path.exists(path) or not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="Target directory not found")
        
    uploaded_counts = 0
    try:
        for file in files:
            file_path = os.path.join(path, file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            uploaded_counts += 1
            
        return {"message": f"Successfully uploaded {uploaded_counts} files"}
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied to write to this directory")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/download")
async def download_file(
    path: str = Query(..., description="Absolute path to file"),
    user: dict = Depends(get_current_user)
):
    """Download a file."""
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
