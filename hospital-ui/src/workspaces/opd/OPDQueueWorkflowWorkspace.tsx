import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, Megaphone, RefreshCw, UserRound, Volume2, VolumeX } from "lucide-react";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { opdQueueApi, OPDQueueEntry, OPDQueueReason, OPDQueueSummary } from "../../api/opdQueueApi";

const reasons = [
  ["CLINICAL_PRIORITY", "Clinical priority / emergency"],
  ["DOCTOR_REQUESTED", "Doctor requested"],
  ["SPECIAL_ASSISTANCE", "Special assistance"],
  ["SCHEDULED_PROCEDURE", "Scheduled procedure / review"],
  ["ADMINISTRATIVE_CORRECTION", "Administrative correction"],
  ["OTHER", "Other"],
] as const;

const stateClass = (state: OPDQueueEntry["state"]) => ({
  CALLED: "bg-sky-950 text-sky-300 border-sky-800",
  ARRIVED: "bg-amber-950 text-amber-300 border-amber-800",
  IN_CONSULTATION: "bg-violet-950 text-violet-300 border-violet-800",
  ON_HOLD: "bg-orange-950 text-orange-300 border-orange-800",
  COMPLETED: "bg-emerald-950 text-emerald-300 border-emerald-800",
  NO_SHOW: "bg-rose-950 text-rose-300 border-rose-800",
}[state] || "bg-slate-900 text-slate-300 border-slate-700");

export const OPDQueueWorkflowWorkspace: React.FC = () => {
  const [queues, setQueues] = useState<OPDQueueSummary[]>([]);
  const [queueId, setQueueId] = useState<number | null>(null);
  const [entries, setEntries] = useState<OPDQueueEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [audio, setAudio] = useState(true);
  const [specific, setSpecific] = useState<OPDQueueEntry | null>(null);
  const [reasonCode, setReasonCode] = useState("CLINICAL_PRIORITY");
  const [reasonNote, setReasonNote] = useState("");

  const loadQueues = useCallback(async () => {
    try {
      const data = await opdQueueApi.listQueues();
      setQueues(data);
      setQueueId(current => current && data.some(q => q.id === current) ? current : data[0]?.id ?? null);
      setError(null);
    } catch (e) { setError(e instanceof Error ? e.message : "Unable to load OPD queues."); }
    finally { setLoading(false); }
  }, []);

  const loadEntries = useCallback(async (id: number) => {
    try { setEntries(await opdQueueApi.listEntries(id)); }
    catch (e) { setError(e instanceof Error ? e.message : "Unable to load queue entries."); }
  }, []);

  useEffect(() => { void loadQueues(); }, [loadQueues]);
  useEffect(() => {
    if (queueId == null) { setEntries([]); return; }
    void loadEntries(queueId);
    const timer = window.setInterval(() => void loadEntries(queueId), 4000);
    return () => window.clearInterval(timer);
  }, [queueId, loadEntries]);

  const selected = queues.find(q => q.id === queueId) ?? null;
  const waiting = useMemo(() => entries.filter(e => e.state === "WAITING"), [entries]);
  const active = useMemo(() => entries.find(e => ["CALLED", "ARRIVED", "IN_CONSULTATION"].includes(e.state)), [entries]);
  const completed = entries.filter(e => e.state === "COMPLETED").length;

  const announce = (token: number) => {
    if (!audio || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(`Token number ${token}. Please proceed to the consultation room.`);
    u.lang = "en-IN"; u.rate = 0.9; window.speechSynthesis.speak(u);
  };

  const command = async (key: string, fn: () => Promise<unknown>) => {
    if (busy || queueId == null) return;
    setBusy(key); setError(null);
    try {
      const result = await fn();
      if (result && typeof result === "object" && "token_number" in result) announce(Number((result as { token_number: number }).token_number));
      await loadEntries(queueId);
    } catch (e) { setError(e instanceof Error ? e.message : "OPD command failed."); }
    finally { setBusy(null); }
  };

  const callSpecific = () => {
    if (!specific || queueId == null) return;
    if (reasonCode === "OTHER" && !reasonNote.trim()) { setError("A reason note is required for OTHER."); return; }
    const reason: OPDQueueReason = { reason_code: reasonCode, reason_note: reasonNote.trim() || undefined };
    void command(`call-${specific.id}`, async () => {
      const result = await opdQueueApi.callSpecific(queueId, specific.id, reason);
      setSpecific(null); setReasonNote(""); return result;
    });
  };

  if (loading) return <div className="flex h-full items-center justify-center bg-slate-950 text-slate-300">Loading OPD workflow…</div>;

  return <div className="flex h-full flex-col overflow-hidden bg-slate-950 text-slate-100">
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 bg-slate-900 px-5 py-4">
      <div><div className="flex items-center gap-2"><Megaphone className="h-5 w-5 text-sky-400"/><h1 className="font-bold">OPD Command Center</h1><Badge className="border border-emerald-800 bg-emerald-950 text-emerald-300">LIVE</Badge></div><p className="mt-1 text-xs text-slate-400">Authoritative database queue: reception and doctor actions share the same lifecycle.</p></div>
      <div className="flex gap-2"><Button variant="outline" className="text-xs" onClick={() => setAudio(v => !v)}>{audio ? <Volume2 size={14}/> : <VolumeX size={14}/>} {audio ? "Audio ON" : "Muted"}</Button><Button variant="outline" className="text-xs" onClick={() => void loadQueues()}><RefreshCw size={14}/> Refresh</Button></div>
    </header>
    {error && <div className="mx-5 mt-4 flex gap-3 rounded-lg border border-rose-900 bg-rose-950/60 p-3 text-sm text-rose-200"><AlertTriangle size={16}/><span>{error}</span><button className="ml-auto underline" onClick={() => setError(null)}>Dismiss</button></div>}
    <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-hidden p-5 lg:grid-cols-[280px_1fr]">
      <Card className="min-h-0 overflow-auto border-slate-800 bg-slate-900 p-3"><div className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-400">Doctor Queues</div>{queues.map(q => <button key={q.id} onClick={() => setQueueId(q.id)} className={`mb-2 w-full rounded-lg border p-3 text-left ${queueId === q.id ? "border-sky-700 bg-sky-950/50" : "border-slate-800 bg-slate-950"}`}><div className="font-semibold">Doctor #{q.doctor_id}</div><div className="text-xs text-slate-400">Department #{q.department_id} · {q.room_label || "Room not assigned"}</div><div className="mt-1 text-[10px] text-slate-500">{q.status} · v{q.version}</div></button>)}{!queues.length && <div className="p-4 text-center text-xs text-slate-500">No queues today.</div>}</Card>
      <section className="min-h-0 overflow-auto">{selected ? <>
        <div className="mb-4 grid grid-cols-3 gap-3"><Metric icon={<Clock3 size={16}/>} label="Waiting" value={waiting.length}/><Metric icon={<UserRound size={16}/>} label="Active" value={active ? 1 : 0}/><Metric icon={<CheckCircle2 size={16}/>} label="Completed" value={completed}/></div>
        <Card className="mb-4 border-slate-800 bg-slate-900 p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><div className="text-xs text-slate-500">SELECTED QUEUE</div><div className="font-bold">Doctor #{selected.doctor_id} · Department #{selected.department_id}</div><div className="text-xs text-slate-400">{selected.room_label || "Room not assigned"}</div></div><Button disabled={!!busy || !!active || !waiting.length} onClick={() => void command("call-next", () => opdQueueApi.callNext(selected.id))} className="text-xs"><Megaphone size={14}/> Call Next</Button></div></Card>
        <Card className="overflow-hidden border-slate-800 bg-slate-900"><div className="border-b border-slate-800 px-4 py-3 text-xs font-bold uppercase text-slate-400">Queue Entries</div>{entries.map(e => <div key={e.id} className="flex flex-wrap items-center gap-3 border-b border-slate-800 px-4 py-3"><div className="flex h-10 w-14 items-center justify-center rounded-lg bg-slate-950 text-lg font-black text-sky-300">{e.token_number}</div><div className="min-w-[180px] flex-1"><div className="font-semibold">Token {e.token_number}</div><div className="text-[11px] text-slate-500">Position {e.queue_position} · Priority {e.priority} · Appointment #{e.appointment_id}</div></div><span className={`rounded-full border px-2 py-1 text-[10px] font-bold uppercase ${stateClass(e.state)}`}>{e.state.replaceAll("_", " ")}</span><div className="flex flex-wrap gap-1.5">
          {e.state === "WAITING" && <><Button variant="outline" className="text-[11px]" disabled={!!busy} onClick={() => setSpecific(e)}>Call Specific</Button><Button variant="outline" className="text-[11px]" disabled={!!busy} onClick={() => void command(`noshow-${e.id}`, () => opdQueueApi.markNoShow(selected.id, e.id, { reason_code: "NO_SHOW" }))}>No Show</Button></>}
          {e.state === "CALLED" && <><Button variant="outline" className="text-[11px]" disabled={!!busy} onClick={() => void command(`repeat-${e.id}`, () => opdQueueApi.repeatCall(selected.id, e.id))}>Repeat</Button><Button variant="outline" className="text-[11px]" disabled={!!busy} onClick={() => void command(`arrive-${e.id}`, () => opdQueueApi.markArrived(selected.id, e.id))}>Arrived</Button></>}
          {e.state === "ARRIVED" && <Button variant="outline" className="text-[11px]" disabled={!!busy} onClick={() => void command(`start-${e.id}`, () => opdQueueApi.startConsultation(selected.id, e.id))}>Start Consultation</Button>}
          {e.state === "IN_CONSULTATION" && <Button variant="outline" className="text-[11px]" disabled={!!busy} onClick={() => void command(`complete-${e.id}`, () => opdQueueApi.completeConsultation(selected.id, e.id, { reason_code: "CONSULTATION_COMPLETED" }))}>Complete Consultation</Button>}
          {e.state === "ON_HOLD" && <Button variant="outline" className="text-[11px]" disabled={!!busy} onClick={() => void command(`release-${e.id}`, () => opdQueueApi.releaseHold(selected.id, e.id))}>Release Hold</Button>}
        </div></div>)}{!entries.length && <div className="p-8 text-center text-sm text-slate-500">No entries in this queue.</div>}</Card>
      </> : <div className="flex h-full items-center justify-center text-sm text-slate-500">No OPD queue selected.</div>}</section>
    </div>
    {specific && selected && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"><Card className="w-full max-w-lg border-slate-700 bg-slate-900 p-5"><h2 className="font-bold">Call Token {specific.token_number} Out of Sequence</h2><p className="mt-1 text-xs text-slate-400">The bypass is audited and does not rewrite queue position.</p><label className="mt-4 block text-xs font-semibold">Reason</label><select value={reasonCode} onChange={e => setReasonCode(e.target.value)} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-sm">{reasons.map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select><textarea value={reasonNote} onChange={e => setReasonNote(e.target.value)} placeholder="Optional explanation" className="mt-3 h-24 w-full rounded-lg border border-slate-700 bg-slate-950 p-2 text-sm"/><div className="mt-4 flex justify-end gap-2"><Button variant="outline" onClick={() => setSpecific(null)}>Cancel</Button><Button disabled={!!busy} onClick={callSpecific}>Call Patient</Button></div></Card></div>}
  </div>;
};

const Metric: React.FC<{ icon: React.ReactNode; label: string; value: React.ReactNode }> = ({ icon, label, value }) => <Card className="border-slate-800 bg-slate-900 p-3"><div className="flex items-center gap-2 text-xs text-slate-400">{icon}{label}</div><div className="mt-1 text-2xl font-black">{value}</div></Card>;
