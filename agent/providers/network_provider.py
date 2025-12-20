"""
Pi Agent - Network Provider (Stub)

Discovers and manages network interfaces (eth, wifi, bluetooth).
Full implementation in Sprint 6.
"""

from datetime import datetime
from typing import Dict, List, Optional

import structlog

from .base import BaseProvider, Resource, ResourceClass, ResourceState, ActionResult

logger = structlog.get_logger(__name__)


class NetworkProvider(BaseProvider):
    """Provider for network interfaces."""
    
    @property
    def name(self) -> str:
        return "network"
    
    async def start(self) -> None:
        """Initialize network provider."""
        self._is_healthy = True
        logger.info("Network provider initialized (stub)")
    
    async def stop(self) -> None:
        """Cleanup network provider."""
        pass
    
    async def discover(self) -> List[Resource]:
        """Discover network interfaces."""
        # Stub implementation - full implementation in Sprint 6
        resources = []
        
        # TODO: Implement network interface discovery
        # - Read from /sys/class/net/
        # - Get IP addresses via ip command
        # - Get WiFi info via iwconfig/iw
        # - Get Bluetooth status via bluetoothctl
        
        logger.debug("Network discovery (stub)", interfaces=len(resources))
        return resources
    
    async def get_resource(self, resource_id: str) -> Optional[Resource]:
        """Get a specific interface."""
        return self._resources.get(resource_id)
    
    async def execute_action(
        self,
        resource_id: str,
        action: str,
        params: Optional[Dict] = None
    ) -> ActionResult:
        """Execute an action on a network interface."""
        # Stub implementation
        return ActionResult(
            success=False,
            message="Network actions not yet implemented",
            error="NOT_IMPLEMENTED"
        )
