import { apiClient } from "./client";
import {
  PatientQuickSearchItem,
  PatientSummaryCard,
  DoctorQueueSummary,
  DetailedBedItem,
  CashierShiftStatus,
} from "../types";

export const uiApi = {
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
};

