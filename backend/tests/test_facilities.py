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


def test_mapping_uses_nfhs_geography_and_reporting_flags():
    facility = map_facility(BASE_ROW, "ICU")

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
    mock_query.return_value = [BASE_ROW]

    results = list_facilities("ICU", "Bangalore", "Karnataka")

    sql_text, params = mock_query.call_args.args
    assert "CAST(capability AS STRING)" in sql_text
    assert "LOWER(nfhs_district_name) = ?" in sql_text
    assert "LOWER(nfhs_state_ut) = ?" in sql_text
    assert params == ["%icu%", "bangalore", "karnataka"]
    assert results[0].facility_id == "facility-123"


@patch("backend.services.facilities.query")
def test_single_facility_uses_unique_id_parameter(mock_query):
    mock_query.return_value = [BASE_ROW]

    facility = get_facility("facility-123")

    assert mock_query.call_args.args[1] == ["facility-123"]
    assert facility is not None
    assert facility.unique_id == "facility-123"
