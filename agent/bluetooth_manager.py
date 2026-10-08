"""BlueZ Bluetooth management through its command-line D-Bus client."""

import asyncio
import re
from typing import Dict, List, Tuple


MAC_RE = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


class BluetoothManager:
    async def _run(self, *args: str, timeout: int = 20) -> Tuple[int, str]:
        try:
            process = await asyncio.create_subprocess_exec(
                "bluetoothctl",
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("bluetoothctl is not installed") from exc

        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            raise RuntimeError("Bluetooth operation timed out")
        return process.returncode or 0, stdout.decode("utf-8", errors="replace").strip()

    @staticmethod
    def _parse_devices(output: str) -> List[Dict]:
        devices = []
        for line in output.splitlines():
            match = re.match(r"^Device\s+((?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})\s*(.*)$", line.strip())
            if match:
                devices.append({"address": match.group(1).upper(), "name": match.group(2) or "Unknown"})
        return devices

    @staticmethod
    def _properties(output: str) -> Dict[str, str]:
        properties: Dict[str, str] = {}
        for line in output.splitlines():
            line = line.strip()
            if ": " in line:
                key, value = line.split(": ", 1)
                properties[key.lower()] = value
        return properties

    @staticmethod
    def _validate_address(address: str) -> str:
        if not MAC_RE.fullmatch(address or ""):
            raise ValueError("Invalid Bluetooth device address")
        return address.upper()

    async def status(self) -> Dict:
        rc, output = await self._run("show")
        if rc != 0 or "Controller " not in output:
            raise RuntimeError(output or "No Bluetooth controller found")
        props = self._properties(output)

        rc, paired_output = await self._run("devices", "Paired")
        if rc != 0:
            rc, paired_output = await self._run("paired-devices")
        paired = self._parse_devices(paired_output) if rc == 0 else []
        for device in paired:
            info_rc, info = await self._run("info", device["address"])
            if info_rc == 0:
                device_props = self._properties(info)
                device.update({
                    "connected": device_props.get("connected", "no").lower() == "yes",
                    "trusted": device_props.get("trusted", "no").lower() == "yes",
                    "paired": device_props.get("paired", "no").lower() == "yes",
                })
        return {
            "enabled": props.get("powered", "no").lower() == "yes",
            "discoverable": props.get("discoverable", "no").lower() == "yes",
            "pairable": props.get("pairable", "no").lower() == "yes",
            "controller": props.get("controller") or output.splitlines()[0].split()[1],
            "paired_devices": paired,
        }

    async def scan(self, seconds: int = 8) -> Dict:
        seconds = max(2, min(int(seconds), 30))
        rc, output = await self._run("--timeout", str(seconds), "scan", "on", timeout=seconds + 5)
        if rc != 0:
            return {"success": False, "message": output or "Bluetooth scan failed", "error": output}
        list_rc, device_output = await self._run("devices")
        if list_rc != 0:
            return {"success": False, "message": device_output or "Could not list Bluetooth devices", "error": device_output}
        return {"success": True, "message": "Bluetooth scan completed", "data": {"devices": self._parse_devices(device_output)}}

    async def power(self, enabled: bool) -> Dict:
        return await self._action("power", "on" if enabled else "off")

    async def pair(self, address: str) -> Dict:
        return await self._action("pair", self._validate_address(address), timeout=45)

    async def trust(self, address: str) -> Dict:
        return await self._action("trust", self._validate_address(address))

    async def connect(self, address: str) -> Dict:
        return await self._action("connect", self._validate_address(address), timeout=30)

    async def disconnect(self, address: str) -> Dict:
        return await self._action("disconnect", self._validate_address(address))

    async def remove(self, address: str) -> Dict:
        return await self._action("remove", self._validate_address(address))

    async def _action(self, *args: str, timeout: int = 20) -> Dict:
        rc, output = await self._run(*args, timeout=timeout)
        success = rc == 0 and "failed" not in output.lower()
        return {
            "success": success,
            "message": output or ("Bluetooth operation completed" if success else "Bluetooth operation failed"),
            "error": None if success else output,
        }
