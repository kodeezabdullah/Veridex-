import logging

from fastapi import APIRouter, HTTPException

from backend.db import DatabricksConfigurationError
from backend.services.validation import system_validation_summary

router = APIRouter(prefix="/api", tags=["validation"])
logger = logging.getLogger(__name__)


@router.get("/validation/summary")
def validation_summary() -> dict:
    try:
        return system_validation_summary()
    except DatabricksConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        logger.exception("Validation summary query failed")
        raise HTTPException(status_code=503, detail="Validation metrics are unavailable from the live evidence tables.") from error
