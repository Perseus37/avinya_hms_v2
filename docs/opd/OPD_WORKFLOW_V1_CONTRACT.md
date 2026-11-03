# OPD Workflow V1 — Domain & API Contract

Status: Draft for implementation  
Branch: `feature/opd-workflow-v1`  
Base: `ui-redesign/v1`

## 1. Goals

Deliver a reliable, shared OPD workflow for reception, doctors, waiting-room displays and clinical staff. The database is the source of truth. Browser state is a cache/presentation layer only.

V1 includes appointment/walk-in check-in, queue orchestration, calling, specific-patient override, waiting-room display snapshots, doctor queue controls, nurse assessment, SOAP documentation, diagnoses, orders and encounter completion.

## 2. Domain boundaries

Do not create a second patient or appointment system. Queue entries reference the existing patient, appointment and encounter records. An appointment may have at most one active queue entry for the relevant visit/branch/queue date. Walk-ins must use the existing appointment/encounter creation workflow (or an explicitly approved walk-in command) before queue admission.

Recommended queue aggregate:

- `OPDQueue`: tenant/branch, service date, department/specialty, assigned doctor, room, status, sequence/version.
- `OPDQueueEntry`: patient_id, appointment_id (nullable only for approved walk-in flow), encounter_id (nullable until encounter creation), token, priority, queue_position, state, check-in/called/arrived/consultation timestamps, hold/skip/no-show metadata.
- `OPDQueueEvent`: immutable actor/action/reason, before/after state and position, aggregate version, occurred_at, correlation_id.
- `OPDDisplayDevice`: branch, configured display scope, enabled state, opaque credential/device key reference and last_seen_at. Never expose clinical data to display clients.

All records must be tenant- and branch-scoped. Enforce tenant isolation in the database/session layer and authorization layer; never trust tenant/branch identifiers supplied by the browser.

## 3. Separate state machines

### Appointment
`SCHEDULED -> CHECKED_IN -> IN_CONSULTATION -> COMPLETED`  
Terminal/alternate states: `CANCELLED`, `NO_SHOW`, `RESCHEDULED`.

Map legacy appointment statuses at the API boundary; do not silently rewrite persisted legacy values without a migration and compatibility plan.

### Queue entry
`WAITING -> CALLED -> ARRIVED -> IN_CONSULTATION -> COMPLETED`

Allowed alternate transitions (policy/permission controlled):
- `CALLED -> WAITING` via explicit recall/requeue, with reason and audit.
- `WAITING|CALLED -> ON_HOLD`; `ON_HOLD -> WAITING`.
- `WAITING|CALLED -> NO_SHOW` only after policy-defined grace period or authorized override.
- `WAITING|CALLED|ON_HOLD -> TRANSFERRED` with a destination queue and reason.
- Priority changes preserve the entry and record old/new priority and position.

A queue entry is not completed merely because an announcement was made. A consultation cannot be started by selecting an arbitrary patient from a list; the server must validate the queue transition and doctor/room assignment.

### Encounter
Keep encounter lifecycle separate from queue and appointment lifecycle. Suggested: `DRAFT -> IN_PROGRESS -> DOCUMENTATION_PENDING -> SIGNED -> COMPLETED`. Signing a clinical note and closing an encounter are distinct operations. Do not mark an appointment completed as a fallback when a clinical API call fails.

## 4. Queue invariants and concurrency

1. At most one active consultation per doctor/room unless a facility policy explicitly allows parallel sessions.
2. At most one current active call per queue/doctor context.
3. `call-next` selects the next eligible entry on the server using configured priority then stable queue order.
4. `call-specific` may call an eligible patient out of order. It does not silently move, delete or renumber other patients. Record original position, override reason and actor.
5. `repeat-call` emits another announcement for the current call; it does not alter state, position or wait-time origin.
6. `recall` is a distinct state transition/requeue action and requires a reason.
7. Simultaneous receptionist/doctor actions must serialize using a row lock or optimistic version check. Only one conflicting transition succeeds; stale requests receive HTTP 409 with current state/version.
8. Every command is idempotent using an idempotency key. Duplicate submissions must not create duplicate calls/events.
9. Emergency/STAT priority is governed by a facility policy and authorized role; it must not be a client-only sort.
10. Payment, identity, consent and other mandatory preconditions are checked server-side before queue admission or consultation start, according to configured hospital policy.

## 5. Proposed API

All routes are branch-context aware and require authenticated, authorized access except the narrowly scoped display snapshot route, which uses a registered display credential.

### Read
- `GET /api/opd/queues?date=YYYY-MM-DD&department_id=&doctor_id=&status=`
- `GET /api/opd/queues/{queue_id}`
- `GET /api/opd/queues/{queue_id}/entries?state=&search=&cursor=`
- `GET /api/opd/doctor/queue-today` (compatibility facade for existing doctor UI; response contract to be reconciled)
- `GET /api/opd/displays/{device_id}/snapshot` (display credential; token/room/doctor display fields only)

### Commands
- `POST /api/opd/appointments/{appointment_id}/check-in`
- `POST /api/opd/queues/{queue_id}/call-next`
- `POST /api/opd/queue-entries/{entry_id}/call` — specific-patient override; requires reason.
- `POST /api/opd/queue-entries/{entry_id}/repeat-call`
- `POST /api/opd/queue-entries/{entry_id}/arrive`
- `POST /api/opd/queue-entries/{entry_id}/recall`
- `POST /api/opd/queue-entries/{entry_id}/hold`
- `POST /api/opd/queue-entries/{entry_id}/release-hold`
- `POST /api/opd/queue-entries/{entry_id}/skip`
- `POST /api/opd/queue-entries/{entry_id}/no-show`
- `POST /api/opd/queue-entries/{entry_id}/transfer`
- `POST /api/opd/queue-entries/{entry_id}/priority`
- `POST /api/opd/queue-entries/{entry_id}/start-consultation`

### Command envelope

Commands accept `Idempotency-Key` header and an optional `expected_version` in the body. Specific call example:

```json
{
  "reason_code": "CLINICAL_PRIORITY",
  "reason_note": "Patient requires earlier assessment",
  "expected_version": 12
}
```

Reason codes: `EMERGENCY`, `CLINICAL_PRIORITY`, `DOCTOR_REQUEST`, `SPECIAL_ASSISTANCE`, `SCHEDULED_PROCEDURE`, `ADMIN_CORRECTION`, `OTHER`. Require a note for `OTHER`; avoid storing unnecessary sensitive clinical detail in operational reason notes.

Successful command responses return the updated queue entry, queue version, current call (if applicable), and event identifier. Conflicts return HTTP 409 and the latest safe state.

## 6. Real-time events

Publish committed domain events only after the database transaction succeeds. Suggested event envelope:

```json
{
  "event_id": "uuid",
  "event_type": "opd.queue.patient_called",
  "tenant_id": "server-derived",
  "branch_id": "server-derived",
  "queue_id": "uuid",
  "queue_version": 13,
  "occurred_at": "ISO-8601",
  "payload": {
    "entry_id": "uuid",
    "token_number": "A024",
    "doctor_display_name": "Dr. Display Name",
    "room_display_name": "Room 2",
    "announcement_sequence": 1
  }
}
```

Use an outbox or equivalent reliable publication mechanism. WebSocket/SSE is a delivery channel, not the source of truth. On reconnect, clients fetch a fresh snapshot and resume from the latest version. Clients ignore duplicate/older events.

## 7. TV display privacy and behavior

- Dedicated display mode, not a resized staff dashboard.
- Default public display fields: token, room, doctor/department display name, call state and next-token list.
- Do not expose patient name, MRN/UHID, phone, DOB, diagnosis, orders, or clinical notes.
- Audio announcements default to token + room; patient names are disabled unless a facility explicitly configures a lawful, privacy-reviewed policy.
- Device must be registered, revocable and scoped to a branch/display group. Do not put long-lived credentials in URL path parameters.
- Support multiple display groups, reconnect snapshot, stale/offline indicator, configurable language and announcement mute.

## 8. Permissions

Use existing authorization/role infrastructure; do not introduce a parallel role system.

- Doctor: view assigned queue; call next/specific within assigned queue; repeat; mark arrived/start consultation; optional priority override by policy.
- Reception: check-in and manage assigned queues; call next/specific only if granted; transfer/hold/no-show according to policy.
- Nurse: assigned queue and arrival/assessment actions only when granted.
- OPD manager: permitted branch queues, queue reassignment and priority override.
- Hospital admin: authorized branch scope; not an automatic cross-tenant bypass.
- Display device: read-only, scoped snapshot/events only.

Every command must be authorized server-side and audited with actor, role/permission, tenant, branch, queue, entry, before/after state, reason, timestamp and correlation/idempotency identifiers.

## 9. Clinical workflow

Nurse assessment captures structured vitals with value, unit, measured_at, source and recorded_by. Doctor cockpit loads patient context and encounter context separately.

SOAP:
- Subjective: complaint, onset, duration, relevant history.
- Objective: vitals, examination and reviewed investigation findings.
- Assessment: diagnosis and differential diagnosis.
- Plan: medication, investigation, procedure, referral, counselling and follow-up.

Persist clinical notes against an encounter. Draft autosave must not imply signing. Signed notes are immutable; corrections use an auditable amendment/addendum workflow. Clinical orders are persisted independently of their execution/dispensing lifecycle. Consultation completion does not mean lab, radiology or pharmacy work is complete.

## 10. Analytics definitions

At minimum expose counts and time distributions with explicit definitions:
- waiting count: entries currently in `WAITING` (include held separately).
- average and median wait: check-in to first call; report P50/P90 and exclude/categorize cancelled/no-show entries.
- consultation duration: consultation start to consultation end.
- call-to-arrival: first call to patient-arrived.
- no-show rate: no-show entries / eligible checked-in appointments, with denominator definition.
- appointment utilization: completed + attended appointments / bookable slots (slot definition configurable).
- SLA breach: based on branch/department policy, not hardcoded 30 minutes.
All analytics filter by tenant/branch, date, department, specialty, doctor and visit type, subject to authorization.

## 11. Acceptance criteria

- Reception and doctor see the same server-backed queue state.
- Two concurrent call-next requests cannot call two entries for the same single-active-call queue.
- Specific-patient call changes only the selected entry's call state; other queue positions remain unchanged and an override event is recorded.
- Repeat call does not change queue order or wait-time origin.
- Unauthorized cross-branch access is denied.
- Display credential cannot retrieve patient identity or clinical data.
- Reconnect obtains a current snapshot and does not replay stale calls as new announcements.
- Failed clinical persistence never silently marks an appointment/encounter complete.
- All state transitions have automated positive, negative, concurrency, tenant-isolation and audit tests.

## 12. Implementation gates

Before coding backend routes, inspect and map the existing appointment, encounter, patient, payment, authorization, audit and event models/services/routes. Reuse existing entities and naming where sound. Add migrations only after the mapping is complete. Do not create duplicate appointment/encounter endpoints or models without an ADR.

Before replacing local UI state, identify the actual backend contract and implement typed API clients with loading, empty, error, conflict and reconnect states. No production UI should fall back to fabricated patient data.
