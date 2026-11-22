# AUD-004 DBID-R66–DBID-R73 Independent Review

**Review target:** PR #66, `design/aud-004-dbid-r66-r73-resolution`  
**Reviewed head:** `18e3df5438ac1992a5967387ec900ba0efec3899`  
**Status:** Independent design review; no implementation or production authorization.

## Executive result

PR #66 improves the design and removes the inherited envelope's hardcoded cryptographic profile assumptions. However, the new contracts remain insufficiently normative to authorize implementation. Eight residual findings DBID-R74–R81 are recorded below. DBID-R74 is Critical because a proof reference and digest do not define verifiable authority evidence or close the external-revocation race. DBID-R75–R80 are High; DBID-R81 is High.

## DBID-R74 — Critical: revocation proof schema does not define verifiable signed proof or effective-time semantics

The proof instance contains `signature_ref`, `proof_digest`, authority/domain and sequence fields, but does not define the signed proof object, signature algorithm/profile reference, signer key identity/trust chain, exact signed bytes, canonicalization, authority scope, or verification order. `AUTHORITY_LEASE` and `SOURCE_BARRIER_EVENT` share one schema; `lease_guarantee` and `event_type` are optional and are not conditionally required by mode. A source-barrier event is not itself proof that the authority has serialized revocation against the release. The schema also lacks an explicit effective-at / not-before boundary and monotonic sequence comparison semantics.

**Required:** distinct closed schemas for lease and barrier-event evidence; exact signed payload and profile-registry binding; issuer key/trust identity and revocation; authority subject/scope and operation binding; effective-time and sequence semantics; source-side verification/commit protocol; and deterministic interleavings for revoke-before-lease, revoke-during-lease, lease expiry, sequence gap, key compromise and source outage. A status response or detached reference must never be accepted as a lease.

## DBID-R75 — High: sole-egress contract asserts exclusivity but does not prove or order it

The schema accepts `sole_payload_emitter: true` and capability strings, while deployment evidence is only opaque digests. The `milestones` array requires six unique values but does not encode order, timestamps, state transitions, permit identity, worker identity or evidence for each transition. A valid instance can therefore list milestones in an impossible order. The contract does not prove that the API server, framework middleware, reverse proxy, service mesh, sidecar, error handler or streaming layer cannot emit protected bytes independently.

**Required:** model egress as a transition/evidence registry with ordered, timestamped, operation-bound events; identify actual authenticated workload and permit; include enforced route/capability inventory and network-policy evidence; explicitly model buffering, streaming, retries, proxy termination and response-body paths. Negative tests must prove non-egress principals cannot read artifacts or write recipient payloads. A boolean assertion is not proof of sole capability.

## DBID-R76 — High: profile-neutral envelope still lacks encoding and immutable profile binding semantics

Replacing hardcoded JCS/SHA-256/base64url assumptions is directionally correct, but the outer schema represents byte strings as unconstrained JSON strings without declaring the transport encoding or decoding limits. It permits algorithm/key identifiers without binding them to a selected immutable registry entry. The proposal says profile-specific validation occurs, but the schema does not reference a profile-specific schema digest, registry generation, activation/revocation state, or exact profile-selection/verification order. `registry_digest` is a free string and is not tied to the signature preimage by a schema-level contract.

**Required:** define an outer transport encoding independently of cryptographic algorithm choice; exact byte decoding and size limits; immutable profile registry instance schema and digest; profile-specific schema digest and version; registry generation, activation, retirement and revocation semantics; exact order for lookup, parse, signature verification, decryption and manifest validation; and cross-language negative vectors. Do not approve any algorithm by implication.

## DBID-R77 — High: poll/redemption contracts do not enforce authenticated binding or safe response equivalence

The candidate contract uses `oneOf` over several message shapes, but poll response permits a candidate reference for any status and does not require one for READY or prohibit it for DENIED/UNAVAILABLE/EXPIRED. Poll context is a separate object rather than an enforced server-authenticated envelope around the request/response. The redemption request accepts caller-supplied operation and binding digests; no schema-level relation proves they match the stored operation or authenticated principal. Candidate reference format does not establish that it is hashed at rest, non-bearer, single-use or bound to actor, tenant, branch, purpose, action, projection, policy generation and profile. Generic response equivalence, cache controls, size limits and rate-limit semantics are absent.

**Required:** separate request/response schemas with conditional status rules; server-derived authenticated context that is never accepted from request JSON; immutable operation binding stored and recomputed server-side; candidate reference entropy/hash/storage contract and one-time atomic consume; idempotency scope and digest relation; exact generic response/cache/rate-limit contract; and tests for cross-tenant polling, actor substitution, replay, concurrent consume, expiry, revocation and lost responses.

## DBID-R78 — High: ACL evidence schema still does not contain a complete, lossless ACL inventory

The new inventory records role attributes and membership options, but database and object ACLs are represented only by opaque `acl_digest` values. There are no per-privilege grant tuples with grantor, grantee, privilege and grant-option fields; no structured stable object identity including schema/name/signature/OID lifecycle; no explicit PUBLIC principal; and no exact role attributes such as validity/configuration and all version-specific role flags. The object class enum does not clearly cover every relevant catalog object or privileged execution path. The schema does not require unique role/database/object IDs or prove inventory completeness across every database and template. The proposal's claim that each grant has its own grant option is therefore not represented by this schema.

**Required:** include typed per-privilege ACL grant rows and structured object identity; represent PUBLIC and ownership separately; enumerate all required PostgreSQL-major-specific object classes, default ACLs, extensions, routines, FDW/dblink and privileged paths; require unique IDs and referential integrity; bind complete catalog inventory/root counts and inaccessible scopes; and sign an independently verified effective-privilege result. Unknown catalog coverage must block PASS.

## DBID-R79 — High: lifecycle graph attestation is detached from a normative graph instance and verifier rules

The added attestation schema only records a registry digest and a verifier result. It does not reference a normative lifecycle graph schema or constrain the inherited graph registry. The prior lifecycle registry's structural weaknesses (duplicate IDs, dangling state references, invalid initial state, terminal outgoing transitions, unreachable/dead-end states and incomplete failure paths) are not repaired by adding an attestation envelope. The attestation itself has no explicit canonicalization profile, verifier policy digest, evidence bundle digest, freshness/expiry or signer key/trust version.

**Required:** define a complete graph instance schema with unique identifiers and exact references; a deterministic graph-verifier specification and error taxonomy; explicit initial, terminal, retry, timeout, uncertainty and compensation rules; signed attestation binding canonical graph bytes, schema, verifier build/policy, evidence and trust-root generation; and model-check/conformance fixtures. An attestation must not convert an invalid or incomplete graph into PASS.

## DBID-R80 — High: provider trust attestation does not independently prove page-chain completeness

The attestation schema binds aggregate digest strings and a result, but it does not prove the underlying provider evidence was collected from a complete authoritative root. The referenced inventory schema still relies on page cursor digests and producer-supplied collection statuses without a verifiable cursor chain, exact request/response binding, snapshot consistency guarantee, terminal-page verification, per-scope expected counts or explicit pagination completeness witness. The attestation lacks the exact evidence-bundle schema/version, page-chain root, scope reconciliation arithmetic and independent witness signature over the complete bundle. A producer can still assert a PASS with opaque digest references unless the verifier contract is independently specified and enforced.

**Required:** bind provider root-of-scope, immutable snapshot token and API version; preserve canonical request/response evidence and contiguous cursor chain; prove terminal page for every scope; reconcile expected/observed counts and inaccessible/unsupported/excluded/deleted scopes; require unique IDs/referential integrity; sign the full evidence-bundle digest and verifier output with an independent witness and rollback-resistant checkpoint. Missing pages or unknown scopes must yield UNKNOWN/NOT_READY.

## DBID-R81 — High: worker measurement schema does not establish trusted platform enforcement

The schema constrains some controls, but a digest field is not evidence that seccomp or network policy is actually enforced. The worker contract does not bind a platform-specific closed profile to an approved measurement policy; host actor capabilities remain arbitrary strings; mount records lack propagation/privilege semantics; namespace IDs are free strings; and there is no explicit trusted collector attestation signature/key chain and freshness/revocation proof in the schema itself. Empty capability arrays do not fully describe Linux effective, permitted, inheritable, ambient and bounding sets or other platform privilege channels. CPU/memory/PID limits have no approved profile bounds.

**Required:** platform-specific closed schemas and versioned approved profiles; measured kernel/runtime/boot and workload identity; explicit capability-set dimensions and forbidden privilege paths; mount flags/propagation, namespace identity, seccomp and MAC enforcement evidence; network routes and host-admin/agent access graph; bounded resource values; signed collector/platform attestation chain with freshness and revocation; and an independent verifier. Unsupported or unmeasurable controls must be NOT_READY.

## Cross-cutting disposition

- PR #66 is a useful design iteration but is **not implementation-ready**.
- DBID-R74 Critical and DBID-R75–R81 High remain open.
- DBID-06–08, CAN-01, CAN-02 and AUD-004 remain open.
- D-01–D-14 remain formally pending. D-11 project direction YES is not formal approval.
- Emergency federation remains disabled.
- Review is limited to repository documentation and schemas. No production infrastructure, live PostgreSQL catalogs, provider IAM, secrets, transport, audit stores, worker hosts or patient data were inspected.

**Non-authorization:** This review authorizes no runtime implementation, SQL, migrations, credential/role/ACL/network changes, production or patient-data access, partner onboarding, trust provisioning, federation activation, emergency access, pilot, deployment, release or merge. Keep PRs draft and unmerged; AUD-004 remains a release blocker.
