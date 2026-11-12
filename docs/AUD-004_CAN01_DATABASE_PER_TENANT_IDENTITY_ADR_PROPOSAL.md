# AUD-004 CAN-01 Database-per-Tenant Identity Architecture Decision Proposal

**Status:** PROPOSED ADR — NOT ACCEPTED / NOT AUTHORIZED FOR IMPLEMENTATION  
**Parent review:** PR #43 — runtime architecture review of CAN-01  
**Related design:** PR #42 — enforceable source-owned boundary proposal  
**Finding:** CAN-01A / CAN-01B / CAN-01C  
**Decision scope:** PostgreSQL tenant isolation and source-owned database access for local cross-branch and remote federation  
**Release status:** AUD-004 remains a release blocker.

## 1. Decision summary

### Proposed decision

1. **Retain database-per-tenant** as the target isolation unit for the current implementation. The inspected runtime already maps each tenant registry record to a distinct PostgreSQL database through `TenantRegistry.db_name`. This proposal does not introduce a schema-per-tenant migration.
2. **Remove global runtime database credentials from cross-tenant source access.** The current shared `DATABASE_URL` pattern must not be reused by a source authorization/data-access service.
3. **Use source-owned service identities and tenant-scoped PostgreSQL credentials.** A source service identity for tenant A can connect only to tenant A's database and only access the approved source data objects. It cannot connect to tenant B's database.
4. **Destination API, import worker, admin/support, background and recovery identities cannot connect to foreign tenant databases.** Their DB credentials are destination-local only.
5. **Keep provisioning/migration authority separate** from all runtime identities. Runtime services do not receive the PostgreSQL cluster administration or database-creation credential.
6. **Local cross-branch calls use the same authenticated source-owned protocol as remote federation.** The destination never opens a foreign tenant SQLAlchemy engine/session.
7. **The control plane routes to a source service; it does not broker raw DB credentials to destination code.**

This is a decision proposal for architecture/security/database review. It is not a governance approval or authorization to alter production infrastructure.

## 2. Runtime facts and evidence boundary

The repository review found:

- `TenantRegistry` has a unique `db_name` and describes tenants as isolated PostgreSQL databases.
- `build_db_url(db_name)` starts with `settings.DATABASE_URL` and changes the database name only.
- `settings.DATABASE_URL` is constructed from one configured PostgreSQL username/password pair.
- The tenant engine registry uses this URL builder for each tenant database.
- The inspected federation discovery/import router opens source tenant sessions through the shared tenant engine registry.
- The inspected provisioning helper connects to the `postgres` database using the shared URL builder and can issue `CREATE DATABASE` if a tenant database does not exist.

This proves a shared credential construction pattern in inspected source code. It does **not** prove the effective privileges of a deployed PostgreSQL role, whether it is a superuser, whether it has `CREATEDB`, or which production databases it can access. Those require live catalog and deployment evidence.

## 3. Why retain database-per-tenant

| Consideration | Database-per-tenant | Schema-per-tenant |
|---|---|---|
| Current code alignment | Matches inspected `TenantRegistry.db_name` and tenant engine routing | Would require a significant storage/routing migration |
| Isolation boundary | Database `CONNECT` plus object privileges and separate roles | Schema/object grants, ownership and safe role context within one database |
| Backup/restore | Tenant database can be backed up/restored independently | Requires schema-aware backup/restore discipline |
| Connection overhead | More databases and pools; needs bounded pool management | Fewer database connections may be possible |
| Cross-tenant federation | Must call source service; no foreign DB connection from destination | Must still enforce strict schema privilege isolation and source authorization |
| Migration complexity now | Incremental credential/access redesign | Adds data migration and operational change unrelated to the immediate authorization defect |

**Proposal:** do not combine CAN-01 remediation with a tenant storage-topology migration. Database-per-tenant is already the implementation contract visible in code. If a later scale or cost review recommends schema-per-tenant, it must be a separate ADR and migration project with independent threat modeling and isolation tests.

## 4. Proposed identity and credential model

### 4.1 Runtime identities

| Identity | DB access | Allowed use | Prohibited use |
|---|---|---|---|
| Destination API role for tenant A | Tenant A database only | Same-tenant CRUD and destination-side request state | Any connection to tenant B database |
| Destination import worker for tenant A | Tenant A database only | Destination clone, provenance, idempotency and operation state | Source reads from tenant B |
| Source service role for tenant A | Tenant A database only | Source-side policy, search, candidate authorization, approved source reads and source audit | Any connection to tenant B |
| Control-plane runtime role | Control-plane database only; minimal registry/routing metadata | Tenant/service routing, status and bounded control-plane operations | Patient/allergy table reads or tenant DB credential retrieval |
| Admin/support runtime role | No foreign tenant patient DB access by default; scoped access only through approved source workflow | Operational metadata and approved support workflows | Direct cross-tenant clinical reads |
| Migration role | Explicitly provisioned target database(s), used only by migration job | Schema migrations and controlled ownership tasks | Request handling, background clinical work |
| Provisioning/cluster administrator | PostgreSQL cluster/database creation operations | Tenant database creation and role provisioning | Runtime API, import, source reads |
| Backup/restore identity | Backup/restore scope only | Approved backup and recovery operations | Interactive patient query or federation disclosure |

The actual role names are intentionally not specified; names must follow repository/deployment conventions and be unique and auditable.

### 4.2 Per-tenant database roles

For each tenant database, provisioning creates distinct identities or equivalent independently scoped credentials:

- `tenant_<id>_app`: destination-local application operations.
- `tenant_<id>_source`: source-owned federation operations only.
- `tenant_<id>_migration`: schema migration, not mounted into runtime.
- `tenant_<id>_backup`: backup/restore scope, not mounted into API/worker containers.

The names above are examples, not prescribed SQL identifiers.

The source role must be limited to the minimum objects required for source policy, source clinician mapping, patient/resource reads, and source audit. If the source audit schema is in a separate database, the audit write boundary must be explicitly designed so a failure cannot be mistaken for successful authorization.

Where separate database roles within the same tenant database are used, ownership and inherited memberships must not allow the app role to assume the source or migration role. The destination app role must not be able to `SET ROLE` to a stronger identity, create arbitrary privileged functions, alter protected tables, or read source-only audit data.

### 4.3 Source service isolation

The target is one source security principal per tenant. It may be deployed as a dedicated process/container or as an isolated workload instance on shared compute, provided the workload identity, secret access, DB credential and network policy are independently scoped to one tenant.

A shared host, Kubernetes cluster, VM pool or service mesh does not itself provide tenant isolation. The enforcement must be demonstrated by distinct workload identity, secret policy, database credential, network policy and effective PostgreSQL privileges.

The source service:
- derives its tenant identity from its own provisioned configuration and workload identity;
- does not accept `db_name`, schema, credential reference, DSN or tenant ID as a caller-controlled routing override;
- authenticates destination service identity and verifies the clinician assertion;
- verifies source-controlled actor mapping/status, purpose/action, destination, resource/scope, policy and replay;
- commits required source authorization/disclosure audit evidence before selector resolution or disclosure;
- returns only the minimum authorized response;
- never returns a DB session, engine, ORM object or credential.

The source service identity for tenant A cannot retrieve tenant B's secret or use tenant B's DB role.

### 4.4 Control-plane responsibilities

The control plane may store:
- tenant ID and branch code;
- tenant database name as non-secret routing metadata;
- source service endpoint/workload identity;
- secret-manager reference identifier (opaque metadata only), if needed for operations;
- service health and configuration version.

The control plane must not store plaintext database passwords or expose secret-manager references as bearer credentials to destination services. A secret reference is not authorization to retrieve the secret.

A destination request cannot ask the control plane to return a source database URL, username/password, connection string, or arbitrary secret. Source service secret access is governed by workload identity and secret-manager policy, not by request payload.

### 4.5 Provisioning and migration separation

The existing shared URL builder and provisioning helper must not remain available to runtime federation code.

Proposed separation:
- **Provisioning job:** short-lived identity permitted to create a tenant database and provision its roles; activated only by a controlled provisioning workflow.
- **Migration job:** short-lived identity permitted to apply migrations to explicitly enumerated tenant database(s); no cluster-wide superuser credential in web/worker containers.
- **Runtime services:** only their minimum operational database credentials.
- **Secret manager:** stores per-tenant credentials; access policy binds each secret to the corresponding tenant source workload identity.
- **Rotation:** rotates a tenant credential without distributing it to unrelated tenant workloads; revoke old credential after controlled pool drain and validation.

No runtime process may call a generic helper that silently turns a global cluster credential into a connection to any tenant database.

## 5. Request and connection flow

### 5.1 Local cross-branch discovery/import

1. Tenant A destination API authenticates the clinician's tenant-local session and validates request shape.
2. Destination API resolves an eligible source service endpoint from trusted control-plane metadata. It does not retrieve source database credentials.
3. Destination API sends a bounded, authenticated request to source tenant B's source service.
4. Source B authenticates destination workload identity and validates the signed clinician assertion, issuer, audience, destination, purpose, action and scope.
5. Source B resolves the clinician against source-controlled identity/affiliation/credential records.
6. Source B commits the required source authorization/audit record before patient-specific selector resolution.
7. Source B resolves the bounded selector inside tenant B's database using only tenant B's source DB credential.
8. Source B authorizes each candidate/resource and commits disclosure intent before protected response serialization/release.
9. Source B returns a minimum response with an authenticated integrity envelope.
10. Destination A validates the response and performs only destination-side import/idempotency/provenance operations using tenant A's DB credential.
11. Acknowledgement, pointer synchronization and recovery follow the separate lifecycle protocol; none grants a new source read.

Remote federation follows the same source-owned sequence, with a different transport and trust relationship. Locality must not weaken authorization.

### 5.2 Same-tenant requests

Ordinary same-tenant CRUD continues to use the tenant's local application identity. A request is not same-tenant merely because it originated from an authenticated user in that tenant. Any source branch mismatch must use the source-owned protocol.

## 6. PostgreSQL enforcement requirements

The database team must validate the following against the actual deployed PostgreSQL version/configuration.

1. Each tenant database has an explicit allowlist of runtime roles permitted to connect.
2. Tenant A app/source roles cannot connect to tenant B's database.
3. No runtime role has `SUPERUSER`, `CREATEDB`, `CREATEROLE`, ownership of unrelated tenant databases, or membership in a broad role that grants equivalent access.
4. Tenant app role cannot `SET ROLE` to source, migration, backup or provisioning roles.
5. Tenant source role cannot connect to any other tenant database.
6. Database ownership is assigned to a non-login owner or tightly controlled migration identity, not the web/API role.
7. Default privileges and future objects do not accidentally grant broad access.
8. Views, materialized views, functions, triggers, extensions, foreign data wrappers, dblink-like functionality and SECURITY DEFINER routines do not provide a bypass.
9. The control-plane role cannot connect to tenant databases unless a separately justified and reviewed operational function requires it.
10. Connection pool identity is immutable per engine. No request-time mutation of username, role, DSN or target database is permitted.
11. Runtime container secrets are enumerated and verified. No runtime container receives provisioning, cluster-admin, migration or unrelated tenant credentials.
12. Network policies restrict which workloads can reach tenant database endpoints; network controls supplement but do not replace PostgreSQL authorization.
13. Logs and metrics do not contain passwords, DSNs, authorization headers, patient selectors or protected patient data.

A database name is not a security boundary if the same credential has `CONNECT` and object privileges on every tenant database.

## 7. Alternatives and decision rationale

### Option A — Per-tenant source service and per-tenant DB identity (recommended)

**Security:** strongest tenant blast-radius boundary. Compromise of one source workload should expose at most that tenant, assuming secret, network and database grants are correctly isolated.

**Operational cost:** more workload identities, per-tenant service lifecycle, monitoring, service discovery, secret rotation and connection management. Can be implemented as isolated workload instances on shared compute; one VM/cluster per tenant is not required.

**Fit:** closest to the source-ownership model and easiest to reason about in an independent security review.

### Option B — Shared source gateway with per-tenant credentials

**Security:** central gateway can potentially access every tenant secret. If compromised, blast radius may span the fleet. Per-tenant DB credentials reduce database privilege but do not eliminate central secret-broker compromise.

**Operational cost:** fewer service instances, simpler routing and lower baseline compute.

**Conditions for consideration:** secret manager must enforce per-request tenant scoping that the gateway cannot bypass; a separate authorization broker or hardware-backed policy may be needed; tenant credential retrieval must be audited; no long-lived fleet-wide secret cache; compromise and incident-response plan must explicitly cover all tenants.

**Disposition:** not the default recommendation. It may be proposed as a cost-optimized alternative only with an independently reviewed threat model demonstrating that the gateway cannot freely enumerate/retrieve all tenant secrets.

### Option C — Database-enforced stored procedures / restricted role

**Security:** can deny base-table reads to the application and expose only narrow approved operations, but trusted actor context, audit ordering, replay, clinician identity and policy semantics become database responsibilities.

**Operational cost:** complex PL/pgSQL/procedure lifecycle, testing, migration and policy maintenance.

**Disposition:** not selected in this proposal. Requires a separate design proving equivalence to the source authorization protocol.

### Option D — Keep global PostgreSQL credential and rely on source service code

**Security:** no enforceable database boundary; a compromised process or code path can query other tenant databases.

**Disposition:** rejected.

## 8. Cost and capacity controls for Option A

Option A does not require one always-on VM or one dedicated Kubernetes cluster per tenant. The following deployment pattern may reduce cost while preserving per-tenant identity:

- shared compute substrate with per-tenant source workload identities;
- scale-to-zero or on-demand source workers only if cold-start and authorization/audit semantics remain safe;
- bounded connection pools per tenant with explicit total connection budgets;
- no shared connection pool that can switch DB credentials between tenants;
- service discovery from trusted control-plane metadata;
- per-tenant health, latency, failure and credential-rotation telemetry without patient data;
- explicit limits on concurrent source queries, fan-out, connection count and queue depth;
- safe idle pool disposal and secret rotation with bounded connection drain.

A pooled worker that can load any tenant secret is effectively Option B, not Option A. Deployment labels do not determine the security model; effective workload identity and secret permissions do.

## 9. Migration sequence after separate authorization

This sequence is a future proposal only; it is not authorization to execute it.

1. Inventory current deployed PostgreSQL roles, memberships, database ACLs, ownership, object privileges, secret mounts, service accounts, network policy and tenant engine usage.
2. Confirm database-per-tenant in all supported deployment modes, including on-premise/self-hosted and cloud.
3. Create a non-production proof-of-isolation environment with synthetic tenants A and B.
4. Provision distinct app/source/migration identities for A and B; verify the negative privilege matrix before writing application integration.
5. Separate cluster provisioning and migration workflows from runtime application configuration.
6. Implement source service identity and authenticated transport under disabled feature flags.
7. Replace direct foreign-tenant engine/session calls in discovery/import and all internal/job/recovery paths.
8. Prove source search authorization and candidate authorization/audit ordering.
9. Run static analysis, DB privilege tests, service identity tests, route alias parity and failure injection.
10. Independently review deployed secret mounts, role grants, source service blast radius and rollback behavior.
11. Conduct non-production synthetic-data validation.
12. Obtain formal governance, clinical, privacy/legal, security, database and operations approvals before pilot or production activation.

Rollback must disable cross-branch functionality. It must never restore a destination credential that can connect to arbitrary tenant databases.

## 10. Required acceptance tests and evidence

### 10.1 Database access matrix

For tenant A and tenant B, test all identities:

| Attempt | Expected |
|---|---|
| A app → A database | Allowed only for app grants |
| A app → B database | Denied at connection |
| A import worker → B database | Denied at connection |
| A admin/support runtime → B database | Denied at connection |
| A source service → A database | Allowed only for source grants |
| A source service → B database | Denied at connection |
| B source service → A database | Denied at connection |
| Control-plane runtime → A/B patient DB | Denied unless a separately approved non-patient metadata operation is proven |
| Runtime API/worker → `postgres` administrative DB | Denied |
| Runtime API/worker → `CREATE DATABASE` / `CREATE ROLE` | Denied |
| Migration identity → explicitly assigned DB | Allowed only during controlled migration |
| Provisioning identity → cluster provisioning | Allowed only in isolated provisioning workflow |

### 10.2 Effective privilege evidence

Capture and review, for every runtime role:
- role attributes and memberships from `pg_roles` and `pg_auth_members`;
- database ownership and `datacl` for every tenant DB;
- `CONNECT` privilege results using `has_database_privilege`;
- schema/table/sequence/function privileges using effective privilege functions;
- ownership, default privileges and privileged routine inventory;
- secret manager access policy and audit events;
- deployment environment variables and mounted secret names (never secret values);
- network reachability matrix from each workload to each tenant DB.

### 10.3 Application and service bypass evidence

- Destination code cannot instantiate a foreign tenant engine/session because it has no DSN/credential and DB access is denied.
- No destination path imports a global tenant engine factory to read a foreign source DB.
- Caller-supplied `db_name`, tenant ID, schema or credential reference cannot change the source service's own tenant identity.
- Source service B cannot access A's secret or database.
- Source service outage does not trigger direct SQL fallback.
- Pool reuse, worker reuse, retry and cancellation cannot carry tenant credentials/context across tenants.
- Root/V1 aliases, local/remote requests, jobs/admin/support/recovery have identical source authorization requirements.
- Authorization and audit failures deny before selector resolution/disclosure.

### 10.4 Independent sign-off

Evidence must be reviewed by:
- PostgreSQL/database owner;
- application security reviewer;
- platform/operations owner;
- privacy/legal owner;
- clinical governance owner for source disclosure and quarantine semantics.

Passing automated tests is necessary but not sufficient.

## 11. Open decisions

- Whether Option A is operationally accepted as the security baseline.
- Whether source workload instances are persistent, autoscaled or on-demand.
- Secret manager technology, tenant-scoped policy and credential rotation protocol.
- Exact PostgreSQL role/object privilege templates and ownership pattern.
- Whether tenant databases share a PostgreSQL cluster and the required cluster-level blast-radius controls.
- Network isolation and workload identity mechanism.
- Control-plane availability and source endpoint discovery failure semantics.
- On-premise deployment parity and customer-managed PostgreSQL support.
- Backup/restore identity and disaster recovery access model.
- Cost ceilings, connection budgets and service SLOs.
- Formal D-01–D-14 governance decisions, including D-11 local cross-branch approval.

No values are invented or treated as approved.

## 12. Explicit non-authorization

This proposal does not authorize:
- runtime implementation or application refactoring;
- PostgreSQL role/database/grant changes;
- production credential or secret-manager creation, retrieval, rotation or revocation;
- database provisioning or migrations;
- production patient-data access, import or export;
- partner onboarding, local/remote federation enablement, emergency access or pilot;
- deployment, release or merge.

AUD-004 remains a release blocker. PR #42 and this proposal remain design-only until independent architecture, security, database, clinical, privacy/legal and operations approvals are recorded. Project direction D-11 YES is not formal governance approval.
