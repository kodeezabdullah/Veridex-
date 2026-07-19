"""Run the pure validator rules against the real Databricks gold tables."""

from databricks.sql.exc import Error as DatabricksError

from db_connection import DatabricksConfigurationError, get_connection
from validator import run_all_validators


CAPABILITY_QUERY = "SELECT * FROM veridex.gold.capability_evidence"
FACILITIES_QUERY = """
SELECT
    unique_id,
    doctors_reported,
    capacity_reported,
    source_type_count,
    affiliated_staff_presence,
    custom_logo_presence,
    number_of_facts_about_the_organization,
    coordinates_valid,
    district_resolved
FROM veridex.gold.facilities_clean
"""

RULE_NAMES = (
    "check_unsupported_claim",
    "check_single_source_high_acuity",
    "check_low_legitimacy_signals",
    "check_unverified_location",
    "check_geography_unresolved",
)

CAPABILITY_FIELDS = ("unique_id", "capability", "evidence_status")
FACILITY_FIELDS = (
    "doctors_reported",
    "capacity_reported",
    "source_type_count",
    "affiliated_staff_presence",
    "custom_logo_presence",
    "number_of_facts_about_the_organization",
    "coordinates_valid",
    "district_resolved",
)


def _fetch_dicts(cursor, query: str) -> list[dict]:
    cursor.execute(query)
    column_names = [description[0] for description in cursor.description]
    return [dict(zip(column_names, values)) for values in cursor.fetchall()]


def _table_is_missing(error: Exception) -> bool:
    message = str(error).lower()
    return any(
        marker in message
        for marker in ("table_or_view_not_found", "table not found", "does not exist")
    )


def _print_flag_rates(counts: dict[str, int], total_rows: int) -> None:
    print(f"Total capability_evidence rows: {total_rows}")
    print(f"{'Rule':<40} {'Triggered':>10} {'Percentage':>12}")
    print("-" * 64)
    for rule_name in RULE_NAMES:
        count = counts[rule_name]
        percentage = count / total_rows * 100
        print(f"{rule_name:<40} {count:>10} {percentage:>11.2f}%")


def main() -> int:
    try:
        connection = get_connection()
    except DatabricksConfigurationError as error:
        print(f"Databricks configuration unavailable: {error}")
        return 1
    except DatabricksError as error:
        print(f"Could not connect to Databricks: {error}")
        return 1

    try:
        with connection:
            with connection.cursor() as cursor:
                try:
                    capability_rows = _fetch_dicts(cursor, CAPABILITY_QUERY)
                except DatabricksError as error:
                    if _table_is_missing(error):
                        print(
                            "capability_evidence not ready yet — "
                            "Vector Search pipeline may still be running"
                        )
                        return 0
                    raise

                if not capability_rows:
                    print(
                        "capability_evidence not ready yet — "
                        "Vector Search pipeline may still be running"
                    )
                    return 0

                facility_rows = _fetch_dicts(cursor, FACILITIES_QUERY)
    except DatabricksError as error:
        print(f"Databricks query failed: {error}")
        return 1

    facilities_by_id = {row["unique_id"]: row for row in facility_rows}
    missing_facility_ids = {
        row["unique_id"]
        for row in capability_rows
        if row["unique_id"] not in facilities_by_id
    }
    if missing_facility_ids:
        print(
            "Validator run stopped: facilities_clean join failed for "
            f"{len(missing_facility_ids)} unique_id value(s)."
        )
        return 1

    counts = {rule_name: 0 for rule_name in RULE_NAMES}
    for capability_row in capability_rows:
        facility_row = facilities_by_id[capability_row["unique_id"]]
        validator_row = {
            field: capability_row[field] for field in CAPABILITY_FIELDS
        }
        validator_row.update(
            {field: facility_row[field] for field in FACILITY_FIELDS}
        )

        for flag in run_all_validators(validator_row):
            counts[flag["rule"]] += 1

    _print_flag_rates(counts, len(capability_rows))

    invalid_rates = [
        rule_name
        for rule_name, count in counts.items()
        if count == 0 or count == len(capability_rows)
    ]
    if invalid_rates:
        print(
            "Sanity check failed: the following rules are exactly 0% or 100%: "
            + ", ".join(invalid_rates)
        )
        return 1

    print("Sanity check passed: no validator rule is at 0% or 100%.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
