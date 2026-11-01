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
} from "lucide-react";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { useActivePatient } from "../../core/context/ActivePatientContext";

interface AvailableBedOption {
  bedId: number;
  bedNumber: string;
  roomNumber: string;
  wardName: string;
  dailyTariffRupees: number;
  category: "General" | "Semi-Private" | "Private" | "ICU";
  features: string[];
}

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

  // Available Beds Pool
  const [availableBeds] = useState<AvailableBedOption[]>([
    { bedId: 201, bedNumber: "B-102", roomNumber: "R-101", wardName: "General Ward 1", dailyTariffRupees: 2500, category: "General", features: ["O2 Wall Outlet", "Call Bell"] },
    { bedId: 202, bedNumber: "B-103", roomNumber: "R-102", wardName: "General Ward 1", dailyTariffRupees: 2500, category: "General", features: ["O2 Wall Outlet", "Call Bell"] },
    { bedId: 203, bedNumber: "SP-201", roomNumber: "R-201", wardName: "Semi-Private Ward", dailyTariffRupees: 4500, category: "Semi-Private", features: ["Air Conditioned", "Attached Bath"] },
    { bedId: 204, bedNumber: "PV-301", roomNumber: "R-301", wardName: "Private Deluxe Suite", dailyTariffRupees: 7500, category: "Private", features: ["Attendant Couch", "Smart TV", "Mini Fridge"] },
    { bedId: 205, bedNumber: "ICU-05", roomNumber: "ICU-BAY-B", wardName: "Intensive Care Unit", dailyTariffRupees: 12000, category: "ICU", features: ["Ventilator Ready", "Invasive Arterial Line", "Cardiac Monitor"] },
  ]);

  const [bedCategoryFilter, setBedCategoryFilter] = useState<"ALL" | "General" | "Semi-Private" | "Private" | "ICU">("ALL");

  // Form State
  const [targetPatientName, setTargetPatientName] = useState(patientSummary?.full_name || "Siddharth Verma");
  const [targetMrn, setTargetMrn] = useState(patientSummary?.mrn || "MRN-2026-0001");
  const [admissionType, setAdmissionType] = useState<"EMERGENCY" | "ELECTIVE" | "DAYCARE" | "MATERNITY" | "ICU_TRANSFER">("ELECTIVE");
  const [selectedBedId, setSelectedBedId] = useState<number>(201);
  const [admittingDoctor, setAdmittingDoctor] = useState("Dr. Vikram Seth (Cardiology)");
  const [admissionDiagnosis, setAdmissionDiagnosis] = useState("Unstable Angina Pectoris • Coronary Angiography Planned");
  
  // MLC State
  const [isMlc, setIsMlc] = useState(false);
  const [policeStation, setPoliceStation] = useState("");
  const [mlcNumber, setMlcNumber] = useState("");

  // Insurance State
  const [hasInsurance, setHasInsurance] = useState(true);
  const [payerName, setPayerName] = useState("Star Health Insurance");
  const [preAuthAmount, setPreAuthAmount] = useState("150000");

  // Bed Transfer State
  const [isTransferModalOpen, setIsTransferModalOpen] = useState(false);
  const [transferringAdmission, setTransferringAdmission] = useState<ActiveAdmissionItem | null>(null);
  const [transferDestinationBedId, setTransferDestinationBedId] = useState<number>(202);
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

  useEffect(() => {
    if (patientSummary) {
      setTargetPatientName(patientSummary.full_name);
      setTargetMrn(patientSummary.mrn);
    }
  }, [patientSummary]);

  const handleAdmissionSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage("");

    const chosenBed = availableBeds.find((b) => b.bedId === selectedBedId);
    if (!chosenBed) {
      setErrorMessage("Please select an available bed from the matrix.");
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
    const firstOther = availableBeds.find((b) => b.bedNumber !== adm.bedNumber);
    if (firstOther) {
      setTransferDestinationBedId(firstOther.bedId);
    }
    setIsTransferModalOpen(true);
  };

  const handleExecuteTransfer = (e: React.FormEvent) => {
    e.preventDefault();
    if (!transferringAdmission) return;
    const destBed = availableBeds.find((b) => b.bedId === transferDestinationBedId);
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
          {/* Patient Selection Banner */}
          <Card className="p-4 bg-slate-900/80 border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <User size={14} className="text-sky-400" /> Patient For Inpatient Admission
              </span>
              <span className="text-[11px] font-mono text-sky-400">
                {patientSummary ? "Active CCOW Context" : "Manual Selection"}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Patient Full Name</label>
                <input
                  type="text"
                  required
                  value={targetPatientName}
                  onChange={(e) => setTargetPatientName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500 font-semibold"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">UHID / MRN</label>
                <input
                  type="text"
                  required
                  value={targetMrn}
                  onChange={(e) => setTargetMrn(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500"
                />
              </div>
            </div>
          </Card>

          {/* Clinical Admission Details */}
          <Card className="p-4 bg-slate-900/80 border-slate-800 space-y-4">
            <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <Activity size={14} className="text-emerald-400" /> Admission Parameters & Clinical Specialty
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

          {/* Interactive Bed Matrix Selection */}
          <Card className="p-4 bg-slate-900/80 border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <BedDouble size={14} className="text-sky-400" /> Select Target Available Bed
              </h2>
              <span className="text-[11px] font-mono text-emerald-400">{availableBeds.length} Vacant Beds Ready</span>
            </div>

            {/* Category Filter Pills */}
            <div className="flex items-center gap-1.5 pt-1">
              {(["ALL", "General", "Semi-Private", "Private", "ICU"] as const).map((cat) => {
                const count = cat === "ALL" ? availableBeds.length : availableBeds.filter((b) => b.category === cat).length;
                return (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => setBedCategoryFilter(cat)}
                    className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold transition-all ${
                      bedCategoryFilter === cat
                        ? "bg-sky-500/20 text-sky-400 border border-sky-500/40"
                        : "bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800"
                    }`}
                  >
                    {cat} ({count})
                  </button>
                );
              })}
            </div>

            <div className="grid grid-cols-3 gap-3">
              {(bedCategoryFilter === "ALL"
                ? availableBeds
                : availableBeds.filter((b) => b.category === bedCategoryFilter)
              ).map((bed) => {
                const isSelected = selectedBedId === bed.bedId;
                return (
                  <div
                    key={bed.bedId}
                    onClick={() => setSelectedBedId(bed.bedId)}
                    className={`p-3 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? "bg-sky-950/60 border-sky-400 ring-2 ring-sky-500/50 shadow-lg"
                        : "bg-slate-950 border-slate-800 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-bold text-xs text-slate-100 font-mono">Bed {bed.bedNumber}</span>
                      <Badge variant={bed.category === "ICU" ? "danger" : "info"} size="sm">
                        {bed.category}
                      </Badge>
                    </div>
                    <div className="text-[11px] text-slate-400">{bed.wardName}</div>
                    <div className="text-[10px] text-slate-500 font-mono mt-0.5">Room: {bed.roomNumber}</div>

                    {bed.features && bed.features.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {bed.features.map((f, i) => (
                          <span key={i} className="px-1.5 py-0.5 rounded text-[9px] bg-slate-900 text-slate-400 border border-slate-800 font-mono">
                            {f}
                          </span>
                        ))}
                      </div>
                    )}

                    <div className="mt-2 pt-1.5 border-t border-slate-800 flex justify-between items-center text-[11px] font-mono">
                      <span className="text-slate-400">Tariff:</span>
                      <span className="text-emerald-400 font-bold">₹{bed.dailyTariffRupees.toLocaleString()}/day</span>
                    </div>
                  </div>
                );
              })}
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

          <div className="flex items-center justify-end gap-3 pt-2">
            <Button
              type="submit"
              variant="primary"
              size="lg"
              className="flex items-center gap-2 font-bold px-6"
            >
              <DoorOpen size={16} /> Confirm Admission & Lock Bed
            </Button>
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
                {availableBeds
                  .filter((b) => b.bedNumber !== transferringAdmission.bedNumber)
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

      {/* Modal: Printable Formal Discharge Summary */}
      {lastDischargedRecord && (
        <Modal
          isOpen={isDischargeSummaryOpen}
          onClose={() => setIsDischargeSummaryOpen(false)}
          title="Clinical Discharge Summary Slip"
        >
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3 font-mono text-xs">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <div>
                  <span className="text-slate-400 text-[10px] uppercase block">Hospital Discharge Document</span>
                  <span className="font-bold text-emerald-400">DISCHARGE #{lastDischargedRecord.admission.id}</span>
                </div>
                <div className="text-right">
                  <span className="text-slate-400 text-[10px] uppercase block">Disposition</span>
                  <span className="font-bold text-sky-400">{lastDischargedRecord.disposition}</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-slate-500 text-[10px] block">Patient Name</span>
                  <span className="text-slate-200 font-semibold">{lastDischargedRecord.admission.patientName}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] block">UHID / MRN</span>
                  <span className="text-slate-200">{lastDischargedRecord.admission.mrn}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] block">Admission Ward / Bed</span>
                  <span className="text-slate-200">{lastDischargedRecord.admission.ward} ({lastDischargedRecord.admission.bedNumber})</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] block">Discharge Time</span>
                  <span className="text-slate-200">{lastDischargedRecord.dischargedAt}</span>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-800">
                <span className="text-slate-400 text-[10px] uppercase block mb-1">Clinical Advice / Course in Hospital</span>
                <p className="text-slate-200 bg-slate-900 p-2.5 rounded text-[11px] leading-relaxed">
                  {lastDischargedRecord.summaryNotes}
                </p>
              </div>

              <div className="flex items-center justify-between pt-1">
                <span className="text-slate-400 text-[11px]">Recommended Follow-up:</span>
                <span className="text-sky-400 font-bold">{lastDischargedRecord.followup}</span>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => window.print()}
                className="flex items-center gap-1.5"
              >
                <Printer size={13} /> Print Discharge Summary
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

      {/* Modal: Inpatient Admission Confirmation & Bed Head Ticket */}
      {confirmedAdmission && (
        <Modal
          isOpen={isSuccessModalOpen}
          onClose={() => setIsSuccessModalOpen(false)}
          title="Inpatient Admission Confirmed & Bed Assigned"
        >
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3 font-mono text-xs">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <div>
                  <span className="text-slate-400 text-[10px] uppercase block">Admission ID</span>
                  <span className="font-bold text-emerald-400">ADM-{confirmedAdmission.id}</span>
                </div>
                <div className="text-right">
                  <span className="text-slate-400 text-[10px] uppercase block">Assigned Bed</span>
                  <span className="font-bold text-sky-400 text-sm">
                    {confirmedAdmission.bedNumber} ({confirmedAdmission.roomNumber})
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-slate-500 text-[10px] block">Patient Name</span>
                  <span className="text-slate-200 font-semibold">{confirmedAdmission.patientName}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] block">MRN / UHID</span>
                  <span className="text-slate-200">{confirmedAdmission.mrn}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] block">Ward</span>
                  <span className="text-slate-200">{confirmedAdmission.ward}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] block">Admitted At</span>
                  <span className="text-slate-200">{confirmedAdmission.admittedAt}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => window.print()}
                className="flex items-center gap-1.5"
              >
                <Printer size={13} /> Print Bed Head Ticket (BHT)
              </Button>

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
