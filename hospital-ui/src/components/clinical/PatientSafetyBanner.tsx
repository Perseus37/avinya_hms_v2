import React from "react";
import { useActivePatient } from "../../core/context/ActivePatientContext";
import { AlertTriangle, User, Activity, BedDouble, X } from "lucide-react";

interface PatientSafetyBannerProps {
  onOpenPatientRecord?: () => void;
}

export const PatientSafetyBanner: React.FC<PatientSafetyBannerProps> = ({ onOpenPatientRecord }) => {
  const { patientSummary, clearPatient } = useActivePatient();

  if (!patientSummary) {
    return (
      <div className="bg-slate-900/60 border-b border-slate-800/80 px-4 py-2 flex items-center justify-between text-xs text-slate-400">
        <div className="flex items-center gap-2">
          <User size={14} className="text-slate-500" />
          <span>No active patient selected. Press <kbd className="px-1.5 py-0.5 bg-slate-800 border border-slate-700 rounded text-[11px] text-slate-300 font-mono">Cmd + K</kbd> to search MPI.</span>
        </div>
        <div className="text-[11px] text-slate-500 font-mono">CCOW SAFE CONTEXT: UNBOUND</div>
      </div>
    );
  }

  const {
    full_name,
    mrn,
    gender,
    age_years,
    blood_group,
    critical_allergies,
    latest_vitals,
    active_admission,
  } = patientSummary;

  return (
    <div className="bg-slate-900 border-b border-sky-500/30 px-4 py-2.5 flex items-center justify-between shadow-md">
      {/* Patient Identification */}
      <div className="flex items-center gap-4">
        <div className="h-9 w-9 rounded-full bg-sky-500/10 border border-sky-400/30 flex items-center justify-center text-sky-400 font-bold text-sm">
          {full_name.charAt(0)}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-100 text-sm">{full_name}</span>
            <span className="font-mono text-xs text-sky-400 bg-sky-950/60 px-1.5 py-0.5 rounded border border-sky-800/50">
              {mrn}
            </span>
            <span className="text-xs text-slate-400">
              {gender} • {age_years !== null ? `${age_years}y` : "--"}
            </span>
            {blood_group && (
              <span className="text-xs font-bold font-mono text-rose-400 bg-rose-950/50 px-1.5 py-0.5 rounded border border-rose-900/50">
                {blood_group}
              </span>
            )}
          </div>
          {/* Location & Admission */}
          <div className="flex items-center gap-3 text-xs text-slate-400 mt-0.5">
            {active_admission ? (
              <span className="flex items-center gap-1 text-emerald-400 font-medium">
                <BedDouble size={13} />
                {active_admission.ward_name} / Bed {active_admission.bed_number}
              </span>
            ) : (
              <span className="text-slate-500">Outpatient / Ambulatory</span>
            )}
            {active_admission?.attending_doctor_name && (
              <span>Attending: Dr. {active_admission.attending_doctor_name}</span>
            )}
          </div>
        </div>
      </div>

      {/* Critical Clinical Indicators (Allergies & Vitals) */}
      <div className="flex items-center gap-6">
        {/* Allergies Indicator */}
        <div className="flex items-center gap-1.5">
          {critical_allergies.length > 0 ? (
            <div className="flex items-center gap-1.5 bg-rose-950/80 border border-rose-800 px-2.5 py-1 rounded text-xs font-medium text-rose-300">
              <AlertTriangle size={13} className="text-rose-400" />
              <span>
                ALLERGIES:{" "}
                <span className="font-bold text-rose-200">
                  {critical_allergies.map((a) => a.allergen).join(", ")}
                </span>
              </span>
            </div>
          ) : (
            <span className="text-xs text-slate-500 font-mono">NKDA (No Known Allergies)</span>
          )}
        </div>

        {/* Latest NEWS2 / Vitals */}
        {latest_vitals && (
          <div className="flex items-center gap-3 text-xs font-mono bg-slate-950 px-2.5 py-1 rounded border border-slate-800">
            <Activity size={13} className="text-sky-400" />
            <span>BP: {latest_vitals.blood_pressure || "--"}</span>
            <span>HR: {latest_vitals.heart_rate_bpm || "--"}</span>
            <span>SpO2: {latest_vitals.spo2_percent ? `${latest_vitals.spo2_percent}%` : "--"}</span>
            {latest_vitals.news2_total_score !== null && (
              <span
                className={`font-bold px-1 rounded ${
                  (latest_vitals.news2_total_score || 0) >= 5
                    ? "bg-rose-900 text-rose-200"
                    : (latest_vitals.news2_total_score || 0) >= 3
                    ? "bg-amber-900 text-amber-200"
                    : "bg-emerald-900 text-emerald-200"
                }`}
              >
                NEWS2: {latest_vitals.news2_total_score}
              </span>
            )}
          </div>
        )}

        {/* Patient 360 Jump Button */}
        {onOpenPatientRecord && (
          <button
            onClick={onOpenPatientRecord}
            className="text-xs px-2.5 py-1 rounded-lg bg-sky-950/80 hover:bg-sky-900 border border-sky-800 text-sky-300 font-semibold transition-colors flex items-center gap-1 shadow-sm"
            title="Open Complete Patient 360 Record & Longitudinal Timeline"
          >
            <span>Patient 360</span>
          </button>
        )}

        {/* Clear active patient button */}
        <button
          onClick={clearPatient}
          title="Clear Patient Context (Lock Safe)"
          className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
        >
          <X size={16} />
        </button>
      </div>
    </div>
  );
};

