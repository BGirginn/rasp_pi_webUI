"""
JWT Settings Helpers
Handles JWT secret and version storage in settings.
"""

import secrets
from typing import Tuple

from config import settings


async def get_jwt_secret(db) -> str:
    """Fetch JWT secret from settings table or fallback to configured secret."""
    secret = None
    cursor = await db.execute(
        "SELECT value FROM settings WHERE key = 'jwt_secret'"
    )
    row = await cursor.fetchone()
    if row and row[0]:
        secret = row[0]

    return secret or settings.get_jwt_secret()


async def get_jwt_secret_version(db) -> int:
    """Fetch JWT secret version from settings table (defaults to 1)."""
    cursor = await db.execute(
        "SELECT value FROM settings WHERE key = 'jwt_secret_version'"
    )
    row = await cursor.fetchone()
    if not row:
        return 1

    try:
        return int(row[0])
    except (TypeError, ValueError):
        return 1


async def get_jwt_secret_and_version(db) -> Tuple[str, int]:
    """Return current JWT secret and version."""
    secret = await get_jwt_secret(db)
    version = await get_jwt_secret_version(db)
    return secret, version


async def rotate_jwt_secret(db) -> int:
    """Rotate JWT secret and return the new version."""
    new_secret = secrets.token_urlsafe(64)
    current_version = await get_jwt_secret_version(db)
    new_version = current_version + 1

    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        ("jwt_secret", new_secret)
    )
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
        ("jwt_secret_version", str(new_version))
    )

    # Drop existing sessions to force re-authentication.
    await db.execute("DELETE FROM sessions")
    await db.commit()

    # Update in-memory secret for current process.
    settings.jwt_secret = new_secret

    return new_version
