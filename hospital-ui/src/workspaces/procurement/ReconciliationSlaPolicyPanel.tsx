import React, { useCallback, useEffect, useState } from "react";
import { ChevronDown, Clock3, LockKeyhole, RefreshCw, ShieldCheck } from "lucide-react";
import { reconciliationSlaPolicyApi, ReconciliationSlaPolicyDirectory, ReconciliationSeverity } from "../../api/reconciliationApi";
import { usePermissions } from "../../core/context/PermissionsContext";

const severities: ReconciliationSeverity[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];

export const ReconciliationSlaPolicyPanel: React.FC = () => {
  const { hasPermission } = usePermissions();
  const canRead = hasPermission("finance.view_reconciliation");
  const canManage = hasPermission("finance.manage_sla_policies");
  const [directory, setDirectory] = useState<ReconciliationSlaPolicyDirectory | null>(null);
  const [targets, setTargets] = useState<Record<ReconciliationSeverity, number>>({
    CRITICAL: 4, HIGH: 24, MEDIUM: 72, LOW: 168,
  });
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    if (!canRead) return;
    const result = await reconciliationSlaPolicyApi.list();
    setDirectory(result);
    if (result.active_policy_id === null) setTargets(result.baseline_fallback);
    else {
      const active = result.items.find((item) => item.id === result.active_policy_id);
      if (active) setTargets(active.severity_targets_hours);
    }
  }, [canRead]);

  useEffect(() => { void load().catch((err) => setError(err instanceof Error ? err.message : "Unable to load SLA policy versions.")); }, [load]);
  if (!canRead) return null;

  const createDraft = async () => {
    if (reason.trim().length < 10) {
      setError("Enter a change reason of at least 10 characters.");
      return;
    }
    if (severities.some((severity) => !Number.isInteger(targets[severity]) || targets[severity] < 1 || targets[severity] > 8760)) {
      setError("Each severity target must be a whole number between 1 and 8760 hours.");
      return;
    }
    setBusy(true); setError(""); setMessage("");
    try {
      const created = await reconciliationSlaPolicyApi.createDraft({
        severity_targets_hours: targets,
        change_reason: reason.trim(),
      });
      setReason("");
      await load();
      setMessage(`Draft policy version ${created.version} created. Review it below and publish when approved.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create SLA policy draft.");
    } finally { setBusy(false); }
  };

  const publish = async (id: number) => {
    setBusy(true); setError(""); setMessage("");
    try {
      const published = await reconciliationSlaPolicyApi.publish(id);
      await load();
      setMessage(`Policy version ${published.version} is now effective. Existing investigations retain their captured SLA targets.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to publish SLA policy.");
    } finally { setBusy(false); }
  };

  return (
    <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-bold text-slate-900"><Clock3 size={15} /> Reconciliation SLA policy</h2>
          <p className="mt-0.5 text-[11px] text-slate-500">Tenant-wide, versioned severity targets. Published versions apply to new investigations only.</p>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-slate-500">
          <ShieldCheck size={13} />
          {directory?.active_policy_version ? `Active version ${directory.active_policy_version}` : "Baseline defaults active"}
          <button type="button" onClick={() => void load()} disabled={busy} aria-label="Refresh SLA policies" className="rounded-md border border-slate-200 p-1.5 hover:bg-slate-50 disabled:opacity-50"><RefreshCw size={12} /></button>
        </div>
      </div>
      <div className="space-y-3 p-4">
        {error && <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</p>}
        {message && <p role="status" className="rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-700">{message}</p>}
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {severities.map((severity) => (
            <label key={severity} className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              {severity} · hours
              <input type="number" min={1} max={8760} step={1} value={targets[severity]} onChange={(event) => setTargets((current) => ({ ...current, [severity]: Number(event.target.value) }))} disabled={!canManage || busy} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-800 disabled:bg-slate-50" />
            </label>
          ))}
        </div>
        {canManage ? (
          <div className="grid gap-2 md:grid-cols-[1fr_auto]">
            <input value={reason} onChange={(event) => setReason(event.target.value)} maxLength={1000} placeholder="Change reason and governance approval reference (minimum 10 characters)" disabled={busy} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs" />
            <button type="button" onClick={() => void createDraft()} disabled={busy || reason.trim().length < 10} className="rounded-lg bg-slate-900 px-3 py-2 text-xs font-semibold text-white disabled:opacity-40">Create draft version</button>
          </div>
        ) : (
          <p className="flex items-center gap-1.5 text-[10px] text-slate-500"><LockKeyhole size={12} /> Read-only policy view. A user with SLA policy management permission is required to create or publish versions.</p>
        )}
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wide text-slate-500"><ChevronDown size={12} /> Policy version history</div>
          {directory?.items.length ? directory.items.map((policy) => (
            <div key={policy.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-100 px-3 py-2">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-slate-800">
                  Version {policy.version}
                  <span className={`rounded-full px-2 py-0.5 text-[9px] ${policy.status === "PUBLISHED" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>{policy.status}</span>
                  {directory.active_policy_id === policy.id && <span className="text-[9px] font-bold text-blue-700">CURRENT</span>}
                </div>
                <p className="mt-1 truncate text-[10px] text-slate-500">{policy.change_reason}</p>
                <p className="mt-0.5 text-[9px] text-slate-400">{severities.map((severity) => `${severity}: ${policy.severity_targets_hours[severity]}h`).join(" · ")}</p>
              </div>
              {canManage && policy.status === "DRAFT" && <button type="button" onClick={() => void publish(policy.id)} disabled={busy} className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-[10px] font-semibold text-blue-700 disabled:opacity-40">Publish version</button>}
            </div>
          )) : <p className="text-[10px] text-slate-400">No custom versions have been published. The baseline defaults remain active.</p>}
        </div>
      </div>
    </section>
  );
};
