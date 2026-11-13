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

### 13.3.1 Backup-sidecar and vault deployment distinction

A separate review of `docker-compose.yml` at commit `20b8a5e48518c81820a7e28494fd73aeda33b46f` identifies `backup-sidecar` (runs `backend/scripts/backup_service.py --daemon`) and `backup-vault` (runs the same script in `--vault-mode`). Both load `.env`. The sidecar is a database-reading backup workload; the vault is a file-copy/sealing workload and should not receive database credentials.

That development Compose file mounts the same read-write `hms_backups` volume into `api`, `worker`, `onboarding-portal` and `backup-sidecar`; `backup-vault` sees it at `/source:ro` and writes to a separate vault volume. This creates a shared artifact-tampering boundary for the read-write mounts. The read-only vault source mount is a positive control, but chmod-based read-only files are not proof of storage-level WORM protection.

The inspected `docker-compose.prod.yml` does not declare either backup service. This is a deployment-profile gap to resolve: do not assume the development backup-sidecar/vault pair is the production backup execution path. Identify the actual production scheduler/container/host and prove its environment, mounts, network and credentials independently. The absence from this one manifest does not establish that no production backup process exists.

Required target: backup-sidecar receives only the intended backup credential and tenant-scoped backup key capability; vault receives no PostgreSQL, CP, tenant, or encryption-key credentials and only read-only artifact input plus write-only/append-only vault output as supported by the storage platform. API/worker/onboarding must not have write access to sealed artifacts or trusted ownership metadata. Test read/write/delete attempts across all service identities and verify effective volume permissions and storage-level retention controls.
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
## 14. Additional connection-consumer and privileged-path cross-check (2026-11-13)

**Scope:** targeted static inspection of the queue, worker, integration listener, fleet operations, control-plane migration routes, restore drill and host backup/restore scripts on `main`. This supplements Section 13; it does not claim a repository-wide proof that every database access has been found.

### 14.1 Additional runtime and background access paths

| Path | Current access evidenced | Required identity boundary |
|---|---|---|
| `backend/core/queue.py` | Queue processing opens `ControlSessionLocal` and obtains tenant engines from `tenant_engine_pool` for job execution (`:352-361`, `:428-431`). | A queued `db_name` is routing data only. Authenticate the job's tenant binding, authorize it against immutable tenant identity, and execute with a tenant-bound capability; never let a payload choose an arbitrary database. |
| `backend/domains/integrations/listener.py` | HL7 listener reads control-plane metadata and obtains a tenant engine from `tenant_engine_pool` (`:12`, `:68`, `:137`). | Integration credentials must be scoped to the assigned tenant and interface; listener must not inherit a fleet-wide tenant login. Validate tenant/interface binding before opening a session. |
| `backend/control_plane/api/routers/fleet_ops.py` | Fleet operations obtains tenant engines at multiple paths (`:132`, `:343`, `:382`, `:494`, `:780`, `:844`, `:862`, `:998`, `:1050`, `:1252`); one path builds a tenant URL and invokes migration (`:864-865`). | Split read-only fleet observation from tenant mutation/migration. Each operation must declare tenant scope and minimum privileges; fleet control-plane identity must not itself imply unrestricted clinical DB access. Privileged migration is delegated to a separate runner. |
| `backend/control_plane/api/routers/migration.py` | Control-plane migration routes obtain tenant engines directly (`:483`, `:554`) and maintain CP sessions (`:21`, `:531`). | The control-plane web process must enqueue an approved migration request, not hold tenant DDL credentials. A separately authenticated migration runner validates immutable tenant identity and approved version/operation. |
| `backend/control_plane/app.py` | Control-plane app imports and disposes the shared tenant engine registry (`:34`, `:62`) in addition to using CP sessions. | Onboarding/control-plane runtime should not be able to instantiate arbitrary tenant engines. Remove tenant registry access from this process or place the operation behind an independently enforced broker/worker boundary. |
| `backend/scripts/build_indexes_concurrently.py` | CLI accepts a database URL and creates engines; it also reads CP URL and tenant URLs from registry (`:209-239`). | Treat as a privileged maintenance CLI. Require explicit allowlisted tenant scope, short-lived migration/maintenance identity, operator authorization and auditable per-database execution. Do not accept an untrusted arbitrary URL. |
| `backend/scripts/restore_drill.py` | Restore drill constructs administrative and target engines, runs `pg_restore`, and reads CP registry (`:142`, `:162-176`, `:203`, `:260`, `:307`). | Isolate in a DR-only environment with a dedicated restore capability and quarantined target. Never expose admin credentials to API/worker; verify artifact, target ownership and restore result before any registry cutover. |

### 14.2 Host-level PostgreSQL backup and restore scripts

- `deployments/backup-postgres.sh` connects inside the PostgreSQL container using `POSTGRES_USER`/`POSTGRES_PASSWORD` for database inventory, `pg_dump` and `pg_dumpall --globals-only` (`:79`, `:130`, `:139`). This is effectively an infrastructure/cluster backup path, not a tenant-scoped `backup_service.py` path. Its global-role dump is especially privileged and must be isolated from application credentials. The target design needs a separately approved cluster-global backup identity/process plus per-database data backup scope, or an explicitly reviewed equivalent.
- `deployments/restore-postgres.sh` uses the same configured PostgreSQL login to check target existence, create the target database owned by `POSTGRES_USER`, and run `pg_restore` (`:66`, `:72`, `:74-75`). It therefore restores as the configured owner/superuser-equivalent identity rather than a narrowly scoped restore capability. Keep it out of normal application service environments; require a new quarantined target and a separate reviewed cutover.
- These host scripts are additional to `backend/scripts/backup_service.py` and `backend/scripts/restore_tenant.py`; they must not be collapsed into one assumed execution model. Their actual scheduler, host access, environment source, mounted backup paths and operator privileges remain deployment evidence to collect.

### 14.3 Expanded privilege-boundary findings

1. The shared `tenant_engine_pool` is reachable from queue processing, the HL7 listener, fleet operations and the control-plane app/routes, not only the primary API request path. A role split cannot be completed by changing `Settings.DATABASE_URL` alone.
2. Migration execution has at least three surfaces: bootstrap/migrate scripts, control-plane migration/fleet routes, and the concurrent-index maintenance CLI. All must be routed through one governed migration capability or explicitly separated profiles.
3. Backup/restore has at least four distinct code/ops surfaces: `backup_service.py`, `restore_tenant.py`, `restore_drill.py`, and host-level `backup-postgres.sh` / `restore-postgres.sh`. Their credential and artifact boundaries differ and need separate tests.
4. The queue is a security boundary: tenant identifiers in queued messages must be treated as untrusted selectors until checked against a signed/server-owned job record. A background worker with unrestricted registry access is still a cross-tenant credential path.
5. The current `worker.py` entry point itself contains no direct SQL connection call in the inspected file; the relevant access is delegated to `core.queue` and task modules. This does not imply that worker execution is database-free.

### 14.4 Additional static source references

| Repository path | Inspected `main` blob SHA |
|---|---|
| `backend/core/queue.py` | `aad0c663e52e7a73d7261658f5ecc1889b7e36b7` |
| `backend/domains/integrations/listener.py` | `3b3a72669f7b2746785ea874a728f145af607067` |
| `backend/control_plane/api/routers/fleet_ops.py` | `b286c202182e9af9b2ea5ed485d66889bf7409d9` |
| `backend/control_plane/api/routers/migration.py` | `d0660422e781ff913788d31664be69191fc269e0` |
| `backend/control_plane/app.py` | `cae7f78718cbf5356f9766361f91ab2fb4362322` |
| `backend/scripts/build_indexes_concurrently.py` | `6ac8804343a81407d724110882a733f09d87d7e2` |
| `backend/scripts/restore_drill.py` | `85c0fdf555f24ee87aab7bcab70671b2195a44bf` |
| `deployments/backup-postgres.sh` | `a66b9d45362b2e393bc50cddc1aa20eb2b053d95` |
| `deployments/restore-postgres.sh` | `0c21ae21b3630b1c0570b9012b44b9bd19041982` |
| `docker-compose.yml` | `0faced7760516a84ec096f49ea84ec1c5a8d65bc` |

**Disposition:** the additional paths strengthen the finding that CP web processes and generic workers currently reach tenant databases through a shared engine registry, while maintenance and host backup/restore scripts use broadly privileged configured credentials. The inventory remains static and bounded; the next step is a path-by-path source audit of every tenant-engine call site and task payload, followed by isolated PostgreSQL tests. No code, SQL, migration, Compose, secret, database, patient data or production setting was changed.
## 15. Tenant-engine call-site classification (2026-11-13)

**Method:** searched the inspected backend Python source on `main` for `tenant_engine_pool.get_engine()` and reviewed surrounding code at each match in the core request dependency, queue handlers, HL7 listener, fleet operations, migration routes and federation router. This is a call-site classification, not a claim that every indirect SQL connection or dynamic URL consumer has been exhausted.

### 15.1 Call-site inventory and disposition

| Source / call site | Operation evidenced | Security classification and required disposition |
|---|---|---|
| `backend/core/database.py:260` (`get_db`) | Resolves request tenant context, then opens the tenant DB session and stamps trusted branch/subdomain metadata on the session. | **Required tenant runtime path.** Keep only if the API process has a capability bound to the authenticated/resolved tenant. A generic process-wide fleet credential defeats DB-per-tenant isolation. Prove host/header/subdomain spoofing cannot change the binding. |
| `backend/core/queue.py:361` (`privacy.retention.execute`) | Resolves active tenant from CP using `tenant_subdomain`, then reads approved retention revision and may execute retention. | **Tenant-bound background execution.** Job must carry immutable tenant ID plus server-issued operation authorization; resolve current DB name from CP at execution, re-check active status, approval, actor separation and production guard. No arbitrary DB name in payload. |
| `backend/core/queue.py:431` (`privacy.retention.scheduled_daily_sweep`) | Iterates every active tenant, reads approved policy revisions and enqueues work. | **Fleet scheduler, not tenant runtime.** Split into CP-only scheduler plus tenant-scoped read/execute jobs. The scheduler must not query every clinical DB with one fleet credential. |
| `backend/domains/integrations/listener.py:137` (`process_and_route_result`) | Maps HL7 MSH-4 facility to tenant DB and writes ORU result. | **Tenant-bound integration ingress.** Resolve facility from trusted CP mapping after validating interface secret; dispatch to a tenant-bound processor. A listener receiving arbitrary tenant DB names must not directly select a credential. |
| `backend/control_plane/api/routers/fleet_ops.py:132` | Fleet dashboard aggregates patient, bed and revenue counts across tenants. | **Cross-tenant PHI/financial aggregation.** Prefer tenant-generated minimal aggregate telemetry or a dedicated read-only reporting path; do not grant CP web runtime broad clinical table access by default. |
| `backend/control_plane/api/routers/fleet_ops.py:343` | Federation key rotation attempts to synchronize the new key into tenant `FederatedClient`. | **Privileged tenant mutation.** Move to a tenant-bound key-rotation command with audited operation ID; do not let general CP runtime write tenant DBs. |
| `backend/control_plane/api/routers/fleet_ops.py:382` | Emergency tenant admin password reset, invalidates sessions/tokens and changes credentials. | **Break-glass privileged mutation.** Isolate behind separately authorized, time-bound support workflow and tenant-bound executor; require strong approval/audit and safe one-time secret delivery. Not a general CP runtime privilege. |
| `backend/control_plane/api/routers/fleet_ops.py:494` | Tenant telemetry endpoint opens tenant DB for operational data. | **Read-only tenant telemetry.** Use narrowly defined views/aggregate output or tenant-side reporting agent; avoid general ORM access from CP process. |
| `backend/control_plane/api/routers/fleet_ops.py:780` | Creates a sandbox DB using PostgreSQL `CREATE DATABASE ... WITH TEMPLATE` after terminating source DB connections. | **Infrastructure/provisioning privilege.** Must be a separate provisioning workflow/identity with explicit source/target allowlists, isolation checks and approval. Never expose database-owner/createdb capability to the CP web role. |
| `backend/control_plane/api/routers/fleet_ops.py:844` | Reads tenant Alembic version for fleet schema parity. | **Read-only schema metadata.** Delegate to a tenant-bound probe or grant only required catalog/version-table read; no application-table access needed. |
| `backend/control_plane/api/routers/fleet_ops.py:862` | Tenant sync obtains tenant engine, runs Alembic upgrade and seeds universal tenant data. | **Migration plus privileged tenant initialization.** Move DDL to migration runner and seeding to a separately scoped initialization operation. The CP endpoint should submit/monitor a durable job only. |
| `backend/control_plane/api/routers/fleet_ops.py:998` | Reads tenant policy to enrich tenant telemetry/details. | **Read-only policy projection.** Prefer a CP-maintained approved projection or narrow tenant-side read capability. |
| `backend/control_plane/api/routers/fleet_ops.py:1050` | Reads tenant federation sharing policy for network topology. | **Federation authorization metadata.** Prefer CP-authoritative policy projection; do not make CP topology route a direct clinical DB reader. |
| `backend/control_plane/api/routers/fleet_ops.py:1252` | Fleet summary reads patient, bed, invoice and user login metrics from each tenant. | **Cross-tenant PHI/financial aggregation.** Replace with minimized, purpose-limited aggregates produced within each tenant boundary; explicitly classify which metrics may leave tenant DB. |
| `backend/control_plane/api/routers/migration.py:483` | CSV migration preview reads existing values from target tenant to identify duplicates. | **Tenant-scoped import preview.** Preview must run in tenant-bound import worker; upload validation and mapping may remain CP-side without tenant DB credentials. |
| `backend/control_plane/api/routers/migration.py:554` | Background bulk CSV migration writes rows into target tenant DB. | **Tenant-scoped data mutation.** Worker must use a server-authorized tenant binding and an import operation record; do not pass unchecked `tenant_db_name` as authority. |
| `backend/domains/federation/router.py:347` | Federation discovery reads branch patient data after resolving pointers and branch registries. | **Source-owned federation read.** Critical boundary: do not connect to a foreign tenant DB using destination/API fleet credentials. Dispatch a request to the source tenant's own authorized federation service, which applies source policy locally and returns only permitted data. |
| `backend/domains/federation/router.py:572` | Patient import reads source tenant policy and source patient data before importing to destination. | **Source-owned federation read plus destination-owned write.** Source retrieval must execute under source authorization; destination import runs under destination identity. Never combine both sides under a single fleet-wide tenant credential. |

### 15.2 Architectural consequences

1. **The current shared registry is a capability amplifier.** Any process importing it can select a tenant DB by name. `db_name` is an identifier, not an authorization token. Access must be enforced by a process boundary or broker that binds the authenticated workload and operation to an immutable tenant identity.
2. **One generic tenant runtime role is insufficient if shared across all tenant databases.** Even if each database has its own login, a process able to retrieve every tenant password remains a fleet-wide credential oracle. Prefer tenant-bound execution contexts/workers with isolated secret access; if a broker is selected, document caller authentication, allowed operation, tenant binding, credential TTL, replay resistance, revocation, audit and protection against caller-selected tenant IDs.
3. **Control-plane web runtime should become CP-only.** Dashboard aggregation, telemetry, policy reads, password reset, key rotation, schema sync, CSV import and federation source reads should become separate projections or delegated jobs with distinct authorization and identities.
4. **Federation must be source-owned.** Discovery and import source reads cannot be secured merely by checking a CP pointer and then connecting directly to the source DB. The source workload must revalidate current source policy and purpose before releasing data.
5. **Privilege tiers must distinguish operations, not just services:** CP metadata CRUD; tenant clinical runtime; tenant read-only telemetry; tenant import writer; federation source read; tenant migration/DDL; tenant provisioning/clone; break-glass support; cluster backup/restore; monitoring/exporter.

### 15.3 Required acceptance tests before implementation

- For each endpoint/job above, assert the workload can connect only to its authorized database set; tenant A capability cannot connect to tenant B or CP unless explicitly required.
- Tamper with tenant slug, database name, branch code, queue payload, HL7 MSH-4 and federation pointer between authorization and execution; require fail-closed behavior.
- Revoke/disable a tenant and prove queued jobs and long-lived pools cannot continue using stale credentials or cached engines.
- Verify fleet dashboard and telemetry return only approved aggregate fields and cannot query patient-level rows.
- Verify support reset, key rotation, tenant clone, schema sync and bulk import require distinct audited capabilities and cannot be invoked by ordinary CP runtime identity.
- Verify federation discovery/import source reads execute in the source tenant boundary and destination writes execute in the destination tenant boundary.
- Use independent PostgreSQL logins and independent sessions/processes to prove positive and negative grants; test `PUBLIC` ACLs, ownership, role memberships and existing authenticated sessions.

**Disposition:** the call-site review confirms that direct tenant DB access is embedded in core request handling, background work, integration ingress, CP fleet/support routes, migration tooling and federation. The next design decision should be process/workload isolation, not another role SQL revision. No runtime, SQL, migration, Compose, credential, database, patient-data or production change was made.