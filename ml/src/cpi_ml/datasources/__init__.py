"""Clients for official Government of Canada data sources."""

from cpi_ml.datasources.statcan_wds import StatCanWdsClient
from cpi_ml.datasources.msc_geomet import MscGeoMetClient

__all__ = ["StatCanWdsClient", "MscGeoMetClient"]
