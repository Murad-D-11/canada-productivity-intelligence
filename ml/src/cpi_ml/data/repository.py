"""Database repository for the StatCan pipeline (SQLAlchemy Core).

Targets the tables created by Prisma (PascalCase, quoted). We use SQLAlchemy
Core rather than the ORM so we can do efficient transactional batch upserts and
avoid maintaining a second model definition. IDs are generated in Python as
collision-resistant strings compatible with Prisma's ``String @id`` columns.

All writes for an ingestion run happen inside a single transaction so a
mid-run failure rolls back cleanly and preserves existing data.
"""

from __future__ import annotations

import secrets
from collections.abc import Sequence
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import Connection


def make_id() -> str:
    """Generate a short, URL-safe unique id (Prisma cuid-compatible string)."""
    return "c" + secrets.token_hex(12)


def _normalize_db_url(url: str) -> str:
    """Normalize a Prisma-style URL for SQLAlchemy + psycopg2.

    Prisma accepts a ``?schema=public`` query parameter, but psycopg2 rejects
    ``schema`` as a connection option. We drop that parameter (public is the
    default search_path) while preserving any other query parameters, and ensure
    the psycopg2 driver prefix is present.
    """
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    parts = urlsplit(url)
    query_pairs = [(k, v) for k, v in parse_qsl(parts.query) if k != "schema"]
    new_query = urlencode(query_pairs)
    scheme = parts.scheme
    if scheme == "postgresql":
        scheme = "postgresql+psycopg2"
    return urlunsplit((scheme, parts.netloc, parts.path, new_query, parts.fragment))


class StatCanRepository:
    """Data-access layer for StatCan pipeline tables."""

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

    # -- dataset ------------------------------------------------------------
    def upsert_dataset(
        self,
        conn: Connection,
        *,
        product_id: int,
        title: str,
        table_ref: str | None,
        frequency_code: int | None,
        frequency: str | None,
        start_date: date | None,
        end_date: date | None,
        release_time: datetime | None,
    ) -> str:
        """Insert or update a dataset row; returns its id."""
        row = conn.execute(
            text('SELECT id FROM "StatCanDataset" WHERE "productId" = :pid'),
            {"pid": product_id},
        ).fetchone()
        now = datetime.utcnow()
        if row:
            dataset_id = row[0]
            conn.execute(
                text(
                    'UPDATE "StatCanDataset" SET "title"=:title, "tableRef"=:ref, '
                    '"frequencyCode"=:fc, "frequency"=CAST(:freq AS "PeriodType"), '
                    '"startDate"=:sd, "endDate"=:ed, "releaseTime"=:rt, "updatedAt"=:now '
                    'WHERE id=:id'
                ),
                {
                    "title": title, "ref": table_ref, "fc": frequency_code, "freq": frequency,
                    "sd": start_date, "ed": end_date, "rt": release_time, "now": now,
                    "id": dataset_id,
                },
            )
            return dataset_id
        dataset_id = make_id()
        conn.execute(
            text(
                'INSERT INTO "StatCanDataset" '
                '(id, "productId", title, "tableRef", "frequencyCode", frequency, '
                '"startDate", "endDate", "releaseTime", "createdAt", "updatedAt") '
                'VALUES (:id, :pid, :title, :ref, :fc, CAST(:freq AS "PeriodType"), '
                ':sd, :ed, :rt, :now, :now)'
            ),
            {
                "id": dataset_id, "pid": product_id, "title": title, "ref": table_ref,
                "fc": frequency_code, "freq": frequency, "sd": start_date, "ed": end_date,
                "rt": release_time, "now": now,
            },
        )
        return dataset_id

    # -- dimension members --------------------------------------------------
    def upsert_member(
        self,
        conn: Connection,
        *,
        table: str,
        dataset_id: str,
        member_id: int,
        name: str,
        classification_code: str | None = None,
        parent_member_id: int | None = None,
        unit_of_measure: str | None = None,
    ) -> str:
        """Upsert an industry/geography/measure member; returns its row id.

        ``table`` is one of StatCanIndustry / StatCanGeography / StatCanMeasure.
        """
        row = conn.execute(
            text(f'SELECT id FROM "{table}" WHERE "datasetId"=:d AND "memberId"=:m'),
            {"d": dataset_id, "m": member_id},
        ).fetchone()
        if row:
            row_id = row[0]
            if table == "StatCanIndustry":
                conn.execute(
                    text(
                        'UPDATE "StatCanIndustry" SET name=:n, "classificationCode"=:c, '
                        '"parentMemberId"=:p WHERE id=:id'
                    ),
                    {"n": name, "c": classification_code, "p": parent_member_id, "id": row_id},
                )
            elif table == "StatCanMeasure":
                conn.execute(
                    text('UPDATE "StatCanMeasure" SET name=:n, "unitOfMeasure"=:u WHERE id=:id'),
                    {"n": name, "u": unit_of_measure, "id": row_id},
                )
            else:
                conn.execute(
                    text(
                        'UPDATE "StatCanGeography" SET name=:n, "classificationCode"=:c WHERE id=:id'
                    ),
                    {"n": name, "c": classification_code, "id": row_id},
                )
            return row_id

        row_id = make_id()
        now = datetime.utcnow()
        if table == "StatCanIndustry":
            conn.execute(
                text(
                    'INSERT INTO "StatCanIndustry" '
                    '(id, "datasetId", "memberId", name, "classificationCode", "parentMemberId", "createdAt") '
                    'VALUES (:id, :d, :m, :n, :c, :p, :now)'
                ),
                {"id": row_id, "d": dataset_id, "m": member_id, "n": name,
                 "c": classification_code, "p": parent_member_id, "now": now},
            )
        elif table == "StatCanMeasure":
            conn.execute(
                text(
                    'INSERT INTO "StatCanMeasure" '
                    '(id, "datasetId", "memberId", name, "unitOfMeasure", "createdAt") '
                    'VALUES (:id, :d, :m, :n, :u, :now)'
                ),
                {"id": row_id, "d": dataset_id, "m": member_id, "n": name,
                 "u": unit_of_measure, "now": now},
            )
        else:
            conn.execute(
                text(
                    'INSERT INTO "StatCanGeography" '
                    '(id, "datasetId", "memberId", name, "classificationCode", "createdAt") '
                    'VALUES (:id, :d, :m, :n, :c, :now)'
                ),
                {"id": row_id, "d": dataset_id, "m": member_id, "n": name,
                 "c": classification_code, "now": now},
            )
        return row_id

    def save_source_metadata(
        self,
        conn: Connection,
        *,
        dataset_id: str,
        source_method: str,
        payload_json: str,
        dimension_count: int,
        member_count: int,
    ) -> None:
        conn.execute(
            text(
                'INSERT INTO "SourceMetadata" '
                '(id, "datasetId", "sourceMethod", payload, "dimensionCount", "memberCount", "retrievedAt") '
                'VALUES (:id, :d, :sm, CAST(:p AS jsonb), :dc, :mc, :now)'
            ),
            {"id": make_id(), "d": dataset_id, "sm": source_method, "p": payload_json,
             "dc": dimension_count, "mc": member_count, "now": datetime.utcnow()},
        )

    # -- ingestion run ------------------------------------------------------
    def create_ingestion_run(self, conn: Connection, *, dataset_id: str, mode: str) -> str:
        run_id = make_id()
        conn.execute(
            text(
                'INSERT INTO "IngestionRun" (id, "datasetId", status, mode, "startedAt") '
                'VALUES (:id, :d, CAST(:s AS "IngestionStatus"), CAST(:m AS "IngestionMode"), :now)'
            ),
            {"id": run_id, "d": dataset_id, "s": "RUNNING", "m": mode, "now": datetime.utcnow()},
        )
        return run_id

    def finish_ingestion_run(
        self, conn: Connection, *, run_id: str, status: str, metrics: dict[str, Any]
    ) -> None:
        conn.execute(
            text(
                'UPDATE "IngestionRun" SET status=CAST(:s AS "IngestionStatus"), '
                '"finishedAt"=:now, "observationsDownloaded"=:dl, "observationsInserted"=:ins, '
                '"observationsUpdated"=:upd, "duplicatesSkipped"=:dup, "rowsRejected"=:rej, '
                '"missingValues"=:miss, "earliestPeriod"=:early, "latestPeriod"=:late, '
                '"industriesDiscovered"=:ind, "measuresDiscovered"=:meas, '
                '"durationSeconds"=:dur, "errorMessage"=:err WHERE id=:id'
            ),
            {
                "s": status, "now": datetime.utcnow(),
                "dl": metrics.get("downloaded", 0), "ins": metrics.get("inserted", 0),
                "upd": metrics.get("updated", 0), "dup": metrics.get("duplicates", 0),
                "rej": metrics.get("rejected", 0), "miss": metrics.get("missing", 0),
                "early": metrics.get("earliest"), "late": metrics.get("latest"),
                "ind": metrics.get("industries", 0), "meas": metrics.get("measures", 0),
                "dur": metrics.get("duration_seconds"), "err": metrics.get("error"),
                "id": run_id,
            },
        )

    # -- observations -------------------------------------------------------
    def existing_coordinate_periods(self, conn: Connection, dataset_id: str) -> set[tuple[str, date]]:
        """Return the set of (coordinate, periodStart) already stored.

        Used for incremental ingestion and duplicate detection.
        """
        rows = conn.execute(
            text('SELECT coordinate, "periodStart" FROM "StatCanObservation" WHERE "datasetId"=:d'),
            {"d": dataset_id},
        ).fetchall()
        result: set[tuple[str, date]] = set()
        for coord, period in rows:
            period_date = period.date() if isinstance(period, datetime) else period
            result.add((coord, period_date))
        return result

    def upsert_observations(self, conn: Connection, rows: Sequence[dict[str, Any]]) -> tuple[int, int]:
        """Batch upsert observations by natural key.

        Uses ON CONFLICT on (datasetId, coordinate, periodStart). Returns
        ``(inserted, updated)``. Because ON CONFLICT can't cheaply distinguish
        insert vs update counts in one statement, we pre-split using the caller-
        provided ``_is_new`` flag.
        """
        inserted = 0
        updated = 0
        for r in rows:
            params = {k: v for k, v in r.items() if k != "_is_new"}
            result = conn.execute(
                text(
                    'INSERT INTO "StatCanObservation" '
                    '(id, "datasetId", "industryId", "geographyId", "measureId", '
                    '"periodStart", "periodLabel", "periodType", value, unit, '
                    'coordinate, "vectorId", "refPeriodRaw", "statusCode", "symbolCode", '
                    '"scalarFactorCode", "retrievedAt", "ingestedAt", "ingestionRunId") '
                    'VALUES (:id, :datasetId, :industryId, :geographyId, :measureId, '
                    ':periodStart, :periodLabel, CAST(:periodType AS "PeriodType"), :value, :unit, '
                    ':coordinate, :vectorId, :refPeriodRaw, :statusCode, :symbolCode, '
                    ':scalarFactorCode, :retrievedAt, :ingestedAt, :ingestionRunId) '
                    'ON CONFLICT ("datasetId", coordinate, "periodStart") DO UPDATE SET '
                    'value=EXCLUDED.value, unit=EXCLUDED.unit, "statusCode"=EXCLUDED."statusCode", '
                    '"symbolCode"=EXCLUDED."symbolCode", "vectorId"=EXCLUDED."vectorId", '
                    '"retrievedAt"=EXCLUDED."retrievedAt", "ingestedAt"=EXCLUDED."ingestedAt", '
                    '"ingestionRunId"=EXCLUDED."ingestionRunId"'
                ),
                params,
            )
            # rowcount is 1 for insert, 2 for update on many drivers; use flag.
            if r.get("_is_new", True):
                inserted += 1
            else:
                updated += 1
            _ = result
        return inserted, updated
