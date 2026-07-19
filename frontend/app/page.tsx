import { ChatMapExperience } from "@/components/ChatMapExperience";
import { getFacilities } from "@/lib/api";
import { getCoverageGeoJson, getDistrictCoverage } from "@/lib/api.server";

export default async function Home({ searchParams }: { searchParams: Promise<{ capability?: string }> }) {
  const query = await searchParams;
  const capability = query.capability ?? "ICU";
  const [coverage, facilities, geoJson] = await Promise.all([getDistrictCoverage(capability), getFacilities({ capability }), getCoverageGeoJson()]);
  return <ChatMapExperience initialCapability={capability} initialCoverage={coverage} initialFacilities={facilities} geoJson={geoJson as Parameters<typeof ChatMapExperience>[0]["geoJson"]} />;
}
