import React, { createContext, useContext, useState, useEffect, useRef } from "react";
import { generateEnterprise500Beds } from "../../data/enterpriseBeds";
import { uiApi } from "../../api/uiApi";
import { HardwarePrinterBackendConfig } from "../../types";

export type BedCategory = "General" | "Semi-Private" | "Private" | "ICU";
export type BedOccupancyStatus = "VACANT_CLEAN" | "OCCUPIED" | "HOUSEKEEPING" | "RESERVED";

export interface EnterpriseBed {
  bedId: number;
  bedNumber: string;
  roomNumber: string;
  tower: string;
  floor: string;
  wardName: string;
  category: BedCategory;
  status: BedOccupancyStatus;
  dailyTariffRupees: number;
  features: string[];
  occupiedBy?: {
    patientName: string;
    mrn: string;
    admittedDays: number;
    doctor: string;
  };
}

export interface OpdDoctor {
  id: string;
  name: string;
  specialty: string;
  department: string;
  roomNumber: string;
  consultationFee: number;
  currentWaitMins: number;
  patientsWaiting: number;
  isActive: boolean;
  revisitFreeWindowDays: number;
  revisitMaxFreeVisits: number;
  revisitDiscountPercent: number;
}

export interface HospitalProfile {
  name: string;
  subdomain: string;
  address: string;
  phone: string;
  emergencyPhone: string;
  accreditation: string;
  taxGstin: string;
}

export interface HospitalPolicies {
  requireUpfrontPaymentForToken: boolean;
  enforceDpdpConsent: boolean;
  autoAlertMlcToPolice: boolean;
  allowTariffOverride: boolean;
  defaultBedView: "GRID" | "TABLE";
  defaultRevisitFreeDays: number;
  allowDoctorSpecificRevisitRules: boolean;
  enforceRevisitWindowExpiry: boolean;
}

export type WristbandPreset =
  | "ADULT_STANDARD_280x25"
  | "ADULT_WIDE_280x28"
  | "ADULT_SLIM_250x19"
  | "PEDIATRIC_180x19"
  | "INFANT_NICU_150x15"
  | "NEONATE_MICRO_100x12"
  | "CUSTOM";

export type ThermalRollWidth = "58mm" | "80mm" | "112mm" | "CUSTOM";

export type PrinterConnectionType = "NETWORK_IP" | "USB" | "WIFI" | "SYSTEM_DRIVER";
export type PrinterTargetCategory = "WRISTBAND" | "THERMAL_TOKEN" | "CLINICAL_A4" | "LAB_LABEL";
export type PrinterProtocol = "HTML_DRIVER" | "RAW_ZPL" | "RAW_ESCPOS";

export interface HospitalPrinterDevice {
  id: string;
  name: string;
  location: string;
  connectionType: PrinterConnectionType;
  targetCategory: PrinterTargetCategory;
  protocol: PrinterProtocol;
  ipAddress?: string;
  port?: number;
  usbVendorId?: string;
  isDefault: boolean;
  mediaWidthMm: number; // Fully customizable by hospital
  mediaHeightMm: number; // Fully customizable (0 for continuous thermal rolls)
  printableWidthMm?: number;
  printableHeightMm?: number;
  marginTopMm: number;
  marginBottomMm: number;
  marginLeftMm: number;
  marginRightMm: number;
  orientation: "PORTRAIT" | "LANDSCAPE";
  dpi: number;
  status: "ONLINE" | "OFFLINE" | "READY";
}

export interface PrintTemplatesConfig {
  thermalToken: {
    headerTitle: string;
    subHeader: string;
    rollWidth: ThermalRollWidth;
    customWidthMm?: number;
    showEstimatedWait: boolean;
    showCashierReceipt: boolean;
    showBarcode: boolean;
    footerNotice: string;
  };
  wristband: {
    hospitalName: string;
    preset: WristbandPreset;
    widthMm: number;
    heightMm: number;
    printableLengthMm: number;
    orientation: "LANDSCAPE" | "PORTRAIT";
    printerType: "ZEBRA_HC100" | "DIRECT_THERMAL_ROLL" | "LASER_SHEETLET" | "STANDARD_POS";
    wristbandType: "ADULT_STANDARD" | "PEDIATRIC" | "INFANT_NICU" | "BARCODE_ONLY";
    showBloodGroup: boolean;
    showEmergencyPhone: boolean;
    showAllergyWarning: boolean;
    barcodeFormat: "CODE128" | "QR";
  };
  bedHeadTicket: {
    hospitalTitle: string;
    subTitle: string;
    showFinancialInfo: boolean;
    showNurseChecklist: boolean;
    showSignatureBlock: boolean;
    customSealText: string;
  };
  dischargeSummary: {
    hospitalHeader: string;
    subTitle: string;
    showMedicationReconciliation: boolean;
    showDietaryInstructions: boolean;
    showWarningSigns: boolean;
    showDoctorSealBlock: boolean;
    showSuperintendentSign: boolean;
    disclaimerText: string;
  };
}

const DEFAULT_PROFILE: HospitalProfile = {
  name: "Avinya Super-Specialty Apex Hospital",
  subdomain: "apollo-indraprastha",
  address: "Plot 12, Health City, Gachibowli, Hyderabad, Telangana 500032",
  phone: "+91 40 8829 0000",
  emergencyPhone: "1066 / +91 40 8829 0911",
  accreditation: "Accredited by NABH, NABL & JCI • Apex Multi-Specialty Care",
  taxGstin: "36AABCA1234D1Z5",
};

const DEFAULT_POLICIES: HospitalPolicies = {
  requireUpfrontPaymentForToken: true,
  enforceDpdpConsent: true,
  autoAlertMlcToPolice: true,
  allowTariffOverride: false,
  defaultBedView: "GRID",
  defaultRevisitFreeDays: 7,
  allowDoctorSpecificRevisitRules: true,
  enforceRevisitWindowExpiry: true,
};

export const DEFAULT_PRINT_TEMPLATES: PrintTemplatesConfig = {
  thermalToken: {
    headerTitle: "AVINYA HEALTHCARE APEX",
    subHeader: "OPD CONSULTATION TOKEN & RECEIPT",
    rollWidth: "80mm",
    showEstimatedWait: true,
    showCashierReceipt: true,
    showBarcode: true,
    footerNotice: "Please proceed to waiting lounge. Valid today only.",
  },
  wristband: {
    hospitalName: "AVINYA HEALTHCARE APEX",
    preset: "ADULT_STANDARD_280x25",
    widthMm: 280,
    heightMm: 25,
    printableLengthMm: 75,
    orientation: "LANDSCAPE",
    printerType: "DIRECT_THERMAL_ROLL",
    wristbandType: "ADULT_STANDARD",
    showBloodGroup: true,
    showEmergencyPhone: true,
    showAllergyWarning: true,
    barcodeFormat: "CODE128",
  },
  bedHeadTicket: {
    hospitalTitle: "AVINYA SUPER-SPECIALTY APEX HOSPITAL",
    subTitle: "INPATIENT ADMISSION FACE SHEET & BED HEAD TICKET (BHT)",
    showFinancialInfo: true,
    showNurseChecklist: true,
    showSignatureBlock: true,
    customSealText: "Accredited by NABH & JCI • Apex Multi-Specialty Care",
  },
  dischargeSummary: {
    hospitalHeader: "AVINYA SUPER-SPECIALTY APEX HOSPITAL",
    subTitle: "FORMAL STATUTORY INPATIENT DISCHARGE SUMMARY",
    showMedicationReconciliation: true,
    showDietaryInstructions: true,
    showWarningSigns: true,
    showDoctorSealBlock: true,
    showSuperintendentSign: true,
    disclaimerText: "This is a computer-generated statutory clinical discharge summary under NABH Clinical Standards.",
  },
};

const DEFAULT_DOCTORS: OpdDoctor[] = [
  { id: "doc-1", name: "Dr. Vikram Seth", specialty: "Interventional Cardiology", department: "Cardiology", roomNumber: "OPD Cabin 204", consultationFee: 800, currentWaitMins: 15, patientsWaiting: 4, isActive: true, revisitFreeWindowDays: 7, revisitMaxFreeVisits: 1, revisitDiscountPercent: 100 },
  { id: "doc-2", name: "Dr. Rajesh Sharma", specialty: "Internal Medicine", department: "General Medicine", roomNumber: "OPD Cabin 102", consultationFee: 500, currentWaitMins: 10, patientsWaiting: 6, isActive: true, revisitFreeWindowDays: 10, revisitMaxFreeVisits: 1, revisitDiscountPercent: 100 },
  { id: "doc-3", name: "Dr. Radhika Sen", specialty: "General & Laparoscopic Surgery", department: "General Surgery", roomNumber: "OPD Cabin 210", consultationFee: 800, currentWaitMins: 20, patientsWaiting: 3, isActive: true, revisitFreeWindowDays: 14, revisitMaxFreeVisits: 2, revisitDiscountPercent: 100 },
  { id: "doc-4", name: "Dr. Sunita Rao", specialty: "Pediatrics & Neonatology", department: "Pediatrics", roomNumber: "OPD Cabin 105", consultationFee: 600, currentWaitMins: 5, patientsWaiting: 2, isActive: true, revisitFreeWindowDays: 7, revisitMaxFreeVisits: 1, revisitDiscountPercent: 100 },
  { id: "doc-5", name: "Dr. Harish Patel", specialty: "Orthopedics & Joint Replacement", department: "Orthopedics", roomNumber: "OPD Cabin 215", consultationFee: 700, currentWaitMins: 25, patientsWaiting: 5, isActive: true, revisitFreeWindowDays: 10, revisitMaxFreeVisits: 1, revisitDiscountPercent: 100 },
  { id: "doc-6", name: "Dr. Anjali Nair", specialty: "Obstetrics & Gynecology", department: "Obstetrics & Gynecology", roomNumber: "OPD Cabin 112", consultationFee: 750, currentWaitMins: 12, patientsWaiting: 3, isActive: true, revisitFreeWindowDays: 7, revisitMaxFreeVisits: 1, revisitDiscountPercent: 100 },
  { id: "doc-7", name: "Dr. Sameer Joshi", specialty: "Critical Care & Pulmonology", department: "Pulmonology", roomNumber: "OPD Cabin 208", consultationFee: 750, currentWaitMins: 18, patientsWaiting: 4, isActive: true, revisitFreeWindowDays: 7, revisitMaxFreeVisits: 1, revisitDiscountPercent: 100 },
];

const DEFAULT_BEDS: EnterpriseBed[] = generateEnterprise500Beds();

export const DEFAULT_PRINTERS: HospitalPrinterDevice[] = [
  {
    id: "prn-1",
    name: "Front Desk Zebra ZD510-HC Dedicated Wristband Printer",
    location: "Admission Desk Counter 1",
    connectionType: "NETWORK_IP",
    targetCategory: "WRISTBAND",
    protocol: "RAW_ZPL",
    ipAddress: "192.168.1.182",
    port: 9100,
    isDefault: true,
    mediaWidthMm: 25,
    mediaHeightMm: 280,
    printableWidthMm: 22,
    printableHeightMm: 75,
    marginTopMm: 1,
    marginBottomMm: 1,
    marginLeftMm: 2,
    marginRightMm: 2,
    orientation: "PORTRAIT",
    dpi: 300,
    status: "ONLINE",
  },
  {
    id: "prn-2",
    name: "Reception Counter 1 Token & Receipt Slip Printer",
    location: "OPD Front Registration Counter 1",
    connectionType: "USB",
    targetCategory: "THERMAL_TOKEN",
    protocol: "RAW_ESCPOS",
    isDefault: true,
    mediaWidthMm: 80,
    mediaHeightMm: 0,
    printableWidthMm: 76,
    printableHeightMm: 0,
    marginTopMm: 2,
    marginBottomMm: 2,
    marginLeftMm: 2,
    marginRightMm: 2,
    orientation: "PORTRAIT",
    dpi: 203,
    status: "ONLINE",
  },
  {
    id: "prn-3",
    name: "Emergency Triage & Trauma WiFi Wristband Unit",
    location: "ED Resuscitation Bay 1",
    connectionType: "WIFI",
    targetCategory: "WRISTBAND",
    protocol: "HTML_DRIVER",
    ipAddress: "192.168.1.185",
    port: 9100,
    isDefault: false,
    mediaWidthMm: 28,
    mediaHeightMm: 280,
    printableWidthMm: 25,
    printableHeightMm: 80,
    marginTopMm: 1,
    marginBottomMm: 1,
    marginLeftMm: 2,
    marginRightMm: 2,
    orientation: "PORTRAIT",
    dpi: 300,
    status: "ONLINE",
  },
  {
    id: "prn-4",
    name: "Inpatient Clinical Ward Managed HP LaserJet",
    location: "Ward Nursing Station Central",
    connectionType: "NETWORK_IP",
    targetCategory: "CLINICAL_A4",
    protocol: "HTML_DRIVER",
    ipAddress: "192.168.1.190",
    port: 9100,
    isDefault: true,
    mediaWidthMm: 210,
    mediaHeightMm: 297,
    printableWidthMm: 200,
    printableHeightMm: 287,
    marginTopMm: 5,
    marginBottomMm: 5,
    marginLeftMm: 5,
    marginRightMm: 5,
    orientation: "PORTRAIT",
    dpi: 600,
    status: "ONLINE",
  },
  {
    id: "prn-5",
    name: "Central Phlebotomy Tube Barcode Labeler",
    location: "Diagnostics Specimen Collection Counter",
    connectionType: "USB",
    targetCategory: "LAB_LABEL",
    protocol: "RAW_ZPL",
    isDefault: true,
    mediaWidthMm: 50,
    mediaHeightMm: 25,
    printableWidthMm: 46,
    printableHeightMm: 22,
    marginTopMm: 1,
    marginBottomMm: 1,
    marginLeftMm: 2,
    marginRightMm: 2,
    orientation: "LANDSCAPE",
    dpi: 203,
    status: "ONLINE",
  },
];

interface HospitalConfigContextType {
  hospitalProfile: HospitalProfile;
  policies: HospitalPolicies;
  doctors: OpdDoctor[];
  beds: EnterpriseBed[];
  printTemplates: PrintTemplatesConfig;
  printers: HospitalPrinterDevice[];
  towers: string[];
  floors: string[];
  departments: string[];
  updateHospitalProfile: (profile: Partial<HospitalProfile>) => void;
  updatePolicies: (policies: Partial<HospitalPolicies>) => void;
  updatePrintTemplates: (templates: Partial<PrintTemplatesConfig>) => void;
  addBed: (bed: Omit<EnterpriseBed, "bedId">) => void;
  updateBed: (bedId: number, partial: Partial<EnterpriseBed>) => void;
  deleteBed: (bedId: number) => void;
  addDoctor: (doc: Omit<OpdDoctor, "id">) => void;
  updateDoctor: (docId: string, partial: Partial<OpdDoctor>) => void;
  deleteDoctor: (docId: string) => void;
  addPrinter: (printer: Omit<HospitalPrinterDevice, "id">) => void;
  updatePrinter: (printerId: string, partial: Partial<HospitalPrinterDevice>) => void;
  deletePrinter: (printerId: string) => void;
  setDefaultPrinter: (printerId: string) => void;
  getPrinterForCategory: (category: PrinterTargetCategory) => HospitalPrinterDevice | undefined;
  resetToDefaultCatalog: () => void;
}

const HospitalConfigContext = createContext<HospitalConfigContextType | undefined>(undefined);

const STORAGE_KEYS = {
  PROFILE: "avinya_hospital_profile",
  POLICIES: "avinya_hospital_policies",
  DOCTORS: "avinya_hospital_doctors",
  BEDS: "avinya_hospital_beds",
  PRINT_TEMPLATES: "avinya_hospital_print_templates",
  PRINTERS: "avinya_hospital_printers",
};

export function toBackendPrinter(device: HospitalPrinterDevice): HardwarePrinterBackendConfig {
  return {
    id: device.id,
    name: device.name,
    location: device.location,
    connection_type: device.connectionType,
    target_category: device.targetCategory,
    protocol: device.protocol,
    ip_address: device.ipAddress,
    port: device.port,
    media_width_mm: device.mediaWidthMm,
    media_height_mm: device.mediaHeightMm,
    printable_width_mm: device.printableWidthMm,
    printable_height_mm: device.printableHeightMm,
    margin_top_mm: device.marginTopMm,
    margin_bottom_mm: device.marginBottomMm,
    margin_left_mm: device.marginLeftMm,
    margin_right_mm: device.marginRightMm,
    orientation: device.orientation,
    dpi: device.dpi,
    status: device.status,
    is_default: device.isDefault,
  };
}

export function fromBackendPrinter(config: HardwarePrinterBackendConfig): HospitalPrinterDevice {
  return {
    id: config.id,
    name: config.name,
    location: config.location,
    connectionType: (config.connection_type as PrinterConnectionType) || "USB",
    targetCategory: (config.target_category as PrinterTargetCategory) || "THERMAL_TOKEN",
    protocol: (config.protocol as PrinterProtocol) || "RAW_ESCPOS",
    ipAddress: config.ip_address,
    port: config.port,
    mediaWidthMm: config.media_width_mm,
    mediaHeightMm: config.media_height_mm,
    printableWidthMm: config.printable_width_mm,
    printableHeightMm: config.printable_height_mm,
    marginTopMm: config.margin_top_mm ?? 0,
    marginBottomMm: config.margin_bottom_mm ?? 0,
    marginLeftMm: config.margin_left_mm ?? 0,
    marginRightMm: config.margin_right_mm ?? 0,
    orientation: (config.orientation as "PORTRAIT" | "LANDSCAPE") || "PORTRAIT",
    dpi: config.dpi || 203,
    status: (config.status as "ONLINE" | "OFFLINE" | "READY") || "ONLINE",
    isDefault: !!config.is_default,
  };
}

export const HospitalConfigProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [hospitalProfile, setHospitalProfile] = useState<HospitalProfile>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEYS.PROFILE);
      return saved ? JSON.parse(saved) : DEFAULT_PROFILE;
    } catch {
      return DEFAULT_PROFILE;
    }
  });

  const [policies, setPolicies] = useState<HospitalPolicies>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEYS.POLICIES);
      return saved ? JSON.parse(saved) : DEFAULT_POLICIES;
    } catch {
      return DEFAULT_POLICIES;
    }
  });

  const [doctors, setDoctors] = useState<OpdDoctor[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEYS.DOCTORS);
      return saved ? JSON.parse(saved) : DEFAULT_DOCTORS;
    } catch {
      return DEFAULT_DOCTORS;
    }
  });

  const [beds, setBeds] = useState<EnterpriseBed[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEYS.BEDS);
      const parsed = saved ? JSON.parse(saved) : null;
      if (parsed && Array.isArray(parsed) && parsed.length >= 100) {
        return parsed;
      }
      return DEFAULT_BEDS;
    } catch {
      return DEFAULT_BEDS;
    }
  });

  const [printTemplates, setPrintTemplates] = useState<PrintTemplatesConfig>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEYS.PRINT_TEMPLATES);
      return saved ? JSON.parse(saved) : DEFAULT_PRINT_TEMPLATES;
    } catch {
      return DEFAULT_PRINT_TEMPLATES;
    }
  });

  const [printers, setPrinters] = useState<HospitalPrinterDevice[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEYS.PRINTERS);
      return saved ? JSON.parse(saved) : DEFAULT_PRINTERS;
    } catch {
      return DEFAULT_PRINTERS;
    }
  });

  // Save to localStorage whenever state changes
  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.PROFILE, JSON.stringify(hospitalProfile));
  }, [hospitalProfile]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.POLICIES, JSON.stringify(policies));
  }, [policies]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.DOCTORS, JSON.stringify(doctors));
  }, [doctors]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.BEDS, JSON.stringify(beds));
  }, [beds]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.PRINT_TEMPLATES, JSON.stringify(printTemplates));
  }, [printTemplates]);

  // Synchronize physical printers from backend / Redis on mount
  useEffect(() => {
    let isMounted = true;
    uiApi
      .getFacilityPrinters()
      .then((backendPrinters) => {
        if (isMounted && backendPrinters && backendPrinters.length > 0) {
          const mapped = backendPrinters.map(fromBackendPrinter);
          setPrinters(mapped);
          localStorage.setItem(STORAGE_KEYS.PRINTERS, JSON.stringify(mapped));
        }
      })
      .catch((err) => {
        console.warn("Facility printers backend sync offline, using local configuration", err);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const isPrintersInitialMount = useRef(true);
  useEffect(() => {
    localStorage.setItem(STORAGE_KEYS.PRINTERS, JSON.stringify(printers));
    if (isPrintersInitialMount.current) {
      isPrintersInitialMount.current = false;
      return;
    }
    const timer = setTimeout(() => {
      uiApi
        .saveFacilityPrinters(printers.map(toBackendPrinter))
        .catch((err) => console.warn("Failed persisting facility printers to backend:", err));
    }, 800);
    return () => clearTimeout(timer);
  }, [printers]);

  const updateHospitalProfile = (partial: Partial<HospitalProfile>) => {
    setHospitalProfile((prev) => ({ ...prev, ...partial }));
  };

  const updatePolicies = (partial: Partial<HospitalPolicies>) => {
    setPolicies((prev) => ({ ...prev, ...partial }));
  };

  const updatePrintTemplates = (partial: Partial<PrintTemplatesConfig>) => {
    setPrintTemplates((prev) => ({ ...prev, ...partial }));
  };

  const addBed = (bed: Omit<EnterpriseBed, "bedId">) => {
    const nextId = beds.length > 0 ? Math.max(...beds.map((b) => b.bedId)) + 1 : 201;
    const newBed: EnterpriseBed = { ...bed, bedId: nextId };
    setBeds((prev) => [newBed, ...prev]);
  };

  const updateBed = (bedId: number, partial: Partial<EnterpriseBed>) => {
    setBeds((prev) => prev.map((b) => (b.bedId === bedId ? { ...b, ...partial } : b)));
  };

  const deleteBed = (bedId: number) => {
    setBeds((prev) => prev.filter((b) => b.bedId !== bedId));
  };

  const addDoctor = (doc: Omit<OpdDoctor, "id">) => {
    const nextId = `doc-${Date.now().toString().slice(-4)}`;
    const newDoc: OpdDoctor = { ...doc, id: nextId };
    setDoctors((prev) => [...prev, newDoc]);
  };

  const updateDoctor = (docId: string, partial: Partial<OpdDoctor>) => {
    setDoctors((prev) => prev.map((d) => (d.id === docId ? { ...d, ...partial } : d)));
  };

  const deleteDoctor = (docId: string) => {
    setDoctors((prev) => prev.filter((d) => d.id !== docId));
  };

  const addPrinter = (printer: Omit<HospitalPrinterDevice, "id">) => {
    const nextId = `prn-${Date.now().toString().slice(-4)}`;
    const newPrn: HospitalPrinterDevice = { ...printer, id: nextId };
    setPrinters((prev) => [...prev, newPrn]);
  };

  const updatePrinter = (printerId: string, partial: Partial<HospitalPrinterDevice>) => {
    setPrinters((prev) => prev.map((p) => (p.id === printerId ? { ...p, ...partial } : p)));
  };

  const deletePrinter = (printerId: string) => {
    setPrinters((prev) => prev.filter((p) => p.id !== printerId));
  };

  const setDefaultPrinter = (printerId: string) => {
    const target = printers.find((p) => p.id === printerId);
    if (!target) return;
    setPrinters((prev) =>
      prev.map((p) =>
        p.targetCategory === target.targetCategory
          ? { ...p, isDefault: p.id === printerId }
          : p
      )
    );
  };

  const getPrinterForCategory = (category: PrinterTargetCategory): HospitalPrinterDevice | undefined => {
    return printers.find((p) => p.targetCategory === category && p.isDefault) || printers.find((p) => p.targetCategory === category);
  };

  const resetToDefaultCatalog = () => {
    setHospitalProfile(DEFAULT_PROFILE);
    setPolicies(DEFAULT_POLICIES);
    setDoctors(DEFAULT_DOCTORS);
    setBeds(DEFAULT_BEDS);
    setPrintTemplates(DEFAULT_PRINT_TEMPLATES);
    setPrinters(DEFAULT_PRINTERS);
    localStorage.removeItem(STORAGE_KEYS.PROFILE);
    localStorage.removeItem(STORAGE_KEYS.POLICIES);
    localStorage.removeItem(STORAGE_KEYS.DOCTORS);
    localStorage.removeItem(STORAGE_KEYS.BEDS);
    localStorage.removeItem(STORAGE_KEYS.PRINT_TEMPLATES);
    localStorage.removeItem(STORAGE_KEYS.PRINTERS);
  };

  // Derive unique towers, floors, and departments from configured dataset
  const towers = Array.from(new Set(beds.map((b) => b.tower)));
  const floors = Array.from(new Set(beds.map((b) => b.floor)));
  const departments = Array.from(new Set(doctors.map((d) => d.department)));

  return (
    <HospitalConfigContext.Provider
      value={{
        hospitalProfile,
        policies,
        doctors,
        beds,
        printTemplates,
        printers,
        towers,
        floors,
        departments,
        updateHospitalProfile,
        updatePolicies,
        updatePrintTemplates,
        addBed,
        updateBed,
        deleteBed,
        addDoctor,
        updateDoctor,
        deleteDoctor,
        addPrinter,
        updatePrinter,
        deletePrinter,
        setDefaultPrinter,
        getPrinterForCategory,
        resetToDefaultCatalog,
      }}
    >
      {children}
    </HospitalConfigContext.Provider>
  );
};

export const useHospitalConfig = (): HospitalConfigContextType => {
  const context = useContext(HospitalConfigContext);
  if (!context) {
    throw new Error("useHospitalConfig must be used within a HospitalConfigProvider");
  }
  return context;
};

