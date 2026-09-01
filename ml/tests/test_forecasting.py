"""Tests for time-aware backtesting and explainability aggregation."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from cpi_ml.explainability import mean_absolute_attributions
from cpi_ml.forecasting import backtest, expanding_window_splits


def test_expanding_window_never_leaks_future() -> None:
    splits = expanding_window_splits(n_samples=20, n_folds=4, min_train=8)
    assert len(splits) >= 1
    for train_idx, test_idx in splits:
        # Every training index must come strictly before every test index.
        assert train_idx.max() < test_idx.min()


def test_backtest_reports_real_metrics() -> None:
    n = 40
    x = pd.DataFrame({"f1": np.arange(n, dtype=float)})
    y = pd.Series(np.arange(n, dtype=float) * 2.0 + 1.0)
    metrics = backtest(lambda: LinearRegression(), x, y, n_folds=3, min_train=10)
    assert metrics.n_eval_points > 0
    # Perfect linear relationship -> near-zero error.
    assert metrics.mae < 1e-6


def test_attributions_sorted_descending() -> None:
    shap = np.array([[1.0, -3.0], [2.0, 3.0]])
    attrs = mean_absolute_attributions(shap, ["f1", "f2"])
    assert attrs[0].feature == "f2"
    assert attrs[0].mean_abs_contribution >= attrs[1].mean_abs_contribution
