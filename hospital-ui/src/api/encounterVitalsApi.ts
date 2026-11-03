import { apiClient } from "./client";

export interface EncounterVital {
  id: number;
  encounter_id: number;
  temperature_f: number | null;
  pulse_bpm: number | null;
  bp_systolic: number | null;
  bp_diastolic: number | null;
  respiratory_rate: number | null;
  spo2_percent: number | null;
  weight_kg: number | null;
  height_cm: number | null;
  bmi: number | null;
  notes: string | null;
  created_by_id: number | null;
  created_at: string;
}

export interface EncounterVitalInput {
  temperature_f?: number | null;
  pulse_bpm?: number | null;
  bp_systolic?: number | null;
  bp_diastolic?: number | null;
  respiratory_rate?: number | null;
  spo2_percent?: number | null;
  weight_kg?: number | null;
  height_cm?: number | null;
  notes?: string | null;
}

export const encounterVitalsApi = {
  list: (encounterId: number) =>
    apiClient<EncounterVital[]>(`/api/clinical/encounters/${encounterId}/vitals`),

  record: (encounterId: number, observation: EncounterVitalInput) =>
    apiClient<EncounterVital>(`/api/clinical/encounters/${encounterId}/vitals`, {
      method: "POST",
      body: JSON.stringify(observation),
    }),
};
