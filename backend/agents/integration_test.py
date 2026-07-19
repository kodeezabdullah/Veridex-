"""Run the Validator, Explanation, and Tavily agents together on real rows."""

from __future__ import annotations

import ast
import argparse
import json
from collections import Counter
from typing import Any

from db_connection import get_connection
from explanation_agent import generate_explanation
from tavily_check import (
    check_facility_digital_footprint,
    register_facility_source_urls,
)
from validator import run_all_validators


STATUSES = ("verified", "likely", "weak_signal", "no_signal")
TAVILY_CAPABILITIES = {"ICU", "NICU", "Trauma", "Oncology"}
TAVILY_STATUSES = {"verified", "likely"}

REAL_ROWS_QUERY = """
WITH joined AS (
    SELECT
        evidence.unique_id,
        evidence.capability,
        evidence.evidence_status,
        evidence.trust_score,
        evidence.trust_score_pct,
        evidence.field_source,
        evidence.text_span,
        evidence.score,
        evidence.richness_prior,
        evidence.confirm_message,
        facility.doctors_reported,
        facility.capacity_reported,
        facility.source_type_count,
        facility.affiliated_staff_presence,
        facility.custom_logo_presence,
        facility.number_of_facts_about_the_organization,
        facility.coordinates_valid,
        facility.district_resolved,
        facility.name AS facility_name,
        facility.address_city,
        facility.source_urls
    FROM veridex.gold.capability_evidence AS evidence
    INNER JOIN veridex.gold.facilities_clean AS facility
        ON evidence.unique_id = facility.unique_id
    WHERE evidence.evidence_status IN (
        'verified', 'likely', 'weak_signal', 'no_signal'
    )
      AND facility.name IS NOT NULL
      AND TRIM(facility.name) <> ''
      AND facility.address_city IS NOT NULL
      AND TRIM(facility.address_city) <> ''
),
one_capability_per_facility AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY evidence_status, unique_id
            ORDER BY
                CASE
                    WHEN evidence_status IN ('verified', 'likely')
                     AND capability IN ('ICU', 'NICU', 'Trauma', 'Oncology')
                    THEN 0 ELSE 1
                END,
                trust_score_pct DESC,
                capability
        ) AS facility_rank
    FROM joined
),
two_per_status AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY evidence_status
            ORDER BY
                CASE
                    WHEN evidence_status IN ('verified', 'likely')
                     AND capability IN ('ICU', 'NICU', 'Trauma', 'Oncology')
                    THEN 0 ELSE 1
                END,
                trust_score_pct DESC,
                unique_id
        ) AS status_rank
    FROM one_capability_per_facility
    WHERE facility_rank = 1
)
SELECT
    unique_id,
    capability,
    evidence_status,
    trust_score,
    trust_score_pct,
    field_source,
    text_span,
    score,
    richness_prior,
    confirm_message,
    doctors_reported,
    capacity_reported,
    source_type_count,
    affiliated_staff_presence,
    custom_logo_presence,
    number_of_facts_about_the_organization,
    coordinates_valid,
    district_resolved,
    facility_name,
    address_city,
    source_urls
FROM two_per_status
WHERE status_rank <= 2
ORDER BY
    CASE evidence_status
        WHEN 'verified' THEN 1
        WHEN 'likely' THEN 2
        WHEN 'weak_signal' THEN 3
        WHEN 'no_signal' THEN 4
    END,
    status_rank
"""


def _fetch_rows() -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(REAL_ROWS_QUERY)
            column_names = [column[0] for column in cursor.description]
            rows = [dict(zip(column_names, values)) for values in cursor.fetchall()]

    status_counts = Counter(row["evidence_status"] for row in rows)
    expected_counts = {status: 2 for status in STATUSES}
    if len(rows) != 8 or dict(status_counts) != expected_counts:
        raise RuntimeError(
            "Real-row selection did not return exactly two rows per status: "
            f"total={len(rows)}, counts={dict(status_counts)}"
        )
    return rows


def _parse_source_urls(raw_urls: Any) -> list[str]:
    if isinstance(raw_urls, (list, tuple)):
        return [str(url).strip() for url in raw_urls if str(url).strip()]
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
        return [str(url).strip() for url in parsed if str(url).strip()]
    return [str(parsed).strip()] if str(parsed).strip() else []


def _print_summary(
    index: int,
    row: dict[str, Any],
    validator_flags: list[dict],
    explanation: str,
    tavily_result: dict | str,
) -> None:
    print("=" * 80)
    print(f"ROW {index} OF 8")
    print(f"Facility: {row['facility_name']}")
    print(f"Capability: {row['capability']}")
    print(f"Evidence status: {row['evidence_status']}")
    print(f"Trust score: {row['trust_score_pct']}%")
    print("Validator flags:")
    if validator_flags:
        for flag in validator_flags:
            print(f"  - {flag['rule']}: {flag['reason']}")
    else:
        print("  none")
    print("Explanation:")
    print(explanation)
    print("Tavily result:")
    if isinstance(tavily_result, dict):
        print(json.dumps(tavily_result, ensure_ascii=False, indent=2))
    else:
        print(tavily_result)


def main(start_row: int = 1) -> int:
    if start_row < 1 or start_row > 8:
        raise ValueError("start_row must be between 1 and 8")
    rows = _fetch_rows()

    for index, row in enumerate(rows, start=1):
        if index < start_row:
            continue
        validator_flags = run_all_validators(row)
        explanation_result = generate_explanation(row, validator_flags)
        if not explanation_result.get("ok"):
            raise RuntimeError(
                "Explanation Agent failed for "
                f"unique_id={row['unique_id']}, capability={row['capability']}: "
                f"{json.dumps(explanation_result, ensure_ascii=False)}"
            )
        explanation = str(explanation_result["explanation"])

        tavily_eligible = (
            row["capability"] in TAVILY_CAPABILITIES
            and row["evidence_status"] in TAVILY_STATUSES
        )
        if tavily_eligible:
            register_facility_source_urls(
                str(row["facility_name"]),
                str(row["address_city"]),
                _parse_source_urls(row.get("source_urls")),
            )
            tavily_result: dict | str = check_facility_digital_footprint(
                str(row["facility_name"]), str(row["address_city"])
            )
        else:
            tavily_result = "not eligible for Tavily check"

        _print_summary(
            index,
            row,
            validator_flags,
            explanation,
            tavily_result,
        )

    print("=" * 80)
    print(f"INTEGRATION TEST COMPLETE: rows {start_row}-8 processed")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-row", type=int, default=1)
    arguments = parser.parse_args()
    raise SystemExit(main(start_row=arguments.start_row))
