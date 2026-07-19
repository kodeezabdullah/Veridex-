import { AppHeader } from "@/components/AppHeader";
import { MapExplorer } from "@/components/MapExplorer";
import { getFacilities } from "@/lib/api";
import { getCoverageGeoJson, getDistrictCoverage } from "@/lib/api.server";

export default async function MapPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const query = await searchParams;
  const capability = typeof query.capability === "string" ? query.capability : "ICU";
  const district = typeof query.district === "string" ? query.district : undefined;
  const [coverage, facilities, geoJson] = await Promise.all([getDistrictCoverage(capability), getFacilities({ capability }), getCoverageGeoJson()]);
  return <><AppHeader section="Facility list" /><MapExplorer capability={capability} initialDistrict={district} coverage={coverage} facilities={facilities} geoJson={geoJson as Parameters<typeof MapExplorer>[0]["geoJson"]} /></>;
}
