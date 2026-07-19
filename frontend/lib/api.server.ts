import { readFile } from "node:fs/promises";
import path from "node:path";

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
