"""Tests for temporal feature engineering (no look-ahead leakage)."""

from __future__ import annotations

import pandas as pd

from cpi_ml.features import add_lags, add_rolling_mean


def _sample() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "series": ["a", "a", "a", "a"],
            "ref_period": pd.to_datetime(["2020-01-01", "2020-04-01", "2020-07-01", "2020-10-01"]),
            "value": [10.0, 20.0, 30.0, 40.0],
        }
    )


def test_add_lags_uses_only_past_values() -> None:
    out = add_lags(_sample(), group_cols=["series"], value_col="value", lags=[1])
    # First row has no prior period, so lag must be null.
    assert pd.isna(out.iloc[0]["value_lag1"])
    # Each subsequent lag equals the immediately preceding value.
    assert out.iloc[1]["value_lag1"] == 10.0
    assert out.iloc[3]["value_lag1"] == 30.0


def test_rolling_mean_excludes_current_period() -> None:
    out = add_rolling_mean(_sample(), group_cols=["series"], value_col="value", window=2)
    # Current period is shifted out, so the first row has no trailing window.
    assert pd.isna(out.iloc[0]["value_rollmean2"])
    # Row index 2 (value 30) sees trailing window of [10, 20] -> mean 15.
    assert out.iloc[2]["value_rollmean2"] == 15.0
