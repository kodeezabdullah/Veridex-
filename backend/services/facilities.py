"""Databricks facility and capability-evidence queries."""

from __future__ import annotations

import ast
import json
from typing import Any

from backend.db import query
from backend.models import (
    CapabilityEvidence,
    DataCompleteness,
    FacilityLocation,
    FacilityResponse,
    RawFacilityFields,
)

FACILITIES_TABLE = "veridex.gold.facilities_clean"
CAPABILITY_EVIDENCE_TABLE = "veridex.gold.capability_evidence"
TAVILY_CAPABILITIES = {"ICU", "NICU", "Trauma", "Oncology"}
TAVILY_STATUSES = {"verified", "likely"}


def _run_validators(row: dict[str, Any]) -> list[dict[str, str]]:
    from backend.agents.validator import run_all_validators

    return run_all_validators(row)


def _generate_explanation(
    row: dict[str, Any], flags: list[dict[str, str]]
) -> dict[str, Any]:
    from backend.agents.explanation_agent import generate_explanation

    return generate_explanation(row, flags)


def _check_tavily(
    facility_name: str, city: str, source_urls: list[str]
) -> dict[str, Any]:
    from backend.agents.tavily_check import (
        check_facility_digital_footprint,
        register_facility_source_urls,
    )

    register_facility_source_urls(facility_name, city, source_urls)
    return check_facility_digital_footprint(facility_name, city)


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


def _clean_text(value: Any) -> str | None:
    cleaned = str(value).strip() if value is not None else ""
    return cleaned or None


def _evidence_from_row(
    row: dict[str, Any], *, prefixed: bool = False
) -> CapabilityEvidence:
    prefix = "evidence_" if prefixed else ""
    return CapabilityEvidence(
        unique_id=str(row[f"{prefix}unique_id"]),
        capability=str(row[f"{prefix}capability"]),
        evidence_status=str(row[f"{prefix}evidence_status"]),
        trust_score=float(row[f"{prefix}trust_score"]),
        trust_score_pct=int(row[f"{prefix}trust_score_pct"]),
        field_source=_clean_text(row.get(f"{prefix}field_source")),
        text_span=_clean_text(row.get(f"{prefix}text_span")),
        confirm_message=str(row[f"{prefix}confirm_message"]),
    )


def _source_urls(raw_urls: Any) -> list[str]:
    if isinstance(raw_urls, (list, tuple)):
        return [str(value).strip() for value in raw_urls if str(value).strip()]
    if not isinstance(raw_urls, str) or not raw_urls.strip():
        return []
    try:
        parsed = json.loads(raw_urls)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(raw_urls)
        except (ValueError, SyntaxError):
            parsed = [raw_urls]
    if isinstance(parsed, (list, tuple)):
        return [str(value).strip() for value in parsed if str(value).strip()]
    return [str(parsed).strip()] if str(parsed).strip() else []


def map_facility(
    row: dict[str, Any],
    evidence_rows: list[dict[str, Any]] | None = None,
) -> FacilityResponse:
    unique_id = str(_first(row, "unique_id", "facility_id", "id") or "")
    coordinates_valid = _as_bool(row.get("coordinates_valid"))
    district_resolved = _as_bool(row.get("district_resolved"))
    capacity_reported = _as_bool(row.get("capacity_reported"))
    doctors_reported = _as_bool(row.get("doctors_reported"))
    if evidence_rows is None:
        evidence = (
            [_evidence_from_row(row, prefixed=True)]
            if row.get("evidence_unique_id") is not None
            else []
        )
    else:
        evidence = [_evidence_from_row(item) for item in evidence_rows]

    return FacilityResponse(
        facility_id=unique_id,
        unique_id=unique_id,
        name=str(
            _first(row, "facility_name", "name", "facilityName", "hospital_name")
            or "Unnamed facility"
        ),
        location=FacilityLocation(
            state=_clean_text(_first(row, "nfhs_state_ut")),
            district=_clean_text(_first(row, "nfhs_district_name")),
            city=None,
            pin=_clean_text(
                _first(row, "address_postalCode", "postal_code", "pin")
            ),
            lat=_as_float(row.get("latitude")) if coordinates_valid else None,
            lon=_as_float(row.get("longitude")) if coordinates_valid else None,
            unresolved=not district_resolved,
        ),
        capability_evidence=evidence,
        raw_fields=RawFacilityFields(
            description=_first(row, "description", "description_clean"),
            procedure=_first(row, "procedure", "procedure_clean"),
            equipment=_first(row, "equipment", "equipment_clean"),
            numberDoctors=_as_int(row.get("numberDoctors_clean"))
            if doctors_reported
            else None,
            capacity=_as_int(row.get("capacity_clean"))
            if capacity_reported
            else None,
            yearEstablished=_clean_text(
                _first(row, "yearEstablished_clean", "yearEstablished")
            ),
        ),
        data_completeness=DataCompleteness(
            capacity_reported=capacity_reported,
            doctors_reported=doctors_reported,
        ),
    )


def list_facilities(
    capability: str | None, district: str | None, state: str | None
) -> list[FacilityResponse]:
    conditions: list[str] = []
    params: list[str] = []
    join = ""
    evidence_columns = ""
    if capability:
        join = (
            f" INNER JOIN {CAPABILITY_EVIDENCE_TABLE} AS evidence"
            " ON evidence.unique_id = facility.unique_id"
        )
        conditions.append(
            "LOWER(TRIM(evidence.capability)) = LOWER(TRIM(?))"
        )
        params.append(capability)
        evidence_columns = """,
            evidence.unique_id AS evidence_unique_id,
            evidence.capability AS evidence_capability,
            evidence.evidence_status AS evidence_evidence_status,
            evidence.trust_score AS evidence_trust_score,
            evidence.trust_score_pct AS evidence_trust_score_pct,
            evidence.field_source AS evidence_field_source,
            evidence.text_span AS evidence_text_span,
            evidence.confirm_message AS evidence_confirm_message"""
    if district:
        conditions.append(
            "LOWER(TRIM(facility.nfhs_district_name)) = LOWER(TRIM(?))"
        )
        params.append(district)
    if state:
        conditions.append(
            "LOWER(TRIM(facility.nfhs_state_ut)) = LOWER(TRIM(?))"
        )
        params.append(state)
    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = query(
        f"SELECT facility.*{evidence_columns} FROM {FACILITIES_TABLE} AS facility"
        f"{join}{where_clause} ORDER BY facility.name LIMIT 500",
        params,
    )
    return [map_facility(row) for row in rows]


def _agent_row(
    facility: dict[str, Any], evidence: dict[str, Any]
) -> dict[str, Any]:
    return {
        **evidence,
        "doctors_reported": _as_bool(facility.get("doctors_reported")),
        "capacity_reported": _as_bool(facility.get("capacity_reported")),
        "source_type_count": _as_int(facility.get("source_type_count")) or 0,
        "affiliated_staff_presence": _as_bool(
            facility.get("affiliated_staff_presence")
        ),
        "custom_logo_presence": _as_bool(facility.get("custom_logo_presence")),
        "number_of_facts_about_the_organization": _as_int(
            facility.get("number_of_facts_about_the_organization")
        )
        or 0,
        "coordinates_valid": _as_bool(facility.get("coordinates_valid")),
        "district_resolved": _as_bool(facility.get("district_resolved")),
    }


def get_facility(
    unique_id: str, viewed_capability: str | None = None
) -> FacilityResponse | None:
    facilities = query(
        f"SELECT * FROM {FACILITIES_TABLE} WHERE unique_id = ? LIMIT 1",
        [unique_id],
    )
    if not facilities:
        return None
    facility = facilities[0]
    evidence_rows = query(
        f"""
        SELECT *
        FROM {CAPABILITY_EVIDENCE_TABLE}
        WHERE unique_id = ?
        ORDER BY capability
        """,
        [unique_id],
    )
    result = map_facility(facility, evidence_rows)

    selected = next(
        (
            row
            for row in evidence_rows
            if viewed_capability
            and str(row.get("capability", "")).casefold()
            == viewed_capability.strip().casefold()
        ),
        None,
    )
    if selected is None:
        return result

    agent_row = _agent_row(facility, selected)
    flags = _run_validators(agent_row)
    result.viewed_capability = str(selected["capability"])
    result.validator_flags = flags
    result.explanation = _generate_explanation(agent_row, flags)

    tavily_eligible = (
        result.viewed_capability in TAVILY_CAPABILITIES
        and selected["evidence_status"] in TAVILY_STATUSES
    )
    result.tavily_eligible = tavily_eligible
    if tavily_eligible:
        facility_name = result.name
        city = _clean_text(facility.get("address_city")) or ""
        result.tavily_result = _check_tavily(
            facility_name,
            city,
            _source_urls(facility.get("source_urls")),
        )
    return result
