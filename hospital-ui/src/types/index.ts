export type WorkspaceId =
  | "overview"
  | "registration"
  | "patient-record"
  | "opd-queue"
  | "adt"
  | "doctor"
  | "nursing"
  | "triage"
  | "surgery"
  | "blood-bank"
  | "pharmacy"
  | "diagnostics"
  | "billing"
  | "procurement-reconciliation"
  | "infection-control"
  | "biomedical"
  | "admin";

export interface UserProfile {
  id: number;
  login_id: string;
  email: string;
  full_name: string;
  status: "ACTIVE" | "LOCKED" | "SUSPENDED";
  is_superuser: boolean;
  roles: Array<{
    id: number;
    code: string;
    name: string;
    permissions?: Array<{ code: string }>;
  }>;
}

export interface PatientQuickSearchItem {
  id: number;
  mrn: string;
  full_name: string;
  gender: string;
  date_of_birth?: string;
  age_years?: number;
  phone_number?: string;
  blood_group?: string;
  abha_number?: string;
}

export interface PatientSummaryCard {
  patient_id: number;
  mrn: string;
  full_name: string;
  gender: string;
  date_of_birth?: string;
  age_years?: number;
  phone_number?: string;
  blood_group?: string;
  registered_at?: string;
  active_admission?: {
    admission_id: number;
    admission_type: string;
    admitted_at?: string;
    ward_name?: string;
    room_number?: string;
    bed_number?: string;
    attending_doctor_name?: string;
  } | null;
  critical_allergies: Array<{
    id: number;
    allergen: string;
    allergy_type: string;
    severity: string;
    reaction?: string;
  }>;
  latest_vitals?: {
    vital_id: number;
    blood_pressure?: string;
    heart_rate_bpm?: number;
    respiratory_rate_bpm?: number;
    spo2_percent?: number;
    temperature_f?: number;
    news2_total_score?: number;
    news2_risk_level?: string;
    recorded_at?: string;
  } | null;
  active_diagnoses: Array<{
    id: number;
    code: string;
    description: string;
    diagnosis_type: string;
  }>;
}

export interface DoctorQueueSummary {
  doctor_id: number;
  doctor_name: string;
  queue_date: string;
  total_scheduled: number;
  checked_in: number;
  in_consultation: number;
  completed: number;
  cancelled: number;
  appointments: Array<{
    appointment_id: number;
    token_number: number;
    patient_id: number;
    patient_name: string;
    mrn?: string;
    gender?: string;
    age_years?: number;
    scheduled_time?: string;
    status: string;
    chief_complaint?: string;
    wait_minutes: number;
  }>;
}

export interface DetailedBedItem {
  bed_id: number;
  bed_number: string;
  room_id: number;
  room_number: string;
  status: "AVAILABLE" | "OCCUPIED" | "CLEANING" | "MAINTENANCE";
  occupied_details?: {
    admission_id: number;
    patient_id: number;
    patient_name: string;
    mrn: string;
    gender: string;
    age_years?: number;
    admitted_at?: string;
    attending_doctor_name?: string;
    news2_score?: number;
    news2_risk?: string;
  } | null;
}

export interface CashierShiftStatus {
  is_open: boolean;
  counter_id?: string;
  opened_at?: string;
  starting_float_paise: number;
  total_receipts_count: number;
  total_collected_paise: number;
  by_payment_method: Record<string, number>;
}

export interface PatientTimelineEvent {
  id: string;
  timestamp: string;
  date: string;
  time: string;
  category: "REGISTRATION" | "CLINICAL" | "TRIAGE" | "LAB" | "MEDICATION" | "ADMISSION" | "BILLING" | string;
  title: string;
  subtitle?: string;
  doctor_name?: string;
  department?: string;
  status?: string;
  severity?: "NORMAL" | "WARNING" | "CRITICAL" | "STAT" | string;
  details?: Record<string, any>;
}

export interface RevisitEligibility {
  patient_id: number;
  doctor_id: number;
  doctor_name: string;
  department: string;
  is_free_revisit: boolean;
  revisit_type: "FREE_REVISIT" | "PAID_FOLLOWUP" | "NEW_VISIT" | string;
  revisit_day_elapsed: number;
  grace_period_days: number;
  days_remaining: number;
  standard_fee_rupees: number;
  applicable_fee_rupees: number;
  last_consultation_date?: string | null;
  policy_summary: string;
}

export interface HardwarePrinterBackendConfig {
  id: string;
  name: string;
  location: string;
  connection_type: "NETWORK_IP" | "USB" | "WIFI" | "SYSTEM_DRIVER" | string;
  target_category: "WRISTBAND" | "THERMAL_TOKEN" | "CLINICAL_A4" | "LAB_LABEL" | string;
  protocol: "RAW_ZPL" | "RAW_ESCPOS" | "HTML_DRIVER" | string;
  ip_address?: string;
  port?: number;
  media_width_mm: number;
  media_height_mm: number;
  printable_width_mm?: number;
  printable_height_mm?: number;
  margin_top_mm?: number;
  margin_bottom_mm?: number;
  margin_left_mm?: number;
  margin_right_mm?: number;
  orientation?: "PORTRAIT" | "LANDSCAPE" | string;
  dpi?: number;
  status?: string;
  is_default?: boolean;
}
