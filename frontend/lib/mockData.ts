export const capabilities = ["ICU", "Maternity", "Emergency", "Oncology", "Trauma", "NICU"] as const;
export type CapabilityName = (typeof capabilities)[number];

export type GeographyOption = {
  state: string;
  districts: Array<{ name: string; cities: Array<{ name: string; pins: string[] }> }>;
};

export const geographies: GeographyOption[] = [
  { state: "Karnataka", districts: [
    { name: "Bengaluru Urban", cities: [{ name: "Bengaluru", pins: ["560001", "560034", "560068"] }] },
    { name: "Mysuru", cities: [{ name: "Mysuru", pins: ["570001", "570015"] }] },
  ] },
  { state: "Maharashtra", districts: [
    { name: "Mumbai City", cities: [{ name: "Mumbai", pins: ["400001", "400008"] }] },
    { name: "Pune", cities: [{ name: "Pune", pins: ["411001", "411038"] }, { name: "Pimpri-Chinchwad", pins: ["411018", "411044"] }] },
  ] },
  { state: "Odisha", districts: [
    { name: "Khordha", cities: [{ name: "Bhubaneswar", pins: ["751001", "751024"] }] },
    { name: "Cuttack", cities: [{ name: "Cuttack", pins: ["753001", "753014"] }] },
  ] },
  { state: "Tamil Nadu", districts: [
    { name: "Chennai", cities: [{ name: "Chennai", pins: ["600001", "600020"] }] },
    { name: "Coimbatore", cities: [{ name: "Coimbatore", pins: ["641001", "641018"] }] },
  ] },
];

export type ClaimStatus = "verified" | "claimed-only" | "no-signal";
export type ConfidenceLevel = "high" | "medium" | "low";
export type CoverageStatus = "verified_coverage" | "weak_coverage" | "no_facility" | "no_data";
export type Evidence = { field: string; text_span: string; type: "corroborating" | "claim" | "absence" };
export type CapabilityClaim = { name: string; status: ClaimStatus; trust_score: number; confidence_level: ConfidenceLevel; evidence: Evidence[] };
export type Facility = {
  facility_id: string;
  name: string;
  location: { state: string; district: string; city: string; pin: string; lat: number; lon: number };
  capabilities: CapabilityClaim[];
  raw_fields: { description: string; procedure: string; equipment: string; numberDoctors: number | null; capacity: number | null; yearEstablished: string | null };
  data_completeness: { capacity_reported: boolean; doctors_reported: boolean };
};

export type RegionCoverage = {
  region_id: string;
  region_name: string;
  state: string;
  level: "district";
  capability_queried: string;
  coverage_status: CoverageStatus;
  facility_count: number;
  avg_trust_score: number;
};

const baseFacilities: Omit<Facility, "capabilities">[] = [
  { facility_id: "f_00123", name: "Victoria District Hospital", location: { state: "Karnataka", district: "Bengaluru Urban", city: "Bengaluru", pin: "560001", lat: 12.9634, lon: 77.5738 }, raw_fields: { description: "District referral centre with a 10-bed ICU with ventilator support and 24/7 staffing. A neonatal intensive care wing is listed in the annual report.", procedure: "Critical care, emergency stabilisation, maternity and neonatal referral procedures.", equipment: "Ventilators, multiparameter monitors and neonatal warmers were recorded in the 2025 equipment audit.", numberDoctors: null, capacity: 280, yearEstablished: "1900" }, data_completeness: { capacity_reported: true, doctors_reported: false } },
  { facility_id: "f_00456", name: "St. Martha’s Medical Centre", location: { state: "Karnataka", district: "Bengaluru Urban", city: "Bengaluru", pin: "560034", lat: 12.9279, lon: 77.6271 }, raw_fields: { description: "The hospital website describes ICU and round-the-clock emergency services.", procedure: "Emergency medicine and general surgery are listed; staffing hours are not specified.", equipment: "Ventilator support claimed in a provider directory; no current inventory was supplied.", numberDoctors: 42, capacity: 180, yearEstablished: "1988" }, data_completeness: { capacity_reported: true, doctors_reported: true } },
  { facility_id: "f_00789", name: "Kaveri Women & Children’s Hospital", location: { state: "Karnataka", district: "Mysuru", city: "Mysuru", pin: "570015", lat: 12.2958, lon: 76.6394 }, raw_fields: { description: "Dedicated maternity hospital advertising NICU support and high-risk obstetric care.", procedure: "Caesarean delivery and neonatal stabilisation are listed.", equipment: "No independently dated equipment inventory was available.", numberDoctors: 18, capacity: 90, yearEstablished: "2007" }, data_completeness: { capacity_reported: true, doctors_reported: true } },
  { facility_id: "f_01011", name: "Sahyadri Institute of Medical Sciences", location: { state: "Maharashtra", district: "Pune", city: "Pune", pin: "411001", lat: 18.5204, lon: 73.8567 }, raw_fields: { description: "Tertiary centre with a verified trauma unit, critical care block, oncology day care and emergency department.", procedure: "Trauma surgery, chemotherapy and intensive care procedures were present in the accreditation record.", equipment: "CT, ventilators and infusion systems matched the latest accreditation annexure.", numberDoctors: 86, capacity: 420, yearEstablished: "1996" }, data_completeness: { capacity_reported: true, doctors_reported: true } },
  { facility_id: "f_01212", name: "Harbour General Hospital", location: { state: "Maharashtra", district: "Mumbai City", city: "Mumbai", pin: "400008", lat: 18.9633, lon: 72.8331 }, raw_fields: { description: "Public general hospital listing emergency, maternity and ICU services.", procedure: "Emergency and obstetric procedures appear in the service directory.", equipment: "The source does not include a dated critical-care inventory.", numberDoctors: null, capacity: 310, yearEstablished: "1954" }, data_completeness: { capacity_reported: true, doctors_reported: false } },
  { facility_id: "f_02020", name: "Kalinga Regional Medical Centre", location: { state: "Odisha", district: "Khordha", city: "Bhubaneswar", pin: "751024", lat: 20.2961, lon: 85.8245 }, raw_fields: { description: "Regional referral facility with emergency and maternity departments; ICU appears in the provider’s self-description.", procedure: "Emergency stabilisation and obstetric surgery listed.", equipment: "No corroborating ICU equipment source was found in the indexed material.", numberDoctors: 34, capacity: null, yearEstablished: "2002" }, data_completeness: { capacity_reported: false, doctors_reported: true } },
  { facility_id: "f_03030", name: "Marina Cancer & Critical Care Centre", location: { state: "Tamil Nadu", district: "Chennai", city: "Chennai", pin: "600020", lat: 13.0067, lon: 80.2573 }, raw_fields: { description: "Accredited oncology centre with a critical care unit and 24-hour emergency response.", procedure: "Medical oncology, radiation oncology and intensive care procedures verified through accreditation.", equipment: "Linear accelerator, ventilators and infusion pumps appear in the accreditation inventory.", numberDoctors: 73, capacity: 260, yearEstablished: "1999" }, data_completeness: { capacity_reported: true, doctors_reported: true } },
];

const claims: Record<string, CapabilityClaim[]> = {
  f_00123: [
    { name: "ICU", status: "verified", trust_score: 0.82, confidence_level: "high", evidence: [{ field: "description", text_span: "10-bed ICU with ventilator support and 24/7 staffing", type: "corroborating" }] },
    { name: "NICU", status: "verified", trust_score: 0.76, confidence_level: "high", evidence: [{ field: "equipment", text_span: "neonatal warmers were recorded in the 2025 equipment audit", type: "corroborating" }] },
    { name: "Maternity", status: "claimed-only", trust_score: 0.61, confidence_level: "medium", evidence: [{ field: "procedure", text_span: "maternity and neonatal referral procedures", type: "claim" }] },
  ],
  f_00456: [
    { name: "ICU", status: "claimed-only", trust_score: 0.58, confidence_level: "medium", evidence: [{ field: "description", text_span: "hospital website describes ICU", type: "claim" }] },
    { name: "Emergency", status: "claimed-only", trust_score: 0.55, confidence_level: "medium", evidence: [{ field: "description", text_span: "round-the-clock emergency services", type: "claim" }] },
  ],
  f_00789: [
    { name: "Maternity", status: "verified", trust_score: 0.79, confidence_level: "high", evidence: [{ field: "procedure", text_span: "Caesarean delivery and neonatal stabilisation", type: "corroborating" }] },
    { name: "NICU", status: "claimed-only", trust_score: 0.49, confidence_level: "low", evidence: [{ field: "description", text_span: "advertising NICU support", type: "claim" }] },
  ],
  f_01011: [
    { name: "ICU", status: "verified", trust_score: 0.91, confidence_level: "high", evidence: [{ field: "procedure", text_span: "intensive care procedures were present in the accreditation record", type: "corroborating" }] },
    { name: "Trauma", status: "verified", trust_score: 0.94, confidence_level: "high", evidence: [{ field: "description", text_span: "verified trauma unit", type: "corroborating" }] },
    { name: "Oncology", status: "verified", trust_score: 0.84, confidence_level: "high", evidence: [{ field: "procedure", text_span: "chemotherapy", type: "corroborating" }] },
    { name: "Emergency", status: "verified", trust_score: 0.88, confidence_level: "high", evidence: [{ field: "description", text_span: "emergency department", type: "corroborating" }] },
  ],
  f_01212: [
    { name: "ICU", status: "claimed-only", trust_score: 0.52, confidence_level: "low", evidence: [{ field: "description", text_span: "listing emergency, maternity and ICU services", type: "claim" }] },
    { name: "Maternity", status: "verified", trust_score: 0.72, confidence_level: "medium", evidence: [{ field: "procedure", text_span: "obstetric procedures appear in the service directory", type: "corroborating" }] },
    { name: "Emergency", status: "verified", trust_score: 0.74, confidence_level: "medium", evidence: [{ field: "procedure", text_span: "Emergency and obstetric procedures", type: "corroborating" }] },
  ],
  f_02020: [
    { name: "ICU", status: "claimed-only", trust_score: 0.44, confidence_level: "low", evidence: [{ field: "description", text_span: "ICU appears in the provider’s self-description", type: "claim" }] },
    { name: "Emergency", status: "verified", trust_score: 0.69, confidence_level: "medium", evidence: [{ field: "procedure", text_span: "Emergency stabilisation", type: "corroborating" }] },
    { name: "Maternity", status: "claimed-only", trust_score: 0.57, confidence_level: "medium", evidence: [{ field: "description", text_span: "emergency and maternity departments", type: "claim" }] },
  ],
  f_03030: [
    { name: "Oncology", status: "verified", trust_score: 0.93, confidence_level: "high", evidence: [{ field: "procedure", text_span: "Medical oncology, radiation oncology", type: "corroborating" }] },
    { name: "ICU", status: "verified", trust_score: 0.86, confidence_level: "high", evidence: [{ field: "equipment", text_span: "ventilators and infusion pumps appear in the accreditation inventory", type: "corroborating" }] },
    { name: "Emergency", status: "verified", trust_score: 0.81, confidence_level: "high", evidence: [{ field: "description", text_span: "24-hour emergency response", type: "corroborating" }] },
  ],
};

export const facilities: Facility[] = baseFacilities.map((facility) => ({ ...facility, capabilities: claims[facility.facility_id] }));

const coverageMatrix: Record<CapabilityName, CoverageStatus[]> = {
  ICU: ["verified_coverage", "weak_coverage", "verified_coverage", "weak_coverage", "weak_coverage", "no_data", "verified_coverage", "no_facility"],
  Maternity: ["weak_coverage", "verified_coverage", "no_facility", "verified_coverage", "weak_coverage", "no_data", "no_data", "weak_coverage"],
  Emergency: ["weak_coverage", "no_data", "verified_coverage", "verified_coverage", "verified_coverage", "no_facility", "verified_coverage", "weak_coverage"],
  Oncology: ["no_data", "no_facility", "verified_coverage", "no_data", "no_facility", "no_data", "verified_coverage", "weak_coverage"],
  Trauma: ["no_data", "no_facility", "verified_coverage", "no_data", "weak_coverage", "no_facility", "weak_coverage", "no_data"],
  NICU: ["verified_coverage", "weak_coverage", "no_data", "no_facility", "no_data", "no_data", "weak_coverage", "verified_coverage"],
};

const regionDefs = [
  ["KA-BU", "Bengaluru Urban", "Karnataka"], ["KA-MY", "Mysuru", "Karnataka"],
  ["MH-PU", "Pune", "Maharashtra"], ["MH-MC", "Mumbai City", "Maharashtra"],
  ["OD-KH", "Khordha", "Odisha"], ["OD-CT", "Cuttack", "Odisha"],
  ["TN-CH", "Chennai", "Tamil Nadu"], ["TN-CO", "Coimbatore", "Tamil Nadu"],
] as const;

export const regionCoverage: RegionCoverage[] = capabilities.flatMap((capability) =>
  regionDefs.map(([region_id, region_name, state], index) => {
    const matching = facilities.filter((f) => f.location.district === region_name && f.capabilities.some((c) => c.name === capability));
    const scores = matching.flatMap((f) => f.capabilities.filter((c) => c.name === capability).map((c) => c.trust_score));
    return { region_id, region_name, state, level: "district", capability_queried: capability, coverage_status: coverageMatrix[capability][index], facility_count: matching.length, avg_trust_score: scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : 0 };
  }),
);

export type ScenarioNote = { facility_id: string; note: string; timestamp: string };
export type ScenarioOverride = { facility_id: string; capability: string; value: "accept" | "needs-review" | "reject"; reason: string; timestamp: string };
export type Scenario = { scenario_id: string; name: string; shortlist: string[]; notes: ScenarioNote[]; overrides: ScenarioOverride[]; created_at: string; updated_at?: string };

export const initialScenarios: Scenario[] = [{ scenario_id: "s_001", name: "ICU gap review — Karnataka", shortlist: ["f_00123"], notes: [{ facility_id: "f_00123", note: "Confirm ventilator count by phone", timestamp: "2026-07-19T10:00:00Z" }], overrides: [], created_at: "2026-07-19T09:00:00Z" }];
