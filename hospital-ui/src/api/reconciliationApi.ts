import { apiClient } from "./client";

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
  amount_paise: number;
  matched_amount_paise: number;
  unmatched_amount_paise: number;
  summary: string;
  assigned_to_id: number | null;
  first_detected_at: string;
  last_detected_at: string;
  resolved_at: string | null;
  resolution_note: string | null;
  detection_snapshot: Record<string, unknown>;
}

export interface ReconciliationQueue {
  total: number;
  sla_summary: {
    open_or_in_review: number;
    sla_overdue: number;
    unassigned_open: number;
    missing_from_latest_detection: number;
  };
  exceptions: ReconciliationException[];
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
  getExceptionHistory: (id: number) =>
    apiClient<ReconciliationExceptionHistory>("/api/procurement/reconciliation/exceptions/" + id + "/history"),
  assignException: (id: number, payload: { assigned_to_id: number | null; note?: string }) =>
    apiClient<{ id: number; assigned_to_id: number | null; status: ReconciliationStatus }>("/api/procurement/reconciliation/exceptions/" + id + "/assignment", { method: "PATCH", body: JSON.stringify(payload) }),
  updateExceptionStatus: (id: number, payload: { status: ReconciliationStatus; note?: string }) =>
    apiClient<{ id: number; status: ReconciliationStatus; resolved_at: string | null; resolution_note: string | null }>("/api/procurement/reconciliation/exceptions/" + id + "/status", { method: "PATCH", body: JSON.stringify(payload) }),
  addExceptionNote: (id: number, payload: { note: string }) =>
    apiClient<{ exception_id: number; note_recorded: boolean }>("/api/procurement/reconciliation/exceptions/" + id + "/notes", { method: "POST", body: JSON.stringify(payload) }),
};


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
  finance_permissions: string[];
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

export interface ReconciliationExceptionHistory {
  exception_id: number;
  events: ReconciliationExceptionEvent[];
}
