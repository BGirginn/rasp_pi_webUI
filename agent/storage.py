"""Linux removable-storage discovery and safety helpers."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


LSBLK_COLUMNS = (
    "NAME,KNAME,PATH,TYPE,SIZE,MODEL,VENDOR,SERIAL,TRAN,RM,RO,HOTPLUG,"
    "FSTYPE,FSVER,LABEL,UUID,MOUNTPOINTS,FSAVAIL,FSUSED,FSUSE%,PKNAME,MAJ:MIN"
)


class StorageSafetyError(ValueError):
    """Raised when a block-device operation is not safe."""


def _run(command: List[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


def _as_bool(value: Any) -> bool:
    return str(value).lower() in {"1", "true", "yes"}


def _as_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _mount_points(node: Dict[str, Any]) -> List[str]:
    values = node.get("mountpoints")
    if not isinstance(values, list):
        values = [node.get("mountpoint")]
    return [str(value) for value in values if value]


def _fingerprint(node: Dict[str, Any]) -> str:
    identity = "|".join(
        str(node.get(key) or "")
        for key in ("path", "maj:min", "serial", "size", "model")
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


def _volume(node: Dict[str, Any]) -> Dict[str, Any]:
    mounts = _mount_points(node)
    return {
        "id": str(node.get("kname") or node.get("name") or ""),
        "name": str(node.get("name") or ""),
        "path": str(node.get("path") or ""),
        "type": str(node.get("type") or ""),
        "size_bytes": _as_int(node.get("size")),
        "filesystem": node.get("fstype"),
        "filesystem_version": node.get("fsver"),
        "label": node.get("label"),
        "uuid": node.get("uuid"),
        "read_only": _as_bool(node.get("ro")),
        "mount_points": mounts,
        "mounted": bool(mounts),
        "available_bytes": _as_int(node.get("fsavail")),
        "used_bytes": _as_int(node.get("fsused")),
        "used_percent": node.get("fsuse%"),
    }


def _flatten_volumes(nodes: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    volumes: List[Dict[str, Any]] = []
    for node in nodes:
        if node.get("type") in {"part", "crypt", "lvm"}:
            volumes.append(_volume(node))
        volumes.extend(_flatten_volumes(node.get("children") or []))
    return volumes


def discover_block_devices() -> List[Dict[str, Any]]:
    """Return normalized block disks from lsblk."""
    result = _run(["lsblk", "-J", "-b", "-o", LSBLK_COLUMNS], timeout=15)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "lsblk failed")
    nodes = json.loads(result.stdout or "{}").get("blockdevices") or []
    devices: List[Dict[str, Any]] = []
    for node in nodes:
        if node.get("type") != "disk":
            continue
        volumes = _flatten_volumes(node.get("children") or [])
        if node.get("fstype") or _mount_points(node):
            volumes.insert(0, _volume(node))
        mount_points = [
            point
            for volume in volumes
            for point in volume.get("mount_points") or []
        ]
        devices.append(
            {
                "id": str(node.get("kname") or node.get("name") or ""),
                "name": str(node.get("name") or ""),
                "device_path": str(node.get("path") or ""),
                "major_minor": node.get("maj:min"),
                "transport": node.get("tran"),
                "removable": _as_bool(node.get("rm")),
                "hotplug": _as_bool(node.get("hotplug")),
                "read_only": _as_bool(node.get("ro")),
                "size_bytes": _as_int(node.get("size")),
                "model": (node.get("model") or "").strip() or None,
                "vendor": (node.get("vendor") or "").strip() or None,
                "serial": (node.get("serial") or "").strip() or None,
                "mount_points": mount_points,
                "mounted": bool(mount_points),
                "partitions": volumes,
                "fingerprint": _fingerprint(node),
            }
        )
    return devices


def discover_usb_storage() -> List[Dict[str, Any]]:
    return [
        device
        for device in discover_block_devices()
        if device.get("transport") == "usb"
    ]


def get_safe_usb_device(device_path: str, fingerprint: str) -> Dict[str, Any]:
    """Resolve a client-selected disk and reject system/non-removable devices."""
    if not device_path.startswith("/dev/") or Path(device_path).name != device_path[5:]:
        raise StorageSafetyError("Invalid block device path")

    target = next(
        (item for item in discover_block_devices() if item["device_path"] == device_path),
        None,
    )
    if not target:
        raise StorageSafetyError("Block device is no longer present")
    if target["fingerprint"] != fingerprint:
        raise StorageSafetyError("Device identity changed; refresh and try again")
    if target.get("transport") != "usb" or not target.get("removable"):
        raise StorageSafetyError("Only removable USB disks are supported")
    if target.get("read_only"):
        raise StorageSafetyError("The USB disk is hardware read-only")

    protected_sources = set()
    for mount in ("/", "/boot", "/boot/firmware"):
        result = _run(["findmnt", "-n", "-o", "SOURCE", "--target", mount], timeout=5)
        if result.returncode == 0 and result.stdout.strip().startswith("/dev/"):
            protected_sources.add(os.path.realpath(result.stdout.strip()))
    target_path = os.path.realpath(target["device_path"])
    if any(source == target_path or source.startswith(target_path) for source in protected_sources):
        raise StorageSafetyError("System boot/root disk cannot be modified")

    swaps = Path("/proc/swaps")
    if swaps.exists():
        for line in swaps.read_text(encoding="utf-8").splitlines()[1:]:
            source = line.split()[0] if line.split() else ""
            if source and os.path.realpath(source).startswith(target_path):
                raise StorageSafetyError("Active swap disk cannot be modified")
    return target


def resolve_volume(device: Dict[str, Any], volume_id: Optional[str]) -> Dict[str, Any]:
    volumes = device.get("partitions") or []
    if volume_id:
        volume = next((item for item in volumes if item["id"] == volume_id), None)
    elif len(volumes) == 1:
        volume = volumes[0]
    else:
        volume = None
    if not volume:
        raise StorageSafetyError("Select a valid USB volume")
    if not str(volume.get("path") or "").startswith(device["device_path"]):
        raise StorageSafetyError("Volume does not belong to the selected USB disk")
    return volume


def unmount_device(device: Dict[str, Any]) -> List[str]:
    unmounted: List[str] = []
    volumes = sorted(
        device.get("partitions") or [],
        key=lambda item: len(str(item.get("path") or "")),
        reverse=True,
    )
    for volume in volumes:
        for mount_point in volume.get("mount_points") or []:
            if shutil.which("udisksctl") and volume.get("path", "").startswith("/dev/"):
                result = _run(
                    ["udisksctl", "unmount", "-b", volume["path"]],
                    timeout=60,
                )
            else:
                result = _run(["umount", "--", mount_point], timeout=30)
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or f"Failed to unmount {mount_point}")
            unmounted.append(mount_point)
    return unmounted


def mount_volume(volume_path: str, read_only: bool = False) -> str:
    if not volume_path.startswith("/dev/"):
        raise StorageSafetyError("Invalid volume path")
    command = ["udisksctl", "mount", "-b", volume_path]
    if read_only:
        command.extend(["-o", "ro"])
    result = _run(command, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Mount failed")
    refreshed = next(
        (
            volume
            for device in discover_block_devices()
            for volume in device.get("partitions") or []
            if volume.get("path") == volume_path
        ),
        None,
    )
    mounts = refreshed.get("mount_points") if refreshed else []
    if not mounts:
        raise RuntimeError("Volume mounted but no mount point was reported")
    return mounts[0]


def power_off_device(device: Dict[str, Any]) -> None:
    if shutil.which("udisksctl"):
        result = _run(["udisksctl", "power-off", "-b", device["device_path"]], timeout=60)
        if result.returncode == 0:
            return
        if "not supported" not in result.stderr.lower():
            raise RuntimeError(result.stderr.strip() or "USB power-off failed")
    result = _run(["eject", device["device_path"]], timeout=30)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "USB eject failed")
