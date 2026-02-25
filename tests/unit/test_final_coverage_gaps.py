"""Tests to close the final coverage gaps (18 lines across 9 files)."""

from __future__ import annotations

import asyncio
import importlib

import pytest
from fastapi.testclient import TestClient

from labclaw.api.app import app
from labclaw.core.events import event_registry
from labclaw.orchestrator.steps import StepContext, StepName, StepResult


# ---------------------------------------------------------------------------
# 1. orchestrator/loop.py:146-158 — step fails (success=False)
# ---------------------------------------------------------------------------
class TestLoopStepFailure:
    def test_cycle_records_failed_step(self):
        """When a step returns success=False, the cycle records it and marks cycle failed."""
        from labclaw.orchestrator.loop import ScientificLoop

        class FailingStep:
            name = StepName.OBSERVE

            async def run(self, context: StepContext) -> StepResult:
                return StepResult(
                    step=StepName.OBSERVE,
                    success=False,
                    context=context,
                    duration_seconds=0.01,
                )

        class PassingStep:
            name = StepName.ASK

            async def run(self, context: StepContext) -> StepResult:
                return StepResult(
                    step=StepName.ASK,
                    success=True,
                    context=context,
                    duration_seconds=0.01,
                )

        loop = ScientificLoop(steps=[FailingStep(), PassingStep()])
        result = asyncio.run(loop.run_cycle([{"x": 1, "y": 2}]))
        assert "observe" in result.steps_completed
        assert result.success is False


# ---------------------------------------------------------------------------
# 2-6. API router gaps — use the module-level `app` directly
# ---------------------------------------------------------------------------
@pytest.fixture
def api_client():
    return TestClient(app)


class TestDevicesRouterGaps:
    def test_list_devices(self, api_client):
        resp = api_client.get("/api/devices/")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_update_device_status_success(self, api_client):
        # Register a device
        resp = api_client.post(
            "/api/devices/",
            json={
                "name": "test-status",
                "device_type": "sensor",
                "model": "v1",
                "manufacturer": "acme",
                "location": "lab",
            },
        )
        assert resp.status_code == 201
        dev_id = resp.json()["device_id"]
        resp2 = api_client.patch(f"/api/devices/{dev_id}/status", json={"status": "offline"})
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "offline"

    def test_unregister_device_success(self, api_client):
        resp = api_client.post(
            "/api/devices/",
            json={
                "name": "del-dev",
                "device_type": "sensor",
                "model": "v1",
                "manufacturer": "acme",
                "location": "lab",
            },
        )
        assert resp.status_code == 201
        dev_id = resp.json()["device_id"]
        resp2 = api_client.delete(f"/api/devices/{dev_id}")
        assert resp2.status_code == 200
        assert resp2.json()["deleted"] == "true"


class TestDiscoveryRouterGap:
    def test_mine_patterns_endpoint(self, api_client):
        resp = api_client.post(
            "/api/discovery/mine",
            json={
                "data": [
                    {"x": 1.0, "y": 2.0},
                    {"x": 2.0, "y": 4.0},
                    {"x": 3.0, "y": 6.0},
                ],
                "config": {},
            },
        )
        assert resp.status_code == 200


class TestEventsRouterGap:
    def test_list_events(self, api_client):
        resp = api_client.get("/api/events/")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestHealthStatusGap:
    def test_status_endpoint(self, api_client):
        resp = api_client.get("/api/status")
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
        assert "version" in body


class TestMemoryRouterGap:
    def test_search_empty_query(self, api_client):
        resp = api_client.get("/api/memory/search/query", params={"q": ""})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_search_nonempty_query(self, api_client):
        """Line 59: backend.search(q, limit=limit) with non-empty query."""
        resp = api_client.get("/api/memory/search/query", params={"q": "test"})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 7. discovery/modeling.py:424-426 — bootstrap sklearn clone exception
# ---------------------------------------------------------------------------
class TestModelingBootstrapFallback:
    def test_bootstrap_ci_sklearn_exception_fallback(self):
        """Lines 424-426: when sklearn model clone fails, fall back to linreg_pure."""
        from labclaw.discovery.modeling import ModelConfig, PredictiveModel

        model = PredictiveModel()
        data = [{"x": float(i), "target": float(i * 2 + 1)} for i in range(30)]
        config = ModelConfig(target_column="target", feature_columns=["x"])
        model.train(data, config)

        if model._model is not None:
            original_get_params = model._model.get_params

            def failing_get_params(**kwargs):
                raise RuntimeError("Clone failed")

            model._model.get_params = failing_get_params
            lo, hi = model._bootstrap_ci([3.0])
            assert lo <= hi
            model._model.get_params = original_get_params

    def test_extract_xy_empty_data(self):
        """Line 476: _extract_Xy with empty data."""
        from labclaw.discovery.modeling import ModelConfig, PredictiveModel

        config = ModelConfig(target_column="target")
        features, targets, cols = PredictiveModel._extract_Xy([], config)
        assert features == []
        assert targets == []
        assert cols == []


# ---------------------------------------------------------------------------
# 8. hardware/drivers/file_watcher.py:34 — event already registered
# ---------------------------------------------------------------------------
class TestFileWatcherEventRegistration:
    def test_event_already_registered_skips(self):
        """Line 33-34: re-import with event already registered (skip path)."""
        import labclaw.hardware.drivers.file_watcher as fw

        assert event_registry.is_registered("hardware.file.detected")
        importlib.reload(fw)
        assert event_registry.is_registered("hardware.file.detected")

    def test_event_not_yet_registered_registers(self):
        """Line 34: event NOT registered → registers it on import."""
        import labclaw.hardware.drivers.file_watcher as fw

        # Temporarily unregister by removing from _schemas dict
        was_registered = "hardware.file.detected" in event_registry._schemas
        if was_registered:
            saved = event_registry._schemas.pop("hardware.file.detected")
        assert not event_registry.is_registered("hardware.file.detected")

        importlib.reload(fw)
        assert event_registry.is_registered("hardware.file.detected")

        # Restore original schema if we removed one
        if was_registered:
            event_registry._schemas["hardware.file.detected"] = saved
