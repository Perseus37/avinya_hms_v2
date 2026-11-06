import { apiClient, apiClientBlob } from "./client";

export type ReconciliationStatus = "OPEN" | "IN_REVIEW" | "RESOLVED" | "DISMISSED";
export type ReconciliationSeverity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";

export interface ReconciliationDashboard {
  as_of: string;
  filters: {
    from_date: string | null;
    to_date: string | null;
    severity: ReconciliationSeverity | null;
    status: ReconciliationStatus | null;
    assigned_to_id: number | null;
    date_basis: string;
  };
  overview: {
    total_exceptions: number;
    open_count: number;
    in_review_count: number;
    resolved_count: number;
    dismissed_count: number;
    source_missing_open_count: number;
    unassigned_open_count: number;
    sla_breached_open_count: number;
    sla_paused_open_count: number;
  };
  by_status: Record<ReconciliationStatus, number>;
  by_severity: Record<ReconciliationSeverity, number>;
  by_exception_type: Record<string, { count: number; open_count: number; resolved_count: number }>;
  open_aging: Record<string, number>;
  sla_breaches_by_severity: Record<ReconciliationSeverity, number>;
  sla_breaches_by_detection_day: Array<{ date: string; breached_count: number }>;
  resolution_performance: {
    resolved_count: number;
    average_resolution_hours: number | null;
    median_resolution_hours: number | null;
    method: string;
  };
  daily_trend: Array<{ date: string; opened_count: number; resolved_count: number }>;
  finance_workload: Array<{
    user_id: number | null;
    user_name: string | null;
    assigned_total: number;
    assigned_open: number;
    assigned_resolved_count: number;
    assigned_sla_overdue: number;
    oldest_open_age_hours: number;
    open_by_severity: Record<ReconciliationSeverity, number>;
  }>;
  resolved_by_user: Array<{ user_id: number | null; user_name: string | null; resolved_count: number }>;
  investigation_amounts_by_exception_type: Record<string, {
    exception_count: number;
    open_count: number;
    investigation_amount_paise: number;
    unmatched_amount_paise: number;
  }>;
  investigation_amounts_by_supplier: Array<{
    vendor_id: number;
    vendor_name: string | null;
    exception_count: number;
    investigation_amount_paise: number;
    unmatched_amount_paise: number;
  }>;
  investigation_amounts_by_bank_account: Array<{
    bank_account_ref: string;
    exception_count: number;
    investigation_amount_paise: number;
    unmatched_amount_paise: number;
  }>;
  amount_methodology: {
    currency_unit: string;
    not_a_confirmed_loss: boolean;
    possible_duplicate_supplier_payment: string;
    no_cross_type_total: string;
  };
  controls: { read_only: boolean; persisted_snapshot_only: boolean };
}

export interface ReconciliationException {
  id: number;
  exception_type: string;
  severity: ReconciliationSeverity;
  status: ReconciliationStatus;
  reference_type: string;
  reference_id: number;
  source_present: boolean;
  missed_refresh_count: number;
  age_hours: number;
  sla_hours: number;
  sla_overdue: boolean;
  sla_elapsed_hours: number;
  sla_remaining_hours: number;
  sla_paused: boolean;
  sla_paused_at: string | null;
  sla_paused_seconds: number;
  sla_due_at: string | null;
  sla_breached_at: string | null;
  amount_paise: number;
  matched_amount_paise: number;
  unmatched_amount_paise: number;
  summary: string;
  assigned_to_id: number | null;
  first_detected_at: string;
  last_detected_at: string;
  resolved_at: string | null;
  resolution_note: string | null;
  root_cause_code?: string | null;
  resolution_checklist?: Record<string, boolean>;
  reopen_count?: number;
  resolution_review_status?: "NOT_REQUIRED" | "PENDING" | "APPROVED" | "REJECTED";
  detection_snapshot: Record<string, unknown>;
}

export interface ReconciliationQueue {
  total: number;
  sla_summary: {
    open_or_in_review: number;
    sla_overdue: number;
    sla_paused: number;
    unassigned_open: number;
    missing_from_latest_detection: number;
  };
  exceptions: ReconciliationException[];
}

export interface ReconciliationEvidence {
  id: number;
  exception_id: number;
  evidence_type: "BANK_STATEMENT" | "PAYMENT_PROOF" | "INVOICE" | "SUPPLIER_CORRESPONDENCE" | "APPROVAL_RECORD" | "OTHER";
  description: string | null;
  original_filename: string;
  media_type: string;
  size_bytes: number;
  sha256_hex: string;
  uploaded_by_id: number;
  uploaded_at: string;
  download_url?: string;
}

export interface ReconciliationResolutionGuidance {
  exception_id: number;
  exception_type: string;
  root_cause_codes: string[];
  required_checklist: Array<{ code: string; required: boolean }>;
  independent_review_required: boolean;
  resolution_policy: string;
}

export interface ReconciliationFilters {
  from_date?: string;
  to_date?: string;
  severity?: ReconciliationSeverity;
  status?: ReconciliationStatus;
  assigned_to_id?: number;
  exception_type?: string;
}

export const reconciliationApi = {
  getMyAssignments: (limit = 100) =>
    apiClient<MyReconciliationAssignments>("/api/procurement/reconciliation/my-assignments", { params: { limit } }),
  getDashboard: (filters: ReconciliationFilters = {}) =>
    apiClient<ReconciliationDashboard>("/api/procurement/analytics/reconciliation-dashboard", {
      params: { ...filters },
    }),
  getQueue: (filters: Pick<ReconciliationFilters, "severity" | "status" | "assigned_to_id" | "exception_type"> & { source_present?: boolean; sla_overdue?: boolean; unassigned_only?: boolean; open_only?: boolean } = {}) =>
    apiClient<ReconciliationQueue>("/api/procurement/reconciliation/exceptions/queue", {
      params: { ...filters },
    }),
  getAssignableUsers: (q = "", limit = 50) =>
    apiClient<ReconciliationAssigneeDirectory>("/api/procurement/reconciliation/assignees", {
      params: { q: q.trim() || undefined, limit },
    }),
  getAssignmentRecommendations: (id: number, limit = 5) =>
    apiClient<ReconciliationAssignmentRecommendations>("/api/procurement/reconciliation/exceptions/" + id + "/assignment-recommendations", {
      params: { limit },
    }),
  getAssignmentEscalations: (limit = 100) =>
    apiClient<ReconciliationAssignmentEscalationQueue>("/api/procurement/reconciliation/exceptions/escalations", {
      params: { limit },
    }),
  respondToAssignment: (id: number, payload: { decision: "ACCEPT" | "REJECT"; reason?: string }) =>
    apiClient<{ exception_id: number; decision: "ACCEPT" | "REJECT"; assigned_to_id: number | null; recorded: boolean }>("/api/procurement/reconciliation/exceptions/" + id + "/assignment-response", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getExceptionHistory: (id: number) =>
    apiClient<ReconciliationExceptionHistory>("/api/procurement/reconciliation/exceptions/" + id + "/history"),
  getEvidence: (id: number) =>
    apiClient<ReconciliationEvidence[]>("/api/procurement/reconciliation/exceptions/" + id + "/evidence"),
  uploadEvidence: (id: number, payload: FormData) =>
    apiClient<ReconciliationEvidence>("/api/procurement/reconciliation/exceptions/" + id + "/evidence", {
      method: "POST",
      body: payload,
    }),
  downloadEvidence: (id: number, evidenceId: number) =>
    apiClientBlob("/api/procurement/reconciliation/exceptions/" + id + "/evidence/" + evidenceId + "/download"),
  exportAuditPackage: (id: number) =>
    apiClientBlob("/api/procurement/reconciliation/exceptions/" + id + "/audit-export"),
  assignException: (id: number, payload: { assigned_to_id: number | null; note?: string }) =>
    apiClient<{ id: number; assigned_to_id: number | null; status: ReconciliationStatus; acknowledgement_status: string; notification_status?: "QUEUED" | "QUEUE_UNAVAILABLE" | "EMAIL_UNAVAILABLE" | "DISABLED_BY_POLICY" | "ASSIGNEE_EMAIL_UNAVAILABLE" | "NOT_REQUIRED" }>("/api/procurement/reconciliation/exceptions/" + id + "/assignment", { method: "PATCH", body: JSON.stringify(payload) }),
  getResolutionGuidance: (id: number) =>
    apiClient<ReconciliationResolutionGuidance>("/api/procurement/reconciliation/exceptions/" + id + "/resolution-guidance"),
  updateExceptionStatus: (id: number, payload: { status: ReconciliationStatus; note?: string; root_cause_code?: string; resolution_checklist?: Record<string, boolean> }) =>
    apiClient<{ id: number; status: ReconciliationStatus; resolved_at: string | null; resolution_note: string | null; root_cause_code?: string | null; resolution_checklist?: Record<string, boolean>; resolution_review_status?: "NOT_REQUIRED" | "PENDING" | "APPROVED" | "REJECTED" }>("/api/procurement/reconciliation/exceptions/" + id + "/status", { method: "PATCH", body: JSON.stringify(payload) }),
  reviewExceptionResolution: (id: number, payload: { decision: "APPROVE" | "REJECT"; note: string }) =>
    apiClient<{ id: number; status: ReconciliationStatus; resolution_review_status: "APPROVED" | "REJECTED"; resolved_at: string | null; resolved_by_id: number | null }>("/api/procurement/reconciliation/exceptions/" + id + "/resolution-review", { method: "PATCH", body: JSON.stringify(payload) }),
  reopenException: (id: number, payload: { reason: string }) =>
    apiClient<{ id: number; status: ReconciliationStatus; reopen_count: number }>("/api/procurement/reconciliation/exceptions/" + id + "/reopen", { method: "POST", body: JSON.stringify(payload) }),
  pauseSla: (id: number, payload: { reason: string }) =>
    apiClient<{ id: number; paused: boolean; sla_paused_at: string; sla_paused_seconds: number; sla_elapsed_hours: number; sla_remaining_hours: number; sla_overdue: boolean; sla_breached_at: string | null }>("/api/procurement/reconciliation/exceptions/" + id + "/sla/pause", { method: "POST", body: JSON.stringify(payload) }),
  resumeSla: (id: number, payload: { reason: string }) =>
    apiClient<{ id: number; paused: boolean; sla_paused_at: null; sla_paused_seconds: number; sla_elapsed_hours: number; sla_remaining_hours: number; sla_overdue: boolean; sla_breached_at: string | null }>("/api/procurement/reconciliation/exceptions/" + id + "/sla/resume", { method: "POST", body: JSON.stringify(payload) }),
  addExceptionNote: (id: number, payload: { note: string }) =>
    apiClient<{ exception_id: number; note_recorded: boolean }>("/api/procurement/reconciliation/exceptions/" + id + "/notes", { method: "POST", body: JSON.stringify(payload) }),
};


export interface MyReconciliationAssignment {
  id: number;
  exception_type: string;
  severity: ReconciliationSeverity;
  status: ReconciliationStatus;
  reference_type: string;
  summary: string;
  source_present: boolean;
  first_detected_at: string;
  assigned_at: string;
  acknowledgement_status: "PENDING" | "ACCEPTED" | "REJECTED";
  acknowledged_at: string | null;
  response_target_hours: number;
}

export interface MyReconciliationAssignments {
  total: number;
  items: MyReconciliationAssignment[];
  scope: "CURRENT_USER_ACTIVE_ASSIGNMENTS";
}

export interface ReconciliationExceptionEvent {
  id: number;
  event_type: string;
  actor_user_id: number | null;
  old_status: string | null;
  new_status: string | null;
  old_assignee_id: number | null;
  new_assignee_id: number | null;
  note: string | null;
  event_metadata: Record<string, unknown> | null;
  occurred_at: string;
}

export interface ReconciliationAssignee {
  id: number;
  full_name: string;
  login_id: string;
  roles: Array<{ code: string; name: string }>;
}

export interface ReconciliationAssigneeDirectory {
  items: ReconciliationAssignee[];
  count: number;
  limit: number;
}

export interface ReconciliationAssignmentRecommendation {
  user_id: number;
  user_name: string;
  login_id: string;
  roles: Array<{ code: string; name: string }>;
  finance_suitable: boolean;
  procurement_suitable: boolean;
  finance_permissions: string[];
  procurement_permissions: string[];
  current_assignee: boolean;
  open_count: number;
  overdue_count: number;
  open_by_severity: Record<ReconciliationSeverity, number>;
  resolved_count: number;
  median_resolution_hours: number | null;
  score: number;
  reasons: string[];
}

export interface ReconciliationAssignmentRecommendations {
  exception_id: number;
  target_severity: ReconciliationSeverity;
  current_assignee_id: number | null;
  recommendations: ReconciliationAssignmentRecommendation[];
  methodology: {
    manual_confirmation_required: boolean;
    workload_scope: string;
    historical_resolution_scope: string;
    role_suitability: string;
    score_weights: Record<string, number>;
    automatic_assignment: boolean;
  };
}

export interface ReconciliationAssignmentEscalation {
  exception_id: number;
  severity: ReconciliationSeverity;
  status: ReconciliationStatus;
  assigned_to_id: number;
  assigned_at: string;
  unacknowledged_hours: number;
  response_target_hours: number;
  escalation_due: boolean;
  escalation_levels_notified?: number;
  notification_jobs?: Array<{ job_id: string; queue_status: string; completed_at: string | null; delivery_result: { sent?: boolean; error?: string } | null; queue_error: string | null }>;
  delivery_semantics?: "QUEUE_STATUS_ONLY_NOT_MAILBOX_DELIVERY";
}

export interface ReconciliationAssignmentEscalationQueue {
  total: number;
  items: ReconciliationAssignmentEscalation[];
  automatic_escalation: boolean;
}

export interface ReconciliationExceptionHistory {
  exception_id: number;
  events: ReconciliationExceptionEvent[];
}


export interface ReconciliationSlaPolicy {
  id: number;
  policy_key: string;
  version: number;
  status: "DRAFT" | "PUBLISHED" | "RETIRED";
  severity_targets_hours: Record<ReconciliationSeverity, number>;
  change_reason: string;
  effective_from: string;
  effective_to: string | null;
  created_by_id: number;
  created_at: string;
  published_by_id: number | null;
  published_at: string | null;
}

export interface ReconciliationSlaPolicyDirectory {
  active_policy_id: number | null;
  active_policy_version: number | null;
  baseline_fallback: Record<ReconciliationSeverity, number>;
  items: ReconciliationSlaPolicy[];
}

export const reconciliationSlaPolicyApi = {
  list: () => apiClient<ReconciliationSlaPolicyDirectory>("/api/procurement/reconciliation/sla-policies"),
  createDraft: (payload: { severity_targets_hours: Record<ReconciliationSeverity, number>; change_reason: string }) =>
    apiClient<ReconciliationSlaPolicy>("/api/procurement/reconciliation/sla-policies", {
      method: "POST", body: JSON.stringify(payload),
    }),
  publish: (id: number) =>
    apiClient<ReconciliationSlaPolicy>(`/api/procurement/reconciliation/sla-policies/${id}/publish`, {
      method: "POST", body: JSON.stringify({}),
    }),
  events: (id: number) => apiClient<{ policy_id: number; events: ReconciliationSlaPolicyEvent[] }>(`/api/procurement/reconciliation/sla-policies/${id}/events`),
};


export interface ReconciliationSlaPolicyEvent {
  id: number;
  event_type: string;
  actor_user_id: number | null;
  event_metadata: Record<string, unknown>;
  occurred_at: string;
}



export interface ReconciliationEscalationPolicy {
  id: number;
  version: number;
  status: "DRAFT" | "PUBLISHED" | "RETIRED";
  response_targets_hours: Record<ReconciliationSeverity, number>;
  escalation_levels: Array<{ level: number; after_hours: number; notify_assignee: boolean; notify_assigning_manager: boolean; notify_finance_managers: boolean }>;
  notification_preferences: { email_enabled: boolean; assignee: boolean; assigning_manager: boolean; finance_managers: boolean };
  change_reason: string;
  effective_from: string;
  effective_to: string | null;
  created_at: string;
  published_at: string | null;
}
export interface ReconciliationGovernanceReport {
  id: number;
  period_start: string;
  period_end: string;
  snapshot: Record<string, unknown>;
  generated_by_id: number;
  created_at: string;
}
export interface ReconciliationAuditExport {
  id: number;
  exception_id: number | null;
  export_type: string;
  status: "GENERATED" | "FAILED" | "EXPIRED";
  file_sha256: string | null;
  file_size_bytes: number | null;
  filter_snapshot: Record<string, unknown>;
  actor_user_id: number;
  actor_email: string;
  requested_at: string;
}
export const reconciliationGovernanceApi = {
  escalationPolicies: () => apiClient<{ active_policy_id: number | null; active_policy_version: number | null; baseline_response_targets_hours: Record<ReconciliationSeverity, number>; items: ReconciliationEscalationPolicy[] }>("/api/procurement/reconciliation/escalation-policies"),
  createEscalationPolicy: (payload: { response_targets_hours: Record<ReconciliationSeverity, number>; escalation_levels: Array<{ after_hours: number; notify_assignee: boolean; notify_assigning_manager: boolean; notify_finance_managers: boolean }>; notification_preferences: { email_enabled: boolean; assignee: boolean; assigning_manager: boolean; finance_managers: boolean }; change_reason: string }) =>
    apiClient<{ id: number; version: number; status: string }>("/api/procurement/reconciliation/escalation-policies", { method: "POST", body: JSON.stringify(payload) }),
  publishEscalationPolicy: (id: number) =>
    apiClient<{ id: number; version: number; status: string }>("/api/procurement/reconciliation/escalation-policies/" + id + "/publish", { method: "POST", body: JSON.stringify({}) }),
  closureQuality: () => apiClient<Record<string, unknown>>("/api/procurement/reconciliation/governance/closure-quality"),
  dashboard: () => apiClient<Record<string, unknown>>("/api/procurement/reconciliation/governance/dashboard"),
  createMonthlyReport: (period_start: string, period_end: string) =>
    apiClient<ReconciliationGovernanceReport>("/api/procurement/reconciliation/governance/monthly-reports", { method: "POST", body: JSON.stringify({ period_start, period_end }) }),
  monthlyReports: () => apiClient<{ items: ReconciliationGovernanceReport[] }>("/api/procurement/reconciliation/governance/monthly-reports"),
  auditExports: () => apiClient<{ items: ReconciliationAuditExport[] }>("/api/procurement/reconciliation/audit-exports"),
};
