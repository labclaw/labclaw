"""Extended tests for PatternMiner covering correlation, anomaly, and temporal paths."""

from __future__ import annotations

import random

from labclaw.discovery.mining import MiningConfig, PatternMiner, PatternRecord

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _correlated_data(n: int = 20, noise: float = 0.1) -> list[dict]:
    """Return rows where y ≈ 2*x + noise."""
    rng = random.Random(42)
    return [{"x": float(i), "y": 2.0 * i + rng.gauss(0, noise)} for i in range(n)]


def _data_with_outliers(n: int = 20) -> list[dict]:
    """Return rows with one large outlier in column 'value'."""
    rows = [{"value": float(i)} for i in range(n)]
    rows[0] = {"value": 1000.0}  # extreme outlier
    return rows


def _trending_data(n: int = 20) -> list[dict]:
    """Return rows with a temporal trend: metric rises over time."""
    return [{"timestamp": float(i), "metric": float(i) * 3.0} for i in range(n)]


# ---------------------------------------------------------------------------
# MiningConfig defaults
# ---------------------------------------------------------------------------


def test_mining_config_defaults() -> None:
    cfg = MiningConfig()
    assert cfg.min_sessions == 10
    assert cfg.correlation_threshold == 0.5
    assert cfg.anomaly_z_threshold == 2.0
    assert cfg.feature_columns == []


# ---------------------------------------------------------------------------
# mine() — high-level orchestration
# ---------------------------------------------------------------------------


def test_mine_with_correlations() -> None:
    miner = PatternMiner()
    data = _correlated_data(n=30)
    cfg = MiningConfig(min_sessions=10, correlation_threshold=0.5)

    result = miner.mine(data, cfg)

    corr_patterns = [p for p in result.patterns if p.pattern_type == "correlation"]
    assert len(corr_patterns) >= 1
    assert corr_patterns[0].evidence["col_a"] in ("x", "y")
    assert abs(corr_patterns[0].evidence["r"]) > 0.5


def test_mine_with_anomalies() -> None:
    miner = PatternMiner()
    data = _data_with_outliers(n=30)
    cfg = MiningConfig(min_sessions=10, anomaly_z_threshold=2.0)

    result = miner.mine(data, cfg)

    anomaly_patterns = [p for p in result.patterns if p.pattern_type == "anomaly"]
    assert len(anomaly_patterns) >= 1
    assert anomaly_patterns[0].evidence["column"] == "value"


def test_mine_with_temporal_trends() -> None:
    miner = PatternMiner()
    data = _trending_data(n=20)
    cfg = MiningConfig(min_sessions=10)

    result = miner.mine(data, cfg)

    temporal_patterns = [p for p in result.patterns if p.pattern_type == "temporal"]
    assert len(temporal_patterns) >= 1
    assert temporal_patterns[0].evidence["direction"] == "increasing"


def test_mine_insufficient_sessions() -> None:
    miner = PatternMiner()
    data = _correlated_data(n=5)
    cfg = MiningConfig(min_sessions=10)  # more than 5 rows

    result = miner.mine(data, cfg)

    assert result.patterns == []
    assert result.data_summary["row_count"] == 5


def test_mine_empty_data() -> None:
    miner = PatternMiner()
    result = miner.mine([], MiningConfig())
    assert result.patterns == []
    assert result.data_summary["row_count"] == 0


# ---------------------------------------------------------------------------
# find_correlations — edge cases
# ---------------------------------------------------------------------------


def test_find_correlations_too_few_rows() -> None:
    miner = PatternMiner()
    data = [{"x": 1.0, "y": 2.0}, {"x": 2.0, "y": 4.0}]
    assert miner.find_correlations(data) == []


def test_find_correlations_single_column() -> None:
    miner = PatternMiner()
    data = [{"x": float(i)} for i in range(10)]
    assert miner.find_correlations(data) == []


def test_find_correlations_below_threshold() -> None:
    miner = PatternMiner()
    # x and y are independent — use alternating pattern so |r| is near zero
    data = [{"x": float(i % 3), "y": float((i + 1) % 5)} for i in range(20)]
    patterns = miner.find_correlations(data, threshold=0.99)
    assert patterns == []


# ---------------------------------------------------------------------------
# find_anomalies — edge cases
# ---------------------------------------------------------------------------


def test_find_anomalies_too_few_rows() -> None:
    miner = PatternMiner()
    assert miner.find_anomalies([{"v": 1.0}, {"v": 2.0}]) == []


def test_find_anomalies_constant_column() -> None:
    miner = PatternMiner()
    data = [{"v": 5.0} for _ in range(10)]
    # std == 0, should produce no pattern
    assert miner.find_anomalies(data) == []


def test_find_anomalies_returns_pattern_record() -> None:
    miner = PatternMiner()
    data = _data_with_outliers(n=20)
    patterns = miner.find_anomalies(data, z_threshold=2.0)
    assert all(isinstance(p, PatternRecord) for p in patterns)
    assert all(p.pattern_type == "anomaly" for p in patterns)


# ---------------------------------------------------------------------------
# find_temporal_patterns — edge cases
# ---------------------------------------------------------------------------


def test_find_temporal_patterns_too_few_rows() -> None:
    miner = PatternMiner()
    data = [{"timestamp": float(i), "v": float(i)} for i in range(3)]
    assert miner.find_temporal_patterns(data) == []


def test_find_temporal_patterns_no_time_column() -> None:
    miner = PatternMiner()
    data = [{"x": float(i), "v": float(i)} for i in range(10)]
    assert miner.find_temporal_patterns(data, time_col="timestamp") == []


def test_find_temporal_patterns_flat_signal() -> None:
    miner = PatternMiner()
    # flat signal — no trend
    data = [{"timestamp": float(i), "metric": 5.0} for i in range(20)]
    patterns = miner.find_temporal_patterns(data)
    assert patterns == []
