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

## 16. Compose workload topology and minimum isolation boundary (2026-11-13)

### 16.1 Evidence inspected

This inventory compares the checked-in `docker-compose.yml` and `docker-compose.prod.yml` on the PR branch, `Dockerfile`, `backend/scripts/bootstrap.py`, `backend/scripts/backup_service.py`, and the host backup/restore scripts. It is a static configuration/source review; it does not prove which profile is deployed, the effective merged Compose configuration, runtime environment values, host scheduler, mounted storage, database grants or active sessions.

The production Compose file gives the following application services the same `.env.production` file: `db-init`, `api`, `hl7-listener`, `worker`, and `onboarding-portal`. The DB container also receives it. The exporter receives the same PostgreSQL username/password through `DATA_SOURCE_NAME`. This is not a workload-specific secret boundary.

A particularly important bootstrap detail: production runs `python backend/scripts/bootstrap.py --apply-roles`. In the inspected implementation, `bootstrap_system(apply_roles=True)` provisions physical databases, applies the role SQL, and then continues into control-plane and tenant migrations/seeding. The flag does **not** make the process a roles-only task or exit after applying roles. Thus `db-init` is currently a combined provisioning, role-administration, migration and initialization workload using the shared configured PostgreSQL login.

### 16.2 Current-to-target workload matrix

| Compose/host workload | Current database capability and adjacent access | Target identity / boundary | Minimum safe architectural disposition |
|---|---|---|---|
| `db` | PostgreSQL server; bootstrap credentials are initialized from `.env.production`. | Database server only; no application workload identity. | Keep server credentials out of application containers; provision individual login secrets through a controlled mechanism. Verify network reachability and effective ACLs at runtime. |
| `db-init` | Full `.env.production`; uses shared POSTGRES login to create databases, apply roles, migrate CP and tenant DBs, and seed. | Split short-lived cluster provisioner, role administrator, migration runner and tenant initializer. | Do not treat `--apply-roles` as a narrow role-only mode. Before any implementation, specify separate commands/entrypoints and distinct short-lived credentials; ensure API/worker startup depends only on completed approved initialization. |
| `api` | Full `.env.production`; API request path can open CP and arbitrary tenant DBs through shared engine/URL construction. Production also mounts `hms_backups` read-write and attachment storage. | Tenant-bound clinical API execution; CP access only where strictly required by an explicit separate capability. | Split tenant-facing execution from CP administration or enforce an independently reviewed tenant-bound credential broker/process model. Remove cluster-wide DB secrets and unnecessary backup-volume access from the API. Validate whether any route still requires CP access. |
| `onboarding-portal` | Full `.env.production`; serves CP app but imports shared tenant engine paths via fleet/support/migration surfaces. Also mounts `hms_backups` read-write. | CP-only web identity; delegated tenant operations use separately authorized workers. | Remove direct tenant DB credentials and shared backup-volume access. Replace tenant reads/writes with minimal CP projections and durable, audited tenant-bound jobs. |
| `worker` | Full `.env.production`; generic queue worker can access CP and tenant DBs; shares read-write backup volume and attachments. | Distinct queue consumers by operation class, with tenant-bound clinical/privacy/import execution and no arbitrary DB selector. | Separate job types/queues and execution identities; bind tenant and operation server-side, validate at execution, and ensure credentials/engine caches are revoked on disablement. Remove backup volume unless a specific worker operation proves it is required. |
| `hl7-listener` | Full `.env.production`; reads CP routing metadata and directly obtains tenant engines after interpreting inbound facility/interface data. | Integration ingress plus source/tenant-bound result processor. | Listener should authenticate interface/facility and submit a signed or otherwise authenticated, tenant-bound operation. Clinical DB write must occur in the authorized tenant boundary; inbound MSH-4 is routing data, not authority. |
| `postgres-exporter` | Production Compose builds a connection string from shared `POSTGRES_USER`/`POSTGRES_PASSWORD` and configured `POSTGRES_DB`. | Dedicated monitoring login with only required statistics/catalog visibility, no clinical table read. | Replace shared application credential with a dedicated monitoring identity; test effective privileges and exporter collector behavior using independent sessions. |
| `backup-sidecar` (development Compose only) | Loads `.env`; backup daemon reads CP registry/secrets and invokes `pg_dump` using shared POSTGRES login. | Dedicated backup coordinator plus per-database dump identity or isolated backup executor. | Treat as development-profile evidence only; do not infer it runs in production. Scope backup identity to assigned DBs and remove tenant-secret decryption/cluster-wide credentials from general services. |
| `backup-vault` (development Compose only) | Loads `.env` although file-copy/vault mode does not need DB or application secrets; reads shared backup volume and writes vault volume. | Credential-free artifact replication identity. | Remove DB/application secret injection; make source read-only and destination write-only where platform permits; verify immutability, retention and off-host delivery. |
| Production host `backup-postgres.sh` | Host script reads production env and uses `docker compose exec db` with POSTGRES login for database inventory and dumps; also handles host backup storage. | Host-controlled backup orchestration with narrowly scoped DB dump identity and separate storage identity. | Identify the actual scheduler/host and secret delivery. Scope inventory/dump access; independently verify off-host delivery and storage mount. Do not assume the development sidecar provides production scheduling. |
| Production host `restore-postgres.sh` | Host script uses the DB container's shared POSTGRES login to create a restore DB and run `pg_restore`. | Explicitly approved restore executor with isolated target allowlist and time-bounded create/restore privileges. | Separate restore from application identity; validate artifact provenance/integrity and target ownership before restore. No tenant routing/cutover until independent restore verification and approval. |
| `redis` / `redis-exporter` | Redis password is separately supplied; not a PostgreSQL identity, but queue access can trigger privileged DB operations. | Redis service identity plus queue-specific producer/consumer authorization. | Keep Redis credential separate from PostgreSQL; do not mistake queue authentication for tenant authorization. Enforce job authorization in the consumer. |
| `hospital-ui`, reverse proxy, monitoring stack, node exporter, scanner | No intended direct PostgreSQL application access in the inspected Compose definitions (exporter is separately listed above). | No PostgreSQL credential. | Preserve no-DB-secret boundary; verify effective environment and network policies in deployed profile. |

### 16.3 Topology findings and minimum safe sequence

1. **The current Compose service split is not a DB privilege split.** API, worker, HL7 listener and onboarding portal are separate containers but receive the same production environment file. Container separation alone does not constrain database access when each container can read the same fleet-capable credentials.
2. **The CP portal is not CP-only today.** Its code paths can instantiate the tenant engine registry, and its container receives the same database secret bundle. A service name or separate process does not establish an authorization boundary.
3. **The API has an additional storage concern.** Production API mounts the shared backup volume read-write. The API and worker should not receive backup artifact access by default; document and test any unavoidable attachment/backup interaction separately.
4. **The HL7 listener is an independent ingress surface.** It should not inherit a fleet credential merely because it needs routing metadata. The authenticated interface identity must bind the target tenant before clinical write execution.
5. **The exporter is a distinct read surface.** It must not reuse the application login. Confirm the precise PostgreSQL statistics collectors and required catalog privileges before granting any monitoring access.
6. **Backup and restore production execution remains unresolved.** The checked-in production Compose file does not declare the development backup-sidecar/vault services. The host scripts show a separate host-executed path, but this static review does not establish its scheduler, host isolation, secret store, mounts or actual production use.
7. **Bootstrap is over-privileged by construction.** The current `--apply-roles` command continues through provisioning, migrations and seeding. A future split must ensure each command has a distinct purpose, identity, lifetime and audit record; merely changing its name or Compose service is insufficient.

Minimum safe order for a future approved implementation:
- First decide the tenant-bound execution model and secret delivery mechanism; retain database-per-tenant.
- Separate CP web runtime from tenant DB access and remove its shared backup mount.
- Separate tenant clinical API and queue consumers so each execution context is bound to one authorized tenant; do not put all tenant passwords in a common process.
- Move HL7 clinical writes behind an authenticated tenant-bound processor.
- Split provisioning, role administration, migration and initialization into separately authorized short-lived operations.
- Give exporter, backup and restore dedicated identities and storage boundaries; identify the actual production backup scheduler before changing Compose.
- Prove the resulting topology with independent PostgreSQL logins/processes, cross-tenant negative tests, queue tampering/revocation tests, exporter privilege tests, and backup/restore isolation drills.

**Disposition:** this matrix identifies the smallest meaningful workload boundaries; it is not an approved deployment design or implementation authorization. No Compose, Dockerfile, runtime, SQL, migration, credential, database, storage, patient-data or production setting was changed. PostgreSQL database-per-tenant is preserved.


## 17. Minimum target deployment topology and phased isolation plan (2026-11-13)

### 17.1 Design constraints

This target is intentionally a **small number of privilege-separated workloads**, not a microservices decomposition. Preserve:
- PostgreSQL database-per-tenant; one tenant's clinical records remain in its tenant database.
- The existing modular-monolith codebase and domain boundaries unless an independently justified extraction is required.
- Existing Compose deployment as the initial packaging mechanism; do not introduce Kubernetes, a service mesh, or a fleet of always-on per-tenant containers by default.
- Explicitly separate control-plane metadata from tenant clinical data, and separate ordinary runtime from provisioning, migration, backup and break-glass authority.

A Compose service boundary counts as a security boundary only when its environment, secrets, database grants, mounted volumes, network access, process identity and callable operations are independently constrained.

### 17.2 Minimum logical workload set

| Logical workload | Responsibility | Permitted database scope | Must not possess |
|---|---|---|---|
| **Control-plane web** (onboarding portal/API) | Authentication, tenant registry, subscriptions, routing metadata, user/tenant lifecycle metadata and CP-owned configuration. | Control-plane DB only. | Tenant clinical DB credentials, tenant engine registry capability, backup artifacts, migration/DDL or cluster administration. |
| **Tenant clinical API** | Authenticated hospital/branch requests and clinical/business transactions. | Only the tenant DB selected from trusted server-side identity and bound to the request execution context. CP lookup is via a narrow, separately authenticated resolver or signed tenant context, not unrestricted CP ORM access. | Arbitrary tenant DB selection, fleet tenant secrets, cluster administration, backup storage and migration privileges. |
| **Tenant-bound background execution** | Queue jobs that mutate or read tenant data (including privacy retention and imports). | One tenant DB per execution context/job; tenant and operation are revalidated at execution. | Trust in queue-supplied DB names/tenant slugs, a generic fleet-wide DB login, or ability to reuse a stale tenant engine after revocation. |
| **Integration ingress and tenant processor** | Authenticate HL7/interface sender, resolve a trusted facility/interface mapping, validate message and submit a tenant-bound result operation. | Ingress: no direct clinical DB access (CP routing metadata only through a narrow resolver). Processor: one authorized tenant DB for the operation. | Treating MSH-4, source IP or an unverified message field as authorization; fleet-wide tenant DB credentials in the listener. |
| **Privileged operations runner** | Database creation, role/ACL reconciliation, tenant migrations, seed/initialization, tenant clone and other DDL/provisioning operations. | Only the explicitly named target DB(s) for a short-lived approved operation; cluster-level authority only for provisioning/role tasks that require it. | Long-running API/worker credentials, general clinical traffic, automatic execution from an ordinary request or queue payload. |
| **Backup/restore executor** | Inventory, consistent dump, encryption, artifact validation, restore drills and approved recovery. | Read/dump only the assigned database set; restore authority restricted to isolated restore targets until verification and approval. | API/worker access to backup volumes, general clinical writes, unverified tenant routing/cutover. |
| **Monitoring/exporter** | PostgreSQL health and approved statistics. | Monitoring/catalog/statistics only as required by proven collectors. | Clinical table reads, writes, DDL, tenant secrets or shared application login. |
| **Existing infrastructure services** | PostgreSQL, Redis, reverse proxy, scanner, metrics, UI. | No direct tenant clinical access except the separately constrained exporter. | Application DB credentials in UI, proxy, scanner or unrelated infrastructure containers. |

### 17.3 Deployment shape: avoid a container per tenant as the default

**Recommended initial target:** retain one deployable application codebase but use two web trust domains (CP-only and tenant clinical) plus separately scoped background/operations workloads. Tenant execution must be bound to a tenant-specific credential capability at the process or connection boundary.

There are two acceptable implementation patterns; select one in an ADR before coding:

**Pattern A — tenant-bound execution instances.** Run tenant API/worker execution instances with access only to the tenant DB credential(s) assigned to that instance. This gives the clearest PostgreSQL and secret boundary, but creates operational overhead as tenant count grows. It is appropriate for a small/regulated deployment or high-risk tenants, not automatically one container per branch.

**Pattern B — constrained credential/connection broker.** A small broker holds or obtains tenant credentials and issues a connection only after authenticating the calling workload, validating the operation and binding it to an immutable tenant identity. The broker must not expose a caller-controlled arbitrary DB-name/password lookup. It needs workload authentication, signed/short-lived capabilities, tenant and operation allowlists, TTL, replay protection, revocation, audit, rate limits, pool invalidation and negative tests. The broker itself is a high-value security boundary and must be isolated from ordinary CP/API processes.

A process that can read every tenant password and call `get_engine(db_name)` is **not** Pattern B; it remains a fleet-wide credential oracle. Per-database PostgreSQL logins do not repair that process-level flaw if all secrets are available to the same workload.

**Decision gate:** choose Pattern A or B based on expected tenant count, deployment operations, threat model and acceptable blast radius. Do not implement both or create a permanent per-tenant container fleet without measured need. A hybrid can reserve Pattern A for high-risk tenants and Pattern B for standard tenants, but only after a documented threat model and operational proof.

### 17.4 Minimum Compose-level target (logical, not a literal service-name prescription)

| Current service | Minimum target disposition |
|---|---|
| `api` | Split the current combined API surface into CP-only web and tenant clinical request surfaces. Keep the same repository/domain modules where practical. |
| `onboarding-portal` | CP-only; remove tenant engine access and backup volume. |
| `worker` | Split consumers by privilege class: tenant-bound clinical/privacy/import jobs versus CP-only scheduling/dispatch. Do not split every domain into a service. |
| `hl7-listener` | Keep as a small ingress process with no direct clinical DB credential; delegate authenticated tenant-bound processing. |
| `db-init` | Replace the ambiguous combined role with explicit, separately invoked provision, role-reconcile, migrate and initialize commands. Each command gets only the authority it needs. |
| `postgres-exporter` | Dedicated monitoring identity and verified minimal collector grants. |
| Host backup/restore | Dedicated executor and protected storage; keep out of API/worker containers. Identify and verify the actual production scheduler before deployment changes. |
| `db`, `redis`, proxy, UI, scanner and metrics | Retain as infrastructure; no broad tenant credentials. |

Do not mechanically split services until route and dependency inventories identify which endpoints require CP metadata and which require tenant clinical sessions. The existing shared application package may remain a modular monolith behind separate entrypoints.

### 17.5 Implementation phases and gates

| Phase | Scope | Exit evidence / gate |
|---|---|---|
| **0 — design freeze** | Decide Pattern A or B; map endpoints/jobs to CP vs tenant operations; inventory secret sources, environment variables, mounts, networks and connection pools. | Approved ADR, threat model, workload identity contract, tenant binding contract, rollback and migration plan. No production credentials changed yet. |
| **1 — CP isolation** | Make CP web genuinely CP-only; remove tenant registry/engine capability and backup mount; split CP scheduler from tenant job execution. | Static import/route scan plus runtime tests show CP identity cannot connect to any tenant DB; CP workflows still pass. |
| **2 — tenant execution isolation** | Implement tenant-bound request and job contexts; remove fleet credentials from general API/worker; enforce revocation and pool invalidation. | Independent-session tests prove tenant A cannot connect to B; queue tampering and tenant-disable tests fail closed; concurrency tests pass. |
| **3 — ingress and privileged operations** | Move HL7 writes behind tenant-bound processor; split bootstrap provisioning, role reconciliation, migrations and initialization. | Sender/facility spoofing tests; each privileged command tested with only its intended grant; ordinary API cannot perform DDL/provisioning. |
| **4 — backup, restore and monitoring** | Dedicated dump/restore and exporter identities; isolate artifact storage; prove actual scheduler and off-host delivery. | Cross-tenant dump denial, restore-to-isolated-target drill, artifact integrity/provenance checks, exporter cannot read clinical rows, off-host failure is surfaced as failure. |
| **5 — production readiness gate** | Full security, operational and recovery verification in a production-like environment. | Independent penetration/security review, backup restore evidence, load/concurrency tests, incident/credential-rotation drills, audit-log verification, compliance review and explicit release approval. |

### 17.6 Non-negotiable acceptance criteria

- No general-purpose web or worker process can retrieve credentials for every tenant and select arbitrary DB names.
- Every tenant DB operation has a server-validated immutable tenant binding and an operation-specific authorization decision.
- CP runtime cannot query tenant clinical tables.
- Tenant A credentials cannot connect to tenant B or CP unless a separately documented capability explicitly permits that access.
- Queue payloads, HL7 headers, request parameters and federation pointers are never authorization sources.
- Tenant disablement/revocation invalidates queued work, credential capabilities and pooled connections within a documented bounded interval.
- Provisioning, migration, backup, restore, exporter and break-glass support identities are distinct from ordinary clinical runtime.
- Existing sessions, PUBLIC ACLs, role membership, object ownership and default privileges are tested, not inferred from role SQL text alone.
- Backup and restore evidence includes the actual production host/scheduler, protected secrets, storage mount, off-host target and a completed restore drill.
- No patient data or production credentials are used in CI; synthetic independent DBs/logins are used for isolation tests.

### 17.7 Explicit non-goals

This milestone does not authorize schema-per-tenant, microservices, Kubernetes, service mesh, a new database platform, a tenant-per-container fleet, a change to patient/branch data ownership, or a production credential/ACL rollout. It does not establish HIPAA, DPDP, GDPR or other compliance certification.

**Disposition:** this is the minimum target topology and a phased decision framework. Pattern A versus Pattern B remains an explicit architecture decision; no runtime implementation or production change is authorized by this document.


## 18. Pattern A versus Pattern B decision analysis (2026-11-13)

### 18.1 Repository facts that constrain the decision

The decision is based on checked-in code and Compose configuration, not an assumed customer forecast:

- The product supports multiple active tenant records in the control plane and routes cloud requests by tenant subdomain. It also has an explicit on-prem deployment mode. The repository does not provide a reliable forecast of active cloud tenants, tenant growth, or per-tenant workload concurrency.
- The current API is a shared multi-tenant process. `TenantEngineRegistry` caches engines by caller-supplied database name (LRU limit 64), while `build_db_url(db_name)` changes only the database component of the same configured `DATABASE_URL`. It does not select a tenant-specific login or prove authorization.
- The request path resolves a tenant record from the control plane and then obtains an engine by `ctx.db_name`; this is useful routing context but does not constrain the shared PostgreSQL credential.
- CP fleet/support, migration, queue, HL7 and federation paths also access tenant engines. A change limited to the HTTP request dependency would leave alternate tenant access paths.
- Production Compose supplies the same `.env.production` to API, worker, HL7 listener, onboarding portal and db-init. Separate containers therefore do not currently imply separate database identities.
- No credential broker, tenant-aware PostgreSQL connection proxy, per-tenant secret delivery integration, or enforceable workload-to-tenant capability protocol was identified in the inspected paths.
- The source does not establish production tenant count, hosting provider, managed-versus-self-hosted PostgreSQL split, operational staffing, secret manager, pooler use, or actual deployed topology. Those are open deployment inputs, not facts to invent.

### 18.2 Comparative decision matrix

| Dimension | Pattern A — tenant-bound execution instances | Pattern B — constrained connection broker |
|---|---|---|
| Cross-tenant blast radius | Strongest straightforward boundary: process identity and secret access can be limited to one tenant DB. A compromised tenant process does not automatically expose other tenant credentials. | Potentially small if the broker authenticates callers and enforces immutable tenant and operation scope on every checkout. Broker compromise or policy bypass can expose many/all tenants. |
| Fit with current code | Requires replacing shared tenant engine access with tenant-bound runtime instances and routing; CP/fleet/queue/HL7/federation call sites must be delegated or isolated too. | Requires a substantial connection acquisition refactor. Existing arbitrary `get_engine(db_name)` cannot simply be wrapped in a broker call while the caller retains fleet credentials. |
| Initial engineering complexity | Moderate-to-high deployment and routing work; comparatively simple security model and easier negative proof. | High: protocol, broker authentication, capability lifecycle, connection ownership, pool partitioning, failure semantics and independent security review. |
| Operating cost | More process/service instances, secret bindings, health checks and deployment objects as tenant count grows. Per-tenant DB connections still exist either way. | Fewer app processes, but a highly available broker/proxy and its monitoring, scaling, backup, patching and on-call become critical shared infrastructure. |
| Scaling | Horizontal scale within each tenant boundary; noisy-neighbour controls can be applied per tenant. Deployment object count grows with tenant count. | App tier scales more uniformly; broker throughput, connection limits and pool cardinality become shared bottlenecks. Requires strict per-tenant fairness and limits. |
| Tenant onboarding/offboarding | Explicitly provision and bind a new execution identity/instance; revoke by disabling routing, revoking secret and draining that tenant's pools. | Register tenant policy and credential in broker; prove policy propagation, cache eviction, active connection termination and revocation under race conditions. |
| Rotation/revocation | Secret rotation and pool drain are tenant-local and comparatively observable. | Broker must revoke capabilities and terminate already-issued/backend pooled sessions within a bounded interval; credential rotation alone is insufficient. |
| Connection pooling | Pools are naturally partitioned by tenant process/identity. More pools and idle connections must be budgeted. | Pool keys must include immutable tenant identity, DB, role and privilege class; never multiplex one backend session across tenant identities without verified reset and isolation. |
| Availability | A tenant instance failure can be isolated to that tenant; deployment fleet control-plane overhead increases. | Broker is on the critical path for tenant DB access; it needs HA, safe degraded behavior and careful failure-domain design. |
| Observability/audit | Tenant process identity gives direct attribution; central correlation still required. | Broker can centralize decisions, but must log caller identity, immutable tenant, operation, grant decision, connection/session identity and revocation events without logging secrets or PHI. |
| Disaster recovery | Tenant execution can be recreated from declarative tenant binding and secret references; broker is not a new recovery dependency. | Broker policy, signing keys, tenant credential metadata and backend connectivity become additional recovery-critical assets. |
| Testability | Independent PostgreSQL logins and process identities give a direct, understandable positive/negative test oracle. | Requires adversarial protocol tests, forged/replayed capability tests, concurrent checkout/revocation tests, pool contamination tests and independent broker-policy verification. |
| On-prem deployment | Natural fit for a hospital-dedicated deployment where the deployment already has a single tenant trust domain. | Usually unjustified unless the on-prem deployment itself has multiple independently isolated tenant DBs. |
| Small initial cloud cohort | Higher operational footprint, but easiest boundary to reason about and verify before clinical data is onboarded. | Disproportionate complexity unless there is a concrete scale requirement and an independently operated broker/proxy. |
| Large multi-tenant SaaS | Can become operationally expensive; automate deployment and secret binding before tenant count grows. | Can be viable if the broker is purpose-built, independently reviewed, highly available and proven to enforce tenant binding end-to-end. |

### 18.3 Broker design distinction — mandatory

“Broker” must mean a **connection broker/proxy that retains backend credentials and enforces the database binding**, not a password vending endpoint.

A broker that returns a tenant password/DSN to the shared API is not sufficient: after issuance, the API can retain, copy, log, reuse or present that credential to another database unless PostgreSQL grants independently prevent it. A process that can retrieve every tenant secret remains a fleet-wide credential oracle.

A viable Pattern B must, at minimum:

1. Authenticate each caller using a workload identity unavailable to ordinary end users.
2. Accept a signed capability whose tenant immutable ID, database identity, role/privilege class, operation scope, expiry and audience are server-issued; caller-provided tenant/database strings are not authority.
3. Validate that capability against current CP lifecycle state and revocation generation on every new checkout, with a documented maximum stale-policy interval.
4. Retain backend credentials inside the broker/proxy boundary; never return passwords, reusable DSNs or raw secret material to the application.
5. Enforce the tenant DB and PostgreSQL role at connection establishment, and partition backend pools by immutable tenant ID, DB, role and privilege class.
6. Prevent session-state leakage across checkouts (role, search_path, temp objects, prepared statements, GUCs, advisory locks, transactions and failed reset); discard a backend session if reset cannot be proven.
7. Terminate or quarantine already-open sessions on tenant disablement, credential revocation and policy-generation change within a measured bounded interval.
8. Apply per-tenant connection, concurrency, rate and queue limits; fail closed if CP policy or broker authentication is unavailable.
9. Emit tamper-resistant audit records for allow/deny, checkout, release, reset failure, expiry, revocation and backend identity.
10. Be independently deployed and administered from CP/API workloads; broker administrators and secret readers are privileged roles subject to separate controls.
11. Be tested with concurrent adversarial tenant A/B sessions, replayed and expired capabilities, stale policy, forged DB names, pool reuse, broker outage, partial revocation and credential rotation.

A generic SQLAlchemy engine factory, Redis cache, API helper, or service that hands out passwords does not satisfy this definition.

### 18.4 Provisional architecture recommendation

**Select Pattern A as the initial security baseline for the first cloud production cohort and for tenant-specific/high-risk execution. Do not build Pattern B in the current remediation phase.** This is a security-first, reversible choice, not a claim that Pattern A is cheapest at every scale.

Reasons:
- The current application already has a fleet-wide database credential and many call sites that can choose a tenant DB. Pattern A provides a direct path to proving that a compromised tenant execution identity cannot authenticate to another tenant DB.
- No broker exists, and the repository contains no evidence of the infrastructure, team ownership or operating maturity needed to make a broker a safer choice today.
- A password-vending broker would only move the credential leak point; a true connection proxy is a new critical security component with significant design and test burden.
- The code supports on-prem deployment mode, for which a tenant-dedicated deployment is the natural default.
- Pattern A can be implemented incrementally without changing PostgreSQL database-per-tenant or decomposing the modular monolith into domain microservices.

This recommendation does **not** authorize a permanent container-per-tenant fleet or imply that the current shared API can be relabeled as Pattern A. The first implementation must define a tenant-bound execution unit, its routing contract, immutable tenant binding, secret reference, pool lifecycle and health/recovery behavior. The CP web tier must remain CP-only. Queue, HL7, federation, support, migration, provisioning and backup operations must be separately assigned to tenant-bound or privileged execution boundaries.

### 18.5 Reconsideration trigger and required evidence

Reopen Pattern B only when a measured operating case demonstrates that Pattern A's deployment/operations cost or connection footprint is unacceptable. Before changing the decision, collect:

- Current and forecast active cloud tenant counts (12/24/36 months), onboarding/offboarding rate, peak concurrent tenant workloads and per-tenant connection demand.
- Actual cloud/on-prem split, hosting profiles, PostgreSQL service topology, pooler availability, network latency and secret-management capabilities.
- Per-tenant process/container cost, idle resource use, deployment/upgrade toil, incident isolation and on-call burden from a representative pilot.
- Connection count and pool utilization under peak load, including background jobs, integrations and migrations.
- A broker threat model, ownership/on-call plan, HA design, recovery plan, policy consistency model and independent security review.
- A working prototype that passes the Section 9 independent PostgreSQL access matrix plus the broker-specific adversarial tests in Section 18.3.

The architecture decision must compare measured total cost and failure/blast-radius outcomes, not container count alone. Until those measurements exist, retain Pattern A as the default and do not introduce a broker as a cost-saving assumption.

### 18.6 Implementation sequence under this decision

1. Keep CP web isolated and CP-only; move fleet clinical reads and support actions to explicitly authorized delegated operations.
2. Define a tenant-bound execution identity and process contract for cloud tenant API and tenant workers. A tenant instance receives only that tenant's DB credential; no shared process receives the fleet secret set.
3. Route cloud tenant traffic to the bound execution unit using trusted server-side mapping. Host/subdomain, JWT tenant slug, queue payload and database name remain selectors, not database authorization.
4. Keep on-prem installs tenant-dedicated by deployment boundary, with the same PostgreSQL role/ACL and verification contract.
5. Split HL7 ingress from tenant-bound processing; isolate source-owned federation reads; use dedicated short-lived migration/provisioning identities; isolate backup/restore and monitoring.
6. Prove tenant A/B and CP denials with independent PostgreSQL logins and actual Compose/process secret inspection before any clinical production onboarding.
7. Measure operating cost and revisit Pattern B only at the evidence gate above.

**Decision status:** Pattern A is the recommended initial target; final implementation approval remains with architecture, DBA, security and operations owners. This decision does not authorize runtime, SQL, migration, Compose, secret, database, patient-data or production changes. PostgreSQL database-per-tenant remains invariant.


## 19. Pattern A tenant-bound execution contract (2026-11-13)

This section turns the Section 18 recommendation into a testable design contract. It is not a runtime specification ready for implementation until the open identity, routing, secret-manager and revocation decisions below are approved.

### 19.1 Identity model and immutable binding

Every tenant execution unit MUST have one server-assigned tenant identity and one explicit database authorization scope.

The binding consists of:
- immutable tenant identifier (not a subdomain, branch code, hospital name, database name or request parameter);
- canonical tenant database identity, verified against the control-plane registry;
- deployment/execution-unit identity;
- credential reference for that tenant's PostgreSQL login (secret material is not part of the binding document);
- privilege class (clinical runtime, read-only projection, import, integration, etc.);
- binding generation/version and activation state;
- issuance time, expiry/rotation metadata and revocation state.

The existing `TenantRegistry.id` is an integer primary key and the current routing record also contains mutable operational identifiers such as `subdomain_slug` and `db_name`. Do not silently assume that an integer ID is the final cross-system immutable identity contract. Before implementation, decide whether to retain the current ID as the canonical identity or introduce a UUID with a safe backfill and uniqueness plan. That is a migration/ADR decision, not part of this documentation-only milestone.

A deployment manifest may contain tenant identity, database identity, credential reference and generation, but MUST be provisioned by a trusted control-plane/operations workflow, integrity-protected, versioned and auditable. Application request data MUST NOT be able to create or mutate this binding.

### 19.2 HTTP ingress and tenant routing

Target request path:

1. Public ingress terminates TLS and validates the requested host against the configured domain policy.
2. A trusted routing layer resolves the host to an active tenant identity using authoritative control-plane metadata. A host/subdomain is a routing hint, not database authorization.
3. The routing layer forwards only to the execution unit bound to that tenant. The unit has no ability to select another tenant DB.
4. The tenant execution unit verifies that the signed user/session identity is valid for its assigned tenant and that token tenant identity equals the unit binding. Host, JWT tenant slug and client-supplied tenant IDs cannot override the assignment.
5. The unit opens a session only against its configured tenant DB using its tenant-specific login. It does not call a generic `get_engine(db_name)` with a request-derived value.
6. The unit attaches the immutable tenant identity and privilege class to the DB session for audit and application-level consistency checks; this metadata is supplementary and does not replace PostgreSQL grants.

Routing must fail closed for unknown, inactive, suspended, unassigned, mismatched or stale tenant mappings. The default-tenant fallback must not convert an unknown cloud host into access to a default clinical database. Header-based tenant override remains disabled outside a separately authenticated internal/test path; a proxy-provided header is trusted only when the immediate peer is an explicitly configured trusted proxy.

The current repository uses host/subdomain extraction and control-plane lookup in the shared API, then calls a shared engine registry. That is a useful starting routing mechanism, but it does not meet the target because all tenants still use the same configured PostgreSQL login and the API process can select arbitrary database names.

### 19.3 Process and secret boundary

For Pattern A, the tenant clinical execution unit MUST:
- receive exactly one tenant DB credential reference for its assigned tenant and privilege class;
- have no permission to enumerate, decrypt, read or request credentials for other tenants;
- have no cluster administrator, database creator, role administrator, migrator, backup or exporter credential;
- have no general control-plane DB write access; any needed lifecycle/routing decision must use a narrow authenticated interface or an independently scoped read-only projection;
- use a dedicated OS/container workload identity and least-privilege filesystem/network policy;
- avoid shared environment files containing credentials for multiple workloads; inject secrets at runtime through an approved secret-delivery mechanism;
- avoid writing credentials, DSNs, capability tokens or patient data into logs, task metadata, crash dumps or metrics;
- run with a privilege class appropriate to the workload, rather than combining clinical API, support, import, federation source read and migration authority in one process.

**Secret-delivery decision remains open.** The repository currently constructs `DATABASE_URL` from `POSTGRES_USER`/`POSTGRES_PASSWORD` and does not establish a tenant-specific secret manager or workload identity provider. A production secret manager, encrypted deployment secret store or host-level protected secret file may be evaluated, but must be selected and threat-modelled before implementation. The application must receive only its assigned secret; merely encrypting a fleet-wide secret map with a key available to every API process is not isolation.

The existing encrypted `TenantRegistry.jwt_secret_key` and HL7 shared secret are application/authentication secrets, not proof of per-tenant PostgreSQL credential delivery. Do not reuse or relabel them as database credentials.

### 19.4 PostgreSQL login and connection contract

Each tenant execution unit connects using a tenant-specific PostgreSQL login whose grants are limited to:
- CONNECT on its assigned tenant database only;
- required schema USAGE and table/sequence/function privileges for the approved runtime role;
- no CREATE DATABASE, CREATEROLE, SUPERUSER, REPLICATION, BYPASSRLS, ownership or migration privileges;
- no CONNECT to the control-plane database or another tenant database;
- no membership in cluster-wide data-reading or administrative roles.

The global PUBLIC CONNECT/TEMP defaults and inherited role memberships must be explicitly reconciled. A role's effective permissions must be tested on the actual PostgreSQL cluster, not inferred from role SQL declarations.

Connection construction MUST use a server-owned database identity from the unit binding. No request, queue payload, HL7 field, federation pointer, slug or database-name string may be passed to a generic URL builder or engine factory as authority.

For Pattern A, the preferred initial pool shape is one tenant DB + one runtime login + one privilege class per process. Pool settings must be sized across all processes/replicas and tenant workloads; do not create unbounded pools or allow an LRU eviction to disguise cross-tenant capability. On shutdown, revocation or rotation, stop new checkouts, drain or terminate sessions, dispose the pool and prove that no old connection remains usable. A stale pool must never be reattached to a new tenant binding.

### 19.5 Background jobs and scheduler separation

Tenant-bound work MUST carry a durable, authenticated execution envelope containing:
- task ID and idempotency key;
- immutable tenant identity and binding generation;
- approved task name/operation and schema/version;
- actor/initiator and approval reference where applicable;
- created-at, not-before and expiry;
- audience/execution-unit identity;
- integrity protection or a server-side durable operation record that prevents payload tampering.

The worker validates the envelope, tenant lifecycle state, current binding generation, operation allowlist and actor/approval constraints before opening the assigned tenant DB. A payload's `tenant_subdomain`, `db_name`, branch code or tenant ID is a selector only; it is not authority. Replayed, expired, revoked, malformed, wrong-audience or wrong-generation work is rejected and audited.

The producer must not fall back to executing tenant work synchronously inside a CP/API process when the queue is unavailable. The current `enqueue_task(..., sync_fallback=True)` default can run the handler in the producer process; this behavior is incompatible with a strict process boundary for tenant-bound tasks. Queue outage must produce a durable retry/outage state or a clear failure, not privilege-boundary bypass.

The current generic worker imports handlers that can reach the shared tenant registry. The target separates:
- CP scheduler/dispatcher: CP-only; discovers due work from CP-owned metadata and emits tenant-bound operations, but does not open clinical DBs;
- tenant-bound worker: executes jobs only for its assigned tenant and privilege class;
- privileged worker/runner: handles explicitly approved provisioning, migrations, import, backup/restore and break-glass operations under distinct identities.

A fleet sweep must not iterate every tenant DB from a general worker. Each tenant's scheduled operation is emitted with a binding and revalidated at execution. Job acknowledgement, retry, idempotency, dead-letter handling and cancellation/revocation semantics must be durable and testable; Redis queue contents alone are not the authorization record.

### 19.6 HL7 and federation execution

HL7 ingress authenticates the sender/interface and resolves the facility mapping, but the listener itself must not hold fleet-wide clinical DB credentials or select a tenant database for direct writes. It emits an authenticated, tenant-bound processing operation. The processor receives only the assigned tenant DB capability and revalidates sender/interface authorization, tenant lifecycle and message replay/idempotency state.

MSH-4, source IP and message-control ID are untrusted routing/authentication inputs until verified against the configured interface identity. The current listener resolves a branch code and encrypted shared secret from CP metadata, then passes a DB name to the shared tenant engine registry. That is not the target execution boundary.

Federation source reads execute inside the source tenant's own bound execution unit and release only an approved transfer payload. Destination writes execute inside the destination tenant's bound execution unit. Neither side receives the other tenant's DB credential or direct session. Federation pointers and partner-provided identifiers never authorize database selection.

### 19.7 Tenant lifecycle, revocation and rotation

Tenant state transitions MUST be explicit and auditable: provisioned/pending, active, maintenance/read-only, suspended/disabled, deprovisioning and retired (final names remain an application contract decision).

On disablement, suspension, credential compromise or tenant reassignment:
1. Mark the tenant execution binding revoked/inactive in authoritative control-plane state and increment its generation.
2. Stop ingress routing and reject new sessions, tokens and job envelopes for the old generation.
3. Stop/disable tenant-bound workers and cancel or quarantine queued/scheduled work for the tenant.
4. Revoke the old PostgreSQL login or its CONNECT grants as appropriate, rotate credentials and verify no inherited/public grant bypass remains.
5. Terminate existing DB sessions and dispose all process pools; revoke cached capabilities and secret leases.
6. Record actor, reason, timestamps, binding generation, affected execution units, job disposition, session termination evidence and completion status.
7. Re-enable only after fresh credential issuance, binding deployment and positive/negative connection tests.

The system must define and test a maximum revocation propagation interval. No numeric SLA is assumed here because the repository does not establish deployment latency, session lifetime or operational response objectives. During CP, secret-store or revocation-service unavailability, the execution unit must fail closed for new authorization and must not extend an expired capability indefinitely.

Credential rotation is a controlled overlap: issue new credential, deploy/update the tenant-bound unit, verify new connections, drain old sessions, revoke old credential, then prove old credentials fail. The overlap duration and rollback process must be approved and bounded.

### 19.8 Scaling, availability and disaster recovery

Pattern A must be operated as a fleet of tenant-bound execution units managed by automation, not as manually maintained snowflakes. The unit may have multiple replicas for availability only if every replica receives the same single-tenant binding and credential; it must never become a multi-tenant credential pool. A tenant's API and worker may be separate processes with distinct privilege classes but the same immutable tenant binding.

Before production sizing, measure per-tenant baseline memory/CPU, peak request concurrency, background concurrency, PostgreSQL connection demand, queue depth, cold-start/routing latency and upgrade/restart duration. Define placement constraints and resource quotas to prevent one tenant starving others. A shared ingress/router and deployment controller may serve all tenants but must not hold clinical DB credentials.

Tenant unit recovery must be reproducible from a signed/versioned binding and secret reference. Restore operations remain a separate privileged workflow: a restored DB is not routable until integrity, ownership, role/ACL, schema version, tenant identity and application-level checks pass and an authorized cutover is recorded. Disaster recovery must cover loss of the deployment controller/secret manager as well as the database.

### 19.9 Required verification suite

Before any clinical tenant is routed to Pattern A, prove at minimum:

**Identity and routing**
- Tenant A host + A token routes to A; A host + B token, B host + A token, unknown host, inactive tenant and stale binding all fail closed.
- Spoofed `X-Hospital-Subdomain`, `X-Forwarded-Host`, JWT tenant slug, request body tenant ID and direct DB name cannot change the process binding.
- A tenant unit cannot retrieve B's credential reference or resolve B's DB through any public/internal endpoint.

**PostgreSQL**
- Independent tenant A login connects to A and is denied B and CP; B login has the inverse result.
- PUBLIC CONNECT/TEMP, inherited role membership, object ownership, default privileges, functions, sequences and existing sessions are checked.
- Runtime role cannot create DB/roles, migrate, provision, dump/restore or read backup artifacts.
- Revocation terminates existing sessions and stale pool reuse fails.

**Queue and worker**
- Tampered, replayed, expired, wrong-audience, wrong-tenant and stale-generation envelopes are rejected.
- Tenant A worker cannot execute a job for B, even when Redis payload fields are changed.
- Queue outage never invokes tenant handlers in CP/API process through synchronous fallback.
- Scheduler has no tenant clinical DB session; retries, idempotency, cancellation and dead-letter behavior are verified.

**HL7 and federation**
- Forged MSH-4, invalid shared secret, replayed control ID, inactive interface and stale tenant mapping cannot cause a clinical DB write.
- HL7 ingress has no tenant DB credentials; processor A cannot connect to B.
- Federation source A cannot read B; destination B cannot open source A's DB; transfer payload and audit evidence are verified.

**Operations**
- Rotation, revocation, tenant move/reassignment, process restart, deployment rollback, CP outage, secret-store outage and restore/cutover are failure-injected.
- Process environment, mounted files, network policy, container identity and runtime secret access are inspected in the production-like deployment.
- Audit events correlate request/job/interface, tenant immutable identity, process identity, DB role/session and decision without exposing secrets or PHI.

### 19.10 Decisions still required before implementation

1. Canonical immutable tenant identity: retain integer `TenantRegistry.id` or introduce UUID; migration/backfill and federation pointer compatibility.
2. Routing topology: per-tenant host routing to dedicated service instances, or another ingress/deployment controller design that preserves single-tenant process credentials.
3. Secret delivery and workload identity provider, including on-prem supported profile and recovery if the secret service is unavailable.
4. Tenant-specific PostgreSQL login/role lifecycle and exact object ownership/default-privilege model.
5. Process orchestration, desired tenant scale, replica strategy, autoscaling, resource quotas and deployment/upgrade automation.
6. Queue technology/contract changes, durable operation record, capability signing, idempotency, retry and revocation behavior.
7. Revocation and rotation maximum propagation intervals and operational ownership.
8. Whether CP read-only tenant routing metadata is delivered by a narrow resolver, signed deployment manifest or a read-only projection; no CP clinical DB access is permitted.
9. How on-prem tenant-dedicated deployments share the same contract without requiring a cloud control plane.
10. Explicit acceptance by architecture, DBA, application security, platform and operations owners.

**Disposition:** this is a detailed tenant-bound execution contract and verification baseline. It deliberately leaves provider-specific secrets, identity, routing, orchestration and immutable-ID migration decisions open. No runtime, queue, listener, router, SQL, migration, Compose, secret, database, patient-data or production change was made. PostgreSQL database-per-tenant remains invariant.


## 20. PostgreSQL tenant role and credential lifecycle contract (2026-11-13)

**Status: proposed design and verification contract; not SQL or rollout authorization.** This section translates Sections 17–19 into a database-per-tenant role lifecycle. It deliberately does not finalize literal role names, exact grants, ownership commands, secret provider or backup platform until DBA/platform review and a disposable-cluster proof.

### 20.1 Current repository behavior verified

The inspected source revisions show the following:

- `deployments/postgres-roles.sql` creates four cluster roles only when absent: `hms_app`, `hms_migrator`, `hms_backup` and `hms_exporter`. The script sets several attributes at creation but does not reconcile attributes on an already-existing role. It does not configure passwords or a credential handoff.
- The same SQL grants `pg_read_all_data` to `hms_backup` and `pg_monitor` to `hms_exporter`. The former is cluster-wide data-read capability, not tenant-scoped backup access. The app/migrator grants shown in the file target the literal database `postgres`, not the control-plane database or each tenant database. The file does not revoke PUBLIC CONNECT/TEMP, assign database ownership, or establish a per-tenant role/grant lifecycle.
- `backend/scripts/bootstrap.py::apply_database_roles()` connects with `settings.POSTGRES_USER/PASSWORD` to database `postgres` and executes the SQL file. `provision_physical_databases()` uses the same configured login to create the control-plane/default tenant databases. Migration URLs are built from the same configured `DATABASE_URL`; tenant initialization and seeding then use those URLs.
- `bootstrap_system(apply_roles=True)` is not a roles-only operation. It provisions physical databases, applies role SQL, upgrades the control-plane DB, seeds CP data, may create/upgrade/seed the default tenant, and validates active production tenant revisions. A production command or Compose entrypoint using `--apply-roles` therefore has a much broader effect than its option name suggests.
- `backend/core/database.py::build_db_url(db_name)` changes only the database component of the configured URL. `ensure_postgres_db_exists()` uses that same configured login for cluster-level database creation. The runtime engine registry and CP engine also derive from the shared URL.
- `deployments/backup-postgres.sh` runs database inventory queries, `pg_dump` for every application DB, and `pg_dumpall --globals-only` as `POSTGRES_USER` inside the database container. It does not use `hms_backup`. The global dump is a separate cluster-level operation and must not be conflated with a tenant-scoped database dump.
- `deployments/restore-postgres.sh` checks/creates the isolated `restore_*` target as `POSTGRES_USER`, assigns that login as owner, and runs `pg_restore --no-owner --no-acl` as the same login. This is a diagnostic restore path, not yet a tenant-role-aware restore/cutover process. The script explicitly says not to route tenants to the target before verification.

These are source-level observations, not proof of deployed role attributes, environment values, effective grants, host controls or production scheduler configuration. Source blob revisions were inspected on 2026-11-13: roles SQL `315ab21d141cd5a9e4b7d973c6ad4eb6e41e1ebe`; bootstrap `418a6f6641c17f2bc17b22f4bc09371ae9857bfd`; database module `043f4ccbdad4d2bfe4c89af0b46988ce60610b01`; backup script `a66b9d45362b2e393bc50cddc1aa20eb2b053d95`; restore script `0c21ae21b3630b1c0570b9012b44b9bd19041982`.

### 20.2 Target role classes and boundaries

The target separates cluster administration, database ownership, application login and operational capabilities. A PostgreSQL role is not automatically a workload identity; credential delivery and process isolation remain mandatory under Pattern A.

| Role class | Scope and intended capability | Explicit exclusions |
|---|---|---|
| Cluster bootstrap/provisioner | Short-lived infrastructure identity for approved role creation/reconciliation and database creation. Executes a separately approved provisioning operation. | Never present in API, CP portal, generic worker or HL7 ingress. No routine clinical DML. No unattended fleet-wide credential exposure to application processes. |
| Database owner (NOLOGIN group role) | Owns exactly one application database (CP or one tenant DB) and its intended objects; receives ownership only during provisioning/migration/restore handoff. | Not used as a connection login; no cross-tenant ownership. Do not make the application runtime a database owner. |
| CP runtime login | Connects only to the control-plane DB and performs the minimum CP metadata operations. | No tenant DB CONNECT, tenant credentials, tenant clinical tables, DDL, provisioning, backup or cluster administration. |
| Tenant runtime login | One distinct login per tenant DB and assigned tenant execution unit; DML/sequence/function permissions only where required by application behavior. | No CP or other-tenant CONNECT, DDL, ownership, role membership, database creation, backup, restore, replication or cluster-wide read roles. |
| Tenant migration identity | Short-lived, explicitly invoked identity scoped to one target database for approved schema migrations. Object creation/ownership and default privileges must be deliberately coordinated with the database owner role. | Not available to the running API, CP portal, general tenant worker or HL7 ingress; no cluster-wide role administration. |
| Backup executor identity | Dedicated backup operation identity with only the database/object-read capability required for the assigned DB(s), plus a separately reviewed cluster-inventory mechanism if required. | No application writes, schema ownership, DDL, role administration, tenant runtime use or general-purpose API/worker access. No default cluster-wide `pg_read_all_data` grant to a tenant-scoped executor. |
| Restore executor identity | Creates/restores only an explicitly named isolated target under an approved operation, then applies/validates intended owner and ACL state before handoff. | No tenant routing/cutover authority by virtue of DB creation; no API/worker use; no overwrite of an existing target. |
| Monitoring/exporter identity | Statistics/catalog visibility required for monitoring, using the narrowest supported monitoring capability. | No clinical table data, backup artifacts, write privileges, migration or tenant application login. |

A separate NOLOGIN owner/group role per database is the preferred model to evaluate: one CP owner and one owner per tenant database. Runtime and operational login roles receive explicit membership/grants appropriate to their task without becoming owners. The DBA must decide whether migration creates objects as the owner role (for example, via tightly controlled role switching) or uses an equivalent ownership/default-privilege pattern. Do not assume that granting broad schema privileges to a migrator automatically produces correct ownership for future tables, sequences, functions or extensions.

### 20.3 Database creation, ownership and ACL lifecycle

Provisioning must be an explicit state machine, not an incidental side effect of application startup:

1. An approved provisioner creates the CP or tenant database using a validated canonical database identity and a safe identifier-quoting strategy.
2. The database is assigned to its intended NOLOGIN owner role. The owner role is unique to that database; it is not shared across tenants.
3. PUBLIC database privileges are reconciled. The target policy explicitly revokes unneeded PUBLIC CONNECT and TEMPORARY privileges, then grants CONNECT only to the database owner/approved runtime, migration and operational identities. Any exception must be documented and tested.
4. The public schema and any additional schemas have explicit ownership and USAGE/CREATE policy. Do not assume that the `public` schema is the only schema or that PostgreSQL-version defaults are identical across supported versions.
5. Runtime privileges are granted to the tenant-specific runtime identity only for the application objects and operations it needs. Sequence, function, type, large-object and extension privileges must be inventoried rather than inferred from table DML grants.
6. Default privileges are configured for the actual object-creating role(s), in the correct database and schema. PostgreSQL default privileges are creator-role-specific; a default-privilege statement executed as the wrong role does not solve ownership or future-object access.
7. Migration, initialization and seed operations run under their separately approved identity. After completion, verify object ownership, ACLs, default ACLs, role memberships and effective privileges before the tenant is marked ready.
8. The CP registry is updated to active/routable only after DB identity, ownership, grants, migration revision, seed invariants and connection tests pass.

Database-per-tenant remains the isolation unit. No schema-per-tenant conversion is implied. Database names, branch codes, slugs and hostnames are validated identifiers/selectors, not authorization tokens.

### 20.4 Migration and initialization lifecycle

Separate the current combined bootstrap behavior into independently invocable, idempotent operations with distinct identities and explicit target confirmation:

- cluster role bootstrap/reconciliation;
- CP database provisioning and CP migration;
- individual tenant database provisioning;
- individual tenant migration;
- tenant initialization/seeding;
- verification and activation.

A role-reconciliation command must not silently create databases, migrate schemas, seed users or activate tenants. A migration command must name one approved database/tenant binding, validate its current lifecycle/generation and expected revision, acquire a migration lock, record start/result, and fail closed on identity mismatch. Fleet migration is a separately approved orchestrated operation with bounded batches/canaries and per-tenant outcomes; it must not be an implicit API/worker startup side effect.

Migration object ownership must remain stable across upgrades. The design must cover Alembic version tables, tables, indexes, sequences, views, functions, triggers, extensions and any objects created outside the migration owner. The runtime login must not inherit migration/owner privileges after migration completes.

### 20.5 Role reconciliation and credential issuance

Role SQL must become declarative reconciliation, not create-if-absent-only behavior. Every run must inspect and enforce approved role attributes (LOGIN/NOLOGIN, SUPERUSER, CREATEDB, CREATEROLE, REPLICATION, BYPASSRLS, INHERIT/NOINHERIT, connection limits and valid-until policy), membership edges, database ACLs, schema/object ACLs, ownership and default privileges. Unexpected grants or attributes must be reported and corrected only by an approved reconciliation operation. Reconciliation must be idempotent and safe to re-run.

Credentials are provisioned out-of-band through the approved secret-delivery mechanism; no plaintext passwords are committed to SQL, source, CI logs or generated docs. Each tenant runtime credential is unique to one tenant execution boundary. CP, tenant runtime, migrator, backup, restore, monitoring and cluster provisioner credentials are distinct. Credential references are bound to immutable tenant identity, database, role class, execution unit and binding generation.

The exact secret provider, rotation API and on-prem equivalent remain open decisions. A single shared `POSTGRES_USER/PASSWORD` injected into all containers is not an acceptable target. A tenant unit must not be able to enumerate or retrieve another tenant's credential.

### 20.6 Rotation, revocation and emergency response

Normal rotation uses a bounded overlap: issue a new credential; deploy it only to the matching execution unit; prove a fresh connection and required application operation; stop new checkouts on the old pool; drain/terminate old sessions; revoke or expire the old credential; and prove the old credential cannot reconnect. Record role, tenant identity, generation, actor, timestamps, affected sessions and verification result without logging secret material.

Tenant disablement/reassignment follows Section 19.7: increment binding generation, block routing and jobs, revoke the tenant login or CONNECT, terminate sessions, invalidate secret leases and dispose pools. Revoking a role alone is insufficient evidence if already-open sessions remain active. Re-enablement requires fresh credentials and independent positive/negative tests.

Cluster provisioner and migration credentials require shorter lifetimes and explicit operation windows. Break-glass use is separate, approved, time-bounded, attributable and reviewed after use. The emergency process must not silently restore a broad shared login to application containers.

### 20.7 Backup and restore identity contract

Tenant DB backup must be scoped to an assigned DB and a reviewed read capability. Evaluate whether a non-owner backup role can read all required tables, sequences, large objects, metadata and extension state using explicit grants, or whether an owner/backup role is temporarily assumed under a controlled executor. Do not grant `pg_read_all_data` cluster-wide to a tenant-scoped backup identity by default. If a cluster-wide globals/roles export is required, treat it as a distinct cluster-administration artifact and operation, protect it separately, and do not pass that identity to a tenant dump worker.

The backup executor must enumerate only authorized databases from trusted control-plane/infra inventory, not accept arbitrary database names from callers. Artifact write access is isolated from API, worker, CP portal and HL7 workloads. The file-copy vault receives no DB credential. Backup success requires encrypted dump validation, integrity manifest, remote/off-host completion where required, and durable status that distinguishes local snapshot from off-site replication.

Restore runs in an isolated target database, never overwrites a live tenant DB, and initially remains unroutable. A restore executor creates the target with a controlled owner; restores data; applies the approved owner/ACL/default-privilege policy; validates tenant identity, schema revision, integrity and application invariants; and produces evidence for a separately authorized cutover. Because current `pg_restore --no-owner --no-acl` leaves restored objects owned according to the restoring context, ownership normalization must be an explicit post-restore step, not assumed. Global role restore is a separate reviewed operation and must not be run as part of a routine tenant restore.

### 20.8 Required disposable-PostgreSQL proof matrix

Extend the existing PR #71 characterization harness into acceptance tests only after the target role model is approved. Use a fresh disposable PostgreSQL cluster and independent login connections; never use production credentials or patient data.

| Proof area | Required positive proof | Required negative proof |
|---|---|---|
| Cluster identities | Provisioner can create only approved roles/DBs in the test fixture; exporter can read required monitoring statistics. | CP/tenant runtime, tenant migrator, backup and exporter cannot administer roles or create arbitrary DBs. |
| CP boundary | CP runtime connects to CP DB and performs approved CP metadata operations. | CP runtime cannot CONNECT to tenant A/B or read clinical objects. |
| Tenant A/B | A runtime connects to A and performs required DML; B runtime does the same on B. | A is denied B and CP; B is denied A and CP; neither can create roles/DBs, alter schema or assume owner/migrator. |
| Ownership/default ACL | Provisioning and migration create expected owner, object ACLs and future-object defaults for tables, sequences, functions and other supported objects. | Runtime cannot become owner; objects created by an unexpected role do not silently receive broad runtime grants. |
| PUBLIC and membership | Approved explicit grants allow only intended identities; catalog and effective privilege checks match the matrix. | PUBLIC CONNECT/TEMP, nested membership, predefined roles, inherited privileges or ownership do not bypass the tenant boundary. |
| Reconciliation | Reapply converges drifted role attributes, membership, ACLs and ownership to approved state. | Existing unsafe attributes, unexpected memberships or stale grants do not survive an apparently successful no-op run. |
| Migration | Scoped migrator can upgrade one target and leave ownership/default ACLs correct. | Migrator for A cannot migrate B/CP; runtime cannot run DDL or inherit migrator rights. |
| Backup | Backup executor dumps the assigned DB and validates the artifact; separately approved globals export is tested independently. | Tenant A backup identity cannot dump B/CP or access cluster globals; API/worker cannot read/write backup artifacts. |
| Restore | Isolated restore target is created, restored, normalized to expected owner/ACL and verified before simulated cutover. | Existing DB cannot be overwritten; restored DB cannot become routable before verification; restore login cannot access unrelated tenant DBs. |
| Rotation/revocation | New credential works during approved overlap and old credential is revoked after pool drain. | Old login cannot reconnect; pre-existing sessions are terminated; stale pool/job/capability cannot use the old generation. |

Tests must inspect `pg_roles`, `pg_auth_members`, `pg_database`, `pg_namespace`, `pg_class`, `pg_default_acl`, `pg_proc`, database/schema/object ACLs, ownership and effective privilege functions. Include existing-session tests, nested membership, PUBLIC defaults, reapply after deliberate drift, multiple independent sessions and failure injection between every provisioning/restore stage. The existing PR #71 test is a characterization proof of current unsafe behavior, not a pass of this acceptance matrix.

### 20.9 Decisions and approvals still required

1. Final NOLOGIN owner-role and LOGIN role naming convention, including per-tenant identity uniqueness and naming-length constraints.
2. Whether migration assumes a per-database owner role or uses a separately controlled object-ownership/default-privilege model.
3. Exact runtime privileges for tables, sequences, functions, large objects, extensions and future objects, based on a complete application query inventory.
4. Supported PostgreSQL versions and PUBLIC/schema default behavior across those versions.
5. Provisioner implementation, execution environment, approval model, credential TTL and audit ownership.
6. Secret provider/workload identity and on-prem deployment equivalent.
7. Tenant-scoped backup privilege strategy, cluster globals export owner, off-host storage and restore executor separation.
8. Role/credential rotation overlap and maximum revocation/session-termination SLA.
9. Safe split of the current `bootstrap.py --apply-roles` command into explicit operations without accidental migration/seeding side effects.
10. DBA, architecture, application-security, platform and operations sign-off plus passing independent-session disposable-PostgreSQL tests.

**Disposition:** this section is a proposed role/credential lifecycle contract. It identifies concrete mismatches in the current role SQL, bootstrap, shared URL construction and host backup/restore scripts. It does not authorize SQL/runtime/Compose/migration/secret changes. PostgreSQL **database-per-tenant** and Pattern A remain the target baseline; no schema-per-tenant change is proposed.


## 21. Application PostgreSQL privilege inventory (2026-11-13)

**Status: source-grounded initial inventory; not a final grant script or exhaustive per-route certification.** This section records the database operations visible in the inspected application entry points, operational scripts, migration environment and selected immutable-ledger migrations. It distinguishes ordinary application DML from capabilities that must be removed from general runtime identities. The inventory must be completed against the full route/model/query set and verified against live-like PostgreSQL sessions before exact grants are approved.

### 21.1 Evidence inspected and scope

Inspected source includes tenant/CP session construction and routing (`backend/core/database.py`, `backend/core/dependencies.py`); queue and worker entry points; HL7 listener; CP provisioning, fleet operations and CSV migration routes; Alembic environments for tenant and CP databases; backup, restore and index-maintenance scripts; audit mixins/models; and migrations that install append-only PostgreSQL triggers. This is a source review of the current `main` tree, not deployed database telemetry, a full static call-graph proof or a production permission audit.

The application uses SQLAlchemy ORM sessions for the majority of request/domain operations. The inspected tenant request dependency opens a tenant session after CP tenant lookup; the CP dependency opens a CP session. `AuditMixin` stamps actor IDs in SQLAlchemy `before_flush`; it does not require a separate database privilege. The tenant and CP runtime paths therefore need ordinary SELECT/INSERT/UPDATE/DELETE only on their respective mutable application tables, plus sequence and schema access. The exact table allowlist remains to be generated from model metadata and route/query usage; do not translate this summary into blanket grants on every table.

### 21.2 Workload-to-database operation matrix

| Workload / source path | Observed database operations | Required target capability | Must not inherit |
|---|---|---|---|
| Tenant clinical HTTP API (`get_db`, tenant domain routers/services) | ORM reads, inserts, updates and deletes across tenant clinical, identity, facility, finance, billing, diagnostics, pharmacy, procurement, workforce, privacy and related domain models. Audit actor stamping occurs in ORM flush. | Tenant-specific CONNECT; schema USAGE; SELECT/INSERT/UPDATE/DELETE on approved mutable tenant tables; sequence USAGE/SELECT where generated IDs are used; narrowly required type/function access. | CP DB, other tenant DBs, schema CREATE/DDL, ownership, role administration, database creation, TRUNCATE, REFERENCES/TRIGGER, cluster monitoring, backup/restore, or fleet-wide credentials. |
| Control-plane API (`get_control_db`, CP routers/services) | ORM CRUD over tenant registry, operator/access, pricing/billing metadata, federation node metadata, snapshots registry and CP audit logs; CP routing lookup is read-heavy. | CP-only CONNECT; schema USAGE; CRUD only on mutable CP tables; CP audit log SELECT/INSERT only; required sequence access. | Tenant clinical DBs, tenant credentials, tenant DDL, cluster provisioning, backup/restore and session termination. |
| CP provisioning route (`control_plane/api/routers/provisioning.py`) | CP metadata reads/writes; creates tenant database; invokes tenant Alembic upgrade; seeds tenant users/roles/reference data and federation configuration. | Split operation: CP API metadata DML; isolated provisioner for CREATE DATABASE/ownership/ACL; scoped tenant migrator for DDL; tenant initializer for approved seed DML. | No single CP web runtime identity should hold all these capabilities. |
| Fleet/support routes (`fleet_ops.py`) | CP registry CRUD; tenant aggregate/telemetry reads; federation key rotation and admin reset writes; `pg_stat_activity` inspection; `pg_terminate_backend`; sandbox `CREATE DATABASE ... WITH TEMPLATE`; schema-version reads; tenant migrations and seed; backup/restore launch. | Separate read-only aggregate/projection; tenant-bound audited support/key operations; privileged session-management/clone runner; scoped migration runner; backup/restore executor. | General CP API and tenant runtime must not have PG_SIGNAL_BACKEND, CREATEDB, template clone, DDL, backup or arbitrary tenant DB access. |
| CP CSV migration route (`control_plane/api/routers/migration.py`) | CP tenant lookup; tenant duplicate preview SELECT; tenant bulk import INSERT/UPDATE and related reads. | CP control-plane metadata plus delegated, tenant-bound import worker with only the selected tenant DB DML. | CP web process must not directly open arbitrary tenant DBs for preview/import. |
| Background worker (`worker.py`, `core/queue.py`) | Redis queue operations; registered task handlers may open CP and tenant sessions, including retention sweeps and other cross-tenant operational tasks. Queue itself does not require PostgreSQL. | Split CP scheduler/dispatcher, tenant-bound worker and privileged operations runner. Assign per-handler DML/read scope after handler inventory. | No shared worker credential capable of selecting every tenant DB; no synchronous fallback from CP/API that executes tenant work in producer context. |
| HL7 listener (`domains/integrations/listener.py`) | CP facility/interface lookup followed by tenant database processing/write of integration results. | CP-only ingress resolver plus a tenant-bound processor with assigned tenant DML; listener itself holds no fleet clinical credential. | No tenant clinical DB credential in network-facing ingress. |
| Federation source/destination paths | Source-side patient/pointer/allergy reads and transfer-log writes; destination-side patient/import writes and CP pointer/receipt metadata operations. | Source-owned read/release operation and destination-owned write operation, each in its own tenant-bound context; CP metadata access separately scoped. | No source process opens destination DB; no destination process opens source DB; no generic fleet tenant engine. |
| Tenant/CP Alembic runners (`backend/alembic/env.py`, `control_plane/alembic/env.py`) | DDL for tables, columns, indexes, constraints, enum types; data backfills; PostgreSQL PL/pgSQL function and trigger creation/removal; transaction advisory lock `pg_advisory_xact_lock`; migration-version table reads/writes. | Short-lived DDL-capable migrator scoped to exactly one target DB; ownership/default-privilege policy for all objects it creates; separately scoped CP migrator. | Runtime/API/worker credentials must not migrate or own schema objects. |
| Concurrent index maintenance (`scripts/build_indexes_concurrently.py`) | Catalog reads from `pg_index`, `pg_class`, `pg_namespace`; raw autocommit `CREATE INDEX CONCURRENTLY` and `DROP INDEX CONCURRENTLY`. | Explicit maintenance identity scoped to one target DB/schema, with controlled index DDL and audited invocation. | Runtime login and monitoring/exporter cannot create/drop indexes. |
| Backup daemon/manual backup (`scripts/backup_service.py`, host backup script) | CP registry SELECT; `pg_dump` of selected tenant DBs; host script also inventories databases and runs `pg_dumpall --globals-only`. | Dedicated executor with CP metadata read and per-DB dump access; a distinct, tightly controlled cluster-globals export identity/operation if globals backup is required. | No `pg_read_all_data` for a tenant-scoped identity by default; no backup credential in API, worker, onboarding portal or HL7 listener. |
| Restore/drill (`restore_tenant.py`, `restore_drill.py`, host restore script) | Isolated database creation, `pg_restore`, schema/object creation and data load; drill drops/recreates its disposable target; post-restore row/schema checks. | Isolated restore executor for an explicit non-live target; controlled owner/ACL normalization; separate approval for cutover. | Runtime identities cannot create/drop databases, restore, or route traffic to unverified targets. |
| Monitoring/exporter | PostgreSQL statistics/catalog reads via monitoring capability. | Dedicated `pg_monitor`-class read-only identity only if the exact exporter requires it; verify its effective view visibility. | No clinical table reads, application DML, DDL, backup or cluster admin. |

### 21.3 Minimum ordinary runtime privilege shape

The following is the initial least-privilege baseline to validate, not an instruction to apply grants immediately:

**Tenant runtime login**
- CONNECT only to its assigned tenant database.
- USAGE on the required application schema(s); no CREATE on schemas.
- SELECT/INSERT/UPDATE/DELETE only on mutable tables used by that tenant's HTTP/API and assigned worker operations.
- SELECT/INSERT only on immutable evidence/ledger tables where the business workflow appends and reads records; explicitly no UPDATE/DELETE on those tables.
- USAGE/SELECT on generated-ID sequences that the runtime inserts into; do not grant sequence UPDATE (which permits `setval`) unless a concrete runtime call site proves it is needed.
- USAGE on required enum/domain types and EXECUTE only on required functions. Do not blanket-revoke PUBLIC function/type privileges until built-in and custom dependencies are inventoried.
- No TEMPORARY, TRUNCATE, REFERENCES, TRIGGER, CREATE, ownership, role membership, BYPASSRLS, CREATEDB, CREATEROLE, REPLICATION, SUPERUSER, pg_monitor, pg_read_all_data or pg_signal_backend unless a specific reviewed runtime operation proves otherwise. No temporary-table use was identified in the inspected request paths.

**Control-plane runtime login**
- CONNECT only to the control-plane database.
- Schema USAGE; SELECT/INSERT/UPDATE/DELETE only on mutable CP metadata tables required by the CP API.
- SELECT/INSERT only on `control_plane_audit_logs`; the current immutability guard is a SQLAlchemy ORM event, not a PostgreSQL trigger, so table ACLs are necessary to prevent raw SQL or alternate clients from updating/deleting audit evidence.
- Required sequence USAGE/SELECT and narrowly required types/functions.
- No tenant DB CONNECT, tenant engine/credential access, DDL, CREATEDB, PG_SIGNAL_BACKEND, backup/restore or clinical data access.

The existing `postgres-roles.sql` blanket grants to all tables in `public` are not sufficient as a final policy. The grant plan must be table-aware and must account for future tables via creator-role-specific default privileges. Runtime should not inherit the migrator or owner role.

### 21.4 Append-only and immutable evidence tables found

The inspected PostgreSQL migrations/models identify the following table families where ordinary runtime UPDATE/DELETE grants should be withheld, in addition to their database trigger/ORM safeguards:

- `control_plane_audit_logs`: CP audit; ORM `before_update`/`before_delete` listeners only, no DB trigger found in the inspected model.
- `federation_transfer_logs`: PostgreSQL trigger rejects UPDATE/DELETE.
- `security_audit_export_register`: PostgreSQL trigger rejects UPDATE/DELETE.
- `procurement_supplier_payments` and `procurement_supplier_payment_allocations`: PostgreSQL append-only trigger.
- `procurement_bank_statement_batches`, `procurement_bank_statement_lines` and `procurement_supplier_payment_bank_matches`: PostgreSQL append-only trigger.
- `procurement_purchase_returns` and `procurement_purchase_return_items`: PostgreSQL immutable trigger.
- `procurement_patient_indent_issue_allocations` and `procurement_patient_indent_return_events`: PostgreSQL immutable trigger.
- `procurement_reconciliation_investigation_events`: PostgreSQL immutable trigger.
- `procurement_reconciliation_notification_config_events`: PostgreSQL append-only trigger.
- `procurement_reconciliation_governance_reports`: PostgreSQL immutable trigger.

The table list is a verified minimum from inspected migrations, not a guarantee that no other append-only/audit tables exist. Before generating grants, scan all model metadata, migrations and write call sites for audit/event/ledger semantics. Some workflow tables (for example payment requests or investigation case headers) are mutable and must not be confused with their immutable event/ledger companions. Append-only tables still need INSERT and usually SELECT; do not assume every such table is read-only.

### 21.5 Privileged operations that must leave ordinary runtime

1. **Database provisioning:** `ensure_postgres_db_exists()` queries `pg_database` and executes `CREATE DATABASE` using the shared configured URL. Move to a short-lived provisioner with explicit database-name allowlist, owner assignment and ACL setup.
2. **Connection termination:** `_terminate_db_connections()` calls `pg_terminate_backend` against sessions for a target DB. This requires a privileged signal capability (or superuser); it must not be granted to CP web or tenant runtime. Use an audited operations runner with explicit target binding.
3. **Sandbox clone:** fleet ops uses `CREATE DATABASE ... WITH TEMPLATE`, terminates source connections and scrubs the cloned tenant. This requires database creation/template-owner privileges and then tenant DML; split into a privileged clone executor plus a tenant-bound scrub operation.
4. **Migration and seed:** provisioning/sync currently invokes Alembic and universal seeding from CP request/operational paths. DDL and seed DML must be separate identities/steps, with no implicit role reconciliation side effects.
5. **Backup:** the daemon and host script currently use `POSTGRES_USER`; host backup additionally exports global roles. Separate tenant-scoped dump from cluster-global metadata export and isolate artifact storage.
6. **Restore:** current restore flows use the configured admin login to create/restore targets. Restore must be isolated and followed by explicit owner/ACL normalization and verification before routing.
7. **Concurrent indexes:** index maintenance uses raw DB-API autocommit and DDL; invoke only through the approved migration/maintenance runner.

### 21.6 Migration-specific SQL capabilities

The inspected Alembic environments use `pg_advisory_xact_lock` to serialize migration execution and apply transaction-local lock/statement timeouts. The tenant migration chain also contains PostgreSQL-specific enum alterations and custom PL/pgSQL trigger functions/triggers for immutable records. Migration identity therefore needs schema/object DDL and appropriate ownership of objects it creates; a normal runtime role must not receive these grants.

The application DML paths do not directly invoke the custom immutable trigger functions. PostgreSQL fires them as part of INSERT/UPDATE/DELETE processing; the trigger functions are created by migrations. The functions inspected are ordinary trigger functions (no `SECURITY DEFINER` declaration found in those definitions). If PUBLIC EXECUTE is later restricted, preserve the exact privileges required for trigger creation and all application-called built-ins/custom functions; verify with migration and runtime negative tests.

The Alembic advisory lock is a built-in function call, not a reason to grant arbitrary advisory-lock or administrative privileges. Migration table/index DDL, enum changes, trigger/function creation and data backfills remain migrator-only.

### 21.7 Backup and restore privilege details still to prove

The current tenant backup service invokes `pg_dump` as `POSTGRES_USER` and reads CP tenant registry metadata. The host script also queries database inventory and invokes `pg_dumpall --globals-only`. The repository does not yet prove that a non-superuser, per-tenant backup login can produce a complete dump for every supported object type. A disposable proof must include all tables, sequences, views, functions, enum types, extensions, large objects (if used), row-level security behavior and metadata required by restore.

A cluster-global roles/tablespaces export is not the same permission as dumping one tenant database. If required, run it under a separately controlled cluster backup identity and protect the artifact independently. The vault/file-copy process needs artifact access, not PostgreSQL credentials.

Restore currently uses `--no-owner --no-acl` in the host path and a separate encrypted restore helper for tenant snapshots. The exact owner/ACL behavior of each path must be tested. The restoring login must not become the permanent tenant runtime login by accident. After restore, explicitly set the intended database owner, schema/object owners, grants and default privileges, then verify before cutover.

### 21.8 Verification and inventory completion gates

Before drafting exact SQL grants, complete these steps:

1. Generate a deterministic table/sequence/type/function inventory from tenant and CP SQLAlchemy metadata and compare it with the live-like PostgreSQL catalogs after all migrations.
2. Map each route, background handler, listener operation and script to its actual ORM/raw SQL operations and target DB; identify cross-tenant loops and mixed-privilege processes.
3. Identify every append-only table and all write paths. Prove application workflows only INSERT/SELECT those records and do not rely on UPDATE/DELETE.
4. Inventory use of temporary tables, advisory locks, custom functions, extensions, large objects, COPY, TRUNCATE, setval, sequence reads, views/materialized views and row-level security. Absence from the inspected snippets is not proof of absence across the whole repository.
5. Test each role using independent PostgreSQL logins and sessions, including default ACLs, role membership, ownership, inherited privileges, PUBLIC grants and existing sessions.
6. Prove tenant A runtime cannot connect to tenant B or CP, CP runtime cannot connect to tenant DBs, and no ordinary process can call `pg_terminate_backend`, create/drop DBs or run DDL.
7. Prove append-only table runtime logins can SELECT/INSERT but cannot UPDATE/DELETE even when using raw SQL outside SQLAlchemy ORM hooks.
8. Prove backup/restore completeness and isolation on disposable data, including separate global export and owner/ACL normalization.
9. Re-run the PR #71 characterization tests as a baseline, then add acceptance tests that fail on current unsafe grants and pass only after approved remediation.

### 21.9 Disposition and limitations

The initial inventory shows that ordinary tenant and CP request traffic can be reduced to database-local, table-scoped DML, while provisioning, fleet support, migrations, index maintenance, backup and restore require separate privileged execution identities. It also identifies multiple append-only tables where table-level UPDATE/DELETE must be denied, not merely rejected by ORM hooks or triggers.

This inventory is not yet a complete route-by-route privilege map, does not prove deployed grants or PostgreSQL role attributes, and does not authorize implementation. The exact table grants, default privileges, ownership transfer and backup role strategy remain pending full metadata/query inventory and DBA/security review. No runtime, SQL, migration, Compose, credential, secret, database, patient-data or production change was made. PostgreSQL **database-per-tenant** remains invariant.


## 22. Source-declared SQLAlchemy model inventory — first-pass object baseline

**Evidence status:** static source inventory from the two declarative registries and the tenant Alembic import manifest; not yet an executed `MetaData` dump and not a live PostgreSQL catalog inventory. This section is intentionally not a grant script.

### 22.1 Registry separation and migration registration

The repository defines two independent declarative registries:

- Tenant database: `backend.core.database.Base`, declared in `backend/core/database.py`.
- Control plane database: `backend.control_plane.models.ControlBase`, declared in `backend/control_plane/models.py`.

Tenant Alembic targets `Base.metadata` and explicitly imports 23 model modules in `backend/alembic/env.py`: `abdm`, `audit`, `billing`, `bloodbank`, `clinical`, `diagnostics`, `encounters`, `facility`, `federation`, `finance`, `identity`, `insurance`, `integrations`, `patients`, `pharmacy`, `policies`, `privacy`, `procurement`, `quality`, `reports`, `service_ops`, `surgery`, and `workforce`. This explicit import list is the strongest source-backed declaration of the tenant migration model-registration boundary.

Control-plane Alembic targets `ControlBase.metadata` from `backend/control_plane/models.py`; it does not import the tenant model registry.

### 22.2 Tenant model table declarations

The following table names were extracted from literal `__tablename__` declarations in the listed model modules. Grouping is by source module, not a permission recommendation.

| Model module | Declared tables |
|---|---|
| `abdm` | `abdm_consent_artefacts`, `nhcx_claim_exchange_logs` |
| `audit` | `security_audit_export_register` |
| `billing` | `invoices`, `invoice_line_items`, `payment_receipts`, `patient_deposits`, `refund_vouchers`, `procurement_vendor_invoices`, `procurement_vendor_invoice_items`, `charge_capture_events` |
| `bloodbank` | `blood_bag_inventory`, `blood_cross_match_orders`, `radiology_study_metadata` |
| `clinical` | `encounter_vitals`, `clinical_notes`, `encounter_diagnoses`, `fluid_balance_logs`, `er_triage_assessments`, `medico_legal_cases`, `patient_comorbidities`, `encounter_physical_exams`, `birth_records`, `death_records`, `order_set_masters`, `order_set_items`, `clinical_early_warning_scores` |
| `diagnostics` | `service_categories`, `service_catalog`, `service_bundle_mappings`, `diagnostic_orders`, `diagnostic_tasks`, `lab_delta_check_configs` |
| `encounters` | `patient_encounters`, `inpatient_admissions`, `bed_transfer_logs`, `appointments`, `appointment_status_history`, `service_demand_requests`, `service_demand_status_history`, `appointment_waitlist_entries`, `appointment_waitlist_history`, `doctor_leaves` |
| `facility` | `floors`, `wards`, `physical_rooms_master`, `beds_master`, `nursing_shift_assignments` |
| `federation` | `federated_clients`, `federation_transfer_logs` |
| `finance` | `finance_expenses`, `finance_recurring_expenses` |
| `identity` | `departments`, `roles`, `permissions`, `role_permissions`, `users`, `auth_sessions`, `password_reset_tokens`, `mfa_recovery_codes`, `mfa_enrollment_codes`, `user_roles`, `doctor_profiles` |
| `insurance` | `insurance_providers`, `insurance_plans`, `insurance_plan_tariffs`, `patient_insurance_policies`, `insurance_pre_auths`, `insurance_claims` |
| `integrations` | `equipment_master`, `hl7_integration_logs`, `equipment_test_mappings` |
| `patients` | `chief_complaints_master`, `comorbidities_master`, `allergies_master`, `diagnoses_master`, `physical_examinations_master`, `patients`, `break_glass_grants`, `break_glass_uses`, `patient_allergies` |
| `pharmacy` | `medication_master`, `inventory_batches`, `prescriptions`, `prescription_items`, `medication_administration_logs`, `pharmacy_return_logs`, `controlled_substance_vaults`, `controlled_substance_movement_logs`, `bcma_scan_audit_logs` |
| `policies` | `hospital_policy_settings` |
| `privacy` | `patient_consent_records`, `privacy_retention_policies`, `privacy_policy_revisions`, `privacy_decision_audits`, `privacy_legal_holds`, `privacy_retention_run_ledgers`, `patient_data_rights_requests`, `privacy_data_breach_incidents` |
| `procurement` | `procurement_vendors`, `procurement_purchase_orders`, `procurement_po_items`, `procurement_grn`, `procurement_grn_items`, `procurement_purchase_returns`, `procurement_purchase_return_items`, `procurement_indents`, `procurement_indent_items`, `procurement_patient_indent_issue_allocations`, `procurement_patient_indent_return_events`, `procurement_vendor_invoices`, `procurement_document_download_audits`, `procurement_vendor_invoice_items`, `procurement_supplier_payments`, `procurement_supplier_payment_allocations`, `procurement_supplier_payment_requests`, `procurement_supplier_payment_request_allocations`, `procurement_bank_statement_batches`, `procurement_bank_statement_lines`, `procurement_supplier_payment_bank_matches`, `procurement_reconciliation_investigations`, `procurement_reconciliation_sla_policies`, `procurement_reconciliation_investigation_events`, `procurement_reconciliation_escalation_policies`, `procurement_reconciliation_notification_preferences`, `procurement_reconciliation_notification_config_events`, `procurement_reconciliation_notification_outbox`, `procurement_reconciliation_governance_reports` |
| `quality` | `clinical_quality_incidents`, `quality_indicator_benchmarks` |
| `reports` | `report_templates` |
| `service_ops` | `ambulance_vehicles`, `ambulance_dispatches`, `dietary_orders`, `cssd_instrument_sets`, `cssd_sterilization_batches`, `mortuary_cases`, `service_workflow_events`, `biomedical_waste_manifests`, `biomedical_waste_bags` |
| `surgery` | `operation_theatres`, `surgical_schedules`, `who_surgical_safety_checklists`, `operative_anesthesia_records`, `surgical_implant_logs` |
| `workforce` | `attendance_records`, `leave_requests`, `salary_profiles`, `payroll_periods`, `payroll_lines`, `payroll_calculation_events` |

### 22.3 Control-plane model table declarations

The `ControlBase` registry declares these 11 tables in `backend/control_plane/models.py`:

`tenant_registry`, `federated_nodes`, `global_patient_pointers`, `control_plane_audit_logs`, `tenant_snapshots_registry`, `module_catalog`, `bundle_catalog`, `blueprint_catalog`, `migration_schemas`, `control_plane_operators`, and `control_plane_operator_sessions`.

These are CP-database objects. Their names must not be included in tenant runtime grants. Conversely, tenant table names must not be included in the CP runtime allow-list.

### 22.4 Enum declarations and sequence caveats

The static model scan found enum classes in the following tenant modules:

- `billing`: `InvoiceStatusEnum`, `PaymentMethodEnum`, `DepositStatusEnum`, `VendorInvoiceStatusEnum`, `ChargeCaptureEventTypeEnum`.
- `bloodbank`: `BloodComponentTypeEnum`, `BloodBagStatusEnum`, `TransfusionReactionTypeEnum`, `DicomModalityEnum`.
- `clinical`: `FluidDirectionEnum`, `TriageAcuityEnum`, `MLCCauseEnum`, `DeliveryModeEnum`, `MannerOfDeathEnum`, `OrderSetItemTypeEnum`, `OrderSetPriorityEnum`, `EarlyWarningRiskEnum`.
- `diagnostics`: `ServiceTypeEnum`, `OrderStatusEnum`, `TaskStatusEnum`.
- `encounters`: `EncounterTypeEnum`, `EncounterStatusEnum`, `DiagnosisTypeEnum`, `AdmissionTypeEnum`, `DischargeDispositionEnum`, `AppointmentStatusEnum`, `ServiceDemandStatusEnum`, `ServiceDemandReasonEnum`, `ServiceDemandSourceEnum`, `AppointmentWaitlistStatusEnum`.
- `facility`: `WardTypeEnum`, `RoomTypeEnum`, `BedTypeEnum`, `BedStatusEnum`, `ShiftTypeEnum`.
- `finance`: `ExpenseCategoryEnum`, `ExpenseStatusEnum`, `RecurringFrequencyEnum`.
- `identity`: `GenderEnum`, `BloodGroupEnum`, `UserStatusEnum`.
- `insurance`: `InsuranceProviderTypeEnum`, `PreAuthStatusEnum`, `ClaimStatusEnum`.
- `integrations`: `ProtocolEnum`.
- `patients`: `AllergyCategoryEnum`, `AllergySeverityEnum`, `BodySystemEnum`.
- `pharmacy`: `MedicationFormEnum`, `PrescriptionStatusEnum`, `eMARStatusEnum`.
- `policies`: `FederationPolicyEnum`.
- `procurement`: `VendorCategoryEnum`, `POStatusEnum`, `GRNStatusEnum`, `IndentStatusEnum`, `VendorInvoiceStatusEnum`, `SupplierPaymentMethodEnum`.
- `quality`: `ClinicalIncidentTypeEnum`, `ClinicalIncidentSeverityEnum`, `ClinicalIncidentStatusEnum`.
- `reports`: `ReportTypeEnum`, `PageSizeEnum`, `PrintModeEnum`.
- `service_ops`: `BMWColorCategoryEnum`, `BMWBagStatusEnum`.
- `surgery`: `OTTheatreTypeEnum`, `SurgeryStatusEnum`, `AnesthesiaTypeEnum`.

The CP model declares `DeploymentModeEnum`, `PricingModelEnum`, and `BillingCycleEnum`.

No explicit SQLAlchemy `Sequence(...)` declaration was found in the scanned model files. Many integer primary keys use SQLAlchemy autoincrement conventions, but that does **not** prove the deployed PostgreSQL object names or whether each database version uses SERIAL-backed sequences versus identity columns. Do not generate sequence grants from naming guesses. The actual metadata objects and migrated PostgreSQL catalogs must be queried to enumerate generated sequences and enum type names, including schema, ownership and dependencies.

### 22.5 What this inventory does and does not prove

This source inventory establishes a first allow-list candidate universe for the two registries. It does not establish:
- that every listed model is actually imported in every runtime process before ORM use;
- that all live tables are represented by these models;
- that Alembic history has no manually created or legacy objects;
- that every model table is accessed by the general HTTP runtime;
- that all tables require CRUD rather than narrower operation-specific rights;
- exact sequence, enum, domain, view, materialized-view, function, extension or trigger inventory;
- actual PostgreSQL owner, ACL, PUBLIC, role-membership, default-privilege or RLS state.

The model declarations include both ordinary mutable entities and evidence/ledger tables. Do not infer DML rights from module membership. In particular, retain the immutable-table restrictions already recorded in Section 21; compare those lists against all model and migration objects before any grant design.

### 22.6 Required deterministic metadata and catalog extraction

Before preparing grant SQL, implement a disposable, no-production-access inventory runner that imports the same 23 tenant modules in the same order as tenant Alembic, imports `ControlBase`, and emits stable machine-readable output for each registry:
1. sorted table names, schema, columns, primary/foreign/unique/check constraints and indexes;
2. identity/autoincrement configuration and every metadata sequence, including associated table/column;
3. every Enum type name, native/non-native setting, schema and value set;
4. server defaults, computed columns, views/materialized views if represented, and explicit schema-qualified objects;
5. source module/class for each mapped table, including duplicate table/type declarations and import collisions.

Then, against a disposable PostgreSQL instance migrated from the repository's exact revisions, extract catalogs for relations, sequences, enum/domain types, functions/procedures, triggers, views, extensions, ownership, ACLs, default ACLs, memberships and PUBLIC grants. Diff source metadata against migrated catalogs and explain every extra/missing object. Include all handwritten migration SQL and operational scripts, not only Alembic autogenerate metadata.

Finally, map each table to concrete request routes, worker task handlers, listener paths and scripts, and mark operation classes separately: SELECT, INSERT, UPDATE, DELETE, sequence nextval/currval/setval, COPY, temporary objects, DDL, and maintenance. Use that mapping—not module names—to define runtime grants. The final allow-list must be generated deterministically, reviewed, and tested with independent PostgreSQL login sessions for CP, tenant A, tenant B, migrator, backup and monitoring identities.

**Implementation status:** documentation and source inspection only. No model, migration, SQL, runtime, Compose, credential, secret, database or production configuration was changed. PostgreSQL database-per-tenant remains mandatory.


## 23. Route, worker and listener to database-object operation map — first-pass source trace

**Evidence status:** bounded source trace of the currently inspected control-plane fleet/migration routers, federation router, queue handlers and application router registration. This is not a complete tenant-domain route audit. The method is to identify concrete model/table access and execution boundary; exact column-level or per-endpoint grants are not proposed here.

### 23.1 Runtime router registration and privilege domains

`backend/main.py` registers tenant-domain routers for authentication, patients, break-glass, FHIR, clinical, federation, reports/registers, UI, websocket, tenant policies, audit, OPD/ADT, facility, pharmacy, diagnostics, billing, insurance, surgery, blood bank, analytics, finance, integrations, procurement, service operations, privacy, workforce, ABDM and quality. This confirms the ordinary tenant API has a broad domain surface; it does not prove each route needs access to every model imported by a module.

`backend/control_plane/app.py` separately registers CP fleet operations, pricing, migration, provisioning, SaaS billing, UI console, network and operator authentication. Despite the separate app, some CP route handlers directly acquire tenant engines. Router separation alone therefore does not establish database capability isolation.

### 23.2 Control-plane fleet operations

Source: `backend/control_plane/api/routers/fleet_ops.py`.

| Endpoint | CP database objects observed | Tenant database objects / privileged operations observed | Operation and boundary finding |
|---|---|---|---|
| `GET /fleet/overview` | `tenant_registry` | Tenant engine reads; fleet aggregates include patient/bed/revenue indicators | CP SELECT plus cross-tenant clinical reads. Replace with approved tenant-produced aggregate projection; CP web must not connect to tenant DBs. |
| `GET /tenants` | `tenant_registry`, `federated_nodes`, `global_patient_pointers` | None established by this route's primary registry reads | CP SELECT. |
| `PATCH /tenants/{slug}/status` | `tenant_registry`, `federated_nodes`, `control_plane_audit_logs` | None in primary path | CP read/update of registry and node state; audit insert. |
| `PATCH /tenants/{slug}/deployment-mode` | `tenant_registry` | None established | CP registry read/update. |
| `POST /tenants/{slug}/rotate-keys` | `tenant_registry`, `federated_nodes`, `control_plane_audit_logs` | `federated_clients` in tenant DB | CP read/update + audit insert; tenant-bound federation key update must be delegated. |
| `POST /tenants/{slug}/reset-admin-password` | `tenant_registry`, `control_plane_audit_logs` | `users`, `auth_sessions`, `password_reset_tokens` | Tenant user read/update and session/token DELETE; privileged, audited tenant-bound support operation, not CP runtime DML. |
| `PATCH /tenants/{slug}/entitlements` | `tenant_registry`, `control_plane_audit_logs` | No tenant table DML established in primary path | CP registry update + audit insert. |
| `GET /tenants/{slug}/telemetry` | `tenant_registry` | Tenant telemetry reads | CP SELECT plus cross-tenant reads; replace with narrow approved read-only projection. |
| Backup list/trigger/restore endpoints | `tenant_registry`, `control_plane_audit_logs` | Host/filesystem/backup/restore executor; restore is privileged | CP metadata/audit only; separate backup/restore identity and process. |
| `POST /tenants/{slug}/clone-sandbox` | `tenant_registry`, `control_plane_audit_logs` | Executes `CREATE DATABASE ... WITH TEMPLATE`, terminates source connections, clones and scrubs tenant DB | Cluster provisioning/clone capability; never grant to CP web or tenant runtime. |
| `GET /fleet/schema-status` | `tenant_registry` | Connects to tenant DBs to read `alembic_version` | CP SELECT plus cross-tenant metadata probes; isolate to read-only fleet checker or report published status. |
| Tenant sync endpoints | `tenant_registry`, `control_plane_audit_logs` | Tenant Alembic migration and seed operations | CP metadata/audit plus DDL/seed runner. Migration role only; split fleet scheduler from per-tenant migrator. |
| `GET /tenants/{slug}/details` | `tenant_registry` | Tenant details/telemetry paths require further line-level decomposition | CP SELECT; tenant access must be replaced by approved projection if present. |
| `GET /federation/topology` | `tenant_registry`, `federated_nodes`, `global_patient_pointers` | Reads tenant federation policy | CP SELECT plus tenant policy read; prefer CP-authoritative projection or scoped policy service. |
| `GET /mpi/lookup` | `global_patient_pointers`, `control_plane_audit_logs` | No tenant patient row read established in primary lookup path | CP SELECT and audit insert. |
| `GET /fleet/audit-logs` | `control_plane_audit_logs` | None | CP audit SELECT only. |
| `GET /fleet/analytics` | `tenant_registry` | Reads tenant `users`, `invoices`, `patient_encounters`, `beds_master` or related aggregate source rows | CP SELECT plus cross-tenant tenant-data reads; publish minimal aggregates rather than granting CP web access. |
| SaaS charge endpoint | `tenant_registry`, `control_plane_audit_logs` | Tenant-specific billing context needs further decomposition | CP metadata/audit; isolate payment provider and tenant entitlement update path as separate capabilities. |

**Important audit distinction:** the method-level scan detects `db.add()`, `execute()` and `commit()` but cannot infer whether an ORM object was mutated in memory before commit. In particular, a commit on a route is not proof of INSERT-only behavior. The route-level classification above must be treated as candidate operation scope pending exact assignment/attribute-write inspection.

### 23.3 Control-plane CSV migration routes

Source: `backend/control_plane/api/routers/migration.py`.

| Endpoint | CP objects | Tenant objects | Operations / disposition |
|---|---|---|---|
| `POST /{slug}/analyze-csv` | `tenant_registry` SELECT | No tenant data access established in the analyze path | CP lookup and file/schema analysis. |
| `POST /{slug}/preview-mapping` | `tenant_registry`, `control_plane_audit_logs` | `patients`, `invoices`, `users` or dynamically selected registered entity models are inspected for duplicate/constraint preview | Tenant SELECT; CP audit INSERT. Preview must execute through a tenant-bound read capability. |
| `POST /{slug}/execute-node-mapping` | `tenant_registry`, `control_plane_audit_logs` | Dynamically selected entity model rows; duplicate lookup and bulk entity INSERT | Tenant SELECT + INSERT (and inspect dynamic conflict/update behavior before final grant); CP audit INSERT. Execute through a tenant-bound import worker with idempotency and durable operation state. |

The migration route dynamically selects entity models and fields based on mapping metadata. This is a strong reason not to infer a narrow grant list from its static imports alone. The allowed entity/table/column set must be explicit, validated and versioned before the worker receives a write capability.

### 23.4 Federation router

Source: `backend/domains/federation/router.py`.

| Endpoint | CP objects | Tenant objects | Operation / boundary |
|---|---|---|---|
| `POST /clients` | `federated_nodes` | `federated_clients` lifecycle/registration context | CP and tenant metadata writes. Separate partner registration/credential operation; no general tenant runtime key-management grant. |
| `GET /clients` | Federation partner metadata | None established | Read-only partner listing; exact CP/tenant source depends on helper path and must be confirmed in final route audit. |
| `DELETE /clients/{client_id}` | Partner metadata and audit path | Federated-client revocation context | Revocation is a write operation; preserve as separately authorized, audited capability. |
| Publish local patient pointer | `global_patient_pointers`, `tenant_registry` | Local `patients`, `patient_allergies`, `hospital_policy_settings` reads | Source tenant authorizes its own patient disclosure; CP pointer is a minimal discovery index. |
| Discover patient | `global_patient_pointers`, `tenant_registry` | Source tenant patient/allergy reads; `federation_transfer_logs` evidence writes | Source-owned read/release per tenant. Do not let destination or generic CP process connect directly to source clinical DBs. |
| Import patient | `global_patient_pointers`, `tenant_registry` | Source patient/allergy reads; destination `patients`, `patient_allergies` writes; destination/source transfer evidence paths | Split source read/release and destination write into separate tenant-bound capabilities. Preserve durable idempotency/recovery requirements tracked by AUD-003/PR #23. |

Federation is not safely modeled as one runtime identity with access to all participating databases. The source-side operation must execute under source ownership and policy; the destination-side operation must write only to the destination tenant. CP pointer metadata is not authorization to read a clinical record.

### 23.5 Background queue and HL7 ingress

Source: `backend/core/queue.py`; listener source previously inspected at `backend/domains/integrations/listener.py`.

Queue handlers currently registered in `backend/core/queue.py`:
- `email.send`: external email delivery; no PostgreSQL model access identified in this handler.
- `privacy.retention.execute`: resolves a tenant database and performs tenant retention work; tenant-bound worker operation with policy SELECT and data lifecycle operations. Exact affected tables and DELETE/update semantics require tracing the privacy service called by the handler.
- `privacy.retention.scheduled_daily_sweep`: enumerates active tenants from CP and enqueues tenant work; CP scheduler should have CP-only read/enqueue authority and must not open tenant clinical DBs.

The queue's tenant database selector and task payload are not authorization. The current shared tenant engine registry and synchronous fallback path remain incompatible with a strict tenant-bound worker boundary. Split CP scheduler, tenant-bound retention executor and privileged retention/deletion workflow where required.

HL7 listener source: `backend/domains/integrations/listener.py`. The listener resolves an inbound facility/interface to a tenant and processes ORU result writes. MSH-4/facility identifiers are untrusted routing inputs until matched to a trusted configured interface. Separate ingress resolution from tenant-bound result processing; ingress must not hold fleet-wide clinical DB credentials.

### 23.6 Candidate operation matrix by execution identity

| Execution identity / process | Candidate operation scope | Explicit exclusions |
|---|---|---|
| Tenant clinical API bound to one tenant | Table-scoped SELECT/INSERT/UPDATE/DELETE only for route-owned tables; immutable evidence tables SELECT/INSERT only | Other tenant DBs, CP DB, DDL, ownership, cluster administration, backup/restore |
| CP API | CP metadata SELECT and table-scoped registry/operator/config DML; CP audit SELECT/INSERT | Every tenant DB, patient/clinical rows, migrations, clone, backup/restore |
| CP fleet scheduler | CP registry SELECT and durable enqueue/operation-record writes | Tenant DB CONNECT, clinical rows, DDL |
| Tenant-bound retention worker | Tenant policy SELECT plus only the reviewed retention operation set for its single bound tenant | Other tenants, CP DB unless separately brokered, fleet credential access |
| Tenant-bound import worker | Approved target-table SELECT/INSERT and any specifically justified conflict operation | Arbitrary model/table selection, other tenants, DDL |
| Federation source worker | Source tenant policy/patient/allergy SELECT and source-owned release/evidence writes | Destination DB, unrelated tenants |
| Federation destination worker | Destination patient/allergy INSERT and destination evidence writes | Source DB, unrelated tenants |
| HL7 tenant processor | Single tenant result/order-related SELECT/INSERT/UPDATE as justified by processing path | Fleet tenant selection and other tenant DBs |
| Migration runner | DDL and migration data backfill on one explicitly selected target DB | General HTTP/worker runtime credentials |
| Provisioner/clone runner | Explicit database lifecycle and narrowly scoped session management | General CP/tenant runtime |
| Backup/restore executor | Tenant-scoped dump/restore and isolated artifact access; separate cluster-global export where approved | Clinical HTTP runtime and general worker |
| Monitoring/exporter | Catalog/statistics read-only access | Clinical table DML, DDL, backup/restore |

### 23.7 Completion gaps and next source-trace batch

This first pass does **not** yet cover every tenant domain router, nested router, service layer or repository abstraction. It does not yet trace the concrete retention service, HL7 processor call graph, billing/payment integrations, clinical workflows, pharmacy inventory, diagnostics, procurement, privacy, workforce, ABDM or reporting routes down to every mapped table and mutation. It also does not prove actual PostgreSQL grants.

Next required work:
1. Inventory each router registered by `backend/main.py`, including nested routers and service-layer calls; trace every mapped model/table and actual read/create/attribute-update/delete.
2. Trace queue handlers to the called service and enumerate affected objects, including bulk SQL and raw SQL.
3. Trace HL7 listener parsing, trusted interface resolution, tenant selection and final result/order writes.
4. Trace background schedulers, notification/outbox workers, exports and scripts; include all DB access paths.
5. Record each table's required operation set per identity, and compare with immutable-trigger tables from Section 21.
6. Add executable route/service-level SQL statement characterization and independent PostgreSQL role tests before any grant SQL is drafted.

**Implementation status:** documentation/source inspection only. No application code, SQL, migrations, Compose, credentials, secrets, database, patient data or production configuration changed. PostgreSQL database-per-tenant remains mandatory.


## 24. Tenant-domain route/service-to-object operation trace — evidence-backed sample (13 Nov 2026)

**Status:** Second bounded source-trace batch. This section records operations visible in the inspected route/service implementations. It is deliberately a sample, not a complete route inventory or final privilege allow-list. Operation labels describe the code path, not a recommendation to grant the general API role every listed right.

### 24.1 Billing API — `backend/domains/billing/router.py`

Observed paths and objects:

| Path / behavior | Source-declared objects | Observed operation shape | Privilege implication |
|---|---|---|---|
| Create invoice | `invoices`, `patients`, optionally `patient_encounters` | SELECT patient/encounter; INSERT invoice; refresh/read invoice | Invoice creation identity needs narrowly scoped INSERT plus the referenced lookup SELECTs. |
| List/read invoice and CSV export | `invoices`, related `invoice_line_items`, payment relation, optionally `patients`; privacy runtime also reads consent/policy data and records decision audit | SELECT with joins/count/pagination/export; privacy evaluation can add SELECT and audit INSERT | Read/export is not a pure invoice SELECT. Keep privacy evaluation and audit writes in the same transaction identity or split behind a narrowly defined service. |
| Add invoice line | `invoices`, `invoice_line_items`, `service_catalog`, price-resolution dependencies | SELECT invoice with row lock, SELECT catalog/pricing, INSERT line, UPDATE invoice totals/tax fields | This workflow needs invoice UPDATE as well as line INSERT; it should not imply UPDATE on all billing tables. |
| Remove draft line | `invoices`, `invoice_line_items` | SELECT/row lock; DELETE line; UPDATE invoice totals | DELETE is present in a draft-only path. It is not a basis for DELETE on finalized financial evidence or unrelated billing objects. |

Model and route imports additionally identify `PaymentReceipt`, `PatientDeposit` and `RefundVoucher`; their individual endpoint semantics and write patterns still require complete handler tracing. The `RefundVoucher` model docstring calls it an immutable financial audit voucher, but no DB trigger/ACL proof is inferred from that comment.

### 24.2 Pharmacy API — `backend/domains/pharmacy/router.py`

Observed paths and objects:

| Path / behavior | Source-declared objects | Observed operation shape | Privilege implication |
|---|---|---|---|
| Add/list/update/deactivate formulary item | `medication_master` | SELECT duplicate/existing row; INSERT; SELECT list; UPDATE attributes; deactivation is UPDATE of `is_active` | The DELETE HTTP verb for deactivation does not issue SQL DELETE in the inspected handler. Grant operation follows SQL behavior, not HTTP method name. |
| Receive/list inventory batch | `inventory_batches`, `medication_master` | SELECT medication; INSERT batch; SELECT batches with medication relationship | Batch receipt requires INSERT; listing requires SELECT. |
| Dispense/returns/controlled-substance workflows | Imported models include `prescriptions`, `prescription_items`, `pharmacy_return_logs`, `controlled_substance_vaults`, `controlled_substance_movement_logs`, `bcma_scan_audit_logs`; related billing models are also imported | Full mutation paths not exhaustively traced in this pass | Do not infer CRUD from imports. Continue handler-by-handler and identify immutable evidence/ledger tables before assigning writes. |

### 24.3 Diagnostics API — `backend/domains/diagnostics/router.py`

Observed catalog paths:

- Create category: duplicate-check SELECT on `service_categories`, then INSERT.
- List/get category: SELECT on `service_categories`.
- Update/deactivate category: SELECT then UPDATE; the HTTP DELETE handler deactivates by setting `is_active = False`, not SQL DELETE.
- Create service catalog item: duplicate-check SELECT on `service_catalog`, then INSERT.
- List/get service catalog item: SELECT on `service_catalog`.

The same router imports diagnostic order/task models and service functions that auto-bill and reverse cancelled-order billing. Their result-entry, verification, cancellation, billing side-effect and HL7-facing write paths need a separate complete trace; catalog observations do not establish those rights.

### 24.4 Privacy runtime — `backend/domains/privacy/runtime.py`

Observed policy evaluation path:

- Reads active `PrivacyPolicyRevision` and patient rows to derive age/context.
- Reads `PatientConsentRecord` rows for the requested patient IDs, purpose and active revision.
- Records decision audit rows through `_record_audits(...)`; the concrete audit model/table and bulk-write statement must be included in statement-level extraction.
- Some branches intentionally avoid loading patient rows when there is no active policy; the active-policy branch performs additional reads.
- This helper is called from billing and other patient-data disclosure paths, so its DB operations are transitive dependencies of those routes.

This is a key reason a route's directly imported business model list is not a sufficient privilege inventory.

### 24.5 HL7 listener — `backend/domains/integrations/listener.py`

Observed execution boundary:

1. `_tenant_hl7_config` reads `TenantRegistry` from `ControlSessionLocal` and obtains the tenant DB name plus encrypted shared secret.
2. Authentication compares the supplied secret using constant-time comparison.
3. `process_and_route_result` obtains a tenant engine by the resolved DB name and opens a tenant session.
4. The result processor receives the tenant session. Imports show it works with diagnostic tasks/orders, patient data and integration logs; exact DML must be extracted from `process_hl7_oru_r01_in_session` and its called helpers before assigning grants.

The listener process therefore currently has both CP lookup and tenant-engine connection capability. This code observation reinforces the split ingress-resolver / tenant-bound processor contract; it is not proof that authentication alone makes the shared tenant engine registry an authorization boundary.

### 24.6 Queue execution and transitive DB access

`backend/core/queue.py` declares `enqueue_task(..., sync_fallback=True)` by default. If Redis enqueue fails, the producer may invoke the registered handler inline. This means the producer's process identity can inherit the handler's database requirements, undermining a clean API/worker separation. The default and every call-site override must be included in the operation map; this contract does not authorize changing the default.

The queue module imports `ControlSessionLocal` and `tenant_engine_pool`. The retention scheduler and tenant retention executor must be traced separately, including policy revision reads, retention ledgers, legal holds, deletion/erasure operations and audit events. No blanket DELETE grant is implied.

### 24.7 Operation-map confidence and remaining work

The source evidence above supports only the specific operation shapes stated. It does not prove complete transitive ORM flush behavior, cascades, database triggers, raw SQL, bulk DML, background task registration, route coverage, or deployed grants. SQLAlchemy relationship cascades and database-side trigger effects must be included in the eventual statement/catalog characterization.

Required next batch:
1. Complete each pharmacy dispense, return and controlled-substance handler.
2. Complete diagnostic order lifecycle, task result/verification and auto-billing/reversal service paths.
3. Trace all billing payment, deposit, refund, discount, reconciliation and RCM handlers.
4. Trace clinical, patient, encounter, identity, surgery, insurance, blood bank, procurement, workforce, ABDM, quality, service-ops and report routers to transitive model/service calls.
5. Trace privacy retention scheduler/executor and all worker/outbox/notification handlers, including inline fallback call sites.
6. Capture SQLAlchemy emitted statements and raw SQL against disposable migrated tenant/CP databases; map statement types to exact relation/sequence/type/function objects.
7. Compare this map against immutable evidence tables in Section 21, then test the proposed per-workload operation matrix using independent PostgreSQL sessions.

**No runtime code, SQL, migrations, Compose, credentials, secrets, databases, patient data or production settings were changed.** Database-per-tenant remains the required architecture. No final grants are approved by this source trace.
