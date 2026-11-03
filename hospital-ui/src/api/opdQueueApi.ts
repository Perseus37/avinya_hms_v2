import { apiClient } from "./client";

export type OPDQueueState =
  | "WAITING"
  | "CALLED"
  | "ARRIVED"
  | "IN_CONSULTATION"
  | "ON_HOLD"
  | "TRANSFERRED"
  | "NO_SHOW"
  | "COMPLETED";

export interface OPDQueueSummary {
  id: number;
  service_date: string;
  department_id: number;
  doctor_id: number;
  room_label: string | null;
  status: "OPEN" | "PAUSED" | "CLOSED";
  version: number;
}

export interface OPDQueueEntry {
  id: number;
  appointment_id: number;
  patient_id: number;
  token_number: number;
  queue_position: number;
  priority: number;
  state: OPDQueueState;
  version: number;
  checked_in_at: string;
  first_called_at: string | null;
}

export interface OPDQueueCommandResponse {
  queue_id: number;
  entry_id: number;
  token_number: number;
  state: OPDQueueState;
  queue_version: number;
  event_id: number;
  first_called_at: string | null;
  last_called_at: string | null;
}

export interface OPDQueueReason {
  reason_code: string;
  reason_note?: string;
}

export const opdQueueApi = {
  listQueues: (serviceDate?: string) =>
    apiClient<OPDQueueSummary[]>("/api/opd/queues", {
      params: { service_date: serviceDate },
    }),

  listEntries: (queueId: number) =>
    apiClient<OPDQueueEntry[]>(`/api/opd/queues/${queueId}/entries`),

  checkIn: (appointmentId: number, roomLabel?: string) =>
    apiClient<{ queue_id: number; entry_id: number; appointment_id: number; patient_id: number; token_number: number; queue_position: number; state: OPDQueueState; queue_version: number; event_id: number }>(
      "/api/opd/queues/check-in",
      {
        method: "POST",
        body: JSON.stringify({ appointment_id: appointmentId, room_label: roomLabel }),
      }
    ),

  callNext: (queueId: number) =>
    apiClient<OPDQueueCommandResponse>(`/api/opd/queues/${queueId}/call-next`, {
      method: "POST",
    }),

  callSpecific: (queueId: number, entryId: number, reason: OPDQueueReason, expectedVersion?: number) =>
    apiClient<OPDQueueCommandResponse>(
      `/api/opd/queues/${queueId}/entries/${entryId}/call`,
      {
        method: "POST",
        body: JSON.stringify({ ...reason, expected_version: expectedVersion }),
      }
    ),

  repeatCall: (queueId: number, entryId: number) =>
    apiClient<OPDQueueCommandResponse>(
      `/api/opd/queues/${queueId}/entries/${entryId}/repeat-call`,
      { method: "POST" }
    ),

  markArrived: (queueId: number, entryId: number) =>
    apiClient<OPDQueueCommandResponse>(
      `/api/opd/queues/${queueId}/entries/${entryId}/arrive`,
      { method: "POST" }
    ),

  hold: (queueId: number, entryId: number, reason: OPDQueueReason) =>
    apiClient<OPDQueueCommandResponse>(
      `/api/opd/queues/${queueId}/entries/${entryId}/hold`,
      { method: "POST", body: JSON.stringify(reason) }
    ),

  releaseHold: (queueId: number, entryId: number) =>
    apiClient<OPDQueueCommandResponse>(
      `/api/opd/queues/${queueId}/entries/${entryId}/release-hold`,
      { method: "POST" }
    ),

  markNoShow: (queueId: number, entryId: number, reason: OPDQueueReason) =>
    apiClient<OPDQueueCommandResponse>(
      `/api/opd/queues/${queueId}/entries/${entryId}/no-show`,
      { method: "POST", body: JSON.stringify(reason) }
    ),

  startConsultation: (queueId: number, entryId: number, encounterId: number, reason?: string) =>
    apiClient<OPDQueueCommandResponse>(
      `/api/opd/queues/${queueId}/entries/${entryId}/start-consultation`,
      {
        method: "POST",
        body: JSON.stringify({ encounter_id: encounterId, reason }),
      }
    ),

  completeConsultation: (queueId: number, entryId: number, reason: OPDQueueReason) =>
    apiClient<OPDQueueCommandResponse>(
      `/api/opd/queues/${queueId}/entries/${entryId}/complete-consultation`,
      { method: "POST", body: JSON.stringify(reason) }
    ),
};
