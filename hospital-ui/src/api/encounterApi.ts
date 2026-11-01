import { apiClient } from "./client";

export interface AppointmentStatusUpdatePayload {
  status: "SCHEDULED" | "ARRIVED" | "IN_CONSULTATION" | "COMPLETED" | "CANCELLED" | "NO_SHOW";
}

export interface ClinicalNotePayload {
  subjective: string;
  objective?: string;
  assessment: string;
  plan?: string;
}

export interface PrescriptionItemPayload {
  medication_id: number;
  dosage: string;
  frequency: string;
  duration_days: number;
  requested_quantity: number;
  instructions?: string;
}

export interface CreatePrescriptionPayload {
  encounter_id: number;
  items: PrescriptionItemPayload[];
}

export interface DiagnosticOrderPayload {
  patient_id: number;
  ordered_service_ids: number[];
  clinical_notes?: string;
}

export const encounterApi = {
  updateAppointmentStatus: async (
    appointmentId: number,
    status: AppointmentStatusUpdatePayload["status"]
  ) => {
    return apiClient(`/api/appointments/${appointmentId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
  },

  createClinicalNote: async (encounterId: number, note: ClinicalNotePayload) => {
    return apiClient(`/api/encounters/${encounterId}/notes`, {
      method: "POST",
      body: JSON.stringify(note),
    });
  },

  signClinicalNote: async (noteId: number) => {
    return apiClient(`/api/notes/${noteId}/sign`, {
      method: "PATCH",
    });
  },

  createPrescription: async (payload: CreatePrescriptionPayload) => {
    return apiClient("/api/prescriptions", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  createDiagnosticOrder: async (payload: DiagnosticOrderPayload) => {
    return apiClient("/api/orders", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};

