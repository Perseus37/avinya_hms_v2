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

class VendorMaster(AuditMixin, Base):
    """Registered hospital suppliers, distributors, and manufacturers."""
    __tablename__ = "procurement_vendors"
    __table_args__ = (
        CheckConstraint("credit_period_days >= 0", name="ck_vendor_credit_days_non_neg"),
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
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendors.id", ondelete="RESTRICT"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    document_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    issuer: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    issue_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
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
