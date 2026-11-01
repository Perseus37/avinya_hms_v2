import React from "react";
import { Siren, Clock, User } from "lucide-react";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { useActivePatient } from "../../core/context/ActivePatientContext";

export const EDTriageBoard: React.FC = () => {
  const { selectPatient } = useActivePatient();

  const esiColumns = [
    {
      level: 1,
      name: "Resuscitation (ESI 1)",
      color: "border-rose-500 bg-rose-950/20 text-rose-400",
      cases: [
        { id: 101, name: "Unknown Trauma Male", mrn: "ER-0912", arrival: "4m ago", complaint: "Cardiac arrest post RTA", vitals: "BP 60/40, HR 140" },
      ],
    },
    {
      level: 2,
      name: "Emergent (ESI 2)",
      color: "border-orange-500 bg-orange-950/20 text-orange-400",
      cases: [
        { id: 102, name: "Ananya Deshmukh", mrn: "ER-0914", arrival: "12m ago", complaint: "Severe chest pain radiating to left arm", vitals: "BP 160/95, SpO2 93%" },
      ],
    },
    {
      level: 3,
      name: "Urgent (ESI 3)",
      color: "border-amber-500 bg-amber-950/20 text-amber-400",
      cases: [
        { id: 103, name: "Harish Rao", mrn: "ER-0915", arrival: "28m ago", complaint: "Acute right lower quadrant pain, febrile", vitals: "BP 130/80, Temp 102.4F" },
      ],
    },
    {
      level: 4,
      name: "Less Urgent (ESI 4)",
      color: "border-emerald-500 bg-emerald-950/20 text-emerald-400",
      cases: [
        { id: 104, name: "Pooja Nair", mrn: "ER-0918", arrival: "45m ago", complaint: "Wrist sprain after fall", vitals: "Normal" },
      ],
    },
    {
      level: 5,
      name: "Non-Urgent (ESI 5)",
      color: "border-sky-500 bg-sky-950/20 text-sky-400",
      cases: [
        { id: 105, name: "Manoj Kumar", mrn: "ER-0920", arrival: "1h 10m ago", complaint: "Suture removal, prescription refill", vitals: "Normal" },
      ],
    },
  ];

  return (
    <div className="flex-1 flex flex-col bg-slate-950 p-6 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between pb-6 border-b border-slate-800">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <Siren className="text-rose-500" />
            Emergency Department (ED) Triage & Trauma Board
          </h1>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            ESI 1-5 Severity Stratification • Real-time Door-to-Doctor Tracking
          </p>
        </div>
      </div>

      {/* Kanban 5 Columns */}
      <div className="flex-1 grid grid-cols-5 gap-3 mt-6 overflow-hidden">
        {esiColumns.map((col) => (
          <div key={col.level} className="flex flex-col rounded-xl bg-slate-900/60 border border-slate-800 p-3 overflow-hidden">
            <div className={`p-2 rounded-lg border font-semibold text-xs mb-3 flex items-center justify-between ${col.color}`}>
              <span>{col.name}</span>
              <span className="font-mono font-bold text-[11px] bg-slate-950 px-1.5 py-0.2 rounded">
                {col.cases.length}
              </span>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              {col.cases.map((c) => (
                <Card
                  key={c.id}
                  onClick={() => selectPatient(c.id)}
                  className="p-3 bg-slate-900 border-slate-800 hover:border-slate-700 cursor-pointer transition-all shadow-sm"
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-semibold text-xs text-slate-200 flex items-center gap-1.5">
                      <User size={13} className="text-slate-400" />
                      {c.name}
                    </span>
                    <span className="font-mono text-[10px] text-slate-400">{c.mrn}</span>
                  </div>
                  <div className="text-[11px] text-slate-300 italic mb-2">
                    &quot;{c.complaint}&quot;
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1.5 border-t border-slate-800/80">
                    <span className="font-mono text-sky-400">{c.vitals}</span>
                    <Badge variant="neutral" size="sm" className="flex items-center gap-1">
                      <Clock size={10} /> {c.arrival}
                    </Badge>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

