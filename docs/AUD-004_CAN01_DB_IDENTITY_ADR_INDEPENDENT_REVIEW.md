# Independent Review — AUD-004 CAN-01 Database Identity ADR Proposal

**Review status:** Independent design review — findings open  
**Reviewed:** PR #44, head `eb65846efa782b8f7536b0c03a08e698b22943b3`  
**Runtime baseline:** PR #43 and inspected database-per-tenant source architecture  
**Disposition:** PR #44 corrects the tenant storage-topology mismatch and proposes a substantially stronger identity model. It is not yet a complete PostgreSQL privilege or credential-lifecycle implementation contract. CAN-01 remains HIGH and unresolved. AUD-004 remains release-blocking.

## 1. Executive assessment

PR #44 makes several important corrections:

- It explicitly retains the inspected database-per-tenant model instead of incorrectly applying schema-per-tenant controls.
- It rejects reuse of the global runtime PostgreSQL credential for cross-tenant source access.
- It separates destination, source, control-plane, migration, provisioning and backup responsibilities.
- It proposes a source-owned service identity per tenant and routes local cross-branch access through the same source-owned protocol as remote federation.
- It recognizes that a shared source gateway with access to all tenant secrets has a larger compromise blast radius.
- It requires negative cross-database tests and effective privilege evidence rather than relying on application conventions.

The proposal still needs more exact PostgreSQL semantics and operational lifecycle contracts. In particular, PostgreSQL roles are cluster-wide rather than database-local; default database CONNECT privileges and inherited role membership must be addressed explicitly. Secret rotation must invalidate active connections, not only update a secret value. Provisioning and recovery identities also need tighter privilege and evidence boundaries.

This review is based on repository documentation and source-level context. It did not inspect a live PostgreSQL cluster, deployed secret manager, runtime container, network policy, or patient data.

## 2. Findings

### DBID-01 — High: PostgreSQL cluster-wide role semantics and default CONNECT grants are not explicit enough

**Issue**

The ADR says each tenant database will have an explicit allowlist of runtime roles and that tenant A identities cannot connect to tenant B. It does not prescribe the default PostgreSQL behavior that must be neutralized.

PostgreSQL roles are cluster-wide. Database-level CONNECT is commonly available to PUBLIC unless explicitly revoked. Creating a role per tenant does not by itself stop it from connecting to another database if PUBLIC or another inherited role grants CONNECT. A role may also inherit privileges through memberships.

**Required resolution**

1. Explicitly revoke database CONNECT from PUBLIC on every tenant database, unless a documented exception is required.
2. Grant CONNECT only to the exact tenant runtime login roles and explicitly approved operational identities.
3. Audit role membership recursively, including `INHERIT`, `SET ROLE` capability, predefined roles and any role that owns/controls protected objects.
4. Verify that no tenant runtime role is a member of a cross-tenant, cluster-admin, migration, backup or provisioning role.
5. Include the control-plane database and administrative `postgres` database in the same access matrix.
6. Define a safe default for newly provisioned databases so a newly created tenant cannot temporarily inherit broad access before hardening completes.

**Acceptance evidence**

- Catalog snapshot of `pg_roles`, `pg_auth_members`, `pg_database.datacl`, database owners and effective CONNECT checks for every runtime login.
- Negative tests using actual destination/source runtime identities against every other tenant database.
- Provisioning test proves the database is not exposed between CREATE DATABASE and completion of role/ACL hardening.

### DBID-02 — High: Source and application role privilege separation inside a tenant database needs an exact ownership model

**Issue**

The ADR lists separate app, source, migration and backup roles but leaves the actual ownership and login/group-role arrangement open. If an application login owns patient tables, can alter protected objects, can create privileged functions, or can assume the source role, the proposed separation collapses.

Conversely, if the source service role has broad SELECT across all patient/clinical tables, its compromise may expose the full tenant database. That may be the accepted tenant-level blast radius, but the minimum source data-access scope and review evidence should be explicit.

**Required resolution**

1. Define non-login object-owner roles separately from runtime login roles.
2. Runtime app/source logins must not own protected tables, schemas, functions or databases.
3. Runtime logins must not have `CREATEROLE`, `CREATEDB`, `SUPERUSER`, replication or bypass-RLS capability unless independently justified.
4. Define explicit membership direction: app login cannot `SET ROLE` to source, migration, owner or backup; source login cannot assume owner/migration; migration login is not mounted into app/source runtime.
5. Specify object-level grants for source operations, including patient, allergy, clinician mapping, source policy, provenance and source audit writes. Avoid granting broad table access by default.
6. Review views, SECURITY DEFINER functions, triggers, extensions, foreign data wrappers and database links for privilege escalation or cross-database access.
7. Document whether row-level security is used and ensure runtime identities cannot bypass it. RLS is supplementary and must not substitute for database isolation.

**Acceptance evidence**

- Reviewed role-membership graph and object-ownership matrix.
- `has_table_privilege`, `has_schema_privilege`, `has_function_privilege` and effective database checks for every runtime login.
- Negative tests for ALTER/DROP/CREATE FUNCTION/SET ROLE/CREATE EXTENSION and protected-table access from destination roles.
- Independent review of all SECURITY DEFINER and cross-database capable objects.

### DBID-03 — High: Secret bootstrap, rotation, revocation and pool invalidation are not yet an executable lifecycle

**Issue**

PR #44 states that credentials are stored per tenant, rotated, and old credentials revoked after a controlled pool drain. It does not yet define how the initial credential is delivered to the source workload, how secret-manager access is bound to an immutable workload identity, or how active sessions are invalidated after compromise/revocation.

Updating a secret-manager value does not terminate already authenticated PostgreSQL sessions. Long-lived SQLAlchemy pools may continue using existing connections until disposed. A source service with cached credentials or broad secret-manager permissions can also exceed the intended tenant boundary.

**Required resolution**

Define lifecycle states and owners for:
- initial role/secret creation and one-time bootstrap;
- workload identity attestation and authorization to retrieve exactly one tenant secret;
- secret versioning and activation;
- credential rotation with bounded overlap, pool disposal/recreation and verification;
- emergency revocation after compromise, including termination of active DB sessions where required;
- secret-manager outage and stale-cache behavior;
- service restart, autoscaling, restore and disaster-recovery behavior;
- audit records for create/read/rotate/revoke operations, without logging secret values;
- tenant deprovisioning and credential destruction/retention.

The source service must not receive a fleet-wide secret-manager role. Secret lookup must be bound to a provisioned workload identity and immutable tenant assignment, not a request parameter or mutable tenant context.

**Acceptance evidence**

- Threat-modeled secret-manager policy and workload identity binding.
- Tests show tenant A workload cannot read tenant B secret.
- Rotation test proves old connections are drained and old credentials no longer authenticate.
- Emergency revocation test proves the credential and active sessions are unusable within an approved bounded interval.
- Secret-manager outage fails closed; it does not fall back to the global DATABASE_URL credential.
- No secret values appear in logs, traces, crash dumps or deployment metadata.

### DBID-04 — High: Provisioning and migration privilege separation needs a safe, atomic bootstrap contract

**Issue**

The ADR separates provisioning and migration identities, but the existing helper uses the shared URL builder to connect to the `postgres` database and issue CREATE DATABASE. A future provisioning workflow must ensure that tenant DB creation, role creation, ACL hardening and secret registration happen as one controlled lifecycle. A partially provisioned database must not be reachable by ordinary runtime identities.

**Required resolution**

1. Define a provisioning state machine, for example: REQUESTED → DATABASE_CREATED → OWNER_ASSIGNED → RUNTIME_ROLES_CREATED → PUBLIC_ACCESS_REVOKED → ACL_VERIFIED → SECRET_REGISTERED → SERVICE_BOUND → READY.
2. Any failure before READY leaves the tenant unavailable to runtime services; retries are idempotent and reconcile observed catalog state.
3. Provisioning identity is short-lived, separately authenticated and unavailable to runtime containers.
4. Separate cluster-level CREATE DATABASE/ROLE privileges from database migration privileges.
5. Migration role is restricted to enumerated target DBs and cannot create unrelated databases, roles or secrets.
6. Role/ACL templates are versioned and validated against PostgreSQL version and managed-service constraints.
7. Tenant deletion, restore and re-provisioning must not accidentally reuse old credentials or leave stale role memberships.

**Acceptance evidence**

- Failure-injection tests at every provisioning state.
- Catalog assertions after successful and failed provisioning.
- Runtime cannot connect to a tenant DB until ACL hardening and source workload binding are complete.
- Provisioning and migration credentials are absent from API, worker, source and control-plane containers.

### DBID-05 — High: Source audit durability and DB transaction boundaries require a concrete design

**Issue**

The ADR correctly says source authorization/audit must commit before selector resolution and disclosure. It also acknowledges that source audit may live in a separate database. It does not fully define what happens if authorization state, audit write, patient read and disclosure intent span different databases or transactions.

A source service must not return data if the required audit event was not durably committed. A failed network response after disclosure intent or response generation must not create a false success or allow an unaudited retry.

**Required resolution**

1. Identify the authoritative source audit store and whether it is in the tenant database or a separate audit service/database.
2. Define the exact commit boundary for search authorization, candidate authorization, disclosure intent and delivery outcome.
3. If audit and clinical data are in separate databases, define an outbox/transaction protocol and explain how a protected read is prevented until the authorization event is durably committed.
4. Distinguish authorization decision, disclosure intent, response generation, network delivery and destination acknowledgement.
5. Define outcome-uncertain states and reconciliation; never synthesize success after an audit or network failure.
6. Specify audit retention, immutability/tamper evidence, access control and backup/restore behavior consistent with the prior ADV-11/12 design.

**Acceptance evidence**

- Failure-injection tests at each transaction boundary.
- Proof that no selector resolution or protected read occurs when required authorization audit persistence fails.
- Proof that response delivery cannot be recorded as acknowledged solely because a network write succeeded.
- Independent review of source audit store availability and recovery.

### DBID-06 — Medium: Backup/restore identity could become an alternate cross-tenant data path

**Issue**

The ADR includes a backup/restore identity but does not define whether backup operators, restore jobs or restored database owners can bypass the source-owned access model. Backups contain patient data and restoring a tenant database into a shared environment can unintentionally make it accessible to broad runtime roles.

**Required resolution**

- Scope backup credentials to the minimum database/backup operations and separate them from interactive runtime identities.
- Restrict backup artifact access, encryption keys and restore permissions by tenant and operational purpose.
- Restore into a quarantined environment with default-deny network and database ACLs.
- Reapply and verify tenant-specific roles, ownership, CONNECT revocations, secret rotation and service identity before a restored tenant becomes available.
- Prohibit restore operators from querying patient tables as part of ordinary support work.
- Audit restore, export, download and key-use events.

**Acceptance evidence**

- Restore test proves a restored tenant is inaccessible to other tenant identities before and after activation.
- Backup/restore identities cannot perform ordinary patient SELECT.
- Quarantine and activation evidence is independently reviewed.

### DBID-07 — Medium: Shared-cluster and on-premise deployment assumptions need an explicit support matrix

**Issue**

PR #44 correctly says that shared compute does not itself provide isolation and that the deployment model may vary. It does not yet state which PostgreSQL deployment modes can meet the proposed controls or what happens when customers operate their own cluster/credentials.

**Required resolution**

Define supported deployment profiles:
- managed PostgreSQL shared cluster with tenant databases;
- self-managed PostgreSQL shared cluster;
- separate PostgreSQL cluster per tenant, if supported;
- on-premise customer-managed deployment.

For each profile specify identity provisioning, database ACL enforcement, secret storage, network boundary, role inspection, credential rotation, backup/restore and evidence collection. If a profile cannot provide required controls, it must be unsupported for cross-branch federation or use a separately approved compensating design.

**Acceptance evidence**

- Profile-specific threat model and deployment conformance test.
- No silent fallback to the global credential pattern in unsupported profiles.

### DBID-08 — Medium: Database and role names must remain non-authoritative routing metadata

**Issue**

The ADR says the source service derives its tenant identity from provisioned configuration and does not accept caller-controlled `db_name` or tenant ID. It should explicitly guard against a confused-deputy path where a compromised control-plane record, stale registry entry or mutable deployment variable causes a source workload to connect to a different tenant DB.

**Required resolution**

- Bind tenant identity, workload identity, DB credential reference and DB name in a signed/versioned provisioning record or equivalently protected configuration.
- Source service verifies this binding at startup and on configuration refresh.
- Destination cannot supply an override; control-plane changes require audited privileged approval and safe rollout.
- Credential/DB-name mismatch fails closed.
- Service identity and DB identity are checked together in health/readiness and audit evidence.

**Acceptance evidence**

- Tests mutate request tenant IDs, registry routing fields and secret references; source service cannot switch tenant DB.
- Mismatched config prevents readiness and protected source operations.
- Audit identifies the immutable source workload/tenant identity.

## 3. Recommended ADR amendments

Before the ADR is accepted, add:
1. A concrete PostgreSQL role/ownership/membership matrix, including PUBLIC CONNECT revocation and effective grants.
2. A credential lifecycle state machine with workload identity, bootstrap, rotation, revocation, pool disposal and outage behavior.
3. A provisioning state machine that prevents partially hardened tenant DBs from becoming available.
4. A source audit transaction/outbox contract.
5. A backup/restore quarantine and re-hardening contract.
6. A deployment profile support matrix, including on-premise constraints.
7. A tamper-resistant binding between source workload identity, tenant identity, DB name and secret reference.

The review does not require choosing a specific cloud secret manager or orchestration platform in this ADR. It does require defining the security properties and test evidence independent of vendor.

## 4. Disposition and stop conditions

PR #44 is a strong architecture proposal, but **not yet implementation-ready**. DBID-01 through DBID-05 are High and must be resolved before CAN-01 can be closed. DBID-06 through DBID-08 are Medium and must be addressed before the implementation design is approved for a production-capable deployment.

Required next gates:
- independent PostgreSQL/database owner review;
- application security review of role and secret boundaries;
- platform/operations review of workload identity, pools, rotation and provisioning;
- privacy/legal and clinical governance review of source disclosure and audit;
- formal D-01–D-14 decisions and implementation authorization;
- non-production synthetic-data isolation proof before any pilot request.

## 5. Evidence limitations

This review did not inspect production PostgreSQL catalogs, effective grants, role memberships, database owners, secret-manager policy or values, workload identity, runtime containers, network policies, backups or patient data. It therefore does not claim that a production role is superuser, that production is exposed, or that any cross-tenant data was accessed.

The findings identify missing design contracts and evidence required to demonstrate isolation. Actual exploitability remains unproven until deployed evidence is independently collected.

## 6. Explicit non-authorization

This review is documentation-only. It does not authorize:
- runtime implementation or refactoring;
- database/role/ACL changes or tenant provisioning;
- credential or secret-manager creation, retrieval, rotation or revocation;
- production patient-data access, import or export;
- partner onboarding, federation activation, emergency access or pilot;
- deployment, release or merge.

AUD-004 remains a release blocker. PR #44 should remain draft and unmerged pending resolution and independent review of the findings above.
