"""
Pi Control Panel - IoT Device Discovery Service

Handles mDNS discovery of ESP32 devices and manages their state.
Stores sensor readings to database for historical analysis.
"""

import asyncio
import socket
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict, field
import time
import aiohttp

from zeroconf import ServiceBrowser, Zeroconf, ServiceInfo, ServiceStateChange
from services.sse import sse_manager, Channels

logger = logging.getLogger(__name__)

# Devices can be "LED-only": no `/info`, but accepts LED HTTP command endpoint.
LED_HTTP_COMMAND_ENDPOINTS = [
    "/api/led/command",
    "/led/command",
    "/command",
]

@dataclass
class IoTDevice:
    id: str  # Unique ID (e.g., MAC address or sanitized hostname)
    name: str
    ip: str
    port: int
    last_seen: float
    status: str = "online"  # online, offline
    sensors: List[Dict] = field(default_factory=list)

class DeviceDiscoveryService:
    def __init__(self):
        self.zeroconf: Optional[Zeroconf] = None
        self.browser: Optional[ServiceBrowser] = None
        self.devices: Dict[str, IoTDevice] = {}
        self._running = False
        self._poll_task: Optional[asyncio.Task] = None
        self.service_type = "_iot-device._tcp.local."
        self._db = None

    async def _ensure_db(self) -> bool:
        """Ensure database connection is available. Returns True if connected."""
        if self._db:
            return True
        try:
            from db import get_telemetry_db
            self._db = await get_telemetry_db()
            return True
        except Exception as e:
            logger.warning(f"Could not get database connection: {e}")
            return False

    async def start(self):
        """Start the discovery service."""
        if self._running:
            return

        logger.info("Starting IoT Device Discovery Service...")
        self._running = True
        
        # Get database connection
        try:
            from db import get_telemetry_db
            self._db = await get_telemetry_db()
            # Load existing devices from database
            await self._load_devices_from_db()
        except Exception as e:
            logger.warning(f"Could not connect to database: {e}")
        
        # Initialize Zeroconf lazily to avoid port conflicts during import
        # Use InterfaceChoice.Default to avoid socket binding issues on macOS
        try:
            from zeroconf import InterfaceChoice
            self.zeroconf = Zeroconf(interfaces=InterfaceChoice.Default)
            
            # Start mDNS browser
            self.browser = ServiceBrowser(
                self.zeroconf, 
                self.service_type, 
                handlers=[self._on_service_state_change]
            )
        except OSError as e:
            logger.warning(f"Failed to initialize Zeroconf: {e}. mDNS discovery disabled, using manual/simulated devices only.")

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

    async def _load_devices_from_db(self):
        """Load existing devices from database."""
        if not self._db:
            return
        try:
            cursor = await self._db.execute(
                "SELECT id, name, ip, port, status, last_seen FROM iot_devices"
            )
            rows = await cursor.fetchall()
            for row in rows:
                device = IoTDevice(
                    id=row[0],
                    name=row[1],
                    ip=row[2],
                    port=row[3],
                    status=row[4] or "offline",
                    last_seen=row[5] if row[5] else time.time(),
                    sensors=[]
                )
                self.devices[device.id] = device
            logger.info(f"Loaded {len(rows)} devices from database")
        except Exception as e:
            logger.warning(f"Failed to load devices from database: {e}")

    async def _save_device_to_db(self, device: IoTDevice):
        """Save or update device in database."""
        if not await self._ensure_db():
            return
        
        try:
            await self._db.execute("""
                INSERT INTO iot_devices (id, name, ip, port, status, last_seen)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    ip = excluded.ip,
                    port = excluded.port,
                    status = excluded.status,
                    last_seen = datetime('now')
            """, (device.id, device.name, device.ip, device.port, device.status))
            await self._db.commit()
        except Exception as e:
            logger.warning(f"Failed to save device to database: {e}")

    async def _save_sensor_readings(self, device_id: str, sensors: List[Dict]):
        """Save sensor readings to database for historical tracking."""
        if not sensors:
            return
        
        if not await self._ensure_db():
            return
        
        try:
            timestamp = int(time.time())
            for sensor in sensors:
                await self._db.execute("""
                    INSERT INTO iot_sensor_readings (device_id, sensor_type, value, unit, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (device_id, sensor.get("type"), sensor.get("value"), sensor.get("unit"), timestamp))
            await self._db.commit()
            logger.debug(f"Saved {len(sensors)} sensor readings for {device_id}")
        except Exception as e:
            logger.warning(f"Failed to save sensor readings: {e}")

    async def get_device_history(self, device_id: str, hours: int = 24, sensor_type: Optional[str] = None) -> List[Dict]:
        """Get historical sensor readings for a device."""
        if not self._db:
            return []
        try:
            cutoff = int(time.time()) - (hours * 3600)
            if sensor_type:
                cursor = await self._db.execute("""
                    SELECT sensor_type, value, unit, timestamp
                    FROM iot_sensor_readings
                    WHERE device_id = ? AND sensor_type = ? AND timestamp > ?
                    ORDER BY timestamp ASC
                """, (device_id, sensor_type, cutoff))
            else:
                cursor = await self._db.execute("""
                    SELECT sensor_type, value, unit, timestamp
                    FROM iot_sensor_readings
                    WHERE device_id = ? AND timestamp > ?
                    ORDER BY timestamp ASC
                """, (device_id, cutoff))
            
            rows = await cursor.fetchall()
            return [
                {"sensor_type": r[0], "value": r[1], "unit": r[2], "timestamp": r[3]}
                for r in rows
            ]
        except Exception as e:
            logger.warning(f"Failed to get device history: {e}")
            return []

    async def get_device(self, device_id: str) -> Optional[Dict]:
        """Get a single device by ID."""
        device = self.devices.get(device_id)
        if device:
            return asdict(device)
        return None

    def _on_service_state_change(self, zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange) -> None:
        """Handle mDNS service changes."""
        logger.debug(f"Service {name} {state_change}")
        
        if state_change == ServiceStateChange.Added or state_change == ServiceStateChange.Updated:
            info = zeroconf.get_service_info(service_type, name)
            if info:
                asyncio.create_task(self._add_or_update_device_async(info))
        elif state_change == ServiceStateChange.Removed:
            asyncio.create_task(self._remove_device_async(name))

    async def _add_or_update_device_async(self, info: ServiceInfo):
        """Add or update a device in the registry (async version)."""
        # Parse IP
        addresses = [socket.inet_ntoa(addr) for addr in info.addresses]
        if not addresses:
            return
            
        ip = addresses[0]
        port = info.port
        
        # Create a unique ID from the name
        device_id = info.name.split('.')[0]
        device_name = device_id.replace('-', ' ').title()

        device = IoTDevice(
            id=device_id,
            name=device_name,
            ip=ip,
            port=port,
            last_seen=time.time(),
            status="online",
            sensors=[]
        )
        
        is_new = device_id not in self.devices
        self.devices[device_id] = device
        
        # Save to database
        await self._save_device_to_db(device)
        
        logger.info(f"{'Discovered' if is_new else 'Updated'} device: {device_name} at {ip}:{port}")
        
        # Trigger immediate poll for new devices to get sensor info
        if is_new:
            await self._poll_device(device_id)
             
        self._broadcast_update()

    async def _remove_device_async(self, service_name: str):
        """Remove a device from the registry (async version)."""
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
            
            await asyncio.sleep(2)  # Poll every 2 seconds

    async def _poll_device(self, device_id: str):
        """Poll a single device for its status/info."""
        device = self.devices.get(device_id)
        if not device:
            return

        # Check if this is a simulated device (192.168.1.10x pattern with no real endpoint)
        is_simulated = device.ip.startswith("192.168.1.10") and device.sensors
        
        if is_simulated:
            # Simulated device - just update with random data
            await self._update_simulated_device(device)
            return

        # Real device - try to connect
        try:
            timeout = aiohttp.ClientTimeout(total=2.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Prefer `/info` for full device state.
                url = f"http://{device.ip}:{device.port}/info"
                try:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json()

                            device.last_seen = time.time()
                            device.status = "online"

                            if isinstance(data, dict) and "sensors" in data:
                                device.sensors = data["sensors"] or []
                                await self._save_sensor_readings(device_id, device.sensors)

                            await self._save_device_to_db(device)
                            self._broadcast_update()
                            return
                except Exception:
                    # Fall through to LED-only probe.
                    pass

                # Some devices may not expose `/info`, but can still be controlled via LED HTTP endpoint.
                if await self._probe_led_only_device(session, device):
                    return

                await self._mark_offline(device)
        except Exception:
            await self._mark_offline(device)

    async def _probe_led_only_device(self, session: aiohttp.ClientSession, device: IoTDevice) -> bool:
        """
        Mark device online if it responds to a lightweight LED HTTP command.
        This keeps LED controls usable even when `/info` is not implemented.
        """
        # First try a simple status endpoint used by some RGB sketches.
        try:
            async with session.get(f"http://{device.ip}:{device.port}/status") as resp:
                if 200 <= resp.status < 300:
                    try:
                        data = await resp.json()
                        if isinstance(data, dict) and all(k in data for k in ("r", "g", "b")):
                            device.sensors = [
                                {"type": "led_r", "value": int(data.get("r", 0)), "unit": ""},
                                {"type": "led_g", "value": int(data.get("g", 0)), "unit": ""},
                                {"type": "led_b", "value": int(data.get("b", 0)), "unit": ""},
                            ]
                    except Exception:
                        pass
                    device.last_seen = time.time()
                    device.status = "online"
                    await self._save_device_to_db(device)
                    self._broadcast_update()
                    return True
        except Exception:
            pass

        # Next try JSON LED command endpoints.
        request_body = {"command": "ping", "payload": {}}
        for endpoint in LED_HTTP_COMMAND_ENDPOINTS:
            url = f"http://{device.ip}:{device.port}{endpoint}"
            try:
                async with session.post(url, json=request_body) as resp:
                    if 200 <= resp.status < 300:
                        device.last_seen = time.time()
                        device.status = "online"
                        await self._save_device_to_db(device)
                        self._broadcast_update()
                        return True
            except Exception:
                continue
        return False

    async def _update_simulated_device(self, device: IoTDevice):
        """Update a simulated device with realistic random sensor data."""
        import random
        
        # Only update if device has sensors (meaning it's a simulated device)
        if not device.sensors:
            await self._mark_offline(device)
            return
        
        device.last_seen = time.time()
        device.status = "online"
        
        # Generate new sensor values with realistic variations
        new_sensors = []
        for sensor in device.sensors:
            sensor_type = sensor.get("type", "unknown")
            old_value = sensor.get("value", 0)
            unit = sensor.get("unit", "")
            
            # Generate realistic variations based on sensor type
            if sensor_type == "temperature":
                # Temperature changes slowly: ±0.5°C variation
                variation = random.uniform(-0.5, 0.5)
                new_value = max(10, min(40, old_value + variation))
                new_value = round(new_value, 1)
            elif sensor_type == "humidity":
                # Humidity: ±2% variation
                variation = random.uniform(-2, 2)
                new_value = max(20, min(90, old_value + variation))
                new_value = round(new_value, 1)
            elif sensor_type == "light":
                # Light can change more: ±50 lux variation
                variation = random.uniform(-50, 50)
                new_value = max(0, min(2000, old_value + variation))
                new_value = int(new_value)
            elif sensor_type == "voltage":
                # Voltage is very stable: ±0.05V
                variation = random.uniform(-0.05, 0.05)
                new_value = max(3.0, min(4.5, old_value + variation))
                new_value = round(new_value, 2)
            elif sensor_type == "signal_strength":
                # Signal strength: ±3 dBm
                variation = random.uniform(-3, 3)
                new_value = max(-100, min(-20, old_value + variation))
                new_value = int(new_value)
            elif sensor_type == "co2":
                # CO2: ±20 ppm
                variation = random.uniform(-20, 20)
                new_value = max(400, min(2000, old_value + variation))
                new_value = int(new_value)
            elif sensor_type == "pressure":
                # Pressure: ±2 hPa
                variation = random.uniform(-2, 2)
                new_value = max(950, min(1050, old_value + variation))
                new_value = int(new_value)
            elif sensor_type == "noise":
                # Noise: ±5 dB
                variation = random.uniform(-5, 5)
                new_value = max(20, min(100, old_value + variation))
                new_value = int(new_value)
            elif sensor_type == "soil_moisture":
                # Soil moisture: ±3%
                variation = random.uniform(-3, 3)
                new_value = max(0, min(100, old_value + variation))
                new_value = int(new_value)
            elif sensor_type == "gas":
                # Gas level: ±10 ppm
                variation = random.uniform(-10, 10)
                new_value = max(0, min(500, old_value + variation))
                new_value = int(new_value)
            elif sensor_type == "smoke":
                # Smoke level: ±5 ppm
                variation = random.uniform(-5, 5)
                new_value = max(0, min(200, old_value + variation))
                new_value = int(new_value)
            elif sensor_type == "air_quality":
                # Air Quality Index: ±5
                variation = random.uniform(-5, 5)
                new_value = max(0, min(500, old_value + variation))
                new_value = int(new_value)
            elif sensor_type == "motion":
                # Motion: random 0 or 1
                new_value = random.randint(0, 1)
            else:
                # Generic: ±5% variation
                variation = random.uniform(-5, 5)
                new_value = max(0, old_value + variation)
                new_value = round(new_value, 1)
            
            new_sensors.append({
                "type": sensor_type,
                "value": new_value,
                "unit": unit
            })
        
        device.sensors = new_sensors
        
        # Save to database (with error handling)
        try:
            await self._save_sensor_readings(device.id, new_sensors)
            await self._save_device_to_db(device)
        except Exception as e:
            logger.warning(f"Failed to save simulated data for {device.id}: {e}")
        
        # Broadcast update
        self._broadcast_update()
            
    async def _mark_offline(self, device: IoTDevice):
        """Mark device as offline."""
        if device.status != "offline":
            device.status = "offline"
            await self._save_device_to_db(device)
            self._broadcast_update()

    def _broadcast_update(self):
        """Broadcast current device list to frontend via SSE."""
        payload = [asdict(d) for d in self.devices.values()]
        asyncio.create_task(sse_manager.broadcast(
            Channels.TELEMETRY,
            "iot_update",
            payload
        ))

    def get_devices(self) -> List[Dict]:
        """Get all devices as list of dicts."""
        return [asdict(d) for d in self.devices.values()]

    async def add_device_manual(self, device_id: str, name: str, ip: str, port: int, sensors: List[Dict] = None) -> IoTDevice:
        """Manually add a device (for simulation/testing)."""
        device = IoTDevice(
            id=device_id,
            name=name,
            ip=ip,
            port=port,
            last_seen=time.time(),
            status="online",
            sensors=sensors or []
        )
        self.devices[device_id] = device
        await self._save_device_to_db(device)
        if sensors:
            await self._save_sensor_readings(device_id, sensors)
        self._broadcast_update()
        return device

# Global instance
discovery_service = DeviceDiscoveryService()
