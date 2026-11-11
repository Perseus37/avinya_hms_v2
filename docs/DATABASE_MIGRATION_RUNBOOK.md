# Database Migration Runbook

## Purpose and release invariant

Avinya HMS uses separate PostgreSQL databases for the control plane and hospital tenants. A release that changes the database schema is not ready for application traffic until the control-plane database, the canary tenant, and every active cloud tenant have reached the exact Alembic revision shipped with that release and pass ORM/schema parity checks.

This runbook applies to cloud-managed databases. On-premises tenants follow their separately scheduled upgrade process and must not be silently included in the cloud fleet rollout.

## Non-negotiable controls

- Production applies checked-in Alembic revisions only. Runtime autogeneration is prohibited.
- Every migration is reviewed for data correctness, lock duration, table size, index build strategy, and compatibility with the currently deployed application.
- Back up the target databases before a release and verify that the backup is restorable. A backup job reporting success is not a restore test.
- Run the control-plane and default-tenant canary first. Review application health and representative clinical workflows before fleet rollout.
- Fleet rollout records a result per tenant and continues after an individual failure so the full failure set is visible. Any failure makes the rollout command fail; do not switch application traffic or declare the release complete.
- Re-run only after diagnosing the failed tenant. Migrations must be safe to resume or have a documented recovery procedure.
- Never edit a migration that may already have been applied to any environment. Ship a corrective forward migration instead.

## Migration connection limits

Both online Alembic environments use a database-local transaction-scoped advisory lock to serialize migration runners targeting the same database. Separate tenant databases do not block one another.

PostgreSQL migration sessions also set transaction-local limits:

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `ALEMBIC_LOCK_TIMEOUT` | `5s` | Maximum time a statement waits to acquire a PostgreSQL lock, including the migration advisory lock |
| `ALEMBIC_STATEMENT_TIMEOUT` | `30min` | Maximum execution time for an individual statement |

Set these variables in the migration job/container environment when a reviewed migration needs a different window. For example, an approved large backfill may need a longer statement timeout, but should normally be redesigned as a resumable batch job instead. PostgreSQL validates the duration values; invalid values fail the migration rather than silently disabling the limit. These settings are local to the migration transaction and do not change database-wide defaults.

A timeout is a safety stop, not a reason to repeatedly retry without investigation. Inspect blocking sessions, query plans, table sizes, and migration progress before retrying.

## Review and design requirements

### Expand and contract

1. Add nullable columns, new tables, or compatible indexes first.
2. Deploy application code that can read both old and new representations.
3. Backfill and validate data.
4. Switch reads/writes to the new representation.
5. Remove obsolete columns or constraints only in a later release after all application instances and background workers have stopped using them.

Do not combine a destructive schema change with the application change that first depends on it.

### Indexes on live tables

Ordinary `CREATE INDEX` can block writes while it builds. For large or write-heavy tables, evaluate PostgreSQL `CREATE INDEX CONCURRENTLY` and its operational trade-offs.

Concurrent index creation cannot run inside a normal transaction block. Put it in a dedicated Alembic revision configured for non-transactional execution (for example, an Alembic `autocommit_block`) and test failure/retry behavior, including invalid or incomplete indexes. Transaction-scoped advisory locks do not survive a transaction boundary created by an autocommit block; if such a migration is introduced, explicitly design a session-level lock lifecycle or another serialization mechanism and release it in a guaranteed cleanup path. Do not assume the existing transaction-scoped lock protects work across that boundary.

For smaller tables or maintenance windows, a normal transactional index migration may be appropriate when the lock impact is understood and accepted.

### Data backfills

- Avoid unbounded table-wide updates in schema migration transactions.
- Prefer a resumable, idempotent background/batch operation with a stable key range, bounded batch size, progress checkpoint, retry behavior, and observable completion state.
- Define how concurrent application writes are captured while the backfill runs.
- Validate row counts, null counts, uniqueness, and referential integrity before enforcing new constraints.
- Keep schema expansion and data movement separate when the operation may exceed the migration statement budget.

### Constraints and defaults

Review lock and rewrite behavior for adding non-null columns, server defaults, foreign keys, unique constraints, and check constraints. Where practical, add constraints as `NOT VALID`, validate them separately, and only then rely on them. Confirm the PostgreSQL version and exact operation semantics before choosing this pattern.

## Release sequence

1. **Prepare:** identify the target Alembic head; inspect the migration graph; review every operation and its downgrade limitations; estimate data volume and lock impact.
2. **Backup:** take backups for the control plane and target tenant databases; verify restore procedures in a non-production environment.
3. **Compatibility:** ensure the currently running application can operate with the expanded schema and that the new application is not deployed before its required schema is available.
4. **Canary:** run the approved canary command against the control plane and configured default tenant. Confirm the canary revision equals the checked-in head and schema parity passes.
5. **Observe:** run smoke tests for login, patient registration/search, encounter/appointment workflows, billing, diagnostics, pharmacy, and any domain touched by the migration. Review database health and application errors.
6. **Fleet:** run the fleet migration command. Review the per-tenant audit outcomes and command exit code. A non-zero exit or any failed tenant blocks release completion.
7. **Gate:** before enabling the new application release or switching traffic, verify every active cloud tenant is at the required revision and passes schema parity. The application startup tenant-revision check is a safety net, not a replacement for this deployment gate.
8. **Post-release:** monitor query latency, lock waits, deadlocks, error rates, and tenant-level health. Retain migration logs and audit records with the release commit identifier.

## Failure and recovery

- A lock timeout usually indicates a conflicting transaction or another migration runner. Identify the blocker and retry only after the cause is understood.
- A statement timeout or migration exception may leave a transaction rolled back, but non-transactional operations can leave partial artifacts. Inspect the actual database state before rerunning.
- A fleet rollout can be partially complete. Keep the old application release compatible with the expanded schema, repair the failed tenant, and rerun the fleet command. Do not roll back already-upgraded tenants just to make revisions uniform.
- Do not use `alembic downgrade` as a general production rollback strategy. Downgrades may lose data or be irreversible in practice. Prefer a forward corrective migration. For data corruption or destructive operations, follow the approved point-in-time recovery/restore plan and account for the resulting data-loss window.
- Record the tenant, database, release SHA, Alembic revision, error class, recovery action, and verification result in the incident/change record. Do not put credentials or patient data in migration logs.

## Deployment gate ownership

The production Compose topology currently provides a startup gate: `db-init` runs `backend/scripts/bootstrap.py`, and the API service depends on `db-init` completing successfully. In production, bootstrap deliberately skips automatic upgrades of existing tenant databases and then validates every active cloud tenant against the checked-in Alembic head and ORM metadata; a lagging tenant causes bootstrap to fail and prevents the API service from starting. Keep this dependency intact in every production deployment topology. The staged migration command's per-tenant failure result remains a separate pre-release control. Any alternative orchestrator must preserve both controls: consume the migration exit status and verify the full active cloud tenant fleet before switching traffic.
