"""BDD step definitions for L3 Discovery (ASK -> HYPOTHESIZE).

Spec: docs/specs/L3-discovery.md
Uses conftest fixtures: event_capture
"""

from __future__ import annotations

import random
from typing import Any

from pytest_bdd import given, parsers, then, when

from labclaw.core.events import event_registry
from labclaw.discovery.hypothesis import (
    HypothesisGenerator,
    HypothesisInput,
    HypothesisOutput,
)
from labclaw.discovery.mining import (
    MiningConfig,
    MiningResult,
    PatternMiner,
    PatternRecord,
)

# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------


@given("the pattern miner is initialized", target_fixture="miner")
def pattern_miner_initialized(event_capture: object) -> PatternMiner:
    """Provide a PatternMiner and subscribe event capture."""
    for evt_name in [
        "discovery.pattern.found",
        "discovery.mining.completed",
        "discovery.hypothesis.created",
    ]:
        event_registry.subscribe(evt_name, event_capture)  # type: ignore[arg-type]
    return PatternMiner()


@given("the hypothesis generator is initialized", target_fixture="generator")
def hypothesis_generator_initialized() -> HypothesisGenerator:
    return HypothesisGenerator()


# ---------------------------------------------------------------------------
# Data fixtures
# ---------------------------------------------------------------------------


@given(
    parsers.parse('experimental data with columns "{col1}", "{col2}", "{col3}"'),
    target_fixture="exp_data",
)
def experimental_data_columns(col1: str, col2: str, col3: str) -> list[dict[str, Any]]:
    """Create a base data frame with 3 named columns (empty, to be filled by next step)."""
    # Return placeholder; next step will replace with correlated data
    return [{col1: 0.0, col2: 0.0, col3: 0.0, "session_id": f"s{i}"} for i in range(20)]


@given(
    parsers.parse("{n:d} rows where speed and accuracy are strongly correlated"),
    target_fixture="exp_data",
)
def rows_with_strong_correlation(n: int) -> list[dict[str, Any]]:
    """Generate data where speed and accuracy are strongly correlated."""
    rng = random.Random(42)
    data: list[dict[str, Any]] = []
    for i in range(n):
        speed = 10.0 + i * 0.5 + rng.gauss(0, 0.3)
        # accuracy strongly tracks speed
        accuracy = 50.0 + speed * 2.0 + rng.gauss(0, 0.5)
        temperature = 22.0 + rng.gauss(0, 1.0)
        data.append(
            {
                "speed": speed,
                "accuracy": accuracy,
                "temperature": temperature,
                "session_id": f"s{i}",
            }
        )
    return data


@given(
    parsers.parse(
        "experimental data with {n_normal:d} normal rows and {n_anomaly:d} "
        'anomalous rows for column "{column}"'
    ),
    target_fixture="exp_data",
)
def data_with_anomalies(n_normal: int, n_anomaly: int, column: str) -> list[dict[str, Any]]:
    """Generate data with normal values and outliers."""
    rng = random.Random(42)
    data: list[dict[str, Any]] = []

    # Normal rows: mean=100, std=5
    for i in range(n_normal):
        data.append(
            {
                column: 100.0 + rng.gauss(0, 5.0),
                "session_id": f"s{i}",
            }
        )

    # Anomalous rows: far from the mean (mean + 5*std = 125)
    for i in range(n_anomaly):
        data.append(
            {
                column: 100.0 + 50.0 + rng.gauss(0, 1.0),
                "session_id": f"s{n_normal + i}",
            }
        )

    return data


@given(
    "experimental data with correlations and anomalies",
    target_fixture="exp_data",
)
def data_with_correlations_and_anomalies() -> list[dict[str, Any]]:
    """Generate data that has both correlations and anomalies."""
    rng = random.Random(42)
    data: list[dict[str, Any]] = []

    for i in range(20):
        x = 10.0 + i * 0.5 + rng.gauss(0, 0.3)
        y = 50.0 + x * 2.0 + rng.gauss(0, 0.5)
        data.append(
            {
                "x": x,
                "y": y,
                "z": 5.0 + rng.gauss(0, 1.0),
                "session_id": f"s{i}",
                "timestamp": i,
            }
        )

    # Add anomaly in z
    data[18]["z"] = 50.0
    data[19]["z"] = -40.0

    return data


@given(
    parsers.parse("experimental data with only {n:d} rows"),
    target_fixture="exp_data",
)
def data_with_few_rows(n: int) -> list[dict[str, Any]]:
    """Generate minimal data."""
    return [{"x": float(i), "y": float(i * 2), "session_id": f"s{i}"} for i in range(n)]


@given(
    parsers.parse("{n:d} correlation patterns exist"),
    target_fixture="existing_patterns",
)
def correlation_patterns_exist(n: int) -> list[PatternRecord]:
    """Create pre-built correlation patterns."""
    patterns: list[PatternRecord] = []
    for i in range(n):
        patterns.append(
            PatternRecord(
                pattern_type="correlation",
                description=f"Correlation between col_{i}_a and col_{i}_b: r=0.85, p=0.001",
                evidence={
                    "r": 0.85,
                    "p_value": 0.001,
                    "col_a": f"col_{i}_a",
                    "col_b": f"col_{i}_b",
                    "n": 20,
                },
                confidence=0.85,
                session_ids=[f"s{j}" for j in range(20)],
            )
        )
    return patterns


# ---------------------------------------------------------------------------
# New data fixtures for expanded scenarios
# ---------------------------------------------------------------------------


@given(
    parsers.parse('experimental data with an increasing temporal trend for column "{col}"'),
    target_fixture="exp_data",
)
def data_with_increasing_trend(col: str) -> list[dict[str, Any]]:
    """Generate 20 rows with a strong increasing trend in col."""
    rng = random.Random(7)
    data: list[dict[str, Any]] = []
    for i in range(20):
        # Strong upward trend; second half mean >> first half mean by > overall std
        data.append(
            {
                col: float(i) * 3.0 + rng.gauss(0, 0.5),
                "timestamp": i,
                "session_id": f"s{i}",
            }
        )
    return data


@given(
    parsers.parse('experimental data with a decreasing temporal trend for column "{col}"'),
    target_fixture="exp_data",
)
def data_with_decreasing_trend(col: str) -> list[dict[str, Any]]:
    """Generate 20 rows with a strong decreasing trend in col."""
    rng = random.Random(7)
    data: list[dict[str, Any]] = []
    for i in range(20):
        data.append(
            {
                col: 60.0 - float(i) * 3.0 + rng.gauss(0, 0.5),
                "timestamp": i,
                "session_id": f"s{i}",
            }
        )
    return data


@given(
    parsers.parse("experimental data with no timestamp column and {n:d} rows"),
    target_fixture="exp_data",
)
def data_without_timestamp(n: int) -> list[dict[str, Any]]:
    """Generate data rows without a timestamp column."""
    rng = random.Random(42)
    return [
        {"x": rng.gauss(0, 1.0), "y": rng.gauss(0, 1.0), "session_id": f"s{i}"} for i in range(n)
    ]


@given(
    parsers.parse("experimental data with {n:d} rows where all values are identical"),
    target_fixture="exp_data",
)
def data_with_identical_values(n: int) -> list[dict[str, Any]]:
    """All rows have the same value — std=0, no correlations possible."""
    return [{"x": 5.0, "y": 3.0, "session_id": f"s{i}"} for i in range(n)]


@given(
    parsers.parse("experimental data with {n:d} rows of weakly correlated columns"),
    target_fixture="exp_data",
)
def data_with_weak_correlation(n: int) -> list[dict[str, Any]]:
    """Columns with r << 0.8 threshold."""
    rng = random.Random(99)
    return [
        {"x": rng.gauss(0, 1.0), "y": rng.gauss(0, 1.0), "session_id": f"s{i}"} for i in range(n)
    ]


@given(
    "experimental data with mixed columns including non-numeric",
    target_fixture="exp_data",
)
def data_with_mixed_columns() -> list[dict[str, Any]]:
    """Data with numeric and string columns."""
    rng = random.Random(42)
    data: list[dict[str, Any]] = []
    for i in range(15):
        x = float(i) + rng.gauss(0, 0.1)
        y = x * 2.0 + rng.gauss(0, 0.2)
        data.append(
            {
                "x": x,
                "y": y,
                "label": f"group_{i % 3}",
                "session_id": f"s{i}",
            }
        )
    return data


@given(
    parsers.parse("experimental data with {n:d} rows containing string columns"),
    target_fixture="exp_data",
)
def data_with_string_columns(n: int) -> list[dict[str, Any]]:
    """Data where one column is string — should be ignored by miner."""
    rng = random.Random(42)
    data: list[dict[str, Any]] = []
    for i in range(n):
        data.append(
            {
                "numeric_a": rng.gauss(10, 2),
                "numeric_b": rng.gauss(5, 1),
                "label": f"cat_{i % 4}",
                "session_id": f"s{i}",
            }
        )
    return data


@given(
    parsers.parse('experimental data with {n:d} identical values in column "{col}"'),
    target_fixture="exp_data",
)
def data_with_identical_column(n: int, col: str) -> list[dict[str, Any]]:
    """All values in col are the same — std=0, no anomalies possible."""
    rng = random.Random(42)
    return [{col: 42.0, "other": rng.gauss(0, 1.0), "session_id": f"s{i}"} for i in range(n)]


@given(
    parsers.parse('experimental data with {n:d} identical single-column values in column "{col}"'),
    target_fixture="exp_data",
)
def data_with_identical_single_column(n: int, col: str) -> list[dict[str, Any]]:
    """Only one numeric column, all values identical — std=0, no anomalies possible."""
    return [{col: 42.0, "session_id": f"s{i}"} for i in range(n)]


@given(
    parsers.parse("experimental data with {n:d} rows where some rows have missing values"),
    target_fixture="exp_data",
)
def data_with_missing_values(n: int) -> list[dict[str, Any]]:
    """Some rows have missing 'b' column."""
    rng = random.Random(42)
    data: list[dict[str, Any]] = []
    for i in range(n):
        row: dict[str, Any] = {"a": rng.gauss(10, 2), "session_id": f"s{i}"}
        if i % 5 != 0:  # 4 out of 5 rows have 'b'
            row["b"] = row["a"] * 1.5 + rng.gauss(0, 0.5)
        data.append(row)
    return data


@given(
    parsers.parse("{n:d} anomaly pattern exists"),
    target_fixture="existing_patterns",
)
def anomaly_patterns_exist(n: int) -> list[PatternRecord]:
    """Create pre-built anomaly patterns."""
    patterns: list[PatternRecord] = []
    for i in range(n):
        patterns.append(
            PatternRecord(
                pattern_type="anomaly",
                description=f"Anomalous values in col_{i}: 2 outlier(s)",
                evidence={
                    "column": f"col_{i}",
                    "anomalous_indices": [5, 12],
                    "z_scores": [3.2, -3.5],
                    "mean": 10.0,
                    "std": 2.0,
                    "threshold": 2.0,
                },
                confidence=0.7,
                session_ids=["s5", "s12"],
            )
        )
    return patterns


@given(
    parsers.parse("{n:d} temporal pattern exists"),
    target_fixture="existing_patterns",
)
def temporal_patterns_exist(n: int) -> list[PatternRecord]:
    """Create pre-built temporal patterns."""
    patterns: list[PatternRecord] = []
    for i in range(n):
        patterns.append(
            PatternRecord(
                pattern_type="temporal",
                description=f"Temporal trend in col_{i}: increasing",
                evidence={
                    "column": f"col_{i}",
                    "direction": "increasing",
                    "mean_first_half": 10.0,
                    "mean_second_half": 25.0,
                    "difference": 15.0,
                    "overall_std": 5.0,
                },
                confidence=0.8,
                session_ids=[f"s{j}" for j in range(10)],
            )
        )
    return patterns


@given(
    parsers.parse("{n:d} cluster pattern exists"),
    target_fixture="existing_patterns",
)
def cluster_patterns_exist(n: int) -> list[PatternRecord]:
    """Create pre-built cluster patterns."""
    patterns: list[PatternRecord] = []
    for i in range(n):
        patterns.append(
            PatternRecord(
                pattern_type="cluster",
                description=f"Found 3 clusters in data (run {i})",
                evidence={
                    "n_clusters": 3,
                    "cluster_sizes": {0: 10, 1: 10, 2: 10},
                    "inertia": 5.0,
                    "method": "kmeans",
                },
                confidence=0.75,
                session_ids=[f"s{j}" for j in range(30)],
            )
        )
    return patterns


@given(
    parsers.parse("{n:d} unknown pattern type exists"),
    target_fixture="existing_patterns",
)
def unknown_patterns_exist(n: int) -> list[PatternRecord]:
    """Create patterns with unrecognized type."""
    patterns: list[PatternRecord] = []
    for i in range(n):
        patterns.append(
            PatternRecord(
                pattern_type="unknown_type",
                description=f"Unknown pattern {i}",
                evidence={},
                confidence=0.5,
            )
        )
    return patterns


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when(
    parsers.parse("I find correlations with threshold {threshold:f}"),
    target_fixture="correlation_patterns",
)
def find_correlations(
    miner: PatternMiner, exp_data: list[dict[str, Any]], threshold: float
) -> list[PatternRecord]:
    return miner.find_correlations(exp_data, threshold=threshold)


@when(
    parsers.parse("I find anomalies with z-threshold {z_threshold:f}"),
    target_fixture="anomaly_patterns",
)
def find_anomalies(
    miner: PatternMiner, exp_data: list[dict[str, Any]], z_threshold: float
) -> list[PatternRecord]:
    return miner.find_anomalies(exp_data, z_threshold=z_threshold)


@when(
    "I run the full mining pipeline",
    target_fixture="mining_result",
)
def run_full_mining(miner: PatternMiner, exp_data: list[dict[str, Any]]) -> MiningResult:
    return miner.mine(exp_data)


@when(
    parsers.parse("I run the full mining pipeline with min_sessions {min_sessions:d}"),
    target_fixture="mining_result",
)
def run_mining_with_min_sessions(
    miner: PatternMiner, exp_data: list[dict[str, Any]], min_sessions: int
) -> MiningResult:
    config = MiningConfig(min_sessions=min_sessions)
    return miner.mine(exp_data, config=config)


@when(
    parsers.parse('I run the full mining pipeline with feature_columns "{col1}" and "{col2}"'),
    target_fixture="mining_result",
)
def run_mining_with_feature_columns(
    miner: PatternMiner, exp_data: list[dict[str, Any]], col1: str, col2: str
) -> MiningResult:
    config = MiningConfig(feature_columns=[col1, col2], min_sessions=5)
    return miner.mine(exp_data, config=config)


@when(
    "I find temporal patterns",
    target_fixture="temporal_patterns",
)
def find_temporal_patterns(
    miner: PatternMiner, exp_data: list[dict[str, Any]]
) -> list[PatternRecord]:
    return miner.find_temporal_patterns(exp_data)


@when(
    "I generate hypotheses",
    target_fixture="hypotheses",
)
def generate_hypotheses(
    generator: HypothesisGenerator, existing_patterns: list[PatternRecord]
) -> list[HypothesisOutput]:
    inp = HypothesisInput(patterns=existing_patterns)
    return generator.generate(inp)


# ---------------------------------------------------------------------------
# Then steps — correlations
# ---------------------------------------------------------------------------


@then(
    parsers.parse("at least {count:d} correlation pattern is found"),
)
def check_correlation_count(correlation_patterns: list[PatternRecord], count: int) -> None:
    assert len(correlation_patterns) >= count, (
        f"Expected >= {count} correlation patterns, got {len(correlation_patterns)}"
    )


@then(
    parsers.parse('the pattern describes "{col_a}" and "{col_b}"'),
)
def check_pattern_columns(
    correlation_patterns: list[PatternRecord],
    col_a: str,
    col_b: str,
) -> None:
    found = False
    for p in correlation_patterns:
        ev = p.evidence
        if (ev.get("col_a") == col_a and ev.get("col_b") == col_b) or (
            ev.get("col_a") == col_b and ev.get("col_b") == col_a
        ):
            found = True
            break
    assert found, (
        f"No pattern found describing {col_a!r} and {col_b!r}. "
        f"Patterns: {[p.evidence for p in correlation_patterns]}"
    )


@then(parsers.parse("{count:d} correlation patterns are found"))
def check_zero_correlations(correlation_patterns: list[PatternRecord], count: int) -> None:
    assert len(correlation_patterns) == count, (
        f"Expected {count} correlation patterns, got {len(correlation_patterns)}"
    )


# ---------------------------------------------------------------------------
# Then steps — anomalies
# ---------------------------------------------------------------------------


@then(
    parsers.parse("at least {count:d} anomaly pattern is found"),
)
def check_anomaly_count(anomaly_patterns: list[PatternRecord], count: int) -> None:
    assert len(anomaly_patterns) >= count, (
        f"Expected >= {count} anomaly patterns, got {len(anomaly_patterns)}"
    )


@then("the anomaly references the outlier rows")
def check_anomaly_references_outliers(anomaly_patterns: list[PatternRecord]) -> None:
    for p in anomaly_patterns:
        assert p.evidence.get("anomalous_indices"), (
            f"Anomaly pattern missing anomalous_indices: {p.evidence}"
        )
        assert p.session_ids, "Anomaly pattern has empty session_ids"


@then(parsers.parse("{count:d} anomaly patterns are found"))
def check_zero_anomalies(anomaly_patterns: list[PatternRecord], count: int) -> None:
    assert len(anomaly_patterns) == count, (
        f"Expected {count} anomaly patterns, got {len(anomaly_patterns)}"
    )


# ---------------------------------------------------------------------------
# Then steps — temporal patterns
# ---------------------------------------------------------------------------


@then(parsers.parse("at least {count:d} temporal pattern is found"))
def check_temporal_count(temporal_patterns: list[PatternRecord], count: int) -> None:
    assert len(temporal_patterns) >= count, (
        f"Expected >= {count} temporal patterns, got {len(temporal_patterns)}"
    )


@then(parsers.parse("{count:d} temporal patterns are found"))
def check_zero_temporal(temporal_patterns: list[PatternRecord], count: int) -> None:
    assert len(temporal_patterns) == count, (
        f"Expected {count} temporal patterns, got {len(temporal_patterns)}"
    )


@then(parsers.parse('the temporal pattern direction is "{direction}"'))
def check_temporal_direction(temporal_patterns: list[PatternRecord], direction: str) -> None:
    assert temporal_patterns, "No temporal patterns found"
    found = any(p.evidence.get("direction") == direction for p in temporal_patterns)
    assert found, (
        f"Expected direction {direction!r} in patterns: "
        f"{[p.evidence.get('direction') for p in temporal_patterns]}"
    )


# ---------------------------------------------------------------------------
# Then steps — mining result
# ---------------------------------------------------------------------------


@then("a MiningResult is returned with patterns")
def check_mining_result_has_patterns(mining_result: MiningResult) -> None:
    assert mining_result.patterns, "MiningResult has no patterns"
    assert mining_result.config is not None
    assert mining_result.data_summary


@then(
    parsers.parse("the MiningResult has {count:d} patterns"),
)
def check_mining_result_pattern_count(mining_result: MiningResult, count: int) -> None:
    assert len(mining_result.patterns) == count, (
        f"Expected {count} patterns, got {len(mining_result.patterns)}"
    )


@then("the MiningResult only includes patterns for specified columns")
def check_mining_result_custom_columns(mining_result: MiningResult) -> None:
    # With feature_columns=['x','y'], any correlation or temporal pattern
    # should only reference those columns
    for p in mining_result.patterns:
        if p.pattern_type == "correlation":
            ev = p.evidence
            assert ev.get("col_a") in {"x", "y"} and ev.get("col_b") in {"x", "y"}, (
                f"Unexpected columns in correlation: {ev}"
            )


@then("the MiningResult does not include string column patterns")
def check_no_string_column_patterns(mining_result: MiningResult) -> None:
    for p in mining_result.patterns:
        if p.pattern_type == "correlation":
            ev = p.evidence
            assert ev.get("col_a") != "label" and ev.get("col_b") != "label"
        if p.pattern_type == "anomaly":
            assert p.evidence.get("column") != "label"


@then("the miner runs without error")
def check_miner_no_error(correlation_patterns: list[PatternRecord]) -> None:
    # Just verifying the call didn't raise an exception
    assert isinstance(correlation_patterns, list)


# ---------------------------------------------------------------------------
# Then steps — hypotheses
# ---------------------------------------------------------------------------


@then(
    parsers.parse("at least {count:d} hypotheses are generated"),
)
def check_hypothesis_count(hypotheses: list[HypothesisOutput], count: int) -> None:
    assert len(hypotheses) >= count, f"Expected >= {count} hypotheses, got {len(hypotheses)}"


@then(parsers.parse("at least {count:d} hypothesis is generated"))
def check_hypothesis_count_singular(hypotheses: list[HypothesisOutput], count: int) -> None:
    assert len(hypotheses) >= count, f"Expected >= {count} hypotheses, got {len(hypotheses)}"


@then(parsers.parse("{count:d} hypotheses are generated"))
def check_hypothesis_count_exact(hypotheses: list[HypothesisOutput], count: int) -> None:
    assert len(hypotheses) == count, f"Expected {count} hypotheses, got {len(hypotheses)}"


@then("each hypothesis has a statement")
def check_hypothesis_statements(hypotheses: list[HypothesisOutput]) -> None:
    for h in hypotheses:
        assert h.statement, f"Hypothesis {h.hypothesis_id} has empty statement"


@then("each hypothesis is marked as testable")
def check_hypothesis_testable(hypotheses: list[HypothesisOutput]) -> None:
    for h in hypotheses:
        assert h.testable, f"Hypothesis {h.hypothesis_id} is not testable"


@then(parsers.parse('the hypothesis mentions "{keyword}"'))
def check_hypothesis_keyword(hypotheses: list[HypothesisOutput], keyword: str) -> None:
    assert hypotheses, "No hypotheses to check"
    found = any(keyword in h.statement for h in hypotheses)
    assert found, (
        f"No hypothesis mentions {keyword!r}. Statements: {[h.statement[:80] for h in hypotheses]}"
    )
