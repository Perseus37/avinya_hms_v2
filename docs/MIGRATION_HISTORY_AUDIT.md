# Tenant Alembic History Audit

**Reviewed branch:** `ui-redesign/v1`  
**Reviewed head:** `0035d3e6c31799d6007bcffd12f5f1948799c96b`  
**Scope:** 39 tenant Alembic revision files identified in the branch tree. This is a source-level operational-risk review, not proof of execution against production-sized PostgreSQL databases.

## Findings requiring release controls

### 1. Appointment status-history backfill is unbounded

Revision `82ca74d1b605_appointment_status_history.py` creates the history table and performs one unbounded:

```sql
INSERT INTO appointment_status_history (...)
SELECT ...
FROM appointments;
```

**Risk:** On a large tenant this can scan and copy the entire appointments table in one migration transaction, extending lock/transaction lifetime, generating WAL, increasing replication lag, and delaying vacuum cleanup. It also records only the current status at migration time; historical transitions before the migration are explicitly unavailable.

**Disposition:** Do not silently rewrite this revision if any tenant may already have applied it. Before a production rollout, measure it on a representative data volume and check WAL/replication/lock impact. For tenants where it exceeds the approved migration window, use a separately designed resumable, idempotent backfill with a stable key cursor and progress ledger, then validate counts before marking the migration complete. Coordinate application writes during the backfill so new appointments/status changes are not missed. Do not mark the revision applied until the backfill is complete and verified.

### 2. Large batches of ordinary index creation

The reviewed history contains these ordinary transactional index batches:

| Revision | Operations | Operational concern |
| --- | ---: | --- |
| `8c14e73a92bf` | 6 indexes | Ordinary index builds on operational/time-series tables |
| `c74e11ab42d9` | 19 indexes | Ordinary index builds across clinical, billing, and operational tables |
| `c1f4e8b2a937` | 14 indexes | Index builds plus batch column alterations |
| `e1a3c7b5d902` | 134 index creation calls | Very large foreign-key index rollout |

**Risk:** Ordinary PostgreSQL `CREATE INDEX` takes a lock that can block writes while the index is built. A sequence of 134 index operations can produce a long deployment window and significant I/O/WAL pressure. The total migration duration is not bounded by the per-statement timeout alone.

Revision `e1a3c7b5d902` uses `IF NOT EXISTS`. PostgreSQL's name-exists behavior does not prove that a pre-existing index with the same name has the intended columns, predicate, uniqueness, or access method. An existing but incorrect index can therefore be silently accepted.

**Disposition:** Before enabling this revision for large tenants:
- Capture per-table row counts and relation sizes for every target index.
- Check whether each named index already exists and compare its definition with the intended definition using `pg_get_indexdef`.
- Check for equivalent indexes under other names to avoid duplicate storage/write overhead.
- Benchmark on a production-sized clone and record expected duration, lock behavior, WAL, and replica lag.
- For large/hot tables, plan dedicated `CREATE INDEX CONCURRENTLY` revisions and validate failure cleanup/retry. Such revisions need a deliberately designed lock lifecycle: transaction-scoped advisory locks do not span Alembic autocommit boundaries.
- Keep ordinary builds only where measured table size and maintenance window make their blocking behavior acceptable.

Do not edit these historical revisions in place if they may have been applied. Use a corrective forward migration or an explicit operational remediation plan.

### 3. Batch alterations and downgrade data-loss risks

Revision `c1f4e8b2a937` widens privacy evidence/reason columns and creates 14 indexes. On PostgreSQL, Alembic batch operations generally resolve to direct ALTER operations when table recreation is not required, but the actual generated SQL and lock behavior must be checked for the configured dialect/version. Its downgrade narrows both columns back to 100 characters; values longer than 100 characters can make downgrade fail or lose data depending on the database/operation.

Revision `a4f2c8d1e639` uses batch alterations to add privacy-policy and consent columns/constraints. Review the generated PostgreSQL SQL and constraint validation cost against actual table size before production rollout.

**Disposition:** Treat downgrades that narrow columns or remove data-bearing columns as non-automatic. Verify data compatibility before any downgrade; prefer a forward fix for production recovery.

### 4. Federation transfer-log immutability migration

Revision `f9b7c3d1e205` replaces the patient foreign key with `ON DELETE RESTRICT` and creates a trigger rejecting UPDATE/DELETE on `federation_transfer_logs`.

**Risk:** Dropping/recreating the foreign key requires a strong table lock and can wait behind long-running transactions. The immutability trigger also means ordinary ORM cleanup, retention jobs, and patient deletion paths must not attempt to mutate/delete those audit rows. The downgrade restores `ON DELETE CASCADE`, which would reintroduce the possibility of audit history being removed with a patient.

**Disposition:** Before rollout, inspect table size, blockers, and existing FK state. Confirm application and retention code treats these logs as append-only. Do not use the downgrade as an incident rollback without an explicit audit-retention decision.

### 5. Baseline migration

The root revision `6f591125aedc_baseline.py` creates the initial tenant schema and 82 indexes. This is expected to run against a newly provisioned empty tenant database, not to be replayed against a live database with manually created application tables. Existing databases must be managed through their recorded Alembic revision and the canary/fleet validation process.

## Migration graph and runtime verification still required

The branch tree contains 39 revision files and the inspected chain includes:

`6f591125aedc` → `3605df409a44` → `8c14e73a92bf` → `c74e11ab42d9` → … → `c1f4e8b2a937` → `d8a2f1c4e705` → `e1a3c7b5d902` → `f9b7c3d1e205` → `a7c4e9d2b615`.

This abbreviated chain is not a substitute for running `alembic history`, `alembic heads`, and `alembic branches` in the actual backend environment. CI should assert exactly one intended tenant head and one intended control-plane head, and verify every revision has a resolvable parent. A PostgreSQL 17 migration-parity run should apply the full chain from empty state and compare the final schema to ORM metadata.

## Release decision

**Do not treat the migration history as production-scale validated yet.** The unbounded appointment backfill and the 134-index revision need measured data-volume/lock evidence or an approved remediation plan before a large, live tenant fleet is upgraded. The 5-second lock timeout and 30-minute per-statement timeout are guardrails, not evidence that these operations are online-safe.

The deployment gate remains: control-plane and canary first; then every active cloud tenant; no application traffic switch or release completion if any tenant fails or remains behind. Preserve the currently deployed application's compatibility with the expanded schema during partial rollout.
