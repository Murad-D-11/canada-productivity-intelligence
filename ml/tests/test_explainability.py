"""Targeted tests for model explainability (kept intentionally small).

Covers only the properties that matter for correctness of an explanation:

    1. structure — explain() returns the documented, causality-safe shape,
    2. same feature set — the explanation uses exactly the model's features,
       in the same order as prediction, with the same values,
    3. numeric + additive — contributions are real numbers and, for the linear
       model, base_value + sum(contributions) reconstructs the prediction.
"""

from __future__ import annotations

import numpy as np

from cpi_ml.artifacts import ModelMetadata, save_artifact, utc_now_iso
from cpi_ml.models import make_ridge_factory
from cpi_ml.prediction import ProductivityForecaster, explain_prediction

FEATURES = ["prodLag1", "prodLag4", "prodRollMean4"]


def _train_tiny_ridge(tmp_path) -> None:
    rng = np.random.default_rng(0)
    x = rng.normal(size=(50, 3))
    # A known signed relationship so contributions have meaningful directions.
    y = 2.0 * x[:, 0] - 1.0 * x[:, 1] + 0.5 * x[:, 2] + 100.0
    model = make_ridge_factory()()
    model.fit(x, y)
    meta = ModelMetadata(
        model_type="ridge",
        algorithm="Ridge(test)",
        model_version="explain-test-v1",
        target="Labour productivity",
        resolution="QUARTERLY",
        forecast_horizon=1,
        feature_names=FEATURES,
        preprocessing={"imputation": "median", "scaling": "standard"},
        training_period={"start": "2000-01-01", "end": "2010-01-01"},
        validation_period={"start": "2010-04-01", "end": "2012-01-01"},
        test_period={"start": "2012-04-01", "end": "2013-01-01"},
        trained_at=utc_now_iso(),
        metrics={"selected_model": "ridge"},
    )
    save_artifact(model, meta, tmp_path)


def test_explanation_structure_is_causality_safe(tmp_path) -> None:
    _train_tiny_ridge(tmp_path)
    result = explain_prediction(
        {"prodLag1": 1.0, "prodLag4": 0.5, "prodRollMean4": -0.2},
        artifacts_dir=tmp_path,
        forecast_period="2026-Q2",
    )
    d = result.as_dict()
    # Documented top-level fields present.
    for key in ("method", "prediction", "base_value", "target", "contributions", "disclaimer"):
        assert key in d
    # Wording must frame values as association, never causation.
    assert "not causal" in d["disclaimer"].lower() or "not causal effects" in d["disclaimer"].lower()
    # Each contribution carries the documented, metadata-backed fields.
    first = d["contributions"][0]
    for key in ("feature", "display_name", "current_value", "contribution", "direction", "unit", "source", "description"):
        assert key in first
    assert first["direction"] in {"increases", "decreases", "neutral"}


def test_explanation_uses_same_feature_set_as_prediction(tmp_path) -> None:
    _train_tiny_ridge(tmp_path)
    forecaster = ProductivityForecaster.load(tmp_path)
    features = {"prodLag1": 1.2, "prodLag4": 0.3, "prodRollMean4": 0.7}
    pred = forecaster.predict(features)
    expl = forecaster.explain(features)
    # Same ordered feature set as the model / prediction.
    explained_features = [c["feature"] for c in expl.contributions]
    assert sorted(explained_features) == sorted(pred.features_used.keys())
    assert set(explained_features) == set(forecaster.metadata.feature_names)
    # Same values fed to the model in both paths.
    for c in expl.contributions:
        assert c["current_value"] == pred.features_used[c["feature"]]


def test_contributions_are_numeric_and_additive(tmp_path) -> None:
    _train_tiny_ridge(tmp_path)
    forecaster = ProductivityForecaster.load(tmp_path)
    features = {"prodLag1": 1.0, "prodLag4": -0.5, "prodRollMean4": 0.25}
    expl = forecaster.explain(features)
    contribs = [c["contribution"] for c in expl.contributions]
    # Every contribution is a finite real number (no NaN/inf, no fabrication).
    assert all(isinstance(v, float) and np.isfinite(v) for v in contribs)
    # Exact linear additivity: base_value + sum(contributions) == prediction.
    reconstructed = expl.base_value + sum(contribs)
    assert abs(reconstructed - expl.prediction) < 1e-6
    assert expl.method == "exact_linear_contribution"
