"""Typed exceptions for the StatCan data pipeline.

A small hierarchy so callers can distinguish transport failures from response
contract violations from data-validation problems.
"""

from __future__ import annotations


class StatCanError(Exception):
    """Base class for all StatCan pipeline errors."""


class StatCanHTTPError(StatCanError):
    """Raised when an HTTP request to WDS fails after retries.

    Carries the final status code (if any) for diagnostics.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class StatCanResponseError(StatCanError):
    """Raised when a WDS response does not match the documented contract.

    Examples: missing ``status`` field, ``status != "SUCCESS"``, or an
    unexpected payload shape.
    """


class StatCanValidationError(StatCanError):
    """Raised when an observation row fails validation.

    ETL uses this to reject and log malformed rows rather than crashing.
    """


class WeatherError(Exception):
    """Base class for all MSC GeoMet weather pipeline errors."""


class WeatherHTTPError(WeatherError):
    """Raised when an HTTP request to GeoMet fails after retries.

    Carries the final status code (if any) for diagnostics.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class WeatherResponseError(WeatherError):
    """Raised when a GeoMet response does not match the expected contract.

    Examples: missing ``features`` array, non-GeoJSON payload shape.
    """


class WeatherValidationError(WeatherError):
    """Raised when a weather record fails validation.

    ETL uses this to reject and log malformed records rather than crashing.
    """
