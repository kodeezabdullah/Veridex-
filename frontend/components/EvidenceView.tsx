"use client";

import { useEffect, useState } from "react";
import { addFacilityToScenario, addScenarioNote, addScenarioOverride, createScenario, getScenarios } from "@/lib/api";
import type { CapabilityClaim, Facility, Scenario } from "@/lib/mockData";

function HighlightedField({ text, spans }: { text: string; spans: string[] }) {
  const matches = spans.filter((span) => text.toLowerCase().includes(span.toLowerCase()));
  if (!matches.length) return <>{text}</>;
  const match = matches[0]; const start = text.toLowerCase().indexOf(match.toLowerCase());
  return <>{text.slice(0, start)}<mark>{text.slice(start, start + match.length)}</mark>{text.slice(start + match.length)}</>;
}

function ClaimEvidence({ claim, facility }: { claim: CapabilityClaim; facility: Facility }) {
  const fields = Array.from(new Set(claim.evidence.map((item) => item.field)));
  return (
    <article className="claim-evidence">
      <header><div><span className={`claim-badge ${claim.status}`}>{claim.status.replace("-", " ")}</span><h3>{claim.name}</h3></div><div className="confidence"><strong>{Math.round(claim.trust_score * 100)}</strong><span>trust score<br />{claim.confidence_level} confidence</span></div></header>
      <div className="evidence-fields">{fields.map((field) => { const raw = facility.raw_fields[field as keyof Facility["raw_fields"]]; const spans = claim.evidence.filter((item) => item.field === field).map((item) => item.text_span); return <div key={field}><span className="source-label">Source field · {field}</span><blockquote>{typeof raw === "string" ? <HighlightedField text={raw} spans={spans} /> : raw ?? "Not reported"}</blockquote></div>; })}</div>
      {claim.status !== "verified" && <p className="uncertainty-note"><span aria-hidden="true">!</span>{claim.status === "claimed-only" ? "This claim appears in source material but lacks independent corroboration." : "No supporting signal was found. This does not prove the capability is absent."}</p>}
    </article>
  );
}

export function EvidenceView({ facility, initialCapability }: { facility: Facility; initialCapability?: string }) {
  const [scenarios, setScenarios] = useState<Scenario[]>([]); const [scenarioId, setScenarioId] = useState(""); const [note, setNote] = useState(""); const [override, setOverride] = useState<"accept" | "needs-review" | "reject">("needs-review"); const [reason, setReason] = useState(""); const [message, setMessage] = useState("");
  const [activeClaim, setActiveClaim] = useState(initialCapability && facility.capabilities.some((claim) => claim.name === initialCapability) ? initialCapability : facility.capabilities[0].name);
  useEffect(() => { getScenarios().then((items) => { setScenarios(items); setScenarioId(items[0]?.scenario_id ?? ""); }); }, []);
  const selectedClaim = facility.capabilities.find((claim) => claim.name === activeClaim) ?? facility.capabilities[0];
  const ensureScenario = async () => { if (scenarioId) return scenarioId; const created = await createScenario(`${activeClaim} review — ${facility.location.state}`); setScenarios((current) => [created, ...current]); setScenarioId(created.scenario_id); return created.scenario_id; };
  const savePlannerInput = async () => { const id = await ensureScenario(); await addFacilityToScenario(id, facility.facility_id); if (note.trim()) await addScenarioNote(id, { facility_id: facility.facility_id, note: note.trim(), timestamp: new Date().toISOString() }); if (reason.trim()) await addScenarioOverride(id, { facility_id: facility.facility_id, capability: activeClaim, value: override, reason: reason.trim(), timestamp: new Date().toISOString() }); setMessage("Saved to scenario. Your note and override remain distinct from source evidence."); };

  return (
    <div className="evidence-layout">
      <section className="profile-main">
        <div className="claim-tabs" role="tablist" aria-label="Facility capabilities">{facility.capabilities.map((claim) => <button key={claim.name} role="tab" aria-selected={claim.name === activeClaim} onClick={() => setActiveClaim(claim.name)}>{claim.name}<i className={claim.status} /></button>)}</div>
        <ClaimEvidence claim={selectedClaim} facility={facility} />
        <section className="raw-profile"><div className="section-heading"><div><p className="eyebrow">Source completeness</p><h2>Raw facility profile</h2></div><p>Missing values stay visible; they are never interpreted as zero.</p></div><dl><div><dt>Established</dt><dd>{facility.raw_fields.yearEstablished ?? "Not reported"}</dd></div><div><dt>Capacity</dt><dd>{facility.raw_fields.capacity ?? "Not reported"}</dd></div><div><dt>Doctors</dt><dd>{facility.raw_fields.numberDoctors ?? "Not reported"}</dd></div><div><dt>Equipment</dt><dd>{facility.raw_fields.equipment}</dd></div></dl></section>
      </section>
      <aside className="planner-panel"><p className="eyebrow">Planner workspace</p><h2>Add context, not a verdict</h2><p className="planner-intro">Notes and overrides capture your judgment. They never alter the source evidence or trust score.</p><label>Scenario<select value={scenarioId} onChange={(event) => setScenarioId(event.target.value)}><option value="">Create a new scenario automatically</option>{scenarios.map((scenario) => <option key={scenario.scenario_id} value={scenario.scenario_id}>{scenario.name}</option>)}</select></label><label>Planner note<textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="e.g. Confirm ventilator count by phone" rows={4} /></label><fieldset><legend>Manual disposition</legend><div className="override-options">{(["accept", "needs-review", "reject"] as const).map((value) => <label key={value}><input type="radio" name="override" value={value} checked={override === value} onChange={() => setOverride(value)} /><span>{value.replace("-", " ")}</span></label>)}</div></fieldset><label>Reason for override<textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Explain the local context behind your disposition" rows={3} /></label><button className="primary-button" onClick={savePlannerInput}>Save to scenario <span aria-hidden="true">→</span></button>{message && <p className="save-message" role="status">{message}</p>}</aside>
    </div>
  );
}
