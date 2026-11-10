from datetime import date, datetime
from enum import Enum as PyEnum
from typing import List, Optional
from sqlalchemy import (
    DDL,
    event,
    Boolean,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.audit import AuditMixin
from backend.core.database import Base
from backend.domains.identity.models import Department, User
from backend.domains.encounters.models import PatientEncounter
from backend.domains.pharmacy.models import MedicationMaster, InventoryBatch

# PostgreSQL needs 64-bit paise values; SQLite INTEGER already stores signed 64-bit values.
PAISE_AMOUNT_TYPE = BigInteger().with_variant(Integer, "sqlite")
# from backend.domains.procurement.models import VendorMaster, PurchaseOrder, GoodsReceiptNote


class VendorCategoryEnum(str, PyEnum):
    PHARMACEUTICALS = "PHARMACEUTICALS"
    SURGICAL_IMPLANTS = "SURGICAL_IMPLANTS"
    LAB_REAGENTS = "LAB_REAGENTS"
    EQUIPMENT_MAINTENANCE = "EQUIPMENT_MAINTENANCE"
    GENERAL_SUPPLIES = "GENERAL_SUPPLIES"


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


class PurchaseOrder(AuditMixin, Base):
    """Official procurement order placed with a vendor."""
    __tablename__ = "procurement_purchase_orders"
    __table_args__ = (
        Index("ix_po_vendor_status", "vendor_id", "status"),
        CheckConstraint("total_amount_paise >= 0", name="ck_po_total_non_neg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendors.id"), nullable=False)
    status: Mapped[POStatusEnum] = mapped_column(default=POStatusEnum.DRAFT, nullable=False)
    delivery_due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payment_terms: Mapped[str] = mapped_column(String(255), nullable=False)
    total_amount_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    approved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    vendor: Mapped["VendorMaster"] = relationship()
    approved_by: Mapped[Optional["User"]] = relationship(foreign_keys=[approved_by_id])
    items: Mapped[List["PurchaseOrderItem"]] = relationship(back_populates="purchase_order", cascade="all, delete-orphan")


class PurchaseOrderItem(AuditMixin, Base):
    """Line items on a Purchase Order (Medication or General Consumables)."""
    __tablename__ = "procurement_po_items"
    __table_args__ = (
        CheckConstraint("quantity_ordered > 0", name="ck_po_item_qty_pos"),
        CheckConstraint("unit_price_paise >= 0", name="ck_po_item_price_non_neg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("procurement_purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    medication_id: Mapped[Optional[int]] = mapped_column(ForeignKey("medication_master.id"), nullable=True, index=True)
    item_description: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unit_price_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    total_price_paise: Mapped[int] = mapped_column(Integer, nullable=False)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="items")
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
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    invoice_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[GRNStatusEnum] = mapped_column(default=GRNStatusEnum.PENDING_INSPECTION, nullable=False)
    inspected_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    inspection_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    purchase_order: Mapped["PurchaseOrder"] = relationship()
    inspected_by: Mapped["User"] = relationship(foreign_keys=[inspected_by_id])
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

    invoice: Mapped["VendorInvoice"] = relationship(back_populates="items")


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


class SupplierPayment(AuditMixin, Base):
    """Recorded supplier outflow; invoice allocations are the settlement source of truth."""
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
    amount_paise: Mapped[int] = mapped_column(PAISE_AMOUNT_TYPE, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    allocations: Mapped[List["SupplierPaymentAllocation"]] = relationship(back_populates="payment")


class SupplierPaymentAllocation(Base):
    """Positive, append-only invoice allocation for a recorded supplier payment."""
    __tablename__ = "procurement_supplier_payment_allocations"
    __table_args__ = (
        UniqueConstraint("payment_id", "invoice_id", name="uq_supplier_payment_invoice_allocation"),
        CheckConstraint("amount_paise > 0", name="ck_supplier_payment_allocation_positive"),
        Index("ix_supplier_payment_allocation_invoice", "invoice_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("procurement_supplier_payments.id", ondelete="RESTRICT"), nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendor_invoices.id", ondelete="RESTRICT"), nullable=False)
    amount_paise: Mapped[int] = mapped_column(PAISE_AMOUNT_TYPE, nullable=False)
    payment: Mapped["SupplierPayment"] = relationship(back_populates="allocations")


class SupplierPaymentRequest(AuditMixin, Base):
    """Scheduled supplier outflow awaiting independent approval and execution."""
    __tablename__ = "procurement_supplier_payment_requests"
    __table_args__ = (
        UniqueConstraint("vendor_id", "payment_reference", name="uq_supplier_payment_request_reference"),
        CheckConstraint("amount_paise > 0", name="ck_supplier_payment_request_amount_positive"),
        CheckConstraint("status IN ('PENDING','APPROVED','REJECTED','EXECUTED','CANCELLED')", name="ck_supplier_payment_request_status"),
        Index("ix_supplier_payment_request_status_date", "status", "scheduled_date"),
        UniqueConstraint("executed_payment_id", name="uq_supplier_payment_request_executed_payment"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendors.id", ondelete="RESTRICT"), nullable=False)
    payment_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    payment_method: Mapped[SupplierPaymentMethodEnum] = mapped_column(Enum(SupplierPaymentMethodEnum), nullable=False)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_paise: Mapped[int] = mapped_column(PAISE_AMOUNT_TYPE, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    executed_payment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("procurement_supplier_payments.id", ondelete="RESTRICT"), nullable=True
    )
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    allocations: Mapped[List["SupplierPaymentRequestAllocation"]] = relationship(back_populates="request")


class SupplierPaymentRequestAllocation(Base):
    """Invoice balance reserved by a pending or approved payment request."""
    __tablename__ = "procurement_supplier_payment_request_allocations"
    __table_args__ = (
        UniqueConstraint("request_id", "invoice_id", name="uq_supplier_payment_request_invoice"),
        CheckConstraint("amount_paise > 0", name="ck_supplier_payment_request_allocation_positive"),
        Index("ix_supplier_payment_request_allocation_invoice", "invoice_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("procurement_supplier_payment_requests.id", ondelete="RESTRICT"), nullable=False)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("procurement_vendor_invoices.id", ondelete="RESTRICT"), nullable=False)
    amount_paise: Mapped[int] = mapped_column(PAISE_AMOUNT_TYPE, nullable=False)
    request: Mapped["SupplierPaymentRequest"] = relationship(back_populates="allocations")

class BankStatementBatch(Base):
    """Immutable bank statement import envelope; account_key is an opaque tenant-local alias."""
    __tablename__ = "procurement_bank_statement_batches"
    __table_args__ = (
        UniqueConstraint("account_key", "statement_reference", name="uq_bank_statement_account_reference"),
        CheckConstraint("period_end >= period_start", name="ck_bank_statement_period_valid"),
        Index("ix_bank_statement_period", "period_start", "period_end"),
        Index("ix_bank_statement_imported_by", "imported_by_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_key: Mapped[str] = mapped_column(String(64), nullable=False)
    account_label: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    statement_reference: Mapped[str] = mapped_column(String(120), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    opening_balance_paise: Mapped[int] = mapped_column(PAISE_AMOUNT_TYPE, nullable=False)
    closing_balance_paise: Mapped[int] = mapped_column(PAISE_AMOUNT_TYPE, nullable=False)
    imported_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class BankStatementLine(Base):
    """Immutable bank transaction line; only DEBIT lines may be matched to supplier outflows."""
    __tablename__ = "procurement_bank_statement_lines"
    __table_args__ = (
        UniqueConstraint("account_key", "bank_transaction_id", name="uq_bank_statement_transaction_identity"),
        CheckConstraint("direction IN ('DEBIT','CREDIT')", name="ck_bank_statement_direction"),
        CheckConstraint("amount_paise > 0", name="ck_bank_statement_amount_positive"),
        Index("ix_bank_statement_line_batch_date", "batch_id", "transaction_date"),
        Index("ix_bank_statement_line_direction_date", "direction", "transaction_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("procurement_bank_statement_batches.id", ondelete="RESTRICT"), nullable=False)
    account_key: Mapped[str] = mapped_column(String(64), nullable=False)
    bank_transaction_id: Mapped[str] = mapped_column(String(160), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    value_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    amount_paise: Mapped[int] = mapped_column(PAISE_AMOUNT_TYPE, nullable=False)
    bank_reference: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class SupplierPaymentBankMatch(Base):
    """Append-only manual allocation between a bank debit and a supplier payment."""
    __tablename__ = "procurement_supplier_payment_bank_matches"
    __table_args__ = (
        UniqueConstraint("statement_line_id", "supplier_payment_id", name="uq_bank_match_line_payment"),
        CheckConstraint("amount_paise > 0", name="ck_bank_match_amount_positive"),
        Index("ix_bank_match_payment", "supplier_payment_id"),
        Index("ix_bank_match_actor_time", "matched_by_id", "matched_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    statement_line_id: Mapped[int] = mapped_column(ForeignKey("procurement_bank_statement_lines.id", ondelete="RESTRICT"), nullable=False)
    supplier_payment_id: Mapped[int] = mapped_column(ForeignKey("procurement_supplier_payments.id", ondelete="RESTRICT"), nullable=False)
    amount_paise: Mapped[int] = mapped_column(PAISE_AMOUNT_TYPE, nullable=False)
    matched_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    matched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)



class ReconciliationInvestigation(Base):
    """Tenant-scoped human investigation opened from a reconciliation source indicator."""
    __tablename__ = "procurement_reconciliation_investigations"
    __table_args__ = (
        UniqueConstraint("external_key", name="uq_recon_investigation_external_key"),
        CheckConstraint("severity IN ('LOW','MEDIUM','HIGH','CRITICAL')", name="ck_recon_investigation_severity"),
        CheckConstraint("status IN ('OPEN','ASSIGNED','IN_REVIEW','RESOLVED','DISMISSED')", name="ck_recon_investigation_status"),
        CheckConstraint("version >= 1", name="ck_recon_investigation_version_positive"),
        CheckConstraint("reopen_count >= 0", name="ck_recon_investigation_reopen_count_nonneg"),
        CheckConstraint("resolution_quality_status IN ('NOT_REVIEWED','APPROVED','REJECTED')", name="ck_recon_investigation_quality_status"),
        Index("ix_recon_investigation_status_severity", "status", "severity"),
        Index("ix_recon_investigation_opened_by", "opened_by_id"),
        Index("ix_recon_investigation_closed_by", "closed_by_id"),
        Index("ix_recon_investigation_quality_reviewer", "resolution_quality_reviewed_by_id"),
        Index("ix_recon_investigation_sla_policy", "sla_policy_id"),
        Index("ix_recon_investigation_sla_due_status", "status", "sla_due_at"),
        Index("ix_recon_investigation_assignee_status", "assigned_to_id", "status"),
        Index("ix_recon_investigation_source", "source_type", "source_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_key: Mapped[str] = mapped_column(String(220), nullable=False)
    candidate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_reference: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(12), nullable=False, default="MEDIUM")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="OPEN")
    opened_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    assigned_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    root_cause: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    reopen_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    resolution_quality_status: Mapped[str] = mapped_column(String(16), nullable=False, default="NOT_REVIEWED", server_default="NOT_REVIEWED")
    resolution_quality_reviewed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolution_quality_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_quality_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sla_policy_id: Mapped[Optional[int]] = mapped_column(ForeignKey("procurement_reconciliation_sla_policies.id", ondelete="RESTRICT"), nullable=True)
    sla_policy_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sla_target_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sla_warning_percent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sla_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ReconciliationSLAPolicy(Base):
    """Versioned severity-based SLA policy; new cases snapshot its values."""
    __tablename__ = "procurement_reconciliation_sla_policies"
    __table_args__ = (
        UniqueConstraint("severity", "version", name="uq_recon_sla_severity_version"),
        CheckConstraint("severity IN ('LOW','MEDIUM','HIGH','CRITICAL')", name="ck_recon_sla_severity"),
        CheckConstraint("target_minutes > 0", name="ck_recon_sla_target_positive"),
        CheckConstraint("warning_percent BETWEEN 1 AND 99", name="ck_recon_sla_warning_percent"),
        CheckConstraint("version >= 1", name="ck_recon_sla_version_positive"),
        Index("uq_recon_sla_active_severity", "severity", unique=True,
              sqlite_where=text("is_active = 1"),
              postgresql_where=text("is_active = true")),
        Index("ix_recon_sla_created_by", "created_by_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    severity: Mapped[str] = mapped_column(String(12), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    target_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    warning_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=80, server_default="80")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ReconciliationInvestigationEvent(Base):
    """Append-only event history for investigation assignment and lifecycle transitions."""
    __tablename__ = "procurement_reconciliation_investigation_events"
    __table_args__ = (
        Index("ix_recon_investigation_event_case_time", "investigation_id", "occurred_at"),
        Index("ix_recon_investigation_event_actor_time", "actor_user_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[int] = mapped_column(
        ForeignKey("procurement_reconciliation_investigations.id", ondelete="RESTRICT"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    to_status: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ReconciliationEscalationPolicy(Base):
    """Versioned tenant-local escalation rule; currently configuration only."""
    __tablename__ = "procurement_reconciliation_escalation_policies"
    __table_args__ = (
        UniqueConstraint("severity", "trigger", "version", name="uq_recon_escalation_version"),
        CheckConstraint("severity IN ('LOW','MEDIUM','HIGH','CRITICAL')", name="ck_recon_escalation_severity"),
        CheckConstraint("trigger IN ('WARNING','BREACHED')", name="ck_recon_escalation_trigger"),
        CheckConstraint("version >= 1", name="ck_recon_escalation_version_positive"),
        CheckConstraint("delay_minutes >= 0", name="ck_recon_escalation_delay_nonneg"),
        Index("uq_recon_escalation_active", "severity", "trigger", unique=True,
              sqlite_where=text("is_active = 1"),
              postgresql_where=text("is_active = true")),
        Index("ix_recon_escalation_created_by", "created_by_id"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    severity: Mapped[str] = mapped_column(String(12), nullable=False)
    trigger: Mapped[str] = mapped_column(String(12), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    delay_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    recipient_role_ids: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    channels: Mapped[str] = mapped_column(Text, nullable=False, server_default='["IN_APP"]')
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ReconciliationNotificationPreference(Base):
    """A user's own notification choice for one event and delivery channel."""
    __tablename__ = "procurement_reconciliation_notification_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "event_type", "channel", name="uq_recon_notification_preference"),
        CheckConstraint("event_type IN ('SLA_WARNING','SLA_BREACHED')", name="ck_recon_notification_event"),
        CheckConstraint("channel IN ('IN_APP','EMAIL','SMS','PUSH')", name="ck_recon_notification_channel"),
        Index("ix_recon_notification_pref_updated_by", "updated_by_id"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    channel: Mapped[str] = mapped_column(String(12), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)


class ReconciliationNotificationConfigEvent(Base):
    """Append-only audit for escalation policy and preference changes."""
    __tablename__ = "procurement_reconciliation_notification_config_events"
    __table_args__ = (
        Index("ix_recon_notification_config_actor_time", "actor_user_id", "occurred_at"),
        Index("ix_recon_notification_config_subject", "subject_user_id"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    # Preserve the historical subject identifier after user deletion; audit rows are immutable.
    subject_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    object_type: Mapped[str] = mapped_column(String(32), nullable=False)
    object_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ReconciliationNotificationOutbox(Base):
    """Durable, tenant-local in-app notification intent; delivery is a later stage."""
    __tablename__ = "procurement_reconciliation_notification_outbox"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_recon_notification_outbox_idempotency"),
        CheckConstraint("event_type IN ('SLA_WARNING','SLA_BREACHED')", name="ck_recon_outbox_event"),
        CheckConstraint("channel = 'IN_APP'", name="ck_recon_outbox_channel"),
        CheckConstraint("status IN ('PENDING','PROCESSING','DELIVERED','RETRY','DEAD_LETTER','SUPPRESSED')", name="ck_recon_outbox_status"),
        Index("ix_recon_outbox_recipient_created", "recipient_user_id", "created_at"),
        Index("ix_recon_outbox_recipient_read_created", "recipient_user_id", "read_at", "created_at"),
        Index("ix_recon_outbox_status_available", "status", "available_at"),
        Index("ix_recon_outbox_investigation", "investigation_id"),
        Index("ix_recon_outbox_policy", "policy_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    idempotency_key: Mapped[str] = mapped_column(String(220), nullable=False)
    investigation_id: Mapped[int] = mapped_column(
        ForeignKey("procurement_reconciliation_investigations.id", ondelete="RESTRICT"), nullable=False
    )
    policy_id: Mapped[int] = mapped_column(
        ForeignKey("procurement_reconciliation_escalation_policies.id", ondelete="RESTRICT"), nullable=False
    )
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    recipient_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    channel: Mapped[str] = mapped_column(String(12), nullable=False, server_default="IN_APP")
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="PENDING")
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ReconciliationGovernanceReport(Base):
    """Immutable, tenant-local monthly governance snapshot; payload contains aggregates only."""
    __tablename__ = "procurement_reconciliation_governance_reports"
    __table_args__ = (
        UniqueConstraint("report_month", name="uq_recon_governance_report_month"),
        CheckConstraint("schema_version >= 1", name="ck_recon_governance_schema_version"),
        Index("ix_recon_governance_generated_at", "generated_at"),
        Index("ix_recon_governance_generated_by", "generated_by_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_month: Mapped[str] = mapped_column(String(7), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_by_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)


# Keep metadata-created SQLite databases immutable too (unit/integration test parity).
event.listen(
    ReconciliationGovernanceReport.__table__,
    "after_create",
    DDL(
        """
        CREATE TRIGGER trg_procurement_reconciliation_governance_reports_immutable_update
        BEFORE UPDATE ON procurement_reconciliation_governance_reports
        BEGIN SELECT RAISE(ABORT, 'Monthly reconciliation governance reports are immutable'); END
        """
    ).execute_if(dialect="sqlite"),
)
event.listen(
    ReconciliationGovernanceReport.__table__,
    "after_create",
    DDL(
        """
        CREATE TRIGGER trg_procurement_reconciliation_governance_reports_immutable_delete
        BEFORE DELETE ON procurement_reconciliation_governance_reports
        BEGIN SELECT RAISE(ABORT, 'Monthly reconciliation governance reports are immutable'); END
        """
    ).execute_if(dialect="sqlite"),
)
