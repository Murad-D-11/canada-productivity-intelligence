"""Command-line entry point for ML pipelines.

Provides discoverable subcommands. Data-fetching commands perform live requests
against official endpoints; they never emit fabricated data.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from cpi_ml import __version__
from cpi_ml.config import get_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cpi-ml",
        description="Canada Productivity Intelligence ML pipelines.",
    )
    parser.add_argument("--version", action="version", version=f"cpi-ml {__version__}")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("config", help="Print resolved configuration (no secrets).")
    sub.add_parser("sources", help="Show configured official data sources.")

    ingest = sub.add_parser(
        "ingest-statcan",
        help="Ingest Statistics Canada table 36-10-0207-01 (labour productivity).",
    )
    ingest.add_argument(
        "--product-id", type=int, default=36100207, help="StatCan product ID (default 36100207)."
    )
    ingest.add_argument(
        "--incremental",
        action="store_true",
        help="Only ingest observations not already stored (skip duplicates).",
    )
    ingest.add_argument(
        "--log-level", default="INFO", help="Logging level (DEBUG/INFO/WARNING/ERROR)."
    )

    weather = sub.add_parser(
        "ingest-weather",
        help="Ingest Environment Canada (MSC GeoMet) weather observations.",
    )
    weather.add_argument(
        "--collection", default="climate-monthly",
        help="MSC GeoMet collection id (default climate-monthly).",
    )
    weather.add_argument(
        "--period", default="MONTHLY", choices=["ANNUAL", "QUARTERLY", "MONTHLY"],
        help="Temporal resolution to aggregate weather to (default MONTHLY).",
    )
    weather.add_argument(
        "--provinces", default=None,
        help="Comma-separated province codes to ingest (default: all Canadian provinces).",
    )
    weather.add_argument(
        "--start", default=None, help="Start date YYYY-MM-DD (optional).",
    )
    weather.add_argument(
        "--end", default=None, help="End date YYYY-MM-DD (optional).",
    )
    weather.add_argument(
        "--max-per-province", type=int, default=None,
        help="Cap records fetched per province (useful for a quick smoke ingest).",
    )
    weather.add_argument(
        "--incremental", action="store_true",
        help="Only ingest observations not already stored (skip duplicates).",
    )
    weather.add_argument(
        "--log-level", default="INFO", help="Logging level (DEBUG/INFO/WARNING/ERROR)."
    )

    feats = sub.add_parser(
        "generate-features",
        help="Build the ML-ready feature matrix from productivity + weather.",
    )
    feats.add_argument(
        "--name", default="productivity+weather@v1",
        help="Feature set name recorded for reproducibility.",
    )
    feats.add_argument(
        "--log-level", default="INFO", help="Logging level (DEBUG/INFO/WARNING/ERROR)."
    )

    train = sub.add_parser(
        "train-model",
        help="Train + evaluate forecasting models and save the best as an artifact.",
    )
    train.add_argument(
        "--feature-set-id", default=None,
        help="FeatureSet id to train on (default: most recent).",
    )
    train.add_argument(
        "--horizon", type=int, default=1,
        help="Forecast horizon in periods/quarters ahead (default 1).",
    )
    train.add_argument(
        "--val-fraction", type=float, default=0.2,
        help="Fraction of the time span used for the validation block (default 0.2).",
    )
    train.add_argument(
        "--test-fraction", type=float, default=0.2,
        help="Fraction of the time span used for the held-out test block (default 0.2).",
    )
    train.add_argument(
        "--log-level", default="INFO", help="Logging level (DEBUG/INFO/WARNING/ERROR)."
    )

    predict = sub.add_parser(
        "predict",
        help="Generate a forecast from a trained model artifact (JSON feature input).",
    )
    predict.add_argument(
        "--model-version", default=None,
        help="Model version to use (default: latest trained).",
    )
    predict.add_argument(
        "--features", default=None,
        help='Feature values as JSON, e.g. \'{"prodLag1": 101.2, "prodLag4": 99.8}\'.',
    )
    predict.add_argument(
        "--features-file", default=None,
        help="Path to a JSON file with feature values (alternative to --features).",
    )
    predict.add_argument(
        "--forecast-period", default=None,
        help="Optional label for the period being forecast (recorded in output).",
    )
    predict.add_argument(
        "--log-level", default="WARNING", help="Logging level (DEBUG/INFO/WARNING/ERROR)."
    )

    return parser


def cmd_config() -> int:
    settings = get_settings()
    print("Resolved ML configuration:")
    print(f"  StatCan WDS base URL : {settings.statcan_wds_base_url}")
    print(f"  MSC GeoMet base URL  : {settings.msc_geomet_ogc_api_base_url}")
    print(f"  Random seed          : {settings.random_seed}")
    print(f"  Artifacts dir        : {settings.artifacts_dir}")
    print(f"  Database configured  : {bool(settings.database_url)}")
    return 0


def cmd_sources() -> int:
    settings = get_settings()
    print("Official data sources (live endpoints; no fabricated data):")
    print(f"  Statistics Canada WDS  -> {settings.statcan_wds_base_url}")
    print(f"  MSC GeoMet OGC API     -> {settings.msc_geomet_ogc_api_base_url}")
    print("  Canadian Survey on Business Conditions -> via StatCan WDS vectors")
    return 0


def cmd_ingest_statcan(product_id: int, incremental: bool, log_level: str) -> int:
    """Run the StatCan ETL for the given cube and write quality reports."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Imports are local so `cpi-ml config` works without DB/network deps loaded.
    from sqlalchemy import text

    from cpi_ml.data.etl import TABLE_REF, StatCanETL
    from cpi_ml.data.report import build_report_payload, write_reports
    from cpi_ml.data.repository import StatCanRepository
    from cpi_ml.data.statcan_client import StatCanClient

    settings = get_settings()
    if not settings.database_url:
        print("ERROR: DATABASE_URL is not configured. Set it in .env or the environment.")
        return 2

    client = StatCanClient(
        settings.statcan_wds_base_url,
        request_delay_ms=settings.request_delay_ms,
    )
    repo = StatCanRepository(settings.database_url)

    etl = StatCanETL(client, repo)
    print(f"Ingesting StatCan product {product_id} ({TABLE_REF})...")
    metrics = etl.ingest(product_id=product_id, incremental=incremental)

    # Read back discovered industries/measures + dataset title for the report.
    with repo.transaction() as conn:
        title = conn.execute(
            text('SELECT title FROM "StatCanDataset" WHERE "productId"=:p'),
            {"p": product_id},
        ).scalar_one()
        dataset_id = conn.execute(
            text('SELECT id FROM "StatCanDataset" WHERE "productId"=:p'),
            {"p": product_id},
        ).scalar_one()
        industries = [
            r[0]
            for r in conn.execute(
                text('SELECT name FROM "StatCanIndustry" WHERE "datasetId"=:d ORDER BY name'),
                {"d": dataset_id},
            ).fetchall()
        ]
        measures = [
            r[0]
            for r in conn.execute(
                text('SELECT name FROM "StatCanMeasure" WHERE "datasetId"=:d ORDER BY name'),
                {"d": dataset_id},
            ).fetchall()
        ]

    payload = build_report_payload(
        product_id=product_id,
        table_ref=TABLE_REF,
        title=title,
        metrics=metrics,
        industries=industries,
        measures=measures,
        mode="INCREMENTAL" if incremental else "INITIAL",
    )
    # docs/ lives at the repo root (two levels up from ml/src/cpi_ml).
    docs_dir = Path(__file__).resolve().parents[3] / "docs"
    md_path, json_path = write_reports(payload, docs_dir=docs_dir)

    print("\nIngestion summary:")
    print(f"  downloaded={metrics.downloaded} inserted={metrics.inserted} "
          f"updated={metrics.updated} duplicates={metrics.duplicates} "
          f"rejected={metrics.rejected} missing={metrics.missing}")
    print(f"  period: {metrics.earliest} -> {metrics.latest}")
    print(f"  industries={metrics.industries} measures={metrics.measures}")
    print(f"  reports: {md_path}")
    print(f"           {json_path}")
    return 0


def cmd_ingest_weather(
    *,
    collection: str,
    period: str,
    provinces: str | None,
    start: str | None,
    end: str | None,
    max_per_province: int | None,
    incremental: bool,
    log_level: str,
) -> int:
    """Run the MSC GeoMet weather ETL and write quality reports."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    from datetime import date

    from cpi_ml.data.schemas import PeriodType
    from cpi_ml.data.weather_client import WeatherClient
    from cpi_ml.data.weather_etl import WeatherETL
    from cpi_ml.data.weather_report import build_report_payload, write_reports
    from cpi_ml.data.weather_repository import WeatherRepository

    settings = get_settings()
    if not settings.database_url:
        print("ERROR: DATABASE_URL is not configured. Set it in .env or the environment.")
        return 2

    def _parse_date(s: str | None) -> date | None:
        return date.fromisoformat(s) if s else None

    prov_tuple = (
        tuple(p.strip().upper() for p in provinces.split(",") if p.strip())
        if provinces
        else None
    )

    client = WeatherClient(
        settings.msc_geomet_ogc_api_base_url,
        request_delay_ms=settings.request_delay_ms,
    )
    repo = WeatherRepository(settings.database_url)
    etl = WeatherETL(client, repo)

    print(f"Ingesting MSC GeoMet weather (collection {collection}, period {period})...")
    metrics = etl.ingest(
        collection_id=collection,
        period_type=PeriodType(period),
        provinces=prov_tuple,
        start=_parse_date(start),
        end=_parse_date(end),
        incremental=incremental,
        max_records_per_province=max_per_province,
    )

    payload = build_report_payload(
        collection_id=collection,
        metrics=metrics,
        period_type=period,
        mode="INCREMENTAL" if incremental else "INITIAL",
    )
    docs_dir = Path(__file__).resolve().parents[3] / "docs"
    md_path, json_path = write_reports(payload, docs_dir=docs_dir)

    print("\nWeather ingestion summary:")
    print(f"  downloaded={metrics.downloaded} inserted={metrics.inserted} "
          f"updated={metrics.updated} duplicates={metrics.duplicates} "
          f"rejected={metrics.rejected} missing={metrics.missing}")
    print(f"  stations={metrics.stations} provinces={sorted(metrics.provinces)}")
    print(f"  period: {metrics.earliest} -> {metrics.latest}")
    print(f"  reports: {md_path}")
    print(f"           {json_path}")
    return 0


def cmd_generate_features(*, name: str, log_level: str) -> int:
    """Build + persist the ML-ready feature matrix."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    from cpi_ml.features_pipeline import FeaturePipeline

    settings = get_settings()
    if not settings.database_url:
        print("ERROR: DATABASE_URL is not configured. Set it in .env or the environment.")
        return 2

    pipeline = FeaturePipeline(settings.database_url)
    print(f"Generating feature matrix '{name}'...")
    metrics = pipeline.run(name=name)

    print("\nFeature generation summary:")
    print(f"  rows={metrics.rows} industries={metrics.industries} "
          f"measures={metrics.measures}")
    print(f"  rows with weather={metrics.with_weather}")
    print(f"  period: {metrics.earliest} -> {metrics.latest}")
    print(f"  feature set id: {metrics.feature_set_id}")
    print(f"  duration: {metrics.duration_seconds}s")
    return 0


def cmd_train_model(
    *,
    feature_set_id: str | None,
    horizon: int,
    val_fraction: float,
    test_fraction: float,
    log_level: str,
) -> int:
    """Train, evaluate, select, and persist a forecasting model artifact."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    from cpi_ml.training import ForecastTrainer

    settings = get_settings()
    if not settings.database_url:
        print("ERROR: DATABASE_URL is not configured. Set it in .env or the environment.")
        return 2

    # Resolve the artifacts dir relative to the ml/ package root when relative.
    artifacts_dir = settings.artifacts_dir
    if not Path(artifacts_dir).is_absolute():
        artifacts_dir = str(Path(__file__).resolve().parents[2] / artifacts_dir)

    trainer = ForecastTrainer(
        settings.database_url,
        artifacts_dir=artifacts_dir,
        random_seed=settings.random_seed,
    )
    print(f"Training forecasting models (horizon={horizon} period(s))...")
    report = trainer.run(
        feature_set_id=feature_set_id,
        horizon=horizon,
        val_fraction=val_fraction,
        test_fraction=test_fraction,
    )

    print("\nModel comparison (chronological validation, then held-out test):")
    print(f"  feature set: {report.feature_set_id}")
    print(f"  features   : {', '.join(report.feature_names)}")
    print(f"  train {report.train_period['start']}..{report.train_period['end']} "
          f"({report.n_train_rows} rows) | "
          f"val {report.val_period['start']}..{report.val_period['end']} "
          f"({report.n_val_rows}) | "
          f"test {report.test_period['start']}..{report.test_period['end']} "
          f"({report.n_test_rows})")
    print(f"  {'model':<16}{'val MAE':>10}{'val RMSE':>11}{'val R2':>9}"
          f"{'test MAE':>11}{'test RMSE':>12}{'test R2':>9}")
    for r in report.results:
        r2 = f"{r.val_r2:.3f}" if r.val_r2 is not None else "n/a"
        tr2 = f"{r.test_r2:.3f}" if r.test_r2 is not None else "n/a"
        tmae = f"{r.test_mae:.4f}" if r.test_mae is not None else "n/a"
        trmse = f"{r.test_rmse:.4f}" if r.test_rmse is not None else "n/a"
        marker = " *" if r.model_type == report.selected_model_type else "  "
        print(f"{marker}{r.model_type:<14}{r.val_mae:>10.4f}{r.val_rmse:>11.4f}{r2:>9}"
              f"{tmae:>11}{trmse:>12}{tr2:>9}")
    print(f"\n  selected: {report.selected_model_type} "
          f"({'beats' if report.beats_baseline else 'does NOT beat'} naive baseline)")
    print(f"  model version: {report.model_version}")
    print(f"  artifact: {report.artifact_dir}")
    return 0


def cmd_predict(
    *,
    model_version: str | None,
    features: str | None,
    features_file: str | None,
    forecast_period: str | None,
    log_level: str,
) -> int:
    """Load a trained artifact and print a structured forecast as JSON."""
    import json

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.WARNING),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    from cpi_ml.prediction import ProductivityForecaster

    settings = get_settings()
    artifacts_dir = settings.artifacts_dir
    if not Path(artifacts_dir).is_absolute():
        artifacts_dir = str(Path(__file__).resolve().parents[2] / artifacts_dir)

    if features_file:
        feature_values = json.loads(Path(features_file).read_text(encoding="utf-8"))
    elif features:
        feature_values = json.loads(features)
    else:
        print("ERROR: provide feature values via --features or --features-file.")
        return 2

    try:
        forecaster = ProductivityForecaster.load(artifacts_dir, model_version)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 2

    result = forecaster.predict(feature_values, forecast_period=forecast_period)
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "config":
        return cmd_config()
    if args.command == "sources":
        return cmd_sources()
    if args.command == "ingest-statcan":
        return cmd_ingest_statcan(args.product_id, args.incremental, args.log_level)
    if args.command == "ingest-weather":
        return cmd_ingest_weather(
            collection=args.collection,
            period=args.period,
            provinces=args.provinces,
            start=args.start,
            end=args.end,
            max_per_province=args.max_per_province,
            incremental=args.incremental,
            log_level=args.log_level,
        )
    if args.command == "generate-features":
        return cmd_generate_features(name=args.name, log_level=args.log_level)
    if args.command == "train-model":
        return cmd_train_model(
            feature_set_id=args.feature_set_id,
            horizon=args.horizon,
            val_fraction=args.val_fraction,
            test_fraction=args.test_fraction,
            log_level=args.log_level,
        )
    if args.command == "predict":
        return cmd_predict(
            model_version=args.model_version,
            features=args.features,
            features_file=args.features_file,
            forecast_period=args.forecast_period,
            log_level=args.log_level,
        )

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
