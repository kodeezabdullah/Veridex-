import type { CapabilityName } from "@/lib/mockData";

type CapabilitySelectorProps = {
  capabilities: readonly CapabilityName[];
  value: string;
  onChange: (value: string) => void;
};

export function CapabilitySelector({
  capabilities,
  value,
  onChange,
}: CapabilitySelectorProps) {
  return (
    <label className="field-group">
      <span className="field-label">
        Care capability <span aria-hidden="true">01</span>
      </span>
      <span className="select-shell">
        <select
          name="capability"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          required
        >
          <option value="">Choose a capability</option>
          {capabilities.map((capability) => (
            <option key={capability} value={capability}>
              {capability}
            </option>
          ))}
        </select>
        <span className="select-chevron" aria-hidden="true">⌄</span>
      </span>
      <span className="field-hint">
        Select the service whose evidence and coverage you want to inspect.
      </span>
    </label>
  );
}
