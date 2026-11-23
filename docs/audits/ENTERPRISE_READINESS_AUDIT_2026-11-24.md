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

## 8. Next audit pass

The next pass should turn each P0/P1 finding into a narrowly scoped implementation/review work item with:
- accountable engineering, security, clinical, privacy/legal, and operations owners;
- exact source files and threat/workflow boundaries;
- tests and negative tests;
- staging evidence requirements;
- independent reviewer and explicit release-gate criteria.

Do not bundle the AUD-004 identity redesign, privacy enforcement, payment gates, and monitoring changes into one large implementation PR. Keep security-sensitive work independently reviewable.
