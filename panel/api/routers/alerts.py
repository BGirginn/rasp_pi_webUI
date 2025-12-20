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
from .auth import get_current_user, require_role

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


@router.post("/rules", response_model=AlertRuleResponse)
async def create_alert_rule(
    rule: AlertRuleCreate,
    user: dict = Depends(require_role("admin"))
):
    """Create a new alert rule."""
    if rule.condition not in CONDITION_OPERATORS:
        raise HTTPException(status_code=400, detail=f"Invalid condition: {rule.condition}")
    
    if rule.severity not in ("info", "warning", "critical"):
        raise HTTPException(status_code=400, detail="Invalid severity")
    
    db = await get_control_db()
    
    rule_id = str(uuid.uuid4())[:8]
    notify_json = json.dumps(rule.notify_channels) if rule.notify_channels else None
    now = datetime.utcnow().isoformat()
    
    await db.execute(
        """INSERT INTO alert_rules 
           (id, name, description, metric, condition, threshold, severity, 
            cooldown_minutes, enabled, notify_channels, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
        (rule_id, rule.name, rule.description, rule.metric, rule.condition,
         rule.threshold, rule.severity, rule.cooldown_minutes, notify_json, now)
    )
    
    # Audit log
    await db.execute(
        """INSERT INTO audit_log (user_id, action, details)
           VALUES (?, ?, ?)""",
        (user["id"], "alert_rule.create", f"rule_id: {rule_id}, name: {rule.name}")
    )
    
    await db.commit()
    
    return AlertRuleResponse(
        id=rule_id,
        enabled=True,
        created_at=now,
        **rule.dict()
    )


@router.put("/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: str,
    rule: AlertRuleCreate,
    user: dict = Depends(require_role("admin"))
):
    """Update an alert rule."""
    db = await get_control_db()
    
    cursor = await db.execute("SELECT id FROM alert_rules WHERE id = ?", (rule_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Rule not found")
    
    notify_json = json.dumps(rule.notify_channels) if rule.notify_channels else None
    
    await db.execute(
        """UPDATE alert_rules SET
           name = ?, description = ?, metric = ?, condition = ?, threshold = ?,
           severity = ?, cooldown_minutes = ?, notify_channels = ?, updated_at = datetime('now')
           WHERE id = ?""",
        (rule.name, rule.description, rule.metric, rule.condition, rule.threshold,
         rule.severity, rule.cooldown_minutes, notify_json, rule_id)
    )
    
    await db.commit()
    
    return AlertRuleResponse(
        id=rule_id,
        enabled=True,
        created_at=datetime.utcnow().isoformat(),
        **rule.dict()
    )


@router.post("/rules/{rule_id}/toggle")
async def toggle_alert_rule(
    rule_id: str,
    enabled: bool,
    user: dict = Depends(require_role("admin"))
):
    """Enable or disable an alert rule."""
    db = await get_control_db()
    
    result = await db.execute(
        "UPDATE alert_rules SET enabled = ? WHERE id = ?",
        (1 if enabled else 0, rule_id)
    )
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    await db.commit()
    
    return {"message": f"Rule {rule_id} {'enabled' if enabled else 'disabled'}"}


@router.delete("/rules/{rule_id}")
async def delete_alert_rule(
    rule_id: str,
    user: dict = Depends(require_role("admin"))
):
    """Delete an alert rule."""
    db = await get_control_db()
    
    # First delete all alerts for this rule
    await db.execute("DELETE FROM alerts WHERE rule_id = ?", (rule_id,))
    
    result = await db.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    await db.commit()
    
    return {"message": f"Rule {rule_id} deleted"}


# === Active Alerts ===

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


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    user: dict = Depends(get_current_user)
):
    """Acknowledge an alert."""
    db = await get_control_db()
    
    cursor = await db.execute(
        "SELECT state FROM alerts WHERE id = ?",
        (alert_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    if row[0] == "acknowledged":
        raise HTTPException(status_code=400, detail="Alert already acknowledged")
    
    await db.execute(
        """UPDATE alerts SET state = 'acknowledged', 
           acknowledged_by = ?, acknowledged_at = datetime('now')
           WHERE id = ?""",
        (user["id"], alert_id)
    )
    
    # Audit log
    await db.execute(
        """INSERT INTO audit_log (user_id, action, details)
           VALUES (?, ?, ?)""",
        (user["id"], "alert.acknowledge", f"alert_id: {alert_id}")
    )
    
    await db.commit()
    
    # Broadcast
    await sse_manager.broadcast(Channels.ALERTS, "alert_acknowledged", {
        "alert_id": alert_id,
        "acknowledged_by": user["username"]
    })
    
    return {"message": f"Alert {alert_id} acknowledged"}


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str,
    user: dict = Depends(require_role("admin", "operator"))
):
    """Manually resolve an alert."""
    db = await get_control_db()
    
    cursor = await db.execute(
        "SELECT id, rule_id, severity, message, value, fired_at FROM alerts WHERE id = ?",
        (alert_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    # Update alert
    await db.execute(
        "UPDATE alerts SET state = 'resolved', resolved_at = datetime('now') WHERE id = ?",
        (alert_id,)
    )
    
    # Add to history
    fired_at = datetime.fromisoformat(row[5]) if row[5] else datetime.utcnow()
    duration = int((datetime.utcnow() - fired_at).total_seconds())
    
    await db.execute(
        """INSERT INTO alert_history 
           (alert_id, rule_id, severity, message, value, fired_at, resolved_at, duration_seconds)
           VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)""",
        (row[0], row[1], row[2], row[3], row[4], row[5], duration)
    )
    
    # Audit log
    await db.execute(
        """INSERT INTO audit_log (user_id, action, details)
           VALUES (?, ?, ?)""",
        (user["id"], "alert.resolve", f"alert_id: {alert_id}")
    )
    
    await db.commit()
    
    # Broadcast
    await sse_manager.broadcast(Channels.ALERTS, "alert_resolved", {"alert_id": alert_id})
    
    return {"message": f"Alert {alert_id} resolved"}


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
