import React, { useState, useEffect } from "react";
import {
  User,
  Clock,
  Activity,
  FileText,
  Pill,
  CreditCard,
  ShieldCheck,
  AlertTriangle,
  Search,
  Stethoscope,
  Heart,
  Printer,
  FileCheck,
  RotateCcw,
  CheckCircle2,
  Sparkles,
  AlertCircle,
  RefreshCw,
} from "lucide-react";
import { useActivePatient } from "../../core/context/ActivePatientContext";
import { useHospitalConfig } from "../../core/context/HospitalConfigContext";
import { printDocument } from "../../utils/printDocument";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { uiApi } from "../../api/uiApi";
import { PatientTimelineEvent, RevisitEligibility } from "../../types";

type PatientRecordTab =
  | "overview"
  | "timeline"
  | "clinical"
  | "vitals"
  | "medications"
  | "orders"
  | "billing"
  | "consents";

export const PatientRecordWorkspace: React.FC = () => {
  const { patientSummary: activePatient } = useActivePatient();
  const { doctors, policies, hospitalProfile, printTemplates, getPrinterForCategory } = useHospitalConfig();
  const [activeTab, setActiveTab] = useState<PatientRecordTab>("overview");
  const [timelineFilter, setTimelineFilter] = useState<"ALL" | "CLINICAL" | "LAB" | "MED" | "BILLING">("ALL");
  const [bookedRevisitDoctor, setBookedRevisitDoctor] = useState<string | null>(null);
  const [revisitPolicyNotice, setRevisitPolicyNotice] = useState<string | null>(null);

  // Live timeline & doctor-specific revisit eligibility from backend
  const [liveTimeline, setLiveTimeline] = useState<PatientTimelineEvent[] | null>(null);
  const [loadingTimeline, setLoadingTimeline] = useState<boolean>(false);
  const [liveRevisitMap, setLiveRevisitMap] = useState<Record<string, RevisitEligibility>>({});

  const refreshTimeline = () => {
    if (!activePatient?.patient_id) return;
    setLoadingTimeline(true);
    uiApi
      .getPatientTimeline(activePatient.patient_id)
      .then((events) => {
        if (Array.isArray(events) && events.length > 0) {
          setLiveTimeline(events);
        }
      })
      .catch((err) => {
        console.warn("Could not fetch live patient timeline, using fallback", err);
      })
      .finally(() => {
        setLoadingTimeline(false);
      });
  };

  useEffect(() => {
    if (!activePatient?.patient_id) return;
    let isCurrent = true;
    setLoadingTimeline(true);

    uiApi
      .getPatientTimeline(activePatient.patient_id)
      .then((events) => {
        if (isCurrent && Array.isArray(events) && events.length > 0) {
          setLiveTimeline(events);
        }
      })
      .catch((err) => {
        console.warn("Could not fetch live patient timeline, using fallback", err);
      })
      .finally(() => {
        if (isCurrent) setLoadingTimeline(false);
      });

    // Check doctor-specific revisit eligibility with backend for common attending doctors
    [1, 2, 3].forEach((docNum) => {
      uiApi
        .getRevisitEligibility(activePatient.patient_id, docNum)
        .then((resp) => {
          if (isCurrent && resp) {
            setLiveRevisitMap((prev) => ({ ...prev, [`doc-${docNum}`]: resp }));
          }
        })
        .catch(() => {
          // Keep local calculation fallback
        });
    });

    return () => {
      isCurrent = false;
    };
  }, [activePatient?.patient_id]);

  if (!activePatient) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-slate-950">
        <div className="w-16 h-16 rounded-2xl bg-sky-950/60 border border-sky-800 flex items-center justify-center text-sky-400 mb-4 shadow-xl">
          <User size={32} />
        </div>
        <h2 className="text-xl font-bold text-slate-100 mb-2">No Active Patient Selected</h2>
        <p className="text-sm text-slate-400 max-w-md mb-6">
          Search the Master Patient Index (MPI) using <kbd className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-sky-400 text-xs font-mono font-bold">Cmd+K</kbd> to load a patient record, or register a new patient intake.
        </p>
        <div className="flex gap-3">
          <Button
            onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }))}
            className="flex items-center gap-2 bg-sky-600 hover:bg-sky-500 text-slate-950 font-bold"
          >
            <Search size={16} />
            <span>Search Patient MPI (Cmd+K)</span>
          </Button>
        </div>
      </div>
    );
  }

  // Doctor-Specific Revisit & Follow-up Status Tracking
  const getFreeWindow = (docId: string, fallbackDays: number) => {
    const doc = doctors.find((d) => d.id === docId);
    return policies.allowDoctorSpecificRevisitRules
      ? (doc?.revisitFreeWindowDays || fallbackDays)
      : (policies.defaultRevisitFreeDays || fallbackDays);
  };

  const doc1Window = getFreeWindow("doc-1", 7);
  const doc2Window = getFreeWindow("doc-2", 10);
  const doc3Window = getFreeWindow("doc-3", 14);

  const baseDoctorRevisitRecords = [
    {
      doctorId: "doc-1",
      numericId: 1,
      doctorName: "Dr. Vikram Seth",
      specialty: "Interventional Cardiology",
      lastVisitDate: "28-Oct-2026",
      daysElapsed: 4,
      freeWindowDays: doc1Window,
      maxFreeVisits: doctors.find((d) => d.id === "doc-1")?.revisitMaxFreeVisits || 1,
      standardFee: doctors.find((d) => d.id === "doc-1")?.consultationFee || 800,
      isFreeRevisitEligible: 4 <= doc1Window,
      daysRemaining: Math.max(0, doc1Window - 4),
      policySummary: "Within 7-day grace window. ₹800 fee waived.",
    },
    {
      doctorId: "doc-2",
      numericId: 2,
      doctorName: "Dr. Rajesh Sharma",
      specialty: "Internal Medicine",
      lastVisitDate: "14-Oct-2026",
      daysElapsed: 18,
      freeWindowDays: doc2Window,
      maxFreeVisits: doctors.find((d) => d.id === "doc-2")?.revisitMaxFreeVisits || 1,
      standardFee: doctors.find((d) => d.id === "doc-2")?.consultationFee || 500,
      isFreeRevisitEligible: 18 <= doc2Window,
      daysRemaining: Math.max(0, doc2Window - 18),
      policySummary: "Grace window expired. Follow-up fee applies.",
    },
    {
      doctorId: "doc-3",
      numericId: 3,
      doctorName: "Dr. Radhika Sen",
      specialty: "General Surgery",
      lastVisitDate: "20-Oct-2026",
      daysElapsed: 12,
      freeWindowDays: doc3Window,
      maxFreeVisits: doctors.find((d) => d.id === "doc-3")?.revisitMaxFreeVisits || 2,
      standardFee: doctors.find((d) => d.id === "doc-3")?.consultationFee || 800,
      isFreeRevisitEligible: 12 <= doc3Window,
      daysRemaining: Math.max(0, doc3Window - 12),
      policySummary: "Within surgical follow-up grace window. ₹800 fee waived.",
    },
  ];

  const doctorRevisitRecords = baseDoctorRevisitRecords.map((rec) => {
    const live = liveRevisitMap[rec.doctorId];
    if (!live) return rec;
    return {
      ...rec,
      isFreeRevisitEligible: live.is_free_revisit,
      daysElapsed: live.revisit_day_elapsed,
      daysRemaining: live.days_remaining,
      freeWindowDays: live.grace_period_days,
      standardFee: live.standard_fee_rupees,
      policySummary: live.policy_summary,
      lastVisitDate: live.last_consultation_date || rec.lastVisitDate,
    };
  });

  const handlePrintWristband = () => {
    const template = printTemplates.wristband;
    const printerDevice = getPrinterForCategory("WRISTBAND");
    const html = `
      <div class="wristband-slip">
        <div>
          <div class="bold" style="font-size: 11px;">${(template.hospitalName || hospitalProfile.name).toUpperCase()}</div>
          <div class="bold" style="font-size: 13px; margin-top: 2px;">${activePatient.full_name.toUpperCase()}</div>
          <div style="font-size: 9px;">${activePatient.gender} ${template.showBloodGroup && activePatient.blood_group ? `• Blood: ${activePatient.blood_group}` : ""}</div>
          ${template.showEmergencyPhone && activePatient.phone_number ? `<div style="font-size: 8px;">Ph: ${activePatient.phone_number}</div>` : ""}
          ${template.showAllergyWarning ? `<div class="allergy-tag" style="margin-top: 2px;">ALLERGIES: PENICILLIN G</div>` : ""}
        </div>
        <div class="center">
          <div class="barcode-box">||||| | |||| || ||| | |||</div>
          <div class="bold" style="font-size: 12px;">${activePatient.mrn}</div>
        </div>
      </div>
    `;
    printDocument(html, {
      title: `Wristband_${activePatient.mrn}`,
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

  const handlePrintChartSummary = () => {
    const html = `
      <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 720px; margin: 0 auto; border: 1px solid #333; padding: 24px;">
        <div style="text-align: center; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 14px;">
          <h2 style="margin: 0; font-size: 18px; text-transform: uppercase;">${hospitalProfile.name}</h2>
          <div style="font-size: 11px; font-weight: bold; color: #555;">PATIENT 360 COMPREHENSIVE CLINICAL CHART</div>
          <div style="font-size: 10px; color: #777;">${hospitalProfile.accreditation} • Phone: ${hospitalProfile.phone}</div>
        </div>
        <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #ddd; padding-bottom: 8px; font-size: 12px; margin-bottom: 12px;">
          <div><b>Patient:</b> ${activePatient.full_name} (${activePatient.gender} • ${activePatient.age_years || 42}y)</div>
          <div><b>UHID:</b> ${activePatient.mrn}</div>
          <div><b>Blood Group:</b> ${activePatient.blood_group || "O+"}</div>
        </div>
        <div style="margin-bottom: 12px; font-size: 12px;">
          <b>Active Problem List (ICD-10):</b>
          <div style="padding: 6px 0;">1. Angina pectoris (I20.9) • 2. Essential hypertension (I10)</div>
        </div>
        <div style="margin-bottom: 12px; font-size: 12px;">
          <b>Hemodynamics Baseline:</b>
          <div style="padding: 6px 0;">BP: 148/92 mmHg • HR: 88 bpm • SpO2: 97% • NEWS2 Score: 1 (Low Risk)</div>
        </div>
        <div style="margin-bottom: 12px; font-size: 12px;">
          <b>Critical Allergies:</b>
          <div style="color: red; font-weight: bold;">Severe Penicillin Anaphylaxis • Sulfa Drugs</div>
        </div>
        <div style="margin-top: 30px; font-size: 11px; border-top: 1px solid #ccc; padding-top: 8px; display: flex; justify-content: space-between;">
          <div>Generated on: ${new Date().toLocaleString()}</div>
          <div>Avinya Clinical OS Record</div>
        </div>
      </div>
    `;
    const a4Printer = getPrinterForCategory("CLINICAL_A4");
    printDocument(html, {
      title: `Chart_Summary_${activePatient.mrn}`,
      docType: "CLINICAL_SUMMARY",
      printerDevice: a4Printer,
    });
  };

  const handlePrintConsentCertificate = () => {
    if (!activePatient) return;
    const a4Printer = getPrinterForCategory("CLINICAL_A4");
    const html = `
      <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 700px; margin: 0 auto; border: 2px solid #000; padding: 24px;">
        <div style="text-align: center; border-bottom: 2px solid #000; padding-bottom: 12px; margin-bottom: 16px;">
          <h2 style="margin: 0; font-size: 20px; text-transform: uppercase;">${hospitalProfile.name}</h2>
          <div style="font-size: 12px; font-weight: bold; color: #0284c7; margin-top: 2px;">
            STATUTORY DATA PRINCIPAL CONSENT & PRIVACY DISCLOSURE CERTIFICATE
          </div>
          <div style="font-size: 10px; color: #555;">Issued under Section 6 of India Digital Personal Data Protection (DPDP) Act 2023 • Form DPDP-CERT-01</div>
        </div>

        <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #ccc; padding-bottom: 8px; font-size: 12px; margin-bottom: 14px;">
          <div><b>Data Principal (Patient):</b> ${activePatient.full_name.toUpperCase()}</div>
          <div><b>UHID / MRN:</b> ${activePatient.mrn}</div>
          <div><b>Age / Gender:</b> ${activePatient.age_years}Y / ${activePatient.gender}</div>
          <div><b>Date:</b> ${new Date().toLocaleDateString()}</div>
        </div>

        <div style="border: 1px solid #cbd5e1; background: #f8fafc; padding: 12px; border-radius: 6px; margin-bottom: 16px; font-size: 11px;">
          <h4 style="margin: 0 0 8px 0; font-size: 12px; text-transform: uppercase; color: #0f172a;">Purpose-Specific Consent Audit Register:</h4>
          <table style="width: 100%; border-collapse: collapse; font-size: 11px;">
            <thead>
              <tr style="border-bottom: 1px solid #cbd5e1; text-align: left; background: #e2e8f0;">
                <th style="padding: 6px;">Processing Purpose</th>
                <th style="padding: 6px; text-align: center;">Status</th>
                <th style="padding: 6px; text-align: center;">Recorded Date</th>
              </tr>
            </thead>
            <tbody>
              <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 6px;">Routine Clinical Consultation & Diagnostics</td>
                <td style="padding: 6px; text-align: center; font-weight: bold; color: #16a34a;">GRANTED</td>
                <td style="padding: 6px; text-align: center;">01-Nov-2026</td>
              </tr>
              <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 6px;">Inpatient Hospital Care & Nursing Administration</td>
                <td style="padding: 6px; text-align: center; font-weight: bold; color: #16a34a;">GRANTED</td>
                <td style="padding: 6px; text-align: center;">01-Nov-2026</td>
              </tr>
              <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 6px;">TPA Insurance Cashless Claim Adjudication</td>
                <td style="padding: 6px; text-align: center; font-weight: bold; color: #16a34a;">GRANTED</td>
                <td style="padding: 6px; text-align: center;">01-Nov-2026</td>
              </tr>
              <tr>
                <td style="padding: 6px;">Anonymized Medical Research & Academic Studies</td>
                <td style="padding: 6px; text-align: center; font-weight: bold; color: #dc2626;">REFUSED</td>
                <td style="padding: 6px; text-align: center;">01-Nov-2026</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div style="background: #f1f5f9; border: 1px solid #cbd5e1; padding: 10px; border-radius: 6px; font-family: monospace; font-size: 10px; margin-bottom: 16px;">
          <div><b>Cryptographic SHA-256 Consent Hash:</b> e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855</div>
          <div><b>Consent Notice Version:</b> DPDP-NOTIF-v2.1 • Storage: Immutable Hospital Vault</div>
        </div>

        <div style="font-size: 10px; color: #475569; line-height: 1.5; margin-bottom: 24px;">
          <b>Data Principal Rights Notice:</b> As per Chapter III of the DPDP Act 2023, the data principal reserves the right to access, correct, update, or withdraw consent at any time via the Hospital Data Protection Officer (DPO) at <u>dpo@${hospitalProfile.subdomain || "hospital"}.in</u>.
        </div>

        <div style="display: flex; justify-content: space-between; margin-top: 50px; font-size: 11px;">
          <div style="border-top: 1px solid #000; width: 220px; text-align: center; padding-top: 4px;">Data Protection Officer (DPO)</div>
          <div style="border-top: 1px solid #000; width: 220px; text-align: center; padding-top: 4px;">Medical Records Officer / Registrar</div>
        </div>
      </div>
    `;

    printDocument(html, {
      title: `DPDP_Consent_Cert_${activePatient.mrn}`,
      docType: "CLINICAL_SUMMARY",
      printerDevice: a4Printer,
    });
  };

  // Sample structured timeline data for active patient with revisit tagging
  const sampleTimelineEvents = [
    {
      id: "ev-1",
      timestamp: "Today, 09:02",
      type: "REGISTRATION",
      category: "CLINICAL",
      title: "Outpatient Intake & Registration",
      actor: "Priya Nair (Front Desk)",
      details: "UHID issued: " + activePatient.mrn + " | Fast-track token CARDIO-14 issued. OPD registration fee ₹800 collected via UPI.",
      icon: User,
      color: "sky",
    },
    {
      id: "ev-2",
      timestamp: "Today, 09:18",
      type: "TRIAGE",
      category: "CLINICAL",
      title: "Nursing Triage & Vitals Recorded",
      actor: "Sister Anjali (RN)",
      details: "BP: 148/92 mmHg | HR: 88 bpm | SpO2: 97% | Temp: 98.4°F | Calculated NEWS2 Score: 1 (Low Risk).",
      icon: Activity,
      color: "emerald",
    },
    {
      id: "ev-3",
      timestamp: "Today, 09:42",
      type: "CONSULTATION",
      category: "CLINICAL",
      title: "Doctor SOAP Consultation",
      actor: "Dr. Ramesh Gupta (Cardiology)",
      details: "Chief Complaint: Exertional chest tightness. Assigned ICD-10 diagnosis: I20.9 (Angina pectoris, unspecified).",
      icon: Stethoscope,
      color: "sky",
    },
    {
      id: "ev-4",
      timestamp: "Today, 09:50",
      type: "CPOE_ORDER",
      category: "LAB",
      title: "CPOE Diagnostic Orders Placed",
      actor: "Dr. Ramesh Gupta",
      details: "Orders: 1. STAT 12-Lead ECG  2. High-Sensitivity Serum Troponin-I  3. Complete Blood Count (CBC).",
      icon: FileText,
      color: "indigo",
    },
    {
      id: "ev-5",
      timestamp: "Today, 10:28",
      type: "LAB_RESULT",
      category: "LAB",
      title: "Critical Lab Result & Panic Delta Check",
      actor: "Central Diagnostic Pathology",
      details: "Serum Troponin-I: 0.12 ng/mL (CRITICAL HIGH, ref < 0.04). Delta: 300% elevation over baseline. Telephone read-back logged with Dr. Gupta.",
      icon: AlertTriangle,
      color: "rose",
    },
    {
      id: "ev-6",
      timestamp: "Today, 10:35",
      type: "ADMISSION",
      category: "CLINICAL",
      title: "Urgent CCU Admission Ordered",
      actor: "Dr. Ramesh Gupta",
      details: "Patient scheduled for admission to Coronary Care Unit (CCU). Bed CCU-204 allocated. TPA Pre-auth initiated.",
      icon: Heart,
      color: "amber",
    },
  ];

  const getTimelineCategory = (cat: string): "CLINICAL" | "LAB" | "MED" | "BILLING" => {
    const c = (cat || "").toUpperCase();
    if (c === "LAB" || c === "DIAGNOSTIC") return "LAB";
    if (c === "MEDICATION" || c === "PHARMACY") return "MED";
    if (c === "BILLING" || c === "PAYMENT") return "BILLING";
    return "CLINICAL";
  };

  const getTimelineIcon = (cat: string) => {
    const c = (cat || "").toUpperCase();
    if (c === "REGISTRATION") return User;
    if (c === "TRIAGE") return Activity;
    if (c === "CLINICAL" || c === "CONSULTATION") return Stethoscope;
    if (c === "LAB" || c === "DIAGNOSTIC") return FileText;
    if (c === "MEDICATION" || c === "PHARMACY") return Pill;
    if (c === "BILLING") return CreditCard;
    if (c === "ADMISSION") return Heart;
    return Activity;
  };

  const effectiveTimeline = liveTimeline && liveTimeline.length > 0
    ? liveTimeline.map((ev) => ({
        id: ev.id,
        timestamp: `${ev.date} ${ev.time}`,
        type: ev.category,
        category: getTimelineCategory(ev.category),
        title: ev.title,
        actor: ev.doctor_name || ev.department || "Hospital Staff",
        details: ev.subtitle || (ev.details && Object.keys(ev.details).length > 0 ? Object.entries(ev.details).map(([k, v]) => `${k}: ${v}`).join(" • ") : "Event logged in electronic medical record."),
        icon: getTimelineIcon(ev.category),
        color: ev.severity === "CRITICAL" ? "rose" : ev.category === "TRIAGE" ? "emerald" : "sky",
      }))
    : sampleTimelineEvents;

  const filteredEvents = effectiveTimeline.filter(
    (ev) => timelineFilter === "ALL" || ev.category === timelineFilter
  );

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-slate-950">
      {/* 1. Patient Record Master Header */}
      <div className="p-4 bg-slate-900 border-b border-slate-800 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-sky-500 to-indigo-600 flex items-center justify-center text-slate-950 font-black text-lg shadow-md shadow-sky-500/20">
            {activePatient.full_name.charAt(0)}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-slate-100">{activePatient.full_name}</h1>
              <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-800 text-sky-400 font-bold border border-slate-700">
                {activePatient.mrn}
              </span>
              {activePatient.blood_group && (
                <span className="text-xs px-1.5 py-0.5 rounded bg-rose-950/80 text-rose-300 border border-rose-800 font-bold">
                  {activePatient.blood_group}
                </span>
              )}
            </div>
            <div className="text-xs text-slate-400 flex items-center gap-3 mt-0.5">
              <span>{activePatient.age_years || 42}y / {activePatient.gender}</span>
              <span>•</span>
              <span className="font-mono">{activePatient.phone_number || "+91 98123 04918"}</span>
              <span>•</span>
              <span className="text-emerald-400 flex items-center gap-1 font-mono text-[11px]">
                <ShieldCheck size={12} /> ABHA: 91-4829-1029-41
              </span>
            </div>
          </div>
        </div>

        {/* Quick Action Tools */}
        <div className="flex items-center gap-2">
          <Button
            onClick={handlePrintWristband}
            variant="outline"
            className="flex items-center gap-1.5 text-xs text-slate-300 border-slate-700"
          >
            <Printer size={14} />
            <span>Print Wristband</span>
          </Button>
          <Button
            onClick={handlePrintChartSummary}
            variant="outline"
            className="flex items-center gap-1.5 text-xs text-slate-300 border-slate-700"
          >
            <FileCheck size={14} />
            <span>Chart Summary</span>
          </Button>
        </div>
      </div>

      {/* 2. Navigation Tabs */}
      <div className="bg-slate-900/60 border-b border-slate-800 px-4 flex space-x-1 overflow-x-auto text-xs font-semibold">
        {[
          { id: "overview", label: "Patient 360 Overview", icon: User },
          { id: "timeline", label: "Longitudinal Timeline", icon: Clock },
          { id: "clinical", label: "Problem List & Diagnoses", icon: Stethoscope },
          { id: "vitals", label: "Vitals & Hemodynamics", icon: Activity },
          { id: "medications", label: "Active Medications", icon: Pill },
          { id: "orders", label: "CPOE Diagnostic Orders", icon: FileText },
          { id: "billing", label: "Folio & Insurance Ledger", icon: CreditCard },
          { id: "consents", label: "DPDP Consents & Rights", icon: ShieldCheck },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as PatientRecordTab)}
              className={`flex items-center gap-2 py-3 px-3.5 border-b-2 transition-all whitespace-nowrap ${
                isActive
                  ? "border-sky-400 text-sky-400 font-bold bg-sky-950/20"
                  : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"
              }`}
            >
              <Icon size={14} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* 3. Tab Content Area */}
      <div className="flex-1 overflow-y-auto p-4 lg:p-6 space-y-6">
        {/* TAB 1: PATIENT 360 OVERVIEW (INTEGRATED CLINICAL SNAPSHOT + LONGITUDINAL TIMELINE) */}
        {activeTab === "overview" && (
          <div className="space-y-6 max-w-7xl mx-auto">
            {/* Active Clinical Alert Strip */}
            <div className="p-3.5 rounded-xl bg-amber-950/40 border border-amber-800/80 text-amber-200 text-xs flex items-center justify-between shadow-lg">
              <div className="flex items-center gap-2.5">
                <AlertTriangle size={18} className="text-amber-400 shrink-0" />
                <span>
                  <strong>CRITICAL PATIENT SAFETY ALERT:</strong> Severe Penicillin Anaphylaxis documented. Fall risk assessed as HIGH. Full Code resuscitation active.
                </span>
              </div>
              <Badge variant="warning" className="uppercase font-mono text-[10px]">
                Safety Gate Active
              </Badge>
            </div>

            {/* Doctor-Tied Revisit & Free Follow-up Tracking Radar */}
            <Card className="p-4 bg-slate-900 border-slate-800 space-y-3">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <div>
                  <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                    <RotateCcw size={14} className="text-purple-400" /> Doctor Revisit &amp; Follow-up Policy Tracking
                  </h3>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Hospital Revisit Policy: Treating doctors configure individual free follow-up windows. Consultations within limit are 100% free.
                  </p>
                </div>
                <Badge variant="purple" className="text-[10px] font-mono">
                  Doctor-Specific Rules Active
                </Badge>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {doctorRevisitRecords.map((rec) => (
                  <div
                    key={rec.doctorId}
                    className={`p-3 rounded-xl border flex flex-col justify-between transition-all ${
                      rec.isFreeRevisitEligible
                        ? "bg-purple-950/20 border-purple-800/60 ring-1 ring-purple-500/20"
                        : "bg-slate-950/60 border-slate-800/80 opacity-80"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-bold text-xs text-slate-100">{rec.doctorName}</span>
                        <span className="text-[10px] font-mono text-slate-400">{rec.specialty}</span>
                      </div>
                      <div className="text-[11px] text-slate-400 mb-2">
                        Last Consultation: <span className="text-slate-200 font-mono">{rec.lastVisitDate}</span> ({rec.daysElapsed} days ago)
                      </div>

                      {rec.isFreeRevisitEligible ? (
                        <div className="p-2 rounded bg-purple-900/30 border border-purple-700/50 text-[11px] space-y-1">
                          <div className="flex items-center gap-1 text-emerald-400 font-bold">
                            <Sparkles size={12} /> Free Revisit Eligible ({rec.daysRemaining} days left)
                          </div>
                          <div className="text-slate-300 text-[10px]">
                            Window: {rec.freeWindowDays} days • Fee: <span className="line-through text-slate-500 font-mono">₹{rec.standardFee}</span> <span className="text-emerald-400 font-bold font-mono">₹0.00 (100% Free)</span>
                          </div>
                        </div>
                      ) : (
                        <div className="p-2 rounded bg-slate-900/60 border border-slate-800 text-[11px] space-y-1">
                          <div className="flex items-center gap-1 text-rose-400 font-semibold">
                            <AlertCircle size={12} /> Revisit Window Expired
                          </div>
                          <div className="text-slate-400 text-[10px]">
                            Window was {rec.freeWindowDays} days • Next consult: <span className="text-slate-200 font-bold font-mono">₹{rec.standardFee}.00</span>
                          </div>
                        </div>
                      )}
                    </div>

                    <div className="mt-3 pt-2 border-t border-slate-800/60 flex items-center justify-between">
                      {rec.isFreeRevisitEligible ? (
                        <Button
                          size="sm"
                          variant="primary"
                          onClick={() => {
                            setBookedRevisitDoctor(rec.doctorName);
                            setRevisitPolicyNotice(rec.policySummary);
                            setTimeout(() => {
                              setBookedRevisitDoctor(null);
                              setRevisitPolicyNotice(null);
                            }, 4000);
                          }}
                          className="w-full text-xs bg-emerald-600 hover:bg-emerald-500 text-white font-bold flex items-center justify-center gap-1"
                        >
                          <Sparkles size={12} /> Issue Free Revisit Token (₹0)
                        </Button>
                      ) : (
                        <Button
                          size="sm"
                          variant="outline"
                          className="w-full text-xs text-slate-300 border-slate-700 hover:bg-slate-800"
                        >
                          Book Standard Consultation
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {bookedRevisitDoctor && (
                <div className="p-2.5 rounded bg-emerald-950/80 border border-emerald-700 text-xs text-emerald-300 font-mono flex items-center gap-2">
                  <CheckCircle2 size={15} className="text-emerald-400 shrink-0" />
                  <span>
                    <strong>Free Follow-Up Revisit Token Issued:</strong> Scheduled with {bookedRevisitDoctor}. {revisitPolicyNotice || "Doctor's revisit rule applied: Fee waived to ₹0.00!"}
                  </span>
                </div>
              )}
            </Card>

            {/* 2-Column Clinical Command Layout: Left = Tracked State, Right = Longitudinal Timeline */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* LEFT COLUMN: Clinical Tracked Snapshots (7 cols) */}
              <div className="lg:col-span-7 space-y-4">
                {/* Active Care & Admission Card */}
                <Card className="p-4 bg-slate-900 border-slate-800 space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                      <Heart size={14} className="text-rose-400" /> Active Clinical Encounter
                    </span>
                    <Badge variant="success">INPATIENT ADMITTED</Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <span className="text-slate-400 block text-[10px]">Admitted Ward:</span>
                      <span className="font-semibold text-slate-100">Coronary Care Unit (CCU)</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px]">Assigned Bed:</span>
                      <span className="font-mono font-bold text-sky-400">Bed CCU-204 (Room R-CCU-102)</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px]">Treating Consultant:</span>
                      <span className="font-semibold text-slate-100">Dr. Vikram Seth (Interventional Cardiology)</span>
                    </div>
                    <div>
                      <span className="text-slate-400 block text-[10px]">Admission Date &amp; LOS:</span>
                      <span className="font-mono text-slate-200">01-Nov-2026 (Day 1)</span>
                    </div>
                  </div>
                </Card>

                {/* Hemodynamic Vitals & NEWS2 Score Card */}
                <Card className="p-4 bg-slate-900 border-slate-800 space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                      <Activity size={14} className="text-sky-400" /> Hemodynamics &amp; Early Warning Score
                    </span>
                    <Badge variant="info">NEWS2: 1 (LOW RISK)</Badge>
                  </div>
                  <div className="grid grid-cols-4 gap-2 text-xs">
                    <div className="p-2 rounded bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-400 uppercase">BP</div>
                      <div className="text-sm font-bold text-slate-100 font-mono">148/92</div>
                    </div>
                    <div className="p-2 rounded bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-400 uppercase">Pulse</div>
                      <div className="text-sm font-bold text-slate-100 font-mono">88 bpm</div>
                    </div>
                    <div className="p-2 rounded bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-400 uppercase">SpO2</div>
                      <div className="text-sm font-bold text-emerald-400 font-mono">97%</div>
                    </div>
                    <div className="p-2 rounded bg-slate-950 border border-slate-800">
                      <div className="text-[10px] text-slate-400 uppercase">Temp</div>
                      <div className="text-sm font-bold text-slate-100 font-mono">98.4 °F</div>
                    </div>
                  </div>
                </Card>

                {/* Problem List (ICD-10) */}
                <Card className="p-4 bg-slate-900 border-slate-800 space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                      <Stethoscope size={14} className="text-amber-400" /> Active Problem List &amp; Diagnoses
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono">ICD-10 Codified</span>
                  </div>
                  <div className="space-y-2 text-xs">
                    <div className="p-2 rounded bg-slate-950 border border-slate-800 flex items-start justify-between">
                      <div>
                        <div className="font-semibold text-slate-200">Angina pectoris, unspecified (I20.9)</div>
                        <div className="text-[10px] font-mono text-slate-400">Onset: 01-Nov-2026 • Acute Presentation</div>
                      </div>
                      <Badge variant="warning">Primary</Badge>
                    </div>
                    <div className="p-2 rounded bg-slate-950 border border-slate-800 flex items-start justify-between">
                      <div>
                        <div className="font-semibold text-slate-200">Essential (primary) hypertension (I10)</div>
                        <div className="text-[10px] font-mono text-slate-400">Onset: 14-Jan-2024 • Chronic Condition</div>
                      </div>
                      <Badge variant="neutral">Chronic</Badge>
                    </div>
                  </div>
                </Card>

                {/* Active Medications & CPOE Orders Summary */}
                <div className="grid grid-cols-2 gap-4">
                  <Card className="p-3 bg-slate-900 border-slate-800 space-y-2">
                    <div className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1">
                      <Pill size={12} className="text-emerald-400" /> Active Medications
                    </div>
                    <div className="space-y-1.5 text-[11px] font-mono">
                      <div className="p-1.5 rounded bg-slate-950 border border-slate-800">
                        <div className="font-bold text-slate-200">Tab. Aspirin 75mg</div>
                        <div className="text-[10px] text-slate-400">1-0-0 • Post Meals • Dr. Seth</div>
                      </div>
                      <div className="p-1.5 rounded bg-slate-950 border border-slate-800">
                        <div className="font-bold text-slate-200">Tab. Atorvastatin 40mg</div>
                        <div className="text-[10px] text-slate-400">0-0-1 • Bedtime • Dr. Seth</div>
                      </div>
                    </div>
                  </Card>

                  <Card className="p-3 bg-slate-900 border-slate-800 space-y-2">
                    <div className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1">
                      <FileText size={12} className="text-indigo-400" /> CPOE Lab Results
                    </div>
                    <div className="space-y-1.5 text-[11px] font-mono">
                      <div className="p-1.5 rounded bg-rose-950/30 border border-rose-900/60">
                        <div className="font-bold text-rose-300">Serum Troponin-I: 0.12 ng/mL</div>
                        <div className="text-[10px] text-rose-400">CRITICAL HIGH (Ref &lt; 0.04)</div>
                      </div>
                      <div className="p-1.5 rounded bg-slate-950 border border-slate-800">
                        <div className="font-bold text-slate-200">Complete Blood Count (CBC)</div>
                        <div className="text-[10px] text-emerald-400">Normal Range • Verified</div>
                      </div>
                    </div>
                  </Card>
                </div>
              </div>

              {/* RIGHT COLUMN: Embedded Longitudinal Patient Care Timeline (5 cols) */}
              <div className="lg:col-span-5 space-y-4">
                <Card className="p-4 bg-slate-900 border-slate-800 space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <div className="flex items-center gap-2">
                      <div className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                        <Clock size={14} className="text-sky-400" /> Patient Care Timeline
                      </div>
                      <button
                        type="button"
                        onClick={refreshTimeline}
                        title="Sync latest cross-encounter clinical timeline"
                        className="text-slate-400 hover:text-sky-400 transition-colors p-0.5 rounded"
                      >
                        <RefreshCw size={11} className={loadingTimeline ? "animate-spin text-sky-400" : ""} />
                      </button>
                    </div>
                    <div className="flex gap-1 bg-slate-950 p-1 rounded border border-slate-800 text-[10px]">
                      {(["ALL", "CLINICAL", "LAB", "MED", "BILLING"] as const).map((filter) => (
                        <button
                          key={filter}
                          type="button"
                          onClick={() => setTimelineFilter(filter)}
                          className={`px-1.5 py-0.5 rounded font-semibold transition-all ${
                            timelineFilter === filter
                              ? "bg-sky-500 text-slate-950 font-bold"
                              : "text-slate-400 hover:text-slate-200"
                          }`}
                        >
                          {filter}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* High-Density Timeline Stream */}
                  <div className="space-y-3 max-h-[640px] overflow-y-auto pr-1">
                    {filteredEvents.map((ev) => {
                      const EvIcon = ev.icon;
                      return (
                        <div
                          key={ev.id}
                          className="p-2.5 rounded-lg bg-slate-950 border border-slate-800/80 hover:border-slate-700 transition-colors space-y-1.5"
                        >
                          <div className="flex items-center justify-between text-[11px]">
                            <span className="font-bold text-slate-200 flex items-center gap-1.5">
                              <EvIcon size={12} className="text-sky-400" /> {ev.title}
                            </span>
                            <span className="font-mono text-[10px] text-slate-400">{ev.timestamp}</span>
                          </div>

                          <div className="text-[11px] text-slate-300 leading-relaxed">{ev.details}</div>

                          <div className="flex items-center justify-between pt-1 border-t border-slate-900 text-[10px] text-slate-500 font-mono">
                            <span>Actor: {ev.actor}</span>
                            <Badge variant={ev.category === "CLINICAL" ? "info" : "neutral"} size="sm">
                              {ev.category}
                            </Badge>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </Card>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: LONGITUDINAL TIMELINE */}
        {activeTab === "timeline" && (
          <div className="max-w-4xl mx-auto space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-slate-100">Longitudinal Clinical Care Stream</h3>
                  <button
                    type="button"
                    onClick={refreshTimeline}
                    title="Sync latest cross-encounter clinical timeline"
                    className="text-slate-400 hover:text-sky-400 transition-colors p-1 rounded"
                  >
                    <RefreshCw size={13} className={loadingTimeline ? "animate-spin text-sky-400" : ""} />
                  </button>
                  {liveTimeline && liveTimeline.length > 0 && (
                    <Badge variant="success" size="sm" className="text-[10px] font-mono">
                      Live Synchronized ({liveTimeline.length} events)
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-slate-400">Synchronized cross-encounter timeline from initial registration to present care.</p>
              </div>
              <div className="flex gap-1 bg-slate-900 p-1 rounded-lg border border-slate-800 text-xs">
                {(["ALL", "CLINICAL", "LAB", "MED", "BILLING"] as const).map((filter) => (
                  <button
                    key={filter}
                    onClick={() => setTimelineFilter(filter)}
                    className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-all ${
                      timelineFilter === filter
                        ? "bg-sky-500 text-slate-950 font-bold"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {filter}
                  </button>
                ))}
              </div>
            </div>

            {/* Timeline Stream */}
            <div className="relative border-l-2 border-slate-800 ml-4 space-y-6 py-2">
              {filteredEvents.map((ev) => {
                const Icon = ev.icon;
                return (
                  <div key={ev.id} className="relative pl-6 group">
                    {/* Circle Node */}
                    <div className="absolute -left-2.5 top-1.5 w-5 h-5 rounded-full bg-slate-900 border-2 border-sky-400 flex items-center justify-center text-[10px] shadow-md shadow-sky-500/20">
                      <div className="w-1.5 h-1.5 rounded-full bg-sky-400" />
                    </div>

                    <Card className="p-4 bg-slate-900 border-slate-800 hover:border-slate-700 transition-colors">
                      <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
                        <span className="font-mono text-sky-400 font-semibold">{ev.timestamp}</span>
                        <span className="text-[10px] font-mono uppercase bg-slate-950 px-2 py-0.5 rounded border border-slate-800 text-slate-400">
                          {ev.actor}
                        </span>
                      </div>
                      <div className="font-bold text-sm text-slate-200 mb-1 flex items-center gap-2">
                        <Icon size={15} className="text-sky-400" />
                        <span>{ev.title}</span>
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed bg-slate-950 p-2.5 rounded-lg border border-slate-800/80 font-mono">
                        {ev.details}
                      </p>
                    </Card>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* TAB 3: PROBLEM LIST & CLINICAL */}
        {activeTab === "clinical" && (
          <div className="max-w-5xl mx-auto space-y-6">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-sm font-bold text-slate-100">Active Problems & ICD-10 Diagnoses</h3>
                <p className="text-xs text-slate-400">Longitudinal morbidity profile tracked across all hospital admissions.</p>
              </div>
              <Button className="bg-sky-500 text-slate-950 font-bold text-xs">+ Add Clinical Diagnosis</Button>
            </div>
            <Card className="p-0 bg-slate-900 border-slate-800 overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 uppercase font-mono text-[10px]">
                  <tr>
                    <th className="p-3">ICD-10 Code</th>
                    <th className="p-3">Diagnosis Description</th>
                    <th className="p-3">Classification</th>
                    <th className="p-3">OnsetDate</th>
                    <th className="p-3">Diagnosing Physician</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800 text-slate-300">
                  <tr className="hover:bg-slate-800/40">
                    <td className="p-3 font-mono font-bold text-sky-400">I20.9</td>
                    <td className="p-3 font-semibold text-slate-100">Angina pectoris, unspecified</td>
                    <td className="p-3"><Badge variant="warning">Acute Active</Badge></td>
                    <td className="p-3 font-mono">01-Nov-2026</td>
                    <td className="p-3">Dr. Ramesh Gupta (Cardiology)</td>
                  </tr>
                  <tr className="hover:bg-slate-800/40">
                    <td className="p-3 font-mono font-bold text-sky-400">I10</td>
                    <td className="p-3 font-semibold text-slate-100">Essential (primary) hypertension</td>
                    <td className="p-3"><Badge variant="neutral">Chronic</Badge></td>
                    <td className="p-3 font-mono">14-Jan-2024</td>
                    <td className="p-3">Dr. Anita Roy (General Med)</td>
                  </tr>
                </tbody>
              </table>
            </Card>
          </div>
        )}

        {/* TAB 4: VITALS & HEMODYNAMICS */}
        {activeTab === "vitals" && (
          <div className="max-w-5xl mx-auto space-y-6">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-sm font-bold text-slate-100">Hemodynamic Vitals & Deterioration History</h3>
                <p className="text-xs text-slate-400">Time-series hemodynamic tracking and National Early Warning Score 2 (NEWS2).</p>
              </div>
              <Button className="bg-emerald-500 text-slate-950 font-bold text-xs">+ Record Bedside Vitals</Button>
            </div>
            <Card className="p-0 bg-slate-900 border-slate-800 overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 uppercase font-mono text-[10px]">
                  <tr>
                    <th className="p-3">Timestamp</th>
                    <th className="p-3">BP (mmHg)</th>
                    <th className="p-3">Pulse (bpm)</th>
                    <th className="p-3">SpO2 (%)</th>
                    <th className="p-3">Temp (°F)</th>
                    <th className="p-3">Resp Rate</th>
                    <th className="p-3">NEWS2 Score</th>
                    <th className="p-3">Recorded By</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800 text-slate-300 font-mono">
                  <tr className="hover:bg-slate-800/40">
                    <td className="p-3 text-sky-400 font-semibold">Today 09:18</td>
                    <td className="p-3 font-bold text-slate-100">148/92</td>
                    <td className="p-3">88</td>
                    <td className="p-3 text-emerald-400">97% (Air)</td>
                    <td className="p-3">98.4</td>
                    <td className="p-3">16</td>
                    <td className="p-3"><Badge variant="info">1 (Low)</Badge></td>
                    <td className="p-3 text-slate-400">Sister Anjali (RN)</td>
                  </tr>
                </tbody>
              </table>
            </Card>
          </div>
        )}

        {/* TAB 5: ACTIVE MEDICATIONS */}
        {activeTab === "medications" && (
          <div className="max-w-5xl mx-auto space-y-6">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-sm font-bold text-slate-100">Current Inpatient & Outpatient Prescriptions</h3>
                <p className="text-xs text-slate-400">Medications verified against CDS allergy and drug-drug clash radars.</p>
              </div>
              <Button className="bg-sky-500 text-slate-950 font-bold text-xs">+ CPOE Prescribe (Rx)</Button>
            </div>
            <Card className="p-0 bg-slate-900 border-slate-800 overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 uppercase font-mono text-[10px]">
                  <tr>
                    <th className="p-3">Medication Name</th>
                    <th className="p-3">Dosage & Route</th>
                    <th className="p-3">Frequency</th>
                    <th className="p-3">Duration</th>
                    <th className="p-3">Status</th>
                    <th className="p-3">Prescribing Doctor</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800 text-slate-300">
                  <tr className="hover:bg-slate-800/40">
                    <td className="p-3 font-bold text-slate-100">Aspirin Gastro-Resistant</td>
                    <td className="p-3 font-mono">75 mg (Oral Tab)</td>
                    <td className="p-3">Once Daily (OD)</td>
                    <td className="p-3 font-mono">30 Days</td>
                    <td className="p-3"><Badge variant="success">Active</Badge></td>
                    <td className="p-3">Dr. Ramesh Gupta</td>
                  </tr>
                  <tr className="hover:bg-slate-800/40">
                    <td className="p-3 font-bold text-slate-100">Atorvastatin Calcium</td>
                    <td className="p-3 font-mono">40 mg (Oral Tab)</td>
                    <td className="p-3">Night at bedtime (QHS)</td>
                    <td className="p-3 font-mono">30 Days</td>
                    <td className="p-3"><Badge variant="success">Active</Badge></td>
                    <td className="p-3">Dr. Ramesh Gupta</td>
                  </tr>
                  <tr className="hover:bg-slate-800/40">
                    <td className="p-3 font-bold text-slate-100">Clopidogrel Bisulfate</td>
                    <td className="p-3 font-mono">75 mg (Oral Tab)</td>
                    <td className="p-3">Once Daily (OD)</td>
                    <td className="p-3 font-mono">30 Days</td>
                    <td className="p-3"><Badge variant="success">Active</Badge></td>
                    <td className="p-3">Dr. Ramesh Gupta</td>
                  </tr>
                </tbody>
              </table>
            </Card>
          </div>
        )}

        {/* TAB 6: ORDERS & DIAGNOSTICS */}
        {activeTab === "orders" && (
          <div className="max-w-5xl mx-auto space-y-6">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-sm font-bold text-slate-100">CPOE Diagnostic Orders & Reports</h3>
                <p className="text-xs text-slate-400">Laboratory investigations, microbiology, and DICOM radiology PACS studies.</p>
              </div>
              <Button className="bg-sky-500 text-slate-950 font-bold text-xs">+ Place Diagnostic Order</Button>
            </div>
            <Card className="p-0 bg-slate-900 border-slate-800 overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950 text-slate-400 border-b border-slate-800 uppercase font-mono text-[10px]">
                  <tr>
                    <th className="p-3">Order Code</th>
                    <th className="p-3">Investigation Name</th>
                    <th className="p-3">Priority</th>
                    <th className="p-3">Order Time</th>
                    <th className="p-3">Result / Report</th>
                    <th className="p-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800 text-slate-300">
                  <tr className="hover:bg-slate-800/40">
                    <td className="p-3 font-mono text-sky-400 font-bold">LAB-TROP-I</td>
                    <td className="p-3 font-semibold text-slate-100">Serum Troponin-I (High Sensitivity)</td>
                    <td className="p-3"><Badge variant="danger">STAT</Badge></td>
                    <td className="p-3 font-mono">Today 09:50</td>
                    <td className="p-3 font-mono font-bold text-rose-400">0.12 ng/mL (HIGH)</td>
                    <td className="p-3"><Badge variant="success">Verified</Badge></td>
                  </tr>
                  <tr className="hover:bg-slate-800/40">
                    <td className="p-3 font-mono text-sky-400 font-bold">RAD-ECG-12</td>
                    <td className="p-3 font-semibold text-slate-100">12-Lead Electrocardiogram (ECG)</td>
                    <td className="p-3"><Badge variant="danger">STAT</Badge></td>
                    <td className="p-3 font-mono">Today 09:50</td>
                    <td className="p-3 text-slate-300">Sinus rhythm, ST depression V4-V6</td>
                    <td className="p-3"><Badge variant="success">Verified</Badge></td>
                  </tr>
                </tbody>
              </table>
            </Card>
          </div>
        )}

        {/* TAB 7: BILLING & FOLIO */}
        {activeTab === "billing" && (
          <div className="max-w-5xl mx-auto space-y-6">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-sm font-bold text-slate-100">Patient Inpatient Folio & Charges</h3>
                <p className="text-xs text-slate-400">Running itemized charges, TPA insurance pre-authorizations, and payment receipts.</p>
              </div>
              <Button className="bg-emerald-500 text-slate-950 font-bold text-xs">+ Post Folio Payment</Button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Card className="p-3 bg-slate-900 border-slate-800">
                <div className="text-[10px] text-slate-400 uppercase">Gross Charges</div>
                <div className="text-lg font-bold font-mono text-slate-100 mt-1">₹34,800</div>
              </Card>
              <Card className="p-3 bg-slate-900 border-slate-800">
                <div className="text-[10px] text-slate-400 uppercase">TPA Pre-Auth Limit</div>
                <div className="text-lg font-bold font-mono text-emerald-400 mt-1">₹1,50,000</div>
              </Card>
              <Card className="p-3 bg-slate-900 border-slate-800">
                <div className="text-[10px] text-slate-400 uppercase">Advance Deposits</div>
                <div className="text-lg font-bold font-mono text-sky-400 mt-1">₹10,000</div>
              </Card>
              <Card className="p-3 bg-slate-900 border-slate-800">
                <div className="text-[10px] text-slate-400 uppercase">Patient Net Due</div>
                <div className="text-lg font-bold font-mono text-slate-400 mt-1">₹0 (Covered)</div>
              </Card>
            </div>
          </div>
        )}

        {/* TAB 8: DPDP CONSENTS & PRIVACY */}
        {activeTab === "consents" && (
          <div className="max-w-5xl mx-auto space-y-6">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-sm font-bold text-slate-100">India DPDP Act 2023 Consent Governance</h3>
                <p className="text-xs text-slate-400">Purpose-specific digital consent artifacts and data principal access audit trail.</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="success">DPDP SECTION 6 COMPLIANT</Badge>
                <Button
                  onClick={handlePrintConsentCertificate}
                  variant="outline"
                  size="sm"
                  className="flex items-center gap-1.5 text-xs text-sky-400 border-sky-800 hover:bg-sky-950/40"
                  title="Print Official Form DPDP-CERT-01"
                >
                  <Printer size={13} /> Print Statutory Consent Record
                </Button>
              </div>
            </div>
            <Card className="p-4 bg-slate-900 border-slate-800 space-y-4">
              <div className="text-xs text-slate-300">
                Digital consent recorded with cryptographic hash under Section 6 of India's Digital Personal Data Protection Act 2023.
              </div>
              <div className="space-y-2">
                {[
                  { purpose: "Routine Clinical Consultation & Diagnostics", status: "GRANTED", date: "01-Nov-2026" },
                  { purpose: "Inpatient Hospital Care & Nursing Administration", status: "GRANTED", date: "01-Nov-2026" },
                  { purpose: "TPA Insurance Cashless Claim Adjudication", status: "GRANTED", date: "01-Nov-2026" },
                  { purpose: "Anonymized Medical Research & Academic Studies", status: "REFUSED", date: "01-Nov-2026" },
                ].map((item, idx) => (
                  <div key={idx} className="flex items-center justify-between p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs">
                    <div>
                      <span className="font-semibold text-slate-200">{item.purpose}</span>
                      <div className="text-[10px] text-slate-500 font-mono">Recorded: {item.date}</div>
                    </div>
                    <Badge variant={item.status === "GRANTED" ? "success" : "danger"}>
                      {item.status}
                    </Badge>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
};
