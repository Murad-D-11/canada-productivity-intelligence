"""ETL pipeline for StatCan cube ingestion (Milestone 3).

Flow: StatCan API -> raw CSV -> validation -> normalization -> transformation
-> PostgreSQL (transactional batches).

The full-table CSV bundle is the extraction source (all historical
observations). Each row is validated; malformed rows are rejected and logged
with a reason. Transformation resolves the StatCan coordinate to member ids and
normalizes the period, unit, and identifiers while preserving every original
StatCan identifier. Loading happens in a single transaction so a mid-run
failure rolls back and preserves existing data.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from cpi_ml.data.exceptions import StatCanValidationError
from cpi_ml.data.metadata import DimensionRoles, store_metadata
from cpi_ml.data.repository import StatCanRepository, make_id
from cpi_ml.data.schemas import CubeMetadata, PeriodType
from cpi_ml.data.statcan_client import StatCanClient
from cpi_ml.data.validators import normalize_period, normalize_unit, parse_value

logger = logging.getLogger("cpi_ml.data.etl")

PRODUCT_ID = 36100207
TABLE_REF = "36-10-0207-01"

# CSV column names in the StatCan full-table data file.
COL_REF_DATE = "REF_DATE"
COL_UOM = "UOM"
COL_VECTOR = "VECTOR"
COL_COORDINATE = "COORDINATE"
COL_VALUE = "VALUE"
COL_STATUS = "STATUS"
COL_SYMBOL = "SYMBOL"
COL_SCALAR_ID = "SCALAR_ID"


@dataclass
class RejectedRow:
    line_number: int
    reason: str
    raw: dict[str, str]


@dataclass
class IngestionMetrics:
    downloaded: int = 0
    inserted: int = 0
    updated: int = 0
    duplicates: int = 0
    rejected: int = 0
    missing: int = 0
    earliest: date | None = None
    latest: date | None = None
    industries: int = 0
    measures: int = 0
    duration_seconds: float | None = None
    error: str | None = None
    rejected_rows: list[RejectedRow] = field(default_factory=list)

    def as_run_dict(self) -> dict[str, Any]:
        return {
            "downloaded": self.downloaded, "inserted": self.inserted,
            "updated": self.updated, "duplicates": self.duplicates,
            "rejected": self.rejected, "missing": self.missing,
            "earliest": self.earliest, "latest": self.latest,
            "industries": self.industries, "measures": self.measures,
            "duration_seconds": self.duration_seconds, "error": self.error,
        }


def _coordinate_positions(coordinate: str) -> list[int]:
    """Parse a coordinate like ``1.1.19`` into ``[1, 1, 19]`` (trailing zeros ok)."""
    parts = [p for p in coordinate.split(".") if p != ""]
    return [int(p) for p in parts]


@dataclass
class _RoleColumns:
    """Which CSV columns / coordinate positions correspond to each role."""

    geography_pos: int
    measure_pos: int
    industry_pos: int


def _role_columns(roles: DimensionRoles) -> _RoleColumns:
    # dimensionPositionId is 1-based; coordinate parts are in that order.
    return _RoleColumns(
        geography_pos=roles.geography.dimension_position_id,
        measure_pos=roles.measure.dimension_position_id,
        industry_pos=roles.industry.dimension_position_id,
    )


class StatCanETL:
    """Orchestrates extraction, validation, transformation, and loading."""

    def __init__(self, client: StatCanClient, repo: StatCanRepository) -> None:
        self._client = client
        self._repo = repo

    def ingest(self, *, product_id: int = PRODUCT_ID, incremental: bool = False) -> IngestionMetrics:
        """Run a full ingestion. Returns quality metrics.

        If ``incremental`` is True, observations whose (coordinate, period) are
        already stored are skipped (counted as duplicates) rather than updated,
        avoiding redundant work while still detecting genuinely new rows.
        """
        started = time.time()
        metrics = IngestionMetrics()

        # 1. Metadata discovery + dataset/member persistence (own transaction).
        metadata = self._client.get_cube_metadata(product_id)
        with self._repo.transaction() as conn:
            dataset_id, roles, geo_map, industry_map, measure_map = store_metadata(
                conn, self._repo, metadata, table_ref=TABLE_REF
            )
        metrics.industries = len(industry_map)
        metrics.measures = len(measure_map)
        role_cols = _role_columns(roles)
        period_type = metadata.period_type or PeriodType.ANNUAL

        # 2. Extraction: download the full-table CSV bundle.
        data_csv, _meta_csv = self._client.download_full_table_csv(product_id, "en")

        # 3. Determine existing keys for incremental / duplicate detection.
        with self._repo.transaction() as conn:
            existing = self._repo.existing_coordinate_periods(conn, dataset_id)

        retrieved_at = datetime.now(UTC)

        # 4. Single transaction for the whole load (rollback-safe).
        try:
            with self._repo.transaction() as conn:
                run_id = self._repo.create_ingestion_run(
                    conn, dataset_id=dataset_id, mode="INCREMENTAL" if incremental else "INITIAL"
                )
                batch: list[dict[str, Any]] = []
                for line_no, row in enumerate(self._client.iter_data_csv_rows(data_csv), start=1):
                    metrics.downloaded += 1
                    try:
                        prepared = self._transform_row(
                            row, dataset_id, metadata, roles, role_cols,
                            geo_map, industry_map, measure_map, period_type,
                            retrieved_at, run_id,
                        )
                    except StatCanValidationError as exc:
                        metrics.rejected += 1
                        if len(metrics.rejected_rows) < 200:
                            metrics.rejected_rows.append(RejectedRow(line_no, str(exc), row))
                        continue

                    if prepared["value"] is None:
                        metrics.missing += 1

                    key = (prepared["coordinate"], prepared["periodStart"])
                    is_new = key not in existing
                    if not is_new and incremental:
                        metrics.duplicates += 1
                        continue
                    prepared["_is_new"] = is_new

                    # Track period range.
                    ps = prepared["periodStart"]
                    metrics.earliest = ps if metrics.earliest is None else min(metrics.earliest, ps)
                    metrics.latest = ps if metrics.latest is None else max(metrics.latest, ps)

                    batch.append(prepared)
                    if len(batch) >= 1000:
                        ins, upd = self._repo.upsert_observations(conn, batch)
                        metrics.inserted += ins
                        metrics.updated += upd
                        batch.clear()

                if batch:
                    ins, upd = self._repo.upsert_observations(conn, batch)
                    metrics.inserted += ins
                    metrics.updated += upd

                metrics.duration_seconds = round(time.time() - started, 3)
                self._repo.finish_ingestion_run(
                    conn, run_id=run_id, status="SUCCESS", metrics=metrics.as_run_dict()
                )
        except Exception as exc:  # noqa: BLE001 - record failure then re-raise
            metrics.error = str(exc)
            metrics.duration_seconds = round(time.time() - started, 3)
            logger.exception("ingestion failed; transaction rolled back")
            # Record the failure in its own transaction (the load txn rolled back).
            try:
                with self._repo.transaction() as conn:
                    run_id2 = self._repo.create_ingestion_run(
                        conn, dataset_id=dataset_id,
                        mode="INCREMENTAL" if incremental else "INITIAL",
                    )
                    self._repo.finish_ingestion_run(
                        conn, run_id=run_id2, status="FAILED", metrics=metrics.as_run_dict()
                    )
            except Exception:  # noqa: BLE001
                logger.exception("failed to record failed ingestion run")
            raise

        logger.info(
            "ingestion complete: downloaded=%d inserted=%d updated=%d duplicates=%d rejected=%d",
            metrics.downloaded, metrics.inserted, metrics.updated,
            metrics.duplicates, metrics.rejected,
        )
        return metrics

    # -- transform one row --------------------------------------------------
    def _transform_row(
        self,
        row: dict[str, str],
        dataset_id: str,
        metadata: CubeMetadata,
        roles: DimensionRoles,
        role_cols: _RoleColumns,
        geo_map: dict[int, str],
        industry_map: dict[int, str],
        measure_map: dict[int, str],
        period_type: PeriodType,
        retrieved_at: datetime,
        run_id: str,
    ) -> dict[str, Any]:
        coordinate = (row.get(COL_COORDINATE) or "").strip()
        if not coordinate:
            raise StatCanValidationError("missing COORDINATE")
        positions = _coordinate_positions(coordinate)

        def member_at(pos: int) -> int:
            idx = pos - 1
            if idx < 0 or idx >= len(positions):
                raise StatCanValidationError(
                    f"coordinate {coordinate!r} has no position {pos}"
                )
            return positions[idx]

        geo_member = member_at(role_cols.geography_pos)
        measure_member = member_at(role_cols.measure_pos)
        industry_member = member_at(role_cols.industry_pos)

        geography_id = geo_map.get(geo_member)
        measure_id = measure_map.get(measure_member)
        industry_id = industry_map.get(industry_member)
        if geography_id is None:
            raise StatCanValidationError(f"unknown geography member {geo_member}")
        if measure_id is None:
            raise StatCanValidationError(f"unknown measure member {measure_member}")
        if industry_id is None:
            raise StatCanValidationError(f"unknown industry member {industry_member}")

        ref_period_raw = (row.get(COL_REF_DATE) or "").strip()
        period_start, period_label = normalize_period(ref_period_raw, period_type)

        value = parse_value(row.get(COL_VALUE))
        unit = normalize_unit(row.get(COL_UOM))

        vector_raw = (row.get(COL_VECTOR) or "").strip().lstrip("vV")
        vector_id = int(vector_raw) if vector_raw.isdigit() else None
        scalar_raw = (row.get(COL_SCALAR_ID) or "").strip()
        scalar_id = int(scalar_raw) if scalar_raw.isdigit() else None

        return {
            "id": make_id(),
            "datasetId": dataset_id,
            "industryId": industry_id,
            "geographyId": geography_id,
            "measureId": measure_id,
            "periodStart": period_start,
            "periodLabel": period_label,
            "periodType": period_type.value,
            "value": value,
            "unit": unit,
            "coordinate": coordinate,
            "vectorId": vector_id,
            "refPeriodRaw": ref_period_raw,
            "statusCode": (row.get(COL_STATUS) or "").strip() or None,
            "symbolCode": (row.get(COL_SYMBOL) or "").strip() or None,
            "scalarFactorCode": scalar_id,
            "retrievedAt": retrieved_at,
            "ingestedAt": datetime.now(UTC),
            "ingestionRunId": run_id,
        }
