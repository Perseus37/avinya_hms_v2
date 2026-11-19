# AUD-004 ADV-07/ADV-08 Source Access Boundary and Purpose/Scope Registry Proposal

**Status:** PROPOSED DESIGN — NOT APPROVED FOR IMPLEMENTATION  
**Parent:** PR #36 (ADV-05/ADV-06 revocation and resource artifact proposal)  
**Scope:** Resolve ADV-07 routing/source-boundary bypass risks and ADV-08 purpose/scope downgrade and confused-deputy risks.  
**Constraint:** This document is a design proposal. It does not establish runtime compliance, choose an unapproved topology, close findings, or authorize implementation.

## 1. Executive result and proposed direction

Two controls must be made enforceable rather than diagrammatic:

1. **One source-owned authorization boundary:** every remote, local cross-branch, synchronous, internal, background, administrative and retry path that resolves or reads another tenant's patient data must pass through the same logical source authorization contract. Direct ORM/session access from a caller or adapter is not an alternate route.
2. **One canonical purpose/action/scope vocabulary:** all participants use versioned, source-governed identifiers and a source-owned authorization matrix. Unknown, deprecated, ambiguous, wildcard, aliased or downgraded values are denied. Search, demographic disclosure, allergy disclosure and import are distinct actions with distinct scopes.

**Proposed topology for review:** use a source-owned authorization service/API as the only policy and data-access boundary. A routing coordinator may deliver opaque requests to source endpoints but must not decide patient authorization or expose candidate topology. For local cross-branch access, invoke the same source-owned authorization interface through an in-process adapter; the adapter must not bypass source policy or call patient repositories directly. Whether the global patient index is retained, and whether routing is fan-out or index-assisted, remains a separate governance/security decision. No topology option may weaken source-side authorization.

## 2. ADV-07 — Mandatory source access boundary

### 2.1 Security invariant

Before any patient-specific selector resolution, source record read, candidate existence signal, resource handle, summary, payload serialization or disclosure, the source tenant must:
- authenticate the registered caller relationship where applicable;
- verify the actor assertion and source-controlled clinician identity/affiliation;
- authorize the exact canonical action, purpose, destination, resource/search scope and data categories;
- check current source patient policy and relevant revocation status;
- durably record the required authorization/audit event;
- execute the query/read only through the source-owned boundary.

This invariant applies to:
- remote cross-hospital federation;
- local cross-branch/cross-tenant imports (D-11 project direction YES; formal governance pending);
- discovery search and candidate resolution;
- demographic, allergy and other clinical disclosures;
- import source re-read;
- HTTP routes, root and V1 aliases, internal service calls, scheduled tasks, queue consumers, retries, admin tools, support tooling and recovery workers.

Same-branch ordinary CRUD remains governed by ordinary tenant-local authentication/authorization and is outside this cross-tenant source-boundary contract. A same-branch workflow must not be used to disguise a cross-branch source read.

### 2.2 Logical source authorization interface

Define one narrow, source-owned interface (names illustrative; final API contract pending) with operations such as:
- `authorize_discovery_search(actor_context, destination, purpose, selector_kind, bounded_scope)`;
- `resolve_authorized_candidates(search_decision, canonical_selector)`;
- `authorize_candidate(actor_context, candidate_ref, action, purpose, destination, requested_data_categories)`;
- `commit_disclosure_intent(authorization_decision, resource_ref, payload_scope)`;
- `read_authorized_resource(disclosure_decision, resource_ref)`;
- `authorize_import(actor_context, source_resource_ref, destination, purpose, import_scope)`;
- `record_delivery_or_uncertain_outcome(operation_ref, delivery_evidence)`.

The interface must:
- derive tenant/branch identity from trusted server context, not caller-supplied schema or branch strings;
- accept opaque server-owned resource references, not raw table names, ORM models, SQL fragments or arbitrary source patient IDs from callers;
- derive actor subject/class from verified assertion and source mapping, not request body fields;
- canonicalize action/purpose/scope with the source's registry;
- evaluate source policy and revocation freshness at each required boundary;
- commit durable audit/decision evidence before protected query/read/disclosure;
- return only the minimum authorized result;
- produce typed, stable denial/uncertain outcomes without leaking patient existence or topology;
- be idempotent only where the exact operation contract permits, with durable replay/fencing state;
- be the only application-level entry point to protected cross-tenant patient repositories.

Do not create a generic `read_patient(tenant, patient_id)` interface that accepts arbitrary caller-controlled tenant and patient identifiers. Avoid a broad service facade that simply forwards unvalidated parameters.

### 2.3 Remote and local adapters

**Remote adapter**
- Authenticates node/partner transport identity.
- Carries a signed, audience-bound actor assertion and canonical operation request to the source endpoint.
- Does not resolve patient records, apply source privacy policy, or decide which candidate is authorized.
- Does not return branch/candidate metadata before source search authorization and candidate authorization.
- Treats coordinator/index results as routing hints only; source independently validates every source resource reference and authorization.

**Local cross-branch adapter**
- Runs inside the trusted application boundary but must call the same logical source authorization interface with an explicit source-branch context derived from the tenant registry.
- Establishes a source-verifiable actor context from the authenticated local clinician session; local origin is not an exemption.
- Must perform source policy, identity/affiliation, purpose/scope, audit, replay and revocation checks equivalent to remote access.
- Must not open the source tenant's SQLAlchemy session, query source patient/allergy models, or invoke source repositories directly before/around the authorization service.
- Must not treat same corporate ownership, shared deployment, superuser role or destination `patients:write` permission as source authorization.

**Background/recovery adapter**
- Receives a durable operation reference, not a serialized privilege or stale actor claim.
- Re-establishes the authorized actor/operation context and checks whether the workflow permits continuation.
- A retry that requires a new source read must obtain fresh source authorization; expired artifacts cannot authorize a new read.
- A worker cannot inherit authority from queue membership, service account identity or operator invocation alone.
- Uses monotonic fencing generations and conditional transitions; stale workers cannot read, commit, publish or acknowledge.

### 2.4 Routing topology and metadata visibility

The design must choose and threat-model one topology before implementation. Candidate patterns:

| Pattern | Description | Main risks / constraints |
|---|---|---|
| Source-directed fan-out | Coordinator sends opaque request to eligible source endpoints; each source independently authorizes before resolving selectors | Coordinator may learn partner topology; fan-out can amplify load; source count/timing must not leak to destination |
| Protected index-assisted routing | Restricted index returns opaque route tokens to coordinator; source independently authorizes and resolves the selector | Index compromise/correlation; key separation, token rotation, migration, access and audit are required |
| Direct source registry routing | Destination selects an explicitly known partner/source endpoint | May reveal partner topology and creates caller-supplied routing risks; source still authorizes independently |

**Proposed default:** prefer source-directed fan-out to a bounded, eligible partner set unless measured scale/latency justifies a protected index. Do not expose branch candidates or index matches to the destination. If an index is required, it is a routing optimization only; it cannot answer patient existence or authorize access. Index design remains coupled to ADV-09 and needs a separate decision on keyed tokenization, key separation, rotation, retention, backfill, collision handling and rollback.

Regardless of topology:
- route only to registered, active, policy-eligible sources;
- bound fan-out and enforce distributed budgets before source work;
- avoid destination-visible per-source status/count/latency details that reveal patient matches or topology;
- normalize externally observable outcomes within the approved anti-enumeration policy;
- keep routing telemetry free of raw selectors and unnecessary PHI;
- source independently validates destination, action, purpose, actor and resource;
- routing failure cannot cause a direct database fallback or weaker authorization path.

### 2.5 Enforcing the boundary in the repository and database

A code convention or sequence diagram alone is insufficient. Proposed defense in depth:

1. **Repository inventory:** identify every code path that opens tenant sessions or reads patient, allergy, pointer, federation, import or transfer data. Include route aliases, dependencies, services, tasks, scripts, tests, admin/support utilities and migrations.
2. **Narrow repositories:** protected patient reads for cross-branch/federation are reachable only from the source authorization service module. Keep raw tenant session factories and ORM repositories out of adapters.
3. **Dependency direction:** adapters depend on the authorization interface; the authorization service depends on source repositories. Source repositories must not import remote/local adapters, routers or caller request models.
4. **Database identity:** where operationally feasible, use distinct database roles/connection paths so coordinator/worker roles cannot directly read arbitrary tenant patient tables. Source authorization service holds the minimum necessary access. Do not claim this control if all components share unrestricted database credentials.
5. **Trusted context:** derive source tenant/branch from a trusted registry and server-side execution context; reject request-provided schema names, connection strings, tenant overrides and branch codes as authority.
6. **Architecture tests:** statically fail if non-allowlisted modules import protected patient models/session factories or call protected repository methods. Maintain a small explicit allowlist for source authorization implementation, migration code and narrowly scoped tests.
7. **Runtime tests:** instrument source repository calls and prove every cross-tenant read has a preceding source authorization/audit event with matching operation, actor, purpose, destination and resource scope.
8. **Route parity:** test root and V1 aliases for equivalent authentication, authorization, audit, replay and error behavior. Alias routing must not bypass middleware or dependencies.
9. **Operational paths:** protect Celery/queue/scheduler workers, admin/support scripts, data repair, retries, exports and one-off tools. Require auditable, least-privilege break-glass separately governed; no implicit superuser bypass.
10. **Continuous inventory:** CI detects new routes, task entry points, tenant session creation and protected model imports; new access paths require security review.

If architectural separation cannot be enforced due shared credentials or broad imports, document the residual risk and add compensating controls; do not describe the boundary as mandatory until tested.

### 2.6 Required route and access-path inventory

Maintain a generated or reviewed inventory with:
- route/method and all mounted aliases;
- caller class and authentication mechanism;
- actor assertion requirement;
- source authorization operation;
- purpose/action/scope registry version;
- source data categories read;
- source audit event;
- destination and source tenant context;
- synchronous/background/internal/admin entry path;
- retry/recovery behavior;
- test IDs and owning module.

At minimum inventory federation clients/trust administration, pointer publication, discovery, import, patient registration/update/deactivation, allergy chart/deactivation, transfer-log handling, index sync, federation workers and operator recovery. Existing route inventory in PR #21 is a starting point, not proof that every current/future path is covered. Root and V1 route aliases must be tested for exact security parity.

## 3. ADV-08 — Canonical purpose, action and scope registry

### 3.1 Registry design

Create a versioned, source-governed registry with separate namespaces for:
- **Action:** what operation is being requested (for example, discovery search, demographic disclosure, allergy disclosure, clinical document disclosure, import, pointer publication).
- **Purpose:** why the clinician needs the information (controlled clinical/business reason).
- **Resource type:** which source resource family is involved.
- **Data category:** the exact categories that may be disclosed (demographics, allergy summary, medication, encounter, lab result, document, etc.).
- **Scope:** bounded resource subset, time window, encounter or other approved restriction.
- **Destination class:** which registered recipient class/tenant/branch may receive it.
- **Actor class/credential requirements:** which source-approved clinician class and credential/affiliation evidence may request it.

Purpose and action are not interchangeable. A purpose never grants an action by itself. A broad action never implies all data categories. A data category never grants access without source authorization. Destination RBAC is an additional check, not a substitute for the source matrix.

Each registry entry should include:
- immutable canonical identifier and namespace;
- semantic definition and explicit permitted use;
- registry/schema version and effective dates;
- owner and approving governance role;
- allowed action/purpose combinations;
- allowed actor classes/credential conditions;
- allowed destination classes;
- permitted resource/data categories and maximum scope;
- whether search, candidate disclosure, import or replay is permitted;
- deprecation/sunset and migration rules;
- audit classification and retention references.

Do not silently change the meaning of an existing identifier. Semantic changes require a new version/identifier and explicit migration compatibility policy.

### 3.2 Example proposed action identifiers

Illustrative names only; they are not approved registry values:

| Action | Intended boundary | Must not imply |
|---|---|---|
| `DISCOVERY_SEARCH` | Bounded source-authorized exact selector search | Candidate disclosure or import |
| `DISCOVERY_CANDIDATE_SUMMARY` | Candidate-specific minimal demographic summary | Allergy, medication or full chart |
| `ALLERGY_SUMMARY_DISCLOSURE` | Explicit allergy-summary release after candidate authorization | Full medication/chart access |
| `CLINICAL_DOCUMENT_DISCLOSURE` | One approved document/category/scope | All records or future documents |
| `PATIENT_IMPORT` | Source-authorized re-read and transfer for one destination/operation | General source browsing or later refresh |
| `POINTER_PUBLICATION` | Publish minimum locator metadata under its own policy | Patient record disclosure or authorization |

The registry must distinguish selector search from candidate summary, and each clinical data category from the others. Discovery authorization must not return allergy details merely because allergy summary is available in the source system. Import must always be separately authorized even when discovery previously succeeded.

### 3.3 Canonicalization and strict validation

- Accept only exact canonical identifiers for the negotiated registry version.
- Reject unknown, empty, null, deprecated, misspelled, case-variant or ambiguous identifiers unless a specifically approved normalization rule exists.
- Do not silently map legacy aliases, free-text labels, numeric role values or client-local enums to privileged canonical values.
- Reject wildcard, `*`, `all`, omitted scope, implicit default scope and unbounded time ranges for protected actions.
- Normalize encoding and serialization before signature/hash/authorization evaluation using an approved canonical representation.
- Reject duplicate JSON keys, conflicting fields, multiple aliases for one semantic field and non-canonical encodings.
- Never let destination or caller choose the registry version to obtain broader legacy permissions. The source selects/negotiates an approved version and records it.
- Unknown newer/older versions fail closed with a safe protocol-version error; no automatic downgrade.
- Deprecated values are denied after their approved sunset; migration must be explicit and audited.
- A request with extra unrecognized fields is rejected or ignored only under a documented strict schema policy; it must never widen scope.
- Scope is intersected with source policy and the narrowest applicable permission. No union or widening from multiple claims.

### 3.4 Source-owned authorization matrix

The source evaluates a governed matrix across at least:

`issuer × clinician_subject × actor_class × credential_status × affiliation × destination × action × purpose × resource_type × data_category × scope × patient_policy`

A request is allowed only when every required dimension is valid and the exact combination is permitted. A missing dimension is deny-by-default. The source must not accept destination-supplied roles or clinician classes as authoritative; it resolves them from source-controlled mapping and evidence.

The matrix should support explicit deny rules and precedence. Deny overrides allow where policies conflict. Broad group membership, same corporate ownership, shared hosting or a destination administrator assertion cannot grant source access. Policy evaluation records the matrix/registry version and stable decision reference.

### 3.5 Purpose and scope downgrade/confused-deputy defenses

- Bind the exact canonical action, purpose, destination, resource, data categories, scope, protocol version and operation into the signed assertion/authorization decision/manifest as applicable.
- Source re-computes the authorization tuple; it does not trust a destination-provided "authorized" boolean.
- A routing service, import worker or admin endpoint cannot substitute a broader purpose or action than the original verified actor request.
- Purpose cannot be changed between search, candidate authorization, disclosure, artifact retrieval or import. A different purpose requires a new source authorization.
- Search scope cannot be upgraded to candidate disclosure; candidate summary cannot be upgraded to allergy or full chart; discovery cannot be upgraded to import.
- Data-category lists are exact sets with deterministic ordering/canonicalization. Unknown categories or extra categories cause denial, not partial widening.
- Scope narrowing may be allowed only if the source explicitly defines safe subset semantics; widening always requires a new authorization.
- Protocol downgrade, registry downgrade and algorithm downgrade are distinct and all rejected unless an explicit, time-bounded compatibility profile is approved by governance.
- Retries preserve the exact operation tuple and registry version. A retry with changed purpose/action/scope/destination is a conflict and requires a new operation/authorization.
- Destination import validation compares the manifest and provenance tuple against the fresh import authorization; a valid signature cannot authorize a wider payload.
- Audit events record requested and effective canonical tuples (with sensitive identifiers protected), policy version and denial reason category.

### 3.6 Compatibility and version negotiation

Protocol and registry negotiation must be source-controlled:
1. Destination advertises only supported protocol/registry versions from an approved allowlist.
2. Source chooses an intersection from its approved policy; destination cannot force a lower version.
3. The chosen version is bound into challenge, actor assertion, authorization decision, handle/manifest, operation and acknowledgement.
4. Any mismatch across artifacts is rejected.
5. Removed/deprecated versions are disabled by source policy; old clients must upgrade rather than silently fall back.
6. Emergency compatibility requires explicit governance approval, a narrow partner/action/data scope, expiry, monitoring and rollback plan. No automatic compatibility fallback.

## 4. Combined access and downgrade threat matrix

| Attack / failure | Required control | Expected result |
|---|---|---|
| Local branch adapter opens another tenant's ORM session directly | Narrow source authorization service, dependency rules and DB-role separation | Architecture/permission test fails; no patient read |
| New background job queries source patient table | CI import/session boundary checks and runtime audit correlation | Blocked until reviewed and routed through boundary |
| Root route has weaker checks than V1 alias | Route inventory and alias parity tests | Security test fails |
| Coordinator/index returns candidate branch or match count | Opaque routing and source-only candidate resolution | No candidate metadata to destination |
| Caller supplies tenant schema/patient ID to generic reader | Trusted server context and opaque source resource refs | Reject before DB access |
| Caller changes purpose from treatment to another value | Exact canonical registry + source policy | Deny/conflict; no scope widening |
| Caller adds allergy category to demographic summary | Exact data-category binding | Deny; no partial broadening |
| Old client negotiates weaker protocol/registry | Source-controlled version selection and no downgrade | Reject |
| Worker reuses search authorization for import | Separate action and fresh import authorization | Reject before source re-read |
| Admin/superuser uses direct source DB path | Least-privilege DB roles and audited privileged workflow | Deny unless separately governed |
| Retry changes destination/action/purpose/scope | Immutable operation tuple and durable idempotency | Conflict; fresh authorization required |
| Multiple allow rules combine to widen scope | Explicit matrix semantics and deny precedence | Narrowest approved scope only |

## 5. Audit, observability and evidence

Record source-generated, versioned events for:
- source boundary entry and caller/adapter identity;
- actor assertion and source mapping verification result;
- registry/protocol version selected;
- canonical action/purpose/scope and destination class;
- search authorization, candidate authorization and disclosure intent;
- source repository operation reference and resource scope;
- policy/matrix version and status versions evaluated;
- routing request/correlation reference without exposing candidate topology;
- outcome, stable denial category, replay/fencing generation and operation state.

Keep restricted patient-linked audit separate from operational telemetry. Do not emit raw selectors, patient IDs, PHI, assertions, handles, private keys, source SQL/schema details or candidate branch lists to ordinary logs. Audit retention/access/integrity remains governed by D-12 and the PR #35/PR #36 audit proposals. Audit failure at a mandatory authorization boundary prevents the protected query/read/disclosure.

## 6. Required acceptance tests

### 6.1 Source boundary coverage
- Enumerate all source patient/allergy/document repositories and every call site.
- Static architecture test rejects protected model/session imports from routers, adapters, coordinators, tasks, admin/support tools and unrelated services.
- Only approved source authorization modules can access protected repositories; allowlist is explicit and reviewed.
- Runtime instrumentation proves every cross-tenant source read has a matching preceding source authorization and durable audit event.
- Attempt direct ORM/session access through remote, local, background, retry, admin and test helper paths; no bypass succeeds.
- Local cross-branch and remote federation produce equivalent source policy/actor/audit decisions.
- Root and V1 route aliases have identical authentication, assertion, authorization, replay and denial behavior.
- Missing/forged source context, caller-supplied schema, branch, patient ID, role or authorization boolean is rejected before patient repository access.
- Background worker with only service-account identity cannot read patient data without a valid operation/actor authorization context.
- Stale worker/fencing generation cannot bypass source boundary or continue after revocation.
- New route/task/repository import added in CI without security inventory update fails review/test.

### 6.2 Routing topology and privacy
- Destination cannot observe candidate branch, match count, patient existence, source-specific status or per-source failure details before source authorization.
- Fan-out limits aggregate across nodes and aliases; coordinator outage cannot trigger direct DB fallback.
- Index, if selected, returns only opaque routing hints to trusted coordinator and cannot authorize or disclose matches.
- Cross-tenant selector correlation controls are tested with separated key/context and rotation if index retained (ADV-09 dependency).
- Routing and operational logs contain no raw selectors or unnecessary PHI.
- Source independently rejects a valid route hint with wrong destination, actor, purpose, action or resource.
- Timing/body/size/status normalization is tested within the approved anti-enumeration policy.

### 6.3 Purpose/scope registry
- Unknown, null, empty, deprecated, case-variant, alias, wildcard and omitted purpose/action/scope are denied.
- Purpose/action mismatch, wrong actor class, expired credential, wrong destination class and patient-policy denial are rejected.
- Search permission cannot disclose candidate summary; summary cannot disclose allergy/medication/document; discovery cannot authorize import.
- Extra or reordered data categories cannot widen scope; canonical set comparison is deterministic.
- Purpose/action/scope/registry version changed during retry causes conflict and requires fresh authorization.
- Protocol or registry downgrade, unsupported version, duplicate JSON keys, ambiguous encoding and extra privilege-bearing fields are rejected.
- Valid signature with altered purpose, destination, data categories, scope, operation or registry version is rejected.
- Source policy deny overrides destination allow and conflicting matrix rules.
- Audit contains effective canonical tuple and policy version without leaking PHI.

### 6.4 Database and fault injection
Use PostgreSQL integration tests with independent sessions/processes. Inject failure at source authorization, audit commit, repository read, routing, worker lease/fencing, revocation check and destination handoff. Prove no patient read occurs before required authorization and no failure falls back to a weaker path. SQLite-only/unit-only evidence is insufficient for concurrency, locking and durable audit ordering.

## 7. Governance decisions required

| Decision | Proposed direction | Accountable approval | Status |
|---|---|---|---|
| Source access boundary architecture | One source-owned authorization interface for all remote/local/internal/background paths | Security architecture + platform + clinical governance | Pending |
| Repository and DB-role enforcement | Narrow repository access, CI architecture tests and least-privilege database identities where feasible | Security + platform/SRE + data owner | Pending |
| Routing topology | Prefer bounded source-directed fan-out unless measured need justifies protected index | Security architecture + privacy/legal + platform | Pending |
| Candidate/selector visibility | No destination-visible candidate branch, count or match details before authorization | Privacy/legal + security | Pending |
| Local adapter equivalence | Same source policy and audit boundary as remote federation | Clinical governance + security | Pending |
| Admin/support/recovery access | Separate least-privilege and dual-control workflow; no implicit superuser bypass | Security + clinical governance + operations | Pending |
| Canonical registry ownership | Source-governed, versioned registry with named owner and approval authority | Clinical governance + privacy/legal + security | Pending |
| Purpose/action vocabulary | Exact canonical identifiers; unknown/deprecated values denied | Clinical governance + product + security | Pending |
| Actor/data-category matrix | Explicit clinician-class × purpose × action × resource × category × destination matrix | Clinical governance + privacy/legal | Pending |
| Scope semantics | No wildcard/default; explicit subset rules and deny precedence | Clinical governance + security | Pending |
| Protocol/registry compatibility | Source-selected version; no automatic downgrade | Security architecture + partner governance | Pending |
| Audit content/retention | Reconcile with D-12 and prior proposals | Audit owner + privacy/legal + security | Pending |

Record each approval in the canonical D-01–D-14 register with approver name, organization, role, date, governance reference, evidence, affected stages, residual risk, compensating controls, expiry and disable conditions. D-11 project direction remains YES for local cross-branch imports, while formal governance approval remains pending.

## 8. Implementation gates

Do not begin runtime implementation for ADV-07/ADV-08 until:
1. The source-owned interface and trust-context contract are reviewed and approved.
2. Remote, local, root/V1, internal, background, admin, support, retry and recovery paths are inventoried.
3. Routing topology and candidate metadata visibility are threat-modelled; ADV-09 index decision is reconciled.
4. Repository dependency rules and practical database-role separation are demonstrated in a prototype/test environment.
5. Canonical purpose/action/resource/data-category/scope registry and source-owned authorization matrix are approved.
6. Protocol/registry negotiation and no-downgrade behavior are reconciled with assertions, handles, manifests and acknowledgements.
7. PostgreSQL integration, architecture, route parity, anti-enumeration and fault-injection tests are accepted.
8. Formal governance decisions and explicit implementation authorization are recorded.

## 9. Relationship to prior proposals

- PR #21 inventories the federation route surface and identifies root/V1 aliases and local import bypass concerns; its inventory must be expanded to all access paths.
- PR #32 requires the same source authorization boundary for remote, local, synchronous and background access.
- PR #33 identifies ADV-07 and ADV-08 as high-risk unresolved findings.
- PR #34 defines source-controlled clinician identity and two-stage discovery authorization.
- PR #35 separates challenge/search/candidate/disclosure and destination delivery boundaries.
- PR #36 defines revocation freshness and resource artifact binding; those checks apply at this source boundary.
- PRs #23/#24 require import provenance, fencing and no unauthorized source re-read during recovery.
- PR #19 runtime behavior does not currently prove these architecture guarantees. Design documentation is not evidence of enforcement.

## 10. Disposition

This document proposes controls for ADV-07 and ADV-08; it does not close either finding. Closure requires selected and threat-modelled routing topology, complete access-path inventory, independently reviewed source-boundary enforcement, approved canonical purpose/scope governance, PostgreSQL and architecture-test evidence, and verified runtime enforcement across remote federation and local cross-branch paths.

**AUD-004 remains release-blocking.** This document authorizes no runtime code, migrations, configuration, database-role changes, cryptographic/key changes, trust entries, partner onboarding, pilot, production patient-data access, merge, deployment, release or emergency federation.
