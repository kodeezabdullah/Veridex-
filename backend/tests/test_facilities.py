from unittest.mock import patch

from backend.services.facilities import get_facility, list_facilities, map_facility


BASE_ROW = {
    "unique_id": "facility-123",
    "facility_name": "District Hospital",
    "nfhs_state_ut": "Karnataka",
    "nfhs_district_name": "Bangalore",
    "address_city": "CORRUPTED CITY",
    "address_stateOrRegion": "CORRUPTED STATE",
    "latitude": 12.97,
    "longitude": 77.59,
    "coordinates_valid": True,
    "district_resolved": True,
    "capability": ["ICU", "Emergency"],
    "description": "A 10-bed ICU with ventilator support is listed.",
    "procedure": "Emergency stabilisation",
    "equipment": "Ventilators",
    "numberDoctors_clean": 42,
    "capacity_clean": 180,
    "doctors_reported": False,
    "capacity_reported": True,
}

EVIDENCE_ROW = {
    "unique_id": "facility-123",
    "capability": "ICU",
    "evidence_status": "verified",
    "trust_score": 0.82,
    "trust_score_pct": 82,
    "field_source": "description",
    "text_span": "A 10-bed ICU with ventilator support is listed.",
    "confirm_message": "Confirm directly with the facility.",
}


def test_mapping_uses_nfhs_geography_and_reporting_flags():
    facility = map_facility(
        {**BASE_ROW, "nfhs_state_ut": " Karnataka ", "nfhs_district_name": " Bangalore "},
        [EVIDENCE_ROW],
    )

    assert facility.location.state == "Karnataka"
    assert facility.location.district == "Bangalore"
    assert facility.location.city is None
    assert facility.location.lat == 12.97
    assert facility.raw_fields.numberDoctors is None
    assert facility.raw_fields.capacity == 180
    assert facility.capability_evidence[0].capability == "ICU"
    assert 0 <= facility.capability_evidence[0].trust_score_pct <= 100


def test_invalid_coordinates_and_unresolved_district_are_explicit():
    facility = map_facility({**BASE_ROW, "coordinates_valid": False, "district_resolved": False})

    assert facility.location.lat is None
    assert facility.location.lon is None
    assert facility.location.unresolved is True


@patch("backend.services.facilities.query")
def test_list_query_uses_parameterized_capability_and_nfhs_filters(mock_query):
    mock_query.return_value = [
        {
            **BASE_ROW,
            **{f"evidence_{key}": value for key, value in EVIDENCE_ROW.items()},
        }
    ]

    results = list_facilities("ICU", "Bangalore", "Karnataka")

    sql_text, params = mock_query.call_args.args
    assert "INNER JOIN veridex.gold.capability_evidence" in sql_text
    assert "LOWER(TRIM(evidence.capability)) = LOWER(TRIM(?))" in sql_text
    assert "LOWER(TRIM(facility.nfhs_district_name)) = LOWER(TRIM(?))" in sql_text
    assert "LOWER(TRIM(facility.nfhs_state_ut)) = LOWER(TRIM(?))" in sql_text
    assert params == ["ICU", "Bangalore", "Karnataka"]
    assert results[0].facility_id == "facility-123"


@patch("backend.services.facilities.query")
def test_single_facility_uses_unique_id_parameter(mock_query):
    mock_query.side_effect = [[BASE_ROW], [EVIDENCE_ROW]]

    facility = get_facility("facility-123")

    assert mock_query.call_args_list[0].args[1] == ["facility-123"]
    assert mock_query.call_args_list[1].args[1] == ["facility-123"]
    assert facility is not None
    assert facility.unique_id == "facility-123"


@patch("backend.services.facilities._check_tavily")
@patch("backend.services.facilities._generate_explanation")
@patch("backend.services.facilities._run_validators", return_value=[])
@patch("backend.services.facilities.query")
def test_high_acuity_verified_detail_runs_tavily_gate(
    mock_query, _validators, explanation, tavily
):
    mock_query.side_effect = [[BASE_ROW], [EVIDENCE_ROW]]
    explanation.return_value = {"ok": True, "explanation": "Verified."}
    tavily.return_value = {"status": "independently_corroborated"}

    facility = get_facility("facility-123", "ICU")

    assert facility is not None
    assert facility.tavily_eligible is True
    tavily.assert_called_once()


@patch("backend.services.facilities._check_tavily")
@patch("backend.services.facilities._generate_explanation")
@patch("backend.services.facilities._run_validators", return_value=[])
@patch("backend.services.facilities.query")
def test_noneligible_detail_does_not_call_tavily(
    mock_query, _validators, explanation, tavily
):
    weak_emergency = {
        **EVIDENCE_ROW,
        "capability": "Emergency",
        "evidence_status": "weak_signal",
        "trust_score": 0.6,
        "trust_score_pct": 60,
    }
    mock_query.side_effect = [[BASE_ROW], [weak_emergency]]
    explanation.return_value = {"ok": True, "explanation": "Limited evidence."}

    facility = get_facility("facility-123", "Emergency")

    assert facility is not None
    assert facility.tavily_eligible is False
    tavily.assert_not_called()
