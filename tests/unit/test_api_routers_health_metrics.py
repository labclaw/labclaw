"""Tests for health, metrics, and discovery router uncovered branches.

Targets:
- api/routers/health.py:    35-36 (OSError probe), 54-55 (event_bus exc),
                            67-68 (evolution exc), 82 (unhealthy status_code)
- api/routers/metrics.py:   31-32 (miner exc), 52-53 (engine exc)
- api/routers/discovery.py: 49-54 (hypothesize endpoint)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from labclaw.api.app import app
from labclaw.api.deps import reset_all


@pytest.fixture(autouse=True)
def _reset_deps() -> None:
    reset_all()


# ---------------------------------------------------------------------------
# health.py private helpers — direct unit tests
# ---------------------------------------------------------------------------


class TestHealthHelpers:
    def test_check_memory_degraded_when_root_missing(self, tmp_path) -> None:
        from labclaw.api.routers.health import _check_memory

        nonexistent = tmp_path / "no_such_dir"
        with patch("labclaw.api.deps._default_memory_root", return_value=nonexistent):
            result = _check_memory()
        assert result["status"] == "degraded"
        assert "does not exist" in result["detail"]

    def test_check_memory_degraded_when_not_writable(self, tmp_path) -> None:
        """OSError during probe write → degraded (lines 35-36)."""
        from labclaw.api.routers.health import _check_memory

        with (
            patch("labclaw.api.deps._default_memory_root", return_value=tmp_path),
            patch("pathlib.Path.write_text", side_effect=OSError("permission denied")),
        ):
            result = _check_memory()
        assert result["status"] == "degraded"
        assert "not writable" in result["detail"]

    def test_check_event_bus_unhealthy_on_exception(self) -> None:
        """Exception in list_events → unhealthy (lines 54-55)."""
        from labclaw.api.routers.health import _check_event_bus

        mock_reg = MagicMock()
        mock_reg.list_events.side_effect = RuntimeError("bus down")

        with patch("labclaw.api.routers.health.get_event_registry", return_value=mock_reg):
            result = _check_event_bus()
        assert result["status"] == "unhealthy"
        assert "bus down" in result["detail"]

    def test_check_evolution_unhealthy_on_exception(self) -> None:
        """Exception in get_active_cycles → unhealthy (lines 67-68)."""
        from labclaw.api.routers.health import _check_evolution

        mock_engine = MagicMock()
        mock_engine.get_active_cycles.side_effect = RuntimeError("engine dead")

        with patch("labclaw.api.routers.health.get_evolution_engine", return_value=mock_engine):
            result = _check_evolution()
        assert result["status"] == "unhealthy"
        assert "engine dead" in result["detail"]


# ---------------------------------------------------------------------------
# health endpoint — unhealthy overall → 503 (line 82)
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_503_when_unhealthy(self) -> None:
        """When a component is unhealthy, /api/health returns 503 (line 82)."""

        with (
            patch(
                "labclaw.api.routers.health._check_event_bus",
                return_value={"status": "unhealthy", "detail": "bus down"},
            ),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/health")

        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_health_returns_200_when_degraded(self) -> None:
        """When a component is degraded (but none unhealthy), returns 200."""
        with patch(
            "labclaw.api.routers.health._check_data",
            return_value={"status": "degraded", "detail": "data dir missing"},
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/health")
        # degraded still returns 200 (not 503)
        assert resp.status_code == 200
        assert resp.json()["status"] == "degraded"


# ---------------------------------------------------------------------------
# metrics.py — exception fallback paths (lines 31-32, 52-53)
# ---------------------------------------------------------------------------


class TestMetricsExceptionPaths:
    @pytest.mark.asyncio
    async def test_metrics_miner_exception_falls_back_to_zero(self) -> None:
        """When get_pattern_miner() raises, pattern_count falls back to 0 (lines 31-32)."""
        with patch(
            "labclaw.api.routers.metrics.get_pattern_miner",
            side_effect=RuntimeError("miner unavailable"),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/metrics")
        assert resp.status_code == 200
        assert "labclaw_patterns_discovered_total 0" in resp.text

    @pytest.mark.asyncio
    async def test_metrics_engine_exception_falls_back_to_zero(self) -> None:
        """When get_evolution_engine() raises, promoted/rolled_back/active → 0 (lines 52-53)."""
        with patch(
            "labclaw.api.routers.metrics.get_evolution_engine",
            side_effect=RuntimeError("engine unavailable"),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.get("/api/metrics")
        assert resp.status_code == 200
        assert 'labclaw_evolution_cycles_total{status="promoted"} 0' in resp.text


# ---------------------------------------------------------------------------
# discovery.py — hypothesize endpoint (lines 49-54)
# ---------------------------------------------------------------------------


class TestDiscoveryHypothesizeEndpoint:
    @pytest.mark.asyncio
    async def test_hypothesize_empty_patterns(self) -> None:
        """POST /api/discovery/hypothesize with empty patterns returns list (lines 49-54)."""
        from labclaw.api.deps import get_hypothesis_generator
        from labclaw.discovery.hypothesis import HypothesisGenerator

        # Override the dependency with a lambda to avoid FastAPI inspecting
        # HypothesisGenerator.__init__ params (plugin_templates) as body params
        app.dependency_overrides[get_hypothesis_generator] = lambda: HypothesisGenerator()
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                resp = await c.post(
                    "/api/discovery/hypothesize",
                    json={"patterns": [], "context": "test", "constraints": []},
                )
        finally:
            app.dependency_overrides.pop(get_hypothesis_generator, None)

        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
