# AUD-004 DBID-R13–DBID-R18 Resolution Proposal — Independent Review

**Review target:** PR #52 — DBID-R13–DBID-R18 Resolution Proposal  
**Reviewed head:** `81c465ecfbdb06ad0feeb130fa183b2cc9e88a06`  
**Status:** INDEPENDENT DESIGN REVIEW — NOT IMPLEMENTATION APPROVAL  
**Release status:** AUD-004 remains a release blocker.

## 1. Executive conclusion

PR #52 materially improves the design. It introduces a closed-world trust graph, typed source-owned selectors, request-scoped candidate references, monotonic authorization generations, resource-level fencing requirements, explicit PostgreSQL connection topologies, a layered signed wire format and a deterministic ACL-verification objective.

The proposal is not yet a complete implementation-ready contract. This review identifies eight residual findings:

1. **DBID-R19 High:** The trust graph does not yet prove inventory completeness or safely model transitive trust/administrative control paths.
2. **DBID-R20 High:** Selector anti-enumeration and query budgets lack a concrete, externally testable response and cost-control contract.
3. **DBID-R21 Critical:** The disclosure-intent linearization point is not reconciled with later protected reads and revocation; a stale authorization can still race at the read boundary.
4. **DBID-R22 High:** PostgreSQL role identity and database-per-tenant isolation are underspecified because PostgreSQL roles are cluster-wide and poolers may multiplex server sessions.
5. **DBID-R23 High:** The wire profile leaves canonical manifest encoding, signature coverage, encryption recipient binding and chunk aggregate construction underspecified.
6. **DBID-R24 High:** The ACL manifest example is not yet a complete schema for PostgreSQL's cluster-wide roles, memberships, database ACLs and default privileges.
7. **DBID-R25 Medium:** Trust graph and ACL evidence are signed but lack a defined independent attestation, freshness, rollback and revocation chain.
8. **DBID-R26 Medium:** The proposal lacks an end-to-end lifecycle consistency matrix connecting source authorization, response artifact, destination import, acknowledgement and recovery.

These are design gaps, not evidence that production infrastructure is exposed or misconfigured. No production catalogs, network, credentials, secret manager, audit store or patient data were inspected.

## 2. Findings

### DBID-R19 — High: Trust graph completeness and transitive control paths are not fully enforceable

**Evidence in PR #52:** Sections 2.1–2.4 define graph nodes/edges, authoritative reconciliation, threat paths and negative pre-READY tests.

**Gap:** A signed graph and reconciliation adapter do not by themselves prove the inventory source is complete or independent of the principal being assessed. If an administrator or compromised control plane can modify both the underlying IAM/network configuration and the inventory feed, the graph may faithfully attest to an incomplete or attacker-modified view. The graph describes direct edges but does not normatively define transitive reachability, delegated administration, policy mutation rights, identity issuance authority or who can alter the verifier and its trust roots.

The pre-READY instruction to attempt connections from every workload class also does not specify how the test proves it enumerated every concrete workload, network path, alternate address family, provider management path and newly introduced principal. A negative test suite can pass while an unenumerated path remains.

**Required resolution:**
1. Define a closed-world inventory coverage manifest listing every authoritative control plane, API, account/subscription/project, region, network plane, identity issuer, orchestration domain, PostgreSQL cluster, proxy/pooler and management plane in scope.
2. Model control-plane mutation authority as graph edges: who can create identities, mint tokens, change workload bindings, alter routes/DNS, modify pooler configuration, grant PostgreSQL membership, replace trust roots or change the verifier.
3. Define transitive reachability and privilege composition, including delegated roles, group nesting, token exchange, impersonation, shared service accounts and provider support access.
4. Require independent evidence sources or a separately controlled attestation path for high-trust inventory sources; the same principal must not both mutate and solely attest the control being verified.
5. Bind verifier binary, policy, graph, inventory snapshots and trust roots to an independently controlled release/attestation chain.
6. Define enumeration completeness metrics and fail closed when any account, region, principal class, route family or management interface cannot be enumerated.

**Closure evidence:** provider-specific control-plane coverage manifest, transitive trust graph, independent inventory attestations, verifier supply-chain evidence and tests proving unenumerated/mutated control paths are detected.

### DBID-R20 — High: Selector anti-enumeration remains qualitative rather than an executable response contract

**Evidence in PR #52:** Sections 3.1–3.4 define a source-owned selector registry, keyed commitments, predicate-only pre-authorization evaluation, query budgets and common external response envelope.

**Gap:** The proposal says the protocol MUST specify exact status/body/header/retry behavior but does not define that matrix. It simultaneously lists no-match, denied, unavailable, partial, expired and throttled as distinct test cases without specifying which distinctions are intentionally externally visible. It also requires database statement cost/rows examined and lock-wait budgets, but these are not uniformly measurable or enforceable as hard PostgreSQL query limits across plans, cache states and provider implementations.

The request-scoped candidate reference still needs a precise lifetime/consumption state machine. “Non-bearer” and “bound server-side” are good goals, but no one-time transition or atomic redemption rule is specified.

**Required resolution:**
1. Define a complete outcome table mapping each internal outcome to public status, canonical body, permitted headers, retry semantics and timing treatment; identify intentionally observable throttling behavior without revealing match state.
2. Define the observable threat model and measurable thresholds for timing, response size, database work, cache effects and lock effects; avoid claiming exact constant-time behavior where the platform cannot guarantee it.
3. Specify enforceable limits using concrete mechanisms supported by each database/provider profile (statement timeout, cancellation, concurrency semaphore, per-principal rate budget, result cap and bounded query plan); unknown/unmeasurable budget dimensions must be explicit residual risks.
4. Define candidate-reference states, one-time consumption, atomic binding to candidate authorization, expiry, revocation and replay behavior.
5. Clarify selector combinations and corroboration semantics; reject conflicting or ambiguous identifiers without leaking which predicate matched.
6. Require tests for all externally observable response dimensions and for reference replay across process restart, duplicate requests and concurrent redemption.

**Closure evidence:** normative outcome matrix, deployment-specific enforceable budget profile, candidate-reference state machine and repeatable anti-enumeration tests.

### DBID-R21 — Critical: Disclosure-intent commit does not yet fence the later source read

**Evidence in PR #52:** Section 4.3 makes disclosure-intent compare-and-commit the authorization linearization point, then places protected read/artifact creation and release at later steps. Section 4.4 acknowledges in-flight revocation races.

**Gap:** If the source commits disclosure intent at generation N, then a clinician, issuer, destination or policy is revoked at generation N+1 before the protected patient read, what exactly prevents the query from reading and materializing patient data? The document says each protected resource rejects stale tokens, but it does not define how the PostgreSQL transaction itself checks the current generation in the same consistency domain as the read. A prior intent commit plus an application-level token check can still have a check/use gap. Conversely, if a database transaction locks the generation row through the read, the design must specify lock ordering, isolation, revocation blocking and the precise point at which disclosure becomes irrevocable.

The protocol also needs to distinguish authorization to perform a source read from authorization to release an already materialized artifact. Treating one intent as both without a precise state machine risks either post-revocation reads or incorrect assumptions about bytes already released.

**Required resolution:**
1. Define separate state transitions and authority points for permission to query, permission to materialize the exact resource, and permission to release the resulting artifact.
2. Specify the exact database consistency mechanism that fences the source read (for example, transactionally checking/locking the authoritative generation record in the same database/consistency domain, or a formally justified alternative); an application cache/check is insufficient.
3. Define revocation ordering against active read transactions: whether revocation waits, aborts/invalidates the read, or accepts a bounded in-flight read, and how this is evidenced.
4. Bind the read transaction, candidate, projection, operation and artifact digest to one fencing generation and ensure the source query cannot run with an older snapshot.
5. Define release authorization separately, including whether a revocation after materialization but before network release cancels delivery or enters outcome-uncertain state.
6. Provide deterministic interleaving tests for revoke-before-read, revoke-during-read, revoke-after-read-before-artifact, revoke-before-outbox-claim, revoke-before-socket-write and revoke-during-send.

**Closure evidence:** transaction/sequence diagrams with exact locks/snapshots/linearization points, database-enforced fencing proof, revocation/read interleaving tests and explicit accepted residual race windows.

### DBID-R22 — High: Cluster-wide PostgreSQL roles and database-per-tenant scope are not fully reconciled

**Evidence in PR #52:** Section 5 proposes distinct LOGIN roles per tenant and credential version, and the document retains the database-per-tenant architecture. Section 7's sample policy identifies a tenant/database and role names but does not define a cluster-wide role namespace or complete cross-database ACL model.

**Gap:** PostgreSQL roles are cluster-wide, not scoped to an individual database. A tenant-specific database does not automatically make a role tenant-specific or prevent that role from connecting to another database in the same cluster. The proposal does not specify globally unique role naming/identity, database-level CONNECT/TEMP ACLs for every database, PUBLIC defaults, role membership across the cluster, or how role creation and grant revocation are reconciled when a cluster hosts multiple tenants. It also does not define how a pooler that authenticates upstream as one shared role can preserve per-tenant authorization when server-side roles are global.

**Required resolution:**
1. Define a cluster-wide immutable role identity scheme bound to tenant, database, workload and credential version; role names must be unique within the PostgreSQL cluster.
2. Specify database-level CONNECT/TEMP policy for every database, including `postgres`, template databases and newly created tenant databases; revoke or explicitly constrain PUBLIC access as required by the approved baseline.
3. Verify effective privileges and memberships across the entire cluster, not only while connected to one tenant database.
4. Define cluster-wide role membership, SET ROLE, ownership and grantor controls, including protection against cross-tenant membership grants by migration/provisioning identities.
5. Specify role/database provisioning order so no newly created role or database is exposed through default ACLs before hardening.
6. Require cross-tenant negative connection tests from every tenant role to every other tenant database and control database, through every supported proxy/pooler mode.

**Closure evidence:** cluster-wide identity/ACL model, cross-database catalog verifier, provisioning sequence and matrix of negative connection tests across all tenants and supported connection topologies.

### DBID-R23 — High: Signed wire profile lacks normative canonical manifest and encryption binding details

**Evidence in PR #52:** Sections 6.1–6.4 distinguish canonical content, transport envelope, content/envelope/chunk digests, signed manifest and receipt/commit evidence.

**Gap:** The document specifies that a manifest is canonical and signed, but does not define its exact canonical encoding, duplicate/unknown-field handling, integer/length bounds, signature input prefix or algorithm/key identifier encoding. It says the manifest binds destination and recipient, but does not define encryption recipient binding, key wrapping, authenticated associated data, nonce uniqueness or how a recipient verifies that the ciphertext was encrypted for its identity. Chunk aggregate digest/root construction is also unspecified; “aggregate digest/root” permits incompatible implementations.

**Required resolution:**
1. Define a strict manifest schema with exact field names/types, required/optional fields, duplicate-key rejection, unknown-field policy, integer bounds, encoding and canonical byte serialization.
2. Define the exact signature input bytes and domain separation, including profile/version and manifest digest; signature algorithm and key lifecycle may remain governance-selected but the wire mechanism must prevent algorithm confusion.
3. Bind encryption recipient identity, destination tenant/branch, artifact ID, operation ID and content profile into authenticated encryption associated data; define nonce uniqueness and key-wrapping metadata requirements.
4. Define a deterministic chunk aggregate construction (including leaf domain separation, index, count, lengths and tree/root algorithm if used); do not leave “digest/root” as an implementation choice.
5. Separate source signature, recipient encryption, transport integrity, receipt and durable commit proof with explicit verifier responsibilities.
6. Provide canonical test vectors and negative vectors for duplicate fields, unknown algorithms, recipient substitution, nonce reuse, altered AAD, chunk reorder/duplication/truncation and manifest reserialization.

**Closure evidence:** normative schema and canonical encoding, cryptographic binding profile, deterministic chunk algorithm and cross-language positive/negative conformance vectors.

### DBID-R24 — High: ACL manifest schema is not yet sufficient for cluster-wide PostgreSQL privilege verification

**Evidence in PR #52:** Section 7 provides an illustrative YAML manifest and a broad catalog normalization checklist.

**Gap:** The sample schema is incomplete for PostgreSQL's cluster-wide role system and per-database privilege model. It does not encode cluster identity, role attributes, role membership edges (including grantor, admin option, inherit/set options), database-level ACLs across all databases, PUBLIC role policy, default ACL owner/creator role, or the full set of object-specific privilege forms. A single `allowed_memberships` array is not enough to express and verify effective privileges and delegation. Nor does the manifest identify the cluster-wide scope over which the verifier must search for unexpected memberships and cross-database access.

**Required resolution:**
1. Add immutable cluster identity and an explicit inventory of every database and cluster-wide role in scope, including control/template databases.
2. Define role records with LOGIN, SUPERUSER, CREATEDB, CREATEROLE, REPLICATION, BYPASSRLS, INHERIT and SET ROLE attributes, validity/connection limits and membership grant options.
3. Define membership edges with grantor, ADMIN OPTION, INHERIT/SET options and approval/evidence; verify transitive closure and ability to assume privileged roles.
4. Model database CONNECT/TEMP ACLs, PUBLIC privileges, schema ACLs, object ACLs, ownership, grant options and default ACLs per object-creating role and schema.
5. Specify exact privilege enums and object identity grammar for every supported PostgreSQL object type; unsupported or new catalog classes fail closed.
6. Require cluster-wide verifier runs and cross-database effective-privilege calculations, not isolated database-local checks.

**Closure evidence:** complete strict schema, PostgreSQL-versioned cluster-wide catalog normalization, fixtures for membership/role/database ACL combinations and independent cross-database privilege oracle.

### DBID-R25 — Medium: Signed graph and ACL evidence lack an independent attestation and rollback model

**Evidence in PR #52:** Sections 2.2 and 7.3 require signed reconciliation/conformance outputs bound to versions, snapshots and verifier build.

**Gap:** A signature establishes integrity relative to a signing key; it does not establish that the key, signer, verifier or source snapshot is trustworthy. The proposal does not define who controls attestation keys, separation of duties, verifier build provenance, key rotation/revocation, evidence freshness, monotonic sequence numbers or rollback detection. An old signed PASS could be replayed after a privilege or network change unless the consumer checks current generation and expiry against a trusted authority.

**Required resolution:**
1. Define distinct identities and duties for policy author, infrastructure operator, verifier builder, verifier runner, evidence signer and release approver.
2. Bind attestation to monotonic graph/policy/catalog generations and a trusted freshness authority; consumers reject stale or rolled-back evidence.
3. Define signing-key custody, rotation, revocation, compromise response and verification trust roots.
4. Require reproducible/attested verifier builds or equivalent independently reviewed provenance.
5. Specify evidence retention, immutable storage, access control and re-verification triggers after IAM/network/role/migration/provider changes.
6. Require independent signature and semantic verification; a signed PASS is not accepted if coverage is incomplete or any source is UNKNOWN.

**Closure evidence:** attestation trust model, monotonic freshness/rollback protocol, key lifecycle, verifier provenance and independent evidence verification.

### DBID-R26 — Medium: End-to-end lifecycle contracts are not reconciled across protocol documents

**Evidence in PR #52:** Sections 4 and 6 define authorization/fencing and response artifacts; section 8 gives a local finding closure matrix. Earlier design documents define destination import operations, recovery, acknowledgements, pointer synchronization and quarantine.

**Gap:** PR #52 does not provide one end-to-end state/authority matrix showing how the new generation/fencing token and signed manifest flow through the existing source discovery, artifact delivery, destination import, durable commit, acknowledgement, pointer sync and recovery lifecycle. In particular, it is unclear which exact generation and artifact digest the destination operation records, how a retry after source revocation is authorized, and whether a destination can commit a valid but now-revoked artifact. The document says changed artifacts require new authorization but does not reconcile that with prior retry Strategy A/B and durable idempotency semantics.

**Required resolution:**
1. Produce a cross-document protocol matrix linking each source and destination state to its authority, durable evidence, operation ID, artifact/content digest, fencing generation and allowed retry.
2. Define destination acceptance rules for a signed artifact whose source authorization was revoked after artifact creation but before receipt/commit; distinguish already-disclosed bytes from permission to create a new destination clinical record.
3. Bind import idempotency key, source pointer, destination tenant/branch, protocol version, content digest and fencing generation to the durable operation record without demographic matching.
4. Specify recovery after expired receipt, duplicate delivery, uncertain network outcome, source revocation, destination commit, ack loss and pointer-sync failure; no retry may silently create a new disclosure or report false completion.
5. Ensure acknowledgement proves the exact operation/artifact digest/generation and durable destination commit; pointer sync remains a separate completion condition.
6. Require cross-document consistency tests and state-transition/failure injection across both source and destination services.

**Closure evidence:** canonical end-to-end state/authority matrix, updated cross-document references, idempotency/recovery test suite and independent lifecycle review.

## 3. Cross-finding assessment

| Finding | Assessment |
|---|---|
| DBID-R13 | Graph and inventory requirements improved; DBID-R19 prevents closure |
| DBID-R14 | Selector and budget concepts improved; DBID-R20 prevents closure |
| DBID-R15 | Epoch/fencing concept improved; DBID-R21 prevents closure |
| DBID-R16 | Topology/role requirements improved; DBID-R22 prevents closure |
| DBID-R17 | Digest layers improved; DBID-R23 prevents closure |
| DBID-R18 | Verifier requirements improved; DBID-R24 prevents closure |
| Evidence integrity | DBID-R25 remains open |
| Lifecycle consistency | DBID-R26 remains open |

This review does not close any finding by implication. DBID-06 through DBID-08 from PR #45 remain separate open findings. CAN-01 and CAN-02 remain open. AUD-004 remains a release blocker.

## 4. Required next design work

A follow-up proposal should resolve DBID-R19 through DBID-R26 with:
- independent, complete trust inventory and transitive control-plane graph;
- executable selector outcome/budget/candidate-reference contract;
- transactionally enforced read and release fencing;
- cluster-wide PostgreSQL role/database identity and ACL model;
- strict signed manifest, encryption binding and deterministic chunk profile;
- complete cluster-wide ACL manifest and effective privilege algorithm;
- independent attestation freshness and rollback protection;
- end-to-end source/destination state, idempotency and recovery matrix.

The work remains documentation-only pending formal governance and separate implementation authorization.

## 5. Scope and limitations

This review evaluates PR #52 as a design document. It is not a live PostgreSQL privilege audit, network penetration test, cryptographic implementation review, provider attestation, workload identity assessment, secret-manager review, clinical safety approval or privacy/legal opinion. No production infrastructure, credentials, audit store or patient data were accessed.

## 6. Explicit non-authorization

This review authorizes documentation and independent design review only. It does NOT authorize runtime code changes, SQL execution, database/role/ACL/network changes, credential or secret-manager operations, production access, patient-data access, partner onboarding, trust/key provisioning, federation activation, emergency access, pilot, deployment, release or merge.

PR #52 remains draft and unmerged. DBID-06 through DBID-08, CAN-01, CAN-02 and AUD-004 remain open. D-01–D-14 formal governance decisions remain pending; D-11 project direction YES is not formal governance approval.
