import { apiClient } from "./client";

export interface PatientCreatePayload {
  mrn?: string;
  full_name: string;
  date_of_birth: string; // ISO String YYYY-MM-DDTHH:MM:SS
  gender: "MALE" | "FEMALE" | "OTHER";
  phone_number?: string;
  abha_number?: string;
  email?: string;
  blood_group?: "A+" | "A-" | "B+" | "B-" | "AB+" | "AB-" | "O+" | "O-";
  address?: string;
  pincode?: string;
  city?: string;
  district?: string;
  state?: string;
  village?: string;
  emergency_contact_name?: string;
  emergency_contact_phone?: string;
  allow_network_sharing?: boolean;
}

export interface PatientCreatedResponse {
  id: number;
  mrn: string;
  full_name: string;
  date_of_birth: string;
  gender: string;
  phone_number?: string;
  abha_number?: string;
  blood_group?: string;
  address?: string;
  city?: string;
  state?: string;
  pincode?: string;
}

export interface PincodeSuggestion {
  pincode: string;
  suggestions: Array<{
    name: string;
    branch_type: string;
    delivery_status: string;
    circle: string;
    district: string;
    division: string;
    region: string;
    block: string;
    state: string;
    country: string;
  }>;
}

export const patientApi = {
  createPatient: async (payload: PatientCreatePayload): Promise<PatientCreatedResponse> => {
    return apiClient<PatientCreatedResponse>("/api/patients", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listPatients: async (search?: string, page: number = 1): Promise<{ items: PatientCreatedResponse[]; total: number }> => {
    return apiClient<{ items: PatientCreatedResponse[]; total: number }>("/api/patients", {
      params: { search, page, page_size: 20 },
    });
  },

  getPincodeSuggestions: async (pincode: string): Promise<PincodeSuggestion> => {
    return apiClient<PincodeSuggestion>("/api/patients/pincode-suggestions", {
      params: { pincode },
    });
  },
};
