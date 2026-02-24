"""Built-in agent tools — callable functions that agents can invoke.

Each tool is wrapped in an AgentTool object that the AgentRuntime registers.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool result model
# ---------------------------------------------------------------------------


class ToolResult(BaseModel):
    """Standardised return type for all agent tools."""

    success: bool
    data: Any = None
    error: str = ""


# ---------------------------------------------------------------------------
# AgentTool wrapper
# ---------------------------------------------------------------------------


class AgentTool:
    """A callable tool available to agents."""

    def __init__(
        self,
        name: str,
        description: str,
        fn: Any,
        parameters_schema: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.fn = fn
        self.parameters_schema = parameters_schema or {}

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given arguments."""
        try:
            result = await self.fn(**kwargs)
            if isinstance(result, ToolResult):
                return result
            return ToolResult(success=True, data=result)
        except Exception as exc:
            logger.exception("Tool %s failed", self.name)
            return ToolResult(success=False, error=str(exc))


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


async def _query_memory(
    query: str,
    *,
    memory_root: Any | None = None,
    limit: int = 10,
) -> ToolResult:
    """Search Tier A memory for matching entries."""
    try:
        if memory_root is None:
            return ToolResult(
                success=True,
                data={"results": [], "note": "No memory root configured"},
            )

        from labclaw.memory.markdown import TierABackend

        backend = TierABackend(memory_root)
        results = backend.search(query, limit=limit)
        return ToolResult(
            success=True,
            data={
                "results": [
                    {
                        "entity_id": r.entity_id,
                        "snippet": r.snippet,
                        "score": r.score,
                        "source": r.source,
                    }
                    for r in results
                ],
            },
        )
    except Exception as exc:
        logger.exception("query_memory failed")
        return ToolResult(success=False, error=str(exc))


async def _run_mining(
    data_rows: list[dict[str, Any]],
) -> ToolResult:
    """Run PatternMiner on provided data rows."""
    try:
        from labclaw.discovery.mining import MiningConfig, PatternMiner

        miner = PatternMiner()
        result = miner.mine(data_rows, MiningConfig())
        return ToolResult(
            success=True,
            data={
                "pattern_count": len(result.patterns),
                "patterns": [
                    {
                        "pattern_id": p.pattern_id,
                        "pattern_type": p.pattern_type,
                        "description": p.description,
                        "confidence": p.confidence,
                    }
                    for p in result.patterns
                ],
                "data_summary": result.data_summary,
            },
        )
    except Exception as exc:
        logger.exception("run_mining failed")
        return ToolResult(success=False, error=str(exc))


async def _hypothesize(
    patterns: list[dict[str, Any]],
) -> ToolResult:
    """Generate hypotheses from pattern dicts."""
    try:
        from labclaw.discovery.hypothesis import (
            HypothesisGenerator,
            HypothesisInput,
        )
        from labclaw.discovery.mining import PatternRecord

        records = [PatternRecord(**p) for p in patterns]
        gen = HypothesisGenerator()
        hypotheses = gen.generate(HypothesisInput(patterns=records))
        return ToolResult(
            success=True,
            data={
                "hypothesis_count": len(hypotheses),
                "hypotheses": [
                    {
                        "hypothesis_id": h.hypothesis_id,
                        "statement": h.statement,
                        "confidence": h.confidence,
                        "required_experiments": h.required_experiments,
                    }
                    for h in hypotheses
                ],
            },
        )
    except Exception as exc:
        logger.exception("hypothesize failed")
        return ToolResult(success=False, error=str(exc))


async def _device_status(
    *,
    device_registry: Any | None = None,
) -> ToolResult:
    """List all devices and their current status."""
    try:
        if device_registry is None:
            return ToolResult(
                success=True,
                data={"devices": [], "note": "No device registry configured"},
            )

        devices = device_registry.list_devices()
        return ToolResult(
            success=True,
            data={
                "devices": [
                    {
                        "device_id": d.device_id,
                        "name": d.name,
                        "device_type": d.device_type,
                        "status": d.status.value,
                        "location": d.location,
                    }
                    for d in devices
                ],
            },
        )
    except Exception as exc:
        logger.exception("device_status failed")
        return ToolResult(success=False, error=str(exc))


async def _propose_experiment(
    hypothesis_id: str,
    *,
    numeric_ranges: dict[str, tuple[float, float]] | None = None,
) -> ToolResult:
    """Suggest next experiment parameters for a given hypothesis."""
    try:
        from labclaw.optimization.optimizer import (
            BayesianOptimizer,
            ParameterDimension,
            ParameterSpace,
        )

        if not numeric_ranges:
            return ToolResult(
                success=True,
                data={
                    "proposals": [],
                    "note": "No numeric_ranges provided; cannot propose parameters",
                    "hypothesis_id": hypothesis_id,
                },
            )

        dims = [
            ParameterDimension(name=name, low=lo, high=hi)
            for name, (lo, hi) in numeric_ranges.items()
        ]
        space = ParameterSpace(name="agent_proposal", dimensions=dims)
        optimizer = BayesianOptimizer(space)
        proposals = optimizer.suggest(n=1)

        return ToolResult(
            success=True,
            data={
                "hypothesis_id": hypothesis_id,
                "proposals": [
                    {
                        "proposal_id": p.proposal_id,
                        "parameters": p.parameters,
                    }
                    for p in proposals
                ],
            },
        )
    except Exception as exc:
        logger.exception("propose_experiment failed")
        return ToolResult(success=False, error=str(exc))


async def _get_evolution_status(
    *,
    evolution_engine: Any | None = None,
) -> ToolResult:
    """Get current evolution cycle status."""
    try:
        if evolution_engine is None:
            return ToolResult(
                success=True,
                data={"cycles": [], "note": "No evolution engine configured"},
            )

        active = evolution_engine.get_active_cycles()
        return ToolResult(
            success=True,
            data={
                "active_cycle_count": len(active),
                "cycles": [
                    {
                        "cycle_id": c.cycle_id,
                        "target": c.target.value,
                        "stage": c.stage.value,
                        "candidate": c.candidate.description,
                        "promoted": c.promoted,
                    }
                    for c in active
                ],
            },
        )
    except Exception as exc:
        logger.exception("get_evolution_status failed")
        return ToolResult(success=False, error=str(exc))


async def _search_findings(
    query: str,
    *,
    memory_root: Any | None = None,
    limit: int = 10,
) -> ToolResult:
    """Search findings (conclusions from scientific cycles) in memory."""
    try:
        if memory_root is None:
            return ToolResult(
                success=True,
                data={"results": [], "note": "No memory root configured"},
            )

        from labclaw.memory.markdown import TierABackend

        backend = TierABackend(memory_root)
        # Search with findings-specific context
        results = backend.search(f"cycle_conclusion {query}", limit=limit)
        return ToolResult(
            success=True,
            data={
                "results": [
                    {
                        "entity_id": r.entity_id,
                        "snippet": r.snippet,
                        "score": r.score,
                        "source": r.source,
                    }
                    for r in results
                ],
            },
        )
    except Exception as exc:
        logger.exception("search_findings failed")
        return ToolResult(success=False, error=str(exc))


# ---------------------------------------------------------------------------
# Built-in tool factory
# ---------------------------------------------------------------------------


def build_builtin_tools(
    *,
    memory_root: Any | None = None,
    device_registry: Any | None = None,
    evolution_engine: Any | None = None,
) -> list[AgentTool]:
    """Create all built-in AgentTool instances with injected dependencies."""
    from functools import partial

    return [
        AgentTool(
            name="query_memory",
            description="Search lab memory for past findings, patterns, and conclusions.",
            fn=partial(_query_memory, memory_root=memory_root),
            parameters_schema={
                "query": {"type": "string", "description": "Search query"},
            },
        ),
        AgentTool(
            name="run_mining",
            description="Run pattern mining on experimental data rows.",
            fn=_run_mining,
            parameters_schema={
                "data_rows": {"type": "array", "description": "List of data row dicts"},
            },
        ),
        AgentTool(
            name="hypothesize",
            description="Generate testable hypotheses from discovered patterns.",
            fn=_hypothesize,
            parameters_schema={
                "patterns": {"type": "array", "description": "List of pattern dicts"},
            },
        ),
        AgentTool(
            name="device_status",
            description="List all lab devices and their current status.",
            fn=partial(_device_status, device_registry=device_registry),
            parameters_schema={},
        ),
        AgentTool(
            name="propose_experiment",
            description="Suggest next experiment parameters for a hypothesis.",
            fn=_propose_experiment,
            parameters_schema={
                "hypothesis_id": {"type": "string", "description": "Hypothesis ID"},
            },
        ),
        AgentTool(
            name="get_evolution_status",
            description="Get current self-evolution cycle status.",
            fn=partial(_get_evolution_status, evolution_engine=evolution_engine),
            parameters_schema={},
        ),
        AgentTool(
            name="search_findings",
            description="Search findings and conclusions from scientific cycles.",
            fn=partial(_search_findings, memory_root=memory_root),
            parameters_schema={
                "query": {"type": "string", "description": "Search query"},
            },
        ),
    ]
