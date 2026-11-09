import React, { useState } from "react";
import {
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  Search,
  Filter,
  Printer,
  Sparkles,
  Pill,
} from "lucide-react";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { useHospitalConfig } from "../../core/context/HospitalConfigContext";
import { printDocument } from "../../utils/printDocument";

export interface HaiSurveillanceCase {
  id: string;
  patientName: string;
  mrn: string;
  ageGender: string;
  wardLocation: string;
  deviceType: "CENTRAL_LINE" | "FOLEYS_CATHETER" | "VENTILATOR" | "SURGICAL_WOUND";
  deviceDays: number;
  suspectedInfection: "CLABSI" | "CAUTI" | "VAP" | "SSI";
  isolatedPathogen?: string;
  mdrClassification?: "CRE" | "MRSA" | "VRE" | "ESBL" | "PAN_DRUG_RESISTANT";
  isolationStatus: "CONTACT_ISOLATION" | "DROPLET" | "AIRBORNE" | "STANDARD";
  attendingPhysician: string;
  detectionDate: string;
  status: "ACTIVE_SURVEILLANCE" | "CONFIRMED_HAI" | "RESOLVED" | "DE_ISOLATED";
}

export interface AspRequest {
  id: string;
  patientName: string;
  mrn: string;
  wardBed: string;
  prescribingDoctor: string;
  antibioticName: string;
  dosage: string;
  clinicalIndication: string;
  procalcitoninLevel: string;
  cultureReportStatus: "AWAITED" | "ISOLATE_IDENTIFIED" | "EMPIRICAL_SEPSIS";
  identifiedOrganism?: string;
  creatinineClearance: string;
  requestTimestamp: string;
  approvalStatus: "PENDING_REVIEW" | "APPROVED_48H" | "DE_ESCALATED" | "REJECTED";
  idSpecialistNotes?: string;
}

export const InfectionControlWorkspace: React.FC = () => {
  const { hospitalProfile, getPrinterForCategory } = useHospitalConfig();
  const [activeTab, setActiveTab] = useState<"HAI_SURVEILLANCE" | "ASP_QUEUE" | "ANTIBIOGRAM" | "HAND_HYGIENE">("HAI_SURVEILLANCE");
  const [searchQuery, setSearchQuery] = useState("");
  const [deviceFilter, setDeviceFilter] = useState<string>("ALL");

  // Sample HAI Surveillance Register
  const [haiCases] = useState<HaiSurveillanceCase[]>([
    {
      id: "HAI-2026-081",
      patientName: "Gopal Kishan",
      mrn: "AV-2026-00412",
      ageGender: "64M",
      wardLocation: "MICU - Bed 04",
      deviceType: "CENTRAL_LINE",
      deviceDays: 9,
      suspectedInfection: "CLABSI",
      isolatedPathogen: "Klebsiella pneumoniae",
      mdrClassification: "CRE",
      isolationStatus: "CONTACT_ISOLATION",
      attendingPhysician: "Dr. Sameer Joshi",
      detectionDate: "30-Oct-2026",
      status: "CONFIRMED_HAI",
    },
    {
      id: "HAI-2026-082",
      patientName: "Meenakshi Sundaram",
      mrn: "AV-2026-00508",
      ageGender: "52F",
      wardLocation: "SICU - Bed 02",
      deviceType: "VENTILATOR",
      deviceDays: 6,
      suspectedInfection: "VAP",
      isolatedPathogen: "Acinetobacter baumannii",
      mdrClassification: "PAN_DRUG_RESISTANT",
      isolationStatus: "CONTACT_ISOLATION",
      attendingPhysician: "Dr. Radhika Sen",
      detectionDate: "31-Oct-2026",
      status: "CONFIRMED_HAI",
    },
    {
      id: "HAI-2026-083",
      patientName: "Rajendra Prasad",
      mrn: "AV-2026-00614",
      ageGender: "71M",
      wardLocation: "Cardio Ward - Bed 14",
      deviceType: "FOLEYS_CATHETER",
      deviceDays: 12,
      suspectedInfection: "CAUTI",
      isolatedPathogen: "Pseudomonas aeruginosa",
      mdrClassification: "ESBL",
      isolationStatus: "STANDARD",
      attendingPhysician: "Dr. Vikram Seth",
      detectionDate: "01-Nov-2026",
      status: "ACTIVE_SURVEILLANCE",
    },
    {
      id: "HAI-2026-084",
      patientName: "Fatima Begum",
      mrn: "AV-2026-00720",
      ageGender: "45F",
      wardLocation: "General Surgery - Bed 22",
      deviceType: "SURGICAL_WOUND",
      deviceDays: 4,
      suspectedInfection: "SSI",
      isolatedPathogen: "Staphylococcus aureus",
      mdrClassification: "MRSA",
      isolationStatus: "CONTACT_ISOLATION",
      attendingPhysician: "Dr. Radhika Sen",
      detectionDate: "01-Nov-2026",
      status: "CONFIRMED_HAI",
    },
  ]);

  // Sample ASP Restricted Antibiotics Approval Queue
  const [aspRequests, setAspRequests] = useState<AspRequest[]>([
    {
      id: "ASP-2026-301",
      patientName: "Meenakshi Sundaram",
      mrn: "AV-2026-00508",
      wardBed: "SICU - Bed 02",
      prescribingDoctor: "Dr. Radhika Sen",
      antibioticName: "Colistin (Polymyxin E)",
      dosage: "9 Million IU Loading, then 4.5 MIU q12h IV",
      clinicalIndication: "Severe Septic Shock secondary to VAP with Pan-Drug Resistant Acinetobacter",
      procalcitoninLevel: "14.2 ng/mL (High Acuity Sepsis)",
      cultureReportStatus: "ISOLATE_IDENTIFIED",
      identifiedOrganism: "Acinetobacter baumannii (Only Colistin & Tigecycline sensitive)",
      creatinineClearance: "48 mL/min (Renally adjusted)",
      requestTimestamp: "01-Nov-2026 10:15",
      approvalStatus: "PENDING_REVIEW",
    },
    {
      id: "ASP-2026-302",
      patientName: "Gopal Kishan",
      mrn: "AV-2026-00412",
      wardBed: "MICU - Bed 04",
      prescribingDoctor: "Dr. Sameer Joshi",
      antibioticName: "Ceftazidime + Avibactam",
      dosage: "2.5g IV q8h over 2 hours",
      clinicalIndication: "CLABSI with Carbapenem-Resistant Enterobacterales (OXA-48 producer)",
      procalcitoninLevel: "8.6 ng/mL",
      cultureReportStatus: "ISOLATE_IDENTIFIED",
      identifiedOrganism: "Klebsiella pneumoniae (KPC/OXA-48 producer)",
      creatinineClearance: "62 mL/min",
      requestTimestamp: "01-Nov-2026 08:30",
      approvalStatus: "APPROVED_48H",
      idSpecialistNotes: "Approved for 48 hours empirical therapy. Repeat blood culture on Day 3.",
    },
    {
      id: "ASP-2026-303",
      patientName: "Sanjay Singhania",
      mrn: "AV-2026-00811",
      wardBed: "Neuro Ward - Bed 08",
      prescribingDoctor: "Dr. Rajesh Sharma",
      antibioticName: "Meropenem",
      dosage: "1g IV q8h",
      clinicalIndication: "Post-op pyrexia with elevated CRP, no focal infection site identified yet",
      procalcitoninLevel: "0.4 ng/mL (Low bacterial likelihood)",
      cultureReportStatus: "AWAITED",
      creatinineClearance: "85 mL/min",
      requestTimestamp: "01-Nov-2026 11:00",
      approvalStatus: "PENDING_REVIEW",
    },
  ]);

  // Antibiogram susceptibility percentages
  const antibiogramData = [
    { pathogen: "Klebsiella pneumoniae (n=240)", amikacin: 78, meropenem: 42, colistin: 96, cipro: 34, ceftazAvibactam: 88 },
    { pathogen: "Acinetobacter baumannii (n=180)", amikacin: 22, meropenem: 14, colistin: 94, cipro: 12, tigecycline: 72 },
    { pathogen: "Pseudomonas aeruginosa (n=195)", amikacin: 74, meropenem: 68, piperTazo: 71, cipro: 62, colistin: 98 },
    { pathogen: "Escherichia coli (n=410)", amikacin: 92, meropenem: 86, piperTazo: 79, cipro: 41, colistin: 99 },
    { pathogen: "Staphylococcus aureus (n=160)", oxacillin: 38, vancomycin: 100, linezolid: 100, daptomycin: 98, clindamycin: 52 },
    { pathogen: "Enterococcus faecium (n=90)", ampicillin: 18, vancomycin: 64, linezolid: 98, daptomycin: 96, teicoplanin: 66 },
  ];

  // Actions
  const handleApproveAsp = (id: string) => {
    setAspRequests((prev) =>
      prev.map((r) =>
        r.id === id
          ? {
              ...r,
              approvalStatus: "APPROVED_48H",
              idSpecialistNotes: "Authorized 48h therapy under ASP. Mandatory re-assessment upon 48h culture update.",
            }
          : r
      )
    );
  };

  const handleDeescalateAsp = (id: string) => {
    setAspRequests((prev) =>
      prev.map((r) =>
        r.id === id
          ? {
              ...r,
              approvalStatus: "DE_ESCALATED",
              idSpecialistNotes: "Culture reports sensitive to Cefoperazone-Sulbactam or Piperacillin-Tazobactam. Reserve antibiotic de-escalated.",
            }
          : r
      )
    );
  };

  const handlePrintHaiReport = (item: HaiSurveillanceCase) => {
    const reportHtml = `
      <div style="font-family: sans-serif; padding: 20px; color: #0f172a; max-width: 800px; margin: 0 auto; line-height: 1.4;">
        <div style="border-bottom: 2px solid #0f172a; padding-bottom: 12px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: flex-start;">
          <div>
            <h1 style="font-size: 18px; font-weight: 800; margin: 0; text-transform: uppercase;">${hospitalProfile.name}</h1>
            <p style="font-size: 11px; color: #475569; margin: 2px 0;">INFECTION PREVENTION & CONTROL COMMITTEE (HICC)</p>
            <p style="font-size: 10px; color: #64748b; margin: 0;">FORM HICC-04: STATUTORY HOSPITAL-ACQUIRED INFECTION (HAI) INCIDENT DOSSIER</p>
          </div>
          <div style="text-align: right;">
            <span style="display: inline-block; padding: 4px 8px; background: #fee2e2; color: #991b1b; font-size: 11px; font-weight: 700; border: 1px solid #f87171; border-radius: 4px;">
              SURVEILLANCE CONFIRMED
            </span>
            <p style="font-size: 10px; font-family: monospace; margin: 4px 0 0 0;">DOSSIER NO: ${item.id}</p>
          </div>
        </div>

        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; margin-bottom: 16px;">
          <h3 style="font-size: 12px; font-weight: 700; margin: 0 0 8px 0; color: #1e293b; text-transform: uppercase;">Patient Demographics & Clinical Location</h3>
          <table style="width: 100%; font-size: 11px; border-collapse: collapse;">
            <tr>
              <td style="padding: 4px 0; width: 25%; color: #64748b;">Patient Full Name:</td>
              <td style="padding: 4px 0; width: 25%; font-weight: 700;">${item.patientName}</td>
              <td style="padding: 4px 0; width: 25%; color: #64748b;">UHID / MRN:</td>
              <td style="padding: 4px 0; width: 25%; font-family: monospace; font-weight: 700;">${item.mrn}</td>
            </tr>
            <tr>
              <td style="padding: 4px 0; color: #64748b;">Age / Gender:</td>
              <td style="padding: 4px 0; font-weight: 600;">${item.ageGender}</td>
              <td style="padding: 4px 0; color: #64748b;">Current Ward & Bed:</td>
              <td style="padding: 4px 0; font-weight: 700; color: #0284c7;">${item.wardLocation}</td>
            </tr>
            <tr>
              <td style="padding: 4px 0; color: #64748b;">Attending Clinician:</td>
              <td style="padding: 4px 0; font-weight: 600;">${item.attendingPhysician}</td>
              <td style="padding: 4px 0; color: #64748b;">Incident Detection Date:</td>
              <td style="padding: 4px 0; font-family: monospace;">${item.detectionDate}</td>
            </tr>
          </table>
        </div>

        <div style="border: 1px solid #cbd5e1; border-radius: 6px; padding: 12px; margin-bottom: 16px;">
          <h3 style="font-size: 12px; font-weight: 700; margin: 0 0 8px 0; color: #991b1b; text-transform: uppercase;">Device & Microbiological Surveillance</h3>
          <table style="width: 100%; font-size: 11px; border-collapse: collapse;">
            <tr style="border-bottom: 1px solid #f1f5f9;">
              <td style="padding: 6px 0; color: #64748b;">Infection Classification:</td>
              <td style="padding: 6px 0; font-weight: 700; color: #dc2626;">${item.suspectedInfection} (${item.deviceType})</td>
              <td style="padding: 6px 0; color: #64748b;">In-Situ Device Dwell Days:</td>
              <td style="padding: 6px 0; font-weight: 700;">${item.deviceDays} Days</td>
            </tr>
            <tr style="border-bottom: 1px solid #f1f5f9;">
              <td style="padding: 6px 0; color: #64748b;">Isolated Pathogen:</td>
              <td style="padding: 6px 0; font-weight: 700; font-style: italic;">${item.isolatedPathogen || "Specimen culture awaited"}</td>
              <td style="padding: 6px 0; color: #64748b;">Resistance Classification:</td>
              <td style="padding: 6px 0; font-weight: 700; color: #b91c1c;">${item.mdrClassification || "Standard"}</td>
            </tr>
            <tr>
              <td style="padding: 6px 0; color: #64748b;">Infection Control Precautions:</td>
              <td colspan="3" style="padding: 6px 0; font-weight: 700; color: #0284c7;">
                ${item.isolationStatus} (Gown, Gloves, Dedicated Equipment, Strict Terminal Cleaning)
              </td>
            </tr>
          </table>
        </div>

        <div style="border: 1px solid #cbd5e1; border-radius: 6px; padding: 12px; margin-bottom: 24px; background: #fffbeb;">
          <h4 style="font-size: 11px; font-weight: 700; margin: 0 0 4px 0; color: #b45309; text-transform: uppercase;">Corrective & Preventive Action (CAPA) Directives</h4>
          <ul style="font-size: 10px; color: #78350f; margin: 0; padding-left: 18px; line-height: 1.5;">
            <li>Daily necessity review for device removal by Primary Treating Consultant.</li>
            <li>Infection Control Nurse (ICN) to audit barrier nursing compliance twice daily.</li>
            <li>Mandatory notification to State Health Authority NCDC portal within 24 hours under NABH Standards.</li>
            <li>Antimicrobial stewardship consultation required prior to escalation to Colistin / Polymyxin B.</li>
          </ul>
        </div>

        <div style="display: flex; justify-content: space-between; margin-top: 40px; padding-top: 16px; border-top: 1px dashed #94a3b8; font-size: 10px; color: #475569;">
          <div style="text-align: center; width: 30%;">
            <div style="border-bottom: 1px solid #0f172a; height: 35px; margin-bottom: 4px;"></div>
            <strong>Infection Control Nurse (ICN)</strong><br />
            Registration / ID: ICN-904
          </div>
          <div style="text-align: center; width: 30%;">
            <div style="border-bottom: 1px solid #0f172a; height: 35px; margin-bottom: 4px;"></div>
            <strong>Clinical Microbiologist</strong><br />
            HICC Secretary
          </div>
          <div style="text-align: center; width: 30%;">
            <div style="border-bottom: 1px solid #0f172a; height: 35px; margin-bottom: 4px;"></div>
            <strong>Medical Superintendent</strong><br />
            ${hospitalProfile.name}
          </div>
        </div>
      </div>
    `;

    const a4Printer = getPrinterForCategory("CLINICAL_A4");
    printDocument(reportHtml, {
      docType: "CLINICAL_SUMMARY",
      title: `HAI_Case_${item.id}_${item.mrn}`,
      printerDevice: a4Printer,
    });
  };

  const handlePrintIsolationPlacard = (item: HaiSurveillanceCase) => {
    const isContact = item.isolationStatus === "CONTACT_ISOLATION";
    const isAirborne = item.isolationStatus === "AIRBORNE";
    const headerColor = isContact ? "#dc2626" : isAirborne ? "#ca8a04" : "#0284c7";
    const headerBg = isContact ? "#fef2f2" : isAirborne ? "#fefce8" : "#f0f9ff";

    const placardHtml = `
      <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 750px; margin: 0 auto; border: 4px solid ${headerColor}; padding: 24px; text-align: center; background: #ffffff;">
        <div style="background: ${headerColor}; color: #ffffff; padding: 14px; border-radius: 6px; margin-bottom: 20px;">
          <h1 style="margin: 0; font-size: 28px; font-weight: 900; letter-spacing: 2px;">🛑 STOP! PRECAUTIONS REQUIRED</h1>
          <div style="font-size: 14px; font-weight: bold; margin-top: 4px; text-transform: uppercase;">
            ${hospitalProfile.name} • INFECTION PREVENTION & CONTROL (HICC)
          </div>
        </div>

        <div style="border: 2px dashed ${headerColor}; background: ${headerBg}; padding: 16px; border-radius: 8px; margin-bottom: 24px;">
          <div style="font-size: 22px; font-weight: 900; color: ${headerColor}; text-transform: uppercase; margin-bottom: 6px;">
            ${item.isolationStatus.replace(/_/g, " ")}
          </div>
          <div style="font-size: 14px; font-weight: bold; color: #1e293b;">
            LOCATION: ${item.wardLocation.toUpperCase()} • PATIENT: ${item.patientName.toUpperCase()} (${item.mrn})
          </div>
          ${item.mdrClassification ? `<div style="font-size: 12px; font-weight: bold; color: #b91c1c; margin-top: 4px; font-family: monospace;">TAG: ${item.mdrClassification} (${item.isolatedPathogen || "MDR Pathogen"})</div>` : ""}
        </div>

        <div style="text-align: left; margin-bottom: 24px;">
          <h3 style="font-size: 14px; font-weight: 800; color: #0f172a; border-bottom: 2px solid #0f172a; padding-bottom: 6px; text-transform: uppercase; margin-bottom: 12px;">
            MANDATORY PROTOCOL PRIOR TO ROOM ENTRY:
          </h3>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 12px;">
            <div style="border: 1px solid #cbd5e1; padding: 10px; border-radius: 6px;">
              <strong>1. HAND HYGIENE:</strong><br />
              Perform 6-step alcohol rub or soap & water wash before entering and immediately upon exiting.
            </div>
            <div style="border: 1px solid #cbd5e1; padding: 10px; border-radius: 6px;">
              <strong>2. PERSONAL PROTECTIVE EQUIPMENT:</strong><br />
              ${isContact ? "Wear clean disposable gown and non-sterile gloves for all patient / environmental contact." : isAirborne ? "Fit-tested N95 / FFP2 respirator mandatory before entering room." : "Surgical mask and eye shield mandatory within 2 meters."}
            </div>
            <div style="border: 1px solid #cbd5e1; padding: 10px; border-radius: 6px;">
              <strong>3. DEDICATED EQUIPMENT:</strong><br />
              Use dedicated stethoscope, BP cuff, and thermometer. Terminal bleach disinfection required before leaving.
            </div>
            <div style="border: 1px solid #cbd5e1; padding: 10px; border-radius: 6px;">
              <strong>4. VISITOR RESTRICTION:</strong><br />
              Visitors must report to Nursing Station before entering. Maximum 1 visitor with full barrier PPE.
            </div>
          </div>
        </div>

        <div style="display: flex; justify-content: space-between; border-top: 1px solid #e2e8f0; padding-top: 14px; font-size: 11px; color: #64748b;">
          <div><b>POSTED DATE:</b> ${item.detectionDate}</div>
          <div><b>AUTHORIZED BY:</b> Hospital Infection Control Officer</div>
          <div><b>FORM:</b> HICC-PL-02</div>
        </div>
      </div>
    `;

    const a4Printer = getPrinterForCategory("CLINICAL_A4");
    printDocument(placardHtml, {
      docType: "CLINICAL_SUMMARY",
      title: `Isolation_Placard_${item.wardLocation.replace(/[^a-zA-Z0-9]/g, "_")}`,
      printerDevice: a4Printer,
    });
  };

  const filteredCases = haiCases.filter((c) => {
    const matchesQuery =
      c.patientName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.mrn.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (c.isolatedPathogen && c.isolatedPathogen.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesDevice = deviceFilter === "ALL" || c.deviceType === deviceFilter;
    return matchesQuery && matchesDevice;
  });

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-slate-950 font-sans">
      {/* 1. Header Bar */}
      <div className="p-4 bg-slate-900 border-b border-slate-800 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-rose-400" />
              Infection Prevention & Control (HICC) & Antimicrobial Stewardship (ASP)
            </h1>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-950 text-rose-400 border border-rose-800 font-bold">
              NABH SURVEILLANCE
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Active device-associated HAI surveillance, reserve antibiotic approvals, and hospital cumulative antibiogram.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Tabs */}
          <div className="flex rounded-lg bg-slate-950 p-1 border border-slate-800 text-xs">
            <button
              onClick={() => setActiveTab("HAI_SURVEILLANCE")}
              className={`px-3 py-1.5 rounded-md font-semibold transition-all ${
                activeTab === "HAI_SURVEILLANCE"
                  ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              HAI Surveillance ({haiCases.filter((c) => c.status === "CONFIRMED_HAI").length})
            </button>
            <button
              onClick={() => setActiveTab("ASP_QUEUE")}
              className={`px-3 py-1.5 rounded-md font-semibold transition-all flex items-center gap-1.5 ${
                activeTab === "ASP_QUEUE"
                  ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <Pill size={12} />
              <span>ASP Approvals ({aspRequests.filter((r) => r.approvalStatus === "PENDING_REVIEW").length})</span>
            </button>
            <button
              onClick={() => setActiveTab("ANTIBIOGRAM")}
              className={`px-3 py-1.5 rounded-md font-semibold transition-all ${
                activeTab === "ANTIBIOGRAM"
                  ? "bg-sky-500/20 text-sky-300 border border-sky-500/40"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              Antibiogram
            </button>
            <button
              onClick={() => setActiveTab("HAND_HYGIENE")}
              className={`px-3 py-1.5 rounded-md font-semibold transition-all ${
                activeTab === "HAND_HYGIENE"
                  ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              Hand Hygiene
            </button>
          </div>
        </div>
      </div>

      {/* 2. Benchmark Surveillance KPI Ribbon */}
      <div className="p-4 border-b border-slate-800/80 bg-slate-900/40 grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="p-3 bg-slate-900 border-slate-800">
          <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider flex items-center justify-between">
            <span>CLABSI Rate</span>
            <span className="text-[9px] text-emerald-400 font-mono">Benchmark: &lt;1.5</span>
          </div>
          <div className="text-2xl font-black font-mono text-emerald-400 mt-1 flex items-baseline gap-2">
            <span>1.12</span>
            <span className="text-[10px] text-slate-400 font-normal">/ 1,000 line days</span>
          </div>
        </Card>

        <Card className="p-3 bg-slate-900 border-slate-800">
          <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider flex items-center justify-between">
            <span>CAUTI Rate</span>
            <span className="text-[9px] text-emerald-400 font-mono">Benchmark: &lt;2.0</span>
          </div>
          <div className="text-2xl font-black font-mono text-amber-400 mt-1 flex items-baseline gap-2">
            <span>1.84</span>
            <span className="text-[10px] text-slate-400 font-normal">/ 1,000 catheter days</span>
          </div>
        </Card>

        <Card className="p-3 bg-slate-900 border-slate-800">
          <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider flex items-center justify-between">
            <span>VAP Rate</span>
            <span className="text-[9px] text-emerald-400 font-mono">Benchmark: &lt;3.5</span>
          </div>
          <div className="text-2xl font-black font-mono text-emerald-400 mt-1 flex items-baseline gap-2">
            <span>2.40</span>
            <span className="text-[10px] text-slate-400 font-normal">/ 1,000 vent days</span>
          </div>
        </Card>

        <Card className="p-3 bg-slate-900 border-slate-800">
          <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider flex items-center justify-between">
            <span>Restricted Rx Pending</span>
            <span className="text-[9px] text-rose-400 font-mono">ASP Review</span>
          </div>
          <div className="text-2xl font-black font-mono text-rose-400 mt-1 flex items-baseline gap-2">
            <span>{aspRequests.filter((r) => r.approvalStatus === "PENDING_REVIEW").length}</span>
            <span className="text-[10px] text-slate-400 font-normal">Colistin / Meropenem</span>
          </div>
        </Card>
      </div>

      {/* 3. Main Body */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* TAB 1: HAI SURVEILLANCE */}
        {activeTab === "HAI_SURVEILLANCE" && (
          <div className="space-y-4">
            {/* Search and Filters */}
            <div className="flex items-center justify-between gap-3 bg-slate-900 p-3 rounded-xl border border-slate-800">
              <div className="flex items-center gap-2 flex-1 max-w-md">
                <Search size={15} className="text-slate-400" />
                <input
                  type="text"
                  placeholder="Filter by patient name, MRN, or organism..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="bg-transparent text-xs text-white placeholder-slate-500 focus:outline-none w-full"
                />
              </div>

              <div className="flex items-center gap-2 text-xs">
                <Filter size={13} className="text-slate-400" />
                <select
                  value={deviceFilter}
                  onChange={(e) => setDeviceFilter(e.target.value)}
                  className="bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-slate-200 focus:outline-none"
                >
                  <option value="ALL">All Device Types</option>
                  <option value="CENTRAL_LINE">Central Venous Line (CLABSI)</option>
                  <option value="VENTILATOR">Mechanical Ventilator (VAP)</option>
                  <option value="FOLEYS_CATHETER">Urinary Catheter (CAUTI)</option>
                  <option value="SURGICAL_WOUND">Surgical Wound (SSI)</option>
                </select>
              </div>
            </div>

            {/* HAI Case Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredCases.map((item) => (
                <Card
                  key={item.id}
                  className="p-4 bg-slate-900 border-slate-800 hover:border-slate-700 transition-all flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between text-xs mb-2 pb-2 border-b border-slate-800">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-rose-400 bg-rose-950/60 px-2 py-0.5 rounded border border-rose-800/80">
                          {item.id}
                        </span>
                        <Badge
                          variant={
                            item.status === "CONFIRMED_HAI"
                              ? "danger"
                              : item.status === "ACTIVE_SURVEILLANCE"
                              ? "warning"
                              : "success"
                          }
                        >
                          {item.status}
                        </Badge>
                      </div>
                      <span className="text-[10px] font-mono text-slate-400">
                        Detected: {item.detectionDate}
                      </span>
                    </div>

                    <div className="flex items-start justify-between">
                      <div>
                        <div className="text-base font-bold text-white">{item.patientName}</div>
                        <div className="text-xs text-slate-400 font-mono">
                          {item.ageGender} • UHID: {item.mrn} • Location: <strong className="text-sky-400">{item.wardLocation}</strong>
                        </div>
                      </div>
                      <Badge variant="purple" className="text-[10px]">
                        {item.isolationStatus}
                      </Badge>
                    </div>

                    <div className="mt-3 p-2.5 rounded-lg bg-slate-950 border border-slate-800/80 text-xs space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Suspected Infection:</span>
                        <span className="font-bold text-rose-400">{item.suspectedInfection} ({item.deviceType})</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Device In-Situ Duration:</span>
                        <span className="font-mono text-amber-300 font-semibold">{item.deviceDays} Days</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Isolated Pathogen:</span>
                        <span className="font-semibold italic text-slate-200">
                          {item.isolatedPathogen || "Pending Culture"}
                        </span>
                      </div>
                      {item.mdrClassification && (
                        <div className="flex items-center justify-between pt-1 border-t border-slate-800">
                          <span className="text-slate-400">Resistance Tag:</span>
                          <span className="font-mono font-black text-rose-400 bg-rose-950 px-1.5 py-0.2 rounded border border-rose-800">
                            {item.mdrClassification}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between">
                    <span className="text-[10px] text-slate-400 font-mono">
                      Consultant: {item.attendingPhysician}
                    </span>
                    <div className="flex items-center gap-2">
                      <Button
                        onClick={() => handlePrintIsolationPlacard(item)}
                        variant="outline"
                        className="text-xs py-1 px-2 flex items-center gap-1 border-amber-800 text-amber-300 bg-amber-950/40 hover:bg-amber-900/60 font-semibold"
                        title="Print Door / Bedside Isolation Precaution Placard"
                      >
                        <ShieldAlert size={12} /> Door Placard
                      </Button>
                      <Button
                        onClick={() => handlePrintHaiReport(item)}
                        variant="outline"
                        className="text-xs py-1 px-2.5 flex items-center gap-1.5 border-rose-800 text-rose-300 bg-rose-950/40 hover:bg-rose-900/60 font-semibold"
                      >
                        <Printer size={12} /> Dossier
                      </Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* TAB 2: ASP QUEUE */}
        {activeTab === "ASP_QUEUE" && (
          <div className="space-y-4">
            <div className="bg-amber-950/20 border border-amber-800/60 rounded-xl p-3 flex items-center justify-between text-xs text-amber-300">
              <div className="flex items-center gap-2">
                <AlertTriangle size={16} className="text-amber-400" />
                <span>
                  <strong>Antimicrobial Stewardship Mandatory Gate:</strong> Reserve antibiotics (Colistin, Meropenem, Ceftazidime-Avibactam) require clinical microbiologist / ID specialist sign-off before pharmacy fulfillment beyond initial 24h.
                </span>
              </div>
            </div>

            <div className="space-y-3">
              {aspRequests.map((req) => (
                <Card
                  key={req.id}
                  className="p-4 bg-slate-900 border-slate-800 hover:border-slate-700 transition-all"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-slate-800 mb-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-amber-400 bg-amber-950/80 px-2 py-0.5 rounded border border-amber-800 text-xs">
                        {req.id}
                      </span>
                      <span className="font-bold text-sm text-white">{req.patientName}</span>
                      <span className="text-xs font-mono text-slate-400">({req.mrn} • {req.wardBed})</span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Badge
                        variant={
                          req.approvalStatus === "APPROVED_48H"
                            ? "success"
                            : req.approvalStatus === "DE_ESCALATED"
                            ? "info"
                            : req.approvalStatus === "REJECTED"
                            ? "danger"
                            : "warning"
                        }
                      >
                        {req.approvalStatus}
                      </Badge>
                      <span className="text-[10px] font-mono text-slate-500">{req.requestTimestamp}</span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                    <div className="space-y-1.5 bg-slate-950 p-3 rounded-lg border border-slate-800">
                      <div>
                        <span className="text-slate-400">Requested Antibiotic:</span>{" "}
                        <strong className="text-rose-400 text-sm">{req.antibioticName}</strong>
                      </div>
                      <div>
                        <span className="text-slate-400">Dosing Regimen:</span>{" "}
                        <span className="font-mono text-slate-200">{req.dosage}</span>
                      </div>
                      <div>
                        <span className="text-slate-400">Indication:</span>{" "}
                        <span className="text-slate-300">{req.clinicalIndication}</span>
                      </div>
                      <div>
                        <span className="text-slate-400">Prescribing Clinician:</span>{" "}
                        <span className="font-semibold text-sky-400">{req.prescribingDoctor}</span>
                      </div>
                    </div>

                    <div className="space-y-1.5 bg-slate-950 p-3 rounded-lg border border-slate-800">
                      <div>
                        <span className="text-slate-400">Procalcitonin / Biomarker:</span>{" "}
                        <strong className="text-amber-400">{req.procalcitoninLevel}</strong>
                      </div>
                      <div>
                        <span className="text-slate-400">Culture Sensitivity:</span>{" "}
                        <span className="font-semibold text-slate-200">{req.cultureReportStatus}</span>
                        {req.identifiedOrganism && (
                          <div className="text-[11px] text-rose-300 italic mt-0.5">{req.identifiedOrganism}</div>
                        )}
                      </div>
                      <div>
                        <span className="text-slate-400">Renal Clearance:</span>{" "}
                        <span className="font-mono text-slate-300">{req.creatinineClearance}</span>
                      </div>
                      {req.idSpecialistNotes && (
                        <div className="pt-1.5 border-t border-slate-800 text-[11px] text-emerald-400">
                          <strong>ID Note:</strong> {req.idSpecialistNotes}
                        </div>
                      )}
                    </div>
                  </div>

                  {req.approvalStatus === "PENDING_REVIEW" && (
                    <div className="mt-3 pt-3 border-t border-slate-800 flex items-center justify-end gap-2">
                      <Button
                        onClick={() => handleDeescalateAsp(req.id)}
                        variant="outline"
                        className="text-xs py-1 px-3 border-sky-800 text-sky-300 hover:bg-sky-900/50"
                      >
                        Recommend De-escalation
                      </Button>
                      <Button
                        onClick={() => handleApproveAsp(req.id)}
                        className="text-xs py-1 px-3 bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-bold flex items-center gap-1"
                      >
                        <CheckCircle2 size={13} /> Approve 48h Course
                      </Button>
                    </div>
                  )}
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* TAB 3: ANTIBIOGRAM */}
        {activeTab === "ANTIBIOGRAM" && (
          <div className="space-y-4">
            <div className="bg-slate-900 p-4 rounded-xl border border-slate-800">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
                <div>
                  <h3 className="font-bold text-sm text-slate-100">
                    Cumulative Hospital Antibiogram (ICU & Inpatient Isolates - Past 6 Months)
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Percentage of isolates susceptible (%S) following CLSI M100 clinical breakpoints.
                  </p>
                </div>
                <Badge variant="info">CLSI / EUCAST 2026</Badge>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-800 bg-slate-950/60 text-slate-400 font-mono uppercase text-[10px]">
                      <th className="p-2.5">Organism Isolated</th>
                      <th className="p-2.5 text-center">Amikacin</th>
                      <th className="p-2.5 text-center">Meropenem</th>
                      <th className="p-2.5 text-center">Colistin</th>
                      <th className="p-2.5 text-center">Ciprofloxacin</th>
                      <th className="p-2.5 text-center">Reserve / Others</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {antibiogramData.map((row, idx) => (
                      <tr key={idx} className="hover:bg-slate-800/40 transition-colors">
                        <td className="p-2.5 font-semibold text-slate-200">{row.pathogen}</td>
                        <td className="p-2.5 text-center font-mono">
                          <span
                            className={`px-2 py-0.5 rounded font-bold ${
                              (row.amikacin ?? 0) >= 80
                                ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                                : (row.amikacin ?? 0) >= 50
                                ? "bg-amber-950 text-amber-400 border border-amber-800"
                                : "bg-rose-950 text-rose-400 border border-rose-800"
                            }`}
                          >
                            {row.amikacin !== undefined ? `${row.amikacin}%` : "-"}
                          </span>
                        </td>
                        <td className="p-2.5 text-center font-mono">
                          <span
                            className={`px-2 py-0.5 rounded font-bold ${
                              (row.meropenem ?? 0) >= 80
                                ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                                : (row.meropenem ?? 0) >= 50
                                ? "bg-amber-950 text-amber-400 border border-amber-800"
                                : "bg-rose-950 text-rose-400 border border-rose-800"
                            }`}
                          >
                            {row.meropenem !== undefined ? `${row.meropenem}%` : "-"}
                          </span>
                        </td>
                        <td className="p-2.5 text-center font-mono">
                          <span
                            className={`px-2 py-0.5 rounded font-bold ${
                              (row.colistin ?? 0) >= 80
                                ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                                : "bg-amber-950 text-amber-400 border border-amber-800"
                            }`}
                          >
                            {row.colistin !== undefined ? `${row.colistin}%` : "-"}
                          </span>
                        </td>
                        <td className="p-2.5 text-center font-mono">
                          <span
                            className={`px-2 py-0.5 rounded font-bold ${
                              (row.cipro ?? 0) >= 80
                                ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                                : (row.cipro ?? 0) >= 50
                                ? "bg-amber-950 text-amber-400 border border-amber-800"
                                : "bg-rose-950 text-rose-400 border border-rose-800"
                            }`}
                          >
                            {row.cipro !== undefined ? `${row.cipro}%` : "-"}
                          </span>
                        </td>
                        <td className="p-2.5 text-center font-mono text-slate-300">
                          {row.ceftazAvibactam && (
                            <span className="text-emerald-400 font-bold">CAZ-AVI: {row.ceftazAvibactam}%</span>
                          )}
                          {row.tigecycline && (
                            <span className="text-amber-400 font-bold">TGC: {row.tigecycline}%</span>
                          )}
                          {row.vancomycin && (
                            <span className="text-emerald-400 font-bold">VAN: {row.vancomycin}%</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: HAND HYGIENE */}
        {activeTab === "HAND_HYGIENE" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card className="p-4 bg-slate-900 border-slate-800">
              <h3 className="font-bold text-sm text-slate-100 mb-3 flex items-center gap-2">
                <Sparkles size={16} className="text-emerald-400" />
                WHO 5 Moments Compliance by High-Risk Care Units
              </h3>
              <div className="space-y-3">
                {[
                  { ward: "Neonatal ICU (NICU)", compliance: 96, audits: 120 },
                  { ward: "Surgical ICU (SICU)", compliance: 92, audits: 140 },
                  { ward: "Medical ICU (MICU)", compliance: 88, audits: 155 },
                  { ward: "Operating Theatres (OT Suite)", compliance: 98, audits: 210 },
                  { ward: "Emergency Resuscitation", compliance: 84, audits: 95 },
                ].map((unit, i) => (
                  <div key={i} className="bg-slate-950 p-2.5 rounded-lg border border-slate-800 text-xs">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-slate-200">{unit.ward}</span>
                      <span className="font-mono font-bold text-emerald-400">{unit.compliance}%</span>
                    </div>
                    <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                      <div
                        className="bg-emerald-500 h-full rounded-full transition-all"
                        style={{ width: `${unit.compliance}%` }}
                      />
                    </div>
                    <div className="text-[10px] text-slate-500 mt-1">{unit.audits} unannounced observation audits</div>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="p-4 bg-slate-900 border-slate-800 flex flex-col justify-between">
              <div>
                <h3 className="font-bold text-sm text-slate-100 mb-3">Audit Protocol & Standards</h3>
                <div className="text-xs text-slate-300 space-y-2 leading-relaxed">
                  <p>
                    • Audits conducted using validated WHO Hand Hygiene Observation Tool by certified Infection Control Link Nurses.
                  </p>
                  <p>
                    • Focus on high-risk moments: <strong>Moment 1</strong> (Before touching patient) and <strong>Moment 2</strong> (Before clean/aseptic procedure).
                  </p>
                  <p>
                    • Units with compliance below 85% undergo mandatory simulation re-training within 72 hours.
                  </p>
                </div>
              </div>
              <div className="pt-3 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
                <span>NABH 5th Edition Standard HIC 4</span>
                <Badge variant="success">PASS</Badge>
              </div>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
};
