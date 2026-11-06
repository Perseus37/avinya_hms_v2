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
      params: filters,
    }),
  getQueue: (filters: Pick<ReconciliationFilters, "severity" | "status" | "assigned_to_id" | "exception_type"> = {}) =>
    apiClient<ReconciliationQueue>("/api/procurement/reconciliation/exceptions/queue", {
      params: filters,
    }),
};
