# AUD-004 DBID-R74–DBID-R81 Consolidated Resolution Proposal

**Status:** Design proposal only; not accepted or authorized for implementation.  
**Parent review:** PR #67.  
**Target architecture:** PostgreSQL database-per-tenant.  
**Release status:** AUD-004 remains a release blocker.

## 1. Explicit architecture boundary

This proposal retains **database-per-tenant**. It does not introduce PostgreSQL schema-per-tenant, a tenant-schema migration, or a change to the tenant storage topology.

The existing application model identifies a tenant database through its database name. The security correction is to make database access tenant-scoped and source-owned:
- each tenant database remains a separate PostgreSQL database;
- tenant runtime identities and credentials are scoped to their own database;
- a destination API/import worker must not connect directly to another tenant's database;
- a source-owned service is the only path for an authorized source read;
- control-plane routing metadata is not a database credential or authority to retrieve one;
- provisioning, migration, backup and runtime identities remain separate.

The term **JSON Schema** in prior review documents referred only to JSON document-validation specifications. It did not mean PostgreSQL schemas. To avoid further ambiguity and premature contract machinery, this proposal adds no JSON Schema files. Any future machine-readable contract should follow an accepted architecture decision and be named/documented explicitly as a JSON document contract.

## 2. DBID-R74 — verifiable revocation proof and effective-time semantics

### Required contract

A revocation proof is an operation-scoped, cryptographically verifiable statement, not a database row reference or a status-query response. The proof must bind:
- authority and key identity, trust-registry version and proof type;
- authority domain and immutable subject identifier;
- source operation, source tenant/branch, destination workload/tenant/branch;
- action, purpose, resource/scope and policy generation;
- monotonic authority sequence, source generation, nonce;
- issued-at, effective-at, not-before (where applicable) and expiry;
- exact signed payload bytes, encoding profile, signature profile and signature.

Two proof modes remain distinct:
1. **AUTHORITY_LEASE:** the authority provides a verifiable lease/linearization guarantee that defines how revocations are ordered during the lease. A point-in-time status query is not a lease.
2. **SOURCE_BARRIER_EVENT:** the source records and commits an authoritative barrier event/generation. The protocol must state that this is the effective point for the protocol and document any propagation delay accepted by clinical, privacy and legal owners.

The source release transaction must verify the proof, compare monotonic sequence/generation, bind the proof digest to the operation and commit the source release decision under the same source consistency boundary. Sequence gaps, stale proofs, expired leases, invalid signatures, unknown keys and authority outages fail closed. The design must not claim that a source database lock can serialize a revocation that remains external and has not reached the source.

### Required race evidence

Tests must deterministically cover revocation before proof issuance, during a valid lease, between proof verification and source commit, lease expiry, sequence gap/replay, key compromise, source outage and delayed external event delivery. Governance must select the effective-time model and accept its legal/clinical implications before implementation.

## 3. DBID-R75 — sole egress and transport ordering

The source application may stage an encrypted artifact internally, but a staging result must contain only an operation identifier and generic state. It must not return artifact bytes, a bearer artifact locator, or a capability usable by ordinary API/import workers.

One separately identified egress workload is the sole principal permitted to retrieve a staged artifact and write recipient payload bytes. The required sequence is:
1. source authorization and artifact staging commit;
2. egress workload authenticates and claims the operation;
3. egress workload validates recipient, operation, digest, policy generation and revocation proof;
4. release authorization commits under the defined revocation ordering;
5. the egress adapter attempts transport;
6. local socket acceptance, remote receipt and delivery confirmation are recorded as distinct evidence.

The design must account for application servers, framework middleware, response buffering, reverse proxies, service meshes, sidecars, streaming, retries, error handlers, observability agents and host administrators. If any unreviewed component can read staged payloads or emit protected response bytes, the deployment is NOT_READY.

A database commit cannot atomically commit a remote socket write. The protocol must preserve OUTCOME_UNCERTAIN where the write may have occurred but receipt is unknown. A claimed sole-egress property requires deployment evidence and negative tests, not a boolean configuration flag.

## 4. DBID-R76 — profile registry and envelope rules

The outer transport envelope is profile-neutral. It must not hardcode a cryptographic algorithm, canonicalization format, digest algorithm, base64 encoding, nonce length or signature length.

Every envelope selects an immutable registry entry by profile identifier, version and registry generation/digest. That entry binds the exact outer-envelope schema, inner-manifest schema, canonicalization rules, signature profile, encryption profile, key registry version and approval evidence. Registry entries have explicit DRAFT, APPROVED, ACTIVE, RETIRED and REVOKED lifecycle semantics. Only an ACTIVE entry with valid approval and trust evidence may be used.

Verification order is normative: bounded outer parse; strict byte decoding; immutable registry lookup; profile/schema match; key/trust and signature verification over the profile-defined bytes; recipient/AAD validation; decryption; inner manifest validation; operation/recipient/policy binding. Unknown, retired, revoked, mismatched or downgraded profiles fail closed.

No algorithm or key format is approved by this proposal. Algorithm selection requires a separate security/cryptography decision and cross-language positive and negative test vectors.

## 5. DBID-R77 — authenticated polling, candidate redemption and idempotency

Trusted identity is derived by the server from authenticated workload transport and tenant routing. It is never accepted from caller-supplied JSON fields.

Polling returns only a generic state and, when ready, an opaque short-lived candidate reference. It never returns patient data, an artifact locator or an envelope. Response classes for denied, absent, expired, unavailable and unauthorized cases must not disclose selector-match information; cache headers, body size, status, retry and rate-limit behavior must be specified and tested.

The candidate reference is random, stored only as a hash, bound server-side to the immutable actor/workload, tenant, branch, destination, operation, purpose, action, resource, field projection, policy generation, profile and expiry. Redemption re-derives authenticated identity, compares it with the stored binding and atomically consumes the reference. The only path that can deliver the resulting envelope is the egress flow in section 3.

Idempotency is scoped to the immutable operation. Same key and same canonical request digest returns the same operation/result without a new source read; same key with a different digest returns conflict. Concurrent redemption has one winner. Lost-response recovery retrieves status/receipt only and cannot repeat source disclosure or bypass egress.

## 6. DBID-R78 — complete PostgreSQL ACL inventory

The ACL review must cover the **whole PostgreSQL cluster role namespace** and every database, including template and control-plane databases. The evidence set must include:
- database identities, owners, CONNECT and TEMP ACLs;
- all role attributes, login validity, role configuration and privilege flags;
- role membership edges with grantor, ADMIN, INHERIT and SET options;
- every grant as a separate tuple: database, stable object identity, grantor, grantee, privilege and that privilege's grant option;
- schema, table, view, materialized view, sequence, routine overload, type/domain and version-relevant object ACLs;
- default privileges for each creator role and schema;
- PUBLIC grants and ownership-derived privileges;
- extensions, SECURITY DEFINER routines, languages, foreign data wrappers, dblink and other cross-database/privileged paths;
- inaccessible, unsupported, excluded and unknown inventory scopes.

Object identities must be structured and stable enough to distinguish overloaded routines and object replacement. Effective privileges must be evaluated for direct grants, ownership, PUBLIC, inherited membership, SET ROLE, grant options, default ACLs and privileged execution paths under the actual PostgreSQL major version.

The inventory root, catalog snapshot, adapter version, verifier policy, independent oracle and signed verifier output must bind together. Any missing database, inaccessible catalog, unknown object class or incomplete inventory yields UNKNOWN/NOT_READY, never PASS.

## 7. DBID-R79 — lifecycle graph verification

A lifecycle is not accepted merely because its JSON parses or a producer declares PASS. The normative graph must define unique state and transition identifiers, valid references, exactly one initial state, reachability, terminal-state behavior, transition authority, preconditions, required evidence, timeout/failure/uncertain outcomes, retry class and compensation/reconciliation rules.

An independent deterministic verifier must reject duplicate IDs, dangling references, terminal outgoing transitions, unreachable states, nonterminal dead ends, missing uncertainty paths, unsafe cycles and transitions lacking authority/evidence. The verifier emits a signed attestation bound to the exact canonical graph digest, schema version, verifier build, policy generation, evidence bundle and trust-root version. Conformance fixtures must include both valid and deliberately invalid graphs.

## 8. DBID-R80 — provider-rooted inventory and pagination proof

Provider inventory must begin from an authoritative root-of-scope and immutable provider snapshot/consistency token. For each scope, retain the API/version, collection principal, canonical request and response evidence, cursor chain, page sequence, page digest, item count and terminal-page proof.

Reconciliation must account for all expected scopes and resources, including inaccessible, unsupported, excluded, deleted and unknown scopes. Page chains must be contiguous and scope-bound; resource/edge identifiers must be unique and references valid. Expected and observed counts must reconcile under a documented provider snapshot model. Where the provider cannot supply a consistent snapshot, the limitation must be explicit and the result cannot claim stronger completeness than the provider guarantees.

An independent verifier and witness sign the complete evidence-bundle digest, provider root, snapshot, page-chain roots, graph, exceptions, reconciliation result, trust-root version, monotonic generation and previous checkpoint. Missing pages, cursor gaps, inaccessible required scopes, unknown resources or rollback must produce UNKNOWN/NOT_READY.

## 9. DBID-R81 — trusted worker platform measurement

Worker evidence separates desired policy from observed platform measurements. It must bind the exact workload image, runtime, host, kernel and boot measurement to a platform-specific approved profile.

Measurements must include effective/permitted/inheritable/ambient/bounding capability sets; enforced seccomp and MAC profiles; PID/mount/network/user namespace identities; mount flags and propagation; CPU, memory and process limits; ptrace restrictions; core-dump and swap policy; effective network routes; crash-handler payload policy; and a complete host actor/agent access graph.

The collector must provide a verifiable attestation chain, key/trust-root version, measurement timestamp and freshness proof. An independent verifier checks both desired policy and measured state, including revocation and freshness. Unsupported, unmeasurable, stale or unknown controls yield NOT_READY. A digest string alone is not proof of enforcement.

## 10. Cross-contract acceptance gates

No implementation work begins until all of the following are accepted:
1. database-per-tenant topology is reaffirmed in the accepted architecture decision;
2. source-owned boundary is enforceable and foreign-tenant direct DB access is removed from all request, job, admin, support and recovery paths;
3. revocation effective-time semantics and authority proof are approved;
4. sole-egress transport boundary and uncertainty handling are demonstrated;
5. profile registry and cryptographic profile are approved by security review;
6. polling/redemption binding and idempotency contracts pass adversarial tests;
7. cluster-wide PostgreSQL ACL inventory and effective-privilege verifier pass on supported versions;
8. lifecycle graph verifier and conformance suite pass;
9. provider inventory completeness and independent witness are demonstrated;
10. worker platform measurement is independently verified;
11. D-01–D-14 governance decisions, clinical/privacy/legal/security/database/operations ownership and release gate are completed;
12. independent reviewers accept evidence from a non-production synthetic-data environment.

## 11. Work sequencing and stop rule

This is the final planned design-resolution bundle for DBID-R74–R81. It is followed by one independent review. If that review still identifies Critical or High findings, work stops at a consolidated implementation-readiness report. No automatic sequence of further proposal/review PRs will be created without first presenting the remaining blockers, their owners and a bounded decision plan.

The review process must not be confused with implementation progress. PR count, document count and schema count are not security evidence.

## 12. Explicit non-authorization

This document does not authorize runtime changes, SQL, migrations, database or PostgreSQL schema changes, credential/role/ACL/network changes, secret provisioning, production or patient-data access, partner onboarding, trust provisioning, federation activation, emergency access, pilot, deployment, release or merge.

All related PRs remain draft and unmerged. AUD-004 remains a release blocker. D-01–D-14 remain formally pending; D-11 project direction YES is not formal approval. Emergency federation remains disabled.
