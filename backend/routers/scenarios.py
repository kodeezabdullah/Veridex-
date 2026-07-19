"""Temporary scenario stubs pending Lakebase or Supabase persistence."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter

from backend.models import Scenario, ScenarioCreate

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])

_SCENARIOS = [
    Scenario(
        scenario_id="s_mock_001",
        name="Karnataka ICU evidence review",
        shortlist=[],
        notes=[],
        overrides=[],
        created_at="2026-07-19T09:00:00Z",
    )
]


@router.get("", response_model=list[Scenario])
def get_scenarios() -> list[Scenario]:
    # TEMPORARY IN-MEMORY MOCK — replace behind this contract when persistence is ready.
    return _SCENARIOS


@router.post("", response_model=Scenario, status_code=201)
def create_scenario(payload: ScenarioCreate) -> Scenario:
    scenario = Scenario(
        scenario_id=f"s_{uuid4().hex[:12]}",
        name=payload.name,
        created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    _SCENARIOS.insert(0, scenario)
    return scenario
