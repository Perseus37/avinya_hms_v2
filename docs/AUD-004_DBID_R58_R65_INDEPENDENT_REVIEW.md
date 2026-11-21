# AUD-004 DBID-R58–DBID-R65 Independent Review

**Review target:** PR #64  
**Review type:** Independent adversarial design and schema review  
**Status:** Residual findings remain open; this review does not authorize implementation.

## 1. Scope and limitations

Reviewed the PR #64 proposal and all seven newly added JSON Schema files at the exact PR head. Also inspected the inherited federation-envelope, worker-hardening, cluster-ACL, lifecycle and trust-coverage schemas referenced by the proposal. This is a document/schema consistency review only. No live PostgreSQL catalogs, provider inventory, workload runtime, network/egress topology, external authority, secret store, audit service or patient data was inspected.

JSON parsing is not Draft 2020-12 schema validation. Schema validation is not proof of evidence authenticity, cross-document consistency, runtime enforcement or operational behavior.

## 2. Executive result

PR #64 improves the design and adds useful machine-readable contracts, but eight residual findings remain:

- **DBID-R66 High:** The revocation-authority schema describes a lease profile, not a verifiable per-operation authority lease/barrier proof. It cannot demonstrate the consistency guarantee R58 relies on.
- **DBID-R67 High:** The sole-egress design is not represented as an enforceable transport contract; the stage-result schema exposes an artifact identifier and does not prove the handler lacks payload-emission capability.
- **DBID-R68 High:** The new profile registry conflicts with the inherited envelope schema, which still hardcodes JCS-RFC8785-UTF8, SHA-256 and base64url encoding.
- **DBID-R69 High:** Candidate/poll/redemption contracts omit authenticated polling identity and do not close the operation, receipt, replay and response-binding lifecycle.
- **DBID-R70 High:** The new ACL grant/inventory schema does not carry the complete cluster-wide role, membership, object, default-ACL and exception evidence it claims to attest.
- **DBID-R71 High:** The lifecycle schema still permits structurally invalid graphs and a self-asserted PASS without a signed, independently verifiable graph result.
- **DBID-R72 High:** Trust inventory pagination and reconciliation evidence is not sufficient to independently prove complete provider-root coverage; the witness does not bind all required evidence.
- **DBID-R73 High:** Worker attestation still permits weak or unknown control states and does not prove the observed state was measured by a trusted platform collector.

## 3. Findings

### DBID-R66 — High: revocation lease schema lacks the runtime proof that makes the lease authoritative

**Evidence**

The revocation contract's `lease_profile` contains issuer, audience, subject/scope binding, maximum lifetime, a textual revocation guarantee and a signature profile ID. It is a static authority configuration. It does not define the per-authorization lease instance: authority-issued monotonic version, subject/domain/scope, issued-at/not-before/expiry, token or signed payload digest, signature/key reference, revocation sequence, nonce/request binding, or proof that the authority promises no effective revocation during that exact lease.

The source-barrier mode likewise describes sequence monotonicity but has no event envelope or signed event proof schema binding the external event to the source generation update. A schema-valid configuration therefore cannot establish either effective-time protocol.

**Required resolution**

1. Separate static authority configuration from a closed per-operation lease/barrier evidence object.
2. Bind the proof to authority, domain, immutable subject, action/purpose, destination, source operation, monotonic authority version, source generation, issue/expiry and exact protocol checkpoint.
3. Define signature/key/profile validation and replay/sequence handling without choosing an unapproved production algorithm.
4. Define how source commits and retains the exact proof digest and how restore/rollback cannot reuse an older lease or event.
5. Add negative vectors for wrong subject/domain/audience, expired lease, repeated version, sequence gap, stale source generation and authority key revocation.

**Closure evidence:** Authority-specific signed proof contract, exact source transaction binding, and deterministic revoke/lease-expiry race tests. A static profile is not proof of a live linearizable lease.

### DBID-R67 — High: sole-egress requirement is not an enforceable API/transport boundary

**Evidence**

The proposal says internal staging returns only an opaque operation identifier and generic status, while the egress adapter alone emits payload bytes. However, the candidate schema's `stage_result` includes `artifact_id` and `egress_state`, and there is no closed contract for the internal stage endpoint, egress adapter input/output, transport response, or authenticated delivery receipt exchange. The schema does not distinguish an internal-only message from an externally serializable API response.

The prose does not specify how a web framework's response body, streaming response, exception path, reverse proxy, service mesh, compression layer or observability middleware is technically prevented from reading or emitting staged bytes. An architecture statement alone does not prove the sole-egress capability.

**Required resolution**

1. Define separate internal-only stage command/result and externally visible API response schemas; the external result must contain only an opaque operation handle and generic state.
2. Do not expose artifact IDs unless explicitly classified as non-sensitive, non-authorizing identifiers and recipient-bound.
3. Define the egress adapter's sole network capability, workload identity, artifact retrieval capability and release-permit verification interface.
4. Define response streaming, buffering, compression, cancellation, retry, partial-write, proxy and middleware behavior, including the exact point before the first payload byte.
5. Provide route/dataflow and deployment negative tests proving no alternate route, listener, worker, middleware or proxy can emit the artifact.

**Closure evidence:** Enforced deployment topology, closed API contracts and executable bypass tests. A JSON field called `egress_state` is not an egress enforcement control.

### DBID-R68 — High: profile registry and inherited envelope schema contradict one another

**Evidence**

The new wire-profile registry allows profile-specific canonicalization, digest, signature, key-agreement, encryption, key-wrapping, AAD and encoding identifiers. But the inherited `aud004-federation-envelope.schema.json` still requires `manifest_encoding = JCS-RFC8785-UTF8`, `content_digest_algorithm = SHA-256` and base64url-unpadded signature encoding. Its digest pattern is fixed at 64 hexadecimal characters. The new registry is not referenced by the envelope schema through a conditional profile-specific schema or immutable registry digest.

Consequently, a profile registry entry cannot actually select a different approved profile without conflicting with the envelope contract. Conversely, an envelope can claim a profile ID while using fields that the registry has not approved. The registry also does not define uniqueness of profile ID/version or an activation/revocation transition rule.

**Required resolution**

1. Replace the inherited fixed envelope schema with a genuinely profile-neutral outer envelope.
2. Define profile-specific closed schemas selected by exact immutable profile ID and version, and bind the exact signed registry generation/digest to each envelope.
3. Ensure all field encodings, lengths, digest copies, AAD and signature coverage are derived from the selected profile; reject any mismatch.
4. Define uniqueness and immutable version rules for profile IDs, plus approved/deprecated/revoked activation transitions and rollback protection.
5. Add cross-language vectors proving a profile is accepted only under its exact registered schema and unknown/downgraded profiles are rejected.

**Closure evidence:** Updated envelope schema, profile registry instance and digest binding, plus positive/negative wire vectors. No algorithm is approved by this review.

### DBID-R69 — High: candidate and polling contracts do not close authenticated operation binding

**Evidence**

The polling request contains only `operation_id`; the polling response carries status, request ID, candidate reference and retry delay. The schemas do not represent the authenticated destination workload/tenant/branch and actor context used to authorize polling, nor the authorization evidence that binds the operation lookup to that authenticated principal. The candidate reference record has a binding object, but no closed egress-operation record binds that reference to the staged artifact, release permit, transport state, receipt and final outcome.

The redemption request contains candidate reference, idempotency key, canonical request digest and operation ID, but does not itself carry or cryptographically reference the immutable binding digest expected by the server. The schema alone cannot demonstrate that the request being replayed is the same actor/destination/purpose/projection request originally authorized. The stage result also does not define a complete receipt retrieval or lost-response status contract.

**Required resolution**

1. Define server-derived authenticated poll context and exact operation ownership checks; caller-supplied identity fields must not become authority.
2. Bind polling, reference issuance, redemption, staged artifact, egress operation, receipt and acknowledgement to one immutable operation/binding digest.
3. Define canonical idempotency-key scope and encoding; same key/same digest returns the same operation, different digest conflicts, concurrent claims have one winner.
4. Define candidate reference hashing algorithm/key version as a profile-governed value, expiry/revocation, atomic consume and lost-response recovery.
5. Add closed schemas for egress operation, status response, delivery receipt/acknowledgement and all externally visible headers/cache/rate-limit outcomes.

**Closure evidence:** Complete operation lifecycle schemas and adversarial tests for cross-tenant polling, wrong actor, altered projection, replay, concurrent redemption and lost response.

### DBID-R70 — High: ACL inventory digest references do not constitute complete cluster-wide ACL evidence

**Evidence**

The new ACL grant schema correctly models one privilege and its own `grant_option`. However, its inventory contains database/role ID arrays, aggregate digests, a few counts and one collection evidence reference. It does not carry or reference a typed, independently verifiable inventory manifest for role attributes, membership edges and grant options, per-database ACLs, schema/object identities and owners, default ACL entries per creating role, PUBLIC privileges, extensions, privileged routines, FDW/dblink and exceptions. The grant object identity permits `schema_name: null` and a generic object name without a stable catalog identity or class-specific identity constraints.

The schema's `attestation.result` can be set to PASS without structurally binding a signed inventory artifact, verifier execution evidence, catalog snapshot or independent oracle. The proposal's prose describes these controls but the schema cannot validate their existence.

**Required resolution**

1. Add closed, typed records or digest-addressed immutable artifacts for every required catalog class, role attribute, membership option, default ACL, exception and inaccessible scope.
2. Define exact object identity per PostgreSQL object class, including stable database/role identity and routine identity arguments; reject ambiguous or unknown classes.
3. Bind a complete cluster root and every database (including templates/control DBs) to a consistent catalog snapshot and exact per-object inventory digests.
4. Require signed verifier output bound to policy, inventory, server major, adapter version, snapshot and independent oracle result; UNKNOWN/inaccessible data cannot PASS.
5. Provide PostgreSQL-major-specific fixtures for mixed grant options, inherited memberships, PUBLIC, default ACLs, ownership and privileged functions.

**Closure evidence:** Complete inventory artifact schemas, signed snapshot evidence and independent effective-privilege verifier tests.

### DBID-R71 — High: lifecycle graph schema still accepts invalid graph structure and untrusted PASS

**Evidence**

The new lifecycle schema declares states and transitions as arrays. JSON Schema `uniqueItems` is not applied to state or transition IDs and, even if applied, would not guarantee uniqueness of an ID property. `initial_state_id`, `from_state_ids` and `to_state_id` are unconstrained strings with no structural reference to declared state IDs. The schema permits empty transition arrays and does not enforce terminal-state rules, reachability, dead-end handling, or required failure/timeout edges.

The `verification` object permits `result: PASS` with arbitrary verifier ID/version and signature reference. There is no schema for a signed graph-verifier attestation, trust-root validation, canonicalization algorithm or independent verifier identity. The proposal correctly says a separate graph verifier is needed, but the supplied contract does not make a purported PASS independently checkable.

**Required resolution**

1. Define a complete registry instance and a normative graph-verifier input/output and deterministic error contract.
2. Enforce unique IDs, declared references, initial-state existence, terminal-state restrictions, reachability and required nonterminal timeout/uncertain/failure paths.
3. Define allowed cycles and progress/recovery properties; reject prohibited transitions to success.
4. Bind verifier output to exact canonical registry bytes/digest, schema version, policy generation, verifier build and signer trust root.
5. Require independent verification and negative graph fixtures before activation; a producer-provided PASS field is not evidence.

**Closure evidence:** Complete graph fixtures, verifier specification, signed attestation schema and reproducible model-checking results.

### DBID-R72 — High: provider trust evidence still cannot prove complete pagination and root reconciliation

**Evidence**

The new trust schema records cursor digests, page sequence, response digest and counts, but it does not define a verifiable cursor-chain protocol or uniqueness/contiguity constraints per scope. It does not include a provider-issued snapshot token or immutable collection request/response artifact sufficient to reproduce the inventory. Root scope is represented as independent arrays, without authoritative source object identities and a required reconciliation to every page scope. Resources and edges lack unique-ID and referential-integrity constraints at schema level.

The reconciliation object contains counts and `result: PASS/FAIL/UNKNOWN`, but no signed verifier attestation over the exact root, snapshot, pages, resources, edges and exceptions. The witness binds an attested graph digest and generation, but does not explicitly bind the reconciliation result, provider inventory digest, verifier build, previous witness generation or trust-root version. Thus a structurally valid document can assert completeness without proving it.

**Required resolution**

1. Define provider-specific snapshot and pagination evidence: request parameters, scope, page index, prior/next cursor digest, terminal-page proof, API version and raw response digest.
2. Define exact reconciliation of authoritative organization/account/project/region roots to every discovered scope and page, with unique IDs, contiguous page sequences, count arithmetic and referential integrity.
3. Require explicit evidence for inaccessible, unsupported, excluded, deleted and unknown scopes; any unapproved unresolved scope blocks PASS.
4. Sign the exact root/snapshot/page/resource/edge/exception/reconciliation digest bundle with a verifier identity independently rooted from the collector.
5. Bind witness to verifier result, all evidence digests, trust-root version, monotonic generation and previous checkpoint; define restore/rollback and witness outage behavior.

**Closure evidence:** Provider-specific complete and partial-pagination fixtures, independent reconciliation implementation and signed witness vectors.

### DBID-R73 — High: measured worker attestation still admits unproven or unsafe effective states

**Evidence**

The worker schema improves over a desired-state checklist, but several required controls are not constrained to secure values. `dump_swap.core_dumps_disabled` is any boolean; `swap_policy` permits UNKNOWN; MAC allows `OTHER_APPROVED` without a referenced approval; cgroup CPU limit is a free-form string; host actors contain only principal ID and free-form capability scope. The network evidence contains policy digests, not a measured effective route/allowlist and proof that no alternate path exists. The seccomp/MAC/cgroup/mount measurements are not bound to a platform-specific closed profile or raw trusted measurement evidence.

The top-level verification object contains a generic signature reference and digest strings, but no signed attestation payload schema identifying the trusted collector, measurement source, host boot/TPM or cloud attestation chain, verifier trust root, evidence freshness policy or revocation state. A producer can therefore supply plausible values without proving they were measured by a trusted platform source.

**Required resolution**

1. Make mandatory controls exact per supported platform profile; unsafe values (core dumps enabled, unknown swap state, unenforced MAC, unbounded cgroups or unverified network policy) must be NOT_READY.
2. Replace free-form policy strings with versioned closed identifiers and measured values; bind the observed state to exact image, host, boot and runtime identities.
3. Require trusted platform measurement provenance, collector identity, signed raw evidence digest, verifier trust chain, freshness and revocation state.
4. Enumerate host/provider administrators and their effective capabilities; unsupported/unmeasurable host controls remain explicit blockers.
5. Add negative tests with forged measurements, stale attestations, host identity mismatch, permissive mount/network policy and disabled mandatory controls.

**Closure evidence:** Platform-specific measured attestation schemas, independently verifiable signed evidence and runtime negative tests.

## 4. Disposition

| Finding | Severity | Status |
|---|---|---|
| DBID-R66 | High | Open — no verifiable authority lease/event proof |
| DBID-R67 | High | Open — sole-egress capability not enforceably contracted |
| DBID-R68 | High | Open — profile registry conflicts with inherited envelope |
| DBID-R69 | High | Open — authenticated operation/replay lifecycle incomplete |
| DBID-R70 | High | Open — ACL inventory evidence incomplete |
| DBID-R71 | High | Open — lifecycle graph and PASS attestation incomplete |
| DBID-R72 | High | Open — trust pagination/root/witness proof incomplete |
| DBID-R73 | High | Open — worker measurement provenance and secure values incomplete |

PR #64 is a meaningful documentation improvement but is **not ready for implementation approval**. The R58 authority contract and R59 sole-egress boundary remain unresolved at the enforceability level. R60's inherited schema conflict must be corrected before any wire implementation. DBID-06–08, CAN-01, CAN-02 and AUD-004 remain open. D-01–D-14 remain formally pending; D-11 project direction YES is not formal approval. Emergency federation remains disabled.

## 5. Review limitations

No production infrastructure, live PostgreSQL catalogs, provider IAM/inventory, worker runtime, secrets, external revocation authorities, transport topology, audit stores or patient data were inspected. Findings are limited to the submitted design and schemas.

## 6. Explicit non-authorization

This review authorizes documentation and design review only. It does NOT authorize runtime code changes, SQL, migrations, database/role/ACL/network changes, credential or secret operations, production access, patient-data access, partner onboarding, trust/key provisioning, federation activation, emergency access, pilot, deployment, release or merge. Keep this review PR draft and unmerged. PR #64 and all preceding design/review PRs remain unmerged.
