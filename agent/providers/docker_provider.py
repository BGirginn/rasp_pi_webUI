"""
Pi Agent - Docker Provider

Discovers and manages Docker containers, images, volumes, and networks.
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional

import structlog

try:
    import docker
    from docker.errors import DockerException, NotFound
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

from .base import BaseProvider, Resource, ResourceClass, ResourceState, ActionResult

logger = structlog.get_logger(__name__)


class DockerProvider(BaseProvider):
    """Provider for Docker containers and resources."""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self._client: Optional[docker.DockerClient] = None
    
    @property
    def name(self) -> str:
        return "docker"
    
    async def start(self) -> None:
        """Initialize Docker client."""
        if not DOCKER_AVAILABLE:
            logger.warning("Docker SDK not available")
            self._is_healthy = False
            return
        
        try:
            self._client = docker.from_env()
            self._client.ping()
            logger.info("Docker client connected")
            self._is_healthy = True
        except DockerException as e:
            logger.error("Failed to connect to Docker", error=str(e))
            self._is_healthy = False
    
    async def stop(self) -> None:
        """Close Docker client."""
        if self._client:
            self._client.close()
            self._client = None
    
    async def discover(self) -> List[Resource]:
        """Discover Docker containers."""
        if not self._client or not self._is_healthy:
            return []
        
        resources = []
        
        try:
            # Discover containers
            containers = await asyncio.to_thread(self._client.containers.list, all=True)
            
            for container in containers:
                resource = self._container_to_resource(container)
                resources.append(resource)
                self._resources[resource.id] = resource
            
            logger.debug("Docker discovery complete", containers=len(resources))
            
        except DockerException as e:
            logger.error("Docker discovery failed", error=str(e))
            self._is_healthy = False
        
        return resources
    
    def _container_to_resource(self, container) -> Resource:
        """Convert Docker container to Resource."""
        # Determine state
        status = container.status
        state_map = {
            "running": ResourceState.RUNNING,
            "exited": ResourceState.STOPPED,
            "paused": ResourceState.STOPPED,
            "restarting": ResourceState.RESTARTING,
            "created": ResourceState.STOPPED,
            "dead": ResourceState.FAILED,
        }
        state = state_map.get(status, ResourceState.UNKNOWN)
        
        # Get labels
        labels = container.labels or {}
        
        # Classify resource
        resource_class = self.classify_resource(container.name, labels)
        
        # Extract port mappings
        ports = []
        if container.attrs.get("NetworkSettings", {}).get("Ports"):
            for container_port, host_bindings in container.attrs["NetworkSettings"]["Ports"].items():
                if host_bindings:
                    for binding in host_bindings:
                        ports.append({
                            "container": container_port,
                            "host": binding.get("HostPort"),
                            "protocol": container_port.split("/")[-1] if "/" in container_port else "tcp"
                        })
        
        # Get image name
        image_tags = container.image.tags if container.image else []
        image = image_tags[0] if image_tags else container.attrs.get("Image", "unknown")
        
        return Resource(
            id=container.id[:12],
            name=container.name,
            type="container",
            provider=self.name,
            resource_class=resource_class,
            state=state,
            image=image,
            ports=ports,
            labels=labels,
            last_seen=datetime.utcnow(),
            metadata={
                "created": container.attrs.get("Created"),
                "started_at": container.attrs.get("State", {}).get("StartedAt"),
                "restart_count": container.attrs.get("RestartCount", 0),
            }
        )
    
    async def get_resource(self, resource_id: str) -> Optional[Resource]:
        """Get a specific container."""
        if not self._client:
            return None
        
        try:
            container = await asyncio.to_thread(self._client.containers.get, resource_id)
            return self._container_to_resource(container)
        except NotFound:
            return None
        except DockerException as e:
            logger.error("Failed to get container", id=resource_id, error=str(e))
            return None
    
    async def execute_action(
        self,
        resource_id: str,
        action: str,
        params: Optional[Dict] = None
    ) -> ActionResult:
        """Execute an action on a container."""
        if not self._client:
            return ActionResult(success=False, message="Docker not available", error="NOT_AVAILABLE")
        
        try:
            container = await asyncio.to_thread(self._client.containers.get, resource_id)
            
            if action == "start":
                await asyncio.to_thread(container.start)
                return ActionResult(success=True, message=f"Container {resource_id} started")
            
            elif action == "stop":
                timeout = params.get("timeout", 10) if params else 10
                await asyncio.to_thread(container.stop, timeout=timeout)
                return ActionResult(success=True, message=f"Container {resource_id} stopped")
            
            elif action == "restart":
                timeout = params.get("timeout", 10) if params else 10
                await asyncio.to_thread(container.restart, timeout=timeout)
                return ActionResult(success=True, message=f"Container {resource_id} restarted")
            
            elif action == "pause":
                await asyncio.to_thread(container.pause)
                return ActionResult(success=True, message=f"Container {resource_id} paused")
            
            elif action == "unpause":
                await asyncio.to_thread(container.unpause)
                return ActionResult(success=True, message=f"Container {resource_id} unpaused")
            
            else:
                return ActionResult(success=False, message=f"Unknown action: {action}", error="UNKNOWN_ACTION")
            
        except NotFound:
            return ActionResult(success=False, message=f"Container not found: {resource_id}", error="NOT_FOUND")
        except DockerException as e:
            return ActionResult(success=False, message=f"Action failed: {str(e)}", error="DOCKER_ERROR")
    
    async def get_logs(
        self,
        resource_id: str,
        tail: int = 100,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> List[str]:
        """Get container logs."""
        if not self._client:
            return []
        
        try:
            container = await asyncio.to_thread(self._client.containers.get, resource_id)
            
            kwargs = {"tail": tail, "timestamps": True}
            if since:
                kwargs["since"] = since
            if until:
                kwargs["until"] = until
            
            logs = await asyncio.to_thread(container.logs, **kwargs)
            
            # Decode and split lines
            if isinstance(logs, bytes):
                logs = logs.decode("utf-8", errors="replace")
            
            return logs.splitlines()
            
        except (NotFound, DockerException) as e:
            logger.error("Failed to get logs", id=resource_id, error=str(e))
            return []
    
    async def get_stats(self, resource_id: str) -> Optional[Dict]:
        """Get container stats."""
        if not self._client:
            return None
        
        try:
            container = await asyncio.to_thread(self._client.containers.get, resource_id)
            
            # Get single stats snapshot (stream=False)
            stats = await asyncio.to_thread(container.stats, stream=False)
            
            # Calculate CPU percentage
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                       stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                          stats["precpu_stats"]["system_cpu_usage"]
            cpu_count = stats["cpu_stats"]["online_cpus"]
            
            cpu_pct = (cpu_delta / system_delta) * cpu_count * 100 if system_delta > 0 else 0
            
            # Memory stats
            mem_usage = stats["memory_stats"].get("usage", 0)
            mem_limit = stats["memory_stats"].get("limit", 0)
            mem_pct = (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0
            
            # Network stats
            networks = stats.get("networks", {})
            net_rx = sum(n.get("rx_bytes", 0) for n in networks.values())
            net_tx = sum(n.get("tx_bytes", 0) for n in networks.values())
            
            return {
                "cpu_pct": round(cpu_pct, 2),
                "memory_usage_mb": round(mem_usage / (1024 * 1024), 2),
                "memory_limit_mb": round(mem_limit / (1024 * 1024), 2),
                "memory_pct": round(mem_pct, 2),
                "network_rx_bytes": net_rx,
                "network_tx_bytes": net_tx,
            }
            
        except (NotFound, DockerException, KeyError) as e:
            logger.error("Failed to get stats", id=resource_id, error=str(e))
            return None
