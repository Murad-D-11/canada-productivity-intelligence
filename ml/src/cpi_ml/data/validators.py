"""Validation and normalization helpers for StatCan observations.

These functions enforce the data-quality rules required by the ETL pipeline:
malformed rows are rejected (with a reason), and raw values are normalized
without ever silently altering a genuine target value. Missing values remain
``None`` rather than being imputed.
"""

from __future__ import annotations

import math
import re
from datetime import date

from cpi_ml.data.exceptions import StatCanValidationError
from cpi_ml.data.schemas import PeriodType

# StatCan reference periods appear as:
#   "2019"            -> annual
#   "2019/2020"       -> annual (fiscal year span); use the start year
#   "2019-01" / "2019/01" -> monthly
#   "2019-01-01"      -> explicit date (quarter/month start)
_ANNUAL_RE = re.compile(r"^(\d{4})$")
_FISCAL_RE = re.compile(r"^(\d{4})/(\d{4})$")
_YEAR_MONTH_RE = re.compile(r"^(\d{4})[-/](\d{2})$")
_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def normalize_period(ref_period: str, period_type: PeriodType) -> tuple[date, str]:
    """Normalize a raw StatCan reference period string.

    Returns a ``(period_start_date, period_label)`` tuple. The label is a
    stable, human-friendly key: ``"2019"`` for annual, ``"2019-Q1"`` for
    quarterly, ``"2019-01"`` for monthly.

    Raises ``StatCanValidationError`` for unparseable periods so ETL can reject
    the row rather than guess.
    """
    raw = (ref_period or "").strip()
    if not raw:
        raise StatCanValidationError("empty reference period")

    if m := _ISO_DATE_RE.match(raw):
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        start = _safe_date(year, month, day)
        return _label_for(start, period_type)

    if m := _YEAR_MONTH_RE.match(raw):
        year, month = int(m.group(1)), int(m.group(2))
        start = _safe_date(year, month, 1)
        return _label_for(start, period_type)

    if m := _FISCAL_RE.match(raw):
        # Fiscal-year span "2019/2020": anchor at the start year.
        year = int(m.group(1))
        return _safe_date(year, 1, 1), str(year)

    if m := _ANNUAL_RE.match(raw):
        year = int(m.group(1))
        return _safe_date(year, 1, 1), str(year)

    raise StatCanValidationError(f"unrecognized reference period format: {raw!r}")


def _safe_date(year: int, month: int, day: int) -> date:
    if not (1900 <= year <= 2100):
        raise StatCanValidationError(f"year out of range: {year}")
    if not (1 <= month <= 12):
        raise StatCanValidationError(f"month out of range: {month}")
    try:
        return date(year, month, day)
    except ValueError as exc:  # invalid day for month
        raise StatCanValidationError(str(exc)) from exc


def _label_for(start: date, period_type: PeriodType) -> tuple[date, str]:
    if period_type is PeriodType.ANNUAL:
        return date(start.year, 1, 1), str(start.year)
    if period_type is PeriodType.QUARTERLY:
        quarter = (start.month - 1) // 3 + 1
        q_start = date(start.year, (quarter - 1) * 3 + 1, 1)
        return q_start, f"{start.year}-Q{quarter}"
    # Monthly
    return date(start.year, start.month, 1), f"{start.year}-{start.month:02d}"


def validate_quarter_label(label: str) -> None:
    """Ensure a quarterly label is well-formed (e.g. ``2019-Q3``)."""
    if not re.match(r"^\d{4}-Q[1-4]$", label):
        raise StatCanValidationError(f"malformed quarter label: {label!r}")


def parse_value(raw: str | float | int | None) -> float | None:
    """Parse a StatCan value cell into a float or ``None``.

    Empty strings, ``".."``, ``"..."``, ``"F"``, ``"x"`` and similar StatCan
    symbols represent unavailable/suppressed data and become ``None`` — never
    zero, never imputed. Genuine numbers are returned as floats.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        if isinstance(raw, float) and math.isnan(raw):
            return None
        return float(raw)

    text = str(raw).strip()
    if text == "" or text in {"..", "...", ".", "F", "x", "X", "E", "..E"}:
        return None
    # Remove thousands separators only (never a decimal comma in English CSV).
    text = text.replace(",", "")
    try:
        return float(text)
    except ValueError as exc:
        raise StatCanValidationError(f"non-numeric value: {raw!r}") from exc


def require_non_empty(name: str, value: str | None) -> str:
    """Validate a required classifying field (industry/geography/measure)."""
    if value is None or not str(value).strip():
        raise StatCanValidationError(f"missing required field: {name}")
    return str(value).strip()


def normalize_unit(unit: str | None) -> str:
    """Normalize a unit label; unknown/blank units become ``"Unknown"``."""
    if unit is None or not str(unit).strip():
        return "Unknown"
    return str(unit).strip()
