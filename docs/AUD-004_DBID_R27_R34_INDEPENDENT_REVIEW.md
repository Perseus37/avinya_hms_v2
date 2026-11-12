# AUD-004 DBID-R27–DBID-R34 Independent Review

**Review target:** PR #56 — DBID-R27–DBID-R34 Resolution Proposal  
**Review type:** Independent documentation/security architecture review  
**Status:** DESIGN REVIEW ONLY — NOT IMPLEMENTATION APPROVAL  
**Release status:** AUD-004 remains a release blocker.

## 1. Executive conclusion

PR #56 is a substantial improvement. It distinguishes source-read authorization from network release, explicitly acknowledges that a database commit cannot atomically commit a remote socket write, adds a closed-world inventory direction, and improves PostgreSQL identity, wire-profile, ACL, attestation and import-recovery requirements.

However, DBID-R27–DBID-R34 are not yet closed. The most important remaining issue is DBID-R29: the document calls the database transaction commit the ReadCommit point, but protected rows have already been fetched into application memory before that commit. A later transaction abort cannot undo that materialization. The same transaction can also roll back the audit/outbox row that was intended to prove the attempted read. The proposal needs an explicit pre-read durable intent and an aborted/uncertain outcome protocol, plus a strict rule that fetched data cannot be used or released until the read transaction commits.

The ReleaseStart design also uses the state name RELEASE_STARTED for a database transition that occurs before the first network byte. That is a valid authorization boundary if stated accurately, but it is not evidence that transport actually started. A stale or paused worker holding a previously issued permit remains a critical edge case requiring exact permit/lease enforcement and explicit residual-risk acceptance.

The other findings concern the missing 202-operation completion channel, incomplete byte-level wire profile, conceptual rather than executable ACL schema, and lifecycle-state inconsistencies. These are design gaps, not claims of production exploitation. No production infrastructure, live PostgreSQL catalogs, credentials, secret manager, network configuration, audit store or patient data were inspected.

## 2. Findings summary

| ID | Severity | Finding |
|---|---|---|
| DBID-R35 | Critical | ReadCommit occurs after protected rows have already been materialized in application memory; rollback can erase the same-transaction audit evidence |
| DBID-R36 | High | ReleaseStart is named RELEASE_STARTED before transport begins; permit/lease enforcement for paused or stale workers is incomplete |
| DBID-R37 | High | HTTP 202 search operation has no defined result-delivery or completion-retrieval contract |
| DBID-R38 | High | Wire signature input is not fully byte-exact despite being described as normative |
| DBID-R39 | High | ACL manifest remains a conceptual skeleton with empty object/default/exception collections and incomplete executable schema |
| DBID-R40 | Medium | Source/destination lifecycle state machines are not fully reconciled, including RELEASE_PERMITTED and pre-read/audit failure states |
| DBID-R41 | Medium | Trust coverage and freshness evidence still lack a machine-validated schema and exact freshness/expiry decision contract |

## 3. Detailed findings

### DBID-R35 — Critical: ReadCommit follows application materialization and can roll back its audit evidence

**Affected section:** §4.3 ReadCommit transaction profile; §4.2 source authority and generation model.

The proposal says the protected projection is executed inside a transaction, then a durable read/disclosure-intent event and artifact-staging row are inserted in the same transaction, and finally the transaction commits as ReadCommit. In ordinary application/database execution, rows returned by the SELECT have already crossed the database-to-application boundary before COMMIT. The application process can hold the patient data in memory while the transaction is still open. If a later insert, commit, timeout, process exception or connection failure aborts the transaction, PostgreSQL cannot retract bytes already delivered to the process.

The proposal's claim that revocation ordered before ReadCommit prevents materialization is therefore too broad unless “materialization” is narrowly defined as durable authorization to use/release the fetched bytes. A transaction rollback does not prove that the process never received or observed the selected values.

There is a second coupled problem: if the disclosure-intent/audit row is in the same transaction and that transaction rolls back, the audit row rolls back too. The system may have fetched protected rows into process memory without retaining durable evidence that the fetch occurred or that its outcome was uncertain. This is precisely the kind of ambiguous boundary the protocol must make explicit.

**Required resolution:**
1. Distinguish at least three events: durable pre-read authorization intent, protected-row fetch/materialization attempt, and committed authorization to use/release the fetched projection.
2. Commit a source-owned intent/operation record before the protected SELECT. It must bind actor, destination, resource/candidate, purpose/action, exact projection, policy/generation, operation ID and fencing context.
3. Define the outcome record after the read transaction: READ_COMMITTED, READ_ABORTED_AFTER_FETCH, READ_OUTCOME_UNCERTAIN or READ_NOT_EXECUTED. If the transaction outcome is uncertain, do not infer that no data reached the process.
4. Define an application data-handling barrier: fetched values remain in a restricted staging buffer, cannot be serialized, logged, traced, cached, returned or passed to downstream work before the required commit and generation checks. On abort/uncertain outcome, discard the buffer and quarantine the operation. Acknowledge that reliable memory zeroization in managed runtimes may not be provable.
5. Ensure audit evidence for a failed/uncertain read survives rollback of the data transaction, using a separately committed pre-read intent plus a durable outcome/reconciliation protocol. Do not describe a same-transaction outbox row as durable if the transaction can roll back.
6. Add failure-injection tests for exception after SELECT, before audit insert, after audit insert, during COMMIT, connection loss during COMMIT, process crash and stale worker. Tests must assert both whether application memory received data and whether durable audit evidence exists.

**Closure evidence:** reviewed pre-read intent/outcome protocol, data-handling barrier, rollback-safe audit design and deterministic tests for every fetch/commit interleaving. This finding remains Critical until the read/materialization and audit semantics are precise.

### DBID-R36 — High: ReleaseStart state is committed before transport starts; stale permit behavior is incomplete

**Affected section:** §4.4 ReleaseStart transaction and unavoidable transport boundary.

The document atomically changes RELEASE_PENDING to RELEASE_STARTED and commits a release permit, then says the worker may invoke the transport adapter. Therefore RELEASE_STARTED is reached before the first socket write. The proposal correctly admits that revocation after this point cannot recall bytes, but the state name and lifecycle evidence can mislead operators into treating RELEASE_STARTED as proof that delivery began.

The document also says the permit is one-use and short-lived, but does not specify a complete enforcement contract for a worker paused after commit, process suspension, delayed scheduling, lease expiry, credential revocation, network partition or a stale process that resumes after a replacement worker has claimed a newer fencing generation. A database fencing check performed when the permit is issued cannot physically prevent a stale process from writing later unless the transport boundary independently enforces the permit and expiry. A local in-memory permit is not self-enforcing.

**Required resolution:**
1. Rename the committed state to RELEASE_AUTHORIZED or RELEASE_START_COMMITTED. Reserve TRANSPORT_WRITE_STARTED for evidence from the transport adapter that the first write was actually attempted; reserve DELIVERY_CONFIRMED for authenticated destination evidence.
2. Define the permit schema: immutable operation/artifact/recipient/destination, worker workload identity, fencing generation, lease ID, issuance time, not-before, expiry, one-time nonce, allowed transport endpoint and maximum payload digest/length.
3. Define how the transport adapter validates the permit at the actual write boundary, prevents reuse, rejects expired permits and binds the actual socket/session to the authorized worker and recipient.
4. Define lease expiry and replacement semantics. A new worker must not assume that an old process is dead; stale workers must be prevented from obtaining or using a valid transport capability. If this cannot be guaranteed by the chosen transport, document the residual possibility and do not claim fencing at the socket boundary.
5. Specify the crash/paused-worker sequence: permit commit, process pause, revocation, lease expiry, new worker claim, old process resume. State whether the old worker may still write and how the outcome is recorded.
6. Keep the post-authorization race explicit: a revocation after RELEASE_AUTHORIZED may be ordered after authorization even if no bytes have yet been sent. Obtain explicit security/privacy/clinical acceptance of that semantic.

**Closure evidence:** corrected state names, transport-bound permit contract, lease/stale-worker proof and deterministic paused-worker/revocation tests.

### DBID-R37 — High: HTTP 202 has no defined result-delivery/completion contract

**Affected section:** §3.1 public outcome profile; §3.3 candidate reference and operation record.

The proposal defines a canonical HTTP 202 body containing only a random request ID and states that candidate references are never returned to a browser or end user. It says the candidate reference is carried internally over an authenticated source-to-destination service channel. However, it does not define how the destination service learns that a search operation completed, obtains an authorized candidate, or correlates the operation to a later import request.

There is no specified authenticated polling endpoint, callback/webhook, queue/event delivery contract, response schema, retry behavior, delivery acknowledgement, or protection against operation-ID enumeration. The current text defines the public acceptance response but not the full API lifecycle. Without this, a uniform 202 response is not an executable protocol and can encourage implementers to expose candidate handles or add an unreviewed side channel.

**Required resolution:**
1. Define whether completion is retrieved by authenticated destination-to-source polling, source-to-destination callback, or a durable message channel. Select one primary mechanism per protocol profile.
2. Bind retrieval/delivery to the same immutable destination workload, tenant/branch, actor authorization, search operation, policy/generation and expiry established at admission.
3. Define exact status/body/header contract for pending, completed-with-authorized-candidate, no authorized candidate, denied, expired, unavailable and uncertain outcomes. Candidate/resource identifiers must remain inside the trusted service channel.
4. Define callback authentication, replay protection, idempotency, retry/backoff, acknowledgement, dead-letter/reconciliation and destination outage behavior if callbacks are selected.
5. Define polling authorization, rate limits and non-enumerable request-ID behavior if polling is selected. A random request ID alone is not authorization.
6. Test cross-destination retrieval, request-ID guessing, duplicate delivery, lost callback/ack, expired operation and partial fan-out.

**Closure evidence:** complete request/response and delivery sequence, endpoint/message schemas, authorization binding and end-to-end retry tests.

### DBID-R38 — High: Signature input remains short of byte-exact normative definition

**Affected section:** §6.2 Canonical bytes and signature input; §6.3 encryption and recipient binding.

The proposal improves the profile substantially, but the signature input is still described as a domain label, zero byte, fixed-width protocol-profile identifier, zero byte and digest. It does not specify the exact domain-label bytes/length, profile identifier width and byte order, digest encoding, or a complete binary grammar for the signed preimage. “Fixed-width” is not itself a byte-level definition. The exact JSON manifest schema and which fields are critical/covered are also left to a future profile registry.

The algorithm suite is still a candidate set pending approval, which is acceptable as a governance gate, but the document should not call the wire profile normative or executable until the registry and exact test vectors exist. The AEAD AAD is described as canonical encoding of a list of fields but does not identify an exact schema/encoding version and byte sequence in the proposal. Key-wrapping and envelope signature coverage also need to be unambiguous.

**Required resolution:**
1. Publish a versioned wire registry entry with exact ASCII/hex domain-prefix bytes, profile ID width/encoding, digest bytes, field order, integer widths/endianness, length prefixes and exact signature preimage.
2. Define a closed manifest schema: required/optional/critical fields, duplicate/unknown-field behavior, exact canonicalization, exact timestamp and identifier encodings, and whether every security-relevant envelope field is covered by signature or authenticated data.
3. Define AAD as a separately versioned schema with exact canonical bytes and cross-language vectors, including recipient key ID/version and destination identity.
4. Define exact key-wrapping envelope fields, their authenticity coverage, nonce uniqueness scope and failure behavior. Do not rely on a prose assertion that key ID is “covered” without specifying where and how.
5. Keep candidate algorithms marked unapproved until governance selects the profile; do not permit implementation to choose algorithms ad hoc.
6. Supply byte-for-byte positive/negative vectors independently implemented by two stacks before closure.

**Closure evidence:** complete registry entry, binary grammar, canonical manifest/AAD schemas and independently reproduced signature/encryption vectors.

### DBID-R39 — High: ACL manifest is still a conceptual skeleton, not an executable policy schema

**Affected section:** §7.1 normative data model; §7.2 catalog normalization and effective privileges.

The document explicitly labels its YAML as a “required conceptual structure” and leaves `schemas`, `objects`, `default_privileges` and `exceptions` as empty arrays. It also leaves exact enum values and semantics to a future production schema. That does not yet resolve the original finding that the ACL manifest/verifier is conceptual rather than machine-readable and executable.

The example's database kind value `"tenant|control|template"` is descriptive notation, not a normative enum encoding. Object identity, routine signatures/overloads, partition inheritance, creator/default-ACL matching, grantor/owner semantics, provider-managed object evidence and privilege expansion are not fully specified. The effective-privilege description does not provide a deterministic algorithm or complete fixture set.

**Required resolution:**
1. Publish an actual schema artifact (for example, JSON Schema plus versioned PostgreSQL-major semantic profile) with exact enums, required fields, nullability, formats, uniqueness and referential constraints.
2. Define exact object identity for each supported catalog class, including routine identity/argument signature, partitions, sequences, types/domains, extensions, FDW and provider-managed resources.
3. Define normalized ACL entry grammar and deterministic expansion for PUBLIC, owner powers, grantor/grant options, membership INHERIT/SET/ADMIN, default privileges per creator/schema/object class, SECURITY DEFINER and extension-owned objects.
4. Define unsupported/unobservable catalog behavior as UNKNOWN/FAIL, and specify the independent oracle's inputs, algorithm version, output schema and independence boundary.
5. Include non-empty representative fixtures for allowed and denied cases, plus cross-tenant path and default-privilege regression fixtures.

**Closure evidence:** validated schema artifact, provider/major adapters, complete catalog fixture suite and independent verifier/oracle.

### DBID-R40 — Medium: Lifecycle states are not fully reconciled across R29 and R34

**Affected section:** §4.4 release state machine; §9.2 state/authority matrix; §9.3 destination transaction.

R29 lists RELEASE_PERMITTED as a state but describes a direct transition from RELEASE_PENDING to RELEASE_STARTED when the permit/outbox event is committed. R34 omits RELEASE_PERMITTED and does not include the read-intent/read-aborted states required by DBID-R35. R29 also does not define the durable audit state for a read that fetched rows but whose transaction later aborted or whose commit outcome is uncertain.

These are not merely naming differences: state-machine divergence can cause different components to interpret the same operation as pending, authorized, started, delivered or recoverable. The destination lifecycle also uses DESTINATION_COMMITTING for a transaction that is supposed to atomically create the patient clone, provenance and operation marker; the exact durable representation of “commit in progress” versus “commit outcome unknown” needs a consistent rule.

**Required resolution:**
1. Publish one canonical source/destination lifecycle schema used by the source router, dispatcher, transport adapter, destination importer, acknowledgement verifier and pointer synchronizer.
2. Define every state with owner, durable storage location, entry evidence, exit evidence, permitted transitions, terminality, retry authority and timeout behavior.
3. Reconcile read intent/fetch/commit/abort/uncertain states and release authorization/transport-start/delivery-confirmed states.
4. Distinguish an uncommitted transaction from an externally observable durable state; use OUTCOME_UNCERTAIN when commit outcome cannot be established.
5. Define exact recovery for duplicate workers, stale fencing, crash during commit, ack loss and pointer sync failure; unknown state must not be coerced into success.

**Closure evidence:** canonical machine-readable state/transition schema and conformance tests proving every component uses the same transition contract.

### DBID-R41 — Medium: Trust coverage and freshness claims still need executable schemas and expiry semantics

**Affected section:** §2.1–§2.3 trust coverage; §8 freshness and rollback protocol.

The proposal identifies appropriate root inventories, graph nodes/edges, source reconciliation and independent checkpoints. However, it specifies field lists in prose rather than a machine-validated schema, and it does not define exact provider adapter contracts or a deterministic reconciliation format for root evidence. The graph algorithm is described at a high level but does not specify canonical identity keys, edge-condition evaluation, time interval semantics, evidence precedence or the signed output schema.

The freshness section also says a prior PASS expires conservatively and that maximum staleness is set by governance, but does not define how the verifier computes effective expiry across multiple domains, clock uncertainty and delayed events, or how a generation gap invalidates dependent attestations. This is a valid explicit NOT_READY gate, but it is not yet an executable attestation contract.

**Required resolution:**
1. Publish versioned schemas for scope roots, inventory snapshots, graph nodes/edges, exclusions, evidence references and completeness attestations.
2. Define provider adapter inputs/outputs, immutable identity normalization, tombstones, pagination/snapshot guarantees and exact reconciliation result schema.
3. Specify graph edge condition evaluation, transitive capability composition, cycles, time-window evaluation and canonical output ordering/digest.
4. Define the freshness calculation: per-domain maximum age, event sequence/generation, clock skew allowance, checkpoint expiry and dependency invalidation.
5. Define which evidence is invalidated by each mutation generation and how missing/out-of-order events force UNKNOWN.
6. Add schema-validation, hidden-root, stale-event, clock-skew, restore and independent-reproduction tests.

**Closure evidence:** machine-validated schema bundle, provider adapters, deterministic graph/freshness algorithm and independent conformance tests.

## 4. Cross-finding dependencies

- **R35** blocks the source disclosure/read protocol because fetched data and audit durability are not fully ordered.
- **R36** blocks trustworthy release-state and stale-worker enforcement.
- **R37** blocks an executable search API lifecycle.
- **R38/R39** block production-capable artifact integrity and database privilege verification.
- **R40** blocks safe orchestration and recovery across source and destination components.
- **R41** blocks reliance on coverage/freshness PASS evidence for runtime authorization.

These findings are coupled. R35/R36/R40 define the actual data lifecycle; R37 determines how the trusted destination participates; R38/R39/R41 determine whether the authorization, artifact and infrastructure evidence can be trusted.

## 5. Overall closure status

PR #56 materially improves the design, but **DBID-R27–DBID-R34 remain open** pending resolution of DBID-R35–DBID-R41 and independent evidence. DBID-06 through DBID-08 remain open. CAN-01 and CAN-02 remain open. AUD-004 remains a release blocker.

D-01 through D-14 remain formally pending unless separately approved by designated authorities. D-11 project direction YES is not formal governance approval. Emergency federation remains disabled absent separate approval.

## 6. Review limitations and explicit non-authorization

This was a documentation-only adversarial review of PR #56 and its stated parent context. It did not inspect production infrastructure, live PostgreSQL catalogs, credentials, secrets, network policies, backups, audit stores or patient data. Findings describe design evidence gaps, not verified production vulnerabilities or exposure.

This review authorizes documentation and independent design review only. It does NOT authorize runtime changes, SQL, database/role/ACL/network changes, credential or secret operations, production access, patient-data access, partner onboarding, trust/key provisioning, federation activation, emergency access, pilot, deployment, release or merge. PR #56 must remain draft and unmerged pending further review.
