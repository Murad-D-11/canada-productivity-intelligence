"""Shared pytest fixtures/helpers for StatCan data tests."""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

import requests


class FakeResponse:
    """Minimal stand-in for ``requests.Response`` used by client tests."""

    def __init__(self, status_code: int = 200, json_body: Any = None, content: bytes = b""):
        self.status_code = status_code
        self._json = json_body
        self.content = content

    def json(self) -> Any:
        if self._json is None:
            raise ValueError("no json body")
        return self._json


class FakeSession:
    """Fake ``requests.Session`` that returns queued responses per (method, url substring)."""

    def __init__(self) -> None:
        self.routes: list[tuple[str, str, FakeResponse]] = []
        self.calls: list[tuple[str, str]] = []

    def add(self, method: str, url_contains: str, response: FakeResponse) -> None:
        self.routes.append((method.upper(), url_contains, response))

    def request(self, method: str, url: str, **_kwargs: object) -> FakeResponse:
        self.calls.append((method.upper(), url))
        for m, frag, resp in self.routes:
            if m == method.upper() and frag in url:
                return resp
        raise requests.ConnectionError(f"no fake route for {method} {url}")


def make_cube_metadata_body() -> list[dict[str, Any]]:
    """A realistic (trimmed) getCubeMetadata response for product 36100207."""
    return [
        {
            "status": "SUCCESS",
            "object": {
                "productId": 36100207,
                "cubeTitleEn": "Indexes of labour productivity",
                "frequencyCode": 9,
                "cubeStartDate": "1981-01-01",
                "cubeEndDate": "2026-01-01",
                "releaseTime": "2026-03-01 08:30",
                "dimension": [
                    {
                        "dimensionPositionId": 1,
                        "dimensionNameEn": "Geography",
                        "member": [
                            {"memberId": 1, "memberNameEn": "Canada", "classificationCode": "11124"}
                        ],
                    },
                    {
                        "dimensionPositionId": 2,
                        "dimensionNameEn": "Labour productivity measures and related variables",
                        "member": [
                            {"memberId": 1, "memberNameEn": "Real gross domestic product (GDP)"},
                            {"memberId": 5, "memberNameEn": "Labour productivity"},
                        ],
                    },
                    {
                        "dimensionPositionId": 3,
                        "dimensionNameEn": "North American Industry Classification System (NAICS)",
                        "member": [
                            {"memberId": 19, "memberNameEn": "Total economy"},
                            {
                                "memberId": 2,
                                "memberNameEn": "Agriculture, forestry, fishing and hunting [11]",
                                "classificationCode": "11",
                                "parentMemberId": 1,
                            },
                        ],
                    },
                ],
            },
        }
    ]


def make_full_table_zip() -> bytes:
    """Build a valid StatCan-style CSV zip bundle in memory."""
    header = (
        '"REF_DATE","GEO","DGUID","Labour productivity measures and related variables",'
        '"North American Industry Classification System (NAICS)","UOM","UOM_ID",'
        '"SCALAR_FACTOR","SCALAR_ID","VECTOR","COORDINATE","VALUE","STATUS","SYMBOL",'
        '"TERMINATED","DECIMALS"\n'
    )
    rows = [
        # measure=5 (Labour productivity), industry=19 (Total economy) with a value
        '"2020-01","Canada","2016A000011124","Labour productivity","Total economy",'
        '"Index, 2017=100","373","units","0","v1","1.5.19","101.5","","","","3"\n',
        # suppressed value (STATUS "..") -> None
        '"2020-01","Canada","2016A000011124","Real gross domestic product (GDP)","Total economy",'
        '"Index, 2017=100","373","units","0","v2","1.1.19","","..","","","3"\n',
    ]
    data_csv = (header + "".join(rows)).encode("utf-8")
    meta_csv = b'"Cube Title","Indexes of labour productivity"\n'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("36100207.csv", data_csv)
        zf.writestr("36100207_MetaData.csv", meta_csv)
    return buf.getvalue()


def json_bytes(obj: Any) -> bytes:
    return json.dumps(obj).encode("utf-8")
