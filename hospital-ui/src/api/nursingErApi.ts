import { apiClient } from "./client";

export interface EmarAdministrationPayload {
  prescription_item_id: number;
  administered_dose: string;
  route: string;
  notes?: string;
  witness_user_id?: number;
}

export interface FluidLogPayload {
  direction: "INTAKE" | "OUTPUT";
  fluid_type: string;
  volume_ml: number;
  notes?: string;
}

export interface ErTriagePayload {
  acuity_level: "RED_RESUSCITATION" | "ORANGE_EMERGENT" | "YELLOW_URGENT" | "GREEN_LESS_URGENT" | "BLUE_NON_URGENT";
  chief_complaint: string;
  systolic_bp?: number;
  diastolic_bp?: number;
  pulse_rate_bpm?: number;
  respiratory_rate_bpm?: number;
  spo2_percent?: number;
  temperature_celsius?: number;
  gcs_score?: number;
  pain_score_10?: number;
}

export interface MlcCreatePayload {
  encounter_id: number;
  cause_of_injury: string;
  alleged_history: string;
  identification_marks?: string;
  brought_by_name?: string;
  brought_by_relation?: string;
  brought_by_phone?: string;
  police_station_name?: string;
  police_constable_buckle_no?: string;
}

export interface MlcPoliceIntimationPayload {
  police_constable_buckle_no: string;
  police_station_name?: string;
}

export const nursingErApi = {
  recordEmarAdministration: async (encounterId: number, payload: EmarAdministrationPayload) => {
    return apiClient(`/api/nursing/encounters/${encounterId}/emar`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listEmarLogs: async (encounterId: number) => {
    return apiClient(`/api/nursing/encounters/${encounterId}/emar`);
  },

  recordFluidBalanceLog: async (encounterId: number, payload: FluidLogPayload) => {
    return apiClient(`/api/nursing/encounters/${encounterId}/fluid-logs`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getFluidBalanceSummary: async (encounterId: number) => {
    return apiClient(`/api/nursing/encounters/${encounterId}/fluid-balance`);
  },

  recordErTriageAssessment: async (encounterId: number, payload: ErTriagePayload) => {
    return apiClient(`/api/er/encounters/${encounterId}/triage`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  registerMlc: async (payload: MlcCreatePayload) => {
    return apiClient("/api/er/mlc", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  recordMlcPoliceIntimation: async (mlcId: number, payload: MlcPoliceIntimationPayload) => {
    return apiClient(`/api/er/mlc/${mlcId}/police-intimation`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
};
