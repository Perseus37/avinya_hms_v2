import React, { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, RefreshCw, ClipboardList } from "lucide-react";
import { reconciliationApi, MyReconciliationAssignment, ReconciliationSeverity } from "../../api/reconciliationApi";

const severityClass: Record<ReconciliationSeverity, string> = {
  CRITICAL: "border-rose-200 bg-rose-50 text-rose-800",
  HIGH: "border-amber-200 bg-amber-50 text-amber-800",
  MEDIUM: "border-blue-200 bg-blue-50 text-blue-800",
  LOW: "border-slate-200 bg-slate-50 text-slate-700",
};

const dateTime = (value: string) => new Date(value).toLocaleString("en-IN", {
  dateStyle: "medium", timeStyle: "short",
});

export const MyAssignedInvestigationsWorkspace: React.FC = () => {
  const [items, setItems] = useState<MyReconciliationAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [reasonById, setReasonById] = useState<Record<number, string>>({});
  const [busyId, setBusyId] = useState<number | null>(null);
  const [notice, setNotice] = useState("");

  const load = useCallback(async (background = false) => {
    if (background) setRefreshing(true); else setLoading(true);
    setError("");
    try {
      const result = await reconciliationApi.getMyAssignments(250);
      setItems(result.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load your assigned investigations.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const respond = async (item: MyReconciliationAssignment, decision: "ACCEPT" | "REJECT") => {
    const reason = (reasonById[item.id] || "").trim();
    if (decision === "REJECT" && reason.length < 10) {
      setError("A rejection reason of at least 10 characters is required.");
      return;
    }
    setBusyId(item.id); setError(""); setNotice("");
    try {
      await reconciliationApi.respondToAssignment(item.id, { decision, reason: reason || undefined });
      setNotice(decision === "ACCEPT"
        ? `Investigation #${item.id} accepted.`
        : `Investigation #${item.id} rejected and returned to the manager's unassigned queue.`);
      setReasonById((current) => ({ ...current, [item.id]: "" }));
      await load(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to record your assignment response.");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col overflow-hidden">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-6 py-4">
        <div>
          <div className="flex items-center gap-2 text-lg font-bold text-slate-900"><ClipboardList size={20} /> My Assigned Investigations</div>
          <p className="mt-1 text-xs text-slate-500">Only active reconciliation cases assigned to your signed-in branch account are shown.</p>
        </div>
        <button type="button" onClick={() => void load(true)} disabled={refreshing || loading} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50">
          <RefreshCw size={14} className={refreshing ? "animate-spin" : ""} /> Refresh
        </button>
      </header>

      <div className="flex-1 space-y-4 overflow-y-auto p-6">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-slate-200 bg-white p-4"><div className="text-[11px] font-semibold uppercase text-slate-500">Active assignments</div><div className="mt-2 text-2xl font-bold tabular-nums text-slate-900">{items.length}</div></div>
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-4"><div className="text-[11px] font-semibold uppercase text-amber-700">Awaiting acknowledgement</div><div className="mt-2 text-2xl font-bold tabular-nums text-amber-900">{items.filter((item) => item.acknowledgement_status === "PENDING").length}</div></div>
          <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4"><div className="text-[11px] font-semibold uppercase text-emerald-700">Accepted</div><div className="mt-2 text-2xl font-bold tabular-nums text-emerald-900">{items.filter((item) => item.acknowledgement_status === "ACCEPTED").length}</div></div>
        </div>

        {error && <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-800">{error}</div>}
        {notice && <div role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs text-emerald-800">{notice}</div>}

        {loading ? (
          <div className="rounded-xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-500">Loading your assignments…</div>
        ) : items.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center">
            <CheckCircle2 size={28} className="mx-auto text-emerald-500" />
            <h2 className="mt-3 text-sm font-bold text-slate-800">No active assignments</h2>
            <p className="mt-1 text-xs text-slate-500">New investigations assigned to your account will appear here.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((item) => {
              const pending = item.acknowledgement_status === "PENDING";
              return (
                <article key={item.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-bold text-slate-900">Investigation #{item.id}</span>
                        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold ${severityClass[item.severity]}`}>{item.severity}</span>
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-700">{item.status.replaceAll("_", " ")}</span>
                        {pending && <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-800"><AlertTriangle size={11} /> Acknowledgement needed</span>}
                        {!pending && item.acknowledgement_status === "ACCEPTED" && <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800"><CheckCircle2 size={11} /> Accepted</span>}
                      </div>
                      <p className="mt-2 text-xs font-semibold text-slate-700">{item.exception_type.replaceAll("_", " ")}</p>
                      <p className="mt-1 text-xs leading-relaxed text-slate-600">{item.summary}</p>
                      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[10px] text-slate-500">
                        <span>Reference: {item.reference_type.replaceAll("_", " ")}</span>
                        <span>Assigned: {dateTime(item.assigned_at)}</span>
                        <span>Detected: {dateTime(item.first_detected_at)}</span>
                        <span className="inline-flex items-center gap-1"><Clock3 size={11} /> Response target: {item.response_target_hours}h</span>
                        {!item.source_present && <span className="font-semibold text-amber-700">Not present in latest detection scan</span>}
                      </div>
                    </div>
                  </div>
                  {pending && (
                    <div className="mt-4 border-t border-slate-100 pt-3">
                      <label className="mb-1 block text-[10px] font-semibold text-slate-600" htmlFor={`assignment-reason-${item.id}`}>Rejection reason (required to reject)</label>
                      <textarea id={`assignment-reason-${item.id}`} value={reasonById[item.id] || ""} onChange={(event) => setReasonById((current) => ({ ...current, [item.id]: event.target.value }))} rows={2} maxLength={1000} placeholder="Explain why this investigation should be reassigned…" disabled={busyId === item.id} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100" />
                      <div className="mt-2 flex flex-wrap justify-end gap-2">
                        <button type="button" onClick={() => void respond(item, "REJECT")} disabled={busyId === item.id || (reasonById[item.id] || "").trim().length < 10} className="rounded-lg border border-rose-200 px-3 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-40">Reject assignment</button>
                        <button type="button" onClick={() => void respond(item, "ACCEPT")} disabled={busyId === item.id} className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50">{busyId === item.id ? "Saving…" : "Accept assignment"}</button>
                      </div>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default MyAssignedInvestigationsWorkspace;
