# AUD-004 CAN-01 Enforceable Source-Owned Boundary Proposal

**Status:** PROPOSED DESIGN — NOT APPROVED FOR IMPLEMENTATION  
**Parent:** PR #41, independent review of the AUD-004 canonical baseline  
**Finding:** CAN-01 — local cross-branch source authorization is specified logically but is not yet a technically enforced boundary.  
**Scope:** Local cross-branch/cross-tenant patient discovery, source reads, import, retries and recovery. The same source-owned boundary also applies to remote federation.  
**Release status:** AUD-004 remains a release blocker. This proposal changes no runtime code, database grants, migrations, credentials, keys, trust entries, partner configuration or production behavior.

## 1. Executive decision proposal

A shared Python interface, repository convention, router dependency or code-review rule is not a security boundary if the destination process can still open a source tenant session or execute SQL against source patient tables.

**Recommended target:** a separately enforced source-owned authorization/data-access service boundary, backed by database identities and grants that prevent the destination application/import worker from reading source patient tables directly.

The local adapter must call the same source-owned protocol used by remote federation. It may use an internal transport, but it must not obtain source patient sessions, ORM objects, raw source patient identifiers or unrestricted source database credentials.

The enforcement is a combination of:

1. **Process/service separation:** source authorization and source patient reads execute in a source-owned service/process boundary.
2. **Credential separation:** destination web/API, import worker, background worker, admin and support identities have no direct SELECT privilege on foreign/source patient or allergy tables.
3. **Database least privilege:** source service database identities are restricted to the source tenant/schema and required tables or approved database operations. A single broad service credential spanning all tenant schemas is not acceptable as proof of branch isolation.
4. **Source-owned policy and audit:** source service verifies actor, destination, purpose, action, resource/scope, current source policy and revocation; it durably records the required authorization/disclosure event before protected lookup/read/disclosure.
5. **Complete path coverage:** HTTP aliases, internal calls, scheduled jobs, queue consumers, support/admin tools, retries and recovery use this boundary. No alternate direct repository path exists.

This proposal does not select final infrastructure, network topology, database role layout, service SLO, or governance values. Those require architecture, security, privacy and operations review.

## 2. Security invariants

These invariants apply to local cross-branch access under project direction D-11 (YES; formal governance approval remains pending), and to remote cross-hospital federation:

- The source branch owns the source patient record, source clinician mapping, source authorization decision, source privacy policy and source-side disclosure audit.
- The destination process cannot directly read source patient or allergy tables, even if a route, worker, retry handler or developer omits an application-level authorization call.
- A source tenant/schema is derived from trusted server-side routing and tenant registry state, never from a caller-supplied schema name, branch ID or SQL fragment.
- A verified clinician assertion and destination node/service identity are inputs to source authorization, not authorization by themselves.
- Durable source authorization for the exact search must precede patient-specific selector resolution.
- Candidate/resource authorization and durable disclosure intent must precede candidate existence signals, protected source reads, serialization or release.
- Import is a distinct source-authorized action. Discovery permission, receipt, handle, pointer, operation ID or destination permission does not authorize a new source read.
- A retry that performs a new source read requires fresh source authorization and a new source audit event. An already-created immutable response artifact may only be replayed under its separately approved recipient-bound artifact contract.
- Failure of source authorization, source audit, credential isolation, policy/status registry, replay store or source database authorization fails closed. There is no direct-query fallback.
- Ordinary same-branch CRUD remains on the tenant-local path. A request crossing a branch boundary cannot be relabelled as same-branch work to bypass this protocol.

## 3. Trust boundaries and service identities

### 3.1 Required logical identities

| Identity | Permitted responsibility | Must not be able to do |
|---|---|---|
| Destination API/web process | Authenticate local session; validate request shape; initiate source-bound operation | SELECT foreign patient/allergy rows; choose source schema; mint source authorization |
| Destination import worker | Coordinate operation state, destination clone/provenance, acknowledgement and pointer-sync workflow | Read source patient rows directly; reuse stale actor authority; bypass source authorization on retry |
| Destination admin/support process | Perform explicitly authorized operational tasks with dual-control where required | Assume administrative status grants clinical source access |
| Source authorization service | Verify source trust, actor mapping/status, action/purpose/destination/scope, policy, replay and audit | Trust caller-provided tenant/schema/actor/role or issue broader authority than requested |
| Source data-access service/repository | Execute only source-authorized, bounded patient/resource operations | Expose generic arbitrary-tenant patient lookup |
| Source database role | Read only the approved source tenant/schema and minimum required tables/operations | Read all tenant schemas or switch to another tenant based on caller input |
| Control-plane/router | Resolve trusted service/source routing metadata and bounded eligible-source set | Resolve patient existence, authorize patient access or disclose candidate topology |

A service may implement both source authorization and source data access only if it remains a separately enforced process/credential boundary and its internal APIs preserve the same checks. Merely splitting Python modules/classes is insufficient.

### 3.2 No caller-controlled authority

The source service must derive the source tenant and branch from a trusted source registry and authenticated service context. It must reject caller-controlled:

- schema/table names, database URLs, tenant session factories or raw SQL;
- arbitrary source patient IDs where an opaque source-owned resource reference is required;
- clinician user IDs, role labels, issuer identities or credential status;
- action, purpose or data scope values not in the source-governed versioned registry;
- destination branch values not bound to the authenticated destination relationship and signed actor assertion.

A caller may provide a requested destination and operation, but the source must validate them against trusted node/partner configuration and the challenge/assertion binding.

## 4. Enforcement architecture

### 4.1 Recommended deployment shape

The destination and source components may run on the same physical host or within the same private network, but they must remain distinct security principals:

```
Destination API / Import Worker / Admin / Queue Worker
                 |
                 | authenticated, bounded source operation
                 v
       Source-owned authorization endpoint
                 |
                 | verified source decision + audit evidence
                 v
       Source-owned patient data-access layer
                 |
                 | source-scoped DB identity only
                 v
       Source tenant schema / patient tables
```

For a local cross-branch request, the local adapter sends the same canonical request to the source endpoint as a remote adapter would. The transport can be private-network RPC/HTTP or another authenticated service transport. The exact transport is an ADR decision; the security property is that destination credentials cannot bypass it.

The source endpoint must verify the destination service identity and clinician assertion, source-controlled clinician mapping/status, exact action/purpose/destination/scope, source policy and replay state. It then commits required source audit evidence before the protected selector query or patient read.

### 4.2 PostgreSQL/schema-per-tenant isolation

The schema-per-tenant model needs database enforcement, not only SQLAlchemy routing conventions.

Required target properties:

- Destination application and worker roles have no direct SELECT privilege on foreign tenant patient, allergy, clinical-resource or source pointer-to-patient mapping tables.
- Source data-access credentials are source-tenant scoped. A credential used for source branch A cannot SELECT from source branch B's schema.
- No destination role has membership in a broad tenant-owner, migration, superuser or cross-schema read role at runtime.
- Migration/owner credentials are separate from application credentials, unavailable to web/worker containers and not used by request code.
- Search path is not treated as an isolation boundary. Explicit schema qualification, role grants and connection identity must enforce scope.
- Connection pooling must not permit role/schema context to leak between requests. Any approved role switching must be transaction-scoped, server-controlled, reset/verified on checkout/checkin, and independently tested.
- The source service cannot accept arbitrary schema identifiers or switch its DB identity based on an untrusted request field.
- Database grants are reviewed from effective privileges, including inherited role memberships, views, functions, triggers and SECURITY DEFINER functions.

**Important deployment caveat:** if the current runtime uses one shared database superuser or a broad role with access to all tenant schemas, a separate Python service process alone does not close CAN-01. The database credential and grant model must also change. Until effective privileges prove isolation, the boundary is not enforced.

### 4.3 Alternatives considered

| Option | Assessment | Disposition |
|---|---|---|
| Shared Python function/repository/dependency in destination process | Bypassable by direct session, ORM, SQL, background task or new route | Reject as sole boundary |
| In-process source adapter with the destination's broad DB credential | Same process and credential can bypass adapter | Reject as sole boundary |
| Separate source service/process with distinct source-scoped DB identities and grants | Enforces a process and database privilege boundary; supports local and remote parity | Recommended target |
| Database stored procedures/RLS with a restricted role | Can provide strong enforcement if the caller cannot bypass procedures, forge source context or assume broader roles; operational complexity and context propagation require proof | Viable alternative only with independent database security review |
| One central source service using a DB role that can read every tenant schema | Removes destination direct access but centralizes broad patient-data authority and increases blast radius | Not acceptable without a separately approved threat model and stronger per-source enforcement |

A database-only design may be selected instead of a separate service only if it demonstrates equivalent isolation: destination roles cannot read base tables, approved functions enforce source authorization and audit, caller-controlled session variables cannot forge trusted identity, and all alternate database paths are denied. RLS alone is not sufficient if application roles can bypass it, own tables, change policy context or assume privileged roles.

## 5. Operation contract

The source-owned interface is a narrow protocol, not a generic database facade. Names below are illustrative and require API-contract review.

| Operation | Required source-side work | Protected query permitted? |
|---|---|---|
| `begin_discovery` | Authenticate node/destination, validate syntax and abuse budget, create bounded challenge | No patient-specific selector query |
| `authorize_discovery_search` | Verify assertion, issuer/key, actor mapping/status, action/purpose/destination/scope, replay; durably record search grant | Only after durable allow |
| `resolve_authorized_candidates` | Validate grant and budget; resolve selector inside source boundary | Yes, bounded source-local query |
| `authorize_candidate` | Check exact source resource and current patient policy/data categories | No disclosure until allow |
| `commit_disclosure_intent` | Persist source audit/decision evidence for exact resource/scope | No protected serialization until durable success |
| `read_authorized_resource` | Revalidate decision freshness and read only approved minimum data | Yes, bounded read |
| `authorize_import` | Distinct import challenge/assertion, exact source pointer and destination, policy and replay checks | Only after durable allow |
| `read_import_source` | Source-controlled read of exact authorized resource | Yes, no arbitrary patient lookup |
| `record_delivery_outcome` | Record source-observed send/uncertain/acknowledged stage with evidence | No new source read |
| `resume_import` | Validate durable operation, fresh receipt/authorization if another source read is needed, fencing and revocation | Only under explicit recovery authorization |

The source endpoint returns minimum data and a source-authenticated result envelope. It does not return ORM objects, SQLAlchemy sessions, lazy relationships, database URLs, schema names or unrestricted internal model objects.

## 6. Fail-closed and uncertain behavior

| Failure | Required behavior |
|---|---|
| Source authorization service unavailable | Deny/defer protected operation; no destination-side direct query fallback |
| Source DB credential/grant invalid or overly broad | Stop rollout; security incident/remediation; do not silently use migration/admin credentials |
| Actor assertion invalid, expired, wrong audience or wrong destination | Deny; no selector resolution |
| Clinician mapping, affiliation, credential status or revocation source unavailable/stale beyond approved policy | Deny or hold pending; never infer allow |
| Source audit store unavailable or audit commit uncertain | Do not query/disclose; persist an explicit uncertain state if possible without claiming authorization |
| Replay store unavailable or duplicate assertion | Deny/uncertain according to durable replay contract; never treat as a fresh authorization |
| Source policy engine unavailable or ambiguous | Deny |
| Source endpoint times out after authorization but before response | Record truthful uncertain outcome; retry follows approved artifact/fresh-read policy |
| Destination import commit succeeds but acknowledgement/pointer sync fails | Keep destination operation in durable recovery state; do not mark COMPLETED; recovery cannot bypass source authorization |
| Operator/support asks for manual recovery | Dual-control workflow and immutable evidence; no manual force-completion or direct source DB access |

Error response equivalence and timing behavior for match/no-match/denied/unavailable/partial outcomes must satisfy the anti-enumeration contract from CAN-06. This proposal does not invent exact HTTP codes, timing windows or rate budgets; those remain protocol decisions.

## 7. Complete path inventory

Before implementation, repository-wide inventory must include:

- Federation discovery and import routes, including root and V1 mounts/aliases.
- Patient routers and any global pointer/index read/write paths.
- Every SQLAlchemy session factory, tenant database dependency, direct engine/connection use and raw SQL execution.
- All direct queries to patient, allergy, clinical resource, source-pointer and tenant mapping models.
- Background/scheduled tasks, queue consumers, event handlers and async jobs.
- Admin, support, diagnostics, reporting, exports and maintenance commands.
- Retry, reconciliation, idempotency recovery, dead-letter and operator repair paths.
- Tests, fixtures, scripts and CLI commands that may use privileged DB identities.

Search results alone are not proof of completeness. The review must combine static call-graph/data-flow analysis, effective database privilege inspection, runtime negative tests and deployment manifest/secret inspection.

Any path that reads another branch's patient data must call the source boundary. Any path that cannot prove source identity and authority must deny.

## 8. Required acceptance evidence

CAN-01 is not closed by document review or green unit tests alone. At minimum, independent reviewers must inspect the following evidence.

### 8.1 Database privilege tests

1. Connect as the destination API role and attempt direct SELECT from a foreign tenant's patient, allergy and clinical-resource tables: denied.
2. Repeat as destination import worker, background worker, admin/support runtime roles and queue consumer: denied.
3. Connect as source service role for branch A: reads permitted only for branch A's approved source tables; branch B denied.
4. Verify inherited roles, ownership, default privileges, views, functions, triggers, SECURITY DEFINER functions and search-path behavior do not restore cross-tenant access.
5. Verify runtime containers cannot access migration, owner or superuser credentials.
6. Verify a pool connection cannot retain another branch's role/schema context after reuse.

### 8.2 Application bypass tests

1. A destination process cannot obtain or construct a source tenant SQLAlchemy session.
2. Direct ORM queries, raw SQL, engine connections and repository imports from destination code fail at the database boundary.
3. Source endpoint rejects caller-supplied schema, tenant, actor, purpose, scope and arbitrary SQL/model identifiers.
4. Source authorization and audit are committed before selector resolution and disclosure.
5. A forced source-service outage does not activate an old direct-query code path.
6. Retry/recovery workers cannot reuse an expired receipt to perform a new source read.

### 8.3 Route and workflow parity

1. Root and V1 route aliases enforce identical authorization and produce equivalent protected outcomes.
2. Local cross-branch and remote cross-hospital requests use the same source authorization semantics.
3. Discovery search and candidate authorization remain distinct.
4. Import uses a distinct action/challenge and revalidates source authorization.
5. Admin, support, background, scheduled, async, retry and recovery workflows cannot bypass the source boundary.
6. Ordinary same-branch CRUD remains functional without acquiring cross-branch privileges.

### 8.4 Multi-tenant and adversarial tests

- Concurrent requests cannot switch source tenant context through pooled connections.
- Tenant/schema identifiers with SQL metacharacters or unexpected encodings are rejected before routing.
- A compromised destination role cannot enumerate source schemas or read source patient tables.
- A source service identity for one branch cannot query another branch.
- Stale, replayed, revoked or destination-mismatched assertions are denied.
- Audit, policy, replay, key or DB failures are injected at every boundary; no false allow or success is emitted.
- Static scan findings are triaged and independently signed off; no unreviewed direct source-session call remains.

### 8.5 Deployment evidence

- Service/process diagram and network policy.
- Runtime service-account inventory and secret mount inventory.
- Database role/grant matrix generated from the deployed database, not merely migration source.
- Effective privilege snapshots for every application identity.
- Container/process identity and network reachability tests.
- Independent security review of DB grants, source boundary and bypass scan.

## 9. Rollout and migration constraints

A safe implementation sequence, after formal authorization, should be:

1. Inventory current DB identities, grants, session factories, schemas and every source-data access path.
2. Design source service contract and DB role model; complete threat model and ADR.
3. Create isolated non-production test schemas and least-privilege roles.
4. Implement source-owned authorization/data-access boundary behind disabled feature flags.
5. Prove destination roles cannot directly read source data before enabling any route.
6. Migrate local cross-branch and remote routes, aliases, jobs and recovery paths to the boundary.
7. Run negative tests and static/data-flow scan; independently inspect deployed grants and secrets.
8. Perform staged non-production validation with synthetic data only.
9. Obtain separate governance, security, clinical, privacy/legal and operations approvals before any pilot or production activation.

Do not temporarily retain a direct-query fallback “for compatibility.” If the source boundary is unavailable, protected cross-branch operations are unavailable.

Rollback must not restore destination cross-tenant read privileges. A rollback may disable cross-branch functionality; it must not reintroduce the bypass that CAN-01 is intended to eliminate.

## 10. Open decisions and dependencies

The following remain unresolved and must be decided by authorized owners:

- Deployment topology: separate service/process, database-enforced procedure/RLS alternative, or a reviewed hybrid.
- Whether source services are deployed per tenant, per branch, or as a shared control plane with independently scoped database identities.
- Exact PostgreSQL role/schema grant model and operational role rotation.
- Local transport and service authentication (including mTLS/workload identity requirements).
- Source service availability objectives, bounded timeouts and capacity/fan-out limits.
- Source audit durability, retention, residency, access and tamper-evidence details (ADV-11 / D-12).
- Clinician issuer, identity proofing, credential status and trust governance (D-01–D-10).
- Local cross-branch formal approval (D-11); project direction YES is not governance approval.
- Emergency/break-glass policy (D-13); federation remains disabled initially.
- Pilot/release decision (D-14); no pre-approval is possible.
- Clinical/privacy handling of post-commit revocation quarantine and downstream use.

## 11. Relationship to existing proposals and runtime

- PR #19 contains unmerged runtime remediation and still has direct source-database access in the import path; its current code is not evidence that CAN-01 is enforced.
- PR #21 identifies the direct source DB read and warns its route inventory is not a repository-wide static-analysis certificate.
- PR #28 is an implementation blueprint; it must be updated to reflect an enforceable boundary and not just a logical source interface.
- PR #37 proposes a logical source-owned interface and lists local, remote, internal, background, admin, support and recovery paths. This proposal adds the missing process/credential/database enforcement needed to prevent bypass.
- PR #40 is the proposed canonical protocol/governance baseline. PR #41 independently identifies CAN-01 as high severity.
- PRs #23/#24 define import idempotency and recovery. Their operation state and fencing controls do not grant source-read authority.

No statement in this document means the repository has implemented, tested or deployed these controls.

## 12. Explicit non-authorization

This proposal does not authorize:

- runtime implementation or migrations;
- creating/changing production database roles, grants, credentials or secrets;
- production key generation, trust registry entries or partner onboarding;
- enabling local cross-branch or remote federation;
- accessing, importing, exporting or modifying production patient data;
- emergency/break-glass federation, pilot, deployment, release or merge.

AUD-004 remains a release blocker. PR #19 and the design PR series remain unmerged unless separately approved. Formal governance decisions D-01–D-14 remain pending as recorded in the canonical register; D-11 project direction YES does not satisfy formal approval.

## 13. Review checklist

- [ ] Architecture/security review accepts the process and credential boundary.
- [ ] Database owner validates effective PostgreSQL role/grant isolation.
- [ ] Privacy/legal and clinical owners approve source authorization and audit semantics.
- [ ] Repository-wide source-session/ORM/SQL inventory is complete.
- [ ] Root/V1, local/remote, sync/async, admin/support and recovery path matrix is complete.
- [ ] Negative DB privilege and application bypass tests pass.
- [ ] Deployment secret/process/network evidence is independently reviewed.
- [ ] Rollback cannot restore direct cross-tenant patient-table access.
- [ ] Governance decisions and implementation authorization are recorded separately.
