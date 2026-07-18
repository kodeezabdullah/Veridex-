import {
  capabilities,
  facilities,
  geographies,
  regionCoverage,
  type CapabilityName,
  type Facility,
  type GeographyOption,
} from "./mockData";

export type SelectorOptions = {
  capabilities: readonly CapabilityName[];
  geographies: GeographyOption[];
};

export async function getSelectorOptions(): Promise<SelectorOptions> {
  return Promise.resolve({ capabilities, geographies });
}

export async function getFacilities(filters: {
  capability?: string;
  state?: string;
  district?: string;
  city?: string;
  pin?: string;
} = {}): Promise<Facility[]> {
  return Promise.resolve(
    facilities.filter((facility) => {
      const capabilityMatches =
        !filters.capability ||
        facility.capabilities.some(
          (capability) => capability.name === filters.capability,
        );

      return (
        capabilityMatches &&
        (!filters.state || facility.location.state === filters.state) &&
        (!filters.district || facility.location.district === filters.district) &&
        (!filters.city || facility.location.city === filters.city) &&
        (!filters.pin || facility.location.pin === filters.pin)
      );
    }),
  );
}

export async function getRegionCoverage(capability: string) {
  return Promise.resolve(
    regionCoverage.filter(
      (region) => region.capability_queried === capability,
    ),
  );
}
