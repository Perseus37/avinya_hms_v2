# Reconciliation Investigation Lifecycle Foundation

## Purpose

The source-candidate endpoint identifies records requiring human reconciliation review. This slice adds a durable case lifecycle without automatically deciding accounting outcomes or treating indicators as fraud.

## Data model

- `procurement_reconciliation_investigations` stores one case per stable candidate/source identity.
- Source identity is polymorphic (`source_type`, `source_id`) and deliberately does not create a foreign key into bank/payment tables. This avoids coupling the investigation retention lifecycle to operational source deletion.
- `external_key` is unique and prevents duplicate cases for the same candidate type and source record.
- Severity, status, assignment, resolution, root-cause label, and optimistic version are stored on the case.
- `procurement_reconciliation_investigation_events` records opening, assignment and status transitions. Database triggers prevent event updates/deletes on PostgreSQL and SQLite.

No patient data, raw account numbers, bank statement descriptions, or full source snapshots are copied into an investigation. The caller supplies a short title, summary, and optional source reference.

## API

- `POST /api/procurement/reconciliation/investigations` — open a case from an existing bank statement line, supplier payment, or supplier payment request (`finance:write`).
- `GET /api/procurement/reconciliation/investigations` — paginated case list with status, severity, and assignee filters (`finance:read`).
- `PATCH /api/procurement/reconciliation/investigations/{id}/assign` — assign/reassign an open case with optimistic version check (`finance:write`).
- `PATCH /api/procurement/reconciliation/investigations/{id}/transition` — move case to review, resolved, or dismissed with optimistic version check (`finance:approve`).
- `GET /api/procurement/reconciliation/investigations/{id}/events` — append-only case history (`finance:read`).

Allowed transitions:

- OPEN → ASSIGNED (assignment) or IN_REVIEW or DISMISSED
- ASSIGNED → IN_REVIEW or DISMISSED
- IN_REVIEW → RESOLVED or DISMISSED
- RESOLVED and DISMISSED are terminal in this first slice.

A resolution note is mandatory for RESOLVED; a reason is mandatory for DISMISSED. A case's version increments on every mutation; stale writes return HTTP 409. Assignment and transition changes append an actor/time event in the same transaction.

## Limitations and follow-up gates

- Candidate discovery remains read-only. Case creation is an explicit human action; this slice does not auto-create cases or infer severity/root cause.
- No reopen workflow yet; reopening needs explicit reason, authority, and a new lifecycle event.
- No SLA clock, escalation/notifications, manager dashboard, monthly snapshot report, closure-quality analytics, or audit-export register in this slice.
- Source references are not hard foreign keys; source availability must be checked by the application when opening a case.
- Event rows are append-only, but this is not a complete cryptographic/tamper-evident audit chain.
- Tenant isolation depends on the existing tenant-schema database routing and must be validated in integration tests.
- No legal retention periods or statutory erasure claims are made.

## Migration

`b8d3f6a1c920` follows the clean mainline source foundation `a7c4e9d2f610`. It does not import the diverged feature branch's migration ancestry.
