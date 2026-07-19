export const capabilities = [
  "ICU",
  "NICU",
  "Emergency",
  "Maternity",
  "Oncology",
  "Trauma",
] as const;

export type CapabilityName = (typeof capabilities)[number];
export type ClaimStatus = "verified" | "likely" | "weak_signal" | "no_signal";
export type ConfidenceLevel = "high" | "medium" | "low";
export type CoverageStatus =
  | "verified_coverage"
  | "weak_coverage"
  | "no_facility"
  | "no_data";

export type Evidence = {
  field: string;
  text_span: string;
  type: "corroborating" | "claim" | "absence";
};

export type CapabilityClaim = {
  name: string;
  status: ClaimStatus;
  trust_score: number;
  trust_score_pct: number;
  confidence_level: ConfidenceLevel;
  evidence: Evidence[];
  confirm_message: string;
};

export type Facility = {
  facility_id: string;
  name: string;
  location: {
    state: string;
    district: string;
    city: string;
    pin: string;
    lat: number;
    lon: number;
  };
  capabilities: CapabilityClaim[];
  raw_fields: {
    description: string;
    procedure: string;
    equipment: string;
    numberDoctors: number | null;
    capacity: number | null;
    yearEstablished: string | null;
  };
  data_completeness: {
    capacity_reported: boolean;
    doctors_reported: boolean;
  };
};

export type RegionCoverage = {
  region_id: string;
  region_name: string;
  state: string;
  level: "district";
  capability_queried: string;
  coverage_status: CoverageStatus;
  facility_count: number;
  avg_trust_score_pct: number;
};

export type ScenarioNote = {
  facility_id: string;
  note: string;
  timestamp: string;
};

export type ScenarioOverride = {
  facility_id: string;
  capability: string;
  value: "accept" | "needs-review" | "reject";
  reason: string;
  timestamp: string;
};

export type Scenario = {
  scenario_id: string;
  name: string;
  shortlist: string[];
  notes: ScenarioNote[];
  overrides: ScenarioOverride[];
  created_at: string;
  updated_at?: string;
};

export function normalizeName(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}
