"use client";

import { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Activity,
  BarChart3,
  Building2,
  ChevronDown,
  CircleAlert,
  Database,
  LayoutDashboard,
  Map as MapIcon,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  UsersRound,
} from "lucide-react";
import {
  capabilities,
  normalizeName,
  type CoverageStatus,
  type Facility,
  type RegionCoverage,
} from "@/lib/types";
import { COVERAGE_COLORS } from "@/lib/coverage";
import { coverageLabels } from "./CoverageLegend";
import { MapView } from "./MapView";
import { BrandMark } from "./BrandMark";

type GeoCollection = Parameters<typeof MapView>[0]["geoJson"];

const statusOrder: CoverageStatus[] = [
  "verified_coverage",
  "weak_coverage",
  "no_facility",
  "no_data",
];

const navItems = [
  { label: "Overview", href: "/", icon: LayoutDashboard },
  { label: "Map view", href: "#map", icon: MapIcon },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
  { label: "Scenarios", href: "/scenarios", icon: UsersRound },
];

function claimFor(facility: Facility, capability: string) {
  return facility.capabilities.find((claim) => claim.name === capability) ?? facility.capabilities[0];
}

function scoreTone(score: number) {
  if (score >= 80) return "score-high";
  if (score >= 60) return "score-mid";
  return "score-low";
}

export function MapExplorer({
  capability,
  initialDistrict,
  coverage,
  facilities,
  geoJson,
}: {
  capability: string;
  initialDistrict?: string;
  coverage: RegionCoverage[];
  facilities: Facility[];
  geoJson: GeoCollection;
}) {
  const router = useRouter();
  const params = useSearchParams();
  const hasRun = Boolean(params.get("state") && params.get("district"));
  const initial =
    coverage.find((item) => normalizeName(item.region_name) === normalizeName(initialDistrict ?? ""))?.region_id ??
    coverage.find((item) => item.facility_count > 0)?.region_id ??
    coverage[0]?.region_id ??
    "";
  const [selectedRegion, setSelectedRegion] = useState(hasRun ? initial : "");
  const [sort, setSort] = useState<"high" | "low">("high");
  const [statusFilter, setStatusFilter] = useState("all");
  const [focusedFacilityId] = useState<string | undefined>(params.get("facility") ?? undefined);

  const selected = coverage.find((item) => item.region_id === selectedRegion);
  const selectedState = params.get("state") ?? selected?.state ?? "";
  const [draftCapability, setDraftCapability] = useState(capability);
  const [draftState, setDraftState] = useState(selectedState);
  const [draftDistrict, setDraftDistrict] = useState(initialDistrict ?? selected?.region_name ?? "");

  const states = useMemo(
    () => Array.from(new Set(coverage.map((item) => item.state).filter(Boolean))).sort(),
    [coverage],
  );
  const districts = useMemo(
    () => Array.from(new Set(coverage
      .filter((item) => !draftState || normalizeName(item.state) === normalizeName(draftState))
      .map((item) => item.region_name.trim())
      .filter(Boolean)))
      .sort((left, right) => left.localeCompare(right, "en-IN", { sensitivity: "base" })),
    [coverage, draftState],
  );
  const selectRegion = useCallback((regionId: string) => setSelectedRegion(regionId), []);

  const regionFacilities = useMemo(
    () => (hasRun ? facilities : [])
      .filter((facility) => selected && normalizeName(facility.location.district) === normalizeName(selected.region_name))
      .filter((facility) => statusFilter === "all" || claimFor(facility, capability)?.status === statusFilter)
      .sort((left, right) => {
        const leftScore = claimFor(left, capability)?.trust_score_pct ?? 0;
        const rightScore = claimFor(right, capability)?.trust_score_pct ?? 0;
        return sort === "high" ? rightScore - leftScore : leftScore - rightScore;
      }),
    [capability, facilities, hasRun, selected, sort, statusFilter],
  );

  const stats = useMemo(() => {
    const claims = regionFacilities.map((facility) => claimFor(facility, capability)).filter(Boolean);
    const verified = claims.filter((claim) => claim.status === "verified").length;
    const avgTrust = claims.length
      ? Math.round(claims.reduce((total, claim) => total + claim.trust_score_pct, 0) / claims.length)
      : 0;
    const statusCounts = Object.fromEntries(
      statusOrder.map((status) => [status, coverage.filter((region) => region.coverage_status === status).length]),
    ) as Record<CoverageStatus, number>;
    return {
      facilities: regionFacilities.length,
      verified,
      avgTrust,
      coveredRegions: coverage.filter((region) => region.coverage_status === "verified_coverage").length,
      statusCounts,
      totalRegions: Math.max(coverage.length, 1),
    };
  }, [capability, coverage, regionFacilities]);

  const runCoverage = () => {
    const nextParams = new URLSearchParams(params.toString());
    nextParams.set("capability", draftCapability);
    if (draftState) nextParams.set("state", draftState);
    else nextParams.delete("state");
    if (draftDistrict) nextParams.set("district", draftDistrict);
    else nextParams.delete("district");
    router.push(`/map?${nextParams}`);
  };

  return (
    <div className="explorer-shell">
      <aside className="explorer-rail" aria-label="Primary navigation">
        <Link href="/" className="rail-brand" aria-label="Veridex overview">
          <BrandMark size={30} />
          <span className="rail-brand-copy"><strong>Veridex</strong><small>Care intelligence</small></span>
        </Link>
        <nav className="rail-nav">
          {navItems.map((item) => {
            const Icon = item.icon;
            return <Link key={item.label} href={item.href} className={`rail-nav-item ${item.label === "Map view" ? "active" : ""}`}><Icon size={17} strokeWidth={1.8} /><span>{item.label}</span></Link>;
          })}
        </nav>
        <div className="rail-bottom">
          <div className="rail-trust"><ShieldCheck size={16} /><span><strong>Evidence first</strong><small>Decision support, not endorsement</small></span></div>
          <Link href="/scenarios" className="rail-settings"><Settings size={16} /> Planning workspace</Link>
        </div>
      </aside>

      <main className="explorer-main">
        <header className="explorer-topbar">
          <div className="topbar-title"><p>Veridex / coverage intelligence</p><h1>Regional care coverage</h1></div>
          <div className="topbar-actions"><span className="data-status"><Activity size={14} /> Live indexed data</span><Link href="/scenarios">Saved scenarios <span>→</span></Link></div>
        </header>

        <div className="explorer-content">
          <section className="map-column" id="map">
            <div className="map-intro">
              <div><span className="section-kicker">Trust-weighted map</span><h2>{capability} availability across India</h2><p>Explore district signals, facility evidence, and confidence before planning outreach.</p></div>
              <div className="map-intro-badge"><Database size={15} /><span><strong>{stats.facilities.toLocaleString()}</strong> facilities indexed</span></div>
            </div>
            <div className="map-surface">
              <MapView geoJson={geoJson} coverage={coverage} facilities={hasRun ? facilities : []} selectedRegion={selectedRegion} focusedRegionIds={selected?.region_name ? [selected.region_name] : []} focusedFacilityId={focusedFacilityId} matchedFacilityIds={focusedFacilityId ? [focusedFacilityId] : []} queriedCapability={capability} onSelectRegion={selectRegion} />
              <div className="map-legend-panel"><p>Coverage signal</p>{statusOrder.map((status) => <div key={status} className="legend-item"><i className={`coverage-swatch ${status}`} /><span>{coverageLabels[status].label}</span></div>)}</div>
              <span className="map-attribution">Mapbox light · geoBoundaries ADM2</span>
            </div>
          </section>

          <aside className="inspector-panel" aria-label="Coverage controls and facility information">
            <div className="inspector-scroll">
              <div className="inspector-heading"><div><span className="section-kicker">Planner controls</span><h2>Build a coverage view</h2></div><SlidersHorizontal size={18} /></div>
              <div className="control-stack">
                <label>Capability<select value={draftCapability} onChange={(event) => setDraftCapability(event.target.value)}>{capabilities.map((item) => <option key={item}>{item}</option>)}</select><ChevronDown className="select-icon" size={15} /></label>
                <label>State<select value={draftState} onChange={(event) => { setDraftState(event.target.value); setDraftDistrict(""); }}><option value="">All states</option>{states.map((state) => <option key={state}>{state}</option>)}</select><ChevronDown className="select-icon" size={15} /></label>
                <label>District<select value={draftDistrict} onChange={(event) => setDraftDistrict(event.target.value)} disabled={!draftState}><option value="">Select district</option>{districts.map((district) => <option key={district}>{district}</option>)}</select><ChevronDown className="select-icon" size={15} /></label>
                <button type="button" className="run-coverage-button" onClick={runCoverage} disabled={!draftState || !draftDistrict}><Activity size={15} /> Run coverage <span>→</span></button>
              </div>

              <section className="analytics-section" id="analytics"><div className="section-heading-row"><span className="section-kicker">At a glance</span><BarChart3 size={15} /></div><div className="analytics-grid"><div><Building2 size={15} /><strong>{stats.facilities.toLocaleString()}</strong><span>Facilities</span></div><div><ShieldCheck size={15} /><strong>{stats.verified.toLocaleString()}</strong><span>Verified signals</span></div><div><Activity size={15} /><strong>{stats.avgTrust}<small>/100</small></strong><span>Mean trust</span></div><div><MapIcon size={15} /><strong>{stats.coveredRegions.toLocaleString()}</strong><span>Covered districts</span></div></div><div className="distribution"><div className="distribution-header"><span>District status mix</span><span>{coverage.length.toLocaleString()} regions</span></div><div className="distribution-bar">{statusOrder.map((status) => <span key={status} style={{ width: `${(stats.statusCounts[status] / stats.totalRegions) * 100}%`, background: COVERAGE_COLORS[status] }} />)}</div><div className="distribution-key">{statusOrder.map((status) => <span key={status}><i style={{ background: COVERAGE_COLORS[status] }} />{coverageLabels[status].label.replace(" coverage", "")}</span>)}</div></div></section>

              {selected && <section className="selected-region"><div className="region-overline"><span>Selected district</span><span className={`region-status ${selected.coverage_status}`}>{coverageLabels[selected.coverage_status].label}</span></div><h2>{selected.region_name}</h2><p>{selected.state} · {selected.facility_count.toLocaleString()} facilities in source data</p><div className="region-facts"><div><strong>{selected.avg_trust_score_pct || "—"}</strong><span>Avg trust</span></div><div><strong>{selected.facility_count}</strong><span>Facilities</span></div></div></section>}

              <section className="facility-inspector"><div className="section-heading-row"><div><span className="section-kicker">Facility evidence</span><h2>{regionFacilities.length} matching records</h2></div><CircleAlert size={15} /></div><div className="facility-filters"><select aria-label="Filter evidence status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All signals</option><option value="verified">Verified</option><option value="likely">Likely</option><option value="weak_signal">Weak signal</option><option value="no_signal">No signal</option></select><select aria-label="Sort trust score" value={sort} onChange={(event) => setSort(event.target.value as "high" | "low")}><option value="high">Trust high → low</option><option value="low">Trust low → high</option></select></div><div className="inspector-list">{regionFacilities.length ? regionFacilities.map((facility) => { const claim = claimFor(facility, capability); return <Link key={facility.facility_id} href={`/facility/${facility.facility_id}?capability=${encodeURIComponent(capability)}`} className="inspector-facility-card"><div className="facility-card-line"><span className={`signal-badge ${claim.status}`}>{claim.status.replace("_", " ")}</span><span className={`facility-score ${scoreTone(claim.trust_score_pct)}`}>{claim.trust_score_pct}<small>/100</small></span></div><h3>{facility.name}</h3><p>{facility.location.city || facility.location.district} · {facility.location.state}</p><blockquote>{claim.evidence[0]?.text_span ?? "No supporting text signal indexed"}</blockquote><span className="inspect-link">Review full evidence <span>→</span></span></Link>; }) : <div className="inspector-empty"><span>—</span><p>{selected?.coverage_status === "no_data" ? "Evidence is unavailable for this district." : "No matching facility evidence found."}</p></div>}</div></section>
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}
