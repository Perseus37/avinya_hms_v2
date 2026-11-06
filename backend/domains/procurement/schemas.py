from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from backend.domains.procurement.models import (
    VendorCategoryEnum,
    POStatusEnum,
    GRNStatusEnum,
    IndentStatusEnum,
    PurchaseRequisitionStatusEnum,
    VendorInvoiceStatusEnum,
    SupplierPaymentMethodEnum,
    SupplierAdjustmentTypeEnum,
    SupplierAdjustmentStatusEnum,
    SupplierQuotationStatusEnum,
    POAmendmentStatusEnum,
    POShipmentStatusEnum,
)

# --- Vendor Master ---
class VendorCreate(BaseModel):
    code: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=2, max_length=150)
    category: VendorCategoryEnum
    gstin: Optional[str] = None
    pan: Optional[str] = None
    contact_person: str
    phone: str
    email: EmailStr
    address: str
    bank_account_number: Optional[str] = None
    bank_ifsc: Optional[str] = None
    credit_period_days: int = Field(default=30, ge=0)

class VendorResponse(VendorCreate):
    id: int
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

class VendorDirectoryResponse(BaseModel):
    id: int
    code: str
    name: str
    category: VendorCategoryEnum
    gstin: Optional[str] = None
    pan: Optional[str] = None
    contact_person: str
    phone: str
    email: EmailStr
    address: str
    credit_period_days: int
    is_active: bool
    is_suspended: bool = False
    suspension_reason: Optional[str] = None
    suspended_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class VendorStatusUpdate(BaseModel):
    is_active: bool


class SupplierLifecycleRequestCreate(BaseModel):
    action: str = Field(pattern="^(SUSPEND|REINSTATE)$")
    reason: str = Field(min_length=10, max_length=2000)


class SupplierLifecycleRequestReview(BaseModel):
    approved: bool
    review_notes: str = Field(min_length=3, max_length=2000)


class SupplierLifecycleRequestResponse(BaseModel):
    id: int
    vendor_id: int
    action: str
    reason: str
    status: str
    requested_by_id: int
    requested_at: datetime
    reviewed_by_id: Optional[int]
    reviewed_at: Optional[datetime]
    review_notes: Optional[str]
    model_config = ConfigDict(from_attributes=True)

# --- Purchase Requisitions ---
class PurchaseRequisitionItemCreate(BaseModel):
    medication_id: Optional[int] = None
    purchase_uom_id: Optional[int] = None
    item_description: str = Field(min_length=1, max_length=200)
    requested_quantity: int = Field(gt=0)
    estimated_unit_price_paise: Optional[int] = Field(default=None, ge=0)
    notes: Optional[str] = Field(default=None, max_length=500)


class PurchaseRequisitionCreate(BaseModel):
    requesting_department_id: int
    required_by_date: Optional[datetime] = None
    justification: str = Field(min_length=10, max_length=2000)
    items: List[PurchaseRequisitionItemCreate] = Field(min_length=1, max_length=100)


class PurchaseRequisitionItemResponse(BaseModel):
    id: int
    medication_id: Optional[int]
    purchase_uom_id: Optional[int] = None
    item_description: str
    requested_quantity: int
    approved_quantity: Optional[int]
    estimated_unit_price_paise: Optional[int]
    notes: Optional[str]
    model_config = ConfigDict(from_attributes=True)


class PurchaseRequisitionResponse(BaseModel):
    id: int
    requisition_number: str
    requesting_department_id: int
    requested_by_id: int
    status: PurchaseRequisitionStatusEnum
    required_by_date: Optional[datetime]
    justification: str
    submitted_at: Optional[datetime]
    reviewed_by_id: Optional[int]
    reviewed_at: Optional[datetime]
    review_notes: Optional[str]
    items: List[PurchaseRequisitionItemResponse]
    model_config = ConfigDict(from_attributes=True)


class PurchaseRequisitionItemApproval(BaseModel):
    requisition_item_id: int
    approved_quantity: int = Field(ge=0)
    estimated_unit_price_paise: Optional[int] = Field(default=None, ge=0)


class PurchaseRequisitionReview(BaseModel):
    approved: bool
    review_notes: str = Field(min_length=3, max_length=2000)
    items: List[PurchaseRequisitionItemApproval] = Field(default_factory=list, max_length=100)


class PurchaseOrderFromRequisitionItem(BaseModel):
    requisition_item_id: int
    quantity_ordered: int = Field(gt=0)
    unit_price_paise: int = Field(ge=0)
    tax_percentage: Optional[int] = Field(default=None, ge=0, le=100)
    purchase_uom_id: Optional[int] = None
    budget_category: Optional[str] = Field(default=None, pattern="^(PHARMACY|LABORATORY|GENERAL_SUPPLIES|EQUIPMENT|SERVICES|OTHER)$")


class PurchaseOrderFromRequisitionCreate(BaseModel):
    vendor_id: int
    contract_id: Optional[int] = None
    delivery_due_date: datetime
    payment_terms: str = Field(min_length=1, max_length=255)
    items: List[PurchaseOrderFromRequisitionItem] = Field(min_length=1, max_length=100)


# --- Purchase Orders ---
class POItemCreate(BaseModel):
    medication_id: Optional[int] = None
    item_description: str
    quantity_ordered: int = Field(gt=0)
    unit_price_paise: int = Field(ge=0)
    tax_percentage: int = Field(default=0, ge=0, le=100)
    purchase_uom_id: Optional[int] = None
    budget_department_id: Optional[int] = None
    budget_category: Optional[str] = Field(default=None, pattern="^(PHARMACY|LABORATORY|GENERAL_SUPPLIES|EQUIPMENT|SERVICES|OTHER)$")

    @model_validator(mode="after")
    def validate_medication_budget_category(self):
        if self.medication_id is not None and self.budget_category not in (None, "PHARMACY"):
            raise ValueError("Medication purchase lines must use the PHARMACY budget category.")
        return self

class POCreate(BaseModel):
    vendor_id: int
    contract_id: Optional[int] = None
    delivery_due_date: datetime
    payment_terms: str
    items: List[POItemCreate] = Field(min_length=1)

class POItemResponse(POItemCreate):
    id: int
    requisition_item_id: Optional[int] = None
    quantity_received: int
    total_price_paise: int
    tax_amount_paise: int
    gross_total_paise: int
    purchase_uom_code: Optional[str] = None
    base_uom_code: Optional[str] = None
    units_per_purchase_unit: Optional[Decimal] = None
    base_quantity: Optional[Decimal] = None
    base_unit_price_paise: Optional[Decimal] = None
    budget_department_id: Optional[int] = None
    budget_category: str
    budget_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

class POResponse(BaseModel):
    id: int
    po_number: str
    vendor_id: int
    requisition_id: Optional[int] = None
    contract_id: Optional[int] = None
    status: POStatusEnum
    delivery_due_date: datetime
    payment_terms: str
    subtotal_paise: int
    tax_amount_paise: int
    total_amount_paise: int
    items: List[POItemResponse]
    model_config = ConfigDict(from_attributes=True)

# --- Goods Receipt Note (GRN) ---
class GRNItemCreate(BaseModel):
    po_item_id: int
    batch_number: str = Field(min_length=1, max_length=50)
    expiry_date: datetime
    received_quantity: int = Field(ge=0)
    accepted_quantity: int = Field(ge=0)
    rejection_reason: Optional[str] = Field(default=None, max_length=255)

class GRNCreate(BaseModel):
    po_id: int
    location_id: Optional[int] = None
    invoice_number: str = Field(min_length=1, max_length=100)
    invoice_date: datetime
    items: List[GRNItemCreate] = Field(min_length=1)

# --- Vendor Invoices (Donut AI Integration) ---
class VendorInvoiceItemResponse(BaseModel):
    id: int
    po_item_id: Optional[int]
    medication_id: Optional[int]
    item_description: str
    batch_number: str
    expiry_date: datetime
    quantity: int
    unit_price_paise: int
    tax_percentage: int
    total_price_paise: int
    purchase_uom_code: Optional[str] = None
    base_uom_code: Optional[str] = None
    units_per_purchase_unit: Optional[float] = None
    base_quantity: Optional[float] = None
    base_unit_price_paise: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)

class VendorInvoiceResponse(BaseModel):
    id: int
    vendor_id: int
    po_id: Optional[int]
    grn_id: Optional[int]
    invoice_number: str
    invoice_date: datetime
    due_date: datetime
    subtotal_paise: int
    tax_amount_paise: int
    discount_paise: int
    total_amount_paise: int
    status: VendorInvoiceStatusEnum
    notes: Optional[str]
    items: List[VendorInvoiceItemResponse]
    model_config = ConfigDict(from_attributes=True)

class VendorInvoiceItemReview(BaseModel):
    po_item_id: Optional[int] = None
    medication_id: Optional[int] = None
    purchase_uom_code: Optional[str] = Field(default=None, max_length=24)
    item_description: str = Field(min_length=1, max_length=200)
    batch_number: str = Field(min_length=1, max_length=50)
    expiry_date: datetime
    quantity: int = Field(gt=0)
    unit_price_paise: int = Field(ge=0)
    tax_percentage: int = Field(ge=0, le=100)
    total_price_paise: int = Field(ge=0)

class SupplierPaymentAllocationCreate(BaseModel):
    invoice_id: int = Field(gt=0)
    amount_paise: int = Field(gt=0)


class SupplierPaymentCreate(BaseModel):
    vendor_id: int = Field(gt=0)
    payment_reference: str = Field(min_length=2, max_length=100)
    payment_method: SupplierPaymentMethodEnum
    payment_date: datetime
    amount_paise: int = Field(gt=0)
    notes: Optional[str] = Field(default=None, max_length=2000)
    allocations: List[SupplierPaymentAllocationCreate] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_allocations(self):
        invoice_ids = [row.invoice_id for row in self.allocations]
        if len(invoice_ids) != len(set(invoice_ids)):
            raise ValueError("Each invoice may appear only once in a payment allocation.")
        if sum(row.amount_paise for row in self.allocations) != self.amount_paise:
            raise ValueError("Payment amount must equal the sum of its invoice allocations.")
        return self


class SupplierPaymentAllocationResponse(BaseModel):
    id: int
    invoice_id: int
    amount_paise: int
    model_config = ConfigDict(from_attributes=True)


class SupplierPaymentResponse(BaseModel):
    id: int
    vendor_id: int
    payment_reference: str
    payment_method: SupplierPaymentMethodEnum
    payment_date: datetime
    amount_paise: int
    notes: Optional[str]
    recorded_by_id: int
    allocations: List[SupplierPaymentAllocationResponse]
    model_config = ConfigDict(from_attributes=True)


class SupplierInvoiceSettlementResponse(BaseModel):
    invoice_id: int
    vendor_id: int
    invoice_number: str
    invoice_total_paise: int
    amount_paid_paise: int
    credit_adjustments_paise: int = 0
    advances_applied_paise: int = 0
    outstanding_paise: int
    status: VendorInvoiceStatusEnum



class SupplierAdjustmentCreate(BaseModel):
    vendor_id: int = Field(gt=0)
    adjustment_type: SupplierAdjustmentTypeEnum
    document_number: str = Field(min_length=2, max_length=100)
    document_date: date
    amount_paise: int = Field(gt=0)
    reason: str = Field(min_length=5, max_length=2000)
    notes: Optional[str] = Field(default=None, max_length=2000)


class SupplierAdjustmentReview(BaseModel):
    approved: bool
    review_notes: Optional[str] = Field(default=None, max_length=2000)


class SupplierAdjustmentApply(BaseModel):
    invoice_id: int = Field(gt=0)
    amount_paise: int = Field(gt=0)


class SupplierAdjustmentResponse(BaseModel):
    id: int
    vendor_id: int
    adjustment_type: SupplierAdjustmentTypeEnum
    document_number: str
    document_date: date
    amount_paise: int
    reason: str
    notes: Optional[str]
    status: SupplierAdjustmentStatusEnum
    requested_by_id: int
    reviewed_by_id: Optional[int]
    reviewed_at: Optional[datetime]
    review_notes: Optional[str]
    model_config = ConfigDict(from_attributes=True)


class SupplierAdvanceCreate(BaseModel):
    vendor_id: int = Field(gt=0)
    advance_reference: str = Field(min_length=2, max_length=100)
    payment_method: SupplierPaymentMethodEnum
    advance_date: datetime
    amount_paise: int = Field(gt=0)
    notes: Optional[str] = Field(default=None, max_length=2000)


class SupplierAdvanceApply(BaseModel):
    invoice_id: int = Field(gt=0)
    amount_paise: int = Field(gt=0)


class SupplierAdvanceResponse(BaseModel):
    id: int
    vendor_id: int
    advance_reference: str
    payment_method: SupplierPaymentMethodEnum
    advance_date: datetime
    amount_paise: int
    notes: Optional[str]
    recorded_by_id: int
    model_config = ConfigDict(from_attributes=True)



class VendorInvoiceReview(BaseModel):
    po_id: Optional[int] = None
    grn_id: Optional[int] = None
    invoice_number: str = Field(min_length=1, max_length=100)
    invoice_date: datetime
    due_date: datetime
    subtotal_paise: int = Field(ge=0)
    tax_amount_paise: int = Field(ge=0)
    discount_paise: int = Field(ge=0)
    total_amount_paise: int = Field(ge=0)
    items: List[VendorInvoiceItemReview] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_totals(self):
        if self.subtotal_paise + self.tax_amount_paise - self.discount_paise != self.total_amount_paise:
            raise ValueError("Invoice total must equal subtotal plus tax minus discount.")
        if self.discount_paise > self.subtotal_paise:
            raise ValueError("Invoice discount cannot exceed its subtotal.")
        if sum(item.total_price_paise for item in self.items) != self.subtotal_paise:
            raise ValueError("Invoice subtotal must equal the sum of its line-item totals.")
        if self.due_date < self.invoice_date:
            raise ValueError("Invoice due date cannot be earlier than its invoice date.")
        return self

class StoreIndentItemCreate(BaseModel):
    medication_id: int
    requested_quantity: int = Field(gt=0)

class StoreIndentCreate(BaseModel):
    requesting_department_id: int
    encounter_id: Optional[int] = None
    remarks: Optional[str] = None
    items: List[StoreIndentItemCreate]

class StoreIndentItemResponse(BaseModel):
    id: int
    medication_id: int
    requested_quantity: int
    issued_quantity: int
    model_config = ConfigDict(from_attributes=True)

class StoreIndentResponse(BaseModel):
    id: int
    indent_number: str
    requesting_department_id: int
    encounter_id: Optional[int]
    status: IndentStatusEnum
    remarks: Optional[str]
    items: List[StoreIndentItemResponse]
    model_config = ConfigDict(from_attributes=True)

class IndentIssueItem(BaseModel):
    indent_item_id: int
    batch_id: int
    issue_quantity: int = Field(gt=0)

class IndentIssueRequest(BaseModel):
    items: List[IndentIssueItem]

class IndentReturnItem(BaseModel):
    indent_item_id: int
    batch_id: int
    return_quantity: int = Field(gt=0)

class IndentReturnRequest(BaseModel):
    items: List[IndentReturnItem]

# --- Purchase Returns / Debit Notes ---
class PurchaseReturnItemCreate(BaseModel):
    grn_item_id: int
    return_quantity: int = Field(gt=0)
    return_reason: str = Field(min_length=5)

class PurchaseReturnCreate(BaseModel):
    grn_id: int
    vendor_id: int
    items: List[PurchaseReturnItemCreate]
    remarks: Optional[str] = None

# --- Supplier Quotations ---
class SupplierQuotationItemCreate(BaseModel):
    requisition_item_id: int
    quantity_quoted: int = Field(gt=0)
    unit_price_paise: int = Field(ge=0)
    tax_percentage: int = Field(default=0, ge=0, le=100)
    purchase_uom_id: Optional[int] = None


class SupplierQuotationCreate(BaseModel):
    vendor_id: int
    quotation_number: str = Field(min_length=1, max_length=100)
    quoted_at: datetime
    valid_until: Optional[datetime] = None
    delivery_days: Optional[int] = Field(default=None, ge=0)
    payment_terms: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = None
    items: List[SupplierQuotationItemCreate] = Field(min_length=1, max_length=100)


class SupplierQuotationItemResponse(BaseModel):
    id: int
    requisition_item_id: int
    quantity_quoted: int
    unit_price_paise: int
    tax_percentage: int
    tax_amount_paise: int
    line_total_paise: int
    purchase_uom_code: Optional[str] = None
    base_uom_code: Optional[str] = None
    units_per_purchase_unit: Optional[float] = None
    base_quantity: Optional[float] = None
    base_unit_price_paise: Optional[float] = None
    model_config = ConfigDict(from_attributes=True)


class SupplierQuotationResponse(BaseModel):
    id: int
    requisition_id: int
    vendor_id: int
    quotation_number: str
    quoted_at: datetime
    valid_until: Optional[datetime]
    delivery_days: Optional[int]
    payment_terms: Optional[str]
    notes: Optional[str]
    total_amount_paise: int
    status: SupplierQuotationStatusEnum
    selected_by_id: Optional[int]
    selected_at: Optional[datetime]
    selection_reason: Optional[str]
    items: List[SupplierQuotationItemResponse]
    model_config = ConfigDict(from_attributes=True)


class SupplierQuotationSelection(BaseModel):
    selection_reason: str = Field(min_length=10, max_length=2000)


# --- Purchase order approval authority ---
class PurchaseOrderApprovalAuthorityUpdate(BaseModel):
    max_amount_paise: int = Field(ge=0)
    is_active: bool = True


class PurchaseOrderApprovalAuthorityResponse(BaseModel):
    id: int
    role_id: int
    max_amount_paise: int
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


# --- Purchase order amendments ---
class PurchaseOrderAmendmentItemCreate(POItemCreate):
    requisition_item_id: Optional[int] = None


class PurchaseOrderAmendmentCreate(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)
    delivery_due_date: datetime
    payment_terms: str = Field(min_length=1, max_length=255)
    items: List[PurchaseOrderAmendmentItemCreate] = Field(min_length=1, max_length=100)


class PurchaseOrderAmendmentReview(BaseModel):
    approved: bool
    review_notes: str = Field(min_length=3, max_length=2000)


class PurchaseOrderAmendmentResponse(BaseModel):
    id: int
    po_id: int
    version: int
    reason: str
    prior_snapshot: dict
    proposed_snapshot: dict
    status: POAmendmentStatusEnum
    reviewed_by_id: Optional[int]
    reviewed_at: Optional[datetime]
    review_notes: Optional[str]
    model_config = ConfigDict(from_attributes=True)


# --- Purchase order shipment tracking ---
class PurchaseOrderShipmentCreate(BaseModel):
    carrier: str = Field(min_length=2, max_length=120)
    tracking_number: Optional[str] = Field(default=None, max_length=120)
    expected_delivery_at: datetime
    notes: Optional[str] = None


class PurchaseOrderShipmentUpdate(BaseModel):
    status: POShipmentStatusEnum
    event_at: Optional[datetime] = None
    location: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = None


class PurchaseOrderShipmentEventResponse(BaseModel):
    id: int
    status: POShipmentStatusEnum
    event_at: datetime
    location: Optional[str]
    notes: Optional[str]
    actor_user_id: Optional[int]
    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderShipmentResponse(BaseModel):
    id: int
    po_id: int
    carrier: str
    tracking_number: Optional[str]
    expected_delivery_at: datetime
    dispatched_at: Optional[datetime]
    delivery_confirmed_at: Optional[datetime]
    status: POShipmentStatusEnum
    notes: Optional[str]
    events: List[PurchaseOrderShipmentEventResponse]
    model_config = ConfigDict(from_attributes=True)


class OverduePurchaseOrderResponse(BaseModel):
    po_id: int
    po_number: str
    vendor_id: int
    vendor_name: str
    delivery_due_date: datetime
    days_overdue: int
    status: POStatusEnum
    total_amount_paise: int
    outstanding_quantity: int


# --- Procurement units and medication pack configuration ---
class ProcurementUnitOfMeasureResponse(BaseModel):
    id: int
    code: str
    display_name: str
    dimension: str
    allows_fractional: bool
    is_packaging_unit: bool
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class MedicationPackConfigurationCreate(BaseModel):
    purchase_uom_id: int
    base_uom_id: int
    units_per_purchase_unit: Decimal = Field(gt=0, le=1000000000)
    effective_from: datetime


class MedicationPackConfigurationResponse(BaseModel):
    id: int
    medication_id: int
    purchase_uom_id: int
    base_uom_id: int
    units_per_purchase_unit: float
    effective_from: datetime
    effective_to: Optional[datetime]
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


# --- Procurement price benchmarking and variance controls ---
class MedicationPriceControlUpdate(BaseModel):
    max_variance_pct: int = Field(ge=0, le=1000)
    minimum_observations: int = Field(default=3, ge=2, le=100)
    lookback_days: int = Field(default=180, ge=1, le=1825)
    is_active: bool = True


class MedicationPriceControlResponse(BaseModel):
    id: int
    medication_id: int
    max_variance_pct: int
    minimum_observations: int
    lookback_days: int
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderApprovalRequest(BaseModel):
    override_reason: Optional[str] = Field(default=None, min_length=10, max_length=2000)


class PurchaseOrderPriceReviewResponse(BaseModel):
    id: int
    po_id: int
    po_item_id: int
    medication_id: int
    base_uom_code: str
    proposed_base_unit_price_paise: Decimal
    benchmark_median_paise: Decimal
    benchmark_min_paise: Decimal
    benchmark_max_paise: Decimal
    benchmark_observations: int
    threshold_pct: int
    variance_pct: Decimal
    override_reason: str
    reviewed_by_id: int
    reviewed_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Procurement budget allocation and maker-checker revisions ---
class ProcurementBudgetCreate(BaseModel):
    budget_number: str = Field(min_length=3, max_length=50)
    requesting_department_id: int
    parent_budget_id: Optional[int] = None
    period_type: str = Field(pattern="^(ANNUAL|QUARTERLY)$")
    period_start: date
    period_end: date
    category: str = Field(pattern="^(PHARMACY|LABORATORY|GENERAL_SUPPLIES|EQUIPMENT|SERVICES|OTHER)$")
    total_amount_paise: int = Field(ge=0)
    warning_threshold_pct: int = Field(default=80, ge=1, le=100)

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_end < self.period_start:
            raise ValueError("Budget period_end cannot be earlier than period_start.")
        if self.period_type == "ANNUAL" and self.parent_budget_id is not None:
            raise ValueError("Annual budgets cannot be children of another budget.")
        if self.period_type == "QUARTERLY" and self.period_start.month not in (1, 4, 7, 10):
            raise ValueError("Quarterly budgets must begin in January, April, July or October.")
        if self.period_type == "ANNUAL" and self.period_start.month not in (1, 4):
            raise ValueError("Annual budgets must begin in January or April.")
        if self.period_start.day != 1:
            raise ValueError("Budget periods must start on the first day of a calendar month.")
        import calendar
        if self.period_end.day != calendar.monthrange(self.period_end.year, self.period_end.month)[1]:
            raise ValueError("Budget periods must end on the last day of a calendar month.")
        month_span = (self.period_end.year - self.period_start.year) * 12 + self.period_end.month - self.period_start.month + 1
        expected_months = 12 if self.period_type == "ANNUAL" else 3
        if month_span != expected_months:
            raise ValueError(f"{self.period_type} budgets must cover exactly {expected_months} calendar months.")
        return self


class ProcurementBudgetRevisionCreate(BaseModel):
    proposed_amount_paise: int = Field(ge=0)
    reason: str = Field(min_length=10, max_length=2000)


class ProcurementBudgetRevisionReview(BaseModel):
    approved: bool
    review_notes: str = Field(min_length=3, max_length=2000)


class ProcurementBudgetRevisionResponse(BaseModel):
    id: int
    budget_id: int
    revision_number: int
    prior_amount_paise: int
    proposed_amount_paise: int
    reason: str
    status: str
    reviewed_by_id: Optional[int]
    reviewed_at: Optional[datetime]
    review_notes: Optional[str]
    model_config = ConfigDict(from_attributes=True)


class ProcurementBudgetResponse(BaseModel):
    id: int
    budget_number: str
    requesting_department_id: int
    parent_budget_id: Optional[int]
    period_type: str
    period_start: date
    period_end: date
    category: str
    total_amount_paise: int
    warning_threshold_pct: int
    status: str
    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderCancelRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=2000)


# --- Supplier contracts and negotiated rate cards ---
class SupplierContractRateCreate(BaseModel):
    scope_type: str = Field(pattern="^(MEDICATION|CATEGORY)$")
    medication_id: Optional[int] = None
    category: Optional[str] = Field(default=None, pattern="^(PHARMACY|LABORATORY|GENERAL_SUPPLIES|EQUIPMENT|SERVICES|OTHER)$")
    uom_code: str = Field(min_length=1, max_length=24)
    unit_price_paise: int = Field(ge=0)
    tax_percentage: int = Field(default=0, ge=0, le=100)
    notes: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_scope(self):
        if self.scope_type == "MEDICATION" and (self.medication_id is None or self.category is not None):
            raise ValueError("Medication rates require medication_id and no category.")
        if self.scope_type == "CATEGORY" and (self.category is None or self.medication_id is not None):
            raise ValueError("Category rates require category and no medication_id.")
        return self




class SupplierCompliancePolicyUpdate(BaseModel):
    is_required: bool


class SupplierCompliancePolicyResponse(BaseModel):
    id: int
    vendor_category: str
    document_type: str
    is_required: bool
    updated_by_id: int
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SupplierComplianceDocumentResponse(BaseModel):
    id: int
    vendor_id: int
    document_type: str
    document_number: Optional[str]
    issuer: Optional[str]
    issue_date: Optional[date]
    expiry_date: Optional[date]
    original_filename: str
    status: str
    uploaded_by_id: int
    uploaded_at: datetime
    verified_by_id: Optional[int]
    verified_at: Optional[datetime]
    review_notes: Optional[str]
    model_config = ConfigDict(from_attributes=True)


class SupplierComplianceDocumentReview(BaseModel):
    approved: bool
    review_notes: str = Field(min_length=3, max_length=2000)


class SupplierContractCreate(BaseModel):
    vendor_id: int
    contract_number: str = Field(min_length=2, max_length=80)
    title: str = Field(min_length=3, max_length=200)
    valid_from: date
    valid_to: date
    renewal_notice_days: int = Field(default=90, ge=0, le=730)
    auto_renew: bool = False
    payment_terms: Optional[str] = Field(default=None, max_length=255)
    summary: Optional[str] = Field(default=None, max_length=5000)
    rates: List[SupplierContractRateCreate] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_dates_and_rates(self):
        if self.valid_to < self.valid_from:
            raise ValueError("Contract valid_to cannot be earlier than valid_from.")
        keys = [(r.scope_type, r.medication_id, r.category, r.uom_code) for r in self.rates]
        if len(keys) != len(set(keys)):
            raise ValueError("Contract rate scope and UOM combinations must be unique.")
        return self


class SupplierContractRateResponse(BaseModel):
    id: int
    scope_type: str
    medication_id: Optional[int]
    category: Optional[str]
    uom_code: str
    unit_price_paise: int
    tax_percentage: int
    notes: Optional[str]
    model_config = ConfigDict(from_attributes=True)


class SupplierContractResponse(BaseModel):
    id: int
    vendor_id: int
    contract_number: str
    title: str
    valid_from: date
    valid_to: date
    renewal_notice_days: int
    auto_renew: bool
    status: str
    payment_terms: Optional[str]
    summary: Optional[str]
    version_number: int
    submitted_at: Optional[datetime]
    approved_by_id: Optional[int]
    approved_at: Optional[datetime]
    rates: List[SupplierContractRateResponse]
    model_config = ConfigDict(from_attributes=True)


class SupplierContractRevisionCreate(BaseModel):
    proposed_valid_to: Optional[date] = None
    proposed_payment_terms: Optional[str] = Field(default=None, max_length=255)
    proposed_summary: Optional[str] = Field(default=None, max_length=5000)
    proposed_rates: Optional[List[SupplierContractRateCreate]] = Field(default=None, min_length=1, max_length=500)
    reason: str = Field(min_length=10, max_length=2000)

    @model_validator(mode="after")
    def validate_proposed_rate_scopes(self):
        if self.proposed_rates is not None:
            keys = [(r.scope_type, r.medication_id, r.category, r.uom_code) for r in self.proposed_rates]
            if len(keys) != len(set(keys)):
                raise ValueError("Proposed contract rate scope and UOM combinations must be unique.")
        return self


class SupplierContractRevisionReview(BaseModel):
    approved: bool
    review_notes: str = Field(min_length=3, max_length=2000)


class SupplierContractRevisionResponse(BaseModel):
    id: int
    contract_id: int
    revision_number: int
    prior_snapshot: dict
    proposed_snapshot: dict
    reason: str
    status: str
    requested_by_id: int
    reviewed_by_id: Optional[int]
    reviewed_at: Optional[datetime]
    review_notes: Optional[str]
    model_config = ConfigDict(from_attributes=True)
