export type WorkspaceId =
  | "admin"
  | "doctor"
  | "triage"
  | "nursing"
  | "pharmacy"
  | "diagnostics"
  | "billing";

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
