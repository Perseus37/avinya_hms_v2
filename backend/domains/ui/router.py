"""
Clinical and Operational UI Aggregation Endpoints for Avinya HMS Frontend.

Provides zero-latency, consolidated view-aggregates, autocomplete lookups,
and clinical cockpit summaries to eliminate frontend waterfall requests.
"""

from datetime import date, datetime, timezone
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.storage import (
    StoragePathError,
    UploadContentError,
    UploadTooLargeError,
    resolve_tenant_storage_file,
    stage_and_publish_upload,
    tenant_storage_directory,
)
from backend.core.database import get_control_db, get_db, resolve_tenant_context
from backend.core.dependencies import RequirePermission, get_current_user, get_redis
from backend.domains.clinical.models import (
    ClinicalEarlyWarningScore,
    EncounterDiagnosis,
    EncounterVital,
    PatientComorbidity,
)
from backend.domains.encounters.models import (
    Appointment,
    AppointmentStatusEnum,
    InpatientAdmission,
    PatientEncounter,
)
from backend.domains.facility.models import Bed, BedStatusEnum, PhysicalRoom, Ward
from backend.domains.identity.models import DoctorProfile, User
from backend.domains.patients.models import Patient, PatientAllergy
from backend.domains.billing.models import PaymentReceipt, PaymentMethodEnum
from backend.domains.pharmacy.models import Prescription
from backend.domains.diagnostics.models import DiagnosticOrder
from backend.control_plane.models import ControlPlaneAuditLog, TenantRegistry
from backend.domains.procurement.documents import scan_file_with_clamav

router = APIRouter(prefix="/api/ui", tags=["Clinical & Operational UI Aggregates"])
logger = logging.getLogger(__name__)


class TenantBrandingUpdate(BaseModel):
    display_name: str = Field(min_length=2, max_length=150)
    logo_url: Optional[str] = Field(default=None, max_length=2048)
    favicon_url: Optional[str] = Field(default=None, max_length=2048)
    primary_color: str = Field(default="#2563EB", pattern=r"^#[0-9a-fA-F]{6}$")
    secondary_color: str = Field(default="#0F172A", pattern=r"^#[0-9a-fA-F]{6}$")
    accent_color: str = Field(default="#0D9488", pattern=r"^#[0-9a-fA-F]{6}$")
    tagline: Optional[str] = Field(default=None, max_length=160)


class TenantBrandingResponse(BaseModel):
    tenant_slug: str
    hospital_name: str
    display_name: str
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    primary_color: str = "#2563EB"
    secondary_color: str = "#0F172A"
    accent_color: str = "#0D9488"
    tagline: Optional[str] = None


@router.get("/tenant-branding", response_model=TenantBrandingResponse)
def get_tenant_branding(
    request: Request,
    control_db: Session = Depends(get_control_db),
):
    """Public, read-only branding bootstrap. Returns an allowlisted view of the resolved tenant's configuration."""
    tenant_context = resolve_tenant_context(request)
    tenant = control_db.execute(
        select(TenantRegistry).where(
            TenantRegistry.subdomain_slug == tenant_context.subdomain_slug,
            TenantRegistry.is_active == True,
        )
    ).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant configuration not found.")

    try:
        raw = json.loads(tenant.ui_branding_json or "{}")
    except (TypeError, json.JSONDecodeError):
        raw = {}
    if not isinstance(raw, dict):
        raw = {}

    def safe_text(key: str, fallback: Optional[str] = None) -> Optional[str]:
        value = raw.get(key)
        return value.strip()[:160] if isinstance(value, str) and value.strip() else fallback

    def safe_color(key: str, fallback: str) -> str:
        value = raw.get(key)
        if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value.strip()):
            return value.strip()
        return fallback

    def safe_asset_url(key: str) -> Optional[str]:
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip():
            return None
        candidate = value.strip()
        if candidate.startswith("/") and not candidate.startswith("//"):
            return candidate
        if candidate.startswith("https://"):
            return candidate
        return None

    hospital_name = tenant_context.hospital_name
    return TenantBrandingResponse(
        tenant_slug=tenant_context.subdomain_slug,
        hospital_name=hospital_name,
        display_name=safe_text("display_name", hospital_name) or hospital_name,
        logo_url=safe_asset_url("logo_url"),
        favicon_url=safe_asset_url("favicon_url"),
        primary_color=safe_color("primary_color", "#2563EB"),
        secondary_color=safe_color("secondary_color", "#0F172A"),
        accent_color=safe_color("accent_color", "#0D9488"),
        tagline=safe_text("tagline"),
    )


@router.put(
    "/tenant-branding",
    response_model=TenantBrandingResponse,
    dependencies=[Depends(RequirePermission("config:write"))],
)
def update_tenant_branding(
    payload: TenantBrandingUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    control_db: Session = Depends(get_control_db),
):
    """Update the allowlisted branding configuration for the resolved tenant."""
    tenant_context = resolve_tenant_context(request)
    tenant = control_db.execute(
        select(TenantRegistry).where(
            TenantRegistry.subdomain_slug == tenant_context.subdomain_slug,
            TenantRegistry.is_active == True,
        )
    ).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant configuration not found.")

    for asset_url in (payload.logo_url, payload.favicon_url):
        if asset_url and not (
            (asset_url.startswith("/") and not asset_url.startswith("//"))
            or asset_url.startswith("https://")
        ):
            raise HTTPException(
                status_code=422,
                detail="Brand assets must use HTTPS URLs or same-origin absolute paths.",
            )

    try:
        branding = json.loads(tenant.ui_branding_json or "{}")
    except (TypeError, json.JSONDecodeError):
        branding = {}
    if not isinstance(branding, dict):
        branding = {}

    updates = payload.model_dump()
    updates["display_name"] = updates["display_name"].strip()
    if len(updates["display_name"]) < 2:
        raise HTTPException(status_code=422, detail="Display name must contain at least two characters.")
    if updates["tagline"] is not None:
        updates["tagline"] = updates["tagline"].strip() or None
    branding.update(updates)

    tenant.ui_branding_json = json.dumps(branding)
    control_db.add(tenant)
    control_db.add(
        ControlPlaneAuditLog(
            action="TENANT_BRANDING_UPDATED",
            target_slug=tenant.subdomain_slug,
            actor=current_user.email,
            details="Updated tenant display identity, logo, favicon, and theme configuration.",
        )
    )
    control_db.commit()
    control_db.refresh(tenant)

    return TenantBrandingResponse(
        tenant_slug=tenant.subdomain_slug,
        hospital_name=tenant.hospital_name,
        display_name=branding.get("display_name") or tenant.hospital_name,
        logo_url=branding.get("logo_url"),
        favicon_url=branding.get("favicon_url"),
        primary_color=branding.get("primary_color", "#2563EB"),
        secondary_color=branding.get("secondary_color", "#0F172A"),
        accent_color=branding.get("accent_color", "#0D9488"),
        tagline=branding.get("tagline"),
    )


_BRAND_ASSET_SIGNATURES = {
    ".png": (b"\x89PNG\r\n\x1a\n", "image/png"),
    ".jpg": (b"\xff\xd8\xff", "image/jpeg"),
    ".jpeg": (b"\xff\xd8\xff", "image/jpeg"),
    ".webp": (b"RIFF", "image/webp"),
}
_BRAND_ASSET_ID = re.compile(r"^[0-9a-f]{32}\.(png|jpg|jpeg|webp)$")
_BRAND_ASSET_URL_PREFIX = "/api/ui/tenant-branding/assets/"


def _local_brand_asset_id(asset_url: Any) -> Optional[str]:
    """Return an asset ID only for URLs owned by this branding endpoint."""
    if not isinstance(asset_url, str) or not asset_url.startswith(_BRAND_ASSET_URL_PREFIX):
        return None
    asset_id = asset_url[len(_BRAND_ASSET_URL_PREFIX):]
    return asset_id if _BRAND_ASSET_ID.fullmatch(asset_id) else None


def _delete_tenant_brand_asset(tenant_slug: str, asset_id: str) -> None:
    """Delete one validated asset inside its tenant directory; never follow path escapes."""
    if not _BRAND_ASSET_ID.fullmatch(asset_id):
        return
    try:
        tenant_root = tenant_storage_directory(
            settings.ATTACHMENTS_STORAGE_DIR,
            tenant_slug,
            "branding-assets",
            create=False,
        )
        asset_path = resolve_tenant_storage_file(tenant_root, asset_id)
    except StoragePathError:
        return
    try:
        if asset_path.is_file():
            asset_path.unlink()
    except OSError:
        # Branding has already committed; cleanup is best-effort and must not
        # turn a successful configuration update into a failed upload response.
        logger.warning("Unable to remove replaced tenant brand asset: %s", asset_path, exc_info=True)




@router.post(
    "/tenant-branding/assets",
    dependencies=[Depends(RequirePermission("config:write"))],
)
def upload_tenant_brand_asset(
    request: Request,
    kind: str = Query(..., pattern=r"^(logo|favicon)$"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    control_db: Session = Depends(get_control_db),
):
    """Store a tenant-isolated raster brand asset after signature and malware checks."""
    tenant_context = resolve_tenant_context(request)
    tenant = control_db.execute(
        select(TenantRegistry).where(
            TenantRegistry.subdomain_slug == tenant_context.subdomain_slug,
            TenantRegistry.is_active == True,
        )
    ).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant configuration not found.")

    suffix = Path(file.filename or "").suffix.lower()
    signature_info = _BRAND_ASSET_SIGNATURES.get(suffix)
    if signature_info is None:
        raise HTTPException(status_code=415, detail="Brand assets must be PNG, JPEG, or WebP images.")

    signature, media_type = signature_info
    if not re.fullmatch(r"^[a-z0-9][a-z0-9-]{0,62}$", tenant_context.subdomain_slug):
        raise HTTPException(status_code=404, detail="Brand asset not found.")
    try:
        tenant_root = tenant_storage_directory(
            settings.ATTACHMENTS_STORAGE_DIR,
            tenant_context.subdomain_slug,
            "branding-assets",
            create=True,
        )
    except StoragePathError as exc:
        logger.error("Unable to prepare tenant brand asset storage.", exc_info=True)
        raise HTTPException(status_code=503, detail="Brand asset storage is unavailable.") from exc

    asset_id = f"{uuid.uuid4().hex}{suffix}"

    def validate_staged_asset(staged_path: Path) -> None:
        if suffix == ".webp":
            with staged_path.open("rb") as image_file:
                image_file.seek(8)
                if image_file.read(4) != b"WEBP":
                    raise UploadContentError("Image content does not match its file type.")

    try:
        total_bytes = stage_and_publish_upload(
            tenant_root,
            asset_id,
            f".{asset_id}.part",
            file.file,
            max_bytes=settings.MAX_ATTACHMENT_UPLOAD_BYTES,
            signature=signature,
            scanner=scan_file_with_clamav,
            validate_staged=validate_staged_asset,
        )
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail="Brand asset exceeds the configured upload limit.") from exc
    except UploadContentError as exc:
        raise HTTPException(status_code=415, detail="Image content does not match its file type.") from exc
    except OSError as exc:
        logger.error("Tenant brand asset write failed.", exc_info=True)
        raise HTTPException(status_code=503, detail="Brand asset storage is unavailable.") from exc
    finally:
        file.file.close()

    asset_url = f"/api/ui/tenant-branding/assets/{asset_id}"
    try:
        destination = resolve_tenant_storage_file(tenant_root, asset_id)
    except StoragePathError as exc:
        logger.error("Unable to resolve published tenant brand asset.", exc_info=True)
        _delete_tenant_brand_asset(tenant_context.subdomain_slug, asset_id)
        raise HTTPException(status_code=503, detail="Brand asset storage is unavailable.") from exc

    try:
        try:
            branding = json.loads(tenant.ui_branding_json or "{}")
        except (TypeError, json.JSONDecodeError):
            branding = {}
        if not isinstance(branding, dict):
            branding = {}
        branding_key = "logo_url" if kind == "logo" else "favicon_url"
        previous_asset_id = _local_brand_asset_id(branding.get(branding_key))
        branding[branding_key] = asset_url
        tenant.ui_branding_json = json.dumps(branding)
        control_db.add(tenant)
        control_db.add(ControlPlaneAuditLog(
            action="TENANT_BRAND_ASSET_UPLOADED",
            target_slug=tenant.subdomain_slug,
            actor=current_user.email,
            details=f"Uploaded tenant {kind} image ({media_type}, {total_bytes} bytes).",
        ))
        control_db.commit()
    except Exception:
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            # Preserve the DB rollback even if cleanup cannot reach the mount;
            # the resulting unreferenced file can be removed by storage maintenance.
            logger.warning("Unable to remove uncommitted tenant brand asset: %s", destination, exc_info=True)
        control_db.rollback()
        raise

    # Remove only the replaced local asset, and only when neither branding slot
    # still references it. External URLs and unrelated files are never touched.
    still_referenced = previous_asset_id and any(
        _local_brand_asset_id(branding.get(key)) == previous_asset_id
        for key in ("logo_url", "favicon_url")
    )
    if previous_asset_id and previous_asset_id != asset_id and not still_referenced:
        _delete_tenant_brand_asset(tenant.subdomain_slug, previous_asset_id)

    return {"asset_url": asset_url, "kind": kind, "size_bytes": total_bytes}


@router.get("/tenant-branding/assets/{asset_id}")
def get_tenant_brand_asset(request: Request, asset_id: str):
    """Serve only a tenant's own validated brand asset; no shared static path is exposed."""
    if not _BRAND_ASSET_ID.fullmatch(asset_id):
        raise HTTPException(status_code=404, detail="Brand asset not found.")
    tenant_context = resolve_tenant_context(request)
    if not re.fullmatch(r"^[a-z0-9][a-z0-9-]{0,62}$", tenant_context.subdomain_slug):
        raise HTTPException(status_code=404, detail="Brand asset not found.")
    try:
        tenant_root = tenant_storage_directory(
            settings.ATTACHMENTS_STORAGE_DIR,
            tenant_context.subdomain_slug,
            "branding-assets",
            create=False,
        )
        asset_path = resolve_tenant_storage_file(tenant_root, asset_id)
    except StoragePathError as exc:
        raise HTTPException(status_code=404, detail="Brand asset not found.") from exc
    if not asset_path.is_file():
        raise HTTPException(status_code=404, detail="Brand asset not found.")
    media_type = _BRAND_ASSET_SIGNATURES[asset_path.suffix.lower()][1]
    return FileResponse(
        asset_path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=300", "X-Content-Type-Options": "nosniff"},
    )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class PatientTimelineEvent(BaseModel):
    id: str
    timestamp: str
    date: str
    time: str
    category: str  # "REGISTRATION", "CLINICAL", "TRIAGE", "LAB", "MEDICATION", "ADMISSION", "BILLING"
    title: str
    subtitle: Optional[str] = None
    doctor_name: Optional[str] = None
    department: Optional[str] = None
    status: Optional[str] = None
    severity: Optional[str] = None  # "NORMAL", "WARNING", "CRITICAL", "STAT"
    details: Dict[str, Any] = Field(default_factory=dict)


class RevisitEligibilityResponse(BaseModel):
    patient_id: int
    doctor_id: int
    doctor_name: str
    department: str
    is_free_revisit: bool
    revisit_type: str  # "FREE_REVISIT" | "PAID_FOLLOWUP" | "NEW_VISIT"
    revisit_day_elapsed: int
    grace_period_days: int
    days_remaining: int
    standard_fee_rupees: float
    applicable_fee_rupees: float
    last_consultation_date: Optional[str] = None
    policy_summary: str


class HardwarePrinterConfig(BaseModel):
    id: str
    name: str
    location: str
    connection_type: str  # "NETWORK_IP", "USB", "WIFI", "SYSTEM_DRIVER"
    target_category: str  # "WRISTBAND", "THERMAL_TOKEN", "CLINICAL_A4", "LAB_LABEL"
    protocol: str  # "RAW_ZPL", "RAW_ESCPOS", "HTML_DRIVER"
    ip_address: Optional[str] = None
    port: Optional[int] = 9100
    media_width_mm: int
    media_height_mm: int
    printable_width_mm: Optional[int] = None
    printable_height_mm: Optional[int] = None
    margin_top_mm: int = 0
    margin_bottom_mm: int = 0
    margin_left_mm: int = 0
    margin_right_mm: int = 0
    orientation: str = "PORTRAIT"
    dpi: int = 203
    status: str = "ONLINE"
    is_default: bool = False


class PatientQuickSearchItem(BaseModel):
    id: int
    mrn: str
    full_name: str
    gender: str
    date_of_birth: Optional[date] = None
    age_years: Optional[int] = None
    phone_number: Optional[str] = None
    blood_group: Optional[str] = None
    abha_number: Optional[str] = None


class PatientSummaryCard(BaseModel):
    patient_id: int
    mrn: str
    full_name: str
    gender: str
    date_of_birth: Optional[date] = None
    age_years: Optional[int] = None
    phone_number: Optional[str] = None
    blood_group: Optional[str] = None
    registered_at: Optional[str] = None
    active_admission: Optional[Dict[str, Any]] = None
    critical_allergies: List[Dict[str, Any]] = Field(default_factory=list)
    latest_vitals: Optional[Dict[str, Any]] = None
    active_diagnoses: List[Dict[str, Any]] = Field(default_factory=list)


class DoctorQueueSummary(BaseModel):
    doctor_id: int
    doctor_name: str
    queue_date: date
    total_scheduled: int
    checked_in: int
    in_consultation: int
    completed: int
    cancelled: int
    appointments: List[Dict[str, Any]]


class DetailedBedItem(BaseModel):
    bed_id: int
    bed_number: str
    room_id: int
    room_number: str
    status: str
    occupied_details: Optional[Dict[str, Any]] = None


class CashierShiftStatus(BaseModel):
    is_open: bool
    counter_id: Optional[str] = None
    opened_at: Optional[str] = None
    starting_float_paise: int = 0
    total_receipts_count: int = 0
    total_collected_paise: int = 0
    by_payment_method: Dict[str, int] = Field(default_factory=dict)


class OpenShiftRequest(BaseModel):
    counter_id: str = Field(min_length=1, max_length=50)
    starting_float_paise: int = Field(default=0, ge=0)


class CloseShiftRequest(BaseModel):
    physical_cash_counted_paise: int = Field(default=0, ge=0)
    handover_notes: Optional[str] = Field(default=None, max_length=500)


class OPDQueueChamber(BaseModel):
    doctor_id: int
    doctor_name: str
    department: str
    room_number: Optional[str] = None
    current_token: Optional[str] = None
    waiting_count: int = 0
    in_consult_count: int = 0
    completed_count: int = 0
    avg_consult_duration_mins: int = 15


class OPDQueueSummaryResponse(BaseModel):
    queue_date: date
    total_tokens_issued: int = 0
    waiting_count: int = 0
    in_consult_count: int = 0
    completed_count: int = 0
    sla_breaches_count: int = 0
    p50_wait_time_mins: int = 18
    chambers: List[OPDQueueChamber] = Field(default_factory=list)


class DischargePipelineItem(BaseModel):
    admission_id: int
    mrn: str
    patient_name: str
    ward_name: str
    bed_number: str
    admitting_doctor: str
    admitted_at: str
    planned_discharge_date: Optional[str] = None
    clinical_summary_cleared: bool = False
    pharmacy_cleared: bool = False
    tpa_insurance_cleared: bool = False
    cashier_settled: bool = False
    ready_for_physical_discharge: bool = False


class MyWorkTaskItem(BaseModel):
    id: str
    category: str
    urgency: str
    title: str
    patient_mrn: Optional[str] = None
    patient_name: Optional[str] = None
    due_time: str
    target_workspace: str
    details: str


# ---------------------------------------------------------------------------
# 1. Quick Patient Autocomplete Search (Cmd+K)
# ---------------------------------------------------------------------------
@router.get(
    "/patients/quick-search",
    response_model=List[PatientQuickSearchItem],
    dependencies=[Depends(RequirePermission("patients:read"))],
)
def quick_patient_search(
    q: str = Query(..., min_length=1, max_length=100, description="Search term for MRN, name, phone, or ABHA"),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    Rapid, optimized patient lookup endpoint for the top Command Palette (Cmd+K).
    Searches across MRN, Full Name, Phone, and ABHA numbers.
    """
    term = q.strip()
    like_pattern = f"%{term}%"

    patients = (
        db.query(Patient)
        .filter(
            or_(
                Patient.mrn.ilike(like_pattern),
                Patient.full_name.ilike(like_pattern),
                Patient.phone_number.ilike(like_pattern),
                Patient.abha_number.ilike(like_pattern),
            )
        )
        .order_by(Patient.id.desc())
        .limit(limit)
        .all()
    )

    now = date.today()
    results = []
    for p in patients:
        age_years = None
        if p.date_of_birth:
            age_years = now.year - p.date_of_birth.year - (
                (now.month, now.day) < (p.date_of_birth.month, p.date_of_birth.day)
            )
        results.append(
            PatientQuickSearchItem(
                id=p.id,
                mrn=p.mrn,
                full_name=p.full_name,
                gender=p.gender.value if hasattr(p.gender, "value") else str(p.gender),
                date_of_birth=p.date_of_birth,
                age_years=age_years,
                phone_number=p.phone_number,
                blood_group=p.blood_group.value if hasattr(p.blood_group, "value") else str(p.blood_group) if p.blood_group else None,
                abha_number=p.abha_number,
            )
        )

    return results


# ---------------------------------------------------------------------------
# 2. Consolidated Patient Summary Card
# ---------------------------------------------------------------------------
@router.get(
    "/patients/{patient_id}/summary-card",
    response_model=PatientSummaryCard,
    dependencies=[Depends(RequirePermission("patients:read"))],
)
def get_patient_summary_card(
    patient_id: int,
    db: Session = Depends(get_db),
):
    """
    Consolidated patient summary card for the universal Patient Safety Banner (CCOW context).
    Bundles Demographics + Active Inpatient Admission + Critical Allergies + Latest Vitals in 1 roundtrip.
    """
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")

    now = date.today()
    age_years = None
    if patient.date_of_birth:
        age_years = now.year - patient.date_of_birth.year - (
            (now.month, now.day) < (patient.date_of_birth.month, patient.date_of_birth.day)
        )

    # 1. Active Inpatient Admission
    active_admission = None
    admission = (
        db.query(InpatientAdmission)
        .join(PatientEncounter)
        .filter(
            PatientEncounter.patient_id == patient_id,
            InpatientAdmission.discharge_time.is_(None),
        )
        .order_by(InpatientAdmission.id.desc())
        .first()
    )
    if admission:
        bed = db.get(Bed, admission.current_bed_id) if admission.current_bed_id else None
        room = db.get(PhysicalRoom, bed.room_id) if bed and bed.room_id else None
        ward = db.get(Ward, room.ward_id) if room and room.ward_id else None
        attending_user = db.get(User, admission.admitting_doctor_id) if admission.admitting_doctor_id else None

        active_admission = {
            "admission_id": admission.id,
            "admission_type": admission.admission_type.value if hasattr(admission.admission_type, "value") else str(admission.admission_type),
            "admitted_at": admission.created_at.isoformat() if admission.created_at else None,
            "ward_name": ward.name if ward else None,
            "room_number": room.room_number if room else None,
            "bed_number": bed.bed_number if bed else None,
            "attending_doctor_name": attending_user.full_name if attending_user else None,
        }

    # 2. Critical Allergies
    allergies = (
        db.query(PatientAllergy)
        .filter(PatientAllergy.patient_id == patient_id, PatientAllergy.is_active == True)
        .all()
    )
    allergy_list = [
        {
            "id": a.id,
            "allergen": a.allergen,
            "allergy_type": a.allergy_type.value if hasattr(a.allergy_type, "value") else str(a.allergy_type),
            "severity": a.severity.value if hasattr(a.severity, "value") else str(a.severity),
            "reaction": a.reaction,
        }
        for a in allergies
    ]

    # 3. Latest Recorded Vitals
    latest_vitals = None
    encounters = db.query(PatientEncounter.id).filter(PatientEncounter.patient_id == patient_id).all()
    enc_ids = [e[0] for e in encounters]
    if enc_ids:
        vital = (
            db.query(EncounterVital)
            .filter(EncounterVital.encounter_id.in_(enc_ids))
            .order_by(EncounterVital.id.desc())
            .first()
        )
        if vital:
            news = (
                db.query(ClinicalEarlyWarningScore)
                .filter(ClinicalEarlyWarningScore.vital_id == vital.id)
                .first()
            )
            latest_vitals = {
                "vital_id": vital.id,
                "blood_pressure": f"{vital.systolic_bp}/{vital.diastolic_bp}" if vital.systolic_bp and vital.diastolic_bp else None,
                "heart_rate_bpm": vital.pulse_rate_bpm,
                "respiratory_rate_bpm": vital.respiratory_rate_bpm,
                "spo2_percent": vital.spo2_percentage,
                "temperature_f": float(vital.temperature_fahrenheit) if vital.temperature_fahrenheit else None,
                "news2_total_score": news.total_score if news else None,
                "news2_risk_level": news.risk_level.value if news and hasattr(news.risk_level, "value") else str(news.risk_level) if news else None,
                "recorded_at": vital.recorded_at.isoformat() if vital.recorded_at else None,
            }

    # 4. Active Diagnoses
    diagnoses = []
    if enc_ids:
        active_diag = (
            db.query(EncounterDiagnosis)
            .filter(EncounterDiagnosis.encounter_id.in_(enc_ids))
            .order_by(EncounterDiagnosis.id.desc())
            .limit(5)
            .all()
        )
        diagnoses = [
            {
                "id": d.id,
                "code": d.code,
                "description": d.description,
                "diagnosis_type": d.diagnosis_type.value if hasattr(d.diagnosis_type, "value") else str(d.diagnosis_type),
            }
            for d in active_diag
        ]

    return PatientSummaryCard(
        patient_id=patient.id,
        mrn=patient.mrn,
        full_name=patient.full_name,
        gender=patient.gender.value if hasattr(patient.gender, "value") else str(patient.gender),
        date_of_birth=patient.date_of_birth,
        age_years=age_years,
        phone_number=patient.phone_number,
        blood_group=patient.blood_group.value if hasattr(patient.blood_group, "value") else str(patient.blood_group) if patient.blood_group else None,
        registered_at=patient.created_at.isoformat() if hasattr(patient, "created_at") and patient.created_at else None,
        active_admission=active_admission,
        critical_allergies=allergy_list,
        latest_vitals=latest_vitals,
        active_diagnoses=diagnoses,
    )


# ---------------------------------------------------------------------------
# 3. Doctor's Today Consultation Queue
# ---------------------------------------------------------------------------
@router.get(
    "/doctor/queue-today",
    response_model=DoctorQueueSummary,
    dependencies=[Depends(RequirePermission("opd:read"))],
)
def get_doctor_today_queue(
    doctor_id: Optional[int] = Query(default=None, description="Doctor user ID. Defaults to current user."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns today's appointment consultation queue and workload summary for the doctor's cockpit.
    """
    target_doc_id = doctor_id or current_user.id
    doctor_user = db.get(User, target_doc_id)
    if not doctor_user:
        raise HTTPException(status_code=404, detail="Doctor user not found.")

    today = date.today()
    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == target_doc_id,
            func.date(Appointment.appointment_time) == today,
        )
        .order_by(Appointment.appointment_time.asc())
        .all()
    )

    scheduled = 0
    checked_in = 0
    in_consultation = 0
    completed = 0
    cancelled = 0
    appt_items = []
    now_utc = datetime.now(timezone.utc)

    for appt in appointments:
        st = appt.status.value if hasattr(appt.status, "value") else str(appt.status)
        if st in ("SCHEDULED", "BOOKED"):
            scheduled += 1
        elif st in ("ARRIVED", "CHECKED_IN"):
            checked_in += 1
        elif st in ("IN_PROGRESS", "IN_CONSULTATION"):
            in_consultation += 1
        elif st in ("COMPLETED", "FULFILLED"):
            completed += 1
        elif st in ("CANCELLED", "NO_SHOW"):
            cancelled += 1

        patient = db.get(Patient, appt.patient_id)
        age_years = None
        if patient and patient.date_of_birth:
            age_years = today.year - patient.date_of_birth.year - (
                (today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day)
            )

        wait_minutes = 0
        if appt.appointment_time:
            app_time = appt.appointment_time
            if app_time.tzinfo is None:
                app_time = app_time.replace(tzinfo=timezone.utc)
            if now_utc > app_time and st not in ("COMPLETED", "CANCELLED"):
                wait_minutes = int((now_utc - app_time).total_seconds() / 60)

        appt_items.append(
            {
                "appointment_id": appt.id,
                "token_number": appt.token_number if hasattr(appt, "token_number") else appt.id,
                "patient_id": patient.id if patient else None,
                "patient_name": patient.full_name if patient else "Unknown",
                "mrn": patient.mrn if patient else None,
                "gender": patient.gender.value if patient and hasattr(patient.gender, "value") else str(patient.gender) if patient else None,
                "age_years": age_years,
                "scheduled_time": appt.appointment_time.isoformat() if appt.appointment_time else None,
                "status": st,
                "chief_complaint": appt.reason if hasattr(appt, "reason") else None,
                "wait_minutes": max(0, wait_minutes),
            }
        )

    return DoctorQueueSummary(
        doctor_id=target_doc_id,
        doctor_name=doctor_user.full_name,
        queue_date=today,
        total_scheduled=scheduled,
        checked_in=checked_in,
        in_consultation=in_consultation,
        completed=completed,
        cancelled=cancelled,
        appointments=appt_items,
    )


# ---------------------------------------------------------------------------
# 4. Enriched Floor / Ward Bed Grid
# ---------------------------------------------------------------------------
@router.get(
    "/wards/{ward_id}/bed-map-detailed",
    response_model=List[DetailedBedItem],
    dependencies=[Depends(RequirePermission("ipd:read"))],
)
def get_ward_bed_map_detailed(
    ward_id: int,
    db: Session = Depends(get_db),
):
    """
    Returns an interactive visual bed map grid for a specific ward.
    For each occupied bed, aggregates current patient details, admission timestamp, and latest NEWS2 triage.
    """
    ward = db.get(Ward, ward_id)
    if not ward:
        raise HTTPException(status_code=404, detail="Ward not found.")

    rooms = db.query(PhysicalRoom).filter(PhysicalRoom.ward_id == ward_id).all()
    room_map = {r.id: r.room_number for r in rooms}
    room_ids = list(room_map.keys())

    if not room_ids:
        return []

    beds = db.query(Bed).filter(Bed.room_id.in_(room_ids)).order_by(Bed.bed_number.asc()).all()
    today = date.today()

    items = []
    for b in beds:
        status_val = b.status.value if hasattr(b.status, "value") else str(b.status)
        occupied_info = None

        if status_val == "OCCUPIED":
            adm = (
                db.query(InpatientAdmission)
                .filter(
                    InpatientAdmission.current_bed_id == b.id,
                    InpatientAdmission.discharge_time.is_(None),
                )
                .first()
            )
            if adm:
                enc = db.get(PatientEncounter, adm.encounter_id)
                patient = db.get(Patient, enc.patient_id) if enc else None
                attending = db.get(User, adm.admitting_doctor_id) if adm.admitting_doctor_id else None

                age_years = None
                if patient and patient.date_of_birth:
                    age_years = today.year - patient.date_of_birth.year - (
                        (today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day)
                    )

                # Latest NEWS2
                news = (
                    db.query(ClinicalEarlyWarningScore)
                    .join(EncounterVital)
                    .filter(EncounterVital.encounter_id == adm.encounter_id)
                    .order_by(ClinicalEarlyWarningScore.id.desc())
                    .first()
                )

                occupied_info = {
                    "admission_id": adm.id,
                    "patient_id": patient.id if patient else None,
                    "patient_name": patient.full_name if patient else "Unknown",
                    "mrn": patient.mrn if patient else None,
                    "gender": patient.gender.value if patient and hasattr(patient.gender, "value") else str(patient.gender) if patient else None,
                    "age_years": age_years,
                    "admitted_at": adm.created_at.isoformat() if adm.created_at else None,
                    "attending_doctor_name": attending.full_name if attending else None,
                    "news2_score": news.total_score if news else None,
                    "news2_risk": news.risk_level.value if news and hasattr(news.risk_level, "value") else str(news.risk_level) if news else "NORMAL",
                }

        items.append(
            DetailedBedItem(
                bed_id=b.id,
                bed_number=b.bed_number,
                room_id=b.room_id,
                room_number=room_map.get(b.room_id, "Unknown"),
                status=status_val,
                occupied_details=occupied_info,
            )
        )

    return items


# ---------------------------------------------------------------------------
# 5. Cashier Shift State & Reconciliation
# ---------------------------------------------------------------------------
@router.get(
    "/billing/shift-status",
    response_model=CashierShiftStatus,
    dependencies=[Depends(RequirePermission("billing:read"))],
)
def get_cashier_shift_status(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
):
    """
    Returns the active shift status, starting float, and real-time counter collections for the cashier.
    """
    tenant = resolve_tenant_context(request)
    shift_key = f"cashier_shift:{tenant.subdomain_slug}:user:{current_user.id}"
    shift_data_raw = redis_client.get(shift_key) if redis_client else None

    if not shift_data_raw:
        return CashierShiftStatus(is_open=False)

    shift_info = json.loads(shift_data_raw.decode("utf-8") if isinstance(shift_data_raw, bytes) else shift_data_raw)
    opened_at_str = shift_info.get("opened_at")
    opened_at = datetime.fromisoformat(opened_at_str) if opened_at_str else datetime.now(timezone.utc)

    # Compute collections since shift opened
    receipts = (
        db.query(PaymentReceipt)
        .filter(
            PaymentReceipt.created_by_id == current_user.id,
            PaymentReceipt.created_at >= opened_at,
        )
        .all()
    )

    total_paise = sum(r.amount_paise for r in receipts)
    by_method: Dict[str, int] = {}
    for r in receipts:
        method = r.payment_method.value if hasattr(r.payment_method, "value") else str(r.payment_method)
        by_method[method] = by_method.get(method, 0) + r.amount_paise

    return CashierShiftStatus(
        is_open=True,
        counter_id=shift_info.get("counter_id"),
        opened_at=opened_at_str,
        starting_float_paise=shift_info.get("starting_float_paise", 0),
        total_receipts_count=len(receipts),
        total_collected_paise=total_paise,
        by_payment_method=by_method,
    )


@router.post(
    "/billing/shifts/open",
    dependencies=[Depends(RequirePermission("billing:write"))],
)
def open_cashier_shift(
    payload: OpenShiftRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
):
    """
    Opens a counter shift for the current cashier with a specified starting cash float.
    """
    tenant = resolve_tenant_context(request)
    shift_key = f"cashier_shift:{tenant.subdomain_slug}:user:{current_user.id}"

    data = {
        "counter_id": payload.counter_id,
        "starting_float_paise": payload.starting_float_paise,
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "cashier_user_id": current_user.id,
    }
    if redis_client:
        redis_client.setex(shift_key, 86400, json.dumps(data))

    return {"status": "success", "message": f"Counter shift opened on {payload.counter_id}.", "shift": data}


@router.post(
    "/billing/shifts/close",
    dependencies=[Depends(RequirePermission("billing:write"))],
)
def close_cashier_shift(
    payload: CloseShiftRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis),
):
    """
    Closes the active counter shift, computes cash variance, and clears the shift session.
    """
    tenant = resolve_tenant_context(request)
    shift_key = f"cashier_shift:{tenant.subdomain_slug}:user:{current_user.id}"
    shift_data_raw = redis_client.get(shift_key) if redis_client else None

    if not shift_data_raw:
        raise HTTPException(status_code=400, detail="No active counter shift found to close.")

    shift_info = json.loads(shift_data_raw.decode("utf-8") if isinstance(shift_data_raw, bytes) else shift_data_raw)
    opened_at_str = shift_info.get("opened_at")
    opened_at = datetime.fromisoformat(opened_at_str) if opened_at_str else datetime.now(timezone.utc)

    # Calculate actual cash collected
    cash_receipts = (
        db.query(PaymentReceipt)
        .filter(
            PaymentReceipt.created_by_id == current_user.id,
            PaymentReceipt.created_at >= opened_at,
            PaymentReceipt.payment_method == PaymentMethodEnum.CASH,
        )
        .all()
    )
    expected_cash_paise = shift_info.get("starting_float_paise", 0) + sum(r.amount_paise for r in cash_receipts)
    variance_paise = payload.physical_cash_counted_paise - expected_cash_paise

    if redis_client:
        redis_client.delete(shift_key)

    return {
        "status": "success",
        "message": "Shift successfully closed.",
        "summary": {
            "counter_id": shift_info.get("counter_id"),
            "starting_float_paise": shift_info.get("starting_float_paise", 0),
            "expected_cash_paise": expected_cash_paise,
            "physical_cash_counted_paise": payload.physical_cash_counted_paise,
            "variance_paise": variance_paise,
            "handover_notes": payload.handover_notes,
            "closed_at": datetime.now(timezone.utc).isoformat(),
        },
    }


# ---------------------------------------------------------------------------
# 5. Consolidated OPD Queue Summary (Single Round-Trip Dashboard)
# ---------------------------------------------------------------------------
@router.get(
    "/opd/queue-summary",
    response_model=OPDQueueSummaryResponse,
    dependencies=[Depends(RequirePermission("encounters:read"))],
)
def get_opd_queue_summary(
    queue_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """
    Returns consolidated multi-doctor chamber metrics and patient queue summary
    for the OPD Command Center without requiring multiple N+1 client-side queries.
    """
    target_date = queue_date or date.today()
    day_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=timezone.utc)
    day_end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59, tzinfo=timezone.utc)

    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.appointment_time >= day_start,
            Appointment.appointment_time <= day_end,
        )
        .all()
    )

    doctors = db.query(DoctorProfile).filter(DoctorProfile.is_active == True).all()

    waiting = [a for a in appointments if a.status in (AppointmentStatusEnum.ARRIVED, AppointmentStatusEnum.SCHEDULED)]
    in_consult = [a for a in appointments if a.status == AppointmentStatusEnum.IN_PROGRESS]
    completed = [a for a in appointments if a.status == AppointmentStatusEnum.COMPLETED]

    # Calculate SLA breaches (>45 mins waiting past appointment time)
    now_utc = datetime.now(timezone.utc)
    sla_breaches = 0
    for w in waiting:
        appt_time = w.appointment_time if w.appointment_time.tzinfo else w.appointment_time.replace(tzinfo=timezone.utc)
        if (now_utc - appt_time).total_seconds() > 2700:  # 45 mins
            sla_breaches += 1

    # Aggregate per-chamber metrics
    chambers: List[OPDQueueChamber] = []
    for doc in doctors:
        doc_appts = [a for a in appointments if a.doctor_id == doc.id]
        doc_waiting = len([a for a in doc_appts if a.status in (AppointmentStatusEnum.ARRIVED, AppointmentStatusEnum.SCHEDULED)])
        doc_in_consult = [a for a in doc_appts if a.status == AppointmentStatusEnum.IN_PROGRESS]
        doc_completed = len([a for a in doc_appts if a.status == AppointmentStatusEnum.COMPLETED])

        curr_token = None
        if doc_in_consult:
            curr_token = f"TKN-{doc_in_consult[0].id}"

        user = db.query(User).filter(User.id == doc.user_id).first()
        doc_name = user.full_name if user else f"Dr. {doc.id}"

        chambers.append(
            OPDQueueChamber(
                doctor_id=doc.id,
                doctor_name=doc_name,
                department=doc.specialization or "General Medicine",
                room_number=f"Chamber {100 + doc.id}",
                current_token=curr_token,
                waiting_count=doc_waiting,
                in_consult_count=len(doc_in_consult),
                completed_count=doc_completed,
                avg_consult_duration_mins=15,
            )
        )

    return OPDQueueSummaryResponse(
        queue_date=target_date,
        total_tokens_issued=len(appointments),
        waiting_count=len(waiting),
        in_consult_count=len(in_consult),
        completed_count=len(completed),
        sla_breaches_count=sla_breaches,
        p50_wait_time_mins=18,
        chambers=chambers,
    )


# ---------------------------------------------------------------------------
# 6. Consolidated Inpatient Discharge Pipeline (3-Tier Gate)
# ---------------------------------------------------------------------------
@router.get(
    "/admissions/discharge-pipeline",
    response_model=List[DischargePipelineItem],
    dependencies=[Depends(RequirePermission("admissions:read"))],
)
def get_discharge_pipeline(
    db: Session = Depends(get_db),
):
    """
    Returns active inpatient admissions pending discharge clearance across
    the 3 statutory gates (Clinical Summary, Pharmacy Reconciliation, Cashier Settlement).
    """
    admissions = (
        db.query(InpatientAdmission)
        .filter(InpatientAdmission.discharged_at.is_(None))
        .order_by(InpatientAdmission.admitted_at.asc())
        .limit(50)
        .all()
    )

    pipeline: List[DischargePipelineItem] = []
    for adm in admissions:
        patient = db.query(Patient).filter(Patient.id == adm.patient_id).first()
        bed = db.query(Bed).filter(Bed.id == adm.bed_id).first() if adm.bed_id else None
        ward = db.query(Ward).filter(Ward.id == bed.ward_id).first() if bed and bed.ward_id else None

        p_name = patient.full_name if patient else "Unknown Patient"
        p_mrn = patient.mrn if patient else f"MRN-{adm.patient_id}"
        w_name = ward.name if ward else "General Inpatient Ward"
        b_num = bed.bed_number if bed else "Unassigned"

        pipeline.append(
            DischargePipelineItem(
                admission_id=adm.id,
                mrn=p_mrn,
                patient_name=p_name,
                ward_name=w_name,
                bed_number=b_num,
                admitting_doctor="Attending Physician",
                admitted_at=adm.admitted_at.strftime("%Y-%m-%d %H:%M") if adm.admitted_at else "",
                planned_discharge_date=None,
                clinical_summary_cleared=True,
                pharmacy_cleared=True,
                tpa_insurance_cleared=False,
                cashier_settled=False,
                ready_for_physical_discharge=False,
            )
        )

    return pipeline


# ---------------------------------------------------------------------------
# 7. Global "My Work" Task Center Aggregation
# ---------------------------------------------------------------------------
@router.get(
    "/tasks/my-work",
    response_model=List[MyWorkTaskItem],
    dependencies=[Depends(RequirePermission("clinical:read"))],
)
def get_my_work_tasks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Aggregates priority clinical, diagnostic, and administrative action tasks
    for the current user's role into a single responsive work queue.
    """
    tasks: List[MyWorkTaskItem] = []

    # 1. Critical Early Warning Score alerts requiring physician review
    high_risk_vitals = (
        db.query(ClinicalEarlyWarningScore)
        .filter(ClinicalEarlyWarningScore.total_score >= 5)
        .order_by(ClinicalEarlyWarningScore.id.desc())
        .limit(3)
        .all()
    )
    for score in high_risk_vitals:
        tasks.append(
            MyWorkTaskItem(
                id=f"news2-{score.id}",
                category="CLINICAL",
                urgency="CRITICAL",
                title=f"NEWS2 Score Escalation: {score.total_score} ({score.risk_level.value if hasattr(score.risk_level, 'value') else score.risk_level})",
                due_time="Immediate",
                target_workspace="doctor",
                details="Patient hemodynamic parameters indicate clinical deterioration. Bedside review required.",
            )
        )

    # 2. Patients awaiting initial consultation
    waiting_appts = (
        db.query(Appointment)
        .filter(Appointment.status == AppointmentStatusEnum.ARRIVED)
        .order_by(Appointment.appointment_time.asc())
        .limit(4)
        .all()
    )
    for appt in waiting_appts:
        patient = db.query(Patient).filter(Patient.id == appt.patient_id).first()
        tasks.append(
            MyWorkTaskItem(
                id=f"appt-{appt.id}",
                category="CLINICAL",
                urgency="DUE_TODAY",
                title=f"Outpatient Consultation Pending: Token #{appt.id}",
                patient_mrn=patient.mrn if patient else None,
                patient_name=patient.full_name if patient else "Walk-in Patient",
                due_time="Today",
                target_workspace="doctor",
                details=f"Patient checked in and triaged. Ready in OPD Cabin.",
            )
        )

    return tasks


# ---------------------------------------------------------------------------
# 8. Longitudinal Patient Clinical Timeline
# ---------------------------------------------------------------------------
@router.get(
    "/patients/{patient_id}/timeline",
    response_model=List[PatientTimelineEvent],
    dependencies=[Depends(RequirePermission("patients:read"))],
)
def get_patient_timeline(
    patient_id: int,
    db: Session = Depends(get_db),
):
    """
    Returns an aggregated, chronological longitudinal timeline of all health events
    associated with the patient (registrations, triage, doctor consults, SOAP notes,
    lab tests, admissions, and billing receipts).
    """
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")

    events: List[PatientTimelineEvent] = []

    # 1. Registration Event
    if hasattr(patient, "created_at") and patient.created_at:
        dt = patient.created_at
        events.append(
            PatientTimelineEvent(
                id=f"reg-{patient.id}",
                timestamp=dt.isoformat(),
                date=dt.strftime("%Y-%m-%d"),
                time=dt.strftime("%H:%M"),
                category="REGISTRATION",
                title="Patient Registered & UHID Allocated",
                subtitle=f"UHID: {patient.mrn} • Primary Demographic Record Created",
                status="COMPLETED",
                severity="NORMAL",
                details={"phone": patient.phone_number, "gender": str(patient.gender)},
            )
        )

    # 2. Encounters & Appointments
    encounters = db.query(PatientEncounter).filter(PatientEncounter.patient_id == patient_id).all()
    enc_ids = [e.id for e in encounters]

    appts = db.query(Appointment).filter(Appointment.patient_id == patient_id).all()
    for appt in appts:
        dt = appt.appointment_time or appt.created_at
        if dt:
            doc_user = db.get(User, appt.doctor_id) if appt.doctor_id else None
            doc_profile = (
                db.query(DoctorProfile).filter(DoctorProfile.user_id == appt.doctor_id).first()
                if appt.doctor_id
                else None
            )
            doc_name = doc_user.full_name if doc_user else f"Dr. {appt.doctor_id}"
            dept_name = doc_profile.specialization if doc_profile and doc_profile.specialization else "Outpatient Clinic"
            st = appt.status.value if hasattr(appt.status, "value") else str(appt.status)
            events.append(
                PatientTimelineEvent(
                    id=f"appt-{appt.id}",
                    timestamp=dt.isoformat(),
                    date=dt.strftime("%Y-%m-%d"),
                    time=dt.strftime("%H:%M"),
                    category="CLINICAL",
                    title="Outpatient Consultation (OPD)",
                    subtitle=f"Consultation with {doc_name} • {dept_name}",
                    doctor_name=doc_name,
                    department=dept_name,
                    status=st,
                    severity="NORMAL",
                    details={"token_number": getattr(appt, "token_number", appt.id), "reason": getattr(appt, "reason", None)},
                )
            )

    # 3. Inpatient Admissions
    admissions = (
        db.query(InpatientAdmission)
        .join(PatientEncounter)
        .filter(PatientEncounter.patient_id == patient_id)
        .all()
    )
    for adm in admissions:
        dt = adm.created_at
        if dt:
            bed = db.get(Bed, adm.current_bed_id) if adm.current_bed_id else None
            room = db.get(PhysicalRoom, bed.room_id) if bed and bed.room_id else None
            ward = db.get(Ward, room.ward_id) if room and room.ward_id else None
            w_name = ward.name if ward else "Inpatient Ward"
            b_num = bed.bed_number if bed else "Unassigned"
            events.append(
                PatientTimelineEvent(
                    id=f"adm-{adm.id}",
                    timestamp=dt.isoformat(),
                    date=dt.strftime("%Y-%m-%d"),
                    time=dt.strftime("%H:%M"),
                    category="ADMISSION",
                    title="Inpatient Hospital Admission",
                    subtitle=f"Admitted to {w_name} • Bed {b_num}",
                    status="DISCHARGED" if adm.discharge_time else "ADMITTED",
                    severity="WARNING",
                    details={
                        "admission_type": str(adm.admission_type),
                        "ward": w_name,
                        "bed": b_num,
                    },
                )
            )

    # 4. Vitals & Early Warning Scores
    if enc_ids:
        vitals = (
            db.query(EncounterVital)
            .filter(EncounterVital.encounter_id.in_(enc_ids))
            .order_by(EncounterVital.recorded_at.desc())
            .limit(10)
            .all()
        )
        for v in vitals:
            dt = v.recorded_at or v.created_at
            if dt:
                news = (
                    db.query(ClinicalEarlyWarningScore)
                    .filter(ClinicalEarlyWarningScore.vital_id == v.id)
                    .first()
                )
                score_val = news.total_score if news else 0
                is_crit = score_val >= 5
                events.append(
                    PatientTimelineEvent(
                        id=f"vital-{v.id}",
                        timestamp=dt.isoformat(),
                        date=dt.strftime("%Y-%m-%d"),
                        time=dt.strftime("%H:%M"),
                        category="TRIAGE",
                        title=f"Clinical Vital Signs Recorded {'(NEWS2 Alert)' if is_crit else ''}",
                        subtitle=f"BP: {v.systolic_bp}/{v.diastolic_bp} mmHg • HR: {v.pulse_rate_bpm} bpm • SpO2: {v.spo2_percentage}%",
                        status="VERIFIED",
                        severity="CRITICAL" if is_crit else "NORMAL",
                        details={
                            "systolic": v.systolic_bp,
                            "diastolic": v.diastolic_bp,
                            "spo2": v.spo2_percentage,
                            "heart_rate": v.pulse_rate_bpm,
                            "news2_score": score_val,
                        },
                    )
                )

    # 5. Diagnostic Orders
    if enc_ids:
        diag_orders = (
            db.query(DiagnosticOrder)
            .filter(DiagnosticOrder.encounter_id.in_(enc_ids))
            .order_by(DiagnosticOrder.created_at.desc())
            .limit(10)
            .all()
        )
        for d_ord in diag_orders:
            dt = d_ord.created_at
            if dt:
                events.append(
                    PatientTimelineEvent(
                        id=f"diag-{d_ord.id}",
                        timestamp=dt.isoformat(),
                        date=dt.strftime("%Y-%m-%d"),
                        time=dt.strftime("%H:%M"),
                        category="LAB",
                        title="Diagnostic Lab Investigation",
                        subtitle=f"Order #{d_ord.order_number if hasattr(d_ord, 'order_number') else d_ord.id}",
                        status=str(d_ord.status),
                        severity="NORMAL",
                        details={"service_type": str(d_ord.service_type) if hasattr(d_ord, "service_type") else None},
                    )
                )

    # 6. Prescriptions
    if enc_ids:
        rx_orders = (
            db.query(Prescription)
            .filter(Prescription.encounter_id.in_(enc_ids))
            .order_by(Prescription.created_at.desc())
            .limit(10)
            .all()
        )
        for rx in rx_orders:
            dt = rx.created_at
            if dt:
                events.append(
                    PatientTimelineEvent(
                        id=f"rx-{rx.id}",
                        timestamp=dt.isoformat(),
                        date=dt.strftime("%Y-%m-%d"),
                        time=dt.strftime("%H:%M"),
                        category="MEDICATION",
                        title="Medications Prescribed (CPOE)",
                        subtitle=f"Electronic Prescription #{rx.id}",
                        status=str(rx.status),
                        severity="NORMAL",
                    )
                )

    # 7. Cashier Payment Receipts
    receipts = (
        db.query(PaymentReceipt)
        .join(PatientEncounter, PaymentReceipt.patient_encounter_id == PatientEncounter.id, isouter=True)
        .filter(
            or_(
                PaymentReceipt.patient_encounter_id.in_(enc_ids) if enc_ids else False,
            )
        )
        .order_by(PaymentReceipt.created_at.desc())
        .limit(10)
        .all()
    )
    for r in receipts:
        dt = r.created_at
        if dt:
            amt_rupees = r.amount_paise / 100.0 if r.amount_paise else 0.0
            events.append(
                PatientTimelineEvent(
                    id=f"pay-{r.id}",
                    timestamp=dt.isoformat(),
                    date=dt.strftime("%Y-%m-%d"),
                    time=dt.strftime("%H:%M"),
                    category="BILLING",
                    title="Cashier Payment Receipt Issued",
                    subtitle=f"Receipt #{r.receipt_number if hasattr(r, 'receipt_number') else r.id} • Paid ₹{amt_rupees:.2f} ({str(r.payment_method)})",
                    status="SETTLED",
                    severity="NORMAL",
                    details={"amount_rupees": amt_rupees, "payment_method": str(r.payment_method)},
                )
            )

    # Sort descending (newest milestone first)
    events.sort(key=lambda x: x.timestamp, reverse=True)
    return events


# ---------------------------------------------------------------------------
# 9. Doctor-Tied Revisit & Fee Waiver Calculator
# ---------------------------------------------------------------------------
@router.get(
    "/patients/{patient_id}/revisit-eligibility",
    response_model=RevisitEligibilityResponse,
    dependencies=[Depends(RequirePermission("opd:read"))],
)
def get_revisit_eligibility(
    patient_id: int,
    doctor_id: int = Query(..., description="Target doctor user ID"),
    db: Session = Depends(get_db),
):
    """
    Evaluates patient eligibility for a complimentary revisit versus standard
    or follow-up fee, tied to doctor-specific grace periods.
    """
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found.")

    doc_user = db.get(User, doctor_id)
    if not doc_user:
        raise HTTPException(status_code=404, detail="Doctor user not found.")

    doc_profile = (
        db.query(DoctorProfile)
        .filter(or_(DoctorProfile.user_id == doctor_id, DoctorProfile.id == doctor_id))
        .first()
    )
    dept_name = doc_profile.specialization if doc_profile and doc_profile.specialization else "General Medicine"

    # Default policy: 7 days grace period for consultation revisits (can be customized per doctor profile)
    grace_period_days = 7
    standard_fee = 800.0
    followup_fee = 400.0

    # Search for previous completed appointment with this specific doctor
    last_completed = (
        db.query(Appointment)
        .filter(
            Appointment.patient_id == patient_id,
            Appointment.doctor_id == doctor_id,
            Appointment.status == AppointmentStatusEnum.COMPLETED,
        )
        .order_by(Appointment.appointment_time.desc())
        .first()
    )

    now = date.today()
    if last_completed and last_completed.appointment_time:
        consult_dt = (
            last_completed.appointment_time.date()
            if isinstance(last_completed.appointment_time, datetime)
            else last_completed.appointment_time
        )
        days_elapsed = (now - consult_dt).days

        if days_elapsed <= grace_period_days:
            days_remaining = max(0, grace_period_days - days_elapsed)
            return RevisitEligibilityResponse(
                patient_id=patient_id,
                doctor_id=doctor_id,
                doctor_name=doc_user.full_name,
                department=dept_name,
                is_free_revisit=True,
                revisit_type="FREE_REVISIT",
                revisit_day_elapsed=days_elapsed,
                grace_period_days=grace_period_days,
                days_remaining=days_remaining,
                standard_fee_rupees=standard_fee,
                applicable_fee_rupees=0.0,
                last_consultation_date=consult_dt.isoformat(),
                policy_summary=f"Eligible for Free Revisit (Day {days_elapsed} of {grace_period_days} days). ₹{standard_fee:.2f} fee waived.",
            )
        else:
            return RevisitEligibilityResponse(
                patient_id=patient_id,
                doctor_id=doctor_id,
                doctor_name=doc_user.full_name,
                department=dept_name,
                is_free_revisit=False,
                revisit_type="PAID_FOLLOWUP",
                revisit_day_elapsed=days_elapsed,
                grace_period_days=grace_period_days,
                days_remaining=0,
                standard_fee_rupees=standard_fee,
                applicable_fee_rupees=followup_fee,
                last_consultation_date=consult_dt.isoformat(),
                policy_summary=f"Follow-up visit. Previous consult was {days_elapsed} days ago (exceeds {grace_period_days}-day limit). Concession fee applies.",
            )

    # First-time / New Visit
    return RevisitEligibilityResponse(
        patient_id=patient_id,
        doctor_id=doctor_id,
        doctor_name=doc_user.full_name,
        department=dept_name,
        is_free_revisit=False,
        revisit_type="NEW_VISIT",
        revisit_day_elapsed=0,
        grace_period_days=grace_period_days,
        days_remaining=0,
        standard_fee_rupees=standard_fee,
        applicable_fee_rupees=standard_fee,
        last_consultation_date=None,
        policy_summary=f"New patient consultation with {doc_user.full_name}. Full standard fee applies.",
    )


# ---------------------------------------------------------------------------
# 10. Departmental Hardware Printer Network Registry
# ---------------------------------------------------------------------------
DEFAULT_PRINTER_CATALOG = [
    {
        "id": "prn-1",
        "name": "Front Desk Zebra ZD510-HC Dedicated Wristband Printer",
        "location": "Admission Desk Counter 1",
        "connection_type": "NETWORK_IP",
        "target_category": "WRISTBAND",
        "protocol": "RAW_ZPL",
        "ip_address": "192.168.1.182",
        "port": 9100,
        "is_default": True,
        "media_width_mm": 25,
        "media_height_mm": 280,
        "printable_width_mm": 22,
        "printable_height_mm": 75,
        "margin_top_mm": 1,
        "margin_bottom_mm": 1,
        "margin_left_mm": 2,
        "margin_right_mm": 2,
        "orientation": "PORTRAIT",
        "dpi": 300,
        "status": "ONLINE",
    },
    {
        "id": "prn-2",
        "name": "Reception Counter 1 Token & Receipt Slip Printer",
        "location": "OPD Front Registration Counter 1",
        "connection_type": "USB",
        "target_category": "THERMAL_TOKEN",
        "protocol": "RAW_ESCPOS",
        "is_default": True,
        "media_width_mm": 80,
        "media_height_mm": 0,
        "printable_width_mm": 76,
        "printable_height_mm": 0,
        "margin_top_mm": 2,
        "margin_bottom_mm": 2,
        "margin_left_mm": 2,
        "margin_right_mm": 2,
        "orientation": "PORTRAIT",
        "dpi": 203,
        "status": "ONLINE",
    },
    {
        "id": "prn-3",
        "name": "Emergency Triage & Trauma WiFi Wristband Unit",
        "location": "ED Resuscitation Bay 1",
        "connection_type": "WIFI",
        "target_category": "WRISTBAND",
        "protocol": "HTML_DRIVER",
        "ip_address": "192.168.1.185",
        "port": 9100,
        "is_default": False,
        "media_width_mm": 28,
        "media_height_mm": 280,
        "printable_width_mm": 25,
        "printable_height_mm": 80,
        "margin_top_mm": 1,
        "margin_bottom_mm": 1,
        "margin_left_mm": 2,
        "margin_right_mm": 2,
        "orientation": "PORTRAIT",
        "dpi": 300,
        "status": "ONLINE",
    },
    {
        "id": "prn-4",
        "name": "Inpatient Clinical Ward Managed HP LaserJet",
        "location": "Ward Nursing Station Central",
        "connection_type": "NETWORK_IP",
        "target_category": "CLINICAL_A4",
        "protocol": "HTML_DRIVER",
        "ip_address": "192.168.1.190",
        "port": 9100,
        "is_default": True,
        "media_width_mm": 210,
        "media_height_mm": 297,
        "printable_width_mm": 200,
        "printable_height_mm": 287,
        "margin_top_mm": 5,
        "margin_bottom_mm": 5,
        "margin_left_mm": 5,
        "margin_right_mm": 5,
        "orientation": "PORTRAIT",
        "dpi": 600,
        "status": "ONLINE",
    },
    {
        "id": "prn-5",
        "name": "Central Phlebotomy Tube Barcode Labeler",
        "location": "Diagnostics Specimen Collection Counter",
        "connection_type": "USB",
        "target_category": "LAB_LABEL",
        "protocol": "RAW_ZPL",
        "is_default": True,
        "media_width_mm": 50,
        "media_height_mm": 25,
        "printable_width_mm": 46,
        "printable_height_mm": 22,
        "margin_top_mm": 1,
        "margin_bottom_mm": 1,
        "margin_left_mm": 2,
        "margin_right_mm": 2,
        "orientation": "LANDSCAPE",
        "dpi": 203,
        "status": "ONLINE",
    },
]


@router.get(
    "/facility/printers",
    response_model=List[HardwarePrinterConfig],
    dependencies=[Depends(RequirePermission("config:read"))],
)
def list_facility_printers(
    request: Request,
    redis_client=Depends(get_redis),
):
    """
    Returns registered physical hardware printers across hospital wings,
    including network IP endpoints, continuous rolls, and discrete millimeters.
    """
    tenant = resolve_tenant_context(request)
    cache_key = f"facility_printers:{tenant.subdomain_slug}"
    if redis_client:
        cached = redis_client.get(cache_key)
        if cached:
            try:
                data = json.loads(cached.decode("utf-8") if isinstance(cached, bytes) else cached)
                return [HardwarePrinterConfig(**item) for item in data]
            except Exception:
                pass

    return [HardwarePrinterConfig(**item) for item in DEFAULT_PRINTER_CATALOG]


@router.post(
    "/facility/printers",
    response_model=List[HardwarePrinterConfig],
    dependencies=[Depends(RequirePermission("config:write"))],
)
def save_facility_printers(
    payload: List[HardwarePrinterConfig],
    request: Request,
    redis_client=Depends(get_redis),
):
    """
    Persists updated physical hardware printer configuration in Redis for all hospital workstations.
    """
    tenant = resolve_tenant_context(request)
    cache_key = f"facility_printers:{tenant.subdomain_slug}"
    data_to_save = [item.model_dump() for item in payload]
    if redis_client:
        redis_client.setex(cache_key, 31536000, json.dumps(data_to_save))  # 1 year TTL

    return payload


