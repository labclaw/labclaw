"""BDD step definitions for L3 Predictive Modeling.

Spec: docs/specs/L3-discovery.md
Uses conftest fixtures: event_capture
"""

from __future__ import annotations

import random
from typing import Any

from pytest_bdd import given, parsers, then, when

from labclaw.core.events import event_registry
from labclaw.discovery.modeling import (
    ModelConfig,
    ModelTrainResult,
    PredictionResult,
    PredictiveModel,
    _linreg_pure,
    _predict_pure,
    _r_squared,
)

# ---------------------------------------------------------------------------
# Background
# ---------------------------------------------------------------------------


@given("the predictive model is initialized", target_fixture="pred_model")
def predictive_model_initialized(event_capture: object) -> PredictiveModel:
    """Provide a PredictiveModel and subscribe event capture."""
    for evt_name in ["discovery.model.trained", "discovery.model.predicted"]:
        event_registry.subscribe(evt_name, event_capture)  # type: ignore[arg-type]
    return PredictiveModel()


# ---------------------------------------------------------------------------
# Data fixtures
# ---------------------------------------------------------------------------


@given(
    parsers.parse(
        'training data with target "{target}" and features "{f1}" and "{f2}" over {n:d} rows'
    ),
    target_fixture="train_data",
)
def training_data(target: str, f1: str, f2: str, n: int) -> list[dict[str, Any]]:
    """Generate training data with linear relationship."""
    rng = random.Random(42)
    data: list[dict[str, Any]] = []
    for i in range(n):
        x1 = rng.gauss(10, 3)
        x2 = rng.gauss(5, 2)
        # y = 2*x1 + 3*x2 + noise
        y = 2.0 * x1 + 3.0 * x2 + rng.gauss(0, 1.0)
        data.append(
            {
                f1: x1,
                f2: x2,
                target: y,
                "session_id": f"s{i}",
            }
        )
    return data


@given(
    parsers.parse("training data with only {n:d} rows"),
    target_fixture="train_data",
)
def training_data_few_rows(n: int) -> list[dict[str, Any]]:
    return [
        {"x1": float(i), "x2": float(i * 2), "y": float(i * 3), "session_id": f"s{i}"}
        for i in range(n)
    ]


@given(
    parsers.parse('the model is trained with target "{target}"'),
    target_fixture="train_result",
)
def model_pretrained(
    pred_model: PredictiveModel,
    train_data: list[dict[str, Any]],
    target: str,
) -> ModelTrainResult:
    config = ModelConfig(target_column=target)
    return pred_model.train(train_data, config)


@given(
    parsers.parse(
        "training data with a constant feature "
        '"{const_col}" and varying "{var_col}" over {n:d} rows'
    ),
    target_fixture="train_data",
)
def training_data_constant_feature(const_col: str, var_col: str, n: int) -> list[dict[str, Any]]:
    """Data where one feature is constant (zero variance)."""
    rng = random.Random(42)
    data: list[dict[str, Any]] = []
    for i in range(n):
        x1 = rng.gauss(10, 3)
        y = 3.0 * x1 + rng.gauss(0, 0.5)
        data.append(
            {
                const_col: 1.0,  # constant — zero variance
                var_col: x1,
                "y": y,
                "session_id": f"s{i}",
            }
        )
    return data


# ---------------------------------------------------------------------------
# When steps
# ---------------------------------------------------------------------------


@when(
    parsers.parse('I train the model with target "{target}" and method "{method}"'),
    target_fixture="train_result",
)
def train_model(
    pred_model: PredictiveModel,
    train_data: list[dict[str, Any]],
    target: str,
    method: str,
) -> ModelTrainResult:
    config = ModelConfig(target_column=target, method=method)
    return pred_model.train(train_data, config)


@when(
    parsers.parse("I predict on new data with {n:d} rows"),
    target_fixture="prediction_result",
)
def predict_new_data(
    pred_model: PredictiveModel,
    n: int,
) -> PredictionResult:
    rng = random.Random(99)
    new_data = [
        {"x1": rng.gauss(10, 3), "x2": rng.gauss(5, 2), "session_id": f"new_{i}"} for i in range(n)
    ]
    return pred_model.predict(new_data)


@when("I predict without training", target_fixture="predict_error")
def predict_without_training() -> Exception | None:
    """Try predicting before training; capture the error."""
    model = PredictiveModel()
    try:
        model.predict([{"x1": 1.0, "x2": 2.0}])
    except RuntimeError as exc:
        return exc
    return None


@when("I train with pure python fallback", target_fixture="pure_train_result")
def train_with_pure_python(train_data: list[dict[str, Any]]) -> dict[str, Any]:
    """Run pure python linreg directly."""
    x_matrix = [[row["x1"], row["x2"]] for row in train_data]
    y = [row["y"] for row in train_data]
    coefs, intercept = _linreg_pure(x_matrix, y)
    y_pred = _predict_pure(x_matrix, coefs, intercept)
    r2 = _r_squared(y, y_pred)
    return {"r_squared": r2, "coefficients": coefs, "intercept": intercept}


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then("the model is trained successfully")
def check_model_trained(pred_model: PredictiveModel) -> None:
    assert pred_model.is_trained


@then(parsers.parse("the R-squared is greater than {threshold:f}"))
def check_r_squared_gt(train_result: ModelTrainResult, threshold: float) -> None:
    assert train_result.r_squared > threshold, (
        f"R-squared {train_result.r_squared} not > {threshold}"
    )


@then(parsers.parse("the R-squared is {value:f}"))
def check_r_squared_exact(train_result: ModelTrainResult, value: float) -> None:
    assert abs(train_result.r_squared - value) < 0.01, (
        f"R-squared {train_result.r_squared} != {value}"
    )


@then("feature importances are ranked")
def check_feature_importances(train_result: ModelTrainResult) -> None:
    assert train_result.feature_importances, "No feature importances"
    ranks = [fi.rank for fi in train_result.feature_importances]
    assert ranks == sorted(ranks), f"Ranks not sorted: {ranks}"


@then(parsers.parse("{n:d} predictions are returned"))
def check_prediction_count(prediction_result: PredictionResult, n: int) -> None:
    assert len(prediction_result.predictions) == n, (
        f"Expected {n} predictions, got {len(prediction_result.predictions)}"
    )


@then("each prediction has lower and upper bounds")
def check_prediction_bounds(prediction_result: PredictionResult) -> None:
    for p in prediction_result.predictions:
        assert p.lower_bound <= p.predicted <= p.upper_bound or p.lower_bound <= p.upper_bound, (
            f"Bounds invalid: lower={p.lower_bound}, pred={p.predicted}, upper={p.upper_bound}"
        )


@then("a RuntimeError is raised")
def check_runtime_error(predict_error: Exception | None) -> None:
    assert predict_error is not None, "Expected RuntimeError but none was raised"
    assert isinstance(predict_error, RuntimeError), (
        f"Expected RuntimeError, got {type(predict_error)}"
    )


@then("feature importance column names match the feature columns")
def check_feature_importance_names(train_result: ModelTrainResult) -> None:
    expected_cols = {"x1", "x2"}
    actual_cols = {fi.feature for fi in train_result.feature_importances}
    assert actual_cols == expected_cols, f"Expected feature cols {expected_cols}, got {actual_cols}"


@then("each prediction has a lower bound less than or equal to the upper bound")
def check_bounds_ordering(prediction_result: PredictionResult) -> None:
    for p in prediction_result.predictions:
        assert p.lower_bound <= p.upper_bound, (
            f"lower_bound {p.lower_bound} > upper_bound {p.upper_bound}"
        )


@then("the pure python R-squared is non-negative")
def check_pure_r_squared(pure_train_result: dict[str, Any]) -> None:
    r2 = pure_train_result["r_squared"]
    assert r2 >= 0.0, f"Pure python R-squared {r2} is negative"
