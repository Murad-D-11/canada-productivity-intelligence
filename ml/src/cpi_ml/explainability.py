"""SHAP-based explainability.

Produces feature-attribution summaries for tree models. Attributions describe
statistical ASSOCIATION between features and predictions, not causation. This
distinction is enforced in naming and documentation and must be preserved in
any UI that surfaces these values.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


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
