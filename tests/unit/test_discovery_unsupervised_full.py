"""Full-coverage tests for labclaw.discovery.unsupervised.

Targets uncovered lines:
  - Lines 63, 67: _uuid(), _now() helpers
  - Sklearn fallback paths (_kmeans_pure, _pca_pure via numpy)
  - DimensionalityReducer.reduce() edge cases
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
    _now,
    _uuid,
)

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def test_uuid_returns_nonempty_string() -> None:
    uid = _uuid()
    assert isinstance(uid, str)
    assert len(uid) > 0


def test_now_returns_utc_datetime() -> None:
    dt = _now()
    assert isinstance(dt, datetime)
    assert dt.tzinfo is not None


# ---------------------------------------------------------------------------
# _cluster_confidence
# ---------------------------------------------------------------------------


def test_cluster_confidence_empty_labels() -> None:
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
    cfg = ClusterConfig(n_clusters=2)
    result = ClusterResult(
        labels=[0, 0, 0, 0, 1],
        n_clusters=2,
        centroids=[[0.0], [1.0]],
        inertia=1.0,
        config=cfg,
    )
    confidence = ClusterDiscovery._cluster_confidence(result)
    assert 0.0 <= confidence <= 1.0


# ---------------------------------------------------------------------------
# _extract_features edge cases
# ---------------------------------------------------------------------------


def test_extract_features_no_numeric_cols() -> None:
    data = [{"label": "a"}, {"label": "b"}, {"label": "c"}]
    matrix, cols = ClusterDiscovery._extract_features(data, [])
    assert matrix == []
    assert cols == []


def test_extract_features_explicit_cols_with_missing_row() -> None:
    data = [
        {"x": 1.0, "y": 2.0},
        {"x": 3.0},
        {"x": 5.0, "y": 6.0},
    ]
    matrix, cols = ClusterDiscovery._extract_features(data, ["x", "y"])
    assert len(matrix) == 2
    assert cols == ["x", "y"]


def test_extract_features_empty_data() -> None:
    matrix, cols = ClusterDiscovery._extract_features([], [])
    assert matrix == []
    assert cols == []


# ---------------------------------------------------------------------------
# Numpy fallback paths (sklearn unavailable)
# ---------------------------------------------------------------------------


def test_cluster_numpy_fallback(monkeypatch: object) -> None:
    """With sklearn unavailable, _kmeans_pure (numpy) is called."""
    monkeypatch.setattr(_unsupervised_mod, "SklearnKMeans", None)

    data = [{"x": float(i), "y": float(i % 2)} for i in range(10)]
    analyzer = ClusterDiscovery()
    cfg = ClusterConfig(n_clusters=2, random_seed=42)
    result = analyzer.cluster(data, cfg)

    assert result.n_clusters == 2
    assert len(result.labels) == 10
    assert len(result.centroids) == 2


def test_discover_patterns_numpy_fallback(monkeypatch: object) -> None:
    """discover_patterns also works with sklearn unavailable."""
    monkeypatch.setattr(_unsupervised_mod, "SklearnKMeans", None)

    data = [{"x": float(i), "y": float(i)} for i in range(12)]
    analyzer = ClusterDiscovery()
    patterns = analyzer.discover_patterns(data, ClusterConfig(n_clusters=2))

    assert len(patterns) == 1
    assert patterns[0].pattern_type == "cluster"


# ---------------------------------------------------------------------------
# DimensionalityReducer — numpy PCA fallback
# ---------------------------------------------------------------------------


def test_reduce_numpy_pca_fallback(monkeypatch: object) -> None:
    """With sklearn unavailable, _pca_pure (numpy eigh) is called."""
    monkeypatch.setattr(_unsupervised_mod, "SklearnPCA", None)

    data = [{"x": float(i), "y": float(i) * 2.0} for i in range(10)]
    reducer = DimensionalityReducer()
    cfg = ReductionConfig(n_components=1)
    result = reducer.reduce(data, cfg)

    assert isinstance(result, ReductionResult)
    assert len(result.components) == 10
    assert all(len(row) == 1 for row in result.components)


def test_reduce_no_numeric_cols_returns_empty() -> None:
    data = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
    reducer = DimensionalityReducer()
    result = reducer.reduce(data)
    assert result.components == []
    assert result.explained_variance == []


def test_reduce_with_feature_columns_arg() -> None:
    data = [{"x": float(i), "y": float(i) * 2.0, "z": float(i) * 0.1} for i in range(10)]
    reducer = DimensionalityReducer()
    cfg = ReductionConfig(n_components=1)
    result = reducer.reduce(data, cfg, feature_columns=["x", "y"])

    assert len(result.components) == 10
    assert all(len(row) == 1 for row in result.components)


def test_reduce_insufficient_rows_returns_empty() -> None:
    data = [{"x": 1.0, "y": 2.0}]
    reducer = DimensionalityReducer()
    result = reducer.reduce(data)
    assert result.components == []
    assert result.explained_variance == []


def test_pca_pure_single_column(monkeypatch: object) -> None:
    """Single-feature data → cov is scalar (ndim==0) → reshape to (1,1)."""
    monkeypatch.setattr(_unsupervised_mod, "SklearnPCA", None)
    from labclaw.discovery.unsupervised import _pca_pure

    data = [[float(i)] for i in range(5)]
    projected, explained = _pca_pure(data, n_components=1)
    assert len(projected) == 5
    assert all(len(row) == 1 for row in projected)
    assert len(explained) == 1


# ---------------------------------------------------------------------------
# Bool exclusion
# ---------------------------------------------------------------------------


def test_extract_features_excludes_booleans() -> None:
    data = [{"x": float(i), "flag": True} for i in range(5)]
    matrix, cols = ClusterDiscovery._extract_features(data, [])
    assert "flag" not in cols
    assert "x" in cols
