"""Full-coverage tests for labclaw.discovery.modeling.

Targets the uncovered lines:
  - 72, 78: _mean([]) → 0.0; _std with len <= ddof → 0.0
  - 171: ModelTrainResult for insufficient data (< 3 samples or 0 features)
  - 190, 211: sklearn random_forest branch (train + cv_score)
  - 225: cross_val_score skipped when n < 5 in linear branch
  - 290-308: random_forest training path
  - 325-328: bootstrap CI with sklearn model (get_params branch)
  - 395, 402-403: _predict_single without sklearn; _bootstrap_ci with empty train_X
  - 424-429: bootstrap fallback via _linreg_pure (exception in boot_model.fit)
  - 443: _linear_importances with empty X or empty coefficients
  - 476: _extract_Xy with missing feature column in a row
  - 494, 496: _extract_Xy extract_target=False path
"""

from __future__ import annotations

import labclaw.discovery.modeling as _modeling_mod
from labclaw.discovery.modeling import (
    ModelConfig,
    PredictiveModel,
    UncertaintyEstimate,
    _mean,
    _predict_pure,
    _r_squared,
    _std,
)

# ---------------------------------------------------------------------------
# _mean edge cases (line 72)
# ---------------------------------------------------------------------------


def test_mean_empty() -> None:
    assert _mean([]) == 0.0


def test_mean_nonempty() -> None:
    assert _mean([10.0, 20.0, 30.0]) == 20.0


# ---------------------------------------------------------------------------
# _std edge cases (line 78)
# ---------------------------------------------------------------------------


def test_std_empty() -> None:
    assert _std([]) == 0.0


def test_std_single_ddof1() -> None:
    # len([x]) == 1 <= ddof 1
    assert _std([5.0], ddof=1) == 0.0


def test_std_population_of_two() -> None:

    result = _std([0.0, 4.0], ddof=0)
    assert abs(result - 2.0) < 1e-9


# ---------------------------------------------------------------------------
# ModelTrainResult — insufficient data path (line 171)
# ---------------------------------------------------------------------------


def test_train_zero_feature_cols_returns_early() -> None:
    """Data with only the target column → feature_cols == [] → early return (line 171)."""
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
# Random forest training path (lines 190, 211, 290-308)
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
    # RF feature importances are from model.feature_importances_
    assert all(fi.importance >= 0.0 for fi in result.feature_importances)
    assert model.is_trained is True


def test_train_random_forest_cv_score_set_with_enough_data() -> None:
    """With n >= 5, cross_val_score is called and cv_score is populated (line 307-308)."""
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
# Linear model — cv_score skipped when n < 5 (line 225 is skipped; n>=5 is taken)
# ---------------------------------------------------------------------------


def test_train_linear_cv_score_with_five_samples() -> None:
    """Exactly 5 samples → cv_score branch is taken (line 320-322)."""
    data = [{"x": float(i), "y": float(i) * 2.0} for i in range(5)]
    config = ModelConfig(
        target_column="y",
        feature_columns=["x"],
        method="linear",
    )
    model = PredictiveModel()
    result = model.train(data, config)
    assert isinstance(result.cv_score, float)


def test_train_linear_cv_score_skipped_below_5(monkeypatch: object) -> None:
    """With n == 4 and sklearn available, cross_val_score is NOT called (line 225 skipped)."""
    # We test with 4 samples — sklearn is available but n < 5
    data = [{"x": float(i), "y": float(i) * 2.0} for i in range(4)]
    config = ModelConfig(
        target_column="y",
        feature_columns=["x"],
        method="linear",
    )
    model = PredictiveModel()
    result = model.train(data, config)
    # cv_score stays 0.0 because n < 5
    assert result.cv_score == 0.0


# ---------------------------------------------------------------------------
# Pure-Python fallback paths (lines 325-328)
# ---------------------------------------------------------------------------


def test_train_pure_python_fallback(monkeypatch: object) -> None:
    """With numpy unavailable, falls back to _linreg_pure (lines 325-328)."""
    monkeypatch.setattr(_modeling_mod, "np", None)
    monkeypatch.setattr(_modeling_mod, "SklearnLR", None)

    data = [{"x": float(i), "y": float(i) * 2.0} for i in range(10)]
    config = ModelConfig(target_column="y", feature_columns=["x"])
    model = PredictiveModel()
    result = model.train(data, config)

    assert result.r_squared > 0.99
    assert model.is_trained is True
    assert len(result.feature_importances) >= 1


def test_predict_pure_python_fallback(monkeypatch: object) -> None:
    """predict() with pure-python model (no sklearn model object) (line 395)."""
    monkeypatch.setattr(_modeling_mod, "np", None)
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
# _predict_single without sklearn model (line 395)
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
# _bootstrap_ci with empty train_X (lines 402-403)
# ---------------------------------------------------------------------------


def test_bootstrap_ci_empty_train_x_returns_point_pred() -> None:
    """Empty _train_X → CI is (pred, pred) (lines 402-403)."""
    model = PredictiveModel()
    model._is_trained = True
    model._coefficients = [1.0]
    model._intercept = 0.0
    model._model = None
    config = ModelConfig(target_column="y", feature_columns=["x"])
    model._config = config
    model._train_X = []  # empty!
    model._train_y = []

    lower, upper = model._bootstrap_ci([5.0])
    assert lower == 5.0
    assert upper == 5.0


# ---------------------------------------------------------------------------
# Bootstrap CI — sklearn model exception fallback (lines 424-429)
# ---------------------------------------------------------------------------


def test_bootstrap_ci_sklearn_fit_exception_falls_back_to_linreg() -> None:
    """When boot_model.fit raises, _linreg_pure is used instead (lines 424-429)."""
    from unittest.mock import MagicMock

    model = PredictiveModel()
    model._is_trained = True
    model._coefficients = [2.0]
    model._intercept = 0.0

    # Create a mock sklearn model that raises on fit
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
# _linear_importances edge cases (line 443)
# ---------------------------------------------------------------------------


def test_linear_importances_empty_x() -> None:
    """Empty X → returns [] (line 443)."""
    model = PredictiveModel()
    result = model._linear_importances([], ["a"])
    assert result == []


def test_linear_importances_empty_coefficients() -> None:
    """Empty coefficients → returns [] (line 443)."""
    model = PredictiveModel()
    model._coefficients = []
    result = model._linear_importances([[1.0, 2.0]], ["a", "b"])
    assert result == []


def test_linear_importances_all_zero_total() -> None:
    """All importances zero (constant features) → normalization total == 0 → no division."""
    model = PredictiveModel()
    model._coefficients = [0.0, 0.0]
    # Constant features → std == 0 → imp == 0 for all
    X = [[5.0, 3.0], [5.0, 3.0], [5.0, 3.0]]
    result = model._linear_importances(X, ["a", "b"])
    # All importances are 0; result is still returned (normalized to 0/0 guard)
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# _extract_Xy — missing feature columns in a row (line 476)
# ---------------------------------------------------------------------------


def test_extract_xy_skips_rows_with_missing_features() -> None:
    """Rows where a required feature column is absent are skipped (line 476)."""
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
    assert len(X) == 2  # only rows 0 and 2 have both "x" and "z"
    assert len(y) == 2
    assert cols == ["x", "z"]


# ---------------------------------------------------------------------------
# _extract_Xy — extract_target=False (lines 494, 496)
# ---------------------------------------------------------------------------


def test_extract_xy_no_target_extraction() -> None:
    """extract_target=False → y is always empty, target column presence not required."""
    data = [
        {"x": 1.0},
        {"x": 2.0},
        {"x": 3.0},
    ]
    config = ModelConfig(
        target_column="y",
        feature_columns=["x"],
    )
    X, y, cols = PredictiveModel._extract_Xy(data, config, extract_target=False)
    assert len(X) == 3
    assert y == []
    assert cols == ["x"]


def test_extract_xy_skips_row_missing_target_when_extracting() -> None:
    """Rows missing the target column are skipped when extract_target=True (line 495)."""
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
# _predict_pure helper
# ---------------------------------------------------------------------------


def test_predict_pure_basic() -> None:
    preds = _predict_pure([[1.0, 2.0], [3.0, 4.0]], [1.0, 2.0], 0.5)
    assert abs(preds[0] - (0.5 + 1.0 + 4.0)) < 1e-9  # 5.5
    assert abs(preds[1] - (0.5 + 3.0 + 8.0)) < 1e-9  # 11.5


# ---------------------------------------------------------------------------
# _r_squared — constant y → ss_tot == 0 → return 0.0 (line 225)
# ---------------------------------------------------------------------------


def test_r_squared_constant_y() -> None:
    """When all y_true values are identical, ss_tot == 0 → return 0.0 (line 225)."""
    y_true = [5.0, 5.0, 5.0, 5.0]
    y_pred = [4.0, 6.0, 5.0, 5.0]
    assert _r_squared(y_true, y_pred) == 0.0


# ---------------------------------------------------------------------------
# _linreg_pure singular matrix path (lines 171, 190)
# ---------------------------------------------------------------------------


def test_linreg_pure_singular_matrix_returns_fallback() -> None:
    """Singular X^T X → _solve_linear_system returns None → fallback (line 171)."""
    from labclaw.discovery.modeling import _linreg_pure

    # Duplicate rows → singular augmented matrix
    X = [[1.0], [1.0], [1.0]]
    y = [2.0, 3.0, 4.0]
    coefs, intercept = _linreg_pure(X, y)
    # With degenerate data, either returns the fallback [0.0]*p, mean(y) or
    # a valid solution from gaussian elimination. Just assert no crash.
    assert isinstance(coefs, list)
    assert isinstance(intercept, float)


def test_solve_linear_system_near_zero_pivot() -> None:
    """Pivot near zero → _solve_linear_system returns None (line 190)."""
    from labclaw.discovery.modeling import _solve_linear_system

    # All-zeros matrix → pivot == 0 → return None
    A = [[0.0, 0.0], [0.0, 0.0]]
    b = [1.0, 2.0]
    result = _solve_linear_system(A, b)
    assert result is None


# ---------------------------------------------------------------------------
# Integration: random_forest fallback when RandomForestRegressor is None (line 309)
# ---------------------------------------------------------------------------


def test_train_rf_method_falls_back_to_linear_when_rf_unavailable(monkeypatch: object) -> None:
    """method='random_forest' but RandomForestRegressor is None → linear branch (line 309)."""
    monkeypatch.setattr(_modeling_mod, "RandomForestRegressor", None)

    data = [{"x": float(i), "y": float(i) * 2.0} for i in range(10)]
    config = ModelConfig(
        target_column="y",
        feature_columns=["x"],
        method="random_forest",
    )
    model = PredictiveModel()
    result = model.train(data, config)
    # Falls through to SklearnLR branch
    assert result.r_squared > 0.9
    assert model.is_trained is True
