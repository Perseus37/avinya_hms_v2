import React, { useCallback, useEffect, useState } from "react";
import { reconciliationGovernanceApi, ReconciliationAuditExport, ReconciliationEscalationPolicy, ReconciliationGovernanceReport } from "../../api/reconciliationApi";
import { usePermissions } from "../../core/context/PermissionsContext";

const field = "rounded-lg border border-slate-200 px-2 py-1.5 text-xs";
const button = "rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white disabled:opacity-40";

export const ReconciliationGovernancePanel: React.FC = () => {
  const { hasPermission } = usePermissions();
  const canManage = hasPermission("finance.manage_sla_policies");
  const [policy, setPolicy] = useState<ReconciliationEscalationPolicy | null>(null);
  const [draftId, setDraftId] = useState<number | null>(null);
  const [reports, setReports] = useState<ReconciliationGovernanceReport[]>([]);
  const [exports, setExports] = useState<ReconciliationAuditExport[]>([]);
  const [dashboard, setDashboard] = useState<Record<string, unknown> | null>(null);
  const [quality, setQuality] = useState<Record<string, unknown> | null>(null);
  const [targets, setTargets] = useState({ CRITICAL: 0.5, HIGH: 2, MEDIUM: 8, LOW: 24 });
  const [levels, setLevels] = useState([0.5, 2, 8]);
  const [reason, setReason] = useState("");
  const [emailEnabled, setEmailEnabled] = useState(true);
  const [notifyAssignee, setNotifyAssignee] = useState(true);
  const [notifyManager, setNotifyManager] = useState(true);
  const [notifyFinanceManagers, setNotifyFinanceManagers] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const [policies, reportRows, exportRows, dash, closure] = await Promise.all([
        reconciliationGovernanceApi.escalationPolicies(),
        reconciliationGovernanceApi.monthlyReports(),
        reconciliationGovernanceApi.auditExports(),
        reconciliationGovernanceApi.dashboard(),
        reconciliationGovernanceApi.closureQuality(),
      ]);
      const active = policies.items.find((item) => item.status === "PUBLISHED" && !item.effective_to) || null;
      setPolicy(active);
      setReports(reportRows.items);
      setExports(exportRows.items);
      setDashboard(dash);
      setQuality(closure);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load reconciliation governance.");
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const savePolicy = async () => {
    setBusy(true); setError(""); setMessage("");
    try {
      const draft = await reconciliationGovernanceApi.createEscalationPolicy({
        response_targets_hours: targets,
        escalation_levels: levels.map((after_hours) => ({
          after_hours, notify_assignee: notifyAssignee, notify_assigning_manager: notifyManager, notify_finance_managers: notifyFinanceManagers,
        })),
        notification_preferences: { email_enabled: emailEnabled, assignee: notifyAssignee, assigning_manager: notifyManager, finance_managers: notifyFinanceManagers },
        change_reason: reason,
      });
      setDraftId(draft.id);
      setMessage("Escalation policy draft created. Publish it to make it effective.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create policy draft.");
    } finally { setBusy(false); }
  };

  const publishPolicy = async () => {
    if (!draftId) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await reconciliationGovernanceApi.publishEscalationPolicy(draftId);
      setDraftId(null); setReason("");
      setMessage("Escalation policy published.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to publish policy.");
    } finally { setBusy(false); }
  };

  const generateReport = async () => {
    setBusy(true); setError(""); setMessage("");
    try {
      const now = new Date();
      const start = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - 1, 1));
      const end = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 0));
      const iso = (d: Date) => d.toISOString().slice(0, 10);
      await reconciliationGovernanceApi.createMonthlyReport(iso(start), iso(end));
      setMessage("Monthly governance snapshot generated.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to generate report. The period may already exist.");
    } finally { setBusy(false); }
  };

  const overview = (dashboard?.overview || {}) as Record<string, number>;
  const rootCauses = (quality?.root_causes || []) as Array<{ root_cause_code: string; resolved_count: number; reopened_count: number }>;

  return (
    <section className="space-y-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div><h2 className="text-sm font-bold text-slate-900">Reconciliation governance</h2>
          <p className="text-[11px] text-slate-500">Escalation controls, closure quality, monthly reporting and export accountability</p></div>
        <button type="button" className={field} onClick={() => void load()}>Refresh governance</button>
      </div>
      {error && <p role="alert" className="rounded-lg bg-rose-50 p-2 text-xs text-rose-700">{error}</p>}
      {message && <p role="status" className="rounded-lg bg-emerald-50 p-2 text-xs text-emerald-700">{message}</p>}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ["Open cases", overview.open_cases ?? 0], ["SLA breached", overview.sla_breached_open ?? 0],
          ["Unassigned", overview.unassigned_open ?? 0], ["Reopened", overview.reopened_cases ?? 0],
        ].map(([label, value]) => <div key={label} className="rounded-lg border border-slate-200 bg-white p-3">
          <div className="text-[10px] font-semibold uppercase text-slate-500">{label}</div>
          <div className="mt-1 text-xl font-bold tabular-nums">{Number(value).toLocaleString("en-IN")}</div>
        </div>)}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <h3 className="text-xs font-bold">Escalation policy</h3>
          <p className="mt-1 text-[11px] text-slate-500">{policy ? `Published version ${policy.version}` : "No published escalation policy; baseline targets remain active."}</p>
          {policy && <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
            {Object.entries(policy.response_targets_hours).map(([key, value]) => <div key={key} className="flex justify-between rounded bg-slate-50 px-2 py-1"><span>{key}</span><b>{value}h</b></div>)}
          </div>}
          {canManage && <div className="mt-3 space-y-2 border-t border-slate-100 pt-3">
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(targets).map(([key, value]) => <label key={key} className="text-[10px] text-slate-600">{key} response hours
                <input className={field + " mt-1 w-full"} type="number" min="0.1" max="8760" step="0.1" value={value}
                  onChange={(e) => setTargets((old) => ({ ...old, [key]: Number(e.target.value) }))} /></label>)}
            </div>
            <label className="block text-[10px] text-slate-600">Escalation levels (hours after assignment, comma-separated)
              <input className={field + " mt-1 w-full"} value={levels.join(", ")} onChange={(e) => setLevels(e.target.value.split(",").map(Number).filter((v) => Number.isFinite(v) && v > 0))} />
            </label>
            <div className="flex flex-wrap gap-x-4 gap-y-2 text-[10px] text-slate-600">
              <label className="flex items-center gap-1"><input type="checkbox" checked={emailEnabled} onChange={(e) => setEmailEnabled(e.target.checked)} /> Email enabled</label>
              <label className="flex items-center gap-1"><input type="checkbox" checked={notifyAssignee} onChange={(e) => setNotifyAssignee(e.target.checked)} /> Assignee</label>
              <label className="flex items-center gap-1"><input type="checkbox" checked={notifyManager} onChange={(e) => setNotifyManager(e.target.checked)} /> Assigning manager</label>
              <label className="flex items-center gap-1"><input type="checkbox" checked={notifyFinanceManagers} onChange={(e) => setNotifyFinanceManagers(e.target.checked)} /> Finance Managers</label>
            </div>
            <textarea className={field + " w-full"} rows={2} minLength={10} maxLength={1000} placeholder="Reason for policy change (minimum 10 characters)" value={reason} onChange={(e) => setReason(e.target.value)} />
            <div className="flex flex-wrap gap-2">
              <button type="button" className={button} disabled={busy || reason.trim().length < 10 || !levels.length} onClick={() => void savePolicy()}>Create policy draft</button>
              {draftId && <button type="button" className={button} disabled={busy} onClick={() => void publishPolicy()}>Publish draft #{draftId}</button>}
            </div>
          </div>}
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <h3 className="text-xs font-bold">Closure quality and recurring root causes</h3>
          <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
            <div className="rounded bg-slate-50 p-2"><span className="text-slate-500">Resolved</span><div className="font-bold">{Number(quality?.resolved_count || 0).toLocaleString("en-IN")}</div></div>
            <div className="rounded bg-slate-50 p-2"><span className="text-slate-500">Reopen rate</span><div className="font-bold">{Number(quality?.reopen_rate_percent || 0).toFixed(1)}%</div></div>
            <div className="rounded bg-slate-50 p-2"><span className="text-slate-500">Avg resolution</span><div className="font-bold">{quality?.average_resolution_hours == null ? "—" : Number(quality.average_resolution_hours).toFixed(1) + "h"}</div></div>
            <div className="rounded bg-slate-50 p-2"><span className="text-slate-500">Review approved</span><div className="font-bold">{Number((quality?.independent_review as Record<string, number> | undefined)?.approved || 0)}</div></div>
          </div>
          <div className="mt-3 space-y-1">{rootCauses.slice(0, 6).map((item) => <div key={item.root_cause_code} className="flex justify-between gap-2 border-b border-slate-100 py-1 text-[11px]"><span>{item.root_cause_code}</span><span className="text-slate-500">{item.resolved_count} resolved · {item.reopened_count} reopened</span></div>)}</div>
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <div className="flex items-center justify-between gap-2"><h3 className="text-xs font-bold">Monthly governance reports</h3>
            {canManage && <button type="button" className={button} disabled={busy} onClick={() => void generateReport()}>Generate previous month</button>}</div>
          <div className="mt-2 space-y-2">{reports.length ? reports.map((report) => <div key={report.id} className="flex justify-between border-b border-slate-100 py-1 text-[11px]"><span>{report.period_start} – {report.period_end}</span><span>{String(report.snapshot.case_count ?? 0)} cases · #{report.id}</span></div>) : <p className="text-[11px] text-slate-400">No monthly snapshots generated yet.</p>}</div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <h3 className="text-xs font-bold">Audit export register</h3>
          <div className="mt-2 space-y-2">{exports.length ? exports.slice(0, 8).map((item) => <div key={item.id} className="border-b border-slate-100 py-1 text-[11px]">
            <div className="flex justify-between"><b>#{item.id} · {item.export_type}</b><span>{item.status}</span></div>
            <div className="text-slate-500">{new Date(item.requested_at).toLocaleString()} · {item.actor_email} · {item.file_size_bytes ?? 0} bytes</div>
            {item.file_sha256 && <div className="break-all font-mono text-[9px] text-slate-400">{item.file_sha256}</div>}
          </div>) : <p className="text-[11px] text-slate-400">No audit exports recorded.</p>}</div>
        </div>
      </div>
    </section>
  );
};
