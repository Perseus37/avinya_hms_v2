import React, { useEffect, useState } from "react";
import { uiApi } from "../../api/uiApi";
import { DetailedBedItem } from "../../types";
import { useActivePatient } from "../../core/context/ActivePatientContext";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { BedDouble, RefreshCw, Activity, Sparkles, User } from "lucide-react";

export const WardNursingStation: React.FC = () => {
  const [beds, setBeds] = useState<DetailedBedItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedWardId] = useState(1);
  const { selectPatient } = useActivePatient();

  // NEWS2 / Vitals Recording Modal
  const [activeBedForVitals, setActiveBedForVitals] = useState<DetailedBedItem | null>(null);
  const [respRate, setRespRate] = useState(16);
  const [spo2, setSpo2] = useState(98);
  const [onOxygen, setOnOxygen] = useState(false);
  const [systolicBp, setSystolicBp] = useState(120);
  const [pulse, setPulse] = useState(72);
  const [consciousness, setConsciousness] = useState<"ALERT" | "CVPU">("ALERT");
  const [temperature, setTemperature] = useState(37.0);

  const calculateNews2 = () => {
    let score = 0;
    // Respiration rate
    if (respRate <= 8 || respRate >= 25) score += 3;
    else if (respRate >= 21 && respRate <= 24) score += 2;
    else if (respRate >= 9 && respRate <= 11) score += 1;

    // SpO2
    if (spo2 <= 91) score += 3;
    else if (spo2 >= 92 && spo2 <= 93) score += 2;
    else if (spo2 >= 94 && spo2 <= 95) score += 1;

    // Oxygen
    if (onOxygen) score += 2;

    // Systolic BP
    if (systolicBp <= 90 || systolicBp >= 220) score += 3;
    else if (systolicBp >= 91 && systolicBp <= 100) score += 2;
    else if (systolicBp >= 101 && systolicBp <= 110) score += 1;

    // Pulse
    if (pulse <= 40 || pulse >= 131) score += 3;
    else if (pulse >= 111 && pulse <= 130) score += 2;
    else if ((pulse >= 41 && pulse <= 50) || (pulse >= 91 && pulse <= 110)) score += 1;

    // Consciousness
    if (consciousness === "CVPU") score += 3;

    // Temperature
    if (temperature <= 35.0) score += 3;
    else if (temperature >= 39.1) score += 2;
    else if ((temperature >= 35.1 && temperature <= 36.0) || (temperature >= 38.1 && temperature <= 39.0)) score += 1;

    return score;
  };

  const calculatedScore = calculateNews2();

  const loadBeds = async () => {
    setIsLoading(true);
    try {
      const data = await uiApi.getWardBedMap(selectedWardId);
      setBeds(data);
    } catch (err) {
      console.error("Failed to load bed map:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadBeds();
  }, [selectedWardId]);

  const toggleSanitization = (bedId: number) => {
    setBeds((prev) =>
      prev.map((b) => {
        if (b.bed_id !== bedId) return b;
        const newStatus = b.status === "CLEANING" ? "AVAILABLE" : "CLEANING";
        return { ...b, status: newStatus };
      })
    );
  };

  const handleSaveVitals = (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeBedForVitals) return;

    setBeds((prev) =>
      prev.map((b) => {
        if (b.bed_id !== activeBedForVitals.bed_id) return b;
        return {
          ...b,
          occupied_details: b.occupied_details
            ? {
                ...b.occupied_details,
                news2_score: calculatedScore,
              }
            : b.occupied_details,
        };
      })
    );

    setActiveBedForVitals(null);
    alert(`Vitals & NEWS2 score of ${calculatedScore} recorded for Bed ${activeBedForVitals.bed_number}.`);
  };

  const occupiedCount = beds.filter((b) => b.status === "OCCUPIED").length;
  const availableCount = beds.filter((b) => b.status === "AVAILABLE").length;
  const cleaningCount = beds.filter((b) => b.status === "CLEANING").length;

  return (
    <div className="flex-1 flex flex-col bg-slate-950 p-6 overflow-y-auto">
      {/* Header & Ward Census Summary */}
      <div className="flex items-center justify-between pb-6 border-b border-slate-800">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <BedDouble className="text-emerald-400" />
            Ward Nursing Station — Inpatient Bed Census Matrix
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            General Inpatient Ward 1 • Real-time occupancy, sanitization & NEWS2 vital surveillance
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs font-mono">
            <span className="px-2.5 py-1 rounded bg-emerald-950 border border-emerald-800 text-emerald-400">
              {availableCount} Available
            </span>
            <span className="px-2.5 py-1 rounded bg-sky-950 border border-sky-800 text-sky-400">
              {occupiedCount} Occupied
            </span>
            <span className="px-2.5 py-1 rounded bg-amber-950 border border-amber-800 text-amber-400">
              {cleaningCount} Sanitizing
            </span>
          </div>

          <button
            onClick={loadBeds}
            disabled={isLoading}
            className="p-2 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 transition-colors"
          >
            <RefreshCw size={15} className={isLoading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {/* Interactive Bed Matrix Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mt-6">
        {beds.length === 0 ? (
          <div className="col-span-full py-16 text-center text-slate-500 text-sm">
            No beds configured in this ward, or loading bed matrix...
          </div>
        ) : (
          beds.map((bed) => {
            const isOccupied = bed.status === "OCCUPIED" && bed.occupied_details;
            const patient = bed.occupied_details;

            return (
              <Card
                key={bed.bed_id}
                onClick={() => {
                  if (patient?.patient_id) {
                    selectPatient(patient.patient_id);
                  }
                }}
                className={`p-4 rounded-xl border transition-all cursor-pointer ${
                  isOccupied
                    ? "bg-slate-900/90 border-slate-700 hover:border-sky-500 shadow-md"
                    : bed.status === "CLEANING"
                    ? "bg-amber-950/20 border-amber-900/40"
                    : "bg-slate-950 border-slate-800 hover:border-slate-700 opacity-70"
                }`}
              >
                <div className="flex items-center justify-between pb-2 border-b border-slate-800 mb-3">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-bold text-slate-200">
                      Bed {bed.bed_number}
                    </span>
                    <span className="text-[11px] text-slate-500 font-mono">
                      Room {bed.room_number}
                    </span>
                  </div>
                  <Badge
                    variant={
                      bed.status === "OCCUPIED"
                        ? "info"
                        : bed.status === "AVAILABLE"
                        ? "success"
                        : "warning"
                    }
                    size="sm"
                  >
                    {bed.status}
                  </Badge>
                </div>

                {isOccupied && patient ? (
                  <div className="space-y-3">
                    <div>
                      <div className="font-semibold text-sm text-slate-100 flex items-center gap-1.5">
                        <User size={13} className="text-slate-400" />
                        {patient.patient_name}
                      </div>
                      <div className="text-[11px] text-slate-400 font-mono">
                        {patient.mrn} • {patient.gender} • {patient.age_years ? `${patient.age_years}y` : "--"}
                      </div>
                    </div>

                    <div className="text-xs text-slate-400">
                      Admitted:{" "}
                      <span className="font-mono text-slate-300">
                        {patient.admitted_at ? new Date(patient.admitted_at).toLocaleDateString() : "--"}
                      </span>
                    </div>

                    <div className="flex items-center justify-between pt-2 border-t border-slate-800/80">
                      <div className="flex items-center gap-1 text-xs">
                        <span className="text-slate-400">NEWS2:</span>
                        <span
                          className={`font-mono font-bold px-1.5 py-0.5 rounded text-[11px] ${
                            (patient.news2_score ?? 0) >= 7
                              ? "bg-rose-950 text-rose-400 border border-rose-800 animate-pulse"
                              : (patient.news2_score ?? 0) >= 5
                              ? "bg-amber-950 text-amber-400 border border-amber-800"
                              : "bg-emerald-950 text-emerald-400 border border-emerald-800"
                          }`}
                        >
                          {patient.news2_score ?? 0}
                        </span>
                      </div>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveBedForVitals(bed);
                        }}
                        className="px-2 py-1 text-[11px] rounded bg-sky-950 text-sky-400 border border-sky-800 hover:bg-sky-900 transition-colors flex items-center gap-1"
                      >
                        <Activity size={11} /> Vitals & NEWS2
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="py-6 flex flex-col items-center justify-center text-slate-600 space-y-2">
                    <span className="text-xs">
                      {bed.status === "CLEANING" ? "Terminal Sanitization in Progress" : "Ready for Inpatient Admission"}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleSanitization(bed.bed_id);
                      }}
                      className="px-2 py-1 rounded text-[10px] bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800 flex items-center gap-1"
                    >
                      <Sparkles size={11} /> {bed.status === "CLEANING" ? "Mark Ready / Clean" : "Request Cleaning"}
                    </button>
                  </div>
                )}
              </Card>
            );
          })
        )}
      </div>

      {/* Modal: Bedside Vitals & NEWS2 Scoring */}
      {activeBedForVitals && (
        <Modal
          isOpen={true}
          onClose={() => setActiveBedForVitals(null)}
          title={`Bedside Vitals & NEWS2 Assessment — Bed ${activeBedForVitals.bed_number}`}
        >
          <form onSubmit={handleSaveVitals} className="space-y-4">
            <div className="text-xs text-slate-300">
              Patient: <strong>{activeBedForVitals.occupied_details?.patient_name}</strong> (
              {activeBedForVitals.occupied_details?.mrn})
            </div>

            {/* Calculated Score Bar */}
            <div
              className={`p-3 rounded-lg border flex items-center justify-between font-mono text-xs ${
                calculatedScore >= 7
                  ? "bg-rose-950/40 border-rose-800 text-rose-300"
                  : calculatedScore >= 5
                  ? "bg-amber-950/40 border-amber-800 text-amber-300"
                  : "bg-emerald-950/40 border-emerald-800 text-emerald-300"
              }`}
            >
              <div>
                <span className="font-bold">Calculated NEWS2 Score: {calculatedScore}</span>
                <div className="text-[10px] opacity-80">
                  {calculatedScore >= 7
                    ? "HIGH RISK — Immediate Emergency Doctor Escalation / MET Team"
                    : calculatedScore >= 5
                    ? "MEDIUM RISK — Urgent Ward Doctor Review Required"
                    : "LOW RISK — Routine 4-6h Inpatient Surveillance"}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Respiration Rate (breaths/min)</label>
                <input
                  type="number"
                  value={respRate}
                  onChange={(e) => setRespRate(parseInt(e.target.value) || 0)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                />
              </div>

              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Oxygen Saturation (SpO2 %)</label>
                <input
                  type="number"
                  value={spo2}
                  onChange={(e) => setSpo2(parseInt(e.target.value) || 0)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                />
              </div>

              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Systolic BP (mmHg)</label>
                <input
                  type="number"
                  value={systolicBp}
                  onChange={(e) => setSystolicBp(parseInt(e.target.value) || 0)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                />
              </div>

              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Pulse / Heart Rate (bpm)</label>
                <input
                  type="number"
                  value={pulse}
                  onChange={(e) => setPulse(parseInt(e.target.value) || 0)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                />
              </div>

              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Body Temperature (°C)</label>
                <input
                  type="number"
                  step="0.1"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value) || 37.0)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                />
              </div>

              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Consciousness Level</label>
                <select
                  value={consciousness}
                  onChange={(e) => setConsciousness(e.target.value as "ALERT" | "CVPU")}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                >
                  <option value="ALERT">Alert (A)</option>
                  <option value="CVPU">Confused / Voice / Pain / Unresponsive (CVPU)</option>
                </select>
              </div>
            </div>

            <div className="flex items-center gap-2 p-2 rounded bg-slate-950 border border-slate-800">
              <input
                type="checkbox"
                id="on-oxygen"
                checked={onOxygen}
                onChange={(e) => setOnOxygen(e.target.checked)}
                className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-sky-500"
              />
              <label htmlFor="on-oxygen" className="text-xs text-slate-300 cursor-pointer">
                Supplemental Oxygen Therapy (Nasal Cannula / Venturi / Mask)
              </label>
            </div>

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setActiveBedForVitals(null)}
              >
                Cancel
              </Button>
              <Button type="submit" variant="primary" size="sm">
                Save Vitals & Record NEWS2
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
};
