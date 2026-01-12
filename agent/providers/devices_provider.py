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


class DevicesProvider(BaseProvider):
    """Provider for hardware devices."""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self._esp_devices: Dict[str, dict] = {}
        self._usb_devices: Dict[str, dict] = {}
        self._http_client: Optional[httpx.AsyncClient] = None
    
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
        for r in resources:
            self._resources[r.id] = r
        
        logger.info("Device discovery complete", 
                   usb=len(usb_resources),
                   serial=len(serial_resources),
                   esp=len(esp_resources))
        return resources
    
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
        resources = []
        
        # Get known ESP devices from config
        esp_config = self.config.get("esp_devices", [])
        
        for esp in esp_config:
            ip = esp.get("ip")
            name = esp.get("name", f"ESP-{ip}")
            
            if not ip:
                continue
            
            # Check if device is online
            is_online = await self._check_esp_online(ip)
            device_id = f"esp-{ip.replace('.', '-')}"
            
            # Get device info if online
            telemetry = {}
            capabilities = ["command"]
            
            if is_online:
                info = await self._get_esp_info(ip)
                if info:
                    name = info.get("name", name)
                    telemetry = info.get("telemetry", {})
                    capabilities = info.get("capabilities", capabilities)
            
            resource = Resource(
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
            resources.append(resource)
            self._esp_devices[device_id] = {"ip": ip, "online": is_online}
        
        return resources
    
    async def _check_esp_online(self, ip: str) -> bool:
        """Check if ESP device is reachable."""
        if not self._http_client:
            return False
        
        try:
            response = await self._http_client.get(f"http://{ip}/state", timeout=3.0)
            return response.status_code == 200
        except Exception:
            return False
    
    async def _get_esp_info(self, ip: str) -> Optional[dict]:
        """Get ESP device info via HTTP."""
        if not self._http_client:
            return None
        
        try:
            response = await self._http_client.get(f"http://{ip}/discovery", timeout=3.0)
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
            return await self._eject_usb(resource)
        
        # ESP command action
        if resource.type == "esp" and action == "command":
            command = params.get("command", "") if params else ""
            return await self._send_esp_command(resource, command, params)
        
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
            payload = {"action": command}
            if params:
                payload.update(params)
            
            response = await self._http_client.post(
                f"http://{ip}/control",
                json=payload,
                timeout=5.0
            )
            
            if response.status_code == 200:
                return ActionResult(
                    success=True,
                    message=f"Command sent: {command}",
                    data=response.json()
                )
            else:
                return ActionResult(
                    success=False,
                    message=f"ESP returned {response.status_code}",
                    error="ESP_ERROR"
                )
                
        except Exception as e:
            return ActionResult(
                success=False,
                message=str(e),
                error="COMMAND_FAILED"
            )
