"""LabClaw MCP Server — expose lab intelligence as MCP tools.

Allows any MCP-compatible AI (Claude Desktop, etc.) to:
- Query lab memory and findings
- Run pattern mining on data
- Generate hypotheses
- Check evolution status
- View device status
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


def _get_pattern_miner():  # noqa: ANN202
    from labclaw.api.deps import get_pattern_miner

    return get_pattern_miner()


def _get_hypothesis_generator():  # noqa: ANN202
    from labclaw.api.deps import get_hypothesis_generator

    return get_hypothesis_generator()


def _get_evolution_engine():  # noqa: ANN202
    from labclaw.api.deps import get_evolution_engine

    return get_evolution_engine()


def _get_device_registry():  # noqa: ANN202
    from labclaw.api.deps import get_device_registry

    return get_device_registry()


def _get_search_engine():  # noqa: ANN202
    from labclaw.api.deps import get_tier_a_backend
    from labclaw.memory.search import HybridSearchEngine

    return HybridSearchEngine(tier_a=get_tier_a_backend())


def create_server() -> FastMCP:
    """Create and configure the LabClaw MCP server."""
    mcp = FastMCP("labclaw")

    @mcp.tool()
    def discover(
        min_sessions: int = 10,
        correlation_threshold: float = 0.5,
        anomaly_z_threshold: float = 2.0,
    ) -> str:
        """Run pattern mining on lab data.

        Args:
            min_sessions: Minimum number of sessions required to mine patterns.
            correlation_threshold: Minimum absolute correlation to report.
            anomaly_z_threshold: Z-score threshold for anomaly detection.
        """
        from labclaw.discovery.mining import MiningConfig

        miner = _get_pattern_miner()
        config = MiningConfig(
            min_sessions=min_sessions,
            correlation_threshold=correlation_threshold,
            anomaly_z_threshold=anomaly_z_threshold,
        )
        # Load experiment rows from session chronicle via memory/API
        rows: list[dict[str, Any]] = []
        try:
            from labclaw.api.deps import get_session_chronicle

            chronicle = get_session_chronicle()
            for session in chronicle.list_sessions():
                row = session.model_dump()
                rows.append(row)
        except (ImportError, Exception):
            logger.debug("Could not load session data for mining", exc_info=True)
            rows = []
        if not rows:
            return json.dumps(
                {
                    "patterns": [],
                    "data_summary": {"row_count": 0},
                    "message": "No experiment data available. Ingest data first.",
                },
                indent=2,
            )
        result = miner.mine(rows, config=config)
        return result.model_dump_json(indent=2)

    @mcp.tool()
    def hypothesize(context: str = "", constraints: str = "") -> str:
        """Generate hypotheses from discovered patterns.

        Args:
            context: Domain context to guide hypothesis generation.
            constraints: Comma-separated constraints for hypotheses.
        """
        from labclaw.discovery.hypothesis import HypothesisInput

        generator = _get_hypothesis_generator()
        constraint_list = [c.strip() for c in constraints.split(",") if c.strip()]
        # Load latest mined patterns from session chronicle
        try:
            from labclaw.api.deps import get_latest_patterns

            patterns = get_latest_patterns()
        except (ImportError, Exception):
            patterns = []
        inp = HypothesisInput(patterns=patterns, context=context, constraints=constraint_list)
        results = generator.generate(inp)
        return json.dumps(
            [r.model_dump(mode="json") for r in results],
            indent=2,
            default=str,
        )

    @mcp.tool()
    def evolution_status() -> str:
        """Get current self-evolution cycle status."""
        engine = _get_evolution_engine()
        active = engine.get_active_cycles()
        history = engine.get_history()
        summary: dict[str, Any] = {
            "active_cycles": len(active),
            "total_cycles": len(history),
            "cycles": [],
        }
        for cycle in active:
            summary["cycles"].append(
                {
                    "cycle_id": cycle.cycle_id,
                    "target": cycle.target.value,
                    "stage": cycle.stage.value,
                    "started_at": cycle.started_at.isoformat(),
                    "candidate": cycle.candidate.description,
                }
            )
        return json.dumps(summary, indent=2, default=str)

    @mcp.tool()
    def device_status() -> str:
        """List all lab devices and their status."""
        registry = _get_device_registry()
        devices = registry.list_devices()
        result = []
        for d in devices:
            result.append(
                {
                    "device_id": d.device_id,
                    "name": d.name,
                    "type": d.device_type,
                    "status": d.status.value,
                    "location": d.location,
                    "model": d.model,
                }
            )
        return json.dumps(result, indent=2, default=str)

    @mcp.tool()
    def query_memory(query: str) -> str:
        """Search lab memory for information.

        Args:
            query: Search query text.
        """
        from labclaw.memory.search import HybridSearchQuery

        engine = _get_search_engine()
        results = engine.search(HybridSearchQuery(text=query, limit=10))
        output = []
        for r in results:
            output.append(
                {
                    "entity_id": r.entity_id,
                    "snippet": r.snippet,
                    "score": r.score,
                    "source": f"tier-{r.source_tier}:{r.source_detail}",
                }
            )
        return json.dumps(output, indent=2, default=str)

    @mcp.tool()
    def list_findings(limit: int = 10) -> str:
        """List recent scientific findings from lab memory.

        Args:
            limit: Maximum number of findings to return.
        """
        from labclaw.memory.search import HybridSearchQuery

        engine = _get_search_engine()
        results = engine.search(
            HybridSearchQuery(text="finding discovery hypothesis result", limit=limit)
        )
        output = []
        for r in results:
            output.append(
                {
                    "entity_id": r.entity_id,
                    "snippet": r.snippet,
                    "score": r.score,
                    "source": f"tier-{r.source_tier}:{r.source_detail}",
                }
            )
        return json.dumps(output, indent=2, default=str)

    return mcp


def main() -> None:
    """Run MCP server via stdio transport."""
    server = create_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
