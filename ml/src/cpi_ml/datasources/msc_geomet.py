"""Client for the Environment and Climate Change Canada MSC GeoMet OGC API.

Reference: https://eccc-msc.github.io/open-data/msc-geomet/ogc_api_en/

Uses the documented OGC API - Features endpoints under https://api.weather.gc.ca.
Performs live HTTP requests only; never fabricates responses.
"""

from __future__ import annotations

from typing import Any

import requests


class MscGeoMetClient:
    """Wrapper over the GeoMet-OGC-API (OGC API - Features)."""

    def __init__(self, base_url: str, session: requests.Session | None = None, timeout: int = 30):
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._timeout = timeout

    def list_collections(self) -> dict[str, Any]:
        """GET /collections — list available data collections."""
        url = f"{self._base_url}/collections"
        resp = self._session.get(url, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

    def get_collection(self, collection_id: str) -> dict[str, Any]:
        """GET /collections/{collectionId} — metadata for one collection."""
        url = f"{self._base_url}/collections/{collection_id}"
        resp = self._session.get(url, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()

    def get_items(
        self, collection_id: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """GET /collections/{collectionId}/items — feature records as GeoJSON."""
        url = f"{self._base_url}/collections/{collection_id}/items"
        resp = self._session.get(url, params=params or {}, timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()
