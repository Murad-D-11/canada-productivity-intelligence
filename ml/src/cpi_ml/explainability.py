"""Model explainability.

Two layers live here:

  * Legacy SHAP aggregation helpers (``mean_absolute_attributions`` etc.) kept
    for tree models and any future SHAP-based reporting.
  * An exact, deterministic explainer for the SELECTED linear (ridge) model:
    ``global_importance`` and per-forecast ``contributions``. For a linear model
    inside a ``SimpleImputer -> StandardScaler -> Ridge`` pipeline, the
    prediction decomposes exactly as

        prediction = intercept + sum_i ( coef_i * scaled_value_i )

    where ``scaled_value_i = (imputed_i - scaler.mean_i) / scaler.scale_i``.
    Each term ``coef_i * scaled_value_i`` is that feature's contribution to this
    specific prediction. This is the same decomposition SHAP's LinearExplainer
    produces for a linear model, computed in closed form — so it is exact, fast,
    and needs no extra dependency or sampling approximation.

CRITICAL — association, not causation:
Every value here is a MODEL CONTRIBUTION (a "prediction driver") describing how a
feature relates to the model's output on historical data. It is NOT a causal
effect. A large contribution does NOT mean that changing the feature would cause
productivity to change. Naming, docstrings, and metadata all preserve this.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from cpi_ml.feature_metadata import get_feature_meta


@dataclass(frozen=True)
class FeatureAttribution:
    """Mean absolute SHAP contribution for a single feature."""

    feature: str
    mean_abs_contribution: float


def mean_absolute_attributions(
    shap_values: np.ndarray, feature_names: list[str]
) -> list[FeatureAttribution]:
    """Aggregate per-sample SHAP values into mean absolute contributions.

    ``shap_values`` has shape (n_samples, n_features). Returns attributions
    sorted from most to least influential.
    """
    if shap_values.ndim != 2:
        raise ValueError("Expected a 2D SHAP value matrix")
    if shap_values.shape[1] != len(feature_names):
        raise ValueError("feature_names length must match SHAP columns")

    means = np.abs(shap_values).mean(axis=0)
    attributions = [
        FeatureAttribution(feature=name, mean_abs_contribution=float(value))
        for name, value in zip(feature_names, means, strict=True)
    ]
    attributions.sort(key=lambda a: a.mean_abs_contribution, reverse=True)
    return attributions


def attributions_to_frame(attributions: list[FeatureAttribution]) -> pd.DataFrame:
    """Convert attribution records to a tidy DataFrame for storage/reporting."""
    return pd.DataFrame(
        [{"feature": a.feature, "mean_abs_contribution": a.mean_abs_contribution} for a in attributions]
    )


# ---------------------------------------------------------------------------
# Exact analytic explainer for the selected linear (ridge) model
# ---------------------------------------------------------------------------


def _direction_label(value: float) -> str:
    """Map a signed contribution/coefficient to a direction word."""
    if value > 0:
        return "increases"
    if value < 0:
        return "decreases"
    return "neutral"


@dataclass(frozen=True)
class GlobalFeatureImportance:
    """How influential a feature is to the model overall (not a causal effect)."""

    feature: str
    display_name: str
    importance: float  # |standardized coefficient| (or tree importance)
    direction: str  # "increases" / "decreases" / "neutral" / "unknown"
    source: str
    description: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class FeatureContribution:
    """A single feature's contribution to ONE prediction (model driver, not cause)."""

    feature: str
    display_name: str
    current_value: float | None
    contribution: float  # coef_i * scaled_value_i (additive toward prediction)
    direction: str  # "increases" / "decreases" / "neutral"
    unit: str
    source: str
    description: str

    def as_dict(self) -> dict:
        return asdict(self)


def _unwrap_pipeline(model: Any) -> tuple[Any, Any, Any]:
    """Return (imputer, scaler, estimator) from a fitted pipeline.

    Any missing step is returned as None. Works for both the ridge pipeline
    (impute+scale+model) and the random-forest pipeline (impute+model).
    """
    steps = getattr(model, "named_steps", None)
    if steps is None:
        # A bare estimator (e.g. the naive baseline) — no preprocessing.
        return None, None, model
    return steps.get("impute"), steps.get("scale"), steps.get("model")


def _is_linear(estimator: Any) -> bool:
    """True if the estimator exposes linear coefficients we can decompose."""
    return hasattr(estimator, "coef_") and hasattr(estimator, "intercept_")


def _scaled_row(
    raw_row: np.ndarray, imputer: Any, scaler: Any
) -> np.ndarray:
    """Apply the same imputation + scaling the model saw at fit time."""
    x = raw_row.reshape(1, -1)
    if imputer is not None:
        x = imputer.transform(x)
    if scaler is not None:
        x = scaler.transform(x)
    return x.ravel()


def global_importance(model: Any, feature_names: list[str]) -> list[GlobalFeatureImportance]:
    """Return per-feature global importance, sorted most→least influential.

    For the selected linear model, importance is the magnitude of the
    standardized coefficient (comparable across features because inputs are
    standardized), and direction is the sign of the coefficient. For a tree
    model we fall back to ``feature_importances_`` (magnitude only; direction is
    reported as "unknown" because tree importances are unsigned).

    These are MODEL CONTRIBUTIONS / prediction drivers, not causal effects.
    """
    _, _, estimator = _unwrap_pipeline(model)

    items: list[GlobalFeatureImportance] = []
    if _is_linear(estimator):
        coefs = np.asarray(estimator.coef_, dtype=float).ravel()
        if len(coefs) != len(feature_names):
            raise ValueError("coefficient count does not match feature_names")
        for name, coef in zip(feature_names, coefs, strict=True):
            meta = get_feature_meta(name)
            items.append(
                GlobalFeatureImportance(
                    feature=name,
                    display_name=meta.display_name,
                    importance=float(abs(coef)),
                    direction=_direction_label(float(coef)),
                    source=meta.source,
                    description=meta.description,
                )
            )
    elif hasattr(estimator, "feature_importances_"):
        importances = np.asarray(estimator.feature_importances_, dtype=float).ravel()
        for name, imp in zip(feature_names, importances, strict=True):
            meta = get_feature_meta(name)
            items.append(
                GlobalFeatureImportance(
                    feature=name,
                    display_name=meta.display_name,
                    importance=float(imp),
                    direction="unknown",  # tree importances are unsigned
                    source=meta.source,
                    description=meta.description,
                )
            )
    else:
        # Baseline / unsupported estimator: no learned importances to report.
        for name in feature_names:
            meta = get_feature_meta(name)
            items.append(
                GlobalFeatureImportance(
                    feature=name,
                    display_name=meta.display_name,
                    importance=0.0,
                    direction="unknown",
                    source=meta.source,
                    description=meta.description,
                )
            )

    items.sort(key=lambda i: i.importance, reverse=True)
    return items


def linear_contributions(
    model: Any,
    raw_row: np.ndarray,
    feature_names: list[str],
    feature_values: dict[str, float | None],
) -> tuple[list[FeatureContribution], float]:
    """Exact additive per-forecast contributions for the linear model.

    Returns (contributions sorted by |contribution| desc, intercept). For each
    feature, contribution = coef_i * scaled_value_i, and
    prediction == intercept + sum(contributions). The reported ``current_value``
    is the ORIGINAL (pre-scaling) feature value so it is human-readable; the
    contribution itself is computed on the scaled value the model actually uses.

    Raises if the model is not linear — callers should branch on model type.
    """
    imputer, scaler, estimator = _unwrap_pipeline(model)
    if not _is_linear(estimator):
        raise ValueError("linear_contributions requires a linear estimator (coef_)")

    coefs = np.asarray(estimator.coef_, dtype=float).ravel()
    scaled = _scaled_row(raw_row, imputer, scaler)
    intercept = float(np.asarray(estimator.intercept_).ravel()[0])

    contributions: list[FeatureContribution] = []
    for idx, name in enumerate(feature_names):
        meta = get_feature_meta(name)
        contrib = float(coefs[idx] * scaled[idx])
        contributions.append(
            FeatureContribution(
                feature=name,
                display_name=meta.display_name,
                current_value=feature_values.get(name),
                contribution=contrib,
                direction=_direction_label(contrib),
                unit=meta.unit,
                source=meta.source,
                description=meta.description,
            )
        )

    contributions.sort(key=lambda c: abs(c.contribution), reverse=True)
    return contributions, intercept


@dataclass(frozen=True)
class ExplanationResult:
    """Structured, causality-safe explanation of a single forecast.

    ``contributions`` are additive MODEL DRIVERS: for the linear model,
    ``base_value + sum(contribution) == prediction`` (up to floating point).
    They describe how each feature moved the model's output relative to the
    model's baseline — an ASSOCIATION learned from history, NOT a causal effect.
    """

    method: str
    prediction: float
    base_value: float  # model intercept (baseline before feature contributions)
    target: str
    model_version: str
    model_type: str
    forecast_period: str | None
    contributions: list[dict]  # FeatureContribution.as_dict(), sorted by |value|
    missing_features: list[str]
    disclaimer: str = (
        "Values are model contributions (prediction drivers) describing "
        "association learned from historical data. They are NOT causal effects: "
        "a contribution does not mean changing the feature would cause "
        "productivity to change."
    )
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)
