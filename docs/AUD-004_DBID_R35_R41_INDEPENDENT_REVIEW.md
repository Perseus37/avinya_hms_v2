# AUD-004 DBID-R35–DBID-R41 Independent Review

**Review target:** PR #58 — DBID-R35–DBID-R41 Resolution Proposal  
**Review type:** Independent documentation/security architecture review  
**Status:** DESIGN REVIEW ONLY — NOT IMPLEMENTATION APPROVAL  
**Release status:** AUD-004 remains a release blocker.

## 1. Executive conclusion

PR #58 materially improves the protocol. In particular, it correctly acknowledges that protected rows enter application memory before transaction commit, introduces a pre-read durable intent, separates post-read authorization from the read transaction, renames the pre-transport state to RELEASE_AUTHORIZED, selects destination-service polling, and keeps unapproved algorithms and governance values gated.

However, the proposal is not yet implementation-ready. The most important residual issue is that the read/revocation lock ordering is described but not specified as an exact transaction protocol. A worker can only claim that a source revocation is ordered against the protected SELECT if the epoch lock, isolation level, transaction scope, and conflicting revocation update are precisely defined and tested. “Locks and rechecks” is not sufficient to prove the ordering.

The proposal also describes a restricted memory buffer without specifying how the database driver, ORM, runtime, allocator, exception handling and process supervisor enforce that no alternate copy or egress path exists. The explicit caveat about zeroization is good, but the isolation claim still needs a concrete execution boundary.

Other gaps remain in the egress permit's revocation linearization, the polling response/envelope contract, the exact canonical byte profile, the executable ACL schema, the complete lifecycle transition registry and the trust/freshness schemas. Several sections identify what a future artifact must contain but do not yet supply the normative schema or deterministic algorithm.

These are design evidence gaps, not findings of verified production exploitation. No production infrastructure, live PostgreSQL catalogs, credentials, secrets, network policies, audit store or patient data were inspected.

## 2. Findings summary

| ID | Severity | Finding |
|---|---|---|
| DBID-R42 | Critical | Read-generation lock and revocation ordering are not specified as an exact transaction/linearization protocol |
| DBID-R43 | High | Restricted memory staging is not yet an enforceable process/driver/ORM boundary |
| DBID-R44 | High | Egress permit acceptance, nonce consumption and revocation are not atomically ordered in one authoritative consistency domain |
| DBID-R45 | High | Polling response and candidate-envelope redemption/receipt contract remains underspecified |
| DBID-R46 | High | Wire grammar still lacks exact canonicalization and unambiguous digest framing/closed manifest schema |
| DBID-R47 | High | ACL policy remains a field inventory, not an actual machine-validatable schema and executable privilege algorithm |
| DBID-R48 | High | Lifecycle registry gives a success path but not a complete state/transition/authority/recovery schema |
| DBID-R49 | Medium | Trust graph and freshness contract remains descriptive rather than deterministically machine-verifiable |

## 3. Detailed findings

### DBID-R42 — Critical: Read-generation lock and revocation ordering are not an exact protocol

**Affected sections:** §2.2 durable intent; §2.3 restricted staging; §2.5 post-read authorization.

The proposal says the read worker “locks and rechecks the source authorization generation and operation binding, then executes the SELECT.” It does not specify:
- the exact PostgreSQL isolation level;
- the exact epoch-row lock mode and transaction boundary;
- whether the lock is held continuously through the protected SELECT and fetch completion;
- the exact conflicting operation used by revocation;
- whether the protected SELECT is in the same transaction and connection as the lock;
- how multiple revocation domains are ordered;
- what happens when the read worker loses its database connection while rows have already been returned.

Without these details, the text does not prove that revocation and protected read have a single authoritative order. A worker might check a generation, lose the lock/transaction, and continue with a query or fetched buffer under stale authorization. The post-read check prevents later use/release but cannot undo the source worker's receipt of rows.

**Required resolution:**
1. Specify one source-owned consistency domain and exact SQL/transaction protocol for read authorization and revocation. Identify the row(s), lock mode, isolation level, transaction start, lock acquisition, SELECT, fetch completion and commit ordering.
2. Define revocation as a conflicting update/lock in the same consistency domain. State precisely whether revocation waits for a protected read to finish or causes the read to abort, and how a worker proves it still holds the required lock.
3. Define multi-domain generation handling (issuer/key, clinician, partner/destination, policy, workload/database identity, credential/session and audit) and the atomicity/ordering of their updates.
4. Define connection loss, transaction abort and cancellation after partial row delivery. Such cases must be READ_OUTCOME_UNCERTAIN or READ_ABORTED_AFTER_FETCH; no stale worker may continue to use/release the buffer.
5. Provide deterministic interleaving tests for revocation before lock, while waiting, after lock/before SELECT, during fetch, after final row/before commit, during commit and after commit/before post-read authorization.

**Closure evidence:** exact transaction/SQL protocol, reviewed lock graph, documented linearization point and concurrency tests proving all revocation/read interleavings.

### DBID-R43 — High: Memory staging is not yet an enforceable isolation boundary

**Affected section:** §2.3 restricted application-memory staging; §2.6 required tests.

The proposal lists desirable restrictions (no logs, tracing, cache, ORM reuse, lazy loading, downstream handoff and direct client response), but does not define the mechanism that enforces them. In particular, a “dedicated worker” and an “operation-scoped buffer” do not by themselves prevent:
- database-driver row buffers or ORM objects from retaining copies;
- exception messages, stack traces, telemetry instrumentation or debug tooling from serializing values;
- allocator/GC copies, swap, core dumps, process snapshots or host-level diagnostics from capturing memory;
- another thread/task or shared process component from observing the same object;
- accidental access through generic serializer or response helpers.

The proposal correctly says managed-runtime zeroization cannot generally be proven. That caveat makes the process boundary, not a claimed buffer discipline alone, the primary control. It still needs an enforceable design and evidence.

**Required resolution:**
1. Define the worker as a separate OS/container security principal with no client-facing listener, no shared memory/API with general application workers, restricted filesystem, no core dumps/swap where supported, and narrowly controlled supervisor/host access.
2. Define the approved database access method and prohibit ORM entity materialization; specify raw projection types, driver buffering/fetch-size behavior and maximum row/byte bounds.
3. Define a capability interface that exposes only a staged opaque artifact handle to the operation coordinator; the coordinator must not receive raw row objects or generic serialization methods.
4. Define how logs, traces, metrics, exception reporting, crash reporting and process inspection are configured and tested. Host administrators and orchestration/monitoring agents must be included in the trust model.
5. Treat any uncertain memory exposure, worker crash or unexpected egress as quarantine and security incident evidence; do not claim physical erasure.
6. Add negative tests for ORM hooks, driver debug logging, exception formatting, telemetry, shared-memory access, core dumps and unauthorized process inspection.

**Closure evidence:** worker isolation profile, host/process trust graph, approved driver contract, no-ORM proof and adversarial data-egress tests.

### DBID-R44 — High: Egress permit acceptance and revocation lack an atomic linearization contract

**Affected section:** §3.2 sole egress capability; §3.3 paused workers and residual race.

The proposal states that the egress adapter validates current operation state, consumes a one-use nonce and records the transport attempt before writing. It does not define whether these steps are one atomic transaction in the same consistency domain as revocation, how a permit is fenced against concurrent revocation, or what durable state is authoritative if the adapter crashes between nonce consumption, transport state persistence and first socket write.

A permit could be accepted under one generation while a revocation commits concurrently elsewhere. “Rechecks fencing” is not enough without a linearization protocol. Also, the adapter is said to own the socket after acceptance, but no exact cancellation/termination guarantee is established for already queued writes or kernel/proxy buffers.

**Required resolution:**
1. Define the authoritative permit-consumption store and make current-generation check, lease/fencing check, nonce consumption and RELEASE_ACCEPTED transition atomic or explicitly ordered under a single consistency protocol.
2. Define revocation's conflicting update and exact winner semantics for races with permit consumption. No permit may be accepted on stale generation.
3. Distinguish durable EGRESS_ACCEPTED, TRANSPORT_WRITE_ATTEMPTED, BYTES_ACCEPTED_BY_LOCAL_SOCKET, REMOTE_RECEIPT and DELIVERY_CONFIRMED evidence. Do not infer one from another.
4. Specify crash recovery at every boundary: before consume, after consume/before state commit, after commit/before socket, during write, after local write/before receipt. Uncertain sends must not be blindly retried.
5. Specify adapter process identity, socket ownership, proxy/service-mesh behavior, cancellation semantics and what “controls continuation/cancellation” can actually guarantee.
6. Add deterministic revocation/permit race and crash-injection tests, including stale adapter instances and network partitions.

**Closure evidence:** atomic permit/revocation protocol, authoritative egress state schema, supported network topology and paused/crashed adapter tests.

### DBID-R45 — High: Polling response and candidate redemption contract remains incomplete

**Affected section:** §4 authenticated destination-service polling.

The proposal chooses polling, which resolves the earlier mechanism ambiguity. However, the response profile is still expressed as prose labels rather than a closed schema. It does not provide exact field types, required/optional fields, header allowlist, content-type/cache rules, maximum sizes or precise status mapping. The 200 COMPLETE response conflates no result, denied and expired outcomes; that may be intentional anti-enumeration, but it needs an explicit equivalence class and tests proving no observable differential.

The READY envelope contains a one-time candidate reference and operation binding, but the redemption protocol is not specified: endpoint/method, token consumption transaction, actor proof, operation binding, expiry, duplicate redemption, revocation check and outcome receipt are missing. “A signed receipt binds envelope digest and operation” does not define receipt fields, signer identity or verification lifecycle.

**Required resolution:**
1. Publish a closed OpenAPI/JSON schema with exact response status, headers, content types, field types, required fields, body-size limits and cache behavior.
2. Define the external equivalence classes for denied/no-match/expired/partial outcomes and test status/body/header/timing/resource equivalence.
3. Specify the candidate redemption endpoint and exact one-time consume transaction, including actor assertion, destination workload, tenant/branch, operation, purpose, projection, generation and expiry binding.
4. Define replay, concurrent redemption, lost response, receipt signature, receipt key rotation and source-side verification.
5. Specify polling rate/budget and operation retention/reconciliation limits; request IDs must not reveal operation existence across destinations.
6. Test cross-tenant and cross-workload polling/redemption, guessed IDs, replay, simultaneous redemption, expired envelopes, revoked actor and lost acknowledgement.

**Closure evidence:** executable API schema, redemption/receipt state machine and end-to-end anti-enumeration/replay tests.

### DBID-R46 — High: Wire grammar is not yet byte-exact end to end

**Affected section:** §5.2 signature preimage; §5.3 manifest and AAD.

The proposal defines a domain label and length prefixes, which is progress, but the complete byte contract remains ambiguous:
- the manifest canonicalization algorithm and version are referenced but not selected or fully specified;
- the canonical manifest schema is described as closed but its exact fields/types/order are not supplied;
- the digest field has no encoded length in the preimage, while the text permits profile-selected digest lengths;
- the profile identifier is ASCII-restricted but described as UTF-8; this should be one exact encoding rule;
- AAD field order is listed, but the byte serialization of each field, null/optional behavior, string encoding, integer width and length prefixes are not defined;
- encryption envelope and signature coverage still defer to future profile wording.

A signature preimage is only byte-exact when every byte and every length is deterministic for every valid input. Referring to a future profile registry is acceptable as a NOT_READY gate, but it does not resolve the current design finding.

**Required resolution:**
1. Define the canonical manifest serialization completely (for example, a named canonical JSON profile with exact duplicate-key, ordering, escaping, number, Unicode and null rules) and supply the full closed schema.
2. Add an explicit digest algorithm identifier and digest length to a length-delimited signature preimage, or define a fixed digest length per immutable profile with an exact registry schema and parser rule.
3. Define profile ID as one encoding only (ASCII bytes) and specify the exact allowed grammar and byte length.
4. Define AAD as a closed binary schema with exact field tags/order, types, widths, endianness, length prefixes and absent/null behavior.
5. Define precisely which manifest/envelope fields are covered by signature, AEAD AAD and ciphertext digest; avoid circular digest dependencies.
6. Supply cross-language positive/negative vectors for empty, maximum-length, Unicode, malformed, duplicate-key, unknown-field and altered-recipient cases.

**Closure evidence:** complete schemas, canonicalization and binary grammar plus independently reproduced byte vectors.

### DBID-R47 — High: ACL policy is still a field inventory, not an executable schema

**Affected section:** §6.1 required schema; §6.2 effective privileges; §6.3 verifier output.

The proposal improves the list of required collections, but does not actually publish a JSON Schema or equivalent machine-readable schema. Field types, exact enums, required-vs-optional rules, formats, numeric ranges, uniqueness keys and referential constraints are described generally rather than specified. The effective privilege algorithm is also a prose list of categories to expand, not a deterministic, version-specific algorithm.

The document itself identifies an “actual schema artifact” as future closure evidence. Therefore DBID-R39 remains open.

**Required resolution:**
1. Include the actual versioned JSON Schema (or equivalent normative schema artifact) with exact types, enums, required fields, nullability, formats, bounds and uniqueness/reference rules.
2. Define PostgreSQL-major-specific catalog adapters and exact object identity for all supported classes, including overloaded routines, partitions, defaults, extension-owned objects and provider-managed resources.
3. Specify a deterministic role-membership and privilege-expansion algorithm, including PostgreSQL version semantics for INHERIT/SET/ADMIN, grantors, grant options, ownership and default ACLs.
4. Define catalog normalization and unknown/unobservable behavior precisely; UNKNOWN must block PASS.
5. Provide non-empty signed fixture bundles and an independently implemented oracle with expected effective-access paths.

**Closure evidence:** validated schema artifact, PostgreSQL/provider adapters, algorithm specification, fixtures and independent verifier.

### DBID-R48 — High: Lifecycle registry remains a success path, not a complete transition contract

**Affected section:** §7 canonical lifecycle registry.

The proposal supplies a useful happy-path sequence and a list of alternative states, but does not define a complete transition graph. It does not specify for every state the allowed incoming/outgoing transitions, owner, durable store, entry/exit evidence, timeout, retry authority, terminality and compensation behavior. For example, it is unclear which transitions lead from READ_OUTCOME_UNCERTAIN to reconciliation, how RELEASE_QUARANTINED can be resolved, or how destination rejection and post-commit source revocation affect acknowledgement and pointer synchronization.

The phrase “all components consume one versioned lifecycle registry” is an architectural requirement, not the registry itself.

**Required resolution:**
1. Publish a machine-readable state and transition schema with unique state/transition IDs.
2. For every transition define source state, destination state, sole authority, preconditions, durable evidence, fencing/generation requirements, timeout, retry owner and terminal/reconciliation behavior.
3. Model all failure and uncertain outcomes, including audit outage, source revocation, worker crash, egress uncertainty, duplicate delivery, destination commit uncertainty, ack loss and pointer-sync failure.
4. Define post-artifact and post-destination-commit revocation/quarantine semantics and downstream clinical access restrictions.
5. Require each component to validate transitions against the same versioned registry; add conformance and model-based state exploration tests.

**Closure evidence:** complete machine-readable transition registry, authority matrix and exhaustive model/conformance tests.

### DBID-R49 — Medium: Trust graph and freshness remain descriptive, not deterministic

**Affected section:** §8 trust coverage and freshness schemas.

The proposal enumerates useful root, snapshot, node, edge and attestation fields, but it does not define their exact types, key formats, required/optional fields, canonical identity rules, uniqueness, referential integrity or provider adapter schemas. “Cycles are evaluated to a fixed point” does not define the capability-composition algebra, convergence condition or handling of mutually recursive conditional edges.

Freshness likewise lacks an exact computation contract for event sequence gaps, delayed events, clock skew, generation dependency mapping and witness checkpoint rollback. Saying effective expiry is the earliest of several deadlines is directionally sound but insufficient without exact time representation, inclusive/exclusive boundary semantics and deterministic invalidation rules.

**Required resolution:**
1. Publish machine-validated schemas for roots, snapshots, nodes, edges, exclusions, reconciliation and completeness attestations.
2. Define immutable ID normalization, provider adapter pagination/snapshot semantics, tombstones, evidence precedence and completeness proof.
3. Define capability composition, cycles, condition evaluation, trusted time intervals and deterministic graph convergence.
4. Define exact freshness arithmetic, time units/encoding, clock uncertainty treatment, event ordering and dependency invalidation.
5. Define independent witness signing, generation monotonicity, restore/rollback detection and outage behavior.
6. Add schema, graph, omitted-root, stale-event, clock-boundary, cycle and restore test vectors.

**Closure evidence:** schema bundle, provider adapters, deterministic graph/freshness algorithm and independent reproduction tests.

## 4. Cross-finding dependencies

- R42/R43 determine whether a source read is correctly ordered and contained.
- R44 determines whether a release permit is actually fenced at the network boundary.
- R45 determines whether the trusted destination can retrieve and redeem a candidate without an alternate disclosure path.
- R46/R47 determine whether artifacts and database access evidence can be independently validated.
- R48/R49 determine whether orchestration and trust evidence are machine-verifiable.

These gaps are coupled; none should be treated as closed solely because a prose proposal exists.

## 5. Overall closure status

PR #58 materially improves the design, but **DBID-R35–DBID-R41 remain open** pending resolution of DBID-R42–DBID-R49 and independent evidence. DBID-06 through DBID-08 remain open. CAN-01 and CAN-02 remain open. AUD-004 remains a release blocker.

D-01 through D-14 remain formally pending unless separately approved by designated authorities. D-11 project direction YES is not formal governance approval. Emergency federation remains disabled absent separate approval.

## 6. Review limitations and explicit non-authorization

This was a documentation-only adversarial review of PR #58 and its stated parent context. It did not inspect production infrastructure, live PostgreSQL catalogs, credentials, secrets, network policies, backups, audit stores or patient data. Findings describe design evidence gaps, not verified production vulnerabilities or exposure.

This review authorizes documentation and independent design review only. It does NOT authorize runtime changes, SQL, database/role/ACL/network changes, credential or secret operations, production access, patient-data access, partner onboarding, trust/key provisioning, federation activation, emergency access, pilot, deployment, release or merge. PR #58 must remain draft and unmerged pending further review.
