"""Tests for StatCan validators and normalization (regression coverage)."""

from __future__ import annotations

from datetime import date

import pytest

from cpi_ml.data.exceptions import StatCanValidationError
from cpi_ml.data.schemas import PeriodType
from cpi_ml.data.validators import (
    normalize_period,
    normalize_unit,
    parse_value,
    require_non_empty,
    validate_quarter_label,
)


def test_normalize_period_annual() -> None:
    start, label = normalize_period("2019", PeriodType.ANNUAL)
    assert start == date(2019, 1, 1)
    assert label == "2019"


def test_normalize_period_monthly() -> None:
    start, label = normalize_period("2019-04", PeriodType.MONTHLY)
    assert start == date(2019, 4, 1)
    assert label == "2019-04"


def test_normalize_period_quarterly_from_month() -> None:
    start, label = normalize_period("2019-07", PeriodType.QUARTERLY)
    assert start == date(2019, 7, 1)
    assert label == "2019-Q3"


def test_normalize_period_fiscal_span() -> None:
    start, label = normalize_period("2019/2020", PeriodType.ANNUAL)
    assert start == date(2019, 1, 1)
    assert label == "2019"


# --- Regression: malformed quarters/periods are rejected -------------------
@pytest.mark.parametrize("bad", ["", "notadate", "2019-13", "2019-99-99", "19x9"])
def test_normalize_period_rejects_malformed(bad: str) -> None:
    with pytest.raises(StatCanValidationError):
        normalize_period(bad, PeriodType.MONTHLY)


def test_validate_quarter_label_accepts_valid() -> None:
    validate_quarter_label("2019-Q3")  # no raise


@pytest.mark.parametrize("bad", ["2019-Q5", "2019Q1", "2019-3", "Q1-2019"])
def test_validate_quarter_label_rejects_malformed(bad: str) -> None:
    with pytest.raises(StatCanValidationError):
        validate_quarter_label(bad)


# --- Regression: null/suppressed values never become numbers ---------------
@pytest.mark.parametrize("empty", ["", "..", "...", "F", "x", None])
def test_parse_value_treats_suppressed_as_none(empty: str | None) -> None:
    assert parse_value(empty) is None


def test_parse_value_parses_real_numbers() -> None:
    assert parse_value("101.5") == 101.5
    assert parse_value("1,234.5") == 1234.5
    assert parse_value(42) == 42.0


def test_parse_value_rejects_garbage() -> None:
    with pytest.raises(StatCanValidationError):
        parse_value("abc")


# --- Regression: required classifying fields must be present ---------------
def test_require_non_empty_rejects_blank() -> None:
    with pytest.raises(StatCanValidationError):
        require_non_empty("industry", "")
    with pytest.raises(StatCanValidationError):
        require_non_empty("industry", None)


def test_normalize_unit_defaults_unknown() -> None:
    assert normalize_unit("") == "Unknown"
    assert normalize_unit(None) == "Unknown"
    assert normalize_unit("Index, 2017=100") == "Index, 2017=100"
