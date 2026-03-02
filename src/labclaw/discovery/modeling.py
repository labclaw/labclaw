"""Predictive modeling — feature importance, uncertainty quantification.

Spec: docs/specs/L3-discovery.md (future implementation)
Design doc: section 5.3 (Discovery Loop — PREDICT step)

Maps to the PREDICT step of the scientific method:
instead of low-dimensional linear predictions,
build multi-variable nonlinear models with calibrated uncertainty.

Consumes data rows and builds regression/classification models that
quantify uncertainty and feature importance for each target variable.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from labclaw.core.events import event_registry

try:
    from sklearn.ensemble import RandomForestRegressor  # pragma: no cover
    from sklearn.linear_model import LinearRegression as SklearnLR  # pragma: no cover
    from sklearn.model_selection import cross_val_score  # pragma: no cover
except ImportError:  # pragma: no cover
    RandomForestRegressor = None  # type: ignore[assignment, misc]
    SklearnLR = None  # type: ignore[assignment, misc]
    cross_val_score = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Register events
# ---------------------------------------------------------------------------

_MODELING_EVENTS = [
    "discovery.model.trained",
    "discovery.model.predicted",
]

for _evt in _MODELING_EVENTS:
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


class ModelConfig(BaseModel):
    """Configuration for predictive model training."""

    target_column: str
    feature_columns: list[str] = Field(default_factory=list)
    method: str = "linear"  # "linear" or "random_forest"
    n_bootstrap: int = 100
    confidence_level: float = 0.95
    random_seed: int = 42


class FeatureImportance(BaseModel):
    """Feature importance score for a single feature."""

    feature: str
    importance: float
    rank: int


class UncertaintyEstimate(BaseModel):
    """Calibrated prediction with confidence interval."""

    predicted: float
    lower_bound: float
    upper_bound: float
    confidence_level: float


class ModelTrainResult(BaseModel):
    """Result of training a predictive model."""

    model_id: str = Field(default_factory=_uuid)
    config: ModelConfig
    r_squared: float = 0.0
    cv_score: float = 0.0
    feature_importances: list[FeatureImportance] = Field(default_factory=list)
    n_samples: int = 0
    n_features: int = 0
    trained_at: datetime = Field(default_factory=_now)


class PredictionResult(BaseModel):
    """Result of a prediction with uncertainty."""

    predictions: list[UncertaintyEstimate]
    model_id: str


# ---------------------------------------------------------------------------
# Numpy-based math helpers (replacing pure-Python fallbacks)
# ---------------------------------------------------------------------------


def _linreg_pure(
    X: list[list[float]],
    y: list[float],
) -> tuple[list[float], float]:
    """OLS linear regression via numpy least-squares.

    Returns: (coefficients, intercept)
    """
    n = len(X)
    if n == 0:
        return [], 0.0

    X_arr = np.array(X)
    y_arr = np.array(y)

    # Add intercept column
    ones = np.ones((n, 1))
    X_aug = np.hstack([ones, X_arr])

    result, _, _, _ = np.linalg.lstsq(X_aug, y_arr, rcond=None)
    return result[1:].tolist(), float(result[0])


def _predict_pure(
    X: list[list[float]],
    coefficients: list[float],
    intercept: float,
) -> list[float]:
    """Predict using linear model coefficients."""
    return (np.array(X) @ np.array(coefficients) + intercept).tolist()  # type: ignore[no-any-return]


def _r_squared(y_true: list[float], y_pred: list[float]) -> float:
    """Compute R-squared (coefficient of determination)."""
    if len(y_true) < 2:
        return 0.0
    yt = np.array(y_true)
    yp = np.array(y_pred)
    ss_tot = float(np.sum((yt - np.mean(yt)) ** 2))
    if ss_tot == 0:
        return 0.0
    ss_res = float(np.sum((yt - yp) ** 2))
    return 1.0 - ss_res / ss_tot


# ---------------------------------------------------------------------------
# PredictiveModel
# ---------------------------------------------------------------------------


class PredictiveModel:
    """Trains on experimental data, outputs predictions with confidence intervals.

    Uses sklearn when available (LinearRegression or RandomForestRegressor),
    falls back to numpy OLS.
    """

    def __init__(self) -> None:
        self._model: Any = None
        self._coefficients: list[float] = []
        self._intercept: float = 0.0
        self._config: ModelConfig | None = None
        self._feature_cols: list[str] = []
        self._is_trained = False
        # Store training data for bootstrap uncertainty
        self._train_X: list[list[float]] = []
        self._train_y: list[float] = []

    @property
    def is_trained(self) -> bool:
        return self._is_trained

    def train(
        self,
        data: list[dict[str, Any]],
        config: ModelConfig,
    ) -> ModelTrainResult:
        """Train the model on data rows.

        Returns ModelTrainResult with R-squared, CV score, and feature importances.
        """
        self._config = config

        # Extract features and target
        X, y, feature_cols = self._extract_Xy(data, config)
        self._feature_cols = feature_cols
        self._train_X = X
        self._train_y = y

        if len(X) < 3 or len(feature_cols) == 0:
            return ModelTrainResult(
                config=config,
                n_samples=len(X),
                n_features=len(feature_cols),
            )

        # Train
        r_squared = 0.0
        cv_score = 0.0
        importances: list[FeatureImportance] = []

        if SklearnLR is not None:  # pragma: no cover
            X_arr = np.array(X)
            y_arr = np.array(y)

            if config.method == "random_forest" and RandomForestRegressor is not None:
                model = RandomForestRegressor(
                    n_estimators=50,
                    random_state=config.random_seed,
                )
                model.fit(X_arr, y_arr)
                self._model = model
                r_squared = float(model.score(X_arr, y_arr))

                # Feature importances from RF
                fi = model.feature_importances_
                for rank, idx in enumerate(fi.argsort()[::-1], 1):
                    importances.append(
                        FeatureImportance(
                            feature=feature_cols[idx],
                            importance=float(fi[idx]),
                            rank=rank,
                        )
                    )

                if cross_val_score is not None and len(X) >= 5:
                    cv = cross_val_score(model, X_arr, y_arr, cv=min(5, len(X)))
                    cv_score = float(cv.mean())
            else:
                model = SklearnLR()
                model.fit(X_arr, y_arr)
                self._model = model
                self._coefficients = model.coef_.tolist()
                self._intercept = float(model.intercept_)
                r_squared = float(model.score(X_arr, y_arr))

                # Feature importances from |coefficient * std(feature)|
                importances = self._linear_importances(X, feature_cols)

                if cross_val_score is not None and len(X) >= 5:
                    cv = cross_val_score(model, X_arr, y_arr, cv=min(5, len(X)))
                    cv_score = float(cv.mean())
        else:
            # Numpy-only fallback (no sklearn)
            self._coefficients, self._intercept = _linreg_pure(X, y)
            y_pred = _predict_pure(X, self._coefficients, self._intercept)
            r_squared = _r_squared(y, y_pred)
            importances = self._linear_importances(X, feature_cols)

        self._is_trained = True

        result = ModelTrainResult(
            config=config,
            r_squared=r_squared,
            cv_score=cv_score,
            feature_importances=importances,
            n_samples=len(X),
            n_features=len(feature_cols),
        )

        event_registry.emit(
            "discovery.model.trained",
            payload={
                "model_id": result.model_id,
                "method": config.method,
                "r_squared": float(r_squared),
                "n_samples": len(X),
            },
        )
        return result

    def predict(
        self,
        data: list[dict[str, Any]],
    ) -> PredictionResult:
        """Predict target values with uncertainty estimates.

        Uses bootstrap resampling for confidence intervals.
        Requires the model to be trained first.
        """
        if not self._is_trained or self._config is None:
            raise RuntimeError("Model must be trained before prediction")

        X_new, _, _ = self._extract_Xy(
            data,
            self._config,
            extract_target=False,
        )

        predictions: list[UncertaintyEstimate] = []

        for row in X_new:
            point_pred = self._predict_single(row)
            lower, upper = self._bootstrap_ci(row)
            predictions.append(
                UncertaintyEstimate(
                    predicted=point_pred,
                    lower_bound=lower,
                    upper_bound=upper,
                    confidence_level=self._config.confidence_level,
                )
            )

        model_id = _uuid()
        event_registry.emit(
            "discovery.model.predicted",
            payload={
                "model_id": model_id,
                "n_predictions": len(predictions),
            },
        )

        return PredictionResult(predictions=predictions, model_id=model_id)

    def _predict_single(self, x: list[float]) -> float:
        """Predict a single point."""
        if self._model is not None:  # pragma: no cover
            return float(self._model.predict(np.array([x]))[0])
        return self._intercept + sum(c * xi for c, xi in zip(self._coefficients, x))

    def _bootstrap_ci(self, x: list[float]) -> tuple[float, float]:
        """Bootstrap confidence interval for a single prediction."""
        if not self._train_X or self._config is None:
            pred = self._predict_single(x)
            return pred, pred

        n = len(self._train_X)
        n_boot = min(self._config.n_bootstrap, 50)
        alpha = 1.0 - self._config.confidence_level

        import random

        rng = random.Random(self._config.random_seed)

        boot_preds: list[float] = []
        for _ in range(n_boot):
            indices = [rng.randint(0, n - 1) for _ in range(n)]
            X_boot = [self._train_X[i] for i in indices]
            y_boot = [self._train_y[i] for i in indices]

            if self._model is not None and hasattr(self._model, "get_params"):
                try:
                    boot_model = type(self._model)(**self._model.get_params())
                    boot_model.fit(np.array(X_boot), np.array(y_boot))
                    pred = float(boot_model.predict(np.array([x]))[0])
                except Exception:  # pragma: no cover
                    coefs, intercept = _linreg_pure(X_boot, y_boot)
                    pred = intercept + sum(c * xi for c, xi in zip(coefs, x))
            else:
                coefs, intercept = _linreg_pure(X_boot, y_boot)
                pred = intercept + sum(c * xi for c, xi in zip(coefs, x))
            boot_preds.append(pred)

        boot_preds.sort()
        lower_idx = max(0, int(alpha / 2 * n_boot) - 1)
        upper_idx = min(n_boot - 1, int((1.0 - alpha / 2) * n_boot))

        return boot_preds[lower_idx], boot_preds[upper_idx]

    def _linear_importances(
        self,
        X: list[list[float]],
        feature_cols: list[str],
    ) -> list[FeatureImportance]:
        """Compute feature importances from linear coefficients * feature std."""
        if not X or not self._coefficients:
            return []

        X_arr = np.array(X)
        p = len(feature_cols)
        importances: list[tuple[str, float]] = []

        for j in range(min(p, len(self._coefficients))):
            std_val = float(np.std(X_arr[:, j]))
            imp = abs(self._coefficients[j]) * std_val
            importances.append((feature_cols[j], imp))

        # Normalize
        total = sum(imp for _, imp in importances)
        if total > 0:
            importances = [(f, imp / total) for f, imp in importances]

        # Sort by importance descending
        importances.sort(key=lambda x: x[1], reverse=True)

        return [
            FeatureImportance(feature=f, importance=imp, rank=rank)
            for rank, (f, imp) in enumerate(importances, 1)
        ]

    @staticmethod
    def _extract_Xy(
        data: list[dict[str, Any]],
        config: ModelConfig,
        extract_target: bool = True,
    ) -> tuple[list[list[float]], list[float], list[str]]:
        """Extract feature matrix X and target vector y from data rows."""
        if not data:
            return [], [], []

        # Determine feature columns
        if config.feature_columns:
            feature_cols = [c for c in config.feature_columns if c != config.target_column]
        else:
            feature_cols = []
            for key, val in data[0].items():
                if key == config.target_column:
                    continue
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    feature_cols.append(key)

        X: list[list[float]] = []
        y: list[float] = []

        for row in data:
            if not all(col in row for col in feature_cols):
                continue
            if extract_target and config.target_column not in row:
                continue

            x_row = [float(row[col]) for col in feature_cols]
            X.append(x_row)
            if extract_target:
                y.append(float(row[config.target_column]))

        return X, y, feature_cols
