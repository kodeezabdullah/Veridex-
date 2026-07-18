import districtGeoJson from "@/public/geojson/demo-districts.json";
import { capabilities, facilities, geographies, initialScenarios, regionCoverage, type CapabilityName, type Facility, type GeographyOption, type Scenario, type ScenarioNote, type ScenarioOverride } from "./mockData";

export type SelectorOptions = { capabilities: readonly CapabilityName[]; geographies: GeographyOption[] };
export type FacilityFilters = { capability?: string; state?: string; district?: string; city?: string; pin?: string };
const SCENARIO_KEY = "veridex.scenarios.v1";

export async function getSelectorOptions(): Promise<SelectorOptions> { return Promise.resolve({ capabilities, geographies }); }
export async function getCoverageGeoJson() { return Promise.resolve(districtGeoJson); }

export async function getFacilities(filters: FacilityFilters = {}): Promise<Facility[]> {
  return Promise.resolve(facilities.filter((facility) => (!filters.capability || facility.capabilities.some((claim) => claim.name === filters.capability)) && (!filters.state || facility.location.state === filters.state) && (!filters.district || facility.location.district === filters.district) && (!filters.city || facility.location.city === filters.city) && (!filters.pin || facility.location.pin === filters.pin)));
}

export async function getFacility(id: string): Promise<Facility | null> { return Promise.resolve(facilities.find((facility) => facility.facility_id === id) ?? null); }
export async function getRegionCoverage(capability: string) { return Promise.resolve(regionCoverage.filter((region) => region.capability_queried === capability)); }

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
