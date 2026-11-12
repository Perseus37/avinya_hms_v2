# Independent Runtime Architecture Review — AUD-004 CAN-01 Proposal (PR #42)

**Review status:** Independent design/runtime cross-check — findings open  
**Reviewed proposal:** PR #42, head `66b6ed518689824e4eeac819ec228e5163ef294a`  
**Runtime evidence inspected:** default-branch `backend/core/database.py`, `backend/core/config.py`, `backend/control_plane/models.py`, `backend/domains/federation/router.py`; corresponding PR #19 federation remediation branch was also inspected.  
**Disposition:** PR #42 correctly rejects a shared Python interface as a security boundary, but its database isolation section assumes the wrong tenant storage topology and does not yet specify a viable credential architecture for the inspected runtime. CAN-01 remains HIGH and unresolved. AUD-004 remains release-blocking.

## 1. Executive assessment

PR #42 proposes a separately enforced source-owned process/service boundary plus source-scoped database identities and grants. That is a sound security direction in principle. However, the inspected runtime does not match the proposal's repeated schema-per-tenant framing:

1. The runtime maps each tenant to a **separate PostgreSQL database** using `TenantRegistry.db_name`, not a schema name.
2. `build_db_url(db_name)` starts from the single `settings.DATABASE_URL` and changes only the database component.
3. `settings.DATABASE_URL` is constructed from one `POSTGRES_USER` and `POSTGRES_PASSWORD` pair.
4. The tenant engine registry uses that same URL builder for every tenant database.
5. The federation discovery/import router directly creates sessions for other tenants' databases through `tenant_engine_pool.get_engine(source_registry.db_name)`.
6. The inspected `TenantRegistry` model stores `db_name` and tenant application secrets, but no per-tenant PostgreSQL username/credential reference is visible in the model inspected.

This means process separation by itself would not establish branch isolation if the source service receives the same broad PostgreSQL identity as the destination service. The actual effective database privileges were not available in this source review; they must be inspected in the deployed database. No claim is made here that the configured role is definitely a PostgreSQL superuser. The concrete finding is that the inspected configuration and connection factory do not provide per-tenant database identities or demonstrate least-privilege grants.

## 2. Findings

### CAN-01A — High: Proposal's schema-per-tenant enforcement model does not match the inspected database-per-tenant runtime

**Evidence**
- `backend/control_plane/models.py`: `TenantRegistry` describes isolated PostgreSQL databases and stores a unique `db_name`.
- `backend/core/database.py`: `build_db_url(db_name)` calls `make_url(settings.DATABASE_URL)` and changes only the database name.
- `backend/core/config.py`: `DATABASE_URL` is constructed from one configured `POSTGRES_USER`, `POSTGRES_PASSWORD`, host and port.
- `TenantEngineRegistry.get_engine(db_name)` creates engines through this shared URL builder.
- `backend/domains/federation/router.py`: discovery and import resolve source tenant `db_name` from the control plane and open a source session through the shared tenant engine registry.

**Gap**
PR #42 Section 4.2 focuses on schema grants, `search_path`, and schema-qualified access. Those controls do not directly describe the inspected runtime, where the tenant boundary is a database name. The proposal therefore cannot be used as an implementation contract without first reconciling the storage topology.

**Required resolution**
1. State explicitly that the inspected runtime is database-per-tenant, not schema-per-tenant.
2. Define the intended target topology and whether the project is changing it. Do not silently apply schema-grant guidance to database-per-tenant deployment.
3. Specify database-level `CONNECT`, object privileges, role memberships, ownership, `CREATEDB`, and administrative credential boundaries for each tenant database.
4. Add an architecture decision record that explains the security and operational trade-offs between database-per-tenant and schema-per-tenant for this codebase.
5. Update all proposed source-boundary and deployment diagrams to identify the actual database isolation unit.

**Acceptance evidence**
- An approved ADR matches the actual runtime data model.
- A live privilege matrix covers each database and every runtime identity.
- Negative tests demonstrate that a destination identity cannot connect to or read another tenant database.

### CAN-01B — High: One configured PostgreSQL identity is reused across tenant databases; process separation alone may preserve cross-tenant access

**Evidence**
- `Settings.DATABASE_URL` uses one `POSTGRES_USER` and `POSTGRES_PASSWORD`.
- `build_db_url(db_name)` changes only the database name, not the username or password.
- Both control-plane and tenant engines use the same URL builder.
- `TenantEngineRegistry.get_engine` has no tenant-specific credential lookup.
- `TenantRegistry` has a `db_name` field but the inspected model does not expose a tenant-specific database credential reference.
- `ensure_postgres_db_exists` also builds a connection to the `postgres` database through the same configured identity and issues `CREATE DATABASE` when absent.

**Gap**
If a new source authorization process is provisioned with the same configured PostgreSQL identity, it can retain whatever database privileges that identity already has. Splitting the application into processes does not constrain SQL privileges. Conversely, merely creating distinct service accounts in the deployment does not help if every service receives the same global credential from the shared settings path.

The source review cannot determine effective PostgreSQL grants, role inheritance, database `CONNECT` ACLs, ownership or the production credential mounted into containers. Those are required evidence, not assumptions.

**Required resolution**
1. Choose a credential model with independently scoped identities. Viable patterns include:
   - per-tenant database roles with explicit database `CONNECT` and object privileges, with source service obtaining only the relevant source credential from an approved secret manager;
   - a source service per tenant/database with a database credential that can access only that tenant database;
   - a reviewed database-enforced stored-procedure design where destination roles cannot read base tables and cannot assume privileged roles.
2. Keep provisioning/migration credentials separate from runtime API, worker, source service and control-plane credentials. The runtime must not receive a role capable of `CREATEDB`, owning tenant databases, or reading all tenant databases unless a narrowly justified and independently approved requirement exists.
3. Remove any destination-side code path that accepts a tenant database name and uses a global credential to open it.
4. Define credential storage, rotation, revocation, bootstrapping, disaster recovery and secret-access audit.
5. Verify role membership and effective privileges, not only grants authored in migration files.
6. Ensure source service credentials cannot connect to other tenant databases, and destination credentials cannot connect to source databases.

**Acceptance evidence**
- Runtime secret inventory shows distinct service identities and no shared broad credential.
- PostgreSQL inspection captures `pg_roles`, `pg_auth_members`, database `datacl`, ownership, schema/table/function privileges and effective `has_database_privilege` / `has_table_privilege` results for every runtime role.
- Tests attempt direct connection and SELECT from another tenant database using destination API, worker, admin/support and queue identities; all fail.
- A source identity for tenant A cannot connect to tenant B's database.
- Runtime containers cannot access migration/provisioning credentials.
- Credential rotation/revocation tests demonstrate old credentials cease to work.

### CAN-01C — High: Existing federation source reads bypass the proposed source-owned boundary

**Evidence**
- The inspected federation router imports `tenant_engine_pool` and `sessionmaker`.
- Discovery resolves tenant database names from `TenantRegistry`, calls `tenant_engine_pool.get_engine(branch_db_name)`, and opens `BranchSession` to read source policy, patient and allergy data.
- Import resolves `source_registry.db_name`, calls `tenant_engine_pool.get_engine(source_registry.db_name)`, and opens `SourceSession` before reading source policy and patient/allergy data.
- The router is mounted through the application route structure; route alias parity remains a separate required check.

**Gap**
The current router path is itself a destination-side source-database reader. A future source service is not an enforcement boundary while this code path, or an equivalent helper, retains the ability to open arbitrary tenant databases. The proposal says to remove these paths but does not yet give a migration cutover rule tied to the concrete connection factory.

**Required resolution**
1. Remove direct foreign-tenant engine/session access from the destination federation router and all other destination-side modules.
2. Replace it with an authenticated source-owned endpoint/client contract. The source endpoint must derive its own tenant database from trusted local source configuration, not a caller-supplied `db_name`.
3. Do not pass SQLAlchemy sessions, engines, ORM entities, lazy relationships, or broad source credentials across the service boundary.
4. Enforce source-side search authorization before selector query and candidate authorization before disclosure.
5. Apply the same source-owned boundary to local cross-branch and remote federation paths.
6. Keep the destination import transaction limited to destination data and durable provenance/operation state.

**Acceptance evidence**
- Repository-wide scan finds no destination-side `tenant_engine_pool.get_engine(source_db_name)` or equivalent foreign tenant session creation in protected workflows.
- Static/data-flow review covers imports of session factories, engine factories, raw SQL, model repositories, jobs and CLI paths.
- Runtime tests prove the destination service cannot create a source DB session even if authorization code is bypassed.
- Local and remote paths pass the same source-side authorization tests.

## 3. Corrected target architecture for this runtime

The proposal should choose and document one of these options before implementation.

### Option A — Per-tenant source service and per-tenant database identity

- Each tenant/source branch has a source authorization/data-access service identity.
- That service can connect only to its own tenant database.
- Destination API/import worker has no source database credential and cannot connect to arbitrary tenant databases.
- A local cross-branch call uses authenticated service-to-service transport to the source branch endpoint, just like remote federation.
- Control-plane routing provides only trusted service endpoint metadata; it does not provide database credentials or patient existence.

**Advantages:** strongest alignment with source ownership and least privilege; compromise of one source service is bounded to its tenant if secrets and DB grants are correctly scoped.

**Costs:** more service instances or logical isolation units, service discovery, credential lifecycle, operational monitoring and per-tenant deployment complexity.

### Option B — Shared source service with per-tenant database credentials

- A hardened source service is the only component allowed to retrieve tenant-scoped database credentials.
- It derives tenant identity from trusted server-side registry state and maps it to a source credential through a secret manager.
- The service never accepts a caller-supplied database name, credential reference or schema.
- Each source connection is made with a credential limited to one tenant database; a request cannot cause role switching into another tenant.
- The service must constrain its own blast radius, memory/secret exposure, caches, connection pools, concurrency and tenant context.

**Advantages:** lower service deployment overhead than one service per tenant.

**Costs:** the central service and its secret-broker access become high-value targets; compromise could expose multiple tenant credentials. This requires a stronger threat model, per-tenant isolation inside the service, and independently tested secret access boundaries.

### Option C — Shared runtime with database-enforced stored procedures

- Destination roles cannot SELECT protected patient/allergy tables directly.
- Only approved database functions/procedures can perform source operations.
- Trusted actor/destination context is cryptographically or otherwise unforgeably bound; caller-controlled session variables cannot manufacture it.
- Procedures enforce source policy, replay and audit semantics before protected reads.
- Destination roles cannot own tables, bypass RLS, change policies, execute arbitrary privileged functions or assume a stronger role.

**Advantages:** database can enforce the boundary even if application code omits a call.

**Costs:** complex policy logic, transaction semantics, testability and schema migration burden; must be reviewed against the full clinician identity and source-audit protocol.

**Recommendation:** evaluate Option A as the strongest initial security model. Option B may be a practical alternative if operational scale requires it, but only with per-tenant credentials and independently constrained secret retrieval. Option C should be selected only if the team can prove equivalent enforcement for every route, actor, audit and recovery requirement.

No option is approved by this review.

## 4. Additional precision required in PR #42

1. Replace schema-specific terms (`search_path`, schema owner, schema grants) with database-per-tenant equivalents where the inspected runtime is authoritative. If a future schema-per-tenant target is intended, state it as a proposed architecture migration and specify how it relates to current code.
2. Clarify the relationship between the control-plane database and tenant databases. Current code builds both connections from the same global PostgreSQL identity; the control plane must not become a credential broker by accident.
3. The source service's database credential must be provisioned independently of the destination process. A shared `POSTGRES_USER` environment variable mounted into both processes defeats the intended separation.
4. Tenant registry must store only a non-secret credential reference (or a service routing identity), not plaintext database credentials. Secret manager access must be source-scoped and audited.
5. Do not use the current global tenant engine registry as the source service's authorization mechanism. It is a connection-routing cache, not an access-control boundary.
6. Treat provisioning/migration database access separately. The inspected helper uses the shared URL builder to connect to the `postgres` database and create databases; this capability must not be present in runtime request services.
7. Require deployment evidence from the actual environment. Source code cannot prove what PostgreSQL roles, grants, secrets or network policies are active.

## 5. Required implementation gates

CAN-01 must remain open until all of the following are satisfied:

- [ ] Runtime topology is explicitly confirmed as database-per-tenant or schema-per-tenant.
- [ ] Architecture ADR chooses the enforcement option and records blast radius/trade-offs.
- [ ] Source service has a separately authenticated identity and source-scoped credential.
- [ ] Destination API, import, background, admin/support and recovery identities cannot connect to source tenant databases or read their protected tables.
- [ ] Provisioning/migration credentials are unavailable to runtime services.
- [ ] Source authorization is durably committed before selector resolution; candidate authorization and disclosure intent precede disclosure.
- [ ] All foreign-tenant source session/engine/SQL paths are removed or denied at the database boundary.
- [ ] Root/V1 route aliases and local/remote workflows are tested for parity.
- [ ] Secret retrieval, rotation, revocation, caching and connection-pool isolation are independently tested.
- [ ] Effective database privileges and deployed secret mounts are reviewed by an independent database/security owner.
- [ ] Fail-closed behavior and no-direct-query-fallback are tested under source service outage.
- [ ] Governance D-01–D-14 and implementation authorization are separately recorded.

## 6. Evidence limitations

This review inspected repository source files and an unmerged PR #19 branch. It did not access production infrastructure, secret values, database catalogs, live grants, runtime containers, or patient data. Therefore:

- It establishes that the inspected code constructs tenant database connections using one configured PostgreSQL username/password pair.
- It establishes that the inspected federation router opens source tenant sessions directly through the tenant engine registry.
- It does **not** establish whether the deployed PostgreSQL role is superuser, has `CREATEDB`, or has effective access to every tenant database.
- It does **not** establish that production is currently exposed or that any patient data was accessed.
- The effective privilege and deployment evidence requested above is necessary to determine actual exploitability and close the finding.

## 7. Explicit non-authorization

This review is design evidence only. It does not authorize runtime implementation, migrations, database role/grant changes, credential creation/rotation, secret-manager changes, production patient-data access, partner onboarding, federation enablement, pilot, deployment, release or merge.

AUD-004 remains a release blocker. PR #42 should remain draft and unmerged until CAN-01A/B/C are reconciled with the actual runtime architecture and independently reviewed.
