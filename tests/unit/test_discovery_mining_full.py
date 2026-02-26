"""Full-coverage tests for labclaw.discovery.mining.

Targets edge cases and boundary conditions in the mining pipeline.
"""

from __future__ import annotations

from labclaw.discovery.mining import PatternMiner

# ---------------------------------------------------------------------------
# find_correlations — deduplication and sparse data
# ---------------------------------------------------------------------------


def test_find_correlations_deduplication() -> None:
    """Same column pair should only be processed once."""
    miner = PatternMiner()
    data = [{"a": float(i), "b": float(i)} for i in range(10)]
    patterns = miner.find_correlations(data, threshold=0.5)
    ab_patterns = [
        p for p in patterns if set([p.evidence.get("col_a"), p.evidence.get("col_b")]) == {"a", "b"}
    ]
    assert len(ab_patterns) == 1


def test_find_correlations_sparse_pair_too_few_rows(monkeypatch: object) -> None:
    """If col_b has fewer than 3 paired observations, skip it."""
    import labclaw.discovery.mining as m

    data = [
        {"a": 1.0, "b": 10.0},
        {"a": 2.0, "b": 20.0},
        {"a": 3.0},
        {"a": 4.0},
        {"a": 5.0},
    ]
    monkeypatch.setattr(
        m.PatternMiner,
        "_detect_numeric_columns",
        staticmethod(lambda data, fc=None: ["a", "b"]),
    )
    miner = PatternMiner()
    patterns = miner.find_correlations(data, threshold=0.0)
    assert all(
        not (p.evidence.get("col_a") == "a" and p.evidence.get("col_b") == "b") for p in patterns
    )


# ---------------------------------------------------------------------------
# find_anomalies — sparse column edge cases
# ---------------------------------------------------------------------------


def test_find_anomalies_column_with_too_few_valid_values(monkeypatch: object) -> None:
    """A detected column with < 3 indexed values is skipped."""
    import labclaw.discovery.mining as m

    data = [{"common": float(i)} for i in range(15)]
    data[0]["rare"] = 1.0
    data[1]["rare"] = 2.0

    monkeypatch.setattr(
        m.PatternMiner,
        "_detect_numeric_columns",
        staticmethod(lambda data, fc=None: ["common", "rare"]),
    )
    miner = PatternMiner()
    patterns = miner.find_anomalies(data, z_threshold=2.0)
    rare_patterns = [p for p in patterns if p.evidence.get("column") == "rare"]
    assert rare_patterns == []


def test_find_anomalies_non_numeric_values_skipped() -> None:
    """ValueError/TypeError from float() conversion is silently skipped."""
    miner = PatternMiner()
    data = [{"v": float(i)} for i in range(18)]
    data[3]["v"] = "N/A"
    data[7]["v"] = None
    patterns = miner.find_anomalies(data, z_threshold=100.0)
    assert isinstance(patterns, list)


def test_find_anomalies_zero_std_constant_column_skipped() -> None:
    """Column with std == 0 is skipped."""
    miner = PatternMiner()
    data = [{"v": 42.0} for _ in range(10)]
    patterns = miner.find_anomalies(data)
    assert patterns == []


# ---------------------------------------------------------------------------
# find_temporal_patterns — edge cases
# ---------------------------------------------------------------------------


def test_find_temporal_patterns_col_missing_first_half(monkeypatch: object) -> None:
    """When a detected column is absent from the first half, skip it."""
    import labclaw.discovery.mining as m

    n = 12
    data = [{"timestamp": float(i)} for i in range(n)]
    for i in range(6, n):
        data[i]["metric"] = float(i) * 10.0

    monkeypatch.setattr(
        m.PatternMiner,
        "_detect_numeric_columns",
        staticmethod(lambda data, fc=None: ["metric"]),
    )
    miner = PatternMiner()
    patterns = miner.find_temporal_patterns(data, time_col="timestamp")
    assert isinstance(patterns, list)


def test_find_temporal_patterns_flat_std_skip() -> None:
    """overall_std == 0 → skip column."""
    miner = PatternMiner()
    data = [{"timestamp": float(i), "flat": 5.0} for i in range(10)]
    patterns = miner.find_temporal_patterns(data, time_col="timestamp")
    assert patterns == []


# ---------------------------------------------------------------------------
# _detect_numeric_columns
# ---------------------------------------------------------------------------


def test_detect_numeric_columns_empty_data() -> None:
    result = PatternMiner._detect_numeric_columns([])
    assert result == []


def test_detect_numeric_columns_with_feature_columns() -> None:
    data = [{"a": 1.0, "b": 2.0}]
    result = PatternMiner._detect_numeric_columns(data, feature_columns=["a"])
    assert result == ["a"]


def test_detect_numeric_columns_excludes_booleans() -> None:
    data = [{"x": 1.0, "flag": True, "y": 2.0} for _ in range(5)]
    result = PatternMiner._detect_numeric_columns(data)
    assert "flag" not in result
    assert "x" in result
    assert "y" in result


# ---------------------------------------------------------------------------
# session_id handling
# ---------------------------------------------------------------------------


def test_correlation_uses_session_id_from_row() -> None:
    miner = PatternMiner()
    data = [{"session_id": f"sess_{i}", "x": float(i), "y": float(i) * 3.0} for i in range(12)]
    patterns = miner.find_correlations(data, threshold=0.5)
    assert len(patterns) >= 1
    assert any("sess_" in sid for sid in patterns[0].session_ids)


def test_correlation_session_ids_only_from_participating_rows() -> None:
    """session_ids must only include rows where BOTH columns had valid values (C1 fix)."""
    miner = PatternMiner()
    # Rows 0–9: both x and y present; rows 10–14: only x present (y missing)
    data = [{"session_id": f"valid_{i}", "x": float(i), "y": float(i) * 2.0} for i in range(10)] + [
        {"session_id": f"missing_y_{i}", "x": float(i)} for i in range(5)
    ]
    patterns = miner.find_correlations(data, threshold=0.5)
    assert len(patterns) >= 1
    xy_pattern = next(
        p for p in patterns if p.evidence.get("col_a") == "x" and p.evidence.get("col_b") == "y"
    )
    # Only 10 valid rows participated; session_ids should not include missing_y_* entries
    assert len(xy_pattern.session_ids) == 10
    assert all(sid.startswith("valid_") for sid in xy_pattern.session_ids)
    assert not any(sid.startswith("missing_y_") for sid in xy_pattern.session_ids)


def test_anomaly_uses_session_id_from_row() -> None:
    miner = PatternMiner()
    data = [{"session_id": f"s{i}", "v": float(i)} for i in range(15)]
    data[0]["v"] = 9999.0
    patterns = miner.find_anomalies(data, z_threshold=2.0)
    assert len(patterns) >= 1
    assert any("s0" in sid for sid in patterns[0].session_ids)


# ---------------------------------------------------------------------------
# mine() — data_summary for empty data
# ---------------------------------------------------------------------------


def test_mine_data_summary_empty() -> None:
    miner = PatternMiner()
    result = miner.mine([])
    assert result.data_summary["row_count"] == 0
    assert result.data_summary["total_columns"] == []
    assert result.data_summary["numeric_columns"] == []
