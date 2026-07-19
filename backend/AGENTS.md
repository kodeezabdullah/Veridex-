# Veridex Backend — Project Memory

## Scope

This folder contains the FastAPI service that exposes Veridex facility, evidence, coverage, and scenario contracts. It reads facility records from Databricks and keeps unavailable downstream data behind stable temporary mocks.

## Connection setup

- Copy values into `backend/.env` from `backend/.env.example`; never commit `.env`.
- Required variables: `DATABRICKS_SERVER_HOSTNAME`, `DATABRICKS_HTTP_PATH`, and `DATABRICKS_TOKEN`.
- `db.py` resolves `backend/.env` from its own absolute `__file__` location and loads it with `override=True`, so behavior does not depend on the command's working directory or inherited blank variables. `get_connection()` validates configuration lazily so imports and API startup work without credentials. Missing values produce a clear configuration error only when a real Databricks endpoint is called.
- `db.py::query()` opens a connection per query, uses parameterized SQL, maps cursor columns to dictionaries, and always closes the connection.
- Run locally from the repository root with `backend/.venv/Scripts/python -m uvicorn backend.main:app`; deployment must likewise use the package-qualified `backend.main:app` entrypoint.
- After filling `.env`, smoke-test both real endpoints in-process with `backend/.venv/Scripts/python -m backend.scripts.smoke_databricks --capability ICU --state Karnataka --district Bangalore`. Pass `--unique-id` when checking a known facility directly.

## Endpoint status

- **Real:** `GET /api/facilities` queries `veridex.gold.facilities_clean`, with optional capability, state, and district filters.
- **Real:** `GET /api/facility/{unique_id}` queries the same table by `unique_id`.
- **Temporary mock:** `GET /api/regions/coverage` remains mocked until Muhammad provides the district aggregation table. Do not remove the mock before the aggregation and capability evidence inputs exist.
- **Temporary stub:** `GET /api/scenarios` and `POST /api/scenarios` return in-memory mock contracts until Lakebase/Supabase persistence is implemented.

Facility mapping uses `nfhs_state_ut` and `nfhs_district_name`, never unreliable address geography for display. Coordinates are returned only when `coordinates_valid` is true. Doctors and capacity are returned only when their corresponding reported flags are true. `district_resolved=false` is exposed as `location.unresolved=true`, not as a coverage gap.

## capability_evidence integration seam

The real table is pending. Responses already expose `capability_evidence` entries with the final shape:

```json
{
  "unique_id": "facility-id",
  "capability": "ICU",
  "evidence_status": "verified",
  "trust_score": 0.82,
  "trust_score_pct": 82,
  "field_source": "description",
  "text_span": "10-bed ICU with ventilator support",
  "confirm_message": "Verified capability evidence is available."
}
```

`evidence_status` is one of `verified`, `likely`, `weak_signal`, or `no_signal`; `trust_score` is 0–1 and `trust_score_pct` is 0–100 and is the display value. The mock is deterministic. When Muhammad's `capability_evidence` table lands, replace only the evidence query/provider internals and retain this response contract.

## Pending dependencies

- Muhammad: production `capability_evidence` table.
- Muhammad: district-level capability aggregation table for `/api/regions/coverage`.
- GIS/persistence workstream: Lakebase or Supabase scenario persistence.
- Live facility smoke tests require the user-supplied Databricks values in `backend/.env`.
