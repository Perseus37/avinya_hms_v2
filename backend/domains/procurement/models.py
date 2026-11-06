from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.audit import AuditMixin
from backend.core.database import Base
from backend.domains.identity.models import Department, User, Role
from backend.domains.encounters.models import PatientEncounter
from backend.domains.pharmacy.models import MedicationMaster, InventoryBatch
# from backend.domains.procurement.models import VendorMaster, PurchaseOrder, GoodsReceiptNote


class VendorCategoryEnum(str, PyEnum):
    PHARMACEUTICALS = "PHARMACEUTICALS"
    SURGICAL_IMPLANTS = "SURGICAL_IMPLANTS"
    LAB_REAGENTS = "LAB_REAGENTS"
    EQUIPMENT_MAINTENANCE = "EQUIPMENT_MAINTENANCE"
    GENERAL_SUPPLIES = "GENERAL_SUPPLIES"


class PurchaseRequisitionStatusEnum(str, PyEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PARTIALLY_ORDERED = "PARTIALLY_ORDERED"
    CONVERTED = "CONVERTED"
    CANCELLED = "CANCELLED"


class POShipmentStatusEnum(str, PyEnum):
    PLANNED = "PLANNED"
    DISPATCHED = "DISPATCHED"
    IN_TRANSIT = "IN_TRANSIT"
    DELAYED = "DELAYED"
    DELIVERY_CONFIRMED = "DELIVERY_CONFIRMED"
    CANCELLED = "CANCELLED"


class POAmendmentStatusEnum(str, PyEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class POStatusEnum(str, PyEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class GRNStatusEnum(str, PyEnum):
    PENDING_INSPECTION = "PENDING_INSPECTION"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class IndentStatusEnum(str, PyEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"

class VendorInvoiceStatusEnum(str, PyEnum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    PRICE_VARIANCE_FLAGGED = "PRICE_VARIANCE_FLAGGED"
    MATCHED_APPROVED = "MATCHED_APPROVED"
    PAID = "PAID"
    REJECTED = "REJECTED"

class SupplierPaymentMethodEnum(str, PyEnum):
    BANK_TRANSFER = "BANK_TRANSFER"
    UPI = "UPI"
    CHEQUE = "CHEQUE"
    CASH = "CASH"
    CARD = "CARD"
    NEFT = "NEFT"
    RTGS = "RTGS"
    IMPS = "IMPS"
    OTHER = "OTHER"

class VendorMaster(AuditMixin, Base):
    """Registered hospital suppliers, distributors, and manufacturers."""
    __tablename__ = "procurement_vendors"
    __table_args__ = (
        CheckConstraint("credit_period_days >= 0", name="ck_vendor_credit_days_non_neg"),
        Index("ix_procurement_vendors_is_suspended", "is_suspended"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[VendorCategoryEnum] = mapped_column(nullable=False)
    gstin: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    pan: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)
    contact_person: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    bank_account_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    bank_ifsc: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    credit_period_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    suspension_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suspended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class SupplierLifecycleRequest(Base):
    """Maker-checker request and durable decision history for supplier suspension."""
    __tablename__ = "procurement_supplier_lifecycle_requests"
    __table_args__ = (
        CheckConstraint("action IN ('SUSPEND','REINSTATE')", name="ck_supplier_lifecycle_action"),
        CheckConstraint("status IN ('PENDING','APPROVED','REJECTED')", name="ck_supplier_lifecycle_status"),
        Index("ix_supplier_lifecycle_vendor_created", "vendor_id", "requested_at"),
        Index("ix_supplier_lifecycle_status_created", "status", "requested_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendors.id", ondelete="RESTRICT"), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", nullable=False)
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PurchaseRequisition(AuditMixin, Base):
    """Department-originated request to procure goods from an external supplier."""
    __tablename__ = "procurement_requisitions"
    __table_args__ = (
        Index("ix_proc_requisition_status_created", "status", "created_at"),
        Index("ix_proc_requisition_department_status", "requesting_department_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    requisition_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    requesting_department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=False, index=True)
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[PurchaseRequisitionStatusEnum] = mapped_column(
        Enum(PurchaseRequisitionStatusEnum), default=PurchaseRequisitionStatusEnum.DRAFT, nullable=False
    )
    required_by_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    requesting_department: Mapped["Department"] = relationship()
    requested_by: Mapped["User"] = relationship(foreign_keys=[requested_by_id])
    reviewed_by: Mapped[Optional["User"]] = relationship(foreign_keys=[reviewed_by_id])
    items: Mapped[List["PurchaseRequisitionItem"]] = relationship(
        back_populates="requisition", cascade="all, delete-orphan"
    )
    purchase_orders: Mapped[List["PurchaseOrder"]] = relationship(back_populates="requisition")


class PurchaseRequisitionItem(AuditMixin, Base):
    """Requested catalogue or free-text item and approved procurement quantity."""
    __tablename__ = "procurement_requisition_items"
    __table_args__ = (
        CheckConstraint("requested_quantity > 0", name="ck_proc_req_item_qty_pos"),
        CheckConstraint("approved_quantity IS NULL OR approved_quantity >= 0", name="ck_proc_req_item_approved_qty_nonneg"),
        Index("ix_proc_req_items_requisition", "requisition_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    requisition_id: Mapped[int] = mapped_column(
        ForeignKey("procurement_requisitions.id", ondelete="CASCADE"), nullable=False
    )
    medication_id: Mapped[Optional[int]] = mapped_column(ForeignKey("medication_master.id"), nullable=True, index=True)
    purchase_uom_id: Mapped[Optional[int]] = mapped_column(ForeignKey("procurement_units_of_measure.id"), nullable=True)
    item_description: Mapped[str] = mapped_column(String(200), nullable=False)
    requested_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    estimated_unit_price_paise: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    requisition: Mapped["PurchaseRequisition"] = relationship(back_populates="items")
    medication: Mapped[Optional["MedicationMaster"]] = relationship()


class PurchaseOrder(AuditMixin, Base):
    """Official procurement order placed with a vendor."""
    __tablename__ = "procurement_purchase_orders"
    __table_args__ = (
        Index("ix_po_vendor_status", "vendor_id", "status"),
        CheckConstraint("subtotal_paise >= 0", name="ck_po_subtotal_non_neg"),
        CheckConstraint("tax_amount_paise >= 0", name="ck_po_tax_non_neg"),
        CheckConstraint("total_amount_paise >= 0", name="ck_po_total_non_neg"),
        CheckConstraint("subtotal_paise + tax_amount_paise = total_amount_paise", name="ck_po_financial_totals"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendors.id"), nullable=False)
    requisition_id: Mapped[Optional[int]] = mapped_column(ForeignKey("procurement_requisitions.id"), nullable=True, index=True)
    contract_id: Mapped[Optional[int]] = mapped_column(ForeignKey("procurement_supplier_contracts.id", ondelete="RESTRICT"), nullable=True, index=True)
    status: Mapped[POStatusEnum] = mapped_column(default=POStatusEnum.DRAFT, nullable=False)
    delivery_due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payment_terms: Mapped[str] = mapped_column(String(255), nullable=False)
    # Commercial totals: subtotal is pre-tax, tax is explicit, total is tax-inclusive.
    subtotal_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tax_amount_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_amount_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    approved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    amendment_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    vendor: Mapped["VendorMaster"] = relationship()
    requisition: Mapped[Optional["PurchaseRequisition"]] = relationship(back_populates="purchase_orders")
    approved_by: Mapped[Optional["User"]] = relationship(foreign_keys=[approved_by_id])
    items: Mapped[List["PurchaseOrderItem"]] = relationship(back_populates="purchase_order", cascade="all, delete-orphan")
    shipments: Mapped[List["PurchaseOrderShipment"]] = relationship(back_populates="purchase_order", cascade="all, delete-orphan")


class PurchaseOrderItem(AuditMixin, Base):
    """Line items on a Purchase Order (Medication or General Consumables)."""
    __tablename__ = "procurement_po_items"
    __table_args__ = (
        CheckConstraint("quantity_ordered > 0", name="ck_po_item_qty_pos"),
        CheckConstraint("unit_price_paise >= 0", name="ck_po_item_price_non_neg"),
        CheckConstraint("tax_percentage >= 0 AND tax_percentage <= 100", name="ck_po_item_tax_range"),
        CheckConstraint("tax_amount_paise >= 0", name="ck_po_item_tax_non_neg"),
        CheckConstraint("gross_total_paise >= 0", name="ck_po_item_gross_non_neg"),
        CheckConstraint("total_price_paise + tax_amount_paise = gross_total_paise", name="ck_po_item_financial_totals"),
        CheckConstraint("budget_category IN ('PHARMACY', 'LABORATORY', 'GENERAL_SUPPLIES', 'EQUIPMENT', 'SERVICES', 'OTHER')", name="ck_po_item_budget_category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("procurement_purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    requisition_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("procurement_requisition_items.id"), nullable=True, index=True)
    medication_id: Mapped[Optional[int]] = mapped_column(ForeignKey("medication_master.id"), nullable=True, index=True)
    item_description: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unit_price_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    total_price_paise: Mapped[int] = mapped_column(Integer, nullable=False)  # pre-tax line amount
    tax_percentage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tax_amount_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    gross_total_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Immutable unit snapshots; NULL means the historical/entered unit is unknown.
    purchase_uom_code: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    base_uom_code: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    units_per_purchase_unit: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 6), nullable=True)
    base_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 6), nullable=True)
    base_unit_price_paise: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 8), nullable=True)
    budget_department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), nullable=True, index=True)
    budget_category: Mapped[str] = mapped_column(String(24), default="GENERAL_SUPPLIES", nullable=False)
    budget_id: Mapped[Optional[int]] = mapped_column(ForeignKey("procurement_budgets.id", ondelete="RESTRICT"), nullable=True, index=True)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="items")
    budget_department: Mapped[Optional["Department"]] = relationship(foreign_keys=[budget_department_id])
    budget: Mapped[Optional["ProcurementBudget"]] = relationship()
    medication: Mapped[Optional["MedicationMaster"]] = relationship()


class GoodsReceiptNote(AuditMixin, Base):
    """Document verifying delivery inspection and physical stock arrival."""
    __tablename__ = "procurement_grn"
    __table_args__ = (
        Index("ix_grn_po_id", "po_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grn_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("procurement_purchase_orders.id"), nullable=False)
    location_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pharmacy_locations.id"), nullable=True, index=True)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    invoice_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[GRNStatusEnum] = mapped_column(default=GRNStatusEnum.PENDING_INSPECTION, nullable=False)
    inspected_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    inspection_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    purchase_order: Mapped["PurchaseOrder"] = relationship()
    location: Mapped[Optional["PharmacyLocation"]] = relationship()
    inspected_by: Mapped[Optional["User"]] = relationship(foreign_keys=[inspected_by_id])
    items: Mapped[List["GoodsReceiptItem"]] = relationship(back_populates="grn", cascade="all, delete-orphan")


class GoodsReceiptItem(AuditMixin, Base):
    """Specific stock items checked into inventory batches upon GRN acceptance."""
    __tablename__ = "procurement_grn_items"
    __table_args__ = (
        CheckConstraint("received_quantity >= 0", name="ck_grn_rcv_qty_non_neg"),
        CheckConstraint("accepted_quantity >= 0", name="ck_grn_acc_qty_non_neg"),
        CheckConstraint("accepted_quantity <= received_quantity", name="ck_grn_acc_lte_rcv"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    grn_id: Mapped[int] = mapped_column(ForeignKey("procurement_grn.id", ondelete="CASCADE"), nullable=False, index=True)
    po_item_id: Mapped[int] = mapped_column(ForeignKey("procurement_po_items.id"), nullable=False, index=True)
    batch_number: Mapped[str] = mapped_column(String(50), nullable=False)
    expiry_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    accepted_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    rejected_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    unit_price_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    purchase_uom_code: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    base_uom_code: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    units_per_purchase_unit: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    base_quantity: Mapped[Optional[float]] = mapped_column(Numeric(20, 6), nullable=True)
    base_unit_price_paise: Mapped[Optional[float]] = mapped_column(Numeric(24, 8), nullable=True)
    created_batch_id: Mapped[Optional[int]] = mapped_column(ForeignKey("inventory_batches.id"), nullable=True, index=True)

    grn: Mapped["GoodsReceiptNote"] = relationship(back_populates="items")
    po_item: Mapped["PurchaseOrderItem"] = relationship()
    created_batch: Mapped[Optional["InventoryBatch"]] = relationship()


class StoreIndent(AuditMixin, Base):
    """Ward or Department request for consumables/medicines from the Central Pharmacy/Store either for ward stock or a specific patient."""
    __tablename__ = "procurement_indents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    indent_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    requesting_department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), nullable=False, index=True)

    encounter_id: Mapped[Optional[int]] = mapped_column(ForeignKey("patient_encounters.id"), nullable=True, index=True)

    status: Mapped[IndentStatusEnum] = mapped_column(default=IndentStatusEnum.PENDING, nullable=False)
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    approved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    remarks: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    encounter: Mapped[Optional["PatientEncounter"]] = relationship()

    requesting_department: Mapped["Department"] = relationship()
    requested_by: Mapped["User"] = relationship(foreign_keys=[requested_by_id])
    approved_by: Mapped[Optional["User"]] = relationship(foreign_keys=[approved_by_id])
    items: Mapped[List["StoreIndentItem"]] = relationship(back_populates="indent", cascade="all, delete-orphan")


class StoreIndentItem(AuditMixin, Base):
    """Individual line items requested in an Indent."""
    __tablename__ = "procurement_indent_items"
    __table_args__ = (
        CheckConstraint("requested_quantity > 0", name="ck_indent_req_qty_pos"),
        CheckConstraint("issued_quantity >= 0", name="ck_indent_iss_qty_non_neg"),
        CheckConstraint("issued_quantity <= requested_quantity", name="ck_indent_no_overissue"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    indent_id: Mapped[int] = mapped_column(ForeignKey("procurement_indents.id", ondelete="CASCADE"), nullable=False, index=True)
    medication_id: Mapped[int] = mapped_column(ForeignKey("medication_master.id"), nullable=False, index=True)
    requested_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    issued_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    indent: Mapped["StoreIndent"] = relationship(back_populates="items")
    medication: Mapped["MedicationMaster"] = relationship()

class VendorInvoice(AuditMixin, Base):
    """Vendor tax invoice uploaded for procurement settlement and 3-way matching."""
    __tablename__ = "procurement_vendor_invoices"
    __table_args__ = (
        UniqueConstraint("vendor_id", "invoice_number", name="uq_vendor_invoice_number"),
        CheckConstraint("total_amount_paise >= 0", name="ck_invoice_total_non_neg"),
        Index("ix_vendor_inv_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendors.id"), nullable=False, index=True)
    po_id: Mapped[Optional[int]] = mapped_column(ForeignKey("procurement_purchase_orders.id"), nullable=True, index=True)
    grn_id: Mapped[Optional[int]] = mapped_column(ForeignKey("procurement_grn.id"), nullable=True, index=True)

    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    invoice_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    subtotal_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_amount_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    discount_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[VendorInvoiceStatusEnum] = mapped_column(
        Enum(VendorInvoiceStatusEnum), default=VendorInvoiceStatusEnum.PENDING_VERIFICATION, nullable=False
    )
    document_file_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    verified_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    linked_expense_id: Mapped[Optional[int]] = mapped_column(ForeignKey("finance_expenses.id"), nullable=True, index=True)

    vendor: Mapped["VendorMaster"] = relationship()
    purchase_order: Mapped[Optional["PurchaseOrder"]] = relationship()
    grn: Mapped[Optional["GoodsReceiptNote"]] = relationship()
    verified_by: Mapped[Optional["User"]] = relationship(foreign_keys=[verified_by_id])
    items: Mapped[List["VendorInvoiceItem"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")




class SupplierAdjustmentTypeEnum(str, PyEnum):
    SUPPLIER_CREDIT_NOTE = "SUPPLIER_CREDIT_NOTE"
    HOSPITAL_DEBIT_NOTE = "HOSPITAL_DEBIT_NOTE"


class SupplierAdjustmentStatusEnum(str, PyEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SupplierAdjustment(AuditMixin, Base):
    """Supplier-issued credit or hospital-issued debit note; application is tracked separately."""
    __tablename__ = "procurement_supplier_adjustments"
    __table_args__ = (
        UniqueConstraint("vendor_id", "adjustment_type", "document_number", name="uq_supplier_adjustment_document"),
        CheckConstraint("amount_paise > 0", name="ck_supplier_adjustment_amount_positive"),
        Index("ix_supplier_adjustment_vendor_date", "vendor_id", "document_date"),
        Index("ix_supplier_adjustment_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendors.id", ondelete="RESTRICT"), nullable=False)
    adjustment_type: Mapped[SupplierAdjustmentTypeEnum] = mapped_column(Enum(SupplierAdjustmentTypeEnum), nullable=False)
    document_number: Mapped[str] = mapped_column(String(100), nullable=False)
    document_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[SupplierAdjustmentStatusEnum] = mapped_column(Enum(SupplierAdjustmentStatusEnum), default=SupplierAdjustmentStatusEnum.PENDING, nullable=False)
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SupplierAdjustmentApplication(Base):
    """Immutable application of an approved supplier adjustment against one invoice."""
    __tablename__ = "procurement_supplier_adjustment_applications"
    __table_args__ = (
        UniqueConstraint("adjustment_id", "invoice_id", name="uq_supplier_adjustment_invoice"),
        CheckConstraint("amount_paise > 0", name="ck_supplier_adjustment_application_positive"),
        Index("ix_supplier_adjustment_application_invoice", "invoice_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    adjustment_id: Mapped[int] = mapped_column(ForeignKey("procurement_supplier_adjustments.id", ondelete="RESTRICT"), nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendor_invoices.id", ondelete="RESTRICT"), nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)


class SupplierAdvance(AuditMixin, Base):
    """Cash paid to a supplier in advance; not an invoice payment until allocated."""
    __tablename__ = "procurement_supplier_advances"
    __table_args__ = (
        UniqueConstraint("vendor_id", "advance_reference", name="uq_supplier_advance_reference"),
        CheckConstraint("amount_paise > 0", name="ck_supplier_advance_amount_positive"),
        Index("ix_supplier_advance_vendor_date", "vendor_id", "advance_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendors.id", ondelete="RESTRICT"), nullable=False)
    advance_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    payment_method: Mapped[SupplierPaymentMethodEnum] = mapped_column(Enum(SupplierPaymentMethodEnum), nullable=False)
    advance_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)


class SupplierAdvanceAllocation(Base):
    """Immutable application of a recorded supplier advance to an approved invoice."""
    __tablename__ = "procurement_supplier_advance_allocations"
    __table_args__ = (
        UniqueConstraint("advance_id", "invoice_id", name="uq_supplier_advance_invoice"),
        CheckConstraint("amount_paise > 0", name="ck_supplier_advance_allocation_positive"),
        Index("ix_supplier_advance_allocation_invoice", "invoice_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    advance_id: Mapped[int] = mapped_column(ForeignKey("procurement_supplier_advances.id", ondelete="RESTRICT"), nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendor_invoices.id", ondelete="RESTRICT"), nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)




class BankStatementDirectionEnum(str, PyEnum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class BankStatementBatch(AuditMixin, Base):
    """Imported bank statement header; original statement totals are retained for audit."""
    __tablename__ = "procurement_bank_statement_batches"
    __table_args__ = (
        UniqueConstraint("bank_account_ref", "statement_reference", name="uq_bank_statement_account_reference"),
        CheckConstraint("period_end >= period_start", name="ck_bank_statement_period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bank_account_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    statement_reference: Mapped[str] = mapped_column(String(120), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    opening_balance_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    closing_balance_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    imported_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)


class BankStatementLine(Base):
    """Immutable imported bank transaction line; amounts are always positive with direction separate."""
    __tablename__ = "procurement_bank_statement_lines"
    __table_args__ = (
        UniqueConstraint("bank_account_ref", "bank_transaction_id", name="uq_bank_statement_transaction"),
        CheckConstraint("amount_paise > 0", name="ck_bank_statement_line_amount_positive"),
        Index("ix_bank_statement_line_batch_date", "batch_id", "transaction_date"),
        Index("ix_bank_statement_line_reference", "bank_reference"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("procurement_bank_statement_batches.id", ondelete="RESTRICT"), nullable=False)
    bank_account_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    bank_transaction_id: Mapped[str] = mapped_column(String(150), nullable=False)
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    direction: Mapped[BankStatementDirectionEnum] = mapped_column(Enum(BankStatementDirectionEnum), nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    bank_reference: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SupplierPaymentBankMatch(Base):
    """Append-only match between a bank debit line and a recorded supplier payment."""
    __tablename__ = "procurement_supplier_payment_bank_matches"
    __table_args__ = (
        CheckConstraint("amount_paise > 0", name="ck_supplier_payment_bank_match_positive"),
        Index("ix_supplier_payment_bank_match_payment", "payment_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    statement_line_id: Mapped[int] = mapped_column(ForeignKey("procurement_bank_statement_lines.id", ondelete="RESTRICT"), nullable=False)
    payment_id: Mapped[int] = mapped_column(ForeignKey("procurement_supplier_payments.id", ondelete="RESTRICT"), nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    matched_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    match_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SupplierPayment(AuditMixin, Base):
    """Immutable recorded outflow to a supplier; allocations identify invoices settled."""
    __tablename__ = "procurement_supplier_payments"
    __table_args__ = (
        UniqueConstraint("vendor_id", "payment_reference", name="uq_supplier_payment_vendor_reference"),
        CheckConstraint("amount_paise > 0", name="ck_supplier_payment_amount_positive"),
        Index("ix_supplier_payment_vendor_date", "vendor_id", "payment_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendors.id", ondelete="RESTRICT"), nullable=False)
    payment_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    payment_method: Mapped[SupplierPaymentMethodEnum] = mapped_column(Enum(SupplierPaymentMethodEnum), nullable=False)
    payment_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    allocations: Mapped[List["SupplierPaymentAllocation"]] = relationship(back_populates="payment", cascade="all, delete-orphan")


class SupplierPaymentAllocation(Base):
    """Append-only allocation of a supplier payment to one verified invoice."""
    __tablename__ = "procurement_supplier_payment_allocations"
    __table_args__ = (
        UniqueConstraint("payment_id", "invoice_id", name="uq_supplier_payment_invoice_allocation"),
        CheckConstraint("amount_paise > 0", name="ck_supplier_payment_allocation_positive"),
        Index("ix_supplier_payment_allocation_invoice", "invoice_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("procurement_supplier_payments.id", ondelete="RESTRICT"), nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendor_invoices.id", ondelete="RESTRICT"), nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    payment: Mapped["SupplierPayment"] = relationship(back_populates="allocations")


class SupplierPaymentRequest(AuditMixin, Base):
    """Scheduled supplier outflow awaiting independent approval and execution."""
    __tablename__ = "procurement_supplier_payment_requests"
    __table_args__ = (
        UniqueConstraint("vendor_id", "payment_reference", name="uq_supplier_payment_request_reference"),
        CheckConstraint("amount_paise > 0", name="ck_supplier_payment_request_amount_positive"),
        CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','EXECUTED','CANCELLED')", name="ck_supplier_payment_request_status"),
        Index("ix_supplier_payment_request_status_date", "status", "scheduled_date"),
        Index("ix_supplier_payment_request_run", "payment_run_reference"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendors.id", ondelete="RESTRICT"), nullable=False)
    payment_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    payment_method: Mapped[SupplierPaymentMethodEnum] = mapped_column(Enum(SupplierPaymentMethodEnum), nullable=False)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_run_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    executed_payment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("procurement_supplier_payments.id", ondelete="RESTRICT"), nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    allocations: Mapped[List["SupplierPaymentRequestAllocation"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )


class SupplierPaymentRequestAllocation(Base):
    """Invoice-level reservation made by a pending or approved payment request."""
    __tablename__ = "procurement_supplier_payment_request_allocations"
    __table_args__ = (
        UniqueConstraint("request_id", "invoice_id", name="uq_supplier_payment_request_invoice"),
        CheckConstraint("amount_paise > 0", name="ck_supplier_payment_request_allocation_positive"),
        Index("ix_supplier_payment_request_allocation_invoice", "invoice_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("procurement_supplier_payment_requests.id", ondelete="RESTRICT"), nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendor_invoices.id", ondelete="RESTRICT"), nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    request: Mapped["SupplierPaymentRequest"] = relationship(back_populates="allocations")


class ProcurementDocumentDownloadAudit(Base):
    """Records authorized requests to download a procurement invoice document."""
    __tablename__ = "procurement_document_download_audits"
    __table_args__ = (
        Index("ix_proc_doc_download_invoice_time", "invoice_id", "requested_at"),
        Index("ix_proc_doc_download_actor_time", "actor_user_id", "requested_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("procurement_vendor_invoices.id", ondelete="SET NULL"),
        nullable=True,
    )
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_email: Mapped[str] = mapped_column(String(255), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class VendorInvoiceItem(AuditMixin, Base):
    """Line item details extracted or mapped from the vendor invoice."""
    __tablename__ = "procurement_vendor_invoice_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_inv_item_qty_pos"),
        CheckConstraint("unit_price_paise >= 0", name="ck_inv_item_price_non_neg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendor_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    po_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("procurement_po_items.id"), nullable=True, index=True)
    medication_id: Mapped[Optional[int]] = mapped_column(ForeignKey("medication_master.id"), nullable=True, index=True)

    item_description: Mapped[str] = mapped_column(String(200), nullable=False)
    batch_number: Mapped[str] = mapped_column(String(50), nullable=False)
    expiry_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_percentage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # e.g., 5, 12, 18
    total_price_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    purchase_uom_code: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    base_uom_code: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    units_per_purchase_unit: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    base_quantity: Mapped[Optional[float]] = mapped_column(Numeric(20, 6), nullable=True)
    base_unit_price_paise: Mapped[Optional[float]] = mapped_column(Numeric(24, 8), nullable=True)

    invoice: Mapped["VendorInvoice"] = relationship(back_populates="items")

class SupplierQuotationStatusEnum(str, PyEnum):
    RECEIVED = "RECEIVED"
    SELECTED = "SELECTED"
    NOT_SELECTED = "NOT_SELECTED"
    WITHDRAWN = "WITHDRAWN"


class SupplierQuotation(AuditMixin, Base):
    """A supplier's commercial offer recorded against an approved purchase requisition."""
    __tablename__ = "procurement_supplier_quotations"
    __table_args__ = (
        UniqueConstraint("vendor_id", "quotation_number", name="uq_proc_quote_vendor_number"),
        Index("ix_proc_quote_requisition_status", "requisition_id", "status"),
        CheckConstraint("total_amount_paise >= 0", name="ck_proc_quote_total_non_neg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    requisition_id: Mapped[int] = mapped_column(ForeignKey("procurement_requisitions.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendors.id"), nullable=False, index=True)
    quotation_number: Mapped[str] = mapped_column(String(100), nullable=False)
    quoted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payment_terms: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[SupplierQuotationStatusEnum] = mapped_column(
        Enum(SupplierQuotationStatusEnum), default=SupplierQuotationStatusEnum.RECEIVED, nullable=False
    )
    selected_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    selected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    selection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    requisition: Mapped["PurchaseRequisition"] = relationship()
    vendor: Mapped["VendorMaster"] = relationship()
    selected_by: Mapped[Optional["User"]] = relationship(foreign_keys=[selected_by_id])
    items: Mapped[List["SupplierQuotationItem"]] = relationship(back_populates="quotation", cascade="all, delete-orphan")


class SupplierQuotationItem(AuditMixin, Base):
    """Supplier price and delivery offer for one approved requisition line."""
    __tablename__ = "procurement_supplier_quotation_items"
    __table_args__ = (
        UniqueConstraint("quotation_id", "requisition_item_id", name="uq_proc_quote_item_line"),
        CheckConstraint("quantity_quoted > 0", name="ck_proc_quote_qty_pos"),
        CheckConstraint("unit_price_paise >= 0", name="ck_proc_quote_price_non_neg"),
        CheckConstraint("tax_percentage >= 0 AND tax_percentage <= 100", name="ck_proc_quote_tax_range"),
        CheckConstraint("tax_amount_paise >= 0", name="ck_proc_quote_tax_non_neg"),
        CheckConstraint("line_total_paise = quantity_quoted * unit_price_paise + tax_amount_paise", name="ck_proc_quote_line_total"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quotation_id: Mapped[int] = mapped_column(ForeignKey("procurement_supplier_quotations.id", ondelete="CASCADE"), nullable=False, index=True)
    requisition_item_id: Mapped[int] = mapped_column(ForeignKey("procurement_requisition_items.id"), nullable=False, index=True)
    quantity_quoted: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_percentage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tax_amount_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    line_total_paise: Mapped[int] = mapped_column(Integer, nullable=False)  # tax-inclusive line total
    purchase_uom_code: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    base_uom_code: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    units_per_purchase_unit: Mapped[Optional[float]] = mapped_column(Numeric(18, 6), nullable=True)
    base_quantity: Mapped[Optional[float]] = mapped_column(Numeric(20, 6), nullable=True)
    base_unit_price_paise: Mapped[Optional[float]] = mapped_column(Numeric(24, 8), nullable=True)

    quotation: Mapped["SupplierQuotation"] = relationship(back_populates="items")
    requisition_item: Mapped["PurchaseRequisitionItem"] = relationship()


class PurchaseOrderApprovalAuthority(AuditMixin, Base):
    """Role-based maximum PO amount that a member may approve; amounts are paise."""
    __tablename__ = "procurement_po_approval_authorities"
    __table_args__ = (
        CheckConstraint("max_amount_paise >= 0", name="ck_po_approval_limit_non_neg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, unique=True)
    max_amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    role: Mapped["Role"] = relationship()


class PurchaseOrderAmendment(AuditMixin, Base):
    """Proposed revision with immutable before/after snapshots and independent review."""
    __tablename__ = "procurement_po_amendments"
    __table_args__ = (
        UniqueConstraint("po_id", "version", name="uq_po_amendment_version"),
        Index("ix_po_amendment_po_status", "po_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("procurement_purchase_orders.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    prior_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    proposed_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[POAmendmentStatusEnum] = mapped_column(
        Enum(POAmendmentStatusEnum), default=POAmendmentStatusEnum.PENDING, nullable=False
    )
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    purchase_order: Mapped["PurchaseOrder"] = relationship()
    reviewed_by: Mapped[Optional["User"]] = relationship(foreign_keys=[reviewed_by_id])


class PurchaseOrderShipment(AuditMixin, Base):
    """Shipment-level carrier tracking; does not substitute for hospital GRN acceptance."""
    __tablename__ = "procurement_po_shipments"
    __table_args__ = (
        Index("ix_po_shipment_po_status", "po_id", "status"),
        Index("ix_po_shipment_expected_status", "expected_delivery_at", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("procurement_purchase_orders.id", ondelete="CASCADE"), nullable=False)
    carrier: Mapped[str] = mapped_column(String(120), nullable=False)
    tracking_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    expected_delivery_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dispatched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[POShipmentStatusEnum] = mapped_column(
        Enum(POShipmentStatusEnum), default=POShipmentStatusEnum.PLANNED, nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="shipments")
    events: Mapped[List["PurchaseOrderShipmentEvent"]] = relationship(
        back_populates="shipment", cascade="all, delete-orphan", order_by="PurchaseOrderShipmentEvent.event_at"
    )


class PurchaseOrderShipmentEvent(Base):
    """Append-only carrier milestone and exception history."""
    __tablename__ = "procurement_po_shipment_events"
    __table_args__ = (
        Index("ix_po_shipment_event_shipment_time", "shipment_id", "event_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("procurement_po_shipments.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[POShipmentStatusEnum] = mapped_column(Enum(POShipmentStatusEnum), nullable=False)
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    shipment: Mapped["PurchaseOrderShipment"] = relationship(back_populates="events")
    actor: Mapped[Optional["User"]] = relationship()


class ProcurementUnitOfMeasure(Base):
    """Canonical purchasing or inventory unit; seeded values are shared within a branch database."""
    __tablename__ = "procurement_units_of_measure"
    __table_args__ = (
        CheckConstraint("dimension IN ('COUNT', 'MASS', 'VOLUME', 'LENGTH')", name="ck_proc_uom_dimension"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    dimension: Mapped[str] = mapped_column(String(16), nullable=False)
    allows_fractional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_packaging_unit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MedicationPriceControl(AuditMixin, Base):
    """Explicit per-medication threshold for normalized purchase-price escalation."""
    __tablename__ = "procurement_medication_price_controls"
    __table_args__ = (
        CheckConstraint("max_variance_pct >= 0 AND max_variance_pct <= 1000", name="ck_med_price_control_variance_range"),
        CheckConstraint("minimum_observations >= 2 AND minimum_observations <= 100", name="ck_med_price_control_min_observations"),
        CheckConstraint("lookback_days >= 1 AND lookback_days <= 1825", name="ck_med_price_control_lookback_days"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    medication_id: Mapped[int] = mapped_column(ForeignKey("medication_master.id", ondelete="RESTRICT"), nullable=False, unique=True)
    max_variance_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_observations: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    lookback_days: Mapped[int] = mapped_column(Integer, default=180, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    medication: Mapped["MedicationMaster"] = relationship()


class PurchaseOrderPriceReview(AuditMixin, Base):
    """Immutable evidence and reason for accepting a PO above its comparable price threshold."""
    __tablename__ = "procurement_po_price_reviews"
    __table_args__ = (
        UniqueConstraint("po_id", "po_item_id", name="uq_po_price_review_line"),
        CheckConstraint("benchmark_observations >= 0", name="ck_po_price_review_observations_non_neg"),
        CheckConstraint("threshold_pct >= 0", name="ck_po_price_review_threshold_non_neg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("procurement_purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    po_item_id: Mapped[int] = mapped_column(ForeignKey("procurement_po_items.id", ondelete="CASCADE"), nullable=False)
    medication_id: Mapped[int] = mapped_column(ForeignKey("medication_master.id", ondelete="RESTRICT"), nullable=False)
    base_uom_code: Mapped[str] = mapped_column(String(24), nullable=False)
    proposed_base_unit_price_paise: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    benchmark_median_paise: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    benchmark_min_paise: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    benchmark_max_paise: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    benchmark_observations: Mapped[int] = mapped_column(Integer, nullable=False)
    threshold_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    variance_pct: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    override_reason: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MedicationPackConfiguration(AuditMixin, Base):
    """Effective-dated, auditable conversion from a medication purchase unit to its stock base unit."""
    __tablename__ = "procurement_medication_pack_configurations"
    __table_args__ = (
        CheckConstraint("units_per_purchase_unit > 0", name="ck_med_pack_conversion_positive"),
        CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="ck_med_pack_effective_window"),
        UniqueConstraint("medication_id", "purchase_uom_id", "effective_from", name="uq_med_pack_effective_start"),
        Index("ix_med_pack_medication_active", "medication_id", "is_active"),
        Index(
            "uq_med_pack_active_purchase_uom", "medication_id", "purchase_uom_id",
            unique=True, postgresql_where=text("is_active = true"),
            sqlite_where=text("is_active = 1"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    medication_id: Mapped[int] = mapped_column(ForeignKey("medication_master.id", ondelete="RESTRICT"), nullable=False)
    purchase_uom_id: Mapped[int] = mapped_column(ForeignKey("procurement_units_of_measure.id", ondelete="RESTRICT"), nullable=False)
    base_uom_id: Mapped[int] = mapped_column(ForeignKey("procurement_units_of_measure.id", ondelete="RESTRICT"), nullable=False)
    units_per_purchase_unit: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    medication: Mapped["MedicationMaster"] = relationship()
    purchase_uom: Mapped["ProcurementUnitOfMeasure"] = relationship(foreign_keys=[purchase_uom_id])
    base_uom: Mapped["ProcurementUnitOfMeasure"] = relationship(foreign_keys=[base_uom_id])


class ProcurementBudget(AuditMixin, Base):
    """Department/category allocation for a defined annual or quarterly period."""
    __tablename__ = "procurement_budgets"
    __table_args__ = (
        CheckConstraint("period_type IN ('ANNUAL', 'QUARTERLY')", name="ck_proc_budget_period_type"),
        CheckConstraint("category IN ('PHARMACY', 'LABORATORY', 'GENERAL_SUPPLIES', 'EQUIPMENT', 'SERVICES', 'OTHER')", name="ck_proc_budget_category"),
        CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'CLOSED')", name="ck_proc_budget_status"),
        CheckConstraint("period_end >= period_start", name="ck_proc_budget_period_valid"),
        CheckConstraint("total_amount_paise >= 0", name="ck_proc_budget_amount_non_neg"),
        CheckConstraint("warning_threshold_pct >= 1 AND warning_threshold_pct <= 100", name="ck_proc_budget_warning_range"),
        UniqueConstraint("requesting_department_id", "category", "period_start", "period_end", name="uq_proc_budget_department_category_period"),
        Index("ix_proc_budget_period_status", "period_start", "period_end", "status"),
        Index("ix_proc_budget_department_category", "requesting_department_id", "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    budget_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    parent_budget_id: Mapped[Optional[int]] = mapped_column(ForeignKey("procurement_budgets.id", ondelete="RESTRICT"), nullable=True, index=True)
    requesting_department_id: Mapped[int] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False)
    period_type: Mapped[str] = mapped_column(String(12), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    total_amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    warning_threshold_pct: Mapped[int] = mapped_column(Integer, default=80, nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="DRAFT", nullable=False)

    department: Mapped["Department"] = relationship()
    parent_budget: Mapped[Optional["ProcurementBudget"]] = relationship(
        remote_side="ProcurementBudget.id", foreign_keys=[parent_budget_id]
    )


class ProcurementBudgetRevision(AuditMixin, Base):
    """Maker-checker request to change an active budget's approved allocation."""
    __tablename__ = "procurement_budget_revisions"
    __table_args__ = (
        UniqueConstraint("budget_id", "revision_number", name="uq_proc_budget_revision_number"),
        Index("ix_proc_budget_revision_status", "budget_id", "status"),
        CheckConstraint("proposed_amount_paise >= 0", name="ck_proc_budget_revision_amount_non_neg"),
        CheckConstraint("status IN ('PENDING', 'APPROVED', 'REJECTED')", name="ck_proc_budget_revision_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    budget_id: Mapped[int] = mapped_column(ForeignKey("procurement_budgets.id", ondelete="RESTRICT"), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    prior_amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    proposed_amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="PENDING", nullable=False)
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    budget: Mapped["ProcurementBudget"] = relationship()
    reviewed_by: Mapped[Optional["User"]] = relationship(foreign_keys=[reviewed_by_id])


class ProcurementBudgetMovement(AuditMixin, Base):
    """Append-only monetary ledger for PO commitments and accepted receipt consumption."""
    __tablename__ = "procurement_budget_movements"
    __table_args__ = (
        CheckConstraint("movement_type IN ('RESERVATION', 'RELEASE', 'RECEIPT')", name="ck_proc_budget_movement_type"),
        CheckConstraint("amount_paise > 0", name="ck_proc_budget_movement_amount_positive"),
        UniqueConstraint("reference_key", name="uq_proc_budget_movement_reference"),
        Index("ix_proc_budget_movement_budget_type", "budget_id", "movement_type"),
        Index("ix_proc_budget_movement_po", "po_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    budget_id: Mapped[int] = mapped_column(ForeignKey("procurement_budgets.id", ondelete="RESTRICT"), nullable=False)
    po_id: Mapped[int] = mapped_column(ForeignKey("procurement_purchase_orders.id", ondelete="RESTRICT"), nullable=False)
    # Historical numeric identifiers intentionally have no FK: PO amendment replaces line rows.
    po_item_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    grn_item_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    movement_type: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_key: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    budget: Mapped["ProcurementBudget"] = relationship()
    purchase_order: Mapped["PurchaseOrder"] = relationship()
    actor: Mapped["User"] = relationship(foreign_keys=[actor_user_id])



class SupplierComplianceDocument(Base):
    """Vendor-level regulatory evidence; upload does not itself establish legal validity."""
    __tablename__ = "procurement_supplier_compliance_documents"
    __table_args__ = (
        CheckConstraint("status IN ('PENDING_VERIFICATION','VERIFIED','REJECTED')", name="ck_supplier_compliance_status"),
        CheckConstraint("expiry_date IS NULL OR issue_date IS NULL OR expiry_date >= issue_date", name="ck_supplier_compliance_dates"),
        Index("ix_supplier_compliance_vendor_type", "vendor_id", "document_type"),
        Index("ix_supplier_compliance_expiry_status", "status", "expiry_date"),
        UniqueConstraint("storage_key", name="uq_supplier_compliance_storage_key"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendors.id", ondelete="RESTRICT"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    document_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    issuer: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    issue_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="PENDING_VERIFICATION", nullable=False)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    verified_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vendor: Mapped["VendorMaster"] = relationship()
    uploaded_by: Mapped["User"] = relationship(foreign_keys=[uploaded_by_id])
    verified_by: Mapped[Optional["User"]] = relationship(foreign_keys=[verified_by_id])



class SupplierCompliancePolicy(Base):
    """Tenant-configured mandatory evidence rules for each supplier category."""
    __tablename__ = "procurement_supplier_compliance_policies"
    __table_args__ = (
        UniqueConstraint("vendor_category", "document_type", name="uq_supplier_compliance_policy_scope"),
        CheckConstraint("vendor_category IN ('PHARMACEUTICALS','SURGICAL_IMPLANTS','LAB_REAGENTS','EQUIPMENT_MAINTENANCE','GENERAL_SUPPLIES')", name="ck_supplier_compliance_policy_category"),
        CheckConstraint("length(document_type) BETWEEN 2 AND 40", name="ck_supplier_compliance_policy_document_type"),
        Index("ix_supplier_compliance_policy_category_required", "vendor_category", "is_required"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_category: Mapped[str] = mapped_column(String(40), nullable=False)
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    updated_by: Mapped["User"] = relationship()



class SupplierCompliancePolicyAudit(Base):
    """Immutable history of changes to mandatory supplier evidence requirements."""
    __tablename__ = "procurement_supplier_compliance_policy_audits"
    __table_args__ = (
        Index("ix_supplier_compliance_policy_audit_policy_time", "policy_id", "changed_at"),
        Index("ix_supplier_compliance_policy_audit_actor_time", "changed_by_id", "changed_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[Optional[int]] = mapped_column(ForeignKey("procurement_supplier_compliance_policies.id", ondelete="SET NULL"), nullable=True)
    vendor_category: Mapped[str] = mapped_column(String(40), nullable=False)
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    previous_is_required: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    new_is_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    changed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    changed_by_email: Mapped[str] = mapped_column(String(255), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SupplierComplianceDocumentDownloadAudit(Base):
    """Append-only access record for supplier regulatory documents."""
    __tablename__ = "procurement_supplier_compliance_download_audits"
    __table_args__ = (
        Index("ix_supplier_compliance_audit_doc_time", "document_id", "requested_at"),
        Index("ix_supplier_compliance_audit_actor_time", "actor_user_id", "requested_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[Optional[int]] = mapped_column(ForeignKey("procurement_supplier_compliance_documents.id", ondelete="SET NULL"), nullable=True)
    vendor_name: Mapped[str] = mapped_column(String(150), nullable=False)
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_email: Mapped[str] = mapped_column(String(255), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SupplierContract(AuditMixin, Base):
    """Structured supplier agreement; signed evidence remains in tenant document storage."""
    __tablename__ = "procurement_supplier_contracts"
    __table_args__ = (
        UniqueConstraint("vendor_id", "contract_number", name="uq_proc_contract_vendor_number"),
        CheckConstraint("valid_to >= valid_from", name="ck_proc_contract_valid_period"),
        CheckConstraint("renewal_notice_days >= 0 AND renewal_notice_days <= 730", name="ck_proc_contract_notice_days"),
        CheckConstraint("status IN ('DRAFT','PENDING_APPROVAL','ACTIVE','EXPIRED','TERMINATED')", name="ck_proc_contract_status"),
        Index("ix_proc_contract_vendor_status", "vendor_id", "status"),
        Index("ix_proc_contract_validity", "status", "valid_to"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendors.id", ondelete="RESTRICT"), nullable=False)
    contract_number: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)
    renewal_notice_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="DRAFT", nullable=False)
    payment_terms: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    document_file_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    terminated_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    terminated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    termination_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vendor: Mapped["VendorMaster"] = relationship()
    approved_by: Mapped[Optional["User"]] = relationship(foreign_keys=[approved_by_id])
    rates: Mapped[List["SupplierContractRate"]] = relationship(back_populates="contract", cascade="all, delete-orphan")


class SupplierContractRate(AuditMixin, Base):
    """A negotiated price for one medication or procurement category and UOM."""
    __tablename__ = "procurement_supplier_contract_rates"
    __table_args__ = (
        CheckConstraint("scope_type IN ('MEDICATION','CATEGORY')", name="ck_proc_contract_rate_scope"),
        CheckConstraint("(scope_type = 'MEDICATION' AND medication_id IS NOT NULL AND category IS NULL) OR (scope_type = 'CATEGORY' AND medication_id IS NULL AND category IS NOT NULL)", name="ck_proc_contract_rate_scope_target"),
        CheckConstraint("unit_price_paise >= 0", name="ck_proc_contract_rate_price_non_neg"),
        CheckConstraint("tax_percentage >= 0 AND tax_percentage <= 100", name="ck_proc_contract_rate_tax_range"),
        UniqueConstraint("contract_id", "scope_type", "medication_id", "category", "uom_code", name="uq_proc_contract_rate_scope_uom"),
        Index("ix_proc_contract_rate_medication", "medication_id", "uom_code"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("procurement_supplier_contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False)
    medication_id: Mapped[Optional[int]] = mapped_column(ForeignKey("medication_master.id", ondelete="RESTRICT"), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    uom_code: Mapped[str] = mapped_column(String(24), nullable=False)
    unit_price_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_percentage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    contract: Mapped["SupplierContract"] = relationship(back_populates="rates")
    medication: Mapped[Optional["MedicationMaster"]] = relationship()


class SupplierContractRevision(Base):
    """Immutable record of proposed contract amendments and independent decisions."""
    __tablename__ = "procurement_supplier_contract_revisions"
    __table_args__ = (
        UniqueConstraint("contract_id", "revision_number", name="uq_proc_contract_revision_number"),
        CheckConstraint("status IN ('PENDING','APPROVED','REJECTED')", name="ck_proc_contract_revision_status"),
        Index("ix_proc_contract_revision_status", "contract_id", "status"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("procurement_supplier_contracts.id", ondelete="RESTRICT"), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    prior_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    proposed_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="PENDING", nullable=False)
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    contract: Mapped["SupplierContract"] = relationship()
    requested_by: Mapped["User"] = relationship(foreign_keys=[requested_by_id])
    reviewed_by: Mapped[Optional["User"]] = relationship(foreign_keys=[reviewed_by_id])


class SupplierContractDocumentDownloadAudit(Base):
    """Audit trail for access to confidential signed supplier agreements."""
    __tablename__ = "procurement_contract_document_download_audits"
    __table_args__ = (
        Index("ix_proc_contract_doc_audit_contract_time", "contract_id", "requested_at"),
        Index("ix_proc_contract_doc_audit_actor_time", "actor_user_id", "requested_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("procurement_supplier_contracts.id", ondelete="SET NULL"), nullable=True
    )
    contract_number: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_email: Mapped[str] = mapped_column(String(255), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProcurementReconciliationException(Base):
    """Persisted finance investigation item; state changes are separately journaled."""
    __tablename__ = "procurement_reconciliation_exceptions"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_proc_recon_exception_fingerprint"),
        CheckConstraint("status IN ('OPEN','IN_REVIEW','RESOLVED','DISMISSED')", name="ck_proc_recon_exception_status"),
        CheckConstraint("severity IN ('CRITICAL','HIGH','MEDIUM','LOW')", name="ck_proc_recon_exception_severity"),
        CheckConstraint("resolution_review_status IN ('NOT_REQUIRED','PENDING','APPROVED','REJECTED')", name="ck_proc_recon_resolution_review_status"),
        CheckConstraint("resolution_submitted_status IS NULL OR resolution_submitted_status IN ('RESOLVED','DISMISSED')", name="ck_proc_recon_resolution_submitted_status"),
        CheckConstraint("reopen_count >= 0", name="ck_proc_recon_exception_reopen_count_nonneg"),
        CheckConstraint("sla_target_hours IS NULL OR sla_target_hours BETWEEN 1 AND 8760", name="ck_proc_recon_exception_sla_target_positive"),
        CheckConstraint("sla_paused_seconds >= 0", name="ck_proc_recon_exception_sla_paused_seconds_nonneg"),
        Index("ix_proc_recon_exception_queue", "status", "severity", "last_detected_at"),
        Index("ix_proc_recon_exception_assignee", "assigned_to_id", "status"),
        Index("ix_proc_recon_exception_reference", "reference_type", "reference_id"),
        Index("ix_proc_recon_exception_sla_pause", "status", "sla_paused_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    exception_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(12), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", nullable=False)
    reference_type: Mapped[str] = mapped_column(String(40), nullable=False)
    reference_id: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matched_amount_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unmatched_amount_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    detection_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_present: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    missed_refresh_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    assigned_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    root_cause_code: Mapped[Optional[str]] = mapped_column(String(48), nullable=True)
    resolution_checklist: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    reopen_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resolution_review_status: Mapped[str] = mapped_column(String(16), default="NOT_REQUIRED", nullable=False)
    resolution_submitted_status: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    resolution_submitted_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolution_reviewed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolution_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_policy_id: Mapped[Optional[int]] = mapped_column(ForeignKey("procurement_reconciliation_sla_policies.id", ondelete="SET NULL"), nullable=True)
    sla_target_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sla_paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_paused_seconds: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=False)
    sla_breached_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_to: Mapped[Optional["User"]] = relationship(foreign_keys=[assigned_to_id])
    resolved_by: Mapped[Optional["User"]] = relationship(foreign_keys=[resolved_by_id])


class ProcurementReconciliationEvidence(Base):
    """Private, immutable evidence file attached to one finance investigation."""
    __tablename__ = "procurement_reconciliation_evidence"
    __table_args__ = (
        UniqueConstraint("storage_key", name="uq_proc_recon_evidence_storage_key"),
        CheckConstraint("evidence_type IN ('BANK_STATEMENT','PAYMENT_PROOF','INVOICE','SUPPLIER_CORRESPONDENCE','APPROVAL_RECORD','OTHER')", name="ck_proc_recon_evidence_type"),
        CheckConstraint("size_bytes > 0", name="ck_proc_recon_evidence_size"),
        Index("ix_proc_recon_evidence_exception_time", "exception_id", "uploaded_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exception_id: Mapped[int] = mapped_column(ForeignKey("procurement_reconciliation_exceptions.id", ondelete="RESTRICT"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(40), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256_hex: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProcurementReconciliationEvidenceDownloadAudit(Base):
    """Append-only audit of authorized evidence downloads."""
    __tablename__ = "procurement_reconciliation_evidence_download_audits"
    __table_args__ = (
        Index("ix_proc_recon_evidence_download_time", "exception_id", "requested_at"),
        Index("ix_proc_recon_evidence_download_actor", "actor_user_id", "requested_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_id: Mapped[Optional[int]] = mapped_column(ForeignKey("procurement_reconciliation_evidence.id", ondelete="SET NULL"), nullable=True)
    exception_id: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_email: Mapped[str] = mapped_column(String(255), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProcurementReconciliationExceptionEvent(Base):
    """Append-only investigation history for reconciliation exceptions."""
    __tablename__ = "procurement_reconciliation_exception_events"
    __table_args__ = (
        Index("ix_proc_recon_exception_event_time", "exception_id", "occurred_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exception_id: Mapped[int] = mapped_column(ForeignKey("procurement_reconciliation_exceptions.id", ondelete="RESTRICT"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    old_status: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    new_status: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    old_assignee_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    new_assignee_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProcurementReconciliationSlaPolicy(Base):
    """Versioned tenant-wide SLA targets for reconciliation investigations."""
    __tablename__ = "procurement_reconciliation_sla_policies"
    __table_args__ = (
        UniqueConstraint("policy_key", "version", name="uq_proc_recon_sla_policy_version"),
        CheckConstraint("version > 0", name="ck_proc_recon_sla_policy_version_positive"),
        CheckConstraint("status IN ('DRAFT','PUBLISHED','RETIRED')", name="ck_proc_recon_sla_policy_status"),
        CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="ck_proc_recon_sla_policy_effective_window"),
        Index("ix_proc_recon_sla_policy_effective", "status", "effective_from", "effective_to"),
        Index("uq_proc_recon_sla_policy_single_open", "policy_key", unique=True,
              postgresql_where=text("status = 'PUBLISHED' AND effective_to IS NULL"),
              sqlite_where=text("status = 'PUBLISHED' AND effective_to IS NULL")),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_key: Mapped[str] = mapped_column(String(48), default="DEFAULT", nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="DRAFT", nullable=False)
    severity_targets_hours: Mapped[dict] = mapped_column(JSON, nullable=False)
    change_reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    published_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ProcurementReconciliationSlaPolicyEvent(Base):
    """Append-only audit trail for SLA policy lifecycle changes."""
    __tablename__ = "procurement_reconciliation_sla_policy_events"
    __table_args__ = (
        Index("ix_proc_recon_sla_policy_event_time", "policy_id", "occurred_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("procurement_reconciliation_sla_policies.id", ondelete="RESTRICT"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
