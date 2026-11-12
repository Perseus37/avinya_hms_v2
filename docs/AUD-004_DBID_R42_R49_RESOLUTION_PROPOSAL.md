# AUD-004 DBID-R42–DBID-R49 Resolution Proposal

**Status:** DESIGN PROPOSAL ONLY — NOT IMPLEMENTATION APPROVAL  
**Parent review:** PR #59  
**Release status:** AUD-004 remains a release blocker.

## 1. Purpose

This documentation-only proposal provides concrete contracts for the eight residual findings. The three companion JSON Schema 2020-12 files are proposed machine-readable baselines, not approved production policy. They require PostgreSQL-major/provider validation, independent security review, clinical/privacy/legal review and formal governance before implementation. No production infrastructure, IAM inventory, PostgreSQL catalog, network topology, secrets, backup system or patient data was inspected.

## 2. DBID-R42 — exact source read/revocation ordering

### 2.1 One consistency domain

Use one source-owned PostgreSQL transaction domain and one authorization epoch row per source scope. The row contains a monotonically increasing generation and a canonical versioned vector covering issuer/key trust, clinician identity/status/affiliation, partner/destination, source policy, workload/database binding, credential/session and audit authority. Destination workloads and the control plane cannot update it.

All revocation mutations are applied by the source-owned epoch writer. Each mutation updates the vector and increments generation in the same transaction. A single row avoids cross-domain lock-order ambiguity. Sharding into multiple rows is outside this proposal and requires deterministic global lock order, atomic mutation and separate review.

### 2.2 Protected-read protocol

Use PostgreSQL READ COMMITTED. One authenticated source connection and one transaction are used from epoch lock through bounded protected-row fetching. The worker cannot switch connections or continue after losing the transaction.

1. Commit a durable READ_INTENT in a separate transaction before any protected selector resolution or protected-row query. Record operation ID, source scope, actor/destination binding, requested projection, policy version, fencing generation and idempotency correlation; no patient payload.
2. Begin a new READ COMMITTED transaction on the source database.
3. Execute the equivalent of: SELECT generation, generation_vector FROM source_authorization_epoch WHERE source_id = :source_id FOR SHARE.
4. Compare the returned generation/vector with the signed authorization envelope and operation fence. A mismatch aborts. The statement must complete after any lock wait and observe the current committed row version.
5. In the same transaction and connection, while retaining the FOR SHARE row lock, execute the narrowly scoped protected SELECT. Fetch all rows within explicit row, byte and time bounds. No ORM entities, relationship loading, unbounded cursor or alternate connection.
6. Retain the epoch lock until the cursor is fully consumed or cancelled and the read transaction commits or rolls back. Commit is the read-ordering point. Only a separate post-read authorization can permit use or artifact construction.
7. Revocation performs an UPDATE of the same epoch row and commits before revocation is reported complete. The UPDATE's row lock conflicts with the reader's FOR SHARE lock. If revocation commits first, the reader waits and sees the new generation under READ COMMITTED, then aborts. If the reader locks first, revocation cannot commit its epoch change until the read transaction finishes or aborts. This orders read and revocation; it cannot retract a read after commit.
8. Post-read authorization rechecks the complete generation vector and operation state. Any changed generation, missing evidence or ambiguous state quarantines the operation.

The implementation must verify this lock-conflict behavior on every supported PostgreSQL major. Enforce one epoch row per source scope, unique source key, monotonic generation, non-null vector and no runtime update grants except the source revocation authority.

### 2.3 Abort and failure semantics

Connection loss, cancellation, cursor failure, worker termination or transaction abort after rows may have reached the driver is READ_ABORTED_AFTER_FETCH or READ_OUTCOME_UNCERTAIN, never successful. The worker must not use, serialize, log, cache, trace or release the buffer. A new worker cannot inherit the old lock or memory; it must create a fresh read attempt and authorization. Managed runtimes cannot prove physical zeroization, and the system must not claim secure erasure. If a generation cannot be validated, fail closed.

### 2.4 Required interleaving tests

Use two independent PostgreSQL sessions on each supported major. Test revocation before reader lock; revocation holding the update lock while reader waits; reader lock before revocation; revocation after lock but before SELECT; revocation during fetch; final row before commit; connection loss during fetch; read commit followed by newer generation before post-read authorization; and ambiguous epoch-update commit. Assert actual lock and transaction behavior.

## 3. DBID-R43 — enforceable memory-staging boundary

The source read worker is a separate OS/container security principal and deployment unit, not a thread/task. It has no client listener, shared memory, general application IPC, writable shared volume or generic serializer endpoint. Network policy and workload identity permit only the source database, dedicated audit/operation store and specifically approved artifact/egress service.

Use a reviewed raw SQL/Core cursor projection with an explicit field allowlist. ORM entities, identity maps, eager/lazy relationships and generic model serialization are prohibited. Document and test exact driver/version buffering, fetch size, maximum rows/bytes, statement timeout and cancellation behavior. Disable value/parameter debug logging.

The worker holds raw values only in a bounded process-local staging area. The coordinator receives only an opaque operation-scoped artifact handle and state/evidence metadata; it cannot receive row objects or invoke generic serialization. The capability interface exposes only stage, discard and report-outcome operations bound to operation and fencing generation.

Where supported, disable core dumps and swap; use a restricted filesystem, read-only root, minimal capabilities, no shell/debug endpoint, no process namespace sharing and controlled supervisor/host access. Crash reporting, tracing, profiling, metrics and exception formatting must exclude row values, SQL parameters, tokens and artifacts. Host administrators, orchestration agents, monitoring agents, backup operators and container-runtime administrators are part of the trust graph.

These controls do not protect against a fully privileged host/kernel administrator and do not prove allocator/GC zeroization. Unexpected inspection, crash dump, unauthorized egress, buffer escape or worker compromise quarantines the operation and raises incident evidence. Negative tests cover ORM hooks, driver debug output, exception formatting, telemetry, core-dump/swap policy, IPC, filesystem writes, process inspection and network egress, using synthetic fixtures only.

## 4. DBID-R44 — egress acceptance and revocation

### 4.1 Atomic acceptance

The source operation store and authorization epoch must share one transactional consistency domain for permit acceptance and revocation. If they cannot share a transaction, this design is not implementable as written; an eventually consistent cache or separate queue is not an authority.

A one-use permit binds permit ID, operation/artifact IDs, canonical content digest, source, destination workload/tenant/branch, recipient key, purpose/action, projection digest, generation vector, fencing generation, adapter identity, endpoint, nonce, issue time and expiry.

The egress adapter executes one transaction that locks/checks the current epoch row, validates the exact operation/artifact/destination/worker binding and expiry, consumes the unused nonce, and transitions to EGRESS_ACCEPTED. Revocation updates the same epoch row. If revocation commits first, acceptance sees a newer generation and is rejected. If EGRESS_ACCEPTED commits first, the permit was accepted under the prior generation; later revocation prevents new acceptance but cannot promise recall of bytes already handed to transport.

Nonce consumption and EGRESS_ACCEPTED must be in the same transaction. Lost commit acknowledgement is EGRESS_ACCEPTANCE_UNCERTAIN; query authoritative state and never guess or reuse the nonce.

### 4.2 Separate transport evidence

Persist distinct append-only states: EGRESS_ACCEPTED; TRANSPORT_WRITE_ATTEMPTED; BYTES_ACCEPTED_BY_LOCAL_SOCKET; REMOTE_RECEIPT; DELIVERY_CONFIRMED. Local socket success is not remote receipt. The outbox schedules work but cannot authorize it. Stale adapters must present current fencing at permit consumption. No proxy/sidecar may silently retry or buffer outside the declared trust graph.

Crash handling: before acceptance, request a new permit after fresh authorization; after acceptance but before write, reconcile accepted permit and lease; during write or after local socket acceptance without receipt, mark uncertain and do not blindly retransmit; after remote receipt, retrieve receipt idempotently. Every supported proxy/service-mesh topology must document byte queues, copies, retries and termination points. No state may be inferred from a weaker state.

## 5. DBID-R45 — polling and candidate redemption

### 5.1 Polling API

Authenticated destination-service polling endpoint:

GET /v1/federation/discovery-operations/{request_id}

Authentication is mutual TLS plus a destination workload identity resolved by the source trust registry. Destination tenant/branch/workload are derived from authenticated identity; caller-supplied overrides are rejected. Request ID is at least 256 bits of secure randomness, stored as a keyed hash, and is not a bearer credential.

Headers: Content-Type application/json; Cache-Control no-store, private; Pragma no-cache. No redirects, ETags or shared-cache validators. Maximum body 64 KiB. No patient payload or selector echo in non-READY states.

Closed response fields: state (PENDING, READY, COMPLETE, UNAVAILABLE, OUTCOME_UNCERTAIN); operation_id (opaque random ID); retry_after_seconds (integer 1–30, absent only for terminal states); candidate_envelope (READY only); delivery_receipt (COMPLETE only after a terminal receipt exists). No additional properties.

COMPLETE is the external equivalence class for no-match, denied, expired and policy-filtered outcomes; source audit distinguishes them. UNAVAILABLE is only for source service outage; OUTCOME_UNCERTAIN requires reconciliation. Status mapping: 200 for a valid operation representation; 404 for unknown, cross-destination or unauthorized IDs with equivalent body/header behavior; 429 for destination-scoped rate limit; 503 for source outage. No Location, Server-Timing or diagnostic headers. Timing equivalence is statistically tested under load, not claimed as identical wall-clock duration. Budgets are source-owned and bounded per destination, actor, source and time window.

Publish OpenAPI and JSON Schema before implementation, with additionalProperties false, conditional state constraints, exact headers, size limits and cache rules.

### 5.2 One-time candidate redemption

POST /v1/federation/candidate-redemptions

Request fields: operation_id, candidate_ref, fresh signed clinician assertion, purpose, action, requested_projection, protocol_version and idempotency_key. The candidate reference is random, hashed at rest, one-time and short-lived; it is bound server-side to destination workload, tenant/branch, actor, source, operation, resource, purpose, action, projection digest and generation vector. It is not authority by itself.

In one source transaction: derive destination from mTLS; validate assertion signature/issuer/audience/actor mapping/current registration/status/affiliation and policy; lock/check epoch and fencing; verify operation/candidate/destination/purpose/action/projection/expiry; atomically consume the reference and persist redemption/audit intent. Return only the recipient-encrypted envelope and signed receipt after commit.

Concurrent redemption has one winner. Same idempotency key and same canonical request returns the stored outcome; same key with a different digest returns conflict. Lost response is recovered by authenticated polling, not a new source read. Receipt binds source, destination workload, tenant/branch, operation, candidate, artifact digest, projection digest, generation, issue/expiry, signer key ID and protocol version. Destination verifies signature and exact binding. Revoked actor or changed generation rejects redemption.

## 6. DBID-R46 — byte-exact wire profile

Candidate profile AVINYA-FED-JSON-1 is proposed, not approved. D-07 and independent cryptographic review remain gates.

Manifest encoding: RFC 8785 JSON Canonicalization Scheme (JCS), UTF-8, no BOM. Reject duplicate keys before canonicalization, unknown fields, NaN/Infinity and non-integer numeric values; integers stay in interoperable safe range. Identifiers/enums are ASCII. Free-text is NFC-normalized before schema validation; serializer performs no implicit normalization. Null is forbidden unless explicitly permitted by schema. Closed manifest fields: profile_id, protocol_version, source_id, destination_workload_id, destination_tenant_id, destination_branch_id, actor_subject_id, actor_issuer_id, actor_assertion_digest, resource_ref, purpose, action, policy_version, projection, projection_digest, operation_id, candidate_id, fencing_generation, source_generation_vector, content_digest_algorithm, content_digest, content_length, issued_at, expires_at, recipient_key_id, encryption_algorithm, nonce and aad_profile_id.

content_digest is SHA-256 over canonical plaintext artifact bytes before encryption; content_length is that exact byte length. Compression is disabled in v1. Envelope/ciphertext digest is separate and covers exact transmitted envelope bytes.

Signature preimage, all integers unsigned big-endian:

ASCII("AVINYA-FED-MANIFEST") || 0x00 || uint16(1) || uint16(profile_id_length) || ASCII(profile_id) || uint16(digest_algorithm_id_length) || ASCII(digest_algorithm_id) || uint16(digest_length) || digest_bytes || uint64(manifest_length) || canonical_manifest_bytes

Profile and digest algorithm IDs are ASCII, 1–64 bytes, grammar [A-Z0-9][A-Z0-9._-]{0,63}. SHA-256 digest length is exactly 32 bytes. Reject length mismatch, trailing bytes, unknown profile, duplicate key, unknown field or unsupported algorithm. Signature bytes are outside the manifest and not included in their own digest.

AAD is a separate closed JCS UTF-8 object containing exactly aad_profile_id, profile_id, source_id, destination_workload_id, destination_tenant_id, destination_branch_id, recipient_key_id, operation_id, candidate_id, resource_ref, purpose, action, projection_digest, content_digest, fencing_generation and protocol_version. All required, no null. AEAD uses the exact JCS bytes. Envelope schema is closed and contains profile, recipient key ID, algorithm, nonce, AAD bytes, ciphertext, authentication tag and signed manifest. Nonce uniqueness per encryption key is mandatory and must survive restart/restore. Signature covers manifest preimage; AEAD authenticates AAD/ciphertext. Chunking is disabled in v1.

Required cross-language vectors: empty/minimum/maximum payload, Unicode, malformed UTF-8, duplicate keys, unknown fields, wrong digest length, altered recipient, nonce reuse, expired manifest and signature tampering. Future chunking requires a new profile with exact index/count/length/digest/order/aggregate-root/reassembly rules.

## 7. DBID-R47 — executable PostgreSQL ACL contract

Companion schema: docs/schemas/aud004-cluster-acl-policy.schema.json. It defines core types/enums and rejects unknown properties for cluster identity, roles, memberships, database/schema/object ACLs, default privileges, extensions, foreign access and dual-approved exceptions.

The PostgreSQL-major-specific catalog adapter must enumerate every database including templates/control plane; every role and role attribute; membership edges with grantor, ADMIN, INHERIT and SET semantics; database CONNECT/TEMP; schema CREATE/USAGE; object ACLs and owners; PUBLIC grants; default ACLs for each creator; extension-owned objects; exact routine identity/signature; partitions, sequences, types/domains and foreign access.

The verifier computes effective access from direct and PUBLIC grants, membership inheritance, SET ROLE, grant options, ownership and default privileges using that major's exact semantics. It evaluates each path against explicit allow rules and unexpired dual-approved exact-object exceptions; wildcard object patterns are prohibited. Unknown role, grantor, membership, privilege, extension, object or unobservable catalog entry is UNKNOWN and blocks PASS. Emit deterministic normalized catalog digest, verifier version, server major, cluster identity, policy digest, exceptions, effective paths, findings, completeness counters, timestamp and signer evidence.

Bind to actual PostgreSQL-authenticated role and authoritative workload/credential mapping. application_name and caller metadata are not authority. Require independent verifier/oracle and non-empty synthetic fixtures for every supported major/provider. This proposal authorizes no production role/ACL change.

## 8. DBID-R48 — lifecycle registry

Companion schema: docs/schemas/aud004-lifecycle-registry.schema.json. It defines machine-validatable state and transition envelopes; it does not by itself prove graph completeness.

Required state families include read (READ_INTENT, READ_STARTED, READ_ABORTED_AFTER_FETCH, READ_OUTCOME_UNCERTAIN, READ_COMMITTED, POST_READ_AUTHORIZED, POST_READ_DENIED); artifact (ARTIFACT_STAGED, ARTIFACT_QUARANTINED, ARTIFACT_READY); egress (RELEASE_AUTHORIZED, EGRESS_ACCEPTED, TRANSPORT_WRITE_ATTEMPTED, BYTES_ACCEPTED_BY_LOCAL_SOCKET, REMOTE_RECEIPT, DELIVERY_CONFIRMED, DELIVERY_UNCERTAIN, RELEASE_QUARANTINED); destination (IMPORT_CLAIMED, SOURCE_VALIDATED, DESTINATION_COMMITTED, DESTINATION_COMMIT_UNCERTAIN, ACK_PENDING, ACK_SIGNED, ACK_VERIFIED); pointer/recovery (INDEX_SYNC_PENDING, COMPLETED, RECONCILIATION_REQUIRED, FAILED_RETRYABLE, REJECTED, QUARANTINED).

Every transition must have one authority, source/target states, preconditions, durable evidence, generation/fencing requirements, timeout, retry owner and terminal/reconciliation behavior. Persist operation ID, actor/workload, generation, idempotency key, event digest and timestamp. Source read worker cannot mark post-read authorization; egress cannot claim remote receipt; destination importer cannot sign source acknowledgement; pointer reconciler cannot claim destination commit. COMPLETED is allowed only after destination commit evidence, verified acknowledgement and verified pointer synchronization.

Define every failure boundary: audit outage, revocation before/after read, worker crash, egress acceptance uncertainty, partial socket write, duplicate delivery, destination validation/commit failure, ack loss, pointer-sync failure and operator reconciliation. Timeout is never success or automatic failure; it becomes uncertain and is reconciled by the responsible authority. Post-artifact or post-commit revocation moves to restricted quarantine; no automatic activation, silent deletion or ordinary clinical use. Clinical/privacy/legal owners must approve downstream orders, access restrictions, correction, legal hold, retention, deletion and backup expiry. Manual reconciliation requires dual control. All components must run shared conformance and model-based transition tests.

## 9. DBID-R49 — trust coverage and freshness

Companion schema: docs/schemas/aud004-trust-coverage.schema.json. It is a baseline, not proof of inventory completeness.

Root scope comes from authoritative provider organization/account/region inventory APIs, not an operator list alone. Snapshot pagination must be complete and tied to provider snapshot/version where available. If the provider offers no consistent snapshot, record the limitation and do not attest atomic completeness. Reconcile discovered resources to provider inventory; every missing, unknown, tombstoned or inaccessible resource is explicit. Unknown nodes/edges or unexplained count differences block PASS.

Graph identity is provider, organization/account, region, native resource ID, kind and lifecycle generation. Edges describe concrete capability plus authentication, authorization and policy evidence. Capability composition is monotonic set union along paths; conditional edges are traversable only when every condition is independently proven true. Cycles use a least fixed point over finite capability sets and stop only when no reachable set changes. Unknown conditions or unbounded delegation are treated as reachable/denied for isolation analysis, never ignored.

Freshness uses UTC RFC 3339 timestamps with explicit offset and millisecond precision. Effective expiry is the earliest required source snapshot, policy, credential, witness and configured maximum-age expiry. At now >= expires_at, evidence is stale. Clock uncertainty is bounded by an independently monitored maximum skew; exceeding it yields UNKNOWN. Event sequence gaps, delayed/out-of-order mutation events, generation regression, restore to an older snapshot or witness rollback invalidate attestation and require full reconciliation. Generations are monotonic and stored outside the attested resource. Independent witness signs root, snapshot digest, graph digest, reconciliation result, generation and expiry. Missing provider source, expired credential, inaccessible management plane, unknown edge, stale witness or clock anomaly yields NOT_READY.

## 10. Closure matrix

| Finding | Proposed resolution | Mandatory closure evidence |
|---|---|---|
| R42 | READ COMMITTED epoch FOR SHARE; conflicting revocation UPDATE | Two-session PostgreSQL race tests on every supported major |
| R43 | Isolated worker, bounded raw projection, opaque handle | Worker profile, host trust graph, no-ORM and negative-egress tests |
| R44 | Atomic epoch/nonce/permit acceptance | Permit/revocation race and crash-boundary tests |
| R45 | Authenticated polling and one-time redemption | OpenAPI/schema, anti-enumeration, replay and receipt tests |
| R46 | JCS manifest, explicit preimage and AAD | Cross-language byte vectors |
| R47 | ACL schema and deterministic major-specific verifier | Catalog fixtures, independent oracle, UNKNOWN blocks PASS |
| R48 | Lifecycle registry and single-owner transitions | Complete graph, model-based and component conformance tests |
| R49 | Trust schema, provider reconciliation and freshness | Provider snapshots, independent witness and graph test vectors |

## 11. Remaining gates

DBID-06–08, CAN-01, CAN-02 and AUD-004 remain open. Provider isolation, PostgreSQL support matrix, provider adapters, proxy/pooler support, clinical quarantine workflows, retention/residency, cryptographic algorithms, key custody, revocation freshness and operator dual control remain unresolved.

D-01–D-14 remain formally pending unless approved by designated authorities. D-11 project direction YES is not formal approval. Emergency federation remains disabled. All schemas and protocol values remain proposals pending governance and independent implementation review.

## 12. Explicit non-authorization

This PR authorizes documentation and design review only. It does NOT authorize runtime code changes, SQL, migrations, database/role/ACL/network changes, credential or secret operations, production access, patient-data access, partner onboarding, trust/key provisioning, federation activation, emergency access, pilot, deployment, release or merge. Keep this PR draft and unmerged. PRs #58 and #59 remain unmerged. AUD-004 remains a release blocker.
