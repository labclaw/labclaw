"""Tests for src/labclaw/agents/tools.py — ToolResult, AgentTool, built-in tools."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from labclaw.agents.tools import (
    AgentTool,
    ToolResult,
    _device_status,
    _get_evolution_status,
    _hypothesize,
    _propose_experiment,
    _query_memory,
    _run_mining,
    _search_findings,
    build_builtin_tools,
)

# ---------------------------------------------------------------------------
# ToolResult model
# ---------------------------------------------------------------------------


class TestToolResult:
    def test_success_defaults(self) -> None:
        r = ToolResult(success=True)
        assert r.success is True
        assert r.data is None
        assert r.error == ""

    def test_failure_with_error(self) -> None:
        r = ToolResult(success=False, error="boom")
        assert r.success is False
        assert r.error == "boom"

    def test_data_field(self) -> None:
        r = ToolResult(success=True, data={"key": [1, 2, 3]})
        assert r.data == {"key": [1, 2, 3]}


# ---------------------------------------------------------------------------
# AgentTool wrapper
# ---------------------------------------------------------------------------


class TestAgentTool:
    @pytest.mark.asyncio
    async def test_execute_success_returns_tool_result(self) -> None:
        async def fn(**kwargs: Any) -> ToolResult:
            return ToolResult(success=True, data=kwargs)

        tool = AgentTool(name="test", description="d", fn=fn)
        result = await tool.execute(x=1)
        assert result.success is True
        assert result.data == {"x": 1}

    @pytest.mark.asyncio
    async def test_execute_wraps_plain_return(self) -> None:
        async def fn(**kwargs: Any) -> str:
            return "hello"

        tool = AgentTool(name="test", description="d", fn=fn)
        result = await tool.execute()
        assert result.success is True
        assert result.data == "hello"

    @pytest.mark.asyncio
    async def test_execute_exception_path(self) -> None:
        async def fn(**kwargs: Any) -> None:
            raise ValueError("test error")

        tool = AgentTool(name="boom", description="d", fn=fn)
        result = await tool.execute()
        assert result.success is False
        assert "test error" in result.error

    def test_parameters_schema_default(self) -> None:
        tool = AgentTool(name="t", description="d", fn=lambda: None)
        assert tool.parameters_schema == {}

    def test_parameters_schema_set(self) -> None:
        schema = {"x": {"type": "int"}}
        tool = AgentTool(name="t", description="d", fn=lambda: None, parameters_schema=schema)
        assert tool.parameters_schema == schema


# ---------------------------------------------------------------------------
# build_builtin_tools()
# ---------------------------------------------------------------------------


class TestBuildBuiltinTools:
    def test_returns_7_tools(self) -> None:
        tools = build_builtin_tools()
        assert len(tools) == 7

    def test_tool_names(self) -> None:
        tools = build_builtin_tools()
        names = {t.name for t in tools}
        expected = {
            "query_memory",
            "run_mining",
            "hypothesize",
            "device_status",
            "propose_experiment",
            "get_evolution_status",
            "search_findings",
        }
        assert names == expected

    def test_all_are_agent_tools(self) -> None:
        tools = build_builtin_tools()
        for t in tools:
            assert isinstance(t, AgentTool)


# ---------------------------------------------------------------------------
# _query_memory
# ---------------------------------------------------------------------------


class TestQueryMemory:
    @pytest.mark.asyncio
    async def test_memory_root_none(self) -> None:
        result = await _query_memory("test", memory_root=None)
        assert result.success is True
        assert result.data["results"] == []
        assert "No memory root" in result.data["note"]

    @pytest.mark.asyncio
    async def test_with_mock_backend(self, tmp_path: Any) -> None:
        mock_result = SimpleNamespace(entity_id="e1", snippet="found it", score=0.9, source="soul")
        mock_backend = MagicMock()
        mock_backend.search.return_value = [mock_result]

        with patch("labclaw.memory.markdown.TierABackend", return_value=mock_backend):
            result = await _query_memory("test", memory_root=tmp_path)

        assert result.success is True
        assert len(result.data["results"]) == 1
        assert result.data["results"][0]["entity_id"] == "e1"


# ---------------------------------------------------------------------------
# _run_mining
# ---------------------------------------------------------------------------


class TestRunMining:
    @pytest.mark.asyncio
    async def test_with_empty_data(self) -> None:
        mock_result = SimpleNamespace(patterns=[], data_summary={"row_count": 0})
        mock_miner = MagicMock()
        mock_miner.mine.return_value = mock_result

        with patch("labclaw.discovery.mining.PatternMiner", return_value=mock_miner):
            result = await _run_mining([])

        assert result.success is True
        assert result.data["pattern_count"] == 0

    @pytest.mark.asyncio
    async def test_with_valid_data(self) -> None:
        pattern = SimpleNamespace(
            pattern_id="p1",
            pattern_type="correlation",
            description="x correlates with y",
            confidence=0.8,
        )
        mock_result = SimpleNamespace(
            patterns=[pattern],
            data_summary={"row_count": 5},
        )
        mock_miner = MagicMock()
        mock_miner.mine.return_value = mock_result

        with patch("labclaw.discovery.mining.PatternMiner", return_value=mock_miner):
            result = await _run_mining([{"x": 1}])

        assert result.success is True
        assert result.data["pattern_count"] == 1
        assert result.data["patterns"][0]["pattern_id"] == "p1"


# ---------------------------------------------------------------------------
# _hypothesize
# ---------------------------------------------------------------------------


class TestHypothesize:
    @pytest.mark.asyncio
    async def test_with_empty_patterns(self) -> None:
        mock_gen = MagicMock()
        mock_gen.generate.return_value = []

        with (
            patch("labclaw.discovery.hypothesis.HypothesisGenerator", return_value=mock_gen),
            patch("labclaw.discovery.mining.PatternRecord"),
        ):
            result = await _hypothesize([])

        assert result.success is True
        assert result.data["hypothesis_count"] == 0

    @pytest.mark.asyncio
    async def test_with_valid_patterns(self) -> None:
        hyp = SimpleNamespace(
            hypothesis_id="h1",
            statement="X causes Y",
            confidence=0.7,
            required_experiments=["exp1"],
        )
        mock_gen = MagicMock()
        mock_gen.generate.return_value = [hyp]

        with (
            patch("labclaw.discovery.hypothesis.HypothesisGenerator", return_value=mock_gen),
            patch("labclaw.discovery.mining.PatternRecord"),
            patch("labclaw.discovery.hypothesis.HypothesisInput"),
        ):
            result = await _hypothesize([{"pattern_id": "p1"}])

        assert result.success is True
        assert result.data["hypothesis_count"] == 1
        assert result.data["hypotheses"][0]["statement"] == "X causes Y"


# ---------------------------------------------------------------------------
# _device_status
# ---------------------------------------------------------------------------


class TestDeviceStatus:
    @pytest.mark.asyncio
    async def test_registry_none(self) -> None:
        result = await _device_status(device_registry=None)
        assert result.success is True
        assert result.data["devices"] == []
        assert "No device registry" in result.data["note"]

    @pytest.mark.asyncio
    async def test_with_mock_registry(self) -> None:
        from labclaw.core.schemas import DeviceStatus

        device = SimpleNamespace(
            device_id="d1",
            name="Camera",
            device_type="camera",
            status=DeviceStatus.ONLINE,
            location="lab-1",
        )
        mock_reg = MagicMock()
        mock_reg.list_devices.return_value = [device]

        result = await _device_status(device_registry=mock_reg)
        assert result.success is True
        assert len(result.data["devices"]) == 1
        assert result.data["devices"][0]["name"] == "Camera"


# ---------------------------------------------------------------------------
# _propose_experiment
# ---------------------------------------------------------------------------


class TestProposeExperiment:
    @pytest.mark.asyncio
    async def test_no_ranges(self) -> None:
        result = await _propose_experiment("hyp-1")
        assert result.success is True
        assert result.data["proposals"] == []
        assert "No numeric_ranges" in result.data["note"]

    @pytest.mark.asyncio
    async def test_with_valid_ranges(self) -> None:
        proposal = SimpleNamespace(proposal_id="prop-1", parameters={"temp": 37.0})
        mock_opt = MagicMock()
        mock_opt.suggest.return_value = [proposal]

        with (
            patch("labclaw.optimization.optimizer.BayesianOptimizer", return_value=mock_opt),
            patch("labclaw.optimization.optimizer.ParameterDimension"),
            patch("labclaw.optimization.optimizer.ParameterSpace"),
        ):
            result = await _propose_experiment("hyp-1", numeric_ranges={"temp": (20.0, 40.0)})

        assert result.success is True
        assert len(result.data["proposals"]) == 1
        assert result.data["proposals"][0]["proposal_id"] == "prop-1"


# ---------------------------------------------------------------------------
# _get_evolution_status
# ---------------------------------------------------------------------------


class TestGetEvolutionStatus:
    @pytest.mark.asyncio
    async def test_engine_none(self) -> None:
        result = await _get_evolution_status(evolution_engine=None)
        assert result.success is True
        assert result.data["cycles"] == []
        assert "No evolution engine" in result.data["note"]

    @pytest.mark.asyncio
    async def test_with_mock_engine(self) -> None:

        cycle = SimpleNamespace(
            cycle_id="c1",
            target=SimpleNamespace(value="protocol"),
            stage=SimpleNamespace(value="evaluation"),
            candidate=SimpleNamespace(description="better protocol"),
            promoted=False,
        )
        mock_engine = MagicMock()
        mock_engine.get_active_cycles.return_value = [cycle]

        result = await _get_evolution_status(evolution_engine=mock_engine)
        assert result.success is True
        assert result.data["active_cycle_count"] == 1
        assert result.data["cycles"][0]["cycle_id"] == "c1"


# ---------------------------------------------------------------------------
# _search_findings
# ---------------------------------------------------------------------------


class TestSearchFindings:
    @pytest.mark.asyncio
    async def test_memory_root_none(self) -> None:
        result = await _search_findings("test", memory_root=None)
        assert result.success is True
        assert result.data["results"] == []
        assert "No memory root" in result.data["note"]

    @pytest.mark.asyncio
    async def test_with_mock_backend(self) -> None:
        mock_result = SimpleNamespace(
            entity_id="e2", snippet="conclusion", score=0.5, source="memory"
        )
        mock_backend = MagicMock()
        mock_backend.search.return_value = [mock_result]

        with patch("labclaw.memory.markdown.TierABackend", return_value=mock_backend):
            result = await _search_findings("test", memory_root="/tmp")

        assert result.success is True
        assert len(result.data["results"]) == 1
        # Verify the search query has "cycle_conclusion" prefix
        call_args = mock_backend.search.call_args
        assert "cycle_conclusion" in call_args[0][0]
