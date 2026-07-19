"""Databricks-backed district coverage queries."""

from __future__ import annotations

from backend.db import query
from backend.models import RegionCoverage

REGION_COVERAGE_TABLE = "veridex.gold.region_coverage"


def list_region_coverage(
    capability: str,
    state: str | None = None,
    district: str | None = None,
) -> list[RegionCoverage]:
    conditions = ["LOWER(TRIM(capability_queried)) = LOWER(TRIM(?))"]
    params = [capability]

    if state:
        conditions.append("LOWER(TRIM(state)) = LOWER(TRIM(?))")
        params.append(state)
    if district:
        conditions.append("LOWER(TRIM(region_name)) = LOWER(TRIM(?))")
        params.append(district)

    rows = query(
        f"""
        SELECT
            region_id,
            TRIM(region_name) AS region_name,
            TRIM(state) AS state,
            'district' AS level,
            capability_queried,
            coverage_status,
            facility_count,
            CAST(ROUND(COALESCE(avg_trust_score_pct, 0)) AS INT)
                AS avg_trust_score_pct
        FROM {REGION_COVERAGE_TABLE}
        WHERE {' AND '.join(conditions)}
        ORDER BY state, region_name
        """,
        params,
    )
    return [RegionCoverage.model_validate(row) for row in rows]
