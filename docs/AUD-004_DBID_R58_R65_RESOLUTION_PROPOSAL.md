# AUD-004 DBID-R58–DBID-R65 Resolution Proposal

**Status:** Design-only proposal; all decisions require independent review and formal governance approval.  
**Parent review:** PR #63.  
**Scope:** Resolve DBID-R58 through DBID-R65. This proposal does not close AUD-004 or authorize implementation.

## 1. Binding constraints

1. No point-in-time external status query is described as atomic with a later source PostgreSQL transaction.
2. No candidate-redemption handler, polling handler, application middleware or proxy may emit the protected envelope. The sole egress adapter is the only payload-emitting capability.
3. No production cryptographic algorithm, key format, profile, retention period or provider topology is selected by this proposal.
4. No producer-supplied boolean such as `complete`, `ready` or `pagination_complete` constitutes independent evidence.
5. Schemas validate structure; independent verifiers validate cross-record invariants, evidence provenance, graph properties and measured runtime state.
6. Any unknown, stale, unsupported, inaccessible or unverifiable mandatory evidence results in NOT_READY / fail closed.

## 2. DBID-R58 — external revocation effective-time contract

Two explicit modes are permitted, selected per revocation domain by governance:

- **SOURCE_BARRIER_EFFECTIVE (conservative default):** an external change becomes effective for this federation protocol only when the source authority has authenticated the event, checked sequence continuity and committed the corresponding monotonic source epoch update. The external system's earlier wall-clock event time is retained as evidence but is not represented as atomically enforced by the source. Governance must explicitly accept the propagation interval and its clinical/legal consequences. Until the source barrier commits, the protocol's last committed source generation remains authoritative; the system must not claim instantaneous external revocation.
- **AUTHORITY_LEASE (only when externally supported):** the external authority issues a signed, bounded lease/token with a monotonic version and a contractual guarantee that the authorization cannot be revoked effective during the lease, or provides an equivalent linearizable barrier. The source validates the issuer, audience, domain, subject, version, expiry, scope and signature; stores the exact token digest/version; and checks the lease at release authorization. A read-only status query is not a lease.

For each domain (issuer/key, clinician registration, affiliation, partner/destination, purpose policy, workload identity, credential/session and audit authority), record its authority, mode, event sequence, freshness policy, outage behavior, owner and approval. Sequence gaps, replay, invalid signatures, expired leases, clock uncertainty or unavailable authority block new authorization. A source restore must not roll back accepted generations; recovery requires an independently witnessed monotonic checkpoint.

A revocation arriving after a source release transaction commits cannot be retroactively serialized before it. The durable event is applied immediately upon receipt, blocks subsequent releases and triggers the approved in-flight/quarantine policy. If immediate external effectiveness is mandatory and no authority lease/barrier exists, federation remains disabled for that domain.

## 3. DBID-R59 — sole egress capability

Candidate redemption is split into two operations:

1. **Internal stage:** authenticate destination service, validate fresh clinician authorization and candidate binding, atomically consume the candidate reference, and persist an encrypted artifact plus a pending egress operation. It returns only an opaque operation identifier and generic status to the internal caller. It has no response-body capability and cannot return artifact bytes.
2. **Egress release:** the isolated egress adapter loads the staged artifact by operation ID, obtains the R50 reservation and commits the R50 release authorization/lease against current source generations, then emits bytes. It alone owns the network response capability for the protected payload.

The API route is a control-plane facade, not the payload transport. Framework response objects, streaming generators, middleware, compression, exception handlers, reverse proxies, service meshes, retries, debug tooling and tracing must not buffer, serialize, log or emit the artifact before the adapter's permit check. If deployment topology cannot enforce the sole-egress property, the deployment is NOT_READY.

Transport evidence distinguishes EGRESS_ACCEPTED, TRANSPORT_RELEASE_COMMITTED, TRANSPORT_WRITE_ATTEMPTED, LOCAL_SOCKET_ACCEPTED, REMOTE_RECEIPT and DELIVERY_CONFIRMED. These are not synonyms. Partial writes, disconnects and ambiguous delivery produce OUTCOME_UNCERTAIN; never infer remote receipt from local socket acceptance. A database commit cannot atomically commit a remote socket write.

## 4. DBID-R60 — profile-neutral envelope and immutable profile registry

The envelope schema defines only profile identifier, opaque artifact ID, profile-specific protected payload object and bounded routing/operation references. It does not impose JCS, SHA-256, base64url, Ed25519, AEAD or any other algorithm before governance approval.

An immutable profile registry entry contains a unique profile ID and version; canonicalization identifier; digest, signature, key-agreement, content-encryption and key-wrapping algorithm identifiers; exact key/nonce/tag/signature/digest lengths and encodings; AAD grammar; signature preimage grammar; recipient binding; parser limits; approval evidence; activation generation and revocation state. Unknown, unapproved, deprecated or revoked profiles are rejected. A profile's schema is closed and conditional on that exact profile ID.

Each approved profile must publish byte-level test vectors and negative vectors for duplicate JSON keys, malformed encodings, wrong lengths, mismatched recipient/AAD, altered manifest, digest mismatch, invalid signature, unsupported version and downgrade attempts. Content digest, envelope/ciphertext digest, signature and receipt are separate evidence values with non-circular definitions. Duplicate copies of a digest are prohibited unless the schema/verifier requires byte-for-byte equality.

## 5. DBID-R61 — ACL grant tuples and inventory binding

Represent every grant as an individual tuple: cluster identity, database identity, exact object identity, grantor, grantee, one privilege, and that privilege's grant-option boolean. Structured object identities distinguish database, schema, relation, sequence, routine (including identity argument types), type/domain, language, extension and other supported object classes. Unknown object classes or ambiguous identities fail closed.

The ACL policy is bound to a signed inventory manifest covering the cluster root, every database including templates/control databases, roles, attributes, membership edges and options, schemas, objects, owners/creators, default ACLs, PUBLIC ACLs, extensions, privileged functions, FDW/dblink and inaccessible scopes. The independent verifier reconciles provider/cluster inventory to catalog enumeration, validates counts and references, computes effective privileges for the supported PostgreSQL major, and emits a signed result bound to exact policy and inventory digests. Missing/inaccessible catalog data cannot produce PASS.

## 6. DBID-R62 — lifecycle graph registry

A complete registry declares a version, initial state, unique state IDs, unique transition IDs, terminal states and every transition. Every transition references declared states and declares actor authority, preconditions, durable evidence, timeout behavior, retry class and failure outcome. Terminal states have no outgoing transitions. Every nonterminal state has explicit success, denial, timeout and uncertain/failure handling where applicable. Every state must be reachable from the initial state unless explicitly marked as an externally entered recovery state with its own proof.

A separate deterministic graph verifier rejects duplicate IDs, dangling references, unreachable states, terminal outgoing edges, dead ends, missing timeout/uncertain paths, unauthorized transitions, cycles without bounded progress/recovery semantics and prohibited shortcuts to success. The verifier result includes deterministic error codes, verifier build/version, policy generation and exact canonical registry digest; it is signed by an independently controlled verifier identity. Activation requires schema validation AND graph verification for the same signed digest. JSON Schema alone is not claimed to prove graph completeness.

## 7. DBID-R63 — provider-rooted trust inventory and witness

The trust evidence starts from an authoritative organization/account/project/subscription and region root-of-scope obtained using a separately identified collection principal. Record provider API/version, snapshot semantics, collection start/end, pagination cursor chain, page sequence/count/digest, response digest, resource counts and all inaccessible, unsupported, excluded, deleted and unknown scopes. Root inventory must be reconciled to discovered nodes and edges with exact count arithmetic and referential integrity.

The producer cannot self-assert readiness using `complete=true`. An independent verifier obtains or validates authoritative root evidence, checks pagination continuity and scope coverage, reconciles every discovered object and capability edge, calculates the graph digest, and signs a result bound to root/snapshot/node/edge/exclusion/reconciliation digests. An independent witness verifies the verifier identity and trust root, monotonic generation and rollback protection. Missing pages, inaccessible scopes, unsupported APIs, stale snapshots, unresolved resources or witness failure result in NOT_READY.

## 8. DBID-R64 — measured worker enforcement

Worker policy separates **desired configuration** from **measured effective state**. Platform-specific closed profiles are required for each supported OS/runtime/provider combination. Required measurements include immutable workload/image identity; host and boot identity; UID/GID; effective capabilities; seccomp policy digest and enforcement; AppArmor/SELinux profile and enforcement mode; namespace IDs; mount inventory and writable paths; cgroup CPU/memory/PID limits; ptrace restrictions; core-dump/swap state; network policy; crash-handler behavior; host/platform actor inventory; collection time; verifier build and signature.

Evidence must come from trusted platform APIs/attestation sources, not application-provided strings. Desired state differing from observed state is NOT_READY. Unsupported or unmeasurable mandatory controls are NOT_READY, not waived by an empty field or generic evidence URI. Host administrators and provider control-plane administrators remain explicit trust assumptions unless independently constrained and attested.

## 9. DBID-R65 — candidate, polling, redemption and receipt contracts

Closed schemas define:
- polling request and response;
- candidate-reference record;
- redemption request and internal stage result;
- egress operation;
- delivery receipt.

The reference is a random opaque identifier; only a keyed/hash representation is stored. It is not authority by possession. Redemption requires fresh source authorization and binds immutable actor subject/issuer, destination workload, tenant and branch, source operation/resource, purpose/action, projection digest, policy version, generation vector, profile ID and expiry. The reference is consumed atomically in the same authoritative store as the idempotency claim and operation transition.

Same idempotency key + same canonical request digest returns the same operation result without a second source disclosure; same key + different digest is a conflict. Concurrent consumes have exactly one winner. Expired/revoked references cannot be redeemed. Lost-response recovery returns status/receipt for the same operation but does not repeat a source read or emit the envelope outside the egress adapter. Polling returns status and opaque reference only; it never returns protected candidate data. Denied/no-match/expired outcomes use the approved generic external contract and bounded rate/resource budgets.

## 10. Cross-document invariants and validation plan

- R58 authority mode and generation evidence must be referenced by the R50 release permit and lifecycle operation.
- R59 is a hard architectural constraint on R50: all payload bytes flow through one measured egress adapter.
- R60 profile ID and canonical profile digest bind envelope, candidate reference, artifact, receipt and acknowledgement.
- R61 ACL PASS requires R63 trust-root evidence and R64 measured worker identity for the verifier.
- R62 lifecycle verifier result binds the exact operation registry used by source and destination components.
- R63 witness generation and R58 revocation generations must be rollback-resistant and independently reconciled.
- R65 candidate and redemption operation IDs bind to the R62 lifecycle and R59 egress gate.

Required tests include deterministic concurrency/interleaving tests, sequence gaps and authority outage, duplicate/replay/concurrent redemption, same-key/different-digest conflict, middleware/proxy bypass attempts, partial transport writes, profile downgrade and malformed bytes, mixed grant-option fixtures, lifecycle graph mutation, incomplete provider pagination, unknown ACL objects, forged worker evidence and stale witness rollback.

These are design/test requirements, not completed test results. JSON schema parsing or structural validation does not prove PostgreSQL behavior, provider completeness, OS enforcement or protocol safety.

## 11. Open decisions and stop conditions

DBID-06–08, CAN-01, CAN-02 and AUD-004 remain open. D-01–D-14 remain formally pending; D-11 project direction YES is not formal approval. Algorithm selection, external authority effective-time semantics, provider/OS support matrix, retention/residency, quarantine governance, deployment topology, operational ownership and independent verifier/witness key custody require named approvals.

No runtime code, SQL, migrations, ACLs, credentials, network changes, production access, patient-data access, partner onboarding, trust provisioning, federation activation, emergency access, pilot, deployment, release or merge is authorized. Keep all related PRs draft and unmerged. Emergency federation remains disabled.
