import { CoverageSelector } from "@/components/CoverageSelector";
import { getRegionCoverage } from "@/lib/api";
import { capabilities, type CapabilityName } from "@/lib/types";

export default async function Home({ searchParams }: { searchParams: Promise<{ capability?: string }> }) {
  const query = await searchParams;
  const requestedCapability = query.capability;
  const capability: CapabilityName = capabilities.includes(
    requestedCapability as CapabilityName,
  )
    ? (requestedCapability as CapabilityName)
    : "ICU";
  const coverageResult = await getRegionCoverage(capability)
    .then((coverage) => ({ coverage, error: undefined }))
    .catch(() => ({
      coverage: [],
      error:
        "Real coverage data is unavailable. Configure VERIDEX_API_BASE_URL and verify the backend service.",
    }));
  return (
    <CoverageSelector
      initialCapability={capability}
      coverage={coverageResult.coverage}
      dataError={coverageResult.error}
    />
  );
}
