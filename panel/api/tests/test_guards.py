"""
Test Guards (Confirmation + Cooldown)
Validates confirmation and cooldown enforcement.
"""

import pytest
from datetime import datetime, timedelta
from core.actions.loader import get_registry
from core.actions.guards import requires_confirmation, check_cooldown
from fastapi import HTTPException
import aiosqlite


def test_requires_confirmation_action_with_confirmation():
    """Actions with requires_confirmation:true should return True."""
    registry = get_registry()
    
    # svc.stop has requires_confirmation: true
    assert requires_confirmation(registry, "svc.stop") is True
    
    # power.reboot_safe has requires_confirmation: true
    assert requires_confirmation(registry, "power.reboot_safe") is True


def test_requires_confirmation_action_without_confirmation():
    """Actions without requires_confirmation should use default (false)."""
    registry = get_registry()
    
    # svc.restart has no requires_confirmation field, should use default (false)
    assert requires_confirmation(registry, "svc.restart") is False
    
    # obs.get_system_status has no requires_confirmation field
    assert requires_confirmation(registry, "obs.get_system_status") is False


def test_requires_confirmation_unknown_action():
    """Unknown actions should require confirmation (deny-by-default safety)."""
    registry = get_registry()
    
    assert requires_confirmation(registry, "unknown.action") is True


@pytest.mark.asyncio
async def test_cooldown_not_active():
    """Action executed long ago should not trigger cooldown."""
    # Create in-memory test DB
    db = await aiosqlite.connect(":memory:")
    
    # Create audit_log table
    await db.execute("""
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            action TEXT,
            resource_id TEXT,
            details TEXT,
            created_at TEXT
        )
    """)
    
    # Insert old audit entry (70 seconds ago, cooldown is 60 seconds)
    old_time = datetime.utcnow() - timedelta(seconds=70)
    await db.execute(
        """INSERT INTO audit_log (user_id, username, action, created_at)
           VALUES (?, ?, ?, ?)""",
        (1, "testuser", "svc.disable", old_time.isoformat())
    )
    await db.commit()
    
    # Should NOT raise exception (cooldown expired)
    await check_cooldown(db, 1, "svc.disable", 60)
    
    await db.close()


@pytest.mark.asyncio
async def test_cooldown_active():
    """Action executed recently should trigger 429 cooldown error."""
    # Create in-memory test DB
    db = await aiosqlite.connect(":memory:")
    
    # Create audit_log table
    await db.execute("""
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            action TEXT,
            resource_id TEXT,
            details TEXT,
            created_at TEXT
        )
    """)
    
    # Insert recent audit entry (10 seconds ago, cooldown is 60 seconds)
    recent_time = datetime.utcnow() - timedelta(seconds=10)
    await db.execute(
        """INSERT INTO audit_log (user_id, username, action, created_at)
           VALUES (?, ?, ?, ?)""",
        (1, "testuser", "svc.disable", recent_time.isoformat())
    )
    await db.commit()
    
    # Should raise 429 (within cooldown period)
    with pytest.raises(HTTPException) as exc_info:
        await check_cooldown(db, 1, "svc.disable", 60)
    
    assert exc_info.value.status_code == 429
    assert "COOLDOWN_ACTIVE" in str(exc_info.value.detail)
    
    await db.close()


@pytest.mark.asyncio
async def test_cooldown_no_previous_execution():
    """First execution should not trigger cooldown."""
    # Create in-memory test DB
    db = await aiosqlite.connect(":memory:")
    
    # Create audit_log table
    await db.execute("""
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            action TEXT,
            resource_id TEXT,
            details TEXT,
            created_at TEXT
        )
    """)
    await db.commit()
    
    # No previous execution - should NOT raise exception
    await check_cooldown(db, 1, "svc.disable", 60)
    
    await db.close()
