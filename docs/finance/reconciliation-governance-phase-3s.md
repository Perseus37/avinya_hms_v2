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
- The register exposes Redis task state and the email handler's send result (mailer accepted or delivery failed) while task metadata remains available. Neither state proves final mailbox delivery. Task metadata expires after the queue's configured retention window; older records are shown as UNKNOWN_OR_EXPIRED.

### 3S.4 — Closure quality and recurring root causes
- Read-only closure-quality endpoint reports resolution duration, median/average, case-level reopen rate, independent review outcomes, and recurring root-cause buckets.
- Reopen rate denominator: distinct cases with a RESOLVED transition during the selected period. Numerator: distinct cases in that cohort with a later REOPENED event. Repeated reopen cycles count once in the rate and separately in reopen_events.
- Reopened events retain their prior root-cause metadata; current root-cause labels are not treated as proof that the underlying issue is permanently fixed.
- Root-cause counts are descriptive; they do not automatically infer or overwrite root-cause codes.

### 3S.5 — Finance Manager governance dashboard
- Read-only governance dashboard aggregates open cases, SLA breaches, unassigned work, resolved cases, distinct cases with one or more reopen cycles, and closure-quality measures.
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
- Revision: k6e9f1b3c210 (parent: j5d8c2a7f410) changes the audit-export-to-investigation FK from ON DELETE SET NULL to ON DELETE RESTRICT, preventing a parent deletion from mutating an append-only export row.

## Operational notes and verification

- The existing Redis queue/worker is reused; no second scheduler is introduced.
- Existing default acknowledgement targets remain CRITICAL 0.5h, HIGH 2h, MEDIUM 8h, LOW 24h until a published escalation policy takes effect.
- Notification task status and mailer send result are exposed while Redis task metadata remains available, otherwise UNKNOWN_OR_EXPIRED. This is not a mailbox delivery receipt.
- Added API regression coverage in tests/test_26_reconciliation_governance.py and tests/test_27_reconciliation_governance_regressions.py / tests/test_28_reconciliation_governance_regressions.py.
- Automated tests, Alembic upgrade/downgrade, TypeScript typecheck, and production build have NOT been executed in this environment. Run them before deploying this migration.


## Phase 3S verification corrections

- The escalation-policy register now applies the same effective-window rule as assignment: effective_from <= now and (effective_to IS NULL or effective_to > now). A published future-dated policy is not presented as active before its start.
- The governance dashboard's reopened_cases value is a distinct-case count, not the sum of cumulative reopen_count values.
- The audit-export register's nullable investigation reference is protected with RESTRICT semantics. Export rows remain immutable and cannot be silently rewritten by deleting an investigation.
- Regression tests cover future-effective policy visibility and a case with multiple reopen events. Execution remains pending CI/local validation.
