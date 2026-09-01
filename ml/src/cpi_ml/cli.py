"""Command-line entry point for ML pipelines.

Provides discoverable subcommands. Data-fetching commands perform live requests
against official endpoints; they never emit fabricated data. In this milestone
the commands validate configuration and connectivity intent without shipping a
populated dataset.
"""

from __future__ import annotations

import argparse
import sys

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

    sources = sub.add_parser("sources", help="Show configured official data sources.")
    sources.set_defaults(command="sources")

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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "config":
        return cmd_config()
    if args.command == "sources":
        return cmd_sources()

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
