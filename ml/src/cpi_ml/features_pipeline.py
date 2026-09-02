"""Reproducible feature-engineering pipeline (Master Prompt 3).

Reads ingested StatCan productivity observations and MSC GeoMet weather
observations from PostgreSQL, assembles a leakage-safe, ML-ready feature matrix,
and persists it to the ``FeatureSet`` / ``FeatureRow`` tables.

Features produced per (industry, geography, measure, period):
    * targetValue        — the observed productivity value for the period
    * prodLag1, prodLag4 — lagged productivity (strictly past)
    * prodRollMean4      — trailing rolling mean, excludes current period
    * employmentGrowth   — period-over-period growth of "Total number of jobs"
    * labourCostGrowth   — growth of "Total compensation per hour worked"
    * quarter, month     — seasonal indicators derived from the period
    * weatherTempMean / weatherPrecipSum / weatherSnowfallSum / weatherWindMean
                         — weather aggregates matched to the same period

All lag/rolling/growth features use ONLY information available up to (and not
including) the current period — computed with ``shift(1)`` — so training never
sees the value it predicts. Missing inputs propagate as null (never imputed).

Determinism: the pipeline sorts inputs deterministically and derives features
purely from stored observations, so repeated runs over the same data produce
identical output (reproducible).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import Engine, create_engine, text

from cpi_ml.data.repository import _normalize_db_url, make_id
from cpi_ml.data.schemas import PeriodType
from cpi_ml.features import add_lags, add_rolling_mean

logger = logging.getLogger("cpi_ml.features_pipeline")

# StatCan measure names used to derive growth features. These are matched
# case-insensitively against ingested measure names (discovered, not hardcoded
# member ids). If a measure is absent, its derived feature stays null.
MEASURE_LABOUR_PRODUCTIVITY = "labour productivity"
MEASURE_EMPLOYMENT = "total number of jobs"
MEASURE_LABOUR_COST = "total compensation per hour worked"

# Ordered feature column names persisted for reproducibility metadata.
FEATURE_COLUMNS = [
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

# How many periods per year, for lag semantics, by period type.
_LAGS_BY_PERIOD = {
    PeriodType.ANNUAL: {"lag1": 1, "lag4": 2, "roll": 3},
    PeriodType.QUARTERLY: {"lag1": 1, "lag4": 4, "roll": 4},
    PeriodType.MONTHLY: {"lag1": 1, "lag4": 12, "roll": 12},
}


@dataclass
class FeatureMetrics:
    rows: int = 0
    industries: int = 0
    measures: int = 0
    with_weather: int = 0
    earliest: str | None = None
    latest: str | None = None
    duration_seconds: float | None = None
    feature_set_id: str | None = None
    warnings: list[str] = field(default_factory=list)


class FeaturePipeline:
    """Builds and persists the productivity + weather feature matrix."""

    def __init__(self, database_url: str, engine: Engine | None = None) -> None:
        self._engine = engine or create_engine(_normalize_db_url(database_url), future=True)

    # -- data access --------------------------------------------------------
    def _load_productivity(self) -> pd.DataFrame:
        """Load productivity observations as a tidy frame (real data only)."""
        sql = text(
            'SELECT o."periodStart" AS period_start, o."periodLabel" AS period_label, '
            'o."periodType" AS period_type, o.value AS value, '
            'i.name AS industry, m.name AS measure, g.name AS geography '
            'FROM "StatCanObservation" o '
            'JOIN "StatCanIndustry" i ON i.id = o."industryId" '
            'JOIN "StatCanMeasure" m ON m.id = o."measureId" '
            'JOIN "StatCanGeography" g ON g.id = o."geographyId" '
        )
        with self._engine.connect() as conn:
            df = pd.read_sql(sql, conn)
        return df

    def _load_weather(self) -> pd.DataFrame:
        """Load weather observations pivoted to one row per (province, period)."""
        sql = text(
            'SELECT "periodStart" AS period_start, province, variable, '
            'AVG(value) AS value FROM "WeatherObservation" '
            'GROUP BY "periodStart", province, variable'
        )
        with self._engine.connect() as conn:
            df = pd.read_sql(sql, conn)
        if df.empty:
            return df
        # Pivot variables into columns; province-level then averaged to national.
        pivot = df.pivot_table(
            index="period_start", columns="variable", values="value", aggfunc="mean"
        ).reset_index()
        return pivot

    # -- feature construction ----------------------------------------------
    def build(self, *, name: str = "productivity+weather@v1") -> tuple[pd.DataFrame, PeriodType]:
        """Assemble the feature matrix in memory (no DB writes). Returns the
        frame and the dominant period type used for lag semantics."""
        prod = self._load_productivity()
        if prod.empty:
            raise ValueError("no productivity observations found; ingest StatCan first")

        # Dominant period type drives lag windows.
        period_type = PeriodType(prod["period_type"].mode().iloc[0])
        lags = _LAGS_BY_PERIOD[period_type]

        # Target series: labour productivity per (industry, geography).
        target = prod[prod["measure"].str.lower() == MEASURE_LABOUR_PRODUCTIVITY].copy()
        if target.empty:
            # Fall back to the first measure so the pipeline still produces rows.
            first_measure = prod["measure"].iloc[0]
            target = prod[prod["measure"] == first_measure].copy()
            logger.warning(
                "measure %r not found; using %r as target",
                MEASURE_LABOUR_PRODUCTIVITY, first_measure,
            )

        target = target.rename(columns={"value": "targetValue"})
        target = target.sort_values(["industry", "geography", "period_start"])

        group_cols = ["industry", "geography"]
        # Lagged productivity + rolling mean (leakage-safe via shift in helpers).
        target = add_lags(target, group_cols, "targetValue",
                          [lags["lag1"], lags["lag4"]], time_col="period_start")
        target = add_rolling_mean(target, group_cols, "targetValue",
                                 lags["roll"], time_col="period_start")
        target = target.rename(columns={
            f"targetValue_lag{lags['lag1']}": "prodLag1",
            f"targetValue_lag{lags['lag4']}": "prodLag4",
            f"targetValue_rollmean{lags['roll']}": "prodRollMean4",
        })

        # Growth features from other measures, joined by (industry, geo, period).
        target = self._add_growth(target, prod, MEASURE_EMPLOYMENT,
                                  "employmentGrowth", group_cols)
        target = self._add_growth(target, prod, MEASURE_LABOUR_COST,
                                  "labourCostGrowth", group_cols)

        # Seasonal indicators.
        target["quarter"] = ((pd.to_datetime(target["period_start"]).dt.month - 1) // 3 + 1)
        target["month"] = pd.to_datetime(target["period_start"]).dt.month

        # Weather aggregates matched by period (national alignment).
        target = self._add_weather(target)

        return target, period_type

    def _add_growth(
        self,
        target: pd.DataFrame,
        prod: pd.DataFrame,
        measure_name: str,
        out_col: str,
        group_cols: list[str],
    ) -> pd.DataFrame:
        """Add a leakage-safe period-over-period growth feature from a measure."""
        src = prod[prod["measure"].str.lower() == measure_name][
            ["industry", "geography", "period_start", "value"]
        ].copy()
        if src.empty:
            target[out_col] = pd.NA
            return target
        src = src.sort_values([*group_cols, "period_start"])
        grouped = src.groupby(group_cols, group_keys=False)
        # Growth relative to the previous period; uses only past+current source,
        # then shifted by one row so the current target period sees prior growth.
        src["_prev"] = grouped["value"].shift(1)
        src[out_col] = (src["value"] - src["_prev"]) / src["_prev"]
        src[out_col] = grouped[out_col].shift(1)
        merged = target.merge(
            src[["industry", "geography", "period_start", out_col]],
            on=["industry", "geography", "period_start"],
            how="left",
        )
        return merged

    def _add_weather(self, target: pd.DataFrame) -> pd.DataFrame:
        """Attach national weather aggregates matched by period start."""
        weather = self._load_weather()
        mapping = {
            "TEMPERATURE": "weatherTempMean",
            "PRECIPITATION": "weatherPrecipSum",
            "SNOWFALL": "weatherSnowfallSum",
            "WIND_SPEED": "weatherWindMean",
        }
        for col in mapping.values():
            if col not in target:
                target[col] = pd.NA

        if weather.empty:
            return target

        rename = {src: dst for src, dst in mapping.items() if src in weather.columns}
        weather = weather.rename(columns=rename)
        keep = ["period_start", *rename.values()]
        weather = weather[keep]
        merged = target.drop(columns=[c for c in mapping.values() if c in target]).merge(
            weather, on="period_start", how="left"
        )
        return merged

    # -- persistence --------------------------------------------------------
    def persist(self, frame: pd.DataFrame, period_type: PeriodType, *, name: str) -> FeatureMetrics:
        """Write the feature matrix to FeatureSet + FeatureRow transactionally."""
        metrics = FeatureMetrics()
        metrics.rows = len(frame)
        metrics.industries = int(frame["industry"].nunique())
        metrics.measures = int(frame["measure"].nunique()) if "measure" in frame else 1
        metrics.with_weather = int(frame["weatherTempMean"].notna().sum())
        if not frame.empty:
            metrics.earliest = str(pd.to_datetime(frame["period_start"]).min().date())
            metrics.latest = str(pd.to_datetime(frame["period_start"]).max().date())

        cutoff = pd.to_datetime(frame["period_start"]).max().to_pydatetime()
        feature_set_id = make_id()

        with self._engine.begin() as conn:
            conn.execute(
                text(
                    'INSERT INTO "FeatureSet" '
                    '(id, name, "periodCutoff", "periodType", "featureListJson", "rowCount", "createdAt") '
                    'VALUES (:id, :n, :cut, CAST(:pt AS "PeriodType"), CAST(:fl AS jsonb), :rc, :now)'
                ),
                {"id": feature_set_id, "n": name, "cut": cutoff, "pt": period_type.value,
                 "fl": json.dumps(FEATURE_COLUMNS), "rc": len(frame), "now": datetime.utcnow()},
            )
            for _, row in frame.iterrows():
                conn.execute(
                    text(
                        'INSERT INTO "FeatureRow" '
                        '(id, "featureSetId", industry, geography, measure, "periodStart", '
                        '"periodLabel", "periodType", "targetValue", "prodLag1", "prodLag4", '
                        '"prodRollMean4", "employmentGrowth", "labourCostGrowth", quarter, month, '
                        '"weatherTempMean", "weatherPrecipSum", "weatherSnowfallSum", '
                        '"weatherWindMean", "createdAt") '
                        'VALUES (:id, :fsid, :ind, :geo, :meas, :ps, :pl, '
                        'CAST(:pt AS "PeriodType"), :tv, :l1, :l4, :rm, :eg, :lcg, :q, :mo, '
                        ':wt, :wp, :ws, :ww, :now) '
                        'ON CONFLICT ("featureSetId", industry, geography, measure, "periodStart") '
                        'DO NOTHING'
                    ),
                    {
                        "id": make_id(), "fsid": feature_set_id,
                        "ind": row["industry"], "geo": row["geography"],
                        "meas": row.get("measure", "Labour productivity"),
                        "ps": pd.to_datetime(row["period_start"]).to_pydatetime(),
                        "pl": row["period_label"], "pt": period_type.value,
                        "tv": _num(row.get("targetValue")),
                        "l1": _num(row.get("prodLag1")), "l4": _num(row.get("prodLag4")),
                        "rm": _num(row.get("prodRollMean4")),
                        "eg": _num(row.get("employmentGrowth")),
                        "lcg": _num(row.get("labourCostGrowth")),
                        "q": _int(row.get("quarter")), "mo": _int(row.get("month")),
                        "wt": _num(row.get("weatherTempMean")),
                        "wp": _num(row.get("weatherPrecipSum")),
                        "ws": _num(row.get("weatherSnowfallSum")),
                        "ww": _num(row.get("weatherWindMean")),
                        "now": datetime.utcnow(),
                    },
                )

        metrics.feature_set_id = feature_set_id
        logger.info("persisted feature set %s with %d rows", feature_set_id, len(frame))
        return metrics

    def run(self, *, name: str = "productivity+weather@v1") -> FeatureMetrics:
        """Build + persist in one call. Returns metrics."""
        import time

        started = time.time()
        frame, period_type = self.build(name=name)
        metrics = self.persist(frame, period_type, name=name)
        metrics.duration_seconds = round(time.time() - started, 3)
        return metrics


def _num(value: Any) -> float | None:
    """Coerce a possibly-NA pandas value to float or None (never NaN at rest)."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    n = _num(value)
    return int(n) if n is not None else None
