# AUD-004 DBID-R01–DBID-R06 Resolution Proposal — Independent Review

**Review target:** PR #48 — DBID-R01–DBID-R06 Resolution Proposal  
**Review basis:** Complete proposal document at the reviewed PR head  
**Status:** INDEPENDENT DESIGN REVIEW — NOT IMPLEMENTATION APPROVAL  
**Release status:** AUD-004 remains a release blocker.

## 1. Executive conclusion

PR #48 materially improves the design. It selects an external provisioning-only network/cluster boundary, adds a versioned PostgreSQL privilege baseline, separates minimal selector resolution from protected projection, enumerates revocation checkpoints, strengthens pool/session invalidation, and binds authorization to read-set and response-digest evidence.

The proposal is directionally sound but is **not yet sufficient to close all six findings**. This review identifies three High and three Medium residual findings. They concern: completeness of the provisioning trust boundary; the precise meaning of “no patient data read” during selector matching; atomic revocation fencing; credential-version attribution of live PostgreSQL sessions; and the exact artifact layer covered by the digest contract. These are design gaps, not evidence that a production environment is exposed.

No production catalogs, networks, identities, credentials, secret manager, audit store, or patient data were inspected.

## 2. Findings

### DBID-R07 — High: Provisioning boundary trust graph and privileged bypass paths are incomplete

**Evidence in PR #48:** Sections 2.1–2.4 select a provisioning-only network/cluster boundary, deny runtime paths until READY, and require direct-connect tests from application, source, import, background, support, control-plane and peer-tenant workloads.

**Gap:** The reachability matrix does not fully enumerate privileged and infrastructure identities that may have network or control-plane access to the database listener. Examples include database/platform administrators, backup and restore agents, monitoring/observability agents, migration runners, CI/CD runners, orchestration nodes, host agents, service-mesh sidecars, secret-broker workloads and emergency support identities. “Ordinary operator workloads” is not a precise identity class or an enforceable exception policy.

A separate network/cluster boundary is only meaningful if all paths into it are enumerated, including management planes, peering, shared hosts, IPv6, private endpoints, proxy/pooler paths and privileged orchestration APIs. The document also needs to distinguish the provisioning control-plane identity from a workload allowed to establish database sessions; control-plane authority must not imply a general-purpose database client.

**Required resolution:**
1. Define a complete principal inventory by identity, workload, host/network location, credential class and permitted operation.
2. Add explicit rows for provisioning, migration, backup/restore, monitoring, DBA/platform administration, CI/CD, orchestration, support and emergency access.
3. Define the only permitted pre-READY connection path, its workload identity, tenant/database binding, authentication, authorization and audit requirements.
4. Prohibit shared runners/hosts or broad cluster-admin identities from becoming an unreviewed path from ordinary runtime networks into the provisioning boundary.
5. Include IPv4/IPv6, DNS, peering, private endpoints, proxies/poolers, host networking, sidecars and management-plane routes in the threat model.
6. Specify dual-control, time-bound access and evidence for any exceptional human or platform-admin path; no emergency bypass may silently make a database READY.

**Closure evidence:** A complete trust-boundary/data-flow diagram and principal-to-network-to-database access matrix; negative connection tests for every non-provisioning identity class; and independent review of management-plane and infrastructure bypass paths.

### DBID-R08 — High: Selector matching semantics conflict with the prohibition on reading identifiers

**Evidence in PR #48:** Section 4.1 says selector resolution returns only an opaque source-local candidate reference and prohibits loading demographics, ABHA, phone, DOB and other personal/clinical payload. Section 4.2 prohibits ORM entities and requires explicit projections.

**Gap:** A selector search commonly compares a supplied phone number, ABHA, MRN or other patient identifier against a source-held value. The database engine must evaluate that value to perform the match. The current wording can be read as prohibiting even the internal predicate evaluation, while it does not clearly distinguish:
- a sensitive field being evaluated inside the source database solely as a bounded match predicate;
- the value being projected/materialized into the source application process;
- the value or match detail being returned to the destination.

Without this distinction, implementers may either build an impossible “no identifier read” query or weaken the rule by loading patient rows/ORM entities into application memory. The proposal also does not normatively identify which selector classes may be used, their canonicalization, rate/budget constraints or privacy-preserving index mechanism. CAN-02's prohibition on plain/global deterministic hashes remains applicable.

**Required resolution:**
1. Define an explicit selector-evaluation contract: only approved selector input classes may be evaluated, only inside the source-owned boundary, solely for bounded equality/match resolution.
2. Permit database-internal predicate evaluation of the approved selector value while prohibiting projection/materialization of the stored identifier, demographics or clinical payload into application memory before candidate authorization.
3. Return only a non-bearer opaque candidate reference and the minimum authorization metadata; do not return match counts, identifier fragments, candidate ordering or existence-specific details to an unauthorized caller.
4. Specify the approved selector canonicalization, keyed/source-scoped commitment or index design, key separation/rotation and anti-enumeration budgets consistently with CAN-02.
5. Define query plans and SQL-level tests that prove the sensitive field is used only as a predicate and is not selected, serialized, logged, relationship-loaded or returned.
6. State how exact-match and ambiguous/no-match cases produce externally indistinguishable outcomes under the approved response contract.

**Closure evidence:** A precise database-vs-application read boundary, selector allowlist and privacy design; instrumented SQL tests proving predicate-only evaluation; and anti-enumeration tests for response body, headers, counts, errors and timing.

### DBID-R09 — High: Revocation checkpoints remain vulnerable to a check/use race

**Evidence in PR #48:** Section 5 defines checks before selector resolution, candidate authorization, disclosure-intent commit and payload release. Section 5.4 correctly recognizes that disclosure may become irreversible once bytes leave the source process.

**Gap:** “Immediately before” checks do not by themselves make authorization current at the moment the protected read or release is committed. A key, clinician affiliation, destination, policy or workload can be revoked after the final check but before the protected query, serialization, queue publication or network write. The document does not define a linearization point or fencing mechanism that orders revocation against disclosure.

Recording OUTCOME_UNCERTAIN after the race is necessary but does not prevent a stale worker from continuing after another worker or control-plane process has revoked authority.

**Required resolution:**
1. Define a source-owned authorization generation/epoch or equivalent fencing token for each relevant revocation domain and operation.
2. Bind candidate authorization, disclosure intent, protected read and response artifact to the same generation set.
3. Define the atomic/serialized boundary at which the source commits permission to disclose, and how a concurrent revocation invalidates or fences a worker that has not crossed that boundary.
4. Require every worker, retry and queued task to validate the current fencing generation before protected read and before release; stale generations must be rejected.
5. Define which revocations can be made strictly effective before disclosure and which have an unavoidable propagation window; identify that residual risk and require governance approval of its maximum.
6. Include deterministic concurrency tests for revocation between every check and use, including stale worker resumption after lease expiry or process pause.

**Closure evidence:** A documented linearization/fencing model, monotonic generation state and race tests proving that stale workers cannot read or release after a newer revocation generation becomes effective. Any unavoidable in-flight disclosure window must be explicit and formally accepted.

### DBID-R10 — Medium: Credential-version attribution of existing PostgreSQL sessions is not guaranteed

**Evidence in PR #48:** Section 6 requires stopping checkout, draining/invalidation, disposing pools, revoking credentials, terminating sessions and verifying server-side state. Section 6.2 suggests application_name plus server-side role identity.

**Gap:** If credential rotation reuses the same PostgreSQL login role, server-side session identity may not distinguish sessions authenticated with the old password from sessions authenticated with the new password. application_name is useful metadata but is not authoritative if the process can set or reuse it. Connection poolers may also multiplex client connections onto server sessions authenticated under a pooler role, obscuring the original tenant credential version.

**Required resolution:**
1. Prefer a distinct login role per credential version (or another server-verifiable session identity) so old and new sessions are distinguishable without trusting caller-set metadata.
2. Define role membership and privilege parity for rotation so the new login does not gain broader privileges and the old login can be revoked independently.
3. Specify behavior for transaction/statement poolers and managed database proxies, including which side owns server sessions and how client-to-server attribution is proven.
4. Treat application_name as diagnostic metadata only, not sole proof of credential version.
5. Require server-side tests that establish sessions with both versions, rotate/revoke the old version, and prove exactly which sessions remain.
6. If a platform cannot attribute or terminate old sessions reliably, require source isolation/quarantine or a separately reviewed rotation strategy rather than claiming completion.

**Closure evidence:** Credential-version-specific server identity or equivalent authoritative attribution; pooler-aware rotation tests; and proof that old sessions cannot persist or reconnect after revocation completion.

### DBID-R11 — Medium: Response digest does not identify the exact artifact layer

**Evidence in PR #48:** Section 7 requires a canonical digest over the exact response artifact and integrity metadata, bound to operation, resource, destination, projection, policy/protocol and artifact version. Delivery and acknowledgement reference the same digest.

**Gap:** “Exact response artifact” remains ambiguous where the payload is serialized, compressed, encrypted, framed, chunked or transformed in transit. A digest over canonical plaintext clinical content differs from a digest over ciphertext bytes or a transport envelope. The destination must know exactly which representation it verifies, and the protocol must prevent a valid digest for one layer from being mistaken for proof about another. A digest alone also provides integrity comparison, not origin authentication or proof of receipt.

**Required resolution:**
1. Define the canonical artifact layer covered by the digest (for example, canonical serialized payload before transport encryption) and separately identify any transport/encryption envelope.
2. Specify deterministic serialization, field ordering, null/omission rules, character encoding, numeric/date normalization, compression behavior and version negotiation.
3. Bind both payload digest and, where needed, transport-envelope metadata to the operation and projection without treating encryption randomness as a change in clinical content.
4. Define which party computes and verifies each digest and the signed acknowledgement's exact claims.
5. Distinguish content integrity, sender authenticity, recipient commit and source acknowledgement verification as separate evidence.
6. Add cross-version and transformation tests for serialization, encryption, compression, chunking, retries and re-encoding.

**Closure evidence:** Canonical byte-level test vectors, a documented digest-layer diagram, destination verification tests and signed-ack tests that reject payload/envelope substitution.

### DBID-R12 — Medium: PostgreSQL privilege baseline needs explicit exception and migration-owner reconciliation

**Evidence in PR #48:** Section 3 defines versioned defaults, PUBLIC privilege revocation, per-creator default privileges, extension review and post-migration catalog assertions.

**Gap:** The proposal allows documented exceptions but does not define a single machine-readable exception register or prove that the catalog verifier evaluates both explicit ACLs and effective privileges after role membership/SET ROLE. In addition, migration ownership and extension installation may introduce objects under identities not present in the approved object-creator list. A policy can therefore pass a textual review while a newly introduced creator role or exception is not covered by generated checks.

**Required resolution:**
1. Define a versioned, machine-readable ACL exception manifest keyed by database, schema, object, principal and privilege, with approver, rationale, expiry and compensating control.
2. Require the catalog verifier to compare live ACLs and effective privileges against both the baseline and the exception manifest.
3. Enumerate every object-creating identity, including extension owners and migration helpers, and fail on an unknown creator.
4. Verify inherited memberships, SET ROLE paths, role attributes and ownership paths in the same conformance run.
5. Make exception expiry fail closed: expired or unrecognized exceptions block migration completion/READY until reviewed.

**Closure evidence:** Generated catalog checks against baseline plus exception manifest; tests for unknown creator roles, expired exceptions, inherited grants and migration-created objects.

## 3. Cross-finding assessment

| Finding | Assessment |
|---|---|
| DBID-R01 | Improved; DBID-R07 prevents closure |
| DBID-R02 | Substantially improved; DBID-R12 remains |
| DBID-R03 | Improved structurally; DBID-R08 prevents closure |
| DBID-R04 | Checkpoints are enumerated; DBID-R09 prevents closure |
| DBID-R05 | Lifecycle is stronger; DBID-R10 prevents closure |
| DBID-R06 | Digest and acknowledgement linkage improved; DBID-R11 prevents closure |

The proposal should be amended before these findings are marked resolved or used as an implementation-ready baseline.

## 4. Required next design work

The next proposal should resolve DBID-R07 through DBID-R12 with:
- complete provisioning trust-boundary principal and network inventory;
- explicit database-internal selector predicate versus application-visible projection semantics;
- revocation generations/fencing and a defined disclosure linearization point;
- credential-version-specific session attribution through supported poolers/proxies;
- byte-level artifact/digest layer definitions and cross-version test vectors;
- machine-readable privilege exceptions and catalog verification.

DBID-06 through DBID-08 remain open from the prior review. CAN-01 and AUD-004 remain open. This review does not close any prior finding by implication.

## 5. Scope and limitations

This review evaluates PR #48 as a design document. It is not a live PostgreSQL privilege audit, network penetration test, workload identity review, secret-manager review, implementation test, production configuration assessment, privacy/legal opinion or clinical safety approval. No production infrastructure or patient data was accessed.

## 6. Explicit non-authorization

This review authorizes documentation and independent design review only. It does NOT authorize runtime code changes, SQL execution, database/role/ACL/network changes, credential or secret-manager operations, production access, patient-data access, partner onboarding, trust/key provisioning, federation activation, emergency access, pilot, deployment, release or merge.

PR #48 remains draft and unmerged. DBID-06 through DBID-08 remain open. CAN-01 and AUD-004 remain release blockers. D-01–D-14 formal governance decisions remain pending; D-11 project direction YES is not formal governance approval.
