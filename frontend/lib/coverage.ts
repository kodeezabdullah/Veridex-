import type { CoverageStatus } from "./types";

export const COVERAGE_COLORS: Record<CoverageStatus, string> = {
  verified_coverage: "#059669",
  weak_coverage: "#d97706",
  no_facility: "#dc2626",
  no_data: "#94a3b8",
};
