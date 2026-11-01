import React, { createContext, useContext, useState, useEffect } from "react";
import { generateEnterprise500Beds } from "../../data/enterpriseBeds";

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
};

const DEFAULT_DOCTORS: OpdDoctor[] = [
  { id: "doc-1", name: "Dr. Vikram Seth", specialty: "Interventional Cardiology", department: "Cardiology", roomNumber: "OPD Cabin 204", consultationFee: 800, currentWaitMins: 15, patientsWaiting: 4, isActive: true },
  { id: "doc-2", name: "Dr. Rajesh Sharma", specialty: "Internal Medicine", department: "General Medicine", roomNumber: "OPD Cabin 102", consultationFee: 500, currentWaitMins: 10, patientsWaiting: 6, isActive: true },
  { id: "doc-3", name: "Dr. Radhika Sen", specialty: "General & Laparoscopic Surgery", department: "General Surgery", roomNumber: "OPD Cabin 210", consultationFee: 800, currentWaitMins: 20, patientsWaiting: 3, isActive: true },
  { id: "doc-4", name: "Dr. Sunita Rao", specialty: "Pediatrics & Neonatology", department: "Pediatrics", roomNumber: "OPD Cabin 105", consultationFee: 600, currentWaitMins: 5, patientsWaiting: 2, isActive: true },
  { id: "doc-5", name: "Dr. Harish Patel", specialty: "Orthopedics & Joint Replacement", department: "Orthopedics", roomNumber: "OPD Cabin 215", consultationFee: 700, currentWaitMins: 25, patientsWaiting: 5, isActive: true },
  { id: "doc-6", name: "Dr. Anjali Nair", specialty: "Obstetrics & Gynecology", department: "Obstetrics & Gynecology", roomNumber: "OPD Cabin 112", consultationFee: 750, currentWaitMins: 12, patientsWaiting: 3, isActive: true },
  { id: "doc-7", name: "Dr. Sameer Joshi", specialty: "Critical Care & Pulmonology", department: "Pulmonology", roomNumber: "OPD Cabin 208", consultationFee: 750, currentWaitMins: 18, patientsWaiting: 4, isActive: true },
];

const DEFAULT_BEDS: EnterpriseBed[] = generateEnterprise500Beds();

interface HospitalConfigContextType {
  hospitalProfile: HospitalProfile;
  policies: HospitalPolicies;
  doctors: OpdDoctor[];
  beds: EnterpriseBed[];
  towers: string[];
  floors: string[];
  departments: string[];
  updateHospitalProfile: (profile: Partial<HospitalProfile>) => void;
  updatePolicies: (policies: Partial<HospitalPolicies>) => void;
  addBed: (bed: Omit<EnterpriseBed, "bedId">) => void;
  updateBed: (bedId: number, partial: Partial<EnterpriseBed>) => void;
  deleteBed: (bedId: number) => void;
  addDoctor: (doc: Omit<OpdDoctor, "id">) => void;
  updateDoctor: (docId: string, partial: Partial<OpdDoctor>) => void;
  deleteDoctor: (docId: string) => void;
  resetToDefaultCatalog: () => void;
}

const HospitalConfigContext = createContext<HospitalConfigContextType | undefined>(undefined);

const STORAGE_KEYS = {
  PROFILE: "avinya_hospital_profile",
  POLICIES: "avinya_hospital_policies",
  DOCTORS: "avinya_hospital_doctors",
  BEDS: "avinya_hospital_beds",
};

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

  const updateHospitalProfile = (partial: Partial<HospitalProfile>) => {
    setHospitalProfile((prev) => ({ ...prev, ...partial }));
  };

  const updatePolicies = (partial: Partial<HospitalPolicies>) => {
    setPolicies((prev) => ({ ...prev, ...partial }));
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

  const resetToDefaultCatalog = () => {
    setHospitalProfile(DEFAULT_PROFILE);
    setPolicies(DEFAULT_POLICIES);
    setDoctors(DEFAULT_DOCTORS);
    setBeds(DEFAULT_BEDS);
    localStorage.removeItem(STORAGE_KEYS.PROFILE);
    localStorage.removeItem(STORAGE_KEYS.POLICIES);
    localStorage.removeItem(STORAGE_KEYS.DOCTORS);
    localStorage.removeItem(STORAGE_KEYS.BEDS);
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
        towers,
        floors,
        departments,
        updateHospitalProfile,
        updatePolicies,
        addBed,
        updateBed,
        deleteBed,
        addDoctor,
        updateDoctor,
        deleteDoctor,
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

