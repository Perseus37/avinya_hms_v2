# OPD Workflow V1 — Existing Backend Integration Map

Branch: `feature/opd-workflow-v1`  
Audit date: 2026-11-03

## Existing components to reuse

| Capability | Existing implementation | Integration decision |
|---|---|---|
| Appointment | `backend/domains/encounters/models.py:Appointment` | Queue entry references appointment; do not duplicate booking |
| Appointment lifecycle | `AppointmentStatusEnum`, `AppointmentStatusHistory` | Keep separate from queue state; update through explicit service transition |
| Encounter | `PatientEncounter` | Queue entry may reference the existing encounter |
| OPD routes | `backend/domains/encounters/opd_router.py` | Keep appointment scheduling/status endpoints; add queue routes alongside |
| Vitals | `backend/domains/clinical/models.py:EncounterVital` | Reuse; existing capture includes BMI calculation |
| SOAP | `ClinicalNote` | Reuse existing SOAP fields and signed-note lock |
| Diagnosis | `EncounterDiagnosis` | Reuse |
| Authorization | `RequirePermission`, `user_has_permission` | Reuse granular permission framework |
| Tenant context | `resolve_tenant_context`, tenant-routed `get_db` | Queue data is stored in the resolved tenant DB; branch code is server-derived |
| Realtime | `publish_tenant_event`, `waiting_room` stream | Reuse delivery infrastructure; add queue-specific events and safe payloads |

## Existing behavior requiring correction before UI integration

1. `PATCH /api/opd/appointments/{id}/status` row-locks the appointment and records status history, which is a useful foundation.
2. The status endpoint publishes `TOKEN_CALLED_IN_CONSULTATION` to the waiting-room stream after committing. The existing event payload includes appointment ID, token, doctor ID/name and department. New public display events should be token/room oriented and must not leak patient identifiers.
3. The appointment status endpoint attaches an encounter and invokes `auto_bill_opd_consultation` when entering consultation. Do not bypass or duplicate this billing behavior; queue check-in/calling must not create a second charge.
4. Appointment status currently has no explicit `CHECKED_IN` state; `ARRIVED` is the current checked-in equivalent. Keep compatibility at the API boundary.
5. `EncounterVital` and `ClinicalNote` are already persisted against `PatientEncounter`. SOAP note updates reject signed notes. Use these APIs rather than creating parallel clinical tables.
6. Existing clinical vitals write/read permissions use `adt:write` / `adt:read`, while SOAP uses `opd:write`. Confirm permission grants and role assignments before exposing nurse workflows; do not assume all nurses currently hold ADT permissions.
7. The current Redis publisher is best-effort pub/sub, not a transactional outbox. A committed queue state remains authoritative; clients must refresh snapshots on reconnect. Reliable outbox delivery is a follow-up hardening requirement if event loss is unacceptable.

## New queue persistence introduced

- `OPDQueue`: one doctor/department service queue per branch and service date.
- `OPDQueueEntry`: references existing appointment, patient and optional encounter; stores queue position, priority, state and timestamps.
- `OPDQueueEvent`: records queue commands and actor/reason metadata.

Files:
- `backend/domains/encounters/opd_queue_models.py`
- `backend/alembic/versions/a1b2c3d4e5f6_create_opd_queue_tables.py`

The encounters package imports the queue model module so the SQLAlchemy metadata is registered when the backend loads. Alembic's environment imports the encounters package before migration metadata is evaluated.

## Important design caveats before enabling writes

- The current tenant architecture routes to a tenant database and stamps trusted `branch_code` into `db.info`; it is not evidence of a separate branch-level database schema. Queue queries must explicitly constrain the trusted branch code.
- Existing appointments do not currently carry a branch code column in the inspected model. They are tenant-database scoped; the queue's branch assignment is derived from tenant context.
- The proposed unique appointment constraint prevents duplicate queue admission for an appointment. Walk-ins should first be represented by the existing appointment record until a separately approved walk-in domain is designed.
- A queue-level row lock must serialize both `call-next` and `call-specific`. Entry row locks alone are insufficient to prevent two callers selecting different patients concurrently.
- Queue position uniqueness makes naive position swaps unsafe. Specific-patient calling must not renumber waiting entries; priority changes require a dedicated, transaction-safe reorder algorithm or stable sequence keys.
- Do not allow multiple active calls in the same queue. The command service must reject a new call while a previous entry remains CALLED/ARRIVED/IN_CONSULTATION, unless an explicit facility policy is implemented.
- Do not assume payment is already settled at appointment check-in. The current billing integration shown in the appointment status endpoint occurs at consultation start; queue eligibility/payment policy needs a dedicated verified check before it is enforced.
- No migration has been run against a live tenant database and no automated tests have been executed in this remote repository session. Treat the migration and ORM metadata as unverified until CI/local Alembic upgrade and tests pass.

## Next vertical slice

1. Validate migration head and run Alembic upgrade against an isolated PostgreSQL test database.
2. Implement a queue service with queue-row locking, version checks, idempotency and event persistence in the same transaction.
3. Add queue list, check-in, call-next, call-specific, repeat-call and arrive commands with existing permission dependencies.
4. Add concurrency, transition, branch-isolation and audit tests.
5. Replace OPD queue sample state with typed API integration only after the backend contract is tested.
