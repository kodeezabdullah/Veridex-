import Link from "next/link";
import { notFound } from "next/navigation";
import { AppHeader } from "@/components/AppHeader";
import { EvidenceView } from "@/components/EvidenceView";
import { getFacility } from "@/lib/api";

export default async function FacilityPage({ params, searchParams }: { params: Promise<{ id: string }>; searchParams: Promise<{ capability?: string }> }) {
  const [{ id }, query] = await Promise.all([params, searchParams]); const facility = await getFacility(id); if (!facility) notFound();
  return <><AppHeader section="Evidence" /><main className="facility-detail"><Link className="back-link" href={`/?capability=${encodeURIComponent(query.capability ?? facility.capabilities[0].name)}`}>← Back to coverage</Link><header className="facility-hero"><div><p className="eyebrow">Facility evidence record · {facility.facility_id}</p><h1>{facility.name}</h1><p>{facility.location.city}, {facility.location.district}, {facility.location.state} · PIN {facility.location.pin}</p></div><div className="profile-caution"><span aria-hidden="true">◇</span><p><strong>Evidence, not endorsement</strong>This record presents indexed signals for planner review.</p></div></header><EvidenceView facility={facility} initialCapability={query.capability} /></main></>;
}
