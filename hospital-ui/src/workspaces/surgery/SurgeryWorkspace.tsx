import React, { useState } from "react";
import {
  Scissors,
  ShieldCheck,
  Printer,
  Sparkles,
  Activity,
  PlusCircle,
  Search,
  Check,
} from "lucide-react";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { useActivePatient } from "../../core/context/ActivePatientContext";
import { useHospitalConfig } from "../../core/context/HospitalConfigContext";
import { printDocument } from "../../utils/printDocument";

export type TheatreStatus =
  | "IN_SURGERY"
  | "PRE_OP_INDUCTION"
  | "PACU_RECOVERY"
  | "STERILIZATION_TURNOVER"
  | "SCHEDULED_READY";

export interface SurgicalCase {
  id: string;
  theatreNumber: string;
  theatreName: string;
  patientName: string;
  mrn: string;
  age: number;
  gender: string;
  bloodGroup: string;
  procedureName: string;
  leadSurgeon: string;
  anesthesiologist: string;
  scrubNurse: string;
  anesthesiaType: "GENERAL" | "SPINAL" | "EPIDURAL" | "REGIONAL_BLOCK" | "MAC_SEDATION";
  asaGrade: "ASA I" | "ASA II" | "ASA III" | "ASA IV" | "ASA E";
  bloodUnitsCrossmatched: number;
  scheduledTime: string;
  status: TheatreStatus;
  elapsedMinutes?: number;
  whoChecklist: {
    signInComplete: boolean;
    timeOutComplete: boolean;
    signOutComplete: boolean;
  };
  spongeCount: {
    initial: number;
    retrieved: number;
    reconciled: boolean;
  };
  needleCount: {
    initial: number;
    retrieved: number;
    reconciled: boolean;
  };
  implantDetails?: {
    deviceType: string;
    manufacturer: string;
    serialLotNumber: string;
    udiBarcode: string;
  };
  aldreteScore?: {
    activity: number;
    respiration: number;
    circulation: number;
    consciousness: number;
    o2Sat: number;
  };
}

export const SurgeryWorkspace: React.FC = () => {
  const { selectPatient } = useActivePatient();
  const { hospitalProfile, getPrinterForCategory } = useHospitalConfig();

  const [activeTab, setActiveTab] = useState<"theatres" | "checklist" | "counts" | "pacu">("theatres");
  const [selectedCaseId, setSelectedCaseId] = useState<string>("CASE-01");
  const [searchFilter, setSearchFilter] = useState("");

  // Operational Surgical Cases
  const [cases, setCases] = useState<SurgicalCase[]>([
    {
      id: "CASE-01",
      theatreNumber: "OT-1",
      theatreName: "Cardiac & Thoracic Hybrid Suite",
      patientName: "Siddharth Verma",
      mrn: "MRN-2026-0001",
      age: 38,
      gender: "MALE",
      bloodGroup: "B+",
      procedureName: "Emergency Percutaneous Coronary Angioplasty (PTCA) + Stenting (LAD)",
      leadSurgeon: "Dr. Vikram Seth (Cardiology)",
      anesthesiologist: "Dr. Sunita Kulkarni, MD",
      scrubNurse: "Staff Nurse Anita Roy",
      anesthesiaType: "MAC_SEDATION",
      asaGrade: "ASA III",
      bloodUnitsCrossmatched: 2,
      scheduledTime: "08:30 AM",
      status: "IN_SURGERY",
      elapsedMinutes: 45,
      whoChecklist: {
        signInComplete: true,
        timeOutComplete: true,
        signOutComplete: false,
      },
      spongeCount: {
        initial: 10,
        retrieved: 10,
        reconciled: true,
      },
      needleCount: {
        initial: 4,
        retrieved: 4,
        reconciled: true,
      },
      implantDetails: {
        deviceType: "Drug-Eluting Coronary Stent (DES) 3.5 x 28mm",
        manufacturer: "Abbott Vascular • Xience Sierra",
        serialLotNumber: "LOT-882914-A",
        udiBarcode: "(01)08717648291038(17)281231(10)LOT-882914-A",
      },
      aldreteScore: {
        activity: 2,
        respiration: 2,
        circulation: 2,
        consciousness: 2,
        o2Sat: 2,
      },
    },
    {
      id: "CASE-02",
      theatreNumber: "OT-2",
      theatreName: "Neurosurgery & Image-Guided Suite",
      patientName: "Kavita Ramachandran",
      mrn: "MRN-2026-0012",
      age: 46,
      gender: "FEMALE",
      bloodGroup: "A+",
      procedureName: "Left Frontoparietal Craniotomy for Meningioma Excision (Neuronavigation)",
      leadSurgeon: "Dr. Devendra Rathore (Neurosurgery)",
      anesthesiologist: "Dr. Anand Varma, MD (Neuro-Anesthesia)",
      scrubNurse: "Staff Nurse Preethi Jose",
      anesthesiaType: "GENERAL",
      asaGrade: "ASA II",
      bloodUnitsCrossmatched: 4,
      scheduledTime: "09:00 AM",
      status: "IN_SURGERY",
      elapsedMinutes: 110,
      whoChecklist: {
        signInComplete: true,
        timeOutComplete: true,
        signOutComplete: false,
      },
      spongeCount: {
        initial: 20,
        retrieved: 20,
        reconciled: true,
      },
      needleCount: {
        initial: 8,
        retrieved: 8,
        reconciled: true,
      },
    },
    {
      id: "CASE-03",
      theatreNumber: "OT-3",
      theatreName: "Orthopedics & Joint Replacement Suite",
      patientName: "Vikramaditya Singhania",
      mrn: "MRN-2026-0003",
      age: 64,
      gender: "MALE",
      bloodGroup: "A+",
      procedureName: "Total Knee Arthroplasty (TKA) - Left Knee (Robotic-Assisted)",
      leadSurgeon: "Dr. Harish Patel (Orthopedics)",
      anesthesiologist: "Dr. Meenakshi S., MD",
      scrubNurse: "Staff Nurse Thomas Kurian",
      anesthesiaType: "SPINAL",
      asaGrade: "ASA II",
      bloodUnitsCrossmatched: 2,
      scheduledTime: "11:30 AM",
      status: "PRE_OP_INDUCTION",
      whoChecklist: {
        signInComplete: true,
        timeOutComplete: false,
        signOutComplete: false,
      },
      spongeCount: {
        initial: 15,
        retrieved: 15,
        reconciled: true,
      },
      needleCount: {
        initial: 6,
        retrieved: 6,
        reconciled: true,
      },
      implantDetails: {
        deviceType: "Triathlon Posterior-Stabilized (PS) Knee System (Size 5)",
        manufacturer: "Stryker Orthopaedics",
        serialLotNumber: "LOT-TKA-77319",
        udiBarcode: "(01)07612345678901(17)290630(10)LOT-TKA-77319",
      },
    },
    {
      id: "CASE-04",
      theatreNumber: "OT-4",
      theatreName: "Laparoscopic & Minimal Access Surgery",
      patientName: "Deepak Choudhury",
      mrn: "MRN-2026-0018",
      age: 29,
      gender: "MALE",
      bloodGroup: "O+",
      procedureName: "Laparoscopic Cholecystectomy + Intraoperative Cholangiogram",
      leadSurgeon: "Dr. Radhika Sen (General Surgery)",
      anesthesiologist: "Dr. Sunita Kulkarni, MD",
      scrubNurse: "Staff Nurse Sunita Das",
      anesthesiaType: "GENERAL",
      asaGrade: "ASA I",
      bloodUnitsCrossmatched: 1,
      scheduledTime: "12:15 PM",
      status: "PACU_RECOVERY",
      whoChecklist: {
        signInComplete: true,
        timeOutComplete: true,
        signOutComplete: true,
      },
      spongeCount: {
        initial: 10,
        retrieved: 10,
        reconciled: true,
      },
      needleCount: {
        initial: 4,
        retrieved: 4,
        reconciled: true,
      },
      aldreteScore: {
        activity: 2,
        respiration: 2,
        circulation: 2,
        consciousness: 1,
        o2Sat: 2,
      },
    },
    {
      id: "CASE-05",
      theatreNumber: "OT-5",
      theatreName: "Obstetrics & Emergency C-Section Suite",
      patientName: "Meenakshi Sundaram",
      mrn: "MRN-2026-0004",
      age: 45,
      gender: "FEMALE",
      bloodGroup: "AB+",
      procedureName: "Total Abdominal Hysterectomy with Bilateral Salpingo-Oophorectomy (TAH-BSO)",
      leadSurgeon: "Dr. Radhika Sen (OBG/Gynae-Oncology)",
      anesthesiologist: "Dr. Anand Varma, MD",
      scrubNurse: "Staff Nurse Deepa Nair",
      anesthesiaType: "EPIDURAL",
      asaGrade: "ASA II",
      bloodUnitsCrossmatched: 2,
      scheduledTime: "02:00 PM",
      status: "STERILIZATION_TURNOVER",
      whoChecklist: {
        signInComplete: false,
        timeOutComplete: false,
        signOutComplete: false,
      },
      spongeCount: {
        initial: 0,
        retrieved: 0,
        reconciled: true,
      },
      needleCount: {
        initial: 0,
        retrieved: 0,
        reconciled: true,
      },
    },
    {
      id: "CASE-06",
      theatreNumber: "OT-6",
      theatreName: "STAT Poly-Trauma & Emergency Resuscitation Suite",
      patientName: "Trauma Code Red Unidentified",
      mrn: "ER-0912",
      age: 32,
      gender: "MALE",
      bloodGroup: "O- (Universal Donor)",
      procedureName: "Emergency Damage Control Laparotomy + Splenectomy (Blunt Abdominal Trauma)",
      leadSurgeon: "Dr. Radhika Sen & On-call Trauma Team",
      anesthesiologist: "Dr. Sameer Joshi (Trauma Critical Care)",
      scrubNurse: "Staff Nurse Anita Roy",
      anesthesiaType: "GENERAL",
      asaGrade: "ASA E",
      bloodUnitsCrossmatched: 6,
      scheduledTime: "NOW (STAT EMERGENCY)",
      status: "SCHEDULED_READY",
      whoChecklist: {
        signInComplete: false,
        timeOutComplete: false,
        signOutComplete: false,
      },
      spongeCount: {
        initial: 25,
        retrieved: 25,
        reconciled: true,
      },
      needleCount: {
        initial: 10,
        retrieved: 10,
        reconciled: true,
      },
    },
  ]);

  // Modal State for New Surgical Case Booking
  const [isNewBookingModalOpen, setIsNewBookingModalOpen] = useState(false);
  const [bookPatientName, setBookPatientName] = useState("Rajesh Nambiar");
  const [bookMrn, setBookMrn] = useState("MRN-2026-0022");
  const [bookProcedure, setBookProcedure] = useState("Right Inguinal Hernia Repair (Mesh Plasty)");
  const [bookTheatre, setBookTheatre] = useState("OT-4");
  const [bookSurgeon, setBookSurgeon] = useState("Dr. Radhika Sen (General Surgery)");
  const [bookAnesthesia, setBookAnesthesia] = useState<"GENERAL" | "SPINAL" | "EPIDURAL" | "REGIONAL_BLOCK" | "MAC_SEDATION">("SPINAL");
  const [bookAsa, setBookAsa] = useState<"ASA I" | "ASA II" | "ASA III" | "ASA IV" | "ASA E">("ASA I");

  // Active Selected Case
  const activeCase = cases.find((c) => c.id === selectedCaseId) || cases[0];

  // WHO Checklist Toggle Handler
  const toggleWhoItem = (phase: "signInComplete" | "timeOutComplete" | "signOutComplete") => {
    setCases((prev) =>
      prev.map((c) => {
        if (c.id !== activeCase.id) return c;
        return {
          ...c,
          whoChecklist: {
            ...c.whoChecklist,
            [phase]: !c.whoChecklist[phase],
          },
        };
      })
    );
  };

  // Sponge Count Adjustment
  const adjustSpongeRetrieved = (delta: number) => {
    setCases((prev) =>
      prev.map((c) => {
        if (c.id !== activeCase.id) return c;
        const newRetrieved = Math.max(0, c.spongeCount.retrieved + delta);
        return {
          ...c,
          spongeCount: {
            ...c.spongeCount,
            retrieved: newRetrieved,
            reconciled: newRetrieved === c.spongeCount.initial,
          },
        };
      })
    );
  };

  // Needle Count Adjustment
  const adjustNeedleRetrieved = (delta: number) => {
    setCases((prev) =>
      prev.map((c) => {
        if (c.id !== activeCase.id) return c;
        const newRetrieved = Math.max(0, c.needleCount.retrieved + delta);
        return {
          ...c,
          needleCount: {
            ...c.needleCount,
            retrieved: newRetrieved,
            reconciled: newRetrieved === c.needleCount.initial,
          },
        };
      })
    );
  };

  // Calculate Aldrete Total Score
  const aldreteTotal = activeCase.aldreteScore
    ? activeCase.aldreteScore.activity +
      activeCase.aldreteScore.respiration +
      activeCase.aldreteScore.circulation +
      activeCase.aldreteScore.consciousness +
      activeCase.aldreteScore.o2Sat
    : 0;

  // Print Statutory Intra-Operative Surgical Docket & Face Sheet
  const handlePrintOperativeDocket = (c: SurgicalCase) => {
    const html = `
      <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 720px; margin: 0 auto; border: 2px solid #000; padding: 24px;">
        <div style="text-align: center; border-bottom: 2px solid #000; padding-bottom: 12px; margin-bottom: 16px;">
          <h2 style="margin: 0; font-size: 20px; text-transform: uppercase;">${hospitalProfile.name}</h2>
          <div style="font-size: 12px; font-weight: bold; color: #0284c7; margin-top: 2px;">DEPARTMENT OF SURGERY & ANESTHESIOLOGY • INTRA-OPERATIVE DOCKET</div>
          <div style="font-size: 10px; color: #555;">${hospitalProfile.address} • Tel: ${hospitalProfile.phone}</div>
        </div>

        <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #ccc; padding-bottom: 8px; font-size: 12px; margin-bottom: 12px;">
          <div><b>Patient Legal Name:</b> ${c.patientName.toUpperCase()}</div>
          <div><b>UHID / MRN:</b> ${c.mrn}</div>
          <div><b>Age / Gender:</b> ${c.age} Y / ${c.gender}</div>
          <div><b>Blood Group:</b> ${c.bloodGroup}</div>
        </div>

        <div style="border: 1px solid #999; padding: 10px; background: #f8fafc; font-size: 12px; margin-bottom: 14px; line-height: 1.6;">
          <div><b>Surgical Theatre:</b> ${c.theatreNumber} — ${c.theatreName}</div>
          <div><b>Scheduled Procedure:</b> <span style="font-weight: bold; color: #0f172a;">${c.procedureName}</span></div>
          <div><b>Chief Operating Surgeon:</b> ${c.leadSurgeon}</div>
          <div><b>Consultant Anesthesiologist:</b> ${c.anesthesiologist}</div>
          <div><b>Scrub & Circulating Nurse:</b> ${c.scrubNurse}</div>
          <div><b>Anesthesia Modality:</b> ${c.anesthesiaType} • <b>ASA Grade:</b> ${c.asaGrade}</div>
          <div><b>Blood Transfusion Reserve:</b> ${c.bloodUnitsCrossmatched} Units PRBC Crossmatched</div>
        </div>

        <div style="margin-bottom: 14px; border: 1px solid #cbd5e1; padding: 10px; font-size: 11px;">
          <div style="font-weight: bold; text-transform: uppercase; margin-bottom: 6px; color: #1e293b;">
            WHO Surgical Safety Checklist Execution Status:
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px;">
            <div style="padding: 6px; background: ${c.whoChecklist.signInComplete ? "#f0fdf4" : "#fef2f2"}; border: 1px solid ${c.whoChecklist.signInComplete ? "#86efac" : "#fca5a5"};">
              <b>Phase 1: SIGN IN</b><br/>${c.whoChecklist.signInComplete ? "✓ Verified & Sealed" : "✗ Pending"}
            </div>
            <div style="padding: 6px; background: ${c.whoChecklist.timeOutComplete ? "#f0fdf4" : "#fef2f2"}; border: 1px solid ${c.whoChecklist.timeOutComplete ? "#86efac" : "#fca5a5"};">
              <b>Phase 2: TIME OUT</b><br/>${c.whoChecklist.timeOutComplete ? "✓ Verified & Sealed" : "✗ Pending"}
            </div>
            <div style="padding: 6px; background: ${c.whoChecklist.signOutComplete ? "#f0fdf4" : "#fef2f2"}; border: 1px solid ${c.whoChecklist.signOutComplete ? "#86efac" : "#fca5a5"};">
              <b>Phase 3: SIGN OUT</b><br/>${c.whoChecklist.signOutComplete ? "✓ Verified & Sealed" : "✗ Pending"}
            </div>
          </div>
        </div>

        <div style="margin-bottom: 14px; border: 1px solid #cbd5e1; padding: 10px; font-size: 11px;">
          <div style="font-weight: bold; text-transform: uppercase; margin-bottom: 6px; color: #1e293b;">
            Sterile Swab, Sponge & Needle Reconciliation:
          </div>
          <div style="display: flex; justify-content: space-between;">
            <div>Surgical Sponges: Initial (${c.spongeCount.initial}) • Retrieved (${c.spongeCount.retrieved}) • <b style="color: ${c.spongeCount.reconciled ? "#16a34a" : "#dc2626"};">${c.spongeCount.reconciled ? "RECONCILED (0 DEFICIT)" : "ALERT: COUNT DEFICIT"}</b></div>
            <div>Needles/Sutures: Initial (${c.needleCount.initial}) • Retrieved (${c.needleCount.retrieved}) • <b style="color: ${c.needleCount.reconciled ? "#16a34a" : "#dc2626"};">${c.needleCount.reconciled ? "RECONCILED (0 DEFICIT)" : "ALERT: COUNT DEFICIT"}</b></div>
          </div>
        </div>

        ${c.implantDetails ? `
        <div style="margin-bottom: 14px; border: 1px dashed #0284c7; background: #f0f9ff; padding: 10px; font-size: 11px;">
          <div style="font-weight: bold; color: #0369a1; text-transform: uppercase;">Medical Implant / Prosthesis Registry Record:</div>
          <div><b>Device:</b> ${c.implantDetails.deviceType}</div>
          <div><b>Manufacturer:</b> ${c.implantDetails.manufacturer} • <b>Lot/Serial:</b> ${c.implantDetails.serialLotNumber}</div>
          <div style="font-family: monospace; font-size: 10px; color: #555;">UDI: ${c.implantDetails.udiBarcode}</div>
        </div>
        ` : ""}

        <div style="margin-top: 50px; display: flex; justify-content: space-between; font-size: 11px;">
          <div style="border-top: 1px solid #000; width: 220px; text-align: center; padding-top: 4px;">Chief Operating Surgeon Signature</div>
          <div style="border-top: 1px solid #000; width: 220px; text-align: center; padding-top: 4px;">Scrub Nurse Verification Signature</div>
        </div>
        <div style="margin-top: 24px; text-align: center; font-size: 9px; color: #64748b;">
          Avinya HMS Statutory Surgical Suite Clinical OS • Confidential Medical Record
        </div>
      </div>
    `;
    const a4Printer = getPrinterForCategory("CLINICAL_A4");
    printDocument(html, {
      title: `OT_Docket_${c.mrn}`,
      docType: "CLINICAL_SUMMARY",
      printerDevice: a4Printer,
    });
  };

  const getStatusBadge = (status: TheatreStatus) => {
    switch (status) {
      case "IN_SURGERY":
        return <Badge variant="danger" size="sm">IN SURGERY</Badge>;
      case "PRE_OP_INDUCTION":
        return <Badge variant="warning" size="sm">INDUCTION</Badge>;
      case "PACU_RECOVERY":
        return <Badge variant="info" size="sm">PACU RECOVERY</Badge>;
      case "STERILIZATION_TURNOVER":
        return <Badge variant="neutral" size="sm">TURNOVER / STERILE</Badge>;
      case "SCHEDULED_READY":
        return <Badge variant="success" size="sm">READY / NEXT</Badge>;
    }
  };

  return (
    <div className="flex-1 flex flex-col bg-slate-950 overflow-hidden select-none">
      {/* Top Banner: OT Suite Command Header */}
      <div className="p-4 bg-slate-900/80 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-rose-950/60 border border-rose-800 text-rose-400">
            <Scissors size={20} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold text-slate-100">
                Operating Theatre (OT) &amp; Surgical Suite Command
              </h1>
              <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-rose-950/80 text-rose-300 border border-rose-800/80">
                6 Modular ORs Live
              </span>
            </div>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              WHO 3-Phase Surgical Checklist • Sterile Count Reconciliation • PACU Aldrete Scoring • Implant Registry
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Quick Sub-navigation */}
          <div className="flex bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs">
            <button
              onClick={() => setActiveTab("theatres")}
              className={`px-3 py-1 rounded font-semibold transition-all ${
                activeTab === "theatres" ? "bg-rose-500/20 text-rose-300 border border-rose-500/40" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Theatres Grid
            </button>
            <button
              onClick={() => setActiveTab("checklist")}
              className={`px-3 py-1 rounded font-semibold transition-all ${
                activeTab === "checklist" ? "bg-rose-500/20 text-rose-300 border border-rose-500/40" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              WHO Safety Checklist
            </button>
            <button
              onClick={() => setActiveTab("counts")}
              className={`px-3 py-1 rounded font-semibold transition-all ${
                activeTab === "counts" ? "bg-rose-500/20 text-rose-300 border border-rose-500/40" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              Sterile Counts &amp; Implants
            </button>
            <button
              onClick={() => setActiveTab("pacu")}
              className={`px-3 py-1 rounded font-semibold transition-all ${
                activeTab === "pacu" ? "bg-rose-500/20 text-rose-300 border border-rose-500/40" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              PACU Recovery
            </button>
          </div>

          <Button
            size="sm"
            variant="primary"
            onClick={() => setIsNewBookingModalOpen(true)}
            className="flex items-center gap-1.5 font-bold bg-rose-600 hover:bg-rose-500 text-slate-950"
          >
            <PlusCircle size={14} /> Schedule Surgical Case
          </Button>
        </div>
      </div>

      {/* Main Workspace 2-Column Clinical Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Column: Theatre Grid & Patient Queue */}
        <div className="w-[420px] bg-slate-950 border-r border-slate-800 flex flex-col overflow-y-auto">
          <div className="p-3 border-b border-slate-800 bg-slate-900/40">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-2.5 text-slate-500" />
              <input
                type="text"
                placeholder="Filter by patient, procedure, surgeon, or OT..."
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-rose-500"
              />
            </div>
          </div>

          <div className="p-3 space-y-2.5 overflow-y-auto flex-1">
            {cases
              .filter(
                (c) =>
                  c.patientName.toLowerCase().includes(searchFilter.toLowerCase()) ||
                  c.procedureName.toLowerCase().includes(searchFilter.toLowerCase()) ||
                  c.theatreNumber.toLowerCase().includes(searchFilter.toLowerCase()) ||
                  c.leadSurgeon.toLowerCase().includes(searchFilter.toLowerCase())
              )
              .map((c) => {
                const isSelected = c.id === activeCase.id;
                return (
                  <div
                    key={c.id}
                    onClick={() => {
                      setSelectedCaseId(c.id);
                      selectPatient(1);
                    }}
                    className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? "bg-rose-950/40 border-rose-500/80 ring-1 ring-rose-500/50 shadow-lg"
                        : "bg-slate-900/60 border-slate-800 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-rose-400 bg-rose-950/60 px-2 py-0.5 rounded border border-rose-800/80">
                          {c.theatreNumber}
                        </span>
                        <span className="text-xs font-bold text-slate-100">{c.patientName}</span>
                      </div>
                      {getStatusBadge(c.status)}
                    </div>

                    <div className="text-xs text-slate-300 font-medium line-clamp-1 mb-1">
                      {c.procedureName}
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono mt-2 pt-2 border-t border-slate-800/80">
                      <span>Surgeon: {c.leadSurgeon.split("(")[0]}</span>
                      <span className="text-amber-400 font-bold">{c.scheduledTime}</span>
                    </div>

                    {c.elapsedMinutes && (
                      <div className="mt-2 flex items-center justify-between text-[10px] font-mono text-slate-400 bg-slate-950/80 px-2 py-1 rounded">
                        <span className="flex items-center gap-1 text-rose-400 font-bold">
                          <Activity size={10} /> In-Op Timer: {c.elapsedMinutes} mins
                        </span>
                        <span>ASA: {c.asaGrade}</span>
                      </div>
                    )}
                  </div>
                );
              })}
          </div>
        </div>

        {/* Right Column: Case Deep-Dive & Clinical Protocol Manager */}
        <div className="flex-1 flex flex-col overflow-y-auto p-6 space-y-6">
          {/* Active Case Header Summary */}
          <Card className="p-4 bg-slate-900/80 border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold text-rose-400 bg-rose-950/80 px-2 py-0.5 rounded border border-rose-800">
                    {activeCase.theatreNumber} • {activeCase.theatreName}
                  </span>
                  <h2 className="text-lg font-bold text-slate-100">{activeCase.patientName}</h2>
                  <span className="text-xs text-slate-400 font-mono">({activeCase.mrn})</span>
                </div>
                <div className="text-xs text-rose-300 font-semibold mt-1">
                  {activeCase.procedureName}
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handlePrintOperativeDocket(activeCase)}
                  className="flex items-center gap-1.5"
                >
                  <Printer size={13} /> Print Operative Docket
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-4 gap-3 pt-3 border-t border-slate-800 text-xs">
              <div>
                <span className="text-[10px] text-slate-500 uppercase font-bold block">Operating Surgeon</span>
                <span className="text-slate-200 font-semibold">{activeCase.leadSurgeon}</span>
              </div>
              <div>
                <span className="text-[10px] text-slate-500 uppercase font-bold block">Consultant Anesthetist</span>
                <span className="text-slate-200 font-semibold">{activeCase.anesthesiologist}</span>
              </div>
              <div>
                <span className="text-[10px] text-slate-500 uppercase font-bold block">Anesthesia &amp; ASA</span>
                <span className="text-sky-400 font-semibold">{activeCase.anesthesiaType} ({activeCase.asaGrade})</span>
              </div>
              <div>
                <span className="text-[10px] text-slate-500 uppercase font-bold block">Blood Bank Crossmatch</span>
                <span className="text-emerald-400 font-semibold">{activeCase.bloodUnitsCrossmatched} Units PRBC On Hold</span>
              </div>
            </div>
          </Card>

          {/* Tab 1: WHO 3-Phase Surgical Safety Checklist */}
          {activeTab === "checklist" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2 uppercase tracking-wider">
                  <ShieldCheck size={16} className="text-rose-400" />
                  WHO 3-Phase Surgical Safety Checklist Protocol
                </h3>
                <span className="text-xs font-mono text-slate-400">
                  Accredited by WHO / NABH Standards
                </span>
              </div>

              <div className="grid grid-cols-3 gap-4">
                {/* Phase 1: SIGN IN */}
                <Card className={`p-4 border transition-all ${
                  activeCase.whoChecklist.signInComplete
                    ? "bg-emerald-950/20 border-emerald-800/60"
                    : "bg-slate-900/60 border-slate-800"
                }`}>
                  <div className="flex items-center justify-between pb-2 border-b border-slate-800 mb-3">
                    <div>
                      <span className="text-[10px] font-mono font-bold text-slate-400 uppercase">Phase 1</span>
                      <h4 className="text-xs font-bold text-slate-100">SIGN IN (Pre-Induction)</h4>
                    </div>
                    <button
                      onClick={() => toggleWhoItem("signInComplete")}
                      className={`px-2 py-1 rounded text-[10px] font-bold font-mono border ${
                        activeCase.whoChecklist.signInComplete
                          ? "bg-emerald-500 text-slate-950 border-emerald-400"
                          : "bg-slate-800 text-slate-300 border-slate-700"
                      }`}
                    >
                      {activeCase.whoChecklist.signInComplete ? "✓ Sealed" : "Mark Done"}
                    </button>
                  </div>
                  <ul className="text-xs space-y-2 text-slate-300">
                    <li className="flex items-center gap-2">
                      <Check size={12} className={activeCase.whoChecklist.signInComplete ? "text-emerald-400" : "text-slate-600"} />
                      Patient identity, operative site &amp; consent verified
                    </li>
                    <li className="flex items-center gap-2">
                      <Check size={12} className={activeCase.whoChecklist.signInComplete ? "text-emerald-400" : "text-slate-600"} />
                      Operative site marked by lead surgeon
                    </li>
                    <li className="flex items-center gap-2">
                      <Check size={12} className={activeCase.whoChecklist.signInComplete ? "text-emerald-400" : "text-slate-600"} />
                      Anesthesia machine &amp; medication check complete
                    </li>
                    <li className="flex items-center gap-2">
                      <Check size={12} className={activeCase.whoChecklist.signInComplete ? "text-emerald-400" : "text-slate-600"} />
                      Pulse oximeter on patient and functioning
                    </li>
                    <li className="flex items-center gap-2">
                      <Check size={12} className={activeCase.whoChecklist.signInComplete ? "text-emerald-400" : "text-slate-600"} />
                      Known allergy check (Antibiotics, Latex)
                    </li>
                  </ul>
                </Card>

                {/* Phase 2: TIME OUT */}
                <Card className={`p-4 border transition-all ${
                  activeCase.whoChecklist.timeOutComplete
                    ? "bg-emerald-950/20 border-emerald-800/60"
                    : "bg-slate-900/60 border-slate-800"
                }`}>
                  <div className="flex items-center justify-between pb-2 border-b border-slate-800 mb-3">
                    <div>
                      <span className="text-[10px] font-mono font-bold text-slate-400 uppercase">Phase 2</span>
                      <h4 className="text-xs font-bold text-slate-100">TIME OUT (Pre-Incision)</h4>
                    </div>
                    <button
                      onClick={() => toggleWhoItem("timeOutComplete")}
                      className={`px-2 py-1 rounded text-[10px] font-bold font-mono border ${
                        activeCase.whoChecklist.timeOutComplete
                          ? "bg-emerald-500 text-slate-950 border-emerald-400"
                          : "bg-slate-800 text-slate-300 border-slate-700"
                      }`}
                    >
                      {activeCase.whoChecklist.timeOutComplete ? "✓ Sealed" : "Mark Done"}
                    </button>
                  </div>
                  <ul className="text-xs space-y-2 text-slate-300">
                    <li className="flex items-center gap-2">
                      <Check size={12} className={activeCase.whoChecklist.timeOutComplete ? "text-emerald-400" : "text-slate-600"} />
                      All team members introduced by name &amp; role
                    </li>
                    <li className="flex items-center gap-2">
                      <Check size={12} className={activeCase.whoChecklist.timeOutComplete ? "text-emerald-400" : "text-slate-600"} />
                      Surgeon, Anesthetist &amp; Nurse verbally confirm patient &amp; incision
                    </li>
                    <li className="flex items-center gap-2">
                      <Check size={12} className={activeCase.whoChecklist.timeOutComplete ? "text-emerald-400" : "text-slate-600"} />
                      Anticipated critical steps &amp; operative duration reviewed
                    </li>
                    <li className="flex items-center gap-2">
                      <Check size={12} className={activeCase.whoChecklist.timeOutComplete ? "text-emerald-400" : "text-slate-600"} />
                      Antibiotic prophylaxis administered within 60 mins
                    </li>
                    <li className="flex items-center gap-2">
                      <Check size={12} className={activeCase.whoChecklist.timeOutComplete ? "text-emerald-400" : "text-slate-600"} />
                      Diagnostic CT/Angiogram imaging displayed on OR monitor
                    </li>
                  </ul>
                </Card>

                {/* Phase 3: SIGN OUT */}
                <Card className={`p-4 border transition-all ${
                  activeCase.whoChecklist.signOutComplete
                    ? "bg-emerald-950/20 border-emerald-800/60"
                    : "bg-slate-900/60 border-slate-800"
                }`}>
                  <div className="flex items-center justify-between pb-2 border-b border-slate-800 mb-3">
                    <div>
                      <span className="text-[10px] font-mono font-bold text-slate-400 uppercase">Phase 3</span>
                      <h4 className="text-xs font-bold text-slate-100">SIGN OUT (Pre-Exit)</h4>
                    </div>
                    <button
                      onClick={() => toggleWhoItem("signOutComplete")}
                      className={`px-2 py-1 rounded text-[10px] font-bold font-mono border ${
                        activeCase.whoChecklist.signOutComplete
                          ? "bg-emerald-500 text-slate-950 border-emerald-400"
                          : "bg-slate-800 text-slate-300 border-slate-700"
                      }`}
                    >
                      {activeCase.whoChecklist.signOutComplete ? "✓ Sealed" : "Mark Done"}
                    </button>
                  </div>
                  <ul className="text-xs space-y-2 text-slate-300">
                    <li className="flex items-center gap-2">
                      <Check size={12} className={activeCase.whoChecklist.signOutComplete ? "text-emerald-400" : "text-slate-600"} />
                      Name of procedure recorded formally
                    </li>
                    <li className="flex items-center gap-2">
                      <Check size={12} className={activeCase.whoChecklist.signOutComplete ? "text-emerald-400" : "text-slate-600"} />
                      Instrument, sponge &amp; needle counts are complete (0 deficit)
                    </li>
                    <li className="flex items-center gap-2">
                      <Check size={12} className={activeCase.whoChecklist.signOutComplete ? "text-emerald-400" : "text-slate-600"} />
                      Biopsy/tissue specimen labelled with 2 identifiers
                    </li>
                    <li className="flex items-center gap-2">
                      <Check size={12} className={activeCase.whoChecklist.signOutComplete ? "text-emerald-400" : "text-slate-600"} />
                      Equipment malfunction issues documented
                    </li>
                    <li className="flex items-center gap-2">
                      <Check size={12} className={activeCase.whoChecklist.signOutComplete ? "text-emerald-400" : "text-slate-600"} />
                      Surgeon &amp; Anesthetist review post-op recovery &amp; PACU plan
                    </li>
                  </ul>
                </Card>
              </div>
            </div>
          )}

          {/* Tab 2: Sterile Swab, Sponge, Needle Counts & Implant Tracker */}
          {activeTab === "counts" && (
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2 uppercase tracking-wider">
                <Scissors size={16} className="text-rose-400" />
                Sterile Surgical Counts &amp; Medical Device Implant Registry
              </h3>

              <div className="grid grid-cols-2 gap-4">
                {/* Sponge Count */}
                <Card className="p-4 bg-slate-900/70 border-slate-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-xs font-bold text-slate-100">Laparotomy Sponges &amp; Gauze Swabs</h4>
                      <p className="text-[11px] text-slate-400">Radiopaque thread verified prior to closure</p>
                    </div>
                    <Badge variant={activeCase.spongeCount.reconciled ? "success" : "danger"} size="sm">
                      {activeCase.spongeCount.reconciled ? "COUNT MATCHED (0 DEFICIT)" : "DISCREPANCY ALERT"}
                    </Badge>
                  </div>

                  <div className="grid grid-cols-3 gap-2 text-center py-2 bg-slate-950 rounded-lg border border-slate-800">
                    <div>
                      <span className="text-[10px] text-slate-500 uppercase block">Initial Given</span>
                      <span className="text-base font-bold font-mono text-slate-200">{activeCase.spongeCount.initial}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500 uppercase block">Retrieved Count</span>
                      <span className="text-base font-bold font-mono text-rose-400">{activeCase.spongeCount.retrieved}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500 uppercase block">Deficit</span>
                      <span className={`text-base font-bold font-mono ${activeCase.spongeCount.reconciled ? "text-emerald-400" : "text-rose-500"}`}>
                        {activeCase.spongeCount.initial - activeCase.spongeCount.retrieved}
                      </span>
                    </div>
                  </div>

                  <div className="flex justify-end gap-2">
                    <Button size="sm" variant="outline" onClick={() => adjustSpongeRetrieved(-1)}>-</Button>
                    <Button size="sm" variant="outline" onClick={() => adjustSpongeRetrieved(1)}>+</Button>
                  </div>
                </Card>

                {/* Needle & Suture Count */}
                <Card className="p-4 bg-slate-900/70 border-slate-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-xs font-bold text-slate-100">Surgical Needles &amp; Sharps</h4>
                      <p className="text-[11px] text-slate-400">Magnetic needle counter block verified</p>
                    </div>
                    <Badge variant={activeCase.needleCount.reconciled ? "success" : "danger"} size="sm">
                      {activeCase.needleCount.reconciled ? "COUNT MATCHED (0 DEFICIT)" : "DISCREPANCY ALERT"}
                    </Badge>
                  </div>

                  <div className="grid grid-cols-3 gap-2 text-center py-2 bg-slate-950 rounded-lg border border-slate-800">
                    <div>
                      <span className="text-[10px] text-slate-500 uppercase block">Initial Given</span>
                      <span className="text-base font-bold font-mono text-slate-200">{activeCase.needleCount.initial}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500 uppercase block">Retrieved Count</span>
                      <span className="text-base font-bold font-mono text-rose-400">{activeCase.needleCount.retrieved}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500 uppercase block">Deficit</span>
                      <span className={`text-base font-bold font-mono ${activeCase.needleCount.reconciled ? "text-emerald-400" : "text-rose-500"}`}>
                        {activeCase.needleCount.initial - activeCase.needleCount.retrieved}
                      </span>
                    </div>
                  </div>

                  <div className="flex justify-end gap-2">
                    <Button size="sm" variant="outline" onClick={() => adjustNeedleRetrieved(-1)}>-</Button>
                    <Button size="sm" variant="outline" onClick={() => adjustNeedleRetrieved(1)}>+</Button>
                  </div>
                </Card>
              </div>

              {/* Implant Registry Card */}
              {activeCase.implantDetails ? (
                <Card className="p-4 bg-sky-950/20 border-sky-800/60 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Sparkles size={16} className="text-sky-400" />
                      <h4 className="text-xs font-bold text-sky-200 uppercase tracking-wider">
                        Medical Implant / Prosthesis Registry Record
                      </h4>
                    </div>
                    <Badge variant="info" size="sm">UDI VERIFIED</Badge>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs pt-1">
                    <div>
                      <span className="text-slate-400 block text-[10px]">Device Name &amp; Dimensions:</span>
                      <span className="font-semibold text-slate-100">{activeCase.implantDetails.deviceType}</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px]">Manufacturer &amp; Lot Number:</span>
                      <span className="font-semibold text-slate-100">
                        {activeCase.implantDetails.manufacturer} ({activeCase.implantDetails.serialLotNumber})
                      </span>
                    </div>
                  </div>

                  <div className="p-2 rounded bg-slate-950 border border-slate-800 font-mono text-[11px] text-sky-300">
                    UDI Barcode: {activeCase.implantDetails.udiBarcode}
                  </div>
                </Card>
              ) : (
                <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800 text-xs text-slate-400 text-center">
                  Nil permanent surgical implants logged for this procedure.
                </div>
              )}
            </div>
          )}

          {/* Tab 3: PACU Recovery & Aldrete Score */}
          {activeTab === "pacu" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2 uppercase tracking-wider">
                    <Activity size={16} className="text-emerald-400" />
                    Post-Anesthesia Care Unit (PACU) Aldrete Scoring Matrix
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Evaluation of physiological recovery prior to discharge to Inpatient Ward or Step-Down ICU
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-slate-400">Total Score:</span>
                  <span className={`text-lg font-bold font-mono px-3 py-1 rounded border ${
                    aldreteTotal >= 9 ? "bg-emerald-950 text-emerald-300 border-emerald-700" : "bg-amber-950 text-amber-300 border-amber-700"
                  }`}>
                    {aldreteTotal} / 10
                  </span>
                  <Badge variant={aldreteTotal >= 9 ? "success" : "warning"} size="sm">
                    {aldreteTotal >= 9 ? "FIT FOR WARD TRANSFER" : "RETAIN IN PACU"}
                  </Badge>
                </div>
              </div>

              <div className="grid grid-cols-5 gap-3">
                <Card className="p-3 bg-slate-900/70 border-slate-800 text-center space-y-1">
                  <span className="text-[10px] text-slate-400 uppercase font-bold block">1. Activity</span>
                  <span className="text-lg font-bold font-mono text-slate-100">{activeCase.aldreteScore?.activity ?? 2} / 2</span>
                  <span className="text-[10px] text-slate-500 block">Moves 4 limbs voluntarily</span>
                </Card>

                <Card className="p-3 bg-slate-900/70 border-slate-800 text-center space-y-1">
                  <span className="text-[10px] text-slate-400 uppercase font-bold block">2. Respiration</span>
                  <span className="text-lg font-bold font-mono text-slate-100">{activeCase.aldreteScore?.respiration ?? 2} / 2</span>
                  <span className="text-[10px] text-slate-500 block">Breathes deeply &amp; coughs</span>
                </Card>

                <Card className="p-3 bg-slate-900/70 border-slate-800 text-center space-y-1">
                  <span className="text-[10px] text-slate-400 uppercase font-bold block">3. Circulation</span>
                  <span className="text-lg font-bold font-mono text-slate-100">{activeCase.aldreteScore?.circulation ?? 2} / 2</span>
                  <span className="text-[10px] text-slate-500 block">BP ± 20% of pre-op level</span>
                </Card>

                <Card className="p-3 bg-slate-900/70 border-slate-800 text-center space-y-1">
                  <span className="text-[10px] text-slate-400 uppercase font-bold block">4. Consciousness</span>
                  <span className="text-lg font-bold font-mono text-slate-100">{activeCase.aldreteScore?.consciousness ?? 2} / 2</span>
                  <span className="text-[10px] text-slate-500 block">Fully awake &amp; oriented</span>
                </Card>

                <Card className="p-3 bg-slate-900/70 border-slate-800 text-center space-y-1">
                  <span className="text-[10px] text-slate-400 uppercase font-bold block">5. O2 Saturation</span>
                  <span className="text-lg font-bold font-mono text-slate-100">{activeCase.aldreteScore?.o2Sat ?? 2} / 2</span>
                  <span className="text-[10px] text-slate-500 block">SpO2 &gt; 92% on room air</span>
                </Card>
              </div>
            </div>
          )}

          {/* Tab 0: Theatres Overview Grid */}
          {activeTab === "theatres" && (
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
                Live Theatre Complex Status (6 Suites)
              </h3>

              <div className="grid grid-cols-3 gap-4">
                {cases.map((c) => (
                  <Card
                    key={c.id}
                    className={`p-4 border transition-all ${
                      c.id === activeCase.id
                        ? "bg-rose-950/20 border-rose-500/80"
                        : "bg-slate-900/70 border-slate-800 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-mono font-bold text-rose-400">{c.theatreNumber}</span>
                      {getStatusBadge(c.status)}
                    </div>
                    <div className="font-bold text-xs text-slate-100 mb-1">{c.theatreName}</div>
                    <div className="text-[11px] text-slate-300 line-clamp-1 mb-2">{c.procedureName}</div>

                    <div className="pt-2 border-t border-slate-800/80 text-[10px] text-slate-400 font-mono space-y-0.5">
                      <div>Patient: {c.patientName} ({c.mrn})</div>
                      <div>Surgeon: {c.leadSurgeon.split("(")[0]}</div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Modal: Schedule New Surgical Case */}
      {isNewBookingModalOpen && (
        <Modal
          isOpen={true}
          onClose={() => setIsNewBookingModalOpen(false)}
          title="Schedule Operating Theatre Booking & Case Induction"
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const newCase: SurgicalCase = {
                id: `CASE-${Date.now().toString().slice(-4)}`,
                theatreNumber: bookTheatre,
                theatreName:
                  bookTheatre === "OT-1"
                    ? "Cardiac & Thoracic Hybrid Suite"
                    : bookTheatre === "OT-2"
                    ? "Neurosurgery & Image-Guided Suite"
                    : bookTheatre === "OT-3"
                    ? "Orthopedics & Joint Replacement Suite"
                    : bookTheatre === "OT-4"
                    ? "Laparoscopic & Minimal Access Surgery"
                    : "Obstetrics & Emergency Suite",
                patientName: bookPatientName,
                mrn: bookMrn,
                age: 42,
                gender: "MALE",
                bloodGroup: "O+",
                procedureName: bookProcedure,
                leadSurgeon: bookSurgeon,
                anesthesiologist: "Dr. Sunita Kulkarni, MD",
                scrubNurse: "Staff Nurse Anita Roy",
                anesthesiaType: bookAnesthesia,
                asaGrade: bookAsa,
                bloodUnitsCrossmatched: 2,
                scheduledTime: "03:30 PM",
                status: "SCHEDULED_READY",
                whoChecklist: {
                  signInComplete: false,
                  timeOutComplete: false,
                  signOutComplete: false,
                },
                spongeCount: {
                  initial: 10,
                  retrieved: 10,
                  reconciled: true,
                },
                needleCount: {
                  initial: 4,
                  retrieved: 4,
                  reconciled: true,
                },
              };
              setCases((prev) => [newCase, ...prev]);
              setSelectedCaseId(newCase.id);
              setIsNewBookingModalOpen(false);
            }}
            className="space-y-4"
          >
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <label className="block text-slate-400 font-semibold mb-1">Patient Legal Name</label>
                <input
                  type="text"
                  required
                  value={bookPatientName}
                  onChange={(e) => setBookPatientName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-slate-200"
                />
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1">Patient UHID / MRN</label>
                <input
                  type="text"
                  required
                  value={bookMrn}
                  onChange={(e) => setBookMrn(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-slate-200 font-mono"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs text-slate-400 font-semibold mb-1">Surgical Procedure Name</label>
              <input
                type="text"
                required
                value={bookProcedure}
                onChange={(e) => setBookProcedure(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
              />
            </div>

            <div>
              <label className="block text-xs text-slate-400 font-semibold mb-1">Lead Operating Surgeon</label>
              <input
                type="text"
                required
                value={bookSurgeon}
                onChange={(e) => setBookSurgeon(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
              />
            </div>

            <div className="grid grid-cols-3 gap-3 text-xs">
              <div>
                <label className="block text-slate-400 font-semibold mb-1">Assigned Theatre</label>
                <select
                  value={bookTheatre}
                  onChange={(e) => setBookTheatre(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-slate-200"
                >
                  <option value="OT-1">OT-1 (Cardiac Hybrid)</option>
                  <option value="OT-2">OT-2 (Neurosurgery)</option>
                  <option value="OT-3">OT-3 (Orthopedics)</option>
                  <option value="OT-4">OT-4 (Laparoscopic)</option>
                  <option value="OT-5">OT-5 (Obstetrics)</option>
                  <option value="OT-6">OT-6 (STAT Trauma)</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1">Anesthesia Modality</label>
                <select
                  value={bookAnesthesia}
                  onChange={(e) => setBookAnesthesia(e.target.value as any)}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-slate-200"
                >
                  <option value="GENERAL">General Anesthesia (GA)</option>
                  <option value="SPINAL">Spinal Anesthesia</option>
                  <option value="EPIDURAL">Epidural Anesthesia</option>
                  <option value="REGIONAL_BLOCK">Regional Nerve Block</option>
                  <option value="MAC_SEDATION">Monitored Anesthesia Care (MAC)</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-400 font-semibold mb-1">ASA Physical Status</label>
                <select
                  value={bookAsa}
                  onChange={(e) => setBookAsa(e.target.value as any)}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-slate-200"
                >
                  <option value="ASA I">ASA I (Normal Healthy)</option>
                  <option value="ASA II">ASA II (Mild Systemic Disease)</option>
                  <option value="ASA III">ASA III (Severe Systemic Disease)</option>
                  <option value="ASA IV">ASA IV (Threat to Life)</option>
                  <option value="ASA E">ASA E (Emergency Surgery)</option>
                </select>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
              <Button type="button" variant="outline" size="sm" onClick={() => setIsNewBookingModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" size="sm" className="bg-rose-600 hover:bg-rose-500 text-slate-950 font-bold">
                Confirm &amp; Allocate Theatre
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
