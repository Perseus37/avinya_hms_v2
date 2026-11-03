import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, Megaphone, RefreshCw, UserRound, Volume2, VolumeX } from "lucide-react";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { opdQueueApi, OPDQueueEntry, OPDQueueReason, OPDQueueSummary } from "../../api/opdQueueApi";

const reasonOptions = [
  ["CLINICAL_PRIORITY", "Clinical priority / emergency"],
  ["DOCTOR_REQUESTED", "Doctor requested"],
  ["SPECIAL_ASSISTANCE", "Special assistance"],
  ["SCHEDULED_PROCEDURE", "Scheduled procedure / review"],
  ["ADMINISTRATIVE_CORRECTION", "Administrative correction"],
  ["OTHER", "Other"],
] as const;

type ActionError = { message: string; status?: number };

function errorFromUnknown(error: unknown): ActionError {
  const message = error instanceof Error ? error.message : "Queue command failed.";
  const statusMatch = message.match(/HTTP Error (\d+)/);
  return { message, status: statusMatch ? Number(statusMatch[1]) : undefined };
}

function stateLabel(state: OPDQueueEntry["state"]): string {
  return state.replaceAll("_", " ");
}

function stateClass(state: OPDQueueEntry["state"]): string {
  switch (state) {
    case "CALLED": return "bg-sky-950 text-sky-300 border-sky-800";
    case "ARRIVED": return "bg-amber-950 text-amber-300 border-amber-800";
    case "IN_CONSULTATION": return "bg-violet-950 text-violet-300 border-violet-800";
    case "ON_HOLD": return "bg-orange-950 text-orange-300 border-orange-800";
    case "COMPLETED": return "bg-emerald-950 text-emerald-300 border-emerald-800";
    case "NO_SHOW": return "bg-rose-950 text-rose-300 border-rose-800";
    default: return "bg-slate-900 text-slate-300 border-slate-700";
  }
}

export const OPDQueueLiveWorkspace: React.FC = () => {
  const [queues, setQueues] = useState<OPDQueueSummary[]>([]);
  const [selectedQueueId, setSelectedQueueId] = useState<number | null>(null);
  const [entries, setEntries] = useState<OPDQueueEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [error, setError] = useState<ActionError | null>(null);
  const [specificEntry, setSpecificEntry] = useState<OPDQueueEntry | null>(null);
  const [reasonCode, setReasonCode] = useState("CLINICAL_PRIORITY");
  const [reasonNote, setReasonNote] = useState("");
  const [audioEnabled, setAudioEnabled] = useState(true);
  const [announcedToken, setAnnouncedToken] = useState<number | null>(null);

  const loadQueues = useCallback(async (showSpinner = false) => {
    if (showSpinner) setRefreshing(true);
    try {
      const result = await opdQueueApi.listQueues();
      setQueues(result);
      setSelectedQueueId((current) => current && result.some((q) => q.id === current) ? current : result[0]?.id ?? null);
      setError(null);
    } catch (err) {
      setError(errorFromUnknown(err));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const loadEntries = useCallback(async (queueId: number) => {
    try {
      const result = await opdQueueApi.listEntries(queueId);
      setEntries(result);
      setError(null);
    } catch (err) {
      setError(errorFromUnknown(err));
    }
  }, []);

  useEffect(() => { void loadQueues(); }, [loadQueues]);

  useEffect(() => {
    if (selectedQueueId == null) {
      setEntries([]);
      return;
    }
    void loadEntries(selectedQueueId);
    const timer = window.setInterval(() => void loadEntries(selectedQueueId), 5000);
    return () => window.clearInterval(timer);
  }, [selectedQueueId, loadEntries]);

  const selectedQueue = queues.find((q) => q.id === selectedQueueId) ?? null;
  const waiting = useMemo(() => entries.filter((e) => e.state === "WAITING"), [entries]);
  const active = useMemo(() => entries.find((e) => ["CALLED", "ARRIVED", "IN_CONSULTATION"].includes(e.state)), [entries]);
  const completed = useMemo(() => entries.filter((e) => e.state === "COMPLETED").length, [entries]);

  const announce = useCallback((entry: OPDQueueEntry) => {
    setAnnouncedToken(entry.token_number);
    if (!audioEnabled || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(`Token number ${entry.token_number}. Please proceed to the consultation room.`);
    utterance.lang = "en-IN";
    utterance.rate = 0.9;
    window.speechSynthesis.speak(utterance);
  }, [audioEnabled]);

  const runCommand = useCallback(async (key: string, command: () => Promise<unknown>, onSuccess?: () => void) => {
    if (busyKey) return;
    setBusyKey(key);
    setError(null);
    try {
      const result = await command();
      onSuccess?.();
      if (result && typeof result === "object" && "token_number" in result) {
        const token = Number((result as { token_number: number }).token_number);
        const entry = entries.find((e) => e.token_number === token);
        if (entry) announce(entry);
      }
      if (selectedQueueId != null) await loadEntries(selectedQueueId);
    } catch (err) {
      setError(errorFromUnknown(err));
    } finally {
      setBusyKey(null);
    }
  }, [announce, busyKey, entries, loadEntries, selectedQueueId]);

  const callNext = () => {
    if (selectedQueueId == null) return;
    void runCommand("call-next", () => opdQueueApi.callNext(selectedQueueId));
  };

  const callSpecific = () => {
    if (!specificEntry || selectedQueueId == null) return;
    if (reasonCode === "OTHER" && !reasonNote.trim()) {
      setError({ message: "A reason note is required for an out-of-sequence call using OTHER." });
      return;
    }
    const reason: OPDQueueReason = { reason_code: reasonCode, reason_note: reasonNote.trim() || undefined };
    void runCommand(`call-${specificEntry.id}`, () => opdQueueApi.callSpecific(selectedQueueId, specificEntry.id, reason), () => {
      setSpecificEntry(null);
      setReasonNote("");
    });
  };

  const act = (key: string, command: () => Promise<unknown>) => void runCommand(key, command);

  if (loading) {
    return <div className="flex h-full items-center justify-center bg-slate-950 text-slate-300">Loading OPD queue…</div>;
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-slate-950 text-slate-100">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 bg-slate-900 px-5 py-4">
        <div>
          <div className="flex items-center gap-2">
            <Megaphone className="h-5 w-5 text-sky-400" />
            <h1 className="text-base font-bold">OPD Command Center</h1>
            <Badge className="border border-emerald-800 bg-emerald-950 text-emerald-300">BACKEND LIVE</Badge>
          </div>
          <p className="mt-1 text-xs text-slate-400">Database-backed queue state. Refreshing the snapshot does not create queue transitions.</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" className="text-xs" onClick={() => setAudioEnabled((v) => !v)}>
            {audioEnabled ? <Volume2 size={14} /> : <VolumeX size={14} />} {audioEnabled ? "Audio ON" : "Muted"}
          </Button>
          <Button variant="outline" className="text-xs" onClick={() => void loadQueues(true)} disabled={refreshing}>
            <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} /> Refresh
          </Button>
        </div>
      </header>

      {error && (
        <div className="mx-5 mt-4 flex items-start gap-3 rounded-lg border border-rose-900 bg-rose-950/60 p-3 text-sm text-rose-200">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div><div className="font-semibold">Queue command failed{error.status ? ` (${error.status})` : ""}</div><div className="text-xs opacity-90">{error.message}</div></div>
          <button className="ml-auto text-xs underline" onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-hidden p-5 lg:grid-cols-[280px_1fr]">
        <Card className="min-h-0 overflow-auto border-slate-800 bg-slate-900 p-3">
          <div className="mb-3 flex items-center justify-between"><span className="text-xs font-bold uppercase tracking-wider text-slate-400">Doctor Queues</span><span className="text-xs text-slate-500">{queues.length}</span></div>
          <div className="space-y-2">
            {queues.map((queue) => (
              <button key={queue.id} onClick={() => setSelectedQueueId(queue.id)} className={`w-full rounded-lg border p-3 text-left transition ${selectedQueueId === queue.id ? "border-sky-700 bg-sky-950/50" : "border-slate-800 bg-slate-950 hover:border-slate-700"}`}>
                <div className="flex items-center justify-between"><span className="font-semibold">Doctor #{queue.doctor_id}</span><span className="text-[10px] uppercase text-slate-500">{queue.status}</span></div>
                <div className="mt-1 text-xs text-slate-400">Department #{queue.department_id}{queue.room_label ? ` · ${queue.room_label}` : ""}</div>
                <div className="mt-2 text-[10px] text-slate-500">Queue version {queue.version}</div>
              </button>
            ))}
            {!queues.length && <div className="rounded-lg border border-dashed border-slate-800 p-5 text-center text-xs text-slate-500">No OPD queues for today.</div>}
          </div>
        </Card>

        <section className="min-h-0 overflow-auto">
          {selectedQueue ? (
            <>
              <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
                <Metric icon={<Clock3 size={16} />} label="Waiting" value={waiting.length} />
                <Metric icon={<UserRound size={16} />} label="Active" value={active ? 1 : 0} />
                <Metric icon={<CheckCircle2 size={16} />} label="Completed" value={completed} />
                <Metric icon={<span className="text-sky-400">#</span>} label="Announced" value={announcedToken ?? "—"} />
              </div>

              <Card className="mb-4 border-slate-800 bg-slate-900 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div><div className="text-xs uppercase tracking-wider text-slate-500">Selected queue</div><div className="text-lg font-bold">Doctor #{selectedQueue.doctor_id} · Department #{selectedQueue.department_id}</div><div className="text-xs text-slate-400">{selectedQueue.room_label || "Room not assigned"}</div></div>
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={callNext} disabled={!!busyKey || !!active || !waiting.length} className="text-xs"><Megaphone size={14} /> Call Next</Button>
                    {active && active.state === "CALLED" && <Button variant="outline" className="text-xs" disabled={!!busyKey} onClick={() => act(`repeat-${active.id}`, () => opdQueueApi.repeatCall(selectedQueue.id, active.id))}>Repeat Call</Button>}
                  </div>
                </div>
              </Card>

              <Card className="overflow-hidden border-slate-800 bg-slate-900">
                <div className="border-b border-slate-800 px-4 py-3 text-xs font-bold uppercase tracking-wider text-slate-400">Queue Entries</div>
                <div className="divide-y divide-slate-800">
                  {entries.map((entry) => (
                    <div key={entry.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                      <div className="flex h-10 w-14 items-center justify-center rounded-lg bg-slate-950 text-lg font-black text-sky-300">{entry.token_number}</div>
                      <div className="min-w-[150px] flex-1"><div className="font-semibold">Token {entry.token_number}</div><div className="text-[11px] text-slate-500">Position {entry.queue_position} · Priority {entry.priority} · Appointment #{entry.appointment_id}</div></div>
                      <span className={`rounded-full border px-2 py-1 text-[10px] font-bold uppercase ${stateClass(entry.state)}`}>{stateLabel(entry.state)}</span>
                      <div className="flex flex-wrap gap-1.5">
                        {entry.state === "WAITING" && <><Button variant="outline" className="text-[11px]" disabled={!!busyKey} onClick={() => setSpecificEntry(entry)}>Call Specific</Button><Button variant="outline" className="text-[11px]" disabled={!!busyKey} onClick={() => act(`noshow-${entry.id}`, () => opdQueueApi.markNoShow(selectedQueue.id, entry.id, { reason_code: "NO_SHOW" }))}>No Show</Button></>}
                        {entry.state === "CALLED" && <Button variant="outline" className="text-[11px]" disabled={!!busyKey} onClick={() => act(`arrive-${entry.id}`, () => opdQueueApi.markArrived(selectedQueue.id, entry.id))}>Mark Arrived</Button>}
                        {entry.state === "ARRIVED" && <Button variant="outline" className="text-[11px]" disabled={!!busyKey} onClick={() => setError({ message: "Consultation start requires the encounter id. The queue projection will expose it in the next backend projection update." })}>Start Consultation</Button>}
                        {entry.state === "ON_HOLD" && <Button variant="outline" className="text-[11px]" disabled={!!busyKey} onClick={() => act(`release-${entry.id}`, () => opdQueueApi.releaseHold(selectedQueue.id, entry.id))}>Release Hold</Button>}
                      </div>
                    </div>
                  ))}
                  {!entries.length && <div className="p-8 text-center text-sm text-slate-500">No entries in this queue.</div>}
                </div>
              </Card>
            </>
          ) : <div className="flex h-full items-center justify-center text-sm text-slate-500">Select a doctor queue.</div>}
        </section>
      </div>

      {specificEntry && selectedQueue && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <Card className="w-full max-w-lg border-slate-700 bg-slate-900 p-5">
            <h2 className="text-base font-bold">Call Token {specificEntry.token_number} Out of Sequence</h2>
            <p className="mt-1 text-xs text-slate-400">This records an explicit bypass reason. Queue position is not silently rewritten.</p>
            <label className="mt-4 block text-xs font-semibold text-slate-300">Reason</label>
            <select value={reasonCode} onChange={(e) => setReasonCode(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200">
              {reasonOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <label className="mt-3 block text-xs font-semibold text-slate-300">Explanation {reasonCode === "OTHER" ? "(required)" : "(optional)"}</label>
            <textarea value={reasonNote} onChange={(e) => setReasonNote(e.target.value)} rows={3} maxLength={500} className="mt-1 w-full resize-none rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200" />
            <div className="mt-4 flex justify-end gap-2"><Button variant="outline" onClick={() => setSpecificEntry(null)}>Cancel</Button><Button onClick={callSpecific} disabled={!!busyKey}>Call Token</Button></div>
          </Card>
        </div>
      )}
    </div>
  );
};

const Metric: React.FC<{ icon: React.ReactNode; label: string; value: React.ReactNode }> = ({ icon, label, value }) => (
  <Card className="border-slate-800 bg-slate-900 p-3"><div className="flex items-center gap-2 text-xs text-slate-500">{icon}{label}</div><div className="mt-1 text-xl font-bold text-slate-100">{value}</div></Card>
);
