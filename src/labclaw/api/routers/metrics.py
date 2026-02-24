"""Prometheus-compatible metrics endpoint.

Serves plain-text metrics without requiring the ``prometheus_client``
dependency.  Each metric follows the Prometheus exposition format:
``# HELP``, ``# TYPE``, then value lines.
"""

from __future__ import annotations

import time

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from labclaw.api.deps import get_evolution_engine, get_pattern_miner

router = APIRouter()

_START_TIME = time.monotonic()


def _collect() -> str:
    lines: list[str] = []

    # -- patterns discovered ------------------------------------------------
    try:
        miner = get_pattern_miner()
        # Use last_result if available (set after mine()), not internal _cache
        last = getattr(miner, "last_result", None)
        pattern_count = len(last.patterns) if last is not None else 0
    except Exception:
        pattern_count = 0
    lines.append("# HELP labclaw_patterns_discovered_total Total patterns discovered")
    lines.append("# TYPE labclaw_patterns_discovered_total counter")
    lines.append(f"labclaw_patterns_discovered_total {pattern_count}")

    # -- hypotheses generated (placeholder) ---------------------------------
    lines.append("# HELP labclaw_hypotheses_generated_total Total hypotheses generated")
    lines.append("# TYPE labclaw_hypotheses_generated_total counter")
    lines.append("labclaw_hypotheses_generated_total 0")

    # -- evolution cycles ----------------------------------------------------
    try:
        engine = get_evolution_engine()
        history = engine.get_history()
        promoted = sum(1 for c in history if c.promoted)
        rolled_back = sum(1 for c in history if c.rollback_reason is not None)
        active = sum(
            1 for c in history
            if not c.promoted and c.rollback_reason is None
        )
    except Exception:
        promoted = rolled_back = active = 0
    lines.append("# HELP labclaw_evolution_cycles_total Evolution cycles by status")
    lines.append("# TYPE labclaw_evolution_cycles_total counter")
    lines.append(f'labclaw_evolution_cycles_total{{status="promoted"}} {promoted}')
    lines.append(f'labclaw_evolution_cycles_total{{status="rolled_back"}} {rolled_back}')
    lines.append(f'labclaw_evolution_cycles_total{{status="active"}} {active}')

    # -- data rows ingested (placeholder — daemon tracks this) ---------------
    lines.append("# HELP labclaw_data_rows_ingested_total Total data rows ingested")
    lines.append("# TYPE labclaw_data_rows_ingested_total counter")
    lines.append("labclaw_data_rows_ingested_total 0")

    # -- uptime --------------------------------------------------------------
    uptime = round(time.monotonic() - _START_TIME, 2)
    lines.append("# HELP labclaw_uptime_seconds Seconds since process start")
    lines.append("# TYPE labclaw_uptime_seconds gauge")
    lines.append(f"labclaw_uptime_seconds {uptime}")

    # -- discovery cycle duration (placeholder) ------------------------------
    lines.append(
        "# HELP labclaw_discovery_cycle_duration_seconds Discovery cycle duration"
    )
    lines.append("# TYPE labclaw_discovery_cycle_duration_seconds summary")
    lines.append("labclaw_discovery_cycle_duration_seconds_count 0")
    lines.append("labclaw_discovery_cycle_duration_seconds_sum 0")

    lines.append("")  # trailing newline
    return "\n".join(lines)


@router.get("/metrics")
def metrics() -> PlainTextResponse:
    return PlainTextResponse(content=_collect(), media_type="text/plain; charset=utf-8")
