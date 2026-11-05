import secrets
from decimal import Decimal

from datetime import date, datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, BackgroundTasks, Response, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from typing import Optional
from backend.core.database import get_db, resolve_tenant_context
from backend.core.document_responses import pdf_attachment_response
from backend.core.date_ranges import resolve_record_date_window
from backend.core.dependencies import RequirePermission, validate_pagination, user_has_department_access
from backend.core.export import stream_csv_response, chunked_query_fetcher
from backend.domains.identity.models import User, Department, Role
from backend.domains.finance.models import ExpenseRecord, ExpenseStatusEnum
from backend.domains.pharmacy.models import MedicationMaster, InventoryMovement, InventoryBatch
from backend.domains.procurement.models import (
    VendorMaster, PurchaseOrder, PurchaseOrderItem, POStatusEnum,
    GoodsReceiptNote, GoodsReceiptItem, GRNStatusEnum,
    VendorInvoice, VendorInvoiceItem, VendorInvoiceStatusEnum,
    ProcurementDocumentDownloadAudit,
    StoreIndent, StoreIndentItem, IndentStatusEnum,
    PurchaseRequisition, PurchaseRequisitionItem, PurchaseRequisitionStatusEnum,
    SupplierQuotation, SupplierQuotationItem, SupplierQuotationStatusEnum,
    PurchaseOrderApprovalAuthority, PurchaseOrderAmendment, POAmendmentStatusEnum,
    PurchaseOrderShipment, PurchaseOrderShipmentEvent, POShipmentStatusEnum,
    ProcurementUnitOfMeasure, MedicationPackConfiguration,
    MedicationPriceControl, PurchaseOrderPriceReview, ProcurementBudget, ProcurementBudgetRevision
)
from backend.domains.procurement.schemas import (
    VendorCreate, VendorResponse, VendorDirectoryResponse, VendorStatusUpdate, POCreate, POResponse, GRNCreate, VendorInvoiceResponse, VendorInvoiceReview, IndentReturnRequest,StoreIndentResponse,StoreIndentCreate,
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
    ProcurementBudgetRevisionResponse
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
    if vendor is None or not vendor.is_active:
        raise HTTPException(status_code=409, detail="An active registered vendor is required.")
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

    subtotal = 0
    tax_total = 0
    for item in payload.items:
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
            created_by_id=current_user.id
        ))

    po.subtotal_paise = subtotal
    po.tax_amount_paise = tax_total
    po.total_amount_paise = subtotal + tax_total
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
        unit_snapshot = _resolve_medication_unit_snapshot(
            db,
            medication_id=req_line.medication_id if po.requisition_id is not None else item.medication_id,
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
    _: User = Depends(RequirePermission("procurement:read")),
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
    ap_expenses = []
    if linked_expense_ids:
        ap_expenses = db.query(ExpenseRecord).filter(
            ExpenseRecord.id.in_(linked_expense_ids)
        ).all()
    outstanding_expenses = [
        row for row in ap_expenses if row.status == ExpenseStatusEnum.APPROVED
    ]
    paid_expenses = [row for row in ap_expenses if row.status == ExpenseStatusEnum.PAID]
    overdue_expenses = [
        row for row in outstanding_expenses
        if row.due_date is not None and row.due_date < now
    ]
    upcoming_expenses = [
        row for row in outstanding_expenses
        if row.due_date is not None and now <= row.due_date <= due_cutoff
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
            "posted_invoice_count": len(ap_expenses),
            "approved_unpaid_value_paise": sum(int(row.amount_paise or 0) for row in outstanding_expenses),
            "paid_expense_value_paise": sum(int(row.amount_paise or 0) for row in paid_expenses),
            "overdue_approved_count": len(overdue_expenses),
            "overdue_approved_value_paise": sum(int(row.amount_paise or 0) for row in overdue_expenses),
            "due_within_days": due_within_days,
            "due_soon_count": len(upcoming_expenses),
            "due_soon_value_paise": sum(int(row.amount_paise or 0) for row in upcoming_expenses),
            "definition": "Derived from finance expenses linked to vendor invoices. APPROVED is treated as unpaid; PAID as paid. No partial settlement ledger exists, so partial payments are not represented.",
        },
        "supplier_concentration": {
            "basis": "Tax-inclusive PO commitments in the selected PO creation-date period.",
            "suppliers": concentration,
            "top_supplier_share_pct": concentration[0]["commitment_share_pct"] if concentration else None,
        },
        "limitations": [
            "No procurement budget or department budget allocation model exists; budget utilization and budget variance are not reported.",
            "PO commitment, accepted receipt valuation, invoice value and AP expense value are distinct lifecycle measures and must not be added together.",
            "AP payment tracking is expense-status based; partial settlements and bank reconciliation are not modeled.",
            "Supplier concentration is based on PO commitments, not settled payments or accepted receipt value.",
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
    matched_unpaid = [
        invoice for invoice in invoices
        if invoice.status == VendorInvoiceStatusEnum.MATCHED_APPROVED
    ]
    matched_unpaid_exposure_paise = sum(int(invoice.total_amount_paise or 0) for invoice in matched_unpaid)

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
            "exposure_definition": "Only MATCHED_APPROVED invoices are included; pending, flagged, rejected and PAID invoices are excluded. Payment execution/partial settlement is not represented by this metric.",
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
    if not user_has_department_access(db, current_user, department.id):
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
    _: User = Depends(RequirePermission("procurement:read")),
):
    query = db.query(ProcurementBudget)
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
    _: User = Depends(RequirePermission("procurement:read")),
):
    budget = db.get(ProcurementBudget, budget_id)
    if budget is None:
        raise HTTPException(status_code=404, detail="Procurement budget not found.")
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
        allocated = db.query(func.coalesce(func.sum(ProcurementBudget.total_amount_paise), 0)).filter(
            ProcurementBudget.parent_budget_id == parent.id,
            ProcurementBudget.status == "ACTIVE",
        ).scalar() or 0
        if overlapping:
            raise HTTPException(status_code=409, detail="An active quarterly allocation already overlaps this period.")
        if int(allocated) + budget.total_amount_paise > parent.total_amount_paise:
            raise HTTPException(status_code=409, detail="Quarterly allocations cannot exceed the parent annual budget.")
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
    _: User = Depends(RequirePermission("procurement:read")),
):
    if db.get(ProcurementBudget, budget_id) is None:
        raise HTTPException(status_code=404, detail="Procurement budget not found.")
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
    revision.updated_by_id = current_user.id
    revision.status = "APPROVED" if payload.approved else "REJECTED"
    if payload.approved:
        active_quarter_allocations = db.query(func.coalesce(func.sum(ProcurementBudget.total_amount_paise), 0)).filter(
            ProcurementBudget.parent_budget_id == budget.id,
            ProcurementBudget.status == "ACTIVE",
        ).scalar() or 0
        if int(active_quarter_allocations) > revision.proposed_amount_paise:
            raise HTTPException(status_code=409, detail="The revised annual amount cannot be lower than its active quarterly allocations.")
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
    if budget.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="Only active budgets can be closed.")
    pending = db.query(ProcurementBudgetRevision.id).filter(
        ProcurementBudgetRevision.budget_id == budget.id,
        ProcurementBudgetRevision.status == "PENDING",
    ).first()
    if pending:
        raise HTTPException(status_code=409, detail="Resolve pending budget revisions before closing the budget.")
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
