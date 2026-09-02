"""Critical tests for the MSC GeoMet weather client (mocked; no network).

Focuses on the behaviour that matters most: parsing GeoMet feature records into
typed observations, and the no-fabrication rule (missing variables -> None).
"""

from __future__ import annotations

from cpi_ml.data.weather_client import WeatherClient
from cpi_ml.data.weather_schemas import WeatherVariable
from tests.conftest import FakeResponse, FakeSession

BASE = "https://example.test"


def _client(session: FakeSession) -> WeatherClient:
    # page_size larger than any test body so pagination terminates after one page
    # (the FakeSession returns the same page regardless of offset).
    return WeatherClient(BASE, session=session, max_retries=1, backoff_base=0.0, page_size=100)


def _items_body(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


def _feature(**props) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-79.4, 43.7, 76.5]},
        "properties": props,
    }


def test_parses_all_four_variables_and_identity() -> None:
    session = FakeSession()
    body = _items_body(
        [
            _feature(
                CLIMATE_IDENTIFIER="6158355",
                STATION_NAME="TORONTO",
                PROVINCE_CODE="ON",
                LOCAL_DATE="2020-01-01",
                MEAN_TEMPERATURE=-4.2,
                TOTAL_PRECIPITATION=55.1,
                TOTAL_SNOWFALL=30.0,
                SPEED_MAX_GUST=41.0,
            )
        ]
    )
    session.add("GET", "/collections/climate-monthly/items", FakeResponse(200, body))

    records = list(_client(session).iter_observations("climate-monthly", province="ON"))
    assert len(records) == 1
    rec = records[0]
    assert rec.station_id == "6158355"
    assert rec.province == "ON"
    assert rec.observed_on.year == 2020 and rec.observed_on.month == 1
    assert rec.latitude == 43.7 and rec.longitude == -79.4 and rec.elevation == 76.5
    assert rec.values[WeatherVariable.TEMPERATURE] == -4.2
    assert rec.values[WeatherVariable.PRECIPITATION] == 55.1
    assert rec.values[WeatherVariable.SNOWFALL] == 30.0
    assert rec.values[WeatherVariable.WIND_SPEED] == 41.0


def test_missing_variable_stays_none_not_fabricated() -> None:
    session = FakeSession()
    body = _items_body(
        [
            _feature(
                CLIMATE_IDENTIFIER="1",
                STATION_NAME="NOWHERE",
                PROVINCE_CODE="BC",
                LOCAL_DATE="2021-06-01",
                MEAN_TEMPERATURE=15.0,
                # precipitation/snow/wind absent -> must be None
            )
        ]
    )
    session.add("GET", "/collections/climate-monthly/items", FakeResponse(200, body))

    rec = list(_client(session).iter_observations("climate-monthly"))[0]
    assert rec.values[WeatherVariable.TEMPERATURE] == 15.0
    assert rec.values[WeatherVariable.PRECIPITATION] is None
    assert rec.values[WeatherVariable.SNOWFALL] is None
    assert rec.values[WeatherVariable.WIND_SPEED] is None


def test_skips_features_without_station_or_date() -> None:
    session = FakeSession()
    body = _items_body(
        [
            {"type": "Feature", "geometry": None, "properties": {"MEAN_TEMPERATURE": 1.0}},
            _feature(CLIMATE_IDENTIFIER="9", LOCAL_DATE="2020-01-01", MEAN_TEMPERATURE=2.0),
        ]
    )
    session.add("GET", "/collections/climate-monthly/items", FakeResponse(200, body))

    records = list(_client(session).iter_observations("climate-monthly"))
    # Only the valid feature is yielded; the malformed one is skipped.
    assert len(records) == 1
    assert records[0].station_id == "9"
