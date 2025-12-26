"""
Pi Control Panel - Resources Router

Handles resource discovery, management, and actions.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from db import get_control_db
from services.agent_client import agent_client
from .auth import get_current_user

router = APIRouter()


# Pydantic models
class ResourceResponse(BaseModel):
    id: str
    name: str
    type: str
    resource_class: str
    provider: str
    state: str
    health_score: int
    managed: bool
    updated_at: str
    cpu_usage: Optional[float] = 0.0
    memory_usage: Optional[float] = 0.0


# Routes
@router.get("", response_model=List[ResourceResponse])
async def list_resources(
    provider: Optional[str] = Query(None, description="Filter by provider"),
    resource_class: Optional[str] = Query(None, description="Filter by class"),
    managed: Optional[bool] = Query(None, description="Filter by managed status"),
    user: dict = Depends(get_current_user)
):
    """List all discovered resources."""
    db = await get_control_db()
    
    query = "SELECT id, name, type, class, provider, state, health_score, managed, updated_at FROM resources WHERE 1=1"
    params = []
    
    if provider:
        query += " AND provider = ?"
        params.append(provider)
    
    if resource_class:
        query += " AND class = ?"
        params.append(resource_class)
    
    if managed is not None:
        query += " AND managed = ?"
        params.append(1 if managed else 0)
    
    query += " ORDER BY name"
    
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    
    # If no resources in DB, fall back to agent snapshot
    if len(rows) == 0:
        agent_resources = await _get_agent_resources(
            provider=provider,
            resource_class=resource_class,
            managed=managed,
            requested_by=user,
        )
        if agent_resources:
            return agent_resources
    
    return [
        ResourceResponse(
            id=row[0],
            name=row[1],
            type=row[2],
            resource_class=row[3],
            provider=row[4],
            state=row[5],
            health_score=row[6],
            managed=bool(row[7]),
            updated_at=row[8]
        )
        for row in rows
    ]



async def _get_agent_resources(
    *,
    provider: Optional[str],
    resource_class: Optional[str],
    managed: Optional[bool],
    requested_by: Optional[dict],
) -> List[ResourceResponse]:
    """Get resources from agent snapshot without host command execution."""
    try:
        snapshot = await agent_client.get_snapshot(requested_by=requested_by)
    except Exception:
        return []

    if not isinstance(snapshot, dict):
        return []

    resources = snapshot.get("resources", [])
    timestamp = snapshot.get("timestamp") or datetime.utcnow().isoformat()
    mapped: List[ResourceResponse] = []

    for resource in resources:
        if not isinstance(resource, dict):
            continue

        mapped.append(ResourceResponse(
            id=resource.get("id", ""),
            name=resource.get("name", ""),
            type=resource.get("type", ""),
            resource_class=resource.get("class", "UNKNOWN"),
            provider=resource.get("provider", "unknown"),
            state=resource.get("state", "unknown"),
            health_score=resource.get("health_score", 0),
            managed=bool(resource.get("managed", False)),
            updated_at=resource.get("last_seen") or timestamp,
            cpu_usage=resource.get("metadata", {}).get("cpu_usage", 0.0),
            memory_usage=resource.get("metadata", {}).get("memory_usage", 0.0),
        ))

    filtered = []
    for entry in mapped:
        if provider and entry.provider != provider:
            continue
        if resource_class and entry.resource_class != resource_class:
            continue
        if managed is not None and entry.managed is not managed:
            continue
        filtered.append(entry)

    return filtered


@router.get("/unmanaged", response_model=List[ResourceResponse])
async def list_unmanaged_resources(user: dict = Depends(get_current_user)):
    """List unmanaged resources (discovery queue)."""
    db = await get_control_db()
    
    cursor = await db.execute(
        """SELECT id, name, type, class, provider, state, health_score, managed, updated_at
           FROM resources WHERE managed = 0 ORDER BY discovered_at DESC"""
    )
    rows = await cursor.fetchall()
    
    return [
        ResourceResponse(
            id=row[0],
            name=row[1],
            type=row[2],
            resource_class=row[3],
            provider=row[4],
            state=row[5],
            health_score=row[6],
            managed=bool(row[7]),
            updated_at=row[8]
        )
        for row in rows
    ]


@router.get("/{resource_id}", response_model=ResourceResponse)
async def get_resource(resource_id: str, user: dict = Depends(get_current_user)):
    """Get a specific resource."""
    db = await get_control_db()
    
    cursor = await db.execute(
        """SELECT id, name, type, class, provider, state, health_score, managed, updated_at
           FROM resources WHERE id = ?""",
        (resource_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    return ResourceResponse(
        id=row[0],
        name=row[1],
        type=row[2],
        resource_class=row[3],
        provider=row[4],
        state=row[5],
        health_score=row[6],
        managed=bool(row[7]),
        updated_at=row[8]
    )
