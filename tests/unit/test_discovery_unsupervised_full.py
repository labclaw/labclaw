"""Full-coverage tests for labclaw.discovery.unsupervised.

Targets uncovered lines:
  - Lines 63, 67, 71-73: _uuid(), _now(), _mean() helpers
  - Line 303: KMeans pure-python fallback (sklearn unavailable)
  - Lines 370, 407, 458: DimensionalityReducer.reduce() edge cases
    (empty labels → _cluster_confidence returns 0.0; no numeric cols; sklearn PCA fallback)
"""

from __future__ import annotations

from datetime import datetime

import labclaw.discovery.unsupervised as _unsupervised_mod
from labclaw.discovery.unsupervised import (
    ClusterConfig,
    ClusterDiscovery,
    ClusterResult,
    DimensionalityReducer,
    ReductionConfig,
    ReductionResult,
    _mean,
    _now,
    _uuid,
)

# ---------------------------------------------------------------------------
# Helper functions (lines 63, 67, 71-73)
# ---------------------------------------------------------------------------


def test_uuid_returns_nonempty_string() -> None:
    uid = _uuid()
    assert isinstance(uid, str)
    assert len(uid) > 0


def test_now_returns_utc_datetime() -> None:
    dt = _now()
    assert isinstance(dt, datetime)
    assert dt.tzinfo is not None


def test_mean_empty() -> None:
    assert _mean([]) == 0.0


def test_mean_single_value() -> None:
    assert _mean([42.0]) == 42.0


def test_mean_multiple_values() -> None:
    assert _mean([1.0, 2.0, 3.0]) == 2.0


# ---------------------------------------------------------------------------
# _cluster_confidence with empty labels (line 370)
# ---------------------------------------------------------------------------


def test_cluster_confidence_empty_labels() -> None:
    """Empty labels → confidence == 0.0 (line 370)."""
    cfg = ClusterConfig()
    result = ClusterResult(
        labels=[],
        n_clusters=0,
        centroids=[],
        inertia=0.0,
        config=cfg,
    )
    confidence = ClusterDiscovery._cluster_confidence(result)
    assert confidence == 0.0


def test_cluster_confidence_perfectly_balanced() -> None:
    """Perfectly balanced clusters yield high confidence."""
    cfg = ClusterConfig(n_clusters=2)
    result = ClusterResult(
        labels=[0, 0, 0, 1, 1, 1],
        n_clusters=2,
        centroids=[[0.0], [1.0]],
        inertia=0.1,
        config=cfg,
    )
    confidence = ClusterDiscovery._cluster_confidence(result)
    assert confidence >= 0.5


def test_cluster_confidence_with_singleton_cluster() -> None:
    """A cluster with 1 member gets a 0.5 penalty."""
    cfg = ClusterConfig(n_clusters=2)
    result = ClusterResult(
        labels=[0, 0, 0, 0, 1],  # cluster 1 has only 1 member
        n_clusters=2,
        centroids=[[0.0], [1.0]],
        inertia=1.0,
        config=cfg,
    )
    confidence = ClusterDiscovery._cluster_confidence(result)
    # Should be penalised but not negative
    assert 0.0 <= confidence <= 1.0


# ---------------------------------------------------------------------------
# _extract_features — no numeric columns (line 407)
# ---------------------------------------------------------------------------


def test_extract_features_no_numeric_cols() -> None:
    """All values are non-numeric → empty matrix (line 407)."""
    data = [{"label": "a"}, {"label": "b"}, {"label": "c"}]
    matrix, cols = ClusterDiscovery._extract_features(data, [])
    assert matrix == []
    assert cols == []


def test_extract_features_explicit_cols_with_missing_row() -> None:
    """Rows missing required feature columns are skipped."""
    data = [
        {"x": 1.0, "y": 2.0},
        {"x": 3.0},  # missing "y"
        {"x": 5.0, "y": 6.0},
    ]
    matrix, cols = ClusterDiscovery._extract_features(data, ["x", "y"])
    assert len(matrix) == 2
    assert cols == ["x", "y"]


def test_extract_features_empty_data() -> None:
    """Empty input → ([], [])."""
    matrix, cols = ClusterDiscovery._extract_features([], [])
    assert matrix == []
    assert cols == []


# ---------------------------------------------------------------------------
# KMeans pure-python fallback (line 303)
# ---------------------------------------------------------------------------


def test_cluster_pure_python_fallback(monkeypatch: object) -> None:
    """With sklearn unavailable, _kmeans_pure is called (line 303)."""
    monkeypatch.setattr(_unsupervised_mod, "np", None)
    monkeypatch.setattr(_unsupervised_mod, "SklearnKMeans", None)

    data = [{"x": float(i), "y": float(i % 2)} for i in range(10)]
    analyzer = ClusterDiscovery()
    cfg = ClusterConfig(n_clusters=2, random_seed=42)
    result = analyzer.cluster(data, cfg)

    assert result.n_clusters == 2
    assert len(result.labels) == 10
    assert len(result.centroids) == 2


def test_discover_patterns_pure_python_fallback(monkeypatch: object) -> None:
    """discover_patterns also works with sklearn unavailable."""
    monkeypatch.setattr(_unsupervised_mod, "np", None)
    monkeypatch.setattr(_unsupervised_mod, "SklearnKMeans", None)

    data = [{"x": float(i), "y": float(i)} for i in range(12)]
    analyzer = ClusterDiscovery()
    patterns = analyzer.discover_patterns(data, ClusterConfig(n_clusters=2))

    assert len(patterns) == 1
    assert patterns[0].pattern_type == "cluster"


# ---------------------------------------------------------------------------
# DimensionalityReducer — pure-python PCA fallback (line 458)
# ---------------------------------------------------------------------------


def test_reduce_pure_python_pca_fallback(monkeypatch: object) -> None:
    """With sklearn unavailable, _pca_pure is called (line 458)."""
    monkeypatch.setattr(_unsupervised_mod, "np", None)
    monkeypatch.setattr(_unsupervised_mod, "SklearnPCA", None)

    data = [{"x": float(i), "y": float(i) * 2.0} for i in range(10)]
    reducer = DimensionalityReducer()
    cfg = ReductionConfig(n_components=1)
    result = reducer.reduce(data, cfg)

    assert isinstance(result, ReductionResult)
    assert len(result.components) == 10
    assert all(len(row) == 1 for row in result.components)


def test_reduce_no_numeric_cols_returns_empty(monkeypatch: object) -> None:
    """No numeric columns in data → empty result (via _extract_features returning [])."""
    data = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
    reducer = DimensionalityReducer()
    result = reducer.reduce(data)
    assert result.components == []
    assert result.explained_variance == []


def test_reduce_with_feature_columns_arg() -> None:
    """feature_columns kwarg restricts which columns are used."""
    data = [{"x": float(i), "y": float(i) * 2.0, "z": float(i) * 0.1} for i in range(10)]
    reducer = DimensionalityReducer()
    cfg = ReductionConfig(n_components=1)
    result = reducer.reduce(data, cfg, feature_columns=["x", "y"])

    assert len(result.components) == 10
    assert all(len(row) == 1 for row in result.components)


def test_reduce_insufficient_rows_returns_empty() -> None:
    """Only 1 row → len(matrix) < 2 → empty result (existing line 444-449)."""
    data = [{"x": 1.0, "y": 2.0}]
    reducer = DimensionalityReducer()
    result = reducer.reduce(data)
    assert result.components == []
    assert result.explained_variance == []


# ---------------------------------------------------------------------------
# Integration: ClusterDiscovery with bool exclusion
# ---------------------------------------------------------------------------


def test_extract_features_excludes_booleans() -> None:
    """Boolean values must not be treated as numeric features."""
    data = [{"x": float(i), "flag": True} for i in range(5)]
    matrix, cols = ClusterDiscovery._extract_features(data, [])
    assert "flag" not in cols
    assert "x" in cols
