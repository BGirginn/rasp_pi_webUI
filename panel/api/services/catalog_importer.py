"""
Catalog Importer Service

Imports application catalogs from CasaOS and Runtipi app stores.
These are the primary sources for self-hosted applications.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

import aiohttp
import structlog
import yaml

logger = structlog.get_logger(__name__)


# Category mapping from source categories to our internal categories
CATEGORY_MAP = {
    # Runtipi categories
    "media": "media",
    "development": "development",
    "utilities": "utilities",
    "network": "network",
    "social": "social",
    "security": "security",
    "automation": "automation",
    "data": "database",
    "gaming": "gaming",
    "finance": "finance",
    "ai": "ai",
    "books": "media",
    "music": "media",
    "photos": "media",
    # CasaOS categories
    "backup": "storage",
    "cloud": "storage",
    "communication": "social",
    "developer": "development",
    "documents": "productivity",
    "download": "utilities",
    "entertainment": "media",
    "file sync": "storage",
    "home automation": "automation",
    "monitoring": "monitoring",
    "photo": "media",
    "productivity": "productivity",
    "vpn": "network",
    "web": "web",
}

# Our internal categories with display info
INTERNAL_CATEGORIES = {
    "media": {"name": "Media & Entertainment", "icon": "play-circle"},
    "network": {"name": "Network & Security", "icon": "shield"},
    "automation": {"name": "Home Automation", "icon": "home"},
    "storage": {"name": "Storage & Cloud", "icon": "hard-drive"},
    "monitoring": {"name": "Monitoring & Analytics", "icon": "activity"},
    "development": {"name": "Development Tools", "icon": "code"},
    "database": {"name": "Databases", "icon": "database"},
    "utilities": {"name": "Utilities", "icon": "wrench"},
    "social": {"name": "Social & Communication", "icon": "message-circle"},
    "security": {"name": "Security", "icon": "lock"},
    "gaming": {"name": "Gaming", "icon": "gamepad-2"},
    "finance": {"name": "Finance", "icon": "wallet"},
    "ai": {"name": "AI & Machine Learning", "icon": "brain"},
    "productivity": {"name": "Productivity", "icon": "briefcase"},
    "web": {"name": "Web Services", "icon": "globe"},
    "other": {"name": "Other", "icon": "box"},
}


class CatalogImporter:
    """Imports and manages application catalogs from external sources."""
    
    CASAOS_APPS_API = "https://api.github.com/repos/IceWhaleTech/CasaOS-AppStore/contents/Apps"
    CASAOS_RAW_BASE = "https://raw.githubusercontent.com/IceWhaleTech/CasaOS-AppStore/main/Apps"
    
    RUNTIPI_APPS_API = "https://api.github.com/repos/runtipi/runtipi-appstore/contents/apps"
    RUNTIPI_RAW_BASE = "https://raw.githubusercontent.com/runtipi/runtipi-appstore/master/apps"
    
    def __init__(self):
        self._catalog_path = Path(__file__).parent.parent / "data" / "app_catalog.json"
        self._last_refresh: Optional[datetime] = None
        
    async def _fetch_json(self, url: str, session: aiohttp.ClientSession) -> Optional[Any]:
        """Fetch JSON from URL."""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        except Exception as e:
            logger.error("Error fetching URL", url=url, error=str(e))
            return None
    
    async def _fetch_text(self, url: str, session: aiohttp.ClientSession) -> Optional[str]:
        """Fetch text content from URL."""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    return await resp.text()
                return None
        except Exception as e:
            logger.error("Error fetching URL", url=url, error=str(e))
            return None
    
    async def fetch_runtipi_apps(self) -> List[Dict]:
        """Fetch applications from Runtipi app store."""
        apps = []
        
        async with aiohttp.ClientSession() as session:
            app_list = await self._fetch_json(self.RUNTIPI_APPS_API, session)
            if not app_list:
                logger.error("Failed to fetch Runtipi app list")
                return apps
            
            app_dirs = [
                item["name"] for item in app_list 
                if item["type"] == "dir" and not item["name"].startswith("__") and not item["name"].endswith(".json")
            ]
            
            logger.info("Found Runtipi apps", count=len(app_dirs))
            
            batch_size = 20
            for i in range(0, len(app_dirs), batch_size):
                batch = app_dirs[i:i + batch_size]
                tasks = []
                
                for app_name in batch:
                    config_url = f"{self.RUNTIPI_RAW_BASE}/{app_name}/config.json"
                    tasks.append(self._fetch_json(config_url, session))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for app_name, result in zip(batch, results):
                    if isinstance(result, dict) and result.get("available", True):
                        app = self._convert_runtipi_app(result, app_name)
                        if app:
                            apps.append(app)
                
                if i + batch_size < len(app_dirs):
                    await asyncio.sleep(0.5)
        
        logger.info("Fetched Runtipi apps", count=len(apps))
        return apps
    
    def _convert_runtipi_app(self, config: Dict, app_name: str) -> Optional[Dict]:
        """Convert Runtipi app config to our format."""
        try:
            categories = config.get("categories", [])
            category = "other"
            for cat in categories:
                if cat.lower() in CATEGORY_MAP:
                    category = CATEGORY_MAP[cat.lower()]
                    break
            
            supported_archs = config.get("supported_architectures", [])
            if supported_archs and "arm64" not in supported_archs:
                return None
            
            port = config.get("port", 80)
            
            return {
                "id": config.get("id", app_name),
                "name": config.get("name", app_name.title()),
                "description": config.get("short_desc") or config.get("description", ""),
                "category": category,
                "image": "",
                "version": config.get("version", "latest"),
                "logo": f"https://raw.githubusercontent.com/runtipi/runtipi-appstore/master/apps/{app_name}/metadata/logo.jpg",
                "website": config.get("website", config.get("source", "")),
                "source": "runtipi",
                "tags": [c.lower() for c in categories],
                "ports": [{"container": port, "host": port, "protocol": "tcp"}] if port else [],
                "volumes": [{"host": f"/opt/pi-apps/{app_name}/data", "container": "/data"}],
                "environment": [],
                "restart_policy": "unless-stopped",
            }
        except Exception as e:
            logger.error("Failed to convert Runtipi app", app=app_name, error=str(e))
            return None
    
    async def fetch_casaos_apps(self) -> List[Dict]:
        """Fetch applications from CasaOS app store."""
        apps = []
        
        async with aiohttp.ClientSession() as session:
            app_list = await self._fetch_json(self.CASAOS_APPS_API, session)
            if not app_list:
                logger.error("Failed to fetch CasaOS app list")
                return apps
            
            app_dirs = [item["name"] for item in app_list if item["type"] == "dir"]
            logger.info("Found CasaOS apps", count=len(app_dirs))
            
            batch_size = 20
            for i in range(0, len(app_dirs), batch_size):
                batch = app_dirs[i:i + batch_size]
                tasks = []
                
                for app_name in batch:
                    compose_url = f"{self.CASAOS_RAW_BASE}/{app_name}/docker-compose.yml"
                    tasks.append(self._fetch_text(compose_url, session))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for app_name, result in zip(batch, results):
                    if isinstance(result, str):
                        app = self._convert_casaos_app(result, app_name)
                        if app:
                            apps.append(app)
                
                if i + batch_size < len(app_dirs):
                    await asyncio.sleep(0.5)
        
        logger.info("Fetched CasaOS apps", count=len(apps))
        return apps
    
    def _convert_casaos_app(self, compose_yaml: str, app_name: str) -> Optional[Dict]:
        """Convert CasaOS docker-compose to our format."""
        try:
            compose = yaml.safe_load(compose_yaml)
            if not compose:
                return None
            
            services = compose.get("services", {})
            if not services:
                return None
            
            main_service = list(services.values())[0]
            casaos_meta = compose.get("x-casaos", {})
            
            # Check architecture
            architectures = casaos_meta.get("architectures", [])
            if architectures:
                arch_names = [a.get("arch") if isinstance(a, dict) else a for a in architectures]
                if arch_names and not any(arch in ["arm64", "aarch64", "arm/v8"] for arch in arch_names):
                    return None
            
            # Get category
            category = CATEGORY_MAP.get(casaos_meta.get("category", "").lower(), "other")
            
            # Get image
            image = main_service.get("image", "")
            
            # Get ports
            ports = []
            for port_def in main_service.get("ports", []):
                if isinstance(port_def, dict):
                    ports.append({
                        "container": int(port_def.get("target", 80)),
                        "host": int(str(port_def.get("published", 80)).strip('"')),
                        "protocol": port_def.get("protocol", "tcp")
                    })
                elif isinstance(port_def, str) and ":" in port_def:
                    parts = port_def.split(":")
                    if len(parts) >= 2:
                        container_port = parts[-1].split("/")[0]
                        host_port = parts[-2] if parts[-2] else container_port
                        ports.append({"container": int(container_port), "host": int(host_port)})
            
            # Get volumes
            volumes = []
            for vol_def in main_service.get("volumes", []):
                if isinstance(vol_def, dict):
                    container_path = vol_def.get("target", "")
                    host_path = vol_def.get("source", "").replace("$AppID", app_name.lower()).replace("/DATA/AppData/", "/opt/pi-apps/")
                    if container_path:
                        volumes.append({"container": container_path, "host": host_path or f"/opt/pi-apps/{app_name.lower()}{container_path}"})
                elif isinstance(vol_def, str) and ":" in vol_def:
                    parts = vol_def.split(":")
                    if len(parts) >= 2:
                        host_path = parts[0].replace("$AppID", app_name.lower()).replace("/DATA/AppData/", "/opt/pi-apps/")
                        volumes.append({"container": parts[1], "host": host_path})
            
            # Get environment
            environment = []
            env_list = main_service.get("environment", [])
            if isinstance(env_list, dict):
                env_list = [f"{k}={v}" for k, v in env_list.items()]
            for env in env_list:
                if isinstance(env, str) and "=" in env:
                    key, value = env.split("=", 1)
                    environment.append({"key": key, "value": value})
            
            # Get title/description
            title = casaos_meta.get("title", {})
            if isinstance(title, dict):
                title = title.get("en_US", app_name)
            
            description = casaos_meta.get("description", {})
            if isinstance(description, dict):
                description = description.get("en_US", "")
            
            icon = casaos_meta.get("icon", f"https://raw.githubusercontent.com/IceWhaleTech/CasaOS-AppStore/main/Apps/{app_name}/icon.png")
            
            return {
                "id": f"casaos-{app_name.lower()}",
                "name": title or app_name,
                "description": description or f"{app_name} application",
                "category": category,
                "image": image,
                "version": image.split(":")[-1] if ":" in image else "latest",
                "logo": icon,
                "website": casaos_meta.get("project_url", ""),
                "source": "casaos",
                "tags": [category],
                "ports": ports,
                "volumes": volumes,
                "environment": environment,
                "restart_policy": main_service.get("restart", "unless-stopped"),
                "network_mode": main_service.get("network_mode", "bridge"),
            }
        except Exception as e:
            logger.error("Failed to convert CasaOS app", app=app_name, error=str(e))
            return None
    
    async def import_all(self, sources: Optional[List[str]] = None) -> Dict:
        """Import apps from all or specified sources."""
        if sources is None:
            sources = ["casaos", "runtipi"]
        
        all_apps = []
        imported_sources = []
        
        if "runtipi" in sources:
            runtipi_apps = await self.fetch_runtipi_apps()
            all_apps.extend(runtipi_apps)
            if runtipi_apps:
                imported_sources.append("runtipi")
        
        if "casaos" in sources:
            casaos_apps = await self.fetch_casaos_apps()
            all_apps.extend(casaos_apps)
            if casaos_apps:
                imported_sources.append("casaos")
        
        # Remove duplicates
        seen_names = {}
        unique_apps = []
        for app in all_apps:
            name_key = app["name"].lower().replace(" ", "").replace("-", "")
            if name_key not in seen_names:
                seen_names[name_key] = True
                unique_apps.append(app)
        
        unique_apps.sort(key=lambda x: x["name"].lower())
        
        used_categories = set(app["category"] for app in unique_apps)
        categories = [
            {"id": cat_id, **cat_info}
            for cat_id, cat_info in INTERNAL_CATEGORIES.items()
            if cat_id in used_categories
        ]
        
        catalog = {
            "version": "2.0.0",
            "last_updated": datetime.utcnow().isoformat(),
            "sources": imported_sources,
            "categories": categories,
            "apps": unique_apps,
        }
        
        logger.info("Imported apps", total=len(unique_apps), sources=imported_sources)
        return catalog
    
    async def refresh_catalog(self, sources: Optional[List[str]] = None) -> Dict:
        """Refresh and save the catalog."""
        catalog = await self.import_all(sources)
        
        try:
            self._catalog_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._catalog_path, "w") as f:
                json.dump(catalog, f, indent=2)
            
            self._last_refresh = datetime.utcnow()
            logger.info("Catalog saved", path=str(self._catalog_path), apps=len(catalog["apps"]))
        except Exception as e:
            logger.error("Failed to save catalog", error=str(e))
        
        return catalog


catalog_importer = CatalogImporter()
