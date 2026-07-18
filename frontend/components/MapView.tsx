"use client";

import { useEffect, useRef } from "react";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { GeoJsonLayer, ScatterplotLayer } from "@deck.gl/layers";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Facility, RegionCoverage, CoverageStatus } from "@/lib/mockData";

type GeoFeature = { type: "Feature"; properties: { region_id: string; region_name: string; state: string; coverage_status?: CoverageStatus; facility_count?: number; avg_trust_score?: number }; geometry: { type: "Polygon"; coordinates: number[][][] } };
type GeoCollection = { type: "FeatureCollection"; features: GeoFeature[] };
const colors: Record<CoverageStatus, [number, number, number, number]> = { verified_coverage: [62, 122, 91, 215], weak_coverage: [215, 165, 63, 215], no_facility: [174, 69, 53, 215], no_data: [139, 145, 140, 150] };

export function MapView({ geoJson, coverage, facilities, selectedRegion, onSelectRegion }: { geoJson: GeoCollection; coverage: RegionCoverage[]; facilities: Facility[]; selectedRegion: string; onSelectRegion: (regionId: string) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);

  useEffect(() => {
    if (!container.current || mapRef.current) return;
    const map = new maplibregl.Map({ container: container.current, style: { version: 8, sources: {}, layers: [{ id: "background", type: "background", paint: { "background-color": "#e8e5db" } }] }, center: [79.2, 16.2], zoom: 4.2, minZoom: 3.5, maxZoom: 11, attributionControl: false });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    const overlay = new MapboxOverlay({ interleaved: false, layers: [] });
    map.addControl(overlay);
    mapRef.current = map;
    overlayRef.current = overlay;
    return () => { map.remove(); mapRef.current = null; overlayRef.current = null; };
  }, []);

  useEffect(() => {
    const overlay = overlayRef.current;
    if (!overlay) return;
    const lookup = new Map(coverage.map((region) => [region.region_id, region]));
    const enriched: GeoCollection = { ...geoJson, features: geoJson.features.map((feature) => ({ ...feature, properties: { ...feature.properties, ...lookup.get(feature.properties.region_id) } })) };
    const hatchLines = enriched.features.filter((feature) => feature.properties.coverage_status === "no_data").flatMap((feature) => {
      const ring = feature.geometry.coordinates[0]; const xs = ring.map((p) => p[0]); const ys = ring.map((p) => p[1]); const minX = Math.min(...xs); const maxX = Math.max(...xs); const minY = Math.min(...ys); const maxY = Math.max(...ys);
      return Array.from({ length: 9 }, (_, index) => { const offset = (index / 8) * ((maxX - minX) + (maxY - minY)); const x1 = Math.max(minX, minX + offset - (maxY - minY)); const y1 = minY + Math.max(0, offset - (maxX - minX)); const x2 = Math.min(maxX, minX + offset); const y2 = minY + Math.min(maxY - minY, offset); return { type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: [[x1, y1], [x2, y2]] } }; });
    });
    overlay.setProps({ layers: [
      new GeoJsonLayer({ id: "coverage-polygons", data: enriched as never, pickable: true, stroked: true, filled: true, lineWidthMinPixels: 1, getLineColor: (feature) => (feature as unknown as GeoFeature).properties.region_id === selectedRegion ? [247, 249, 242, 255] as [number, number, number, number] : [251, 249, 242, 190] as [number, number, number, number], getLineWidth: (feature) => (feature as unknown as GeoFeature).properties.region_id === selectedRegion ? 4 : 1, getFillColor: (feature) => colors[(feature as unknown as GeoFeature).properties.coverage_status ?? "no_data"], onClick: ({ object }) => object && onSelectRegion((object as unknown as GeoFeature).properties.region_id), updateTriggers: { getLineColor: [selectedRegion], getLineWidth: [selectedRegion] } }),
      new GeoJsonLayer({ id: "no-data-hatching", data: { type: "FeatureCollection", features: hatchLines } as never, pickable: false, stroked: true, filled: false, getLineColor: [82, 88, 84, 165], getLineWidth: 1.2, lineWidthMinPixels: 1 }),
      new ScatterplotLayer({ id: "facility-points", data: facilities, pickable: false, getPosition: (facility: Facility) => [facility.location.lon, facility.location.lat], getRadius: 7500, radiusMinPixels: 4, radiusMaxPixels: 8, getFillColor: [251, 249, 242, 255], getLineColor: [23, 63, 53, 255], stroked: true, lineWidthMinPixels: 2 }),
    ] });
  }, [coverage, facilities, geoJson, onSelectRegion, selectedRegion]);

  return <div ref={container} className="map-canvas" aria-label="Interactive district coverage map" />;
}
