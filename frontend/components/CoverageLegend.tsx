import type { CoverageStatus } from "@/lib/types";

export const coverageLabels: Record<CoverageStatus, { label: string; detail: string }> = {
  verified_coverage: { label: "Verified coverage", detail: "Corroborated facility claims" },
  weak_coverage: { label: "Weak coverage", detail: "Claimed, not yet corroborated" },
  no_facility: { label: "Confirmed gap", detail: "No matching facility found" },
  no_data: { label: "No data", detail: "Evidence is insufficient" },
};

export function CoverageLegend({ compact = false }: { compact?: boolean }) {
  return (
    <div className={compact ? "coverage-legend compact" : "coverage-legend"} aria-label="Coverage status legend">
      {(Object.entries(coverageLabels) as Array<[CoverageStatus, { label: string; detail: string }]>).map(([status, copy]) => (
        <div className="legend-item" key={status}>
          <i className={`coverage-swatch ${status}`} aria-hidden="true" />
          <span><strong>{copy.label}</strong>{!compact && <small>{copy.detail}</small>}</span>
        </div>
      ))}
    </div>
  );
}
