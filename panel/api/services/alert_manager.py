
import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta

from db import get_control_db
from services.agent_client import agent_client
from services.sse import sse_manager, Channels

logger = logging.getLogger(__name__)

class AlertManager:
    def __init__(self):
        self.running = False
        self.task = None
        self.interval = 10  # Check every 10 seconds

    async def start(self):
        """Start the alert monitoring loop."""
        if self.running:
            return
        
        self.running = True
        self.task = asyncio.create_task(self._monitor_loop())
        logger.info("Alert Manager started")

    async def stop(self):
        """Stop the alert monitoring loop."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Alert Manager stopped")

    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                await self._check_alerts()
            except Exception as e:
                logger.error(f"Error in alert monitor loop: {e}")
            
            await asyncio.sleep(self.interval)

    async def _check_alerts(self):
        """Check all rules against current telemetry."""
        # 1. Get Telemetry
        try:
            telemetry = await agent_client.get_telemetry()
        except Exception:
            # If agent is down, we can't check metrics. 
            # Optionally we could raise a specific 'Agent Down' alert here.
            return

        # Flatten metric map for easier lookup (e.g. host.cpu.pct_total)
        # Assuming telemetry structure matches what Rules expect.
        metrics = self._flatten_telemetry(telemetry)

        # 2. Get Rules
        db = await get_control_db()
        cursor = await db.execute(
            "SELECT id, name, metric, condition, threshold, severity, cooldown_minutes FROM alert_rules WHERE enabled = 1"
        )
        rules = await cursor.fetchall()

        for rule in rules:
            rule_id, rule_name, metric, condition, threshold, severity, cooldown = rule
            
            # Skip if metric not present
            if metric not in metrics:
                continue
            
            current_value = metrics[metric]
            
            # Check condition
            is_triggered = self._evaluate_condition(current_value, condition, threshold)
            
            if is_triggered:
                await self._trigger_alert(db, rule_id, rule_name, severity, current_value, threshold, condition)
            else:
                await self._resolve_alert_if_active(db, rule_id)

    def _evaluate_condition(self, value, condition, threshold):
        try:
            val = float(value)
            thresh = float(threshold)
            
            if condition == 'gt': return val > thresh
            if condition == 'gte': return val >= thresh
            if condition == 'lt': return val < thresh
            if condition == 'lte': return val <= thresh
            if condition == 'eq': return val == thresh
            if condition == 'neq': return val != thresh
            return False
        except:
            return False

    async def _trigger_alert(self, db, rule_id, rule_name, severity, value, threshold, condition):
        # Check cooldown / existing active alert
        cursor = await db.execute(
            "SELECT id, state, fired_at FROM alerts WHERE rule_id = ? AND state IN ('pending', 'firing', 'acknowledged')",
            (rule_id,)
        )
        existing = await cursor.fetchone()
        
        if existing:
            # Alert already active, maybe update value?
            # Or if acknowledged, do we re-fire? Usually no, unless re-notification policy.
            # For now, just ignore if already active.
            return
            
        # Create new alert
        alert_id = str(uuid.uuid4())[:8]
        now = datetime.utcnow().isoformat()
        message = f"{rule_name}: Value {value} is {condition} {threshold}"
        
        await db.execute(
            """INSERT INTO alerts (id, rule_id, state, severity, message, value, fired_at)
               VALUES (?, ?, 'firing', ?, ?, ?, ?)""",
            (alert_id, rule_id, severity, message, value, now)
        )
        await db.commit()
        
        # Broadcast
        await sse_manager.broadcast(Channels.ALERTS, "alert_fired", {
            "id": alert_id,
            "rule_name": rule_name,
            "severity": severity,
            "message": message,
            "value": value,
            "fired_at": now
        })
        logger.warning(f"Alert Fired: {message}")

    async def _resolve_alert_if_active(self, db, rule_id):
        # Find active alerts for this rule
        cursor = await db.execute(
            "SELECT id FROM alerts WHERE rule_id = ? AND state IN ('pending', 'firing', 'acknowledged')",
            (rule_id,)
        )
        row = await cursor.fetchone()
        
        if row:
            alert_id = row[0]
            # Resolve it
            await db.execute(
                "UPDATE alerts SET state = 'resolved', resolved_at = datetime('now') WHERE id = ?",
                (alert_id,)
            )
            await db.commit()
            
            await sse_manager.broadcast(Channels.ALERTS, "alert_resolved", {"alert_id": alert_id})
            logger.info(f"Alert Resolved: {alert_id}")

    def _flatten_telemetry(self, data, prefix=''):
        """Flatten nested dictionary to dotted keys."""
        items = {}
        for k, v in data.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                items.update(self._flatten_telemetry(v, key))
            else:
                items[key] = v
        return items

alert_manager = AlertManager()
