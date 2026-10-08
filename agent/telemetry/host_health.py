"""Observed host power rails and public HTTPS reachability, without estimates."""

import asyncio
import math
import re
import subprocess
import time

import httpx
import psutil
import structlog

logger = structlog.get_logger(__name__)
_ADC_LINE = re.compile(
    r"^\s*([A-Z0-9_]+)_([AV])\s+(current|volt)\(\d+\)=([0-9.]+)([AV])\s*$"
)
_PROBES = (
    ("https://www.gstatic.com/generate_204", 204),
    ("https://www.cloudflare.com/cdn-cgi/trace", 200),
)


def parse_pmic_readings(output: str) -> dict[str, float]:
    """Keep each rail separate; PMIC currents do not measure total 5 V input."""
    metrics = {}
    for line in output.splitlines():
        match = _ADC_LINE.fullmatch(line)
        if not match:
            continue
        rail, suffix, kind, raw, unit = match.groups()
        if (suffix, kind, unit) not in (("A", "current", "A"), ("V", "volt", "V")):
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        if not math.isfinite(value) or value < 0:
            continue
        measurement = "current_a" if suffix == "A" else "voltage_v"
        metrics[f"host.power.pmic.{rail.lower()}.{measurement}"] = value
        if rail == "EXT5V" and suffix == "V":
            metrics["host.power.input_voltage_v"] = value
    return metrics


def read_pmic_metrics() -> dict[str, float]:
    try:
        result = subprocess.run(
            ["/usr/bin/vcgencmd", "pmic_read_adc"],
            capture_output=True,
            text=True,
            timeout=3,
            check=True,
        )
    except FileNotFoundError:
        return {"host.power.pmic.available": 0.0}
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("PMIC measurement unavailable", error=type(exc).__name__)
        return {"host.power.pmic.available": 0.0}
    metrics = parse_pmic_readings(result.stdout)
    metrics["host.power.pmic.available"] = float(bool(metrics))
    return metrics


async def probe_internet() -> dict[str, float]:
    """1 means at least one fixed public HTTPS endpoint responded as expected."""
    async with httpx.AsyncClient(
        timeout=2, follow_redirects=False, trust_env=False
    ) as client:
        for url, status in _PROBES:
            started = time.monotonic()
            try:
                response = await asyncio.wait_for(client.get(url), timeout=2.5)
            except (httpx.HTTPError, asyncio.TimeoutError):
                continue
            if response.status_code == status and (
                status == 204 or "ip=" in response.text
            ):
                return {
                    "host.net.internet_connected": 1.0,
                    "host.net.internet_latency_ms": (time.monotonic() - started) * 1000,
                }
    return {"host.net.internet_connected": 0.0}


class HostHealthCollector:
    """Share bounded probes between periodic persistence and current requests."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._metrics: dict[str, float] = {}
        self._expires_at = 0.0

    async def collect(self) -> dict[str, float]:
        async with self._lock:
            if time.monotonic() < self._expires_at:
                return dict(self._metrics)
            internet, power = await asyncio.gather(
                probe_internet(), asyncio.to_thread(read_pmic_metrics)
            )
            self._metrics = {
                **internet,
                **power,
                "host.power.on": 1.0,
                "host.boot.timestamp": psutil.boot_time(),
            }
            self._expires_at = time.monotonic() + 5
            return dict(self._metrics)


host_health_collector = HostHealthCollector()
