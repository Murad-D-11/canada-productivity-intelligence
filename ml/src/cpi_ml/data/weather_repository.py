"""Database repository for the weather pipeline (SQLAlchemy Core).

Mirrors :mod:`cpi_ml.data.repository` (StatCan) exactly: SQLAlchemy Core against
the Prisma-created PascalCase tables, Python-generated string ids, a single
transaction per run, and ``ON CONFLICT`` batch upserts. Values are written as
``None`` when the source reported them missing — never fabricated.
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy import text
from sqlalchemy.engine import Connection

from cpi_ml.data.repository import _normalize_db_url, make_id


class WeatherRepository:
    """Data-access layer for WeatherStation / WeatherObservation / run tables."""

    def __init__(self, database_url: str, engine: Engine | None = None) -> None:
        self._engine = engine or create_engine(_normalize_db_url(database_url), future=True)

    @property
    def engine(self) -> Engine:
        return self._engine

    @contextmanager
    def transaction(self):
        """Yield a connection wrapped in a single transaction (commit/rollback)."""
        with self._engine.begin() as conn:
            yield conn

    # -- stations -----------------------------------------------------------
    def upsert_station(
        self,
        conn: Connection,
        *,
        station_id: str,
        name: str,
        province: str,
        latitude: float | None,
        longitude: float | None,
        elevation: float | None,
    ) -> str:
        """Insert or update a station by its natural key; returns its row id."""
        row = conn.execute(
            text('SELECT id FROM "WeatherStation" WHERE "stationId" = :s'),
            {"s": station_id},
        ).fetchone()
        if row:
            row_id = row[0]
            conn.execute(
                text(
                    'UPDATE "WeatherStation" SET name=:n, province=:p, latitude=:lat, '
                    'longitude=:lon, elevation=:elev WHERE id=:id'
                ),
                {"n": name, "p": province, "lat": latitude, "lon": longitude,
                 "elev": elevation, "id": row_id},
            )
            return row_id
        row_id = make_id()
        conn.execute(
            text(
                'INSERT INTO "WeatherStation" '
                '(id, "stationId", name, province, latitude, longitude, elevation, "createdAt") '
                'VALUES (:id, :s, :n, :p, :lat, :lon, :elev, :now)'
            ),
            {"id": row_id, "s": station_id, "n": name, "p": province, "lat": latitude,
             "lon": longitude, "elev": elevation, "now": datetime.utcnow()},
        )
        return row_id

    # -- ingestion run ------------------------------------------------------
    def create_ingestion_run(self, conn: Connection, *, collection_id: str, mode: str) -> str:
        run_id = make_id()
        conn.execute(
            text(
                'INSERT INTO "WeatherIngestionRun" (id, status, mode, "collectionId", "startedAt") '
                'VALUES (:id, CAST(:s AS "IngestionStatus"), CAST(:m AS "IngestionMode"), :c, :now)'
            ),
            {"id": run_id, "s": "RUNNING", "m": mode, "c": collection_id, "now": datetime.utcnow()},
        )
        return run_id

    def finish_ingestion_run(
        self, conn: Connection, *, run_id: str, status: str, metrics: dict[str, Any]
    ) -> None:
        conn.execute(
            text(
                'UPDATE "WeatherIngestionRun" SET status=CAST(:s AS "IngestionStatus"), '
                '"finishedAt"=:now, "observationsDownloaded"=:dl, "observationsInserted"=:ins, '
                '"observationsUpdated"=:upd, "duplicatesSkipped"=:dup, "rowsRejected"=:rej, '
                '"missingValues"=:miss, "stationsDiscovered"=:st, "earliestPeriod"=:early, '
                '"latestPeriod"=:late, "durationSeconds"=:dur, "errorMessage"=:err WHERE id=:id'
            ),
            {
                "s": status, "now": datetime.utcnow(),
                "dl": metrics.get("downloaded", 0), "ins": metrics.get("inserted", 0),
                "upd": metrics.get("updated", 0), "dup": metrics.get("duplicates", 0),
                "rej": metrics.get("rejected", 0), "miss": metrics.get("missing", 0),
                "st": metrics.get("stations", 0), "early": metrics.get("earliest"),
                "late": metrics.get("latest"), "dur": metrics.get("duration_seconds"),
                "err": metrics.get("error"), "id": run_id,
            },
        )

    # -- observations -------------------------------------------------------
    def existing_station_period_variables(
        self, conn: Connection
    ) -> set[tuple[str, date, str]]:
        """Return the set of (stationRowId, periodStart, variable) already stored.

        Used for incremental ingestion and duplicate detection.
        """
        rows = conn.execute(
            text('SELECT "stationId", "periodStart", variable FROM "WeatherObservation"')
        ).fetchall()
        result: set[tuple[str, date, str]] = set()
        for station_row_id, period, variable in rows:
            period_date = period.date() if isinstance(period, datetime) else period
            result.add((station_row_id, period_date, str(variable)))
        return result

    def upsert_observations(
        self, conn: Connection, rows: Sequence[dict[str, Any]]
    ) -> tuple[int, int]:
        """Batch upsert weather observations by natural key.

        Uses ON CONFLICT on (stationId, periodStart, variable). Returns
        ``(inserted, updated)`` using the caller-provided ``_is_new`` flag.
        """
        inserted = 0
        updated = 0
        for r in rows:
            params = {k: v for k, v in r.items() if k != "_is_new"}
            conn.execute(
                text(
                    'INSERT INTO "WeatherObservation" '
                    '(id, "stationId", province, "periodStart", "periodLabel", "periodType", '
                    'variable, value, unit, aggregation, "sampleCount", source, "collectionId", '
                    '"retrievedAt", "ingestedAt", "ingestionRunId") '
                    'VALUES (:id, :stationId, :province, :periodStart, :periodLabel, '
                    'CAST(:periodType AS "PeriodType"), CAST(:variable AS "WeatherVariable"), '
                    ':value, :unit, :aggregation, :sampleCount, CAST(:source AS "DataSource"), '
                    ':collectionId, :retrievedAt, :ingestedAt, :ingestionRunId) '
                    'ON CONFLICT ("stationId", "periodStart", variable) DO UPDATE SET '
                    'value=EXCLUDED.value, unit=EXCLUDED.unit, aggregation=EXCLUDED.aggregation, '
                    '"sampleCount"=EXCLUDED."sampleCount", "retrievedAt"=EXCLUDED."retrievedAt", '
                    '"ingestedAt"=EXCLUDED."ingestedAt", "ingestionRunId"=EXCLUDED."ingestionRunId"'
                ),
                params,
            )
            if r.get("_is_new", True):
                inserted += 1
            else:
                updated += 1
        return inserted, updated
