"""Run exactly five synthetic explanation-agent checks for manual review."""

import json

from explanation_agent import generate_explanation


SYNTHETIC_CASES = [
    {
        "label": "verified",
        "row": {
            "unique_id": "synthetic-verified-001",
            "capability": "ICU",
            "evidence_status": "verified",
            "trust_score": 0.91,
            "trust_score_pct": 91,
            "field_source": "services_text",
            "text_span": "24/7 ICU with ventilator support",
            "score": 0.95,
            "richness_prior": 0.88,
            "confirm_message": "Confirm current ICU availability directly with the facility.",
        },
        "validator_flags": [],
    },
    {
        "label": "likely",
        "row": {
            "unique_id": "synthetic-likely-001",
            "capability": "Oncology",
            "evidence_status": "likely",
            "trust_score": 0.72,
            "trust_score_pct": 72,
            "field_source": "department_list",
            "text_span": "Cancer care and chemotherapy department",
            "score": 0.76,
            "richness_prior": 0.68,
            "confirm_message": "Confirm oncology services directly with the facility.",
        },
        "validator_flags": [],
    },
    {
        "label": "weak_signal",
        "row": {
            "unique_id": "synthetic-weak-001",
            "capability": "Trauma",
            "evidence_status": "weak_signal",
            "trust_score": 0.34,
            "trust_score_pct": 34,
            "field_source": "website_summary",
            "text_span": "Emergency and trauma support may be available",
            "score": 0.38,
            "richness_prior": 0.29,
            "confirm_message": "Confirm trauma capability directly with the facility.",
        },
        "validator_flags": [],
    },
    {
        "label": "no_signal",
        "row": {
            "unique_id": "synthetic-none-001",
            "capability": "NICU",
            "evidence_status": "no_signal",
            "trust_score": 0.0,
            "trust_score_pct": 0,
            "field_source": "services_text",
            "text_span": "No NICU-related text was found",
            "score": 0.0,
            "richness_prior": 0.21,
            "confirm_message": "Confirm NICU capability directly with the facility.",
        },
        "validator_flags": [],
    },
    {
        "label": "verified_with_two_flags",
        "row": {
            "unique_id": "synthetic-flagged-001",
            "capability": "Dialysis",
            "evidence_status": "verified",
            "trust_score": 0.86,
            "trust_score_pct": 86,
            "field_source": "services_text",
            "text_span": "Dialysis unit operating six days a week",
            "score": 0.9,
            "richness_prior": 0.82,
            "confirm_message": "Confirm dialysis capacity and location directly with the facility.",
        },
        "validator_flags": [
            {
                "rule": "check_unsupported_claim",
                "reason": (
                    "Verified or likely evidence has neither doctors_reported nor "
                    "capacity_reported."
                ),
            },
            {
                "rule": "check_unverified_location",
                "reason": "The facility coordinates are not valid.",
            },
        ],
    },
]


def main() -> int:
    for index, case in enumerate(SYNTHETIC_CASES, start=1):
        result = generate_explanation(case["row"], case["validator_flags"])
        if not result.get("ok"):
            raise AssertionError(
                f"Synthetic case {case['label']} failed: "
                f"{json.dumps(result, ensure_ascii=False)}"
            )
        assert result["field_source"] == case["row"]["field_source"]
        assert result["text_span"] == case["row"]["text_span"]
        print(f"\n=== SYNTHETIC OUTPUT {index}: {case['label']} ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
