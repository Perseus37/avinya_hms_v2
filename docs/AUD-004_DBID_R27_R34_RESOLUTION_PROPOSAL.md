# AUD-004 DBID-R27–DBID-R34 Resolution Proposal

**Status:** DESIGN PROPOSAL — NOT IMPLEMENTATION APPROVAL  
**Parent:** PR #55 — Independent review of DBID-R19–DBID-R26  
**Architecture:** database-per-tenant; no schema-per-tenant conversion proposed.  
**Release status:** AUD-004 remains a release blocker.

## 1. Purpose and decision posture

This proposal responds to DBID-R27 through DBID-R34. It converts the residual findings into concrete data contracts, state transitions, transaction ordering, evidence requirements and test obligations.

This is not a claim that the proposed controls exist or that production infrastructure satisfies them. Values that depend on a provider, deployment topology, security authority, clinical policy or legal retention decision remain explicitly unapproved. A missing required profile value means NOT_READY; it must not be replaced by a permissive default.

The most important correction is DBID-R29: a database transaction cannot atomically commit a remote socket write. The design therefore defines two separate linearization points—source materialization and authorization to begin release—and explicitly treats any race after release-start as an irreversible/uncertain delivery boundary. It does not promise that revocation can recall bytes already handed to the transport.

## 2. DBID-R27 — Closed-world inventory and transitive control graph

### 2.1 Root-of-scope manifest

A coverage manifest MUST begin from independently attested scope roots, not from the inventory returned by a single project-local API. The schema is versioned and contains:

| Field | Requirement |
|---|---|
| manifest_id, schema_version | Immutable manifest identity and parser version |
| organization_roots[] | Provider organization/account/tenant roots with immutable provider IDs |
| regions[] | Explicit enabled, disabled and unsupported regions |
| services[] | Provider service inventory, API version and inclusion/exclusion status |
| identity_roots[] | Human, workload, federation, token-exchange and emergency identity authorities |
| network_roots[] | IPv4/IPv6, DNS, routing, peering, private endpoint, proxy and service-mesh authorities |
| data_roots[] | PostgreSQL clusters, databases, templates, poolers, backups and provider management plane |
| control_roots[] | CI/CD, orchestration, host agents, secret/KMS, monitoring, migration and support planes |
| evidence_sources[] | Source identity, scope, API version, pagination/snapshot proof, owner and independence class |
| exclusions[] | Exact excluded service/resource class, rationale, approver, expiry and residual risk |
| completeness_attestation | Independent root-scope evidence, collection generation, digest, signer and expiry |

Every root has an immutable provider ID, parent relationship, source-of-authority, accountable owner and independent approver. Account/organization enumeration MUST be obtained from the provider's highest applicable authoritative scope (for example, organization or billing-root enumeration) and reconciled with project/subscription inventories. If the provider does not expose a complete root inventory, the coverage claim is UNKNOWN and the deployment cannot be marked READY.

An empty list is not proof of absence. Every collector reports COMPLETE, INCOMPLETE or UNKNOWN, including pagination completion, API errors, permission scope, snapshot/version token, object count, truncation indicators and collection time. Explicit exclusions are visible and time-bounded; an expired exclusion becomes UNKNOWN.

### 2.2 Canonical graph schema

Each graph node contains: immutable node ID; provider and provider-native resource ID; resource type/version; parent scope; lifecycle state (ACTIVE, DELETING, TOMBSTONED, UNKNOWN); tenant/database scope; authoritative source; first/last observed generation; owner; evidence references; and sensitivity classification.

Each directed edge contains: immutable edge ID; source and target node IDs; capability enum; grantor/issuer; authentication context; tenant/resource scope; conditions; start/expiry; approval/evidence reference; authoritative mutation source; and status. Capability enums include CONNECT, AUTHENTICATE_AS, ASSUME_ROLE, EXCHANGE_TOKEN, IMPERSONATE, MINT_CREDENTIAL, READ_SECRET, USE_KEY, MUTATE_IDENTITY, MUTATE_WORKLOAD, MUTATE_NETWORK, MUTATE_DNS, MUTATE_PROXY, MUTATE_DATABASE, GRANT_ROLE, ALTER_OWNER, ALTER_ACL, ALTER_POLICY, ALTER_VERIFIER, ALTER_EVIDENCE and PROVIDER_SUPPORT.

Provider-native IDs are normalized by a versioned adapter without losing the original ID. Deleted resources remain tombstones for the evidence retention period. Conflicting source observations become CONFLICT/UNKNOWN; precedence cannot be guessed from collection order. An unobservable edge is UNKNOWN, never absent.

### 2.3 Transitive closure and completeness

The graph engine computes transitive reachability over delegation, nested groups/roles, token exchange, workload impersonation, host administration, network mutation, secret/key access, database role mutation, verifier deployment and evidence-store mutation. Cycles are detected and reported; they are not silently truncated. Time-bounded edges are evaluated at both current time and every relevant overlap interval. Composed capabilities are retained with their full path and evidence.

Coverage attestation binds (a) the root-of-scope proof, (b) all collector snapshots and scopes, (c) normalized nodes/edges, (d) exclusions, (e) adapter/verifier build digests and (f) the graph result. An independent reviewer or verifier must reproduce the scope reconciliation and graph digest using separately obtained root evidence. The collector or administrator being evaluated cannot be the sole source of proof for its own completeness.

A readiness report states expected and observed counts by root/resource class, source pagination completion, exclusions, unknowns, conflicts, graph paths to protected assets and principals able to alter their own evidence. Any UNKNOWN root, incomplete collector, unexplained count mismatch, unapproved exclusion, unknown transitive path or unverified verifier build blocks READY. Negative tests introduce a hidden account, second region, IPv6 route, delegated role, shared runner, token-exchange path, stale/deleted resource, truncated page and evidence-source disagreement.

**Closure evidence:** provider-specific root schema and scope proof, complete collector inventory, canonical graph schema, independent reconciliation, reproducible transitive closure and omission tests.

## 3. DBID-R28 — Executable selector contract, budgets and candidate redemption

### 3.1 Public outcome profile

The source exposes no match-dependent result before candidate authorization. For all syntactically valid, authenticated, in-budget searches, the public pending outcome is the same canonical response:

- HTTP status: 202.
- Content-Type: application/json.
- Cache-Control: no-store.
- Body schema: `{"status":"accepted","request_id":"<random-opaque-id>"}`.
- No candidate count, match/no-match bit, source name, candidate reference, selector echo, per-source result or match-dependent header.
- The request ID is random, short-lived and not a selector-derived commitment.

No-match, candidate-denied and candidate-pending cases use the same status, body shape and allowed headers. A request is not proof of a match. A generic service-unavailable result (503) is reserved for source/policy/audit unavailability and partial fan-out; rate rejection (429) is decided before selector evaluation and is not match-dependent; malformed request (400) reflects schema validation only. Error bodies use fixed codes and do not disclose which selector component matched. No-store applies to all responses. Retry-After is emitted only from a fixed provider profile and not varied by match outcome.

The exact response schema, field ordering/canonical serialization, header allowlist and error-code registry are versioned. Any implementation-specific header is denied by default. Differential tests compare status, body bytes, content type, cache headers and timing distributions for match, no-match and denied-candidate cases.

### 3.2 Required budget profile

A provider cannot be activated until the signed profile supplies numeric values for maximum request bytes, selector count, selector input length, requests per actor/destination/time window, concurrent searches, per-source fan-out, statement timeout, lock timeout, server-side cancellation deadline, rows returned, rows examined where enforceable, result bytes, candidate lifetime and outstanding references.

Each value records unit, scope, enforcement point, owner, evidence of enforcement, expiry and overload action. Admission controls occur before source selector evaluation. PostgreSQL statement_timeout and lock_timeout, server-side cancellation, bounded indexed predicates, result caps, source semaphores and gateway rate budgets are required where supported. Query planner estimates or post-hoc query-cost metrics are not represented as hard limits. If a provider cannot enforce a required bound, that profile remains NOT_SUPPORTED or records an explicit residual risk approved by security/privacy; it cannot silently claim equivalence.

Cancellation must be acknowledged by the database/session layer before concurrency capacity is released. Client disconnect or gateway timeout alone does not prove server work stopped. Cache/plan/lock/timing side channels are measured against thresholds in the signed profile; absent thresholds means NOT_READY.

### 3.3 Candidate reference and operation record

The candidate reference is never returned to a browser or end user. It is an internal opaque value carried only over the authenticated source-to-destination service channel. It contains at least 256 bits of cryptographically secure randomness; storage retains only a keyed verifier/hash. It is bound to a single source search operation, source tenant/resource, destination tenant/branch, authenticated destination workload, actor assertion, action, purpose, selector commitment/type, policy version, generation vector, expiry and projection ceiling.

The source creates one durable SearchOperation row with a unique operation ID and idempotency key. Search authorization, selector execution, candidate issuance, candidate authorization and audit events reference that row. The candidate table has a unique verifier, operation ID, resource ID and state. Redemption requires mTLS/workload identity plus the exact bound operation context; caller-supplied resource, destination, purpose, projection or key ID cannot override the stored binding.

Atomic redemption is a compare-and-swap from ISSUED to REDEEMED under the operation row lock and current generation check. A concurrent duplicate returns the same non-sensitive operation status and cannot cause a second read. Cross-operation, cross-destination, expired, revoked or already-consumed references are rejected uniformly. A retry that needs a new source read must obtain fresh source authorization and a new candidate reference.

**Closure evidence:** signed provider budget profiles, canonical HTTP contract, durable operation/reference schema, authenticated channel binding, one-time redemption tests and quantitative side-channel results.

## 4. DBID-R29 — Source-read and release linearization protocol

### 4.1 Two independent linearization points

The design does not claim atomicity between PostgreSQL and a remote network write. It defines two points:

1. **ReadCommit:** the source transaction commits the authorized, bounded protected read evidence and immutable artifact-staging record.
2. **ReleaseStart:** the source release authority commits a one-time authorization permit for a specific artifact and fencing generation immediately before the transport is allowed to begin writing bytes.

A revocation ordered before ReadCommit prevents materialization. A revocation ordered before ReleaseStart prevents a new send. A revocation ordered after ReleaseStart cannot guarantee recall of bytes already accepted by the transport; the result is delivered or OUTCOME_UNCERTAIN and is audited accordingly.

### 4.2 Source authority and generation model

All source-relevant revocation domains are represented in one source-owned authorization authority: issuer/key trust, clinician identity/status/affiliation, destination/workload binding, purpose/action policy, source policy, credential/session state and audit availability. External authorities publish signed changes to this source authority. For any domain that cannot synchronously update or be checked against the source authority, the source MUST treat the domain as unavailable once its approved freshness lease expires and deny new search/read/release operations.

The source authority stores a monotonic generation vector and a current policy digest. Each accepted revocation increments the relevant generation and the aggregate authorization generation in the same transaction that records the revocation event. A mutation is not considered effective/acknowledged by the integration until the source authority has durably advanced its generation. If upstream revocation cannot wait for this acknowledgement, the source must fail closed through a pre-expiry lease/heartbeat contract; the allowed freshness interval is a governance-owned value, not a hidden cache TTL.

### 4.3 ReadCommit transaction profile

The proposed baseline for a PostgreSQL source tenant database is READ COMMITTED with an explicit row-lock protocol; exact server major/provider support must be validated before approval.

- Begin a bounded transaction.
- Lock the source authorization epoch row using a lock mode that conflicts with the revocation UPDATE (for example, SELECT ... FOR SHARE). The lock is held until transaction end.
- Read and validate the current generation vector, operation binding, candidate state, actor/destination, purpose/action, projection and policy digest after obtaining the lock. Do not use a snapshot created before the lock to validate authorization.
- Execute only the approved protected projection. The query and serializers cannot load unapproved relationships.
- Insert a durable read/disclosure-intent event and artifact-staging operation row in the same database transaction as the protected read's materialization evidence. The staged artifact is not yet releasable.
- Commit. This commit is ReadCommit; it orders against revocation because revocation must update/lock the same epoch row.

Revocation updates the epoch row under an incompatible lock. If revocation commits first, the read observes the new generation and aborts. If the read holds the lock first, revocation waits for the bounded transaction; the read commits or aborts, then revocation advances. The audit records this ordering. Transactions have hard statement/lock/overall deadlines; deadlock, serialization, timeout or uncertain commit results in abort/reconciliation, never inferred success.

This baseline applies only when all relevant generation state is truly in the same source database consistency domain. If a revocation domain resides elsewhere, a synchronous source-owned generation update/lease protocol is required; independent databases and caches are not treated as one transaction. The chosen isolation/lock semantics require tests on every supported PostgreSQL/provider profile.

### 4.4 ReleaseStart transaction and unavoidable transport boundary

The source stores an artifact-release row with states SEALED, RELEASE_PENDING, RELEASE_PERMITTED, RELEASE_STARTED, DELIVERY_CONFIRMED, OUTCOME_UNCERTAIN, BLOCKED and QUARANTINED. It binds artifact digest, recipient, destination tenant/branch, source generation, operation ID, projection and fencing sequence.

A dispatcher first claims a lease with a monotonically increasing fencing sequence. Immediately before transport write, it opens a short transaction, locks the same authorization epoch and artifact-release row, checks current generation, recipient, artifact status, lease owner/sequence, expiry and policy, then atomically changes RELEASE_PENDING to RELEASE_STARTED and writes a signed release permit/outbox event. This commit is ReleaseStart. Only the worker holding the returned permit and current fencing sequence may invoke the transport adapter. Duplicate/stale workers cannot obtain a permit.

A revocation ordered before the ReleaseStart transaction obtains the epoch lock first and causes the release check to fail. If ReleaseStart commits first, revocation is ordered after release authorization; bytes may be sent even if revocation commits before the first byte reaches the remote peer. The transport adapter must make the interval from permit to first write bounded and observable, but no finite bound is represented as atomicity. If the process dies or the connection fails after ReleaseStart, state becomes OUTCOME_UNCERTAIN; no second send occurs automatically unless the selected retry strategy and destination evidence permit exact replay. A cancellation may stop a queued/active stream where the transport supports it, but cannot recall bytes already transmitted or buffered by intermediaries.

The release permit is one-use, recipient-bound and short-lived; it cannot be transferred to another worker or operation. The source never changes RELEASE_STARTED back to RELEASE_PENDING merely because an acknowledgement is absent. Reconciliation obtains destination receipt/commit evidence or leaves the operation uncertain/quarantined.

### 4.5 Required concurrency model

A deterministic model and database integration tests cover:
- revocation wins before read lock; read observes new generation and aborts;
- read lock wins; revocation blocks until ReadCommit/abort;
- revocation wins before ReleaseStart; no permit and no socket write;
- ReleaseStart wins; later revocation cannot claim to recall bytes and produces correct audit/outcome;
- stale lease holder, duplicate dispatcher, expired permit, process crash between permit and socket, partial write, lost ack and destination timeout;
- upstream revocation unavailable, stale lease, epoch-store outage, deadlock, database failover and uncertain commit.

Assertions must prove no protected read without ReadCommit, no socket write without a unique valid ReleaseStart permit, no duplicate automatic send, no false DELIVERY_CONFIRMED and no false COMPLETED. Security/privacy/clinical authorities must explicitly accept the post-ReleaseStart irreversibility window before any implementation approval.

**Closure evidence:** PostgreSQL-specific lock/isolation proof, source-authority generation contract, release permit protocol, executable interleaving model, failure-injection results and formal acceptance of residual transport race.

## 5. DBID-R30 — Immutable PostgreSQL principal and authenticated session binding

A separate principal registry is authoritative for workload-to-database identity. Each record contains immutable principal UUID, tenant ID, permitted database IDs, workload identity issuer/subject, deployment profile, PostgreSQL cluster ID, LOGIN role immutable registry ID, credential version, authentication method, valid-from/expiry, status and evidence. PostgreSQL role name is an attribute, not the principal key.

The connection broker binds workload identity and requested tenant/database to the registered principal before credential retrieval. PostgreSQL authentication establishes a LOGIN role; the trusted broker/pooler records a tamper-evident session-binding event containing the authenticated workload, credential version, actual server-authenticated role, cluster/database, connection/session identifier and validity. The database-side role cannot self-assert another tenant or credential version using application_name, custom GUCs or request headers. If a supported proxy cannot preserve independently verifiable per-session identity, that topology is unsupported.

Role creation assigns a new immutable registry ID. Rename retains the same registry identity only through an approved signed migration. Drop/recreate always creates a new identity; name reuse is prohibited. Restore/failover must rebind cluster identity and reverify credentials/roles before READY. Credential rotation creates a new LOGIN principal/role version, blocks new checkout on the old version, drains and terminates old sessions as required, then revokes the old credential. Role IDs and secret versions are never recycled.

The versioned role profile enumerates all server-major attributes, memberships (grantor, ADMIN OPTION, INHERIT, SET), ownership, database/schema/object privileges, PUBLIC, special/provider roles, replication, bypass-RLS, superuser, create-role/database, connection limits and validity. Unsupported or provider-hidden role capabilities yield UNKNOWN. The verifier evaluates effective CONNECT/TEMP for every database, including postgres and templates, and all transitive role paths cluster-wide.

**Closure evidence:** principal registry schema, workload-to-server-session binding proof, supported direct/proxy topology matrix, full role profile and cross-database negative tests.

## 6. DBID-R31 — Normative wire profile and conformance vectors

### 6.1 One profile per protocol version

A protocol version selects exactly one manifest canonicalization, digest/signature suite, encryption suite and chunk mode. No runtime negotiation may silently fall back to another construction. The initial candidate profile is UTF-8 JSON with RFC 8785 JCS canonicalization, SHA-256 content digests, Ed25519 manifest signatures and an approved authenticated-encryption envelope. These are proposed candidates only; security governance must approve algorithm availability, cryptographic module/provider support, key custody and migration before any implementation.

Unknown, deprecated, unapproved or mismatched profile IDs are rejected. The signed manifest includes profile ID and version, source/destination immutable identities, actor authorization reference, resource and projection, operation/idempotency identifiers, generation/fencing sequence, content digest/length, recipient key identity/version, encryption metadata and expiry.

### 6.2 Canonical bytes and signature input

Parsing rejects duplicate JSON member names, invalid UTF-8, non-finite numbers, unsupported numeric ranges, unknown critical fields and non-canonical encodings. Strings are not Unicode-normalized unless the schema explicitly defines normalization for that field; identifiers use field-specific canonicalization. Timestamps use one strict UTC RFC 3339 representation. Byte strings use one specified base64url encoding without padding.

The signature field is excluded from the canonical payload object. Signature input is a fixed ASCII domain label followed by a zero byte, a fixed-width protocol-profile identifier, a zero byte, and the SHA-256 digest of the exact JCS canonical payload bytes. The signature envelope identifies algorithm and immutable signer key ID; those values are themselves covered by the profile-bound manifest fields and verified against the trusted registry. No parser may reconstruct or normalize signed fields differently.

### 6.3 Encryption and recipient binding

Authenticated associated data is the exact canonical encoding of profile ID, artifact ID, source identity, destination tenant/branch, recipient immutable key ID/version, operation ID and content digest. The envelope includes algorithm IDs, key-wrapping metadata, nonce/IV, tag, ciphertext length and AAD digest. Recipient identity is checked against the authenticated destination workload, not a caller-supplied string.

The selected AEAD profile MUST specify nonce generation, uniqueness scope, collision monitoring and behavior at key usage limits. Nonce reuse under the same key is a hard reject and security incident. If the selected algorithm requires a counter-based construction, the counter allocator is durable and single-authority; if random nonces are selected, the profile must prove collision bounds and enforce key rotation limits. Key wrapping, rotation, compromise and decryption authority remain governed separately.

### 6.4 Chunk profile

Chunking is DISABLED in protocol version 1. A single artifact is bounded by the approved maximum payload size. If later required, a new protocol version must define exactly one chunk construction; no "ordered concatenation or Merkle" choice exists within one version. The new profile must specify byte-level leaf and parent encodings, integer width/endianness, length prefixes, odd-leaf behavior, empty content, chunk count/size, order and root verification, with cross-language vectors before activation.

**Closure evidence:** approved wire-profile registry, strict parser schema, exact byte vectors, independent implementations, encryption/AAD/nonce tests and downgrade/recipient-substitution negatives.

## 7. DBID-R32 — Machine-readable cluster-wide ACL manifest and verifier

### 7.1 Normative data model

The ACL policy is a versioned JSON/YAML document validated against a published schema. The following is the required conceptual structure; exact enum values are versioned per supported PostgreSQL major/provider profile:

~~~yaml
schema_version: "acl-policy-v1"
policy_id: "immutable-policy-id"
cluster:
  immutable_cluster_id: "cluster-id"
  provider_profile: "provider-profile-id"
  postgres_major: 0
  inventory_generation: 0
databases:
  - database_id: "immutable-db-id"
    name: "exact-name"
    kind: "tenant|control|template"
    owner_role_id: "nonlogin-owner-id"
    connect_acl:
      - grantee_role_id: "role-id-or-public"
        grantor_role_id: "role-id"
        privileges: ["CONNECT"]
        grant_options: []
    temp_acl: []
roles:
  - role_id: "immutable-cluster-role-id"
    name: "cluster-unique-name"
    tenant_id: "tenant-id-or-null"
    login: false
    superuser: false
    createdb: false
    createrole: false
    replication: false
    bypassrls: false
    inherit: false
    valid_until: null
    connection_limit: 0
memberships:
  - member_role_id: "role-id"
    granted_role_id: "role-id"
    grantor_role_id: "role-id"
    admin_option: false
    inherit_option: false
    set_option: false
schemas: []
objects: []
default_privileges: []
extensions: []
foreign_access: []
exceptions: []
evidence_policy:
  verifier_profile_id: "approved-profile"
  required_generation: 0
  expires_at: "RFC3339"
~~~

The production schema MUST define exact required fields, nullability, enum values, identity keys and uniqueness constraints. Object records identify database, schema, object class, immutable catalog identity where available, exact qualified name, owner, creator, ACL entries, grantor, privilege set and grant options. Wildcard object patterns are prohibited. Default privilege records bind database, schema (including global/default schema scope), creator role, object class, grantee, grantor, privileges and grant options. Exceptions bind exact principal, database/object, privilege, grantor, reason, two independent approvers, evidence and expiry. No exception can authorize cross-tenant access by implication.

### 7.2 Catalog normalization and effective privileges

A PostgreSQL-major-specific adapter emits a deterministic normalized catalog snapshot covering cluster roles/attributes/memberships; all databases and owners; database CONNECT/TEMP ACLs and PUBLIC; schemas and schema ACLs; tables, partitions, views, materialized views, sequences, routines/procedures, types/domains, large objects where supported, extensions, languages, FDW servers/user mappings, foreign tables, SECURITY DEFINER routines, event triggers and provider-managed objects/roles. The adapter also records default ACLs for every role capable of creating objects and all supported object classes.

Effective privilege computation includes owner powers, PUBLIC, direct and transitive membership, ADMIN OPTION, INHERIT, SET ROLE, grant options, grantor authority, database connection rights, schema CREATE/USAGE, object privileges, default privileges, SECURITY DEFINER execution paths and foreign/network access. The algorithm is specified and versioned per PostgreSQL major; unsupported catalog classes or unobservable provider capabilities return UNKNOWN.

An independent verifier consumes the signed policy, independently collected catalog snapshot and adapter build digest. It emits a signed report with cluster ID, policy digest, inventory generation, snapshot ID, normalized catalog digest, verifier build, exception expansion, every effective cross-tenant path, unknown/unobservable items, PASS/FAIL/UNKNOWN and expiry. PASS requires zero unauthorized paths and zero unresolved UNKNOWN items. A separate oracle validates role closure and selected high-risk privilege calculations. New migration/extension/object-creator paths trigger re-verification before tenant traffic is admitted.

**Closure evidence:** schema validation, catalog adapters for every supported major/provider, fixtures for every object/privilege class, independent effective-privilege oracle and cross-database negative tests.

## 8. DBID-R33 — Independent attestation freshness and rollback protocol

Each attested domain maps to an authoritative mutation source and generation owner:

| Domain | Mutation authority | Required invalidation |
|---|---|---|
| Cloud/IAM/workload identity | Provider organization/IAM event source | Identity and trust-graph generation |
| Network/DNS/proxy/orchestration | Provider control-plane audit/config source | Network and workload-path generation |
| PostgreSQL roles/ACLs/objects | Cluster catalog verifier plus privileged DDL audit | Cluster ACL generation |
| Secret/KMS/key trust | Secret/KMS audit and trust registry | Credential/key generation |
| Policy/exceptions | Independently approved policy registry | Policy generation |
| Verifier/adapter/build | Protected build and deployment attestation | Verifier generation |
| Backup/restore | Backup control plane and restore attestation | Restore generation and mandatory full reverify |

A mutation event is accepted only after durable recording and monotonic generation advancement in the attestation authority. Where the underlying provider mutation cannot participate atomically, the integration uses a pre-change deny/freeze or a short-lived attestation lease: if event delivery is delayed, lost or ambiguous, the prior PASS expires conservatively and the affected capability is restricted. Event consumers are idempotent and sequence-aware; gaps, duplicate sequence with different digest or out-of-order generations trigger UNKNOWN and full reconciliation.

The freshness checkpoint is signed by an independent checkpoint authority and witnessed by a separate administrative domain. It binds generation vector, evidence-chain root, policy/coverage/verifier digests, timestamp, expiry and previous checkpoint digest. The witness retains the highest accepted generation/root independently of the primary evidence store. Restoring an older evidence database cannot lower the witnessed generation. A verifier runner cannot sign or witness its own checkpoint.

On freshness-authority outage, event gap, clock uncertainty beyond the approved bound, signer compromise, evidence restore or stale PASS, new source search/read/release is denied or restricted until independent reconciliation. Maximum staleness is set separately for each domain by security/privacy/operations owners; missing values mean zero trusted freshness and NOT_READY. A signer compromise revokes its key, invalidates attestations within its scope and requires re-attestation under a new key with independent review.

**Closure evidence:** mutation-source map, generation transaction/lease design, independent witness protocol, outage/restore recovery, signer rotation and rollback tests.

## 9. DBID-R34 — End-to-end lifecycle and recovery contract

### 9.1 Canonical operation identity

The idempotency tuple is encoded as a versioned canonical structure, not string concatenation:

`IdempotencyV1 = { destination_tenant_id, destination_branch_id, validated_source_pointer_id, source_branch_id, protocol_version }`

The key is a domain-separated digest of canonical bytes under a destination-controlled key; raw demographics are never included. The durable operation row has a unique constraint on the tuple and stores source pointer version, source registry identity, artifact/content digest, provenance digest, generation, fencing sequence and current state. Same tuple + same digest returns the existing operation. Same tuple + different digest is a hard conflict requiring reconciliation; it never overwrites the first operation.

Source-pointer validation checks the source-owned pointer ID, source tenant/branch, version, status, resource reference and source authorization evidence. Pointer version changes create a new validated source reference; caller-supplied branch/resource substitutions are rejected.

### 9.2 State/authority matrix

| State | Authority and durable commit | Permitted next state |
|---|---|---|
| SEARCH_AUTHORIZED | Source search operation and bounded permission | CANDIDATE_ISSUED / DENIED |
| CANDIDATE_AUTHORIZED | Source one-time candidate transition | READ_COMMITTED / DENIED |
| READ_COMMITTED | Source fenced read evidence + artifact staging | ARTIFACT_SEALED / RECONCILIATION_REQUIRED |
| ARTIFACT_SEALED | Source canonical manifest/digest and generation | RELEASE_PENDING / QUARANTINED |
| RELEASE_STARTED | Source one-time release permit and fencing sequence | DELIVERY_CONFIRMED / OUTCOME_UNCERTAIN |
| DELIVERY_CONFIRMED | Authenticated destination receipt bound to artifact | DESTINATION_VALIDATING |
| DESTINATION_VALIDATING | Destination validates recipient, signature, freshness, policy, digest and source status | DESTINATION_COMMITTING / QUARANTINED / REJECTED |
| DESTINATION_COMMITTING | Destination unique operation claim and transaction | DESTINATION_COMMITTED / RECONCILIATION_REQUIRED |
| DESTINATION_COMMITTED | Durable clone + provenance + operation marker + commit digest | ACK_PENDING |
| ACK_PENDING | Destination signed commit acknowledgement | ACK_VERIFIED |
| ACK_VERIFIED | Source/control owner verifies exact acknowledgement | POINTER_SYNC_PENDING |
| POINTER_SYNC_PENDING | Pointer/index owner commits exact versioned pointer update | COMPLETED |
| QUARANTINED | Authorized clinical/privacy workflow | Explicit reviewed disposition only |
| RECONCILIATION_REQUIRED | Dual-controlled operator workflow | Resume only from verified durable evidence |

Each transition has an owner, required evidence, generation/fencing precondition, idempotency behavior, timeout and failure state. No caller may set state directly. Unknown state, missing evidence or conflicting digests fail closed.

### 9.3 Destination transaction

The destination first claims the unique idempotency tuple in a durable operation table. A unique constraint serializes concurrent requests. In one database transaction it writes the operation claim (or locks its existing row), creates the patient clone and only explicitly approved related records, writes immutable source provenance and the operation correlation marker, and records the canonical committed payload/provenance digest. The transaction commits atomically.

On a duplicate request, the destination re-reads the operation row and provenance marker in a fresh transaction. If tuple and digest match a committed operation, it returns the same durable result and does not clone again. If tuple matches but digest/provenance differs, it enters RECONCILIATION_REQUIRED and does not mutate the patient. If commit outcome is uncertain, the worker re-reads the unique operation marker and related provenance; it never assumes rollback or repeats the clone blindly.

The signed destination acknowledgement is generated only after a fresh durable re-read confirms patient clone, provenance, operation marker and digest. It binds destination identity, source pointer/version, source branch, protocol version, operation ID, idempotency tuple digest, artifact/content digest, provenance digest, source generation, destination commit generation and fencing sequence. Ack resend reproduces the same acknowledgement for the same committed evidence; it does not repeat the transaction.

Pointer synchronization is a separate idempotent state transition. The pointer owner checks the exact source pointer/version, destination operation, acknowledgement and fencing sequence. COMPLETED is set only after the pointer update is independently re-read and verified. Commit acknowledgement alone never means pointer sync succeeded.

### 9.4 Revocation and strategy decision

Two artifact retry strategies remain mutually exclusive protocol-profile choices:

- **A — retained exact artifact:** retain an immutable recipient-bound encrypted artifact for an approved bounded period. Retry can resend only the exact artifact and digest; destination performs a fresh acceptance check. No content change or new source read occurs.
- **B — no retained PHI artifact:** discard staged payload after the approved boundary. Retry requires a fresh source authorization, new candidate and new source read. Expired receipts never authorize a new read.

A profile must select one; mixed/implicit fallback is forbidden. Strategy A retention and post-revocation acceptance require clinical, privacy/legal and security approval.

If source revocation occurs after artifact creation but before destination commit, destination checks the source's current signed generation/status. If current status cannot be established, it quarantines. If revoked, the default is quarantine pending named clinical/privacy/legal disposition; automatic activation, silent import, deletion or demographic reuse is prohibited. Already disclosed bytes cannot be recalled. Any permitted commit after revocation requires an explicit policy decision and auditable approval bound to the exact artifact and operation.

Recovery after receipt expiry requires fresh source authorization for any new source read. Exact replay of an already sealed artifact is permitted only under the selected Strategy A profile and current destination acceptance policy. Ack loss allows acknowledgement regeneration from verified durable commit. Pointer failure remains POINTER_SYNC_PENDING. No false COMPLETED, synthetic success, demographic identity shortcut or stale-worker override is allowed.

**Closure evidence:** canonical operation schema/constraints, complete transition table, selected retry strategy, clinical/privacy decision, destination transaction tests, signed-ack conformance and end-to-end failure injection.

## 10. Consolidated finding closure matrix

| Finding | Proposed control | Required independent evidence |
|---|---|---|
| DBID-R27 | Root-of-scope manifest and reproducible transitive trust graph | Provider inventory and independent completeness attestation |
| DBID-R28 | Fixed public outcome profile, numeric budgets and one-time internal candidate redemption | Provider profile and quantitative side-channel/replay tests |
| DBID-R29 | Separate ReadCommit and ReleaseStart serialization points | Database ordering proof and deterministic interleaving tests |
| DBID-R30 | Immutable principal registry and authenticated session binding | Broker/server identity proof and topology tests |
| DBID-R31 | One strict byte-level wire profile; v1 chunking disabled | Independent cross-language cryptographic vectors |
| DBID-R32 | Machine-readable cluster ACL schema and effective-privilege verifier | Catalog adapter and independent oracle |
| DBID-R33 | Mutation-to-generation mapping and independent freshness witness | Rollback, outage and restore tests |
| DBID-R34 | Canonical idempotency tuple and end-to-end state/authority matrix | Destination transaction and recovery evidence |

This proposal does not close findings by assertion. DBID-06 through DBID-08 remain separate. CAN-01 and CAN-02 remain open. AUD-004 remains a release blocker.

## 11. Governance and implementation gates

The following remain formal decisions: provider root inventory/completeness, supported deployment profiles, selector budgets and public response contract, residual timing side channels, PostgreSQL transaction/lock profile, upstream revocation freshness, release-start residual race, principal registry and proxy support, cryptographic algorithms/key custody, ACL exception policy, attestation freshness/retention, artifact retry strategy, post-revocation acceptance, quarantine workflow and clinical/legal retention.

D-01 through D-14 remain pending unless separately approved by designated product, clinical, security, privacy/legal and operations authorities. D-11 project direction YES includes local cross-branch imports in intended scope but is not formal governance approval. Emergency federation remains disabled absent separate approval.

Before implementation require independent review, approved provider-specific threat model, formal governance decisions, transaction and concurrency proof, cryptographic conformance vectors, complete ACL verifier, independent attestation chain, clinical/privacy acceptance, test evidence and separate explicit implementation authorization.

## 12. Explicit non-authorization

This document authorizes documentation and independent design review only. It does NOT authorize runtime code changes, SQL execution, database/role/ACL/network changes, credentials or secret-manager operations, production access, patient-data access, partner onboarding, trust/key provisioning, federation activation, emergency access, pilot, deployment, release or merge.

PR #55 remains draft and unmerged. This proposal is intended as a draft, unmerged follow-up. All existing release blockers and governance gates remain in force.
