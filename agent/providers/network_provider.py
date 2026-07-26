"""
Pi Agent - Network Provider (nmcli based)

Discovers and manages network interfaces (eth, wifi, bluetooth).
"""

import asyncio
import socket
import subprocess
from typing import Dict, List, Optional

import psutil
import structlog

from .base import BaseProvider, Resource, ResourceClass, ResourceState, ActionResult

logger = structlog.get_logger(__name__)


class NetworkProvider(BaseProvider):
    """Provider for network interfaces using NetworkManager (nmcli)."""

    def __init__(self, config: dict):
        super().__init__(config)
        self._rollback_tasks: Dict[str, asyncio.Task] = {}
        self._checkpoints: Dict[str, str] = {}
    
    @property
    def name(self) -> str:
        return "network"
    
    async def start(self) -> None:
        """Initialize network provider."""
        self._is_healthy = True
        logger.info("Network provider initialized (nmcli)")
    
    async def stop(self) -> None:
        """Cleanup network provider."""
        for task in self._rollback_tasks.values():
            task.cancel()
        self._rollback_tasks.clear()
    
    async def discover(self) -> List[Resource]:
        """Discover network interfaces."""
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        counters = psutil.net_io_counters(pernic=True)
        gateways = await self._default_gateways()
        resources: List[Resource] = []
        for name, addresses in addrs.items():
            if name == "lo":
                continue
            ip = mac = netmask = None
            for address in addresses:
                if address.family == socket.AF_INET:
                    ip, netmask = address.address, address.netmask
                elif address.family == psutil.AF_LINK:
                    mac = address.address
            interface_stats = stats.get(name)
            io = counters.get(name)
            interface_type = self._interface_type(name)
            is_up = bool(interface_stats and interface_stats.isup)
            resource = Resource(
                id=name,
                name=name,
                type="interface",
                provider=self.name,
                resource_class=ResourceClass.SYSTEM,
                state=ResourceState.RUNNING if is_up else ResourceState.STOPPED,
                capabilities=["enable", "disable", "restart"],
                metadata={
                    "interface_type": interface_type,
                    "status": "up" if is_up else "down",
                    "mac": mac,
                    "ip": ip,
                    "subnet_mask": netmask,
                    "gateway": gateways.get(name),
                    "rx_bytes": io.bytes_recv if io else 0,
                    "tx_bytes": io.bytes_sent if io else 0,
                    "speed_mbps": interface_stats.speed if interface_stats and interface_stats.speed > 0 else None,
                },
            )
            resources.append(resource)
            self._resources[name] = resource
        logger.debug("Network discovery complete", interfaces=len(resources))
        return resources

    async def _default_gateways(self) -> Dict[str, str]:
        process = await asyncio.create_subprocess_exec(
            "ip", "route", "show", "default",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate()
        gateways: Dict[str, str] = {}
        if process.returncode == 0:
            for line in stdout.decode().splitlines():
                parts = line.split()
                if "dev" in parts and "via" in parts:
                    gateways[parts[parts.index("dev") + 1]] = parts[parts.index("via") + 1]
        return gateways

    @staticmethod
    def _interface_type(name: str) -> str:
        if name.startswith(("wl", "wlan")):
            return "wifi"
        if name.startswith("tailscale"):
            return "vpn"
        if name.startswith(("br-", "docker", "virbr")):
            return "bridge"
        if name.startswith(("veth", "tun", "tap")):
            return "virtual"
        return "ethernet"
    
    async def get_resource(self, resource_id: str) -> Optional[Resource]:
        """Get a specific interface."""
        return self._resources.get(resource_id)
    
    async def execute_action(
        self,
        resource_id: str,
        action: str,
        params: Optional[Dict] = None
    ) -> ActionResult:
        """Execute an action on a network interface."""
        params = params or {}
        
        # WiFi-specific actions
        if action == "scan" and resource_id.startswith("wlan"):
            return await self._scan_wifi(resource_id)
        elif action == "enable":
            self._cancel_rollback(resource_id)
            # If it's a wifi interface, enable wifi radio
            if resource_id.startswith("wlan"):
                return await self._enable_wifi()
            else:
                 return await self._enable_interface(resource_id)
        elif action == "disable":
            # If it's a wifi interface, disable wifi radio
            if resource_id.startswith("wlan"):
                return await self._disable_wifi(params.get("rollback_seconds", 0))
            else:
                return await self._disable_interface(
                    resource_id, params.get("rollback_seconds", 0)
                )
        elif action == "restart":
            return await self._restart_interface(resource_id)
        elif action == "status":
            return await self._get_wifi_status()
        elif action == "connect":
            return await self._connect_wifi(params.get("ssid"), params.get("password"), params.get("hidden", False))
        elif action == "disconnect":
            return await self._disconnect_wifi()
        elif action == "checkpoint_confirm":
            return await self.confirm_checkpoint(params.get("checkpoint_id", ""))
        elif action == "checkpoint_rollback":
            return await self.rollback_checkpoint(params.get("checkpoint_id", ""))
            
        return ActionResult(
            success=False,
            message=f"Action '{action}' not implemented for {resource_id}",
            error="NOT_IMPLEMENTED"
        )

    def _cancel_rollback(self, resource_id: str) -> None:
        task = self._rollback_tasks.pop(resource_id, None)
        if task and task is not asyncio.current_task():
            task.cancel()

    def _schedule_rollback(self, resource_id: str, delay: int, enable_callback) -> None:
        if delay <= 0:
            return
        self._cancel_rollback(resource_id)

        async def restore() -> None:
            try:
                await asyncio.sleep(delay)
                await enable_callback()
            except asyncio.CancelledError:
                raise
            finally:
                if self._rollback_tasks.get(resource_id) is asyncio.current_task():
                    self._rollback_tasks.pop(resource_id, None)

        self._rollback_tasks[resource_id] = asyncio.create_task(restore())

    async def _run_nmcli(self, args: List[str]) -> tuple:
        """Helper to run nmcli commands."""
        cmd = ["nmcli"] + args
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode("utf-8"), stderr.decode("utf-8")

    async def _enable_wifi(self) -> ActionResult:
        """Enable WiFi radio."""
        try:
            rc, out, err = await self._run_nmcli(["radio", "wifi", "on"])
            if rc != 0:
                return ActionResult(False, f"Failed to enable WiFi: {err}", error=err)
            logger.info("WiFi enabled")
            return ActionResult(True, "WiFi enabled")
        except Exception as e:
            return ActionResult(False, str(e), error=str(e))

    async def _disable_wifi(self, rollback_seconds: int = 0) -> ActionResult:
        """Disable WiFi radio."""
        try:
            checkpoint = await self._create_checkpoint(["wlan0"], rollback_seconds)
            rc, out, err = await self._run_nmcli(["radio", "wifi", "off"])
            if rc != 0:
                await self.rollback_checkpoint(checkpoint)
                return ActionResult(False, f"Failed to disable WiFi: {err}", error=err)
            # NetworkManager checkpoints restore device connectivity. Keep the
            # radio timer as a second guard because radio state is host-global.
            self._schedule_rollback("wlan0", rollback_seconds, self._enable_wifi)
            logger.info("WiFi disabled")
            return ActionResult(
                True,
                "WiFi disabled",
                data={
                    "rollback_seconds": rollback_seconds,
                    "checkpoint_id": checkpoint,
                },
            )
        except Exception as e:
            return ActionResult(False, str(e), error=str(e))

    async def _enable_interface(self, interface: str) -> ActionResult:
        """Enable a network interface."""
        try:
            rc, out, err = await self._run_nmcli(["device", "connect", interface])
            if rc != 0:
                return ActionResult(False, f"Failed to enable interface {interface}: {err}", error=err)
            logger.info("Interface enabled", interface=interface)
            return ActionResult(True, f"Interface {interface} enabled")
        except Exception as e:
            return ActionResult(False, str(e), error=str(e))

    async def _disable_interface(self, interface: str, rollback_seconds: int = 0) -> ActionResult:
        """Disable a network interface."""
        try:
            checkpoint = await self._create_checkpoint([interface], rollback_seconds)
            rc, out, err = await self._run_nmcli(["device", "disconnect", interface])
            if rc != 0:
                await self.rollback_checkpoint(checkpoint)
                return ActionResult(False, f"Failed to disable interface {interface}: {err}", error=err)
            logger.info("Interface disabled", interface=interface)
            return ActionResult(
                True,
                f"Interface {interface} disabled",
                data={"rollback_seconds": rollback_seconds, "checkpoint_id": checkpoint},
            )
        except Exception as e:
            return ActionResult(False, str(e), error=str(e))

    async def _restart_interface(self, interface: str) -> ActionResult:
        """Reconnect an interface and report failures instead of false success."""
        try:
            checkpoint = await self._create_checkpoint([interface], 60)
            rc, _, err = await self._run_nmcli(["device", "disconnect", interface])
            if rc != 0:
                await self.rollback_checkpoint(checkpoint)
                return ActionResult(False, f"Failed to disconnect {interface}: {err}", error=err)
            await asyncio.sleep(1)
            rc, _, err = await self._run_nmcli(["device", "connect", interface])
            if rc != 0:
                await self.rollback_checkpoint(checkpoint)
                return ActionResult(False, f"Failed to reconnect {interface}: {err}", error=err)
            await self.confirm_checkpoint(checkpoint)
            return ActionResult(True, f"Interface {interface} restarted")
        except Exception as e:
            return ActionResult(False, str(e), error=str(e))

    async def _get_wifi_status(self) -> ActionResult:
        """Get WiFi status including current connection."""
        try:
            # Check radio status
            rc, out, _ = await self._run_nmcli(["radio", "wifi"])
            radio_enabled = out.strip().lower() == "enabled"
            
            # Get active connection
            rc2, out2, _ = await self._run_nmcli(["-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"])
            
            connected = False
            ssid = None
            ip = None
            signal_quality = None
            frequency = None
            
            for line in out2.strip().split("\n"):
                parts = line.split(":")
                if len(parts) >= 4 and parts[0].startswith("wlan"):
                    if parts[2] == "connected":
                        connected = True
                        ssid = parts[3]
                        # Get IP
                        rc3, out3, _ = await self._run_nmcli(["-t", "-f", "IP4.ADDRESS", "device", "show", parts[0]])
                        for ipline in out3.strip().split("\n"):
                            if ipline.startswith("IP4.ADDRESS"):
                                ip = ipline.split(":")[1].split("/")[0] if ":" in ipline else None
                        rc4, out4, _ = await self._run_nmcli([
                            "-t", "-f", "IN-USE,SIGNAL,FREQ",
                            "device", "wifi", "list", "ifname", parts[0],
                        ])
                        if rc4 == 0:
                            for wifi_line in out4.strip().split("\n"):
                                wifi_parts = wifi_line.split(":")
                                if len(wifi_parts) >= 3 and wifi_parts[0] == "*":
                                    signal_quality = (
                                        int(wifi_parts[1])
                                        if wifi_parts[1].isdigit()
                                        else None
                                    )
                                    raw_frequency = wifi_parts[2].strip()
                                    frequency = (
                                        raw_frequency
                                        if raw_frequency.lower().endswith("mhz")
                                        else f"{raw_frequency} MHz"
                                    ) if raw_frequency else None
                                    break
                        break
            
            return ActionResult(True, "Status retrieved", data={
                "radio_enabled": radio_enabled,
                "connected": connected,
                "ssid": ssid,
                "ip": ip,
                "ip_address": ip,
                "signal_quality": signal_quality,
                "frequency": frequency,
            })
        except Exception as e:
            return ActionResult(False, str(e), error=str(e))

    async def _connect_wifi(self, ssid: str, password: Optional[str], hidden: bool = False) -> ActionResult:
        """Connect to a WiFi network."""
        if not ssid:
            return ActionResult(False, "SSID is required", error="MISSING_SSID")
        
        try:
            # Check if connection profile exists
            rc, out, _ = await self._run_nmcli(["-t", "-f", "NAME", "connection", "show"])
            profiles = [p.strip() for p in out.strip().split("\n") if p.strip()]
            
            # If profile exists and password is provided, delete old profile to allow new credentials
            if ssid in profiles and password:
                logger.info("Deleting old profile to apply new credentials", ssid=ssid)
                await self._run_nmcli(["connection", "delete", ssid])
            elif ssid in profiles:
                # Profile exists and no new password, just activate
                rc, out, err = await self._run_nmcli(["connection", "up", ssid])
                if rc != 0:
                    return ActionResult(False, f"Activation failed: {err}", error=err)
                logger.info("WiFi activated from existing profile", ssid=ssid)
                return ActionResult(True, f"Connected to {ssid}")
            
            # Create new connection using device wifi connect
            args = ["device", "wifi", "connect", ssid]
            if password:
                args += ["password", password]
            if hidden:
                args += ["hidden", "yes"]
            rc, out, err = await self._run_nmcli(args)
            
            if rc != 0:
                return ActionResult(False, f"Connection failed: {err}", error=err)
            
            logger.info("WiFi connected", ssid=ssid)
            return ActionResult(True, f"Connected to {ssid}")
        except Exception as e:
            return ActionResult(False, str(e), error=str(e))

    async def _disconnect_wifi(self) -> ActionResult:
        """Disconnect from current WiFi."""
        try:
            # Find active WiFi device
            rc, out, _ = await self._run_nmcli(["-t", "-f", "DEVICE,TYPE,STATE", "device", "status"])
            
            wlan_device = None
            for line in out.strip().split("\n"):
                parts = line.split(":")
                if len(parts) >= 3 and parts[1] == "wifi" and parts[2] == "connected":
                    wlan_device = parts[0]
                    break
            
            if not wlan_device:
                return ActionResult(True, "No active WiFi connection")
            
            rc, out, err = await self._run_nmcli(["device", "disconnect", wlan_device])
            if rc != 0:
                return ActionResult(False, f"Disconnect failed: {err}", error=err)
            
            logger.info("WiFi disconnected", device=wlan_device)
            return ActionResult(True, "WiFi disconnected")
        except Exception as e:
            return ActionResult(False, str(e), error=str(e))

    async def _create_checkpoint(self, interfaces: List[str], timeout: int) -> str:
        if timeout <= 0:
            raise ValueError("A positive rollback timeout is required")

        def create() -> str:
            import dbus

            bus = dbus.SystemBus()
            manager_object = bus.get_object("org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager")
            manager = dbus.Interface(manager_object, "org.freedesktop.NetworkManager")
            device_paths = []
            for interface in interfaces:
                result = subprocess.run(
                    ["nmcli", "-g", "GENERAL.DBUS-PATH", "device", "show", interface],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                if result.returncode != 0 or not result.stdout.strip():
                    raise RuntimeError(f"NetworkManager device not found: {interface}")
                device_paths.append(dbus.ObjectPath(result.stdout.strip()))
            return str(manager.CheckpointCreate(device_paths, int(timeout), 1))

        checkpoint = await asyncio.to_thread(create)
        self._checkpoints[checkpoint] = checkpoint
        return checkpoint

    async def confirm_checkpoint(self, checkpoint_id: str) -> ActionResult:
        return await self._checkpoint_action(checkpoint_id, rollback=False)

    async def rollback_checkpoint(self, checkpoint_id: str) -> ActionResult:
        return await self._checkpoint_action(checkpoint_id, rollback=True)

    async def _checkpoint_action(self, checkpoint_id: str, rollback: bool) -> ActionResult:
        if not checkpoint_id or not checkpoint_id.startswith("/org/freedesktop/NetworkManager/Checkpoint/"):
            return ActionResult(False, "Invalid checkpoint", error="INVALID_CHECKPOINT")

        def apply() -> None:
            import dbus

            bus = dbus.SystemBus()
            obj = bus.get_object("org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager")
            manager = dbus.Interface(obj, "org.freedesktop.NetworkManager")
            if rollback:
                manager.CheckpointRollback(dbus.ObjectPath(checkpoint_id))
            else:
                manager.CheckpointDestroy(dbus.ObjectPath(checkpoint_id))

        try:
            await asyncio.to_thread(apply)
            self._checkpoints.pop(checkpoint_id, None)
            action = "rolled back" if rollback else "confirmed"
            return ActionResult(True, f"Network checkpoint {action}")
        except Exception as exc:
            return ActionResult(False, str(exc), error=str(exc))
        
    async def _scan_wifi(self, interface: str) -> ActionResult:
        """Scan for WiFi networks using nmcli."""
        try:
            # nmcli -t -f SSID,BSSID,SIGNAL,BARS,SECURITY,CHAN,FREQ device wifi list
            cmd = ["nmcli", "-t", "-f", "SSID,BSSID,SIGNAL,BARS,SECURITY,CHAN,FREQ", "device", "wifi", "list"]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                err_msg = stderr.decode().strip()
                logger.error("nmcli scan failed", error=err_msg)
                return ActionResult(False, "WiFi scan failed", error=err_msg)
            
            networks = []
            output = stdout.decode("utf-8")
            
            for line in output.split("\n"):
                if not line.strip():
                    continue
                
                clean_line = line.replace("\\:", "__COLON__")
                parts = clean_line.split(":")
                
                if len(parts) < 7:
                    continue
                    
                parts = [p.replace("__COLON__", ":") for p in parts]
                
                ssid = parts[0]
                bssid = parts[1]
                try:
                    signal = int(parts[2])
                except:
                    signal = 0
                
                quality = signal
                dbm = (quality / 2) - 100
                
                networks.append({
                    "ssid": ssid,
                    "bssid": bssid,
                    "signal_strength": int(dbm),
                    "signal_quality": quality,
                    "channel": int(parts[5]) if parts[5].isdigit() else 0,
                    "frequency": parts[6],
                    "security": parts[4],
                    "connected": False
                })

            return ActionResult(True, "Scan completed", data={"networks": networks})
            
        except Exception as e:
            logger.exception("WiFi scan exception", error=str(e))
            return ActionResult(False, f"Scan failed: {str(e)}", error=str(e))
