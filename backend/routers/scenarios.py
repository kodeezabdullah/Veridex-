"""Lakebase-backed scenario endpoints."""

import logging

from fastapi import APIRouter, HTTPException

from backend.lakebase import LakebaseConfigurationError
from backend.models import (
    Scenario,
    ScenarioCreate,
    ScenarioNoteCreate,
    ScenarioShortlistCreate,
)
from backend.services.scenarios import (
    add_note,
    add_shortlist_item,
    create_scenario as persist_scenario,
    list_scenarios,
)

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])
logger = logging.getLogger(__name__)


def _unavailable(error: Exception) -> HTTPException:
    if isinstance(error, LakebaseConfigurationError):
        return HTTPException(status_code=503, detail=str(error))
    logger.exception("Lakebase scenario operation failed")
    return HTTPException(status_code=503, detail="Lakebase persistence is unavailable.")


@router.get("", response_model=list[Scenario])
def get_scenarios() -> list[Scenario]:
    try:
        return list_scenarios()
    except Exception as error:
        raise _unavailable(error) from error


@router.post("", response_model=Scenario, status_code=201)
def create_scenario(payload: ScenarioCreate) -> Scenario:
    try:
        return persist_scenario(payload.name)
    except Exception as error:
        raise _unavailable(error) from error


@router.post("/{scenario_id}/notes", response_model=Scenario)
def create_note(scenario_id: str, payload: ScenarioNoteCreate) -> Scenario:
    try:
        result = add_note(scenario_id, payload.facility_unique_id, payload.note_text)
    except Exception as error:
        raise _unavailable(error) from error
    if result is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return result


@router.post("/{scenario_id}/shortlist", response_model=Scenario)
def create_shortlist_item(
    scenario_id: str, payload: ScenarioShortlistCreate
) -> Scenario:
    try:
        result = add_shortlist_item(scenario_id, payload.facility_unique_id)
    except Exception as error:
        raise _unavailable(error) from error
    if result is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return result
