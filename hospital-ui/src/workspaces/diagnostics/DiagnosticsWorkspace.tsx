import React, { useCallback, useEffect, useState } from "react";
import { AlertTriangle, FlaskConical, Plus, RefreshCw, ShieldCheck } from "lucide-react";
import { apiClient } from "../../api/client";
import { patientApi, type PatientCreatedResponse } from "../../api/patientApi";

type TaskStatus =
  | "PENDING"
  | "SAMPLE_COLLECTED"
  | "SAMPLE_REJECTED"
  | "IN_PROGRESS"
  | "RESULT_ENTERED"
  | "VERIFIED"
  | "CANCELLED";

interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

interface DiagnosticTask {
  id: number;
  order_id: number;
  service_id: number;
  status: TaskStatus;
  result_value?: string | null;
  result_notes?: string | null;
  is_critical_panic: boolean;
  rejection_reason?: string | null;
  delta_check_flag?: string | null;
  previous_result_value?: string | null;
  delta_percentage?: number | null;
  service_name?: string | null;
  service_code?: string | null;
  patient_name?: string | null;
  patient_mrn?: string | null;
  order_status?: string | null;
}

interface ServiceCatalogItem {
  id: number;
  code: string;
  name: string;
  service_type: string;
  base_price_paise: number;
  is_order_set: boolean;
  is_active: boolean;
}

interface DiagnosticOrderCreated {
  id: number;
  status: string;
  tasks: Array<{ id: number; service_id: number; status: TaskStatus }>;
}

const statusLabel: Record<TaskStatus, string> = {
  PENDING: "Awaiting sample",
  SAMPLE_COLLECTED: "Sample collected",
  SAMPLE_REJECTED: "Sample rejected",
  IN_PROGRESS: "In analysis",
  RESULT_ENTERED: "Result entered",
  VERIFIED: "Verified",
  CANCELLED: "Cancelled",
};

const statusStyle: Record<TaskStatus, string> = {
  PENDING: "bg-amber-50 text-amber-800",
  SAMPLE_COLLECTED: "bg-sky-50 text-sky-800",
  SAMPLE_REJECTED: "bg-rose-50 text-rose-800",
  IN_PROGRESS: "bg-indigo-50 text-indigo-800",
  RESULT_ENTERED: "bg-violet-50 text-violet-800",
  VERIFIED: "bg-emerald-50 text-emerald-800",
  CANCELLED: "bg-slate-100 text-slate-600",
};

export const DiagnosticsWorkspace: React.FC = () => {
  const [tasks, setTasks] = useState<DiagnosticTask[]>([]);
  const [panicAlerts, setPanicAlerts] = useState<DiagnosticTask[]>([]);
  const [catalog, setCatalog] = useState<ServiceCatalogItem[]>([]);
  const [patients, setPatients] = useState<PatientCreatedResponse[]>([]);
  const [patientSearch, setPatientSearch] = useState("");
  const [selectedPatientId, setSelectedPatientId] = useState<number | "">("");
  const [selectedServiceIds, setSelectedServiceIds] = useState<number[]>([]);
  const [clinicalNotes, setClinicalNotes] = useState("");
  const [showOrderForm, setShowOrderForm] = useState(false);
  const [selectedTask, setSelectedTask] = useState<DiagnosticTask | null>(null);
  const [resultValue, setResultValue] = useState("");
  const [resultNotes, setResultNotes] = useState("");
  const [criticalPanic, setCriticalPanic] = useState(false);
  const [rejectionReason, setRejectionReason] = useState("HEMOLYZED_SAMPLE");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const loadWorklists = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [worklist, alerts] = await Promise.all([
        apiClient<Page<DiagnosticTask>>("/api/diagnostics/tasks/worklist", {
          params: { page: 1, page_size: 100 },
        }),
        apiClient<DiagnosticTask[]>("/api/diagnostics/tasks/panic-alerts"),
      ]);
      setTasks(worklist.items);
      setPanicAlerts(alerts);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load laboratory worklists.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadWorklists();
    apiClient<Page<ServiceCatalogItem>>("/api/diagnostics/catalog", {
      params: { page: 1, page_size: 100 },
    })
      .then((response) => setCatalog(response.items.filter((item) => item.is_active)))
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load the diagnostic catalog."));
  }, [loadWorklists]);

  const searchPatients = async (value: string) => {
    setPatientSearch(value);
    setSelectedPatientId("");
    if (value.trim().length < 2) {
      setPatients([]);
      return;
    }
    try {
      const response = await patientApi.listPatients(value.trim(), 1);
      setPatients(response.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Patient search failed.");
    }
  };

  const createOrder = async (event: React.FormEvent) => {
    event.preventDefault();
    if (selectedPatientId === "" || selectedServiceIds.length === 0) {
      setError("Select a patient and at least one diagnostic service.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await apiClient<DiagnosticOrderCreated>("/api/diagnostics/orders", {
        method: "POST",
        body: JSON.stringify({
          patient_id: selectedPatientId,
          ordered_service_ids: selectedServiceIds,
          clinical_notes: clinicalNotes.trim() || null,
        }),
      });
      setShowOrderForm(false);
      setPatientSearch("");
      setPatients([]);
      setSelectedPatientId("");
      setSelectedServiceIds([]);
      setClinicalNotes("");
      await loadWorklists();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to place diagnostic order.");
    } finally {
      setSaving(false);
    }
  };

  const updateTask = async (
    task: DiagnosticTask,
    payload: {
      status: TaskStatus;
      result_value?: string;
      result_notes?: string;
      is_critical_panic?: boolean;
      rejection_reason?: string;
    },
  ) => {
    setSaving(true);
    setError(null);
    try {
      await apiClient(`/api/diagnostics/tasks/${task.id}/result`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      setSelectedTask(null);
      setResultValue("");
      setResultNotes("");
      setCriticalPanic(false);
      await loadWorklists();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update laboratory task.");
    } finally {
      setSaving(false);
    }
  };

  const openResultEntry = (task: DiagnosticTask) => {
    setSelectedTask(task);
    setResultValue(task.result_value ?? "");
    setResultNotes(task.result_notes ?? "");
    setCriticalPanic(task.is_critical_panic);
  };

  const submitResult = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedTask || !resultValue.trim()) return;
    await updateTask(selectedTask, {
      status: "RESULT_ENTERED",
      result_value: resultValue.trim(),
      result_notes: resultNotes.trim() || undefined,
      is_critical_panic: criticalPanic,
    });
  };

  const rejectSample = async (task: DiagnosticTask) => {
    const reason = rejectionReason.trim();
    if (!reason) {
      setError("A specimen rejection reason is required.");
      return;
    }
    await updateTask(task, { status: "SAMPLE_REJECTED", rejection_reason: reason });
  };

  const pendingCount = tasks.filter((task) => task.status !== "VERIFIED" && task.status !== "CANCELLED").length;

  return (
    <div className="space-y-6 p-4 md:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-xl font-semibold text-slate-900">
            <FlaskConical className="h-6 w-6 text-sky-700" />
            Diagnostics & Laboratory
          </div>
          <p className="mt-1 text-sm text-slate-500">Live diagnostic orders, specimen workflow and result lifecycle</p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={() => void loadWorklists()} disabled={loading} className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium disabled:opacity-50">
            <RefreshCw className="h-4 w-4" /> Refresh
          </button>
          <button type="button" onClick={() => setShowOrderForm((value) => !value)} className="inline-flex items-center gap-2 rounded-lg bg-sky-700 px-3 py-2 text-sm font-medium text-white">
            <Plus className="h-4 w-4" /> New diagnostic order
          </button>
        </div>
      </header>

      {error && <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}

      {panicAlerts.length > 0 && (
        <section className="rounded-xl border border-rose-300 bg-rose-50 p-4" aria-label="Critical laboratory alerts">
          <div className="flex items-center gap-2 font-semibold text-rose-900">
            <AlertTriangle className="h-5 w-5" /> Critical / panic laboratory alerts ({panicAlerts.length})
          </div>
          <p className="mt-1 text-sm text-rose-800">Escalate critical values immediately using the hospital's approved clinical communication process. This workspace does not record a verbal read-back acknowledgement.</p>
          <ul className="mt-3 space-y-2">
            {panicAlerts.map((task) => (
              <li key={task.id} className="rounded-lg bg-white/80 p-3 text-sm">
                <strong>{task.patient_name || "Patient identity unavailable"}</strong>
                <span className="mx-2 text-slate-500">{task.patient_mrn || "MRN unavailable"}</span>
                <span>{task.service_name || `Service #${task.service_id}`}</span>
                <span className="ml-2 font-semibold text-rose-700">{task.result_value || "Critical result"}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {showOrderForm && (
        <form onSubmit={createOrder} className="space-y-4 rounded-xl border bg-white p-4 shadow-sm">
          <div className="font-semibold text-slate-900">Place diagnostic order</div>
          <label className="block text-sm font-medium text-slate-700">
            Find patient
            <input value={patientSearch} onChange={(event) => void searchPatients(event.target.value)} placeholder="Search by name or MRN" className="mt-1 w-full rounded-lg border px-3 py-2 font-normal" />
          </label>
          {patients.length > 0 && (
            <label className="block text-sm font-medium text-slate-700">
              Patient
              <select value={selectedPatientId} onChange={(event) => setSelectedPatientId(event.target.value ? Number(event.target.value) : "")} className="mt-1 w-full rounded-lg border px-3 py-2 font-normal">
                <option value="">Select patient</option>
                {patients.map((patient) => <option key={patient.id} value={patient.id}>{patient.full_name} — {patient.mrn}</option>)}
              </select>
            </label>
          )}
          <fieldset>
            <legend className="mb-2 text-sm font-medium text-slate-700">Diagnostic services</legend>
            <div className="grid gap-2 md:grid-cols-2">
              {catalog.map((item) => (
                <label key={item.id} className="flex items-center gap-2 rounded-lg border p-3 text-sm">
                  <input type="checkbox" checked={selectedServiceIds.includes(item.id)} onChange={(event) => setSelectedServiceIds((current) => event.target.checked ? [...current, item.id] : current.filter((id) => id !== item.id))} />
                  <span className="min-w-0 flex-1">{item.name} <span className="text-xs text-slate-500">({item.code})</span></span>
                  <span className="text-xs text-slate-500">{(item.base_price_paise / 100).toFixed(2)}</span>
                </label>
              ))}
            </div>
            {catalog.length === 0 && <p className="text-sm text-slate-500">No active diagnostic catalog items are available.</p>}
          </fieldset>
          <label className="block text-sm font-medium text-slate-700">
            Clinical notes (optional)
            <textarea value={clinicalNotes} onChange={(event) => setClinicalNotes(event.target.value)} rows={2} className="mt-1 w-full rounded-lg border px-3 py-2 font-normal" />
          </label>
          <div className="flex gap-2">
            <button disabled={saving} className="rounded-lg bg-sky-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{saving ? "Placing…" : "Place order"}</button>
            <button type="button" onClick={() => setShowOrderForm(false)} className="rounded-lg border px-4 py-2 text-sm">Cancel</button>
          </div>
        </form>
      )}

      <section className="rounded-xl border bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b p-4">
          <div>
            <h2 className="font-semibold text-slate-900">Laboratory worklist</h2>
            <p className="text-sm text-slate-500">{pendingCount} active task(s) in the current page</p>
          </div>
          <span className="text-xs text-slate-500">Showing up to 100 tasks</span>
        </div>
        {loading ? (
          <p className="p-6 text-sm text-slate-500">Loading live worklist…</p>
        ) : tasks.length === 0 ? (
          <p className="p-6 text-sm text-slate-500">No active laboratory tasks.</p>
        ) : (
          <div className="divide-y">
            {tasks.map((task) => (
              <article key={task.id} className="grid gap-3 p-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <strong className="text-slate-900">{task.service_name || `Service #${task.service_id}`}</strong>
                    <span className={`rounded-full px-2 py-1 text-xs font-medium ${statusStyle[task.status]}`}>{statusLabel[task.status]}</span>
                    {task.is_critical_panic && <span className="rounded-full bg-rose-100 px-2 py-1 text-xs font-semibold text-rose-800">PANIC</span>}
                  </div>
                  <p className="mt-1 text-sm text-slate-600">{task.patient_name || "Patient identity unavailable"} · {task.patient_mrn || "MRN unavailable"} · Order #{task.order_id} · Task #{task.id}</p>
                  {task.result_value && <p className="mt-1 text-sm"><span className="font-medium">Result:</span> {task.result_value} {task.delta_check_flag && <span className="ml-2 text-amber-700">Delta: {task.delta_check_flag}</span>}</p>}
                  {task.rejection_reason && <p className="mt-1 text-sm text-rose-700">Rejection: {task.rejection_reason}</p>}
                </div>
                <div className="flex flex-wrap gap-2">
                  {task.status === "PENDING" && <button disabled={saving} onClick={() => void updateTask(task, { status: "SAMPLE_COLLECTED" })} className="rounded-lg border px-3 py-2 text-xs font-medium">Mark collected</button>}
                  {task.status === "SAMPLE_COLLECTED" && <button disabled={saving} onClick={() => void updateTask(task, { status: "IN_PROGRESS" })} className="rounded-lg border px-3 py-2 text-xs font-medium">Start analysis</button>}
                  {task.status === "SAMPLE_REJECTED" && <button disabled={saving} onClick={() => void updateTask(task, { status: "SAMPLE_COLLECTED" })} className="rounded-lg border px-3 py-2 text-xs font-medium">Recollect</button>}
                  {(task.status === "PENDING" || task.status === "SAMPLE_COLLECTED" || task.status === "IN_PROGRESS") && (
                    <button disabled={saving} onClick={() => openResultEntry(task)} className="rounded-lg bg-sky-700 px-3 py-2 text-xs font-medium text-white">Enter result</button>
                  )}
                  {(task.status === "PENDING" || task.status === "SAMPLE_COLLECTED" || task.status === "IN_PROGRESS") && (
                    <button disabled={saving} onClick={() => void rejectSample(task)} className="rounded-lg border border-rose-200 px-3 py-2 text-xs font-medium text-rose-700">Reject sample</button>
                  )}
                  {task.status === "RESULT_ENTERED" && <button disabled={saving} onClick={() => void updateTask(task, { status: "VERIFIED" })} className="inline-flex items-center gap-1 rounded-lg bg-emerald-700 px-3 py-2 text-xs font-medium text-white"><ShieldCheck className="h-3.5 w-3.5" /> Verify result</button>}
                  {task.status === "VERIFIED" && <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700"><ShieldCheck className="h-4 w-4" /> Verified</span>}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {selectedTask && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4">
          <form onSubmit={submitResult} className="w-full max-w-lg space-y-4 rounded-xl bg-white p-5 shadow-xl">
            <div>
              <h3 className="font-semibold text-slate-900">Enter laboratory result</h3>
              <p className="text-sm text-slate-500">{selectedTask.service_name || `Task #${selectedTask.id}`} · {selectedTask.patient_name || "Patient identity unavailable"}</p>
            </div>
            <label className="block text-sm font-medium">Result value
              <input required value={resultValue} onChange={(event) => setResultValue(event.target.value)} className="mt-1 w-full rounded-lg border px-3 py-2" />
            </label>
            <label className="block text-sm font-medium">Result notes
              <textarea value={resultNotes} onChange={(event) => setResultNotes(event.target.value)} rows={3} className="mt-1 w-full rounded-lg border px-3 py-2" />
            </label>
            <label className="flex items-center gap-2 text-sm text-rose-800">
              <input type="checkbox" checked={criticalPanic} onChange={(event) => setCriticalPanic(event.target.checked)} />
              Mark as critical / panic value
            </label>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setSelectedTask(null)} className="rounded-lg border px-4 py-2 text-sm">Cancel</button>
              <button disabled={saving || !resultValue.trim()} className="rounded-lg bg-sky-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">{saving ? "Saving…" : "Submit result"}</button>
            </div>
          </form>
        </div>
      )}

      <p className="text-xs text-slate-500">Result verification is enforced by the backend, including permission checks and separation of duties. Critical-value communication acknowledgement and report printing are not represented as completed workflows here.</p>
    </div>
  );
};
