"""Train, evaluate, and select productivity forecasting models.

Pipeline overview (all steps are leakage-safe and time-ordered):

    1. Load the ML-ready feature matrix (``FeatureRow``) for a ``FeatureSet``.
    2. Construct the supervised target: for each (industry, geography) series,
       y = productivity value HORIZON periods in the FUTURE (shift(-h)). The
       predictors for period t are already past-only (built with shift(1) in the
       feature pipeline), so pairing them with a future target is a valid
       one-step-ahead forecast with no look-ahead in the inputs.
    3. Split by TIME into train / validation / test on the shared period axis so
       every industry is cut at the same calendar boundary. No shuffling.
    4. Fit each candidate model on TRAIN, score on VALIDATION. Preprocessing
       (imputation, scaling) lives inside each model's Pipeline, so it is fit on
       train only — never on validation/test.
    5. Select the model with the lowest validation MAE, then confirm its
       performance on the held-out TEST period (retraining on train+val first).
    6. Persist a reproducible artifact with full metadata.

Every metric is computed from real held-out predictions. If a learned model
does not beat the naive baseline, that is reported honestly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd
from sqlalchemy import Engine, create_engine, text

from cpi_ml.artifacts import (
    ModelMetadata,
    make_model_version,
    save_artifact,
    utc_now_iso,
)
from cpi_ml.data.repository import _normalize_db_url
from cpi_ml.forecasting import (
    ForecastConfig,
    OPTIONAL_WEATHER_FEATURES,
    chronological_split_index,
    regression_metrics,
)
from cpi_ml.models import (
    ALGORITHM_LABELS,
    make_naive_factory,
    make_random_forest_factory,
    make_ridge_factory,
)

logger = logging.getLogger("cpi_ml.training")

SERIES_KEYS = ["industry", "geography", "measure"]


@dataclass
class ModelResult:
    """Validation + test metrics for one candidate model."""

    model_type: str
    algorithm: str
    val_mae: float
    val_rmse: float
    val_r2: float | None
    test_mae: float | None = None
    test_rmse: float | None = None
    test_r2: float | None = None

    def as_dict(self) -> dict:
        return {
            "model_type": self.model_type,
            "algorithm": self.algorithm,
            "validation": {"mae": self.val_mae, "rmse": self.val_rmse, "r2": self.val_r2},
            "test": {"mae": self.test_mae, "rmse": self.test_rmse, "r2": self.test_r2},
        }


@dataclass
class TrainingReport:
    """Full outcome of a training run (returned to the CLI for printing)."""

    config: ForecastConfig
    feature_set_id: str
    feature_names: list[str]
    results: list[ModelResult]
    selected_model_type: str
    baseline_model_type: str
    beats_baseline: bool
    model_version: str
    artifact_dir: str
    n_train_rows: int
    n_val_rows: int
    n_test_rows: int
    train_period: dict[str, str | None]
    val_period: dict[str, str | None]
    test_period: dict[str, str | None]


class ForecastTrainer:
    """Loads features, trains/evaluates/selects, and persists an artifact."""

    def __init__(
        self,
        database_url: str,
        *,
        artifacts_dir: str,
        random_seed: int = 42,
        engine: Engine | None = None,
    ) -> None:
        self._engine = engine or create_engine(_normalize_db_url(database_url), future=True)
        self._artifacts_dir = artifacts_dir
        self._seed = random_seed

    # -- data ---------------------------------------------------------------
    def _resolve_feature_set(self, conn, feature_set_id: str | None) -> str:
        if feature_set_id:
            return feature_set_id
        row = conn.execute(
            text('SELECT id FROM "FeatureSet" ORDER BY "createdAt" DESC LIMIT 1')
        ).fetchone()
        if not row:
            raise ValueError("no FeatureSet found; run `cpi-ml generate-features` first")
        return row[0]

    def _load_feature_rows(self, feature_set_id: str) -> pd.DataFrame:
        sql = text(
            'SELECT industry, geography, measure, "periodStart" AS period_start, '
            '"periodLabel" AS period_label, "targetValue" AS target_value, '
            '"prodLag1", "prodLag4", "prodRollMean4", "employmentGrowth", '
            '"labourCostGrowth", quarter, month, "weatherTempMean", '
            '"weatherPrecipSum", "weatherSnowfallSum", "weatherWindMean" '
            'FROM "FeatureRow" WHERE "featureSetId" = :fsid'
        )
        with self._engine.connect() as conn:
            df = pd.read_sql(sql, conn, params={"fsid": feature_set_id})
        return df

    # -- supervised construction -------------------------------------------
    def _build_supervised(
        self, frame: pd.DataFrame, config: ForecastConfig
    ) -> tuple[pd.DataFrame, list[str]]:
        """Attach the future target and select usable features.

        The label ``y`` is the productivity value ``horizon`` periods ahead
        within each series (shift(-h)). Rows without a known future target, or
        without a known previous-period value (needed by the naive baseline),
        are dropped. Returns the modelling frame and the effective feature list.
        """
        df = frame.sort_values([*SERIES_KEYS, "period_start"]).copy()
        df["period_start"] = pd.to_datetime(df["period_start"])

        # Future target within each series — this is what we forecast.
        grouped = df.groupby(SERIES_KEYS, group_keys=False)
        df["y"] = grouped["target_value"].shift(-config.horizon)

        # Decide the effective feature set: configured features plus any weather
        # feature that actually has data (weather is null when not ingested).
        candidate = list(config.feature_names)
        for wcol in OPTIONAL_WEATHER_FEATURES:
            if wcol in df.columns and df[wcol].notna().any():
                candidate.append(wcol)
        # Drop features that are entirely null (nothing to learn from).
        features = [c for c in candidate if c in df.columns and df[c].notna().any()]

        # Need a known future target to train/evaluate against.
        df = df[df["y"].notna()].copy()
        # Need the previous-period value so the naive baseline is well defined.
        if "prodLag1" in df.columns:
            df = df[df["prodLag1"].notna()].copy()
        return df, features

    # -- training -----------------------------------------------------------
    def run(
        self,
        *,
        feature_set_id: str | None = None,
        horizon: int = 1,
        val_fraction: float = 0.2,
        test_fraction: float = 0.2,
    ) -> TrainingReport:
        config = ForecastConfig(horizon=horizon)

        with self._engine.connect() as conn:
            resolved_fsid = self._resolve_feature_set(conn, feature_set_id)
        frame = self._load_feature_rows(resolved_fsid)
        if frame.empty:
            raise ValueError(f"FeatureSet {resolved_fsid} has no rows")

        model_df, features = self._build_supervised(frame, config)
        if len(model_df) < 20:
            raise ValueError(
                f"only {len(model_df)} usable training rows after target construction; "
                "ingest more data or lower the horizon"
            )

        # Chronological split on the shared period axis (no shuffling).
        val_start, test_start = chronological_split_index(
            model_df["period_start"], val_fraction=val_fraction, test_fraction=test_fraction
        )
        train_mask = model_df["period_start"] < val_start
        val_mask = (model_df["period_start"] >= val_start) & (model_df["period_start"] < test_start)
        test_mask = model_df["period_start"] >= test_start

        train_df = model_df[train_mask]
        val_df = model_df[val_mask]
        test_df = model_df[test_mask]
        if train_df.empty or val_df.empty or test_df.empty:
            raise ValueError("chronological split produced an empty partition; check data span")

        x_train, y_train = train_df[features].to_numpy(), train_df["y"].to_numpy()
        x_val, y_val = val_df[features].to_numpy(), val_df["y"].to_numpy()
        x_test, y_test = test_df[features].to_numpy(), test_df["y"].to_numpy()

        # Candidate models. Naive baseline is bound to the prodLag1 column.
        lag_index = features.index("prodLag1") if "prodLag1" in features else 0
        factories: dict[str, Any] = {
            "naive": make_naive_factory(lag_index),
            "ridge": make_ridge_factory(alpha=1.0, random_state=self._seed),
            "random_forest": make_random_forest_factory(
                n_estimators=300, random_state=self._seed
            ),
        }

        # 1) Fit on train, score on validation.
        results: list[ModelResult] = []
        fitted_on_train: dict[str, Any] = {}
        for key, factory in factories.items():
            model = factory()
            model.fit(x_train, y_train)
            fitted_on_train[key] = model
            val_pred = model.predict(x_val)
            mae, rmse, r2 = regression_metrics(y_val, val_pred)
            results.append(
                ModelResult(
                    model_type=key,
                    algorithm=ALGORITHM_LABELS[key],
                    val_mae=mae,
                    val_rmse=rmse,
                    val_r2=r2,
                )
            )
            logger.info("validation %s: MAE=%.4f RMSE=%.4f R2=%s", key, mae, rmse, r2)

        # 2) Select best by validation MAE.
        results.sort(key=lambda r: r.val_mae)
        selected = results[0]
        baseline = next(r for r in results if r.model_type == "naive")
        beats_baseline = selected.model_type == "naive" or selected.val_mae < baseline.val_mae

        # 3) Confirm every model on the held-out TEST period after retraining on
        #    train+val (standard practice: use all data before test for the
        #    final fit). Metrics remain genuine out-of-sample on test.
        x_trval = pd.concat([train_df, val_df])[features].to_numpy()
        y_trval = pd.concat([train_df, val_df])["y"].to_numpy()
        selected_test_model = None
        for r in results:
            model = factories[r.model_type]()
            model.fit(x_trval, y_trval)
            test_pred = model.predict(x_test)
            t_mae, t_rmse, t_r2 = regression_metrics(y_test, test_pred)
            r.test_mae, r.test_rmse, r.test_r2 = t_mae, t_rmse, t_r2
            logger.info("test %s: MAE=%.4f RMSE=%.4f R2=%s", r.model_type, t_mae, t_rmse, t_r2)
            if r.model_type == selected.model_type:
                selected_test_model = model

        assert selected_test_model is not None

        # 4) Persist artifact (the selected model, retrained on train+val).
        trained_at = utc_now_iso()
        version = make_model_version(config.target_measure, config.horizon, trained_at)
        preprocessing = {
            "imputation": "median (fit on training folds only)",
            "scaling": "StandardScaler for ridge; none for tree/naive",
            "missing_target_rows": "dropped",
            "missing_prodLag1_rows": "dropped",
        }

        def _span(df: pd.DataFrame) -> dict[str, str | None]:
            if df.empty:
                return {"start": None, "end": None}
            return {
                "start": str(df["period_start"].min().date()),
                "end": str(df["period_start"].max().date()),
            }

        metadata = ModelMetadata(
            model_type=selected.model_type,
            algorithm=selected.algorithm,
            model_version=version,
            target=config.target_measure,
            resolution=config.resolution,
            forecast_horizon=config.horizon,
            feature_names=features,
            preprocessing=preprocessing,
            training_period=_span(train_df),
            validation_period=_span(val_df),
            test_period=_span(test_df),
            trained_at=trained_at,
            metrics={
                "selected_model": selected.model_type,
                "beats_baseline": beats_baseline,
                "models": [r.as_dict() for r in results],
            },
            feature_set_id=resolved_fsid,
            n_train_rows=int(len(train_df)),
            n_val_rows=int(len(val_df)),
            n_test_rows=int(len(test_df)),
            random_seed=self._seed,
            notes=[
                "Attributions/associations only; the model does not establish causation.",
                "Weather features excluded when weather data is absent.",
                "One-step-ahead quarterly forecast; predictors are past-only.",
            ],
        )
        artifact_dir = save_artifact(selected_test_model, metadata, self._artifacts_dir)

        return TrainingReport(
            config=config,
            feature_set_id=resolved_fsid,
            feature_names=features,
            results=results,
            selected_model_type=selected.model_type,
            baseline_model_type="naive",
            beats_baseline=beats_baseline,
            model_version=version,
            artifact_dir=str(artifact_dir),
            n_train_rows=int(len(train_df)),
            n_val_rows=int(len(val_df)),
            n_test_rows=int(len(test_df)),
            train_period=_span(train_df),
            val_period=_span(val_df),
            test_period=_span(test_df),
        )
