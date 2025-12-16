"""
Pi Control Panel - Logs Router

Handles log retrieval, search, and streaming.
"""

import asyncio
from datetime import datetime
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from services.agent_client import agent_client
from services.sse import sse_manager, Channels
from .auth import get_current_user

router = APIRouter()


class LogLine(BaseModel):
    timestamp: str
    level: str
    message: str
    source: Optional[str] = None


class LogsResponse(BaseModel):
    resource_id: str
    lines: List[LogLine]
    total: int


class SearchResult(BaseModel):
    line_number: int
    timestamp: str
    content: str
    context: List[str]


@router.get("/{resource_id}", response_model=LogsResponse)
async def get_logs(
    resource_id: str,
    tail: int = Query(100, ge=1, le=10000),
    since: Optional[str] = Query(None, description="ISO timestamp"),
    until: Optional[str] = Query(None, description="ISO timestamp"),
    level: Optional[str] = Query(None, description="Filter by level (error, warning, info)"),
    user: dict = Depends(get_current_user)
):
    """Get logs for a resource."""
    try:
        raw_logs = await agent_client.get_resource_logs(resource_id, tail)
    except Exception as e:
        # Return empty list if agent unavailable
        print(f"Error fetching logs: {e}")
        raw_logs = []
    
    # Parse log lines
    lines = []
    for raw_line in raw_logs:
        parsed = _parse_log_line(raw_line)
        
        # Apply level filter
        if level and parsed.level.lower() != level.lower():
            continue
        
        # Apply timestamp filters
        if since and parsed.timestamp < since:
            continue
        if until and parsed.timestamp > until:
            continue
        
        lines.append(parsed)
    
    return LogsResponse(
        resource_id=resource_id,
        lines=lines,
        total=len(lines)
    )


@router.get("/{resource_id}/search", response_model=List[SearchResult])
async def search_logs(
    resource_id: str,
    query: str = Query(..., min_length=1, max_length=100),
    since: Optional[str] = Query(None),
    until: Optional[str] = Query(None),
    context_lines: int = Query(2, ge=0, le=10),
    max_results: int = Query(100, ge=1, le=1000),
    user: dict = Depends(get_current_user)
):
    """Search logs for a resource."""
    try:
        raw_logs = await agent_client.get_resource_logs(resource_id, 5000)
    except Exception:
        raw_logs = []
    
    results = []
    query_lower = query.lower()
    
    for i, raw_line in enumerate(raw_logs):
        if query_lower in raw_line.lower():
            parsed = _parse_log_line(raw_line)
            
            # Get context lines
            start = max(0, i - context_lines)
            end = min(len(raw_logs), i + context_lines + 1)
            context = raw_logs[start:end]
            
            results.append(SearchResult(
                line_number=i,
                timestamp=parsed.timestamp,
                content=raw_line,
                context=context
            ))
            
            if len(results) >= max_results:
                break
    
    return results


@router.get("/{resource_id}/stream")
async def stream_logs(
    resource_id: str,
    request=None,
    user: dict = Depends(get_current_user)
):
    """Stream logs via SSE."""
    from fastapi import Request
    
    client_id = str(uuid.uuid4())
    
    client = await sse_manager.connect(client_id, user["id"])
    await sse_manager.subscribe(client_id, Channels.logs(resource_id))
    
    async def event_stream():
        try:
            # Send initial logs
            try:
                initial_logs = await agent_client.get_resource_logs(resource_id, 50)
                for log_line in initial_logs[-50:]:
                    parsed = _parse_log_line(log_line)
                    yield f"event: log\ndata: {{\"timestamp\": \"{parsed.timestamp}\", \"level\": \"{parsed.level}\", \"message\": \"{parsed.message}\"}}\n\n"
            except Exception:
                yield f"event: error\ndata: {{\"message\": \"Could not fetch initial logs\"}}\n\n"
            
            # Stream new logs
            async for event in sse_manager.event_generator(client):
                yield event
        finally:
            await sse_manager.disconnect(client_id)
    
    return EventSourceResponse(event_stream())


@router.get("/{resource_id}/tail")
async def tail_logs(
    resource_id: str,
    lines: int = Query(50, ge=1, le=500),
    user: dict = Depends(get_current_user)
):
    """Get the latest N log lines."""
    try:
        raw_logs = await agent_client.get_resource_logs(resource_id, lines)
    except Exception:
        raw_logs = []
    
    parsed_lines = [_parse_log_line(line) for line in raw_logs[-lines:]]
    
    return {
        "resource_id": resource_id,
        "lines": [line.dict() for line in parsed_lines],
        "count": len(parsed_lines)
    }


@router.get("/{resource_id}/stats")
async def log_stats(
    resource_id: str,
    hours: int = Query(24, ge=1, le=168),
    user: dict = Depends(get_current_user)
):
    """Get log statistics for a resource."""
    try:
        raw_logs = await agent_client.get_resource_logs(resource_id, 10000)
    except Exception:
        raw_logs = []
    
    # Count by level
    level_counts = {"error": 0, "warning": 0, "info": 0, "debug": 0, "unknown": 0}
    
    for line in raw_logs:
        parsed = _parse_log_line(line)
        level_key = parsed.level.lower() if parsed.level.lower() in level_counts else "unknown"
        level_counts[level_key] += 1
    
    return {
        "resource_id": resource_id,
        "total_lines": len(raw_logs),
        "by_level": level_counts
    }


def _parse_log_line(raw_line: str) -> LogLine:
    """Parse a raw log line into structured format."""
    # Try common log formats
    
    # Docker/systemd format: timestamp [LEVEL] message
    import re
    
    # ISO timestamp with level in brackets
    match = re.match(
        r'^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s*\[?(\w+)\]?\s*(.*)$',
        raw_line
    )
    
    if match:
        return LogLine(
            timestamp=match.group(1),
            level=match.group(2).upper(),
            message=match.group(3)
        )
    
    # Syslog format: Mon DD HH:MM:SS hostname service: message
    match = re.match(
        r'^(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+(\S+)\s+(\S+):\s*(.*)$',
        raw_line
    )
    
    if match:
        return LogLine(
            timestamp=match.group(1),
            level="INFO",
            message=match.group(4),
            source=match.group(3)
        )
    
    # Fallback: unknown format
    return LogLine(
        timestamp=datetime.utcnow().isoformat(),
        level="INFO",
        message=raw_line
    )
