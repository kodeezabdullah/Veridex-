"""Build district-level capability coverage for the frontend map."""

from db_connection import DatabricksConfigurationError, get_connection


EXPECTED_CAPABILITIES = {
    "ICU",
    "NICU",
    "Emergency",
    "Maternity",
    "Oncology",
    "Trauma",
}
OUTPUT_TABLE = "veridex.gold.region_coverage"
MAX_STATUS_SHARE = 0.85


REGION_COVERAGE_QUERY = """
WITH capabilities AS (
    SELECT DISTINCT capability
    FROM veridex.gold.capability_evidence
),
resolved_facilities AS (
    SELECT
        unique_id,
        TRIM(nfhs_district_name) AS nfhs_district_name,
        TRIM(nfhs_state_ut) AS nfhs_state_ut
    FROM veridex.gold.facilities_clean
    WHERE district_resolved = true
      AND nfhs_district_name IS NOT NULL
      AND TRIM(nfhs_district_name) <> ''
      AND nfhs_state_ut IS NOT NULL
      AND TRIM(nfhs_state_ut) <> ''
),
districts AS (
    SELECT DISTINCT nfhs_district_name, nfhs_state_ut
    FROM resolved_facilities
),
base AS (
    SELECT
        district.nfhs_district_name,
        district.nfhs_state_ut,
        capability.capability
    FROM districts AS district
    CROSS JOIN capabilities AS capability
),
facility_counts AS (
    SELECT
        nfhs_district_name,
        nfhs_state_ut,
        COUNT(DISTINCT unique_id) AS facility_count
    FROM resolved_facilities
    GROUP BY nfhs_district_name, nfhs_state_ut
),
evidence_summary AS (
    SELECT
        facility.nfhs_district_name,
        facility.nfhs_state_ut,
        evidence.capability,
        MAX(CASE
            WHEN evidence.evidence_status IN ('verified', 'likely') THEN 1
            ELSE 0
        END) AS has_verified_or_likely,
        MAX(CASE
            WHEN evidence.evidence_status = 'weak_signal' THEN 1
            ELSE 0
        END) AS has_weak_signal,
        AVG(evidence.trust_score_pct) AS avg_trust_score_pct
    FROM resolved_facilities AS facility
    INNER JOIN veridex.gold.capability_evidence AS evidence
        ON facility.unique_id = evidence.unique_id
    GROUP BY
        facility.nfhs_district_name,
        facility.nfhs_state_ut,
        evidence.capability
)
SELECT
    CONCAT(base.nfhs_district_name, '_', base.nfhs_state_ut) AS region_id,
    base.nfhs_district_name AS region_name,
    base.nfhs_state_ut AS state,
    'district' AS level,
    base.capability AS capability_queried,
    CASE
        WHEN COALESCE(facility_counts.facility_count, 0) = 0 THEN 'no_data'
        WHEN COALESCE(evidence_summary.has_verified_or_likely, 0) = 1
            THEN 'verified_coverage'
        WHEN COALESCE(evidence_summary.has_weak_signal, 0) = 1
            THEN 'weak_coverage'
        ELSE 'no_facility'
    END AS coverage_status,
    CAST(COALESCE(facility_counts.facility_count, 0) AS INT) AS facility_count,
    CAST(ROUND(COALESCE(evidence_summary.avg_trust_score_pct, 0)) AS INT)
        AS avg_trust_score_pct
FROM base
LEFT JOIN facility_counts
    ON base.nfhs_district_name = facility_counts.nfhs_district_name
    AND base.nfhs_state_ut = facility_counts.nfhs_state_ut
LEFT JOIN evidence_summary
    ON base.nfhs_district_name = evidence_summary.nfhs_district_name
    AND base.nfhs_state_ut = evidence_summary.nfhs_state_ut
    AND base.capability = evidence_summary.capability
"""


def _fetch_distribution(cursor, query: str) -> tuple[int, list[tuple[str, int]]]:
    cursor.execute(
        f"""
        SELECT coverage_status, COUNT(*) AS rows
        FROM ({query}) AS coverage
        GROUP BY coverage_status
        ORDER BY coverage_status
        """
    )
    distribution = [(str(row[0]), int(row[1])) for row in cursor.fetchall()]
    total_rows = sum(count for _, count in distribution)
    return total_rows, distribution


def _print_distribution(total_rows: int, distribution: list[tuple[str, int]]) -> None:
    print(f"Total region coverage rows: {total_rows}")
    print(f"{'coverage_status':<22} {'rows':>8} {'percentage':>12}")
    print("-" * 44)
    for status, count in distribution:
        percentage = count / total_rows * 100 if total_rows else 0
        print(f"{status:<22} {count:>8} {percentage:>11.2f}%")


def main() -> int:
    try:
        connection = get_connection()
    except DatabricksConfigurationError as error:
        print(f"Databricks configuration unavailable: {error}")
        return 1

    with connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT DISTINCT capability "
                "FROM veridex.gold.capability_evidence ORDER BY capability"
            )
            actual_capabilities = {str(row[0]) for row in cursor.fetchall()}
            if actual_capabilities != EXPECTED_CAPABILITIES:
                print(
                    "Region aggregation stopped: unexpected capabilities. "
                    f"expected={sorted(EXPECTED_CAPABILITIES)}, "
                    f"actual={sorted(actual_capabilities)}"
                )
                return 1

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM veridex.gold.facilities_clean
                WHERE district_resolved = true
                  AND (
                      nfhs_district_name IS NULL
                      OR TRIM(nfhs_district_name) = ''
                      OR nfhs_state_ut IS NULL
                      OR TRIM(nfhs_state_ut) = ''
                  )
                """
            )
            invalid_region_rows = int(cursor.fetchone()[0])
            if invalid_region_rows:
                print(
                    "Excluded resolved facilities with incomplete region keys: "
                    f"{invalid_region_rows} (district/state was not guessed)"
                )

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT DISTINCT
                        TRIM(nfhs_district_name),
                        TRIM(nfhs_state_ut)
                    FROM veridex.gold.facilities_clean
                    WHERE district_resolved = true
                      AND nfhs_district_name IS NOT NULL
                      AND TRIM(nfhs_district_name) <> ''
                      AND nfhs_state_ut IS NOT NULL
                      AND TRIM(nfhs_state_ut) <> ''
                ) AS districts
                """
            )
            district_count = int(cursor.fetchone()[0])

            preview_rows, preview_distribution = _fetch_distribution(
                cursor, REGION_COVERAGE_QUERY
            )
            expected_rows = district_count * len(EXPECTED_CAPABILITIES)
            print(f"Resolved districts: {district_count}")
            print(f"Expected rows ({district_count} x 6): {expected_rows}")
            _print_distribution(preview_rows, preview_distribution)

            if preview_rows != expected_rows:
                print(
                    "Region aggregation stopped: preview row count does not match "
                    f"the district-capability cross product ({preview_rows} != {expected_rows})."
                )
                return 1

            if preview_rows == 0:
                print("Region aggregation stopped: preview returned no rows.")
                return 1

            skewed = [
                (status, count / preview_rows)
                for status, count in preview_distribution
                if count / preview_rows > MAX_STATUS_SHARE
            ]
            if skewed:
                print(
                    "Region aggregation stopped before write: a coverage status "
                    f"exceeds 85%: {skewed}"
                )
                return 1

            cursor.execute(
                f"CREATE OR REPLACE TABLE {OUTPUT_TABLE} USING DELTA AS "
                f"{REGION_COVERAGE_QUERY}"
            )

            cursor.execute(f"SELECT COUNT(*) FROM {OUTPUT_TABLE}")
            written_rows = int(cursor.fetchone()[0])
            cursor.execute(
                f"""
                SELECT coverage_status, COUNT(*) AS rows
                FROM {OUTPUT_TABLE}
                GROUP BY coverage_status
                ORDER BY coverage_status
                """
            )
            written_distribution = [
                (str(row[0]), int(row[1])) for row in cursor.fetchall()
            ]

            if written_rows != preview_rows or written_distribution != preview_distribution:
                print(
                    "Region aggregation write verification failed: preview and written "
                    "results differ."
                )
                return 1

            print(f"Wrote {OUTPUT_TABLE}.")
            _print_distribution(written_rows, written_distribution)
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
