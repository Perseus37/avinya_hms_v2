import { apiClient } from "./client";
import {
  PatientQuickSearchItem,
  PatientSummaryCard,
  DoctorQueueSummary,
  DetailedBedItem,
  CashierShiftStatus,
  PatientTimelineEvent,
  RevisitEligibility,
  HardwarePrinterBackendConfig,
} from "../types";

export interface TenantBranding {
  tenant_slug: string;
  hospital_name: string;
  display_name: string;
  logo_url: string | null;
  favicon_url: string | null;
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  tagline: string | null;
}

export const uiApi = {
  getTenantBranding: async (): Promise<TenantBranding> => {
    return apiClient<TenantBranding>("/api/ui/tenant-branding");
  },
  quickSearchPatients: async (query: string, limit = 10): Promise<PatientQuickSearchItem[]> => {
    if (!query || query.trim().length === 0) return [];
    return apiClient<PatientQuickSearchItem[]>("/api/ui/patients/quick-search", {
      params: { q: query.trim(), limit },
    });
  },

  getPatientSummary: async (patientId: number): Promise<PatientSummaryCard> => {
    return apiClient<PatientSummaryCard>(`/api/ui/patients/${patientId}/summary-card`);
  },

  getDoctorQueueToday: async (doctorId?: number): Promise<DoctorQueueSummary> => {
    return apiClient<DoctorQueueSummary>("/api/ui/doctor/queue-today", {
      params: { doctor_id: doctorId },
    });
  },

  getWardBedMap: async (wardId: number): Promise<DetailedBedItem[]> => {
    return apiClient<DetailedBedItem[]>(`/api/ui/wards/${wardId}/bed-map-detailed`);
  },

  getCashierShiftStatus: async (): Promise<CashierShiftStatus> => {
    return apiClient<CashierShiftStatus>("/api/ui/billing/shift-status");
  },

  openCashierShift: async (counterId: string, startingFloatPaise = 0) => {
    return apiClient("/api/ui/billing/shifts/open", {
      method: "POST",
      body: JSON.stringify({ counter_id: counterId, starting_float_paise: startingFloatPaise }),
    });
  },

  closeCashierShift: async (physicalCashCountedPaise: number, handoverNotes?: string) => {
    return apiClient("/api/ui/billing/shifts/close", {
      method: "POST",
      body: JSON.stringify({
        physical_cash_counted_paise: physicalCashCountedPaise,
        handover_notes: handoverNotes,
      }),
    });
  },

  getOpdQueueSummary: async (queueDate?: string) => {
    return apiClient<any>("/api/ui/opd/queue-summary", {
      params: { queue_date: queueDate },
    });
  },

  getDischargePipeline: async () => {
    return apiClient<any[]>("/api/ui/admissions/discharge-pipeline");
  },

  getMyWorkTasks: async () => {
    return apiClient<any[]>("/api/ui/tasks/my-work");
  },

  getPatientTimeline: async (patientId: number): Promise<PatientTimelineEvent[]> => {
    return apiClient<PatientTimelineEvent[]>(`/api/ui/patients/${patientId}/timeline`);
  },

  getRevisitEligibility: async (patientId: number, doctorId: number): Promise<RevisitEligibility> => {
    return apiClient<RevisitEligibility>(`/api/ui/patients/${patientId}/revisit-eligibility`, {
      params: { doctor_id: doctorId },
    });
  },

  getFacilityPrinters: async (): Promise<HardwarePrinterBackendConfig[]> => {
    return apiClient<HardwarePrinterBackendConfig[]>("/api/ui/facility/printers");
  },

  saveFacilityPrinters: async (
    printers: HardwarePrinterBackendConfig[]
  ): Promise<HardwarePrinterBackendConfig[]> => {
    return apiClient<HardwarePrinterBackendConfig[]>("/api/ui/facility/printers", {
      method: "POST",
      body: JSON.stringify(printers),
    });
  },
};

