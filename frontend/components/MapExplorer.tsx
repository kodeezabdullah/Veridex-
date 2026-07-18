"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { Facility, RegionCoverage } from "@/lib/mockData";
import { CoverageLegend, coverageLabels } from "./CoverageLegend";
import { FacilityCard } from "./FacilityCard";
import { MapView } from "./MapView";

type GeoCollection = Parameters<typeof MapView>[0]["geoJson"];

export function MapExplorer({ capability, initialDistrict, coverage, facilities, geoJson }: { capability: string; initialDistrict?: string; coverage: RegionCoverage[]; facilities: Facility[]; geoJson: GeoCollection }) {
  const router = useRouter(); const params = useSearchParams();
  const initial = coverage.find((item) => item.region_name === initialDistrict)?.region_id ?? coverage.find((item) => item.facility_count > 0)?.region_id ?? coverage[0]?.region_id ?? "";
  const [selectedRegion, setSelectedRegion] = useState(initial); const [sort, setSort] = useState<"high" | "low">("high"); const [statusFilter, setStatusFilter] = useState("all");
  const selected = coverage.find((item) => item.region_id === selectedRegion);
  const selectRegion = useCallback((regionId: string) => setSelectedRegion(regionId), []);
  const regionFacilities = useMemo(() => facilities.filter((facility) => facility.location.district === selected?.region_name).filter((facility) => statusFilter === "all" || facility.capabilities.find((claim) => claim.name === capability)?.status === statusFilter).sort((a, b) => { const aScore = a.capabilities.find((claim) => claim.name === capability)?.trust_score ?? 0; const bScore = b.capabilities.find((claim) => claim.name === capability)?.trust_score ?? 0; return sort === "high" ? bScore - aScore : aScore - bScore; }), [capability, facilities, selected?.region_name, sort, statusFilter]);
  const changeCapability = (next: string) => { const nextParams = new URLSearchParams(params.toString()); nextParams.set("capability", next); router.push(`/map?${nextParams}`); };

  return (
    <main className="map-page">
      <section className="map-toolbar"><div><p className="eyebrow">District coverage explorer</p><h1>Trust-weighted care coverage</h1></div><label>Capability<select value={capability} onChange={(event) => changeCapability(event.target.value)}>{["ICU", "Maternity", "Emergency", "Oncology", "Trauma", "NICU"].map((item) => <option key={item}>{item}</option>)}</select></label></section>
      <div className="map-layout">
        <section className="map-stage"><MapView geoJson={geoJson} coverage={coverage} facilities={facilities} selectedRegion={selectedRegion} onSelectRegion={selectRegion} /><div className="map-legend-panel"><p>Coverage signal</p><CoverageLegend compact /></div><p className="map-source">Demo district geometry · PIN used for facility filtering only</p></section>
        <aside className="facility-panel">
          {selected && <div className={`region-summary ${selected.coverage_status}`}><div><span>{selected.state}</span><h2>{selected.region_name}</h2></div><span className="coverage-status"><i className={`coverage-swatch ${selected.coverage_status}`} />{coverageLabels[selected.coverage_status].label}</span><p>{coverageLabels[selected.coverage_status].detail}. This is an evidence state, not a planning decision.</p><div className="region-metrics"><span><strong>{selected.facility_count}</strong> facilities</span><span><strong>{selected.avg_trust_score ? Math.round(selected.avg_trust_score * 100) : "—"}</strong> avg. trust</span></div></div>}
          <div className="list-controls"><span>{regionFacilities.length} matching facilities</span><div><select aria-label="Filter by claim status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All signals</option><option value="verified">Verified</option><option value="claimed-only">Claimed only</option><option value="no-signal">No signal</option></select><select aria-label="Sort facilities" value={sort} onChange={(event) => setSort(event.target.value as "high" | "low")}><option value="high">Trust: high first</option><option value="low">Trust: low first</option></select></div></div>
          <div className="facility-list">{regionFacilities.length ? regionFacilities.map((facility) => <FacilityCard key={facility.facility_id} facility={facility} queriedCapability={capability} />) : <div className={`empty-evidence ${selected?.coverage_status === "no_data" ? "no-data" : "confirmed-gap"}`}><span aria-hidden="true">{selected?.coverage_status === "no_data" ? "///" : "×"}</span><h3>{selected?.coverage_status === "no_data" ? "Evidence unavailable" : "No matching facility"}</h3><p>{selected?.coverage_status === "no_data" ? "We cannot infer a gap from the indexed material. Additional source collection is needed." : "The indexed sources confirm no matching facility for this capability in the district."}</p></div>}</div>
        </aside>
      </div>
    </main>
  );
}
