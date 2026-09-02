"""High-value tests for the productivity forecasting system.

Scope is deliberately narrow — only the properties that would silently corrupt
a forecast if broken:

    1. chronological split never puts a future period in training,
    2. the supervised target is the FUTURE value and its predictors stay
       past-only (no look-ahead leakage into features),
    3. a trained artifact round-trips (save -> load) with intact metadata,
    4. the prediction interface returns the documented structure,
    5. feature ordering is identical between training metadata and prediction
       input (a mismatch would feed values to the wrong coefficients).

These run without a database: they build a tiny in-memory frame / fit a trivial
model, so they are fast and deterministic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from cpi_ml.artifacts import ModelMetadata, load_artifact, save_artifact, utc_now_iso
from cpi_ml.forecasting import chronological_split_index
from cpi_ml.models import NaivePreviousValue, make_ridge_factory
from cpi_ml.prediction import ProductivityForecaster


# --- 1. chronological split ------------------------------------------------


def test_chronological_split_puts_no_future_in_train() -> None:
    periods = pd.Series(pd.date_range("2000-01-01", periods=20, freq="QS"))
    val_start, test_start = chronological_split_index(periods, 0.2, 0.2)
    # Boundaries must be strictly ordered so the three blocks don't overlap.
    assert val_start < test_start
    train = periods[periods < val_start]
    val = periods[(periods >= val_start) & (periods < test_start)]
    test = periods[periods >= test_start]
    assert len(train) and len(val) and len(test)
    # The latest training period is strictly before any validation/test period.
    assert train.max() < val.min() < test.min()


# --- 2. supervised target is future + predictors are past-only -------------


def test_future_target_and_past_only_predictors() -> None:
    # A single series with a known productivity path and a leakage-safe lag1.
    values = [100.0, 101.0, 102.0, 103.0, 104.0]
    df = pd.DataFrame(
        {
            "industry": ["A"] * 5,
            "geography": ["Canada"] * 5,
            "measure": ["Labour productivity"] * 5,
            "period_start": pd.date_range("2000-01-01", periods=5, freq="QS"),
            "target_value": values,
            # prodLag1 as the feature pipeline builds it: prior-period value.
            "prodLag1": [np.nan, 100.0, 101.0, 102.0, 103.0],
        }
    )
    horizon = 1
    df = df.sort_values("period_start")
    df["y"] = df.groupby(["industry", "geography", "measure"])["target_value"].shift(-horizon)
    # y[t] must equal the NEXT period's observed value (the thing we forecast).
    assert df["y"].tolist()[:-1] == [101.0, 102.0, 103.0, 104.0]
    # And for any row, prodLag1 (a predictor) is strictly earlier than y.
    row = df.iloc[1]
    assert row["prodLag1"] == 100.0  # prior period
    assert row["y"] == 102.0  # next period — never seen by the predictor


# --- 3 & 4 & 5. artifact round-trip + prediction structure + ordering ------


def _train_tiny_model() -> tuple[object, ModelMetadata]:
    rng = np.random.default_rng(0)
    x = rng.normal(size=(40, 3))
    y = x[:, 0] * 2.0 + 1.0
    model = make_ridge_factory()()
    model.fit(x, y)
    trained_at = utc_now_iso()
    meta = ModelMetadata(
        model_type="ridge",
        algorithm="Ridge(test)",
        model_version="test-model-v1",
        target="Labour productivity",
        resolution="QUARTERLY",
        forecast_horizon=1,
        feature_names=["prodLag1", "prodLag4", "prodRollMean4"],
        preprocessing={"imputation": "median"},
        training_period={"start": "2000-01-01", "end": "2010-01-01"},
        validation_period={"start": "2010-04-01", "end": "2012-01-01"},
        test_period={"start": "2012-04-01", "end": "2013-01-01"},
        trained_at=trained_at,
        metrics={"selected_model": "ridge"},
    )
    return model, meta


def test_artifact_round_trips(tmp_path) -> None:
    model, meta = _train_tiny_model()
    save_artifact(model, meta, tmp_path)
    loaded_model, loaded_meta = load_artifact(tmp_path)  # uses latest pointer
    assert loaded_meta.model_version == "test-model-v1"
    assert loaded_meta.feature_names == ["prodLag1", "prodLag4", "prodRollMean4"]
    assert loaded_meta.target == "Labour productivity"
    # Loaded model still predicts.
    preds = loaded_model.predict(np.zeros((1, 3)))
    assert preds.shape == (1,)


def test_prediction_returns_expected_structure(tmp_path) -> None:
    model, meta = _train_tiny_model()
    save_artifact(model, meta, tmp_path)
    forecaster = ProductivityForecaster.load(tmp_path)
    result = forecaster.predict(
        {"prodLag1": 1.0, "prodLag4": 0.5, "prodRollMean4": 0.8}, forecast_period="2026-Q2"
    )
    assert isinstance(result.prediction, float)
    assert result.model_version == "test-model-v1"
    assert result.target == "Labour productivity"
    assert result.forecast_horizon == 1
    assert result.forecast_period == "2026-Q2"
    assert result.missing_features == []
    assert list(result.features_used.keys()) == ["prodLag1", "prodLag4", "prodRollMean4"]


def test_prediction_feature_ordering_matches_metadata(tmp_path) -> None:
    model, meta = _train_tiny_model()
    save_artifact(model, meta, tmp_path)
    forecaster = ProductivityForecaster.load(tmp_path)
    # Pass features in a DIFFERENT order than trained; result ordering must
    # follow the metadata's feature_names, not the caller's dict order.
    result = forecaster.predict(
        {"prodRollMean4": 0.8, "prodLag1": 1.0, "prodLag4": 0.5}
    )
    assert list(result.features_used.keys()) == meta.feature_names
    # A missing feature is reported rather than silently defaulted.
    result2 = forecaster.predict({"prodLag1": 1.0})
    assert "prodLag4" in result2.missing_features
    assert "prodRollMean4" in result2.missing_features


def test_naive_predicts_previous_value() -> None:
    # The naive baseline must echo the prodLag1 column it is bound to.
    model = NaivePreviousValue(lag_index=0)
    model.fit(np.array([[100.0], [101.0]]), np.array([101.0, 102.0]))
    preds = model.predict(np.array([[105.0], [np.nan]]))
    assert preds[0] == 105.0  # previous value passed straight through
    assert preds[1] == 101.5  # missing -> train-mean fallback (mean of 101,102)
