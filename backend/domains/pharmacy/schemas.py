"""Pydantic schemas owned by the Avinya HMS domain."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from backend.domains.pharmacy.models import MedicationFormEnum, PrescriptionStatusEnum, InventoryTransferStatusEnum

class MedicationMasterCreate(BaseModel):
    code: str
    brand_name: str
    generic_name: str
    form: MedicationFormEnum
    strength: str
    is_controlled_substance: bool = False
    ndc_or_barcode: Optional[str] = None
    low_stock_threshold_units: Optional[int] = Field(default=None, ge=0)
    fefo_expiry_warning_days: Optional[int] = Field(default=None, ge=1, le=365)

class MedicationMasterUpdate(BaseModel):
    brand_name: Optional[str] = None
    generic_name: Optional[str] = None
    form: Optional[MedicationFormEnum] = None
    dosage_form: Optional[MedicationFormEnum] = None
    strength: Optional[str] = None
    is_controlled_substance: Optional[bool] = None
    ndc_or_barcode: Optional[str] = None
    is_active: Optional[bool] = None
    low_stock_threshold_units: Optional[int] = Field(default=None, ge=0)
    fefo_expiry_warning_days: Optional[int] = Field(default=None, ge=1, le=365)

class MedicationMasterResponse(BaseModel):
    id: int
    code: str
    brand_name: str
    generic_name: str
    form: MedicationFormEnum
    strength: str
    is_controlled_substance: bool = False
    ndc_or_barcode: Optional[str] = None
    is_active: bool
    low_stock_threshold_units: Optional[int] = None
    fefo_expiry_warning_days: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

class PharmacyLocationCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)
    location_type: str = Field(default="STORE", min_length=2, max_length=30)


class PharmacyLocationAccessCreate(BaseModel):
    user_id: int


class PharmacyLocationResponse(BaseModel):
    id: int
    code: str
    name: str
    location_type: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class InventoryBatchCreate(BaseModel):
    medication_id: int
    location_id: Optional[int] = None
    batch_number: str
    expiry_date: datetime
    stock_quantity: int
    unit_price_paise: Decimal = Field(ge=0)

class InventoryBatchUpdate(BaseModel):
    batch_number: Optional[str] = None
    expiry_date: Optional[datetime] = None
    unit_price_paise: Optional[Decimal] = Field(default=None, ge=0)

class InventoryBatchResponse(BaseModel):
    id: int
    medication_id: int
    location_id: int
    batch_number: str
    expiry_date: datetime
    stock_quantity: int
    unit_price_paise: int
    medication: MedicationMasterResponse
    model_config = ConfigDict(from_attributes=True)

class InventoryMovementResponse(BaseModel):
    id: int
    location_id: int
    medication_id: int
    inventory_batch_id: int
    movement_type: str
    quantity_delta: int
    stock_before: int
    stock_after: int
    unit_price_paise: int
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    actor_id: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InventoryTransferCreate(BaseModel):
    source_batch_id: int
    destination_location_id: int
    quantity: int = Field(gt=0)
    notes: Optional[str] = Field(default=None, max_length=500)


class InventoryTransferResponse(BaseModel):
    id: int
    source_batch_id: int
    source_location_id: int
    medication_id: int
    batch_number: str
    expiry_date: datetime
    unit_price_paise: int
    destination_location_id: int
    quantity: int
    status: InventoryTransferStatusEnum
    requested_by_id: int
    approved_by_id: Optional[int] = None
    dispatched_by_id: Optional[int] = None
    received_by_id: Optional[int] = None
    received_batch_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    dispatched_at: Optional[datetime] = None
    received_at: Optional[datetime] = None
    notes: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class InventoryStockAdjustment(BaseModel):
    quantity_adjustment: int = Field(default=..., description="Must not be zero")
    reason: Optional[str] = Field(default=None, max_length=500)


class InventoryCountSessionCreate(BaseModel):
    location_id: int
    count_type: str = Field(default="CYCLE", pattern=r"^(CYCLE|FULL|SPOT)$")
    notes: Optional[str] = Field(default=None, max_length=500)


class InventoryCountLineEntry(BaseModel):
    physical_quantity: int = Field(ge=0)
    reason_code: Optional[str] = Field(default=None, max_length=40)
    notes: Optional[str] = Field(default=None, max_length=500)


class InventoryCountLineResponse(BaseModel):
    id: int
    inventory_batch_id: int
    medication_id: int
    batch_number: str
    expiry_date: datetime
    physical_quantity: Optional[int] = None
    counted_by_id: Optional[int] = None
    counted_at: Optional[datetime] = None
    variance: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class InventoryCountSessionResponse(BaseModel):
    id: int
    location_id: int
    count_type: str
    status: str
    created_by_id: int
    submitted_by_id: Optional[int] = None
    approved_by_id: Optional[int] = None
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    notes: Optional[str] = None
    lines: List[InventoryCountLineResponse] = []
    model_config = ConfigDict(from_attributes=True)


class ExpiryReportItem(BaseModel):
    batch_id: int
    location_id: int
    medication_id: int
    medication_name: str
    batch_number: str
    expiry_date: datetime
    stock_quantity: int
    days_to_expiry: int


class PrescriptionItemCreate(BaseModel):
    medication_id: int
    dosage_instruction: str
    requested_quantity: int

class PrescriptionCreate(BaseModel):
    encounter_id: int
    clinical_notes: Optional[str] = None
    items: List[PrescriptionItemCreate]
    override_ddi_warning: Optional[bool] = False
    ddi_override_justification: Optional[str] = None

class ClinicalDdiPrecheckRequest(BaseModel):
    patient_id: int
    medication_ids: List[int] = Field(min_length=1)

class ClinicalDdiPrecheckResponse(BaseModel):
    has_critical_hard_stop: bool
    has_critical_warning: bool
    findings: List[dict]

class PrescriptionUpdate(BaseModel):
    clinical_notes: Optional[str] = None
    status: Optional[PrescriptionStatusEnum] = None

class PrescriptionItemResponse(BaseModel):
    id: int
    medication_id: int
    dosage_instruction: str
    requested_quantity: int
    dispensed_quantity: int
    medication: MedicationMasterResponse
    model_config = ConfigDict(from_attributes=True)

class PrescriptionResponse(BaseModel):
    id: int
    encounter_id: int
    prescribing_doctor_id: int
    status: PrescriptionStatusEnum
    clinical_notes: Optional[str]
    items: List[PrescriptionItemResponse]
    model_config = ConfigDict(from_attributes=True)

class DispenseItem(BaseModel):
    prescription_item_id: int
    batch_id: int
    quantity_to_dispense: int = Field(gt=0, description="Cannot dispense negative or zero stock")

class PrescriptionDispenseRequest(BaseModel):
    items: List[DispenseItem]

class PharmacyReturnItem(BaseModel):
    prescription_item_id: int
    batch_id: int
    quantity_to_return: int = Field(gt=0)
    return_reason: str = Field(min_length=3, max_length=255)

class PharmacyReturnRequest(BaseModel):
    items: List[PharmacyReturnItem] = Field(min_length=1)

class PharmacyReturnLogResponse(BaseModel):
    id: int
    prescription_id: int
    prescription_item_id: int
    batch_id: int
    returned_by_id: int
    returned_quantity: int
    credit_amount_paise: int
    return_reason: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

MedicationCreate = MedicationMasterCreate
MedicationResponse = MedicationMasterResponse
MedicationUpdate = MedicationMasterUpdate
DispenseRequest = PrescriptionDispenseRequest


# -----------------------------------------------------------------------------
# Barcode Medication Administration (BCMA) 5-Rights Verification Schemas
# -----------------------------------------------------------------------------

class BCMAVerificationRequest(BaseModel):
    encounter_id: int
    prescription_item_id: int
    scanned_patient_barcode: str
    scanned_medication_barcode: str
    dose_given: Optional[str] = None
    route: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    override_warning: bool = False
    override_reason: Optional[str] = None


class BCMAVerificationResponse(BaseModel):
    is_verified: bool
    verification_status: str  # VERIFIED, WARNING_OVERRIDDEN, BLOCKED_MISMATCH
    patient_matched: bool
    medication_matched: bool
    dose_matched: bool
    route_matched: bool = True
    time_status: str  # ON_TIME, EARLY, LATE, PRN
    messages: List[str]
    emar_log_id: Optional[int] = None
    bcma_log_id: Optional[int] = None


# -----------------------------------------------------------------------------
# Controlled Substances (Narcotics) Vault & Dual-Witness Wastage Schemas
# -----------------------------------------------------------------------------

class ControlledSubstanceVaultCreate(BaseModel):
    medication_id: int
    location_id: Optional[int] = None
    vault_location: str = "MAIN_NARCOTICS_SAFE"
    initial_balance_units: int = Field(default=0, ge=0)
    unit_of_measure: str = "AMPOULE"
    tamper_seal_number: Optional[str] = None


class ControlledSubstanceVaultResponse(BaseModel):
    id: int
    medication_id: int
    location_id: int
    vault_location: str
    current_balance_units: int
    unit_of_measure: str
    tamper_seal_number: Optional[str] = None
    is_locked: bool
    medication: MedicationMasterResponse
    model_config = ConfigDict(from_attributes=True)


class ControlledSubstanceReceiptRequest(BaseModel):
    vault_id: int
    quantity_units: int = Field(gt=0)
    batch_number: str = Field(min_length=3)
    witness_user_id: int
    witness_password: str
    tamper_seal_number: Optional[str] = None
    notes: str = Field(min_length=5, description="Procurement or supply reference documentation")


class ControlledSubstanceDispenseRequest(BaseModel):
    vault_id: int
    quantity_units: int = Field(gt=0)
    encounter_id: Optional[int] = None
    prescription_item_id: Optional[int] = None
    witness_user_id: Optional[int] = None
    witness_password: Optional[str] = None
    batch_number: Optional[str] = None
    notes: Optional[str] = None


class ControlledSubstanceReturnRequest(BaseModel):
    vault_id: int
    quantity_units: int = Field(gt=0)
    witness_user_id: int
    witness_password: str
    encounter_id: Optional[int] = None
    prescription_item_id: Optional[int] = None
    batch_number: Optional[str] = None
    notes: Optional[str] = Field(default=None, description="Detailed clinical return justification")


class ControlledSubstanceWastageRequest(BaseModel):
    vault_id: int
    quantity_units: int = Field(gt=0)
    encounter_id: Optional[int] = None
    prescription_item_id: Optional[int] = None
    wastage_reason: str = Field(min_length=5, max_length=255)
    disposal_method: str = Field(min_length=3, max_length=100)
    witness_user_id: int
    witness_password: str
    batch_number: Optional[str] = None
    notes: Optional[str] = None


class ControlledSubstanceMovementResponse(BaseModel):
    id: int
    vault_id: int
    movement_type: str
    quantity_units: int
    balance_before: int
    balance_after: int
    encounter_id: Optional[int] = None
    prescription_item_id: Optional[int] = None
    primary_user_id: Optional[int] = None
    witness_user_id: Optional[int] = None
    witness_verified: bool
    wastage_reason: Optional[str] = None
    disposal_method: Optional[str] = None
    batch_number: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ControlledVaultCountCreate(BaseModel):
    vault_id: int
    physical_balance: int = Field(ge=0)
    witness_user_id: int
    witness_password: str = Field(min_length=1)
    reason: str = Field(min_length=5, max_length=500)


class ControlledVaultCountDecision(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)


class ControlledVaultCountResponse(BaseModel):
    id: int
    vault_id: int
    expected_balance: int
    physical_balance: int
    counted_by_id: int
    witness_user_id: int
    approved_by_id: Optional[int] = None
    status: str
    reason: str
    rejection_reason: Optional[str] = None
    counted_at: datetime
    approved_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


