"use client";

import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";
import { getFacilities, getRegionCoverage, queryAgent, type AgentQueryResponse } from "@/lib/api";
import { mockDistrictNameForBoundary, normalizeStateName, type Facility, type RegionCoverage } from "@/lib/mockData";
import { CoverageLegend } from "./CoverageLegend";
import { MapView } from "./MapView";

type GeoCollection = Parameters<typeof MapView>[0]["geoJson"];
type Message = { id: string; role: "user" | "agent"; content: string };

const suggestions = ["ICU coverage in Karnataka", "Maternity care near Bengaluru", "Oncology facilities in Chennai"];

export function ChatMapExperience({ initialCapability, initialCoverage, initialFacilities, geoJson }: { initialCapability: string; initialCoverage: RegionCoverage[]; initialFacilities: Facility[]; geoJson: GeoCollection }) {
  const [capability, setCapability] = useState(initialCapability);
  const [coverage, setCoverage] = useState(initialCoverage);
  const [facilities, setFacilities] = useState(initialFacilities);
  const [focusedRegions, setFocusedRegions] = useState<string[]>([]);
  const [matchedFacilityIds, setMatchedFacilityIds] = useState<string[]>([]);
  const [messages, setMessages] = useState<Message[]>([{ id: "welcome", role: "agent", content: "Ask about a care capability and place. I’ll focus the district-level evidence map without making the planning decision for you." }]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const conversationEnd = useRef<HTMLDivElement>(null);

  const applyResponse = async (response: AgentQueryResponse) => {
    const [nextCoverage, nextFacilities] = await Promise.all([getRegionCoverage(response.capability), getFacilities({ capability: response.capability, state: response.region.state ?? undefined, district: response.region.district ?? undefined })]);
    const regions = nextCoverage.filter((region) => (!response.region.state || normalizeStateName(region.state) === normalizeStateName(response.region.state)) && (!response.region.district || normalizeStateName(mockDistrictNameForBoundary(region.region_name)) === normalizeStateName(response.region.district))).map((region) => region.region_id);
    setCapability(response.capability);
    setCoverage(nextCoverage);
    setFacilities(nextFacilities);
    setFocusedRegions(regions);
    setMatchedFacilityIds(response.matched_facility_ids);
    setMessages((current) => [...current, { id: `agent-${Date.now()}`, role: "agent", content: response.reply }]);
    requestAnimationFrame(() => conversationEnd.current?.scrollIntoView({ behavior: "smooth" }));
  };

  const submitQuery = async (message: string) => {
    const clean = message.trim();
    if (!clean || thinking) return;
    setMessages((current) => [...current, { id: `user-${Date.now()}`, role: "user", content: clean }]);
    setInput("");
    setThinking(true);
    try { await applyResponse(await queryAgent(clean)); }
    finally { setThinking(false); }
  };
  const submit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); void submitQuery(input); };

  return (
    <main className="chat-map-shell">
      <section className="chat-map-stage">
        <MapView geoJson={geoJson} coverage={coverage} facilities={facilities} selectedRegion={focusedRegions[0] ?? ""} focusedRegionIds={focusedRegions} matchedFacilityIds={matchedFacilityIds} queriedCapability={capability} onSelectRegion={(regionId) => setFocusedRegions([regionId])} />
        <header className="map-brand-bar"><Link href="/" className="brand"><span className="brand-mark" aria-hidden="true">V</span><span>Veridex</span></Link><span className="live-context"><i /> Evidence map · {capability}</span><nav><Link href="/scenarios">Scenarios</Link></nav></header>
        <div className="hero-map-legend"><p>Coverage signal</p><CoverageLegend compact /></div>
        <div className="map-prompt"><span>Explore healthcare evidence across India’s districts</span><small>Ask the agent to focus the map</small></div>
      </section>
      <aside className="chat-panel">
        <header><div><span className="agent-orb" aria-hidden="true">✦</span><div><strong>Coverage agent</strong><small>Mock evidence assistant</small></div></div><span className="mock-badge">Mock</span></header>
        <div className="chat-history" aria-live="polite">
          {messages.map((message) => <div className={`chat-message ${message.role}`} key={message.id}><span>{message.role === "agent" ? "Veridex" : "You"}</span><p>{message.content}</p></div>)}
          {thinking && <div className="chat-message agent typing"><span>Veridex</span><p><i /><i /><i /></p></div>}
          <div ref={conversationEnd} />
        </div>
        {messages.length === 1 && <div className="query-suggestions"><span>Try asking</span>{suggestions.map((suggestion) => <button key={suggestion} onClick={() => void submitQuery(suggestion)}>{suggestion}<i aria-hidden="true">↗</i></button>)}</div>}
        <form className="chat-composer" onSubmit={submit}><label htmlFor="agent-query">Ask about coverage or facilities</label><div><textarea id="agent-query" value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void submitQuery(input); } }} placeholder="e.g. ICU coverage in Karnataka" rows={2} disabled={thinking} /><button type="submit" disabled={!input.trim() || thinking} aria-label="Send query">↑</button></div><p>Evidence assistant · Verify source details before deciding</p></form>
      </aside>
    </main>
  );
}
