import { AppHeader } from "@/components/AppHeader";
import { MapExplorer } from "@/components/MapExplorer";
import { getFacilities, getRegionCoverage } from "@/lib/api";
import { getCoverageGeoJson } from "@/lib/api.server";

export default async function MapPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const query = await searchParams;
  const capability = typeof query.capability === "string" ? query.capability : "ICU";
  const state = typeof query.state === "string" ? query.state : undefined;
  const district = typeof query.district === "string" ? query.district : undefined;
  const data = await Promise.all([
      getRegionCoverage(capability),
      getFacilities({ capability, state, district }),
      getCoverageGeoJson(),
    ]).catch(() => null);
  if (!data) {
    return <><AppHeader section="Facility list" /><main className="data-unavailable"><span aria-hidden="true">!</span><h1>Coverage data unavailable</h1><p>Configure the real backend API and verify its facilities and region coverage endpoints.</p></main></>;
  }
  const [coverage, facilities, geoJson] = data;
  return <><AppHeader section="Facility list" /><MapExplorer capability={capability} initialDistrict={district} coverage={coverage} facilities={facilities} geoJson={geoJson as Parameters<typeof MapExplorer>[0]["geoJson"]} /></>;
}
