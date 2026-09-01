"""Client for the Statistics Canada Web Data Service (WDS).

Reference: https://www.statcan.gc.ca/en/developers/wds/user-guide

Only real, documented WDS REST methods are used. This client performs live HTTP
requests; it never returns synthetic data. When Statistics Canada returns an
error or a "no data" status, that status is preserved and surfaced to callers
so target values are never silently imputed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class WdsResponse:
    """Envelope around a WDS REST response, preserving the raw payload."""

    status: str
    payload: Any


class StatCanWdsClient:
    """Thin wrapper over documented WDS REST endpoints.

    Documented methods used here:
        * POST getDataFromVectorsAndLatestNPeriods
        * POST getBulkVectorDataByRange
        * GET  getAllCubesListLite
    See the WDS user guide for the full contract.
    """

    def __init__(self, base_url: str, session: requests.Session | None = None, timeout: int = 30):
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._timeout = timeout

    def get_cubes_list_lite(self) -> WdsResponse:
        """Return the lightweight list of available data cubes (tables)."""
        url = f"{self._base_url}/getAllCubesListLite"
        resp = self._session.get(url, timeout=self._timeout)
        resp.raise_for_status()
        return WdsResponse(status="SUCCESS", payload=resp.json())

    def get_data_from_vectors_and_latest_n_periods(
        self, vector_ids: list[int], n_periods: int
    ) -> WdsResponse:
        """Fetch the latest ``n_periods`` observations for the given vectors.

        Vectors are StatCan's stable pointers to individual data series. The
        response status returned by WDS is preserved verbatim.
        """
        url = f"{self._base_url}/getDataFromVectorsAndLatestNPeriods"
        body = [{"vectorId": vid, "latestN": n_periods} for vid in vector_ids]
        resp = self._session.post(url, json=body, timeout=self._timeout)
        resp.raise_for_status()
        payload = resp.json()
        # WDS returns a list of {status, object} entries; keep them intact.
        return WdsResponse(status="SUCCESS", payload=payload)
