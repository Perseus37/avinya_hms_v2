import logging

from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import select, func
from fastapi import HTTPException

from backend.core.database import tenant_engine_pool
from backend.domains.procurement.models import (
    StoreIndent,
    StoreIndentItem,
    PatientIndentIssueAllocation,
    PatientIndentReturnEvent,
    IndentStatusEnum,
    GoodsReceiptNote,
    GoodsReceiptItem,
    PurchaseOrder,
    PurchaseOrderItem,
    POStatusEnum,
    GRNStatusEnum,
    PurchaseReturnRecord,
    PurchaseReturnItem,
    VendorInvoice,
    VendorInvoiceItem,
    VendorInvoiceStatusEnum,
)
from backend.domains.pharmacy.models import InventoryBatch, MedicationMaster
from backend.domains.finance.models import ExpenseRecord, ExpenseCategoryEnum, ExpenseStatusEnum
from backend.domains.procurement.ai_parser import DonutInvoiceParser
from backend.domains.billing.models import Invoice, InvoiceLineItem, InvoiceStatusEnum
from backend.domains.billing.rcm_services import recalculate_invoice_totals
from backend.domains.reports.pdf import render_html_pdf
from backend.domains.reports.templates import render_sandboxed_template

logger = logging.getLogger(__name__)

def process_grn_acceptance(db: Session, grn: GoodsReceiptNote, current_user_id: int):
    """Atomically validate accepted quantities, update the PO, and provision pharmacy batches."""
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == grn.po_id
    ).with_for_update().one_or_none()
    if po is None or po.status not in {POStatusEnum.APPROVED, POStatusEnum.PARTIALLY_RECEIVED}:
        raise ValueError("Goods receipt requires an approved purchase order.")

    po_items = db.query(PurchaseOrderItem).filter(
        PurchaseOrderItem.po_id == po.id
    ).with_for_update().all()
    po_items_by_id = {item.id: item for item in po_items}
    accepted_by_item = {}
    for grn_item in grn.items:
        po_item = po_items_by_id.get(grn_item.po_item_id)
        if po_item is None:
            raise ValueError("Goods receipt item does not belong to its purchase order.")
        accepted_by_item[po_item.id] = accepted_by_item.get(po_item.id, 0) + grn_item.accepted_quantity
    for item_id, accepted_quantity in accepted_by_item.items():
        po_item = po_items_by_id[item_id]
        if accepted_quantity > po_item.quantity_ordered - po_item.quantity_received:
            raise ValueError("Accepted goods exceed the remaining purchase-order quantity.")

    for grn_item in grn.items:
        if grn_item.accepted_quantity > 0:
            po_item = po_items_by_id[grn_item.po_item_id]
            po_item.quantity_received += grn_item.accepted_quantity

            if po_item.medication_id:
                new_batch = InventoryBatch(
                    medication_id=po_item.medication_id,
                    batch_number=grn_item.batch_number,
                    expiry_date=grn_item.expiry_date,
                    stock_quantity=grn_item.accepted_quantity,
                    unit_price_paise=grn_item.unit_price_paise,
                    created_by_id=current_user_id
                )
                db.add(new_batch)
                db.flush()
                grn_item.created_batch_id = new_batch.id

    all_po_items_fulfilled = all(
        item.quantity_received >= item.quantity_ordered for item in po_items
    )
    po.status = POStatusEnum.COMPLETED if all_po_items_fulfilled else POStatusEnum.PARTIALLY_RECEIVED

def trigger_donut_invoice_extraction(db_name: str, invoice_id: int, document_path: str):
    """Extract invoice data in a fresh tenant session while retaining the source file."""
    session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=tenant_engine_pool.get_engine(db_name),
    )
    db = session_factory()
    try:
        invoice = db.get(VendorInvoice, invoice_id)
        if not invoice:
            logger.error("Invoice extraction target %s no longer exists.", invoice_id)
            return

        parser = DonutInvoiceParser()
        extracted_data = parser.extract_invoice_data(document_path)

        # Map Donut's nested output to strict procurement schema
        invoice.invoice_number = extracted_data.get("invoice_number", "UNKNOWN")

        raw_date = extracted_data.get("date")
        if raw_date:
            try:
                invoice.invoice_date = datetime.strptime(raw_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        total_price_str = str(extracted_data.get("total_price", "0")).replace(",", "").replace(".", "")
        invoice.total_amount_paise = int(total_price_str) if total_price_str.isdigit() else 0

        # Parse line items
        line_items = extracted_data.get("line_items", [])
        if isinstance(line_items, dict):
            line_items = [line_items]

        for item in line_items:
            qty_str = str(item.get("quantity", "1")).replace(",", "")
            price_str = str(item.get("price", "0")).replace(",", "").replace(".", "")

            db.add(VendorInvoiceItem(
                invoice_id=invoice.id,
                item_description=item.get("name", "Unknown Item"),
                batch_number=item.get("batch_number", "UNKNOWN_BATCH"),
                expiry_date=datetime.now(timezone.utc), # Requires heuristic refinement based on Donut output
                quantity=int(qty_str) if qty_str.isdigit() else 1,
                unit_price_paise=int(price_str) if price_str.isdigit() else 0,
                total_price_paise=(int(qty_str) * int(price_str)) if (qty_str.isdigit() and price_str.isdigit()) else 0
            ))

        invoice.status = VendorInvoiceStatusEnum.PENDING_VERIFICATION
        db.commit()

    except Exception:
        db.rollback()
        invoice = db.get(VendorInvoice, invoice_id)
        if invoice:
            logger.exception("AI extraction failed for vendor invoice %s.", invoice_id)
            invoice.notes = "AI extraction failed; the source document is retained for manual review."
            invoice.status = VendorInvoiceStatusEnum.PENDING_VERIFICATION
            db.commit()
    finally:
        db.close()

def execute_3_way_match(db: Session, invoice: VendorInvoice) -> VendorInvoiceStatusEnum:
    """Validates Vendor Invoice against PO and GRN for financial integrity."""
    if not invoice.po_id:
        return VendorInvoiceStatusEnum.PENDING_VERIFICATION

    po = db.get(PurchaseOrder, invoice.po_id)
    if (
        not po
        or po.vendor_id != invoice.vendor_id
        or po.status
        not in {
            POStatusEnum.APPROVED,
            POStatusEnum.PARTIALLY_RECEIVED,
            POStatusEnum.COMPLETED,
        }
    ):
        return VendorInvoiceStatusEnum.PENDING_VERIFICATION
    # A financial three-way match requires an accepted goods receipt.
    if not invoice.grn_id:
        return VendorInvoiceStatusEnum.PENDING_VERIFICATION

    receipt = db.get(GoodsReceiptNote, invoice.grn_id)
    if (
        not receipt
        or receipt.po_id != po.id
        or receipt.status != GRNStatusEnum.ACCEPTED
    ):
        return VendorInvoiceStatusEnum.PENDING_VERIFICATION
    calculated_gross = invoice.subtotal_paise + invoice.tax_amount_paise - invoice.discount_paise

    # Rule 1: Mathematical Integrity Tolerance (+/- 100 paise)
    if abs(calculated_gross - invoice.total_amount_paise) > 100:
        return VendorInvoiceStatusEnum.PENDING_VERIFICATION

    # Rule 2: Aggregate invoice quantities by PO line before comparing limits.
    po_lines_by_id = {line.id: line for line in po.items}
    invoiced_by_po_line = {}
    for item in invoice.items:
        if not item.po_item_id or item.po_item_id not in po_lines_by_id:
            return VendorInvoiceStatusEnum.PENDING_VERIFICATION
        invoiced_by_po_line[item.po_item_id] = (
            invoiced_by_po_line.get(item.po_item_id, 0) + item.quantity
        )

    received_by_po_line = {}
    if receipt:
        for receipt_item in receipt.items:
            received_by_po_line[receipt_item.po_item_id] = (
                received_by_po_line.get(receipt_item.po_item_id, 0)
                + receipt_item.accepted_quantity
            )

    for item in invoice.items:
        po_line = po_lines_by_id[item.po_item_id]
        if invoiced_by_po_line[item.po_item_id] > po_line.quantity_ordered:
            return VendorInvoiceStatusEnum.PENDING_VERIFICATION
        if receipt and invoiced_by_po_line[item.po_item_id] > received_by_po_line.get(po_line.id, 0):
            return VendorInvoiceStatusEnum.PENDING_VERIFICATION

        # Flag variance if invoiced unit price strictly exceeds PO unit price
        if item.unit_price_paise > po_line.unit_price_paise:
            return VendorInvoiceStatusEnum.PRICE_VARIANCE_FLAGGED

    return VendorInvoiceStatusEnum.MATCHED_APPROVED

def post_invoice_to_accounts_payable(db: Session, invoice: VendorInvoice, current_user_id: int):
    """Triggers Accounts Payable ledger entry upon successful invoice match."""
    expense = ExpenseRecord(
        category=ExpenseCategoryEnum.PHARMACY_STOCK,
        title=f"Vendor Invoice Payout: {invoice.invoice_number}",
        amount_paise=invoice.total_amount_paise,
        status=ExpenseStatusEnum.APPROVED,
        approved_by_id=current_user_id,
        approved_at=datetime.now(timezone.utc),
        due_date=invoice.due_date,
        vendor_name=invoice.vendor.name,
        created_by_id=current_user_id
    )
    db.add(expense)
    db.flush()
    invoice.linked_expense_id = expense.id

def issue_patient_indent(db: Session, indent: StoreIndent, issue_request: list, current_user_id: int):
    """Issue from locked stock and persist exact batch and invoice-line provenance."""
    if indent.status not in {IndentStatusEnum.APPROVED, IndentStatusEnum.PARTIALLY_FULFILLED}:
        raise HTTPException(status_code=409, detail="Patient indent must be independently approved before pharmacy issue.")
    invoice = None
    if indent.encounter_id:
        invoice = db.execute(select(Invoice).where(
            Invoice.encounter_id == indent.encounter_id,
            Invoice.status == InvoiceStatusEnum.DRAFT
        ).with_for_update()).scalar_one_or_none()
        if not invoice:
            import secrets
            invoice = Invoice(
                invoice_number=f"INV-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(6).upper()}",
                patient_id=indent.encounter.patient_id, encounter_id=indent.encounter_id,
                status=InvoiceStatusEnum.DRAFT, total_amount_paise=0, amount_paid_paise=0
            )
            db.add(invoice)
            db.flush()

    total_billed_paise = 0
    created_allocations = []
    for issue_item in issue_request:
        indent_item = db.execute(select(StoreIndentItem).where(
            StoreIndentItem.id == issue_item.indent_item_id,
            StoreIndentItem.indent_id == indent.id,
        ).with_for_update()).scalar_one_or_none()
        if not indent_item:
            raise HTTPException(status_code=404, detail=f"Indent item {issue_item.indent_item_id} not found.")
        if indent_item.issued_quantity + issue_item.issue_quantity > indent_item.requested_quantity:
            raise HTTPException(status_code=400, detail="Cannot issue more than requested quantity.")
        batch = db.execute(select(InventoryBatch).where(
            InventoryBatch.id == issue_item.batch_id
        ).with_for_update()).scalar_one_or_none()
        if not batch or batch.medication_id != indent_item.medication_id:
            raise HTTPException(status_code=400, detail="Invalid batch for requested medication.")
        # SQLite may return timezone-naive values despite timezone=True; interpret
        # those stored UTC timestamps consistently before checking expiry.
        batch_expiry = batch.expiry_date
        if batch_expiry.tzinfo is None:
            batch_expiry = batch_expiry.replace(tzinfo=timezone.utc)
        if batch_expiry <= datetime.now(timezone.utc):
            raise HTTPException(status_code=409, detail=f"Cannot issue expired stock from batch {batch.batch_number}.")
        if batch.stock_quantity < issue_item.issue_quantity:
            raise HTTPException(status_code=409, detail=f"Insufficient stock in batch {batch.batch_number}.")

        batch.stock_quantity -= issue_item.issue_quantity
        indent_item.issued_quantity += issue_item.issue_quantity
        line_item = None
        if invoice:
            med = db.get(MedicationMaster, indent_item.medication_id)
            line_cost = issue_item.issue_quantity * batch.unit_price_paise
            total_billed_paise += line_cost
            line_item = InvoiceLineItem(
                invoice_id=invoice.id,
                description=f"WARD ISSUE: {med.brand_name} - Batch: {batch.batch_number} [IndentItem:{indent_item.id}]",
                quantity=issue_item.issue_quantity,
                unit_price_paise=batch.unit_price_paise,
                total_price_paise=line_cost,
            )
            db.add(line_item)
            db.flush()
        allocation = PatientIndentIssueAllocation(
            indent_item_id=indent_item.id,
            inventory_batch_id=batch.id,
            invoice_line_item_id=line_item.id if line_item else None,
            issued_quantity=issue_item.issue_quantity,
            created_by_id=current_user_id,
        )
        db.add(allocation)
        db.flush()
        created_allocations.append({
            "allocation_id": allocation.id, "indent_item_id": indent_item.id,
            "batch_id": batch.id, "issued_quantity": allocation.issued_quantity,
            "invoice_line_item_id": allocation.invoice_line_item_id,
        })

    if invoice:
        invoice.total_amount_paise += total_billed_paise
    all_fulfilled = all(item.issued_quantity >= item.requested_quantity for item in indent.items)
    indent.status = IndentStatusEnum.FULFILLED if all_fulfilled else IndentStatusEnum.PARTIALLY_FULFILLED
    return created_allocations

def process_purchase_return(
    db: Session,
    vendor_id: int,
    grn_id: int,
    return_items: list,
    current_user_id: int,
    remarks: str | None = None,
):
    """Process a vendor return with cumulative GRN quantity controls and immutable detail records."""
    grn = db.query(GoodsReceiptNote).filter(
        GoodsReceiptNote.id == grn_id
    ).with_for_update().one_or_none()
    if (
        not grn
        or grn.status != GRNStatusEnum.ACCEPTED
        or grn.purchase_order.vendor_id != vendor_id
    ):
        raise HTTPException(
            status_code=400,
            detail="Purchase return requires the specified vendor's accepted GRN.",
        )

    validated_items = []
    total_credit_paise = 0
    for item in return_items:
        grn_item = db.execute(
            select(GoodsReceiptItem)
            .where(GoodsReceiptItem.id == item.grn_item_id)
            .with_for_update()
        ).scalar_one_or_none()
        if not grn_item or grn_item.grn_id != grn.id:
            raise HTTPException(
                status_code=400,
                detail="GRN item does not belong to the specified goods receipt.",
            )
        already_returned = db.execute(
            select(func.coalesce(func.sum(PurchaseReturnItem.return_quantity), 0))
            .where(PurchaseReturnItem.grn_item_id == grn_item.id)
        ).scalar_one()
        if already_returned + item.return_quantity > grn_item.accepted_quantity:
            raise HTTPException(
                status_code=409,
                detail="Return quantity exceeds the remaining accepted quantity for this GRN item.",
            )
        if not grn_item.created_batch_id:
            raise HTTPException(status_code=400, detail="GRN item has no associated inventory batch.")

        batch = db.execute(
            select(InventoryBatch)
            .where(InventoryBatch.id == grn_item.created_batch_id)
            .with_for_update()
        ).scalar_one_or_none()
        if not batch or batch.stock_quantity < item.return_quantity:
            raise HTTPException(status_code=409, detail="Insufficient current stock to process return to vendor.")

        line_amount_paise = item.return_quantity * grn_item.unit_price_paise
        total_credit_paise += line_amount_paise
        validated_items.append((item, grn_item, batch, line_amount_paise))

    if total_credit_paise > 2_147_483_647:
        raise HTTPException(status_code=422, detail="Purchase return credit exceeds the supported debit-note amount.")

    return_record = PurchaseReturnRecord(
        grn_id=grn.id,
        vendor_id=vendor_id,
        remarks=remarks,
        total_credit_paise=total_credit_paise,
        created_by_id=current_user_id,
    )
    db.add(return_record)
    db.flush()

    for item, grn_item, batch, line_amount_paise in validated_items:
        batch.stock_quantity -= item.return_quantity
        db.add(PurchaseReturnItem(
            return_id=return_record.id,
            grn_item_id=grn_item.id,
            inventory_batch_id=batch.id,
            return_quantity=item.return_quantity,
            unit_price_paise=grn_item.unit_price_paise,
            amount_paise=line_amount_paise,
            return_reason=item.return_reason,
            created_by_id=current_user_id,
        ))

    db.add(ExpenseRecord(
        category=ExpenseCategoryEnum.PHARMACY_STOCK,
        title=f"Purchase Return / Debit Note for GRN: {grn.id}",
        amount_paise=-total_credit_paise,
        status=ExpenseStatusEnum.APPROVED,
        approved_by_id=current_user_id,
        approved_at=datetime.now(timezone.utc),
        vendor_name=grn.purchase_order.vendor.name,
        receipt_reference=f"PURCHASE-RETURN-{return_record.id}",
        created_by_id=current_user_id,
    ))
    return return_record


def return_patient_indent_stock(db: Session, indent: StoreIndent, return_request: list, current_user_id: int):
    """Return only against the original issue allocation and credit its exact invoice line."""
    invoice = None
    if indent.encounter_id:
        invoice = db.execute(select(Invoice).where(
            Invoice.encounter_id == indent.encounter_id,
            Invoice.status == InvoiceStatusEnum.DRAFT
        ).with_for_update()).scalar_one_or_none()
        if invoice is None:
            raise HTTPException(
                status_code=409,
                detail="Patient invoice is no longer in draft state; use the credit-note/refund workflow before returning stock.",
            )

    for return_item in return_request:
        indent_item = db.execute(select(StoreIndentItem).where(
            StoreIndentItem.id == return_item.indent_item_id,
            StoreIndentItem.indent_id == indent.id,
        ).with_for_update()).scalar_one_or_none()
        if not indent_item:
            raise HTTPException(status_code=404, detail=f"Indent item {return_item.indent_item_id} not found.")
        allocation = db.execute(select(PatientIndentIssueAllocation).where(
            PatientIndentIssueAllocation.id == return_item.allocation_id,
            PatientIndentIssueAllocation.indent_item_id == indent_item.id,
        ).with_for_update()).scalar_one_or_none()
        if not allocation:
            raise HTTPException(status_code=400, detail="Issue allocation does not belong to this indent item.")
        already_returned = db.execute(select(func.coalesce(func.sum(PatientIndentReturnEvent.return_quantity), 0)).where(
            PatientIndentReturnEvent.allocation_id == allocation.id
        )).scalar_one()
        if already_returned + return_item.return_quantity > allocation.issued_quantity:
            raise HTTPException(status_code=409, detail="Return quantity exceeds the remaining quantity in this issue allocation.")

        batch = db.execute(select(InventoryBatch).where(
            InventoryBatch.id == allocation.inventory_batch_id
        ).with_for_update()).scalar_one_or_none()
        if not batch or batch.medication_id != indent_item.medication_id:
            raise HTTPException(status_code=409, detail="The original issue batch is unavailable or no longer matches the medication.")
        if indent_item.issued_quantity < return_item.return_quantity:
            raise HTTPException(status_code=409, detail="Return quantity exceeds the indent item's remaining issued quantity.")

        matching_line = None
        if invoice:
            if allocation.invoice_line_item_id is None:
                raise HTTPException(status_code=409, detail="The original invoice line is unavailable for this return.")
            matching_line = db.execute(select(InvoiceLineItem).where(
                InvoiceLineItem.id == allocation.invoice_line_item_id,
                InvoiceLineItem.invoice_id == invoice.id,
            ).with_for_update()).scalar_one_or_none()
            if matching_line is None or matching_line.quantity < return_item.return_quantity:
                raise HTTPException(status_code=409, detail="The original invoice line is unavailable for this return.")

        batch.stock_quantity += return_item.return_quantity
        indent_item.issued_quantity -= return_item.return_quantity
        db.add(PatientIndentReturnEvent(
            allocation_id=allocation.id, return_quantity=return_item.return_quantity,
            created_by_id=current_user_id,
        ))
        # The session may disable autoflush; make this return visible to the next
        # duplicate allocation entry in the same request before summing its ledger.
        db.flush()
        if matching_line:
            credit_value = return_item.return_quantity * matching_line.unit_price_paise
            if matching_line.quantity == return_item.return_quantity:
                # Keep the original invoice line as a zero-value audit trace; the
                # allocation retains its immutable reference to this exact line.
                matching_line.description = f"RETURNED: {matching_line.description}"
                matching_line.total_price_paise = 0
                matching_line.tax_amount_paise = 0
            else:
                matching_line.quantity -= return_item.return_quantity
                matching_line.total_price_paise -= credit_value
                if matching_line.gst_rate_percent and matching_line.gst_rate_percent > 0:
                    matching_line.tax_amount_paise = round(
                        (matching_line.total_price_paise * matching_line.gst_rate_percent) / 100
                    )

    if invoice:
        db.flush()
        recalculate_invoice_totals(invoice)
        if invoice.discount_amount_paise and invoice.discount_amount_paise > invoice.total_amount_paise:
            invoice.discount_amount_paise = invoice.total_amount_paise
    if all(i.issued_quantity == 0 for i in indent.items):
        indent.status = IndentStatusEnum.PENDING
    else:
        indent.status = IndentStatusEnum.PARTIALLY_FULFILLED
