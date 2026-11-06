# Reconciliation Governance — Phase 3S.3–3S.7

## Scope delivered

### 3S.3 — Escalation and notification governance
- Versioned, tenant-scoped escalation policies with draft/publish lifecycle.
- Severity-specific acknowledgement response targets.
- One to five ordered escalation levels, each with its own elapsed-hours threshold and recipient switches.
- Notification preferences for email enablement, assignee, assigning manager, and Finance Manager recipients.
- Assignment events capture the published policy's response target and preferences at assignment time; later policy publication does not rewrite queued task payloads.
- Existing Redis worker performs assignment-event-bound, multi-level escalation. Reassignment, terminal status, acknowledgement, and already-notified levels are checked before dispatch. Committed event history deduplicates normal retries; enqueue and event commit are not a distributed transaction, so a process crash in that narrow window can still cause at-least-once duplicate email. A durable transactional outbox is required for stronger exactly-once dispatch guarantees.
- Escalation events retain level, recipient IDs, queued email task IDs, and queue state.
- Queue status is not proof of SMTP acceptance or mailbox delivery. The current email task provider does not expose a durable delivery receipt contract to this workflow; the UI and API label this as queue status only.

### 3S.4 — Closure quality and recurring root causes
- Read-only closure-quality endpoint reports resolution duration, median/average, reopen rate, independent review outcomes, and recurring root-cause buckets.
- Reopened events retain their prior root-cause metadata; current root-cause labels are not treated as proof that the underlying issue is permanently fixed.
- Root-cause counts are descriptive; they do not automatically infer or overwrite root-cause codes.

### 3S.5 — Finance Manager governance dashboard
- Read-only governance dashboard aggregates open cases, SLA breaches, unassigned work, resolved cases, reopened cases, and closure-quality measures.
- Existing finance:read controls visibility; policy/report generation requires finance:sla:manage.

### 3S.6 — Monthly governance reports
- Authorized users can create immutable point-in-time snapshots for complete calendar-month periods. The snapshot basis is current case state for cases first detected during the selected period, not a reconstructed historical state as of the period end.
- Duplicate periods are rejected; historical report snapshots are not recalculated when case data changes.
- Snapshot includes status/severity distribution, breached open cases, resolved count, reopen count, and root-cause distribution.

### 3S.7 — Audit export register
- Successful investigation audit ZIP generation now writes a register record with actor, timestamp, exception, artifact SHA-256, size, and manifest/evidence summary.
- Register is tenant-scoped and append-only at the database layer on PostgreSQL.
- Listing endpoint exposes export accountability metadata; it does not expose file contents or bypass the existing evidence authorization path.

## API surface

- GET/POST /api/procurement/reconciliation/escalation-policies
- POST /api/procurement/reconciliation/escalation-policies/{id}/publish
- GET /api/procurement/reconciliation/governance/closure-quality
- GET /api/procurement/reconciliation/governance/dashboard
- POST/GET /api/procurement/reconciliation/governance/monthly-reports
- GET /api/procurement/reconciliation/audit-exports
- Existing GET /api/procurement/reconciliation/exceptions/{id}/audit-export now records the generated ZIP.

All endpoints execute against the tenant database session and use existing finance permissions. No cross-tenant aggregate is introduced.

## Migration

- Revision: j5d8c2a7f410
- Parent: h4c2e7a9d510
- Adds escalation policy versions, immutable monthly report snapshots, and audit export register.
- PostgreSQL triggers protect published escalation policy content and make report/export records immutable.

## Operational notes and verification

- The existing Redis queue/worker is reused; no second scheduler is introduced.
- Existing default acknowledgement targets remain CRITICAL 0.5h, HIGH 2h, MEDIUM 8h, LOW 24h until a published escalation policy takes effect.
- Notification task status is exposed as QUEUED/COMPLETED/FAILED where Redis task metadata remains available, otherwise UNKNOWN_OR_EXPIRED. This is not a delivery receipt.
- Added API regression coverage in tests/test_26_reconciliation_governance.py.
- Automated tests, Alembic upgrade/downgrade, TypeScript typecheck, and production build have NOT been executed in this environment. Run them before deploying this migration.
