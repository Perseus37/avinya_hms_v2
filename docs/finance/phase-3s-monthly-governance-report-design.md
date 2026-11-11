# Phase 3S — Monthly Reconciliation Governance Report

## Status

Design approved for implementation on the Phase 3S branch. This slice is a manually generated, immutable monthly snapshot. It does not introduce a scheduler, notification channel, export download, or background worker.

## API contract

- `POST /api/procurement/reconciliation/governance-reports` — generate one report for a completed UTC calendar month; requires `finance:approve`.
- `GET /api/procurement/reconciliation/governance-reports` — list report metadata with bounded pagination; requires `finance:read`.
- `GET /api/procurement/reconciliation/governance-reports/{report_id}` — read one frozen report; requires `finance:read`.

The request identifies a month as `YYYY-MM`. The current or a future month is rejected. A month can be generated only once. A repeated request returns HTTP 409; reports are never silently overwritten or regenerated. Corrections require a separately designed superseding-report workflow, not mutation.

## Snapshot contents

Each report freezes:
- reporting month, UTC period boundaries, generation timestamp, schema version and generating actor;
- investigations opened and resolved during the period;
- recorded reopen events during the period;
- closure-quality status for cases resolved during the period, as observed at generation time;
- on-time/late SLA outcomes for cases resolved during the period where an SLA deadline exists;
- recurring exception patterns grouped by candidate type and source type;
- recurring root-cause categories from an allow-listed code set only; free-text and unknown legacy values are excluded;
- active backlog at generation time, including severity, overdue and missing-SLA counts.

The report stores aggregate counts and allow-listed categorical labels only. It must not include investigation titles, summaries, resolutions, notes, patient identifiers, bank references, source IDs, user identities, or notification payloads.

## Integrity and isolation

- The report table is tenant-local through the existing tenant database/schema boundary.
- A unique month key prevents duplicate snapshots within a tenant.
- The canonical JSON payload is stored with a SHA-256 digest and schema version.
- Database-level UPDATE and DELETE guards make snapshots append-only on SQLite and PostgreSQL.
- The generator uses one database transaction; a uniqueness race returns conflict rather than creating multiple snapshots.
- The report is generated on demand after the month closes. No scheduler is enabled.
- Sandbox sanitization classifies report snapshots as purgeable audit/report data and temporarily disables/reinstates append-only guards only during controlled sandbox scrubbing.

## Interpretation

Period activity is based on event timestamps in UTC. Closure-quality status is the state visible when the report is generated, not necessarily the state at the exact instant of closure. The active backlog is a point-in-time snapshot at generation, not a reconstructed historical month-end backlog. SLA results use the stored elapsed-time deadline and do not implement business calendars or pause windows. Recurring labels are investigator-entered classifications, not verified causal findings.

## Deferred

- PDF/CSV export and export accountability register.
- Superseding/corrected report workflow.
- Automated monthly scheduling and report notifications.
- Tenant-local timezone calendars and pause-aware SLA calculations.
- External delivery providers.


## Implemented API and persistence

The monthly snapshot is now implemented with:
- `POST /api/procurement/reconciliation/governance-reports` (`finance:approve`) for manual generation of completed UTC months;
- `GET /api/procurement/reconciliation/governance-reports` and `GET /{report_id}` (`finance:read`) for bounded metadata listing and frozen detail retrieval;
- one report per month enforced by a tenant-local unique constraint, plus a database append-only trigger on PostgreSQL and SQLite;
- canonical JSON serialization and SHA-256 digest verification;
- tenant-local sandbox purge classification that temporarily disables and restores the append-only guard during controlled scrubbing.

The implementation test covers monthly aggregates, recurrence, closure quality, SLA results, backlog-at-generation, payload minimization, digest correctness, duplicate/current-month rejection and database-level immutability.


## Root-cause data minimization

Investigation root causes are categorical codes, not free text. Accepted values are
`DUPLICATE_REFERENCE`, `VENDOR_MISMATCH`, `AMOUNT_MISMATCH`,
`PAYMENT_ALLOCATION_ERROR`, `MISSING_SUPPORTING_DOCUMENT`,
`BANK_STATEMENT_DATA_ERROR`, `PROCESS_CONTROL_GAP`, and `OTHER`.
The API normalizes case, surrounding whitespace, spaces and hyphens before validation.
Recurrence analytics and monthly snapshots include only these approved categories;
unknown legacy values are excluded and are never copied into aggregate report payloads.
