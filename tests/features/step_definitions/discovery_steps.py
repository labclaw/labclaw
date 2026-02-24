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
    parsers.parse(
        'experimental data with columns "{col1}", "{col2}", "{col3}"'
    ),
    target_fixture="exp_data",
)
def experimental_data_columns(col1: str, col2: str, col3: str) -> list[dict[str, Any]]:
    """Create a base data frame with 3 named columns (empty, to be filled by next step)."""
    # Return placeholder; next step will replace with correlated data
    return [
        {col1: 0.0, col2: 0.0, col3: 0.0, "session_id": f"s{i}"}
        for i in range(20)
    ]


@given(
    parsers.parse(
        "{n:d} rows where speed and accuracy are strongly correlated"
    ),
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
        data.append({
            "speed": speed,
            "accuracy": accuracy,
            "temperature": temperature,
            "session_id": f"s{i}",
        })
    return data


@given(
    parsers.parse(
        "experimental data with {n_normal:d} normal rows and {n_anomaly:d} "
        'anomalous rows for column "{column}"'
    ),
    target_fixture="exp_data",
)
def data_with_anomalies(
    n_normal: int, n_anomaly: int, column: str
) -> list[dict[str, Any]]:
    """Generate data with normal values and outliers."""
    rng = random.Random(42)
    data: list[dict[str, Any]] = []

    # Normal rows: mean=100, std=5
    for i in range(n_normal):
        data.append({
            column: 100.0 + rng.gauss(0, 5.0),
            "session_id": f"s{i}",
        })

    # Anomalous rows: far from the mean (mean + 5*std = 125)
    for i in range(n_anomaly):
        data.append({
            column: 100.0 + 50.0 + rng.gauss(0, 1.0),
            "session_id": f"s{n_normal + i}",
        })

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
        data.append({
            "x": x,
            "y": y,
            "z": 5.0 + rng.gauss(0, 1.0),
            "session_id": f"s{i}",
            "timestamp": i,
        })

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
    return [
        {"x": float(i), "y": float(i * 2), "session_id": f"s{i}"}
        for i in range(n)
    ]


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
def run_full_mining(
    miner: PatternMiner, exp_data: list[dict[str, Any]]
) -> MiningResult:
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
    correlation_patterns: list[PatternRecord], col_a: str, col_b: str,
) -> None:
    found = False
    for p in correlation_patterns:
        ev = p.evidence
        if (
            (ev.get("col_a") == col_a and ev.get("col_b") == col_b)
            or (ev.get("col_a") == col_b and ev.get("col_b") == col_a)
        ):
            found = True
            break
    assert found, (
        f"No pattern found describing {col_a!r} and {col_b!r}. "
        f"Patterns: {[p.evidence for p in correlation_patterns]}"
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


# ---------------------------------------------------------------------------
# Then steps — hypotheses
# ---------------------------------------------------------------------------


@then(
    parsers.parse("at least {count:d} hypotheses are generated"),
)
def check_hypothesis_count(hypotheses: list[HypothesisOutput], count: int) -> None:
    assert len(hypotheses) >= count, (
        f"Expected >= {count} hypotheses, got {len(hypotheses)}"
    )


@then("each hypothesis has a statement")
def check_hypothesis_statements(hypotheses: list[HypothesisOutput]) -> None:
    for h in hypotheses:
        assert h.statement, f"Hypothesis {h.hypothesis_id} has empty statement"


@then("each hypothesis is marked as testable")
def check_hypothesis_testable(hypotheses: list[HypothesisOutput]) -> None:
    for h in hypotheses:
        assert h.testable, f"Hypothesis {h.hypothesis_id} is not testable"
