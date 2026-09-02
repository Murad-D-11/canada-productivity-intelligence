"""Typed models for StatCan WDS metadata and observations.

We never pass raw JSON around the application. WDS responses are parsed into
these dataclasses at the client boundary. Dimension/member structures mirror
the documented ``getCubeMetadata`` response.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class PeriodType(str, Enum):
    """Normalized reference-period granularity."""

    ANNUAL = "ANNUAL"
    QUARTERLY = "QUARTERLY"
    MONTHLY = "MONTHLY"


# StatCan cube "frequencyCode" values (from the WDS code sets) mapped to our
# normalized granularity. Only the codes relevant to productivity cubes are
# mapped; unknown codes fall back to None and are handled explicitly.
FREQUENCY_CODE_TO_PERIOD: dict[int, PeriodType] = {
    1: PeriodType.ANNUAL,  # Annual
    6: PeriodType.QUARTERLY,  # Quarterly
    9: PeriodType.MONTHLY,  # Monthly
    # 12 = Annual (fiscal year) also occurs; treat as annual.
    12: PeriodType.ANNUAL,
}


@dataclass(frozen=True)
class DimensionMember:
    """A single member within a cube dimension."""

    member_id: int
    name: str
    parent_member_id: int | None = None
    classification_code: str | None = None
    # Terminated members are historical; kept for provenance but flagged.
    terminated: bool = False


@dataclass(frozen=True)
class Dimension:
    """A cube dimension with its ordered members."""

    dimension_position_id: int
    name: str
    members: list[DimensionMember] = field(default_factory=list)

    def has_geography_semantics(self) -> bool:
        """Heuristic: is this the geography dimension?"""
        return self.name.strip().lower() in {"geography", "géographie"}


@dataclass(frozen=True)
class CubeMetadata:
    """Parsed ``getCubeMetadata`` response for one product."""

    product_id: int
    cube_title: str
    frequency_code: int | None
    period_type: PeriodType | None
    start_date: date | None
    end_date: date | None
    release_time: datetime | None
    dimensions: list[Dimension]
    # The full, unmodified payload for archival in SourceMetadata.
    raw_payload: dict

    @property
    def dimension_count(self) -> int:
        return len(self.dimensions)

    @property
    def member_count(self) -> int:
        return sum(len(d.members) for d in self.dimensions)

    def dimension_by_name(self, *names: str) -> Dimension | None:
        """Return the first dimension whose name matches any of ``names`` (ci)."""
        wanted = {n.strip().lower() for n in names}
        for dim in self.dimensions:
            if dim.name.strip().lower() in wanted:
                return dim
        return None


@dataclass(frozen=True)
class Observation:
    """A single normalized observation parsed from a full-table download.

    Original StatCan identifiers are always retained (coordinate, ref period
    string, status/symbol codes) so provenance is never lost.
    """

    product_id: int
    coordinate: str
    # Resolved member names for each classifying dimension.
    geography: str
    industry: str
    measure: str
    unit: str
    # Normalized period.
    period_start: date
    period_label: str
    period_type: PeriodType
    # Value is None when suppressed / not available (never imputed).
    value: float | None
    # Original identifiers.
    ref_period_raw: str
    vector_id: int | None = None
    status_code: str | None = None
    symbol_code: str | None = None
    scalar_factor_code: int | None = None
