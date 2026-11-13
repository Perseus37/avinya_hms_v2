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
