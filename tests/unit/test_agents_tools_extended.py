"""Extended tests for agents/tools.py — covers exception paths (lines 98-100,
128-130, 162-164, 195-197, 244-246, 278-280, 316-318).

Each exception-path test triggers the except block in the corresponding
async tool function, verifying it returns ToolResult(success=False).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from labclaw.agents.tools import (
    _device_status,
    _get_evolution_status,
    _hypothesize,
    _propose_experiment,
    _query_memory,
    _run_mining,
    _search_findings,
)

# ---------------------------------------------------------------------------
# _query_memory exception path (lines 98-100)
# ---------------------------------------------------------------------------


class TestQueryMemoryException:
    @pytest.mark.asyncio
    async def test_exception_returns_failure(self) -> None:
        """_query_memory exception block → ToolResult(success=False)."""
        bad_backend = MagicMock()
        bad_backend.search.side_effect = RuntimeError("backend exploded")

        with patch("labclaw.memory.markdown.TierABackend", return_value=bad_backend):
            result = await _query_memory("query", memory_root="/tmp")

        assert result.success is False
        assert "backend exploded" in result.error


# ---------------------------------------------------------------------------
# _run_mining exception path (lines 128-130)
# ---------------------------------------------------------------------------


class TestRunMiningException:
    @pytest.mark.asyncio
    async def test_exception_returns_failure(self) -> None:
        """_run_mining exception block → ToolResult(success=False)."""
        bad_miner = MagicMock()
        bad_miner.mine.side_effect = ValueError("mining failed")

        with patch("labclaw.discovery.mining.PatternMiner", return_value=bad_miner):
            result = await _run_mining([{"x": 1}])

        assert result.success is False
        assert "mining failed" in result.error


# ---------------------------------------------------------------------------
# _hypothesize exception path (lines 162-164)
# ---------------------------------------------------------------------------


class TestHypothesizeException:
    @pytest.mark.asyncio
    async def test_exception_returns_failure(self) -> None:
        """_hypothesize exception block → ToolResult(success=False)."""
        bad_gen = MagicMock()
        bad_gen.generate.side_effect = RuntimeError("hypothesis crash")

        with (
            patch("labclaw.discovery.hypothesis.HypothesisGenerator", return_value=bad_gen),
            patch("labclaw.discovery.mining.PatternRecord"),
        ):
            result = await _hypothesize([])

        assert result.success is False
        assert "hypothesis crash" in result.error


# ---------------------------------------------------------------------------
# _device_status exception path (lines 195-197)
# ---------------------------------------------------------------------------


class TestDeviceStatusException:
    @pytest.mark.asyncio
    async def test_exception_returns_failure(self) -> None:
        """_device_status exception block → ToolResult(success=False)."""
        bad_registry = MagicMock()
        bad_registry.list_devices.side_effect = RuntimeError("registry broken")

        result = await _device_status(device_registry=bad_registry)

        assert result.success is False
        assert "registry broken" in result.error


# ---------------------------------------------------------------------------
# _propose_experiment exception path (lines 244-246)
# ---------------------------------------------------------------------------


class TestProposeExperimentException:
    @pytest.mark.asyncio
    async def test_exception_returns_failure(self) -> None:
        """_propose_experiment exception block → ToolResult(success=False)."""
        bad_opt = MagicMock()
        bad_opt.suggest.side_effect = RuntimeError("optimizer broke")

        with (
            patch("labclaw.optimization.optimizer.BayesianOptimizer", return_value=bad_opt),
            patch("labclaw.optimization.optimizer.ParameterDimension"),
            patch("labclaw.optimization.optimizer.ParameterSpace"),
        ):
            result = await _propose_experiment("hyp-1", numeric_ranges={"temp": (20.0, 40.0)})

        assert result.success is False
        assert "optimizer broke" in result.error


# ---------------------------------------------------------------------------
# _get_evolution_status exception path (lines 278-280)
# ---------------------------------------------------------------------------


class TestGetEvolutionStatusException:
    @pytest.mark.asyncio
    async def test_exception_returns_failure(self) -> None:
        """_get_evolution_status exception block → ToolResult(success=False)."""
        bad_engine = MagicMock()
        bad_engine.get_active_cycles.side_effect = RuntimeError("engine crash")

        result = await _get_evolution_status(evolution_engine=bad_engine)

        assert result.success is False
        assert "engine crash" in result.error


# ---------------------------------------------------------------------------
# _search_findings exception path (lines 316-318)
# ---------------------------------------------------------------------------


class TestSearchFindingsException:
    @pytest.mark.asyncio
    async def test_exception_returns_failure(self) -> None:
        """_search_findings exception block → ToolResult(success=False)."""
        bad_backend = MagicMock()
        bad_backend.search.side_effect = OSError("disk error")

        with patch("labclaw.memory.markdown.TierABackend", return_value=bad_backend):
            result = await _search_findings("test", memory_root="/tmp")

        assert result.success is False
        assert "disk error" in result.error
