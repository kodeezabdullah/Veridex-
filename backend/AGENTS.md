# Veridex Backend — Project Memory

## Scope

This FastAPI service exposes Veridex facility, evidence, coverage, and scenario contracts. Facility, capability-evidence, and coverage data come from Databricks; scenario persistence uses Lakebase PostgreSQL.

## Connections

- Copy values into `backend/.env` from `backend/.env.example`; never commit `.env`.
- Databricks requires `DATABRICKS_SERVER_HOSTNAME`, `DATABRICKS_HTTP_PATH`, and `DATABRICKS_TOKEN`.
- `db.py` resolves `.env` relative to its own file, validates settings lazily, opens one Databricks SQL connection per query, maps rows to dictionaries, and always closes the connection.
- Lakebase requires the `LAKEBASE_*` settings in `.env`. `lakebase.py` resolves the Autoscaling endpoint by matching `LAKEBASE_HOST` against workspace Postgres endpoints.
- Every new PostgreSQL connection calls `WorkspaceClient.postgres.generate_database_credential`; the short-lived credential is never cached.
- Run locally from the repository root with `backend/.venv/Scripts/python -m uvicorn backend.main:app`.
- Smoke-test facilities with `backend/.venv/Scripts/python -m backend.scripts.smoke_databricks --capability ICU --state Karnataka --district Bangalore`.

## Endpoint status

- **Real:** `GET /api/facilities` joins `veridex.gold.facilities_clean` to `veridex.gold.capability_evidence`, with optional capability, state, and district filters.
- **Real:** `GET /api/facility/{unique_id}` returns the complete facility and all capability-evidence rows. An optional `capability` query parameter activates capability-specific validator, explanation, and Tavily enrichment.
- **Real:** `GET /api/regions/coverage` queries `veridex.gold.region_coverage`. It returns `region_id` as `{nfhs_district_name}_{nfhs_state_ut}`, `level="district"`, and `avg_trust_score_pct` as an integer from 0–100. It returns an empty list for no match and a clear 503 when the table or service is unavailable; it never falls back to mocks.
- **Real:** `GET /api/scenarios`, `POST /api/scenarios`, `POST /api/scenarios/{id}/notes`, and `POST /api/scenarios/{id}/shortlist` persist planner data in Lakebase.

Facility mapping uses trimmed `nfhs_state_ut` and `nfhs_district_name`, never unreliable address geography for display. Coordinates are returned only when `coordinates_valid` is true. Doctors and capacity are returned only when their reporting flags are true. `district_resolved=false` becomes `location.unresolved=true`, not a coverage gap.

## Capability evidence and enrichment

Capability filtering uses the real `veridex.gold.capability_evidence` table rather than raw facility text. Evidence rows retain this contract:

```json
{
  "unique_id": "facility-id",
  "capability": "ICU",
  "evidence_status": "verified",
  "trust_score": 0.82,
  "trust_score_pct": 82,
  "field_source": "description",
  "text_span": "10-bed ICU with ventilator support",
  "confirm_message": "Confirm directly with the facility."
}
```

`evidence_status` is `verified`, `likely`, `weak_signal`, or `no_signal`. For a viewed capability, the detail endpoint runs `run_all_validators` and `generate_explanation`. Tavily is caller-gated to ICU, NICU, Trauma, or Oncology with verified or likely evidence.

## Operations and pending work

- Refresh `veridex.gold.region_coverage` with `backend/agents/region_aggregation.py` after facility or evidence updates.
- Tavily enrichment requires `TAVILY_API_KEY`; absence returns an explicit unavailable result without failing facility detail.
- The four required Lakebase scenario operations are real. Rename, delete, override, and shortlist-removal endpoints remain future contract additions.
