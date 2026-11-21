# AUD-004 DBID-R50–DBID-R57 Resolution Proposal

**Status:** DESIGN PROPOSAL ONLY — NOT IMPLEMENTATION APPROVAL  
**Parent review:** PR #61  
**Release status:** AUD-004 remains a release blocker.

## 1. Purpose and disposition

This documentation-only proposal resolves the eight residual findings raised by PR #61. It defines conservative protocol semantics and machine-readable schema baselines. These remain proposals pending formal governance, independent security review, clinical/privacy/legal review and implementation-specific verification.

No production infrastructure, live PostgreSQL catalogs, provider IAM, operating-system profile, credentials, secrets, network topology, backup system, audit store or patient data was inspected. JSON Schema validation does not prove referential integrity, graph completeness, cryptographic correctness or runtime enforcement.

## 2. DBID-R50 — egress acceptance versus revocation

### 2.1 Normative distinction

EGRESS_ACCEPTED is a reservation of a one-use permit, **not irrevocable authorization to disclose**. It consumes the nonce and binds the exact operation, artifact, destination and adapter, but does not permit the adapter to write bytes.

A separate TRANSPORT_RELEASE_COMMITTED event is the source authorization linearization point for starting transport. This event is committed in the same authoritative PostgreSQL consistency domain as the source authorization epoch. A database commit cannot be atomic with a remote socket write; the protocol therefore defines a bounded in-flight authorization interval and records uncertain transport outcomes honestly.

Proposed conservative policy: a revocation that commits before TRANSPORT_RELEASE_COMMITTED prevents transport. If release commitment wins first, that operation receives a short-lived, one-use transport lease. A later revocation prevents new release commitments but cannot guarantee recall of that already-authorized in-flight operation. This residual interval requires explicit clinical/privacy/security acceptance. If governance requires revocation to stop even a release already committed but not yet written, this protocol is insufficient and must not be implemented as though it provides that guarantee.

### 2.2 State and transaction protocol

Append-only states: PERMIT_ISSUED, EGRESS_ACCEPTED, EGRESS_CANCELLED, TRANSPORT_RELEASE_COMMITTED, TRANSPORT_WRITE_ATTEMPTED, BYTES_ACCEPTED_BY_LOCAL_SOCKET, REMOTE_RECEIPT, DELIVERY_CONFIRMED, DELIVERY_UNCERTAIN, RELEASE_REJECTED, RELEASE_EXPIRED and RELEASE_QUARANTINED.

EGRESS_ACCEPTED transaction:
1. Lock the source authorization epoch row and operation row in a fixed documented order.
2. Verify current generation vector, exact artifact digest, projection, destination, recipient, adapter workload, endpoint, operation state and permit expiry.
3. Atomically consume the nonce and create EGRESS_ACCEPTED with observed generation and short reservation expiry.
4. Commit. Lost commit acknowledgement becomes EGRESS_ACCEPTANCE_UNCERTAIN; query authoritative state and never reuse the nonce.

TRANSPORT_RELEASE_COMMITTED transaction:
1. Adapter submits reservation using authenticated workload identity; source resolves adapter from mTLS/workload credentials, never caller metadata.
2. Lock the same epoch row and operation row in the same lock order.
3. Require reservation unexpired, unused for release, bound to this adapter and exact artifact/destination, and in an eligible state.
4. Compare every current revocation generation with the reservation authorization vector. Any mismatch, stale external-authority evidence, policy change, expiry or uncertainty rejects release.
5. Atomically consume the reservation for release, write TRANSPORT_RELEASE_COMMITTED, record current generation vector and create a short lease with expiry, one-use transport attempt ID and fencing generation.
6. Commit. Revocation updates the same epoch row. Whichever transaction commits first defines order: revocation first means release denied; release first means the bounded lease is authorized under the approved residual-risk policy.

The adapter must begin its single permitted write before lease expiry and may not queue the payload for later use. The transport adapter is the only process with network capability and the only component allowed to consume the lease. If paused until expiry, the lease is unusable; the adapter discards its staged transport copy and obtains fresh authorization. Old workers cannot resume under a newer fencing generation.

A revocation after TRANSPORT_RELEASE_COMMITTED cannot be represented as though it recalled bytes. It blocks new permits and release commitments after its epoch transaction commits. The already committed lease is handled only under the approved bounded-lease policy. If the policy owner does not accept that interval, release leases must not be enabled.

Once TRANSPORT_WRITE_ATTEMPTED is durable, crash, partial write, reset or missing remote receipt becomes DELIVERY_UNCERTAIN. No blind retransmission occurs. A remote receipt binds source, destination workload/tenant/branch, operation, artifact digest, projection digest, release ID, fencing generation and protocol version. Local socket success is not remote receipt.

No proxy, sidecar, service mesh, retry middleware or kernel queue may be omitted from the transport trust graph. If the platform cannot prove the adapter is the sole egress path, readiness is denied.

### 2.3 Required tests

Deterministic two-session and adapter-controlled tests cover revocation before reservation, between reservation and release, racing release, immediately after release commit, adapter pause, lease expiry, stale adapter resume, fencing change, partial write, local socket acceptance without remote receipt, duplicate receipt, lost commit acknowledgement and crash at every durable boundary.

## 3. DBID-R51 — one polling and redemption path

Choose one disclosure path: **polling never returns a candidate envelope**.

GET /v1/federation/discovery-operations/{request_id} returns only generic operation state and, when a candidate is ready for explicit authorization, an opaque non-bearer candidate_ref. It never returns patient data, resource identifier, manifest, envelope or delivery receipt. READY means only that a candidate reference exists and can be submitted for fresh authorization; it does not mean disclosure is approved.

POST /v1/federation/candidate-redemptions is the sole candidate disclosure endpoint. It requires mTLS-derived destination workload, fresh signed clinician assertion, purpose, action, exact projection, protocol version and idempotency key. The source verifies actor and policy facts, checks current generation, atomically consumes the candidate reference and persists disclosure intent before returning the recipient-encrypted envelope and signed source response receipt.

The candidate reference is random, hashed at rest, one-time, short-lived and bound to source, operation, actor, destination workload/tenant/branch, purpose, action, projection digest, generation and expiry. It is not a bearer capability. Concurrent redemptions have one winner. Same idempotency key and same canonical request returns the stored response; same key with a different digest conflicts.

Polling states: PENDING, READY, COMPLETE, UNAVAILABLE and OUTCOME_UNCERTAIN. COMPLETE is a generic external terminal class for no-match, denied, expired or policy-filtered outcomes; source audit preserves the precise reason. Polling does not prove delivery. The redemption response receipt proves the source committed a specific envelope response, not that destination durably received or imported it. Destination receipt, import commit acknowledgement and pointer synchronization remain separate evidence.

Require closed OpenAPI and JSON Schema, additionalProperties false, exact state-dependent fields, status/header/cache/body limits, mTLS binding, anti-enumeration tests, idempotency, one-time redemption, key rotation and response-loss recovery.

## 4. DBID-R52 — immutable wire profile registry and envelope contract

The previous AVINYA-FED-JSON-1 proposal is **not interoperable and must not be used on the wire** until a profile registry entry is formally approved. A profile ID is immutable; algorithms cannot be silently selected by deployment.

Companion schema: docs/schemas/aud004-federation-envelope.schema.json. The approved registry entry must fix signature algorithm, public-key encoding, signature length and transport encoding; encryption/AEAD algorithm, nonce/tag lengths and recipient key encoding; digest algorithm and length; base64url alphabet/padding; JCS version and accepted JSON constraints; exact signature preimage and AAD bytes; key ID grammar, key version, validity, revocation and rotation rules.

Until all values are approved and a signed registry artifact is published, negotiation rejects the profile as UNSUPPORTED_PROFILE. No fallback algorithm, implicit default, downgrade or per-node override is permitted.

Validation order is fixed by the approved profile: parse only bounded outer envelope; validate profile/encoding; resolve recipient/key version from trusted registry; authenticate/decrypt using exact AAD; parse authenticated manifest with duplicate-key rejection; validate closed schema and exact source/destination/actor/resource/operation bindings; verify signature over prescribed preimage bytes; verify canonical plaintext digest/length; then check expiry, revocation generation and policy before use. Implementations retain and verify exact canonical bytes, never sign one representation and verify a reserialized alternative.

Publish exact cross-language positive/negative vectors for input JSON, canonical bytes, signature preimage, digest, signature, AAD, nonce, ciphertext, tag, recipient binding, content and expected result. No production algorithm or key custody is approved here.

## 5. DBID-R53 — lossless PostgreSQL ACL model and inventory evidence

Companion schema: docs/schemas/aud004-cluster-acl-policy.schema.json.

Represent each privilege grant as an individual tuple containing grantee, grantor, privilege and grant_option. Do not attach one grant-option boolean to a list of privileges. Object identity is structured and exact: server major, database, object class, schema where applicable, object name, routine identity arguments and stable catalog identity where supported. Wildcards and free-form object patterns are prohibited in exceptions.

Every evaluation includes signed inventory coverage: cluster identity, PostgreSQL major/minor, adapter version, authoritative catalog sources, snapshot/collection ID, every database including templates/control plane, role/membership counts, per-object-class counts, exclusions, inaccessible scopes, normalized catalog digest, completeness counters and verifier identity. Empty arrays are accepted only with explicit verified zero-count evidence. Missing or inaccessible inventory is UNKNOWN, never zero.

Verifier evaluates direct/PUBLIC ACLs, per-privilege grant options, role attributes, membership grantor/admin/inherit/set options, ownership, database CONNECT/TEMP, schema CREATE/USAGE, object privileges, default privileges for each creating role, routine overloads, sequences, types/domains, partitions, extensions, foreign access and SECURITY DEFINER paths using PostgreSQL-major-specific semantics. Unknown privilege, catalog class, role edge, grantor, owner, extension or catalog row blocks PASS.

Fixtures include mixed SELECT/UPDATE grant options, PUBLIC grants, grant chains, ADMIN OPTION, INHERIT/SET ROLE, ownership, default ACLs, partitioned tables, overloaded routines, sequences, extension objects, foreign access and version-specific privileges. An independent oracle compares expected effective privileges for every supported major. A syntactically valid policy without complete signed inventory evidence cannot produce PASS.

## 6. DBID-R54 — lifecycle graph validation

Companion schema: docs/schemas/aud004-lifecycle-registry.schema.json. JSON Schema validates individual structures; a separate graph verifier is mandatory for cross-reference and reachability invariants.

Every state and transition has a stable unique ID. Each transition references declared state IDs, has exactly one authority, explicit preconditions, durable evidence, generation/fencing requirements, timeout, idempotency rule, retry owner and recovery outcome. Terminal states have no outgoing transitions. Every nonterminal state has defined success, denial, timeout and uncertainty behavior as applicable. No transition is unowned; no state is unreachable unless explicitly marked reserved; every documented failure boundary maps to a state.

Registry instance is versioned, canonicalized and signed. Workers pin an approved registry digest; stale/unknown versions fail closed. Activation and rollback require dual approval and monotonic registry generation; rollback cannot lower a security generation or re-enable a prohibited transition.

A complete registry instance and graph verifier are required before implementation. Model-based tests prove COMPLETED cannot be reached without destination commit proof, verified acknowledgement and pointer synchronization; source worker cannot assert destination commit; egress cannot assert remote receipt; timeout/uncertainty cannot become success by retry.

## 7. DBID-R55 — trust coverage and attestation completeness

Companion schema: docs/schemas/aud004-trust-coverage.schema.json.

Coverage is not accepted merely because a producer sets complete=true. Root scope must reconcile against authoritative provider organization/account/region inventory evidence, including provider API identity/version, snapshot token or documented lack of consistent snapshot, pagination cursors, collection principal, times, pages fetched and source response digests. If provider offers no atomic snapshot, attestation states the limitation and cannot claim atomic point-in-time completeness.

Independent verifier enforces:
- discovered = matched + unmatched + unknown + tombstoned, with mutually exclusive categories;
- all node, edge, evidence, account, region and exclusion references resolve;
- every in-scope account/region is represented, including inaccessible/unsupported scopes;
- every exclusion has owner, rationale, approval, scope and expiry;
- all transitive delegation, impersonation, network, secret, workload, proxy, host and management-plane paths are included;
- capability evaluation reaches deterministic least fixed point over finite sets; unknown conditions are treated as reachable for isolation analysis;
- attestation binds exact canonical digests for root inventory, provider snapshots, nodes, edges, exclusions and reconciliation.

Attestation includes witness trust-root ID, key ID/version, algorithm/profile, monotonic generation, previous attestation digest, issue/expiry, verifier build identity and signed payload digest. Evidence collection, graph construction, independent verification, witness signing and release approval are separate duties. Restore, event gap, stale pagination, unknown resource, witness compromise or generation rollback invalidates readiness.

## 8. DBID-R56 — mandatory worker hardening profile

Companion schema: docs/schemas/aud004-worker-hardening-profile.schema.json. A valid policy document is not proof that a host enforces it.

Every supported platform publishes a versioned mandatory profile covering dedicated non-root UID/GID and immutable workload identity; private PID/mount/IPC/network namespaces; no shared memory with application/control-plane workloads; read-only root filesystem and bounded staging mount; no hostPath/shared application volume; dropped capabilities; seccomp; AppArmor/SELinux; ptrace restrictions; cgroup memory/CPU/PID limits; bounded driver fetch buffers and statement timeout; core dump, swap and crash-handler policy; no debug endpoint; outbound allowlist; and supervisor/orchestration/host/kernel/monitoring/backup/emergency administrator paths.

Mandatory controls unsupported by a provider yield NOT_READY, not silent downgrade. Exceptions require named risk owner, scope, compensating control, expiry and dual approval; exceptions cannot waive sole-egress boundary, staging isolation or audit integrity. Root/host administrators remain a trust boundary included in the graph and risk acceptance.

Signed runtime evidence binds profile digest, image digest, host/platform identity, workload identity, enforcement policy versions, effective capabilities, namespace/mount/network state, collection time and independent verifier. Negative tests cover IPC, process inspection, ptrace, filesystem, dump/swap, debug, telemetry leakage and unauthorized egress.

## 9. DBID-R57 — external revocation authority freshness

A source epoch row orders only revocations already committed to that row. It does not make external identity, licensure, partner or key authorities transactionally atomic with PostgreSQL. Every generation-vector component therefore needs an authority contract.

For each domain record immutable authority ID, source system, authoritative version/sequence, authenticated event channel, signature/transport trust, ordering guarantee, maximum freshness age, propagation SLO, last confirmed version/time, gap-detection cursor, reconciliation API, outage behavior and accountable owner.

Conservative rule: **no asynchronous-only revocation feed may authorize a protected read or release**. Before search, candidate authorization, protected read, post-read authorization and transport release, source proves each required authority snapshot is within its approved freshness bound and has no sequence gap. If authority provides signed monotonic status token, bind token/version to operation and recheck at relevant boundary. If sufficiently fresh proof is unavailable, fail closed. Received revocation is applied to source epoch before source acknowledges it as locally effective; if policy defines external revocation effective immediately, source synchronously queries authority or uses formally approved revocation barrier. Eventual delivery alone is insufficient.

Event ingestion is authenticated, replay-protected, idempotent and monotonic. Duplicate events are harmless; out-of-order events cannot roll back generation; sequence gaps pause affected domain; outage/stale cache pauses affected operations; full reconciliation is required before resumption. Source epoch writer commits updated vector and generation in one transaction. Tests inject delayed/dropped/duplicated/reordered/forged events, authority outage, key compromise, sequence gap, stale cache, writer outage and restore rollback.

## 10. Closure matrix

| Finding | Proposed resolution | Required closure evidence |
|---|---|---|
| R50 | Reservation separated from release commitment; revocation ordering and bounded lease explicit | Two-session/adapter race tests; approved residual lease risk |
| R51 | Polling returns state/reference only; redemption is sole envelope path | Closed OpenAPI/schema and one-time redemption tests |
| R52 | Immutable approved profile registry; reject unapproved profile | Complete schemas and cross-language byte vectors |
| R53 | Per-privilege grant option and signed complete inventory | Major-specific catalog adapters, fixtures and independent oracle |
| R54 | Unique state/transition IDs and graph verifier | Complete registry instance and model-based conformance |
| R55 | Provider-rooted coverage, referential integrity and independent witness | Provider fixtures, count reconciliation and rollback tests |
| R56 | Mandatory platform profile with signed runtime evidence | Platform enforcement and negative tests |
| R57 | Authority-by-authority freshness and revocation barrier | External authority race, outage and sequence-gap tests |

## 11. Remaining gates

DBID-06–08, CAN-01, CAN-02 and AUD-004 remain open. D-01–D-14 remain formally pending; D-11 project direction YES is not formal approval. Cryptographic profile values, revocation freshness limits, lease duration, provider/platform support, ACL exception policy, lifecycle registry activation, trust witness independence, worker platform profile and quarantine governance require named approvals.

Emergency federation remains disabled. No production algorithms, keys, trust entries, partner configuration, worker deployment or database policy are authorized by this proposal.

## 12. Explicit non-authorization

This PR authorizes documentation and design review only. It does NOT authorize runtime code changes, SQL, migrations, database/role/ACL/network changes, credential or secret operations, production access, patient-data access, partner onboarding, trust/key provisioning, federation activation, emergency access, pilot, deployment, release or merge. Keep this PR draft and unmerged. PRs #58–#61 remain unmerged. AUD-004 remains a release blocker.
