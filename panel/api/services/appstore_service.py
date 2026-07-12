"""
App Store Service

Manages Docker application installation, configuration, and lifecycle.
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

import structlog

try:
    import docker
    from docker.errors import DockerException, NotFound, ImageNotFound, APIError
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

logger = structlog.get_logger(__name__)


class AppStatus(str, Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLING = "installing"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    UPDATING = "updating"


@dataclass
class InstalledApp:
    """Represents an installed application."""
    app_id: str
    container_id: str
    container_name: str
    image: str
    version: str
    status: AppStatus
    installed_at: str
    ports: List[Dict] = field(default_factory=list)
    volumes: List[Dict] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    web_url: Optional[str] = None


class AppStoreService:
    """Service for managing Docker applications."""
    
    def __init__(self):
        self._client: Optional[docker.DockerClient] = None
        self._catalog: Dict = {}
        self._catalog_path = Path(__file__).parent.parent / "data" / "app_catalog.json"
        self._installed_apps_path = Path("/var/lib/pi-control/installed_apps.json")
        self._installed_apps: Dict[str, InstalledApp] = {}
        self._installing: set = set()
        
    async def initialize(self) -> bool:
        """Initialize the service."""
        if not DOCKER_AVAILABLE:
            logger.warning("Docker SDK not available")
            return False
        
        try:
            self._client = docker.from_env()
            self._client.ping()
            logger.info("Docker client connected for App Store")
        except DockerException as e:
            logger.error("Failed to connect to Docker", error=str(e))
            return False
        
        # Load catalog
        await self._load_catalog()
        
        # Load installed apps
        await self._load_installed_apps()
        
        # Sync with running containers
        await self._sync_installed_apps()
        
        return True
    
    async def _load_catalog(self) -> None:
        """Load application catalog from JSON."""
        try:
            if self._catalog_path.exists():
                with open(self._catalog_path, 'r') as f:
                    self._catalog = json.load(f)
                logger.info("App catalog loaded", apps=len(self._catalog.get('apps', [])))
            else:
                logger.warning("App catalog not found", path=str(self._catalog_path))
                self._catalog = {"version": "1.0.0", "categories": [], "apps": []}
        except Exception as e:
            logger.error("Failed to load app catalog", error=str(e))
            self._catalog = {"version": "1.0.0", "categories": [], "apps": []}
    
    async def _load_installed_apps(self) -> None:
        """Load installed apps from persistent storage."""
        try:
            if self._installed_apps_path.exists():
                with open(self._installed_apps_path, 'r') as f:
                    data = json.load(f)
                    for app_id, app_data in data.items():
                        self._installed_apps[app_id] = InstalledApp(**app_data)
                logger.info("Installed apps loaded", count=len(self._installed_apps))
        except Exception as e:
            logger.error("Failed to load installed apps", error=str(e))
    
    async def _save_installed_apps(self) -> None:
        """Save installed apps to persistent storage."""
        try:
            self._installed_apps_path.parent.mkdir(parents=True, exist_ok=True)
            data = {app_id: asdict(app) for app_id, app in self._installed_apps.items()}
            with open(self._installed_apps_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("Failed to save installed apps", error=str(e))
    
    async def _sync_installed_apps(self) -> None:
        """Sync installed apps with actual running containers."""
        if not self._client:
            return
        
        try:
            containers = await asyncio.to_thread(self._client.containers.list, all=True)
            container_map = {c.name: c for c in containers}
            
            for app_id, app in list(self._installed_apps.items()):
                container = container_map.get(app.container_name)
                if container:
                    status = container.status
                    if status == "running":
                        app.status = AppStatus.RUNNING
                    elif status in ("exited", "stopped"):
                        app.status = AppStatus.STOPPED
                    else:
                        app.status = AppStatus.ERROR
                    app.container_id = container.id[:12]
                else:
                    # Container doesn't exist anymore
                    app.status = AppStatus.NOT_INSTALLED
            
            await self._save_installed_apps()
            
        except DockerException as e:
            logger.error("Failed to sync installed apps", error=str(e))
    
    def get_catalog(self) -> Dict:
        """Get the full application catalog."""
        return self._catalog
    
    def get_categories(self) -> List[Dict]:
        """Get all categories."""
        return self._catalog.get("categories", [])
    
    def get_apps(self, category: Optional[str] = None, search: Optional[str] = None) -> List[Dict]:
        """Get apps with optional filtering."""
        apps = self._catalog.get("apps", [])
        
        if category:
            apps = [a for a in apps if a.get("category") == category]
        
        if search:
            search_lower = search.lower()
            apps = [
                a for a in apps 
                if search_lower in a.get("name", "").lower() 
                or search_lower in a.get("description", "").lower()
                or any(search_lower in tag.lower() for tag in a.get("tags", []))
            ]
        
        # Add installation status to each app
        for app in apps:
            app_id = app.get("id")
            if app_id in self._installed_apps:
                installed = self._installed_apps[app_id]
                app["installed"] = True
                app["status"] = installed.status.value
                app["container_id"] = installed.container_id
                app["web_url"] = installed.web_url
            else:
                app["installed"] = False
                app["status"] = AppStatus.NOT_INSTALLED.value
        
        return apps
    
    def get_app(self, app_id: str) -> Optional[Dict]:
        """Get a specific app by ID."""
        for app in self._catalog.get("apps", []):
            if app.get("id") == app_id:
                # Add installation status
                if app_id in self._installed_apps:
                    installed = self._installed_apps[app_id]
                    app["installed"] = True
                    app["status"] = installed.status.value
                    app["container_id"] = installed.container_id
                    app["web_url"] = installed.web_url
                else:
                    app["installed"] = False
                    app["status"] = AppStatus.NOT_INSTALLED.value
                return app
        return None
    
    def get_installed_apps(self) -> List[Dict]:
        """Get all installed apps."""
        result = []
        for app_id, installed in self._installed_apps.items():
            app_info = self.get_app(app_id)
            if app_info:
                result.append({
                    **app_info,
                    "container_id": installed.container_id,
                    "container_name": installed.container_name,
                    "installed_at": installed.installed_at,
                    "status": installed.status.value,
                    "web_url": installed.web_url,
                })
        return result
    
    async def install_app(
        self, 
        app_id: str, 
        custom_config: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Install an application."""
        if not self._client:
            return {"success": False, "error": "Docker not available"}
        
        if app_id in self._installing:
            return {"success": False, "error": "Installation already in progress"}
        
        app = self.get_app(app_id)
        if not app:
            return {"success": False, "error": f"App not found: {app_id}"}
        
        if app_id in self._installed_apps and self._installed_apps[app_id].status != AppStatus.NOT_INSTALLED:
            return {"success": False, "error": "App already installed"}
        
        self._installing.add(app_id)
        
        try:
            logger.info("Installing app", app_id=app_id, image=app.get("image"))
            
            # Pull image
            image_name = app.get("image")
            try:
                await asyncio.to_thread(self._client.images.pull, image_name)
                logger.info("Image pulled", image=image_name)
            except ImageNotFound:
                return {"success": False, "error": f"Image not found: {image_name}"}
            except APIError as e:
                return {"success": False, "error": f"Failed to pull image: {str(e)}"}
            
            # Prepare container configuration
            container_name = f"picontrol-{app_id}"
            
            # Ports
            ports = {}
            port_bindings = {}
            for port_config in app.get("ports", []):
                container_port = f"{port_config['container']}/{port_config.get('protocol', 'tcp')}"
                host_port = custom_config.get("ports", {}).get(
                    str(port_config['container']), 
                    port_config['host']
                ) if custom_config else port_config['host']
                ports[container_port] = {}
                port_bindings[container_port] = [{"HostPort": str(host_port)}]
            
            # Volumes
            volumes = {}
            binds = []
            for vol_config in app.get("volumes", []):
                host_path = vol_config['host']
                container_path = vol_config['container']
                mode = "ro" if vol_config.get("readonly") else "rw"
                
                # Create host directory if it doesn't exist
                if not host_path.startswith("/var/run") and not host_path.startswith("/lib"):
                    os.makedirs(host_path, exist_ok=True)
                
                volumes[container_path] = {}
                binds.append(f"{host_path}:{container_path}:{mode}")
            
            # Environment variables
            environment = {}
            for env_config in app.get("environment", []):
                key = env_config['key']
                value = custom_config.get("environment", {}).get(
                    key, 
                    env_config.get('value', '')
                ) if custom_config else env_config.get('value', '')
                if value:  # Only add non-empty values
                    environment[key] = value
            
            # Create host config
            host_config_kwargs = {
                "port_bindings": port_bindings,
                "binds": binds,
                "restart_policy": {"Name": app.get("restart_policy", "unless-stopped")},
            }
            
            # Capabilities
            if app.get("capabilities"):
                host_config_kwargs["cap_add"] = app["capabilities"]
            
            # Privileged mode
            if app.get("privileged"):
                host_config_kwargs["privileged"] = True
            
            # Sysctls
            if app.get("sysctls"):
                host_config_kwargs["sysctls"] = app["sysctls"]
            
            # Network mode
            network_mode = app.get("network_mode")
            if network_mode:
                host_config_kwargs["network_mode"] = network_mode
            
            host_config = self._client.api.create_host_config(**host_config_kwargs)
            
            # Create container
            container = await asyncio.to_thread(
                self._client.api.create_container,
                image=image_name,
                name=container_name,
                ports=ports,
                environment=environment,
                volumes=list(volumes.keys()),
                host_config=host_config,
                detach=True,
            )
            
            container_id = container["Id"][:12]
            
            # Start container
            await asyncio.to_thread(self._client.api.start, container_id)
            
            # Determine web URL
            web_url = None
            for port_config in app.get("ports", []):
                if port_config.get("description", "").lower().find("web") >= 0 or port_config['container'] in [80, 443, 8080, 8443]:
                    host_port = custom_config.get("ports", {}).get(
                        str(port_config['container']), 
                        port_config['host']
                    ) if custom_config else port_config['host']
                    web_url = f"http://localhost:{host_port}"
                    break
            
            # Save installed app
            installed_app = InstalledApp(
                app_id=app_id,
                container_id=container_id,
                container_name=container_name,
                image=image_name,
                version=app.get("version", "latest"),
                status=AppStatus.RUNNING,
                installed_at=datetime.utcnow().isoformat(),
                ports=[{"host": p['host'], "container": p['container']} for p in app.get("ports", [])],
                volumes=[{"host": v['host'], "container": v['container']} for v in app.get("volumes", [])],
                environment=environment,
                web_url=web_url,
            )
            
            self._installed_apps[app_id] = installed_app
            await self._save_installed_apps()
            
            logger.info("App installed successfully", app_id=app_id, container_id=container_id)
            
            return {
                "success": True,
                "container_id": container_id,
                "container_name": container_name,
                "web_url": web_url,
                "message": f"{app.get('name')} installed successfully"
            }
            
        except Exception as e:
            logger.error("Failed to install app", app_id=app_id, error=str(e))
            return {"success": False, "error": str(e)}
        finally:
            self._installing.discard(app_id)
    
    async def uninstall_app(self, app_id: str, remove_data: bool = False) -> Dict[str, Any]:
        """Uninstall an application."""
        if not self._client:
            return {"success": False, "error": "Docker not available"}
        
        if app_id not in self._installed_apps:
            return {"success": False, "error": "App not installed"}
        
        installed = self._installed_apps[app_id]
        
        try:
            # Get container
            try:
                container = await asyncio.to_thread(
                    self._client.containers.get, 
                    installed.container_name
                )
                
                # Stop container if running
                if container.status == "running":
                    await asyncio.to_thread(container.stop, timeout=10)
                
                # Remove container
                await asyncio.to_thread(container.remove, v=remove_data)
                
            except NotFound:
                logger.warning("Container not found during uninstall", app_id=app_id)
            
            # Remove from installed apps
            del self._installed_apps[app_id]
            await self._save_installed_apps()
            
            logger.info("App uninstalled", app_id=app_id)
            
            return {"success": True, "message": f"App {app_id} uninstalled successfully"}
            
        except Exception as e:
            logger.error("Failed to uninstall app", app_id=app_id, error=str(e))
            return {"success": False, "error": str(e)}
    
    async def start_app(self, app_id: str) -> Dict[str, Any]:
        """Start an installed application."""
        if not self._client:
            return {"success": False, "error": "Docker not available"}
        
        if app_id not in self._installed_apps:
            return {"success": False, "error": "App not installed"}
        
        installed = self._installed_apps[app_id]
        
        try:
            container = await asyncio.to_thread(
                self._client.containers.get, 
                installed.container_name
            )
            await asyncio.to_thread(container.start)
            
            installed.status = AppStatus.RUNNING
            await self._save_installed_apps()
            
            return {"success": True, "message": f"App {app_id} started"}
            
        except NotFound:
            return {"success": False, "error": "Container not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def stop_app(self, app_id: str) -> Dict[str, Any]:
        """Stop an installed application."""
        if not self._client:
            return {"success": False, "error": "Docker not available"}
        
        if app_id not in self._installed_apps:
            return {"success": False, "error": "App not installed"}
        
        installed = self._installed_apps[app_id]
        
        try:
            container = await asyncio.to_thread(
                self._client.containers.get, 
                installed.container_name
            )
            await asyncio.to_thread(container.stop, timeout=10)
            
            installed.status = AppStatus.STOPPED
            await self._save_installed_apps()
            
            return {"success": True, "message": f"App {app_id} stopped"}
            
        except NotFound:
            return {"success": False, "error": "Container not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def restart_app(self, app_id: str) -> Dict[str, Any]:
        """Restart an installed application."""
        if not self._client:
            return {"success": False, "error": "Docker not available"}
        
        if app_id not in self._installed_apps:
            return {"success": False, "error": "App not installed"}
        
        installed = self._installed_apps[app_id]
        
        try:
            container = await asyncio.to_thread(
                self._client.containers.get, 
                installed.container_name
            )
            await asyncio.to_thread(container.restart, timeout=10)
            
            installed.status = AppStatus.RUNNING
            await self._save_installed_apps()
            
            return {"success": True, "message": f"App {app_id} restarted"}
            
        except NotFound:
            return {"success": False, "error": "Container not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_app_logs(self, app_id: str, tail: int = 100) -> Dict[str, Any]:
        """Get logs for an installed application."""
        if not self._client:
            return {"success": False, "error": "Docker not available"}
        
        if app_id not in self._installed_apps:
            return {"success": False, "error": "App not installed"}
        
        installed = self._installed_apps[app_id]
        
        try:
            container = await asyncio.to_thread(
                self._client.containers.get, 
                installed.container_name
            )
            logs = await asyncio.to_thread(
                container.logs, 
                tail=tail, 
                timestamps=True
            )
            
            if isinstance(logs, bytes):
                logs = logs.decode("utf-8", errors="replace")
            
            return {"success": True, "logs": logs.splitlines()}
            
        except NotFound:
            return {"success": False, "error": "Container not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_app_stats(self, app_id: str) -> Dict[str, Any]:
        """Get resource stats for an installed application."""
        if not self._client:
            return {"success": False, "error": "Docker not available"}
        
        if app_id not in self._installed_apps:
            return {"success": False, "error": "App not installed"}
        
        installed = self._installed_apps[app_id]
        
        try:
            container = await asyncio.to_thread(
                self._client.containers.get, 
                installed.container_name
            )
            
            if container.status != "running":
                return {"success": True, "stats": None, "message": "Container not running"}
            
            stats = await asyncio.to_thread(container.stats, stream=False)
            
            # Calculate CPU percentage
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                       stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                          stats["precpu_stats"]["system_cpu_usage"]
            cpu_count = stats["cpu_stats"].get("online_cpus", 1)
            
            cpu_pct = (cpu_delta / system_delta) * cpu_count * 100 if system_delta > 0 else 0
            
            # Memory stats
            mem_usage = stats["memory_stats"].get("usage", 0)
            mem_limit = stats["memory_stats"].get("limit", 0)
            mem_pct = (mem_usage / mem_limit) * 100 if mem_limit > 0 else 0
            
            return {
                "success": True,
                "stats": {
                    "cpu_pct": round(cpu_pct, 2),
                    "memory_usage_mb": round(mem_usage / (1024 * 1024), 2),
                    "memory_limit_mb": round(mem_limit / (1024 * 1024), 2),
                    "memory_pct": round(mem_pct, 2),
                }
            }
            
        except NotFound:
            return {"success": False, "error": "Container not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Singleton instance
appstore_service = AppStoreService()
