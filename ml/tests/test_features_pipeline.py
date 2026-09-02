"""Critical tests for the feature-engineering pipeline.

Focuses on the property that matters most for ML correctness: no look-ahead
leakage. Lag, rolling-mean, and growth features must use only information
available strictly before the current period. Also checks the null-coercion
helpers so NaN never reaches the database as a fabricated value.
"""

from __future__ import annotations

import math

import pandas as pd

from cpi_ml.features import add_lags, add_rolling_mean
from cpi_ml.features_pipeline import FEATURE_COLUMNS, _int, _num


def _series() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "industry": ["A"] * 5,
            "geography": ["Canada"] * 5,
            "period_start": pd.to_datetime(
                ["2019-01-01", "2020-01-01", "2021-01-01", "2022-01-01", "2023-01-01"]
            ),
            "targetValue": [100.0, 110.0, 120.0, 130.0, 140.0],
        }
    )


def test_lag_uses_only_prior_period() -> None:
    out = add_lags(_series(), ["industry", "geography"], "targetValue", [1], "period_start")
    out = out.sort_values("period_start").reset_index(drop=True)
    # First row has no prior value; subsequent lag1 equals the previous target.
    assert math.isnan(out["targetValue_lag1"].iloc[0])
    assert out["targetValue_lag1"].iloc[1] == 100.0
    assert out["targetValue_lag1"].iloc[2] == 110.0


def test_rolling_mean_excludes_current_period() -> None:
    out = add_rolling_mean(_series(), ["industry", "geography"], "targetValue", 2, "period_start")
    out = out.sort_values("period_start").reset_index(drop=True)
    # Row 2 (2021) trailing mean over the two prior periods (100, 110) = 105,
    # and crucially never includes the current period's own value (120).
    assert out["targetValue_rollmean2"].iloc[2] == 105.0
    assert math.isnan(out["targetValue_rollmean2"].iloc[0])


def test_null_coercion_never_emits_nan() -> None:
    assert _num(None) is None
    assert _num(float("nan")) is None
    assert _num("12.5") == 12.5
    assert _int(3.9) == 3
    assert _int(None) is None


def test_feature_columns_are_stable() -> None:
    # Guards the persisted feature contract from silent drift.
    assert FEATURE_COLUMNS == [
        "prodLag1",
        "prodLag4",
        "prodRollMean4",
        "employmentGrowth",
        "labourCostGrowth",
        "quarter",
        "month",
        "weatherTempMean",
        "weatherPrecipSum",
        "weatherSnowfallSum",
        "weatherWindMean",
    ]
