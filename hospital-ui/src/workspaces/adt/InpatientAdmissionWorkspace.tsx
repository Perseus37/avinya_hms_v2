import React, { useState, useEffect } from "react";
import {
  DoorOpen,
  BedDouble,
  User,
  ShieldAlert,
  CreditCard,
  Printer,
  Activity,
  ArrowRightLeft,
  LogOut,
  Search,
  Filter,
  CheckCircle2,
  Building,
  Layers,
  LayoutGrid,
  Table as TableIcon,
  Sparkles,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { useActivePatient } from "../../core/context/ActivePatientContext";
import { useHospitalConfig } from "../../core/context/HospitalConfigContext";
import { PermissionGate } from "../../components/auth/PermissionGate";
import { printDocument } from "../../utils/printDocument";
import { uiApi } from "../../api/uiApi";
import { PatientQuickSearchItem } from "../../types";

export interface MasterPatientRecord {
  id: number;
  mrn: string;
  name: string;
  gender: "MALE" | "FEMALE" | "OTHER";
  age: number;
  bloodGroup: string;
  phone: string;
  allergies: string[];
  activeDiagnosis: string;
  preferredDoctor: string;
  insurancePayer: string;
  insurancePreAuth: number;
}

const MASTER_PATIENT_DIRECTORY: MasterPatientRecord[] = [
  {
    id: 1,
    mrn: "MRN-2026-0001",
    name: "Siddharth Verma",
    gender: "MALE",
    age: 38,
    bloodGroup: "B+",
    phone: "9876543210",
    allergies: ["Penicillin G", "Sulfa drugs"],
    activeDiagnosis: "Acute Coronary Syndrome • Unstable Angina (Troponin-T: 0.14 ng/mL)",
    preferredDoctor: "Dr. Vikram Seth (Cardiology)",
    insurancePayer: "Star Health Insurance",
    insurancePreAuth: 150000,
  },
  {
    id: 2,
    mrn: "MRN-2026-0002",
    name: "Ananya Deshmukh",
    gender: "FEMALE",
    age: 32,
    bloodGroup: "O+",
    phone: "9123456780",
    allergies: ["NSAIDs (Ibuprofen)"],
    activeDiagnosis: "Severe Dengue with Thrombocytopenia (Platelets: 28,000/μL)",
    preferredDoctor: "Dr. Sameer Joshi (Critical Care / ICU)",
    insurancePayer: "HDFC ERGO Health",
    insurancePreAuth: 300000,
  },
  {
    id: 3,
    mrn: "MRN-2026-0003",
    name: "Vikramaditya Singhania",
    gender: "MALE",
    age: 64,
    bloodGroup: "A+",
    phone: "9811223344",
    allergies: ["Ciprofloxacin"],
    activeDiagnosis: "Grade-IV Bilateral Knee Osteoarthritis • Planned Left TKA",
    preferredDoctor: "Dr. Harish Patel (Orthopedics)",
    insurancePayer: "Max Bupa / Niva Bupa",
    insurancePreAuth: 220000,
  },
  {
    id: 4,
    mrn: "MRN-2026-0004",
    name: "Meenakshi Sundaram",
    gender: "FEMALE",
    age: 45,
    bloodGroup: "AB+",
    phone: "9444332211",
    allergies: [],
    activeDiagnosis: "Acute Calculous Cholecystitis • Planned Lap Cholecystectomy",
    preferredDoctor: "Dr. Radhika Sen (General Surgery)",
    insurancePayer: "Care Health Insurance",
    insurancePreAuth: 180000,
  },
  {
    id: 5,
    mrn: "MRN-2026-0005",
    name: "Rajeshwari Rao",
    gender: "FEMALE",
    age: 29,
    bloodGroup: "O-",
    phone: "9700112233",
    allergies: ["Latex"],
    activeDiagnosis: "High-Risk Primigravida 34 Weeks • Gestational Hypertension",
    preferredDoctor: "Dr. Anjali Nair (Obstetrics & Gynecology)",
    insurancePayer: "Star Health Insurance",
    insurancePreAuth: 140000,
  },
  {
    id: 6,
    mrn: "MRN-2026-0006",
    name: "Farhan Qureshi",
    gender: "MALE",
    age: 52,
    bloodGroup: "B-",
    phone: "9988776655",
    allergies: ["Contrast Dye"],
    activeDiagnosis: "Type 2 Diabetic Foot Gangrene with Sepsis",
    preferredDoctor: "Dr. Rajesh Sharma (General Medicine)",
    insurancePayer: "ICICI Lombard",
    insurancePreAuth: 250000,
  },
];

interface ActiveAdmissionItem {
  id: number;
  mrn: string;
  patientName: string;
  admissionType: string;
  ward: string;
  bedNumber: string;
  roomNumber: string;
  admittingDoctor: string;
  admittedAt: string;
  isMlc: boolean;
  tpaInsurance?: string;
  edd: string;
  clearances: {
    clinicalSummary: boolean;
    pharmacyCleared: boolean;
    tpaApproved: boolean;
    cashierSettled: boolean;
  };
}

export const InpatientAdmissionWorkspace: React.FC = () => {
  const { patientSummary } = useActivePatient();
  const { beds: ENTERPRISE_BED_POOL, hospitalProfile, printTemplates, getPrinterForCategory } = useHospitalConfig();
  const [errorMessage, setErrorMessage] = useState("");
  const [isSuccessModalOpen, setIsSuccessModalOpen] = useState(false);
  const [confirmedAdmission, setConfirmedAdmission] = useState<ActiveAdmissionItem | null>(null);

  // Active Admissions Census
  const [admissions, setAdmissions] = useState<ActiveAdmissionItem[]>([
    {
      id: 101,
      mrn: "MRN-2026-0001",
      patientName: "Siddharth Verma",
      admissionType: "ELECTIVE",
      ward: "General Inpatient Ward 1",
      bedNumber: "B-101",
      roomNumber: "R-101",
      admittingDoctor: "Dr. Vikram Seth (Cardiology)",
      admittedAt: "2026-10-31 09:30",
      isMlc: false,
      tpaInsurance: "Star Health (Auth: ₹1,50,000)",
      edd: "2026-11-03",
      clearances: {
        clinicalSummary: true,
        pharmacyCleared: true,
        tpaApproved: true,
        cashierSettled: false,
      },
    },
    {
      id: 102,
      mrn: "ER-0914",
      patientName: "Ananya Deshmukh",
      admissionType: "EMERGENCY",
      ward: "Intensive Care Unit (ICU)",
      bedNumber: "ICU-03",
      roomNumber: "ICU-BAY-A",
      admittingDoctor: "Dr. Sameer Joshi (Emergency / CCU)",
      admittedAt: "2026-10-31 14:10",
      isMlc: false,
      tpaInsurance: "HDFC ERGO (Auth: ₹3,00,000)",
      edd: "2026-11-05",
      clearances: {
        clinicalSummary: false,
        pharmacyCleared: false,
        tpaApproved: true,
        cashierSettled: false,
      },
    },
  ]);

  // Hierarchical Bed Navigator State
  const [selectedTower, setSelectedTower] = useState<string>("ALL");
  const [selectedFloor, setSelectedFloor] = useState<string>("ALL");
  const [bedCategoryFilter, setBedCategoryFilter] = useState<"ALL" | "General" | "Semi-Private" | "Private" | "ICU">("ALL");
  const [selectedStatus, setSelectedStatus] = useState<string>("ALL");
  const [selectedEquipment, setSelectedEquipment] = useState<string>("ALL");
  const [bedSearchQuery, setBedSearchQuery] = useState("");
  const [bedViewMode, setBedViewMode] = useState<"GRID" | "TABLE">("GRID");
  const [bedPage, setBedPage] = useState(1);
  const [bedPageSize, setBedPageSize] = useState<number>(36);

  // Patient MPI Search & Auto-Population State
  const [patientSearchQuery, setPatientSearchQuery] = useState("");
  const [isPatientDropdownOpen, setIsPatientDropdownOpen] = useState(false);
  const [selectedPatientRecord, setSelectedPatientRecord] = useState<MasterPatientRecord | null>(MASTER_PATIENT_DIRECTORY[0]);
  const [mpiSearchResults, setMpiSearchResults] = useState<PatientQuickSearchItem[]>([]);
  const [isSearchingMpi, setIsSearchingMpi] = useState(false);

  // Form State
  const [targetPatientName, setTargetPatientName] = useState(MASTER_PATIENT_DIRECTORY[0].name);
  const [targetMrn, setTargetMrn] = useState(MASTER_PATIENT_DIRECTORY[0].mrn);
  const [admissionType, setAdmissionType] = useState<"EMERGENCY" | "ELECTIVE" | "DAYCARE" | "MATERNITY" | "ICU_TRANSFER">("ELECTIVE");
  const [selectedBedId, setSelectedBedId] = useState<number>(201);
  const [admittingDoctor, setAdmittingDoctor] = useState(MASTER_PATIENT_DIRECTORY[0].preferredDoctor);
  const [admissionDiagnosis, setAdmissionDiagnosis] = useState(MASTER_PATIENT_DIRECTORY[0].activeDiagnosis);
  
  // MLC State
  const [isMlc, setIsMlc] = useState(false);
  const [policeStation, setPoliceStation] = useState("");
  const [mlcNumber, setMlcNumber] = useState("");

  // Insurance State
  const [hasInsurance, setHasInsurance] = useState(true);
  const [payerName, setPayerName] = useState(MASTER_PATIENT_DIRECTORY[0].insurancePayer);
  const [preAuthAmount, setPreAuthAmount] = useState(MASTER_PATIENT_DIRECTORY[0].insurancePreAuth.toString());

  // Attendant & Visitor Pass State
  const [attendantName, setAttendantName] = useState("");
  const [attendantRelation, setAttendantRelation] = useState("Spouse / Relative");
  const [attendantPhone, setAttendantPhone] = useState("");

  // Bed Transfer State
  const [isTransferModalOpen, setIsTransferModalOpen] = useState(false);
  const [transferringAdmission, setTransferringAdmission] = useState<ActiveAdmissionItem | null>(null);
  const [transferDestinationBedId, setTransferDestinationBedId] = useState<number>(203);
  const [transferReason, setTransferReason] = useState("Clinical step-down / condition stable");

  // Clinical Discharge State
  const [isDischargeModalOpen, setIsDischargeModalOpen] = useState(false);
  const [dischargingAdmission, setDischargingAdmission] = useState<ActiveAdmissionItem | null>(null);
  const [dischargeDisposition, setDischargeDisposition] = useState<
    "ROUTINE_DISCHARGE" | "REFERRED_OUT" | "AGAINST_MEDICAL_ADVICE" | "DECEASED"
  >("ROUTINE_DISCHARGE");
  const [dischargeSummaryNotes, setDischargeSummaryNotes] = useState(
    "Patient is clinically and hemodynamically stable. Nil acute complaints. Prescriptions explained. Follow-up advised in OPD."
  );
  const [followupDate, setFollowupDate] = useState("2026-11-08");
  const [isDischargeSummaryOpen, setIsDischargeSummaryOpen] = useState(false);
  const [lastDischargedRecord, setLastDischargedRecord] = useState<{
    admission: ActiveAdmissionItem;
    disposition: string;
    summaryNotes: string;
    followup: string;
    dischargedAt: string;
  } | null>(null);

  const handleSelectPatient = (p: MasterPatientRecord) => {
    setSelectedPatientRecord(p);
    setTargetPatientName(p.name);
    setTargetMrn(p.mrn);
    setAdmissionDiagnosis(p.activeDiagnosis);
    setAdmittingDoctor(p.preferredDoctor);
    setPayerName(p.insurancePayer);
    setPreAuthAmount(p.insurancePreAuth.toString());
    setHasInsurance(p.insurancePreAuth > 0);
    setIsPatientDropdownOpen(false);
    setPatientSearchQuery("");
  };

  const handleSelectMpiPatient = (item: PatientQuickSearchItem) => {
    setTargetPatientName(item.full_name);
    setTargetMrn(item.mrn);
    setAdmissionDiagnosis("Inpatient Admission Evaluation");
    setIsPatientDropdownOpen(false);
    setPatientSearchQuery("");
  };

  // Debounced Live MPI Quick Search
  useEffect(() => {
    if (!patientSearchQuery.trim() || patientSearchQuery.trim().length < 2) {
      setMpiSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setIsSearchingMpi(true);
      try {
        const results = await uiApi.quickSearchPatients(patientSearchQuery.trim());
        setMpiSearchResults(results);
        setIsPatientDropdownOpen(true);
      } catch {
        setMpiSearchResults([]);
      } finally {
        setIsSearchingMpi(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [patientSearchQuery]);

  useEffect(() => {
    if (patientSummary) {
      setTargetPatientName(patientSummary.full_name);
      setTargetMrn(patientSummary.mrn);
      const match = MASTER_PATIENT_DIRECTORY.find((p) => p.mrn === patientSummary.mrn);
      if (match) {
        setSelectedPatientRecord(match);
        setAdmissionDiagnosis(match.activeDiagnosis);
        setAdmittingDoctor(match.preferredDoctor);
        setPayerName(match.insurancePayer);
        setPreAuthAmount(match.insurancePreAuth.toString());
      }
    }
  }, [patientSummary]);

  // Dynamic Campus Towers extracted from 500+ Bed Pool
  const campusTowers = Array.from(new Set(ENTERPRISE_BED_POOL.map((b) => b.tower)));
  const campusFloors = Array.from(new Set(ENTERPRISE_BED_POOL.map((b) => b.floor)));

  // Filter beds according to 500+ scale hierarchical criteria
  const filteredBeds = ENTERPRISE_BED_POOL.filter((bed) => {
    if (selectedTower !== "ALL" && bed.tower !== selectedTower) return false;
    if (selectedFloor !== "ALL" && bed.floor !== selectedFloor) return false;
    if (bedCategoryFilter !== "ALL" && bed.category !== bedCategoryFilter) return false;
    if (selectedStatus !== "ALL" && bed.status !== selectedStatus) return false;
    if (selectedEquipment !== "ALL") {
      const hasEq = bed.features.some((f) => f.toLowerCase().includes(selectedEquipment.toLowerCase()));
      if (!hasEq) return false;
    }
    if (bedSearchQuery.trim()) {
      const q = bedSearchQuery.toLowerCase();
      const matchBed = bed.bedNumber.toLowerCase().includes(q);
      const matchRoom = bed.roomNumber.toLowerCase().includes(q);
      const matchWard = bed.wardName.toLowerCase().includes(q);
      const matchPatient = bed.occupiedBy?.patientName.toLowerCase().includes(q);
      if (!matchBed && !matchRoom && !matchWard && !matchPatient) return false;
    }
    return true;
  });

  // 500+ Bed Pagination
  const totalBedPages = Math.max(1, Math.ceil(filteredBeds.length / bedPageSize));
  const paginatedBeds = filteredBeds.slice((bedPage - 1) * bedPageSize, bedPage * bedPageSize);

  const vacantBedsCount = ENTERPRISE_BED_POOL.filter((b) => b.status === "VACANT_CLEAN").length;
  const occupiedBedsCount = ENTERPRISE_BED_POOL.filter((b) => b.status === "OCCUPIED").length;
  const housekeepingBedsCount = ENTERPRISE_BED_POOL.filter((b) => b.status === "HOUSEKEEPING").length;
  const reservedBedsCount = ENTERPRISE_BED_POOL.filter((b) => b.status === "RESERVED").length;

  const handleAdmissionSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage("");

    const chosenBed = ENTERPRISE_BED_POOL.find((b) => b.bedId === selectedBedId);
    if (!chosenBed) {
      setErrorMessage("Please select a bed from the campus matrix.");
      return;
    }

    if (chosenBed.status !== "VACANT_CLEAN") {
      setErrorMessage(`Bed ${chosenBed.bedNumber} is not ready for admission (Status: ${chosenBed.status}). Please choose an available green vacant bed.`);
      return;
    }

    const newAdmission: ActiveAdmissionItem = {
      id: 100 + admissions.length + 1,
      mrn: targetMrn,
      patientName: targetPatientName,
      admissionType,
      ward: chosenBed.wardName,
      bedNumber: chosenBed.bedNumber,
      roomNumber: chosenBed.roomNumber,
      admittingDoctor,
      admittedAt: new Date().toISOString().replace("T", " ").substring(0, 16),
      isMlc,
      tpaInsurance: hasInsurance ? `${payerName} (Auth: ₹${parseInt(preAuthAmount || "0").toLocaleString()})` : undefined,
      edd: new Date(Date.now() + 3 * 86400000).toISOString().slice(0, 10),
      clearances: {
        clinicalSummary: false,
        pharmacyCleared: false,
        tpaApproved: hasInsurance,
        cashierSettled: false,
      },
    };

    setAdmissions([newAdmission, ...admissions]);
    setConfirmedAdmission(newAdmission);
    setIsSuccessModalOpen(true);
  };

  const handleOpenTransfer = (adm: ActiveAdmissionItem) => {
    setTransferringAdmission(adm);
    const firstOther = ENTERPRISE_BED_POOL.find((b) => b.bedNumber !== adm.bedNumber && b.status === "VACANT_CLEAN");
    if (firstOther) {
      setTransferDestinationBedId(firstOther.bedId);
    }
    setIsTransferModalOpen(true);
  };

  const handleExecuteTransfer = (e: React.FormEvent) => {
    e.preventDefault();
    if (!transferringAdmission) return;
    const destBed = ENTERPRISE_BED_POOL.find((b) => b.bedId === transferDestinationBedId);
    if (!destBed) return;

    setAdmissions((prev) =>
      prev.map((a) =>
        a.id === transferringAdmission.id
          ? {
              ...a,
              ward: destBed.wardName,
              bedNumber: destBed.bedNumber,
              roomNumber: destBed.roomNumber,
            }
          : a
      )
    );

    setIsTransferModalOpen(false);
    setTransferringAdmission(null);
  };

  const handleOpenDischarge = (adm: ActiveAdmissionItem) => {
    setDischargingAdmission(adm);
    setIsDischargeModalOpen(true);
  };

  const handleExecuteDischarge = (e: React.FormEvent) => {
    e.preventDefault();
    if (!dischargingAdmission) return;

    const record = {
      admission: dischargingAdmission,
      disposition: dischargeDisposition,
      summaryNotes: dischargeSummaryNotes,
      followup: followupDate,
      dischargedAt: new Date().toISOString().replace("T", " ").substring(0, 16),
    };

    setLastDischargedRecord(record);
    setAdmissions((prev) => prev.filter((a) => a.id !== dischargingAdmission.id));
    setIsDischargeModalOpen(false);
    setDischargingAdmission(null);
    setIsDischargeSummaryOpen(true);
  };

  const handlePrintBHT = () => {
    if (!confirmedAdmission) return;
    const template = printTemplates.bedHeadTicket;
    const html = `
      <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 680px; margin: 0 auto; border: 1px solid #333; padding: 24px;">
        <div style="text-align: center; border-bottom: 2px solid #000; padding-bottom: 12px; margin-bottom: 16px;">
          <h2 style="margin: 0; font-size: 20px; text-transform: uppercase;">${template.hospitalTitle || hospitalProfile.name}</h2>
          <div style="font-size: 11px; font-weight: bold; color: #444; margin-top: 2px;">${template.subTitle}</div>
          <div style="font-size: 10px; color: #666;">${hospitalProfile.accreditation} • Phone: ${hospitalProfile.phone}</div>
        </div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 14px; font-family: monospace; font-size: 13px;">
          <div><b>ADMISSION DOCKET:</b> ADM-${confirmedAdmission.id}</div>
          <div><b>ASSIGNED BED:</b> Bed ${confirmedAdmission.bedNumber} (${confirmedAdmission.roomNumber})</div>
        </div>
        <div style="border: 1px solid #ccc; padding: 12px; font-size: 12px; margin-bottom: 14px; line-height: 1.6;">
          <div><b>Patient Legal Name:</b> ${confirmedAdmission.patientName.toUpperCase()}</div>
          <div><b>UHID / MRN:</b> ${confirmedAdmission.mrn}</div>
          <div><b>Ward / Department:</b> ${confirmedAdmission.ward}</div>
          <div><b>Admitting Consultant:</b> ${confirmedAdmission.admittingDoctor}</div>
          <div><b>Admission Timestamp:</b> ${confirmedAdmission.admittedAt}</div>
          ${template.showFinancialInfo ? `<div><b>Financial Classification:</b> ${confirmedAdmission.tpaInsurance || "Self-Pay / Cash"}</div>` : ""}
        </div>
        <div style="text-align: center; padding: 10px; background: #f5f5f5; border: 1px solid #ccc; font-family: monospace; letter-spacing: 4px; font-size: 14px; margin-bottom: 16px;">
          *ADM-${confirmedAdmission.id}-${confirmedAdmission.mrn}*
        </div>
        ${template.showNurseChecklist ? `
        <div style="border: 1px solid #ddd; padding: 10px; margin-bottom: 16px; font-size: 11px; background: #fafafa;">
          <div style="font-weight: bold; margin-bottom: 6px; text-transform: uppercase; color: #333;">Nursing Intake Checklist:</div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px;">
            <div>[ ] Bedside Wristband Affixed & Verified</div>
            <div>[ ] Initial Vital Signs & NEWS2 Scored</div>
            <div>[ ] Allergy & Fall Risk Bands Applied</div>
            <div>[ ] Valuables Handover / Inventory Signed</div>
          </div>
        </div>
        ` : ""}
        ${template.showSignatureBlock ? `
        <div style="display: flex; justify-content: space-between; margin-top: 50px; font-size: 11px;">
          <div style="border-top: 1px solid #000; width: 220px; text-align: center; padding-top: 4px;">ADT Officer Signature</div>
          <div style="border-top: 1px solid #000; width: 220px; text-align: center; padding-top: 4px;">Patient / Guardian Signature</div>
        </div>
        ` : ""}
        <div style="margin-top: 24px; text-align: center; font-size: 9px; color: #777;">
          ${template.customSealText}
        </div>
      </div>
    `;
    const a4Printer = getPrinterForCategory("CLINICAL_A4");
    printDocument(html, { title: `BHT_${confirmedAdmission.mrn}`, docType: "CLINICAL_SUMMARY", printerDevice: a4Printer });
  };

  const handlePrintAdmissionWristband = () => {
    if (!confirmedAdmission) return;
    const template = printTemplates.wristband;
    const printerDevice = getPrinterForCategory("WRISTBAND");
    const html = `
      <div class="wristband-slip">
        <div>
          <div class="bold" style="font-size: 11px;">${(template.hospitalName || hospitalProfile.name).toUpperCase()}</div>
          <div class="bold" style="font-size: 13px; margin-top: 2px;">${confirmedAdmission.patientName.toUpperCase()}</div>
          <div style="font-size: 9px;">${confirmedAdmission.ward} • Bed: ${confirmedAdmission.bedNumber}</div>
          <div style="font-size: 8px;">Attending: ${confirmedAdmission.admittingDoctor}</div>
          ${template.showAllergyWarning ? `<div class="allergy-tag" style="margin-top: 2px;">ALLERGIES: VERIFY AT BEDSIDE</div>` : ""}
        </div>
        <div class="center">
          <div class="barcode-box">||||| | |||| || ||| | |||</div>
          <div class="bold" style="font-size: 12px;">${confirmedAdmission.mrn}</div>
        </div>
      </div>
    `;
    printDocument(html, {
      title: `Admission_Wristband_${confirmedAdmission.mrn}`,
      docType: "WRISTBAND",
      wristbandConfig: {
        widthMm: printerDevice?.mediaWidthMm || template.widthMm || 280,
        heightMm: printerDevice?.mediaHeightMm || template.heightMm || 25,
        printableLengthMm: printerDevice?.printableHeightMm || printerDevice?.printableWidthMm || template.printableLengthMm || 75,
        orientation: printerDevice ? (printerDevice.orientation.toLowerCase() as "portrait" | "landscape") : (template.orientation === "PORTRAIT" ? "portrait" : "landscape"),
        printerType: template.printerType,
      },
      printerDevice,
    });
  };

  const handlePrintAttendantPass = () => {
    if (!confirmedAdmission) return;
    const printerDevice = getPrinterForCategory("THERMAL_TOKEN");
    const html = `
      <div class="thermal-receipt" style="text-align: center; font-family: monospace; font-size: 11px;">
        <div style="font-size: 13px; font-weight: bold;">${(hospitalProfile.name || "HEALTHCARE FACILITY").toUpperCase()}</div>
        <div style="font-size: 11px; font-weight: bold; border-top: 1px dashed #000; border-bottom: 1px dashed #000; padding: 4px 0; margin: 4px 0;">
          INPATIENT ATTENDANT &amp; VISITOR PASS
        </div>
        <div style="text-align: left; margin: 6px 0; line-height: 1.4;">
          <div><b>Patient:</b> ${confirmedAdmission.patientName.toUpperCase()}</div>
          <div><b>UHID / MRN:</b> ${confirmedAdmission.mrn}</div>
          <div><b>Ward / Room:</b> ${confirmedAdmission.ward} (Bed: ${confirmedAdmission.bedNumber})</div>
          <div><b>Attendant:</b> ${(attendantName || "Primary Nominee").toUpperCase()} (${attendantRelation})</div>
          ${attendantPhone ? `<div><b>Phone:</b> ${attendantPhone}</div>` : ""}
          <div><b>Admitted:</b> ${confirmedAdmission.admittedAt}</div>
          <div><b>Doctor:</b> ${confirmedAdmission.admittingDoctor}</div>
        </div>
        <div style="background: #f1f5f9; padding: 4px; border: 1px solid #cbd5e1; margin: 6px 0; font-size: 9px; text-align: left;">
          <b>VISITING HOURS &amp; RULES:</b><br/>
          • Morning: 11:00 AM - 01:00 PM<br/>
          • Evening: 05:00 PM - 07:00 PM<br/>
          <i>Only 1 attendant permitted at bedside with this badge. Turnstile scanning required at gate.</i>
        </div>
        <div style="margin: 6px 0;">
          <div style="font-size: 16px; letter-spacing: 3px;">||| | |||| || | ||||</div>
          <div style="font-size: 9px;">*PASS-${confirmedAdmission.mrn}-${confirmedAdmission.bedNumber}*</div>
        </div>
        <div style="font-size: 8px; color: #475569; margin-top: 4px;">
          Hospital Security Gate Pass • Valid until Discharge
        </div>
      </div>
    `;
    printDocument(html, {
      title: `Attendant_Pass_${confirmedAdmission.mrn}`,
      docType: "THERMAL_TOKEN",
      printerDevice,
    });
  };

  const handlePrintDischargeSummary = () => {
    if (!lastDischargedRecord) return;
    const template = printTemplates.dischargeSummary;
    const { admission, disposition, summaryNotes, followup, dischargedAt } = lastDischargedRecord;
    const html = `
      <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 720px; margin: 0 auto; border: 1px solid #333; padding: 24px;">
        <div style="text-align: center; border-bottom: 2px solid #000; padding-bottom: 12px; margin-bottom: 16px;">
          <h2 style="margin: 0; font-size: 20px; text-transform: uppercase;">${template.hospitalHeader || hospitalProfile.name}</h2>
          <div style="font-size: 12px; font-weight: bold; color: #333; margin-top: 2px;">${template.subTitle}</div>
          <div style="font-size: 10px; color: #666;">${hospitalProfile.address} • Tel: ${hospitalProfile.phone}</div>
        </div>
        <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #ccc; padding-bottom: 8px; font-size: 12px; margin-bottom: 12px;">
          <div><b>Patient Name:</b> ${admission.patientName.toUpperCase()}</div>
          <div><b>UHID / MRN:</b> ${admission.mrn}</div>
          <div><b>Discharge Date:</b> ${dischargedAt}</div>
        </div>
        <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #ccc; padding-bottom: 8px; font-size: 12px; margin-bottom: 12px;">
          <div><b>Attending Doctor:</b> ${admission.admittingDoctor}</div>
          <div><b>Discharge Ward:</b> ${admission.ward} (Bed ${admission.bedNumber})</div>
          <div><b>Disposition:</b> ${disposition.replace(/_/g, " ")}</div>
        </div>
        <div style="margin-bottom: 14px; font-size: 12px;">
          <b>Clinical Course & Summary Notes:</b>
          <p style="background: #fafafa; border: 1px solid #eee; padding: 12px; margin-top: 6px; line-height: 1.5;">${summaryNotes}</p>
        </div>
        ${template.showMedicationReconciliation ? `
        <div style="margin-bottom: 14px; font-size: 12px;">
          <b>Discharge Medication Reconciliation:</b>
          <div style="background: #f8fafc; border: 1px solid #cbd5e1; padding: 8px 12px; margin-top: 4px; font-size: 11px;">
            <div>1. Tab. Pantoprazole 40mg OD Before Breakfast (5 Days)</div>
            <div>2. Tab. Paracetamol 650mg SOS for Fever / Body Pain</div>
            <div>3. Complete prescribed course as detailed in e-Prescription.</div>
          </div>
        </div>
        ` : ""}
        ${template.showDietaryInstructions ? `
        <div style="margin-bottom: 14px; font-size: 11px; color: #334155;">
          <b>Dietary & Lifestyle Advice:</b> Low sodium, high fiber diet. Maintain adequate hydration. Avoid strenuous physical exertion for 1 week.
        </div>
        ` : ""}
        <div style="margin-bottom: 14px; font-size: 12px;">
          <b>Outpatient Follow-Up Plan:</b>
          <div style="padding: 6px 0; color: #0284c7; font-weight: bold;">Review with ${admission.admittingDoctor} on ${followup} in OPD.</div>
        </div>
        ${template.showWarningSigns ? `
        <div style="margin-bottom: 14px; padding: 8px 12px; background: #fff1f2; border: 1px solid #fecdd3; border-radius: 4px; font-size: 11px; color: #9f1239;">
          <b>RED FLAG WARNING SIGNS:</b> Report immediately to Emergency Room (ER) if patient experiences sudden severe shortness of breath, chest pain, uncontrolled bleeding, high-grade fever (>102°F), or altered sensorium.
        </div>
        ` : ""}
        <div style="display: flex; justify-content: space-between; margin-top: 50px; font-size: 11px;">
          ${template.showDoctorSealBlock ? `<div style="border-top: 1px solid #000; width: 230px; text-align: center; padding-top: 4px;">Treating Consultant Signature & Seal</div>` : `<div></div>`}
          ${template.showSuperintendentSign ? `<div style="border-top: 1px solid #000; width: 230px; text-align: center; padding-top: 4px;">Medical Superintendent Clearance</div>` : `<div></div>`}
        </div>
        <div style="margin-top: 24px; text-align: center; font-size: 8px; color: #64748b; border-top: 1px dashed #cbd5e1; padding-top: 6px;">
          ${template.disclaimerText}
        </div>
      </div>
    `;
    printDocument(html, { title: `Discharge_Summary_${admission.mrn}`, docType: "CLINICAL_SUMMARY" });
  };

  return (
    <div className="flex-1 flex overflow-hidden bg-slate-950">
      {/* Left Column: Admission & Bed Allocation Form */}
      <div className="flex-1 flex flex-col p-6 overflow-y-auto border-r border-slate-800">
        <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-6">
          <div>
            <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
              <DoorOpen className="text-emerald-400" />
              Inpatient Admission & Bed Allocation (ADT Desk)
            </h1>
            <p className="text-xs text-slate-400 mt-0.5 font-mono">
              IPD Census • Real-Time Bed Locking • TPA Pre-Auth & MLC Police Intimation
            </p>
          </div>
        </div>

        {errorMessage && (
          <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-900/60 text-xs text-rose-300 font-mono mb-4">
            {errorMessage}
          </div>
        )}

        <form onSubmit={handleAdmissionSubmit} className="space-y-6 max-w-4xl">
          {/* Section 1: Patient Search & Auto-Population from Master Patient Index (MPI) */}
          <Card className="p-4 bg-slate-900/80 border-slate-800 space-y-3 relative">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <User size={14} className="text-sky-400" /> 1. Patient Identification & MPI Autocomplete
              </span>
              <div className="flex items-center gap-2">
                {patientSummary && (
                  <button
                    type="button"
                    onClick={() => {
                      const match = MASTER_PATIENT_DIRECTORY.find((p) => p.mrn === patientSummary.mrn);
                      if (match) handleSelectPatient(match);
                      else {
                        setTargetPatientName(patientSummary.full_name);
                        setTargetMrn(patientSummary.mrn);
                      }
                    }}
                    className="text-[10px] font-mono bg-sky-500/20 text-sky-400 border border-sky-500/40 px-2 py-0.5 rounded hover:bg-sky-500/30 flex items-center gap-1"
                  >
                    <Sparkles size={10} /> Active Patient: {patientSummary.full_name}
                  </button>
                )}
                <span className="text-[11px] font-mono text-emerald-400">Enterprise MPI Linked</span>
              </div>
            </div>

            {/* Live Autocomplete Search Input */}
            <div className="relative">
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Search Master Patient Index (by Name, MRN / UHID, Mobile, or Diagnosis)
              </label>
              <div className="relative">
                <Search size={14} className="absolute left-3 top-2.5 text-slate-400" />
                <input
                  type="text"
                  placeholder="Type to search (e.g., 'Siddharth', '0002', 'Dengue', '9876')..."
                  value={patientSearchQuery}
                  onFocus={() => setIsPatientDropdownOpen(true)}
                  onChange={(e) => {
                    setPatientSearchQuery(e.target.value);
                    setIsPatientDropdownOpen(true);
                  }}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500 font-mono"
                />
              </div>

              {/* Autocomplete Dropdown */}
              {isPatientDropdownOpen && (
                <div className="absolute left-0 right-0 top-full mt-1 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl z-50 max-h-64 overflow-y-auto">
                  <div className="p-2 border-b border-slate-800 text-[10px] font-mono text-slate-400 uppercase tracking-wider flex justify-between">
                    <span>Matching MPI Patient Records</span>
                    <button
                      type="button"
                      onClick={() => setIsPatientDropdownOpen(false)}
                      className="text-slate-400 hover:text-white"
                    >
                      Close ✕
                    </button>
                  </div>
                  {/* Live Backend MPI Search Results */}
                  {isSearchingMpi && (
                    <div className="p-3 text-center text-xs text-sky-400 font-mono flex items-center justify-center gap-2">
                      <Sparkles size={13} className="animate-spin" /> Querying Master Patient Index...
                    </div>
                  )}

                  {mpiSearchResults.map((mpi) => (
                    <div
                      key={`mpi-${mpi.id}`}
                      onClick={() => handleSelectMpiPatient(mpi)}
                      className="p-3 hover:bg-slate-800/80 cursor-pointer border-b border-slate-800/50 last:border-0 transition-colors bg-sky-950/20"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-bold text-xs text-slate-100 flex items-center gap-1.5">
                          {mpi.full_name}
                          <span className="font-mono text-[10px] font-normal text-slate-400">
                            ({mpi.age_years || "--"}y • {mpi.gender})
                          </span>
                        </span>
                        <span className="font-mono text-[10px] text-emerald-400 bg-emerald-950 px-1.5 py-0.5 rounded border border-emerald-800">
                          {mpi.mrn}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono mt-1 pt-1 border-t border-slate-800/40">
                        <span>Blood: {mpi.blood_group || "O+"} • Ph: {mpi.phone_number || "--"}</span>
                        <span className="text-sky-400 font-semibold">Live Enterprise MPI</span>
                      </div>
                    </div>
                  ))}

                  {/* Seeded Directory Records */}
                  {MASTER_PATIENT_DIRECTORY.filter((p) => {
                    if (!patientSearchQuery.trim()) return true;
                    const q = patientSearchQuery.toLowerCase();
                    return (
                      p.name.toLowerCase().includes(q) ||
                      p.mrn.toLowerCase().includes(q) ||
                      p.phone.includes(q) ||
                      p.activeDiagnosis.toLowerCase().includes(q)
                    );
                  }).map((p) => (
                    <div
                      key={p.id}
                      onClick={() => handleSelectPatient(p)}
                      className="p-3 hover:bg-slate-800/80 cursor-pointer border-b border-slate-800/50 last:border-0 transition-colors"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-bold text-xs text-slate-100 flex items-center gap-1.5">
                          {p.name}
                          <span className="font-mono text-[10px] font-normal text-slate-400">
                            ({p.age}y • {p.gender})
                          </span>
                        </span>
                        <span className="font-mono text-[10px] text-sky-400 bg-sky-950 px-1.5 py-0.5 rounded border border-sky-800">
                          {p.mrn}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-300 line-clamp-1">{p.activeDiagnosis}</div>
                      <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono mt-1 pt-1 border-t border-slate-800/40">
                        <span>Blood: {p.bloodGroup} • TPA: {p.insurancePayer}</span>
                        <span className="text-emerald-400">Auth: ₹{p.insurancePreAuth.toLocaleString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Resolved Active Patient Demographics Card */}
            {selectedPatientRecord && (
              <div className="p-3 rounded-xl bg-slate-950 border border-emerald-900/50 text-xs space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 size={15} className="text-emerald-400" />
                    <span className="font-bold text-slate-100">{selectedPatientRecord.name}</span>
                    <span className="font-mono text-[10px] text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/60">
                      {selectedPatientRecord.mrn}
                    </span>
                  </div>
                  <span className="text-[11px] font-mono text-slate-400">
                    {selectedPatientRecord.gender} • {selectedPatientRecord.age} Years • Blood: {selectedPatientRecord.bloodGroup}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div>
                    <span className="text-slate-500 block">Primary Diagnosis / Indication:</span>
                    <span className="text-slate-300 font-medium">{selectedPatientRecord.activeDiagnosis}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">TPA Pre-Authorization Status:</span>
                    <span className="text-emerald-400 font-semibold font-mono">
                      {selectedPatientRecord.insurancePayer} (Sanctioned: ₹{selectedPatientRecord.insurancePreAuth.toLocaleString()})
                    </span>
                  </div>
                </div>

                {selectedPatientRecord.allergies.length > 0 && (
                  <div className="text-[10px] text-rose-300 font-mono flex items-center gap-1.5 pt-1 border-t border-slate-900">
                    <ShieldAlert size={12} className="text-rose-400" />
                    <span>Documented Allergies: {selectedPatientRecord.allergies.join(", ")}</span>
                  </div>
                )}
              </div>
            )}
          </Card>

          {/* Section 2: Clinical Admission Parameters */}
          <Card className="p-4 bg-slate-900/80 border-slate-800 space-y-4">
            <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <Activity size={14} className="text-emerald-400" /> 2. Admission Parameters & Admitting Consultant
            </h2>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Admission Type</label>
                <select
                  value={admissionType}
                  onChange={(e) => setAdmissionType(e.target.value as any)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 focus:outline-none focus:border-emerald-500 font-semibold"
                >
                  <option value="ELECTIVE">Elective / Planned Admission</option>
                  <option value="EMERGENCY">Emergency / Acute Resuscitation</option>
                  <option value="DAYCARE">Day Care (Chemotherapy / Dialysis / Endoscopy)</option>
                  <option value="MATERNITY">Maternity / Labor & Delivery</option>
                  <option value="ICU_TRANSFER">Direct ICU Step-In Transfer</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Admitting Attending Doctor</label>
                <select
                  value={admittingDoctor}
                  onChange={(e) => setAdmittingDoctor(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
                >
                  <option value="Dr. Vikram Seth (Cardiology)">Dr. Vikram Seth (Cardiology)</option>
                  <option value="Dr. Radhika Sen (General Surgery)">Dr. Radhika Sen (General Surgery)</option>
                  <option value="Dr. Sameer Joshi (Critical Care / ICU)">Dr. Sameer Joshi (Critical Care / ICU)</option>
                  <option value="Dr. Anjali Nair (Obstetrics & Gynecology)">Dr. Anjali Nair (OB/GYN)</option>
                  <option value="Dr. Harish Patel (Orthopedics)">Dr. Harish Patel (Orthopedics)</option>
                  <option value="Dr. Rajesh Sharma (General Medicine)">Dr. Rajesh Sharma (General Medicine)</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Provisional Admission Diagnosis</label>
              <input
                type="text"
                required
                value={admissionDiagnosis}
                onChange={(e) => setAdmissionDiagnosis(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
              />
            </div>
          </Card>

          {/* Section 3: Hierarchical 500+ Bed Scale Campus Matrix */}
          <Card className="p-4 bg-slate-900/80 border-slate-800 space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <div>
                <h2 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                  <BedDouble size={14} className="text-sky-400" /> 3. Campus Bed Matrix & Allocation (500+ Beds Scale)
                </h2>
                <div className="text-[10px] text-slate-400 mt-0.5">
                  Real-time bed availability across 4 towers, 5 clinical floors, and multiple specialty wards.
                </div>
              </div>

              {/* View Mode Toggle */}
              <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
                <button
                  type="button"
                  onClick={() => setBedViewMode("GRID")}
                  className={`px-2.5 py-1 rounded text-xs flex items-center gap-1 font-semibold transition-all ${
                    bedViewMode === "GRID"
                      ? "bg-sky-500/20 text-sky-400 border border-sky-500/40"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  <LayoutGrid size={12} /> Floorplan Grid
                </button>
                <button
                  type="button"
                  onClick={() => setBedViewMode("TABLE")}
                  className={`px-2.5 py-1 rounded text-xs flex items-center gap-1 font-semibold transition-all ${
                    bedViewMode === "TABLE"
                      ? "bg-sky-500/20 text-sky-400 border border-sky-500/40"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  <TableIcon size={12} /> Census Table
                </button>
              </div>
            </div>

            {/* Tower Selection Pills */}
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-slate-400 flex items-center gap-1 w-16">
                  <Building size={12} /> Tower:
                </span>
                <div className="flex flex-wrap gap-1.5">
                  <button
                    type="button"
                    onClick={() => { setSelectedTower("ALL"); setBedPage(1); }}
                    className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold transition-all ${
                      selectedTower === "ALL"
                        ? "bg-sky-600 text-white shadow-sm"
                        : "bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800"
                    }`}
                  >
                    All Towers ({ENTERPRISE_BED_POOL.length} Beds)
                  </button>
                  {campusTowers.map((towerName) => {
                    const towerBeds = ENTERPRISE_BED_POOL.filter((b) => b.tower === towerName);
                    const occ = towerBeds.filter((b) => b.status === "OCCUPIED").length;
                    const pct = towerBeds.length > 0 ? Math.round((occ / towerBeds.length) * 100) : 0;
                    return (
                      <button
                        key={towerName}
                        type="button"
                        onClick={() => { setSelectedTower(towerName); setBedPage(1); }}
                        className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold transition-all ${
                          selectedTower === towerName
                            ? "bg-sky-600 text-white shadow-sm"
                            : "bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800"
                        }`}
                      >
                        {towerName} ({towerBeds.length} • {pct}% Occ)
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Floor Selection */}
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-slate-400 flex items-center gap-1 w-16">
                  <Layers size={12} /> Floor:
                </span>
                <div className="flex flex-wrap gap-1.5">
                  <button
                    type="button"
                    onClick={() => { setSelectedFloor("ALL"); setBedPage(1); }}
                    className={`px-2 py-0.5 rounded text-[10px] font-mono transition-all ${
                      selectedFloor === "ALL"
                        ? "bg-sky-500/20 text-sky-300 border border-sky-500/50 font-bold"
                        : "bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800"
                    }`}
                  >
                    ALL
                  </button>
                  {campusFloors.map((fl) => (
                    <button
                      key={fl}
                      type="button"
                      onClick={() => { setSelectedFloor(fl); setBedPage(1); }}
                      className={`px-2 py-0.5 rounded text-[10px] font-mono transition-all ${
                        selectedFloor === fl
                          ? "bg-sky-500/20 text-sky-300 border border-sky-500/50 font-bold"
                          : "bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800"
                      }`}
                    >
                      {fl}
                    </button>
                  ))}
                </div>
              </div>

              {/* Status & Category Filters */}
              <div className="grid grid-cols-2 gap-3 pt-1">
                {/* Status Filter */}
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] font-mono text-slate-400 uppercase">Status:</span>
                  <div className="flex gap-1">
                    {[
                      { id: "ALL", label: "All" },
                      { id: "VACANT_CLEAN", label: `🟢 Vacant (${vacantBedsCount})` },
                      { id: "OCCUPIED", label: `🔴 Occupied (${occupiedBedsCount})` },
                      { id: "HOUSEKEEPING", label: `🟡 Clean (${housekeepingBedsCount})` },
                      { id: "RESERVED", label: `🟣 Res (${reservedBedsCount})` },
                    ].map((s) => (
                      <button
                        key={s.id}
                        type="button"
                        onClick={() => setSelectedStatus(s.id)}
                        className={`px-2 py-0.5 rounded text-[10px] font-semibold transition-all ${
                          selectedStatus === s.id
                            ? "bg-slate-800 text-white border border-slate-600"
                            : "bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800"
                        }`}
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Bed Category Filter */}
                <div className="flex items-center gap-1.5 justify-end">
                  <span className="text-[10px] font-mono text-slate-400 uppercase">Category:</span>
                  <div className="flex gap-1">
                    {(["ALL", "General", "Semi-Private", "Private", "ICU"] as const).map((cat) => (
                      <button
                        key={cat}
                        type="button"
                        onClick={() => setBedCategoryFilter(cat)}
                        className={`px-2 py-0.5 rounded text-[10px] font-semibold transition-all ${
                          bedCategoryFilter === cat
                            ? "bg-sky-500/20 text-sky-400 border border-sky-500/40"
                            : "bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800"
                        }`}
                      >
                        {cat}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Search & Equipment Sub-Filter Bar */}
              <div className="flex items-center gap-3 pt-1">
                <div className="flex-1 relative">
                  <Search size={12} className="absolute left-2.5 top-2 text-slate-500" />
                  <input
                    type="text"
                    placeholder="Search bed # (e.g. 'ICU-401', 'B-201'), room, ward, or patient..."
                    value={bedSearchQuery}
                    onChange={(e) => setBedSearchQuery(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-sky-500"
                  />
                </div>

                <div className="flex items-center gap-1 text-[11px] font-mono text-slate-400">
                  <Filter size={12} />
                  <select
                    value={selectedEquipment}
                    onChange={(e) => setSelectedEquipment(e.target.value)}
                    className="bg-slate-950 border border-slate-800 rounded-lg px-2 py-1.5 text-xs text-slate-200"
                  >
                    <option value="ALL">All Clinical Capabilities</option>
                    <option value="Ventilator">Ventilator Ready</option>
                    <option value="Cardiac">Cardiac Telemetry</option>
                    <option value="O2">O2 Wall Outlet</option>
                    <option value="Dialysis">Dialysis Port</option>
                    <option value="Isolation">Negative Pressure Isolation</option>
                  </select>
                </div>
              </div>
            </div>

            {/* View Mode 1: Visual Floorplan Grid */}
            {bedViewMode === "GRID" && (
              <div className="grid grid-cols-3 gap-3 pt-2 max-h-96 overflow-y-auto pr-1">
                {filteredBeds.length === 0 ? (
                  <div className="col-span-3 py-10 text-center text-slate-500 text-xs font-mono">
                    No beds matching the selected filter criteria.
                  </div>
                ) : (
                  paginatedBeds.map((bed) => {
                    const isSelected = selectedBedId === bed.bedId;
                    const isVacant = bed.status === "VACANT_CLEAN";
                    return (
                      <div
                        key={bed.bedId}
                        onClick={() => {
                          if (isVacant) setSelectedBedId(bed.bedId);
                        }}
                        className={`p-3 rounded-xl border transition-all ${
                          isVacant
                            ? isSelected
                              ? "bg-sky-950/70 border-sky-400 ring-2 ring-sky-500/50 shadow-lg cursor-pointer"
                              : "bg-slate-950 border-emerald-900/60 hover:border-emerald-500/80 cursor-pointer"
                            : "bg-slate-950/50 border-slate-800/80 opacity-70 cursor-not-allowed"
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-1.5">
                            <span
                              className={`w-2 h-2 rounded-full ${
                                bed.status === "VACANT_CLEAN"
                                  ? "bg-emerald-400 animate-pulse"
                                  : bed.status === "OCCUPIED"
                                  ? "bg-rose-500"
                                  : bed.status === "HOUSEKEEPING"
                                  ? "bg-amber-400"
                                  : "bg-purple-400"
                              }`}
                            />
                            <span className="font-bold text-xs text-slate-100 font-mono">{bed.bedNumber}</span>
                          </div>

                          <div className="flex items-center gap-1">
                            <Badge variant={bed.category === "ICU" ? "danger" : "info"} size="sm">
                              {bed.category}
                            </Badge>
                          </div>
                        </div>

                        <div className="text-[11px] text-slate-300 font-medium">{bed.wardName}</div>
                        <div className="text-[10px] text-slate-400 font-mono">
                          {bed.tower} • {bed.floor} • Room {bed.roomNumber}
                        </div>

                        {bed.occupiedBy ? (
                          <div className="mt-2 p-1.5 rounded bg-rose-950/40 border border-rose-900/50 text-[10px] text-rose-300">
                            Occupied: {bed.occupiedBy.patientName} ({bed.occupiedBy.mrn}) • Day {bed.occupiedBy.admittedDays}
                          </div>
                        ) : (
                          <div className="flex flex-wrap gap-1 mt-2">
                            {bed.features.map((f, i) => (
                              <span
                                key={i}
                                className="px-1.5 py-0.5 rounded text-[9px] bg-slate-900 text-slate-300 border border-slate-800 font-mono"
                              >
                                {f}
                              </span>
                            ))}
                          </div>
                        )}

                        <div className="mt-2 pt-1.5 border-t border-slate-800 flex justify-between items-center text-[10px] font-mono">
                          <span className="text-slate-400">Tariff:</span>
                          <span className="text-emerald-400 font-bold">₹{bed.dailyTariffRupees.toLocaleString()}/day</span>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            )}

            {/* View Mode 2: High-Density Census Table */}
            {bedViewMode === "TABLE" && (
              <div className="max-h-96 overflow-y-auto border border-slate-800 rounded-lg">
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-slate-900 text-slate-400 text-[10px] uppercase sticky top-0">
                    <tr>
                      <th className="p-2.5">Bed / Room</th>
                      <th className="p-2.5">Tower & Floor</th>
                      <th className="p-2.5">Ward / Specialty</th>
                      <th className="p-2.5">Category</th>
                      <th className="p-2.5">Equipment</th>
                      <th className="p-2.5">Daily Tariff</th>
                      <th className="p-2.5">Status</th>
                      <th className="p-2.5 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/80 text-slate-300">
                    {paginatedBeds.map((bed) => {
                      const isVacant = bed.status === "VACANT_CLEAN";
                      const isSelected = selectedBedId === bed.bedId;
                      return (
                        <tr
                          key={bed.bedId}
                          className={`hover:bg-slate-900/60 transition-colors ${
                            isSelected ? "bg-sky-950/40" : ""
                          }`}
                        >
                          <td className="p-2.5 font-bold text-slate-100">
                            {bed.bedNumber} ({bed.roomNumber})
                          </td>
                          <td className="p-2.5 text-[11px] text-slate-400">
                            {bed.tower} • {bed.floor}
                          </td>
                          <td className="p-2.5 text-[11px] text-slate-300">{bed.wardName}</td>
                          <td className="p-2.5">
                            <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-900 border border-slate-800 text-sky-400">
                              {bed.category}
                            </span>
                          </td>
                          <td className="p-2.5 text-[10px] text-slate-400 max-w-xs truncate">
                            {bed.features.join(", ")}
                          </td>
                          <td className="p-2.5 font-bold text-emerald-400">
                            ₹{bed.dailyTariffRupees.toLocaleString()}
                          </td>
                          <td className="p-2.5">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                                isVacant
                                  ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                                  : bed.status === "OCCUPIED"
                                  ? "bg-rose-950 text-rose-300 border border-rose-900"
                                  : "bg-amber-950 text-amber-300 border border-amber-900"
                              }`}
                            >
                              {bed.status}
                            </span>
                          </td>
                          <td className="p-2.5 text-right">
                            {isVacant ? (
                              <Button
                                size="sm"
                                variant={isSelected ? "primary" : "outline"}
                                onClick={() => setSelectedBedId(bed.bedId)}
                                className="text-[11px] py-1 px-2.5"
                              >
                                {isSelected ? "Selected ✓" : "Allocate Bed"}
                              </Button>
                            ) : (
                              <span className="text-[10px] text-slate-500">Unavailable</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* 500+ Bed Scale Pagination & Census Barometer */}
            <div className="flex items-center justify-between pt-2 border-t border-slate-800 text-xs font-mono">
              <div className="flex items-center gap-2 text-slate-400">
                <span>Showing {filteredBeds.length === 0 ? 0 : (bedPage - 1) * bedPageSize + 1}–{Math.min(bedPage * bedPageSize, filteredBeds.length)} of {filteredBeds.length} Beds</span>
                <span className="text-slate-600">|</span>
                <span>Page Size:</span>
                {[36, 72, 144].map((size) => (
                  <button
                    key={size}
                    type="button"
                    onClick={() => { setBedPageSize(size); setBedPage(1); }}
                    className={`px-1.5 py-0.5 rounded ${
                      bedPageSize === size
                        ? "bg-sky-500/20 text-sky-400 font-bold border border-sky-500/50"
                        : "text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    {size}
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-2">
                <span className="text-slate-400">
                  Page {bedPage} of {totalBedPages}
                </span>
                <button
                  type="button"
                  disabled={bedPage <= 1}
                  onClick={() => setBedPage((p) => Math.max(1, p - 1))}
                  className="p-1 rounded bg-slate-900 border border-slate-800 text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-800"
                >
                  <ChevronLeft size={14} />
                </button>
                <button
                  type="button"
                  disabled={bedPage >= totalBedPages}
                  onClick={() => setBedPage((p) => Math.min(totalBedPages, p + 1))}
                  className="p-1 rounded bg-slate-900 border border-slate-800 text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-800"
                >
                  <ChevronRight size={14} />
                </button>
              </div>
            </div>
          </Card>

          {/* Medico-Legal Case (MLC) Intimation */}
          <Card className="p-4 bg-slate-900/80 border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="mlc-intake"
                  checked={isMlc}
                  onChange={(e) => setIsMlc(e.target.checked)}
                  className="rounded bg-slate-900 border-slate-700 text-rose-500 focus:ring-rose-500 h-4 w-4"
                />
                <label htmlFor="mlc-intake" className="text-xs font-bold text-rose-400 cursor-pointer flex items-center gap-1.5">
                  <ShieldAlert size={14} /> Tag as Medico-Legal Case (MLC) • RTA / Assault / Poisoning
                </label>
              </div>
              {isMlc && <Badge variant="danger" size="sm">Police Notification Mandatory</Badge>}
            </div>

            {isMlc && (
              <div className="grid grid-cols-2 gap-4 pt-2 border-t border-slate-800">
                <div>
                  <label className="block text-[11px] text-slate-300 mb-1">Police Station Jurisdiction</label>
                  <input
                    type="text"
                    required={isMlc}
                    placeholder="e.g. Banjara Hills PS"
                    value={policeStation}
                    onChange={(e) => setPoliceStation(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                  />
                </div>
                <div>
                  <label className="block text-[11px] text-slate-300 mb-1">MLC / General Diary (GD) #</label>
                  <input
                    type="text"
                    required={isMlc}
                    placeholder="e.g. MLC-2026-0811"
                    value={mlcNumber}
                    onChange={(e) => setMlcNumber(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                  />
                </div>
              </div>
            )}
          </Card>

          {/* TPA Insurance Pre-Authorization */}
          <Card className="p-4 bg-slate-900/80 border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="ins-intake"
                  checked={hasInsurance}
                  onChange={(e) => setHasInsurance(e.target.checked)}
                  className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-sky-500 h-4 w-4"
                />
                <label htmlFor="ins-intake" className="text-xs font-bold text-sky-400 cursor-pointer flex items-center gap-1.5">
                  <CreditCard size={14} /> Third-Party Administrator (TPA) / Cashless Insurance
                </label>
              </div>
            </div>

            {hasInsurance && (
              <div className="grid grid-cols-2 gap-4 pt-2 border-t border-slate-800">
                <div>
                  <label className="block text-[11px] text-slate-300 mb-1">Insurance Carrier / TPA</label>
                  <input
                    type="text"
                    value={payerName}
                    onChange={(e) => setPayerName(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                  />
                </div>
                <div>
                  <label className="block text-[11px] text-slate-300 mb-1">Pre-Authorized Amount (₹)</label>
                  <input
                    type="number"
                    value={preAuthAmount}
                    onChange={(e) => setPreAuthAmount(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                  />
                </div>
              </div>
            )}
          </Card>

          {/* Attendant & Security Visitor Pass Details */}
          <Card className="p-4 bg-slate-900/80 border-slate-800 space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <span className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                <User size={14} className="text-purple-400" /> Bedside Attendant &amp; Security Pass Allocation
              </span>
              <span className="text-[10px] font-mono text-purple-400">1 Primary Pass Allowed</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="block text-[11px] text-slate-300 mb-1">Attendant Full Name</label>
                <input
                  type="text"
                  placeholder="e.g. Ramesh Varma"
                  value={attendantName}
                  onChange={(e) => setAttendantName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 placeholder:text-slate-600"
                />
              </div>
              <div>
                <label className="block text-[11px] text-slate-300 mb-1">Relationship to Patient</label>
                <select
                  value={attendantRelation}
                  onChange={(e) => setAttendantRelation(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                >
                  <option value="Spouse">Spouse</option>
                  <option value="Parent">Parent / Guardian</option>
                  <option value="Child / Son / Daughter">Child (Son / Daughter)</option>
                  <option value="Sibling">Sibling (Brother / Sister)</option>
                  <option value="Other Relative">Other Relative / Nominee</option>
                </select>
              </div>
              <div>
                <label className="block text-[11px] text-slate-300 mb-1">Attendant Phone / Contact</label>
                <input
                  type="tel"
                  placeholder="10-digit mobile number"
                  value={attendantPhone}
                  onChange={(e) => setAttendantPhone(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 placeholder:text-slate-600 font-mono"
                />
              </div>
            </div>
          </Card>

          <div className="flex items-center justify-end gap-3 pt-2">
            <PermissionGate
              permission="bed.allocate"
              fallback={
                <div className="p-3 rounded-lg bg-amber-950/40 border border-amber-800/60 text-xs text-amber-300 font-mono">
                  🔒 Action Locked: Your current staff role does not possess &apos;bed.allocate&apos; authorization.
                </div>
              }
            >
              <Button
                type="submit"
                variant="primary"
                size="lg"
                className="flex items-center gap-2 font-bold px-6"
              >
                <DoorOpen size={16} /> Confirm Admission & Lock Bed
              </Button>
            </PermissionGate>
          </div>
        </form>
      </div>

      {/* Right Column: Live Inpatient Census & Action Bar */}
      <div className="w-96 flex flex-col bg-slate-900/40 p-4 border-l border-slate-800 overflow-hidden">
        <div className="mb-4">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
              Current Inpatient Census ({admissions.length})
            </h2>
            <Badge variant="success" size="sm">Occupied</Badge>
          </div>
          <p className="text-[11px] text-slate-500 font-mono">Live active admissions on floor</p>
        </div>

        <div className="flex-1 overflow-y-auto space-y-3 pr-1">
          {admissions.map((adm) => (
            <Card key={adm.id} className="p-3 bg-slate-900 border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-semibold text-xs text-slate-100">{adm.patientName}</span>
                  <div className="text-[10px] text-slate-400 font-mono">{adm.mrn}</div>
                </div>
                <div className="text-right">
                  <span className="font-mono text-xs font-bold text-sky-400">{adm.bedNumber}</span>
                  <div className="text-[10px] text-slate-500 font-mono">{adm.roomNumber}</div>
                </div>
              </div>

              <div className="text-[11px] text-slate-400">{adm.ward}</div>
              <div className="text-[10px] text-slate-500">{adm.admittingDoctor}</div>

              {adm.tpaInsurance && (
                <div className="text-[10px] text-sky-400 font-mono bg-sky-950/40 p-1 rounded border border-sky-900/60">
                  {adm.tpaInsurance}
                </div>
              )}

              {/* Discharge Readiness Checklist */}
              <div className="pt-2 border-t border-slate-800/80 space-y-1">
                <div className="text-[10px] uppercase text-slate-500 font-mono flex items-center justify-between">
                  <span>Discharge Readiness (EDD: {adm.edd})</span>
                </div>
                <div className="grid grid-cols-2 gap-1 text-[10px] font-mono">
                  <span
                    className={`px-1.5 py-0.5 rounded text-center border ${
                      adm.clearances?.clinicalSummary
                        ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/60"
                        : "bg-slate-950 text-slate-500 border-slate-800"
                    }`}
                  >
                    {adm.clearances?.clinicalSummary ? "✓ Summary Signed" : "○ Summary Due"}
                  </span>
                  <span
                    className={`px-1.5 py-0.5 rounded text-center border ${
                      adm.clearances?.pharmacyCleared
                        ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/60"
                        : "bg-slate-950 text-slate-500 border-slate-800"
                    }`}
                  >
                    {adm.clearances?.pharmacyCleared ? "✓ Pharmacy Clr" : "○ Pharmacy Due"}
                  </span>
                  <span
                    className={`px-1.5 py-0.5 rounded text-center border ${
                      adm.clearances?.tpaApproved
                        ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/60"
                        : "bg-slate-950 text-slate-500 border-slate-800"
                    }`}
                  >
                    {adm.clearances?.tpaApproved ? "✓ TPA Pre-Auth" : "○ TPA Query"}
                  </span>
                  <span
                    className={`px-1.5 py-0.5 rounded text-center border ${
                      adm.clearances?.cashierSettled
                        ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/60"
                        : "bg-amber-950/60 text-amber-400 border-amber-800/60"
                    }`}
                  >
                    {adm.clearances?.cashierSettled ? "✓ Bill Settled" : "⏳ Bill Pending"}
                  </span>
                </div>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-slate-800">
                <div className="flex items-center gap-1">
                  <Badge variant="neutral" size="sm" className="text-[9px]">
                    {adm.admissionType}
                  </Badge>
                  {adm.isMlc && (
                    <Badge variant="danger" size="sm" className="text-[9px]">
                      MLC
                    </Badge>
                  )}
                </div>

                <div className="flex items-center gap-1.5">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleOpenTransfer(adm)}
                    className="text-[10px] py-0.5 px-2 text-sky-400 hover:bg-sky-950 flex items-center gap-1"
                  >
                    <ArrowRightLeft size={10} /> Transfer
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleOpenDischarge(adm)}
                    className="text-[10px] py-0.5 px-2 text-rose-400 hover:bg-rose-950 flex items-center gap-1"
                  >
                    <LogOut size={10} /> Discharge
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>

      {/* Modal: Bed Transfer */}
      {transferringAdmission && (
        <Modal
          isOpen={isTransferModalOpen}
          onClose={() => setIsTransferModalOpen(false)}
          title={`Bed Transfer Desk — ${transferringAdmission.patientName} (${transferringAdmission.bedNumber})`}
        >
          <form onSubmit={handleExecuteTransfer} className="space-y-4">
            <div className="p-3 rounded-lg bg-sky-950/30 border border-sky-900/60 text-xs text-sky-300 font-mono">
              Current Bed: {transferringAdmission.bedNumber} ({transferringAdmission.roomNumber} - {transferringAdmission.ward})
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Destination Available Bed</label>
              <select
                value={transferDestinationBedId}
                onChange={(e) => setTransferDestinationBedId(parseInt(e.target.value, 10))}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200"
              >
                {ENTERPRISE_BED_POOL
                  .filter((b) => b.status === "VACANT_CLEAN" && b.bedNumber !== transferringAdmission.bedNumber)
                  .map((b) => (
                    <option key={b.bedId} value={b.bedId}>
                      {b.bedNumber} — {b.roomNumber} ({b.wardName} - {b.category} • ₹{b.dailyTariffRupees}/day)
                    </option>
                  ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Reason for Bed Transfer</label>
              <select
                value={transferReason}
                onChange={(e) => setTransferReason(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 mb-2"
              >
                <option value="Clinical step-down / condition stable">Clinical step-down (ICU to Ward) / Condition stable</option>
                <option value="Clinical escalation / requires ICU hemodynamic monitoring">Clinical escalation / Requires ICU monitoring</option>
                <option value="Patient / Attendant request for room upgrade (Private Deluxe)">Attendant request for room upgrade (Private Deluxe)</option>
                <option value="Infection control isolation requirement">Infection control isolation requirement</option>
                <option value="Terminal sanitization of previous room">Terminal sanitization of previous room</option>
              </select>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
              <Button type="button" variant="outline" size="sm" onClick={() => setIsTransferModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" size="sm" className="flex items-center gap-1.5">
                <ArrowRightLeft size={12} /> Confirm Bed Transfer
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* Modal: Clinical Discharge Entry */}
      {dischargingAdmission && (
        <Modal
          isOpen={isDischargeModalOpen}
          onClose={() => setIsDischargeModalOpen(false)}
          title={`Clinical Discharge Order — ${dischargingAdmission.patientName} (${dischargingAdmission.mrn})`}
        >
          <form onSubmit={handleExecuteDischarge} className="space-y-4">
            <div className="p-3 rounded-lg bg-amber-950/30 border border-amber-900/60 text-xs text-amber-300 font-mono">
              Terminal Discharge: Releases bed {dischargingAdmission.bedNumber} to Housekeeping sanitization queue.
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Discharge Disposition</label>
              <select
                value={dischargeDisposition}
                onChange={(e) => setDischargeDisposition(e.target.value as any)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 font-semibold"
              >
                <option value="ROUTINE_DISCHARGE">Routine Medical Discharge (Condition Improved / Stable)</option>
                <option value="REFERRED_OUT">Referred Out to Tertiary Super-Specialty Center</option>
                <option value="AGAINST_MEDICAL_ADVICE">Left Against Medical Advice (LAMA / DAMA)</option>
                <option value="DECEASED">Deceased / Clinical Death Intimation</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Discharge Summary & Medical Advice</label>
              <textarea
                rows={3}
                required
                value={dischargeSummaryNotes}
                onChange={(e) => setDischargeSummaryNotes(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Scheduled OPD Follow-up Date</label>
              <input
                type="date"
                value={followupDate}
                onChange={(e) => setFollowupDate(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 font-mono"
              />
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
              <Button type="button" variant="outline" size="sm" onClick={() => setIsDischargeModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="danger" size="sm" className="flex items-center gap-1.5">
                <LogOut size={12} /> Confirm & Authorize Discharge
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* Modal: Printable Formal Discharge Summary (ISOLATED PRINT AREA) */}
      {lastDischargedRecord && (
        <Modal
          isOpen={isDischargeSummaryOpen}
          onClose={() => setIsDischargeSummaryOpen(false)}
          title="Clinical Discharge Summary Slip"
        >
          <div className="space-y-4">
            <div className="print-area p-6 rounded-xl bg-white text-slate-900 border border-slate-300 font-sans text-xs space-y-3 shadow-sm">
              {/* Letterhead */}
              <div className="text-center border-b border-slate-300 pb-2.5">
                <div className="font-bold text-sm tracking-wide text-slate-900 uppercase">
                  {hospitalProfile.name}
                </div>
                <div className="text-[10px] text-slate-600 font-mono">
                  Clinical Discharge Summary & Post-Hospitalization Care Plan
                </div>
                <div className="text-[9px] text-slate-500">
                  {hospitalProfile.accreditation} • {hospitalProfile.address}
                </div>
              </div>

              {/* Document Reference Header */}
              <div className="flex items-center justify-between border-b border-slate-200 pb-2 font-mono">
                <div>
                  <span className="text-slate-500 text-[10px] uppercase block">Discharge Reference</span>
                  <span className="font-bold text-slate-900">DISCHARGE #{lastDischargedRecord.admission.id}</span>
                </div>
                <div className="text-right">
                  <span className="text-slate-500 text-[10px] uppercase block">Discharge Disposition</span>
                  <span className="font-bold text-sky-800 bg-sky-50 px-2 py-0.5 rounded border border-sky-300">
                    {lastDischargedRecord.disposition}
                  </span>
                </div>
              </div>

              {/* Patient Core Grid */}
              <div className="grid grid-cols-2 gap-2 bg-slate-50 p-2.5 rounded border border-slate-200">
                <div>
                  <span className="text-slate-500 text-[10px] block font-mono">Patient Name</span>
                  <span className="text-slate-900 font-bold">{lastDischargedRecord.admission.patientName}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] block font-mono">UHID / MRN</span>
                  <span className="text-slate-900 font-bold">{lastDischargedRecord.admission.mrn}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] block font-mono">Inpatient Ward & Bed</span>
                  <span className="text-slate-800">
                    {lastDischargedRecord.admission.ward} ({lastDischargedRecord.admission.bedNumber})
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] block font-mono">Discharge Timestamp</span>
                  <span className="text-slate-800 font-mono">{lastDischargedRecord.dischargedAt}</span>
                </div>
              </div>

              {/* Clinical Course */}
              <div className="pt-2 border-t border-slate-200">
                <span className="text-slate-700 font-bold text-[11px] uppercase block mb-1">
                  Hospital Course & Medical Advice on Discharge
                </span>
                <p className="text-slate-800 bg-slate-50 p-3 rounded border border-slate-200 text-[11px] leading-relaxed">
                  {lastDischargedRecord.summaryNotes}
                </p>
              </div>

              {/* Follow-up instructions */}
              <div className="flex items-center justify-between p-2.5 rounded bg-emerald-50 border border-emerald-200">
                <span className="text-emerald-900 font-semibold text-[11px]">Next OPD Review Appointment:</span>
                <span className="text-emerald-800 font-bold font-mono">{lastDischargedRecord.followup}</span>
              </div>

              {/* Physician Signature Line */}
              <div className="pt-6 flex justify-between items-end border-t border-slate-300 text-[10px] font-mono">
                <div>
                  <div>Nursing Station Clearance: Completed ✓</div>
                  <div>Pharmacy Clearance: Settled ✓</div>
                </div>
                <div className="text-right">
                  <div className="border-b border-slate-400 w-44 pb-1 mb-1"></div>
                  <div className="font-bold text-slate-800">{lastDischargedRecord.admission.admittingDoctor}</div>
                  <div className="text-slate-500">Authorized Treating Consultant</div>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handlePrintDischargeSummary}
                className="flex items-center gap-1.5"
              >
                <Printer size={13} className="text-sky-400" /> Print Formal Discharge Summary
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => setIsDischargeSummaryOpen(false)}
              >
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Modal: Inpatient Admission Confirmation & Bed Head Ticket (ISOLATED PRINT AREA) */}
      {confirmedAdmission && (
        <Modal
          isOpen={isSuccessModalOpen}
          onClose={() => setIsSuccessModalOpen(false)}
          title="Inpatient Admission Confirmed & Bed Assigned"
        >
          <div className="space-y-4">
            <div className="print-area p-6 rounded-xl bg-white text-slate-900 border border-slate-300 font-sans text-xs space-y-3 shadow-sm">
              {/* Hospital Header */}
              <div className="text-center border-b border-slate-300 pb-2.5">
                <div className="font-bold text-sm tracking-wide text-slate-900 uppercase">
                  {hospitalProfile.name}
                </div>
                <div className="text-[10px] text-slate-600 font-mono">
                  Inpatient Admission Face Sheet & Bed Head Ticket (BHT)
                </div>
                <div className="text-[9px] text-slate-500">
                  {hospitalProfile.accreditation} • Tel: {hospitalProfile.phone}
                </div>
              </div>

              {/* Reference Header */}
              <div className="flex items-center justify-between border-b border-slate-200 pb-2 font-mono">
                <div>
                  <span className="text-slate-500 text-[10px] uppercase block">Admission Docket</span>
                  <span className="font-bold text-emerald-800 text-sm">ADM-{confirmedAdmission.id}</span>
                </div>
                <div className="text-right">
                  <span className="text-slate-500 text-[10px] uppercase block">Assigned Bed & Room</span>
                  <span className="font-bold text-sky-800 text-sm bg-sky-50 px-2.5 py-0.5 rounded border border-sky-300">
                    Bed {confirmedAdmission.bedNumber} ({confirmedAdmission.roomNumber})
                  </span>
                </div>
              </div>

              {/* Patient Core Grid */}
              <div className="grid grid-cols-2 gap-2 bg-slate-50 p-2.5 rounded border border-slate-200">
                <div>
                  <span className="text-slate-500 text-[10px] block font-mono">Patient Legal Name</span>
                  <span className="text-slate-900 font-bold">{confirmedAdmission.patientName}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] block font-mono">Universal Hospital ID (UHID)</span>
                  <span className="text-slate-900 font-bold font-mono">{confirmedAdmission.mrn}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] block font-mono">Clinical Ward & Discipline</span>
                  <span className="text-slate-800">{confirmedAdmission.ward}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] block font-mono">Admitting Consultant</span>
                  <span className="text-slate-800 font-medium">{confirmedAdmission.admittingDoctor}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] block font-mono">Admission Timestamp</span>
                  <span className="text-slate-800 font-mono">{confirmedAdmission.admittedAt}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] block font-mono">Billing / TPA Coverage</span>
                  <span className="text-emerald-800 font-mono">{confirmedAdmission.tpaInsurance || "Self-Pay / Cash"}</span>
                </div>
              </div>

              {/* Barcode Strip */}
              <div className="py-2 border-t border-slate-200 flex flex-col items-center justify-center">
                <div className="h-8 w-60 bg-slate-900 flex items-center justify-center text-[10px] text-white font-mono tracking-widest">
                  ||||| | |||| || ||| | |||
                </div>
                <div className="text-[9px] font-mono text-slate-600 mt-1">
                  *ADM-{confirmedAdmission.id}-{confirmedAdmission.mrn}*
                </div>
              </div>

              {/* Nurse Intake & Verification Handover Check */}
              <div className="p-2.5 bg-slate-50 rounded border border-slate-200 text-[10px] font-mono space-y-1">
                <div className="font-bold text-slate-800 uppercase">Station Nurse Handover Protocol:</div>
                <div className="flex justify-between">
                  <span>[✓] Patient Wristband Attached & Verified</span>
                  <span>[✓] Vital Signs Baseline Logged</span>
                </div>
                <div className="flex justify-between">
                  <span>[✓] Allergy Band Verified</span>
                  <span>[✓] Attendant Welcome Kit Provided</span>
                </div>
              </div>

              {/* Signature section */}
              <div className="pt-4 flex justify-between items-end border-t border-slate-300 text-[10px] font-mono">
                <div>
                  <div className="border-b border-slate-400 w-36 pb-1 mb-1"></div>
                  <div>ADT Desk Officer Signature</div>
                </div>
                <div className="text-right">
                  <div className="border-b border-slate-400 w-36 pb-1 mb-1"></div>
                  <div>Patient / Attendant Consent</div>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 gap-2">
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handlePrintBHT}
                  className="flex items-center gap-1.5"
                >
                  <Printer size={13} className="text-sky-400" /> Print Bed Head Ticket (BHT)
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handlePrintAdmissionWristband}
                  className="flex items-center gap-1.5 border-purple-800 text-purple-300 bg-purple-950/40 hover:bg-purple-900/60"
                >
                  <Printer size={13} className="text-purple-400" /> Print Bedside Wristband
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handlePrintAttendantPass}
                  className="flex items-center gap-1.5 border-emerald-800 text-emerald-300 bg-emerald-950/40 hover:bg-emerald-900/60"
                  title="Print Bedside Attendant & Security Visitor Gate Pass"
                >
                  <Printer size={13} className="text-emerald-400" /> Print Attendant Pass
                </Button>
              </div>

              <Button
                variant="primary"
                size="sm"
                onClick={() => setIsSuccessModalOpen(false)}
              >
                Done
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
