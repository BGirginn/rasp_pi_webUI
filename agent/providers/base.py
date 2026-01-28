"""
Pi Agent - Base Provider Interface

All providers must implement this interface for consistent resource discovery
and management across different resource types.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ResourceClass(str, Enum):
    """Resource classification for access control."""
    CORE = "CORE"       # Read-only, cannot be stopped (docker, tailscale, etc.)
    SYSTEM = "SYSTEM"   # Can restart, cannot stop (ssh, nginx, etc.)
    APP = "APP"         # Full control (user containers, apps)
    DEVICE = "DEVICE"   # Hardware devices (ESP, USB, GPIO)


class ResourceState(str, Enum):
    """Resource operational state."""
    RUNNING = "running"
    STOPPED = "stopped"
    STARTING = "starting"
    STOPPING = "stopping"
    RESTARTING = "restarting"
    FAILED = "failed"
    UNKNOWN = "unknown"
    ONLINE = "online"      # For devices
    OFFLINE = "offline"    # For devices


@dataclass
class Resource:
    """Discovered resource representation."""
    id: str
    name: str
    type: str                   # container, service, interface, device
    provider: str               # docker, systemd, network, devices, mqtt
    resource_class: ResourceClass
    state: ResourceState
    
    # Optional metadata
    image: Optional[str] = None           # Docker image
    ports: Optional[List[Dict]] = None    # Exposed ports
    labels: Optional[Dict] = None         # Docker/systemd labels
    capabilities: Optional[List[str]] = None  # Device capabilities
    
    # Telemetry references
    health_score: int = 0
    last_seen: Optional[datetime] = None
    
    # Manifest reference
    manifest_id: Optional[str] = None
    managed: bool = False
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "provider": self.provider,
            "class": self.resource_class.value,
            "state": self.state.value,
            "image": self.image,
            "ports": self.ports,
            "labels": self.labels,
            "capabilities": self.capabilities,
            "health_score": self.health_score,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "manifest_id": self.manifest_id,
            "managed": self.managed,
            "metadata": self.metadata,
        }


@dataclass
class ActionResult:
    """Result of a resource action."""
    success: bool
    message: str
    data: Optional[Dict] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "error": self.error
        }


class BaseProvider(ABC):
    """Base class for all resource providers."""
    
    def __init__(self, config: dict):
        self.config = config
        self._resources: Dict[str, Resource] = {}
        self._is_healthy = True
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'docker', 'systemd')."""
        pass
    
    @property
    def is_healthy(self) -> bool:
        """Check if provider is healthy."""
        return self._is_healthy
    
    @abstractmethod
    async def start(self) -> None:
        """Initialize the provider."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Cleanup provider resources."""
        pass
    
    @abstractmethod
    async def discover(self) -> List[Resource]:
        """Discover resources managed by this provider."""
        pass
    
    @abstractmethod
    async def get_resource(self, resource_id: str) -> Optional[Resource]:
        """Get a specific resource by ID."""
        pass
    
    @abstractmethod
    async def execute_action(
        self,
        resource_id: str,
        action: str,
        params: Optional[Dict] = None
    ) -> ActionResult:
        """Execute an action on a resource."""
        pass
    
    async def get_logs(
        self,
        resource_id: str,
        tail: int = 100,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> List[str]:
        """Get logs for a resource. Override in subclass if supported."""
        return []
    
    async def get_stats(self, resource_id: str) -> Optional[Dict]:
        """Get stats for a resource. Override in subclass if supported."""
        return None
    
    def classify_resource(self, name: str, labels: Optional[Dict] = None) -> ResourceClass:
        """Classify a resource based on name and labels."""
        # Check CORE list
        core_list = self.config.get("classification", {}).get("core", [])
        if name in core_list:
            return ResourceClass.CORE
        
        # Check SYSTEM list
        system_list = self.config.get("classification", {}).get("system", [])
        if name in system_list:
            return ResourceClass.SYSTEM
        
        # Check labels for explicit classification
        if labels:
            class_label = labels.get("pi-control.class")
            if class_label:
                try:
                    return ResourceClass(class_label.upper())
                except ValueError:
                    pass
        
        # Default to APP for containers, SYSTEM for services
        return ResourceClass.APP
    
    def get_allowed_actions(self, resource_class: ResourceClass) -> List[str]:
        """Get allowed actions for a resource class."""
        if resource_class == ResourceClass.CORE:
            return ["logs", "stats"]  # Read-only
        elif resource_class == ResourceClass.SYSTEM:
            return ["logs", "stats", "restart", "enable", "disable"]
        elif resource_class == ResourceClass.APP:
            return ["logs", "stats", "start", "stop", "restart", "update", "backup", "restore"]
        elif resource_class == ResourceClass.DEVICE:
            return ["command", "mute", "update_firmware"]
        return []
