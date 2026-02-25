"""Coverage boost tests — targets remaining uncovered lines:

- agents/__init__.py:         35-40, 51-56  (factory functions)
- api/routers/agents.py:      61-67         (_build_runtime called end-to-end)
- api/routers/orchestrator.py: 36-37        (exception handler)
- evolution/fitness.py:       63-66         (get_latest returns None)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from labclaw.api.app import app
from labclaw.api.deps import reset_all
from labclaw.core.schemas import EvolutionTarget
from labclaw.evolution.fitness import FitnessTracker

# ---------------------------------------------------------------------------
# agents/__init__.py — create_lab_assistant / create_experiment_designer
# ---------------------------------------------------------------------------


class TestAgentFactories:
    def test_create_lab_assistant_returns_agent_runtime(self) -> None:
        """create_lab_assistant() builds an AgentRuntime with injected tools."""
        from labclaw.agents import AgentRuntime, create_lab_assistant

        mock_llm = MagicMock()
        runtime = create_lab_assistant(mock_llm)

        assert isinstance(runtime, AgentRuntime)
        assert len(runtime.tools) >= 1

    def test_create_lab_assistant_with_dependencies(self) -> None:
        """create_lab_assistant() passes optional deps through to tools."""
        from labclaw.agents import AgentRuntime, create_lab_assistant

        mock_llm = MagicMock()
        mock_registry = MagicMock()
        mock_engine = MagicMock()

        runtime = create_lab_assistant(
            mock_llm,
            device_registry=mock_registry,
            evolution_engine=mock_engine,
        )
        assert isinstance(runtime, AgentRuntime)

    def test_create_experiment_designer_returns_agent_runtime(self) -> None:
        """create_experiment_designer() builds an AgentRuntime with injected tools."""
        from labclaw.agents import AgentRuntime, create_experiment_designer

        mock_llm = MagicMock()
        runtime = create_experiment_designer(mock_llm)

        assert isinstance(runtime, AgentRuntime)
        assert len(runtime.tools) >= 1

    def test_create_experiment_designer_with_dependencies(self) -> None:
        """create_experiment_designer() passes optional deps through to tools."""
        from labclaw.agents import AgentRuntime, create_experiment_designer

        mock_llm = MagicMock()
        runtime = create_experiment_designer(
            mock_llm,
            memory_root="/tmp",
            device_registry=MagicMock(),
        )
        assert isinstance(runtime, AgentRuntime)


# ---------------------------------------------------------------------------
# api/routers/agents.py — _build_runtime (lines 61-67) called end-to-end
# ---------------------------------------------------------------------------


class TestBuildRuntimeEndToEnd:
    @pytest.fixture(autouse=True)
    def _reset(self) -> None:
        reset_all()

    @pytest.mark.asyncio
    async def test_lab_assistant_chat_calls_build_runtime(self) -> None:
        """A successful chat request exercises _build_runtime fully (lines 61-67)."""
        from labclaw.api.deps import get_llm_provider as _real_dep

        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value="hello from lab-assistant")
        mock_llm.model_name = "test-model"

        # Inject the mock LLM through dependency override so _require_llm passes.
        # Let _build_runtime run for real — it calls get_tier_a_backend(),
        # get_device_registry(), get_evolution_engine(), which are all safe
        # in-memory singletons.
        app.dependency_overrides[_real_dep] = lambda: mock_llm
        try:
            # Also patch AgentRuntime.chat so it doesn't actually call the LLM
            chat_mock = AsyncMock(return_value="hi")
            with patch("labclaw.agents.runtime.AgentRuntime.chat", new=chat_mock):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    resp = await client.post("/api/agents/chat", json={"message": "test"})
        finally:
            app.dependency_overrides.pop(_real_dep, None)

        assert resp.status_code == 200
        assert resp.json()["agent"] == "lab-assistant"


# ---------------------------------------------------------------------------
# api/routers/orchestrator.py — exception handler (lines 36-37)
# ---------------------------------------------------------------------------


class TestOrchestratorException:
    @pytest.mark.asyncio
    async def test_run_cycle_exception_returns_500(self) -> None:
        """When ScientificLoop.run_cycle raises, the endpoint returns 500."""
        with patch(
            "labclaw.orchestrator.loop.ScientificLoop.run_cycle",
            new=AsyncMock(side_effect=RuntimeError("loop crashed")),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post("/api/orchestrator/cycle", json={"data_rows": []})

        assert resp.status_code == 500
        assert resp.json()["detail"] == "Internal server error"

    @pytest.mark.asyncio
    async def test_cycle_history_trimmed_when_over_max(self) -> None:
        """When _cycle_history exceeds _MAX_CYCLE_HISTORY, oldest entries are evicted."""
        import labclaw.api.routers.orchestrator as orch_mod
        from labclaw.orchestrator.loop import CycleResult

        fake_result = CycleResult(cycle_id="trim-test")
        original_history = orch_mod._cycle_history
        big_history: list = [CycleResult() for _ in range(orch_mod._MAX_CYCLE_HISTORY)]
        orch_mod._cycle_history = big_history
        try:
            with patch(
                "labclaw.orchestrator.loop.ScientificLoop.run_cycle",
                new=AsyncMock(return_value=fake_result),
            ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    resp = await client.post("/api/orchestrator/cycle", json={"data_rows": []})
            assert resp.status_code == 201
            assert len(orch_mod._cycle_history) == orch_mod._MAX_CYCLE_HISTORY
        finally:
            orch_mod._cycle_history = original_history


# ---------------------------------------------------------------------------
# evolution/fitness.py — get_latest returns None (lines 63-66)
# ---------------------------------------------------------------------------


class TestFitnessTrackerGetLatest:
    def test_get_latest_returns_none_when_no_history(self) -> None:
        """get_latest() returns None when no scores recorded for target."""
        tracker = FitnessTracker()
        result = tracker.get_latest(EvolutionTarget.ANALYSIS_PARAMS)
        assert result is None

    def test_get_latest_returns_most_recent_score(self) -> None:
        """get_latest() returns the last recorded score."""
        tracker = FitnessTracker()
        tracker.measure(EvolutionTarget.ANALYSIS_PARAMS, {"acc": 0.8})
        tracker.measure(EvolutionTarget.ANALYSIS_PARAMS, {"acc": 0.9})
        latest = tracker.get_latest(EvolutionTarget.ANALYSIS_PARAMS)
        assert latest is not None
        assert latest.metrics["acc"] == 0.9

    def test_get_latest_empty_target_after_history_cleared(self) -> None:
        """get_latest() on target with empty history list returns None."""

        tracker = FitnessTracker()
        # Manually insert an empty list to hit the `if not history` branch
        tracker._history[EvolutionTarget.PROMPTS] = []
        result = tracker.get_latest(EvolutionTarget.PROMPTS)
        assert result is None


class TestFitnessTrackerFromDict:
    def test_from_dict_roundtrip(self) -> None:
        """FitnessTracker.from_dict restores history across all targets."""
        tracker = FitnessTracker()
        tracker.measure(EvolutionTarget.ANALYSIS_PARAMS, {"acc": 0.75}, data_points=10)
        tracker.measure(EvolutionTarget.PROMPTS, {"quality": 0.9}, data_points=5)

        serialized = tracker.to_dict()
        restored = FitnessTracker.from_dict(serialized)

        latest_ap = restored.get_latest(EvolutionTarget.ANALYSIS_PARAMS)
        assert latest_ap is not None
        assert latest_ap.metrics["acc"] == 0.75

        latest_pr = restored.get_latest(EvolutionTarget.PROMPTS)
        assert latest_pr is not None
        assert latest_pr.metrics["quality"] == 0.9

    def test_from_dict_empty(self) -> None:
        """from_dict with empty dict returns empty tracker."""
        tracker = FitnessTracker.from_dict({})
        assert tracker.get_history(EvolutionTarget.PROMPTS) == []
