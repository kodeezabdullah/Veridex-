import type { CoverageStatus } from "./types";

export const COVERAGE_COLORS: Record<CoverageStatus, string> = {
  verified_coverage: "#4f8064",
  weak_coverage: "#d7a53f",
  no_facility: "#b4523e",
  no_data: "#9a9d97",
};
