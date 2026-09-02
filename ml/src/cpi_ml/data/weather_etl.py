"""ETL pipeline for MSC GeoMet weather ingestion (Master Prompt 3).

Flow: GeoMet API -> raw feature records -> validation -> province matching ->
temporal aggregation (to productivity resolution) -> missing-value cleaning ->
PostgreSQL (transactional batches).

Design mirrors :class:`cpi_ml.data.etl.StatCanETL`:
    * a single rollback-safe transaction for the load
    * per-record validation with rejected-row tracking
    * IngestionMetrics for the quality report
    * ORIGINAL identifiers preserved (station id, province, source date)
    * missing values remain ``None`` (never imputed)

Aggregation: raw records (daily or monthly, per station) are grouped by
(station, normalized period, variable) and reduced using each variable's
semantics — MEAN for temperature/wind, SUM for precipitation/snowfall — over the
non-null samples only. A period with no non-null samples yields ``None``.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from cpi_ml.data.exceptions import WeatherValidationError
from cpi_ml.data.repository import make_id
from cpi_ml.data.schemas import PeriodType
from cpi_ml.data.validators import normalize_period
from cpi_ml.data.weather_client import WeatherClient
from cpi_ml.data.weather_repository import WeatherRepository
from cpi_ml.data.weather_schemas import (
    VARIABLE_AGGREGATION,
    VARIABLE_UNIT,
    Aggregation,
    RawWeatherRecord,
    WeatherVariable,
)

logger = logging.getLogger("cpi_ml.data.weather_etl")

# Canadian province/territory codes used to scope ingestion and to match
# weather to the provinces where productivity industries operate. Discovered
# station provinces are validated against this set.
CANADIAN_PROVINCES: tuple[str, ...] = (
    "AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT",
)


@dataclass
class RejectedRecord:
    reason: str
    station_id: str


@dataclass
class WeatherMetrics:
    downloaded: int = 0
    inserted: int = 0
    updated: int = 0
    duplicates: int = 0
    rejected: int = 0
    missing: int = 0
    stations: int = 0
    earliest: date | None = None
    latest: date | None = None
    duration_seconds: float | None = None
    error: str | None = None
    rejected_records: list[RejectedRecord] = field(default_factory=list)
    provinces: set[str] = field(default_factory=set)

    def as_run_dict(self) -> dict[str, Any]:
        return {
            "downloaded": self.downloaded, "inserted": self.inserted,
            "updated": self.updated, "duplicates": self.duplicates,
            "rejected": self.rejected, "missing": self.missing,
            "stations": self.stations, "earliest": self.earliest,
            "latest": self.latest, "duration_seconds": self.duration_seconds,
            "error": self.error,
        }


# One aggregation bucket per (station, period, variable).
@dataclass
class _Bucket:
    station: RawWeatherRecord
    period_start: date
    period_label: str
    variable: WeatherVariable
    samples: list[float] = field(default_factory=list)


class WeatherETL:
    """Orchestrates extraction, validation, aggregation, and loading."""

    def __init__(self, client: WeatherClient, repo: WeatherRepository) -> None:
        self._client = client
        self._repo = repo

    def ingest(
        self,
        *,
        collection_id: str,
        period_type: PeriodType = PeriodType.MONTHLY,
        provinces: tuple[str, ...] | None = None,
        start: date | None = None,
        end: date | None = None,
        incremental: bool = False,
        max_records_per_province: int | None = None,
    ) -> WeatherMetrics:
        """Run a weather ingestion. Returns quality metrics.

        Records are downloaded per province (so we can attribute weather to the
        provinces where industries operate), aggregated to ``period_type``, and
        loaded in a single transaction (rollback-safe).
        """
        started = time.time()
        metrics = WeatherMetrics()
        target_provinces = provinces or CANADIAN_PROVINCES
        retrieved_at = datetime.now(UTC)

        # 1. Extraction + aggregation (in memory; weather volumes are modest at
        #    monthly/provincial resolution).
        buckets: dict[tuple[str, date, WeatherVariable], _Bucket] = {}
        stations_seen: dict[str, RawWeatherRecord] = {}

        for province in target_provinces:
            for record in self._client.iter_observations(
                collection_id,
                province=province,
                start=start,
                end=end,
                max_records=max_records_per_province,
            ):
                metrics.downloaded += 1
                try:
                    self._accumulate(record, period_type, buckets, metrics)
                except WeatherValidationError as exc:
                    metrics.rejected += 1
                    if len(metrics.rejected_records) < 200:
                        metrics.rejected_records.append(
                            RejectedRecord(str(exc), record.station_id)
                        )
                    continue
                stations_seen[record.station_id] = record
                if record.province:
                    metrics.provinces.add(record.province)

        metrics.stations = len(stations_seen)

        # 2. Determine existing keys for incremental / duplicate detection.
        with self._repo.transaction() as conn:
            station_row_ids = {
                sid: self._repo.upsert_station(
                    conn,
                    station_id=rec.station_id,
                    name=rec.station_name,
                    province=rec.province,
                    latitude=rec.latitude,
                    longitude=rec.longitude,
                    elevation=rec.elevation,
                )
                for sid, rec in stations_seen.items()
            }
            existing = (
                self._repo.existing_station_period_variables(conn)
                if incremental
                else set()
            )

        # 3. Single transaction for the load (rollback-safe).
        try:
            with self._repo.transaction() as conn:
                run_id = self._repo.create_ingestion_run(
                    conn,
                    collection_id=collection_id,
                    mode="INCREMENTAL" if incremental else "INITIAL",
                )
                batch: list[dict[str, Any]] = []
                for (sid, period_start, variable), bucket in buckets.items():
                    station_row_id = station_row_ids[sid]
                    value = _aggregate(bucket.samples, VARIABLE_AGGREGATION[variable])
                    if value is None:
                        metrics.missing += 1

                    key = (station_row_id, period_start, variable.value)
                    is_new = key not in existing
                    if not is_new and incremental:
                        metrics.duplicates += 1
                        continue

                    metrics.earliest = (
                        period_start if metrics.earliest is None
                        else min(metrics.earliest, period_start)
                    )
                    metrics.latest = (
                        period_start if metrics.latest is None
                        else max(metrics.latest, period_start)
                    )

                    batch.append({
                        "id": make_id(),
                        "stationId": station_row_id,
                        "province": bucket.station.province,
                        "periodStart": period_start,
                        "periodLabel": bucket.period_label,
                        "periodType": period_type.value,
                        "variable": variable.value,
                        "value": value,
                        "unit": VARIABLE_UNIT[variable],
                        "aggregation": VARIABLE_AGGREGATION[variable].value,
                        "sampleCount": len(bucket.samples),
                        "source": "MSC_GEOMET",
                        "collectionId": collection_id,
                        "retrievedAt": retrieved_at,
                        "ingestedAt": datetime.now(UTC),
                        "ingestionRunId": run_id,
                        "_is_new": is_new,
                    })
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
            logger.exception("weather ingestion failed; transaction rolled back")
            try:
                with self._repo.transaction() as conn:
                    run_id2 = self._repo.create_ingestion_run(
                        conn, collection_id=collection_id,
                        mode="INCREMENTAL" if incremental else "INITIAL",
                    )
                    self._repo.finish_ingestion_run(
                        conn, run_id=run_id2, status="FAILED", metrics=metrics.as_run_dict()
                    )
            except Exception:  # noqa: BLE001
                logger.exception("failed to record failed weather ingestion run")
            raise

        logger.info(
            "weather ingestion complete: downloaded=%d inserted=%d updated=%d "
            "duplicates=%d rejected=%d stations=%d",
            metrics.downloaded, metrics.inserted, metrics.updated,
            metrics.duplicates, metrics.rejected, metrics.stations,
        )
        return metrics

    # -- accumulate one record into aggregation buckets ---------------------
    def _accumulate(
        self,
        record: RawWeatherRecord,
        period_type: PeriodType,
        buckets: dict[tuple[str, date, WeatherVariable], _Bucket],
        metrics: WeatherMetrics,
    ) -> None:
        province = (record.province or "").strip().upper()
        if province and province not in CANADIAN_PROVINCES:
            raise WeatherValidationError(f"unknown province code: {province!r}")

        # Reuse the StatCan period normalizer so weather aligns to the same
        # temporal grid as productivity. The source date drives the period.
        period_start, period_label = normalize_period(
            record.observed_on.isoformat(), period_type
        )

        for variable, value in record.values.items():
            key = (record.station_id, period_start, variable)
            bucket = buckets.get(key)
            if bucket is None:
                bucket = _Bucket(
                    station=record,
                    period_start=period_start,
                    period_label=period_label,
                    variable=variable,
                )
                buckets[key] = bucket
            # Only real (non-null) samples contribute; missing stays missing.
            if value is not None:
                bucket.samples.append(value)


def _aggregate(samples: list[float], how: Aggregation) -> float | None:
    """Aggregate non-null samples. Empty -> None (never fabricated)."""
    if not samples:
        return None
    if how is Aggregation.SUM:
        return round(sum(samples), 4)
    return round(sum(samples) / len(samples), 4)
