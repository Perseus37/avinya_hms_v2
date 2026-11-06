import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CalendarDays,
  CheckCircle2,
  Clock3,
  Download,
  Filter,
  RefreshCw,
  Search,
  ShieldAlert,
  Users,
  Wallet,
} from "lucide-react";
import {
  reconciliationApi,
  ReconciliationDashboard,
  ReconciliationException,
  ReconciliationFilters,
  ReconciliationQueue,
  ReconciliationSeverity,
  ReconciliationStatus,
} from "../../api/reconciliationApi";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";

const severityOptions: ReconciliationSeverity[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
const statusOptions: ReconciliationStatus[] = ["OPEN", "IN_REVIEW", "RESOLVED", "DISMISSED"];

const severityVariant = (severity: ReconciliationSeverity): "danger" | "warning" | "info" | "neutral" => {
  if (severity === "CRITICAL") return "danger";
  if (severity === "HIGH") return "warning";
  if (severity === "MEDIUM") return "info";
  return "neutral";
};

const statusVariant = (status: ReconciliationStatus): "danger" | "warning" | "success" | "neutral" => {
  if (status === "OPEN") return "danger";
  if (status === "IN_REVIEW") return "warning";
  if (status === "RESOLVED") return "success";
  return "neutral";
};

const money = (paise: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format((paise || 0) / 100);

const number = (value: number) => new Intl.NumberFormat("en-IN").format(value || 0);
const hours = (value: number | null) => value === null ? "—" : value < 24 ? `${value.toFixed(1)}h` : `${(value / 24).toFixed(1)}d`;
const titleCase = (value: string) => value.toLowerCase().replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
const localDate = (date: Date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const StatCard: React.FC<{
  label: string;
  value: string;
  detail: string;
  icon: React.ElementType;
  tone?: "normal" | "danger" | "warning" | "success";
}> = ({ label, value, detail, icon: Icon, tone = "normal" }) => {
  const tones = {
    normal: "border-slate-200 bg-white text-slate-800",
    danger: "border-rose-200 bg-rose-50 text-rose-800",
    warning: "border-amber-200 bg-amber-50 text-amber-800",
    success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  };
  return (
    <div className={`rounded-xl border p-4 shadow-sm ${tones[tone]}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide opacity-70">{label}</span>
        <Icon size={17} className="opacity-70" />
      </div>
      <div className="mt-3 text-2xl font-bold tabular-nums">{value}</div>
      <div className="mt-1 text-[11px] opacity-70">{detail}</div>
    </div>
  );
};

const Section: React.FC<{ title: string; description?: string; action?: React.ReactNode; children: React.ReactNode }> = ({
  title, description, action, children,
}) => (
  <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-4 py-3">
      <div>
        <h2 className="text-sm font-bold text-slate-900">{title}</h2>
        {description && <p className="mt-0.5 text-[11px] text-slate-500">{description}</p>}
      </div>
      {action}
    </div>
    <div className="p-4">{children}</div>
  </section>
);

export const ProcurementReconciliationWorkspace: React.FC = () => {
  const today = useMemo(() => new Date(), []);
  const thirtyDaysAgo = useMemo(() => {
    const value = new Date();
    value.setDate(value.getDate() - 30);
    return value;
  }, []);
  const [fromDate, setFromDate] = useState(localDate(thirtyDaysAgo));
  const [toDate, setToDate] = useState(localDate(today));
  const [severity, setSeverity] = useState<ReconciliationSeverity | "">("");
  const [status, setStatus] = useState<ReconciliationStatus | "">("");
  const [assignedToId, setAssignedToId] = useState("");
  const [exceptionType, setExceptionType] = useState("");
  const [dashboard, setDashboard] = useState<ReconciliationDashboard | null>(null);
  const [queue, setQueue] = useState<ReconciliationQueue | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastLoadedAt, setLastLoadedAt] = useState<Date | null>(null);

  const filters = useMemo<ReconciliationFilters>(() => ({
    from_date: fromDate || undefined,
    to_date: toDate || undefined,
    severity: severity || undefined,
    status: status || undefined,
    assigned_to_id: assignedToId ? Number(assignedToId) : undefined,
  }), [fromDate, toDate, severity, status, assignedToId]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [summary, worklist] = await Promise.all([
        reconciliationApi.getDashboard(filters),
        reconciliationApi.getQueue({
          severity: severity || undefined,
          status: status || undefined,
          assigned_to_id: assignedToId ? Number(assignedToId) : undefined,
          exception_type: exceptionType || undefined,
        }),
      ]);
      setDashboard(summary);
      setQueue(worklist);
      setLastLoadedAt(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load procurement reconciliation data.");
    } finally {
      setLoading(false);
    }
  }, [filters, severity, status, assignedToId, exceptionType]);

  useEffect(() => { void load(); }, [load]);

  const exceptionTypes = useMemo(() => Object.keys(dashboard?.by_exception_type || {}).sort(), [dashboard]);
  const maxAging = Math.max(1, ...Object.values(dashboard?.open_aging || {}));
  const trend = dashboard?.daily_trend.slice(-14) || [];
  const maxTrend = Math.max(1, ...trend.flatMap((item) => [item.opened_count, item.resolved_count]));

  const exportQueue = () => {
    if (!queue) return;
    const columns = ["id", "exception_type", "severity", "status", "reference_type", "reference_id", "age_hours", "sla_overdue", "amount_paise", "unmatched_amount_paise", "assigned_to_id", "summary"];
    const escape = (value: unknown) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    const csv = [columns.join(","), ...queue.exceptions.map((row) => columns.map((key) => escape(row[key as keyof ReconciliationException])).join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `reconciliation-exceptions-${localDate(new Date())}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const selectExceptionType = (value: string) => {
    setExceptionType((current) => current === value ? "" : value);
    setStatus("OPEN");
  };

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden bg-[#f5f7fa]">
      <header className="border-b border-slate-200 bg-white px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-blue-700">
              <Wallet size={14} /> Finance operations
            </div>
            <h1 className="mt-1 text-xl font-bold tracking-tight text-slate-900">Procurement reconciliation</h1>
            <p className="mt-1 max-w-2xl text-xs text-slate-500">
              Investigate bank matching exceptions, supplier payment variances, SLA breaches and finance workload.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {lastLoadedAt && <span className="hidden text-[10px] text-slate-400 sm:inline">Updated {lastLoadedAt.toLocaleTimeString()}</span>}
            <Button variant="outline" size="sm" className="border-slate-300 text-slate-700 hover:bg-slate-100 focus:ring-blue-400 focus:ring-offset-white" onClick={() => void load()} disabled={loading}>
              <RefreshCw size={13} className={loading ? "mr-1.5 animate-spin" : "mr-1.5"} /> Reload
            </Button>
            <Button variant="outline" size="sm" className="border-slate-300 text-slate-700 hover:bg-slate-100 focus:ring-blue-400 focus:ring-offset-white" onClick={exportQueue} disabled={!queue?.exceptions.length}>
              <Download size={13} className="mr-1.5" /> Export queue
            </Button>
          </div>
        </div>
      </header>

      <div className="flex-1 space-y-4 overflow-y-auto p-4 md:p-5">
        <div className="rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-[11px] leading-relaxed text-blue-900">
          <div className="flex items-center gap-2 font-semibold"><ShieldAlert size={14} /> Investigation data, not a loss statement</div>
          <p className="mt-1 text-blue-800">
            Bank-side and supplier-payment exceptions are shown separately to avoid double-counting one transfer.
            Possible duplicate-payment candidates are investigation signals only and are excluded from monetary totals.
          </p>
        </div>

        <Section title="Dashboard filters" description="Date filters apply to first detection in UTC. Worklist filters apply to the current exception queue.">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-6">
            <label className="text-[11px] font-semibold text-slate-600">
              From date
              <input type="date" value={fromDate} max={toDate || undefined} onChange={(event) => setFromDate(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-xs text-slate-800 outline-none focus:border-blue-400" />
            </label>
            <label className="text-[11px] font-semibold text-slate-600">
              To date
              <input type="date" value={toDate} min={fromDate || undefined} onChange={(event) => setToDate(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-xs text-slate-800 outline-none focus:border-blue-400" />
            </label>
            <label className="text-[11px] font-semibold text-slate-600">
              Severity
              <select value={severity} onChange={(event) => setSeverity(event.target.value as ReconciliationSeverity | "")} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-xs text-slate-800">
                <option value="">All severities</option>
                {severityOptions.map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <label className="text-[11px] font-semibold text-slate-600">
              Status
              <select value={status} onChange={(event) => setStatus(event.target.value as ReconciliationStatus | "")} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-xs text-slate-800">
                <option value="">All statuses</option>
                {statusOptions.map((item) => <option key={item} value={item}>{titleCase(item)}</option>)}
              </select>
            </label>
            <label className="text-[11px] font-semibold text-slate-600">
              Assignee user ID
              <input type="number" min="1" value={assignedToId} onChange={(event) => setAssignedToId(event.target.value)} placeholder="Any assignee" className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-xs text-slate-800 outline-none focus:border-blue-400" />
            </label>
            <label className="text-[11px] font-semibold text-slate-600">
              Exception category
              <select value={exceptionType} onChange={(event) => setExceptionType(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-xs text-slate-800">
                <option value="">All categories</option>
                {exceptionTypes.map((item) => <option key={item} value={item}>{titleCase(item)}</option>)}
              </select>
            </label>
          </div>
          <div className="mt-3 flex items-center justify-between gap-2 border-t border-slate-100 pt-3">
            <span className="flex items-center gap-1.5 text-[10px] text-slate-400"><Filter size={12} /> Filters load automatically</span>
            <button type="button" onClick={() => { setFromDate(localDate(thirtyDaysAgo)); setToDate(localDate(today)); setSeverity(""); setStatus(""); setAssignedToId(""); setExceptionType(""); }} className="text-[11px] font-semibold text-blue-700 hover:text-blue-900">Reset filters</button>
          </div>
        </Section>

        {error && (
          <div role="alert" className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
            <AlertTriangle size={15} className="mt-0.5 shrink-0" />
            <div><div className="font-semibold">Could not load reconciliation data</div><div className="mt-0.5">{error}</div></div>
          </div>
        )}

        {loading && !dashboard ? (
          <div className="flex min-h-56 items-center justify-center rounded-xl border border-slate-200 bg-white text-xs text-slate-500">
            <RefreshCw size={15} className="mr-2 animate-spin" /> Loading finance dashboard…
          </div>
        ) : dashboard ? (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard label="Open investigations" value={number(dashboard.overview.open_count + dashboard.overview.in_review_count)} detail={`${number(dashboard.overview.in_review_count)} currently in review`} icon={Search} />
              <StatCard label="SLA breached" value={number(dashboard.overview.sla_breached_open_count)} detail="Open cases beyond severity SLA" icon={Clock3} tone={dashboard.overview.sla_breached_open_count ? "danger" : "success"} />
              <StatCard label="Unassigned" value={number(dashboard.overview.unassigned_open_count)} detail="Open investigations without an owner" icon={Users} tone={dashboard.overview.unassigned_open_count ? "warning" : "normal"} />
              <StatCard label="Source missing" value={number(dashboard.overview.source_missing_open_count)} detail="Still open; absent in latest detection" icon={AlertTriangle} tone={dashboard.overview.source_missing_open_count ? "warning" : "normal"} />
            </div>

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
              <Section title="Exception aging" description="Age of currently open and in-review investigations">
                <div className="space-y-3">
                  {[
                    ["Under 4 hours", dashboard.open_aging.under_4_hours || 0],
                    ["4–24 hours", dashboard.open_aging["4_to_24_hours"] || 0],
                    ["1–3 days", dashboard.open_aging["1_to_3_days"] || 0],
                    ["3–7 days", dashboard.open_aging["3_to_7_days"] || 0],
                    ["Over 7 days", dashboard.open_aging.over_7_days || 0],
                  ].map(([label, value]) => (
                    <div key={label as string}>
                      <div className="mb-1 flex justify-between text-[11px]"><span className="text-slate-600">{label}</span><strong className="tabular-nums text-slate-800">{number(value as number)}</strong></div>
                      <div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-blue-500" style={{ width: `${Math.max(0, (Number(value) / maxAging) * 100)}%` }} /></div>
                    </div>
                  ))}
                </div>
              </Section>

              <Section title="SLA breaches by severity" description="Open cases that exceed their configured SLA">
                <div className="space-y-2">
                  {severityOptions.map((item) => (
                    <button key={item} type="button" onClick={() => { setSeverity(item); setStatus("OPEN"); }} className="flex w-full items-center justify-between rounded-lg border border-slate-100 px-3 py-2 text-left hover:border-slate-300 hover:bg-slate-50">
                      <Badge variant={severityVariant(item)}>{item}</Badge>
                      <span className="text-sm font-bold tabular-nums text-slate-800">{number(dashboard.sla_breaches_by_severity[item] || 0)}</span>
                    </button>
                  ))}
                </div>
              </Section>

              <Section title="Resolution performance" description="Resolved cases only; dismissed cases excluded">
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg bg-slate-50 p-3"><div className="text-[10px] font-semibold uppercase text-slate-500">Median time</div><div className="mt-2 text-xl font-bold text-slate-900">{hours(dashboard.resolution_performance.median_resolution_hours)}</div></div>
                  <div className="rounded-lg bg-slate-50 p-3"><div className="text-[10px] font-semibold uppercase text-slate-500">Average time</div><div className="mt-2 text-xl font-bold text-slate-900">{hours(dashboard.resolution_performance.average_resolution_hours)}</div></div>
                </div>
                <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-3 text-[11px] text-slate-500"><span>Resolved investigations</span><strong className="text-slate-800">{number(dashboard.resolution_performance.resolved_count)}</strong></div>
              </Section>
            </div>

            <Section title="Detection and resolution trend" description="Daily counts based on first detection date and resolution date (UTC)">
              {trend.length ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-4 text-[10px] text-slate-500"><span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm bg-blue-500" /> Opened</span><span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm bg-emerald-500" /> Resolved</span></div>
                  <div className="flex h-36 items-end gap-2 overflow-x-auto border-b border-slate-100 pb-1">
                    {trend.map((item) => (
                      <div key={item.date} className="flex min-w-8 flex-1 flex-col items-center justify-end gap-1">
                        <div className="flex h-28 w-full items-end justify-center gap-1">
                          <div title={`Opened: ${item.opened_count}`} className="w-2/5 rounded-t bg-blue-500" style={{ height: `${Math.max(item.opened_count ? 4 : 0, (item.opened_count / maxTrend) * 100)}%` }} />
                          <div title={`Resolved: ${item.resolved_count}`} className="w-2/5 rounded-t bg-emerald-500" style={{ height: `${Math.max(item.resolved_count ? 4 : 0, (item.resolved_count / maxTrend) * 100)}%` }} />
                        </div>
                        <span className="text-[9px] text-slate-400">{item.date.slice(5)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : <p className="text-xs text-slate-400">No trend data in this date range.</p>}
            </Section>

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
              <Section title="Investigation amounts by supplier" description="Open supplier-linked exceptions; not confirmed loss">
                {dashboard.investigation_amounts_by_supplier.length ? (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[420px] text-left text-xs">
                      <thead><tr className="border-b border-slate-100 text-[10px] uppercase text-slate-400"><th className="pb-2">Supplier</th><th className="pb-2 text-right">Cases</th><th className="pb-2 text-right">Unmatched</th></tr></thead>
                      <tbody className="divide-y divide-slate-50">
                        {dashboard.investigation_amounts_by_supplier.slice(0, 8).map((item) => <tr key={item.vendor_id}><td className="py-2 pr-3"><div className="font-semibold text-slate-800">{item.vendor_name || `Vendor #${item.vendor_id}`}</div><div className="text-[10px] text-slate-400">ID {item.vendor_id}</div></td><td className="py-2 text-right text-slate-600">{number(item.exception_count)}</td><td className="py-2 text-right font-semibold text-slate-800">{money(item.unmatched_amount_paise)}</td></tr>)}
                      </tbody>
                    </table>
                  </div>
                ) : <p className="text-xs text-slate-400">No supplier-linked open investigation amounts.</p>}
              </Section>

              <Section title="Investigation amounts by bank account" description="Statement-line exceptions only; kept separate from supplier payment cases">
                {dashboard.investigation_amounts_by_bank_account.length ? (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[420px] text-left text-xs">
                      <thead><tr className="border-b border-slate-100 text-[10px] uppercase text-slate-400"><th className="pb-2">Bank account reference</th><th className="pb-2 text-right">Cases</th><th className="pb-2 text-right">Unmatched</th></tr></thead>
                      <tbody className="divide-y divide-slate-50">
                        {dashboard.investigation_amounts_by_bank_account.slice(0, 8).map((item) => <tr key={item.bank_account_ref}><td className="py-2 pr-3 font-semibold text-slate-800">{item.bank_account_ref}</td><td className="py-2 text-right text-slate-600">{number(item.exception_count)}</td><td className="py-2 text-right font-semibold text-slate-800">{money(item.unmatched_amount_paise)}</td></tr>)}
                      </tbody>
                    </table>
                  </div>
                ) : <p className="text-xs text-slate-400">No bank-account-linked open investigation amounts.</p>}
              </Section>
            </div>

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
              <Section title="Exception categories" description="Select a category to inspect its open worklist">
                <div className="space-y-1.5">
                  {Object.entries(dashboard.by_exception_type).sort((a, b) => b[1].open_count - a[1].open_count).map(([type, counts]) => (
                    <button key={type} type="button" onClick={() => selectExceptionType(type)} className={`flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left transition-colors ${exceptionType === type ? "border-blue-300 bg-blue-50" : "border-slate-100 hover:bg-slate-50"}`}>
                      <span className="text-xs font-medium text-slate-700">{titleCase(type)}</span>
                      <span className="flex items-center gap-3 text-[11px]"><span className="text-slate-400">{number(counts.count)} total</span><strong className="text-slate-800">{number(counts.open_count)} open</strong></span>
                    </button>
                  ))}
                </div>
              </Section>

              <Section title="Finance team workload" description="Current assignment load and resolved investigations">
                {dashboard.finance_workload.length ? (
                  <div className="space-y-2">
                    {dashboard.finance_workload.slice(0, 8).map((item) => (
                      <div key={item.user_id ?? "unassigned"} className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 px-3 py-2">
                        <div><div className="text-xs font-semibold text-slate-800">{item.user_name || (item.user_id ? `User #${item.user_id}` : "Unassigned")}</div><div className="mt-0.5 text-[10px] text-slate-400">{number(item.assigned_total)} assigned · {number(item.assigned_resolved_count)} resolved</div></div>
                        <div className="text-right"><div className="text-sm font-bold tabular-nums text-slate-900">{number(item.assigned_open)}</div><div className="text-[10px] text-slate-400">open</div></div>
                      </div>
                    ))}
                  </div>
                ) : <p className="text-xs text-slate-400">No workload records in this date range.</p>}
              </Section>
            </div>
          </>
        ) : null}

        <Section
          title="Reconciliation exception worklist"
          description={`${number(queue?.total || 0)} records returned · maximum 1,000 · select a category above or use filters`}
          action={<span className="text-[10px] text-slate-400">Persisted investigation queue</span>}
        >
          {queue?.exceptions.length ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-left text-xs">
                <thead><tr className="border-b border-slate-100 text-[10px] uppercase tracking-wide text-slate-400">
                  <th className="pb-2 pr-3">Exception</th><th className="pb-2 pr-3">Severity</th><th className="pb-2 pr-3">Status</th><th className="pb-2 pr-3">Reference</th><th className="pb-2 pr-3 text-right">Age</th><th className="pb-2 pr-3 text-right">Unmatched</th><th className="pb-2">Source</th><th className="pb-2">SLA</th>
                </tr></thead>
                <tbody className="divide-y divide-slate-50">
                  {queue.exceptions.map((item) => (
                    <tr key={item.id} className="align-top hover:bg-slate-50/70">
                      <td className="py-3 pr-3"><div className="font-semibold text-slate-800">{titleCase(item.exception_type)}</div><div className="mt-0.5 max-w-xs text-[10px] leading-relaxed text-slate-500">{item.summary}</div><div className="mt-1 text-[10px] text-slate-400">#{item.id}</div></td>
                      <td className="py-3 pr-3"><Badge variant={severityVariant(item.severity)} size="sm">{item.severity}</Badge></td>
                      <td className="py-3 pr-3"><Badge variant={statusVariant(item.status)} size="sm">{titleCase(item.status)}</Badge></td>
                      <td className="py-3 pr-3"><div className="font-medium text-slate-700">{item.reference_type}</div><div className="text-[10px] text-slate-400">#{item.reference_id}</div></td>
                      <td className="py-3 pr-3 text-right tabular-nums text-slate-700">{hours(item.age_hours)}</td>
                      <td className="py-3 pr-3 text-right font-semibold tabular-nums text-slate-800">{money(item.unmatched_amount_paise)}</td>
                      <td className="py-3 pr-3">{item.source_present ? <Badge variant="success" size="sm">Present</Badge> : <Badge variant="warning" size="sm">Missing</Badge>}</td>
                      <td className="py-3">{item.sla_overdue ? <Badge variant="danger" size="sm">Breached</Badge> : <Badge variant="neutral" size="sm">Within SLA</Badge>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <div className="py-8 text-center"><CheckCircle2 size={22} className="mx-auto text-emerald-500" /><p className="mt-2 text-xs font-semibold text-slate-700">No exceptions match these filters</p><p className="mt-1 text-[11px] text-slate-400">Try clearing one or more worklist filters.</p></div>}
        </Section>

        <div className="flex flex-wrap items-center justify-between gap-2 pb-2 text-[10px] text-slate-400">
          <span className="flex items-center gap-1.5"><CalendarDays size={12} /> Date basis: UTC first-detected date</span>
          <span>Dashboard is read-only. Status, assignment and resolution changes remain in the controlled investigation workflow.</span>
        </div>
      </div>
    </div>
  );
};

export default ProcurementReconciliationWorkspace;
