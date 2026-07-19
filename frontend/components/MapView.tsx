"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { ScatterplotLayer } from "@deck.gl/layers";
import maplibregl, { type GeoJSONSource, type MapLayerMouseEvent } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Facility, RegionCoverage, CoverageStatus } from "@/lib/types";
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
    avg_trust_score_pct?: number;
  };
  geometry: { type: "Polygon" | "MultiPolygon"; coordinates: number[][][] | number[][][][] };
};
type GeoCollection = { type: "FeatureCollection"; features: GeoFeature[] };
type PreviewPosition = { facility: Facility; x: number; y: number };
const EMPTY_MATCHED_FACILITY_IDS: string[] = [];
const MAX_PREVIEW_MARKERS = 72;

function previewPositionsEqual(
  current: PreviewPosition[],
  next: PreviewPosition[],
): boolean {
  return current.length === next.length && current.every((position, index) => {
    const candidate = next[index];
    return position.facility.facility_id === candidate.facility.facility_id
      && Math.abs(position.x - candidate.x) < 0.1
      && Math.abs(position.y - candidate.y) < 0.1;
  });
}

function claimFor(facility: Facility, capability: string) {
  return facility.capabilities.find((claim) => claim.name === capability) ?? facility.capabilities[0];
}

function scoreTone(score: number) {
  if (score >= 80) return "score-high";
  if (score >= 60) return "score-mid";
  return "score-low";
}

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";
const mapTiles = MAPBOX_TOKEN
  ? [`https://api.mapbox.com/styles/v1/mapbox/light-v11/tiles/512/{z}/{x}/{y}@2x?access_token=${MAPBOX_TOKEN}`]
  : [
      "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
      "https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
      "https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
    ];

const mapStyle: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    "mapbox-light": {
      type: "raster",
      tiles: mapTiles,
      tileSize: 512,
      attribution: "© <a href='https://www.mapbox.com/about/maps/'>Mapbox</a> © <a href='http://www.openstreetmap.org/copyright'>OpenStreetMap</a>",
    },
  },
  layers: [{ id: "mapbox-light", type: "raster", source: "mapbox-light", minzoom: 0, maxzoom: 22 }],
};

function createHatchPattern(): { width: number; height: number; data: Uint8Array } {
  const width = 8;
  const height = 8;
  const data = new Uint8Array(width * height * 4);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const index = (y * width + x) * 4;
      const stripe = (x + y) % 6 < 2;
      data[index] = stripe ? 148 : 209;
      data[index + 1] = stripe ? 163 : 213;
      data[index + 2] = stripe ? 175 : 219;
      data[index + 3] = stripe ? 200 : 140;
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

export function MapView({ geoJson, coverage, facilities, selectedRegion, focusedRegionIds = [], focusedFacilityId, matchedFacilityIds = EMPTY_MATCHED_FACILITY_IDS, queriedCapability = "ICU", onSelectRegion }: { geoJson: GeoCollection; coverage: RegionCoverage[]; facilities: Facility[]; selectedRegion: string; focusedRegionIds?: string[]; focusedFacilityId?: string; matchedFacilityIds?: string[]; queriedCapability?: string; onSelectRegion: (regionId: string) => void }) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const initialData = useRef({ geoJson, coverage });
  const selectRegionRef = useRef(onSelectRegion);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [globeReady, setGlobeReady] = useState(false);
  const [popupFacility, setPopupFacility] = useState<Facility | null>(null);
  const [popupPosition, setPopupPosition] = useState({ x: 0, y: 0 });
  const [previewPositions, setPreviewPositions] = useState<PreviewPosition[]>([]);
  const matchedFacilities = useMemo(() => facilities.filter((facility) => matchedFacilityIds.includes(facility.facility_id)), [facilities, matchedFacilityIds]);
  const previewFacilities = useMemo(
    () => {
      if (matchedFacilityIds.length) return matchedFacilities;
      return facilities
        .filter((facility) => Number.isFinite(facility.location.lat) && Number.isFinite(facility.location.lon))
        .sort((left, right) => (claimFor(right, queriedCapability)?.trust_score_pct ?? 0) - (claimFor(left, queriedCapability)?.trust_score_pct ?? 0))
        .slice(0, MAX_PREVIEW_MARKERS);
    },
    [facilities, matchedFacilities, matchedFacilityIds.length, queriedCapability],
  );
  const matchedFacilitiesKey = useMemo(
    () => previewFacilities.map((facility) => `${facility.facility_id}:${facility.location.lon}:${facility.location.lat}`).join("|"),
    [previewFacilities],
  );
  const matchedFacilitiesRef = useRef(previewFacilities);
  const activePopupFacility = popupFacility && (matchedFacilityIds.length === 0 || matchedFacilityIds.includes(popupFacility.facility_id)) ? popupFacility : null;

  useEffect(() => {
    matchedFacilitiesRef.current = previewFacilities;
  }, [previewFacilities]);

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
    let globeTimer: number | undefined;
    let spinFrame = 0;

    const handleDistrictClick = (event: MapLayerMouseEvent) => {
      const regionId = event.features?.[0]?.properties?.shapeName as string | undefined;
      if (regionId) selectRegionRef.current(regionId);
    };
    const handleMapBackgroundClick = (event: MapLayerMouseEvent) => {
      if (!event.defaultPrevented) setPopupFacility(null);
    };
    map.on("load", () => {
      map.setProjection({ type: "globe" });
      if (container.current) container.current.dataset.projection = "globe";
      map.setCenter([22, 22]);
      map.setZoom(1.45);
      let bearing = -14;
      const spin = () => {
        if (!map.isMoving()) {
          bearing -= 0.08;
          map.setBearing(bearing);
        }
        spinFrame = window.requestAnimationFrame(spin);
      };
      spinFrame = window.requestAnimationFrame(spin);
      globeTimer = window.setTimeout(() => {
        window.cancelAnimationFrame(spinFrame);
        map.easeTo({ center: [78.9, 22.5], zoom: 2.7, bearing: 0, duration: 1800, essential: true });
        map.once("moveend", () => setGlobeReady(true));
      }, 2000);
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
      map.addLayer({ id: "district-borders", type: "line", source: "district-coverage", paint: { "line-color": "#ffffff", "line-width": 1.5, "line-opacity": 0.95 } });
      map.on("click", "district-fill", handleDistrictClick);
      map.on("click", handleMapBackgroundClick);
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
      if (globeTimer) window.clearTimeout(globeTimer);
      window.cancelAnimationFrame(spinFrame);
      if (map.getLayer("district-fill")) map.off("click", "district-fill", handleDistrictClick);
      map.off("click", handleMapBackgroundClick);
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
    mapRef.current.setPaintProperty("district-borders", "line-color", ["case", ["==", ["get", "shapeName"], selectedRegion], "#16a34a", "#ffffff"]);
    mapRef.current.setPaintProperty("district-borders", "line-width", ["case", ["==", ["get", "shapeName"], selectedRegion], 4, 1.5]);
  }, [mapLoaded, selectedRegion]);

  useEffect(() => {
    const map = mapRef.current;
    if (!mapLoaded || !globeReady || !map || focusedRegionIds.length === 0) return;
    const features = geoJson.features.filter((feature) => focusedRegionIds.includes(feature.properties.shapeName));
    if (!features.length) return;
    const collectPoints = (coordinates: unknown): number[][] => Array.isArray(coordinates) && typeof coordinates[0] === "number" ? [coordinates as number[]] : Array.isArray(coordinates) ? coordinates.flatMap(collectPoints) : [];
    const points = features.flatMap((feature) => collectPoints(feature.geometry.coordinates));
    const minX = Math.min(...points.map((point) => point[0]));
    const maxX = Math.max(...points.map((point) => point[0]));
    const minY = Math.min(...points.map((point) => point[1]));
    const maxY = Math.max(...points.map((point) => point[1]));
    const camera = map.cameraForBounds([[minX, minY], [maxX, maxY]], { padding: 85, maxZoom: 7.5 });
    map.easeTo({ center: camera?.center ?? [(minX + maxX) / 2, (minY + maxY) / 2], zoom: camera?.zoom ?? 5.5, duration: 1350, essential: true });
    map.setPaintProperty("district-borders", "line-color", ["case", ["in", ["get", "shapeName"], ["literal", focusedRegionIds]], "#16a34a", "#ffffff"]);
    map.setPaintProperty("district-borders", "line-width", ["case", ["in", ["get", "shapeName"], ["literal", focusedRegionIds]], 4, 1.5]);
  }, [focusedRegionIds, geoJson, globeReady, mapLoaded]);

  useEffect(() => {
    if (!mapLoaded || !globeReady || !mapRef.current || !focusedFacilityId) return;
    const facility = facilities.find((item) => item.facility_id === focusedFacilityId);
    if (!facility || !Number.isFinite(facility.location.lat) || !Number.isFinite(facility.location.lon)) return;
    mapRef.current.easeTo({ center: [facility.location.lon, facility.location.lat], zoom: 12.5, duration: 1200, essential: true });
  }, [facilities, focusedFacilityId, globeReady, mapLoaded]);

  useEffect(() => {
    if (!mapLoaded || !overlayRef.current) return;
    overlayRef.current.setProps({ layers: [new ScatterplotLayer({ id: "facility-points", data: facilities, pickable: true, getPosition: (facility: Facility) => [facility.location.lon, facility.location.lat], getRadius: (facility: Facility) => matchedFacilityIds.includes(facility.facility_id) ? 11000 : 7000, radiusMinPixels: 4, radiusMaxPixels: 13, getFillColor: (facility: Facility) => matchedFacilityIds.length === 0 || matchedFacilityIds.includes(facility.facility_id) ? [255, 255, 255, 255] : [156, 163, 175, 130], getLineColor: (facility: Facility) => matchedFacilityIds.includes(facility.facility_id) ? [22, 163, 74, 255] : [22, 163, 74, 180], getLineWidth: (facility: Facility) => matchedFacilityIds.includes(facility.facility_id) ? 2 : 1, stroked: true, lineWidthMinPixels: 2, onClick: ({ object }, event) => { if (object && (matchedFacilityIds.length === 0 || matchedFacilityIds.includes((object as Facility).facility_id))) { event.srcEvent.preventDefault(); setPopupFacility(object as Facility); return true; } return false; }, updateTriggers: { getRadius: [matchedFacilityIds], getFillColor: [matchedFacilityIds], getLineColor: [matchedFacilityIds], getLineWidth: [matchedFacilityIds] } })] });
  }, [facilities, mapLoaded, matchedFacilityIds]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapLoaded) return;
    const update = () => {
      const occupied: Array<{ x: number; y: number }> = [];
      const candidates = [{ x: 0, y: 0 }, { x: 0, y: -34 }, { x: 34, y: 0 }, { x: -34, y: 0 }, { x: 0, y: 34 }];
      const nextPositions = matchedFacilitiesRef.current.map((facility) => {
        const point = map.project([facility.location.lon, facility.location.lat]);
        const offset = candidates.find((candidate) => occupied.every((placed) => Math.abs(point.x + candidate.x - placed.x) > 36 || Math.abs(point.y + candidate.y - placed.y) > 36)) ?? candidates[occupied.length % candidates.length];
        const position = { x: point.x + offset.x, y: point.y + offset.y };
        occupied.push(position);
        return { facility, ...position };
      });
      setPreviewPositions((current) => previewPositionsEqual(current, nextPositions) ? current : nextPositions);
    };
    update();
    map.on("move", update);
    return () => { map.off("move", update); };
  }, [mapLoaded, matchedFacilitiesKey]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !activePopupFacility) return;
    const update = () => { const point = map.project([activePopupFacility.location.lon, activePopupFacility.location.lat]); setPopupPosition({ x: point.x, y: point.y }); };
    update();
    map.on("move", update);
    return () => { map.off("move", update); };
  }, [activePopupFacility]);

  const popupClaim = activePopupFacility?.capabilities.find((c) => c.name === queriedCapability) ?? activePopupFacility?.capabilities[0];

  return (
    <>
      <div
        ref={container}
        className="map-canvas"
        aria-label="Interactive district coverage map"
        data-boundary-count={geoJson.features.length}
        data-coverage-status-count={new Set(coverage.map((r) => r.coverage_status)).size}
        data-coverage-colors={Object.values(COVERAGE_COLORS).join(",")}
      />

      {/* Location pin markers */}
      <AnimatePresence>
        {previewPositions
          .filter(({ facility }) => facility.facility_id !== activePopupFacility?.facility_id)
          .map(({ facility, x, y }) => {
            const claim = claimFor(facility, queriedCapability);
            const isHospital = /hospital|medical centre|medical center/i.test(facility.name);
            return (
            <motion.div
              key={facility.facility_id}
              className={`facility-pin-wrapper ${scoreTone(claim?.trust_score_pct ?? 0)}`}
              style={{ left: x, top: y }}
              initial={{ opacity: 0, scale: 0.4, y: 16 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.4, y: 16 }}
              transition={{ type: "spring", stiffness: 320, damping: 22, mass: 0.8 }}
            >
              <button
                type="button"
                className="facility-pin-head"
                onClick={(e) => { e.stopPropagation(); setPopupFacility(facility); }}
                aria-label={`Open ${facility.name} details`}
              >
                <div className="facility-pin-rings"><div className="facility-pin-ring" /><div className="facility-pin-ring" /><div className="facility-pin-ring" /></div>
                <svg className="facility-pin-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
                  {isHospital ? <><path d="M4 21V5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v16" /><path d="M2 21h20M8 7h2m4 0h2M8 11h2m4 0h2M10 21v-5h4v5" /></> : <><path d="M12 21a8 8 0 1 0 0-16 8 8 0 0 0 0 16Z" /><path d="M12 9v6m-3-3h6" /></>}
                </svg>
              </button>
              <div className="facility-pin-tail" />
            </motion.div>
            );
          })}
      </AnimatePresence>

      {/* Detail popup */}
      <AnimatePresence mode="wait">
        {activePopupFacility && popupClaim && (
          <motion.div
            key={activePopupFacility.facility_id}
            className="facility-map-popup"
            style={{ left: popupPosition.x, top: popupPosition.y }}
            role="dialog"
            aria-label={`${activePopupFacility.name} details`}
            initial={{ opacity: 0, scale: .92, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: .92, y: 10 }}
            transition={{ duration: .18 }}
          >
            <button
              className="popup-close"
              type="button"
              onClick={(e) => { e.stopPropagation(); setPopupFacility(null); }}
              aria-label="Close"
            >
              <X size={14} />
            </button>
            <div className="popup-topline"><span>Facility evidence</span><span className={`popup-signal ${popupClaim.status}`}>{popupClaim.status.replace("_", " ")}</span></div>
            <div className="popup-heading">
              <span className={`claim-badge ${popupClaim.status}`}>
                {popupClaim.status.replace("_", " ")}
              </span>
              <span className="trust-score">
                <strong>{popupClaim.trust_score_pct}</strong>/100
              </span>
            </div>
            <p style={{ margin: "12px 0 4px", color: "var(--muted)", fontSize: 8, letterSpacing: ".08em", textTransform: "uppercase" }}>
              {activePopupFacility.location.city} · {activePopupFacility.location.district}
            </p>
            <h2 style={{ margin: "0 0 10px", fontSize: 18, fontWeight: 700, lineHeight: 1.25 }}>
              {activePopupFacility.name}
            </h2>
            <p className="popup-location">{activePopupFacility.location.city || activePopupFacility.location.district} · {activePopupFacility.location.state}</p>
            <div className="popup-facts"><div><strong>{popupClaim.trust_score_pct}</strong><span>Trust score</span></div><div><strong>{activePopupFacility.raw_fields.capacity ?? "—"}</strong><span>Capacity reported</span></div><div><strong>{activePopupFacility.raw_fields.numberDoctors ?? "—"}</strong><span>Doctors reported</span></div></div>
            {popupClaim.evidence[0] && (
              <p style={{ margin: "0 0 12px", fontSize: 10, fontStyle: "italic", color: "var(--muted)", borderLeft: "2px solid var(--verdigris)", paddingLeft: 8, lineHeight: 1.55 }}>
                &ldquo;{popupClaim.evidence[0].text_span}&rdquo;
              </p>
            )}
            <p className="popup-confirm">{popupClaim.confirm_message}</p>
            <Link
              className="text-link"
              href={`/facility/${activePopupFacility.facility_id}?capability=${encodeURIComponent(queriedCapability)}`}
              style={{ fontSize: 11, fontWeight: 800, letterSpacing: ".03em", textTransform: "uppercase" }}
            >
              Review evidence →
            </Link>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
