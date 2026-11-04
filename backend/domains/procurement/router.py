import secrets

from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, BackgroundTasks, Response, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import select, func
from typing import Optional
from backend.core.database import get_db, resolve_tenant_context
from backend.core.document_responses import pdf_attachment_response
from backend.core.date_ranges import resolve_record_date_window
from backend.core.dependencies import RequirePermission, validate_pagination, user_has_department_access
from backend.core.export import stream_csv_response, chunked_query_fetcher
from backend.domains.identity.models import User, Department
from backend.domains.pharmacy.models import MedicationMaster
from backend.domains.procurement.models import (
    VendorMaster, PurchaseOrder, PurchaseOrderItem, POStatusEnum,
    GoodsReceiptNote, GoodsReceiptItem, GRNStatusEnum,
    VendorInvoice, VendorInvoiceItem, VendorInvoiceStatusEnum,
    ProcurementDocumentDownloadAudit,
    StoreIndent, StoreIndentItem, IndentStatusEnum,
    PurchaseRequisition, PurchaseRequisitionItem, PurchaseRequisitionStatusEnum
)
from backend.domains.procurement.schemas import (
    VendorCreate, VendorResponse, VendorDirectoryResponse, VendorStatusUpdate, POCreate, POResponse, GRNCreate, VendorInvoiceResponse, VendorInvoiceReview, IndentReturnRequest,StoreIndentResponse,StoreIndentCreate,
    IndentIssueRequest, PurchaseReturnCreate,
    PurchaseRequisitionCreate, PurchaseRequisitionResponse, PurchaseRequisitionReview,
    PurchaseOrderFromRequisitionCreate
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
        db.add(PurchaseRequisitionItem(
            requisition_id=requisition.id,
            medication_id=item.medication_id,
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
    if vendor is None or not vendor.is_active:
        raise HTTPException(status_code=409, detail="An active registered vendor is required.")
    item_map = {item.id: item for item in requisition.items}
    requested_ids = [item.requisition_item_id for item in payload.items]
    if len(requested_ids) != len(set(requested_ids)):
        raise HTTPException(status_code=422, detail="A requisition line can appear only once in a purchase order.")
    prepared = []
    for item in payload.items:
        req_item = item_map.get(item.requisition_item_id)
        if req_item is None or req_item.approved_quantity is None:
            raise HTTPException(status_code=422, detail="Every purchase order line must reference an approved requisition line.")
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
        prepared.append((item, req_item))
    po = PurchaseOrder(
        po_number=_generate_reference("PO"),
        vendor_id=vendor.id,
        requisition_id=requisition.id,
        status=POStatusEnum.SUBMITTED,
        delivery_due_date=payload.delivery_due_date,
        payment_terms=payload.payment_terms,
        created_by_id=current_user.id,
    )
    db.add(po)
    db.flush()
    total_amount = 0
    for item, req_item in prepared:
        total = item.quantity_ordered * item.unit_price_paise
        total_amount += total
        db.add(PurchaseOrderItem(
            po_id=po.id,
            requisition_item_id=req_item.id,
            medication_id=req_item.medication_id,
            item_description=req_item.item_description,
            quantity_ordered=item.quantity_ordered,
            unit_price_paise=item.unit_price_paise,
            total_price_paise=total,
            created_by_id=current_user.id,
        ))
    po.total_amount_paise = total_amount
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
    db.commit()
    db.refresh(po)
    return po


# --- Purchase Orders ---
@router.post("/purchase-orders", response_model=POResponse, status_code=status.HTTP_201_CREATED)
def draft_purchase_order(payload: POCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("procurement:write"))):
    vendor = db.get(VendorMaster, payload.vendor_id)
    if vendor is None or not vendor.is_active:
        raise HTTPException(status_code=409, detail="An active registered vendor is required to create a purchase order.")
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
    if invoice.created_by_id == current_user.id:
        raise HTTPException(status_code=409, detail="The invoice uploader cannot approve the same vendor invoice.")

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
    if po.created_by_id == current_user.id:
        raise HTTPException(status_code=409, detail="The purchase order creator cannot approve the same purchase order.")

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