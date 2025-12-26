"""
Pi Control Panel - Authentication Router

Handles login, logout, token refresh, and user management.
"""

from datetime import datetime, timedelta
from typing import List, Optional
import uuid

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel
import pyotp

from config import settings
from core.auth.jwt import get_jwt_secret_and_version
from db import get_control_db

router = APIRouter()
security = HTTPBearer()


# Pydantic models
class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class RefreshResponse(BaseModel):
    access_token: str
    expires_in: int


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    has_totp: bool
    created_at: str


# Utility functions
def create_access_token(
    data: dict,
    secret: str,
    version: int,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes))
    to_encode.update({"exp": expire, "type": "access", "ver": version})
    return jwt.encode(to_encode, secret, algorithm=settings.jwt_algorithm)


def create_refresh_token() -> str:
    """Create refresh token."""
    return str(uuid.uuid4())


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    try:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    except Exception:
        return False


async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash (async - runs in thread pool)."""
    import asyncio
    try:
        return await asyncio.to_thread(bcrypt.checkpw, plain_password.encode(), hashed_password.encode())
    except Exception:
        return False


def hash_password(password: str) -> str:
    """Hash password."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


async def hash_password_async(password: str) -> str:
    """Hash password (async - runs in thread pool)."""
    import asyncio
    return await asyncio.to_thread(lambda: bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode())


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Get current user from JWT token."""
    token = credentials.credentials
    
    try:
        db = await get_control_db()
        secret, version = await get_jwt_secret_and_version(db)
        payload = jwt.decode(token, secret, algorithms=[settings.jwt_algorithm])
        
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")

        if payload.get("ver") != version:
            raise HTTPException(status_code=401, detail="Token expired")
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Get user from database
        cursor = await db.execute(
            "SELECT id, username, role, totp_secret FROM users WHERE id = ?",
            (int(user_id),)
        )
        row = await cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=401, detail="User not found")
        
        return {
            "id": row[0],
            "username": row[1],
            "role": row[2],
            "has_totp": bool(row[3])
        }
        
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_role(*roles: str):
    """Dependency to require specific roles."""
    async def role_checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] == "owner":
            return user
        if user["role"] not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user['role']}' not authorized. Required: {roles}"
            )
        return user
    return role_checker


# Routes
@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, response: Response, req: Request):
    """Authenticate user and return tokens."""
    db = await get_control_db()
    
    # Find user
    cursor = await db.execute(
        "SELECT id, username, password_hash, role, totp_secret FROM users WHERE username = ?",
        (request.username,)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user_id, username, password_hash, role, totp_secret = row
    
    # Verify password (using async version to avoid blocking)
    if not await verify_password_async(request.password, password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Verify TOTP if enabled
    if totp_secret:
        if not request.totp_code:
            raise HTTPException(status_code=401, detail="TOTP code required")
        
        totp = pyotp.TOTP(totp_secret)
        if not totp.verify(request.totp_code):
            raise HTTPException(status_code=401, detail="Invalid TOTP code")
    
    # Create tokens
    secret, version = await get_jwt_secret_and_version(db)
    access_token = create_access_token({"sub": str(user_id), "role": role}, secret, version)
    refresh_token = create_refresh_token()
    
    # Store session
    session_id = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
    
    await db.execute(
        """INSERT INTO sessions (id, user_id, refresh_token_hash, device_info, expires_at)
           VALUES (?, ?, ?, ?, ?)""",
        (session_id, user_id, hash_password(refresh_token), req.headers.get("User-Agent", ""), expires_at)
    )
    await db.commit()
    
    # Set refresh token as HttpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=settings.jwt_refresh_token_expire_days * 24 * 60 * 60
    )
    
    # Audit log
    await db.execute(
        "INSERT INTO audit_log (user_id, action, details, ip_address) VALUES (?, ?, ?, ?)",
        (user_id, "login", None, req.client.host if req.client else None)
    )
    await db.commit()
    
    return LoginResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user={"id": user_id, "username": username, "role": role, "has_totp": bool(totp_secret)}
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(request: Request):
    """Refresh access token using refresh token cookie."""
    refresh_token = request.cookies.get("refresh_token")
    
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token required")
    
    db = await get_control_db()
    
    # Find valid session
    cursor = await db.execute(
        """SELECT s.id, s.user_id, s.refresh_token_hash, u.role
           FROM sessions s
           JOIN users u ON s.user_id = u.id
           WHERE s.expires_at > datetime('now')"""
    )
    
    valid_session = None
    async for row in cursor:
        if verify_password(refresh_token, row[2]):
            valid_session = {"id": row[0], "user_id": row[1], "role": row[3]}
            break
    
    if not valid_session:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    
    # Create new access token
    secret, version = await get_jwt_secret_and_version(db)
    access_token = create_access_token({
        "sub": str(valid_session["user_id"]),
        "role": valid_session["role"]
    }, secret, version)
    
    return RefreshResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60
    )


@router.post("/logout")
async def logout(response: Response, user: dict = Depends(get_current_user)):
    """Logout and invalidate refresh token."""
    db = await get_control_db()
    
    # Delete user's sessions
    await db.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
    await db.commit()
    
    # Clear cookie
    response.delete_cookie("refresh_token")
    
    # Audit log
    await db.execute(
        "INSERT INTO audit_log (user_id, action) VALUES (?, ?)",
        (user["id"], "logout")
    )
    await db.commit()
    
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    """Get current user info."""
    db = await get_control_db()
    cursor = await db.execute(
        "SELECT id, username, role, totp_secret, created_at FROM users WHERE id = ?",
        (user["id"],)
    )
    row = await cursor.fetchone()
    
    return UserResponse(
        id=row[0],
        username=row[1],
        role=row[2],
        has_totp=bool(row[3]),
        created_at=row[4]
    )


@router.get("/users", response_model=List[UserResponse])
async def list_users(current_user: dict = Depends(require_role("owner"))):
    """List all users (owner only)."""
    db = await get_control_db()
    cursor = await db.execute("SELECT id, username, role, totp_secret, created_at FROM users")
    users = []
    async for row in cursor:
        users.append(UserResponse(
            id=row[0],
            username=row[1],
            role=row[2],
            has_totp=bool(row[3]),
            created_at=row[4]
        ))
    return users


@router.post("/password/change")
async def change_password(request: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    """Change current user's password."""
    db = await get_control_db()
    
    # Verify current password
    cursor = await db.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],))
    row = await cursor.fetchone()
    if not row or not verify_password(request.current_password, row[0]):
        raise HTTPException(status_code=400, detail="Incorrect current password")
    
    # Update password
    new_hash = hash_password(request.new_password)
    await db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (new_hash, user["id"])
    )
    
    # Audit log
    await db.execute(
        "INSERT INTO audit_log (user_id, action) VALUES (?, ?)",
        (user["id"], "change_password")
    )
    await db.commit()
    return {"message": "Password updated successfully"}
