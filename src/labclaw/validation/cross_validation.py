"""Cross-validation — hold-out tests, permutation tests, generalization checks.

Spec: docs/specs/L3-validation.md
Design doc: section 5.5 (Validator)
"""

from __future__ import annotations

import random


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
