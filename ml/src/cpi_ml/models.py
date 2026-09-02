"""Model definitions for productivity forecasting.

A small, deliberate set of models (not a research ensemble):

    1. naive      — previous-period baseline. Predicts the most recent known
                    productivity value (the ``prodLag1`` feature). This answers
                    the essential question: does any learned model beat "assume
                    next quarter looks like this quarter"?
    2. ridge      — regularized linear regression with standardization and
                    median imputation, wrapped in a Pipeline so scaling and
                    imputation are fit ONLY on the training fold (no leakage).
    3. random_forest — tree-based regression. Handles non-linearity and needs no
                    scaling; median imputation keeps it robust to occasional
                    missing predictors.

All estimators expose the scikit-learn ``fit`` / ``predict`` API so they can be
used interchangeably by the evaluation and training code. Model factories are
zero-arg callables returning a fresh, unfitted estimator (required by the
expanding-window backtester).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


class NaivePreviousValue:
    """Previous-period baseline predictor.

    Predicts y[t+h] as the most recent known productivity level. It reads the
    ``prodLag1`` column (the value from the prior period) directly from the
    feature matrix, so it uses only information available at the cutoff.

    Implements the sklearn fit/predict API (fit is a no-op) so it slots into the
    same evaluation harness as the learned models.
    """

    def __init__(self, lag_index: int = 0) -> None:
        # Index of the prodLag1 column within the feature matrix passed to
        # fit/predict. Training code sets this to match feature ordering.
        self.lag_index = lag_index
        self._fallback: float = 0.0

    def fit(self, x: np.ndarray, y: np.ndarray) -> NaivePreviousValue:
        # Fallback used only when the lag feature itself is missing (NaN).
        y = np.asarray(y, dtype=float)
        self._fallback = float(np.nanmean(y)) if y.size else 0.0
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=float)
        preds = x[:, self.lag_index].copy()
        # If the previous-period value is missing, fall back to the train mean.
        missing = np.isnan(preds)
        preds[missing] = self._fallback
        return preds


def make_naive_factory(lag_index: int) -> Callable[[], NaivePreviousValue]:
    """Return a zero-arg factory building a naive predictor bound to a column."""
    return lambda: NaivePreviousValue(lag_index=lag_index)


def make_ridge_factory(alpha: float = 1.0, random_state: int = 42) -> Callable[[], Pipeline]:
    """Regularized linear model with imputation + scaling (leakage-safe pipeline)."""

    def factory() -> Pipeline:
        return Pipeline(
            steps=[
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
                ("model", Ridge(alpha=alpha, random_state=random_state)),
            ]
        )

    return factory


def make_random_forest_factory(
    n_estimators: int = 300, max_depth: int | None = None, random_state: int = 42
) -> Callable[[], Pipeline]:
    """Tree-based regression with median imputation (no scaling needed)."""

    def factory() -> Pipeline:
        return Pipeline(
            steps=[
                ("impute", SimpleImputer(strategy="median")),
                (
                    "model",
                    RandomForestRegressor(
                        n_estimators=n_estimators,
                        max_depth=max_depth,
                        random_state=random_state,
                        n_jobs=-1,
                    ),
                ),
            ]
        )

    return factory


# Human-readable algorithm labels recorded in model metadata.
ALGORITHM_LABELS = {
    "naive": "NaivePreviousValue",
    "ridge": "Ridge(+StandardScaler,+MedianImpute)",
    "random_forest": "RandomForestRegressor(+MedianImpute)",
}
