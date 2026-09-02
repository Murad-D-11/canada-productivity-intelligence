"""Weather data-quality report generation (Master Prompt 3).

After each weather ingestion we write a human-readable Markdown report and a
machine-readable JSON report (consumed by the backend Data Status surface),
mirroring :mod:`cpi_ml.data.report`.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cpi_ml.data.weather_etl import WeatherMetrics

logger = logging.getLogger("cpi_ml.data.weather_report")


def build_report_payload(
    *,
    collection_id: str,
    metrics: WeatherMetrics,
    period_type: str,
    mode: str,
) -> dict[str, Any]:
    """Assemble the JSON-serializable weather report payload."""
    return {
        "generatedAt": datetime.now(UTC).isoformat(),
        "source": {
            "provider": "Environment and Climate Change Canada (MSC GeoMet)",
            "collectionId": collection_id,
        },
        "mode": mode,
        "periodType": period_type,
        "counts": {
            "downloaded": metrics.downloaded,
            "inserted": metrics.inserted,
            "updated": metrics.updated,
            "duplicates": metrics.duplicates,
            "rejected": metrics.rejected,
            "missingValues": metrics.missing,
            "stations": metrics.stations,
        },
        "period": {
            "earliest": metrics.earliest.isoformat() if metrics.earliest else None,
            "latest": metrics.latest.isoformat() if metrics.latest else None,
        },
        "provincesDiscovered": sorted(metrics.provinces),
        "variables": ["TEMPERATURE", "PRECIPITATION", "SNOWFALL", "WIND_SPEED"],
        "durationSeconds": metrics.duration_seconds,
        "rejectedSamples": [
            {"station": r.station_id, "reason": r.reason}
            for r in metrics.rejected_records[:25]
        ],
    }


def write_reports(payload: dict[str, Any], *, docs_dir: Path) -> tuple[Path, Path]:
    """Write the Markdown + JSON weather reports. Returns their paths."""
    reports_dir = docs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    md_path = reports_dir / "weather_ingestion_report.md"
    json_path = reports_dir / "weather_ingestion_report.json"

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    logger.info("wrote weather reports: %s , %s", md_path, json_path)
    return md_path, json_path


def _render_markdown(p: dict[str, Any]) -> str:
    src = p["source"]
    c = p["counts"]
    per = p["period"]
    lines = [
        "# Weather Ingestion Report",
        "",
        f"- Generated: `{p['generatedAt']}`",
        f"- Source: **{src['provider']}**",
        f"- Collection: `{src['collectionId']}`",
        f"- Period type: `{p['periodType']}`",
        f"- Mode: `{p['mode']}`",
        "",
        "## Counts",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Observations downloaded | {c['downloaded']} |",
        f"| Inserted | {c['inserted']} |",
        f"| Updated | {c['updated']} |",
        f"| Duplicates skipped | {c['duplicates']} |",
        f"| Rejected | {c['rejected']} |",
        f"| Missing values | {c['missingValues']} |",
        f"| Stations discovered | {c['stations']} |",
        "",
        "## Coverage",
        "",
        f"- Earliest period: `{per['earliest']}`",
        f"- Latest period: `{per['latest']}`",
        f"- Ingestion duration: `{p['durationSeconds']}s`",
        "",
        f"## Provinces discovered ({len(p['provincesDiscovered'])})",
        "",
    ]
    lines += [f"- {code}" for code in p["provincesDiscovered"]] or ["_None_"]
    lines += ["", "## Variables", ""]
    lines += [f"- {v}" for v in p["variables"]]

    if p["rejectedSamples"]:
        lines += ["", "## Rejected record samples", "", "| Station | Reason |", "| --- | --- |"]
        lines += [f"| {r['station']} | {r['reason']} |" for r in p["rejectedSamples"]]
    else:
        lines += ["", "## Rejected record samples", "", "_No records were rejected._"]

    lines.append("")
    return "\n".join(lines)
