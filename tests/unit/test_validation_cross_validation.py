from __future__ import annotations

import pytest

from labclaw.validation.cross_validation import holdout_validate, kfold_validate, permutation_test

# ---------------------------------------------------------------------------
# holdout_validate
# ---------------------------------------------------------------------------


def test_holdout_validate_normal_keys_and_sizes() -> None:
    data = list(range(10))
    result = holdout_validate(data, train_fraction=0.8, seed=0)

    assert set(result.keys()) == {"train_mean", "test_mean", "train_size", "test_size", "mae"}
    assert result["train_size"] + result["test_size"] == 10.0
    assert result["train_size"] >= 1.0
    assert result["test_size"] >= 1.0


def test_holdout_validate_edge_two_elements() -> None:
    result = holdout_validate([1.0, 2.0], train_fraction=0.5, seed=0)

    assert result["train_size"] + result["test_size"] == 2.0
    assert "mae" in result


def test_holdout_validate_empty_raises() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        holdout_validate([])


def test_holdout_validate_fraction_zero_raises() -> None:
    with pytest.raises(ValueError, match="train_fraction"):
        holdout_validate([1.0, 2.0], train_fraction=0.0)


def test_holdout_validate_fraction_one_raises() -> None:
    with pytest.raises(ValueError, match="train_fraction"):
        holdout_validate([1.0, 2.0], train_fraction=1.0)


def test_holdout_validate_seed_reproducibility() -> None:
    data = [float(i) for i in range(20)]
    r1 = holdout_validate(data, seed=99)
    r2 = holdout_validate(data, seed=99)

    assert r1 == r2


# ---------------------------------------------------------------------------
# kfold_validate
# ---------------------------------------------------------------------------


def test_kfold_validate_five_folds_on_twenty() -> None:
    data = list(range(20))
    result = kfold_validate(data, k=5, seed=0)

    assert result["k"] == 5
    assert len(result["fold_maes"]) == 5
    assert "mean_mae" in result
    assert "std_mae" in result


def test_kfold_validate_k2_on_four() -> None:
    result = kfold_validate([1.0, 2.0, 3.0, 4.0], k=2, seed=0)

    assert result["k"] == 2
    assert len(result["fold_maes"]) == 2


def test_kfold_validate_k_greater_than_data_raises() -> None:
    with pytest.raises(ValueError, match="k.*must be <= len"):
        kfold_validate([1.0, 2.0, 3.0], k=5)


def test_kfold_validate_empty_raises() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        kfold_validate([])


def test_kfold_validate_k_less_than_two_raises() -> None:
    with pytest.raises(ValueError, match="k must be >= 2"):
        kfold_validate([1.0, 2.0, 3.0], k=1)


# ---------------------------------------------------------------------------
# permutation_test
# ---------------------------------------------------------------------------


def test_permutation_test_known_different_groups_low_p() -> None:
    group_a = [0.0] * 20
    group_b = [10.0] * 20
    result = permutation_test(group_a, group_b, n_perms=1000, seed=42)

    assert result["p_value"] < 0.05


def test_permutation_test_identical_groups_high_p() -> None:
    group_a = [5.0] * 20
    group_b = [5.0] * 20
    result = permutation_test(group_a, group_b, n_perms=1000, seed=42)

    assert result["p_value"] > 0.1


def test_permutation_test_empty_group_a_raises() -> None:
    with pytest.raises(ValueError, match="group_a must be non-empty"):
        permutation_test([], [1.0, 2.0])


def test_permutation_test_empty_group_b_raises() -> None:
    with pytest.raises(ValueError, match="group_b must be non-empty"):
        permutation_test([1.0, 2.0], [])
