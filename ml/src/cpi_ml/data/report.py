"""Data-quality report generation (Milestone 5).

After each ingestion we write a human-readable Markdown report and a
machine-readable JSON report (consumed by the backend Data Status page).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cpi_ml.data.etl import IngestionMetrics

logger = logging.getLogger("cpi_ml.data.report")


def build_report_payload(
    *,
    product_id: int,
    table_ref: str,
    title: str,
    metrics: IngestionMetrics,
    industries: list[str],
    measures: list[str],
    mode: str,
) -> dict[str, Any]:
    """Assemble the JSON-serializable report payload."""
    return {
        "generatedAt": datetime.now(UTC).isoformat(),
        "dataset": {
            "productId": product_id,
            "tableRef": table_ref,
            "title": title,
        },
        "mode": mode,
        "counts": {
            "downloaded": metrics.downloaded,
            "inserted": metrics.inserted,
            "updated": metrics.updated,
            "duplicates": metrics.duplicates,
            "rejected": metrics.rejected,
            "missingValues": metrics.missing,
        },
        "period": {
            "earliest": metrics.earliest.isoformat() if metrics.earliest else None,
            "latest": metrics.latest.isoformat() if metrics.latest else None,
        },
        "industriesDiscovered": len(industries),
        "measuresDiscovered": len(measures),
        "industries": industries,
        "measures": measures,
        "durationSeconds": metrics.duration_seconds,
        "rejectedSamples": [
            {"line": r.line_number, "reason": r.reason} for r in metrics.rejected_rows[:25]
        ],
    }


def write_reports(payload: dict[str, Any], *, docs_dir: Path) -> tuple[Path, Path]:
    """Write the Markdown + JSON reports. Returns their paths."""
    reports_dir = docs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    md_path = reports_dir / "statcan_ingestion_report.md"
    json_path = reports_dir / "statcan_ingestion_report.json"

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(payload), encoding="utf-8")
    logger.info("wrote reports: %s , %s", md_path, json_path)
    return md_path, json_path


def _render_markdown(p: dict[str, Any]) -> str:
    ds = p["dataset"]
    c = p["counts"]
    per = p["period"]
    lines = [
        "# StatCan Ingestion Report",
        "",
        f"- Generated: `{p['generatedAt']}`",
        f"- Dataset: **{ds['title']}**",
        f"- Table: `{ds['tableRef']}` (product ID `{ds['productId']}`)",
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
        "",
        "## Coverage",
        "",
        f"- Earliest period: `{per['earliest']}`",
        f"- Latest period: `{per['latest']}`",
        f"- Ingestion duration: `{p['durationSeconds']}s`",
        "",
        f"## Industries discovered ({p['industriesDiscovered']})",
        "",
    ]
    lines += [f"- {name}" for name in p["industries"]]
    lines += ["", f"## Measures discovered ({p['measuresDiscovered']})", ""]
    lines += [f"- {name}" for name in p["measures"]]

    if p["rejectedSamples"]:
        lines += ["", "## Rejected row samples", "", "| Line | Reason |", "| ---: | --- |"]
        lines += [f"| {r['line']} | {r['reason']} |" for r in p["rejectedSamples"]]
    else:
        lines += ["", "## Rejected row samples", "", "_No rows were rejected._"]

    lines.append("")
    return "\n".join(lines)
