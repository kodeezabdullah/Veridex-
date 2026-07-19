"""Real facility endpoints backed by the Databricks gold table."""

import logging

from fastapi import APIRouter, HTTPException, Query

from backend.db import DatabricksConfigurationError
from backend.models import FacilityResponse
from backend.services.facilities import get_facility, list_facilities

router = APIRouter(prefix="/api", tags=["facilities"])
logger = logging.getLogger(__name__)


def _service_unavailable(error: Exception) -> HTTPException:
    if isinstance(error, DatabricksConfigurationError):
        return HTTPException(status_code=503, detail=str(error))
    logger.exception("Databricks facility query failed")
    return HTTPException(status_code=502, detail="The Databricks facility query failed. Check service connectivity and logs.")


@router.get("/facilities", response_model=list[FacilityResponse])
def facilities(
    capability: str | None = Query(default=None, min_length=1),
    district: str | None = Query(default=None, min_length=1),
    state: str | None = Query(default=None, min_length=1),
) -> list[FacilityResponse]:
    try:
        return list_facilities(capability, district, state)
    except Exception as error:
        raise _service_unavailable(error) from error


@router.get("/facility/{unique_id}", response_model=FacilityResponse)
def facility(
    unique_id: str,
    capability: str | None = Query(default=None, min_length=1),
) -> FacilityResponse:
    try:
        result = get_facility(unique_id, capability)
    except Exception as error:
        raise _service_unavailable(error) from error
    if result is None:
        raise HTTPException(status_code=404, detail="Facility not found")
    return result
