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
- During mock development, `lib/api.ts` reads `lib/mockData.ts` while retaining backend-compatible JSON shapes

## Screens and user flow

1. **Selector (`/`)**: Capability selector (ICU, maternity, emergency, oncology, trauma, NICU) and a cascading/searchable geography selector (state → district → city → PIN). Search navigates to `/map` with query parameters.
2. **Map (`/map`)**: District-level India choropleth showing trust-weighted coverage. `verified_coverage` is green, `weak_coverage` is amber, `no_facility` is red, and `no_data` is a visually distinct hatched/grey treatment. Selecting a district drills into its facilities.
3. **Facility list (within map flow)**: Facility cards show name, claimed capabilities, evidence-aware trust status, and trust score. The list supports filtering and sorting by trust score.
4. **Facility detail (`/facility/[id]`)**: Full profile and evidence view. Each claim shows `verified`, `claimed-only`, or `no-signal`, confidence, and the exact `text_span` highlighted in the corresponding `raw_fields` value. Notes and overrides are explicit planner inputs; the UI does not decide for them.
5. **Scenarios (`/scenarios`)**: Saved facilities, notes, and overrides persisted across sessions in Lakebase or Supabase/PostGIS.

## Coverage semantics

Coverage status is always one of:

- `verified_coverage`: corroborated claims; green treatment
- `weak_coverage`: claimed-only evidence; amber treatment
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
  "capabilities": [
    {
      "name": "ICU",
      "status": "verified",
      "trust_score": 0.82,
      "confidence_level": "high",
      "evidence": [
        {
          "field": "description",
          "text_span": "10-bed ICU with ventilator support and 24/7 staffing",
          "type": "corroborating"
        }
      ]
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

## Intended folder structure

```text
frontend/
  app/
    page.tsx
    map/page.tsx
    facility/[id]/page.tsx
    scenarios/page.tsx
  components/
    CapabilitySelector.tsx
    RegionSelector.tsx
    MapView.tsx
    FacilityCard.tsx
    EvidenceView.tsx
  lib/
    mockData.ts
    api.ts
  public/geojson/
  AGENTS.md
```

Additional app-level files (layout, global styles, configuration, assets) may be added as required by Next.js.

## Design system direction

The visual language should feel like a premium civic intelligence product rather than a generic admin dashboard. Use a warm mineral/off-white canvas, deep ink and forest surfaces, a restrained verdigris accent, and semantic moss/amber/rust/stone coverage colors. Headings use a distinctive display face paired with a highly legible sans-serif UI face. Establish named tokens for color, type scale, spacing, radii, shadows, and motion in global styles/configuration. Prefer generous whitespace, crisp information hierarchy, quiet texture, restrained borders, and purposeful micro-interactions. Include hover/focus transitions and loading skeletons, while respecting reduced-motion preferences.

Accessibility requirements: visible keyboard focus, semantic labels, adequate contrast, non-color status cues, and touch targets of at least 44px.

## Geographic data rules

- Use district-level GeoJSON from a credible source such as DataMeet or Survey of India-derived shapefiles; record license/provenance when added.
- Do not source or fabricate PIN-level polygons.
- PIN is a facility filter and point-marker attribute only, not a choropleth boundary.
- Verify source district names/codes against backend region identifiers before production joining.

## Current progress

- [x] Project context and constraints recorded in this living document.
- [x] Design tokens and base application shell established (warm mineral canvas, forest/verdigris palette, Georgia display typography, responsive shell, focus and reduced-motion states).
- [x] Screen 1 selector built against India-consistent mock geography with cascading state → district → city → PIN controls and query-param navigation to `/map`.
- [x] Map and coverage legend built with MapLibre GL JS + Deck.gl, district selection, facility point markers, all four semantic statuses, and explicit diagonal hatching for `no_data`.
- [x] Facility list built inside the map flow with claim-status filtering, trust-score sorting, evidence previews, and explicit `no_data` vs confirmed-gap empty states.
- [x] Facility detail and evidence highlighting built with claim tabs, exact `text_span` highlighting inside `raw_fields`, confidence/trust context, completeness indicators, planner notes, and manual dispositions.
- [x] Scenario workspace implemented with create, rename, delete, shortlist removal, saved notes, overrides, and persistence across browser sessions via a versioned `localStorage` adapter behind `lib/api.ts`.
- [ ] Databricks Apps deployment configured and smoke-tested.

## Open decisions and risks

- Persistence provider: the functional mock uses browser `localStorage` through `lib/api.ts`. This is durable for the demo browser but is not shared or multi-user. Lakebase remains the preferred production provider; Supabase/PostGIS is the fallback once credentials and connectivity are available.
- Final facility and region list response envelopes need backend confirmation.
- Geography reference data and canonical state/district/city/PIN hierarchy need backend alignment.
- The example contract labels Punjab/Faisalabad with PIN `38000`, which is not an India-consistent location. Treat it as an opaque shape example; use India-consistent mock geography in the UI and confirm backend data quality expectations.
- Production GeoJSON source, license, simplification level, and join-key mapping remain to be chosen. `public/geojson/demo-districts.json` is a deliberately small rectangular demo fixture for interaction/state testing and must not be represented as authoritative district boundaries.
- Databricks Apps runtime environment variables, build command, health check, and persistent data connectivity need early validation.
- `/map` is the next implementation target; Screen 1 currently routes there but the route is intentionally not scaffolded ahead of the specified build order.
- Screen 1 verification: `npm run lint` and `npm run build` pass on Next.js 16.2.10; `/` is statically prerendered and standalone output is enabled.
- Dependency audit after upgrading from vulnerable Next.js 16.1.6 to 16.2.10 reports two moderate findings for Next.js's bundled PostCSS `<8.5.10`. npm offers only an invalid breaking downgrade (`next@9.3.3`) via `audit fix --force`; do not apply it. Recheck when Next.js ships a release bundling patched PostCSS.
- Full frontend verification on 2026-07-19: `npm run lint` and `npm run build` pass. Dev-server HTTP checks returned 200 for `/`, `/map?capability=ICU`, `/facility/f_00123?capability=ICU`, and `/scenarios`, with no Next error markers or server stderr. Browser automation could not run because the `agent-browser` CLI is unavailable in the environment; manually verify map clicks, responsive layout, and localStorage reload behavior before demo.
- Git/GitHub work is explicitly paused by the user until the frontend is functionally complete. Do not commit, configure remotes, push, or modify authorship unless the user explicitly resumes that work.

## Working conventions

- Read this file at the start of every frontend session.
- Update it after every meaningful screen, API contract, design, deployment, persistence, or blocker change.
- Work only inside `frontend/`; do not touch `/backend`.
- Keep backend/mock switching isolated to `lib/api.ts`.
- Preserve evidence, confidence, and uncertainty in every relevant UI state.
- When the user explicitly resumes Git work, make small focused commits using their Git identity with no AI attribution or co-author lines. Until then, make no Git/GitHub changes.
