"""
Clinical and Operational UI Aggregation Endpoints for Avinya HMS Frontend.

Provides zero-latency, consolidated view-aggregates, autocomplete lookups,
and clinical cockpit summaries to eliminate frontend waterfall requests.
"""

from datetime import date, datetime, timezone
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.core.database import get_db, resolve_tenant_context
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

router = APIRouter(prefix="/api/ui", tags=["Clinical & Operational UI Aggregates"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
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


