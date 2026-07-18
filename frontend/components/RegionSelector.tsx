import type { GeographyOption } from "@/lib/mockData";

export type RegionSelection = {
  state: string;
  district: string;
  city: string;
  pin: string;
};

type RegionSelectorProps = {
  geographies: GeographyOption[];
  value: RegionSelection;
  onChange: (value: RegionSelection) => void;
};

function Field({
  label,
  name,
  value,
  disabled,
  placeholder,
  options,
  onChange,
}: {
  label: string;
  name: keyof RegionSelection;
  value: string;
  disabled?: boolean;
  placeholder: string;
  options: string[];
  onChange: (name: keyof RegionSelection, value: string) => void;
}) {
  return (
    <label className="region-field">
      <span>{label}</span>
      <span className="select-shell compact">
        <select
          name={name}
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(name, event.target.value)}
        >
          <option value="">{placeholder}</option>
          {options.map((option) => (
            <option key={option} value={option}>{option}</option>
          ))}
        </select>
        <span className="select-chevron" aria-hidden="true">⌄</span>
      </span>
    </label>
  );
}

export function RegionSelector({
  geographies,
  value,
  onChange,
}: RegionSelectorProps) {
  const selectedState = geographies.find((item) => item.state === value.state);
  const selectedDistrict = selectedState?.districts.find(
    (item) => item.name === value.district,
  );
  const selectedCity = selectedDistrict?.cities.find(
    (item) => item.name === value.city,
  );

  const update = (name: keyof RegionSelection, nextValue: string) => {
    if (name === "state") {
      onChange({ state: nextValue, district: "", city: "", pin: "" });
    } else if (name === "district") {
      onChange({ ...value, district: nextValue, city: "", pin: "" });
    } else if (name === "city") {
      onChange({ ...value, city: nextValue, pin: "" });
    } else {
      onChange({ ...value, pin: nextValue });
    }
  };

  return (
    <fieldset className="field-group">
      <legend className="field-label">
        Geography <span aria-hidden="true">02</span>
      </legend>
      <div className="region-grid">
        <Field label="State" name="state" value={value.state} placeholder="All states" options={geographies.map((item) => item.state)} onChange={update} />
        <Field label="District" name="district" value={value.district} disabled={!selectedState} placeholder="All districts" options={selectedState?.districts.map((item) => item.name) ?? []} onChange={update} />
        <Field label="City" name="city" value={value.city} disabled={!selectedDistrict} placeholder="All cities" options={selectedDistrict?.cities.map((item) => item.name) ?? []} onChange={update} />
        <Field label="PIN" name="pin" value={value.pin} disabled={!selectedCity} placeholder="All PINs" options={selectedCity?.pins ?? []} onChange={update} />
      </div>
      <p className="field-hint">
        Start broad or narrow the search. PINs filter facility markers; map coverage remains district-level.
      </p>
    </fieldset>
  );
}
