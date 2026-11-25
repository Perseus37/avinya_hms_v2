# Avinya HMS — Enterprise Readiness Audit

**Audit status:** Initial repository-wide evidence review; remediation backlog opened  
**Baseline:** `main` at `41614d24f31f3b7ece9623c910ee0155b3312ee8`  
**Audit date:** 2026-11-24  
**Scope:** Source code, migrations, automated tests, CI workflows, deployment manifests, and project documentation  
**Data boundary:** No production credentials, production database, patient data, or live hospital environment accessed.

> **Conclusion: NOT READY for production hospital workloads or real patient data.** The repository has substantial implementation breadth and useful automated controls, but critical runtime identity/isolation, privacy enforcement, audit integrity, and clinical/financial workflow gates remain unproven or incomplete. Passing CI is not a production-readiness certification.

This report is an evidence-based engineering assessment, not a legal opinion, penetration-test report, clinical validation, regulatory certification, or independent deployment audit. Findings marked “unverified” require evidence from an approved staging or production-like environment.

## 1. Executive assessment

| Readiness area | Current assessment | Main reason |
|---|---|---|
| Product/domain breadth | Strong implementation breadth | Many clinical, operational, finance, integration, and administration domains exist |
| Tenant isolation | **Critical gap** | Tenant DB routing changes database name but retains one global DB username/password |
| Authentication and authorization | Partial | Tenant sessions, MFA and permission dependencies exist; control-plane rate-limit failure mode needs correction |
| Privacy and data governance | **Critical gap** | Consent policy is not a universal authorization gate; production enforcement and data lifecycle remain incomplete |
| Audit integrity | **Critical gap** | ORM guards do not prove raw-SQL append-only behavior for every ledger |
| Clinical and financial workflows | Partial | Many state machines and billing controls exist; required consultation/lab payment gates are absent |
| PostgreSQL/migrations | Good foundation, incomplete operational proof | PostgreSQL 17 CI coverage exists, while most workflow tests use SQLite |
| Backup and disaster recovery | Partial | Backup/restore code and tests exist; host/off-host/attachment recovery exercise remains unverified |
| Deployment and availability | Not enterprise-HA proven | Production Compose is a single-host starting point; capacity and failover evidence is absent |
| Frontend quality | Buildable, weak workflow-test evidence | UI builds and narrow unit tests exist; no browser-driven clinical workflow suite found |
| External interoperability | Implementation foundation only | Synthetic tests exist; live partner sandbox/conformance evidence is absent |
| Compliance claims | **Documentation risk** | Some documents state “100% certified” / “certified production-ready” without evidence of certification |

## 2. Evidence baseline and review limits

### Verified repository/CI facts

- The reviewed `main` commit is `41614d24f31f3b7ece9623c910ee0155b3312ee8`.
- Mainline workflow run [#45147254991](https://github.com/Perseus37/avinya_hms_v2/actions/runs/45147254991) completed successfully for that commit.
- Monitoring PR #106 head `69280129fe26ad8a9cb8f039bdf25bfbac168c55` has a successful full release-gate run [#45243900552](https://github.com/Perseus37/avinya_hms_v2/actions/runs/45243900552). The publish/attest job was skipped for the pull-request event, as expected. PR #106 remains draft and unmerged.
- AUD-004 PR #71 remains open and draft. Its unresolved database-identity, source-boundary, and raw-SQL evidence requirements remain release blockers. This audit does not close or modify that work.
- The repository contains 26+ domain packages, separate tenant and control-plane migration histories, a hospital UI, an onboarding UI, and a broad pytest suite.
- The core pytest fixtures create SQLite databases. The opt-in PostgreSQL 17 integration file currently contains three focused tests.
- The two UI packages have narrow test files for role mapping and onboarding constants. No Playwright/Cypress/browser E2E suite was found in the repository tree.
- The restore-drill test in `tests/test_45_offhost_backups_and_restore_drills.py` mocks database engine, subprocess, and inspection calls. It is not an actual host-level recovery exercise.

### Not inspected or proven

No live infrastructure, cloud account, secret manager, network ACL, external ABDM/NHCX sandbox, hospital analyzer, real mail/webhook destination, production restore, penetration test, or independent clinical/legal sign-off was inspected. No statement in this report should be read as evidence that these exercises have occurred.

## 3. Prioritized findings

Severity:
- **P0 / Critical:** Blocks real patient-data production use or a safe hospital pilot.
- **P1 / High:** Must be closed before production rollout or before enabling the affected capability.
- **P2 / Medium:** Required for accurate product contracts, supportability, or planned scale.

### ER-001 — Runtime database identity is shared across tenants and services

**Severity: P0 / Critical**  
**Evidence:**
- `backend/core/config.py`: `DATABASE_URL` is constructed from global `POSTGRES_USER` and `POSTGRES_PASSWORD`.
- `backend/core/database.py`: `build_db_url(db_name)` changes only the database component of that same URL; `get_db()` selects the tenant DB name from the control-plane registry and reuses the shared credentials.
- `backend/scripts/bootstrap.py`: provisioning and migration paths use the same global PostgreSQL identity.
- `docker-compose.prod.yml`: API, worker, HL7 listener, onboarding portal, db-init, and DB services receive the broad `.env.production` environment file.
- `deployments/postgres-roles.sql` defines `hms_app`, but the inspected runtime connection path does not select that role. The grants shown in that file are not a complete per-tenant identity/CONNECT policy.

**Impact:** Database-per-tenant currently describes the storage layout, but the runtime credential boundary is not tenant-specific. A compromised runtime component can potentially authenticate to databases beyond the tenant it is serving. Control-plane and tenant services also receive a broad shared credential set. This is the central AUD-004 identity issue.

**Required closure evidence:**
1. Separate control-plane, tenant API, worker, HL7, migration, backup, restore, and monitoring identities.
2. Tenant runtime credentials are source-bound and can connect only to the intended tenant database; no fleet-wide tenant credential bundle is available to normal runtime services.
3. Database ownership, CONNECT, schema, table, sequence, and default-privilege inventories are reviewed from PostgreSQL catalogs.
4. Negative tests prove Tenant A runtime identity cannot connect to Tenant B or control-plane DB; control-plane identity cannot query tenant clinical data; normal runtime identities cannot perform DDL or privileged role changes.
5. Secret bootstrap, rotation, revocation, connection invalidation, and recovery are exercised.
6. Independent review approves the effective privilege oracle and evidence set.

**Disposition:** Keep AUD-004 blocked. Do not replace this with application-only tenant filters.

### ER-002 — Consent/privacy policy is not end-to-end production enforcement

**Severity: P0 / Critical**  
**Evidence:**
- `backend/domains/privacy/runtime.py`: when no active consent policy revision exists, evaluation uses mode `OFF`.
- `backend/domains/privacy/data_use_points.py` defines registered data-use points, and CI checks route coverage for GET paths.
- `docs/PRODUCTION_READINESS_ROADMAP.md` explicitly states that the consent ledger is not a universal authorization gate, POST/PUT/PATCH response coverage and non-GET exports need review, ENFORCE is not activatable, and no deletion/anonymisation path exists.
- The same roadmap states legal holds are not consumed by a purge workflow and no tenant inventory adapters are configured.

**Impact:** Consent capture and policy evaluation scaffolding must not be represented as complete DPDP enforcement. A consent record does not automatically govern every clinical, administrative, export, background, integration, or federation use.

**Required closure evidence:**
1. Inventory every patient-data read, write, response, print, export, background job, integration, analytics, and federation disclosure.
2. Define and implement the production authorization policy for each purpose/action/scope, including default-deny behavior where required.
3. Add negative tests for absent, expired, withdrawn, mismatched-scope, invalid, and revoked consent across all relevant routes and non-HTTP paths.
4. Implement approved data-principal access/correction/grievance/erasure workflows with retention, legal-hold, backup, export, and integration semantics.
5. Obtain jurisdiction-specific legal/privacy review and record accountable hospital data-protection ownership.

### ER-003 — OPD consultation prepayment and lab payment gates are absent

**Severity: P1 / High**  
**Evidence:**
- `backend/domains/encounters/opd_router.py`, `book_appointment()`: assigns a daily queue token and creates a SCHEDULED appointment without checking payment state.
- The OPD transition to `IN_CONSULTATION` calls `auto_bill_opd_consultation()`; it does not require a paid consultation.
- `backend/domains/diagnostics/router.py`, `place_diagnostic_order()`: creates an ACTIVE diagnostic order and PENDING tasks, then adds charges to a draft invoice without checking payment.
- `tests/test_04_wards_opd_and_adt.py` and `tests/test_05_diagnostics_and_lis.py` exercise appointment/token and lab-order creation without a payment prerequisite.

**Impact:** The current behavior conflicts with the product requirement that consultation payment precede OPD token issuance and lab payment precede lab order execution.

**Required closure evidence:**
1. Define the exact paid/partial/advance/insurance/split-payment rules for each workflow.
2. Enforce payment authorization atomically before token issuance and before lab task activation/collection.
3. Prevent race conditions, duplicate payment callbacks, and stale invoice-state reads from bypassing the gate.
4. Define documented emergency/exception policy with actor, reason, expiry, and audit trail if exceptions are permitted.
5. Add negative tests for unpaid, partial, reversed, refunded, cancelled, concurrent, and duplicate payment scenarios.

### ER-004 — Control-plane authentication rate limits fail open on Redis errors

**Severity: P1 / High**  
**Evidence:**
- `backend/core/dependencies.py`, `RateLimiter._check()`: sensitive behavior is selected using `self.scope.startswith(("auth_login", "auth_mfa"))`.
- `backend/control_plane/services/auth.py` uses scopes `control_plane_auth_login` and `control_plane_auth_mfa`, which do not match those prefixes.
- `tests/test_33_control_plane_operator_auth.py` covers named operator MFA login/logout, but does not test Redis outage behavior for these scopes.

**Impact:** Redis failure can bypass the intended fail-closed rate-limit behavior on control-plane login/MFA routes. Database account lockout is a separate safeguard, not a substitute for correct rate-limit outage handling.

**Required closure evidence:**
1. Replace fragile name-prefix classification with an explicit fail-closed policy/flag for sensitive authentication limiters.
2. Add tests for missing Redis, Redis connection errors, pipeline errors, malformed counters, and TTL recovery for tenant and control-plane login/MFA paths.
3. Prove 503/fail-closed behavior and that no authentication attempt proceeds without the required limiter.

### ER-005 — Audit immutability is not proven against raw SQL across all ledgers

**Severity: P0 / Critical**  
**Evidence:**
- `backend/control_plane/models.py` protects `ControlPlaneAuditLog` with SQLAlchemy before-update/delete listeners.
- `backend/domains/audit/models.py` includes database triggers for the security export register.
- ORM listeners do not prevent a sufficiently privileged database session from issuing direct SQL.
- AUD-004 review artifacts identify the control-plane audit table as lacking database triggers/functions and require a complete append-only inventory plus raw-SQL negative tests.

**Impact:** “Immutable” or “tamper-proof” cannot be claimed for every audit stream based only on ORM hooks. Privileged SQL access, migration/owner roles, and raw-SQL paths must be considered.

**Required closure evidence:**
1. Approved inventory of every append-only or tamper-evident table, its owner, grants, triggers, functions, and privileged exceptions.
2. Disposable PostgreSQL raw-SQL UPDATE/DELETE/TRUNCATE/ALTER/owner-change negative tests across all inventoried ledgers.
3. Independent effective-privilege review and controlled break-glass/retention exception model.
4. Verified external export/retention, integrity verification, and recovery procedures.

**Disposition:** Remains coupled to AUD-004; do not mark cleared based on ORM tests.

### ER-006 — Production backup, restore, and attachment recovery are not demonstrated

**Severity: P1 / High**  
**Evidence:**
- `deployments/backup-postgres.sh` and `deployments/restore-postgres.sh` implement host-level backup/restore flows.
- `tests/test_45_offhost_backups_and_restore_drills.py` mocks database/process inspection in its restore-drill test.
- `docs/PRODUCTION_READINESS_ROADMAP.md` states that host backup/restore on attached storage, off-host copy, attachments, and production restore remain unverified.

**Impact:** Backup code and synthetic tests do not establish recoverability, RPO/RTO, off-host retention, or complete patient-document restoration.

**Required closure evidence:**
1. Run a scheduled backup against a disposable production-like PostgreSQL 17 deployment with attached backup storage.
2. Verify encryption, checksums, off-host copy, access separation, retention, and restore into a new isolated database.
3. Restore attachments and prove database-to-file references resolve correctly.
4. Verify schema revisions, representative records, application login, and clinical/financial workflows after restore.
5. Record measured RPO/RTO, operator steps, failure alerts, and independent sign-off.

### ER-007 — Clinical UI end-to-end workflow evidence is insufficient

**Severity: P1 / High**  
**Evidence:**
- `hospital-ui/package.json` and `onboarding-ui/package.json` expose build/test scripts.
- The UI test tree contains only `hospital-ui/tests/roleMapping.test.js` and `onboarding-ui/tests/constants.test.js`.
- CI builds both UIs and runs those narrow tests; no browser E2E framework or clinical user-journey suite was found.
- `tests/test_67_branch_isolation.py` currently contains three focused cases: tenant-token branch-claim mismatch (401), procurement invoice/document list-detail-download isolation (empty/404), and insurance-provider catalog isolation (not listed/404). It does not exercise cross-tenant patient, encounter, medication, diagnostic, pharmacy, or billing records.
- The authentication implementation has positive controls: `get_current_user()` checks tenant slug and branch claims plus the server-side `AuthSession` owner, revocation, and expiry; production header-based tenant override defaults to disabled; `tests/test_33_control_plane_operator_auth.py` verifies a named operator's logout revokes the session. These focused checks do not substitute for clinical workflow-level cross-tenant denial tests.

**Impact:** TypeScript/Vite builds do not prove that registration, OPD, ADT, clinical notes, nursing/eMAR, pharmacy, LIS, billing, and discharge workflows work end to end for each role.

**Required closure evidence:**
1. Add browser-driven synthetic-data workflows for each frontline workspace and key role.
2. Test permission denial, session expiry/revocation, tenant switching, patient-context switching, and safe failure states.
3. Add accessibility, keyboard, responsive, print/PDF, and browser compatibility checks for critical screens.
4. Run a supervised hospital-user acceptance test with documented outcomes.

### ER-008 — External interoperability is not partner-conformance evidence

**Severity: P1 / High**  
**Evidence:**
- `tests/test_51_abdm_and_nhcx_gateways.py` tests local API behavior with synthetic payloads.
- `tests/test_52_hl7_mllp_analyzer_interface.py` tests parser/task workflows locally.
- `docs/PRODUCTION_READINESS_ROADMAP.md` states official ABDM/NHCX sandbox credentials and physical analyzer network configuration remain deployment tasks.

**Impact:** Internal serialization, callback handling, or parser tests do not establish certification, partner connectivity, consent-manager interoperability, production cryptographic trust, or device compatibility.

**Required closure evidence:**
1. Approved official sandbox credentials and partner test plans.
2. Protocol/profile conformance tests, negative signature/consent/replay cases, retry/idempotency, timeout, and outage handling.
3. End-to-end tests with a real test partner/analyzer on an approved isolated network.
4. Operational ownership, key rotation, incident handling, and monitoring for each enabled integration.

### ER-009 — Compliance and production-readiness documentation overstates assurance

**Severity: P1 / High**  
**Evidence:**
- `docs/complete_guide/06_SECURITY_PRIVACY_AND_COMPLIANCE.md` states “100% Certified” for DPDP, ABDM, NHCX, and NABH/JCI.
- `docs/SYSTEM_INVENTORY_AND_BOUNDARIES.md` labels multiple domains “CERTIFIED PRODUCTION-READY”.
- `docs/SYSTEM_ARCHITECTURE_AND_DESIGN.md` and `docs/SYSTEM_INVENTORY_AND_BOUNDARIES.md` contain stale repository identity, commit, and test-count references.
- The current readiness roadmap records privacy enforcement, live integration, production restore, and legal/privacy sign-off as outstanding.

**Impact:** These claims could mislead hospitals, partners, procurement, auditors, and internal release decisions. Software implementation and automated tests do not confer legal compliance or hospital accreditation.

**Required closure evidence:**
1. Replace unsupported “certified” and “production-ready” claims with precise implemented/tested/deployment-pending/externally-certified labels.
2. Add a dated evidence source and accountable owner to every assurance claim.
3. Reconcile documentation with current mainline code and remove stale repo/commit/test baselines.
4. Obtain formal external certification or accreditation evidence before using those terms.

### ER-010 — Availability and representative capacity are not proven

**Severity: P1 / High**  
**Evidence:**
- `docker-compose.prod.yml` is a single-host deployment topology.
- `docs/PRODUCTION_READINESS_ROADMAP.md` says the included k6 read baseline has not been run and is single-tenant/read-only rather than representative clinical/billing/reporting load.
- No live failover or host-loss exercise was found in the reviewed evidence.

**Impact:** There is no demonstrated high availability, multi-host recovery, capacity envelope, or agreed SLO/RPO/RTO.

**Required closure evidence:**
1. Define service SLOs, RPO/RTO, maintenance windows, and downtime procedures with hospital owners.
2. Run approved synthetic multi-tenant load covering clinical reads/writes, billing, reports, queues, integrations, and background work.
3. Exercise host loss, DB unavailability, Redis outage, certificate expiry, disk exhaustion, and backup failure.
4. Document the supported deployment topology and accepted single-host risk before the first live hospital.

### ER-011 — Financial state vocabulary needs reconciliation with product requirements

**Severity: P2 / Medium**  
**Evidence:** `backend/domains/billing/models.py` defines invoice states `DRAFT`, `UNPAID`, `PARTIAL`, `PAID`, and `VOID`. Refunds are represented separately through `RefundVoucher`; the invoice enum does not contain explicit `REFUNDED` or `CANCELLED` states.

**Impact:** Reporting, reconciliation, integrations, and operator workflows need an unambiguous distinction between void, cancellation, payment reversal, credit note, and refund.

**Required closure evidence:** Approve a financial state-transition matrix, map it to ledger entries and GST/credit-note rules, and test full/partial refund, reversal, cancellation, insurance settlement, and reconciliation outcomes.

### ER-012 — FHIR documentation is inconsistent with the current API surface

**Severity: P2 / Medium**  
**Evidence:** `backend/domains/fhir/router.py` implements read/search routes for Patient, Encounter, Observation, and Condition. `docs/OPERATIONS_RUNBOOK.md` describes a Patient-only read/search scope.

**Impact:** API consumers and operators may rely on incorrect resource support information.

**Required closure evidence:** Reconcile CapabilityStatement, implementation, API guide, supported search parameters, authorization, consent behavior, and conformance tests.

## 4. Positive controls worth preserving

The audit found meaningful engineering work that should be retained and expanded:

- Database-per-tenant routing exists, with tenant registry lookup and tenant/branch claims in the access token.
- Tenant access sessions are server-tracked and revocable; tenant MFA and control-plane MFA flows exist.
- Permission dependencies are used throughout domain routers.
- The code has clinical state machines, concurrency guards, independent diagnostic result verification, BCMA/controlled-substance workflows, and discharge controls.
- Billing uses integer paise, invoice/payment constraints, idempotency, overpayment guards, and payment reversal handling.
- Migration histories are separated for tenant and control-plane databases; PostgreSQL 17 migration tests run in CI.
- Dependency and container scanning, SBOM generation, Compose validation, and UI builds are part of the release-gate workflow.
- Monitoring PR #106 adds important scrape-secret, exporter credential, alert-rendering, and isolated webhook-delivery validation. It remains a draft and does not prove live production monitoring.

## 5. Remediation order

### Gate A — Before any real patient data or hospital pilot

1. ER-001: tenant/control-plane database identity and effective privilege isolation.
2. ER-002: production privacy policy enforcement and complete patient-data-use inventory.
3. ER-005: append-only audit integrity against raw SQL and privileged database paths.
4. ER-003: required OPD and lab payment gates, including approved exception handling.
5. Complete independent security review of AUD-004 before any federation trust or cross-branch disclosure is enabled.

### Gate B — Before production rollout

6. ER-004: control-plane authentication rate-limit fail-closed behavior.
7. ER-006: actual off-host database and attachment restore exercise with measured RPO/RTO.
8. ER-007: browser-driven end-to-end clinical workflows and hospital-user acceptance.
9. ER-008: external sandbox/partner conformance for each enabled integration.
10. ER-009: remove unsupported certification and production-readiness claims.
11. ER-010: capacity, failure, and downtime exercises with approved service objectives.

### Gate C — Before broad enterprise scale

12. ER-011: financial state/reconciliation vocabulary.
13. ER-012: FHIR documentation and conformance alignment.
14. Multi-tenant capacity, operational access review, periodic penetration testing, incident exercises, and recurring independent assurance.

## 6. Release decision

**Current decision: NO-GO for production PHI, live hospital onboarding, or federation activation.**

Synthetic-data development, local demonstrations, and controlled engineering validation may continue. This audit does not authorize production deployment, pilot use, partner onboarding, trust provisioning, or patient-data migration.

AUD-004 PR #71 remains blocked. Monitoring PR #106 remains draft/unmerged pending independent review. No code, production environment, secrets, database, or deployment state was changed as part of this audit report.

## 7. Supplemental findings — clinical and operational pass

### ER-013 — Direct eMAR endpoint can record administration without BCMA verification

**Severity: P0 / Critical if barcode verification is the approved bedside standard; otherwise P1 / High until an explicit clinical exception policy exists.**

**Evidence:**
- `backend/domains/clinical/nursing_er_router.py`, `record_emar_administration()`: accepts `status=ADMINISTERED`, rechecks allergy only, and inserts a `MedicationAdministrationLog` directly.
- `backend/domains/clinical/schemas.py`, `eMARCreate`: defaults status to `ADMINISTERED`; it has no BCMA verification token or reference.
- The separate `backend/domains/pharmacy/router.py` `/bcma/verify-and-administer` endpoint invokes `execute_bcma_administration()`, which validates patient, medication, dose, route, timing, allergy, and duplicate administration, then creates both eMAR and BCMA audit records.
- `tests/test_10_nursing_emar_and_er_mlc.py` explicitly treats direct eMAR POST as a successful administration path without wristband or medication barcode scans.
- `tests/test_49_bcma_and_controlled_substances.py` separately validates the BCMA route and its hard stops.

**Impact:** A client with the eMAR permission can record an administered dose without invoking the five-rights verification and duplicate-dose controls. The direct route also does not serialize on the prescription item or check for an already administered dose. This creates two different bedside administration safety paths, and the safer path is not enforced by the API.

**Required closure evidence:**
1. Clinical governance explicitly decides which wards, medication classes, and scenarios require BCMA.
2. If mandatory, make the direct endpoint incapable of creating `ADMINISTERED` records without a server-verifiable BCMA result; avoid trusting a client-supplied boolean.
3. If non-BCMA administration is allowed, implement a distinct exception workflow with qualified role, reason, second check where required, timestamp, and immutable audit attribution.
4. Add concurrent and repeated-dose negative tests against every administration endpoint.
5. Ensure the UI does not expose a weaker route as an equivalent bedside administration action.

### ER-014 — Admission cancellation hard-deletes the admission and cascades transfer history

**Severity: P1 / High**

**Evidence:**
- `backend/domains/encounters/adt_router.py`, `cancel_admission()`: releases the current bed and calls `db.delete(admission)`.
- `backend/domains/encounters/models.py`: `BedTransferLog.admission_id` has `ondelete="CASCADE"`; `InpatientAdmission.transfer_logs` is linked to that admission.
- The cancellation handler does not create a cancellation event or reason-bearing audit record before deletion.

**Impact:** Cancelling an admission can permanently remove its bed-transfer history. In a hospital record system, cancellation should normally preserve the admission attempt and its operational history rather than erase it. This can weaken auditability and incident reconstruction.

**Required closure evidence:**
1. Replace hard delete with a terminal cancelled/void state and mandatory reason, actor, and timestamp.
2. Preserve bed-transfer history and all related clinical/operational evidence.
3. Add a controlled correction/void workflow with authorization and audit event.
4. Test cancellation before/after bed assignment and after one or more transfers, proving historical records remain queryable and bed occupancy is reconciled.

### ER-015 — Pharmacy FEFO override is advertised but not representable by the request schema

**Severity: P2 / Medium**

**Evidence:**
- `backend/domains/pharmacy/router.py`, `dispense_medication()`: checks `getattr(disp_item, "override_fefo", False)` and tells callers to pass `override_fefo=True`.
- `backend/domains/pharmacy/schemas.py`, `DispenseItem`: declares only `prescription_item_id`, `batch_id`, and `quantity_to_dispense`; no `override_fefo` field or override reason exists.
- Pydantic's default extra-field behavior means the undeclared field is not a supported contract for the request.

**Impact:** The documented FEFO override cannot be used through the declared API contract. If strict FEFO is intentional, the error text is misleading; if a clinical/pharmacy exception is intended, the API has no controlled, attributable way to request it.

**Required closure evidence:**
1. Decide whether FEFO is absolute or allows an exception.
2. If absolute, remove the unreachable override branch and return actionable instructions.
3. If exceptions are allowed, add a typed override field, mandatory reason, permission check, actor attribution, and audit event.
4. Add API contract tests for both normal FEFO and authorized exception behavior.

### ER-016 — Payment reversal deletes the original receipt instead of preserving a reversal ledger

**Severity: P1 / High**

**Evidence:**
- `backend/domains/billing/router.py`, `reverse_payment()`: after reducing invoice paid balance and restoring an advance deposit where applicable, it calls `db.delete(receipt)`.
- `PaymentReceipt` has no reversal status, reversal timestamp, reversing actor, or reference to a compensating reversal record in `backend/domains/billing/models.py`.
- The current payment reversal test verifies balance restoration and subsequent invoice voiding, but does not assert preservation of the original receipt or a reversal ledger entry.

**Impact:** The original receipt is removed from the operational payment table. A financial audit trail should preserve the original receipt and record a compensating reversal with actor, reason, time, and external bank/provider reference. This is especially important for disputes, reconciliation, GST/accounting evidence, and incident reconstruction.

**Required closure evidence:**
1. Make payment receipts immutable after posting.
2. Represent reversals as separate linked records/events; do not delete the original receipt.
3. Require reversal reason, actor, timestamp, approval policy, and external reversal reference where applicable.
4. Ensure invoice balances are derived or reconciled from posted receipts and reversal entries.
5. Add tests proving original receipt retention, repeated-reversal rejection, and exact ledger/balance reconciliation.

### ER-017 — Payment idempotency is optional, so retry safety is caller-dependent

**Severity: P1 / High for online payment methods; P2 / Medium for manually entered cash receipts.**

**Evidence:**
- `backend/domains/billing/router.py`, `record_payment()`: `Idempotency-Key` is optional and `payload.transaction_reference` is also optional.
- `backend/domains/billing/schemas.py`, `PaymentReceiptCreate`: transaction reference is optional.
- `PaymentReceipt` has a unique constraint on `(invoice_id, transaction_reference)`; SQL databases permit multiple NULL values in this composite uniqueness constraint.
- `tests/test_06_pharmacy_and_billing.py` verifies duplicate prevention when the same idempotency key is supplied, but does not verify behavior when a retry omits both identifiers.

**Impact:** The API prevents duplicate recording only when the caller supplies a stable key/reference. A network retry or repeated request without one can create a second receipt and increase the paid balance. This is not a safe default for UPI/card/provider callbacks.

**Required closure evidence:**
1. Require an idempotency key for retryable payment submissions and provider callbacks, with a documented retention window and request-payload consistency check.
2. Enforce uniqueness for provider transaction references and define behavior for missing/duplicate references by payment method.
3. Persist request outcome so exact retries return the original result while mismatched payload reuse is rejected.
4. Add concurrent duplicate-request tests and retry tests for UPI, card, cash, insurance, and advance adjustment, as applicable.

### ER-018 — Federation discovery purpose is caller-asserted, not bound to an authorization scope

**Severity: P1 / High**

**Evidence:**
- `backend/domains/federation/router.py`, `discover_and_aggregate_patient_across_branches()`: `purpose` is accepted as a free-text query parameter with only length constraints (3–255 characters).
- The endpoint rejects a fixed list of emergency-purpose strings, but routine discovery does not validate `purpose` against an approved purpose vocabulary or bind it to a node-/scope-specific capability.
- Source-side `FederationTransferLog` stores the supplied `purpose` as audit metadata. The source data-use decision is evaluated against the fixed `federation.patient.discover` data-use point; it does not authorize the requested purpose value.
- `get_federated_node()` authenticates an active hospital node using its API key. That credential does not identify the individual clinician or staff member initiating the request.
- The route comments explicitly defer remote emergency disclosure until a node-bound, purpose/scope-bound capability and verifiable human actor assertion exist. The same authorization-binding gap remains relevant to routine disclosure, even though emergency labels are blocked.
- Existing federation security tests cover payload tampering, missing receipts, stale identifiers, allergy-sharing settings, and import retry recovery; the reviewed test file does not demonstrate rejection of an unapproved routine purpose or enforcement of purpose-specific disclosure scopes.

**Impact:** The source audit log can record a caller-selected purpose that is not independently authorized or verified. A compromised or misused partner key may request routine demographic disclosure under a purpose label chosen by the caller, while the source policy evaluates only the general discovery data-use point. The audit record therefore proves what the caller supplied, not that the purpose was permitted or that a named clinician initiated the request.

**Required closure evidence:**
1. Define an approved purpose vocabulary and the permitted data categories/actions for each purpose.
2. Bind each request to a server-verifiable, short-lived capability scoped to the authenticated partner node, purpose, patient/selector, destination, and allowed data categories; reject unknown or mismatched scopes.
3. Introduce a verifiable human actor assertion for workflows that require clinician-level attribution; do not trust an unsigned identity header.
4. Preserve source-side audit events with both the authenticated node identity and verified actor/capability identifiers, while minimizing patient identifiers.
5. Add negative tests for unknown purposes, purpose/scope mismatch, cross-destination replay, revoked capability, expired capability, and attempts to obtain demographics/allergies outside the authorized category.
6. Keep remote emergency disclosure disabled until its stronger actor, purpose, and emergency authorization protocol is independently validated.

### ER-019 — CPOE allergy pre-check can disclose patient allergy details without a patient privacy decision

**Severity: P1 / High**

**Evidence:**
- `backend/domains/clinical/router.py`, `run_cpoe_allergy_check()` (POST `/api/clinical/cpoe/allergy-check`, also aliased as `/api/clinical/orders/check-allergy`): accepts `patient_id` and `allergen_keywords`; its only dependency is `RequirePermission("patients:read", "pharmacy:write")`.
- The handler calls `check_allergy_hard_stop()` directly. It does not load/validate an active patient, call `evaluate_tenant_data_use()`, or attach a registered `x-privacy-data-use-point`.
- `backend/domains/clinical/services.py`, `check_allergy_hard_stop()`: queries active severe/anaphylactic `PatientAllergy` rows for the supplied patient ID. On a match it raises HTTP 409 with the allergy name, severity, reaction description, and an order-blocked message. A non-match returns `{"status":"SAFE"}`.
- `backend/domains/privacy/data_use_points.py` has no data-use point for either CPOE allergy-check route. Existing points cover patient MPI/allergy reads and pharmacy prescription reads, but not this pre-check disclosure.
- The existing general permission check does not establish that the caller is permitted to access the selected patient's allergy record under the active privacy policy.

**Impact:** A user with either broad `patients:read` or `pharmacy:write` permission can submit arbitrary patient IDs and medication keywords to test for severe allergies. The response can disclose allergy names and reaction details, or confirm absence of a matching severe allergy, without a patient-specific privacy decision. This is a concrete disclosure path, not merely missing test coverage.

**Required closure evidence:**
1. Resolve the patient from the tenant database and return a consistent not-found response for missing/inactive patients.
2. Add a dedicated registered data-use point for CPOE allergy safety checks and evaluate the active patient privacy policy before returning allergy-dependent results.
3. Define the clinical safety behavior when privacy policy denies a pre-check; do not silently return `SAFE` or bypass an allergy hard-stop. Use a clinically governed denial/exception workflow.
4. Minimize response details to the authorized clinical need; avoid exposing reaction text to callers who only need a hard-stop result.
5. Add negative tests for denied consent/policy, inactive/nonexistent patient, unauthorized role, no matching allergy, matching severe allergy, and both route aliases.
6. Verify audit events identify the actor, patient, data-use point, decision, and time without unnecessarily duplicating sensitive reaction text.

### ER-020 — Direct nursing eMAR administration exposes detailed allergy data through an unscoped hard-stop response

**Severity: P1 / High**

**Evidence:**
- `backend/domains/clinical/nursing_er_router.py`, `record_emar_administration()` (POST `/api/nursing/encounters/{encounter_id}/emar`): accepts callers with `adt:write` OR `pharmacy:dispense`, validates the encounter and prescription-item relationship, then calls `check_allergy_hard_stop(db, enc.patient_id, [...])` when the requested status is `ADMINISTERED`.
- This write endpoint does not evaluate a patient privacy decision before invoking the allergy lookup. Its corresponding GET endpoint has a registered `nursing.emar.read` data-use point and evaluates patient policy; the POST path has no equivalent allergy-check data-use point.
- `backend/domains/clinical/services.py`, `check_allergy_hard_stop()`: on a severe/anaphylactic match, raises HTTP 409 containing allergy name, severity, and reaction description. The same helper is used by the CPOE allergy-check routes documented in ER-019.
- The separate pharmacy BCMA `/bcma/verify-and-administer` workflow has stronger bedside verification controls (see ER-013), but the direct eMAR route remains independently callable under its own permission dependency.

**Impact:** A caller permitted to record eMAR entries can use a medication-administration request to trigger a patient-specific allergy lookup and receive detailed allergy/reaction data without a patient-specific privacy decision. In addition, the endpoint remains a distinct direct administration path and must not be treated as equivalent to the BCMA-verified workflow.

**Required closure evidence:**
1. Decide through clinical governance whether direct eMAR administration is permitted at all, and define explicit ward/medication exceptions if BCMA is mandatory.
2. Ensure allergy hard-stop decisions are enforced without exposing unnecessary reaction details to callers; use a clinically safe, privacy-aware response that does not convert a denied privacy decision into an apparent safe-to-administer result.
3. Add a registered data-use point or equivalent approved authorization mechanism for the allergy lookup performed during administration, with actor/patient attribution and auditable decision.
4. Add negative tests for policy denial, unauthorized roles, patient/encounter mismatch, severe allergy match, and direct-vs-BCMA path parity; include repeated/concurrent dose safety checks.
5. Ensure UI and API clients cannot present the direct endpoint as a BCMA-equivalent path where bedside barcode verification is required.

### ER-021 — MLC police-intimation mutation returns sensitive case details without a patient privacy decision

**Severity: P1 / High**

**Evidence:**
- `backend/domains/clinical/nursing_er_router.py`, `register_medico_legal_case()` (POST `/api/er/mlc`): permits `opd:write`, resolves an active encounter, creates the MLC with patient-linked medico-legal details, and returns the complete `MLCResponse` without a patient privacy decision.
- The same file's `record_mlc_police_intimation()` (PATCH `/api/er/mlc/{mlc_id}/police-intimation`): permits `opd:write` OR `adt:write`, loads and locks the MLC by ID, updates police-intimation fields, and returns the complete `MLCResponse`.
- `backend/domains/clinical/schemas.py`, `MLCResponse`: response includes patient ID, alleged history, identification marks, brought-by name/relation/phone, injury cause, police station, FIR number, and other case identifiers.
- Neither the POST registration nor PATCH police-intimation handler evaluates a patient privacy decision. By contrast, the MLC print endpoint in the same router resolves the patient and evaluates the registered `registry.mlc.print` data-use point before disclosure.
- `tests/test_10_nursing_emar_and_er_mlc.py` exercises successful MLC registration and police-intimation PATCH and asserts returned fields, but does not test privacy-policy denial or role-specific minimization.

**Impact:** A caller with either broad write permission can receive sensitive medico-legal and identifying patient details in the mutation response without the patient-specific privacy gate applied by the print workflow. The write operation may be legitimate, but its response is also a PHI disclosure and needs an explicit policy decision.

**Required closure evidence:**
1. Resolve the MLC's patient and evaluate an approved MLC police-intimation data-use point before returning patient-linked details.
2. Separate permission to record the police-intimation event from permission to receive the full MLC payload; return a minimal mutation acknowledgement where full case details are not required.
3. Preserve forensic locking and audit attribution for both registration and police-intimation; do not weaken duplicate-case or duplicate-intimation protection.
4. Add negative tests for privacy-policy denial, roles with write but no read permission, patient/case mismatch, and response-field minimization for both POST and PATCH; retain positive tests for registration, first intimation, and duplicate intimation.

### ER-022 — Birth/death registry creation responses disclose patient-linked certificate data without a privacy decision

**Severity: P1 / High**

**Evidence:**
- `backend/domains/clinical/vital_registries_router.py`, `register_maternity_birth()` (POST `/api/registries/births`): requires `adt:write` OR `opd:write`, creates a birth record and (for live births) a linked newborn patient, then returns `BirthRecordResponse` without evaluating a patient privacy decision.
- `backend/domains/clinical/schemas.py`, `BirthRecordResponse`: includes mother/newborn patient IDs, newborn MRN, certificate number, attending doctor ID, birth time, delivery mode, weight, APGAR scores, and clinical notes.
- `certify_patient_death_mccd()` (POST `/api/registries/deaths`): requires `opd:write`, records death and closes the encounter/admission, then returns `DeathRecordResponse` without evaluating a patient privacy decision.
- `DeathRecordResponse` includes patient ID, certificate number, cause-of-death diagnosis ID, death time/manner, antecedent-cause notes, autopsy flag, and body handover recipient.
- The corresponding birth-list, birth-print, and death-print read paths explicitly evaluate registered patient data-use points. The creation responses do not.
- `tests/test_15_birth_death_registries_and_discharge_gate.py` asserts both POST operations return 201 and consumes the full response to obtain registry and newborn identifiers; it does not exercise privacy-policy denial or response minimization.

**Impact:** A caller authorized to perform a registry write also receives a full patient-linked clinical registry representation without an explicit patient privacy decision. This is a response disclosure issue; it does not imply that the underlying birth/death clinical write should be blocked.

**Required closure evidence:**
1. Separate permission to perform a statutory clinical registry action from permission to receive the full patient-linked response.
2. Evaluate an approved patient data-use point before returning patient-linked fields, or return a minimal creation acknowledgement containing only the record identifier and non-sensitive workflow status.
3. Preserve statutory record creation, newborn MPI linkage, encounter closure, bed release, and transaction integrity if the response is minimized or policy denies readback.
4. Add tests for policy denial, minimal response shape, authorized readback, and both stillbirth/live-birth and death-registration paths.

### ER-023 — Diagnostic result mutation response discloses prior patient result values without a privacy decision

**Severity: P1 / High**

**Evidence:**
- `backend/domains/diagnostics/router.py`, `submit_task_result()` (PATCH `/api/diagnostics/tasks/{task_id}/result`): accepts `diagnostics:write` OR `diagnostics:verify`, loads the task and its order, and can evaluate prior results for the same patient through `evaluate_lab_delta_check()`.
- The delta-check helper's result is persisted on the task as `previous_result_value`, `delta_percentage`, and a delta flag. The handler then returns `previous_result_value`, `delta_percentage`, and `result_notes` in its JSON response.
- This mutation handler does not call `evaluate_tenant_patient_data_uses()` and has no registered privacy data-use point in `backend/domains/privacy/data_use_points.py`. Read endpoints for diagnostic orders, tasks, worklists, and panic alerts do evaluate patient data-use decisions.
- The delta-check lookup uses the order's patient ID, so the prior result is patient-linked historical clinical information, not merely metadata about the current task.

**Impact:** A user authorized to enter or verify a laboratory result can receive historical patient result values and clinical notes in the mutation response without a patient-specific privacy decision. The result-entry action may be valid while the historical comparison fields are not necessarily authorized for disclosure to that actor.

**Required closure evidence:**
1. Define whether diagnostic result entry/verification permission inherently includes access to prior patient results; if so, encode and audit that as an explicit purpose-specific policy rather than relying on the write permission alone.
2. Evaluate the patient privacy decision for the delta-check/history access and response before returning prior result values or notes.
3. Minimize mutation responses for actors who may update a task but are not authorized to read the patient's historical results.
4. Add negative tests for policy denial, write-only/verify-only roles, prior-result presence, and response minimization; preserve positive delta-check and critical-result workflows.

### ER-024 — Statutory financial registers export patient identifiers without a patient privacy decision

**Severity: P1 / High**

**Evidence:**
- `backend/domains/reports/registers_router.py`, `get_cashier_shift_reconciliation()` (GET `/api/registers/cashier-shift-reconciliation`): permission is `billing:read` OR `finance:read`; it joins each payment receipt to its invoice and patient, then includes `patient_mrn` and `patient_name` in the transaction rows returned in JSON and in the optional CSV export.
- `get_ar_aging_ledger()` (GET `/api/registers/ar-aging`): permission is `billing:read` OR `finance:read`; it loads outstanding invoices with their patients and includes patient MRN/name, invoice number, payer source, and outstanding balance in the JSON sample and optional CSV export.
- Neither handler evaluates `evaluate_tenant_patient_data_uses()`, and neither route declares a patient-data-use point. The privacy data-use registry contains billing invoice read/search points, but no corresponding statutory-register disclosure points for these two endpoints.
- The same handlers return the patient-linked rows regardless of whether the caller requests JSON or CSV; changing the representation does not change the disclosure.
- The inspected handlers do not include a patient-policy denial path or tests proving that export is denied/minimized when patient disclosure is not permitted.

**Impact:** A caller with broad billing/finance read permission can retrieve or bulk-export identifiable patient financial records without a patient-specific privacy decision. This exposes MRNs, names, invoice/payment references, and financial balances through a reporting surface that is separate from the guarded invoice read/print routes.

**Required closure evidence:**
1. Define and register purpose-specific data-use points for cashier reconciliation and AR aging, including both JSON and CSV output modes.
2. Evaluate patient disclosure decisions for the exact patient set included in each response/export; do not authorize a whole unbounded export based solely on the caller's broad billing permission.
3. Where operational reconciliation does not require patient identity, provide a minimized/aggregated export; where identity is required, enforce an approved role, purpose, and patient-policy decision.
4. Add negative tests for denied policy, billing-read versus finance-read roles, JSON versus CSV parity, and multi-patient exports containing mixed policy outcomes.
5. Verify export audit records capture actor, purpose, filters/time window, record count, and export format without duplicating sensitive row contents in the audit event.

### ER-025 — CSV exports bypass patient privacy decisions enforced by the corresponding list endpoints

**Severity: P1 / High**

**Evidence:**
- `backend/domains/encounters/opd_router.py`, `list_appointments()` (GET `/api/opd/appointments?format=csv`): the CSV branch streams appointment rows containing patient MRN, patient name, and reason for visit, then returns before the JSON path's `evaluate_tenant_patient_data_uses()` call for `opd.appointments.search`.
- `backend/domains/encounters/adt_router.py`, `list_admissions()` (GET `/api/adt/admissions?format=csv`): the CSV branch streams patient MRN/name and admission details, then returns before the JSON path's `adt.admissions.search` privacy decision.
- `backend/domains/billing/router.py`, `list_invoices()` (GET `/api/billing/invoices?format=csv`): the CSV branch streams patient MRN/name and invoice financial details, then returns before the JSON path's `billing.invoices.search` privacy decision.
- In each route, the non-CSV paginated branch evaluates patient-specific decisions and returns 403 if any returned patient is denied. The corresponding CSV branch does not call that evaluator at all.
- `backend/domains/patients/router.py`, `list_patients()`, is an important contrast: its CSV row generator evaluates patient data-use decisions batch-by-batch and omits denied rows. It is not included as a bypass in this finding.
- `tests/test_61_streaming_export_and_registers.py` verifies that the CSV exports return successfully and contain expected columns, but does not test privacy-policy denial or JSON/CSV authorization parity for appointments, admissions, or invoices.

**Impact:** A caller with the route's ordinary read permission can bypass the patient-specific privacy gate by adding `format=csv`. The same patient-linked data that is denied by the paginated JSON endpoint can be bulk-exported through the alternate representation. The exposure includes appointment context, admission details, patient identifiers, and invoice balances.

**Required closure evidence:**
1. Apply the same patient-specific data-use decision to every row/batch streamed by these CSV endpoints before emitting that row; do not rely on OpenAPI metadata or the JSON branch's enforcement.
2. Define safe behavior for mixed authorization results in a stream (for example, omit denied rows with auditable decisions or reject the export before response headers are sent); ensure the chosen behavior is deterministic and documented.
3. Add paired JSON/CSV negative tests for denied policy, mixed allowed/denied patient sets, empty exports, pagination/filter parity, and large multi-batch exports.
4. Verify the streaming generator does not disclose rows before the relevant authorization decision and that policy evaluation/audit persistence works throughout stream iteration.
5. Add a route-level coverage assertion that every patient-linked export path enforces an approved data-use point, including future export formats.

### ER-026 — Insurance claims list exposes patient-linked financial and insurance data without a patient privacy decision

**Severity: P1 / High**

**Evidence:**
- `backend/domains/insurance/router.py`, `list_insurance_claims()` (GET `/api/insurance/claims`): the endpoint requires `billing:read`, joins each claim to its invoice and patient, and returns `InsuranceClaimResponse` rows in the paginated JSON response.
- Its optional CSV branch additionally emits patient MRN/name, provider, claim status, claimed amount, insurer payable, patient copay, settled amount, and settlement UTR reference.
- Neither JSON nor CSV branch calls `evaluate_tenant_patient_data_uses()`; the endpoint has no `x-privacy-data-use-point` annotation.
- `backend/domains/privacy/data_use_points.py` defines patient insurance-policy read and insurance preauthorization/claim-document print points, but no list/search point for the claims collection.
- `tests/test_09_insurance_and_auto_billing.py` covers claim creation, settlement, and supporting-document PDF behavior; no patient privacy-denial test for the claims list or CSV export was found.

**Impact:** A billing-read caller can enumerate patient-linked insurance claims and financial responsibility data without a patient-specific disclosure decision. The separate guarded claim-document endpoint does not protect this collection/list route.

**Required closure evidence:**
1. Register an insurance-claims search/list data-use point and evaluate it for the exact patient IDs in the JSON page and every CSV batch.
2. Define mixed-policy export behavior and ensure no rows are emitted before their decisions are available.
3. Minimize identifiers/financial fields according to role and purpose; ensure settlement UTR and other payment references are not exposed to roles that do not need them.
4. Add negative tests for denied policy, mixed patient decisions, JSON/CSV parity, pagination, and multi-batch exports.

### ER-027 — Surgery schedule list exposes patient identifiers and procedure context without a patient privacy decision

**Severity: P1 / High**

**Evidence:**
- `backend/domains/surgery/router.py`, `list_surgeries()` (GET `/api/ot/surgeries`): the endpoint requires either `adt:read` or `opd:read`, joins each schedule to its patient, and returns `SurgicalScheduleResponse` records in JSON.
- Its CSV branch explicitly emits case number, patient MRN, patient name, theatre, procedure name, lead surgeon, scheduled/actual times, and surgery status.
- Neither JSON nor CSV branch calls `evaluate_tenant_patient_data_uses()`; no patient-data-use point is declared for the list route.
- The separate completed-operative-note print route does enforce `ot.surgery.print`, demonstrating that a privacy gate exists for one surgical disclosure surface but not this schedule list.
- `tests/test_11_operation_theatre_and_surgery.py` verifies surgery scheduling, status transitions, and operative-note printing; no patient privacy-denial test for list or CSV output was found.

**Impact:** A user with broad OPD/ADT read permission can enumerate identifiable surgical schedules and associated procedure context without a patient-specific privacy decision. This exposes sensitive planned or completed care information beyond the guarded operative-note print flow.

**Required closure evidence:**
1. Register an OT surgery list/search data-use point and enforce it for both JSON pages and every CSV batch.
2. Define role- and purpose-based minimization for patient identifiers, procedure details, and schedule timestamps.
3. Add negative tests for denied/mixed decisions, JSON/CSV parity, pagination, and large exports.
4. Preserve operational access for authorized perioperative teams through explicit policy rather than relying on broad OPD/ADT permission alone.

### ER-028 — NHCX transaction retrieval returns patient-linked claim bundle without a patient privacy decision

**Severity: P1 / High**

**Evidence:**
- `backend/domains/abdm/router.py`, `get_nhcx_transaction_log()` (GET `/api/nhcx/transactions/{transaction_id}`): permission is any of `billing:read`, `insurance:read`, or `auditor:read`.
- The handler returns `patient_id`, `encounter_id`, `claim_id`, adjudication metadata, rejection reason, and the complete parsed `bundle_json` stored in `NHCXClaimExchangeLog`.
- `backend/domains/abdm/models.py` defines the log as patient- and encounter-linked and stores the raw FHIR claim bundle and response bundle JSON.
- The handler does not load/evaluate the patient privacy decision, check an NHCX-specific data-use point, or validate the current consent artefact before returning the stored bundle. The route has no patient-data-use-point annotation.
- `backend/domains/abdm/services.py` does generate the initial claim bundle from internal insurance data, but the retrieval handler is a separate read path and does not repeat a consent/policy check.
- `tests/test_51_abdm_and_nhcx_gateways.py` validates claim submission, adjudication callbacks, and transaction-log retrieval, but does not test retrieval denial after consent revocation/expiry or patient-policy denial.

**Impact:** A caller with broad billing, insurance, or auditor read permission and a transaction identifier can retrieve stored patient-linked claim data without a patient-specific disclosure decision. Because the bundle is returned in full, the exposure may exceed the minimum transaction metadata needed for reconciliation or audit.

**Required closure evidence:**
1. Define a distinct NHCX transaction-read data-use point and evaluate it against the patient linked to the transaction.
2. Enforce current consent/authority semantics for the requested operation, including revocation and expiry behavior; distinguish a lawful retained audit record from permission to disclose its full payload.
3. Return minimal transaction metadata by default; require a separately authorized purpose and role for full bundle retrieval, with field minimization where possible.
4. Add negative tests for patient-policy denial, revoked/expired consent, wrong patient/transaction scope, each permitted role, and attempts to retrieve full bundle versus metadata.
5. Audit actor, purpose, transaction ID, decision, and whether a full payload was disclosed without copying the raw bundle into audit metadata.

### ER-029 — Clinical quality incident records expose patient-linked safety narratives without a patient privacy decision

**Severity: P1 / High**

**Evidence:**
- `backend/domains/quality/router.py` exposes GET `/api/quality/incidents` and GET `/api/quality/incidents/{incident_id}` to callers with broad `clinical:read`, `nursing:read`, or `opd:read` permissions (detail also accepts `ipd:read` and `emr:read`).
- Both routes return `ClinicalIncidentResponse`, which includes `patient_id`, `encounter_id`, incident description, root-cause analysis, CAPA plan, severity, and lifecycle timestamps. These free-text fields can contain sensitive patient-safety, infection, adverse-drug-event, or treatment details.
- The same router's POST and PATCH mutation handlers return the same patient-linked response model without evaluating a patient privacy decision.
- `backend/domains/quality/models.py` links incidents to patient and encounter records; `backend/domains/quality/schemas.py` confirms the response exposes the identifiers and narrative fields.
- `backend/domains/privacy/data_use_points.py` contains no clinical-quality incident read/list/detail point, and the inspected quality routes do not call `evaluate_tenant_patient_data_uses()`.
- `tests/test_53_nabh_quality_indicators.py` exercises incident reporting, listing, detail retrieval, and CAPA lifecycle, but contains no patient privacy-denial or response-minimization tests.

**Impact:** A broadly read-authorized quality or clinical user can retrieve patient-linked incident narratives and investigation/CAPA details without a patient-specific disclosure decision. This is not merely an aggregate quality metric: the response contains case-level identifiers and free-text clinical narratives.

**Required closure evidence:**
1. Define a governed quality-incident data-use point and enforce it for list/detail and any mutation response that includes patient-linked data.
2. Separate authority to manage safety investigations from authority to disclose patient identity; provide minimized/redacted case responses where identity is not required.
3. Define mixed-patient list behavior and ensure filters/pagination cannot be used to infer denied cases.
4. Add negative tests for denied patient policy, roles with write-but-not-read authority, incident with no patient link, response minimization, and list/detail/mutation-response parity.
5. Audit actor, purpose, incident ID, patient decision, and disclosed field class without duplicating sensitive narrative text into audit metadata.

### ER-030 — Clinical chart mutation responses disclose patient-linked observations and narratives without a privacy decision

**Severity: P1 / High**

**Evidence:**
- `backend/domains/clinical/router.py` defines `_evaluate_patient_read()` and `_evaluate_encounter_read()`; the corresponding GET endpoints for encounter vitals, SOAP notes, diagnoses, patient comorbidities, and physical examinations invoke those helpers with purpose-specific points.
- The mutation endpoints return patient-linked clinical response models without an equivalent privacy decision:
  - `record_encounter_vitals()` POST `/api/clinical/encounters/{encounter_id}/vitals` requires `adt:write` and returns `EncounterVitalResponse` (vital measurements, BMI, notes, encounter ID).
  - `create_soap_clinical_note()` POST `/api/clinical/encounters/{encounter_id}/notes`, `update_soap_clinical_note()` PUT `/api/clinical/notes/{note_id}`, and `sign_off_clinical_note()` PATCH `/api/clinical/notes/{note_id}/sign` require `opd:write` and return `ClinicalNoteResponse` with subjective, objective, assessment, and plan narratives.
  - `attach_encounter_diagnosis()` POST `/api/clinical/encounters/{encounter_id}/diagnoses` requires `opd:write` and returns the diagnosis plus clinical remarks.
  - `chart_patient_comorbidity()` POST `/api/clinical/patients/{patient_id}/comorbidities` accepts any of `patients:write`, `opd:write`, or `adt:write` and returns the comorbidity and clinical remarks.
  - `record_encounter_physical_exam()` POST `/api/clinical/encounters/{encounter_id}/physical-exams` accepts `opd:write` or `adt:write` and returns exam findings and notes.
  - `evaluate_encounter_news2()` POST `/api/clinical/encounters/{encounter_id}/vitals/news2` accepts `clinical:write`, `opd:write`, or `adt:write` and returns patient-linked NEWS2/qSOFA scores, deterioration risk, RRT trigger state, sub-scores, and clinical recommendation. Its paired historical-score GET endpoint invokes the encounter privacy helper using `clinical.encounter.vitals.read`; the POST handler does not.
- The corresponding list/read handlers call the privacy helper using `clinical.encounter.vitals.read`, `clinical.encounter.notes.read`, `clinical.encounter.diagnoses.read`, `clinical.patient.comorbidities.read`, and `clinical.encounter.physical_exams.read`; the mutation handlers above do not call it or declare a mutation-response data-use point.
- `backend/domains/clinical/schemas.py` confirms these response models contain clinical measurements, free-text notes, diagnosis remarks, comorbidity remarks, and physical-exam findings.
- `tests/test_08_emr_vitals_and_reports.py` exercises clinical note creation/edit/sign behavior, including concurrent edit/sign locking, but the inspected coverage does not test privacy-policy denial or mutation-response minimization for these endpoints.

**Impact:** A caller with a clinical write permission can receive the full clinical record representation as a side effect of charting or signing, even where the corresponding read path would deny disclosure under patient-specific policy. This finding concerns response disclosure; it does not imply that valid clinical documentation actions should be blocked.

**Required closure evidence:**
1. Separate authority to create/update/sign clinical documentation from authority to receive the full patient-linked representation in the response.
2. Apply the matching patient data-use decision before returning clinical fields, or return a minimal acknowledgement and require a separately authorized read for full details.
3. Preserve clinical write integrity, note signature locking, and urgent bedside workflows when response disclosure is denied or minimized.
4. Add negative tests for policy denial and write-only roles, plus authorized readback and response-minimization tests for vitals, notes (create/update/sign), diagnoses, comorbidities, physical exams, and NEWS2 scoring.
5. Verify the mutation response cannot be used as a read-policy bypass and that audit metadata records actor, patient/encounter, purpose, decision, and response class without duplicating clinical narratives.

### ER-031 — Patient MPI and allergy mutation responses return patient-linked records without a privacy decision

**Severity: P1 / High**

**Evidence:**
- `backend/domains/patients/router.py`, `update_patient()`, PUT `/api/patients/{patient_id}`, requires `patients:write`, loads and updates an active patient, then returns the complete `PatientResponse`.
- `PatientResponse` in `backend/domains/patients/schemas.py` includes MRN, full name, date of birth, gender, phone, ABHA number, email, blood group, address, pincode, city/district/state/village, and emergency contact details.
- The corresponding GET `/api/patients/{patient_id}` evaluates `patients.mpi.read` and denies the response when the patient-specific decision is not allowed. The PUT handler does not evaluate that decision or declare a mutation-response data-use point.
- `backend/domains/patients/router.py`, `chart_patient_allergy()`, POST `/api/patients/{patient_id}/allergies`, requires `patients:write`, writes or updates the allergy record, synchronizes the central patient pointer, and returns `PatientAllergyResponse`.
- `PatientAllergyResponse` includes allergy ID, severity, reaction description, active state, and nested allergy metadata. The corresponding GET `/api/patients/{patient_id}/allergies` evaluates `patients.allergies.read`; the POST handler does not.
- `backend/domains/privacy/data_use_points.py` registers the MPI and allergy read points but no patient MPI update-response or allergy chart-response point.
- `tests/test_03_mpi_and_clinical_mdm.py` covers patient registration, allergy charting/idempotent updates, and allergy hard-stop behavior, but the inspected tests do not exercise privacy denial or mutation-response minimization for these endpoints.

**Impact:** A caller with patient write permission can receive broad demographic/contact data or allergy/reaction details in a mutation response even when the corresponding read endpoint would deny patient disclosure. The concern is the response payload, not whether a properly authorized clinical or registration update should be performed.

**Required closure evidence:**
1. Separate MPI/allergy write authority from authority to receive the full patient-linked representation.
2. Apply the applicable patient-specific decision before returning full response data, or return a minimal mutation acknowledgement and require a separately authorized readback.
3. Preserve clinical safety: allergy charting must still commit and propagate critical allergy indicators even if response disclosure is denied or minimized.
4. Add negative tests for denied policy and write-only roles, plus authorized readback and response-minimization tests for MPI update and allergy create/update.
5. Verify no mutation response bypasses MPI/allergy read policy; audit actor, patient, purpose, decision, and response class without copying sensitive values into audit metadata.

### ER-032 — ADT encounter create/update responses disclose patient-linked encounter records without a privacy decision

**Severity: P1 / High**

**Evidence:**
- `backend/domains/encounters/adt_router.py`, `create_encounter()`, POST `/api/adt/encounters`, requires `adt:write`, locks and validates the patient, creates an active encounter, and returns the complete `PatientEncounterResponse`. The response includes `patient_id`, encounter type/status, start/end times, primary doctor, and department. The handler does not evaluate a patient privacy decision.
- `update_encounter()`, PUT `/api/adt/encounters/{encounter_id}`, requires `adt:write`, updates doctor/department/chief-complaint fields, and returns the same patient-linked response model without a patient privacy decision.
- The corresponding GET `/api/adt/encounters/{encounter_id}` evaluates `adt.encounters.read` against the encounter's patient ID before returning `PatientEncounterResponse`; the active-encounter list similarly evaluates `adt.encounters.active.read`.
- `backend/domains/privacy/data_use_points.py` registers the two GET read points but no encounter create/update mutation-response point.
- `backend/domains/encounters/schemas.py` confirms `PatientEncounterResponse` includes `patient_id` and encounter context.
- `tests/test_04_wards_opd_and_adt.py` exercises encounter creation as part of OPD/IPD workflows and duplicate-active-encounter handling. The inspected tests do not exercise privacy-policy denial or response minimization for encounter create/update responses.

**Impact:** A caller with ADT write permission can receive a patient-linked encounter representation from a mutation even when the corresponding encounter read endpoint would deny disclosure under the patient-specific policy. The finding concerns response disclosure, not whether a valid encounter creation or update should be blocked.

**Required closure evidence:**
1. Separate ADT encounter write authority from authority to receive the full patient-linked response.
2. Apply the applicable patient-specific decision before returning the full response, or return a minimal acknowledgement and require separately authorized readback.
3. Preserve encounter creation, duplicate prevention, update integrity, and OPD/IPD workflows when response disclosure is denied or minimized.
4. Add negative tests for denied policy and write-only roles, plus authorized readback and response-minimization tests for POST and PUT.
5. Verify that the mutation response cannot bypass `adt.encounters.read`; audit actor, patient/encounter, purpose, decision, and response class without duplicating chief-complaint text.

### ER-033 — OPD appointment mutation responses disclose patient-linked scheduling and visit context without a privacy decision

**Severity: P1 / High**

**Evidence:**
- `backend/domains/encounters/opd_router.py`, `book_appointment()`, POST `/api/opd/appointments`, requires `opd:write`, accepts a patient ID and optional visit reason, creates the appointment, and returns the complete `AppointmentResponse`.
- `reschedule_appointment()`, PUT `/api/opd/appointments/{appointment_id}`, and `update_appointment_status()`, PATCH `/api/opd/appointments/{appointment_id}/status`, also require `opd:write` and return the same full response model after updating the record.
- `AppointmentResponse` in `backend/domains/encounters/schemas.py` includes `patient_id`, doctor and department IDs, appointment time, status, token number, free-text `reason_for_visit`, and linked encounter ID.
- The corresponding GET `/api/opd/appointments/{appointment_id}` evaluates `opd.appointments.read` against the appointment's patient ID before returning that response. The list endpoint evaluates `opd.appointments.search` for JSON results.
- `backend/domains/privacy/data_use_points.py` registers appointment read/search and print/history points, but no appointment create/reschedule/status mutation-response point.
- `tests/test_04_wards_opd_and_adt.py` covers successful booking, rescheduling, state transitions, and encounter binding. The inspected tests do not exercise patient-policy denial or response minimization for these mutation responses.

**Impact:** A caller with OPD write permission can obtain the patient-linked appointment representation, including the visit reason and encounter linkage, as a side effect of booking, rescheduling, or changing status even where the corresponding read endpoint would deny disclosure. This finding concerns response disclosure; it does not recommend blocking valid scheduling or status transitions.

**Required closure evidence:**
1. Separate OPD appointment write authority from authority to receive the full patient-linked response.
2. Apply the appropriate patient-specific decision before returning full details, or return a minimal acknowledgement and require separately authorized readback.
3. Preserve booking, overlap prevention, token allocation, appointment state transitions, encounter binding, and billing triggers when response disclosure is denied or minimized.
4. Add negative tests for denied policy and write-only roles, plus authorized readback and response-minimization tests for POST, PUT, and PATCH.
5. Verify that mutation responses cannot bypass `opd.appointments.read`; audit actor, patient/appointment, purpose, decision, and response class without duplicating visit-reason text.

### ER-034 — Diagnostic order create/update responses disclose patient-linked order and clinical context without a privacy decision

**Severity: P1 / High**

**Evidence:**
- `backend/domains/diagnostics/router.py`, `place_diagnostic_order()`, POST `/api/diagnostics/orders`, requires `diagnostics:write`, accepts `patient_id` and free-text `clinical_notes`, creates the order and tasks, then returns the complete `DiagnosticOrderResponse`.
- `update_diagnostic_order()`, PUT `/api/diagnostics/orders/{order_id}`, also requires `diagnostics:write`, updates clinical notes/status, and returns the same response model.
- `DiagnosticOrderResponse` in `backend/domains/diagnostics/schemas.py` includes `patient_id`, `ordering_doctor_id`, status, clinical notes, and nested task details. `DiagnosticTaskResponse` can include result values, result notes, critical-panic state, rejection reason, and delta-check context.
- The corresponding GET `/api/diagnostics/orders` and GET `/api/diagnostics/orders/{order_id}` evaluate `diagnostics.orders.search` and `diagnostics.orders.read` against the affected patient IDs before returning order data. The POST and PUT handlers do not evaluate a patient-specific privacy decision.
- `backend/domains/privacy/data_use_points.py` registers diagnostic order search/read and task read/queue points, but no diagnostic order create/update mutation-response point.
- `tests` coverage inspected for diagnostic order creation/update does not establish negative tests for privacy denial or response minimization on these mutation routes.

**Impact:** A caller with diagnostic write permission can receive patient-linked order and clinical context as a side effect of creating or updating an order even where the corresponding GET route would deny disclosure under patient-specific policy. The finding concerns response disclosure; it does not imply that valid diagnostic ordering or status updates should be blocked.

**Required closure evidence:**
1. Separate diagnostic order write authority from authority to receive the full patient-linked order/task representation.
2. Apply the relevant patient-specific decision before returning full details, or return a minimal acknowledgement and require separately authorized readback.
3. Preserve order creation, task expansion, billing, status transitions, and urgent laboratory workflows when response disclosure is denied or minimized.
4. Add negative tests for denied policy and write-only roles, plus authorized readback and response-minimization tests for POST and PUT.
5. Verify mutation responses cannot bypass `diagnostics.orders.read`; audit actor, patient/order, purpose, decision, and response class without duplicating clinical narratives or result values.

### ER-035 — Pharmacy prescription create/update responses disclose encounter-linked medication details without a privacy decision

**Severity: P1 / High**

**Evidence:**
- `backend/domains/pharmacy/router.py`, `write_prescription()`, POST `/api/pharmacy/prescriptions`, requires `pharmacy:write`, accepts an encounter ID, clinical notes, and medication/dosage items, then returns `PrescriptionResponse`.
- `update_prescription()`, PUT `/api/pharmacy/prescriptions/{prescription_id}`, also requires `pharmacy:write`, updates clinical notes/status, and returns the same response model.
- `PrescriptionResponse` in `backend/domains/pharmacy/schemas.py` includes `encounter_id`, prescribing doctor, clinical notes, and nested medication items with dosage instructions and requested/dispensed quantities. It omits patient name and MRN, but the encounter identifier directly links the returned medication/treatment details to a patient encounter.
- The corresponding GET `/api/pharmacy/prescriptions` and GET `/api/pharmacy/prescriptions/{prescription_id}` evaluate `pharmacy.prescriptions.search` / `pharmacy.prescriptions.read` against the encounter's patient ID before returning the prescription representation. The POST and PUT handlers do not evaluate a patient-specific privacy decision.
- `backend/domains/privacy/data_use_points.py` registers prescription search/read points but no prescription create/update mutation-response point.

**Impact:** A caller with pharmacy write permission can receive encounter-linked medication and dosage details through a mutation response even where the corresponding prescription GET route would deny disclosure under patient-specific policy. Patient name/MRN are omitted, which limits direct identity disclosure, but does not remove the patient linkage or sensitivity of the treatment details. The finding concerns response disclosure, not whether a valid prescription should be created or updated.

**Required closure evidence:**
1. Separate prescription write authority from authority to receive the full encounter-linked prescription representation.
2. Apply the applicable patient-specific decision before returning full details, or return a minimal acknowledgement and require separately authorized readback.
3. Preserve prescription creation, allergy/DDI hard-stops, dispensing integrity, and valid status updates when response disclosure is denied or minimized.
4. Add negative tests for denied policy and write-only roles, plus authorized readback and response-minimization tests for POST and PUT.
5. Verify mutation responses cannot bypass `pharmacy.prescriptions.read`; audit actor, patient/encounter, purpose, decision, and response class without duplicating clinical notes or dosage narratives.

### ER-036 — Diagnostic task result mutation response discloses prior patient laboratory result without a privacy decision

**Severity: P1 / High**

**Evidence:**
- `backend/domains/diagnostics/router.py`, `submit_task_result()`, PATCH `/api/diagnostics/tasks/{task_id}/result`, requires `diagnostics:write` and/or `diagnostics:verify` depending on transition. It loads the task's parent order and patient-linked task history, updates the result lifecycle, and returns a response containing `delta_check_flag`, `previous_result_value`, `delta_percentage`, and `result_notes`.
- On `RESULT_ENTERED`, the handler calls `evaluate_lab_delta_check()` using `task.order.patient_id` and the service ID. It then copies the prior result value and computed comparison metadata into the mutation response. The prior value is historical patient laboratory data, not merely an acknowledgement of the new write.
- The response is returned after the database commit without evaluating a patient-specific data-use decision. The handler also has no mutation-response privacy point.
- The corresponding task/order read paths use patient-specific points including `diagnostics.order.tasks.read`, `diagnostics.tasks.pending.read`, and `diagnostics.tasks.panic.read`. These checks do not protect the PATCH response.
- `DiagnosticTaskResponse` in `backend/domains/diagnostics/schemas.py` confirms the task result, result notes, delta flag, previous result, and percentage fields are represented in the domain response schema.

**Impact:** A diagnostic writer/verifier can receive historical patient laboratory information and delta-check context through a result mutation response without the patient-specific decision used by the task read routes. The finding is specifically about the prior-result disclosure and response path; it does not challenge the clinical value of delta checking or require suppressing a clinically necessary panic alert.

**Required closure evidence:**
1. Separate authority to enter/verify a result from authority to receive prior patient results and detailed delta context.
2. Apply the appropriate patient-specific decision before returning prior-result fields, or return a minimal status acknowledgement and require separately authorized task readback.
3. Preserve delta-check computation, result lifecycle, separation of duties, and critical panic alert delivery.
4. Add negative tests for denied policy and write-only roles, plus authorized readback and response-minimization tests for RESULT_ENTERED, repeat result entry, sample rejection, and verification transitions.
5. Verify that the mutation response cannot bypass `diagnostics.order.tasks.read` or the relevant patient-specific task read point; audit actor, patient/order/task, purpose, decision, and response class without copying result values into audit metadata.

### ER-037 — Controlled-substance movement responses and ledger reads disclose encounter-linked narcotics records without a privacy decision

**Severity: P1 / High**

**Evidence:**
- `backend/domains/pharmacy/router.py` exposes POST `/api/pharmacy/controlled-substances/dispense`, `/return`, and `/waste`. The handlers require pharmacy/nursing/clinical write permissions and return `ControlledSubstanceMovementResponse` from `process_controlled_substance_movement()`.
- Dispense, return, and wastage requests accept optional `encounter_id` and `prescription_item_id`. The service persists these identifiers on `ControlledSubstanceMovementLog` and returns the movement record after commit.
- `ControlledSubstanceMovementResponse` in `backend/domains/pharmacy/schemas.py` includes encounter ID, prescription-item ID, movement type, quantity/balance, wastage reason, disposal method, batch number, and notes. The linked prescription item resolves to a medication and dosage instruction; the encounter identifies the patient context.
- GET `/api/pharmacy/controlled-substances/movements` returns the full movement ledger, including those patient-linked identifiers and clinical wastage/return notes. Neither the mutation routes nor the ledger GET declares a patient-specific privacy decision. The GET route also has no `openapi_extra` privacy data-use point.
- `backend/domains/privacy/data_use_points.py` registers `pharmacy.prescriptions.search/read` but no controlled-substance movement read or mutation-response point.
- `backend/domains/pharmacy/models.py` confirms that movement records persist `encounter_id`, `prescription_item_id`, `wastage_reason`, `disposal_method`, and `notes`. These fields are not merely aggregate stock balances.

**Impact:** A caller authorized to perform or list controlled-substance movements can receive encounter-linked narcotics transaction details and clinical wastage/return context through the mutation response or unrestricted ledger read path without the patient-specific disclosure decision applied to prescription reads. This is a response/read disclosure finding; it does not challenge dual-witness verification, vault balance controls, or the need to retain the perpetual controlled-substance register.

**Required closure evidence:**
1. Separate controlled-substance movement write authority from authority to receive encounter-linked movement details.
2. Apply a patient-specific decision when a movement is linked to an encounter/prescription item, or return a minimal mutation acknowledgement and require separately authorized readback.
3. Add a privacy-gated ledger read that evaluates each linked patient and handles non-patient-linked receipts/ward stock movements under an explicit approved purpose policy.
4. Preserve dual-witness credential checks, return caps, vault locking/balance integrity, wastage documentation, and perpetual auditability.
5. Add denied-policy and write-only-role tests for dispense, return, wastage, and ledger GET, plus authorized readback and minimal-response tests. Ensure non-patient-linked receipt records remain available under the approved inventory purpose.
6. Audit actor, movement, linked patient/encounter, purpose, decision, and response class without copying clinical notes, wastage narratives, or prescription details into audit metadata.

### ER-038 — Pharmacy medication-return response discloses prescription-linked return and credit details without a privacy decision

**Severity: P1 / High**

**Evidence:**
- POST `/api/pharmacy/prescriptions/{prescription_id}/return` in `backend/domains/pharmacy/router.py` loads the prescription and its encounter, validates each returned `PrescriptionItem` against that prescription, restores inventory, adjusts dispensing quantities, and creates `PharmacyReturnLog` records.
- The endpoint returns the created records directly as `list[PharmacyReturnLogResponse]` after commit. The response schema in `backend/domains/pharmacy/schemas.py` includes `prescription_id`, `prescription_item_id`, `returned_quantity`, `credit_amount_paise`, and free-text `return_reason`.
- The prescription ID and item ID link the return event to the patient's encounter and prescribed medication. The return reason may contain patient-care context; this is not merely an aggregate inventory acknowledgement.
- The return handler has no patient-specific call to `evaluate_tenant_patient_data_uses()` and no mutation-response privacy data-use point. The corresponding GET prescription route evaluates `pharmacy.prescriptions.read`; that read decision does not protect the return mutation response.
- The pharmacy return response is distinct from the controlled-substance movement ledger in ER-037: it covers ordinary prescription return records and their credit/return-reason details.

**Impact:** A caller with pharmacy write/dispense permission can receive prescription-linked return and credit details through the mutation response without the patient-specific disclosure decision used by prescription reads. This is a source-level authorization/privacy gap, not evidence of production exploitation.

**Required closure evidence:**
1. Separate permission to process a medication return from permission to receive prescription-linked return details.
2. Evaluate the patient-specific decision before returning detailed return records, or return a minimal acknowledgement and require separately authorized readback.
3. Preserve stock restoration, dispensed-quantity reconciliation, invoice credit/refund handling, and immutable return provenance.
4. Add denied-policy and write-only-role tests for the return endpoint, plus authorized readback and response-minimization tests.
5. Ensure audit metadata records actor, prescription/item, patient linkage, purpose, decision, and response class without copying the free-text return reason or other clinical details.

### ER-039 — Nursing eMAR creation response discloses encounter-linked administration details without a privacy decision

**Severity: P1 / High**

**Evidence:**
- POST `/api/nursing/encounters/{encounter_id}/emar` in `backend/domains/clinical/nursing_er_router.py` requires `adt:write` or `pharmacy:dispense`, validates that the prescription item belongs to the supplied encounter, writes a `MedicationAdministrationLog`, commits, refreshes, and returns the complete ORM record.
- The response schema `eMARResponse` in `backend/domains/clinical/schemas.py` includes encounter ID, prescription-item ID, administering user ID, scheduled/administered timestamps, status, dose given, and free-text notes. The prescription-item ID links the record to the medication and treatment context.
- The corresponding GET `/api/nursing/encounters/{encounter_id}/emar` declares `nursing.emar.read`, loads the encounter's patient ID, and calls `evaluate_tenant_patient_data_uses()` before returning administration logs.
- The POST handler performs encounter/item ownership validation and the clinical allergy hard-stop, but does not call the patient-specific privacy evaluator and has no mutation-response privacy data-use point. The privacy registry defines `nursing.emar.read` only.
- This finding concerns the successful eMAR creation response. It is distinct from ER-020, which concerns allergy details returned by the nursing eMAR allergy hard-stop path.

**Impact:** A caller authorized to record a nursing administration can receive encounter-linked medication administration details and free-text notes in the POST response without the patient-specific disclosure decision required by the corresponding GET route. This is a source-level privacy enforcement gap, not evidence of production exploitation.

**Required closure evidence:**
1. Separate authority to record the administration from authority to receive the complete patient-linked eMAR record.
2. Evaluate the patient-specific decision before returning detailed eMAR fields, or return a minimal creation acknowledgement and require separately authorized readback.
3. Preserve encounter/prescription-item ownership checks, allergy hard-stop behavior, medication administration lifecycle, and clinical audit provenance.
4. Add negative tests for denied patient policy and write-only roles, plus authorized readback and response-minimization tests for ADMINISTERED, HELD, REFUSED, and MISSED states.
5. Audit actor, patient/encounter, prescription item, purpose, decision, and response class without copying dose notes or clinical narratives into audit metadata.

### ER-040 — Nursing fluid-balance creation response discloses encounter-linked intake/output details without a privacy decision

**Severity: P1 / High**

**Evidence:**
- POST `/api/nursing/encounters/{encounter_id}/fluid-logs` in `backend/domains/clinical/nursing_er_router.py` requires `adt:write`, validates that the encounter is active, creates a `FluidBalanceLog`, commits, refreshes, and returns the complete record.
- `FluidLogResponse` in `backend/domains/clinical/schemas.py` includes encounter ID, recording user, intake/output direction, fluid type, volume, timestamp, and free-text notes. These are encounter-linked clinical monitoring details.
- The corresponding GET `/api/nursing/encounters/{encounter_id}/fluid-balance` evaluates patient-specific `nursing.fluid_balance.read` before returning the logs and calculated balance.
- The POST route does not evaluate a patient-specific data-use decision and has no mutation-response privacy data-use point. The privacy registry defines the read point only.
- The inspected `tests/test_04_wards_opd_and_adt.py` contains no fluid-balance test coverage; no negative privacy-denial or response-minimization coverage was found in that inspected test file.

**Impact:** A caller authorized to record a nursing fluid log can receive encounter-linked intake/output measurements and notes in the POST response without the patient-specific disclosure decision required by the corresponding GET route. This is a source-level privacy enforcement gap, not evidence of production exploitation.

**Required closure evidence:**
1. Separate authority to record fluid observations from authority to receive the complete encounter-linked log response.
2. Evaluate the patient-specific decision before returning detailed log fields, or return a minimal creation acknowledgement and require separately authorized readback.
3. Preserve active-encounter validation, intake/output accounting, timestamps, and clinical audit provenance.
4. Add denied-policy/write-only-role tests and authorized readback/response-minimization tests for intake and output entries, including notes.
5. Audit actor, patient/encounter, purpose, decision, and response class without copying clinical notes into audit metadata.

### ER-041 — ER triage creation/upsert response discloses encounter-linked emergency assessment without a privacy decision

**Severity: P1 / High**

**Evidence:**
- POST `/api/er/encounters/{encounter_id}/triage` in `backend/domains/clinical/nursing_er_router.py` requires `adt:write` or `opd:write`, validates an active ER encounter, and either updates the existing triage assessment or creates one. It commits, refreshes, and returns the complete ORM record.
- `ERTriageResponse` in `backend/domains/clinical/schemas.py` includes encounter ID, triaging user ID, acuity level, chief complaint, GCS and pain scores, airway/breathing/circulation status, suspected MLC flag, triage notes, and creation timestamp.
- The same router's GET `/api/er/triage-queue` declares `er.triage_queue.read` and evaluates patient-specific data-use decisions for the patient IDs associated with all active triage encounters before returning the queue.
- The POST handler does not call `evaluate_tenant_patient_data_uses()` and does not declare a mutation-response privacy data-use point. It validates encounter type and status, but those checks do not establish permission to disclose the patient-linked assessment in the response.
- For RED_RESUSCITATION, the handler also publishes an `ER_RESUSCITATION_ALERT` containing encounter ID, acuity, chief complaint, GCS score, suspected-MLC flag, and triaging user ID. The event payload is a separate downstream disclosure surface that should be covered by an explicit, purpose-bound policy and recipient review.
- The inspected `tests/test_04_wards_opd_and_adt.py` contains no ER triage create/upsert privacy-denial or response-minimization tests.

**Impact:** A caller authorized to write ADT/OPD data can receive detailed emergency triage information through the create/update response without the patient-specific disclosure decision applied by the triage-queue read route. RED resuscitation event publication additionally propagates selected clinical details to the tenant event stream without a visible patient-specific decision in this handler. This is a source-level privacy enforcement gap, not evidence of production exploitation.

**Required closure evidence:**
1. Separate permission to create/update a triage assessment from permission to receive its complete patient-linked response.
2. Evaluate the patient-specific decision before returning detailed fields, or return a minimal acknowledgement and require separately authorized readback.
3. Define and enforce the purpose, authorized consumers, minimization, and audit requirements for RED resuscitation event payloads; do not assume tenant scoping alone authorizes every consumer.
4. Preserve active-ER-encounter validation, triage upsert semantics, acuity escalation, and emergency workflow availability.
5. Add denied-policy/write-only-role tests, authorized readback and response-minimization tests, and event-consumer authorization/payload tests for RED_RESUSCITATION.

### ER-042 — Blood transfusion cross-match, issue, and reaction responses disclose patient-linked transfusion records without a privacy decision

**Severity: P1 / High**

**Evidence:**
- POST `/api/blood-bank/cross-match` in `backend/domains/bloodbank/router.py` validates an active encounter, loads the encounter patient and blood group, checks donor-bag compatibility, creates a `BloodCrossMatchOrder`, and returns the complete record with its blood-bag relationship.
- PATCH `/api/blood-bank/cross-match/{cross_match_id}/issue` and PATCH `/api/blood-bank/cross-match/{cross_match_id}/reaction` also return the complete `BloodCrossMatchResponse` after updating issue or adverse-reaction state.
- `BloodCrossMatchResponse` in `backend/domains/bloodbank/schemas.py` exposes encounter ID, patient ID, blood-bag ID and bag details, ordering/cross-match/issue actor IDs, issue timestamp, reaction type, and free-text reaction notes. The model links each order to both a patient and encounter; reaction notes can contain clinical observations.
- The three mutation handlers do not call `evaluate_tenant_patient_data_uses()` and declare no patient-specific mutation-response data-use point. The privacy data-use registry `backend/domains/privacy/data_use_points.py` includes registry and diagnostic study points but no blood-bank/transfusion point.
- The inspected `tests/test_12_blood_bank_and_radiology_pacs.py` tests compatibility hard-stops, successful cross-match, issue/billing, reaction quarantine, and date/expiry controls; it contains no patient-policy denial or response-minimization tests for these routes.

**Impact:** A caller authorized to perform a transfusion workflow can receive patient-linked blood-group/transfusion state and, on the reaction route, clinical reaction notes through the mutation response without a patient-specific disclosure decision. This is a source-level privacy enforcement gap, not evidence of production exploitation.

**Required closure evidence:**
1. Separate authority to perform cross-match/issue/reaction actions from authority to receive the complete patient-linked transfusion record.
2. Add explicit purpose-bound privacy data-use points and evaluate the patient-specific decision before returning detailed responses, or return minimal acknowledgements with separately authorized readback.
3. Preserve compatibility hard-stops, bag locking and status transitions, issue billing, reaction quarantine, and emergency transfusion availability.
4. Add denied-policy/write-only-role tests and response-minimization/readback tests for cross-match, issue, and reaction workflows.
5. Audit actor, patient/encounter, blood-bag reference, purpose, decision, and response class without copying reaction narratives into audit metadata.


### ER-043 — Surgical schedule, safety checklist, operative record, implant, and status mutation responses disclose patient-linked surgical data without a privacy decision

**Severity: P1 / High**

**Evidence:**
- POST `/api/ot/surgeries` in `backend/domains/surgery/router.py` validates an active patient encounter, copies `enc.patient_id` into a new `SurgicalSchedule`, commits, refreshes, and returns the full `SurgicalScheduleResponse`. That schema exposes patient ID, encounter ID, case number, procedure and theatre identifiers, assigned clinician IDs, schedule times, status, and pre-operative diagnosis notes.
- PUT `/api/ot/surgeries/{surgery_id}/checklist` returns `WHOChecklistResponse`, including surgery ID, verifier ID, patient identity confirmation, site marking, consent confirmation, allergy check, prophylaxis, and instrument/specimen sign-out checks. These are patient-linked surgical safety attestations.
- PUT `/api/ot/surgeries/{surgery_id}/operative-record` returns `OperativeRecordResponse`, including anesthesia type, ASA physical status, anesthesia notes, operative findings, post-operative instructions, and estimated blood loss. The model stores free-text clinical findings and notes.
- POST `/api/ot/surgeries/{surgery_id}/implants` returns `SurgicalImplantResponse`, including surgery ID, implant identity/manufacturer, serial or batch number, quantity, and unit price. The implant model links the record to the patient-linked surgical schedule.
- PATCH `/api/ot/surgeries/{surgery_id}/status` returns `SurgicalScheduleResponse` containing patient and encounter identifiers and surgery lifecycle details. The handler loads related checklist, operative record, and implant relationships for workflow validation, although the response schema itself is the schedule schema.
- These mutation handlers enforce workflow permissions and state constraints but do not call `evaluate_tenant_patient_data_uses()` or declare mutation-response data-use points. The privacy registry includes `ot.surgery.print` for GET `/api/ot/surgeries/{surgery_id}/print`; that print handler evaluates a patient-specific decision before rendering the operative note. No corresponding surgical mutation-response points are registered.
- `tests/test_11_operation_theatre_and_surgery.py` covers scheduling conflicts, WHO checklist hard-stops, operative completion and billing, print output, and terminal-state write protection. The inspected tests do not cover patient-policy denial or response minimization for schedule creation, checklist, operative-record, implant, or status mutation responses.

**Impact:** A caller with surgical workflow write permission can receive patient-linked surgical identifiers, safety attestations, operative clinical narratives, and implant traceability details through mutation responses without the patient-specific disclosure decision used by the operative-note print route. This is a source-level privacy enforcement gap, not evidence of production exploitation. This finding is distinct from ER-027, which concerns surgery list JSON/CSV retrieval rather than mutation responses.

**Required closure evidence:**
1. Separate permission to perform each surgical workflow mutation from authority to receive its complete patient-linked response.
2. Add purpose-bound data-use points and evaluate the patient-specific decision before returning detailed responses, or return minimal acknowledgements with separately authorized readback.
3. Apply the response policy consistently to schedule creation, checklist upsert, operative-record upsert, implant logging, and status transitions; assess any billing/event side effects as separate disclosure channels where applicable.
4. Preserve theatre/clinician conflict locking, WHO checklist hard-stops, terminal-state protections, implant traceability, completion billing, and emergency surgical workflow availability.
5. Add denied-policy/write-only-role tests and response-minimization/readback tests for each mutation route. Keep operative findings, anesthesia notes, and other clinical narratives out of audit metadata.


### ER-044 — PACS/DICOM metadata upsert returns patient-linked imaging metadata and radiologist impression without a patient-specific privacy decision

**Severity: P1 / High**

**Evidence:**
- The PACS integration is implemented in `backend/domains/bloodbank/router.py` (the module is mounted from `backend/main.py` as the blood-bank/PACS router), not in the diagnostics router.
- PUT `/api/diagnostics/tasks/{task_id}/dicom-study` requires `diagnostics:write` or `diagnostics:verify`, locks the associated diagnostic order and task, rejects completed/cancelled workflows and non-radiology tasks, then creates or updates `RadiologyStudyMetadata`, commits, refreshes, and returns the complete `RadiologyStudyResponse`.
- The response contains the diagnostic task ID, DICOM Study Instance UID, accession number, modality, PACS viewer URL, radiation dose, and radiologist impression. The metadata model links to `DiagnosticTask`, which links through its order to the patient.
- The corresponding GET endpoint declares and evaluates `diagnostics.study.read` against the order's patient ID before returning the same imaging metadata. The privacy data-use registry includes this read point, but no separate write/mutation-response point is registered or evaluated by the PUT handler.
- `tests/test_12_blood_bank_and_radiology_pacs.py` verifies that metadata can only attach to radiology tasks and that verified/cancelled/completed records cannot be modified. The inspected PACS tests do not verify patient-policy denial or minimal mutation responses.
- The inspected repository has no DICOM image proxy, binary image download, or PACS session authorization endpoint. The current finding is limited to the metadata upsert response and its embedded viewer URL; it does not claim that the application itself serves image pixels.

**Impact:** A caller authorized to write diagnostic metadata can receive a patient-linked imaging locator and radiologist impression in the mutation response without the patient-specific disclosure decision required by the matching GET route. The viewer URL may be a capability or sensitive locator depending on the external PACS implementation; its actual access semantics and downstream authentication are not established by this source review. This is distinct from ER-034 (diagnostic order mutation responses) and ER-036 (diagnostic task result mutation responses).

**Required closure evidence:**
1. Define a purpose-bound PACS metadata mutation-response data-use point and evaluate the patient-specific decision before returning detailed metadata, or return a minimal acknowledgement and require authorized readback.
2. Decide whether the PACS viewer URL is a bearer capability, session-bound URL, or non-sensitive locator; document and test expiry, authentication, revocation, and logging behavior with the PACS provider.
3. Add denied-policy and response-minimization tests for both create and update paths while preserving task/order locking, modality checks, UID uniqueness, and terminal-state immutability.
4. Confirm separately whether image pixel retrieval is handled exclusively by the external PACS; if HMS later proxies or downloads images, require a separately authorized patient-specific access point and audit trail.

## 9. Next audit pass

The next pass should turn each P0/P1 finding into a narrowly scoped implementation/review work item with:
- accountable engineering, security, clinical, privacy/legal, and operations owners;
- exact source files and threat/workflow boundaries;
- tests and negative tests;
- staging evidence requirements;
- independent reviewer and explicit release-gate criteria.

Do not bundle the AUD-004 identity redesign, privacy enforcement, payment gates, and monitoring changes into one large implementation PR. Keep security-sensitive work independently reviewable.
