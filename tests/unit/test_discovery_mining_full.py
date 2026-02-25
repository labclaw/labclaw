"""Full-coverage tests for labclaw.discovery.mining.

Targets the uncovered lines reported by coverage:
  - 102, 108: _mean / _std edge cases (empty list, len <= ddof)
  - 116-140: _pearson_r pure-python fallback (scipy unavailable, r=±1, erfc branch)
  - 218: seen_pairs deduplication (same pair twice)
  - 230: paired observation count < 3
  - 237: fallback path in find_correlations
  - 291-292, 294: find_anomalies rows with too-few indexed values
  - 377: find_temporal_patterns col missing from one half
  - 438: _detect_numeric_columns with empty data when feature_columns is None
"""

from __future__ import annotations

import labclaw.discovery.mining as _mining_mod
from labclaw.discovery.mining import (
    PatternMiner,
    _mean,
    _pearson_r,
    _std,
)

# ---------------------------------------------------------------------------
# _mean edge cases  (line 102)
# ---------------------------------------------------------------------------


def test_mean_empty_list() -> None:
    assert _mean([]) == 0.0


def test_mean_single_value() -> None:
    assert _mean([7.0]) == 7.0


def test_mean_multiple_values() -> None:
    assert _mean([1.0, 2.0, 3.0]) == 2.0


# ---------------------------------------------------------------------------
# _std edge cases  (line 108)
# ---------------------------------------------------------------------------


def test_std_empty_list_ddof_0() -> None:
    # len([]) == 0 <= ddof 0  → 0.0
    assert _std([]) == 0.0


def test_std_single_value_ddof_1() -> None:
    # len([x]) == 1 <= ddof 1  → 0.0
    assert _std([5.0], ddof=1) == 0.0


def test_std_population() -> None:

    vals = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    result = _std(vals, ddof=0)
    assert abs(result - 2.0) < 1e-9


# ---------------------------------------------------------------------------
# _pearson_r — pure-python fallback (lines 116-140)
# ---------------------------------------------------------------------------


def test_pearson_r_too_few_points() -> None:
    """n < 3 → (0.0, 1.0)."""
    r, p = _pearson_r([1.0, 2.0], [1.0, 2.0])
    assert r == 0.0
    assert p == 1.0


def test_pearson_r_zero_std_x() -> None:
    """Constant x → (0.0, 1.0)."""
    r, p = _pearson_r([3.0, 3.0, 3.0], [1.0, 2.0, 3.0])
    assert r == 0.0
    assert p == 1.0


def test_pearson_r_zero_std_y() -> None:
    """Constant y → (0.0, 1.0)."""
    r, p = _pearson_r([1.0, 2.0, 3.0], [5.0, 5.0, 5.0])
    assert r == 0.0
    assert p == 1.0


def test_pearson_r_perfect_positive_branch(monkeypatch: object) -> None:
    """abs(r) >= 1.0 branch → p == 0.0 (line 131).

    x = [0, 1, 2] identical to y gives r = 1.0 exactly in IEEE-754 float,
    which triggers the `if abs(r) >= 1.0: p = 0.0` branch.
    With scipy unavailable the erfc branch would run, so we also disable scipy
    to confirm the branch short-circuits to p = 0.0.
    """
    monkeypatch.setattr(_mining_mod, "scipy_stats", None)
    # [0, 1, 2] gives r = 1.0 exactly via population-std formula
    x = [0.0, 1.0, 2.0]
    r, p = _pearson_r(x, x)
    assert r == 1.0
    assert p == 0.0


def test_pearson_r_erfc_branch_no_scipy(monkeypatch: object) -> None:
    """With scipy unavailable, p is computed via erfc (line 138)."""
    monkeypatch.setattr(_mining_mod, "scipy_stats", None)
    x = [float(i) for i in range(10)]
    y = [float(i) * 0.5 + 1.0 for i in range(10)]  # strong positive correlation
    r, p = _pearson_r(x, y)
    assert abs(r) > 0.9
    assert 0.0 <= p <= 1.0


def test_pearson_r_with_scipy_available() -> None:
    """With scipy available, the scipy t.sf branch is taken (line 135).

    Use x and y with a non-perfect correlation so |r| < 1 and the scipy
    branch computes a finite p-value (not the abs(r)>=1 short-circuit).
    """
    # Non-perfect correlation: y has added noise
    x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    y = [2.1, 3.9, 6.2, 7.8, 9.9, 12.1, 14.0, 15.9, 18.1, 20.0]
    r, p = _pearson_r(x, y)
    # Strong but imperfect correlation → scipy branch used
    assert abs(r) > 0.99
    assert abs(r) < 1.0  # ensures we did NOT hit the abs(r)>=1 shortcut
    assert 0.0 <= p < 0.01


# ---------------------------------------------------------------------------
# find_correlations — deduplication and sparse data (lines 218, 230, 237)
# ---------------------------------------------------------------------------


def test_find_correlations_deduplication() -> None:
    """Same column pair should only be processed once (seen_pairs guard, line 218)."""
    # _detect_numeric_columns returns sorted columns — we just need >=2 numeric cols
    # with enough paired observations. The deduplication is internal; test that
    # calling find_correlations with explicit feature_columns doesn't duplicate.
    miner = PatternMiner()
    data = [{"a": float(i), "b": float(i)} for i in range(10)]
    patterns = miner.find_correlations(data, threshold=0.5)
    # There should be exactly one pattern for the (a,b) pair, not two
    ab_patterns = [
        p for p in patterns if set([p.evidence.get("col_a"), p.evidence.get("col_b")]) == {"a", "b"}
    ]
    assert len(ab_patterns) == 1


def test_find_correlations_sparse_pair_too_few_rows(monkeypatch: object) -> None:
    """If col_b has fewer than 3 paired observations, skip it (line 230).

    We monkeypatch _detect_numeric_columns to include 'b' even though it
    only appears in 2 rows, so the paired-count guard at line 230 is hit.
    """
    import labclaw.discovery.mining as m

    data = [
        {"a": 1.0, "b": 10.0},
        {"a": 2.0, "b": 20.0},
        {"a": 3.0},
        {"a": 4.0},
        {"a": 5.0},
    ]
    # Force both 'a' and 'b' to be detected as numeric columns
    monkeypatch.setattr(
        m.PatternMiner,
        "_detect_numeric_columns",
        staticmethod(lambda data, fc=None: ["a", "b"]),
    )
    miner = PatternMiner()
    patterns = miner.find_correlations(data, threshold=0.0)
    # 'b' has only 2 paired rows with 'a' → skipped (line 230 hit)
    assert all(
        not (p.evidence.get("col_a") == "a" and p.evidence.get("col_b") == "b") for p in patterns
    )


def test_find_correlations_no_scipy_fallback(monkeypatch: object) -> None:
    """With both numpy and scipy unavailable, _pearson_r fallback is used (line 237)."""
    monkeypatch.setattr(_mining_mod, "np", None)
    monkeypatch.setattr(_mining_mod, "scipy_stats", None)

    miner = PatternMiner()
    n = 15
    data = [{"x": float(i), "y": float(i) * 2.0} for i in range(n)]
    patterns = miner.find_correlations(data, threshold=0.8)
    assert len(patterns) >= 1
    assert abs(patterns[0].evidence["r"]) > 0.8


# ---------------------------------------------------------------------------
# find_anomalies — sparse column edge cases (lines 291-292, 294)
# ---------------------------------------------------------------------------


def test_find_anomalies_column_with_too_few_valid_values(monkeypatch: object) -> None:
    """A detected column with < 3 indexed values is skipped (line 294).

    We monkeypatch _detect_numeric_columns to include 'rare' even though
    it only appears in 2 rows, so the indexed-count guard fires.
    """
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
    # 'rare' has only 2 indexed values → skipped (line 294 hit)
    rare_patterns = [p for p in patterns if p.evidence.get("column") == "rare"]
    assert rare_patterns == []


def test_find_anomalies_non_numeric_values_skipped() -> None:
    """ValueError/TypeError from float() conversion is silently skipped (lines 291-292)."""
    miner = PatternMiner()
    # Mix of numeric and non-numeric in the same column
    data = [{"v": float(i)} for i in range(18)]
    # Overwrite some rows with string values
    data[3]["v"] = "N/A"
    data[7]["v"] = None

    # Should not raise; the non-numeric values are skipped
    # The remaining 16 numeric values should still be processed
    patterns = miner.find_anomalies(data, z_threshold=100.0)  # high threshold → no anomalies
    # No crash is the main assertion
    assert isinstance(patterns, list)


def test_find_anomalies_zero_std_constant_column_skipped() -> None:
    """Column with std == 0 is skipped even when all values are present (line 300)."""
    miner = PatternMiner()
    data = [{"v": 42.0} for _ in range(10)]
    patterns = miner.find_anomalies(data)
    assert patterns == []


# ---------------------------------------------------------------------------
# find_temporal_patterns — empty half edge case (line 377)
# ---------------------------------------------------------------------------


def test_find_temporal_patterns_col_missing_first_half(monkeypatch: object) -> None:
    """When a detected column is absent from the first half, skip it (line 377).

    We monkeypatch _detect_numeric_columns to include 'metric' even though it
    only appears in the second half of the sorted data.
    """
    import labclaw.discovery.mining as m

    n = 12
    data = [{"timestamp": float(i)} for i in range(n)]
    # 'metric' only in second half (rows 6..11)
    for i in range(6, n):
        data[i]["metric"] = float(i) * 10.0

    monkeypatch.setattr(
        m.PatternMiner,
        "_detect_numeric_columns",
        staticmethod(lambda data, fc=None: ["metric"]),
    )
    miner = PatternMiner()
    # first_half of 'metric' is empty → line 377 triggered → continue
    patterns = miner.find_temporal_patterns(data, time_col="timestamp")
    assert isinstance(patterns, list)


def test_find_temporal_patterns_flat_std_skip() -> None:
    """overall_std == 0 → skip column (line 386-387)."""
    miner = PatternMiner()
    # All values identical in both halves → std == 0 → continue
    data = [{"timestamp": float(i), "flat": 5.0} for i in range(10)]
    patterns = miner.find_temporal_patterns(data, time_col="timestamp")
    assert patterns == []


# ---------------------------------------------------------------------------
# _detect_numeric_columns — empty data branch (line 438)
# ---------------------------------------------------------------------------


def test_detect_numeric_columns_empty_data() -> None:
    """Empty data list → empty column list (line 440-441)."""
    result = PatternMiner._detect_numeric_columns([])
    assert result == []


def test_detect_numeric_columns_with_feature_columns() -> None:
    """Explicit feature_columns bypasses detection (line 437-438)."""
    data = [{"a": 1.0, "b": 2.0}]
    result = PatternMiner._detect_numeric_columns(data, feature_columns=["a"])
    assert result == ["a"]


def test_detect_numeric_columns_excludes_booleans() -> None:
    """Boolean values are excluded from numeric columns."""
    data = [{"x": 1.0, "flag": True, "y": 2.0} for _ in range(5)]
    result = PatternMiner._detect_numeric_columns(data)
    assert "flag" not in result
    assert "x" in result
    assert "y" in result


# ---------------------------------------------------------------------------
# CSV export / formatting paths (lines 218, 230, 237 — also session_id branch)
# ---------------------------------------------------------------------------


def test_correlation_uses_session_id_from_row() -> None:
    """Rows with 'session_id' field use it in session_ids list (line 240-243)."""
    miner = PatternMiner()
    data = [{"session_id": f"sess_{i}", "x": float(i), "y": float(i) * 3.0} for i in range(12)]
    patterns = miner.find_correlations(data, threshold=0.5)
    assert len(patterns) >= 1
    assert any("sess_" in sid for sid in patterns[0].session_ids)


def test_anomaly_uses_session_id_from_row() -> None:
    """Anomalous rows with 'session_id' field use it in session_ids list."""
    miner = PatternMiner()
    data = [{"session_id": f"s{i}", "v": float(i)} for i in range(15)]
    data[0]["v"] = 9999.0  # extreme outlier
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
