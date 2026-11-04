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
    IndentStatusEnum,
    GoodsReceiptNote,
    GoodsReceiptItem,
    PurchaseOrder,
    PurchaseOrderItem,
    POStatusEnum,
    GRNStatusEnum,
    VendorInvoice,
    VendorInvoiceItem,
    VendorInvoiceStatusEnum,
)
from backend.domains.pharmacy.models import (InventoryBatch, InventoryMovement, MedicationMaster, PharmacyLocation, PharmacyLocationAccess)
from backend.domains.finance.models import ExpenseRecord, ExpenseCategoryEnum, ExpenseStatusEnum
from backend.domains.procurement.ai_parser import DonutInvoiceParser
from backend.domains.billing.models import Invoice, InvoiceLineItem, InvoiceStatusEnum
from backend.domains.billing.rcm_services import recalculate_invoice_totals
from backend.domains.reports.pdf import render_html_pdf
from backend.domains.reports.templates import render_sandboxed_template

logger = logging.getLogger(__name__)

def _ensure_stock_location_access(db: Session, location_id: int, user_id: int) -> None:
    """Require explicit location grants for organization-authenticated branch sessions."""
    if "central_branch_department_codes" not in db.info:
        return
    assignment = db.execute(select(PharmacyLocationAccess.id).where(
        PharmacyLocationAccess.location_id == location_id,
        PharmacyLocationAccess.user_id == user_id,
        PharmacyLocationAccess.is_active.is_(True),
    )).scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=403, detail="You are not assigned to this pharmacy stock location.")


def _append_stock_movement(
    db: Session,
    batch: InventoryBatch,
    *,
    movement_type: str,
    quantity_delta: int,
    stock_before: int,
    actor_user_id: int,
    reference_type: str,
    reference_id: int | str,
    notes: str | None = None,
) -> None:
    if quantity_delta == 0:
        return
    stock_after = stock_before + quantity_delta
    if stock_before < 0 or stock_after < 0:
        raise HTTPException(status_code=409, detail="Inventory movement would create an invalid stock balance.")
    db.add(InventoryMovement(
        location_id=batch.location_id,
        medication_id=batch.medication_id,
        inventory_batch_id=batch.id,
        movement_type=movement_type,
        quantity_delta=quantity_delta,
        stock_before=stock_before,
        stock_after=stock_after,
        unit_price_paise=batch.unit_price_paise,
        reference_type=reference_type,
        reference_id=str(reference_id),
        actor_id=actor_user_id,
        notes=notes,
    ))


def process_grn_acceptance(db: Session, grn: GoodsReceiptNote, current_user_id: int):
    """Atomically post an inspected GRN into the selected stock location and movement ledger."""
    po = db.execute(select(PurchaseOrder).where(PurchaseOrder.id == grn.po_id).with_for_update()).scalar_one_or_none()
    if po is None or po.status not in {POStatusEnum.APPROVED, POStatusEnum.PARTIALLY_RECEIVED}:
        raise HTTPException(status_code=409, detail="The purchase order is not open for goods receipt.")
    po_items = {
        item.id: item for item in db.execute(
            select(PurchaseOrderItem).where(PurchaseOrderItem.po_id == po.id).with_for_update()
        ).scalars().all()
    }
    for grn_item in grn.items:
        po_item = po_items.get(grn_item.po_item_id)
        if po_item is None:
            raise HTTPException(status_code=422, detail="A GRN line does not belong to its purchase order.")
        if grn_item.accepted_quantity > grn_item.received_quantity:
            raise HTTPException(status_code=422, detail="Accepted quantity cannot exceed received quantity.")
        if po_item.quantity_received + grn_item.accepted_quantity > po_item.quantity_ordered:
            raise HTTPException(status_code=409, detail=f"GRN would over-receive PO item {po_item.id}.")
        if grn_item.accepted_quantity <= 0:
            continue
        po_item.quantity_received += grn_item.accepted_quantity
        if not po_item.medication_id:
            continue
        if not grn.location_id:
            raise HTTPException(status_code=422, detail="A pharmacy location is required for medication receipts.")
        location = db.execute(select(PharmacyLocation).where(
            PharmacyLocation.id == grn.location_id, PharmacyLocation.is_active.is_(True)
        )).scalar_one_or_none()
        if location is None:
            raise HTTPException(status_code=404, detail="The selected pharmacy location is unavailable.")
        _ensure_stock_location_access(db, location.id, current_user_id)
        batch = db.execute(select(InventoryBatch).where(
            InventoryBatch.medication_id == po_item.medication_id,
            InventoryBatch.batch_number == grn_item.batch_number,
            InventoryBatch.location_id == location.id,
        ).with_for_update()).scalar_one_or_none()
        if batch:
            if batch.expiry_date != grn_item.expiry_date or batch.unit_price_paise != po_item.unit_price_paise:
                raise HTTPException(status_code=409, detail="This batch already exists at the selected location with a different expiry date or unit cost.")
            stock_before = batch.stock_quantity
            batch.stock_quantity += grn_item.accepted_quantity
        else:
            batch = InventoryBatch(
                medication_id=po_item.medication_id, location_id=location.id,
                batch_number=grn_item.batch_number, expiry_date=grn_item.expiry_date,
                stock_quantity=grn_item.accepted_quantity, unit_price_paise=po_item.unit_price_paise,
                created_by_id=current_user_id,
            )
            db.add(batch)
            db.flush()
            stock_before = 0
        _append_stock_movement(
            db, batch, movement_type="RECEIPT", quantity_delta=grn_item.accepted_quantity,
            stock_before=stock_before, actor_user_id=current_user_id,
            reference_type="GOODS_RECEIPT", reference_id=grn.id,
            notes=f"GRN item {grn_item.id}",
        )
        grn_item.unit_price_paise = po_item.unit_price_paise
        grn_item.created_batch_id = batch.id
    db.flush()
    po.status = POStatusEnum.COMPLETED if all(
        item.quantity_received >= item.quantity_ordered for item in po_items.values()
    ) else POStatusEnum.PARTIALLY_RECEIVED

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

def _percentage_amount_paise(base_paise: int, percentage: int) -> int:
    """Calculate a whole-percent tax amount in paise using half-up rounding."""
    return (base_paise * percentage + 50) // 100


def execute_3_way_match(db: Session, invoice: VendorInvoice) -> VendorInvoiceStatusEnum:
    """Reconcile invoice arithmetic, PO pricing, accepted receipts and prior invoices.

    A missing accepted GRN is deliberately not considered a successful three-way match.
    Tax is checked against the invoice's own line tax rates; PO tax rates are not yet
    represented in the PO schema, so no unsupported tax-rate assumption is made here.
    """
    if not invoice.po_id or not invoice.items:
        return VendorInvoiceStatusEnum.PENDING_VERIFICATION

    # Serialize invoice matching per PO so two concurrent invoices cannot both
    # consume the same accepted receipt quantity.
    po = db.execute(
        select(PurchaseOrder).where(PurchaseOrder.id == invoice.po_id).with_for_update()
    ).scalar_one_or_none()
    if (
        not po
        or po.vendor_id != invoice.vendor_id
        or po.status not in {
            POStatusEnum.APPROVED,
            POStatusEnum.PARTIALLY_RECEIVED,
            POStatusEnum.COMPLETED,
        }
    ):
        return VendorInvoiceStatusEnum.PENDING_VERIFICATION

    receipt = db.get(GoodsReceiptNote, invoice.grn_id) if invoice.grn_id else None
    if not receipt or receipt.po_id != po.id or receipt.status != GRNStatusEnum.ACCEPTED:
        return VendorInvoiceStatusEnum.PENDING_VERIFICATION

    # Header totals must reconcile exactly. Each invoice line's net amount is
    # quantity * unit price; tax is rounded per line to avoid aggregate drift.
    expected_subtotal = 0
    expected_tax = 0
    for item in invoice.items:
        line_net = item.quantity * item.unit_price_paise
        if item.total_price_paise != line_net:
            return VendorInvoiceStatusEnum.PENDING_VERIFICATION
        expected_subtotal += line_net
        expected_tax += _percentage_amount_paise(line_net, item.tax_percentage)

    if (
        invoice.subtotal_paise != expected_subtotal
        or invoice.tax_amount_paise != expected_tax
        or invoice.discount_paise > invoice.subtotal_paise
        or invoice.total_amount_paise
        != invoice.subtotal_paise + invoice.tax_amount_paise - invoice.discount_paise
    ):
        return VendorInvoiceStatusEnum.PENDING_VERIFICATION

    po_lines = {line.id: line for line in po.items}
    # Refuse matching if persisted PO financial totals no longer reconcile.
    po_subtotal = sum(line.total_price_paise for line in po_lines.values())
    po_tax = sum(line.tax_amount_paise for line in po_lines.values())
    po_gross = sum(line.gross_total_paise for line in po_lines.values())
    if (
        po.subtotal_paise != po_subtotal
        or po.tax_amount_paise != po_tax
        or po.total_amount_paise != po_gross
        or po_subtotal + po_tax != po_gross
    ):
        return VendorInvoiceStatusEnum.PENDING_VERIFICATION

    invoiced_by_po_line = {}
    price_variance = False
    for item in invoice.items:
        if not item.po_item_id or item.po_item_id not in po_lines:
            return VendorInvoiceStatusEnum.PENDING_VERIFICATION
        po_line = po_lines[item.po_item_id]
        invoiced_by_po_line[item.po_item_id] = (
            invoiced_by_po_line.get(item.po_item_id, 0) + item.quantity
        )
        if item.medication_id is not None and item.medication_id != po_line.medication_id:
            return VendorInvoiceStatusEnum.PENDING_VERIFICATION
        if (
            item.unit_price_paise != po_line.unit_price_paise
            or item.tax_percentage != po_line.tax_percentage
        ):
            price_variance = True

    # Compare cumulative accepted quantity across all accepted GRNs, not just the
    # GRN selected on this invoice.
    for po_item_id, current_invoice_qty in invoiced_by_po_line.items():
        accepted_qty = db.query(func.coalesce(func.sum(GoodsReceiptItem.accepted_quantity), 0)).join(
            GoodsReceiptNote, GoodsReceiptNote.id == GoodsReceiptItem.grn_id
        ).filter(
            GoodsReceiptNote.po_id == po.id,
            GoodsReceiptNote.status == GRNStatusEnum.ACCEPTED,
            GoodsReceiptItem.po_item_id == po_item_id,
        ).scalar()
        if current_invoice_qty > int(accepted_qty or 0):
            return VendorInvoiceStatusEnum.PENDING_VERIFICATION

        previously_invoiced = db.query(func.coalesce(func.sum(VendorInvoiceItem.quantity), 0)).join(
            VendorInvoice, VendorInvoice.id == VendorInvoiceItem.invoice_id
        ).filter(
            VendorInvoice.po_id == po.id,
            VendorInvoice.id != invoice.id,
            VendorInvoice.status.in_([
                VendorInvoiceStatusEnum.MATCHED_APPROVED,
                VendorInvoiceStatusEnum.PAID,
                VendorInvoiceStatusEnum.PRICE_VARIANCE_FLAGGED,
            ]),
            VendorInvoiceItem.po_item_id == po_item_id,
        ).scalar()
        if int(previously_invoiced or 0) + current_invoice_qty > int(accepted_qty or 0):
            return VendorInvoiceStatusEnum.PENDING_VERIFICATION

    return (
        VendorInvoiceStatusEnum.PRICE_VARIANCE_FLAGGED
        if price_variance
        else VendorInvoiceStatusEnum.MATCHED_APPROVED
    )

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
    """Fulfills indent, decrements FEFO stock, and auto-bills the patient's active encounter."""
    invoice = None
    if indent.encounter_id:
        stmt_inv = select(Invoice).where(
            Invoice.encounter_id == indent.encounter_id,
            Invoice.status == InvoiceStatusEnum.DRAFT
        ).with_for_update()
        invoice = db.execute(stmt_inv).scalar_one_or_none()

        if not invoice:
            import secrets
            date_prefix = datetime.now(timezone.utc).strftime("%Y%m%d")
            invoice = Invoice(
                invoice_number=f"INV-{date_prefix}-{secrets.token_hex(6).upper()}",
                patient_id=indent.encounter.patient_id,
                encounter_id=indent.encounter_id,
                status=InvoiceStatusEnum.DRAFT,
                total_amount_paise=0,
                amount_paid_paise=0
            )
            db.add(invoice)
            db.flush()

    total_billed_paise = 0
    all_fulfilled = True

    for issue_item in issue_request:
        indent_item = next((i for i in indent.items if i.id == issue_item.indent_item_id), None)
        if not indent_item:
            raise HTTPException(status_code=404, detail=f"Indent item {issue_item.indent_item_id} not found.")

        if indent_item.issued_quantity + issue_item.issue_quantity > indent_item.requested_quantity:
            raise HTTPException(status_code=400, detail="Cannot issue more than requested quantity.")

        batch = db.execute(select(InventoryBatch).where(InventoryBatch.id == issue_item.batch_id).with_for_update()).scalar_one_or_none()
        if not batch or batch.medication_id != indent_item.medication_id:
            raise HTTPException(status_code=400, detail="Invalid batch for requested medication.")

        if batch.stock_quantity < issue_item.issue_quantity:
            raise HTTPException(status_code=409, detail=f"Insufficient stock in batch {batch.batch_number}.")

        # Decrement physical stock and append the ward issue movement atomically.
        _ensure_stock_location_access(db, batch.location_id, current_user_id)
        stock_before = batch.stock_quantity
        batch.stock_quantity -= issue_item.issue_quantity
        _append_stock_movement(
            db, batch, movement_type="WARD_ISSUE", quantity_delta=-issue_item.issue_quantity,
            stock_before=stock_before, actor_user_id=current_user_id,
            reference_type="STORE_INDENT", reference_id=indent.id,
            notes=f"Indent item {indent_item.id}",
        )
        indent_item.issued_quantity += issue_item.issue_quantity

        if indent_item.issued_quantity < indent_item.requested_quantity:
            all_fulfilled = False

        # Auto-bill to patient invoice
        if invoice:
            med = db.get(MedicationMaster, indent_item.medication_id)
            line_cost = issue_item.issue_quantity * batch.unit_price_paise
            total_billed_paise += line_cost

            line_item = InvoiceLineItem(
                invoice_id=invoice.id,
                description=f"WARD ISSUE: {med.brand_name} - Batch: {batch.batch_number} [IndentItem:{indent_item.id}]",
                quantity=issue_item.issue_quantity,
                unit_price_paise=batch.unit_price_paise,
                total_price_paise=line_cost
            )
            db.add(line_item)

    if invoice:
        invoice.total_amount_paise += total_billed_paise

    indent.status = IndentStatusEnum.FULFILLED if all_fulfilled else IndentStatusEnum.PARTIALLY_FULFILLED
    indent.approved_by_id = current_user_id

def process_purchase_return(db: Session, vendor_id: int, grn_id: int, return_items: list, current_user_id: int):
    """Process a vendor return only against accepted quantities on the specified GRN."""
    grn = db.execute(
        select(GoodsReceiptNote).where(GoodsReceiptNote.id == grn_id).with_for_update()
    ).scalar_one_or_none()
    if grn is None or grn.status != GRNStatusEnum.ACCEPTED:
        raise HTTPException(status_code=404, detail="Accepted goods receipt note not found.")
    po = db.get(PurchaseOrder, grn.po_id)
    if po is None or po.vendor_id != vendor_id:
        raise HTTPException(status_code=400, detail="The specified GRN does not belong to this vendor.")

    total_credit_paise = 0
    requested_by_line = {}
    for item in return_items:
        grn_item = db.execute(
            select(GoodsReceiptItem).where(
                GoodsReceiptItem.id == item.grn_item_id,
                GoodsReceiptItem.grn_id == grn_id,
            ).with_for_update()
        ).scalar_one_or_none()
        if not grn_item:
            raise HTTPException(status_code=400, detail="Return line must belong to the specified GRN.")
        if not grn_item.created_batch_id:
            raise HTTPException(status_code=400, detail="GRN item has no associated inventory batch.")

        batch = db.execute(
            select(InventoryBatch).where(InventoryBatch.id == grn_item.created_batch_id).with_for_update()
        ).scalar_one_or_none()
        if not batch:
            raise HTTPException(status_code=409, detail="The GRN inventory batch no longer exists.")
        _ensure_stock_location_access(db, batch.location_id, current_user_id)

        prior_delta = db.execute(select(func.coalesce(func.sum(InventoryMovement.quantity_delta), 0)).where(
            InventoryMovement.inventory_batch_id == batch.id,
            InventoryMovement.movement_type == "PURCHASE_RETURN",
            InventoryMovement.reference_type == "PURCHASE_RETURN",
            InventoryMovement.reference_id == str(grn_id),
            InventoryMovement.notes.like(f"GRN item {grn_item.id}%"),
        )).scalar_one()
        prior_returned = -int(prior_delta or 0)
        already_requested = requested_by_line.get(grn_item.id, 0)
        if prior_returned + already_requested + item.return_quantity > grn_item.accepted_quantity:
            raise HTTPException(status_code=409, detail="Return quantity exceeds the accepted quantity remaining on this GRN line.")
        if batch.stock_quantity < item.return_quantity:
            raise HTTPException(status_code=409, detail="Insufficient current stock to process return to vendor.")

        stock_before = batch.stock_quantity
        batch.stock_quantity -= item.return_quantity
        _append_stock_movement(
            db, batch, movement_type="PURCHASE_RETURN", quantity_delta=-item.return_quantity,
            stock_before=stock_before, actor_user_id=current_user_id,
            reference_type="PURCHASE_RETURN", reference_id=grn_id,
            notes=f"GRN item {grn_item.id}: {item.return_reason.strip()}",
        )
        requested_by_line[grn_item.id] = already_requested + item.return_quantity
        total_credit_paise += item.return_quantity * batch.unit_price_paise

    debit_note = ExpenseRecord(
        category=ExpenseCategoryEnum.PHARMACY_STOCK,
        title=f"Purchase Return / Debit Note for GRN: {grn_id}",
        amount_paise=-total_credit_paise,
        status=ExpenseStatusEnum.APPROVED,
        approved_by_id=current_user_id,
        approved_at=datetime.now(timezone.utc),
        vendor_name=po.vendor.name,
        created_by_id=current_user_id,
    )
    db.add(debit_note)

def return_patient_indent_stock(db: Session, indent: StoreIndent, return_request: list, current_user_id: int):
    """Processes ward returns, restores FEFO batch stock, and credits the patient's DRAFT invoice."""
    invoice = None
    if indent.encounter_id:
        stmt_inv = select(Invoice).where(
            Invoice.encounter_id == indent.encounter_id,
            Invoice.status == InvoiceStatusEnum.DRAFT
        ).with_for_update()
        invoice = db.execute(stmt_inv).scalar_one_or_none()

    total_credit_paise = 0

    for return_item in return_request:
        indent_item = next((i for i in indent.items if i.id == return_item.indent_item_id), None)
        if not indent_item:
            raise HTTPException(status_code=404, detail=f"Indent item {return_item.indent_item_id} not found.")

        if return_item.return_quantity > indent_item.issued_quantity:
            raise HTTPException(status_code=400, detail="Cannot return more stock than was issued.")

        batch = db.execute(select(InventoryBatch).where(InventoryBatch.id == return_item.batch_id).with_for_update()).scalar_one_or_none()
        if not batch or batch.medication_id != indent_item.medication_id:
            raise HTTPException(status_code=400, detail="Invalid batch for the returned medication.")

        # 1. Restore physical stock and decrement issued tracking.
        _ensure_stock_location_access(db, batch.location_id, current_user_id)
        stock_before = batch.stock_quantity
        batch.stock_quantity += return_item.return_quantity
        _append_stock_movement(
            db, batch, movement_type="WARD_RETURN", quantity_delta=return_item.return_quantity,
            stock_before=stock_before, actor_user_id=current_user_id,
            reference_type="STORE_INDENT_RETURN", reference_id=indent.id,
            notes=f"Indent item {indent_item.id}",
        )
        indent_item.issued_quantity -= return_item.return_quantity

        # 2. Credit the patient's DRAFT invoice by reversing the specific line item
        if invoice:
            exact_tag = f"[IndentItem:{indent_item.id}]"
            matching_line = next((li for li in invoice.line_items if exact_tag in li.description), None)

            if matching_line:
                credit_value = return_item.return_quantity * matching_line.unit_price_paise
                total_credit_paise += credit_value

                if matching_line.quantity <= return_item.return_quantity:
                    if matching_line in invoice.line_items:
                        invoice.line_items.remove(matching_line)
                    db.delete(matching_line)
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

    # Re-evaluate Indent Status
    if all(i.issued_quantity == 0 for i in indent.items):
        indent.status = IndentStatusEnum.PENDING
    else:
        indent.status = IndentStatusEnum.PARTIALLY_FULFILLED