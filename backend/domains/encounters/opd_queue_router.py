"""Transactional OPD queue commands.

The queue row is the serialization point: call-next and call-specific both lock
it before checking the single-active-call invariant.
"""
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import RequirePermission
from backend.domains.encounters.models import (
    Appointment, AppointmentStatusEnum, AppointmentStatusHistory,
)
from backend.domains.encounters.opd_queue_models import (
    OPDQueue, OPDQueueEntry, OPDQueueEntryStatus, OPDQueueEvent,
    OPDQueueStatus,
)
from backend.domains.identity.models import User

router = APIRouter(prefix="/api/opd/queues", tags=["OPD Queue V1"])


class CheckInPayload(BaseModel):
    appointment_id: int = Field(gt=0)
    room_label: Optional[str] = Field(default=None, max_length=100)


class CallSpecificPayload(BaseModel):
    reason_code: str = Field(min_length=1, max_length=40)
    reason_note: Optional[str] = Field(default=None, max_length=500)
    expected_version: Optional[int] = Field(default=None, ge=1)


class QueueCommandResponse(BaseModel):
    queue_id: int
    entry_id: int
    token_number: int
    state: str
    queue_version: int
    event_id: int
    first_called_at: Optional[datetime] = None
    last_called_at: Optional[datetime] = None


def _branch_code(db: Session) -> str:
    value = db.info.get("tenant_branch_code")
    if not value:
        raise HTTPException(status_code=500, detail="Trusted branch context is unavailable.")
    return str(value)


def _queue_or_404(db: Session, queue_id: int, branch_code: str, *, lock: bool = False):
    stmt = select(OPDQueue).where(
        OPDQueue.id == queue_id,
        OPDQueue.branch_code == branch_code,
    )
    if lock:
        stmt = stmt.with_for_update()
    queue = db.execute(stmt).scalar_one_or_none()
    if queue is None:
        raise HTTPException(status_code=404, detail="OPD queue not found.")
    return queue


def _entry_or_404(db: Session, entry_id: int, queue_id: int, *, lock: bool = False):
    stmt = select(OPDQueueEntry).where(
        OPDQueueEntry.id == entry_id,
        OPDQueueEntry.queue_id == queue_id,
    )
    if lock:
        stmt = stmt.with_for_update()
    entry = db.execute(stmt).scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Queue entry not found.")
    return entry


def _active_call(db: Session, queue_id: int):
    return db.execute(
        select(OPDQueueEntry)
        .where(
            OPDQueueEntry.queue_id == queue_id,
            OPDQueueEntry.state.in_([
                OPDQueueEntryStatus.CALLED,
                OPDQueueEntryStatus.ARRIVED,
                OPDQueueEntryStatus.IN_CONSULTATION,
            ]),
        )
        .order_by(OPDQueueEntry.id)
        .limit(1)
    ).scalar_one_or_none()


def _record_event(db, queue, entry, actor, event_type, from_state, to_state, reason_code=None, reason_note=None):
    event = OPDQueueEvent(
        queue_id=queue.id,
        entry_id=entry.id,
        actor_id=actor.id,
        event_type=event_type,
        from_state=from_state,
        to_state=to_state,
        reason_code=reason_code,
        reason_note=reason_note,
    )
    db.add(event)
    queue.version += 1
    entry.version += 1
    return event


def _response(queue, entry, event):
    return QueueCommandResponse(
        queue_id=queue.id,
        entry_id=entry.id,
        token_number=entry.token_number,
        state=entry.state.value,
        queue_version=queue.version,
        event_id=event.id,
        first_called_at=entry.first_called_at,
        last_called_at=entry.last_called_at,
    )


@router.post("/check-in", status_code=201)
def check_in_appointment(
    payload: CheckInPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("opd:write")),
):
    """Admit an existing appointment into its branch/doctor OPD queue."""
    branch_code = _branch_code(db)
    appointment = db.execute(
        select(Appointment).where(Appointment.id == payload.appointment_id).with_for_update()
    ).scalar_one_or_none()
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found.")
    if appointment.status not in (AppointmentStatusEnum.SCHEDULED, AppointmentStatusEnum.ARRIVED):
        raise HTTPException(status_code=409, detail=f"Appointment cannot enter the queue from {appointment.status.value}.")
    if appointment.appointment_time.date() != date.today():
        raise HTTPException(status_code=409, detail="Only appointments scheduled for today can enter today's OPD queue.")

    # Insert-on-conflict handles two receptionists creating the same doctor queue concurrently.
    queue_insert = pg_insert(OPDQueue).values(
        branch_code=branch_code,
        service_date=date.today(),
        department_id=appointment.department_id,
        doctor_id=appointment.doctor_id,
        room_label=payload.room_label,
        status=OPDQueueStatus.OPEN,
        version=1,
    ).on_conflict_do_nothing(
        constraint="uq_opd_queue_branch_date_department_doctor"
    )
    db.execute(queue_insert)
    queue = db.execute(
        select(OPDQueue).where(
            OPDQueue.branch_code == branch_code,
            OPDQueue.service_date == date.today(),
            OPDQueue.department_id == appointment.department_id,
            OPDQueue.doctor_id == appointment.doctor_id,
        ).with_for_update()
    ).scalar_one()

    existing = db.execute(
        select(OPDQueueEntry).where(OPDQueueEntry.appointment_id == appointment.id)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Appointment is already admitted to an OPD queue.")

    max_position = db.scalar(
        select(func.max(OPDQueueEntry.queue_position)).where(OPDQueueEntry.queue_id == queue.id)
    ) or 0
    max_token = db.scalar(
        select(func.max(OPDQueueEntry.token_number)).where(OPDQueueEntry.queue_id == queue.id)
    ) or 0
    entry = OPDQueueEntry(
        queue_id=queue.id,
        appointment_id=appointment.id,
        patient_id=appointment.patient_id,
        encounter_id=appointment.encounter_id,
        token_number=max_token + 1,
        queue_position=max_position + 1,
        priority=100,
        state=OPDQueueEntryStatus.WAITING,
        checked_in_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    if appointment.status == AppointmentStatusEnum.SCHEDULED:
        previous = appointment.status
        appointment.status = AppointmentStatusEnum.ARRIVED
        db.add(AppointmentStatusHistory(
            appointment_id=appointment.id,
            from_status=previous.value,
            to_status=AppointmentStatusEnum.ARRIVED.value,
            changed_by_id=current_user.id,
            reason="OPD queue check-in",
        ))
    db.flush()
    event = _record_event(
        db, queue, entry, current_user, "PATIENT_CHECKED_IN",
        None, OPDQueueEntryStatus.WAITING.value,
    )
    db.flush()
    result = {
        "queue_id": queue.id, "entry_id": entry.id,
        "appointment_id": appointment.id, "patient_id": appointment.patient_id,
        "token_number": entry.token_number, "queue_position": entry.queue_position,
        "state": entry.state.value, "queue_version": queue.version,
        "event_id": event.id,
    }
    db.commit()
    return result


@router.get("")
def list_queues(
    service_date: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("opd:read")),
):
    branch_code = _branch_code(db)
    service_date = service_date or date.today()
    rows = db.execute(
        select(OPDQueue).where(
            OPDQueue.branch_code == branch_code,
            OPDQueue.service_date == service_date,
        ).order_by(OPDQueue.department_id, OPDQueue.doctor_id)
    ).scalars().all()
    return [{
        "id": q.id, "service_date": q.service_date.isoformat(),
        "department_id": q.department_id, "doctor_id": q.doctor_id,
        "room_label": q.room_label, "status": q.status.value,
        "version": q.version,
    } for q in rows]


@router.get("/{queue_id}/entries")
def list_queue_entries(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("opd:read")),
):
    queue = _queue_or_404(db, queue_id, _branch_code(db))
    rows = db.execute(
        select(OPDQueueEntry).where(OPDQueueEntry.queue_id == queue.id)
        .order_by(OPDQueueEntry.priority, OPDQueueEntry.queue_position)
    ).scalars().all()
    return [{
        "id": e.id, "appointment_id": e.appointment_id,
        "patient_id": e.patient_id, "token_number": e.token_number,
        "queue_position": e.queue_position, "priority": e.priority,
        "state": e.state.value, "version": e.version,
        "checked_in_at": e.checked_in_at.isoformat(),
        "first_called_at": e.first_called_at.isoformat() if e.first_called_at else None,
    } for e in rows]


def _call_entry(db, queue, entry, actor, *, reason_code=None, reason_note=None, event_type="PATIENT_CALLED"):
    if queue.status != OPDQueueStatus.OPEN:
        raise HTTPException(status_code=409, detail="Queue is not open.")
    if entry.state != OPDQueueEntryStatus.WAITING:
        raise HTTPException(status_code=409, detail="Only waiting patients can be called.")
    active = _active_call(db, queue.id)
    if active is not None:
        raise HTTPException(
            status_code=409,
            detail={"message": "Another patient is already active in this queue.", "active_entry_id": active.id},
        )
    now = datetime.now(timezone.utc)
    entry.state = OPDQueueEntryStatus.CALLED
    entry.first_called_at = entry.first_called_at or now
    entry.last_called_at = now
    entry.reason_code = reason_code
    entry.reason_note = reason_note
    event = _record_event(
        db, queue, entry, actor, event_type,
        OPDQueueEntryStatus.WAITING.value, OPDQueueEntryStatus.CALLED.value,
        reason_code, reason_note,
    )
    db.flush()
    return _response(queue, entry, event)


@router.post("/{queue_id}/call-next", response_model=QueueCommandResponse)
def call_next(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("opd:write")),
):
    queue = _queue_or_404(db, queue_id, _branch_code(db), lock=True)
    if _active_call(db, queue.id):
        raise HTTPException(status_code=409, detail="A patient is already active in this queue.")
    entry = db.execute(
        select(OPDQueueEntry)
        .where(
            OPDQueueEntry.queue_id == queue.id,
            OPDQueueEntry.state == OPDQueueEntryStatus.WAITING,
        )
        .order_by(OPDQueueEntry.priority, OPDQueueEntry.queue_position, OPDQueueEntry.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    ).scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="No waiting patients in this queue.")
    result = _call_entry(db, queue, entry, current_user)
    db.commit()
    return result


@router.post("/{queue_id}/entries/{entry_id}/call", response_model=QueueCommandResponse)
def call_specific(
    queue_id: int,
    entry_id: int,
    payload: CallSpecificPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("opd:write")),
):
    if payload.reason_code == "OTHER" and not payload.reason_note:
        raise HTTPException(status_code=422, detail="A reason note is required for OTHER.")
    queue = _queue_or_404(db, queue_id, _branch_code(db), lock=True)
    if payload.expected_version is not None and payload.expected_version != queue.version:
        raise HTTPException(status_code=409, detail={"message": "Queue version conflict.", "current_version": queue.version})
    entry = _entry_or_404(db, entry_id, queue.id, lock=True)
    result = _call_entry(
        db, queue, entry, current_user,
        reason_code=payload.reason_code,
        reason_note=payload.reason_note,
        event_type="PATIENT_CALLED_OUT_OF_SEQUENCE",
    )
    db.commit()
    return result


@router.post("/{queue_id}/entries/{entry_id}/repeat-call", response_model=QueueCommandResponse)
def repeat_call(
    queue_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("opd:write")),
):
    queue = _queue_or_404(db, queue_id, _branch_code(db), lock=True)
    entry = _entry_or_404(db, entry_id, queue.id, lock=True)
    if entry.state != OPDQueueEntryStatus.CALLED:
        raise HTTPException(status_code=409, detail="Only the currently called patient can be announced again.")
    entry.last_called_at = datetime.now(timezone.utc)
    event = _record_event(
        db, queue, entry, current_user, "PATIENT_CALL_REPEATED",
        entry.state.value, entry.state.value,
    )
    db.flush()
    result = _response(queue, entry, event)
    db.commit()
    return result


@router.post("/{queue_id}/entries/{entry_id}/arrive", response_model=QueueCommandResponse)
def mark_arrived(
    queue_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("opd:write")),
):
    queue = _queue_or_404(db, queue_id, _branch_code(db), lock=True)
    entry = _entry_or_404(db, entry_id, queue.id, lock=True)
    if entry.state != OPDQueueEntryStatus.CALLED:
        raise HTTPException(status_code=409, detail="Only a called patient can be marked arrived.")
    before = entry.state.value
    entry.state = OPDQueueEntryStatus.ARRIVED
    entry.arrived_at = datetime.now(timezone.utc)
    event = _record_event(db, queue, entry, current_user, "PATIENT_ARRIVED", before, entry.state.value)
    db.flush()
    result = _response(queue, entry, event)
    db.commit()
    return result


class QueueReasonPayload(BaseModel):
    reason_code: str = Field(min_length=1, max_length=40)
    reason_note: Optional[str] = Field(default=None, max_length=500)


def _change_appointment_status(db, appointment_id, target_status, actor, reason):
    appointment = db.execute(
        select(Appointment).where(Appointment.id == appointment_id).with_for_update()
    ).scalar_one_or_none()
    if appointment is None:
        raise HTTPException(status_code=409, detail="Linked appointment no longer exists.")
    if appointment.status == target_status:
        return
    previous = appointment.status
    appointment.status = target_status
    db.add(AppointmentStatusHistory(
        appointment_id=appointment.id,
        from_status=previous.value,
        to_status=target_status.value,
        changed_by_id=actor.id,
        reason=reason,
    ))


@router.post("/{queue_id}/entries/{entry_id}/hold", response_model=QueueCommandResponse)
def hold_entry(
    queue_id: int,
    entry_id: int,
    payload: QueueReasonPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("opd:write")),
):
    queue = _queue_or_404(db, queue_id, _branch_code(db), lock=True)
    entry = _entry_or_404(db, entry_id, queue.id, lock=True)
    if entry.state not in (OPDQueueEntryStatus.WAITING, OPDQueueEntryStatus.CALLED):
        raise HTTPException(status_code=409, detail="Only waiting or called patients can be placed on hold.")
    previous = entry.state.value
    entry.state = OPDQueueEntryStatus.ON_HOLD
    entry.reason_code = payload.reason_code
    entry.reason_note = payload.reason_note
    event = _record_event(
        db, queue, entry, current_user, "PATIENT_PUT_ON_HOLD",
        previous, entry.state.value, payload.reason_code, payload.reason_note,
    )
    db.flush()
    result = _response(queue, entry, event)
    db.commit()
    return result


@router.post("/{queue_id}/entries/{entry_id}/release-hold", response_model=QueueCommandResponse)
def release_hold(
    queue_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("opd:write")),
):
    queue = _queue_or_404(db, queue_id, _branch_code(db), lock=True)
    entry = _entry_or_404(db, entry_id, queue.id, lock=True)
    if entry.state != OPDQueueEntryStatus.ON_HOLD:
        raise HTTPException(status_code=409, detail="Only patients on hold can be released.")
    entry.state = OPDQueueEntryStatus.WAITING
    entry.reason_code = None
    entry.reason_note = None
    event = _record_event(
        db, queue, entry, current_user, "PATIENT_RELEASED_FROM_HOLD",
        OPDQueueEntryStatus.ON_HOLD.value, OPDQueueEntryStatus.WAITING.value,
    )
    db.flush()
    result = _response(queue, entry, event)
    db.commit()
    return result


@router.post("/{queue_id}/entries/{entry_id}/no-show", response_model=QueueCommandResponse)
def mark_no_show(
    queue_id: int,
    entry_id: int,
    payload: QueueReasonPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("opd:write")),
):
    queue = _queue_or_404(db, queue_id, _branch_code(db), lock=True)
    entry = _entry_or_404(db, entry_id, queue.id, lock=True)
    if entry.state not in (OPDQueueEntryStatus.WAITING, OPDQueueEntryStatus.CALLED):
        raise HTTPException(status_code=409, detail="Only waiting or called patients can be marked no-show.")
    previous = entry.state.value
    entry.state = OPDQueueEntryStatus.NO_SHOW
    entry.reason_code = payload.reason_code
    entry.reason_note = payload.reason_note
    _change_appointment_status(
        db, entry.appointment_id, AppointmentStatusEnum.NO_SHOW, current_user,
        f"OPD no-show: {payload.reason_code} {payload.reason_note or ''}".strip(),
    )
    event = _record_event(
        db, queue, entry, current_user, "PATIENT_MARKED_NO_SHOW",
        previous, entry.state.value, payload.reason_code, payload.reason_note,
    )
    db.flush()
    result = _response(queue, entry, event)
    db.commit()
    return result
