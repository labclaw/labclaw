"""Pattern mining — exhaustive correlation discovery, anomaly detection, temporal patterns.

Spec: docs/specs/L3-discovery.md
Design doc: section 5.3 (Discovery Loop)

Maps to the ASK step of the scientific method:
instead of humans asking questions limited by what they observed,
mine all variable pairs and time scales for statistically significant patterns.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import numpy as np
from pydantic import BaseModel, Field
from scipy import stats as scipy_stats

from labclaw.core.events import event_registry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------


class MiningConfig(BaseModel):
    """Configuration for the pattern mining pipeline."""

    min_sessions: int = 10
    correlation_threshold: float = 0.5
    anomaly_z_threshold: float = 2.0
    feature_columns: list[str] = Field(default_factory=list)


class PatternRecord(BaseModel):
    """A single discovered pattern with evidence and provenance."""

    pattern_id: str = Field(default_factory=_uuid)
    pattern_type: str  # "correlation" | "anomaly" | "temporal" | "cluster"
    description: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    session_ids: list[str] = Field(default_factory=list)
    discovered_at: datetime = Field(default_factory=_now)


class MiningResult(BaseModel):
    """Result of a full mining run."""

    config: MiningConfig
    patterns: list[PatternRecord] = Field(default_factory=list)
    run_at: datetime = Field(default_factory=_now)
    data_summary: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Register events
# ---------------------------------------------------------------------------

_DISCOVERY_EVENTS = [
    "discovery.pattern.found",
    "discovery.mining.completed",
]

for _evt in _DISCOVERY_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


# ---------------------------------------------------------------------------
# PatternMiner
# ---------------------------------------------------------------------------


class PatternMiner:
    """Exhaustive pattern mining across experimental data.

    Spec: docs/specs/L3-discovery.md
    """

    def __init__(self) -> None:
        self.last_result: MiningResult | None = None

    def mine(
        self,
        data: list[dict[str, Any]],
        config: MiningConfig | None = None,
    ) -> MiningResult:
        """Run the full mining pipeline: correlations + anomalies + temporal.

        If len(data) < config.min_sessions, returns empty patterns.
        Emits discovery.mining.completed event.
        """
        cfg = config or MiningConfig()
        numeric_cols = self._detect_numeric_columns(data, cfg.feature_columns)

        summary: dict[str, Any] = {
            "row_count": len(data),
            "numeric_columns": numeric_cols,
            "total_columns": list(data[0].keys()) if data else [],
        }

        patterns: list[PatternRecord] = []

        if len(data) >= cfg.min_sessions:
            patterns.extend(self.find_correlations(data, threshold=cfg.correlation_threshold))
            patterns.extend(self.find_anomalies(data, z_threshold=cfg.anomaly_z_threshold))
            patterns.extend(self.find_temporal_patterns(data))

        result = MiningResult(
            config=cfg,
            patterns=patterns,
            data_summary=summary,
        )

        event_registry.emit(
            "discovery.mining.completed",
            payload={
                "pattern_count": len(patterns),
                "run_at": result.run_at.isoformat(),
            },
        )

        self.last_result = result
        return result

    def find_correlations(
        self,
        data: list[dict[str, Any]],
        threshold: float = 0.5,
    ) -> list[PatternRecord]:
        """Find pairwise Pearson correlations among all numeric columns."""
        if len(data) < 3:
            return []

        numeric_cols = self._detect_numeric_columns(data)
        if len(numeric_cols) < 2:
            return []

        patterns: list[PatternRecord] = []

        for i, col_a in enumerate(numeric_cols):
            for col_b in numeric_cols[i + 1 :]:
                # Build paired observations — only rows where both columns exist
                vals_a: list[float] = []
                vals_b: list[float] = []
                for row in data:
                    if col_a in row and col_b in row:
                        try:
                            val_a = float(row[col_a])
                            val_b = float(row[col_b])
                        except (TypeError, ValueError):
                            continue
                        vals_a.append(val_a)
                        vals_b.append(val_b)

                if len(vals_a) < 3:
                    continue

                r_val, p_val = scipy_stats.pearsonr(vals_a, vals_b)
                r = float(r_val)
                p = float(p_val)

                if abs(r) > threshold:
                    session_ids = [str(row.get("session_id", idx)) for idx, row in enumerate(data)]
                    pattern = PatternRecord(
                        pattern_type="correlation",
                        description=(
                            f"Correlation between {col_a} and {col_b}: r={r:.3f}, p={p:.4f}"
                        ),
                        evidence={
                            "r": float(r),
                            "p_value": float(p),
                            "col_a": col_a,
                            "col_b": col_b,
                            "n": len(vals_a),
                        },
                        confidence=min(abs(r), 1.0),
                        session_ids=session_ids,
                    )
                    patterns.append(pattern)

                    event_registry.emit(
                        "discovery.pattern.found",
                        payload={
                            "pattern_id": pattern.pattern_id,
                            "pattern_type": "correlation",
                            "confidence": float(pattern.confidence),
                        },
                    )

        return patterns

    def find_anomalies(
        self,
        data: list[dict[str, Any]],
        z_threshold: float = 2.0,
    ) -> list[PatternRecord]:
        """Detect anomalous rows via z-score analysis on numeric columns."""
        if len(data) < 3:
            return []

        numeric_cols = self._detect_numeric_columns(data)
        patterns: list[PatternRecord] = []

        for col in numeric_cols:
            indexed_values: list[tuple[int, float]] = []
            for idx, row in enumerate(data):
                if col in row:
                    try:
                        indexed_values.append((idx, float(row[col])))
                    except (ValueError, TypeError):
                        continue
            if len(indexed_values) < 3:
                continue

            values = np.array([v for _, v in indexed_values])
            mean_val = float(np.mean(values))
            std_val = float(np.std(values))

            if std_val == 0.0:
                continue

            anomalous_original: list[int] = []
            z_scores: list[float] = []

            for i, (orig_idx, val) in enumerate(indexed_values):
                z = (val - mean_val) / std_val
                if abs(z) > z_threshold:
                    anomalous_original.append(orig_idx)
                    z_scores.append(float(z))

            if anomalous_original:
                session_ids = [str(data[idx].get("session_id", idx)) for idx in anomalous_original]
                pattern = PatternRecord(
                    pattern_type="anomaly",
                    description=(
                        f"Anomalous values in {col}: "
                        f"{len(anomalous_original)} outlier(s) "
                        f"with |z| > {z_threshold}"
                    ),
                    evidence={
                        "column": col,
                        "anomalous_indices": anomalous_original,
                        "z_scores": z_scores,
                        "mean": float(mean_val),
                        "std": float(std_val),
                        "threshold": float(z_threshold),
                    },
                    confidence=min(max(abs(z) for z in z_scores) / 5.0, 1.0),
                    session_ids=session_ids,
                )
                patterns.append(pattern)

                event_registry.emit(
                    "discovery.pattern.found",
                    payload={
                        "pattern_id": pattern.pattern_id,
                        "pattern_type": "anomaly",
                        "confidence": float(pattern.confidence),
                    },
                )

        return patterns

    def find_temporal_patterns(
        self,
        data: list[dict[str, Any]],
        time_col: str = "timestamp",
    ) -> list[PatternRecord]:
        """Detect temporal trends in numeric data sorted by time column."""
        if len(data) < 4:
            return []

        # Check time column exists
        if not any(time_col in row for row in data):
            return []

        # Sort by time column
        sorted_data = sorted(data, key=lambda r: r.get(time_col, 0))

        numeric_cols = self._detect_numeric_columns(sorted_data)
        patterns: list[PatternRecord] = []

        mid = len(sorted_data) // 2

        for col in numeric_cols:
            if col == time_col:
                continue

            first_half: list[float] = []
            second_half: list[float] = []
            for row in sorted_data[:mid]:
                if col in row:
                    try:
                        first_half.append(float(row[col]))
                    except (TypeError, ValueError):
                        continue
            for row in sorted_data[mid:]:
                if col in row:
                    try:
                        second_half.append(float(row[col]))
                    except (TypeError, ValueError):
                        continue

            if not first_half or not second_half:
                continue

            all_values = np.array(first_half + second_half)
            mean_first = float(np.mean(first_half))
            mean_second = float(np.mean(second_half))
            overall_std = float(np.std(all_values))

            diff = mean_second - mean_first

            if overall_std == 0.0:
                continue

            # Significant trend if |diff| > overall_std
            if abs(diff) > overall_std:
                direction = "increasing" if diff > 0 else "decreasing"
                session_ids = [
                    str(row.get("session_id", idx)) for idx, row in enumerate(sorted_data)
                ]
                confidence = min(abs(diff) / (overall_std * 3.0), 1.0)

                pattern = PatternRecord(
                    pattern_type="temporal",
                    description=(
                        f"Temporal trend in {col}: {direction} "
                        f"(first half mean={mean_first:.3f}, "
                        f"second half mean={mean_second:.3f})"
                    ),
                    evidence={
                        "column": col,
                        "direction": direction,
                        "mean_first_half": float(mean_first),
                        "mean_second_half": float(mean_second),
                        "difference": float(diff),
                        "overall_std": float(overall_std),
                    },
                    confidence=confidence,
                    session_ids=session_ids,
                )
                patterns.append(pattern)

                event_registry.emit(
                    "discovery.pattern.found",
                    payload={
                        "pattern_id": pattern.pattern_id,
                        "pattern_type": "temporal",
                        "confidence": float(pattern.confidence),
                    },
                )

        return patterns

    # ----- Private helpers -----

    @staticmethod
    def _detect_numeric_columns(
        data: list[dict[str, Any]],
        feature_columns: list[str] | None = None,
    ) -> list[str]:
        """Detect numeric columns from the data, or use provided list."""
        if feature_columns:
            return list(feature_columns)

        if not data:
            return []

        sample = data[:5]
        all_cols: set[str] = set()
        for row in sample:
            all_cols.update(row.keys())
        numeric_cols: list[str] = []
        for col in sorted(all_cols):
            numeric_count = sum(
                1
                for row in sample
                if col in row
                and isinstance(row[col], (int, float))
                and not isinstance(row[col], bool)
            )
            if numeric_count > len(sample) / 2:
                numeric_cols.append(col)
        return numeric_cols
