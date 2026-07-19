"""Real district coverage endpoint backed by Databricks aggregation."""

import logging

from fastapi import APIRouter, HTTPException, Query

from backend.db import DatabricksConfigurationError
from backend.models import RegionCoverage
from backend.services.coverage import list_region_coverage

router = APIRouter(prefix="/api", tags=["coverage"])
logger = logging.getLogger(__name__)


@router.get("/regions/coverage", response_model=list[RegionCoverage])
def region_coverage(
    capability: str = Query(default="ICU", min_length=1),
    state: str | None = Query(default=None, min_length=1),
    district: str | None = Query(default=None, min_length=1),
) -> list[RegionCoverage]:
    try:
        return list_region_coverage(capability, state, district)
    except DatabricksConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        logger.exception("Databricks region coverage query failed")
        raise HTTPException(
            status_code=503,
            detail=(
                "Region coverage data is unavailable. Verify that "
                "veridex.gold.region_coverage exists and is accessible."
            ),
        ) from error
