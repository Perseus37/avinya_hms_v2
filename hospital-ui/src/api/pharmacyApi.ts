import { apiClient } from "./client";

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Medication {
  id: number;
  code: string;
  brand_name: string;
  generic_name: string;
  form: string;
  strength: string;
  is_controlled_substance: boolean;
  ndc_or_barcode?: string | null;
  is_active: boolean;
}

export interface InventoryBatch {
  id: number;
  medication_id: number;
  batch_number: string;
  expiry_date: string;
  stock_quantity: number;
  unit_price_paise: number;
  medication: Medication;
}

export interface PrescriptionItem {
  id: number;
  medication_id: number;
  dosage_instruction: string;
  requested_quantity: number;
  dispensed_quantity: number;
  medication: Medication;
}

export interface Prescription {
  id: number;
  encounter_id: number;
  prescribing_doctor_id: number;
  status: "ACTIVE" | "PARTIAL" | "DISPENSED" | "CANCELLED";
  clinical_notes?: string | null;
  patient_name?: string | null;
  patient_mrn?: string | null;
  items: PrescriptionItem[];
}

export interface DispenseRequest {
  items: Array<{
    prescription_item_id: number;
    batch_id: number;
    quantity_to_dispense: number;
  }>;
}

export interface DispenseResult {
  status: string;
  prescription_status: string;
  billed_to_invoice: string;
}

export interface ControlledSubstanceVault {
  id: number;
  medication_id: number;
  vault_location: string;
  current_balance_units: number;
  unit_of_measure: string;
  tamper_seal_number?: string | null;
  is_locked: boolean;
  medication: Medication;
}

export interface ControlledSubstanceMovement {
  id: number;
  vault_id: number;
  movement_type: string;
  quantity_units: number;
  balance_before: number;
  balance_after: number;
  encounter_id?: number | null;
  prescription_item_id?: number | null;
  primary_user_id: number;
  witness_user_id?: number | null;
  witness_verified: boolean;
  wastage_reason?: string | null;
  disposal_method?: string | null;
  batch_number?: string | null;
  notes?: string | null;
  created_at: string;
}

export const pharmacyApi = {
  listPrescriptions: (status: "ACTIVE" | "PARTIAL") =>
    apiClient<Page<Prescription>>("/api/pharmacy/prescriptions", {
      params: { status_filter: status, page: 1, page_size: 50 },
    }),

  listInventoryBatches: (medicationId?: number) =>
    apiClient<Page<InventoryBatch>>("/api/pharmacy/inventory/batches", {
      params: { medication_id: medicationId, include_depleted: false, page: 1, page_size: 50 },
    }),

  dispensePrescription: (prescriptionId: number, payload: DispenseRequest) =>
    apiClient<DispenseResult>(`/api/pharmacy/prescriptions/${prescriptionId}/dispense`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listControlledSubstanceVaults: () =>
    apiClient<ControlledSubstanceVault[]>("/api/pharmacy/controlled-substances/vault"),

  listControlledSubstanceMovements: (vaultId?: number) =>
    apiClient<ControlledSubstanceMovement[]>("/api/pharmacy/controlled-substances/movements", {
      params: { vault_id: vaultId },
    }),
};
