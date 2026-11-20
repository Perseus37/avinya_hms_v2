# AUD-004 DBID-R13–DBID-R18 Resolution Proposal

**Status:** DESIGN PROPOSAL — NOT IMPLEMENTATION APPROVAL  
**Parent review:** PR #51 — Independent review of DBID-R07–DBID-R12  
**Scope:** Documentation only; database-per-tenant architecture retained.

## 1. Executive summary

This proposal turns the six residual findings in PR #51 into concrete protocol and verification requirements:

- **DBID-R13:** a versioned, closed-world deployment trust graph with authoritative inventory reconciliation and fail-closed drift handling;
- **DBID-R14:** a strict source-owned selector contract, bounded predicate execution, request-scoped candidate references and measurable anti-enumeration behavior;
- **DBID-R15:** a source-owned monotonic authorization epoch and resource-enforced fencing protocol with explicit linearization points;
- **DBID-R16:** a supported PostgreSQL connection-topology matrix that distinguishes client identity from upstream server identity and makes revocation verifiable;
- **DBID-R17:** a normative signed wire-profile and chunk manifest contract separating content, transport and receipt evidence;
- **DBID-R18:** a concrete ACL exception manifest and deterministic effective-privilege conformance algorithm.

This is a design proposal, not a statement that the required infrastructure currently exists. Values that require product, security, clinical, privacy/legal or platform-owner approval remain unresolved. The proposal does not close earlier findings by assertion.

## 2. DBID-R13 — Closed-world deployment trust graph

### 2.1 Normative graph model

Every supported deployment MUST publish a versioned trust graph. The graph is a closed-world allowlist: an identity or communication edge not present in a currently approved graph is denied. Prose inventories and cloud-console screenshots alone are not sufficient.

Each graph document MUST contain:

- `graph_schema_version`, `graph_id`, `environment_id`, `deployment_profile_id`, `provider_profile`, `postgres_major_version`, `issued_at`, `expires_at`, `policy_version`, and a cryptographic digest/signature envelope;
- immutable node identifiers and node type;
- authoritative source system and source object identifier;
- owning team and accountable approver;
- tenant/database scope, environment and region;
- authentication mechanism and authorization policy reference;
- credential or workload-identity reference (never secret material);
- permitted network/listener/proxy/pooler relationships;
- server-side PostgreSQL identity after each hop;
- evidence references, last-reconciled time and expiry;
- lifecycle state: proposed, approved, active, quarantined, revoked or expired.

Node types MUST include, where present: application workload, source authorization service, destination API, background worker, admin/support workload, migration runner, backup/restore workload, monitoring agent, CI/CD runner, orchestrator/controller, host/node agent, service-mesh sidecar, secret broker, proxy, pooler, PostgreSQL cluster, database, LOGIN role, non-login owner role, provider management principal and human administrator.

Each directed edge MUST specify source node, destination node, protocol/listener, authentication, authorization, tenant/database binding, allowed operation, network policy, identity propagation/binding, owner, approver, expiry, audit evidence and the authoritative inventory that proves the edge exists. Edges MUST be narrowly scoped; “internal network”, “trusted subnet” or “admin access” are not valid unrestricted grants.

### 2.2 Authoritative inventory and reconciliation

A deployment adapter MUST reconcile graph nodes and edges against all applicable authoritative systems, including cloud IAM/workload identity, orchestration and admission policy, network security groups/firewalls, routing/peering, DNS, private endpoints, proxies/poolers, secret broker, PostgreSQL roles/ACLs, backup/restore control plane and provider management-plane evidence.

The reconciler MUST compare both presence and absence. It MUST detect newly created identities, role memberships, listeners, routes, trust relationships, shared runners, token-exchange paths and proxy configuration drift. An inventory source that is unavailable, stale beyond its approved freshness limit, incomplete or not independently attributable produces UNKNOWN, not PASS.

The reconciler MUST emit a signed result bound to graph ID/digest, inventory snapshot IDs, provider/profile versions, verifier version, timestamp and findings. Any unknown principal, unapproved edge, unbounded wildcard, expired approval or unexplained drift moves the tenant provisioning state to QUARANTINED and prevents READY. No operator may override an unknown edge by editing only the graph; the authoritative source and approval evidence must be corrected.

### 2.3 Threat paths and trust binding

The threat model MUST explicitly cover workload identity federation and token exchange, impersonation, compromised shared CI runner, host/node compromise, sidecar or proxy forwarding, DNS/route substitution, secret-broker compromise, provider control-plane changes, privileged human administration and backup/restore paths.

For every proxy/pooler hop, record both the client-authenticated identity and the identity that actually authenticates to PostgreSQL. If the upstream identity is shared, the graph must specify an independently verifiable binding from the original workload and tenant to the server session; otherwise that topology is unsupported for source-tenant authorization.

Control-plane permission to discover a database or secret reference MUST NOT imply permission to connect to that database. A route, DNS name, service-mesh identity or possession of a tenant identifier is not database authorization.

### 2.4 Pre-READY enforcement tests

Before a tenant can become READY, automated tests MUST enumerate graph nodes and attempt connections from every non-bootstrap workload class to every tenant database, including via alternate DNS names, private endpoints, proxies, poolers, IPv4/IPv6, peering and management paths. All unapproved attempts must be denied and produce attributable evidence.

Tests MUST include newly introduced identity/edge mutations, forged workload claims, token audience substitution, shared-runner impersonation, proxy forwarding, expired graph approvals, inventory outages and stale reconciliation. A positive test of the intended source identity is not sufficient; negative tests must prove that each forbidden path is denied.

**Closure evidence:** signed machine-readable graph, authoritative reconciliation adapters, drift tests, provider-specific threat model, complete path inventory and negative connection/impersonation evidence for each supported deployment profile.

## 3. DBID-R14 — Selector input, bounded execution and anti-enumeration

### 3.1 Source-owned selector contract

The source service owns selector parsing, canonicalization, key selection, commitment generation and query construction. Callers submit only a versioned typed request. They MUST NOT submit SQL, ORM expressions, arbitrary selector types, commitments, key identifiers, canonicalization profiles or source-internal candidate references.

The initial supported selector allowlist is an explicit governance-controlled registry (for example, exact ABHA identifier, exact MRN with source-branch scope, or exact phone plus approved corroborating attributes). This list is illustrative, not a declaration that any selector is approved. Prefix, wildcard, fuzzy, phonetic, multi-result and bulk selectors are denied unless separately approved and threat-modeled.

For each selector class, the registry defines canonicalization version, accepted character/length rules, normalization, required corroboration, source scope, keyed commitment domain, query plan constraints, permitted result cardinality and expiry. Invalid, ambiguous, conflicting or unsupported input is rejected before query execution. Canonicalization happens inside the trusted source boundary; raw selector values never enter general telemetry or cross-tenant logs.

The source authorization envelope binds selector class and canonical commitment to source tenant, destination tenant/branch, actor and issuer, action, purpose, policy version, requested data categories, request ID, query budget and expiry. Commitments MUST use source-specific keyed derivation with domain separation and managed key rotation. Plain SHA-256 or other unkeyed deterministic hashes of low-entropy identifiers are prohibited. A commitment from one tenant, purpose or protocol domain MUST be unusable in another.

### 3.2 Predicate evaluation versus materialization

The database may evaluate an approved predicate against protected source columns before candidate authorization only within the source authorization boundary and under the strict query contract. This is database-internal comparison, not permission to materialize a patient entity.

Before candidate authorization, the application may receive only a request-scoped opaque candidate reference and the minimum metadata strictly required to complete authorization. It MUST NOT select, hydrate, serialize, log or expose patient demographics, allergies, clinical data, related ORM entities or unrestricted row contents. Eager/lazy relationship loading and identity-map leakage are prohibited. SQL projection allowlists and ORM instrumentation MUST prove this boundary.

Candidate references MUST be random, short-lived, request-scoped, non-bearer, non-correlatable across requests and bound server-side to the actor, source, destination, selector request and authorization transaction. They cannot be used to retrieve a record through another route or after the authorization transaction expires.

Only after source candidate authorization commits may a separate narrowly scoped query materialize the exact approved resource and field projection. The actual SQL read-set and serialized projection must be equal to or narrower than the authorized categories and fields. A widened projection, implicit relationship load or changed destination/purpose invalidates authorization.

### 3.3 Resource and abuse budgets

The source policy MUST define approved limits for each actor, destination, source tenant and global scope: request rate, concurrent requests, selector attempts, database execution time, statement cost/rows examined, lock wait, memory, response size and outstanding candidate references. Limits are governance-owned configuration, versioned and audited. Missing or unavailable limit state fails closed.

Queries MUST use bounded plans and cancellation. Timeouts and cancellation must terminate server-side work, not merely abandon the client await. Cache behavior, prepared statements, indexes, lock behavior and query-plan changes must be assessed for existence leakage. Rate-limit counters and audit records must not reveal whether a candidate matched.

### 3.4 External anti-enumeration contract

For unauthorized, no-match, denied, expired, throttled, unavailable and policy-restricted outcomes, the public response MUST use the approved common response envelope and avoid match-specific fields, counts, candidate references, source topology or diagnostic details. A generic externally visible response does not remove the requirement to record the precise internal outcome in the restricted source audit.

The protocol MUST specify status code, body schema, header set, retry behavior and rate-limit behavior for each outcome class. Where operationally possible, response handling should reduce timing and resource differentials; the design MUST state measurable bounds and residual leakage rather than claim perfect constant-time behavior. High-volume probing is stopped by budgets and abuse controls, not by relying on response padding alone.

Tests MUST compare response status/body/header distributions and timing/resource distributions for match, no-match, denied, unavailable, partial, expired and throttled cases; test cache and lock side effects, repeated probes, cross-tenant commitment correlation, malformed selectors, caller-supplied key IDs/commitments, concurrency exhaustion and query cancellation. Tests must establish practical detection thresholds and document residual side-channel risk.

**Closure evidence:** versioned selector registry and input schema, source-side canonicalization and keyed commitment design, projection instrumentation, explicit budgets, request-scoped candidate reference tests and measurable anti-enumeration contract aligned with CAN-02.

## 4. DBID-R15 — Authorization epochs and resource-enforced fencing

### 4.1 Authoritative generation state

Each source authorization authority MUST maintain monotonic generations for the independently revocable domains: issuer/key trust, clinician identity/registration/affiliation, partner/destination trust, source policy, workload/database binding, credential/session state and audit availability. The source authority owns updates. Generations cannot be supplied or lowered by callers, destinations, workers or the control plane.

The design MUST identify one authoritative consistency domain for generation reads and updates per deployment. It must state transaction isolation, durability, failover behavior, read consistency, clock assumptions and recovery semantics. A cache may accelerate lookup but cannot authorize disclosure from stale or unverifiable state. If authoritative generation state is unavailable, stale or split-brain, new disclosure is denied and in-flight work is restricted/uncertain.

### 4.2 Fencing token

After authorization, the source issues an integrity-protected fencing token containing at minimum: protocol/profile version, source tenant, source authorization authority, actor/issuer subject, destination tenant/branch, operation ID, resource reference, action, purpose, policy version, authorized data projection, generation vector, worker identity, lease/fencing sequence, issuance/expiry and unique token ID.

The token is unforgeable under a governance-approved signing/MAC profile, audience-bound, non-transferable and monotonic for the protected operation. A worker cannot refresh or widen its own token. Renewal requires a source-authority decision against current generations. A lease expiry alone is not a fence; every protected resource must reject stale generations.

### 4.3 Linearization and enforcement points

The protocol MUST define the following ordered points:

1. **Search authorization commit:** source durably authorizes the bounded selector query under the current generation vector.
2. **Candidate authorization commit:** source binds the exact candidate/resource and allowed projection to the current actor, destination, purpose and generations.
3. **Disclosure-intent compare-and-commit:** the source atomically compares current generations and commits a unique disclosure intent/outbox record. This is the authorization linearization point for that disclosure attempt.
4. **Protected read/artifact creation:** the source query and canonical response artifact are bound to the intent, operation, projection and fencing sequence. The source boundary rejects stale tokens at the resource being read or written.
5. **Release gate:** immediately before outbox dispatch/socket write, the release authority validates current generations and fencing sequence. The implementation must define how this check is serialized against revocation and what happens if a send is already in progress.

If the database, artifact store, outbox and network dispatcher do not share a transaction, the design must specify the transactional outbox, compare-and-swap/fencing protocol and failure states. An application-level “check then use” is insufficient. A stale worker must be unable to commit a protected artifact, claim an outbox item or release bytes after a newer generation is effective. Every consumer must validate the token at its own resource boundary.

### 4.4 In-flight disclosure and residual race windows

Revocation after disclosure-intent commit but before bytes leave the source is not automatically equivalent to revocation before authorization. The protocol must define the authoritative revocation ordering, whether an already committed intent may proceed, whether a release gate can atomically serialize against revocation, and what uncertainty is recorded if the network write has begun.

No design may claim that bytes already received by a destination can be recalled. A revocation observed after possible disclosure requires an explicit outcome-uncertain/restricted workflow, source and destination audit, and clinical/privacy governance. Any non-zero race window requires named security, privacy/legal and clinical owner acceptance before activation.

Concurrency tests MUST pause workers at every boundary, advance each generation independently, restart/reassign leases, duplicate messages, partition the authority, fail over the store, delay network writes and replay stale tokens. Assertions must prove stale workers cannot cross protected DB, artifact, outbox or release boundaries.

**Closure evidence:** deployment-specific state/sequence diagrams, consistency contract, token profile, resource-level enforcement proof, concurrency/failure-injection suite and approved residual-risk record.

## 5. DBID-R16 — PostgreSQL connection topology and credential revocation

### 5.1 Required topology matrix

Each deployment MUST declare exactly which connection modes it supports. The matrix must cover direct PostgreSQL, session pooler, transaction pooler, statement pooler and managed proxy where relevant. For each mode, record:

- client authentication identity and credential version;
- proxy/pooler authentication identity;
- upstream PostgreSQL LOGIN role and server-observed session identity;
- tenant/database binding and how it is independently verified;
- whether `SET ROLE`, role inheritance or session state can cross requests;
- server-session owner and termination API;
- handling of prepared transactions, long-running transactions, replication, maintenance and idle pooled sessions;
- authoritative evidence and failure behavior.

A topology is unsupported for tenant source authorization if it collapses multiple clients into a shared upstream PostgreSQL identity without an independently verified, tamper-resistant tenant/credential binding enforced at every protected operation. Caller-set `application_name`, connection tags or custom GUCs are diagnostic metadata, not authority.

### 5.2 Role constraints

Use distinct LOGIN roles per tenant and credential version where server-side attribution is required. LOGIN roles MUST NOT own objects. Non-login owner roles, migration roles, backup roles and provisioning roles are separate. Runtime roles MUST NOT inherit or SET ROLE into owner, migration, backup, provisioning or platform-admin roles. Role membership, `INHERIT`, `SET` options, superuser, replication, bypass-RLS, create-role, create-database and connection privileges are included in effective privilege review.

Role names and credential references must be immutable/versioned and bound to tenant, database, workload and approved topology. Secret rotation must not silently retarget an existing pool to a different tenant or credential version.

### 5.3 Rotation and revocation completion

Rotation sequence: stop new checkouts; mark old credential version revoked; block new authentication; drain active work within approved bounds; invalidate checked-out client and server connections; dispose application pools; terminate remaining old PostgreSQL backend sessions as required; handle prepared transactions and proxy-held sessions; verify server-side absence of old identities; then declare rotation complete.

The completion check must query authoritative server/proxy state and be attributable to the old credential version. Engine disposal alone, client disconnect alone or caller-supplied session labels do not prove server-side termination. If the provider cannot enumerate or terminate a relevant session class, the tenant remains restricted until an approved compensating isolation boundary is proven.

Tests MUST cover each supported pooler mode, credential overlap, old/new role attribution, SET ROLE and inherited memberships, long transactions, prepared transactions, replication/maintenance connections, proxy idle pools, network partition, pooler restart and failed termination. The verifier must reject unsupported topologies rather than silently downgrade the assurance claim.

**Closure evidence:** signed topology matrix, server-observed identity tests, least-privilege role graph, rotation/revocation runbook and evidence that old sessions cannot continue protected work.

## 6. DBID-R17 — Normative signed wire profile

### 6.1 Profile negotiation

Every response artifact MUST identify a versioned canonicalization profile and wire profile. The source chooses the profile from an allowlisted protocol registry; the destination cannot request a weaker profile. Unknown, deprecated, unsupported or weaker versions/algorithms are rejected. The selected profile, protocol version and algorithm identifiers are bound into the signed manifest so negotiation downgrade or profile substitution is detectable.

Algorithm names must be registered identifiers, not free-form strings. Exact digest, signature, key size, canonicalization and deprecation values remain governance decisions; this proposal does not choose cryptographic algorithms.

### 6.2 Canonical content and transport layers

The protocol distinguishes:

- **Canonical content bytes:** deterministic serialization of the authorized clinical/resource projection before transport compression or encryption.
- **Content digest:** domain-separated digest over the exact canonical content bytes.
- **Transport envelope:** versioned metadata, encryption/wrapping and transport framing.
- **Envelope/ciphertext digest:** integrity digest over the exact transmitted envelope bytes.
- **Chunk digest:** digest over each exact chunk byte sequence.
- **Manifest signature:** signature over the canonical manifest bytes, binding all content and transport identifiers.
- **Receipt and commit evidence:** separate signed statements proving delivery/receipt and destination durable commit; neither is implied by a valid digest or signature.

Canonicalization MUST specify encoding, Unicode normalization, field ordering, number/date representation, null/omission rules, duplicate-key rejection, schema version, media type and deterministic serialization. The digest input MUST include a domain-separation label and profile identifier. Compression/encryption happen only after canonical content digest creation; the exact transport-envelope digest is computed over the bytes actually sent, including defined framing.

### 6.3 Signed manifest contract

The manifest schema MUST bind at minimum:

- schema/profile/protocol versions and algorithm identifiers;
- source and destination tenant/branch identities;
- source workload/issuer and actor authorization reference;
- source resource reference and authorized field projection/data categories;
- operation ID, request/intent ID and fencing generation;
- canonicalization profile and content byte length/digest;
- transport envelope profile, ciphertext/envelope byte length/digest;
- chunking profile, chunk count, ordered chunk descriptors and aggregate digest/root;
- signing key identifier, key status/freshness reference, signature and issuance/expiry;
- retry/replay identity and any response-artifact identifier.

The signature covers the canonical manifest representation and all fields that determine interpretation, routing, recipient, operation and integrity. The source and destination independently validate the manifest, source/destination binding, key status, expiry, operation/fencing state and digest values. A digest proves byte equality under its algorithm; it does not by itself prove sender identity, authorization, receipt or durable commit.

### 6.4 Chunking and reassembly

If chunking is enabled, every chunk has a zero-based index, declared count, exact byte length, per-chunk digest and manifest binding. The manifest declares aggregate content length and aggregate digest/root. Reassembly MUST reject missing, duplicate, reordered, overlapping, extra, truncated, oversized or cross-manifest chunks. A partial artifact is never treated as a complete response. Retries may replay only the exact recipient-bound artifact and exact manifest under the approved retry strategy; a changed artifact requires a new authorization/operation.

Cross-language conformance vectors MUST cover canonical serialization, Unicode, numeric/date edge cases, null and omitted fields, content digest, envelope digest, compression/encryption boundaries, manifest signature, chunk order/reassembly, duplicate/missing chunks, altered projection, destination substitution, stale key, expired manifest and downgrade attempts.

**Closure evidence:** normative schema/profile registry, signed test vectors, cross-language implementations, chunk/reassembly conformance suite and explicit downgrade/replay rejection.

## 7. DBID-R18 — ACL exception manifest and deterministic verifier

### 7.1 Machine-readable manifest

The ACL policy MUST be a strict, versioned machine-readable document. The following YAML illustrates the required structure; it is a schema example, not an approved production manifest or grant:

```yaml
schema_version: "1"
policy_id: "tenant-postgres-acl-baseline"
policy_version: "REQUIRES_GOVERNANCE_APPROVAL"
provider_profile: "REQUIRES_APPROVED_PROFILE"
postgres_major_version: "REQUIRES_SUPPORTED_VERSION"
tenant_id: "immutable-tenant-id"
database_id: "immutable-database-id"
issued_at: "RFC3339 timestamp"
expires_at: "RFC3339 timestamp"
approvals:
  - approver_role: "database-security-owner"
    evidence_ref: "immutable-evidence-reference"
principals:
  - principal_id: "runtime-login-version-id"
    database_role_name: "exact-role-name"
    role_kind: "login"
    tenant_id: "immutable-tenant-id"
    credential_version: "immutable-version"
    allowed_memberships: []
objects:
  - object_kind: "table"
    catalog_identity:
      database: "exact-database"
      schema: "exact-schema"
      name: "exact-object"
      identity_arguments: null
    owner_role: "exact-nonlogin-owner"
    allowed_privileges:
      - "SELECT"
    grant_options: []
exceptions:
  - exception_id: "unique-id"
    principal_id: "exact-principal-id"
    object_selector:
      object_kind: "sequence"
      database: "exact-database"
      schema: "exact-schema"
      name: "exact-object"
    privileges: ["USAGE"]
    grantor: "exact-grantor"
    approvers: ["independent-approver-a", "independent-approver-b"]
    reason: "bounded operational necessity"
    evidence_ref: "immutable-evidence-reference"
    issued_at: "RFC3339 timestamp"
    expires_at: "RFC3339 timestamp"
    status: "approved"
verifier:
  verifier_id: "immutable-verifier-build"
  catalog_adapter_version: "version"
  normalization_version: "version"
```

The production schema MUST reject unknown fields, duplicate identities, invalid privilege/object combinations, missing owners, unbounded wildcard patterns, expired exceptions, self-approval and missing evidence. Object selectors use exact catalog identities or a formally specified finite expansion set. Glob, regex, prefix and implicit schema-wide wildcards are prohibited unless a separately approved grammar defines their bounded expansion and the verifier records the exact expanded object list.

Approvals require independent accountable roles; the principal requesting or implementing a grant cannot be its sole approver. Exceptions are time-bounded, least-privilege and scoped to exact tenant/database/principal/object/privilege. Expired or unresolved exceptions fail closed.

### 7.2 Deterministic catalog normalization

For each supported PostgreSQL major/provider profile, the verifier MUST use a versioned adapter to collect and normalize:

1. database CONNECT/TEMP privileges and database ownership;
2. schema USAGE/CREATE and schema ownership;
3. relation ACLs for tables, views, materialized views and foreign tables;
4. sequence privileges and ownership;
5. routine/function/procedure EXECUTE, ownership and SECURITY DEFINER properties;
6. types/domains and relevant type privileges;
7. extension ownership, installed extension objects and extension update/creator identities;
8. PUBLIC privileges and default privileges;
9. role attributes, LOGIN state, superuser, createdb/createrole, replication, bypass-RLS, inheritance and SET ROLE capability;
10. direct and transitive memberships, grant options, ownership and effective privileges;
11. default-privilege rules for every object-creating role and object class;
12. FDW, foreign server, user mapping, dblink and other cross-database/network-capable features;
13. privileged functions, event triggers and provider-managed objects that can alter or bypass the intended boundary.

The normalization algorithm MUST resolve effective privileges, not merely compare explicit ACL strings. It must model PUBLIC, ownership, grant options, inherited memberships, SET ROLE, role attributes and default privileges. It must account for objects created by migrations, extensions, runtime roles, maintenance jobs and provider automation.

The verifier compares the normalized observed state against the baseline plus exact active exceptions. It emits deterministic differences: missing grants, excess grants, unknown principals, unexpected memberships, unexpected owners, unapproved object creators, expired exceptions, unmodeled objects, unsupported catalog versions and unobservable privilege paths. Unknown catalog object classes or missing catalog evidence are UNKNOWN/FAIL, never silently ignored.

### 7.3 Signed evidence and independent verification

The signed conformance result MUST bind policy ID/version/digest, tenant/database IDs, provider and PostgreSQL major version, catalog snapshot/time, migration ID, object-creator inventory, verifier binary/build digest, adapter/normalization version, exception expansion, findings and final result. The verifier identity and evidence chain must be independently authenticated.

Provider-managed privileges that cannot be inspected must fail closed unless an approved evidence adapter supplies independently verifiable evidence with explicit coverage and limitations. The adapter cannot convert “not observable” into “no privilege.” Unsupported provider profiles remain unsupported.

The verifier MUST have deterministic fixtures and mutation tests for every object/privilege class, PUBLIC access, ownership, grant options, transitive membership, SET ROLE, default privileges, SECURITY DEFINER, extensions, FDW/dblink, unknown creator, new PostgreSQL object type, wildcard expansion, expired exception, altered manifest, stale verifier and missing provider evidence. A separate independent implementation or test oracle MUST validate high-risk effective-privilege calculations before the conformance result becomes a release gate.

**Closure evidence:** approved JSON/YAML schema, canonical object identity grammar, PostgreSQL-versioned normalization algorithm, signed verifier evidence, fixtures/mutation suite and independent oracle results.

## 8. Cross-finding closure matrix

| Finding | Proposed resolution | Required evidence before closure |
|---|---|---|
| DBID-R13 | Closed-world trust graph and authoritative reconciliation | Signed graph, provider adapters, drift and negative path tests |
| DBID-R14 | Typed selector contract, bounded predicate and anti-enumeration | Selector registry, budgets, projection tests, response/timing/resource tests |
| DBID-R15 | Monotonic epochs and resource-level fencing | Consistency contract, token profile, concurrency and stale-worker tests |
| DBID-R16 | Explicit topology and server identity/revocation | Supported topology matrix, server-side attribution and termination tests |
| DBID-R17 | Signed canonical wire and chunk profile | Normative schema, cross-language vectors and downgrade/replay tests |
| DBID-R18 | Machine-readable ACL policy and deterministic verifier | Approved schema, catalog adapter, signed evidence and independent oracle |

This proposal does not close DBID-R07–R12 by itself. DBID-06 through DBID-08 from PR #45 remain separate open findings. CAN-01 and CAN-02 remain open until their complete dependency chains are independently verified. AUD-004 remains a release blocker.

## 9. Governance and unresolved decisions

The following remain explicit governance decisions, not values this design author may silently select:

- supported cloud/provider and on-prem deployment profiles; PostgreSQL major versions; trust-graph freshness and approver roles;
- selector types, canonicalization, source-key custody/rotation, rate/resource budgets and acceptable residual side-channel risk;
- epoch authority topology, consistency/failover guarantees, token cryptographic profile, release linearization and acceptable in-flight race windows;
- supported pooler/proxy modes, session termination capabilities and exception handling;
- canonical serialization, digest/signature algorithms, key lifecycle, chunking profile and artifact retention;
- ACL baseline, object exception approval roles, provider evidence adapters, independent verifier ownership and audit retention/residency.

D-01 through D-14 remain formally pending unless separately approved by their designated product, clinical, security, privacy/legal and operational authorities. D-11 project direction YES continues to mean local cross-branch imports are in intended scope; it is not formal governance approval. No emergency federation or break-glass authority is implied.

## 10. Implementation and release gates

Before any runtime implementation is considered, require:

1. independent review of this proposal and all predecessor design dependencies;
2. formal decisions by named governance authorities for the relevant D-01–D-14 items;
3. approved provider/deployment support matrix and threat model;
4. independently verified trust graph, selector contract, epoch/fencing protocol, connection topology, wire profile and ACL verifier;
5. documented privacy/clinical risk acceptance for disclosure and post-commit quarantine semantics;
6. implementation plan with migrations, backward compatibility, feature flags disabled by default, rollback and operational ownership;
7. isolated test evidence for negative cross-tenant paths, revocation races, session termination, wire conformance and privilege drift;
8. explicit separate authorization for implementation, production access, partner onboarding, pilot, deployment and release.

A green documentation CI or a mergeable draft PR is not evidence that these gates are satisfied.

## 11. Explicit non-authorization

This proposal authorizes documentation and independent design review only. It does NOT authorize runtime code changes, SQL execution, database/role/ACL/network changes, credential or secret-manager operations, production access, patient-data access, partner onboarding, trust/key provisioning, federation activation, emergency access, pilot, deployment, release or merge.

PR #51 remains draft and unmerged. This proposal is intended to be a draft, unmerged follow-up. All prior release blockers and governance gates remain in force.
