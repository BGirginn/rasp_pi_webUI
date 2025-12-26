"""
Pi Control Panel - Manifest Wizard Router

Resource manifest creation and management.
"""

import json
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from db import get_control_db
from .auth import get_current_user

router = APIRouter()


class ManifestBase(BaseModel):
    name: str
    resource_id: str
    version: Optional[str] = "1.0.0"
    config: Dict


class ManifestResponse(ManifestBase):
    id: str
    approved_by: Optional[int]
    approved_at: Optional[str]
    created_at: str


class ManifestDiff(BaseModel):
    field: str
    old_value: Optional[str]
    new_value: Optional[str]


# Provider-specific manifest templates
MANIFEST_TEMPLATES = {
    "docker": {
        "container": {
            "image": "",
            "ports": [],
            "volumes": [],
            "environment": {},
            "restart_policy": "unless-stopped",
            "memory_limit": "512m",
            "cpu_limit": "1.0",
            "healthcheck": {
                "test": [],
                "interval": "30s",
                "timeout": "10s",
                "retries": 3
            },
            "labels": {},
            "networks": []
        }
    },
    "systemd": {
        "service": {
            "description": "",
            "exec_start": "",
            "working_directory": "",
            "user": "",
            "group": "",
            "restart": "on-failure",
            "restart_sec": 10,
            "environment": {},
            "capabilities": [],
            "protected": False
        }
    },
    "esp_device": {
        "device": {
            "name": "",
            "type": "",
            "telemetry_interval": 30,
            "capabilities": [],
            "commands": [],
            "alert_thresholds": {}
        }
    }
}


@router.get("/templates")
async def get_templates(user: dict = Depends(get_current_user)):
    """Get available manifest templates."""
    return MANIFEST_TEMPLATES


@router.get("/{manifest_id}", response_model=ManifestResponse)

async def get_manifest(manifest_id: str, user: dict = Depends(get_current_user)):
    """Get a manifest by ID."""
    db = await get_control_db()
    
    cursor = await db.execute(
        """SELECT id, resource_id, name, version, config_json, 
                  approved_by, approved_at, created_at
           FROM manifests WHERE id = ?""",
        (manifest_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Manifest not found")
    
    return ManifestResponse(
        id=row[0],
        resource_id=row[1],
        name=row[2],
        version=row[3],
        config=json.loads(row[4]),
        approved_by=row[5],
        approved_at=row[6],
        created_at=row[7]
    )


@router.get("/resource/{resource_id}", response_model=List[ManifestResponse])
async def get_resource_manifests(
    resource_id: str,
    user: dict = Depends(get_current_user)
):
    """Get all manifests for a resource."""
    db = await get_control_db()
    
    cursor = await db.execute(
        """SELECT id, resource_id, name, version, config_json,
                  approved_by, approved_at, created_at
           FROM manifests WHERE resource_id = ?
           ORDER BY created_at DESC""",
        (resource_id,)
    )
    rows = await cursor.fetchall()
    
    return [
        ManifestResponse(
            id=row[0],
            resource_id=row[1],
            name=row[2],
            version=row[3],
            config=json.loads(row[4]),
            approved_by=row[5],
            approved_at=row[6],
            created_at=row[7]
        )
        for row in rows
    ]


@router.post("/{manifest_id}/diff", response_model=List[ManifestDiff])

async def compare_manifests(
    manifest_id: str,
    compare_to: str,
    user: dict = Depends(get_current_user)
):
    """Compare two manifests and return differences."""
    db = await get_control_db()
    
    # Get both manifests
    cursor = await db.execute(
        "SELECT config_json FROM manifests WHERE id IN (?, ?)",
        (manifest_id, compare_to)
    )
    rows = await cursor.fetchall()
    
    if len(rows) != 2:
        raise HTTPException(status_code=404, detail="One or both manifests not found")
    
    config1 = json.loads(rows[0][0])
    config2 = json.loads(rows[1][0])
    
    # Find differences
    diffs = []
    all_keys = set(config1.keys()) | set(config2.keys())
    
    for key in all_keys:
        val1 = json.dumps(config1.get(key)) if key in config1 else None
        val2 = json.dumps(config2.get(key)) if key in config2 else None
        
        if val1 != val2:
            diffs.append(ManifestDiff(
                field=key,
                old_value=val1,
                new_value=val2
            ))
    
    return diffs
