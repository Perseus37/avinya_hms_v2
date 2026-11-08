import secrets

from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, BackgroundTasks, Response, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import select, func
from typing import Optional
from backend.core.database import get_db, resolve_tenant_context
from backend.core.date_ranges import resolve_record_date_window
from backend.core.dependencies import RequirePermission, validate_pagination
from backend.core.export import stream_csv_response, chunked_query_fetcher
from backend.domains.identity.models import User
from backend.domains.finance.models import ExpenseRecord, ExpenseStatusEnum
from backend.domains.procurement.models import (
    VendorMaster, PurchaseOrder, PurchaseOrderItem, POStatusEnum,
    GoodsReceiptNote, GoodsReceiptItem, GRNStatusEnum,
    VendorInvoice, VendorInvoiceItem, VendorInvoiceStatusEnum,
    ProcurementDocumentDownloadAudit,
    StoreIndent, StoreIndentItem, IndentStatusEnum,
    SupplierPaymentMethodEnum, SupplierPayment, SupplierPaymentAllocation,
    SupplierPaymentRequest, SupplierPaymentRequestAllocation,
)
from backend.domains.procurement.schemas import (
    VendorCreate, VendorResponse, POCreate, POResponse, GRNCreate, VendorInvoiceResponse, VendorInvoiceReview, IndentReturnRequest,StoreIndentResponse,StoreIndentCreate,
    IndentIssueRequest, PurchaseReturnCreate,
    SupplierPaymentRequestCreate, SupplierPaymentRequestReview,
    SupplierPaymentRequestExecute, SupplierPaymentRequestResponse,
    SupplierPaymentResponse,
)
from backend.domains.procurement.services import (
    process_grn_acceptance, trigger_donut_invoice_extraction,
    execute_3_way_match, post_invoice_to_accounts_payable, process_purchase_return,
    return_patient_indent_stock, issue_patient_indent,
)
from backend.domains.procurement.documents import (
    resolve_vendor_invoice_document,
    store_vendor_invoice_document,
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

def _generate_reference(prefix: str) -> str:
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"{prefix}-{date_part}-{secrets.token_hex(4).upper()}"

# --- Vendor Management ---
@router.post("/vendors", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
def create_vendor(payload: VendorCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("procurement:write"))):
    vendor = VendorMaster(**payload.model_dump(), is_active=True, created_by_id=current_user.id)
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor

# --- Purchase Orders ---
@router.post("/purchase-orders", response_model=POResponse, status_code=status.HTTP_201_CREATED)
def draft_purchase_order(payload: POCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("procurement:write"))):
    po = PurchaseOrder(
        po_number=_generate_reference("PO"),
        vendor_id=payload.vendor_id,
        status=POStatusEnum.SUBMITTED,
        delivery_due_date=payload.delivery_due_date,
        payment_terms=payload.payment_terms,
        created_by_id=current_user.id
    )
    db.add(po)
    db.flush()

    total_amount = 0
    for item in payload.items:
        line_total = item.quantity_ordered * item.unit_price_paise
        total_amount += line_total
        db.add(PurchaseOrderItem(
            po_id=po.id,
            medication_id=item.medication_id,
            item_description=item.item_description,
            quantity_ordered=item.quantity_ordered,
            unit_price_paise=item.unit_price_paise,
            total_price_paise=line_total,
            created_by_id=current_user.id
        ))

    po.total_amount_paise = total_amount
    db.commit()
    db.refresh(po)
    return po

# --- Goods Receipt Note (GRN) ---
@router.post("/grn", status_code=status.HTTP_201_CREATED)
def receive_goods(payload: GRNCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("procurement:write"))):
    grn = GoodsReceiptNote(
        grn_number=_generate_reference("GRN"),
        po_id=payload.po_id,
        invoice_number=payload.invoice_number,
        invoice_date=payload.invoice_date,
        status=GRNStatusEnum.PENDING_INSPECTION,
        inspected_by_id=current_user.id,
        created_by_id=current_user.id
    )
    db.add(grn)
    db.flush()

    for item in payload.items:
        db.add(GoodsReceiptItem(**item.model_dump(), grn_id=grn.id, unit_price_paise=0, created_by_id=current_user.id))

    db.commit()
    return {"status": "success", "id": grn.id, "grn_number": grn.grn_number}

@router.patch("/grn/{grn_id}/accept")
def accept_goods(grn_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("procurement:approve"))):
    grn = db.get(GoodsReceiptNote, grn_id)
    if not grn or grn.status != GRNStatusEnum.PENDING_INSPECTION:
        raise HTTPException(status_code=400, detail="Invalid GRN or already processed.")

    process_grn_acceptance(db, grn, current_user.id)
    grn.status = GRNStatusEnum.ACCEPTED
    db.commit()
    return {"status": "success", "message": "Goods accepted into Pharmacy inventory."}


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
        headers={"X-Content-Type-Options": "nosniff"},
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

    po_item_ids = {item.id for item in purchase_order.items} if purchase_order else set()
    if any(item.po_item_id is not None and item.po_item_id not in po_item_ids for item in payload.items):
        raise HTTPException(status_code=422, detail="Invoice line items must reference items from the selected purchase order.")
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

    invoice.status = VendorInvoiceStatusEnum.MATCHED_APPROVED
    invoice.verified_by_id = current_user.id
    invoice.verified_at = datetime.now(timezone.utc)

    post_invoice_to_accounts_payable(db, invoice, current_user.id)
    db.commit()
    return {"status": "success", "message": "Invoice approved and posted to Accounts Payable."}

# --- Purchase Order Approval & PDF ---
@router.patch("/purchase-orders/{po_id}/approve", response_model=POResponse)
def approve_purchase_order(po_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("procurement:approve"))):
    po = db.get(PurchaseOrder, po_id)
    # FIX: Check for both DRAFT and SUBMITTED statuses
    if not po or po.status not in [POStatusEnum.DRAFT, POStatusEnum.SUBMITTED]:
        raise HTTPException(status_code=400, detail="Only DRAFT or SUBMITTED purchase orders can be approved.")

    po.status = POStatusEnum.APPROVED
    po.approved_by_id = current_user.id
    po.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(po)
    return po

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
            "total_amount": format_amount(po.total_amount_paise),
        },
        "items": [
            {
                "description": item.item_description,
                "quantity_ordered": item.quantity_ordered,
                "unit_price": format_amount(item.unit_price_paise),
                "total_price": format_amount(item.total_price_paise),
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

    filename = f"{po.po_number}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

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

@router.get("/vendors/{vendor_id}/metrics")
def get_vendor_metrics(vendor_id: int, db: Session = Depends(get_db), _: User = Depends(RequirePermission("procurement:read"))):
    """Calculates fulfillment rates and delivery delays for vendor evaluation."""
    vendor = db.get(VendorMaster, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found.")

    pos = db.query(PurchaseOrder).options(joinedload(PurchaseOrder.items)).filter(
        PurchaseOrder.vendor_id == vendor_id,
        PurchaseOrder.status.in_([POStatusEnum.COMPLETED, POStatusEnum.PARTIALLY_RECEIVED])
    ).all()

    total_pos = len(pos)
    total_items_ordered = 0
    total_items_received = 0
    late_deliveries = 0

    for po in pos:
        grns = db.query(GoodsReceiptNote).filter(
            GoodsReceiptNote.po_id == po.id,
            GoodsReceiptNote.status == GRNStatusEnum.ACCEPTED
        ).all()

        # Check for late delivery
        if grns:
            last_delivery_date = max(grn.created_at for grn in grns)
            if last_delivery_date > po.delivery_due_date:
                late_deliveries += 1

        for item in po.items:
            total_items_ordered += item.quantity_ordered
            total_items_received += item.quantity_received

    fulfillment_rate = (total_items_received / total_items_ordered * 100) if total_items_ordered > 0 else 0.0

    return {
        "vendor_code": vendor.code,
        "vendor_name": vendor.name,
        "total_completed_pos": total_pos,
        "late_deliveries_count": late_deliveries,
        "on_time_delivery_rate_pct": round(((total_pos - late_deliveries) / total_pos * 100), 2) if total_pos > 0 else 100.0,
        "item_fulfillment_rate_pct": round(fulfillment_rate, 2)
    }

# --- Supplier payment approval and execution ---
def _supplier_invoice_paid_paise(db: Session, invoice_id: int) -> int:
    value = db.query(func.coalesce(func.sum(SupplierPaymentAllocation.amount_paise), 0)).filter(
        SupplierPaymentAllocation.invoice_id == invoice_id
    ).scalar()
    return int(value or 0)


def _supplier_invoice_reserved_paise(
    db: Session, invoice_id: int, *, exclude_request_id: Optional[int] = None
) -> int:
    query = db.query(func.coalesce(func.sum(SupplierPaymentRequestAllocation.amount_paise), 0)).join(
        SupplierPaymentRequest,
        SupplierPaymentRequest.id == SupplierPaymentRequestAllocation.request_id,
    ).filter(
        SupplierPaymentRequestAllocation.invoice_id == invoice_id,
        SupplierPaymentRequest.status.in_(("PENDING", "APPROVED")),
    )
    if exclude_request_id is not None:
        query = query.filter(SupplierPaymentRequest.id != exclude_request_id)
    return int(query.scalar() or 0)


def _load_payment_request(db: Session, request_id: int, *, for_update: bool = False):
    query = db.query(SupplierPaymentRequest).options(
        selectinload(SupplierPaymentRequest.allocations)
    )
    if for_update:
        query = query.with_for_update()
    return query.filter(SupplierPaymentRequest.id == request_id).one_or_none()


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
    if not vendor.is_active:
        raise HTTPException(status_code=409, detail="Inactive suppliers cannot receive new payment requests.")

    reference = payload.payment_reference.strip()
    normalized_reference = reference.casefold()
    duplicate_payment = db.query(SupplierPayment.id).filter(
        SupplierPayment.vendor_id == vendor.id,
        func.lower(SupplierPayment.payment_reference) == normalized_reference,
    ).first()
    duplicate_request = db.query(SupplierPaymentRequest.id).filter(
        SupplierPaymentRequest.vendor_id == vendor.id,
        func.lower(SupplierPaymentRequest.payment_reference) == normalized_reference,
    ).first()
    if duplicate_payment or duplicate_request:
        raise HTTPException(status_code=409, detail="This supplier payment reference has already been used.")

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
            raise HTTPException(status_code=422, detail="A payment request can only include invoices belonging to its selected supplier.")
        if invoice.status != VendorInvoiceStatusEnum.MATCHED_APPROVED or invoice.linked_expense_id is None:
            raise HTTPException(status_code=409, detail=f"Invoice {invoice.invoice_number} is not approved for settlement.")
        expense = db.query(ExpenseRecord).filter(
            ExpenseRecord.id == invoice.linked_expense_id
        ).with_for_update().one_or_none()
        if expense is None or expense.status != ExpenseStatusEnum.APPROVED:
            raise HTTPException(status_code=409, detail=f"Invoice {invoice.invoice_number} has no payable approved Accounts Payable entry.")
        paid = _supplier_invoice_paid_paise(db, invoice.id)
        reserved = _supplier_invoice_reserved_paise(db, invoice.id)
        available = max(int(invoice.total_amount_paise) - paid - reserved, 0)
        if allocation.amount_paise > available:
            raise HTTPException(status_code=409, detail={
                "message": f"Invoice {invoice.invoice_number} has insufficient unreserved balance.",
                "invoice_id": invoice.id,
                "outstanding_paise": max(int(invoice.total_amount_paise) - paid, 0),
                "reserved_paise": reserved,
                "available_paise": available,
            })

    request_row = SupplierPaymentRequest(
        vendor_id=vendor.id,
        payment_reference=reference,
        payment_method=payload.payment_method,
        scheduled_date=payload.scheduled_date,
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
    return _load_payment_request(db, request_row.id)


@router.get(
    "/supplier-payment-requests",
    response_model=list[SupplierPaymentRequestResponse],
)
def list_supplier_payment_requests(
    status_filter: Optional[str] = Query(default=None, alias="status", pattern="^(PENDING|APPROVED|REJECTED|EXECUTED|CANCELLED)$"),
    vendor_id: Optional[int] = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    query = db.query(SupplierPaymentRequest).options(
        selectinload(SupplierPaymentRequest.allocations)
    )
    if status_filter:
        query = query.filter(SupplierPaymentRequest.status == status_filter)
    if vendor_id:
        query = query.filter(SupplierPaymentRequest.vendor_id == vendor_id)
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
    request_row = _load_payment_request(db, request_id, for_update=True)
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
        if set(by_id) != set(invoice_ids):
            raise HTTPException(status_code=409, detail="A requested invoice no longer exists.")
        for allocation in request_row.allocations:
            invoice = by_id[allocation.invoice_id]
            if invoice.vendor_id != request_row.vendor_id or invoice.status != VendorInvoiceStatusEnum.MATCHED_APPROVED:
                raise HTTPException(status_code=409, detail="A requested invoice is no longer approved for settlement.")
            expense = db.query(ExpenseRecord).filter(
                ExpenseRecord.id == invoice.linked_expense_id
            ).with_for_update().one_or_none() if invoice.linked_expense_id else None
            if expense is None or expense.status != ExpenseStatusEnum.APPROVED:
                raise HTTPException(status_code=409, detail="A requested Accounts Payable entry is no longer payable.")
            paid = _supplier_invoice_paid_paise(db, invoice.id)
            reserved = _supplier_invoice_reserved_paise(db, invoice.id, exclude_request_id=request_row.id)
            available = max(int(invoice.total_amount_paise) - paid - reserved, 0)
            if allocation.amount_paise > available:
                raise HTTPException(status_code=409, detail={
                    "message": f"Invoice {invoice.invoice_number} no longer has sufficient unreserved balance.",
                    "invoice_id": invoice.id,
                    "outstanding_paise": max(int(invoice.total_amount_paise) - paid, 0),
                    "reserved_paise": reserved,
                    "available_paise": available,
                })
        request_row.status = "APPROVED"
    else:
        request_row.status = "REJECTED"

    request_row.reviewed_by_id = current_user.id
    request_row.reviewed_at = datetime.now(timezone.utc)
    request_row.review_notes = payload.review_notes.strip()
    request_row.updated_by_id = current_user.id
    db.commit()
    return _load_payment_request(db, request_row.id)


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
    request_row = _load_payment_request(db, request_id, for_update=True)
    if request_row is None:
        raise HTTPException(status_code=404, detail="Supplier payment request not found.")
    if request_row.status != "APPROVED":
        raise HTTPException(status_code=409, detail="Only approved payment requests can be executed.")
    if request_row.scheduled_date > datetime.now(timezone.utc).date():
        raise HTTPException(status_code=409, detail="A payment scheduled for a future date cannot yet be executed.")

    reference_key = request_row.payment_reference.casefold()
    if db.query(SupplierPayment.id).filter(
        SupplierPayment.vendor_id == request_row.vendor_id,
        func.lower(SupplierPayment.payment_reference) == reference_key,
    ).first():
        raise HTTPException(status_code=409, detail="The supplier payment reference has already been recorded.")

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

    expenses = {}
    for allocation in request_row.allocations:
        invoice = by_id[allocation.invoice_id]
        if invoice.vendor_id != vendor.id or invoice.status != VendorInvoiceStatusEnum.MATCHED_APPROVED:
            raise HTTPException(status_code=409, detail="A requested invoice is no longer approved for settlement.")
        if invoice.linked_expense_id is None:
            raise HTTPException(status_code=409, detail="A requested invoice has no Accounts Payable posting.")
        expense = db.query(ExpenseRecord).filter(
            ExpenseRecord.id == invoice.linked_expense_id
        ).with_for_update().one_or_none()
        if expense is None or expense.status != ExpenseStatusEnum.APPROVED:
            raise HTTPException(status_code=409, detail="A requested Accounts Payable entry is no longer payable.")
        expenses[invoice.id] = expense
        paid = _supplier_invoice_paid_paise(db, invoice.id)
        reserved = _supplier_invoice_reserved_paise(db, invoice.id, exclude_request_id=request_row.id)
        available = max(int(invoice.total_amount_paise) - paid - reserved, 0)
        if allocation.amount_paise > available:
            raise HTTPException(status_code=409, detail={
                "message": f"Invoice {invoice.invoice_number} no longer has sufficient unreserved balance.",
                "invoice_id": invoice.id,
                "outstanding_paise": max(int(invoice.total_amount_paise) - paid, 0),
                "reserved_paise": reserved,
                "available_paise": available,
            })

    if sum(row.amount_paise for row in request_row.allocations) != request_row.amount_paise:
        raise HTTPException(status_code=409, detail="The approved request allocations no longer equal the request total.")

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

    for allocation in request_row.allocations:
        invoice = by_id[allocation.invoice_id]
        paid_after_payment = _supplier_invoice_paid_paise(db, invoice.id)
        if paid_after_payment >= int(invoice.total_amount_paise):
            invoice.status = VendorInvoiceStatusEnum.PAID
            expense = expenses[invoice.id]
            expense.status = ExpenseStatusEnum.PAID
            expense.receipt_reference = payment.payment_reference
            expense.updated_by_id = current_user.id

    request_row.status = "EXECUTED"
    request_row.executed_payment_id = payment.id
    request_row.executed_at = datetime.now(timezone.utc)
    request_row.updated_by_id = current_user.id
    db.commit()
    return db.query(SupplierPayment).options(
        selectinload(SupplierPayment.allocations)
    ).filter(SupplierPayment.id == payment.id).one()
