# AUD-004 DBID-R07–DBID-R12 Resolution Proposal

**Status:** DESIGN PROPOSAL — DOCUMENTATION ONLY — NOT IMPLEMENTATION APPROVAL  
**Parent review:** PR #49, independent review of DBID-R01–DBID-R06  
**Parent head:** `54c7e677678d0a251137c0fd001affb73ef98450`  
**Purpose:** Resolve the six residual findings DBID-R07 through DBID-R12 without changing runtime behavior.

## 1. Executive position

This proposal makes the earlier DBID controls more operationally testable. It does not assert that any production environment currently satisfies them. The repository's inspected application model is database-per-tenant; this proposal retains that model and does not introduce schema-per-tenant assumptions.

The proposal establishes:
- a complete, enumerated provisioning trust graph and a strict distinction between control-plane authority and database-session authority;
- a selector contract that permits only bounded database-internal predicate evaluation while prohibiting pre-authorization materialization or disclosure of patient data;
- source-owned monotonic revocation generations and fencing around the disclosure decision;
- credential-version-specific server identity and pooler-aware session revocation;
- canonical payload bytes and separately identified transport-envelope evidence;
- a machine-readable ACL exception manifest reconciled against effective PostgreSQL privileges and every object creator.

All algorithms, provider capabilities, freshness bounds, retention values and exception approvals remain subject to the accountable governance decisions listed below.

## 2. DBID-R07 — Complete provisioning trust boundary

### 2.1 Principal inventory

A deployment profile MUST maintain a versioned principal inventory. Every principal is classified by immutable workload identity, owning team, execution location, credential class, permitted operation, tenant/database scope, network zones, approver, expiry and audit source.

At minimum, inventory these distinct classes:

| Principal class | Permitted responsibility | Explicit prohibition |
|---|---|---|
| Provisioning controller | Create tenant database and advance provisioning state through approved control-plane APIs | No general patient-data query; no runtime application identity |
| Database bootstrap identity | Apply initial ownership and ACL hardening through the isolated bootstrap path | No ordinary application traffic; no long-lived shared runtime use |
| Tenant source-service identity | Execute only source-owned, tenant-scoped authorization and disclosure operations | No cross-tenant database access |
| Tenant application identity | Tenant-local application operations under approved grants | No foreign tenant DB CONNECT or source-disclosure authority |
| Migration runner | Apply reviewed migrations under a bounded migration identity and window | No use by web workers, support or general CI jobs |
| Backup/restore agent | Approved backup/restore operations with separately scoped credentials | No interactive clinical querying or cross-tenant export |
| Monitoring/observability agent | Health and explicitly approved aggregate metrics | No patient payload or unrestricted table reads |
| DBA/platform administrator | Time-bound, dual-controlled platform maintenance | No implicit clinical authorization or silent readiness override |
| CI/CD runner | Build/test and invoke narrowly scoped deployment workflows | No direct tenant database credentials by default |
| Orchestrator/control-plane agent | Schedule workloads and manage declared infrastructure resources | Control-plane permission does not imply database client permission |
| Host/network/sidecar agent | Enforce host, network and service-mesh policy | No credential extraction, arbitrary proxying or tenant DB session |
| Secret broker/workload identity service | Authenticate workloads and release only bound secret versions | No patient-data query; no caller-selected tenant/secret override |
| Support/operator identity | Approved diagnostic actions with minimum access and recorded purpose | No direct patient query or bypass of source authorization |
| Emergency identity | Only separately governed, time-limited break-glass procedure | No standing access; no automatic readiness or federation enablement |

Unknown principal classes, identities without an owner, shared identities spanning incompatible trust zones, and expired grants MUST fail closed.

### 2.2 Network and management-plane inventory

The trust-boundary diagram and access matrix MUST include all paths, not only application subnets:
- IPv4 and IPv6 routes, DNS resolution and private DNS;
- peering, transit gateways, private endpoints, VPNs and inter-region links;
- database listeners, proxies, connection poolers and service-mesh ingress/egress;
- host networking, node agents, sidecars, orchestration APIs and privileged daemon access;
- cloud/provider management planes, control APIs and support channels;
- CI/CD, migration, backup/restore, monitoring and secret-broker networks;
- shared runners, shared hosts, bastions, jump boxes and administrative workstations.

The matrix MUST state source identity, source network, destination listener, authentication method, database role, tenant binding, allowed protocol/operation, owner and evidence. A network label alone is not authorization.

### 2.3 Pre-READY bootstrap boundary

Before a tenant database reaches READY, the only permitted database-session path is the dedicated bootstrap path from the approved provisioning zone using a bootstrap identity bound to the requested immutable tenant/database record.

The provisioning controller is a control-plane client, not a database client by implication. If it invokes bootstrap work, it MUST dispatch to the separately authenticated bootstrap workload. Caller-supplied database names, tenant IDs, secret references or role names MUST be checked against the authoritative provisioning record.

The provisioning boundary MUST be unreachable from runtime, source, destination/import, background, support, monitoring, ordinary CI/CD and peer-tenant workloads until ACL, role membership, ownership, schema/default privileges, secret binding and network policy are verified. A routing flag or application-level READY flag is not a substitute for network and database enforcement.

If a provider cannot enforce and evidence this boundary, the deployment profile MUST use a separately isolated cluster or remain unavailable. No operator may manually mark READY to bypass a failed check.

### 2.4 Exceptional administrative access

Any exceptional human or platform-admin path requires named accountable approvers, dual control, time-bounded authorization, just-in-time identity, explicit tenant/database scope, session recording or equivalent tamper-evident evidence, purpose, and post-access review. Emergency access does not waive source-side clinician authorization for patient disclosure and does not change tenant readiness.

### 2.5 Acceptance evidence

- Complete principal/network/database matrix and data-flow diagram reviewed by platform security.
- Negative connection tests from every prohibited principal class and each applicable network path, including IPv6 and proxy/pooler paths.
- Positive tests proving only the designated bootstrap identity can connect pre-READY.
- Management-plane and shared-host bypass assessment.
- Tests proving control-plane credentials cannot be used as database credentials.
- Provider capability evidence and independent review for each supported deployment profile.

## 3. DBID-R08 — Selector predicate versus application-visible data

### 3.1 Normative selector contract

Only explicitly approved selector classes may be accepted. The initial profile SHOULD use exact-match selectors only; fuzzy, prefix, wildcard, multi-candidate and bulk search remain disabled unless separately approved.

The source-owned database may evaluate the approved selector against a protected source field as a bounded predicate. This is a database-internal comparison, not permission to project the stored identifier or patient row into application memory.

Before candidate authorization:
- SQL may compare the supplied canonical selector with an approved source field inside the source database boundary.
- The result may expose only a source-local opaque candidate reference and the minimum non-PHI protocol metadata needed to continue authorization.
- The application MUST NOT select, materialize, serialize, log or return stored phone, ABHA, MRN, DOB, demographics, allergy or clinical values.
- ORM entities and relationship graphs MUST NOT be loaded; eager/lazy relationship loading and serializer traversal are prohibited.
- Match counts, candidate ordering, identifier fragments and existence-specific error details MUST NOT be disclosed to an unauthorized caller.

After source candidate authorization succeeds, a separately scoped query may read only the exact approved field projection bound to the authorization envelope.

### 3.2 Canonicalization and privacy

Selector canonicalization MUST be versioned per selector class and performed inside the source-owned boundary or another specifically approved trusted component. Invalid or ambiguous input is rejected without a broader fallback.

Any lookup commitment or index MUST be source-scoped, keyed, domain-separated by selector type and protocol purpose, and governed for key custody, rotation and compromise. Plain SHA-256 or another unkeyed deterministic hash of low-entropy identifiers MUST NOT be used as a privacy-preserving commitment. No global deterministic cross-tenant selector token is permitted.

Raw selector values MUST NOT appear in application logs, traces, metrics, exception messages, audit telemetry or destination responses. Search budgets, rate limits and anti-enumeration behavior must align with CAN-02 and the approved external response contract.

### 3.3 Acceptance tests

- SQL instrumentation proves protected identifiers appear only in predicate parameters and are absent from SELECT projections before candidate authorization.
- Query-plan and ORM tests detect entity loading, eager/lazy relationship access and serializer traversal.
- Logs, traces, metrics and errors are scanned for raw selector values and match-specific details.
- Tests cover exact match, no match, ambiguous match, denied actor, unavailable source, throttling and malformed selectors with indistinguishable unauthorized external outcomes.
- Key rotation and cross-tenant/domain-separation tests prove commitments cannot be correlated across tenants or selector purposes.

## 4. DBID-R09 — Revocation generations, fencing and disclosure linearization

### 4.1 Source-owned generations

The source authorization authority MUST maintain monotonic generations (epochs) for relevant revocation domains, at minimum:
- issuer and signing-key trust;
- clinician identity, registration/status and source affiliation;
- partner/destination authorization;
- purpose/action/data-category policy;
- source workload identity and tenant/database binding;
- database credential/session generation;
- audit and authorization-service health state where required by policy.

Each authorization decision receives a signed or otherwise integrity-protected generation set bound to the actor, source resource, destination, action, purpose, selector commitment, policy version, operation ID and expiry. Generations are source-owned; a destination or caller cannot choose or lower them.

### 4.2 Linearization point

Candidate authorization alone does not authorize disclosure. The source MUST atomically compare the authorization generation set with current source state and commit a durable disclosure-intent record that reserves the exact resource, projection, destination and operation.

That successful compare-and-commit is the disclosure authorization linearization point. The protected read and artifact creation MUST be fenced to the committed intent and its generation set. The source MUST NOT release payload bytes unless:
1. the intent is durable;
2. the operation and worker fencing generation are current;
3. all required revocation generations still match under the defined release check;
4. the exact authorized projection and digest evidence are available; and
5. required audit persistence has succeeded.

Where the database cannot atomically couple the generation comparison, disclosure-intent commit and protected read, the design MUST state the residual race, use a source-owned serialization/lease mechanism that prevents stale workers from proceeding, and obtain explicit risk approval. A statement that a check happens “immediately before” use is insufficient.

### 4.3 Revocation behavior

A revocation advances the applicable generation monotonically. Every worker, retry, queue consumer and recovery process MUST compare its bound generations before protected read and before response release. A stale generation is rejected; it cannot be refreshed by the destination or by reusing an old assertion.

If revocation wins before the linearization point, no protected read or disclosure is permitted. If it occurs after the source has durably committed disclosure intent but before bytes are released, the source MUST apply the approved serialization rule: either revoke/fence the intent before release, or record the defined in-flight outcome and prevent any additional release. If bytes may already have left the source boundary, record OUTCOME_UNCERTAIN, stop further delivery/retry, preserve evidence and apply the approved quarantine/reconciliation procedure. No system may claim to retract bytes already received.

The maximum propagation/freshness window and any unavoidable in-flight disclosure risk require explicit approval by security, privacy/legal and clinical owners. Until approved, the conservative behavior is fail closed and do not release.

### 4.4 Acceptance tests

- Deterministic concurrency tests pause workers before and after each checkpoint while a revocation advances the epoch.
- Tests cover key, clinician, affiliation, destination, purpose policy, workload binding, DB credential and audit-service revocation.
- Stale workers cannot read, serialize, queue, send or acknowledge after a newer generation becomes effective.
- Lease expiry, duplicate worker, delayed queue, retry and process-resume tests prove fencing is monotonic.
- Tests distinguish revocation before intent, after intent but before read, after read but before send, during send and after possible receipt.
- All uncertain outcomes preserve audit evidence and cannot transition to successful completion without approved reconciliation.

## 5. DBID-R10 — Credential-version-specific PostgreSQL session identity

### 5.1 Rotation identity

The preferred baseline is a distinct PostgreSQL LOGIN role for each credential version, bound to one tenant workload and tenant database. The version-specific login inherits only the approved non-login runtime role(s); it MUST NOT own database objects or gain privileges beyond the approved role baseline. The old and new login roles must be independently revocable.

If a provider cannot support distinct login identities, an alternative is acceptable only when it provides equivalent authoritative server-side attribution of credential version and is independently reviewed. Caller-set `application_name`, connection tags or log fields are diagnostic only and MUST NOT be treated as proof of authenticated credential version.

### 5.2 Poolers and proxies

Each deployment profile MUST document whether it uses direct PostgreSQL sessions, session pooling, transaction pooling, statement pooling or a managed proxy. It must identify which component authenticates to PostgreSQL, which identity appears in server catalogs, whether client-to-server identity is preserved, and how tenant and credential version are authoritatively bound.

Where a pooler multiplexes client sessions onto a shared server login, the design MUST NOT claim PostgreSQL server-side credential-version attribution unless a verifiable mapping and revocation mechanism exists. Unsupported attribution/termination behavior requires a different deployment profile or quarantine.

### 5.3 Rotation completion

Credential rotation MUST:
1. create a new version-specific login with narrowly scoped, verified privilege parity;
2. bind the secret version to the immutable workload/tenant/database identity;
3. stop new checkout using the old version;
4. drain or cancel in-flight work under the approved policy;
5. invalidate checked-out and idle client connections;
6. dispose pools and prevent stale workers from recreating them;
7. revoke the old login/credential;
8. terminate old server-side sessions where required and supported;
9. verify from authoritative server-side evidence that no old-version session remains and no new authentication using the old version succeeds.

Engine disposal alone is not evidence that checked-out PostgreSQL sessions ended. If the platform cannot prove session attribution or termination, rotation is incomplete and the tenant/source service remains restricted.

### 5.4 Acceptance tests

- Establish simultaneous sessions under old and new credential versions and prove authoritative attribution.
- Revoke the old role while testing direct connections, poolers, proxies, idle pools, checked-out connections and stale workers.
- Prove old sessions cannot persist or reconnect after rotation completion.
- Prove the new login has no additional membership, ownership, SET ROLE or effective privilege.
- Fail closed when session state cannot be verified.

## 6. DBID-R11 — Canonical payload bytes and digest layers

### 6.1 Two distinct layers

The protocol MUST distinguish:
1. **Canonical content artifact:** deterministic serialized payload containing exactly the authorized field projection, before transport compression/encryption.
2. **Transport envelope:** the encrypted/compressed/framed/chunked representation used to deliver that artifact, including protocol metadata and cryptographic parameters.

The canonical content digest identifies clinical content independent of randomized encryption or transport framing. Where transport integrity is required, a separate envelope or ciphertext digest identifies the exact transmitted representation. The two digests MUST never be substituted for one another.

### 6.2 Canonical serialization contract

A versioned canonicalization profile MUST define:
- character encoding and Unicode normalization;
- deterministic field ordering and object representation;
- null versus omitted field semantics;
- numeric precision and formatting;
- date/time and timezone normalization;
- binary encoding;
- array ordering and duplicate handling;
- schema/version identifiers;
- treatment of unknown fields and extension data;
- compression boundary and whether compressed bytes are covered by the envelope digest;
- chunk ordering, chunk identifiers and reassembly validation.

The selected digest and signature algorithms remain D-07 governance decisions. No algorithm is silently selected by this proposal.

### 6.3 Evidence claims

The source computes the canonical content digest from the exact authorized projection. The destination recomputes it after decrypting/decompressing and canonicalizing under the same versioned profile. If transport integrity is enabled, the sender and receiver separately verify the envelope/ciphertext digest at the defined transport boundary.

A signed source manifest binds the content digest, optional envelope digest, canonicalization profile, projection, source resource reference, destination, actor authorization reference, policy version, operation ID, protocol version and fencing generation.

The destination acknowledgement MUST state separately whether:
- the content digest was verified;
- sender authenticity was verified;
- the exact artifact was durably committed;
- the operation/provenance marker was re-read and verified;
- the acknowledgement itself was signed and bound to the same operation, content digest, projection and fencing generation.

A digest proves byte/content equality only; it does not alone prove sender identity, delivery, receipt or durable destination commit.

### 6.4 Acceptance tests

- Publish canonical byte-level test vectors, including Unicode, null/omitted fields, numeric/date values and extension fields.
- Verify identical content produces identical canonical digest across supported implementations.
- Verify encryption randomness changes envelope bytes without changing canonical content digest.
- Reject payload, projection, manifest, chunk, compression or envelope substitution.
- Test retries, re-encoding, protocol-version negotiation and signed acknowledgement binding.
- Ensure the ack cannot assert durable commit before destination transaction and provenance re-read succeed.

## 7. DBID-R12 — Machine-readable ACL exceptions and creator inventory

### 7.1 Versioned exception manifest

Every supported PostgreSQL major version and deployment profile MUST have a machine-readable, version-controlled ACL exception manifest. Each exception record MUST identify:
- tenant/database and deployment profile;
- schema and exact object or approved object pattern;
- principal and privilege;
- grantor/owner where relevant;
- reason and business/technical necessity;
- accountable approver(s);
- compensating control and evidence;
- creation date, review date and expiry;
- linked migration/extension/provider capability;
- status (proposed, approved, expired, revoked).

Wildcard or unbounded exceptions are prohibited. An exception must not grant cross-tenant CONNECT, broad ownership, unrestricted role inheritance or a bypass of source-owned authorization. Expired, malformed, duplicate, unapproved or unmatched exceptions fail closed.

### 7.2 Complete object-creator inventory

The provisioning and migration manifest MUST enumerate every identity that can create or own database objects, including:
- schema/object owner roles;
- application migration roles;
- extension installation/upgrader roles;
- provider-managed extension identities where observable;
- restore/recovery identities;
- migration helper and CI/CD identities;
- controlled SECURITY DEFINER function owners.

Unknown creator identities or an object created outside the approved ownership model block conformance.

### 7.3 Catalog verifier

A versioned verifier MUST compare the live database state with both the normative baseline and exception manifest. It must evaluate direct ACLs and effective privileges, including:
- database CONNECT/TEMP privileges and PUBLIC grants;
- schema USAGE/CREATE;
- table, view, sequence, routine, type/domain and other supported object privileges;
- default privileges for every approved object-creating role;
- role attributes, memberships, transitive inheritance and SET ROLE paths;
- object/database/schema ownership and grant options;
- SECURITY DEFINER functions, search_path safety, extension ownership and privileged helpers;
- migration-created objects and newly introduced creator roles.

The verifier MUST fail on unknown objects/creators, unmodeled privilege types, stale manifests, expired exceptions, unexpected ownership, missing default privileges or any effective privilege exceeding the approved baseline. A textual review or a check of explicit ACL rows alone is insufficient.

### 7.4 Migration and READY gate

Every migration and extension change MUST run the verifier after object creation. The output must be machine-readable, tied to database identity, schema/version, manifest version and migration identifier, and retained as tamper-evident evidence. A failed or incomplete verifier blocks migration completion and READY. Restore workflows must re-run the same conformance checks before restored data is made available.

### 7.5 Acceptance tests

- Unknown object creator, unknown privilege, expired exception, wildcard exception and unapproved owner all fail.
- Tests cover inherited role grants, transitive membership, SET ROLE, grant options, SECURITY DEFINER and default privileges.
- Tests cover every object class and extension/migration creator.
- Baseline plus manifest produces deterministic expected effective privileges.
- A newly introduced migration role cannot silently bypass the verifier.

## 8. Cross-finding integration and closure matrix

| Finding | Required evidence before closure | Dependency |
|---|---|---|
| DBID-R07 | Complete trust graph, principal/network matrix, pre-READY isolation tests | Provider/deployment profile, platform security |
| DBID-R08 | Selector allowlist, predicate-only SQL tests, CAN-02-compatible privacy design | CAN-02, privacy/security |
| DBID-R09 | Monotonic source epochs, atomic fencing/linearization model, race tests and accepted residual risk | D-02, D-05, D-07, D-09, D-10, D-12 |
| DBID-R10 | Version-specific server identity, pooler-aware attribution and session termination evidence | Provider capabilities, secrets/workload identity |
| DBID-R11 | Canonical byte contract, test vectors, digest/signature choices and ack verification | D-07, D-10, D-12 |
| DBID-R12 | Versioned exception manifest, complete creator inventory and effective-privilege verifier | PostgreSQL major versions, migration/extension inventory |

These proposals do not close DBID-01 through DBID-06 automatically. They refine their acceptance criteria. DBID-06 through DBID-08 from PR #45 remain separate open findings and must be resolved. CAN-01, CAN-02 and AUD-004 remain open until independently reviewed and supported by implementation evidence.

## 9. Governance and unresolved decisions

The following require accountable owners; this document does not approve them:
- supported cloud/on-prem deployment profiles and provider-specific provisioning isolation;
- principal ownership and exceptional DBA/platform access policy;
- selector classes, canonicalization, key custody, anti-enumeration budgets and CAN-02 alignment;
- revocation authorities, epoch storage/consistency, freshness bounds and maximum in-flight disclosure risk;
- credential rotation model, pooler/proxy support matrix and session termination capability;
- canonical serialization profile, digest/signature algorithms and key custody under D-07;
- ACL exception approvers, expiry policy, PostgreSQL major versions and extension inventory;
- audit retention/residency, legal hold and access under D-12;
- quarantine and clinical workflow semantics.

Required review includes platform/database engineering, application security, privacy/legal, clinical safety, operations and independent security review. Formal D-01–D-14 decisions remain pending. D-11 project direction YES remains distinct from formal governance approval.

## 10. Explicit non-authorization and stop conditions

This proposal authorizes documentation and independent design review only. It does NOT authorize:
- runtime code changes, federation route refactoring or implementation;
- SQL execution, database/role creation, grants, revocations, ACL or schema changes;
- network, cluster, workload identity, secret-manager, credential or pooler operations;
- production catalog, infrastructure, audit-store or session inspection;
- patient-data access, query, import, export, migration or backup restoration;
- partner onboarding, trust/key provisioning, federation activation, emergency access or pilot;
- deployment, release, merge, or removal of the AUD-004 release blocker.

PR #49 and this proposal must remain draft/unmerged pending independent review. DBID-06 through DBID-08, CAN-01, CAN-02 and AUD-004 remain open. No release or runtime authorization is implied.
