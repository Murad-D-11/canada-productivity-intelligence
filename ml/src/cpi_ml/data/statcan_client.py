"""Typed client for the Statistics Canada Web Data Service (WDS).

Reference: https://www.statcan.gc.ca/en/developers/wds/user-guide

Implements the documented REST methods needed for full-history ingestion of a
data cube:

    * ``POST /getCubeMetadata``            -> dimensions, members, coverage
    * ``GET  /getFullTableDownloadCSV/{pid}/en`` -> URL to a zipped CSV bundle

The full-table CSV bundle is the correct mechanism for retrieving *every*
historical observation of a cube (the point-query methods are for small,
discrete pulls). The client returns typed objects — never raw JSON — and
preserves the original payload for archival.

Design:
    * configurable timeout
    * retries with exponential backoff on transient failures (5xx, timeouts)
    * graceful HTTP failure handling -> typed exceptions
    * structured logging via the stdlib logger
    * no fabricated responses; StatCan status strings are surfaced verbatim
"""

from __future__ import annotations

import io
import logging
import time
import zipfile
from collections.abc import Iterator
from datetime import date, datetime

import requests

from cpi_ml.data.exceptions import (
    StatCanHTTPError,
    StatCanResponseError,
)
from cpi_ml.data.schemas import (
    FREQUENCY_CODE_TO_PERIOD,
    CubeMetadata,
    Dimension,
    DimensionMember,
)

logger = logging.getLogger("cpi_ml.data.statcan")

# Transient HTTP statuses that justify a retry.
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class StatCanClient:
    """Typed, resilient client for the StatCan WDS.

    Parameters
    ----------
    base_url:
        WDS REST base, e.g. ``https://www150.statcan.gc.ca/t1/wds/rest``.
    session:
        Optional pre-configured ``requests.Session`` (used by tests to mount
        mock adapters).
    timeout:
        Per-request timeout in seconds.
    max_retries:
        Number of retry attempts for transient failures.
    backoff_base:
        Base for exponential backoff (seconds). Delay = base * 2**attempt.
    request_delay_ms:
        Politeness delay applied before each request.
    """

    def __init__(
        self,
        base_url: str,
        *,
        session: requests.Session | None = None,
        timeout: float = 30.0,
        max_retries: int = 4,
        backoff_base: float = 0.5,
        request_delay_ms: int = 0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._request_delay = request_delay_ms / 1000.0

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
                    last_exc = StatCanHTTPError(
                        f"HTTP {resp.status_code} from {url}", status_code=resp.status_code
                    )
                else:
                    return resp

            if attempt < self._max_retries:
                delay = self._backoff_base * (2**attempt)
                logger.info("backing off %.2fs before retry", delay)
                time.sleep(delay)

        assert last_exc is not None
        if isinstance(last_exc, StatCanHTTPError):
            raise last_exc
        raise StatCanHTTPError(f"request to {url} failed: {last_exc}") from last_exc

    # -- metadata discovery -------------------------------------------------
    def get_cube_metadata(self, product_id: int) -> CubeMetadata:
        """Discover a cube's dimensions, members, coverage, and frequency.

        Calls ``POST /getCubeMetadata`` with ``[{"productId": <pid>}]`` and
        parses the response into a typed :class:`CubeMetadata`.
        """
        url = f"{self._base_url}/getCubeMetadata"
        resp = self._request("POST", url, json=[{"productId": product_id}])
        if resp.status_code != 200:
            raise StatCanHTTPError(
                f"getCubeMetadata returned HTTP {resp.status_code}", status_code=resp.status_code
            )
        body = resp.json()
        entry = _first_entry(body, "getCubeMetadata")
        obj = entry.get("object")
        if not isinstance(obj, dict):
            raise StatCanResponseError("getCubeMetadata: missing 'object' in response")
        return _parse_cube_metadata(product_id, obj)

    # -- full historical download -------------------------------------------
    def get_full_table_download_url(self, product_id: int, lang: str = "en") -> str:
        """Return the URL of the zipped full-table CSV bundle for a cube.

        Calls ``GET /getFullTableDownloadCSV/{pid}/{lang}``. StatCan returns a
        JSON envelope whose ``object`` is the download URL.
        """
        url = f"{self._base_url}/getFullTableDownloadCSV/{product_id}/{lang}"
        resp = self._request("GET", url)
        if resp.status_code != 200:
            raise StatCanHTTPError(
                f"getFullTableDownloadCSV returned HTTP {resp.status_code}",
                status_code=resp.status_code,
            )
        body = resp.json()
        if not isinstance(body, dict) or body.get("status") != "SUCCESS":
            raise StatCanResponseError(f"getFullTableDownloadCSV: unexpected response {body!r}")
        download_url = body.get("object")
        if not isinstance(download_url, str) or not download_url:
            raise StatCanResponseError("getFullTableDownloadCSV: missing download URL")
        return download_url

    def download_full_table_csv(self, product_id: int, lang: str = "en") -> tuple[bytes, bytes]:
        """Download and unzip the full-table bundle.

        Returns ``(data_csv_bytes, metadata_csv_bytes)``. The bundle contains
        ``{pid}.csv`` (data) and ``{pid}_Metadata.csv``.
        """
        download_url = self.get_full_table_download_url(product_id, lang)
        logger.info("downloading full table bundle for %d from %s", product_id, download_url)
        resp = self._request("GET", download_url)
        if resp.status_code != 200:
            raise StatCanHTTPError(
                f"bundle download returned HTTP {resp.status_code}", status_code=resp.status_code
            )
        return _split_bundle(resp.content, product_id)

    def iter_data_csv_rows(self, data_csv: bytes) -> Iterator[dict[str, str]]:
        """Yield rows from the data CSV as dicts (streaming, memory-friendly)."""
        import csv

        text = io.TextIOWrapper(io.BytesIO(data_csv), encoding="utf-8-sig", newline="")
        reader = csv.DictReader(text)
        for row in reader:
            yield {(k or "").strip(): (v or "").strip() for k, v in row.items()}


# --------------------------------------------------------------------------
# Response parsing helpers
# --------------------------------------------------------------------------
def _first_entry(body: object, method: str) -> dict:
    """WDS array-style responses return a list of ``{status, object}`` items."""
    if isinstance(body, list):
        if not body:
            raise StatCanResponseError(f"{method}: empty response array")
        entry = body[0]
    elif isinstance(body, dict):
        entry = body
    else:
        raise StatCanResponseError(f"{method}: unexpected response type {type(body)!r}")
    if entry.get("status") != "SUCCESS":
        raise StatCanResponseError(f"{method}: status={entry.get('status')!r}")
    return entry


def _parse_date(value: object) -> date | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _parse_cube_metadata(product_id: int, obj: dict) -> CubeMetadata:
    freq_code = obj.get("frequencyCode")
    freq_code_int = int(freq_code) if isinstance(freq_code, (int, str)) and str(freq_code).isdigit() else None
    period_type = FREQUENCY_CODE_TO_PERIOD.get(freq_code_int) if freq_code_int is not None else None

    dimensions: list[Dimension] = []
    for dim in obj.get("dimension", []) or []:
        members = [
            DimensionMember(
                member_id=int(m["memberId"]),
                name=str(m.get("memberNameEn") or m.get("memberName") or "").strip(),
                parent_member_id=(
                    int(m["parentMemberId"])
                    if m.get("parentMemberId") not in (None, "", 0, "0")
                    else None
                ),
                classification_code=(
                    str(m["classificationCode"]).strip()
                    if m.get("classificationCode") not in (None, "")
                    else None
                ),
                terminated=str(m.get("terminated", "0")) in {"1", "true", "True"},
            )
            for m in (dim.get("member", []) or [])
            if m.get("memberId") is not None
        ]
        dimensions.append(
            Dimension(
                dimension_position_id=int(dim.get("dimensionPositionId", len(dimensions) + 1)),
                name=str(dim.get("dimensionNameEn") or dim.get("dimensionName") or "").strip(),
                members=members,
            )
        )

    return CubeMetadata(
        product_id=product_id,
        cube_title=str(obj.get("cubeTitleEn") or obj.get("cubeTitle") or "").strip(),
        frequency_code=freq_code_int,
        period_type=period_type,
        start_date=_parse_date(obj.get("cubeStartDate")),
        end_date=_parse_date(obj.get("cubeEndDate")),
        release_time=_parse_datetime(obj.get("releaseTime")),
        dimensions=dimensions,
        raw_payload=obj,
    )


def _split_bundle(content: bytes, product_id: int) -> tuple[bytes, bytes]:
    """Split a StatCan CSV zip bundle into (data, metadata) byte blobs."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise StatCanResponseError("full-table bundle is not a valid zip") from exc

    data_name: str | None = None
    meta_name: str | None = None
    for name in zf.namelist():
        lower = name.lower()
        if lower.endswith("_metadata.csv"):
            meta_name = name
        elif lower.endswith(".csv"):
            data_name = name
    if data_name is None:
        raise StatCanResponseError(
            f"data CSV not found in bundle for {product_id}; contents={zf.namelist()}"
        )
    data_bytes = zf.read(data_name)
    meta_bytes = zf.read(meta_name) if meta_name else b""
    return data_bytes, meta_bytes
