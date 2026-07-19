# AGENTS.md — backend/agents/

## Purpose
This folder builds the Validator Agent and Explanation Agent for Veridex's
trust-scoring pipeline (Data Legend / Medical Desert Planner track).

## Data already available (Databricks, catalog `veridex.gold`)
- `capability_evidence`: unique_id, capability, evidence_status
  (verified/likely/weak_signal/no_signal), trust_score, trust_score_pct,
  field_source, text_span, score, richness_prior, confirm_message
- `facilities_clean`: doctors_reported, capacity_reported, source_type_count,
  affiliated_staff_presence, custom_logo_presence,
  number_of_facts_about_the_organization, coordinates_valid,
  district_resolved, name, address_city, nfhs_state_ut, nfhs_district_name

## Module 1 — Validator Agent (rule-based, NO LLM — fast, deterministic)
Implement as pure functions, one per rule, each taking a row and returning
(flag: bool, reason: str). Combine into a `validator_flags` array column.

Rules:
1. unsupported_claim — evidence_status in (verified, likely) AND
   doctors_reported=false AND capacity_reported=false
2. single_source_high_acuity — capability in (ICU, NICU, Trauma, Oncology)
   AND evidence_status in (verified, likely) AND source_type_count <= 1
3. low_legitimacy_signals — evidence_status=verified AND
   affiliated_staff_presence=false AND custom_logo_presence=false AND
   number_of_facts_about_the_organization < 3
4. unverified_location — coordinates_valid=false
5. geography_unresolved — district_resolved=false

## Module 2 — Explanation Agent (LLM-based)
- MUST use Databricks Foundation Model API, never an external OpenAI key.
- Model fallback chain (try in order, catch and continue on failure):
  1. databricks-claude-sonnet-5
  2. databricks-meta-llama-3-3-70b-instruct
  3. databricks-gpt-oss-120b
- Input: one capability_evidence row + its validator_flags
- Output: 2-3 sentence plain-language explanation for a non-technical NGO
  planner. Must state: what was found, which field it came from, confidence
  level, any validator flags in plain language, and always end with the
  confirm_message.
- Wrap every call with MLflow tracing (mlflow.start_run or autolog) — this
  covers the "Agentic Traceability" stretch goal.
- Never let the agent claim more certainty than evidence_status supports.
  A "weak_signal" result must sound uncertain in the explanation, not
  confident.

## Module 3 — Tavily cross-check (self-correction, stretch goal)
- Only runs for capability in (ICU, NICU, Trauma, Oncology) with
  evidence_status in (verified, likely).
- Search: facility name + address_city via Tavily.
- No independent results found -> flag "no_digital_footprint", lower
  confidence.
- Independent corroboration found -> note it as an additional citation,
  slightly raise confidence.

## Module 4 — Region Aggregation
Roll up facility-level `capability_evidence` into district-level coverage for
the frontend map.

Output contract:
- `region_id`: nfhs_district_name + "_" + nfhs_state_ut
- `region_name`: nfhs_district_name
- `state`: nfhs_state_ut
- `level`: "district"
- `capability_queried`: one of the 6 capabilities
- `coverage_status`: verified_coverage/weak_coverage/no_facility/no_data
- `facility_count`: distinct facilities in the district, regardless of capability
- `avg_trust_score_pct`: average trust_score_pct for matched capability rows,
  or null/0 when none

Logic:
1. Base population is every distinct (nfhs_district_name, nfhs_state_ut)
   combination from `facilities_clean` where district_resolved=true, crossed
   with all 6 capabilities.
2. For each district/state/capability:
   - facility_count=0 -> no_data
   - any matched evidence_status in (verified, likely) -> verified_coverage
   - otherwise, any matched evidence_status=weak_signal -> weak_coverage
   - otherwise -> no_facility, including all-no_signal and no joined evidence rows
3. Write the result to `veridex.gold.region_coverage`.
4. Print row count and the overall coverage_status distribution.
5. Stop and report if any coverage_status exceeds 85% of all rows.

Rows incorrectly marked `district_resolved=true` but missing either district
or state cannot satisfy the region API contract. Exclude and report them;
never infer or fabricate the missing geography.

## Non-negotiable principles (carried from the data layer work)
- Never force a guess. If uncertain, output "unresolved"/"no-call", not a
  fabricated confidence number.
- Every explanation must cite field_source + text_span — no unsupported claims.
- confirm_message is always included in any planner-facing output.

## Required build order — verification before scale, every step
Do NOT write the full pipeline in one shot. Build and verify in this order:
1. Write all 5 validator rules as independent pure functions with unit
   tests — one synthetic "should trigger" and one "should not trigger"
   example per rule. Do not proceed until all pass.
2. Run the validator over the real capability_evidence table. Print flag
   rate per rule (% of rows flagged). Sanity check: none should be 0% or
   100% — flag and stop if so, that likely means a bug, not real data.
3. Build the Explanation Agent. Test on 5 hand-picked rows spanning all
   four evidence_status values. Print and manually review output before
   batch-running.
4. Build the Tavily cross-check. Test on 2-3 known real facilities before
   wiring into the main flow.
5. Only after 1-4 each pass their checks: run the full batch and write
   results to a new gold table.

Confirm each step's test output before moving to the next step.
