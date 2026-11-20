# AUD-004 DBID-R07–DBID-R12 Resolution Proposal — Independent Review

**Review target:** PR #50 — DBID-R07–DBID-R12 Resolution Proposal  
**Reviewed head:** `30f1844967261c9e1843c6d0b16867b05d6d447d`  
**Status:** INDEPENDENT DESIGN REVIEW — NOT IMPLEMENTATION APPROVAL  
**Release status:** AUD-004 remains a release blocker.

## 1. Executive conclusion

PR #50 materially strengthens the design and correctly preserves the database-per-tenant model. It distinguishes database-internal selector predicate evaluation from application-visible projection, introduces source-owned revocation generations, improves credential-version rotation, separates canonical content from transport bytes, and requires machine-readable ACL exceptions.

The proposal is not yet sufficient to close DBID-R07–DBID-R12 or serve as an implementation-ready specification. This review identifies six residual findings:

1. **DBID-R13 High:** The trust-boundary principal inventory is broad but lacks a concrete, closed-world trust graph and enforceable path-denial contract.
2. **DBID-R14 High:** Predicate-only selector evaluation still lacks a complete side-channel, resource-bound and selector-input trust contract.
3. **DBID-R15 High:** Revocation generations are not yet specified as a transactionally enforceable fencing protocol across intent, read, artifact creation and release.
4. **DBID-R16 High:** Version-specific login roles do not fully resolve identity attribution and revocation through poolers/proxies or role inheritance.
5. **DBID-R17 Medium:** Canonical artifact and envelope digests lack a fully deterministic, signed, version-negotiated wire profile and chunk/reassembly contract.
6. **DBID-R18 High:** The ACL exception manifest and verifier are requirements, not a defined machine-readable schema and deterministic conformance algorithm.

These are design gaps. They are not evidence that production infrastructure is exposed or misconfigured. No production catalog, network, credential, secret manager, audit store or patient data was inspected.

## 2. Findings

### DBID-R13 — High: Trust-boundary inventory is not yet a closed-world enforceable graph

**Evidence in PR #50:** Sections 2.1–2.4 enumerate principal classes, network paths, bootstrap isolation and exceptional administrative access.

**Gap:** The inventory is a useful minimum list, but it does not define a closed-world source of truth for every concrete principal and path. Terms such as “approved provisioning zone,” “separately authenticated bootstrap workload,” “approved network path,” and “equivalent evidence” still require implementers to invent the enforcement contract. The matrix is described as required evidence, not as a versioned machine-readable artifact whose completeness can be checked.

It also does not fully distinguish identity of the workload initiating a connection from the identity of a proxy, pooler, node, host agent or provider control-plane principal that actually opens the PostgreSQL server session. A forbidden client may reach a permitted proxy; a shared runner may acquire a bootstrap identity; an infrastructure administrator may alter network policy or workload identity bindings. The proposal names many of these classes but does not specify the trust chain or prove these paths cannot be composed into a bypass.

**Required resolution:**
1. Define a versioned deployment trust graph with concrete principal IDs/classes, workload identities, host/node pools, network zones, listeners, proxy/pooler hops, database roles and allowed edges.
2. Require every edge to declare authentication, authorization, tenant/database binding, owner, expiry, audit evidence and policy source. Unknown edges or principals fail closed.
3. Define the authoritative inventory source and reconciliation process across cloud IAM, orchestration, network policy, DNS, secret broker, PostgreSQL roles and pooler configuration.
4. Explicitly model impersonation, workload identity federation, token exchange, shared runner/host compromise, proxy forwarding, management-plane changes and privileged administrator paths.
5. State which principal authenticates to PostgreSQL after every proxy/pooler hop and how the original workload identity is cryptographically or administratively bound to that session.
6. Make pre-READY tests enumerate the inventory and prove every non-bootstrap identity and route is denied, including newly introduced identities and changed network edges.

**Closure evidence:** A machine-readable trust graph, automated drift/completeness verifier, provider-specific threat model, and negative connection/impersonation tests. A manually maintained prose matrix alone is insufficient.

### DBID-R14 — High: Selector predicate-only evaluation does not fully address side channels or resource abuse

**Evidence in PR #50:** Section 3 permits bounded source-side predicate evaluation and prohibits pre-authorization projection/materialization, raw selector logging and unauthorized match details.

**Gap:** Hiding selected values and match counts does not guarantee that an unauthorized caller cannot infer patient existence through timing, status, rate-limit behavior, resource consumption, cache effects, query-plan differences, lock contention or repeated probing. The proposal refers to indistinguishable outcomes but does not define a measurable response contract or bound database work. A source-local opaque candidate reference may also become a stable correlation handle if reused across requests or leaked through logs.

The selector input trust boundary is also unclear: who canonicalizes the submitted selector, how malformed or conflicting values are handled, whether multiple selector classes can be combined, and how caller-supplied selector commitments are prevented from selecting a different predicate or key domain.

**Required resolution:**
1. Define the permitted selector input schema, canonicalization owner/version, accepted combinations and rejection behavior; callers cannot submit arbitrary SQL, commitments, key IDs or selector types.
2. Bind selector class, canonical value commitment, source tenant, destination, actor, action, purpose, request budget and expiry into the source authorization envelope.
3. Define per-actor, per-destination, per-source and global query budgets, concurrency limits, maximum execution time, cancellation and abuse response behavior.
4. Specify anti-enumeration response status/body/header/retry semantics and timing/resource leakage mitigations; define the limits of any timing guarantee rather than claiming perfect constant time.
5. Make candidate references request-scoped or otherwise non-correlatable, non-bearer and unusable outside the authorization transaction.
6. Add tests for timing distributions, query count/work bounds, cache and lock side effects, rate-limit differentials, repeated probes, malformed inputs and cross-tenant commitment correlation.
7. Require source-side audit for attempted enumeration without logging raw identifiers or disclosing match-specific detail.

**Closure evidence:** A versioned selector contract, explicit budgets and measurable anti-enumeration tests aligned with CAN-02 and the external response contract.

### DBID-R15 — High: Revocation epoch proposal lacks a fully enforceable atomic fencing protocol

**Evidence in PR #50:** Section 4 introduces source-owned monotonic generations, binds them to authorization, defines disclosure-intent compare-and-commit as the linearization point and requires checks before read/release.

**Gap:** The proposal does not specify where the generation vector is stored, how it is atomically advanced, how a worker obtains an unforgeable fencing token, or how protected reads and release are prevented from proceeding under stale generations. A database transaction that commits an intent does not by itself fence a process that already has a read transaction, a queue message, a cached authorization result or an open socket. Nor is it clear whether generation updates and disclosure-intent commits share one transactional authority or require distributed coordination.

The phrase “all required revocation generations still match under the defined release check” risks reintroducing a check/use race unless the release boundary itself is serialized or fenced. The proposal correctly acknowledges residual risk but does not identify a concrete protocol for each supported deployment topology.

**Required resolution:**
1. Select an authoritative consistency domain for each revocation epoch and define its monotonic update and read guarantees.
2. Specify token issuance, signature/integrity protection, monotonicity, scope, expiry, worker identity and operation binding.
3. Define how database reads, artifact creation, outbox enqueue and socket/network release validate a fencing generation, including stale transaction and already-open connection behavior.
4. Define transactional/outbox boundaries and recovery when revocation state is unavailable or cannot be atomically checked with the disclosure intent.
5. Prove stale workers cannot commit a protected read/artifact or release after a newer generation has taken effect; leases alone are insufficient without fencing at the resource being protected.
6. Enumerate deployment-specific race windows and require explicit acceptance by named security, privacy/legal and clinical owners before any non-zero in-flight window is enabled.

**Closure evidence:** A protocol/state diagram with exact linearization points, executable concurrency/failure-injection tests and evidence that the protected database/artifact/network boundaries enforce fencing rather than relying only on application checks.

### DBID-R16 — High: Credential-version identity remains incomplete across pooler and role-membership paths

**Evidence in PR #50:** Section 5 prefers distinct LOGIN roles per credential version, limits inherited roles and requires pooler-aware attribution and session verification.

**Gap:** Distinct login roles help only if the PostgreSQL server authenticates each connection using that role. Transaction/statement poolers or managed proxies may authenticate upstream using a shared service role, while clients authenticate separately to the proxy. In that topology, PostgreSQL catalogs show the proxy identity, not necessarily the original tenant credential version. The proposal says to document this but does not define acceptable identity propagation or prohibit unsupported configurations.

It also does not fully specify revocation of sessions that have executed SET ROLE, inherited privileges, prepared transactions, long-running transactions, replication/maintenance connections or proxy-held server sessions. Revoke of a LOGIN role prevents new authentication but does not necessarily terminate already authenticated sessions or remove privileges from sessions whose effective role has changed.

**Required resolution:**
1. Define a supported connection topology matrix: direct, session pooler, transaction pooler, statement pooler and managed proxy.
2. For each topology, identify client authentication, server authentication, authoritative session identity, tenant binding, credential-version attribution and session termination owner.
3. Prohibit a topology from claiming credential-version isolation when the upstream server session uses a shared identity without a separately verified binding and revocation mechanism.
4. Specify role inheritance and SET ROLE policy, including preventing runtime identities from assuming owner, migration, backup or provisioning roles.
5. Include prepared transactions, long-running transactions, replication/maintenance sessions and proxy-held idle server connections in rotation/revocation tests.
6. Define evidence required before rotation is declared complete and a fail-closed restricted state when provider APIs cannot verify termination.

**Closure evidence:** Per-topology identity/privilege matrix, server-side attribution tests, pooler integration tests and proof old sessions cannot continue protected work after revocation.

### DBID-R17 — Medium: Canonical digest contract still lacks a normative wire profile

**Evidence in PR #50:** Section 6 distinguishes canonical content artifact from transport envelope, defines many serialization concerns and separates integrity, authenticity, receipt and commit evidence.

**Gap:** The proposal describes fields a future profile must define but does not specify the profile structure or negotiation rules. It does not define how the canonicalization profile itself is authenticated, how unknown profile versions are rejected, how manifest signatures cover the content/envelope digests, or how chunk manifests bind chunk order, count, boundaries and reassembly. A receiver might verify a payload digest but accept a manifest or chunk sequence with different semantics. The proposal also leaves digest/signature algorithms pending, appropriately, but needs a protocol mechanism that prevents algorithm downgrade or ambiguous algorithm identifiers once governance selects them.

**Required resolution:**
1. Define a versioned canonical artifact profile identifier and a signed manifest schema; unknown, deprecated or weaker profiles fail closed.
2. Specify exact digest input bytes and domain-separation labels for content, envelope, manifest and chunks.
3. Define chunk count, index, byte length, ordering, per-chunk digest and aggregate digest/root, plus duplicate, missing, reordered and truncated chunk behavior.
4. Bind the selected canonicalization/digest/signature algorithms and protocol version into the signed manifest; prohibit negotiation downgrade.
5. Define signature verification, key status/freshness, sender identity and destination binding independently of digest verification.
6. Add immutable cross-language test vectors and substitution tests covering serialization, compression, encryption, chunking, retries and profile downgrade.

**Closure evidence:** A normative wire-profile schema, signed test vectors, cross-implementation conformance suite and explicit downgrade/replay rejection tests.

### DBID-R18 — High: ACL exception manifest and verifier remain conceptual, not machine-verifiable

**Evidence in PR #50:** Section 7 requires a version-controlled exception manifest, complete object-creator inventory and catalog verifier comparing direct/effective privileges with baseline and exceptions.

**Gap:** The document enumerates fields and expected verifier behavior but does not define a concrete schema, canonical identity model, object addressing rules, privilege normalization, manifest signing/versioning or deterministic comparison algorithm. “Approved object pattern” may permit broad wildcard exceptions unless pattern grammar and expansion rules are fixed. PostgreSQL catalogs expose privileges and ownership across multiple catalog views; effective privileges depend on role attributes, memberships, inheritance, SET ROLE, ownership and grant options. The verifier could therefore implement inconsistent interpretations and still claim conformance.

It also does not define how provider-managed roles/objects that cannot be inspected are represented, how catalog-version changes are handled, or how verifier binaries and policy manifests are authenticated.

**Required resolution:**
1. Publish a normative machine-readable schema with strict versioning, canonical principal/database/schema/object identities, explicit privilege enums and no unbounded wildcard patterns.
2. Define object identity and pattern expansion deterministically for tables, views, sequences, routines, types, schemas, databases, extensions and provider-managed objects.
3. Specify the catalog-to-policy normalization algorithm for direct ACLs, PUBLIC, ownership, grant options, role attributes, transitive membership, SET ROLE and default privileges.
4. Bind manifest, verifier version, PostgreSQL major version, provider profile and migration ID into signed conformance evidence.
5. Define treatment of unobservable provider-managed privileges: fail closed, or use a separately approved evidence adapter with documented limits; never silently assume no privilege.
6. Require verifier self-tests, mutation tests and deterministic fixtures for each privilege/object class, including wildcard expansion, unknown creator, new PostgreSQL object type, expired exception and altered manifest.
7. Require an independent verifier implementation or independent test oracle for high-risk privilege calculations before accepting the conformance result as a release gate.

**Closure evidence:** Published schema and algorithm, signed policy/evidence chain, catalog fixtures across supported PostgreSQL versions, mutation tests and independent verification.

## 3. Cross-finding assessment

| Finding | Assessment |
|---|---|
| DBID-R07 | Improved inventory; DBID-R13 prevents closure |
| DBID-R08 | Predicate/projection boundary clarified; DBID-R14 prevents closure |
| DBID-R09 | Epoch/fencing concept introduced; DBID-R15 prevents closure |
| DBID-R10 | Version-specific login direction improved; DBID-R16 prevents closure |
| DBID-R11 | Digest layers separated; DBID-R17 prevents closure |
| DBID-R12 | Manifest/verifier requirements improved; DBID-R18 prevents closure |

This review does not close any finding by implication. DBID-06 through DBID-08 from PR #45 remain separate open findings.

## 4. Required next design work

A follow-up proposal should resolve DBID-R13 through DBID-R18 with:
- machine-readable trust graph and automated drift/completeness checks;
- bounded selector input contract, side-channel/resource budgets and non-correlatable candidate references;
- concrete epoch authority, fencing token and protected-resource enforcement;
- supported PostgreSQL proxy/pooler identity and revocation matrix;
- normative signed artifact/manifest/chunk wire profile;
- concrete ACL exception schema and deterministic effective-privilege verifier.

The next design work should remain documentation-only until the governance and implementation gates are separately authorized.

## 5. Scope and limitations

This review evaluates PR #50 as a design document. It is not a live PostgreSQL privilege audit, network penetration test, workload identity assessment, secret-manager review, implementation test, production configuration assessment, privacy/legal opinion or clinical safety approval. No production infrastructure, credentials, audit store or patient data were accessed.

## 6. Explicit non-authorization

This review authorizes documentation and independent design review only. It does NOT authorize runtime code changes, SQL execution, database/role/ACL/network changes, credential or secret-manager operations, production access, patient-data access, partner onboarding, trust/key provisioning, federation activation, emergency access, pilot, deployment, release or merge.

PR #50 remains draft and unmerged. DBID-06 through DBID-08, CAN-01, CAN-02 and AUD-004 remain open. D-01–D-14 formal governance decisions remain pending; D-11 project direction YES is not formal governance approval.
