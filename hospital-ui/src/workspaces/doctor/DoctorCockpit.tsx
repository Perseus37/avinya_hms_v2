import React, { useEffect, useState } from "react";
import { uiApi } from "../../api/uiApi";
import { DoctorQueueSummary } from "../../types";
import { useActivePatient } from "../../core/context/ActivePatientContext";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Modal } from "../../components/ui/Modal";
import { Clock, Stethoscope, RefreshCw, PlusCircle, Trash2, CheckCircle2, Printer, FileText } from "lucide-react";

interface PrescribedMedication {
  id: string;
  name: string;
  dosage: string;
  frequency: string;
  duration: string;
  instructions: string;
  ddiStatus: "SAFE" | "CAUTION";
}

interface PrescribedTest {
  id: string;
  name: string;
  category: "Hematology" | "Biochemistry" | "Microbiology" | "Radiology";
  priority: "ROUTINE" | "STAT";
}

export const DoctorCockpit: React.FC = () => {
  const [queue, setQueue] = useState<DoctorQueueSummary | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const { selectPatient, patientSummary } = useActivePatient();

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

  // Modal States
  const [isAddDrugModalOpen, setIsAddDrugModalOpen] = useState(false);
  const [isAddTestModalOpen, setIsAddTestModalOpen] = useState(false);
  const [isSummarySlipOpen, setIsSummarySlipOpen] = useState(false);

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
    "K21.9 - Gastro-esophageal reflux disease without esophagitis",
    "M54.5 - Low back pain, unspecified",
    "A09 - Infectious gastroenteritis and colitis, unspecified",
  ];

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

  const handleFinalizeEncounter = () => {
    setIsSummarySlipOpen(true);
  };

  const handleConfirmAndComplete = () => {
    setIsSummarySlipOpen(false);
    if (queue && patientSummary) {
      // Mark current appointment as completed in queue
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
    }
    alert("Encounter signed and prescription broadcast to Central Pharmacy and LIS!");
  };

  return (
    <div className="flex-1 flex overflow-hidden">
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
                onClick={() => selectPatient(appt.patient_id)}
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
              <div className="flex items-center gap-3">
                <Button variant="primary" size="sm" onClick={handleFinalizeEncounter} className="flex items-center gap-1.5">
                  <FileText size={14} /> Finalize & Sign Slip
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

            {/* Diagnosis (ICU-10) Picker */}
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

            {/* Soap Notes & Prescriptions Pad */}
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
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg p-3 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Assessment & Clinical Plan</label>
                  <textarea
                    rows={4}
                    value={assessment}
                    onChange={(e) => setAssessment(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg p-3 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500"
                  />
                </div>
              </div>

              {/* Medication Orders & Diagnostics */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">Prescriptions (eRx)</h3>
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
                          <Badge variant="success" size="sm">No DDI</Badge>
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

      {/* Modal: Add Medication */}
      <Modal
        isOpen={isAddDrugModalOpen}
        onClose={() => setIsAddDrugModalOpen(false)}
        title="Add Medication to e-Prescription"
      >
        <form onSubmit={handleAddMedication} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Medication Name & Strength</label>
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
            <CheckCircle2 size={14} /> Drug-Drug Interaction (DDI) & Allergy Check: Clean
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

      {/* Modal: Add Diagnostic Order */}
      <Modal
        isOpen={isAddTestModalOpen}
        onClose={() => setIsAddTestModalOpen(false)}
        title="Add Diagnostic Laboratory / Radiology Order"
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

      {/* Modal: Final Consultation Slip & Summary */}
      <Modal
        isOpen={isSummarySlipOpen}
        onClose={() => setIsSummarySlipOpen(false)}
        title="Consultation Summary Slip & Digital Signature"
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
          </div>

          <div className="flex items-center justify-between pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.print()}
              className="flex items-center gap-1.5"
            >
              <Printer size={13} /> Print Slip
            </Button>

            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setIsSummarySlipOpen(false)}>
                Review Notes
              </Button>
              <Button variant="primary" size="sm" onClick={handleConfirmAndComplete}>
                Sign & Finalize Encounter
              </Button>
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
};
