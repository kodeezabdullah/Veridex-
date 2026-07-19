"""Temporary district coverage mock pending Muhammad's aggregation table."""

from fastapi import APIRouter, Query

from backend.models import RegionCoverage

router = APIRouter(prefix="/api", tags=["coverage"])


@router.get("/regions/coverage", response_model=list[RegionCoverage])
def region_coverage(capability: str = Query(default="ICU", min_length=1)) -> list[RegionCoverage]:
    # TEMPORARY MOCK — DO NOT REMOVE UNTIL capability_evidence + district aggregation exist.
    return [
        RegionCoverage(region_id="Bangalore", region_name="Bangalore", state="Karnataka", capability_queried=capability, coverage_status="verified_coverage", facility_count=14, avg_trust_score=0.78),
        RegionCoverage(region_id="Mysore", region_name="Mysore", state="Karnataka", capability_queried=capability, coverage_status="weak_coverage", facility_count=5, avg_trust_score=0.53),
        RegionCoverage(region_id="Kolar", region_name="Kolar", state="Karnataka", capability_queried=capability, coverage_status="no_facility", facility_count=0, avg_trust_score=0),
        RegionCoverage(region_id="Kodagu", region_name="Kodagu", state="Karnataka", capability_queried=capability, coverage_status="no_data", facility_count=0, avg_trust_score=0),
    ]
