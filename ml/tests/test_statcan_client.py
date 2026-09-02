"""Tests for the StatCan client (mocked responses only — no network)."""

from __future__ import annotations

import pytest

from cpi_ml.data.exceptions import StatCanHTTPError, StatCanResponseError
from cpi_ml.data.schemas import PeriodType
from cpi_ml.data.statcan_client import StatCanClient
from tests.conftest import (
    FakeResponse,
    FakeSession,
    make_cube_metadata_body,
    make_full_table_zip,
)

BASE = "https://example.test/t1/wds/rest"


def _client(session: FakeSession) -> StatCanClient:
    # backoff_base=0 so retries don't sleep during tests.
    return StatCanClient(BASE, session=session, max_retries=2, backoff_base=0.0)


def test_get_cube_metadata_parses_dimensions() -> None:
    session = FakeSession()
    session.add("POST", "/getCubeMetadata", FakeResponse(200, make_cube_metadata_body()))
    md = _client(session).get_cube_metadata(36100207)

    assert md.product_id == 36100207
    assert md.period_type is PeriodType.MONTHLY
    assert md.dimension_count == 3
    industry_dim = md.dimension_by_name(
        "North American Industry Classification System (NAICS)"
    )
    assert industry_dim is not None
    # Industry names are discovered from source, never hardcoded.
    names = {m.name for m in industry_dim.members}
    assert "Total economy" in names


def test_get_cube_metadata_rejects_non_success_status() -> None:
    session = FakeSession()
    session.add("POST", "/getCubeMetadata", FakeResponse(200, [{"status": "FAILED"}]))
    with pytest.raises(StatCanResponseError):
        _client(session).get_cube_metadata(36100207)


def test_full_table_download_splits_bundle() -> None:
    session = FakeSession()
    session.add(
        "GET",
        "/getFullTableDownloadCSV",
        FakeResponse(200, {"status": "SUCCESS", "object": "https://dl.test/36100207-eng.zip"}),
    )
    session.add("GET", "36100207-eng.zip", FakeResponse(200, content=make_full_table_zip()))

    data_csv, meta_csv = _client(session).download_full_table_csv(36100207)
    assert b"REF_DATE" in data_csv
    assert b"Cube Title" in meta_csv


def test_retry_on_transient_5xx_then_success() -> None:
    session = FakeSession()
    # First matching route returns 503; client should retry. Because FakeSession
    # matches the first route, we simulate recovery by swapping after one call.
    calls = {"n": 0}

    class FlakySession(FakeSession):
        def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:  # type: ignore[override]
            calls["n"] += 1
            if calls["n"] == 1:
                return FakeResponse(503)
            return FakeResponse(200, make_cube_metadata_body())

    md = _client(FlakySession()).get_cube_metadata(36100207)
    assert md.product_id == 36100207
    assert calls["n"] == 2  # one failure + one success


def test_exhausted_retries_raise_http_error() -> None:
    session = FakeSession()
    session.add("POST", "/getCubeMetadata", FakeResponse(500))
    with pytest.raises(StatCanHTTPError):
        _client(session).get_cube_metadata(36100207)
