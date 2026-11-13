# AUD-004 PostgreSQL Least-Privilege Remediation Contract

**Status:** PROPOSED — design and review only; not approved for implementation
**Date:** 2026-11-13
**Architecture invariant:** PostgreSQL database-per-tenant. No schema-per-tenant conversion.
**Scope:** PostgreSQL role model, database/object ACLs, workload identity, credential lifecycle, provisioning/migration/backup boundaries, and required disposable-cluster evidence.

## 1. Purpose and non-goals

This contract defines the target PostgreSQL authorization model needed to make database-per-tenant an enforceable security boundary. Database names and control-plane routing metadata are selectors only; they are never authorization or credential material.

Non-goals: changing tenant storage topology; selecting a cloud secret manager or identity provider; choosing a production pooler/proxy; implementing SQL or application changes; approving federation activation; or authorizing production catalog inspection, credential provisioning, migration, deployment, or rollout.

## 2. Normative security invariants

1. Every tenant remains a separate PostgreSQL database. The control-plane database remains separate from every tenant database.
2. A tenant runtime login is bound to exactly one tenant database. Tenant A runtime cannot CONNECT to Tenant B or the control-plane database, even if application routing is manipulated.
3. Control-plane runtime can access only the control-plane database and cannot CONNECT to tenant clinical databases.
4. A source-disclosure workload is tenant-bound. Its database identity and configuration identify one source tenant; caller-supplied database names, DSNs, tenant overrides, SQL identifiers, or arbitrary engine selectors are forbidden.
5. A destination import workload has no foreign tenant database credential or direct foreign-database connection capability. Cross-tenant disclosure must be performed by the source-owned service.
6. Migration and provisioning privileges are unavailable to ordinary API, worker, HL7, onboarding, federation, and support runtime workloads.
7. Backup and restore are separate privileged operational capabilities with explicit database scope. No ordinary runtime receives backup credentials.
8. No login role is a superuser, has CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS, or inherits a broader role unless a separately approved, time-bounded operational exception explicitly requires it.
9. Effective privileges are evaluated across the whole PostgreSQL cluster, including PUBLIC, role memberships, database ACLs, object ACLs, ownership, default privileges, functions, extensions, and predefined roles. Reviewing role attributes alone is insufficient.
10. Missing identity, secret, policy, grant, audit, or network evidence fails closed. No fallback to a shared cluster credential is permitted.

## 3. Target identity classes

| Identity class | Scope and intended capability | Explicitly prohibited |
|---|---|---|
| `cp_owner` (NOLOGIN) | Own control-plane objects; schema/object ownership only | Login from an application container; tenant DB access |
| `cp_runtime` (LOGIN) | Control-plane DML required by the control-plane API | Tenant DB CONNECT; DDL; cluster administration |
| `tenant_<immutable-id>_owner` (NOLOGIN) | Own objects inside exactly one tenant database | Login; access to another database |
| `tenant_<immutable-id>_runtime` (LOGIN) | Minimum tenant-local DML required by that tenant's runtime | CONNECT to other tenant DBs or CP; DDL; cluster-wide reads |
| `tenant_<immutable-id>_source` (LOGIN, if separately needed) | Source-owned read/policy/audit operations inside exactly one tenant DB | Other tenant DBs; destination-selected tenant routing; broad write access |
| `migration_runner` (LOGIN, short-lived) | Execute approved migrations against an explicitly enumerated database set | Normal API use; persistent workload injection; CREATEDB/CREATEROLE; arbitrary cluster access |
| `provisioner` (LOGIN, short-lived) | Create/drop/assign tenant databases and grant approved roles under a controlled provisioning workflow | Patient-row access; ordinary runtime use; unbounded secret retrieval |
| `backup_<immutable-id>` (LOGIN, if per-tenant isolation is supported) | Read the explicitly assigned tenant database for backup | Cluster-wide `pg_read_all_data`; unrelated tenant/CP databases |
| `restore_operator` (LOGIN, short-lived) | Restore into an isolated/quarantined target under a separately approved DR workflow | Live tenant access before validation; general application use |
| `monitoring` (LOGIN) | Approved PostgreSQL statistics/health metadata | Patient table reads; `pg_read_all_data`; DDL or data mutation |

Names above are logical classes, not approved literal role names. Immutable tenant identity must not be derived solely from mutable branch codes or user-facing tenant names. The final naming and secret model requires DBA/security review.

## 4. Database and role authorization model

### 4.1 Database CONNECT policy

- Revoke `CONNECT` and `TEMPORARY` from `PUBLIC` on the control-plane database and every tenant database, after validating operational dependencies and owner/admin access.
- Explicitly grant `CONNECT` only to the database owner/required non-login owner chain and the exact runtime, source, migration, backup, restore, and monitoring identities approved for that database.
- Explicitly deny or omit every cross-tenant grant. A tenant A identity must not inherit tenant B access through `PUBLIC`, `pg_read_all_data`, membership, `SET ROLE`, or another role.
- Apply the same policy to template databases and any auxiliary database that could expose tenant data. Inventory the maintenance database separately; do not assume its default ACL is harmless.
- Treat `pg_hba.conf`, network security groups, service mesh, pooler routing and secret-manager policy as defense in depth, not substitutes for database ACL enforcement.

### 4.2 Object ownership and grants

- Use non-login owner roles for database/schema/object ownership. Runtime logins must not own schemas, tables, sequences, functions, extensions, or databases.
- Runtime DML grants must be explicit and database-local. Grant only the required table/sequence/function privileges; do not use blanket grants to all future objects without a controlled owner/default-privilege policy.
- Set default privileges for the actual migration/owner role in each database. Default privileges are creator-role- and database-specific; executing `ALTER DEFAULT PRIVILEGES` in the maintenance database does not configure tenant databases.
- Revoke PUBLIC EXECUTE on sensitive functions where appropriate; inventory SECURITY DEFINER functions, ownership, search_path, extension functions, and any function that can cross an authorization boundary.
- Migration ownership transfer and grants must be deterministic for both existing and newly created tenant databases.

### 4.3 Membership and role switching

- Runtime logins must not be members of provisioning, migration, owner, backup, or cluster-wide predefined roles.
- Do not grant a runtime role membership that permits `SET ROLE` into a more privileged identity.
- Any membership used by a controlled operational runner must be explicit, narrowly scoped, non-inheriting where appropriate, audited, and removed/revoked after the task.
- `pg_read_all_data` is not an acceptable default backup role for a multi-tenant cluster because it crosses database boundaries. Any exception requires a separately approved threat model and proof that the cluster-level scope is intended.

## 5. Workload-to-identity mapping

| Workload | Required identity | Required database access |
|---|---|---|
| Control-plane API | `cp_runtime` | Control-plane DB only |
| Tenant API / tenant worker | Tenant-specific runtime identity | Its own tenant DB only |
| Source federation service | Tenant-specific source identity | Its own tenant DB only; source-owned authorization and audit |
| Destination federation/import service | Destination tenant runtime identity | Destination DB only; no source DB session |
| HL7 listener | Tenant-specific identity or narrowly scoped integration identity | Only assigned tenant DB(s); exact integration grants |
| Onboarding portal | Separate onboarding identity or CP-only identity | No tenant clinical DB access unless explicitly justified and isolated |
| Migration runner | Short-lived migration identity | Only the approved database set for that migration window |
| Provisioning service | Short-lived provisioning identity | Database/role administration only; no patient data reads |
| Backup agent | Per-tenant backup identity or equivalently isolated backup execution boundary | Explicitly assigned database(s) only |
| Restore operator | Short-lived restore identity | Quarantined target only until verification and approval |
| Monitoring/exporter | Monitoring identity | Statistics/health only; no clinical table reads |

A process that serves multiple tenants must not be given a bundle of all tenant passwords. Prefer tenant-isolated processes or an independently authenticated broker that issues only the current tenant's narrowly scoped credential. A generic engine registry accepting an arbitrary database name is not an authorization mechanism.

## 6. Credential and lifecycle requirements

- Provision credentials through an approved secret manager or workload identity mechanism; never embed passwords in SQL, images, source control, Compose files, logs, or test fixtures beyond synthetic CI-only credentials.
- The bootstrap identity is separate from application identities, used only for initial cluster/database setup, and unavailable to steady-state services.
- Provisioning creates the database, assigns non-login ownership, creates or binds the tenant-specific runtime/source identities, applies grants/default privileges, and verifies negative access before marking the tenant ready.
- Migration credentials are issued just in time for a named migration run, restricted to a declared database set, rotated/revoked after use, and never mounted into ordinary runtime containers.
- Rotation must support overlap only for a bounded period, update secret references atomically, drain/recreate connection pools, verify new authentication, then revoke the old credential. Revocation must invalidate or drain already authenticated pooled sessions.
- Tenant deactivation, credential compromise, offboarding, and tenant database restore each have explicit credential revocation and pool invalidation procedures.
- Secret retrieval authorization must bind workload identity, environment, tenant immutable ID, purpose, and allowed database. A caller-provided tenant ID alone is insufficient.

## 7. Provisioning and migration transaction boundaries

Provisioning is a privileged control-plane operation, not an API side effect performed with the normal runtime login. It must be idempotent, auditable, and restart-safe.

Required sequence (design target):
1. Authenticate the provisioning workload and authorize the requested tenant lifecycle transition.
2. Allocate an immutable tenant identity and bind it to one database record; reject name/branch-code reuse as identity continuity.
3. Create the tenant database using the isolated provisioning capability.
4. Create/verify non-login owner and tenant-scoped runtime/source roles; reconcile existing role attributes rather than relying only on `IF NOT EXISTS`.
5. Revoke unintended PUBLIC database privileges and apply explicit CONNECT policy.
6. Apply schema/object ownership, grants and creator-specific default privileges in the tenant database.
7. Run migrations with the short-lived migration identity; do not use the runtime login as migration owner.
8. Verify role attributes, memberships, database ACLs, ownership, object grants, default privileges and cross-database denials.
9. Publish the tenant as ready only after all verification succeeds; otherwise leave it quarantined and prevent application routing.

Existing tenant migration must be staged: inventory and classify current owners/grants, produce a per-database plan, test on disposable clones, verify rollback/forward-repair strategy, then migrate one non-production tenant at a time. Do not bulk alter production ownership or ACLs based on this proposal.

## 8. Backup and restore boundary

- Remove cluster-wide `pg_read_all_data` from the default backup design. Prefer per-tenant backup credentials or an isolated backup agent that receives one tenant-scoped credential at a time.
- Backup must not receive the application runtime password, provisioning login, or migration login.
- Backup artifacts must be tenant-bound, encrypted, integrity-verified, and stored outside the runtime's writable trust boundary. Backup metadata must not reveal patient data.
- Restore must target a new isolated/quarantined database, verify artifact ownership, integrity, tenant identity and migration compatibility, and only then request a separately approved cutover.
- Backup/restore authorization, retention, legal hold, off-host replication, deletion and evidence retention require a separate DR owner decision. This contract does not claim those controls currently exist.

## 9. Mandatory disposable PostgreSQL proof

Acceptance must use a fresh supported PostgreSQL cluster with at least control-plane, tenant A, and tenant B databases, independent login roles, independent sessions, and actual connection attempts. SQLite, mocked permission checks, or in-process mutexes are not sufficient.

### 9.1 Positive access matrix

| Identity | CP DB | Tenant A DB | Tenant B DB |
|---|---:|---:|---:|
| `cp_runtime` | Allow | Deny | Deny |
| `tenant_A_runtime` | Deny | Allow | Deny |
| `tenant_B_runtime` | Deny | Deny | Allow |
| `tenant_A_source` | Deny | Allow | Deny |
| `tenant_B_source` | Deny | Deny | Allow |
| `migration_runner` | Allow only when explicitly included in run scope | Allow only when explicitly included | Allow only when explicitly included |
| `provisioner` | No clinical row access; database administration only | No clinical row access; lifecycle only | No clinical row access; lifecycle only |
| `backup_A` | Deny | Read only | Deny |
| `backup_B` | Deny | Deny | Read only |
| `monitoring` | Statistics only if approved | Statistics only if approved | Statistics only if approved |

Each matrix cell must be tested with real PostgreSQL authentication and SQL, not inferred from role definitions. For migration/provisioning/monitoring, test both allowed operations and forbidden data access.

### 9.2 Catalog and adversarial assertions

Capture before/after snapshots of:
- role attributes (`rolsuper`, `rolcreatedb`, `rolcreaterole`, `rolreplication`, `rolbypassrls`, `rolinherit`, login status);
- role memberships and grant options, including predefined roles;
- `pg_database.datacl`, PUBLIC CONNECT/TEMP, database owners and connection limits;
- schema/table/sequence/function ACLs, object owners, default privileges, SECURITY DEFINER functions and search paths;
- database creation/ownership and template database ACLs;
- effective privilege probes using independent logins, not just catalog interpretation.

Adversarial cases must include:
- fresh bootstrap and idempotent rerun;
- pre-existing unsafe roles (bootstrap must detect/fail or safely reconcile under an approved policy);
- accidental PUBLIC CONNECT/TEMP and inherited role grants;
- tenant A to tenant B and CP, tenant B to tenant A and CP, CP to both tenant DBs;
- attempts to `SET ROLE`, read via `pg_read_all_data`, use privileged functions, create objects, alter grants, and access sequences;
- missing/expired/revoked secrets and already-open pooled connections;
- tenant creation, migration, backup and restore workflows, including partial failure and retry;
- a role or database name collision and tenant immutable-ID mismatch.

### 9.3 Evidence and independent oracle

CI evidence must include exact commit, PostgreSQL major/minor image, image digest, SQL/bootstrap revision, sanitized catalog snapshots, command results, and positive/negative connection attempts. The test harness must use only disposable synthetic databases and CI-only credentials.

At least one independent verifier must compute effective privileges separately from the bootstrap code under test. The bootstrap must not be its own sole oracle. A passing characterization test that reproduces a vulnerability is not acceptance evidence.

## 10. Rollout gates

1. DBA and application-security owners approve the final identity and ACL matrix.
2. Supported deployment modes (single-host, managed PostgreSQL, pooler/proxy, cloud/on-prem) and their credential/identity behavior are documented.
3. A complete inventory exists for every database, role, membership, object owner, grant, secret consumer, connection path and service workload.
4. A forward-only, restart-safe migration and recovery plan is reviewed, including rollback/forward-repair limits and connection-pool invalidation.
5. Disposable PostgreSQL positive/negative tests pass for bootstrap, provisioning, migration, runtime, source, backup and restore identities.
6. Actual Compose/service wiring is tested with isolated synthetic secrets; each service receives only its declared identity.
7. Network and secret-manager evidence independently confirms there is no shared credential or alternate cross-tenant path.
8. Independent security review signs off the exact implementation commit and evidence package.
9. Federation remains disabled until the separate source-owned protocol, clinician trust, clinical/privacy governance and all AUD-004 gates are approved.

## 11. Current findings this contract is intended to close

This design responds to repository evidence that the current role bootstrap creates nominal `hms_app`, `hms_migrator`, `hms_backup`, and `hms_exporter` roles but does not wire them into application, migration, provisioning, or backup connection paths; the SQL grants only against the literal `postgres` database; `hms_backup` receives cluster-wide `pg_read_all_data`; role creation does not reconcile pre-existing unsafe attributes; and PostgreSQL default PUBLIC CONNECT permits access unless revoked/scoped.

The disposable PR #71 characterization proof passed on 2026-11-13, but it intentionally demonstrates current gaps. It is not evidence that this proposed target model is implemented.

## 12. Decisions still required

- Confirm whether tenant runtime and source-disclosure identities are separate logins or one tenant-bound login with independently enforced service boundary.
- Select immutable tenant identity representation and role/secret naming convention.
- Decide backup granularity and whether a single isolated backup broker is acceptable versus per-tenant backup logins.
- Define the exact provisioning identity capability and whether it is PostgreSQL-native, cloud control-plane, or broker-mediated.
- Select supported PostgreSQL versions, managed/on-prem profiles, pooler mode and authentication mechanism.
- Approve rotation, revocation, emergency operations, audit retention and DR procedures.

Until those decisions and independent reviews are complete, this contract remains proposed. No SQL, runtime, migrations, Compose, secrets, live databases, patient data, federation activation or deployment has been changed or authorized.

## 13. Repository-grounded workload-to-database implementation map (2026-11-13)

**Evidence boundary:** static inspection of `main` at the paths/revisions listed below, compared with the proposed contract. This is not deployed-environment evidence and does not prove the effective privileges of a live PostgreSQL cluster. It is a remediation map, not authorization to change code or deployment.

### 13.1 Current connection construction

| Code path | Current behavior observed | Required target change |
|---|---|---|
| `backend/core/config.py::Settings.DATABASE_URL` | Builds one PostgreSQL URL from `POSTGRES_USER`, `POSTGRES_PASSWORD`, host/port and `POSTGRES_DB`. | Replace the single shared login assumption with explicit CP, tenant-bound runtime, migration, provisioning and backup credential sources. No fallback to the legacy shared login in production. |
| `backend/core/database.py::build_db_url(db_name)` | Changes only the database component of `settings.DATABASE_URL`; username/password remain unchanged. | Database selection must be paired with an independently authorized identity. The function must not turn a caller-controlled database name into cross-tenant authority. |
| `backend/core/database.py::control_engine` / `ControlSessionLocal` | Control-plane engine is created from `build_db_url(CONTROL_PLANE_DB_NAME)`, therefore uses the same configured username/password as tenant engines. | CP runtime identity must be CP-only and must not be accepted by tenant databases. |
| `backend/core/database.py::TenantEngineRegistry.get_engine(db_name)` | Accepts a database name, constructs an engine from the shared URL and caches it by database name. | Remove arbitrary database-name access as an authorization primitive. Bind tenant context to an authenticated immutable tenant identity and a tenant-scoped credential capability; reject unapproved DB/tenant pairs before connection creation. |
| `backend/core/database.py::ensure_postgres_db_exists(db_name)` | Builds a connection to `postgres` using the same configured URL and can create a database. | Move database creation to a separate short-lived provisioning capability; ordinary API/tenant code must not hold this privilege. |

### 13.2 Production Compose service map

| Compose service | Current PostgreSQL exposure evidenced in `docker-compose.prod.yml` | Required target identity / disposition |
|---|---|---|
| `db` | Receives `.env.production`; initializes the PostgreSQL container using the configured POSTGRES variables. | Treat initialization/bootstrap superuser as an infrastructure-only secret; never expose it to application services. |
| `db-init` | Receives the full `.env.production`; runs `python backend/scripts/bootstrap.py --apply-roles`. | Split into explicitly authorized provisioning/bootstrap and migration phases. Do not pass the full environment to an ordinary runtime. Current command continues into CP migration, seed and tenant validation; it is not role-SQL-only. |
| `api` | Receives full `.env.production`; serves tenant API and uses both CP and tenant session paths in the shared backend process. | Requires a reviewed broker/tenant-isolation design: CP access should be narrowly mediated; tenant DB sessions must be tenant-bound and cannot use one fleet-wide login. A single multi-tenant API process with one login cannot satisfy the per-tenant DB credential matrix without a separately enforced credential broker/process boundary. |
| `worker` | Receives full `.env.production`; shares the backend package and backup volume mount. | Inventory each job's data scope. Split tenant work into tenant-bound execution contexts; give each job only the required tenant credential. Backup must be a separate workload/identity, not inherited from generic worker configuration. |
| `hl7-listener` | Receives full `.env.production`; connects to PostgreSQL through shared settings; profile-gated as `integrations`. | Integration identity must be tenant-scoped to assigned interface/tenant and must not have CP/provisioning/migration or other-tenant access. |
| `onboarding-portal` | Receives full `.env.production`; runs `backend.control_plane.app:app`, but current config still defines the shared `DATABASE_URL`. | CP-only runtime identity. It must not receive tenant DB credentials, patient-data access or the provisioning superuser credential. Provisioning should call a separate narrowly scoped capability. |
| `postgres-exporter` | `DATA_SOURCE_NAME` explicitly uses `POSTGRES_USER` / `POSTGRES_PASSWORD` and connects to `POSTGRES_DB`. | Dedicated monitoring identity with only approved statistics/health access; no shared application login and no clinical table read. Confirm exporter collector requirements before finalizing grants. |
| `prometheus`, `alertmanager`, `redis-exporter`, `node-exporter`, `hospital-ui`, `reverse-proxy`, `docker-proxy`, `clamav` | No direct PostgreSQL credentials are shown in their service definitions (other than exporter separately listed). | Keep DB credentials absent. Validate indirect access only through intended API/network paths. |
| Backup daemon / vault worker | No dedicated backup service is present in the inspected production Compose service list; backup implementation exists in `backend/scripts/backup_service.py`. | Decide and document the actual execution host/service. It must have a separate backup identity, no app or provisioning credential, no shared writable runtime trust boundary, and per-database scope. Do not assume a separate backup service exists because the code module exists. |

### 13.3 Privileged operational paths

- `backend/scripts/bootstrap.py::provision_physical_databases()` connects to the `postgres` maintenance database using the shared `POSTGRES_USER`/`POSTGRES_PASSWORD` and creates CP/default-tenant databases. `apply_database_roles()` uses that same identity. `bootstrap_system()` then upgrades CP, seeds CP, may migrate/seed a tenant and validates active cloud tenant URLs. This is a combined privileged startup path, not a separated provisioning/migration identity.
- `backend/control_plane/api/routers/provisioning.py` creates tenant DBs via `ensure_postgres_db_exists`, builds a tenant URL, runs `upgrade_tenant_database_url`, and creates a tenant engine from the shared configuration. Provisioning therefore combines database creation, migration and tenant initialization in the control-plane application path.
- `backend/scripts/migrate.py` accepts a database URL and creates SQLAlchemy engines from it for Alembic/schema operations. Migration privilege is inherited from the supplied URL; the reviewed configuration does not inject a distinct migration identity.
- `backend/scripts/backup_service.py::_dump_and_encrypt()` invokes `pg_dump` using `settings.POSTGRES_USER` and `settings.POSTGRES_PASSWORD` for the selected `db_name`. `run_backup_cycle()` reads active CLOUD tenants from the CP database and iterates their database names. The database selector is not matched to a per-tenant PostgreSQL credential.
- `backend/scripts/restore_tenant.py::restore_encrypted_backup()` calls `ensure_postgres_db_exists(target_db_name)` and runs `pg_restore` using the shared configured login. It can also promote a registry entry to CLOUD. Restore is therefore not an isolated, quarantined-target-only capability in the inspected path.

### 13.4 Priority gaps and dependencies

1. **P0 — Identity architecture before code:** a single API process currently accesses CP plus arbitrary tenant DBs through shared credentials. A tenant-scoped database login per tenant cannot be safely selected by a plain `db_name` argument. Decide whether to isolate tenant execution into tenant-bound processes, use a broker that authorizes and issues narrowly scoped short-lived credentials, or adopt another independently enforceable boundary. A broker must not become a fleet-wide credential oracle.
2. **P0 — Remove shared superuser/owner exposure:** separate infrastructure bootstrap, provisioning, migration and runtime capabilities. Ensure the full `.env.production` is no longer mounted into every service.
3. **P0 — Provisioning lifecycle:** move DB creation, owner assignment, tenant runtime credential creation, grants and verification out of the normal control-plane request process, or isolate behind a separately authenticated and audited provisioning service.
4. **P0 — Federation source boundary:** source reads must execute inside a source-owned tenant workload/identity. Destination API/import workers must never use the tenant engine registry to connect to a foreign tenant database.
5. **P0 — Backup/restore:** define actual service placement, per-tenant credential issuance, artifact isolation, restore quarantine, integrity/ownership verification and cutover approval before wiring new DB roles.
6. **P1 — Monitoring:** replace the exporter shared credential with a dedicated monitoring identity and test the exact exporter collectors against minimum grants.
7. **P1 — Connection lifecycle:** design tenant credential rotation/revocation against SQLAlchemy engine caching, process workers, `NullPool`, long-lived sessions and already authenticated PostgreSQL sessions. Revoking a password alone does not terminate existing sessions.

### 13.5 Required follow-up inventory before implementation

- Exhaustively enumerate every `create_engine`, `psycopg2.connect`, `asyncpg`/driver connection, `pg_dump`, `pg_restore`, raw SQL connection and `DATABASE_URL` consumer across backend, scripts, worker tasks, integrations, tests and deployment manifests.
- Map each endpoint, background job, CLI, migration command, restore path, federation path and support/admin operation to the exact database set and minimum SQL operations it needs.
- Confirm whether API process boundaries can be split without breaking request routing, transactions, cross-domain workflows and background jobs. If not, specify the credential broker threat model and prove it cannot mint credentials for an untrusted caller-selected tenant.
- Inspect actual `pg_hba.conf`, role memberships, `PUBLIC` ACLs, DB/object owners, predefined-role memberships, secret mounts, Docker networks, runtime process environment and live service connections only in an approved isolated deployment test. No such live inspection is claimed here.
- Add negative tests at the real service boundary: tenant A request/job cannot obtain or use tenant B credentials; onboarding cannot connect to clinical DBs; exporter cannot read patient tables; backup A cannot read tenant B or CP; restore cannot promote an unverified target.

### 13.6 Static source references

| Repository path | Inspected revision on `main` |
|---|---|
| `docker-compose.prod.yml` | `bfce52948c508e137875a0be2af09ae11178e78` |
| `backend/core/config.py` | `6c00f90f66f28402c0afa03b669aebff6225ceb7` |
| `backend/core/database.py` | `043f4ccbdad4d2bfe4c89af0b46988ce60610b01` |
| `backend/control_plane/api/routers/provisioning.py` | `40bb98fc9f79fb700b8b9484688d818c3ef1c441` |
| `backend/scripts/migrate.py` | `5ebc4364c127afdebaea187a74df5d0b9e78984b` |
| `backend/scripts/backup_service.py` | `8ad90420fb4c2f487ed3c6318f657411e3b9cfa8` |
| `backend/scripts/restore_tenant.py` | `33598657b29ae4e24f136d079543e02dc91098e6` |
| `backend/scripts/bootstrap.py` | `418a6f6641c17f2bc17b22f4bc09371ae9857bfd` |

This map is bounded by the files listed. It is not an exhaustive proof that no other database connection path exists. The complete connection-consumer inventory in Section 13.5 is still required.

**Disposition:** repository evidence demonstrates that role separation requires application architecture and deployment changes, not just replacement SQL. The next implementation proposal must first resolve the single-process multi-tenant credential boundary. No code, SQL, migration, Compose, secret, database or production setting was changed by this audit.