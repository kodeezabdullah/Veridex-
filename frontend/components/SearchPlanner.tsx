"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import type { SelectorOptions } from "@/lib/api";
import { CapabilitySelector } from "./CapabilitySelector";
import { RegionSelector, type RegionSelection } from "./RegionSelector";

const emptyRegion: RegionSelection = {
  state: "",
  district: "",
  city: "",
  pin: "",
};

export function SearchPlanner({ capabilities, geographies }: SelectorOptions) {
  const router = useRouter();
  const [capability, setCapability] = useState("");
  const [region, setRegion] = useState(emptyRegion);

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const params = new URLSearchParams({ capability });

    Object.entries(region).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });

    router.push(`/map?${params.toString()}`);
  };

  return (
    <form className="search-panel" onSubmit={submit}>
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Begin an assessment</p>
          <h2>Define the care question</h2>
        </div>
        <p className="panel-note">Evidence, confidence, and uncertainty stay visible at every step.</p>
      </div>

      <CapabilitySelector capabilities={capabilities} value={capability} onChange={setCapability} />
      <div className="rule" />
      <RegionSelector geographies={geographies} value={region} onChange={setRegion} />

      <div className="form-footer">
        <p><span className="pulse-dot" aria-hidden="true" /> Mock evidence index ready</p>
        <button className="search-button" type="submit" disabled={!capability}>
          Explore coverage
          <span aria-hidden="true">↗</span>
        </button>
      </div>
    </form>
  );
}
