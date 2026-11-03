from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import RequirePermission
from backend.domains.encounters.models import Appointment, AppointmentStatusEnum, AppointmentStatusHistory, EncounterStatusEnum, PatientEncounter
from backend.domains.encounters.opd_queue_models import OPDQueue, OPDQueueEntry, OPDQueueEntryStatus, OPDQueueEvent
from backend.domains.identity.models import User
from backend.domains.billing.services import assert_opd_consultation_paid


class LifecycleReasonPayload(BaseModel):
    reason_code: Optional[str] = Field(default=None, max_length=40)
    reason_note: Optional[str] = Field(default=None, max_length=500)


def register(router):
    def branch_code(db: Session) -> str:
        value = db.info.get("tenant_branch_code")
        if not value:
            raise HTTPException(status_code=500, detail="Trusted branch context is unavailable.")
        return str(value)

    def queue_entry(db: Session, queue_id: int, entry_id: int):
        queue = db.execute(
            select(OPDQueue).where(OPDQueue.id == queue_id, OPDQueue.branch_code == branch_code(db)).with_for_update()
        ).scalar_one_or_none()
        if queue is None:
            raise HTTPException(status_code=404, detail="OPD queue not found.")
        entry = db.execute(
            select(OPDQueueEntry).where(OPDQueueEntry.id == entry_id, OPDQueueEntry.queue_id == queue.id).with_for_update()
        ).scalar_one_or_none()
        if entry is None:
            raise HTTPException(status_code=404, detail="Queue entry not found.")
        return queue, entry

    def response(queue, entry, event):
        return {
            "queue_id": queue.id,
            "entry_id": entry.id,
            "appointment_id": entry.appointment_id,
            "encounter_id": entry.encounter_id,
            "token_number": entry.token_number,
            "state": entry.state.value,
            "queue_version": queue.version,
            "event_id": event.id,
        }

    def record_event(db, queue, entry, actor, event_type, before, reason):
        event = OPDQueueEvent(
            queue_id=queue.id,
            entry_id=entry.id,
            actor_id=actor.id,
            event_type=event_type,
            from_state=before,
            to_state=entry.state.value,
            reason_code=reason.reason_code if reason else None,
            reason_note=reason.reason_note if reason else None,
        )
        db.add(event)
        queue.version += 1
        entry.version += 1
        db.flush()
        return event

    @router.post("/{queue_id}/entries/{entry_id}/start", status_code=200)
    def start_from_queue(
        queue_id: int,
        entry_id: int,
        payload: LifecycleReasonPayload | None = None,
        db: Session = Depends(get_db),
        current_user: User = Depends(RequirePermission("opd:write")),
    ):
        queue, entry = queue_entry(db, queue_id, entry_id)
        if entry.state != OPDQueueEntryStatus.ARRIVED:
            raise HTTPException(status_code=409, detail="Patient must be ARRIVED before consultation starts.")
        appointment = db.execute(
            select(Appointment).where(Appointment.id == entry.appointment_id).with_for_update()
        ).scalar_one_or_none()
        if appointment is None or appointment.status != AppointmentStatusEnum.ARRIVED:
            raise HTTPException(status_code=409, detail="Linked appointment is not ARRIVED.")
        if not entry.encounter_id or appointment.encounter_id != entry.encounter_id:
            raise HTTPException(status_code=409, detail="Queue entry has no valid appointment encounter linkage.")
        encounter = db.execute(
            select(PatientEncounter).where(PatientEncounter.id == entry.encounter_id).with_for_update()
        ).scalar_one_or_none()
        if encounter is None or encounter.patient_id != appointment.patient_id or encounter.primary_doctor_id != appointment.doctor_id or encounter.department_id != appointment.department_id or encounter.status not in (EncounterStatusEnum.PLANNED, EncounterStatusEnum.ACTIVE):
            raise HTTPException(status_code=409, detail="Encounter does not match the appointment clinical context.")
        assert_opd_consultation_paid(db, encounter.id, appointment.patient_id)

        now = datetime.now(timezone.utc)
        encounter.status = EncounterStatusEnum.ACTIVE
        encounter.start_time = encounter.start_time or now
        previous_appointment = appointment.status
        appointment.status = AppointmentStatusEnum.IN_CONSULTATION
        db.add(AppointmentStatusHistory(
            appointment_id=appointment.id,
            from_status=previous_appointment.value,
            to_status=appointment.status.value,
            changed_by_id=current_user.id,
            reason=(payload.reason_note if payload and payload.reason_note else "OPD consultation started"),
        ))
        before = entry.state.value
        entry.state = OPDQueueEntryStatus.IN_CONSULTATION
        entry.consultation_started_at = now
        event = record_event(db, queue, entry, current_user, "CONSULTATION_STARTED", before, payload or LifecycleReasonPayload())
        result = response(queue, entry, event)
        db.commit()
        return result

    @router.post("/{queue_id}/entries/{entry_id}/complete", status_code=200)
    def complete_from_queue(
        queue_id: int,
        entry_id: int,
        payload: LifecycleReasonPayload | None = None,
        db: Session = Depends(get_db),
        current_user: User = Depends(RequirePermission("opd:write")),
    ):
        queue, entry = queue_entry(db, queue_id, entry_id)
        if entry.state != OPDQueueEntryStatus.IN_CONSULTATION:
            raise HTTPException(status_code=409, detail="Only an active consultation can be completed.")
        appointment = db.execute(
            select(Appointment).where(Appointment.id == entry.appointment_id).with_for_update()
        ).scalar_one_or_none()
        if appointment is None or appointment.status != AppointmentStatusEnum.IN_CONSULTATION:
            raise HTTPException(status_code=409, detail="Linked appointment is not IN_CONSULTATION.")
        now = datetime.now(timezone.utc)
        previous_appointment = appointment.status
        appointment.status = AppointmentStatusEnum.COMPLETED
        db.add(AppointmentStatusHistory(
            appointment_id=appointment.id,
            from_status=previous_appointment.value,
            to_status=appointment.status.value,
            changed_by_id=current_user.id,
            reason=(payload.reason_note if payload and payload.reason_note else "OPD consultation completed"),
        ))
        before = entry.state.value
        entry.state = OPDQueueEntryStatus.COMPLETED
        entry.completed_at = now
        event = record_event(db, queue, entry, current_user, "CONSULTATION_COMPLETED", before, payload or LifecycleReasonPayload())
        result = response(queue, entry, event)
        db.commit()
        return result
