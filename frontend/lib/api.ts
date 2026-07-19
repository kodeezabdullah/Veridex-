import { capabilities, facilities, geographies, initialScenarios, normalizeStateName, type CapabilityName, type Facility, type RegionCoverage, type Scenario, type ScenarioNote, type ScenarioOverride } from "./mockData";

export type FacilityFilters = { capability?: string; state?: string; district?: string; city?: string; pin?: string };
export type AgentQueryResponse = {
  reply: string;
  capability: CapabilityName;
  region: { state: string | null; district: string | null };
  matched_facility_ids: string[];
};
const SCENARIO_KEY = "veridex.scenarios.v1";

export async function getFacilities(filters: FacilityFilters = {}): Promise<Facility[]> {
  return Promise.resolve(facilities.filter((facility) => (!filters.capability || facility.capabilities.some((claim) => claim.name === filters.capability)) && (!filters.state || facility.location.state === filters.state) && (!filters.district || facility.location.district === filters.district) && (!filters.city || facility.location.city === filters.city) && (!filters.pin || facility.location.pin === filters.pin)));
}

export async function getFacility(id: string): Promise<Facility | null> { return Promise.resolve(facilities.find((facility) => facility.facility_id === id) ?? null); }
export async function getRegionCoverage(capability: string): Promise<RegionCoverage[]> {
  if (typeof window === "undefined") throw new Error("Use getDistrictCoverage from api.server.ts during server rendering");
  const response = await fetch(`/api/coverage?capability=${encodeURIComponent(capability)}`);
  if (!response.ok) throw new Error(`Coverage request failed with ${response.status}`);
  return response.json() as Promise<RegionCoverage[]>;
}

export async function queryAgent(message: string): Promise<AgentQueryResponse> {
  await new Promise((resolve) => setTimeout(resolve, 600));
  const normalized = normalizeStateName(message);
  const capability = capabilities.find((item) => normalized.includes(item.toLowerCase())) ?? "ICU";
  const matchedDistrict = geographies.flatMap((item) => item.districts.map((district) => ({ state: item.state, district: district.name, cities: district.cities }))).find((item) => normalized.includes(item.district.toLowerCase()) || item.cities.some((city) => normalized.includes(city.name.toLowerCase())));
  const familiarState = geographies.find((item) => normalized.includes(normalizeStateName(item.state)))?.state;
  const matchedState = matchedDistrict?.state ?? familiarState ?? null;
  const district = matchedDistrict?.district ?? null;
  const matches = facilities.filter((facility) => facility.capabilities.some((claim) => claim.name === capability) && (!matchedState || normalizeStateName(facility.location.state) === normalizeStateName(matchedState)) && (!district || facility.location.district === district));
  const regionLabel = district ? `${district}, ${matchedState}` : matchedState ?? "the indexed districts";
  const evidenceSummary = matches.length === 0 ? `I found no indexed facilities matching ${capability} in ${regionLabel}. That may reflect a confirmed gap or insufficient data—select a district to inspect its evidence state.` : `Found ${matches.length} ${matches.length === 1 ? "facility" : "facilities"} with ${capability} signals in ${regionLabel}. I’ve focused the map and highlighted the matching facilities; open a marker to inspect trust and source evidence.`;
  return { reply: evidenceSummary, capability, region: { state: matchedState, district }, matched_facility_ids: matches.map((facility) => facility.facility_id) };
}

function readScenarios(): Scenario[] {
  if (typeof window === "undefined") return initialScenarios;
  const stored = window.localStorage.getItem(SCENARIO_KEY);
  if (!stored) { window.localStorage.setItem(SCENARIO_KEY, JSON.stringify(initialScenarios)); return initialScenarios; }
  try { return JSON.parse(stored) as Scenario[]; } catch { return initialScenarios; }
}
function writeScenarios(scenarios: Scenario[]) { if (typeof window !== "undefined") window.localStorage.setItem(SCENARIO_KEY, JSON.stringify(scenarios)); }

export async function getScenarios(): Promise<Scenario[]> { return Promise.resolve(readScenarios()); }
export async function createScenario(name: string): Promise<Scenario> { const scenarios = readScenarios(); const scenario: Scenario = { scenario_id: `s_${Date.now()}`, name, shortlist: [], notes: [], overrides: [], created_at: new Date().toISOString() }; writeScenarios([scenario, ...scenarios]); return scenario; }
export async function saveScenario(next: Scenario): Promise<Scenario> { const scenarios = readScenarios(); const saved = { ...next, updated_at: new Date().toISOString() }; writeScenarios(scenarios.some((item) => item.scenario_id === saved.scenario_id) ? scenarios.map((item) => item.scenario_id === saved.scenario_id ? saved : item) : [saved, ...scenarios]); return saved; }
export async function addFacilityToScenario(scenarioId: string, facilityId: string): Promise<Scenario> { const scenario = readScenarios().find((item) => item.scenario_id === scenarioId); if (!scenario) throw new Error("Scenario not found"); return saveScenario({ ...scenario, shortlist: scenario.shortlist.includes(facilityId) ? scenario.shortlist : [...scenario.shortlist, facilityId] }); }
export async function removeFacilityFromScenario(scenarioId: string, facilityId: string): Promise<Scenario> { const scenario = readScenarios().find((item) => item.scenario_id === scenarioId); if (!scenario) throw new Error("Scenario not found"); return saveScenario({ ...scenario, shortlist: scenario.shortlist.filter((id) => id !== facilityId), notes: scenario.notes.filter((note) => note.facility_id !== facilityId), overrides: scenario.overrides.filter((override) => override.facility_id !== facilityId) }); }
export async function addScenarioNote(scenarioId: string, note: ScenarioNote): Promise<Scenario> { const scenario = readScenarios().find((item) => item.scenario_id === scenarioId); if (!scenario) throw new Error("Scenario not found"); return saveScenario({ ...scenario, notes: [...scenario.notes.filter((item) => item.facility_id !== note.facility_id), note] }); }
export async function addScenarioOverride(scenarioId: string, override: ScenarioOverride): Promise<Scenario> { const scenario = readScenarios().find((item) => item.scenario_id === scenarioId); if (!scenario) throw new Error("Scenario not found"); return saveScenario({ ...scenario, overrides: [...scenario.overrides.filter((item) => !(item.facility_id === override.facility_id && item.capability === override.capability)), override] }); }
export async function deleteScenario(scenarioId: string): Promise<void> { writeScenarios(readScenarios().filter((item) => item.scenario_id !== scenarioId)); }
