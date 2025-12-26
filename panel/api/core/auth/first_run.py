"""
First-Run Helpers
Tracks whether initial owner setup is complete.
"""

from typing import Optional


async def is_first_run(db) -> bool:
    """Return True if first-run setup has not been completed."""
    cursor = await db.execute(
        "SELECT value FROM settings WHERE key = 'first_run_complete'"
    )
    row = await cursor.fetchone()
    if not row:
        return True
    return str(row[0]).lower() != "true"


async def mark_first_run_complete(db) -> None:
    """Mark first-run setup as complete."""
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        ("first_run_complete", "true")
    )
    await db.commit()
