export interface MetricItem {
  id: string;
  name: string;
  domainId: number;
  domainName: string;
  category: "Clinical" | "Operational" | "Financial" | "Quality" | "Governance" | "Infrastructure";
  description: string;
  formula: string;
  unit: string;
  targetBenchmark?: string;
}

export const METRIC_DOMAINS = [
  { id: 1, name: "Executive / Hospital", count: 41, category: "Financial" },
  { id: 2, name: "Patient Access", count: 27, category: "Operational" },
  { id: 3, name: "Registration & MPI", count: 15, category: "Operational" },
  { id: 4, name: "Outpatient (OPD)", count: 27, category: "Clinical" },
  { id: 5, name: "Inpatient (IPD)", count: 24, category: "Clinical" },
  { id: 6, name: "Emergency Department", count: 26, category: "Clinical" },
  { id: 7, name: "Patient Flow & TAT", count: 20, category: "Operational" },
  { id: 8, name: "Bed & Capacity", count: 32, category: "Operational" },
  { id: 9, name: "Doctor & CPOE", count: 31, category: "Clinical" },
  { id: 10, name: "Nursing & Ward", count: 25, category: "Clinical" },
  { id: 11, name: "ICU & Critical Care", count: 26, category: "Clinical" },
  { id: 12, name: "Surgery / OT", count: 27, category: "Clinical" },
  { id: 13, name: "Laboratory (LIS)", count: 26, category: "Clinical" },
  { id: 14, name: "Radiology / PACS", count: 22, category: "Clinical" },
  { id: 15, name: "Pharmacy & NDPS", count: 28, category: "Operational" },
  { id: 16, name: "Blood Bank", count: 21, category: "Clinical" },
  { id: 17, name: "Inventory & Stores", count: 21, category: "Operational" },
  { id: 18, name: "Procurement & PO", count: 20, category: "Operational" },
  { id: 19, name: "Finance & Accounts", count: 31, category: "Financial" },
  { id: 20, name: "Revenue Cycle (RCM)", count: 31, category: "Financial" },
  { id: 21, name: "Insurance & TPA", count: 25, category: "Financial" },
  { id: 22, name: "Patient Safety", count: 18, category: "Quality" },
  { id: 23, name: "Infection Control", count: 19, category: "Quality" },
  { id: 24, name: "Clinical Quality (NABH)", count: 17, category: "Quality" },
  { id: 25, name: "Patient Experience", count: 18, category: "Quality" },
  { id: 26, name: "Workforce & HR", count: 26, category: "Governance" },
  { id: 27, name: "Compliance & Legal", count: 16, category: "Governance" },
  { id: 28, name: "Security & Audit", count: 19, category: "Governance" },
  { id: 29, name: "ABDM & FHIR", count: 20, category: "Infrastructure" },
  { id: 30, name: "SaaS Multi-tenant", count: 26, category: "Infrastructure" },
  { id: 31, name: "SaaS Reliability", count: 26, category: "Infrastructure" },
  { id: 32, name: "Predictive AI Forecasts", count: 22, category: "Clinical" },
];

export const SAMPLE_METRIC_CATALOG: MetricItem[] = [
  // 1. Executive
  {
    id: "MET-001",
    name: "Total Gross Revenue",
    domainId: 1,
    domainName: "Executive / Hospital",
    category: "Financial",
    description: "Sum of all unadjusted item charges across consultations, bed stay, lab, pharmacy, and procedures.",
    formula: "SUM(invoice_line_items.total_price_paise)",
    unit: "₹ INR",
    targetBenchmark: "Growth > 15% YoY",
  },
  {
    id: "MET-002",
    name: "AR Days (Accounts Receivable Days)",
    domainId: 1,
    domainName: "Executive / Hospital",
    category: "Financial",
    description: "Average days elapsed between invoice issuance and physical collection or insurer settlement.",
    formula: "(Total Accounts Receivable / Annual Net Revenue) × 365",
    unit: "Days",
    targetBenchmark: "< 45 Days",
  },
  {
    id: "MET-003",
    name: "ARPOB (Avg Revenue Per Occupied Bed)",
    domainId: 1,
    domainName: "Executive / Hospital",
    category: "Financial",
    description: "Operational inpatient revenue generated per occupied bed day.",
    formula: "Inpatient Revenue / Occupied Bed Days",
    unit: "₹ / Bed Day",
    targetBenchmark: "₹25,000 – ₹45,000",
  },
  {
    id: "MET-004",
    name: "Bed Occupancy Rate (BOR %)",
    domainId: 1,
    domainName: "Executive / Hospital",
    category: "Operational",
    description: "Percentage of operational licensed hospital beds occupied by active inpatients at census cut-off.",
    formula: "(Occupied Beds / Operational Licensed Beds) × 100",
    unit: "%",
    targetBenchmark: "82% – 88%",
  },

  // 2. Patient Access
  {
    id: "MET-005",
    name: "Appointment Conversion Rate",
    domainId: 2,
    domainName: "Patient Access",
    category: "Operational",
    description: "Percentage of requested slots successfully booked and attended.",
    formula: "(Completed Visits / Appointment Requests) × 100",
    unit: "%",
    targetBenchmark: "> 85%",
  },
  {
    id: "MET-006",
    name: "No-Show Rate",
    domainId: 2,
    domainName: "Patient Access",
    category: "Operational",
    description: "Percentage of booked appointment slots that patients neither attended nor cancelled.",
    formula: "(No-Show Appointments / Total Booked Slots) × 100",
    unit: "%",
    targetBenchmark: "< 8%",
  },

  // 3. Registration
  {
    id: "MET-007",
    name: "Registration TAT (Turnaround Time)",
    domainId: 3,
    domainName: "Registration & MPI",
    category: "Operational",
    description: "Duration from patient token generation to UHID creation and consent capture.",
    formula: "TIMESTAMP(UHID Issued) - TIMESTAMP(Token Issued)",
    unit: "Minutes",
    targetBenchmark: "< 3.5 Minutes",
  },
  {
    id: "MET-008",
    name: "ABHA Linkage Rate",
    domainId: 3,
    domainName: "Registration & MPI",
    category: "Operational",
    description: "Percentage of newly registered patients successfully bound to a 14-digit ABHA ID.",
    formula: "(ABHA Linked Registrations / Total Registrations) × 100",
    unit: "%",
    targetBenchmark: "> 80%",
  },

  // 4. OPD
  {
    id: "MET-009",
    name: "Average Consultation Duration",
    domainId: 4,
    domainName: "Outpatient (OPD)",
    category: "Clinical",
    description: "Mean time spent by consultant in active consultation with patient.",
    formula: "AVG(Consultation End Time - Consultation Start Time)",
    unit: "Minutes",
    targetBenchmark: "12 – 18 Minutes",
  },
  {
    id: "MET-010",
    name: "OPD Waiting Time (P90)",
    domainId: 4,
    domainName: "Outpatient (OPD)",
    category: "Operational",
    description: "90th percentile of duration patients wait in clinic lounge after arrival.",
    formula: "PERCENTILE_DISC(0.9) WITHIN GROUP (ORDER BY Consultation Start - Arrival Time)",
    unit: "Minutes",
    targetBenchmark: "< 25 Minutes",
  },

  // 5. IPD
  {
    id: "MET-011",
    name: "Average Length of Stay (ALOS)",
    domainId: 5,
    domainName: "Inpatient (IPD)",
    category: "Clinical",
    description: "Mean duration of inpatient hospitalization from admission to clinical discharge.",
    formula: "Total Inpatient Bed Days / Total Discharged Inpatients",
    unit: "Days",
    targetBenchmark: "3.2 – 4.5 Days",
  },
  {
    id: "MET-012",
    name: "Unplanned 30-Day Readmission Rate",
    domainId: 5,
    domainName: "Inpatient (IPD)",
    category: "Quality",
    description: "Inpatients readmitted unexpectedly for related diagnosis within 30 days of discharge.",
    formula: "(Readmitted Inpatients within 30d / Total Discharges) × 100",
    unit: "%",
    targetBenchmark: "< 4.5%",
  },

  // 6. Emergency Department
  {
    id: "MET-013",
    name: "Door-to-Doctor Time (ESI-1/2)",
    domainId: 6,
    domainName: "Emergency Department",
    category: "Clinical",
    description: "Elapsed time between patient arrival at emergency bay and first physician exam.",
    formula: "TIMESTAMP(Doctor First Touch) - TIMESTAMP(ED Bay Arrival)",
    unit: "Minutes",
    targetBenchmark: "< 5 Mins (ESI 1: Immediate)",
  },
  {
    id: "MET-014",
    name: "Left Without Being Seen (LWBS) Rate",
    domainId: 6,
    domainName: "Emergency Department",
    category: "Operational",
    description: "Percentage of emergency patients who left the facility before clinical evaluation.",
    formula: "(LWBS Patients / Total ED Arrivals) × 100",
    unit: "%",
    targetBenchmark: "< 1.5%",
  },

  // 11. ICU
  {
    id: "MET-015",
    name: "Ventilator Associated Pneumonia (VAP) Rate",
    domainId: 11,
    domainName: "ICU & Critical Care",
    category: "Quality",
    description: "Number of hospital-acquired pneumonia episodes per 1,000 mechanical ventilator days.",
    formula: "(Confirmed VAP Episodes / Total Ventilator Days) × 1,000",
    unit: "Per 1,000 Vent Days",
    targetBenchmark: "< 1.0",
  },

  // 13. Laboratory
  {
    id: "MET-016",
    name: "Critical Panic Delta Verbal Callout SLA",
    domainId: 13,
    domainName: "Laboratory (LIS)",
    category: "Quality",
    description: "Percentage of panic laboratory values verbally communicated to attending doctor within 15 mins.",
    formula: "(Verbal Callouts Completed < 15m / Total Panic Analyte Results) × 100",
    unit: "%",
    targetBenchmark: "100% NABH Mandate",
  },

  // 15. Pharmacy
  {
    id: "MET-017",
    name: "NDPS Perpetual Schedule H1 Variance",
    domainId: 15,
    domainName: "Pharmacy & NDPS",
    category: "Governance",
    description: "Discrepancy between physical narcotic ampoule count and electronic double-custody ledger.",
    formula: "Physical Ampoule Count - Digital Vault Balance",
    unit: "Units",
    targetBenchmark: "0.00 (Zero Tolerance)",
  },

  // 20. RCM & Finance
  {
    id: "MET-018",
    name: "First-Pass Claim Acceptance Rate",
    domainId: 20,
    domainName: "Revenue Cycle (RCM)",
    category: "Financial",
    description: "Percentage of electronic insurance pre-auths and claims accepted without initial query/rejection.",
    formula: "(Accepted First-Pass Claims / Total Submitted Claims) × 100",
    unit: "%",
    targetBenchmark: "> 92%",
  },

  // 27. Regulatory Compliance
  {
    id: "MET-019",
    name: "DPDP Act Statutory Consent Compliance",
    domainId: 27,
    domainName: "Compliance & Legal",
    category: "Governance",
    description: "Percentage of active health records with unexpired, cryptographically verifiable consent tokens.",
    formula: "(Active EMRs with Valid Consent / Total Active Patient EMRs) × 100",
    unit: "%",
    targetBenchmark: "100%",
  },

  // 31. SaaS Reliability
  {
    id: "MET-020",
    name: "API Availability & P99 Latency",
    domainId: 31,
    domainName: "SaaS Reliability",
    category: "Infrastructure",
    description: "Multi-tenant cloud API uptime percentage and 99th percentile response time.",
    formula: "Uptime % | P99 (Response Time ms)",
    unit: "% | ms",
    targetBenchmark: "99.99% | < 85ms",
  },
];

