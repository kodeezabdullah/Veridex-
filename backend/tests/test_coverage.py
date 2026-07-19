from unittest.mock import patch

from backend.services.coverage import list_region_coverage


@patch("backend.services.coverage.query")
def test_coverage_query_is_parameterized_and_preserves_contract(mock_query):
    mock_query.return_value = [
        {
            "region_id": "Bangalore_Karnataka",
            "region_name": "Bangalore",
            "state": "Karnataka",
            "level": "district",
            "capability_queried": "ICU",
            "coverage_status": "verified_coverage",
            "facility_count": 14,
            "avg_trust_score_pct": 78,
        }
    ]

    results = list_region_coverage("ICU", "Karnataka", "Bangalore")

    sql_text, params = mock_query.call_args.args
    assert "veridex.gold.region_coverage" in sql_text
    assert "LOWER(TRIM(state)) = LOWER(TRIM(?))" in sql_text
    assert "LOWER(TRIM(region_name)) = LOWER(TRIM(?))" in sql_text
    assert params == ["ICU", "Karnataka", "Bangalore"]
    assert results[0].avg_trust_score_pct == 78


@patch("backend.services.coverage.query", return_value=[])
def test_coverage_query_returns_clean_empty_result(_mock_query):
    assert list_region_coverage("ICU") == []
