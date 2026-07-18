export const capabilities = [
  "ICU",
  "Maternity",
  "Emergency",
  "Oncology",
  "Trauma",
  "NICU",
] as const;

export type CapabilityName = (typeof capabilities)[number];

export type GeographyOption = {
  state: string;
  districts: Array<{
    name: string;
    cities: Array<{
      name: string;
      pins: string[];
    }>;
  }>;
};

export const geographies: GeographyOption[] = [
  {
    state: "Karnataka",
    districts: [
      {
        name: "Bengaluru Urban",
        cities: [
          { name: "Bengaluru", pins: ["560001", "560034", "560068"] },
        ],
      },
      {
        name: "Mysuru",
        cities: [{ name: "Mysuru", pins: ["570001", "570015"] }],
      },
    ],
  },
  {
    state: "Maharashtra",
    districts: [
      {
        name: "Mumbai City",
        cities: [{ name: "Mumbai", pins: ["400001", "400008"] }],
      },
      {
        name: "Pune",
        cities: [
          { name: "Pune", pins: ["411001", "411038"] },
          { name: "Pimpri-Chinchwad", pins: ["411018", "411044"] },
        ],
      },
    ],
  },
  {
    state: "Odisha",
    districts: [
      {
        name: "Khordha",
        cities: [{ name: "Bhubaneswar", pins: ["751001", "751024"] }],
      },
      {
        name: "Cuttack",
        cities: [{ name: "Cuttack", pins: ["753001", "753014"] }],
      },
    ],
  },
  {
    state: "Tamil Nadu",
    districts: [
      {
        name: "Chennai",
        cities: [{ name: "Chennai", pins: ["600001", "600020"] }],
      },
      {
        name: "Coimbatore",
        cities: [{ name: "Coimbatore", pins: ["641001", "641018"] }],
      },
    ],
  },
];

export type Evidence = {
  field: string;
  text_span: string;
  type: string;
};

export type Facility = {
  facility_id: string;
  name: string;
  location: {
    state: string;
    district: string;
    city: string;
    pin: string;
    lat: number;
    lon: number;
  };
  capabilities: Array<{
    name: string;
    status: "verified" | "claimed-only" | "no-signal";
    trust_score: number;
    confidence_level: "high" | "medium" | "low";
    evidence: Evidence[];
  }>;
  raw_fields: {
    description: string;
    procedure: string;
    equipment: string;
    numberDoctors: number | null;
    capacity: number | null;
    yearEstablished: string | null;
  };
  data_completeness: {
    capacity_reported: boolean;
    doctors_reported: boolean;
  };
};

export const facilities: Facility[] = [
  {
    facility_id: "f_00123",
    name: "Victoria District Hospital",
    location: {
      state: "Karnataka",
      district: "Bengaluru Urban",
      city: "Bengaluru",
      pin: "560001",
      lat: 12.9634,
      lon: 77.5738,
    },
    capabilities: [
      {
        name: "ICU",
        status: "verified",
        trust_score: 0.82,
        confidence_level: "high",
        evidence: [
          {
            field: "description",
            text_span: "10-bed ICU with ventilator support and 24/7 staffing",
            type: "corroborating",
          },
        ],
      },
    ],
    raw_fields: {
      description: "District referral centre with a 10-bed ICU with ventilator support and 24/7 staffing.",
      procedure: "Critical care and emergency stabilisation.",
      equipment: "Ventilators and multiparameter monitors.",
      numberDoctors: null,
      capacity: null,
      yearEstablished: "1900",
    },
    data_completeness: {
      capacity_reported: false,
      doctors_reported: false,
    },
  },
];

export const regionCoverage = [
  {
    region_id: "KA-BU",
    region_name: "Bengaluru Urban",
    level: "district" as const,
    capability_queried: "ICU",
    coverage_status: "verified_coverage" as const,
    facility_count: 14,
    avg_trust_score: 0.71,
  },
];
