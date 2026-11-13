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

## 8. PR #23 design review — proposed, not implementation-ready

PR #23 provides a useful design direction for PR #19's concurrent-import and post-commit pointer-sync failures. Its current text correctly identifies a server-derived operation identity, durable import state, destination correlation marker, recoverable pointer synchronization, cross-database partial progress, and PostgreSQL concurrency/failure-injection tests.

The independent review comment on PR #23 requires these details to become normative before implementation:

- mandatory monotonic fencing generation for every claim, state transition and destination commit; explicit lease expiry, renewal and takeover semantics;
- two durable uniqueness barriers: unique control-plane operation identity and unique destination-side correlation marker committed atomically with the patient/allergy clone;
- versioned, domain-separated and unambiguous canonical identity encoding using destination identity, immutable source pointer identity/generation, source branch identity and protocol version; no demographics;
- provenance verification before uncertain-commit reconciliation, preventing attachment to an unrelated patient;
- explicit receipt consumption and expiry semantics, plus source identity/policy revalidation on retries;
- machine-readable API states, operation identifiers, polling/retry behavior and safe disclosure boundaries;
- PostgreSQL tests across independent sessions and separate worker processes, including stale-worker fencing, lock/unique conflicts and process termination at every cross-database boundary.

Until these details are accepted and implemented, PR #23 is a proposed design only. It does not remediate PR #19, authorize a migration or close the data-integrity findings. PR #19 remains open and unmerged; AUD-004 remains a separate release blocker.

## 9. Evidence gates before implementation or release

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

## 10. Non-authorization and change control

This is a documentation consolidation only. It does not authorize runtime code changes, SQL, migrations, PostgreSQL role/ACL/network/secret changes, production or patient-data access, partner onboarding, trust provisioning, federation activation, emergency access, pilot, deployment, release or merge.

PostgreSQL **database-per-tenant** remains unchanged. Emergency federation remains disabled. All linked PRs remain draft/unmerged unless separately and explicitly authorized.
