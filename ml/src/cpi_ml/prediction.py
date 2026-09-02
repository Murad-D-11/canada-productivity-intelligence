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
from typing import Any

import numpy as np

from cpi_ml.artifacts import ModelMetadata, load_artifact


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
