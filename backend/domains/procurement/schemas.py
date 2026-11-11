from datetime import date, datetime
import re
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
MAX_PAISE_AMOUNT = 9_223_372_036_854_775_807

from backend.domains.procurement.models import (
    VendorCategoryEnum,
    POStatusEnum,
    GRNStatusEnum,
    IndentStatusEnum,
    VendorInvoiceStatusEnum,
    SupplierPaymentMethodEnum,
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

# --- Purchase Orders ---
class POItemCreate(BaseModel):
    medication_id: Optional[int] = None
    item_description: str
    quantity_ordered: int = Field(gt=0)
    unit_price_paise: int = Field(ge=0)

class POCreate(BaseModel):
    vendor_id: int
    delivery_due_date: datetime
    payment_terms: str
    items: List[POItemCreate]

class POItemResponse(POItemCreate):
    id: int
    quantity_received: int
    total_price_paise: int
    model_config = ConfigDict(from_attributes=True)

class POResponse(BaseModel):
    id: int
    po_number: str
    vendor_id: int
    status: POStatusEnum
    delivery_due_date: datetime
    payment_terms: str
    total_amount_paise: int
    items: List[POItemResponse]
    model_config = ConfigDict(from_attributes=True)

# --- Goods Receipt Note (GRN) ---
class GRNItemCreate(BaseModel):
    po_item_id: int = Field(gt=0)
    batch_number: str = Field(min_length=1, max_length=50)
    expiry_date: datetime
    received_quantity: int = Field(gt=0)
    accepted_quantity: int = Field(ge=0)
    rejection_reason: Optional[str] = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def accepted_quantity_does_not_exceed_received(self):
        if self.accepted_quantity > self.received_quantity:
            raise ValueError("Accepted quantity cannot exceed received quantity.")
        return self

class GRNCreate(BaseModel):
    po_id: int = Field(gt=0)
    invoice_number: str = Field(min_length=1, max_length=100)
    invoice_date: datetime
    items: List[GRNItemCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_purchase_order_items(self):
        item_ids = [item.po_item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("A GRN may contain each purchase-order item only once.")
        return self

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
    item_description: str = Field(min_length=1, max_length=200)
    batch_number: str = Field(min_length=1, max_length=50)
    expiry_date: datetime
    quantity: int = Field(gt=0)
    unit_price_paise: int = Field(ge=0)
    tax_percentage: int = Field(ge=0, le=100)
    total_price_paise: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_line_total(self):
        if self.quantity * self.unit_price_paise != self.total_price_paise:
            raise ValueError("Invoice line total must equal quantity multiplied by unit price before tax.")
        return self

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
        expected_tax_paise = sum(
            (item.total_price_paise * item.tax_percentage + 50) // 100
            for item in self.items
        )
        if expected_tax_paise != self.tax_amount_paise:
            raise ValueError("Invoice tax must equal the sum of rounded line-item taxes.")
        po_item_ids = [item.po_item_id for item in self.items if item.po_item_id is not None]
        if len(po_item_ids) != len(set(po_item_ids)):
            raise ValueError("Each purchase-order line may appear only once on an invoice.")
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
    items: List[IndentIssueItem] = Field(min_length=1, max_length=100)

class IndentReturnItem(BaseModel):
    indent_item_id: int
    allocation_id: int = Field(gt=0)
    return_quantity: int = Field(gt=0)

class IndentReturnRequest(BaseModel):
    items: List[IndentReturnItem] = Field(min_length=1, max_length=100)

# --- Purchase Returns / Debit Notes ---
class PurchaseReturnItemCreate(BaseModel):
    grn_item_id: int = Field(gt=0)
    return_quantity: int = Field(gt=0)
    return_reason: str = Field(min_length=5, max_length=255)

    @field_validator("return_reason")
    @classmethod
    def normalize_return_reason(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 5:
            raise ValueError("Return reason must contain at least five non-whitespace characters.")
        return normalized


class PurchaseReturnCreate(BaseModel):
    grn_id: int = Field(gt=0)
    vendor_id: int = Field(gt=0)
    items: List[PurchaseReturnItemCreate] = Field(min_length=1, max_length=100)
    remarks: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("remarks")
    @classmethod
    def normalize_remarks(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def unique_grn_items(self):
        item_ids = [item.grn_item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Each GRN item may appear only once in a purchase return.")
        return self


class SupplierPaymentRequestAllocationCreate(BaseModel):
    invoice_id: int = Field(gt=0)
    amount_paise: int = Field(gt=0, le=MAX_PAISE_AMOUNT)


class SupplierPaymentRequestCreate(BaseModel):
    vendor_id: int = Field(gt=0)
    payment_reference: str = Field(min_length=2, max_length=100)
    payment_method: SupplierPaymentMethodEnum

    @field_validator("payment_reference")
    @classmethod
    def normalize_payment_reference(cls, value: str) -> str:
        normalized = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._/-]{1,99}", normalized):
            raise ValueError("payment_reference must use 2-100 ASCII letters, digits, spaces, or ._/- characters.")
        return normalized.upper()
    scheduled_date: date
    amount_paise: int = Field(gt=0, le=MAX_PAISE_AMOUNT)
    notes: Optional[str] = Field(default=None, max_length=2000)
    allocations: List[SupplierPaymentRequestAllocationCreate] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_allocations(self):
        invoice_ids = [row.invoice_id for row in self.allocations]
        if len(invoice_ids) != len(set(invoice_ids)):
            raise ValueError("Each invoice may appear only once in a payment request.")
        if sum(row.amount_paise for row in self.allocations) != self.amount_paise:
            raise ValueError("Requested payment amount must equal the sum of invoice allocations.")
        if not self.payment_reference.strip():
            raise ValueError("Payment reference cannot be blank.")
        return self


class SupplierPaymentRequestReview(BaseModel):
    approved: bool
    review_notes: str = Field(min_length=3, max_length=2000)

    @field_validator("review_notes")
    @classmethod
    def normalize_review_notes(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("review_notes must contain at least three non-whitespace characters.")
        return normalized


class SupplierPaymentRequestExecute(BaseModel):
    payment_date: datetime


class SupplierPaymentRequestAllocationResponse(BaseModel):
    id: int
    invoice_id: int
    amount_paise: int
    model_config = ConfigDict(from_attributes=True)


class SupplierPaymentRequestResponse(BaseModel):
    id: int
    vendor_id: int
    payment_reference: str
    payment_method: SupplierPaymentMethodEnum
    scheduled_date: date
    amount_paise: int
    notes: Optional[str]
    status: str
    requested_by_id: int
    requested_at: datetime
    reviewed_by_id: Optional[int]
    reviewed_at: Optional[datetime]
    review_notes: Optional[str]
    executed_payment_id: Optional[int]
    executed_at: Optional[datetime]
    allocations: List[SupplierPaymentRequestAllocationResponse]
    model_config = ConfigDict(from_attributes=True)


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
