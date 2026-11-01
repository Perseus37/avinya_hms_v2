import React, { useState } from "react";
import {
  Clock,
  CheckCircle2,
  Volume2,
  Tv,
  Filter,
  Stethoscope,
} from "lucide-react";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";

interface OPDQueueItem {
  id: string;
  tokenNumber: string;
  patientName: string;
  mrn: string;
  ageGender: string;
  doctorName: string;
  department: string;
  chamberNumber: string;
  arrivalTime: string;
  waitTimeMinutes: number;
  status: "WAITING" | "TRIAGED" | "IN_CONSULT" | "LAB_TRANSIT" | "COMPLETED" | "NO_SHOW";
  isSlaBreach: boolean;
}

export const OPDQueueWorkspace: React.FC = () => {
  const [selectedDept, setSelectedDept] = useState<string>("ALL");
  const [isTvDisplayOpen, setIsTvDisplayOpen] = useState(false);
  const [calledToken, setCalledToken] = useState<string | null>("CARDIO-14");

  // Sample real-time queue items
  const [queueItems, setQueueItems] = useState<OPDQueueItem[]>([
    {
      id: "q-1",
      tokenNumber: "CARDIO-14",
      patientName: "John Doe",
      mrn: "AV-2026-00412",
      ageGender: "42M",
      doctorName: "Dr. Ramesh Gupta",
      department: "Cardiology",
      chamberNumber: "Chamber 4",
      arrivalTime: "09:02",
      waitTimeMinutes: 28,
      status: "IN_CONSULT",
      isSlaBreach: false,
    },
    {
      id: "q-2",
      tokenNumber: "CARDIO-15",
      patientName: "Sunita Sharma",
      mrn: "AV-2026-00415",
      ageGender: "58F",
      doctorName: "Dr. Ramesh Gupta",
      department: "Cardiology",
      chamberNumber: "Chamber 4",
      arrivalTime: "09:12",
      waitTimeMinutes: 18,
      status: "TRIAGED",
      isSlaBreach: false,
    },
    {
      id: "q-3",
      tokenNumber: "NEURO-08",
      patientName: "Kishore Rao",
      mrn: "AV-2026-00398",
      ageGender: "62M",
      doctorName: "Dr. Anita Roy",
      department: "Neurology",
      chamberNumber: "Chamber 2",
      arrivalTime: "08:40",
      waitTimeMinutes: 50,
      status: "WAITING",
      isSlaBreach: true,
    },
    {
      id: "q-4",
      tokenNumber: "ORTHO-22",
      patientName: "Manish Singh",
      mrn: "AV-2026-00421",
      ageGender: "34M",
      doctorName: "Dr. Vikram Seth",
      department: "Orthopedics",
      chamberNumber: "Chamber 7",
      arrivalTime: "09:22",
      waitTimeMinutes: 8,
      status: "WAITING",
      isSlaBreach: false,
    },
    {
      id: "q-5",
      tokenNumber: "CARDIO-12",
      patientName: "Priya Varma",
      mrn: "AV-2026-00384",
      ageGender: "29F",
      doctorName: "Dr. Ramesh Gupta",
      department: "Cardiology",
      chamberNumber: "Chamber 4",
      arrivalTime: "08:30",
      waitTimeMinutes: 15,
      status: "COMPLETED",
      isSlaBreach: false,
    },
  ]);

  const handleCallPatient = (item: OPDQueueItem) => {
    setCalledToken(item.tokenNumber);
    setQueueItems((prev) =>
      prev.map((q) => (q.id === item.id ? { ...q, status: "IN_CONSULT" } : q))
    );
  };

  const handleMarkCompleted = (id: string) => {
    setQueueItems((prev) =>
      prev.map((q) => (q.id === id ? { ...q, status: "COMPLETED" } : q))
    );
  };

  const handleMarkNoShow = (id: string) => {
    setQueueItems((prev) =>
      prev.map((q) => (q.id === id ? { ...q, status: "NO_SHOW" } : q))
    );
  };

  const filteredItems = queueItems.filter(
    (item) => selectedDept === "ALL" || item.department === selectedDept
  );

  const waitingCount = filteredItems.filter((i) => i.status === "WAITING" || i.status === "TRIAGED").length;
  const inConsultCount = filteredItems.filter((i) => i.status === "IN_CONSULT").length;
  const completedCount = filteredItems.filter((i) => i.status === "COMPLETED").length;
  const slaBreachCount = filteredItems.filter((i) => i.isSlaBreach).length;

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-slate-950">
      {/* 1. Header & Live Telemetry Strip */}
      <div className="p-4 bg-slate-900 border-b border-slate-800 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-bold text-slate-100">Outpatient (OPD) Command Center & Queue Board</h1>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 flex items-center gap-1 font-bold">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> LIVE STREAM
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time chamber queues, waiting-room telemetry, and TV display announcements.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Department Filter */}
          <div className="flex items-center gap-2 text-xs">
            <Filter size={14} className="text-slate-400" />
            <select
              value={selectedDept}
              onChange={(e) => setSelectedDept(e.target.value)}
              className="px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
            >
              <option value="ALL">All Departments</option>
              <option value="Cardiology">Cardiology</option>
              <option value="Neurology">Neurology</option>
              <option value="Orthopedics">Orthopedics</option>
              <option value="Pediatrics">Pediatrics</option>
            </select>
          </div>

          <Button
            onClick={() => setIsTvDisplayOpen(true)}
            variant="outline"
            className="flex items-center gap-1.5 text-xs text-sky-400 border-sky-800 bg-sky-950/40 hover:bg-sky-900/60 font-bold"
          >
            <Tv size={14} />
            <span>Waiting Room TV Mode</span>
          </Button>
        </div>
      </div>

      {/* 2. OPD Executive Metrics KPI Strip */}
      <div className="p-4 border-b border-slate-800/80 bg-slate-900/40 grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="p-3 bg-slate-900 border-slate-800">
          <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">Patients In Lobby</div>
          <div className="text-xl font-black font-mono text-slate-100 mt-1 flex items-baseline gap-2">
            <span>{waitingCount}</span>
            <span className="text-[10px] text-slate-500 font-normal">Waiting</span>
          </div>
        </Card>
        <Card className="p-3 bg-slate-900 border-slate-800">
          <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">In Consultation</div>
          <div className="text-xl font-black font-mono text-sky-400 mt-1 flex items-baseline gap-2">
            <span>{inConsultCount}</span>
            <span className="text-[10px] text-slate-500 font-normal">Active Chambers</span>
          </div>
        </Card>
        <Card className="p-3 bg-slate-900 border-slate-800">
          <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">Completed Today</div>
          <div className="text-xl font-black font-mono text-emerald-400 mt-1 flex items-baseline gap-2">
            <span>{completedCount}</span>
            <span className="text-[10px] text-slate-500 font-normal">Checked Out</span>
          </div>
        </Card>
        <Card className="p-3 bg-slate-900 border-slate-800">
          <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">SLA Breaches (&gt;45m)</div>
          <div className="text-xl font-black font-mono text-rose-400 mt-1 flex items-baseline gap-2">
            <span>{slaBreachCount}</span>
            <span className="text-[10px] text-rose-500 font-normal">Urgent Delay</span>
          </div>
        </Card>
      </div>

      {/* 3. Multi-Chamber Queue Visualizer */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 h-full">
          {/* COLUMN 1: WAITING & TRIAGED IN LOBBY */}
          <div className="flex flex-col bg-slate-900/50 rounded-xl border border-slate-800 p-3 overflow-hidden">
            <div className="flex items-center justify-between pb-2.5 border-b border-slate-800 mb-3">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <Clock size={14} className="text-amber-400" /> Lobby Waiting Queue
              </span>
              <Badge variant="warning">{waitingCount}</Badge>
            </div>
            <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
              {filteredItems
                .filter((item) => item.status === "WAITING" || item.status === "TRIAGED")
                .map((item) => (
                  <Card
                    key={item.id}
                    className={`p-3 bg-slate-900 border transition-all ${
                      item.isSlaBreach ? "border-rose-700/80 shadow-rose-950/50 shadow-md" : "border-slate-800"
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <span className="font-mono font-bold text-sky-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                        {item.tokenNumber}
                      </span>
                      <span className={`text-[10px] font-mono ${item.isSlaBreach ? "text-rose-400 font-bold" : "text-slate-400"}`}>
                        Wait: {item.waitTimeMinutes}m {item.isSlaBreach && "⚠️ SLA"}
                      </span>
                    </div>
                    <div className="font-bold text-sm text-slate-200">{item.patientName}</div>
                    <div className="text-[11px] text-slate-400 flex items-center justify-between mt-1">
                      <span>{item.department}</span>
                      <span className="font-semibold text-slate-300">{item.chamberNumber}</span>
                    </div>
                    <div className="mt-2.5 pt-2 border-t border-slate-800/80 flex items-center justify-between">
                      <Button
                        onClick={() => handleCallPatient(item)}
                        className="flex items-center gap-1 text-[11px] py-1 px-2.5 bg-sky-600 hover:bg-sky-500 text-slate-950 font-bold"
                      >
                        <Volume2 size={12} /> Call In
                      </Button>
                      <button
                        onClick={() => handleMarkNoShow(item.id)}
                        className="text-[10px] text-slate-500 hover:text-rose-400 underline"
                      >
                        No-Show
                      </button>
                    </div>
                  </Card>
                ))}
            </div>
          </div>

          {/* COLUMN 2: IN CONSULTATION (CHAMBER) */}
          <div className="flex flex-col bg-slate-900/50 rounded-xl border border-slate-800 p-3 overflow-hidden">
            <div className="flex items-center justify-between pb-2.5 border-b border-slate-800 mb-3">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <Stethoscope size={14} className="text-sky-400" /> In Consultation
              </span>
              <Badge variant="info">{inConsultCount}</Badge>
            </div>
            <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
              {filteredItems
                .filter((item) => item.status === "IN_CONSULT")
                .map((item) => (
                  <Card key={item.id} className="p-3 bg-slate-900 border-sky-800/70 shadow-lg shadow-sky-950/20">
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <span className="font-mono font-bold text-sky-400 bg-slate-950 px-2 py-0.5 rounded border border-sky-800">
                        {item.tokenNumber}
                      </span>
                      <Badge variant="info">IN CHAMBER</Badge>
                    </div>
                    <div className="font-bold text-sm text-slate-100">{item.patientName}</div>
                    <div className="text-[11px] text-slate-400 mt-1">
                      Consulting: <span className="font-semibold text-slate-200">{item.doctorName}</span>
                    </div>
                    <div className="text-[11px] text-sky-400 font-mono mt-0.5">{item.chamberNumber}</div>
                    <div className="mt-2.5 pt-2 border-t border-slate-800/80 flex items-center justify-end">
                      <Button
                        onClick={() => handleMarkCompleted(item.id)}
                        className="flex items-center gap-1 text-[11px] py-1 px-3 bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-bold"
                      >
                        <CheckCircle2 size={12} /> Complete Visit
                      </Button>
                    </div>
                  </Card>
                ))}
            </div>
          </div>

          {/* COLUMN 3: COMPLETED VISITS */}
          <div className="flex flex-col bg-slate-900/50 rounded-xl border border-slate-800 p-3 overflow-hidden">
            <div className="flex items-center justify-between pb-2.5 border-b border-slate-800 mb-3">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <CheckCircle2 size={14} className="text-emerald-400" /> Completed & Checked Out
              </span>
              <Badge variant="success">{completedCount}</Badge>
            </div>
            <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
              {filteredItems
                .filter((item) => item.status === "COMPLETED")
                .map((item) => (
                  <Card key={item.id} className="p-3 bg-slate-900/80 border-slate-800/80 opacity-80">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-mono text-slate-400">{item.tokenNumber}</span>
                      <span className="text-[10px] text-emerald-400 font-bold">Checked Out</span>
                    </div>
                    <div className="font-semibold text-xs text-slate-200">{item.patientName}</div>
                    <div className="text-[10px] text-slate-500 font-mono mt-0.5">{item.doctorName} • {item.department}</div>
                  </Card>
                ))}
            </div>
          </div>
        </div>
      </div>

      {/* 4. Fullscreen Public Waiting Room TV Display Mode */}
      {isTvDisplayOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950 flex flex-col p-8 select-none animate-fadeIn">
          <div className="flex items-center justify-between pb-6 border-b border-slate-800">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-sky-500 flex items-center justify-center text-slate-950 font-black text-lg">
                OPD
              </div>
              <div>
                <h1 className="text-2xl font-black text-slate-100 tracking-wide">AVINYA HOSPITAL QUEUE DISPLAY</h1>
                <p className="text-sm font-mono text-sky-400">Please proceed to your assigned chamber when called</p>
              </div>
            </div>
            <Button
              onClick={() => setIsTvDisplayOpen(false)}
              variant="outline"
              className="text-xs text-slate-400 border-slate-700"
            >
              Exit TV Display
            </Button>
          </div>

          <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-8 py-8">
            {/* Active Token Call Box */}
            <div className="rounded-3xl bg-gradient-to-br from-sky-950/80 to-slate-900 border-2 border-sky-500/80 p-8 flex flex-col justify-center items-center text-center shadow-2xl shadow-sky-500/20">
              <div className="text-sm font-mono uppercase tracking-widest text-sky-300 font-bold mb-2">NOW CALLING</div>
              <div className="text-7xl font-black font-mono text-white tracking-tight mb-4 animate-pulse">
                {calledToken || "CARDIO-14"}
              </div>
              <div className="text-2xl font-bold text-slate-200 mb-1">PROCEED TO CHAMBER 4</div>
              <div className="text-sm font-semibold text-sky-400">Dr. Ramesh Gupta • Cardiology</div>
            </div>

            {/* Waiting List Preview */}
            <div className="rounded-3xl bg-slate-900 border border-slate-800 p-6 flex flex-col">
              <div className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-4 border-b border-slate-800 pb-2">
                Upcoming Queue
              </div>
              <div className="flex-1 divide-y divide-slate-800 overflow-y-auto">
                {queueItems
                  .filter((i) => i.status === "WAITING" || i.status === "TRIAGED")
                  .map((item) => (
                    <div key={item.id} className="py-3 flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <span className="font-mono text-xl font-bold text-sky-400">{item.tokenNumber}</span>
                        <div>
                          <div className="text-base font-bold text-slate-200">{item.patientName.charAt(0)}***</div>
                          <div className="text-xs text-slate-500">{item.department}</div>
                        </div>
                      </div>
                      <Badge variant="warning">{item.chamberNumber}</Badge>
                    </div>
                  ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
