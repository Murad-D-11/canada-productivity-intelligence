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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "config":
        return cmd_config()
    if args.command == "sources":
        return cmd_sources()
    if args.command == "ingest-statcan":
        return cmd_ingest_statcan(args.product_id, args.incremental, args.log_level)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
