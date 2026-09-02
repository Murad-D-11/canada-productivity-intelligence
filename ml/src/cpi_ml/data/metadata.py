"""Metadata discovery (Milestone 2).

Discovers a cube's dimensions, members, geography, measures, frequency,
coverage, and units from ``getCubeMetadata`` and persists them to PostgreSQL.
Industry names are discovered from the source — never hardcoded.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from sqlalchemy.engine import Connection

from cpi_ml.data.repository import StatCanRepository
from cpi_ml.data.schemas import CubeMetadata, Dimension

logger = logging.getLogger("cpi_ml.data.metadata")

# Case-insensitive dimension-name hints. The productivity cube uses these exact
# dimension names; we match on them but fall back to positional roles if the
# names differ, so we never hardcode member VALUES.
GEOGRAPHY_NAMES = ("geography", "géographie")
INDUSTRY_NAMES = (
    "north american industry classification system (naics)",
    "industry",
)
MEASURE_NAMES = (
    "labour productivity measures and related variables",
    "labour productivity measures and related variables ",
)


@dataclass(frozen=True)
class DimensionRoles:
    """Resolved dimension roles for a cube."""

    geography: Dimension
    industry: Dimension
    measure: Dimension


def resolve_dimension_roles(metadata: CubeMetadata) -> DimensionRoles:
    """Identify which dimensions are geography / industry / measure.

    Uses name hints first; if a role can't be matched by name, falls back to a
    positional heuristic (geography usually position 1). Raises if the cube does
    not have the expected three-dimension productivity structure.
    """
    geography = metadata.dimension_by_name(*GEOGRAPHY_NAMES)
    industry = metadata.dimension_by_name(*INDUSTRY_NAMES)
    measure = metadata.dimension_by_name(*MEASURE_NAMES)

    dims = list(metadata.dimensions)
    if geography is None and dims:
        geography = dims[0]
    if measure is None:
        measure = next(
            (d for d in dims if d is not geography and "productivity" in d.name.lower()),
            None,
        )
    if industry is None:
        industry = next(
            (d for d in dims if d is not geography and d is not measure),
            None,
        )

    if not (geography and industry and measure):
        raise ValueError(
            "Could not resolve geography/industry/measure dimensions from cube metadata; "
            f"found dimensions: {[d.name for d in dims]}"
        )
    return DimensionRoles(geography=geography, industry=industry, measure=measure)


def store_metadata(
    conn: Connection,
    repo: StatCanRepository,
    metadata: CubeMetadata,
    *,
    table_ref: str | None,
) -> tuple[str, DimensionRoles, dict[int, str], dict[int, str], dict[int, str]]:
    """Persist dataset + members. Returns lookup maps for the ETL to reuse.

    Returns
    -------
    (dataset_id, roles, geo_map, industry_map, measure_map)
        where each ``*_map`` maps StatCan memberId -> our row id.
    """
    roles = resolve_dimension_roles(metadata)

    dataset_id = repo.upsert_dataset(
        conn,
        product_id=metadata.product_id,
        title=metadata.cube_title,
        table_ref=table_ref,
        frequency_code=metadata.frequency_code,
        frequency=metadata.period_type.value if metadata.period_type else None,
        start_date=metadata.start_date,
        end_date=metadata.end_date,
        release_time=metadata.release_time,
    )

    geo_map: dict[int, str] = {}
    for m in roles.geography.members:
        geo_map[m.member_id] = repo.upsert_member(
            conn, table="StatCanGeography", dataset_id=dataset_id,
            member_id=m.member_id, name=m.name, classification_code=m.classification_code,
        )

    industry_map: dict[int, str] = {}
    for m in roles.industry.members:
        industry_map[m.member_id] = repo.upsert_member(
            conn, table="StatCanIndustry", dataset_id=dataset_id,
            member_id=m.member_id, name=m.name, classification_code=m.classification_code,
            parent_member_id=m.parent_member_id,
        )

    measure_map: dict[int, str] = {}
    for m in roles.measure.members:
        measure_map[m.member_id] = repo.upsert_member(
            conn, table="StatCanMeasure", dataset_id=dataset_id,
            member_id=m.member_id, name=m.name,
        )

    repo.save_source_metadata(
        conn,
        dataset_id=dataset_id,
        source_method="getCubeMetadata",
        payload_json=json.dumps(metadata.raw_payload),
        dimension_count=metadata.dimension_count,
        member_count=metadata.member_count,
    )

    logger.info(
        "stored metadata: %d geographies, %d industries, %d measures",
        len(geo_map), len(industry_map), len(measure_map),
    )
    return dataset_id, roles, geo_map, industry_map, measure_map
