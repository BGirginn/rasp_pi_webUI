"""
Pi Agent - Systemd Provider

Discovers and manages systemd services.
"""

import asyncio
import subprocess
from datetime import datetime
from typing import Dict, List, Optional

import structlog

from .base import BaseProvider, Resource, ResourceClass, ResourceState, ActionResult

logger = structlog.get_logger(__name__)


class SystemdProvider(BaseProvider):
    """Provider for systemd services."""
    
    def __init__(self, config: dict):
        super().__init__(config)
    
    @property
    def name(self) -> str:
        return "systemd"
    
    async def start(self) -> None:
        """Initialize systemd provider."""
        # Check if systemctl is available
        try:
            result = await self._run_command(["systemctl", "--version"])
            if result["returncode"] == 0:
                self._is_healthy = True
                logger.info("Systemd provider initialized")
            else:
                self._is_healthy = False
                logger.warning("systemctl not available")
        except Exception as e:
            self._is_healthy = False
            logger.error("Failed to initialize systemd provider", error=str(e))
    
    async def stop(self) -> None:
        """Cleanup systemd provider."""
        pass
    
    async def _run_command(self, cmd: List[str]) -> Dict:
        """Run a shell command asynchronously."""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            return {
                "returncode": process.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            }
        except Exception as e:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
            }
    
    async def discover(self) -> List[Resource]:
        """Discover systemd services."""
        if not self._is_healthy:
            return []
        
        resources = []
        
        try:
            # List all services
            result = await self._run_command([
                "systemctl", "list-units",
                "--type=service",
                "--all",
                "--no-pager",
                "--no-legend",
                "--plain"
            ])
            
            if result["returncode"] != 0:
                logger.error("Failed to list services", stderr=result["stderr"])
                return []
            
            # Parse output
            for line in result["stdout"].strip().split("\n"):
                if not line.strip():
                    continue
                
                parts = line.split()
                if len(parts) < 4:
                    continue
                
                unit_name = parts[0]
                load_state = parts[1]
                active_state = parts[2]
                sub_state = parts[3]
                
                # Skip template units
                if "@" in unit_name and not unit_name.endswith(".service"):
                    continue
                
                resource = self._parse_service(unit_name, load_state, active_state, sub_state)
                if resource:
                    resources.append(resource)
                    self._resources[resource.id] = resource
            
            logger.debug("Systemd discovery complete", services=len(resources))
            
        except Exception as e:
            logger.error("Systemd discovery failed", error=str(e))
        
        return resources
    
    def _parse_service(
        self,
        unit_name: str,
        load_state: str,
        active_state: str,
        sub_state: str
    ) -> Optional[Resource]:
        """Parse service info into Resource."""
        # Determine state
        state_map = {
            ("active", "running"): ResourceState.RUNNING,
            ("active", "exited"): ResourceState.STOPPED,
            ("inactive", "dead"): ResourceState.STOPPED,
            ("failed", "failed"): ResourceState.FAILED,
            ("activating", "start"): ResourceState.STARTING,
            ("deactivating", "stop"): ResourceState.STOPPING,
            ("reloading", "reload"): ResourceState.RESTARTING,
        }
        state = state_map.get((active_state, sub_state), ResourceState.UNKNOWN)
        
        # Clean service name
        service_name = unit_name.replace(".service", "")
        
        # Classify resource
        resource_class = self.classify_resource(unit_name)
        
        return Resource(
            id=unit_name,
            name=service_name,
            type="service",
            provider=self.name,
            resource_class=resource_class,
            state=state,
            last_seen=datetime.utcnow(),
            metadata={
                "load_state": load_state,
                "active_state": active_state,
                "sub_state": sub_state,
            }
        )
    
    async def get_resource(self, resource_id: str) -> Optional[Resource]:
        """Get a specific service."""
        result = await self._run_command([
            "systemctl", "show", resource_id,
            "--property=LoadState,ActiveState,SubState,Description"
        ])
        
        if result["returncode"] != 0:
            return None
        
        # Parse properties
        props = {}
        for line in result["stdout"].strip().split("\n"):
            if "=" in line:
                key, value = line.split("=", 1)
                props[key] = value
        
        return self._parse_service(
            resource_id,
            props.get("LoadState", "unknown"),
            props.get("ActiveState", "unknown"),
            props.get("SubState", "unknown")
        )
    
    async def execute_action(
        self,
        resource_id: str,
        action: str,
        params: Optional[Dict] = None
    ) -> ActionResult:
        """Execute an action on a service."""
        resource = self._resources.get(resource_id)
        
        # Check CORE protection
        if resource and resource.resource_class == ResourceClass.CORE:
            return ActionResult(
                success=False,
                message=f"Cannot modify CORE service: {resource_id}",
                error="PROTECTED_RESOURCE"
            )
        
        # Check if action is allowed for SYSTEM resources
        if resource and resource.resource_class == ResourceClass.SYSTEM:
            if action in ["stop"]:
                return ActionResult(
                    success=False,
                    message=f"Cannot stop SYSTEM service: {resource_id}. Use restart instead.",
                    error="ACTION_NOT_ALLOWED"
                )
        
        # Map actions to systemctl commands
        action_map = {
            "start": "start",
            "stop": "stop",
            "restart": "restart",
            "reload": "reload",
            "enable": "enable",
            "disable": "disable",
        }
        
        systemctl_action = action_map.get(action)
        if not systemctl_action:
            return ActionResult(success=False, message=f"Unknown action: {action}", error="UNKNOWN_ACTION")
        
        # Execute command
        result = await self._run_command(["systemctl", systemctl_action, resource_id])
        
        if result["returncode"] == 0:
            return ActionResult(success=True, message=f"Service {resource_id} {action}ed successfully")
        else:
            return ActionResult(
                success=False,
                message=f"Failed to {action} service: {result['stderr']}",
                error="SYSTEMCTL_ERROR"
            )
    
    async def get_logs(
        self,
        resource_id: str,
        tail: int = 100,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> List[str]:
        """Get service logs from journalctl."""
        cmd = ["journalctl", "-u", resource_id, "-n", str(tail), "--no-pager"]
        
        if since:
            cmd.extend(["--since", since.strftime("%Y-%m-%d %H:%M:%S")])
        if until:
            cmd.extend(["--until", until.strftime("%Y-%m-%d %H:%M:%S")])
        
        result = await self._run_command(cmd)
        
        if result["returncode"] != 0:
            logger.error("Failed to get logs", service=resource_id, error=result["stderr"])
            return []
        
        return result["stdout"].strip().split("\n")
    
    async def get_stats(self, resource_id: str) -> Optional[Dict]:
        """Get service stats (memory, CPU from cgroup)."""
        # Get main PID
        result = await self._run_command([
            "systemctl", "show", resource_id, "--property=MainPID,MemoryCurrent,CPUUsageNSec"
        ])
        
        if result["returncode"] != 0:
            return None
        
        props = {}
        for line in result["stdout"].strip().split("\n"):
            if "=" in line:
                key, value = line.split("=", 1)
                props[key] = value
        
        main_pid = props.get("MainPID", "0")
        memory_bytes = int(props.get("MemoryCurrent", 0) or 0)
        cpu_ns = int(props.get("CPUUsageNSec", 0) or 0)
        
        return {
            "main_pid": int(main_pid) if main_pid.isdigit() else 0,
            "memory_mb": round(memory_bytes / (1024 * 1024), 2),
            "cpu_time_seconds": round(cpu_ns / 1_000_000_000, 2),
        }
