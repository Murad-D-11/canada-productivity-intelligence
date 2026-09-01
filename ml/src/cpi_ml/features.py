"""Feature engineering with strict temporal ordering.

All lag/rolling features are computed using ONLY past information relative to
each row's period. This prevents look-ahead leakage into model training.
"""

from __future__ import annotations

import pandas as pd


def add_lags(
    frame: pd.DataFrame,
    group_cols: list[str],
    value_col: str,
    lags: list[int],
    time_col: str = "ref_period",
) -> pd.DataFrame:
    """Append lagged copies of ``value_col`` within each group.

    Rows are sorted by time within each group so that ``shift`` only pulls
    strictly earlier observations. The original value column is untouched.
    """
    out = frame.sort_values([*group_cols, time_col]).copy()
    grouped = out.groupby(group_cols, group_keys=False)
    for lag in lags:
        out[f"{value_col}_lag{lag}"] = grouped[value_col].shift(lag)
    return out


def add_rolling_mean(
    frame: pd.DataFrame,
    group_cols: list[str],
    value_col: str,
    window: int,
    time_col: str = "ref_period",
) -> pd.DataFrame:
    """Append a trailing rolling mean that excludes the current period.

    The current row is shifted out (``shift(1)``) before the rolling window so
    the feature never incorporates the value it is used to predict.
    """
    out = frame.sort_values([*group_cols, time_col]).copy()
    grouped = out.groupby(group_cols, group_keys=False)
    out[f"{value_col}_rollmean{window}"] = grouped[value_col].transform(
        lambda s: s.shift(1).rolling(window, min_periods=1).mean()
    )
    return out
