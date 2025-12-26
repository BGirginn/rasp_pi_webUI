"""
Pi Control Panel - Alerts Router

Handles alert rules, active alerts, and notifications.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from db import get_control_db
from services.sse import sse_manager, Channels
from .auth import get_current_user

router = APIRouter()


class AlertRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    metric: str
    condition: str  # gt, gte, lt, lte, eq, neq
    threshold: float
    severity: str  # info, warning, critical
    cooldown_minutes: int = 15
    notify_channels: Optional[List[str]] = None


class AlertRuleResponse(AlertRuleCreate):
    id: str
    enabled: bool
    created_at: str


class AlertResponse(BaseModel):
    id: str
    rule_id: str
    rule_name: Optional[str]
    state: str
    severity: str
    message: Optional[str]
    value: Optional[float]
    fired_at: Optional[str]
    resolved_at: Optional[str]
    acknowledged_by: Optional[int]
    acknowledged_at: Optional[str]


# Alert condition operators
CONDITION_OPERATORS = {
    "gt": lambda v, t: v > t,
    "gte": lambda v, t: v >= t,
    "lt": lambda v, t: v < t,
    "lte": lambda v, t: v <= t,
    "eq": lambda v, t: v == t,
    "neq": lambda v, t: v != t,
}


# === Alert Rules ===

@router.get("/rules", response_model=List[AlertRuleResponse])
async def list_alert_rules(user: dict = Depends(get_current_user)):
    """List all alert rules."""
    db = await get_control_db()
    
    cursor = await db.execute(
        """SELECT id, name, description, metric, condition, threshold, 
                  severity, cooldown_minutes, enabled, notify_channels, created_at
           FROM alert_rules ORDER BY name"""
    )
    rows = await cursor.fetchall()
    
    return [
        AlertRuleResponse(
            id=row[0],
            name=row[1],
            description=row[2],
            metric=row[3],
            condition=row[4],
            threshold=row[5],
            severity=row[6],
            cooldown_minutes=row[7],
            enabled=bool(row[8]),
            notify_channels=json.loads(row[9]) if row[9] else None,
            created_at=row[10]
        )
        for row in rows
    ]


@router.get("", response_model=List[AlertResponse])
async def list_alerts(
    state: Optional[str] = Query(None, description="Filter by state"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    user: dict = Depends(get_current_user)
):
    """List active alerts."""
    db = await get_control_db()
    
    query = """SELECT a.id, a.rule_id, r.name, a.state, a.severity, a.message,
                      a.value, a.fired_at, a.resolved_at, a.acknowledged_by, a.acknowledged_at
               FROM alerts a
               LEFT JOIN alert_rules r ON a.rule_id = r.id
               WHERE 1=1"""
    params = []
    
    if state:
        query += " AND a.state = ?"
        params.append(state)
    
    if severity:
        query += " AND a.severity = ?"
        params.append(severity)
    
    query += " ORDER BY a.fired_at DESC"
    
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    
    return [
        AlertResponse(
            id=row[0],
            rule_id=row[1],
            rule_name=row[2],
            state=row[3],
            severity=row[4],
            message=row[5],
            value=row[6],
            fired_at=row[7],
            resolved_at=row[8],
            acknowledged_by=row[9],
            acknowledged_at=row[10]
        )
        for row in rows
    ]


@router.get("/active/count")
async def active_alert_count(user: dict = Depends(get_current_user)):
    """Get count of active alerts by severity."""
    db = await get_control_db()
    
    cursor = await db.execute(
        """SELECT severity, COUNT(*) FROM alerts
           WHERE state IN ('pending', 'firing')
           GROUP BY severity"""
    )
    rows = await cursor.fetchall()
    
    counts = {row[0]: row[1] for row in rows}
    total = sum(counts.values())
    
    return {
        "total": total,
        "by_severity": counts
    }


@router.get("/history")
async def alert_history(
    days: int = Query(7, ge=1, le=90),
    rule_id: Optional[str] = Query(None),
    user: dict = Depends(get_current_user)
):
    """Get alert history."""
    db = await get_control_db()
    
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    
    query = """SELECT alert_id, rule_id, rule_name, severity, message, 
                      value, fired_at, resolved_at, duration_seconds
               FROM alert_history WHERE created_at >= ?"""
    params = [since]
    
    if rule_id:
        query += " AND rule_id = ?"
        params.append(rule_id)
    
    query += " ORDER BY fired_at DESC LIMIT 500"
    
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    
    return {
        "period_days": days,
        "alerts": [
            {
                "alert_id": row[0],
                "rule_id": row[1],
                "rule_name": row[2],
                "severity": row[3],
                "message": row[4],
                "value": row[5],
                "fired_at": row[6],
                "resolved_at": row[7],
                "duration_seconds": row[8]
            }
            for row in rows
        ]
    }
