"""
Pi Agent - Devices Provider

Discovers and manages hardware devices:
- USB devices (mass storage, serial ports)
- ESP devices (via network/mDNS)
- Serial ports (ttyUSB, ttyACM)

Cross-platform support: Linux (Raspberry Pi) and macOS (development).
"""

import asyncio
import json
import os
import platform
import subprocess
from time import monotonic
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import structlog

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from .base import BaseProvider, Resource, ResourceClass, ResourceState, ActionResult

logger = structlog.get_logger(__name__)

ESP_HTTP_COMMAND_ENDPOINTS = [
    "/api/led/command",
    "/led/command",
    "/command",
]

ESP_HTTP_STATUS_ENDPOINTS = [
    "/status",
]

ESP_HTTP_INFO_ENDPOINTS = [
    "/info",
]

_DISCOVERY_CACHE_TTL_SECONDS = 3.0
_ESP_DISCOVERY_CONCURRENCY = 8


class DevicesProvider(BaseProvider):
    """Provider for hardware devices."""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self._esp_devices: Dict[str, dict] = {}
        self._usb_devices: Dict[str, dict] = {}
        self._http_client: Optional[httpx.AsyncClient] = None
        self._discover_cache: Optional[List[Resource]] = None
        self._discover_cache_expires_at: float = 0.0
        self._discover_cache_ttl: float = float(
            config.get("discovery", {}).get("devices_cache_ttl", _DISCOVERY_CACHE_TTL_SECONDS)
        )
        self._discover_cache_lock = asyncio.Lock()
    
    @property
    def name(self) -> str:
        return "devices"
    
    async def start(self) -> None:
        """Initialize devices provider."""
        if HTTPX_AVAILABLE:
            self._http_client = httpx.AsyncClient(timeout=5.0)
        self._is_healthy = True
        logger.info("Devices provider initialized", platform=platform.system())
    
    async def stop(self) -> None:
        """Cleanup devices provider."""
        if self._http_client:
            await self._http_client.aclose()
    
    async def discover(self) -> List[Resource]:
        """Discover all hardware devices."""
        now = monotonic()
        if self._discover_cache is not None and now < self._discover_cache_expires_at:
            return list(self._discover_cache)

        async with self._discover_cache_lock:
            now = monotonic()
            if self._discover_cache is not None and now < self._discover_cache_expires_at:
                return list(self._discover_cache)

            resources = await self._discover_all_resources()
            self._resources = {r.id: r for r in resources}
            self._discover_cache = list(resources)
            self._discover_cache_expires_at = monotonic() + self._discover_cache_ttl
            return list(resources)

    async def _discover_all_resources(self) -> List[Resource]:
        """Run the expensive discovery pass once and assemble the result."""
        resources = []

        # Discover USB devices
        usb_resources = await self._discover_usb_devices()
        resources.extend(usb_resources)
        
        # Discover serial ports
        serial_resources = await self._discover_serial_ports()
        resources.extend(serial_resources)
        
        # Discover ESP devices via network
        esp_resources = await self._discover_esp_devices()
        resources.extend(esp_resources)
        
        # Cache all resources
        logger.info("Device discovery complete", 
                   usb=len(usb_resources),
                   serial=len(serial_resources),
                   esp=len(esp_resources))
        return resources

    def _invalidate_discovery_cache(self) -> None:
        """Force the next discover() call to refresh from the host/network."""
        self._discover_cache_expires_at = 0.0
    
    # =========================================
    # USB Device Discovery
    # =========================================
    
    async def _discover_usb_devices(self) -> List[Resource]:
        """Discover USB devices based on platform."""
        system = platform.system()
        
        if system == "Linux":
            return await self._discover_usb_linux()
        elif system == "Darwin":  # macOS
            return await self._discover_usb_macos()
        else:
            logger.warning("USB discovery not supported", platform=system)
            return []
    
    async def _discover_usb_linux(self) -> List[Resource]:
        """Discover USB devices on Linux via sysfs."""
        resources = []
        usb_path = Path("/sys/bus/usb/devices")
        
        if not usb_path.exists():
            return resources
        
        for device_dir in usb_path.iterdir():
            # Skip interfaces (e.g., 1-1:1.0)
            if ":" in device_dir.name:
                continue
            
            try:
                # Read device info
                vendor_file = device_dir / "idVendor"
                product_file = device_dir / "idProduct"
                manufacturer_file = device_dir / "manufacturer"
                product_name_file = device_dir / "product"
                
                if not vendor_file.exists() or not product_file.exists():
                    continue
                
                vendor_id = vendor_file.read_text().strip()
                product_id = product_file.read_text().strip()
                manufacturer = manufacturer_file.read_text().strip() if manufacturer_file.exists() else "Unknown"
                product_name = product_name_file.read_text().strip() if product_name_file.exists() else "USB Device"
                
                # Skip internal hubs (usually have no product name)
                if product_name == "USB Device" and manufacturer == "Unknown":
                    continue
                
                device_id = f"usb-{vendor_id}-{product_id}-{device_dir.name}"
                
                # Check if it's a storage device
                is_storage = await self._is_usb_storage(device_dir)
                mount_point = await self._get_usb_mount_point(device_dir) if is_storage else None
                
                capabilities = ["read"]
                if is_storage:
                    capabilities.extend(["storage", "write", "eject"])
                
                resource = Resource(
                    id=device_id,
                    name=product_name,
                    type="usb",
                    provider=self.name,
                    resource_class=ResourceClass.DEVICE,
                    state=ResourceState.ONLINE,
                    capabilities=capabilities,
                    last_seen=datetime.utcnow(),
                    metadata={
                        "vendor_id": vendor_id,
                        "product_id": product_id,
                        "manufacturer": manufacturer,
                        "is_storage": is_storage,
                        "mount_point": mount_point,
                        "path": str(device_dir),
                    }
                )
                resources.append(resource)
                
            except Exception as e:
                logger.debug("Failed to read USB device", path=str(device_dir), error=str(e))
        
        return resources
    
    async def _is_usb_storage(self, device_dir: Path) -> bool:
        """Check if USB device is a mass storage device."""
        # Look for block device subdirectory
        for subdir in device_dir.iterdir():
            if not subdir.is_dir():
                continue
            block_path = subdir / "block"
            if block_path.exists():
                return True
        return False
    
    async def _get_usb_mount_point(self, device_dir: Path) -> Optional[str]:
        """Get mount point for USB storage device."""
        try:
            # Find the block device name (e.g., sda, sdb)
            for subdir in device_dir.iterdir():
                if not subdir.is_dir():
                    continue
                block_path = subdir / "block"
                if block_path.exists():
                    for block_name in block_path.iterdir():
                        # Check /proc/mounts for mount point
                        mounts = Path("/proc/mounts").read_text()
                        for line in mounts.split("\n"):
                            if block_name.name in line:
                                parts = line.split()
                                if len(parts) >= 2:
                                    return parts[1]
        except Exception:
            pass
        return None
    
    async def _discover_usb_macos(self) -> List[Resource]:
        """Discover USB devices on macOS via system_profiler."""
        resources = []
        
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["system_profiler", "SPUSBDataType", "-json"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return resources
            
            data = json.loads(result.stdout)
            usb_data = data.get("SPUSBDataType", [])
            
            for bus in usb_data:
                await self._parse_macos_usb_bus(bus, resources)
            
        except Exception as e:
            logger.error("macOS USB discovery failed", error=str(e))
        
        return resources
    
    async def _parse_macos_usb_bus(self, node: dict, resources: list, depth: int = 0):
        """Recursively parse macOS USB tree."""
        # Get device items
        items = node.get("_items", [])
        
        for item in items:
            name = item.get("_name", "Unknown USB Device")
            vendor_id = item.get("vendor_id", "").replace("0x", "")
            product_id = item.get("product_id", "").replace("0x", "")
            manufacturer = item.get("manufacturer", "Unknown")
            serial = item.get("serial_num", "")
            
            # Skip internal Apple devices
            if "Apple" in manufacturer and depth == 0:
                continue
            
            # Skip hubs unless they have interesting children
            if "Hub" in name and not item.get("_items"):
                continue
            
            device_id = f"usb-{vendor_id}-{product_id}-{serial[:8] if serial else 'dev'}"
            
            # Check if it's a storage device
            is_storage = "Mass Storage" in item.get("bcd_device", "") or \
                        any(m.get("bsd_name") for m in item.get("Media", []))
            
            # Get mount point for storage
            mount_point = None
            if is_storage:
                for media in item.get("Media", []):
                    for volume in media.get("volumes", []):
                        mount_point = volume.get("mount_point")
                        if mount_point:
                            break
            
            capabilities = ["read"]
            if is_storage:
                capabilities.extend(["storage", "write", "eject"])
            
            resource = Resource(
                id=device_id,
                name=name,
                type="usb",
                provider=self.name,
                resource_class=ResourceClass.DEVICE,
                state=ResourceState.ONLINE,
                capabilities=capabilities,
                last_seen=datetime.utcnow(),
                metadata={
                    "vendor_id": vendor_id,
                    "product_id": product_id,
                    "manufacturer": manufacturer,
                    "serial": serial,
                    "is_storage": is_storage,
                    "mount_point": mount_point,
                }
            )
            resources.append(resource)
            
            # Recurse into child devices
            if "_items" in item:
                await self._parse_macos_usb_bus(item, resources, depth + 1)
    
    # =========================================
    # Serial Port Discovery
    # =========================================
    
    async def _discover_serial_ports(self) -> List[Resource]:
        """Discover serial ports (ttyUSB, ttyACM, cu.*)."""
        resources = []
        system = platform.system()
        
        if system == "Linux":
            patterns = ["/dev/ttyUSB*", "/dev/ttyACM*"]
        elif system == "Darwin":
            patterns = ["/dev/cu.usbserial*", "/dev/cu.usbmodem*"]
        else:
            return resources
        
        import glob
        for pattern in patterns:
            for port_path in glob.glob(pattern):
                port_name = os.path.basename(port_path)
                device_id = f"serial-{port_name}"
                
                resource = Resource(
                    id=device_id,
                    name=f"Serial Port ({port_name})",
                    type="serial",
                    provider=self.name,
                    resource_class=ResourceClass.DEVICE,
                    state=ResourceState.ONLINE,
                    capabilities=["serial", "read", "write"],
                    last_seen=datetime.utcnow(),
                    metadata={
                        "path": port_path,
                        "port_name": port_name,
                    }
                )
                resources.append(resource)
        
        return resources
    
    # =========================================
    # ESP Device Discovery (Network)
    # =========================================
    
    async def _discover_esp_devices(self) -> List[Resource]:
        """Discover ESP devices via network scanning or MQTT."""
        esp_config = self.config.get("esp_devices", [])
        if not esp_config:
            return []

        semaphore = asyncio.Semaphore(_ESP_DISCOVERY_CONCURRENCY)
        discovered: List[Optional[Resource]] = [None] * len(esp_config)
        esp_state: Dict[str, dict] = {}

        async def inspect_esp(index: int, esp: dict) -> None:
            ip = esp.get("ip")
            if not ip:
                return

            async with semaphore:
                name = esp.get("name", f"ESP-{ip}")
                is_online = await self._check_esp_online(ip)
                device_id = f"esp-{ip.replace('.', '-')}"

                telemetry = {}
                capabilities = ["command"]

                if is_online:
                    info = await self._get_esp_info(ip)
                    if info:
                        name = info.get("name", name)
                        telemetry = info.get("telemetry", {})
                        capabilities = info.get("capabilities", capabilities)

                discovered[index] = Resource(
                    id=device_id,
                    name=name,
                    type="esp",
                    provider=self.name,
                    resource_class=ResourceClass.DEVICE,
                    state=ResourceState.ONLINE if is_online else ResourceState.OFFLINE,
                    capabilities=capabilities,
                    last_seen=datetime.utcnow() if is_online else None,
                    metadata={
                        "ip": ip,
                        "telemetry": telemetry,
                    }
                )
                esp_state[device_id] = {"ip": ip, "online": is_online}

        await asyncio.gather(*(inspect_esp(index, esp) for index, esp in enumerate(esp_config)))
        self._esp_devices = esp_state
        return [resource for resource in discovered if resource is not None]
    
    async def _check_esp_online(self, ip: str) -> bool:
        """Check if ESP device is reachable."""
        if not self._http_client:
            return False
        
        try:
            for endpoint in ESP_HTTP_STATUS_ENDPOINTS:
                response = await self._http_client.get(f"http://{ip}{endpoint}", timeout=3.0)
                if response.status_code == 200:
                    return True
        except Exception:
            return False
        return False

    async def _get_esp_info(self, ip: str) -> Optional[dict]:
        """Get ESP device info via HTTP."""
        if not self._http_client:
            return None
        
        try:
            for endpoint in ESP_HTTP_INFO_ENDPOINTS:
                response = await self._http_client.get(f"http://{ip}{endpoint}", timeout=3.0)
                if response.status_code == 200:
                    return response.json()
        except Exception:
            pass
        return None
    
    # =========================================
    # Resource Actions
    # =========================================
    
    async def get_resource(self, resource_id: str) -> Optional[Resource]:
        """Get a specific device."""
        return self._resources.get(resource_id)
    
    async def execute_action(
        self,
        resource_id: str,
        action: str,
        params: Optional[Dict] = None
    ) -> ActionResult:
        """Execute an action on a device."""
        resource = self._resources.get(resource_id)
        
        if not resource:
            return ActionResult(
                success=False,
                message=f"Device not found: {resource_id}",
                error="NOT_FOUND"
            )
        
        # USB eject action
        if resource.type == "usb" and action == "eject":
            result = await self._eject_usb(resource)
            if result.success:
                self._invalidate_discovery_cache()
            return result

        # ESP command action
        if resource.type == "esp" and action == "command":
            command = params.get("command", "") if params else ""
            result = await self._send_esp_command(resource, command, params)
            if result.success:
                self._invalidate_discovery_cache()
            return result
        
        return ActionResult(
            success=False,
            message=f"Unknown action: {action}",
            error="UNKNOWN_ACTION"
        )
    
    async def _eject_usb(self, resource: Resource) -> ActionResult:
        """Safely eject USB storage device."""
        mount_point = resource.metadata.get("mount_point")
        
        if not mount_point:
            return ActionResult(
                success=False,
                message="Device is not mounted",
                error="NOT_MOUNTED"
            )
        
        try:
            system = platform.system()
            
            if system == "Linux":
                # Unmount and eject
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["umount", mount_point],
                    capture_output=True,
                    timeout=30
                )
            elif system == "Darwin":
                # macOS eject
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["diskutil", "eject", mount_point],
                    capture_output=True,
                    timeout=30
                )
            else:
                return ActionResult(
                    success=False,
                    message="Eject not supported on this platform",
                    error="NOT_SUPPORTED"
                )
            
            if result.returncode == 0:
                return ActionResult(
                    success=True,
                    message=f"Device ejected: {mount_point}"
                )
            else:
                return ActionResult(
                    success=False,
                    message=f"Eject failed: {result.stderr.decode()}",
                    error="EJECT_FAILED"
                )
                
        except Exception as e:
            return ActionResult(
                success=False,
                message=str(e),
                error="EJECT_ERROR"
            )
    
    async def _send_esp_command(
        self, 
        resource: Resource, 
        command: str, 
        params: Optional[Dict]
    ) -> ActionResult:
        """Send command to ESP device via HTTP."""
        if not self._http_client:
            return ActionResult(
                success=False,
                message="HTTP client not available",
                error="NO_HTTP_CLIENT"
            )
        
        ip = resource.metadata.get("ip")
        if not ip:
            return ActionResult(
                success=False,
                message="No IP address for ESP device",
                error="NO_IP"
            )
        
        try:
            payload = {"command": command, "payload": params or {}}
            endpoints = list(ESP_HTTP_COMMAND_ENDPOINTS)

            # Keep a simple query-string fallback for controllers that only expose /set.
            if command in {"set_color", "set_power"}:
                endpoints.append("/set")

            last_error = None
            for endpoint in endpoints:
                if endpoint == "/set" and command == "set_color":
                    payload_data = params or {}
                    query = {}
                    if "r" in payload_data:
                        query["r"] = payload_data.get("r", 0)
                    if "g" in payload_data:
                        query["g"] = payload_data.get("g", 0)
                    if "b" in payload_data:
                        query["b"] = payload_data.get("b", 0)
                    if "brightness" in payload_data:
                        query["brightness"] = payload_data.get("brightness", 255)
                    if "power" in payload_data:
                        query["power"] = 1 if bool(payload_data.get("power")) else 0
                    response = await self._http_client.get(
                        f"http://{ip}{endpoint}",
                        params=query,
                        timeout=5.0
                    )
                elif endpoint == "/set" and command == "set_power":
                    payload_data = params or {}
                    response = await self._http_client.get(
                        f"http://{ip}{endpoint}",
                        params={"power": 1 if bool(payload_data.get("on", payload_data.get("power", True))) else 0},
                        timeout=5.0
                    )
                else:
                    response = await self._http_client.post(
                        f"http://{ip}{endpoint}",
                        json=payload,
                        timeout=5.0
                    )

                if response.status_code == 200:
                    try:
                        data = response.json()
                    except Exception:
                        data = {"raw": response.text}
                    return ActionResult(
                        success=True,
                        message=f"Command sent: {command}",
                        data=data
                    )

                last_error = f"{endpoint} -> HTTP {response.status_code}"

            return ActionResult(
                success=False,
                message=last_error or f"ESP returned an unexpected status for {command}",
                error="ESP_ERROR"
            )
                
        except Exception as e:
            return ActionResult(
                success=False,
                message=str(e),
                error="COMMAND_FAILED"
            )
