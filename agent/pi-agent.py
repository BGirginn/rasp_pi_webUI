#!/usr/bin/env python3
"""
Pi Control Panel - Agent

The Pi Agent runs as a systemd service on the Raspberry Pi and provides:
- Resource discovery (Docker, systemd, network, devices)
- Telemetry collection (CPU, memory, disk, network, temperature)
- Job execution (backup, restore, update, cleanup)
- MQTT bridge for ESP devices
- Unix socket RPC for Panel API communication

Usage:
    python3 pi-agent.py [--config CONFIG_PATH]
"""

import asyncio
import argparse
import signal
import sys
from pathlib import Path

import structlog
import yaml

from rpc.socket_server import SocketServer
from providers import ProviderManager
from telemetry.collector import TelemetryCollector
from jobs.runner import JobRunner
from mqtt.bridge import MQTTBridge

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class PiAgent:
    """Main Pi Agent application."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.running = False
        self._shutdown_event = asyncio.Event()
        
        # Initialize components
        self.provider_manager = ProviderManager(self.config)
        self.telemetry_collector = TelemetryCollector(self.config)
        self.job_runner = JobRunner(self.config)
        self.mqtt_bridge = MQTTBridge(self.config) if self.config.get("mqtt", {}).get("enabled") else None
        # Initialize components
        socket_config = self.config.get("socket", {})
        self.socket_server = SocketServer(
            socket_path=socket_config.get("path"),
            handler=self._handle_rpc,
            permissions=socket_config.get("permissions", "0660"),
            group=socket_config.get("group")
        )
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        path = Path(config_path)
        if not path.exists():
            logger.warning("Config file not found, using defaults", path=config_path)
            return self._default_config()
        
        with open(path, "r") as f:
            config = yaml.safe_load(f)
        
        logger.info("Configuration loaded", path=config_path)
        return config
    
    def _default_config(self) -> dict:
        """Return default configuration."""
        return {
            "agent": {"name": "pi-agent", "version": "1.0.0"},
            "socket": {"path": "/run/pi-agent/agent.sock", "permissions": "0660"},
            "discovery": {"interval": 30, "providers": ["docker", "systemd"]},
            "telemetry": {"interval": 2, "db_path": "/var/lib/pi-control/telemetry.db"},
            "health": {"interval": 10},
            "jobs": {"max_concurrent": 2, "default_timeout": 600},
            "mqtt": {"enabled": False},
            "logging": {"level": "INFO"},
        }
    
    async def _handle_rpc(self, method: str, params: dict) -> dict:
        """Handle RPC requests from Panel API."""
        logger.debug("RPC request received", method=method)
        
        handlers = {
            # Discovery
            "discovery.snapshot": self.provider_manager.get_snapshot,
            "discovery.refresh": self.provider_manager.refresh,
            
            # Resource actions
            "resource.action": self.provider_manager.execute_action,
            "resource.logs": self.provider_manager.get_logs,
            "resource.stats": self.provider_manager.get_stats,
            
            # Telemetry
            "telemetry.current": self.telemetry_collector.get_current,
            "telemetry.query": self.telemetry_collector.query,
            
            # Jobs
            "job.run": self.job_runner.run_job,
            "job.status": self.job_runner.get_status,
            "job.cancel": self.job_runner.cancel_job,
            
            # System
            "system.info": self._get_system_info,
            "system.health": self._get_health,
            
            # Network
            "network.interfaces": self.provider_manager.get_network_interfaces,
            "network.wifi.toggle": self.provider_manager.toggle_wifi,
            "network.wifi.scan": self.provider_manager.scan_wifi,
            "network.wifi.status": self.provider_manager.wifi_status,
            "network.wifi.connect": self.provider_manager.wifi_connect,
            "network.wifi.disconnect": self.provider_manager.wifi_disconnect,
            "network.interface.enable": lambda interface: self.provider_manager.toggle_wifi(True),
            "network.interface.disable": lambda interface, rollback_seconds=0: self.provider_manager.toggle_wifi(False),
            "network.interface.restart": lambda interface: self.provider_manager.toggle_wifi(True),
            
            # Devices
            "devices.list": self.provider_manager.get_devices,
            "devices.command": self._send_device_command,
        }
        
        handler = handlers.get(method)
        if not handler:
            return {"error": f"Unknown method: {method}"}
        
        try:
            result = await handler(**params) if params else await handler()
            return {"result": result}
        except Exception as e:
            logger.exception("RPC handler error", method=method, error=str(e))
            return {"error": str(e)}
    
    async def _get_system_info(self) -> dict:
        """Get system information."""
        import platform
        import psutil
        
        return {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "agent_version": self.config["agent"]["version"],
            "uptime_seconds": int(psutil.boot_time()),
            "cpu_count": psutil.cpu_count(),
            "memory_total_mb": psutil.virtual_memory().total // (1024 * 1024),
        }
    
    async def _get_health(self) -> dict:
        """Get agent health status."""
        return {
            "status": "healthy",
            "components": {
                "socket_server": self.socket_server.is_running,
                "provider_manager": self.provider_manager.is_healthy,
                "telemetry_collector": self.telemetry_collector.is_running,
                "job_runner": self.job_runner.is_healthy,
                "mqtt_bridge": self.mqtt_bridge.is_connected if self.mqtt_bridge else None,
            }
        }
    
    async def _send_device_command(self, device_id: str, command: str, payload: dict = None) -> dict:
        """Send command to device via MQTT."""
        if not self.mqtt_bridge:
            return {"error": "MQTT bridge not enabled"}
        
        return await self.mqtt_bridge.send_command(device_id, command, payload)
    
    async def _discovery_loop(self):
        """Run discovery at configured interval."""
        interval = self.config["discovery"]["interval"]
        
        while self.running:
            try:
                await self.provider_manager.discover()
                logger.debug("Discovery completed")
            except Exception as e:
                logger.exception("Discovery error", error=str(e))
            
            await asyncio.sleep(interval)
    
    async def _health_beacon_loop(self):
        """Send health beacons at configured interval."""
        interval = self.config["health"]["interval"]
        
        while self.running:
            try:
                health = await self._get_health()
                logger.debug("Health beacon", status=health["status"])
                # TODO: POST to Panel API health endpoint
            except Exception as e:
                logger.exception("Health beacon error", error=str(e))
            
            await asyncio.sleep(interval)
    
    async def start(self):
        """Start the Pi Agent."""
        logger.info("Starting Pi Agent", version=self.config["agent"]["version"])
        self.running = True
        
        # Start components
        await self.socket_server.start()
        await self.provider_manager.start()
        await self.telemetry_collector.start()
        await self.job_runner.start()
        
        if self.mqtt_bridge:
            await self.mqtt_bridge.start()
        
        # Start background loops
        asyncio.create_task(self._discovery_loop())
        asyncio.create_task(self._health_beacon_loop())
        
        logger.info("Pi Agent started successfully")
        
        # Wait for shutdown signal
        await self._shutdown_event.wait()
    
    async def stop(self):
        """Stop the Pi Agent gracefully."""
        logger.info("Stopping Pi Agent")
        self.running = False
        
        # Stop components
        if self.mqtt_bridge:
            await self.mqtt_bridge.stop()
        
        await self.job_runner.stop()
        await self.telemetry_collector.stop()
        await self.provider_manager.stop()
        await self.socket_server.stop()
        
        self._shutdown_event.set()
        logger.info("Pi Agent stopped")
    
    def handle_signal(self, signum, frame):
        """Handle shutdown signals."""
        logger.info("Received signal", signal=signum)
        asyncio.create_task(self.stop())


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Pi Control Panel Agent")
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Path to configuration file"
    )
    args = parser.parse_args()
    
    agent = PiAgent(config_path=args.config)
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, agent.handle_signal)
    signal.signal(signal.SIGINT, agent.handle_signal)
    
    try:
        await agent.start()
    except Exception as e:
        logger.exception("Agent failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
