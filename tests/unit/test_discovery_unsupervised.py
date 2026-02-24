"""Tests for unsupervised clustering and dimensionality reduction.

Covers:
- src/labclaw/discovery/unsupervised.py
  (ClusterDiscovery, DimensionalityReducer, ClusterConfig, ClusterResult,
   ReductionConfig, ReductionResult, _kmeans_pure, _pca_pure)
"""

from __future__ import annotations

import pytest

from labclaw.discovery.unsupervised import (
    ClusterConfig,
    ClusterDiscovery,
    ClusterResult,
    DimensionalityReducer,
    ReductionConfig,
    ReductionResult,
    _euclidean_dist,
    _kmeans_pure,
    _pca_pure,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _two_group_data() -> list[dict[str, float]]:
    """20 rows clearly in two clusters: group A near (0,0), group B near (10,10)."""
    rows: list[dict[str, float]] = []
    for i in range(10):
        rows.append({"x": float(i % 3) * 0.1, "y": float(i % 3) * 0.1})
    for i in range(10):
        rows.append({"x": 10.0 + float(i % 3) * 0.1, "y": 10.0 + float(i % 3) * 0.1})
    return rows


# ---------------------------------------------------------------------------
# ClusterConfig defaults
# ---------------------------------------------------------------------------


class TestClusterConfig:
    def test_defaults(self) -> None:
        cfg = ClusterConfig()
        assert cfg.n_clusters == 3
        assert cfg.method == "kmeans"
        assert cfg.max_iterations == 100
        assert cfg.random_seed == 42
        assert cfg.feature_columns == []

    def test_custom_values(self) -> None:
        cfg = ClusterConfig(n_clusters=5, method="kmeans", random_seed=0)
        assert cfg.n_clusters == 5
        assert cfg.random_seed == 0


# ---------------------------------------------------------------------------
# ClusterResult schema
# ---------------------------------------------------------------------------


class TestClusterResult:
    def test_fields_present(self) -> None:
        cfg = ClusterConfig()
        result = ClusterResult(
            labels=[0, 1, 0, 1],
            n_clusters=2,
            centroids=[[0.0, 0.0], [1.0, 1.0]],
            inertia=0.5,
            config=cfg,
        )
        assert result.labels == [0, 1, 0, 1]
        assert result.n_clusters == 2
        assert len(result.centroids) == 2
        assert result.inertia == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# ClusterDiscovery.cluster()
# ---------------------------------------------------------------------------


class TestClusterDiscovery:
    def test_two_clusters_found(self) -> None:
        data = _two_group_data()
        analyzer = ClusterDiscovery()
        cfg = ClusterConfig(n_clusters=2, random_seed=42)
        result = analyzer.cluster(data, cfg)

        assert result.n_clusters == 2
        assert len(result.labels) == 20
        # Check that both labels are used
        assert set(result.labels) == {0, 1}

    def test_two_clusters_separated(self) -> None:
        """The two groups must not be merged into one cluster."""
        data = _two_group_data()
        analyzer = ClusterDiscovery()
        cfg = ClusterConfig(n_clusters=2, random_seed=42)
        result = analyzer.cluster(data, cfg)

        # Group 0 (first 10 rows) should all have the same label
        first_label = result.labels[0]
        assert all(result.labels[i] == first_label for i in range(10))
        # Group 1 (last 10 rows) should have the other label
        second_label = result.labels[10]
        assert second_label != first_label
        assert all(result.labels[i] == second_label for i in range(10, 20))

    def test_cluster_returns_centroids(self) -> None:
        data = _two_group_data()
        analyzer = ClusterDiscovery()
        cfg = ClusterConfig(n_clusters=2)
        result = analyzer.cluster(data, cfg)
        assert len(result.centroids) == 2
        assert all(len(c) == 2 for c in result.centroids)

    def test_cluster_empty_data(self) -> None:
        analyzer = ClusterDiscovery()
        result = analyzer.cluster([])
        assert result.n_clusters == 0
        assert result.labels == []

    def test_cluster_k_clamped_to_n_samples(self) -> None:
        """When n_clusters > n_samples, k is clamped to n_samples."""
        data = [{"x": 1.0}, {"x": 2.0}]
        analyzer = ClusterDiscovery()
        cfg = ClusterConfig(n_clusters=10)
        result = analyzer.cluster(data, cfg)
        assert result.n_clusters <= 2

    def test_discover_patterns_returns_pattern_records(self) -> None:
        data = _two_group_data()
        analyzer = ClusterDiscovery()
        cfg = ClusterConfig(n_clusters=2)
        patterns = analyzer.discover_patterns(data, cfg)
        assert len(patterns) == 1
        p = patterns[0]
        assert p.pattern_type == "cluster"
        assert p.confidence >= 0.0
        assert "n_clusters" in p.evidence

    def test_discover_patterns_empty_data(self) -> None:
        analyzer = ClusterDiscovery()
        patterns = analyzer.discover_patterns([])
        assert patterns == []

    def test_cluster_with_explicit_feature_columns(self) -> None:
        data = [{"x": float(i), "y": float(i), "label": i} for i in range(12)]
        analyzer = ClusterDiscovery()
        cfg = ClusterConfig(n_clusters=2, feature_columns=["x", "y"])
        result = analyzer.cluster(data, cfg)
        assert result.n_clusters == 2


# ---------------------------------------------------------------------------
# DimensionalityReducer
# ---------------------------------------------------------------------------


class TestDimensionalityReducer:
    def test_reduce_2d_to_1d(self) -> None:
        data = [{"x": float(i), "y": float(i)} for i in range(10)]
        reducer = DimensionalityReducer()
        cfg = ReductionConfig(n_components=1)
        result = reducer.reduce(data, cfg)
        assert isinstance(result, ReductionResult)
        assert len(result.components) == 10
        assert all(len(row) == 1 for row in result.components)

    def test_reduce_insufficient_data(self) -> None:
        reducer = DimensionalityReducer()
        result = reducer.reduce([{"x": 1.0}])
        assert result.components == []
        assert result.explained_variance == []

    def test_reduction_config_defaults(self) -> None:
        cfg = ReductionConfig()
        assert cfg.n_components == 2
        assert cfg.method == "pca"


# ---------------------------------------------------------------------------
# Pure-Python k-means
# ---------------------------------------------------------------------------


class TestKmeansPure:
    def test_two_clear_clusters(self) -> None:
        # Use unique points so the random seed can always select two distinct centroids
        data = [[float(i), float(i)] for i in range(5)] + [
            [100.0 + float(i), 100.0 + float(i)] for i in range(5)
        ]
        labels, centroids, inertia = _kmeans_pure(data, k=2, seed=0)
        assert len(labels) == 10
        assert len(centroids) == 2
        assert set(labels) == {0, 1}

    def test_empty_data(self) -> None:
        labels, centroids, inertia = _kmeans_pure([], k=2)
        assert labels == []
        assert centroids == []
        assert inertia == 0.0

    def test_k_zero(self) -> None:
        data = [[1.0], [2.0]]
        labels, centroids, inertia = _kmeans_pure(data, k=0)
        assert labels == []


# ---------------------------------------------------------------------------
# Pure-Python PCA
# ---------------------------------------------------------------------------


class TestPcaPure:
    def test_pca_reduces_dimensions(self) -> None:
        data = [[float(i), float(i), float(i)] for i in range(10)]
        projected, eigenvalues = _pca_pure(data, n_components=2)
        assert len(projected) == 10
        assert all(len(row) == 2 for row in projected)

    def test_pca_empty_data(self) -> None:
        projected, eigenvalues = _pca_pure([], n_components=2)
        assert projected == []
        assert eigenvalues == []


# ---------------------------------------------------------------------------
# Euclidean distance helper
# ---------------------------------------------------------------------------


class TestEuclideanDist:
    def test_same_point(self) -> None:
        assert _euclidean_dist([1.0, 2.0], [1.0, 2.0]) == pytest.approx(0.0)

    def test_unit_vectors(self) -> None:
        assert _euclidean_dist([0.0, 0.0], [3.0, 4.0]) == pytest.approx(5.0)
