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
import { WorkspaceRail } from "@/components/WorkspaceRail";

function compareNames(a: string, b: string) {
  return a.localeCompare(b, "en-IN", { sensitivity: "base" });
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
      Array.from(new Set(coverage.map((r) => r.state.trim()).filter(Boolean))).sort(compareNames),
    [coverage],
  );

  const districts = useMemo(
    () =>
      Array.from(
        new Set(
          coverage
            .filter((r) => state && normalizeName(r.state) === normalizeName(state))
            .map((r) => r.region_name.trim())
            .filter(Boolean),
        ),
      ).sort(compareNames),
    [coverage, state],
  );

  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!state || !district) return;
    const params = new URLSearchParams({ capability, state, district });
    router.push(`/map?${params.toString()}`);
  };

  return (
    <div className="page-shell-with-rail"><WorkspaceRail /><main className="landing-dark">
      <header className="landing-dark-header">
        <Link href="/" className="brand">
          <span className="brand-mark">V</span>
          <span>Veridex</span>
        </Link>
        <nav className="landing-dark-nav">
          <Link href="/scenarios">Planning scenarios →</Link>
        </nav>
      </header>

      <div className="landing-dark-body">
        <div className="landing-dark-copy">
          <p className="eyebrow">Evidence-led regional planning</p>
          <h1>
            Find care gaps.<br />
            <em>Know the evidence.</em>
          </h1>
          <p>
            Select a healthcare capability and district to inspect trust-weighted
            coverage and the facility evidence behind every signal.
          </p>
          <div className="landing-dark-badges">
            <span className="landing-dark-badge"><i style={{ background: "#059669" }} /> Verified coverage</span>
            <span className="landing-dark-badge"><i style={{ background: "#f59e0b" }} /> Weak coverage</span>
            <span className="landing-dark-badge"><i style={{ background: "#ef4444" }} /> No facility found</span>
            <span className="landing-dark-badge"><i style={{ background: "#94a3b8" }} /> No data</span>
          </div>
        </div>

        <form className="landing-dark-panel" onSubmit={submit}>
          <h2>Choose an area</h2>
          <p className="landing-dark-panel-sub">
            Results describe indexed evidence — not a recommendation or final planning decision.
          </p>

          <label className="dark-field-label" htmlFor="capability">Capability</label>
          <div className="dark-select-wrap">
            <select
              id="capability"
              value={capability}
              onChange={(e) => setCapability(e.target.value as CapabilityName)}
            >
              {capabilities.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <span className="dark-select-chevron">▾</span>
          </div>

          <div className="dark-divider" />

          <div className="dark-region-grid">
            <div>
              <span className="dark-region-label">State</span>
              <div className="dark-select-wrap" style={{ marginBottom: 0 }}>
                <select
                  value={state}
                  onChange={(e) => { setState(e.target.value); setDistrict(""); }}
                >
                  <option value="">Select state</option>
                  {states.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <span className="dark-select-chevron">▾</span>
              </div>
            </div>
            <div>
              <span className="dark-region-label">District</span>
              <div className="dark-select-wrap" style={{ marginBottom: 0 }}>
                <select
                  value={district}
                  onChange={(e) => setDistrict(e.target.value)}
                  disabled={!state}
                >
                  <option value="">{state ? "Select district" : "Choose state first"}</option>
                  {districts.map((d) => <option key={d} value={d}>{d}</option>)}
                </select>
                <span className="dark-select-chevron">▾</span>
              </div>
            </div>
          </div>

          <div className="dark-submit-row">
            <span className="dark-submit-hint">
              <span className="dark-pulse" />
              {states.length} states indexed
            </span>
            <button
              className="dark-submit-btn"
              type="submit"
              disabled={!state || !district || Boolean(dataError)}
            >
              View Coverage →
            </button>
          </div>
          {dataError && <p className="dark-api-error" role="alert">{dataError}</p>}
        </form>
      </div>

      <footer className="landing-dark-footer">
        <p>Decision support only · Confirm facility services directly</p>
        <p>District-level coverage · India ADM2</p>
      </footer>
    </main></div>
  );
}
