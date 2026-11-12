# AUD-004 DBID-R35–DBID-R41 Resolution Proposal

**Status:** DESIGN PROPOSAL — NOT IMPLEMENTATION APPROVAL  
**Parent:** PR #57  
**Architecture:** database-per-tenant.  
**Release status:** AUD-004 remains a release blocker.

## 1. Purpose and decision posture

This proposal resolves the design gaps identified in DBID-R35 through DBID-R41. It distinguishes database commit, application-memory materialization, authorization to use fetched bytes, transport authorization and actual delivery. It does not claim that rollback can retract values already returned to a process or that a database commit can be atomic with a remote socket write.

Provider-specific values, cryptographic suites, freshness intervals, clinical disposition and other authority-dependent decisions remain unapproved. Missing values mean NOT_READY, never a permissive default.

## 2. DBID-R35 — Pre-read intent, isolated staging and rollback-safe audit

### 2.1 Separate the events

The source lifecycle MUST distinguish:
1. **READ_INTENT_COMMITTED:** a durable authorization intent is committed before any protected SELECT.
2. **READ_FETCH_ATTEMPTED:** an isolated worker executes the protected query; this records an attempt, not permission to use the result.
3. **READ_COMMITTED:** the read transaction committed successfully and its outcome was durably reconciled.
4. **READ_AUTHORIZED_FOR_RELEASE:** a separate post-read authorization check permits the staged projection to proceed.
5. **READ_NOT_EXECUTED, READ_ABORTED_AFTER_FETCH, READ_OUTCOME_UNCERTAIN, READ_DENIED_AFTER_FETCH, READ_QUARANTINED:** explicit non-success outcomes.

### 2.2 Durable intent before SELECT

Before a protected SELECT, the source commits a unique operation/intent record in a separate short transaction. It binds operation ID, actor and issuer, destination workload and tenant/branch, source tenant/resource candidate, action, purpose, exact field projection, policy digest, generation vector, expiry and worker/lease fencing context. The transaction also requires acknowledgement from the durable source audit boundary.

If intent or audit persistence is unavailable, no protected SELECT begins. The intent is never deleted to make an attempted read disappear.

### 2.3 Restricted application-memory staging

The protected read runs in a dedicated least-privilege source worker with no direct client response path, no general logging/tracing/crash-dump access to the buffer, no cache, no ORM identity-map reuse, no lazy relationship loading and no downstream task handoff. The query uses a strict allowlisted projection and bounded result size.

The worker locks and rechecks the source authorization generation and operation binding, then executes the SELECT. Returned rows necessarily enter worker memory before transaction commit. The design explicitly acknowledges this materialization; it does not claim that ReadCommit prevents it.

Until transaction outcome and post-read authorization are established, the buffer is quarantined: no serialization, logging, tracing, caching, response, matching beyond the authorized predicate, or downstream use. On abort or uncertainty, the buffer is discarded and the isolated worker is terminated/recycled under the approved process policy. Managed runtimes cannot generally prove physical zeroization of every copy; process isolation and short buffer lifetime are compensating controls, not perfect-erasure claims.

### 2.4 Outcome survives rollback

The pre-read intent is committed separately and therefore survives rollback of the read transaction. After the read, the worker writes READ_COMMITTED or READ_ABORTED_AFTER_FETCH in a separate durable outcome transaction. If the process crashes, connection is lost during COMMIT, or the outcome cannot be established, the operation remains READ_OUTCOME_UNCERTAIN. Missing outcome evidence is never interpreted as READ_NOT_EXECUTED.

An audit row inserted only inside the protected read transaction is not considered rollback-safe. If a required audit service is unavailable, the read does not start. Any uncertainty after fetch quarantines the operation.

### 2.5 Post-read authorization barrier

After READ_COMMITTED, a separate source-owned transaction locks/rechecks the current generation, actor, destination, purpose, policy and exact projection. Only then can the operation transition to READ_AUTHORIZED_FOR_RELEASE. Revocation before this check prevents use/release and causes READ_DENIED_AFTER_FETCH or READ_QUARANTINED. This does not undo the worker's earlier receipt of the rows; the durable intent and outcome preserve that fact.

### 2.6 Required tests

Inject failures before SELECT, after first row, after final row, before commit, during commit, after commit before outcome write, after outcome write, before post-read authorization and during process termination. Prove: no SELECT without durable intent; no output before post-read authorization; pre-read audit survives rollback; uncertain outcomes never become “not executed” by inference; audit outage prevents reads; stale workers cannot authorize release; ORM, tracing, exception and crash-dump paths do not expose the buffer.

**Closure evidence:** transaction ordering proof, isolated worker threat model, audit acknowledgement contract and deterministic failure-injection tests.

## 3. DBID-R36 — Release authorization versus actual transport

### 3.1 Correct state names

The database transition before network activity is **RELEASE_AUTHORIZED**, not RELEASE_STARTED. The states are RELEASE_PENDING, RELEASE_AUTHORIZED, TRANSPORT_WRITE_STARTED, DELIVERY_CONFIRMED, OUTCOME_UNCERTAIN, RELEASE_BLOCKED and RELEASE_QUARANTINED. RELEASE_AUTHORIZED is not evidence that a socket opened or bytes were sent.

### 3.2 Sole egress capability

The application/source worker receives no reusable socket credential and has no direct network route to the destination. Network policy permits only a dedicated egress adapter to connect. The adapter alone converts release authorization into transport bytes.

A permit binds immutable operation/artifact IDs, content digest and length, source/destination identities and tenant/branch, recipient key ID/version, worker and egress workload identities, lease ID, monotonically increasing fencing generation, one-use random nonce, allowed endpoint, protocol profile, issue/not-before/expiry times and maximum bytes. The egress adapter validates the authenticated permit against authoritative operation state, consumes the nonce once, and records the transport attempt before writing. Caller headers, application_name and local in-memory flags are not authority.

### 3.3 Paused workers and residual race

A paused worker cannot retain independent network capability. If it pauses before the egress adapter accepts the request, expiry/revocation causes rejection. Once accepted, the egress adapter—not the worker—owns the socket and controls continuation/cancellation. A replacement worker cannot initiate a second send while the first is active or uncertain.

The adapter rechecks fencing at acceptance and supported chunk boundaries. If the transport is a single non-interruptible write, that residual window is documented. If a provider/proxy cannot enforce sole egress ownership, current generation checks and duplicate-send suppression, that topology is unsupported.

Revocation before RELEASE_AUTHORIZED blocks. Revocation after RELEASE_AUTHORIZED but before adapter acceptance is checked again and blocks. Revocation after adapter acceptance is ordered after the accepted send; bytes already written or buffered cannot be recalled. This residual boundary requires explicit security, privacy/legal and clinical acceptance.

**Closure evidence:** network isolation, permit schema, nonce/lease/fencing enforcement, paused-worker tests and transport residual-risk approval.

## 4. DBID-R37 — Authenticated destination-service polling

Protocol v1 selects destination-service polling as its single completion mechanism. No browser/patient-facing client polls the source; no callback/webhook is used in v1. The initial POST returns the fixed 202 acceptance response. Its random request ID is a locator, not authorization.

The destination service polls over mutually authenticated service transport. The source derives destination workload and tenant/branch from the authenticated channel and registry; caller-supplied destination, actor, purpose, projection or source identity overrides are rejected. The operation must still be bound to that workload, actor authorization, policy/generation and expiry.

Versioned response schema:
- 200 PENDING: status, request_id and fixed-profile retry_after_seconds.
- 200 READY: status, request_id and encrypted candidate_delivery envelope.
- 200 COMPLETE: status, request_id and null candidate_delivery for no authorized result, denied or expired cases.
- 503 SOURCE_UNAVAILABLE: fixed generic body; retry only within operation deadline.
- 409 OPERATION_CONTEXT_CONFLICT: fixed generic body without match-specific detail.
- 429 RATE_LIMITED: fixed provider-profile retry response independent of match.

The READY envelope is encrypted/authenticated to the destination workload key and contains a one-time candidate reference plus operation binding. It is not a raw resource ID, patient identifier or bearer capability. Redemption requires the destination's authenticated workload and original actor/operation context; source authorization is revalidated. READY does not authorize import.

Polling is idempotent. A signed receipt binds envelope digest and operation. Lost response/ack is reconciled by polling; it never creates a second candidate. Expiry, revocation and partial fan-out use the same generic external outcome contract.

**Closure evidence:** API schema, workload binding, encrypted envelope, poll/ack idempotency, request-ID enumeration and outage tests.

## 5. DBID-R38 — Exact wire encoding contract

### 5.1 Immutable profile registry

Each protocol version references one immutable WireProfile: profile ID, schema version, canonicalization, digest, signature, encryption, key-wrap and AAD schema IDs, chunk mode, maximum payload and approval status. Only APPROVED profiles may be enabled. Candidate algorithms remain PROPOSED; implementation cannot select algorithms ad hoc.

### 5.2 Signature preimage

The byte grammar is:

**ASCII("AVINYA-HMS-FED-MANIFEST") || 0x00 || uint16_be(profile_id_length) || profile_id_utf8 || uint64_be(canonical_manifest_length) || digest_bytes**

The domain label is exactly the ASCII bytes shown, without quotes. Profile ID is 1–128 UTF-8 bytes restricted to ASCII characters A–Z, 0–9, period, underscore and hyphen; its byte length is unsigned 16-bit big-endian. Manifest length is unsigned 64-bit big-endian. Digest bytes are the raw output of the profile-selected digest, never hexadecimal text. No trailing bytes are permitted. The signature field is excluded from canonical manifest bytes. Signer key ID, profile, source/destination, recipient key version, operation, projection, generation and expiry are included in the canonical manifest and covered by its digest.

This defines the serialization shape, not algorithm approval. A profile selecting another digest must define a new exact digest length and grammar. No runtime negotiation or silent substitution is permitted.

### 5.3 Manifest and AAD

The manifest is a closed schema. Duplicate JSON names, unknown critical fields, invalid UTF-8, non-finite numbers, out-of-range integers, invalid timestamps and non-canonical encodings are rejected. Timestamps use strict UTC RFC 3339 with fixed precision and Z. Binary values use unpadded base64url. Identifier normalization is field-specific and versioned; no global Unicode normalization is assumed.

AAD is a separate versioned canonical structure with exactly these fields in order: profile_id, artifact_id, source_cluster_id, source_tenant_id, source_branch_id, destination_tenant_id, destination_branch_id, recipient_key_id, recipient_key_version, operation_id, content_digest_algorithm, content_digest, content_length. Exact canonical bytes are passed unchanged to AEAD; the envelope records AAD schema ID and digest. Recipient identity is compared to the authenticated destination workload.

The signed manifest covers encryption and key-wrap suite IDs, recipient key ID/version, nonce/IV, ciphertext length, AAD schema ID/digest and envelope digest. The profile must specify precisely which signature or AEAD authenticates each envelope field.

### 5.4 Nonce and chunks

Nonce uniqueness is scoped to a key version and requires a durable uniqueness mechanism and key-usage ceiling. Operation ID alone is not a nonce source. Allocator rollback or nonce reuse revokes the affected key version. Chunking is DISABLED in v1; payload size is bounded by the approved profile. Any future chunking requires a new version with exact byte-level leaf/parent encodings, integer widths/endianness, odd/empty rules and cross-language vectors.

**Closure evidence:** approved registry entries, closed schemas and independently reproduced positive/negative byte vectors. No cryptographic algorithm is approved here.

## 6. DBID-R39 — Machine-validated cluster ACL policy

### 6.1 Required schema

The ACL policy is a versioned JSON document validated against a published schema and a PostgreSQL-major/provider semantic profile. Required top-level properties are:
- schema_version and immutable policy_id;
- cluster: immutable cluster ID, provider profile, PostgreSQL major and inventory generation;
- roles: every cluster role with immutable role ID/name, LOGIN, SUPERUSER, CREATEDB, CREATEROLE, REPLICATION, BYPASSRLS, INHERIT, connection limit, validity and owner/admin status;
- memberships: member, granted role, grantor, ADMIN OPTION, INHERIT and SET options;
- databases: every tenant, control, postgres and template DB, immutable ID/name/owner and CONNECT/TEMP ACL;
- schemas: exact database/schema identity, owner and CREATE/USAGE ACL;
- objects: exact database/schema/class/object identity, owner, creator and ACL;
- default_privileges: database, schema scope, creator role, object class, grantee, grantor, privileges and grant options;
- extensions: exact name/version/schema/owner and provider capability;
- foreign_access: FDW/server/user mapping/foreign table/network destination/effective principal;
- exceptions: exact principal/object/privilege, two independent approvers, reason, evidence, start/expiry and policy generation;
- evidence_policy: verifier profile, required generation, snapshot requirement, expiry and signer identities.

Every collection has unique immutable keys and referential constraints. Unknown fields are rejected unless a non-security annotation namespace is explicitly allowed. Wildcard object names, regex grants and unbounded patterns are prohibited. Enums are actual arrays of exact values, never pipe-delimited prose.

### 6.2 Object identity and effective privileges

Object identity is the tuple of immutable cluster ID, database ID, catalog class, schema identity where applicable, object identity and version-specific signature. Routine identity includes exact argument signature and overload. Partitions are individually enumerated with parent identity. Sequences, types/domains, large objects, extensions, languages, FDW servers/user mappings, foreign tables, event triggers and SECURITY DEFINER routines have distinct classes.

An ACL entry contains grantee role ID or PUBLIC, grantor role ID, exact privilege enum set and grant-option set. Default privileges bind the creating role and schema scope; global defaults are not conflated with schema-specific defaults. Exceptions cannot wildcard a tenant/database/object class.

The deterministic verifier expands owner powers, PUBLIC, direct grants, grant options, transitive membership with grantor/ADMIN/INHERIT/SET semantics, database CONNECT/TEMP, schema CREATE/USAGE, object privileges, default ACLs for every creator role, SECURITY DEFINER execution context, extension/provider roles, foreign access and cluster-wide attributes such as superuser, replication, BYPASSRLS, role/database creation. It evaluates every runtime/source/destination/import/background/support/migration/backup/provisioning principal against every database and protected object.

Unsupported or unobservable provider semantics return UNKNOWN, never PASS. A separate oracle validates role closure and selected privilege calculations. Fixtures include allowed/denied CONNECT, PUBLIC, TEMP, schema CREATE, owner, inherited roles, SET ROLE, grant options, per-creator defaults, overloaded routines, SECURITY DEFINER, extensions, FDW, restore and migration-created objects.

### 6.3 Signed verifier output

The result binds cluster ID, policy digest, catalog snapshot digest, provider/PostgreSQL profile, adapter/verifier build digests, generation, exception expansion, effective access paths, UNKNOWN list, timestamp, expiry and previous attestation digest. PASS requires zero unauthorized cross-tenant paths, zero unapproved exceptions and zero UNKNOWN. FAIL identifies unauthorized paths; UNKNOWN is not PASS.

**Closure evidence:** actual schema artifact, provider/major adapters, deterministic algorithm, complete fixtures and independent verifier oracle.

## 7. DBID-R40 — One canonical lifecycle registry

All source router, read worker, audit writer, egress adapter, destination importer, acknowledgement verifier and pointer synchronizer consume one versioned lifecycle registry.

Canonical success path:

**SEARCH_ACCEPTED → SEARCH_AUTHORIZED → CANDIDATE_ISSUED → CANDIDATE_AUTHORIZED → READ_INTENT_COMMITTED → READ_FETCH_ATTEMPTED → READ_COMMITTED → READ_AUTHORIZED_FOR_RELEASE → ARTIFACT_SEALED → RELEASE_PENDING → RELEASE_AUTHORIZED → TRANSPORT_WRITE_STARTED → DELIVERY_CONFIRMED → DESTINATION_VALIDATING → DESTINATION_COMMITTED → ACK_VERIFIED → POINTER_SYNC_PENDING → COMPLETED**

Alternative states include DENIED, READ_NOT_EXECUTED, READ_ABORTED_AFTER_FETCH, READ_OUTCOME_UNCERTAIN, READ_DENIED_AFTER_FETCH, READ_QUARANTINED, RELEASE_BLOCKED, RELEASE_QUARANTINED, OUTCOME_UNCERTAIN, DESTINATION_REJECTED and RECONCILIATION_REQUIRED. No transition may skip required states.

Every state record includes schema version, operation ID, prior state/version, sole authority, generation/fencing token, evidence digest, trusted event time, owner and retry authority. Transitions use compare-and-swap and unique constraints. An in-flight SQL transaction is not represented as a durable COMMITTING state unless a separate durable operation row exists. Destination commit uncertainty is resolved by re-reading the unique operation marker in a fresh transaction. Unknown state, missing evidence, conflicting digest or stale generation becomes RECONCILIATION_REQUIRED.

Read retries after READ_OUTCOME_UNCERTAIN require reconciliation. Candidate retry after expiry requires fresh authorization. Release retry follows the selected artifact strategy and egress idempotency record. Ack loss is reconciled against destination evidence. Pointer sync remains separate; COMPLETED follows independent verification of the exact pointer update only.

**Closure evidence:** machine-readable state schema, transition registry and component conformance/crash/retry tests.

## 8. DBID-R41 — Trust coverage and freshness schemas

### 8.1 Coverage schema

The versioned schema contains:
- roots: provider organization/account/project/subscription, regions, identity authorities, network/control planes, PostgreSQL clusters/databases, backups and provider management scope;
- snapshots: provider/source ID, API version, immutable snapshot token, collection time, pagination completion, permission scope, counts and truncation/error status;
- nodes: immutable normalized ID, provider-native ID, resource type, parent/root, lifecycle, tenant/database scope, owner, source evidence and generation;
- edges: immutable edge ID, source/target, capability enum, grantor, authentication context, conditions, scope, validity interval, mutation authority and evidence;
- exclusions: exact resource/class, reason, independent approvers, evidence and expiry;
- reconciliation: expected/observed roots and counts, missing/extra/conflicting/unknown objects, pagination proof and disposition;
- completeness attestation: graph digest, snapshot digests, adapter/verifier builds, independent signer, generation, issue time and expiry.

IDs are namespaced by provider, root and resource type; provider-native IDs are retained. Tombstones preserve deletion evidence. Conflicting observations are UNKNOWN until authoritative precedence resolves them. A collector cannot attest to its own completeness.

### 8.2 Deterministic graph evaluation

Provider adapters have versioned input/output contracts. Root reconciliation independently obtains organization/account inventory and compares it with project/subscription/service collectors. Missing root, inaccessible region, truncated pagination, hidden account, unknown edge or provider API disagreement blocks PASS.

Edge conditions are evaluated against trusted time intervals and exact principal/resource context. Unknown conditions are UNKNOWN, not false. Transitive paths preserve complete edge sequences and evidence. Cycles are reported and evaluated to a fixed point; arbitrary traversal cutoffs are prohibited. Canonical output sorts immutable node/edge IDs and capability enums before digesting.

### 8.3 Freshness and invalidation

Each evidence domain has an approved maximum age and authoritative mutation sequence. Effective expiry is the earliest of every required evidence-source expiry, domain maximum-age deadline, signer/key expiry, policy expiry, provider snapshot expiry and checkpoint expiry, adjusted conservatively for the approved clock-uncertainty bound. Missing limits or clock bounds mean UNKNOWN/NOT_READY.

IAM/workload/delegation changes invalidate identity/trust-graph evidence. Network/DNS/proxy/orchestration changes invalidate path/workload evidence. PostgreSQL role/ACL/object/extension changes invalidate cluster ACL evidence. Secret/key changes invalidate credential/wire trust evidence. Policy/exception changes invalidate authorization/ACL evidence. Verifier/adapter changes invalidate attestations produced by that build. Backup/restore/failover invalidates database identity, ACL and session evidence until full re-verification.

Generation gaps, delayed/out-of-order events, sequence reuse with a different digest, restore rollback, clock uncertainty or witness outage force UNKNOWN and deny new dependent authorization. An independent witness retains the highest generation/checkpoint digest outside the evidence store. Revalidation requires a fresh independently collected snapshot and signed checkpoint; an old PASS cannot be replayed.

**Closure evidence:** schema bundle, provider adapters, deterministic graph/freshness algorithm, independent witness and omission/staleness/restore tests.

## 9. Closure matrix and remaining gates

| Finding | Proposed control | Required evidence |
|---|---|---|
| R35 | Pre-read intent, isolated buffer, independent outcome and post-read authorization | Rollback-safe audit and failure injection |
| R36 | Sole egress capability and distinct release/transport states | Stale-worker and transport proof |
| R37 | Authenticated destination-service polling | API schemas and retry tests |
| R38 | Exact wire grammar and immutable profile registry | Independent byte vectors |
| R39 | Machine-validated cluster ACL policy | Catalog adapters and verifier oracle |
| R40 | One lifecycle registry | Component conformance tests |
| R41 | Closed-world coverage and freshness | Independent reconciliation and witness tests |

This proposal does not close findings by assertion. DBID-06 through DBID-08 remain open. CAN-01 and CAN-02 remain open. AUD-004 remains a release blocker. D-01 through D-14 remain formally pending unless separately approved. D-11 project direction YES is not formal governance approval. Emergency federation remains disabled absent separate approval. Provider-specific values, algorithms, freshness limits, clinical disposition, retention and residual transport risk remain unapproved.

## 10. Explicit non-authorization

This document authorizes documentation and independent design review only. It does NOT authorize runtime changes, SQL, database/role/ACL/network changes, credentials or secret-manager operations, production access, patient-data access, partner onboarding, trust/key provisioning, federation activation, emergency access, pilot, deployment, release or merge.

PR #57 remains draft and unmerged. This proposal is a draft, unmerged follow-up. All release blockers and governance gates remain in force.
