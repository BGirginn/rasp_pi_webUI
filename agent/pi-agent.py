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
import ipaddress
import json
import signal
import ssl
import sys
from pathlib import Path

import structlog
import yaml

from rpc.socket_server import SocketServer
from rpc.tls_server import TLSSocketServer
from policy.loader import get_registry
from policy.validate import PolicyError, enforce_action
from security.auth import AuthError, verify_envelope
from security.mtls import validate_client_certificate
from security.replay import ReplayCache, ReplayError
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
        self.socket_server = SocketServer(
            socket_path=self.config["socket"]["path"],
            handler=self._handle_rpc
        )
        self.tls_server = None
        self.policy_registry = get_registry()
        security_config = self.config.get("security", {})
        self.replay_cache = ReplayCache(ttl_seconds=int(security_config.get("replay_ttl_seconds", 300)))
        self.clock_skew_seconds = int(security_config.get("clock_skew_seconds", 120))
        self.params_max_bytes = int(security_config.get("params_max_bytes", 16384))
        self.allow_hmac_fallback = bool(security_config.get("allow_hmac_fallback", False))

        self._configure_tls_server()
    
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
            "rpc": {
                "transport": "unix",
                "host": "127.0.0.1",
                "port": 9443,
                "tailscale_cidr": "100.64.0.0/10",
            },
            "discovery": {"interval": 30, "providers": ["docker", "systemd"]},
            "telemetry": {"interval": 2, "db_path": "/data/telemetry.db"},
            "health": {"interval": 10},
            "jobs": {"max_concurrent": 2, "default_timeout": 600},
            "mqtt": {"enabled": False},
            "logging": {"level": "INFO"},
            "security": {
                "panel_shared_key": "",
                "clock_skew_seconds": 120,
                "replay_ttl_seconds": 300,
                "params_max_bytes": 16384,
                "allow_hmac_fallback": True,
            },
            "mtls": {
                "server_cert": "",
                "server_key": "",
                "client_ca": "",
                "allowed_client_identities": [],
                "allowed_client_fingerprints": [],
            },
        }
    
    async def _handle_rpc(self, method: str, params: dict, client_info: dict = None) -> dict:
        """Handle RPC requests from Panel API."""
        logger.debug("RPC request received", method=method)

        request_id = None
        action_id = None
        client_info = client_info or {}
        mtls_authenticated = bool(client_info.get("mtls_authenticated"))
        
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
            
            # Devices
            "devices.list": self.provider_manager.get_devices,
            "devices.command": self._send_device_command,
        }
        
        handler = handlers.get(method)
        if not handler:
            return {"error": {"code": "unknown_action", "message": f"Unknown action '{method}'"}}

        try:
            if not isinstance(params, dict):
                raise PolicyError("invalid_params", "Envelope must be an object")

            action_id = params.get("action_id")
            request_id = params.get("request_id")

            if not action_id or not isinstance(action_id, str):
                raise PolicyError("invalid_params", "action_id is required")
            if action_id != method:
                raise PolicyError("invalid_params", "action_id does not match method")
            if not request_id or not isinstance(request_id, str):
                raise PolicyError("invalid_params", "request_id is required")

            issued_at = params.get("issued_at")
            if not isinstance(issued_at, (int, float)):
                raise PolicyError("invalid_params", "issued_at is required")

            nonce = params.get("nonce")
            if not isinstance(nonce, str) or not nonce:
                raise PolicyError("invalid_params", "nonce is required")

            requested_by = params.get("requested_by")
            if requested_by is not None and not isinstance(requested_by, dict):
                raise PolicyError("invalid_params", "requested_by must be an object")

            envelope_params = params.get("params") or {}
            if envelope_params and not isinstance(envelope_params, dict):
                raise PolicyError("invalid_params", "params must be an object")

            if self.params_max_bytes:
                size_bytes = len(json.dumps(envelope_params, sort_keys=True, separators=(",", ":")))
                if size_bytes > self.params_max_bytes:
                    raise PolicyError("invalid_params", "params too large")

            if not mtls_authenticated and not self.allow_hmac_fallback:
                raise AuthError("unauthorized", "mTLS required")

            verify_envelope(
                params,
                self.config,
                max_skew_seconds=self.clock_skew_seconds,
                require_signature=not mtls_authenticated,
            )
            await self.replay_cache.check_and_store(nonce)

            policy_result = enforce_action(
                registry=self.policy_registry,
                action_id=action_id,
                params=envelope_params,
                confirm_token=params.get("confirm_token"),
            )
            validated_params = policy_result["params"]

            result = await handler(**validated_params) if validated_params else await handler()
            return {"result": result, "request_id": request_id}

        except (PolicyError, AuthError, ReplayError) as e:
            logger.warning(
                "RPC request rejected",
                method=method,
                request_id=request_id,
                error_code=e.code,
            )
            return {
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "data": {"request_id": request_id, "action_id": action_id},
                }
            }
        except Exception as e:
            logger.exception("RPC handler error", method=method, request_id=request_id, error=str(e))
            return {
                "error": {
                    "code": "internal_error",
                    "message": "Internal error",
                    "data": {"request_id": request_id, "action_id": action_id},
                }
            }

    def _configure_tls_server(self) -> None:
        rpc_config = self.config.get("rpc", {})
        if rpc_config.get("transport") != "tls":
            return

        host = rpc_config.get("host", "127.0.0.1")
        port = int(rpc_config.get("port", 9443))
        tailscale_cidr = rpc_config.get("tailscale_cidr", "100.64.0.0/10")

        self._validate_bind_address(host, tailscale_cidr)

        mtls_config = self.config.get("mtls", {})
        server_cert = mtls_config.get("server_cert")
        server_key = mtls_config.get("server_key")
        client_ca = mtls_config.get("client_ca")

        if not server_cert or not server_key or not client_ca:
            raise ValueError("mTLS config requires server_cert, server_key, and client_ca")

        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.verify_mode = ssl.CERT_REQUIRED
        ssl_context.load_cert_chain(certfile=server_cert, keyfile=server_key)
        ssl_context.load_verify_locations(cafile=client_ca)

        allowed_identities = mtls_config.get("allowed_client_identities", [])
        allowed_fingerprints = mtls_config.get("allowed_client_fingerprints", [])

        def _validator(peer_cert, fingerprint):
            validate_client_certificate(
                peer_cert,
                fingerprint,
                allowed_identities=allowed_identities,
                allowed_fingerprints=allowed_fingerprints,
            )

        self.tls_server = TLSSocketServer(
            host=host,
            port=port,
            handler=self._handle_rpc,
            ssl_context=ssl_context,
            client_validator=_validator,
        )

    def _validate_bind_address(self, host: str, tailscale_cidr: str) -> None:
        if host in ("localhost", ""):
            return
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            raise ValueError(f"RPC bind host must be an IP address: {host}")

        if ip.is_loopback:
            return

        try:
            tailscale_net = ipaddress.ip_network(tailscale_cidr)
        except ValueError:
            raise ValueError("Invalid tailscale CIDR")

        if ip not in tailscale_net:
            raise ValueError("RPC bind host must be loopback or Tailscale address")
    
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
                "tls_server": self.tls_server.is_running if self.tls_server else None,
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

        rpc_transport = self.config.get("rpc", {}).get("transport", "unix")
        if rpc_transport == "tls":
            if not self.tls_server:
                raise RuntimeError("TLS transport requested but TLS server not configured")
            await self.tls_server.start()
            if self.allow_hmac_fallback:
                await self.socket_server.start()
        else:
            if not self.allow_hmac_fallback:
                raise RuntimeError("HMAC fallback disabled without TLS transport")
            await self.socket_server.start()

        # Start components
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
        if self.tls_server:
            await self.tls_server.stop()
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
