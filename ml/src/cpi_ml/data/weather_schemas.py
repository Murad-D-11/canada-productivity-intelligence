"""Typed models for MSC GeoMet weather data.

We never pass raw GeoJSON around the application. OGC API - Features responses
are parsed into these dataclasses at the client boundary. Only the variables
useful for productivity forecasting are retained: temperature, precipitation,
snowfall, and wind speed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class WeatherVariable(str, Enum):
    """Weather variables retained for forecasting (mirrors Prisma enum)."""

    TEMPERATURE = "TEMPERATURE"
    PRECIPITATION = "PRECIPITATION"
    SNOWFALL = "SNOWFALL"
    WIND_SPEED = "WIND_SPEED"


class Aggregation(str, Enum):
    """How a variable is aggregated over a reporting period."""

    MEAN = "MEAN"
    SUM = "SUM"


# Each retained variable's aggregation semantics + canonical unit. Temperature
# and wind are averaged over the period; precipitation and snowfall are summed.
VARIABLE_AGGREGATION: dict[WeatherVariable, Aggregation] = {
    WeatherVariable.TEMPERATURE: Aggregation.MEAN,
    WeatherVariable.PRECIPITATION: Aggregation.SUM,
    WeatherVariable.SNOWFALL: Aggregation.SUM,
    WeatherVariable.WIND_SPEED: Aggregation.MEAN,
}

VARIABLE_UNIT: dict[WeatherVariable, str] = {
    WeatherVariable.TEMPERATURE: "degC",
    WeatherVariable.PRECIPITATION: "mm",
    WeatherVariable.SNOWFALL: "cm",
    WeatherVariable.WIND_SPEED: "km/h",
}

# Candidate MSC GeoMet property names per variable. GeoMet climate collections
# expose several property names over time; we probe these in order and use the
# first present, non-null value. Nothing is fabricated when all are absent.
VARIABLE_SOURCE_PROPERTIES: dict[WeatherVariable, tuple[str, ...]] = {
    WeatherVariable.TEMPERATURE: (
        "MEAN_TEMPERATURE",
        "TEMP_MEAN",
        "mean_temp",
        "MEAN_TEMP",
    ),
    WeatherVariable.PRECIPITATION: (
        "TOTAL_PRECIPITATION",
        "TOTAL_PRECIP",
        "total_precip",
        "PRECIP_TOTAL",
    ),
    WeatherVariable.SNOWFALL: (
        "TOTAL_SNOWFALL",
        "TOTAL_SNOW",
        "SNOW_ON_GRND",
        "total_snow",
    ),
    WeatherVariable.WIND_SPEED: (
        "SPEED_MAX_GUST",
        "WIND_SPEED",
        "wind_speed",
        "MEAN_WIND_SPEED",
    ),
}


@dataclass(frozen=True)
class Station:
    """A weather station discovered from GeoMet feature records."""

    station_id: str
    name: str
    province: str
    latitude: float | None = None
    longitude: float | None = None
    elevation: float | None = None


@dataclass(frozen=True)
class RawWeatherRecord:
    """A single parsed GeoMet feature (one station-period record).

    Retains the original station id and date. ``values`` maps each retained
    variable to its parsed float (or None when the source reported it missing).
    """

    station_id: str
    station_name: str
    province: str
    observed_on: date
    latitude: float | None
    longitude: float | None
    elevation: float | None
    values: dict[WeatherVariable, float | None] = field(default_factory=dict)
