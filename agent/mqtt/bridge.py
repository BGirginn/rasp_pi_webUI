"""
Pi Agent - MQTT Bridge

Bridges ESP devices to the control panel via MQTT.
Full implementation in Sprint 7.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import structlog

try:
    import paho.mqtt.client as mqtt
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False

logger = structlog.get_logger(__name__)


class MQTTBridge:
    """MQTT bridge for ESP device communication."""
    
    def __init__(self, config: dict):
        self.config = config.get("mqtt", {})
        self._host = self.config.get("host", "localhost")
        self._port = self.config.get("port", 1883)
        self._username = self.config.get("username", "panel")
        self._password = self._load_password()
        
        self._client: Optional[mqtt.Client] = None
        self._connected = False
        self._devices: Dict[str, Dict] = {}
        self._telemetry_callback: Optional[Callable] = None
    
    def _load_password(self) -> Optional[str]:
        """Load MQTT password from file or config."""
        password_file = self.config.get("password_file")
        if password_file:
            try:
                with open(password_file, "r") as f:
                    return f.read().strip()
            except FileNotFoundError:
                pass
        return self.config.get("password")
    
    @property
    def is_connected(self) -> bool:
        return self._connected
    
    async def start(self) -> None:
        """Start MQTT connection."""
        if not PAHO_AVAILABLE:
            logger.warning("paho-mqtt not available, MQTT bridge disabled")
            return
        
        self._client = mqtt.Client(client_id="pi-control-panel")
        
        # Set callbacks
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        
        # Set credentials
        if self._username and self._password:
            self._client.username_pw_set(self._username, self._password)
        
        # Connect
        try:
            self._client.connect_async(self._host, self._port, keepalive=60)
            self._client.loop_start()
            logger.info("MQTT bridge starting", host=self._host, port=self._port)
        except Exception as e:
            logger.error("Failed to connect to MQTT", error=str(e))
    
    async def stop(self) -> None:
        """Stop MQTT connection."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
        self._connected = False
        logger.info("MQTT bridge stopped")
    
    def _on_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection."""
        if rc == 0:
            self._connected = True
            logger.info("MQTT connected")
            
            # Subscribe to device topics
            topics = self.config.get("topics", {})
            telemetry_topic = topics.get("devices", "devices/+/telemetry")
            status_topic = topics.get("status", "devices/+/status")
            
            client.subscribe(telemetry_topic)
            client.subscribe(status_topic)
            logger.debug("Subscribed to topics", telemetry=telemetry_topic, status=status_topic)
        else:
            logger.error("MQTT connection failed", rc=rc)
    
    def _on_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection."""
        self._connected = False
        if rc != 0:
            logger.warning("MQTT disconnected unexpectedly", rc=rc)
        else:
            logger.info("MQTT disconnected")
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT message."""
        try:
            topic_parts = msg.topic.split("/")
            if len(topic_parts) < 3:
                return
            
            device_id = topic_parts[1]
            message_type = topic_parts[2]
            
            payload = json.loads(msg.payload.decode("utf-8"))
            
            if message_type == "telemetry":
                self._handle_telemetry(device_id, payload)
            elif message_type == "status":
                self._handle_status(device_id, payload)
            
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in MQTT message", topic=msg.topic)
        except Exception as e:
            logger.exception("Error handling MQTT message", error=str(e))
    
    def _handle_telemetry(self, device_id: str, payload: Dict) -> None:
        """Handle device telemetry message."""
        if device_id not in self._devices:
            self._devices[device_id] = {"id": device_id, "first_seen": datetime.utcnow()}
        
        self._devices[device_id]["last_telemetry"] = payload
        self._devices[device_id]["last_seen"] = datetime.utcnow()
        
        logger.debug("Device telemetry", device=device_id, payload=payload)
        
        if self._telemetry_callback:
            asyncio.create_task(self._telemetry_callback(device_id, payload))
    
    def _handle_status(self, device_id: str, payload: Dict) -> None:
        """Handle device status message."""
        if device_id not in self._devices:
            self._devices[device_id] = {"id": device_id, "first_seen": datetime.utcnow()}
        
        self._devices[device_id]["status"] = payload.get("status", "unknown")
        self._devices[device_id]["last_seen"] = datetime.utcnow()
        
        logger.info("Device status", device=device_id, status=payload)
    
    async def send_command(
        self,
        device_id: str,
        command: str,
        payload: Optional[Dict] = None
    ) -> Dict:
        """Send command to device."""
        if not self._connected or not self._client:
            return {"success": False, "error": "MQTT not connected"}
        
        topic = f"devices/{device_id}/command"
        message = {
            "command": command,
            "payload": payload or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            result = self._client.publish(topic, json.dumps(message), qos=1)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info("Command sent", device=device_id, command=command)
                return {"success": True, "message": f"Command '{command}' sent to {device_id}"}
            else:
                return {"success": False, "error": f"Publish failed: {result.rc}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_devices(self) -> List[Dict]:
        """Get list of known devices."""
        return [
            {
                "id": device_id,
                "status": info.get("status", "unknown"),
                "last_seen": info.get("last_seen").isoformat() if info.get("last_seen") else None,
                "telemetry": info.get("last_telemetry", {}),
            }
            for device_id, info in self._devices.items()
        ]
    
    def set_telemetry_callback(self, callback: Callable) -> None:
        """Set callback for telemetry messages."""
        self._telemetry_callback = callback
