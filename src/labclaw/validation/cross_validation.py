"""Cross-validation — hold-out tests, permutation tests, generalization checks.

Spec: docs/specs/L3-validation.md
Design doc: section 5.5 (Validator)
"""

from __future__ import annotations

import math
import random
from typing import Any


def holdout_validate(
    data: list[float],
    train_fraction: float = 0.8,
    seed: int = 42,
) -> dict[str, float]:
    """Basic hold-out validation: split data, compute train/test means and MAE.

    Args:
        data: Input data values.
        train_fraction: Fraction of data to use for training (0 < x < 1).
        seed: Random seed for reproducibility.

    Returns:
        Dict with keys: train_mean, test_mean, train_size, test_size, mae.

    Raises:
        ValueError: If data is empty or train_fraction is out of range.
    """
    if not data:
        raise ValueError("Data must be non-empty")
    if not 0 < train_fraction < 1:
        raise ValueError(f"train_fraction must be in (0, 1), got {train_fraction}")

    shuffled = list(data)
    rng = random.Random(seed)
    rng.shuffle(shuffled)

    split_idx = max(1, int(len(shuffled) * train_fraction))
    train = shuffled[:split_idx]
    test = shuffled[split_idx:] if split_idx < len(shuffled) else shuffled[-1:]

    train_mean = sum(train) / len(train)
    test_mean = sum(test) / len(test)

    # MAE: how well the train mean predicts test values
    mae = sum(abs(v - train_mean) for v in test) / len(test)

    return {
        "train_mean": train_mean,
        "test_mean": test_mean,
        "train_size": float(len(train)),
        "test_size": float(len(test)),
        "mae": mae,
    }


def kfold_validate(
    data: list[float],
    k: int = 5,
    seed: int = 42,
) -> dict[str, Any]:
    """K-fold cross-validation returning per-fold MAE plus mean and std.

    Args:
        data: Input data values.
        k: Number of folds (must be >= 2 and <= len(data)).
        seed: Random seed for reproducibility.

    Returns:
        Dict with keys: k, fold_maes, mean_mae, std_mae.

    Raises:
        ValueError: If data is empty, k < 2, or k > len(data).
    """
    if not data:
        raise ValueError("Data must be non-empty")
    if k < 2:
        raise ValueError(f"k must be >= 2, got {k}")
    if k > len(data):
        raise ValueError(f"k ({k}) must be <= len(data) ({len(data)})")

    shuffled = list(data)
    rng = random.Random(seed)
    rng.shuffle(shuffled)

    fold_maes: list[float] = []
    for i in range(k):
        test = shuffled[i::k]
        train = [v for j, v in enumerate(shuffled) if j % k != i]
        train_mean = sum(train) / len(train)
        mae = sum(abs(v - train_mean) for v in test) / len(test)
        fold_maes.append(mae)

    mean_mae = sum(fold_maes) / k
    std_mae = math.sqrt(sum((m - mean_mae) ** 2 for m in fold_maes) / k)

    return {
        "k": k,
        "fold_maes": fold_maes,
        "mean_mae": mean_mae,
        "std_mae": std_mae,
    }


def permutation_test(
    group_a: list[float],
    group_b: list[float],
    n_perms: int = 1000,
    seed: int = 42,
) -> dict[str, float | int]:
    """Permutation test for difference in means between two groups.

    Args:
        group_a: First group of values.
        group_b: Second group of values.
        n_perms: Number of permutations.
        seed: Random seed for reproducibility.

    Returns:
        Dict with keys: observed_diff, p_value, n_perms.

    Raises:
        ValueError: If either group is empty.
    """
    if not group_a:
        raise ValueError("group_a must be non-empty")
    if not group_b:
        raise ValueError("group_b must be non-empty")
    if n_perms < 1:
        raise ValueError(f"n_perms must be >= 1, got {n_perms}")

    combined = list(group_a) + list(group_b)
    n_a = len(group_a)
    observed_diff = abs(sum(group_a) / n_a - sum(group_b) / len(group_b))

    rng = random.Random(seed)
    count_extreme = 0
    for _ in range(n_perms):
        rng.shuffle(combined)
        perm_a = combined[:n_a]
        perm_b = combined[n_a:]
        perm_diff = abs(sum(perm_a) / len(perm_a) - sum(perm_b) / len(perm_b))
        if perm_diff >= observed_diff:
            count_extreme += 1

    return {
        "observed_diff": observed_diff,
        "p_value": count_extreme / n_perms,
        "n_perms": n_perms,
    }
