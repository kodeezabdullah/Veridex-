"""Databricks facility queries and contract mapping."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from backend.db import query
from backend.models import (
    CapabilityClaim,
    CapabilityEvidence,
    DataCompleteness,
    EvidenceSnippet,
    FacilityLocation,
    FacilityResponse,
    RawFacilityFields,
)

FACILITIES_TABLE = "veridex.gold.facilities_clean"


def _first(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None and value != "":
            return value
    return None


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _as_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    try:
        return int(float(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def _capability_names(raw: Any, requested: str | None) -> list[str]:
    if requested:
        return [requested]
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        return [str(item).strip() for item in raw if str(item).strip()]
    text = str(raw).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass
    return [item.strip(" []'\"") for item in re.split(r"[,;|]", text) if item.strip(" []'\"")]


def mock_capability_evidence(row: dict[str, Any], capability: str) -> CapabilityEvidence:
    """TEMPORARY MOCK until Muhammad's capability_evidence table is available."""
    unique_id = str(_first(row, "unique_id", "facility_id", "id") or "unknown")
    sources = (
        ("description", _first(row, "description", "description_clean")),
        ("procedure", _first(row, "procedure", "procedure_clean")),
        ("equipment", _first(row, "equipment", "equipment_clean")),
    )
    field_source, source_text = next(
        ((field, str(text)) for field, text in sources if text and capability.lower() in str(text).lower()),
        next(((field, str(text)) for field, text in sources if text), (None, None)),
    )
    if source_text is None:
        status = "no_signal"
        score_pct = 0
    else:
        digest = hashlib.sha256(f"{unique_id}:{capability}".encode()).digest()[0]
        score_pct = 45 + digest % 44
        status = "verified" if score_pct >= 80 else "likely" if score_pct >= 65 else "weak_signal"

    messages = {
        "verified": "Verified capability evidence is available.",
        "likely": "Capability evidence is likely; confirm against the source record.",
        "weak_signal": "Only a weak capability signal is available; manual confirmation is recommended.",
        "no_signal": "No capability evidence signal is currently available.",
    }
    return CapabilityEvidence(
        unique_id=unique_id,
        capability=capability,
        evidence_status=status,
        trust_score=score_pct / 100,
        trust_score_pct=score_pct,
        field_source=field_source,
        text_span=source_text[:220] if source_text else None,
        confirm_message=messages[status],
    )


def _claim_from_evidence(evidence: CapabilityEvidence) -> CapabilityClaim:
    status = "verified" if evidence.evidence_status == "verified" else "no-signal" if evidence.evidence_status == "no_signal" else "claimed-only"
    confidence = "high" if evidence.trust_score_pct >= 80 else "medium" if evidence.trust_score_pct >= 60 else "low"
    snippets = [] if evidence.text_span is None else [EvidenceSnippet(
        field=evidence.field_source or "unknown",
        text_span=evidence.text_span,
        type="corroborating" if status == "verified" else "claim",
    )]
    return CapabilityClaim(
        name=evidence.capability,
        status=status,
        trust_score=evidence.trust_score,
        confidence_level=confidence,
        evidence=snippets,
    )


def map_facility(row: dict[str, Any], requested_capability: str | None = None) -> FacilityResponse:
    unique_id = str(_first(row, "unique_id", "facility_id", "id") or "")
    coordinates_valid = _as_bool(row.get("coordinates_valid"))
    district_resolved = _as_bool(row.get("district_resolved"))
    capacity_reported = _as_bool(row.get("capacity_reported"))
    doctors_reported = _as_bool(row.get("doctors_reported"))
    capabilities = _capability_names(_first(row, "capability", "capabilities"), requested_capability)
    evidence = [mock_capability_evidence(row, capability) for capability in capabilities]

    return FacilityResponse(
        facility_id=unique_id,
        unique_id=unique_id,
        name=str(_first(row, "facility_name", "name", "facilityName", "hospital_name") or "Unnamed facility"),
        location=FacilityLocation(
            state=_first(row, "nfhs_state_ut"),
            district=_first(row, "nfhs_district_name"),
            city=None,
            pin=str(_first(row, "address_postalCode", "postal_code", "pin") or "") or None,
            lat=_as_float(row.get("latitude")) if coordinates_valid else None,
            lon=_as_float(row.get("longitude")) if coordinates_valid else None,
            unresolved=not district_resolved,
        ),
        capabilities=[_claim_from_evidence(item) for item in evidence],
        capability_evidence=evidence,
        raw_fields=RawFacilityFields(
            description=_first(row, "description", "description_clean"),
            procedure=_first(row, "procedure", "procedure_clean"),
            equipment=_first(row, "equipment", "equipment_clean"),
            numberDoctors=_as_int(row.get("numberDoctors_clean")) if doctors_reported else None,
            capacity=_as_int(row.get("capacity_clean")) if capacity_reported else None,
            yearEstablished=str(_first(row, "yearEstablished_clean", "yearEstablished") or "") or None,
        ),
        data_completeness=DataCompleteness(
            capacity_reported=capacity_reported,
            doctors_reported=doctors_reported,
        ),
    )


def list_facilities(capability: str | None, district: str | None, state: str | None) -> list[FacilityResponse]:
    conditions: list[str] = []
    params: list[str] = []
    if capability:
        conditions.append("LOWER(CAST(capability AS STRING)) LIKE ?")
        params.append(f"%{capability.lower()}%")
    if district:
        conditions.append("LOWER(nfhs_district_name) = ?")
        params.append(district.lower())
    if state:
        conditions.append("LOWER(nfhs_state_ut) = ?")
        params.append(state.lower())
    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = query(f"SELECT * FROM {FACILITIES_TABLE}{where_clause} LIMIT 500", params)
    return [map_facility(row, capability) for row in rows]


def get_facility(unique_id: str) -> FacilityResponse | None:
    rows = query(f"SELECT * FROM {FACILITIES_TABLE} WHERE unique_id = ? LIMIT 1", [unique_id])
    return map_facility(rows[0]) if rows else None
