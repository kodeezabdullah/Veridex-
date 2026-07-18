import { AppHeader } from "@/components/AppHeader";
import { MapExplorer } from "@/components/MapExplorer";
import { getCoverageGeoJson, getFacilities, getRegionCoverage } from "@/lib/api";

export default async function MapPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const query = await searchParams; const capability = typeof query.capability === "string" ? query.capability : "ICU"; const district = typeof query.district === "string" ? query.district : undefined;
  const [coverage, facilities, geoJson] = await Promise.all([getRegionCoverage(capability), getFacilities({ capability }), getCoverageGeoJson()]);
  return <><AppHeader section="Coverage" /><MapExplorer capability={capability} initialDistrict={district} coverage={coverage} facilities={facilities} geoJson={geoJson as Parameters<typeof MapExplorer>[0]["geoJson"]} /></>;
}
