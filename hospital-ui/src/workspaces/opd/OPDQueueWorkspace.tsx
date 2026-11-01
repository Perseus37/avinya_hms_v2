import React, { useState, useEffect, useRef } from "react";
import {
  Clock,
  CheckCircle2,
  Volume2,
  VolumeX,
  Tv,
  Filter,
  Stethoscope,
  AlertTriangle,
  ArrowRight,
  UserCheck,
  RotateCcw,
  RefreshCw,
  X,
  ShieldCheck,
  Megaphone,
  Sparkles,
} from "lucide-react";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { useHospitalConfig } from "../../core/context/HospitalConfigContext";

export type ChamberDoctorStatus = "IN_CHAMBER" | "ON_ROUNDS" | "IN_OT" | "PAUSED";

export interface OPDQueueItem {
  id: string;
  tokenNumber: string;
  patientName: string;
  mrn: string;
  ageGender: string;
  doctorId: string;
  doctorName: string;
  department: string;
  chamberNumber: string;
  arrivalTime: string;
  waitTimeMinutes: number;
  status: "WAITING" | "TRIAGED" | "IN_CONSULT" | "LAB_TRANSIT" | "COMPLETED" | "NO_SHOW";
  isSlaBreach: boolean;
  priorityLevel: "ROUTINE" | "PRIORITY" | "STAT";
  revisitType: "NEW_VISIT" | "FREE_REVISIT" | "PAID_FOLLOWUP";
  revisitDayElapsed?: number;
  revisitWindowMaxDays?: number;
}

export const OPDQueueWorkspace: React.FC = () => {
  const { doctors, departments, hospitalProfile } = useHospitalConfig();

  const [selectedDept, setSelectedDept] = useState<string>("ALL");
  const [isTvDisplayOpen, setIsTvDisplayOpen] = useState(false);
  const [calledToken, setCalledToken] = useState<OPDQueueItem | null>(null);
  const [audioEnabled, setAudioEnabled] = useState<boolean>(true);
  const [currentTime, setCurrentTime] = useState<string>(new Date().toLocaleTimeString());

  // Doctor Chamber Presence state (defaults to IN_CHAMBER)
  const [doctorStatuses, setDoctorStatuses] = useState<Record<string, ChamberDoctorStatus>>({
    "doc-1": "IN_CHAMBER",
    "doc-2": "IN_CHAMBER",
    "doc-3": "IN_OT",
    "doc-4": "IN_CHAMBER",
    "doc-5": "ON_ROUNDS",
    "doc-6": "IN_CHAMBER",
    "doc-7": "IN_CHAMBER",
  });

  // Reassignment Modal state
  const [reassignItem, setReassignItem] = useState<OPDQueueItem | null>(null);
  const [targetDoctorId, setTargetDoctorId] = useState<string>("");

  // Realistic sample OPD Queue
  const [queueItems, setQueueItems] = useState<OPDQueueItem[]>([
    {
      id: "q-1",
      tokenNumber: "CARD-101",
      patientName: "Arun K. Sharma",
      mrn: "AV-2026-00912",
      ageGender: "56M",
      doctorId: "doc-1",
      doctorName: "Dr. Vikram Seth",
      department: "Cardiology",
      chamberNumber: "OPD Cabin 204",
      arrivalTime: "09:02",
      waitTimeMinutes: 38,
      status: "IN_CONSULT",
      isSlaBreach: true,
      priorityLevel: "ROUTINE",
      revisitType: "FREE_REVISIT",
      revisitDayElapsed: 4,
      revisitWindowMaxDays: 7,
    },
    {
      id: "q-2",
      tokenNumber: "CARD-102",
      patientName: "Sunita Deshmukh",
      mrn: "AV-2026-00915",
      ageGender: "62F",
      doctorId: "doc-1",
      doctorName: "Dr. Vikram Seth",
      department: "Cardiology",
      chamberNumber: "OPD Cabin 204",
      arrivalTime: "09:15",
      waitTimeMinutes: 25,
      status: "TRIAGED",
      isSlaBreach: false,
      priorityLevel: "PRIORITY",
      revisitType: "NEW_VISIT",
    },
    {
      id: "q-3",
      tokenNumber: "CARD-103",
      patientName: "Mohan Lal Gupta",
      mrn: "AV-2026-00918",
      ageGender: "69M",
      doctorId: "doc-1",
      doctorName: "Dr. Vikram Seth",
      department: "Cardiology",
      chamberNumber: "OPD Cabin 204",
      arrivalTime: "09:28",
      waitTimeMinutes: 12,
      status: "WAITING",
      isSlaBreach: false,
      priorityLevel: "STAT",
      revisitType: "FREE_REVISIT",
      revisitDayElapsed: 6,
      revisitWindowMaxDays: 7,
    },
    {
      id: "q-4",
      tokenNumber: "MED-201",
      patientName: "Kavita Reddy",
      mrn: "AV-2026-00922",
      ageGender: "44F",
      doctorId: "doc-2",
      doctorName: "Dr. Rajesh Sharma",
      department: "General Medicine",
      chamberNumber: "OPD Cabin 102",
      arrivalTime: "08:50",
      waitTimeMinutes: 50,
      status: "WAITING",
      isSlaBreach: true,
      priorityLevel: "ROUTINE",
      revisitType: "FREE_REVISIT",
      revisitDayElapsed: 3,
      revisitWindowMaxDays: 10,
    },
    {
      id: "q-5",
      tokenNumber: "MED-202",
      patientName: "Praveen Nair",
      mrn: "AV-2026-00925",
      ageGender: "38M",
      doctorId: "doc-2",
      doctorName: "Dr. Rajesh Sharma",
      department: "General Medicine",
      chamberNumber: "OPD Cabin 102",
      arrivalTime: "09:10",
      waitTimeMinutes: 30,
      status: "WAITING",
      isSlaBreach: false,
      priorityLevel: "ROUTINE",
      revisitType: "NEW_VISIT",
    },
    {
      id: "q-6",
      tokenNumber: "PED-301",
      patientName: "Baby Aarav Patel",
      mrn: "AV-2026-00930",
      ageGender: "3M",
      doctorId: "doc-4",
      doctorName: "Dr. Sunita Rao",
      department: "Pediatrics",
      chamberNumber: "OPD Cabin 105",
      arrivalTime: "09:22",
      waitTimeMinutes: 18,
      status: "IN_CONSULT",
      isSlaBreach: false,
      priorityLevel: "PRIORITY",
      revisitType: "NEW_VISIT",
    },
    {
      id: "q-7",
      tokenNumber: "PED-302",
      patientName: "Ananya Iyer",
      mrn: "AV-2026-00934",
      ageGender: "7F",
      doctorId: "doc-4",
      doctorName: "Dr. Sunita Rao",
      department: "Pediatrics",
      chamberNumber: "OPD Cabin 105",
      arrivalTime: "09:30",
      waitTimeMinutes: 10,
      status: "WAITING",
      isSlaBreach: false,
      priorityLevel: "ROUTINE",
      revisitType: "FREE_REVISIT",
      revisitDayElapsed: 2,
      revisitWindowMaxDays: 7,
    },
    {
      id: "q-8",
      tokenNumber: "SURG-401",
      patientName: "Ramesh Chander",
      mrn: "AV-2026-00902",
      ageGender: "51M",
      doctorId: "doc-3",
      doctorName: "Dr. Radhika Sen",
      department: "General Surgery",
      chamberNumber: "OPD Cabin 210",
      arrivalTime: "08:45",
      waitTimeMinutes: 55,
      status: "WAITING",
      isSlaBreach: true,
      priorityLevel: "ROUTINE",
      revisitType: "FREE_REVISIT",
      revisitDayElapsed: 8,
      revisitWindowMaxDays: 14,
    },
  ]);

  const tvAnnouncementTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Live Clock for TV Mode & Header
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date().toLocaleTimeString());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Set initial called token
  useEffect(() => {
    if (!calledToken && queueItems.length > 0) {
      setCalledToken(queueItems[0]);
    }
  }, [queueItems, calledToken]);

  // Audio Chime & Speech Synthesis Engine
  const playChimeTone = () => {
    if (!audioEnabled) return;
    try {
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const now = ctx.currentTime;

      // Bell chime: Tone 1 (D5 ~587.33 Hz)
      const osc1 = ctx.createOscillator();
      const gain1 = ctx.createGain();
      osc1.type = "sine";
      osc1.frequency.setValueAtTime(587.33, now);
      gain1.gain.setValueAtTime(0.3, now);
      gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.6);
      osc1.connect(gain1);
      gain1.connect(ctx.destination);
      osc1.start(now);
      osc1.stop(now + 0.6);

      // Harmonious response: Tone 2 (A4 ~440.00 Hz)
      const osc2 = ctx.createOscillator();
      const gain2 = ctx.createGain();
      osc2.type = "sine";
      osc2.frequency.setValueAtTime(440, now + 0.25);
      gain2.gain.setValueAtTime(0.35, now + 0.25);
      gain2.gain.exponentialRampToValueAtTime(0.001, now + 1.0);
      osc2.connect(gain2);
      gain2.connect(ctx.destination);
      osc2.start(now + 0.25);
      osc2.stop(now + 1.0);
    } catch {
      // AudioContext may be restricted by browser policy before first interaction
    }
  };

  const speakTokenAnnouncement = (item: OPDQueueItem) => {
    if (!audioEnabled || !("speechSynthesis" in window)) return;
    try {
      window.speechSynthesis.cancel();
      const text = `Token number ${item.tokenNumber}. Patient ${item.patientName}. Please proceed to ${item.chamberNumber}, ${item.doctorName}.`;
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.88;
      utterance.pitch = 1.02;
      utterance.lang = "en-IN";
      window.speechSynthesis.speak(utterance);
    } catch {
      // Silently catch speech synthesis exceptions
    }
  };

  const handleCallPatient = (item: OPDQueueItem) => {
    setCalledToken(item);
    setQueueItems((prev) =>
      prev.map((q) =>
        q.id === item.id
          ? { ...q, status: "IN_CONSULT" }
          : q.doctorId === item.doctorId && q.status === "IN_CONSULT"
          ? { ...q, status: "COMPLETED" }
          : q
      )
    );

    // Play chime then voice announcement
    playChimeTone();
    if (tvAnnouncementTimerRef.current) clearTimeout(tvAnnouncementTimerRef.current);
    tvAnnouncementTimerRef.current = setTimeout(() => {
      speakTokenAnnouncement(item);
    }, 600);
  };

  const handleRepeatCall = () => {
    if (!calledToken) return;
    playChimeTone();
    setTimeout(() => {
      speakTokenAnnouncement(calledToken);
    }, 600);
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

  const handleToggleDoctorStatus = (docId: string) => {
    setDoctorStatuses((prev) => {
      const current = prev[docId] || "IN_CHAMBER";
      const nextMap: Record<ChamberDoctorStatus, ChamberDoctorStatus> = {
        IN_CHAMBER: "ON_ROUNDS",
        ON_ROUNDS: "IN_OT",
        IN_OT: "PAUSED",
        PAUSED: "IN_CHAMBER",
      };
      return { ...prev, [docId]: nextMap[current] };
    });
  };

  const handleExecuteReassignment = () => {
    if (!reassignItem || !targetDoctorId) return;
    const targetDoc = doctors.find((d) => d.id === targetDoctorId);
    if (!targetDoc) return;

    setQueueItems((prev) =>
      prev.map((q) =>
        q.id === reassignItem.id
          ? {
              ...q,
              doctorId: targetDoc.id,
              doctorName: targetDoc.name,
              department: targetDoc.department,
              chamberNumber: targetDoc.roomNumber,
            }
          : q
      )
    );
    setReassignItem(null);
    setTargetDoctorId("");
  };

  const filteredItems = queueItems.filter(
    (item) => selectedDept === "ALL" || item.department === selectedDept
  );

  const waitingCount = filteredItems.filter(
    (i) => i.status === "WAITING" || i.status === "TRIAGED"
  ).length;
  const inConsultCount = filteredItems.filter((i) => i.status === "IN_CONSULT").length;
  const completedCount = filteredItems.filter((i) => i.status === "COMPLETED").length;
  const slaBreachCount = filteredItems.filter(
    (i) => i.isSlaBreach && (i.status === "WAITING" || i.status === "TRIAGED")
  ).length;

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-slate-950 font-sans">
      {/* 1. Header & Live Telemetry Strip */}
      <div className="p-4 bg-slate-900 border-b border-slate-800 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <Megaphone className="w-5 h-5 text-sky-400" />
              OPD Command Center & Smart Queue Board
            </h1>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 flex items-center gap-1 font-bold">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> LIVE STREAM
            </span>
            <span className="text-xs font-mono text-slate-400 bg-slate-950 px-2.5 py-0.5 rounded border border-slate-800">
              {currentTime}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Synchronized with <span className="text-slate-200 font-semibold">{hospitalProfile.name}</span> chamber roster & revisit policy radar.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          {/* Department Filter */}
          <div className="flex items-center gap-1.5 text-xs">
            <Filter size={14} className="text-slate-400" />
            <select
              value={selectedDept}
              onChange={(e) => setSelectedDept(e.target.value)}
              className="px-2.5 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
            >
              <option value="ALL">All Departments ({departments.length})</option>
              {departments.map((dept) => (
                <option key={dept} value={dept}>
                  {dept}
                </option>
              ))}
            </select>
          </div>

          {/* Audio Chime Mute/Unmute */}
          <Button
            onClick={() => setAudioEnabled(!audioEnabled)}
            variant="outline"
            className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 border ${
              audioEnabled
                ? "text-emerald-400 border-emerald-800 bg-emerald-950/40 hover:bg-emerald-900/60"
                : "text-slate-500 border-slate-800 bg-slate-900 hover:text-slate-300"
            }`}
            title={audioEnabled ? "Voice announcement enabled" : "Voice announcement muted"}
          >
            {audioEnabled ? <Volume2 size={14} /> : <VolumeX size={14} />}
            <span>{audioEnabled ? "Audio Chime ON" : "Muted"}</span>
          </Button>

          {/* Waiting Room TV Mode Button */}
          <Button
            onClick={() => setIsTvDisplayOpen(true)}
            variant="outline"
            className="flex items-center gap-1.5 text-xs text-sky-400 border-sky-800 bg-sky-950/50 hover:bg-sky-900/70 font-bold px-3 py-1.5"
          >
            <Tv size={14} />
            <span>Launch TV Lounge Display (4K)</span>
          </Button>
        </div>
      </div>

      {/* 2. Doctor Chamber Presence Status Bar */}
      <div className="px-4 py-2 bg-slate-900/80 border-b border-slate-800/80 flex items-center gap-3 overflow-x-auto text-xs">
        <span className="text-[10px] uppercase font-bold text-slate-400 whitespace-nowrap tracking-wider">
          Chamber Roster:
        </span>
        <div className="flex items-center gap-2">
          {doctors.map((doc) => {
            const status = doctorStatuses[doc.id] || "IN_CHAMBER";
            const waitingForDoc = queueItems.filter(
              (q) => q.doctorId === doc.id && (q.status === "WAITING" || q.status === "TRIAGED")
            ).length;

            return (
              <button
                key={doc.id}
                onClick={() => handleToggleDoctorStatus(doc.id)}
                title={`Click to toggle ${doc.name} status (Currently: ${status})`}
                className={`flex items-center gap-2 px-2.5 py-1 rounded-md border text-left transition-all ${
                  status === "IN_CHAMBER"
                    ? "bg-emerald-950/40 border-emerald-800 text-slate-200 hover:border-emerald-700"
                    : status === "ON_ROUNDS"
                    ? "bg-amber-950/40 border-amber-800 text-amber-200 hover:border-amber-700"
                    : status === "IN_OT"
                    ? "bg-purple-950/40 border-purple-800 text-purple-200 hover:border-purple-700"
                    : "bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-700"
                }`}
              >
                <div className="flex flex-col">
                  <div className="flex items-center gap-1.5">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        status === "IN_CHAMBER"
                          ? "bg-emerald-400 animate-pulse"
                          : status === "ON_ROUNDS"
                          ? "bg-amber-400"
                          : status === "IN_OT"
                          ? "bg-purple-400 animate-ping"
                          : "bg-slate-600"
                      }`}
                    />
                    <span className="font-semibold text-[11px]">{doc.name}</span>
                  </div>
                  <div className="text-[10px] text-slate-400 flex items-center gap-1">
                    <span>{doc.roomNumber}</span>
                    <span className="text-sky-400 font-mono font-bold">({waitingForDoc} wait)</span>
                  </div>
                </div>
                <Badge
                  variant={
                    status === "IN_CHAMBER"
                      ? "success"
                      : status === "ON_ROUNDS"
                      ? "warning"
                      : status === "IN_OT"
                      ? "purple"
                      : "neutral"
                  }
                  className="text-[9px] px-1 py-0 uppercase tracking-tighter"
                >
                  {status === "IN_CHAMBER"
                    ? "Active"
                    : status === "ON_ROUNDS"
                    ? "Rounds"
                    : status === "IN_OT"
                    ? "In OT"
                    : "Paused"}
                </Badge>
              </button>
            );
          })}
        </div>
      </div>

      {/* 3. OPD Executive Metrics KPI Strip */}
      <div className="p-4 border-b border-slate-800/80 bg-slate-900/40 grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="p-3 bg-slate-900 border-slate-800">
          <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider flex items-center justify-between">
            <span>Patients In Lobby</span>
            <Clock size={12} className="text-amber-400" />
          </div>
          <div className="text-2xl font-black font-mono text-slate-100 mt-1 flex items-baseline gap-2">
            <span>{waitingCount}</span>
            <span className="text-[10px] text-slate-500 font-normal">Waiting in queue</span>
          </div>
        </Card>
        <Card className="p-3 bg-slate-900 border-slate-800">
          <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider flex items-center justify-between">
            <span>In Consultation</span>
            <Stethoscope size={12} className="text-sky-400" />
          </div>
          <div className="text-2xl font-black font-mono text-sky-400 mt-1 flex items-baseline gap-2">
            <span>{inConsultCount}</span>
            <span className="text-[10px] text-slate-500 font-normal">Active Chambers</span>
          </div>
        </Card>
        <Card className="p-3 bg-slate-900 border-slate-800">
          <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider flex items-center justify-between">
            <span>Completed Today</span>
            <CheckCircle2 size={12} className="text-emerald-400" />
          </div>
          <div className="text-2xl font-black font-mono text-emerald-400 mt-1 flex items-baseline gap-2">
            <span>{completedCount}</span>
            <span className="text-[10px] text-slate-500 font-normal">Checked Out</span>
          </div>
        </Card>
        <Card className="p-3 bg-slate-900 border-slate-800">
          <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider flex items-center justify-between">
            <span>SLA Breaches (&gt;30m)</span>
            <AlertTriangle size={12} className="text-rose-400" />
          </div>
          <div className="text-2xl font-black font-mono text-rose-400 mt-1 flex items-baseline gap-2">
            <span>{slaBreachCount}</span>
            <span className="text-[10px] text-rose-500 font-normal">Needs Intervention</span>
          </div>
        </Card>
      </div>

      {/* 4. Active Chamber Call Ribbon */}
      {calledToken && (
        <div className="px-4 py-2.5 bg-sky-950/40 border-b border-sky-800/80 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="flex h-3 w-3 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-sky-500"></span>
            </span>
            <div className="flex items-center gap-2">
              <span className="text-xs uppercase font-mono tracking-widest text-sky-300 font-bold">
                LAST CALLED:
              </span>
              <span className="font-mono font-black text-sm px-2 py-0.5 rounded bg-sky-500 text-slate-950">
                {calledToken.tokenNumber}
              </span>
              <span className="text-xs font-bold text-slate-200">{calledToken.patientName}</span>
              <span className="text-xs text-slate-400">→</span>
              <span className="text-xs font-semibold text-sky-300">{calledToken.chamberNumber}</span>
              <span className="text-xs text-slate-400 font-mono">({calledToken.doctorName})</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              onClick={handleRepeatCall}
              variant="outline"
              className="text-xs py-1 px-2.5 flex items-center gap-1 border-sky-700 text-sky-300 hover:bg-sky-900/50"
            >
              <RotateCcw size={12} /> Repeat Announcement
            </Button>
          </div>
        </div>
      )}

      {/* 5. Tri-Column Workflow Visualizer */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 h-full">
          {/* COLUMN 1: WAITING & TRIAGED IN LOBBY */}
          <div className="flex flex-col bg-slate-900/60 rounded-xl border border-slate-800 p-3 overflow-hidden">
            <div className="flex items-center justify-between pb-2.5 border-b border-slate-800 mb-3">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <Clock size={14} className="text-amber-400" /> Lobby Waiting Queue
              </span>
              <div className="flex items-center gap-1.5">
                <Badge variant="warning">{waitingCount}</Badge>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
              {filteredItems
                .filter((item) => item.status === "WAITING" || item.status === "TRIAGED")
                .map((item) => (
                  <Card
                    key={item.id}
                    className={`p-3 bg-slate-900 border transition-all ${
                      item.isSlaBreach
                        ? "border-rose-700/80 shadow-rose-950/40 shadow-md"
                        : "border-slate-800 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <div className="flex items-center gap-1.5">
                        <span className="font-mono font-bold text-sky-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                          {item.tokenNumber}
                        </span>
                        {item.priorityLevel === "STAT" && (
                          <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-rose-950 text-rose-300 border border-rose-800 animate-pulse">
                            STAT
                          </span>
                        )}
                        {item.priorityLevel === "PRIORITY" && (
                          <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-amber-950 text-amber-300 border border-amber-800">
                            PRIORITY
                          </span>
                        )}
                      </div>
                      <span
                        className={`text-[10px] font-mono ${
                          item.isSlaBreach ? "text-rose-400 font-bold" : "text-slate-400"
                        }`}
                      >
                        Wait: {item.waitTimeMinutes}m {item.isSlaBreach && "⚠️ SLA"}
                      </span>
                    </div>

                    <div className="flex items-baseline justify-between">
                      <div className="font-bold text-sm text-slate-200">{item.patientName}</div>
                      <div className="text-[10px] font-mono text-slate-400">{item.ageGender} • {item.mrn}</div>
                    </div>

                    {/* Revisit indicator */}
                    <div className="mt-1 flex items-center gap-1">
                      {item.revisitType === "FREE_REVISIT" ? (
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-950/70 text-emerald-400 border border-emerald-800">
                          <Sparkles size={10} /> FREE REVISIT (Day {item.revisitDayElapsed}/{item.revisitWindowMaxDays})
                        </span>
                      ) : item.revisitType === "PAID_FOLLOWUP" ? (
                        <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                          Follow-up (Paid)
                        </span>
                      ) : (
                        <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-slate-800/60 text-slate-400">
                          New Consultation
                        </span>
                      )}
                    </div>

                    <div className="text-[11px] text-slate-400 flex items-center justify-between mt-1.5 pt-1.5 border-t border-slate-800/60">
                      <span>{item.department}</span>
                      <span className="font-semibold text-slate-300">{item.chamberNumber} ({item.doctorName})</span>
                    </div>

                    <div className="mt-2.5 pt-2 border-t border-slate-800 flex items-center justify-between">
                      <Button
                        onClick={() => handleCallPatient(item)}
                        className="flex items-center gap-1 text-[11px] py-1 px-3 bg-sky-600 hover:bg-sky-500 text-slate-950 font-bold"
                      >
                        <Volume2 size={12} /> Call In
                      </Button>

                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => {
                            setReassignItem(item);
                            setTargetDoctorId(doctors[0]?.id || "");
                          }}
                          className="text-[10px] text-sky-400 hover:text-sky-300 underline"
                          title="Transfer token to another available doctor"
                        >
                          Transfer
                        </button>
                        <button
                          onClick={() => handleMarkNoShow(item.id)}
                          className="text-[10px] text-slate-500 hover:text-rose-400 underline"
                        >
                          No-Show
                        </button>
                      </div>
                    </div>
                  </Card>
                ))}
            </div>
          </div>

          {/* COLUMN 2: IN CONSULTATION (CHAMBER) */}
          <div className="flex flex-col bg-slate-900/60 rounded-xl border border-slate-800 p-3 overflow-hidden">
            <div className="flex items-center justify-between pb-2.5 border-b border-slate-800 mb-3">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <Stethoscope size={14} className="text-sky-400" /> In Consultation (Active)
              </span>
              <Badge variant="info">{inConsultCount}</Badge>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2.5 pr-1">
              {filteredItems
                .filter((item) => item.status === "IN_CONSULT")
                .map((item) => (
                  <Card
                    key={item.id}
                    className="p-3 bg-slate-900 border-sky-800/80 shadow-lg shadow-sky-950/20"
                  >
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
                    <div className="text-[11px] text-sky-400 font-mono mt-0.5 flex items-center justify-between">
                      <span>{item.chamberNumber}</span>
                      <span className="text-slate-400 text-[10px]">MRN: {item.mrn}</span>
                    </div>

                    <div className="mt-3 pt-2 border-t border-slate-800 flex items-center justify-between">
                      <Button
                        onClick={() => {
                          setCalledToken(item);
                          handleRepeatCall();
                        }}
                        variant="outline"
                        className="text-[10px] py-1 px-2 text-slate-300 border-slate-700 hover:text-white"
                      >
                        <Volume2 size={11} className="mr-1" /> Re-announce
                      </Button>

                      <Button
                        onClick={() => handleMarkCompleted(item.id)}
                        className="flex items-center gap-1 text-[11px] py-1 px-3 bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-bold"
                      >
                        <CheckCircle2 size={12} /> Complete Consultation
                      </Button>
                    </div>
                  </Card>
                ))}
            </div>
          </div>

          {/* COLUMN 3: COMPLETED VISITS */}
          <div className="flex flex-col bg-slate-900/60 rounded-xl border border-slate-800 p-3 overflow-hidden">
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
                  <Card
                    key={item.id}
                    className="p-3 bg-slate-900/80 border-slate-800/80 opacity-80"
                  >
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-mono text-slate-400 font-bold">{item.tokenNumber}</span>
                      <span className="text-[10px] text-emerald-400 font-bold flex items-center gap-1">
                        <UserCheck size={11} /> Checked Out
                      </span>
                    </div>
                    <div className="font-semibold text-xs text-slate-200">{item.patientName}</div>
                    <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                      {item.doctorName} • {item.department}
                    </div>
                  </Card>
                ))}
            </div>
          </div>
        </div>
      </div>

      {/* 6. Reassignment Modal */}
      {reassignItem && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 max-w-md w-full shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
              <h3 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                <RefreshCw size={15} className="text-sky-400" /> Transfer Patient Queue Token
              </h3>
              <button
                onClick={() => setReassignItem(null)}
                className="text-slate-400 hover:text-white"
              >
                <X size={16} />
              </button>
            </div>

            <div className="text-xs text-slate-300 space-y-2 mb-4 bg-slate-950 p-3 rounded border border-slate-800">
              <div>
                Patient: <span className="font-bold text-white">{reassignItem.patientName}</span> ({reassignItem.tokenNumber})
              </div>
              <div>
                Currently Assigned: <span className="text-slate-400">{reassignItem.doctorName} ({reassignItem.chamberNumber})</span>
              </div>
            </div>

            <div className="space-y-1 mb-4">
              <label className="text-xs font-semibold text-slate-300">
                Select Destination Doctor / Chamber:
              </label>
              <select
                value={targetDoctorId}
                onChange={(e) => setTargetDoctorId(e.target.value)}
                className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded text-xs text-white focus:outline-none focus:border-sky-500"
              >
                {doctors
                  .filter((d) => d.id !== reassignItem.doctorId)
                  .map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.department} - {d.roomNumber})
                    </option>
                  ))}
              </select>
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
              <Button
                variant="outline"
                onClick={() => setReassignItem(null)}
                className="text-xs border-slate-700 text-slate-300"
              >
                Cancel
              </Button>
              <Button
                onClick={handleExecuteReassignment}
                className="text-xs bg-sky-600 hover:bg-sky-500 text-slate-950 font-bold"
              >
                Confirm Transfer
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* 7. Fullscreen Public Waiting Room TV Display Mode (4K High Contrast) */}
      {isTvDisplayOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950 flex flex-col p-6 select-none animate-fadeIn">
          {/* TV Top Header */}
          <div className="flex items-center justify-between pb-4 border-b border-slate-800">
            <div className="flex items-center gap-3">
              <div className="h-12 w-12 rounded-xl bg-gradient-to-tr from-sky-600 to-cyan-400 flex items-center justify-center text-slate-950 font-black text-xl shadow-lg shadow-sky-500/30">
                OPD
              </div>
              <div>
                <h1 className="text-2xl font-black text-white tracking-wide flex items-center gap-2">
                  <span>{hospitalProfile.name}</span>
                  <span className="text-xs font-mono font-normal text-emerald-400 border border-emerald-800 bg-emerald-950/60 px-2 py-0.5 rounded">
                    OUTPATIENT DISPLAY
                  </span>
                </h1>
                <p className="text-xs font-mono text-sky-400">
                  Please proceed to your assigned chamber when your token number is announced
                </p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="text-right">
                <div className="text-2xl font-black font-mono text-white tracking-widest">{currentTime}</div>
                <div className="text-xs font-mono text-slate-400">
                  {new Date().toLocaleDateString("en-IN", {
                    weekday: "long",
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  })}
                </div>
              </div>

              <Button
                onClick={() => setIsTvDisplayOpen(false)}
                variant="outline"
                className="text-xs text-slate-400 border-slate-700 hover:text-white"
              >
                Exit TV Mode
              </Button>
            </div>
          </div>

          {/* TV Main Grid */}
          <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 py-4 overflow-hidden">
            {/* Left Col (5 cols): Active Called Token Hero Banner */}
            <div className="lg:col-span-5 flex flex-col gap-4">
              <div className="flex-1 rounded-3xl bg-gradient-to-br from-slate-900 via-sky-950/50 to-slate-900 border-2 border-sky-500/90 p-8 flex flex-col justify-center items-center text-center shadow-2xl shadow-sky-500/20 relative overflow-hidden">
                <div className="absolute top-4 left-6 flex items-center gap-2">
                  <span className="flex h-3 w-3 relative">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                  </span>
                  <span className="text-xs font-mono uppercase tracking-widest text-emerald-400 font-bold">
                    NOW CALLING
                  </span>
                </div>

                <div className="text-8xl font-black font-mono text-white tracking-tight my-4 drop-shadow-[0_10px_20px_rgba(56,189,248,0.4)]">
                  {calledToken ? calledToken.tokenNumber : "CARD-101"}
                </div>

                <div className="text-2xl font-bold text-slate-200 mb-2">
                  {calledToken ? calledToken.patientName : "Patient Call"}
                </div>

                <div className="flex items-center gap-2 text-xl font-bold text-sky-300 bg-sky-950/80 px-4 py-2 rounded-xl border border-sky-800 mb-2">
                  <span>PROCEED TO:</span>
                  <span className="text-white underline decoration-sky-400">
                    {calledToken ? calledToken.chamberNumber : "OPD Cabin 204"}
                  </span>
                  <ArrowRight className="w-5 h-5 text-sky-400 animate-pulse" />
                </div>

                <div className="text-sm font-semibold text-slate-400">
                  {calledToken ? `${calledToken.doctorName} • ${calledToken.department}` : "Cardiology"}
                </div>
              </div>

              {/* Safety notice / Audio icon */}
              <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <ShieldCheck className="w-6 h-6 text-emerald-400" />
                  <div className="text-xs text-slate-300">
                    <div className="font-bold text-slate-200">Patient Courtesy Advisory</div>
                    <div className="text-[11px] text-slate-400">
                      Please keep token slips ready. Wheelchair assistance available at Lounge Desk.
                    </div>
                  </div>
                </div>
                {audioEnabled ? (
                  <Badge variant="success" className="text-[10px]">Audio Chime ON</Badge>
                ) : (
                  <Badge variant="neutral" className="text-[10px]">Muted</Badge>
                )}
              </div>
            </div>

            {/* Right Col (7 cols): Multi-Chamber Status Matrix */}
            <div className="lg:col-span-7 flex flex-col bg-slate-900 border border-slate-800 rounded-3xl p-5 overflow-hidden">
              <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
                <h2 className="text-sm font-black text-slate-200 uppercase tracking-wider flex items-center gap-2">
                  <Stethoscope size={16} className="text-sky-400" /> Active Chambers & Next In Line
                </h2>
                <span className="text-xs font-mono text-slate-400">
                  Total in lobby: <strong className="text-white">{waitingCount}</strong>
                </span>
              </div>

              <div className="flex-1 overflow-y-auto space-y-3 pr-1">
                {doctors.map((doc) => {
                  const status = doctorStatuses[doc.id] || "IN_CHAMBER";
                  const inConsultForDoc = queueItems.find(
                    (q) => q.doctorId === doc.id && q.status === "IN_CONSULT"
                  );
                  const waitingForDoc = queueItems.filter(
                    (q) => q.doctorId === doc.id && (q.status === "WAITING" || q.status === "TRIAGED")
                  );

                  return (
                    <div
                      key={doc.id}
                      className="bg-slate-950 rounded-2xl border border-slate-800/80 p-3 flex items-center justify-between gap-4"
                    >
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-sm text-slate-200">{doc.name}</span>
                          <span className="text-xs text-slate-400 font-mono">({doc.department})</span>
                          <Badge
                            variant={
                              status === "IN_CHAMBER"
                                ? "success"
                                : status === "ON_ROUNDS"
                                ? "warning"
                                : status === "IN_OT"
                                ? "purple"
                                : "neutral"
                            }
                            className="text-[9px]"
                          >
                            {status === "IN_CHAMBER"
                              ? "CONSULTING"
                              : status === "ON_ROUNDS"
                              ? "ON WARD ROUNDS"
                              : status === "IN_OT"
                              ? "EMERGENCY SURGERY"
                              : "PAUSED"}
                          </Badge>
                        </div>
                        <div className="text-xs font-mono text-sky-400 mt-0.5">{doc.roomNumber}</div>
                      </div>

                      {/* Current token in chamber */}
                      <div className="text-right border-l border-slate-800 pl-4 min-w-[130px]">
                        <div className="text-[10px] uppercase font-mono text-slate-500">Currently Inside</div>
                        {inConsultForDoc ? (
                          <div className="font-mono font-black text-lg text-emerald-400">
                            {inConsultForDoc.tokenNumber}
                          </div>
                        ) : (
                          <div className="text-xs text-slate-500 italic">Chamber Ready</div>
                        )}
                      </div>

                      {/* Next waiting tokens */}
                      <div className="text-right border-l border-slate-800 pl-4 min-w-[140px]">
                        <div className="text-[10px] uppercase font-mono text-slate-500">Next In Line</div>
                        <div className="flex items-center justify-end gap-1.5 mt-0.5">
                          {waitingForDoc.length > 0 ? (
                            waitingForDoc.slice(0, 2).map((w, idx) => (
                              <span
                                key={w.id}
                                className={`font-mono text-xs font-bold px-1.5 py-0.5 rounded ${
                                  idx === 0
                                    ? "bg-sky-950 text-sky-300 border border-sky-800"
                                    : "bg-slate-900 text-slate-400"
                                }`}
                              >
                                {w.tokenNumber}
                              </span>
                            ))
                          ) : (
                            <span className="text-xs text-slate-600">No wait</span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Bottom Ticker */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl px-4 py-2 flex items-center gap-3 overflow-hidden">
            <span className="text-[10px] font-bold uppercase tracking-wider text-rose-400 bg-rose-950/80 px-2 py-0.5 rounded border border-rose-800 whitespace-nowrap">
              HOSPITAL NOTICE
            </span>
            <div className="flex-1 overflow-hidden whitespace-nowrap">
              <p className="text-xs text-slate-300 font-medium animate-marquee inline-block">
                Emergency 24x7 Helpline: {hospitalProfile.emergencyPhone} • Pharmacy Counter 4 open for Senior Citizens • Revisit consultations are valid for 7-14 days based on consulting specialist • Thank you for your patience.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
