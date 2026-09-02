"""Statistics Canada data pipeline package.

Provides a typed client for the StatCan Web Data Service (WDS), schema models,
validators, and ETL orchestration for ingesting official Canadian productivity
data (e.g. table 36-10-0207-01, product ID 36100207).

No module fabricates data, endpoints, or metrics. All observations preserve
their original StatCan identifiers for full provenance.
"""

from cpi_ml.data.exceptions import (
    StatCanError,
    StatCanHTTPError,
    StatCanResponseError,
    StatCanValidationError,
)

__all__ = [
    "StatCanError",
    "StatCanHTTPError",
    "StatCanResponseError",
    "StatCanValidationError",
]
