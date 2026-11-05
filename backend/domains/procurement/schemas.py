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
    model_config = ConfigDict(from_attributes=True)

class VendorStatusUpdate(BaseModel):
    is_active: bool

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


class PurchaseOrderFromRequisitionCreate(BaseModel):
    vendor_id: int
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

class POCreate(BaseModel):
    vendor_id: int
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
    model_config = ConfigDict(from_attributes=True)

class POResponse(BaseModel):
    id: int
    po_number: str
    vendor_id: int
    requisition_id: Optional[int] = None
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
    period_type: str
    period_start: date
    period_end: date
    category: str
    total_amount_paise: int
    warning_threshold_pct: int
    status: str
    model_config = ConfigDict(from_attributes=True)
