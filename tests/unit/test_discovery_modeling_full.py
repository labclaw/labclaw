"""Full-coverage tests for labclaw.discovery.modeling.

Targets edge cases and boundary conditions in the modeling pipeline.
"""

from __future__ import annotations

import labclaw.discovery.modeling as _modeling_mod
from labclaw.discovery.modeling import (
    ModelConfig,
    PredictiveModel,
    UncertaintyEstimate,
    _linreg_pure,
    _predict_pure,
    _r_squared,
)

# ---------------------------------------------------------------------------
# ModelTrainResult — insufficient data path
# ---------------------------------------------------------------------------


def test_train_zero_feature_cols_returns_early() -> None:
    """Data with only the target column → feature_cols == [] → early return."""
    data = [{"target": float(i)} for i in range(10)]
    config = ModelConfig(target_column="target", feature_columns=[])
    model = PredictiveModel()
    result = model.train(data, config)
    assert result.r_squared == 0.0
    assert result.n_features == 0
    assert model.is_trained is False


def test_train_too_few_samples_returns_early() -> None:
    """Fewer than 3 samples → early return."""
    data = [{"x": 1.0, "target": 2.0}, {"x": 2.0, "target": 4.0}]
    config = ModelConfig(target_column="target", feature_columns=["x"])
    model = PredictiveModel()
    result = model.train(data, config)
    assert result.n_samples == 2
    assert model.is_trained is False


# ---------------------------------------------------------------------------
# Random forest training path
# ---------------------------------------------------------------------------


def test_train_random_forest() -> None:
    """method='random_forest' trains RandomForestRegressor when sklearn available."""
    data = [{"x": float(i), "y": float(i) * 2.0 + 1.0} for i in range(20)]
    config = ModelConfig(
        target_column="y",
        feature_columns=["x"],
        method="random_forest",
        random_seed=0,
    )
    model = PredictiveModel()
    result = model.train(data, config)
    assert result.r_squared > 0.8
    assert len(result.feature_importances) >= 1
    assert all(fi.importance >= 0.0 for fi in result.feature_importances)
    assert model.is_trained is True


def test_train_random_forest_cv_score_set_with_enough_data() -> None:
    """With n >= 5, cross_val_score is called and cv_score is populated."""
    data = [{"x": float(i), "y": float(i) * 3.0} for i in range(15)]
    config = ModelConfig(
        target_column="y",
        feature_columns=["x"],
        method="random_forest",
        random_seed=42,
    )
    model = PredictiveModel()
    result = model.train(data, config)
    assert isinstance(result.cv_score, float)


def test_train_random_forest_predict() -> None:
    """Random forest can predict after training."""
    data = [{"x": float(i), "y": float(i)} for i in range(20)]
    config = ModelConfig(
        target_column="y",
        feature_columns=["x"],
        method="random_forest",
        random_seed=0,
    )
    model = PredictiveModel()
    model.train(data, config)
    pred_result = model.predict([{"x": 10.0}])
    assert len(pred_result.predictions) == 1
    est = pred_result.predictions[0]
    assert isinstance(est, UncertaintyEstimate)


# ---------------------------------------------------------------------------
# Linear model — cv_score edge cases
# ---------------------------------------------------------------------------


def test_train_linear_cv_score_with_five_samples() -> None:
    """Exactly 5 samples → cv_score branch is taken."""
    data = [{"x": float(i), "y": float(i) * 2.0} for i in range(5)]
    config = ModelConfig(
        target_column="y",
        feature_columns=["x"],
        method="linear",
    )
    model = PredictiveModel()
    result = model.train(data, config)
    assert isinstance(result.cv_score, float)


def test_train_linear_cv_score_skipped_below_5() -> None:
    """With n == 4, cross_val_score is NOT called."""
    data = [{"x": float(i), "y": float(i) * 2.0} for i in range(4)]
    config = ModelConfig(
        target_column="y",
        feature_columns=["x"],
        method="linear",
    )
    model = PredictiveModel()
    result = model.train(data, config)
    assert result.cv_score == 0.0


# ---------------------------------------------------------------------------
# Numpy-only fallback paths (sklearn unavailable)
# ---------------------------------------------------------------------------


def test_train_numpy_fallback(monkeypatch: object) -> None:
    """With sklearn unavailable, falls back to numpy OLS."""
    monkeypatch.setattr(_modeling_mod, "SklearnLR", None)

    data = [{"x": float(i), "y": float(i) * 2.0} for i in range(10)]
    config = ModelConfig(target_column="y", feature_columns=["x"])
    model = PredictiveModel()
    result = model.train(data, config)

    assert result.r_squared > 0.99
    assert model.is_trained is True
    assert len(result.feature_importances) >= 1


def test_predict_numpy_fallback(monkeypatch: object) -> None:
    """predict() with numpy-only model (no sklearn model object)."""
    monkeypatch.setattr(_modeling_mod, "SklearnLR", None)

    data = [{"x": float(i), "y": float(i) * 2.0} for i in range(10)]
    config = ModelConfig(target_column="y", feature_columns=["x"], n_bootstrap=10)
    model = PredictiveModel()
    model.train(data, config)

    pred_result = model.predict([{"x": 5.0}])
    assert len(pred_result.predictions) == 1
    est = pred_result.predictions[0]
    assert est.lower_bound <= est.predicted <= est.upper_bound


# ---------------------------------------------------------------------------
# _predict_single without sklearn model
# ---------------------------------------------------------------------------


def test_predict_single_pure_python() -> None:
    """_predict_single uses intercept + dot product when self._model is None."""
    model = PredictiveModel()
    model._is_trained = True
    model._coefficients = [2.0]
    model._intercept = 1.0
    model._model = None
    result = model._predict_single([3.0])
    assert result == 7.0  # 1.0 + 2.0 * 3.0


# ---------------------------------------------------------------------------
# _bootstrap_ci edge cases
# ---------------------------------------------------------------------------


def test_bootstrap_ci_empty_train_x_returns_point_pred() -> None:
    """Empty _train_X → CI is (pred, pred)."""
    model = PredictiveModel()
    model._is_trained = True
    model._coefficients = [1.0]
    model._intercept = 0.0
    model._model = None
    config = ModelConfig(target_column="y", feature_columns=["x"])
    model._config = config
    model._train_X = []
    model._train_y = []

    lower, upper = model._bootstrap_ci([5.0])
    assert lower == 5.0
    assert upper == 5.0


def test_bootstrap_ci_sklearn_fit_exception_falls_back() -> None:
    """When boot_model.fit raises, numpy OLS is used instead."""
    from unittest.mock import MagicMock

    model = PredictiveModel()
    model._is_trained = True
    model._coefficients = [2.0]
    model._intercept = 0.0

    bad_model = MagicMock()
    bad_model.get_params.return_value = {}
    bad_model.fit.side_effect = RuntimeError("simulated sklearn failure")
    model._model = bad_model

    config = ModelConfig(
        target_column="y",
        feature_columns=["x"],
        n_bootstrap=5,
        random_seed=0,
    )
    model._config = config
    model._train_X = [[float(i)] for i in range(5)]
    model._train_y = [float(i) * 2.0 for i in range(5)]

    lower, upper = model._bootstrap_ci([3.0])
    assert isinstance(lower, float)
    assert isinstance(upper, float)


# ---------------------------------------------------------------------------
# _linear_importances edge cases
# ---------------------------------------------------------------------------


def test_linear_importances_empty_x() -> None:
    model = PredictiveModel()
    result = model._linear_importances([], ["a"])
    assert result == []


def test_linear_importances_empty_coefficients() -> None:
    model = PredictiveModel()
    model._coefficients = []
    result = model._linear_importances([[1.0, 2.0]], ["a", "b"])
    assert result == []


def test_linear_importances_all_zero_total() -> None:
    """All importances zero (constant features) → normalization handles 0/0."""
    model = PredictiveModel()
    model._coefficients = [0.0, 0.0]
    X = [[5.0, 3.0], [5.0, 3.0], [5.0, 3.0]]
    result = model._linear_importances(X, ["a", "b"])
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# _extract_Xy edge cases
# ---------------------------------------------------------------------------


def test_extract_xy_skips_rows_with_missing_features() -> None:
    data = [
        {"x": 1.0, "z": 10.0, "y": 2.0},
        {"x": 2.0, "y": 4.0},  # missing "z"
        {"x": 3.0, "z": 30.0, "y": 6.0},
    ]
    config = ModelConfig(
        target_column="y",
        feature_columns=["x", "z"],
    )
    X, y, cols = PredictiveModel._extract_Xy(data, config)
    assert len(X) == 2
    assert len(y) == 2
    assert cols == ["x", "z"]


def test_extract_xy_no_target_extraction() -> None:
    data = [{"x": 1.0}, {"x": 2.0}, {"x": 3.0}]
    config = ModelConfig(target_column="y", feature_columns=["x"])
    X, y, cols = PredictiveModel._extract_Xy(data, config, extract_target=False)
    assert len(X) == 3
    assert y == []
    assert cols == ["x"]


def test_extract_xy_skips_row_missing_target_when_extracting() -> None:
    data = [
        {"x": 1.0, "y": 2.0},
        {"x": 2.0},  # no "y"
        {"x": 3.0, "y": 6.0},
    ]
    config = ModelConfig(target_column="y", feature_columns=["x"])
    X, y, _ = PredictiveModel._extract_Xy(data, config, extract_target=True)
    assert len(X) == 2
    assert len(y) == 2


# ---------------------------------------------------------------------------
# _predict_pure / _r_squared / _linreg_pure helpers
# ---------------------------------------------------------------------------


def test_predict_pure_basic() -> None:
    preds = _predict_pure([[1.0, 2.0], [3.0, 4.0]], [1.0, 2.0], 0.5)
    assert abs(preds[0] - (0.5 + 1.0 + 4.0)) < 1e-9  # 5.5
    assert abs(preds[1] - (0.5 + 3.0 + 8.0)) < 1e-9  # 11.5


def test_r_squared_constant_y() -> None:
    """When all y_true values are identical, ss_tot == 0 → return 0.0."""
    y_true = [5.0, 5.0, 5.0, 5.0]
    y_pred = [4.0, 6.0, 5.0, 5.0]
    assert _r_squared(y_true, y_pred) == 0.0


def test_linreg_pure_singular_matrix_returns_fallback() -> None:
    """Singular X^T X → lstsq handles gracefully."""
    # Duplicate rows → degenerate, but lstsq still returns a solution
    X = [[1.0], [1.0], [1.0]]
    y = [2.0, 3.0, 4.0]
    coefs, intercept = _linreg_pure(X, y)
    assert isinstance(coefs, list)
    assert isinstance(intercept, float)


# ---------------------------------------------------------------------------
# Integration: RF fallback when RandomForestRegressor is None
# ---------------------------------------------------------------------------


def test_train_rf_method_falls_back_to_linear_when_rf_unavailable(monkeypatch: object) -> None:
    """method='random_forest' but RandomForestRegressor is None → linear branch."""
    monkeypatch.setattr(_modeling_mod, "RandomForestRegressor", None)

    data = [{"x": float(i), "y": float(i) * 2.0} for i in range(10)]
    config = ModelConfig(
        target_column="y",
        feature_columns=["x"],
        method="random_forest",
    )
    model = PredictiveModel()
    result = model.train(data, config)
    assert result.r_squared > 0.9
    assert model.is_trained is True
