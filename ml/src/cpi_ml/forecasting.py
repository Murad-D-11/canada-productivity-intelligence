"""Forecasting models and time-aware backtesting.

Uses scikit-learn / XGBoost. Evaluation uses an expanding-window,
time-ordered split so the model is always validated on periods strictly after
its training data. Reported metrics come only from real backtests; nothing is
hard-coded or fabricated.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error


@dataclass(frozen=True)
class BacktestMetrics:
    """Metrics computed from a genuine out-of-sample backtest."""

    mae: float
    rmse: float
    n_folds: int
    n_eval_points: int


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


def backtest(
    model_factory,
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
        model.fit(x[train_idx], y[train_idx])
        preds = model.predict(x[test_idx])
        all_true.extend(y[test_idx].tolist())
        all_pred.extend(np.asarray(preds).tolist())

    if not all_true:
        raise ValueError("Backtest produced no evaluation points; check inputs")

    mae = float(mean_absolute_error(all_true, all_pred))
    rmse = float(np.sqrt(mean_squared_error(all_true, all_pred)))
    return BacktestMetrics(
        mae=mae, rmse=rmse, n_folds=len(splits), n_eval_points=len(all_true)
    )
