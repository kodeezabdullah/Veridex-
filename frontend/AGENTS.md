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

1. **Chat-driven evidence map (`/`)**: The full-screen MapLibre + Deck.gl map is the primary landing view with a docked conversational agent. Natural-language queries replace the retired categorical selector. A response changes capability coverage, smoothly flies to matching districts, emphasizes matched facility markers, and remains visible in conversation history.
2. **Facility marker popup (within `/`)**: Clicking a marker opens a custom evidence card with facility name, claim/trust status, exact evidence snippet, and a link to the full evidence record. Coverage polygons are real district-level ADM2 boundaries.
3. **Facility list (`/map`)**: The existing list-oriented map workspace remains available as a secondary view. Facility cards show name, claimed capabilities, evidence-aware trust status, and trust score with filtering and sorting.
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

### `queryAgent(message: string)` — mocked integration seam

The landing chat calls only `lib/api.ts::queryAgent`. The current implementation waits 600ms and uses keyword matching for capability, state, district, and city against mock data. Replace only this function’s internals when the backend agent is ready; callers depend on this exact response:

```json
{
  "reply": "Found 2 facilities with ICU signals in Karnataka. I’ve focused the map and highlighted the matching facilities; open a marker to inspect trust and source evidence.",
  "capability": "ICU",
  "region": {
    "state": "Karnataka",
    "district": null
  },
  "matched_facility_ids": ["f_00123", "f_00456"]
}
```

`capability` is one of the canonical capability names. `state` and `district` are nullable canonical geography names. `matched_facility_ids` contains only facility IDs already represented by the facility contract. The reply must describe evidence found without making a planning decision.

## Intended folder structure

```text
frontend/
  app/
    page.tsx
    map/page.tsx
    facility/[id]/page.tsx
    scenarios/page.tsx
  components/
    ChatMapExperience.tsx
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

- The active boundary source is `public/geojson/geoBoundaries-IND-ADM2_simplified.geojson`, containing 735 simplified India district features from the official geoBoundaries gbOpen ADM2 release (API metadata reports 736 units). `shapeName` is the district coverage join key; both Polygon and MultiPolygon geometry are supported.
- Source provenance: geoBoundaries boundary `IND-ADM2-76128533`, represented year 2021, source Pathways Data Pvt. Ltd./lgdirectory.gov.in, Open Data Commons Open Database License 1.0.
- Do not source or fabricate PIN-level polygons.
- PIN is a facility filter and point-marker attribute only, not a choropleth boundary.
- Verify source district names/codes against backend region identifiers before production joining.

## Current progress

- [x] Project context and constraints recorded in this living document.
- [x] Design tokens and base application shell established (warm mineral canvas, forest/verdigris palette, Georgia display typography, responsive shell, focus and reduced-motion states).
- [x] Original categorical Screen 1 retired and replaced by a full-screen chat-driven evidence map on `/`, with conversational history, suggestions, typing state, mock agent response, animated regional focus, matched markers, and premium facility popups.
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
- Real simplified India ADM2 geometry is active and keyed by exact district `shapeName`. Explicit aliases bridge source names such as `Bangalore`, `Mysore`, and `Mumbai` to mock-data names `Bengaluru Urban`, `Mysuru`, and `Mumbai City`. Retain geoBoundaries ODbL attribution in public deployment.
- Databricks Apps runtime environment variables, build command, health check, and persistent data connectivity need early validation.
- `/map` remains as a secondary facility-list workspace; `/` is the primary map and agent experience.
- Screen 1 verification: `npm run lint` and `npm run build` pass on Next.js 16.2.10; `/` is statically prerendered and standalone output is enabled.
- Dependency audit after upgrading from vulnerable Next.js 16.1.6 to 16.2.10 reports two moderate findings for Next.js's bundled PostCSS `<8.5.10`. npm offers only an invalid breaking downgrade (`next@9.3.3`) via `audit fix --force`; do not apply it. Recheck when Next.js ships a release bundling patched PostCSS.
- Full frontend verification on 2026-07-19: `npm run lint` and `npm run build` pass. Dev-server HTTP checks returned 200 for `/`, `/map?capability=ICU`, `/facility/f_00123?capability=ICU`, and `/scenarios`, with no Next error markers or server stderr. Browser automation could not run because the `agent-browser` CLI is unavailable in the environment; manually verify map clicks, responsive layout, and localStorage reload behavior before demo.
- Map rendering fix verified on 2026-07-19 through Chrome DevTools Protocol: `.map-canvas`, the MapLibre canvas, and `.deck-canvas` all inherit the full `.map-stage` height (560px at the narrow breakpoint; 708px at 1440×900). The map uses no-key CARTO Positron raster tiles, native MapLibre GeoJSON fill/pattern/border layers for coverage, a generated hatch pattern for `no_data`, and Deck.gl facility markers. All sampled CARTO tiles returned HTTP 200 with no browser errors.
- Chat/map pivot verified on 2026-07-19 through Chrome DevTools Protocol at 1440×900. Querying “ICU coverage in Karnataka” produced the documented mock reply, retained the three-message conversation trail, flew to Karnataka’s coverage geometry, outlined the matching region, and enlarged two matched markers. Clicking `f_00456` opened a custom animated popup showing claimed-only, 58/100 trust, the evidence text “hospital website describes ICU,” and a working full-evidence link. No browser exceptions were observed; build and lint passed.
- ADM2 boundary pivot: coverage is generated for all 735 real district `shapeName` keys. Facility counts/trust aggregate by district; known claims produce verified/weak coverage and unmatched districts alternate deterministically between confirmed-gap and no-data. The four canonical colors are centralized in `lib/coverage.ts`. Natural-language state queries focus the indexed mock districts within that state; district/city queries focus the matching ADM2 shape. Default camera starts at `[78.9, 22.5]`, zoom 4, then responsively fits India-wide bounds with overlay-aware padding. The desktop chat column remains 460px and chat body/input/suggestion text was enlarged for readability.
- ADM2 browser verification on 2026-07-19: fresh loads at 1440x900 and 1024x900 showed the complete India extent with 735 district features, all four coverage statuses, two active map canvases, and no horizontal overflow. Rendered colors were `#4f8064`, `#d7a53f`, `#b4523e`, and `#9a9d97`; chat message/input text rendered at 13px and suggestion text at 11px. The coverage endpoint returned HTTP 200 and the Karnataka ICU query completed its animated district focus without browser exceptions.
- Matched query results use a two-tier map overlay: every matched facility receives an icon-only health-worker marker using `svg/health-worker-svgrepo-com.svg`, with compact screen-space collision offsets for nearby results. Names, trust state, and evidence remain hidden until selection. Selecting an icon or matched marker replaces it with the single rich evidence card; selecting another result swaps cards, while a map-background click restores the icon-only state. Motion handles keyed scale/fade transitions for both tiers.
- Two-tier popup verification on 2026-07-19: the `ICU coverage in Karnataka` flow rendered two compact previews (`Victoria District Hospital` and `St. Martha’s Medical Centre`). Selecting Victoria produced one remaining preview and one rich detail card; a map-background click restored both previews and removed the card. No Next.js error overlay appeared; production build and lint passed.
- Git/GitHub work is explicitly paused by the user until the frontend is functionally complete. Do not commit, configure remotes, push, or modify authorship unless the user explicitly resumes that work.

## Working conventions

- Read this file at the start of every frontend session.
- Update it after every meaningful screen, API contract, design, deployment, persistence, or blocker change.
- Work only inside `frontend/`; do not touch `/backend`.
- Keep backend/mock switching isolated to `lib/api.ts`.
- Preserve evidence, confidence, and uncertainty in every relevant UI state.
- When the user explicitly resumes Git work, make small focused commits using their Git identity with no AI attribution or co-author lines. Until then, make no Git/GitHub changes.
