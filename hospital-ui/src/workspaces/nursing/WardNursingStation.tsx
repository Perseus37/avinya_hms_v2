import React, { useEffect, useState } from "react";
import { uiApi } from "../../api/uiApi";
import { DetailedBedItem } from "../../types";
import { useActivePatient } from "../../core/context/ActivePatientContext";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { BedDouble, RefreshCw, AlertTriangle } from "lucide-react";

export const WardNursingStation: React.FC = () => {
  const [beds, setBeds] = useState<DetailedBedItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedWardId] = useState(1);
  const { selectPatient } = useActivePatient();

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
            General Inpatient Ward 1 • Real-time occupancy & vital surveillance
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
                  <div className="space-y-2">
                    <div>
                      <div className="text-sm font-semibold text-slate-100 flex items-center justify-between">
                        <span>{patient.patient_name}</span>
                        <span className="font-mono text-xs text-sky-400">{patient.mrn}</span>
                      </div>
                      <div className="text-xs text-slate-400 mt-0.5">
                        {patient.gender} • {patient.age_years ? `${patient.age_years}y` : "--"}
                      </div>
                    </div>

                    <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs">
                      <div className="text-slate-400 truncate max-w-[150px]">
                        Dr. {patient.attending_doctor_name || "--"}
                      </div>
                      {patient.news2_score !== null && (
                        <div
                          className={`font-mono font-bold text-[11px] px-1.5 py-0.5 rounded flex items-center gap-1 ${
                            (patient.news2_score || 0) >= 5
                              ? "bg-rose-950 text-rose-300 border border-rose-800"
                              : (patient.news2_score || 0) >= 3
                              ? "bg-amber-950 text-amber-300 border border-amber-800"
                              : "bg-emerald-950 text-emerald-300 border border-emerald-800"
                          }`}
                        >
                          {(patient.news2_score || 0) >= 5 && <AlertTriangle size={10} />}
                          NEWS2: {patient.news2_score}
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="py-6 text-center text-xs text-slate-500 font-mono">
                    {bed.status === "AVAILABLE" ? "Ready for Admission" : "Sanitization In Progress"}
                  </div>
                )}
              </Card>
            );
          })
        )}
      </div>
    </div>
  );
};

