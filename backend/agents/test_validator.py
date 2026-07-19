from validator import (
    check_geography_unresolved,
    check_low_legitimacy_signals,
    check_single_source_high_acuity,
    check_unsupported_claim,
    check_unverified_location,
    run_all_validators,
)


def test_unsupported_claim_should_trigger():
    row = {
        "evidence_status": "verified",
        "doctors_reported": False,
        "capacity_reported": False,
    }
    assert check_unsupported_claim(row)[0] is True


def test_unsupported_claim_should_not_trigger():
    row = {
        "evidence_status": "likely",
        "doctors_reported": True,
        "capacity_reported": False,
    }
    assert check_unsupported_claim(row)[0] is False


def test_single_source_high_acuity_should_trigger():
    row = {
        "capability": "ICU",
        "evidence_status": "likely",
        "source_type_count": 1,
    }
    assert check_single_source_high_acuity(row)[0] is True


def test_single_source_high_acuity_should_not_trigger():
    row = {
        "capability": "Oncology",
        "evidence_status": "verified",
        "source_type_count": 2,
    }
    assert check_single_source_high_acuity(row)[0] is False


def test_low_legitimacy_signals_should_trigger():
    row = {
        "evidence_status": "verified",
        "affiliated_staff_presence": False,
        "custom_logo_presence": False,
        "number_of_facts_about_the_organization": 2,
    }
    assert check_low_legitimacy_signals(row)[0] is True


def test_low_legitimacy_signals_should_not_trigger():
    row = {
        "evidence_status": "verified",
        "affiliated_staff_presence": False,
        "custom_logo_presence": False,
        "number_of_facts_about_the_organization": 3,
    }
    assert check_low_legitimacy_signals(row)[0] is False


def test_unverified_location_should_trigger():
    row = {"coordinates_valid": False}
    assert check_unverified_location(row)[0] is True


def test_unverified_location_should_not_trigger():
    row = {"coordinates_valid": True}
    assert check_unverified_location(row)[0] is False


def test_geography_unresolved_should_trigger():
    row = {"district_resolved": False}
    assert check_geography_unresolved(row)[0] is True


def test_geography_unresolved_should_not_trigger():
    row = {"district_resolved": True}
    assert check_geography_unresolved(row)[0] is False


def test_run_all_validators_returns_exactly_two_triggered_rules():
    row = {
        "evidence_status": "weak_signal",
        "doctors_reported": False,
        "capacity_reported": False,
        "capability": "ICU",
        "source_type_count": 1,
        "affiliated_staff_presence": False,
        "custom_logo_presence": False,
        "number_of_facts_about_the_organization": 1,
        "coordinates_valid": False,
        "district_resolved": False,
    }

    flags = run_all_validators(row)
    rule_names = {flag["rule"] for flag in flags}

    assert len(flags) == 2
    assert rule_names == {
        "check_unverified_location",
        "check_geography_unresolved",
    }
