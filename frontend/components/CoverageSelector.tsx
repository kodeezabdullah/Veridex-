"use client";

import Link from "next/link";
import { useMemo, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  capabilities,
  normalizeName,
  type CapabilityName,
  type RegionCoverage,
} from "@/lib/types";

function compareNames(left: string, right: string) {
  return left.localeCompare(right, "en-IN", { sensitivity: "base" });
}

export function CoverageSelector({
  initialCapability,
  coverage,
  dataError,
}: {
  initialCapability: CapabilityName;
  coverage: RegionCoverage[];
  dataError?: string;
}) {
  const router = useRouter();
  const [capability, setCapability] = useState<CapabilityName>(initialCapability);
  const [state, setState] = useState("");
  const [district, setDistrict] = useState("");

  const states = useMemo(
    () =>
      Array.from(
        new Set(coverage.map((region) => region.state.trim()).filter(Boolean)),
      ).sort(compareNames),
    [coverage],
  );

  const districts = useMemo(
    () =>
      Array.from(
        new Set(
          coverage
            .filter(
              (region) =>
                state &&
                normalizeName(region.state) === normalizeName(state),
            )
            .map((region) => region.region_name.trim())
            .filter(Boolean),
        ),
      ).sort(compareNames),
    [coverage, state],
  );

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!state || !district) return;
    const params = new URLSearchParams({ capability, state, district });
    router.push(`/map?${params.toString()}`);
  };

  return (
    <main className="landing-shell">
      <header className="site-header">
        <Link href="/" className="brand">
          <span className="brand-mark" aria-hidden="true">V</span>
          <span>Veridex</span>
        </Link>
        <span className="header-context">
          <i className="header-rule" /> Medical desert planner
        </span>
        <Link href="/scenarios" className="saved-link">
          Planning scenarios <span aria-hidden="true">→</span>
        </Link>
      </header>

      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Evidence-led regional planning</p>
          <h1>
            Find care gaps.<br />
            <em>Know the evidence.</em>
          </h1>
          <p className="hero-intro">
            Select a healthcare capability and district to inspect trust-weighted
            coverage and the facility evidence behind it.
          </p>
          <div className="status-key" aria-label="Coverage status key">
            <span><i className="verified" /> Verified coverage</span>
            <span><i className="claimed" /> Weak coverage</span>
            <span><i className="gap" /> No facility found</span>
            <span><i className="unknown" /> No data</span>
          </div>
        </div>

        <form className="search-panel" onSubmit={submit}>
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Coverage selector</p>
              <h2>Choose an area to review</h2>
            </div>
            <p className="panel-note">
              Results describe indexed evidence, not a recommendation or final
              planning decision.
            </p>
          </div>

          <fieldset className="field-group">
            <label className="field-label" htmlFor="capability">
              Capability <span>Required</span>
            </label>
            <span className="select-shell">
              <select
                id="capability"
                value={capability}
                onChange={(event) =>
                  setCapability(event.target.value as CapabilityName)
                }
              >
                {capabilities.map((option) => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
              <span className="select-chevron" aria-hidden="true">⌄</span>
            </span>
            <p className="field-hint">
              Coverage is calculated independently for each clinical capability.
            </p>
          </fieldset>

          <div className="rule" />

          <div className="region-grid">
            <label className="region-field" htmlFor="state">
              <span>State</span>
              <span className="select-shell compact">
                <select
                  id="state"
                  value={state}
                  onChange={(event) => {
                    setState(event.target.value);
                    setDistrict("");
                  }}
                >
                  <option value="">Select a state</option>
                  {states.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
                <span className="select-chevron" aria-hidden="true">⌄</span>
              </span>
            </label>

            <label className="region-field" htmlFor="district">
              <span>District</span>
              <span className="select-shell compact">
                <select
                  id="district"
                  value={district}
                  onChange={(event) => setDistrict(event.target.value)}
                  disabled={!state}
                >
                  <option value="">
                    {state ? "Select a district" : "Choose a state first"}
                  </option>
                  {districts.map((option) => (
                    <option key={option} value={option}>{option}</option>
                  ))}
                </select>
                <span className="select-chevron" aria-hidden="true">⌄</span>
              </span>
            </label>
          </div>

          <div className="form-footer">
            <p><i className="pulse-dot" /> {states.length} states indexed</p>
            <button
              className="search-button"
              type="submit"
              disabled={!state || !district || Boolean(dataError)}
            >
              View Coverage <span aria-hidden="true">→</span>
            </button>
          </div>
          {dataError && <p className="api-error" role="alert">{dataError}</p>}
        </form>
      </section>

      <footer className="landing-footer">
        <p>Decision support only · Confirm facility services directly</p>
        <span>District-level coverage</span>
      </footer>
    </main>
  );
}
