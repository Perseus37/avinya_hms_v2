# AUD-004 Canonical Baseline and Decision Register

**Status:** Consolidated working baseline — proposed, not formally approved  
**Purpose:** One main-based navigation and decision register for the AUD-004 design/review history.  
**Architecture invariant:** PostgreSQL **database-per-tenant**. No schema-per-tenant migration is proposed.  
**Release status:** AUD-004 remains a release blocker. This document does not authorize implementation, merge, pilot or deployment.

## 1. Document authority and precedence

This register is the main-based index for implementation-readiness and decision tracking. It does not silently promote draft proposals into approved policy.

Use this authority order:

1. Formal governance decisions, when recorded with accountable approvers and evidence, control policy choices.
2. The accepted architecture decision, when approved, controls the tenant storage and identity model.
3. This register tracks the current proposed baseline, unresolved findings and evidence gates.
4. Detailed design and independent-review documents linked below retain their detailed rationale, test cases and review history.
5. Runtime source code is evidence of what the repository currently does; proposed documents do not prove enforcement.
6. Deployed PostgreSQL catalogs, secret policies, network rules, workload identity and provider controls require independent deployment evidence. They have not been inspected as part of this repository review.

If this register conflicts with a detailed review, runtime evidence or a formal decision, do not silently choose one. Record and resolve the conflict before implementation.

## 2. Architecture baseline — preserve database-per-tenant

The inspected application uses a separate PostgreSQL database for each tenant. The tenant registry stores a database name; the connection builder changes the database component of a shared configured URL. The inspected federation routes resolve another tenant's database name and open a session through the tenant engine registry.

The target architecture must preserve database-per-tenant while closing the identity boundary:

- Tenant A application identity can connect only to Tenant A's database.
- Tenant A source-disclosure identity is source-bound to Tenant A and has only the minimum source-policy, clinician-mapping, patient/resource-read and source-audit permissions required.
- A destination import identity cannot open a direct session to a foreign tenant database.
- Control-plane API identity accesses control-plane data, not tenant clinical databases.
- Provisioning and migration identities are separate, short-lived and unavailable to normal runtime services.
- Backup, restore/DR, retention, integration, monitoring and vault identities have explicit separate scopes.
- No tenant-facing service receives a fleet-wide bundle of tenant database credentials.
- Database names and control-plane routing metadata are selectors, not credentials or authorization.

The JSON Schema files in the design series describe JSON document contracts. They are not PostgreSQL schemas, namespaces or migrations. No database topology change is authorized or required by these findings.

## 3. Federation protocol invariants

The proposed protocol keeps three lifecycles distinct:

1. **Source clinician authorization and disclosure:** the source tenant authenticates the requesting node, validates a source-trusted clinician assertion, resolves source-controlled clinician mapping, authorizes the bounded search before any patient-specific selector query, authorizes each candidate/resource, and durably records disclosure intent before releasing data.
2. **Discovery response integrity and delivery:** signed manifests, receipts and handles prove only their explicitly bound integrity/delivery facts. They are not clinician authority or bearer permission for a new source read. A retry that performs a new source read requires fresh source authorization.
3. **Destination import and recovery:** a server-derived immutable operation identity and unique claim prevent duplicate imports; clone, provenance and operation marker commit atomically in the destination database; acknowledgement is derived from re-read durable commit evidence; pointer synchronization is a separate recoverable step; COMPLETED is impossible until pointer sync is verified.

The same source-owned authorization boundary must apply to remote federation and local cross-branch access, including internal, background, administrative, support, retry and recovery paths. No direct foreign-database fallback is permitted when the source service is unavailable.

Other non-negotiable controls include deny-by-default purpose/action/scope, anti-enumeration, opaque recipient-bound non-bearer handles, replay protection, source-owned audit, explicit uncertain outcomes, and emergency/break-glass federation remaining disabled.

## 4. Consolidated open finding register

All entries below remain open unless a later formal decision and objective evidence explicitly closes them.

| Finding | Severity | Required closure evidence |
|---|---|---|
| CAN-01 | High | Enforceable source-owned boundary; no destination direct foreign DB reads; complete route/job/admin/support/recovery inventory; database-role negative tests |
| CAN-02 | High | No plain/global deterministic hashes of low-entropy selectors; approved keyed commitment, canonicalization, key custody/rotation and privacy tests |
| CAN-03 | High | Trusted eligible-source registry, server-bounded fan-out, partial-outcome and anti-enumeration tests |
| CAN-04 | High | Exact immutable import idempotency tuple, destination unique claim, atomic clone/provenance/marker commit, acknowledgement and fencing proof |
| CAN-05 | High | Named clinical/privacy/operations ownership and approved post-commit quarantine semantics |
| CAN-06 | Medium | Externally testable anti-enumeration response equivalence, cache and rate-limit contract |
| CAN-01A–C | High | Reconcile actual database-per-tenant runtime; remove shared-credential foreign DB path; enforce source-owned reads |
| DBID-01–05 | High | PostgreSQL cluster-wide role/CONNECT rules; ownership and object grants; secret bootstrap/rotation/revocation/pool invalidation; safe provisioning/migration; source-audit transaction boundaries |
| DBID-06–08 | Medium | Backup/restore alternate-path controls; supported deployment matrix; non-authoritative database/role naming |
| DBID-R74 | Critical | Approved external revocation authority and protocol, signed proof/trust lifecycle, effective-time semantics and deterministic race evidence |
| DBID-R75 | High | Selected deployment topology, sole artifact-read capability, enforced egress boundary and negative tests |
| DBID-R76 | High | Exact envelope byte encoding, immutable cryptographic profile registry, trust/key lifecycle and cross-language vectors |
| DBID-R77 | High | Versioned authenticated polling/redemption API, reference lifecycle, idempotency, response equivalence and replay/race tests |
| DBID-R78 | High | Supported PostgreSQL catalog adapters, lossless cluster-wide ACL inventory, independent effective-privilege oracle and synthetic-cluster evidence |
| DBID-R79 | High | Normative lifecycle graph, deterministic verifier, error taxonomy, conformance/model-check suite and authority matrix |
| DBID-R80 | High | Provider support matrix, root-of-scope and pagination evidence, snapshot guarantees and independent completeness witness |
| DBID-R81 | High | Supported worker platform profiles, trusted measured-state source, attestation chain and independent enforcement verification |

A finding is not closed by a document, a schema file, a green synthetic fixture, a PR being open, or an assertion from the component being evaluated.

## 5. Governance and approval status

D-01 through D-14 remain formally pending. D-11 has a project direction of YES, but that is not formal governance approval. The required clinical, privacy, legal, security/cryptography, database, platform/operations and provider owners must record their decisions and evidence.

The following decisions must not be inferred:

- no approval of the external revocation authority or its effective-time guarantee;
- no approval of a cryptographic profile, key authority or issuer trust model;
- no approval of a provider/platform support matrix;
- no approval of a production routing topology or global selector index exception;
- no authorization for partner onboarding, trust provisioning or federation activation.

## 6. PR portfolio and traceability

| PRs | Role in the history | Disposition |
|---|---|---|
| #17 | Mainline security/lifecycle audit history | Preserve as audit record |
| #19 | AUD-001–003 runtime remediation | Keep open for focused review, CI and remaining remediation; not a substitute for AUD-004 |
| #20–#39 | Clinician assertion, import recovery, protocol, adversarial review and ADV resolution series | Supporting stacked design/review history |
| #40–#41 | Canonical protocol/governance consolidation and independent review | Key protocol checkpoint; review findings CAN-01–CAN-06 remain open |
| #42–#43 | CAN-01 enforceable source-boundary proposal and runtime cross-check | Key source-boundary checkpoint; confirms actual database-per-tenant/shared-credential mismatch in inspected code |
| #44–#45 | Database-per-tenant identity ADR and independent review | Key database identity checkpoint; DBID-01–05 High and DBID-06–08 Medium remain open |
| #46–#66 | DBID proposal/review sequence and JSON Schema document contracts | Supporting stacked design/review history; not PostgreSQL migrations |
| #67–#69 | DBID-R66–R81 review, resolution and independent review | Latest DBID checkpoint; DBID-R74 Critical and DBID-R75–R81 High remain open |
| #70 | Main-based implementation-readiness report and owner register | Current readiness/portfolio record |
| #71 | Disposable PostgreSQL ACL proof harness | Keep as synthetic evidence only; does not prove deployed identity/grants |

The chains are stacked: later PRs use earlier PR branches as their base. PR #40 is based on the PR #39 branch; #42 follows the #41 review branch; #44 follows #43; #68 follows #67. The latest consolidation PRs are therefore not independently based on main. Do not bulk-close or merge these PRs individually before preserving their unique content and review history on a durable main-based record.

## 7. PR #19 runtime-remediation stop conditions

PR #19 is main-based, non-draft and has a successful Release gates workflow run at the inspected head. That is useful CI evidence for that commit; it is not approval to merge and does not close the open data-integrity/recovery findings recorded in the PR discussion.

The latest inspected PR #19 head still has these explicit follow-ups:

- **Post-commit pointer synchronization:** destination patient/allergy rows commit before pointer synchronization. If pointer sync then fails, the request can return an error after the patient is already committed. The existing-patient retry path can return early without repairing the pointer. Required: a durable pending-sync/reconciliation state, idempotent retry repair, and failure-injection tests proving the committed import is never reported as fully complete until pointer sync is verified.
- **Concurrent duplicate imports:** short-lived discovery receipts are reusable for retries, but the fallback identity (phone, date of birth, full name) has no database uniqueness constraint. Concurrent requests can both pass the lookup and create duplicate no-ABHA clones; ABHA races may surface as an unhandled uniqueness error. Required: a durable idempotency claim keyed by destination plus source pointer/transfer identity, enforced by a unique constraint and transaction-safe claim, with concurrency and lost-response retry tests.
- **Independent proof boundary:** PR #19's receipt is a useful server-side completeness control, but it does not solve the separate AUD-004 source-owned database boundary. The inspected federation implementation still opens source tenant sessions through the tenant engine registry; source authorization and tenant database identity isolation remain AUD-004 blockers.
- **Retention behavior:** the fail-closed dependency-query change is positive, but release acceptance still requires tests for database/query failure, rollback behavior, immutable federation transfer-log retention, and approved retention/legal policy.

The PR discussion links a proposed durable idempotency and recovery design in PR #23. That proposal is design evidence only; it does not mean the runtime fix exists. Do not treat PR #19's successful workflow as proof that these follow-ups are implemented, tested or independently accepted.

## 8. PR #23 design review and repository implementation dependency audit — still unapproved

PR #23's design document was expanded at head `99719aeb5f8c24efc018f9886ca223ec03351355` to include a read-only, repository-grounded implementation dependency map. It records the actual separation between `ControlBase` and tenant `Base`, separate control-plane and tenant Alembic histories, the staged migration runner, current patient/pointer/receipt models, and the existing source transfer audit.

The audit identified concrete prerequisites that must be resolved before runtime implementation:

- `GlobalPatientPointer` has no explicit monotonic generation/version; timestamp alone is not a fencing generation.
- `TenantRegistry` has an integer primary key, unique branch code and unique database name, but no dedicated immutable UUID. The canonical tenant identity must be formally selected or added.
- Current discovery receipt migration `6c9f2a1d8b40` has a source-pointer foreign key with `ON DELETE CASCADE`; durable operation/audit evidence must not be erased by pointer deletion or receipt expiry.
- No tenant-local federation import correlation/provenance model currently exists in the inspected PR #19 branch.
- Existing `migrate_remaining_fleet` selects active CLOUD tenants; it does not include ON_PREM tenant databases. A separate controlled ON_PREM migration and verification path is required before enabling the feature there.

The design now orders the work as identity prerequisites, control-plane persistence, tenant-local persistence, destination fencing proof, saga/API orchestration, PostgreSQL failure-injection evidence, and gated CLOUD plus ON_PREM rollout. It explicitly states that repository source inspection is not proof of live migration heads or production database state.

The revised document remains **PROPOSED — NOT APPROVED FOR IMPLEMENTATION OR RELEASE**. PR #23 remains draft and stacked on PR #19, not `main`; no submitted independent GitHub review is recorded. No runtime changes, migration execution or production database queries occurred. PostgreSQL **database-per-tenant** remains the architecture; no schema-per-tenant conversion is proposed. PR #19 remains open and unmerged; AUD-004 remains a separate release blocker.
## 9. PR #19 implementation trace against PR #23 recovery criteria

Read-only static review of PR #19 head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`, performed after the PR #23 design review. This is source inspection only; no tests were executed as part of this review.

| Required invariant | Current PR #19 evidence | Assessment |
|---|---|---|
| Server-derived durable import identity | `backend/domains/federation/router.py:915-925` checks ABHA, then phone + DOB + exact name; existing match returns early | **Not met** — demographic lookup is not an operation identity |
| Atomic durable control-plane claim | `backend/control_plane/models.py` contains the discovery receipt model but no federated-import operation model | **Not met** |
| Destination-side unique correlation marker | Import creates a patient at `router.py:927-979`; no source-pointer/operation marker is written atomically with the clone | **Not met** |
| Recover post-commit pointer failure | Patient/allergies commit at `router.py:979`; pointer sync occurs at `router.py:985` | **Not met** — pointer failure occurs after destination commit |
| Retry repairs pointer | Existing-patient return at `router.py:924` exits before the pointer-sync call | **Not met** |
| Fencing and stale-worker rejection | No operation generation/lease state or conditional transition is present in the reviewed model/migration | **Not met** |
| Durable import migration | Migration `6c9f2a1d8b40_federated_discovery_receipts.py` creates only the short-lived discovery receipt table | **Not met** |
| Concurrency and crash-window proof | `tests/test_07_federation_and_backups.py:853-925` tests receipt rejection, ambiguous phone discovery and partial discovery; no concurrent import, lost-response, pointer-repair or stale-worker test is present | **Not met** |
| PostgreSQL multi-worker failure injection | No test evidence for independent concurrent sessions/processes at import commit boundaries in the reviewed PR #19 test changes | **Not met** |

The receipt/completeness guard in PR #19 remains a positive remediation: import requires a server-issued receipt and validates its destination, selector, summary and current pointer snapshot before source revalidation. That does not provide durable import idempotency or recovery.

A read-only review note with this trace was added to PR #19. The two core data-integrity gaps are therefore confirmed in the current code, not just design concerns. PR #19 should remain unmerged until durable operation identity, both uniqueness barriers, fencing, recoverable pointer synchronization, migration, PostgreSQL concurrency/failure-injection tests and independent review are complete. AUD-004's source-owned database boundary remains a separate release blocker.

## 10. Current PR and CI evidence snapshot — 2026-11-13

Live GitHub metadata was rechecked after the PR #19 source trace:

- **PR #19** remains open, non-draft, based on `main`, head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; GitHub reports `mergeable_state=blocked`. The latest recorded check-run set has six successful jobs (Python tests/PostgreSQL 17 migrations, hospital UI, onboarding UI, Compose validation, image build/scan, and scanned-image handoff) and one skipped job (`Publish, attest, and verify release images`). These CI successes do not prove the missing import recovery invariants and do not constitute production approval.
- **PR #23** remains open/draft and is stacked on PR #19's branch, not `main`. Its current head at this register refresh is `99719aeb5f8c24efc018f9886ca223ec03351355`; the recovery-design document blob is `a1b07e636ac7afb524612470f3c84cc340e86056`. The PR has no submitted GitHub reviews. The design-review comment is feedback, not approval.
- **PR #70** remains open/draft, based on `main`, with the current canonical-document commit as its head. This register is still a proposal pending independent review and merge; it is not yet the repository's accepted baseline on `main`.

The PR #19 check-run snapshot is tied to the exact head listed above. Recheck CI after any subsequent commit. A skipped image publication/attestation job must not be described as a successful release-image publication. No PR was merged or closed in this review.

## 11. Evidence gates before implementation or release

1. Formalize the database-per-tenant identity ADR and assign accountable database/security/platform owners.
2. Approve the source-owned boundary and remove all direct foreign-tenant database sessions from runtime paths.
3. Prove effective PostgreSQL role membership, CONNECT, object privileges, ownership and privileged execution paths on supported versions.
4. Prove secret isolation, bootstrap, rotation, revocation, pool invalidation and no fleet-wide tenant-secret access.
5. Resolve CAN-02/CAN-03 selector privacy and routing authority.
6. Resolve import idempotency, fencing, destination commit, acknowledgement, pointer sync and quarantine semantics.
7. Resolve DBID-R74 through R81 with concrete authority/provider/platform decisions and independent verifiers.
8. Complete governance D-01–D-14 and independent clinical/privacy/legal/security/database/operations sign-off.
9. Run deterministic non-production synthetic-data tests against actual isolated identities and deployment-like boundaries.
10. Conduct a separate production deployment and disaster-recovery evidence review before any controlled pilot.

AUD-004 implementation remains blocked until the Critical and High items are resolved with objective evidence and independent sign-off.

## 12. Non-authorization and change control

This is a documentation consolidation only. It does not authorize runtime code changes, SQL, migrations, PostgreSQL role/ACL/network/secret changes, production or patient-data access, partner onboarding, trust provisioning, federation activation, emergency access, pilot, deployment, release or merge.

PostgreSQL **database-per-tenant** remains unchanged. Emergency federation remains disabled. All linked PRs remain draft/unmerged unless separately and explicitly authorized.


## 13. Recovery-design reference refresh — 2026-11-13 13:47 IST

Live GitHub metadata and file contents were re-fetched before this register update. PR #23 is still open/draft, based on PR #19's branch rather than `main`, at head `99719aeb5f8c24efc018f9886ca223ec03351355`; its design document blob is `a1b07e636ac7afb524612470f3c84cc340e86056`. PR #70 is still open/draft and main-based; this register update is being made against its current head. PR #19 remains the parent runtime-remediation PR. This refresh corrects the stale PR #23 head reference in Section 10; it does not represent independent review, implementation approval, merge approval, test execution or production evidence. PostgreSQL **database-per-tenant** remains unchanged. No runtime code, migration, database or production resource was changed.

## 14. Tenant identity and pointer-generation contract refresh — 2026-11-13

PR #23 design head is now 5fa4a7aa6ddd981a49c369e98dd141f0f95d0576 (design document blob de5f26e69d9a9d5f42ce8ba78c357ece1f7365fb). Section 11 proposes a dedicated immutable tenant UUID, monotonically increasing source-pointer generation, generation-bound discovery receipts, tombstone semantics, and canonical idempotency-key inputs. The existing TenantRegistry integer primary key remains intact; UUID supplements it. Existing database-per-tenant routing, branch codes and database names are not replaced.

These are proposed contracts, not approved decisions or implemented behavior. Required follow-up includes inventorying every pointer writer, defining tombstone retention and administrative repair authorization, resolving disaster-recovery identity reconciliation, and independently reviewing the migration/backfill and rollout plan. PR #23 remains draft and stacked on PR #19. No runtime code, migration, test execution, database query or production operation occurred in this update.
## 15. Federated pointer-writer inventory refresh — 2026-11-13

PR #23 now contains Section 12, a **partial** pointer-writer inventory based on read-only inspection of PR #19 head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`. It identifies the shared `sync_patient_pointer` insert/update/delete paths, the direct delete in `backend/domains/patients/router.py::deactivate_patient`, and the patient registration, update, allergy-charting, explicit publish and post-import call sites. It distinguishes source-identity mutations from summary/freshness refreshes and records the required tombstone treatment for privacy opt-out/deactivation.

PR #23 design head is now `051a11f281a05da7ef70a011d1d277033610c006` (design document blob `8143a788e27e6560cb03e5c3700311430774996c`). The inventory is expressly **not exhaustive**: this pass inspected targeted files, not all 334 Python files, and did not prove absence of raw SQL or indirect writes in other modules. A complete all-file scan, CI guard and independent review remain prerequisites before any generation migration or implementation.

Required next steps: complete repository-wide ORM/raw-SQL writer enumeration; centralize pointer mutations; define whether searchable identity changes invalidate receipts; replace physical-delete-only invalidation with durable tombstones; and prove cross-database retry/reconciliation for each patient lifecycle call site. No runtime code, migrations, database operations, tests or production resources were changed. PR #23 remains draft/stacked on PR #19; PR #70 remains draft/main-based; PR #19 remains open/blocked. PostgreSQL **database-per-tenant** remains unchanged.
## 16. Pointer revocation and stale-index findings — 2026-11-13

Deeper inspection of `sync_patient_pointer` and its callers in PR #19 identified additional correctness gaps recorded in PR #23 Section 12.5:

- A denied `federation.patient.publish_pointer` data-use decision returns before patient opt-out and branch-isolation cleanup, so an existing pointer can remain published after disclosure is denied. The publish endpoint's 403 does not itself revoke it.
- `allow_network_sharing=False` is checked after the privacy decision; revocation must be processed as a restrictive action even when disclosure is denied.
- `EMERGENCY_ALLERGIES_ONLY` can return without removing an existing non-critical pointer, and the `has_critical_allergies or pointer.has_critical_allergies` update prevents a previous critical flag from clearing.
- Pointer refresh currently uses an ordinary select/update without row locking or expected-generation fencing. Concurrent writers can overwrite newer state.
- PatientUpdate exposes phone and ABHA changes but not MRN; any MRN reassignment path outside this public route remains to be found in the full repository scan.
- Patient lifecycle routes commit tenant data before the control-plane pointer action, leaving split-commit stale-index windows if control-plane synchronization fails.

PR #23 Section 12.5 adds required tests for denied-policy revocation, opt-out, branch policy transitions, critical-allergy removal, concurrent refresh and cross-database failure recovery. These are repository-source findings, not runtime test results. PR #23 remains proposed/draft; no implementation, migrations, tests, database queries or production changes were performed. The all-file ORM/raw-SQL writer scan is still incomplete. PostgreSQL **database-per-tenant** remains unchanged.

PR #23 reference at this refresh: head `8a859dfe5b23e03dbb126bf8e8d3d577123ba7f0`; design document blob `23eef980164235eca0780c6af6054597c47ebdb2`. This is a documentation-only design update, not independent review or approval.

## 17. Pointer migration and receipt-retention constraints (2026-11-13)

Direct inspection of the PR #19 source commit (`0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`) confirms:

- Control-plane baseline migration `95769c3ab4b3_baseline.py` creates `global_patient_pointers` with uniqueness `(phone_hash, branch_code, source_mrn)` and no tenant UUID or pointer generation column.
- Control-plane migration `6c9f2a1d8b40_federated_discovery_receipts.py` gives `federated_discovery_receipts.source_pointer_id` an `ON DELETE CASCADE` foreign key to the pointer table.
- Physical pointer deletion can therefore cascade-delete linked receipt evidence. Any future tombstone, revocation and receipt-consumption design must preserve audit/recovery evidence independently of the pointer row and explicitly revise this FK/retention model.
- The other inspected control-plane migrations and migration router/catalog showed no additional pointer writers. This is a bounded control-plane/migration audit, not a completed all-repository writer inventory.

No runtime behavior or migrations were changed. PR #23 Section 12.6 records the design implication. Database-per-tenant remains the architecture; this finding does not authorize a topology change.
## 18. Additional pointer-writer inventory pass (2026-11-13)

A targeted pass inspected adjacent FHIR, ABDM, integrations and encounter routers/services; control-plane provisioning/fleet/network routers; patient service/break-glass modules; privacy decision/runtime/retention modules; and seed/restore scripts. No additional pointer ORM writes, raw table writes or `sync_patient_pointer` calls were found in those inspected files.

`backend/control_plane/api/routers/fleet_ops.py` reads `GlobalPatientPointer` for fleet counts and operator MPI lookup; the inspected route writes only a separate `ControlPlaneAuditLog` record. This is a read/audit path, not a pointer writer.

The known mutation paths remain the federation synchronization function and the direct patient-deactivation deletion path previously recorded. The all-file inventory remains incomplete: the majority of unrelated backend Python files and all raw-SQL matches have not been exhaustively scanned; GitHub code-search yielded no indexed results for the pointer symbols. Do not treat this targeted pass as proof that no other writer exists.
## 19. Tenant federation transfer-log retention is separate from discovery receipts (2026-11-13)

A targeted review of patient/privacy/identity/federation/FHIR/ABDM tenant migration files found no additional writes to the control-plane global pointer table or pointer-generation/tombstone migration. It did identify a separate tenant-local audit safeguard:

- `a7c4e9d2b615_federation_audit_node_attribution.py` adds requesting-node attribution to `federation_transfer_logs`.
- `f9b7c3d1e205_immutable_federation_transfer_logs.py` changes the patient FK to `ON DELETE RESTRICT` and installs a PostgreSQL trigger blocking update/delete of transfer-log rows.
- This immutable tenant-local transfer history must not be confused with control-plane `federated_discovery_receipts`. It does not provide pointer revocation tombstones or durable import operation recovery.

This was a targeted migration review, not an exhaustive scan of every migration/SQL statement. The all-repository pointer-writer inventory remains incomplete.
## 20. Deployment PostgreSQL role script does not establish tenant-isolated credentials

Inspection of `deployments/postgres-roles.sql` found that the documented role bootstrap is broad rather than tenant-scoped:

- `hms_app` is granted `CONNECT` on the literal database `postgres`, plus DML on all current tables and sequences in `public` and matching default privileges for future objects.
- `hms_migrator` receives `CONNECT, TEMPORARY` on `postgres`, all privileges on the `public` schema, all current tables/sequences, and broad default privileges.
- `hms_backup` is granted PostgreSQL's cluster-wide `pg_read_all_data` predefined role.

This script does not demonstrate a distinct runtime identity and least-privilege grant set per tenant database, nor a narrowly scoped control-plane identity. The literal `postgres` database grants also do not by themselves establish the intended tenant database grants. Treat this as deployment-RBAC evidence gap / high-priority design defect to resolve before production, not as proof of an exploitable deployed environment. Validate intended roles, memberships, ownership, `CONNECT` grants, default privileges, and actual credentials on a disposable PostgreSQL instance before proposing replacement SQL.

No role script or credentials were changed. This inspection was static; no PostgreSQL server was contacted.
## 21. PostgreSQL role bootstrap is invoked but not wired to runtime identities (2026-11-13)

Follow-up inspection confirms the role script is not merely an unused example: `docker-compose.prod.yml` runs `backend/scripts/bootstrap.py --apply-roles` in the one-shot `db-init` service. However, the resulting roles are not wired into the application, migration, provisioning, or backup connection paths:

- `bootstrap.py::apply_database_roles()` connects to the `postgres` database using `settings.POSTGRES_USER` / `settings.POSTGRES_PASSWORD` and executes `deployments/postgres-roles.sql`. The SQL creates `hms_app`, `hms_migrator`, `hms_backup`, and `hms_exporter` with `LOGIN`, but assigns no passwords, does not grant membership/role switching to the configured runtime account, and does not configure per-tenant database ownership or grants.
- The SQL grants `hms_app` and `hms_migrator` on the literal `postgres` database and the `public` schema there. It does not loop through or grant `CONNECT`/object privileges on the control-plane database and each tenant database. `hms_backup` receives `pg_read_all_data` (cluster-wide read access) but no credential is configured for the backup process.
- `docker-compose.prod.yml` supplies `.env.production` to the API, onboarding portal, worker, HL7 listener, and `db-init`. The environment exposes one `POSTGRES_USER` / `POSTGRES_PASSWORD` pair, not separate control-plane, tenant-runtime, migration, and backup identities.
- `backend/core/config.py::DATABASE_URL`, `backend/core/database.py::build_db_url()`, the control-plane engine, and `TenantEngineRegistry` all retain the same configured username/password while changing only the database name.
- `backend/control_plane/api/routers/provisioning.py` creates tenant databases, runs migrations, and seeds them with URLs from that same builder; it does not transfer ownership or grant access to `hms_app`/`hms_migrator` afterward.
- `backend/scripts/migrate.py` migration engines receive the supplied URL directly. `backend/scripts/backup_service.py::_dump_and_encrypt()` invokes `pg_dump` with `settings.POSTGRES_USER` and `settings.POSTGRES_PASSWORD`. `backend/scripts/restore_tenant.py` uses the same configured login for database creation and `pg_restore`.

Therefore, the role bootstrap currently creates nominal role objects but does not enforce the claimed least-privilege separation. The application continues to use the shared configured database identity for control-plane and tenant access, and backup/migration paths do likewise. This is a repository-level critical/high-priority AUD-004 isolation gap. The exact effective privilege of a deployed `POSTGRES_USER` still depends on how the PostgreSQL cluster and that login were initialized; static repository evidence alone does not prove the live role is a superuser or establish deployed exploitability.

Required remediation evidence before production: define separate CP runtime, tenant runtime, migration, backup, and provisioning/bootstrap identities; explicitly scope grants/ownership and default privileges across the control-plane and each tenant database; ensure tenant provisioning assigns the tenant runtime/migration roles safely; use backup credentials with only the intended database read scope; remove broad `pg_read_all_data` unless separately justified; then prove with disposable PostgreSQL tests that each identity can access only its intended database and cannot cross-read/write another tenant. Do not implement this by changing the database-per-tenant topology.

No SQL, credentials, Compose configuration, or runtime code was changed. This was a static source review; no live PostgreSQL instance was contacted.
## 22. Existing disposable ACL proof is a useful target, not production wiring evidence

PR #71 (`security/aud004-disposable-postgres-proof`, head `ae28c153abd4ada2a257fa360c699c24acc3bb0c`) provides the right synthetic test shape: three distinct non-superuser logins, separate probe containers with only their own secret pair, positive own-database access, explicit cross-database `CONNECT` denial, and assertions for superuser/CREATEDB/CREATEROLE/replication/BYPASSRLS flags, role memberships, and PUBLIC privileges. Its recorded workflow run `43364452642` passed 27 ACL assertions (9 per identity) and 10 reconciliation tests on that exact head.

That evidence is still a fixture-level proof. It does not exercise the production `bootstrap.py` role script, the actual `Settings.DATABASE_URL`/`build_db_url()` connection construction, Compose-provided application credentials, provisioning/migration role handoff, or backup/restore logins. The next implementation proof must test the actual production role/bootstrap configuration against a disposable PostgreSQL cluster and prove that the real app, control-plane, migration, provisioning, and backup identities each have only their intended database access. It must also verify that a tenant A application login cannot connect to tenant B or control-plane DB, and vice versa, while each service's intended functions continue to work.

Do not treat the 27 synthetic assertions as closing the production role-wiring finding. PR #71 remains draft/unmerged; no production or application runtime was changed.
## 23. Bootstrap ordering and role-script execution semantics (2026-11-13)

Further source tracing establishes the exact production startup sequence:

1. `docker-compose.prod.yml` starts `db-init` with the complete `.env.production` and runs `python backend/scripts/bootstrap.py --apply-roles`.
2. `bootstrap_system()` calls `provision_physical_databases()` first, then `apply_database_roles()`, then upgrades the control-plane database and (for a newly created default tenant) the tenant database.
3. `apply_database_roles()` opens a connection to the literal `postgres` database using `POSTGRES_USER` / `POSTGRES_PASSWORD`, and executes the entire `deployments/postgres-roles.sql` script on that connection.
4. The SQL grants object privileges only on the `postgres` database's `public` schema and database. It does not connect to the configured control-plane DB or any tenant DB.
5. `ControlSessionLocal`, `build_db_url()`, tenant migration engines, provisioning, and the backup/restore helpers continue using the shared configured login; no `hms_app`, `hms_migrator`, or `hms_backup` credentials are selected by these paths.

Additional role-script correctness gaps:

- Role creation is guarded by `IF NOT EXISTS`; existing roles are not reconciled with the declared attributes, passwords, or membership policy. A prior role with unsafe attributes would remain unchanged.
- The four roles are created with `LOGIN`, but this script does not set passwords or provision secret files for them. The disposable PR #71 harness's per-service secret pairs are not connected to these role definitions.
- The `ALTER DEFAULT PRIVILEGES` statements execute as the bootstrap connection's current role and in the `postgres` database context. They do not establish default privileges for objects created by `hms_migrator` in each control-plane/tenant database.
- The `hms_backup` grant of `pg_read_all_data` is cluster-wide by design; it is not the least-privilege, per-database backup identity implied by the role-script header.

These facts reinforce the prior high-priority/critical repository finding: the role bootstrap runs, but does not implement the advertised isolation. The actual power of `POSTGRES_USER` remains dependent on the external PostgreSQL initialization and live grants; static review does not establish that production login's effective role attributes.

### Required disposable-cluster proof before changing runtime

Use a fresh PostgreSQL 17 disposable cluster and run the exact production `bootstrap.py --apply-roles` path with synthetic-only credentials. Capture SQL role attributes, role memberships, database ACLs, schema/table/sequence grants, object ownership, and default privileges before and after bootstrap. Exercise both first-run and rerun cases, including pre-existing roles with deliberately unsafe attributes. Assert the current behavior first so the gap is reproducible; then design the intended role model separately.

After an approved remediation design, repeat the proof with distinct CP runtime, per-tenant runtime, migration, backup, and provisioning identities. Test positive intended access and explicit negative cross-database access, including tenant A to tenant B and CP, tenant B to tenant A and CP, CP to tenant databases, and backup scope. Verify migrations and provisioning can perform only their approved operations, and verify backup can read/restore only its approved database set. The proof must test the actual Compose service environment/secret mounts and production bootstrap code, not just hand-created synthetic roles.

No runtime, Compose, SQL, credentials, or database topology changes were made. No live PostgreSQL server was contacted; this section records static source findings and a proposed disposable-only evidence plan.
## 24. Production Compose startup gate: `db-init` performs full bootstrap, not a role-only task (2026-11-13)

The exact `db-init` service definition in `docker-compose.prod.yml` is:

- Image: `avinya-hms-api:${VERSION:-v4.5.0}`.
- Environment: full `.env.production` via `env_file`, plus timezone settings.
- Command: `python backend/scripts/bootstrap.py --apply-roles`.
- Dependency: PostgreSQL `db` must be healthy.

The `api`, `worker`, `hl7-listener`, and `onboarding-portal` services declare `db-init` with `condition: service_completed_successfully`. Consequently, the role-application command is also a startup gate for those services: a failure anywhere in the complete bootstrap prevents dependent services from starting.

Important execution detail: `main()` passes `apply_roles=True` into `bootstrap_system()`, but that flag does not return after `apply_database_roles()`. The function continues to:

1. Ensure the control-plane and default-tenant physical databases exist.
2. Apply the role SQL if requested.
3. Upgrade the control-plane database.
4. Seed control-plane data and create the default tenant registry entry if absent.
5. In development/testing, migrate and seed all active cloud tenants; in production, migrate/seed the default tenant only when it was newly created, otherwise skip existing tenant upgrades.
6. In non-development environments, validate tenant database URLs for active cloud tenants.

Therefore `db-init` is not a narrowly scoped PostgreSQL role initializer. It runs the full environment-sensitive bootstrap workflow with the shared production environment. Any disposable proof that invokes `bootstrap.py --apply-roles` must isolate the entire bootstrap side-effect surface, not merely point the role SQL at a disposable server and assume the command exits after role creation. The safest first proof target is the exact `apply_database_roles()` function in a disposable cluster, with environment overrides and explicit before/after catalog assertions; separately test `bootstrap_system()` sequencing with stubbed migration/seed dependencies or a fully disposable end-to-end fixture.

Security and operational implications:

- The production API startup is coupled to control-plane migration/seed/tenant-validation success, not just role creation.
- The bootstrap container receives the same `.env.production` values as the other services; the dedicated role credentials are not injected or selected by this path.
- The current `apply_database_roles()` implementation does not provision the role passwords needed to authenticate as the newly created roles.
- Do not execute the full `bootstrap.py --apply-roles` against any shared, developer, staging, or production database as part of this proof.

No runtime, Compose, SQL, credentials, or database topology changes were made. This is a static source trace; no PostgreSQL cluster was started and no bootstrap function was executed.

## 25. Test-only execution proof added to PR #71 (2026-11-13)

PR #71 now contains `deployments/aud004-proof/test_production_role_bootstrap.py` and an `aud004-production-role-bootstrap-proof` job in `.github/workflows/on-demand-validation.yml`.

The test parses `backend/scripts/bootstrap.py`, extracts the exact production `apply_database_roles()` function AST, compiles and executes that function body with only its external settings/connection/logger dependencies supplied, and points it at a fresh GitHub Actions PostgreSQL 17 service. It reads and executes the exact repository `deployments/postgres-roles.sql` through the production function. The full `bootstrap_system()` function is deliberately not invoked, so migrations, seeding, provisioning and tenant validation cannot run.

The test is intentionally a characterization proof of current behavior, not a passing least-privilege acceptance test. It checks that:

- A fresh run creates all four declared roles, with the declared restrictive role flags but with no passwords configured.
- The `hms_backup` membership in `pg_read_all_data` is present.
- On a fresh PostgreSQL cluster, `hms_app` can connect to tenant/control-plane databases through PostgreSQL's default PUBLIC CONNECT ACL; the production role SQL does not revoke that default or scope those database grants.
- A deliberately pre-existing unsafe `hms_app` role (`SUPERUSER CREATEDB CREATEROLE`) remains unsafe after rerunning the production function because role creation is guarded by `IF NOT EXISTS` rather than reconciliation.

Safety boundary: the workflow uses only an ephemeral GitHub Actions PostgreSQL service, a fixed synthetic CI-only setup password, and synthetic database names. It does not read `.env.production`, mount production secrets, contact any shared database, or run the complete HMS bootstrap.

Execution evidence (2026-11-13): workflow-dispatch run [43406334294](https://github.com/Perseus37/avinya_hms_v2/actions/runs/43406334294) completed successfully on PR #71 head `d9fa717849b672b1ff768915d9aa252d49916c0d`. The production role-bootstrap proof job passed; its log reports `1 passed in 0.16s`. The reconciliation regression job and the separate disposable PostgreSQL workload-isolation proof also passed. Frontend production builds and Docker Compose validation were skipped by the selected `reconciliation` scope. The preceding run on the earlier harness commit failed because database creation occurred inside a transaction; PR #71 corrected the harness to enable autocommit before entering the connection context, and the rerun passed.

Interpretation: this successful test confirms the characterization assertions above on a disposable PostgreSQL 17 cluster. It reproduces the current ACL/role-policy gaps; it is not a least-privilege acceptance test and does not establish corrected behavior, application connection wiring, per-tenant migration ownership, backup scoping, or provisioning handoff.

No production runtime, SQL, Compose deployment configuration, credentials, or database topology were changed.

## 25.1. Harness execution-environment correction (2026-11-13)

Two harness-only execution defects were identified and corrected before the successful run:

1. The extracted production `apply_database_roles()` function references `ISOLATION_LEVEL_AUTOCOMMIT`; PR #71 injects that symbol from `psycopg2.extensions` into the isolated namespace (commit `71a9d95f64c802448cb0e25a5277a5c4be95ef93`).
2. The first execution attempted `CREATE DATABASE` inside a psycopg2 connection context, which opened a transaction despite setting `conn.autocommit = True` inside the context. The harness now sets autocommit before entering the cursor/context and closes the connection explicitly (commit `d9fa717849b672b1ff768915d9aa252d49916c0d`).

The corrected harness passed in workflow run [43406334294](https://github.com/Perseus37/avinya_hms_v2/actions/runs/43406334294), on the exact corrected PR #71 head. The role-bootstrap test log reports `1 passed in 0.16s`; see Section 25 for the full run and interpretation. This confirms the characterization test executed successfully; it does not resolve the production least-privilege gaps it intentionally demonstrates.

No production runtime, SQL, Compose deployment configuration, credentials, or database topology were changed.
## 26. PostgreSQL least-privilege remediation contract — proposed, not approved (2026-11-13)

A new design-only companion document, [`AUD004_POSTGRESQL_LEAST_PRIVILEGE_REMEDIATION_CONTRACT.md`](AUD004_POSTGRESQL_LEAST_PRIVILEGE_REMEDIATION_CONTRACT.md), defines the target PostgreSQL identity, ACL, workload, credential-lifecycle, provisioning, migration, backup/restore and disposable-cluster proof requirements.

The contract preserves PostgreSQL **database-per-tenant** and defines the core access matrix: control-plane runtime to CP only; each tenant runtime/source identity to its own tenant DB only; backup scoped to an assigned DB; migration and provisioning identities short-lived and explicitly scoped; destination import has no foreign source DB credential or session capability. It prohibits a tenant-facing fleet credential bundle, cluster-wide `pg_read_all_data` as the default backup model, and reliance on database names as authorization.

It makes PostgreSQL `PUBLIC` CONNECT/TEMP revocation and explicit per-database grants a required design target, with object ownership/default privileges configured in each database for the actual creator role. It also requires catalog-wide membership/ACL/ownership/function inspection, effective-privilege probes using independent logins, and disposable PG positive/negative tests for CP, tenant A/B, provisioning, migration, backup and restore.

Important design caveat: the contract does not select final literal role names, secret manager, workload identity provider, backup topology or supported pooler/platform profile. Those remain owner decisions. The existing PR #71 test is characterization evidence of the current behavior, not acceptance evidence for this target.

PR #70 remains open/draft/unmerged. This document is proposed and requires DBA, application-security, platform and operations review. No SQL, runtime, migrations, Compose, credentials, live database, patient data, production rollout or federation activation changed or was authorized.
## 27. Workload-to-database identity implementation map (2026-11-13)

The least-privilege contract now includes a repository-grounded workload map in Section 13, based on static inspection of the production Compose manifest, settings/database engine construction, tenant provisioning, migration, backup, restore and bootstrap paths on `main`.

Key result: the current single API process uses shared database credentials for both control-plane and tenant sessions; `TenantEngineRegistry.get_engine(db_name)` selects a database while retaining the same configured login. The control-plane onboarding service, worker, HL7 listener, API and `db-init` all receive the full `.env.production`. `postgres-exporter` also uses the shared `POSTGRES_USER`/`POSTGRES_PASSWORD`. Provisioning combines DB creation, migration and tenant initialization; backup and restore use the shared login. No dedicated backup service appears in the inspected production Compose service list.

This means role SQL alone cannot deliver the target isolation. A P0 architecture decision is required for the multi-tenant API credential boundary: tenant-bound process isolation, a tightly constrained credential broker, or another independently enforced design. The broker/process design must not become a fleet-wide credential oracle. Federation source reads, provisioning, migration, backup and restore require their own execution boundaries.

Static source revisions and the limits of this bounded inventory are recorded in Section 13. This is not a complete connection-consumer inventory and does not establish deployed grants, environment values, network policy or live sessions. No runtime, SQL, migration, Compose or secret changes were made. The contract remains proposed and PR #70 remains draft/open/unmerged.
## 28. Backup-sidecar and vault profile cross-check (2026-11-13)

A follow-up cross-check against the existing Section 11.2/11.18 findings in `AUD004_IMPLEMENTATION_READINESS_AND_OWNER_REGISTER.md` refined the service map: the development `docker-compose.yml` includes `backup-sidecar` and `backup-vault`, both loading `.env`; the sidecar runs the database-reading backup daemon, while the vault's file-copy mode does not require database or application secrets. The development Compose file also shares the read-write `hms_backups` volume among API, worker, onboarding and backup-sidecar; vault receives the source mount read-only and a separate vault volume.

The checked-in `docker-compose.prod.yml` does not declare those two services. This is a production deployment-profile gap to resolve, not evidence that no backup service runs in production. The actual production scheduler/container/host and its secrets/mounts must be identified and independently verified. The least-privilege contract now records this distinction and requires a credential-free vault identity, separated artifact write boundary, and effective volume/storage immutability tests.

No runtime, Compose, volume, credential or storage configuration was changed. Database-per-tenant remains unchanged; PR #70 remains draft/open/unmerged.
## 29. Additional PostgreSQL connection-consumer cross-check (2026-11-13)

The least-privilege contract Section 14 now records additional database access surfaces found in a targeted static review of the queue, integration listener, control-plane fleet/migration routes, maintenance CLI, restore drill and host-level backup/restore scripts.

Newly explicit access paths:
- `backend/core/queue.py` obtains tenant engines for queued work; queued tenant/database selectors must be bound to a server-owned authorized job, not trusted as arbitrary routing input.
- `backend/domains/integrations/listener.py` reads CP metadata and obtains tenant engines; integration execution must be tenant/interface-bound.
- `backend/control_plane/api/routers/fleet_ops.py`, `backend/control_plane/api/routers/migration.py` and `backend/control_plane/app.py` expose tenant engine access from CP-side surfaces. CP runtime cannot be considered CP-only while it can instantiate this shared registry.
- `backend/scripts/build_indexes_concurrently.py` is an additional privileged maintenance/DDL surface.
- `backend/scripts/restore_drill.py` is an additional DR/admin surface.
- `deployments/backup-postgres.sh` uses configured PostgreSQL credentials for database inventory, `pg_dump` and global-role dump; `deployments/restore-postgres.sh` uses the configured login to create an owned target and restore it. These host scripts are distinct from the Python backup/restore paths.

Result: the shared tenant engine registry is reachable beyond the primary API request path, and backup/restore has multiple distinct execution surfaces. Migration also spans bootstrap/migrate scripts, CP routes/fleet operations and maintenance CLI. These require separate workload identity and negative-test coverage; changing role SQL or the primary API configuration alone cannot close the boundary.

Scope remains a targeted static cross-check, not a complete proof of every repository connection consumer or deployed access. Contract Section 14 records source blob SHAs and explicit limitations. No code, SQL, migration, Compose, secret, database, patient data or production setting changed. PR #70 remains draft/open/unmerged.
## 30. Tenant-engine call-site classification (2026-11-13)

The PostgreSQL least-privilege contract Section 15 now classifies the inspected direct `tenant_engine_pool.get_engine()` call sites in core request handling, privacy queue jobs, HL7 ingress, CP fleet/support routes, CP migration routes and federation.

Key conclusions:
- Tenant selection by `db_name` is not authorization. The shared registry is a capability amplifier because callers can choose a database while using the same configured credential.
- The request dependency is a required tenant runtime path, but must be tenant-bound to the authenticated/resolved tenant and must not have fleet-wide credentials.
- The privacy scheduled sweep is a fleet scheduler and should enqueue tenant-bound work rather than scan every tenant DB using a fleet credential.
- CP fleet routes directly access tenant clinical data for metrics/telemetry, federation key rotation, emergency password reset, sandbox cloning, schema parity/sync, policy reads and fleet summaries. These require minimized projections or distinct delegated operations.
- CP CSV migration preview/background writes require tenant-bound import workers.
- Federation discovery and source-side import reads are cross-tenant access paths; source data release must execute inside the source tenant boundary, while destination writes use destination identity.

Section 15 records the call-site table, classifications and negative-test acceptance criteria. This confirms that the next architecture decision is workload/process isolation (or a rigorously constrained broker), not simply a replacement role SQL file. No runtime, SQL, migration, Compose, credentials, database, patient data or production setting changed. PR #70 remains draft/open/unmerged.

## 31. Compose workload topology and minimum isolation boundaries (2026-11-13)

The least-privilege contract Section 16 now maps the checked-in development and production Compose services, Dockerfile entrypoints, bootstrap behavior, exporter configuration and host backup/restore scripts to their required database identities and workload boundaries.

Key findings:
- Production `api`, `worker`, `hl7-listener`, `onboarding-portal` and `db-init` all receive the same `.env.production`; they are separate containers but not separate PostgreSQL credential boundaries.
- The onboarding portal is not CP-only today: inspected CP fleet/support/migration routes can instantiate the shared tenant engine registry.
- The API and worker mount the shared backup volume read-write; onboarding also mounts it read-write. These are unnecessary by default for the intended workload boundaries and require explicit justification.
- Production `postgres-exporter` uses the shared `POSTGRES_USER`/`POSTGRES_PASSWORD` rather than a dedicated monitoring identity.
- Production Compose does not declare the development `backup-sidecar` or `backup-vault`; host backup/restore scripts are separate execution paths. The actual production scheduler, host, secrets and storage isolation remain unverified.
- Important bootstrap behavior: production runs `bootstrap.py --apply-roles`, but the inspected `bootstrap_system(apply_roles=True)` continues after role application into physical DB provisioning, CP/tenant migrations and seeding. This is not a roles-only command.

Section 16 defines the current-to-target matrix for DB, API, CP portal, worker, HL7 ingress, db-init, exporter, development backup/vault services, host backup/restore, Redis and non-DB-facing services, plus the minimum safe implementation sequence. It explicitly retains PostgreSQL **database-per-tenant**.

Disposition: this is static repository evidence and a proposed topology contract, not proof of deployed environment, actual grants, production scheduler, host controls, network policy or runtime secret isolation. No Compose, Dockerfile, runtime, SQL, migration, credential, database, storage or production setting changed. PR #70 remains draft/open/unmerged.


## 32. Minimum target deployment topology and phased isolation plan (2026-11-13)

The least-privilege contract Section 17 defines a minimum privilege-separated deployment topology while retaining the modular monolith and PostgreSQL **database-per-tenant** architecture.

Target logical workloads:
- CP-only web runtime.
- Tenant clinical API with a server-validated tenant-bound DB capability.
- Tenant-bound background execution, separated from CP scheduling/dispatch.
- HL7 ingress without direct clinical DB credentials, delegating to a tenant-bound processor.
- Short-lived privileged operations runner for provisioning, role reconciliation, migrations and initialization.
- Dedicated backup/restore executor and artifact storage.
- Dedicated monitoring/exporter identity.
- Infrastructure services without broad tenant credentials.

The contract deliberately avoids a default container-per-tenant fleet and records two viable tenant execution patterns requiring an ADR:
- Pattern A: tenant-bound execution instances with access only to assigned tenant DB credentials.
- Pattern B: a constrained credential/connection broker with workload authentication, immutable tenant binding, operation allowlists, short-lived capabilities, replay protection, revocation, audit and pool invalidation. A shared process that can read all tenant passwords is explicitly not an acceptable broker.

Section 17 phases the work: design freeze; CP isolation; tenant execution isolation; ingress and privileged operations; backup/restore and monitoring; production readiness gate. It specifies independent PostgreSQL-session acceptance tests, queue/HL7 tampering tests, revocation tests, exporter restrictions and a verified restore drill.

Open decision: Pattern A versus Pattern B remains unresolved pending tenant-count, deployment-operations, threat-model and blast-radius analysis. No implementation, Compose, runtime, SQL, migration, secret, database, storage, patient-data or production change was made. No schema-per-tenant or microservices redesign is proposed.


## 33. Pattern A versus Pattern B tenant-execution decision (2026-11-13)

The least-privilege contract Section 18 now records a repository-grounded comparison of tenant-bound execution instances (Pattern A) and a constrained connection broker (Pattern B).

**Recommendation: Pattern A is the initial security baseline for the first cloud production cohort, on-prem tenant-dedicated deployments, and high-risk execution. Do not introduce Pattern B in the current remediation phase.** This is provisional pending architecture, DBA, security and operations approval; it is not implementation authorization.

Evidence behind the recommendation:
- The current shared API resolves tenant context and calls `TenantEngineRegistry.get_engine(db_name)`; `build_db_url` changes only the database name and retains the shared configured PostgreSQL login. The registry is an LRU engine cache (64 entries), not an authorization boundary.
- Production Compose gives the same `.env.production` to API, worker, HL7 listener, onboarding portal and db-init. Separate containers are therefore not separate DB identities today.
- Multiple non-request paths (queue, HL7, CP fleet/support/migration and federation) can reach tenant engines; isolating only the HTTP request path would leave cross-tenant access paths.
- No enforceable connection broker/proxy, workload-to-tenant capability protocol, per-tenant secret delivery, tenant-count forecast, hosting mix, or measured operating-cost baseline was established by the inspected repository.
- A password-vending service is not an acceptable Pattern B: the shared application could retain and reuse the returned credential. Pattern B must retain backend credentials inside an independently authenticated connection proxy, bind every checkout to immutable tenant and operation scope, partition/reset pools safely, and enforce revocation of active sessions.

Pattern A does not mean a permanent container-per-branch fleet by assumption. The implementation must define tenant-bound process/secret/pool/routing contracts and quantify the deployment footprint. Keep the modular monolith and PostgreSQL **database-per-tenant** architecture. Reopen Pattern B only after measured active/forecast tenant counts, peak concurrency/connection demand, per-tenant process cost, operational toil, hosting profiles, broker ownership/HA/DR plan and independent adversarial PostgreSQL proof are available.

Section 18 includes the comparative matrix, broker acceptance requirements, provisional decision, reconsideration evidence and implementation sequence. No runtime, SQL, migration, Compose, credential, secret, database, storage, patient-data or production change was made. PR #70 remains draft/open/unmerged.


## 34. Pattern A tenant-bound execution contract (2026-11-13)

The least-privilege contract Section 19 now defines the required tenant-bound execution contract for the recommended Pattern A architecture.

The contract requires an immutable server-assigned tenant identity bound to one canonical tenant database, one execution-unit identity, one tenant-specific credential reference, one privilege class and a versioned/revocable binding generation. Existing `TenantRegistry.id` is an integer primary key; whether it remains the canonical immutable identity or is replaced by a UUID is explicitly an ADR/migration decision, not assumed.

It defines the target HTTP flow: trusted ingress maps host to active tenant metadata; requests reach only the assigned tenant execution unit; the unit validates user/session tenant identity against its own binding and opens only its configured DB. Host, JWT slug, header override, request tenant ID and database name remain selectors, never authorization. Unknown/inactive/mismatched/stale tenant routing fails closed.

Process and secret requirements: one tenant DB credential reference per tenant clinical execution unit; no fleet credential enumeration, CP write access, DDL, backup or cluster privilege; independent workload identity, protected secret delivery, no shared fleet-wide secret map. The repository does not yet establish a tenant-specific PostgreSQL credential store/secret manager. Existing encrypted tenant JWT/HL7 secrets are not PostgreSQL credentials.

The contract also defines:
- Tenant-specific PostgreSQL login and grants limited to the assigned DB and approved runtime operations; explicit PUBLIC ACL, role membership, ownership and existing-session verification.
- Authenticated, expiring, audience-bound, generation-bound job envelopes; CP-only scheduler/dispatcher; tenant-bound workers; no trust in queue-supplied slug/DB name; no synchronous execution fallback from CP/API when queue is unavailable.
- HL7 ingress without clinical DB credentials and tenant-bound processing; source-owned federation reads and destination-owned writes.
- Auditable tenant disablement, credential rotation, queue cancellation/quarantine, active-session termination, pool disposal and bounded revocation propagation.
- Automated tenant-bound replicas, measured resource/connection budgets, signed/versioned recovery bindings and restore validation before tenant cutover.
- Adversarial routing, PostgreSQL, queue, HL7, federation, rotation, revocation, outage and recovery tests.

Open implementation decisions include canonical tenant identity and migration, host-to-execution routing topology, secret/workload identity provider, per-tenant role/ownership model, process orchestration and scale, durable queue/capability/idempotency protocol, revocation SLA, CP metadata delivery and on-prem profile.

Section 19 is a design and verification contract, not runtime implementation authorization. No runtime, queue, listener, router, SQL, migration, Compose, credential, secret, database, patient-data or production change was made. PostgreSQL **database-per-tenant** remains invariant. PR #70 remains draft/open/unmerged.


## 35. PostgreSQL tenant role and credential lifecycle contract (2026-11-13)

The least-privilege remediation contract Section 20 now defines a proposed role/credential lifecycle for PostgreSQL **database-per-tenant** under Pattern A. It is a design and test contract only; no SQL/runtime/Compose/migration/secret change was authorized.

Repository-grounded gaps recorded in Section 20:
- Current `postgres-roles.sql` creates roles only when absent, does not reconcile drifted attributes, gives `hms_backup` cluster-wide `pg_read_all_data`, and applies app/migrator grants to the literal `postgres` database rather than CP and tenant DBs. It does not establish per-tenant ownership, PUBLIC ACL revocation or credential handoff.
- Bootstrap, DB provisioning, migration and tenant initialization use the shared configured PostgreSQL login. `bootstrap.py --apply-roles` is not roles-only: it continues into database provisioning, CP migration/seeding and tenant migration/initialization/validation paths.
- Host backup/restore scripts use `POSTGRES_USER`, not `hms_backup`; backup performs both tenant DB dumps and a distinct cluster globals dump. Restore creates an isolated target owned by the restoring login and uses `--no-owner --no-acl`, so intended ownership/ACL normalization is not yet explicit.

Target role classes are separated into short-lived cluster provisioner, per-database NOLOGIN owner, CP runtime, per-tenant runtime, scoped migration, tenant-scoped backup, isolated restore, and monitoring/exporter identities. The contract defines explicit database creation/ownership/PUBLIC ACL/grant/default-privilege lifecycle, role reconciliation, credential issuance, bounded rotation/revocation, backup/global-export separation and restore verification before cutover.

Section 20 adds an independent-login disposable-PostgreSQL proof matrix covering CP vs tenant A/B, PUBLIC and inherited privileges, ownership/default ACLs, reconciliation after drift, scoped migrations, backup, isolated restore, active sessions and credential rotation. Existing PR #71 remains characterization evidence of current behavior, not acceptance evidence.

Open decisions require DBA/security/platform/operations approval: exact role/ownership model, object privilege inventory, secret provider/workload identity, provisioner operation model, backup/global export strategy, rotation/revocation SLA and safe decomposition of bootstrap. PR #70 remains draft/open/unmerged. No production change or tenant topology change was made.


## 36. Initial application PostgreSQL privilege inventory (2026-11-13)

The least-privilege remediation contract Section 21 now records a source-grounded initial inventory of database operations by workload. It distinguishes ordinary SQLAlchemy ORM DML from privileged provisioning, session termination, database-template cloning, migrations, concurrent index maintenance, backup, restore, fleet support, HL7 and federation execution.

The initial ordinary runtime baseline is database-local and table-scoped: CP runtime connects only to CP; each tenant runtime connects only to its assigned tenant DB; mutable application tables receive only required CRUD; immutable audit/ledger evidence receives SELECT/INSERT only; generated sequences receive USAGE/SELECT where needed. Runtime does not receive DDL, ownership, CREATEDB, PG_SIGNAL_BACKEND, TRUNCATE, role administration, cluster-wide monitoring/data-read roles or backup/restore capability by default.

Section 21 identifies append-only/immutable table families in inspected migrations: CP audit logs, federation transfer logs, security audit export register, supplier payments/allocations, bank statement batches/lines/matches, purchase returns/items, patient-indent issue allocations/return events, reconciliation investigation events, notification configuration events and reconciliation governance reports. It notes that CP audit immutability is currently an ORM event rather than a DB trigger, so DB ACLs are required to prevent raw SQL mutation.

Privileged operations requiring separate identities include CREATE DATABASE, `pg_terminate_backend`, template clone, tenant/CP Alembic DDL, concurrent index DDL, `pg_dump`, cluster-global export and restore. The document records migration advisory-lock and trigger/function needs, and the remaining backup/restore completeness proofs.

**Limitations:** this is an initial source-grounded inventory, not a complete route-by-route or model-wide query certification and not proof of deployed permissions. Exact grants remain blocked on metadata/query inventory, full append-only table discovery, independent PostgreSQL login tests, backup/restore proofs and DBA/security approval. No implementation or production changes were made. PR #70 remains draft/open/unmerged.


## 37. Source-declared SQLAlchemy object inventory (13 Nov 2026)

**Status:** First-pass static declaration inventory added to the AUD-004 least-privilege contract, Section 22. This is not an executed `MetaData` dump or live PostgreSQL catalog proof.

- Tenant registry: `backend.core.database.Base`; tenant Alembic explicitly imports 23 model modules: ABDM, audit, billing, blood bank, clinical, diagnostics, encounters, facility, federation, finance, identity, insurance, integrations, patients, pharmacy, policies, privacy, procurement, quality, reports, service operations, surgery and workforce.
- CP registry: `backend.control_plane.models.ControlBase`; CP Alembic targets only `ControlBase.metadata`.
- Static literal extraction found tenant model table declarations across those 23 modules and 11 CP table declarations: `tenant_registry`, `federated_nodes`, `global_patient_pointers`, `control_plane_audit_logs`, `tenant_snapshots_registry`, `module_catalog`, `bundle_catalog`, `blueprint_catalog`, `migration_schemas`, `control_plane_operators`, `control_plane_operator_sessions`.
- Enum classes are declared in multiple tenant modules and three CP enum classes. No explicit SQLAlchemy `Sequence(...)` declaration was found in the scanned model files; autoincrement does not establish exact PostgreSQL sequence names or SERIAL versus identity implementation.
- Source model inventory is not an operation-level privilege matrix. It does not prove runtime access, complete migrated object coverage, live ownership/ACLs, sequence/type names, views, functions, extensions, triggers or handwritten migration objects.
- Next evidence gate: deterministic metadata extraction from the exact Alembic import graph; disposable PostgreSQL migration; source-to-catalog diff for relations, sequences, enum/domain types, functions, triggers, views, extensions, ownership, ACLs, default ACLs, role memberships and PUBLIC; route/worker/listener/script-to-object operation map; independent-session positive and negative privilege tests.
- No grant SQL, model, migration, runtime, Compose, credential, secret, database or production configuration changed. Database-per-tenant remains the architecture invariant.

Contract: Section 22 in `AUD004_POSTGRESQL_LEAST_PRIVILEGE_REMEDIATION_CONTRACT.md`.


## 38. Route/worker/listener database-operation map — first-pass source trace (13 Nov 2026)

**Status:** A bounded route-level trace has been added as Section 23 of the least-privilege contract.

- Confirmed tenant API router registration across the principal clinical, patient, identity, billing, diagnostics, pharmacy, insurance, surgery, blood bank, finance, integrations, procurement, privacy, workforce, ABDM, quality and related domains in `backend/main.py`.
- Confirmed the separate CP app registers fleet operations, pricing, migration, provisioning, SaaS billing, UI, network and operator authentication. Separation of FastAPI apps does not establish database capability isolation.
- Fleet routes directly access tenant engines for telemetry/analytics, key rotation, admin reset, schema status/sync, federation policy and sandbox clone. Clone performs `CREATE DATABASE ... WITH TEMPLATE` and terminates source connections; sync invokes tenant migrations. These require isolated tenant-bound or privileged runners, not CP web credentials.
- CP CSV mapping preview reads tenant rows; execution dynamically selects target models and writes tenant rows. Requires a constrained tenant-bound import worker with explicit table/field allow-list and durable operation state.
- Federation discovery/import currently spans CP pointer metadata, source tenant reads and destination tenant writes. Source release and destination import must be separate tenant-bound capabilities.
- Queue has email, retention execution and daily retention scheduler handlers. Scheduler should be CP-only; retention execution must be bound to one tenant and its actual service/table operations still need tracing.
- HL7 listener tenant routing and ORU writes remain a separate ingress/processor boundary; facility/interface identity must be trusted before tenant binding.
- Initial operation matrix and exclusions are in Contract Section 23. It is explicitly incomplete: remaining tenant domain routers/services, retention call graph, HL7 processor, payment and workflow paths, outbox workers and scripts still require tracing.
- No grant SQL or code/SQL/migration/Compose/credential/secret/database/production changes were made. Database-per-tenant remains the invariant.

Next gate: complete tenant-domain router/service call graph and map every table to SELECT/INSERT/UPDATE/DELETE/raw SQL per execution identity; then build disposable PostgreSQL independent-session privilege tests. Do not draft final grant SQL before this mapping is complete.


## 39. Tenant-domain route/service operation trace — second source batch (13 Nov 2026)

**Status:** Contract Section 24 adds a bounded, evidence-backed sample of billing, pharmacy, diagnostics, privacy-runtime, HL7 and queue paths.

- Billing invoice creation reads patient/optional encounter and inserts an invoice; line addition reads/locks invoice and service catalog, inserts line items and updates invoice totals; draft line removal performs SQL DELETE plus invoice UPDATE. The invoice listing/export path also invokes privacy evaluation and audit writes.
- Pharmacy formulary deactivation is an HTTP DELETE route but performs SQL UPDATE of `is_active`; inventory receipt inserts batches after reading medication master. This confirms privilege mapping must follow emitted SQL, not HTTP verb names.
- Diagnostics catalog create/list/update/deactivate paths expose SELECT/INSERT/UPDATE patterns; deactivation is an UPDATE. Diagnostic order/task and auto-billing paths remain incomplete.
- Privacy runtime adds transitive patient, consent and policy reads plus decision-audit writes to routes such as billing. A route's direct model imports are not a complete privilege map.
- HL7 listener currently reads CP tenant configuration and then obtains a tenant engine for result processing. The processor's exact writes remain to be traced; this reinforces the separate ingress-resolver and tenant-bound processor requirement.
- Queue enqueue defaults to `sync_fallback=True`; on Redis failure, the producer may execute a registered handler inline. This can transfer worker DB requirements into the producer process and must be represented in workload mapping.
- The source trace is bounded, not exhaustive. It does not prove all ORM cascades, emitted SQL, raw/bulk statements, DB trigger effects or deployed ACLs. No final grant SQL can be generated from this sample.
- Next gate: finish pharmacy/diagnostics/billing handlers, retention and worker call graphs, remaining tenant domains, then capture actual statements against disposable migrated PostgreSQL and test per-workload grants with independent sessions.

No runtime/SQL/migration/Compose/credential/secret/database/production change. PostgreSQL database-per-tenant remains invariant.

Contract: Section 24 in `AUD004_POSTGRESQL_LEAST_PRIVILEGE_REMEDIATION_CONTRACT.md`.


## 40. Tenant-domain mutation and worker trace — third source batch (13 Nov 2026)

Contract Section 25 adds source-backed operation evidence:

- Diagnostic order placement reads patient/catalog/bundle data, inserts order/tasks and calls auto-billing; cancellation updates order/task state and invokes billing reversal. Task result submission updates task state/results and invokes clinical delta-check logic. Delta configuration has SELECT/INSERT/UPDATE behavior.
- Controlled-substance movement locks and reads the vault, optionally reads encounter/prescription/witness records, updates the mutable vault balance and inserts a movement-log event. The ledger is trigger-protected and must remain SELECT/INSERT-only for runtime.
- Supplier payment execution reads/locks payment request, vendor, invoices and expenses; inserts payment and allocation ledger rows; updates invoice, expense and request state. The payment/allocation ledgers are append-only trigger-protected; do not grant their UPDATE/DELETE.
- Privacy evaluation reads active policy, patient and consent data and writes decision-audit rows using Core executemany INSERT. This is a transitive write dependency of routes that perform privacy preflight.
- Daily retention scheduler currently reads CP tenant registry and then opens every tenant DB to read approved retention policy before enqueuing. The execution handler resolves a tenant from payload via CP, reads approved policy and user rows, then invokes category-specific retention service. This is not the intended CP-only scheduler/tenant-bound executor split. Destructive retention service operations remain untraced; no destructive execution was run.
- Billing auto-charge helpers read clinical/bed/blood-bank relationships and create/update draft invoice lines; reversal helpers can DELETE matching draft invoice lines. Clinical callers inherit these transitive billing requirements.
- The trace is still incomplete; it does not prove exact physical names, all ORM cascades, raw SQL, trigger effects, or deployed grants. No final grant SQL is approved.

Next gate: trace retention service, pharmacy dispense/return/BCMA, diagnostic delta-check, procurement reconciliation/returns/indents, billing payment/refund/RCM and remaining worker/domain paths. Then use disposable PostgreSQL statement capture and independent-login privilege tests.

No runtime/SQL/migration/Compose/credential/secret/database/production change. PostgreSQL database-per-tenant remains invariant.


## Section 26 — Retention, clinical delta-check, pharmacy, procurement and RCM transitive database operations

**Scope and confidence.** Source review of the current branch only. This section extends the source-grounded operation map; it is not a complete SQL trace, exact PostgreSQL object inventory, effective-grant proof or authorization to execute retention. No destructive operation was run and no patient data was accessed.

### 26.1 Privacy retention executor

Inspected `backend/domains/privacy/retention_service.py` and the queue call path recorded in Section 25.

- Every category execution reads active `PrivacyLegalHold` rows. It derives category-wide and patient-specific holds before selecting candidates.
- `privacy-decision-audits`: delete action counts and then deletes eligible `PrivacyDecisionAudit` rows older than cutoff, limited to result `ALLOW`, excluding `privacy.retention.execute` and `identity.user.unlock`. Requires SELECT and DELETE on the audit relation; the retention run ledger and execution audit are separately inserted by the revision executor.
- `patients`: candidate SELECT reads `Patient`; clock modes additionally read `PatientEncounter`, `InpatientAdmission`, and/or `Invoice`. Anonymise updates patient identity/contact/network-sharing fields. Delete performs reference checks against encounter, invoice, allergy, diagnostic order, insurance policy and consent records, then deletes eligible patient rows.
- Patient-delete reference checks catch broad exceptions and continue. This means a failed dependency query can be omitted from the in-memory reference set; it is not a safe basis for a production hard-delete grant or retention assurance. The reviewed check list is not proven to cover every FK, dependent table, cascade or external reference. Must fail closed and use a catalog-derived dependency inventory before any production deletion.
- The dry-run path reports candidate count before the hard-delete reference filtering that only runs for non-dry-run execution; therefore dry-run affected count can exceed the actual deletable count. This is a reporting/approval accuracy gap to test.
- Unknown/custom categories return `NOOP_UNKNOWN_CATEGORY` with zero candidates rather than failing closed. The policy/category validation contract must explicitly decide whether unsupported configured categories should reject execution.
- Revision executor requires an APPROVED RETENTION revision, validates its document, iterates requested category codes, and on non-dry-run inserts `PrivacyRetentionRunLedger` and `PrivacyDecisionAudit` before commit. The service itself can perform UPDATE/DELETE/INSERT in one tenant session.
- Exact transaction boundaries, rollback behavior after partial category work, legal-hold race handling, retention ledger trigger/ACL details and every policy category remain to be proven.

### 26.2 Diagnostic LIS delta check

Inspected `backend/domains/clinical/services.py:evaluate_lab_delta_check` and its caller in `backend/domains/diagnostics/router.py:submit_task_result`.

- Reads `LabDeltaCheckConfig` by service ID.
- Reads the most recent prior `DiagnosticTask` joined to `DiagnosticOrder`, filtered by patient, service, non-null result and configured lookback; optionally excludes current task; ordered by created time and ID.
- Performs in-memory numeric parsing and threshold comparison; the helper itself does not write. The caller updates the current task result/status/performer/verifier/critical fields and handles delta result/review state in the enclosing workflow.
- Runtime minimum for this helper is SELECT on config, diagnostic task and order relations. Caller writes are separate and include UPDATE on task; alert/evidence side effects require a complete continuation of the caller and downstream services. Do not infer INSERT requirements from the evaluator alone.

### 26.3 Pharmacy prescription dispensing

Inspected `backend/domains/pharmacy/router.py:dispense_medication`.

- Locks and reads `Prescription`, `PrescriptionItem`, draft `Invoice`, and selected `InventoryBatch`; checks expiry, stock, FEFO and remaining prescription quantity; reads `MedicationMaster`.
- May INSERT a draft invoice; UPDATEs batch stock, prescription-item dispensed quantity, invoice totals and prescription status; INSERTs `InvoiceLineItem` rows with prescription-item and actor provenance.
- A correct runtime privilege map must include reads of the medication and encounter relationship data, row-locking SELECTs, mutable inventory/prescription/invoice UPDATEs, and invoice INSERT/line INSERT. The route does not establish the full BCMA administration workflow or its audit/scan relations; those remain separate trace items.
- No prescription or inventory mutation was executed during this review.

### 26.4 Procurement reconciliation, returns and patient indents

Inspected `backend/domains/procurement/router.py`, `backend/domains/procurement/services.py`, and procurement models.

- Three-way match reads invoice, PO, PO items, GRN, GRN items and quantities; the route locks invoice and updates invoice match status. Posting approved invoice to AP inserts an `ExpenseRecord` and updates the vendor invoice's linked-expense reference.
- Vendor purchase return locks accepted GRN, GRN items and linked inventory batches; sums prior immutable return-item quantities; inserts purchase-return header and immutable return-item rows; decrements mutable batch stock; inserts a negative approved `ExpenseRecord`. Append-only trigger protection for purchase-return header/detail families was recorded in Section 21; runtime requires SELECT/INSERT on those ledger relations, not UPDATE/DELETE.
- Patient indent issue locks indent items and inventory batches, validates quantities/expiry, decrements batch stock, increments issued quantity, creates or locks a draft invoice, inserts invoice lines and `PatientIndentIssueAllocation` provenance rows, and updates indent status/invoice total.
- Patient indent return reads original issue allocations and prior return events, locks inventory batch/indent records, restores stock and records immutable `PatientIndentReturnEvent` rows; invoice credit behavior is constrained to a DRAFT invoice, with non-draft invoices requiring a separate credit-note/refund workflow. Exact per-column writes and full tail of return logic need a focused follow-up.
- These paths mix mutable workflow state with immutable event/ledger tables. Do not grant blanket UPDATE/DELETE to procurement tables as a group. The Section 21 append-only relation inventory remains subject to migration/catalog trigger verification.

### 26.5 Billing / RCM

Inspected `backend/domains/billing/rcm_services.py` and `backend/domains/billing/services.py`.

- Tariff resolution reads service catalog, encounter, patient insurance policy/plan and tariff records.
- Draft invoice helper reads encounter and draft invoices; may INSERT an invoice.
- Clinical charge posting reads charge-capture event for source-reference idempotency, resolves encounter/tariff, inserts invoice line and charge-capture event, recalculates mutable invoice totals/tax fields, and commits.
- Existing auto-billing helpers read doctor/user, bed-transfer/bed, service catalog, insurance tariff and blood-bank relationships; insert invoice lines and update invoice totals. Diagnostic cancellation reversal locks draft invoices and may DELETE matching draft invoice lines, then recalculates totals.
- This is not a complete trace of payment capture, deposits, refunds, insurer/TPA settlement, cashbook, bank reconciliation, write-offs or all RCM endpoints. No conclusion about those privilege requirements is approved.

### 26.6 Least-privilege consequences and next proof

1. Retention is a privileged tenant-bound workload: its category executor can DELETE privacy audits and patients, UPDATE patient records, and INSERT tamper-evident run/audit evidence. It must not run under the ordinary clinical HTTP identity. The queue producer/dispatcher must not inherit its tenant DB credential.
2. Split dry-run/preview from execution identity and enforce immutable approved policy revision, category allowlist, actor/approval, tenant binding, legal-hold snapshot/locking strategy, idempotency and auditable execution result.
3. Replace swallowed dependency-query exceptions with fail-closed behavior; derive delete dependencies from PostgreSQL catalogs and test concurrent FK insertion/legal-hold changes. Resolve dry-run count semantics and unsupported category behavior before enabling execution.
4. Distinguish mutable workflow tables (patient, task, prescription, inventory batch, invoice, indent, vendor invoice) from append-only event/ledger tables (retention run ledger, procurement returns, patient indent allocations/returns, charge-capture events, other Section 21 evidence). Prove triggers and raw-SQL denial in disposable PostgreSQL.
5. Complete BCMA administration, controlled-substance dispense/return, all pharmacy return/adjustment, supplier payment/bank reconciliation, patient-indents return, billing payment/deposit/refund/RCM and every remaining queue handler.
6. Capture SQL against disposable migrated CP and tenant databases, including cascades, trigger effects, sequences and transaction boundaries; test using independent workload logins and adversarial cross-tenant sessions. Only then draft table/sequence/type/function grants and obtain DBA/security review.

No final grant SQL is approved. PostgreSQL database-per-tenant remains invariant. No runtime/SQL/migration/Compose/credential/secret/database/production change; no patient data or destructive retention execution.


## Section 27 — BCMA, controlled substances, supplier-bank reconciliation and patient billing operations

**Scope.** Source review of current branch paths listed below. This is an ORM operation trace, not exhaustive SQL capture, catalog proof, effective-ACL proof or clinical/financial workflow certification. No clinical or financial operation was executed.

### 27.1 BCMA / eMAR

Inspected `backend/domains/pharmacy/services.py:evaluate_bcma_five_rights` and `execute_bcma_administration`, called by `backend/domains/pharmacy/router.py:/bcma/verify-and-administer`.

- Evaluation reads `PatientEncounter`, `Patient`, `PrescriptionItem` and its prescription/medication relationships, validating encounter linkage, active prescription, patient barcode, drug identifier, dose, route and administration time.
- Execution can INSERT `BCMAScanAuditLog` and commit it even for blocked mismatch or unapproved time-window warning; successful administration reads allergy-related records through `check_allergy_hard_stop`, checks prior `MedicationAdministrationLog` records, INSERTs eMAR and BCMA audit rows, increments `PrescriptionItem.dispensed_quantity`, then commits.
- Minimum trace therefore includes SELECT on encounter/patient/prescription/item/medication, allergy and existing administration/audit context; INSERT on BCMA audit and eMAR; UPDATE on prescription item. Exact allergy helper tables and all relationship loader SQL still require capture.
- The blocked/warning audit commit before raising an HTTP error is intentional evidence persistence, not a read-only failed request. Grant design must include these INSERT paths without permitting mutation of the audit rows after insertion.

### 27.2 Pharmacy returns and controlled substances

Inspected `backend/domains/pharmacy/router.py:return_dispensed_medication` and controlled-substance endpoints, plus `backend/domains/pharmacy/services.py:process_controlled_substance_movement`.

- Prescription return locks prescription, latest non-void invoice, prescription items and inventory batches; reads medication and invoice lines; restores stock, decrements dispensed quantities, mutates/deletes matching draft invoice lines and recalculates invoice totals; INSERTs `PharmacyReturnLog`. If the invoice is PAID, it INSERTs `RefundVoucher`. It then UPDATEs prescription status.
- Controlled-substance movements lock `ControlledSubstanceVault`; witness verification reads `User` and permission/credential context. Dispense/return optionally read encounter and prescription item. Return sums prior `ControlledSubstanceMovementLog` DISPENSE and RETURN_TO_VAULT quantities; movement updates vault balance and optional tamper seal, then INSERTs a movement log with actors, witness, quantity, before/after and clinical linkage. Receipt/dispense/wastage/return all use the same service but have different read predicates and evidence requirements.
- Section 21 records DB append-only protection for the controlled-substance movement ledger. Runtime should have SELECT/INSERT on movement log and SELECT/UPDATE on vault, not ledger UPDATE/DELETE. The exact trigger and physical relation still need catalog proof.
- The source trace does not prove every return/disposal workflow, witness credential dependency, nor whether all external credential checks are tenant-local; these require statement capture and negative tests.

### 27.3 Supplier bank-statement reconciliation

Inspected `backend/domains/procurement/bank_reconciliation.py`.

- Statement import checks duplicate batch identity, INSERTs `BankStatementBatch`, checks existing `BankStatementLine` transaction IDs in chunks, then INSERTs statement lines and commits. Integrity conflicts are mapped to HTTP 409.
- Read routes SELECT batches, lines and supplier payments with allocations.
- Match operation locks statement line and supplier payment; checks prior match pair and aggregate amounts already matched against each line/payment; INSERTs `SupplierPaymentBankMatch`. Section 21 records bank batch/line/match tables as append-only trigger-protected evidence: runtime requires SELECT/INSERT, not UPDATE/DELETE.
- This is manual matching of a debit line to a supplier payment. It is not proof of bank feed signature verification, automated reconciliation, statement authenticity, settlement finality or complete external bank integration.

### 27.4 Supplier payment request and execution

Inspected `backend/domains/procurement/router.py` request, cancel, review and execute paths.

- Request creation locks vendor, reads duplicate references against supplier payment and request ledgers, locks vendor invoices, reads/locks linked expenses and aggregates prior payments/reservations; INSERTs mutable `SupplierPaymentRequest` and request-allocation children.
- List reads requests and allocations. Cancel/review lock and UPDATE request workflow state; review additionally checks request allocations/invoices and may read/update approval state.
- Execution locks request, vendor, invoices and expenses; reads duplicate payment reference, existing supplier payments and request reservation aggregates; INSERTs append-only `SupplierPayment` and `SupplierPaymentAllocation`; conditionally UPDATEs invoice and expense status/reference; UPDATEs request execution status, payment linkage, timestamps and updater.
- Section 21 records supplier payment/allocation ledgers as append-only. Do not confuse mutable request/request-allocation workflow tables with the immutable executed payment ledger. Exact request-allocation lifecycle and trigger coverage need metadata proof.

### 27.5 Reconciliation investigations and notification governance

Inspected `backend/domains/procurement/investigations.py`, `escalation.py`, and `notification_inbox.py`.

- Investigation creation reads source record and active SLA policy, checks duplicate investigation, INSERTs mutable investigation and immutable `ReconciliationInvestigationEvent` OPENED event.
- Assignment/transition/reopen/quality-review lock and UPDATE investigation state/version/assignee/resolution/quality fields; append corresponding immutable event rows. Event history routes SELECT event rows.
- SLA policy and escalation-policy endpoints INSERT/SELECT policy records; escalation-policy replacement UPDATEs prior active policy flags and INSERTs a new version plus immutable `ReconciliationNotificationConfigEvent`.
- User notification preference updates SELECT/lock and INSERT or UPDATE mutable preference rows, then INSERT immutable config event. Inbox read SELECTs recipient-owned outbox rows; marking read locks and UPDATEs `ReconciliationNotificationOutbox.read_at`.
- Governance report generation reads reconciliation sources and inserts immutable report records (recorded in Section 21); the complete report aggregation query graph was not fully traced here.
- Keep mutable investigation/policy/preference/outbox state separate from append-only investigation/config/governance evidence. Exact physical names and trigger coverage remain subject to migration/catalog validation.

### 27.6 Patient billing: payments, reversals, deposits and refunds

Inspected `backend/domains/billing/router.py`.

- Payment capture locks invoice; checks duplicate transaction reference; INSERTs `PaymentReceipt`; UPDATEs invoice paid amount/status.
- Payment listing reads invoice and receipts and invokes privacy evaluation, inheriting privacy policy/consent reads and decision-audit INSERT from Section 25.
- Payment reversal locks invoice, reads receipt and may lock/update linked deposit; UPDATEs invoice paid amount/status and DELETEs the payment receipt. Insurance receipts are rejected from this direct reversal path.
- Deposit collection reads active patient and optional encounter; INSERTs `PatientDeposit`.
- Deposit listing invokes privacy evaluation. Applying a deposit locks invoice and deposit; UPDATEs deposit balance/status and invoice paid amount/status; INSERTs an `ADVANCE_ADJUSTMENT` PaymentReceipt.
- Deposit refund locks deposit; UPDATEs remaining balance/status and INSERTs `RefundVoucher`. Refund listing invokes privacy evaluation and SELECTs vouchers.
- These source paths show that payment receipt and refund voucher are not uniformly immutable at DB level: payment reversal explicitly DELETEs `PaymentReceipt`; Section 21 trigger inventory does not list payment receipts as DB append-only. Do not apply an append-only grant policy without an explicit reversal design decision and catalog proof.

### 27.7 Privilege and control implications

1. BCMA and controlled-substance services are distinct clinical evidence workflows. Ordinary pharmacy DML cannot be inferred to cover BCMA audit/eMAR or controlled ledger requirements; grant them by exact table and operation.
2. Keep controlled-substance and procurement evidence ledgers SELECT/INSERT only. Verify triggers and independent-session UPDATE/DELETE denial.
3. Supplier payment execution needs SELECT/INSERT on immutable payment ledgers plus UPDATE on request, vendor invoice and expense workflow rows. Bank reconciliation adds append-only statement/match evidence.
4. Investigation and notification design mixes mutable current-state rows with append-only event rows; avoid blanket grants across model families.
5. Patient billing requires targeted invoice/deposit UPDATE, receipt INSERT and currently observed receipt DELETE reversal, plus refund voucher INSERT and privacy audit side effects. This is a high-risk finance identity and needs explicit approval/audit policy.
6. Complete the remaining bank-reconciliation candidate aggregation, report generation and all model/migration/trigger relationships with disposable PostgreSQL SQL capture. Then test each workload role independently, including raw SQL attempts against evidence tables and cross-tenant/CP connection denial.

No final grant SQL is approved. PostgreSQL database-per-tenant remains invariant. No runtime/SQL/migration/Compose/credential/secret/database/production change; no patient or financial records were accessed or mutated.

### Section 28 — Reconciliation candidates, governance snapshots, insurance settlement, pharmacy stock adjustments and queue handlers

Source-traced on 13 November 2026 from the current `main` source:
- `backend/domains/procurement/bank_reconciliation.py`
- `backend/domains/procurement/investigations.py`
- `backend/domains/insurance/router.py`
- `backend/domains/billing/rcm_services.py`
- `backend/domains/pharmacy/router.py`
- `backend/core/queue.py`

#### 28.1 Bank reconciliation candidate generation and matching
- Candidate listing is a read-only aggregation over bank statement lines, supplier payments and supplier payment requests. It derives unclassified credits, unmatched/partially matched debits, unreconciled/partially reconciled supplier payments, possible duplicate payment references and overdue approved payment requests. Candidate cursors are decoded/validated; the endpoint does not itself create investigations.
- Matching a bank debit locks the statement line first and supplier payment second, checks the pair for an existing match, sums prior matches against both objects, enforces that the new amount fits both remaining balances, and INSERTs a `SupplierPaymentBankMatch`. The match is not an UPDATE to either source ledger.
- Statement import validates statement arithmetic and in-period dates, checks duplicate statement/transaction identities, INSERTs a batch and its lines, and commits together. Application duplicate checks are not a substitute for database uniqueness and concurrent-session tests.
- Candidate aggregation is a live derived view, not a persisted reconciliation result or evidence that a bank statement originated from an authenticated bank feed. External bank authenticity, signature/transport validation and statement completeness remain unproven.

#### 28.2 Governance report snapshots
- `GET /reconciliation/dashboard`, SLA summary, quality summary and recurrence summary are live tenant-local aggregate SELECTs; they are not immutable monthly snapshots.
- Monthly governance report generation accepts only completed UTC calendar months, rejects a duplicate month, calculates aggregate-only counts and classifications, canonicalizes the JSON payload, computes SHA-256, and INSERTs one `ReconciliationGovernanceReport`. Listing/get endpoints SELECT metadata or payload.
- The snapshot intentionally excludes source narratives and source financial identifiers. Its payload includes interpretation limits: closure quality is current state at generation, backlog is point-in-time at generation, SLA is elapsed wall-clock time, and recurrence/root-cause groupings are human-recorded indicators rather than verified causality.
- The SHA-256 field detects accidental payload changes only if the stored digest is trusted; it is not a digital signature, external timestamp, or independent proof of origin. DB immutability still depends on the migration trigger/ACL inventory and independent UPDATE/DELETE denial proof.

#### 28.3 Insurance claim and settlement operations
- Claim submission reads invoice and line items, policy/plan, optional approved preauthorization and plan tariffs; validates invoice state and one-claim-per-invoice at application level; then INSERTs `InsuranceClaim`. Insurer payable is calculated from the invoice net amount before advance deposits are deducted (explicit FIN-001 comment), less exclusions and copay, capped by policy/preauth coverage. Claimed amount is outstanding balance. The different bases need finance-owner confirmation and reconciled examples.
- Claim listing and CSV export read claims joined to invoice/patient and policy/provider. Claim PDF reads claim, invoice, patient, policy, provider, plan, preauth, invoice lines, report template/profile and privacy-decision audit path.
- Settlement locks the claim, rejects already-settled/rejected claims, bounds the amount by insurer payable and remaining invoice balance, then INSERTs an insurance `PaymentReceipt`, UPDATEs invoice paid amount/status and UPDATEs claim status/settled amount/UTR/remarks in one transaction.
- Important semantic risk: the route sets claim status to `SETTLED` for any accepted amount, including an amount lower than `insurer_payable_paise`; it does not model a partially settled claim state. It also has no explicit idempotency key beyond the current SETTLED-state check. A retry after commit is rejected, but timeout/response-loss and concurrent duplicate settlement require independent PostgreSQL proof and a finance-approved partial-settlement policy.
- No settlement reversal/compensation path was established in this trace. Receipt immutability is not established; prior billing trace found a receipt DELETE reversal path elsewhere.

#### 28.4 Pharmacy stock adjustment and void
- Inventory adjustment locks one `InventoryBatch` row with NOWAIT, rejects zero adjustment and negative resulting stock, mutates `stock_quantity`, and commits. It does not INSERT a separate stock-adjustment ledger row in this endpoint.
- Batch void also locks the batch and sets stock to zero rather than deleting it. The endpoint response says this preserves recall traceability, but the reviewed operation does not itself record a distinct immutable reason/actor/quantity adjustment event beyond surrounding application audit behavior (not established here).
- This creates a material evidence gap for inventory reconciliation: before least-privilege grants or production readiness are certified, enumerate every stock mutation path and prove who/when/why, before/after quantities, batch identity, source document and reversal/compensation are independently retained. Do not infer that ORM audit mixins or general audit logs provide a complete inventory subledger.
- Pharmacy return service paths were already traced in Section 27; this section adds the direct batch-adjust/void endpoints and does not claim an exhaustive pharmacy route inventory.

#### 28.5 Queue handler and execution boundary
- The task registry in `backend/core/queue.py` currently has three handlers: `email.send`, `privacy.retention.execute` and `privacy.retention.scheduled_daily_sweep`.
- Email handler invokes the configured mailer; no tenant DB session is opened in the handler itself.
- Retention execution resolves an active tenant in CP, obtains a tenant engine by DB name, opens a tenant session, validates an approved retention revision, resolves an active actor with separation-of-duties checks, then calls the retention service. Non-dry-run is blocked unless the deployment flag is enabled and the environment is not production.
- Daily sweep opens CP session, reads all active tenants, then opens a tenant session per tenant to find the latest approved retention policy; it enqueues one tenant-scoped retention job for each. It forces dry-run in production or when destructive execution is disabled. It records/enqueues tenant subdomains in the result.
- Queue enqueue has `sync_fallback=True` by default; on Redis failure it directly invokes the registered handler in the caller process. This can collapse the intended asynchronous worker boundary and execute a tenant/retention handler inside an API/scheduler process. Queue task status/TTL semantics are Redis-backed and are not a durable database job ledger.
- Current worker/queue code uses the shared tenant engine registry and CP session factory. The handler's tenant selector is a subdomain resolved through CP, but the underlying engine credential is not a per-tenant DB authorization boundary. Keep CP scheduler, tenant-bound worker and privileged retention executor separate; disable synchronous fallback for privileged/destructive tasks and require durable enqueue/claim/ack semantics before production certification.

#### 28.6 Privilege implications and remaining proof
- Reconciliation candidate/dashboard/report reads require targeted SELECT across investigation/event, bank statement, supplier payment/request/match and SLA/report objects. Match/import and investigation/report creation require narrowly scoped INSERT; investigation assignment/transition and SLA configuration also require UPDATE on mutable workflow/configuration rows.
- Insurance claim settlement requires SELECT on invoice/line, policy/plan/preauth/tariff and claim rows; INSERT on PaymentReceipt; UPDATE on Invoice and InsuranceClaim. Patient-linked list/PDF flows also invoke privacy decision auditing. No blanket grant across all billing/insurance models is justified.
- Pharmacy stock adjustment/void require SELECT/UPDATE on InventoryBatch; absence of an explicit stock adjustment ledger in these endpoints is a separate domain evidence gap, not a grant recommendation.
- No final SQL statement capture, live PostgreSQL catalog/trigger comparison, external bank-feed proof, insurer settlement concurrency/idempotency proof, or independent workload-role ACL test was performed.

No production grant SQL is approved. PostgreSQL database-per-tenant remains invariant. No runtime/SQL/migration/Compose/credential/secret/database/production change; no patient or financial records were accessed or mutated.

### Section 29 — Alembic metadata boundary and deterministic inventory limitations

Source-traced on 13 November 2026:
- `backend/alembic/env.py`
- `backend/control_plane/alembic/env.py`
- `backend/core/database.py`
- `backend/control_plane/models.py`
- `backend/domains/audit/models.py`
- `deployments/postgres-roles.sql`

#### 29.1 Two independent declarative metadata roots
- Tenant `Base` is declared in `backend.core.database`; the tenant Alembic environment imports 23 domain model modules before setting `target_metadata=Base.metadata`. The imports cover ABDM, audit, billing, blood bank, clinical, diagnostics, encounters, facility, federation, finance, identity, insurance, integrations, patients, pharmacy, policies, privacy, procurement, quality, reports, service operations, surgery and workforce.
- Control-plane `ControlBase` is declared in `backend.control_plane.models`; the CP Alembic environment imports that module and sets `target_metadata=ControlBase.metadata`. The current module declares 11 CP tables: tenant registry, federated nodes, global patient pointers, CP audit logs, tenant snapshot registry, module catalog, bundle catalog, blueprint catalog, migration schemas, CP operators and CP operator sessions.
- These are separate PostgreSQL databases and separate metadata roots. Do not combine the two metadata sets into one grant inventory or infer a PostgreSQL schema-per-tenant design.

#### 29.2 Metadata is not a live database inventory
- Alembic metadata describes ORM-declared tables and constraints only after the configured imports execute. It does not by itself enumerate live catalog-only objects, views, materialized views, manually-created functions, triggers, extensions, sequences without mapped ownership, grants, role memberships, PUBLIC privileges, large objects or objects created by scripts.
- Tenant environment imports 23 modules explicitly, while CP environment imports a single module containing CP table declarations. This establishes intended ORM metadata loading paths, not proof that every model class, relationship dependency, migration revision or live database object is present and synchronized.
- Both Alembic environments take a configured URL or environment URL and apply a transaction-scoped advisory lock. That lock serializes migrations using the same key; it does not restrict the migration identity's authority or establish target-database authorization.

#### 29.3 Evidence and immutability caveats
- `ControlPlaneAuditLog` has SQLAlchemy `before_update` and `before_delete` listeners in `backend/control_plane/models.py`. These listeners protect ORM unit-of-work paths only; raw SQL, Core/bulk operations and another DB client are outside that guard. Its DB-level immutability remains unproven until the actual CP migration/catalog trigger and ACL are captured.
- `SecurityAuditExportRegister` declares table creation listeners whose shown trigger DDL is explicitly SQLite-only. This source file alone does not establish PostgreSQL trigger installation; PostgreSQL migration and live catalog evidence are required. Do not treat SQLite DDL as PostgreSQL proof.
- The production role SQL still grants `hms_app` CRUD on all tables and sequence UPDATE in the literal `postgres` database, gives `hms_backup` `pg_read_all_data`, and grants `hms_exporter` `pg_monitor`. It does not establish per-tenant database grants or per-object creator-aware default privileges. This remains characterization evidence, not a least-privilege configuration.

#### 29.4 Required deterministic inventory proof
1. Execute a deterministic, versioned metadata-export script in a disposable environment for both metadata roots; record table, column, PK, FK, unique/check constraint, index, enum, sequence and schema names with stable sorting.
2. Independently capture `pg_catalog` and `information_schema` from a clean migrated CP database and at least two independently migrated tenant databases.
3. Compare expected ORM metadata, migration history and live catalog objects; classify every delta as intentional, migration-only, script-created, extension-owned, drift or defect.
4. Enumerate triggers with function definitions, function security mode/owner/search path, views/materialized views, extensions, large objects, sequences/ownership/default ACL, RLS policies, grants, role memberships, PUBLIC ACLs and object owners.
5. Reconcile append-only claims from Sections 21, 27 and 28 against actual PostgreSQL trigger definitions and raw SQL UPDATE/DELETE denials. Do not rely on ORM listeners or SQLite-only DDL.
6. Repeat the comparison after migrations and after restore; include a second tenant to prove database-per-tenant isolation and prevent cross-database inventory assumptions.

No live database was queried in this source-only pass. No final grant SQL is approved. No runtime/SQL/migration/Compose/credential/secret/database/production change; no patient or financial records accessed or mutated.


### Section 30 — Disposable PostgreSQL proof harness boundary and migration-catalog execution plan

Source-traced on 13 November 2026:
- `.github/workflows/on-demand-validation.yml`
- `deployments/aud004-proof/compose.yaml`
- `deployments/aud004-proof/test_production_role_bootstrap.py`
- `backend/alembic.ini`, `backend/alembic/env.py`
- `backend/control_plane/alembic.ini`, `backend/control_plane/alembic/env.py`

#### 30.1 Existing CI proof boundaries
- The on-demand workflow has a dedicated PostgreSQL 17 service for the production role-bootstrap characterization test. That test creates three synthetic databases and executes the actual `apply_database_roles()` function extracted from `backend/scripts/bootstrap.py`; it proves the current role bootstrap's unsafe behavior. It does not run either Alembic environment or inspect migrated application catalogs.
- A separate Docker Compose proof project provisions a disposable PostgreSQL service and runs tenant A, tenant B and CP identity probes in separate containers. Its current fixture is intentionally small and marker-table oriented; it proves database connection/object isolation for its synthetic role setup, not the production Alembic object inventory.
- The workflow's current `reconciliation` scope runs these AUD-004 jobs, while the normal backend scope runs the broader test suite. The existing harness therefore provides a safe disposable-PostgreSQL foundation, but it is not yet the requested migration/catalog acceptance test.

#### 30.2 Migration execution constraints
- Tenant Alembic reads its URL from Alembic config, `DATABASE_URL`, or application settings; its metadata root is populated by importing 23 tenant model modules.
- CP Alembic resolves its URL from config, `DATABASE_URL`, or the application database URL with the configured CP database name; it uses the separate CP metadata root.
- Both online environments execute real migration revisions and take the shared transaction-scoped advisory lock. A test must explicitly set each target URL and must not inherit an ambient developer, staging or production URL.
- The existing CI role-bootstrap job's Postgres service credentials and the separate Compose proof credentials are synthetic CI-only identities. Reuse neither as application production credentials nor as evidence that a migrated catalog has been captured.

#### 30.3 Safe next implementation sequence
1. Add a separate, explicitly named migration/catalog proof job to the existing AUD-004 workflow; keep it on the isolated PostgreSQL 17 service or a uniquely named disposable Compose project with preflight refusal of pre-existing resources.
2. Generate ephemeral setup and workload credentials at job runtime; do not place them in repository files, workflow literals or artifacts. Ensure the job has no production secrets and no network path to any non-disposable database.
3. Create one CP database and two tenant databases with explicit synthetic names. Run the CP Alembic upgrade against only the CP URL, then run tenant Alembic independently against tenant A and tenant B URLs. Assert each database has the expected Alembic version state before catalog capture.
4. Export sorted metadata manifests from the actual tenant and CP declarative roots. Capture live catalogs separately from all three migrated databases, including object definitions, ownership, ACLs, default ACLs, role memberships, PUBLIC privileges, extensions, RLS, large objects, views, triggers and function security attributes.
5. Compare ORM metadata to each live catalog without flattening databases into a schema-per-tenant model. Keep tenant A and B as separate PostgreSQL databases; compare their object inventories independently and explain expected database-local differences.
6. Run raw SQL append-only UPDATE/DELETE denial tests only after the migration has established the relevant object/trigger/ACL; report missing protection as a failing proof, not as a skipped assertion.
7. Preserve redacted, deterministic manifests and concise diff summaries as CI artifacts. Never export application rows, secrets, connection strings or patient/financial data.
8. Repeat the catalog and ACL capture after a disposable backup/restore drill; compare owners, ACLs, default privileges, extensions, triggers and function definitions before calling restore parity established.

#### 30.4 Explicit non-claims
- The current successful production role-bootstrap test is not an Alembic migration test and does not prove the migrated catalog inventory.
- The current tenant A/B/CP identity fixture is not proof that the real application schema, migrations, triggers or role grants are correct.
- No catalog snapshots, migration execution, restore comparison or production privilege certification were performed in this source-only batch.
- Do not generate or apply final grant SQL from ORM metadata alone. PostgreSQL database-per-tenant remains invariant.

No runtime/SQL/migration/Compose/credential/secret/database/production change; no patient or financial records accessed or mutated.
