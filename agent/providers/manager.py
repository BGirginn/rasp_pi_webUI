"""
Pi Agent - Provider Manager

Manages all resource providers and coordinates discovery, actions, and state.
"""

import asyncio
import hashlib
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from .base import BaseProvider, Resource, ActionResult, ResourceClass

logger = structlog.get_logger(__name__)


class ProviderManager:
    """Manages all resource providers."""
    
    def __init__(self, config: dict):
        self.config = config
        self._providers: Dict[str, BaseProvider] = {}
        self._resources: Dict[str, Resource] = {}
        self._last_snapshot_hash: Optional[str] = None
        self._lock = asyncio.Lock()
    
    @property
    def is_healthy(self) -> bool:
        """Check if all providers are healthy."""
        if not self._providers:
            return False
        return all(p.is_healthy for p in self._providers.values())
    
    async def start(self) -> None:
        """Initialize and start all configured providers."""
        enabled_providers = self.config.get("discovery", {}).get("providers", [])
        logger.info("Starting providers", providers=enabled_providers)
        
        for provider_name in enabled_providers:
            try:
                provider = self._create_provider(provider_name)
                if provider:
                    await provider.start()
                    self._providers[provider_name] = provider
                    logger.info("Provider started", provider=provider_name)
            except Exception as e:
                logger.exception("Failed to start provider", provider=provider_name, error=str(e))
        
        # Initial discovery
        await self.discover()
    
    async def stop(self) -> None:
        """Stop all providers."""
        logger.info("Stopping providers")
        
        for name, provider in self._providers.items():
            try:
                await provider.stop()
                logger.info("Provider stopped", provider=name)
            except Exception as e:
                logger.exception("Error stopping provider", provider=name, error=str(e))
        
        self._providers.clear()
    
    def _create_provider(self, name: str) -> Optional[BaseProvider]:
        """Create a provider instance by name."""
        # Import providers dynamically to avoid circular imports
        if name == "docker":
            from .docker_provider import DockerProvider
            return DockerProvider(self.config)
        elif name == "systemd":
            from .systemd_provider import SystemdProvider
            return SystemdProvider(self.config)
        elif name == "network":
            from .network_provider import NetworkProvider
            return NetworkProvider(self.config)
        elif name == "devices":
            from .devices_provider import DevicesProvider
            return DevicesProvider(self.config)
        else:
            logger.warning("Unknown provider", provider=name)
            return None
    
    async def discover(self) -> List[Resource]:
        """Run discovery on all providers."""
        async with self._lock:
            all_resources = []
            
            for name, provider in self._providers.items():
                try:
                    resources = await provider.discover()
                    all_resources.extend(resources)
                    logger.debug("Provider discovery complete", provider=name, count=len(resources))
                except Exception as e:
                    logger.exception("Discovery failed", provider=name, error=str(e))
            
            # Update resource cache
            self._resources = {r.id: r for r in all_resources}
            
            return all_resources
    
    async def refresh(self) -> Dict[str, Any]:
        """Force refresh discovery and return snapshot."""
        await self.discover()
        return await self.get_snapshot()
    
    async def get_snapshot(self) -> Dict[str, Any]:
        """Get current resource snapshot with change detection."""
        resources = [r.to_dict() for r in self._resources.values()]
        
        # Calculate hash for change detection
        content = json.dumps(resources, sort_keys=True)
        current_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        
        changed = current_hash != self._last_snapshot_hash
        self._last_snapshot_hash = current_hash
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "hash": current_hash,
            "changed": changed,
            "resources": resources,
            "counts": {
                "total": len(resources),
                "by_class": self._count_by_class(),
                "by_provider": self._count_by_provider(),
                "by_state": self._count_by_state(),
            }
        }
    
    def _count_by_class(self) -> Dict[str, int]:
        """Count resources by class."""
        counts = {}
        for r in self._resources.values():
            key = r.resource_class.value
            counts[key] = counts.get(key, 0) + 1
        return counts
    
    def _count_by_provider(self) -> Dict[str, int]:
        """Count resources by provider."""
        counts = {}
        for r in self._resources.values():
            counts[r.provider] = counts.get(r.provider, 0) + 1
        return counts
    
    def _count_by_state(self) -> Dict[str, int]:
        """Count resources by state."""
        counts = {}
        for r in self._resources.values():
            key = r.state.value
            counts[key] = counts.get(key, 0) + 1
        return counts
    
    async def execute_action(
        self,
        resource_id: str,
        action: str,
        params: Optional[Dict] = None
    ) -> ActionResult:
        """Execute an action on a resource."""
        resource = self._resources.get(resource_id)
        if not resource:
            return ActionResult(
                success=False,
                message=f"Resource not found: {resource_id}",
                error="NOT_FOUND"
            )
        
        # Check if action is allowed for this resource class
        provider = self._providers.get(resource.provider)
        if not provider:
            return ActionResult(
                success=False,
                message=f"Provider not available: {resource.provider}",
                error="PROVIDER_UNAVAILABLE"
            )
        
        allowed_actions = provider.get_allowed_actions(resource.resource_class)
        if action not in allowed_actions:
            return ActionResult(
                success=False,
                message=f"Action '{action}' not allowed for {resource.resource_class.value} resources",
                error="ACTION_NOT_ALLOWED"
            )
        
        # Execute action
        logger.info("Executing action", resource_id=resource_id, action=action)
        return await provider.execute_action(resource_id, action, params)
    
    async def get_logs(
        self,
        resource_id: str,
        tail: int = 100,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> List[str]:
        """Get logs for a resource."""
        resource = self._resources.get(resource_id)
        if not resource:
            return []
        
        provider = self._providers.get(resource.provider)
        if not provider:
            return []
        
        return await provider.get_logs(resource_id, tail, since, until)
    
    async def get_stats(self, resource_id: str) -> Optional[Dict]:
        """Get stats for a resource."""
        resource = self._resources.get(resource_id)
        if not resource:
            return None
        
        provider = self._providers.get(resource.provider)
        if not provider:
            return None
        
        return await provider.get_stats(resource_id)
    
    async def get_network_interfaces(self) -> List[Dict]:
        """Get network interfaces from network provider."""
        provider = self._providers.get("network")
        if not provider:
            return []
        
        resources = await provider.discover()
        return [r.to_dict() for r in resources]
    
    async def toggle_wifi(self, enable: bool) -> ActionResult:
        """Toggle WiFi interface."""
        provider = self._providers.get("network")
        if not provider:
            return ActionResult(success=False, message="Network provider not available")
        
        action = "enable" if enable else "disable"
        return await provider.execute_action("wlan0", action)
    
    async def scan_wifi(self) -> List[Dict]:
        """Scan for WiFi networks."""
        provider = self._providers.get("network")
        if not provider:
            return []
        
        result = await provider.execute_action("wlan0", "scan")
        return result.data.get("networks", []) if result.success else []
    
    async def get_devices(self) -> List[Dict]:
        """Get hardware devices."""
        provider = self._providers.get("devices")
        if not provider:
            return []
        
        resources = await provider.discover()
        return [r.to_dict() for r in resources]
