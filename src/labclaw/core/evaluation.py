"""Evaluation harness — offline replay, shadow mode, benchmarking.

Used by evolution engine for BACKTEST and SHADOW stages.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from pydantic import BaseModel, Field

from labclaw.core.events import event_registry

logger = logging.getLogger(__name__)

# Register events
_EVAL_EVENTS = [
    "evolution.eval.replay_started",
    "evolution.eval.replay_completed",
    "evolution.eval.shadow_started",
    "evolution.eval.shadow_completed",
]
for _evt in _EVAL_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


class BenchmarkResult(BaseModel):
    """Result of a benchmark run."""

    dataset: str
    fitness_metrics: dict[str, float] = Field(default_factory=dict)
    duration_seconds: float = 0.0
    config_used: dict[str, Any] = Field(default_factory=dict)
    patterns_found: int = 0
    timestamp: str = ""


class EvaluationHarness:
    """Offline replay, shadow mode, and benchmarking for evolution."""

    def offline_replay(
        self,
        historical_data: list[dict[str, Any]],
        candidate_config: dict[str, Any],
    ) -> dict[str, float]:
        """Replay historical data through candidate pipeline config.

        Used during BACKTEST stage of evolution.
        Returns fitness metrics dict.
        """
        from labclaw.discovery.mining import MiningConfig, PatternMiner

        event_registry.emit(
            "evolution.eval.replay_started",
            payload={"data_points": len(historical_data)},
        )

        start = time.monotonic()
        miner = PatternMiner()

        try:
            config = MiningConfig(**candidate_config)
        except Exception:
            config = MiningConfig()

        result = miner.mine(historical_data, config)
        duration = time.monotonic() - start

        numeric_cols = []
        if historical_data:
            numeric_cols = [k for k, v in historical_data[0].items() if isinstance(v, (int, float))]

        metrics = {
            "pattern_count": float(len(result.patterns)),
            "data_rows": float(len(historical_data)),
            "coverage": (
                float(len(result.patterns)) / max(len(numeric_cols), 1) if numeric_cols else 0.0
            ),
            "replay_duration": duration,
        }

        event_registry.emit(
            "evolution.eval.replay_completed",
            payload={"metrics": metrics},
        )
        return metrics

    def shadow_run(
        self,
        production_config: dict[str, Any],
        candidate_config: dict[str, Any],
        data: list[dict[str, Any]],
    ) -> tuple[dict[str, float], dict[str, float]]:
        """Run both production and candidate configs, compare.

        Used during SHADOW stage of evolution.
        Returns (production_metrics, candidate_metrics).
        """
        event_registry.emit(
            "evolution.eval.shadow_started",
            payload={"data_points": len(data)},
        )

        prod_metrics = self.offline_replay(data, production_config)
        cand_metrics = self.offline_replay(data, candidate_config)

        event_registry.emit(
            "evolution.eval.shadow_completed",
            payload={
                "production": prod_metrics,
                "candidate": cand_metrics,
            },
        )
        return prod_metrics, cand_metrics

    def benchmark(
        self,
        dataset: list[dict[str, Any]],
        dataset_name: str = "default",
        config: dict[str, Any] | None = None,
    ) -> BenchmarkResult:
        """Run a standard benchmark on a dataset."""
        from datetime import UTC, datetime

        start = time.monotonic()
        metrics = self.offline_replay(dataset, config or {})
        duration = time.monotonic() - start

        return BenchmarkResult(
            dataset=dataset_name,
            fitness_metrics=metrics,
            duration_seconds=duration,
            config_used=config or {},
            patterns_found=int(metrics.get("pattern_count", 0)),
            timestamp=datetime.now(UTC).isoformat(),
        )
