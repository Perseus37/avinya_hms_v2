from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select,func
from sqlalchemy.orm import Session, joinedload

from backend.domains.policies.router import get_or_create_policy
from backend.core.database import get_db, resolve_tenant_context
from backend.core.dependencies import RequirePermission, ensure_department_id_access, get_user_assigned_department_ids, validate_pagination
from backend.core.date_ranges import resolve_record_date_window
from backend.core.export import stream_csv_response, chunked_query_fetcher
from backend.domains.encounters.models import Appointment, AppointmentStatusEnum, AppointmentStatusHistory, AppointmentWaitlistEntry, AppointmentWaitlistHistory, AppointmentWaitlistStatusEnum, DoctorLeave, PatientEncounter, EncounterTypeEnum, EncounterStatusEnum, ServiceDemandReasonEnum, ServiceDemandRequest, ServiceDemandStatusEnum, ServiceDemandStatusHistory
from backend.domains.identity.models import DoctorProfile, User
from backend.domains.patients.models import Patient
from backend.schemas.common import PaginatedResponse
from backend.domains.encounters.schemas import AppointmentCreate, AppointmentResponse, AppointmentStatusHistoryResponse, AppointmentStatusUpdate, AppointmentUpdate, AppointmentWaitlistBook, AppointmentWaitlistCreate, AppointmentWaitlistHistoryResponse, AppointmentWaitlistResponse, DoctorLeaveCreate, DoctorLeaveResponse, ServiceDemandCreate, ServiceDemandResponse, ServiceDemandStatusHistoryResponse, ServiceDemandUpdate
from backend.domains.billing.services import auto_bill_opd_consultation
from backend.domains.billing.models import Invoice, InvoiceStatusEnum
from backend.domains.diagnostics.models import ServiceCatalog
from backend.domains.identity.models import Department
from backend.core.event_bus import publish_tenant_event
from backend.domains.privacy.runtime import evaluate_tenant_patient_data_uses

router = APIRouter(prefix="/api/opd", tags=["Outpatient Scheduling (OPD), Tokens & Doctor Leaves"])


def _to_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def check_doctor_on_leave(db: Session, doctor_id: int, appointment_time: datetime) -> Optional[DoctorLeave]:
    appt_utc = _to_utc(appointment_time)
    leaves = list(
        db.execute(
            select(DoctorLeave).where(
                DoctorLeave.doctor_id == doctor_id,
                DoctorLeave.is_active == True,
            )
        )
        .scalars()
        .all()
    )
    for lv in leaves:
        if _to_utc(lv.start_time) <= appt_utc <= _to_utc(lv.end_time):
            return lv
    return None


def check_schedule_overlap(
    db: Session,
    doctor_id: int,
    appointment_time: datetime,
    duration: int,
    exclude_appointment_id: Optional[int] = None,
) -> bool:
    """Helper to detect scheduling conflicts, optionally excluding the appointment being rescheduled."""
    time_lower_bound = appointment_time - timedelta(minutes=duration)
    time_upper_bound = appointment_time + timedelta(minutes=duration)

    query = db.query(Appointment).filter(
        Appointment.doctor_id == doctor_id,
        Appointment.status.in_([AppointmentStatusEnum.SCHEDULED, AppointmentStatusEnum.ARRIVED]),
        Appointment.appointment_time > time_lower_bound,
        Appointment.appointment_time < time_upper_bound,
    )
    if exclude_appointment_id is not None:
        query = query.filter(Appointment.id != exclude_appointment_id)

    return query.first() is not None


def _compute_next_daily_token(db: Session, doctor_id: int, appointment_time: datetime) -> int:
    appt_utc = _to_utc(appointment_time)
    day_start = appt_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    same_day_count = (
        db.scalar(
            select(func.count(Appointment.id)).where(
                Appointment.doctor_id == doctor_id,
                Appointment.appointment_time >= day_start,
                Appointment.appointment_time < day_end,
            )
        )
        or 0
    )
    return same_day_count + 1


@router.post("/doctors/leaves", response_model=DoctorLeaveResponse, status_code=status.HTTP_201_CREATED)
def register_doctor_leave_blackout(
    payload: DoctorLeaveCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("opd:write", "iam:write")),
):
    doctor = db.execute(
        select(DoctorProfile).where(DoctorProfile.user_id == payload.doctor_id)
    ).scalar_one_or_none()
    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor profile not found.")
    ensure_department_id_access(db, doctor.department_id, current_user)
    if _to_utc(payload.end_time) <= _to_utc(payload.start_time):
        raise HTTPException(status_code=400, detail="Leave end_time must be after start_time.")

    leave = DoctorLeave(**payload.model_dump(), is_active=True)
    db.add(leave)
    db.commit()
    db.refresh(leave)
    return leave


@router.get("/doctors/{doctor_id}/leaves", response_model=List[DoctorLeaveResponse])
def list_doctor_leaves(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("opd:read")),
):
    doctor = db.execute(
        select(DoctorProfile).where(DoctorProfile.user_id == doctor_id)
    ).scalar_one_or_none()
    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor profile not found.")
    ensure_department_id_access(db, doctor.department_id, current_user)
    stmt = (
        select(DoctorLeave)
        .where(DoctorLeave.doctor_id == doctor_id, DoctorLeave.is_active == True)
        .order_by(DoctorLeave.start_time.asc())
    )
    return list(db.execute(stmt).scalars().all())


@router.post("/appointments", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def book_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("opd:write")),
):
    """Schedules an OPD appointment and prepares its planned encounter and consultation billing ledger."""
    patient = db.get(Patient, payload.patient_id)
    if not patient or not patient.is_active:
        raise HTTPException(status_code=400, detail="Invalid or inactive patient.")
    ensure_department_id_access(db, payload.department_id, current_user)

    doctor = db.execute(
        select(DoctorProfile)
        .where(DoctorProfile.user_id == payload.doctor_id)
        .with_for_update()
    ).scalar_one_or_none()

    if not doctor:
        raise HTTPException(status_code=400, detail="Invalid doctor ID.")
    if doctor.department_id != payload.department_id:
        raise HTTPException(
            status_code=400,
            detail="Appointment department must match the selected doctor's registered department.",
        )

    active_leave = check_doctor_on_leave(db, payload.doctor_id, payload.appointment_time)
    if active_leave:
        raise HTTPException(
            status_code=409,
            detail=f"Doctor is unavailable / on leave during this window ({active_leave.reason}).",
        )

    duration = max(doctor.consultation_duration_minutes, 5)
    if check_schedule_overlap(db, payload.doctor_id, payload.appointment_time, duration):
        raise HTTPException(status_code=409, detail=f"Scheduling conflict detected at {payload.appointment_time}.")

    token_num = _compute_next_daily_token(db, payload.doctor_id, payload.appointment_time)
    appointment = Appointment(
        **payload.model_dump(),
        planned_duration_minutes=duration,
        status=AppointmentStatusEnum.SCHEDULED,
        token_number=token_num,
    )
    db.add(appointment)
    db.flush()

    encounter = PatientEncounter(
        patient_id=appointment.patient_id,
        encounter_type=EncounterTypeEnum.OPD,
        status=EncounterStatusEnum.PLANNED,
        start_time=appointment.appointment_time,
        primary_doctor_id=appointment.doctor_id,
        department_id=appointment.department_id,
        chief_complaint_notes=appointment.reason_for_visit,
    )
    db.add(encounter)
    db.flush()
    appointment.encounter_id = encounter.id

    # Creates the consultation DRAFT invoice only when the doctor has a configured fee.
    # Billing staff must finalize and settle it before queue admission can issue a token.
    auto_bill_opd_consultation(db, appointment.patient_id, encounter.id, appointment.doctor_id)

    db.add(
        AppointmentStatusHistory(
            appointment_id=appointment.id,
            from_status=None,
            to_status=AppointmentStatusEnum.SCHEDULED.value,
            changed_by_id=current_user.id,
            reason="Appointment booked; planned OPD encounter and billing ledger prepared",
        )
    )
    db.commit()
    db.refresh(appointment)
    return appointment


@router.get(
    "/appointments",
    response_model=PaginatedResponse[AppointmentResponse],
    openapi_extra={"x-privacy-data-use-point": "opd.appointments.search"},
)
def list_appointments(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    patient_id: Optional[int] = None,
    doctor_id: Optional[int] = None,
    department_id: Optional[int] = None,
    appointment_status: Optional[AppointmentStatusEnum] = Query(default=None, alias="status"),
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    actor: User = Depends(RequirePermission("opd:read")),
):
    """List appointments only within the actor's assigned clinical departments."""
    start_at, end_at = resolve_record_date_window(start_date, end_date)
    query = db.query(Appointment)
    assigned_department_ids = get_user_assigned_department_ids(db, actor)
    if assigned_department_ids is not None:
        query = query.filter(Appointment.department_id.in_(assigned_department_ids))
    if department_id is not None:
        ensure_department_id_access(db, department_id, actor)
        query = query.filter(Appointment.department_id == department_id)
    if patient_id is not None:
        query = query.filter(Appointment.patient_id == patient_id)
    if doctor_id is not None:
        query = query.filter(Appointment.doctor_id == doctor_id)
    if appointment_status is not None:
        query = query.filter(Appointment.status == appointment_status)
    if start_at is not None and end_at is not None:
        query = query.filter(
            Appointment.appointment_time >= start_at,
            Appointment.appointment_time < end_at,
        )

    page, page_size = validate_pagination(page, page_size)
    query = query.order_by(Appointment.appointment_time.asc(), Appointment.id.asc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    decisions = evaluate_tenant_patient_data_uses(
        db,
        data_use_point="opd.appointments.search",
        patient_ids=[item.patient_id for item in items],
        actor_user_id=actor.id,
    )
    if any(not decision.allowed for decision in decisions):
        raise HTTPException(
            status_code=403,
            detail="Privacy policy does not permit one or more patient disclosures.",
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}
