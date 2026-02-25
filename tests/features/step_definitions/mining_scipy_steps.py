"""BDD step definitions for scipy/numpy-based pattern mining.

Covers the refactored PatternMiner that uses scipy.stats.pearsonr
and numpy z-scores directly (no pure-Python fallbacks).
"""

from __future__ import annotations

import random
from typing import Any

from pytest_bdd import given, parsers, then, when

from labclaw.discovery.mining import (
    MiningConfig,
    MiningResult,
    PatternMiner,
    PatternRecord,
)


# ---------------------------------------------------------------------------
# Additional data fixtures (new; existing ones live in discovery_steps.py)
# ---------------------------------------------------------------------------


@given("empty mining data", target_fixture="exp_data")
def empty_mining_data() -> list[dict[str, Any]]:
    """Zero-row dataset."""
    return []


@given(
    parsers.parse("experimental data with {n:d} rows and a single numeric column"),
    target_fixture="exp_data",
)
def data_with_single_numeric_col(n: int) -> list[dict[str, Any]]:
    """Only one numeric column — Pearson r is impossible, but anomalies are possible."""
    rng = random.Random(42)
    data: list[dict[str, Any]] = []
    for i in range(n):
        val = rng.gauss(10.0, 2.0)
        data.append({"value": val, "label": f"item_{i}", "session_id": f"s{i}"})
    return data


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when(
    parsers.parse("I find correlations again with threshold {threshold:f}"),
    target_fixture="correlation_patterns_2",
)
def find_correlations_again(
    miner: PatternMiner,
    exp_data: list[dict[str, Any]],
    threshold: float,
) -> list[PatternRecord]:
    """Second independent call — used to verify reproducibility."""
    return miner.find_correlations(exp_data, threshold=threshold)


@when("I create a default MiningConfig", target_fixture="default_config")
def create_default_config() -> MiningConfig:
    return MiningConfig()


# ---------------------------------------------------------------------------
# Then steps — scipy Pearson correlation evidence
# ---------------------------------------------------------------------------


@then("the correlation evidence includes a p_value field")
def check_correlation_has_p_value(correlation_patterns: list[PatternRecord]) -> None:
    assert correlation_patterns, "No correlation patterns found"
    for p in correlation_patterns:
        assert "p_value" in p.evidence, (
            f"Correlation pattern missing p_value field: {p.evidence}"
        )


@then("both runs return the same number of patterns")
def check_correlation_reproducible(
    correlation_patterns: list[PatternRecord],
    correlation_patterns_2: list[PatternRecord],
) -> None:
    assert len(correlation_patterns) == len(correlation_patterns_2), (
        f"Run 1: {len(correlation_patterns)} patterns, "
        f"Run 2: {len(correlation_patterns_2)} patterns — not reproducible"
    )


@then("every correlation pattern has r between -1.0 and 1.0")
def check_correlation_r_range(correlation_patterns: list[PatternRecord]) -> None:
    for p in correlation_patterns:
        r = p.evidence.get("r", None)
        assert r is not None, f"Pattern missing 'r' in evidence: {p.evidence}"
        assert -1.0 <= r <= 1.0, f"r={r} is outside [-1, 1]"


# ---------------------------------------------------------------------------
# Then steps — numpy anomaly evidence
# ---------------------------------------------------------------------------


@then("the anomaly evidence includes mean and std fields")
def check_anomaly_has_mean_and_std(anomaly_patterns: list[PatternRecord]) -> None:
    assert anomaly_patterns, "No anomaly patterns found"
    for p in anomaly_patterns:
        assert "mean" in p.evidence, f"Anomaly missing 'mean': {p.evidence}"
        assert "std" in p.evidence, f"Anomaly missing 'std': {p.evidence}"


@then("every anomaly pattern has confidence between 0.0 and 1.0")
def check_anomaly_confidence_clamped(anomaly_patterns: list[PatternRecord]) -> None:
    assert anomaly_patterns, "No anomaly patterns found"
    for p in anomaly_patterns:
        assert 0.0 <= p.confidence <= 1.0, (
            f"Confidence {p.confidence} out of [0, 1]"
        )


# ---------------------------------------------------------------------------
# Then steps — temporal evidence
# ---------------------------------------------------------------------------


@then("the temporal evidence includes direction and half means")
def check_temporal_evidence_fields(temporal_patterns: list[PatternRecord]) -> None:
    assert temporal_patterns, "No temporal patterns found"
    for p in temporal_patterns:
        ev = p.evidence
        assert "direction" in ev, f"Temporal evidence missing 'direction': {ev}"
        assert "mean_first_half" in ev, f"Temporal evidence missing 'mean_first_half': {ev}"
        assert "mean_second_half" in ev, f"Temporal evidence missing 'mean_second_half': {ev}"


# ---------------------------------------------------------------------------
# Then steps — MiningConfig defaults
# ---------------------------------------------------------------------------


@then(parsers.parse("the default min_sessions is {value:d}"))
def check_default_min_sessions(default_config: MiningConfig, value: int) -> None:
    assert default_config.min_sessions == value, (
        f"Expected min_sessions={value}, got {default_config.min_sessions}"
    )


@then(parsers.parse("the default correlation_threshold is {value:f}"))
def check_default_correlation_threshold(default_config: MiningConfig, value: float) -> None:
    assert abs(default_config.correlation_threshold - value) < 1e-9, (
        f"Expected correlation_threshold={value}, got {default_config.correlation_threshold}"
    )


@then(parsers.parse("the default anomaly_z_threshold is {value:f}"))
def check_default_anomaly_z_threshold(default_config: MiningConfig, value: float) -> None:
    assert abs(default_config.anomaly_z_threshold - value) < 1e-9, (
        f"Expected anomaly_z_threshold={value}, got {default_config.anomaly_z_threshold}"
    )


@then("the default feature_columns is empty")
def check_default_feature_columns_empty(default_config: MiningConfig) -> None:
    assert default_config.feature_columns == [], (
        f"Expected empty feature_columns, got {default_config.feature_columns}"
    )


@then(parsers.parse("the MiningResult config min_sessions is {value:d}"))
def check_result_config_min_sessions(mining_result: MiningResult, value: int) -> None:
    assert mining_result.config.min_sessions == value, (
        f"Expected config.min_sessions={value}, got {mining_result.config.min_sessions}"
    )


# ---------------------------------------------------------------------------
# Then steps — MiningResult data_summary
# ---------------------------------------------------------------------------


@then("the data_summary contains row_count")
def check_summary_has_row_count(mining_result: MiningResult) -> None:
    assert "row_count" in mining_result.data_summary, (
        f"data_summary missing 'row_count': {mining_result.data_summary}"
    )


@then("the data_summary contains numeric_columns")
def check_summary_has_numeric_columns(mining_result: MiningResult) -> None:
    assert "numeric_columns" in mining_result.data_summary, (
        f"data_summary missing 'numeric_columns': {mining_result.data_summary}"
    )


@then(parsers.parse("the data_summary row_count is {value:d}"))
def check_summary_row_count_value(mining_result: MiningResult, value: int) -> None:
    actual = mining_result.data_summary.get("row_count")
    assert actual == value, f"Expected row_count={value}, got {actual}"


@then("the miner last_result is set")
def check_miner_last_result(miner: PatternMiner, mining_result: MiningResult) -> None:
    assert miner.last_result is not None, "miner.last_result is None after mine()"
    assert miner.last_result is mining_result, (
        "miner.last_result is not the returned MiningResult"
    )


# ---------------------------------------------------------------------------
# Then steps — edge cases
# ---------------------------------------------------------------------------


@then("no correlation patterns are in the result")
def check_no_correlation_patterns(mining_result: MiningResult) -> None:
    correlation_patterns = [p for p in mining_result.patterns if p.pattern_type == "correlation"]
    assert correlation_patterns == [], (
        f"Expected no correlation patterns, got {correlation_patterns}"
    )
