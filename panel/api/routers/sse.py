"""
Pi Control Panel - SSE Router

Server-Sent Events endpoints for real-time updates.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from services.sse import sse_manager, Channels
from .auth import get_current_user

router = APIRouter()


@router.get("/stream")
async def stream(request: Request, user: dict = Depends(get_current_user)):
    """Main SSE stream endpoint. Subscribe to channels via query params."""
    client_id = str(uuid.uuid4())
    
    # Get requested channels from query params
    channels = request.query_params.get("channels", "").split(",")
    channels = [c.strip() for c in channels if c.strip()]
    
    # Default channels if none specified
    if not channels:
        channels = [Channels.TELEMETRY, Channels.RESOURCES, Channels.ALERTS]
    
    client = await sse_manager.connect(client_id, user["id"])
    
    # Subscribe to channels
    for channel in channels:
        await sse_manager.subscribe(client_id, channel)
    
    async def event_stream():
        try:
            async for event in sse_manager.event_generator(client):
                # Check if client disconnected
                if await request.is_disconnected():
                    break
                yield event
        finally:
            await sse_manager.disconnect(client_id)
    
    return EventSourceResponse(event_stream())


@router.get("/telemetry")
async def telemetry_stream(request: Request, user: dict = Depends(get_current_user)):
    """Stream live telemetry updates."""
    client_id = str(uuid.uuid4())
    
    client = await sse_manager.connect(client_id, user["id"])
    await sse_manager.subscribe(client_id, Channels.TELEMETRY)
    
    async def event_stream():
        try:
            # Send initial telemetry
            yield f"event: connected\ndata: {{\"client_id\": \"{client_id}\"}}\n\n"
            
            async for event in sse_manager.event_generator(client):
                if await request.is_disconnected():
                    break
                yield event
        finally:
            await sse_manager.disconnect(client_id)
    
    return EventSourceResponse(event_stream())


@router.get("/resources")
async def resources_stream(request: Request, user: dict = Depends(get_current_user)):
    """Stream resource updates."""
    client_id = str(uuid.uuid4())
    
    client = await sse_manager.connect(client_id, user["id"])
    await sse_manager.subscribe(client_id, Channels.RESOURCES)
    
    async def event_stream():
        try:
            yield f"event: connected\ndata: {{\"client_id\": \"{client_id}\"}}\n\n"
            
            async for event in sse_manager.event_generator(client):
                if await request.is_disconnected():
                    break
                yield event
        finally:
            await sse_manager.disconnect(client_id)
    
    return EventSourceResponse(event_stream())


@router.get("/logs/{resource_id}")
async def logs_stream(
    resource_id: str,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Stream logs for a specific resource."""
    client_id = str(uuid.uuid4())
    
    client = await sse_manager.connect(client_id, user["id"])
    await sse_manager.subscribe(client_id, Channels.logs(resource_id))
    
    async def event_stream():
        try:
            yield f"event: connected\ndata: {{\"resource_id\": \"{resource_id}\"}}\n\n"
            
            async for event in sse_manager.event_generator(client):
                if await request.is_disconnected():
                    break
                yield event
        finally:
            await sse_manager.disconnect(client_id)
    
    return EventSourceResponse(event_stream())


@router.get("/jobs/{job_id}")
async def job_stream(
    job_id: str,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Stream updates for a specific job."""
    client_id = str(uuid.uuid4())
    
    client = await sse_manager.connect(client_id, user["id"])
    await sse_manager.subscribe(client_id, Channels.job(job_id))
    
    async def event_stream():
        try:
            yield f"event: connected\ndata: {{\"job_id\": \"{job_id}\"}}\n\n"
            
            async for event in sse_manager.event_generator(client):
                if await request.is_disconnected():
                    break
                yield event
        finally:
            await sse_manager.disconnect(client_id)
    
    return EventSourceResponse(event_stream())


@router.get("/alerts")
async def alerts_stream(request: Request, user: dict = Depends(get_current_user)):
    """Stream alert updates."""
    client_id = str(uuid.uuid4())
    
    client = await sse_manager.connect(client_id, user["id"])
    await sse_manager.subscribe(client_id, Channels.ALERTS)
    
    async def event_stream():
        try:
            yield f"event: connected\ndata: {{\"client_id\": \"{client_id}\"}}\n\n"
            
            async for event in sse_manager.event_generator(client):
                if await request.is_disconnected():
                    break
                yield event
        finally:
            await sse_manager.disconnect(client_id)
    
    return EventSourceResponse(event_stream())


@router.get("/stats")
async def sse_stats(user: dict = Depends(get_current_user)):
    """Get SSE connection statistics."""
    return {
        "total_clients": sse_manager.client_count,
        "channels": {
            Channels.TELEMETRY: sse_manager.get_channel_clients(Channels.TELEMETRY),
            Channels.RESOURCES: sse_manager.get_channel_clients(Channels.RESOURCES),
            Channels.ALERTS: sse_manager.get_channel_clients(Channels.ALERTS),
            Channels.JOBS: sse_manager.get_channel_clients(Channels.JOBS),
        }
    }
