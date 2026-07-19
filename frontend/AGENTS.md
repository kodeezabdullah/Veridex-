# Veridex Frontend — Project Memory

Last updated: 2026-07-19

## Product context

Veridex is a healthcare-facility trust and coverage mapping app for planners in India, built for the Hack-Nation Global AI Hackathon Databricks Challenge. The backend workstream (FastAPI ingestion, vector search, evidence extraction, and trust scoring) belongs to another teammate and is out of scope. Frontend work must stay inside `frontend/` and must not modify `/backend`.

The planner-facing product helps users search for a healthcare capability in a geography, inspect trust-weighted district coverage, review facility claims and their exact evidence, and save a human-curated shortlist with notes or overrides. The interface informs decisions; it must never silently make a decision for the planner.

## Technology and deployment

- Next.js with the App Router and TypeScript
- Tailwind CSS
- MapLibre GL JS with Deck.gl for the district choropleth
- Persistence: evaluate Lakebase first; fall back to Supabase with PostGIS if Lakebase setup threatens delivery
- Deployment: Databricks Apps using Next.js/Node
- `next.config` must use `output: "standalone"` before deployment
- All UI data access goes through `lib/api.ts`; components must never call `fetch()` directly
- `lib/api.ts` calls the real backend endpoints and normalizes their response envelopes; unavailable APIs produce explicit error states rather than substituted records

## Screens and user flow

1. **Coverage selector (`/`)**: The landing screen uses structured capability, state, and district dropdowns. District options cascade from the selected state using distinct `region_coverage` rows. Submitting navigates to the trust-weighted map/results workspace with `capability`, `state`, and `district` query parameters; there is no free-text or chat interaction in this track.
2. **Facility marker popup (within `/map`)**: Clicking a marker opens a custom evidence card with facility name, claim/trust status, exact evidence snippet, and a link to the full evidence record. Coverage polygons are real district-level ADM2 boundaries.
3. **Facility list (`/map`)**: The existing list-oriented map workspace remains available as a secondary view. Facility cards show name, claimed capabilities, evidence-aware trust status, and trust score with filtering and sorting.
4. **Facility detail (`/facility/[id]`)**: Full profile and evidence view. Each claim shows its final `verified`, `likely`, `weak_signal`, or `no_signal` status, confidence, and the exact `text_span` highlighted in the corresponding `raw_fields` value. Notes and overrides are explicit planner inputs; the UI does not decide for them.
5. **Scenarios (`/scenarios`)**: Saved facilities, notes, and overrides persisted across sessions in Lakebase or Supabase/PostGIS.

## Coverage semantics

Coverage status is always one of:

- `verified_coverage`: corroborated claims; green treatment
- `weak_coverage`: weak supporting evidence; amber treatment
- `no_facility`: a confirmed gap; red treatment
- `no_data`: insufficient knowledge, never equivalent to a confirmed gap; grey hatched/pattern treatment everywhere it appears

The distinction between `no_data` and `no_facility` is a product invariant across maps, legends, cards, filters, empty states, and details.

## API contract

### `GET /api/facilities?capability=ICU&state=&district=&pin=`

Returns facility records (the supplied contract presents a single record shape):

```json
{
  "facility_id": "f_00123",
  "name": "District Hospital, Example",
  "location": {
    "state": "Punjab",
    "district": "Faisalabad",
    "city": "Faisalabad",
    "pin": "38000",
    "lat": 31.42,
    "lon": 73.08
  },
  "capability_evidence": [
    {
      "unique_id": "f_00123",
      "capability": "ICU",
      "evidence_status": "verified",
      "trust_score": 0.82,
      "trust_score_pct": 82,
      "field_source": "description",
      "text_span": "10-bed ICU with ventilator support and 24/7 staffing",
      "confirm_message": "Confirm directly with the facility."
    }
  ],
  "raw_fields": {
    "description": "...",
    "procedure": "...",
    "equipment": "...",
    "numberDoctors": null,
    "capacity": null,
    "yearEstablished": "1998"
  },
  "data_completeness": {
    "capacity_reported": false,
    "doctors_reported": false
  }
}
```

### `GET /api/regions/coverage?capability=ICU&level=district`

```json
{
  "region_id": "PB-FSD",
  "region_name": "Faisalabad",
  "level": "district",
  "capability_queried": "ICU",
  "coverage_status": "verified_coverage",
  "facility_count": 14,
  "avg_trust_score": 0.71
}
```

### `POST /api/scenarios` and `GET /api/scenarios`

```json
{
  "scenario_id": "s_001",
  "name": "ICU gap review — Punjab",
  "shortlist": ["f_00123", "f_00456"],
  "notes": [
    {
      "facility_id": "f_00123",
      "note": "confirm ventilator count by phone",
      "timestamp": "2026-07-19T10:00:00Z"
    }
  ],
  "overrides": [],
  "created_at": "2026-07-19T09:00:00Z"
}
```

Open API question: confirm whether list endpoints wrap arrays (for example `{ "facilities": [] }`) or return bare arrays. Keep normalization inside `lib/api.ts` so components remain unaffected.

### Structured selector integration seam

The landing selector receives district coverage rows and derives distinct state
and district options from them. It navigates to
`/map?capability=&state=&district=`. Backend requests use the final handoff
contract: `GET /api/regions/coverage?capability=` and
`GET /api/facilities?capability=&state=&district=`. Components do not parse or
send natural-language queries.

## Intended folder structure

```text
frontend/
  app/
    page.tsx
    map/page.tsx
    facility/[id]/page.tsx
    scenarios/page.tsx
  components/
    CoverageSelector.tsx
    MapView.tsx
    FacilityCard.tsx
    EvidenceView.tsx
  lib/
    types.ts
    api.ts
  public/geojson/
  AGENTS.md
```

Additional app-level files (layout, global styles, configuration, assets) may be added as required by Next.js.

## Design system direction

The visual language should feel like a premium civic intelligence product rather than a generic admin dashboard. Use a warm mineral/off-white canvas, deep ink and forest surfaces, a restrained verdigris accent, and semantic moss/amber/rust/stone coverage colors. Headings use a distinctive display face paired with a highly legible sans-serif UI face. Establish named tokens for color, type scale, spacing, radii, shadows, and motion in global styles/configuration. Prefer generous whitespace, crisp information hierarchy, quiet texture, restrained borders, and purposeful micro-interactions. Include hover/focus transitions and loading skeletons, while respecting reduced-motion preferences.

Accessibility requirements: visible keyboard focus, semantic labels, adequate contrast, non-color status cues, and touch targets of at least 44px.

## Geographic data rules

- The active boundary source is `public/geojson/geoBoundaries-IND-ADM2_simplified.geojson`, containing 735 simplified India district features from the official geoBoundaries gbOpen ADM2 release (API metadata reports 736 units). `shapeName` is the district coverage join key; both Polygon and MultiPolygon geometry are supported.
- Source provenance: geoBoundaries boundary `IND-ADM2-76128533`, represented year 2021, source Pathways Data Pvt. Ltd./lgdirectory.gov.in, Open Data Commons Open Database License 1.0.
- Do not source or fabricate PIN-level polygons.
- PIN is a facility filter and point-marker attribute only, not a choropleth boundary.
- Verify source district names/codes against backend region identifiers before production joining.

## Current progress

- [x] Project context and constraints recorded in this living document.
- [x] Design tokens and base application shell established (warm mineral canvas, forest/verdigris palette, Georgia display typography, responsive shell, focus and reduced-motion states).
- [x] Selection-based Screen 1 implemented on `/` with the six canonical capabilities and cascading state/district dropdowns derived from region coverage; submission opens the map/results workspace with structured parameters.
- [x] Map and coverage legend built with MapLibre GL JS + Deck.gl, district selection, facility point markers, all four semantic statuses, and explicit diagonal hatching for `no_data`.
- [x] Facility list built inside the map flow with claim-status filtering, trust-score sorting, evidence previews, and explicit `no_data` vs confirmed-gap empty states.
- [x] Facility detail and evidence highlighting built with claim tabs, exact `text_span` highlighting inside `raw_fields`, confidence/trust context, completeness indicators, planner notes, and manual dispositions.
- [x] Scenario workspace uses the backend scenario, shortlist, notes, and overrides endpoints; it never substitutes seeded browser data when the API is unavailable.
- [x] Hardcoded facilities, geography menus, generated coverage states, and seeded scenarios removed; canonical types remain in `lib/types.ts` and all records come from the real API.
- [ ] Databricks Apps deployment configured and smoke-tested.

## Open decisions and risks

- Persistence depends on the backend Lakebase scenario endpoints documented in the final handoff.
- Final facility and region list response envelopes need backend confirmation.
- Geography reference data and canonical state/district/city/PIN hierarchy need backend alignment.
- Real simplified India ADM2 geometry is active and keyed by exact district `shapeName`. Backend `region_name` values must align with those boundary names. Retain geoBoundaries ODbL attribution in public deployment.
- Databricks Apps runtime environment variables, build command, health check, and persistent data connectivity need early validation.
- `/` is the selection entry point; `/map` is the trust-weighted map and facility-results workspace.
- Screen 1 verification: `npm run lint` and `npm run build` pass on Next.js 16.2.10; `/` is statically prerendered and standalone output is enabled.
- Dependency audit after upgrading from vulnerable Next.js 16.1.6 to 16.2.10 reports two moderate findings for Next.js's bundled PostCSS `<8.5.10`. npm offers only an invalid breaking downgrade (`next@9.3.3`) via `audit fix --force`; do not apply it. Recheck when Next.js ships a release bundling patched PostCSS.
- Full frontend verification on 2026-07-19: `npm run lint` and `npm run build` pass. Browser automation could not run because the `agent-browser` CLI is unavailable in the environment; manually verify map clicks and responsive layout against the live backend before demo.
- Map rendering fix verified on 2026-07-19 through Chrome DevTools Protocol: `.map-canvas`, the MapLibre canvas, and `.deck-canvas` all inherit the full `.map-stage` height (560px at the narrow breakpoint; 708px at 1440×900). The map uses no-key CARTO Positron raster tiles, native MapLibre GeoJSON fill/pattern/border layers for coverage, a generated hatch pattern for `no_data`, and Deck.gl facility markers. All sampled CARTO tiles returned HTTP 200 with no browser errors.
- ADM2 boundary rendering uses the real geoBoundaries file while every coverage status, facility count, trust score, and facility marker comes from backend API responses. The four canonical colors are centralized in `lib/coverage.ts`.
- ADM2 browser verification on 2026-07-19: fresh loads at 1440x900 and 1024x900 showed the complete India extent with 735 district features, all four coverage statuses, two active map canvases, and no horizontal overflow. Rendered colors were `#4f8064`, `#d7a53f`, `#b4523e`, and `#9a9d97`; chat message/input text rendered at 13px and suggestion text at 11px. The coverage endpoint returned HTTP 200 and the Karnataka ICU query completed its animated district focus without browser exceptions.
- Matched query results use a two-tier map overlay: every matched facility receives an icon-only health-worker marker using `svg/health-worker-svgrepo-com.svg`, with compact screen-space collision offsets for nearby results. Names, trust state, and evidence remain hidden until selection. Selecting an icon or matched marker replaces it with the single rich evidence card; selecting another result swaps cards, while a map-background click restores the icon-only state. Motion handles keyed scale/fade transitions for both tiers.
- Two-tier popup behavior supports compact facility previews, a single selected evidence card, and map-background dismissal; verify it with live facility responses before demo.
- Selection-entry pivot verified on 2026-07-19: `/` renders capability, state, and cascading district selects with no chat input; the selector routes with structured `capability`, `state`, and `district` parameters. Lint and the Next.js production build pass, and production-server smoke checks returned HTTP 200 for `/` and a structured `/map` URL.
- Real-data-only frontend verified on 2026-07-19: source scans find no hardcoded facility/geography/scenario datasets, lint and production build pass, and missing backend configuration produces explicit unavailable states with no substituted records. Set `VERIDEX_API_BASE_URL` for server components and optionally `NEXT_PUBLIC_API_BASE_URL` for browser requests.
- The facility API now exposes `capability_evidence` as its sole evidence-status array. `lib/api.ts` normalizes those rows into the frontend's internal `capabilities` view model; the backend no longer emits the legacy `claimed-only` status vocabulary.
- The separate analytics/System Validation dashboard was removed from the primary product flow at the user's request; the map inspector remains the focused planning surface.
- A shared server-rendered brand mark and short client boot gate provide a heartbeat loading screen before the workspace becomes interactive; this is a presentation gate, not an authentication system because no login endpoint exists in the handoff contract.
- Local development defaults both frontend API URL settings to `http://127.0.0.1:8010`; deployments can override `NEXT_PUBLIC_API_BASE_URL` and `VERIDEX_API_BASE_URL`.
- Coverage workspace redesign: `/map` now uses a light Mapbox/MapLibre + Deck.gl canvas with a navigation rail, right-side planner inspector, live analytics cards, score-coded hospital/clinic SVG pins, and evidence popups. Animated preview pins are capped for responsiveness while the full facility feed remains available.
- `/analytics` is a dedicated project dashboard built from all six live `region_coverage` capability responses; it contains no generated or seeded statistics.
- Persistent workspace navigation is now server-rendered through `components/WorkspaceRail.tsx` and appears on overview, analytics, scenarios, and facility pages; only the map workspace retains its specialized client rail.
- The map globe intro is centered on India, uses a white map surface, rotates right-to-left briefly, then eases into the selected region. The right inspector uses contained scrolling and responsive breakpoints for narrow screens.
- Git/GitHub work is explicitly paused by the user until the frontend is functionally complete. Do not commit, configure remotes, push, or modify authorship unless the user explicitly resumes that work.

## Working conventions

- Read this file at the start of every frontend session.
- Update it after every meaningful screen, API contract, design, deployment, persistence, or blocker change.
- Work only inside `frontend/`; do not touch `/backend`.
- Keep backend response normalization and endpoint access isolated to `lib/api.ts`.
- Preserve evidence, confidence, and uncertainty in every relevant UI state.
- When the user explicitly resumes Git work, make small focused commits using their Git identity with no AI attribution or co-author lines. Until then, make no Git/GitHub changes.
