"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { ScatterplotLayer } from "@deck.gl/layers";
import maplibregl, { type GeoJSONSource, type MapLayerMouseEvent } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Facility, RegionCoverage, CoverageStatus } from "@/lib/mockData";
import { COVERAGE_COLORS } from "@/lib/coverage";

type GeoFeature = {
  type: "Feature";
  properties: {
    shapeName: string;
    shapeISO: string;
    shapeGroup: string;
    shapeType: string;
    coverage_status?: CoverageStatus;
    facility_count?: number;
    avg_trust_score?: number;
  };
  geometry: { type: "Polygon" | "MultiPolygon"; coordinates: number[][][] | number[][][][] };
};
type GeoCollection = { type: "FeatureCollection"; features: GeoFeature[] };

const mapStyle: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    "carto-positron": {
      type: "raster",
      tiles: [
        "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
        "https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
        "https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
      ],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors © CARTO",
    },
  },
  layers: [{ id: "carto-positron", type: "raster", source: "carto-positron", minzoom: 0, maxzoom: 20 }],
};

function createHatchPattern(): { width: number; height: number; data: Uint8Array } {
  const width = 8;
  const height = 8;
  const data = new Uint8Array(width * height * 4);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const index = (y * width + x) * 4;
      const stripe = (x + y) % 6 < 2;
      data[index] = stripe ? 92 : 194;
      data[index + 1] = stripe ? 99 : 198;
      data[index + 2] = stripe ? 94 : 193;
      data[index + 3] = stripe ? 210 : 150;
    }
  }
  return { width, height, data };
}

function enrichGeoJson(geoJson: GeoCollection, coverage: RegionCoverage[]): GeoCollection {
  const lookup = new Map(coverage.map((region) => [region.region_name, region]));
  return {
    ...geoJson,
    features: geoJson.features.map((feature) => ({
      ...feature,
      properties: { ...feature.properties, ...lookup.get(feature.properties.shapeName) },
    })),
  };
}

export function MapView({ geoJson, coverage, facilities, selectedRegion, focusedRegionIds = [], matchedFacilityIds = [], queriedCapability = "ICU", onSelectRegion }: { geoJson: GeoCollection; coverage: RegionCoverage[]; facilities: Facility[]; selectedRegion: string; focusedRegionIds?: string[]; matchedFacilityIds?: string[]; queriedCapability?: string; onSelectRegion: (regionId: string) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const initialData = useRef({ geoJson, coverage });
  const selectRegionRef = useRef(onSelectRegion);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [popupFacility, setPopupFacility] = useState<Facility | null>(null);
  const [popupPosition, setPopupPosition] = useState({ x: 0, y: 0 });

  useEffect(() => {
    selectRegionRef.current = onSelectRegion;
  }, [onSelectRegion]);

  useEffect(() => {
    if (!container.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: container.current,
      style: mapStyle,
      center: [78.9, 22.5],
      zoom: 4,
      minZoom: 3,
      maxZoom: 11,
      attributionControl: {},
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    const overlay = new MapboxOverlay({ interleaved: false, layers: [] });
    map.addControl(overlay);
    mapRef.current = map;
    overlayRef.current = overlay;

    const handleDistrictClick = (event: MapLayerMouseEvent) => {
      const regionId = event.features?.[0]?.properties?.shapeName as string | undefined;
      if (regionId) selectRegionRef.current(regionId);
    };
    map.on("load", () => {
      map.fitBounds([[67.5, 6], [97.5, 36.5]], { padding: { top: 105, right: 55, bottom: 65, left: 55 }, maxZoom: 4, duration: 0 });
      map.addImage("no-data-hatch", createHatchPattern());
      map.addSource("district-coverage", { type: "geojson", data: enrichGeoJson(initialData.current.geoJson, initialData.current.coverage) as never });
      map.addLayer({
        id: "district-fill",
        type: "fill",
        source: "district-coverage",
        paint: {
          "fill-color": ["match", ["get", "coverage_status"], "verified_coverage", COVERAGE_COLORS.verified_coverage, "weak_coverage", COVERAGE_COLORS.weak_coverage, "no_facility", COVERAGE_COLORS.no_facility, COVERAGE_COLORS.no_data],
          "fill-opacity": ["case", ["==", ["get", "coverage_status"], "no_data"], 0.22, 0.7],
        },
      });
      map.addLayer({ id: "district-no-data-pattern", type: "fill", source: "district-coverage", filter: ["==", ["get", "coverage_status"], "no_data"], paint: { "fill-pattern": "no-data-hatch", "fill-opacity": 0.82 } });
      map.addLayer({ id: "district-borders", type: "line", source: "district-coverage", paint: { "line-color": "#f8f6ef", "line-width": 1.5, "line-opacity": 0.95 } });
      map.on("click", "district-fill", handleDistrictClick);
      map.on("mouseenter", "district-fill", () => { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", "district-fill", () => { map.getCanvas().style.cursor = ""; });
      requestAnimationFrame(() => {
        const canvases = container.current?.querySelectorAll("canvas");
        canvases?.forEach((canvas) => { if (!canvas.classList.contains("maplibregl-canvas")) canvas.classList.add("deck-canvas"); });
        map.resize();
      });
      setMapLoaded(true);
    });

    return () => {
      if (map.getLayer("district-fill")) map.off("click", "district-fill", handleDistrictClick);
      map.remove();
      mapRef.current = null;
      overlayRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!mapLoaded) return;
    const source = mapRef.current?.getSource("district-coverage") as GeoJSONSource | undefined;
    source?.setData(enrichGeoJson(geoJson, coverage) as never);
  }, [coverage, geoJson, mapLoaded]);

  useEffect(() => {
    if (!mapLoaded || !mapRef.current?.getLayer("district-borders")) return;
    mapRef.current.setPaintProperty("district-borders", "line-color", ["case", ["==", ["get", "shapeName"], selectedRegion], "#173f35", "#f8f6ef"]);
    mapRef.current.setPaintProperty("district-borders", "line-width", ["case", ["==", ["get", "shapeName"], selectedRegion], 4, 1.5]);
  }, [mapLoaded, selectedRegion]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapLoaded || !map || focusedRegionIds.length === 0) return;
    const features = geoJson.features.filter((feature) => focusedRegionIds.includes(feature.properties.shapeName));
    if (!features.length) return;
    const collectPoints = (coordinates: unknown): number[][] => Array.isArray(coordinates) && typeof coordinates[0] === "number" ? [coordinates as number[]] : Array.isArray(coordinates) ? coordinates.flatMap(collectPoints) : [];
    const points = features.flatMap((feature) => collectPoints(feature.geometry.coordinates));
    const minX = Math.min(...points.map((point) => point[0]));
    const maxX = Math.max(...points.map((point) => point[0]));
    const minY = Math.min(...points.map((point) => point[1]));
    const maxY = Math.max(...points.map((point) => point[1]));
    const camera = map.cameraForBounds([[minX, minY], [maxX, maxY]], { padding: 85, maxZoom: 7.5 });
    map.flyTo({ center: camera?.center ?? [(minX + maxX) / 2, (minY + maxY) / 2], zoom: camera?.zoom ?? 5.5, duration: 1350, essential: true, curve: 1.25 });
    map.setPaintProperty("district-borders", "line-color", ["case", ["in", ["get", "shapeName"], ["literal", focusedRegionIds]], "#173f35", "#f8f6ef"]);
    map.setPaintProperty("district-borders", "line-width", ["case", ["in", ["get", "shapeName"], ["literal", focusedRegionIds]], 4, 1.5]);
  }, [focusedRegionIds, geoJson, mapLoaded]);

  useEffect(() => {
    if (!mapLoaded || !overlayRef.current) return;
    overlayRef.current.setProps({ layers: [new ScatterplotLayer({ id: "facility-points", data: facilities, pickable: true, getPosition: (facility: Facility) => [facility.location.lon, facility.location.lat], getRadius: (facility: Facility) => matchedFacilityIds.includes(facility.facility_id) ? 11000 : 7000, radiusMinPixels: 4, radiusMaxPixels: 13, getFillColor: (facility: Facility) => matchedFacilityIds.length === 0 || matchedFacilityIds.includes(facility.facility_id) ? [251, 249, 242, 255] : [157, 163, 158, 130], getLineColor: (facility: Facility) => matchedFacilityIds.includes(facility.facility_id) ? [32, 126, 94, 255] : [23, 63, 53, 220], getLineWidth: (facility: Facility) => matchedFacilityIds.includes(facility.facility_id) ? 2 : 1, stroked: true, lineWidthMinPixels: 2, onClick: ({ object }) => { if (object) setPopupFacility(object as Facility); }, updateTriggers: { getRadius: [matchedFacilityIds], getFillColor: [matchedFacilityIds], getLineColor: [matchedFacilityIds], getLineWidth: [matchedFacilityIds] } })] });
  }, [facilities, mapLoaded, matchedFacilityIds]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !popupFacility) return;
    const update = () => { const point = map.project([popupFacility.location.lon, popupFacility.location.lat]); setPopupPosition({ x: point.x, y: point.y }); };
    update();
    map.on("move", update);
    return () => { map.off("move", update); };
  }, [popupFacility]);

  const popupClaim = popupFacility?.capabilities.find((claim) => claim.name === queriedCapability) ?? popupFacility?.capabilities[0];
  return <><div ref={container} className="map-canvas" aria-label="Interactive district coverage map" data-boundary-count={geoJson.features.length} data-coverage-status-count={new Set(coverage.map((region) => region.coverage_status)).size} data-coverage-colors={Object.values(COVERAGE_COLORS).join(",")} />{popupFacility && popupClaim && <article className="facility-map-popup" style={{ left: popupPosition.x, top: popupPosition.y }}><button className="popup-close" onClick={() => setPopupFacility(null)} aria-label="Close facility popup">×</button><div className="popup-heading"><span className={`claim-badge ${popupClaim.status}`}>{popupClaim.status.replace("-", " ")}</span><span className="trust-score"><strong>{Math.round(popupClaim.trust_score * 100)}</strong>/100 trust</span></div><p>{popupFacility.location.district} · {popupFacility.location.pin}</p><h2>{popupFacility.name}</h2><blockquote>“{popupClaim.evidence[0]?.text_span ?? "No supporting text signal indexed"}”</blockquote><Link href={`/facility/${popupFacility.facility_id}?capability=${encodeURIComponent(queriedCapability)}`}>View full evidence <span aria-hidden="true">→</span></Link></article>}</>;
}
