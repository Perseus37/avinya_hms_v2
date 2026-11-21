# AUD-004 DBID-R19–DBID-R26 Resolution Proposal

**Status:** DESIGN PROPOSAL — NOT IMPLEMENTATION APPROVAL  
**Parent:** PR #53 — Independent review of DBID-R13–DBID-R18  
**Architecture:** database-per-tenant; no schema-per-tenant conversion proposed.  
**Release status:** AUD-004 remains a release blocker.

## 1. Purpose and decision posture

This document proposes resolutions for eight residual findings:

- **DBID-R19:** closed-world inventory completeness and transitive trust/control paths.
- **DBID-R20:** executable selector outcome, budget and candidate-reference contract.
- **DBID-R21:** transactionally ordered source-read and release fencing.
- **DBID-R22:** cluster-wide PostgreSQL role identity and cross-database isolation.
- **DBID-R23:** strict signed manifest, recipient-bound encryption and deterministic chunking.
- **DBID-R24:** cluster-wide ACL schema and effective-privilege verifier.
- **DBID-R25:** independent attestation, freshness and rollback protection.
- **DBID-R26:** end-to-end source/destination state, idempotency and recovery consistency.

MUST/MUST NOT/SHOULD express proposed future protocol requirements. This document does not assert that current infrastructure meets them. Provider, product, security, clinical, privacy/legal and operations decisions remain open. Examples are not approvals of algorithms, retention, limits, provider profiles or clinical workflows.

## 2. DBID-R19 — Closed-world inventory completeness and transitive trust

### 2.1 Coverage manifest

A trust graph is valid only relative to an explicit, versioned coverage manifest. Each deployment profile MUST enumerate every in-scope:

- cloud organization/account/subscription/project and region;
- identity issuer, federation provider, token exchange endpoint and administrative identity plane;
- orchestration cluster, namespace, controller, admission system, workload identity and host/node domain;
- network account, VPC/VNet, subnet, route, firewall/security group, peering, private endpoint, DNS zone/resolver, IPv4/IPv6 path and service mesh;
- PostgreSQL cluster, database, template/control database, role catalog, proxy, pooler and provider management plane;
- secret broker/vault, KMS/HSM, backup/restore system, migration runner, CI/CD, monitoring/agent and emergency-support mechanism;
- evidence source, API version, collection identity/scope, expected object classes, pagination/completeness mechanism, freshness limit and owner.

Each entry has immutable ID, authoritative source, accountable owner, independent approver, expected inventory count or completeness assertion, collection cursor/snapshot, last reconciliation, expiry and status. An omitted account, region, issuer or network plane is UNKNOWN, not empty, and blocks readiness.

### 2.2 Transitive control and mutation graph

The graph MUST model control-plane powers as well as data-plane connections. Edge types include authenticate-as, mint/exchange token, impersonate, assume/delegate role; create or modify workload, identity, route, DNS, endpoint, proxy, pooler, firewall or network policy; read/modify secret, key, trust root or workload binding; create/alter database or role, grant membership, alter ownership/ACL/default privileges; modify backup/restore, migration, CI/CD, verifier, policy, inventory adapter, attestation signer or evidence retention; and provider management/support or emergency access.

Every edge identifies grantor/issuer, scope, conditions, duration, approval, audit source and downstream capabilities. The verifier computes transitive reachability across nested groups, role memberships, delegated roles, token exchange, workload impersonation and shared identities. Privilege composition must identify paths where a combination of powers yields protected access, such as modifying a workload plus minting its identity.

The graph verifier reports paths from every principal to tenant databases, source authorization services, signing/attestation roots and verifier deployment. It separately identifies principals able to alter evidence about their own access.

### 2.3 Independent inventory and readiness

For each high-trust source, the coverage manifest identifies an evidence path independent of the principal being attested. Where independence is technically unavailable, the limitation and compensating control require explicit security-owner approval; one administrator cannot be sole mutator and sole attestor.

Collectors detect pagination truncation, partial API responses, hidden/deleted resources, eventual consistency, API-version changes and missing scopes. Every adapter emits coverage counters, source snapshot IDs, pagination completion, errors and COMPLETE / INCOMPLETE / UNKNOWN. A zero-item result is valid only with proof that the complete scope was enumerated.

Graph, coverage manifest, adapter build, verifier build and evidence-signing root are bound into an independently controlled attestation chain. A signature over incomplete input is not PASS.

Before READY and continuously thereafter, reconciliation compares observed nodes, edges and mutation authorities with approved coverage. Unknown principals, APIs, accounts, routes, memberships, issuers, management paths, verifier changes or evidence gaps result in QUARANTINED/RESTRICTED. Negative tests are generated from the enumerated graph and record population and denominator; omitted inventory classes invalidate a full-coverage claim. Tests deliberately introduce omissions, pagination truncation, stale inventory, false empty results and compromised-source evidence.

**Closure evidence:** provider-specific coverage manifest, independent source evidence, transitive reachability algorithm, complete enumeration report, verifier provenance and mutation/omission tests.

## 3. DBID-R20 — Executable selector response and resource-budget contract

### 3.1 Public outcome matrix

The source retains precise internal outcomes in restricted audit. The proposed external contract is:

| Internal condition | Public result | Body/header behavior | Retry rule |
|---|---|---|---|
| Candidate search accepted, match pending authorization | Generic accepted envelope | No candidate count, identifier, source name or match-specific header | Does not prove a match |
| No match | Same generic accepted envelope | Byte-equivalent body and permitted headers to pending-candidate case | New request under rate policy |
| Candidate denied | Same generic accepted envelope | No denial reason or resource detail | No broadened-scope retry |
| Invalid/expired reference | Generic invalid-reference envelope | No existence detail | Fresh authorized search |
| Source/policy unavailable | Generic service-unavailable envelope | No source topology or partial match count | Bounded backoff and fresh authorization |
| Partial fan-out | Same generic unavailable/indeterminate envelope | No successful/failed source list | Fresh source-authorized request |
| Budget exceeded | Explicit rate-limited envelope | Retry-After only if approved; same behavior independent of match | Bounded retry |
| Malformed/unsupported selector | Generic invalid-request envelope | No predicate-specific match detail | Correct request; repeated abuse throttled |

The accepted envelope means only that the request passed the external request gate; it does not prove a match or authorize disclosure. If rate limiting is externally visible, it applies before match-dependent work. Exact status, canonical body bytes, content type, cache-control, permitted headers, retry semantics and correlation-ID format MUST be normative. Correlation IDs are random and non-correlatable. No selector, commitment, candidate reference or match state enters ordinary telemetry.

### 3.2 Enforceable budgets

Each provider/database profile publishes a machine-readable budget for request size, selector count, concurrent searches, per-actor/destination rate, statement timeout, lock timeout, cancellation deadline, result cardinality, response size and outstanding candidate references.

Enforcement uses concrete supported controls: gateway rate budgets, source-side semaphores, PostgreSQL statement/lock timeouts, server-side cancellation, bounded indexed plans and result caps. Query cost and rows examined may be measured, but MUST NOT be called hard limits unless enforceable. Unenforceable dimensions are explicit residual risks with owners.

Timeout/cancellation MUST stop server-side work and verify termination before releasing capacity. A client timeout alone is insufficient. Cache, plan, lock and resource behavior are assessed for existence side channels. Audit records policy versions and outcomes without raw selectors.

### 3.3 Candidate-reference lifecycle

Candidate references are opaque, request-scoped, short-lived and non-bearer. States are:

CREATED → AUTHORIZATION_PENDING → CONSUMED

Terminal alternatives: EXPIRED, REVOKED, DENIED and ABANDONED.

Creation binds one source tenant/resource, actor/issuer, destination tenant/branch, selector request, action, purpose, policy, projection, generation and expiry. The reference is random; only a protected hash/verifier is persisted.

Candidate authorization atomically checks the binding and current generation and consumes the reference exactly once. Concurrent redemption permits at most one successful transition. Duplicates return the same non-sensitive operation outcome and never repeat the source read. Consumed, expired, revoked or cross-context references cannot be rebound or used through another endpoint. Restart preserves terminal state; missing state fails closed.

**Closure evidence:** exact response contract, provider budget profiles, server-side cancellation proof, reference state machine and differential response/replay tests.

## 4. DBID-R21 — Transactional source-read and release fencing

### 4.1 Separate permissions and states

Search permission, candidate authorization, source materialization and network release are separate authorities. Search authorization does not authorize candidate disclosure; candidate authorization does not authorize an unbounded read; an artifact digest does not authorize release.

Proposed source lifecycle:

SEARCH_AUTHORIZED → CANDIDATE_AUTHORIZED → READ_INTENT_COMMITTED → RESOURCE_READ_COMMITTED → ARTIFACT_SEALED → RELEASE_AUTHORIZED → RELEASE_STARTED → DELIVERY_CONFIRMED

Exceptional states include DENIED, REVOKED_BEFORE_READ, READ_ABORTED, ARTIFACT_QUARANTINED, RELEASE_BLOCKED, OUTCOME_UNCERTAIN and RECONCILIATION_REQUIRED. Every transition binds generation vector, operation, actor, destination, projection and policy.

### 4.2 Same-consistency-domain read fence

The protected read MUST be fenced by the authoritative source authorization generation in the same transactional consistency domain as the resource read. Cache or earlier application checks are insufficient.

For a PostgreSQL source database, the proposed baseline is a dedicated authorization-epoch row (or equivalent authoritative record) updated by every relevant revocation. The read transaction:

1. begins at a specified isolation level;
2. obtains the required lock on the epoch record and verifies the full generation vector and operation binding;
3. checks candidate authorization, destination, purpose, projection and expiry against the same authoritative state;
4. performs the narrow protected query and writes durable read evidence under the same transaction or a formally equivalent transactional outbox protocol;
5. atomically commits read evidence and permitted artifact-staging state.

The supported PostgreSQL version's lock mode and isolation level must be selected and proven. The design must prevent a stale transaction snapshot from seeing an old generation while reading protected rows. If generation authority spans databases/services, a distributed fencing protocol is required; independent local transactions are not atomic.

### 4.3 Revocation ordering

Revocation updates the same authoritative generation under a conflicting serialization mechanism. Proposed ordering:

- If revocation commits first, the read sees the newer generation and aborts before protected materialization.
- If the read obtains the serialization lock first, revocation waits for the bounded read transaction or follows an approved cancellation protocol. Audit records which operation linearized first.
- Connection loss or uncertain commit becomes OUTCOME_UNCERTAIN; the system does not assume no read occurred.
- Read transactions are bounded; revocation cannot wait indefinitely.

A read authorized before revocation may complete before revocation becomes effective. This residual interval is explicit and requires security/privacy/legal/clinical acceptance. Data already materialized or delivered cannot be recalled.

### 4.4 Artifact release is a second fence

Artifact sealing binds content digest, projection, source resource, operation and generation. Before outbox claim and again at release, the dispatcher validates current generations, artifact status, destination and fencing sequence. Revocation before release blocks a new send and quarantines the artifact unless an approved policy says otherwise.

Release state transitions serialize with revocation. Once a network write begins, bytes may be partially or fully received; outcome is OUTCOME_UNCERTAIN until delivery evidence resolves it. No recall claim is permitted.

Tests deterministically race revocation before search, candidate authorization, read lock, during read, after query/before commit, after read/before seal, before outbox claim, before socket write, during send and after delivery/before acknowledgement. They cover failover, stale workers, duplicate workers, snapshot isolation, process death and uncertain commits.

**Closure evidence:** database-specific transaction diagrams, isolation/locking proof, revocation ordering, failure-injection results and accepted residual risk.

## 5. DBID-R22 — Cluster-wide PostgreSQL identity and isolation

PostgreSQL roles are cluster-wide. Every LOGIN identity therefore has a cluster-unique immutable principal ID bound to tenant, database, workload and credential version. Role names are labels, not authorization identity. The registry includes all runtime, control-plane, template, provisioning, migration, backup, monitoring, provider and emergency roles. Revoked identities are tombstoned and never reassigned.

The cluster policy enumerates every database, including tenant databases, postgres, template and provider/control databases. For each LOGIN role/database pair, the verifier computes effective CONNECT and TEMP privileges including PUBLIC, direct grants, inherited memberships, grant options and ownership. New databases remain inaccessible to application/source/destination workloads until ACL, owner, role graph and service binding are verified. Template defaults are tested.

Every tenant LOGIN role is denied connection to every other tenant database and control database unless a narrowly scoped approved exception exists. A source authorization service connects only to its own source tenant database. A destination service cannot open a foreign database using its own or a shared global runtime credential.

The verifier evaluates role attributes, membership grantor, ADMIN OPTION, INHERIT, SET ROLE, ownership, role/database creation, replication, bypass-RLS and all paths to privileged roles across the entire cluster. Provisioning/migration identities cannot create cross-tenant grants outside a controlled approved workflow.

A proxy/pooler is supported only if server-observed PostgreSQL identity and tenant binding remain attributable for every transaction. Shared upstream identities are rejected unless an independently verifiable tamper-resistant per-request binding is enforced at the trusted proxy and database boundary. application_name, custom GUCs and connection tags alone are not authority.

**Closure evidence:** cluster-wide role registry, all-database CONNECT/TEMP matrix, transitive membership verifier, provisioning sequence and cross-tenant negative tests for every supported topology.

## 6. DBID-R23 — Strict signed manifest, encryption and chunk profile

### 6.1 Canonical manifest

Each wire-profile version selects one canonical manifest encoding. Proposed interoperable baseline: strict UTF-8 JSON using a named canonicalization standard such as RFC 8785 JCS, subject to validation and approval. An alternative must provide equivalent byte-level rules and test vectors.

The schema specifies exact names/types, required/optional fields, maximum lengths, integer ranges, timestamp syntax, byte-string representation, duplicate-key rejection, unknown-field rejection and canonicalization. Floating-point values are prohibited in security-sensitive fields. Parsing rejects non-canonical encodings rather than silently normalizing signed input.

### 6.2 Signature profile

Signature input is a domain-separated byte string containing a fixed protocol label, profile ID, schema version and digest of canonical manifest bytes excluding the signature field. Exact prefix encoding, digest/signature algorithms and key lifecycle are selected from a governance-approved registry. Verifiers reject unknown, deprecated, weak or mismatched combinations; callers cannot request fallback algorithms.

The signature binds source, destination, actor authorization reference, resource, projection, operation, content digest, transport digest, chunk profile, key ID, generation and expiry. Signature proves integrity and key possession, not clinician authority or destination commit.

### 6.3 Recipient-bound encryption

Encryption metadata binds recipient immutable cryptographic identity, destination tenant/branch, artifact ID, operation and profile. These values are included in authenticated associated data using unambiguous canonical encoding. Recipient verifies associated data against its authenticated identity and signed manifest before accepting plaintext.

Envelope specifies content-encryption algorithm, key-wrapping algorithm, recipient key ID/version, wrapped key, nonce/IV, tag, ciphertext length and associated-data digest. Nonce uniqueness is mandatory for the selected algorithm/key scope; reuse is a hard reject and security incident. Key rotation and compromise response are governance-owned. Caller-selected arbitrary key IDs are prohibited.

### 6.4 Deterministic chunks and evidence types

Chunking is disabled unless an allowlisted versioned profile is negotiated. Each leaf digest covers a domain-separated encoding of profile ID, artifact ID, zero-based index, chunk count, byte length and exact bytes. Aggregate construction is deterministic: ordered leaves, distinct internal-node domain label, fixed left/right ordering, defined odd-node handling and defined empty-artifact behavior. Manifest records algorithm, leaf count, total length and root. An ordered concatenation alternative is allowed only with a fixed length-prefix and domain-separation formula.

Receiver rejects missing, duplicate, reordered, overlapping, extra, oversized, truncated, cross-artifact or cross-recipient chunks. Reassembly verifies leaves, aggregate root, total length, canonical content digest and envelope digest. Partial content is quarantined.

Source authorization, source artifact manifest, transport integrity, destination receipt, durable commit acknowledgement and pointer-sync completion are separate evidence types. None implies another. Destination acknowledgement binds exact operation, artifact, content digest, recipient, source generation, fencing sequence and durable provenance.

**Closure evidence:** strict schema, canonical byte profile, approved algorithm registry, recipient-bound encryption vectors, deterministic chunk profile and separate receipt/commit tests.

## 7. DBID-R24 — Cluster-wide ACL schema and verifier

### 7.1 Required manifest structure

The policy schema represents the cluster, not one database. Structural illustration only; not an approved ACL or grant instruction.

~~~yaml
schema_version: "REQUIRES_APPROVAL"
policy_id: "tenant-cluster-acl-baseline"
policy_version: "REQUIRES_APPROVAL"
cluster:
  immutable_cluster_id: "exact-cluster-id"
  provider_profile: "approved-profile-id"
  postgres_major_version: "supported-major"
  environment_id: "environment-id"
  inventory_generation: 0
databases:
  - database_id: "immutable-database-id"
    name: "exact-database-name"
    kind: "tenant|control|template"
    owner_role_id: "nonlogin-owner-id"
    connect_policy_ref: "database-policy-id"
    temp_policy_ref: "database-policy-id"
roles:
  - role_id: "immutable-cluster-role-id"
    name: "exact-cluster-unique-role-name"
    tenant_id: "tenant-id-or-null"
    database_scope: ["database-id"]
    credential_version: "version-or-null"
    attributes:
      login: false
      superuser: false
      createdb: false
      createrole: false
      replication: false
      bypassrls: false
      inherit: false
      connection_limit: 0
      valid_until: null
    owner_of: []
memberships:
  - member_role_id: "role-id"
    granted_role_id: "role-id"
    grantor_role_id: "role-id"
    admin_option: false
    inherit_option: false
    set_option: false
    approval_ref: "evidence-id"
database_acl:
  - database_id: "database-id"
    grantee_role_id: "role-id-or-public"
    grantor_role_id: "role-id"
    privileges: ["CONNECT"]
    grant_options: []
objects: []
default_privileges: []
exceptions: []
attestation_policy:
  required_inventory_generation: 0
  verifier_profile: "approved-verifier-profile"
  expires_at: "RFC3339 timestamp"
~~~

The production schema defines exact enums and semantics for role attributes, membership options, database/object privileges, object identity and default privileges. It includes database ACLs for every database, PUBLIC policy, role creation/alteration authority, grantor, grant options, ownership and creator identities. Unknown fields fail validation.

### 7.2 Effective privilege algorithm

For each supported PostgreSQL major/provider profile, the verifier inventories all cluster roles/databases and normalizes role attributes and validity; direct/transitive memberships and grantor controls; database CONNECT/TEMP ACLs and ownership; schema and object ACLs, owners and grant options; default ACLs per creating role/schema/object class; routines and SECURITY DEFINER ownership/search-path safety; extensions; FDW, foreign servers, user mappings, dblink and other cross-database/network features; provider-managed roles/objects and evidence.

It computes effective capability paths: assume role, grant role, create object, alter ACL, connect database and execute privileged routine. It includes PUBLIC and implicit owner powers, not just explicit ACL text. It searches the whole cluster for tenant runtime identities with access to another tenant database or privileged role.

Default privileges are evaluated for every object creator, including migration, extension, runtime, maintenance and provider automation identities. New objects are checked after every migration/extension operation. Unknown catalog classes, unobservable provider privileges, unsupported versions or incomplete inventory produce UNKNOWN/FAIL until an approved adapter proves coverage.

Exceptions are exact cluster/database/principal/object/privilege tuples with grantor, reason, independent approvers, evidence and expiry. Unbounded wildcards are prohibited. Exceptions cannot imply cross-tenant access. Expired, self-approved, ambiguous or unsupported exceptions fail closed.

Signed conformance binds cluster ID, database/role inventory generation, policy digest, migration/object-creator inventory, catalog snapshot, verifier/adapter build, exception expansion and normalized result. An independent oracle validates high-risk role closure and cross-database calculations.

**Closure evidence:** strict cluster-wide schema, PostgreSQL-versioned catalog adapter, role/membership fixtures, provider evidence coverage and independent verifier oracle.

## 8. DBID-R25 — Independent attestation, freshness and rollback protection

### 8.1 Separation of duties

Attestation distinguishes policy author, infrastructure operator, identity issuer, inventory collector, verifier builder, verifier runner, evidence signer, trust-root administrator and release approver. No single principal may change protected configuration and solely certify it.

Attestation keys are managed outside tenant runtime trust under approved KMS/HSM or equivalent custody. Creation, rotation, revocation, compromise response and recovery require dual control and immutable audit. Key IDs are immutable; revoked identities cannot be reactivated.

### 8.2 Monotonic freshness

Each domain maintains monotonic generations for trust graph, coverage manifest, IAM/network snapshot, database role/ACL catalog, verifier build, policy and exception set. A trusted freshness authority records latest accepted generation and digest. Consumers reject expired/stale/lower-generation attestations, same-generation different-digest, revoked signer keys or missing required sources.

A signed PASS is valid only for exact graph/policy/catalog/verifier generations and deployment profile. Relevant mutation invalidates prior PASS or triggers re-verification. Delayed event delivery requires a bounded freshness interval owned by governance and supported by authoritative source guarantees.

The verifier cannot update its own trusted latest-generation checkpoint. Rollback of verifier, root, policy, catalog snapshot or evidence store is detected through an independently controlled monotonic checkpoint and append-only chain. Failure to reach freshness authority means UNKNOWN/RESTRICTED, not use of stale PASS for new source disclosure.

### 8.3 Provenance and retention

Verifier builds are reproducible or independently attested, pinned by immutable digest, reviewed and deployed through a separate protected pipeline. Evidence binds source snapshots, collection coverage, policy/graph digests, verifier build, adapter versions, signer identity, generation, time, expiry, findings and limitations.

Evidence is append-only or tamper-evident with controlled access and approved retention/residency. Re-verification triggers include IAM/network/DNS/route, role/ACL/membership/default privilege, database creation, migration/extension, proxy/pooler, key, verifier, provider API, restore or evidence-gap changes.

Independent verification checks cryptographic validity and semantic completeness. Signature validity cannot turn incomplete coverage, UNKNOWN inputs or unapproved exceptions into PASS.

**Closure evidence:** separation-of-duties matrix, trust-root lifecycle, monotonic checkpoint protocol, verifier provenance, freshness/rollback tests and independent evidence chain.

## 9. DBID-R26 — End-to-end source/destination lifecycle

### 9.1 Canonical operation envelope

One immutable operation ID links source authorization, candidate, read intent, resource read, artifact, delivery, destination import, commit acknowledgement and pointer synchronization. Durable operation record binds source/destination tenant and branch, source pointer/branch, actor authorization, purpose/action, policy/protocol versions, source generation and fencing sequence, projection, content/manifest digests, artifact ID, destination idempotency key, provenance marker, state and evidence.

Idempotency identity follows the approved tuple: destination tenant/branch + validated source pointer + source branch + protocol version. Record additionally binds content digest and generation. Demographics, ABHA, phone, name or DOB are never proof of source identity or a substitute for this idempotency identity.

### 9.2 State and authority matrix

| Stage | Authority | Durable evidence | Retry rule |
|---|---|---|---|
| Search authorization | Source | Search authorization, selector request, generation | New bounded authorization; no reuse after expiry |
| Candidate authorization | Source | Candidate binding and one-time consumption | Duplicate returns same outcome; no second read |
| Read/materialization | Source | Transactionally fenced read and exact projection | Uncertain commit requires reconciliation; no blind reread |
| Artifact seal | Source | Canonical digest, manifest and generation | Exact replay only under approved strategy |
| Delivery | Source/transport | Send attempt and outcome | Network uncertainty is not delivery success |
| Receipt | Destination edge | Signed recipient-bound receipt | Duplicate receipt idempotent |
| Import validation | Destination | Signature, recipient, policy, digest, generation and provenance validation | Reject or quarantine invalid/stale artifact |
| Destination commit | Destination | Atomic clone, provenance and operation marker | Unique claim; retry re-reads durable state |
| Commit acknowledgement | Destination | Signed ack for exact operation/artifact/digest/generation | Ack resend only; no new clone |
| Pointer synchronization | Control/index owner | Verified pointer update and source link | Reconcile separately; not COMPLETED |
| Final completion | Coordinator | Verified commit ack and pointer evidence | COMPLETED only after both verified |

### 9.3 Revocation after artifact creation

- Revocation before source read: DBID-R21 denies the read.
- Revocation after materialization but before release: block release unless an approved policy permits the already-authorized artifact; otherwise quarantine.
- Revocation after possible delivery but before destination commit: destination cannot infer current authority solely from a previously valid signature. It applies an approved acceptance rule bound to source generation and artifact issuance. If freshness is unknown, quarantine and request source-authority reconciliation. A new source read requires fresh authorization.

Whether an already-disclosed immutable artifact may be committed after revocation is a clinical/privacy/legal decision. Proposed default is quarantine pending authorized review, not automatic import, deletion or activation. Demographic match cannot override quarantine.

### 9.4 Retry strategy and recovery

The prior Strategy A/B choice remains pending:

- **Strategy A:** exact replay of immutable recipient-bound encrypted artifact with approved retention and fresh destination acceptance/revocation check; no content mutation or new source read.
- **Strategy B:** no retained PHI artifact; retry requires fresh source authorization and new read/artifact. Expired receipts cannot authorize a source read.

Chosen strategy must be recorded in protocol profile; implicit fallback/mixing is prohibited.

Destination import uses a unique durable idempotency claim. Claim, patient clone, approved related records, provenance and operation marker commit atomically. Existing-patient demographic similarity cannot establish provenance or authorize reuse. Recovery re-reads durable operation/correlation marker and never blindly creates another clone.

Ack loss permits exact acknowledgement regeneration from verified durable commit. Pointer-sync failure remains INDEX_SYNC_PENDING or RECONCILIATION_REQUIRED, never COMPLETED. Stale workers are fenced by monotonic operation generation. No synthetic success, inferred commit, demographic shortcut or unverified pointer update.

Cross-service contract tests verify operation, pointer, generation, projection, manifest digest, idempotency tuple, acknowledgement and quarantine. Failure injection covers revocation, expired receipt, duplicate delivery, uncertain network write, destination crash before/after commit, ack loss, pointer failure, stale worker, replay and recovery. Assertions prohibit duplicate clone, false completion, unauthorized new read and silent quarantine bypass.

**Closure evidence:** canonical state/authority matrix, approved Strategy A/B decision, exact idempotency contract, cross-service tests and independent recovery review.

## 10. Consolidated closure and remaining blockers

| Finding | Resolution proposal | Closure evidence |
|---|---|---|
| DBID-R19 | Complete inventory and transitive control graph | Independent coverage, path enumeration and mutation tests |
| DBID-R20 | Executable response/budget/reference contract | Provider budget, outcome matrix and anti-enumeration tests |
| DBID-R21 | Transactional read and release fences | Database ordering proof and interleaving tests |
| DBID-R22 | Cluster-wide role/database ACL model | Cross-database verifier and negative connection matrix |
| DBID-R23 | Canonical signed/encrypted/chunked wire | Strict schema, algorithm registry and cross-language vectors |
| DBID-R24 | Complete cluster-wide ACL manifest | Catalog adapter, effective privilege oracle and mutation tests |
| DBID-R25 | Independent attestation and freshness | Trust-root, rollback and verifier provenance evidence |
| DBID-R26 | End-to-end lifecycle and recovery | State matrix, idempotency and failure-injection tests |

This proposal does not close findings by assertion. DBID-06 through DBID-08 from PR #45 remain separate. CAN-01 and CAN-02 remain open. AUD-004 remains a release blocker.

## 11. Governance and implementation gates

Named authorities must decide provider/coverage and inventory independence; selector types and public response semantics; query budgets and residual side-channel risk; PostgreSQL isolation and revocation ordering; cryptographic encoding/algorithms/key custody; cluster-wide ACL baseline and exceptions; attestation freshness/retention; Strategy A/B and post-revocation acceptance; quarantine clinical workflow and retention/deletion.

D-01 through D-14 remain formally pending unless separately approved by designated product, clinical, security, privacy/legal and operational authorities. D-11 project direction YES includes local cross-branch imports in intended scope, but is not formal governance approval. Emergency federation remains disabled absent separate approval.

Before implementation require independent review, formal decisions, provider-specific threat model, validated source/destination transaction design, approved wire/ACL profiles, independent evidence chain, isolated negative-path/failure tests, privacy/clinical acceptance and separate explicit implementation authorization.

## 12. Explicit non-authorization

This document authorizes documentation and independent design review only. It does NOT authorize runtime code changes, SQL execution, database/role/ACL/network changes, credential or secret-manager operations, production access, patient-data access, partner onboarding, trust/key provisioning, federation activation, emergency access, pilot, deployment, release or merge.

PR #53 remains draft and unmerged. This proposal is intended to be a draft, unmerged follow-up. All existing release blockers and governance gates remain in force.
