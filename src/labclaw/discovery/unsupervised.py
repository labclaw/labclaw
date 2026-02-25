"""Unsupervised discovery — dimensionality reduction, clustering, state detection.

Spec: docs/specs/L3-discovery.md (future implementation)
Design doc: section 5.3 (Discovery Loop — ASK step, unsupervised branch)

Data-driven behavioral state discovery without pre-defined labels.
Complements PatternMiner by finding hidden structure (clusters, manifolds)
rather than pairwise relationships.

Produces PatternRecord entries with pattern_type="cluster"
that feed into HypothesisGenerator.
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import UTC, datetime
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from labclaw.core.events import event_registry
from labclaw.discovery.mining import PatternRecord

try:
    from sklearn.cluster import KMeans as SklearnKMeans
    from sklearn.decomposition import PCA as SklearnPCA
except ImportError:  # pragma: no cover
    SklearnKMeans = None  # type: ignore[assignment, misc]
    SklearnPCA = None  # type: ignore[assignment, misc]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Register events
# ---------------------------------------------------------------------------

_UNSUPERVISED_EVENTS = [
    "discovery.cluster.found",
    "discovery.reduction.completed",
]

for _evt in _UNSUPERVISED_EVENTS:
    if not event_registry.is_registered(_evt):
        event_registry.register(_evt)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ClusterConfig(BaseModel):
    """Configuration for clustering."""

    n_clusters: int = 3
    method: str = "kmeans"  # "kmeans" (fallback: numpy-based)
    max_iterations: int = 100
    random_seed: int = 42
    feature_columns: list[str] = Field(default_factory=list)


class ReductionConfig(BaseModel):
    """Configuration for dimensionality reduction."""

    n_components: int = 2
    method: str = "pca"  # "pca" (fallback: numpy-based)


class ClusterResult(BaseModel):
    """Result of a clustering run."""

    labels: list[int]
    n_clusters: int
    centroids: list[list[float]]
    inertia: float = 0.0
    config: ClusterConfig


class ReductionResult(BaseModel):
    """Result of a dimensionality reduction run."""

    components: list[list[float]]  # reduced coordinates per sample
    explained_variance: list[float]
    config: ReductionConfig


# ---------------------------------------------------------------------------
# Numpy-based k-means fallback (replaces pure-Python version)
# ---------------------------------------------------------------------------


def _euclidean_dist(a: list[float], b: list[float]) -> float:
    return float(np.linalg.norm(np.array(a) - np.array(b)))


def _kmeans_pure(
    data: list[list[float]],
    k: int,
    max_iter: int = 100,
    seed: int = 42,
) -> tuple[list[int], list[list[float]], float]:
    """Numpy-based k-means clustering (sklearn fallback).

    Returns: (labels, centroids, inertia)
    """
    n = len(data)
    if n == 0 or k <= 0:
        return [], [], 0.0

    rng = random.Random(seed)
    arr = np.array(data)

    # Initialize centroids by random selection
    indices = rng.sample(range(n), min(k, n))
    centroids = arr[indices].copy()

    labels = np.zeros(n, dtype=int)

    for _ in range(max_iter):
        # Assign each point to nearest centroid
        dists = np.linalg.norm(arr[:, np.newaxis] - centroids[np.newaxis, :], axis=2)
        new_labels = np.argmin(dists, axis=1)

        if np.array_equal(new_labels, labels):
            break
        labels = new_labels

        # Update centroids
        for ki in range(k):
            members = arr[labels == ki]
            if len(members) > 0:
                centroids[ki] = members.mean(axis=0)

    # Compute inertia
    inertia = float(np.sum(np.min(
        np.linalg.norm(arr[:, np.newaxis] - centroids[np.newaxis, :], axis=2) ** 2,
        axis=1,
    )))

    return labels.tolist(), centroids.tolist(), inertia


# ---------------------------------------------------------------------------
# Numpy-based PCA fallback (replaces pure-Python power iteration)
# ---------------------------------------------------------------------------


def _pca_pure(
    data: list[list[float]],
    n_components: int = 2,
) -> tuple[list[list[float]], list[float]]:
    """Numpy-based PCA via eigendecomposition (sklearn fallback).

    Returns: (projected_data, explained_variance_per_component)
    """
    n = len(data)
    if n == 0:
        return [], []

    arr = np.array(data)
    dim = arr.shape[1]
    n_comp = min(n_components, dim, n)

    # Center data
    centered = arr - arr.mean(axis=0)

    # Covariance matrix
    cov = np.cov(centered, rowvar=False, ddof=1)
    if cov.ndim == 0:
        cov = cov.reshape(1, 1)

    # Eigendecomposition (symmetric matrix)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)

    # Sort by eigenvalue descending
    idx = np.argsort(eigenvalues)[::-1][:n_comp]
    top_vectors = eigenvectors[:, idx]
    top_values = eigenvalues[idx]

    # Project
    projected = (centered @ top_vectors).tolist()
    explained = [max(float(v), 0.0) for v in top_values]

    return projected, explained


# ---------------------------------------------------------------------------
# ClusterDiscovery
# ---------------------------------------------------------------------------


class ClusterDiscovery:
    """Clustering on feature matrices to discover subpopulations.

    Uses sklearn KMeans when available, falls back to numpy k-means.
    Produces PatternRecord entries with pattern_type="cluster".
    """

    def cluster(
        self,
        data: list[dict[str, Any]],
        config: ClusterConfig | None = None,
    ) -> ClusterResult:
        """Run clustering on numeric features extracted from data rows."""
        cfg = config or ClusterConfig()

        matrix, col_names = self._extract_features(data, cfg.feature_columns)
        k = min(cfg.n_clusters, len(matrix))
        if k <= 0:
            return ClusterResult(
                labels=[],
                n_clusters=0,
                centroids=[],
                config=cfg,
            )

        if SklearnKMeans is not None:
            arr = np.array(matrix)
            km = SklearnKMeans(
                n_clusters=k,
                max_iter=cfg.max_iterations,
                random_state=cfg.random_seed,
                n_init=10,
            )
            km.fit(arr)
            labels = km.labels_.tolist()
            centroids = km.cluster_centers_.tolist()
            inertia = float(km.inertia_)
        else:
            labels, centroids, inertia = _kmeans_pure(
                matrix,
                k,
                cfg.max_iterations,
                cfg.random_seed,
            )

        return ClusterResult(
            labels=labels,
            n_clusters=k,
            centroids=centroids,
            inertia=inertia,
            config=cfg,
        )

    def discover_patterns(
        self,
        data: list[dict[str, Any]],
        config: ClusterConfig | None = None,
    ) -> list[PatternRecord]:
        """Run clustering and convert to PatternRecord entries."""
        cfg = config or ClusterConfig()
        result = self.cluster(data, cfg)

        if result.n_clusters == 0:
            return []

        cluster_counts: dict[int, int] = {}
        for label in result.labels:
            cluster_counts[label] = cluster_counts.get(label, 0) + 1

        patterns: list[PatternRecord] = []
        pattern = PatternRecord(
            pattern_type="cluster",
            description=(
                f"Found {result.n_clusters} clusters in the data. "
                f"Cluster sizes: {dict(sorted(cluster_counts.items()))}."
            ),
            evidence={
                "n_clusters": result.n_clusters,
                "cluster_sizes": dict(sorted(cluster_counts.items())),
                "inertia": float(result.inertia),
                "method": cfg.method,
            },
            confidence=self._cluster_confidence(result),
            session_ids=[str(row.get("session_id", idx)) for idx, row in enumerate(data)],
        )
        patterns.append(pattern)

        event_registry.emit(
            "discovery.cluster.found",
            payload={
                "pattern_id": pattern.pattern_id,
                "n_clusters": result.n_clusters,
                "confidence": float(pattern.confidence),
            },
        )
        return patterns

    @staticmethod
    def _cluster_confidence(result: ClusterResult) -> float:
        """Estimate confidence based on cluster balance and inertia."""
        if not result.labels:
            return 0.0
        n = len(result.labels)
        counts = {}
        for label in result.labels:
            counts[label] = counts.get(label, 0) + 1

        ideal_size = n / result.n_clusters
        imbalance = sum(abs(c - ideal_size) for c in counts.values()) / n
        balance_score = max(0.0, 1.0 - imbalance)

        min_size = min(counts.values())
        size_penalty = 0.0 if min_size >= 2 else 0.5

        return min(max(balance_score - size_penalty, 0.0), 1.0)

    @staticmethod
    def _extract_features(
        data: list[dict[str, Any]],
        feature_columns: list[str],
    ) -> tuple[list[list[float]], list[str]]:
        """Extract numeric feature matrix from data rows."""
        if not data:
            return [], []

        if feature_columns:
            cols = feature_columns
        else:
            cols = []
            for key, val in data[0].items():
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    cols.append(key)

        if not cols:
            return [], []

        matrix: list[list[float]] = []
        for row in data:
            if all(col in row for col in cols):
                matrix.append([float(row[col]) for col in cols])

        return matrix, cols


# ---------------------------------------------------------------------------
# DimensionalityReducer
# ---------------------------------------------------------------------------


class DimensionalityReducer:
    """Dimensionality reduction for visualization and preprocessing.

    Uses sklearn PCA when available, falls back to numpy eigendecomposition.
    """

    def reduce(
        self,
        data: list[dict[str, Any]],
        config: ReductionConfig | None = None,
        feature_columns: list[str] | None = None,
    ) -> ReductionResult:
        """Reduce dimensionality of numeric features."""
        cfg = config or ReductionConfig()

        matrix, _ = ClusterDiscovery._extract_features(
            data,
            feature_columns or [],
        )
        if len(matrix) < 2:
            return ReductionResult(
                components=[],
                explained_variance=[],
                config=cfg,
            )

        if SklearnPCA is not None:
            arr = np.array(matrix)
            n_comp = min(cfg.n_components, arr.shape[1], arr.shape[0])
            pca = SklearnPCA(n_components=n_comp)
            projected = pca.fit_transform(arr).tolist()
            explained = pca.explained_variance_.tolist()
        else:
            projected, explained = _pca_pure(matrix, cfg.n_components)

        event_registry.emit(
            "discovery.reduction.completed",
            payload={
                "method": cfg.method,
                "n_components": cfg.n_components,
                "n_samples": len(matrix),
            },
        )

        return ReductionResult(
            components=projected,
            explained_variance=explained,
            config=cfg,
        )
