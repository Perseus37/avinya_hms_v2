import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  ReconciliationExceptionEvent,
  ReconciliationAssignee,
  ReconciliationAssignmentRecommendation,
  ReconciliationResolutionGuidance,
  ReconciliationEvidence,
} from "../../api/reconciliationApi";
import { Badge } from "../../components/ui/Badge";
import { ReconciliationSlaPolicyPanel } from "./ReconciliationSlaPolicyPanel";
import { Button } from "../../components/ui/Button";
import { usePermissions } from "../../core/context/PermissionsContext";
import { useAuth } from "../../core/context/AuthContext";

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
  onClick: () => void;
  selected?: boolean;
}> = ({ label, value, detail, icon: Icon, tone = "normal", onClick, selected = false }) => {
  const tones = {
    normal: "border-slate-200 bg-white text-slate-800",
    danger: "border-rose-200 bg-rose-50 text-rose-800",
    warning: "border-amber-200 bg-amber-50 text-amber-800",
    success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  };
  return (
    <button type="button" onClick={onClick} aria-pressed={selected} className={`w-full rounded-xl border p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-400 ${tones[tone]} ${selected ? "ring-2 ring-blue-500" : ""}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-wide opacity-70">{label}</span>
        <Icon size={17} className="opacity-70" />
      </div>
      <div className="mt-3 text-2xl font-bold tabular-nums">{value}</div>
      <div className="mt-1 text-[11px] opacity-70">{detail}</div>
    </button>
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
  const { hasPermission } = usePermissions();
  const { user } = useAuth();
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
  const [slaOverdueOnly, setSlaOverdueOnly] = useState(false);
  const [unassignedOnly, setUnassignedOnly] = useState(false);
  const [sourceMissingOnly, setSourceMissingOnly] = useState(false);
  const [openOnly, setOpenOnly] = useState(false);
  const [dashboard, setDashboard] = useState<ReconciliationDashboard | null>(null);
  const [queue, setQueue] = useState<ReconciliationQueue | null>(null);
  const [escalations, setEscalations] = useState<Awaited<ReturnType<typeof reconciliationApi.getAssignmentEscalations>> | null>(null);
  const [assignmentResponseReason, setAssignmentResponseReason] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastLoadedAt, setLastLoadedAt] = useState<Date | null>(null);
  const [selectedException, setSelectedException] = useState<ReconciliationException | null>(null);
  const selectedExceptionIdRef = useRef<number | null>(null);
  const [history, setHistory] = useState<ReconciliationExceptionEvent[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [detailMessage, setDetailMessage] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [assigneeInput, setAssigneeInput] = useState("");
  const [assigneeSearch, setAssigneeSearch] = useState("");
  const [assigneeOptions, setAssigneeOptions] = useState<ReconciliationAssignee[]>([]);
  const [assigneeLoading, setAssigneeLoading] = useState(false);
  const [assigneePickerOpen, setAssigneePickerOpen] = useState(false);
  const [assignmentRecommendations, setAssignmentRecommendations] = useState<ReconciliationAssignmentRecommendation[]>([]);
  const [recommendationsLoading, setRecommendationsLoading] = useState(false);
  const [recommendationsLoaded, setRecommendationsLoaded] = useState(false);
  const [assignmentNote, setAssignmentNote] = useState("");
  const [investigationNote, setInvestigationNote] = useState("");
  const [statusChoice, setStatusChoice] = useState<ReconciliationStatus>("IN_REVIEW");
  const [statusNote, setStatusNote] = useState("");
  const [resolutionGuidance, setResolutionGuidance] = useState<ReconciliationResolutionGuidance | null>(null);
  const [rootCauseCode, setRootCauseCode] = useState("");
  const [resolutionChecklist, setResolutionChecklist] = useState<Record<string, boolean>>({});
  const [resolutionReviewNote, setResolutionReviewNote] = useState("");
  const [reopenReason, setReopenReason] = useState("");
  const [slaPauseReason, setSlaPauseReason] = useState("");
  const [slaResumeReason, setSlaResumeReason] = useState("");
  const [evidence, setEvidence] = useState<ReconciliationEvidence[]>([]);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceUploading, setEvidenceUploading] = useState(false);
  const [auditExporting, setAuditExporting] = useState(false);
  const [evidenceFile, setEvidenceFile] = useState<File | null>(null);
  const [evidenceType, setEvidenceType] = useState<ReconciliationEvidence["evidence_type"]>("OTHER");
  const [evidenceDescription, setEvidenceDescription] = useState("");
  const rankedAssigneeOptions = useMemo(() => [...assigneeOptions].sort((a, b) => {
    const loadA = dashboard?.finance_workload.find((item) => item.user_id === a.id);
    const loadB = dashboard?.finance_workload.find((item) => item.user_id === b.id);
    const overdueDifference = (loadA?.assigned_sla_overdue || 0) - (loadB?.assigned_sla_overdue || 0);
    if (overdueDifference !== 0) return overdueDifference;
    const openDifference = (loadA?.assigned_open || 0) - (loadB?.assigned_open || 0);
    return openDifference !== 0 ? openDifference : a.full_name.localeCompare(b.full_name);
  }), [assigneeOptions, dashboard]);

  useEffect(() => {
    if (!selectedException || !hasPermission("finance.manage_reconciliation") || !assigneePickerOpen) {
      setAssigneeOptions([]);
      setAssigneeLoading(false);
      return;
    }
    let active = true;
    setAssigneeLoading(true);
    const timer = window.setTimeout(async () => {
      try {
        const result = await reconciliationApi.getAssignableUsers(assigneeSearch, 50);
        if (active) setAssigneeOptions(result.items || []);
      } catch (err) {
        if (active) setDetailError(err instanceof Error ? err.message : "Unable to load branch staff.");
      } finally {
        if (active) setAssigneeLoading(false);
      }
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [selectedException?.id, assigneeSearch, assigneePickerOpen, hasPermission]);

  const filters = useMemo<ReconciliationFilters>(() => ({
    from_date: fromDate || undefined,
    to_date: toDate || undefined,
    severity: severity || undefined,
    status: status || undefined,
    assigned_to_id: assignedToId ? Number(assignedToId) : undefined,
  }), [fromDate, toDate, severity, status, assignedToId]);

  const queueFilters = useMemo(() => ({
    severity: severity || undefined,
    status: status || undefined,
    assigned_to_id: assignedToId ? Number(assignedToId) : undefined,
    exception_type: exceptionType || undefined,
    sla_overdue: slaOverdueOnly ? true : undefined,
    unassigned_only: unassignedOnly ? true : undefined,
    source_present: sourceMissingOnly ? false : undefined,
    open_only: openOnly ? true : undefined,
  }), [severity, status, assignedToId, exceptionType, slaOverdueOnly, unassignedOnly, sourceMissingOnly, openOnly]);

  const clearQueueDrilldowns = () => {
    setSlaOverdueOnly(false);
    setUnassignedOnly(false);
    setSourceMissingOnly(false);
  };

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [summary, worklist] = await Promise.all([
        reconciliationApi.getDashboard(filters),
        reconciliationApi.getQueue(queueFilters),
      ]);
      setDashboard(summary);
      setQueue(worklist);
      try {
        const escalationQueue = await reconciliationApi.getAssignmentEscalations(100);
        setEscalations(escalationQueue);
      } catch {
        setEscalations(null);
      }
      setLastLoadedAt(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load procurement reconciliation data.");
    } finally {
      setLoading(false);
    }
  }, [filters, queueFilters]);

  useEffect(() => { void load(); }, [load]);


  const openException = async (item: ReconciliationException) => {
    selectedExceptionIdRef.current = item.id;
    setSelectedException(item); setHistory([]); setDetailError(""); setDetailMessage("");
    setAssigneeInput(item.assigned_to_id === null ? "" : String(item.assigned_to_id));
    setAssigneeSearch("");
    setAssigneeOptions([]);
    setAssigneePickerOpen(false);
    setAssignmentRecommendations([]);
    setRecommendationsLoaded(false);
    setRecommendationsLoading(false);
    setAssignmentNote(""); setAssignmentResponseReason(""); setInvestigationNote(""); setStatusChoice(item.status === "IN_REVIEW" ? "OPEN" : "IN_REVIEW"); setStatusNote("");
    setResolutionGuidance(null); setRootCauseCode(""); setResolutionChecklist({}); setResolutionReviewNote(""); setReopenReason("");
    setEvidence([]); setEvidenceFile(null); setEvidenceType("OTHER"); setEvidenceDescription("");
    setHistoryLoading(true); setEvidenceLoading(true);
    try {
      const [historyResult, guidance, evidenceRows] = await Promise.all([
        reconciliationApi.getExceptionHistory(item.id),
        reconciliationApi.getResolutionGuidance(item.id),
        reconciliationApi.getEvidence(item.id),
      ]);
      if (selectedExceptionIdRef.current === item.id) {
        setHistory(historyResult.events || []);
        setResolutionGuidance(guidance);
        setEvidence(evidenceRows || []);
      }
    } catch (err) { setDetailError(err instanceof Error ? err.message : "Unable to load investigation history, evidence or resolution guidance."); }
    finally { setHistoryLoading(false); setEvidenceLoading(false); }
  };
  const refreshSelectedHistory = async (id: number) => {
    const result = await reconciliationApi.getExceptionHistory(id);
    setHistory(result.events || []);
  };
  const loadAssignmentRecommendations = async () => {
    if (!selectedException) return;
    const targetId = selectedException.id;
    setRecommendationsLoading(true);
    setDetailError("");
    try {
      const result = await reconciliationApi.getAssignmentRecommendations(targetId, 5);
      if (selectedExceptionIdRef.current === targetId) {
        setAssignmentRecommendations(result.recommendations || []);
        setRecommendationsLoaded(true);
      }
    } catch (err) {
      if (selectedException?.id === targetId) {
        setDetailError(err instanceof Error ? err.message : "Unable to calculate assignment recommendations.");
      }
    } finally {
      if (selectedExceptionIdRef.current === targetId) setRecommendationsLoading(false);
    }
  };

  const chooseRecommendedAssignee = (person: ReconciliationAssignmentRecommendation) => {
    setAssigneeInput(String(person.user_id));
    setAssigneeSearch(person.user_name);
    setAssigneeOptions([]);
    setAssigneePickerOpen(false);
    setDetailMessage(`${person.user_name} selected. Review the recommendation and save to confirm assignment.`);
  };

  const saveAssignment = async () => {
    if (!selectedException) return;
    const parsed = assigneeInput.trim() ? Number(assigneeInput) : null;
    if (parsed !== null && (!Number.isInteger(parsed) || parsed < 1)) { setDetailError("Enter a positive branch user ID or leave blank to unassign."); return; }
    if (selectedException.assigned_to_id !== null && parsed !== selectedException.assigned_to_id && assignmentNote.trim().length < 10) {
      setDetailError("A reassignment reason of at least 10 characters is required.");
      return;
    }
    setActionLoading(true); setDetailError(""); setDetailMessage("");
    try {
      const result = await reconciliationApi.assignException(selectedException.id, { assigned_to_id: parsed, note: assignmentNote.trim() || undefined });
      const updated = { ...selectedException, assigned_to_id: result.assigned_to_id };
      setSelectedException(updated);
      setQueue((current) => current ? { ...current, exceptions: current.exceptions.map((row) => row.id === updated.id ? updated : row) } : current);
      setDetailMessage(result.notification_status === "QUEUED" ? "Assignment saved. An email notification and acknowledgement reminder have been queued." : result.notification_status === "QUEUE_UNAVAILABLE" ? "Assignment saved, but notification delivery could not be queued. Please notify the assignee manually." : result.notification_status === "EMAIL_UNAVAILABLE" ? "Assignment saved, but the assignee has no email address configured. Please notify them manually." : "Assignment saved."); setAssignmentNote(""); await refreshSelectedHistory(updated.id); void load();
    } catch (err) { setDetailError(err instanceof Error ? err.message : "Unable to save assignment."); }
    finally { setActionLoading(false); }
  };
  const respondToSelectedAssignment = async (decision: "ACCEPT" | "REJECT") => {
    if (!selectedException) return;
    if (decision === "REJECT" && assignmentResponseReason.trim().length < 10) {
      setDetailError("Please provide a rejection reason of at least 10 characters.");
      return;
    }
    setActionLoading(true); setDetailError(""); setDetailMessage("");
    try {
      const result = await reconciliationApi.respondToAssignment(selectedException.id, {
        decision,
        reason: assignmentResponseReason.trim() || undefined,
      });
      if (decision === "REJECT") {
        const updated = { ...selectedException, assigned_to_id: result.assigned_to_id };
        setSelectedException(updated);
        setQueue((current) => current ? { ...current, exceptions: current.exceptions.map((row) => row.id === updated.id ? updated : row) } : current);
      }
      setDetailMessage(decision === "ACCEPT" ? "Assignment accepted." : "Assignment rejected and returned to the manager's unassigned queue.");
      setAssignmentResponseReason("");
      await refreshSelectedHistory(selectedException.id);
      void load();
    } catch (err) {
      setDetailError(err instanceof Error ? err.message : "Unable to record assignment response.");
    } finally {
      setActionLoading(false);
    }
  };
  const openEscalation = async (exceptionId: number) => {
    const existing = queue?.exceptions.find((item) => item.id === exceptionId);
    if (existing) {
      await openException(existing);
      return;
    }
    try {
      const result = await reconciliationApi.getQueue({ open_only: true });
      setQueue(result);
      const match = result.exceptions.find((item) => item.id === exceptionId);
      if (match) await openException(match);
      else setError("This escalation candidate is no longer in the active worklist. Reload the queue.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to open escalation candidate.");
    }
  };

  const saveExceptionStatus = async () => {
    if (!selectedException) return;
    if ((statusChoice === "RESOLVED" || statusChoice === "DISMISSED") && statusNote.trim().length < 10) { setDetailError("Resolution and dismissal notes must contain at least 10 characters."); return; }
    setActionLoading(true); setDetailError(""); setDetailMessage("");
    try {
      const result = await reconciliationApi.updateExceptionStatus(selectedException.id, {
        status: statusChoice,
        note: statusNote.trim() || undefined,
        root_cause_code: statusChoice === "RESOLVED" ? rootCauseCode : undefined,
        resolution_checklist: statusChoice === "RESOLVED" ? resolutionChecklist : undefined,
      });
      const updated = {
        ...selectedException, status: result.status, resolved_at: result.resolved_at,
        resolution_note: result.resolution_note, root_cause_code: result.root_cause_code,
        resolution_checklist: result.resolution_checklist, resolution_review_status: result.resolution_review_status,
      };
      setSelectedException(updated);
      setQueue((current) => current ? { ...current, exceptions: current.exceptions.map((row) => row.id === updated.id ? updated : row) } : current);
      setDetailMessage(result.resolution_review_status === "PENDING" ? "Resolution submitted. Independent review is required before this case can close." : "Investigation status updated.");
      setStatusNote(""); await refreshSelectedHistory(updated.id); void load();
    } catch (err) { setDetailError(err instanceof Error ? err.message : "Unable to update status."); }
    finally { setActionLoading(false); }
  };
  const pauseSelectedSla = async () => {
    if (!selectedException) return;
    if (slaPauseReason.trim().length < 10) {
      setDetailError("A pause reason of at least 10 characters is required.");
      return;
    }
    setActionLoading(true); setDetailError(""); setDetailMessage("");
    try {
      const result = await reconciliationApi.pauseSla(selectedException.id, { reason: slaPauseReason.trim() });
      const updated = {
        ...selectedException, sla_paused: true, sla_paused_at: result.sla_paused_at,
        sla_paused_seconds: result.sla_paused_seconds, sla_elapsed_hours: result.sla_elapsed_hours,
        sla_remaining_hours: result.sla_remaining_hours, sla_overdue: result.sla_overdue,
        sla_breached_at: result.sla_breached_at,
      };
      setSelectedException(updated);
      setQueue((current) => current ? { ...current, exceptions: current.exceptions.map((row) => row.id === updated.id ? updated : row) } : current);
      setSlaPauseReason("");
      await refreshSelectedHistory(selectedException.id);
      await load();
      setDetailMessage("SLA clock paused. The reason and elapsed clock state were recorded in the investigation history.");
    } catch (err) { setDetailError(err instanceof Error ? err.message : "Unable to pause the SLA clock."); }
    finally { setActionLoading(false); }
  };

  const resumeSelectedSla = async () => {
    if (!selectedException) return;
    if (slaResumeReason.trim().length < 10) {
      setDetailError("A resume reason of at least 10 characters is required.");
      return;
    }
    setActionLoading(true); setDetailError(""); setDetailMessage("");
    try {
      const result = await reconciliationApi.resumeSla(selectedException.id, { reason: slaResumeReason.trim() });
      const updated = {
        ...selectedException, sla_paused: false, sla_paused_at: null,
        sla_paused_seconds: result.sla_paused_seconds, sla_elapsed_hours: result.sla_elapsed_hours,
        sla_remaining_hours: result.sla_remaining_hours, sla_overdue: result.sla_overdue,
        sla_breached_at: result.sla_breached_at,
      };
      setSelectedException(updated);
      setQueue((current) => current ? { ...current, exceptions: current.exceptions.map((row) => row.id === updated.id ? updated : row) } : current);
      setSlaResumeReason("");
      await refreshSelectedHistory(selectedException.id);
      await load();
      setDetailMessage("SLA clock resumed. Paused duration was excluded from active SLA elapsed time.");
    } catch (err) { setDetailError(err instanceof Error ? err.message : "Unable to resume the SLA clock."); }
    finally { setActionLoading(false); }
  };

  const reopenSelectedException = async () => {
    if (!selectedException) return;
    if (reopenReason.trim().length < 10) {
      setDetailError("A reason of at least 10 characters is required to reopen this investigation.");
      return;
    }
    setActionLoading(true); setDetailError(""); setDetailMessage("");
    try {
      const result = await reconciliationApi.reopenException(selectedException.id, { reason: reopenReason.trim() });
      const updated = {
        ...selectedException, status: result.status, reopen_count: result.reopen_count,
        resolved_at: null, resolution_note: null, root_cause_code: null,
        resolution_checklist: {}, resolution_review_status: "NOT_REQUIRED" as const,
      };
      setSelectedException(updated);
      setQueue((current) => current ? { ...current, exceptions: current.exceptions.map((row) => row.id === updated.id ? updated : row) } : current);
      setReopenReason(""); setStatusChoice("IN_REVIEW");
      setDetailMessage("Investigation reopened. The previous resolution remains in the audit history.");
      await refreshSelectedHistory(updated.id); void load();
    } catch (err) { setDetailError(err instanceof Error ? err.message : "Unable to reopen investigation."); }
    finally { setActionLoading(false); }
  };

  const reviewResolution = async (decision: "APPROVE" | "REJECT") => {
    if (!selectedException) return;
    if (resolutionReviewNote.trim().length < 10) {
      setDetailError("An independent review note of at least 10 characters is required.");
      return;
    }
    setActionLoading(true); setDetailError(""); setDetailMessage("");
    try {
      const result = await reconciliationApi.reviewExceptionResolution(selectedException.id, {
        decision, note: resolutionReviewNote.trim(),
      });
      const updated = { ...selectedException, status: result.status, resolution_review_status: result.resolution_review_status, resolved_at: result.resolved_at };
      setSelectedException(updated);
      setQueue((current) => current ? { ...current, exceptions: current.exceptions.map((row) => row.id === updated.id ? updated : row) } : current);
      setResolutionReviewNote("");
      setDetailMessage(decision === "APPROVE" ? "Resolution independently approved and case closed." : "Resolution rejected. Case returned to investigation.");
      await refreshSelectedHistory(updated.id); void load();
    } catch (err) { setDetailError(err instanceof Error ? err.message : "Unable to review resolution."); }
    finally { setActionLoading(false); }
  };

  const uploadInvestigationEvidence = async () => {
    if (!selectedException || !evidenceFile) return;
    if (evidenceFile.size <= 0) {
      setDetailError("Choose a non-empty evidence file.");
      return;
    }
    setEvidenceUploading(true); setDetailError(""); setDetailMessage("");
    try {
      const payload = new FormData();
      payload.append("evidence_type", evidenceType);
      if (evidenceDescription.trim()) payload.append("description", evidenceDescription.trim());
      payload.append("file", evidenceFile);
      const created = await reconciliationApi.uploadEvidence(selectedException.id, payload);
      setEvidence((current) => [...current, created]);
      setEvidenceFile(null); setEvidenceDescription("");
      setDetailMessage("Evidence uploaded, scanned and recorded in the investigation audit history.");
      await refreshSelectedHistory(selectedException.id);
    } catch (err) { setDetailError(err instanceof Error ? err.message : "Unable to upload evidence."); }
    finally { setEvidenceUploading(false); }
  };

  const downloadInvestigationEvidence = async (item: ReconciliationEvidence) => {
    if (!selectedException) return;
    setDetailError(""); setDetailMessage("");
    try {
      const blob = await reconciliationApi.downloadEvidence(selectedException.id, item.id);
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = item.original_filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
      setDetailMessage("Evidence download requested and recorded in the access audit.");
    } catch (err) { setDetailError(err instanceof Error ? err.message : "Unable to download evidence."); }
  };

  const exportInvestigationAudit = async () => {
    if (!selectedException) return;
    setAuditExporting(true); setDetailError(""); setDetailMessage("");
    try {
      const blob = await reconciliationApi.exportAuditPackage(selectedException.id);
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = "reconciliation-" + selectedException.id + "-audit.zip";
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      setDetailMessage("Audit package generated. The export event has been recorded in investigation history.");
      await refreshSelectedHistory(selectedException.id);
    } catch (err) { setDetailError(err instanceof Error ? err.message : "Unable to generate the investigation audit package."); }
    finally { setAuditExporting(false); }
  };

  const saveInvestigationNote = async () => {
    if (!selectedException || !investigationNote.trim()) return;
    setActionLoading(true); setDetailError(""); setDetailMessage("");
    try {
      await reconciliationApi.addExceptionNote(selectedException.id, { note: investigationNote.trim() });
      setDetailMessage("Investigation note added to the audit history."); setInvestigationNote(""); await refreshSelectedHistory(selectedException.id);
    } catch (err) { setDetailError(err instanceof Error ? err.message : "Unable to add note."); }
    finally { setActionLoading(false); }
  };

  const exceptionTypes = useMemo(() => Object.keys(dashboard?.by_exception_type || {}).sort(), [dashboard]);
  const maxAging = Math.max(1, ...Object.values(dashboard?.open_aging || {}).map((value) => Number(value)));
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
    setStatus("");
    setOpenOnly(true);
    clearQueueDrilldowns();
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

        <ReconciliationSlaPolicyPanel />

        {escalations && escalations.total > 0 && (
          <section className="rounded-xl border border-rose-200 bg-rose-50 p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div><div className="flex items-center gap-2 text-sm font-bold text-rose-900"><AlertTriangle size={16} /> Unacknowledged assignments requiring escalation</div>
                <p className="mt-1 text-[11px] text-rose-800">{escalations.total} assignment{escalations.total === 1 ? "" : "s"} exceeded the acknowledgement target. These are escalation candidates, not automatically reassigned cases.</p></div>
              <Badge variant="danger">{escalations.total} overdue</Badge>
            </div>
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              {escalations.items.slice(0, 6).map((item) => (
                <button key={item.exception_id} type="button" onClick={() => void openEscalation(item.exception_id)} className="flex items-center justify-between gap-3 rounded-lg border border-rose-200 bg-white px-3 py-2 text-left hover:bg-rose-100">
                  <span><span className="block text-xs font-semibold text-slate-800">#{item.exception_id} · {item.severity}</span><span className="block text-[10px] text-slate-500">Assigned to user #{item.assigned_to_id} · {hours(item.unacknowledged_hours)} unacknowledged</span></span>
                  <span className="shrink-0 text-[10px] font-semibold text-rose-700">Review <span aria-hidden="true">→</span></span>
                </button>
              ))}
            </div>
          </section>
        )}

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
              <select value={status} onChange={(event) => { setStatus(event.target.value as ReconciliationStatus | ""); setOpenOnly(false); clearQueueDrilldowns(); }} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-xs text-slate-800">
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
            <button type="button" onClick={() => { setFromDate(localDate(thirtyDaysAgo)); setToDate(localDate(today)); setSeverity(""); setStatus(""); setAssignedToId(""); setExceptionType(""); setOpenOnly(false); clearQueueDrilldowns(); }} className="text-[11px] font-semibold text-blue-700 hover:text-blue-900">Reset filters</button>
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
              <StatCard label="Open investigations" value={number(dashboard.overview.open_count + dashboard.overview.in_review_count)} detail="Click to inspect open and in-review cases" icon={Search} selected={openOnly && !slaOverdueOnly && !unassignedOnly && !sourceMissingOnly} onClick={() => { setStatus(""); setOpenOnly(true); clearQueueDrilldowns(); }} />
              <StatCard label="SLA breached" value={number(dashboard.overview.sla_breached_open_count)} detail="Click to inspect overdue open cases" icon={Clock3} tone={dashboard.overview.sla_breached_open_count ? "danger" : "success"} selected={slaOverdueOnly} onClick={() => { setStatus(""); setOpenOnly(true); setSlaOverdueOnly(true); setUnassignedOnly(false); setSourceMissingOnly(false); }} />
              <StatCard label="Unassigned" value={number(dashboard.overview.unassigned_open_count)} detail="Click to inspect cases without an owner" icon={Users} tone={dashboard.overview.unassigned_open_count ? "warning" : "normal"} selected={unassignedOnly} onClick={() => { setStatus(""); setOpenOnly(true); setUnassignedOnly(true); setSlaOverdueOnly(false); setSourceMissingOnly(false); }} />
              <StatCard label="Source missing" value={number(dashboard.overview.source_missing_open_count)} detail="Click to inspect cases absent in latest detection" icon={AlertTriangle} tone={dashboard.overview.source_missing_open_count ? "warning" : "normal"} selected={sourceMissingOnly} onClick={() => { setStatus(""); setOpenOnly(true); setSourceMissingOnly(true); setSlaOverdueOnly(false); setUnassignedOnly(false); }} />
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
                    <button key={item} type="button" onClick={() => { setSeverity(item); setStatus(""); setOpenOnly(true); clearQueueDrilldowns(); }} className="flex w-full items-center justify-between rounded-lg border border-slate-100 px-3 py-2 text-left hover:border-slate-300 hover:bg-slate-50">
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
                  {Object.entries(dashboard.by_exception_type).sort((a, b) => b[1].open_count - a[1].open_count).map(([type, counts]) => {
                    const amount = dashboard.investigation_amounts_by_exception_type[type];
                    return (
                      <button key={type} type="button" onClick={() => selectExceptionType(type)} className={`flex w-full items-center justify-between gap-3 rounded-lg border px-3 py-2 text-left transition-colors ${exceptionType === type ? "border-blue-300 bg-blue-50" : "border-slate-100 hover:bg-slate-50"}`}>
                        <span className="min-w-0"><span className="block text-xs font-medium text-slate-700">{titleCase(type)}</span>{amount && <span className="mt-0.5 block text-[10px] text-slate-400">Unmatched investigation amount: {money(amount.unmatched_amount_paise)}</span>}</span>
                        <span className="shrink-0 text-right text-[11px]"><span className="block text-slate-400">{number(counts.count)} total</span><strong className="text-slate-800">{number(counts.open_count)} open</strong></span>
                      </button>
                    );
                  })}
                </div>
              </Section>

              <Section title="Finance team workload" description="Open case load, SLA breaches and severity mix. Metrics follow the dashboard date and severity filters.">
                {dashboard.finance_workload.length ? (
                  <div className="space-y-2">
                    {dashboard.finance_workload.slice(0, 8).map((item) => (
                      <div key={item.user_id ?? "unassigned"} className="rounded-lg border border-slate-100 px-3 py-2.5">
                        <div className="flex items-start justify-between gap-3">
                          <div><div className="text-xs font-semibold text-slate-800">{item.user_name || (item.user_id ? `User #${item.user_id}` : "Unassigned")}</div><div className="mt-0.5 text-[10px] text-slate-400">{number(item.assigned_total)} assigned · {number(item.assigned_resolved_count)} resolved</div></div>
                          <div className="text-right"><div className="text-sm font-bold tabular-nums text-slate-900">{number(item.assigned_open)} open</div><div className={`text-[10px] font-semibold ${item.assigned_sla_overdue ? "text-rose-700" : "text-emerald-700"}`}>{number(item.assigned_sla_overdue)} SLA overdue</div></div>
                        </div>
                        <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                          <div className="flex flex-wrap gap-1">
                            {severityOptions.map((level) => <span key={level} className={`rounded px-1.5 py-0.5 text-[9px] ${item.open_by_severity[level] ? "bg-slate-100 text-slate-700" : "bg-slate-50 text-slate-300"}`}>{level[0]} {number(item.open_by_severity[level])}</span>)}
                          </div>
                          <span className="text-[9px] text-slate-400">Oldest open: {hours(item.oldest_open_age_hours)}</span>
                        </div>
                      </div>
                    ))}
                    {dashboard.resolved_by_user.length > 0 && (
                      <div className="mt-3 border-t border-slate-100 pt-3">
                        <div className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-slate-400">Resolved by</div>
                        <div className="flex flex-wrap gap-2">
                          {dashboard.resolved_by_user.slice(0, 6).map((item) => (
                            <span key={item.user_id ?? "unknown"} className="rounded-lg bg-emerald-50 px-2.5 py-1.5 text-[10px] text-emerald-800">
                              {item.user_name || (item.user_id ? `User #${item.user_id}` : "Unknown user")}: <strong>{number(item.resolved_count)}</strong>
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
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
                    <tr key={item.id} onClick={() => void openException(item)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); void openException(item); } }} tabIndex={0} role="button" aria-label={"Open investigation " + item.id} className="align-top cursor-pointer hover:bg-blue-50/60 focus:bg-blue-50 focus:outline-none">
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


        {selectedException && (
          <div className="fixed inset-0 z-50 flex justify-end bg-slate-950/40" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !actionLoading) { selectedExceptionIdRef.current = null; setSelectedException(null); } }}>
            <aside role="dialog" aria-modal="true" aria-labelledby="exception-drawer-title" className="flex h-full w-full max-w-2xl flex-col overflow-hidden bg-white shadow-2xl">
              <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-5 py-4">
                <div><div className="flex flex-wrap items-center gap-2"><Badge variant={severityVariant(selectedException.severity)} size="sm">{selectedException.severity}</Badge><Badge variant={statusVariant(selectedException.status)} size="sm">{titleCase(selectedException.status)}</Badge></div>
                  <h2 id="exception-drawer-title" className="mt-2 text-base font-bold text-slate-900">{titleCase(selectedException.exception_type)} <span className="text-slate-400">#{selectedException.id}</span></h2>
                  <p className="mt-1 text-xs text-slate-500">{selectedException.reference_type} #{selectedException.reference_id}</p></div>
                <div className="flex shrink-0 items-center gap-2">
                  <button type="button" onClick={() => void exportInvestigationAudit()} disabled={auditExporting || !hasPermission("finance.view_reconciliation")} className="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-700 disabled:opacity-50">{auditExporting ? "Preparing ZIP…" : "Export audit ZIP"}</button>
                  <button type="button" onClick={() => { selectedExceptionIdRef.current = null; setSelectedException(null); }} disabled={actionLoading || auditExporting} className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600">Close</button>
                </div>
              </div>
              <div className="flex-1 space-y-4 overflow-y-auto p-5">
                {detailError && <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">{detailError}</div>}
                {detailMessage && <div role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-800">{detailMessage}</div>}
                {selectedException.status !== "RESOLVED" && selectedException.status !== "DISMISSED" && (
                  <section className="rounded-xl border border-slate-200 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <h3 className="text-xs font-bold text-slate-800">SLA clock</h3>
                        <p className="mt-1 text-[10px] text-slate-500">
                          {selectedException.sla_paused
                            ? `Paused since ${selectedException.sla_paused_at ? new Date(selectedException.sla_paused_at).toLocaleString() : "—"}`
                            : `${hours(selectedException.sla_remaining_hours)} remaining · active clock`}
                        </p>
                      </div>
                      <Badge variant={selectedException.sla_paused ? "warning" : selectedException.sla_overdue ? "danger" : "success"}>
                        {selectedException.sla_paused ? "Paused" : selectedException.sla_overdue ? "Breached" : "Running"}
                      </Badge>
                    </div>
                    <div className="mt-2 grid grid-cols-2 gap-2 text-[10px]">
                      <div className="rounded-lg bg-slate-50 p-2"><span className="text-slate-500">Active elapsed</span><strong className="mt-0.5 block text-slate-800">{hours(selectedException.sla_elapsed_hours)}</strong></div>
                      <div className="rounded-lg bg-slate-50 p-2"><span className="text-slate-500">Total paused</span><strong className="mt-0.5 block text-slate-800">{hours((selectedException.sla_paused_seconds || 0) / 3600)}</strong></div>
                    </div>
                    {selectedException.sla_breached_at && <p className="mt-2 text-[10px] text-rose-700">First breach: {new Date(selectedException.sla_breached_at).toLocaleString()}</p>}
                    {hasPermission("finance.manage_sla_policies") && (
                      <div className="mt-3 space-y-2">
                        {selectedException.sla_paused ? (
                          <>
                            <textarea value={slaResumeReason} onChange={(event) => setSlaResumeReason(event.target.value)} rows={2} maxLength={2000} placeholder="Reason for resuming the SLA clock (minimum 10 characters)" className="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs" />
                            <div className="flex justify-end"><Button size="sm" onClick={() => void resumeSelectedSla()} disabled={actionLoading || slaResumeReason.trim().length < 10}>Resume SLA clock</Button></div>
                          </>
                        ) : (
                          <>
                            <textarea value={slaPauseReason} onChange={(event) => setSlaPauseReason(event.target.value)} rows={2} maxLength={2000} placeholder="Reason for pausing the SLA clock (minimum 10 characters)" className="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs" />
                            <div className="flex justify-end"><Button size="sm" variant="secondary" onClick={() => void pauseSelectedSla()} disabled={actionLoading || slaPauseReason.trim().length < 10}>Pause SLA clock</Button></div>
                          </>
                        )}
                      </div>
                    )}
                    <p className="mt-2 text-[9px] text-slate-400">SLA clock controls require SLA governance permission and a recorded reason. Closing an investigation automatically ends an active pause.</p>
                  </section>
                )}
                <section className="rounded-xl border border-slate-200 p-3">
                  <h3 className="text-xs font-bold text-slate-800">Detection summary</h3><p className="mt-2 text-xs leading-relaxed text-slate-600">{selectedException.summary}</p>
                  <div className="mt-3 grid grid-cols-2 gap-3 text-[11px]">
                    <div><span className="text-slate-400">Investigation amount</span><div className="font-semibold">{money(selectedException.amount_paise)}</div></div>
                    <div><span className="text-slate-400">Unmatched amount</span><div className="font-semibold">{money(selectedException.unmatched_amount_paise)}</div></div>
                    <div><span className="text-slate-400">Age / SLA</span><div className="font-semibold">{hours(selectedException.age_hours)} / {hours(selectedException.sla_hours)}</div></div>
                    <div><span className="text-slate-400">Latest source check</span><div className="font-semibold">{selectedException.source_present ? "Present" : "Missing (" + selectedException.missed_refresh_count + " scans)"}</div></div>
                    <div><span className="text-slate-400">First detected</span><div>{new Date(selectedException.first_detected_at).toLocaleString()}</div></div>
                    <div><span className="text-slate-400">Last detected</span><div>{new Date(selectedException.last_detected_at).toLocaleString()}</div></div>
                  </div>
                  <p className="mt-3 rounded-lg bg-amber-50 p-2 text-[10px] text-amber-800">Investigation values are not confirmed losses. Bank-side and supplier-payment exposures must not be added together.</p>
                </section>
                <section className="rounded-xl border border-slate-200 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div><h3 className="text-xs font-bold">Investigation evidence files</h3><p className="mt-1 text-[10px] text-slate-500">Private tenant storage · PDF, PNG or JPEG · malware scanned before publication</p></div>
                    <Badge variant="neutral" size="sm">{evidence.length} files</Badge>
                  </div>
                  {evidenceLoading ? <p className="py-3 text-xs text-slate-400">Loading evidence register…</p> : evidence.length ? (
                    <div className="mt-3 divide-y divide-slate-100 rounded-lg border border-slate-100">
                      {evidence.map((item) => (
                        <div key={item.id} className="flex items-center justify-between gap-3 p-3">
                          <div className="min-w-0">
                            <div className="truncate text-xs font-semibold text-slate-800">{item.original_filename}</div>
                            <div className="mt-0.5 text-[10px] text-slate-500">{titleCase(item.evidence_type)} · {(item.size_bytes / 1024).toFixed(1)} KB · {new Date(item.uploaded_at).toLocaleString()}</div>
                            {item.description && <p className="mt-1 break-words text-[10px] text-slate-500">{item.description}</p>}
                            <p className="mt-1 break-all font-mono text-[9px] text-slate-400">SHA-256: {item.sha256_hex}</p>
                          </div>
                          <Button size="sm" variant="secondary" onClick={() => void downloadInvestigationEvidence(item)} disabled={!hasPermission("finance.view_reconciliation")}>Download</Button>
                        </div>
                      ))}
                    </div>
                  ) : <p className="py-3 text-xs text-slate-400">No supporting files have been attached to this investigation.</p>}
                  {selectedException.status !== "RESOLVED" && selectedException.status !== "DISMISSED" && (
                    <div className="mt-3 space-y-2 border-t border-slate-100 pt-3">
                      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                        <label className="text-[10px] font-semibold text-slate-600">Evidence category
                          <select value={evidenceType} onChange={(event) => setEvidenceType(event.target.value as ReconciliationEvidence["evidence_type"])} disabled={!hasPermission("finance.manage_reconciliation") || evidenceUploading} className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs">
                            <option value="BANK_STATEMENT">Bank statement</option>
                            <option value="PAYMENT_PROOF">Payment proof</option>
                            <option value="INVOICE">Invoice</option>
                            <option value="SUPPLIER_CORRESPONDENCE">Supplier correspondence</option>
                            <option value="APPROVAL_RECORD">Approval record</option>
                            <option value="OTHER">Other</option>
                          </select>
                        </label>
                        <label className="text-[10px] font-semibold text-slate-600">Supporting file
                          <input type="file" accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg" onChange={(event) => setEvidenceFile(event.target.files?.[0] || null)} disabled={!hasPermission("finance.manage_reconciliation") || evidenceUploading} className="mt-1 block w-full text-[10px] text-slate-600 file:mr-2 file:rounded-lg file:border-0 file:bg-slate-100 file:px-2 file:py-2 file:text-[10px] file:font-semibold" />
                        </label>
                      </div>
                      <label className="block text-[10px] font-semibold text-slate-600">Description (optional)
                        <input value={evidenceDescription} onChange={(event) => setEvidenceDescription(event.target.value)} maxLength={500} placeholder="What does this evidence demonstrate?" disabled={!hasPermission("finance.manage_reconciliation") || evidenceUploading} className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-xs" />
                      </label>
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate text-[10px] text-slate-400">{evidenceFile ? evidenceFile.name + " · " + (evidenceFile.size / 1024).toFixed(1) + " KB" : "No file selected"}</span>
                        <Button size="sm" onClick={() => void uploadInvestigationEvidence()} disabled={!hasPermission("finance.manage_reconciliation") || !evidenceFile || evidenceUploading}>{evidenceUploading ? "Scanning and uploading…" : "Attach evidence"}</Button>
                      </div>
                    </div>
                  )}
                  {(selectedException.status === "RESOLVED" || selectedException.status === "DISMISSED") && <p className="mt-3 text-[10px] text-slate-500">This investigation is closed. Reopen it before adding further evidence.</p>}
                </section>
                <section className="rounded-xl border border-slate-200 p-3"><h3 className="text-xs font-bold">Detection evidence snapshot</h3><pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-slate-50 p-3 text-[10px]">{JSON.stringify(selectedException.detection_snapshot || {}, null, 2)}</pre></section>
                <section className="rounded-xl border border-slate-200 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div><h3 className="text-xs font-bold">Assignment recommendations</h3><p className="mt-1 text-[10px] text-slate-500">Advisory ranking based on branch workload, SLA pressure, severity fit, role permissions and historical outcomes.</p></div>
                    <Button size="sm" variant="secondary" onClick={() => void loadAssignmentRecommendations()} disabled={recommendationsLoading || selectedException.status === "RESOLVED" || selectedException.status === "DISMISSED"}>{recommendationsLoading ? "Calculating…" : recommendationsLoaded ? "Refresh suggestions" : "Suggest assignees"}</Button>
                  </div>
                  {recommendationsLoaded && (assignmentRecommendations.length ? (
                    <div className="mt-3 space-y-2">
                      {assignmentRecommendations.map((person, index) => (
                        <div key={person.user_id} className="rounded-lg border border-slate-100 p-3">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0"><div className="flex flex-wrap items-center gap-1.5"><span className="text-xs font-semibold text-slate-800">{person.user_name}</span>{index === 0 && <Badge variant="success" size="sm">Top recommendation</Badge>}{person.current_assignee && <Badge variant="info" size="sm">Current assignee</Badge>}{person.finance_suitable && <Badge variant="success" size="sm">Finance role</Badge>}{!person.finance_suitable && person.procurement_suitable && <Badge variant="warning" size="sm">Procurement role</Badge>}</div><div className="mt-0.5 text-[10px] text-slate-400">{person.login_id} · {person.roles.map((role) => role.name).join(", ") || "No role labels"}</div></div>
                            <div className="shrink-0 text-right"><div className="text-sm font-bold tabular-nums text-slate-900">{number(person.score)}/100</div><div className="text-[9px] text-slate-400">recommendation score</div></div>
                          </div>
                          <div className="mt-2 flex flex-wrap gap-1.5 text-[10px]"><span className="rounded bg-slate-50 px-2 py-1">{number(person.open_count)} open</span><span className={`rounded px-2 py-1 ${person.overdue_count ? "bg-rose-50 text-rose-700" : "bg-emerald-50 text-emerald-700"}`}>{number(person.overdue_count)} overdue</span><span className="rounded bg-slate-50 px-2 py-1">{number(person.open_by_severity[selectedException.severity])} {selectedException.severity} open</span><span className="rounded bg-slate-50 px-2 py-1">{number(person.resolved_count)} attributed resolved</span>{person.median_resolution_hours !== null && <span className="rounded bg-slate-50 px-2 py-1">Median resolution {hours(person.median_resolution_hours)}</span>}</div>
                          <ul className="mt-2 list-disc space-y-0.5 pl-4 text-[10px] text-slate-500">{person.reasons.map((reason, reasonIndex) => <li key={reasonIndex}>{reason}</li>)}</ul>
                          {!person.finance_suitable && !person.procurement_suitable && <p className="mt-2 text-[10px] font-medium text-amber-700">No finance or procurement permission was detected on this user's assigned roles. Confirm suitability before assigning.</p>}{!person.finance_suitable && person.procurement_suitable && <p className="mt-2 text-[10px] font-medium text-amber-700">Procurement permissions are present, but no finance permission was detected. Prefer a finance-qualified assignee when available.</p>}
                          <div className="mt-2 flex justify-end"><Button size="sm" variant="secondary" onClick={() => chooseRecommendedAssignee(person)} disabled={!hasPermission("finance.manage_reconciliation") || actionLoading || selectedException.status === "RESOLVED" || selectedException.status === "DISMISSED"}>Select this person</Button></div>
                        </div>
                      ))}
                    </div>
                  ) : <p className="mt-3 text-[10px] text-slate-400">No active branch staff were available for recommendation.</p>)}
                  <p className="mt-3 text-[9px] leading-relaxed text-slate-400">Suggestions are not assignments. Workload uses all persisted investigations in this branch, independent of dashboard date filters. Historical resolution statistics use resolved records still attributed to each assignee. Authorized staff must confirm every assignment.</p>
                </section>
                {user && selectedException.assigned_to_id === user.id && selectedException.status !== "RESOLVED" && selectedException.status !== "DISMISSED" && (() => {
                  const latestAssignment = [...history].reverse().find((event) => event.event_type === "ASSIGNED" && event.new_assignee_id === user.id);
                  const alreadyResponded = latestAssignment ? history.some((event) => event.id > latestAssignment.id && (event.event_type === "ASSIGNMENT_ACCEPTED" || event.event_type === "ASSIGNMENT_REJECTED")) : false;
                  const acknowledgement = latestAssignment ? (latestAssignment.event_metadata?.acknowledgement_status as string | undefined) || "PENDING" : "PENDING";
                  return latestAssignment && !alreadyResponded && acknowledgement === "PENDING" ? (
                    <section className="rounded-xl border border-blue-200 bg-blue-50 p-3">
                      <h3 className="text-xs font-bold text-blue-900">Your assignment requires acknowledgement</h3>
                      <p className="mt-1 text-[10px] text-blue-800">Accept responsibility for this investigation, or reject it with a reason so a manager can reassign it.</p>
                      <textarea value={assignmentResponseReason} onChange={(event) => setAssignmentResponseReason(event.target.value)} rows={2} maxLength={1000} placeholder="Reason (required when rejecting)" disabled={actionLoading} className="mt-2 w-full rounded-lg border border-blue-200 bg-white px-3 py-2 text-xs" />
                      <div className="mt-2 flex justify-end gap-2">
                        <Button size="sm" variant="outline" onClick={() => void respondToSelectedAssignment("REJECT")} disabled={actionLoading || assignmentResponseReason.trim().length < 10}>Reject assignment</Button>
                        <Button size="sm" onClick={() => void respondToSelectedAssignment("ACCEPT")} disabled={actionLoading}>Accept assignment</Button>
                      </div>
                    </section>
                  ) : null;
                })()}
                <section className="rounded-xl border border-slate-200 p-3">
                  <h3 className="text-xs font-bold">Assignment</h3>
                  <p className="mt-1 text-[10px] text-slate-500">Search active staff in this hospital branch. Results include their branch roles.</p>
                  <div className="mt-2">
                    <label htmlFor="reconciliation-assignee-search" className="mb-1 block text-[10px] font-semibold text-slate-600">Find branch staff</label>
                    <input id="reconciliation-assignee-search" role="combobox" aria-autocomplete="list" aria-expanded={assigneeOptions.length > 0} value={assigneeSearch} onChange={(event) => { setAssigneeSearch(event.target.value); setAssigneePickerOpen(true); }} placeholder="Search by staff name or login ID…" disabled={!hasPermission("finance.manage_reconciliation") || actionLoading} className="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs" />
                    {assigneeLoading && <p className="mt-2 text-[10px] text-slate-400">Searching branch directory…</p>}
                    {!assigneeLoading && assigneeSearch.trim() && assigneeOptions.length === 0 && <p className="mt-2 text-[10px] text-slate-400">No active staff matched this search.</p>}
                    {assigneePickerOpen && rankedAssigneeOptions.length > 0 && <ul role="listbox" aria-label="Active branch staff" className="mt-2 max-h-44 divide-y divide-slate-100 overflow-y-auto rounded-lg border border-slate-200">
                      {rankedAssigneeOptions.map((person, index) => {
                        const workload = dashboard?.finance_workload.find((item) => item.user_id === person.id);
                        return <li key={person.id}>
                          <button type="button" role="option" aria-selected={assigneeInput === String(person.id)} onClick={() => { setAssigneeInput(String(person.id)); setAssigneeSearch(person.full_name); setAssigneeOptions([]); setAssigneePickerOpen(false); }} disabled={actionLoading} className="flex w-full items-start justify-between gap-3 px-3 py-2 text-left hover:bg-blue-50 disabled:opacity-50">
                            <span className="min-w-0"><span className="block truncate text-xs font-semibold text-slate-800">{person.full_name}</span><span className="block text-[10px] text-slate-400">{person.login_id} · User #{person.id}</span><span className="mt-1 flex flex-wrap gap-1">{person.roles.length ? person.roles.map((role) => <span key={role.code} className="rounded bg-slate-100 px-1.5 py-0.5 text-[9px] text-slate-600">{role.name}</span>) : <span className="text-[9px] text-slate-400">No assigned role</span>}</span>
                              <span className="mt-1 block text-[10px] text-slate-500">{workload ? `${number(workload.assigned_open)} open · ${number(workload.assigned_sla_overdue)} overdue · oldest ${hours(workload.oldest_open_age_hours)}` : "No cases in current dashboard scope"}</span>{index === 0 && <span className="mt-1 inline-flex rounded bg-emerald-50 px-1.5 py-0.5 text-[9px] font-semibold text-emerald-700">Lowest current load</span>}</span>
                            {assigneeInput === String(person.id) && <CheckCircle2 size={15} className="mt-1 shrink-0 text-blue-600" />}
                          </button>
                        </li>;
                      })}
                    </ul>}
                  </div>
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-2">
                    <div><span className="block text-[9px] uppercase tracking-wide text-slate-400">Selected assignee</span><span className="text-xs font-semibold text-slate-700">{assigneeInput ? (assigneeOptions.find((person) => String(person.id) === assigneeInput)?.full_name || (assigneeSearch.trim() && !assigneeOptions.length ? assigneeSearch : "User #" + assigneeInput)) : "Unassigned"}</span></div>
                    <button type="button" onClick={() => { setAssigneeInput(""); setAssigneeSearch(""); setAssigneeOptions([]); setAssigneePickerOpen(false); }} disabled={!hasPermission("finance.manage_reconciliation") || actionLoading || !assigneeInput} className="text-[10px] font-semibold text-rose-700 disabled:text-slate-300">Clear assignment</button>
                  </div>
                  <div className="mt-2 grid gap-2 sm:grid-cols-[1fr_auto]">
                    <input aria-label="Assignment note" value={assignmentNote} onChange={(event) => setAssignmentNote(event.target.value)} placeholder={selectedException.assigned_to_id !== null && assigneeInput !== String(selectedException.assigned_to_id) ? "Reassignment reason (minimum 10 characters)" : "Optional assignment note"} disabled={!hasPermission("finance.manage_reconciliation") || actionLoading} className="rounded-lg border border-slate-200 px-3 py-2 text-xs" />
                    <Button size="sm" onClick={() => void saveAssignment()} disabled={!hasPermission("finance.manage_reconciliation") || actionLoading}>Save assignment</Button>
                  </div>
                </section>
                {statusChoice === "RESOLVED" && resolutionGuidance && (
                  <section className="rounded-xl border border-amber-200 bg-amber-50/50 p-3">
                    <h3 className="text-xs font-bold text-slate-900">Resolution evidence and root cause</h3>
                    <p className="mt-1 text-[10px] text-slate-600">{resolutionGuidance.resolution_policy}</p>
                    <select aria-label="Root cause" value={rootCauseCode} onChange={(event) => setRootCauseCode(event.target.value)} className="mt-3 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs">
                      <option value="">Select root cause</option>
                      {resolutionGuidance.root_cause_codes.map((code) => <option key={code} value={code}>{titleCase(code)}</option>)}
                    </select>
                    <div className="mt-3 space-y-2">
                      {resolutionGuidance.required_checklist.map((item) => (
                        <label key={item.code} className="flex items-start gap-2 text-[11px] text-slate-700">
                          <input type="checkbox" checked={resolutionChecklist[item.code] === true} onChange={(event) => setResolutionChecklist((current) => ({ ...current, [item.code]: event.target.checked }))} />
                          <span>{titleCase(item.code)}</span>
                        </label>
                      ))}
                    </div>
                    {resolutionGuidance.independent_review_required && <p className="mt-2 text-[10px] font-semibold text-amber-800">This severity requires an independent reviewer before closure.</p>}
                  </section>
                )}
                {(selectedException.status === "RESOLVED" || selectedException.status === "DISMISSED") && (
                  <section className="rounded-xl border border-slate-200 p-3">
                    <h3 className="text-xs font-bold">Reopen investigation</h3>
                    <p className="mt-1 text-[10px] text-slate-500">Reopening creates a new audit event and retains the previous resolution in history. Current reopen count: {selectedException.reopen_count || 0}.</p>
                    <textarea value={reopenReason} onChange={(event) => setReopenReason(event.target.value)} rows={2} maxLength={2000} placeholder="Why does this case need to be reopened? (minimum 10 characters)" className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 text-xs" />
                    <div className="mt-2 flex justify-end"><Button size="sm" onClick={() => void reopenSelectedException()} disabled={!hasPermission("finance.approve_reconciliation") || actionLoading}>Reopen investigation</Button></div>
                  </section>
                )}
                {selectedException.resolution_review_status === "PENDING" && selectedException.status === "IN_REVIEW" && (
                  <section className="rounded-xl border border-amber-300 bg-amber-50 p-3">
                    <h3 className="text-xs font-bold text-amber-900">Independent resolution review pending</h3>
                    <p className="mt-1 text-[10px] text-amber-800">The investigator submitted a resolution. A different user with finance approval permission must approve or reject it.</p>
                    <textarea value={resolutionReviewNote} onChange={(event) => setResolutionReviewNote(event.target.value)} rows={2} maxLength={2000} placeholder="Independent review findings (minimum 10 characters)" className="mt-2 w-full rounded-lg border border-amber-200 bg-white px-3 py-2 text-xs" />
                    <div className="mt-2 flex justify-end gap-2">
                      <Button size="sm" variant="outline" onClick={() => void reviewResolution("REJECT")} disabled={!hasPermission("finance.approve_reconciliation") || actionLoading}>Reject resolution</Button>
                      <Button size="sm" onClick={() => void reviewResolution("APPROVE")} disabled={!hasPermission("finance.approve_reconciliation") || actionLoading}>Approve resolution</Button>
                    </div>
                  </section>
                )}
                {selectedException.status !== "RESOLVED" && selectedException.status !== "DISMISSED" && selectedException.resolution_review_status !== "PENDING" && <section className="rounded-xl border border-slate-200 p-3">
                  <h3 className="text-xs font-bold">Reviewer action</h3><p className="mt-1 text-[10px] text-slate-500">Resolution and dismissal require a reason of at least 10 characters. Finance approval is enforced by the server.</p>
                  <div className="mt-2 grid gap-2 sm:grid-cols-[1fr_2fr]">
                    <select aria-label="New exception status" value={statusChoice} onChange={(event) => setStatusChoice(event.target.value as ReconciliationStatus)} disabled={!hasPermission("finance.approve_reconciliation") || actionLoading} className="rounded-lg border border-slate-200 px-3 py-2 text-xs">
                      {(["OPEN", "IN_REVIEW", "RESOLVED", "DISMISSED"] as ReconciliationStatus[]).filter((value) => value !== selectedException.status).map((value) => <option key={value} value={value}>{titleCase(value)}</option>)}
                    </select>
                    <input aria-label="Reviewer note" value={statusNote} onChange={(event) => setStatusNote(event.target.value)} placeholder="Reviewer / resolution reason" disabled={!hasPermission("finance.approve_reconciliation") || actionLoading} className="rounded-lg border border-slate-200 px-3 py-2 text-xs" />
                  </div>
                  <div className="mt-2 flex justify-end"><Button size="sm" onClick={() => void saveExceptionStatus()} disabled={!hasPermission("finance.approve_reconciliation") || actionLoading}>Apply status</Button></div>
                </section>}
                <section className="rounded-xl border border-slate-200 p-3">
                  <h3 className="text-xs font-bold">Add investigation note</h3><textarea value={investigationNote} onChange={(event) => setInvestigationNote(event.target.value)} rows={3} maxLength={4000} placeholder="Record findings, evidence references or follow-up..." disabled={!hasPermission("finance.manage_reconciliation") || actionLoading} className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 text-xs" />
                  <div className="mt-2 flex justify-end"><Button size="sm" onClick={() => void saveInvestigationNote()} disabled={!hasPermission("finance.manage_reconciliation") || actionLoading || !investigationNote.trim()}>Add note</Button></div>
                </section>
                <section className="rounded-xl border border-slate-200 p-3">
                  <div className="flex items-center justify-between"><h3 className="text-xs font-bold">Audit timeline</h3><button type="button" onClick={() => void refreshSelectedHistory(selectedException.id).catch((err) => setDetailError(err instanceof Error ? err.message : "Unable to refresh history."))} disabled={historyLoading || actionLoading} className="text-[10px] font-semibold text-blue-700">Refresh history</button></div>
                  {historyLoading ? <p className="py-4 text-xs text-slate-400">Loading history…</p> : history.length ? <ol className="mt-3 space-y-3">{history.map((event) => <li key={event.id} className="border-l-2 border-slate-200 pl-3">
                    <div className="flex flex-wrap justify-between gap-2"><span className="text-[11px] font-semibold">{titleCase(event.event_type)}</span><time className="text-[10px] text-slate-400">{new Date(event.occurred_at).toLocaleString()}</time></div>
                    <p className="mt-0.5 text-[10px] text-slate-500">Actor user #{event.actor_user_id ?? "unknown"}{event.old_status || event.new_status ? " · " + (event.old_status || "—") + " → " + (event.new_status || "—") : ""}{event.old_assignee_id !== null || event.new_assignee_id !== null ? " · assignee " + (event.old_assignee_id ?? "none") + " → " + (event.new_assignee_id ?? "none") : ""}</p>
                    {event.note && <p className="mt-1 whitespace-pre-wrap break-words text-xs">{event.note}</p>}
                    {event.event_metadata && Object.keys(event.event_metadata).length > 0 && <pre className="mt-1 whitespace-pre-wrap break-words text-[10px] text-slate-400">{JSON.stringify(event.event_metadata, null, 2)}</pre>}
                  </li>)}</ol> : <p className="py-4 text-xs text-slate-400">No history events have been recorded.</p>}
                </section>
              </div>
              <div className="border-t border-slate-200 px-5 py-3 text-[10px] text-slate-400">All changes are recorded in the append-only investigation history. Server-side permission and lifecycle rules apply.</div>
            </aside>
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-2 pb-2 text-[10px] text-slate-400">
          <span className="flex items-center gap-1.5"><CalendarDays size={12} /> Date basis: UTC first-detected date</span>
          <span>Dashboard is read-only. Status, assignment and resolution changes remain in the controlled investigation workflow.</span>
        </div>
      </div>
    </div>
  );
};

export default ProcurementReconciliationWorkspace;
