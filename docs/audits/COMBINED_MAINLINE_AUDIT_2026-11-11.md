# Combined Mainline Audit — 2026-11-11

**Audit base:** `main` at merge commit `c1f8a8a175a9f7dd6538bfdc1630ad6e996baaf5`  
**Included changes:** PR #1 (UI redesign/federation privacy hardening) and PR #16 (Phase 3S reconciliation, supplier payments, audit export, patient-indent provenance), including the Alembic graph merge revision `f3b8a1d6c902`.

## Executive result

The combined tree passed the PR #16 full release-gates workflow on exact head `4240e73729b292850d957c5f60d90b6d57042e5f` (workflow [#42967323813](https://github.com/Perseus37/avinya_hms_v2/actions/runs/42967323813)): Python tests and PostgreSQL 17 migration parity, both UI builds, Compose validation, production image builds/scans, and SBOM/image artifact handoff all passed. Release publishing was skipped for the PR workflow as configured.

This is a source-level security and lifecycle audit, not a production penetration test, live tenant migration rehearsal, or independent clinical safety certification. The findings below require code-level remediation and regression tests before treating the affected paths as production-ready.

## Findings

### AUD-001 — Retention hard-delete dependency scan omits immutable federation transfer logs

**Severity: High — destructive retention correctness / audit integrity**

**Evidence:** `backend/domains/privacy/retention_service.py`, patient `action == "delete"` handler. The hard-delete guard checks encounters, invoices, allergies, diagnostic orders, insurance policies, and consent records, but does not check `FederationTransferLog.patient_id`. The federation migration `f9b7c3d1e205` changes that FK to `ON DELETE RESTRICT`, and the federation security contract states transfer logs are immutable and must survive patient lifecycle operations.

**Impact:** A patient that has no currently checked dependent rows but has a federation transfer log is treated as deletable. The eventual DELETE is rejected by the database FK, causing retention execution to fail rather than completing the requested category. More generally, the dependency scan currently catches broad exceptions for each dependent-table query and continues; a failed dependency query must never be interpreted as “no references”.

**Required remediation:**
- Include `FederationTransferLog.patient_id` in the dependency scan.
- Remove the broad exception-and-continue behavior for required dependency queries; fail the category closed and record an execution error if any check cannot be completed.
- Add regression coverage for a deactivated patient with an immutable federation transfer log and for a dependency-query failure.
- Verify the run ledger records partial/error outcomes accurately and does not report a successful delete.

### AUD-002 — Patient discovery-pointer synchronization can report success after a database failure

**Severity: Medium — incorrect API outcome / operational integrity**

**Evidence:** `backend/domains/federation/router.py`, `sync_patient_pointer()` catches every exception, rolls back the control-plane transaction, and returns no explicit failure value. The `publish_local_patient_to_discovery_index()` endpoint rejects only the explicit value `False`; a `None` result falls through to a success response.

**Impact:** A failed pointer write can be reported to the caller as “successfully synced”, even though no pointer update was committed. This can leave a patient undiscoverable while the UI/operator believes publication succeeded.

**Required remediation:**
- Propagate unexpected persistence errors (or return a typed result that distinguishes policy denial, no-op, and persistence failure).
- Keep privacy-policy denial distinct from infrastructure failure.
- Add tests proving a control-plane commit failure cannot return HTTP 200 and that an allowed no-op remains explicitly represented.

### AUD-003 — Federated discovery suppresses per-source failures and returns an unmarked partial result

**Severity: High — clinical data completeness / operational transparency**

**Evidence:** `backend/domains/federation/router.py`, source-fetch worker fan-out. The endpoint waits up to five seconds, cancels unfinished futures, and silently ignores both unfinished sources and exceptions from completed futures. It then returns any demographics/allergies collected from the remaining sources without a partial-result indicator or failed-source summary.

**Impact:** A successful HTTP response can omit a permitted source branch because it timed out or failed. In a clinical continuity workflow, consumers cannot distinguish “no additional shareable data exists” from “some sources could not be queried”. Missing allergy data is particularly consequential.

**Required remediation:**
- Make completeness explicit in the response (e.g. complete/partial plus bounded source outcome counts or safe source identifiers).
- Do not expose internal exception details or PHI in failure metadata.
- Define whether incomplete discovery should fail closed for the requested use case or return a clearly marked partial response.
- Add timeout, worker exception, and mixed-success regression tests; ensure all database sessions are closed even when a future times out.

### AUD-004 — Human clinician attribution remains unsupported for remote federation

**Severity: High — compliance / audit attribution gate**

**Evidence:** `docs/FEDERATION_SECURITY.md` explicitly states that a federation API key authenticates a hospital node/service, not the individual clinician. The transfer log records node ID/key prefix and branch, but no cryptographically verified clinician assertion. Remote emergency federation remains disabled pending a source-issued grant and signed actor assertion.

**Impact:** Node-level audit attribution must not be represented as human-level attribution. Any future remote emergency disclosure or clinician-attributed access claim would be unsupported by the current protocol.

**Required remediation:**
- Keep remote emergency federation disabled.
- Before enabling it, design and independently review a signed actor assertion bound to the authenticated node, clinician identity, patient, purpose, scope, expiry, and replay protection.
- Verify the assertion at the source and persist the verified actor identity and assertion provenance in the source audit record.
- Add negative tests for missing, invalid, expired, replayed, wrong-node, wrong-patient, and wrong-purpose assertions.

## Verified controls retained

- PR #1's source allergy-sharing policy is checked during patient import; the regression test `test_federated_import_respects_source_allergy_sharing_setting` is present.
- Federation transfer logs are documented and implemented as append-only, with node/key snapshot attribution and no cross-database FK.
- Remote emergency federation remains fail-closed and disabled.
- Reconciliation investigation events use stable descending-ID pagination; state transitions use row locking and optimistic version checks.
- Reconciliation notification inbox queries are recipient-scoped and require `finance:read`.
- Supplier payment and reconciliation paths have append-only ledgers and maker-checker controls represented in the merged implementation and covered by the successful full workflow.
- The new Alembic merge revision `f3b8a1d6c902` is graph-only (no DDL) and joins the two previously independent migration heads. PostgreSQL 17 migration parity passed on the exact PR head.

## Follow-up verification required before production

1. Implement AUD-001 through AUD-003 with regression tests in a remediation PR; retain AUD-004 as a release gate until the signed actor protocol exists.
2. Run retention tests against PostgreSQL with immutable federation transfer rows and simulate a dependency-query failure.
3. Exercise federation discovery with source timeout, database outage, source policy denial, and mixed-source success; assert completeness semantics.
4. Run the migration chain against a representative production-sized tenant clone. The existing migration-history audit identifies an unbounded appointment-status backfill and a large batch of ordinary index builds that still require measured lock/WAL/duration evidence.
5. Run tenant/branch isolation and privacy-policy regression suites after the remediation changes.
6. Do not enable remote emergency federation, external notification delivery, or destructive production retention execution merely because the current CI workflow passes.
