from fastapi import APIRouter, Depends
from typing import List
from services.discovery import discovery_service
from .auth import get_current_user

router = APIRouter()

@router.get("/devices")
async def get_devices(user: dict = Depends(get_current_user)):
    """Get list of discovered IoT devices."""
    return discovery_service.get_devices()
