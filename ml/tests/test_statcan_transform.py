"""Tests for ETL transformation logic (no DB, no network).

Exercises coordinate parsing, member resolution, period normalization, value
parsing, and the regression rules for invalid industries / malformed quarters /
null values — all at the row-transform level.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cpi_ml.data.etl import StatCanETL, _coordinate_positions, _role_columns
from cpi_ml.data.exceptions import StatCanValidationError
from cpi_ml.data.metadata import resolve_dimension_roles
from cpi_ml.data.schemas import (
    CubeMetadata,
    Dimension,
    DimensionMember,
    PeriodType,
)


def _metadata() -> CubeMetadata:
    return CubeMetadata(
        product_id=36100207,
        cube_title="Indexes of labour productivity",
        frequency_code=9,
        period_type=PeriodType.MONTHLY,
        start_date=None,
        end_date=None,
        release_time=None,
        dimensions=[
            Dimension(1, "Geography", [DimensionMember(1, "Canada", classification_code="11124")]),
            Dimension(
                2,
                "Labour productivity measures and related variables",
                [DimensionMember(1, "Real GDP"), DimensionMember(5, "Labour productivity")],
            ),
            Dimension(
                3,
                "North American Industry Classification System (NAICS)",
                [DimensionMember(19, "Total economy"), DimensionMember(2, "Agriculture")],
            ),
        ],
        raw_payload={},
    )


def _maps():
    return (
        {1: "geo-1"},  # geo_map: memberId -> row id
        {19: "ind-19", 2: "ind-2"},  # industry_map
        {1: "meas-1", 5: "meas-5"},  # measure_map
    )


def _etl() -> StatCanETL:
    # Client/repo unused by _transform_row.
    return StatCanETL(client=None, repo=None)  # type: ignore[arg-type]


def test_coordinate_positions() -> None:
    assert _coordinate_positions("1.5.19") == [1, 5, 19]
    assert _coordinate_positions("1.1.19.0.0") == [1, 1, 19, 0, 0]


def test_transform_row_resolves_members_and_value() -> None:
    md = _metadata()
    roles = resolve_dimension_roles(md)
    role_cols = _role_columns(roles)
    geo_map, ind_map, meas_map = _maps()
    row = {
        "REF_DATE": "2020-01",
        "UOM": "Index, 2017=100",
        "VECTOR": "v12345",
        "COORDINATE": "1.5.19",  # geo=1, measure=5, industry=19
        "VALUE": "101.5",
        "STATUS": "",
        "SYMBOL": "",
        "SCALAR_ID": "0",
    }
    prepared = _etl()._transform_row(
        row, "ds-1", md, roles, role_cols, geo_map, ind_map, meas_map,
        PeriodType.MONTHLY, datetime.now(UTC), "run-1",
    )
    assert prepared["industryId"] == "ind-19"
    assert prepared["measureId"] == "meas-5"
    assert prepared["geographyId"] == "geo-1"
    assert prepared["value"] == 101.5
    assert prepared["coordinate"] == "1.5.19"
    assert prepared["vectorId"] == 12345
    assert prepared["periodLabel"] == "2020-01"


def test_transform_row_suppressed_value_is_none() -> None:
    md = _metadata()
    roles = resolve_dimension_roles(md)
    role_cols = _role_columns(roles)
    geo_map, ind_map, meas_map = _maps()
    row = {
        "REF_DATE": "2020-01", "UOM": "Index, 2017=100", "VECTOR": "v2",
        "COORDINATE": "1.1.19", "VALUE": "", "STATUS": "..", "SYMBOL": "", "SCALAR_ID": "0",
    }
    prepared = _etl()._transform_row(
        row, "ds-1", md, roles, role_cols, geo_map, ind_map, meas_map,
        PeriodType.MONTHLY, datetime.now(UTC), "run-1",
    )
    assert prepared["value"] is None
    assert prepared["statusCode"] == ".."


def test_transform_row_rejects_unknown_industry() -> None:
    md = _metadata()
    roles = resolve_dimension_roles(md)
    role_cols = _role_columns(roles)
    geo_map, ind_map, meas_map = _maps()
    row = {
        "REF_DATE": "2020-01", "UOM": "x", "VECTOR": "v9",
        "COORDINATE": "1.5.999",  # industry 999 not in map
        "VALUE": "1.0", "STATUS": "", "SYMBOL": "", "SCALAR_ID": "0",
    }
    with pytest.raises(StatCanValidationError):
        _etl()._transform_row(
            row, "ds-1", md, roles, role_cols, geo_map, ind_map, meas_map,
            PeriodType.MONTHLY, datetime.now(UTC), "run-1",
        )


def test_transform_row_rejects_missing_coordinate() -> None:
    md = _metadata()
    roles = resolve_dimension_roles(md)
    role_cols = _role_columns(roles)
    geo_map, ind_map, meas_map = _maps()
    row = {"REF_DATE": "2020-01", "COORDINATE": "", "VALUE": "1.0"}
    with pytest.raises(StatCanValidationError):
        _etl()._transform_row(
            row, "ds-1", md, roles, role_cols, geo_map, ind_map, meas_map,
            PeriodType.MONTHLY, datetime.now(UTC), "run-1",
        )


def test_resolve_dimension_roles_maps_correctly() -> None:
    roles = resolve_dimension_roles(_metadata())
    assert roles.geography.name == "Geography"
    assert "NAICS" in roles.industry.name
    assert "productivity" in roles.measure.name.lower()
