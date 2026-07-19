"""Stable API response models shared by real and mocked endpoints."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class FacilityLocation(BaseModel):
    state: str | None
    district: str | None
    city: str | None = None
    pin: str | None = None
    lat: float | None = None
    lon: float | None = None
    unresolved: bool = False


class CapabilityEvidence(BaseModel):
    unique_id: str
    capability: str
    evidence_status: Literal["verified", "likely", "weak_signal", "no_signal"]
    trust_score: float = Field(ge=0, le=1)
    trust_score_pct: int = Field(ge=0, le=100)
    field_source: str | None
    text_span: str | None
    confirm_message: str


class RawFacilityFields(BaseModel):
    description: str | None = None
    procedure: str | None = None
    equipment: str | None = None
    numberDoctors: int | None = None
    capacity: int | None = None
    yearEstablished: str | None = None


class DataCompleteness(BaseModel):
    capacity_reported: bool
    doctors_reported: bool


class FacilityResponse(BaseModel):
    facility_id: str
    unique_id: str
    name: str
    location: FacilityLocation
    capability_evidence: list[CapabilityEvidence]
    raw_fields: RawFacilityFields
    data_completeness: DataCompleteness
    viewed_capability: str | None = None
    validator_flags: list[dict[str, str]] = Field(default_factory=list)
    explanation: dict[str, Any] | None = None
    tavily_eligible: bool = False
    tavily_result: dict[str, Any] | None = None


class RegionCoverage(BaseModel):
    region_id: str
    region_name: str
    state: str
    level: Literal["district"] = "district"
    capability_queried: str
    coverage_status: Literal["verified_coverage", "weak_coverage", "no_facility", "no_data"]
    facility_count: int
    avg_trust_score_pct: int = Field(ge=0, le=100)


class ScenarioNote(BaseModel):
    facility_id: str
    note: str
    timestamp: str


class Scenario(BaseModel):
    scenario_id: str
    name: str
    shortlist: list[str] = Field(default_factory=list)
    notes: list[ScenarioNote] = Field(default_factory=list)
    overrides: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str
    updated_at: str | None = None


class ScenarioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ScenarioNoteCreate(BaseModel):
    facility_unique_id: str = Field(min_length=1)
    note_text: str = Field(min_length=1, max_length=4000)


class ScenarioShortlistCreate(BaseModel):
    facility_unique_id: str = Field(min_length=1)
