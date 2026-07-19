"""Pure validation rules for capability evidence rows."""


def check_unsupported_claim(row: dict) -> tuple[bool, str]:
    """Flag supported evidence that lacks doctor and capacity reporting."""
    triggered = (
        row["evidence_status"] in ("verified", "likely")
        and row["doctors_reported"] is False
        and row["capacity_reported"] is False
    )
    reason = (
        "Verified or likely evidence has neither doctors_reported nor "
        "capacity_reported."
        if triggered
        else ""
    )
    return triggered, reason


def check_single_source_high_acuity(row: dict) -> tuple[bool, str]:
    """Flag supported high-acuity claims backed by at most one source type."""
    triggered = (
        row["capability"] in ("ICU", "NICU", "Trauma", "Oncology")
        and row["evidence_status"] in ("verified", "likely")
        and row["source_type_count"] <= 1
    )
    reason = (
        "A verified or likely high-acuity capability has one or fewer source types."
        if triggered
        else ""
    )
    return triggered, reason


def check_low_legitimacy_signals(row: dict) -> tuple[bool, str]:
    """Flag verified evidence with too few organizational legitimacy signals."""
    triggered = (
        row["evidence_status"] == "verified"
        and row["affiliated_staff_presence"] is False
        and row["custom_logo_presence"] is False
        and row["number_of_facts_about_the_organization"] < 3
    )
    reason = (
        "Verified evidence lacks affiliated staff and a custom logo and has fewer "
        "than three organization facts."
        if triggered
        else ""
    )
    return triggered, reason


def check_unverified_location(row: dict) -> tuple[bool, str]:
    """Flag rows whose coordinates are not valid."""
    triggered = row["coordinates_valid"] is False
    reason = "The facility coordinates are not valid." if triggered else ""
    return triggered, reason


def check_geography_unresolved(row: dict) -> tuple[bool, str]:
    """Flag rows whose district could not be resolved."""
    triggered = row["district_resolved"] is False
    reason = "The facility district is unresolved." if triggered else ""
    return triggered, reason


def run_all_validators(row: dict) -> list[dict]:
    """Run every validation rule and return only triggered flags."""
    validators = (
        check_unsupported_claim,
        check_single_source_high_acuity,
        check_low_legitimacy_signals,
        check_unverified_location,
        check_geography_unresolved,
    )

    flags = []
    for validator in validators:
        triggered, reason = validator(row)
        if triggered:
            flags.append({"rule": validator.__name__, "reason": reason})
    return flags
