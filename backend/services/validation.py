"""Live, ground-truth-free validation metrics for the analytics dashboard."""

from backend.db import query
from backend.agents.validator import run_all_validators

RULES = [
    "check_unsupported_claim",
    "check_single_source_high_acuity",
    "check_low_legitimacy_signals",
    "check_unverified_location",
    "check_geography_unresolved",
]


def system_validation_summary() -> dict:
    rows = query("""
        SELECT ce.evidence_status, ce.keyword_confirmed, ce.capability,
               fc.doctors_reported, fc.capacity_reported, fc.source_type_count,
               fc.affiliated_staff_presence, fc.custom_logo_presence,
               fc.number_of_facts_about_the_organization, fc.coordinates_valid,
               fc.district_resolved
        FROM veridex.gold.capability_evidence ce
        LEFT JOIN veridex.gold.facilities_clean fc ON ce.unique_id = fc.unique_id
    """)
    moderate = [row for row in rows if str(row.get("evidence_status", "")).lower() in {"likely", "weak_signal"}]
    keyword_confirmed = sum(bool(row.get("keyword_confirmed")) for row in moderate)
    rule_counts = {rule: 0 for rule in RULES}
    flagged_rows = 0
    for row in rows:
        flags = run_all_validators(row)
        if flags:
            flagged_rows += 1
        for flag in flags:
            rule_counts[flag["rule"]] += 1
    total = len(rows)
    pct = lambda count, denominator: round(count / denominator * 100, 1) if denominator else 0.0
    return {
        "total_rows": total,
        "keyword_confirmation": {"eligible_rows": len(moderate), "confirmed_rows": keyword_confirmed, "rate_pct": pct(keyword_confirmed, len(moderate))},
        "validator_flagged_rows": flagged_rows,
        "validator_flag_rate_pct": pct(flagged_rows, total),
        "validator_rules": [{"rule": rule, "flagged_rows": rule_counts[rule], "rate_pct": pct(rule_counts[rule], total)} for rule in RULES],
    }
