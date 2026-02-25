"""BDD step definitions for L3 Unsupervised Discovery.

Spec: docs/specs/L3-discovery.md
Uses conftest fixtures: event_capture
"""

from __future__ import annotations

import random
from typing import Any

from pytest_bdd import given, parsers, then, when

from labclaw.core.events import event_registry
from labclaw.discovery.mining import PatternRecord
from labclaw.discovery.unsupervised import (
    ClusterConfig,
    ClusterDiscovery,
    ClusterResult,
    DimensionalityReducer,
    ReductionConfig,
    ReductionResult,
    _kmeans_pure,
)

# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------


@given("the cluster discovery engine is initialized", target_fixture="cluster_engine")
def cluster_engine_initialized(event_capture: object) -> ClusterDiscovery:
    """Provide a ClusterDiscovery and subscribe event capture."""
    for evt_name in ["discovery.cluster.found", "discovery.reduction.completed"]:
        event_registry.subscribe(evt_name, event_capture)  # type: ignore[arg-type]
    return ClusterDiscovery()


# ---------------------------------------------------------------------------
# Data fixtures
# ---------------------------------------------------------------------------


@given(
    parsers.parse("experimental data with {k:d} distinct clusters of {n:d} points each"),
    target_fixture="cluster_data",
)
def data_with_clusters(k: int, n: int) -> list[dict[str, Any]]:
    """Generate data with k well-separated clusters."""
    rng = random.Random(42)
    data: list[dict[str, Any]] = []
    for cluster_idx in range(k):
        center_x = cluster_idx * 20.0  # well separated
        center_y = cluster_idx * 20.0
        for i in range(n):
            data.append(
                {
                    "x": center_x + rng.gauss(0, 1.0),
                    "y": center_y + rng.gauss(0, 1.0),
                    "session_id": f"s{cluster_idx}_{i}",
                }
            )
    return data


@given(
    parsers.parse("experimental data with only {n:d} rows for clustering"),
    target_fixture="cluster_data",
)
def data_few_rows_clustering(n: int) -> list[dict[str, Any]]:
    return [{"x": float(i), "y": float(i * 2), "session_id": f"s{i}"} for i in range(n)]


@given(
    parsers.parse("experimental data with {ncols:d} numeric columns and {nrows:d} rows"),
    target_fixture="cluster_data",
)
def data_multi_columns(ncols: int, nrows: int) -> list[dict[str, Any]]:
    rng = random.Random(42)
    data: list[dict[str, Any]] = []
    col_names = [f"feat_{i}" for i in range(ncols)]
    for i in range(nrows):
        row: dict[str, Any] = {"session_id": f"s{i}"}
        for col in col_names:
            row[col] = rng.gauss(0, 10.0)
        data.append(row)
    return data


@given("empty clustering data", target_fixture="cluster_data")
def empty_cluster_data() -> list[dict[str, Any]]:
    """No data rows at all."""
    return []


@given(
    parsers.parse("experimental data with {ncols:d} numeric column and {nrows:d} rows"),
    target_fixture="cluster_data",
)
def data_single_column(ncols: int, nrows: int) -> list[dict[str, Any]]:
    """Single numeric column only."""
    rng = random.Random(42)
    return [{"feat_0": rng.gauss(0, 1.0), "session_id": f"s{i}"} for i in range(nrows)]


@given(
    parsers.parse("experimental data with {n:d} identical rows"),
    target_fixture="cluster_data",
)
def data_identical_rows(n: int) -> list[dict[str, Any]]:
    """All rows are identical."""
    return [{"x": 5.0, "y": 3.0, "session_id": f"s{i}"} for i in range(n)]


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when(
    parsers.parse("I run clustering with k={k:d}"),
    target_fixture="cluster_result",
)
def run_clustering(
    cluster_engine: ClusterDiscovery,
    cluster_data: list[dict[str, Any]],
    k: int,
) -> ClusterResult:
    config = ClusterConfig(n_clusters=k)
    return cluster_engine.cluster(cluster_data, config)


@when(
    parsers.parse("I discover cluster patterns with k={k:d}"),
    target_fixture="cluster_patterns",
)
def discover_cluster_patterns(
    cluster_engine: ClusterDiscovery,
    cluster_data: list[dict[str, Any]],
    k: int,
) -> list[PatternRecord]:
    config = ClusterConfig(n_clusters=k)
    return cluster_engine.discover_patterns(cluster_data, config)


@when(
    parsers.parse("I reduce dimensionality to {n:d} components"),
    target_fixture="reduction_result",
)
def reduce_dims(
    cluster_data: list[dict[str, Any]],
    n: int,
) -> ReductionResult:
    reducer = DimensionalityReducer()
    config = ReductionConfig(n_components=n)
    return reducer.reduce(cluster_data, config)


@when(
    parsers.parse("I run pure python kmeans with k={k:d}"),
    target_fixture="pure_kmeans_result",
)
def run_pure_kmeans(cluster_data: list[dict[str, Any]], k: int) -> dict[str, Any]:
    """Directly invoke the pure Python k-means fallback."""
    matrix = [[float(row["x"]), float(row["y"])] for row in cluster_data]
    labels, centroids, inertia = _kmeans_pure(matrix, k)
    return {"labels": labels, "centroids": centroids, "inertia": inertia, "k": k}


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then(parsers.parse("{k:d} clusters are found"))
def check_cluster_count(cluster_result: ClusterResult, k: int) -> None:
    assert cluster_result.n_clusters == k, f"Expected {k} clusters, got {cluster_result.n_clusters}"


@then(parsers.parse("each cluster has at least {min_size:d} members"))
def check_cluster_sizes(cluster_result: ClusterResult, min_size: int) -> None:
    counts: dict[int, int] = {}
    for label in cluster_result.labels:
        counts[label] = counts.get(label, 0) + 1
    for cluster_id, count in counts.items():
        assert count >= min_size, (
            f"Cluster {cluster_id} has {count} members, expected >= {min_size}"
        )


@then(parsers.parse("at least {count:d} cluster pattern is returned"))
@then(parsers.parse("at least {count:d} cluster patterns are returned"))
def check_cluster_pattern_count(cluster_patterns: list[PatternRecord], count: int) -> None:
    assert len(cluster_patterns) >= count, (
        f"Expected >= {count} cluster patterns, got {len(cluster_patterns)}"
    )


@then(parsers.parse('the pattern has type "{pattern_type}"'))
def check_pattern_type(cluster_patterns: list[PatternRecord], pattern_type: str) -> None:
    assert any(p.pattern_type == pattern_type for p in cluster_patterns), (
        f"No pattern with type {pattern_type!r} found"
    )


@then("the pattern evidence contains n_clusters")
def check_pattern_evidence_n_clusters(cluster_patterns: list[PatternRecord]) -> None:
    for p in cluster_patterns:
        if p.pattern_type == "cluster":
            assert "n_clusters" in p.evidence, (
                f"Cluster pattern missing n_clusters in evidence: {p.evidence}"
            )


@then(parsers.parse("the reduction result has {n:d} projected points"))
def check_reduction_count(reduction_result: ReductionResult, n: int) -> None:
    assert len(reduction_result.components) == n, (
        f"Expected {n} projected points, got {len(reduction_result.components)}"
    )


@then(parsers.parse("each projected point has {dims:d} dimensions"))
def check_reduction_dims(reduction_result: ReductionResult, dims: int) -> None:
    for i, point in enumerate(reduction_result.components):
        assert len(point) == dims, f"Point {i} has {len(point)} dims, expected {dims}"


@then(parsers.parse("each projected point has at most {dims:d} dimensions"))
def check_reduction_dims_at_most(reduction_result: ReductionResult, dims: int) -> None:
    for i, point in enumerate(reduction_result.components):
        assert len(point) <= dims, f"Point {i} has {len(point)} dims, expected <= {dims}"


@then("the cluster pattern evidence has method field")
def check_cluster_evidence_method(cluster_patterns: list[PatternRecord]) -> None:
    for p in cluster_patterns:
        if p.pattern_type == "cluster":
            assert "method" in p.evidence, f"Missing 'method' in evidence: {p.evidence}"


@then("the cluster pattern evidence has inertia field")
def check_cluster_evidence_inertia(cluster_patterns: list[PatternRecord]) -> None:
    for p in cluster_patterns:
        if p.pattern_type == "cluster":
            assert "inertia" in p.evidence, f"Missing 'inertia' in evidence: {p.evidence}"


@then("the cluster pattern evidence has cluster_sizes field")
def check_cluster_evidence_sizes(cluster_patterns: list[PatternRecord]) -> None:
    for p in cluster_patterns:
        if p.pattern_type == "cluster":
            assert "cluster_sizes" in p.evidence, (
                f"Missing 'cluster_sizes' in evidence: {p.evidence}"
            )


@then("the clustering runs without error")
def check_clustering_no_error(cluster_result: ClusterResult) -> None:
    # No exception means success; verify it's a valid result
    assert isinstance(cluster_result, ClusterResult)


@then(parsers.parse("the pure python result has {k:d} cluster labels"))
def check_pure_kmeans_labels(pure_kmeans_result: dict[str, Any], k: int) -> None:
    labels = pure_kmeans_result["labels"]
    unique = set(labels)
    assert len(unique) <= k, f"Expected at most {k} unique labels, got {len(unique)}: {unique}"
    assert len(labels) > 0, "No labels produced"
