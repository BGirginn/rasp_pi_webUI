#!/usr/bin/env python3
"""Destructive USB engine acceptance test using an isolated loop disk."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def checked(*command: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        command,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"{command[0]} failed")
    return result.stdout.strip()


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("This acceptance test must run as root")

    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo / "agent"))
    from jobs import handlers
    from jobs.handlers import UsbFormatJobHandler, UsbWriteTestJobHandler
    from jobs.runner import Job

    with tempfile.TemporaryDirectory(prefix="pi-control-usb-loop-") as temp_name:
        temp = Path(temp_name)
        image = temp / "usb.img"
        checked("truncate", "-s", "256M", str(image))
        loop = checked("losetup", "--find", "--show", "--partscan", str(image))
        try:
            base_device = {
                "device_path": loop,
                "fingerprint": "loop-acceptance",
                "transport": "usb",
                "removable": True,
                "read_only": False,
                "size_bytes": image.stat().st_size,
                "partitions": [],
            }
            original_safe = handlers.get_safe_usb_device
            try:
                handlers.get_safe_usb_device = lambda *_args: dict(base_device)
                formatter = UsbFormatJobHandler()
                for filesystem in ("exfat", "fat32", "ext4"):
                    job = Job(
                        id=f"fmt-{filesystem}",
                        name=f"Format {filesystem}",
                        type="usb_format",
                        config={
                            "device_id": "loop-usb",
                            "device_path": loop,
                            "fingerprint": "loop-acceptance",
                            "filesystem": filesystem,
                            "label": "PI-TEST",
                            "confirmation": "ERASE loop-usb",
                        },
                    )
                    result = formatter._format(job)
                    detected = checked("blkid", "-s", "TYPE", "-o", "value", result["partition_path"])
                    expected = "vfat" if filesystem == "fat32" else filesystem
                    if detected != expected:
                        raise RuntimeError(f"{filesystem}: expected {expected}, got {detected}")

                partition = f"{loop}p1" if loop[-1].isdigit() else f"{loop}1"
                mount_point = temp / "mount"
                mount_point.mkdir()
                checked("mount", partition, str(mount_point))
                try:
                    write_device = dict(base_device)
                    write_device["partitions"] = [{
                        "id": Path(partition).name,
                        "path": partition,
                        "mount_points": [str(mount_point)],
                        "read_only": False,
                    }]
                    handlers.get_safe_usb_device = lambda *_args: write_device
                    write_job = Job(
                        id="write-loop",
                        name="Write test",
                        type="usb_write_test",
                        config={
                            "device_path": loop,
                            "fingerprint": "loop-acceptance",
                            "volume_id": Path(partition).name,
                            "size_mb": 8,
                        },
                    )
                    write_result = UsbWriteTestJobHandler()._write_test(write_job)
                    if write_result["bytes_tested"] != 8 * 1024 * 1024:
                        raise RuntimeError("Unexpected write-test byte count")
                finally:
                    checked("umount", str(mount_point))
            finally:
                handlers.get_safe_usb_device = original_safe
        finally:
            subprocess.run(["losetup", "--detach", loop], capture_output=True, timeout=30)

    print("USB loop acceptance passed: exFAT, FAT32, ext4, checksum write/read/cleanup")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
