# AUD-004 DBID-R42–DBID-R49 Independent Adversarial Review

**Review target:** PR #60 — AUD-004 DBID-R42–R49 resolution proposal  
**Review type:** Documentation and schema review only  
**Disposition:** CHANGES REQUIRED — do not treat DBID-R42–R49 as closed.

## 1. Executive result

PR #60 materially improves the proposal by making PostgreSQL row-lock ordering, worker isolation, egress state distinctions, candidate API shape, wire encoding direction, ACL verification, lifecycle ownership and trust freshness more concrete.

The proposal is not yet implementation-ready. This review identifies eight residual findings, including a critical gap between egress permit acceptance and the actual transport write. The three JSON documents parse as JSON, but syntactic validity is not equivalent to a complete or semantically enforceable security contract.

No production infrastructure, live PostgreSQL catalogs, credentials, secret stores, provider IAM, network policies, backup systems, audit stores or patient data were inspected.

## 2. Findings

### DBID-R50 — Critical: revocation can occur after egress acceptance but before transport write

**Evidence in PR #60:** Section 4.1 atomically consumes the nonce and records EGRESS_ACCEPTED with the current epoch generation. Section 4.2 records TRANSPORT_WRITE_ATTEMPTED before the transport call. The document says later revocation prevents new permit acceptance, but cannot promise recall of bytes already handed to transport.

**Problem:** The document does not define what happens when revocation commits after EGRESS_ACCEPTED but before TRANSPORT_WRITE_ATTEMPTED. At that point no bytes need have been handed to the transport stack. The current language can be read as allowing the adapter to write using an already accepted permit even though the source authorization generation has advanced. Conversely, rechecking only in the adapter leaves a time-of-check/time-of-use interval before the socket call. The exact authorization linearization point for disclosure is therefore unresolved.

**Required resolution:**
1. Define whether EGRESS_ACCEPTED is irrevocable authorization to disclose, even if revocation commits before any write, or merely a reservation requiring a later release decision. Obtain explicit clinical/privacy/security approval for that semantic.
2. If revocation must block an unstarted write, add a distinct source-authorized TRANSPORT_RELEASE_COMMITTED/lease state whose acceptance is ordered against revocation in the same authoritative consistency domain.
3. Bind the permit to a short lease, adapter identity, operation, artifact digest, destination and generation. Define lease expiry, revocation behavior, adapter pause/resume and stale-worker fencing.
4. Define the irreversible boundary honestly: a database commit cannot be atomic with a remote socket write. Once transport may have accepted bytes, record uncertain delivery and never claim revocation recalled them.
5. Add deterministic tests for revocation after EGRESS_ACCEPTED but before write; adapter paused after every durable state; lease expiry; old adapter resume; revocation racing release commitment; partial write; connection reset and lost state acknowledgement.

**Closure evidence:** A state/authority diagram and executable two-session/adapter interleaving tests demonstrating the approved ordering and residual risk.

### DBID-R51 — High: polling READY response conflicts with one-time candidate redemption

**Evidence in PR #60:** Section 5.1 says a READY polling response contains candidate_envelope. Section 5.2 separately defines POST /v1/federation/candidate-redemptions, which consumes the candidate reference and returns the recipient-encrypted envelope and signed receipt after commit.

**Problem:** The protocol has two apparent delivery paths for the same candidate envelope. It is unclear whether polling itself releases protected candidate data before the explicit redemption endpoint, whether polling only returns a non-sensitive candidate reference, or whether redemption changes the polling state. This undermines the stated source authorization boundary and leaves replay, audit and one-time consumption semantics ambiguous.

**Required resolution:**
1. Choose one path. Preferred: polling returns only generic operation state and an opaque non-bearer candidate reference; the separate redemption endpoint performs fresh clinician authorization and atomic one-time consume before returning the encrypted envelope.
2. If polling is intended to deliver the envelope, remove the separate redemption endpoint or define it strictly as a separate, non-overlapping protocol. There must be one authoritative disclosure transition.
3. Define the exact state progression, including whether READY means candidate exists, redemption is authorized, or artifact is already released.
4. Define COMPLETE versus DELIVERY_CONFIRMED and whether delivery_receipt is a destination receipt, a source response receipt or a final protocol receipt.
5. Publish a closed OpenAPI/JSON Schema contract with conditional field presence, exact status codes, request/response examples, idempotency, one-time redemption, key rotation and lost-response recovery.

**Closure evidence:** A single sequence diagram and tests proving no envelope can be obtained through polling before the authorized redemption transition.

### DBID-R52 — High: wire profile remains incomplete despite byte-exact preimage

**Evidence in PR #60:** Section 6 defines JCS manifest encoding, a signature preimage and JCS AAD, but leaves cryptographic algorithms and key custody to D-07. It does not provide the complete envelope field schema or exact binary/encoding constraints for all fields.

**Problem:** The preimage is more precise, but the complete signed/encrypted wire object is not byte-exact. The profile does not normatively identify the signature algorithm, public-key encoding, signature encoding/length, encryption/AEAD algorithm, nonce length, tag length, base64url canonical rules, key-ID grammar or exact manifest field types/constraints. The profile registry is referenced but not defined. A profile name alone cannot guarantee cross-implementation agreement unless its immutable registry entry fully fixes these values. The document also needs to specify how the signature is carried and how the recipient validates exact manifest bytes without parse/re-serialize ambiguity.

**Required resolution:**
1. Provide a closed machine-readable JSON Schema for manifest and envelope, with required fields, exact types, formats, bounds, enum values and additionalProperties false.
2. Define a profile registry entry that fixes signature algorithm, public-key format, signature bytes/encoding, encryption/AEAD algorithm, nonce and tag lengths, key identifiers, base64url padding rules and all digest algorithms. If these remain governance-pending, mark the wire profile non-interoperable and not byte-exact.
3. Define whether the signature is over the exact preimage bytes and the exact serialized signature representation; prohibit parse/re-serialize ambiguity.
4. Specify the precise order and validation rules for decrypt, authenticate AAD, parse manifest, verify signature, validate recipient, validate content digest and apply expiry/revocation.
5. Add published cross-language positive and negative test vectors containing exact input bytes, expected canonical bytes, preimage bytes, digest, signature, AAD, ciphertext and verification result.

**Closure evidence:** Approved profile registry plus independent cross-language implementation tests. No production algorithm choice is implied by this review.

### DBID-R53 — High: ACL schema cannot faithfully represent PostgreSQL ACL semantics or prove inventory completeness

**Evidence in PR #60:** aud004-cluster-acl-policy.schema.json models a grant with a privileges array and one grantable boolean; object identity is a free-form string; database/schema/object/default-privilege arrays may be empty. The document requires enumeration but the schema has no completeness manifest or expected inventory counts.

**Problem:** PostgreSQL grant option is associated with individual privileges, not one boolean for an arbitrary set of privileges. A grant with SELECT grantable and UPDATE not grantable cannot be faithfully represented. The schema also does not establish a complete catalog inventory: empty arrays or omitted objects can pass JSON Schema validation. Free-form object references do not enforce exact identity/signature grammar or prohibit wildcard/pattern ambiguity. PostgreSQL privilege catalogs and role semantics vary by major; a generic enum can silently omit newly introduced privileges or catalog object classes.

**Required resolution:**
1. Represent each privilege grant as a distinct tuple (grantee, grantor, privilege, grant_option) or an equivalent lossless per-privilege structure.
2. Define exact structured object identity by object class, database, schema, name, routine argument identity where relevant, and server major; reject wildcard and ambiguous identities.
3. Add a signed inventory-coverage section: catalog source, server version, database/role/object counts, enumerated object-class counts, completeness status, exclusions, snapshot ID and catalog digest. Empty arrays must be valid only when accompanied by explicit verified zero-count evidence.
4. Define the complete role-level and cluster-level privilege inventory, including version-specific capabilities and membership options. Unknown privilege/object types must block PASS.
5. Provide PostgreSQL-major-specific schema adapters and non-empty fixtures that exercise mixed grant options, PUBLIC, inherited grants, SET ROLE, owners, default ACLs, partition inheritance, routine overloads, extension objects and newly introduced privileges.

**Closure evidence:** A lossless schema and verifier fixture suite with independent expected effective-privilege results for every supported PostgreSQL major.

### DBID-R54 — High: lifecycle schema does not validate transition references or graph completeness

**Evidence in PR #60:** aud004-lifecycle-registry.schema.json permits arbitrary strings for transition from and to; it does not constrain them to declared state IDs. It does not require unique state/transition IDs or ensure terminal states have no outgoing transitions. The document itself acknowledges that the schema does not prove graph completeness.

**Problem:** A file can validate while containing transitions to nonexistent states, duplicate IDs, unreachable states, missing failure transitions or unauthorized terminal-state exits. This is not yet an executable state machine and cannot independently prevent contradictory lifecycle definitions.

**Required resolution:**
1. Define a normative registry format with stable unique state and transition IDs and references constrained to declared IDs.
2. Add graph-level validation rules: every nonterminal state has defined outcomes; terminal states have no outgoing transitions; every transition has exactly one authority; no unowned or unreachable states; every failure boundary maps to an explicit state.
3. Require explicit state invariants, operation identity, durable evidence, fencing semantics, idempotency behavior, timeout behavior and recovery authority.
4. Define how registry versions are signed, activated, rolled back and rejected when a worker uses an obsolete version.
5. Supply a complete machine-readable lifecycle instance, not only a schema, and model-check it for illegal paths such as COMPLETED without verified acknowledgement and pointer synchronization.

**Closure evidence:** Validated complete registry instance, graph verifier and model-based tests proving prohibited transitions are unreachable.

### DBID-R55 — High: trust coverage schema permits unsupported completeness claims

**Evidence in PR #60:** aud004-trust-coverage.schema.json requires pagination_complete true and reconciliation.complete true, but it does not bind those claims to a provider-issued snapshot token or an enumerated root-scope inventory. Reconciliation counts are not constrained to reconcile. Edge references are strings without schema-level referential integrity. The attestation has a witness ID and signature reference but no explicit witness trust-root/key version or signed payload profile.

**Problem:** A producer can construct a syntactically valid document with incomplete account/region coverage, arbitrary node/edge references, inconsistent counts and an unsupported complete=true assertion. The schema does not itself prove the trust graph is closed-world or that the witness is independent of the operator being attested.

**Required resolution:**
1. Bind root scope to authoritative provider organization/account/region inventory evidence, including source API, snapshot/version token, pagination cursor evidence and collection identity.
2. Define arithmetic invariants for discovered/matched/unmatched/unknown/tombstoned counts and require every node/edge endpoint and evidence reference to resolve.
3. Require explicit per-account/per-region coverage and exclusions; an inaccessible or unsupported scope must block readiness, not disappear from the graph.
4. Bind attestation to exact canonical root/snapshot/nodes/edges/exclusions/reconciliation digests, witness key ID/version, algorithm, signature profile, monotonic generation and previous-attestation digest.
5. Define independence and separation of duties for provider evidence collection, graph construction, verification, witness signing and release approval. Add restore/rollback, event-gap, stale-pagination and witness-compromise tests.

**Closure evidence:** Provider-specific authoritative inventory fixtures and an independent verifier that rejects incomplete, inconsistent or rolled-back graph evidence.

### DBID-R56 — Medium: isolated worker profile lacks mandatory host/process enforcement contract

**Evidence in PR #60:** Section 3 proposes disabling core dumps and swap where supported, minimal capabilities, restricted filesystem and controlled host access, but leaves the actual OS/container enforcement profile and mandatory-versus-optional controls undefined.

**Problem:** These are design intentions rather than a testable deployment contract. Different runtimes and hosts may interpret where supported differently. No mandatory policy is specified for UID/GID, seccomp, AppArmor/SELinux, ptrace/process inspection, namespace isolation, capabilities, cgroup limits, read-only mounts, crash handlers or supervisor access. A worker could be called isolated while sharing host-level access paths that expose staged data.

**Required resolution:**
1. Publish a mandatory per-platform worker hardening profile with explicit required controls and a documented exception process.
2. Define workload UID/GID, namespaces, capabilities, syscall policy, filesystem/mounts, cgroup memory/CPU/PID limits, ptrace restrictions, dump/swap behavior, crash handling and host-admin access.
3. Distinguish mandatory controls from provider-dependent controls; unsupported mandatory controls yield NOT_READY rather than silent waiver.
4. Include the worker and all privileged host/control-plane actors in the signed trust graph.
5. Test the deployed profile with negative process-inspection, IPC, filesystem, dump, swap, debug and egress tests.

**Closure evidence:** Platform-specific profile, signed runtime evidence and negative tests. A privileged host administrator remains a trust boundary and must be explicitly accepted.

### DBID-R57 — High: external revocation authorities are not atomically coupled to epoch generation

**Evidence in PR #60:** Section 2 says all revocation mutations are applied by a source-owned epoch writer and the epoch vector covers issuer/key trust, clinician status/affiliation, partner/destination, policy and credential/session domains.

**Problem:** Those facts may be owned by external identity, clinician-registration, partner or key authorities. The proposal does not specify how an external revocation becomes effective in the source epoch transaction. If an external authority commits a revocation but notification, polling or epoch update is delayed, the source may continue to accept the old generation during the gap. The local PostgreSQL lock protocol orders only mutations that have reached the epoch row; it does not establish freshness of external authorities.

**Required resolution:**
1. For every generation-vector domain, name the authoritative system, event/version source, authenticated transport, ordering guarantee, maximum propagation delay and failure behavior.
2. Define whether revocation becomes effective only after source epoch commit or immediately at the external authority. If immediate, source must synchronously consult or otherwise prove freshness before search/read/release; asynchronous event delivery alone is insufficient.
3. Define event sequence/gap detection, replay protection, duplicate/out-of-order processing, outage handling, stale cache rejection and full reconciliation.
4. Bind each generation component to an immutable authority/version and evidence reference. Missing or stale domain evidence must fail closed.
5. Test delayed, dropped, duplicated and reordered revocation events, authority outage, key compromise and source epoch writer failure.

**Closure evidence:** Domain-by-domain authority/freshness matrix and deterministic revocation propagation tests, including external authority changes that occur before the source epoch is updated.

## 3. Overall disposition and gates

PR #60 is a useful design advance, but DBID-R42–R49 are not closed. DBID-R50 is Critical and blocks any implementation approval until the transport/revocation race is resolved. DBID-R51–R55 and R57 are High; DBID-R56 is Medium.

DBID-06–08, CAN-01, CAN-02 and AUD-004 remain open. D-01–D-14 remain formally pending; D-11 project direction YES is not formal approval. Emergency federation remains disabled.

## 4. Explicit non-authorization

This review authorizes documentation and design review only. It does NOT authorize runtime code changes, SQL, migrations, database/role/ACL/network changes, credential or secret operations, production access, patient-data access, partner onboarding, trust/key provisioning, federation activation, emergency access, pilot, deployment, release or merge. PRs #58–#60 remain unmerged. AUD-004 remains a release blocker.
