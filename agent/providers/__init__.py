"""
Pi Agent - Providers Package

Providers are responsible for discovering and managing different types of resources:
- DockerProvider: Docker containers, images, volumes, networks
- SystemdProvider: systemd services
- NetworkProvider: Network interfaces (eth, wifi, bluetooth)
- DevicesProvider: Hardware devices (USB, serial, GPIO)
- TelemetryProvider: System metrics collection
- LogsProvider: Log aggregation from various sources
- MQTTProvider: ESP device management via MQTT
"""

from .manager import ProviderManager
from .base import BaseProvider, ResourceClass, ResourceState

__all__ = [
    "ProviderManager",
    "BaseProvider",
    "ResourceClass",
    "ResourceState",
]
