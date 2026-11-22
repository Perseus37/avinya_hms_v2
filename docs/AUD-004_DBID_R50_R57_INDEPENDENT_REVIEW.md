# AUD-004 DBID-R50–DBID-R57 Independent Review

**Review target:** PR #62  
**Review type:** Independent adversarial design and schema review  
**Status:** Findings remain open; this review does not authorize implementation.

## 1. Scope and limitations

Reviewed the PR #62 proposal and its three-file diff against the exact PR head. Also inspected the inherited ACL, lifecycle and trust-coverage schemas referenced by the proposal. No production infrastructure, live PostgreSQL catalogs, provider IAM, workload identity, transport topology, secrets, external revocation authorities, operating-system enforcement, audit stores or patient data were inspected.

The review is limited to consistency and enforceability of the submitted design and machine-readable contracts. Parsing JSON is not equivalent to validating schemas with a Draft 2020-12 validator or proving runtime behavior.

## 2. Executive result

PR #62 improves the protocol, especially by distinguishing egress reservation from release commitment and by making polling separate from envelope redemption. It is not yet implementation-ready. Eight residual findings remain:

- **DBID-R58 Critical:** External revocation freshness is not atomically ordered with source release authorization.
- **DBID-R59 High:** Candidate redemption's direct HTTP envelope response is not explicitly forced through the R50 egress permit/lease boundary.
- **DBID-R60 High:** The envelope schema hardcodes some profile choices while leaving other cryptographic encodings unconstrained; it is not a complete immutable profile contract.
- **DBID-R61 High:** The inherited ACL schema still groups privileges under one grantable boolean, contrary to R53's per-privilege requirement.
- **DBID-R62 High:** The inherited lifecycle schema does not structurally enforce transition references, unique IDs, terminal-state rules or graph completeness.
- **DBID-R63 High:** The inherited trust-coverage schema still allows producer assertions of completeness without binding them to authoritative provider inventory evidence.
- **DBID-R64 High:** The worker hardening schema is a descriptive checklist, not enforceable platform evidence for several mandatory controls.
- **DBID-R65 High:** Candidate-reference non-bearer semantics and redemption replay/idempotency are not represented by a closed machine-readable contract.

## 3. Findings

### DBID-R58 — Critical: external revocation and release are not one atomic consistency decision

**Evidence**

R57 requires fresh external-authority proof before transport release, then applies received revocations to the source epoch. R50 orders TRANSPORT_RELEASE_COMMITTED against updates to the source epoch row. However, an external authority can revoke a clinician, partner, issuer or key after the source obtains its freshness proof but before the source commits TRANSPORT_RELEASE_COMMITTED. The PostgreSQL epoch lock cannot serialize a state change that has not yet reached PostgreSQL and is not locked at the external authority.

The proposal says that immediate-effective external revocation requires a synchronous authority query or formally approved revocation barrier. A point-in-time query alone still leaves a query-to-commit race unless the authority offers a lease, lock, monotonic authorization token with bounded validity, or another protocol that defines when revocation becomes effective.

**Required resolution**

1. Define an explicit per-domain effective-revocation point. Conservative default: external revocation becomes effective for this protocol only when the source authority barrier has committed the new generation; document the operational delay and legal/clinical acceptability.
2. If an external authority requires immediate effectiveness, require a linearizable barrier/lease protocol from that authority. A read-only status query is insufficient.
3. Bind the authority-issued version/token, expiry and revocation generation to the source release transaction; define whether the authority promises no revocation can become effective during the token lease.
4. Define behavior when authority status changes during the protected read, after candidate redemption, during release reservation and after release commitment.
5. Provide deterministic tests for revoke-after-query/before-source-commit, revoke-during-lock-wait, event-feed loss, sequence gap, authority outage, lease expiry and source restore.

**Closure evidence:** Authority-by-authority consistency contracts, signed token/barrier schema, legal/clinical approval of effective-time semantics and race tests. Until then, R57 cannot support an immediate-revocation guarantee.

### DBID-R59 — High: candidate redemption can bypass the sole egress release boundary

**Evidence**

R51 states that POST /v1/federation/candidate-redemptions is the sole disclosure endpoint and returns the recipient-encrypted envelope and source response receipt. R50 separately requires the transport adapter to be the only process with network capability and requires TRANSPORT_RELEASE_COMMITTED before transport. The proposal does not explicitly state that the redemption endpoint only creates a staged artifact and that its HTTP response body is emitted exclusively by the R50-controlled egress adapter.

As written, an ordinary API handler could return the envelope directly to the caller without creating or consuming the R50 permit/lease. This would bypass the very release/revocation state machine added to resolve R50.

**Required resolution**

1. Make redemption an internal operation that atomically creates a durable envelope artifact and pending release operation; it must not return the envelope bytes itself.
2. Require the sole egress adapter to obtain the R50 reservation and TRANSPORT_RELEASE_COMMITTED lease before any response body bytes can be emitted.
3. Specify how the HTTP response is streamed through the adapter, including headers, buffering, compression, framework middleware, reverse proxies, retries, cancellation and partial writes.
4. Ensure logs, exception handlers, traces and debug middleware cannot serialize or expose the staged envelope before release authorization.
5. Add route-level and deployment tests proving no alternate listener, route alias, worker or proxy can deliver the artifact outside the egress adapter.

**Closure evidence:** Closed API contract, route-to-egress dataflow, enforced sole-egress topology and negative tests.

### DBID-R60 — High: wire schema is neither profile-neutral nor cryptographically complete

**Evidence**

The proposal says cryptographic profile values remain pending, but the new schema hardcodes manifest_encoding to JCS-RFC8785-UTF8, content_digest_algorithm to SHA-256, signature encoding to base64url-unpadded, and a 64-hex-character digest shape. Conversely, encryption nonce/tag, ciphertext encoding, signature byte length, algorithm/key compatibility and the exact encrypted-key/wrapping structure remain unconstrained. The schema duplicates content_digest at the envelope and manifest levels without a structural equality mechanism. AAD fields have no required bounds or canonical byte encoding in the schema.

This mixes one candidate profile's fixed values with unresolved profile-registry choices, while giving a false impression that the envelope is closed and validated.

**Required resolution**

1. Separate a profile-independent outer envelope from one immutable, versioned profile schema; do not hardcode a profile choice before approval.
2. For each approved profile, define exact algorithm IDs, key encodings, nonce/tag/signature/digest lengths, base64url rules, ciphertext and wrapped-key fields, canonicalization and AAD bytes.
3. Remove duplicated fields or define and test exact equality between copies. Define whether signature covers manifest, ciphertext, content digest or a signed manifest digest; prevent circular dependencies.
4. Add conditional schema branches keyed to an immutable profile ID, and reject unknown IDs.
5. Publish positive and negative cross-language vectors, including malformed encodings, duplicate JSON keys, wrong lengths, mismatched AAD, digest mismatch and wrong recipient.

**Closure evidence:** Closed profile-specific schemas and independently reproduced byte-level vectors. No production algorithm is approved by this review.

### DBID-R61 — High: inherited ACL schema still loses per-privilege grant-option information

**Evidence**

R53 explicitly requires each privilege grant to be represented as an individual tuple with its own grant_option. The inherited docs/schemas/aud004-cluster-acl-policy.schema.json still defines a grant with privileges as an array and one sibling boolean grantable. A single grant object therefore cannot represent, for example, SELECT WITH GRANT OPTION and UPDATE without GRANT OPTION for the same grantee/grantor/object.

The inherited schema also permits free-form object.identity and exception object_ref, and it does not bind an inventory coverage record or signed completeness evidence to the policy instance.

**Required resolution**

1. Change the schema so each privilege is its own grant tuple with its own grant-option value.
2. Use structured exact object identity, including routine identity arguments and database/schema/object class; avoid ambiguous text identity.
3. Bind the ACL document to a signed cluster-wide inventory manifest covering all databases, templates, roles, membership edges, object classes, creators/default ACLs and inaccessible scopes.
4. Require explicit completeness and verified zero-count evidence; unknown or inaccessible catalog data must prevent PASS.
5. Add fixtures proving mixed grant-option states and an independent effective-privilege oracle for each supported PostgreSQL major.

**Closure evidence:** Updated schema, representative fixture bundle, catalog adapter and independent verifier results.

### DBID-R62 — High: lifecycle schema does not enforce graph invariants claimed by R54

**Evidence**

The inherited lifecycle schema defines states and transitions, but JSON Schema uniqueItems:true only rejects structurally identical array entries; it does not enforce uniqueness of id values. Transition from is an array of unconstrained strings and to is an unconstrained string, so either can reference an undeclared state. The schema does not prohibit outgoing transitions from terminal states, require all nonterminal states to have defined failure/timeout outcomes, or require reachability from an initial state. No complete signed registry instance is supplied.

R54 mentions a separate graph verifier, but does not define its input/output evidence contract or require a signed PASS result tied to the exact registry digest.

**Required resolution**

1. Define the initial state, all declared state IDs and transition IDs in a complete registry instance.
2. Define a normative graph-verifier contract with deterministic errors for duplicate IDs, dangling references, terminal outgoing edges, unreachable states, dead ends, missing timeout/uncertain outcomes and forbidden transitions.
3. Bind the verifier result to canonical registry digest, verifier version, policy generation and signer.
4. Require model checking/property tests for prohibited success paths, stale workers, revocation, uncertain outcomes and retry.
5. Reject registry activation unless both schema validation and graph verification pass for the exact signed digest.

**Closure evidence:** Complete sample registry, graph-verifier schema/specification, negative fixtures and reproducible model-checking results.

### DBID-R63 — High: trust coverage schema still permits unsubstantiated completeness claims

**Evidence**

The inherited trust schema accepts pagination_complete:true and reconciliation.complete:true as producer-supplied constants. It does not require provider organization/account inventory evidence, pagination cursors/tokens, collection principal, per-page source digests, inaccessible-scope records or count arithmetic. The root account/region list is not mechanically reconciled with discovered nodes. The attestation contains a witness ID and signature reference but does not bind an independently verified root-scope snapshot digest, verifier build or witness trust-root.

This conflicts with R55's prose, which says completeness must be independently reconciled to authoritative provider inventory.

**Required resolution**

1. Extend the schema with authoritative root-of-scope and provider inventory evidence, collection principal, provider API/version, snapshot consistency semantics, pagination chain and per-page response digests.
2. Require explicit records for inaccessible, unsupported, excluded, deleted and unknown resources.
3. Bind exact root, snapshot, nodes, edges, exclusions and reconciliation digests into the signed attestation.
4. Define the independent verifier and witness trust-root, key lifecycle, monotonic generation and rollback rules.
5. Enforce count arithmetic and all node/edge/evidence references in the verifier; a producer-supplied complete=true must never itself establish readiness.

**Closure evidence:** Updated schema, provider fixtures including partial/inaccessible pagination, independent reconciliation output and signed witness test vectors.

### DBID-R64 — High: worker hardening schema does not prove mandatory controls

**Evidence**

The new worker schema records a free-form syscall_policy, free-form capability strings, host actor strings and generic evidence references. It does not require explicit AppArmor/SELinux enforcement, ptrace policy, seccomp profile digest, namespace IDs, mount inventory, cgroup values actually observed, crash/dump/swap evidence, host admin access, or a signed attestation over the complete effective runtime state. A caller can submit a schema-valid profile describing controls that were never enabled.

**Required resolution**

1. Distinguish desired policy from measured effective runtime evidence.
2. Define platform-specific closed schemas for supported runtimes and host OS versions, with exact policy IDs and evidence fields.
3. Include observed UID/GID, capabilities, seccomp digest, MAC profile/enforcement mode, namespace identifiers, mount list, cgroup limits, dump/swap state, ptrace restrictions, network policy and host actor inventory.
4. Bind evidence to image digest, host/workload identity, boot/runtime measurement, collection time, verifier build and signature.
5. Unsupported or unmeasurable mandatory controls must produce NOT_READY, not a schema-valid PASS.

**Closure evidence:** Platform-specific profile schemas, signed measured-state evidence and negative enforcement tests.

### DBID-R65 — High: candidate reference and redemption idempotency contract is not machine-readable

**Evidence**

R51 describes a random, hashed, one-time candidate reference bound to actor, destination, operation, purpose, action, projection, generation and expiry, but no schema defines the candidate reference record or redemption request/response. The same-idempotency-key behavior is described in prose only. The polling response schema is also absent, including which states may include a candidate reference and the exact status/body/header/cache behavior. Different implementations could therefore treat the candidate reference as a bearer token, permit replay, change projection on redemption, or return different outcomes for same-key retries.

**Required resolution**

1. Define closed schemas for polling request/response, candidate reference record, redemption request, redemption result and receipt.
2. Bind candidate reference to immutable actor subject/issuer, authenticated destination workload, tenant/branch, source operation, purpose/action, projection digest, policy version, generation vector, protocol profile and expiry.
3. Specify one-time atomic consume, same-key/same-digest idempotent replay, same-key/different-digest conflict, concurrent redemption, expiry, revocation and lost-response recovery.
4. Define externally indistinguishable denied/no-match/expired outcomes, bounded polling, cache controls and anti-enumeration behavior.
5. Ensure all successful redemption responses are subject to DBID-R59's egress gate.

**Closure evidence:** OpenAPI/JSON schemas, state/transition tests and adversarial replay/concurrency tests.

## 4. Cross-finding disposition

| Finding | Severity | Status |
|---|---|---|
| DBID-R58 | Critical | Open — external authority/source release race |
| DBID-R59 | High | Open — redemption response may bypass sole egress |
| DBID-R60 | High | Open — incomplete and internally inconsistent wire profile schema |
| DBID-R61 | High | Open — ACL schema contradicts per-privilege grant requirement |
| DBID-R62 | High | Open — lifecycle graph constraints not enforced |
| DBID-R63 | High | Open — trust completeness not independently evidenced |
| DBID-R64 | High | Open — worker profile does not prove effective controls |
| DBID-R65 | High | Open — candidate/redemption contract lacks schemas |

## 5. Overall disposition and stop conditions

PR #62 is a useful design improvement but is **not ready for implementation approval**. DBID-R58 is Critical: the source epoch cannot make an external authority's uncommitted revocation atomic. DBID-R59 also requires resolution before any redemption endpoint is implemented because it could bypass the release gate.

DBID-06–08, CAN-01, CAN-02 and AUD-004 remain open. D-01–D-14 remain formally pending; D-11 project direction YES is not formal approval. Emergency federation remains disabled.

## 6. Explicit non-authorization

This review authorizes documentation and design review only. It does NOT authorize runtime code changes, SQL, migrations, database/role/ACL/network changes, credential or secret operations, production access, patient-data access, partner onboarding, trust/key provisioning, federation activation, emergency access, pilot, deployment, release or merge. Keep this review PR draft and unmerged. PR #62 and all preceding design/review PRs remain unmerged.