import type {
  CapabilityClaim,
  ClaimStatus,
  ConfidenceLevel,
  Evidence,
  Facility,
  RegionCoverage,
  Scenario,
  ScenarioNote,
  ScenarioOverride,
} from "./types";

export type FacilityFilters = {
  capability?: string;
  state?: string;
  district?: string;
  city?: string;
  pin?: string;
};

type JsonRecord = Record<string, unknown>;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function asRecord(value: unknown): JsonRecord | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonRecord)
    : null;
}

function readString(record: JsonRecord, ...keys: string[]): string {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string") return value;
    if (typeof value === "number") return String(value);
  }
  return "";
}

function readNumber(record: JsonRecord, ...keys: string[]): number {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) {
      return Number(value);
    }
  }
  return 0;
}

function readNullableNumber(
  record: JsonRecord,
  ...keys: string[]
): number | null {
  for (const key of keys) {
    const value = record[key];
    if (value === null) return null;
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) {
      return Number(value);
    }
  }
  return null;
}

function readBoolean(record: JsonRecord, ...keys: string[]): boolean {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "boolean") return value;
    if (value === 1 || value === "true") return true;
    if (value === 0 || value === "false") return false;
  }
  return false;
}

function apiUrl(path: string): string {
  const publicBase = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(
    /\/$/,
    "",
  );
  if (typeof window !== "undefined") return `${publicBase}${path}`;

  const serverBase = (
    process.env.VERIDEX_API_BASE_URL ?? publicBase
  ).replace(/\/$/, "");
  if (!serverBase) {
    throw new ApiError(
      "Real backend is not configured. Set VERIDEX_API_BASE_URL for server requests.",
    );
  }
  return `${serverBase}${path}`;
}

async function requestJson(
  path: string,
  init: RequestInit = {},
): Promise<unknown> {
  const response = await fetch(apiUrl(path), {
    ...init,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    const detail = (await response.text()).trim();
    throw new ApiError(
      `API request failed (${response.status})${detail ? `: ${detail}` : ""}`,
      response.status,
    );
  }
  if (response.status === 204) return null;
  return response.json() as Promise<unknown>;
}

function unwrapList(payload: unknown, key: string): unknown[] {
  if (Array.isArray(payload)) return payload;
  const record = asRecord(payload);
  return record && Array.isArray(record[key]) ? record[key] : [];
}

function normalizeClaimStatus(value: string): ClaimStatus {
  const normalized = value.toLowerCase().replace(/-/g, "_");
  if (normalized === "verified" || normalized === "likely") return normalized;
  if (normalized === "weak_signal" || normalized === "claimed_only") {
    return "weak_signal";
  }
  return "no_signal";
}

function confidenceFor(status: ClaimStatus): ConfidenceLevel {
  if (status === "verified") return "high";
  if (status === "likely") return "medium";
  return "low";
}

function normalizeEvidence(
  value: unknown,
  status: ClaimStatus,
  fallbackRecord: JsonRecord,
): Evidence[] {
  const entries = Array.isArray(value) ? value : [];
  const normalized = entries
    .map(asRecord)
    .filter((item): item is JsonRecord => item !== null)
    .map((item) => ({
      field: readString(item, "field", "field_source"),
      text_span: readString(item, "text_span"),
      type:
        status === "verified"
          ? ("corroborating" as const)
          : status === "no_signal"
            ? ("absence" as const)
            : ("claim" as const),
    }))
    .filter((item) => item.field || item.text_span);

  if (normalized.length) return normalized;
  const field = readString(fallbackRecord, "field_source", "field");
  const textSpan = readString(fallbackRecord, "text_span");
  return field || textSpan
    ? [
        {
          field,
          text_span: textSpan,
          type:
            status === "verified"
              ? "corroborating"
              : status === "no_signal"
                ? "absence"
                : "claim",
        },
      ]
    : [];
}

function normalizeClaim(value: unknown): CapabilityClaim | null {
  const record = asRecord(value);
  if (!record) return null;
  const name = readString(record, "name", "capability");
  if (!name) return null;
  const status = normalizeClaimStatus(
    readString(record, "status", "evidence_status"),
  );
  const explicitPct = readNullableNumber(record, "trust_score_pct");
  const rawTrust = readNumber(record, "trust_score");
  const trustScorePct = Math.max(
    0,
    Math.min(100, Math.round(explicitPct ?? rawTrust * 100)),
  );
  return {
    name,
    status,
    trust_score: trustScorePct / 100,
    trust_score_pct: trustScorePct,
    confidence_level:
      (readString(record, "confidence_level") as ConfidenceLevel) ||
      confidenceFor(status),
    evidence: normalizeEvidence(record.evidence, status, record),
    confirm_message: readString(record, "confirm_message"),
  };
}

function claimInputs(envelope: JsonRecord, facility: JsonRecord): unknown[] {
  for (const candidate of [
    envelope.capability_evidence,
    envelope.capabilities,
    facility.capability_evidence,
    facility.capabilities,
  ]) {
    if (Array.isArray(candidate)) return candidate;
  }
  return readString(envelope, "capability") || readString(facility, "capability")
    ? [envelope]
    : [];
}

function normalizeFacility(value: unknown): Facility | null {
  const envelope = asRecord(value);
  if (!envelope) return null;
  const facility = asRecord(envelope.facility) ?? envelope;
  const location = asRecord(facility.location) ?? {};
  const rawFields = asRecord(facility.raw_fields) ?? facility;
  const completeness = asRecord(facility.data_completeness) ?? facility;
  const facilityId = readString(facility, "facility_id", "unique_id");
  if (!facilityId) return null;

  const normalizedClaims = claimInputs(envelope, facility)
    .map(normalizeClaim)
    .filter((claim): claim is CapabilityClaim => claim !== null);

  return {
    facility_id: facilityId,
    name: readString(facility, "name") || "Name unavailable",
    location: {
      state: readString(location, "state") || readString(facility, "nfhs_state_ut"),
      district:
        readString(location, "district") ||
        readString(facility, "nfhs_district_name"),
      city: readString(location, "city") || readString(facility, "address_city"),
      pin:
        readString(location, "pin") ||
        readString(facility, "pin", "pincode", "address_pincode"),
      lat: readNumber(location, "lat") || readNumber(facility, "latitude", "lat"),
      lon: readNumber(location, "lon") || readNumber(facility, "longitude", "lon"),
    },
    capabilities: normalizedClaims,
    raw_fields: {
      description: readString(rawFields, "description"),
      procedure: readString(rawFields, "procedure"),
      equipment: readString(rawFields, "equipment"),
      numberDoctors: readNullableNumber(
        rawFields,
        "numberDoctors",
        "numberDoctors_clean",
      ),
      capacity: readNullableNumber(rawFields, "capacity", "capacity_clean"),
      yearEstablished:
        readString(rawFields, "yearEstablished", "year_established") || null,
    },
    data_completeness: {
      capacity_reported: readBoolean(completeness, "capacity_reported"),
      doctors_reported: readBoolean(completeness, "doctors_reported"),
    },
  };
}

function mergeFacilityRows(rows: unknown[]): Facility[] {
  const facilities = new Map<string, Facility>();
  for (const row of rows) {
    const facility = normalizeFacility(row);
    if (!facility) continue;
    const existing = facilities.get(facility.facility_id);
    if (!existing) {
      facilities.set(facility.facility_id, facility);
      continue;
    }
    const claims = new Map(
      existing.capabilities.map((claim) => [claim.name, claim]),
    );
    for (const claim of facility.capabilities) claims.set(claim.name, claim);
    facilities.set(facility.facility_id, {
      ...existing,
      capabilities: Array.from(claims.values()),
    });
  }
  return Array.from(facilities.values()).filter(
    (facility) => facility.capabilities.length > 0,
  );
}

function normalizeCoverage(value: unknown): RegionCoverage | null {
  const record = asRecord(value);
  if (!record) return null;
  const regionId = readString(record, "region_id");
  const regionName = readString(record, "region_name");
  if (!regionId || !regionName) return null;
  const pct = readNullableNumber(record, "avg_trust_score_pct");
  const legacyScore = readNumber(record, "avg_trust_score");
  return {
    region_id: regionId,
    region_name: regionName,
    state: readString(record, "state"),
    level: "district",
    capability_queried: readString(record, "capability_queried"),
    coverage_status: readString(
      record,
      "coverage_status",
    ) as RegionCoverage["coverage_status"],
    facility_count: Math.round(readNumber(record, "facility_count")),
    avg_trust_score_pct: Math.round(pct ?? legacyScore * 100),
  };
}

function normalizeScenario(value: unknown): Scenario | null {
  const record = asRecord(value);
  if (!record) return null;
  const scenarioId = readString(record, "scenario_id");
  if (!scenarioId) return null;
  const shortlistSource = Array.isArray(record.shortlist)
    ? record.shortlist
    : Array.isArray(record.shortlist_items)
      ? record.shortlist_items
      : [];
  const notesSource = Array.isArray(record.notes) ? record.notes : [];
  const overridesSource = Array.isArray(record.overrides) ? record.overrides : [];
  return {
    scenario_id: scenarioId,
    name: readString(record, "name"),
    shortlist: shortlistSource
      .map((item) => {
        const entry = asRecord(item);
        return entry
          ? readString(entry, "facility_id", "facility_unique_id")
          : String(item ?? "");
      })
      .filter(Boolean),
    notes: notesSource
      .map(asRecord)
      .filter((item): item is JsonRecord => item !== null)
      .map((item) => ({
        facility_id: readString(item, "facility_id", "facility_unique_id"),
        note: readString(item, "note", "note_text"),
        timestamp: readString(item, "timestamp", "created_at"),
      })),
    overrides: overridesSource
      .map(asRecord)
      .filter((item): item is JsonRecord => item !== null)
      .map((item) => ({
        facility_id: readString(item, "facility_id", "facility_unique_id"),
        capability: readString(item, "capability"),
        value: (readString(item, "value") || "needs-review") as
          | "accept"
          | "needs-review"
          | "reject",
        reason: readString(item, "reason", "override_note"),
        timestamp: readString(item, "timestamp", "created_at"),
      })),
    created_at: readString(record, "created_at"),
    updated_at: readString(record, "updated_at") || undefined,
  };
}

function queryString(values: Record<string, string | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value) params.set(key, value);
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

export async function getFacilities(
  filters: FacilityFilters = {},
): Promise<Facility[]> {
  const payload = await requestJson(
    `/api/facilities${queryString({
      capability: filters.capability,
      state: filters.state,
      district: filters.district,
      city: filters.city,
      pin: filters.pin,
    })}`,
  );
  return mergeFacilityRows(unwrapList(payload, "facilities"));
}

export async function getFacility(id: string): Promise<Facility | null> {
  try {
    return normalizeFacility(
      await requestJson(`/api/facility/${encodeURIComponent(id)}`),
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export async function getRegionCoverage(
  capability: string,
): Promise<RegionCoverage[]> {
  const payload = await requestJson(
    `/api/regions/coverage${queryString({ capability })}`,
  );
  return unwrapList(payload, "regions")
    .map(normalizeCoverage)
    .filter((region): region is RegionCoverage => region !== null);
}

export async function getScenarios(): Promise<Scenario[]> {
  const payload = await requestJson("/api/scenarios");
  return unwrapList(payload, "scenarios")
    .map(normalizeScenario)
    .filter((scenario): scenario is Scenario => scenario !== null);
}

export async function createScenario(name: string): Promise<Scenario> {
  const scenario = normalizeScenario(
    await requestJson("/api/scenarios", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  );
  if (!scenario) throw new ApiError("Scenario API returned an invalid record.");
  return scenario;
}

async function refreshedScenario(scenarioId: string): Promise<Scenario> {
  const scenario = (await getScenarios()).find(
    (item) => item.scenario_id === scenarioId,
  );
  if (!scenario) throw new ApiError("Scenario was not returned after the update.");
  return scenario;
}

async function scenarioMutation(
  scenarioId: string,
  path: string,
  init: RequestInit,
): Promise<Scenario> {
  const payload = await requestJson(path, init);
  return normalizeScenario(payload) ?? refreshedScenario(scenarioId);
}

export async function saveScenario(next: Scenario): Promise<Scenario> {
  return scenarioMutation(next.scenario_id, `/api/scenarios/${next.scenario_id}`, {
    method: "PATCH",
    body: JSON.stringify({ name: next.name }),
  });
}

export async function addFacilityToScenario(
  scenarioId: string,
  facilityId: string,
): Promise<Scenario> {
  return scenarioMutation(
    scenarioId,
    `/api/scenarios/${scenarioId}/shortlist`,
    {
      method: "POST",
      body: JSON.stringify({ facility_unique_id: facilityId }),
    },
  );
}

export async function removeFacilityFromScenario(
  scenarioId: string,
  facilityId: string,
): Promise<Scenario> {
  return scenarioMutation(
    scenarioId,
    `/api/scenarios/${scenarioId}/shortlist/${encodeURIComponent(facilityId)}`,
    { method: "DELETE" },
  );
}

export async function addScenarioNote(
  scenarioId: string,
  note: ScenarioNote,
): Promise<Scenario> {
  return scenarioMutation(scenarioId, `/api/scenarios/${scenarioId}/notes`, {
    method: "POST",
    body: JSON.stringify({
      facility_unique_id: note.facility_id,
      note_text: note.note,
    }),
  });
}

export async function addScenarioOverride(
  scenarioId: string,
  override: ScenarioOverride,
): Promise<Scenario> {
  return scenarioMutation(scenarioId, `/api/scenarios/${scenarioId}/overrides`, {
    method: "POST",
    body: JSON.stringify({
      facility_unique_id: override.facility_id,
      capability: override.capability,
      value: override.value,
      override_note: override.reason,
    }),
  });
}

export async function deleteScenario(scenarioId: string): Promise<void> {
  await requestJson(`/api/scenarios/${scenarioId}`, { method: "DELETE" });
}
