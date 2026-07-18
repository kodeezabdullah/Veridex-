import Link from "next/link";
import type { Facility } from "@/lib/mockData";

export function FacilityCard({ facility, queriedCapability }: { facility: Facility; queriedCapability: string }) {
  const claim = facility.capabilities.find((item) => item.name === queriedCapability) ?? facility.capabilities[0];
  return (
    <article className="facility-card">
      <div className="facility-card-top"><span className={`claim-badge ${claim.status}`}>{claim.status.replace("-", " ")}</span><span className="trust-score"><strong>{Math.round(claim.trust_score * 100)}</strong>/100 trust</span></div>
      <div><p className="facility-location">{facility.location.city} · {facility.location.pin}</p><h3>{facility.name}</h3></div>
      <div className="capability-chips">{facility.capabilities.map((item) => <span key={item.name}>{item.name}</span>)}</div>
      <p className="evidence-preview">“{claim.evidence[0]?.text_span ?? "No supporting text signal indexed"}”</p>
      <Link className="text-link" href={`/facility/${facility.facility_id}?capability=${encodeURIComponent(queriedCapability)}`}>Review evidence <span aria-hidden="true">→</span></Link>
    </article>
  );
}
