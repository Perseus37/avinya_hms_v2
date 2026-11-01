import React, { useState } from "react";
import {
  Siren,
  Clock,
  User,
  PlusCircle,
  AlertOctagon,
  Activity,
  ShieldAlert,
  Printer,
} from "lucide-react";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { useActivePatient } from "../../core/context/ActivePatientContext";

interface EmergencyCase {
  id: number;
  name: string;
  mrn: string;
  arrival: string;
  complaint: string;
  vitals: string;
  esi: number;
  isMlc?: boolean;
  gcs?: number;
  eyeScore?: number;
  verbalScore?: number;
  motorScore?: number;
  mlcNumber?: string;
  policeStation?: string;
  policeBuckleNo?: string;
}

export const EDTriageBoard: React.FC = () => {
  const { selectPatient } = useActivePatient();
  const [cases, setCases] = useState<EmergencyCase[]>([
    {
      id: 101,
      name: "Unknown Trauma Male",
      mrn: "ER-0912",
      arrival: "4m ago",
      complaint: "Cardiac arrest post RTA two-wheeler collision",
      vitals: "BP 60/40, HR 140, SpO2 78%",
      esi: 1,
      isMlc: true,
      gcs: 3,
      eyeScore: 1,
      verbalScore: 1,
      motorScore: 1,
      mlcNumber: "MLC-20261101-9F2B",
      policeStation: "Central Police Station, Division B",
      policeBuckleNo: "PC-4882",
    },
    {
      id: 102,
      name: "Ananya Deshmukh",
      mrn: "ER-0914",
      arrival: "12m ago",
      complaint: "Severe crushing chest pain radiating to left arm",
      vitals: "BP 160/95, HR 105, SpO2 93%",
      esi: 2,
      gcs: 15,
      eyeScore: 4,
      verbalScore: 5,
      motorScore: 6,
    },
    {
      id: 103,
      name: "Harish Rao",
      mrn: "ER-0915",
      arrival: "28m ago",
      complaint: "Acute right lower quadrant abdominal pain, febrile",
      vitals: "BP 130/80, HR 92, Temp 102.4F",
      esi: 3,
      gcs: 15,
      eyeScore: 4,
      verbalScore: 5,
      motorScore: 6,
    },
    {
      id: 104,
      name: "Pooja Nair",
      mrn: "ER-0918",
      arrival: "45m ago",
      complaint: "Right wrist deformity & pain after mechanical fall",
      vitals: "BP 120/78, HR 76, SpO2 99%",
      esi: 4,
      gcs: 15,
      eyeScore: 4,
      verbalScore: 5,
      motorScore: 6,
    },
    {
      id: 105,
      name: "Manoj Kumar",
      mrn: "ER-0920",
      arrival: "1h 10m ago",
      complaint: "Suture removal, anti-rabies vaccine booster (Day 7)",
      vitals: "BP 118/74, HR 72, SpO2 99%",
      esi: 5,
      gcs: 15,
      eyeScore: 4,
      verbalScore: 5,
      motorScore: 6,
    },
  ]);

  const [isTriageModalOpen, setIsTriageModalOpen] = useState(false);
  const [isRedAlertActive, setIsRedAlertActive] = useState(false);
  const [selectedCaseForPrint, setSelectedCaseForPrint] = useState<EmergencyCase | null>(null);
  const [selectedCaseForMlc, setSelectedCaseForMlc] = useState<EmergencyCase | null>(null);

  // New Triage Patient Form State
  const [patientName, setPatientName] = useState("");
  const [patientGender, setPatientGender] = useState("Male");
  const [complaint, setComplaint] = useState("");
  const [bp, setBp] = useState("120/80");
  const [hr, setHr] = useState("80");
  const [spo2, setSpo2] = useState("98");
  const [temp, setTemp] = useState("98.6");
  const [selectedEsi, setSelectedEsi] = useState<number>(3);
  const [isMlc, setIsMlc] = useState(false);
  const [policeStationInput, setPoliceStationInput] = useState("Central Traffic Police Station");
  const [policeBuckleInput, setPoliceBuckleInput] = useState("PC-1049");
  const [eyeScore, setEyeScore] = useState(4);
  const [verbalScore, setVerbalScore] = useState(5);
  const [motorScore, setMotorScore] = useState(6);

  const totalGcs = eyeScore + verbalScore + motorScore;

  const handleCreateTriage = (e: React.FormEvent) => {
    e.preventDefault();
    const finalName = patientName.trim() || `Unknown Emergency Patient ${cases.length + 1}`;
    const newId = 100 + cases.length + 1;
    const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, "");

    const newCase: EmergencyCase = {
      id: newId,
      name: finalName,
      mrn: `ER-${newId.toString().padStart(4, "0")}`,
      arrival: "Just now",
      complaint: complaint || "Undifferentiated emergency presentation",
      vitals: `BP ${bp}, HR ${hr}, SpO2 ${spo2}%`,
      esi: selectedEsi,
      isMlc,
      gcs: totalGcs,
      eyeScore,
      verbalScore,
      motorScore,
      mlcNumber: isMlc ? `MLC-${dateStr}-${Math.random().toString(36).substring(2, 6).toUpperCase()}` : undefined,
      policeStation: isMlc ? policeStationInput : undefined,
      policeBuckleNo: isMlc ? policeBuckleInput : undefined,
    };

    setCases((prev) => [newCase, ...prev]);
    setIsTriageModalOpen(false);

    // Reset Form
    setPatientName("");
    setComplaint("");
    setIsMlc(false);
  };

  const moveEsi = (caseId: number, targetEsi: number) => {
    setCases((prev) =>
      prev.map((c) => (c.id === caseId ? { ...c, esi: targetEsi } : c))
    );
  };

  const dischargeOrTransferCase = (caseId: number) => {
    setCases((prev) => prev.filter((c) => c.id !== caseId));
  };

  const esiDefinitions = [
    {
      level: 1,
      title: "Resuscitation (ESI 1)",
      sub: "Immediate life-saving intervention required",
      color: "border-rose-500 bg-rose-950/20 text-rose-400",
      badgeColor: "danger" as const,
    },
    {
      level: 2,
      title: "Emergent (ESI 2)",
      sub: "High risk, confusional state, or severe pain/distress",
      color: "border-orange-500 bg-orange-950/20 text-orange-400",
      badgeColor: "warning" as const,
    },
    {
      level: 3,
      title: "Urgent (ESI 3)",
      sub: "Multiple resources needed (Labs, IV, Imaging)",
      color: "border-amber-500 bg-amber-950/20 text-amber-400",
      badgeColor: "warning" as const,
    },
    {
      level: 4,
      title: "Less Urgent (ESI 4)",
      sub: "One clinical resource needed (e.g. X-ray only)",
      color: "border-emerald-500 bg-emerald-950/20 text-emerald-400",
      badgeColor: "success" as const,
    },
    {
      level: 5,
      title: "Non-Urgent (ESI 5)",
      sub: "No resources needed (Physical exam or Rx refill)",
      color: "border-sky-500 bg-sky-950/20 text-sky-400",
      badgeColor: "info" as const,
    },
  ];

  return (
    <div className="flex-1 flex flex-col bg-slate-950 p-6 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between pb-6 border-b border-slate-800">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <Siren className="text-rose-500 animate-pulse" />
            Emergency Department (ED) Triage &amp; Trauma Board
          </h1>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            ESI 1-5 Severity Stratification • Door-to-Doctor Velocity • Medico-Legal Case (MLC) Registry
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant={isRedAlertActive ? "danger" : "outline"}
            size="sm"
            onClick={() => setIsRedAlertActive(!isRedAlertActive)}
            className="flex items-center gap-2 font-mono"
          >
            <AlertOctagon size={14} className={isRedAlertActive ? "animate-spin" : ""} />
            {isRedAlertActive ? "🔴 CODE RED ACTIVE (Trauma Team)" : "Trigger Code Red (Trauma Alert)"}
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsTriageModalOpen(true)}
            className="flex items-center gap-2"
          >
            <PlusCircle size={15} /> Intake &amp; Triage Patient
          </Button>
        </div>
      </div>

      {/* Code Red Banner if active */}
      {isRedAlertActive && (
        <div className="mt-4 p-3 rounded-lg bg-rose-950/50 border border-rose-500/80 flex items-center justify-between text-rose-300 animate-pulse text-xs font-mono">
          <div className="flex items-center gap-2">
            <Siren size={18} className="text-rose-400" />
            <span>
              <strong>HOSPITAL CODE RED:</strong> Trauma Resuscitation Bay 1 Activated. Blood Bank &amp; Anesthesia paged.
            </span>
          </div>
          <button
            onClick={() => setIsRedAlertActive(false)}
            className="px-2 py-0.5 rounded bg-rose-900 hover:bg-rose-800 text-[11px] font-bold text-white uppercase"
          >
            Stand Down
          </button>
        </div>
      )}

      {/* Kanban 5 Columns */}
      <div className="flex-1 grid grid-cols-5 gap-3 mt-6 overflow-hidden">
        {esiDefinitions.map((col) => {
          const colCases = cases.filter((c) => c.esi === col.level);

          return (
            <div
              key={col.level}
              className="flex flex-col rounded-xl bg-slate-900/60 border border-slate-800 p-3 overflow-hidden"
            >
              <div
                className={`p-2.5 rounded-lg border font-semibold text-xs mb-3 flex items-center justify-between ${col.color}`}
              >
                <div>
                  <div className="font-bold">{col.title}</div>
                  <div className="text-[10px] opacity-80 font-normal">{col.sub}</div>
                </div>
                <span className="font-mono font-bold text-[12px] bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                  {colCases.length}
                </span>
              </div>

              <div className="flex-1 overflow-y-auto space-y-2 pr-1">
                {colCases.length === 0 ? (
                  <div className="h-28 flex items-center justify-center text-[11px] text-slate-600 border border-dashed border-slate-800/80 rounded-lg">
                    No active cases
                  </div>
                ) : (
                  colCases.map((c) => (
                    <Card
                      key={c.id}
                      onClick={() => selectPatient(c.id)}
                      className="p-3 bg-slate-900 border-slate-800 hover:border-slate-700 cursor-pointer transition-all shadow-sm group"
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="font-semibold text-xs text-slate-200 flex items-center gap-1.5">
                          <User size={13} className="text-slate-400" />
                          {c.name}
                        </span>
                        <span className="font-mono text-[10px] text-slate-400">{c.mrn}</span>
                      </div>

                      <div className="text-[11px] text-slate-300 italic mb-2 line-clamp-2">
                        &quot;{c.complaint}&quot;
                      </div>

                      <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1.5 border-t border-slate-800/80 mb-2">
                        <span className="font-mono text-sky-400">{c.vitals}</span>
                        {c.gcs && (
                          <span className="font-mono text-amber-400">GCS {c.gcs}/15</span>
                        )}
                      </div>

                      <div className="flex items-center justify-between pt-1 border-t border-slate-800/50">
                        <div className="flex items-center gap-1">
                          <Badge variant="neutral" size="sm" className="flex items-center gap-1">
                            <Clock size={10} /> {c.arrival}
                          </Badge>
                          {c.isMlc && (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setSelectedCaseForMlc(c);
                              }}
                              className="px-1 py-0.5 rounded bg-rose-950 text-rose-400 border border-rose-800 text-[9px] font-bold flex items-center gap-0.5 hover:bg-rose-900"
                              title="View Police Intimation Form"
                            >
                              <ShieldAlert size={9} /> MLC
                            </button>
                          )}
                        </div>

                        {/* Fast Actions */}
                        <div className="flex items-center gap-1 opacity-80 group-hover:opacity-100">
                          <button
                            title="Print Triage Slip"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedCaseForPrint(c);
                            }}
                            className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
                          >
                            <Printer size={11} />
                          </button>
                          {col.level > 1 && (
                            <button
                              title="Escalate ESI Severity"
                              onClick={(e) => {
                                e.stopPropagation();
                                moveEsi(c.id, col.level - 1);
                              }}
                              className="px-1 text-[10px] bg-rose-950 text-rose-400 hover:bg-rose-900 rounded border border-rose-800 font-bold"
                            >
                              ▲
                            </button>
                          )}
                          {col.level < 5 && (
                            <button
                              title="De-escalate ESI Severity"
                              onClick={(e) => {
                                e.stopPropagation();
                                moveEsi(c.id, col.level + 1);
                              }}
                              className="px-1 text-[10px] bg-slate-800 text-slate-300 hover:bg-slate-700 rounded border border-slate-700 font-bold"
                            >
                              ▼
                            </button>
                          )}
                          <button
                            title="Discharge or Admit"
                            onClick={(e) => {
                              e.stopPropagation();
                              dischargeOrTransferCase(c.id);
                            }}
                            className="px-1.5 py-0.5 text-[9px] bg-sky-950 text-sky-300 hover:bg-sky-900 rounded border border-sky-800 font-bold uppercase"
                          >
                            Admit
                          </button>
                        </div>
                      </div>
                    </Card>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Modal: Triage New Emergency Patient */}
      {isTriageModalOpen && (
        <Modal
          isOpen={true}
          onClose={() => setIsTriageModalOpen(false)}
          title="Emergency Patient Intake &amp; Clinical Triage (ESI 1-5)"
        >
          <form onSubmit={handleCreateTriage} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Patient Name / Identification
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Unknown Trauma Male / John Doe"
                  value={patientName}
                  onChange={(e) => setPatientName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500 font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Gender</label>
                <select
                  value={patientGender}
                  onChange={(e) => setPatientGender(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                >
                  <option value="Male">Male</option>
                  <option value="Female">Female</option>
                  <option value="Other">Other / Unknown</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Chief Emergency Complaint &amp; Mechanism of Injury
              </label>
              <input
                type="text"
                required
                placeholder="e.g. RTA two-wheeler collision with loss of consciousness"
                value={complaint}
                onChange={(e) => setComplaint(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
              />
            </div>

            {/* Vital Signs Grid */}
            <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-2">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <Activity size={12} className="text-sky-400" /> Bedside Emergency Vitals
              </div>
              <div className="grid grid-cols-4 gap-2">
                <div>
                  <label className="text-[10px] text-slate-500">BP (mmHg)</label>
                  <input
                    type="text"
                    value={bp}
                    onChange={(e) => setBp(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1 text-xs text-slate-200 font-mono"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-500">HR (bpm)</label>
                  <input
                    type="text"
                    value={hr}
                    onChange={(e) => setHr(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1 text-xs text-slate-200 font-mono"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-500">SpO2 (%)</label>
                  <input
                    type="text"
                    value={spo2}
                    onChange={(e) => setSpo2(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1 text-xs text-slate-200 font-mono"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-500">Temp (°F)</label>
                  <input
                    type="text"
                    value={temp}
                    onChange={(e) => setTemp(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1 text-xs text-slate-200 font-mono"
                  />
                </div>
              </div>
            </div>

            {/* GCS Calculator */}
            <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  Glasgow Coma Scale (GCS)
                </span>
                <span className="text-xs font-mono font-bold text-amber-400">
                  Score: {totalGcs}/15
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-[10px]">
                <div>
                  <span className="text-slate-500 block mb-0.5">Eye Opening (1-4)</span>
                  <select
                    value={eyeScore}
                    onChange={(e) => setEyeScore(parseInt(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-800 rounded p-1 text-xs text-slate-200 font-mono"
                  >
                    <option value={4}>4 - Spontaneous</option>
                    <option value={3}>3 - To speech</option>
                    <option value={2}>2 - To pain</option>
                    <option value={1}>1 - None</option>
                  </select>
                </div>
                <div>
                  <span className="text-slate-500 block mb-0.5">Verbal Response (1-5)</span>
                  <select
                    value={verbalScore}
                    onChange={(e) => setVerbalScore(parseInt(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-800 rounded p-1 text-xs text-slate-200 font-mono"
                  >
                    <option value={5}>5 - Oriented</option>
                    <option value={4}>4 - Confused</option>
                    <option value={3}>3 - Inappropriate</option>
                    <option value={2}>2 - Incomprehensible</option>
                    <option value={1}>1 - None</option>
                  </select>
                </div>
                <div>
                  <span className="text-slate-500 block mb-0.5">Motor Response (1-6)</span>
                  <select
                    value={motorScore}
                    onChange={(e) => setMotorScore(parseInt(e.target.value))}
                    className="w-full bg-slate-900 border border-slate-800 rounded p-1 text-xs text-slate-200 font-mono"
                  >
                    <option value={6}>6 - Obeys commands</option>
                    <option value={5}>5 - Localizes pain</option>
                    <option value={4}>4 - Normal flexion</option>
                    <option value={3}>3 - Abnormal flexion</option>
                    <option value={2}>2 - Extension</option>
                    <option value={1}>1 - None</option>
                  </select>
                </div>
              </div>
            </div>

            {/* ESI Stratification Selector */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Select ESI Severity Level
              </label>
              <div className="grid grid-cols-5 gap-2">
                {[
                  { lvl: 1, label: "ESI 1 (Resus)", color: "border-rose-500 bg-rose-950/40 text-rose-300" },
                  { lvl: 2, label: "ESI 2 (Emerg)", color: "border-orange-500 bg-orange-950/40 text-orange-300" },
                  { lvl: 3, label: "ESI 3 (Urgent)", color: "border-amber-500 bg-amber-950/40 text-amber-300" },
                  { lvl: 4, label: "ESI 4 (Less)", color: "border-emerald-500 bg-emerald-950/40 text-emerald-300" },
                  { lvl: 5, label: "ESI 5 (Non)", color: "border-sky-500 bg-sky-950/40 text-sky-300" },
                ].map((item) => (
                  <button
                    type="button"
                    key={item.lvl}
                    onClick={() => setSelectedEsi(item.lvl)}
                    className={`p-2 rounded-lg border text-[11px] font-bold text-center transition-all ${
                      selectedEsi === item.lvl
                        ? `${item.color} ring-2 ring-sky-500`
                        : "bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {/* MLC Medico-Legal Checkbox & Inputs */}
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-3">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="mlc-check"
                  checked={isMlc}
                  onChange={(e) => setIsMlc(e.target.checked)}
                  className="rounded bg-slate-900 border-slate-700 text-rose-500 focus:ring-rose-500"
                />
                <label htmlFor="mlc-check" className="text-xs text-rose-300 font-semibold cursor-pointer">
                  Tag as Medico-Legal Case (MLC) • Section 39 CrPC (RTA / Assault / Burns)
                </label>
              </div>

              {isMlc && (
                <div className="grid grid-cols-2 gap-2 text-xs font-mono pt-1 border-t border-slate-800">
                  <div>
                    <label className="text-[10px] text-slate-400 block mb-0.5">Jurisdiction Police Station</label>
                    <input
                      type="text"
                      value={policeStationInput}
                      onChange={(e) => setPoliceStationInput(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1 text-slate-200 text-xs"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-slate-400 block mb-0.5">Constable Buckle / Badge No.</label>
                    <input
                      type="text"
                      value={policeBuckleInput}
                      onChange={(e) => setPoliceBuckleInput(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded px-2 py-1 text-slate-200 text-xs"
                    />
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsTriageModalOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" variant="primary" size="sm">
                Confirm &amp; Admit to Board
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* Modal: Printable Emergency Department Triage Slip */}
      {selectedCaseForPrint && (
        <Modal
          isOpen={true}
          onClose={() => setSelectedCaseForPrint(null)}
          title="Printable Emergency Triage Slip &amp; Clinical Head-Sheet"
        >
          <div className="space-y-4">
            <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg space-y-3 font-mono text-xs">
              <div className="flex justify-between border-b border-slate-800 pb-2">
                <div>
                  <strong className="text-slate-100 text-sm">{selectedCaseForPrint.name}</strong>
                  <div className="text-[11px] text-slate-400">MRN: {selectedCaseForPrint.mrn} • Arrival: {selectedCaseForPrint.arrival}</div>
                </div>
                <div className="text-right">
                  <Badge variant={selectedCaseForPrint.esi === 1 ? "danger" : selectedCaseForPrint.esi <= 3 ? "warning" : "info"} size="sm">
                    ESI {selectedCaseForPrint.esi}
                  </Badge>
                  {selectedCaseForPrint.isMlc && (
                    <div className="text-[10px] text-rose-400 font-bold mt-0.5">MLC #{selectedCaseForPrint.mlcNumber || "MLC-PENDING"}</div>
                  )}
                </div>
              </div>

              <div>
                <span className="text-slate-400 block text-[10px] uppercase">Emergency Presentation:</span>
                <span className="text-slate-200 font-semibold">{selectedCaseForPrint.complaint}</span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase">Vital Signs:</span>
                  <span className="text-sky-400 font-bold">{selectedCaseForPrint.vitals}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase">GCS Breakdown:</span>
                  <span className="text-amber-400 font-bold">
                    {selectedCaseForPrint.gcs}/15 (E{selectedCaseForPrint.eyeScore || 4} V{selectedCaseForPrint.verbalScore || 5} M{selectedCaseForPrint.motorScore || 6})
                  </span>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-800">
                <span className="text-slate-400 block text-[10px] uppercase">Immediate STAT Orders:</span>
                <div className="text-slate-300 space-y-0.5 text-[11px] pl-2 mt-1">
                  <div>• 12-Lead ECG &amp; Continuous Bedside Cardiac Telemetry</div>
                  <div>• STAT Trauma Panel (CBC, ABG, Serum Electrolytes, Crossmatch 2 Units PRBC)</div>
                  <div>• FAST Ultrasonography / Trauma Pan-Scan CT (Bay 1)</div>
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
                <Printer size={13} /> Print Triage Slip
              </Button>
              <Button variant="primary" size="sm" onClick={() => setSelectedCaseForPrint(null)}>
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Modal: Medico-Legal Case (MLC) Police Intimation Certificate */}
      {selectedCaseForMlc && (
        <Modal
          isOpen={true}
          onClose={() => setSelectedCaseForMlc(null)}
          title="Section 39 CrPC Medico-Legal Police Intimation Record"
        >
          <div className="space-y-4">
            <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg space-y-3 font-mono text-xs">
              <div className="flex justify-between border-b border-slate-800 pb-2">
                <div>
                  <strong className="text-rose-400 uppercase text-xs">Official Police Intimation Slip</strong>
                  <div className="text-[11px] text-slate-400">MLC No: {selectedCaseForMlc.mlcNumber || "MLC-20261101-9F2B"}</div>
                </div>
                <div className="text-right">
                  <Badge variant="danger" size="sm">CONFIDENTIAL / FORENSIC</Badge>
                  <div className="text-[10px] text-slate-500 mt-0.5">{new Date().toLocaleString()}</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-slate-500 block text-[10px]">Patient Name:</span>
                  <span className="text-slate-200 font-bold">{selectedCaseForMlc.name}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">MRN:</span>
                  <span className="text-slate-200 font-bold">{selectedCaseForMlc.mrn}</span>
                </div>
              </div>

              <div>
                <span className="text-slate-500 block text-[10px]">Alleged Cause of Injury:</span>
                <span className="text-slate-300">{selectedCaseForMlc.complaint}</span>
              </div>

              <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-800">
                <div>
                  <span className="text-slate-500 block text-[10px]">Police Station:</span>
                  <span className="text-slate-200">{selectedCaseForMlc.policeStation || "Central Traffic Police Station"}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">Officer / Constable Buckle:</span>
                  <span className="text-amber-400 font-bold">{selectedCaseForMlc.policeBuckleNo || "PC-4882"}</span>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-800 text-[10px] text-slate-500 italic">
                Notice dispatched under Section 39 Code of Criminal Procedure (CrPC). Physical copy sealed and preserved in hospital forensic custody.
              </div>
            </div>

            <div className="flex items-center justify-between pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => window.print()}
                className="flex items-center gap-1.5"
              >
                <Printer size={13} /> Print Police Intimation
              </Button>
              <Button variant="primary" size="sm" onClick={() => setSelectedCaseForMlc(null)}>
                Close Record
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
