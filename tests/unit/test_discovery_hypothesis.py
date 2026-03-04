"""Tests for HypothesisGenerator from labclaw.discovery.hypothesis."""

from __future__ import annotations

import pytest

from labclaw.core.schemas import HypothesisStatus
from labclaw.discovery.hypothesis import (
    HypothesisGenerator,
    HypothesisInput,
    HypothesisOutput,
)
from labclaw.discovery.mining import PatternRecord


def _make_pattern(
    pattern_type: str,
    evidence: dict,
    confidence: float = 0.8,
    description: str = "test pattern",
) -> PatternRecord:
    return PatternRecord(
        pattern_type=pattern_type,
        description=description,
        evidence=evidence,
        confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Per-pattern-type generation
# ---------------------------------------------------------------------------


def test_generate_correlation_pattern() -> None:
    """Correlation pattern produces a hypothesis mentioning 'correlated', testable=True."""
    pattern = _make_pattern(
        "correlation",
        evidence={"col_a": "speed", "col_b": "accuracy", "r": 0.85, "p_value": 0.001},
        confidence=0.85,
    )
    gen = HypothesisGenerator()
    results = gen.generate(HypothesisInput(patterns=[pattern]))

    assert len(results) == 1
    hyp = results[0]
    assert "correlated" in hyp.statement.lower() or "correlation" in hyp.statement.lower()
    assert hyp.testable is True
    assert pattern.pattern_id in hyp.patterns_used
    assert hyp.confidence == pytest.approx(0.85)


def test_generate_anomaly_pattern() -> None:
    """Anomaly pattern produces a hypothesis statement mentioning 'Anomalous'."""
    pattern = _make_pattern(
        "anomaly",
        evidence={"column": "fluorescence", "anomalous_indices": [1, 5, 9]},
        confidence=0.7,
    )
    gen = HypothesisGenerator()
    results = gen.generate(HypothesisInput(patterns=[pattern]))

    assert len(results) == 1
    hyp = results[0]
    assert "anomalous" in hyp.statement.lower() or "anomal" in hyp.statement.lower()
    assert hyp.testable is True
    assert pattern.pattern_id in hyp.patterns_used


def test_generate_temporal_pattern() -> None:
    """Temporal pattern produces a hypothesis statement mentioning 'Trend'."""
    pattern = _make_pattern(
        "temporal",
        evidence={"column": "accuracy", "direction": "increasing"},
        confidence=0.6,
    )
    gen = HypothesisGenerator()
    results = gen.generate(HypothesisInput(patterns=[pattern]))

    assert len(results) == 1
    hyp = results[0]
    assert "trend" in hyp.statement.lower()
    assert hyp.testable is True
    assert pattern.pattern_id in hyp.patterns_used


def test_generate_cluster_pattern() -> None:
    """Cluster pattern produces a hypothesis statement mentioning 'clusters' or 'subpopulations'."""
    pattern = _make_pattern(
        "cluster",
        evidence={"n_clusters": 3, "silhouette_score": 0.61},
        confidence=0.75,
    )
    gen = HypothesisGenerator()
    results = gen.generate(HypothesisInput(patterns=[pattern]))

    assert len(results) == 1
    hyp = results[0]
    assert "cluster" in hyp.statement.lower() or "subpopulation" in hyp.statement.lower()
    assert hyp.testable is True
    assert pattern.pattern_id in hyp.patterns_used


def test_generate_unknown_pattern_type() -> None:
    """Unknown pattern_type returns an empty list (skipped with warning)."""
    pattern = _make_pattern(
        "custom",
        evidence={"some_key": "some_value"},
        confidence=0.5,
    )
    gen = HypothesisGenerator()
    results = gen.generate(HypothesisInput(patterns=[pattern]))

    assert results == []


def test_generate_empty_patterns() -> None:
    """Empty patterns list yields empty output."""
    gen = HypothesisGenerator()
    results = gen.generate(HypothesisInput(patterns=[]))

    assert results == []


# ---------------------------------------------------------------------------
# Sorting and multiple patterns
# ---------------------------------------------------------------------------


def test_generate_multiple_patterns_sorted_by_confidence() -> None:
    """Three patterns with different confidences are returned sorted descending."""
    patterns = [
        _make_pattern(
            "correlation", evidence={"col_a": "a", "col_b": "b", "r": 0.6}, confidence=0.3
        ),
        _make_pattern(
            "anomaly", evidence={"column": "x", "anomalous_indices": [0]}, confidence=0.9
        ),
        _make_pattern(
            "temporal", evidence={"column": "y", "direction": "decreasing"}, confidence=0.6
        ),
    ]
    gen = HypothesisGenerator()
    results = gen.generate(HypothesisInput(patterns=patterns))

    assert len(results) == 3
    scores = [h.confidence for h in results]
    assert scores == sorted(scores, reverse=True), "Results must be sorted by confidence descending"


# ---------------------------------------------------------------------------
# Schema defaults
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Plugin templates
# ---------------------------------------------------------------------------


def test_plugin_template_generates_hypothesis() -> None:
    """A valid plugin template produces a hypothesis."""
    templates = [{"statement": "Domain hyp with {pattern_count} patterns", "confidence": 0.75}]
    gen = HypothesisGenerator(plugin_templates=templates)
    pattern = _make_pattern(
        "correlation",
        evidence={"col_a": "x", "col_b": "y", "r": 0.5},
        confidence=0.5,
    )
    results = gen.generate(HypothesisInput(patterns=[pattern]))
    # 1 from correlation + 1 from plugin template
    assert len(results) == 2
    statements = [h.statement for h in results]
    assert any("Domain hyp with 1 patterns" in s for s in statements)


def test_plugin_template_empty_statement_skipped() -> None:
    """A plugin template with empty statement is skipped."""
    templates = [{"statement": "", "confidence": 0.5}]
    gen = HypothesisGenerator(plugin_templates=templates)
    results = gen.generate(HypothesisInput(patterns=[]))
    assert results == []


# ---------------------------------------------------------------------------
# Schema defaults
# ---------------------------------------------------------------------------


def test_hypothesis_output_default_fields() -> None:
    """HypothesisOutput has a non-empty hypothesis_id and status=PROPOSED by default."""
    hyp = HypothesisOutput(statement="Test hypothesis.")

    assert hyp.hypothesis_id != ""
    assert len(hyp.hypothesis_id) > 0
    assert hyp.status == HypothesisStatus.PROPOSED
    assert hyp.testable is True
