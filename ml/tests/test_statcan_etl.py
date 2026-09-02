"""ETL orchestration tests using an in-memory fake repository (no DB).

Covers: full ingest metrics, incremental duplicate detection, and safe
rollback / failed-run recording when loading raises mid-run.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import Any

import pytest

from cpi_ml.data.etl import StatCanETL
from cpi_ml.data.statcan_client import StatCanClient
from tests.conftest import FakeResponse, FakeSession, make_cube_metadata_body, make_full_table_zip

BASE = "https://example.test/t1/wds/rest"


class FakeConn:
    """No-op connection handle."""


class FakeRepo:
    """In-memory repository capturing writes for assertions."""

    def __init__(self) -> None:
        self.observations: list[dict[str, Any]] = []
        self.existing: set[tuple[str, date]] = set()
        self.runs: list[dict[str, Any]] = []
        self.fail_on_upsert = False

    @contextmanager
    def transaction(self):
        yield FakeConn()

    def upsert_dataset(self, conn, **kwargs) -> str:  # noqa: ANN001, ANN003
        return "ds-1"

    def upsert_member(self, conn, *, table, dataset_id, member_id, **kwargs) -> str:  # noqa: ANN001, ANN003
        return f"{table}-{member_id}"

    def save_source_metadata(self, conn, **kwargs) -> None:  # noqa: ANN001, ANN003
        return None

    def create_ingestion_run(self, conn, *, dataset_id, mode) -> str:  # noqa: ANN001, ANN003
        run = {"dataset_id": dataset_id, "mode": mode, "status": "RUNNING"}
        self.runs.append(run)
        return f"run-{len(self.runs)}"

    def finish_ingestion_run(self, conn, *, run_id, status, metrics) -> None:  # noqa: ANN001, ANN003
        self.runs.append({"run_id": run_id, "status": status, "metrics": metrics})

    def existing_coordinate_periods(self, conn, dataset_id) -> set[tuple[str, date]]:  # noqa: ANN001
        return set(self.existing)

    def upsert_observations(self, conn, rows) -> tuple[int, int]:  # noqa: ANN001
        if self.fail_on_upsert:
            raise RuntimeError("simulated DB failure")
        inserted = updated = 0
        for r in rows:
            self.observations.append(r)
            if r.get("_is_new", True):
                inserted += 1
            else:
                updated += 1
        return inserted, updated


def _client() -> StatCanClient:
    session = FakeSession()
    session.add("POST", "/getCubeMetadata", FakeResponse(200, make_cube_metadata_body()))
    session.add(
        "GET",
        "/getFullTableDownloadCSV",
        FakeResponse(200, {"status": "SUCCESS", "object": "https://dl.test/36100207-eng.zip"}),
    )
    session.add("GET", "36100207-eng.zip", FakeResponse(200, content=make_full_table_zip()))
    return StatCanClient(BASE, session=session, backoff_base=0.0)


def test_full_ingest_inserts_all_rows() -> None:
    repo = FakeRepo()
    etl = StatCanETL(_client(), repo)
    metrics = etl.ingest(product_id=36100207, incremental=False)

    # The fixture bundle has 2 data rows (one valued, one suppressed).
    assert metrics.downloaded == 2
    assert metrics.inserted == 2
    assert metrics.rejected == 0
    assert metrics.missing == 1  # the suppressed row
    assert metrics.industries == 2
    assert metrics.measures == 2
    # Final run recorded as SUCCESS.
    assert any(r.get("status") == "SUCCESS" for r in repo.runs)


def test_incremental_skips_existing_as_duplicates() -> None:
    repo = FakeRepo()
    # Pre-seed both natural keys as existing.
    repo.existing = {("1.5.19", date(2020, 1, 1)), ("1.1.19", date(2020, 1, 1))}
    etl = StatCanETL(_client(), repo)
    metrics = etl.ingest(product_id=36100207, incremental=True)

    assert metrics.duplicates == 2
    assert metrics.inserted == 0


def test_failed_load_records_failed_run_and_reraises() -> None:
    repo = FakeRepo()
    repo.fail_on_upsert = True
    etl = StatCanETL(_client(), repo)
    with pytest.raises(RuntimeError):
        etl.ingest(product_id=36100207, incremental=False)
    # A FAILED run must have been recorded (rollback-safe accounting).
    assert any(r.get("status") == "FAILED" for r in repo.runs)
