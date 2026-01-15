"""
Pi Control Panel - IoT Device Discovery Service

Handles mDNS discovery of ESP32 devices and manages their state.
"""

import asyncio
import socket
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import time
import aiohttp

from zeroconf import ServiceBrowser, Zeroconf, ServiceInfo, ServiceStateChange
from services.sse import sse_manager, Channels

logger = logging.getLogger(__name__)

@dataclass
class IoTDevice:
    id: str  # Unique ID (e.g., MAC address or sanitized hostname)
    name: str
    ip: str
    port: int
    last_seen: float
    status: str = "online"  # online, offline
    sensors: List[Dict] = None

class DeviceDiscoveryService:
    def __init__(self):
        self.zeroconf = Zeroconf()
        self.browser: Optional[ServiceBrowser] = None
        self.devices: Dict[str, IoTDevice] = {}
        self._running = False
        self._poll_task: Optional[asyncio.Task] = None
        self.service_type = "_esp-sensor._tcp.local."

    async def start(self):
        """Start the discovery service."""
        if self._running:
            return

        logger.info("Starting IoT Device Discovery Service...")
        self._running = True
        
        # Start mDNS browser
        self.browser = ServiceBrowser(
            self.zeroconf, 
            self.service_type, 
            handlers=[self._on_service_state_change]
        )

        # Start polling task
        self._poll_task = asyncio.create_task(self._monitor_loop())

    async def stop(self):
        """Stop the discovery service."""
        self._running = False
        if self.browser:
            self.browser.cancel()
        if self.zeroconf:
            self.zeroconf.close()
        
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        
        logger.info("IoT Device Discovery Service stopped")

    def _on_service_state_change(self, zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange) -> None:
        """Handle mDNS service changes."""
        logger.debug(f"Service {name} {state_change}")
        
        if state_change == ServiceStateChange.Added or state_change == ServiceStateChange.Updated:
            info = zeroconf.get_service_info(service_type, name)
            if info:
                self._add_or_update_device(info)
        elif state_change == ServiceStateChange.Removed:
            self._remove_device(name)

    def _add_or_update_device(self, info: ServiceInfo):
        """Add or update a device in the registry."""
        # Parse IP
        addresses = [socket.inet_ntoa(addr) for addr in info.addresses]
        if not addresses:
            return
            
        ip = addresses[0]
        port = info.port
        hostname = info.server
        
        # Create a unique ID from the name (e.g., "living-room._esp-sensor._tcp.local." -> "living-room")
        device_id = info.name.split('.')[0]
        device_name = device_id.replace('-', ' ').title()

        device = IoTDevice(
            id=device_id,
            name=device_name,
            ip=ip,
            port=port,
            last_seen=time.time(),
            status="online",
            sensors=[] # Will be populated by polling
        )
        
        is_new = device_id not in self.devices
        self.devices[device_id] = device
        
        logger.info(f"{'Discovered' if is_new else 'Updated'} device: {device_name} at {ip}:{port}")
        
        # Trigger immediate poll for new devices to get sensor info
        if is_new:
             asyncio.create_task(self._poll_device(device_id))
             
        self._broadcast_update()

    def _remove_device(self, service_name: str):
        """Remove a device from the registry."""
        device_id = service_name.split('.')[0]
        if device_id in self.devices:
            logger.info(f"Device removed: {device_id}")
            del self.devices[device_id]
            self._broadcast_update()

    async def _monitor_loop(self):
        """Periodically poll devices for sensor data."""
        while self._running:
            for device_id in list(self.devices.keys()):
                await self._poll_device(device_id)
            
            await asyncio.sleep(2) # Poll every 2 seconds

    async def _poll_device(self, device_id: str):
        """Poll a single device for its status/info."""
        device = self.devices.get(device_id)
        if not device:
            return

        try:
            url = f"http://{device.ip}:{device.port}/info"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=2.0) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # Expecting format: { "name": "...", "sensors": [...] }
                        
                        device.last_seen = time.time()
                        device.status = "online"
                        
                        if "sensors" in data:
                            device.sensors = data["sensors"]
                        
                        # Broadcast sensor update via SSE specifically for this device? 
                        # Or just rely on the periodic _broadcast_update?
                        # For high frequency, we might want a specific channel.
                        # For now, let's update the main state.
                    else:
                         self._mark_offline(device)

        except Exception as e:
            # logger.warn(f"Failed to poll {device.name}: {e}")
            self._mark_offline(device)
            
    def _mark_offline(self, device: IoTDevice):
        if device.status != "offline":
            device.status = "offline"
            self._broadcast_update()

    def _broadcast_update(self):
        """Broadcast current device list to frontend via SSE."""
        payload = [asdict(d) for d in self.devices.values()]
        asyncio.create_task(sse_manager.broadcast(
            Channels.TELEMETRY, # Reusing telemetry channel or create a new 'iot' channel?
            # Telemetry channel is fine for now, or we add 'iot' event type.
            "iot_update",
            payload
        ))

    def get_devices(self) -> List[Dict]:
        return [asdict(d) for d in self.devices.values()]

# Global instance
discovery_service = DeviceDiscoveryService()
