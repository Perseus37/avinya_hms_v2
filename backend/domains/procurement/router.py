import secrets
import re
import hashlib
import io
import json
import zipfile
from pathlib import PurePath
from decimal import Decimal

from datetime import date, datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, BackgroundTasks, Response, Query, Request, Form
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import select, func, or_, text
from sqlalchemy.exc import IntegrityError
from typing import Optional
from backend.core.database import get_db, resolve_tenant_context
from backend.core.document_responses import pdf_attachment_response
from backend.core.date_ranges import resolve_record_date_window
from backend.core.queue import enqueue_task, get_task_status
from backend.core.dependencies import RequirePermission, get_current_user, validate_pagination, user_has_department_access
from backend.core.export import stream_csv_response, chunked_query_fetcher
from backend.domains.identity.models import User, UserStatusEnum, Department, Role, UserRole
from backend.domains.finance.models import ExpenseRecord, ExpenseStatusEnum
from backend.domains.pharmacy.models import MedicationMaster, InventoryMovement, InventoryBatch
from backend.domains.procurement.models import (
    VendorMaster, VendorCategoryEnum, PurchaseOrder, PurchaseOrderItem, POStatusEnum,
    GoodsReceiptNote, GoodsReceiptItem, GRNStatusEnum,
    VendorInvoice, VendorInvoiceItem, VendorInvoiceStatusEnum, SupplierPaymentMethodEnum,
    ProcurementDocumentDownloadAudit,
    StoreIndent, StoreIndentItem, IndentStatusEnum,
    PurchaseRequisition, PurchaseRequisitionItem, PurchaseRequisitionStatusEnum,
    SupplierQuotation, SupplierQuotationItem, SupplierQuotationStatusEnum,
    PurchaseOrderApprovalAuthority, PurchaseOrderAmendment, POAmendmentStatusEnum,
    PurchaseOrderShipment, PurchaseOrderShipmentEvent, POShipmentStatusEnum,
    ProcurementUnitOfMeasure, MedicationPackConfiguration,
    MedicationPriceControl, PurchaseOrderPriceReview, ProcurementBudget, ProcurementBudgetRevision, ProcurementBudgetMovement,
    SupplierPayment, SupplierPaymentAllocation, SupplierPaymentRequest, SupplierPaymentRequestAllocation,
    SupplierAdjustment, SupplierAdjustmentApplication, SupplierAdjustmentTypeEnum, SupplierAdjustmentStatusEnum,
    SupplierAdvance, SupplierAdvanceAllocation,
    BankStatementBatch, BankStatementLine, BankStatementDirectionEnum, SupplierPaymentBankMatch,
    SupplierContract, SupplierContractRate, SupplierContractRevision, SupplierContractDocumentDownloadAudit, SupplierComplianceDocument, SupplierComplianceDocumentDownloadAudit, SupplierCompliancePolicy, SupplierCompliancePolicyAudit, SupplierLifecycleRequest, ProcurementReconciliationException, ProcurementReconciliationExceptionEvent,
    ProcurementReconciliationEvidence, ProcurementReconciliationEvidenceDownloadAudit,
    ProcurementReconciliationSlaPolicy, ProcurementReconciliationSlaPolicyEvent,
    ProcurementReconciliationEscalationPolicy, ProcurementReconciliationGovernanceReport,
    ProcurementReconciliationAuditExport
)
from backend.domains.procurement.schemas import (
    VendorCreate, VendorResponse, VendorDirectoryResponse, VendorStatusUpdate, SupplierLifecycleRequestCreate, SupplierLifecycleRequestReview, SupplierLifecycleRequestResponse, POCreate, POResponse, GRNCreate, VendorInvoiceResponse, VendorInvoiceReview, SupplierPaymentCreate, SupplierPaymentResponse, SupplierInvoiceSettlementResponse, SupplierPaymentRequestCreate, SupplierPaymentRequestReview, SupplierPaymentRequestExecute, SupplierPaymentRequestResponse,
    SupplierAdjustmentCreate, SupplierAdjustmentReview, SupplierAdjustmentApply, SupplierAdjustmentResponse,
    SupplierAdvanceCreate, SupplierAdvanceApply, SupplierAdvanceResponse,
    BankStatementImportCreate, BankStatementBatchResponse, SupplierPaymentBankMatchCreate, IndentReturnRequest,StoreIndentResponse,StoreIndentCreate,
    IndentIssueRequest, PurchaseReturnCreate,
    PurchaseRequisitionCreate, PurchaseRequisitionResponse, PurchaseRequisitionReview,
    PurchaseOrderFromRequisitionCreate, SupplierQuotationCreate,
    SupplierQuotationResponse, SupplierQuotationSelection,
    PurchaseOrderApprovalAuthorityUpdate, PurchaseOrderApprovalAuthorityResponse,
    PurchaseOrderAmendmentCreate, PurchaseOrderAmendmentReview, PurchaseOrderAmendmentResponse,
    PurchaseOrderShipmentCreate, PurchaseOrderShipmentUpdate, PurchaseOrderShipmentResponse,
    OverduePurchaseOrderResponse, ProcurementUnitOfMeasureResponse,
    MedicationPackConfigurationCreate, MedicationPackConfigurationResponse,
    MedicationPriceControlUpdate, MedicationPriceControlResponse,
    PurchaseOrderApprovalRequest, PurchaseOrderPriceReviewResponse,
    ProcurementBudgetCreate, ProcurementBudgetResponse,
    ProcurementBudgetRevisionCreate, ProcurementBudgetRevisionReview,
    ProcurementBudgetRevisionResponse, PurchaseOrderCancelRequest,
    SupplierContractCreate, SupplierContractResponse, SupplierContractRevisionCreate,
    SupplierContractRevisionReview, SupplierContractRevisionResponse, SupplierComplianceDocumentResponse, SupplierComplianceDocumentReview, SupplierCompliancePolicyUpdate, SupplierCompliancePolicyResponse,
    ReconciliationSlaPolicyCreate, ReconciliationSlaPolicyPublish, ReconciliationSlaPolicyResponse
)
from backend.domains.procurement.services import (
    process_grn_acceptance, trigger_donut_invoice_extraction,
    execute_3_way_match, post_invoice_to_accounts_payable, process_purchase_return,
    return_patient_indent_stock, issue_patient_indent,
)
from backend.domains.procurement.documents import (
    resolve_vendor_invoice_document,
    store_vendor_invoice_document,
    store_supplier_contract_document,
    resolve_supplier_contract_document,
    store_supplier_compliance_document,
    resolve_supplier_compliance_document,
    store_reconciliation_evidence,
    resolve_reconciliation_evidence,
    reconciliation_evidence_sha256,
)

from backend.domains.reports.models import PrintModeEnum, ReportTypeEnum
from backend.domains.reports.pdf import render_html_pdf
from backend.domains.reports.router import (
    _format_invoice_amount,
    _invoice_document_profile,
    _render_template_parts,
    _resolve_template_for_print,
)
from backend.schemas.common import PaginatedResponse

router = APIRouter(prefix="/api/procurement", tags=["Supply Chain, POs & Vendor Invoices"])

def _load_vendor_invoice(
    db: Session, invoice_id: int, *, for_update: bool = False
) -> VendorInvoice:
    query = db.query(VendorInvoice).options(selectinload(VendorInvoice.items))
    if for_update:
        query = query.with_for_update()
    invoice = query.filter(VendorInvoice.id == invoice_id).one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return invoice


def _normalized_price_benchmark(
    db: Session,
    medication_id: int,
    base_uom_code: str,
    *,
    lookback_days: int,
    before: Optional[datetime] = None,
    exclude_po_id: Optional[int] = None,
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    query = db.query(PurchaseOrderItem.base_unit_price_paise).join(
        PurchaseOrder, PurchaseOrderItem.po_id == PurchaseOrder.id
    ).filter(
        PurchaseOrderItem.medication_id == medication_id,
        PurchaseOrderItem.base_uom_code == base_uom_code,
        PurchaseOrderItem.base_unit_price_paise.is_not(None),
        PurchaseOrder.status.in_([
            POStatusEnum.APPROVED, POStatusEnum.PARTIALLY_RECEIVED, POStatusEnum.COMPLETED
        ]),
        PurchaseOrder.created_at >= cutoff,
    )
    if before is not None:
        query = query.filter(PurchaseOrder.created_at < before)
    if exclude_po_id is not None:
        query = query.filter(PurchaseOrder.id != exclude_po_id)
    values = sorted(Decimal(str(row[0])) for row in query.all() if row[0] is not None)
    if not values:
        return {"observations": 0, "median": None, "minimum": None, "maximum": None}
    middle = len(values) // 2
    median_value = values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / Decimal("2")
    return {
        "observations": len(values),
        "median": median_value,
        "minimum": values[0],
        "maximum": values[-1],
    }




def _budget_ledger_totals(db: Session, budget_id: int) -> dict:
    budget = db.get(ProcurementBudget, budget_id)
    budget_ids = [budget_id]
    if budget is not None and budget.period_type == "ANNUAL" and budget.parent_budget_id is None:
        budget_ids.extend(row[0] for row in db.query(ProcurementBudget.id).filter(
            ProcurementBudget.parent_budget_id == budget_id
        ).all())
    rows = db.query(
        ProcurementBudgetMovement.movement_type,
        func.coalesce(func.sum(ProcurementBudgetMovement.amount_paise), 0),
    ).filter(
        ProcurementBudgetMovement.budget_id.in_(budget_ids)
    ).group_by(ProcurementBudgetMovement.movement_type).all()
    totals = {kind: int(amount or 0) for kind, amount in rows}
    reserved = max(
        totals.get("RESERVATION", 0)
        - totals.get("RELEASE", 0)
        - totals.get("RECEIPT", 0),
        0,
    )
    received = totals.get("RECEIPT", 0)
    return {"reserved_open_paise": reserved, "received_consumption_paise": received}


def _budget_available_paise(db: Session, budget: ProcurementBudget) -> tuple[int, int]:
    totals = _budget_ledger_totals(db, budget.id)
    used = totals["reserved_open_paise"] + totals["received_consumption_paise"]
    earmarked_for_active_quarters = 0
    if budget.period_type == "ANNUAL" and budget.parent_budget_id is None:
        children = db.query(ProcurementBudget).filter(
            ProcurementBudget.parent_budget_id == budget.id,
            ProcurementBudget.status == "ACTIVE",
        ).all()
        for child in children:
            child_totals = _budget_ledger_totals(db, child.id)
            child_used = child_totals["reserved_open_paise"] + child_totals["received_consumption_paise"]
            earmarked_for_active_quarters += max(child.total_amount_paise - child_used, 0)
    return budget.total_amount_paise - used - earmarked_for_active_quarters, earmarked_for_active_quarters


def _supplier_paid_amounts_by_invoice(db: Session, invoice_ids: set[int]) -> dict[int, int]:
    if not invoice_ids:
        return {}
    rows = db.query(
        SupplierPaymentAllocation.invoice_id,
        func.sum(SupplierPaymentAllocation.amount_paise),
    ).filter(
        SupplierPaymentAllocation.invoice_id.in_(invoice_ids)
    ).group_by(SupplierPaymentAllocation.invoice_id).all()
    return {int(invoice_id): int(amount or 0) for invoice_id, amount in rows}


def _effective_invoice_paid_amount(invoice: VendorInvoice, paid_by_invoice: dict[int, int]) -> int:
    if invoice.id not in paid_by_invoice and invoice.status == VendorInvoiceStatusEnum.PAID:
        return int(invoice.total_amount_paise or 0)
    return min(max(int(paid_by_invoice.get(invoice.id, 0)), 0), int(invoice.total_amount_paise or 0))


def _allocate_paid_amount_to_invoice_lines(lines: list, line_values: dict[int, int], paid_amount_paise: int) -> dict[int, int]:
    """Allocate cash paid proportionally to invoice line gross values with exact paise reconciliation."""
    total_value = sum(max(int(value), 0) for value in line_values.values())
    if total_value <= 0 or paid_amount_paise <= 0:
        return {line.id: 0 for line in lines}
    amount = min(int(paid_amount_paise), total_value)
    allocations = []
    allocated = 0
    for line in lines:
        value = max(int(line_values.get(line.id, 0)), 0)
        base, remainder = divmod(amount * value, total_value)
        allocations.append([line.id, base, remainder])
        allocated += base
    remaining = amount - allocated
    for entry in sorted(allocations, key=lambda row: (-row[2], row[0]))[:remaining]:
        entry[1] += 1
    return {line_id: amount for line_id, amount, _ in allocations}


def _budget_invoice_actuals(db: Session, budget: ProcurementBudget) -> dict:
    """Calculate verified invoice actuals separately from budget consumption.

    Header discounts are allocated proportionally across invoice lines using a
    largest-remainder paise allocation so the distributed discount reconciles
    exactly to the invoice header.
    """
    budget_ids = {budget.id}
    if budget.period_type == "ANNUAL" and budget.parent_budget_id is None:
        budget_ids.update(
            row[0] for row in db.query(ProcurementBudget.id).filter(
                ProcurementBudget.parent_budget_id == budget.id
            ).all()
        )
    invoices = db.query(VendorInvoice).options(
        selectinload(VendorInvoice.items)
    ).filter(
        VendorInvoice.status.in_([
            VendorInvoiceStatusEnum.MATCHED_APPROVED,
            VendorInvoiceStatusEnum.PAID,
        ])
    ).all()
    paid_by_invoice = _supplier_paid_amounts_by_invoice(db, {invoice.id for invoice in invoices})
    po_item_ids = {
        line.po_item_id
        for invoice in invoices
        for line in invoice.items
        if line.po_item_id is not None
    }
    po_items = {
        item.id: item for item in db.query(PurchaseOrderItem).filter(
            PurchaseOrderItem.id.in_(po_item_ids or {-1})
        ).all()
    }
    verified_total = 0
    paid_total = 0
    unpaid_total = 0
    invoice_ids = set()
    for invoice in invoices:
        lines = sorted(invoice.items, key=lambda item: item.id)
        subtotal = sum(int(line.total_price_paise) for line in lines)
        if subtotal <= 0:
            continue
        discount = min(max(int(invoice.discount_paise or 0), 0), subtotal)
        shares = []
        allocated_discount = 0
        for line in lines:
            numerator = discount * int(line.total_price_paise)
            share, remainder = divmod(numerator, subtotal)
            shares.append([line, share, remainder])
            allocated_discount += share
        remaining_discount = discount - allocated_discount
        for entry in sorted(shares, key=lambda value: (-value[2], value[0].id))[:remaining_discount]:
            entry[1] += 1
        line_values = {
            line.id: max(int(line.total_price_paise) + (int(line.total_price_paise) * int(line.tax_percentage or 0) + 50) // 100 - discount_share, 0)
            for line, discount_share, _ in shares
        }
        paid_line_values = _allocate_paid_amount_to_invoice_lines(
            lines, line_values, _effective_invoice_paid_amount(invoice, paid_by_invoice)
        )
        invoice_budget_value = 0
        invoice_paid_value = 0
        for line, _, _ in shares:
            po_item = po_items.get(line.po_item_id) if line.po_item_id is not None else None
            if po_item is None or po_item.budget_id not in budget_ids:
                continue
            value = line_values.get(line.id, 0)
            invoice_budget_value += value
            invoice_paid_value += min(paid_line_values.get(line.id, 0), value)
        if invoice_budget_value <= 0:
            continue
        invoice_ids.add(invoice.id)
        verified_total += invoice_budget_value
        paid_total += invoice_paid_value
        unpaid_total += invoice_budget_value - invoice_paid_value
    return {
        "verified_invoice_actuals_paise": verified_total,
        "paid_invoice_actuals_paise": paid_total,
        "unpaid_verified_invoice_actuals_paise": unpaid_total,
        "verified_invoice_count": len(invoice_ids),
    }



def _budget_invoice_actuals_by_budget_ids(db: Session, budget_ids: set[int]) -> dict[int, dict]:
    """Fetch and allocate verified invoice actuals once for a dashboard portfolio."""
    result = {
        budget_id: {
            "verified_invoice_actuals_paise": 0,
            "paid_invoice_actuals_paise": 0,
            "unpaid_verified_invoice_actuals_paise": 0,
            "verified_invoice_ids": set(),
        }
        for budget_id in budget_ids
    }
    if not budget_ids:
        return result
    invoices = db.query(VendorInvoice).options(
        selectinload(VendorInvoice.items)
    ).filter(
        VendorInvoice.status.in_([
            VendorInvoiceStatusEnum.MATCHED_APPROVED,
            VendorInvoiceStatusEnum.PAID,
        ])
    ).all()
    po_item_ids = {
        line.po_item_id
        for invoice in invoices
        for line in invoice.items
        if line.po_item_id is not None
    }
    po_items = {
        item.id: item for item in db.query(PurchaseOrderItem).filter(
            PurchaseOrderItem.id.in_(po_item_ids or {-1})
        ).all()
    }
    for invoice in invoices:
        lines = sorted(invoice.items, key=lambda item: item.id)
        subtotal = sum(int(line.total_price_paise) for line in lines)
        if subtotal <= 0:
            continue
        discount = min(max(int(invoice.discount_paise or 0), 0), subtotal)
        shares = []
        allocated_discount = 0
        for line in lines:
            share, remainder = divmod(discount * int(line.total_price_paise), subtotal)
            shares.append([line, share, remainder])
            allocated_discount += share
        remaining_discount = discount - allocated_discount
        for entry in sorted(shares, key=lambda value: (-value[2], value[0].id))[:remaining_discount]:
            entry[1] += 1
        line_values = {
            line.id: max(int(line.total_price_paise) + (int(line.total_price_paise) * int(line.tax_percentage or 0) + 50) // 100 - discount_share, 0)
            for line, discount_share, _ in shares
        }
        paid_line_values = _allocate_paid_amount_to_invoice_lines(
            lines, line_values, paid_by_invoice.get(invoice.id, 0)
        )
        for line, _, _ in shares:
            po_item = po_items.get(line.po_item_id) if line.po_item_id is not None else None
            if po_item is None or po_item.budget_id not in budget_ids:
                continue
            value = line_values.get(line.id, 0)
            if value <= 0:
                continue
            paid_value = min(paid_line_values.get(line.id, 0), value)
            actuals = result[po_item.budget_id]
            actuals["verified_invoice_actuals_paise"] += value
            actuals["paid_invoice_actuals_paise"] += paid_value
            actuals["unpaid_verified_invoice_actuals_paise"] += value - paid_value
            actuals["verified_invoice_ids"].add(invoice.id)
    return result

def _resolve_active_procurement_budget(
    db: Session, department_id: int, category: str, order_date: date
) -> Optional[ProcurementBudget]:
    candidates = db.query(ProcurementBudget).filter(
        ProcurementBudget.requesting_department_id == department_id,
        ProcurementBudget.category == category,
        ProcurementBudget.status == "ACTIVE",
        ProcurementBudget.period_start <= order_date,
        ProcurementBudget.period_end >= order_date,
    ).with_for_update().all()
    # Budget management is opt-in per department/category. Once an active
    # allocation exists, that allocation becomes an approval control.
    if not candidates:
        historical_allocation = db.query(ProcurementBudget.id).filter(
            ProcurementBudget.requesting_department_id == department_id,
            ProcurementBudget.category == category,
            ProcurementBudget.period_start <= order_date,
            ProcurementBudget.period_end >= order_date,
        ).first()
        if historical_allocation:
            raise HTTPException(status_code=409, detail="A budget exists for this department/category/period but is not active; procurement cannot bypass its closed or draft control.")
        return None
    quarterly = [b for b in candidates if b.period_type == "QUARTERLY"]
    roots = [b for b in candidates if b.period_type == "ANNUAL" and b.parent_budget_id is None]
    if len(quarterly) > 1 or len(roots) > 1:
        raise HTTPException(status_code=409, detail="Overlapping active budgets require administrative reconciliation.")
    if quarterly:
        chosen = quarterly[0]
        parent = db.get(ProcurementBudget, chosen.parent_budget_id) if chosen.parent_budget_id else None
        if parent is None or parent.status != "ACTIVE":
            raise HTTPException(status_code=409, detail="The quarterly budget's annual parent is not active.")
        return chosen
    if roots:
        closed_quarter = db.query(ProcurementBudget.id).filter(
            ProcurementBudget.parent_budget_id == roots[0].id,
            ProcurementBudget.period_type == "QUARTERLY",
            ProcurementBudget.status == "CLOSED",
            ProcurementBudget.period_start <= order_date,
            ProcurementBudget.period_end >= order_date,
        ).first()
        if closed_quarter:
            raise HTTPException(status_code=409, detail="A quarterly budget covering this period has been closed; the annual allocation cannot be used to bypass that control.")
        return roots[0]
    raise HTTPException(status_code=409, detail="No valid root annual or quarterly budget covers this purchase.")








def _ensure_budget_department_access(db: Session, budget: ProcurementBudget, actor: User) -> None:
    if not actor.is_superuser and not user_has_department_access(
        db, actor, budget.requesting_department_id
    ):
        raise HTTPException(status_code=403, detail="You are not assigned to this procurement budget department.")


def _budget_item_open_reservation(db: Session, po_item_id: int) -> int:
    rows = db.query(
        ProcurementBudgetMovement.movement_type,
        func.coalesce(func.sum(ProcurementBudgetMovement.amount_paise), 0),
    ).filter(
        ProcurementBudgetMovement.po_item_id == po_item_id
    ).group_by(ProcurementBudgetMovement.movement_type).all()
    totals = {kind: int(amount or 0) for kind, amount in rows}
    return max(
        totals.get("RESERVATION", 0)
        - totals.get("RELEASE", 0)
        - totals.get("RECEIPT", 0),
        0,
    )


def _release_po_budget_reservations(
    db: Session,
    po: PurchaseOrder,
    actor: User,
    *,
    reference_suffix: str,
    note: str,
) -> None:
    for line in po.items:
        if line.budget_id is None:
            continue
        outstanding = _budget_item_open_reservation(db, line.id)
        if outstanding <= 0:
            continue
        db.add(ProcurementBudgetMovement(
            budget_id=line.budget_id,
            po_id=po.id,
            po_item_id=line.id,
            movement_type="RELEASE",
            amount_paise=outstanding,
            reference_key=f"PO:{po.id}:ITEM:{line.id}:{reference_suffix}:RELEASE",
            notes=note,
            actor_user_id=actor.id,
            created_by_id=actor.id,
        ))


def _reserve_purchase_order_budget(db: Session, po: PurchaseOrder, actor: User) -> None:
    """Reserve mapped PO lines atomically before the PO becomes approved.

    Requisition-backed lines inherit their department. Direct PO lines must carry
    an explicit budget department to participate in budget enforcement.
    """
    order_date = (po.created_at.date() if po.created_at else datetime.now(timezone.utc).date())
    mapped_count = 0
    if po.requisition_id is not None:
        requisition = po.requisition or db.get(PurchaseRequisition, po.requisition_id)
        if requisition is not None:
            for line in po.items:
                if line.budget_department_id is None:
                    line.budget_department_id = requisition.requesting_department_id
    # Stable lock order avoids deadlocks when concurrent POs span several
    # department/category budget allocations.
    ordered_lines = sorted(
        po.items,
        key=lambda item: (item.budget_department_id or 0, item.budget_category, item.id),
    )
    for line in ordered_lines:
        if line.budget_department_id is None:
            continue
        mapped_count += 1
        budget = _resolve_active_procurement_budget(
            db, line.budget_department_id, line.budget_category, order_date
        )
        if budget is None:
            continue
        existing = db.query(ProcurementBudgetMovement.id).filter(
            ProcurementBudgetMovement.reference_key == f"PO:{po.id}:ITEM:{line.id}:RESERVE"
        ).first()
        if existing:
            if line.budget_id != budget.id:
                raise HTTPException(status_code=409, detail="A PO line already has a reservation against a different budget.")
            continue
        line.budget_id = budget.id
        if line.gross_total_paise == 0:
            continue
        available, _ = _budget_available_paise(db, budget)
        if line.gross_total_paise > available:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Insufficient procurement budget for purchase-order approval.",
                    "budget_id": budget.id,
                    "budget_number": budget.budget_number,
                    "available_paise": available,
                    "required_paise": line.gross_total_paise,
                    "category": line.budget_category,
                    "department_id": line.budget_department_id,
                },
            )
        db.add(ProcurementBudgetMovement(
            budget_id=budget.id,
            po_id=po.id,
            po_item_id=line.id,
            movement_type="RESERVATION",
            amount_paise=line.gross_total_paise,
            reference_key=f"PO:{po.id}:ITEM:{line.id}:RESERVE",
            notes="Approved purchase-order commitment.",
            actor_user_id=actor.id,
            created_by_id=actor.id,
        ))
        db.flush()
    # Requisition-backed lines must always resolve their department. Budget
    # allocations themselves remain optional until configured for that category.
    if po.requisition_id is not None and mapped_count != len(po.items):
        raise HTTPException(status_code=409, detail="Every requisition-backed PO line must have a department budget allocation.")


def _generate_reference(prefix: str) -> str:
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"{prefix}-{date_part}-{secrets.token_hex(4).upper()}"


def _utc_aware(value: datetime) -> datetime:
    """Normalize SQLite-naive and timezone-aware timestamps for safe comparisons."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _resolve_medication_unit_snapshot(
    db: Session,
    *,
    medication_id: Optional[int],
    purchase_uom_id: Optional[int],
    quantity: int,
    unit_price_paise: int,
    effective_at: datetime,
) -> dict:
    """Resolve an effective medication pack definition and calculate precise base-unit economics."""
    if purchase_uom_id is None:
        return {
            "purchase_uom_code": None,
            "base_uom_code": None,
            "units_per_purchase_unit": None,
            "base_quantity": None,
            "base_unit_price_paise": None,
        }
    if medication_id is None:
        raise HTTPException(status_code=422, detail="A purchasing unit can only be assigned to a medication catalogue line.")
    effective_at = _utc_aware(effective_at)
    configuration = db.query(MedicationPackConfiguration).filter(
        MedicationPackConfiguration.medication_id == medication_id,
        MedicationPackConfiguration.purchase_uom_id == purchase_uom_id,
        MedicationPackConfiguration.is_active.is_(True),
        MedicationPackConfiguration.effective_from <= effective_at,
        (MedicationPackConfiguration.effective_to.is_(None) | (MedicationPackConfiguration.effective_to > effective_at)),
    ).options(
        joinedload(MedicationPackConfiguration.purchase_uom),
        joinedload(MedicationPackConfiguration.base_uom),
    ).one_or_none()
    if configuration is None:
        raise HTTPException(status_code=422, detail="No active medication pack configuration exists for this purchase unit and transaction date.")
    factor = Decimal(str(configuration.units_per_purchase_unit))
    if factor <= 0:
        raise HTTPException(status_code=422, detail="Medication pack conversion must be positive.")
    return {
        "purchase_uom_code": configuration.purchase_uom.code,
        "base_uom_code": configuration.base_uom.code,
        "units_per_purchase_unit": factor,
        "base_quantity": Decimal(quantity) * factor,
        "base_unit_price_paise": Decimal(unit_price_paise) / factor,
    }


# --- Procurement units and medication pack configurations ---
@router.get("/units-of-measure", response_model=list[ProcurementUnitOfMeasureResponse])
def list_procurement_units(
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    return db.query(ProcurementUnitOfMeasure).filter(
        ProcurementUnitOfMeasure.is_active.is_(True)
    ).order_by(ProcurementUnitOfMeasure.dimension, ProcurementUnitOfMeasure.code).all()


@router.get(
    "/medications/{medication_id}/pack-configurations",
    response_model=list[MedicationPackConfigurationResponse],
)
def list_medication_pack_configurations(
    medication_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    medication = db.get(MedicationMaster, medication_id)
    if medication is None:
        raise HTTPException(status_code=404, detail="Medication not found.")
    return db.query(MedicationPackConfiguration).filter(
        MedicationPackConfiguration.medication_id == medication_id
    ).order_by(MedicationPackConfiguration.effective_from.desc(), MedicationPackConfiguration.id.desc()).all()


@router.post(
    "/medications/{medication_id}/pack-configurations",
    response_model=MedicationPackConfigurationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_medication_pack_configuration(
    medication_id: int,
    payload: MedicationPackConfigurationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:write")),
):
    medication = db.get(MedicationMaster, medication_id)
    if medication is None or not medication.is_active:
        raise HTTPException(status_code=404, detail="Active medication not found.")
    purchase_uom = db.get(ProcurementUnitOfMeasure, payload.purchase_uom_id)
    base_uom = db.get(ProcurementUnitOfMeasure, payload.base_uom_id)
    if purchase_uom is None or base_uom is None or not purchase_uom.is_active or not base_uom.is_active:
        raise HTTPException(status_code=422, detail="Both units must be active registered units of measure.")
    if base_uom.is_packaging_unit:
        raise HTTPException(status_code=422, detail="The stock base unit must be a dispensing or measurement unit, not a packaging unit.")
    if not purchase_uom.is_packaging_unit and purchase_uom.dimension != base_uom.dimension:
        raise HTTPException(status_code=422, detail="Non-packaging purchase and base units must belong to the same measurement dimension.")
    existing_medication_base = db.query(MedicationPackConfiguration.base_uom_id).filter(
        MedicationPackConfiguration.medication_id == medication_id
    ).distinct().all()
    if existing_medication_base and any(row[0] != base_uom.id for row in existing_medication_base):
        raise HTTPException(status_code=409, detail="A medication must retain one consistent stock base unit across all pack configurations.")
    existing_stock = db.query(InventoryBatch).filter(
        InventoryBatch.medication_id == medication_id,
        InventoryBatch.stock_quantity > 0,
    ).all()
    if any(batch.base_uom_code != base_uom.code for batch in existing_stock):
        raise HTTPException(status_code=409, detail="Existing stock batches must be reconciled to the selected base unit before pack conversion can be enabled. Historical quantities will not be converted automatically.")
    if payload.effective_from.tzinfo is None:
        raise HTTPException(status_code=422, detail="Pack configuration effective_from must include a timezone.")
    if payload.units_per_purchase_unit <= 0:
        raise HTTPException(status_code=422, detail="Pack conversion must be greater than zero.")
    if Decimal(str(payload.units_per_purchase_unit)) != Decimal(str(payload.units_per_purchase_unit)).to_integral_value():
        raise HTTPException(status_code=422, detail="Stock base-unit conversions must be whole numbers because current inventory quantities are stored as integer units.")
    if purchase_uom.id == base_uom.id and Decimal(str(payload.units_per_purchase_unit)) != Decimal("1"):
        raise HTTPException(status_code=422, detail="Identical purchase and base units require a conversion factor of exactly 1.")
    existing = db.query(MedicationPackConfiguration.id).filter(
        MedicationPackConfiguration.medication_id == medication_id,
        MedicationPackConfiguration.purchase_uom_id == purchase_uom.id,
        MedicationPackConfiguration.is_active.is_(True),
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="An active configuration already exists for this medication and purchase unit. Deactivate it before creating a replacement.")
    latest = db.query(MedicationPackConfiguration).filter(
        MedicationPackConfiguration.medication_id == medication_id,
        MedicationPackConfiguration.purchase_uom_id == purchase_uom.id,
    ).order_by(MedicationPackConfiguration.effective_from.desc(), MedicationPackConfiguration.id.desc()).first()
    if latest is not None:
        if _utc_aware(payload.effective_from) <= _utc_aware(latest.effective_from):
            raise HTTPException(status_code=422, detail="A replacement pack configuration must have a later effective start than its prior version.")
        if latest.effective_to is not None and _utc_aware(payload.effective_from) <= _utc_aware(latest.effective_to):
            raise HTTPException(status_code=422, detail="Pack configuration effective periods cannot overlap.")
    config = MedicationPackConfiguration(
        medication_id=medication_id,
        purchase_uom_id=purchase_uom.id,
        base_uom_id=base_uom.id,
        units_per_purchase_unit=payload.units_per_purchase_unit,
        effective_from=payload.effective_from,
        is_active=True,
        created_by_id=current_user.id,
    )
    db.add(config)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A concurrent request created an active pack configuration for this medication and purchase unit.")
    db.refresh(config)
    return config


@router.patch(
    "/medications/{medication_id}/pack-configurations/{configuration_id}/deactivate",
    response_model=MedicationPackConfigurationResponse,
)
def deactivate_medication_pack_configuration(
    medication_id: int,
    configuration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:approve")),
):
    config = db.query(MedicationPackConfiguration).filter(
        MedicationPackConfiguration.id == configuration_id,
        MedicationPackConfiguration.medication_id == medication_id,
    ).with_for_update().one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="Pack configuration not found.")
    if not config.is_active:
        raise HTTPException(status_code=409, detail="Pack configuration is already inactive.")
    now = datetime.now(timezone.utc)
    if _utc_aware(now) <= _utc_aware(config.effective_from):
        raise HTTPException(status_code=409, detail="A pack configuration cannot be deactivated before or at its effective start.")
    config.is_active = False
    config.effective_to = now
    config.updated_by_id = current_user.id
    db.commit()
    db.refresh(config)
    return config


# --- Vendor Management ---
@router.post("/vendors", response_model=VendorDirectoryResponse, status_code=status.HTTP_201_CREATED)
def create_vendor(payload: VendorCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("procurement:write"))):
    vendor = VendorMaster(**payload.model_dump(), is_active=True, created_by_id=current_user.id)
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor


@router.patch("/vendors/{vendor_id}/status", response_model=VendorDirectoryResponse)
def update_vendor_status(
    vendor_id: int,
    payload: VendorStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:approve")),
):
    vendor = db.query(VendorMaster).filter(VendorMaster.id == vendor_id).with_for_update().one_or_none()
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found.")
    if not payload.is_active:
        open_orders = db.query(PurchaseOrder.id).filter(
            PurchaseOrder.vendor_id == vendor.id,
            PurchaseOrder.status.in_([
                POStatusEnum.SUBMITTED,
                POStatusEnum.APPROVED,
                POStatusEnum.PARTIALLY_RECEIVED,
            ]),
        ).first()
        if open_orders:
            raise HTTPException(status_code=409, detail="Vendor cannot be deactivated while open purchase orders remain.")
    vendor.is_active = payload.is_active
    vendor.updated_by_id = current_user.id
    db.commit()
    db.refresh(vendor)
    return vendor



@router.post("/vendors/{vendor_id}/lifecycle-requests", response_model=SupplierLifecycleRequestResponse, status_code=status.HTTP_201_CREATED)
def create_supplier_lifecycle_request(vendor_id: int, payload: SupplierLifecycleRequestCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("procurement:write"))):
    vendor = db.query(VendorMaster).filter(VendorMaster.id == vendor_id).with_for_update().one_or_none()
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found.")
    pending = db.query(SupplierLifecycleRequest.id).filter(SupplierLifecycleRequest.vendor_id == vendor.id, SupplierLifecycleRequest.status == "PENDING").first()
    if pending:
        raise HTTPException(status_code=409, detail="A supplier lifecycle request is already pending.")
    if payload.action == "SUSPEND" and vendor.is_suspended:
        raise HTTPException(status_code=409, detail="Supplier is already suspended.")
    if payload.action == "REINSTATE" and not vendor.is_suspended:
        raise HTTPException(status_code=409, detail="Only a suspended supplier can be reinstated.")
    row = SupplierLifecycleRequest(vendor_id=vendor.id, action=payload.action, reason=payload.reason.strip(), status="PENDING", requested_by_id=current_user.id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/vendors/{vendor_id}/lifecycle-requests", response_model=list[SupplierLifecycleRequestResponse])
def list_supplier_lifecycle_requests(vendor_id: int, db: Session = Depends(get_db), _: User = Depends(RequirePermission("procurement:read"))):
    if db.get(VendorMaster, vendor_id) is None:
        raise HTTPException(status_code=404, detail="Vendor not found.")
    return db.query(SupplierLifecycleRequest).filter(SupplierLifecycleRequest.vendor_id == vendor_id).order_by(SupplierLifecycleRequest.requested_at.desc(), SupplierLifecycleRequest.id.desc()).all()


@router.patch("/vendors/{vendor_id}/lifecycle-requests/{request_id}/review", response_model=SupplierLifecycleRequestResponse)
def review_supplier_lifecycle_request(vendor_id: int, request_id: int, payload: SupplierLifecycleRequestReview, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("procurement:approve"))):
    vendor = db.query(VendorMaster).filter(VendorMaster.id == vendor_id).with_for_update().one_or_none()
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found.")
    row = db.query(SupplierLifecycleRequest).filter(SupplierLifecycleRequest.id == request_id, SupplierLifecycleRequest.vendor_id == vendor.id).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Supplier lifecycle request not found.")
    if row.status != "PENDING":
        raise HTTPException(status_code=409, detail="Only pending supplier lifecycle requests can be reviewed.")
    if row.requested_by_id == current_user.id:
        raise HTTPException(status_code=409, detail="The requester cannot review their own supplier lifecycle request.")
    if payload.approved:
        if row.action == "SUSPEND":
            if vendor.is_suspended:
                raise HTTPException(status_code=409, detail="Supplier is already suspended.")
            vendor.is_suspended = True
            vendor.suspension_reason = row.reason
            vendor.suspended_at = datetime.now(timezone.utc)
            vendor.suspended_by_id = current_user.id
        else:
            if not vendor.is_suspended:
                raise HTTPException(status_code=409, detail="Supplier is no longer suspended.")
            vendor.is_suspended = False
            vendor.suspension_reason = None
            vendor.suspended_at = None
            vendor.suspended_by_id = None
        vendor.updated_by_id = current_user.id
        row.status = "APPROVED"
    else:
        row.status = "REJECTED"
    row.reviewed_by_id = current_user.id
    row.reviewed_at = datetime.now(timezone.utc)
    row.review_notes = payload.review_notes.strip()
    db.commit()
    db.refresh(row)
    return row

@router.get("/vendors", response_model=list[VendorDirectoryResponse])
def list_vendors(
    active_only: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    query = db.query(VendorMaster)
    if active_only:
        query = query.filter(VendorMaster.is_active.is_(True))
    return query.order_by(VendorMaster.name.asc(), VendorMaster.id.asc()).all()


@router.get("/vendors/{vendor_id}", response_model=VendorDirectoryResponse)
def get_vendor(
    vendor_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    vendor = db.get(VendorMaster, vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found.")
    return vendor


# --- External Purchase Requisitions ---
@router.post(
    "/purchase-requisitions",
    response_model=PurchaseRequisitionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_purchase_requisition(
    payload: PurchaseRequisitionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:write")),
):
    department = db.get(Department, payload.requesting_department_id)
    if department is None or not department.is_active:
        raise HTTPException(status_code=404, detail="Requesting department is unavailable.")
    if not user_has_department_access(db, current_user, department.id):
        raise HTTPException(status_code=403, detail="You are not assigned to the requesting department.")
    requisition = PurchaseRequisition(
        requisition_number=_generate_reference("PR"),
        requesting_department_id=department.id,
        requested_by_id=current_user.id,
        status=PurchaseRequisitionStatusEnum.DRAFT,
        required_by_date=payload.required_by_date,
        justification=payload.justification.strip(),
        created_by_id=current_user.id,
    )
    db.add(requisition)
    db.flush()
    for item in payload.items:
        if item.medication_id is not None:
            medication = db.get(MedicationMaster, item.medication_id)
            if medication is None or not medication.is_active:
                raise HTTPException(status_code=422, detail="A requested medication is unavailable.")
        if item.purchase_uom_id is not None:
            _resolve_medication_unit_snapshot(
                db, medication_id=item.medication_id, purchase_uom_id=item.purchase_uom_id,
                quantity=item.requested_quantity, unit_price_paise=0,
                effective_at=datetime.now(timezone.utc),
            )
        db.add(PurchaseRequisitionItem(
            requisition_id=requisition.id,
            medication_id=item.medication_id,
            purchase_uom_id=item.purchase_uom_id,
            item_description=item.item_description.strip(),
            requested_quantity=item.requested_quantity,
            estimated_unit_price_paise=item.estimated_unit_price_paise,
            notes=item.notes,
            created_by_id=current_user.id,
        ))
    db.commit()
    return db.query(PurchaseRequisition).options(
        selectinload(PurchaseRequisition.items)
    ).filter(PurchaseRequisition.id == requisition.id).one()


@router.get("/purchase-requisitions", response_model=PaginatedResponse[PurchaseRequisitionResponse])
def list_purchase_requisitions(
    requisition_status: Optional[PurchaseRequisitionStatusEnum] = Query(default=None, alias="status"),
    department_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    page, page_size = validate_pagination(page, page_size)
    query = db.query(PurchaseRequisition).options(selectinload(PurchaseRequisition.items))
    if requisition_status is not None:
        query = query.filter(PurchaseRequisition.status == requisition_status)
    if department_id is not None:
        query = query.filter(PurchaseRequisition.requesting_department_id == department_id)
    total = query.count()
    items = query.order_by(PurchaseRequisition.created_at.desc(), PurchaseRequisition.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/purchase-requisitions/{requisition_id}", response_model=PurchaseRequisitionResponse)
def get_purchase_requisition(
    requisition_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    requisition = db.query(PurchaseRequisition).options(
        selectinload(PurchaseRequisition.items)
    ).filter(PurchaseRequisition.id == requisition_id).one_or_none()
    if requisition is None:
        raise HTTPException(status_code=404, detail="Purchase requisition not found.")
    return requisition


@router.put("/purchase-requisitions/{requisition_id}", response_model=PurchaseRequisitionResponse)
def update_purchase_requisition(
    requisition_id: int,
    payload: PurchaseRequisitionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:write")),
):
    requisition = db.query(PurchaseRequisition).options(
        selectinload(PurchaseRequisition.items)
    ).filter(PurchaseRequisition.id == requisition_id).with_for_update().one_or_none()
    if requisition is None:
        raise HTTPException(status_code=404, detail="Purchase requisition not found.")
    if requisition.requested_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the requisition requester can edit it.")
    if requisition.status != PurchaseRequisitionStatusEnum.DRAFT:
        raise HTTPException(status_code=409, detail="Only draft requisitions can be edited.")
    department = db.get(Department, payload.requesting_department_id)
    if department is None or not department.is_active:
        raise HTTPException(status_code=404, detail="Requesting department is unavailable.")
    if not user_has_department_access(db, current_user, department.id):
        raise HTTPException(status_code=403, detail="You are not assigned to the requesting department.")
    for item in payload.items:
        if item.medication_id is not None:
            medication = db.get(MedicationMaster, item.medication_id)
            if medication is None or not medication.is_active:
                raise HTTPException(status_code=422, detail="A requested medication is unavailable.")
        if item.purchase_uom_id is not None:
            _resolve_medication_unit_snapshot(
                db, medication_id=item.medication_id, purchase_uom_id=item.purchase_uom_id,
                quantity=item.requested_quantity, unit_price_paise=0,
                effective_at=datetime.now(timezone.utc),
            )
    requisition.requesting_department_id = department.id
    requisition.required_by_date = payload.required_by_date
    requisition.justification = payload.justification.strip()
    requisition.updated_by_id = current_user.id
    for existing in list(requisition.items):
        db.delete(existing)
    db.flush()
    for item in payload.items:
        db.add(PurchaseRequisitionItem(
            requisition_id=requisition.id,
            medication_id=item.medication_id,
            purchase_uom_id=item.purchase_uom_id,
            item_description=item.item_description.strip(),
            requested_quantity=item.requested_quantity,
            estimated_unit_price_paise=item.estimated_unit_price_paise,
            notes=item.notes,
            created_by_id=current_user.id,
        ))
    db.commit()
    return db.query(PurchaseRequisition).options(
        selectinload(PurchaseRequisition.items)
    ).filter(PurchaseRequisition.id == requisition.id).one()


@router.post("/purchase-requisitions/{requisition_id}/cancel", response_model=PurchaseRequisitionResponse)
def cancel_purchase_requisition(
    requisition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:write")),
):
    requisition = db.query(PurchaseRequisition).filter(
        PurchaseRequisition.id == requisition_id
    ).with_for_update().one_or_none()
    if requisition is None:
        raise HTTPException(status_code=404, detail="Purchase requisition not found.")
    if requisition.requested_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the requisition requester can cancel it.")
    if requisition.status not in {
        PurchaseRequisitionStatusEnum.DRAFT,
        PurchaseRequisitionStatusEnum.SUBMITTED,
    }:
        raise HTTPException(status_code=409, detail="Only draft or submitted requisitions can be cancelled.")
    requisition.status = PurchaseRequisitionStatusEnum.CANCELLED
    requisition.updated_by_id = current_user.id
    db.commit()
    db.refresh(requisition)
    return requisition


@router.post("/purchase-requisitions/{requisition_id}/submit", response_model=PurchaseRequisitionResponse)
def submit_purchase_requisition(
    requisition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:write")),
):
    requisition = db.query(PurchaseRequisition).options(
        selectinload(PurchaseRequisition.items)
    ).filter(PurchaseRequisition.id == requisition_id).with_for_update().one_or_none()
    if requisition is None:
        raise HTTPException(status_code=404, detail="Purchase requisition not found.")
    if requisition.requested_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the requisition requester can submit it.")
    if requisition.status != PurchaseRequisitionStatusEnum.DRAFT:
        raise HTTPException(status_code=409, detail="Only draft requisitions can be submitted.")
    if not requisition.items:
        raise HTTPException(status_code=409, detail="A requisition must contain at least one line.")
    requisition.status = PurchaseRequisitionStatusEnum.SUBMITTED
    requisition.updated_by_id = current_user.id
    requisition.submitted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(requisition)
    return requisition


@router.patch("/purchase-requisitions/{requisition_id}/review", response_model=PurchaseRequisitionResponse)
def review_purchase_requisition(
    requisition_id: int,
    payload: PurchaseRequisitionReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:approve")),
):
    requisition = db.query(PurchaseRequisition).options(
        selectinload(PurchaseRequisition.items)
    ).filter(PurchaseRequisition.id == requisition_id).with_for_update().one_or_none()
    if requisition is None:
        raise HTTPException(status_code=404, detail="Purchase requisition not found.")
    if requisition.status != PurchaseRequisitionStatusEnum.SUBMITTED:
        raise HTTPException(status_code=409, detail="Only submitted requisitions can be reviewed.")
    if requisition.requested_by_id == current_user.id:
        raise HTTPException(status_code=409, detail="The requester cannot approve their own requisition.")
    if payload.approved:
        requested_ids = {item.id for item in requisition.items}
        submitted = [item.requisition_item_id for item in payload.items]
        if len(submitted) != len(set(submitted)) or set(submitted) != requested_ids:
            raise HTTPException(status_code=422, detail="Approval must specify exactly one decision for every requisition line.")
        decisions = {item.requisition_item_id: item for item in payload.items}
        if not any(decision.approved_quantity > 0 for decision in payload.items):
            raise HTTPException(status_code=422, detail="At least one line must have a positive approved quantity.")
        for line in requisition.items:
            decision = decisions[line.id]
            if decision.approved_quantity > line.requested_quantity:
                raise HTTPException(status_code=422, detail=f"Approved quantity cannot exceed requested quantity for line {line.id}.")
            line.approved_quantity = decision.approved_quantity
            if decision.estimated_unit_price_paise is not None:
                line.estimated_unit_price_paise = decision.estimated_unit_price_paise
    elif payload.items:
        raise HTTPException(status_code=422, detail="Rejected requisitions must not include approved line quantities.")
    requisition.status = PurchaseRequisitionStatusEnum.APPROVED if payload.approved else PurchaseRequisitionStatusEnum.REJECTED
    requisition.updated_by_id = current_user.id
    requisition.reviewed_by_id = current_user.id
    requisition.reviewed_at = datetime.now(timezone.utc)
    requisition.review_notes = payload.review_notes.strip()
    db.commit()
    db.refresh(requisition)
    return requisition


@router.post(
    "/purchase-requisitions/{requisition_id}/purchase-orders",
    response_model=POResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_purchase_order_from_requisition(
    requisition_id: int,
    payload: PurchaseOrderFromRequisitionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:write")),
):
    requisition = db.query(PurchaseRequisition).options(
        selectinload(PurchaseRequisition.items)
    ).filter(PurchaseRequisition.id == requisition_id).with_for_update().one_or_none()
    if requisition is None:
        raise HTTPException(status_code=404, detail="Purchase requisition not found.")
    if requisition.status not in {
        PurchaseRequisitionStatusEnum.APPROVED,
        PurchaseRequisitionStatusEnum.PARTIALLY_ORDERED,
    }:
        raise HTTPException(status_code=409, detail="Only approved requisitions with remaining approved quantities can create purchase orders.")
    vendor = db.get(VendorMaster, payload.vendor_id)
    if vendor is None:
        raise HTTPException(status_code=409, detail="An active registered vendor is required.")
    _assert_supplier_procurement_eligible(vendor)
    _assert_supplier_compliance_ready(db, vendor)
    if payload.contract_id is not None:
        linked_contract = db.get(SupplierContract, payload.contract_id)
        today = datetime.now(timezone.utc).date()
        if (linked_contract is None or linked_contract.vendor_id != vendor.id
                or linked_contract.status != "ACTIVE"
                or linked_contract.valid_from > today or linked_contract.valid_to < today):
            raise HTTPException(status_code=409, detail="The selected supplier contract must be active, in date, and belong to the PO vendor.")
    vendor_category_code = vendor.category.value if hasattr(vendor.category, "value") else str(vendor.category)
    vendor_budget_category = {
        "PHARMACEUTICALS": "PHARMACY",
        "LAB_REAGENTS": "LABORATORY",
        "EQUIPMENT_MAINTENANCE": "SERVICES",
        "GENERAL_SUPPLIES": "GENERAL_SUPPLIES",
        "SURGICAL_IMPLANTS": "OTHER",
    }.get(vendor_category_code, "OTHER")
    selected_quotes = db.query(SupplierQuotation).options(
        selectinload(SupplierQuotation.items)
    ).filter(
        SupplierQuotation.requisition_id == requisition.id,
        SupplierQuotation.status == SupplierQuotationStatusEnum.SELECTED,
    ).with_for_update().all()
    if len(selected_quotes) > 1:
        raise HTTPException(status_code=409, detail="Multiple selected quotations exist for this requisition; resolve the selection conflict before ordering.")
    selected_quote = selected_quotes[0] if selected_quotes else None
    selected_quote_lines = {
        line.requisition_item_id: line for line in selected_quote.items
    } if selected_quote else {}
    if selected_quote is not None:
        if selected_quote.vendor_id != vendor.id:
            raise HTTPException(status_code=409, detail="Purchase orders must use the supplier selected through the quotation evaluation.")
        if selected_quote.valid_until and selected_quote.valid_until < datetime.now(timezone.utc):
            raise HTTPException(status_code=409, detail="The selected supplier quotation has expired; obtain and select a valid quotation.")
    item_map = {item.id: item for item in requisition.items}
    requested_ids = [item.requisition_item_id for item in payload.items]
    if len(requested_ids) != len(set(requested_ids)):
        raise HTTPException(status_code=422, detail="A requisition line can appear only once in a purchase order.")
    prepared = []
    for item in payload.items:
        req_item = item_map.get(item.requisition_item_id)
        quoted_line = selected_quote_lines.get(item.requisition_item_id) if selected_quote is not None else None
        if selected_quote is not None:
            if quoted_line is None or item.unit_price_paise != quoted_line.unit_price_paise:
                raise HTTPException(status_code=409, detail="Purchase order line pricing must match the selected supplier quotation.")
            if item.tax_percentage is not None and item.tax_percentage != quoted_line.tax_percentage:
                raise HTTPException(status_code=409, detail="Purchase order tax rate must match the selected supplier quotation.")
        if req_item is None or req_item.approved_quantity is None:
            raise HTTPException(status_code=422, detail="Every purchase order line must reference an approved requisition line.")
        if req_item.medication_id is not None and item.budget_category not in (None, "PHARMACY"):
            raise HTTPException(status_code=422, detail="Medication requisition lines must use the PHARMACY budget category.")
        if item.purchase_uom_id != req_item.purchase_uom_id:
            raise HTTPException(status_code=422, detail="Purchase order purchasing unit must match the unit requested on the requisition line.")
        ordered = db.query(func.coalesce(func.sum(PurchaseOrderItem.quantity_ordered), 0)).join(
            PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.po_id
        ).filter(
            PurchaseOrder.requisition_id == requisition.id,
            PurchaseOrderItem.requisition_item_id == req_item.id,
            PurchaseOrder.status != POStatusEnum.CANCELLED,
        ).scalar()
        remaining = req_item.approved_quantity - int(ordered or 0)
        if item.quantity_ordered > remaining:
            raise HTTPException(status_code=409, detail=f"PO quantity exceeds remaining approved quantity for requisition line {req_item.id}.")
        tax_percentage = quoted_line.tax_percentage if quoted_line is not None else (item.tax_percentage or 0)
        if quoted_line is not None:
            requested_uom = db.get(ProcurementUnitOfMeasure, item.purchase_uom_id) if item.purchase_uom_id else None
            if item.purchase_uom_id and (
                requested_uom is None or requested_uom.code != quoted_line.purchase_uom_code
            ):
                raise HTTPException(status_code=409, detail="Purchase order unit must match the selected quotation unit.")
            unit_snapshot = {
                "purchase_uom_code": quoted_line.purchase_uom_code,
                "base_uom_code": quoted_line.base_uom_code,
                "units_per_purchase_unit": quoted_line.units_per_purchase_unit,
                "base_quantity": Decimal(item.quantity_ordered) * Decimal(str(quoted_line.units_per_purchase_unit)) if quoted_line.units_per_purchase_unit is not None else None,
                "base_unit_price_paise": quoted_line.base_unit_price_paise,
            }
            if quoted_line.units_per_purchase_unit is not None and quoted_line.quantity_quoted:
                unit_snapshot["base_quantity"] = Decimal(item.quantity_ordered) * Decimal(str(quoted_line.units_per_purchase_unit))
        else:
            unit_snapshot = _resolve_medication_unit_snapshot(
                db,
                medication_id=req_item.medication_id,
                purchase_uom_id=item.purchase_uom_id,
                quantity=item.quantity_ordered,
                unit_price_paise=item.unit_price_paise,
                effective_at=datetime.now(timezone.utc),
            )
        prepared.append((item, req_item, tax_percentage, unit_snapshot))
    po = PurchaseOrder(
        po_number=_generate_reference("PO"),
        vendor_id=vendor.id,
        contract_id=payload.contract_id,
        requisition_id=requisition.id,
        status=POStatusEnum.SUBMITTED,
        delivery_due_date=payload.delivery_due_date,
        payment_terms=payload.payment_terms,
        created_by_id=current_user.id,
    )
    db.add(po)
    db.flush()
    subtotal = 0
    tax_total = 0
    for item, req_item, tax_percentage, unit_snapshot in prepared:
        line_subtotal = item.quantity_ordered * item.unit_price_paise
        line_tax = (line_subtotal * tax_percentage + 50) // 100
        gross_total = line_subtotal + line_tax
        subtotal += line_subtotal
        tax_total += line_tax
        db.add(PurchaseOrderItem(
            po_id=po.id,
            requisition_item_id=req_item.id,
            medication_id=req_item.medication_id,
            item_description=req_item.item_description,
            quantity_ordered=item.quantity_ordered,
            unit_price_paise=item.unit_price_paise,
            total_price_paise=line_subtotal,
            tax_percentage=tax_percentage,
            tax_amount_paise=line_tax,
            gross_total_paise=gross_total,
            budget_department_id=requisition.requesting_department_id,
            budget_category=item.budget_category or ("PHARMACY" if req_item.medication_id is not None else vendor_budget_category),
            **unit_snapshot,
            created_by_id=current_user.id,
        ))
    po.subtotal_paise = subtotal
    po.tax_amount_paise = tax_total
    po.total_amount_paise = subtotal + tax_total
    all_fulfilled = True
    for req_item in requisition.items:
        ordered = db.query(func.coalesce(func.sum(PurchaseOrderItem.quantity_ordered), 0)).join(
            PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.po_id
        ).filter(
            PurchaseOrder.requisition_id == requisition.id,
            PurchaseOrderItem.requisition_item_id == req_item.id,
            PurchaseOrder.status != POStatusEnum.CANCELLED,
        ).scalar()
        if int(ordered or 0) < int(req_item.approved_quantity or 0):
            all_fulfilled = False
            break
    requisition.status = PurchaseRequisitionStatusEnum.CONVERTED if all_fulfilled else PurchaseRequisitionStatusEnum.PARTIALLY_ORDERED
    requisition.updated_by_id = current_user.id
    db.commit()
    db.refresh(po)
    return po



# --- Supplier quotation collection and evaluation ---
@router.post(
    "/purchase-requisitions/{requisition_id}/quotations",
    response_model=SupplierQuotationResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_supplier_quotation(
    requisition_id: int,
    payload: SupplierQuotationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:write")),
):
    requisition = db.query(PurchaseRequisition).options(
        selectinload(PurchaseRequisition.items)
    ).filter(PurchaseRequisition.id == requisition_id).with_for_update().one_or_none()
    if requisition is None:
        raise HTTPException(status_code=404, detail="Purchase requisition not found.")
    if requisition.status not in {
        PurchaseRequisitionStatusEnum.APPROVED,
        PurchaseRequisitionStatusEnum.PARTIALLY_ORDERED,
    }:
        raise HTTPException(status_code=409, detail="Quotations can only be recorded for approved requisitions.")
    vendor = db.get(VendorMaster, payload.vendor_id)
    if vendor is None or not vendor.is_active:
        raise HTTPException(status_code=409, detail="An active registered vendor is required.")
    line_map = {line.id: line for line in requisition.items}
    line_ids = [line.requisition_item_id for line in payload.items]
    if len(line_ids) != len(set(line_ids)):
        raise HTTPException(status_code=422, detail="A quotation can contain each requisition line only once.")
    if set(line_ids) - set(line_map):
        raise HTTPException(status_code=422, detail="Quotation lines must belong to the selected requisition.")
    required_line_ids = {
        line.id for line in requisition.items
        if line.approved_quantity is not None and line.approved_quantity > 0
    }
    if set(line_ids) != required_line_ids:
        raise HTTPException(status_code=422, detail="A supplier quotation must price every positively approved requisition line to keep comparisons complete.")
    total = 0
    prepared = []
    for line in payload.items:
        req_line = line_map[line.requisition_item_id]
        if req_line.approved_quantity is None or req_line.approved_quantity <= 0:
            raise HTTPException(status_code=422, detail="A quotation cannot price a line with no approved quantity.")
        if line.quantity_quoted != req_line.approved_quantity:
            raise HTTPException(status_code=422, detail="Quoted quantity must equal the approved requisition quantity for that line.")
        if line.purchase_uom_id != req_line.purchase_uom_id:
            raise HTTPException(status_code=422, detail="Supplier quotation purchasing unit must match the unit requested on the requisition line.")
        unit_snapshot = _resolve_medication_unit_snapshot(
            db,
            medication_id=req_line.medication_id,
            purchase_uom_id=line.purchase_uom_id,
            quantity=line.quantity_quoted,
            unit_price_paise=line.unit_price_paise,
            effective_at=payload.quoted_at,
        )
        line_subtotal = line.quantity_quoted * line.unit_price_paise
        line_tax = (line_subtotal * line.tax_percentage + 50) // 100
        line_total = line_subtotal + line_tax
        total += line_total
        prepared.append((line, line_tax, line_total, unit_snapshot))
    quote = SupplierQuotation(
        requisition_id=requisition.id,
        vendor_id=vendor.id,
        quotation_number=payload.quotation_number.strip(),
        quoted_at=payload.quoted_at,
        valid_until=payload.valid_until,
        delivery_days=payload.delivery_days,
        payment_terms=payload.payment_terms,
        notes=payload.notes,
        total_amount_paise=total,
        status=SupplierQuotationStatusEnum.RECEIVED,
        created_by_id=current_user.id,
    )
    db.add(quote)
    db.flush()
    for line, line_tax, line_total, unit_snapshot in prepared:
        db.add(SupplierQuotationItem(
            quotation_id=quote.id,
            requisition_item_id=line.requisition_item_id,
            quantity_quoted=line.quantity_quoted,
            unit_price_paise=line.unit_price_paise,
            tax_percentage=line.tax_percentage,
            tax_amount_paise=line_tax,
            line_total_paise=line_total,
            **unit_snapshot,
            created_by_id=current_user.id,
        ))
    db.commit()
    return db.query(SupplierQuotation).options(
        selectinload(SupplierQuotation.items)
    ).filter(SupplierQuotation.id == quote.id).one()


@router.get(
    "/purchase-requisitions/{requisition_id}/quotations",
    response_model=list[SupplierQuotationResponse],
)
def compare_supplier_quotations(
    requisition_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    requisition = db.get(PurchaseRequisition, requisition_id)
    if requisition is None:
        raise HTTPException(status_code=404, detail="Purchase requisition not found.")
    return db.query(SupplierQuotation).options(
        joinedload(SupplierQuotation.vendor),
        selectinload(SupplierQuotation.items),
    ).filter(
        SupplierQuotation.requisition_id == requisition_id,
        SupplierQuotation.status != SupplierQuotationStatusEnum.WITHDRAWN,
    ).order_by(
        SupplierQuotation.total_amount_paise.asc(),
        SupplierQuotation.delivery_days.asc().nullslast(),
        SupplierQuotation.id.asc(),
    ).all()


@router.patch(
    "/purchase-requisitions/{requisition_id}/quotations/{quotation_id}/select",
    response_model=SupplierQuotationResponse,
)
def select_supplier_quotation(
    requisition_id: int,
    quotation_id: int,
    payload: SupplierQuotationSelection,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:approve")),
):
    requisition = db.query(PurchaseRequisition).filter(
        PurchaseRequisition.id == requisition_id
    ).with_for_update().one_or_none()
    if requisition is None:
        raise HTTPException(status_code=404, detail="Purchase requisition not found.")
    quote = db.query(SupplierQuotation).options(
        selectinload(SupplierQuotation.items)
    ).filter(
        SupplierQuotation.id == quotation_id,
        SupplierQuotation.requisition_id == requisition_id,
    ).with_for_update().one_or_none()
    if quote is None or quote.status != SupplierQuotationStatusEnum.RECEIVED:
        raise HTTPException(status_code=409, detail="Only a received quotation for this requisition can be selected.")
    if quote.created_by_id == current_user.id:
        raise HTTPException(status_code=409, detail="The quotation recorder cannot select their own quotation.")
    existing_selection = db.query(SupplierQuotation.id).filter(
        SupplierQuotation.requisition_id == requisition_id,
        SupplierQuotation.status == SupplierQuotationStatusEnum.SELECTED,
    ).with_for_update().first()
    if existing_selection is not None:
        raise HTTPException(status_code=409, detail="A supplier quotation has already been selected for this requisition.")
    if quote.valid_until and quote.valid_until < datetime.now(timezone.utc):
        raise HTTPException(status_code=409, detail="The supplier quotation has expired.")
    quote.status = SupplierQuotationStatusEnum.SELECTED
    quote.selected_by_id = current_user.id
    quote.selected_at = datetime.now(timezone.utc)
    quote.selection_reason = payload.selection_reason.strip()
    quote.updated_by_id = current_user.id
    alternatives = db.query(SupplierQuotation).filter(
        SupplierQuotation.requisition_id == requisition_id,
        SupplierQuotation.id != quotation_id,
        SupplierQuotation.status == SupplierQuotationStatusEnum.RECEIVED,
    ).with_for_update().all()
    for alternative in alternatives:
        alternative.status = SupplierQuotationStatusEnum.NOT_SELECTED
        alternative.updated_by_id = current_user.id
    db.commit()
    return db.query(SupplierQuotation).options(
        selectinload(SupplierQuotation.items)
    ).filter(SupplierQuotation.id == quotation_id).one()


# --- Purchase Orders ---
@router.post("/purchase-orders", response_model=POResponse, status_code=status.HTTP_201_CREATED)
def draft_purchase_order(payload: POCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("procurement:write"))):
    vendor = db.get(VendorMaster, payload.vendor_id)
    if vendor is None:
        raise HTTPException(status_code=409, detail="An active registered vendor is required to create a purchase order.")
    _assert_supplier_procurement_eligible(vendor)
    _assert_supplier_compliance_ready(db, vendor)
    if payload.contract_id is not None:
        linked_contract = db.get(SupplierContract, payload.contract_id)
        today = datetime.now(timezone.utc).date()
        if (linked_contract is None or linked_contract.vendor_id != vendor.id
                or linked_contract.status != "ACTIVE"
                or linked_contract.valid_from > today or linked_contract.valid_to < today):
            raise HTTPException(status_code=409, detail="The selected supplier contract must be active, in date, and belong to the PO vendor.")
    po = PurchaseOrder(
        po_number=_generate_reference("PO"),
        vendor_id=payload.vendor_id,
        contract_id=payload.contract_id,
        status=POStatusEnum.SUBMITTED,
        delivery_due_date=payload.delivery_due_date,
        payment_terms=payload.payment_terms,
        created_by_id=current_user.id
    )
    db.add(po)
    db.flush()

    assigned_department_ids = {
        row[0] for row in db.query(UserRole.department_id).filter(
            UserRole.user_id == current_user.id,
            UserRole.department_id.is_not(None),
        ).distinct().all() if row[0] is not None
    }
    inferred_department_id = next(iter(assigned_department_ids)) if len(assigned_department_ids) == 1 else None
    vendor_category_code = vendor.category.value if hasattr(vendor.category, "value") else str(vendor.category)
    vendor_budget_category = {
        "PHARMACEUTICALS": "PHARMACY",
        "LAB_REAGENTS": "LABORATORY",
        "EQUIPMENT_MAINTENANCE": "SERVICES",
        "GENERAL_SUPPLIES": "GENERAL_SUPPLIES",
        "SURGICAL_IMPLANTS": "OTHER",
    }.get(vendor_category_code, "OTHER")
    subtotal = 0
    tax_total = 0
    for item in payload.items:
        budget_department_id = item.budget_department_id or inferred_department_id
        if budget_department_id is None:
            raise HTTPException(status_code=422, detail="Select the requesting department for each direct purchase-order line.")
        if budget_department_id is not None and not current_user.is_superuser and not user_has_department_access(db, current_user, budget_department_id):
            raise HTTPException(status_code=403, detail="You are not assigned to the PO line budget department.")
        budget_category = item.budget_category or ("PHARMACY" if item.medication_id is not None else vendor_budget_category)
        line_subtotal = item.quantity_ordered * item.unit_price_paise
        line_tax = (line_subtotal * item.tax_percentage + 50) // 100
        unit_snapshot = _resolve_medication_unit_snapshot(
            db,
            medication_id=item.medication_id,
            purchase_uom_id=item.purchase_uom_id,
            quantity=item.quantity_ordered,
            unit_price_paise=item.unit_price_paise,
            effective_at=po.created_at or datetime.now(timezone.utc),
        )
        subtotal += line_subtotal
        tax_total += line_tax
        db.add(PurchaseOrderItem(
            po_id=po.id,
            medication_id=item.medication_id,
            item_description=item.item_description,
            quantity_ordered=item.quantity_ordered,
            unit_price_paise=item.unit_price_paise,
            total_price_paise=line_subtotal,
            tax_percentage=item.tax_percentage,
            tax_amount_paise=line_tax,
            gross_total_paise=line_subtotal + line_tax,
            **unit_snapshot,
            budget_department_id=budget_department_id,
            budget_category=budget_category,
            created_by_id=current_user.id
        ))

    po.subtotal_paise = subtotal
    po.tax_amount_paise = tax_total
    po.total_amount_paise = subtotal + tax_total
    db.commit()
    db.refresh(po)
    return po




@router.patch("/purchase-orders/{po_id}/cancel")
def cancel_purchase_order(
    po_id: int,
    payload: PurchaseOrderCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:approve")),
):
    po = db.query(PurchaseOrder).options(
        selectinload(PurchaseOrder.items)
    ).filter(PurchaseOrder.id == po_id).with_for_update().one_or_none()
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    if po.status not in {
        POStatusEnum.SUBMITTED,
        POStatusEnum.APPROVED,
        POStatusEnum.PARTIALLY_RECEIVED,
    }:
        raise HTTPException(status_code=409, detail="Only submitted or open approved purchase orders can be cancelled.")
    pending_grn = db.query(GoodsReceiptNote.id).filter(
        GoodsReceiptNote.po_id == po.id,
        GoodsReceiptNote.status == GRNStatusEnum.PENDING_INSPECTION,
    ).first()
    if pending_grn:
        raise HTTPException(status_code=409, detail="Resolve pending GRN inspection before cancelling the purchase order.")
    _release_po_budget_reservations(
        db,
        po,
        current_user,
        reference_suffix=f"CANCEL:{secrets.token_hex(4)}",
        note=f"Outstanding PO commitment released on cancellation: {payload.reason.strip()}",
    )
    po.status = POStatusEnum.CANCELLED
    po.updated_by_id = current_user.id
    db.commit()
    return {
        "status": "CANCELLED",
        "po_id": po.id,
        "po_number": po.po_number,
        "released_commitment": True,
        "reason": payload.reason.strip(),
    }


@router.get("/purchase-orders", response_model=PaginatedResponse[POResponse])
def list_purchase_orders(
    vendor_id: Optional[int] = None,
    po_status: Optional[POStatusEnum] = Query(default=None, alias="status"),
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    page, page_size = validate_pagination(page, page_size)
    query = db.query(PurchaseOrder).options(selectinload(PurchaseOrder.items))
    if vendor_id is not None:
        query = query.filter(PurchaseOrder.vendor_id == vendor_id)
    if po_status is not None:
        query = query.filter(PurchaseOrder.status == po_status)
    total = query.count()
    items = query.order_by(PurchaseOrder.created_at.desc(), PurchaseOrder.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get(
    "/purchase-orders/overdue",
    response_model=list[OverduePurchaseOrderResponse],
)
def list_overdue_purchase_orders(
    as_of: Optional[datetime] = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    now = as_of or datetime.now(timezone.utc)
    query = db.query(PurchaseOrder).options(joinedload(PurchaseOrder.vendor), selectinload(PurchaseOrder.items)).filter(
        PurchaseOrder.status.in_([POStatusEnum.APPROVED, POStatusEnum.PARTIALLY_RECEIVED]),
        PurchaseOrder.delivery_due_date < now,
    ).order_by(PurchaseOrder.delivery_due_date.asc(), PurchaseOrder.id.asc())
    results = []
    for po in query.all():
        outstanding = sum(max(item.quantity_ordered - item.quantity_received, 0) for item in po.items)
        results.append({
            "po_id": po.id,
            "po_number": po.po_number,
            "vendor_id": po.vendor_id,
            "vendor_name": po.vendor.name,
            "delivery_due_date": po.delivery_due_date,
            "days_overdue": max((now.date() - po.delivery_due_date.date()).days, 0),
            "status": po.status,
            "total_amount_paise": po.total_amount_paise,
            "outstanding_quantity": outstanding,
        })
    return results


@router.get("/purchase-orders/{po_id}", response_model=POResponse)
def get_purchase_order(
    po_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    po = db.query(PurchaseOrder).options(selectinload(PurchaseOrder.items)).filter(
        PurchaseOrder.id == po_id
    ).one_or_none()
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    return po


# --- Goods Receipt Note (GRN) ---
@router.post("/grn", status_code=status.HTTP_201_CREATED)
def receive_goods(payload: GRNCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("procurement:write"))):
    po = db.execute(
        select(PurchaseOrder).where(PurchaseOrder.id == payload.po_id).with_for_update()
    ).scalar_one_or_none()
    if po is None or po.status not in {POStatusEnum.APPROVED, POStatusEnum.PARTIALLY_RECEIVED}:
        raise HTTPException(status_code=409, detail="Goods can only be received against an approved, open purchase order.")
    vendor = db.get(VendorMaster, po.vendor_id)
    if vendor is None or not vendor.is_active:
        raise HTTPException(status_code=409, detail="The purchase order vendor is inactive.")

    po_items = {
        item.id: item for item in db.execute(
            select(PurchaseOrderItem).where(PurchaseOrderItem.po_id == po.id)
        ).scalars().all()
    }
    pending_lines = db.query(GoodsReceiptItem).join(GoodsReceiptNote).filter(
        GoodsReceiptNote.po_id == po.id,
        GoodsReceiptNote.status == GRNStatusEnum.PENDING_INSPECTION,
    ).all()
    pending_by_po_item = {}
    for line in pending_lines:
        pending_by_po_item[line.po_item_id] = pending_by_po_item.get(line.po_item_id, 0) + line.accepted_quantity

    prepared_items = []
    for item in payload.items:
        po_item = po_items.get(item.po_item_id)
        if po_item is None:
            raise HTTPException(status_code=422, detail="Every GRN line must belong to the selected purchase order.")
        if item.received_quantity <= 0:
            raise HTTPException(status_code=422, detail="Received quantity must be greater than zero.")
        if item.accepted_quantity > item.received_quantity:
            raise HTTPException(status_code=422, detail="Accepted quantity cannot exceed received quantity.")
        rejected_quantity = item.received_quantity - item.accepted_quantity
        if rejected_quantity and not (item.rejection_reason and item.rejection_reason.strip()):
            raise HTTPException(status_code=422, detail="A rejection reason is required for rejected quantity.")
        total_received = po_item.quantity_received + pending_by_po_item.get(po_item.id, 0) + item.accepted_quantity
        if total_received > po_item.quantity_ordered:
            raise HTTPException(status_code=409, detail=f"Receipt exceeds the remaining quantity for PO item {po_item.id}.")
        prepared_items.append((item, po_item, rejected_quantity))
        pending_by_po_item[po_item.id] = pending_by_po_item.get(po_item.id, 0) + item.accepted_quantity

    if any(po_item.medication_id for _, po_item, _ in prepared_items) and payload.location_id is None:
        raise HTTPException(status_code=422, detail="Select the destination pharmacy location for medication receipts.")

    grn = GoodsReceiptNote(
        grn_number=_generate_reference("GRN"),
        po_id=payload.po_id,
        location_id=payload.location_id,
        invoice_number=payload.invoice_number.strip(),
        invoice_date=payload.invoice_date,
        status=GRNStatusEnum.PENDING_INSPECTION,
        inspected_by_id=None,
        created_by_id=current_user.id,
    )
    db.add(grn)
    db.flush()
    for item, po_item, rejected_quantity in prepared_items:
        db.add(GoodsReceiptItem(
            grn_id=grn.id,
            po_item_id=item.po_item_id,
            batch_number=item.batch_number.strip(),
            expiry_date=item.expiry_date,
            received_quantity=item.received_quantity,
            accepted_quantity=item.accepted_quantity,
            rejected_quantity=rejected_quantity,
            rejection_reason=item.rejection_reason,
            unit_price_paise=po_item.unit_price_paise,
            purchase_uom_code=po_item.purchase_uom_code,
            base_uom_code=po_item.base_uom_code,
            units_per_purchase_unit=po_item.units_per_purchase_unit,
            base_quantity=(Decimal(item.accepted_quantity) * Decimal(str(po_item.units_per_purchase_unit))) if po_item.units_per_purchase_unit is not None else None,
            base_unit_price_paise=po_item.base_unit_price_paise,
            created_by_id=current_user.id,
        ))
    db.commit()
    return {"status": "success", "id": grn.id, "grn_number": grn.grn_number}

@router.patch("/grn/{grn_id}/accept")
def accept_goods(grn_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("procurement:approve"))):
    grn = db.query(GoodsReceiptNote).options(
        selectinload(GoodsReceiptNote.items)
    ).filter(GoodsReceiptNote.id == grn_id).with_for_update().one_or_none()
    if not grn or grn.status != GRNStatusEnum.PENDING_INSPECTION:
        raise HTTPException(status_code=409, detail="GRN is missing or has already been processed.")
    if grn.created_by_id == current_user.id:
        raise HTTPException(status_code=409, detail="The GRN creator cannot inspect and accept the same receipt.")

    process_grn_acceptance(db, grn, current_user.id)
    grn.status = GRNStatusEnum.ACCEPTED
    grn.inspected_by_id = current_user.id
    grn.accepted_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "success", "message": "Goods accepted into the selected pharmacy location."}


@router.get("/grn")
def list_goods_receipt_notes(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    po_id: Optional[int] = None,
    grn_status: Optional[GRNStatusEnum] = Query(default=None, alias="status"),
    page: int = 1,
    page_size: int = 50,
    export_format: Optional[str] = Query(default=None, alias="format"),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    """Lists Goods Receipt Notes (GRN) with date filtering and streaming CSV export."""
    start_at, end_at = resolve_record_date_window(start_date, end_date)
    query = (
        db.query(GoodsReceiptNote)
        .options(
            joinedload(GoodsReceiptNote.purchase_order).joinedload(PurchaseOrder.vendor),
            joinedload(GoodsReceiptNote.items),
        )
    )
    if po_id:
        query = query.filter(GoodsReceiptNote.po_id == po_id)
    if grn_status:
        query = query.filter(GoodsReceiptNote.status == grn_status)
    if start_at is not None and end_at is not None:
        query = query.filter(
            GoodsReceiptNote.created_at >= start_at,
            GoodsReceiptNote.created_at < end_at,
        )

    query = query.order_by(GoodsReceiptNote.id.desc())

    if export_format and export_format.lower() == "csv":
        fieldnames = [
            "id",
            "grn_number",
            "po_number",
            "location_id",
            "vendor_name",
            "invoice_number",
            "invoice_date",
            "items_count",
            "status",
            "created_at",
        ]

        def row_generator():
            for item in chunked_query_fetcher(query, chunk_size=250):
                po = item.purchase_order
                vendor = po.vendor if po else None
                yield {
                    "id": item.id,
                    "grn_number": item.grn_number,
                    "po_number": po.po_number if po else "",
                    "location_id": item.location_id,
                    "vendor_name": vendor.name if vendor else "",
                    "invoice_number": item.invoice_number,
                    "invoice_date": item.invoice_date,
                    "items_count": len(item.items) if item.items else 0,
                    "status": item.status.value if hasattr(item.status, "value") else str(item.status),
                    "created_at": item.created_at,
                }

        filename = f"goods_receipt_notes_{start_date or 'all'}_{end_date or 'all'}"
        return stream_csv_response(row_generator(), fieldnames, filename)

    page, page_size = validate_pagination(page, page_size)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [
            {
                "id": g.id,
                "grn_number": g.grn_number,
                "po_id": g.po_id,
                "po_number": g.purchase_order.po_number if g.purchase_order else None,
                "location_id": g.location_id,
                "vendor_name": g.purchase_order.vendor.name if g.purchase_order and g.purchase_order.vendor else None,
                "invoice_number": g.invoice_number,
                "invoice_date": g.invoice_date,
                "status": g.status,
                "created_at": g.created_at,
            }
            for g in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }

# --- Invoice Upload & AI Matching ---
@router.post("/invoices/upload-document")
def upload_vendor_invoice(
    request: Request,
    vendor_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:write"))
):
    tenant = resolve_tenant_context(request)
    if db.get(VendorMaster, vendor_id) is None:
        raise HTTPException(status_code=404, detail="Vendor not found.")

    try:
        document_key, document_path = store_vendor_invoice_document(
            tenant.subdomain_slug, file.filename, file.file
        )
    finally:
        file.file.close()

    try:
        invoice = VendorInvoice(
            vendor_id=vendor_id,
            invoice_number=_generate_reference("PENDING"),
            invoice_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc),
            subtotal_paise=0,
            total_amount_paise=0,
            status=VendorInvoiceStatusEnum.PENDING_VERIFICATION,
            document_file_url=document_key,
            created_by_id=current_user.id,
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
    except Exception:
        document_path.unlink(missing_ok=True)
        raise

    background_tasks.add_task(
        trigger_donut_invoice_extraction,
        tenant.db_name,
        invoice.id,
        str(document_path),
    )

    return {
        "status": "Processing",
        "invoice_id": invoice.id,
        "message": "Document stored for this hospital and dispatched to invoice extraction."
    }

@router.get("/invoices/{invoice_id}/document")
def download_vendor_invoice_document(
    invoice_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:read")),
):
    tenant = resolve_tenant_context(request)
    invoice = db.get(VendorInvoice, invoice_id)
    if not invoice or not invoice.document_file_url:
        raise HTTPException(status_code=404, detail="Invoice document not found.")

    document_path = resolve_vendor_invoice_document(
        tenant.subdomain_slug, invoice.document_file_url
    )
    media_type = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }[document_path.suffix.lower()]
    db.add(
        ProcurementDocumentDownloadAudit(
            invoice_id=invoice.id,
            invoice_number=invoice.invoice_number,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
        )
    )
    db.commit()
    return FileResponse(
        document_path,
        media_type=media_type,
        filename=f"vendor-invoice-{invoice.id}{document_path.suffix.lower()}",
        headers={
            "Cache-Control": "private, no-store, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Content-Type-Options": "nosniff",
            "X-Download-Options": "noopen",
            "Cross-Origin-Resource-Policy": "same-origin",
        },
    )

@router.get("/invoices", response_model=PaginatedResponse[VendorInvoiceResponse])
def list_vendor_invoices(
    invoice_status: Optional[VendorInvoiceStatusEnum] = Query(default=None),
    vendor_id: Optional[int] = Query(default=None, gt=0),
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    page, page_size = validate_pagination(page, page_size)
    query = db.query(VendorInvoice).options(selectinload(VendorInvoice.items))
    if invoice_status is not None:
        query = query.filter(VendorInvoice.status == invoice_status)
    if vendor_id is not None:
        query = query.filter(VendorInvoice.vendor_id == vendor_id)
    query = query.order_by(VendorInvoice.id.desc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}

@router.get("/invoices/{invoice_id}", response_model=VendorInvoiceResponse)
def get_vendor_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    return _load_vendor_invoice(db, invoice_id)

@router.patch(
    "/invoices/{invoice_id}/review",
    response_model=VendorInvoiceResponse,
)
def review_vendor_invoice(
    invoice_id: int,
    payload: VendorInvoiceReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:write")),
):
    invoice = _load_vendor_invoice(db, invoice_id, for_update=True)
    if invoice.linked_expense_id is not None or invoice.status == VendorInvoiceStatusEnum.PAID:
        raise HTTPException(status_code=409, detail="A posted or paid invoice cannot be changed.")
    if invoice.status not in {
        VendorInvoiceStatusEnum.PENDING_VERIFICATION,
        VendorInvoiceStatusEnum.PRICE_VARIANCE_FLAGGED,
        VendorInvoiceStatusEnum.REJECTED,
    }:
        raise HTTPException(status_code=409, detail="Invoice is not available for review.")

    vendor = db.get(VendorMaster, invoice.vendor_id)
    purchase_order = db.get(PurchaseOrder, payload.po_id) if payload.po_id else None
    if payload.po_id and (
        purchase_order is None or purchase_order.vendor_id != invoice.vendor_id
    ):
        raise HTTPException(status_code=422, detail="Purchase order must belong to this invoice vendor.")

    receipt = db.get(GoodsReceiptNote, payload.grn_id) if payload.grn_id else None
    if payload.grn_id and (
        receipt is None
        or purchase_order is None
        or receipt.po_id != purchase_order.id
    ):
        raise HTTPException(status_code=422, detail="Goods receipt must belong to the selected purchase order.")

    po_items = {item.id: item for item in purchase_order.items} if purchase_order else {}
    if any(item.po_item_id is not None and item.po_item_id not in po_items for item in payload.items):
        raise HTTPException(status_code=422, detail="Invoice line items must reference items from the selected purchase order.")
    for item in payload.items:
        if item.po_item_id is None:
            if item.purchase_uom_code is not None:
                raise HTTPException(status_code=422, detail="An invoice unit can only be supplied when the invoice line is mapped to a purchase-order line.")
            continue
        po_line = po_items[item.po_item_id]
        if item.purchase_uom_code != po_line.purchase_uom_code:
            raise HTTPException(status_code=409, detail="Invoice purchasing unit must match the mapped purchase-order line. Resolve unit differences with a PO amendment before matching.")
    if vendor is None:
        raise HTTPException(status_code=409, detail="Invoice vendor no longer exists.")

    invoice.po_id = payload.po_id
    invoice.grn_id = payload.grn_id
    invoice.invoice_number = payload.invoice_number.strip()
    invoice.invoice_date = payload.invoice_date
    invoice.due_date = payload.due_date
    invoice.subtotal_paise = payload.subtotal_paise
    invoice.tax_amount_paise = payload.tax_amount_paise
    invoice.discount_paise = payload.discount_paise
    invoice.total_amount_paise = payload.total_amount_paise
    invoice.status = VendorInvoiceStatusEnum.PENDING_VERIFICATION
    invoice.notes = None
    invoice.items.clear()
    for item in payload.items:
        invoice.items.append(
            VendorInvoiceItem(
                po_item_id=item.po_item_id,
                medication_id=item.medication_id,
                item_description=item.item_description.strip(),
                batch_number=item.batch_number.strip(),
                expiry_date=item.expiry_date,
                quantity=item.quantity,
                unit_price_paise=item.unit_price_paise,
                tax_percentage=item.tax_percentage,
                total_price_paise=item.total_price_paise,
                purchase_uom_code=po_items[item.po_item_id].purchase_uom_code if item.po_item_id is not None else None,
                base_uom_code=po_items[item.po_item_id].base_uom_code if item.po_item_id is not None else None,
                units_per_purchase_unit=po_items[item.po_item_id].units_per_purchase_unit if item.po_item_id is not None else None,
                base_quantity=(Decimal(item.quantity) * Decimal(str(po_items[item.po_item_id].units_per_purchase_unit))) if item.po_item_id is not None and po_items[item.po_item_id].units_per_purchase_unit is not None else None,
                base_unit_price_paise=po_items[item.po_item_id].base_unit_price_paise if item.po_item_id is not None else None,
                created_by_id=current_user.id,
            )
        )
    db.commit()
    return _load_vendor_invoice(db, invoice_id)

@router.patch("/invoices/{invoice_id}/reconcile", response_model=VendorInvoiceResponse)
def reconcile_invoice_match(invoice_id: int, db: Session = Depends(get_db), _: User = Depends(RequirePermission("procurement:write"))):
    invoice = _load_vendor_invoice(db, invoice_id, for_update=True)
    if invoice.linked_expense_id is not None or invoice.status == VendorInvoiceStatusEnum.PAID:
        raise HTTPException(status_code=409, detail="A posted or paid invoice cannot be reconciled again.")
    match_status = execute_3_way_match(db, invoice)
    invoice.status = match_status
    db.commit()
    db.refresh(invoice)
    return invoice

@router.post("/invoices/{invoice_id}/approve")
def approve_vendor_invoice(invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("finance:approve"))):
    invoice = db.execute(
        select(VendorInvoice)
        .where(VendorInvoice.id == invoice_id)
        .with_for_update()
    ).scalar_one_or_none()
    if invoice and invoice.linked_expense_id is not None:
        raise HTTPException(status_code=409, detail="Invoice has already been posted to accounts payable.")
    if not invoice or invoice.status not in [VendorInvoiceStatusEnum.MATCHED_APPROVED, VendorInvoiceStatusEnum.PRICE_VARIANCE_FLAGGED]:
        raise HTTPException(status_code=400, detail="Invoice must be matched or flagged before financial approval.")
    if invoice.created_by_id == current_user.id:
        raise HTTPException(status_code=409, detail="The invoice uploader cannot approve the same vendor invoice.")

    invoice.status = VendorInvoiceStatusEnum.MATCHED_APPROVED
    invoice.verified_by_id = current_user.id
    invoice.verified_at = datetime.now(timezone.utc)

    post_invoice_to_accounts_payable(db, invoice, current_user.id)
    db.commit()
    return {"status": "success", "message": "Invoice approved and posted to Accounts Payable."}


def _supplier_invoice_paid_amount(db: Session, invoice_id: int) -> int:
    return int(db.query(func.coalesce(func.sum(SupplierPaymentAllocation.amount_paise), 0)).filter(
        SupplierPaymentAllocation.invoice_id == invoice_id
    ).scalar() or 0)



def _supplier_invoice_adjustment_amount(db: Session, invoice_id: int) -> int:
    return int(db.query(func.coalesce(func.sum(SupplierAdjustmentApplication.amount_paise), 0)).join(
        SupplierAdjustment, SupplierAdjustment.id == SupplierAdjustmentApplication.adjustment_id
    ).filter(
        SupplierAdjustmentApplication.invoice_id == invoice_id,
        SupplierAdjustment.status == SupplierAdjustmentStatusEnum.APPROVED,
    ).scalar() or 0)


def _supplier_invoice_advance_amount(db: Session, invoice_id: int) -> int:
    return int(db.query(func.coalesce(func.sum(SupplierAdvanceAllocation.amount_paise), 0)).filter(
        SupplierAdvanceAllocation.invoice_id == invoice_id
    ).scalar() or 0)


def _supplier_invoice_outstanding(db: Session, invoice: VendorInvoice) -> tuple[int, int, int]:
    recorded_cash = _supplier_invoice_paid_amount(db, invoice.id)
    cash = _effective_invoice_paid_amount(
        invoice,
        {invoice.id: recorded_cash} if recorded_cash else {},
    )
    credits = _supplier_invoice_adjustment_amount(db, invoice.id)
    advances = _supplier_invoice_advance_amount(db, invoice.id)
    return max(int(invoice.total_amount_paise) - cash - credits - advances, 0), credits, advances


def _reserved_supplier_payment_amount(
    db: Session, invoice_id: int, *, exclude_request_id: Optional[int] = None
) -> int:
    query = db.query(func.coalesce(func.sum(SupplierPaymentRequestAllocation.amount_paise), 0)).join(
        SupplierPaymentRequest,
        SupplierPaymentRequest.id == SupplierPaymentRequestAllocation.request_id,
    ).filter(
        SupplierPaymentRequestAllocation.invoice_id == invoice_id,
        SupplierPaymentRequest.status.in_(["PENDING", "APPROVED"]),
    )
    if exclude_request_id is not None:
        query = query.filter(SupplierPaymentRequest.id != exclude_request_id)
    return int(query.scalar() or 0)


@router.post("/supplier-adjustments", response_model=SupplierAdjustmentResponse, status_code=status.HTTP_201_CREATED)
def create_supplier_adjustment(
    payload: SupplierAdjustmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:write")),
):
    vendor = db.query(VendorMaster).filter(VendorMaster.id == payload.vendor_id).with_for_update().one_or_none()
    if vendor is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    duplicate = db.query(SupplierAdjustment.id).filter(
        SupplierAdjustment.vendor_id == vendor.id,
        SupplierAdjustment.adjustment_type == payload.adjustment_type,
        SupplierAdjustment.document_number == payload.document_number.strip(),
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="This supplier adjustment document is already recorded.")
    row = SupplierAdjustment(
        vendor_id=vendor.id, adjustment_type=payload.adjustment_type,
        document_number=payload.document_number.strip(), document_date=payload.document_date,
        amount_paise=payload.amount_paise, reason=payload.reason.strip(),
        notes=payload.notes.strip() if payload.notes else None,
        status=SupplierAdjustmentStatusEnum.PENDING, requested_by_id=current_user.id,
        created_by_id=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/vendors/{vendor_id}/adjustments", response_model=list[SupplierAdjustmentResponse])
def list_supplier_adjustments(
    vendor_id: int, db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    if db.get(VendorMaster, vendor_id) is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    return db.query(SupplierAdjustment).filter(
        SupplierAdjustment.vendor_id == vendor_id
    ).order_by(SupplierAdjustment.document_date.desc(), SupplierAdjustment.id.desc()).all()


@router.patch("/supplier-adjustments/{adjustment_id}/review", response_model=SupplierAdjustmentResponse)
def review_supplier_adjustment(
    adjustment_id: int, payload: SupplierAdjustmentReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:approve")),
):
    row = db.query(SupplierAdjustment).filter(
        SupplierAdjustment.id == adjustment_id
    ).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Supplier adjustment not found.")
    if row.status != SupplierAdjustmentStatusEnum.PENDING:
        raise HTTPException(status_code=409, detail="Only pending supplier adjustments can be reviewed.")
    if row.requested_by_id == current_user.id:
        raise HTTPException(status_code=403, detail="The adjustment requester cannot approve their own adjustment.")
    if not payload.approved and not (payload.review_notes or "").strip():
        raise HTTPException(status_code=422, detail="A rejection reason is required.")
    row.status = SupplierAdjustmentStatusEnum.APPROVED if payload.approved else SupplierAdjustmentStatusEnum.REJECTED
    row.reviewed_by_id = current_user.id
    row.reviewed_at = datetime.now(timezone.utc)
    row.review_notes = payload.review_notes.strip() if payload.review_notes else None
    row.updated_by_id = current_user.id
    db.commit()
    db.refresh(row)
    return row


@router.post("/supplier-adjustments/{adjustment_id}/applications", status_code=status.HTTP_201_CREATED)
def apply_supplier_adjustment(
    adjustment_id: int, payload: SupplierAdjustmentApply,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:pay")),
):
    adjustment = db.query(SupplierAdjustment).filter(
        SupplierAdjustment.id == adjustment_id
    ).with_for_update().one_or_none()
    if adjustment is None:
        raise HTTPException(status_code=404, detail="Supplier adjustment not found.")
    if adjustment.status != SupplierAdjustmentStatusEnum.APPROVED:
        raise HTTPException(status_code=409, detail="Only approved supplier adjustments can be applied.")
    invoice = db.query(VendorInvoice).filter(
        VendorInvoice.id == payload.invoice_id
    ).with_for_update().one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Supplier invoice not found.")
    if invoice.vendor_id != adjustment.vendor_id:
        raise HTTPException(status_code=422, detail="Adjustment and invoice must belong to the same supplier.")
    if invoice.status not in {VendorInvoiceStatusEnum.MATCHED_APPROVED, VendorInvoiceStatusEnum.PAID}:
        raise HTTPException(status_code=409, detail="Only approved invoices can receive supplier adjustments.")
    if db.query(SupplierAdjustmentApplication.id).filter(
        SupplierAdjustmentApplication.adjustment_id == adjustment.id,
        SupplierAdjustmentApplication.invoice_id == invoice.id,
    ).first():
        raise HTTPException(status_code=409, detail="This adjustment is already applied to the selected invoice.")
    applied = int(db.query(func.coalesce(func.sum(SupplierAdjustmentApplication.amount_paise), 0)).filter(
        SupplierAdjustmentApplication.adjustment_id == adjustment.id
    ).scalar() or 0)
    if payload.amount_paise > int(adjustment.amount_paise) - applied:
        raise HTTPException(status_code=409, detail="Application exceeds the remaining adjustment value.")
    outstanding, _, _ = _supplier_invoice_outstanding(db, invoice)
    if payload.amount_paise > outstanding:
        raise HTTPException(status_code=409, detail={"message":"Application exceeds invoice outstanding balance.","outstanding_paise":outstanding})
    db.add(SupplierAdjustmentApplication(adjustment_id=adjustment.id, invoice_id=invoice.id, amount_paise=payload.amount_paise))
    db.commit()
    return {"status":"APPLIED","adjustment_id":adjustment.id,"invoice_id":invoice.id,"amount_paise":payload.amount_paise}


@router.post("/supplier-advances", response_model=SupplierAdvanceResponse, status_code=status.HTTP_201_CREATED)
def record_supplier_advance(
    payload: SupplierAdvanceCreate, db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:pay")),
):
    vendor = db.query(VendorMaster).filter(VendorMaster.id == payload.vendor_id).with_for_update().one_or_none()
    if vendor is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    duplicate = db.query(SupplierAdvance.id).filter(
        SupplierAdvance.vendor_id == vendor.id,
        SupplierAdvance.advance_reference == payload.advance_reference.strip(),
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="This supplier advance reference has already been recorded.")
    row = SupplierAdvance(
        vendor_id=vendor.id, advance_reference=payload.advance_reference.strip(),
        payment_method=payload.payment_method, advance_date=payload.advance_date,
        amount_paise=payload.amount_paise, notes=payload.notes.strip() if payload.notes else None,
        recorded_by_id=current_user.id, created_by_id=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/vendors/{vendor_id}/advances", response_model=list[SupplierAdvanceResponse])
def list_supplier_advances(
    vendor_id: int, db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    if db.get(VendorMaster, vendor_id) is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    return db.query(SupplierAdvance).filter(
        SupplierAdvance.vendor_id == vendor_id
    ).order_by(SupplierAdvance.advance_date.desc(), SupplierAdvance.id.desc()).all()


@router.post("/supplier-advances/{advance_id}/applications", status_code=status.HTTP_201_CREATED)
def apply_supplier_advance(
    advance_id: int, payload: SupplierAdvanceApply,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:pay")),
):
    advance = db.query(SupplierAdvance).filter(
        SupplierAdvance.id == advance_id
    ).with_for_update().one_or_none()
    if advance is None:
        raise HTTPException(status_code=404, detail="Supplier advance not found.")
    invoice = db.query(VendorInvoice).filter(
        VendorInvoice.id == payload.invoice_id
    ).with_for_update().one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Supplier invoice not found.")
    if invoice.vendor_id != advance.vendor_id:
        raise HTTPException(status_code=422, detail="Advance and invoice must belong to the same supplier.")
    if invoice.status not in {VendorInvoiceStatusEnum.MATCHED_APPROVED, VendorInvoiceStatusEnum.PAID}:
        raise HTTPException(status_code=409, detail="Only approved invoices can receive supplier advances.")
    if db.query(SupplierAdvanceAllocation.id).filter(
        SupplierAdvanceAllocation.advance_id == advance.id,
        SupplierAdvanceAllocation.invoice_id == invoice.id,
    ).first():
        raise HTTPException(status_code=409, detail="This advance is already applied to the selected invoice.")
    allocated = int(db.query(func.coalesce(func.sum(SupplierAdvanceAllocation.amount_paise), 0)).filter(
        SupplierAdvanceAllocation.advance_id == advance.id
    ).scalar() or 0)
    if payload.amount_paise > int(advance.amount_paise) - allocated:
        raise HTTPException(status_code=409, detail="Application exceeds the remaining advance balance.")
    outstanding, _, _ = _supplier_invoice_outstanding(db, invoice)
    if payload.amount_paise > outstanding:
        raise HTTPException(status_code=409, detail={"message":"Application exceeds invoice outstanding balance.","outstanding_paise":outstanding})
    db.add(SupplierAdvanceAllocation(advance_id=advance.id, invoice_id=invoice.id, amount_paise=payload.amount_paise))
    db.commit()
    return {"status":"APPLIED","advance_id":advance.id,"invoice_id":invoice.id,"amount_paise":payload.amount_paise}




def _bank_line_matched_amount(db: Session, line_id: int) -> int:
    return int(db.query(func.coalesce(func.sum(SupplierPaymentBankMatch.amount_paise), 0)).filter(
        SupplierPaymentBankMatch.statement_line_id == line_id
    ).scalar() or 0)


def _supplier_payment_bank_matched_amount(db: Session, payment_id: int) -> int:
    return int(db.query(func.coalesce(func.sum(SupplierPaymentBankMatch.amount_paise), 0)).filter(
        SupplierPaymentBankMatch.payment_id == payment_id
    ).scalar() or 0)


def _bank_line_reconciliation_status(db: Session, line: BankStatementLine) -> tuple[int, str]:
    matched = _bank_line_matched_amount(db, line.id)
    if matched <= 0:
        return 0, "UNMATCHED"
    if matched >= int(line.amount_paise):
        return matched, "MATCHED"
    return matched, "PARTIALLY_MATCHED"


@router.post("/bank-statements/import", response_model=BankStatementBatchResponse, status_code=status.HTTP_201_CREATED)
def import_supplier_bank_statement(
    payload: BankStatementImportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:pay")),
):
    account_ref = payload.bank_account_ref.strip()
    statement_ref = payload.statement_reference.strip()
    if db.query(BankStatementBatch.id).filter(
        BankStatementBatch.bank_account_ref == account_ref,
        BankStatementBatch.statement_reference == statement_ref,
    ).first():
        raise HTTPException(status_code=409, detail="This bank statement has already been imported.")
    batch = BankStatementBatch(
        bank_account_ref=account_ref, statement_reference=statement_ref,
        period_start=payload.period_start, period_end=payload.period_end,
        opening_balance_paise=payload.opening_balance_paise,
        closing_balance_paise=payload.closing_balance_paise,
        imported_by_id=current_user.id, created_by_id=current_user.id,
    )
    db.add(batch)
    db.flush()
    for item in payload.lines:
        transaction_date = item.transaction_date
        transaction_day = transaction_date.date()
        if transaction_day < payload.period_start or transaction_day > payload.period_end:
            raise HTTPException(status_code=422, detail=f"Transaction {item.bank_transaction_id} falls outside the statement period.")
        transaction_id = item.bank_transaction_id.strip()
        if db.query(BankStatementLine.id).filter(
            BankStatementLine.bank_account_ref == account_ref,
            BankStatementLine.bank_transaction_id == transaction_id,
        ).first():
            raise HTTPException(status_code=409, detail=f"Bank transaction {transaction_id} was already imported.")
        db.add(BankStatementLine(
            batch_id=batch.id, bank_account_ref=account_ref,
            bank_transaction_id=transaction_id, transaction_date=transaction_date,
            value_date=item.value_date, direction=item.direction, amount_paise=item.amount_paise,
            bank_reference=item.bank_reference.strip() if item.bank_reference else None,
            description=item.description.strip() if item.description else None,
        ))
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/bank-statements")
def list_supplier_bank_statements(
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    batches = db.query(BankStatementBatch).order_by(
        BankStatementBatch.period_end.desc(), BankStatementBatch.id.desc()
    ).all()
    result = []
    for batch in batches:
        lines = db.query(BankStatementLine).filter(BankStatementLine.batch_id == batch.id).all()
        debit_lines = [line for line in lines if line.direction == BankStatementDirectionEnum.DEBIT]
        credits = sum(int(line.amount_paise) for line in lines if line.direction == BankStatementDirectionEnum.CREDIT)
        debits = sum(int(line.amount_paise) for line in debit_lines)
        matched = sum(_bank_line_matched_amount(db, line.id) for line in debit_lines)
        result.append({
            "id": batch.id, "bank_account_ref": batch.bank_account_ref,
            "statement_reference": batch.statement_reference,
            "period_start": batch.period_start, "period_end": batch.period_end,
            "opening_balance_paise": batch.opening_balance_paise,
            "closing_balance_paise": batch.closing_balance_paise,
            "line_count": len(lines), "debit_total_paise": debits,
            "credit_total_paise": credits, "matched_debit_paise": matched,
            "unmatched_debit_paise": max(debits - matched, 0),
            "reconciliation_status": "RECONCILED" if debits == matched else ("PARTIALLY_RECONCILED" if matched else "UNRECONCILED"),
        })
    return result


@router.get("/bank-statements/{batch_id}/lines")
def list_supplier_bank_statement_lines(
    batch_id: int, db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    batch = db.get(BankStatementBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Bank statement not found.")
    lines = db.query(BankStatementLine).filter(
        BankStatementLine.batch_id == batch_id
    ).order_by(BankStatementLine.transaction_date, BankStatementLine.id).all()
    result = []
    for line in lines:
        matched, state = _bank_line_reconciliation_status(db, line) if line.direction == BankStatementDirectionEnum.DEBIT else (0, "NOT_APPLICABLE")
        result.append({
            "id": line.id, "batch_id": line.batch_id,
            "bank_transaction_id": line.bank_transaction_id,
            "transaction_date": line.transaction_date, "value_date": line.value_date,
            "direction": line.direction, "amount_paise": line.amount_paise,
            "bank_reference": line.bank_reference, "description": line.description,
            "matched_amount_paise": matched,
            "unmatched_amount_paise": max(int(line.amount_paise) - matched, 0) if line.direction == BankStatementDirectionEnum.DEBIT else 0,
            "reconciliation_status": state,
        })
    return result


@router.get("/bank-statements/{batch_id}/suggestions")
def suggest_supplier_bank_matches(
    batch_id: int, db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    batch = db.get(BankStatementBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Bank statement not found.")
    lines = db.query(BankStatementLine).filter(
        BankStatementLine.batch_id == batch_id,
        BankStatementLine.direction == BankStatementDirectionEnum.DEBIT,
    ).order_by(BankStatementLine.transaction_date, BankStatementLine.id).all()
    suggestions = []
    for line in lines:
        matched_line = _bank_line_matched_amount(db, line.id)
        line_remaining = int(line.amount_paise) - matched_line
        if line_remaining <= 0:
            continue
        reference = (line.bank_reference or "").strip().lower()
        candidates = db.query(SupplierPayment).filter(
            SupplierPayment.payment_date <= line.transaction_date + timedelta(days=7),
            SupplierPayment.payment_date >= line.transaction_date - timedelta(days=7),
        ).order_by(SupplierPayment.payment_date.desc()).limit(100).all()
        candidate_rows = []
        for payment in candidates:
            payment_remaining = int(payment.amount_paise) - _supplier_payment_bank_matched_amount(db, payment.id)
            if payment_remaining <= 0:
                continue
            payment_ref = payment.payment_reference.strip().lower()
            reference_match = bool(reference and (reference in payment_ref or payment_ref in reference))
            amount_match = payment_remaining == line_remaining
            if reference_match or amount_match:
                candidate_rows.append({
                    "payment_id": payment.id, "vendor_id": payment.vendor_id,
                    "payment_reference": payment.payment_reference,
                    "payment_date": payment.payment_date,
                    "payment_amount_paise": payment.amount_paise,
                    "remaining_unreconciled_paise": payment_remaining,
                    "reference_match": reference_match, "amount_match": amount_match,
                })
        suggestions.append({
            "statement_line_id": line.id, "bank_transaction_id": line.bank_transaction_id,
            "bank_reference": line.bank_reference, "amount_paise": line.amount_paise,
            "unmatched_amount_paise": line_remaining, "candidates": candidate_rows,
        })
    return suggestions


@router.post("/bank-statements/lines/{line_id}/matches", status_code=status.HTTP_201_CREATED)
def match_supplier_bank_statement_line(
    line_id: int, payload: SupplierPaymentBankMatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:pay")),
):
    line = db.query(BankStatementLine).filter(
        BankStatementLine.id == line_id
    ).with_for_update().one_or_none()
    if line is None:
        raise HTTPException(status_code=404, detail="Bank statement line not found.")
    if line.direction != BankStatementDirectionEnum.DEBIT:
        raise HTTPException(status_code=422, detail="Only bank debit transactions can be matched to supplier payments.")
    payment = db.query(SupplierPayment).filter(
        SupplierPayment.id == payload.payment_id
    ).with_for_update().one_or_none()
    if payment is None:
        raise HTTPException(status_code=404, detail="Supplier payment not found.")
    if line.transaction_date < payment.payment_date - timedelta(days=7) or line.transaction_date > payment.payment_date + timedelta(days=7):
        if not (payload.match_reason or "").strip():
            raise HTTPException(status_code=422, detail="A reason is required when bank and recorded payment dates differ by more than seven days.")
    if line.bank_reference and line.bank_reference.strip().lower() != payment.payment_reference.strip().lower():
        if not (payload.match_reason or "").strip():
            raise HTTPException(status_code=422, detail="A match reason is required when bank reference differs from the recorded payment reference.")
    line_remaining = int(line.amount_paise) - _bank_line_matched_amount(db, line.id)
    payment_remaining = int(payment.amount_paise) - _supplier_payment_bank_matched_amount(db, payment.id)
    if payload.amount_paise > line_remaining:
        raise HTTPException(status_code=409, detail={"message":"Match exceeds the unmatched bank transaction amount.","unmatched_bank_amount_paise":line_remaining})
    if payload.amount_paise > payment_remaining:
        raise HTTPException(status_code=409, detail={"message":"Match exceeds the unreconciled supplier payment amount.","unreconciled_payment_amount_paise":payment_remaining})
    row = SupplierPaymentBankMatch(
        statement_line_id=line.id, payment_id=payment.id,
        amount_paise=payload.amount_paise, matched_by_id=current_user.id,
        match_reason=payload.match_reason.strip() if payload.match_reason else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id, "statement_line_id": row.statement_line_id,
        "payment_id": row.payment_id, "amount_paise": row.amount_paise,
        "matched_by_id": row.matched_by_id, "matched_at": row.matched_at,
        "match_reason": row.match_reason,
        "statement_line_status": _bank_line_reconciliation_status(db, line)[1],
    }


@router.get("/reconciliation/exceptions")
def get_procurement_reconciliation_exceptions(
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    overdue_days: int = Query(default=0, ge=0, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    """Read-only exception worklist; candidates are investigation signals, not confirmed fraud/errors."""
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must be on or before to_date.")
    today = datetime.now(timezone.utc).date()
    exceptions = []

    def in_window(value):
        day = value.date() if isinstance(value, datetime) else value
        return (from_date is None or day >= from_date) and (to_date is None or day <= to_date)

    # Bank statement debit lines that are not fully reconciled to a recorded supplier payment.
    debit_lines = db.query(BankStatementLine).filter(
        BankStatementLine.direction == BankStatementDirectionEnum.DEBIT
    ).order_by(BankStatementLine.transaction_date, BankStatementLine.id).all()
    for line in debit_lines:
        if not in_window(line.transaction_date):
            continue
        matched, state = _bank_line_reconciliation_status(db, line)
        if state != "MATCHED":
            exceptions.append({
                "exception_type": "UNMATCHED_BANK_DEBIT" if matched == 0 else "PARTIAL_BANK_DEBIT_MATCH",
                "severity": "HIGH" if matched == 0 else "MEDIUM",
                "status": "OPEN",
                "reference_type": "BANK_STATEMENT_LINE",
                "reference_id": line.id,
                "bank_transaction_id": line.bank_transaction_id,
                "bank_account_ref": line.bank_account_ref,
                "transaction_date": line.transaction_date,
                "amount_paise": int(line.amount_paise),
                "matched_amount_paise": matched,
                "unmatched_amount_paise": max(int(line.amount_paise) - matched, 0),
                "description": "Bank debit has no complete supplier-payment reconciliation.",
                "investigation_required": True,
            })

    # Credits are not supplier-payment matches; expose them for treasury classification.
    credit_lines = db.query(BankStatementLine).filter(
        BankStatementLine.direction == BankStatementDirectionEnum.CREDIT
    ).order_by(BankStatementLine.transaction_date, BankStatementLine.id).all()
    for line in credit_lines:
        if in_window(line.transaction_date):
            exceptions.append({
                "exception_type": "UNCLASSIFIED_BANK_CREDIT",
                "severity": "LOW",
                "status": "OPEN",
                "reference_type": "BANK_STATEMENT_LINE",
                "reference_id": line.id,
                "bank_transaction_id": line.bank_transaction_id,
                "bank_account_ref": line.bank_account_ref,
                "transaction_date": line.transaction_date,
                "amount_paise": int(line.amount_paise),
                "matched_amount_paise": 0,
                "unmatched_amount_paise": int(line.amount_paise),
                "description": "Bank credit is imported but is not classified by the supplier-payment reconciliation workflow.",
                "investigation_required": True,
            })

    # Supplier payments not fully evidenced by imported bank debits.
    payments = db.query(SupplierPayment).order_by(
        SupplierPayment.payment_date, SupplierPayment.id
    ).all()
    vendor_ids = {payment.vendor_id for payment in payments}
    vendor_names = {
        vendor.id: vendor.name
        for vendor in db.query(VendorMaster).filter(VendorMaster.id.in_(vendor_ids)).all()
    } if vendor_ids else {}
    normalized_payment_keys = {}
    for payment in payments:
        if not in_window(payment.payment_date):
            continue
        matched = _supplier_payment_bank_matched_amount(db, payment.id)
        remaining = max(int(payment.amount_paise) - matched, 0)
        if remaining:
            exceptions.append({
                "exception_type": "UNRECONCILED_SUPPLIER_PAYMENT" if matched == 0 else "PARTIALLY_RECONCILED_SUPPLIER_PAYMENT",
                "severity": "HIGH" if matched == 0 else "MEDIUM",
                "status": "OPEN",
                "reference_type": "SUPPLIER_PAYMENT",
                "reference_id": payment.id,
                "vendor_id": payment.vendor_id,
                "vendor_name": vendor_names.get(payment.vendor_id),
                "payment_reference": payment.payment_reference,
                "transaction_date": payment.payment_date,
                "amount_paise": int(payment.amount_paise),
                "matched_amount_paise": matched,
                "unmatched_amount_paise": remaining,
                "description": "Recorded supplier outflow is not fully supported by matched bank debit lines.",
                "investigation_required": True,
            })
        normalized_ref = " ".join((payment.payment_reference or "").casefold().split())
        key = (payment.vendor_id, normalized_ref, int(payment.amount_paise))
        normalized_payment_keys.setdefault(key, []).append(payment)
    for (vendor_id, normalized_ref, amount), duplicates in normalized_payment_keys.items():
        if normalized_ref and len(duplicates) > 1:
            for payment in duplicates:
                exceptions.append({
                    "exception_type": "POSSIBLE_DUPLICATE_SUPPLIER_PAYMENT",
                    "severity": "HIGH",
                    "status": "OPEN",
                    "reference_type": "SUPPLIER_PAYMENT",
                    "reference_id": payment.id,
                    "vendor_id": vendor_id,
                    "vendor_name": vendor_names.get(vendor_id),
                    "payment_reference": payment.payment_reference,
                    "transaction_date": payment.payment_date,
                    "amount_paise": amount,
                    "matched_amount_paise": _supplier_payment_bank_matched_amount(db, payment.id),
                    "unmatched_amount_paise": 0,
                    "description": f"Same supplier, normalized reference and amount occur on {len(duplicates)} recorded payments; verify whether these are duplicate records.",
                    "investigation_required": True,
                    "candidate_payment_ids": [row.id for row in duplicates],
                })

    overdue_requests = db.query(SupplierPaymentRequest).filter(
        SupplierPaymentRequest.status == "APPROVED",
        SupplierPaymentRequest.scheduled_date < today - timedelta(days=overdue_days),
    ).order_by(SupplierPaymentRequest.scheduled_date, SupplierPaymentRequest.id).all()
    for request_row in overdue_requests:
        if from_date and request_row.scheduled_date < from_date:
            continue
        if to_date and request_row.scheduled_date > to_date:
            continue
        exceptions.append({
            "exception_type": "OVERDUE_APPROVED_PAYMENT_REQUEST",
            "severity": "HIGH" if (today - request_row.scheduled_date).days > 7 else "MEDIUM",
            "status": "OPEN",
            "reference_type": "SUPPLIER_PAYMENT_REQUEST",
            "reference_id": request_row.id,
            "vendor_id": request_row.vendor_id,
            "payment_reference": request_row.payment_reference,
            "transaction_date": request_row.scheduled_date,
            "amount_paise": int(request_row.amount_paise),
            "matched_amount_paise": 0,
            "unmatched_amount_paise": int(request_row.amount_paise),
            "days_overdue": (today - request_row.scheduled_date).days,
            "description": "Approved payment request passed its scheduled date but has not been executed.",
            "investigation_required": True,
        })

    severity_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    exceptions.sort(key=lambda row: (
        severity_rank.get(row["severity"], 9),
        (row.get("transaction_date").isoformat() if row.get("transaction_date") else ""),
        row["exception_type"],
        row["reference_id"],
    ))
    counts = {}
    for row in exceptions:
        counts[row["exception_type"]] = counts.get(row["exception_type"], 0) + 1
    return {
        "as_of_date": today.isoformat(),
        "filters": {
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
            "overdue_days": overdue_days,
        },
        "summary": {
            "total_exceptions": len(exceptions),
            "high_severity_count": sum(1 for row in exceptions if row["severity"] == "HIGH"),
            "medium_severity_count": sum(1 for row in exceptions if row["severity"] == "MEDIUM"),
            "low_severity_count": sum(1 for row in exceptions if row["severity"] == "LOW"),
            "by_type": counts,
        },
        "exceptions": exceptions,
        "controls": {
            "read_only": True,
            "duplicate_payment_detection": "Candidate detection only; same vendor, normalized reference and amount must be manually investigated before declaring a duplicate.",
            "bank_credit_classification": "All imported bank credits are surfaced because this supplier debit-matching workflow does not classify receipts or transfers.",
            "limitations": [
                "Exceptions are derived live and are not persisted, assigned or resolved in this version.",
                "Unmatched transactions may be timing differences, bank fees, transfers or payments outside the imported statement window.",
                "A payment mismatch is an unreconciled amount, not proof of an incorrect payment.",
            ],
        },
    }


@router.get("/supplier-payments/reconciliation")
def get_supplier_payment_reconciliation(
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must be on or before to_date.")
    payments = db.query(SupplierPayment).order_by(SupplierPayment.payment_date.desc()).all()
    bank_lines = db.query(BankStatementLine).filter(
        BankStatementLine.direction == BankStatementDirectionEnum.DEBIT
    ).order_by(BankStatementLine.transaction_date.desc()).all()
    if from_date:
        payments = [p for p in payments if p.payment_date.date() >= from_date]
        bank_lines = [line for line in bank_lines if line.transaction_date.date() >= from_date]
    if to_date:
        payments = [p for p in payments if p.payment_date.date() <= to_date]
        bank_lines = [line for line in bank_lines if line.transaction_date.date() <= to_date]
    payment_rows = []
    for payment in payments:
        matched = _supplier_payment_bank_matched_amount(db, payment.id)
        payment_rows.append({
            "payment_id": payment.id, "vendor_id": payment.vendor_id,
            "payment_reference": payment.payment_reference, "payment_date": payment.payment_date,
            "amount_paise": payment.amount_paise, "matched_amount_paise": matched,
            "unreconciled_amount_paise": max(int(payment.amount_paise) - matched, 0),
            "status": "RECONCILED" if matched >= int(payment.amount_paise) else ("PARTIALLY_RECONCILED" if matched else "UNRECONCILED"),
        })
    line_rows = []
    for line in bank_lines:
        matched, state = _bank_line_reconciliation_status(db, line)
        if state != "MATCHED":
            line_rows.append({
                "statement_line_id": line.id, "bank_transaction_id": line.bank_transaction_id,
                "transaction_date": line.transaction_date, "bank_reference": line.bank_reference,
                "amount_paise": line.amount_paise, "matched_amount_paise": matched,
                "unmatched_amount_paise": max(int(line.amount_paise) - matched, 0),
                "status": state,
            })
    return {
        "supplier_payments": payment_rows,
        "unmatched_or_partial_bank_debits": line_rows,
        "totals": {
            "supplier_payment_value_paise": sum(int(p.amount_paise) for p in payments),
            "matched_supplier_payment_value_paise": sum(_supplier_payment_bank_matched_amount(db, p.id) for p in payments),
            "unreconciled_supplier_payment_value_paise": sum(max(int(p.amount_paise) - _supplier_payment_bank_matched_amount(db, p.id), 0) for p in payments),
        },
    }



@router.post("/supplier-payments", response_model=SupplierPaymentResponse, status_code=status.HTTP_201_CREATED)
def record_supplier_payment(
    payload: SupplierPaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:pay")),
):
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="Direct supplier payment recording is a superuser break-glass action. Use the payment request and approval workflow.",
        )
    vendor = db.query(VendorMaster).filter(VendorMaster.id == payload.vendor_id).with_for_update().one_or_none()
    if vendor is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    duplicate = db.query(SupplierPayment.id).filter(
        SupplierPayment.vendor_id == vendor.id,
        SupplierPayment.payment_reference == payload.payment_reference.strip(),
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="This supplier payment reference has already been recorded.")

    invoice_ids = sorted(row.invoice_id for row in payload.allocations)
    invoices = db.query(VendorInvoice).filter(
        VendorInvoice.id.in_(invoice_ids)
    ).order_by(VendorInvoice.id).with_for_update().all()
    invoice_by_id = {row.id: row for row in invoices}
    if set(invoice_by_id) != set(invoice_ids):
        raise HTTPException(status_code=404, detail="One or more supplier invoices were not found.")

    for allocation in payload.allocations:
        invoice = invoice_by_id[allocation.invoice_id]
        if invoice.vendor_id != vendor.id:
            raise HTTPException(status_code=422, detail="A payment can only be allocated to invoices belonging to the selected supplier.")
        if invoice.status not in {VendorInvoiceStatusEnum.MATCHED_APPROVED, VendorInvoiceStatusEnum.PAID}:
            raise HTTPException(status_code=409, detail=f"Invoice {invoice.invoice_number} is not approved for settlement.")
        if invoice.linked_expense_id is None:
            raise HTTPException(status_code=409, detail=f"Invoice {invoice.invoice_number} has no Accounts Payable posting.")
        expense = db.get(ExpenseRecord, invoice.linked_expense_id)
        if expense is None or expense.status != ExpenseStatusEnum.APPROVED:
            raise HTTPException(status_code=409, detail=f"Accounts Payable entry for invoice {invoice.invoice_number} is not payable or has already been settled.")
        outstanding, _, _ = _supplier_invoice_outstanding(db, invoice)
        reserved = _reserved_supplier_payment_amount(db, invoice.id)
        available = max(outstanding - reserved, 0)
        if allocation.amount_paise > available:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": f"Allocation exceeds the outstanding balance for invoice {invoice.invoice_number}.",
                    "invoice_id": invoice.id,
                    "outstanding_paise": max(outstanding, 0),
                    "reserved_paise": reserved,
                    "available_paise": available,
                },
            )
        if outstanding <= 0:
            raise HTTPException(status_code=409, detail=f"Invoice {invoice.invoice_number} is already fully settled.")

    payment = SupplierPayment(
        vendor_id=vendor.id,
        payment_reference=payload.payment_reference.strip(),
        payment_method=payload.payment_method,
        payment_date=payload.payment_date,
        amount_paise=payload.amount_paise,
        notes=(f"[SUPERUSER DIRECT SETTLEMENT by user {current_user.id}] " + (payload.notes.strip() if payload.notes else "Break-glass settlement")),
        recorded_by_id=current_user.id,
        created_by_id=current_user.id,
    )
    for allocation in payload.allocations:
        payment.allocations.append(SupplierPaymentAllocation(
            invoice_id=allocation.invoice_id,
            amount_paise=allocation.amount_paise,
        ))
    db.add(payment)
    db.flush()

    for invoice in invoices:
        paid_amount = _supplier_invoice_paid_amount(db, invoice.id)
        if paid_amount >= int(invoice.total_amount_paise):
            invoice.status = VendorInvoiceStatusEnum.PAID
            expense = db.get(ExpenseRecord, invoice.linked_expense_id)
            expense.status = ExpenseStatusEnum.PAID
            expense.receipt_reference = payment.payment_reference
            expense.updated_by_id = current_user.id
        else:
            invoice.status = VendorInvoiceStatusEnum.MATCHED_APPROVED

    db.commit()
    return db.query(SupplierPayment).options(
        selectinload(SupplierPayment.allocations)
    ).filter(SupplierPayment.id == payment.id).one()


@router.get("/vendors/{vendor_id}/payments", response_model=list[SupplierPaymentResponse])
def list_supplier_payments(
    vendor_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    if db.get(VendorMaster, vendor_id) is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    return db.query(SupplierPayment).options(
        selectinload(SupplierPayment.allocations)
    ).filter(
        SupplierPayment.vendor_id == vendor_id
    ).order_by(SupplierPayment.payment_date.desc(), SupplierPayment.id.desc()).all()


@router.get("/analytics/payment-priorities")
def get_supplier_payment_priorities(
    due_within_days: int = Query(default=30, ge=0, le=365),
    vendor_id: Optional[int] = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    """Prioritized AP queue based on net invoice balances and contractual due dates."""
    today = datetime.now(timezone.utc).date()
    query = db.query(VendorInvoice, VendorMaster.name).join(
        VendorMaster, VendorMaster.id == VendorInvoice.vendor_id
    ).filter(
        VendorInvoice.status.in_([
            VendorInvoiceStatusEnum.MATCHED_APPROVED,
            VendorInvoiceStatusEnum.PAID,
        ])
    )
    if vendor_id is not None:
        query = query.filter(VendorInvoice.vendor_id == vendor_id)
    records = query.order_by(VendorInvoice.due_date.asc(), VendorInvoice.id.asc()).all()

    rows = []
    for invoice, vendor_name in records:
        outstanding, credits, advances = _supplier_invoice_outstanding(db, invoice)
        outstanding = max(int(outstanding), 0)
        reserved = _reserved_supplier_payment_amount(db, invoice.id)
        available_to_schedule = max(outstanding - reserved, 0)
        if outstanding <= 0:
            continue
        due_date = invoice.due_date.date() if isinstance(invoice.due_date, datetime) else invoice.due_date
        days_until_due = (due_date - today).days
        if days_until_due > due_within_days:
            continue
        priority = "OVERDUE" if days_until_due < 0 else (
            "DUE_TODAY" if days_until_due == 0 else (
                "DUE_SOON" if days_until_due <= 7 else "UPCOMING"
            )
        )
        recorded_paid = _supplier_invoice_paid_amount(db, invoice.id)
        paid = _effective_invoice_paid_amount(
            invoice, {invoice.id: recorded_paid} if recorded_paid else {}
        )
        rows.append({
            "invoice_id": invoice.id,
            "vendor_id": invoice.vendor_id,
            "vendor_name": vendor_name,
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.invoice_date,
            "due_date": invoice.due_date,
            "days_until_due": days_until_due,
            "priority": priority,
            "invoice_total_paise": int(invoice.total_amount_paise),
            "amount_paid_paise": int(paid),
            "credit_adjustments_paise": int(credits),
            "advances_applied_paise": int(advances),
            "outstanding_paise": outstanding,
            "reserved_paise": reserved,
            "available_to_schedule_paise": available_to_schedule,
        })

    priority_order = {"OVERDUE": 0, "DUE_TODAY": 1, "DUE_SOON": 2, "UPCOMING": 3}
    rows.sort(key=lambda row: (
        priority_order[row["priority"]],
        row["days_until_due"],
        row["due_date"],
        row["invoice_id"],
    ))
    totals = {
        "invoice_count": len(rows),
        "outstanding_paise": sum(row["outstanding_paise"] for row in rows),
        "reserved_paise": sum(row["reserved_paise"] for row in rows),
        "available_to_schedule_paise": sum(row["available_to_schedule_paise"] for row in rows),
        "overdue_count": sum(row["priority"] == "OVERDUE" for row in rows),
        "overdue_paise": sum(row["outstanding_paise"] for row in rows if row["priority"] == "OVERDUE"),
        "due_today_count": sum(row["priority"] == "DUE_TODAY" for row in rows),
        "due_today_paise": sum(row["outstanding_paise"] for row in rows if row["priority"] == "DUE_TODAY"),
        "due_soon_count": sum(row["priority"] == "DUE_SOON" for row in rows),
        "due_soon_paise": sum(row["outstanding_paise"] for row in rows if row["priority"] == "DUE_SOON"),
        "upcoming_count": sum(row["priority"] == "UPCOMING" for row in rows),
        "upcoming_paise": sum(row["outstanding_paise"] for row in rows if row["priority"] == "UPCOMING"),
    }
    return {
        "as_of_date": today,
        "due_within_days": due_within_days,
        "vendor_id": vendor_id,
        "totals": totals,
        "invoices": rows,
    }


@router.post(
    "/supplier-payment-requests",
    response_model=SupplierPaymentRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_supplier_payment_request(
    payload: SupplierPaymentRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:write")),
):
    vendor = db.query(VendorMaster).filter(
        VendorMaster.id == payload.vendor_id
    ).with_for_update().one_or_none()
    if vendor is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    if not vendor.is_active or vendor.is_suspended:
        raise HTTPException(status_code=409, detail="Inactive or suspended suppliers cannot receive new payment requests.")
    if db.query(SupplierPayment.id).filter(
        SupplierPayment.vendor_id == vendor.id,
        SupplierPayment.payment_reference == payload.payment_reference.strip(),
    ).first():
        raise HTTPException(status_code=409, detail="This payment reference is already recorded.")
    if db.query(SupplierPaymentRequest.id).filter(
        SupplierPaymentRequest.vendor_id == vendor.id,
        SupplierPaymentRequest.payment_reference == payload.payment_reference.strip(),
    ).first():
        raise HTTPException(status_code=409, detail="This payment reference already has a request.")

    invoice_ids = sorted(row.invoice_id for row in payload.allocations)
    invoices = db.query(VendorInvoice).filter(
        VendorInvoice.id.in_(invoice_ids)
    ).order_by(VendorInvoice.id).with_for_update().all()
    by_id = {row.id: row for row in invoices}
    if set(by_id) != set(invoice_ids):
        raise HTTPException(status_code=404, detail="One or more supplier invoices were not found.")
    for allocation in payload.allocations:
        invoice = by_id[allocation.invoice_id]
        if invoice.vendor_id != vendor.id:
            raise HTTPException(status_code=422, detail="A payment request can only include invoices from its selected supplier.")
        if invoice.status not in {VendorInvoiceStatusEnum.MATCHED_APPROVED, VendorInvoiceStatusEnum.PAID}:
            raise HTTPException(status_code=409, detail=f"Invoice {invoice.invoice_number} is not approved for settlement.")
        if invoice.linked_expense_id is None:
            raise HTTPException(status_code=409, detail=f"Invoice {invoice.invoice_number} has no Accounts Payable posting.")
        expense = db.get(ExpenseRecord, invoice.linked_expense_id)
        if expense is None or expense.status != ExpenseStatusEnum.APPROVED:
            raise HTTPException(status_code=409, detail=f"Accounts Payable entry for invoice {invoice.invoice_number} is not payable.")
        outstanding, _, _ = _supplier_invoice_outstanding(db, invoice)
        reserved = _reserved_supplier_payment_amount(db, invoice.id)
        available = max(outstanding - reserved, 0)
        if allocation.amount_paise > available:
            raise HTTPException(status_code=409, detail={
                "message": f"Payment request exceeds the unreserved balance for invoice {invoice.invoice_number}.",
                "invoice_id": invoice.id, "outstanding_paise": outstanding,
                "reserved_paise": reserved, "available_paise": available,
            })

    request_row = SupplierPaymentRequest(
        vendor_id=vendor.id,
        payment_reference=payload.payment_reference.strip(),
        payment_method=payload.payment_method,
        scheduled_date=payload.scheduled_date,
        payment_run_reference=payload.payment_run_reference.strip() if payload.payment_run_reference else None,
        amount_paise=payload.amount_paise,
        notes=payload.notes.strip() if payload.notes else None,
        status="PENDING",
        requested_by_id=current_user.id,
        created_by_id=current_user.id,
    )
    request_row.allocations = [
        SupplierPaymentRequestAllocation(invoice_id=row.invoice_id, amount_paise=row.amount_paise)
        for row in payload.allocations
    ]
    db.add(request_row)
    db.commit()
    return db.query(SupplierPaymentRequest).options(
        selectinload(SupplierPaymentRequest.allocations)
    ).filter(SupplierPaymentRequest.id == request_row.id).one()


@router.get("/supplier-payment-requests", response_model=list[SupplierPaymentRequestResponse])
def list_supplier_payment_requests(
    status_filter: Optional[str] = Query(default=None, alias="status", pattern="^(PENDING|APPROVED|REJECTED|EXECUTED|CANCELLED)$"),
    vendor_id: Optional[int] = Query(default=None, gt=0),
    payment_run_reference: Optional[str] = Query(default=None, min_length=2, max_length=100),
    scheduled_from: Optional[date] = Query(default=None),
    scheduled_to: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    if scheduled_from and scheduled_to and scheduled_from > scheduled_to:
        raise HTTPException(status_code=422, detail="scheduled_from must be on or before scheduled_to.")
    query = db.query(SupplierPaymentRequest).options(
        selectinload(SupplierPaymentRequest.allocations)
    )
    if status_filter:
        query = query.filter(SupplierPaymentRequest.status == status_filter)
    if vendor_id:
        query = query.filter(SupplierPaymentRequest.vendor_id == vendor_id)
    if payment_run_reference:
        query = query.filter(SupplierPaymentRequest.payment_run_reference == payment_run_reference.strip())
    if scheduled_from:
        query = query.filter(SupplierPaymentRequest.scheduled_date >= scheduled_from)
    if scheduled_to:
        query = query.filter(SupplierPaymentRequest.scheduled_date <= scheduled_to)
    return query.order_by(
        SupplierPaymentRequest.scheduled_date.asc(),
        SupplierPaymentRequest.id.asc(),
    ).all()


@router.patch(
    "/supplier-payment-requests/{request_id}/review",
    response_model=SupplierPaymentRequestResponse,
)
def review_supplier_payment_request(
    request_id: int,
    payload: SupplierPaymentRequestReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:approve")),
):
    request_row = db.query(SupplierPaymentRequest).options(
        selectinload(SupplierPaymentRequest.allocations)
    ).filter(SupplierPaymentRequest.id == request_id).with_for_update().one_or_none()
    if request_row is None:
        raise HTTPException(status_code=404, detail="Supplier payment request not found.")
    if request_row.status != "PENDING":
        raise HTTPException(status_code=409, detail="Only pending payment requests can be reviewed.")
    if request_row.requested_by_id == current_user.id:
        raise HTTPException(status_code=403, detail="The payment requester cannot approve or reject their own request.")
    if payload.approved:
        invoice_ids = sorted(row.invoice_id for row in request_row.allocations)
        invoices = db.query(VendorInvoice).filter(
            VendorInvoice.id.in_(invoice_ids)
        ).order_by(VendorInvoice.id).with_for_update().all()
        by_id = {row.id: row for row in invoices}
        for allocation in request_row.allocations:
            invoice = by_id.get(allocation.invoice_id)
            if invoice is None or invoice.vendor_id != request_row.vendor_id:
                raise HTTPException(status_code=409, detail="A requested invoice is no longer available for this supplier.")
            if invoice.status not in {VendorInvoiceStatusEnum.MATCHED_APPROVED, VendorInvoiceStatusEnum.PAID} or invoice.linked_expense_id is None:
                raise HTTPException(status_code=409, detail="A requested invoice is no longer approved for settlement.")
            expense = db.get(ExpenseRecord, invoice.linked_expense_id)
            if expense is None or expense.status != ExpenseStatusEnum.APPROVED:
                raise HTTPException(status_code=409, detail="A requested Accounts Payable entry is no longer payable.")
            outstanding, _, _ = _supplier_invoice_outstanding(db, invoice)
            reserved = _reserved_supplier_payment_amount(
                db, invoice.id, exclude_request_id=request_row.id
            )
            available = max(outstanding - reserved, 0)
            if allocation.amount_paise > available:
                raise HTTPException(status_code=409, detail={
                    "message": f"Invoice {invoice.invoice_number} no longer has enough unreserved balance.",
                    "invoice_id": invoice.id, "outstanding_paise": outstanding,
                    "reserved_paise": reserved, "available_paise": available,
                })
        request_row.status = "APPROVED"
    else:
        request_row.status = "REJECTED"
    request_row.reviewed_by_id = current_user.id
    request_row.reviewed_at = datetime.now(timezone.utc)
    request_row.review_notes = payload.review_notes.strip()
    request_row.updated_by_id = current_user.id
    db.commit()
    return db.query(SupplierPaymentRequest).options(
        selectinload(SupplierPaymentRequest.allocations)
    ).filter(SupplierPaymentRequest.id == request_row.id).one()


@router.post(
    "/supplier-payment-requests/{request_id}/execute",
    response_model=SupplierPaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def execute_supplier_payment_request(
    request_id: int,
    payload: SupplierPaymentRequestExecute,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:pay")),
):
    request_row = db.query(SupplierPaymentRequest).options(
        selectinload(SupplierPaymentRequest.allocations)
    ).filter(SupplierPaymentRequest.id == request_id).with_for_update().one_or_none()
    if request_row is None:
        raise HTTPException(status_code=404, detail="Supplier payment request not found.")
    if request_row.status != "APPROVED":
        raise HTTPException(status_code=409, detail="Only approved payment requests can be executed.")
    if request_row.scheduled_date > datetime.now(timezone.utc).date():
        raise HTTPException(status_code=409, detail="This payment is scheduled for a future date and cannot yet be executed.")
    if db.query(SupplierPayment.id).filter(
        SupplierPayment.vendor_id == request_row.vendor_id,
        SupplierPayment.payment_reference == request_row.payment_reference,
    ).first():
        raise HTTPException(status_code=409, detail="The payment reference has already been recorded outside this request.")
    vendor = db.query(VendorMaster).filter(
        VendorMaster.id == request_row.vendor_id
    ).with_for_update().one_or_none()
    if vendor is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    invoice_ids = sorted(row.invoice_id for row in request_row.allocations)
    invoices = db.query(VendorInvoice).filter(
        VendorInvoice.id.in_(invoice_ids)
    ).order_by(VendorInvoice.id).with_for_update().all()
    by_id = {row.id: row for row in invoices}
    if set(by_id) != set(invoice_ids):
        raise HTTPException(status_code=409, detail="A requested invoice no longer exists.")
    for allocation in request_row.allocations:
        invoice = by_id[allocation.invoice_id]
        if invoice.status not in {VendorInvoiceStatusEnum.MATCHED_APPROVED, VendorInvoiceStatusEnum.PAID}:
            raise HTTPException(status_code=409, detail=f"Invoice {invoice.invoice_number} is no longer approved for settlement.")
        outstanding, _, _ = _supplier_invoice_outstanding(db, invoice)
        reserved = _reserved_supplier_payment_amount(
            db, invoice.id, exclude_request_id=request_row.id
        )
        available = max(outstanding - reserved, 0)
        if invoice.vendor_id != vendor.id or allocation.amount_paise > available:
            raise HTTPException(status_code=409, detail={
                "message": f"Invoice {invoice.invoice_number} no longer has sufficient unreserved balance.",
                "invoice_id": invoice.id, "outstanding_paise": outstanding,
                "reserved_paise": reserved, "available_paise": available,
            })
        if invoice.linked_expense_id is None:
            raise HTTPException(status_code=409, detail="A requested invoice no longer has an Accounts Payable posting.")
        expense = db.get(ExpenseRecord, invoice.linked_expense_id)
        if expense is None or expense.status != ExpenseStatusEnum.APPROVED:
            raise HTTPException(status_code=409, detail="A requested Accounts Payable entry is no longer payable.")

    payment = SupplierPayment(
        vendor_id=vendor.id,
        payment_reference=request_row.payment_reference,
        payment_method=request_row.payment_method,
        payment_date=payload.payment_date,
        amount_paise=request_row.amount_paise,
        notes=request_row.notes,
        recorded_by_id=current_user.id,
        created_by_id=current_user.id,
    )
    payment.allocations = [
        SupplierPaymentAllocation(invoice_id=row.invoice_id, amount_paise=row.amount_paise)
        for row in request_row.allocations
    ]
    db.add(payment)
    db.flush()
    for invoice in invoices:
        paid_amount = _supplier_invoice_paid_amount(db, invoice.id)
        if paid_amount >= int(invoice.total_amount_paise):
            invoice.status = VendorInvoiceStatusEnum.PAID
            expense = db.get(ExpenseRecord, invoice.linked_expense_id)
            expense.status = ExpenseStatusEnum.PAID
            expense.receipt_reference = payment.payment_reference
            expense.updated_by_id = current_user.id
        else:
            invoice.status = VendorInvoiceStatusEnum.MATCHED_APPROVED
    request_row.status = "EXECUTED"
    request_row.executed_payment_id = payment.id
    request_row.executed_at = datetime.now(timezone.utc)
    request_row.updated_by_id = current_user.id
    db.commit()
    return db.query(SupplierPayment).options(
        selectinload(SupplierPayment.allocations)
    ).filter(SupplierPayment.id == payment.id).one()


@router.post(
    "/supplier-payment-requests/{request_id}/cancel",
    response_model=SupplierPaymentRequestResponse,
)
def cancel_supplier_payment_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:write")),
):
    request_row = db.query(SupplierPaymentRequest).options(
        selectinload(SupplierPaymentRequest.allocations)
    ).filter(SupplierPaymentRequest.id == request_id).with_for_update().one_or_none()
    if request_row is None:
        raise HTTPException(status_code=404, detail="Supplier payment request not found.")
    if request_row.requested_by_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only the requester or a superuser can cancel this request.")
    if request_row.status not in {"PENDING", "APPROVED"}:
        raise HTTPException(status_code=409, detail="Only pending or approved requests can be cancelled.")
    request_row.status = "CANCELLED"
    request_row.updated_by_id = current_user.id
    db.commit()
    return db.query(SupplierPaymentRequest).options(
        selectinload(SupplierPaymentRequest.allocations)
    ).filter(SupplierPaymentRequest.id == request_row.id).one()


@router.get("/invoices/{invoice_id}/settlement", response_model=SupplierInvoiceSettlementResponse)
def get_supplier_invoice_settlement(
    invoice_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    invoice = db.get(VendorInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    recorded_paid = _supplier_invoice_paid_amount(db, invoice.id)
    paid = _effective_invoice_paid_amount(invoice, {invoice.id: recorded_paid} if recorded_paid else {})
    outstanding, credits, advances = _supplier_invoice_outstanding(db, invoice)
    return {
        "invoice_id": invoice.id,
        "vendor_id": invoice.vendor_id,
        "invoice_number": invoice.invoice_number,
        "invoice_total_paise": invoice.total_amount_paise,
        "amount_paid_paise": paid,
        "credit_adjustments_paise": credits,
        "advances_applied_paise": advances,
        "outstanding_paise": outstanding,
        "status": invoice.status,
    }


# --- Purchase Order Approval & PDF ---

# --- Purchase order amendment lifecycle ---
@router.post(
    "/purchase-orders/{po_id}/amendments",
    response_model=PurchaseOrderAmendmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_purchase_order_amendment(
    po_id: int,
    payload: PurchaseOrderAmendmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:write")),
):
    po = db.query(PurchaseOrder).options(
        selectinload(PurchaseOrder.items)
    ).filter(PurchaseOrder.id == po_id).with_for_update().one_or_none()
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    if po.status != POStatusEnum.APPROVED:
        raise HTTPException(status_code=409, detail="Only approved purchase orders can be amended.")
    if db.query(GoodsReceiptNote.id).filter(GoodsReceiptNote.po_id == po.id).first():
        raise HTTPException(status_code=409, detail="A purchase order with receipt activity cannot be amended.")
    if db.query(PurchaseOrderAmendment.id).filter(
        PurchaseOrderAmendment.po_id == po.id,
        PurchaseOrderAmendment.status == POAmendmentStatusEnum.PENDING,
    ).first():
        raise HTTPException(status_code=409, detail="A pending amendment already exists.")

    proposed_items = []
    proposed_total = 0
    seen_requisition_lines = set()
    for item in payload.items:
        prior_line = next((
            existing for existing in po.items
            if (
                (item.requisition_item_id is not None and existing.requisition_item_id == item.requisition_item_id)
                or (
                    item.requisition_item_id is None
                    and existing.medication_id == item.medication_id
                    and existing.item_description.strip().lower() == item.item_description.strip().lower()
                )
            )
        ), None)
        if prior_line is not None and prior_line.purchase_uom_code is not None and item.purchase_uom_id is None:
            raise HTTPException(status_code=422, detail="Amendment must explicitly retain or replace the purchasing unit for every previously standardized medication line.")
        if po.requisition_id is not None:
            if item.requisition_item_id is None or item.requisition_item_id in seen_requisition_lines:
                raise HTTPException(status_code=422, detail="Every amended line on a requisition-backed PO must reference a unique requisition line.")
            req_line = db.query(PurchaseRequisitionItem).filter(
                PurchaseRequisitionItem.id == item.requisition_item_id,
                PurchaseRequisitionItem.requisition_id == po.requisition_id,
            ).one_or_none()
            if req_line is None or req_line.approved_quantity is None or req_line.approved_quantity <= 0:
                raise HTTPException(status_code=422, detail="Amended quantity must map to a positively approved requisition line.")
            if item.purchase_uom_id != req_line.purchase_uom_id:
                raise HTTPException(status_code=422, detail="An amended requisition-backed PO must retain the purchasing unit approved on its requisition line.")
            # Existing allocations on other non-cancelled POs remain reserved.
            # The current PO is excluded because this amendment replaces its lines.
            ordered_elsewhere = db.query(func.coalesce(func.sum(PurchaseOrderItem.quantity_ordered), 0)).join(
                PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.po_id
            ).filter(
                PurchaseOrder.requisition_id == po.requisition_id,
                PurchaseOrderItem.requisition_item_id == req_line.id,
                PurchaseOrder.id != po.id,
                PurchaseOrder.status != POStatusEnum.CANCELLED,
            ).scalar()
            remaining_for_this_po = req_line.approved_quantity - int(ordered_elsewhere or 0)
            if remaining_for_this_po <= 0 or item.quantity_ordered > remaining_for_this_po:
                raise HTTPException(
                    status_code=409,
                    detail=f"Amended quantity exceeds the remaining approved allocation for requisition line {req_line.id}.",
                )
            if item.medication_id is not None and item.medication_id != req_line.medication_id:
                raise HTTPException(status_code=422, detail="An amended requisition line cannot change its approved medication.")
            seen_requisition_lines.add(item.requisition_item_id)
        elif item.requisition_item_id is not None:
            raise HTTPException(status_code=422, detail="A standalone purchase order cannot reference a requisition line.")
        effective_medication_id = (
            req_line.medication_id
            if po.requisition_id is not None
            else (item.medication_id if item.medication_id is not None else (prior_line.medication_id if prior_line else None))
        )
        effective_budget_department_id = (
            po.requisition.requesting_department_id
            if po.requisition_id is not None
            else (item.budget_department_id or (prior_line.budget_department_id if prior_line else None))
        )
        if effective_medication_id is not None and item.budget_category not in (None, "PHARMACY"):
            raise HTTPException(status_code=422, detail="Medication PO lines must use the PHARMACY budget category.")
        if effective_budget_department_id is None:
            raise HTTPException(status_code=422, detail="Amended PO lines must identify their requesting department.")
        if not current_user.is_superuser and not user_has_department_access(db, current_user, effective_budget_department_id):
            raise HTTPException(status_code=403, detail="You are not assigned to the amended PO line budget department.")
        unit_snapshot = _resolve_medication_unit_snapshot(
            db,
            medication_id=effective_medication_id,
            purchase_uom_id=item.purchase_uom_id,
            quantity=item.quantity_ordered,
            unit_price_paise=item.unit_price_paise,
            effective_at=datetime.now(timezone.utc),
        )
        line_subtotal = item.quantity_ordered * item.unit_price_paise
        line_tax = (line_subtotal * item.tax_percentage + 50) // 100
        line_gross = line_subtotal + line_tax
        proposed_total += line_gross
        unit_snapshot = {
            key: str(value) if isinstance(value, Decimal) else value
            for key, value in unit_snapshot.items()
        }
        proposed_items.append({
            "requisition_item_id": item.requisition_item_id,
            "medication_id": req_line.medication_id if po.requisition_id is not None else item.medication_id,
            "item_description": req_line.item_description if po.requisition_id is not None else item.item_description.strip(),
            "quantity_ordered": item.quantity_ordered,
            "unit_price_paise": item.unit_price_paise,
            "total_price_paise": line_subtotal,
            "tax_percentage": item.tax_percentage,
            "tax_amount_paise": line_tax,
            "gross_total_paise": line_gross,
            "budget_department_id": effective_budget_department_id,
            "budget_category": item.budget_category or (prior_line.budget_category if prior_line else None) or (
                "PHARMACY" if (req_line.medication_id if po.requisition_id is not None else item.medication_id) is not None
                else "GENERAL_SUPPLIES"
            ),
            **unit_snapshot,
        })
    prior_snapshot = {
        "delivery_due_date": po.delivery_due_date.isoformat(),
        "payment_terms": po.payment_terms,
        "subtotal_paise": po.subtotal_paise,
        "tax_amount_paise": po.tax_amount_paise,
        "total_amount_paise": po.total_amount_paise,
        "items": [{
            "id": item.id,
            "requisition_item_id": item.requisition_item_id,
            "medication_id": item.medication_id,
            "item_description": item.item_description,
            "quantity_ordered": item.quantity_ordered,
            "quantity_received": item.quantity_received,
            "unit_price_paise": item.unit_price_paise,
            "total_price_paise": item.total_price_paise,
            "purchase_uom_code": item.purchase_uom_code,
            "base_uom_code": item.base_uom_code,
            "units_per_purchase_unit": str(item.units_per_purchase_unit) if item.units_per_purchase_unit is not None else None,
            "base_quantity": str(item.base_quantity) if item.base_quantity is not None else None,
            "base_unit_price_paise": str(item.base_unit_price_paise) if item.base_unit_price_paise is not None else None,
            "tax_percentage": item.tax_percentage,
            "tax_amount_paise": item.tax_amount_paise,
            "gross_total_paise": item.gross_total_paise,
            "budget_department_id": item.budget_department_id,
            "budget_category": item.budget_category,
        } for item in po.items],
    }
    proposed_snapshot = {
        "delivery_due_date": payload.delivery_due_date.isoformat(),
        "payment_terms": payload.payment_terms,
        "subtotal_paise": sum(item["total_price_paise"] for item in proposed_items),
        "tax_amount_paise": sum(item["tax_amount_paise"] for item in proposed_items),
        "total_amount_paise": proposed_total,
        "items": proposed_items,
    }
    amendment = PurchaseOrderAmendment(
        po_id=po.id,
        version=po.amendment_version + 1,
        reason=payload.reason.strip(),
        prior_snapshot=prior_snapshot,
        proposed_snapshot=proposed_snapshot,
        status=POAmendmentStatusEnum.PENDING,
        created_by_id=current_user.id,
    )
    db.add(amendment)
    db.commit()
    db.refresh(amendment)
    return amendment


@router.get(
    "/purchase-orders/{po_id}/amendments",
    response_model=list[PurchaseOrderAmendmentResponse],
)
def list_purchase_order_amendments(
    po_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    if db.get(PurchaseOrder, po_id) is None:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    return db.query(PurchaseOrderAmendment).filter(
        PurchaseOrderAmendment.po_id == po_id
    ).order_by(PurchaseOrderAmendment.version.asc()).all()


@router.patch(
    "/purchase-orders/{po_id}/amendments/{amendment_id}/review",
    response_model=PurchaseOrderAmendmentResponse,
)
def review_purchase_order_amendment(
    po_id: int,
    amendment_id: int,
    payload: PurchaseOrderAmendmentReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:approve")),
):
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id
    ).with_for_update().one_or_none()
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    amendment = db.query(PurchaseOrderAmendment).filter(
        PurchaseOrderAmendment.id == amendment_id,
        PurchaseOrderAmendment.po_id == po_id,
    ).with_for_update().one_or_none()
    if amendment is None or amendment.status != POAmendmentStatusEnum.PENDING:
        raise HTTPException(status_code=409, detail="Pending amendment not found.")
    if amendment.created_by_id == current_user.id:
        raise HTTPException(status_code=409, detail="The amendment requester cannot review their own amendment.")
    if po.status != POStatusEnum.APPROVED or po.amendment_version + 1 != amendment.version:
        raise HTTPException(status_code=409, detail="The purchase order has changed since this amendment was requested.")
    if db.query(GoodsReceiptNote.id).filter(GoodsReceiptNote.po_id == po.id).first():
        raise HTTPException(status_code=409, detail="The purchase order has receipt activity and cannot be amended.")

    amendment.reviewed_by_id = current_user.id
    amendment.reviewed_at = datetime.now(timezone.utc)
    amendment.review_notes = payload.review_notes.strip()
    amendment.updated_by_id = current_user.id
    if payload.approved:
        snapshot = amendment.proposed_snapshot
        po.delivery_due_date = datetime.fromisoformat(snapshot["delivery_due_date"])
        po.payment_terms = snapshot["payment_terms"]
        po.subtotal_paise = snapshot.get("subtotal_paise", snapshot["total_amount_paise"])
        po.tax_amount_paise = snapshot.get("tax_amount_paise", 0)
        po.total_amount_paise = snapshot["total_amount_paise"]
        for old_item in list(po.items):
            if old_item.budget_id is not None:
                outstanding = _budget_item_open_reservation(db, old_item.id)
                if outstanding:
                    db.add(ProcurementBudgetMovement(
                        budget_id=old_item.budget_id,
                        po_id=po.id,
                        po_item_id=old_item.id,
                        movement_type="RELEASE",
                        amount_paise=outstanding,
                        reference_key=f"PO:{po.id}:ITEM:{old_item.id}:AMEND:{amendment.id}:RELEASE",
                        notes="Outstanding commitment released because the approved PO was amended and requires fresh approval.",
                        actor_user_id=current_user.id,
                        created_by_id=current_user.id,
                    ))
            db.delete(old_item)
        db.flush()
        for item in snapshot["items"]:
            db.add(PurchaseOrderItem(
                po_id=po.id,
                requisition_item_id=item.get("requisition_item_id"),
                medication_id=item["medication_id"],
                item_description=item["item_description"],
                quantity_ordered=item["quantity_ordered"],
                quantity_received=0,
                unit_price_paise=item["unit_price_paise"],
                total_price_paise=item["total_price_paise"],
                tax_percentage=item.get("tax_percentage", 0),
                tax_amount_paise=item.get("tax_amount_paise", 0),
                gross_total_paise=item.get("gross_total_paise", item["total_price_paise"]),
                purchase_uom_code=item.get("purchase_uom_code"),
                base_uom_code=item.get("base_uom_code"),
                units_per_purchase_unit=item.get("units_per_purchase_unit"),
                base_quantity=item.get("base_quantity"),
                base_unit_price_paise=item.get("base_unit_price_paise"),
                budget_department_id=item.get("budget_department_id"),
                budget_category=item.get("budget_category", "GENERAL_SUPPLIES"),
                created_by_id=current_user.id,
            ))
        po.amendment_version = amendment.version
        po.status = POStatusEnum.SUBMITTED
        po.approved_by_id = None
        po.approved_at = None
        po.updated_by_id = current_user.id
        amendment.status = POAmendmentStatusEnum.APPROVED
    else:
        amendment.status = POAmendmentStatusEnum.REJECTED
    db.commit()
    db.refresh(amendment)
    return amendment



# --- Supplier delivery tracking and overdue PO queue ---
_SHIPMENT_TRANSITIONS = {
    POShipmentStatusEnum.PLANNED: {POShipmentStatusEnum.DISPATCHED, POShipmentStatusEnum.CANCELLED},
    POShipmentStatusEnum.DISPATCHED: {
        POShipmentStatusEnum.IN_TRANSIT, POShipmentStatusEnum.DELAYED,
        POShipmentStatusEnum.DELIVERY_CONFIRMED,
    },
    POShipmentStatusEnum.IN_TRANSIT: {
        POShipmentStatusEnum.DELAYED, POShipmentStatusEnum.DELIVERY_CONFIRMED,
    },
    POShipmentStatusEnum.DELAYED: {
        POShipmentStatusEnum.IN_TRANSIT, POShipmentStatusEnum.DELIVERY_CONFIRMED,
        POShipmentStatusEnum.CANCELLED,
    },
    POShipmentStatusEnum.DELIVERY_CONFIRMED: set(),
    POShipmentStatusEnum.CANCELLED: set(),
}


@router.post(
    "/purchase-orders/{po_id}/shipments",
    response_model=PurchaseOrderShipmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_purchase_order_shipment(
    po_id: int,
    payload: PurchaseOrderShipmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:write")),
):
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id
    ).with_for_update().one_or_none()
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    if po.status not in {POStatusEnum.APPROVED, POStatusEnum.PARTIALLY_RECEIVED}:
        raise HTTPException(status_code=409, detail="Shipment tracking can only be created for approved or partially received purchase orders.")
    shipment = PurchaseOrderShipment(
        po_id=po.id,
        carrier=payload.carrier.strip(),
        tracking_number=payload.tracking_number.strip() if payload.tracking_number else None,
        expected_delivery_at=payload.expected_delivery_at,
        notes=payload.notes,
        status=POShipmentStatusEnum.PLANNED,
        created_by_id=current_user.id,
    )
    db.add(shipment)
    db.flush()
    db.add(PurchaseOrderShipmentEvent(
        shipment_id=shipment.id,
        status=POShipmentStatusEnum.PLANNED,
        event_at=datetime.now(timezone.utc),
        notes="Shipment tracking record created.",
        actor_user_id=current_user.id,
    ))
    db.commit()
    return db.query(PurchaseOrderShipment).options(
        selectinload(PurchaseOrderShipment.events)
    ).filter(PurchaseOrderShipment.id == shipment.id).one()


@router.get(
    "/purchase-orders/{po_id}/shipments",
    response_model=list[PurchaseOrderShipmentResponse],
)
def list_purchase_order_shipments(
    po_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    if db.get(PurchaseOrder, po_id) is None:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    return db.query(PurchaseOrderShipment).options(
        selectinload(PurchaseOrderShipment.events)
    ).filter(PurchaseOrderShipment.po_id == po_id).order_by(
        PurchaseOrderShipment.id.asc()
    ).all()


@router.patch(
    "/purchase-orders/{po_id}/shipments/{shipment_id}",
    response_model=PurchaseOrderShipmentResponse,
)
def update_purchase_order_shipment(
    po_id: int,
    shipment_id: int,
    payload: PurchaseOrderShipmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:write")),
):
    shipment = db.query(PurchaseOrderShipment).filter(
        PurchaseOrderShipment.id == shipment_id,
        PurchaseOrderShipment.po_id == po_id,
    ).with_for_update().one_or_none()
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found.")
    if payload.status not in _SHIPMENT_TRANSITIONS[shipment.status]:
        raise HTTPException(
            status_code=409,
            detail=f"Invalid shipment transition from {shipment.status.value} to {payload.status.value}.",
        )
    event_at = payload.event_at or datetime.now(timezone.utc)
    if event_at > datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="Shipment event time cannot be in the future.")
    previous_event_at = db.query(func.max(PurchaseOrderShipmentEvent.event_at)).filter(
        PurchaseOrderShipmentEvent.shipment_id == shipment.id
    ).scalar()
    if previous_event_at is not None and event_at < previous_event_at:
        raise HTTPException(status_code=422, detail="Shipment event time cannot precede the previous recorded shipment event.")
    shipment.status = payload.status
    shipment.updated_by_id = current_user.id
    if payload.status == POShipmentStatusEnum.DISPATCHED:
        shipment.dispatched_at = event_at
    if payload.status == POShipmentStatusEnum.DELIVERY_CONFIRMED:
        shipment.delivery_confirmed_at = event_at
    db.add(PurchaseOrderShipmentEvent(
        shipment_id=shipment.id,
        status=payload.status,
        event_at=event_at,
        location=payload.location,
        notes=payload.notes,
        actor_user_id=current_user.id,
    ))
    db.commit()
    return db.query(PurchaseOrderShipment).options(
        selectinload(PurchaseOrderShipment.events)
    ).filter(PurchaseOrderShipment.id == shipment.id).one()


@router.get(
    "/purchase-order-approval-authorities",
    response_model=list[PurchaseOrderApprovalAuthorityResponse],
)
def list_po_approval_authorities(
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    return db.query(PurchaseOrderApprovalAuthority).order_by(
        PurchaseOrderApprovalAuthority.role_id.asc()
    ).all()


@router.put(
    "/purchase-order-approval-authorities/{role_id}",
    response_model=PurchaseOrderApprovalAuthorityResponse,
)
def set_po_approval_authority(
    role_id: int,
    payload: PurchaseOrderApprovalAuthorityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:approve")),
):
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found.")
    authority = db.query(PurchaseOrderApprovalAuthority).filter(
        PurchaseOrderApprovalAuthority.role_id == role_id
    ).with_for_update().one_or_none()
    if authority is None:
        authority = PurchaseOrderApprovalAuthority(
            role_id=role_id,
            max_amount_paise=payload.max_amount_paise,
            is_active=payload.is_active,
            created_by_id=current_user.id,
        )
        db.add(authority)
    else:
        authority.max_amount_paise = payload.max_amount_paise
        authority.is_active = payload.is_active
        authority.updated_by_id = current_user.id
    db.commit()
    db.refresh(authority)
    return authority


@router.patch("/purchase-orders/{po_id}/approve", response_model=POResponse)
def approve_purchase_order(
    po_id: int,
    payload: Optional[PurchaseOrderApprovalRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:approve")),
):
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id
    ).with_for_update().one_or_none()
    if not po or po.status not in [POStatusEnum.DRAFT, POStatusEnum.SUBMITTED]:
        raise HTTPException(status_code=400, detail="Only DRAFT or SUBMITTED purchase orders can be approved.")
    if po.created_by_id == current_user.id:
        raise HTTPException(status_code=409, detail="The purchase order creator cannot approve the same purchase order.")
    vendor = db.get(VendorMaster, po.vendor_id)
    if vendor is None:
        raise HTTPException(status_code=409, detail="The purchase-order supplier is no longer active.")
    _assert_supplier_procurement_eligible(vendor)
    _assert_supplier_compliance_ready(db, vendor)

    if po.contract_id is not None:
        contract = db.query(SupplierContract).options(
            selectinload(SupplierContract.rates)
        ).filter(SupplierContract.id == po.contract_id).with_for_update().one_or_none()
        if contract is None or contract.vendor_id != po.vendor_id:
            raise HTTPException(status_code=409, detail="The linked supplier contract does not belong to this PO vendor.")
        today = datetime.now(timezone.utc).date()
        if contract.status != "ACTIVE" or contract.valid_from > today or contract.valid_to < today:
            raise HTTPException(status_code=409, detail="The linked supplier contract is not active for today's date.")
        for line in po.items:
            uom_code = line.base_uom_code or line.purchase_uom_code
            if not uom_code:
                raise HTTPException(status_code=409, detail=f"PO line {line.id} has no normalized UOM and cannot be checked against the contract.")
            medication_rates = [
                rate for rate in contract.rates
                if line.medication_id is not None
                and rate.scope_type == "MEDICATION"
                and rate.medication_id == line.medication_id
                and rate.uom_code == uom_code
            ]
            matching = medication_rates or [
                rate for rate in contract.rates
                if rate.scope_type == "CATEGORY"
                and rate.category == line.budget_category
                and rate.uom_code == uom_code
            ]
            if len(matching) != 1:
                raise HTTPException(status_code=409, detail=f"PO line {line.id} must match exactly one negotiated contract rate.")
            rate = matching[0]
            normalized_price = line.base_unit_price_paise if line.base_unit_price_paise is not None else Decimal(line.unit_price_paise)
            if Decimal(str(normalized_price)) != Decimal(rate.unit_price_paise) or line.tax_percentage != rate.tax_percentage:
                raise HTTPException(status_code=409, detail=f"PO line {line.id} price or tax differs from the linked supplier contract rate.")

    if not current_user.is_superuser:
        role_ids = [role.id for role in current_user.roles]
        authorities = db.query(PurchaseOrderApprovalAuthority).filter(
            PurchaseOrderApprovalAuthority.role_id.in_(role_ids or [-1]),
            PurchaseOrderApprovalAuthority.is_active.is_(True),
        ).all()
        allowed_limit = max((authority.max_amount_paise for authority in authorities), default=None)
        if allowed_limit is None or po.total_amount_paise > allowed_limit:
            raise HTTPException(
                status_code=403,
                detail="Your configured purchase-order approval authority is missing or insufficient for this amount.",
            )

    variance_flags = []
    for line in po.items:
        if line.medication_id is None or line.base_unit_price_paise is None or not line.base_uom_code:
            continue
        policy = db.query(MedicationPriceControl).filter(
            MedicationPriceControl.medication_id == line.medication_id,
            MedicationPriceControl.is_active.is_(True),
        ).one_or_none()
        if policy is None:
            continue
        benchmark = _normalized_price_benchmark(
            db, line.medication_id, line.base_uom_code,
            lookback_days=policy.lookback_days,
            before=po.created_at,
            exclude_po_id=po.id,
        )
        if benchmark["observations"] < policy.minimum_observations or benchmark["median"] is None or benchmark["median"] <= 0:
            continue
        variance_pct = (
            (Decimal(str(line.base_unit_price_paise)) - benchmark["median"])
            / benchmark["median"] * Decimal("100")
        )
        if variance_pct > Decimal(policy.max_variance_pct):
            variance_flags.append({
                "line": line,
                "policy": policy,
                "benchmark": benchmark,
                "variance_pct": variance_pct,
            })
    override_reason = payload.override_reason.strip() if payload and payload.override_reason else None
    if variance_flags and not override_reason:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "One or more PO lines exceed configured normalized price-variance thresholds. Supply an override_reason of at least 10 characters to approve with an immutable review record.",
                "price_variances": [{
                    "po_item_id": flag["line"].id,
                    "medication_id": flag["line"].medication_id,
                    "base_uom_code": flag["line"].base_uom_code,
                    "proposed_base_unit_price_paise": float(flag["line"].base_unit_price_paise),
                    "benchmark_median_paise": float(flag["benchmark"]["median"]),
                    "benchmark_observations": flag["benchmark"]["observations"],
                    "threshold_pct": flag["policy"].max_variance_pct,
                    "variance_pct": float(flag["variance_pct"]),
                } for flag in variance_flags],
            },
        )
    if variance_flags:
        for flag in variance_flags:
            db.add(PurchaseOrderPriceReview(
                po_id=po.id,
                po_item_id=flag["line"].id,
                medication_id=flag["line"].medication_id,
                base_uom_code=flag["line"].base_uom_code,
                proposed_base_unit_price_paise=flag["line"].base_unit_price_paise,
                benchmark_median_paise=flag["benchmark"]["median"],
                benchmark_min_paise=flag["benchmark"]["minimum"],
                benchmark_max_paise=flag["benchmark"]["maximum"],
                benchmark_observations=flag["benchmark"]["observations"],
                threshold_pct=flag["policy"].max_variance_pct,
                variance_pct=flag["variance_pct"],
                override_reason=override_reason,
                reviewed_by_id=current_user.id,
                reviewed_at=datetime.now(timezone.utc),
                created_by_id=current_user.id,
            ))
    _reserve_purchase_order_budget(db, po, current_user)
    po.status = POStatusEnum.APPROVED
    po.approved_by_id = current_user.id
    po.approved_at = datetime.now(timezone.utc)
    po.updated_by_id = current_user.id
    db.commit()
    db.refresh(po)
    return po


@router.get("/purchase-orders/{po_id}/price-reviews", response_model=list[PurchaseOrderPriceReviewResponse])
def list_purchase_order_price_reviews(
    po_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    if db.get(PurchaseOrder, po_id) is None:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    return db.query(PurchaseOrderPriceReview).filter(
        PurchaseOrderPriceReview.po_id == po_id
    ).order_by(PurchaseOrderPriceReview.id.asc()).all()


@router.get("/purchase-orders/{po_id}/print")
def print_purchase_order(
    po_id: int,
    request: Request,
    template_code: Optional[str] = Query(default=None),
    print_mode: Optional[PrintModeEnum] = Query(default=None),
    output_format: Optional[str] = Query(default="pdf", alias="format"),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read"))
):
    po = db.query(PurchaseOrder).options(
        joinedload(PurchaseOrder.vendor),
        joinedload(PurchaseOrder.items)
    ).filter(PurchaseOrder.id == po_id).first()

    if not po or po.status not in [POStatusEnum.APPROVED, POStatusEnum.PARTIALLY_RECEIVED, POStatusEnum.COMPLETED]:
        raise HTTPException(status_code=400, detail="Only approved purchase orders can be printed.")

    # 1. Resolve Tenant & Profile Formatting Context
    tenant = resolve_tenant_context(request)
    profile = _invoice_document_profile(db)
    format_amount = lambda value: _format_invoice_amount(value, profile)

    # 2. Build the Safe Jinja2 Context
    context = {
        "tenant": {
            "hospital_name": tenant.hospital_name,
            "branch_code": tenant.branch_code,
            "printed_at": datetime.now(timezone.utc).isoformat(),
            "document_profile": profile,
        },
        "vendor": {
            "name": po.vendor.name,
            "code": po.vendor.code,
            "address": po.vendor.address,
            "gstin": po.vendor.gstin or "N/A",
            "contact_person": po.vendor.contact_person,
            "phone": po.vendor.phone,
        },
        "po": {
            "po_number": po.po_number,
            "status": po.status.value,
            "delivery_due_date": po.delivery_due_date.strftime("%Y-%m-%d"),
            "payment_terms": po.payment_terms,
            "subtotal": format_amount(po.subtotal_paise),
            "tax_amount": format_amount(po.tax_amount_paise),
            "total_amount": format_amount(po.total_amount_paise),
        },
        "items": [
            {
                "description": item.item_description,
                "quantity_ordered": item.quantity_ordered,
                "purchase_uom_code": item.purchase_uom_code,
                "base_uom_code": item.base_uom_code,
                "units_per_purchase_unit": str(item.units_per_purchase_unit) if item.units_per_purchase_unit is not None else None,
                "base_quantity": str(item.base_quantity) if item.base_quantity is not None else None,
                "base_unit_price": str(item.base_unit_price_paise) if item.base_unit_price_paise is not None else None,
                "unit_known": item.purchase_uom_code is not None,
                "unit_price": format_amount(item.unit_price_paise),
                "tax_percentage": item.tax_percentage,
                "net_total_price": format_amount(item.total_price_paise),
                "tax_amount": format_amount(item.tax_amount_paise),
                "total_price": format_amount(item.gross_total_paise),
                "gross_total": format_amount(item.gross_total_paise),
            }
            for item in po.items
        ]
    }

    # 3. Resolve the hospital's specific template (or fallback to SYSTEM DEFAULT)
    tpl_parts = _resolve_template_for_print(
        db, ReportTypeEnum.PURCHASE_ORDER, template_code, print_mode
    )

    # 4. Render through the Security Sandbox
    html = _render_template_parts(tpl_parts, context)
    if output_format and output_format.lower() == "html":
        return HTMLResponse(content=html, status_code=200)

    # 5. Convert to PDF
    try:
        pdf_bytes = render_html_pdf(html)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return pdf_attachment_response(pdf_bytes, f"{po.po_number}.pdf")

# --- Internal Store Indents ---
@router.post("/indents/patient", response_model=StoreIndentResponse, status_code=status.HTTP_201_CREATED)
def raise_patient_indent(payload: StoreIndentCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("wards:write"))):
    if not payload.encounter_id:
        raise HTTPException(status_code=400, detail="Patient encounter ID is required for patient-specific indents.")

    indent = StoreIndent(
        indent_number=_generate_reference("IND"),
        requesting_department_id=payload.requesting_department_id,
        encounter_id=payload.encounter_id,
        status=IndentStatusEnum.PENDING,
        remarks=payload.remarks,
        requested_by_id=current_user.id
    )
    db.add(indent)
    db.flush()

    for item in payload.items:
        db.add(StoreIndentItem(
            indent_id=indent.id,
            medication_id=item.medication_id,
            requested_quantity=item.requested_quantity
        ))

    db.commit()
    db.refresh(indent)
    return indent

@router.post("/indents/patient/{indent_id}/issue")
def issue_indent_stock(indent_id: int, payload: IndentIssueRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("pharmacy:write"))):
    indent = db.query(StoreIndent).options(joinedload(StoreIndent.encounter), joinedload(StoreIndent.items)).filter(StoreIndent.id == indent_id).first()
    if not indent or indent.status in [IndentStatusEnum.FULFILLED, IndentStatusEnum.CANCELLED]:
        raise HTTPException(status_code=400, detail="Invalid indent or already fully fulfilled.")

    issue_patient_indent(db, indent, payload.items, current_user.id)
    db.commit()
    return {"status": "success", "message": "Indent fulfilled and billed to patient encounter."}

@router.post("/indents/patient/{indent_id}/return")
def return_indent_stock(
    indent_id: int,
    payload: IndentReturnRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("wards:write"))
):
    indent = db.query(StoreIndent).options(
        joinedload(StoreIndent.encounter),
        joinedload(StoreIndent.items)
    ).filter(StoreIndent.id == indent_id).first()

    if not indent or indent.status not in [IndentStatusEnum.FULFILLED, IndentStatusEnum.PARTIALLY_FULFILLED]:
        raise HTTPException(status_code=400, detail="Can only return stock from fulfilled or partially fulfilled indents.")

    return_patient_indent_stock(db, indent, payload.items, current_user.id)
    db.commit()
    return {"status": "success", "message": "Stock successfully returned to pharmacy and patient invoice credited."}

# --- Vendor Purchase Returns ---
@router.post("/returns", status_code=status.HTTP_201_CREATED)
def create_purchase_return(payload: PurchaseReturnCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("procurement:write"))):
    process_purchase_return(db, payload.vendor_id, payload.grn_id, payload.items, current_user.id)
    db.commit()
    return {"status": "success", "message": "Purchase return processed and Debit Note generated."}


@router.get("/medications/{medication_id}/price-control", response_model=Optional[MedicationPriceControlResponse])
def get_medication_price_control(
    medication_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    if db.get(MedicationMaster, medication_id) is None:
        raise HTTPException(status_code=404, detail="Medication not found.")
    return db.query(MedicationPriceControl).filter(
        MedicationPriceControl.medication_id == medication_id
    ).one_or_none()


@router.put("/medications/{medication_id}/price-control", response_model=MedicationPriceControlResponse)
def set_medication_price_control(
    medication_id: int,
    payload: MedicationPriceControlUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:approve")),
):
    if db.get(MedicationMaster, medication_id) is None:
        raise HTTPException(status_code=404, detail="Medication not found.")
    policy = db.query(MedicationPriceControl).filter(
        MedicationPriceControl.medication_id == medication_id
    ).with_for_update().one_or_none()
    if policy is None:
        policy = MedicationPriceControl(
            medication_id=medication_id,
            **payload.model_dump(),
            created_by_id=current_user.id,
        )
        db.add(policy)
    else:
        for key, value in payload.model_dump().items():
            setattr(policy, key, value)
        policy.updated_by_id = current_user.id
    db.commit()
    db.refresh(policy)
    return policy


@router.get("/analytics/quotation-outcomes")
def get_procurement_quotation_outcomes(
    from_date: Optional[date] = Query(default=None, description="Inclusive PO creation date filter (UTC)."),
    to_date: Optional[date] = Query(default=None, description="Inclusive PO creation date filter (UTC)."),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    """Compare selected quotation pricing with comparable non-selected offers."""
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must be on or before to_date.")
    start_at = datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc) if from_date else None
    end_at = datetime.combine(to_date, datetime.max.time(), tzinfo=timezone.utc) if to_date else None

    po_query = db.query(PurchaseOrder).options(selectinload(PurchaseOrder.items)).filter(
        PurchaseOrder.requisition_id.is_not(None),
        PurchaseOrder.status.in_([
            POStatusEnum.APPROVED, POStatusEnum.PARTIALLY_RECEIVED, POStatusEnum.COMPLETED,
        ]),
    )
    if start_at:
        po_query = po_query.filter(PurchaseOrder.created_at >= start_at)
    if end_at:
        po_query = po_query.filter(PurchaseOrder.created_at <= end_at)
    purchase_orders = po_query.order_by(PurchaseOrder.created_at.asc(), PurchaseOrder.id.asc()).all()

    requisition_ids = {po.requisition_id for po in purchase_orders}
    quotes_by_requisition = {}
    if requisition_ids:
        quotes = db.query(SupplierQuotation).options(
            joinedload(SupplierQuotation.vendor), selectinload(SupplierQuotation.items)
        ).filter(
            SupplierQuotation.requisition_id.in_(requisition_ids),
            SupplierQuotation.status.in_([
                SupplierQuotationStatusEnum.SELECTED,
                SupplierQuotationStatusEnum.NOT_SELECTED,
            ]),
        ).all()
        for quote in quotes:
            quotes_by_requisition.setdefault(quote.requisition_id, []).append(quote)

    rows = []
    total_selected_gross = 0
    total_best_alternative_gross = 0
    comparable_line_count = 0
    missing_comparison_count = 0
    for po in purchase_orders:
        quotes = quotes_by_requisition.get(po.requisition_id, [])
        selected_quotes = [q for q in quotes if q.status == SupplierQuotationStatusEnum.SELECTED]
        if len(selected_quotes) != 1:
            continue
        selected = selected_quotes[0]
        selected_lines = {line.requisition_item_id: line for line in selected.items}
        alternatives = [q for q in quotes if q.id != selected.id and q.status == SupplierQuotationStatusEnum.NOT_SELECTED]
        for po_line in po.items:
            selected_line = selected_lines.get(po_line.requisition_item_id)
            if selected_line is None or po_line.requisition_item_id is None:
                continue
            selected_tax = int(selected_line.tax_percentage or 0)
            selected_uom = (selected_line.purchase_uom_code, selected_line.base_uom_code)
            if (
                selected_line.unit_price_paise != po_line.unit_price_paise
                or selected_tax != int(po_line.tax_percentage or 0)
                or selected_uom != (po_line.purchase_uom_code, po_line.base_uom_code)
            ):
                continue
            selected_net = int(po_line.quantity_ordered) * int(selected_line.unit_price_paise)
            selected_tax_amount = (selected_net * selected_tax + 50) // 100
            selected_gross = selected_net + selected_tax_amount
            total_selected_gross += selected_gross

            comparable = []
            for alternative in alternatives:
                for alt_line in alternative.items:
                    if (
                        alt_line.requisition_item_id == po_line.requisition_item_id
                        and (alt_line.purchase_uom_code, alt_line.base_uom_code) == selected_uom
                        and int(alt_line.tax_percentage or 0) == selected_tax
                        and alt_line.unit_price_paise is not None
                    ):
                        alt_net = int(po_line.quantity_ordered) * int(alt_line.unit_price_paise)
                        alt_tax = (alt_net * selected_tax + 50) // 100
                        comparable.append({
                            "vendor_id": alternative.vendor_id,
                            "vendor_name": alternative.vendor.name if alternative.vendor else "Unknown vendor",
                            "quotation_number": alternative.quotation_number,
                            "net_paise": alt_net,
                            "tax_paise": alt_tax,
                            "gross_paise": alt_net + alt_tax,
                            "unit_price_paise": int(alt_line.unit_price_paise),
                        })
            comparable.sort(key=lambda item: (item["gross_paise"], item["vendor_id"]))
            best_alternative = comparable[0] if comparable else None
            if best_alternative:
                comparable_line_count += 1
                total_best_alternative_gross += best_alternative["gross_paise"]
                delta = best_alternative["gross_paise"] - selected_gross
            else:
                missing_comparison_count += 1
                delta = None
            rows.append({
                "purchase_order_id": po.id,
                "purchase_order_number": po.po_number,
                "requisition_id": po.requisition_id,
                "requisition_item_id": po_line.requisition_item_id,
                "medication_id": po_line.medication_id,
                "item_description": po_line.item_description,
                "quantity_ordered": po_line.quantity_ordered,
                "purchase_uom_code": po_line.purchase_uom_code,
                "base_uom_code": po_line.base_uom_code,
                "selected_vendor_id": selected.vendor_id,
                "selected_vendor_name": selected.vendor.name if selected.vendor else "Unknown vendor",
                "selected_quotation_number": selected.quotation_number,
                "selected_unit_price_paise": int(selected_line.unit_price_paise),
                "selected_net_paise": selected_net,
                "selected_tax_paise": selected_tax_amount,
                "selected_gross_paise": selected_gross,
                "best_comparable_alternative": best_alternative,
                "competitive_saving_paise": delta if delta is not None and delta > 0 else 0,
                "selected_offer_premium_paise": abs(delta) if delta is not None and delta < 0 else 0,
                "comparison_status": "COMPARABLE" if best_alternative else "NO_COMPARABLE_ALTERNATIVE",
                "classification": "COMPETITIVE_SAVING_VS_BEST_COMPARABLE_OFFER" if delta is not None and delta > 0 else (
                    "SELECTED_OFFER_PREMIUM_VS_BEST_COMPARABLE_OFFER" if delta is not None and delta < 0 else (
                        "PRICE_PARITY" if delta == 0 else "NOT_COMPARABLE"
                    )
                ),
            })

    supplier_outcomes = {}
    for row in rows:
        supplier = supplier_outcomes.setdefault(row["selected_vendor_id"], {
            "vendor_id": row["selected_vendor_id"],
            "vendor_name": row["selected_vendor_name"],
            "purchase_order_line_count": 0,
            "selected_offer_value_paise": 0,
            "competitive_savings_paise": 0,
            "selected_offer_premium_paise": 0,
            "comparable_line_count": 0,
        })
        supplier["purchase_order_line_count"] += 1
        supplier["selected_offer_value_paise"] += row["selected_gross_paise"]
        supplier["competitive_savings_paise"] += row["competitive_saving_paise"]
        supplier["selected_offer_premium_paise"] += row["selected_offer_premium_paise"]
        if row["comparison_status"] == "COMPARABLE":
            supplier["comparable_line_count"] += 1
    supplier_outcome_rows = sorted(
        supplier_outcomes.values(),
        key=lambda row: row["competitive_savings_paise"],
        reverse=True,
    )

    return {
        "period": {
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
            "basis": "Purchase order creation date (UTC).",
        },
        "summary": {
            "purchase_order_line_count": len(rows),
            "comparable_line_count": comparable_line_count,
            "no_comparable_alternative_count": missing_comparison_count,
            "selected_offer_value_paise": total_selected_gross,
            "best_alternative_value_for_ordered_quantities_paise": total_best_alternative_gross,
            "competitive_savings_paise": sum(row["competitive_saving_paise"] for row in rows),
            "selected_offer_premium_paise": sum(row["selected_offer_premium_paise"] for row in rows),
            "competitive_savings_definition": "Difference between the best comparable non-selected quotation and the selected quotation, applied to the PO ordered quantity. This is an estimated competitive price advantage, not realized cash savings.",
        },
        "supplier_outcomes": supplier_outcome_rows,
        "items": rows,
        "limitations": [
            "Only selected and explicitly not-selected quotations are compared; withdrawn or unselected incomplete offers are excluded.",
            "Comparison requires the same requisition line, purchase UOM, base UOM and tax percentage.",
            "The selected quotation price must still match the approved PO line; the system does not claim a post-selection negotiated discount.",
            "This is an alternative-offer benchmark, not actual savings against a paid supplier invoice.",
            "Multiple POs for one requisition line are evaluated independently at each PO quantity and can repeat the same quotation comparison.",
        ],
    }


@router.get("/analytics/price-benchmarks")
def get_procurement_price_benchmarks(
    lookback_days: int = Query(default=180, ge=1, le=1825),
    minimum_observations: int = Query(default=2, ge=2, le=100),
    medication_id: Optional[int] = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    query = db.query(
        PurchaseOrderItem, PurchaseOrder, VendorMaster, MedicationMaster
    ).join(
        PurchaseOrder, PurchaseOrderItem.po_id == PurchaseOrder.id
    ).join(
        VendorMaster, PurchaseOrder.vendor_id == VendorMaster.id
    ).join(
        MedicationMaster, PurchaseOrderItem.medication_id == MedicationMaster.id
    ).filter(
        PurchaseOrder.status.in_([
            POStatusEnum.APPROVED, POStatusEnum.PARTIALLY_RECEIVED, POStatusEnum.COMPLETED
        ]),
        PurchaseOrder.created_at >= cutoff,
        PurchaseOrderItem.base_unit_price_paise.is_not(None),
        PurchaseOrderItem.base_uom_code.is_not(None),
    )
    if medication_id is not None:
        if db.get(MedicationMaster, medication_id) is None:
            raise HTTPException(status_code=404, detail="Medication not found.")
        query = query.filter(PurchaseOrderItem.medication_id == medication_id)
    groups = {}
    for line, po, vendor, medication in query.order_by(PurchaseOrder.created_at.asc()).all():
        key = (medication.id, line.base_uom_code)
        group = groups.setdefault(key, {
            "medication_id": medication.id,
            "medication_code": medication.code,
            "brand_name": medication.brand_name,
            "generic_name": medication.generic_name,
            "base_uom_code": line.base_uom_code,
            "prices": [],
            "suppliers": {},
            "latest_purchase_at": po.created_at,
        })
        price = Decimal(str(line.base_unit_price_paise))
        group["prices"].append(price)
        group["latest_purchase_at"] = max(group["latest_purchase_at"], po.created_at)
        supplier = group["suppliers"].setdefault(vendor.id, {
            "vendor_id": vendor.id, "vendor_name": vendor.name, "observations": 0, "prices": []
        })
        supplier["observations"] += 1
        supplier["prices"].append(price)
    results = []
    for group in groups.values():
        prices = sorted(group["prices"])
        if len(prices) < minimum_observations:
            continue
        mid = len(prices) // 2
        median_price = prices[mid] if len(prices) % 2 else (prices[mid - 1] + prices[mid]) / Decimal("2")
        suppliers = []
        for supplier in group["suppliers"].values():
            vals = sorted(supplier.pop("prices"))
            smid = len(vals) // 2
            supplier["median_base_unit_price_paise"] = float(vals[smid] if len(vals) % 2 else (vals[smid - 1] + vals[smid]) / Decimal("2"))
            suppliers.append(supplier)
        results.append({
            "medication_id": group["medication_id"],
            "medication_code": group["medication_code"],
            "brand_name": group["brand_name"],
            "generic_name": group["generic_name"],
            "base_uom_code": group["base_uom_code"],
            "observation_count": len(prices),
            "median_base_unit_price_paise": float(median_price),
            "average_base_unit_price_paise": float(sum(prices) / len(prices)),
            "minimum_base_unit_price_paise": float(prices[0]),
            "maximum_base_unit_price_paise": float(prices[-1]),
            "latest_purchase_at": group["latest_purchase_at"].isoformat(),
            "suppliers": sorted(suppliers, key=lambda row: row["median_base_unit_price_paise"]),
            "comparison_basis": "Pre-tax normalized PO line prices; same medication and base UOM; approved, partially received or completed POs only. These are approved purchase commitments, not verified final paid invoice prices.",
        })
    return {
        "lookback_days": lookback_days,
        "minimum_observations": minimum_observations,
        "price_source": "Approved purchase-order line prices, not final paid invoice settlement prices.",
        "normalization": "Only verified normalized base-unit prices are compared; unknown legacy units are excluded.",
        "items": results,
    }


@router.get("/analytics/cash-flow-forecast")
def get_procurement_cash_flow_forecast(
    horizon_days: int = Query(default=90, ge=7, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    """Cash forecast separates invoice cash needs, approved schedules, PO commitments and prepaid advances."""
    today = datetime.now(timezone.utc).date()
    horizon_end = today + timedelta(days=horizon_days)
    bucket_edges = (7, 30, 60, 90, 180, 365)
    edges = [edge for edge in bucket_edges if edge < horizon_days] + [horizon_days]
    buckets = []
    lower = 0
    for upper in edges:
        buckets.append({
            "window": f"day_{lower + 1}_to_{upper}",
            "from_date": (today + timedelta(days=lower + 1)).isoformat(),
            "to_date": (today + timedelta(days=upper)).isoformat(),
            "scheduled_approved_paise": 0,
            "unplanned_ap_due_paise": 0,
            "projected_ap_cash_need_paise": 0,
            "invoice_count": 0,
            "payment_request_count": 0,
        })
        lower = upper

    def bucket_for(target_date: date):
        if target_date <= today:
            return buckets[0]
        for row in buckets:
            if date.fromisoformat(row["from_date"]) <= target_date <= date.fromisoformat(row["to_date"]):
                return row
        return None

    approved_requests = db.query(SupplierPaymentRequest).options(
        selectinload(SupplierPaymentRequest.allocations)
    ).filter(SupplierPaymentRequest.status == "APPROVED").all()
    pending_requests = db.query(SupplierPaymentRequest).filter(
        SupplierPaymentRequest.status == "PENDING"
    ).all()
    approved_reservations_by_invoice = {}
    for request_row in approved_requests:
        if request_row.scheduled_date <= horizon_end:
            for allocation in request_row.allocations:
                approved_reservations_by_invoice[allocation.invoice_id] = (
                    approved_reservations_by_invoice.get(allocation.invoice_id, 0)
                    + int(allocation.amount_paise)
                )

    invoices = db.query(VendorInvoice).filter(
        VendorInvoice.status.in_([
            VendorInvoiceStatusEnum.MATCHED_APPROVED,
            VendorInvoiceStatusEnum.PAID,
        ])
    ).all()
    ap_rows = []
    invoice_ids = {row.id for row in invoices}
    paid_by_invoice = _supplier_paid_amounts_by_invoice(db, invoice_ids)
    for invoice in invoices:
        if invoice.linked_expense_id is None:
            continue
        expense = db.get(ExpenseRecord, invoice.linked_expense_id)
        if expense is None or expense.status not in {ExpenseStatusEnum.APPROVED, ExpenseStatusEnum.PAID}:
            continue
        outstanding, credit_amount, advance_amount = _supplier_invoice_outstanding(db, invoice)
        outstanding = max(int(outstanding), 0)
        if outstanding <= 0:
            continue
        due = invoice.due_date.date() if isinstance(invoice.due_date, datetime) else invoice.due_date
        reserved = min(approved_reservations_by_invoice.get(invoice.id, 0), outstanding)
        ap_rows.append({
            "invoice_id": invoice.id,
            "vendor_id": invoice.vendor_id,
            "invoice_number": invoice.invoice_number,
            "due_date": due,
            "outstanding_paise": outstanding,
            "reserved_paise": reserved,
            "unplanned_paise": max(outstanding - reserved, 0),
            "credit_adjustments_paise": int(credit_amount),
            "advances_applied_paise": int(advance_amount),
            "cash_paid_paise": int(_effective_invoice_paid_amount(invoice, paid_by_invoice)),
        })

    approved_schedule_total = 0
    approved_schedule_in_horizon = 0
    approved_schedule_rows = []
    for request_row in approved_requests:
        amount = int(request_row.amount_paise)
        approved_schedule_total += amount
        if request_row.scheduled_date <= horizon_end:
            approved_schedule_in_horizon += amount
            target = bucket_for(request_row.scheduled_date)
            if target is not None:
                target["scheduled_approved_paise"] += amount
                target["payment_request_count"] += 1
            approved_schedule_rows.append({
                "request_id": request_row.id,
                "vendor_id": request_row.vendor_id,
                "scheduled_date": request_row.scheduled_date.isoformat(),
                "payment_run_reference": request_row.payment_run_reference,
                "amount_paise": amount,
            })

    ap_due_total = 0
    unplanned_due_in_horizon = 0
    overdue_ap = 0
    for row in ap_rows:
        due = row["due_date"]
        ap_due_total += row["outstanding_paise"]
        if due < today:
            overdue_ap += row["unplanned_paise"]
        if due <= horizon_end:
            unplanned_due_in_horizon += row["unplanned_paise"]
            target = bucket_for(due)
            if target is not None:
                target["unplanned_ap_due_paise"] += row["unplanned_paise"]
                target["invoice_count"] += 1

    for bucket in buckets:
        bucket["projected_ap_cash_need_paise"] = (
            bucket["scheduled_approved_paise"] + bucket["unplanned_ap_due_paise"]
        )

    # PO commitments are procurement exposure, not dated cash outflows: payment terms
    # and invoice settlement dates are not reliably inferable from PO delivery dates.
    open_pos = db.query(PurchaseOrder).filter(
        PurchaseOrder.status.in_([
            POStatusEnum.SUBMITTED,
            POStatusEnum.APPROVED,
            POStatusEnum.PARTIALLY_RECEIVED,
        ]),
        PurchaseOrder.delivery_due_date <= datetime.combine(
            horizon_end, datetime.max.time(), tzinfo=timezone.utc
        ),
    ).all()
    po_commitment = sum(int(row.total_amount_paise or 0) for row in open_pos)
    po_by_delivery_window = {}
    for po in open_pos:
        delivery_date = po.delivery_due_date.date()
        target = bucket_for(delivery_date)
        if target is not None:
            po_by_delivery_window[target["window"]] = (
                po_by_delivery_window.get(target["window"], 0) + int(po.total_amount_paise or 0)
            )

    advances = db.query(SupplierAdvance).all()
    advance_ids = [row.id for row in advances]
    applied_by_advance = {}
    if advance_ids:
        advance_rows = db.query(
            SupplierAdvanceAllocation.advance_id,
            func.coalesce(func.sum(SupplierAdvanceAllocation.amount_paise), 0),
        ).filter(
            SupplierAdvanceAllocation.advance_id.in_(advance_ids)
        ).group_by(SupplierAdvanceAllocation.advance_id).all()
        applied_by_advance = {int(key): int(value or 0) for key, value in advance_rows}
    unapplied_advances = sum(
        max(int(row.amount_paise) - applied_by_advance.get(row.id, 0), 0)
        for row in advances
    )

    active_budgets = db.query(ProcurementBudget).filter(
        ProcurementBudget.status == "ACTIVE",
        ProcurementBudget.period_start <= horizon_end,
        ProcurementBudget.period_end >= today,
    ).all()
    budget_total = 0
    budget_available = 0
    budget_used = 0
    budget_rows = []
    for budget in active_budgets:
        available, earmarked = _budget_available_paise(db, budget)
        used = int(budget.total_amount_paise) - int(available) - int(earmarked)
        budget_total += int(budget.total_amount_paise)
        budget_available += int(available)
        budget_used += max(used, 0)
        budget_rows.append({
            "budget_id": budget.id,
            "budget_number": budget.budget_number,
            "department_id": budget.requesting_department_id,
            "category": budget.category,
            "period_start": budget.period_start.isoformat(),
            "period_end": budget.period_end.isoformat(),
            "allocated_paise": int(budget.total_amount_paise),
            "used_or_reserved_paise": max(used, 0),
            "available_paise": int(available),
        })

    return {
        "as_of_date": today.isoformat(),
        "horizon_days": horizon_days,
        "horizon_end": horizon_end.isoformat(),
        "currency_unit": "INR paise",
        "cash_position": {
            "overdue_unplanned_ap_paise": overdue_ap,
            "approved_payment_schedule_in_horizon_paise": approved_schedule_in_horizon,
            "unplanned_ap_due_in_horizon_paise": unplanned_due_in_horizon,
            "projected_ap_cash_need_in_horizon_paise": approved_schedule_in_horizon + unplanned_due_in_horizon,
            "all_open_ap_outstanding_paise": ap_due_total,
            "pending_unapproved_payment_requests_paise": sum(int(row.amount_paise) for row in pending_requests),
            "approved_payment_requests_all_dates_paise": approved_schedule_total,
        },
        "forecast_buckets": buckets,
        "approved_payment_schedule": approved_schedule_rows,
        "purchase_order_commitments": {
            "open_po_count": len(open_pos),
            "gross_commitment_due_for_delivery_in_horizon_paise": po_commitment,
            "by_delivery_window_paise": po_by_delivery_window,
            "cash_forecast_included": False,
            "explanation": "Open PO value is shown as a separate commitment exposure. It is not added to AP cash need because delivery dates are not payment dates and PO payment terms do not establish a reliable cash date.",
        },
        "supplier_advances": {
            "unapplied_advance_balance_paise": unapplied_advances,
            "cash_outflow_included_in_forecast": False,
            "explanation": "Advances are historical cash already paid. Unapplied balances are shown as prepaid supplier exposure, not future outflow.",
        },
        "procurement_budgets": {
            "active_budget_count": len(active_budgets),
            "allocated_paise": budget_total,
            "used_or_reserved_paise": budget_used,
            "available_paise": budget_available,
            "budgets": budget_rows,
            "explanation": "Budget availability is a control metric, not a bank cash balance or cash source.",
        },
        "methodology": {
            "approved_scheduled_payments": "Approved, unexecuted payment requests are placed on their scheduled dates.",
            "unplanned_ap": "Net invoice outstanding after cash payments, approved credit/debit adjustments and applied supplier advances, less approved payment allocations scheduled within the forecast horizon; placed on contractual invoice due dates.",
            "no_double_counting": "Reserved amounts are excluded from unplanned AP before approved scheduled amounts are added.",
            "limitations": [
                "This is a procurement cash-requirement forecast, not a bank-balance or whole-hospital cash forecast.",
                "Pending payment requests are disclosed separately and are not treated as approved cash outflows.",
                "PO commitments are not assigned cash dates without a matched invoice/payment schedule.",
                "No revenue, payroll, operating expense, tax remittance or bank-balance forecast is included.",
            ],
        },
    }


@router.get("/analytics/cost-intelligence")
def get_procurement_cost_intelligence(
    from_date: Optional[date] = Query(default=None, description="Inclusive date filter (UTC)."),
    to_date: Optional[date] = Query(default=None, description="Inclusive date filter (UTC)."),
    medication_id: Optional[int] = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    """Summarize procurement spend, medication price observations and supplier returns."""
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must be on or before to_date.")
    if medication_id is not None:
        medication = db.get(MedicationMaster, medication_id)
        if medication is None:
            raise HTTPException(status_code=404, detail="Medication not found.")

    start_at = datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc) if from_date else None
    end_at = datetime.combine(to_date, datetime.max.time(), tzinfo=timezone.utc) if to_date else None
    eligible_statuses = (
        POStatusEnum.APPROVED,
        POStatusEnum.PARTIALLY_RECEIVED,
        POStatusEnum.COMPLETED,
    )

    line_query = db.query(PurchaseOrderItem, PurchaseOrder, VendorMaster, MedicationMaster).join(
        PurchaseOrder, PurchaseOrderItem.po_id == PurchaseOrder.id
    ).join(
        VendorMaster, PurchaseOrder.vendor_id == VendorMaster.id
    ).outerjoin(
        MedicationMaster, PurchaseOrderItem.medication_id == MedicationMaster.id
    ).filter(
        PurchaseOrder.status.in_(eligible_statuses)
    )
    if start_at:
        line_query = line_query.filter(PurchaseOrder.created_at >= start_at)
    if end_at:
        line_query = line_query.filter(PurchaseOrder.created_at <= end_at)
    if medication_id is not None:
        line_query = line_query.filter(PurchaseOrderItem.medication_id == medication_id)
    purchase_lines = line_query.order_by(PurchaseOrder.created_at.asc(), PurchaseOrder.id.asc()).all()

    monthly = {}
    category_spend = {}
    medication_prices = {}
    supplier_comparison = {}
    total_spend_paise = 0
    for item, po, vendor, medication in purchase_lines:
        gross_value = int(item.gross_total_paise or item.total_price_paise or 0)
        total_spend_paise += gross_value
        month_key = po.created_at.strftime("%Y-%m")
        monthly[month_key] = monthly.get(month_key, 0) + gross_value
        category_key = medication.form.value if medication is not None else "GENERAL_OR_UNCLASSIFIED"
        category_spend[category_key] = category_spend.get(category_key, 0) + gross_value

        if medication is not None:
            price_record = {
                "purchase_order_id": po.id,
                "po_number": po.po_number,
                "purchase_date": po.created_at.isoformat(),
                "vendor_id": vendor.id,
                "vendor_name": vendor.name,
                "quantity": int(item.quantity_ordered),
                "purchase_uom_code": item.purchase_uom_code,
                "base_uom_code": item.base_uom_code,
                "units_per_purchase_unit": float(item.units_per_purchase_unit) if item.units_per_purchase_unit is not None else None,
                "base_quantity": float(item.base_quantity) if item.base_quantity is not None else None,
                "unit_price_paise_pre_tax": int(item.unit_price_paise),
                "base_unit_price_paise_pre_tax": float(item.base_unit_price_paise) if item.base_unit_price_paise is not None else None,
                "unit_price_comparable": item.base_unit_price_paise is not None,
                "tax_percentage": int(item.tax_percentage or 0),
            }
            medication_prices.setdefault(medication.id, {
                "medication_id": medication.id,
                "medication_code": medication.code,
                "brand_name": medication.brand_name,
                "generic_name": medication.generic_name,
                "form": medication.form.value,
                "observations": [],
            })["observations"].append(price_record)
            supplier_key = (medication.id, vendor.id)
            supplier_comparison.setdefault(supplier_key, {
                "medication_id": medication.id,
                "medication_code": medication.code,
                "brand_name": medication.brand_name,
                "vendor_id": vendor.id,
                "vendor_name": vendor.name,
                "purchase_line_count": 0,
                "ordered_quantity": 0,
                "pre_tax_value_paise": 0,
                "observed_unit_prices_paise": [],
                "normalized_base_unit_prices_paise": [],
                "base_uom_code": item.base_uom_code,
                "has_unknown_unit_lines": False,
            })
            supplier_row = supplier_comparison[supplier_key]
            supplier_row["purchase_line_count"] += 1
            supplier_row["ordered_quantity"] += int(item.quantity_ordered)
            supplier_row["pre_tax_value_paise"] += int(item.total_price_paise or 0)
            supplier_row["observed_unit_prices_paise"].append(int(item.unit_price_paise))
            supplier_row.setdefault("purchase_unit_price_observations", []).append({
                "price_paise": int(item.unit_price_paise),
                "purchase_uom_code": item.purchase_uom_code,
            })
            if item.base_unit_price_paise is not None and item.base_uom_code:
                supplier_row["normalized_base_unit_prices_paise"].append(float(item.base_unit_price_paise))
            else:
                supplier_row["has_unknown_unit_lines"] = True

    return_query = db.query(InventoryMovement).options(joinedload(InventoryMovement.medication)).filter(
        InventoryMovement.movement_type == "PURCHASE_RETURN",
        InventoryMovement.quantity_delta < 0,
    )
    if start_at:
        return_query = return_query.filter(InventoryMovement.created_at >= start_at)
    if end_at:
        return_query = return_query.filter(InventoryMovement.created_at <= end_at)
    if medication_id is not None:
        return_query = return_query.filter(InventoryMovement.medication_id == medication_id)
    return_movements = return_query.all()
    returned_quantity = sum(abs(int(row.quantity_delta)) for row in return_movements)
    returned_value_paise = sum(
        (Decimal(abs(int(row.quantity_delta))) * Decimal(str(row.unit_price_paise)))
        for row in return_movements
    )
    return_by_medication = {}
    for row in return_movements:
        med = row.medication
        if med is None:
            continue
        entry = return_by_medication.setdefault(med.id, {
            "medication_id": med.id,
            "medication_code": med.code,
            "brand_name": med.brand_name,
            "returned_quantity": 0,
            "base_uom_code": row.base_uom_code,
            "returned_value_paise": 0,
        })
        entry["returned_quantity"] += abs(int(row.quantity_delta))
        entry["returned_value_paise"] += float(
            Decimal(abs(int(row.quantity_delta))) * Decimal(str(row.unit_price_paise))
        )

    return {
        "period": {
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
            "basis": "Purchase order creation date (UTC); supplier returns use inventory movement creation date.",
        },
        "filters": {"medication_id": medication_id},
        "procurement_spend": {
            "total_paise": total_spend_paise,
            "monthly_paise": [
                {"month": month, "spend_paise": amount}
                for month, amount in sorted(monthly.items())
            ],
            "by_medication_form_paise": [
                {"category": category, "spend_paise": amount}
                for category, amount in sorted(category_spend.items())
            ],
            "definition": "Tax-inclusive approved, partially received and completed PO line values; excludes draft, submitted, cancelled and unapproved orders.",
        },
        "medication_price_history": list(medication_prices.values()),
        "supplier_price_comparison": list(supplier_comparison.values()),
        "price_comparison_note": (
            "Purchase-unit prices are retained for audit. Normalized base_unit_price_paise_pre_tax and "
            "normalized_base_unit_prices_paise are available only for lines with a verified pack snapshot; "
            "legacy lines with unknown units are excluded from normalized comparisons. Compare normalized prices "
            "only when base_uom_code matches."
        ),
        "supplier_returns": {
            "movement_count": len(return_movements),
            "returned_quantity": returned_quantity if medication_id is not None else None,
            "returned_quantity_base_units": returned_quantity if medication_id is not None else None,
            "quantity_note": "Quantity is reported only when filtered to one medication; unfiltered totals span incompatible base units.",
            "returned_value_paise": float(returned_value_paise),
            "by_medication": list(return_by_medication.values()),
            "definition": "Value uses immutable PURCHASE_RETURN movement quantity and unit-price snapshots; it is not a supplier credit-note settlement balance.",
        },
    }


@router.get("/analytics/financial-intelligence")
def get_procurement_financial_intelligence(
    from_date: Optional[date] = Query(default=None, description="Inclusive PO creation/invoice date filter (UTC)."),
    to_date: Optional[date] = Query(default=None, description="Inclusive PO creation/invoice date filter (UTC)."),
    due_within_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:read")),
):
    """Executive procurement financial view using approved PO, accepted GRN, invoice and AP records."""
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must be on or before to_date.")

    start_at = datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc) if from_date else None
    end_at = datetime.combine(to_date, datetime.max.time(), tzinfo=timezone.utc) if to_date else None
    now = datetime.now(timezone.utc)
    due_cutoff = now + timedelta(days=due_within_days)
    issued_statuses = (
        POStatusEnum.SUBMITTED, POStatusEnum.APPROVED,
        POStatusEnum.PARTIALLY_RECEIVED, POStatusEnum.COMPLETED,
    )

    po_query = db.query(PurchaseOrder).options(
        selectinload(PurchaseOrder.items), joinedload(PurchaseOrder.vendor)
    ).filter(PurchaseOrder.status.in_(issued_statuses))
    if start_at:
        po_query = po_query.filter(PurchaseOrder.created_at >= start_at)
    if end_at:
        po_query = po_query.filter(PurchaseOrder.created_at <= end_at)
    purchase_orders = po_query.order_by(PurchaseOrder.created_at.asc(), PurchaseOrder.id.asc()).all()
    po_ids = [po.id for po in purchase_orders]

    accepted_grns = []
    if po_ids:
        accepted_grns = db.query(GoodsReceiptNote).options(
            selectinload(GoodsReceiptNote.items)
        ).filter(
            GoodsReceiptNote.po_id.in_(po_ids),
            GoodsReceiptNote.status == GRNStatusEnum.ACCEPTED,
        ).all()

    accepted_value_paise = 0
    accepted_quantity_by_uom = {}
    received_quantity_by_uom = {}
    accepted_grn_line_count = 0
    accepted_po_item_ids = {
        line.po_item_id for grn in accepted_grns for line in grn.items
    }
    po_items_by_id = {}
    if accepted_po_item_ids:
        po_items_by_id = {
            item.id: item for item in db.query(PurchaseOrderItem).filter(
                PurchaseOrderItem.id.in_(accepted_po_item_ids)
            ).all()
        }
    for grn in accepted_grns:
        for line in grn.items:
            po_item = po_items_by_id.get(line.po_item_id)
            if po_item is None:
                continue
            uom_key = line.base_uom_code or "UNKNOWN"
            accepted_quantity_by_uom[uom_key] = (
                accepted_quantity_by_uom.get(uom_key, 0) + int(line.accepted_quantity or 0)
            )
            received_quantity_by_uom[uom_key] = (
                received_quantity_by_uom.get(uom_key, 0) + int(line.received_quantity or 0)
            )
            accepted_grn_line_count += 1
            if po_item.quantity_ordered > 0:
                line_value_numerator = (
                    int(po_item.gross_total_paise or 0) * int(line.accepted_quantity or 0)
                )
                accepted_value_paise += (
                    line_value_numerator + int(po_item.quantity_ordered) // 2
                ) // int(po_item.quantity_ordered)

    committed_paise = sum(int(po.total_amount_paise or 0) for po in purchase_orders)
    vendor_commitments = {}
    for po in purchase_orders:
        row = vendor_commitments.setdefault(po.vendor_id, {
            "vendor_id": po.vendor_id,
            "vendor_name": po.vendor.name if po.vendor else "Unknown vendor",
            "committed_paise": 0,
            "purchase_order_count": 0,
        })
        row["committed_paise"] += int(po.total_amount_paise or 0)
        row["purchase_order_count"] += 1
    concentration = []
    for row in sorted(vendor_commitments.values(), key=lambda x: x["committed_paise"], reverse=True):
        row["commitment_share_pct"] = round(
            row["committed_paise"] / committed_paise * 100, 2
        ) if committed_paise else None
        concentration.append(row)
    concentration_hhi = round(sum(
        (row["committed_paise"] / committed_paise * 100) ** 2
        for row in concentration
    ), 2) if committed_paise else None
    top_three_supplier_share_pct = round(
        sum(row["committed_paise"] for row in concentration[:3]) / committed_paise * 100, 2
    ) if committed_paise else None

    # Reuse the dedicated analytics so definitions and department access stay consistent.
    quotation_outcomes = get_procurement_quotation_outcomes(from_date, to_date, db, current_user)
    budget_dashboard = get_procurement_budget_dashboard(from_date, to_date, None, None, db, current_user)
    budget_rows = budget_dashboard.get("allocations", [])
    budget_summary_by_period_type = {}
    for budget_row in budget_rows:
        period_type = budget_row["period_type"]
        summary = budget_summary_by_period_type.setdefault(period_type, {
            "allocation_count": 0, "allocated_paise": 0, "engaged_paise": 0,
            "available_paise": 0, "warning_count": 0, "over_budget_count": 0,
        })
        summary["allocation_count"] += 1
        summary["allocated_paise"] += int(budget_row["allocated_paise"])
        summary["engaged_paise"] += int(budget_row["engaged_paise"])
        summary["available_paise"] += int(budget_row["available_paise"])
        summary["warning_count"] += int(budget_row["alert"] == "WARNING")
        summary["over_budget_count"] += int(budget_row["alert"] == "OVER_BUDGET")

    invoice_query = db.query(VendorInvoice).filter(
        VendorInvoice.status.in_([
            VendorInvoiceStatusEnum.PENDING_VERIFICATION,
            VendorInvoiceStatusEnum.PRICE_VARIANCE_FLAGGED,
            VendorInvoiceStatusEnum.MATCHED_APPROVED,
            VendorInvoiceStatusEnum.PAID,
        ])
    )
    if start_at:
        invoice_query = invoice_query.filter(VendorInvoice.invoice_date >= start_at)
    if end_at:
        invoice_query = invoice_query.filter(VendorInvoice.invoice_date <= end_at)
    invoices = invoice_query.all()
    invoice_total_paise = sum(int(row.total_amount_paise or 0) for row in invoices)
    pending_verification_paise = sum(
        int(row.total_amount_paise or 0) for row in invoices
        if row.status in (VendorInvoiceStatusEnum.PENDING_VERIFICATION, VendorInvoiceStatusEnum.PRICE_VARIANCE_FLAGGED)
    )

    linked_expense_ids = [row.linked_expense_id for row in invoices if row.linked_expense_id]
    ap_expenses = {}
    if linked_expense_ids:
        ap_expenses = {
            row.id: row for row in db.query(ExpenseRecord).filter(
                ExpenseRecord.id.in_(linked_expense_ids)
            ).all()
        }
    paid_by_invoice = _supplier_paid_amounts_by_invoice(db, {row.id for row in invoices})
    ap_balances = []
    for invoice in invoices:
        expense = ap_expenses.get(invoice.linked_expense_id) if invoice.linked_expense_id else None
        if expense is None:
            continue
        paid_amount = _effective_invoice_paid_amount(invoice, paid_by_invoice)
        outstanding_amount, credit_amount, advance_amount = _supplier_invoice_outstanding(db, invoice)
        ap_balances.append((invoice, expense, paid_amount, outstanding_amount, credit_amount, advance_amount))
    outstanding_balances = [row for row in ap_balances if row[3] > 0]
    overdue_balances = [
        row for row in outstanding_balances
        if row[1].due_date is not None and row[1].due_date < now
    ]
    upcoming_balances = [
        row for row in outstanding_balances
        if row[1].due_date is not None and now <= row[1].due_date <= due_cutoff
    ]

    return {
        "period": {
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
            "purchase_basis": "Purchase order creation date (UTC).",
            "invoice_basis": "Vendor invoice date (UTC).",
        },
        "commitments": {
            "purchase_order_count": len(purchase_orders),
            "committed_value_paise": committed_paise,
            "definition": "Tax-inclusive value of submitted and approved/received purchase orders; excludes draft and cancelled POs.",
        },
        "receipts": {
            "accepted_grn_count": len(accepted_grns),
            "accepted_grn_line_count": accepted_grn_line_count,
            "received_quantity_by_base_uom": received_quantity_by_uom,
            "accepted_quantity_by_base_uom": accepted_quantity_by_uom,
            "accepted_goods_value_paise": accepted_value_paise,
            "valuation_basis": "Accepted quantity valued proportionally at the linked approved PO line's tax-inclusive gross unit value, rounded to the nearest paise per GRN line; quantities are grouped by base UOM to avoid adding incompatible units. This is receipt valuation, not a supplier invoice or payment.",
        },
        "invoices": {
            "invoice_count": len(invoices),
            "invoiced_value_paise": invoice_total_paise,
            "pending_verification_or_variance_value_paise": pending_verification_paise,
            "definition": "Includes pending verification, price-variance flagged, matched-approved and paid invoices in the selected invoice-date period.",
        },
        "accounts_payable": {
            "posted_invoice_count": len(ap_balances),
            "posted_expense_count": len(ap_expenses),
            "approved_unpaid_value_paise": sum(row[3] for row in outstanding_balances),
            "cash_paid_value_paise": sum(row[2] for row in ap_balances),
            "paid_expense_value_paise": sum(row[2] for row in ap_balances),  # Backward-compatible alias.
            "credit_adjustments_applied_paise": sum(row[4] for row in ap_balances),
            "supplier_advances_applied_paise": sum(row[5] for row in ap_balances),
            "overdue_approved_count": len(overdue_balances),
            "overdue_approved_value_paise": sum(row[3] for row in overdue_balances),
            "due_within_days": due_within_days,
            "due_soon_count": len(upcoming_balances),
            "due_soon_value_paise": sum(row[3] for row in upcoming_balances),
            "definition": "Derived from posted supplier invoices, immutable cash payment allocations, approved credit/debit note applications and supplier advance applications. All three reduce net outstanding; cash payments remain separately reported."
        },
        "supplier_concentration": {
            "basis": "Tax-inclusive PO commitments in the selected PO creation-date period.",
            "suppliers": concentration,
            "top_supplier_share_pct": concentration[0]["commitment_share_pct"] if concentration else None,
            "top_three_supplier_share_pct": top_three_supplier_share_pct,
            "herfindahl_hirschman_index": concentration_hhi,
            "hhi_scale": "0 to 10,000; sum of squared supplier commitment shares expressed as percentages. Descriptive concentration measure only.",
        },
        "quotation_savings": {
            **quotation_outcomes["summary"],
            "definition": quotation_outcomes["summary"]["competitive_savings_definition"],
            "realized_cash_savings_reported": False,
        },
        "budget_intelligence": {
            "allocation_count": len(budget_rows),
            "by_period_type": budget_summary_by_period_type,
            "unbudgeted_procurement": budget_dashboard["unbudgeted_procurement"],
            "allocation_definitions": budget_dashboard["definitions"],
            "note": "Annual and quarterly budget allocations are reported separately; budget engagement is not cash expenditure.",
        },
        "limitations": [
            "Quotation savings are estimated competitive price advantages against the best comparable non-selected quotation, not realized cash savings or paid-invoice savings.",
            "PO commitment, accepted receipt valuation, invoice value and AP cash settlement are distinct lifecycle measures and must not be added together.",
            "Supplier payments are recorded as hospital-entered outflows; external bank-statement reconciliation and automated bank feeds are not modeled.",
            "Supplier concentration is based on PO commitments, not settled payments or accepted receipt value.",
            "Budget utilization uses the existing reservation/accepted-receipt ledger; it is a procurement control measure, not a bank cash balance.",
        ],
    }


@router.get("/vendors/{vendor_id}/metrics")
def get_vendor_metrics(
    vendor_id: int,
    from_date: Optional[date] = Query(default=None, description="Inclusive PO creation date (UTC)."),
    to_date: Optional[date] = Query(default=None, description="Inclusive PO creation date (UTC)."),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    """Return a date-filtered supplier scorecard based on accepted hospital receipts."""
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must be on or before to_date.")

    vendor = db.get(VendorMaster, vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Vendor not found.")

    start_at = datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc) if from_date else None
    end_at = datetime.combine(to_date, datetime.max.time(), tzinfo=timezone.utc) if to_date else None

    po_query = db.query(PurchaseOrder).options(
        selectinload(PurchaseOrder.items),
    ).filter(
        PurchaseOrder.vendor_id == vendor_id,
        PurchaseOrder.status != POStatusEnum.CANCELLED,
    )
    if start_at:
        po_query = po_query.filter(PurchaseOrder.created_at >= start_at)
    if end_at:
        po_query = po_query.filter(PurchaseOrder.created_at <= end_at)
    purchase_orders = po_query.order_by(PurchaseOrder.created_at.asc(), PurchaseOrder.id.asc()).all()
    po_ids = [po.id for po in purchase_orders]

    accepted_grns = []
    if po_ids:
        accepted_grns = db.query(GoodsReceiptNote).options(
            selectinload(GoodsReceiptNote.items)
        ).filter(
            GoodsReceiptNote.po_id.in_(po_ids),
            GoodsReceiptNote.status == GRNStatusEnum.ACCEPTED,
        ).all()

    grns_by_po = {}
    accepted_quantity = 0
    rejected_quantity = 0
    received_quantity = 0
    for grn in accepted_grns:
        grns_by_po.setdefault(grn.po_id, []).append(grn)
        for line in grn.items:
            received_quantity += int(line.received_quantity or 0)
            accepted_quantity += int(line.accepted_quantity or 0)
            rejected_quantity += int(line.rejected_quantity or 0)

    issued_pos = [
        po for po in purchase_orders
        if po.status in (
            POStatusEnum.SUBMITTED,
            POStatusEnum.APPROVED,
            POStatusEnum.PARTIALLY_RECEIVED,
            POStatusEnum.COMPLETED,
        )
    ]
    received_pos = [po for po in issued_pos if grns_by_po.get(po.id)]
    late_pos = 0
    delivery_delays = []
    for po in received_pos:
        accepted_at_values = [
            grn.accepted_at or grn.created_at
            for grn in grns_by_po[po.id]
        ]
        actual_receipt_at = max(accepted_at_values)
        due_at = po.delivery_due_date
        # Database timestamps may be returned naive by SQLite test environments.
        if due_at.tzinfo is None and actual_receipt_at.tzinfo is not None:
            due_at = due_at.replace(tzinfo=actual_receipt_at.tzinfo)
        elif actual_receipt_at.tzinfo is None and due_at.tzinfo is not None:
            actual_receipt_at = actual_receipt_at.replace(tzinfo=due_at.tzinfo)
        delay_days = max(0, (actual_receipt_at - due_at).total_seconds() / 86400)
        if delay_days > 0:
            late_pos += 1
            delivery_delays.append(delay_days)

    ordered_quantity = sum(
        int(item.quantity_ordered or 0)
        for po in issued_pos for item in po.items
    )
    invoice_query = db.query(VendorInvoice).filter(VendorInvoice.vendor_id == vendor_id)
    if start_at:
        invoice_query = invoice_query.filter(VendorInvoice.invoice_date >= start_at)
    if end_at:
        invoice_query = invoice_query.filter(VendorInvoice.invoice_date <= end_at)
    invoices = invoice_query.all()

    invoice_count = len(invoices)
    flagged_invoices = sum(
        1 for invoice in invoices
        if invoice.status == VendorInvoiceStatusEnum.PRICE_VARIANCE_FLAGGED
    )
    paid_by_invoice = _supplier_paid_amounts_by_invoice(db, {invoice.id for invoice in invoices})
    matched_unpaid = []
    matched_unpaid_exposure_paise = 0
    for invoice in invoices:
        if invoice.status != VendorInvoiceStatusEnum.MATCHED_APPROVED:
            continue
        paid_amount = _effective_invoice_paid_amount(invoice, paid_by_invoice)
        outstanding_amount, _, _ = _supplier_invoice_outstanding(db, invoice)
        if outstanding_amount > 0:
            matched_unpaid.append(invoice)
            matched_unpaid_exposure_paise += outstanding_amount

    return {
        "vendor_id": vendor.id,
        "vendor_code": vendor.code,
        "vendor_name": vendor.name,
        "period": {
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
            "basis": "purchase_order.created_at (UTC); invoice metrics use invoice_date",
        },
        "purchase_orders": {
            "total": len(purchase_orders),
            "issued": len(issued_pos),
            "received": len(received_pos),
            "open": sum(
                1 for po in issued_pos
                if po.status in (POStatusEnum.SUBMITTED, POStatusEnum.APPROVED, POStatusEnum.PARTIALLY_RECEIVED)
            ),
            "ordered_value_paise": sum(int(po.total_amount_paise or 0) for po in issued_pos),
        },
        "delivery": {
            "received_po_count": len(received_pos),
            "late_po_count": late_pos,
            "on_time_delivery_rate_pct": round(
                (len(received_pos) - late_pos) / len(received_pos) * 100, 2
            ) if received_pos else None,
            "average_delay_days_for_late_pos": round(
                sum(delivery_delays) / len(delivery_delays), 2
            ) if delivery_delays else 0.0,
            "definition": "A PO is counted as received only after at least one GRN is ACCEPTED; latest accepted GRN time is compared with PO due date.",
        },
        "fulfillment": {
            "ordered_quantity": ordered_quantity,
            "physically_received_quantity": received_quantity,
            "accepted_quantity": accepted_quantity,
            "rejected_quantity": rejected_quantity,
            "accepted_fulfillment_rate_pct": round(
                accepted_quantity / ordered_quantity * 100, 2
            ) if ordered_quantity else None,
            "rejection_rate_pct": round(
                rejected_quantity / received_quantity * 100, 2
            ) if received_quantity else None,
            "definition": "Quantities are summed from accepted GRN lines only; carrier delivery events do not count as receipt.",
        },
        "invoices": {
            "total": invoice_count,
            "price_variance_flagged": flagged_invoices,
            "price_variance_flag_rate_pct": round(
                flagged_invoices / invoice_count * 100, 2
            ) if invoice_count else None,
            "matched_approved_unpaid_count": len(matched_unpaid),
            "matched_approved_unpaid_exposure_paise": matched_unpaid_exposure_paise,
            "exposure_definition": "MATCHED_APPROVED invoices with positive net balance are included; cash payments, approved adjustment applications and supplier advance applications reduce exposure. Pending, flagged, rejected and fully PAID invoices are excluded.",
        },
    }



@router.get("/budgets/analytics/dashboard")
def get_procurement_budget_dashboard(
    from_date: Optional[date] = Query(default=None, description="Inclusive movement date filter (UTC)."),
    to_date: Optional[date] = Query(default=None, description="Inclusive movement date filter (UTC)."),
    department_id: Optional[int] = Query(default=None, gt=0),
    category: Optional[str] = Query(default=None, pattern="^(PHARMACY|LABORATORY|GENERAL_SUPPLIES|EQUIPMENT|SERVICES|OTHER)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:read")),
):
    """Budget portfolio, department/category allocation, movement trend and run-rate forecast."""
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must be on or before to_date.")
    today = datetime.now(timezone.utc).date()
    window_end = to_date or today
    window_start = from_date or (window_end - timedelta(days=364))
    start_at = datetime.combine(window_start, datetime.min.time(), tzinfo=timezone.utc)
    end_at = datetime.combine(window_end, datetime.max.time(), tzinfo=timezone.utc)

    query = db.query(ProcurementBudget).options(
        joinedload(ProcurementBudget.department)
    ).filter(
        ProcurementBudget.period_start <= window_end,
        ProcurementBudget.period_end >= window_start,
    )
    scope_department_ids = None
    if department_id is not None:
        if not current_user.is_superuser and not user_has_department_access(db, current_user, department_id):
            raise HTTPException(status_code=403, detail="You are not assigned to the requested budget department.")
        scope_department_ids = {department_id}
        query = query.filter(ProcurementBudget.requesting_department_id == department_id)
    elif not current_user.is_superuser:
        scope_department_ids = {
            row[0] for row in db.query(UserRole.department_id).filter(
                UserRole.user_id == current_user.id,
                UserRole.department_id.is_not(None),
            ).distinct().all()
            if row[0] is not None and user_has_department_access(db, current_user, row[0])
        }
        query = query.filter(ProcurementBudget.requesting_department_id.in_(scope_department_ids or [-1]))
    if category:
        query = query.filter(ProcurementBudget.category == category)
    budgets = query.order_by(
        ProcurementBudget.requesting_department_id.asc(),
        ProcurementBudget.category.asc(),
        ProcurementBudget.period_start.asc(),
        ProcurementBudget.period_type.asc(),
    ).all()

    unbudgeted_query = db.query(
        PurchaseOrderItem.budget_department_id,
        PurchaseOrderItem.budget_category,
        VendorMaster.id,
        VendorMaster.name,
        func.count(func.distinct(PurchaseOrder.id)),
        func.count(PurchaseOrderItem.id),
        func.coalesce(func.sum(PurchaseOrderItem.gross_total_paise), 0),
    ).join(
        PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.po_id
    ).join(
        VendorMaster, VendorMaster.id == PurchaseOrder.vendor_id
    ).filter(
        PurchaseOrderItem.budget_id.is_(None),
        PurchaseOrder.status.in_([
            POStatusEnum.APPROVED,
            POStatusEnum.PARTIALLY_RECEIVED,
            POStatusEnum.COMPLETED,
        ]),
        PurchaseOrder.created_at >= start_at,
        PurchaseOrder.created_at <= end_at,
    )
    if scope_department_ids is not None:
        unbudgeted_query = unbudgeted_query.filter(
            PurchaseOrderItem.budget_department_id.in_(scope_department_ids or [-1])
        )
    if category:
        unbudgeted_query = unbudgeted_query.filter(PurchaseOrderItem.budget_category == category)
    unbudgeted_rows = unbudgeted_query.group_by(
        PurchaseOrderItem.budget_department_id,
        PurchaseOrderItem.budget_category,
        VendorMaster.id,
        VendorMaster.name,
    ).all()
    unbudgeted_by_department_category = {}
    unbudgeted_total_paise = 0
    unbudgeted_po_count = 0
    unbudgeted_line_count = 0
    for dept_id, item_category, vendor_id, vendor_name, po_count, line_count, amount in unbudgeted_rows:
        key = (dept_id, item_category or "UNCLASSIFIED")
        row = unbudgeted_by_department_category.setdefault(key, {
            "department_id": dept_id,
            "category": item_category or "UNCLASSIFIED",
            "po_count": 0,
            "line_count": 0,
            "gross_value_paise": 0,
            "suppliers": [],
        })
        row["po_count"] += int(po_count)
        row["line_count"] += int(line_count)
        row["gross_value_paise"] += int(amount or 0)
        row["suppliers"].append({"vendor_id": vendor_id, "vendor_name": vendor_name})
        unbudgeted_total_paise += int(amount or 0)
        unbudgeted_line_count += int(line_count)

    unbudgeted_count_query = db.query(func.count(func.distinct(PurchaseOrder.id))).select_from(
        PurchaseOrderItem
    ).join(
        PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.po_id
    ).filter(
        PurchaseOrderItem.budget_id.is_(None),
        PurchaseOrder.status.in_([
            POStatusEnum.APPROVED,
            POStatusEnum.PARTIALLY_RECEIVED,
            POStatusEnum.COMPLETED,
        ]),
        PurchaseOrder.created_at >= start_at,
        PurchaseOrder.created_at <= end_at,
    )
    if scope_department_ids is not None:
        unbudgeted_count_query = unbudgeted_count_query.filter(
            PurchaseOrderItem.budget_department_id.in_(scope_department_ids or [-1])
        )
    if category:
        unbudgeted_count_query = unbudgeted_count_query.filter(PurchaseOrderItem.budget_category == category)
    unbudgeted_po_count = int(unbudgeted_count_query.scalar() or 0)

    visible_budget_ids = {budget.id for budget in budgets}
    annual_root_ids = {
        budget.id for budget in budgets
        if budget.period_type == "ANNUAL" and budget.parent_budget_id is None
    }
    child_budget_rows = db.query(ProcurementBudget).filter(
        ProcurementBudget.parent_budget_id.in_(annual_root_ids or {-1})
    ).all()
    all_ledger_budget_ids = visible_budget_ids | {child.id for child in child_budget_rows}
    ledger_rows = db.query(
        ProcurementBudgetMovement.budget_id,
        ProcurementBudgetMovement.movement_type,
        func.coalesce(func.sum(ProcurementBudgetMovement.amount_paise), 0),
    ).filter(
        ProcurementBudgetMovement.budget_id.in_(all_ledger_budget_ids or {-1})
    ).group_by(
        ProcurementBudgetMovement.budget_id,
        ProcurementBudgetMovement.movement_type,
    ).all()
    direct_totals = {}
    for ledger_budget_id, movement_type, amount in ledger_rows:
        direct_totals.setdefault(ledger_budget_id, {})[movement_type] = int(amount or 0)

    def _totals_for_dashboard_budget(budget_id: int, include_children: bool = False) -> dict:
        ids = [budget_id]
        if include_children:
            ids.extend(child.id for child in child_budget_rows if child.parent_budget_id == budget_id)
        totals = {"RESERVATION": 0, "RELEASE": 0, "RECEIPT": 0}
        for ledger_budget_id in ids:
            for movement_type, amount in direct_totals.get(ledger_budget_id, {}).items():
                totals[movement_type] = totals.get(movement_type, 0) + amount
        return {
            "reserved_open_paise": max(totals["RESERVATION"] - totals["RELEASE"] - totals["RECEIPT"], 0),
            "received_consumption_paise": totals["RECEIPT"],
        }

    direct_child_totals = {
        child.id: _totals_for_dashboard_budget(child.id)
        for child in child_budget_rows
    }
    invoice_budget_ids = all_ledger_budget_ids
    invoice_actuals_by_id = _budget_invoice_actuals_by_budget_ids(db, invoice_budget_ids)

    allocation_rows = []
    for budget in budgets:
        is_annual_root = budget.id in annual_root_ids
        totals = _totals_for_dashboard_budget(budget.id, include_children=is_annual_root)
        earmarked = 0
        if is_annual_root:
            for child in child_budget_rows:
                if child.parent_budget_id != budget.id or child.status != "ACTIVE":
                    continue
                child_totals = direct_child_totals[child.id]
                child_used = child_totals["reserved_open_paise"] + child_totals["received_consumption_paise"]
                earmarked += max(child.total_amount_paise - child_used, 0)
        available = budget.total_amount_paise - totals["reserved_open_paise"] - totals["received_consumption_paise"] - earmarked
        engaged = totals["reserved_open_paise"] + totals["received_consumption_paise"] + earmarked
        utilization = round(engaged * 100 / budget.total_amount_paise, 2) if budget.total_amount_paise else None
        if available < 0:
            alert = "OVER_BUDGET"
        elif utilization is not None and utilization >= budget.warning_threshold_pct:
            alert = "WARNING"
        else:
            alert = "NORMAL"
        elapsed_days = max((min(today, budget.period_end) - budget.period_start).days + 1, 0)
        total_days = max((budget.period_end - budget.period_start).days + 1, 1)
        received = totals["received_consumption_paise"]
        projected_received = round(received * total_days / elapsed_days) if elapsed_days > 0 else 0
        allocation_rows.append({
            "budget_id": budget.id,
            "budget_number": budget.budget_number,
            "department_id": budget.requesting_department_id,
            "department_name": budget.department.name if budget.department else None,
            "category": budget.category,
            "period_type": budget.period_type,
            "parent_budget_id": budget.parent_budget_id,
            "period_start": budget.period_start,
            "period_end": budget.period_end,
            "status": budget.status,
            "allocated_paise": budget.total_amount_paise,
            "reserved_open_commitment_paise": totals["reserved_open_paise"],
            "received_consumption_paise": received,
            "active_quarter_earmark_paise": earmarked,
            "engaged_paise": engaged,
            "available_paise": available,
            "utilization_pct": utilization,
            "warning_threshold_pct": budget.warning_threshold_pct,
            "alert": alert,
            "projected_period_receipts_paise": projected_received,
            "forecast_note": "Straight-line projection of accepted GRN consumption from period start through today; excludes open commitments and is not a purchasing recommendation.",
        })

    allocation_summary = {}
    for row in allocation_rows:
        key = (row["department_id"], row["category"], row["period_type"])
        summary = allocation_summary.setdefault(key, {
            "department_id": row["department_id"],
            "department_name": row["department_name"],
            "category": row["category"],
            "period_type": row["period_type"],
            "allocation_count": 0,
            "allocated_paise": 0,
            "engaged_paise": 0,
            "available_paise": 0,
            "warning_count": 0,
            "over_budget_count": 0,
        })
        summary["allocation_count"] += 1
        summary["allocated_paise"] += row["allocated_paise"]
        summary["engaged_paise"] += row["engaged_paise"]
        summary["available_paise"] += row["available_paise"]
        summary["warning_count"] += int(row["alert"] == "WARNING")
        summary["over_budget_count"] += int(row["alert"] == "OVER_BUDGET")

    # Movement rows are read once and grouped by month/category/department.
    visible_budget_id_list = list(visible_budget_ids)
    movements = db.query(
        ProcurementBudgetMovement,
        ProcurementBudget.requesting_department_id,
        ProcurementBudget.category,
    ).join(
        ProcurementBudget, ProcurementBudget.id == ProcurementBudgetMovement.budget_id
    ).filter(
        ProcurementBudgetMovement.budget_id.in_(visible_budget_id_list or [-1]),
        ProcurementBudgetMovement.created_at >= start_at,
        ProcurementBudgetMovement.created_at <= end_at,
    ).order_by(ProcurementBudgetMovement.created_at.asc()).all()

    monthly = {}
    department_category = {}
    for movement, movement_department_id, movement_category in movements:
        month = movement.created_at.strftime("%Y-%m")
        key = (movement_department_id, movement_category)
        monthly_row = monthly.setdefault(month, {
            "month": month,
            "reserved_paise": 0,
            "released_paise": 0,
            "received_paise": 0,
        })
        monthly_row[{
            "RESERVATION": "reserved_paise",
            "RELEASE": "released_paise",
            "RECEIPT": "received_paise",
        }[movement.movement_type]] += movement.amount_paise
        summary = department_category.setdefault(key, {
            "department_id": movement_department_id,
            "category": movement_category,
            "reservation_movement_paise": 0,
            "release_movement_paise": 0,
            "received_movement_paise": 0,
        })
        summary[{
            "RESERVATION": "reservation_movement_paise",
            "RELEASE": "release_movement_paise",
            "RECEIPT": "received_movement_paise",
        }[movement.movement_type]] += movement.amount_paise

    month_cursor = date(window_start.year, window_start.month, 1)
    month_end = date(window_end.year, window_end.month, 1)
    monthly_trend = []
    while month_cursor <= month_end:
        key = month_cursor.strftime("%Y-%m")
        monthly_trend.append(monthly.get(key, {
            "month": key,
            "reserved_paise": 0,
            "released_paise": 0,
            "received_paise": 0,
        }))
        month_cursor = date(
            month_cursor.year + (1 if month_cursor.month == 12 else 0),
            1 if month_cursor.month == 12 else month_cursor.month + 1,
            1,
        )

    # Invoice actuals are fetched once, then rolled up to annual roots.
    invoice_actuals = []
    for budget in budgets:
        actuals = invoice_actuals_by_id.get(budget.id, {
            "verified_invoice_actuals_paise": 0,
            "paid_invoice_actuals_paise": 0,
            "unpaid_verified_invoice_actuals_paise": 0,
            "verified_invoice_ids": set(),
        })
        invoice_ids = set(actuals["verified_invoice_ids"])
        if budget.id in annual_root_ids:
            for child in child_budget_rows:
                if child.parent_budget_id != budget.id:
                    continue
                child_actuals = invoice_actuals_by_id.get(child.id, {})
                for field in (
                    "verified_invoice_actuals_paise",
                    "paid_invoice_actuals_paise",
                    "unpaid_verified_invoice_actuals_paise",
                ):
                    actuals[field] += child_actuals.get(field, 0)
                invoice_ids.update(child_actuals.get("verified_invoice_ids", set()))
        invoice_actuals.append({
            "budget_id": budget.id,
            "verified_invoice_actuals_paise": actuals["verified_invoice_actuals_paise"],
            "paid_invoice_actuals_paise": actuals["paid_invoice_actuals_paise"],
            "unpaid_verified_invoice_actuals_paise": actuals["unpaid_verified_invoice_actuals_paise"],
            "verified_invoice_count": len(invoice_ids),
        })

    return {
        "from_date": window_start,
        "to_date": window_end,
        "allocation_count": len(allocation_rows),
        "allocations": allocation_rows,
        "allocation_summary_by_department_category_period": list(allocation_summary.values()),
        "department_category_movement_summary": list(department_category.values()),
        "monthly_movement_trend": monthly_trend,
        "invoice_actuals_by_budget": invoice_actuals,
        "unbudgeted_procurement": {
            "purchase_order_count": unbudgeted_po_count,
            "line_count": unbudgeted_line_count,
            "gross_value_paise": unbudgeted_total_paise,
            "by_department_category": [
                {
                    **row,
                    "suppliers": sorted(row["suppliers"], key=lambda supplier: (supplier["vendor_name"] or "").lower()),
                }
                for row in unbudgeted_by_department_category.values()
            ],
            "definition": "Approved, partially received and completed PO lines without a budget allocation, filtered by PO creation date. This includes legacy lines and purchases made where no active budget control was configured; it is not automatically proof of policy violation.",
        },
        "definitions": {
            "movement_trend": "RESERVATION, RELEASE and accepted GRN receipt movements in the selected date window; each ledger movement is counted once.",
            "allocation_rows": "Annual and quarterly allocations are shown separately. Annual utilization includes its child-quarter movements and earmarks; do not sum annual and quarterly rows into a single portfolio total.",
            "forecast": "Straight-line accepted-receipt run rate, not an AI forecast; invoice actuals are informational and are not added to budget consumption.",
        },
    }


# --- Procurement budget allocation and controlled revisions ---
@router.post("/budgets", response_model=ProcurementBudgetResponse, status_code=status.HTTP_201_CREATED)
def create_procurement_budget(
    payload: ProcurementBudgetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:write")),
):
    department = db.get(Department, payload.requesting_department_id)
    if department is None or not department.is_active:
        raise HTTPException(status_code=404, detail="Budget department is unavailable.")
    if not current_user.is_superuser and not user_has_department_access(db, current_user, department.id):
        raise HTTPException(status_code=403, detail="You are not assigned to the budget department.")
    parent_budget = None
    if payload.parent_budget_id is not None:
        parent_budget = db.get(ProcurementBudget, payload.parent_budget_id)
        if (
            payload.period_type != "QUARTERLY"
            or parent_budget is None
            or parent_budget.period_type != "ANNUAL"
            or parent_budget.requesting_department_id != department.id
            or parent_budget.category != payload.category
            or payload.period_start < parent_budget.period_start
            or payload.period_end > parent_budget.period_end
            or parent_budget.status == "CLOSED"
        ):
            raise HTTPException(status_code=422, detail="A quarterly child budget must fit within an annual budget for the same department and category.")
    duplicate = db.query(ProcurementBudget.id).filter(
        ProcurementBudget.budget_number == payload.budget_number.strip()
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="Budget number already exists.")
    budget = ProcurementBudget(
        budget_number=payload.budget_number.strip(),
        parent_budget_id=payload.parent_budget_id,
        requesting_department_id=payload.requesting_department_id,
        period_type=payload.period_type,
        period_start=payload.period_start,
        period_end=payload.period_end,
        category=payload.category,
        total_amount_paise=payload.total_amount_paise,
        warning_threshold_pct=payload.warning_threshold_pct,
        status="DRAFT",
        created_by_id=current_user.id,
    )
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


@router.get("/budgets", response_model=list[ProcurementBudgetResponse])
def list_procurement_budgets(
    requesting_department_id: Optional[int] = None,
    category: Optional[str] = Query(default=None, pattern="^(PHARMACY|LABORATORY|GENERAL_SUPPLIES|EQUIPMENT|SERVICES|OTHER)$"),
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
    budget_status: Optional[str] = Query(default=None, alias="status", pattern="^(DRAFT|ACTIVE|CLOSED)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:read")),
):
    query = db.query(ProcurementBudget)
    if not current_user.is_superuser:
        assigned_department_ids = {
            row[0] for row in db.query(UserRole.department_id).filter(
                UserRole.user_id == current_user.id,
                UserRole.department_id.is_not(None),
            ).distinct().all()
            if row[0] is not None and user_has_department_access(db, current_user, row[0])
        }
        query = query.filter(ProcurementBudget.requesting_department_id.in_(assigned_department_ids or [-1]))
    if requesting_department_id is not None:
        query = query.filter(ProcurementBudget.requesting_department_id == requesting_department_id)
    if category is not None:
        query = query.filter(ProcurementBudget.category == category)
    if period_start is not None:
        query = query.filter(ProcurementBudget.period_end >= period_start)
    if period_end is not None:
        query = query.filter(ProcurementBudget.period_start <= period_end)
    if budget_status is not None:
        query = query.filter(ProcurementBudget.status == budget_status)
    return query.order_by(ProcurementBudget.period_start.desc(), ProcurementBudget.requesting_department_id, ProcurementBudget.category).all()


@router.get("/budgets/{budget_id}", response_model=ProcurementBudgetResponse)
def get_procurement_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:read")),
):
    budget = db.get(ProcurementBudget, budget_id)
    if budget is None:
        raise HTTPException(status_code=404, detail="Procurement budget not found.")
    _ensure_budget_department_access(db, budget, current_user)
    return budget


@router.post("/budgets/{budget_id}/activate", response_model=ProcurementBudgetResponse)
def activate_procurement_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:approve")),
):
    budget = db.query(ProcurementBudget).filter(
        ProcurementBudget.id == budget_id
    ).with_for_update().one_or_none()
    if budget is None:
        raise HTTPException(status_code=404, detail="Procurement budget not found.")
    _ensure_budget_department_access(db, budget, current_user)
    if budget.status != "DRAFT":
        raise HTTPException(status_code=409, detail="Only draft budgets can be activated.")
    if budget.created_by_id == current_user.id:
        raise HTTPException(status_code=409, detail="The budget creator cannot activate their own budget.")
    # Serialize activation attempts for the same department so concurrent requests
    # cannot create overlapping active allocations.
    department = db.query(Department).filter(
        Department.id == budget.requesting_department_id
    ).with_for_update().one_or_none()
    if department is None:
        raise HTTPException(status_code=409, detail="The budget department no longer exists.")
    if budget.period_type == "QUARTERLY" and budget.parent_budget_id is not None:
        parent = db.query(ProcurementBudget).filter(
            ProcurementBudget.id == budget.parent_budget_id
        ).with_for_update().one_or_none()
        if (
            parent is None or parent.status != "ACTIVE"
            or parent.period_type != "ANNUAL"
            or parent.requesting_department_id != budget.requesting_department_id
            or parent.category != budget.category
            or budget.period_start < parent.period_start
            or budget.period_end > parent.period_end
        ):
            raise HTTPException(status_code=409, detail="The parent annual budget must be active and cover this quarterly allocation.")
        overlapping = db.query(ProcurementBudget.id).filter(
            ProcurementBudget.id != budget.id,
            ProcurementBudget.parent_budget_id == parent.id,
            ProcurementBudget.status == "ACTIVE",
            ProcurementBudget.period_start <= budget.period_end,
            ProcurementBudget.period_end >= budget.period_start,
        ).first()
        parent_available, _ = _budget_available_paise(db, parent)
        if overlapping:
            raise HTTPException(status_code=409, detail="An active quarterly allocation already overlaps this period.")
        if budget.total_amount_paise > parent_available:
            raise HTTPException(status_code=409, detail="The quarterly allocation exceeds annual capacity after existing receipts, commitments and other quarterly earmarks.")
    else:
        overlapping = db.query(ProcurementBudget.id).filter(
            ProcurementBudget.id != budget.id,
            ProcurementBudget.parent_budget_id.is_(None),
            ProcurementBudget.requesting_department_id == budget.requesting_department_id,
            ProcurementBudget.category == budget.category,
            ProcurementBudget.status == "ACTIVE",
            ProcurementBudget.period_start <= budget.period_end,
            ProcurementBudget.period_end >= budget.period_start,
        ).first()
        if overlapping:
            raise HTTPException(status_code=409, detail="An active root budget already overlaps this department, category and period.")
    budget.status = "ACTIVE"
    budget.updated_by_id = current_user.id
    db.commit()
    db.refresh(budget)
    return budget


@router.post(
    "/budgets/{budget_id}/revisions",
    response_model=ProcurementBudgetRevisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_procurement_budget_revision(
    budget_id: int,
    payload: ProcurementBudgetRevisionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:write")),
):
    budget = db.query(ProcurementBudget).filter(
        ProcurementBudget.id == budget_id
    ).with_for_update().one_or_none()
    if budget is None:
        raise HTTPException(status_code=404, detail="Procurement budget not found.")
    _ensure_budget_department_access(db, budget, current_user)
    if budget.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Only active budgets can be revised.")
    pending = db.query(ProcurementBudgetRevision.id).filter(
        ProcurementBudgetRevision.budget_id == budget.id,
        ProcurementBudgetRevision.status == "PENDING",
    ).first()
    if pending:
        raise HTTPException(status_code=409, detail="A budget revision is already awaiting review.")
    latest_number = db.query(func.max(ProcurementBudgetRevision.revision_number)).filter(
        ProcurementBudgetRevision.budget_id == budget.id
    ).scalar() or 0
    revision = ProcurementBudgetRevision(
        budget_id=budget.id,
        revision_number=latest_number + 1,
        prior_amount_paise=budget.total_amount_paise,
        proposed_amount_paise=payload.proposed_amount_paise,
        reason=payload.reason.strip(),
        status="PENDING",
        created_by_id=current_user.id,
    )
    db.add(revision)
    db.commit()
    db.refresh(revision)
    return revision


@router.get(
    "/budgets/{budget_id}/revisions",
    response_model=list[ProcurementBudgetRevisionResponse],
)
def list_procurement_budget_revisions(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:read")),
):
    budget = db.get(ProcurementBudget, budget_id)
    if budget is None:
        raise HTTPException(status_code=404, detail="Procurement budget not found.")
    _ensure_budget_department_access(db, budget, current_user)
    return db.query(ProcurementBudgetRevision).filter(
        ProcurementBudgetRevision.budget_id == budget_id
    ).order_by(ProcurementBudgetRevision.revision_number.asc()).all()


@router.patch(
    "/budgets/{budget_id}/revisions/{revision_id}/review",
    response_model=ProcurementBudgetRevisionResponse,
)
def review_procurement_budget_revision(
    budget_id: int,
    revision_id: int,
    payload: ProcurementBudgetRevisionReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:approve")),
):
    budget = db.query(ProcurementBudget).filter(
        ProcurementBudget.id == budget_id
    ).with_for_update().one_or_none()
    if budget is None:
        raise HTTPException(status_code=404, detail="Procurement budget not found.")
    _ensure_budget_department_access(db, budget, current_user)
    revision = db.query(ProcurementBudgetRevision).filter(
        ProcurementBudgetRevision.id == revision_id,
        ProcurementBudgetRevision.budget_id == budget_id,
    ).with_for_update().one_or_none()
    if revision is None or revision.status != "PENDING":
        raise HTTPException(status_code=409, detail="Pending budget revision not found.")
    if revision.created_by_id == current_user.id:
        raise HTTPException(status_code=409, detail="The revision requester cannot review their own budget change.")
    if budget.status != "ACTIVE" or revision.prior_amount_paise != budget.total_amount_paise:
        raise HTTPException(status_code=409, detail="The budget changed after this revision was requested.")
    revision.reviewed_by_id = current_user.id
    revision.reviewed_at = datetime.now(timezone.utc)
    revision.review_notes = payload.review_notes.strip()
    revision.status = "APPROVED" if payload.approved else "REJECTED"
    if payload.approved:
        current_available, _ = _budget_available_paise(db, budget)
        already_committed_or_earmarked = budget.total_amount_paise - current_available
        if already_committed_or_earmarked > revision.proposed_amount_paise:
            raise HTTPException(status_code=409, detail="The revised budget cannot be lower than existing commitments, accepted receipts and active quarterly allocations.")
        if budget.period_type == "QUARTERLY" and budget.parent_budget_id is not None:
            parent = db.query(ProcurementBudget).filter(
                ProcurementBudget.id == budget.parent_budget_id
            ).with_for_update().one_or_none()
            if parent is None or parent.status != "ACTIVE":
                raise HTTPException(status_code=409, detail="The quarterly budget's annual parent is not active.")
            parent_available, _ = _budget_available_paise(db, parent)
            child_totals = _budget_ledger_totals(db, budget.id)
            child_used = child_totals["reserved_open_paise"] + child_totals["received_consumption_paise"]
            current_child_unspent = max(budget.total_amount_paise - child_used, 0)
            proposed_child_unspent = max(revision.proposed_amount_paise - child_used, 0)
            if proposed_child_unspent > parent_available + current_child_unspent:
                raise HTTPException(status_code=409, detail="The revised quarterly allocation would exceed the remaining annual parent capacity.")
        budget.total_amount_paise = revision.proposed_amount_paise
        budget.updated_by_id = current_user.id
    db.commit()
    db.refresh(revision)
    return revision


@router.post("/budgets/{budget_id}/close", response_model=ProcurementBudgetResponse)
def close_procurement_budget(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:approve")),
):
    budget = db.query(ProcurementBudget).filter(
        ProcurementBudget.id == budget_id
    ).with_for_update().one_or_none()
    if budget is None:
        raise HTTPException(status_code=404, detail="Procurement budget not found.")
    _ensure_budget_department_access(db, budget, current_user)
    if budget.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Only active budgets can be closed.")
    pending = db.query(ProcurementBudgetRevision.id).filter(
        ProcurementBudgetRevision.budget_id == budget.id,
        ProcurementBudgetRevision.status == "PENDING",
    ).first()
    if pending:
        raise HTTPException(status_code=409, detail="Resolve pending budget revisions before closing the budget.")
    ledger_totals = _budget_ledger_totals(db, budget.id)
    if ledger_totals["reserved_open_paise"] > 0:
        raise HTTPException(status_code=409, detail="Release or receive all outstanding purchase-order commitments before closing the budget.")
    active_children = db.query(ProcurementBudget.id).filter(
        ProcurementBudget.parent_budget_id == budget.id,
        ProcurementBudget.status == "ACTIVE",
    ).first()
    if active_children:
        raise HTTPException(status_code=409, detail="Close active quarterly child budgets before closing the annual budget.")
    budget.status = "CLOSED"
    budget.updated_by_id = current_user.id
    db.commit()
    db.refresh(budget)
    return budget


@router.get("/budgets/{budget_id}/utilization")
def get_procurement_budget_utilization(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:read")),
):
    budget = db.query(ProcurementBudget).filter(
        ProcurementBudget.id == budget_id
    ).one_or_none()
    if budget is None:
        raise HTTPException(status_code=404, detail="Procurement budget not found.")
    _ensure_budget_department_access(db, budget, current_user)
    totals = _budget_ledger_totals(db, budget.id)
    committed_and_consumed = totals["reserved_open_paise"] + totals["received_consumption_paise"]
    available, earmarked_for_active_quarters = _budget_available_paise(db, budget)
    invoice_actuals = _budget_invoice_actuals(db, budget)
    budget_engaged_paise = committed_and_consumed + earmarked_for_active_quarters
    utilization_pct = (
        round((budget_engaged_paise * 100) / budget.total_amount_paise, 2)
        if budget.total_amount_paise > 0 else None
    )
    if available < 0:
        alert = "OVER_BUDGET"
    elif utilization_pct is not None and utilization_pct >= budget.warning_threshold_pct:
        alert = "WARNING"
    else:
        alert = "NORMAL"
    return {
        "budget_id": budget.id,
        "budget_number": budget.budget_number,
        "requesting_department_id": budget.requesting_department_id,
        "category": budget.category,
        "period_start": budget.period_start,
        "period_end": budget.period_end,
        "status": budget.status,
        "total_amount_paise": budget.total_amount_paise,
        "reserved_open_commitment_paise": totals["reserved_open_paise"],
        "received_consumption_paise": totals["received_consumption_paise"],
        "committed_and_consumed_paise": committed_and_consumed,
        "budget_engaged_paise": budget_engaged_paise,
        "available_paise": available,
        "allocated_to_active_quarters_paise": earmarked_for_active_quarters,
        "utilization_pct": utilization_pct,
        "warning_threshold_pct": budget.warning_threshold_pct,
        "alert": alert,
        **invoice_actuals,
        "invoice_actuals_included": True,
        "invoice_actuals_note": "Only matched-approved and paid invoice lines linked to budget-mapped PO lines are included. Header discounts are allocated proportionally across invoice lines. Invoice actuals are informational and are not added again to budget consumption.",
    }


@router.get("/budgets/{budget_id}/movements")
def list_procurement_budget_movements(
    budget_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:read")),
):
    budget = db.get(ProcurementBudget, budget_id)
    if budget is None:
        raise HTTPException(status_code=404, detail="Procurement budget not found.")
    _ensure_budget_department_access(db, budget, current_user)
    budget_ids = [budget.id]
    if budget.period_type == "ANNUAL" and budget.parent_budget_id is None:
        budget_ids.extend(row[0] for row in db.query(ProcurementBudget.id).filter(
            ProcurementBudget.parent_budget_id == budget.id
        ).all())
    rows = db.query(ProcurementBudgetMovement).filter(
        ProcurementBudgetMovement.budget_id.in_(budget_ids)
    ).order_by(ProcurementBudgetMovement.created_at.asc(), ProcurementBudgetMovement.id.asc()).all()
    return [{
        "id": row.id,
        "budget_id": row.budget_id,
        "po_id": row.po_id,
        "po_item_id": row.po_item_id,
        "grn_item_id": row.grn_item_id,
        "movement_type": row.movement_type,
        "amount_paise": row.amount_paise,
        "reference_key": row.reference_key,
        "notes": row.notes,
        "actor_user_id": row.actor_user_id,
        "created_at": row.created_at,
    } for row in rows]


# --- Supplier contract lifecycle and negotiated rates ---

# --- Supplier regulatory compliance documents ---

def _assert_supplier_procurement_eligible(vendor: VendorMaster) -> None:
    if not vendor.is_active:
        raise HTTPException(status_code=409, detail="Supplier is deactivated and cannot be used for new procurement.")
    if vendor.is_suspended:
        raise HTTPException(status_code=409, detail={
            "message": "Supplier is suspended and cannot be used for new procurement.",
            "vendor_id": vendor.id,
            "suspension_reason": vendor.suspension_reason,
            "suspended_at": vendor.suspended_at,
        })


def _assert_supplier_compliance_ready(db: Session, vendor: VendorMaster) -> None:
    category = vendor.category.value if hasattr(vendor.category, "value") else str(vendor.category)
    policies = db.query(SupplierCompliancePolicy).filter(
        SupplierCompliancePolicy.vendor_category == category,
        SupplierCompliancePolicy.is_required.is_(True),
    ).order_by(SupplierCompliancePolicy.document_type.asc()).all()
    if not policies:
        return
    today = datetime.now(timezone.utc).date()
    failures = []
    for policy in policies:
        valid_document = db.query(SupplierComplianceDocument.id).filter(
            SupplierComplianceDocument.vendor_id == vendor.id,
            SupplierComplianceDocument.document_type == policy.document_type,
            SupplierComplianceDocument.status == "VERIFIED",
            or_(SupplierComplianceDocument.issue_date.is_(None), SupplierComplianceDocument.issue_date <= today),
            or_(
                SupplierComplianceDocument.expiry_date.is_(None),
                SupplierComplianceDocument.expiry_date >= today,
            ),
        ).order_by(
            SupplierComplianceDocument.verified_at.desc(),
            SupplierComplianceDocument.uploaded_at.desc(),
        ).first()
        if valid_document is None:
            failures.append(policy.document_type)
    if failures:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Supplier does not satisfy the configured mandatory compliance requirements.",
                "vendor_id": vendor.id,
                "vendor_category": category,
                "missing_or_invalid_documents": failures,
            },
        )


_SUPPLIER_COMPLIANCE_TYPES = {
    "GST_REGISTRATION", "PAN", "DRUG_LICENSE", "WHO_GMP", "ISO_CERTIFICATE",
    "FSSAI_LICENSE", "BIOMEDICAL_AUTHORIZATION", "FIRE_SAFETY_CERTIFICATE",
    "EQUIPMENT_CALIBRATION", "OTHER",
}


def _supplier_compliance_status(document: SupplierComplianceDocument, today: date) -> str:
    if document.status == "PENDING_VERIFICATION":
        return "PENDING_VERIFICATION"
    if document.status == "REJECTED":
        return "REJECTED"
    if document.issue_date is not None and document.issue_date > today:
        return "NOT_YET_VALID"
    if document.expiry_date is not None:
        if document.expiry_date < today:
            return "EXPIRED"
        if document.expiry_date <= today + timedelta(days=30):
            return "EXPIRING_SOON"
    return "VALID"



@router.get("/analytics/supplier-compliance")
def get_supplier_compliance_analytics(
    vendor_category: Optional[str] = Query(default=None),
    active_only: bool = True,
    search: Optional[str] = Query(default=None, min_length=1, max_length=150),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    """Policy-aware supplier compliance dashboard; all data remains tenant-local."""
    today = datetime.now(timezone.utc).date()
    category = vendor_category.strip().upper() if vendor_category else None
    if category is not None and category not in {item.value for item in VendorCategoryEnum}:
        raise HTTPException(status_code=422, detail="Unsupported supplier category.")

    vendor_query = db.query(VendorMaster)
    if category is not None:
        vendor_query = vendor_query.filter(VendorMaster.category == category)
    if active_only:
        vendor_query = vendor_query.filter(VendorMaster.is_active.is_(True))
    if search:
        term = f"%{search.strip()}%"
        vendor_query = vendor_query.filter(or_(
            VendorMaster.name.ilike(term), VendorMaster.code.ilike(term),
            VendorMaster.email.ilike(term),
        ))
    total_suppliers = vendor_query.count()
    vendors = vendor_query.order_by(VendorMaster.name.asc(), VendorMaster.id.asc()).offset(offset).limit(limit).all()
    vendor_ids = [vendor.id for vendor in vendors]
    categories = sorted({v.category.value if hasattr(v.category, "value") else str(v.category) for v in vendors})

    policies = db.query(SupplierCompliancePolicy).filter(
        SupplierCompliancePolicy.is_required.is_(True),
        SupplierCompliancePolicy.vendor_category.in_(categories) if categories else False,
    ).order_by(SupplierCompliancePolicy.vendor_category.asc(),
               SupplierCompliancePolicy.document_type.asc()).all()
    policy_map = {}
    for policy in policies:
        policy_map.setdefault(policy.vendor_category, []).append(policy.document_type)

    documents = db.query(SupplierComplianceDocument).filter(
        SupplierComplianceDocument.vendor_id.in_(vendor_ids)
    ).order_by(SupplierComplianceDocument.uploaded_at.desc(),
               SupplierComplianceDocument.id.desc()).all() if vendor_ids else []
    docs_by_vendor = {}
    for document in documents:
        docs_by_vendor.setdefault(document.vendor_id, []).append(document)

    document_counts = {
        "total": len(documents),
        "pending_verification": sum(d.status == "PENDING_VERIFICATION" for d in documents),
        "verified": sum(d.status == "VERIFIED" for d in documents),
        "rejected": sum(d.status == "REJECTED" for d in documents),
        "expired": 0,
        "not_yet_valid": 0,
        "expiring_within_30_days": 0,
        "expiring_within_60_days": 0,
        "expiring_within_90_days": 0,
    }
    for document in documents:
        if document.status != "VERIFIED":
            continue
        if document.issue_date is not None and document.issue_date > today:
            document_counts["not_yet_valid"] += 1
            continue
        if document.expiry_date is None:
            continue
        days_left = (document.expiry_date - today).days
        if days_left < 0:
            document_counts["expired"] += 1
        else:
            if days_left <= 30:
                document_counts["expiring_within_30_days"] += 1
            if days_left <= 60:
                document_counts["expiring_within_60_days"] += 1
            if days_left <= 90:
                document_counts["expiring_within_90_days"] += 1

    supplier_rows = []
    category_totals = {}
    configured_supplier_count = 0
    compliant_supplier_count = 0
    blocked_supplier_count = 0
    unconfigured_supplier_count = 0
    total_required_obligations = 0
    satisfied_required_obligations = 0
    turnaround_hours = []

    for vendor in vendors:
        vendor_category_code = vendor.category.value if hasattr(vendor.category, "value") else str(vendor.category)
        required_types = policy_map.get(vendor_category_code, [])
        vendor_docs = docs_by_vendor.get(vendor.id, [])
        valid_by_type = {}
        for document in vendor_docs:
            if document.status != "VERIFIED":
                continue
            if document.issue_date is not None and document.issue_date > today:
                continue
            if document.expiry_date is not None and document.expiry_date < today:
                continue
            valid_by_type.setdefault(document.document_type, document)
        missing = [kind for kind in required_types if kind not in valid_by_type]
        if not required_types:
            compliance_state = "NOT_CONFIGURED"
            unconfigured_supplier_count += 1
            score = None
        else:
            configured_supplier_count += 1
            total_required_obligations += len(required_types)
            satisfied = len(required_types) - len(missing)
            satisfied_required_obligations += satisfied
            score = round((satisfied / len(required_types)) * 100, 2)
            compliance_state = "BLOCKED" if missing else "COMPLIANT"
            if missing:
                blocked_supplier_count += 1
            else:
                compliant_supplier_count += 1
        nearest_expiry = min(
            (d.expiry_date for d in vendor_docs
             if d.status == "VERIFIED" and d.expiry_date is not None
             and d.expiry_date >= today
             and (d.issue_date is None or d.issue_date <= today)),
            default=None,
        )
        category_row = category_totals.setdefault(vendor_category_code, {
            "vendor_count": 0, "compliant": 0, "blocked": 0,
            "not_configured": 0, "required_obligations": 0,
            "satisfied_obligations": 0,
        })
        category_row["vendor_count"] += 1
        if compliance_state == "COMPLIANT":
            category_row["compliant"] += 1
        elif compliance_state == "BLOCKED":
            category_row["blocked"] += 1
        else:
            category_row["not_configured"] += 1
        category_row["required_obligations"] += len(required_types)
        category_row["satisfied_obligations"] += len(required_types) - len(missing)
        supplier_rows.append({
            "vendor_id": vendor.id, "vendor_code": vendor.code, "vendor_name": vendor.name,
            "vendor_category": vendor_category_code, "is_active": vendor.is_active,
            "compliance_state": compliance_state, "compliance_score_pct": score,
            "required_document_types": required_types,
            "missing_or_invalid_document_types": missing,
            "valid_required_document_count": len(required_types) - len(missing),
            "required_document_count": len(required_types),
            "document_count": len(vendor_docs), "nearest_verified_expiry_date": nearest_expiry,
        })

    for document in documents:
        if document.status == "VERIFIED" and document.verified_at is not None and document.uploaded_at is not None:
            seconds = (document.verified_at - document.uploaded_at).total_seconds()
            if seconds >= 0:
                turnaround_hours.append(seconds / 3600)
    turnaround_hours.sort()
    median_turnaround = None
    if turnaround_hours:
        middle = len(turnaround_hours) // 2
        median_turnaround = (
            turnaround_hours[middle] if len(turnaround_hours) % 2
            else (turnaround_hours[middle - 1] + turnaround_hours[middle]) / 2
        )

    return {
        "as_of_date": today,
        "filters": {"vendor_category": category, "active_only": active_only, "search": search},
        "pagination": {"total": total_suppliers, "limit": limit, "offset": offset,
                       "returned": len(vendors)},
        "supplier_summary": {
            "total": total_suppliers, "evaluated_on_page": len(vendors),
            "configured": configured_supplier_count, "compliant": compliant_supplier_count,
            "blocked": blocked_supplier_count, "not_configured": unconfigured_supplier_count,
        },
        "compliance_score_pct": (
            round(satisfied_required_obligations / total_required_obligations * 100, 2)
            if total_required_obligations else None
        ),
        "required_obligations": {
            "total": total_required_obligations, "satisfied": satisfied_required_obligations,
            "missing_or_invalid": total_required_obligations - satisfied_required_obligations,
        },
        "document_summary": document_counts,
        "verification_turnaround": {
            "sample_count": len(turnaround_hours),
            "average_hours": round(sum(turnaround_hours) / len(turnaround_hours), 2) if turnaround_hours else None,
            "median_hours": round(median_turnaround, 2) if median_turnaround is not None else None,
        },
        "by_supplier_category": [
            {"vendor_category": key, **value}
            for key, value in sorted(category_totals.items())
        ],
        "suppliers": supplier_rows,
        "definitions": {
            "blocked": "At least one currently required document type has no verified, currently valid document.",
            "not_configured": "No active mandatory document policy exists for this supplier category; this is not counted as compliant.",
            "compliance_score_pct": "Satisfied required document obligations divided by all required obligations for suppliers on this page.",
            "expiry_counts": "Verified documents only; 30/60/90-day buckets are cumulative and may overlap.",
            "verification_turnaround": "Elapsed hours from upload to verification for verified documents on this page; excludes negative durations.",
            "scope": "Supplier compliance is evaluated from tenant-local supplier, policy and document records. No historical compliance state is inferred.",
        },
    }


@router.get("/analytics/supplier-risk-register")
def get_supplier_risk_register(
    vendor_category: Optional[str] = Query(default=None),
    risk_level: Optional[str] = Query(default=None),
    active_only: bool = True,
    include_no_open_orders: bool = True,
    within_days: int = Query(default=90, ge=0, le=730),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    """Consolidated supplier risk register across compliance, contracts and open POs."""
    today = datetime.now(timezone.utc).date()
    category = vendor_category.strip().upper() if vendor_category else None
    if category is not None and category not in {item.value for item in VendorCategoryEnum}:
        raise HTTPException(status_code=422, detail="Unsupported supplier category.")
    requested_risk = risk_level.strip().upper() if risk_level else None
    allowed_risks = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "NOT_EVALUATED"}
    if requested_risk is not None and requested_risk not in allowed_risks:
        raise HTTPException(status_code=422, detail="Unsupported risk level.")

    vendor_query = db.query(VendorMaster)
    if category is not None:
        vendor_query = vendor_query.filter(VendorMaster.category == category)
    if active_only:
        vendor_query = vendor_query.filter(VendorMaster.is_active.is_(True))
    total_vendor_count = vendor_query.count()
    all_vendors = vendor_query.order_by(
        VendorMaster.name.asc(), VendorMaster.id.asc()
    ).offset(offset).limit(limit).all()
    vendor_ids = [vendor.id for vendor in all_vendors]
    category_codes = sorted({
        vendor.category.value if hasattr(vendor.category, "value") else str(vendor.category)
        for vendor in all_vendors
    })
    required_policies = db.query(SupplierCompliancePolicy).filter(
        SupplierCompliancePolicy.is_required.is_(True),
        SupplierCompliancePolicy.vendor_category.in_(category_codes) if category_codes else False,
    ).all()
    required_by_category = {}
    for policy in required_policies:
        required_by_category.setdefault(policy.vendor_category, []).append(policy.document_type)

    docs = db.query(SupplierComplianceDocument).filter(
        SupplierComplianceDocument.vendor_id.in_(vendor_ids)
    ).all() if vendor_ids else []
    docs_by_vendor = {}
    for document in docs:
        docs_by_vendor.setdefault(document.vendor_id, []).append(document)

    contracts = db.query(SupplierContract).filter(
        SupplierContract.vendor_id.in_(vendor_ids),
        SupplierContract.status == "ACTIVE",
    ).all() if vendor_ids else []
    contracts_by_vendor = {}
    for contract in contracts:
        contracts_by_vendor.setdefault(contract.vendor_id, []).append(contract)

    open_statuses = [
        POStatusEnum.SUBMITTED, POStatusEnum.APPROVED, POStatusEnum.PARTIALLY_RECEIVED
    ]
    open_pos = db.query(PurchaseOrder).filter(
        PurchaseOrder.vendor_id.in_(vendor_ids),
        PurchaseOrder.status.in_(open_statuses),
    ).all() if vendor_ids else []
    pos_by_vendor = {}
    for po in open_pos:
        pos_by_vendor.setdefault(po.vendor_id, []).append(po)

    rows = []
    for vendor in all_vendors:
        vendor_category_code = vendor.category.value if hasattr(vendor.category, "value") else str(vendor.category)
        required_types = required_by_category.get(vendor_category_code, [])
        vendor_docs = docs_by_vendor.get(vendor.id, [])
        valid_types = set()
        missing_types = []
        for document in vendor_docs:
            if (document.status == "VERIFIED"
                and (document.issue_date is None or document.issue_date <= today)
                and (document.expiry_date is None or document.expiry_date >= today)):
                valid_types.add(document.document_type)
        missing_types = [kind for kind in required_types if kind not in valid_types]
        compliance_state = (
            "NOT_CONFIGURED" if not required_types
            else ("BLOCKED" if missing_types else "COMPLIANT")
        )
        nearest_doc_expiry = min((
            document.expiry_date for document in vendor_docs
            if document.status == "VERIFIED" and document.expiry_date is not None
            and document.expiry_date >= today
            and (document.issue_date is None or document.issue_date <= today)
        ), default=None)

        vendor_contracts = contracts_by_vendor.get(vendor.id, [])
        expired_contracts = [
            contract for contract in vendor_contracts if contract.valid_to < today
        ]
        expiring_contracts = [
            contract for contract in vendor_contracts
            if today <= contract.valid_to <= today + timedelta(days=within_days)
        ]
        nearest_contract_expiry = min(
            (contract.valid_to for contract in vendor_contracts if contract.valid_to >= today),
            default=None,
        )
        vendor_pos = pos_by_vendor.get(vendor.id, [])
        overdue_pos = [
            po for po in vendor_pos
            if po.delivery_due_date is not None and po.delivery_due_date.date() < today
        ]
        open_value = sum(int(po.total_amount_paise or 0) for po in vendor_pos)
        has_open_exposure = bool(vendor_pos)
        if not include_no_open_orders and not has_open_exposure:
            continue

        if (vendor.is_suspended and has_open_exposure) or (compliance_state == "BLOCKED" and has_open_exposure):
            level = "CRITICAL"
        elif vendor.is_suspended or compliance_state == "BLOCKED" or expired_contracts or overdue_pos:
            level = "HIGH"
        elif (
            (nearest_doc_expiry is not None and nearest_doc_expiry <= today + timedelta(days=30))
            or expiring_contracts
        ):
            level = "MEDIUM"
        elif compliance_state == "NOT_CONFIGURED":
            level = "NOT_EVALUATED"
        else:
            level = "LOW"

        rows.append({
            "vendor_id": vendor.id, "vendor_code": vendor.code,
            "vendor_name": vendor.name, "vendor_category": vendor_category_code,
            "is_active": vendor.is_active, "is_suspended": vendor.is_suspended,
            "suspension_reason": vendor.suspension_reason, "suspended_at": vendor.suspended_at,
            "risk_level": level, "compliance_state": compliance_state,
            "missing_or_invalid_document_types": missing_types,
            "nearest_verified_document_expiry": nearest_doc_expiry,
            "active_contract_count": len(vendor_contracts),
            "expired_active_contract_count": len(expired_contracts),
            "contracts_expiring_within_window": len(expiring_contracts),
            "nearest_active_contract_expiry": nearest_contract_expiry,
            "open_purchase_order_count": len(vendor_pos),
            "overdue_purchase_order_count": len(overdue_pos),
            "open_purchase_order_value_paise": open_value,
            "currency": "INR",
            "risk_reasons": [
                * (["Supplier is suspended: " + vendor.suspension_reason] if vendor.is_suspended and vendor.suspension_reason else (["Supplier is suspended."] if vendor.is_suspended else [])),
                * (["Mandatory supplier compliance documents are missing or invalid."] if missing_types else []),
                * (["Open purchase orders exist while mandatory compliance is blocked."] if missing_types and has_open_exposure else []),
                * ([f"{len(expired_contracts)} active contract(s) have passed their validity end date."] if expired_contracts else []),
                * ([f"{len(overdue_pos)} open purchase order(s) are past delivery due date."] if overdue_pos else []),
                * ([f"{len(expiring_contracts)} active contract(s) expire within the selected window."] if expiring_contracts else []),
                * (["No mandatory compliance policy is configured for this supplier category."] if compliance_state == "NOT_CONFIGURED" else []),
            ],
        })

    if requested_risk:
        rows = [row for row in rows if row["risk_level"] == requested_risk]
    risk_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "NOT_EVALUATED": 4}
    rows.sort(key=lambda row: (
        risk_order[row["risk_level"]],
        row["vendor_name"].lower(),
        row["vendor_id"],
    ))
    total = len(rows)
    summary = {
        level.lower(): sum(row["risk_level"] == level for row in rows)
        for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "NOT_EVALUATED")
    }
    return {
        "as_of_date": today,
        "filters": {
            "vendor_category": category, "risk_level": requested_risk,
            "active_only": active_only, "include_no_open_orders": include_no_open_orders,
            "contract_expiry_window_days": within_days,
        },
        "summary": {
            "supplier_count_after_risk_filter_on_page": total,
            "suppliers_evaluated_on_page": len(all_vendors),
            "critical_count": summary["critical"], "high_count": summary["high"],
            "medium_count": summary["medium"], "low_count": summary["low"],
            "not_evaluated_count": summary["not_evaluated"],
            "suppliers_with_open_pos": sum(row["open_purchase_order_count"] > 0 for row in rows),
            "overdue_open_po_count": sum(row["overdue_purchase_order_count"] for row in rows),
            "open_po_exposure_paise": sum(row["open_purchase_order_value_paise"] for row in rows),
        },
        "pagination": {
            "total_suppliers_before_risk_filter": total_vendor_count,
            "limit": limit, "offset": offset,
            "evaluated_on_page": len(all_vendors),
            "returned_after_risk_filter": len(rows),
        },
        "suppliers": rows,
        "definitions": {
            "critical": "Supplier is suspended with open PO exposure, or mandatory compliance is blocked with at least one open purchase order.",
            "high": "Supplier is suspended, mandatory compliance is blocked, an active contract is past its validity end date, or an open PO is overdue.",
            "medium": "A verified document expires within 30 days or an active contract expires within the selected contract window.",
            "low": "Configured compliance obligations are satisfied and no higher-severity condition was found.",
            "not_evaluated": "No mandatory policy exists for the supplier category; this is not a compliant rating.",
            "open_po_value": "Sum of tax-inclusive totals for SUBMITTED, APPROVED and PARTIALLY_RECEIVED purchase orders; not an accounts-payable balance.",
            "contract_expiry": "Uses ACTIVE contract records and their valid_to date; it does not mutate contract status.",
            "scope": "Risk classification is an operational triage indicator, not a legal or creditworthiness determination.",
            "pagination": "Supplier rows and summary metrics are computed only for the requested vendor page; risk_level and include_no_open_orders filters are applied to that page.",
        },
    }


@router.get("/supplier-compliance/policies", response_model=list[SupplierCompliancePolicyResponse])
def list_supplier_compliance_policies(
    vendor_category: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    query = db.query(SupplierCompliancePolicy)
    if vendor_category is not None:
        category = vendor_category.strip().upper()
        if category not in {item.value for item in VendorCategoryEnum}:
            raise HTTPException(status_code=422, detail="Unsupported supplier category.")
        query = query.filter(SupplierCompliancePolicy.vendor_category == category)
    return query.order_by(
        SupplierCompliancePolicy.vendor_category.asc(),
        SupplierCompliancePolicy.document_type.asc(),
    ).all()


@router.put(
    "/supplier-compliance/policies/{vendor_category}/{document_type}",
    response_model=SupplierCompliancePolicyResponse,
)
def upsert_supplier_compliance_policy(
    vendor_category: str,
    document_type: str,
    payload: SupplierCompliancePolicyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:approve")),
):
    category = vendor_category.strip().upper()
    kind = document_type.strip().upper()
    if category not in {item.value for item in VendorCategoryEnum}:
        raise HTTPException(status_code=422, detail="Unsupported supplier category.")
    if kind not in _SUPPLIER_COMPLIANCE_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported supplier compliance document type.")
    policy = db.query(SupplierCompliancePolicy).filter(
        SupplierCompliancePolicy.vendor_category == category,
        SupplierCompliancePolicy.document_type == kind,
    ).with_for_update().one_or_none()
    previous_value = policy.is_required if policy is not None else None
    if policy is None:
        policy = SupplierCompliancePolicy(
            vendor_category=category, document_type=kind,
            is_required=payload.is_required, updated_by_id=current_user.id,
        )
        db.add(policy)
        db.flush()
    else:
        policy.is_required = payload.is_required
        policy.updated_by_id = current_user.id
    if previous_value != payload.is_required:
        db.add(SupplierCompliancePolicyAudit(
            policy_id=policy.id,
            vendor_category=category,
            document_type=kind,
            previous_is_required=previous_value,
            new_is_required=payload.is_required,
            changed_by_id=current_user.id,
            changed_by_email=current_user.email,
        ))
    db.commit()
    db.refresh(policy)
    return policy



@router.get("/supplier-compliance/policies/{vendor_category}/{document_type}/history")
def list_supplier_compliance_policy_history(
    vendor_category: str,
    document_type: str,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    category = vendor_category.strip().upper()
    kind = document_type.strip().upper()
    if category not in {item.value for item in VendorCategoryEnum}:
        raise HTTPException(status_code=422, detail="Unsupported supplier category.")
    if kind not in _SUPPLIER_COMPLIANCE_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported supplier compliance document type.")
    return db.query(SupplierCompliancePolicyAudit).filter(
        SupplierCompliancePolicyAudit.vendor_category == category,
        SupplierCompliancePolicyAudit.document_type == kind,
    ).order_by(SupplierCompliancePolicyAudit.changed_at.desc(),
               SupplierCompliancePolicyAudit.id.desc()).all()


@router.post("/vendors/{vendor_id}/compliance-documents", status_code=status.HTTP_201_CREATED)
def upload_supplier_compliance_document(
    vendor_id: int,
    request: Request,
    document_type: str = Form(...),
    document_number: Optional[str] = Form(default=None),
    issuer: Optional[str] = Form(default=None),
    issue_date: Optional[date] = Form(default=None),
    expiry_date: Optional[date] = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:write")),
):
    vendor = db.get(VendorMaster, vendor_id)
    if vendor is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    kind = document_type.strip().upper()
    if kind not in _SUPPLIER_COMPLIANCE_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported supplier compliance document type.")
    if issue_date and expiry_date and expiry_date < issue_date:
        raise HTTPException(status_code=422, detail="Document expiry date cannot precede its issue date.")
    if document_number and len(document_number.strip()) > 100:
        raise HTTPException(status_code=422, detail="Document number must be 100 characters or fewer.")
    if issuer and len(issuer.strip()) > 160:
        raise HTTPException(status_code=422, detail="Issuer must be 160 characters or fewer.")
    tenant = resolve_tenant_context(request)
    try:
        storage_key, path = store_supplier_compliance_document(
            tenant.subdomain_slug, file.filename, file.file
        )
    finally:
        file.file.close()
    document = SupplierComplianceDocument(
        vendor_id=vendor.id, document_type=kind,
        document_number=document_number.strip() if document_number else None,
        issuer=issuer.strip() if issuer else None,
        issue_date=issue_date, expiry_date=expiry_date,
        storage_key=storage_key, original_filename=(file.filename or "supplier-document")[:255],
        status="PENDING_VERIFICATION", uploaded_by_id=current_user.id,
    )
    db.add(document)
    try:
        db.commit()
        db.refresh(document)
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    return {**SupplierComplianceDocumentResponse.model_validate(document).model_dump(),
            "compliance_status": "PENDING_VERIFICATION"}


@router.get("/vendors/{vendor_id}/compliance-documents")
def list_supplier_compliance_documents(
    vendor_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    if db.get(VendorMaster, vendor_id) is None:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    today = datetime.now(timezone.utc).date()
    documents = db.query(SupplierComplianceDocument).filter(
        SupplierComplianceDocument.vendor_id == vendor_id
    ).order_by(SupplierComplianceDocument.document_type.asc(),
               SupplierComplianceDocument.uploaded_at.desc()).all()
    return [{**SupplierComplianceDocumentResponse.model_validate(item).model_dump(),
             "compliance_status": _supplier_compliance_status(item, today)}
            for item in documents]


@router.patch("/vendors/{vendor_id}/compliance-documents/{document_id}/review")
def review_supplier_compliance_document(
    vendor_id: int,
    document_id: int,
    payload: SupplierComplianceDocumentReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:approve")),
):
    document = db.query(SupplierComplianceDocument).filter(
        SupplierComplianceDocument.id == document_id,
        SupplierComplianceDocument.vendor_id == vendor_id,
    ).with_for_update().one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Supplier compliance document not found.")
    if document.status != "PENDING_VERIFICATION":
        raise HTTPException(status_code=409, detail="Only pending compliance documents can be reviewed.")
    if document.uploaded_by_id == current_user.id:
        raise HTTPException(status_code=403, detail="The uploader cannot verify their own compliance document.")
    document.status = "VERIFIED" if payload.approved else "REJECTED"
    document.verified_by_id = current_user.id
    document.verified_at = datetime.now(timezone.utc)
    document.review_notes = payload.review_notes.strip()
    db.commit()
    db.refresh(document)
    today = datetime.now(timezone.utc).date()
    return {**SupplierComplianceDocumentResponse.model_validate(document).model_dump(),
            "compliance_status": _supplier_compliance_status(document, today)}


@router.get("/supplier-compliance/expiring")
def list_expiring_supplier_compliance_documents(
    within_days: int = Query(default=60, ge=0, le=730),
    include_expired: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    today = datetime.now(timezone.utc).date()
    upper = today + timedelta(days=within_days)
    query = db.query(SupplierComplianceDocument, VendorMaster).join(
        VendorMaster, VendorMaster.id == SupplierComplianceDocument.vendor_id
    ).filter(
        SupplierComplianceDocument.status == "VERIFIED",
        SupplierComplianceDocument.expiry_date.is_not(None),
        SupplierComplianceDocument.expiry_date <= upper,
    )
    if not include_expired:
        query = query.filter(SupplierComplianceDocument.expiry_date >= today)
    rows = query.order_by(SupplierComplianceDocument.expiry_date.asc()).all()
    return [{
        "document_id": document.id, "vendor_id": vendor.id,
        "vendor_name": vendor.name, "document_type": document.document_type,
        "document_number": document.document_number, "expiry_date": document.expiry_date,
        "days_remaining": (document.expiry_date - today).days,
        "compliance_status": _supplier_compliance_status(document, today),
    } for document, vendor in rows]


@router.get("/vendors/{vendor_id}/compliance-documents/{document_id}/download")
def download_supplier_compliance_document(
    vendor_id: int,
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:read")),
):
    tenant = resolve_tenant_context(request)
    row = db.query(SupplierComplianceDocument, VendorMaster).join(
        VendorMaster, VendorMaster.id == SupplierComplianceDocument.vendor_id
    ).filter(
        SupplierComplianceDocument.id == document_id,
        SupplierComplianceDocument.vendor_id == vendor_id,
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Supplier compliance document not found.")
    document, vendor = row
    path = resolve_supplier_compliance_document(tenant.subdomain_slug, document.storage_key)
    db.add(SupplierComplianceDocumentDownloadAudit(
        document_id=document.id, vendor_name=vendor.name,
        document_type=document.document_type, actor_user_id=current_user.id,
        actor_email=current_user.email,
    ))
    db.commit()
    media_type = {".pdf": "application/pdf", ".png": "image/png",
                  ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}[path.suffix.lower()]
    return FileResponse(path, media_type=media_type,
                        filename=f"{vendor.code}-{document.document_type}{path.suffix}")


@router.post("/supplier-contracts", response_model=SupplierContractResponse, status_code=status.HTTP_201_CREATED)
def create_supplier_contract(
    payload: SupplierContractCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:write")),
):
    vendor = db.get(VendorMaster, payload.vendor_id)
    if vendor is None or not vendor.is_active:
        raise HTTPException(status_code=404, detail="Active supplier not found.")
    contract = SupplierContract(
        vendor_id=vendor.id,
        contract_number=payload.contract_number.strip(),
        title=payload.title.strip(),
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
        renewal_notice_days=payload.renewal_notice_days,
        auto_renew=payload.auto_renew,
        payment_terms=payload.payment_terms,
        summary=payload.summary,
        status="DRAFT",
        created_by_id=current_user.id,
    )
    db.add(contract)
    db.flush()
    for rate in payload.rates:
        if rate.medication_id is not None and db.get(MedicationMaster, rate.medication_id) is None:
            raise HTTPException(status_code=404, detail=f"Medication {rate.medication_id} not found.")
        if db.query(ProcurementUnitOfMeasure.id).filter(
            ProcurementUnitOfMeasure.code == rate.uom_code
        ).one_or_none() is None:
            raise HTTPException(status_code=422, detail=f"Unknown contract rate UOM: {rate.uom_code}.")
        db.add(SupplierContractRate(**rate.model_dump(), contract_id=contract.id, created_by_id=current_user.id))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Contract number or rate scope already exists.") from exc
    return db.query(SupplierContract).options(selectinload(SupplierContract.rates)).filter(
        SupplierContract.id == contract.id
    ).one()


@router.get("/supplier-contracts", response_model=list[SupplierContractResponse])
def list_supplier_contracts(
    vendor_id: Optional[int] = None,
    status_filter: Optional[str] = Query(default=None, alias="status", pattern="^(DRAFT|PENDING_APPROVAL|ACTIVE|EXPIRED|TERMINATED)$"),
    expiring_within_days: Optional[int] = Query(default=None, ge=0, le=730),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    query = db.query(SupplierContract).options(selectinload(SupplierContract.rates))
    if vendor_id is not None:
        query = query.filter(SupplierContract.vendor_id == vendor_id)
    if status_filter:
        query = query.filter(SupplierContract.status == status_filter)
    if expiring_within_days is not None:
        today = datetime.now(timezone.utc).date()
        query = query.filter(
            SupplierContract.status == "ACTIVE",
            SupplierContract.valid_to <= today + timedelta(days=expiring_within_days),
            SupplierContract.valid_to >= today,
        )
    return query.order_by(SupplierContract.valid_to.asc(), SupplierContract.id.asc()).all()


@router.get("/supplier-contracts/{contract_id}", response_model=SupplierContractResponse)
def get_supplier_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    contract = db.query(SupplierContract).options(selectinload(SupplierContract.rates)).filter(
        SupplierContract.id == contract_id
    ).one_or_none()
    if contract is None:
        raise HTTPException(status_code=404, detail="Supplier contract not found.")
    return contract


@router.post("/supplier-contracts/{contract_id}/submit", response_model=SupplierContractResponse)
def submit_supplier_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:write")),
):
    contract = db.query(SupplierContract).filter(SupplierContract.id == contract_id).with_for_update().one_or_none()
    if contract is None:
        raise HTTPException(status_code=404, detail="Supplier contract not found.")
    if contract.status != "DRAFT":
        raise HTTPException(status_code=409, detail="Only draft contracts can be submitted.")
    if contract.created_by_id == current_user.id:
        # Submission is allowed; independent review is enforced at approval.
        pass
    contract.status = "PENDING_APPROVAL"
    contract.submitted_at = datetime.now(timezone.utc)
    contract.updated_by_id = current_user.id
    db.commit()
    return db.query(SupplierContract).options(selectinload(SupplierContract.rates)).filter(
        SupplierContract.id == contract.id
    ).one()


@router.patch("/supplier-contracts/{contract_id}/approve", response_model=SupplierContractResponse)
def approve_supplier_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:approve")),
):
    contract = db.query(SupplierContract).filter(SupplierContract.id == contract_id).with_for_update().one_or_none()
    if contract is None:
        raise HTTPException(status_code=404, detail="Supplier contract not found.")
    if contract.status != "PENDING_APPROVAL":
        raise HTTPException(status_code=409, detail="Only pending supplier contracts can be approved.")
    if contract.created_by_id == current_user.id:
        raise HTTPException(status_code=409, detail="The contract creator cannot approve the same contract.")
    if contract.valid_to < datetime.now(timezone.utc).date():
        raise HTTPException(status_code=409, detail="An expired contract cannot be activated.")
    contract.status = "ACTIVE"
    contract.approved_by_id = current_user.id
    contract.approved_at = datetime.now(timezone.utc)
    contract.updated_by_id = current_user.id
    db.commit()
    return db.query(SupplierContract).options(selectinload(SupplierContract.rates)).filter(
        SupplierContract.id == contract.id
    ).one()


@router.patch("/supplier-contracts/{contract_id}/terminate", response_model=SupplierContractResponse)
def terminate_supplier_contract(
    contract_id: int,
    reason: str = Query(..., min_length=10, max_length=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:approve")),
):
    contract = db.query(SupplierContract).filter(SupplierContract.id == contract_id).with_for_update().one_or_none()
    if contract is None:
        raise HTTPException(status_code=404, detail="Supplier contract not found.")
    if contract.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Only active contracts can be terminated.")
    open_po = db.query(PurchaseOrder.id).filter(
        PurchaseOrder.contract_id == contract.id,
        PurchaseOrder.status.in_([POStatusEnum.SUBMITTED, POStatusEnum.APPROVED, POStatusEnum.PARTIALLY_RECEIVED]),
    ).first()
    if open_po:
        raise HTTPException(status_code=409, detail="Contract cannot be terminated while linked purchase orders remain open.")
    contract.status = "TERMINATED"
    contract.terminated_by_id = current_user.id
    contract.terminated_at = datetime.now(timezone.utc)
    contract.termination_reason = reason.strip()
    contract.updated_by_id = current_user.id
    db.commit()
    return db.query(SupplierContract).options(selectinload(SupplierContract.rates)).filter(
        SupplierContract.id == contract.id
    ).one()


@router.post("/supplier-contracts/{contract_id}/revisions", response_model=SupplierContractRevisionResponse, status_code=status.HTTP_201_CREATED)
def request_supplier_contract_revision(
    contract_id: int,
    payload: SupplierContractRevisionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:write")),
):
    contract = db.query(SupplierContract).filter(SupplierContract.id == contract_id).with_for_update().one_or_none()
    if contract is None:
        raise HTTPException(status_code=404, detail="Supplier contract not found.")
    if contract.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Only active contracts can be amended.")
    if payload.proposed_valid_to is not None and payload.proposed_valid_to < contract.valid_from:
        raise HTTPException(status_code=422, detail="Proposed contract end date cannot precede its start date.")
    pending = db.query(SupplierContractRevision.id).filter(
        SupplierContractRevision.contract_id == contract.id,
        SupplierContractRevision.status == "PENDING",
    ).first()
    if pending:
        raise HTTPException(status_code=409, detail="A pending contract revision already exists.")
    current_rates = db.query(SupplierContractRate).filter(
        SupplierContractRate.contract_id == contract.id
    ).order_by(SupplierContractRate.id.asc()).all()
    prior = {"valid_from": contract.valid_from.isoformat(), "valid_to": contract.valid_to.isoformat(),
             "payment_terms": contract.payment_terms, "summary": contract.summary, "version_number": contract.version_number,
             "rates": [{"scope_type": r.scope_type, "medication_id": r.medication_id, "category": r.category,
                        "uom_code": r.uom_code, "unit_price_paise": r.unit_price_paise,
                        "tax_percentage": r.tax_percentage, "notes": r.notes} for r in current_rates]}
    proposed = dict(prior)
    if payload.proposed_valid_to is not None:
        proposed["valid_to"] = payload.proposed_valid_to.isoformat()
    if payload.proposed_payment_terms is not None:
        proposed["payment_terms"] = payload.proposed_payment_terms
    if payload.proposed_summary is not None:
        proposed["summary"] = payload.proposed_summary
    if payload.proposed_rates is not None:
        for rate in payload.proposed_rates:
            if rate.medication_id is not None and db.get(MedicationMaster, rate.medication_id) is None:
                raise HTTPException(status_code=404, detail=f"Medication {rate.medication_id} not found.")
            if db.query(ProcurementUnitOfMeasure.id).filter(
                ProcurementUnitOfMeasure.code == rate.uom_code
            ).one_or_none() is None:
                raise HTTPException(status_code=422, detail=f"Unknown contract rate UOM: {rate.uom_code}.")
        proposed["rates"] = [rate.model_dump() for rate in payload.proposed_rates]
    revision = SupplierContractRevision(
        contract_id=contract.id, revision_number=contract.version_number + 1,
        prior_snapshot=prior, proposed_snapshot=proposed, reason=payload.reason.strip(),
        requested_by_id=current_user.id,
    )
    db.add(revision)
    db.commit()
    db.refresh(revision)
    return revision


@router.patch("/supplier-contracts/{contract_id}/revisions/{revision_id}/review", response_model=SupplierContractRevisionResponse)
def review_supplier_contract_revision(
    contract_id: int,
    revision_id: int,
    payload: SupplierContractRevisionReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:approve")),
):
    revision = db.query(SupplierContractRevision).filter(
        SupplierContractRevision.id == revision_id,
        SupplierContractRevision.contract_id == contract_id,
    ).with_for_update().one_or_none()
    if revision is None:
        raise HTTPException(status_code=404, detail="Contract revision not found.")
    contract = db.query(SupplierContract).filter(SupplierContract.id == contract_id).with_for_update().one_or_none()
    if revision.status != "PENDING" or contract is None:
        raise HTTPException(status_code=409, detail="Contract revision is no longer pending.")
    if revision.requested_by_id == current_user.id:
        raise HTTPException(status_code=409, detail="The revision requester cannot review their own revision.")
    revision.status = "APPROVED" if payload.approved else "REJECTED"
    revision.reviewed_by_id = current_user.id
    revision.reviewed_at = datetime.now(timezone.utc)
    revision.review_notes = payload.review_notes.strip()
    if payload.approved:
        contract.valid_to = date.fromisoformat(revision.proposed_snapshot["valid_to"])
        contract.payment_terms = revision.proposed_snapshot["payment_terms"]
        contract.summary = revision.proposed_snapshot["summary"]
        if "rates" in revision.proposed_snapshot and revision.proposed_snapshot["rates"] != revision.prior_snapshot.get("rates"):
            db.query(SupplierContractRate).filter(
                SupplierContractRate.contract_id == contract.id
            ).delete(synchronize_session=False)
            for rate_data in revision.proposed_snapshot["rates"]:
                db.add(SupplierContractRate(
                    contract_id=contract.id,
                    created_by_id=current_user.id,
                    **rate_data,
                ))
        contract.version_number = revision.revision_number
        contract.approved_by_id = current_user.id
        contract.approved_at = datetime.now(timezone.utc)
        contract.updated_by_id = current_user.id
    db.commit()
    db.refresh(revision)
    return revision


@router.get("/supplier-contracts/{contract_id}/revisions", response_model=list[SupplierContractRevisionResponse])
def list_supplier_contract_revisions(
    contract_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    if db.get(SupplierContract, contract_id) is None:
        raise HTTPException(status_code=404, detail="Supplier contract not found.")
    return db.query(SupplierContractRevision).filter(
        SupplierContractRevision.contract_id == contract_id
    ).order_by(SupplierContractRevision.revision_number.asc()).all()


@router.get("/supplier-contract-renewals/due")
def list_supplier_contract_renewals(
    within_days: int = Query(default=90, ge=0, le=730),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("procurement:read")),
):
    today = datetime.now(timezone.utc).date()
    contracts = db.query(SupplierContract).options(joinedload(SupplierContract.vendor)).filter(
        SupplierContract.status == "ACTIVE",
        SupplierContract.valid_to <= today + timedelta(days=within_days),
    ).order_by(SupplierContract.valid_to.asc()).all()
    return [{
        "contract_id": c.id, "contract_number": c.contract_number, "title": c.title,
        "vendor_id": c.vendor_id, "vendor_name": c.vendor.name,
        "valid_to": c.valid_to, "days_remaining": (c.valid_to - today).days,
        "renewal_notice_days": c.renewal_notice_days,
        "notice_due": c.valid_to - timedelta(days=c.renewal_notice_days) <= today,
        "auto_renew": c.auto_renew,
    } for c in contracts]


@router.post("/supplier-contracts/{contract_id}/document")
def upload_supplier_contract_document(
    contract_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:write")),
):
    tenant = resolve_tenant_context(request)
    contract = db.query(SupplierContract).filter(
        SupplierContract.id == contract_id
    ).with_for_update().one_or_none()
    if contract is None:
        raise HTTPException(status_code=404, detail="Supplier contract not found.")
    if contract.status != "DRAFT":
        raise HTTPException(status_code=409, detail="Signed contract evidence can only be attached while the contract is a draft.")
    try:
        document_key, document_path = store_supplier_contract_document(
            tenant.subdomain_slug, file.filename, file.file
        )
    finally:
        file.file.close()
    old_key = contract.document_file_url
    contract.document_file_url = document_key
    contract.updated_by_id = current_user.id
    try:
        db.commit()
    except Exception:
        db.rollback()
        document_path.unlink(missing_ok=True)
        raise
    if old_key:
        try:
            old_path = resolve_supplier_contract_document(tenant.subdomain_slug, old_key)
            old_path.unlink(missing_ok=True)
        except HTTPException:
            pass
    return {"contract_id": contract.id, "document_attached": True}


@router.get("/supplier-contracts/{contract_id}/document")
def download_supplier_contract_document(
    contract_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("procurement:read")),
):
    tenant = resolve_tenant_context(request)
    contract = db.get(SupplierContract, contract_id)
    if contract is None or not contract.document_file_url:
        raise HTTPException(status_code=404, detail="Contract document not found.")
    path = resolve_supplier_contract_document(tenant.subdomain_slug, contract.document_file_url)
    media_type = {
        ".pdf": "application/pdf", ".png": "image/png",
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    }[path.suffix.lower()]
    db.add(SupplierContractDocumentDownloadAudit(
        contract_id=contract.id,
        contract_number=contract.contract_number,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
    ))
    db.commit()
    return FileResponse(path, media_type=media_type, filename=f"{contract.contract_number}{path.suffix}")


# --- Private reconciliation investigation evidence ---
_RECONCILIATION_EVIDENCE_TYPES = {
    "BANK_STATEMENT", "PAYMENT_PROOF", "INVOICE",
    "SUPPLIER_CORRESPONDENCE", "APPROVAL_RECORD", "OTHER",
}


@router.post("/reconciliation/exceptions/{exception_id}/evidence", status_code=status.HTTP_201_CREATED)
def upload_reconciliation_evidence(
    exception_id: int,
    request: Request,
    evidence_type: str = Form(...),
    description: Optional[str] = Form(default=None, max_length=500),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:write")),
):
    exception_row = db.get(ProcurementReconciliationException, exception_id)
    if exception_row is None:
        raise HTTPException(status_code=404, detail="Reconciliation exception not found.")
    if exception_row.status in {"RESOLVED", "DISMISSED"}:
        raise HTTPException(status_code=409, detail="Reopen the investigation before attaching additional evidence.")
    kind = evidence_type.strip().upper()
    if kind not in _RECONCILIATION_EVIDENCE_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported reconciliation evidence type.")
    clean_description = description.strip() if description else None
    if clean_description == "":
        clean_description = None
    original_filename = PurePath((file.filename or "evidence").replace(chr(92), "/")).name
    original_filename = re.sub(r"[^A-Za-z0-9._ -]", "_", original_filename).strip(" .")[:255] or "evidence"
    tenant = resolve_tenant_context(request)
    try:
        storage_key, stored_path, size_bytes, sha256_hex, media_type = store_reconciliation_evidence(
            tenant.subdomain_slug, file.filename, file.file
        )
    finally:
        file.file.close()

    # Recheck lifecycle under a row lock after the potentially slow malware scan.
    exception_row = db.query(ProcurementReconciliationException).filter(
        ProcurementReconciliationException.id == exception_id
    ).with_for_update().one_or_none()
    if exception_row is None or exception_row.status in {"RESOLVED", "DISMISSED"}:
        stored_path.unlink(missing_ok=True)
        if exception_row is None:
            raise HTTPException(status_code=404, detail="Reconciliation exception not found.")
        raise HTTPException(status_code=409, detail="The investigation closed while evidence was being scanned; reopen it before uploading.")

    evidence = ProcurementReconciliationEvidence(
        exception_id=exception_row.id,
        evidence_type=kind,
        description=clean_description,
        storage_key=storage_key,
        original_filename=original_filename,
        media_type=media_type,
        size_bytes=size_bytes,
        sha256_hex=sha256_hex,
        uploaded_by_id=current_user.id,
    )
    db.add(evidence)
    try:
        db.flush()
        _record_reconciliation_event(
            db, exception_row, "EVIDENCE_ATTACHED", current_user.id,
            note=f"Evidence attached: {kind}",
            event_metadata={
                "evidence_id": evidence.id,
                "evidence_type": kind,
                "original_filename": original_filename,
                "size_bytes": size_bytes,
                "sha256_hex": sha256_hex,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        stored_path.unlink(missing_ok=True)
        raise
    db.refresh(evidence)
    return {
        "id": evidence.id,
        "exception_id": evidence.exception_id,
        "evidence_type": evidence.evidence_type,
        "description": evidence.description,
        "original_filename": evidence.original_filename,
        "media_type": evidence.media_type,
        "size_bytes": evidence.size_bytes,
        "sha256_hex": evidence.sha256_hex,
        "uploaded_by_id": evidence.uploaded_by_id,
        "uploaded_at": evidence.uploaded_at,
        "download_url": f"/api/procurement/reconciliation/exceptions/{exception_id}/evidence/{evidence.id}/download",
    }


@router.get("/reconciliation/exceptions/{exception_id}/evidence")
def list_reconciliation_evidence(
    exception_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    if db.get(ProcurementReconciliationException, exception_id) is None:
        raise HTTPException(status_code=404, detail="Reconciliation exception not found.")
    rows = db.query(ProcurementReconciliationEvidence).filter(
        ProcurementReconciliationEvidence.exception_id == exception_id
    ).order_by(
        ProcurementReconciliationEvidence.uploaded_at.asc(),
        ProcurementReconciliationEvidence.id.asc(),
    ).all()
    return [{
        "id": row.id,
        "exception_id": row.exception_id,
        "evidence_type": row.evidence_type,
        "description": row.description,
        "original_filename": row.original_filename,
        "media_type": row.media_type,
        "size_bytes": row.size_bytes,
        "sha256_hex": row.sha256_hex,
        "uploaded_by_id": row.uploaded_by_id,
        "uploaded_at": row.uploaded_at,
        "download_url": f"/api/procurement/reconciliation/exceptions/{exception_id}/evidence/{row.id}/download",
    } for row in rows]



@router.get("/reconciliation/exceptions/{exception_id}/audit-export")
def export_reconciliation_exception_audit(
    exception_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:read")),
):
    """Build a tenant-scoped audit ZIP; export generation is itself journaled."""
    exception_row = db.get(ProcurementReconciliationException, exception_id)
    if exception_row is None:
        raise HTTPException(status_code=404, detail="Reconciliation exception not found.")

    tenant = resolve_tenant_context(request)
    evidence_rows = db.query(ProcurementReconciliationEvidence).filter(
        ProcurementReconciliationEvidence.exception_id == exception_id
    ).order_by(
        ProcurementReconciliationEvidence.uploaded_at.asc(),
        ProcurementReconciliationEvidence.id.asc(),
    ).all()
    if len(evidence_rows) > 100:
        raise HTTPException(status_code=413, detail="Investigation has too many evidence files for a single export.")

    payload_files: dict[str, bytes] = {}
    evidence_manifest = []
    total_evidence_bytes = 0
    for evidence in evidence_rows:
        path = resolve_reconciliation_evidence(tenant.subdomain_slug, evidence.storage_key)
        try:
            actual_digest = reconciliation_evidence_sha256(path)
            file_size = path.stat().st_size
        except OSError as exc:
            raise HTTPException(status_code=503, detail="Evidence storage is unavailable; audit export was not generated.") from exc
        if actual_digest != evidence.sha256_hex or file_size != evidence.size_bytes:
            _record_reconciliation_event(
                db, exception_row, "EVIDENCE_HASH_MISMATCH", current_user.id,
                note="Evidence integrity verification failed during audit export.",
                event_metadata={
                    "evidence_id": evidence.id,
                    "expected_sha256": evidence.sha256_hex,
                    "actual_sha256": actual_digest,
                    "expected_size_bytes": evidence.size_bytes,
                    "actual_size_bytes": file_size,
                },
            )
            db.commit()
            raise HTTPException(status_code=409, detail="Evidence integrity verification failed; audit export was not generated.")
        total_evidence_bytes += file_size
        if total_evidence_bytes > 50 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Investigation evidence exceeds the 50 MB audit export limit.")
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", evidence.original_filename).strip("._") or f"evidence-{evidence.id}"
        archive_name = f"evidence/{evidence.id:06d}-{safe_name}"
        try:
            payload_files[archive_name] = path.read_bytes()
        except OSError as exc:
            raise HTTPException(status_code=503, detail="Evidence storage could not be read; audit export was not generated.") from exc
        evidence_manifest.append({
            "evidence_id": evidence.id,
            "evidence_type": evidence.evidence_type,
            "original_filename": evidence.original_filename,
            "archive_path": archive_name,
            "media_type": evidence.media_type,
            "size_bytes": file_size,
            "sha256": actual_digest,
            "uploaded_by_id": evidence.uploaded_by_id,
            "uploaded_at": evidence.uploaded_at,
            "description": evidence.description,
        })

    download_audits = db.query(ProcurementReconciliationEvidenceDownloadAudit).filter(
        ProcurementReconciliationEvidenceDownloadAudit.exception_id == exception_id
    ).order_by(
        ProcurementReconciliationEvidenceDownloadAudit.requested_at.asc(),
        ProcurementReconciliationEvidenceDownloadAudit.id.asc(),
    ).all()
    download_audit_payload = {
        "exception_id": exception_id,
        "downloads": [{
            "evidence_id": item.evidence_id,
            "evidence_type": item.evidence_type,
            "original_filename": item.original_filename,
            "actor_user_id": item.actor_user_id,
            "actor_email": item.actor_email,
            "requested_at": item.requested_at,
        } for item in download_audits],
    }
    payload_files["evidence-download-audit.json"] = json.dumps(
        download_audit_payload, default=str, ensure_ascii=False, sort_keys=True, indent=2
    ).encode("utf-8")

    investigation = {
        "export_schema_version": "1.0",
        "exception": {
            "id": exception_row.id,
            "fingerprint": exception_row.fingerprint,
            "exception_type": exception_row.exception_type,
            "severity": exception_row.severity,
            "status": exception_row.status,
            "reference_type": exception_row.reference_type,
            "reference_id": exception_row.reference_id,
            "amount_paise": exception_row.amount_paise,
            "matched_amount_paise": exception_row.matched_amount_paise,
            "unmatched_amount_paise": exception_row.unmatched_amount_paise,
            "summary": exception_row.summary,
            "detection_snapshot": exception_row.detection_snapshot,
            "source_present": exception_row.source_present,
            "missed_refresh_count": exception_row.missed_refresh_count,
            "first_detected_at": exception_row.first_detected_at,
            "last_detected_at": exception_row.last_detected_at,
            "assigned_to_id": exception_row.assigned_to_id,
            "resolved_by_id": exception_row.resolved_by_id,
            "resolved_at": exception_row.resolved_at,
            "resolution_note": exception_row.resolution_note,
            "root_cause_code": exception_row.root_cause_code,
            "resolution_checklist": exception_row.resolution_checklist,
            "reopen_count": exception_row.reopen_count,
            "resolution_review_status": exception_row.resolution_review_status,
            "resolution_submitted_status": exception_row.resolution_submitted_status,
            "resolution_submitted_by_id": exception_row.resolution_submitted_by_id,
            "resolution_reviewed_by_id": exception_row.resolution_reviewed_by_id,
            "resolution_reviewed_at": exception_row.resolution_reviewed_at,
        },
        "evidence": evidence_manifest,
    }
    investigation_bytes = json.dumps(
        investigation, default=str, ensure_ascii=False, sort_keys=True, indent=2
    ).encode("utf-8")
    payload_files["investigation.json"] = investigation_bytes
    manifest = {
        "manifest_version": "1.0",
        "package_type": "AVINYA_HMS_RECONCILIATION_AUDIT",
        "tenant_slug": tenant.subdomain_slug,
        "exception_id": exception_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by_user_id": current_user.id,
        "files": [
            {"path": name, "size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
            for name, content in sorted(payload_files.items())
        ],
        "manifest_scope_note": "Hashes cover investigation.json, evidence-download-audit.json, and each included evidence file. history.json contains this export-generation event and is intentionally excluded to avoid a circular hash.",
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()

    _record_reconciliation_event(
        db, exception_row, "AUDIT_EXPORT_GENERATED", current_user.id,
        note="Investigation audit package generated.",
        event_metadata={
            "manifest_sha256": manifest_sha256,
            "evidence_count": len(evidence_rows),
            "evidence_total_bytes": total_evidence_bytes,
            "package_type": "AVINYA_HMS_RECONCILIATION_AUDIT",
        },
    )
    db.commit()

    events = db.query(ProcurementReconciliationExceptionEvent).filter(
        ProcurementReconciliationExceptionEvent.exception_id == exception_id
    ).order_by(
        ProcurementReconciliationExceptionEvent.occurred_at.asc(),
        ProcurementReconciliationExceptionEvent.id.asc(),
    ).all()
    history = {
        "exception_id": exception_id,
        "events": [{
            "id": event.id,
            "event_type": event.event_type,
            "actor_user_id": event.actor_user_id,
            "old_status": event.old_status,
            "new_status": event.new_status,
            "old_assignee_id": event.old_assignee_id,
            "new_assignee_id": event.new_assignee_id,
            "note": event.note,
            "event_metadata": event.event_metadata,
            "occurred_at": event.occurred_at,
        } for event in events],
    }
    payload_files["history.json"] = json.dumps(
        history, default=str, ensure_ascii=False, sort_keys=True, indent=2
    ).encode("utf-8")
    payload_files["manifest.json"] = manifest_bytes

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, mode="w", compression=zipfile.ZIP_DEFLATED) as package:
        for name, content in sorted(payload_files.items()):
            package.writestr(name, content)
    archive_bytes = archive.getvalue()
    safe_tenant = re.sub(r"[^A-Za-z0-9_-]", "_", tenant.subdomain_slug)
    db.add(ProcurementReconciliationAuditExport(
        exception_id=exception_id,
        export_type="EXCEPTION_AUDIT_ZIP",
        status="GENERATED",
        file_sha256=hashlib.sha256(archive_bytes).hexdigest(),
        file_size_bytes=len(archive_bytes),
        filter_snapshot={"manifest_sha256": manifest_sha256, "evidence_count": len(evidence_rows)},
        actor_user_id=current_user.id,
        actor_email=current_user.email,
    ))
    db.commit()
    return Response(
        content=archive_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="reconciliation-{safe_tenant}-{exception_id}-audit.zip"',
            "Content-Length": str(len(archive_bytes)),
            "Cache-Control": "private, no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "X-Audit-Manifest-SHA256": manifest_sha256,
        },
    )


@router.get("/reconciliation/exceptions/{exception_id}/evidence/{evidence_id}/download")
def download_reconciliation_evidence(
    exception_id: int,
    evidence_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:read")),
):
    tenant = resolve_tenant_context(request)
    row = db.query(ProcurementReconciliationEvidence).filter(
        ProcurementReconciliationEvidence.id == evidence_id,
        ProcurementReconciliationEvidence.exception_id == exception_id,
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Reconciliation evidence not found.")
    path = resolve_reconciliation_evidence(tenant.subdomain_slug, row.storage_key)
    try:
        actual_sha256 = reconciliation_evidence_sha256(path)
    except OSError as exc:
        raise HTTPException(status_code=503, detail="Reconciliation evidence storage is unavailable.") from exc
    if actual_sha256 != row.sha256_hex:
        exception_row = db.get(ProcurementReconciliationException, exception_id)
        if exception_row is not None:
            _record_reconciliation_event(
                db, exception_row, "EVIDENCE_HASH_MISMATCH", current_user.id,
                note="Evidence integrity verification failed during download.",
                event_metadata={"evidence_id": row.id, "expected_sha256": row.sha256_hex, "actual_sha256": actual_sha256},
            )
            db.commit()
        raise HTTPException(status_code=409, detail="Evidence integrity verification failed; the file was not served.")
    db.add(ProcurementReconciliationEvidenceDownloadAudit(
        evidence_id=row.id,
        exception_id=exception_id,
        evidence_type=row.evidence_type,
        original_filename=row.original_filename,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
    ))
    db.commit()
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", f"reconciliation-{exception_id}-{row.evidence_type}")
    return FileResponse(
        path,
        media_type=row.media_type,
        filename=f"{safe_name}{path.suffix.lower()}",
        headers={
            "Cache-Control": "private, no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Cross-Origin-Resource-Policy": "same-origin",
        },
    )


# --- Persisted reconciliation exception investigation queue ---
def _record_reconciliation_event(db: Session, exception_row: ProcurementReconciliationException, event_type: str, actor_id: int, **kwargs):
    db.add(ProcurementReconciliationExceptionEvent(
        exception_id=exception_row.id, event_type=event_type, actor_user_id=actor_id,
        old_status=kwargs.get("old_status"), new_status=kwargs.get("new_status"),
        old_assignee_id=kwargs.get("old_assignee_id"), new_assignee_id=kwargs.get("new_assignee_id"),
        note=kwargs.get("note"), event_metadata=kwargs.get("event_metadata") or {},
    ))


@router.post("/reconciliation/exceptions/refresh")
def refresh_procurement_reconciliation_exceptions(
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:write")),
):
    """Snapshot current detections and mark absent source items without auto-resolving them."""
    # Serialize full scans per branch database on PostgreSQL.
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(7342198601)"))
    live = get_procurement_reconciliation_exceptions(None, None, 0, db, current_user)
    now = datetime.now(timezone.utc)
    created = updated = unchanged_terminal = missing_marked = 0
    seen_fingerprints = set()
    for item in live["exceptions"]:
        fingerprint = f'{item["exception_type"]}:{item["reference_type"]}:{item["reference_id"]}'
        seen_fingerprints.add(fingerprint)
        row = db.query(ProcurementReconciliationException).filter(
            ProcurementReconciliationException.fingerprint == fingerprint
        ).with_for_update().one_or_none()
        snapshot = {
            key: (value.isoformat() if isinstance(value, (date, datetime)) else value)
            for key, value in item.items()
        }
        sla_policy_id, sla_target_hours = _reconciliation_sla_snapshot(db, item["severity"], now)
        if row is None:
            row = ProcurementReconciliationException(
                fingerprint=fingerprint, exception_type=item["exception_type"],
                severity=item["severity"], status="OPEN",
                reference_type=item["reference_type"], reference_id=item["reference_id"],
                amount_paise=int(item.get("amount_paise", 0)),
                matched_amount_paise=int(item.get("matched_amount_paise", 0)),
                unmatched_amount_paise=int(item.get("unmatched_amount_paise", 0)),
                summary=item["description"], detection_snapshot=snapshot,
                first_detected_at=now, last_detected_at=now,
                source_present=True, missed_refresh_count=0,
                sla_policy_id=sla_policy_id,
                sla_target_hours=sla_target_hours,
            )
            db.add(row)
            db.flush()
            _record_reconciliation_event(db, row, "DETECTED", current_user.id,
                event_metadata={"severity": item["severity"]})
            created += 1
        elif row.status in ("RESOLVED", "DISMISSED"):
            if not row.source_present:
                row.source_present = True
                row.missed_refresh_count = 0
                row.last_detected_at = now
                _record_reconciliation_event(db, row, "TERMINAL_SOURCE_REAPPEARED", current_user.id,
                    event_metadata={"status_preserved": row.status})
            unchanged_terminal += 1
        else:
            was_missing = not row.source_present
            row.source_present = True
            row.missed_refresh_count = 0
            previous_severity = row.severity
            previous_sla_target_hours = row.sla_target_hours
            severity_changed = previous_severity != item["severity"]
            row.severity = item["severity"]
            if severity_changed:
                row.sla_policy_id = sla_policy_id
                row.sla_target_hours = sla_target_hours
            row.amount_paise = int(item.get("amount_paise", 0))
            row.matched_amount_paise = int(item.get("matched_amount_paise", 0))
            row.unmatched_amount_paise = int(item.get("unmatched_amount_paise", 0))
            row.summary = item["description"]
            row.detection_snapshot = snapshot
            row.last_detected_at = now
            _record_reconciliation_event(db, row,
                "SEVERITY_CHANGED" if severity_changed else ("SOURCE_REAPPEARED" if was_missing else "UPDATED"), current_user.id,
                event_metadata={
                    "severity": item["severity"],
                    "previous_severity": previous_severity if severity_changed else None,
                    "previous_sla_target_hours": previous_sla_target_hours if severity_changed else None,
                    "sla_target_hours": row.sla_target_hours,
                    "sla_policy_id": row.sla_policy_id,
                })
            updated += 1

    # Only a completed full scan reaches this point. Absence is evidence of disappearance,
    # not proof of resolution, so the reviewer still owns the terminal decision.
    active_rows = db.query(ProcurementReconciliationException).filter(
        ProcurementReconciliationException.source_present.is_(True)
    ).with_for_update().all()
    for row in active_rows:
        if row.fingerprint not in seen_fingerprints:
            row.source_present = False
            row.missed_refresh_count = int(row.missed_refresh_count or 0) + 1
            _record_reconciliation_event(db, row, "SOURCE_NOT_DETECTED", current_user.id,
                event_metadata={"missed_refresh_count": row.missed_refresh_count})
            missing_marked += 1
    db.commit()
    return {
        "detected": len(live["exceptions"]), "created": created, "updated": updated,
        "terminal_items_not_reopened": unchanged_terminal, "marked_missing": missing_marked,
        "refreshed_at": now,
        "note": "Missing source items remain open until a reviewer resolves or dismisses them.",
    }


RECONCILIATION_DEFAULT_SLA_HOURS = {"CRITICAL": 4, "HIGH": 24, "MEDIUM": 72, "LOW": 168}


def _effective_reconciliation_sla_policy(db: Session, at: Optional[datetime] = None):
    moment = at or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return db.query(ProcurementReconciliationSlaPolicy).filter(
        ProcurementReconciliationSlaPolicy.status == "PUBLISHED",
        ProcurementReconciliationSlaPolicy.effective_from <= moment,
        or_(
            ProcurementReconciliationSlaPolicy.effective_to.is_(None),
            ProcurementReconciliationSlaPolicy.effective_to > moment,
        ),
    ).order_by(ProcurementReconciliationSlaPolicy.effective_from.desc()).first()


def _reconciliation_sla_snapshot(db: Session, severity: str, at: Optional[datetime] = None):
    policy = _effective_reconciliation_sla_policy(db, at)
    target = (policy.severity_targets_hours if policy else RECONCILIATION_DEFAULT_SLA_HOURS).get(
        severity, RECONCILIATION_DEFAULT_SLA_HOURS.get(severity, 168)
    )
    return policy.id if policy else None, int(target)


def _reconciliation_sla_hours(row) -> int:
    return int(row.sla_target_hours or RECONCILIATION_DEFAULT_SLA_HOURS.get(row.severity, 168))


def _reconciliation_sla_clock(row, at: Optional[datetime] = None):
    """Return pause-aware SLA elapsed time, deadline, and breach timestamp.

    first_detected_at is the immutable clock origin. Resolution stops the clock;
    authorized pauses are excluded from active elapsed time.
    """
    now = at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    def utc(value):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    started_at = utc(row.first_detected_at)
    resolved_at = utc(row.resolved_at) if row.status in {"RESOLVED", "DISMISSED"} else None
    clock_end = min(resolved_at, now) if resolved_at else now
    paused_seconds = max(int(row.sla_paused_seconds or 0), 0)
    paused_at = utc(row.sla_paused_at)
    currently_paused = paused_at is not None and row.status in {"OPEN", "IN_REVIEW"}
    current_pause_seconds = 0
    if paused_at is not None:
        pause_end = min(clock_end, now)
        current_pause_seconds = max(int((pause_end - paused_at).total_seconds()), 0)
    elapsed_seconds = max(int((clock_end - started_at).total_seconds()) - paused_seconds - current_pause_seconds, 0)
    target_seconds = _reconciliation_sla_hours(row) * 3600
    breached = elapsed_seconds > target_seconds
    breached_at = utc(row.sla_breached_at)
    if breached and breached_at is None and not currently_paused:
        breached_at = started_at + timedelta(seconds=target_seconds + paused_seconds)
    due_at = breached_at if breached_at is not None else (None if currently_paused else started_at + timedelta(seconds=target_seconds + paused_seconds))
    return {
        "elapsed_seconds": elapsed_seconds,
        "elapsed_hours": round(elapsed_seconds / 3600, 2),
        "remaining_seconds": max(target_seconds - elapsed_seconds, 0),
        "remaining_hours": round(max(target_seconds - elapsed_seconds, 0) / 3600, 2),
        "paused": currently_paused,
        "paused_at": paused_at,
        "paused_seconds": paused_seconds + current_pause_seconds,
        "due_at": due_at,
        "breached": breached or breached_at is not None,
        "breached_at": breached_at,
        "target_hours": _reconciliation_sla_hours(row),
    }


@router.get("/reconciliation/sla-policies")
def list_reconciliation_sla_policies(
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    rows = db.query(ProcurementReconciliationSlaPolicy).order_by(
        ProcurementReconciliationSlaPolicy.version.desc()
    ).limit(50).all()
    active = _effective_reconciliation_sla_policy(db)
    return {
        "active_policy_id": active.id if active else None,
        "active_policy_version": active.version if active else None,
        "baseline_fallback": RECONCILIATION_DEFAULT_SLA_HOURS,
        "items": [ReconciliationSlaPolicyResponse.model_validate(row).model_dump(mode="json") for row in rows],
    }


@router.get("/reconciliation/sla-policies/{policy_id}/events")
def list_reconciliation_sla_policy_events(
    policy_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    policy_exists = db.query(ProcurementReconciliationSlaPolicy.id).filter(
        ProcurementReconciliationSlaPolicy.id == policy_id
    ).scalar()
    if policy_exists is None:
        raise HTTPException(status_code=404, detail="SLA policy version not found.")
    events = db.query(ProcurementReconciliationSlaPolicyEvent).filter(
        ProcurementReconciliationSlaPolicyEvent.policy_id == policy_id
    ).order_by(
        ProcurementReconciliationSlaPolicyEvent.occurred_at.asc(),
        ProcurementReconciliationSlaPolicyEvent.id.asc(),
    ).all()
    return {
        "policy_id": policy_id,
        "events": [{
            "id": event.id,
            "event_type": event.event_type,
            "actor_user_id": event.actor_user_id,
            "event_metadata": event.event_metadata,
            "occurred_at": event.occurred_at,
        } for event in events],
    }


@router.post("/reconciliation/sla-policies", status_code=201)
def create_reconciliation_sla_policy(
    payload: ReconciliationSlaPolicyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:sla:manage")),
):
    latest_version = db.query(func.max(ProcurementReconciliationSlaPolicy.version)).filter(
        ProcurementReconciliationSlaPolicy.policy_key == "DEFAULT"
    ).scalar() or 0
    policy = ProcurementReconciliationSlaPolicy(
        policy_key="DEFAULT",
        version=int(latest_version) + 1,
        status="DRAFT",
        severity_targets_hours=payload.severity_targets_hours,
        change_reason=payload.change_reason.strip(),
        effective_from=datetime.now(timezone.utc),
        created_by_id=current_user.id,
    )
    db.add(policy)
    db.flush()
    db.add(ProcurementReconciliationSlaPolicyEvent(
        policy_id=policy.id,
        event_type="DRAFT_CREATED",
        actor_user_id=current_user.id,
        event_metadata={"version": policy.version, "severity_targets_hours": policy.severity_targets_hours,
                        "change_reason": policy.change_reason},
    ))
    db.commit()
    db.refresh(policy)
    return ReconciliationSlaPolicyResponse.model_validate(policy).model_dump(mode="json")


@router.post("/reconciliation/sla-policies/{policy_id}/publish")
def publish_reconciliation_sla_policy(
    policy_id: int,
    payload: ReconciliationSlaPolicyPublish,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:sla:manage")),
):
    policy = db.query(ProcurementReconciliationSlaPolicy).filter(
        ProcurementReconciliationSlaPolicy.id == policy_id
    ).with_for_update().one_or_none()
    if policy is None:
        raise HTTPException(status_code=404, detail="SLA policy version not found.")
    if policy.status != "DRAFT":
        raise HTTPException(status_code=409, detail="Only draft SLA policy versions can be published.")
    effective_from = payload.effective_from or datetime.now(timezone.utc)
    if effective_from.tzinfo is None:
        effective_from = effective_from.replace(tzinfo=timezone.utc)
    else:
        effective_from = effective_from.astimezone(timezone.utc)
    if effective_from < datetime.now(timezone.utc) - timedelta(minutes=1):
        raise HTTPException(status_code=422, detail="SLA policy effective_from cannot be in the past.")

    published = db.query(ProcurementReconciliationSlaPolicy).filter(
        ProcurementReconciliationSlaPolicy.status == "PUBLISHED",
        or_(
            ProcurementReconciliationSlaPolicy.effective_to.is_(None),
            ProcurementReconciliationSlaPolicy.effective_to > effective_from,
        ),
    ).with_for_update().all()
    for previous in published:
        if previous.effective_from >= effective_from:
            raise HTTPException(status_code=409, detail="A published policy already starts at or after this effective date.")
        previous.effective_to = effective_from
        db.add(ProcurementReconciliationSlaPolicyEvent(
            policy_id=previous.id,
            event_type="SUPERSEDED",
            actor_user_id=current_user.id,
            event_metadata={"superseded_by_policy_id": policy.id, "effective_to": effective_from.isoformat()},
        ))

    policy.status = "PUBLISHED"
    policy.effective_from = effective_from
    policy.published_by_id = current_user.id
    policy.published_at = datetime.now(timezone.utc)
    db.add(ProcurementReconciliationSlaPolicyEvent(
        policy_id=policy.id,
        event_type="PUBLISHED",
        actor_user_id=current_user.id,
        event_metadata={"effective_from": effective_from.isoformat(),
                        "severity_targets_hours": policy.severity_targets_hours},
    ))
    db.commit()
    db.refresh(policy)
    return ReconciliationSlaPolicyResponse.model_validate(policy).model_dump(mode="json")


@router.get("/reconciliation/my-assignments")
def list_my_reconciliation_assignments(
    limit: int = Query(default=100, ge=1, le=250),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return only active reconciliation investigations assigned to the authenticated branch user.

    This intentionally does not require finance:read and does not expose financial
    dashboard data, supplier names, invoice details, or other users' assignments.
    """
    rows = db.query(ProcurementReconciliationException).filter(
        ProcurementReconciliationException.assigned_to_id == current_user.id,
        ProcurementReconciliationException.status.in_(["OPEN", "IN_REVIEW"]),
    ).order_by(
        ProcurementReconciliationException.first_detected_at.asc(),
        ProcurementReconciliationException.id.asc(),
    ).limit(limit).all()
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    rows.sort(key=lambda row: (severity_order.get(row.severity, 4), row.first_detected_at, row.id))
    items = []
    for row in rows:
        assignment = db.query(ProcurementReconciliationExceptionEvent).filter(
            ProcurementReconciliationExceptionEvent.exception_id == row.id,
            ProcurementReconciliationExceptionEvent.event_type == "ASSIGNED",
            ProcurementReconciliationExceptionEvent.new_assignee_id == current_user.id,
        ).order_by(
            ProcurementReconciliationExceptionEvent.occurred_at.desc(),
            ProcurementReconciliationExceptionEvent.id.desc(),
        ).first()
        if assignment is None:
            continue
        answered = db.query(ProcurementReconciliationExceptionEvent).filter(
            ProcurementReconciliationExceptionEvent.exception_id == row.id,
            ProcurementReconciliationExceptionEvent.id > assignment.id,
            ProcurementReconciliationExceptionEvent.event_type.in_(["ASSIGNMENT_ACCEPTED", "ASSIGNMENT_REJECTED"]),
        ).order_by(ProcurementReconciliationExceptionEvent.id.desc()).first()
        acknowledgement = "PENDING" if answered is None else (
            "ACCEPTED" if answered.event_type == "ASSIGNMENT_ACCEPTED" else "REJECTED"
        )
        items.append({
            "id": row.id,
            "exception_type": row.exception_type,
            "severity": row.severity,
            "status": row.status,
            "reference_type": row.reference_type,
            "summary": row.summary,
            "source_present": row.source_present,
            "first_detected_at": row.first_detected_at,
            "assigned_at": assignment.occurred_at,
            "acknowledgement_status": acknowledgement,
            "acknowledged_at": answered.occurred_at if answered else None,
            "response_target_hours": {"CRITICAL": 0.5, "HIGH": 2, "MEDIUM": 8, "LOW": 24}.get(row.severity, 24),
        })
    return {"total": len(items), "items": items, "scope": "CURRENT_USER_ACTIVE_ASSIGNMENTS"}


@router.get("/reconciliation/exceptions/queue")
def list_persisted_reconciliation_exceptions(
    status_filter: Optional[str] = Query(default=None, alias="status", pattern="^(OPEN|IN_REVIEW|RESOLVED|DISMISSED)$"),
    severity: Optional[str] = Query(default=None, pattern="^(CRITICAL|HIGH|MEDIUM|LOW)$"),
    assigned_to_id: Optional[int] = Query(default=None, ge=1),
    exception_type: Optional[str] = Query(default=None, max_length=64),
    source_present: Optional[bool] = Query(default=None),
    sla_overdue: Optional[bool] = Query(default=None),
    unassigned_only: bool = Query(default=False),
    open_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    query = db.query(ProcurementReconciliationException)
    if status_filter:
        query = query.filter(ProcurementReconciliationException.status == status_filter)
    if severity:
        query = query.filter(ProcurementReconciliationException.severity == severity)
    if assigned_to_id:
        query = query.filter(ProcurementReconciliationException.assigned_to_id == assigned_to_id)
    if exception_type:
        query = query.filter(ProcurementReconciliationException.exception_type == exception_type)
    if source_present is not None:
        query = query.filter(ProcurementReconciliationException.source_present == source_present)
    rows = query.order_by(
        ProcurementReconciliationException.last_detected_at.desc(),
        ProcurementReconciliationException.id.desc(),
    ).limit(1000).all()
    now = datetime.now(timezone.utc)
    sla_hours_for = _reconciliation_sla_hours

    def age_hours(row):
        detected = row.first_detected_at
        if detected.tzinfo is None:
            detected = detected.replace(tzinfo=timezone.utc)
        return max(int((now - detected).total_seconds() // 3600), 0)

    def sla_clock(row):
        return _reconciliation_sla_clock(row, now)

    if open_only:
        rows = [row for row in rows if row.status in ("OPEN", "IN_REVIEW")]
    if unassigned_only:
        rows = [row for row in rows if row.assigned_to_id is None]
    if sla_overdue is not None:
        rows = [
            row for row in rows
            if (row.status in ("OPEN", "IN_REVIEW") and sla_clock(row)["breached"]) == sla_overdue
        ]

    open_rows = [row for row in rows if row.status in ("OPEN", "IN_REVIEW")]
    overdue_rows = [
        row for row in open_rows
        if sla_clock(row)["breached"]
    ]
    return {
        "total": len(rows),
        "sla_summary": {
            "open_or_in_review": len(open_rows),
            "sla_overdue": len(overdue_rows),
            "sla_paused": sum(1 for row in open_rows if sla_clock(row)["paused"]),
            "unassigned_open": sum(1 for row in open_rows if row.assigned_to_id is None),
            "missing_from_latest_detection": sum(1 for row in rows if not row.source_present),
        },
        "exceptions": [{
            "id": row.id, "exception_type": row.exception_type, "severity": row.severity,
            "status": row.status, "reference_type": row.reference_type, "reference_id": row.reference_id,
            "sla_policy_id": row.sla_policy_id,
            "source_present": row.source_present, "missed_refresh_count": row.missed_refresh_count,
            "age_hours": age_hours(row), "sla_hours": sla_hours_for(row),
            "sla_elapsed_hours": sla_clock(row)["elapsed_hours"],
            "sla_remaining_hours": sla_clock(row)["remaining_hours"],
            "sla_paused": sla_clock(row)["paused"],
            "sla_paused_at": sla_clock(row)["paused_at"],
            "sla_paused_seconds": sla_clock(row)["paused_seconds"],
            "sla_due_at": sla_clock(row)["due_at"],
            "sla_breached_at": sla_clock(row)["breached_at"],
            "sla_overdue": row.status in ("OPEN", "IN_REVIEW") and sla_clock(row)["breached"],
            "amount_paise": row.amount_paise, "matched_amount_paise": row.matched_amount_paise,
            "unmatched_amount_paise": row.unmatched_amount_paise, "summary": row.summary,
            "assigned_to_id": row.assigned_to_id, "first_detected_at": row.first_detected_at,
            "last_detected_at": row.last_detected_at, "resolved_at": row.resolved_at,
            "resolution_note": row.resolution_note, "root_cause_code": row.root_cause_code,
            "resolution_checklist": row.resolution_checklist, "reopen_count": row.reopen_count,
            "resolution_review_status": row.resolution_review_status,
            "detection_snapshot": row.detection_snapshot,
        } for row in rows],
    }

@router.get("/analytics/reconciliation-dashboard")
def get_reconciliation_dashboard(
    from_date: Optional[date] = Query(default=None, description="Inclusive first-detected date (UTC)."),
    to_date: Optional[date] = Query(default=None, description="Inclusive first-detected date (UTC)."),
    severity: Optional[str] = Query(default=None, pattern="^(CRITICAL|HIGH|MEDIUM|LOW)$"),
    status_filter: Optional[str] = Query(default=None, alias="status", pattern="^(OPEN|IN_REVIEW|RESOLVED|DISMISSED)$"),
    assigned_to_id: Optional[int] = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    """Read-only finance dashboard over persisted reconciliation investigations.

    Monetary investigation amounts are reported by exception type only. Bank-side
    and payment-side exceptions can describe the same transfer, so they are never
    combined into a single exposure total. Possible duplicates are count-only.
    """
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must be on or before to_date.")

    query = db.query(ProcurementReconciliationException)
    if from_date:
        query = query.filter(ProcurementReconciliationException.first_detected_at >= datetime.combine(
            from_date, datetime.min.time(), tzinfo=timezone.utc
        ))
    if to_date:
        query = query.filter(ProcurementReconciliationException.first_detected_at <= datetime.combine(
            to_date, datetime.max.time(), tzinfo=timezone.utc
        ))
    if severity:
        query = query.filter(ProcurementReconciliationException.severity == severity)
    if status_filter:
        query = query.filter(ProcurementReconciliationException.status == status_filter)
    if assigned_to_id:
        query = query.filter(ProcurementReconciliationException.assigned_to_id == assigned_to_id)

    rows = query.order_by(ProcurementReconciliationException.first_detected_at, ProcurementReconciliationException.id).all()
    now = datetime.now(timezone.utc)
    sla_hours_for = _reconciliation_sla_hours

    def as_utc(value):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    def age_hours(row):
        return max(int(((as_utc(row.resolved_at) or now) - as_utc(row.first_detected_at)).total_seconds() // 3600), 0)

    status_counts = {key: 0 for key in ("OPEN", "IN_REVIEW", "RESOLVED", "DISMISSED")}
    severity_counts = {key: 0 for key in ("CRITICAL", "HIGH", "MEDIUM", "LOW")}
    type_counts = {}
    aging = {
        "under_4_hours": 0, "4_to_24_hours": 0, "1_to_3_days": 0,
        "3_to_7_days": 0, "over_7_days": 0,
    }
    sla_breaches = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    sla_paused_open_count = 0
    exposure_by_type = {}
    exposure_by_supplier = {}
    exposure_by_bank_account = {}
    workload = {}
    resolution_hours = []
    opened_by_day = {}
    resolved_by_day = {}
    sla_breaches_by_day = {}
    resolved_by_user = {}

    open_statuses = {"OPEN", "IN_REVIEW"}
    amount_bearing_types = {
        "UNMATCHED_BANK_DEBIT", "PARTIAL_BANK_DEBIT_MATCH",
        "UNCLASSIFIED_BANK_CREDIT", "UNRECONCILED_SUPPLIER_PAYMENT",
        "PARTIALLY_RECONCILED_SUPPLIER_PAYMENT", "OVERDUE_APPROVED_PAYMENT_REQUEST",
    }

    for row in rows:
        status_counts[row.status] = status_counts.get(row.status, 0) + 1
        severity_counts[row.severity] = severity_counts.get(row.severity, 0) + 1
        type_bucket = type_counts.setdefault(row.exception_type, {"count": 0, "open_count": 0, "resolved_count": 0})
        type_bucket["count"] += 1
        if row.status in open_statuses:
            type_bucket["open_count"] += 1
        if row.status == "RESOLVED":
            type_bucket["resolved_count"] += 1

        first_detected = as_utc(row.first_detected_at)
        opened_day = first_detected.date().isoformat()
        opened_by_day[opened_day] = opened_by_day.get(opened_day, 0) + 1

        elapsed = age_hours(row)
        sla_clock = _reconciliation_sla_clock(row, now)
        breached = (
            row.status in open_statuses or row.status == "RESOLVED"
        ) and sla_clock["breached"]
        if breached:
            sla_breaches_by_day[opened_day] = sla_breaches_by_day.get(opened_day, 0) + 1
        if row.status in open_statuses:
            if sla_clock["paused"]:
                sla_paused_open_count += 1
            if elapsed < 4:
                aging["under_4_hours"] += 1
            elif elapsed < 24:
                aging["4_to_24_hours"] += 1
            elif elapsed < 72:
                aging["1_to_3_days"] += 1
            elif elapsed < 168:
                aging["3_to_7_days"] += 1
            else:
                aging["over_7_days"] += 1
            if breached:
                sla_breaches[row.severity] += 1
        elif row.status == "RESOLVED" and row.resolved_at is not None:
            resolution_hours.append(elapsed)
            resolved_day = as_utc(row.resolved_at).date().isoformat()
            resolved_by_day[resolved_day] = resolved_by_day.get(resolved_day, 0) + 1
            resolver_key = str(row.resolved_by_id) if row.resolved_by_id is not None else "UNKNOWN"
            resolved_by_user[resolver_key] = resolved_by_user.get(resolver_key, 0) + 1

        # Do not include possible-duplicate candidates in monetary totals.
        # Keep each exception category separate to avoid summing both sides of
        # one bank transfer (statement debit and supplier payment).
        if row.exception_type in amount_bearing_types:
            bucket = exposure_by_type.setdefault(row.exception_type, {
                "exception_count": 0, "open_count": 0, "investigation_amount_paise": 0,
                "unmatched_amount_paise": 0,
            })
            bucket["exception_count"] += 1
            if row.status in open_statuses:
                bucket["open_count"] += 1
                bucket["investigation_amount_paise"] += max(int(row.amount_paise or 0), 0)
                bucket["unmatched_amount_paise"] += max(int(row.unmatched_amount_paise or 0), 0)

                snapshot = row.detection_snapshot or {}
                vendor_id = snapshot.get("vendor_id")
                vendor_name = snapshot.get("vendor_name")
                if vendor_id is not None:
                    supplier_key = str(vendor_id)
                    supplier_bucket = exposure_by_supplier.setdefault(supplier_key, {
                        "vendor_id": int(vendor_id), "vendor_name": vendor_name,
                        "exception_count": 0, "investigation_amount_paise": 0,
                        "unmatched_amount_paise": 0,
                    })
                    supplier_bucket["exception_count"] += 1
                    supplier_bucket["investigation_amount_paise"] += max(int(row.amount_paise or 0), 0)
                    supplier_bucket["unmatched_amount_paise"] += max(int(row.unmatched_amount_paise or 0), 0)

                bank_account_ref = snapshot.get("bank_account_ref")
                if bank_account_ref and row.reference_type == "BANK_STATEMENT_LINE":
                    account_bucket = exposure_by_bank_account.setdefault(str(bank_account_ref), {
                        "bank_account_ref": str(bank_account_ref), "exception_count": 0,
                        "investigation_amount_paise": 0, "unmatched_amount_paise": 0,
                    })
                    account_bucket["exception_count"] += 1
                    account_bucket["investigation_amount_paise"] += max(int(row.amount_paise or 0), 0)
                    account_bucket["unmatched_amount_paise"] += max(int(row.unmatched_amount_paise or 0), 0)

        assignee_key = str(row.assigned_to_id) if row.assigned_to_id is not None else "UNASSIGNED"
        assignee = workload.setdefault(assignee_key, {
            "user_id": row.assigned_to_id, "assigned_total": 0, "assigned_open": 0,
            "assigned_resolved_count": 0, "assigned_sla_overdue": 0,
            "oldest_open_age_hours": 0,
            "open_by_severity": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
        })
        assignee["assigned_total"] += 1
        if row.status in open_statuses:
            assignee["assigned_open"] += 1
            assignee["open_by_severity"][row.severity] = assignee["open_by_severity"].get(row.severity, 0) + 1
            assignee["oldest_open_age_hours"] = max(assignee["oldest_open_age_hours"], elapsed)
            if breached:
                assignee["assigned_sla_overdue"] += 1
        if row.status == "RESOLVED":
            assignee["assigned_resolved_count"] += 1

    user_ids = {
        int(key) for key in workload
        if key != "UNASSIGNED"
    }
    users = {
        user.id: user.full_name
        for user in db.query(User).filter(User.id.in_(user_ids)).all()
    } if user_ids else {}
    workload_rows = []
    for key, item in workload.items():
        workload_rows.append({
            **item,
            "user_name": users.get(item["user_id"]) if item["user_id"] is not None else None,
        })
    workload_rows.sort(key=lambda item: (-item["assigned_open"], item["user_id"] or 0))

    resolved_count = status_counts["RESOLVED"]
    median_resolution = None
    average_resolution = None
    if resolution_hours:
        ordered = sorted(resolution_hours)
        middle = len(ordered) // 2
        median_resolution = ordered[middle] if len(ordered) % 2 else round((ordered[middle - 1] + ordered[middle]) / 2, 2)
        average_resolution = round(sum(ordered) / len(ordered), 2)

    resolver_ids = {int(key) for key in resolved_by_user if key != "UNKNOWN"}
    resolver_names = {
        user.id: user.full_name
        for user in db.query(User).filter(User.id.in_(resolver_ids)).all()
    } if resolver_ids else {}
    resolver_rows = [{
        "user_id": int(key) if key != "UNKNOWN" else None,
        "user_name": resolver_names.get(int(key)) if key != "UNKNOWN" else None,
        "resolved_count": count,
    } for key, count in resolved_by_user.items()]
    resolver_rows.sort(key=lambda item: (-item["resolved_count"], item["user_id"] or 0))
    supplier_exposure_rows = sorted(
        exposure_by_supplier.values(),
        key=lambda item: (-item["unmatched_amount_paise"], item["vendor_id"]),
    )
    bank_account_exposure_rows = sorted(
        exposure_by_bank_account.values(),
        key=lambda item: (-item["unmatched_amount_paise"], item["bank_account_ref"]),
    )

    trend_days = sorted(set(opened_by_day) | set(resolved_by_day) | set(sla_breaches_by_day))
    return {
        "as_of": now,
        "filters": {
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
            "severity": severity,
            "status": status_filter,
            "assigned_to_id": assigned_to_id,
            "date_basis": "first_detected_at (UTC); resolution trend uses resolved_at (UTC)",
        },
        "overview": {
            "total_exceptions": len(rows),
            "open_count": status_counts["OPEN"],
            "in_review_count": status_counts["IN_REVIEW"],
            "resolved_count": resolved_count,
            "dismissed_count": status_counts["DISMISSED"],
            "source_missing_open_count": sum(1 for row in rows if row.status in open_statuses and not row.source_present),
            "unassigned_open_count": sum(1 for row in rows if row.status in open_statuses and row.assigned_to_id is None),
            "sla_breached_open_count": sum(sla_breaches.values()),
            "sla_paused_open_count": sla_paused_open_count,
        },
        "by_status": status_counts,
        "by_severity": severity_counts,
        "by_exception_type": type_counts,
        "open_aging": aging,
        "sla_breaches_by_severity": sla_breaches,
        "sla_breaches_by_detection_day": [{
            "date": day, "breached_count": sla_breaches_by_day.get(day, 0),
        } for day in sorted(sla_breaches_by_day)],
        "resolution_performance": {
            "resolved_count": resolved_count,
            "average_resolution_hours": average_resolution,
            "median_resolution_hours": median_resolution,
            "method": "Elapsed time from first detection to terminal resolution; dismissed items are excluded.",
        },
        "daily_trend": [{
            "date": day,
            "opened_count": opened_by_day.get(day, 0),
            "resolved_count": resolved_by_day.get(day, 0),
        } for day in trend_days],
        "finance_workload": workload_rows,
        "resolved_by_user": resolver_rows,
        "investigation_amounts_by_exception_type": exposure_by_type,
        "investigation_amounts_by_supplier": supplier_exposure_rows,
        "investigation_amounts_by_bank_account": bank_account_exposure_rows,
        "amount_methodology": {
            "currency_unit": "INR paise",
            "not_a_confirmed_loss": True,
            "possible_duplicate_supplier_payment": "Counted as an investigation signal only; excluded from monetary aggregation.",
            "no_cross_type_total": "Amounts are separated by exception type because a bank debit and its supplier-payment record may represent the same transfer. Do not sum categories into a portfolio loss figure.",
        },
        "controls": {"read_only": True, "persisted_snapshot_only": True},
    }


@router.get("/reconciliation/exceptions/{exception_id}/assignment-recommendations")
def get_reconciliation_assignment_recommendations(
    exception_id: int,
    limit: int = Query(default=5, ge=1, le=10),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    """Rank active branch staff for a manual, workload-aware assignment decision.

    Recommendations are advisory only. Role suitability is inferred from the
    user's assigned role permissions; workload is calculated from all current
    branch investigations, independent of dashboard date filters.
    """
    target = db.query(ProcurementReconciliationException).filter(
        ProcurementReconciliationException.id == exception_id
    ).one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="Reconciliation exception not found.")
    if target.status in {"RESOLVED", "DISMISSED"}:
        raise HTTPException(status_code=409, detail="Terminal investigations cannot be assigned.")

    active_users = db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .where(User.status == UserStatusEnum.ACTIVE)
        .order_by(User.full_name.asc(), User.id.asc())
    ).scalars().unique().all()

    investigations = db.query(ProcurementReconciliationException).all()
    now = datetime.now(timezone.utc)
    workload = {}
    resolved_durations = {}
    all_resolved_durations = []

    def _utc(value):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    for item in investigations:
        user_id = item.assigned_to_id
        if user_id is None:
            continue
        stats = workload.setdefault(user_id, {
            "open": 0, "overdue": 0, "severity": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
            "resolved": 0,
        })
        first = _utc(item.first_detected_at)
        end = _utc(item.resolved_at) if item.resolved_at else now
        elapsed_hours = max((end - first).total_seconds() / 3600, 0) if first else 0
        if item.status in {"OPEN", "IN_REVIEW"}:
            stats["open"] += 1
            stats["severity"][item.severity] = stats["severity"].get(item.severity, 0) + 1
            if _reconciliation_sla_clock(item, now)["breached"]:
                stats["overdue"] += 1
        elif item.status == "RESOLVED" and item.resolved_at and first:
            stats["resolved"] += 1
            resolved_durations.setdefault(user_id, []).append(elapsed_hours)
            all_resolved_durations.append(elapsed_hours)

    overall_median = None
    if all_resolved_durations:
        values = sorted(all_resolved_durations)
        mid = len(values) // 2
        overall_median = values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2

    candidates = []
    for user in active_users:
        stats = workload.get(user.id, {
            "open": 0, "overdue": 0, "severity": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
            "resolved": 0,
        })
        permission_codes = {
            permission.code
            for role in user.roles
            for permission in role.permissions
        }
        finance_permissions = sorted(code for code in permission_codes if code.startswith("finance:"))
        procurement_permissions = sorted(code for code in permission_codes if code.startswith("procurement:"))
        finance_suitable = bool(finance_permissions)
        procurement_suitable = bool(procurement_permissions)
        severity_load = stats["severity"].get(target.severity, 0)
        score = 0
        reasons = []
        if finance_suitable:
            score += 35
            reasons.append("Has finance permissions on an assigned role")
        elif procurement_suitable:
            score += 20
            reasons.append("Has procurement permissions but no finance permission detected")
        else:
            reasons.append("No finance/procurement role permission detected")
        open_score = max(0, 25 - stats["open"] * 5)
        overdue_score = max(0, 20 - stats["overdue"] * 8)
        severity_score = max(0, 10 - severity_load * 5)
        score += open_score + overdue_score + severity_score
        reasons.append(f"{stats['open']} open investigations")
        reasons.append(f"{stats['overdue']} SLA-overdue investigations")
        reasons.append(f"{severity_load} open {target.severity.lower()} investigations")
        durations = resolved_durations.get(user.id, [])
        median_hours = None
        if durations:
            ordered = sorted(durations)
            middle = len(ordered) // 2
            median_hours = round(ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2, 2)
            if overall_median is not None:
                if median_hours <= overall_median:
                    score += 10
                    reasons.append("Historical attributed resolution time is at or below branch median")
                else:
                    score = max(0, score - 5)
                    reasons.append("Historical attributed resolution time is above branch median")
            else:
                reasons.append("Historical resolution baseline is not yet available")
        else:
            reasons.append("No resolved investigations currently attributed to this user")
        candidates.append({
            "user_id": user.id,
            "user_name": user.full_name,
            "login_id": user.login_id,
            "roles": [{"code": role.code, "name": role.name} for role in user.roles],
            "finance_suitable": finance_suitable,
            "procurement_suitable": procurement_suitable,
            "finance_permissions": finance_permissions,
            "procurement_permissions": procurement_permissions,
            "current_assignee": user.id == target.assigned_to_id,
            "open_count": stats["open"],
            "overdue_count": stats["overdue"],
            "open_by_severity": stats["severity"],
            "resolved_count": stats["resolved"],
            "median_resolution_hours": median_hours,
            "score": min(100, score),
            "reasons": reasons,
        })

    candidates.sort(key=lambda item: (
        not item["finance_suitable"], -item["score"], item["overdue_count"],
        item["open_count"], item["user_name"].lower(), item["user_id"],
    ))
    ranked = candidates[:limit]
    return {
        "exception_id": exception_id,
        "target_severity": target.severity,
        "current_assignee_id": target.assigned_to_id,
        "recommendations": ranked,
        "methodology": {
            "manual_confirmation_required": True,
            "workload_scope": "All persisted investigations in the current branch, not the dashboard date filter.",
            "historical_resolution_scope": "Resolved cases still attributed to the assignee; median elapsed hours compared with the branch median.",
            "role_suitability": "Finance permissions receive the strongest suitability weight; procurement-only permissions receive a lower supporting weight.",
            "score_weights": {"role_suitability": 35, "open_workload": 25, "overdue_workload": 20, "target_severity_load": 10, "historical_resolution": 10},
            "automatic_assignment": False,
        },
    }


@router.get("/reconciliation/assignees")
def list_reconciliation_assignees(
    q: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    """Return active users from the current branch for reconciliation assignment."""
    statement = (
        select(User)
        .options(selectinload(User.roles))
        .where(User.status == UserStatusEnum.ACTIVE)
        .order_by(User.full_name.asc(), User.id.asc())
    )
    if q:
        term = f"%{q.strip().lower()}%"
        statement = statement.where(
            or_(func.lower(User.full_name).like(term), func.lower(User.login_id).like(term))
        )
    users = db.execute(statement.limit(limit)).scalars().unique().all()
    return {
        "items": [
            {
                "id": user.id,
                "full_name": user.full_name,
                "login_id": user.login_id,
                "roles": [{"code": role.code, "name": role.name} for role in user.roles],
            }
            for user in users
        ],
        "count": len(users),
        "limit": limit,
    }


@router.patch("/reconciliation/exceptions/{exception_id}/assignment")
def assign_reconciliation_exception(
    exception_id: int, payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:write")),
):
    row = db.query(ProcurementReconciliationException).filter(
        ProcurementReconciliationException.id == exception_id
    ).with_for_update().one_or_none()
    if row is None: raise HTTPException(status_code=404, detail="Reconciliation exception not found.")
    assignee_id = payload.get("assigned_to_id")
    if assignee_id is not None:
        assignee = db.get(User, assignee_id)
        if assignee is None or assignee.status != UserStatusEnum.ACTIVE:
            raise HTTPException(status_code=422, detail="Assignee must be an active user in this branch.")
    if row.status in {"RESOLVED", "DISMISSED"}:
        raise HTTPException(status_code=409, detail="Terminal investigations cannot be reassigned.")
    old = row.assigned_to_id
    reason = str(payload.get("note") or payload.get("reason") or "").strip()
    if old != assignee_id and old is not None and len(reason) < 10:
        raise HTTPException(status_code=422, detail="A reassignment reason of at least 10 characters is required.")
    row.assigned_to_id = assignee_id
    now = datetime.now(timezone.utc)
    active_escalation_policy = db.query(ProcurementReconciliationEscalationPolicy).filter(
        ProcurementReconciliationEscalationPolicy.status == "PUBLISHED",
        ProcurementReconciliationEscalationPolicy.effective_from <= now,
        or_(
            ProcurementReconciliationEscalationPolicy.effective_to.is_(None),
            ProcurementReconciliationEscalationPolicy.effective_to > now,
        ),
    ).order_by(ProcurementReconciliationEscalationPolicy.version.desc()).first()
    policy_targets = active_escalation_policy.response_targets_hours if active_escalation_policy else {
        "CRITICAL": 0.5, "HIGH": 2, "MEDIUM": 8, "LOW": 24
    }
    notification_preferences = active_escalation_policy.notification_preferences if active_escalation_policy else {
        "email_enabled": True, "assignee": True, "assigning_manager": True, "finance_managers": False
    }
    target_hours = float(policy_targets.get(row.severity, 24))
    escalation_levels = active_escalation_policy.escalation_levels if active_escalation_policy else []
    _record_reconciliation_event(db, row, "ASSIGNED", current_user.id,
        old_assignee_id=old, new_assignee_id=assignee_id,
        note=reason or None,
        event_metadata={
            "acknowledgement_status": "PENDING" if assignee_id is not None else "NOT_REQUIRED",
            "assigned_at": now.isoformat(),
            "reassignment": old is not None and old != assignee_id,
            "escalation_policy_id": active_escalation_policy.id if active_escalation_policy else None,
            "escalation_policy_version": active_escalation_policy.version if active_escalation_policy else None,
            "response_target_hours": target_hours,
            "notification_preferences": notification_preferences,
            "escalation_levels": escalation_levels,
        })
    assignment_event = db.query(ProcurementReconciliationExceptionEvent).filter(
        ProcurementReconciliationExceptionEvent.exception_id == row.id,
        ProcurementReconciliationExceptionEvent.event_type == "ASSIGNED",
    ).order_by(
        ProcurementReconciliationExceptionEvent.id.desc()
    ).first()
    db.commit()
    notification_status = "NOT_REQUIRED"
    if assignee_id is not None and not assignee.email:
        notification_status = "EMAIL_UNAVAILABLE"
    if assignee_id is not None:
        tenant_context = resolve_tenant_context(request)
        try:
            if assignee.email and notification_preferences.get("email_enabled", True) and notification_preferences.get("assignee", True):
                enqueue_task("email.send", {
                "recipient": assignee.email,
                "subject": f"Reconciliation investigation #{row.id} assigned to you",
                "text_body": (
                    f"Hello {assignee.full_name},\\n\\n"
                    f"Investigation #{row.id} ({row.severity}) has been assigned to you at "
                    f"{tenant_context.hospital_name}.\\n"
                    f"{row.summary}\\n\\n"
                    f"Please open My Assigned Investigations in Avinya HMS and acknowledge "
                    f"the assignment within {target_hours:g} hour(s)."
                ),
            }, sync_fallback=False)
            if assignment_event is not None:
                enqueue_task("procurement.reconciliation.assignment_escalation", {
                    "tenant_subdomain": tenant_context.subdomain_slug,
                    "exception_id": row.id,
                    "assignment_event_id": assignment_event.id,
                    "assignee_id": assignee_id,
                    "response_target_hours": target_hours,
                    "notification_preferences": notification_preferences,
                    "escalation_levels": escalation_levels,
                }, delay_seconds=int(min(
                    [float(level.get("after_hours", target_hours)) for level in escalation_levels]
                    or [target_hours]
                ) * 3600), sync_fallback=False)
            notification_status = (
                "DISABLED_BY_POLICY" if not notification_preferences.get("email_enabled", True)
                else ("QUEUED" if assignee.email else "ASSIGNEE_EMAIL_UNAVAILABLE")
            )
        except Exception:
            # Assignment is already committed. Queue failures are observable to the
            # caller but must never roll back or silently undo the assignment.
            notification_status = "QUEUE_UNAVAILABLE"
    return {
        "id": row.id, "assigned_to_id": row.assigned_to_id, "status": row.status,
        "acknowledgement_status": "PENDING" if assignee_id is not None else "NOT_REQUIRED",
        "assigned_at": now,
        "notification_status": notification_status,
    }


@router.post("/reconciliation/exceptions/{exception_id}/assignment-response")
def respond_to_reconciliation_assignment(
    exception_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Allow only the current assignee to accept or reject a pending assignment."""
    row = db.query(ProcurementReconciliationException).filter(
        ProcurementReconciliationException.id == exception_id
    ).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Reconciliation exception not found.")
    if row.status in {"RESOLVED", "DISMISSED"}:
        raise HTTPException(status_code=409, detail="Terminal investigations cannot receive assignment responses.")
    if row.assigned_to_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the currently assigned staff member can respond.")
    decision = str(payload.get("decision", "")).upper()
    if decision not in {"ACCEPT", "REJECT"}:
        raise HTTPException(status_code=422, detail="Decision must be ACCEPT or REJECT.")
    note = str(payload.get("reason") or "").strip()
    if decision == "REJECT" and len(note) < 10:
        raise HTTPException(status_code=422, detail="A rejection reason of at least 10 characters is required.")
    latest_assignment = db.query(ProcurementReconciliationExceptionEvent).filter(
        ProcurementReconciliationExceptionEvent.exception_id == row.id,
        ProcurementReconciliationExceptionEvent.event_type == "ASSIGNED",
        ProcurementReconciliationExceptionEvent.new_assignee_id == current_user.id,
    ).order_by(
        ProcurementReconciliationExceptionEvent.occurred_at.desc(),
        ProcurementReconciliationExceptionEvent.id.desc(),
    ).first()
    if latest_assignment is None:
        raise HTTPException(status_code=409, detail="No active assignment event was found.")
    assignment_state = (latest_assignment.event_metadata or {}).get("acknowledgement_status", "PENDING")
    prior_response = db.query(ProcurementReconciliationExceptionEvent.id).filter(
        ProcurementReconciliationExceptionEvent.exception_id == row.id,
        ProcurementReconciliationExceptionEvent.id > latest_assignment.id,
        ProcurementReconciliationExceptionEvent.event_type.in_(["ASSIGNMENT_ACCEPTED", "ASSIGNMENT_REJECTED"]),
    ).first()
    if assignment_state != "PENDING" or prior_response is not None:
        raise HTTPException(status_code=409, detail="This assignment has already been answered.")
    event_type = "ASSIGNMENT_ACCEPTED" if decision == "ACCEPT" else "ASSIGNMENT_REJECTED"
    if decision == "REJECT":
        # Rejection returns the investigation to the manager's unassigned queue.
        row.assigned_to_id = None
    _record_reconciliation_event(
        db, row, event_type, current_user.id,
        old_assignee_id=current_user.id,
        new_assignee_id=current_user.id if decision == "ACCEPT" else None,
        note=note or None,
        event_metadata={"assignment_event_id": latest_assignment.id, "responded_at": datetime.now(timezone.utc).isoformat()},
    )
    db.commit()
    return {"exception_id": row.id, "decision": decision, "assigned_to_id": row.assigned_to_id, "recorded": True}


@router.get("/reconciliation/exceptions/escalations")
def list_reconciliation_assignment_escalations(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    """Read-only queue of unacknowledged assignments and their escalation delivery state.

    The existing Redis worker performs scheduled escalation. Notification state here
    reflects queue job status, not proof of recipient mailbox delivery.
    """
    rows = db.query(ProcurementReconciliationException).filter(
        ProcurementReconciliationException.status.in_(["OPEN", "IN_REVIEW"]),
        ProcurementReconciliationException.assigned_to_id.is_not(None),
    ).all()
    now = datetime.now(timezone.utc)
    active_escalation_policy = db.query(ProcurementReconciliationEscalationPolicy).filter(
        ProcurementReconciliationEscalationPolicy.status == "PUBLISHED",
        ProcurementReconciliationEscalationPolicy.effective_from <= now,
        or_(
            ProcurementReconciliationEscalationPolicy.effective_to.is_(None),
            ProcurementReconciliationEscalationPolicy.effective_to > now,
        ),
    ).order_by(ProcurementReconciliationEscalationPolicy.version.desc()).first()
    response_targets = active_escalation_policy.response_targets_hours if active_escalation_policy else {
        "CRITICAL": 0.5, "HIGH": 2, "MEDIUM": 8, "LOW": 24
    }
    candidates = []
    for row in rows:
        assignment = db.query(ProcurementReconciliationExceptionEvent).filter(
            ProcurementReconciliationExceptionEvent.exception_id == row.id,
            ProcurementReconciliationExceptionEvent.event_type == "ASSIGNED",
            ProcurementReconciliationExceptionEvent.new_assignee_id == row.assigned_to_id,
        ).order_by(
            ProcurementReconciliationExceptionEvent.occurred_at.desc(),
            ProcurementReconciliationExceptionEvent.id.desc(),
        ).first()
        if assignment is None:
            continue
        metadata = assignment.event_metadata or {}
        if metadata.get("acknowledgement_status", "PENDING") != "PENDING":
            continue
        answered = db.query(ProcurementReconciliationExceptionEvent.id).filter(
            ProcurementReconciliationExceptionEvent.exception_id == row.id,
            ProcurementReconciliationExceptionEvent.id > assignment.id,
            ProcurementReconciliationExceptionEvent.event_type.in_(["ASSIGNMENT_ACCEPTED", "ASSIGNMENT_REJECTED"]),
        ).first()
        if answered is not None:
            continue
        assigned_at = assignment.occurred_at
        if assigned_at.tzinfo is None:
            assigned_at = assigned_at.replace(tzinfo=timezone.utc)
        elapsed_hours = max((now - assigned_at).total_seconds() / 3600, 0)
        target_hours = float(metadata.get("response_target_hours", response_targets.get(row.severity, 24)))
        if elapsed_hours < target_hours or _reconciliation_sla_clock(row, now)["paused"]:
            continue
        escalation_events = db.query(ProcurementReconciliationExceptionEvent).filter(
            ProcurementReconciliationExceptionEvent.exception_id == row.id,
            ProcurementReconciliationExceptionEvent.id > assignment.id,
            ProcurementReconciliationExceptionEvent.event_type == "ESCALATION_NOTIFIED",
        ).order_by(ProcurementReconciliationExceptionEvent.id.desc()).all()
        delivery_jobs = []
        for event in escalation_events:
            for job_id in (event.event_metadata or {}).get("notification_job_ids", []):
                task = get_task_status(job_id)
                delivery_jobs.append({
                    "job_id": job_id,
                    "queue_status": task.get("status") if task else "UNKNOWN_OR_EXPIRED",
                    "completed_at": task.get("completed_at") if task else None,
                    "delivery_result": (
                        {"sent": task["result"].get("sent"), "error": task["result"].get("error")}
                        if task and isinstance(task.get("result"), dict) else None
                    ),
                    "queue_error": task.get("error") if task else None,
                })
        candidates.append({
            "exception_id": row.id,
            "severity": row.severity,
            "status": row.status,
            "assigned_to_id": row.assigned_to_id,
            "assigned_at": assignment.occurred_at,
            "unacknowledged_hours": round(elapsed_hours, 2),
            "response_target_hours": target_hours,
            "escalation_due": True,
            "escalation_levels_notified": len(escalation_events),
            "notification_jobs": delivery_jobs,
            "delivery_semantics": "QUEUE_STATUS_ONLY_NOT_MAILBOX_DELIVERY",
        })
    candidates.sort(key=lambda item: (-item["unacknowledged_hours"], item["exception_id"]))
    return {"total": len(candidates), "items": candidates[:limit], "automatic_escalation": True}


_RECONCILIATION_RESOLUTION_CHECKLISTS = {
    "UNMATCHED_BANK_DEBIT": ("bank_statement_verified", "bank_account_and_period_confirmed", "payment_or_expense_traced", "supporting_evidence_reviewed"),
    "PARTIAL_BANK_DEBIT_MATCH": ("statement_line_balance_verified", "remaining_amount_explained", "matching_allocations_reviewed"),
    "UNCLASSIFIED_BANK_CREDIT": ("credit_source_identified", "bank_reference_verified", "ledger_treatment_documented"),
    "UNRECONCILED_SUPPLIER_PAYMENT": ("supplier_payment_verified", "bank_statement_match_or_reason_documented", "invoice_allocations_reviewed"),
    "PARTIALLY_RECONCILED_SUPPLIER_PAYMENT": ("partial_match_balance_verified", "remaining_amount_explained", "payment_allocations_reviewed"),
    "POSSIBLE_DUPLICATE_SUPPLIER_PAYMENT": ("candidate_transactions_compared", "bank_debits_independently_verified", "duplicate_or_false_positive_conclusion_documented"),
    "OVERDUE_APPROVED_PAYMENT_REQUEST": ("request_status_verified", "execution_or_cancellation_confirmed", "supplier_balance_rechecked"),
}

_RECONCILIATION_ROOT_CAUSES = {
    "DATA_ENTRY_ERROR", "BANK_FEED_DELAY", "DUPLICATE_PAYMENT",
    "REFERENCE_MISMATCH", "SUPPLIER_DISPUTE", "BANK_CHARGES",
    "TIMING_DIFFERENCE", "PROCESS_GAP", "SYSTEM_INTEGRATION",
    "FALSE_POSITIVE", "OTHER",
}


@router.get("/reconciliation/exceptions/{exception_id}/resolution-guidance")
def get_reconciliation_resolution_guidance(
    exception_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    row = db.get(ProcurementReconciliationException, exception_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Reconciliation exception not found.")
    required = _RECONCILIATION_RESOLUTION_CHECKLISTS.get(
        row.exception_type, ("investigation_evidence_reviewed", "financial_impact_rechecked", "conclusion_documented")
    )
    return {
        "exception_id": row.id,
        "exception_type": row.exception_type,
        "root_cause_codes": sorted(_RECONCILIATION_ROOT_CAUSES),
        "required_checklist": [{"code": code, "required": True} for code in required],
        "independent_review_required": row.severity in {"CRITICAL", "HIGH"},
        "resolution_policy": "All checklist items must be true; this records investigation completion, not a substitute for correcting the source ledger.",
    }


def _resume_reconciliation_sla_on_close(db: Session, row, actor_user_id: int, at: datetime):
    if row.sla_paused_at is None:
        return
    paused_at = row.sla_paused_at
    if paused_at.tzinfo is None:
        paused_at = paused_at.replace(tzinfo=timezone.utc)
    row.sla_paused_seconds = max(int(row.sla_paused_seconds or 0), 0) + max(
        int((at - paused_at).total_seconds()), 0
    )
    row.sla_paused_at = None
    clock = _reconciliation_sla_clock(row, at)
    if clock["breached"] and row.sla_breached_at is None:
        row.sla_breached_at = clock["breached_at"]
    _record_reconciliation_event(
        db, row, "SLA_AUTO_RESUMED", actor_user_id,
        note="SLA pause closed automatically when the investigation reached a terminal state.",
        event_metadata={
            "pause_started_at": paused_at.isoformat(),
            "pause_ended_at": at.isoformat(),
            "pause_duration_seconds": max(int((at - paused_at).total_seconds()), 0),
            "reason": "INVESTIGATION_CLOSED",
        },
    )


@router.post("/reconciliation/exceptions/{exception_id}/sla/pause")
def pause_reconciliation_exception_sla(
    exception_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:sla:manage")),
):
    row = db.query(ProcurementReconciliationException).filter(
        ProcurementReconciliationException.id == exception_id
    ).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Reconciliation exception not found.")
    if row.status not in {"OPEN", "IN_REVIEW"}:
        raise HTTPException(status_code=409, detail="Only active investigations can have their SLA clock paused.")
    if row.sla_paused_at is not None:
        raise HTTPException(status_code=409, detail="The SLA clock is already paused.")
    reason = str(payload.get("reason") or "").strip()
    if len(reason) < 10 or len(reason) > 2000:
        raise HTTPException(status_code=422, detail="A pause reason between 10 and 2000 characters is required.")
    now = datetime.now(timezone.utc)
    before = _reconciliation_sla_clock(row, now)
    if before["breached"] and row.sla_breached_at is None:
        row.sla_breached_at = before["breached_at"]
    row.sla_paused_at = now
    _record_reconciliation_event(
        db, row, "SLA_PAUSED", current_user.id,
        note=reason,
        event_metadata={
            "paused_at": now.isoformat(),
            "elapsed_active_seconds": before["elapsed_seconds"],
            "sla_target_hours": before["target_hours"],
            "already_breached": before["breached"],
            "breached_at": before["breached_at"].isoformat() if before["breached_at"] else None,
        },
    )
    db.commit()
    clock = _reconciliation_sla_clock(row, now)
    return {
        "id": row.id, "paused": True, "sla_paused_at": row.sla_paused_at,
        "sla_paused_seconds": clock["paused_seconds"],
        "sla_elapsed_hours": clock["elapsed_hours"],
        "sla_remaining_hours": clock["remaining_hours"],
        "sla_overdue": clock["breached"], "sla_breached_at": clock["breached_at"],
    }


@router.post("/reconciliation/exceptions/{exception_id}/sla/resume")
def resume_reconciliation_exception_sla(
    exception_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:sla:manage")),
):
    row = db.query(ProcurementReconciliationException).filter(
        ProcurementReconciliationException.id == exception_id
    ).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Reconciliation exception not found.")
    if row.status not in {"OPEN", "IN_REVIEW"}:
        raise HTTPException(status_code=409, detail="Only active investigations can resume an SLA clock.")
    if row.sla_paused_at is None:
        raise HTTPException(status_code=409, detail="The SLA clock is not paused.")
    reason = str(payload.get("reason") or "").strip()
    if len(reason) < 10 or len(reason) > 2000:
        raise HTTPException(status_code=422, detail="A resume reason between 10 and 2000 characters is required.")
    now = datetime.now(timezone.utc)
    paused_at = row.sla_paused_at
    if paused_at.tzinfo is None:
        paused_at = paused_at.replace(tzinfo=timezone.utc)
    pause_duration = max(int((now - paused_at).total_seconds()), 0)
    row.sla_paused_seconds = max(int(row.sla_paused_seconds or 0), 0) + pause_duration
    row.sla_paused_at = None
    clock = _reconciliation_sla_clock(row, now)
    if clock["breached"] and row.sla_breached_at is None:
        row.sla_breached_at = clock["breached_at"]
    _record_reconciliation_event(
        db, row, "SLA_RESUMED", current_user.id,
        note=reason,
        event_metadata={
            "paused_at": paused_at.isoformat(),
            "resumed_at": now.isoformat(),
            "pause_duration_seconds": pause_duration,
            "total_paused_seconds": row.sla_paused_seconds,
            "elapsed_active_seconds": clock["elapsed_seconds"],
            "sla_target_hours": clock["target_hours"],
            "breached": clock["breached"],
            "breached_at": clock["breached_at"].isoformat() if clock["breached_at"] else None,
        },
    )
    db.commit()
    return {
        "id": row.id, "paused": False, "sla_paused_at": None,
        "sla_paused_seconds": row.sla_paused_seconds,
        "sla_elapsed_hours": clock["elapsed_hours"],
        "sla_remaining_hours": clock["remaining_hours"],
        "sla_overdue": clock["breached"], "sla_breached_at": clock["breached_at"],
    }


@router.patch("/reconciliation/exceptions/{exception_id}/status")
def update_reconciliation_exception_status(
    exception_id: int, payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:approve")),
):
    row = db.query(ProcurementReconciliationException).filter(
        ProcurementReconciliationException.id == exception_id
    ).with_for_update().one_or_none()
    if row is None: raise HTTPException(status_code=404, detail="Reconciliation exception not found.")
    new_status = str(payload.get("status", "")).upper()
    note = str(payload.get("note") or "").strip()
    if new_status not in {"IN_REVIEW", "RESOLVED", "DISMISSED", "OPEN"}:
        raise HTTPException(status_code=422, detail="Unsupported reconciliation exception status.")
    if new_status in {"RESOLVED", "DISMISSED"} and len(note) < 10:
        raise HTTPException(status_code=422, detail="A resolution or dismissal note of at least 10 characters is required.")
    if row.status in {"RESOLVED", "DISMISSED"}:
        raise HTTPException(status_code=409, detail="Terminal exceptions require the explicit reopen workflow.")
    if row.resolution_review_status == "PENDING":
        raise HTTPException(status_code=409, detail="A submitted resolution must be independently reviewed before the investigation can change state.")
    if new_status == row.status:
        raise HTTPException(status_code=409, detail="Exception is already in the requested status.")

    root_cause_code = str(payload.get("root_cause_code") or "").upper().strip() or None
    checklist = payload.get("resolution_checklist") or {}
    if new_status == "RESOLVED":
        if root_cause_code not in _RECONCILIATION_ROOT_CAUSES:
            raise HTTPException(status_code=422, detail="A valid root_cause_code is required to resolve an investigation.")
        if not isinstance(checklist, dict):
            raise HTTPException(status_code=422, detail="resolution_checklist must be an object of checklist codes and boolean values.")
        required = _RECONCILIATION_RESOLUTION_CHECKLISTS.get(
            row.exception_type, ("investigation_evidence_reviewed", "financial_impact_rechecked", "conclusion_documented")
        )
        incomplete = [code for code in required if checklist.get(code) is not True]
        if incomplete:
            raise HTTPException(status_code=422, detail={"message": "Complete every required resolution checklist item.", "incomplete_items": incomplete})
        row.root_cause_code = root_cause_code
        row.resolution_checklist = {code: True for code in required}

    old_status = row.status
    if new_status in {"RESOLVED", "DISMISSED"} and row.severity in {"CRITICAL", "HIGH"}:
        row.resolution_review_status = "PENDING"
        row.resolution_submitted_status = new_status
        row.status = "IN_REVIEW"
        row.resolution_submitted_by_id = current_user.id
        row.resolution_reviewed_by_id = None
        row.resolution_reviewed_at = None
        row.resolution_note = note
        _record_reconciliation_event(db, row, "RESOLUTION_SUBMITTED", current_user.id,
            old_status=old_status, new_status="IN_REVIEW", note=note,
            event_metadata={"root_cause_code": row.root_cause_code, "resolution_checklist": row.resolution_checklist})
    else:
        row.status = new_status
        if new_status in {"RESOLVED", "DISMISSED"}:
            row.resolved_at = datetime.now(timezone.utc)
            _resume_reconciliation_sla_on_close(db, row, current_user.id, row.resolved_at)
            row.resolved_by_id = current_user.id
            row.resolution_note = note
            row.resolution_review_status = "NOT_REQUIRED" if new_status == "RESOLVED" else "NOT_REQUIRED"
        _record_reconciliation_event(db, row, "STATUS_CHANGED", current_user.id,
            old_status=old_status, new_status=new_status, note=note or None,
            event_metadata={
                "root_cause_code": row.root_cause_code if new_status == "RESOLVED" else None,
                "resolution_checklist": row.resolution_checklist if new_status == "RESOLVED" else {},
            })
    db.commit()
    return {"id": row.id, "status": row.status, "resolved_at": row.resolved_at,
            "resolution_note": row.resolution_note, "root_cause_code": row.root_cause_code,
            "resolution_checklist": row.resolution_checklist,
            "resolution_review_status": row.resolution_review_status}


@router.patch("/reconciliation/exceptions/{exception_id}/resolution-review")
def review_reconciliation_resolution(
    exception_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:approve")),
):
    row = db.query(ProcurementReconciliationException).filter(
        ProcurementReconciliationException.id == exception_id
    ).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Reconciliation exception not found.")
    if row.severity not in {"CRITICAL", "HIGH"} or row.resolution_review_status != "PENDING" or row.status != "IN_REVIEW":
        raise HTTPException(status_code=409, detail="This investigation has no pending independent resolution review.")
    if row.resolution_submitted_by_id == current_user.id:
        raise HTTPException(status_code=409, detail="The investigator cannot approve or reject their own resolution.")
    decision = str(payload.get("decision") or "").upper().strip()
    note = str(payload.get("note") or "").strip()
    if decision not in {"APPROVE", "REJECT"}:
        raise HTTPException(status_code=422, detail="Review decision must be APPROVE or REJECT.")
    if len(note) < 10 or len(note) > 2000:
        raise HTTPException(status_code=422, detail="A review note between 10 and 2000 characters is required.")
    now = datetime.now(timezone.utc)
    row.resolution_reviewed_by_id = current_user.id
    row.resolution_reviewed_at = now
    row.resolution_review_status = "APPROVED" if decision == "APPROVE" else "REJECTED"
    old_status = row.status
    if decision == "APPROVE":
        row.status = row.resolution_submitted_status or "RESOLVED"
        row.resolved_at = now
        _resume_reconciliation_sla_on_close(db, row, current_user.id, now)
        row.resolved_by_id = row.resolution_submitted_by_id
    else:
        row.status = "IN_REVIEW"
        row.resolved_at = None
        row.resolved_by_id = None
    _record_reconciliation_event(
        db, row, "RESOLUTION_REVIEWED", current_user.id,
        old_status=old_status, new_status=row.status, note=note,
        event_metadata={
            "decision": decision,
            "submitted_by_id": row.resolution_submitted_by_id,
            "review_status": row.resolution_review_status,
        },
    )
    db.commit()
    return {
        "id": row.id, "status": row.status,
        "resolution_review_status": row.resolution_review_status,
        "resolved_at": row.resolved_at, "resolved_by_id": row.resolved_by_id,
    }


@router.post("/reconciliation/exceptions/{exception_id}/reopen")
def reopen_reconciliation_exception(
    exception_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:approve")),
):
    row = db.query(ProcurementReconciliationException).filter(
        ProcurementReconciliationException.id == exception_id
    ).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Reconciliation exception not found.")
    reason = str(payload.get("reason") or "").strip()
    if len(reason) < 10 or len(reason) > 2000:
        raise HTTPException(status_code=422, detail="A reopen reason between 10 and 2000 characters is required.")
    if row.status not in {"RESOLVED", "DISMISSED"}:
        raise HTTPException(status_code=409, detail="Only resolved or dismissed investigations can be reopened.")
    old_status = row.status
    prior_resolution = {
        "root_cause_code": row.root_cause_code,
        "resolution_note": row.resolution_note,
        "resolution_checklist": row.resolution_checklist,
        "resolved_by_id": row.resolved_by_id,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
    }
    row.status = "OPEN"
    row.reopen_count = (row.reopen_count or 0) + 1
    row.resolved_at = None
    row.resolved_by_id = None
    row.resolution_note = None
    row.root_cause_code = None
    row.resolution_checklist = {}
    row.resolution_review_status = "NOT_REQUIRED"
    row.resolution_submitted_status = None
    row.resolution_submitted_by_id = None
    row.resolution_reviewed_by_id = None
    row.resolution_reviewed_at = None
    _record_reconciliation_event(
        db, row, "REOPENED", current_user.id,
        old_status=old_status, new_status="OPEN", note=reason,
        event_metadata={"prior_resolution": prior_resolution, "reopen_count": row.reopen_count},
    )
    db.commit()
    return {"id": row.id, "status": row.status, "reopen_count": row.reopen_count}


@router.post("/reconciliation/exceptions/{exception_id}/notes", status_code=status.HTTP_201_CREATED)
def add_reconciliation_exception_note(
    exception_id: int, payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:write")),
):
    row = db.get(ProcurementReconciliationException, exception_id)
    if row is None: raise HTTPException(status_code=404, detail="Reconciliation exception not found.")
    note = str(payload.get("note") or "").strip()
    if not note or len(note) > 4000:
        raise HTTPException(status_code=422, detail="Note is required and must not exceed 4000 characters.")
    _record_reconciliation_event(db, row, "NOTE_ADDED", current_user.id, note=note)
    db.commit()
    return {"exception_id": row.id, "note_recorded": True}


@router.get("/reconciliation/exceptions/{exception_id}/history")
def get_reconciliation_exception_history(
    exception_id: int, db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    if db.get(ProcurementReconciliationException, exception_id) is None:
        raise HTTPException(status_code=404, detail="Reconciliation exception not found.")
    events = db.query(ProcurementReconciliationExceptionEvent).filter(
        ProcurementReconciliationExceptionEvent.exception_id == exception_id
    ).order_by(ProcurementReconciliationExceptionEvent.occurred_at, ProcurementReconciliationExceptionEvent.id).all()
    return {"exception_id": exception_id, "events": [{
        "id": event.id, "event_type": event.event_type, "actor_user_id": event.actor_user_id,
        "old_status": event.old_status, "new_status": event.new_status,
        "old_assignee_id": event.old_assignee_id, "new_assignee_id": event.new_assignee_id,
        "note": event.note, "event_metadata": event.event_metadata, "occurred_at": event.occurred_at,
    } for event in events]}


# ---------------------------------------------------------------------------
# Reconciliation governance: escalation policy, quality analytics, reporting,
# and export accountability. All queries are tenant-schema scoped by get_db.
# ---------------------------------------------------------------------------

@router.get("/reconciliation/escalation-policies")
def list_reconciliation_escalation_policies(
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    items = db.query(ProcurementReconciliationEscalationPolicy).order_by(
        ProcurementReconciliationEscalationPolicy.version.desc()
    ).limit(50).all()
    now = datetime.now(timezone.utc)
    active = db.query(ProcurementReconciliationEscalationPolicy).filter(
        ProcurementReconciliationEscalationPolicy.status == "PUBLISHED",
        ProcurementReconciliationEscalationPolicy.effective_from <= now,
        or_(
            ProcurementReconciliationEscalationPolicy.effective_to.is_(None),
            ProcurementReconciliationEscalationPolicy.effective_to > now,
        ),
    ).order_by(ProcurementReconciliationEscalationPolicy.version.desc()).first()
    return {
        "active_policy_id": active.id if active else None,
        "active_policy_version": active.version if active else None,
        "baseline_response_targets_hours": {"CRITICAL": 0.5, "HIGH": 2, "MEDIUM": 8, "LOW": 24},
        "items": [{
            "id": row.id, "version": row.version, "status": row.status,
            "response_targets_hours": row.response_targets_hours,
            "escalation_levels": row.escalation_levels,
            "notification_preferences": row.notification_preferences,
            "change_reason": row.change_reason, "effective_from": row.effective_from,
            "effective_to": row.effective_to, "created_at": row.created_at,
            "published_at": row.published_at,
        } for row in items],
    }


@router.post("/reconciliation/escalation-policies", status_code=status.HTTP_201_CREATED)
def create_reconciliation_escalation_policy(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:sla:manage")),
):
    targets = payload.get("response_targets_hours")
    required = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    if not isinstance(targets, dict) or set(targets) != required or any(
        not isinstance(v, (int, float)) or isinstance(v, bool) or v <= 0 or v > 8760 for v in targets.values()
    ):
        raise HTTPException(status_code=422, detail="Response targets must define positive hours for all four severities.")
    levels = payload.get("escalation_levels")
    if not isinstance(levels, list) or not 1 <= len(levels) <= 5:
        raise HTTPException(status_code=422, detail="Define between one and five escalation levels.")
    normalized_levels = []
    prior = 0
    for index, level in enumerate(levels, start=1):
        if not isinstance(level, dict):
            raise HTTPException(status_code=422, detail="Each escalation level must be an object.")
        after_hours = level.get("after_hours")
        if not isinstance(after_hours, (int, float)) or isinstance(after_hours, bool) or after_hours <= prior or after_hours > 8760:
            raise HTTPException(status_code=422, detail="Escalation levels must have strictly increasing positive after_hours.")
        normalized_levels.append({
            "level": index, "after_hours": float(after_hours),
            "notify_assignee": bool(level.get("notify_assignee", True)),
            "notify_assigning_manager": bool(level.get("notify_assigning_manager", True)),
            "notify_finance_managers": bool(level.get("notify_finance_managers", False)),
        })
        prior = after_hours
    preferences = payload.get("notification_preferences") or {
        "email_enabled": True, "assignee": True, "assigning_manager": True, "finance_managers": False,
    }
    allowed_preferences = {"email_enabled", "assignee", "assigning_manager", "finance_managers"}
    if not isinstance(preferences, dict) or set(preferences) - allowed_preferences or any(type(v) is not bool for v in preferences.values()):
        raise HTTPException(status_code=422, detail="Notification preferences contain unsupported or non-boolean settings.")
    reason = str(payload.get("change_reason") or "").strip()
    if not 10 <= len(reason) <= 1000:
        raise HTTPException(status_code=422, detail="A change reason between 10 and 1000 characters is required.")
    latest = db.query(func.max(ProcurementReconciliationEscalationPolicy.version)).scalar() or 0
    row = ProcurementReconciliationEscalationPolicy(
        policy_key="DEFAULT", version=latest + 1, status="DRAFT",
        response_targets_hours={k: float(v) for k, v in targets.items()},
        escalation_levels=normalized_levels, notification_preferences=preferences,
        change_reason=reason, effective_from=datetime.now(timezone.utc),
        created_by_id=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "version": row.version, "status": row.status}


@router.post("/reconciliation/escalation-policies/{policy_id}/publish")
def publish_reconciliation_escalation_policy(
    policy_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:sla:manage")),
):
    row = db.query(ProcurementReconciliationEscalationPolicy).filter(
        ProcurementReconciliationEscalationPolicy.id == policy_id
    ).with_for_update().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Escalation policy not found.")
    if row.status != "DRAFT":
        raise HTTPException(status_code=409, detail="Only draft escalation policies can be published.")
    publish_now = datetime.now(timezone.utc)
    effective_from = payload.get("effective_from")
    if isinstance(effective_from, str):
        try:
            effective_from = datetime.fromisoformat(effective_from.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=422, detail="effective_from must be an ISO-8601 timestamp.")
    effective_from = effective_from or publish_now
    if effective_from.tzinfo is None:
        effective_from = effective_from.replace(tzinfo=timezone.utc)
    if effective_from < publish_now:
        raise HTTPException(status_code=422, detail="Escalation policy effective_from cannot be in the past.")
    active = db.query(ProcurementReconciliationEscalationPolicy).filter(
        ProcurementReconciliationEscalationPolicy.status == "PUBLISHED",
        ProcurementReconciliationEscalationPolicy.effective_to.is_(None),
    ).with_for_update().all()
    if active and row.version <= max(prior.version for prior in active):
        raise HTTPException(status_code=409, detail="A newer escalation policy version is already published.")
    if active and any(effective_from <= prior.effective_from for prior in active):
        raise HTTPException(status_code=422, detail="A new escalation policy must take effect after the currently published version.")
    for prior in active:
        prior.effective_to = effective_from
    row.status = "PUBLISHED"
    row.effective_from = effective_from
    row.published_by_id = current_user.id
    row.published_at = publish_now
    db.commit()
    return {"id": row.id, "version": row.version, "status": row.status, "effective_from": row.effective_from}


@router.get("/reconciliation/governance/closure-quality")
def get_reconciliation_closure_quality(
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    """Measure case-level reopen rate for cases resolved during the requested period.

    The denominator is distinct cases with a RESOLVED transition in the period.
    The numerator is distinct cases from that cohort with a later REOPENED event.
    Reopen events are also reported separately so repeated reopen cycles remain visible.
    """
    period_start = datetime.combine(from_date, datetime.min.time(), tzinfo=timezone.utc) if from_date else None
    period_end = datetime.combine(to_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc) if to_date else None

    resolution_query = db.query(ProcurementReconciliationExceptionEvent).filter(
        ProcurementReconciliationExceptionEvent.new_status == "RESOLVED",
        ProcurementReconciliationExceptionEvent.event_type.in_(("STATUS_CHANGED", "RESOLUTION_REVIEWED")),
    )
    if period_start:
        resolution_query = resolution_query.filter(ProcurementReconciliationExceptionEvent.occurred_at >= period_start)
    if period_end:
        resolution_query = resolution_query.filter(ProcurementReconciliationExceptionEvent.occurred_at < period_end)
    resolution_events = resolution_query.order_by(
        ProcurementReconciliationExceptionEvent.occurred_at.asc(),
        ProcurementReconciliationExceptionEvent.id.asc(),
    ).all()
    resolution_by_case = {}
    for event in resolution_events:
        resolution_by_case.setdefault(event.exception_id, []).append(event.occurred_at)
    resolved_case_ids = set(resolution_by_case)

    reopen_events = []
    if resolved_case_ids:
        reopen_events = db.query(ProcurementReconciliationExceptionEvent).filter(
            ProcurementReconciliationExceptionEvent.exception_id.in_(resolved_case_ids),
            ProcurementReconciliationExceptionEvent.event_type == "REOPENED",
        ).order_by(
            ProcurementReconciliationExceptionEvent.occurred_at.asc(),
            ProcurementReconciliationExceptionEvent.id.asc(),
        ).all()

    # Count a case once if it was reopened after a qualifying resolution in the period.
    reopened_case_ids = set()
    cause_counts = {}
    reopened_cases_by_root = {}
    for event in reopen_events:
        prior_resolutions = resolution_by_case.get(event.exception_id, [])
        if not any(event.occurred_at > resolved_at for resolved_at in prior_resolutions):
            continue
        reopened_case_ids.add(event.exception_id)
        root = (event.event_metadata or {}).get("prior_resolution", {}).get("root_cause_code") or "UNCLASSIFIED"
        bucket = cause_counts.setdefault(root, {"resolved_count": 0, "reopened_count": 0, "reopen_events": 0, "exception_types": {}})
        bucket["reopen_events"] += 1
        reopened_cases_by_root.setdefault(root, set()).add(event.exception_id)

    case_rows = db.query(ProcurementReconciliationException).filter(
        ProcurementReconciliationException.id.in_(resolved_case_ids)
    ).all() if resolved_case_ids else []
    case_by_id = {row.id: row for row in case_rows}
    for root, case_ids in reopened_cases_by_root.items():
        cause_counts[root]["reopened_count"] = len(case_ids)
    for case_id in resolved_case_ids:
        row = case_by_id.get(case_id)
        root = (row.root_cause_code if row else None) or "UNCLASSIFIED"
        bucket = cause_counts.setdefault(root, {"resolved_count": 0, "reopened_count": 0, "reopen_events": 0, "exception_types": {}})
        bucket["resolved_count"] += 1
        if row:
            bucket["exception_types"][row.exception_type] = bucket["exception_types"].get(row.exception_type, 0) + 1

    # Resolution-time and review metrics use current terminal state for cohort cases;
    # reopen-rate itself is event-cohort based and does not lose cases reopened after closure.
    resolved = [row for row in case_rows if row.status == "RESOLVED" and row.resolved_at and row.first_detected_at]
    resolution_hours = []
    for row in resolved:
        start = row.first_detected_at.replace(tzinfo=timezone.utc) if row.first_detected_at.tzinfo is None else row.first_detected_at
        end = row.resolved_at.replace(tzinfo=timezone.utc) if row.resolved_at.tzinfo is None else row.resolved_at
        resolution_hours.append(max((end - start).total_seconds() / 3600, 0))
    ordered_hours = sorted(resolution_hours)
    median_hours = None
    if ordered_hours:
        middle = len(ordered_hours) // 2
        median_hours = (
            round((ordered_hours[middle - 1] + ordered_hours[middle]) / 2, 2)
            if len(ordered_hours) % 2 == 0 else round(ordered_hours[middle], 2)
        )
    review_required = sum(1 for row in resolved if row.resolution_review_status != "NOT_REQUIRED")
    review_approved = sum(1 for row in resolved if row.resolution_review_status == "APPROVED")
    review_rejected = sum(1 for row in resolved if row.resolution_review_status == "REJECTED")
    reopened_event_count = sum(
        1 for event in reopen_events
        if any(event.occurred_at > resolved_at for resolved_at in resolution_by_case.get(event.exception_id, []))
    )
    return {
        "resolved_count": len(resolved_case_ids),
        "currently_resolved_count": len(resolved),
        "average_resolution_hours": round(sum(resolution_hours) / len(resolution_hours), 2) if resolution_hours else None,
        "median_resolution_hours": median_hours,
        "reopened_cases": len(reopened_case_ids),
        "reopen_events": reopened_event_count,
        "reopen_rate_percent": round((len(reopened_case_ids) / len(resolved_case_ids)) * 100, 2) if resolved_case_ids else 0,
        "independent_review": {"required": review_required, "approved": review_approved, "rejected": review_rejected},
        "root_causes": sorted([{"root_cause_code": key, **value} for key, value in cause_counts.items()],
                              key=lambda x: (x["reopened_count"], x["resolved_count"]), reverse=True),
        "methodology": "Case-level reopen rate: distinct cases with a RESOLVED transition in the selected period that have a subsequent REOPENED event, divided by distinct cases with a RESOLVED transition in that period. Repeated reopen cycles count once in the rate and separately in reopen_events. Resolution duration and independent-review metrics reflect the current terminal state of this resolution cohort.",
    }

@router.get("/reconciliation/governance/dashboard")
def get_reconciliation_governance_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    rows = db.query(ProcurementReconciliationException).all()
    open_rows = [r for r in rows if r.status in {"OPEN", "IN_REVIEW"}]
    overdue = [r for r in open_rows if _reconciliation_sla_clock(r)["breached"]]
    quality = get_reconciliation_closure_quality(from_date=None, to_date=None, db=db, _=None)
    return {
        "as_of": datetime.now(timezone.utc),
        "overview": {
            "total_cases": len(rows), "open_cases": len(open_rows),
            "sla_breached_open": len(overdue),
            "unassigned_open": sum(1 for r in open_rows if r.assigned_to_id is None),
            "resolved_cases": sum(1 for r in rows if r.status == "RESOLVED"),
            "reopened_cases": sum(1 for r in rows if int(r.reopen_count or 0) > 0),
        },
        "closure_quality": quality,
    }


@router.post("/reconciliation/governance/monthly-reports", status_code=status.HTTP_201_CREATED)
def create_reconciliation_monthly_governance_report(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:sla:manage")),
):
    try:
        start = date.fromisoformat(str(payload.get("period_start")))
        end = date.fromisoformat(str(payload.get("period_end")))
    except ValueError:
        raise HTTPException(status_code=422, detail="period_start and period_end must be ISO dates.")
    if start.day != 1 or (end + timedelta(days=1)).day != 1 or end < start:
        raise HTTPException(status_code=422, detail="Report periods must cover one or more complete calendar months.")
    existing = db.query(ProcurementReconciliationGovernanceReport).filter(
        ProcurementReconciliationGovernanceReport.period_start == start,
        ProcurementReconciliationGovernanceReport.period_end == end,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="A governance report already exists for this period.")
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    cases = db.query(ProcurementReconciliationException).filter(
        ProcurementReconciliationException.first_detected_at >= start_dt,
        ProcurementReconciliationException.first_detected_at < end_dt,
    ).all()
    resolved = [r for r in cases if r.status == "RESOLVED"]
    reopen_events_period = db.query(ProcurementReconciliationExceptionEvent).filter(
        ProcurementReconciliationExceptionEvent.event_type == "REOPENED",
        ProcurementReconciliationExceptionEvent.occurred_at >= start_dt,
        ProcurementReconciliationExceptionEvent.occurred_at < end_dt,
    ).all()
    resolution_hours = []
    for case in resolved:
        first = case.first_detected_at.replace(tzinfo=timezone.utc) if case.first_detected_at.tzinfo is None else case.first_detected_at
        closed = case.resolved_at.replace(tzinfo=timezone.utc) if case.resolved_at.tzinfo is None else case.resolved_at
        resolution_hours.append(max((closed - first).total_seconds() / 3600, 0))
    ordered_resolution_hours = sorted(resolution_hours)
    median_resolution_hours = None
    if ordered_resolution_hours:
        middle = len(ordered_resolution_hours) // 2
        median_resolution_hours = (
            round((ordered_resolution_hours[middle - 1] + ordered_resolution_hours[middle]) / 2, 2)
            if len(ordered_resolution_hours) % 2 == 0 else round(ordered_resolution_hours[middle], 2)
        )
    snapshot = {
        "period_start": start.isoformat(), "period_end": end.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_basis": "CURRENT_STATE_OF_CASES_FIRST_DETECTED_IN_PERIOD",
        "case_count": len(cases),
        "by_status": {key: sum(1 for r in cases if r.status == key) for key in ("OPEN", "IN_REVIEW", "RESOLVED", "DISMISSED")},
        "by_severity": {key: sum(1 for r in cases if r.severity == key) for key in ("CRITICAL", "HIGH", "MEDIUM", "LOW")},
        "sla_breached_open": sum(1 for r in cases if r.status in {"OPEN", "IN_REVIEW"} and _reconciliation_sla_clock(r)["breached"]),
        "resolved_count": len(resolved),
        "average_resolution_hours": round(sum(resolution_hours) / len(resolution_hours), 2) if resolution_hours else None,
        "median_resolution_hours": median_resolution_hours,
        "reopened_event_count": len(reopen_events_period),
        "reopened_cases_in_period": len({event.exception_id for event in reopen_events_period}),
        "cohort_cumulative_reopen_count": sum(int(r.reopen_count or 0) for r in cases),
        "root_causes": {},
    }
    for row in resolved:
        key = row.root_cause_code or "UNCLASSIFIED"
        snapshot["root_causes"][key] = snapshot["root_causes"].get(key, 0) + 1
    report = ProcurementReconciliationGovernanceReport(
        period_start=start, period_end=end, report_snapshot=snapshot, generated_by_id=current_user.id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {"id": report.id, "period_start": start, "period_end": end, "snapshot": snapshot, "created_at": report.created_at}


@router.get("/reconciliation/governance/monthly-reports")
def list_reconciliation_monthly_governance_reports(
    limit: int = Query(default=24, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    rows = db.query(ProcurementReconciliationGovernanceReport).order_by(
        ProcurementReconciliationGovernanceReport.period_start.desc()
    ).limit(limit).all()
    return {"items": [{"id": r.id, "period_start": r.period_start, "period_end": r.period_end,
                       "snapshot": r.report_snapshot, "generated_by_id": r.generated_by_id,
                       "created_at": r.created_at} for r in rows]}


@router.get("/reconciliation/audit-exports")
def list_reconciliation_audit_exports(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    rows = db.query(ProcurementReconciliationAuditExport).order_by(
        ProcurementReconciliationAuditExport.requested_at.desc()
    ).limit(limit).all()
    return {"items": [{
        "id": r.id, "exception_id": r.exception_id, "export_type": r.export_type,
        "status": r.status, "file_sha256": r.file_sha256, "file_size_bytes": r.file_size_bytes,
        "filter_snapshot": r.filter_snapshot, "actor_user_id": r.actor_user_id,
        "actor_email": r.actor_email, "requested_at": r.requested_at,
    } for r in rows]}
