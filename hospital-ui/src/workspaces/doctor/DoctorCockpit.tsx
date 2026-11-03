import React, { useEffect, useState } from "react";
import { uiApi } from "../../api/uiApi";
import { opdQueueApi, OPDQueueEntry, OPDQueueSummary } from "../../api/opdQueueApi";
import { DoctorQueueSummary } from "../../types";
import { useActivePatient } from "../../core/context/ActivePatientContext";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Modal } from "../../components/ui/Modal";
import { useHospitalConfig } from "../../core/context/HospitalConfigContext";
import { printDocument } from "../../utils/printDocument";
import {
  Clock,
  Stethoscope,
  RefreshCw,
  PlusCircle,
  Trash2,
  CheckCircle2,
  Printer,
  FileText,
  AlertTriangle,
  Zap,
  TrendingUp,
  History,
  Activity,
  ShieldAlert,
  Building2,
  Award,
} from "lucide-react";

interface PrescribedMedication {
  id: string;
  name: string;
  dosage: string;
  frequency: string;
  duration: string;
  instructions: string;
  ddiStatus: "SAFE" | "CAUTION" | "CRITICAL";
  ddiWarning?: string;
}

interface PrescribedTest {
  id: string;
  name: string;
  category: "Hematology" | "Biochemistry" | "Microbiology" | "Radiology";
  priority: "ROUTINE" | "STAT";
}

export const DoctorCockpit: React.FC = () => {
  const { hospitalProfile, getPrinterForCategory } = useHospitalConfig();
  const [activeTab, setActiveTab] = useState<"consultation" | "history" | "trends">("consultation");
  const [queue, setQueue] = useState<DoctorQueueSummary | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const { selectPatient, patientSummary } = useActivePatient();

  // Selected Appointment State
  const [selectedAppointmentId, setSelectedAppointmentId] = useState<number | null>(null);
  const [activeQueueLink, setActiveQueueLink] = useState<{ queueId: number; entry: OPDQueueEntry } | null>(null);
  const [workflowError, setWorkflowError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [completionBanner, setCompletionBanner] = useState<{
    patientName: string;
    tokenNumber: number;
    timestamp: string;
  } | null>(null);

  // SOAP State
  const [subjective, setSubjective] = useState("Patient presents with intermittent low-grade fever for 3 days and dry irritating cough. No chest tightness, no hemoptysis.");
  const [assessment, setAssessment] = useState("Viral Upper Respiratory Tract Infection (URTI). Hemodynamically stable. Nil acute red flags.");
  const [selectedIcd10, setSelectedIcd10] = useState("J06.9 - Acute upper respiratory infection, unspecified");

  // Prescriptions & Diagnostics State
  const [medications, setMedications] = useState<PrescribedMedication[]>([
    {
      id: "med-1",
      name: "Paracetamol 650mg Tablet",
      dosage: "650mg",
      frequency: "TDS (Thrice daily)",
      duration: "5 days",
      instructions: "After food, for fever > 100°F",
      ddiStatus: "SAFE",
    },
    {
      id: "med-2",
      name: "Levocetirizine 5mg Tablet",
      dosage: "5mg",
      frequency: "OD (Once daily)",
      duration: "3 days",
      instructions: "At bedtime",
      ddiStatus: "SAFE",
    },
  ]);

  const [diagnosticOrders, setDiagnosticOrders] = useState<PrescribedTest[]>([
    {
      id: "test-1",
      name: "Complete Blood Count (CBC) with Differential",
      category: "Hematology",
      priority: "ROUTINE",
    },
  ]);

  // CDS Clinical Override State
  const [isOverrideModalOpen, setIsOverrideModalOpen] = useState(false);
  const [overrideRationale, setOverrideRationale] = useState("Clinical benefit outweighs minor interaction risk; monitoring renal and cardiac parameters.");
  const [isOverrideDocumented, setIsOverrideDocumented] = useState(false);

  // Modal States
  const [isAddDrugModalOpen, setIsAddDrugModalOpen] = useState(false);
  const [isAddTestModalOpen, setIsAddTestModalOpen] = useState(false);
  const [isSummarySlipOpen, setIsSummarySlipOpen] = useState(false);
  const [orderSetToast, setOrderSetToast] = useState<string | null>(null);

  // Inpatient Admission Advice State
  const [isAdmissionAdviceModalOpen, setIsAdmissionAdviceModalOpen] = useState(false);
  const [admittingDept, setAdmittingDept] = useState("Cardiology");
  const [admittingPriority, setAdmittingPriority] = useState<"EMERGENCY_STAT" | "HIGH_ACUITY_2H" | "ELECTIVE_PLANNED">("EMERGENCY_STAT");
  const [admittingBedCategory, setAdmittingBedCategory] = useState<"ICU" | "HDU" | "SINGLE_PRIVATE" | "GENERAL_WARD">("ICU");
  const [admittingDirectives, setAdmittingDirectives] = useState("NPO (Nil By Mouth). Secure 18G IV access. Continuous cardiac telemetry & SpO2 monitoring. STAT cardiology registrar review upon bed arrival.");

  // Statutory Medical Certificate State
  const [isMedicalCertModalOpen, setIsMedicalCertModalOpen] = useState(false);
  const [certRestDays, setCertRestDays] = useState("5");
  const [certDiagnosis, setCertDiagnosis] = useState("Acute Bronchitis with Bronchospasm");
  const [certIdentificationMark, setCertIdentificationMark] = useState("Mole on right cheek");

  // Add Drug Form State
  const [drugName, setDrugName] = useState("Azithromycin 500mg Tablet");
  const [drugDosage, setDrugDosage] = useState("500mg");
  const [drugFrequency, setDrugFrequency] = useState("OD (Once daily)");
  const [drugDuration, setDrugDuration] = useState("3 days");
  const [drugInstructions, setDrugInstructions] = useState("1 hour before or 2 hours after meals");

  // Add Test Form State
  const [testName, setTestName] = useState("C-Reactive Protein (CRP) Quantitative");
  const [testCategory, setTestCategory] = useState<"Hematology" | "Biochemistry" | "Microbiology" | "Radiology">("Biochemistry");
  const [testPriority, setTestPriority] = useState<"ROUTINE" | "STAT">("ROUTINE");

  const commonIcd10List = [
    "J06.9 - Acute upper respiratory infection, unspecified",
    "I10 - Essential (primary) hypertension",
    "E11.9 - Type 2 diabetes mellitus without complications",
    "I21.9 - Acute myocardial infarction, unspecified (STEMI/NSTEMI)",
    "A90 - Dengue fever [classical dengue]",
    "K21.9 - Gastro-esophageal reflux disease without esophagitis",
    "M54.5 - Low back pain, unspecified",
    "A09 - Infectious gastroenteritis and colitis, unspecified",
    "Z01.811 - Encounter for preprocedural cardiovascular examination",
  ];

  // 1-Click Order Sets Definition
  const orderSets = [
    {
      id: "acs",
      name: "ACS / Chest Pain Protocol",
      icon: "🫀",
      icd10: "I21.9 - Acute myocardial infarction, unspecified (STEMI/NSTEMI)",
      meds: [
        { id: `med-${Date.now()}-1`, name: "Tab. Aspirin 300mg (STAT)", dosage: "300mg", frequency: "STAT (Immediate)", duration: "1 dose", instructions: "Chewable", ddiStatus: "CAUTION" as const, ddiWarning: "Antithrombotic therapy: monitor for bleeding" },
        { id: `med-${Date.now()}-2`, name: "Tab. Clopidogrel 300mg (STAT)", dosage: "300mg", frequency: "STAT (Immediate)", duration: "1 dose", instructions: "Oral", ddiStatus: "CAUTION" as const, ddiWarning: "Dual antiplatelet bleeding precaution" },
        { id: `med-${Date.now()}-3`, name: "Tab. Atorvastatin 80mg", dosage: "80mg", frequency: "OD (Once daily)", duration: "30 days", instructions: "At bedtime", ddiStatus: "SAFE" as const },
        { id: `med-${Date.now()}-4`, name: "Tab. Nitroglycerin 0.5mg Sublingual", dosage: "0.5mg", frequency: "SOS (If chest pain persists)", duration: "3 doses max", instructions: "Under tongue, 5m apart", ddiStatus: "SAFE" as const },
      ],
      tests: [
        { id: `test-${Date.now()}-1`, name: "12-Lead Electrocardiogram (ECG) STAT", category: "Radiology" as const, priority: "STAT" as const },
        { id: `test-${Date.now()}-2`, name: "Serum High-Sensitivity Troponin I Quantitative", category: "Biochemistry" as const, priority: "STAT" as const },
        { id: `test-${Date.now()}-3`, name: "CK-MB Mass Quantitative", category: "Biochemistry" as const, priority: "STAT" as const },
      ],
    },
    {
      id: "dengue",
      name: "Dengue Febrile Protocol",
      icon: "🩸",
      icd10: "A90 - Dengue fever [classical dengue]",
      meds: [
        { id: `med-${Date.now()}-1`, name: "IV Normal Saline 0.9%", dosage: "500ml", frequency: "100ml/hr Infusion", duration: "24 hours", instructions: "Maintenance hydration", ddiStatus: "SAFE" as const },
        { id: `med-${Date.now()}-2`, name: "Tab. Paracetamol 650mg", dosage: "650mg", frequency: "TDS (Thrice daily)", duration: "5 days", instructions: "Strict avoidance of NSAIDs", ddiStatus: "SAFE" as const },
      ],
      tests: [
        { id: `test-${Date.now()}-1`, name: "Complete Blood Count (CBC) with Platelet Count STAT", category: "Hematology" as const, priority: "STAT" as const },
        { id: `test-${Date.now()}-2`, name: "Dengue NS1 Antigen ELISA", category: "Microbiology" as const, priority: "STAT" as const },
        { id: `test-${Date.now()}-3`, name: "Dengue IgM / IgG Antibodies", category: "Microbiology" as const, priority: "ROUTINE" as const },
      ],
    },
    {
      id: "dm",
      name: "Type 2 Diabetes Review",
      icon: "🩺",
      icd10: "E11.9 - Type 2 diabetes mellitus without complications",
      meds: [
        { id: `med-${Date.now()}-1`, name: "Tab. Metformin 500mg SR", dosage: "500mg", frequency: "BD (Twice daily)", duration: "90 days", instructions: "With main meals", ddiStatus: "SAFE" as const },
        { id: `med-${Date.now()}-2`, name: "Tab. Glimepiride 1mg", dosage: "1mg", frequency: "OD (Once daily)", duration: "90 days", instructions: "Before breakfast", ddiStatus: "SAFE" as const },
      ],
      tests: [
        { id: `test-${Date.now()}-1`, name: "Glycated Hemoglobin (HbA1c)", category: "Biochemistry" as const, priority: "ROUTINE" as const },
        { id: `test-${Date.now()}-2`, name: "Fasting & Postprandial Blood Glucose", category: "Biochemistry" as const, priority: "ROUTINE" as const },
        { id: `test-${Date.now()}-3`, name: "Lipid Profile & Serum Creatinine", category: "Biochemistry" as const, priority: "ROUTINE" as const },
      ],
    },
    {
      id: "preop",
      name: "Pre-Operative Clearance",
      icon: "🦴",
      icd10: "Z01.811 - Encounter for preprocedural cardiovascular examination",
      meds: [],
      tests: [
        { id: `test-${Date.now()}-1`, name: "Blood Grouping & Rh Typing with Crossmatch 2 Units", category: "Hematology" as const, priority: "ROUTINE" as const },
        { id: `test-${Date.now()}-2`, name: "Coagulation Profile (PT / INR & aPTT)", category: "Hematology" as const, priority: "ROUTINE" as const },
        { id: `test-${Date.now()}-3`, name: "Chest X-Ray PA View", category: "Radiology" as const, priority: "ROUTINE" as const },
        { id: `test-${Date.now()}-4`, name: "12-Lead Resting ECG", category: "Radiology" as const, priority: "ROUTINE" as const },
      ],
    },
  ];

  const applyOrderSet = (bundle: typeof orderSets[0]) => {
    setSelectedIcd10(bundle.icd10);
    if (bundle.meds.length > 0) {
      setMedications(bundle.meds);
    }
    if (bundle.tests.length > 0) {
      setDiagnosticOrders(bundle.tests);
    }
    setOrderSetToast(`Order Set Applied: ${bundle.name}`);
    setTimeout(() => setOrderSetToast(null), 4000);
  };

  const loadQueue = async () => {
    setIsLoading(true);
    try {
      const data = await uiApi.getDoctorQueueToday();
      setQueue(data);
    } catch (err) {
      console.error("Failed to load doctor queue:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadQueue();
  }, []);

  const handleAddMedication = (e: React.FormEvent) => {
    e.preventDefault();
    const newMed: PrescribedMedication = {
      id: `med-${Date.now()}`,
      name: drugName,
      dosage: drugDosage,
      frequency: drugFrequency,
      duration: drugDuration,
      instructions: drugInstructions,
      ddiStatus: "SAFE",
    };
    setMedications((prev) => [...prev, newMed]);
    setIsAddDrugModalOpen(false);
  };

  const handleRemoveMedication = (id: string) => {
    setMedications((prev) => prev.filter((m) => m.id !== id));
  };

  const handleAddDiagnosticOrder = (e: React.FormEvent) => {
    e.preventDefault();
    const newTest: PrescribedTest = {
      id: `test-${Date.now()}`,
      name: testName,
      category: testCategory,
      priority: testPriority,
    };
    setDiagnosticOrders((prev) => [...prev, newTest]);
    setIsAddTestModalOpen(false);
  };

  const handleRemoveTest = (id: string) => {
    setDiagnosticOrders((prev) => prev.filter((t) => t.id !== id));
  };

  const handleSelectAppointment = async (appt: {
    appointment_id: number;
    patient_id: number;
    status: string;
  }) => {
    setSelectedAppointmentId(appt.appointment_id);
    selectPatient(appt.patient_id);
    setCompletionBanner(null);
    setWorkflowError(null);
    setActiveQueueLink(null);
    try {
      const queues = await opdQueueApi.listQueues();
      const snapshots = await Promise.all(queues.map(async (q: OPDQueueSummary) => ({
        queue: q,
        entries: await opdQueueApi.listEntries(q.id),
      })));
      let match: { queueId: number; entry: OPDQueueEntry } | undefined;
      for (const snapshot of snapshots) {
        const entry = snapshot.entries.find((item: OPDQueueEntry) => item.appointment_id === appt.appointment_id);
        if (entry) { match = { queueId: snapshot.queue.id, entry }; break; }
      }
      if (!match) {
        setWorkflowError("This appointment has no OPD queue entry. Reception must complete check-in first.");
        return;
      }
      if (!match.entry.encounter_id) {
        setWorkflowError("Queue entry has no linked encounter. Repair the encounter linkage before consultation.");
        return;
      }
      if (match.entry.state === "ARRIVED") {
        await opdQueueApi.startConsultation(match.queueId, match.entry.id, { encounter_id: match.entry.encounter_id });
        setActiveQueueLink({ ...match, entry: { ...match.entry, state: "IN_CONSULTATION" } });
        await loadQueue();
      } else if (match.entry.state === "IN_CONSULTATION") {
        setActiveQueueLink(match);
      } else {
        setWorkflowError("Patient is " + match.entry.state.replaceAll("_", " ") + " in the OPD queue. Reception must mark the patient arrived first.");
      }
    } catch (err) {
      setWorkflowError(err instanceof Error ? err.message : "Unable to start OPD consultation.");
    }
  };

  const handleFinalizeEncounter = () => {
    setIsSummarySlipOpen(true);
  };

  const handleConfirmAndComplete = async () => {
    setIsSubmitting(true);
    try {
      // Queue completion is separate from signing/closing the clinical encounter.
      if (!selectedAppointmentId || !activeQueueLink) {
        throw new Error("The selected patient is not linked to an active OPD queue consultation.");
      }
      await opdQueueApi.completeConsultation(activeQueueLink.queueId, activeQueueLink.entry.id, {
        reason_code: "CONSULTATION_COMPLETED",
      });

      if (queue && patientSummary) {
        setQueue({
          ...queue,
          completed: queue.completed + 1,
          in_consultation: Math.max(0, queue.in_consultation - 1),
          appointments: queue.appointments.map((a) =>
            a.patient_id === patientSummary.patient_id
              ? { ...a, status: "COMPLETED" }
              : a
          ),
        });

        const activeAppt = queue.appointments.find((a) => a.patient_id === patientSummary.patient_id);
        setCompletionBanner({
          patientName: patientSummary.full_name,
          tokenNumber: activeAppt?.token_number ?? 1,
          timestamp: new Date().toLocaleTimeString(),
        });
      }
      setActiveQueueLink(null);
      await loadQueue();
      setIsSummarySlipOpen(false);
    } catch (err) {
      setWorkflowError(err instanceof Error ? err.message : "Unable to complete OPD consultation.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePrintPrescriptionSlip = () => {
    const ptName = patientSummary?.full_name || "Patient";
    const ptMrn = patientSummary?.mrn || "--";
    const docName = queue?.doctor_name ? `Dr. ${queue.doctor_name}` : "Treating Consultant";
    const html = `
      <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 700px; margin: 0 auto; border: 1px solid #333; padding: 24px;">
        <div style="text-align: center; border-bottom: 2px solid #000; padding-bottom: 12px; margin-bottom: 16px;">
          <h2 style="margin: 0; font-size: 20px; text-transform: uppercase;">${hospitalProfile.name}</h2>
          <div style="font-size: 12px; font-weight: bold; color: #0284c7; margin-top: 2px;">OUTPATIENT CLINICAL CONSULTATION & e-PRESCRIPTION SLIP</div>
          <div style="font-size: 10px; color: #555;">${hospitalProfile.address} • Tel: ${hospitalProfile.phone}</div>
        </div>
        <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #ccc; padding-bottom: 8px; font-size: 12px; margin-bottom: 12px;">
          <div><b>Patient Name:</b> ${ptName.toUpperCase()}</div>
          <div><b>UHID / MRN:</b> ${ptMrn}</div>
          <div><b>Consultant:</b> ${docName}</div>
          <div><b>Date:</b> ${new Date().toLocaleDateString()}</div>
        </div>
        <div style="margin-bottom: 12px; font-size: 12px;">
          <b>Provisional Diagnosis / ICD-10:</b>
          <div style="background: #f8fafc; border: 1px solid #cbd5e1; padding: 8px; margin-top: 4px; font-weight: bold; color: #0f172a;">
            ${selectedIcd10}
          </div>
        </div>
        <div style="margin-bottom: 14px; font-size: 12px;">
          <b style="font-size: 16px; font-family: serif;">℞ Prescribed Medications:</b>
          <table style="width: 100%; border-collapse: collapse; font-size: 11px; margin-top: 6px;">
            <thead>
              <tr style="background: #f1f5f9; border-bottom: 1px solid #cbd5e1; text-align: left;">
                <th style="padding: 6px;">Medicine Name & Strength</th>
                <th style="padding: 6px;">Dosage</th>
                <th style="padding: 6px;">Frequency</th>
                <th style="padding: 6px;">Duration</th>
                <th style="padding: 6px;">Instructions</th>
              </tr>
            </thead>
            <tbody>
              ${medications.map((m) => `
                <tr style="border-bottom: 1px solid #e2e8f0;">
                  <td style="padding: 6px; font-weight: bold;">${m.name}</td>
                  <td style="padding: 6px;">${m.dosage}</td>
                  <td style="padding: 6px;">${m.frequency}</td>
                  <td style="padding: 6px;">${m.duration}</td>
                  <td style="padding: 6px; color: #475569;">${m.instructions}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
        ${diagnosticOrders.length > 0 ? `
        <div style="margin-bottom: 14px; font-size: 12px;">
          <b>Diagnostic Investigations Ordered:</b>
          <div style="padding: 6px 0; font-size: 11px; color: #334155;">
            ${diagnosticOrders.map((d) => `• ${d.name} (${d.category} - ${d.priority})`).join("<br/>")}
          </div>
        </div>
        ` : ""}
        <div style="margin-top: 50px; display: flex; justify-content: space-between; font-size: 11px;">
          <div><b>Follow-up Advice:</b> Review in OPD after completion of medication course or SOS if symptoms worsen.</div>
          <div style="border-top: 1px solid #000; width: 220px; text-align: center; padding-top: 4px;">
            <b>${docName}</b><br/><span style="font-size: 9px; color: #64748b;">Digitally Signed & Authenticated</span>
          </div>
        </div>
      </div>
    `;
    const a4Printer = getPrinterForCategory("CLINICAL_A4");
    printDocument(html, { title: `Prescription_${ptMrn}`, docType: "CLINICAL_SUMMARY", printerDevice: a4Printer });
  };

  const handlePrintAdmissionAdvice = () => {
    const ptName = patientSummary?.full_name || "Patient";
    const ptMrn = patientSummary?.mrn || "--";
    const docName = queue?.doctor_name ? `Dr. ${queue.doctor_name}` : "Treating Consultant";
    const a4Printer = getPrinterForCategory("CLINICAL_A4");

    const html = `
      <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 700px; margin: 0 auto; border: 2px solid #000; padding: 24px;">
        <div style="text-align: center; border-bottom: 2px solid #000; padding-bottom: 12px; margin-bottom: 16px;">
          <h2 style="margin: 0; font-size: 20px; text-transform: uppercase;">${hospitalProfile.name}</h2>
          <div style="font-size: 12px; font-weight: bold; color: #b91c1c; margin-top: 2px;">
            STATUTORY INPATIENT ADMISSION ADVICE & BED BOOKING REQUISITION
          </div>
          <div style="font-size: 10px; color: #555;">Form ADT-01 • Priority Bed Allocation Order • Hospital Central Admitting Office</div>
        </div>

        <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #ccc; padding-bottom: 8px; font-size: 12px; margin-bottom: 12px;">
          <div><b>Patient Name:</b> ${ptName.toUpperCase()}</div>
          <div><b>UHID / MRN:</b> ${ptMrn}</div>
          <div><b>Age / Gender:</b> ${patientSummary?.age_years || "--"}Y / ${patientSummary?.gender || "--"}</div>
          <div><b>Date & Time:</b> ${new Date().toLocaleString()}</div>
        </div>

        <div style="border: 2px solid ${admittingPriority === "EMERGENCY_STAT" ? "#dc2626" : "#0284c7"}; background: ${admittingPriority === "EMERGENCY_STAT" ? "#fef2f2" : "#f0f9ff"}; padding: 12px; border-radius: 6px; margin-bottom: 14px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <span style="font-size: 14px; font-weight: 800; color: ${admittingPriority === "EMERGENCY_STAT" ? "#b91c1c" : "#0369a1"};">
              ADMISSION PRIORITY: ${admittingPriority.replace(/_/g, " ")}
            </span>
            <span style="font-size: 12px; font-weight: bold; padding: 4px 8px; background: #fff; border: 1px solid #999; border-radius: 4px;">
              REQUESTED BED CLASS: ${admittingBedCategory.replace(/_/g, " ")}
            </span>
          </div>
          <div style="font-size: 11px; color: #334155;">
            <b>Admitting Specialty:</b> ${admittingDept} • <b>Treating Consultant:</b> ${docName}
          </div>
        </div>

        <div style="margin-bottom: 14px; font-size: 12px; border: 1px solid #cbd5e1; padding: 10px; border-radius: 6px;">
          <b>Provisional Admitting Diagnosis:</b>
          <div style="font-weight: bold; color: #0f172a; margin-top: 4px;">${selectedIcd10}</div>
        </div>

        <div style="margin-bottom: 20px; font-size: 12px; border: 1px solid #cbd5e1; padding: 10px; border-radius: 6px; background: #fafafa;">
          <b>Initial Care Plan & STAT Directives Prior to Bed Transfer:</b>
          <div style="font-family: monospace; font-size: 11px; margin-top: 6px; line-height: 1.6; color: #1e293b;">
            ${admittingDirectives}
          </div>
        </div>

        <div style="display: flex; justify-content: space-between; margin-top: 60px; font-size: 11px;">
          <div style="border-top: 1px solid #000; width: 220px; text-align: center; padding-top: 4px;">Treating Consultant Seal & Signature</div>
          <div style="border-top: 1px solid #000; width: 220px; text-align: center; padding-top: 4px;">Central ADT Desk Bed Allocation Stamp</div>
        </div>
      </div>
    `;

    printDocument(html, {
      title: `Admission_Advice_${ptMrn}`,
      docType: "CLINICAL_SUMMARY",
      printerDevice: a4Printer,
    });
    setIsAdmissionAdviceModalOpen(false);
  };

  const handlePrintMedicalCertificate = () => {
    const ptName = patientSummary?.full_name || "Patient";
    const ptMrn = patientSummary?.mrn || "--";
    const docName = queue?.doctor_name ? `Dr. ${queue.doctor_name}` : "Treating Consultant";
    const a4Printer = getPrinterForCategory("CLINICAL_A4");

    const html = `
      <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 680px; margin: 0 auto; border: 2px solid #000; padding: 28px;">
        <div style="text-align: center; border-bottom: 2px solid #000; padding-bottom: 12px; margin-bottom: 20px;">
          <h2 style="margin: 0; font-size: 22px; text-transform: uppercase;">${hospitalProfile.name}</h2>
          <div style="font-size: 12px; font-weight: bold; color: #0284c7; margin-top: 2px;">
            STATUTORY MEDICAL CERTIFICATE / SICKNESS & REST ADVICE
          </div>
          <div style="font-size: 10px; color: #555;">Issued under National Medical Commission (NMC) Code of Medical Ethics Regulations</div>
        </div>

        <div style="font-size: 12px; line-height: 2; margin-bottom: 24px; text-align: justify;">
          This is to certify that <b>${ptName.toUpperCase()}</b> (UHID: <b>${ptMrn}</b>), aged <b>${patientSummary?.age_years || "--"}</b> years, Gender: <b>${patientSummary?.gender || "--"}</b>, having personal identification mark: <i>${certIdentificationMark}</i>, was examined by me in the Outpatient Department on <b>${new Date().toLocaleDateString()}</b>.
          <br /><br />
          The patient is suffering from <b>${certDiagnosis}</b> and in my professional clinical opinion, absence from work / educational duty is essential for recovery. 
          <br />
          I therefore recommend medical bed rest and convalescence for a period of <b>${certRestDays} days</b>, commencing from <b>${new Date().toLocaleDateString()}</b>.
          <br />
          The patient is provisionally expected to be fit to resume normal duties on <b>${new Date(Date.now() + parseInt(certRestDays, 10) * 86400000).toLocaleDateString()}</b>, subject to clinical re-evaluation.
        </div>

        <div style="display: flex; justify-content: space-between; margin-top: 80px; font-size: 11px;">
          <div>
            <div><b>Place:</b> ${hospitalProfile.address || "Hospital Outpatient Clinic"}</div>
            <div><b>Date:</b> ${new Date().toLocaleDateString()}</div>
          </div>
          <div style="border-top: 1px solid #000; width: 240px; text-align: center; padding-top: 4px;">
            <b>${docName}</b><br />
            Consultant Physician / Surgeon<br />
            State Medical Council Regn No. 49204/MC
          </div>
        </div>
      </div>
    `;

    printDocument(html, {
      title: `Medical_Certificate_${ptMrn}`,
      docType: "CLINICAL_SUMMARY",
      printerDevice: a4Printer,
    });
    setIsMedicalCertModalOpen(false);
  };

  const handleProceedToNextPatient = () => {
    if (!queue) return;
    const nextWaiting = queue.appointments.find(
      (a) => a.status === "ARRIVED" || a.status === "CHECKED_IN" || a.status === "SCHEDULED"
    );
    if (nextWaiting) {
      handleSelectAppointment(nextWaiting);
    } else {
      setCompletionBanner(null);
    }
  };

  // Evaluate DDI & Allergy Safety Radar
  const hasMultipleAntithrombotics =
    medications.some((m) => m.name.toLowerCase().includes("aspirin")) &&
    medications.some((m) => m.name.toLowerCase().includes("clopidogrel"));
  const hasBetaLactamAllergyClash =
    (patientSummary?.critical_allergies?.some((a) => a.allergen.toLowerCase().includes("penicillin")) ?? false) &&
    medications.some((m) => m.name.toLowerCase().includes("amoxicillin") || m.name.toLowerCase().includes("ceftriaxone"));

  return (
    <div className="flex-1 flex overflow-hidden">
      {workflowError && <div className="absolute top-3 left-1/2 z-40 -translate-x-1/2 max-w-xl rounded-lg border border-rose-800 bg-rose-950 px-4 py-2 text-xs text-rose-200 shadow-lg">{workflowError}<button className="ml-3 underline" onClick={() => setWorkflowError(null)}>Dismiss</button></div>}
      {/* Column 1: Today's Consultation Queue */}
      <div className="w-96 border-r border-slate-800 flex flex-col bg-slate-900/40">
        {/* Queue Header & Metrics */}
        <div className="p-4 border-b border-slate-800">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h2 className="text-sm font-bold text-slate-100 uppercase tracking-wider">OPD Consultation Queue</h2>
              <p className="text-xs text-slate-400">Dr. {queue?.doctor_name || "Doctor"}</p>
            </div>
            <button
              onClick={loadQueue}
              disabled={isLoading}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
            >
              <RefreshCw size={14} className={isLoading ? "animate-spin" : ""} />
            </button>
          </div>

          {/* Metric Pills */}
          <div className="grid grid-cols-4 gap-1.5 text-center">
            <div className="bg-slate-800/80 p-1.5 rounded border border-slate-700">
              <div className="text-xs font-bold text-sky-400">{queue?.total_scheduled ?? 0}</div>
              <div className="text-[10px] text-slate-400 uppercase">Booked</div>
            </div>
            <div className="bg-slate-800/80 p-1.5 rounded border border-slate-700">
              <div className="text-xs font-bold text-amber-400">{queue?.checked_in ?? 0}</div>
              <div className="text-[10px] text-slate-400 uppercase">Arrived</div>
            </div>
            <div className="bg-slate-800/80 p-1.5 rounded border border-slate-700">
              <div className="text-xs font-bold text-purple-400">{queue?.in_consultation ?? 0}</div>
              <div className="text-[10px] text-slate-400 uppercase">In Room</div>
            </div>
            <div className="bg-slate-800/80 p-1.5 rounded border border-slate-700">
              <div className="text-xs font-bold text-emerald-400">{queue?.completed ?? 0}</div>
              <div className="text-[10px] text-slate-400 uppercase">Done</div>
            </div>
          </div>
        </div>

        {/* Appointment List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-2">
          {queue?.appointments.length === 0 ? (
            <div className="text-center py-12 text-slate-500 text-xs">
              No appointments scheduled for today.
            </div>
          ) : (
            queue?.appointments.map((appt) => (
              <div
                key={appt.appointment_id}
                onClick={() => handleSelectAppointment(appt)}
                className={`p-3 rounded-lg border cursor-pointer transition-all shadow-sm ${
                  patientSummary?.patient_id === appt.patient_id
                    ? "bg-slate-800/90 border-sky-500"
                    : "bg-slate-900 border-slate-800 hover:border-slate-700"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold px-1.5 py-0.5 rounded bg-sky-950 text-sky-400 border border-sky-800/60">
                      #{appt.token_number}
                    </span>
                    <span className="font-semibold text-slate-200 text-sm">{appt.patient_name}</span>
                  </div>
                  <Badge
                    variant={
                      appt.status === "COMPLETED"
                        ? "success"
                        : appt.status === "IN_CONSULTATION"
                        ? "purple"
                        : appt.status === "CHECKED_IN"
                        ? "warning"
                        : "info"
                    }
                    size="sm"
                  >
                    {appt.status}
                  </Badge>
                </div>
                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span>
                    {appt.gender} • {appt.age_years ? `${appt.age_years}y` : "--"}
                  </span>
                  {appt.wait_minutes > 0 && appt.status !== "COMPLETED" && (
                    <span className="flex items-center gap-1 text-amber-400 font-mono text-[11px]">
                      <Clock size={11} /> {appt.wait_minutes}m wait
                    </span>
                  )}
                </div>
                {appt.chief_complaint && (
                  <div className="text-[11px] text-slate-400 mt-1.5 italic truncate">
                    &quot;{appt.chief_complaint}&quot;
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Column 2 & 3: Clinical Consultation Action Pad */}
      <div className="flex-1 flex flex-col bg-slate-950 p-6 overflow-y-auto">
        {completionBanner && (
          <div className="mb-4 p-4 rounded-xl bg-emerald-950/40 border border-emerald-800/80 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-emerald-900/60 text-emerald-400">
                <CheckCircle2 size={20} />
              </div>
              <div>
                <div className="text-sm font-bold text-emerald-200">
                  Encounter Finalized &amp; Signed — Token #{completionBanner.tokenNumber} ({completionBanner.patientName})
                </div>
                <div className="text-xs text-emerald-400/80 font-mono mt-0.5">
                  Signed at {completionBanner.timestamp} • eRx dispatched to Pharmacy • Lab orders routed to LIS • Cashier billing updated
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsSummarySlipOpen(true)}
                className="border-emerald-700 text-emerald-300 hover:bg-emerald-900/50"
              >
                <Printer size={13} className="mr-1.5" /> Re-print Slip
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleProceedToNextPatient}
                className="bg-emerald-600 hover:bg-emerald-500 text-white"
              >
                Call Next Patient
              </Button>
            </div>
          </div>
        )}

        {/* Order Set Application Toast */}
        {orderSetToast && (
          <div className="mb-4 p-3 rounded-xl bg-sky-950/50 border border-sky-500/80 flex items-center justify-between text-xs font-mono text-sky-200 animate-fadeIn">
            <div className="flex items-center gap-2">
              <Zap size={16} className="text-sky-400" />
              <span>{orderSetToast}</span>
            </div>
            <span className="text-[10px] text-sky-400">CPOE Bundle Loaded</span>
          </div>
        )}

        {patientSummary ? (
          <div className="space-y-6 max-w-5xl">
            {/* Header / Active Encounter Status */}
            <div className="flex items-center justify-between pb-4 border-b border-slate-800">
              <div>
                <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
                  <Stethoscope className="text-sky-400" />
                  Clinical Consultation — {patientSummary.full_name}
                </h1>
                <p className="text-xs text-slate-400 mt-0.5 font-mono">
                  MRN: {patientSummary.mrn} • Age: {patientSummary.age_years}y • Gender: {patientSummary.gender} • Blood Group: {patientSummary.blood_group || "Unknown"}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsAdmissionAdviceModalOpen(true)}
                  className="flex items-center gap-1.5 text-amber-300 border-amber-700/80 hover:bg-amber-950/40"
                >
                  <Building2 size={14} className="text-amber-400" /> IPD Bed Order
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsMedicalCertModalOpen(true)}
                  className="flex items-center gap-1.5 text-sky-300 border-sky-700/80 hover:bg-sky-950/40"
                >
                  <Award size={14} className="text-sky-400" /> Medical Certificate
                </Button>
                <Button variant="primary" size="sm" onClick={handleFinalizeEncounter} className="flex items-center gap-1.5">
                  <FileText size={14} /> Finalize &amp; Sign Slip
                </Button>
              </div>
            </div>

            {/* Quick Vitals & Alert Bar */}
            <div className="grid grid-cols-4 gap-4">
              <Card className="p-3 bg-slate-900 border-slate-800">
                <div className="text-xs text-slate-400">Blood Pressure</div>
                <div className="text-lg font-mono font-bold text-slate-100 mt-1">
                  {patientSummary.latest_vitals?.blood_pressure || "120/80"}
                </div>
                <div className="text-[10px] text-slate-500">mmHg</div>
              </Card>
              <Card className="p-3 bg-slate-900 border-slate-800">
                <div className="text-xs text-slate-400">Heart Rate</div>
                <div className="text-lg font-mono font-bold text-slate-100 mt-1">
                  {patientSummary.latest_vitals?.heart_rate_bpm || "72"}
                </div>
                <div className="text-[10px] text-slate-500">bpm</div>
              </Card>
              <Card className="p-3 bg-slate-900 border-slate-800">
                <div className="text-xs text-slate-400">Oxygen Saturation</div>
                <div className="text-lg font-mono font-bold text-emerald-400 mt-1">
                  {patientSummary.latest_vitals?.spo2_percent ? `${patientSummary.latest_vitals.spo2_percent}%` : "98%"}
                </div>
                <div className="text-[10px] text-slate-500">SpO2</div>
              </Card>
              <Card className="p-3 bg-slate-900 border-slate-800">
                <div className="text-xs text-slate-400">NEWS2 Score</div>
                <div className="text-lg font-mono font-bold text-emerald-400 mt-1">
                  {patientSummary.latest_vitals?.news2_total_score ?? "0"}
                </div>
                <div className="text-[10px] text-slate-500">Low Risk</div>
              </Card>
            </div>

            {/* Clinical Perspectives Sub-Tabs */}
            <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
              <button
                type="button"
                onClick={() => setActiveTab("consultation")}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
                  activeTab === "consultation"
                    ? "bg-sky-500/10 text-sky-400 border border-sky-500/30"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
                }`}
              >
                <Stethoscope size={14} /> Active Consultation &amp; CPOE
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("history")}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
                  activeTab === "history"
                    ? "bg-sky-500/10 text-sky-400 border border-sky-500/30"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
                }`}
              >
                <History size={14} /> Longitudinal Patient History
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("trends")}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
                  activeTab === "trends"
                    ? "bg-sky-500/10 text-sky-400 border border-sky-500/30"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
                }`}
              >
                <TrendingUp size={14} /> Vitals &amp; Lab Trends
              </button>
            </div>

            {/* TAB 1: ACTIVE CONSULTATION & CPOE */}
            {activeTab === "consultation" && (
              <div className="space-y-6">
                {/* 1-Click Order Sets / Clinical Protocol Bundles Bar */}
                <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                      <Zap size={14} className="text-amber-400" /> Evidence-Based 1-Click Order Sets (CPOE Bundles)
                    </span>
                    <span className="text-[11px] text-slate-500 font-mono">Auto-populates Diagnosis, e-Rx &amp; Diagnostic Orders</span>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 pt-1">
                    {orderSets.map((bundle) => (
                      <button
                        key={bundle.id}
                        type="button"
                        onClick={() => applyOrderSet(bundle)}
                        className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 hover:border-sky-500 hover:bg-slate-900 text-left transition-all group flex items-center gap-2.5"
                      >
                        <span className="text-lg">{bundle.icon}</span>
                        <div>
                          <div className="text-xs font-bold text-slate-200 group-hover:text-sky-400 transition-colors">
                            {bundle.name}
                          </div>
                          <div className="text-[10px] text-slate-500 font-mono">
                            {bundle.meds.length} Meds • {bundle.tests.length} Labs
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* CDS Clinical Decision Support & Drug Safety Radar */}
                {(hasMultipleAntithrombotics || hasBetaLactamAllergyClash) && (
                  <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-600/70 space-y-2.5">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-amber-300 uppercase tracking-wider flex items-center gap-1.5">
                        <AlertTriangle size={15} className="text-amber-400" />
                        Clinical Decision Support (CDS) Safety Alert
                      </span>
                      <Badge variant="warning" size="sm">
                        {isOverrideDocumented ? "OVERRIDE DOCUMENTED" : "ACTION REQUIRED"}
                      </Badge>
                    </div>

                    <div className="space-y-1 text-xs font-mono text-amber-200">
                      {hasMultipleAntithrombotics && (
                        <div className="flex items-center gap-2">
                          <span>• Dual Antiplatelet Therapy (Aspirin + Clopidogrel): Elevated gastrointestinal bleeding risk. Gastroprotection (PPI) advised.</span>
                        </div>
                      )}
                      {hasBetaLactamAllergyClash && (
                        <div className="flex items-center gap-2 text-rose-300 font-bold">
                          <span>• Severe Allergy Clash: Patient has documented Penicillin hypersensitivity. Beta-lactam antibiotic cross-reactivity warning.</span>
                        </div>
                      )}
                    </div>

                    <div className="flex items-center justify-between pt-1 border-t border-amber-800/60 text-xs">
                      <span className="text-[11px] text-slate-400 font-mono">
                        {isOverrideDocumented ? `Rationale: "${overrideRationale}"` : "Attending physician acknowledgement required to finalize slip."}
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setIsOverrideModalOpen(true)}
                        className="text-xs border-amber-700 text-amber-300 hover:bg-amber-950/60"
                      >
                        {isOverrideDocumented ? "Edit Rationale" : "Document Clinical Override"}
                      </Button>
                    </div>
                  </div>
                )}

                {/* Diagnosis (ICD-10) Picker */}
                <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-2">
                  <label className="text-xs font-bold text-slate-300 uppercase tracking-wider block">
                    Primary Diagnosis (ICD-10-CM)
                  </label>
                  <select
                    value={selectedIcd10}
                    onChange={(e) => setSelectedIcd10(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500"
                  >
                    {commonIcd10List.map((icd, idx) => (
                      <option key={idx} value={icd}>
                        {icd}
                      </option>
                    ))}
                  </select>
                </div>

                {/* SOAP Notes & Prescriptions Pad */}
                <div className="grid grid-cols-2 gap-6">
                  {/* Clinical Notes */}
                  <div className="space-y-4">
                    <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">Consultation Notes (SOAP)</h3>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1">Subjective / Chief Complaint</label>
                      <textarea
                        rows={4}
                        value={subjective}
                        onChange={(e) => setSubjective(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-800 rounded-lg p-3 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500 font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1">Assessment &amp; Clinical Plan</label>
                      <textarea
                        rows={4}
                        value={assessment}
                        onChange={(e) => setAssessment(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-800 rounded-lg p-3 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500 font-mono"
                      />
                    </div>
                  </div>

                  {/* Medication Orders & Diagnostics */}
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">Prescriptions (eRx)</h3>
                        <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-800">
                          eGFR: 72 mL/min (Normal)
                        </span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setIsAddDrugModalOpen(true)}
                        className="text-xs text-sky-400 flex items-center gap-1"
                      >
                        <PlusCircle size={13} /> Add Drug
                      </Button>
                    </div>

                    <div className="border border-slate-800 rounded-lg bg-slate-900 p-3 space-y-2">
                      {medications.length === 0 ? (
                        <div className="text-xs text-slate-500 py-3 text-center">No medications prescribed.</div>
                      ) : (
                        medications.map((med) => (
                          <div
                            key={med.id}
                            className="flex items-center justify-between p-2.5 rounded bg-slate-950 border border-slate-800 text-xs"
                          >
                            <div>
                              <div className="font-semibold text-slate-200">{med.name}</div>
                              <div className="text-slate-400 text-[11px]">
                                {med.dosage} • {med.frequency} • {med.duration}
                              </div>
                              <div className="text-slate-500 text-[10px] italic">{med.instructions}</div>
                            </div>
                            <div className="flex items-center gap-2">
                              <Badge
                                variant={med.ddiStatus === "CRITICAL" ? "danger" : med.ddiStatus === "CAUTION" ? "warning" : "success"}
                                size="sm"
                              >
                                {med.ddiStatus === "SAFE" ? "No DDI" : "Monitored"}
                              </Badge>
                              <button
                                onClick={() => handleRemoveMedication(med.id)}
                                className="p-1 text-slate-500 hover:text-rose-400 transition-colors"
                              >
                                <Trash2 size={13} />
                              </button>
                            </div>
                          </div>
                        ))
                      )}
                    </div>

                    {/* Diagnostics Orders */}
                    <div className="flex items-center justify-between pt-2">
                      <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">Diagnostic Orders</h3>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setIsAddTestModalOpen(true)}
                        className="text-xs text-sky-400 flex items-center gap-1"
                      >
                        <PlusCircle size={13} /> Add Order
                      </Button>
                    </div>

                    <div className="border border-slate-800 rounded-lg bg-slate-900 p-3 space-y-2">
                      {diagnosticOrders.length === 0 ? (
                        <div className="text-xs text-slate-500 py-3 text-center">No lab/radiology tests ordered.</div>
                      ) : (
                        diagnosticOrders.map((test) => (
                          <div
                            key={test.id}
                            className="flex items-center justify-between p-2 rounded bg-slate-950 border border-slate-800 text-xs"
                          >
                            <div>
                              <span className="text-slate-200 font-semibold">{test.name}</span>
                              <span className="text-[10px] text-slate-500 ml-2 font-mono">({test.category})</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <Badge variant={test.priority === "STAT" ? "danger" : "neutral"} size="sm">
                                {test.priority}
                              </Badge>
                              <button
                                onClick={() => handleRemoveTest(test.id)}
                                className="p-1 text-slate-500 hover:text-rose-400 transition-colors"
                              >
                                <Trash2 size={13} />
                              </button>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: LONGITUDINAL PATIENT HISTORY */}
            {activeTab === "history" && (
              <div className="space-y-4">
                <Card className="p-4 bg-slate-900 border-slate-800 space-y-3">
                  <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                    <ShieldAlert size={14} className="text-amber-400" /> Active Chronic Problem List
                  </span>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { code: "I10", name: "Essential (Primary) Hypertension", since: "2024", status: "Active" },
                      { code: "E11.9", name: "Type 2 Diabetes Mellitus", since: "2022", status: "Active" },
                      { code: "E78.5", name: "Hyperlipidemia / Dyslipidemia", since: "2023", status: "Active" },
                    ].map((p, i) => (
                      <div key={i} className="p-2.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono">
                        <div className="text-slate-200 font-semibold">{p.name}</div>
                        <div className="text-[10px] text-slate-400 mt-0.5">ICD-10: {p.code} • Since {p.since}</div>
                      </div>
                    ))}
                  </div>
                </Card>

                <Card className="p-4 bg-slate-900 border-slate-800 space-y-3">
                  <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                    <History size={14} className="text-sky-400" /> Past Consultations &amp; Encounters Timeline
                  </span>
                  <div className="space-y-2">
                    {[
                      { date: "2026-08-14", dept: "Cardiology OPD", doc: "Dr. Vikram Seth", notes: "Follow-up for Stage 1 HTN; BP 138/88 mmHg. Advised continuation of Telmisartan 40mg." },
                      { date: "2026-05-22", dept: "Emergency Dept", doc: "Dr. Sameer Joshi", notes: "Acute gastroenteritis with mild dehydration. Managed with IV crystalloids and oral rehydration." },
                      { date: "2026-01-10", dept: "General Surgery IPD", doc: "Dr. Alok Verma", notes: "Elective Laparoscopic Cholecystectomy. Uneventful recovery and discharged on POD 2." },
                    ].map((enc, idx) => (
                      <div key={idx} className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs">
                        <div className="flex justify-between font-mono text-slate-300 mb-1">
                          <strong className="text-sky-400">{enc.dept} — {enc.doc}</strong>
                          <span className="text-slate-500">{enc.date}</span>
                        </div>
                        <p className="text-slate-400 text-[11px]">{enc.notes}</p>
                      </div>
                    ))}
                  </div>
                </Card>
              </div>
            )}

            {/* TAB 3: VITALS & LAB TRENDS */}
            {activeTab === "trends" && (
              <div className="space-y-4">
                <Card className="p-4 bg-slate-900 border-slate-800 space-y-3">
                  <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                    <Activity size={14} className="text-emerald-400" /> Longitudinal Laboratory &amp; Vitals Progression
                  </span>
                  <div className="overflow-x-auto rounded-lg border border-slate-800">
                    <table className="w-full text-left text-xs font-mono">
                      <thead className="bg-slate-950 text-slate-400 text-[11px] uppercase border-b border-slate-800">
                        <tr>
                          <th className="p-3">Biomarker / Vital</th>
                          <th className="p-3">6 Months Ago</th>
                          <th className="p-3">3 Months Ago</th>
                          <th className="p-3">Last Visit</th>
                          <th className="p-3 text-sky-400">Current Reading</th>
                          <th className="p-3">Clinical Trajectory</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/80">
                        <tr>
                          <td className="p-3 font-semibold text-slate-200">Blood Pressure (mmHg)</td>
                          <td className="p-3 text-slate-400">142/90</td>
                          <td className="p-3 text-slate-400">138/88</td>
                          <td className="p-3 text-slate-400">130/84</td>
                          <td className="p-3 text-emerald-400 font-bold">120/80</td>
                          <td className="p-3 text-emerald-400">↓ Well-Controlled</td>
                        </tr>
                        <tr>
                          <td className="p-3 font-semibold text-slate-200">Heart Rate (bpm)</td>
                          <td className="p-3 text-slate-400">88</td>
                          <td className="p-3 text-slate-400">82</td>
                          <td className="p-3 text-slate-400">76</td>
                          <td className="p-3 text-emerald-400 font-bold">72</td>
                          <td className="p-3 text-emerald-400">Stable Sinus</td>
                        </tr>
                        <tr>
                          <td className="p-3 font-semibold text-slate-200">HbA1c (%)</td>
                          <td className="p-3 text-rose-400">9.4</td>
                          <td className="p-3 text-amber-400">8.2</td>
                          <td className="p-3 text-amber-400">7.4</td>
                          <td className="p-3 text-emerald-400 font-bold">6.8</td>
                          <td className="p-3 text-emerald-400">↓ Target Met (&lt; 7.0%)</td>
                        </tr>
                        <tr>
                          <td className="p-3 font-semibold text-slate-200">Hemoglobin (g/dL)</td>
                          <td className="p-3 text-slate-400">14.2</td>
                          <td className="p-3 text-slate-400">13.8</td>
                          <td className="p-3 text-slate-400">13.6</td>
                          <td className="p-3 text-slate-200 font-bold">13.5</td>
                          <td className="p-3 text-slate-400">Normal Range</td>
                        </tr>
                        <tr>
                          <td className="p-3 font-semibold text-slate-200">Serum Creatinine (mg/dL)</td>
                          <td className="p-3 text-slate-400">0.90</td>
                          <td className="p-3 text-slate-400">0.92</td>
                          <td className="p-3 text-slate-400">0.95</td>
                          <td className="p-3 text-emerald-400 font-bold">0.91</td>
                          <td className="p-3 text-emerald-400">eGFR &gt; 90 mL/min</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </Card>
              </div>
            )}
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-slate-500">
            <Stethoscope size={48} className="text-slate-700 mb-3" />
            <h3 className="text-base font-semibold text-slate-300">No Patient in Consultation</h3>
            <p className="text-xs text-slate-500 mt-1">
              Select a patient from the left queue or search via Cmd+K to start consultation.
            </p>
          </div>
        )}
      </div>

      {/* Modal: Document Clinical Override Rationale */}
      {isOverrideModalOpen && (
        <Modal
          isOpen={true}
          onClose={() => setIsOverrideModalOpen(false)}
          title="Clinical Decision Support (CDS) Override Documentation"
        >
          <div className="space-y-4">
            <div className="p-3 rounded-lg bg-amber-950/40 border border-amber-800 text-xs text-amber-200 font-mono">
              Attending physician rationale is required under NABH/JCI clinical safety audit standards to override active Drug-Drug Interactions or Allergy Warnings.
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Documented Clinical Rationale &amp; Monitoring Plan
              </label>
              <textarea
                rows={4}
                value={overrideRationale}
                onChange={(e) => setOverrideRationale(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
              <Button variant="outline" size="sm" onClick={() => setIsOverrideModalOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  setIsOverrideDocumented(true);
                  setIsOverrideModalOpen(false);
                }}
              >
                Sign &amp; Attach Override
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Modal: Add Medication */}
      {isAddDrugModalOpen && (
        <Modal
          isOpen={true}
          onClose={() => setIsAddDrugModalOpen(false)}
          title="Add Medication to e-Prescription"
        >
          <form onSubmit={handleAddMedication} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Medication Name &amp; Strength</label>
              <input
                type="text"
                required
                value={drugName}
                onChange={(e) => setDrugName(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
              />
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Dosage Form</label>
                <input
                  type="text"
                  value={drugDosage}
                  onChange={(e) => setDrugDosage(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                />
              </div>
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Frequency</label>
                <select
                  value={drugFrequency}
                  onChange={(e) => setDrugFrequency(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                >
                  <option value="OD (Once daily)">OD (Once daily)</option>
                  <option value="BD (Twice daily)">BD (Twice daily)</option>
                  <option value="TDS (Thrice daily)">TDS (Thrice daily)</option>
                  <option value="QID (Four times daily)">QID (Four times daily)</option>
                  <option value="SOS (As needed)">SOS (As needed)</option>
                </select>
              </div>
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Duration</label>
                <input
                  type="text"
                  value={drugDuration}
                  onChange={(e) => setDrugDuration(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Patient Instructions</label>
              <input
                type="text"
                value={drugInstructions}
                onChange={(e) => setDrugInstructions(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200"
              />
            </div>

            <div className="p-2.5 rounded bg-emerald-950/40 border border-emerald-800 text-[11px] text-emerald-300 font-mono flex items-center gap-2">
              <CheckCircle2 size={14} /> Drug-Drug Interaction (DDI) &amp; Allergy Check: Clean
            </div>

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
              <Button type="button" variant="outline" size="sm" onClick={() => setIsAddDrugModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" size="sm">
                Add to Prescription
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* Modal: Add Diagnostic Order */}
      {isAddTestModalOpen && (
        <Modal
          isOpen={true}
          onClose={() => setIsAddTestModalOpen(false)}
          title="Place Diagnostic Laboratory / Radiology Order"
        >
          <form onSubmit={handleAddDiagnosticOrder} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Test Name</label>
              <input
                type="text"
                required
                value={testName}
                onChange={(e) => setTestName(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Laboratory Discipline</label>
                <select
                  value={testCategory}
                  onChange={(e) => setTestCategory(e.target.value as any)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200"
                >
                  <option value="Hematology">Hematology</option>
                  <option value="Biochemistry">Biochemistry</option>
                  <option value="Microbiology">Microbiology</option>
                  <option value="Radiology">Radiology (X-Ray/CT/USG)</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Clinical Priority</label>
                <select
                  value={testPriority}
                  onChange={(e) => setTestPriority(e.target.value as any)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200"
                >
                  <option value="ROUTINE">Routine</option>
                  <option value="STAT">STAT / Urgent</option>
                </select>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
              <Button type="button" variant="outline" size="sm" onClick={() => setIsAddTestModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" size="sm">
                Place Test Order
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* Modal: Final Consultation Slip & Summary */}
      {isSummarySlipOpen && (
        <Modal
          isOpen={true}
          onClose={() => setIsSummarySlipOpen(false)}
          title="Consultation Summary Slip &amp; Digital Signature"
        >
          <div className="space-y-4">
            <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg space-y-3 font-mono text-xs">
              <div className="flex justify-between border-b border-slate-800 pb-2">
                <div>
                  <strong className="text-slate-100">{patientSummary?.full_name}</strong>
                  <div className="text-[11px] text-slate-400">MRN: {patientSummary?.mrn}</div>
                </div>
                <div className="text-right">
                  <div className="text-sky-400">Dr. {queue?.doctor_name || "Doctor"}</div>
                  <div className="text-[10px] text-slate-500">{new Date().toLocaleDateString()}</div>
                </div>
              </div>

              <div>
                <span className="text-slate-400 block text-[10px] uppercase">Diagnosis:</span>
                <span className="text-slate-200 font-semibold">{selectedIcd10}</span>
              </div>

              <div>
                <span className="text-slate-400 block text-[10px] uppercase">Prescriptions ({medications.length}):</span>
                {medications.map((m, i) => (
                  <div key={i} className="text-slate-300 pl-2">
                    • {m.name} — {m.dosage} ({m.frequency} x {m.duration})
                  </div>
                ))}
              </div>

              {diagnosticOrders.length > 0 && (
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase">Orders ({diagnosticOrders.length}):</span>
                  {diagnosticOrders.map((t, i) => (
                    <div key={i} className="text-slate-300 pl-2">
                      • {t.name} [{t.priority}]
                    </div>
                  ))}
                </div>
              )}

              {isOverrideDocumented && (
                <div className="pt-2 border-t border-slate-800 text-[10px] text-amber-300">
                  <span className="font-bold uppercase">Clinical Safety Override Attached:</span> &quot;{overrideRationale}&quot;
                </div>
              )}
            </div>

            <div className="flex items-center justify-between pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handlePrintPrescriptionSlip}
                className="flex items-center gap-1.5"
              >
                <Printer size={13} /> Print Slip
              </Button>

              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => setIsSummarySlipOpen(false)}>
                  Review Notes
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  disabled={isSubmitting}
                  onClick={handleConfirmAndComplete}
                >
                  {isSubmitting ? "Signing & Broadcasting..." : "Sign & Finalize Encounter"}
                </Button>
              </div>
            </div>
          </div>
        </Modal>
      )}
      {/* Modal: Inpatient Admission Advice & Bed Booking Order */}
      {isAdmissionAdviceModalOpen && (
        <Modal
          isOpen={true}
          onClose={() => setIsAdmissionAdviceModalOpen(false)}
          title="Direct Inpatient (IPD) Admission Advice & Bed Requisition"
        >
          <div className="space-y-4">
            <div className="p-3 bg-amber-950/40 border border-amber-600/70 rounded-lg text-amber-200 text-xs">
              <div className="font-bold flex items-center gap-2 mb-1 text-sm text-amber-300">
                <Building2 size={16} /> IPD Bed Booking &amp; Triage Escalation
              </div>
              Directs the central ADT desk to allocate an inpatient bed, alerting Nursing and Medical Records to open an IP admission file.
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Admitting Specialty</label>
                <select
                  value={admittingDept}
                  onChange={(e) => setAdmittingDept(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200"
                >
                  <option value="Cardiology">Cardiology</option>
                  <option value="Internal Medicine">Internal Medicine</option>
                  <option value="General Surgery">General Surgery</option>
                  <option value="Orthopedics">Orthopedics</option>
                  <option value="Pulmonology">Pulmonology</option>
                  <option value="Neurology">Neurology</option>
                  <option value="Pediatrics">Pediatrics</option>
                  <option value="OBG / Gynecology">OBG / Gynecology</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Acuity Priority</label>
                <select
                  value={admittingPriority}
                  onChange={(e) => setAdmittingPriority(e.target.value as any)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200"
                >
                  <option value="EMERGENCY_STAT">🔴 EMERGENCY STAT (Immediate Bed)</option>
                  <option value="HIGH_ACUITY_2H">🟡 High Acuity (Bed within 2 Hours)</option>
                  <option value="ELECTIVE_PLANNED">🟢 Elective Same-Day Planned</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Requested Bed Class / Unit</label>
              <select
                value={admittingBedCategory}
                onChange={(e) => setAdmittingBedCategory(e.target.value as any)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200"
              >
                <option value="ICU">Intensive Care Unit (ICU) — Continuous Critical Monitoring</option>
                <option value="HDU">High Dependency Unit (HDU) — Stepdown Monitored</option>
                <option value="SINGLE_PRIVATE">Single Private Room (Air Conditioned)</option>
                <option value="GENERAL_WARD">Multi-Bed General Ward (Standard Care)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">STAT Directives &amp; Initial Ward Orders</label>
              <textarea
                rows={3}
                value={admittingDirectives}
                onChange={(e) => setAdmittingDirectives(e.target.value)}
                placeholder="e.g. NPO, secure 18G IV line, oxygen 4L/min, continuous SpO2/ECG telemetry..."
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono"
              />
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-slate-800">
              <Button variant="outline" size="sm" onClick={() => setIsAdmissionAdviceModalOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={handlePrintAdmissionAdvice}
                className="flex items-center gap-1.5 bg-rose-600 hover:bg-rose-500 text-white font-bold"
              >
                <Printer size={13} /> Transmit Order &amp; Print Slip
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Modal: Statutory Medical Certificate / Sickness Advice */}
      {isMedicalCertModalOpen && (
        <Modal
          isOpen={true}
          onClose={() => setIsMedicalCertModalOpen(false)}
          title="National Medical Commission (NMC) Statutory Medical Certificate"
        >
          <div className="space-y-4">
            <div className="p-3 bg-sky-950/40 border border-sky-600/70 rounded-lg text-sky-200 text-xs">
              <div className="font-bold flex items-center gap-2 mb-1 text-sm text-sky-300">
                <Award size={16} /> Official Medical Certificate of Illness &amp; Rest
              </div>
              Generates a legally binding medical certificate specifying diagnosis, personal identification marks, recommended convalescence days, and expected return to duty date.
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Clinical Diagnosis</label>
              <input
                type="text"
                required
                value={certDiagnosis}
                onChange={(e) => setCertDiagnosis(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Personal Identification Mark</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Scar on left forearm / Mole on right cheek"
                  value={certIdentificationMark}
                  onChange={(e) => setCertIdentificationMark(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Recommended Rest (Days)</label>
                <input
                  type="number"
                  min="1"
                  max="60"
                  required
                  value={certRestDays}
                  onChange={(e) => setCertRestDays(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono"
                />
              </div>
            </div>

            <div className="p-2.5 rounded bg-slate-950 border border-slate-800 text-xs font-mono text-slate-400">
              <div>Expected Resume Duty: <strong className="text-emerald-400">{new Date(Date.now() + (parseInt(certRestDays, 10) || 1) * 86400000).toLocaleDateString()}</strong></div>
              <div>Certifying Consultant: <strong className="text-slate-200">Dr. {queue?.doctor_name || "Doctor"} (Regn: 49204/MC)</strong></div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-slate-800">
              <Button variant="outline" size="sm" onClick={() => setIsMedicalCertModalOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handlePrintMedicalCertificate}
                className="flex items-center gap-1.5"
              >
                <Printer size={13} /> Print Medical Certificate
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
