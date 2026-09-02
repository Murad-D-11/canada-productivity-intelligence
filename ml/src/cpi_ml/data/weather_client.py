"""Typed, resilient client for the MSC GeoMet OGC API - Features.

Reference: https://eccc-msc.github.io/open-data/msc-geomet/ogc_api_en/

Retrieves historical weather observations for the variables useful to
productivity forecasting (temperature, precipitation, snowfall, wind speed)
from the documented ``/collections/{id}/items`` endpoint. The client:

    * uses a configurable timeout
    * retries with exponential backoff on transient failures (5xx, timeouts)
    * paginates automatically via the OGC ``offset``/``limit`` parameters
    * handles HTTP failures gracefully -> typed exceptions
    * emits structured logs
    * returns typed objects (never raw GeoJSON), and never fabricates values —
      variables missing from the source stay ``None``.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from datetime import date, datetime
from typing import Any

import requests

from cpi_ml.data.exceptions import WeatherHTTPError, WeatherResponseError
from cpi_ml.data.weather_schemas import (
    VARIABLE_SOURCE_PROPERTIES,
    RawWeatherRecord,
    WeatherVariable,
)

logger = logging.getLogger("cpi_ml.data.weather")

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# Default MSC GeoMet climate collection with monthly summaries per station.
DEFAULT_COLLECTION = "climate-monthly"

# GeoMet property names commonly used for station identity / province / date.
_STATION_ID_PROPS = ("CLIMATE_IDENTIFIER", "STN_ID", "STATION_ID", "climate_identifier")
_STATION_NAME_PROPS = ("STATION_NAME", "STN_NAME", "station_name", "NAME")
_PROVINCE_PROPS = ("PROVINCE_CODE", "PROV_STATE_TERR_CODE", "province_code", "PROVINCE")
_DATE_PROPS = ("LOCAL_DATE", "DATE", "local_date", "LOCAL_YEAR_MONTH")


class WeatherClient:
    """Typed, resilient client for the GeoMet OGC API - Features."""

    def __init__(
        self,
        base_url: str,
        *,
        session: requests.Session | None = None,
        timeout: float = 30.0,
        max_retries: int = 4,
        backoff_base: float = 0.5,
        request_delay_ms: int = 0,
        page_size: int = 500,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._request_delay = request_delay_ms / 1000.0
        self._page_size = page_size

    # -- low-level request with retry/backoff -------------------------------
    def _request(self, method: str, url: str, **kwargs: object) -> requests.Response:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            if self._request_delay:
                time.sleep(self._request_delay)
            try:
                logger.debug("%s %s (attempt %d)", method, url, attempt + 1)
                resp = self._session.request(method, url, timeout=self._timeout, **kwargs)  # type: ignore[arg-type]
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_exc = exc
                logger.warning("transient network error on %s: %s", url, exc)
            else:
                if resp.status_code in _RETRYABLE_STATUS:
                    logger.warning(
                        "retryable HTTP %d on %s (attempt %d)",
                        resp.status_code,
                        url,
                        attempt + 1,
                    )
                    last_exc = WeatherHTTPError(
                        f"HTTP {resp.status_code} from {url}", status_code=resp.status_code
                    )
                else:
                    return resp

            if attempt < self._max_retries:
                delay = self._backoff_base * (2**attempt)
                logger.info("backing off %.2fs before retry", delay)
                time.sleep(delay)

        assert last_exc is not None
        if isinstance(last_exc, WeatherHTTPError):
            raise last_exc
        raise WeatherHTTPError(f"request to {url} failed: {last_exc}") from last_exc

    # -- collection metadata ------------------------------------------------
    def get_collection(self, collection_id: str) -> dict[str, Any]:
        """GET /collections/{id} — metadata for one collection (typed dict)."""
        url = f"{self._base_url}/collections/{collection_id}"
        resp = self._request("GET", url)
        if resp.status_code != 200:
            raise WeatherHTTPError(
                f"get_collection returned HTTP {resp.status_code}", status_code=resp.status_code
            )
        body = resp.json()
        if not isinstance(body, dict) or "id" not in body:
            raise WeatherResponseError(f"unexpected collection payload: {body!r}")
        return body

    # -- paginated feature retrieval ----------------------------------------
    def iter_observations(
        self,
        collection_id: str,
        *,
        province: str | None = None,
        start: date | None = None,
        end: date | None = None,
        extra_params: dict[str, Any] | None = None,
        max_records: int | None = None,
    ) -> Iterator[RawWeatherRecord]:
        """Yield typed weather records, paginating automatically.

        Parameters mirror the OGC API - Features query model. ``province`` is
        applied as a property filter when provided; ``start``/``end`` bound the
        date range. Records are parsed into :class:`RawWeatherRecord`; malformed
        features (no station id or date) are skipped with a debug log rather
        than fabricated.
        """
        offset = 0
        yielded = 0
        while True:
            params: dict[str, Any] = {
                "f": "json",
                "limit": self._page_size,
                "offset": offset,
            }
            if province:
                # GeoMet climate collections expose PROVINCE_CODE as a queryable.
                params["PROVINCE_CODE"] = province
            if start and end:
                params["datetime"] = f"{start.isoformat()}/{end.isoformat()}"
            elif start:
                params["datetime"] = f"{start.isoformat()}/.."
            elif end:
                params["datetime"] = f"../{end.isoformat()}"
            if extra_params:
                params.update(extra_params)

            url = f"{self._base_url}/collections/{collection_id}/items"
            resp = self._request("GET", url, params=params)
            if resp.status_code != 200:
                raise WeatherHTTPError(
                    f"items returned HTTP {resp.status_code}", status_code=resp.status_code
                )
            body = resp.json()
            features = _features(body)
            if not features:
                break

            for feat in features:
                record = _parse_feature(feat)
                if record is None:
                    continue
                yield record
                yielded += 1
                if max_records is not None and yielded >= max_records:
                    return

            # OGC pagination: stop when fewer than a full page returned.
            if len(features) < self._page_size:
                break
            offset += self._page_size


# --------------------------------------------------------------------------
# Response parsing helpers
# --------------------------------------------------------------------------
def _features(body: object) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise WeatherResponseError(f"expected GeoJSON object, got {type(body)!r}")
    feats = body.get("features")
    if feats is None:
        raise WeatherResponseError("response missing 'features' array")
    if not isinstance(feats, list):
        raise WeatherResponseError("'features' is not a list")
    return feats


def _first_prop(props: dict[str, Any], names: tuple[str, ...]) -> Any:
    for n in names:
        if n in props and props[n] not in (None, ""):
            return props[n]
    return None


def _parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_obs_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    # GeoMet dates appear as "YYYY-MM-DD", "YYYY-MM-DD HH:MM:SS", or "YYYY-MM".
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[: len(fmt) + 4], fmt).date()
        except ValueError:
            continue
    # Bare "YYYY-MM" fallback.
    try:
        parts = text.split("-")
        if len(parts) >= 2:
            return date(int(parts[0]), int(parts[1]), 1)
    except (ValueError, IndexError):
        return None
    return None


def _parse_feature(feat: dict[str, Any]) -> RawWeatherRecord | None:
    props = feat.get("properties")
    if not isinstance(props, dict):
        return None

    station_id = _first_prop(props, _STATION_ID_PROPS)
    obs_date = _parse_obs_date(_first_prop(props, _DATE_PROPS))
    if station_id is None or obs_date is None:
        logger.debug("skipping feature without station id or date")
        return None

    name = _first_prop(props, _STATION_NAME_PROPS) or str(station_id)
    province = (_first_prop(props, _PROVINCE_PROPS) or "").strip().upper()

    lat = lon = elev = None
    geom = feat.get("geometry")
    if isinstance(geom, dict) and isinstance(geom.get("coordinates"), (list, tuple)):
        coords = geom["coordinates"]
        if len(coords) >= 2:
            lon = _parse_float(coords[0])
            lat = _parse_float(coords[1])
        if len(coords) >= 3:
            elev = _parse_float(coords[2])

    values: dict[WeatherVariable, float | None] = {}
    for variable, source_props in VARIABLE_SOURCE_PROPERTIES.items():
        values[variable] = _parse_float(_first_prop(props, source_props))

    return RawWeatherRecord(
        station_id=str(station_id),
        station_name=str(name),
        province=province,
        observed_on=obs_date,
        latitude=lat,
        longitude=lon,
        elevation=elev,
        values=values,
    )
