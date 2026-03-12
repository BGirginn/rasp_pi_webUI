"""
Pi Control Panel - Telemetry Tests

Unit tests for telemetry models, query params, and mocked endpoint behavior.
"""

import pytest
import time
from unittest.mock import patch, AsyncMock

import os
os.environ["JWT_SECRET"] = "test-secret-key-for-testing"
os.environ["DATABASE_PATH"] = ":memory:"
os.environ["TELEMETRY_DB_PATH"] = ":memory:"


class TestMetricsQueryBody:
    """Test MetricsQueryBody Pydantic model."""

    def test_step_defaults_to_60(self):
        from routers.telemetry import MetricsQueryBody
        body = MetricsQueryBody(metrics="host.cpu.pct_total")
        assert body.step == 60

    def test_start_end_optional(self):
        from routers.telemetry import MetricsQueryBody
        body = MetricsQueryBody(metrics="host.cpu.pct_total")
        assert body.start is None
        assert body.end is None

    def test_custom_values(self):
        from routers.telemetry import MetricsQueryBody
        now = int(time.time())
        body = MetricsQueryBody(metrics="host.cpu.pct_total,host.mem.pct", start=now - 3600, end=now, step=30)
        assert body.step == 30
        assert body.start == now - 3600
        assert "," in body.metrics


class TestSystemMetricsModel:
    """Test SystemMetrics Pydantic model."""

    def test_all_fields(self):
        from routers.telemetry import SystemMetrics
        m = SystemMetrics(
            cpu_pct=50.0, memory_pct=60.0, memory_used_mb=1024,
            memory_total_mb=2048, disk_pct=70.0, disk_used_gb=10.0,
            disk_total_gb=32.0, temperature_c=45.0, load_1m=1.0,
            load_5m=0.8, load_15m=0.5, network_rx_bytes=1000,
            network_tx_bytes=2000, uptime_seconds=86400,
        )
        assert m.cpu_pct == 50.0
        assert m.memory_pct == 60.0
        assert m.disk_total_gb == 32.0
        assert m.uptime_seconds == 86400

    def test_temperature_optional(self):
        from routers.telemetry import SystemMetrics
        m = SystemMetrics(
            cpu_pct=50.0, memory_pct=60.0, memory_used_mb=1024,
            memory_total_mb=2048, disk_pct=70.0, disk_used_gb=10.0,
            disk_total_gb=32.0, temperature_c=None, load_1m=1.0,
            load_5m=0.8, load_15m=0.5, network_rx_bytes=1000,
            network_tx_bytes=2000, uptime_seconds=86400,
        )
        assert m.temperature_c is None

    def test_zero_values(self):
        from routers.telemetry import SystemMetrics
        m = SystemMetrics(
            cpu_pct=0, memory_pct=0, memory_used_mb=0,
            memory_total_mb=0, disk_pct=0, disk_used_gb=0,
            disk_total_gb=0, temperature_c=None, load_1m=0,
            load_5m=0, load_15m=0, network_rx_bytes=0,
            network_tx_bytes=0, uptime_seconds=0,
        )
        assert m.cpu_pct == 0


class TestMetricPointModel:
    """Test MetricPoint model."""

    def test_basic(self):
        from routers.telemetry import MetricPoint
        p = MetricPoint(ts=1700000000, value=42.5)
        assert p.ts == 1700000000
        assert p.value == 42.5


class TestMetricsResponseModel:
    """Test MetricsResponse model."""

    def test_with_points(self):
        from routers.telemetry import MetricsResponse, MetricPoint
        r = MetricsResponse(
            metric="host.cpu.pct_total",
            points=[MetricPoint(ts=1700000000, value=25.0), MetricPoint(ts=1700000060, value=30.0)]
        )
        assert r.metric == "host.cpu.pct_total"
        assert len(r.points) == 2

    def test_empty_points(self):
        from routers.telemetry import MetricsResponse
        r = MetricsResponse(metric="host.cpu.pct_total", points=[])
        assert len(r.points) == 0


class TestMetricsSummaryModel:
    """Test MetricsSummary model."""

    def test_basic(self):
        from routers.telemetry import MetricsSummary
        s = MetricsSummary(metric="host.cpu.pct_total", avg=45.0, min=10.0, max=95.0, count=1440)
        assert s.avg == 45.0
        assert s.count == 1440


class TestDashboardDataModel:
    """Test DashboardData model."""

    def test_complete(self):
        from routers.telemetry import DashboardData, SystemMetrics
        d = DashboardData(
            system=SystemMetrics(
                cpu_pct=50.0, memory_pct=60.0, memory_used_mb=1024,
                memory_total_mb=2048, disk_pct=70.0, disk_used_gb=10.0,
                disk_total_gb=32.0, temperature_c=45.0, load_1m=1.0,
                load_5m=0.8, load_15m=0.5, network_rx_bytes=1000,
                network_tx_bytes=2000, uptime_seconds=86400,
            ),
            resource_counts={"docker": 3, "systemd": 5},
            alert_counts={"warning": 1, "critical": 0},
            timestamp="2025-01-01T00:00:00",
        )
        assert d.resource_counts["docker"] == 3
        assert d.alert_counts["warning"] == 1


class TestLocalMetricsFallback:
    """Test _get_local_system_metrics function."""

    @pytest.mark.asyncio
    async def test_returns_dict_with_metrics(self):
        """Test local metrics returns proper structure."""
        from routers.telemetry import _get_local_system_metrics
        result = await _get_local_system_metrics()
        assert isinstance(result, dict)
        assert "metrics" in result
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_has_cpu_metric(self):
        """Test local metrics includes CPU data."""
        from routers.telemetry import _get_local_system_metrics
        result = await _get_local_system_metrics()
        metrics = result.get("metrics", {})
        assert "host.cpu.pct_total" in metrics


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
