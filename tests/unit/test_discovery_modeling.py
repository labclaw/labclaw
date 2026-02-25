"""Tests for predictive modeling module.

Covers:
- src/labclaw/discovery/modeling.py  (PredictiveModel, ModelConfig, PredictionResult)
"""

from __future__ import annotations

import pytest

from labclaw.discovery.modeling import (
    ModelConfig,
    ModelTrainResult,
    PredictionResult,
    PredictiveModel,
    UncertaintyEstimate,
    _linreg_pure,
    _r_squared,
)

# Note: _mean/_std removed in wheel replacement; _linreg_pure/_r_squared kept with numpy impl

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _linear_data() -> list[dict[str, float]]:
    """Perfect linear data: y = 2x."""
    return [{"x": float(i), "y": float(2 * i)} for i in range(1, 11)]


# ---------------------------------------------------------------------------
# PredictiveModel — train + predict
# ---------------------------------------------------------------------------


class TestPredictiveModel:
    def test_linear_model_fit_predict(self) -> None:
        data = _linear_data()
        config = ModelConfig(target_column="y", feature_columns=["x"])
        model = PredictiveModel()
        train_result = model.train(data, config)

        assert train_result.n_samples == 10
        assert train_result.n_features == 1
        assert train_result.r_squared == pytest.approx(1.0, abs=1e-4)
        assert model.is_trained is True

        pred_result = model.predict([{"x": 20.0}])
        assert isinstance(pred_result, PredictionResult)
        assert len(pred_result.predictions) == 1
        # y = 2*20 = 40
        assert pred_result.predictions[0].predicted == pytest.approx(40.0, abs=0.5)

    def test_linear_model_metrics(self) -> None:
        data = _linear_data()
        config = ModelConfig(target_column="y", feature_columns=["x"])
        model = PredictiveModel()
        result = model.train(data, config)

        assert isinstance(result, ModelTrainResult)
        assert result.r_squared >= 0.99
        # When sklearn is available, cv_score is set for n>=5; for pure Python it stays 0
        assert isinstance(result.cv_score, float)

    def test_predict_before_train_raises(self) -> None:
        model = PredictiveModel()
        with pytest.raises(RuntimeError, match="trained"):
            model.predict([{"x": 1.0}])

    def test_train_insufficient_data_returns_empty_result(self) -> None:
        """Less than 3 samples → returns result with 0 r_squared, not trained."""
        data = [{"x": 1.0, "y": 2.0}]
        config = ModelConfig(target_column="y", feature_columns=["x"])
        model = PredictiveModel()
        result = model.train(data, config)
        assert result.r_squared == 0.0
        assert model.is_trained is False

    def test_train_auto_detects_feature_columns(self) -> None:
        data = [{"a": float(i), "b": float(i * 3), "y": float(i * 5)} for i in range(1, 8)]
        config = ModelConfig(target_column="y")
        model = PredictiveModel()
        result = model.train(data, config)
        assert result.n_features == 2
        assert result.n_samples == 7

    def test_uncertainty_estimate_has_bounds(self) -> None:
        data = _linear_data()
        config = ModelConfig(target_column="y", feature_columns=["x"], n_bootstrap=20)
        model = PredictiveModel()
        model.train(data, config)
        pred_result = model.predict([{"x": 5.0}])

        est = pred_result.predictions[0]
        assert isinstance(est, UncertaintyEstimate)
        assert est.lower_bound <= est.predicted
        assert est.predicted <= est.upper_bound

    def test_feature_importances_populated(self) -> None:
        data = _linear_data()
        config = ModelConfig(target_column="y", feature_columns=["x"])
        model = PredictiveModel()
        result = model.train(data, config)
        # Should have at least one importance entry for single feature
        assert len(result.feature_importances) >= 1

    def test_model_id_is_string(self) -> None:
        data = _linear_data()
        config = ModelConfig(target_column="y", feature_columns=["x"])
        model = PredictiveModel()
        result = model.train(data, config)
        assert isinstance(result.model_id, str)
        assert len(result.model_id) > 0


# ---------------------------------------------------------------------------
# Pure-Python math helpers
# ---------------------------------------------------------------------------


class TestLinregPure:
    def test_perfect_linear_fit(self) -> None:
        x_mat = [[float(i)] for i in range(1, 6)]
        y = [float(2 * i) for i in range(1, 6)]
        coefs, intercept = _linreg_pure(x_mat, y)
        assert coefs[0] == pytest.approx(2.0, abs=1e-6)
        assert intercept == pytest.approx(0.0, abs=1e-6)

    def test_empty_data_returns_zeros(self) -> None:
        coefs, intercept = _linreg_pure([], [])
        assert coefs == []
        assert intercept == 0.0

    def test_r_squared_perfect(self) -> None:
        y_true = [1.0, 2.0, 3.0, 4.0]
        y_pred = [1.0, 2.0, 3.0, 4.0]
        assert _r_squared(y_true, y_pred) == pytest.approx(1.0)

    def test_r_squared_constant_prediction(self) -> None:
        """If all predictions equal the mean, R^2 is 0."""
        y_true = [1.0, 2.0, 3.0]
        y_pred = [2.0, 2.0, 2.0]
        r2 = _r_squared(y_true, y_pred)
        assert r2 == pytest.approx(0.0, abs=1e-10)

    def test_r_squared_insufficient_data(self) -> None:
        assert _r_squared([1.0], [1.0]) == 0.0


# ---------------------------------------------------------------------------
# ModelConfig defaults
# ---------------------------------------------------------------------------


class TestModelConfig:
    def test_defaults(self) -> None:
        cfg = ModelConfig(target_column="target")
        assert cfg.method == "linear"
        assert cfg.n_bootstrap == 100
        assert cfg.confidence_level == 0.95
        assert cfg.random_seed == 42
        assert cfg.feature_columns == []
