import { EnterpriseBed, BedCategory, BedOccupancyStatus } from "../core/context/HospitalConfigContext";

interface WardConfig {
  tower: string;
  floor: string;
  wardName: string;
  prefix: string;
  count: number;
  category: BedCategory;
  tariff: number;
  features: string[];
  occupiedRatio: number;
}

const WARD_BLUEPRINTS: WardConfig[] = [
  // 1. Main Inpatient Tower
  {
    tower: "Main Inpatient Tower",
    floor: "Floor 1",
    wardName: "Emergency Observation & Daycare",
    prefix: "ED",
    count: 24,
    category: "General",
    tariff: 3000,
    features: ["O2 Wall Outlet", "Vital Sign Monitor", "Call Bell"],
    occupiedRatio: 0.65,
  },
  {
    tower: "Main Inpatient Tower",
    floor: "Floor 2",
    wardName: "General Surgical Ward 2A & 2B",
    prefix: "GSW",
    count: 48,
    category: "General",
    tariff: 2500,
    features: ["O2 Wall Outlet", "IV Infusion Pole", "Call Bell"],
    occupiedRatio: 0.6,
  },
  {
    tower: "Main Inpatient Tower",
    floor: "Floor 3",
    wardName: "General Medical Ward 3A & 3B",
    prefix: "GMW",
    count: 48,
    category: "General",
    tariff: 2500,
    features: ["O2 Wall Outlet", "Nebulizer Port", "Call Bell"],
    occupiedRatio: 0.55,
  },
  {
    tower: "Main Inpatient Tower",
    floor: "Floor 4",
    wardName: "Intensive Care Complex (MICU / SICU)",
    prefix: "ICU",
    count: 36,
    category: "ICU",
    tariff: 14000,
    features: ["Ventilator Ready", "Invasive Arterial Line", "Cardiac Monitor", "Dialysis Port"],
    occupiedRatio: 0.75,
  },
  {
    tower: "Main Inpatient Tower",
    floor: "Floor 5",
    wardName: "Executive Deluxe Suites",
    prefix: "DLX",
    count: 24,
    category: "Private",
    tariff: 8500,
    features: ["Attendant Couch", "Smart TV", "Mini Fridge", "Attached Luxury Bath", "O2 Outlet"],
    occupiedRatio: 0.45,
  },

  // 2. Cardiac & Vascular Pavilion
  {
    tower: "Cardiac & Vascular Pavilion",
    floor: "Floor 1",
    wardName: "Cardiac Triage & Step-Down",
    prefix: "CAD",
    count: 20,
    category: "General",
    tariff: 4500,
    features: ["Cardiac Telemetry", "O2 High-Flow", "Defibrillator Stand"],
    occupiedRatio: 0.5,
  },
  {
    tower: "Cardiac & Vascular Pavilion",
    floor: "Floor 2",
    wardName: "Interventional Cardiology Post-Cath",
    prefix: "CATH",
    count: 30,
    category: "Semi-Private",
    tariff: 5500,
    features: ["Femoral Compression Stand", "Cardiac Telemetry", "O2 Wall Outlet"],
    occupiedRatio: 0.7,
  },
  {
    tower: "Cardiac & Vascular Pavilion",
    floor: "Floor 3",
    wardName: "Coronary Care Unit (CCU)",
    prefix: "CCU",
    count: 20,
    category: "ICU",
    tariff: 15000,
    features: ["Ventilator Ready", "IABP Support Port", "Cardiac Monitor", "O2 High-Flow"],
    occupiedRatio: 0.8,
  },
  {
    tower: "Cardiac & Vascular Pavilion",
    floor: "Floor 4",
    wardName: "Cardiothoracic Surgical ICU (CTVS)",
    prefix: "CTVS",
    count: 20,
    category: "ICU",
    tariff: 16500,
    features: ["Ventilator Ready", "Chest Tube Drainage Rig", "Cardiac Monitor", "Pacing Ports"],
    occupiedRatio: 0.65,
  },

  // 3. Trauma & Orthopedic Center
  {
    tower: "Trauma & Orthopedic Center",
    floor: "Ground Floor",
    wardName: "Trauma Resuscitation Bays",
    prefix: "TRM",
    count: 16,
    category: "ICU",
    tariff: 9000,
    features: ["Rapid Infuser", "Crash Cart", "Cardiac Monitor", "Ventilator Ready"],
    occupiedRatio: 0.6,
  },
  {
    tower: "Trauma & Orthopedic Center",
    floor: "Floor 1",
    wardName: "Orthopedic Joint Replacement Wards",
    prefix: "ORT",
    count: 36,
    category: "General",
    tariff: 3500,
    features: ["Trapeze Bar", "O2 Wall Outlet", "CPM Machine Port", "Call Bell"],
    occupiedRatio: 0.55,
  },
  {
    tower: "Trauma & Orthopedic Center",
    floor: "Floor 2",
    wardName: "Neuro-Spine Special Unit & HDU",
    prefix: "NEU",
    count: 28,
    category: "Semi-Private",
    tariff: 5000,
    features: ["Air Conditioned", "Specialized Spine Mattress", "ICP Monitor Port", "O2 Outlet"],
    occupiedRatio: 0.65,
  },

  // 4. Women & Child Health Block
  {
    tower: "Women & Child Health Block",
    floor: "Floor 1",
    wardName: "Antenatal & Postnatal Wards",
    prefix: "MAT",
    count: 32,
    category: "Semi-Private",
    tariff: 4500,
    features: ["Baby Bassinet", "Fetal Doppler Port", "Attached Bath", "O2 Outlet"],
    occupiedRatio: 0.5,
  },
  {
    tower: "Women & Child Health Block",
    floor: "Floor 2",
    wardName: "Labor & Delivery Suites (LDR)",
    prefix: "LDR",
    count: 16,
    category: "Private",
    tariff: 7500,
    features: ["Multipurpose Birthing Bed", "Infant Radiant Warmer", "Attached Luxury Bath"],
    occupiedRatio: 0.4,
  },
  {
    tower: "Women & Child Health Block",
    floor: "Floor 3",
    wardName: "Neonatal ICU (NICU) & Pediatric ICU",
    prefix: "NICU",
    count: 30,
    category: "ICU",
    tariff: 13000,
    features: ["Neonatal Incubator", "Phototherapy Unit", "Pediatric Ventilator", "Cardiac Monitor"],
    occupiedRatio: 0.7,
  },

  // 5. Oncology & Daycare Infusion Block
  {
    tower: "Oncology & Daycare Infusion Block",
    floor: "Floor 1",
    wardName: "Daycare Chemotherapy Infusion Bays",
    prefix: "ONC",
    count: 32,
    category: "General",
    tariff: 2800,
    features: ["Reclining Infusion Chair", "Laminar Flow Port", "O2 Outlet", "Smart TV"],
    occupiedRatio: 0.6,
  },
  {
    tower: "Oncology & Daycare Infusion Block",
    floor: "Floor 2",
    wardName: "Bone Marrow Transplant & Oncology Inpatient",
    prefix: "BMT",
    count: 24,
    category: "Private",
    tariff: 11000,
    features: ["HEPA Positive Pressure Filtration", "Isolation Airlock", "O2 Wall Outlet"],
    occupiedRatio: 0.5,
  },

  // 6. Nephrology & Renal Dialysis Wing
  {
    tower: "Nephrology & Renal Dialysis Wing",
    floor: "Floor 1",
    wardName: "Hemodialysis Stations",
    prefix: "DIA",
    count: 24,
    category: "General",
    tariff: 2500,
    features: ["Dialysis RO Water Port", "Heparin Pump Mount", "Vital Sign Monitor"],
    occupiedRatio: 0.65,
  },
  {
    tower: "Nephrology & Renal Dialysis Wing",
    floor: "Floor 2",
    wardName: "Renal Transplant Inpatient Unit",
    prefix: "REN",
    count: 18,
    category: "Semi-Private",
    tariff: 6000,
    features: ["Isolation Barrier", "Cardiac Monitor", "O2 Outlet", "Attached Bath"],
    occupiedRatio: 0.55,
  },

  // 7. Ambulatory Surgery & Short Stay
  {
    tower: "Ambulatory Surgery & Short Stay",
    floor: "Floor 1",
    wardName: "Pre-Op Holding & Post-Anesthesia Recovery (PACU)",
    prefix: "PACU",
    count: 30,
    category: "General",
    tariff: 3200,
    features: ["Warm Air Blanket Port", "Suction & High-Flow O2", "Vital Sign Monitor"],
    occupiedRatio: 0.45,
  },
];

const SAMPLE_PATIENT_NAMES = [
  "Ramesh Sharma",
  "Priya Deshmukh",
  "Ananya Roy",
  "Suresh Patel",
  "Meenakshi Sundaram",
  "Kavita Reddy",
  "Vikramaditya Singhania",
  "Sunil Mittal",
  "Aakash Banerjee",
  "Divya Krishnamurthy",
  "Mohammad Farooq",
  "Deepak Chawla",
  "Lakshmi Narayanan",
  "Arun Kumar",
  "Pooja Bhatia",
  "Girish Kulkarni",
];

const SAMPLE_DOCTORS = [
  "Dr. Vikram Seth (Cardiology)",
  "Dr. Sameer Joshi (Pulmonology / ICU)",
  "Dr. Radhika Sen (General Surgery)",
  "Dr. Harish Patel (Orthopedics)",
  "Dr. Sunita Rao (Pediatrics)",
  "Dr. Anjali Nair (OB/GYN)",
  "Dr. Rajesh Sharma (Internal Medicine)",
  "Dr. Arvind Swaminathan (Nephrology)",
  "Dr. Meera Nambiar (Oncology)",
];

export function generateEnterprise500Beds(): EnterpriseBed[] {
  const beds: EnterpriseBed[] = [];
  let bedIdCounter = 1001;

  for (const blueprint of WARD_BLUEPRINTS) {
    for (let i = 1; i <= blueprint.count; i++) {
      const roomNum = Math.ceil(i / 2);
      const bedSuffix = i % 2 === 1 ? "A" : "B";
      const bedNumber = `${blueprint.prefix}-${100 + roomNum}-${bedSuffix}`;
      const roomNumber = `R-${blueprint.prefix}-${100 + roomNum}`;

      // Status determination based on occupiedRatio
      let status: BedOccupancyStatus = "VACANT_CLEAN";
      let occupiedBy: EnterpriseBed["occupiedBy"] = undefined;

      const seed = (bedIdCounter * 37) % 100;
      if (seed < blueprint.occupiedRatio * 100) {
        status = "OCCUPIED";
        const patientName = SAMPLE_PATIENT_NAMES[(bedIdCounter + i) % SAMPLE_PATIENT_NAMES.length];
        const doctor = SAMPLE_DOCTORS[(bedIdCounter + i) % SAMPLE_DOCTORS.length];
        occupiedBy = {
          patientName,
          mrn: `MRN-2026-${(1000 + (bedIdCounter % 900)).toString().padStart(4, "0")}`,
          admittedDays: ((bedIdCounter % 7) + 1),
          doctor,
        };
      } else if (seed > 92) {
        status = "HOUSEKEEPING";
      } else if (seed > 85) {
        status = "RESERVED";
      }

      beds.push({
        bedId: bedIdCounter++,
        bedNumber,
        roomNumber,
        tower: blueprint.tower,
        floor: blueprint.floor,
        wardName: blueprint.wardName,
        category: blueprint.category,
        status,
        dailyTariffRupees: blueprint.tariff,
        features: [...blueprint.features],
        occupiedBy,
      });
    }
  }

  return beds;
}
