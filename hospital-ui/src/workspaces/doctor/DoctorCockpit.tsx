import React, { useEffect, useState } from "react";
import { uiApi } from "../../api/uiApi";
import { DoctorQueueSummary } from "../../types";
import { useActivePatient } from "../../core/context/ActivePatientContext";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Clock, Stethoscope, RefreshCw } from "lucide-react";

export const DoctorCockpit: React.FC = () => {
  const [queue, setQueue] = useState<DoctorQueueSummary | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const { selectPatient, patientSummary } = useActivePatient();

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
                className="p-3 rounded-lg bg-slate-900 border border-slate-800 hover:border-sky-500/50 hover:bg-slate-800/60 cursor-pointer transition-all shadow-sm"
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
                  MRN: {patientSummary.mrn} • Age: {patientSummary.age_years}y • Gender: {patientSummary.gender}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <Button variant="outline" size="sm">
                  View Past History
                </Button>
                <Button variant="primary" size="sm">
                  Finalize & Sign Slip
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
                <div className="text-[10px] text-slate-500">Low Clinical Risk</div>
              </Card>
            </div>

            {/* Soap Notes & Prescriptions Pad */}
            <div className="grid grid-cols-2 gap-6">
              {/* Clinical Notes */}
              <div className="space-y-4">
                <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">Consultation Notes (SOAP)</h3>
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Subjective / Chief Complaint</label>
                  <textarea
                    rows={3}
                    placeholder="Patient describes fever for 3 days, dry cough..."
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg p-3 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1">Assessment & Plan</label>
                  <textarea
                    rows={4}
                    placeholder="Likely viral upper respiratory infection. Hydration, antipyretics..."
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg p-3 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500"
                  />
                </div>
              </div>

              {/* Medication Orders & Diagnostics */}
              <div className="space-y-4">
                <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">Prescriptions (eRx) & Tests</h3>
                <div className="border border-slate-800 rounded-lg bg-slate-900 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-300">Medication Orders</span>
                    <Button variant="ghost" size="sm" className="text-xs text-sky-400">
                      + Add Drug
                    </Button>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between p-2 rounded bg-slate-950 border border-slate-800 text-xs">
                      <div>
                        <div className="font-semibold text-slate-200">Paracetamol 500mg Tablet</div>
                        <div className="text-slate-400 text-[11px]">1 tab • TDS • After food • 5 days</div>
                      </div>
                      <Badge variant="success" size="sm">No DDI</Badge>
                    </div>
                    <div className="flex items-center justify-between p-2 rounded bg-slate-950 border border-slate-800 text-xs">
                      <div>
                        <div className="font-semibold text-slate-200">Cetirizine 10mg Tablet</div>
                        <div className="text-slate-400 text-[11px]">1 tab • OD • At bedtime • 3 days</div>
                      </div>
                      <Badge variant="success" size="sm">No DDI</Badge>
                    </div>
                  </div>
                </div>

                {/* Diagnostics Orders */}
                <div className="border border-slate-800 rounded-lg bg-slate-900 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-300">Diagnostic Orders (Lab & Radiology)</span>
                    <Button variant="ghost" size="sm" className="text-xs text-sky-400">
                      + Add Lab Test
                    </Button>
                  </div>
                  <div className="p-2 rounded bg-slate-950 border border-slate-800 text-xs text-slate-400">
                    Complete Blood Count (CBC) • Routine
                  </div>
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
    </div>
  );
};
