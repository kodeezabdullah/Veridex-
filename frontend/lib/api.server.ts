import { readFile } from "node:fs/promises";
import path from "node:path";
import { deriveDistrictCoverage, type CapabilityName } from "./mockData";

type BoundaryCollection = { type: "FeatureCollection"; features: Array<{ properties: { shapeName: string } }> };

let boundaryCache: BoundaryCollection | null = null;

async function readBoundaryData(): Promise<BoundaryCollection> {
  if (boundaryCache) return boundaryCache;
  const filePath = path.join(process.cwd(), "public", "geojson", "geoBoundaries-IND-ADM2_simplified.geojson");
  boundaryCache = JSON.parse(await readFile(filePath, "utf8")) as BoundaryCollection;
  return boundaryCache;
}

export async function getCoverageGeoJson() {
  return readBoundaryData();
}

export async function getDistrictCoverage(capability: string) {
  const boundaries = await readBoundaryData();
  const validCapability = (["ICU", "Maternity", "Emergency", "Oncology", "Trauma", "NICU"] as const).includes(capability as CapabilityName) ? capability as CapabilityName : "ICU";
  return deriveDistrictCoverage(boundaries.features.map((feature) => feature.properties.shapeName), validCapability);
}
