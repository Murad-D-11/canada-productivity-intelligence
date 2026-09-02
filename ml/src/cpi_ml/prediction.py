"""Clean, CLI-independent prediction interface.

The backend (or any caller) can produce a forecast without knowing anything
about the training pipeline. Load a predictor once, then call ``predict`` with a
mapping of feature name -> value.

    predictor = ProductivityForecaster.load(artifacts_dir)
    result = predictor.predict({"prodLag1": 101.2, "prodLag4": 99.8, ...})
    result.prediction        # the forecast value
    result.model_version     # which model produced it
    result.target            # what is being predicted
    result.forecast_period   # optional label the caller supplied
    result.features_used     # exact feature values fed to the model (ordered)
    result.model_metadata    # full reproducibility metadata

Feature ordering is taken from the model metadata, so the caller may pass
features in any order (or omit ones the model does not use). Missing features
are passed through as NaN and handled by the model's imputer; the response
records which features were missing so callers can surface data-quality issues
rather than silently trusting an imputed prediction.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from cpi_ml.artifacts import ModelMetadata, load_artifact

if TYPE_CHECKING:
    from cpi_ml.explainability import ExplanationResult


@dataclass(frozen=True)
class PredictionResult:
    """Structured forecast output (safe to serialize to JSON for the API)."""

    prediction: float
    model_version: str
    model_type: str
    target: str
    resolution: str
    forecast_horizon: int
    forecast_period: str | None
    features_used: dict[str, float | None]
    missing_features: list[str]
    model_metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return asdict(self)


class ProductivityForecaster:
    """Wraps a trained artifact and exposes a simple ``predict`` method."""

    def __init__(self, model: Any, metadata: ModelMetadata) -> None:
        self._model = model
        self._metadata = metadata

    @classmethod
    def load(
        cls, artifacts_dir: str | Path, model_version: str | None = None
    ) -> ProductivityForecaster:
        """Load the latest artifact (or a specific version) from disk."""
        model, metadata = load_artifact(artifacts_dir, model_version)
        return cls(model, metadata)

    @property
    def metadata(self) -> ModelMetadata:
        return self._metadata

    def _vectorize(
        self, features: dict[str, float | None]
    ) -> tuple[np.ndarray, dict[str, float | None], list[str]]:
        """Build the model input row in the exact trained feature order.

        Returns (X row, ordered feature values used, missing feature names).
        """
        ordered = self._metadata.feature_names
        row: list[float] = []
        used: dict[str, float | None] = {}
        missing: list[str] = []
        for name in ordered:
            value = features.get(name, None)
            if value is None:
                missing.append(name)
                row.append(float("nan"))
                used[name] = None
            else:
                fval = float(value)
                row.append(fval)
                used[name] = fval
        return np.asarray([row], dtype=float), used, missing

    def predict(
        self, features: dict[str, float | None], *, forecast_period: str | None = None
    ) -> PredictionResult:
        """Produce a single structured forecast from a feature mapping."""
        x, used, missing = self._vectorize(features)
        raw = self._model.predict(x)
        prediction = float(np.asarray(raw).ravel()[0])

        meta = self._metadata
        return PredictionResult(
            prediction=prediction,
            model_version=meta.model_version,
            model_type=meta.model_type,
            target=meta.target,
            resolution=meta.resolution,
            forecast_horizon=meta.forecast_horizon,
            forecast_period=forecast_period,
            features_used=used,
            missing_features=missing,
            model_metadata={
                "algorithm": meta.algorithm,
                "trained_at": meta.trained_at,
                "training_period": meta.training_period,
                "validation_period": meta.validation_period,
                "test_period": meta.test_period,
                "metrics": meta.metrics,
                "feature_set_id": meta.feature_set_id,
                "notes": meta.notes,
            },
        )

    def explain(
        self, features: dict[str, float | None], *, forecast_period: str | None = None
    ) -> "ExplanationResult":
        """Explain a single forecast using the SAME model, preprocessing,
        feature ordering, and feature values as ``predict``.

        For the selected linear (ridge) model the explanation is exact: the
        reported contributions plus the base value equal the prediction. For a
        non-linear served model we report global importances as the drivers and
        note that exact per-forecast additive attribution is unavailable without
        SHAP. Every value is a model contribution (association), not a causal
        effect.
        """
        # Local import avoids a circular import at module load time.
        from cpi_ml.explainability import (
            ExplanationResult,
            _is_linear,
            _unwrap_pipeline,
            global_importance,
            linear_contributions,
        )

        x, used, missing = self._vectorize(features)
        prediction = float(np.asarray(self._model.predict(x)).ravel()[0])
        meta = self._metadata

        _, _, estimator = _unwrap_pipeline(self._model)
        if _is_linear(estimator):
            contribs, base_value = linear_contributions(
                self._model, x.ravel(), meta.feature_names, used
            )
            return ExplanationResult(
                method="exact_linear_contribution",
                prediction=prediction,
                base_value=base_value,
                target=meta.target,
                model_version=meta.model_version,
                model_type=meta.model_type,
                forecast_period=forecast_period,
                contributions=[c.as_dict() for c in contribs],
                missing_features=missing,
                notes=[
                    "base_value is the model intercept; "
                    "base_value + sum(contribution) == prediction.",
                ],
            )

        # Non-linear served model: fall back to global importance as drivers.
        importances = global_importance(self._model, meta.feature_names)
        return ExplanationResult(
            method="global_importance_fallback",
            prediction=prediction,
            base_value=float("nan"),
            target=meta.target,
            model_version=meta.model_version,
            model_type=meta.model_type,
            forecast_period=forecast_period,
            contributions=[i.as_dict() for i in importances],
            missing_features=missing,
            notes=[
                "Served model is non-linear; showing global feature importance "
                "as drivers. Exact additive per-forecast attribution would "
                "require SHAP.",
            ],
        )


def explain_prediction(
    features: dict[str, float | None],
    *,
    artifacts_dir: str | Path = "artifacts",
    model_version: str | None = None,
    forecast_period: str | None = None,
) -> "ExplanationResult":
    """Convenience: load the (latest) model and explain one forecast.

    Mirrors the shape of a plain ``explain_prediction(features)`` call while
    letting callers point at a specific artifacts dir / version. Returns the
    same structured, causality-safe result as ``ProductivityForecaster.explain``.
    """
    forecaster = ProductivityForecaster.load(artifacts_dir, model_version)
    return forecaster.explain(features, forecast_period=forecast_period)
