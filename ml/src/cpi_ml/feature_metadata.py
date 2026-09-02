"""Centralized feature metadata — the single source of truth.

Every engineered feature used by the forecasting model is described exactly
once here: display name, unit, human description, data source, and (where a
feature is a plausible scenario lever) reasonable min/max bounds. Explainability,
the eventual "What drives productivity?" UI, and any scenario simulator should
read from this module rather than redefining descriptions in multiple places.

IMPORTANT — wording discipline:
Descriptions talk about how a feature relates to the MODEL's prediction. They
never claim that changing a feature will CAUSE productivity to change. The model
learns statistical association from historical data, not causal effects.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class FeatureMeta:
    """Descriptive metadata for a single model feature.

    Attributes:
        name: internal feature name (matches the model's feature_names).
        display_name: human-friendly label for UI.
        unit: unit of the raw feature value (e.g. "index", "ratio", "quarter").
        description: what the feature is, in plain language. Describes the
            feature itself, not a causal claim about productivity.
        source: high-level data source (e.g. "Statistics Canada").
        source_table: specific table/API/derivation where known.
        scenario_eligible: whether it is reasonable to let a user vary this
            feature in a what-if scenario. Calendar/lag features are not.
        reasonable_min: a sensible lower bound for scenario sliders (or None).
        reasonable_max: a sensible upper bound for scenario sliders (or None).
    """

    name: str
    display_name: str
    unit: str
    description: str
    source: str
    source_table: str | None = None
    scenario_eligible: bool = False
    reasonable_min: float | None = None
    reasonable_max: float | None = None

    def as_dict(self) -> dict:
        return asdict(self)


# StatCan cube behind the productivity + derived measures.
_STATCAN = "Statistics Canada"
_CUBE = "StatCan table 36-10-0207-01 (product 36100207)"

# Ordered so that iteration is deterministic and matches the model's feature
# ordering for the current artifact. Keyed by internal feature name.
FEATURE_METADATA: dict[str, FeatureMeta] = {
    "prodLag1": FeatureMeta(
        name="prodLag1",
        display_name="Productivity (previous quarter)",
        unit="index",
        description=(
            "Labour productivity from the immediately preceding quarter. The "
            "strongest recent-history signal available to the model."
        ),
        source=_STATCAN,
        source_table=_CUBE,
        scenario_eligible=True,
        reasonable_min=80.0,
        reasonable_max=130.0,
    ),
    "prodLag4": FeatureMeta(
        name="prodLag4",
        display_name="Productivity (4 quarters ago)",
        unit="index",
        description=(
            "Labour productivity from four quarters earlier, capturing the "
            "year-over-year level for seasonal comparison."
        ),
        source=_STATCAN,
        source_table=_CUBE,
        scenario_eligible=True,
        reasonable_min=80.0,
        reasonable_max=130.0,
    ),
    "prodRollMean4": FeatureMeta(
        name="prodRollMean4",
        display_name="Productivity (trailing 4-quarter average)",
        unit="index",
        description=(
            "Average labour productivity over the four prior quarters "
            "(excludes the current quarter). A smoothed recent trend."
        ),
        source=_STATCAN,
        source_table=_CUBE,
        scenario_eligible=True,
        reasonable_min=80.0,
        reasonable_max=130.0,
    ),
    "employmentGrowth": FeatureMeta(
        name="employmentGrowth",
        display_name="Employment growth (prior period)",
        unit="ratio",
        description=(
            "Period-over-period growth in the total number of jobs, lagged one "
            "period so only past information is used."
        ),
        source=_STATCAN,
        source_table=f"{_CUBE}, measure 'Total number of jobs'",
        scenario_eligible=True,
        reasonable_min=-0.1,
        reasonable_max=0.1,
    ),
    "labourCostGrowth": FeatureMeta(
        name="labourCostGrowth",
        display_name="Labour cost growth (prior period)",
        unit="ratio",
        description=(
            "Period-over-period growth in total compensation per hour worked, "
            "lagged one period so only past information is used."
        ),
        source=_STATCAN,
        source_table=f"{_CUBE}, measure 'Total compensation per hour worked'",
        scenario_eligible=True,
        reasonable_min=-0.1,
        reasonable_max=0.1,
    ),
    "quarter": FeatureMeta(
        name="quarter",
        display_name="Quarter of year",
        unit="quarter (1-4)",
        description=(
            "Calendar quarter (1-4) used as a seasonal indicator. A structural "
            "time marker, not something a user can change."
        ),
        source="Derived (calendar)",
        source_table="Derived from period start date",
        scenario_eligible=False,
        reasonable_min=1.0,
        reasonable_max=4.0,
    ),
    "month": FeatureMeta(
        name="month",
        display_name="Month of year",
        unit="month (1-12)",
        description=(
            "Calendar month of the period start used as a seasonal indicator. "
            "A structural time marker, not something a user can change."
        ),
        source="Derived (calendar)",
        source_table="Derived from period start date",
        scenario_eligible=False,
        reasonable_min=1.0,
        reasonable_max=12.0,
    ),
    # Weather features are part of the feature contract but only populated once
    # weather has been ingested. Metadata is defined here so explanations and UI
    # can describe them consistently the moment they become active.
    "weatherTempMean": FeatureMeta(
        name="weatherTempMean",
        display_name="Mean temperature",
        unit="degrees Celsius",
        description=(
            "Average temperature for the period, aggregated from Environment "
            "Canada climate stations. Currently inactive (no weather ingested)."
        ),
        source="Environment and Climate Change Canada (MSC GeoMet)",
        source_table="MSC GeoMet OGC API (api.weather.gc.ca)",
        scenario_eligible=False,
        reasonable_min=-40.0,
        reasonable_max=40.0,
    ),
    "weatherPrecipSum": FeatureMeta(
        name="weatherPrecipSum",
        display_name="Total precipitation",
        unit="millimetres",
        description=(
            "Total precipitation for the period from Environment Canada "
            "stations. Currently inactive (no weather ingested)."
        ),
        source="Environment and Climate Change Canada (MSC GeoMet)",
        source_table="MSC GeoMet OGC API (api.weather.gc.ca)",
        scenario_eligible=False,
        reasonable_min=0.0,
        reasonable_max=1000.0,
    ),
    "weatherSnowfallSum": FeatureMeta(
        name="weatherSnowfallSum",
        display_name="Total snowfall",
        unit="centimetres",
        description=(
            "Total snowfall for the period from Environment Canada stations. "
            "Currently inactive (no weather ingested)."
        ),
        source="Environment and Climate Change Canada (MSC GeoMet)",
        source_table="MSC GeoMet OGC API (api.weather.gc.ca)",
        scenario_eligible=False,
        reasonable_min=0.0,
        reasonable_max=500.0,
    ),
    "weatherWindMean": FeatureMeta(
        name="weatherWindMean",
        display_name="Mean wind speed",
        unit="kilometres per hour",
        description=(
            "Average wind speed for the period from Environment Canada "
            "stations. Currently inactive (no weather ingested)."
        ),
        source="Environment and Climate Change Canada (MSC GeoMet)",
        source_table="MSC GeoMet OGC API (api.weather.gc.ca)",
        scenario_eligible=False,
        reasonable_min=0.0,
        reasonable_max=100.0,
    ),
}

# A generic fallback so an unknown feature never crashes explanation code; it is
# described plainly and marked as not scenario-eligible.
_UNKNOWN_TEMPLATE = FeatureMeta(
    name="",
    display_name="",
    unit="unknown",
    description="No centralized metadata is registered for this feature.",
    source="unknown",
    source_table=None,
    scenario_eligible=False,
)


def get_feature_meta(name: str) -> FeatureMeta:
    """Return metadata for ``name``, or a safe generic fallback if unregistered.

    The fallback uses the feature name as its own display name so callers always
    receive a usable, non-null record.
    """
    meta = FEATURE_METADATA.get(name)
    if meta is not None:
        return meta
    return FeatureMeta(
        name=name,
        display_name=name,
        unit=_UNKNOWN_TEMPLATE.unit,
        description=_UNKNOWN_TEMPLATE.description,
        source=_UNKNOWN_TEMPLATE.source,
        source_table=None,
        scenario_eligible=False,
    )


def scenario_eligible_features() -> list[str]:
    """Return the internal names of features eligible for scenario simulation."""
    return [name for name, meta in FEATURE_METADATA.items() if meta.scenario_eligible]
