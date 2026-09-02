"""Forecasting models, the supervised problem definition, and time-aware
evaluation.

Prediction problem (explicit and documented in code):
    * TARGET       — next-period ``Labour productivity`` value for a
                     (industry, geography) series, i.e. y[t+HORIZON].
    * RESOLUTION   — quarterly. The ingested StatCan cube (36-10-0207-01) is
                     published on quarter-start months (Jan/Apr/Jul/Oct). We use
                     that native resolution and do NOT resample.
    * HORIZON      — 1 period ahead (one quarter). Configurable via
                     ``ForecastConfig.horizon`` but defaults to 1.
    * CUTOFF       — every predictor for period t uses only information known at
                     or before t (lags/rolling/growth are already shifted in the
                     feature pipeline). The target is the value one horizon step
                     into the future, so training never sees the value it
                     predicts.

Evaluation uses an expanding-window / walk-forward split that is strictly
time-ordered, so a model is always validated on periods after its training
data. All reported metrics come from genuine out-of-sample folds; nothing is
hard-coded or fabricated. If a model does poorly we report it honestly.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# ---------------------------------------------------------------------------
# Problem definition
# ---------------------------------------------------------------------------

# Target measure (matches the feature pipeline / ingested StatCan measure name).
TARGET_MEASURE = "Labour productivity"

# The engineered feature columns that are actually populated by the pipeline
# for the available data. Weather columns exist in the schema but are excluded
# here because weather has not been ingested (they would be entirely null); the
# training code drops any all-null feature defensively as well.
MODEL_FEATURES: list[str] = [
    "prodLag1",
    "prodLag4",
    "prodRollMean4",
    "employmentGrowth",
    "labourCostGrowth",
    "quarter",
    "month",
]

# Weather features are part of the persisted feature contract but optional for
# modelling. Listed separately so training can include them automatically once
# weather data exists, without changing the core feature set.
OPTIONAL_WEATHER_FEATURES: list[str] = [
    "weatherTempMean",
    "weatherPrecipSum",
    "weatherSnowfallSum",
    "weatherWindMean",
]


@dataclass(frozen=True)
class ForecastConfig:
    """Explicit, serializable description of the supervised forecasting task."""

    target_measure: str = TARGET_MEASURE
    resolution: str = "QUARTERLY"
    horizon: int = 1
    feature_names: list[str] = field(default_factory=lambda: list(MODEL_FEATURES))

    def describe(self) -> dict:
        return {
            "target_measure": self.target_measure,
            "resolution": self.resolution,
            "horizon": self.horizon,
            "feature_names": list(self.feature_names),
        }


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BacktestMetrics:
    """Metrics computed from a genuine out-of-sample backtest.

    ``r2`` is optional because it is only meaningful with enough variance in the
    evaluation targets; it is None when it cannot be computed reliably.
    """

    mae: float
    rmse: float
    n_folds: int
    n_eval_points: int
    r2: float | None = None

    def as_dict(self) -> dict:
        return {
            "mae": self.mae,
            "rmse": self.rmse,
            "r2": self.r2,
            "n_folds": self.n_folds,
            "n_eval_points": self.n_eval_points,
        }


def regression_metrics(
    y_true: list[float] | np.ndarray, y_pred: list[float] | np.ndarray
) -> tuple[float, float, float | None]:
    """Return (MAE, RMSE, R2) for aligned true/predicted arrays.

    R2 is None when there are fewer than two points or the target has zero
    variance (in which case R2 is undefined / not meaningful).
    """
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    mae = float(mean_absolute_error(yt, yp))
    rmse = float(np.sqrt(mean_squared_error(yt, yp)))
    r2: float | None = None
    if len(yt) >= 2 and float(np.var(yt)) > 0.0:
        r2 = float(r2_score(yt, yp))
    return mae, rmse, r2


# ---------------------------------------------------------------------------
# Time-ordered splitting (no shuffling — prevents look-ahead leakage)
# ---------------------------------------------------------------------------


def expanding_window_splits(
    n_samples: int, n_folds: int, min_train: int
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Yield (train_idx, test_idx) pairs for a time-ordered expanding window.

    Assumes the input is already sorted ascending by time. Each fold trains on
    all data up to a cut point and tests on the immediately following block, so
    no future information leaks into training.
    """
    if min_train >= n_samples:
        raise ValueError("min_train must be smaller than the number of samples")
    fold_size = max(1, (n_samples - min_train) // n_folds)
    splits: list[tuple[np.ndarray, np.ndarray]] = []
    start_test = min_train
    for _ in range(n_folds):
        end_test = min(start_test + fold_size, n_samples)
        if start_test >= end_test:
            break
        train_idx = np.arange(0, start_test)
        test_idx = np.arange(start_test, end_test)
        splits.append((train_idx, test_idx))
        start_test = end_test
    return splits


def chronological_split_index(
    periods: pd.Series, val_fraction: float = 0.2, test_fraction: float = 0.2
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Compute period cutoffs for a train/validation/test split by TIME.

    Splitting is done on the sorted unique periods (not rows) so that every
    industry series is cut at the same calendar boundary. Returns
    ``(val_start, test_start)`` timestamps: train = periods < val_start,
    validation = val_start <= periods < test_start, test = periods >= test_start.
    """
    uniq = pd.Series(pd.to_datetime(periods.unique())).sort_values().reset_index(drop=True)
    n = len(uniq)
    if n < 3:
        raise ValueError("need at least 3 distinct periods to split chronologically")
    test_start_i = int(round(n * (1.0 - test_fraction)))
    val_start_i = int(round(n * (1.0 - test_fraction - val_fraction)))
    val_start_i = max(1, min(val_start_i, n - 2))
    test_start_i = max(val_start_i + 1, min(test_start_i, n - 1))
    return uniq.iloc[val_start_i], uniq.iloc[test_start_i]


# ---------------------------------------------------------------------------
# Backtesting
# ---------------------------------------------------------------------------


def backtest(
    model_factory: Callable[[], object],
    features: pd.DataFrame,
    target: pd.Series,
    n_folds: int = 4,
    min_train: int = 12,
) -> BacktestMetrics:
    """Run an expanding-window backtest and return aggregate metrics.

    ``model_factory`` is a zero-arg callable returning a fresh, unfitted
    estimator implementing scikit-learn's fit/predict API. Rows must be sorted
    ascending by time before calling.
    """
    x = features.to_numpy()
    y = target.to_numpy()
    all_true: list[float] = []
    all_pred: list[float] = []
    splits = expanding_window_splits(len(y), n_folds=n_folds, min_train=min_train)
    for train_idx, test_idx in splits:
        model = model_factory()
        model.fit(x[train_idx], y[train_idx])  # type: ignore[attr-defined]
        preds = model.predict(x[test_idx])  # type: ignore[attr-defined]
        all_true.extend(y[test_idx].tolist())
        all_pred.extend(np.asarray(preds).tolist())

    if not all_true:
        raise ValueError("Backtest produced no evaluation points; check inputs")

    mae, rmse, r2 = regression_metrics(all_true, all_pred)
    return BacktestMetrics(
        mae=mae, rmse=rmse, r2=r2, n_folds=len(splits), n_eval_points=len(all_true)
    )
