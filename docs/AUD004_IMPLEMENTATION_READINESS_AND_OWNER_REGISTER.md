# Avinya HMS — AUD-004 Implementation-Readiness Report

**Report date:** 2026-11-13  
**Repository:** `Perseus37/avinya_hms_v2`  
**Assessment type:** Repository-level architecture and security readiness; no production inspection  
**Decision:** NOT READY for AUD-004 implementation or federation activation  
**Storage architecture baseline:** PostgreSQL database-per-tenant

---

## 1. Executive summary

The project direction remains **one PostgreSQL database per tenant**. This report does not recommend schema-per-tenant, a tenant-storage migration, or a change to the chosen architecture.

The most important gap is not a missing JSON document schema. It is that the current code's database-per-tenant routing does not yet establish a database-per-tenant *credential boundary*:

- `build_db_url(db_name)` changes the database name on the URL derived from the single configured `settings.DATABASE_URL`.
- The tenant engine registry creates engines from that URL builder. The inspected code does not show a per-tenant database credential lookup.
- The federation router resolves a source tenant's database name from control-plane metadata and opens a source tenant session through `tenant_engine_pool.get_engine(source_db_name)`.
- Therefore, database names are separated, but the inspected application path still uses the shared configured PostgreSQL credential. Effective PostgreSQL grants and production deployment configuration have not been inspected, so this report does **not** claim that the credential is a superuser or that production exposure has been proven.

This is the first engineering blocker to resolve. A destination request/import process must not open a foreign tenant database session. The source tenant must own and enforce the source read through an independently authenticated boundary, with PostgreSQL grants and workload identity preventing bypass.

AUD-004 remains a release blocker. The design PR chain has produced useful threat analysis, but the next work should be evidence-driven and bounded—not another automatic sequence of design PRs.

## 2. Terminology — avoid the schema confusion

Three separate concepts must not be conflated:

1. **Database-per-tenant:** each tenant has a separate PostgreSQL database. This is the selected project direction.
2. **PostgreSQL schema:** a namespace inside a PostgreSQL database (for example, `public`). This report does not propose one schema per tenant.
3. **JSON Schema:** a JSON document validation specification used by earlier design documents to describe evidence/API payload shapes. It does not create PostgreSQL namespaces, databases, tables or migrations.

A fourth related concept is a normal database migration: PR #19 adds a control-plane table named `federated_discovery_receipts`. Adding a table through Alembic is not a schema-per-tenant architecture change.

## 3. Repository facts and evidence boundaries

### 3.1 Confirmed from inspected code

| Area | Observed repository behavior | Readiness implication |
|---|---|---|
| Tenant URL construction | `build_db_url(db_name)` derives from `settings.DATABASE_URL` and changes the database name | No per-tenant credential selection is visible in this path |
| Tenant engine registry | `TenantEngineRegistry.get_engine(db_name)` uses `build_db_url(db_name)` | Engine cache is keyed by database name, not by an independently provisioned tenant credential identity |
| Federation source reads | Federation router obtains source `db_name` from control-plane `TenantRegistry`, then creates a source session from the tenant engine registry | Destination-side process can open a foreign tenant session in the inspected design |
| Control plane | Stores tenant registry/routing metadata including database name | Routing metadata must not become permission to retrieve arbitrary tenant credentials |
| Tenant storage model | Code routes sessions to a tenant database name | Database-per-tenant is the implemented topology; schema-per-tenant is not evidenced |
| PR #19 migration | Adds `federated_discovery_receipts` to the control-plane database | This is a control-plane table migration, not a tenant-schema migration |

### 3.2 Not inspected / not proven

The repository review did not inspect live production PostgreSQL catalogs, role memberships, database ACLs, object ownership, secret-manager policies, deployed environment variables, workload identity, network policies, poolers/proxies, backup/restore access, or production patient data.

Consequently, the following are unknown:
- whether the configured PostgreSQL login is superuser, owner, or narrowly restricted;
- whether tenant database CONNECT and object privileges are isolated in the deployed cluster;
- whether runtime containers receive cluster, migration, provisioning or cross-tenant credentials;
- whether a network boundary already prevents direct cross-tenant connections;
- whether production secrets differ from local/default configuration.

These are evidence requests, not assumptions.

## 4. PR and decision status

All statuses below were re-checked at report preparation time.

| PR | Purpose | State | Assessment |
|---|---|---|---|
| #19 | AUD-001–003 runtime remediation | Open, unmerged | Separate runtime change; requires its own code/test review and must not be treated as solving AUD-004 source identity |
| #44 | Database-per-tenant identity ADR proposal | Draft, unmerged | Correctly retains database-per-tenant; not yet formally accepted |
| #67 | Independent review of DBID-R66–R73 | Draft, unmerged | Records R74–R81 residual findings |
| #68 | Consolidated R74–R81 requirements proposal | Draft, unmerged | Useful requirements clarification; not implementation evidence |
| #69 | Independent review of PR #68 | Draft, unmerged | R74 Critical and R75–R81 High remain open |

No PR is merged by this report. No PR is authorized for merge by implication.

## 5. Architecture decision

### ADR-BASELINE: retain PostgreSQL database-per-tenant

**Decision direction:** KEEP DATABASE-PER-TENANT.

- One tenant maps to one PostgreSQL database.
- Do not migrate tenants into separate PostgreSQL namespaces inside a shared tenant database.
- The control-plane database remains separate from tenant patient databases.
- Database names are routing identifiers, not security credentials.
- Each tenant's runtime/source workload must use an independently scoped database identity/credential.
- A tenant A application/import worker must be unable to connect to tenant B's database at the PostgreSQL authorization boundary.
- Local cross-branch access follows the same source-owned authorization model as remote federation; locality is not a bypass.
- A future alternative storage topology would require a separate business case, threat model, ADR and migration plan. It is not part of this remediation.

**Governance status:** this is the confirmed project direction for this report. The related PR #44 ADR proposal remains draft/unmerged and still requires formal architecture/security/database-owner acceptance.

## 6. Prioritized implementation-readiness gates

### P0 — establish real tenant database identity isolation

**Why first:** until foreign database connectivity is denied independently of application code, a source authorization service can be bypassed by any process holding a broad database credential.

Required actions:
1. Inventory every PostgreSQL cluster and database, including control-plane and template databases.
2. Capture role attributes, role memberships, database ACLs, object ownership, schema/table/function/sequence grants, default privileges, privileged functions, extensions and cross-database paths.
3. Identify every credential available to API, worker, federation, admin/support, migration, provisioning and backup workloads.
4. Define non-login owners and separate runtime app, source, migration, provisioning and backup identities.
5. Create tenant-specific login identities/credentials with database allowlists and least-privilege object grants.
6. Remove cluster-wide/provisioning/migration credentials from ordinary runtime workloads.
7. Prove with negative connection tests that tenant A app/import/source identities cannot connect to tenant B's database.
8. Prove that the control-plane runtime cannot read tenant patient databases.
9. Review network paths and secret-manager policy as defense in depth.
10. Test credential rotation, connection drain, revocation, restore and pooler behavior.

**Exit evidence:** signed cluster inventory; effective privilege report; credential-to-workload map; secret policy evidence; network matrix; reproducible two-tenant negative tests; independent database/security sign-off.

### P0 — enforce source-owned federation access

**Why:** the inspected federation router directly creates sessions for source tenant databases. This must be removed from destination request/import paths and other alternate paths.

Required actions:
1. Enumerate all source-DB access paths: HTTP routes, root/V1 aliases, local/remote federation, jobs, admin/support, retries, recovery, CLI and tests.
2. Create a source-owned API/workload that derives its tenant identity from provisioned configuration and authenticated workload identity.
3. Ensure the source workload can retrieve only its own tenant credential.
4. Ensure destination workloads have no foreign tenant DSN, credential or engine/session capability.
5. Route local cross-branch requests through the same source-owned protocol; do not retain an in-process/direct-SQL bypass.
6. Enforce source clinician identity, affiliation/status, action, purpose, destination, resource and policy checks before source disclosure.
7. Make source authorization/audit failure deny before protected data is returned.
8. Remove direct source ORM/entity materialization from destination federation code.
9. Test root/V1 parity and all internal/background/support/recovery bypass surfaces.

**Exit evidence:** source service identity proof; static search report; DB-denied bypass tests; API and workload authentication tests; audit ordering tests; independent architecture/security sign-off.

### P1 — close AUD-001–003 remediation safely

PR #19 includes a control-plane discovery receipt migration, pointer synchronization failure propagation, explicit source failure/partial-result handling, and additional import security tests. It is a separate runtime PR and must be reviewed on its own merits.

Before merge:
- rerun full CI on the exact PR head and inspect all required checks;
- review migration upgrade/downgrade and retention behavior;
- verify the discovery receipt cannot be replayed or rebound to another destination/source/purpose;
- verify source failure and timeout cannot produce a false complete response;
- resolve concurrent duplicate import races and unique-constraint conflict behavior;
- ensure destination commit followed by pointer-sync failure is recoverable and cannot report full completion prematurely;
- remove demographic/ABHA/phone-based identity reuse as a substitute for exact source provenance;
- prove idempotency and recovery with independent PostgreSQL sessions and failure injection;
- independently review the full diff and branch ancestry.

**Important:** PR #19's direct source-session path is visible in the inspected federation router. It is not a substitute for the P0 source-owned boundary. Do not infer that a green test suite proves tenant credential isolation.

### P1 — resolve remaining AUD-004 governance and protocol decisions

The independent review of PR #68 leaves:
- **R74 Critical:** verifiable revocation authority proof and effective-time semantics;
- **R75 High:** sole-egress boundary and transport ordering evidence;
- **R76 High:** immutable wire profile and cryptographic verification contract;
- **R77 High:** authenticated polling/redemption API, binding and idempotency;
- **R78 High:** complete cluster-wide PostgreSQL ACL inventory and independent verifier;
- **R79 High:** executable lifecycle graph and failure/recovery model;
- **R80 High:** provider-specific root/snapshot/pagination completeness evidence;
- **R81 High:** trusted worker platform measurement and independent attestation.

These need named owners, selected technologies/providers and objective evidence. No additional automatic proposal/review PR cycle is recommended. Prepare decisions and implementation evidence in a bounded work plan.

### P2 — clinical, privacy and operational acceptance

Before any pilot or production activation, record named accountable owners and approvals for:
- source clinician proofing and registration/affiliation revocation;
- allowed purposes, actions, resource categories and destination scope;
- local cross-branch scope (D-11 project direction YES is not formal approval);
- audit content, retention, access, tamper evidence and residency;
- post-commit revocation/quarantine, clinical use restrictions and downstream orders;
- legal hold, correction, backup expiry and disposal;
- incident response, break-glass policy (emergency federation remains disabled);
- support/admin access and dual control;
- data residency, privacy/legal review and patient-notification/rights handling where applicable.

## 7. Accountable owner register

Names are intentionally not invented. Assign named individuals in the project governance record.

| Workstream | Accountable owner role | Required decision/evidence |
|---|---|---|
| Storage architecture | Project architect / architecture owner | Confirm database-per-tenant ADR and supported deployment modes |
| PostgreSQL isolation | PostgreSQL/database owner | Roles, ACLs, object ownership, grants, catalog inventory and negative tests |
| Tenant secret lifecycle | Platform/security owner | Workload identity, per-tenant secret policy, rotation/revocation and pool draining |
| Federation source boundary | Backend/domain owner + application security | Source-owned service, no foreign direct DB sessions, route/job/recovery parity |
| Clinician trust | Identity/security owner + clinical governance | Proofing, issuer trust, immutable subject mapping, affiliation and revocation |
| Protocol/cryptography | Security/cryptography owner | Revocation proof, wire profile, key custody, signatures, encryption and test vectors |
| Clinical disclosure | Clinical governance owner | Purpose/action/resource approval, minimum necessary fields, quarantine and clinical use |
| Privacy/legal | Privacy officer / legal owner | DPDP/GDPR/HIPAA applicability, retention, residency, legal hold and rights |
| Provider inventory | Cloud/platform owner | Root-of-scope, snapshot/pagination guarantees, completeness witness |
| Worker hardening | Platform/SRE owner | Measured host/workload controls, attestation and host-admin threat model |
| Backup/restore | Database/DR owner | Isolation, quarantine restore, credential rotation and evidence |
| Release approval | Independent security reviewer + project owner | Final release gate; cannot be pre-approved by a design PR |

## 8. Bounded next-work plan

The next work should be engineering evidence, not more design PRs.

**Phase A — non-production discovery (no patient data):**
- inventory code paths, runtime identities, database roles, secrets and network routes;
- build a synthetic two-tenant PostgreSQL environment;
- prove current cross-tenant connection behavior;
- document gaps without changing production.

**Phase B — approved isolation implementation:**
- implement tenant-specific identities/secret retrieval and source-owned boundary in a separate approved engineering plan;
- keep federation feature flags off;
- add negative DB, API, workload and bypass tests;
- validate migration and rollback in disposable environments.

**Phase C — protocol implementation readiness:**
- resolve R74–R81 with named owners and selected providers/platforms;
- produce executable test vectors, verifiers and non-production evidence;
- complete D-01–D-14 governance and clinical/privacy/security approvals.

**Phase D — independent release review:**
- review exact source commit, CI, migrations, effective DB grants, workload identities, secrets, network controls, audit evidence, recovery and feature-flag defaults;
- no pilot/production activation until all blockers have objective evidence and explicit approval.

Stop if any unknown/unsupported privilege, identity, route, provider scope or host control could permit a cross-tenant read or unlogged disclosure.

### 8.1 Concrete source-owned federation extraction seam

A fresh read of `backend/domains/federation/router.py` and `backend/core/database.py` on `main` identifies the first runtime seams. This is a code-path map, not authorization to change runtime behavior.

| Current code path | Observed behavior | Required boundary change |
|---|---|---|
| `discover_and_aggregate_patient_across_branches()` | Reads global pointers and tenant registry metadata, resolves foreign DB names, then submits each pointer to nested `_fetch_branch_data()` | Keep only non-PHI routing metadata in the destination. Replace each foreign DB session with a typed source-service request after the approved challenge/assertion flow exists. |
| Nested `_fetch_branch_data()` | Calls `tenant_engine_pool.get_engine(branch_db_name)`, reads source policy/patient/allergies, calls `evaluate_tenant_data_use(... actor_user_id=None)`, writes `FederationTransferLog`, commits, then returns source-derived data | Move selector resolution, source policy, actor authorization, minimal data selection and source audit into the source-owned workload. A node API key plus `actor_user_id=None` is not verified clinician authorization. |
| `import_federated_patient_locally()` | Resolves a foreign `TenantRegistry.db_name`, opens `tenant_engine_pool` source session, re-reads patient/policy/allergies and writes source transfer log from destination request | Destination must consume a source-authenticated, operation-bound response; it must not open a source DB session or accept a client-supplied summary as provenance. Reconcile with PRs #23/#24 import operation, fencing and provenance requirements before implementation. |
| `TenantEngineRegistry.get_engine(db_name)` / `build_db_url(db_name)` | Accepts a DB name and changes the database component of the shared `settings.DATABASE_URL` | Do not use this generic registry from a tenant-facing federation request to reach foreign databases. Preserve it only where separately approved operational workloads require it; later split identities by workload and tenant under an independently reviewed rollout. |
| `ensure_postgres_db_exists(db_name)` | Builds a connection to the `postgres` database from the same configured URL and can create databases | Keep provisioning/admin capability out of API and source-disclosure runtime identities. This is a separate privileged-operational-workload gate, not part of the first federation route extraction. |

#### Safe implementation order after wire-profile approval

1. Freeze the normative wire profile by reconciling PR #30 with the outstanding R74/R76/R77 review findings. It must specify exact parsing/validation rules, approved crypto profile, issuer trust, audience and workload identity, actor mapping, operation binding, nonce/replay transaction, revocation effective time, anti-enumeration behavior, response integrity and negative test vectors. Do not choose these in application code.
2. Define a source-service interface whose configuration fixes exactly one source tenant identity and one source database credential. Its request type must have no DB locator, DSN, tenant override, SQL/model/table selector or caller-controlled actor role.
3. Implement and test the source workload independently against synthetic tenant B: it resolves its own tenant DB, authenticates destination and clinician under the approved profile, evaluates current policy, commits source audit before response, and cannot connect to tenant A.
4. Implement the destination client with only destination-A DB access and source-service transport. Prove it cannot retrieve B credentials and cannot reach B PostgreSQL directly.
5. Replace the discovery nested foreign-session function and import foreign-session block with that client. Preserve the existing route contracts only where the reviewed protocol permits; do not retain an alternate in-process/local-branch direct-SQL path.
6. Reconcile discovery and import with the accepted PR #23/#24 durable operation, fencing, provenance, response-integrity and acknowledgement state machine. Do not infer a new idempotency model from the current demographic matching logic.
7. Run the synthetic proof matrix from actual workload containers, including source outage/no-fallback, audit commit failure, replay/concurrency, revocation, response substitution and local cross-branch parity. Keep emergency federation denied.

#### Explicit pre-implementation stop

PR #30 is still a proposed design and explicitly leaves cryptographic algorithms, key custody, trust onboarding and operational lifetimes open. The current source-owned proof contract also says no wire profile is selected. Therefore the present evidence supports a precise extraction plan, but **not yet a safe runtime federation implementation**. The next implementation must wait for a reviewed, approved wire-profile artifact and named source-service/database/platform owners. No production role, secret, network, deployment, tenant registry or connection-routing change is authorized by this report.

## 9. Explicit non-authorization

This report authorizes documentation and non-production synthetic-data assessment only. It does not authorize:
- runtime code changes or application refactoring;
- production PostgreSQL role, database, ACL, network or secret changes;
- production credential creation, retrieval, rotation or revocation;
- production patient-data access, import or export;
- partner onboarding or clinician trust provisioning;
- local/remote federation or emergency federation activation;
- pilot, deployment, release or merge.

AUD-004 remains a release blocker. PRs #19, #44, #68 and #69 remain open/unmerged as last verified. Keep design PRs draft until formal decisions are recorded. No schema-per-tenant migration is proposed.


## 10. Source-code access inventory — main branch

**Inventory basis:** repository tree and source files fetched from `main` at the report base commit `c1f8a8a175a9f7dd6538bfdc1630ad6e996baaf5`. This is static source inspection only. It does not establish deployed process boundaries, effective grants, runtime configuration or production reachability.

| Path / symbol | Observed access pattern | Classification / required disposition |
|---|---|---|
| `backend/core/config.py::Settings.DATABASE_URL` | Constructs a PostgreSQL URL from the shared `POSTGRES_USER`, `POSTGRES_PASSWORD`, host and port settings | Shared credential source. Must not be treated as a tenant credential resolver |
| `backend/core/database.py::build_db_url` | Changes only the database name on `settings.DATABASE_URL` | Confirms that tenant database routing in this helper does not select a tenant-specific login |
| `backend/core/database.py::ensure_postgres_db_exists` | Connects to the `postgres` database using the same URL builder and executes `CREATE DATABASE` when absent | Provisioning/admin capability is imported into the general database module; isolate behind a dedicated provisioning identity/process |
| `backend/core/database.py::TenantEngineRegistry.get_engine` | Creates an engine for any supplied database name using `build_db_url`; cache key is database name | General-purpose cross-database engine factory. Must be replaced or constrained so a tenant runtime cannot request arbitrary tenant databases |
| `backend/core/database.py::get_db` | Resolves tenant metadata, then obtains engine by `ctx.db_name` | Normal request path is tenant-routed, but relies on the shared credential path above |
| `backend/domains/federation/router.py::discover_and_aggregate_patient_across_branches` | Resolves pointer branch codes to database names and calls `tenant_engine_pool.get_engine(branch_db_name)` inside the discovery route | Direct foreign-tenant source reads from the destination-side API process; P0 source-owned boundary |
| `backend/domains/federation/router.py::import_federated_patient` | Resolves source registry and calls `tenant_engine_pool.get_engine(source_registry.db_name)`, then reads patient/policy/allergy data and writes a source transfer log | Direct foreign-tenant source read/write from the destination-side import request; P0 source-owned boundary |
| `backend/control_plane/api/routers/provisioning.py::provision_hospital` | Calls `ensure_postgres_db_exists`, runs tenant migrations, then creates a tenant engine/session to seed tenant data; stores tenant database name and encrypted JWT/backup keys in control-plane registry | Privileged provisioning workflow. Separate its database-admin, migration and tenant-seeding identities from ordinary API credentials; provision per-tenant runtime identity and grants |
| `backend/control_plane/api/routers/migration.py` | Vendor migration preview and background execution call `tenant_engine_pool.get_engine(tenant.db_name)` | Control-plane ETL has broad tenant database access. Treat as a privileged, separately authenticated migration workload; do not share its capability with ordinary API or federation workers |
| `backend/scripts/backup_service.py::_dump_and_encrypt` | Runs `pg_dump` with `POSTGRES_USER` / `POSTGRES_PASSWORD`; backup cycle iterates active tenant registry rows and dumps each tenant database | Central backup workload has cluster-wide tenant read capability by design. Give it a dedicated backup principal, explicit database allowlist and isolated execution identity; never expose its credential to API/federation |
| `backend/scripts/restore_tenant.py::restore_encrypted_backup` | Calls database creation helper and runs `pg_restore` using the shared configured PostgreSQL login against the caller-supplied target database name | Highly privileged restore path. Separate restore identity, require approved target binding, quarantine and audit; do not make this available to request-serving workloads |
| `backend/worker.py` | Queue worker imports Redis/queue code; no direct tenant DB engine creation is visible in this file | Not evidence that registered task handlers are database-free. Inventory every registered handler and its imports/call graph before granting the worker a DB identity |

### 10.1 Immediate conclusions

1. **The shared credential issue is directly visible in source.** `DATABASE_URL` is assembled from one `POSTGRES_USER` / `POSTGRES_PASSWORD` pair; `build_db_url` changes only the database name. No per-tenant DB login selection appears in the inspected path.
2. **The federation bypass is not hypothetical at code level.** Discovery and import routes explicitly open sessions to other tenant databases through the same engine registry. This is a source-code fact; whether PostgreSQL would permit the connection in a particular deployment depends on effective grants and network controls that remain uninspected.
3. **Privileged control-plane workflows need a different treatment from tenant request-serving workloads.** Provisioning, ETL migration, backup and restore may legitimately need elevated capabilities, but those capabilities must be separated by workload, narrowly scoped, audited and unavailable to the federation/API process.
4. **Do not solve this by merely adding a tenant password column and passing it to the existing arbitrary engine factory.** The source-owned boundary must ensure the destination cannot obtain a source credential or ask a shared privileged service to act as an unrestricted confused deputy.
5. **The static inventory is not complete for worker handlers or every indirect call site.** A follow-up repository-wide call-graph/search pass is required for all imports of `tenant_engine_pool`, `build_db_url`, `ensure_postgres_db_exists`, `create_engine`, `pg_dump` and `pg_restore`, including scripts, tests, CLI and deployment entrypoints.

### 10.2 Required synthetic two-tenant proof

In a disposable PostgreSQL cluster only, create synthetic tenants A and B and distinct workload identities. Capture reproducible evidence for:

- A's ordinary API identity can connect to A and is denied `CONNECT` to B.
- B's ordinary API identity can connect to B and is denied `CONNECT` to A.
- A's federation/discovery/import workload cannot connect to B, even when supplied B's database name.
- A source-owned service can read only its own tenant database and rejects a request whose authenticated workload/tenant binding does not match its provisioned source identity.
- Control-plane runtime cannot connect to either patient database.
- Provisioning, migration, backup and restore identities have only their explicitly approved capability sets; those identities are absent from ordinary API/federation containers.
- Role membership, `PUBLIC` grants, database ACLs, schema/table/function/sequence grants, default privileges, ownership, privileged functions and connection pooler behavior are included in the effective-privilege evidence.
- Tests run from the actual container/network identity of each workload, not only from a developer shell.

No live database, credentials, production secrets or patient data were accessed for this inventory.


## 11. Extended inventory — workers, deployment and operational scripts

**Inventory basis:** additional static inspection of `main` at `c1f8a8a175a9f7dd6538bfdc1630ad6e996baaf5`. These findings describe checked-in source/configuration only. A Compose `env_file` reference proves that the service is configured to receive that file; it does not reveal the actual secret values or prove the deployed file contents.

### 11.1 Background task worker

| Path / symbol | Observed behavior | Isolation implication |
|---|---|---|
| `backend/worker.py::run_worker_loop` | Dispatches task names to handlers registered in `backend.core.queue.registry` | Worker is a distinct process, but its task registry determines its data-access capability |
| `backend/core/queue.py::handle_retention_execute` | Resolves an active tenant by subdomain in `ControlSessionLocal`, then calls `tenant_engine_pool.get_engine(db_name)` and opens a tenant session | The general worker can open a tenant DB selected by task payload/control-plane lookup using the shared engine registry |
| `backend/core/queue.py::handle_scheduled_retention_sweep` | Enumerates every active tenant from the control plane, opens each tenant DB, inspects approved retention policies and enqueues work | This handler intentionally traverses the tenant fleet; it must not run under the ordinary API/federation identity |
| `backend/core/queue.py::handle_email_send` | Sends email through the mailer and does not directly open a tenant DB in the inspected handler | Lower database privilege requirement; suitable for a separately scoped worker class if task routing is split |

The checked-in queue module registers three built-in handlers: `email.send`, `privacy.retention.execute` and `privacy.retention.scheduled_daily_sweep`. This is not a complete transitive call-graph of code imported by each handler or future plugin/task registration.

### 11.2 Compose environment sharing

| File / service | Observed configuration | Required disposition |
|---|---|---|
| `docker-compose.prod.yml::api` | Loads `.env.production` | Keep only API-required credentials; no provisioning, backup, migration or fleet-wide DB identity |
| `docker-compose.prod.yml::worker` | Loads the same `.env.production` | Split task classes and give each worker only the credentials required for its assigned handlers |
| `docker-compose.prod.yml::onboarding-portal` | Also loads `.env.production` | Separate control-plane onboarding identity from tenant runtime and database-admin capabilities |
| `docker-compose.prod.yml::hl7-listener` | Loads `.env.production` | Determine whether HL7 ingestion needs a tenant DB connection; if so, bind it to a tenant-specific source identity, not a fleet-wide login |
| `docker-compose.yml::backup-sidecar` | Loads `.env` and runs `backend/scripts/backup_service.py --daemon` | Dedicated backup process, but the shared environment file includes the common configured DB login path in this Compose model |
| `docker-compose.yml::backup-vault` | Loads `.env` although its command is vault mode | Review and remove unnecessary database credentials from the vault-only process environment |
| `docker-compose.prod.yml::postgres-exporter` | Builds `DATA_SOURCE_NAME` from `POSTGRES_USER` and `POSTGRES_PASSWORD` | Give monitoring a read-only monitoring principal with only required statistics access; do not reuse tenant application credentials |

The production Compose configuration also gives the API, worker and onboarding portal access to the same internal network. Network membership alone does not prove database authorization, but it means the deployment file does not establish a network-level separation between those processes. Effective database grants, firewall rules and deployed secrets remain uninspected.

**Deployment caveat:** the checked-in production Compose file does not declare the development Compose `backup-sidecar` service. Do not infer that the production backup daemon is deployed through that file; identify its actual scheduler/container/host deployment before assigning a production control owner.

### 11.3 Operational and maintenance scripts

| Path / symbol | Observed behavior | Classification |
|---|---|---|
| `backend/scripts/bootstrap.py` | Uses configured `POSTGRES_USER` / `POSTGRES_PASSWORD` for database-level operations; reset path includes `DROP DATABASE IF EXISTS`; provisions control-plane/default tenant DBs and loops tenant registry entries for migrations/seeding | High-risk bootstrap/reset utility. Restrict to disposable development or a controlled provisioning environment; require explicit target allowlist and non-production guard |
| `backend/scripts/migrate.py` | Uses database URL / `ensure_postgres_db_exists`, can migrate one database or iterate active tenants | Privileged migration workload; separate credentials and execution identity from API, worker and onboarding |
| `backend/scripts/build_indexes_concurrently.py` | Accepts arbitrary `--database-url`, supports `--control-plane` and `--all-tenants`; all-tenants mode iterates active registry rows and creates engines from tenant URLs | Fleet-wide maintenance capability; restrict invocation, credential scope and audit; arbitrary URL mode is a direct credential-handling surface |
| `backend/scripts/backup_service.py` | Uses configured PostgreSQL username/password for `pg_dump`, iterates active cloud tenants, and decrypts each tenant's backup key from the control-plane registry | Dedicated backup identity required; backup key access and DB read access must be separately governed |
| `deployments/backup-postgres.sh` | Queries `pg_database`, dumps control-plane and tenant-prefixed databases, and exports PostgreSQL globals using `POSTGRES_USER` / `POSTGRES_PASSWORD` | Cluster-wide backup/global metadata capability; keep out of application containers and protect global role export |
| `deployments/restore-postgres.sh` | Checks target database, creates it with `POSTGRES_USER` as owner, and runs `pg_restore` using the configured login | Cluster-level restore capability; approval-bound target, isolated restore identity and quarantine required |
| `backend/scripts/restore_tenant.py` | Restores to a supplied target database using the shared configured login and database-creation helper | Same restore isolation requirement; reject arbitrary target binding in production |
| `backend/scripts/restore_drill.py::run_restore_drill` | Uses configured or caller-supplied PostgreSQL credentials; connects to `postgres`, drops/creates a drill DB, restores and later drops it | Destructive cluster-level capability even though the intended target is a synthetic drill DB; run only with a dedicated disposable-cluster identity and strict target guard |
| `backend/scripts/validate_production_env.py` | Checks required environment variables, including `POSTGRES_PASSWORD` | Configuration validation only in the inspected file; not evidence that secrets are least-privileged |

### 11.4 Revised P0 workload inventory

The credential-to-workload matrix must include at least:

- API request-serving process;
- onboarding/control-plane portal;
- HL7 listener and any integration consumers;
- email-only worker;
- retention/fleet-sweep worker;
- federation source service (not yet established by the inspected runtime path);
- provisioning/bootstrap;
- tenant and control-plane migration;
- concurrent index maintenance;
- backup dump process;
- backup vault process;
- restore and restore-drill processes;
- PostgreSQL exporter/monitoring;
- any external scheduler, CI job, operator shell or host-level maintenance process.

Do not grant all these workloads one common database login merely because they share a Compose environment file or Python image. Split credentials by capability and remove unused secrets from each process environment. For fleet-wide maintenance, use a separately approved, short-lived and audited identity rather than an ordinary tenant runtime credential.

### 11.5 Next evidence collection — no runtime changes

1. Obtain the deployment owner's redacted service-to-environment-variable map. Never copy secret values into this repository report.
2. Establish where production backup, restore, migration and index-maintenance commands actually run; the production Compose file alone does not enumerate all operational execution environments.
3. Inspect registered task handlers and their transitive imports, then classify each task by tenant DB access, control-plane access, filesystem, external service and destructive capability.
4. Capture actual container network attachments and effective PostgreSQL role/database/object grants from an approved non-production cluster.
5. Build synthetic A/B tests from each workload's real container identity and network namespace. Verify denied cross-tenant `CONNECT`, not merely a denied application API request.
6. Confirm the API, onboarding, HL7 and worker processes cannot read secret-manager entries or environment variables assigned to provisioning, backup, restore or migration identities.
7. Treat all maintenance utilities that accept arbitrary database names or URLs as privileged interfaces; require an explicit target allowlist and audited invocation.

No Compose files, runtime code, environment files, database roles, credentials or deployed infrastructure were changed during this review.


## 12. Recommended workload identity separation plan

**Disposition:** recommended implementation sequence for architecture/security owner review. This section is not an accepted ADR, governance approval, runtime change request, or production authorization. The database-per-tenant topology remains unchanged.

### 12.1 Target workload-to-identity matrix

| Workload | Target identity boundary | Permitted database capability | Explicitly prohibited |
|---|---|---|---|
| Tenant A API | Tenant A-bound runtime identity; no tenant B secret access | Tenant A database application grants only | Tenant B database CONNECT, source-only privileges, control-plane admin |
| Tenant A source disclosure service | Tenant A-bound source workload identity and source DB credential | Tenant A minimum source-policy, actor-mapping, patient/resource read and source-audit objects | Any other tenant DB, provisioning, migration, backup or restore |
| Tenant A import operation | Destination A-bound identity | Tenant A destination import/provenance/idempotency objects | Direct source DB session; source secret retrieval |
| Control-plane API | Control-plane workload identity | Control-plane registry/routing metadata only | Patient/resource objects in any tenant DB; cluster administration |
| Onboarding portal | Separate control-plane onboarding identity | Only approved onboarding/control-plane operations | Tenant clinical DBs and cluster administration |
| Email worker | Email-only identity | No tenant DB access unless a demonstrated handler dependency requires it | Tenant registry-wide or patient DB access |
| Retention execution worker | Explicitly authorized tenant-bound execution identity | One tenant DB per execution, only approved retention objects | Fleet-wide credentials in the ordinary worker process |
| Retention scheduler | Separate scheduler identity | Control-plane metadata and enqueue capability; no tenant clinical DB reads if policy evaluation can be moved to tenant-bound execution | Reusing the ordinary API or email worker DB identity |
| HL7 listener | Tenant-bound integration identity selected by trusted routing | Only the destination tenant DB and required integration objects | Arbitrary tenant DB selection or source federation DB access |
| Provisioning | Short-lived provisioning identity | Create approved tenant DB and provision roles; no routine patient query | API/worker runtime and federation disclosure |
| Migration | Short-lived migration identity bound to explicit tenant DB allowlist | DDL required for the selected migration target(s) | Runtime request handling and arbitrary fleet traversal |
| Backup | Dedicated backup identity and isolated backup workload | Read/backup capability for explicitly approved DB allowlist; control-plane key access separately scoped | API, federation, interactive clinical queries |
| Backup vault | Vault identity | Object-store/filesystem vault operations only | PostgreSQL credentials and control-plane DB credentials |
| Restore / DR drill | Separate recovery identity, isolated target cluster or quarantined target | Restore to an approved, bound target; drill identity limited to disposable drill DBs | General runtime use; arbitrary production target; unreviewed global role restore |
| PostgreSQL exporter | Monitoring identity | Required statistics/monitoring views only | Tenant application tables and write privileges |

**Hard-boundary rule:** a process that possesses usable credentials for tenant A and tenant B can technically attempt cross-tenant access, even if normal application routing intends otherwise. For a strict workload-compromise boundary, do not give one tenant-facing process a secret-manager policy or credential bundle covering every tenant. Prefer tenant-bound runtime instances/workload identities (or a separately reviewed isolation mechanism with equivalent enforceable guarantees). A shared process with a fleet-wide credential cache is not an acceptable substitute.

### 12.2 Sequence and gates

**Phase 0 — confirm deployment facts (read-only).**
- Deployment owner supplies a redacted inventory of service names, image/command, environment-variable names, secret references, mounts, network attachments, schedulers and host/CI execution points.
- Database owner supplies non-production PostgreSQL role membership, ownership, database ACL, PUBLIC grants, object grants, default privileges and privileged-function inventory.
- Confirm actual production backup, restore, migration and index-maintenance execution points; do not assume development Compose services exist in production.
- Gate: owners and evidence are recorded; no secret values or patient data enter GitHub documentation.

**Phase 1 — define enforceable identity and ACL contracts.**
- Approve the database-per-tenant identity ADR and name the security principals by workload class.
- Define the per-tenant application/source role split, ownership model, database CONNECT policy, PUBLIC privilege revocation, role memberships, object grants and credential rotation/revocation semantics.
- Verify that database owners, inherited roles, CREATEDB, CREATEROLE, superuser, replication and predefined roles cannot bypass the intended boundary.
- Decide how a tenant-bound API/source workload is scheduled and routed without a shared process receiving every tenant secret.
- Gate: independent reviewer can demonstrate how a compromised tenant A workload is technically denied tenant B access.

**Phase 2 — implement a non-production vertical slice for two synthetic tenants.**
- Provision disposable tenant A and B databases with distinct application and source identities.
- Run the real API/source process images under distinct workload identities and secret policies.
- Prove A can connect to A and is denied CONNECT to B; prove B can connect to B and is denied A.
- Prove destination A cannot connect to source B, while an authenticated source B service can read only B's approved objects.
- Verify revocation, credential rotation, pool drain, stale connection handling, connection-string leakage controls and failure-closed behavior.
- Gate: automated negative tests execute from the actual container/network identity; no developer-shell-only evidence.

**Phase 3 — split background and operational workloads.**
- Remove retention/fleet traversal from the general-purpose worker identity. Route each tenant's retention execution to a tenant-bound worker; keep scheduling/enqueue authority separate from tenant DB access.
- Separate email-only tasks from tenant-data tasks.
- Give provisioning, migration, index maintenance, backup, vault, restore and DR drill dedicated identities and isolated execution entrypoints.
- Remove unnecessary database secrets from onboarding, HL7, email, vault, monitoring and ordinary API environments.
- Gate: inspect effective process environments and secret-manager policies; verify denied access from each workload.

**Phase 4 — federation source ownership.**
- Replace destination-side foreign tenant_engine_pool.get_engine(...) reads in discovery/import with authenticated source-service calls.
- Apply the same protocol to local cross-branch and remote federation.
- Source service derives tenant DB from its own identity/configuration; callers cannot supply a DB name, DSN, secret reference or tenant override.
- Verify clinician assertion, source actor mapping, purpose/action/scope, policy, revocation and source audit before selector-specific patient data is disclosed.
- Gate: repository call-graph and runtime tests show no destination API/import/worker path can open a foreign tenant engine.

**Phase 5 — independent verification and release gate.**
- Independent security reviewer verifies role/catalog evidence, secret policy, container identity, network reachability, negative tests, task routing, recovery isolation and audit evidence.
- Re-run the full relevant test suite and migration/backup/restore validation against disposable non-production databases.
- Resolve all Critical and High findings with evidence before any pilot or production authorization.
- Production rollout, data migration, federation activation, trust provisioning, partner onboarding and merge remain separate explicit approvals.

### 12.3 Critical implementation constraints

1. Do not add a tenant password field to TenantRegistry and let request handlers choose arbitrary tenant DSNs. Secret storage and retrieval must be bound to a workload identity, not merely a tenant identifier supplied by a caller.
2. Do not retain a generic build_db_url(db_name) capability in ordinary runtime packages if it can combine a broad credential with an arbitrary database name.
3. Do not rely on PostgreSQL CONNECT ACLs alone. Validate ownership, role membership, PUBLIC, object privileges, default privileges, privileged functions and any role-switching path.
4. Do not assume separate containers are isolated when they share the same secret bundle, database login and unrestricted network path.
5. Do not put cluster-admin, CREATEDB, migration, backup, restore or global role-export credentials into API, source disclosure, import, email, HL7 or ordinary worker containers.
6. Do not allow the source service to become a confused deputy. It must authorize the caller and exact operation before it resolves or releases patient-specific data.
7. Preserve independent audit and recovery behavior. A source authorization/disclosure record must not be represented as committed until the source transaction confirms it.
8. Keep all proof data synthetic and all database experiments on a disposable non-production cluster.

### 12.4 Immediate next deliverable

The next useful engineering artifact is a **two-tenant non-production identity proof specification**: exact role/ACL assertions, per-workload secret-access assertions, container-level connection attempts, expected PostgreSQL SQLSTATEs, source-service authorization cases, and evidence artifacts. It should be reviewed before SQL migrations or application refactors are authored. This avoids implementing credentials or schema changes before the workload boundary and deployment topology are agreed.

No implementation was performed as part of this readiness update.


## 13. Two-tenant non-production identity proof specification

**Status:** test/evidence specification only. It intentionally does not contain executable SQL, migrations, credentials, or deployment changes. Run only on a disposable PostgreSQL cluster with synthetic records and synthetic identities.

### 13.1 Fixture and identity inventory

Create one disposable cluster with:
- control-plane database CP;
- tenant databases A and B, representing two independent clinics/tenants;
- synthetic patient/resource rows in each tenant, with deliberately distinguishable non-sensitive fixture identifiers;
- source-only federation policy, actor-mapping and audit objects in each tenant;
- isolated workload identities for A API, A source service, A import worker, B API, B source service, control-plane runtime, email worker, migration, provisioning, backup, restore-drill and monitoring.

Use distinct credentials for each workload identity. No test identity may inherit a cluster administrator, database owner, tenant B, tenant A or unrelated workload role. Keep credential values out of logs, test reports and Git.

### 13.2 Database-level negative and positive assertions

| Test ID | Attempt | Expected result | Evidence |
|---|---|---|---|
| DB-01 | A API connects to A | Allow | Successful connection from A API container identity |
| DB-02 | A API connects to B | Deny with PostgreSQL insufficient-privilege SQLSTATE 42501 | Captured SQLSTATE and role/database ACL snapshot |
| DB-03 | B API connects to B | Allow | Successful connection from B API container identity |
| DB-04 | B API connects to A | Deny with SQLSTATE 42501 | Captured SQLSTATE and ACL snapshot |
| DB-05 | A source service connects to A | Allow | Successful source-service connection |
| DB-06 | A source service connects to B | Deny with SQLSTATE 42501 | Captured SQLSTATE and role/database ACL snapshot |
| DB-07 | B source service connects to B | Allow | Successful source-service connection |
| DB-08 | B source service connects to A | Deny with SQLSTATE 42501 | Captured SQLSTATE and role/database ACL snapshot |
| DB-09 | Control-plane runtime connects to CP | Allow | Successful control-plane connection |
| DB-10 | Control-plane runtime connects to A or B | Deny with SQLSTATE 42501 | Captured SQLSTATE and ACL snapshot |
| DB-11 | A API reads a source-only policy/audit object in A | Deny with SQLSTATE 42501, where the approved role model separates those objects | Object privilege snapshot and failed query |
| DB-12 | A source service reads the approved source objects in A | Allow | Successful narrowly scoped query |
| DB-13 | A API attempts SET ROLE to A source, migration, owner or admin role | Deny; expected SQLSTATE 42501 for a role it is not a member of | Membership graph and failed SET ROLE attempt |
| DB-14 | Runtime role attempts CREATE DATABASE, CREATE ROLE, role membership grant, owner change or protected DDL | Deny | Captured SQLSTATE and catalog privilege snapshot |
| DB-15 | A runtime connects after PUBLIC CONNECT has been revoked and only explicit grants remain | A permitted tenant role succeeds; every unlisted tenant role fails | Effective database ACL and live connection attempts |

**SQLSTATE interpretation:** 42501 is the expected authorization-denial code for an existing database whose CONNECT privilege is denied. A failure such as 3D000 (invalid catalog/database name) is not a passing isolation test; it means the test may have targeted a nonexistent database. Record the actual SQLSTATE, server identity and target database for every attempt.

### 13.3 Catalog and privilege evidence

Capture before and after snapshots for:
- all cluster roles and attributes, including SUPERUSER, CREATEDB, CREATEROLE, REPLICATION, BYPASSRLS, LOGIN and connection limits;
- role membership edges, including inherited membership and SET ROLE options;
- database owner, ACL, CONNECT and TEMPORARY privileges, including PUBLIC;
- schema, table, sequence, function and type ownership and grants;
- default privileges for future objects;
- security-definer functions, extension ownership and privileged routines;
- replication, backup, monitoring and predefined PostgreSQL roles;
- active sessions, connection poolers and database endpoints used by each test container.

For each workload role, prove both the positive allowlist and the negative cross-tenant cases. A static ACL query is supporting evidence, not a substitute for a real connection attempt from the workload's actual container identity.

### 13.4 Secret and workload identity assertions

| Test ID | Attempt | Expected result |
|---|---|---|
| SEC-01 | A API workload retrieves A API credential | Allow only if the approved secret policy requires runtime retrieval |
| SEC-02 | A API workload retrieves B API or B source credential | Deny at secret-manager authorization layer |
| SEC-03 | A source workload retrieves A source credential | Allow |
| SEC-04 | A source workload retrieves B source credential | Deny |
| SEC-05 | A import worker requests a source database credential | Deny; it must call the source service instead |
| SEC-06 | Email worker requests any tenant DB credential | Deny |
| SEC-07 | Backup vault requests PostgreSQL credential | Deny |
| SEC-08 | API, onboarding, HL7 and ordinary worker process environments are inspected | No provisioning, migration, backup, restore or unrelated tenant secret is present |
| SEC-09 | Secret rotation revokes old credential after approved pool drain | Old credential cannot establish a new connection; new credential succeeds only for its bound tenant |
| SEC-10 | Runtime logs, exception traces and metrics are inspected | No DSN, password, token, secret payload or raw clinical fixture is exposed |

If a design uses a tenant-bound workload instance, the workload identity must be independently attested by the secret manager. A caller-supplied tenant ID or secret name is not proof of tenant identity.

### 13.5 Source-owned federation authorization cases

Execute through the real source-service endpoint using synthetic actors and records. For every denied case, verify that no patient-specific response body or selector-dependent distinction is released. Exact external status/body behavior must follow the approved anti-enumeration protocol contract.

| Test ID | Source request condition | Required outcome |
|---|---|---|
| SRC-01 | Valid destination workload, valid clinician assertion, correct audience/source/destination, allowed purpose/action/scope | Source authorizes only the bounded request and returns minimum permitted data |
| SRC-02 | Missing or malformed workload authentication | Reject before source database selector resolution |
| SRC-03 | Invalid signature, untrusted issuer/key or wrong audience | Reject before patient-specific selector resolution |
| SRC-04 | Assertion names a different source or destination | Reject; do not silently rewrite tenant or destination binding |
| SRC-05 | Clinician is unmapped, inactive, revoked or not affiliated with the source | Reject without disclosing candidate existence |
| SRC-06 | Purpose, action, resource or scope is not authorized | Reject without patient-specific disclosure |
| SRC-07 | Revocation is effective before source release linearization point | Reject and record the authoritative revocation decision |
| SRC-08 | Request nonce/operation is replayed or selector commitment differs | Reject or return only the exact idempotent prior result permitted by the approved protocol |
| SRC-09 | Source policy denies one candidate/resource | Do not disclose that candidate/resource; preserve approved non-enumerating outcome |
| SRC-10 | Required source authorization/disclosure audit commit fails | Fail closed; no protected response is released |
| SRC-11 | Source DB is unavailable or source audit cannot be confirmed | Return the protocol-defined unavailable/indeterminate result; never claim successful disclosure |
| SRC-12 | Destination A attempts direct SQL connection to source B while also calling B source service | Direct SQL is denied; only the authenticated source-service path can disclose authorized data |

### 13.6 Pool, revocation and lifecycle tests

- Revoke a tenant database CONNECT grant, then prove new connections are denied. Separately prove that already-open pooled sessions are drained/terminated; do not assume ACL revocation closes existing sessions.
- Rotate tenant A credentials and prove tenant B credentials and sessions are unaffected.
- Revoke a source workload identity and verify both secret retrieval and source endpoint authentication fail within the documented revocation bound.
- Restart the workload after revocation to prove stale in-memory credentials cannot silently re-establish access.
- Verify the source service fails closed if tenant binding, policy generation, revocation status, audit commit or DB identity is unavailable.
- Verify connection pools are keyed by immutable tenant/workload identity, never only by caller-supplied database name.
- Verify provisioning, migration, backup and restore jobs have explicit target allowlists and cannot be triggered through ordinary API/task payloads.
- For restore drills, verify the drill principal can create/use/drop only its disposable drill database and cannot drop or restore over A, B or CP.

### 13.7 Evidence package and acceptance criteria

The proof run produces:
1. fixture manifest containing synthetic tenant IDs and database names only;
2. workload-to-image/container/network/secret-reference map with secret values redacted;
3. PostgreSQL role membership and privilege catalog snapshots;
4. positive and negative connection results with SQLSTATE, timestamp, workload identity and target database;
5. object-level permission and role-switch test results;
6. secret-manager allow/deny decision evidence;
7. source authorization case outcomes and audit correlation IDs;
8. pool drain, credential rotation and revocation timing evidence;
9. test command, immutable code revision and environment manifest;
10. independent reviewer disposition for every failed or waived assertion.

**Pass criteria:** all required positive cases succeed; all cross-tenant and privilege-escalation negative cases fail for the intended authorization reason; no secret or patient fixture is disclosed; source audit failure prevents disclosure; and the reviewer can reproduce the evidence from the recorded revision and disposable environment.

**Automatic fail conditions:** cross-tenant connection succeeds; any runtime identity can assume a privileged role; a destination process can read a foreign tenant DB; a source response is released without required source audit; a denied connection is counted as a pass because the target DB was missing; or the test was run only from a developer shell rather than the workload container identity.

No executable test, SQL, migration, credential, secret policy, container or runtime configuration was created or changed by adding this specification.


## 14. Existing PostgreSQL role bootstrap and test-harness gap

Additional source inspection of \`main\` confirms that the repository already contains a role bootstrap. It must be treated as an existing partial control, not as proof that tenant isolation is implemented.

### 14.1 Existing role script is not a tenant identity model

Inspected: \`deployments/postgres-roles.sql\`.

The script creates cluster-wide login roles \`hms_app\`, \`hms_migrator\`, \`hms_backup\` and \`hms_exporter\`. The following gaps are visible in the checked-in SQL:

1. \`hms_app\` receives \`CONNECT\` on database \`postgres\`, and object grants on schema \`public\` in the database where the script is executed. The script does not provision a distinct application role and explicit CONNECT/object ACL for every tenant database.
2. \`hms_migrator\` similarly receives broad grants in the database where the script is executed; the script does not bind it to an approved tenant migration target.
3. \`GRANT pg_read_all_data TO hms_backup\` grants the predefined cluster role to the backup login. This is not a per-tenant backup boundary; it can confer read access across databases where the predefined role applies. Effective reach still depends on PostgreSQL behavior, connection access and deployment grants, which require catalog verification.
4. The script does not define per-tenant source-service identities, source-only object grants, tenant-specific secret retrieval policy, or an ownership/membership model preventing privilege escalation.
5. The SQL does not explicitly revoke PUBLIC CONNECT/TEMPORARY or demonstrate a complete ACL inventory. Absence of those statements is not proof of current PUBLIC grants; inspect the effective catalogs.

Consequently, these roles are useful starting labels for workload classes but do not establish the required database-per-tenant isolation.

### 14.2 Bootstrap applies roles with the configured cluster login

Inspected: \`backend/scripts/bootstrap.py\` and production Compose \`db-init\`.

- \`apply_database_roles()\` connects to the \`postgres\` database using \`settings.POSTGRES_USER\` and \`settings.POSTGRES_PASSWORD\`, then executes the role SQL.
- Production \`db-init\` invokes \`python backend/scripts/bootstrap.py --apply-roles\` and receives \`.env.production\`.
- The same bootstrap then provisions databases, upgrades the control-plane database, and upgrades/seeds tenant databases using URLs built from the same configured database login.
- The bootstrap source therefore does not demonstrate that the application runtime switches to \`hms_app\`, that tenant-specific identities are provisioned, or that the configured login is removed from ordinary services.
- Production API, worker, HL7 listener and onboarding portal still reference the same \`.env.production\` file in Compose.

This is a code/configuration observation. The actual values in deployed environment files and the effective privileges of \`POSTGRES_USER\` were not inspected.

### 14.3 Current automated tenancy tests do not prove PostgreSQL ACL isolation

Inspected: \`tests/conftest.py\`, \`tests/test_01_system_and_tenancy.py\`, \`tests/test_23_compose_redis_config.py\`, \`tests/test_40_background_worker_and_queue.py\`.

- The shared \`multi_tenant_env\` fixture creates the control-plane and tenant databases using in-memory SQLite engines and monkeypatches \`tenant_engine_pool.get_engine\` to return an engine by database-name dictionary lookup.
- This is useful for application routing and tenant-context behavior, but it cannot prove PostgreSQL database CONNECT denial, role membership, ownership, PUBLIC ACL, secret-manager access or network isolation.
- Existing Compose tests parse YAML and assert selected configuration values. They are static configuration checks, not container identity or live database authentication tests.
- Existing worker tests use an in-memory \`FakeRedis\` and exercise queue/dispatch lifecycle. They do not run the worker with distinct PostgreSQL workload credentials.
- Existing restore-drill tests mock \`create_engine\`; they do not prove that a recovery identity is unable to target another tenant database.

**Required test strategy:** retain fast SQLite tests for request routing and domain behavior. Add a separate opt-in integration suite that provisions disposable PostgreSQL tenant A/B databases and real non-superuser roles, then runs positive/negative connection and object-privilege tests from the same container images and workload identities intended for deployment. CI must fail closed or mark the integration suite explicitly not-run when the disposable PostgreSQL service is unavailable; it must never silently substitute SQLite for an ACL proof.

### 14.4 Consequence for implementation order

Do not simply change \`DATABASE_URL\` to \`hms_app\` and assume the design is complete. First define and test:
- how a tenant-bound process obtains only its own credential;
- how control-plane access remains separate from tenant clinical access;
- how per-tenant database roles and object grants are provisioned and rotated;
- how migration, provisioning and backup roles are isolated from runtime;
- how the source service receives only its own tenant credential;
- how the ordinary worker is split so fleet-wide scheduling cannot imply fleet-wide patient DB access.

The existing bootstrap/role SQL should be revised only after the two-tenant disposable-cluster proof demonstrates the intended role topology. No role SQL, bootstrap code, Compose file, test fixture, credential or database was changed by this inventory update.


## 15. Disposable PostgreSQL proof harness — environment boundary and execution plan

### 15.1 Do not reuse the default development Compose project

Inspection of the checked-in \`docker-compose.yml\` on \`main\` found:
- PostgreSQL uses the persistent named volume \`hms_pgdata\`.
- PostgreSQL, \`db-init\`, and application services load the project \`.env\`.
- \`db-init\` runs \`python backend/scripts/bootstrap.py\`.
- The default Compose project also starts the wider application stack.

Therefore, the default Compose project is not an acceptable disposable ACL-test target. A test run must not point at a developer's normal \`hms_pgdata\`, use \`.env\` credentials, invoke the normal bootstrap, or rely on a developer's existing PostgreSQL cluster.

### 15.2 Dedicated harness boundary

The implementation should add a dedicated opt-in test harness (for example, \`deployments/aud004-proof/\`) with these properties:

1. A separate Compose project name and isolated network, with no shared application network.
2. A pinned PostgreSQL image matching the supported project major version.
3. No published host port by default; test containers reach PostgreSQL only over the isolated test network.
4. A uniquely named disposable volume or ephemeral storage. Teardown must be limited to this dedicated project and its explicitly named volume; never use a broad \`docker compose down -v\` against the normal project.
5. No project \`.env\`, \`.env.production\`, application bootstrap, production secrets, patient fixtures, or mounted developer database directories.
6. Synthetic-only fixture data with unmistakable tenant A/B identifiers.
7. A setup identity used only for the disposable cluster to create databases/roles/grants. It must not be reused by the API, source service, import worker or tests asserting runtime denial.
8. Separate test containers/processes for tenant-A API, tenant-B API, tenant-A source, tenant-B source, control-plane API, destination import, email worker and privileged maintenance roles as applicable.
9. Credentials supplied only to the specific test workload that needs them. Test output must redact connection strings, passwords and secret-manager values.
10. A documented manual teardown command scoped to the unique test project, plus a check that refuses teardown if the project label/name does not match the dedicated AUD-004 harness.

### 15.3 Required phases

**H-00 — preflight (read-only):**
- Verify Docker/Compose availability and the pinned image digest.
- Verify the harness project name and volume labels are unique and dedicated to AUD-004.
- Verify no production or default development env file is loaded.
- Verify the test cluster is newly created and contains no pre-existing application databases.
- Abort on ambiguous project, volume, host, or environment identity.

**H-01 — disposable cluster initialization:**
- Create only synthetic CP, tenant-A and tenant-B databases.
- Create cluster-wide PostgreSQL roles deliberately separated by workload and tenant.
- Assign each tenant runtime login CONNECT only to its own database; explicitly review PUBLIC privileges, role memberships, database ownership, schema/object grants, default privileges and predefined roles.
- Keep setup/admin credentials out of all runtime test containers.
- Record catalog snapshots before executing workload tests.

**H-02 — identity proof:**
- Execute the DB-01–DB-15 checks from Section 13 using actual tenant workload credentials.
- Require A-to-A and B-to-B positive connections.
- Require A-to-B and B-to-A denied connections with the intended authentication/authorization error; a missing database, DNS failure, unavailable server, or bad password is not a passing isolation result.
- Verify that the workload cannot SET ROLE to a privileged identity or perform prohibited DDL.
- Verify source-only objects are inaccessible to ordinary tenant API identities.

**H-03 — container identity proof:**
- Run the tests from the actual test container identities, not only from the developer shell or a privileged test runner.
- Verify destination/import and email workloads have no source tenant credentials.
- Verify the source workload cannot retrieve another tenant's credential.
- Verify the control-plane workload cannot connect to tenant databases unless a separately reviewed operation explicitly requires it.

**H-04 — lifecycle proof:**
- Rotate and revoke a test credential; verify new sessions fail after revocation.
- Separately drain/terminate already-established pooled sessions and verify they cannot reconnect with stale credentials.
- Verify test teardown cannot target any database outside the disposable cluster.
- Capture the final role/ACL catalog snapshot and redacted test evidence.

### 15.4 CI behavior

- Keep the current SQLite suite unchanged for fast application/domain tests.
- A separately named PostgreSQL integration job now exists in the dedicated AUD-004 proof workflow and starts the harness from a clean runner.
- The PostgreSQL proof runs inside the isolated Compose network and does not silently fall back to SQLite.
- The latest-head run is [workflow run 43364452642](https://github.com/Perseus37/avinya_hms_v2/actions/runs/43364452642), executed against PR #71 head `ae28c153abd4ada2a257fa360c699c24acc3bb0c`: the disposable PostgreSQL proof passed **27 assertions** (9 for each of tenant A, tenant B and control plane); reconciliation regression tests passed **10 tests** (one existing deprecation warning); disposable container, network, named volume and temporary secrets were cleaned up.
- The selected `reconciliation` scope skipped frontend production builds and the general Compose configuration job. This run must not be represented as validating those scopes.
- Preserve test logs, image digest, Compose configuration hash, fixture manifest and redacted catalog evidence as CI artifacts.
- Do not place reusable credentials in repository secrets. Use short-lived CI job-scoped values for the disposable cluster only.

### 15.5 Execution boundary and current status

The dedicated Compose harness, PostgreSQL 17 fixture, synthetic tenant/control-plane databases, low-privilege runtime roles, ACL assertions and on-demand CI workflow exist in draft PR #71. The latest PR-head run above passed its bounded fixture-level proof and completed disposable teardown.

**What this evidence establishes:** for the tested synthetic PostgreSQL configuration, the three isolated test identities each passed their nine implemented assertions, including own-database positive access, foreign-database CONNECT denial and selected role/privilege checks. The reconciliation regression job passed 10 tests.

**What it does not establish:** complete cluster-wide role/object/default-privilege inventory; actual deployed PostgreSQL grants; production container/workload identity isolation; secret-provider isolation; network egress enforcement; source-owned federation API/authorization; audit-before-disclosure; credential rotation/revocation; existing connection-pool draining; or full lifecycle proof. The source-owned federation service remains unimplemented, and the current federation router still opens foreign tenant database sessions from destination-side discovery/import request paths.

The latest proof was run against exact PR #71 head `ae28c153abd4ada2a257fa360c699c24acc3bb0c`. It is synthetic fixture-level evidence only and does not validate production infrastructure, credentials or deployed ACLs.

No existing development or production database, named volume, production credential, patient data, deployment configuration, role bootstrap, tenant registry, or runtime connection routing was changed. AUD-004 remains **NOT READY** and a release blocker. PostgreSQL **database-per-tenant** remains the architecture; no schema-per-tenant migration is proposed.

The next implementation slice must address the source-owned federation boundary under a separately reviewed wire profile and isolated workload identities. Do not change production identity, role bootstrap, secret, network, deployment or runtime configuration until the disposable evidence and independent review gates are satisfied.


## 16. Existing design reconciliation — avoid duplicate protocol proposals

The existing design documents were cross-checked before any further implementation planning. They contain useful, complementary design material, but none of the following draft PRs is an approved normative implementation contract. Their existence must not be represented as approval or as closure of the corresponding review findings.

| Existing artifact | Material already specified | What remains unresolved / required disposition |
|---|---|---|
| PR #20 — signed clinician actor assertion | Human actor is distinct from node identity; issuer-scoped subject; signed assertion; source-side issuer/key trust; action, purpose, destination, resource and scope binding; source authorization and audit; replay controls. It recommends a per-hospital Avinya backend issuer as a possible first model. | The issuer recommendation is conditional, not an accepted governance decision. Identity authority, clinician classes/credential assurance, external identity mapping, key custody/rotation, status freshness and revocation SLA still need named owners and approval. Local tenant profile fields are not external license verification. |
| PR #30 — discovery, replay and transfer integrity | Source-created challenge; source-side selector canonicalization; no patient-existence disclosure before authorization; opaque resource handles; operation-specific challenge/assertion; atomic replay prevention; durable source audit before response release; response integrity and destination acknowledgement distinctions. | It explicitly leaves cryptographic algorithms, canonicalization/digest construction, challenge/assertion/handle/artifact lifetimes, revocation semantics, trust onboarding and response-artifact retry policy open. Its logical operations must be reconciled with the final approved wire profile and import lifecycle contract. |
| PR #44 — database-per-tenant identity proposal | Retains one PostgreSQL database per tenant; separates tenant-local app, source, migration, provisioning, backup and control-plane identities; prohibits destination-side foreign DB sessions; requires local cross-branch calls to use the same source-owned protocol as remote federation. | It is a proposed ADR, not accepted. Actual deployed role grants, secret-provider policy, workload identity, network reachability, pool lifecycle and cluster-wide ACL evidence remain unproven. The proposal does not authorize role/bootstrap/Compose changes. |

### 16.1 Canonical responsibility split

These documents should be reconciled into one implementation plan, not copied into another protocol proposal:

1. **Actor assertion and issuer trust:** use PR #20 as the actor-identity design source. Its per-hospital issuer recommendation remains a decision candidate until identity-governance approval.
2. **Challenge, discovery privacy, replay and transfer lifecycle:** use PR #30 as the protocol-flow design source, reconciled with the existing import/idempotency work in PRs #23/#24 and runtime remediation in PR #19.
3. **Database and workload isolation:** use PR #44 as the database-per-tenant identity design source. Keep the existing PostgreSQL database-per-tenant topology; do not introduce schema-per-tenant.
4. **Evidence and release readiness:** use this report and the PR #71 disposable proof as evidence tracking. A passing synthetic ACL harness is not proof of deployed workload or secret isolation.

### 16.2 Blocking decision/evidence crosswalk

| Review item | Existing design coverage | Closure evidence still required |
|---|---|---|
| R74 — revocation authority/effective time | PR #20 describes issuer/key/clinician revocation categories; PR #30 treats revocation as a freshness dependency. | Named authority for issuer, key and clinician status; authoritative event/effective-time semantics; propagation and cache invalidation SLA; race tests for revocation between challenge, assertion, authorization and disclosure; independent approval. |
| R76 — immutable wire profile | PRs #20 and #30 define logical claims and flows but intentionally leave critical wire/crypto choices open. | Versioned normative envelope and serialization; algorithm/key/trust profile; issuer/audience/resource/action semantics; canonicalization; freshness/replay rules; response integrity; key rotation/revocation; conformance vectors and independent cryptographic review. |
| R77 — polling/redemption and anti-enumeration | PR #30 specifies privacy-preserving challenge bootstrap and common observable outcomes; PR #20 requires source challenge binding. | Exact authenticated polling/redemption contract; recipient and operation binding; idempotency and retry semantics; uniform status/body/size/timing policy; throttling and abuse controls; concurrent replay and enumeration tests. |
| DBID/source boundary — foreign database access | PR #44 defines the intended per-tenant identity boundary; PR #71 proves a bounded synthetic PostgreSQL ACL configuration. | Actual deployment role/ACL/ownership/default-privilege inventory; per-workload secret retrieval evidence; destination A denied access to B from real workload containers; source B positive access only to B; no alternate route/job/support/recovery bypass; pool drain and revocation evidence. |

### 16.3 Implementation stop rule

Do not create another design-only PR to restate these same responsibilities. Do not implement the source-owned federation service, freeze cryptographic choices, create trust entries or signing keys, alter PostgreSQL roles/bootstrap, change tenant routing, or enable local/remote federation based solely on these proposals.

The next implementation authorization must identify the accountable identity, security, database and platform owners; approve the normative wire profile and source-owned API contract; and define a bounded non-production implementation slice with acceptance tests. Until then, continue only with read-only repository inspection and evidence reconciliation in the existing PR #70/#71.

**Architecture reaffirmation:** PostgreSQL database-per-tenant remains unchanged. JSON Schema (where used) means validation of a JSON document; it is not a PostgreSQL tenant schema and does not alter the storage topology.


### 11.6 Source snapshot revalidation — 2026-11-13

The following current default-branch files were fetched again during this review. The blob identifiers make the inspected source snapshots reproducible; they are not deployment evidence.

| Source file | Fetched blob | Revalidated finding |
|---|---|---|
| `backend/core/database.py` | `043f4ccbdad4d2bfe4c89af0b46988ce60610b01` | `build_db_url` derives from shared `settings.DATABASE_URL`; `ensure_postgres_db_exists` connects to `postgres` and can issue `CREATE DATABASE`; `TenantEngineRegistry.get_engine(db_name)` builds an engine from the caller-supplied database name. |
| `backend/domains/federation/router.py` | `4dd93e0b370e0214c9db19b097e34a3f8efff5bd` | Discovery opens foreign branch sessions at the nested `_fetch_branch_data` path; import opens a source session from `source_registry.db_name`. |
| `backend/control_plane/api/routers/provisioning.py` | `40bb98fc9f79fb700b8b9484688d818c3ef1c441` | Hospital provisioning calls the database-creation helper, runs tenant migration, then opens a tenant engine/session to seed the database. |
| `backend/control_plane/api/routers/migration.py` | `d0660422e781ff913788d31664be69191fc269e0` | Bulk migration preview opens the selected tenant engine; background execution opens it again for the selected tenant. This is a privileged migration path, not ordinary federation routing. |
| `backend/core/queue.py` | `aad0c663e52e7a73d7261658f5ecc1889b7e36b7` | `privacy.retention.execute` resolves a tenant and opens its DB; `privacy.retention.scheduled_daily_sweep` enumerates active tenants and opens each tenant DB before enqueueing work. `email.send` has no direct tenant DB access in the inspected handler. |
| `backend/scripts/backup_service.py` | `8ad90420fb4c2f487ed3c6318f657411e3b9cfa8` | Backup uses configured `POSTGRES_USER`/`POSTGRES_PASSWORD` for `pg_dump), enumerates active cloud tenants and decrypts each tenant backup key from control-plane metadata. |
| `backend/scripts/restore_tenant.py` | `33598657b29ae4e24f136d079543e02dc91098e6` | Restore accepts a target database name, invokes the database-creation helper and runs `pg_restore` using the configured PostgreSQL login. Treat as an isolated recovery interface with approved target binding, not a runtime capability. |
| `backend/worker.py` | `b0fb87568caab841c6557082f885ca39bbb78ca0` | No direct tenant engine creation is visible in this file; the registered handler call graph in `backend/core/queue.py` determines the worker's effective DB capability. |

This revalidation confirms the previously documented fleet-wide retention and backup/restore paths; it does not establish that those paths are currently deployed, scheduled, or reachable in production. It also does not prove effective PostgreSQL grants or secret-manager permissions.

**Classification:** federation discovery/import are direct destination-side foreign-tenant access paths and remain the P0 source-owned-boundary issue. Provisioning, migration, retention sweep, backup and restore are privileged operational capabilities that require distinct identities, explicit target scope, audit and isolation from ordinary API/federation workloads. The email-only handler is a candidate for a database-free worker class, subject to transitive-import verification.

No runtime code, SQL, migration, Compose configuration, environment file, credential, database or patient data was changed by this revalidation.


### 11.7 Worker import and synchronous-fallback boundary revalidation — 2026-11-13

The queue and worker source snapshots were fetched again from the default branch during the transitive-capability check.

| Source file | Fetched blob | Exact code evidence | Security implication |
|---|---|---|---|
| `backend/core/queue.py` | `aad0c663e52e7a73d7261658f5ecc1889b7e36b7` | Lines 18–21 import `ControlSessionLocal` and `tenant_engine_pool` from `backend.core.database` at module import time. | Every process importing this queue module loads the shared database module and its database-capable dependencies, including a process intended only to deliver email. |
| `backend/worker.py` | `b0fb87568caab841c6557082f885ca39bbb78ca0` | Lines 16–25 import `get_redis` and queue dispatch/registry functions; lines 101–112 resolve and invoke the registered handler in the same worker process. | The current worker is a mixed-capability task host. Task-name separation does not isolate credentials or process capabilities. |
| `backend/core/queue.py` | `aad0c663e52e7a73d7261658f5ecc1889b7e36b7` | Lines 69–76 define `enqueue_task` with `sync_fallback: bool = True`; lines 130–134 look up and invoke the handler synchronously when Redis enqueue fails. | Any caller using the default can execute a database-capable handler in its own process during Redis failure. This defeats a proposed worker-only boundary unless callers explicitly opt out and the dispatch contract is redesigned/tested. |
| `backend/core/queue.py` | `aad0c663e52e7a73d7261658f5ecc1889b7e36b7` | Lines 302–322 register `email.send`; lines 325 onward register tenant retention execution; lines 409 onward register a fleet-wide scheduled retention sweep. | Email, tenant-retention and fleet-scheduler handlers share one registry/module and worker process. The email handler's lack of a direct tenant query is not proof of a database-free process. |

**Disposition:** this is an additional source-level P0/P1 isolation finding for the workload-boundary plan. Do not claim an email-only worker is database-free based on its handler body. A safe future split must account for module import closure, task registration, Redis-failure behavior, synchronous fallbacks, periodic scheduling and every enqueue caller. The fleet-wide retention scheduler must be separated from tenant-bound retention execution; the scheduler should use control-plane metadata and enqueue only, while execution must receive a tenant-bound identity and cannot obtain other tenants' credentials. An email-only worker must not import a module that imports tenant DB engines or receive tenant/control-plane DB credentials.

**No runtime change is authorized or made by this inventory.** In particular, do not simply set `sync_fallback=False` globally without reviewing every caller's retry/error semantics, and do not split the worker until task routing, deployment service definitions, secrets and operational ownership are reviewed together.

This source inspection still does not prove which task names are currently enqueued by each deployed API process or what credentials each deployed container receives. Enqueue call-site and deployment-environment mapping remain required evidence. No production or development database, credential, queue, worker deployment, task payload or patient data was changed.


### 11.8 Enqueue caller and production service mapping — 2026-11-13

A targeted source and deployment revalidation was performed after Section 11.7. The following exact default-branch snapshots were inspected:

| Source file | Fetched blob | Exact code evidence | Security / operational implication |
|---|---|---|---|
| `backend/domains/privacy/router.py` | `e63ec483c6aec0f5e8568b82885e5f0b68d68a31` | Lines 722–739 import `enqueue_task` and enqueue `privacy.retention.execute` without specifying `sync_fallback`. | The retention API route inherits the default `sync_fallback=True`. If Redis enqueue fails, the API process can execute the registered tenant-bound retention handler synchronously. |
| `backend/core/queue.py` | `aad0c663e52e7a73d7261658f5ecc1889b7e36b7` | Lines 69–76 set `sync_fallback=True` by default; lines 130–134 invoke the registered handler on enqueue failure. Lines 409–455 show the fleet-wide scheduled sweep querying active tenants and enqueueing `privacy.retention.execute` without overriding the default. | The sweep's per-tenant child task can also execute synchronously inside the process running the sweep if Redis fails. This is distinct from the periodic scheduler enqueue in the worker. |
| `backend/worker.py` | `b0fb87568caab841c6557082f885ca39bbb78ca0` | Lines 79–87 enqueue `privacy.retention.scheduled_daily_sweep` with `sync_fallback=False`; lines 101–112 execute dequeued handlers in the worker process. | The worker's periodic scheduler entry point correctly opts out of synchronous fallback, but its handler later enqueues tenant execution with the default fallback. The single worker still hosts both scheduler and tenant execution handlers. |
| `docker-compose.prod.yml` | `bfce52948c508e137875a0be2af09ae11178e78f` | API lines 226–230, HL7 listener lines 289–293, worker lines 328–332 and onboarding portal lines 368–372 each load `.env.production`. | These production service definitions share the same environment-file source. This is evidence of shared configuration/credential exposure at the Compose definition level, not proof of the actual values, effective DB grants, or runtime secret-provider policy. |
| `docker-compose.yml` | `0faced7760516a84ec096f49ea84ec1c5a8d65bc` | Worker lines 146–156 and onboarding portal lines 173–179 load the same `.env`; other service definitions also use that file. | The development Compose topology has the same broad shared-env pattern. It is not evidence of production runtime state. |

#### 11.8.1 Bounded call-site conclusion

The targeted file inspection confirms the retention API route and the retention sweep's child-task enqueue as concrete enqueue paths. The repository code-search endpoint did not return usable indexed matches for `enqueue_task(` or `sync_fallback`; therefore this pass is **not a complete repository-wide inventory of every enqueue caller**. No claim is made that these are the only call sites. A complete caller inventory and handler import-closure review remain open before any task/worker split or fallback-policy change.

#### 11.8.2 Required disposition

1. Treat retention async enqueue as a caller-process execution path during Redis failure until the contract is changed and tested. Do not represent it as worker-only execution.
2. Treat the scheduled sweep as a fleet-capable process: it reads control-plane tenant metadata and opens tenant databases. It is not a candidate for the email-only worker.
3. The tenant execution handler should ultimately receive a tenant-bound identity; it must not resolve arbitrary tenant DB credentials from a fleet-wide credential bundle.
4. An email-only process must have a minimal import closure and no tenant/control-plane database credentials. Merely separating task names or handlers is insufficient.
5. Before changing fallback defaults, map every caller's failure semantics, retry/idempotency behavior and user-visible response contract. Do not globally disable fallback as a shortcut.
6. Before changing Compose or secret assignments, inventory actual deployed environment values and secret-provider/workload identity policies. The shared `.env.production` reference alone does not prove the effective credentials or PostgreSQL ACLs.

No queue policy, worker code, runtime behavior, Compose file, environment file, secret, credential, database, migration, or patient data was changed. PostgreSQL **database-per-tenant** remains unchanged. PR #70 remains the sole consolidated readiness report for this work; no new PR was created.


### 11.9 Email enqueue and API-process fallback — 2026-11-13

The email path was inspected separately because an email-only worker is a candidate workload for reduced database capability.

| Source file | Fetched blob | Exact code evidence | Security / operational implication |
|---|---|---|---|
| `backend/core/mailer.py` | `689acd3a6d1de0078f43a13a84431237012cec7b` | Lines 83–105 define `enqueue_email`, import `backend.core.queue.enqueue_task`, enqueue `email.send`, and explicitly pass `sync_fallback=True`. | If Redis enqueue fails, `enqueue_task` invokes the email handler in the calling API process. Email delivery is not strictly worker-only. |
| `backend/domains/identity/auth_router.py` | `fae5f7fc1d19af76360059365c56ad18461106db` | Lines 40–54 import `enqueue_email` and route normal dispatch through `_dispatch_email`; lines 329, 497, 677, 806 and 959 call that helper for security alerts, password reset, account unlock and MFA enrollment messages. | The authentication API is a confirmed email enqueue caller. Several of these paths run after DB state changes/commit, so queue failure behavior and delivery guarantees must be treated as part of the auth workflow contract. |
| `backend/domains/identity/auth_router.py` | `fae5f7fc1d19af76360059365c56ad18461106db` | Lines 46–55 show `_dispatch_email` catches and suppresses enqueue exceptions; some callers also wrap dispatch in an additional catch. | The API may return its normal response despite a failed enqueue when Redis is unavailable and synchronous send fails; the fallback handler logs and suppresses delivery exceptions internally. This behavior needs explicit product/security semantics and tests before changing it. |
| `backend/core/queue.py` | `aad0c663e52e7a73d7261658f5ecc1889b7e36b7` | Lines 302–322 register `email.send`; the handler imports `backend.core.mailer.send_email` and performs provider delivery. | The same queue module that imports DB-capable shared database components registers the email handler. A separate email process must not import this module in its current form. |

#### 11.9.1 Email workload disposition

The current design has two independent barriers to a database-free email worker:

1. The shared queue module imports control-plane and tenant-engine database capabilities at module import time.
2. The email enqueue helper permits API-process synchronous delivery on Redis failure.

A safe separation requires a queue/dispatch module whose import closure is database-free, an email worker with only mail-provider and queue credentials, and an explicit failure contract for Redis outage (durable retry/outbox, or a deliberately synchronous fallback in a separately approved process). Do not silently drop auth/security notifications or claim they are delivered because an enqueue call returned a task ID. The current fallback returns the task ID even when the synchronous handler catches a delivery error; this does not constitute durable queue acceptance or successful delivery.

Before changing this behavior, define whether the auth endpoint guarantees only best-effort notification, durable dispatch acceptance, or confirmed delivery; then add tests for Redis unavailable, mail provider unavailable, duplicate retry, and post-commit notification recovery. No email delivery, queue semantics, API response, runtime code, DB, credential or deployment configuration was changed in this inspection.



### 11.10 Additional task registry and caller-surface sweep — 2026-11-13

A further read-only pass expanded beyond the previously documented privacy and identity routes. The recursive source tree at the inspected PR #70 head contains 248 Python files under `backend/`. This pass additionally inspected the control-plane service layer, application startup, selected operational scripts, identity password helpers, integrations service, and the complete queue/worker registration surfaces. It did not fetch and inspect every one of the 248 files; this remains a bounded audit, not a complete repository-wide call-site proof.

| Source file | Fetched blob | Exact code evidence | Finding |
|---|---|---|---|
| `backend/core/queue.py` | `aad0c663e52e7a73d7261658f5ecc1889b7e36b7` | Lines 302, 325 and 409 register `email.send`, `privacy.retention.execute` and `privacy.retention.scheduled_daily_sweep`. | These are the three statically visible handler registrations in the queue module. The two retention handlers have different capabilities: tenant execution and fleet-wide scheduling. |
| `backend/worker.py` | `b0fb87568caab841c6557082f885ca39bbb78ca0` | Lines 17–25 import the queue module's worker/dispatch API; lines 84–90 schedule the fleet sweep and dequeue tasks; lines 97–112 dispatch the registered handler in the worker process. | The production worker imports the same DB-capable queue module used by API enqueue callers. The periodic scheduler runs in this same worker process. |
| `backend/control_plane/app.py`, `backend/control_plane/services/*.py`, `backend/scripts/*.py`, `backend/domains/identity/passwords.py`, `backend/domains/integrations/service.py` | Read at PR #70 head `20b8a5e48518c81820a7e28494fd73aeda33b46f` | A targeted literal scan for `enqueue_task`, `enqueue_email`, `sync_fallback`, `registry.register`, registered task names and direct queue imports returned no matches in these additional files. | No additional direct caller or static registration was identified in this subset. This is not proof that dynamically imported or indirect call paths do not exist elsewhere. |
| `docker-compose.prod.yml` | `bfce52948c508e137875a0be2af09ae11178e78f` | API, HL7 listener, worker and onboarding portal service definitions load `.env.production`; worker command starts `python -m backend.worker`. | Deployment definitions confirm a common environment-file source across these services. They do not establish effective runtime credentials, secret-provider authorization, PostgreSQL grants or network policy. |

#### 11.10.1 Consolidated known queue map

The source evidence currently establishes these known paths:

1. Identity notification callers invoke `enqueue_email` → `enqueue_task("email.send", sync_fallback=True)`. Redis failure may execute the mail handler in the API caller.
2. Privacy retention API invokes `enqueue_task("privacy.retention.execute")` without overriding the default `sync_fallback=True`. Redis failure may execute tenant retention work in the API caller.
3. Worker periodic scheduling invokes `enqueue_task("privacy.retention.scheduled_daily_sweep", sync_fallback=False)`; the sweep handler subsequently enqueues per-tenant execution without overriding the default fallback.
4. The worker dequeues and executes registered handlers in the worker process, but its import closure still includes the shared queue module and its database-capable imports.

The first two caller classes and the scheduler/child-task path are confirmed, not necessarily exhaustive. GitHub code search did not provide usable indexed results in the earlier pass, and this additional scan was not a full fetch of all backend Python files. Therefore, no global fallback change, task split, or claim of complete caller inventory is justified yet.

#### 11.10.2 Next evidence required

- Complete a reproducible local repository scan (all tracked Python files, including tests and scripts) for direct enqueue calls, wrapper aliases, dynamic registry registration, task-name strings and imports; record commit SHA and exact command/output.
- Trace each confirmed caller through exception handling, transaction/commit boundary, retry/idempotency and user-visible API response.
- Build import-closure tests proving the proposed email process cannot import or initialize control-plane or tenant database capabilities.
- Only after the caller contract and complete inventory are reviewed, propose a narrow runtime change with tests. Do not globally disable synchronous fallback as a shortcut.

No runtime code, queue policy, worker, Compose file, environment, secret, credential, database, migration, or patient data was changed. PostgreSQL **database-per-tenant** remains unchanged. PR #70 remains the existing consolidated report; no new PR was created.


### 11.11 Provisioning welcome email bypasses the task queue — 2026-11-13

The test suite exposed a second email dispatch mechanism that is not covered by the identity `enqueue_email` path.

| Source file | Fetched blob | Exact code evidence | Operational implication |
|---|---|---|---|
| `backend/control_plane/api/routers/provisioning.py` | `40bb98fc9f79fb700b8b9484688d818c3ef1c441` | Lines 28, 116–135 import and call `backend.core.mailer.send_email` directly inside `_dispatch_welcome_email`; the helper catches `MailDeliveryError` and returns a boolean/error tuple. | Control-plane provisioning performs synchronous provider delivery in the provisioning API process. This path does not enqueue `email.send` and therefore has a different failure, latency and retry contract from identity notifications. |
| `backend/control_plane/api/routers/provisioning.py` | same blob | Lines 353 onward call `_dispatch_welcome_email` after constructing the provisioning result, record `email_dispatched` / `email_error`, and add a `PROVISION_EMAIL_FAILED` audit record when delivery fails. | Provisioning explicitly surfaces welcome-email failure in its result/audit flow, unlike the best-effort identity dispatch helper. The precise transaction ordering and API response semantics need to be assessed before unifying these paths. |
| `tests/test_24_mail_and_document_profiles.py` | fetched at PR #70 head `20b8a5e48518c81820a7e28494fd73aeda33b46f` | `test_provisioning_welcome_email_never_includes_generated_credentials` monkeypatches `provisioning.send_email` and verifies that the welcome message excludes generated password, federation key and backup key. | Existing coverage protects against credential disclosure in the welcome message, but it does not test provider outage, queue outage, retry/idempotency or provisioning recovery semantics. |
| `tests/test_40_background_worker_and_queue.py` | `1cdbd993f27426baa8b0f71f942cdefa60aaaf50` | Tests use a `FakeRedis`; enqueue and worker tests generally pass `sync_fallback=False`, exercise task status/retry/dead-letter behavior and register a synthetic worker task. | Queue tests validate basic Redis-backed queue mechanics and worker dispatch, but do not exercise Redis-unavailable synchronous fallback, mail-provider failure inside the fallback handler, or the API notification contracts described above. |

#### 11.11.1 Updated email dispatch map

There are at least two distinct email dispatch contracts in the inspected source:

1. **Identity/security notifications:** identity router → `enqueue_email` → `enqueue_task("email.send", sync_fallback=True)`; enqueue exceptions may be suppressed, and Redis failure can invoke the handler in the API process.
2. **Control-plane provisioning welcome email:** provisioning route → direct `send_email` in the API process; delivery failure is returned and recorded in a control-plane audit entry.

These paths should not be collapsed into a single delivery guarantee without an explicit product contract. In particular, provisioning may need durable post-provisioning notification/recovery, while authentication/security notifications need a clearly defined best-effort versus durable-dispatch guarantee. A queue/outbox design must preserve the credential-exclusion property already tested for provisioning emails.

#### 11.11.2 Test gap and disposition

Add explicit tests for (a) Redis unavailable with the identity enqueue helper, (b) mail provider unavailable during synchronous fallback, (c) direct provisioning provider failure and recovery, (d) duplicate delivery/retry idempotency, and (e) post-commit delivery failure without losing the notification intent. Keep provisioning welcome email free of generated credentials. No runtime code or tests were modified in this documentation-only pass.

No runtime, queue, worker, provisioning, email, Compose, secret, credential, database, migration or patient data was changed. PostgreSQL **database-per-tenant** remains unchanged. PR #70 remains the consolidated readiness report; no new PR was created.


### 11.12 Full test-tree literal dispatch scan — 2026-11-13

A bounded but complete **test-tree file inventory scan** was completed against source commit `20b8a5e48518c81820a7e28494fd73aeda33b46f`. The recursive Git tree contained 85 Python files under `tests/`; all 85 were fetched and scanned. This extends the earlier focused review of queue, mail, privacy, identity and deployment tests.

| Scope | Scan method | Result |
|---|---|---|
| All 85 tracked Python test files under `tests/` | Literal pattern scan for `enqueue_task`, `enqueue_email`, `sync_fallback`, `registry.register`, `email.send`, `privacy.retention`, `send_email`, `BackgroundTasks`, `asyncio.create_task` and `create_task(` | No new queue or mail dispatch implementation/caller was identified outside the already documented queue/mail tests. |
| `tests/test_16_websocket_and_realtime_events.py` | Same scan | One `asyncio.create_task(...)` occurrence starts the ASGI application task in a WebSocket test; it is not evidence of a background business-task dispatcher. |
| `tests/test_40_background_worker_and_queue.py` and `tests/test_24_mail_and_document_profiles.py` | Previously inspected in detail | Existing queue mechanics and credential-exclusion coverage remain as described in Section 11.11; no Redis-down fallback or mail-provider-failure recovery proof was found. |

#### 11.12.1 Interpretation and limits

- The test-tree inventory is complete for Python files present under `tests/` at the inspected source commit.
- The scan is lexical, not a Python AST/data-flow proof. It can miss aliased imports, dynamically assembled task names, indirect wrappers, plugin registration and behavior expressed without these literal strings.
- This test-tree scan does **not** complete the backend-wide caller inventory. Production source modules, scripts, deployment runtime configuration and import closures still require a reproducible repository-wide scan and execution-level tracing.
- The only new occurrence of `asyncio.create_task` in the newly scanned test batches is the WebSocket ASGI harness task; it does not change the queue/email map or justify a runtime change.

#### 11.12.2 Disposition

No additional queue caller, email dispatch path, task registration or test proving Redis-unavailable fallback/recovery was established by this test-tree pass. Retain the Section 11.11 test gaps and the Section 11.10 requirement for a reproducible full-repository scan. Do not change the default `sync_fallback`, introduce a queue split, or claim complete production caller coverage on this evidence alone.

No runtime code, tests, queue policy, worker, Compose file, environment, secret, credential, database, migration or patient data was changed. PostgreSQL **database-per-tenant** remains unchanged. PR #70 remains the existing consolidated report; no new PR was created.


### 11.13 Control-plane FastAPI background jobs are a third dispatch mechanism — 2026-11-13

The expanded production-source scan identified long-running control-plane operations dispatched through FastAPI `BackgroundTasks`. These are separate from the Redis task queue and from direct provisioning email delivery.

| Source | Fetched blob at source commit | Code evidence | Reliability / isolation implication |
|---|---|---|---|
| `backend/control_plane/api/routers/fleet_ops.py` | `b286c202182e9af9b2ea5ed485d66889bf7409d9` | Manual backup endpoint adds `_execute_backup` to `background_tasks`; the callback invokes `_dump_and_encrypt` and writes completion/failure audit events. It commits the request audit and returns a “Snapshot queued” response. | The work is attached to the API response lifecycle, not persisted as a Redis task/job. Process termination/restart after response but before completion can lose the in-memory task. |
| Same file | same blob | Restore endpoint terminates tenant DB connections, then adds `_execute_restore` to `background_tasks`. The callback attempts a mandatory pre-restore safety backup, aborts restore if that fails, then restores and records completion/failure audit events. | Destructive restore is an API-process background operation. The pre-restore safety snapshot is a useful fail-closed guard, but it does not make dispatch durable or provide restart recovery. |
| `backend/control_plane/api/routers/migration.py` | `d0660422e781ff913788d31664be69191fc269e0` | CSV upload is written to a local temporary file; `_execute_bulk_migration_background` is added to `background_tasks` with tenant DB name, model, mapping, temp path and duplicate policy. A “started” audit is committed and API returns “processing/queued”. | Job state and temp-file ownership are not shown as durable queue state in this path. API process restart, container replacement or local ephemeral storage loss can strand the operation or its input file. |
| `backend/control_plane/app.py` | `cae7f78718cbf5356f9766361f91ab2fb4362322` | Global webhook endpoint adds `process_webhook_payload` to FastAPI `background_tasks` and returns HTTP 202. The current callback only logs the event type; its own docstring describes future heavy DB processing. | The current implementation is a placeholder/logging callback, not a durable webhook ingestion pipeline. A 202 response means accepted by this API process, not durably stored or completed. |

#### 11.13.1 Dispatch taxonomy updated

The inspected code now shows at least three distinct asynchronous/background mechanisms plus direct synchronous delivery:

1. **Redis task queue:** identity email and privacy retention tasks; default enqueue behavior may execute synchronously in the API caller when Redis enqueue fails.
2. **FastAPI in-process BackgroundTasks:** manual backup, restore, CSV visual migration and webhook callback. No durable job record/queue handoff is established by the inspected endpoint code.
3. **Direct synchronous provider call:** provisioning welcome email uses `send_email` in the control-plane API process.
4. **Worker execution:** `backend.worker` dequeues Redis tasks, but imports the shared DB-capable queue module.

These must be treated as separate reliability contracts. “Queued”, “processing” and HTTP 202 responses from FastAPI BackgroundTasks must not be interpreted as durable acceptance, worker isolation, retry or completion.

#### 11.13.2 Required follow-up evidence

- Inspect the remainder of `fleet_ops.py` and `migration.py` for every BackgroundTasks call, and map every callback's credentials, transaction boundary, input-file lifecycle, idempotency and audit behavior.
- Confirm whether a persistent job ledger or external supervisor exists elsewhere; the endpoint snippets alone do not prove absence across the whole system.
- Design durable job acceptance and status transitions before moving backup, restore or migration work to another worker. Restore must retain its pre-restore safety snapshot and fail-closed behavior.
- Define restart/retry semantics and tenant-scoped execution identity. A general control-plane API process should not need unrestricted tenant DB credentials merely because it starts a background task.
- Webhook ingress must authenticate and durably persist/validate events before returning a success status if it is to become a real integration path.

This pass establishes the specific in-process dispatch call sites above; it is not yet a complete repository-wide AST/data-flow inventory of every BackgroundTasks callback or dynamic task wrapper.

No runtime code, tests, queue policy, worker, Compose file, environment, secret, credential, database, migration or patient data was changed. PostgreSQL **database-per-tenant** remains unchanged. PR #70 remains the consolidated readiness report; no new PR was created.


### 11.14 Callback execution, transaction and credential trace — 2026-11-13

Followed the backup, restore and CSV migration callbacks into their implementation helpers at source commit `20b8a5e48518c81820a7e28494fd73aeda33b46f`.

#### 11.14.1 Restore path has a statically confirmed import failure

- `backend/control_plane/api/routers/fleet_ops.py` imports `create_encrypted_backup` inside `_execute_restore` from `backend.scripts.backup_service`, then calls it for the mandatory pre-restore safety snapshot.
- The complete fetched `backend/scripts/backup_service.py` (blob `8ad90420fb4c2f487ed3c6318f657411e3b9cfa8`, 276 lines) defines `_dump_and_encrypt` and `run_backup_cycle`, but contains no `create_encrypted_backup` definition or import.
- Consequently, on this inspected source snapshot, the callback's import raises `ImportError`; its safety-snapshot exception handler records `PRE_RESTORE_SAFETY_SNAPSHOT_FAILED` and raises before calling `restore_encrypted_backup`.
- This is a **restore-blocking defect** in the inspected code, not merely a missing test. The fail-closed behavior prevents the destructive restore from proceeding, which is safer than restoring without a safety copy, but the endpoint cannot complete until the safety-backup helper reference is reconciled.
- Do not bypass the safety snapshot or weaken fail-closed behavior. Correct the helper/API mismatch and add a test proving snapshot success precedes restore, and snapshot failure prevents restore.

#### 11.14.2 Backup credentials and artifact lifecycle

- Manual backup decrypts `tenant.backup_encryption_key` in the control-plane request handler and captures the resulting plaintext `raw_key` in the in-process callback closure.
- `_dump_and_encrypt` uses `settings.POSTGRES_USER` and `settings.POSTGRES_PASSWORD` (passed as `PGPASSWORD`) for `pg_dump`, selecting the database by name. The source does not show a tenant-specific database login for this path.
- The helper encrypts pg_dump stdout, writes an encrypted temporary artifact and atomically renames it, then writes a SHA-256 sidecar. A failure after the encrypted artifact is renamed but before the checksum is written can leave an artifact without its sidecar; no durable job state or retry reconciliation is established here.
- The callback records completion/failure in the control-plane audit table. Audit-write failures are caught and logged, so task completion can occur without a persisted outcome audit.
- The callback captures plaintext backup key in process memory until execution/closure release. This is not evidence of a leak to logs, but it is a credential-lifetime and process-boundary concern.

#### 11.14.3 Restore credential and ordering details

- The restore callback captures the encrypted tenant backup key and passes it to `restore_encrypted_backup`; that helper decrypts it, decrypts the artifact into a sibling `.restoring.dump` file, and removes that temporary dump in a `finally` block.
- The restore helper calls `ensure_postgres_db_exists(target_db_name)` and then invokes `pg_restore` using the shared configured PostgreSQL URL credentials, with `--clean --if-exists --no-owner --no-acl`.
- The control-plane endpoint terminates current DB connections before scheduling the callback, not inside a durable maintenance job. The request audit is committed after the callback is registered, and the callback executes after response handling.
- On the current source snapshot, the missing safety-backup helper prevents reaching the decrypt/pg_restore stage. Even after that mismatch is fixed, restore remains a destructive operation whose in-process dispatch has no durable restart/recovery contract.

#### 11.14.4 CSV migration transaction and temporary-file behavior

- The migration callback opens the temporary CSV and one tenant session. Each row uses a nested transaction/savepoint; row validation or constraint errors are counted and processing continues. A single outer `target_db.commit()` occurs after the loop.
- An outer exception records a failure audit and the session context closes; the source does not implement resumable chunk checkpoints or a durable per-row job cursor. A process death before the final commit can lose all uncommitted successful rows, and a retry can replay the whole file.
- The callback's `finally` removes the temp file after normal completion or Python-level exception. A process/container crash can bypass `finally`, leaving orphaned files; a restart can also lose a file held only on ephemeral container storage.
- The API writes and closes the temp file before registering the callback, commits the “started” audit, and returns a processing response. The source does not establish a durable job record tying the audit row to an immutable input artifact or execution attempt.
- Migration completion/failure audit writes use a separate control-plane session and swallow audit persistence errors after logging.

#### 11.14.5 Required remediation evidence

1. Reconcile the restore helper name/signature; retain the mandatory pre-restore snapshot and fail-closed gate.
2. Add restore tests for missing helper, snapshot failure, snapshot success, pg_restore failure, retry and concurrent restore exclusion.
3. Replace shared PostgreSQL credentials in tenant-targeted backup/restore processes with a separately approved backup/restore identity and explicit database allowlist, consistent with PostgreSQL database-per-tenant.
4. Avoid capturing plaintext backup keys in long-lived API-process closures; use a bounded worker identity and controlled secret retrieval.
5. Make backup artifacts/checksums a reconciled atomic unit with manifest/status, and make restore/migration jobs durable, observable and restart-safe.
6. For migration, define chunk/checkpoint and idempotency semantics before enabling automatic retry; preserve row-level error reporting and tenant-scoped execution.

No runtime code or tests were changed. These are source-inspection findings and proposed evidence requirements, not a claim that production credentials or deployments were inspected. PostgreSQL **database-per-tenant** remains unchanged. PR #70 remains the existing consolidated report; no new PR was created.

### 11.15 Restore helper contract and test coverage cross-check — 2026-11-13

Cross-checked the restore implementation and the existing backup/DR test module at source commit `20b8a5e48518c81820a7e28494fd73aeda33b46f`.

#### Confirmed helper contract mismatch

- `backend/control_plane/api/routers/fleet_ops.py` imports `create_encrypted_backup` from `backend.scripts.backup_service` in the restore callback.
- The complete `backend/scripts/backup_service.py` exposes `_dump_and_encrypt(db_name, encryption_key, output_dir)`, but does not define `create_encrypted_backup`.
- `backend/scripts/restore_tenant.py` exposes `restore_encrypted_backup(encrypted_file_path, target_db_name, backup_encryption_key, promote_to_cloud=False)`; it does not provide the missing safety-backup helper.
- `backend/scripts/backup_service.py` does not expose an equivalent `create_encrypted_backup` wrapper. Its `_dump_and_encrypt` expects the caller to supply an output directory and an already decrypted encryption key.
- This establishes a source-level API mismatch. It does not establish whether another deployment-specific monkeypatch or untracked module exists; none is shown in the inspected repository files.

#### Existing tests do not exercise this endpoint contract

- `tests/test_45_offhost_backups_and_restore_drills.py` tests checksum verification, Fernet decryption, off-host directory/S3 delivery, and `run_restore_drill` using mocked engine/subprocess/inspection calls.
- It does not import or invoke `restore_tenant_from_snapshot`, `_execute_restore`, or the missing `create_encrypted_backup` helper.
- The restore-drill test exercises `backend.scripts.restore_drill`, which is a separate path from the control-plane tenant restore callback.
- The provisioning/mail test module does not cover this restore route either.
- No runtime test was executed in this audit; these are static source and test-coverage observations.

#### Smallest safe correction candidate — not implemented

1. Define one explicit backup-helper contract in `backup_service.py` (or change the restore callback to the existing supported helper) with documented input types: tenant database name, decrypted key, output directory and returned artifact path.
2. Resolve the encrypted-vs-decrypted key boundary explicitly. The current manual-backup route decrypts the tenant key before calling `_dump_and_encrypt`; the restore route currently passes the encrypted key to the nonexistent helper. Do not pass an encrypted envelope to a helper expecting raw key material.
3. Preserve restore ordering: successfully create and verify a pre-restore snapshot first; only then call `restore_encrypted_backup`. Any snapshot error must stop restore.
4. Add focused tests at the control-plane callback boundary: missing/invalid helper contract, successful snapshot then restore, snapshot failure prevents restore, restore failure audit, successful completion audit, and tenant-key handling. Use synthetic database names/keys and mocked subprocesses; never use patient or production data.
5. Do not introduce a new database layout, schema-per-tenant, shared tenant schema, or global queue-policy change as part of this correction.

No code or tests were changed or executed. This section records a remediation candidate, not a patch. PostgreSQL **database-per-tenant** remains unchanged. PR #70 remains draft/open and no new PR was created.

### 11.16 Restore preparation ordering and artifact selection — 2026-11-13

A focused read of the complete restore endpoint (source commit `20b8a5e48518c81820a7e28494fd73aeda33b46f`, `backend/control_plane/api/routers/fleet_ops.py`, lines 656–735) found two additional control-boundary concerns:

1. **Database connections are terminated before the safety snapshot.** `_terminate_db_connections(control_db, tenant.db_name)` runs synchronously in the request handler before `_execute_restore` is registered. The mandatory safety snapshot is only attempted later inside the background callback. Therefore a missing helper or snapshot failure still aborts before `pg_restore`, but it does not prevent the earlier connection termination. This contradicts the stronger operational expectation that safety snapshot completion precedes restore preparation that interrupts tenant service.
2. **Snapshot selection is path-sanitized but not visibly tenant-bound.** The route reduces the supplied filename to `Path(filename).name` and joins it to the shared `backups` directory. In the inspected handler there is no explicit check that the artifact filename is associated with the requested tenant/database, nor a lookup of an artifact manifest binding tenant ID, database name, checksum and key version. Tenant-key decryption may reject an artifact encrypted for another tenant, but that is not a substitute for an explicit ownership check and integrity verification before destructive operations. This is a static observation of the handler; it is not evidence that cross-tenant restore succeeded.

#### Required remediation/test conditions

- Move connection termination into the controlled restore execution sequence and only perform it after a verified pre-restore safety snapshot; re-check active-connection handling and race conditions before `pg_restore`.
- Bind every restore artifact to the target tenant/database using trusted metadata or a signed/verified manifest. Reject mismatched ownership before terminating connections.
- Verify the selected artifact checksum and expected encryption/key metadata before any destructive action. Treat missing, malformed or mismatched metadata as a hard stop.
- Add tests proving: wrong-tenant artifact rejected with no connection termination; safety snapshot failure leaves tenant connections untouched and never calls restore; successful snapshot precedes termination and restore; checksum failure prevents termination and restore; restore failure is audited.
- Preserve the existing fail-closed rule. Do not simply remove the safety snapshot or catch-and-continue.

No runtime code or tests were changed or executed. PostgreSQL **database-per-tenant** remains unchanged; PR #70 remains draft/open; no new PR was created.

### 11.17 Backup catalog versus restore authorization and integrity — 2026-11-13

A follow-up compared the tenant backup listing, manual backup writer, restore endpoint and existing backup tests at source commit `20b8a5e48518c81820a7e28494fd73aeda33b46f`.

#### Confirmed source behavior

- `list_tenant_backup_snapshots(slug, ...)` enumerates only files matching `{tenant.db_name}_*.dump.enc` under the shared `backups` directory. This is a tenant-scoped presentation/catalog filter.
- `_dump_and_encrypt(db_name, ...)` names artifacts using `{db_name}_{UTC timestamp}.dump.enc` and writes a sibling `.sha256` sidecar after the encrypted artifact has been atomically renamed into place.
- `restore_tenant_from_snapshot(slug, filename, ...)` does **not** reuse the catalog filter or check that the selected filename begins with the requested tenant's database name. It accepts any existing basename under `backups/`.
- The restore handler does not read or verify the corresponding `.sha256` sidecar before terminating connections. The restore helper decrypts the artifact with the selected tenant's key later, after connection termination; Fernet authentication is useful cryptographic protection, but it does not replace explicit tenant/artifact authorization or the pre-disruption integrity gate.
- The current DR tests verify checksum behavior in `restore_drill` and off-host delivery, but the inspected test module does not exercise the control-plane restore route's catalog/restore authorization boundary.

#### Risk and required remediation

The UI/list endpoint's tenant-specific filename filter is not an authorization control. A caller with restore-route access can supply the name of another existing artifact in the shared directory. A mismatched encryption key may cause decryption to fail, but the attempt can still terminate the requested tenant's database connections first. This is a cross-tenant operational disruption risk; the inspected source does not prove that foreign data can be successfully restored.

Before any connection termination, the restore flow should:
1. Resolve the requested artifact through a tenant-bound backup catalog/manifest, or at minimum enforce the expected database-name prefix as an additional check (not the sole trust anchor).
2. Verify manifest tenant ID, database name, artifact identity, encryption/key version and checksum against trusted metadata.
3. Reject missing, mismatched or unverifiable metadata without terminating connections or invoking restore.
4. Create and verify the pre-restore safety snapshot, then terminate connections, then restore.
5. Add route-level tests for foreign-tenant filename rejection, missing/tampered checksum, malformed or mismatched manifest, and assertions that every rejection occurs before connection termination.

The existing filename convention and SHA-256 sidecar can support integrity checks, but a mutable sidecar stored beside the artifact is not by itself a trusted ownership manifest. A signed manifest or independently protected catalog record is needed for a strong tenant binding.

No runtime code or tests were changed or executed. PostgreSQL **database-per-tenant** remains unchanged. PR #70 remains the consolidated draft/open report; no new PR was created.

### 11.18 Shared backup-volume access and vault environment scope — 2026-11-13

Inspected the backup-related service definitions in `docker-compose.yml` at source commit `20b8a5e48518c81820a7e28494fd73aeda33b46f`.

#### Confirmed deployment configuration

- `api`, `worker`, `onboarding-portal` and `backup-sidecar` all mount the same named `hms_backups` volume at `/app/backups` without a read-only suffix; these are read-write mounts.
- The `backup-vault` mounts that volume at `/source:ro` and a separate `hms_vault_storage` volume at `/vault`. The read-only source mount is a positive control.
- The `backup-vault` service also declares `env_file: .env`, while its vault-mode code path scans/copies backup files and writes checksum sidecars; that code path does not require tenant database credentials or control-plane database access.
- The vault service runs the same application image and backup script as the backup sidecar, but with `--vault-mode`. Its current implementation copies newly seen encrypted dump files and sidecars, then chmods the destination files read-only. This is application-level file mode protection, not proof of storage-level WORM/immutability against a process with sufficient volume or host privileges.

#### Security and recovery implications

- A compromise or unintended file operation in any service with the shared read-write mount can potentially read, overwrite or delete the shared encrypted backup artifacts and checksum sidecars for multiple tenants. Encryption at rest limits plaintext exposure where tenant keys remain unavailable, but does not prevent backup deletion, replacement or denial of recovery.
- The shared writable mount also broadens the number of processes that can tamper with the artifact/sidecar pair. A checksum stored beside a mutable artifact cannot independently establish authenticity if both can be changed by the same writer.
- Supplying the complete `.env` to the vault-copy service expands the secrets available inside a component whose stated file-copy role does not need database or application credentials. This is a configuration exposure, not evidence that the vault process currently uses those credentials.
- The current Compose file does not by itself prove the underlying named-volume permissions, host access controls, backup retention policy, cloud object-lock configuration or production deployment overrides. Those require deployment evidence.

#### Required remediation and proof

1. Give each service only the backup access it needs. Prefer a dedicated backup writer and read-only consumers; remove the worker's backup mount if no reviewed worker task requires it.
2. Avoid mounting the full shared backup directory read-write into the general API and onboarding portal. Route backup operations through a narrowly scoped backup service or worker boundary.
3. Remove the full `.env` injection from `backup-vault`; provide only non-secret vault polling/configuration values and a minimal runtime identity.
4. Enforce immutability at the storage layer (for example, object lock/WORM or a separately administered append-only vault), not solely through `chmod 0400` in the same container.
5. Separate artifact and trusted manifest/checksum protection; prove that ordinary API/worker identities cannot rewrite or delete sealed artifacts or trusted ownership metadata.
6. Add deployment tests/evidence for mount read/write modes, effective container UID/GID and volume permissions, secret mounts/environment per service, and attempted cross-service artifact read/write/delete operations.
7. Keep tenant backup encryption keys and PostgreSQL database access out of the vault-copy identity. Preserve PostgreSQL **database-per-tenant**; this finding does not justify changing database topology.

No Compose/runtime code, tests, volumes, secrets or deployment settings were changed or executed. This is a static configuration review of the cited source snapshot, not proof of effective production mounts or permissions. PR #70 remains the consolidated draft/open report; no new PR was created.


### 11.19 Off-host backup delivery is not a uniform completion condition — 2026-11-13

Compared the scheduled backup cycle, manual backup endpoint, S3/remote delivery helper and \`tests/test_45_offhost_backups_and_restore_drills.py\` at source commit \`20b8a5e48518c81820a7e28494fd73aeda33b46f\`.

#### Confirmed source behavior

1. **Manual backup skips off-host delivery.** \`trigger_manual_backup_snapshot()\` in \`backend/control_plane/api/routers/fleet_ops.py\` calls \`_dump_and_encrypt(tenant_db_name, raw_key, backup_dir)\`, then records \`BACKUP_COMPLETED\`. It does not call \`deliver_backup_offhost()\`. Therefore a manually triggered snapshot can be reported as completed after local artifact creation without being copied to the configured remote directory or S3 target.
2. **Scheduled cycle does not enforce off-host success.** \`run_backup_cycle()\` calls \`deliver_backup_offhost()\` but does not inspect its returned \`delivered\` field before incrementing the cycle count. The helper reports disabled delivery as \`delivered: false\`, and catches S3 upload errors into a result with \`delivered: false\`; these outcomes do not raise to the caller. The cycle can therefore count a local encrypted dump as a completed backup even when configured off-host delivery failed.
3. **S3 path has no application-level post-upload verification in this helper.** The code calls \`upload_file()\` for the artifact and checksum sidecar and marks delivery true after both calls return. It does not read the uploaded objects back, compare their bytes/checksum, or request/configure object-lock retention/versioning in this function. Bucket policy, versioning and object-lock settings may exist outside this repository and were not inspected; no claim is made that the deployed bucket lacks them.
4. **Existing tests do not cover the completion contract.** \`tests/test_45_offhost_backups_and_restore_drills.py\` verifies remote-directory copy/checksum behavior and mocks S3 to assert that two \`upload_file()\` calls occur. It does not test S3 upload failure propagation into \`run_backup_cycle()\`, read-after-write verification, object-lock/retention evidence, or the manual backup endpoint's off-host behavior.

#### Reliability and recovery implications

- A \`BACKUP_COMPLETED\` audit event from the manual endpoint currently means the local encrypted snapshot was created; it does not mean the configured off-host copy exists.
- A scheduled cycle's returned count can represent local dump creation rather than successful completion of the configured disaster-recovery delivery requirement.
- S3 SDK upload-call success is evidence that the calls returned without raising, not independent evidence that the expected artifact and trusted metadata are retrievable, correctly bound to the tenant, or protected against deletion/overwrite.
- This is a source-code and test-coverage finding. Effective S3 bucket policy, object-lock retention, replication, IAM boundaries and remote storage behavior require deployment-side evidence.

#### Required remediation and proof

1. Define distinct lifecycle states and audit events for local snapshot creation, off-host upload acceptance, remote verification and immutable-retention confirmation. Do not label the overall backup as off-host complete until the required configured destination has passed its verification gate.
2. Reuse one tenant-bound delivery path from both scheduled and manual backup flows. Manual backup must either deliver and verify off-host or explicitly report that it created a local-only snapshot; do not silently imply DR completion.
3. Make scheduled cycle accounting distinguish local snapshots from off-host-complete snapshots. When off-host delivery is enabled and required, a false delivery result must be surfaced and counted as a delivery failure rather than silently treated as full success.
4. For S3, verify the uploaded artifact and manifest/checksum through a trusted read-after-write or equivalent provider-supported integrity mechanism. Bind tenant/database/artifact identity in protected metadata; do not treat a colocated mutable SHA-256 sidecar as an authenticity control.
5. Obtain deployment evidence for bucket versioning, object-lock mode/retention, delete/overwrite permissions, replication, encryption and the exact IAM identity used by the backup writer. Keep vault administration separate from ordinary application identities.
6. Add tests for: manual backup with off-host enabled and disabled; remote/S3 failure reflected in task status and cycle accounting; partial upload (artifact succeeds, checksum fails); uploaded-object verification failure; idempotent retry; and no false \`BACKUP_COMPLETED\`/DR-complete event before the required delivery gate.
7. Preserve tenant separation and PostgreSQL **database-per-tenant**. This finding requires consistent backup lifecycle semantics, not a database-topology change.

No runtime code, tests, S3 configuration, bucket policy, credentials or deployment settings were changed or executed. This is a static source/test review; production storage controls remain unverified. PR #70 remains the consolidated draft/open report; no new PR was created.

### 11.20 Open pull-request portfolio and safe consolidation order — 2026-11-13

A live GitHub API inventory of the repository's open pull requests found 54 open PRs: 52 drafts and two non-drafts (#17 and #19). The inventory and changed-file lists were reviewed to distinguish implementation work, audit evidence and stacked documentation history.

#### Portfolio groups

| PRs | Purpose | Current disposition |
|---|---|---|
| #17 | Combined mainline security/lifecycle audit | Preserve as audit history; do not merge as implementation |
| #19 | Runtime remediation for AUD-001–003 | Keep open for focused review, CI evidence and remaining remediation |
| #20–#43 | AUD-004 federation actor assertion, import recovery, protocol, governance and review series | Stacked documentation/review chain; preserve until its canonical content is safely consolidated |
| #44–#69 | Database-per-tenant identity and DBID-R01–R81 proposal/review series | Stacked documentation/review chain; preserve until its canonical content is safely consolidated |
| #70 | Implementation-readiness and accountable-owner report | Keep as the current main-based readiness record |
| #71 | Disposable PostgreSQL ACL proof harness | Keep as synthetic test evidence, with its fixture/deployment limitations explicit |

#### Canonical checkpoints and stack dependencies

- PR #40 is the proposed canonical protocol/governance checkpoint for the #20–#39 series, but its base is the PR #39 branch, not main. PR #41 independently reviews it. PRs #42–#43 then add and review the CAN-01 source-owned boundary.
- PR #68 is the consolidated DBID-R74–R81 proposal, but its base is the PR #67 review branch, not main. PR #69 independently reviews it.
- PR #44 proposes the PostgreSQL database-per-tenant identity model; #45 reviews it. Later DBID proposal/review pairs continue as a stack. The latest #68/#69 pair does not establish that every earlier stack document is merged into main.
- PR #70 is based directly on main and records readiness findings and owner gates; it is not a replacement for every detailed protocol/design document in the stacks.
- PR #71 is a separate disposable PostgreSQL ACL proof harness and does not establish production workload identity, secret separation or deployed grant boundaries.

#### JSON Schema versus PostgreSQL schema clarification

The changed-file inventory confirms that PRs #60, #62, #64 and #66 introduce or revise files under docs/schemas/ with .schema.json names. These are JSON Schema documents describing JSON payloads/contracts. They are not PostgreSQL schema/namespace migrations, do not convert database-per-tenant to schema-per-tenant, and do not justify changing the selected tenant storage topology. The canonical architecture remains PostgreSQL **database-per-tenant**.

#### Safe cleanup decision

Do not bulk-close #20–#69 yet. These are stacked PRs whose base branches reference preceding PR branches; the canonical checkpoint PRs themselves are not based on main. Closing predecessors before preserving and validating their unique content risks losing the review trail and breaking the remaining stack's intended comparison context.

The safe sequence is:

1. Keep #17, #19, #70 and #71 open for their distinct audit, remediation, readiness and synthetic-evidence purposes.
2. Treat #40/#41 and #68/#69 as the principal protocol and DBID consolidation/review checkpoints, while retaining #42/#43 as the CAN-01 boundary checkpoint.
3. Reconcile all unique accepted requirements, unresolved findings and review dispositions into a single main-based canonical document set (or a deliberately bounded set of documents), retaining links to the original PRs for traceability.
4. Validate that the canonical documents preserve the full decision history, unresolved Critical/High findings, explicit non-authorization and database-per-tenant architecture.
5. Only after that content is available on a durable main-based branch should superseded stack PRs be closed in dependency order. Do not merge all 50 PRs individually and do not close them merely to reduce the open count.

No PRs were closed, merged, rebased or retargeted during this inventory. No runtime code, PostgreSQL objects, migrations, credentials, deployment settings or patient data were touched. The PR inventory is a point-in-time repository view; it does not constitute production-readiness evidence.


## Section 41 — Domain-operation trace extension: retention and clinical / pharmacy / procurement / RCM

**Evidence added:** source review on the AUD-004 documentation branch of:
- `backend/domains/privacy/retention_service.py`
- `backend/domains/clinical/services.py` (LIS delta-check helper)
- `backend/domains/diagnostics/router.py` (result submission caller)
- `backend/domains/pharmacy/router.py` (prescription dispensing)
- `backend/domains/procurement/router.py`, `backend/domains/procurement/services.py`, and procurement models
- `backend/domains/billing/rcm_services.py` and `backend/domains/billing/services.py`

### Findings added

| Workflow | Source-grounded operations | Privilege implication / status |
|---|---|---|
| Retention legal holds | SELECT active legal holds and held patient IDs | Tenant-bound retention identity requires SELECT on legal-hold relations |
| Privacy decision audit retention | SELECT candidate count; DELETE eligible ALLOW rows; excludes retention/unlock proof rows | DELETE is real and must be isolated from ordinary API; audit execution proof is separately INSERTed |
| Patient retention | SELECT patients plus encounter/admission/invoice clocks and six reviewed dependency references; UPDATE anonymized fields or DELETE eligible patient rows | Privileged tenant operation; current dependency-query exception handling is fail-open and hard-delete dependency coverage is unproven |
| LIS delta-check | SELECT config and latest prior task/order; caller updates task result/review state | Helper itself read-only; caller writes must be mapped separately |
| Prescription dispensing | SELECT/lock prescription, items, invoice, inventory batch and medication; possible invoice INSERT; UPDATE stock, dispensed quantity, invoice totals and prescription status; INSERT invoice lines | Clinical pharmacy runtime needs targeted read/write privileges; BCMA administration remains untraced |
| Procurement 3-way match / AP | SELECT PO/GRN/invoice relations; UPDATE invoice status/link; INSERT expense | Separate mutable workflow state from append-only payment ledgers |
| Vendor purchase return | SELECT/lock GRN/items/batches and prior return totals; INSERT immutable return header/items and expense; UPDATE batch stock | Return ledger should be SELECT/INSERT only; batch stock is mutable |
| Patient indent issue/return | SELECT/lock indent/items/batches/allocation history; UPDATE stock/issued quantities/status/invoice; INSERT invoice lines, issue allocations and return events | Immutable allocation/return evidence needs INSERT only; exact return tail and FK/trigger behavior still need proof |
| RCM clinical charge | SELECT encounter/service/insurance/tariff and idempotency event; INSERT invoice/line/charge event; UPDATE invoice totals/tax | Transitive runtime writes extend beyond billing route's direct ORM statements |
| Diagnostic billing reversal | SELECT/lock draft invoices and lines; DELETE matching draft invoice lines; recalculate invoice totals | Clinical caller inherits billing DELETE and UPDATE needs |

### Readiness blockers / caveats

- Retention hard-delete dependency queries swallow exceptions; a missing/failed reference query can allow deletion without that dependency being checked. This must be changed to fail closed and proven against catalog-derived FK coverage before production execution.
- Retention dry-run candidate/affected count does not apply the non-dry-run reference filtering and can overstate deletable patients.
- Unknown retention category returns a no-op status rather than rejecting unsupported policy categories; behavior requires an explicit fail-closed policy decision.
- Retention policy executor writes a permanent run ledger and privacy audit entry on non-dry-run execution. Retention therefore requires a separate privileged tenant-bound workload, not the normal clinical runtime.
- Delta evaluator is read-only; the caller's task update and any critical-alert/evidence side effects need full caller tracing.
- Pharmacy dispensing uses row locks and mutable stock/prescription/invoice rows; BCMA and controlled-substance pathways are not certified by this trace.
- Procurement append-only evidence relations must not inherit broad table UPDATE/DELETE. Trigger/catalog proof remains outstanding.
- RCM/payment/deposit/refund/TPA/bank settlement flows remain incomplete; no complete billing grant profile can be approved.

### Updated next gate

Complete remaining pharmacy BCMA and controlled-substance return/administration paths, procurement supplier payment and bank reconciliation plus patient-indent return, billing payment/deposit/refund/RCM and all remaining worker handlers. Then run SQL capture on disposable migrated PostgreSQL databases and independent-login positive/negative privilege tests. No production grants until that evidence and independent DBA/security review are complete.

No runtime/SQL/migration/Compose/credential/secret/database/production change. No destructive retention execution or patient-data access. PostgreSQL database-per-tenant remains invariant.


## Section 42 — Extended domain operation and privilege map: BCMA, controlled substances, supplier settlement and patient billing

**New source paths reviewed:** `backend/domains/pharmacy/services.py`, `backend/domains/pharmacy/router.py`, `backend/domains/procurement/bank_reconciliation.py`, `backend/domains/procurement/investigations.py`, `backend/domains/procurement/escalation.py`, `backend/domains/procurement/notification_inbox.py`, `backend/domains/procurement/router.py`, and `backend/domains/billing/router.py`.

| Workflow | Database operations established from source | Privilege boundary / unresolved proof |
|---|---|---|
| BCMA verification | SELECT encounter/patient/prescription/item/medication, allergy and prior eMAR context; INSERT blocked/warning/success BCMA audit; INSERT eMAR; UPDATE prescription dispensed count | Targeted clinical evidence identity; allergy helper and exact loader SQL need capture |
| Pharmacy return | SELECT/lock prescription, invoice, item, batch and medication; UPDATE stock, dispensed quantity, draft invoice lines/totals and prescription status; DELETE fully returned draft invoice line; INSERT return log; optionally INSERT refund voucher | Mixed mutable inventory/billing state and return evidence; no broad table grant |
| Controlled-substance movement | SELECT/lock vault, witness user/permissions, optional encounter/prescription, prior movement aggregates; UPDATE vault; INSERT movement log | Movement ledger SELECT/INSERT only per Section 21; verify trigger and exact relations |
| Bank statement import | SELECT duplicate batch/transaction identities; INSERT statement batch and lines | Append-only statement evidence; SELECT/INSERT only, verify unique constraints and triggers |
| Bank-payment matching | SELECT/lock statement line/payment and prior match aggregates; INSERT match row | Append-only match ledger SELECT/INSERT only |
| Supplier payment request | SELECT/lock vendor/invoices/expenses and duplicate/paid/reserved aggregates; INSERT request and allocation rows | Mutable request workflow is distinct from executed payment ledger |
| Supplier payment execution | SELECT/lock request/vendor/invoice/expense and payment aggregates; INSERT supplier payment/allocation; UPDATE invoice, expense and request state | Executed payment/allocation ledger SELECT/INSERT only per Section 21; workflow rows mutable |
| Reconciliation investigations | SELECT source/SLA/user; INSERT investigation and immutable events; UPDATE current investigation state/version/assignment/quality; SELECT history | Split mutable case state from append-only event evidence |
| Escalation/preferences/inbox | SELECT/UPDATE policy and preferences; INSERT version/config events; SELECT outbox; UPDATE read timestamp | Config events append-only; preference/policy/outbox current state mutable |
| Patient payment | SELECT/lock invoice; duplicate check; INSERT payment receipt; UPDATE invoice paid amount/status | Payment capture needs targeted billing DML |
| Payment reversal | SELECT/lock invoice/receipt/deposit; UPDATE invoice/deposit; DELETE payment receipt | Explicit DELETE is present; payment receipt not established as immutable ledger |
| Deposit and refund | SELECT patient/encounter; INSERT deposit; UPDATE deposit and invoice during application/refund; INSERT adjustment receipt/refund voucher; privacy audit reads/writes on listing | Finance workload plus privacy audit transitive operation |

### Additional readiness notes

- BCMA writes audit evidence on blocked and warning outcomes before returning a conflict response. Tests must assert that failed clinical verification attempts persist the evidence row, while no eMAR administration is created.
- Controlled-substance service maintains a running vault balance and validates return quantity against prior movement-log aggregates. The ledger is source-grounded as append-only by Section 21, but trigger/catalog proof and independent raw-SQL denial remain required.
- Supplier payment request tables are workflow state; supplier payment and allocation tables are executed settlement evidence. Bank statement batches/lines and payment-match rows are separately append-only evidence.
- Reconciliation investigation rows are mutable; investigation event rows are immutable evidence. Notification preferences and outbox read state are mutable, while notification configuration events are append-only.
- Payment reversal currently deletes a receipt and adjusts invoice/deposit balances. The final financial audit model must explicitly decide whether reversal is allowed to delete or should instead create a compensating reversal event; no implementation change is made here.
- No full statement-level SQL capture, complete catalog/trigger comparison, independent workload-role tests or external bank-provider proof has been performed.

### Updated next gate

Finish source tracing for the remaining bank reconciliation candidate/aggregation and governance report paths, remaining billing RCM/insurance settlement workflows, pharmacy return/adjustment routes and all queue handlers. Then capture SQL on disposable migrated PostgreSQL databases and execute positive/negative tests with independent workload logins. Retain the current database-per-tenant architecture and do not produce production grants until DBA/security review.

No runtime/SQL/migration/Compose/credential/secret/database/production change. No patient or financial data access or mutation. PostgreSQL database-per-tenant remains invariant.

### Section 43 — Reconciliation, insurance settlement, pharmacy adjustment and worker execution evidence

**Evidence batch:** source-level trace of bank reconciliation candidates/matching, monthly governance snapshots, insurance claim settlement, direct pharmacy batch adjustment/void, and all registered core queue handlers. This is not live database permission certification.

**Reviewed source:** `backend/domains/procurement/bank_reconciliation.py`, `backend/domains/procurement/investigations.py`, `backend/domains/insurance/router.py`, `backend/domains/billing/rcm_services.py`, `backend/domains/pharmacy/router.py`, `backend/core/queue.py`.

#### Findings and operation map

| Workflow | Read set (source-grounded) | Write set (source-grounded) | Readiness implication |
|---|---|---|---|
| Bank candidate view | Statement lines, batches, supplier payments/allocations, payment requests and match aggregates | None | Live derived candidate list; not bank-feed authenticity proof or a durable reconciliation result |
| Bank match | Locked statement line and supplier payment; prior match rows and aggregate matched amounts | INSERT supplier-payment bank match | Preserve append-only match ledger; prove row-lock/unique constraints under concurrent independent sessions |
| Governance report | Investigation/event history, SLA deadlines, quality state and current backlog | INSERT canonical JSON snapshot + SHA-256 digest | Hash is not signature; trigger/ACL immutability and digest verification remain separate gates |
| Insurance claim submission | Invoice/lines, patient policy/plan, preauth and tariffs | INSERT insurance claim | Application-level duplicate check needs DB uniqueness/concurrency proof |
| Insurance settlement | Locked claim and invoice; approved payable and remaining invoice balance | INSERT insurance PaymentReceipt; UPDATE invoice paid/status and claim settlement fields | Claim is marked SETTLED even when accepted amount is below insurer payable; partial settlement semantics and retry/idempotency require finance decision and PostgreSQL proof |
| Pharmacy stock adjustment | Locked InventoryBatch | UPDATE stock quantity | No separate stock-adjustment ledger INSERT observed in this route |
| Pharmacy batch void | Locked InventoryBatch | UPDATE stock quantity to zero | Reason/actor/before-after event not established as a dedicated immutable subledger in this route |
| Retention execution worker | CP active tenant lookup; tenant approved policy and actor lookup | Delegates to retention service; category-specific writes are detailed in Section 26 | Shared engine registry/credential does not isolate DB authority by tenant |
| Daily retention sweep | CP active tenant registry; per-tenant approved retention revision | Enqueues tenant-scoped jobs | One scheduler process opens tenant sessions across fleet; CP scheduler/tenant worker separation remains required |
| Email worker | Payload only + configured mailer | External mail delivery; no tenant DB write in handler | Delivery provider, retry idempotency and durable outbox evidence require separate validation |

#### Specific issues to carry into remediation

1. **Bank candidate and matching proof:** candidate categories are computed live from statement/payment/request/match records. Matching locks the statement line then supplier payment and inserts an immutable match row after amount checks. Validate uniqueness, overmatch prevention and race behavior with two independent PostgreSQL sessions. Statement import's preflight duplicate checks need matching DB constraints.
2. **Governance snapshot trust:** canonical JSON + SHA-256 gives deterministic content digest, not signer identity or trusted timestamp. Confirm append-only trigger, owner, ACL and raw SQL UPDATE/DELETE denial for `procurement_reconciliation_governance_reports`.
3. **Insurance settlement semantics:** a single settlement request changes claim status to SETTLED regardless of whether settled amount equals full insurer payable. Decide whether partial settlement must be represented explicitly, how residual payable is tracked, and how insurer remittance corrections/reversals are compensated. Add an idempotency key and concurrency/failure-injection tests before considering this workflow financially production-ready.
4. **Deposit/claim calculation basis:** claim insurer payable is calculated from invoice net amount before advance deposits, while claim claimed amount uses outstanding invoice balance. FIN-001 comment explains the deliberate gross basis, but the finance owner must approve and test interactions with deposits, copay, disallowed items, preauth caps and partial receipts.
5. **Inventory adjustment evidence:** direct adjustment and void routes mutate batch stock without a dedicated immutable stock movement record in those handlers. Inventory subledger coverage, reason capture, authorization, reconciliation and compensating entries are P0 evidence requirements for production pharmacy inventory.
6. **Queue execution authority:** only three handlers are registered in the inspected queue module. Retention worker resolves tenant through CP but uses the common tenant engine registry; daily sweep opens a tenant session per active tenant. `sync_fallback=True` may execute a handler synchronously when Redis enqueue fails. Privileged/destructive handlers must not inherit ordinary API/scheduler credentials or synchronous fallback.
7. **Queue durability:** task state is Redis hash/list/zset state with TTL and retry/dead-letter behavior, not a durable relational job ledger. Prove delivery/ack/replay behavior and failure windows; no claim of exactly-once execution is supported.

#### Required owners and acceptance evidence

- **Finance owner:** approve claim gross-vs-outstanding basis, partial settlement lifecycle, remittance reversal/adjustment and receipt compensation rules; provide reconciled examples covering deposits, copay, preauth and insurer cap.
- **Pharmacy owner:** define stock adjustment/void reason codes, authorization, immutable movement ledger and correction semantics; reconcile batch-level opening + receipts - dispenses + returns +/- adjustments = closing stock.
- **Security/DBA:** map these operations to per-workload DB identities under database-per-tenant; prove no cross-tenant/CP access and raw SQL denial for append-only evidence.
- **Platform owner:** split CP sweep scheduler, tenant-bound worker and isolated retention executor; remove synchronous fallback for privileged jobs; prove queue durability/retry/idempotency and least-privilege credentials.
- **QA:** add independent-session PostgreSQL tests for duplicate statement import/match, overmatch races, duplicate claim submission, simultaneous settlement, partial settlement, timeout-after-commit retry, governance snapshot tamper attempts, stock adjustment/void audit, and worker tenant-boundary/fallback behavior.

**Gate:** source trace is more complete, but AUD-004 is still blocked on deterministic ORM-vs-catalog inventory, SQL/trigger proof, independent PostgreSQL workload-role tests, backup/restore proof, and production identity/network/secret validation. No final grant SQL is approved.

No runtime/SQL/migration/Compose/credential/secret/database/production change. No patient or financial data access or mutation. PostgreSQL database-per-tenant remains invariant.

### Section 44 — Metadata-root and live-catalog proof gap

**Evidence batch:** inspection of both Alembic environments, both declarative bases, CP ORM models, tenant audit model and current production role SQL. Source-only; no live PostgreSQL catalog access.

#### Established facts
- Tenant Alembic loads 23 domain model modules into tenant `Base.metadata`.
- CP Alembic uses separate `ControlBase.metadata`, currently containing 11 CP table declarations.
- CP and tenant migrations use separate metadata roots and the same transaction-scoped advisory-lock key.
- `ControlPlaneAuditLog` immutability in the inspected CP model is enforced through SQLAlchemy ORM event listeners, not demonstrated DB triggers.
- The inspected `SecurityAuditExportRegister` model's local trigger DDL is conditional on SQLite. PostgreSQL protection must be demonstrated from migration source and live catalog, not inferred from this file.
- Current `deployments/postgres-roles.sql` still contains blanket app grants on all public tables/sequences in the literal `postgres` database, cluster-wide `pg_read_all_data` for backup, and `pg_monitor` for exporter. No per-tenant least-privilege grant topology is established by this file.

#### Blocking proof
1. Export both metadata roots deterministically and compare against fresh migrated CP + two tenant database catalogs.
2. Include migration-only/script-created objects, functions, triggers, sequences, views, materialized views, extensions, RLS, large objects, owners, ACLs, memberships and PUBLIC grants.
3. Resolve each append-only claim with PostgreSQL trigger/function definitions and negative raw SQL UPDATE/DELETE tests.
4. Prove clean restore recreates the same object/owner/ACL/default-privilege inventory before cutover.
5. Run tenant A / tenant B / CP negative connection and object-access tests with the actual workload identities.

#### Owner and acceptance criteria
- **DBA/platform:** deliver catalog snapshots from disposable migrated CP + two tenant DBs, with secrets redacted and no patient rows exported.
- **Backend:** provide stable metadata export and explain every migration-only or script-created object.
- **Security:** independently verify ACLs, ownership, memberships, PUBLIC privileges, trigger bypass resistance and raw SQL denial.
- **QA:** preserve the comparison as repeatable CI evidence and fail on unexplained drift.

**Gate:** no production grant generation until metadata-vs-catalog deltas and workload-role proofs are complete. The current source trace narrows the inventory boundary but is not an actual PostgreSQL inventory or permission certification.

No production/runtime/SQL/migration/Compose/credential/secret/database change. PostgreSQL database-per-tenant remains invariant.


### Section 45 — CI proof harness gap: migration execution and catalog parity remain unimplemented

**Evidence batch:** existing AUD-004 role-bootstrap test, on-demand workflow, isolated tenant A/B/CP Compose fixture, and both Alembic configuration paths. Source-only review; no database migration or live catalog capture was executed.

#### Established
- The existing role-bootstrap CI test runs the actual production role function against disposable PostgreSQL and intentionally characterizes unsafe current grants. It does not invoke Alembic.
- The separate identity fixture proves synthetic tenant A, tenant B and CP connection boundaries using isolated probe containers. It does not build the production ORM object set or execute the migration graph.
- Tenant and CP Alembic have separate URL resolution and metadata roots. CI must set explicit per-database URLs before each migration invocation and verify the resulting version table in the intended database.

#### Blocking actions
1. **Backend:** add deterministic sorted exports for tenant `Base.metadata` and CP `ControlBase.metadata`; keep exports separate.
2. **Platform/DBA:** execute CP migration and tenant migration independently against three synthetic PostgreSQL databases in an isolated job; assert migration heads/version state for each target.
3. **Security/DBA:** capture owners, ACLs, default ACLs, memberships, PUBLIC, extensions, sequences, views, materialized views, RLS, large objects, trigger definitions and function security attributes from each database.
4. **QA:** compare metadata and catalogs, classify all differences, and fail on unexplained drift or missing expected protection. Include raw SQL UPDATE/DELETE attempts against claimed append-only tables.
5. **Platform/DR:** restore a disposable backup and rerun the same inventory/ACL comparison before restore parity can be accepted.

**Gate:** AUD-004 remains blocked. Existing passing CI proofs are valuable but orthogonal: neither proves the migrated production object inventory, trigger integrity, restore parity nor final least-privilege grants. No final grant SQL is approved.

No runtime/SQL/migration/Compose/credential/secret/database/production change. PostgreSQL database-per-tenant remains invariant.


### Section 46 — First repeatable three-database migration/catalog harness committed; execution pending

**Implementation:** PR #71 adds a dedicated disposable PostgreSQL 17 CI job and a test that runs the real Alembic migration graphs against three newly created synthetic databases: one control-plane database and two independent tenant databases. It explicitly uses the production Alembic environments and revisions, not ORM `create_all()`.

**Captured evidence:** separate tenant/CP metadata manifests; live schemas/tables/columns/constraints/indexes/enums/sequences/views/materialized views; migration version rows; owners; extensions; routine and trigger definitions/security attributes; RLS policies; table grants; default ACLs; role memberships; database and schema ACLs. The test records table-level metadata/catalog deltas in a JSON artifact and asserts both tenant databases reach identical migration version sets.

**Safety:** new databases are synthetic and uniquely named; test refuses pre-existing names; workflow uses a fresh PostgreSQL 17 service and synthetic credentials; no production secrets, patient rows or financial records are used. No bootstrap, seed, or application startup is invoked.

**Status:** source and workflow files were re-fetched and verified on PR #71. The GitHub integration available in this session cannot dispatch Actions, so the new workflow job is committed but not yet executed. Migration success, actual catalog parity and resulting deltas are not claimed. The next acceptance action is to dispatch the on-demand workflow with scope `reconciliation`, inspect the new job logs and review the uploaded report; fix any migration failure or unexplained delta before advancing.

**Gate:** AUD-004 remains blocked. This is a characterization harness, not a least-privilege or restore acceptance result. Raw SQL append-only denial, independent workload-role tests, restore parity and production identity/secret/network proof remain outstanding.


### Section 47 — Catalog characterization boundaries corrected after code review

A source-level review confirmed that PR #71 already records table grants, database/schema ACLs, default ACLs and role memberships. The harness report's limitation text was corrected to distinguish *captured* evidence from *evaluated* evidence. These ACL/membership snapshots are captured but not interpreted or asserted. Column, sequence, routine and type ACLs, role attributes and cluster-wide settings remain outside this pass. Trigger/routine definitions and security settings are captured but not evaluated; raw SQL append-only denial is still outstanding.

This is a test-report accuracy correction only. It does not add a least-privilege assertion or alter production/runtime/SQL/migration/Compose/credential/secret/database behavior. Latest-head migration execution and catalog artifact review remain pending. AUD-004 remains blocked.


### Section 48 — Column-level ORM/catalog characterization added

The PR #71 report now computes column-name deltas for each of the three independently migrated databases. It identifies metadata columns missing from the live catalog and catalog columns missing from the relevant ORM metadata, complementing table-level deltas. This is a report-only comparison; it does not assert parity, compare type/constraint/index semantics, or approve any difference.

The workflow has not yet been run on this new head. AUD-004 remains blocked pending real CI execution, artifact review, and the separate privilege/immutability/restore proofs.



### Section 49 — Expanded PostgreSQL ACL and role-attribute capture added

PR #71's disposable migration/catalog characterization test now expands explicit PostgreSQL ACL entries from the catalogs for relations (including sequences and views), columns, routines and types. The expanded records preserve PUBLIC grantees, grantors, privilege types and grant-option flags. The report also captures role attributes, including superuser, role/database creation, login, replication, BYPASSRLS, connection limit and validity timestamp. These additions complement the existing database/schema ACL, default-ACL and membership snapshots.

**Boundary:** this is capture, not acceptance. The harness does not yet interpret effective privileges, calculate inherited/ownership rights, assert least privilege, or test connection/object access under each production workload identity. The migration/catalog workflow has not been executed on this new head, so SQL compatibility and artifact contents remain unverified. AUD-004 remains blocked.

No production/runtime/SQL/migration/Compose/credential/secret/database/role change. The additions are test-only catalog queries and report fields. PostgreSQL database-per-tenant remains invariant.



### Section 50 — Expanded database, schema and default ACL capture added

The disposable PostgreSQL catalog report now expands database, schema and default-object ACLs into individual privilege records, preserving PUBLIC grantees, grantors, privilege names and grant-option flags. The original raw ACL text snapshots remain available for cross-checking. This complements the explicit relation, column, routine and type ACL expansion in Section 49.

**Boundary:** catalog visibility/capture is not a least-privilege verdict. Effective privileges inherited through role memberships, implicit ownership authority, PUBLIC defaults, predefined-role semantics and privileges outside the connected database still require dedicated interpretation and independent-session tests. The latest workflow head has not been executed; SQL compatibility and report output remain unverified. AUD-004 remains blocked.

No production/runtime/SQL/migration/Compose/credential/secret/database/role change. Test-only catalog queries/report fields were added. PostgreSQL database-per-tenant remains invariant.


### Section 51 — Synthetic workload proof extended to object-level write and DDL denial

PR #71 now extends the independent-login PostgreSQL fixture beyond database CONNECT isolation. Each tenant A, tenant B and control-plane probe asserts that its own synthetic marker is readable, schema USAGE is allowed, schema CREATE is denied, and the marker relation grants SELECT without INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES or TRIGGER. Negative execution checks attempt INSERT, UPDATE, DELETE, TRUNCATE, CREATE SCHEMA and CREATE TABLE under the corresponding unprivileged login and require PostgreSQL insufficient-privilege errors.

**Boundary:** this verifies the fixture's intended narrow ACL contract only. The synthetic roles and marker relations are not the deployed HMS runtime roles or migrated application objects. It does not prove production role mapping, per-table grant completeness, sequence/function/type rights, ownership, inherited memberships, effective privileges on every relation, append-only evidence-table triggers, or backup/restore behavior.

**Execution status:** the test changes are committed on PR #71 at `e8c9f730cdd0ff6a9a0660f8f4207e44f868384c`. No workflow run for this head has been observed; these assertions are not yet reported as passing. The on-demand reconciliation workflow must be dispatched and its three independent probe jobs reviewed before this proof slice can be accepted.

No production/runtime/SQL/migration/Compose/credential/secret/database/role change. Only the synthetic test assertions changed. PostgreSQL database-per-tenant remains invariant. AUD-004 remains blocked.


### Section 52 — Migrated PostgreSQL append-only trigger catalog assertions added

PR #71 now turns the migration-installed PostgreSQL append-only trigger inventory into explicit assertions in the disposable three-database migration/catalog harness. For both independently migrated tenant databases, the test requires the expected row-level `BEFORE UPDATE OR DELETE` trigger on 14 evidence tables: the federation transfer log; security audit export register; supplier payment/allocation; bank reconciliation; purchase return; patient indent provenance; reconciliation investigation event; notification configuration event; and governance report tables. The security audit export register assertion uses the PostgreSQL migration-installed `trg_security_audit_export_no_mutation` trigger.

The catalog check also asserts that each expected trigger is enabled for ordinary origin sessions, its trigger function is not `SECURITY DEFINER`, and its PostgreSQL trigger type includes row-level BEFORE UPDATE and DELETE events. The catalog query now captures `tgtype` and `tgenabled` to support those assertions. This validates the migration-installed trigger definitions after actual Alembic execution rather than relying only on model listeners or source comments.

**Behavioral proof added for one table:** after migrations, the test inserts one synthetic user and one synthetic `security_audit_export_register` row inside a transaction in each tenant database, then attempts raw SQL UPDATE and DELETE. It requires the PostgreSQL trigger's append-only exception and rolls the fixture transaction back, leaving no synthetic rows behind. This is the first populated-row mutation test; it covers this one table only.

**Boundary:** the remaining 13 expected evidence tables receive catalog assertions only, not populated-row mutation tests. TRUNCATE denial, runtime owner/DDL/trigger-disabling authority, and broader raw-SQL coverage remain unproven. The test job must execute on the latest PR #71 head and the resulting catalog artifact/logs must be reviewed. No trigger assertion or behavioral test is claimed to have passed yet.

The expected trigger map now also includes `security_audit_export_register`, whose PostgreSQL trigger is installed by migration `a9c4e7b2d610`. This closes an omission in the source-derived evidence-table inventory; it does not add or alter the migration itself. The disposable harness also now checks actual raw SQL UPDATE/DELETE rejection on a populated synthetic row for this register in both tenant databases, with all fixture writes rolled back.

No production/runtime/SQL/migration/Compose/credential/secret/database/role change. Only disposable test assertions and catalog capture changed. PostgreSQL database-per-tenant remains invariant. AUD-004 remains blocked.


### Section 53 — RLS table enablement state and tenant catalog delta reporting completed

The PR #71 catalog snapshot now records `relrowsecurity` and `relforcerowsecurity` for every ordinary and partitioned application table in each disposable database, in addition to enumerating `pg_policies`. This distinguishes tables with RLS enabled/forced from policy rows alone, including the important case where RLS is enabled but no policy exists. The table-delta artifact also reports tenant A and tenant B migration-only tables independently instead of using tenant A as a proxy for both.

**Boundary:** RLS state is captured, not approved. The harness does not yet evaluate policy expressions, effective role behavior under RLS, `BYPASSRLS`, ownership bypass, or FORCE RLS behavior using the deployed workload identities. No least-privilege conclusion follows from this snapshot. The latest-head workflow remains unexecuted; the new SQL and report fields require CI execution and artifact review.

No production/runtime/SQL/migration/Compose/credential/secret/database/role change. Only disposable catalog capture and report fields changed. PostgreSQL database-per-tenant remains invariant. AUD-004 remains blocked.


### Section 54 — First PostgreSQL catalog workflow failure diagnosed and harness import collision corrected

The first manually dispatched reconciliation workflow on PR #71 head `c1b6a59f93f1f73cd91c099b7f3c8f01a6033c02` completed the workload-isolation proof, role-bootstrap proof, and reconciliation regression tests successfully. The dedicated Alembic/catalog job failed before the first control-plane migration executed. Its traceback showed `backend/control_plane/alembic.ini` prepending `backend/core` to `sys.path`; that directory contains `queue.py`, which shadowed Python's standard-library `queue` during `logging.handlers` / Redis imports and caused `ImportError: cannot import name 'Empty' from partially initialized module 'queue'`. No migration or catalog assertion ran, and no catalog artifact was generated.

PR #71 now changes only the disposable harness's Alembic subprocess invocation: it preloads the standard-library `queue` module before Alembic parses its configuration and prepends `backend/core`. This avoids modifying the application's Alembic configuration or runtime import behavior. Fix commit: `0810745182423ffae5c28a2d22c8cf639dbb2a2a`.

**Validation status:** the correction is committed but has not yet been executed by CI. The next reconciliation dispatch must confirm that control-plane migration starts, then tenant A and tenant B migrations complete, and the catalog artifact is uploaded and reviewed. Do not infer PostgreSQL migration compatibility from the earlier passing jobs. AUD-004 remains blocked.

No production/runtime/SQL/migration/Compose/credential/secret/database/role change. Only the disposable test harness subprocess startup changed. PostgreSQL database-per-tenant remains invariant.



### Section 55 — Backup/restore script boundary and ownership/ACL parity gap

A source review of `deployments/backup-postgres.sh` and `deployments/restore-postgres.sh` confirms several useful operational safeguards: backup requires a protected external GPG passphrase file, enforces a mounted non-root backup destination, serializes runs with `flock`, encrypts each database dump, verifies decryptability and `pg_restore --list`, emits checksums, optionally archives attachments, and can copy encrypted artifacts to a remote destination. The backup enumerates the configured control-plane database plus databases matching the tenant database prefix. Restore requires a new `restore_...` target name, refuses an existing target, verifies a supplied checksum manifest when present, checks the encrypted dump listing, and retains a failed isolated target for diagnosis rather than routing traffic to it.

The scripts do **not** yet prove a least-privilege or ownership-preserving recovery path:

1. Backup invokes `pg_dump` and `pg_dumpall --globals-only` using the Compose database's `POSTGRES_USER` and password. This is the configured database administrator identity, not a separately demonstrated per-database backup identity with bounded read rights.
2. Per-database dumps explicitly use `--no-owner --no-acl`. The separate globals export uses `--no-role-passwords`. These choices avoid embedding ownership/ACL restoration and role password hashes in the per-database dump; the artifact therefore cannot by itself establish that original object owners, grants, default privileges, memberships, and login authentication material can be reconstructed.
3. Restore creates the target database owned by `POSTGRES_USER` and runs `pg_restore --no-owner --no-acl` as that same configured identity. It does not restore the globals artifact, normalize intended workload owners, or reapply and verify per-database ACL/default-privilege policy.
4. The restore script accepts one encrypted dump file, not a backup-set manifest. It validates the checksum file if one happens to be present in the same directory, but does not require a manifest or verify that the dump belongs to the expected control-plane/tenant database set.
5. The script verifies archive readability and successful `pg_restore` execution, but does not run post-restore catalog parity, migration revision, role-effective-privilege, application smoke, or cross-tenant isolation checks. A successful restore command is not an accepted recovery drill.
6. The backup script's optional remote copy uses `rsync`; no remote retention, immutable/WORM storage, independent restore credential, or remote restore verification is established by these scripts.

**Required next proof:** use only disposable PostgreSQL databases and synthetic data to exercise a full backup-set restore, including the globals/role plan as a separately reviewed operation. Compare pre/post database inventory, Alembic revisions, owners, explicit and effective ACLs, memberships, default ACLs, sequences, functions/triggers, extensions, RLS state/policies, and representative synthetic records. Demonstrate that ordinary tenant runtime identities cannot read backup artifacts, restore, create databases, or assume migration/owner roles. Keep cluster-global export/import and database restore as separate privileged steps with explicit approval gates.

**Boundary:** this is a source-code review, not a backup execution or restore drill. No production backup, restore, role, credential, ACL, database, or tenant topology was changed. PostgreSQL database-per-tenant remains invariant. AUD-004 remains blocked.



### Section 56 — PostgreSQL migration/catalog workflow rerun reached trigger assertions; assertion ordering corrected

The reconciliation workflow was manually dispatched against PR #71 head `0810745182423ffae5c28a2d22c8cf639dbb2a2a` (run `43441291510`). The earlier `queue` shadowing problem did not recur: the real control-plane migration and both independent tenant migration graphs completed on PostgreSQL 17. The workload-isolation proof and production role-bootstrap function proof jobs completed successfully. The reconciliation regression job subsequently completed successfully.

The catalog test then failed at the first append-only trigger assertion for `federation_transfer_logs`. PostgreSQL's `pg_get_triggerdef` rendered the valid event ordering as `BEFORE DELETE OR UPDATE`, while the test expected the equivalent `BEFORE UPDATE OR DELETE` string. The catalog showed the expected trigger was present; the failure was a brittle assertion on PostgreSQL's textual event ordering. Because pytest stopped at this assertion, later trigger checks, raw SQL mutation checks, catalog report generation, and artifact upload were not completed. The upload step ran but warned that no report file existed.

PR #71 corrects this in commit `3b3dd76580cb6e6ec0bf9b1ff6e820425e07ab30`: the assertion checks that the definition contains BEFORE, UPDATE and DELETE independent of display order, while retaining the independent PostgreSQL `tgtype` bitmask assertion for ROW + BEFORE + DELETE + UPDATE. This is a test-harness-only change.

**Validation status:** the correction has not yet been run. A new manual reconciliation dispatch on the latest PR #71 head is required. The successful migration steps are now directly observed on PostgreSQL 17; full catalog characterization and artifact review remain pending. AUD-004 remains blocked.

No production/runtime/SQL/migration/Compose/credential/secret/database/role/ACL/topology change. Only a disposable catalog test assertion changed. PostgreSQL database-per-tenant remains invariant.


### Section 57 — Control-plane audit-log immutability has no PostgreSQL migration guard

A direct review of the control-plane baseline migration `backend/control_plane/alembic/versions/95769c3ab4b3_baseline.py` confirms that `control_plane_audit_logs` is created with its primary key and ordinary lookup indexes only. The migration does not install an UPDATE/DELETE trigger, revoke mutation privileges, or establish a dedicated append-only database identity. The model `backend/control_plane/models.py` attaches SQLAlchemy `before_update` and `before_delete` listeners that raise `PermissionError`; those listeners protect ORM unit-of-work changes only and are bypassable by raw SQL, SQLAlchemy Core/bulk operations, or another database client.

This differs from the tenant `security_audit_export_register`, for which a PostgreSQL migration-installed trigger is now present and covered by the disposable tenant catalog test. No equivalent PostgreSQL guard has been found for the control-plane audit log in the baseline migration reviewed.

**Required proof/remediation:** decide whether CP audit rows are truly append-only evidence. If yes, implement only under a separately approved migration/remediation change: database-level UPDATE/DELETE protection plus a CP runtime identity with SELECT/INSERT but no UPDATE/DELETE/TRUNCATE/ownership/trigger-disable authority. Add a disposable CP fixture row and raw SQL UPDATE/DELETE/TRUNCATE attempts under the actual intended CP runtime identity; verify the expected denial and that permitted audit insertion still works. Also test the control-plane audit route's actor/target attribution and ensure no application operation needs to mutate existing audit rows. Do not treat ORM event listeners as the database security boundary.

**Boundary:** this is source inspection only. No migration, trigger, grant, role, runtime, or production change was made. PostgreSQL database-per-tenant remains invariant. AUD-004 remains blocked.


### Section 58 — PostgreSQL 63-byte trigger identifier truncation corrected in the characterization expectation

The next manual reconciliation dispatch, run `43441898408`, used PR #71 head `3b3dd76580cb6e6ec0bf9b1ff6e820425e07ab30`. All three actual Alembic migration graphs completed on PostgreSQL 17; workload-isolation, role-bootstrap and reconciliation regression jobs passed. The catalog test advanced beyond the prior event-order assertion and found that the migration `c8f2a6d1e940_reconciliation_escalation_configuration.py` declares trigger name `trg_procurement_reconciliation_notification_config_events_immutable`, which is 67 bytes. PostgreSQL identifiers are limited to 63 bytes, so the live catalog correctly reports `trg_procurement_reconciliation_notification_config_events_immut`. The trigger was present; the expected-name assertion was too long.

PR #71 corrects only the test's expected catalog name in commit `6b7d5ff39cece427d2619de02f121618be58e075` and documents the PostgreSQL identifier truncation beside the expectation. The migration itself is deliberately unchanged; any future migration rename/cleanup requires a separate reviewed migration decision because the existing catalog name and downgrade behavior must be preserved safely.

**Validation status:** this test expectation correction has not yet run. A fresh manual reconciliation dispatch on the latest PR #71 head is required. Full catalog assertions, raw SQL mutation tests, report artifact and parity review remain pending. AUD-004 remains blocked.

No production/runtime/SQL/migration/Compose/credential/secret/database/role/ACL/topology change. Only the disposable test's expected catalog identifier changed. PostgreSQL database-per-tenant remains invariant.


### Section 59 — SIEM export read/write footprint and outbound webhook boundary

A source review of `backend/domains/audit/router.py`, `backend/domains/audit/models.py`, and `backend/core/export.py` traced the tenant SIEM export surface:

1. `GET /api/audit/security-events` and `GET /api/audit/stream` are both guarded by `RequirePermission("privacy:read")`. Their collector performs SELECT/count operations against four tenant evidence sources: `PrivacyDecisionAudit`, `BreakGlassGrant`, `PrivacyDataBreachIncident`, and `PrivacyRetentionRunLedger`.
2. The NDJSON stream materializes the selected events, computes the exact payload byte count and SHA-256 digest, and INSERTs a `SecurityAuditExportRegister` row before returning the response. If registration fails, it returns 503 and does not deliver the export. The same request/session therefore needs read access to the four evidence sources plus INSERT/sequence access for the export register; it does not need UPDATE/DELETE on the register.
3. The emitted event fields are not uniformly counts-only: break-glass events include patient ID and reason; breach events include incident code/title and affected-subject count; retention events include categories, action, affected/held counts and approval reference. This endpoint is a controlled disclosure/export surface, not merely a metadata inventory. Its authorization, tenant binding, field minimization, rate/volume limits, export logging and retention need to be reviewed together.
4. `GET /api/audit/exports` and `GET /api/audit/exports/{export_id}` read only register metadata and deliberately do not return the payload or event rows. They share the `privacy:read` permission.
5. `POST /api/audit/siem/webhook-test` is guarded by `system:admin`, accepts a caller-supplied URL and optional Authorization header, and sends a fixed connectivity probe containing the HMS source, timestamp, actor email and health status. It rejects credentials over HTTP, blocks non-global/private/loopback/link-local/reserved DNS answers (including CGNAT), pins TCP to validated addresses, disables environment proxy trust and redirects, and applies a five-second timeout. It does not send the SIEM export payload in this connectivity test.
6. The webhook probe still permits outbound connections to any destination that resolves to globally routable addresses; the route does not enforce a centrally configured SIEM destination allowlist or a dedicated egress policy. The optional caller-provided Authorization header is sent to that selected HTTPS destination. The endpoint therefore requires an explicit operational policy for destination approval, credential handling, audit, and network egress; application SSRF checks alone are not an egress-control boundary.
7. The general-purpose `backend/core/export.py` helpers provide CSV and NDJSON response generation, including spreadsheet formula neutralization for CSV cells, but they do not themselves authorize access, bind a query to a tenant, or create an export register entry. Those controls must be verified at each calling route and in the tenant database context.

**Least-privilege implications:** tenant runtime access for the SIEM route must include SELECT on the four source ledgers, and INSERT plus required sequence usage on `security_audit_export_register`. It must not inherit UPDATE/DELETE/TRUNCATE/ownership rights to that append-only register. The read-only export-list/detail operations do not justify broader source-table access. If the webhook test remains in the same API process, outbound network permissions are process-wide rather than database grants and must be handled separately from PostgreSQL ACL design. A future worker split could isolate outbound delivery, but no such architecture change is proposed here.

**Required proof:** exercise these endpoints against disposable tenant databases using the intended non-superuser runtime identity. Prove the four SELECT paths and register INSERT succeed; UPDATE/DELETE/TRUNCATE of the register fail; cross-tenant and CP databases remain inaccessible; and the route cannot read unrelated clinical tables merely because it has `privacy:read`. Separately test destination policy, credential redaction, denied private/reserved destinations, DNS pinning, redirects, timeout and egress restrictions under the actual deployed network policy. Verify that export response fields and limits meet the approved disclosure policy.

**Boundary:** source-code review only. No runtime code, export behavior, permissions, network policy, database role, migration, or production setting changed. PostgreSQL database-per-tenant remains invariant. AUD-004 remains blocked.


### Section 60 — Control-plane audit attribution, asynchronous writes and failure semantics

A focused source trace of `backend/control_plane/app.py`, `backend/control_plane/models.py`, and the provisioning, fleet-operations and visual-migration routers confirms that CP audit insertion is distributed across request handlers, exception handling, and background work:

1. The CP model stores `action`, `target_slug`, `actor`, free-form `details`, and a database-generated timestamp. The model's before-update/before-delete ORM listeners reject ordinary ORM mutations, but they are not a PostgreSQL immutability boundary (Section 57).
2. The CP HTTP middleware authenticates a named operator bearer session, stores operator identity/role in request state, and sets the `control_plane_actor` context variable for the request. A model `before_insert` listener copies that context value into `actor` when present. This is a useful request-path default, but it is application context, not database-authenticated attribution.
3. Several synchronous fleet/provisioning handlers add audit rows to the same SQLAlchemy session as the associated control-plane state change and commit them together. This gives those specific operations a shared transaction boundary for state and audit insertion; it does not guarantee every privileged operation follows that pattern.
4. The provisioning error paths record `PROVISION_FAILED` and `PROVISION_EMAIL_FAILED` in separate commits. A provisioning failure audit can itself fail and mask the original error path; the route does not establish an independent durable audit channel. Successful provisioning writes the tenant registry, federated-node record and `PROVISION_HOSPITAL` audit row in one CP transaction.
5. The global exception handler attempts to insert `API_ERROR` using a new CP session and an explicit actor value `SYSTEM`. If this secondary write fails, it logs the failure and still returns the sanitized HTTP 500. Consequently, the response's claim that the event has been logged is stronger than the implementation can guarantee under CP database failure.
6. The visual migration endpoint starts a FastAPI `BackgroundTasks` operation. The background function runs outside the authenticated request's normal middleware execution context and writes completion/failure audit rows using a new `ControlSessionLocal` session. Its helper explicitly sets actor to `VENDOR_CONSOLE`, so the initiating named operator is not retained in the completion/failure event. The initial `ETL_VISUAL_MIGRATION_STARTED` event is inserted synchronously and can receive the request context actor, producing different attribution for one logical job.
7. The visual migration completion audit includes serialized counts and `sample_errors` taken from row-level exceptions. Those exception strings are truncated in the preview but not consistently normalized in the background audit details. Error text can contain values supplied by imported records or database constraint context; storing it verbatim in a CP-wide audit log risks leaking tenant data and increases the exposure of the CP log reader. The failure event records only exception type and counts, but the completion event includes sample error strings.
8. The migration background worker logs row-level exception details to application logs and catches per-row failures, then commits successful rows. It writes one completion event after the loop, or a failure event for outer exceptions. This is not a durable job ledger: process termination can occur after tenant rows commit but before the CP completion event, and the API's initial response only says processing. No durable operation ID, heartbeat, resumable checkpoint or reconciled final state was established in this source pass.
9. The CP audit listing endpoint reads log rows with bounded pagination and filters, but its access check uses the vendor setup key dependency and master key rather than a per-operation read-only audit permission model. This is a broad administrative disclosure surface over cross-tenant operations and should be separated from ordinary CP viewer/operator permissions.

**Least-privilege and integrity implications:** CP runtime needs INSERT on `control_plane_audit_logs` for audit-producing paths and SELECT for the audit listing path; it should not receive UPDATE/DELETE/TRUNCATE/ownership/trigger-disable rights if the ledger is intended to be immutable. These rights do not justify broad access to tenant clinical tables. Audit actor should be passed as an explicit immutable job initiator identity for background work, rather than defaulting to a generic vendor label. Free-form details should use allowlisted structured metadata and redact row values, credentials, tokens, patient identifiers and raw exception text.

**Required proof/remediation:** define the CP audit event contract and actor provenance; test that each synchronous state change and audit row commit or roll back together; inject CP audit database failures and confirm the API does not falsely claim durable logging; verify asynchronous job start/completion/failure events retain the initiating operator and a stable operation ID; ensure row-level errors are redacted before audit persistence; and exercise raw SQL UPDATE/DELETE/TRUNCATE denial under the intended CP runtime identity while permitting INSERT and SELECT. Add a crash-window/retry test for tenant bulk migration versus CP completion status. Any changes to the audit schema, permissions, background job architecture or route authorization require a separate reviewed implementation decision.

**Boundary:** source-code review only. No runtime, audit schema, role, grant, migration, job, route authorization or production behavior changed. PostgreSQL database-per-tenant remains invariant. AUD-004 remains blocked.



### Section 61 — Fleet break-glass operations, source-tenant connection termination and cross-database audit gaps

A source review of `backend/control_plane/api/routers/fleet_ops.py` traced the privileged tenant key rotation, emergency administrator reset, backup/restore, sandbox clone and schema-sync paths. These operations execute from the CP API process but reach tenant databases and, in several cases, cluster-level PostgreSQL capabilities.

1. The shared `_terminate_db_connections(control_db, db_name)` helper issues `pg_terminate_backend(pid)` for every other session in `pg_stat_activity` whose `datname` matches the supplied name, then commits the CP session. The helper does not filter by application name, owner, session purpose or an allowlisted maintenance operation. Its effective scope is therefore every other connection to that database, not just a maintenance worker's sessions.
2. The restore route calls that helper synchronously before it queues its FastAPI background restore task. This disconnects all other sessions to the target tenant database before the pre-restore safety snapshot and restore actually run. The route then records a queued event and returns; completion/failure is written later through a separate CP session.
3. The sandbox clone route also calls the same helper with `src_tenant.db_name` before issuing `CREATE DATABASE ... WITH TEMPLATE`. That is the production source tenant database, not the new sandbox database. A sandbox clone can therefore terminate active application, staff and worker sessions against the source hospital before creating the clone. The clone path performs a cluster-level template database creation, then scrubs the copied database, and only afterward inserts the sandbox tenant registry and `CLONE_SANDBOX` audit row. A failure between database creation/scrubbing and the final CP commit can leave an unregistered database; the source-tenant connections have already been terminated.
4. The clone operation creates the database through an autocommit connection bound to `settings.POSTGRES_DB`, using a `CREATE DATABASE ... WITH TEMPLATE` statement. The CP request process therefore needs cluster-level database creation authority and access to the source tenant as a template. The source session termination is an additional cluster capability. These are not ordinary CP metadata permissions and must not be granted to the general CP API runtime identity.
5. Manual backup and restore use FastAPI `BackgroundTasks`, not a durable job queue. The request records `TRIGGER_MANUAL_BACKUP` or `RESTORE_SNAPSHOT` in the CP transaction after scheduling the callback. The callback writes completion/failure through `_record_backup_task_audit`, which catches audit persistence exceptions and only logs them. There is no durable operation ID, worker lease, heartbeat, restart recovery or authoritative job state in this route. A process restart can strand an operation after the queued event; an audit database failure can leave the operation outcome unrecorded while the callback's failure is reduced to service logs.
6. The restore callback takes a mandatory safety snapshot and aborts if snapshot creation fails, which is a useful fail-closed guard. However, the failure audit includes `snap_exc` interpolated directly into CP audit details. The restore task's outer failure event records the exception type, but the safety-snapshot failure path can persist raw exception text. Error strings can contain filesystem paths, database names, command context or other operational details and should be normalized before entering the CP-wide ledger.
7. The emergency admin reset updates the selected tenant user's password/status/failed-login counter, deletes that user's active `AuthSession` and `PasswordResetToken` rows, and commits the tenant transaction. Only afterward does it insert and commit `BREAK_GLASS_ADMIN_RESET` in the CP database. These are two independent database transactions: if the CP audit write fails, the credential reset and session invalidation remain committed without the corresponding CP audit event. The endpoint returns the generated one-time password in its response, so request/response logging and support-console handling must explicitly redact it.
8. Tenant key rotation updates encrypted JWT/backup secrets and the CP federation-node key hash in the CP session. For cloud tenants, it separately attempts to synchronize the new federation key hash/prefix into the tenant's `FederatedClient` row. That tenant-side synchronization exception is caught and logged, after which the CP audit row is committed and the newly generated key material is returned. The endpoint can therefore report a successful rotation while CP and tenant federation credentials are out of sync; the audit event records which rotation flags were requested, not whether tenant synchronization succeeded. A missing tenant-side `FederatedClient` row is also not treated as a synchronization failure.
9. The single-tenant and fleet schema-sync routes call the tenant migration/seed helper directly from the CP API request path. The fleet route processes active cloud tenants sequentially and writes one CP audit event only after the loop completes. A mid-fleet exception can leave earlier tenant databases migrated and seeded, later tenants untouched, and no final fleet audit event. These routes authenticate through the CP secret and vendor master key in the shown handlers but do not declare the named operator-role dependency used by the backup, restore, clone, key-rotation and admin-reset routes. This is a distinct authorization and operational separation concern; the effective security of the vendor key must be reviewed as a privileged machine credential, not assumed equivalent to per-operator approval.
10. The source confirms that privileged operations are mixed into one CP API module and process: tenant DB access, cluster connection termination, database cloning, migration execution, secrets handling and CP audit persistence. This is incompatible with treating the CP HTTP runtime as a narrow metadata-only principal. The actual deployed PostgreSQL identity and grants have not been observed in this source pass, so the exact effective authority remains unproven.

**Least-privilege and integrity implications:** the CP web/API identity should not possess `pg_terminate_backend`, `CREATEDB`, tenant database owner, migration DDL, or broad tenant database credentials merely because these routes currently call the operations. Move restore, clone, migration, backup and credential-reset work behind separately authenticated, target-scoped executors with explicit operator identity, approval/maintenance-window checks, tenant target allowlists, durable operation IDs and idempotent state transitions. Source-tenant clone should use a non-disruptive snapshot/backup or a controlled maintenance protocol; it must not terminate ordinary source sessions as an incidental prerequisite. Cross-database actions need an explicit reconciliation design because CP and tenant commits cannot be made atomic by a normal SQLAlchemy session. Secret-returning responses and all logs/audit details require redaction.

**Required proof/remediation:** in disposable PostgreSQL, use independent CP, tenant-runtime and privileged-executor logins to prove that CP runtime cannot terminate sessions, create databases, use another tenant as a template, run tenant DDL or mutate tenant credentials. Add a clone test proving source sessions remain connected and that partial clone/scrub failure is cleaned up or durably tracked. Add failure injection between tenant admin-reset commit and CP audit commit; between CP key rotation and tenant federation-key synchronization; during each tenant of fleet migration; and during backup/restore callback execution and audit persistence. Verify durable job status after worker/process termination, actor continuity, safe retry, redacted errors and one-time secret response handling. Validate named-operator authorization for every privileged route, including the two schema-sync handlers, and confirm that the vendor master key is not a substitute for individual approval and attributable actor identity.

**Boundary:** source-code review only. No runtime, database, credential, role, grant, migration, backup/restore, connection, clone, or production operation was executed or changed. PostgreSQL database-per-tenant remains invariant. AUD-004 remains blocked.


### Section 62 — Fleet route authorization, shared vendor-key elevation and audit coverage

A source review of `backend/control_plane/services/auth.py`, `backend/control_plane/app.py`, `backend/core/config.py` and the complete route declarations in `backend/control_plane/api/routers/fleet_ops.py` compared named-operator RBAC with the route-level dependencies.

1. Named control-plane sessions are issued only after the MFA setup/confirmation or MFA login flow. The access token is tied to a persisted `ControlPlaneOperatorSession`; middleware validates the token/session and places the operator email, ID and role on request state and actor/role context variables. Invalid bearer tokens are rejected by `verify_control_plane_secret` rather than silently falling back to static credentials. This is a meaningful control, but it is not applied as a route-specific role policy everywhere.
2. `require_operator_role(...)` enforces named roles when a route declares it. However, its legacy-static-key branch returns `superadmin` when no named operator identity exists. `_verify_vendor_key()` also skips the vendor key when the context role is `superadmin`; otherwise it requires the shared `MASTER_ONBOARDING_KEY`. Thus, when `CONTROL_PLANE_LEGACY_MASTER_KEY_ENABLED` is enabled, the legacy control-plane master secret can be treated as superadmin by role-gated routes, and routes without role dependencies still rely on the shared vendor key as their additional gate. The setting defaults to `False` in `backend/core/config.py`; deployed environment values were not inspected.
3. Several routes that mutate tenant-wide or commercial control-plane state declare only `verify_control_plane_secret` plus `_verify_vendor_key`, without a named role dependency: tenant circuit-breaker status, deployment-mode switch, entitlement/quota/maintenance updates, single-tenant schema sync and fleet schema sync. Under a valid named viewer/support/billing session, the shared vendor key is therefore the decisive authorization gate for these routes rather than an explicit role allowlist. Under the optional legacy static-key mode, the legacy key path can also inherit superadmin treatment in route dependencies that do use `require_operator_role`.
4. Sensitive read routes also omit named role dependencies: fleet overview, tenant registry listing, per-tenant telemetry, backup snapshot listing, schema status, full governance details, federation topology, fleet analytics and CP audit-log listing. These responses can expose cross-tenant patient/billing aggregates, tenant DB names, admin emails, provisioning configuration, backup filenames, migration versions, federation key prefixes, commercial terms and CP audit details. The handlers require CP authentication and vendor-key validation, but do not distinguish viewer/support/ops/billing scopes in their route declarations.
5. Some high-impact endpoints do explicitly require roles: key rotation is ops/superadmin; emergency tenant admin reset is support/ops/superadmin; manual backup, restore and sandbox clone are ops/superadmin; MPI cross-tenant lookup and CP audit log listing have different treatment (MPI lookup requires support/superadmin, audit listing does not). This inconsistency makes the actual authorization boundary difficult to reason about from a centralized policy.
6. Audit coverage is uneven even among routes that mutate CP state. Tenant status toggle, key rotation, emergency admin reset, entitlement update and schema sync create audit rows. The deployment-mode switch commits the tenant registry change without adding a CP audit event. The fleet schema-sync audit is emitted only after the entire sequential loop, so partial completion is not represented as a per-tenant operation ledger. The status and entitlement routes include some free-form details, but there is no common structured before/after diff, request/correlation ID or approval reference in these route-level records.
7. The `ControlPlaneAuditLog` insert listener attributes actor only when the request middleware has a named operator identity. A shared vendor-key-only request has no named operator actor, so its audit record may retain the model default/empty actor rather than identify the human initiator. The legacy-static-key mode therefore weakens attribution even when the route does write an audit event. Section 60's database-level limitation still applies: context-derived actor attribution is not DB-authenticated.
8. `CONTROL_PLANE_LEGACY_MASTER_KEY_ENABLED=False` is the source default, not proof of deployed configuration. No secret, environment, runtime, or production setting was read. This section does not assert that legacy mode is currently enabled.

**Required remediation:** define a route-by-route authorization matrix and enforce it centrally, with explicit named roles for every mutation and scoped roles for sensitive read surfaces. Remove the legacy static-key-to-superadmin behavior from normal API request paths; if emergency break-glass access is retained, make it time-bound, separately approved, strongly attributable and auditable, without silently converting a shared credential into a named superadmin. Require named operator identity for state-changing routes and make the shared vendor key a machine-to-machine secret only where strictly necessary, not a substitute for human authorization. Add structured audit events for deployment-mode changes and per-tenant migration outcomes, including actor, target DB/tenant, before/after values, correlation/operation ID, approval reference and outcome. Sensitive response fields (admin contacts, backup metadata, DB names, provisioning configuration and key prefixes) should be independently permissioned and minimized.

**Required proof:** route-level tests for every fleet endpoint across viewer, support, ops, billing and superadmin named sessions; tests for missing, invalid and valid vendor keys; tests with legacy mode explicitly false and true in isolated settings; assert that legacy static credentials cannot silently gain superadmin privileges; verify audit actor attribution for every accepted authentication mode; assert deployment-mode changes and partial fleet sync outcomes are recorded; and test that lower-privilege roles cannot read cross-tenant financial/clinical aggregates or CP-wide audit details.

**Boundary:** source review only. No authentication configuration, secret, operator account, role, route, runtime or production state was changed or inspected. PostgreSQL database-per-tenant remains invariant. AUD-004 remains blocked.


## 63. Sandbox clone sanitization coverage, retained identities and credential reset boundary

**Sources reviewed on `main`:**
- `backend/control_plane/services/sandbox_sanitizer.py`
- `backend/control_plane/api/routers/fleet_ops.py` (`_scrub_sandbox_tenant_data`, `clone_hospital_to_sandbox_environment`)
- `backend/domains/identity/models.py` (`User`, `DoctorProfile`)
- `backend/domains/federation/models.py` (`FederatedClient`)

This is static source inspection only. No database was cloned, scrubbed, queried or modified. No runtime tests were executed.

### 63.1 Classification is table-name fail-closed, not a complete data-discovery boundary

- The sanitizer calls SQLAlchemy Inspector `get_table_names()` and rejects names outside the three hard-coded sets: master/config, purged logs and scrubbed data.
- This detects a newly added ordinary table in the inspected schema if its name is absent from the sets. It does not establish complete inventory of views, materialized views, foreign tables, routines, large objects, external object storage, file attachments, database-level secrets or data in other schemas.
- The classification sets are table-level only. They do not define a reviewed per-column inventory of direct identifiers, indirect identifiers, free text, credentials, external references and regulated data.
- Several entries in `SCRUBBED_DATA_TABLES` only increment `stats["scrubbed_tables"]` without issuing a scrub statement in the inspected function (including `payroll_periods`, `user_roles` and `who_surgical_safety_checklists`). A counter increment is not evidence that every row or sensitive field was transformed.
- A complete table-name allowlist therefore does not prove that all cloned information has been anonymized or that every non-table data surface has been considered.

### 63.2 User identity and doctor profile fields remain identifiable

The `users` loop changes password hash, MFA fields, failed-login/lock state, phone number and email. It does not change:
- `login_id`;
- `full_name`;
- `gender`;
- `status` (including ACTIVE);
- `is_superuser`;
- role assignments in `user_roles` (the sanitizer only increments its scrubbed counter for that table).

The inspected `User` model confirms `login_id` and `full_name` are persisted identity fields. The result is that real staff names, usernames, gender, account activation state and privilege assignments can survive the clone even though email and phone are replaced.

For `doctor_profiles`, the sanitizer only replaces `medical_registration_number`. The model also stores `clinical_id`, qualification, specialization, medical council name, registration-validity date, consultation fee and the user relationship. These values are not transformed in the shown scrub statement; in combination with the retained user name/login ID they can identify a real clinician and preserve operationally sensitive profile data.

Patient demographic scrubbing is more comprehensive, but setting DOB to January 1 of the original year retains birth year, while gender and patient-linked clinical/transactional relationships remain. This is pseudonymization, not proof of irreversible anonymization; rare combinations and longitudinal linkage can remain identifying.

### 63.3 Federation partner identity and access state survive

For `federated_clients`, the sanitizer changes only `api_key_hash` to a deterministic `SANDBOX_SCRUBBED_KEY_<id>` string. It leaves `branch_code`, partner `name`, `api_key_prefix`, `is_active` and `last_used_at` unchanged. The model confirms these are stored fields.

Consequences:
- partner organization identity and operational metadata remain in the clone;
- partner records remain marked active;
- the replacement hash is predictable and is not generated as a fresh credential hash using the normal federation key lifecycle;
- no post-scrub proof is shown that the sandbox cannot accept a copied production credential, that every integration secret is invalidated, or that outbound federation/network activity is disabled.

The sanitizer also leaves master/config data by design. A separate secret/config inventory is needed to prove that cloned integration endpoints, webhook credentials, signing material, tokens, certificates, file URLs and external service configuration are either removed or safely sandboxed. The inspected classification alone does not establish this.

### 63.4 Temporary password is shared across all cloned users

The clone route generates one random `sandbox_admin_password` and passes it to the sanitizer. The sanitizer hashes that same value once and assigns the resulting hash to every row in `users`, regardless of role or status. The response returns this single password as `temporary_admin_password`.

This means the returned administrator credential is also the password for every retained staff account. It does not establish a single administrator-only bootstrap identity, least-privilege access, per-user reset, forced password change, or account disablement for non-admin users. Combined with retained `login_id` values and role mappings, this can create a broad, shared-access sandbox credential.

The generated password is random per clone, which is better than the sanitizer's hard-coded fallback `DUMMY_SANDBOX_PASSWORD`; however, the fallback remains in the service and should not be accepted for a production-derived clone. The route's current call supplies a generated password, but the sanitizer itself permits callers to omit it.

### 63.5 Clone failure can leave an unregistered, unsanitized database

The caller's order is:
1. terminate source-tenant connections;
2. create the sandbox database from the source database template;
3. generate the sandbox password;
4. run the sanitizer;
5. generate sandbox secrets and add the sandbox registry/audit rows;
6. commit the control-plane transaction.

There is no visible exception handler around clone creation/sanitization that quarantines or removes the newly created database if the sanitizer raises. The sanitizer intentionally raises before destructive work when it encounters an unclassified table. A scrub statement, model import, trigger recreation or commit can also fail. In these cases the route exits before registry insertion, leaving a database created from the production source but not registered as a sandbox. The failure path does not establish that the database is inaccessible, quarantined, sanitized or cleaned up.

The sanitizer uses one SQLAlchemy session and commits after the scrub operations; PostgreSQL transactional DDL/DML can keep its own changes atomic when the transaction rolls back. That does not make the preceding database creation atomic with the sanitizer or the separate control-plane registry commit.

### 63.6 Append-only guards are temporarily removed during purge

The sanitizer drops and recreates selected PostgreSQL append-only triggers so it can delete cloned audit/ledger rows. This is performed by the same scrub session before its final commit, and the shown code recreates the listed guards before continuing. This is a privileged schema operation, not an ordinary tenant runtime capability.

Required proof is broader than successful function return:
- compare trigger/function definitions, enabled state, owner and security mode before and after scrub;
- prove every expected guard is restored on every supported database dialect;
- inject failures after each trigger drop, delete and recreate step and verify rollback leaves the clone in a safe, non-exposed state;
- verify no additional trigger or rule was silently omitted from the hard-coded drop/recreate lists.

### 63.7 Required remediation and acceptance evidence

1. Replace the broad zero-leakage assertion with a versioned, reviewed per-table/per-column sanitization manifest generated from the migrated PostgreSQL catalog. Include every schema, view/materialized view, foreign table, routine, sequence, large object, attachment/object-store reference and external integration configuration in scope.
2. Classify every field as retain, generalize, pseudonymize, purge or regenerate. Include direct and quasi-identifiers, free text, staff/clinician identities, role memberships, audit/provenance, integration configuration and clinical/financial metadata.
3. Give sandbox users synthetic login IDs and names; remove or replace clinician identifiers/profile data; review whether roles should be reduced to a dedicated sandbox role set. Disable non-bootstrap accounts by default.
4. Create one dedicated sandbox administrator identity with a one-time credential; do not set the same password on every retained account. Force rotation and record controlled delivery/expiry. Remove or fail closed on the hard-coded fallback password.
5. Regenerate or disable all federation clients and integration identities; default federation, outbound webhooks and external integrations to disabled. Verify no production credential or live endpoint remains usable.
6. Make clone lifecycle durable and fail closed: reserve a clone operation ID, create into a quarantined/non-routable state, scrub, run independent post-scrub scans, validate ownership/ACLs/secrets/feature flags, then atomically publish registry state. On any failure, retain a durable failed/quarantined record and prove the database cannot be reached by tenant users; cleanup must be a separately authorized, audited action.
7. Build synthetic canary fixtures with unique marker values in every sensitive field and assert none survive in the clone. Include staff, clinicians, patients, free-text notes, insurance, billing, payroll, procurement, federation, integrations, attachments, logs, and unknown schema objects.
8. Test that the returned temporary credential authenticates only the dedicated bootstrap account, not other staff accounts; prove retained production passwords, MFA seeds, sessions, reset tokens, federation keys and integration secrets are unusable.
9. Run independent post-scrub scans over all cataloged data surfaces and verify the report itself contains no raw patient/staff values or secrets. Obtain privacy/security and database-owner sign-off before enabling sandbox clone in a production-connected environment.

**Assessment:** the source contains a useful fail-closed table-name check, broad field scrubbing and a per-clone random password, but it does not support a zero-leakage guarantee. Retained staff/clinician identities, account roles/status, active federation-client metadata, shared user password reset and the unsanitized-clone failure window are release-blocking concerns for production-derived sandbox cloning.

**Boundary:** source review only. No runtime, migration, database, trigger, credential, network, feature-flag, clone or production state changed. PostgreSQL database-per-tenant remains the project architecture. AUD-004 remains blocked.


## 64. Tenant provisioning bootstrap-secret delivery, split-commit recovery and webhook audit gaps

**Sources reviewed on main:**
- backend/control_plane/api/routers/provisioning.py
- backend/control_plane/api/routers/saas_billing.py
- backend/control_plane/models.py (TenantRegistry, FederatedNode, ControlPlaneAuditLog)
- backend/control_plane/services/auth.py (operator identity and vendor-key authorization)

This is static source inspection only. No tenant was provisioned, no webhook was submitted, and no credentials, databases or production state were accessed or changed.

### 64.1 Provisioning returns all initial credentials in one API response

The provisioning handler generates four high-value secrets:
- initial tenant administrator password;
- tenant JWT signing secret;
- tenant backup-encryption key;
- raw federation API key.

The handler persists the tenant JWT and backup key in encrypted form in the control-plane registry, and stores federation key hashes in the tenant and control-plane federation records. It then returns the raw values together in the successful JSON response (admin_password, jwt_secret_key, backup_encryption_key, federation_api_key).

The welcome email intentionally sends only hospital/branch details, URL and administrator email, and explicitly says initial credentials/recovery keys are not sent by email. This is a positive separation, but it does not mitigate the API response surface: the full credential bundle is available to the caller and may be retained by browser history/devtools, API clients, reverse-proxy/APM response capture, support exports or operator workstations. The source does not show response-field redaction or a one-time credential retrieval/acknowledgement/expiry lifecycle.

The provisioning endpoint accepts a shared master setup key and verifies the control-plane secret. It does not declare a named MFA-authenticated operator role dependency in the route. This is consistent with the shared-key authorization concern in Section 62: the operation is not bound in the route to a specific named operator, role, approval reference or attributable human session.

**Required boundary:** return a non-secret provisioning receipt from the ordinary API response. Deliver each credential through a separate, time-limited, single-use bootstrap channel with audience binding, retrieval audit, acknowledgement and expiry. Keep JWT/backup/federation material out of browser-facing responses and ordinary logs. Provisioning must require a named operator with a specific role and, for credential release, an independently approved break-glass/secret-release action. If machine-to-machine provisioning is required, use a distinct narrowly scoped service identity and record both service principal and initiating human approval.

### 64.2 Tenant database creation and initialization precede control-plane registration

The route's sequence is:
1. check the current control-plane registry for duplicate slug/branch;
2. create the tenant database and run tenant Alembic migrations;
3. open a tenant session, seed the administrator/reference data, create the active tenant-local federation client, apply federation policy and blueprint, then commit the tenant DB;
4. construct the tenant registry and control-plane federation node;
5. insert those rows plus the PROVISION_HOSPITAL audit event and commit the control-plane DB;
6. construct and return the credential-bearing response, then attempt welcome email delivery.

These are separate database transactions. A tenant database can be successfully created, migrated and seeded before the control-plane registry/federation/audit transaction commits. If that final control-plane commit fails, the tenant database and its administrator/federation state can remain without a committed registry record or durable provisioning operation state. Similarly, failures during tenant initialization occur after database creation/migration; the shown failure handler records a generic CP failure event but does not demonstrate quarantine, compensation or cleanup of the partially created database.

The preflight duplicate check is not a durable operation reservation. No operation ID, uniqueness reservation/lease, idempotency key, resumable phase ledger or reconciliation worker is visible in this route. Concurrent or retried requests therefore need explicit proof that they cannot attach credentials to an unintended existing database, seed twice, or leave an orphan database.

### 64.3 Provisioning error and email-delivery state are not a complete lifecycle ledger

The failure branches write a PROVISION_FAILED audit row after tenant database/migration or initialization failures, but they do not include a stable provisioning operation ID or phase checkpoint. The final successful registry/federation/audit write is transactionally coupled within the CP DB, but not with the already committed tenant DB.

Welcome-email delivery happens after the successful CP commit. If delivery fails, the route commits a separate PROVISION_EMAIL_FAILED audit event and still returns the full credential bundle plus email_dispatched=false and email_error. This makes the HTTP response the practical credential delivery path even when the configured email channel fails. The source does not show a controlled re-delivery workflow with recipient verification, single-use credential release, expiry or delivery acknowledgement.

The mailer exception string is also returned in email_error and stored as audit details. The mailer implementation and exception redaction policy were not part of this bounded review; do not assume that transport/provider details are safe for API or audit disclosure without checking them.

### 64.4 Stripe subscription webhook changes tenant availability without an event ledger

The Stripe webhook verifies the signature using the configured webhook secret and updates the matching tenant registry row:
- invoice.payment_succeeded sets is_active=True and updates license_valid_till from the first invoice line's period end;
- invoice.payment_failed and customer.subscription.deleted set is_active=False and a maintenance notice.

The inspected handler does not persist Stripe event ID, event type, customer/subscription/invoice reference, prior/new state, processing outcome or a control-plane audit event. It does not show an idempotency ledger or ordering guard. Stripe retries can therefore repeat state changes without a recorded deduplication decision, and out-of-order success/failure events need explicit handling so an older event cannot overwrite a newer subscription state. The code also assumes the first invoice line contains the relevant period end; multi-line invoice semantics are not characterized here.

A verified webhook signature authenticates the Stripe message; it does not by itself establish durable replay handling, ordering, tenant-state transition policy or a forensic event record.

### 64.5 Required remediation and acceptance evidence

1. Remove all raw credentials from the provisioning response. Return a non-secret operation receipt and use separately authorized, short-lived, single-use secret release with recipient/audience binding, expiry, acknowledgement and redacted observability.
2. Require named MFA-authenticated operator identity and explicit provisioning role. Record actor ID, service principal (if any), approval/reference, target tenant, request/correlation ID and before/after state. Do not treat a shared vendor key as human authorization.
3. Introduce a durable provisioning operation ledger with idempotency key and explicit phases: reserved, database-created, migrated, initialized, CP-registered, credential-issued, delivery-confirmed, failed/quarantined. Reconcile the tenant DB and CP record across crash windows.
4. Create the database in a quarantined/non-routable state. On any failure before final verification, prove no tenant login, federation, external routing or normal runtime access is possible. Cleanup or retry must be idempotent, scoped and audited.
5. Add failure-injection tests after database creation, each migration phase, tenant seed commit, blueprint commit, CP registry/federation/audit commit, credential release and email delivery. Include concurrent duplicate requests and process restart/retry tests using independent PostgreSQL sessions.
6. Add Stripe event inbox/deduplication keyed by Stripe event ID, persist signature-verified event metadata and processing outcome, and apply monotonic subscription-state transitions using authoritative subscription/invoice timestamps or current Stripe object retrieval. Test duplicate, delayed and out-of-order success/failure/deletion events.
7. Write append-only CP audit events for provisioning phase transitions and Stripe subscription state changes, with stable operation/event IDs and attributable actor/source. Keep webhook payloads and secrets out of audit details; retain only a minimal redacted evidence set.
8. Verify that secret release is never included in API, proxy, application, mailer, audit or support logs, and that revoked/expired bootstrap credentials cannot be replayed.

**Assessment:** tenant provisioning currently has a split-database lifecycle without a durable cross-database operation ledger, and returns the complete bootstrap credential bundle from the endpoint. The Stripe webhook performs subscription-driven access changes without a visible event-id deduplication or audit ledger. These are release-blocking lifecycle and credential-governance gaps for production onboarding and automated tenant suspension/reactivation.

**Boundary:** source review only. No runtime, route, auth, credential, migration, database, webhook, network or production state changed. PostgreSQL database-per-tenant remains the project architecture. AUD-004 remains blocked.


## 65. Visual ETL model discovery exposes tenant identity and patient-sharing security fields

**Sources reviewed on main:**
- backend/control_plane/api/routers/migration.py
- backend/control_plane/services/migration_catalog.py
- backend/domains/identity/models.py (User, UserRole)
- backend/domains/patients/models.py (Patient)
- backend/control_plane/services/auth.py (control-plane secret and vendor-key checks)

Static source review only. No CSV was uploaded, no tenant endpoint was called, and no tenant data or account was changed.

### 65.1 The migration studio discovers nearly every tenant ORM model as an import target

get_migration_models() imports every domain models.py file and exposes every mapper registered in the shared tenant Base. The resulting ENTITY_MODEL_MAP is not a purpose-built, low-risk import allowlist. It includes sensitive identity and patient entities, including User and Patient.

_validate_mapping() permits every non-primary-key column except the small SYSTEM_FIELDS set and PROTECTED_FIELDS = {api_key_prefix, api_key_hash}. There is no denylist or approval boundary for account privilege, authentication, patient privacy or network-sharing fields.

The User model's is_superuser, status, mfa_enabled, mfa_secret, failed_login_attempts and other authentication/account fields are not protected by either set. UserRole's composite primary-key fields are excluded, but that does not protect the direct is_superuser flag on User.

### 65.2 CSV import can create or elevate a tenant superuser

The mapping validator permits User.is_superuser and User.status. The value coercion path accepts boolean values such as true/1/yes and enum status values. User.hashed_password is also an allowed destination; the mapping path hashes the supplied value before persistence.

The background executor supports duplicate_policy=update: it looks up a matching User by a selected single-column unique field and assigns every mapped field to the existing ORM object. Therefore, a CSV mapping can create a new active superuser or elevate an existing matching user by setting is_superuser=true and status=ACTIVE. The import route has no additional per-field approval, identity proof, tenant-admin confirmation or privileged-account creation workflow in the inspected code.

Both preview and execute endpoints are protected by the router-level control-plane secret and _verify_vendor_key(master_setup_key), but neither declares a named operator-role dependency. Section 62 already records that shared vendor-key authorization is not attributable human authorization. This finding is more specific: the reachable import target includes a direct tenant superuser privilege field.

The exact exploitability in a deployment depends on who can obtain the control-plane secret and vendor key, whether the migration routes are exposed, and tenant model/runtime behavior. The source path nevertheless permits the sensitive field; this is not a claim that an external unauthenticated caller can reach it.

### 65.3 Patient network-sharing consent can be defaulted to enabled

_apply_dynamic_mapping() unconditionally sets allow_network_sharing=True whenever the destination model exposes that field, unless a mapping already supplied it. Patient.allow_network_sharing is a non-null boolean field.

Thus an imported Patient row that omits this field is explicitly created with network sharing enabled, irrespective of source-system consent state. This is not a safe migration default for patient privacy. The same helper also defaults is_active=True for any target model exposing that field; an import can unintentionally reactivate records unless the mapping explicitly supplies a different value.

This default is independent of the model's own defaults and applies in the shared ETL helper. Preview output shows transformed data, so the default may be visible in preview, but visibility does not make the privacy default safe or consent-authorized.

### 65.4 Import execution also has incomplete operational containment

The execute route queues work through FastAPI BackgroundTasks, which runs within the API process lifecycle rather than a durable worker ledger. The start event is committed before the response, but it does not carry a stable operation ID or durable progress state. The background job commits successful rows as one tenant transaction and writes completion/failure evidence afterward using a new CP session; the helper assigns actor VENDOR_CONSOLE and logs audit persistence failures only.

Row errors are copied into completion audit details and service logs. Some error strings include rejected values (for example, a missing patient MRN or an invalid enum value). Preview also returns transformed row data and validation errors to the caller. This can expose patient/staff source values to the operator/API client and to CP-wide audit/log sinks if raw values appear in errors. A dedicated redaction policy and data-minimized import evidence are not shown.

### 65.5 Required remediation and acceptance evidence

1. Replace mapper-wide discovery with a reviewed explicit import allowlist. Exclude User, roles/permissions, authentication/session/MFA/recovery entities, federation credentials, privacy/consent controls, audit evidence and other security-sensitive models unless a separately authorized migration workflow is designed for them.
2. Add a field-level denylist/allowlist that blocks is_superuser, account status, MFA state/secrets, lockout counters, role/permission assignments, patient network-sharing/consent flags and all other security/privacy control fields from generic CSV mapping and update policies.
3. For any privileged account migration, use a separate audited workflow requiring named operator role, approval, identity validation, one-time bootstrap credential and forced MFA/password enrollment. Never let a generic ETL update set tenant superuser privileges.
4. Change patient privacy defaults to fail closed: preserve verified source consent with provenance, otherwise set allow_network_sharing=false and require explicit consent before federation/network sharing. Do not infer consent from missing CSV columns or ORM defaults.
5. Require explicit mapping for stateful flags such as is_active; reject omitted values or apply a documented safe default per entity. Add preview warnings for all security/privacy-affecting fields.
6. Redact row values from exceptions, audit details and logs. Store only row number, field name, stable error code and aggregate counts; ensure preview/export permissions and retention are narrowly scoped.
7. Move imports to a durable tenant-bound worker with operation ID, actor/approval provenance, resumable phase ledger, bounded retries, per-tenant concurrency controls and a durable terminal state. Do not report completion until tenant commit and CP evidence are reconciled.
8. Add tests proving the ETL schema does not expose User.is_superuser or any authentication/authorization field; attempted create/update of a superuser is rejected; omitted patient consent never enables sharing; and raw patient/staff values do not appear in API errors, CP audit records or logs.

**Assessment:** the generic ETL model/field discovery currently exposes a direct path to create or elevate tenant superusers through CSV import, and it defaults omitted patient network-sharing consent to enabled. These are critical authorization and privacy defects, not merely migration usability issues. Disable the visual ETL endpoints or block sensitive models/fields before any production use until independently tested remediation is approved.

**Boundary:** source review only. No runtime, endpoint, credential, database, tenant account, consent, migration or production state changed. PostgreSQL database-per-tenant remains the project architecture. AUD-004 remains blocked.


## 66. Control-plane console renders stored audit and federation values as executable HTML

**Sources reviewed on main:**
- backend/control_plane/api/routers/ui_console.py
- backend/control_plane/api/routers/fleet_ops.py
- backend/control_plane/api/routers/migration.py
- backend/control_plane/models.py (ControlPlaneAuditLog, FederatedNode)

Static source review only. No console session was opened, no API endpoint was called, and no audit or federation data was modified.

### 66.1 Stored audit fields are interpolated into innerHTML without escaping

The legacy control-plane console's loadAuditLogs() function fetches /api/fleet/audit-logs and constructs table rows with template literals. It inserts l.action, l.target_slug, l.details and l.created_at directly into HTML, then assigns the result to auditLogsContainer.innerHTML.

The API serializes those fields directly from ControlPlaneAuditLog. The source does not HTML-escape or encode them for the HTML sink, nor does the console use textContent/createTextNode for untrusted values.

These fields are not all server-generated constants. The inspected code writes free-form details from operational inputs and exceptions, including:
- MPI lookup justification supplied by the caller;
- migration row error samples, including portions of exception text;
- provisioning/email error details;
- restore/snapshot exception strings and operator-supplied filenames or tenant identifiers in operational audit messages.

An attacker able to influence a value that reaches an audit record, and who can later cause a control-plane operator to load the audit tab, may be able to execute script in that operator's authenticated console origin. The exact exploitability depends on route reachability, the ability to create a malicious persisted value and browser security headers; no live exploit was attempted. The unescaped HTML sink is directly present in source.

The same console uses innerHTML for federation topology rows and interpolates branch_code, hospital_name, subdomain_slug, api_key_prefix and federation_sharing_mode from /api/federation/topology. These are persisted control-plane values, so this is a second stored-data HTML sink, even if their expected values are usually provisioned internally.

### 66.2 The audit endpoint is not a narrow read-only operator permission

/fleet/audit-logs requires the control-plane secret and shared vendor key but does not declare require_operator_role(). This overlaps Section 62's finding that audit-list access uses broad shared-key authorization rather than a narrowly scoped named read-only role. Here the consequence is elevated: the same response feeds an HTML sink in the privileged operator console.

### 66.3 Federation topology fallback can misrepresent policy state

The topology endpoint initializes sharing_mode to FULL_MESH and also assigns FULL_MESH when it cannot read the tenant policy. A failed tenant DB connection or policy read is therefore serialized indistinguishably from a successfully observed FULL_MESH policy. The console presents that value as the hospital sovereignty mode.

This is an integrity/operational safety issue: an unavailable or unreadable tenant policy is rendered as a permissive sharing mode instead of UNKNOWN/UNAVAILABLE. The endpoint is a reporting path, not evidence that the tenant's actual federation policy changed.

### 66.4 Required remediation and acceptance evidence

1. Remove HTML string interpolation for all API-sourced values. Render table cells with DOM APIs and textContent, or use a rigorously tested context-aware escaping helper. Do not treat JSON serialization as HTML escaping.
2. Apply the same safe rendering to audit logs, federation topology, tenant registry, error messages, and every other console table/notification that inserts API values into HTML.
3. Add regression tests with payloads containing HTML tags, quotes, event-handler attributes and script-like strings in action, target, details, hospital name, branch code and key prefix. Verify they appear as inert text and cannot execute.
4. Add a restrictive Content-Security-Policy as defense in depth; the current console's extensive inline script/event-handler design means CSP must be introduced with a deliberate nonce/hash refactor rather than an unsafe-inline exception.
5. Minimize and redact audit details at write time; do not persist raw exception strings, patient/staff values or caller-controlled free text unless strictly necessary. Use structured error codes and bounded, sanitized metadata.
6. Gate audit-log reads behind a named, least-privilege audit-reader role and preserve actor attribution; keep shared vendor keys for machine-to-machine use only.
7. Change federation topology's default/error state to UNKNOWN or UNAVAILABLE, include an explicit policy-read status, and never substitute FULL_MESH when the source policy could not be read. Add tests for tenant DB outage, missing policy and invalid policy value.
8. Add security tests that exercise the actual console rendering code with malicious API fixtures, not only API response schema tests.

**Assessment:** the legacy control-plane console contains stored-data HTML injection sinks for audit and federation fields. Because the page is an authenticated privileged control-plane surface, this is a critical operator-session security defect until safe rendering and regression proof are in place. The federation policy fallback is a separate high-severity integrity issue.

**Boundary:** source review only. No runtime, browser, API, audit data, federation policy, database, credentials or production state changed. PostgreSQL database-per-tenant remains the project architecture. AUD-004 remains blocked.


## 67. Additional privileged-console HTML sinks include tenant cards, snapshot actions and provisioning output

**Sources reviewed on main:**
- backend/control_plane/api/routers/ui_console.py
- backend/control_plane/api/routers/fleet_ops.py
- backend/control_plane/api/routers/provisioning.py
- backend/control_plane/api/routers/migration.py

This section extends Section 66's stored-data HTML injection finding. Static source review only; no browser session, API call, snapshot restore, provisioning operation or exploit was performed.

### 67.1 Tenant registry fields are rendered into HTML and inline JavaScript

renderFleetCards() builds markup using innerHTML and interpolates API fields including hospital_name, subdomain_slug, branch_code, db_name and pricing_model. The tenant detail drawer also inserts tenant-provided values into a template-literal innerHTML for module checkboxes. The schema-status table interpolates tenant slug, database name, migration version and status, including subdomain_slug in an inline onclick handler.

Several values originate from provisioning/operator-supplied fields and persisted CP registry records. The endpoint response is JSON, but JSON does not make values safe for an HTML text, attribute or JavaScript-string context. A value containing markup, quotes or JavaScript delimiters can escape the intended context if it reaches these sinks.

### 67.2 Snapshot filenames enter both HTML text and an inline event-handler argument

renderDrawerSnapshots() interpolates s.filename into visible HTML and into onclick="restoreSnapshot('...')". Snapshot filenames are discovered from backup registry/filesystem state. Path.basename checks in the restore route constrain the eventual filesystem target, but they do not neutralize the value when it is first parsed as HTML/JavaScript in the browser. The correct fix is to avoid inline handlers and bind a click listener using a closure over a validated filename; render the filename with textContent.

### 67.3 Provisioning inputs and server responses are reflected into executable markup

The provisioning form sends operator-entered hospital_name and admin_email. The successful API response is interpolated into provVaultBody.innerHTML, including subdomain URL, database name, admin email, temporary administrator password, federation API key and backup-encryption key. The same workflow passes server error text into appendTermLog(), which appends msg using innerHTML; showToast() also inserts msg through innerHTML.

This creates additional HTML injection sinks for reflected provisioning values and API error strings. The credential vault's 60-second visual clearing does not make HTML insertion safe, nor does it remove values from browser developer tools, extensions, screenshots, browser memory or the already-issued network response. Section 64 separately records the underlying API response credential-delivery risk; this section records the privileged-console rendering exposure.

### 67.4 Dynamic catalogs also use HTML and JavaScript interpolation

renderDynamicCatalogs() inserts blueprint names/descriptions, bundle names/codes and module names/codes into innerHTML. Bundle codes are also interpolated into inline onclick handlers and element IDs. Catalogs may be seeded or operator-maintained; their current provenance and write authorization should be established before they are treated as immutable trusted constants.

### 67.5 Required remediation and proof

1. Treat every API response, persisted CP field, catalog value, filename and exception string as untrusted at the browser rendering boundary.
2. Replace innerHTML template rendering with DOM construction and textContent. Where static markup is unavoidable, use context-specific escaping and never interpolate into inline event handlers, attributes, CSS classes or JavaScript source.
3. Remove inline onclick/onchange handlers and bind event listeners programmatically to validated data objects; use opaque identifiers rather than embedding arbitrary strings into executable contexts.
4. Use URL path encoding for route segments and server-side allowlist validation for snapshot identifiers; retain filesystem containment checks as a separate control.
5. Render provisioning secrets as text nodes in a deliberately restricted credential view, minimize their lifetime, avoid retaining the full response in global/page state, and move toward one-time audience-bound secret retrieval as Section 64 requires.
6. Ensure server error responses and logs use stable error codes and do not echo attacker-controlled or sensitive row values.
7. Add browser-level tests covering malicious values in tenant name, slug, branch code, database name, migration version, snapshot filename, blueprint/module/bundle labels, provisioning response fields and API error details. Assert no script execution and no executable DOM attributes.
8. Inventory every innerHTML/outerHTML/insertAdjacentHTML/document.write sink in the console and any adjacent frontend assets; the findings here cover the reviewed console source, not every frontend bundle.

**Assessment:** Section 66's two demonstrated stored-data sinks are part of a broader unsafe-rendering pattern across the authenticated control-plane console. The additional inline-event-handler contexts increase the number of ways persisted or reflected data can become executable in an operator session. Treat the entire console as unsafe for production operator use until all sinks are removed and browser-level regression tests pass.

**Boundary:** source review only. No runtime, browser, endpoint, credential, tenant, backup, database, migration or production state changed. PostgreSQL database-per-tenant remains the architecture. AUD-004 remains blocked.


## 68. Control-plane authentication rate limits are accidentally fail-open; MFA setup challenge is replayable

**Sources reviewed on main:**
- backend/control_plane/services/auth.py
- backend/core/dependencies.py (RateLimiter)
- backend/control_plane/app.py
- backend/control_plane/models.py (ControlPlaneOperator, ControlPlaneOperatorSession)

Static source review only. No login attempts, MFA challenge, Redis outage, operator account or session was exercised.

### 68.1 RateLimiter scope-prefix mismatch disables fail-closed behavior for control-plane login/MFA

The control-plane login endpoint configures RateLimiter with scope `control_plane_auth_login`; MFA confirmation and login verification use `control_plane_auth_mfa`.

The shared RateLimiter determines whether an endpoint is security-sensitive using:

`self.scope.startswith(("auth_login", "auth_mfa"))`

Neither control-plane scope starts with either prefix. Consequently, when Redis is absent or a Redis operation raises an exception, the limiter takes its generic/non-sensitive path and returns without enforcing the limit. This differs from the fail-closed branch that returns HTTP 503 for sensitive authentication paths.

The control-plane routes therefore have a concrete fail-open mismatch: the decorators are present, but the shared dependency does not classify their actual scope names as sensitive. The configured 10-per-60-second login and 5-per-300-second MFA limits can be bypassed during Redis unavailability. Database-level account lockout after five failed password attempts still exists, but it is not a substitute for the intended IP/rate control and can be targeted against individual operator accounts.

### 68.2 MFA setup endpoint has no rate-limit dependency and setup challenge is not consumed

The password-login flow issues a signed `operator_mfa_setup` challenge with a five-minute expiry when MFA is not yet enabled. `/api/auth/mfa/setup` validates that token and returns the operator's decrypted TOTP secret and provisioning URI.

Unlike `/mfa/confirm` and `/mfa/verify-login`, `/mfa/setup` has no RateLimiter dependency. The setup challenge has no unique identifier or persisted one-time-use/consumption record. While the challenge remains valid and the operator has not completed MFA enrollment, the same challenge can be replayed to retrieve the same TOTP secret repeatedly. The challenge is password-gated and short-lived, so this is not unauthenticated access; it does increase the impact of challenge-token disclosure and leaves a sensitive secret-release endpoint without throttling.

The confirm endpoint does rate-limit code attempts, and successful confirmation sets `mfa_enabled`; subsequent setup calls reject the already-enabled state. These controls reduce but do not eliminate the pre-enrollment replay window.

### 68.3 Additional lifecycle observations

- MFA login challenges are signed JWTs with purpose and expiry, but no challenge ID or server-side consumption state. The TOTP counter check prevents reuse of an already accepted counter; it does not make the challenge itself one-time.
- Access tokens have server-side session rows and are checked for revocation/expiry on each authenticated request, which is a useful control.
- Logout revokes all active sessions for the operator rather than only the presented session. This is consistent with the response message but should be an explicit product/security decision because it forces all operator devices to reauthenticate.
- The operator middleware queries session and operator state for each bearer-authenticated request. No cache invalidation issue was inferred because the implementation does not cache identity state here.

### 68.4 Required remediation and proof

1. Replace prefix inference with an explicit security-sensitive flag or a canonical scope taxonomy shared by route declarations and RateLimiter. Add unit tests for the exact `control_plane_auth_login` and `control_plane_auth_mfa` values.
2. Prove that missing Redis and Redis exceptions both fail closed for control-plane login and MFA verification, and that healthy Redis enforces the configured fixed-window limits.
3. Add a dedicated limit to `/mfa/setup`, and make setup challenges one-time or otherwise bind them to a server-side enrollment transaction with a short expiry and explicit consumption.
4. Avoid returning an already-enrolled TOTP secret on repeat setup calls; require a separately authorized recovery/rotation procedure for MFA secret replacement.
5. Add tests for challenge replay, expiry, concurrent setup/confirm, operator deactivation during challenge lifetime, repeated secret retrieval, and concurrent failed login attempts.
6. Review whether per-IP controls, per-account controls and lockout reset semantics compose safely without enabling trivial account-lockout denial of service.
7. Record security-relevant enrollment, recovery, disablement and session-revocation events with named operator attribution and without logging the TOTP secret or provisioning URI.

**Assessment:** The control-plane login and MFA rate limits do not reliably fail closed under Redis outage because of a literal scope-prefix mismatch. The MFA setup endpoint additionally permits repeated retrieval of the same TOTP secret using a still-valid setup challenge and lacks its own rate limit. These are high-priority authentication-hardening gaps; source review does not establish that Redis is currently unavailable or that any account/challenge has been abused.

**Boundary:** source review only. No authentication requests, Redis changes, MFA enrollment, operator/session changes, database writes, runtime changes or production operations were performed. PostgreSQL database-per-tenant remains the architecture. AUD-004 remains blocked.

## 69. Generic control-plane webhook ingress is unauthenticated, unbounded and acknowledged before durable processing

**Source reviewed:**
- `backend/control_plane/app.py` (`/api/webhooks/ingress`, `process_webhook_payload`)

Static source review only. No webhook request was sent and no external integration, queue, database or production state was exercised.

### 69.1 Public ingress accepts arbitrary JSON without authenticating a sender

The global `POST /api/webhooks/ingress` route is registered directly on the control-plane FastAPI app. It declares no authentication dependency, signature verification, shared-secret check, sender allowlist, timestamp validation or replay/idempotency check. It reads the complete request body through `await request.json()` without an application-level byte limit, then schedules a background task.

Any network caller able to reach the route can therefore submit arbitrary JSON and receive HTTP 202. The route does not establish that the caller is an authorized payment provider, federation partner or other trusted integration. This finding is separate from Section 64's Stripe-specific webhook review: the inspected global route is a distinct generic ingress.

### 69.2 The current background handler is only a placeholder, but the ingress still permits resource/log abuse

The current `process_webhook_payload` implementation only extracts `payload.get("event")` and writes it to the application log; its comment describes future payment/federation processing, but the inspected function does not currently mutate billing, tenant, federation or other application state.

That limits the demonstrated impact today: source review does not establish an unauthenticated path to execute a business operation. However, the endpoint accepts an unbounded JSON document and schedules one in-process FastAPI BackgroundTask per accepted request. A reachable caller can impose request parsing, memory, task scheduling and log-volume costs without proving sender identity. The event value is caller-controlled and is interpolated into the log message; control characters/newlines may make log records misleading depending on the logging handler/collector. The handler's exception path also logs exception text.

HTTP 202 here means the request was accepted for an in-process background callback, not that an event was durably persisted or reliably processed. A process restart or crash can discard work; there is no durable queue, delivery ledger, retry policy, signature evidence or terminal processing status in this route.

### 69.3 Required remediation and acceptance evidence

1. Do not expose a generic webhook receiver until each integration has an explicit sender contract. Require provider-specific signature verification over the exact raw request bytes, timestamp/replay window checks, secret rotation and sender/key identity; reject unknown event sources.
2. Enforce a strict request-body size limit before JSON parsing, validate a typed event schema, cap string/array/depth sizes and reject unknown or malformed event shapes.
3. Persist authenticated events to a durable inbox/queue before returning 2xx. Use provider event IDs or an equivalent idempotency key, unique constraints, bounded retries, ordering rules where required, dead-letter handling and observable terminal states.
4. Return 2xx only after durable acceptance. Do not represent FastAPI in-process BackgroundTasks as a reliable message queue for financial, tenant-lifecycle or federation events.
5. Use structured logging with bounded, sanitized event identifiers and stable error codes; never interpolate arbitrary payload fields or raw exception details into log messages.
6. Add tests for missing/invalid signatures, expired timestamps, replayed IDs, oversized bodies, malformed/deep JSON, concurrent duplicate delivery, queue/database outage, worker crash/retry and log-control characters. Verify no business state changes occur before authentication and durable acceptance.

**Assessment:** The generic ingress is an unauthenticated and unbounded request-to-background-task endpoint. Its current callback is a logging placeholder, so no unauthorized business-state mutation was observed in source; the demonstrated present concern is resource/log abuse and false durability implied by HTTP 202. It must remain disabled or be replaced with a provider-authenticated, size-bounded, durable inbox before any real webhook processing is attached.

**Boundary:** source review only. No runtime code, webhook endpoint, queue, database, credential, tenant, billing, federation or production state changed. PostgreSQL database-per-tenant remains the architecture. AUD-004 remains blocked.

## 70. Traefik dynamic-routing provider references an unmapped tenant field

**Sources reviewed on main:**
- `backend/control_plane/api/routers/network.py`
- `backend/control_plane/models.py` (`TenantRegistry`)
- All five control-plane Alembic migration files under `backend/control_plane/alembic/versions/`

Static source and migration-history review only. The endpoint was not invoked and no proxy, tenant, database or production state was changed.

### 70.1 The route builds its query using an attribute absent from the ORM model

The hidden `GET /api/fleet/traefik-config` provider endpoint constructs a SQLAlchemy query with:

`TenantRegistry.custom_domain.is_not(None)`

It then reads `t.custom_domain` to build each Traefik host rule. The inspected `TenantRegistry` declarative model does not declare a `custom_domain` mapped column or property. The complete set of five control-plane Alembic revisions also contains no `custom_domain` declaration or addition.

As written, evaluating `TenantRegistry.custom_domain` raises an attribute-resolution error while constructing the query, before SQL is sent to PostgreSQL. Therefore the endpoint cannot return its intended dynamic tenant routing configuration in this repository state. This is a deterministic source-level availability defect, not a claim that an active Traefik deployment is currently failing.

### 70.2 The route's intended domain contract is also incomplete

The provisioning request model inspected in `provisioning.py` accepts a subdomain slug and brand asset URLs, but does not define or validate a tenant custom-domain field. The tenant registry model likewise has no persisted custom-domain field. There is consequently no evidenced control-plane write path establishing ownership, verification or lifecycle state for a custom domain consumed by this endpoint.

Adding a column alone would not establish a safe custom-domain feature. A future implementation needs a verified domain lifecycle and a strict hostname parser/allowlist before values are interpolated into Traefik rule syntax. It should reject control characters, whitespace, delimiters and unsupported wildcard forms; require proof of domain control; and define deactivation/removal propagation.

### 70.3 Required remediation and acceptance evidence

1. Decide whether custom tenant domains are supported. If not, remove or disable the unused provider endpoint and its proxy integration references.
2. If supported, add an explicit domain model/column and migration through the approved database-per-tenant/control-plane migration process, with uniqueness and lifecycle state appropriate to the platform.
3. Implement a verified domain-claim workflow (for example, DNS challenge) and persist verification status, owner tenant, verification timestamp and revocation state.
4. Parse and canonicalize hostnames with a strict hostname/IDNA validator; never interpolate unvalidated input into Traefik rule syntax.
5. Add tests proving the endpoint works against a migrated disposable control-plane database, omits unverified/inactive domains, rejects malformed or rule-injection strings, and removes routing after domain revocation.
6. Add an integration check that the actual Traefik provider can consume the returned document and that invalid provider output fails closed without publishing unintended routes.

**Assessment:** The current endpoint is unusable because it references an ORM attribute absent from the mapped model, and the inspected control-plane migration history does not supply that field. The feature's domain ownership/verification lifecycle is also not represented in the inspected provisioning contract. Treat custom-domain routing as unavailable until the model, migration, verified-ownership workflow and proxy integration are implemented and tested.

**Boundary:** static source/migration review only. No runtime, route, proxy, tenant, database, migration, DNS, credential or production state changed. PostgreSQL database-per-tenant remains the architecture. AUD-004 remains blocked.


## 71. Break-glass tenant administrator reset can select a different superuser and returns an unforced temporary password

**Source reviewed:**
- `backend/control_plane/api/routers/fleet_ops.py` (`POST /api/tenants/{slug}/reset-admin-password`)
- `backend/control_plane/models.py` (`TenantRegistry.admin_email`)

Static source review only. The reset endpoint was not invoked; no tenant account, password, session, database or production state was changed.

### 71.1 Target selection is broader than the registered tenant administrator

The endpoint selects the first user ordered by ascending `User.id` where either:

`User.email == tenant.admin_email OR User.is_superuser == True`

This is not an exact lookup of the registered administrator. If the tenant has an earlier-created superuser whose email differs from `TenantRegistry.admin_email`, that unrelated account can be selected and reset instead. With multiple superusers, the lowest-ID matching superuser can win even when the designated admin exists. The operation can therefore reset a different privileged account than the operator intended based on the route's tenant-admin semantics.

The handler then returns the selected account's email, so the response may reveal which account was actually changed, but only after the password reset has already committed.

### 71.2 The generated password is returned without a forced-change state

The handler generates a random one-time-looking password, hashes and stores it, sets the selected user's status to ACTIVE, clears failed-login attempts, updates `password_changed_at`, and deletes that user's active sessions and password-reset tokens. It then commits the tenant database and returns the plaintext `one_time_password` in the control-plane API response.

The inspected handler does not set a password-change-required flag or otherwise establish that the next login must replace this credential. A random password is not automatically single-use: absent a separate enforcement path, it remains a normal valid password until changed or reset again. Returning it in the response also exposes it to the same browser, proxy, observability and support tooling boundaries as other privileged API response secrets; this is distinct from, but related to, Section 64's provisioning-secret response issue.

The control-plane audit record is committed only after the tenant database commit. If the control-plane audit commit fails, the credential reset and session invalidation have already taken effect without the corresponding durable control-plane audit event.

### 71.3 Required remediation and acceptance evidence

1. Resolve the reset target by an exact, immutable tenant-admin user identifier or exact normalized `tenant.admin_email` match. If the designated administrator is absent or ambiguous, fail closed; do not fall back to an arbitrary `is_superuser` account.
2. If emergency superuser recovery is a separate supported operation, expose it as a separately named workflow requiring explicit target selection, stronger authorization and a recorded reason.
3. Enforce a password-change-required state at next login, or use a one-time recovery flow that cannot authenticate as a normal session and expires after a short, bounded interval.
4. Avoid returning reusable credentials in the ordinary JSON response. Use a narrowly scoped, one-time secret-delivery mechanism with explicit audience, expiry and access audit.
5. Add tests with multiple superusers, a non-superuser registered admin, mismatched/missing admin email, and a lower-ID unrelated superuser. Assert that only the exact intended account can be reset.
6. Add failure-injection tests around tenant commit, control-plane audit commit and response delivery; define a durable operation/audit strategy for the split-database boundary.
7. Verify that session/reset-token invalidation and forced credential replacement are atomic with the intended account reset, and that no credential appears in logs or ordinary audit details.

**Assessment:** The break-glass reset query can choose an unrelated superuser instead of the registered tenant administrator, and the returned temporary password is not accompanied by an enforced one-time/forced-change state in the inspected handler. This is a high-priority privileged-account recovery correctness and credential-handling gap. It requires exact target binding and a separately verified recovery lifecycle before production use.

**Boundary:** static source review only. No reset endpoint, user account, credential, tenant database, session, audit row or production state was exercised or changed. PostgreSQL database-per-tenant remains the architecture. AUD-004 remains blocked.


## 72. Reserved zero-price SANDBOX_UAT bundle is accepted by the ordinary tenant entitlement update path

**Sources reviewed:**
- `backend/control_plane/services/pricing.py` (`get_bundle_catalog`, `compute_contract_fee_paise`)
- `backend/control_plane/api/routers/fleet_ops.py` (`EntitlementsUpdateRequest`, `PATCH /api/tenants/{slug}/entitlements`)

Static source review only. No entitlement endpoint was invoked and no tenant commercial record or production state was changed.

### 72.1 The system-only sandbox bundle is exposed to the general pricing resolver

`get_bundle_catalog()` loads active commercial bundles from the control-plane catalog, then unconditionally injects a synthetic `SANDBOX_UAT` bundle with:
- all currently active module codes,
- a bundle annual price of zero.

`compute_contract_fee_paise()` resolves a supplied pricing model against this combined dictionary. When `SANDBOX_UAT` is selected and no non-negative custom fee override is supplied, the resolver treats it as an ordinary bundle and computes a zero annual fee (and zero monthly/per-active-bed fee after cycle conversion). The bundle's module composition is the complete active module list.

### 72.2 The ordinary entitlement mutation accepts this reserved identifier

The fleet entitlement request defines `pricing_model` as an unconstrained string. The `PATCH /tenants/{slug}/entitlements` handler accepts the request for any registered tenant, assigns the supplied pricing model and billing cycle, stores the supplied module JSON, and calls the shared pricing resolver. The inspected handler contains no guard that limits `SANDBOX_UAT` to a sandbox tenant or a sandbox lifecycle state.

Consequently, a caller authorized to use this control-plane mutation can assign the zero-price, all-active-modules sandbox bundle to an ordinary registered tenant. The source establishes the persisted commercial fee and selected bundle composition; it does not, by itself, establish that a payment processor is bypassed or that every runtime module gate consumes this bundle. The immediate proven impact is that the control-plane contract calculation can record a zero recurring license fee for a non-sandbox tenant while resolving the bundle as all active modules.

This is distinct from Section 62's missing named-operator authorization on the general entitlement mutation: Section 72 records the reserved commercial identifier being accepted and its pricing semantics, not the authorization boundary.

### 72.3 Required remediation and acceptance evidence

1. Separate system-only bundle definitions from the customer-selectable commercial catalog; do not expose `SANDBOX_UAT` through the ordinary bundle resolver.
2. Replace free-form `pricing_model` with a strict allowlisted enum or catalog lookup that excludes reserved internal identifiers for ordinary tenants.
3. Enforce tenant lifecycle/type eligibility server-side before applying sandbox pricing; never trust a caller-provided pricing identifier to prove that a tenant is a sandbox.
4. Reject invalid/inactive bundle codes rather than silently converting unknown values into a custom à-la-carte contract.
5. Add pricing unit tests proving ordinary tenants cannot resolve to `SANDBOX_UAT`, that sandbox eligibility is explicit, and that each billing cycle produces the expected fee.
6. Add endpoint tests asserting a normal tenant cannot persist the reserved bundle or a zero fee through this route, including requests with and without `base_license_fee_paise`.
7. Add a control-plane reconciliation check for existing non-sandbox tenants whose stored pricing model is reserved or whose recurring fee is unexpectedly zero.

**Assessment:** A system-internal zero-price sandbox bundle is reachable through the general tenant entitlement update contract without a sandbox-eligibility check. This is a high-priority commercial entitlement and contract-integrity defect. Runtime billing and module enforcement impact should be independently verified; no broader payment-bypass claim is made.

**Boundary:** static source review only. No entitlement mutation, billing operation, tenant database, catalog row or production state was exercised or changed. PostgreSQL database-per-tenant remains the architecture. AUD-004 remains blocked.

## 73. Federation API-key authentication does not enforce the owning tenant's active lifecycle state

**Sources reviewed on main:**
- `backend/core/dependencies.py` (`get_federated_node`)
- `backend/domains/federation/router.py` (`discover_and_aggregate_patient_across_branches`)
- `backend/control_plane/api/routers/fleet_ops.py` (`toggle_tenant_circuit_breaker`)
- `backend/control_plane/models.py` (`TenantRegistry`, `FederatedNode`)

Static source review only. No federation key was used, no discovery request was sent, and no tenant, node, pointer, database or production state was changed.

### 73.1 Federation authentication checks node state but not tenant lifecycle state

`get_federated_node()` hashes the supplied `X-Federation-API-Key` and selects a `FederatedNode` by matching hash plus `FederatedNode.is_active == True`. It does not join or otherwise resolve the owning `TenantRegistry`, and it does not require that a matching tenant registry row exists and has `is_active == True`.

The fleet status endpoint does attempt to keep the two records synchronized: `PATCH /api/tenants/{slug}/status` updates `TenantRegistry.is_active` and, when a matching node exists, sets `FederatedNode.is_active` to the same value in the same control-plane transaction. Federation-key revocation likewise disables the node. That synchronization is a useful lifecycle path, but it is not an authentication invariant: the federation dependency trusts the node flag alone and does not fail closed when the tenant registry is inactive, missing or inconsistent.

### 73.2 Discovery does not reject an inactive calling tenant

After authenticating the node, the discovery handler separately looks up the calling tenant registry with both the node's branch code and `TenantRegistry.is_active == True`. If no active row is found, it sets `calling_group_id = None`; it does not reject the authenticated caller.

For source hospitals configured as `FULL_MESH`, the branch-fetch path does not require a non-null caller registry/group and continues to evaluate source-side privacy, sharing and patient identity conditions. The missing caller registry only prevents access to `CORPORATE_GROUP_ONLY` sources, whose group comparison explicitly fails closed. Therefore, if an active or orphaned `FederatedNode` remains after its tenant registry becomes inactive or disappears, its key can still authenticate and can discover records from eligible `FULL_MESH` source tenants. The existing fleet status route normally disables both records together; this finding is about the missing enforcement at the authentication/discovery boundary if that cross-record state ever drifts.

### 73.3 Required remediation and acceptance evidence

1. Make federation authentication resolve the node's owning tenant registry by an immutable tenant identity and require exactly one matching, active tenant before accepting the key. Reject missing, duplicate or inactive ownership with the same unauthorized response used for revoked keys.
2. In the discovery handler, require the authenticated caller's active tenant context explicitly; do not convert a missing/inactive registry into a nullable group and continue under `FULL_MESH`.
3. Define and enforce a unique control-plane relationship between a federation node and its tenant identity. Branch code alone should not be the only ownership binding if it can be changed or reused.
4. Add tests for active node + inactive tenant, active node + missing tenant, mismatched branch ownership, revoked node, and active tenant + active node. Assert no source-tenant database is queried and no transfer log is written for invalid callers.
5. Add a reconciliation check that reports node/tenant active-state mismatches and orphan nodes; repair must be an explicit audited operation rather than silently reactivating either side.
6. Preserve the existing source-side privacy, purpose, patient-identity and sharing-policy checks; caller lifecycle validation is an additional prerequisite, not a replacement.

**Assessment:** The normal fleet suspension route synchronizes the tenant and node flags, but the federation API-key dependency does not enforce that invariant and discovery does not reject a missing active caller registry. A stale active/orphan node can therefore remain a valid federation caller against `FULL_MESH` sources. Treat this as a medium-priority federation lifecycle authorization gap until caller ownership/activity is enforced at the authentication boundary and covered by tests. This is a conditional state-drift finding, not evidence that a currently suspended tenant can bypass the normal status endpoint.

**Boundary:** static source review only. No runtime federation, key, tenant lifecycle, patient data, transfer log, database or production state was exercised or changed. PostgreSQL database-per-tenant remains the architecture. AUD-004 remains blocked.

## 74. PostgreSQL least-privilege roles are not wired into application or tenant database connections

**Sources reviewed on main:**
- `backend/core/config.py` (`Settings.DATABASE_URL`)
- `backend/core/database.py` (`build_db_url`, `control_engine`, `TenantEngineRegistry`)
- `backend/scripts/bootstrap.py` (`apply_database_roles`, `bootstrap_system`)
- `deployments/postgres-roles.sql`
- `docker-compose.yml` (PostgreSQL, db-init, API and backup service wiring)
- `.env.production.example`

Static configuration/source review only. No PostgreSQL role, database, grant, connection or production setting was changed or queried.

### 74.1 All control-plane and tenant connection URLs inherit the same configured database login

`Settings.DATABASE_URL` constructs a PostgreSQL URL using `POSTGRES_USER` and `POSTGRES_PASSWORD`. `build_db_url(db_name)` changes only the database name; it preserves that same username and password. The control-plane engine is built with `build_db_url(CONTROL_PLANE_DB_NAME)`, and every tenant engine returned by `TenantEngineRegistry.get_engine(db_name)` uses the same builder. Thus application runtime sessions for the control plane and every hospital database share one PostgreSQL login identity; the database-per-tenant boundary is not backed by distinct per-database runtime credentials in this implementation.

The same configured identity is also used by provisioning/database creation, migration helpers and the backup script's `pg_dump` invocation. Those are privileged operational tasks and should not share credentials with ordinary API request handling.

### 74.2 The repository's least-privilege role script is optional and does not establish the runtime role

`bootstrap.py` defines `apply_database_roles()`, but it runs only when the explicit `--apply-roles` argument is supplied or `POSTGRES_APPLY_ROLES` is set to a truthy value. The production Compose `db-init` command invokes only `python backend/scripts/bootstrap.py`; it does not pass `--apply-roles`. The production environment template does not set `POSTGRES_APPLY_ROLES`. Therefore the checked-in production bootstrap path does not apply the role script by default.

Even if applied, `deployments/postgres-roles.sql` creates `hms_app`, `hms_migrator`, `hms_backup` and `hms_exporter`, but the runtime URL builder never selects `hms_app` or `hms_migrator`. The script grants application and migration privileges on the database named `postgres`, not on the control-plane database or each dynamically provisioned tenant database. It also does not assign login passwords to the created roles. Its current grants therefore do not demonstrate a usable, per-tenant least-privilege runtime path.

For a fresh Compose-managed PostgreSQL volume, the official PostgreSQL image initializes `POSTGRES_USER` as its bootstrap database superuser unless an initialization customization changes that behavior. The repository's Compose service mounts no PostgreSQL initialization directory or custom role bootstrap at database-container startup. The production template describes this as a dedicated database user, but does not itself constrain its PostgreSQL attributes. The exact live role attributes remain a deployment fact that requires catalog verification; the source proves that the application does not switch to the separately declared `hms_app` role.

### 74.3 Required remediation and acceptance evidence

1. Split database identities by responsibility: a tightly controlled bootstrap/DB-owner identity, migration identity, API runtime identity, backup identity and monitoring identity. Do not pass bootstrap credentials into the serving API container.
2. Provision the runtime role and grants explicitly for the control-plane database and each tenant database. The runtime role must not be superuser, database owner, role creator, database creator, replication-capable or able to connect to unrelated tenant databases.
3. Ensure the API can connect only to the control-plane database and the one tenant database selected by the trusted control-plane resolver. Prefer distinct tenant-scoped credentials/roles or another PostgreSQL-enforced boundary; do not rely solely on changing the database name in a URL.
4. Use a separate migration role for Alembic and provisioning, and a read-only backup role for `pg_dump`; define the backup role's cross-database scope explicitly without granting it application write privileges.
5. Make role provisioning an explicit, idempotent, reviewed bootstrap prerequisite with safe secret delivery/rotation. Remove the misleading optional script path or make it a verified deployment gate.
6. Add disposable PostgreSQL tests that inspect `rolsuper`, `rolcreatedb`, `rolcreaterole`, `rolreplication`, database ownership, CONNECT, schema/table/sequence grants and default ACLs for the control plane and at least two tenant databases.
7. Prove that the API role can perform required tenant operations in its assigned database but cannot connect to, read, write, create objects in, or change ownership/grants on another tenant database or the control-plane database unless explicitly required.
8. Add deployment validation that fails startup/release if the configured API identity has privileged role attributes or grants outside its approved database allowlist. Keep migration and backup jobs on separate credentials and verify that their secrets are not present in the API container environment.

**Assessment:** The declared PostgreSQL least-privilege roles are not integrated into the application's connection configuration or normal production bootstrap. All control-plane and tenant engines inherit `POSTGRES_USER`, and the optional role script neither configures that runtime identity nor grants the created application role across the actual control-plane/tenant databases. On a fresh standard Compose PostgreSQL initialization, this is likely the bootstrap superuser identity; confirm live catalog attributes before making a deployment-specific assertion. This is a high-priority database isolation and blast-radius gap: separate PostgreSQL databases exist, but the checked-in application configuration does not establish least-privilege database authorization between them.

**Boundary:** static source/configuration review only. No database, role, grant, credential, tenant, migration or production state was exercised or changed. PostgreSQL database-per-tenant remains the architecture. AUD-004 remains blocked.

## 75. Mandatory pre-restore safety snapshot imports a backup function that does not exist

**Sources reviewed on main:**
- `backend/control_plane/api/routers/fleet_ops.py` (`restore_tenant_from_snapshot`)
- `backend/scripts/backup_service.py` (available backup functions)
- `backend/scripts/restore_tenant.py` (`restore_encrypted_backup`)

Static source review only. The restore endpoint was not invoked; no backup, database, tenant, file, or production state was read or changed.

### 75.1 The mandatory safety-snapshot import fails before the restore is attempted

The control-plane endpoint `POST /api/tenants/{slug}/backups/{filename}/restore` queues a background task. Inside that task, before calling `restore_encrypted_backup()`, it executes:

```python
from backend.scripts.backup_service import create_encrypted_backup
safety_path = create_encrypted_backup(tenant_db_name, encrypted_backup_key)
```

The checked-in `backend/scripts/backup_service.py` defines `_dump_and_encrypt(db_name, encryption_key, output_dir)` as its snapshot implementation, plus the backup-cycle/daemon helpers. It does not define or export `create_encrypted_backup`. A repository-wide code search also returned no definition or import-compatible implementation of that name.

Python therefore raises `ImportError` when the background task reaches this import. The exception is caught by the endpoint's task wrapper, recorded as `PRE_RESTORE_SAFETY_SNAPSHOT_FAILED` / `RESTORE_FAILED`, and re-raised. The subsequent `restore_encrypted_backup(str(target_path), ...)` call is unreachable in the current source state. The endpoint can queue and acknowledge the task at HTTP request time, but the background restore will fail before modifying the tenant database.

The safety snapshot is explicitly described in the source as mandatory and fail-closed. This is not a recommendation to bypass that control: the missing implementation prevents both the safety control and the intended restore operation from completing.

### 75.2 Required remediation and acceptance evidence

1. Implement and export a reviewed `create_encrypted_backup` helper with a clear contract, or update the restore task to call the existing `_dump_and_encrypt` helper with the correct raw tenant key and output directory. Do not pass the encrypted-at-rest registry value where a decrypted backup key is required.
2. Keep the mandatory pre-restore snapshot fail-closed. Verify that it is durably written, checksum sidecar is present, and its artifact can be decrypted with the tenant's key before allowing destructive restore to proceed.
3. Add a disposable PostgreSQL integration test that invokes the control-plane restore workflow with synthetic tenant data and a valid encrypted snapshot. Assert the pre-restore snapshot exists and is decryptable, the selected restore completes, and the expected data state is restored.
4. Add failure-injection tests for missing backup helper, snapshot write failure, checksum failure, decryption failure, and pg_restore failure. Every pre-restore failure must leave the original tenant database unchanged and produce a durable, correctly correlated operation result.
5. Avoid returning a successful queued status as the only completion signal. Expose a durable restore operation ID and terminal success/failure state to the operator; verify that the audit events distinguish queued, safety-snapshot complete, restore started, and restore complete.
6. Confirm the safety snapshot helper's call sites and tests use the same documented raw/encrypted key boundary; never log or expose the decrypted key.

**Assessment:** Deterministic functional defect in the privileged restore workflow. The endpoint's mandatory pre-restore safety snapshot imports a symbol absent from the checked-in backup service, so the background task aborts before the actual restore call. This prevents the UI-triggered restore path from completing as implemented. It is not evidence that scheduled backup creation or the standalone restore script is broken.

**Boundary:** static source review only. No restore, backup, snapshot, database, file, credential, migration, or production state was exercised or changed. AUD-004 remains blocked.

## 76. Restore-drill runner can certify a failed restore and unconditionally drops a caller-selected drill database

**Sources reviewed on main:**
- `backend/scripts/restore_drill.py` (`run_restore_drill`, `verify_backup_checksum`, cleanup)

Static source review only. The DR drill was not executed; no PostgreSQL database, backup, tenant, credential or production state was accessed or changed.

### 76.1 The drill's success predicate ignores the pg_restore exit status

The runner invokes `pg_restore` with `check=False` and captures its return code. For a non-zero result it may log an error, but it does not stop the drill or preserve the result as a required success condition. The final `drill_passed` predicate includes only:
- checksum sidecar verification;
- presence of the six names in `CRITICAL_HMS_TABLES`;
- RTO within the configured threshold.

It does not include `proc.returncode == 0`. The subsequent integrity loop counts rows where possible, but the final predicate does not require those counts to be readable, non-negative, non-empty, or consistent with a source manifest. Therefore, a partially restored database that happens to contain all six critical table names can be reported as `PASSED` even though `pg_restore` reported errors. The report also has no explicit restore-command success field. This makes the output unsuitable as a reliable restore certification signal.

### 76.2 A caller-selected drill database is dropped before use

When `drill_db_name` is supplied, the only validation is the identifier pattern `^drill_[a-zA-Z0-9_]+$`. The runner then executes `DROP DATABASE IF EXISTS "<name>" WITH (FORCE)` before creating the database. The cleanup path executes the same unconditional drop unless `keep_drill_db` is true.

There is no existence refusal, unique per-run ownership marker, or proof that an existing database was created by this invocation. Consequently, a caller can supply the name of an unrelated existing database that happens to use the accepted `drill_` prefix, and the runner will drop it before starting the drill. The default generated name uses only tenant slug and a UTC timestamp with one-second precision, so concurrent or repeated invocations within the same second can also collide and drop one another's database.

### 76.3 Required remediation and acceptance evidence

1. Treat every non-zero `pg_restore` exit status as a hard drill failure. Do not proceed to a PASSED state; preserve stderr safely and record the exact exit status in the report.
2. Make the final success predicate require successful restore execution, checksum verification, critical schema checks, meaningful data/integrity checks and RTO compliance. Distinguish warnings from errors according to documented `pg_restore` exit semantics rather than substring matching stderr.
3. Add a restore manifest or independent source-side expectations for critical table/row checks; table-name presence alone is not proof of a complete or usable restore. Mark unavailable/failed checks as failures, not silently as skipped.
4. Never drop a pre-existing database merely because its name matches a prefix. Generate a collision-resistant per-run name, query for existence and fail closed if it already exists. If explicit names remain supported, require the database to be absent before creation.
5. Track whether this invocation successfully created the database and only drop that database during cleanup. Do not run cleanup DROP against a name whose ownership by the current drill has not been established.
6. Add disposable PostgreSQL tests for pg_restore exit codes 1 and 2, partial restore with all critical table names present, failed count queries, pre-existing explicit drill database, concurrent name collision, and cleanup after both successful and failed runs. Assert unrelated databases are never dropped and no failed restore can produce `PASSED`.

**Assessment:** High-priority disaster-recovery integrity and destructive-target-selection defect. The current runner can overstate restore success because it ignores the restore command's exit status, and it can delete an existing database selected by a caller or collided with by another run. Both defects undermine the safety and evidentiary value of DR drills. This is a static code-path finding; no live restore or database deletion was attempted.

**Boundary:** static source review only. No restore drill, database, backup, tenant, credential, migration or production state was exercised or changed. PostgreSQL database-per-tenant remains the architecture. AUD-004 remains blocked.

## 77. Backup vault mode labels chmod-based files as WORM without an immutable storage boundary

**Sources reviewed on main:**
- `backend/scripts/backup_service.py` (`main`, `--vault-mode` branch)
- `docker-compose.prod.yml` (backup-volume and service mounts)

Static source/configuration review only. Vault mode was not run; no backup files, volumes, storage policies, credentials or production state were accessed or changed.

### 77.1 Read-only mode bits are the only immutability control in the vault implementation

The `--vault-mode` branch copies each `*.dump.enc` artifact from `/source` to `/vault/immutable` when the target filename does not already exist, writes a SHA-256 sidecar, and applies `chmod 0400` to both files. The implementation does not establish an immutable/WORM storage policy, object-lock retention, append-only storage service, filesystem immutable attribute, separate administrative trust boundary, or independent audit of retention-policy changes. Ordinary file ownership/privileges can change the mode or remove/replace the files; mode 0400 alone is not a WORM guarantee.

The copy is also performed directly to the final target path. If the process stops after creating a partial target but before completing the copy and sidecar, the next poll sees that the target exists and skips it permanently. There is no temporary target plus atomic publish, completion marker, or validation/retry of an existing target. A partial artifact can therefore occupy the expected filename and prevent later sealing of the source artifact.

The production Compose file reviewed mounts the shared `hms_backups` volume into application services; it does not define a distinct vault service or a separate immutable storage backend. This is a source/configuration observation, not a claim about external storage controls that may exist outside the repository.

### 77.2 Required remediation and acceptance evidence

1. Do not describe chmod-only storage as WORM or immutable. Either rename the feature to reflect its actual best-effort read-only behavior or implement a separately administered immutable storage target with enforced retention/object lock.
2. Separate backup writers from vault retention administrators. Document and test who can delete, overwrite, change retention, or disable immutability, including host/root and cloud-account administrators.
3. Copy to a unique temporary object, verify the complete encrypted artifact and checksum, then atomically publish the final object/manifest. On interrupted copy, discard or resume the temporary object; never treat mere target existence as successful sealing.
4. Verify the destination object and its retention/lock state after publication. Reconcile source artifacts, destination artifacts, manifests and missing/partial objects on every poll.
5. Add tests for interrupted copy, pre-existing partial destination, checksum mismatch, attempted overwrite/delete, retention-policy changes, and recovery after process restart. Demonstrate that the configured storage provider enforces immutability independently of the backup process identity.

**Assessment:** High-priority backup-retention assurance gap if this mode is relied on for WORM or ransomware-resistant recovery. The checked-in implementation provides filesystem permission hardening, not an independently enforced immutable backup boundary; interrupted copies can also be mistaken for completed destinations. External infrastructure could add controls, but none are established by the reviewed repository configuration.

**Boundary:** static source/configuration review only. No vault mode, backup, storage volume, database, credential, migration or production state was exercised or changed. PostgreSQL database-per-tenant remains the architecture. AUD-004 remains blocked.

## 78. Off-host backup configuration is ignored by the S3 client and delivery failures are counted as successful tenant backups

**Sources reviewed on main:**
- `backend/core/config.py` (off-host S3 settings)
- `backend/scripts/backup_service.py` (`deliver_backup_offhost`, `run_backup_cycle`)
- `.env.production.example` (documented off-host configuration)

Static source/configuration review only. No S3 bucket, remote destination, backup, credential or production state was accessed or changed.

### 78.1 Declared S3 endpoint, region and credentials are not passed to boto3

The application settings and production environment example define:
- `BACKUP_OFFHOST_S3_ENDPOINT_URL`
- `BACKUP_OFFHOST_S3_REGION`
- `BACKUP_OFFHOST_S3_ACCESS_KEY`
- `BACKUP_OFFHOST_S3_SECRET_KEY`

However, `deliver_backup_offhost()` constructs its client with only `boto3.client("s3", config=Config(...))`. It does not pass any of the four configured values as `endpoint_url`, `region_name`, `aws_access_key_id` or `aws_secret_access_key`. Therefore the documented custom S3-compatible endpoint, region and explicit credentials do not control the client; boto3 falls back to its ambient default endpoint/region/credential chain. Deployments relying on those settings can fail to upload or can target a different account/endpoint than operators intended.

### 78.2 A failed or absent off-host delivery is not propagated to backup-cycle status

When off-host delivery is enabled but neither remote directory nor S3 bucket is configured, `deliver_backup_offhost()` returns `{"delivered": false, "reason": "OFFHOST_DISABLED"}` only for the disabled flag; with the flag enabled and no destination it returns the initial `{"delivered": false}`. The caller ignores the returned dictionary and increments the successful tenant `count` unconditionally after the call.

The same unconditional count occurs when delivery returns `delivered: false` after an S3 upload failure. The function catches the exception and returns a failure dictionary rather than raising it, so the per-tenant exception handler does not catch the failure. Thus the backup cycle's count can report a tenant as backed up even though the configured off-host copy did not complete. No per-tenant delivery result is emitted as a durable status or metric by this path.

This is distinct from local encrypted snapshot creation: a local backup may exist and be valid while off-host replication has failed. The defect is the inaccurate replication outcome and lack of enforcement when off-host delivery is configured.

### 78.3 Required remediation and acceptance evidence

1. Pass configured endpoint, region and explicit credentials to the S3 client, or remove unsupported settings and document the one supported credential/endpoint mechanism. Never log secret values.
2. Validate configuration at startup: if off-host is enabled, require at least one complete destination configuration and reject partial S3 credential/endpoint settings.
3. Treat delivery result as a separate state from local backup creation. Persist/emit per-tenant local-backup and off-host-delivery outcomes; do not increment a replicated-success count unless `delivered` is true.
4. Ensure any configured mandatory off-host destination failure fails the cycle or produces an explicit degraded result and actionable alert. Define semantics when both remote directory and S3 are configured.
5. Verify both uploaded artifact and uploaded checksum/manifest at destination; use object versioning/retention controls where required and verify the destination account/bucket identity.
6. Add tests for custom endpoint and region propagation, explicit credential propagation, no destination while enabled, boto3 upload exceptions, mixed remote-success/S3-failure, and the backup-cycle result/metrics. Assert local backup success is not conflated with off-host replication success.

**Assessment:** High-priority recovery-point and operational-reporting gap for deployments that rely on off-host replication. The checked-in settings advertise endpoint/region/static credentials that the client ignores, and the caller counts false delivery results as successful tenant backups. Whether a particular deployment still succeeds through ambient AWS credentials/default endpoints depends on external environment configuration and was not tested.

**Boundary:** static source/configuration review only. No off-host destination, S3, backup, database, credential, migration or production state was exercised or changed. PostgreSQL database-per-tenant remains the architecture. AUD-004 remains blocked.


## 79. Host backup retention is local-only and the freshness metric certifies local publication, not remote replication

**Sources reviewed on the audit branch:**
- `deployments/backup-postgres.sh` (success/failure metric publication, optional `BACKUP_REMOTE_DEST` rsync, retention cleanup)
- `deployments/prometheus-alerts.yml` (`BackupFreshnessWarning`, `BackupRunFailed`)
- `deployments/prometheus.yml` (node-exporter scrape)

Static source/configuration review only. No backup command, rsync, remote destination, Prometheus server, storage path, credential or production state was accessed or changed.

### 79.1 The success timestamp is written before optional remote replication

After the encrypted database/global dumps have been generated, decrypted/list-validated, checksummed and atomically moved into the local final directory, the script publishes `backup_last_completion_timestamp_seconds` and sets `backup_last_status 1`. Only after publishing those metrics does it perform the optional `rsync` to `BACKUP_REMOTE_DEST`.

If rsync fails, the EXIT trap subsequently changes `backup_last_status` to zero and records a failure/attempt timestamp, so the existing `BackupRunFailed` rule can alert when the status textfile update succeeds. However, the last-success timestamp remains the timestamp of the locally completed snapshot. `BackupFreshnessWarning` therefore measures local snapshot freshness, not successful completion/freshness of the configured remote copy. Its description says “verified database backup” without distinguishing the two recovery copies.

This is not a claim that rsync failure is completely unalerted: the separate status rule exists. The gap is that the freshness metric and alert do not establish remote-copy freshness, and a successful local run can continue to look fresh while remote replication remains unavailable.

### 79.2 Retention cleanup never applies to the remote destination

The script applies `find ... -mtime +$RETENTION_DAYS -exec rm -rf` only under `$BACKUP_ROOT`. The optional rsync creates a timestamped remote subdirectory named `$backup_name`, but no corresponding remote pruning, lifecycle policy, retention verification or remote-capacity monitoring is implemented in this script. Consequently, when `BACKUP_REMOTE_DEST` is used as a persistent remote filesystem destination without an independently configured lifecycle policy, each run adds another backup directory and the configured local `RETENTION_DAYS` does not bound remote storage growth.

The repository cannot establish whether operators have configured an external remote retention policy; this finding is limited to the checked-in script.

### 79.3 Required remediation and acceptance evidence

1. Publish distinct local-snapshot and remote-replication state/timestamps. Make metric names and alert descriptions state precisely which copy has completed.
2. Add a remote freshness alert whenever remote replication is configured; it must detect missing metrics, failed transfer, and a remote copy older than the declared RPO.
3. Implement remote retention with a documented policy and safe selection rules, or require and validate an external object/filesystem lifecycle policy. Never silently assume local retention applies remotely.
4. Verify remote artifact count, size, checksum/manifest and retention behavior; ensure failed/partial rsync runs are not treated as complete remote snapshots.
5. Add shell-level tests with a disposable local/remote fixture for rsync success, failure, interruption, retention boundary dates, and preservation of the newest known-good remote snapshot. Test the Prometheus expressions against absent, stale and failed local/remote metrics.

**Assessment:** High-priority disaster-recovery operations and storage-governance gap for deployments that configure `BACKUP_REMOTE_DEST` and rely on this script for remote retention or remote RPO assurance. Local retention is implemented; remote retention and remote freshness certification are not. External lifecycle controls may mitigate storage growth, but they are not established by the reviewed repository configuration.

**Boundary:** static source/configuration review only. No backup, restore, rsync, remote destination, storage, database, credential, migration or production state was exercised or changed. PostgreSQL database-per-tenant remains the architecture. AUD-004 remains blocked.


## 80. Tenant backup daemon treats partial tenant failures as a completed cycle and exposes no per-tenant failure signal

**Sources reviewed on the audit branch:**
- `backend/scripts/backup_service.py` (`run_backup_cycle`, `run_backup_daemon`, `main`)
- `docker-compose.prod.yml` (declared production services and commands)

Static source/configuration review only. The daemon was not started; no tenant database, backup, scheduler, credential or production state was accessed or changed.

### 80.1 Per-tenant dump errors are logged and swallowed

`run_backup_cycle()` iterates active cloud tenants. A tenant dump/decryption exception is caught, logged, and the loop continues; the function ultimately returns only an integer count of local snapshots created. It does not return a structured list of tenant outcomes, raise an aggregate failure when one or more tenants fail, or persist a per-tenant last-success/last-failure timestamp. The existing return count is not consumed by the daemon.

### 80.2 The daemon resets backoff and waits the full interval after a partially failed cycle

`run_backup_daemon()` calls `run_backup_cycle()` and ignores its return value. If the cycle returns normally—even when one or more tenants failed inside the per-tenant exception handler—the daemon enters the `else` branch, resets retry delay to the initial value, and waits the full configured interval. Exponential retry is reserved for an `OperationalError` escaping the cycle, such as a control-plane database connection failure; it does not apply to swallowed tenant-level failures.

No per-tenant backup outcome metric is emitted by this daemon path. The production Compose file reviewed does not declare a service running `backend/scripts/backup_service.py --daemon`; therefore this daemon finding applies only where an operator or external scheduler actually launches it. This does not establish that the separate host-level `deployments/backup-postgres.sh` is unscheduled or inactive.

### 80.3 Required remediation and acceptance evidence

1. Return structured per-tenant outcomes from each cycle, including local snapshot, checksum, off-host result, timestamps and sanitized error category.
2. Treat a cycle with any required tenant failure as degraded/failed. Do not silently reset retry state or wait a full interval without recording and surfacing the failed tenant set.
3. Persist per-tenant last-success and last-failure state in a durable control-plane operational register or another explicitly designed monitoring store; avoid high-cardinality or patient-identifying metric labels.
4. Add alerts for tenant backup coverage, missing tenant success within the RPO, repeated tenant failures and unexpected changes in the eligible tenant set.
5. Add tests with multiple synthetic tenants where one dump fails, one succeeds, and off-host delivery fails; assert exact aggregate status, retry behavior, durable outcome and alert signal.
6. Document and test the production scheduler/launcher for this daemon, including single-instance/overlap protection and expected behavior during restarts. Keep this distinct from the host-level PostgreSQL backup schedule.

**Assessment:** High-priority tenant-level recovery assurance gap if this daemon is used as the tenant backup scheduler. A single tenant can miss a backup while the daemon cycle returns normally and proceeds to its regular interval, with only a log entry to indicate the failure. The repository's production Compose file does not itself launch this daemon, so deployment usage must be confirmed before attributing this behavior to a live environment.

**Boundary:** static source/configuration review only. No daemon, backup, tenant database, scheduler, credential, migration or production state was exercised or changed. PostgreSQL database-per-tenant remains the architecture. AUD-004 remains blocked.


## 81. Restore drill labels record age as RPO without measuring the recovery-point gap

**Sources reviewed on the audit branch:**
- `backend/scripts/restore_drill.py` (`run_restore_drill`, report construction and CLI exit status)

Static source review only. The restore drill was not run; no tenant database, backup, clinical record, credential or production state was accessed or changed.

### 81.1 The reported RPO is the age of the newest restored record

The drill queries `MAX(created_at)` from `patient_encounters`, `invoices` and `patients`, takes the newest timestamp it can read, and computes:

`current_UTC_time - newest_restored_record_timestamp`

That value is emitted as `measured_rpo_seconds`. It measures the age of the newest available record in the restored snapshot, not the RPO/data-loss interval. A valid RPO measurement needs a defined failure/cutoff time and the latest committed source transaction represented in the recoverable backup (or an equivalent independently recorded recovery-point marker). The current implementation does not capture or compare those two points. It can therefore report a large value during normal low activity, or a small value even when transactions after the backup were lost.

The candidate timestamp queries also suppress all exceptions. If all three queries fail or yield no timestamp, the report emits `null` for RPO; the drill pass predicate does not require an RPO value or enforce an RPO threshold. The report can still be marked `PASSED` based on checksum, presence of six critical table names, and RTO alone.

### 81.2 Required remediation and acceptance evidence

1. Define the RPO reference point explicitly (for example, a recorded simulated incident cutoff) and persist a trustworthy source-side high-water mark/transaction timestamp at that point.
2. Record the backup's recovery-point timestamp independently at backup creation; compare it with the incident cutoff and, where appropriate, verify the restored snapshot's latest committed marker.
3. Do not infer RPO from the wall-clock age of the newest clinical row. Treat missing/unreadable markers as an unverified RPO, not a numeric measurement.
4. Add a configured RPO threshold to the drill pass predicate if the report is intended to certify an RPO objective. A missing RPO measurement must not silently pass that gate.
5. Add deterministic tests for low-activity tenants, stale backups, post-backup transactions, missing timestamp columns, query failures, empty datasets, and clock/time-zone handling. Assert that the computed loss interval matches the known simulated cutoff and backup marker.

**Assessment:** High-priority disaster-recovery measurement and certification-integrity gap. The current `measured_rpo_seconds` field is not an RPO measurement, and RPO is not part of the pass/fail predicate. The report can therefore claim `PASSED` without establishing whether the declared recovery-point objective was met.

**Boundary:** static source review only. No restore drill, backup, tenant database, clinical record, credential, migration or production state was exercised or changed. PostgreSQL database-per-tenant remains the architecture. AUD-004 remains blocked.


## 82. Restore drill buffers the entire encrypted and decrypted dump in process memory

**Sources reviewed on the audit branch:**
- `backend/scripts/restore_drill.py` (`verify_backup_checksum`, `decrypt_backup_bytes`, `run_restore_drill`)

Static source review only. No backup was opened or decrypted, no restore drill was run, and no database or production resource was accessed or changed.

### 82.1 Multiple full-artifact memory allocations scale with backup size

The checksum verifier reads the complete encrypted artifact with `f.read()` before hashing. `decrypt_backup_bytes()` then loads the complete encrypted file again with `Path.read_bytes()` and returns the complete decrypted dump as a bytes object. `run_restore_drill()` retains that decrypted bytes object and passes it as `subprocess.run(input=...)` while also setting `capture_output=True`, retaining pg_restore stdout/stderr in memory until the subprocess completes.

Peak process memory therefore scales with the full backup size and can include the encrypted artifact, decrypted dump, subprocess input buffering and captured restore output. This is not a bounded streaming restore path. As tenant databases and restore diagnostics grow, a drill can exhaust its container/host memory or be OOM-killed before it produces a report. The same in-memory design also makes the restore-drill capacity profile materially different from the host restore script, which streams GPG output to `pg_restore`.

### 82.2 Required remediation and acceptance evidence

1. Hash the encrypted artifact incrementally in fixed-size chunks; do not call `read()` without a bounded size for the whole file.
2. Stream decryption into a protected temporary file or pipe with restrictive permissions and cleanup guarantees; avoid returning the complete plaintext dump as a Python bytes object.
3. Feed the stream/file directly to `pg_restore`; send stdout/stderr to bounded log files or retain only a capped diagnostic tail.
4. Enforce a configured temporary-storage budget and verify available disk space before starting. Ensure plaintext temporary artifacts are removed on success, failure, interruption and process termination.
5. Add large synthetic dump tests that assert bounded memory behavior, streaming correctness, checksum/decryption failure handling, interrupted restore cleanup and diagnostic truncation.
6. Document expected memory/disk requirements and distinguish drill capacity from the production restore path.

**Assessment:** High-priority restore-drill availability and scalability gap. A backup larger than available memory can prevent the drill from completing, weakening the reliability of scheduled recovery evidence. Actual failure thresholds depend on artifact size, runtime/container limits and subprocess buffering; none were measured in this static review.

**Boundary:** static source review only. No backup, decryption, restore drill, database, credential, migration or production state was exercised or changed. PostgreSQL database-per-tenant remains the architecture. AUD-004 remains blocked.


## 83. Restore drill can certify table presence while table-count verification failed

**Source reviewed:** `backend/scripts/restore_drill.py` (`run_restore_drill`).

Static source review only. No restore drill, database query, backup or patient data was accessed or executed.

### 83.1 Failed table reads are recorded but excluded from certification

The drill enumerates table names and records missing entries from `CRITICAL_HMS_TABLES`. It then attempts `SELECT COUNT(*)` for each discovered table. Any exception is caught and stored as `table_counts[tbl] = -1`. However:

- `all_tables_valid` checks only whether the six critical table names appear in the catalog.
- `drill_passed` checks checksum, critical table-name presence and RTO only.
- It never checks whether any table count equals `-1`, nor whether the critical tables were successfully queried.
- `verified_tables_count` is populated with `len(table_counts)`, which includes entries whose count query failed.

Consequently, a drill can mark the schema/table-presence check as valid and include failed table reads in its reported verified-table total. A permissions problem, damaged relation or other query failure can therefore be represented in the report without making the certification fail. A successful `COUNT(*)` would still prove only that the relation can be scanned/countable, not that clinical content is semantically correct or complete.

This is distinct from the previously documented `pg_restore` return-code omission: even after restore exit handling is corrected, the current table-read verification itself is not a pass/fail gate.

### 83.2 Required remediation and acceptance evidence

1. Track per-table verification outcomes explicitly (queried, failed, skipped), with error classification and bounded diagnostics.
2. Require successful reads for every required critical table; a failed or skipped required check must produce FAILED or UNVERIFIED, never PASSED.
3. Rename the report count to distinguish discovered tables from successfully verified tables; compute the latter from successful checks only.
4. Add deterministic tests that inject a count-query failure for each critical table and a noncritical table, and assert the certification state and report counters.
5. Add a documented integrity policy for checks beyond row counts (schema/revision, constraints, representative domain invariants and backup-manifest/high-water-mark comparisons).

**Assessment:** High-priority restore-evidence integrity gap. Current reporting can overstate what the drill actually read and verified. No claim is made that a particular production restore has failed.

**Boundary:** static source review only; no backup, database, migration, restore drill, credential or production state was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 84. Restore request terminates active tenant database sessions before the safety snapshot is secured

**Sources reviewed on the audit branch:**
- `backend/control_plane/api/routers/fleet_ops.py` (`_terminate_db_connections`, `restore_tenant_from_snapshot`)

Static source review only. The restore endpoint was not invoked; no tenant connection, database, backup, credential or production state was accessed or changed.

### 84.1 Session termination happens synchronously before the background restore's safety gate

The restore request handler calls `_terminate_db_connections(control_db, tenant.db_name)` immediately after checking that the requested snapshot path exists. That helper executes `pg_terminate_backend` for every other session whose `pg_stat_activity.datname` matches the tenant database, then commits.

Only after terminating those sessions does the handler capture the tenant key and register `_execute_restore` with FastAPI `BackgroundTasks`. The mandatory pre-restore safety snapshot is performed later, inside that background task. If the safety snapshot fails, the task aborts before `restore_encrypted_backup()` is called—but the earlier connection termination has already occurred.

This ordering creates an avoidable availability window: an operator can submit a restore request and have all active tenant sessions forcibly disconnected before the system has secured the rollback snapshot or established that the restore can proceed. In the currently reviewed source, Section 75 separately documents that the safety-snapshot import is unresolved; with that defect present, the request can terminate sessions and then fail at the safety gate without performing the intended restore. Even after the missing helper is corrected, a slow or failed snapshot leaves the tenant's active sessions disrupted for longer than necessary.

This finding concerns session availability and sequencing. It does not claim that terminating sessions corrupts the database, that all clients remain disconnected permanently, or that a particular production request has caused an outage.

### 84.2 Required remediation and acceptance evidence

1. Move tenant-session termination out of the synchronous request handler. Validate the snapshot, establish a durable operation record, and complete and verify the mandatory pre-restore safety snapshot before entering the short maintenance/termination window.
2. Re-check the target tenant and restore operation state immediately before termination and restore, so stale or superseded requests cannot unexpectedly disconnect the tenant.
3. Make the transition explicit: queued → safety snapshot created and verified → maintenance/connection drain → restore started → restored/failed → tenant available. Do not report the restore as safely underway before the safety snapshot gate passes.
4. On every pre-restore failure, prove that tenant sessions were not terminated and that the tenant remains available. On restore failure after termination, define and test the reconnection/availability recovery behavior.
5. Add deterministic tests with a mocked `pg_terminate_backend` and injected safety-snapshot success/failure. Assert that no termination occurs on missing/failed snapshot, and that termination occurs only after a verified snapshot and immediately before the restore operation.
6. Keep this acceptance evidence separate from the Section 75 test that proves the safety snapshot helper exists and works, and from Section 76's isolated restore-drill database safety checks.

**Assessment:** High-priority availability and restore-sequencing gap in the privileged tenant restore endpoint. The handler disconnects all current sessions before the mandatory rollback snapshot is attempted; a safety-snapshot failure therefore does not leave the tenant's existing sessions untouched. Actual user-visible impact depends on connection-pool/client reconnect behavior and was not measured.

**Boundary:** static source review only. No restore endpoint, tenant session, backup, database, credential, migration or production state was exercised or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 85. Tenant restore stages plaintext database dumps in the shared backup volume without explicit private-file or crash-cleanup guarantees

**Sources reviewed on the audit branch:**
- `backend/scripts/restore_tenant.py` (`restore_encrypted_backup`)
- `docker-compose.prod.yml` (backup-volume mounts for API, worker and onboarding services)

Static source/configuration review only. No backup was opened or decrypted, no restore was run, and no volume, database, credential or production state was accessed or changed.

### 85.1 Decrypted database content is written beside encrypted backups on the shared application volume

`restore_encrypted_backup()` reads the complete encrypted artifact into memory, decrypts it into `decrypted_bytes`, and writes those plaintext bytes to:

`enc_path.with_suffix(".restoring.dump")`

The helper does not create this file with an explicitly restrictive mode, does not use a private per-operation temporary directory, and does not place the plaintext staging file under a dedicated ephemeral filesystem. File permissions therefore depend on the Python process umask and volume ownership rather than an explicit least-privilege guarantee.

The production Compose configuration mounts the same named `hms_backups` volume at `/app/backups` in the API, worker and onboarding-portal services. The control-plane restore workflow calls this helper using a path under `backups`. As a result, the plaintext staging artifact is created in storage shared with multiple application services, rather than in a restore-only private location.

The helper unlinks the staging file in a `finally` block after the restore function exits normally through Python exception handling. That cleanup is not guaranteed for abrupt process/container termination (for example, SIGKILL or host failure); in such a case the plaintext dump can remain in the persistent named volume. The deterministic `.restoring.dump` name also means concurrent attempts using the same encrypted source path can overwrite or remove one another's staging file. The restore endpoint and helper shown do not establish a per-tenant/per-artifact lock or unique staging path.

### 85.2 Required remediation and acceptance evidence

1. Decrypt into a unique, per-operation temporary file in a dedicated ephemeral location that is not mounted into unrelated application services. Use restrictive permissions at creation time (for example, mode `0600`) rather than relying on the process umask.
2. Ensure the staging directory is private to the restore process and has explicit ownership, mount and lifecycle controls. Do not expose plaintext restore artifacts through the shared encrypted-backup volume.
3. Add startup/reconciliation cleanup for abandoned restore staging artifacts, with safe age/ownership/operation checks; do not delete an artifact belonging to an active restore.
4. Use unique operation-scoped paths and a durable per-tenant restore lock/lease so simultaneous restores cannot share, overwrite or unlink each other's staging files or run concurrent `pg_restore` operations against the same tenant database.
5. Add tests for file mode and directory isolation, concurrent restore attempts, normal cleanup, injected exceptions, abrupt-process termination/restart residue, and cleanup of only abandoned operation-owned files.
6. Stream decryption to the protected staging target and feed `pg_restore` from that file; avoid retaining the entire encrypted and decrypted dump in Python memory. Keep this separate from Section 82, which concerns the restore-drill runner's unbounded memory path.

**Assessment:** High-priority confidentiality and restore-concurrency gap in the tenant restore helper. The source writes decrypted database contents into a shared persistent backup volume without explicitly restrictive file creation or crash-residue recovery. Whether another service process can read a particular file depends on runtime UID/GID, umask and filesystem permissions; those live attributes were not inspected. A hard process termination can bypass the `finally` cleanup, and concurrent restore operations have no operation-specific staging isolation in the reviewed path.

**Boundary:** static source/configuration review only. No encrypted artifact, plaintext dump, restore, volume, database, credential, migration or production state was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.



## 86. Manual backup and restore operations are acknowledged through process-local background tasks, not durable work records

**Source reviewed:** `backend/control_plane/api/routers/fleet_ops.py` (`trigger_manual_backup_snapshot`, `restore_tenant_from_snapshot`).

Static source review only. No endpoint was invoked, no background task was started, and no backup, tenant database, credential or production state was accessed or changed.

### 86.1 A successful queued response does not establish durable execution or recoverability

Both manual operations register an in-process callable through FastAPI `BackgroundTasks` and then return a success response stating that the snapshot or restoration was queued. The backup task calls `_dump_and_encrypt`; the restore task attempts the mandatory safety snapshot and then calls `restore_encrypted_backup`. Completion and failure are recorded as audit-log events from inside the task, but the reviewed path does not persist a durable task/operation record with a recoverable payload, lease, retry policy or startup reconciliation.

FastAPI background tasks execute within the application process after the response is sent; they are not a durable queue. If the serving process/container exits after the client receives the queued response but before the task finishes, the process-local callable is not automatically recovered by another worker. A restore may therefore be acknowledged without a durable mechanism to resume or conclusively reconcile the operation. The pre-restore session termination ordering documented in Section 84 makes this especially consequential: a process interruption after termination can leave the tenant disconnected while the queued restore work is lost or its outcome remains ambiguous.

The control-plane audit event written by the request handler records that work was queued; it is not proof that the task started, completed, or can be resumed. A later completion/failure audit event is best-effort evidence, and its absence cannot distinguish a task that never ran from one interrupted before it could record its outcome. The same durability limitation applies to manual backup creation, where the caller can receive a queued response without a durable retry/reconciliation path.

This finding is about privileged backup/restore task execution durability. It is distinct from Section 69's generic webhook processing path, Section 84's ordering of session termination versus safety snapshot, and Section 75's unresolved safety-snapshot helper import.

### 86.2 Required remediation and acceptance evidence

1. Persist an operation record before acknowledging the request, with a unique operation ID, tenant/database identity, immutable snapshot reference, requested action, actor, timestamps and explicit state.
2. Dispatch work through a durable queue or database-backed worker/outbox pattern with leases, bounded retries, idempotent state transitions and startup recovery. Do not treat FastAPI `BackgroundTasks` as the system of record for destructive restore work.
3. Return the operation ID and a status resource; distinguish accepted, running, safety-snapshot-verified, restoring, completed, failed and outcome-unknown states. Keep audit events correlated to that operation ID.
4. On worker restart or lease expiry, reconcile the database and snapshot state before retrying. Never blindly replay a restore whose destructive phase may have started; require an explicit recovery decision when the outcome cannot be established.
5. Add deterministic tests that terminate or simulate loss of the worker after acceptance, during backup, after safety snapshot, after session drain, and during restore. Prove that every operation is either resumed safely or surfaced as an explicit recoverable/unknown state, with no false completed status.
6. Keep restore-task recovery tests separate from the safety-snapshot ordering tests in Section 84 and the helper existence/decryptability tests in Section 75.

**Assessment:** High-priority backup/restore operational durability gap. The endpoints can acknowledge work that is held only in the serving process, without a durable task state or automatic recovery mechanism in the reviewed implementation. No claim is made that a production task has been lost; actual exposure depends on process lifecycle and whether an external supervisor/operator provides recovery outside the reviewed code.

**Boundary:** static source review only. No endpoint, task, backup, tenant database, credential, migration or production state was exercised or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 87. Tenant backup creation buffers the full plaintext dump and encrypted artifact in process memory

**Source reviewed:** `backend/scripts/backup_service.py` (`_dump_and_encrypt`).

Static source review only. No backup command was run, no database was queried, and no backup artifact, credential or production resource was accessed or changed.

### 87.1 Backup memory consumption grows with the complete tenant database

The tenant backup helper invokes `pg_dump` using `subprocess.run(..., capture_output=True, check=True)`. This captures the complete custom-format dump in `proc.stdout` as a Python bytes object. The helper then calls Fernet `encrypt(proc.stdout)`, creating a second complete in-memory encrypted bytes object before writing it to the pending file.

During encryption/publication, the process therefore retains at least the complete plaintext dump and complete ciphertext, in addition to Python/runtime and cryptographic working memory. Peak memory scales with tenant dump size rather than a configured streaming buffer. A sufficiently large tenant backup can exhaust the worker/container memory or be OOM-killed, preventing backup completion and potentially affecting other workloads sharing the same process/container resource limits. No actual size threshold or memory limit was measured in this static review.

This is the backup-creation counterpart to Section 82's separate restore-drill buffering issue. The host-level `deployments/backup-postgres.sh` uses a pipeline from `pg_dump` through GPG to a file, illustrating a streaming approach in a different backup path; it does not make the Python tenant backup helper streaming.

### 87.2 Required remediation and acceptance evidence

1. Replace `capture_output=True` with a streaming pipeline or bounded temporary-file flow so `pg_dump` output is not retained as one complete Python bytes object.
2. Use a streaming authenticated-encryption format or chunked envelope design with explicit versioning, nonce/metadata handling, and verified end-of-stream authentication; do not assume Fernet's whole-message API can be made streaming by merely iterating over its input.
3. Publish the encrypted artifact only after the dump process exits successfully, encryption finalization/authentication succeeds, and the completed artifact is verified. Preserve atomic publication and clean up operation-owned partial files on every failure path.
4. Bound subprocess diagnostics and avoid retaining potentially unbounded stdout/stderr alongside dump data.
5. Add synthetic large-database tests that measure peak resident memory against a defined bound, inject pg_dump failure and encryption/write failure, and prove no incomplete artifact is exposed as a completed backup.
6. Document the supported maximum tenant backup size and required worker memory until a bounded streaming implementation is deployed.

**Assessment:** High-priority backup availability and scalability gap. The current Python tenant backup path holds the complete dump and encrypted output in memory, so its resource use grows with tenant database size and can prevent backup completion under constrained worker memory. Actual failure thresholds depend on tenant size and runtime limits and were not measured.

**Boundary:** static source review only. No backup, database, credential, migration, tenant record or production state was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 88. Tenant backup artifact is published before its checksum sidecar, leaving a crash-visible incomplete backup set

**Sources reviewed:**
- `backend/scripts/backup_service.py` (`_dump_and_encrypt`)
- `backend/scripts/restore_drill.py` (`verify_backup_checksum`)

Static source review only. No backup was created, read, decrypted or verified; no database, credential or production resource was accessed or changed.

### 88.1 The artifact and its verification sidecar are not published as one completed unit

`_dump_and_encrypt()` writes encrypted bytes to a temporary file and atomically replaces the final `.dump.enc` path. Only after that final artifact is visible does it calculate the SHA-256 digest and write the `.dump.enc.sha256` sidecar directly to its final path.

This creates a publication interval in which the final encrypted artifact exists but the checksum sidecar does not. A process/container termination in that interval, or a sidecar write/permission/storage failure, leaves an apparently published backup artifact without the companion verification file. The sidecar itself is not written through a temporary file plus atomic rename, so an interrupted sidecar write can also leave a partial sidecar.

The restore-drill verifier explicitly returns `False` when the sidecar is absent, so such an artifact cannot pass that checksum gate even if Fernet decryption would otherwise authenticate it. Other directory consumers can still observe/count the final `.dump.enc` file before the backup set is complete; for example, the fleet overview counts encrypted snapshot filenames without checking for a matching sidecar. This is a publication/completeness gap, not a claim that an artifact with a missing sidecar is necessarily cryptographically corrupted.

The host-level backup script uses a different publication model: it creates a staging directory, writes and verifies checksum manifests, and only then renames the completed directory into the final backup namespace. That does not repair the Python tenant backup helper.

### 88.2 Required remediation and acceptance evidence

1. Treat the encrypted artifact and checksum/manifest as a single backup set. Write both under an operation-specific staging name or directory.
2. Write the sidecar/manifest through a temporary file, flush and close it, verify it against the completed encrypted artifact, and publish the complete set atomically (for example, by renaming a completed staging directory).
3. Ensure consumers enumerate only completed sets with a valid completion manifest; do not infer backup readiness from the presence of a `.dump.enc` filename alone.
4. Add startup reconciliation for abandoned staging sets and incomplete final artifacts. Quarantine or safely remove only operation-owned incomplete outputs; never silently bless them as completed backups.
5. Add deterministic failure-injection tests for process interruption after artifact publication, sidecar creation/write failure, checksum mismatch, and concurrent enumeration. Assert that no incomplete set is advertised as available or certified.
6. Keep checksum-sidecar completeness separate from Fernet authentication: both checks may be useful, but neither should be silently substituted for the other.

**Assessment:** High-priority backup publication and recovery-evidence integrity gap. The Python helper exposes the encrypted artifact before its checksum sidecar is safely published, so interruption can leave an incomplete backup set that consumers may count while the restore-drill checksum gate rejects it. No evidence was gathered that this interruption has occurred in a deployed environment.

**Boundary:** static source review only. No backup, checksum, decryption, database, credential, migration or production state was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 89. Manual restore endpoint does not bind the selected snapshot filename to the requested tenant

**Sources reviewed:**
- `backend/control_plane/api/routers/fleet_ops.py` (`list_tenant_backup_snapshots`, `restore_tenant_from_snapshot`)
- `backend/scripts/restore_tenant.py` (`restore_encrypted_backup`)

Static source review only. No restore was requested or executed; no backup artifact, tenant key, database or production resource was accessed.

### 89.1 Listing is tenant-filtered, but restore selection is only directory-scoped

The backup listing endpoint constructs its results using the requested tenant's database-name prefix (`{tenant.db_name}_*.dump.enc`). The restore endpoint does not apply that same predicate. It reduces the caller-supplied `filename` to `Path(filename).name`, joins it to the shared relative `backups` directory, and checks only whether that path exists.

The endpoint then supplies the selected tenant's stored backup encryption key to `restore_encrypted_backup()` and targets that tenant's database. It does not verify that the selected filename belongs to the tenant, nor does the artifact carry a checked tenant/database identity binding in this path.

Fernet authentication should reject an artifact encrypted with a different tenant key, so this review does not claim that a cross-tenant artifact can normally be decrypted or that patient data was exposed. However, tenant ownership is not enforced at the selection boundary; behavior depends on cryptographic key separation remaining correct and the failure is deferred to the asynchronous restore task. The endpoint also terminates target-database sessions before that task runs, so an invalid selection can still trigger the session-disruption path before artifact authentication fails. The pre-restore safety-snapshot helper issue in Section 75 is a separate earlier failure in the current task path and is not treated as a substitute for correct snapshot authorization.

### 89.2 Required remediation and acceptance evidence

1. Resolve a snapshot through a server-side tenant-scoped inventory/manifest, not an arbitrary filename in a shared directory.
2. Enforce the expected tenant/database identity at restore time; filename prefix checking is a minimum defense, not a substitute for a signed or authenticated manifest binding tenant ID, database identity, artifact digest and backup operation ID.
3. Verify manifest, checksum and Fernet authentication before terminating target-database sessions or scheduling destructive restore work.
4. Reject path traversal, symlink escapes and non-regular files; resolve and validate paths against a configured backup root.
5. Add negative tests: tenant A cannot select tenant B's snapshot; mismatched manifest identity is rejected; missing/corrupt sidecar is rejected; invalid artifact causes no session termination and no restore task registration.
6. Record the selected artifact identity and verification outcome in a durable restore operation record before acknowledging work.

**Assessment:** Medium, conditional cross-tenant restore-selection and avoidable service-disruption risk. Current Fernet key authentication is a useful later barrier, but it does not replace tenant-bound artifact selection and preflight validation.

**Boundary:** static source review only. No restore, backup, decryption, database, tenant key, migration or production state was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 90. Restore failure can leave the live tenant database partially replaced

**Source reviewed:** `backend/scripts/restore_tenant.py` (`restore_encrypted_backup`).

Static source review only. No restore command was run, no tenant database or backup artifact was accessed, and no credential or production resource was used.

### 90.1 The restore applies destructive changes directly to the target database without an atomic boundary

The restore helper decrypts the selected dump and invokes `pg_restore` with `--clean` and `--if-exists` against the existing `target_db_name`. The command does not use `--single-transaction`, does not restore into a fresh isolated database for validation, and does not perform a controlled database swap after validation.

The subprocess is checked only after `pg_restore` exits. A non-zero exit code is then converted into a `RuntimeError`, but that error check does not undo SQL statements that were already applied. In the absence of `--exit-on-error`, `pg_restore` can continue processing remaining archive items after an individual restore error; without a transaction boundary, successful earlier and later operations may remain committed even though the helper ultimately reports failure.

Because `--clean` removes existing objects before recreating them, a failed restore can leave the live tenant database in a mixed or incomplete state. The code's later exception is an outcome signal, not a rollback. The pre-restore safety-snapshot attempt in the control-plane task is not an automatic rollback mechanism; in the reviewed path that helper import is separately unresolved as recorded in Section 75.

This is distinct from Section 76's restore-drill database-selection/drop behavior, Section 84's session-termination ordering, and Section 75's missing safety-snapshot helper. This finding concerns the mutation boundary inside the regular tenant restore helper.

### 90.2 Required remediation and acceptance evidence

1. Prefer restoring into a newly created, uniquely named, isolated database using the tenant's validated backup identity; run schema, migration-version, critical-table, row-count and application-level integrity checks before any promotion.
2. Promote only through a controlled, recoverable cutover that preserves the original database until the replacement is verified. Record the old/new database identities and operation ID, and provide a documented rollback path.
3. If an isolated restore-and-swap design is not feasible, explicitly evaluate `pg_restore --single-transaction` and `--exit-on-error` for the supported archive/size profile. Document operational limits rather than assuming either flag alone provides a complete recovery design.
4. Never report restore success based only on process completion; persist per-stage outcomes and require post-restore validation before the tenant is returned to service.
5. Add disposable PostgreSQL integration tests that inject an object-restore failure after destructive cleanup and prove the original tenant database remains available and unchanged, or that the system retains a verified rollback target and exposes a recoverable maintenance state.
6. Test process termination during restore, validation failure, cutover failure and rollback failure. Ensure each state is explicit and that no partially restored database is silently promoted as healthy.

**Assessment:** High-priority tenant data availability and restore-integrity risk. The current helper can modify the live tenant database before discovering and reporting a restore error; no atomic rollback or isolated promotion boundary is present in the inspected command. No evidence was gathered that a production restore has failed or left a tenant database partial.

**Boundary:** static source review only. No restore, backup, database, credential, migration or production state was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 91. Restore drill reports pg_restore duration as end-to-end RTO

**Source reviewed:** `backend/scripts/restore_drill.py` (`run_restore_drill`, RTO timer and report construction).

Static source review only. No restore drill was run, no backup was opened, and no database, credential, patient record or production resource was accessed or changed.

### 91.1 The RTO timer excludes recovery work before and after pg_restore

The helper decrypts the complete backup before creating the drill database. It then creates the database and prepares the restore command. Only immediately before `subprocess.run(restore_cmd, ...)` does it start `restore_start_t`; it stops the timer as soon as the `pg_restore` subprocess returns. The resulting elapsed value is emitted as `measured_rto_seconds` and compared with `max_acceptable_rto_seconds` to set `sla_rto_passed`.

Consequently, the reported duration excludes at least:
- backup artifact checksum verification and decryption;
- drill database creation and connection/setup;
- post-restore catalog inspection, critical-table checks and table-count attempts;
- the RPO query attempts and final certification decision;
- any controlled promotion/cutover or application readiness check (none is part of this drill path).

The measured value is therefore the duration of one restore command, not the elapsed time from recovery initiation to a verified, usable tenant service. A slow decryption, database provisioning step or post-restore validation can add substantial recovery time without affecting the reported RTO. The report can consequently mark the RTO threshold as met even though the end-to-end recovery objective has not been measured.

This is separate from Section 76's ignored `pg_restore` exit status, Sections 81–83's RPO and integrity-certification gaps, and Section 90's live-database mutation boundary. Those findings concern whether restore success is trustworthy and safe; this finding concerns the scope of the clock used to claim an RTO result.

### 91.2 Required remediation and acceptance evidence

1. Define the RTO start and stop events explicitly in the disaster-recovery policy. For a service-recovery objective, start at the declared recovery trigger/operation acceptance and stop only when the restored tenant has passed required integrity checks and an application-level readiness probe.
2. Record phase timings separately (artifact verification, decryption, database provisioning, restore, integrity validation and controlled cutover/readiness) while also calculating one end-to-end elapsed recovery duration from the defined start and stop events.
3. Include the timing boundaries and phase outcomes in the report so an operator can distinguish command duration from service-recovery duration. Do not label the isolated `pg_restore` duration as the complete RTO.
4. Make the RTO pass predicate use the end-to-end duration and the configured threshold. A missing phase, failed validation or absent readiness confirmation must not produce a passing RTO result.
5. Add deterministic tests with injected delays/failures before restore, during restore and during post-restore validation. Prove that all elapsed recovery work contributes to the end-to-end metric and that certification cannot pass before readiness is established.
6. Keep any separate database-command performance metric, if useful, clearly named (for example, `pg_restore_duration_seconds`) and do not substitute it for the service-level RTO.

**Assessment:** High-priority disaster-recovery measurement and SLA-evidence gap. The current report's RTO value covers only the `pg_restore` subprocess and omits other required recovery phases. No actual recovery duration or production SLA breach was measured in this static review.

**Boundary:** static source review only. No restore, backup, database, credential, migration, tenant record or production state was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.



## 92. Discovery request purpose is not enforced by the source privacy decision

**Source reviewed:** `backend/domains/federation/router.py` (`discover_and_aggregate_patient_across_branches`, source-side `_fetch_branch_data` closure); `backend/domains/privacy/runtime.py` (`evaluate_tenant_data_use` and `evaluate_tenant_data_use_for_patients`).

Static source review only. No discovery request was sent, no patient record was read, and no database, credential, migration or production resource was accessed or changed.

### 92.1 Caller-declared purpose is recorded but does not constrain source disclosure

The discovery endpoint accepts a caller-supplied `purpose` string (3–255 characters). It explicitly rejects a small set of emergency-purpose labels, but otherwise does not validate the value against a supported-purpose registry or bind it to a source-approved capability.

Inside each source tenant, the disclosure decision calls `evaluate_tenant_data_use` with the fixed data-use point `federation.patient.discover`. That evaluator resolves the purpose code from the active source tenant's privacy policy using the data-use point; it does not receive the endpoint's caller-supplied `purpose` value. The source `FederationTransferLog` stores the caller-supplied string as `purpose`, so the audit record can say (for example) one purpose while the actual authorization decision was made under the policy mapping for `federation.patient.discover`.

The caller-supplied purpose is also used to decide whether to mint a continuity-of-care import receipt. That check occurs after the discovery response has already been assembled; it does not prevent demographic disclosure for a non-continuity label. Therefore a request labelled with a different non-emergency purpose can still receive the same source-authorized discovery demographics, while merely not receiving an import receipt.

This finding does **not** establish that source consent or source sharing policy is bypassed: the source still checks its active tenant privacy policy, sharing mode, patient sharing opt-out and demographic-sharing setting. The gap is that the request's declared purpose is not part of that source-side authorization decision, so purpose limitation and the meaning of the stored purpose audit field are not reliably enforced.

This is distinct from Section 73's owner-tenant active-state invariant, Section 74's PostgreSQL role boundary, and the explicitly documented missing human actor assertion / remote emergency authorization limitation in PR #19. It concerns the mismatch between the caller-declared purpose and the purpose actually evaluated and recorded for ordinary discovery.

### 92.2 Required remediation and acceptance evidence

1. Define a closed, versioned set of federation purposes and reject unknown or unsupported values before any source database session is opened.
2. Bind each permitted purpose to an explicit source-side data-use point, consent purpose, permitted data categories and operation scope. Do not use one generic discovery data-use point for semantically different purposes.
3. Pass the validated purpose/scope into the source privacy evaluator and require the source policy/consent decision to authorize that exact purpose before reading or returning patient demographics or allergies.
4. Record both the validated purpose code and the source policy/consent decision identifier in the source transfer audit. Ensure the audit cannot record a caller label that differs from the purpose actually authorized.
5. Add tests proving that an unsupported purpose is rejected before source access; a valid but unauthorized purpose returns no patient data; a permitted purpose returns only its allowed data categories; and audit records match the evaluated purpose. Include continuity-of-care and at least one non-continuity purpose.
6. Keep remote emergency federation disabled until the separately required node-bound scope and verifiable human-actor assertion protocol is implemented and independently reviewed.

**Assessment:** High-priority privacy-purpose enforcement and audit-integrity gap for federated discovery. Static code establishes that the request purpose is not passed into the source privacy evaluator; it does not establish that any patient data has been disclosed under an improper purpose in production.

**Boundary:** static source review only. No federation request, patient record, backup, database, credential, migration or production state was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 93. Missing or non-enforcing source privacy configuration permits federated disclosure

**Source reviewed:** `backend/domains/federation/router.py` (`_get_branch_policy`, `_fetch_branch_data`); `backend/domains/policies/models.py` (`HospitalPolicySetting` defaults); `backend/domains/privacy/runtime.py` (`_active_consent_revision`, `evaluate_tenant_data_use_for_patients`); `backend/domains/privacy/decision_engine.py` (`evaluate_data_use`, `_result`); `backend/domains/privacy/models.py` (`PrivacyPolicyRevision` activation constraints).

Static source review only. No federation request was sent, no patient record was read, and no database, credential, migration or production resource was accessed or changed.

### 93.1 Source-side configuration has permissive fallback states

The federation source helper `_get_branch_policy` creates and flushes a new `HospitalPolicySetting` when no row exists. The model defaults that new row to `FULL_MESH`, `federation_share_demographics=True` and `federation_share_allergies=True`. Thus absence of a hospital federation policy row does not suppress sharing; it materializes the most permissive sharing mode and data-category flags.

Separately, `_active_consent_revision` returns `None` when the source tenant has no active CONSENT revision. `evaluate_tenant_data_use_for_patients` then calls `evaluate_data_use(None, ..., mode="OFF")`, which returns `allowed=True` with reason `policy_off`. No consent record is required in this branch.

A configured active revision is not sufficient by itself to guarantee enforcement. The decision engine explicitly treats `OFF` as allowed. In `AUDIT_ONLY`, a decision that would otherwise deny is converted to `allowed=True` with `would_deny=True`; the federation caller therefore still receives data while the denial is only recorded for audit. The database constraints permit an active approved revision in either `AUDIT_ONLY` or `ENFORCE` mode and do not establish that federation disclosure requires `ENFORCE`.

The discovery path subsequently checks source patient activity, patient-level network-sharing opt-out, source sharing mode, ABHA/phone match and the returned decision's `allowed` flag. Those checks are useful, but they do not compensate for the permissive missing-policy and non-enforcing-mode behavior. With no hospital policy row and no active consent revision, the code path defaults to FULL_MESH sharing and an allowed consent decision. With an active AUDIT_ONLY revision, would-deny consent outcomes are also allowed to proceed.

This is distinct from Section 92: Section 92 concerns the caller-declared purpose not being bound to the source evaluator. Section 93 concerns whether the source evaluator is actually configured to enforce any consent decision at all. It is also distinct from Section 73's active tenant registry/node lifecycle check.

### 93.2 Required remediation and acceptance evidence

1. Make absence of a source federation policy row fail closed. Do not create a permissive FULL_MESH row as a read/discovery side effect; require an explicit, approved sharing configuration before source disclosure.
2. Require an active, approved CONSENT policy in `ENFORCE` mode for federation disclosure. Missing, invalid, inactive, OFF or AUDIT_ONLY policy state must deny remote disclosure (or keep the endpoint disabled) rather than treating the result as allowed.
3. Separate audit-only simulation from the authorization decision exposed to the federation route. An audit-only `would_deny` result must not be interpreted as permission to disclose patient data.
4. Add deployment/provisioning readiness checks that prove each enabled source tenant has an approved, valid consent policy with complete data-use-point coverage and enforcement mode ENFORCE, plus an explicit non-permissive federation sharing policy.
5. Add tests for: absent hospital policy row; absent active consent revision; invalid policy document; OFF; AUDIT_ONLY with missing consent; ENFORCE with missing/withdrawn/expired consent; and explicit valid consent. Assert that no denied or unconfigured case returns demographics or allergies.
6. Add an operational report that identifies tenants whose federation is disabled because policy prerequisites are missing. Do not silently auto-enable sharing during discovery.

**Assessment:** High-priority privacy enforcement and default-deny gap. Static code establishes permissive behavior for missing hospital federation settings and missing/non-enforcing consent policy states. It does not establish that any particular production tenant is currently in one of those states or that a production disclosure occurred.

**Boundary:** static source review only. No federation request, patient record, database, credential, migration or production state was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 94. Federated import audit omits the authenticated requesting-node identity

**Source reviewed:** `backend/domains/federation/router.py` (discovery source-log creation and `import_federated_patient_locally`); `backend/domains/federation/models.py` (`FederationTransferLog`); `backend/control_plane/models.py` (`FederatedDiscoveryReceipt`).

Static source review only. No federation request was sent, no patient record was read, and no database, credential, migration or production resource was accessed or changed.

### 94.1 Discovery captures the credential identity, but the later import audit drops that binding

During discovery, the source tenant's `FederationTransferLog` row records `requesting_node_id`, `requesting_key_prefix` and `requesting_branch_code` from the authenticated `calling_node`, alongside the patient and caller-declared purpose. The server-issued discovery receipt separately stores `calling_node_id` and is checked at import for node existence and active status.

The import route then reloads and revalidates the source patient and policy, but its source-side `FederationTransferLog` insert sets only `requesting_branch_code`, the patient ID, a hashed-MRN-derived operation label and the fixed purpose `CONTINUITY_OF_CARE_IMPORT_REQUESTED`. It does not populate the available `requesting_node_id` or `requesting_key_prefix` fields, nor does it persist the receipt identity/hash or a correlation ID linking this import audit row to the receipt and discovery event. The model has no human-actor field either, even though the destination route has an authenticated `current_user`.

Consequently, the source tenant's audit trail can record that a branch-labelled import was requested, but cannot independently identify which authenticated federation node/key credential performed that import or correlate the import to the exact discovery receipt. If multiple nodes or credentials can act for the same branch over time, branch code alone is not a reliable credential-level attribution. The separate discovery log may show a credential used earlier, but the import event itself is not bound to it.

This is an audit attribution and traceability gap, not evidence that receipt validation is bypassed or that an unauthorized import occurred. The import route does validate the receipt's calling node and active state, and rechecks source sharing/privacy conditions. This finding is distinct from Section 92's purpose-enforcement mismatch and Section 93's permissive privacy-policy defaults; it concerns what identity evidence is retained for the import operation after those checks.

### 94.2 Required remediation and acceptance evidence

1. Populate `requesting_node_id`, `requesting_key_prefix` and `requesting_branch_code` from the already-validated receipt/calling node on every source-side import audit row; do not trust caller-supplied identity fields.
2. Persist a non-secret receipt identifier or one-way receipt fingerprint and a stable import operation/correlation ID so discovery, authorization and import events can be joined without storing the bearer token.
3. Define the human-actor attribution model for cross-tenant operations. Where a verifiable destination-user assertion is not available, record that the human actor is unknown rather than implying branch or API-key identity proves a person acted.
4. Ensure audit rows distinguish import requested, destination commit completed, idempotent-existing-patient outcome and failure/unknown outcome. Do not treat the source-side REQUESTED event as proof that the destination clone committed.
5. Add tests proving import audit rows preserve the receipt-bound node ID/key prefix and correlation identifier, cannot be spoofed through payload fields, and accurately represent idempotent and failed destination outcomes.

**Assessment:** Medium-priority federation audit attribution and incident-investigation gap. Static code establishes that discovery logs credential identity while import logs only the requesting branch. It does not establish that any particular import was unauthorized or that an incident has occurred.

**Boundary:** static source review only. No federation request, patient record, database, credential, migration or production state was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.

## 95. Federation transfer-log immutability is enforced only by an ORM flush listener

**Source reviewed:** `backend/domains/federation/models.py` (`FederationTransferLog`, `_protect_federation_transfer_logs`); `backend/domains/federation/router.py` (discovery and import audit writes).

Static source review only. No federation request was sent, no patient record was read, and no database, credential, migration or production resource was accessed or changed.

### 95.1 The immutability guard is scoped to SQLAlchemy unit-of-work flushes

`FederationTransferLog` is described as an immutable audit log. Its protection is implemented by a global SQLAlchemy `Session` `before_flush` listener. The listener rejects dirty mapped `FederationTransferLog` instances and rejects instances placed in `session.deleted`. It also sanitizes ABHA identifiers when new mapped log instances are flushed.

That listener is useful for ordinary ORM unit-of-work changes, but it is not a PostgreSQL constraint or trigger. SQLAlchemy ORM bulk DML and Core/raw SQL execute statements without placing each affected mapped instance in the session's `dirty`/`deleted` collections and do not invoke this `before_flush` object-level guard for those rows. The model therefore does not establish database-level append-only enforcement for the transfer-log table. A database principal able to issue UPDATE or DELETE against the table can bypass this Python listener.

The reviewed router writes transfer rows through `branch_db.add(...)` followed by `branch_db.commit()` for discovery and `source_db.add(...)` followed by `source_db.commit()` for import. Those ordinary ORM inserts are covered by the listener's insertion-time ABHA sanitization. The import path's reduced credential attribution is separately documented in Section 94 and is not repeated here.

The model source itself defines no database trigger or privilege boundary for `federation_transfer_logs`. The repository migration/trigger definition was not conclusively enumerated in this review, so this section does not claim that no external or migration-installed trigger exists in every deployed database. The actionable evidence is that the application model's stated immutability guarantee is implemented only at the ORM flush layer, and the deployment's database-level enforcement has not been demonstrated by the reviewed contract.

### 95.2 Retention and audit correlation review

The reviewed federation model and router contain no application-managed retention or archival operation for `FederationTransferLog`. This means no repository-managed retention lifecycle was identified in the reviewed paths; it does not prove that logs are retained forever or that an external database/backup lifecycle policy does not exist.

Discovery writes one source-side log row for each source branch result. Import writes a separate source-side `CONTINUITY_OF_CARE_IMPORT_REQUESTED` row. The import row's missing validated node/key identity and receipt/correlation binding are already documented in Section 94; this section does not count that same attribution gap again. The separate events currently have no common operation/correlation field in the `FederationTransferLog` model, but Section 94 captures the specific import-to-receipt traceability deficiency and should own its remediation.

### 95.3 Required remediation and acceptance evidence

1. Enforce append-only behavior at the PostgreSQL boundary for `federation_transfer_logs`: deny UPDATE and DELETE to the runtime role and/or install a database trigger that rejects mutation. Ensure only a separately controlled retention/archival principal can perform any approved lifecycle operation.
2. Add disposable PostgreSQL tests that attempt ORM mutation, SQLAlchemy bulk UPDATE/DELETE, Core statements and direct SQL using the runtime role; every mutation path must be denied by the database, not merely by a Python exception.
3. Include the transfer-log table in the catalog proof: trigger definitions/enabled state, table and column grants, role membership, ownership and effective runtime privileges. Verify that the runtime principal cannot disable or bypass the guard.
4. Define an approved retention and archival schedule, legal-hold behavior, access controls and evidence of deletion/archival. Until that policy is approved, do not introduce an ad hoc cleanup job.
5. Keep the Section 94 import receipt/node/correlation remediation as a separate acceptance item; do not treat a shared correlation ID as a substitute for immutable storage.

**Assessment:** Medium-priority audit-integrity control gap. The Python source proves that immutability checks are attached to ORM flushes, not enforced by the model at the database boundary. Actual deployed trigger/privilege state and any external retention policy remain unverified. This is not evidence that a transfer-log row has been altered or deleted.

**Boundary:** static source review only. No federation request, patient record, database, credential, migration or production state was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.
## 96. Discovery receipts are replayable until expiry and expired-row cleanup is opportunistic

**Source reviewed:** `backend/control_plane/models.py` (`FederatedDiscoveryReceipt`); `backend/domains/federation/router.py` (discovery receipt issuance, expiry cleanup and `import_federated_patient_locally`).

Static source review only. No federation request was sent, no patient record was read, and no database, credential, migration or production resource was accessed or changed.

### 96.1 Receipt validation enforces expiry, but does not consume the bearer capability

Discovery issues a random bearer receipt, stores only its SHA-256 token hash in the control-plane database and sets `expires_at` to two minutes after issuance. Import hashes the supplied token, retrieves the receipt, verifies destination branch, expiry, response-summary digest, active calling node, selector digest, current pointer snapshot and exact source pointer. It also revalidates source patient activity, sharing policy, consent decision and current demographic values before cloning. These are meaningful validation controls; this finding does not claim that the receipt can be used after expiry or that source policy checks are skipped.

The receipt model has no consumed/imported/revoked state, nonce-use record or import-operation identifier. The import route does not delete or mark the receipt used after a successful destination commit or an idempotent-existing-patient return. Consequently, the same valid bearer receipt remains acceptable for repeated import requests during its two-minute validity window, provided the caller still has the destination `patients:write` permission and all source/index checks continue to pass.

The destination's identity-based existing-patient lookup reduces ordinary duplicate creation, but it is not one-time receipt consumption. Replays still repeat control-plane pointer validation, source-tenant patient/policy reads and source-side `CONTINUITY_OF_CARE_IMPORT_REQUESTED` audit writes. The source audit row is committed before the destination patient commit, so a replay or failed destination commit can leave multiple REQUESTED events without a corresponding committed-import outcome. The destination route also returns an existing patient without consuming the receipt.

This is a bounded replay/idempotency and audit-noise gap, not evidence of authorization bypass: the bearer is short-lived, destination-bound, tied to the authenticated calling node and current pointer snapshot, and each attempt rechecks source policy and destination permission. It is distinct from Section 94's missing import credential attribution and Section 19's broader cross-database clone recovery/idempotency concerns; the specific additional point here is that the server-issued capability itself is not one-time.

### 96.2 Expired receipt cleanup is coupled to future discovery traffic

The only application cleanup found in the reviewed router is a bulk delete of receipts whose `expires_at` is at or before the current time, executed at the beginning of each discovery request. The import route rejects expired receipts but does not delete them. No scheduled cleanup worker, periodic task or bounded retention mechanism for this table was identified in the reviewed model/router paths.

Thus expired receipt rows are reclaimed only when another discovery request later runs the cleanup statement. If discovery traffic stops, expired rows remain in the control-plane table; the repository does not provide a time-bounded cleanup guarantee. The expiry index supports the delete predicate, but an index does not itself remove expired rows. This is a storage-lifecycle observation, not a claim that expired receipts remain usable: import still checks `expires_at`.

### 96.3 Required remediation and acceptance evidence

1. Define receipt semantics explicitly. If import is intended to be one-time, atomically claim/consume the receipt with a conditional state transition or unique import-operation record before allowing the cross-database workflow to proceed. Do not rely on a read-then-delete sequence that permits concurrent replay.
2. Preserve recoverability across the source/destination transaction boundary: persist operation state and distinguish claimed, source-authorized, destination-committed, idempotent-existing and failed/unknown outcomes. A consumed receipt must not strand a valid import after a transient destination failure; define a safe retry/recovery rule.
3. Add concurrency tests that submit the same receipt in parallel and sequentially, including destination commit failure, existing-patient return, source-policy change, pointer change, expiry boundary and node revocation. Assert one logical import operation and accurate audit outcomes.
4. Move expired-receipt reclamation to a durable scheduled cleanup/retention process with bounded batches, observability and failure/restart tests. Keep import-time expiry validation authoritative regardless of cleanup lag.
5. Extend the disposable PostgreSQL catalog/integration proof to verify receipt state transitions, conditional claim uniqueness and cleanup behavior without touching non-disposable databases.

**Assessment:** Medium-priority capability lifecycle and audit-integrity gap. The two-minute expiry and extensive source revalidation materially limit exposure, but the same receipt is not consumed after use and cleanup is request-driven rather than scheduled. Static review does not establish that replay caused duplicate patient records or that control-plane storage is currently growing without bound.

**Boundary:** static source review only. No federation request, patient record, database, credential, migration or production state was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.

## 97. Denied pointer publication exits before stale discovery-index entries are purged

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/federation/router.py` (`sync_patient_pointer`); `backend/domains/patients/router.py` (`update_patient`, `deactivate_patient`, explicit publish endpoint); `backend/control_plane/models.py` (`GlobalPatientPointer`).

Static source review only. No federation request was sent, no patient record was read, and no database, credential, migration or production resource was accessed or changed.

### 97.1 Privacy denial returns before the existing pointer is located or removed

When a tenant database session is supplied, `sync_patient_pointer` first evaluates `federation.patient.publish_pointer`. If that decision is denied, the function immediately returns `False`. The control-plane pointer lookup and the later patient-level opt-out / hospital `ISOLATED_SILO` purge branches occur only after this early return.

The patient update route commits changes to the tenant patient and then calls `sync_patient_pointer`, but does not inspect its boolean return value. Therefore, when a previously indexed patient's updated state causes the publication decision to be denied, the update route can return the updated patient successfully while leaving the pre-existing `GlobalPatientPointer` untouched. The same ordering means a denied publication attempt does not itself purge a pointer when a patient has opted out or the hospital has moved to an isolated policy, if the publication decision denies first.

This is a concrete stale-index lifecycle gap: the source record can move into a state where publication is denied while the central index still retains its prior phone hash, ABHA value, branch code and MRN locator. Deactivation has a separate explicit pointer deletion path, but the denied-sync path does not.

### 97.2 Existing source-side checks limit the demonstrated impact

Discovery does not return patient demographics solely because a pointer matched. It resolves an active tenant registry and re-reads the source patient, requires the patient to remain active and opted in, checks source sharing mode and re-evaluates the source data-use decision before returning demographic data. Import independently revalidates the source patient and sharing decision. Those checks reduce the risk that a stale pointer alone causes a disclosure.

The demonstrated concern is therefore stale central-index metadata, unnecessary candidate routing and incomplete privacy-state cleanup—not proof that a denied source record is disclosed, that a privacy decision is bypassed, or that patient data has been exposed. This finding is distinct from Section 93's evaluator/default behavior: it concerns the order and outcome of pointer lifecycle handling after a decision has already denied publication.

### 97.3 Required remediation and acceptance evidence

1. Resolve the existing pointer before evaluating publication eligibility. On an explicit patient opt-out, isolated-silo policy or denied publication decision, remove the pointer (or mark it non-discoverable) and commit the cleanup with a defined retry/reconciliation strategy.
2. Make pointer synchronization return a typed outcome such as published, removed, unchanged or denied-with-cleanup, and require callers—especially patient update and explicit publish—to handle it rather than silently ignoring `False`.
3. Define the cross-database failure contract. A tenant update and control-plane pointer deletion cannot be made atomic by the current two-session flow; record a durable cleanup/reconciliation task or outbox event so a control-plane outage cannot leave stale identifiers indefinitely.
4. Add tests for an already-indexed patient followed by privacy-policy denial, patient opt-out, hospital transition to `ISOLATED_SILO`, identifier changes, control-plane write failure and retry. Assert both the tenant-side response and final control-plane pointer state.
5. Add a bounded reconciliation job that compares eligible active/shareable source patients with their central pointers and removes or repairs stale entries without exporting patient plaintext into logs or reports.

**Assessment:** Medium-priority privacy-minimization and index-lifecycle gap. Source-side discovery/import checks materially limit the demonstrated disclosure impact, but the central index can retain identifiers after publication has been denied and the update route does not surface the failed synchronization. No evidence establishes that this state currently exists in production.

**Boundary:** static source review only. No federation request, patient record, database, credential, migration or production state was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 98. Patient update can deactivate a patient without removing its discovery pointer

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/patients/schemas.py` (`PatientUpdate.is_active`); `backend/domains/patients/router.py` (`update_patient`, `deactivate_patient`); `backend/domains/federation/router.py` (`sync_patient_pointer`, discovery source revalidation).

Static source review only. No federation request was sent, no patient record was read, and no database, credential, migration or production resource was accessed or changed.

### 98.1 The update contract permits soft deactivation but the update path republishes the pointer

`PatientUpdate` exposes `is_active: Optional[bool]`. The `PUT /api/patients/{patient_id}` handler applies every supplied field, commits the tenant patient and then unconditionally calls `sync_patient_pointer`. That synchronizer checks publication privacy, patient network-sharing opt-out and hospital sharing mode, but does not reject or remove a pointer when `patient.is_active` is false. For an otherwise publishable patient, the existing pointer is refreshed (or a pointer is inserted) even after the update has made the source patient inactive.

A separate `DELETE /api/patients/{patient_id}` handler explicitly sets `is_active=False` and deletes the corresponding `GlobalPatientPointer`. The two public mutation paths therefore implement different discovery-index lifecycle semantics for the same inactive patient state: DELETE removes the pointer; PUT with `is_active=false` leaves or republishes it.

### 98.2 Source revalidation limits disclosure, but the index remains stale

Federated discovery subsequently loads the source patient with `Patient.is_active IS TRUE` and returns no source result when the patient is inactive. Import also revalidates source patient eligibility. Thus this pointer alone does not establish that an inactive patient's demographics or allergies are disclosed.

The demonstrated defect is retained searchable index metadata and unnecessary cross-branch candidate work after deactivation. It also makes the index inconsistent with the dedicated deactivation route and can leave the record discoverable as a candidate until source revalidation rejects it. This is distinct from Section 97's early return on a denied publication decision: here publication may be allowed, but the synchronizer itself does not treat the persisted inactive state as a removal condition.

### 98.3 Required remediation and acceptance evidence

1. Make `sync_patient_pointer` treat `patient.is_active is False` as an explicit pointer-removal outcome before attempting publication or identifier refresh.
2. Remove or disallow `is_active` from the general `PatientUpdate` contract and require the dedicated deactivation operation, or make both routes call one shared lifecycle service with identical pointer-cleanup semantics.
3. Ensure callers handle typed synchronization outcomes and define retry/reconciliation behavior for the tenant/control-plane commit boundary.
4. Add regression tests for PUT deactivation, dedicated DELETE deactivation, reactivation (if supported), privacy denial and control-plane cleanup failure. Assert that no inactive source retains a discoverable pointer after successful lifecycle completion.
5. Add a bounded reconciliation check for inactive source patients whose pointers remain in the control-plane index.

**Assessment:** Medium-priority privacy-minimization and lifecycle consistency gap. Discovery/import source revalidation materially limits the demonstrated disclosure impact; this is not evidence of an authorization bypass or patient-data exposure. Static source establishes the inconsistent API behavior, not that it has occurred in production.

**Boundary:** static source review only. No federation request, patient record, database, credential, migration or production state was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 99. Privileged global MPI lookup returns pointers belonging to suspended tenants

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/control_plane/api/routers/fleet_ops.py` (`toggle_tenant_circuit_breaker`, `lookup_global_mpi_pointers`); `backend/control_plane/models.py` (`TenantRegistry`, `GlobalPatientPointer`); `backend/domains/federation/router.py` (discovery active-tenant filtering).

Static source review only. No MPI lookup was executed, no patient record was read, and no database, credential, migration or production resource was accessed or changed.

### 99.1 Tenant suspension disables the node but does not remove or scope its indexed pointers

The control-plane tenant status route updates `TenantRegistry.is_active` and the corresponding `FederatedNode.is_active`, then commits. It does not delete, deactivate or otherwise mark that branch's `GlobalPatientPointer` rows. This may be intentional retention for later reactivation; however, the pointer model has no tenant-active snapshot or discoverability state.

The federation discovery route explicitly joins the pointer candidate set to active `TenantRegistry` rows before opening source tenant databases. Suspended tenants therefore do not proceed as active discovery sources through that path. This is an important mitigating control and means the finding is not a claim that suspended-tenant patients are still returned by ordinary federation discovery.

The separate privileged `GET /api/mpi/lookup` route builds its result directly from `GlobalPatientPointer` and filters by phone hash, ABHA number or MRN. It does not join or filter `TenantRegistry.is_active`. Consequently, support/superadmin operators with access to this audited cross-tenant lookup can still retrieve pointer metadata for a suspended tenant: branch code, subdomain slug, source MRN, ABHA number, phone-hash prefix and the critical-allergy flag. The endpoint records a control-plane audit event, but audit logging does not scope the returned records to active tenants.

### 99.2 Scope and impact

This is a privileged operational MPI disclosure-scope inconsistency, not an unauthenticated exposure or a federation-node authorization bypass. The route requires the control-plane secret, vendor-key verification and support/superadmin role, and it logs the lookup. The demonstrated gap is that tenant suspension is enforced by ordinary federation discovery but not by this separate operator-facing index lookup. No evidence establishes that a suspended tenant's pointers were actually queried or that patient data was exposed in production.

### 99.3 Required remediation and acceptance evidence

1. Decide and document whether tenant suspension should hide MPI pointers from operator lookup or whether an explicitly justified break-glass workflow is required. Do not leave the behavior implicit.
2. By default, join `GlobalPatientPointer.branch_code` to `TenantRegistry` and restrict results to active tenants. If inactive-tenant lookup is operationally necessary, require a separate permission and explicit justification, return a clear inactive status, and audit that exceptional scope.
3. Add tests proving suspended tenant pointers are excluded from ordinary operator lookup and active tenant pointers remain searchable. Add a separately authorized test only if inactive-tenant lookup is an approved requirement.
4. Add observability for pointer counts associated with inactive tenants and a bounded review/retention process; do not automatically destroy pointers if reactivation semantics require retention.
5. Keep federation discovery's active-tenant filter as an independent defense and test it alongside the operator lookup.

**Assessment:** Medium-priority privileged data-minimization and control-plane scope gap. The ordinary federation discovery path already excludes inactive tenant registries, and the operator endpoint is authenticated, role-gated and audited. The concern is the unfiltered privileged lookup of retained identifiers for suspended tenants, not proof of unauthorized access or disclosure.

**Boundary:** static source review only. No MPI lookup, patient record, database, credential, migration or production state was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 100. Partner registration route conflicts with the tenant-bound federation identity guard and cannot register a different branch

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/federation/router.py` (`register_federated_branch`); `backend/domains/federation/models.py` (`_protect_federation_transfer_logs` session `before_flush` listener); `backend/core/database.py` (`get_db`).

**Correction to the earlier Section 100 assessment:** a complete source trace shows that the earlier conclusion that this route can mint an active control-plane identity for an arbitrary branch code was incorrect. The tenant session carries a trusted branch identity, and the model-level flush guard rejects a new `FederatedClient` whose branch code differs from that identity. The registration route commits the tenant-local client row before it performs its control-plane `FederatedNode` lookup, so the guard prevents the cross-branch registration from reaching the control-plane write. The arbitrary-branch enrollment scenario described in the prior version is therefore not established by this code path.

### 100.1 The guard is installed on every request-scoped tenant database session

`get_db(request)` resolves the tenant context and sets both `db.info["tenant_branch_code"] = ctx.branch_code` and `db.info["tenant_subdomain_slug"] = ctx.subdomain_slug` before yielding the SQLAlchemy session. This is not an optional or caller-supplied value on this route.

The `Session.before_flush` listener in `backend/domains/federation/models.py` reads `session.info["tenant_branch_code"]`. For every new `FederatedClient`, when that expected branch is present, it compares the normalized entity branch code to the trusted session branch code and raises HTTP 403 if they differ. `register_federated_branch` creates the `FederatedClient` and calls `db.commit()` before querying or writing `FederatedNode`. Therefore a request whose payload names a different branch fails during the tenant-local flush and does not reach the later control-plane node-creation block.

### 100.2 Actual finding: partner enrollment is blocked by the local-identity invariant

The route is explicitly labelled as branch/partner API-key management and accepts a payload branch code. However, its implementation attempts to persist the partner's branch code as a tenant-local `FederatedClient`, while the tenant session guard requires every newly created `FederatedClient` to carry the current tenant's own branch code. For a genuinely different partner branch, the model guard rejects the write. The route therefore cannot complete the advertised partner-registration flow through this path.

If the supplied code equals the current tenant's own branch, the guard permits it, but that is not registration of an external partner. Whether that same-branch attempt then reaches a duplicate conflict or a control-plane node/key mismatch depends on the existing tenant-local client and control-plane node state; no claim is made here about those unobserved states.

### 100.3 Required remediation and acceptance evidence

1. Separate the local tenant's authenticated inbound federation identity from tenant-local records representing outbound partner relationships. Do not weaken the tenant-bound identity guard to make partner enrollment pass.
2. Define partner enrollment as a distinct relationship/credential workflow. A partner's identity and inbound credential must be issued or accepted by the partner/control plane, not created by writing a foreign branch code into the requesting tenant's local identity record.
3. Make the API contract explicit about which side owns each credential and which credential is used for outbound requests versus inbound caller authentication.
4. Add request-level tests using a tenant session populated by `get_db`: a different partner branch must follow the approved enrollment workflow without attempting a forbidden local identity insert; local identity creation must remain restricted to the trusted tenant branch.
5. Add failure-path tests proving a rejected tenant-local write cannot leave a partial control-plane node or return a credential that is not accepted by the inbound authenticator.

**Assessment:** Medium-priority federation integration/functionality gap. Static source establishes that the partner registration route's intended cross-branch write conflicts with an active model-level tenant identity guard and fails before its control-plane registration branch. The previously stated arbitrary-branch active-node creation claim is withdrawn. This is not evidence of unauthorized federation identity creation or patient disclosure.

**Boundary:** static source review only. No federation credential, request, database, patient data, migration or production state was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 101. Federation key revocation commits tenant-local disablement before control-plane authentication is revoked

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/federation/router.py` (`revoke_federated_branch_key`); `backend/core/dependencies.py` (`get_federated_node`); `backend/control_plane/models.py` (`FederatedNode`).

### 101.1 Revocation spans two databases without an atomic or recoverable operation

The tenant-scoped DELETE `/api/federation/clients/{client_id}` route loads the local `FederatedClient`, sets `is_active = False`, and commits the tenant database. Only after that commit does it query the control-plane `FederatedNode` by the client's branch code, set the node inactive, and commit the control-plane database. The route has no distributed transaction, durable revocation operation, outbox, retry state or reconciliation marker connecting the two commits.

If the control-plane lookup or commit fails after the tenant-local commit succeeds, the request can fail after the local record is disabled while the central node remains active. This is a conditional partial-failure state; no such failure was induced or observed.

### 101.2 Inbound authentication consults the control-plane node, not the tenant-local client flag

The inbound `get_federated_node` dependency hashes the supplied `X-Federation-API-Key` and selects an active `FederatedNode` by key hash. It does not consult the tenant-local `FederatedClient.is_active` row. Consequently, if the local commit succeeds but the control-plane disablement does not, the old key continues to satisfy the reviewed inbound authentication predicate while the central node remains active. The local inactive flag alone does not revoke that inbound credential.

This finding is about the failure boundary in the explicit revocation workflow. It does not assert that a control-plane outage occurred, that a revoked key was used, or that patient data was accessed. It is distinct from Section 73's missing owner-registry active-state check and Section 100's partner-registration route/tenant identity-guard conflict.

### 101.3 Required remediation and acceptance evidence

1. Represent revocation as a durable control-plane operation with an explicit pending/revoked state and idempotent operation identifier. Define the control-plane authentication behavior for pending revocation so the security boundary is unambiguous.
2. Prefer disabling the central inbound credential first, then reconcile tenant-local mirror state. If the required product semantics demand the reverse order, ensure the API does not report successful revocation until the central authenticator rejects the key.
3. Add retryable outbox/reconciliation handling for cross-database completion; expose partial status rather than returning success after only one side has committed.
4. Add fault-injection tests for tenant commit failure, control-plane query/commit failure after tenant commit, process interruption between commits, duplicate revoke requests and reconciliation recovery.
5. Verify with an integration test that after the revocation operation reports success, the old key is rejected by `get_federated_node`; test both tenant-local and control-plane state transitions independently.

**Assessment:** Medium-priority federation credential lifecycle and revocation consistency gap. Static source establishes the order of independent commits and that inbound authentication relies on the control-plane active node. The continued-authentication outcome is conditional on a control-plane failure after the tenant commit; no production occurrence or unauthorized access is established.

**Boundary:** static source review only. No key was created, rotated, revoked or tested; no federation request, database, patient data, migration or production state was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 102. Federation key rotation can report success while tenant-local credential synchronization is absent or failed

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/control_plane/api/routers/fleet_ops.py` (`rotate_tenant_cryptographic_keys`); `backend/domains/federation/models.py` (`FederatedClient`).

### 102.1 Control-plane rotation is committed independently of the tenant-local mirror

When `rotate_federation_key` is enabled, the route generates a new raw key and hash, updates or creates the control-plane `FederatedNode`, and places the raw key in the response object. For CLOUD tenants it then attempts to load the tenant database and update the `FederatedClient` row whose branch code matches the tenant's own branch code.

That tenant-local synchronization is not a required success condition. If no matching `FederatedClient` row exists, the route does nothing and continues. If engine/session/query/update/commit raises, the broad exception handler logs a warning and continues. The route then writes the rotation audit event, commits the control-plane transaction and returns the new raw federation key. Thus the endpoint can return its normal success response with the control-plane hash changed while the tenant-local credential row is absent or still contains the previous key hash/prefix.

For non-CLOUD deployment modes, the reviewed code skips tenant-local synchronization altogether while still rotating and returning the control-plane key. This is an explicit code-path difference; the intended credential distribution mechanism for those deployment modes is not established by this route.

### 102.2 Impact and limits

The source proves a split credential-state outcome is possible and that the API does not expose a partial/failed synchronization status. It does not establish that the tenant-local row is used by the inbound authenticator: `get_federated_node` authenticates against the control-plane node. Nor does this review establish an actual failed synchronization or a patient-data access consequence. The concern is credential lifecycle consistency and misleading success reporting across the two database records.

### 102.3 Required remediation and acceptance evidence

1. Make credential rotation a durable operation with explicit pending, centrally-rotated, tenant-synchronized and completed states. Do not return an undifferentiated success when a required mirror update failed or was skipped.
2. Define the authoritative owner of the federation credential and the role of `FederatedClient`. If it is only a legacy/admin mirror, remove it from rotation semantics or report that explicitly; if it is required, make its synchronization mandatory and recoverable.
3. For deployment modes where the control plane cannot reach the tenant database, provide a tenant-initiated authenticated delivery/acknowledgment flow rather than silently skipping synchronization.
4. Add tests for missing local row, tenant database unavailable, commit failure, process interruption, non-CLOUD deployment, retry and reconciliation. Assert that response/audit state accurately reflects the outcome.

**Assessment:** Medium-priority credential lifecycle consistency and operational reporting gap. Static source establishes that the control-plane commit and success response do not depend on successful tenant-local synchronization. No production failure or unauthorized access is established.

**Boundary:** static source review only. No key was generated, rotated or tested; no federation request, database, patient data, migration or production state was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 103. Federation key rotation reactivates a previously revoked node whenever its tenant remains active

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/federation/router.py` (`revoke_federated_branch_key`); `backend/control_plane/api/routers/fleet_ops.py` (`rotate_tenant_cryptographic_keys`); `backend/core/dependencies.py` (`get_federated_node`).

### 103.1 Revocation state and tenant suspension state are conflated during rotation

The tenant-scoped revoke route sets the matching control-plane `FederatedNode.is_active = False` but does not change `TenantRegistry.is_active`. This permits a revoked federation credential/node to remain associated with an otherwise active tenant.

The control-plane key-rotation route, when it finds an existing node, replaces its key prefix/hash and unconditionally sets `fed_node.is_active = tenant.is_active`. Therefore, for a tenant whose registry remains active after a federation-key revocation, a later rotation request changes the revoked node back to active as part of rotating its key. The new key is returned to the operator. Since `get_federated_node` accepts active nodes with a matching hash, the newly rotated credential becomes valid for inbound federation authentication.

### 103.2 Impact and limits

This is a direct state-transition consequence of the reviewed route sequence, not a speculative database failure. A key revocation does not persist as an independent lifecycle state: rotation derives node activation from tenant activation and can silently undo the revocation. This may be intended as an operator re-enrollment action, but the endpoint does not require an explicit reactivation flag or distinguish a revoked federation relationship from a tenant suspension. No actual rotation after revocation was performed, and no production reactivation or patient disclosure is claimed.

### 103.3 Required remediation and acceptance evidence

1. Separate tenant operational status from federation credential/relationship status. Key rotation must preserve a revoked/disabled federation state unless an explicit, separately authorized reactivation operation is requested.
2. Require an explicit reason and permission for federation reactivation; audit rotation and reactivation as distinct actions.
3. Add state-transition tests for active tenant + active node, active tenant + revoked node, suspended tenant + active node, and suspended tenant + revoked node. Verify that rotation alone never changes the relationship state unexpectedly.
4. Assert that a revoked node remains rejected by `get_federated_node` after ordinary key rotation; separately test the approved explicit reactivation path if the product requires one.

**Assessment:** High-priority federation revocation-state integrity gap. Static source establishes that ordinary key rotation reactivates a revoked node when the tenant itself remains active. Practical impact requires an authorized operator to invoke rotation after revocation; no production event or patient disclosure is established.

**Boundary:** static source review only. No key was generated, rotated or tested; no federation request, database, patient data, migration or production state was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 104. Control-plane key-rotation audit event omits the authenticated operator identity

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/control_plane/api/routers/fleet_ops.py` (`rotate_tenant_cryptographic_keys`); `backend/control_plane/models.py` (`ControlPlaneAuditLog.actor`).

### 104.1 Rotation audit record uses the model's generic actor default

The key-rotation endpoint is gated by `verify_control_plane_secret` and `require_operator_role("ops", "superadmin")`. After updating key material, it adds a `ControlPlaneAuditLog` with action `ROTATE_KEYS`, target slug and boolean details describing which key categories were rotated. It does not supply the `actor` field.

The `ControlPlaneAuditLog.actor` mapped column has the non-null default `VENDOR_CONSOLE`. Therefore this route's ORM-created audit record identifies the generic console source rather than the authenticated named operator. The log records the target and operation categories but cannot, from this row, attribute the rotation to a particular operator account.

This finding is limited to the key-rotation audit event's actor attribution. The endpoint's role gate still restricts invocation to an authorized ops/superadmin operator (or the legacy static credential path where enabled); the missing actor field does not itself bypass authorization. The audit row does not include the raw new keys, and no claim is made that secrets are stored in this audit log.

### 104.2 Required remediation and acceptance evidence

1. Populate `ControlPlaneAuditLog.actor` from the authenticated operator identity for named operator sessions, using a stable operator ID plus a separately retained display/email snapshot where appropriate.
2. For legacy static-credential use, record an explicit non-human credential identity and authentication mode rather than silently using the same generic console actor.
3. Add tests for ops and superadmin sessions proving the persisted actor matches the authenticated principal; test legacy mode separately and ensure secrets never enter audit details.
4. Apply the same actor-attribution contract consistently to other privileged control-plane operations, without retroactively claiming that every existing audit row is attributable.

**Assessment:** Medium-priority privileged-operation audit attribution gap. Static source establishes that the rotation route omits actor and the model default is a generic `VENDOR_CONSOLE` value. This weakens operator accountability and incident reconstruction, but does not establish unauthorized rotation or secret disclosure.

**Boundary:** static source review only. No key was generated, rotated or tested; no operator session, request, database, patient data, migration or production state was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 105. Several privileged fleet mutations do not enforce the named-operator role matrix

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/control_plane/api/routers/fleet_ops.py`; `backend/control_plane/services/auth.py` (`verify_control_plane_secret`, `_verify_vendor_key`, `require_operator_role`).

### 105.1 Vendor-key validation is used where endpoint-specific role authorization is absent

The control-plane auth service supports named operator sessions and role-specific dependencies. `require_operator_role(...)` enforces the named session's role, with superadmin override. Separately, `_verify_vendor_key` allows a superadmin session to bypass the vendor setup key; every other caller must present the configured `MASTER_ONBOARDING_KEY`. That helper validates possession of a shared credential; it does not inspect whether the named operator is ops, support, billing or viewer.

The following mutating fleet routes call `verify_control_plane_secret` and `_verify_vendor_key` but do not declare `require_operator_role`:

- `PATCH /api/tenants/{slug}/status` — suspends/reactivates the tenant and federation node.
- `PATCH /api/tenants/{slug}/deployment-mode` — changes CLOUD/ON_PREM deployment mode.
- `PATCH /api/tenants/{slug}/entitlements` — changes modules, quotas, commercial terms and maintenance mode.
- `POST /api/tenants/{slug}/sync` and `POST /api/tenants/sync-fleet` — run tenant or fleet schema/template synchronization.
- `POST /api/tenants/{slug}/saas-billing/charge` — records a SaaS payment entry and changes payment status.

By contrast, nearby sensitive routes such as key rotation, emergency admin reset and sandbox cloning explicitly declare role dependencies. Consequently, for named operator sessions, the routes listed above rely on the shared vendor key without enforcing the operator's role at the route boundary. A named operator account with a lower-privilege role that also obtains the vendor key can pass the helper; the helper itself does not reject that role. This is a conditional authorization-boundary weakness, not proof that a viewer currently possesses the key or that any such request occurred.

The legacy static control-plane credential path is a separate compatibility case: `require_operator_role` treats callers without a named operator identity as superadmin when that legacy path is enabled. This finding concerns named operator sessions and the missing route-level role checks, not the separate legacy compatibility policy.

### 105.2 Required remediation and acceptance evidence

1. Define a route-to-role matrix for every control-plane read and mutation; assign least-privilege roles for tenant suspension, deployment mode, entitlements, schema sync and billing.
2. Require `require_operator_role` on each route and keep the vendor setup key as an additional credential only where explicitly justified, not as a substitute for authorization.
3. Add negative tests for viewer, support and billing sessions against each mutation, plus positive tests for the intended ops/billing/superadmin roles.
4. Test named-session and legacy-static-key paths separately; document and govern any legacy superadmin-equivalent behavior.
5. Ensure audit records identify the authenticated principal and record the authorization mode for each successful mutation.

**Assessment:** High-priority control-plane authorization consistency gap. The route/helper composition permits a lower-privilege named operator who also has the shared vendor key to invoke mutations without a role check. No evidence establishes that such a credential combination exists in practice or that an unauthorized mutation has occurred.

**Boundary:** static source review only. No control-plane request, operator account, vendor key, database, migration, tenant, patient data or production resource was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 106. Fleet audit-log read endpoint exposes unredacted privileged-operation details without an operator-role gate

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/control_plane/api/routers/fleet_ops.py` (`list_control_plane_audit_logs`, privileged audit writers); `backend/control_plane/services/auth.py` (`verify_control_plane_secret`, `_verify_vendor_key`, `require_operator_role`).

### 106.1 Audit-log reader checks shared credentials but does not enforce a named operator role or redact details

`GET /api/fleet/audit-logs` depends on `verify_control_plane_secret` and calls `_verify_vendor_key`, but does not declare `require_operator_role`. The vendor-key helper checks shared-key possession for non-superadmin sessions; it does not authorize a named operator role. This is the same missing role-boundary pattern as the fleet mutations in Section 105, but this endpoint is a read surface with a distinct audit-data exposure impact.

The endpoint returns each selected row's `action`, `target_slug`, `actor`, full `details` and timestamp. Its optional filters only constrain action and a substring of target; there is no actor-based scope, role-based field projection or redaction. The source's audit writers place operationally sensitive context in `details`, including the administrator email for emergency tenant-admin reset and the free-text justification for global MPI lookup (along with a truncated phone-hash prefix and match count). Other privileged-operation details include tenant/database identifiers and backup/restore task context. Therefore the endpoint can disclose more than a minimal audit-event envelope to any caller who satisfies the shared credential checks, including a lower-privilege named operator if that operator also has the vendor key.

This is not an unauthenticated endpoint: control-plane authentication and vendor-key checks remain present, and a named operator without the vendor key is rejected by the helper unless superadmin. The finding does not establish that any lower-privilege operator has the key, that any particular audit row contains patient-identifying data, or that an audit-log read occurred. The concern is that the endpoint does not independently enforce the intended operator role or minimize returned detail once the shared key check succeeds.

### 106.2 Required remediation and acceptance evidence

1. Assign a dedicated audit-read permission/role and enforce it with `require_operator_role`; do not treat vendor-key possession as an authorization role.
2. Define separate audit projections for ordinary operational viewers and restricted security/compliance investigators. Redact or tokenize email addresses, justifications, identifiers, hashes and secret-adjacent operational details unless a documented purpose requires them.
3. Add tests proving viewer/unauthorized roles cannot read audit logs even with the vendor setup key, and intended audit roles receive only their approved projection.
4. Add tests with synthetic audit rows covering emergency reset, MPI lookup, backup/restore and key rotation; assert restricted fields are absent from ordinary responses and pagination/filtering cannot bypass the projection.
5. Audit the audit-log read itself with authenticated actor, role, filters, result count and justification where access is exceptional; avoid recursive disclosure of sensitive query values.

**Assessment:** High-priority privileged audit-data access-control and minimization gap. The endpoint's route signature and response construction establish missing role enforcement and full-detail serialization. Exploitability by a lower-privilege named operator remains conditional on possession of the shared vendor setup key; no unauthorized access or disclosure is claimed.

**Boundary:** static source review only. No audit records, operator accounts, vendor keys, requests, databases, patient data or production resources were accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 107. Fleet and tenant inventory read endpoints expose operational and commercial metadata without a named-operator role gate

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/control_plane/api/routers/fleet_ops.py` (`get_fleet_global_overview`, `list_registered_tenants`, `get_tenant_operational_telemetry`, `list_tenant_backup_snapshots`); `backend/control_plane/services/auth.py` (`verify_control_plane_secret`, `_verify_vendor_key`, `require_operator_role`).

### 107.1 Shared vendor-key validation is not a substitute for endpoint-specific read authorization

The following read routes depend on `verify_control_plane_secret` and call `_verify_vendor_key`, but do not declare `require_operator_role`:

- `GET /api/fleet/overview` — aggregates active-tenant patient counts, bed and occupancy counts, collected revenue, license ARR, global patient-pointer count and encrypted snapshot count.
- `GET /api/tenants` — returns tenant identity and configuration fields including hospital/branch/group identifiers, subdomain and database names, administrator email, deployment and pricing details, quotas, provisioning configuration, module count, operational/federation state, federation key prefix and global-pointer count.
- `GET /api/tenants/{slug}/telemetry` — opens the selected tenant database and returns user/patient/active-encounter/bed/invoice counts, gross and collected revenue, tenant/database identifiers and the latest encrypted backup filename.
- `GET /api/tenants/{slug}/backups` — returns encrypted backup filenames, file sizes and filesystem modification timestamps.

The shared `_verify_vendor_key` helper allows a superadmin session to bypass the vendor key; otherwise it checks possession of the shared `MASTER_ONBOARDING_KEY`. It does not inspect the named operator's role. The routes therefore lack an independent role gate and do not distinguish viewer, support, billing or ops permissions at the endpoint boundary. A lower-privilege named operator who also obtains the shared vendor key can pass these checks and read the returned data. This is a conditional authorization-boundary weakness, not proof that any lower-privilege operator possesses the key or that any read occurred.

The returned values are not raw patient records, but the combined inventory and telemetry are operationally sensitive: tenant administrators and database names, provisioning and commercial configuration, aggregate clinical workload, revenue, federation metadata and backup inventory. The backup-list route exposes metadata only; this review does not establish that it returns or downloads backup contents. The fleet overview also aggregates metrics by opening active tenant databases, so the read path crosses the control-plane-to-tenant database boundary.

This finding is separate from Section 105's mutation routes and Section 106's audit-log reader. It does not claim unauthenticated access: control-plane authentication and vendor-key checks remain present. The legacy static control-plane credential compatibility path is a separate policy issue; the concrete concern here is missing route-level role enforcement for named operator sessions.

### 107.2 Required remediation and acceptance evidence

1. Define and enforce a read-permission matrix for fleet overview, tenant inventory, tenant telemetry and backup inventory. Apply `require_operator_role` or narrower purpose-specific permissions to each route.
2. Minimize each response by role and operational purpose. Avoid returning administrator email, database names, provisioning secrets/configuration, federation metadata or backup filenames to roles that do not need them.
3. Separate commercial/billing fields from operational telemetry, and define whether aggregate patient and encounter counts are available to support/viewer roles.
4. Add negative tests proving viewer and other disallowed named roles are denied even when the vendor key is supplied; add positive tests for the intended roles and superadmin.
5. Add synthetic response-projection tests for tenant inventory, telemetry and backup metadata. Verify no raw patient rows, credentials, backup contents or unapproved configuration fields are returned.
6. Audit sensitive fleet/tenant inventory reads with authenticated actor, role, target tenant, requested projection and result count, without copying sensitive response values into the audit event.

**Assessment:** High-priority control-plane read-authorization and metadata-minimization gap. Static source establishes that these routes omit a named-operator role dependency and return the listed aggregate/configuration/backup metadata after shared-key validation. Exploitability by a lower-privilege named operator remains conditional on possession of the shared vendor setup key; no unauthorized read, patient-record disclosure or backup-content access is claimed.

**Boundary:** static source review only. No endpoint was called; no operator account, vendor key, tenant database, backup artifact, patient data, migration or production resource was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.

## 108. Stripe subscription webhook references billing fields absent from the control-plane tenant model and migrations

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/control_plane/api/routers/saas_billing.py` (`stripe_subscription_webhook`); `backend/control_plane/models.py` (`TenantRegistry`); `backend/control_plane/alembic/versions/95769c3ab4b3_baseline.py` and all subsequent control-plane migration revisions; `tests/test_21_control_plane_migrations.py`.

### 108.1 Webhook lookup uses an unmapped customer identifier

The Stripe webhook verifies the configured Stripe signature and then handles `invoice.payment_succeeded`, `invoice.payment_failed` and `customer.subscription.deleted`. For each recognized event it evaluates a query using `TenantRegistry.stripe_customer_id`.

The reviewed `TenantRegistry` mapped class does not declare `stripe_customer_id`. The control-plane baseline migration creates `tenant_registry` without that column, and the subsequent control-plane migration revisions reviewed add no such column. Consequently, once Stripe is configured and a correctly signed recognized event reaches this query, Python attribute resolution raises `AttributeError` before SQL executes. The webhook does not catch that error in its signature-validation block, so the recognized event is not successfully applied and the handler returns a server error rather than the success response.

### 108.2 Renewal expiry is assigned to a non-persistent attribute

On the payment-succeeded path, the route also assigns `tenant.license_valid_till` from the first invoice line's period end. The reviewed `TenantRegistry` model and control-plane migration history likewise contain no mapped `license_valid_till` field. Even if the customer lookup were repaired independently, assigning an ordinary Python attribute to the ORM instance does not persist that value as a database column. The route therefore has no durable license-expiry record through this field.

The repository test inventory reviewed includes control-plane migration characterization and tenant billing tests, but no Stripe webhook lifecycle test that would catch this model/migration mismatch. No Stripe event was sent and no production billing state was inspected.

### 108.3 Required remediation and acceptance evidence

1. Define the authoritative Stripe customer-to-tenant mapping and add a mapped, uniquely constrained customer identifier with an explicit control-plane migration and backfill/registration lifecycle.
2. Decide whether license expiry is a first-class mapped column or a derived value from a durable subscription/invoice ledger; do not assign it as an unmapped transient attribute.
3. Add signed synthetic webhook tests for payment success, payment failure, subscription deletion, unknown customer, malformed/missing invoice period data and repeated delivery. Assert both HTTP outcome and persisted tenant billing/entitlement state.
4. Add a migration-to-model parity assertion for the new billing fields and verify uniqueness and customer-to-tenant ownership constraints.
5. Make webhook event processing idempotent and auditable before enabling automatic tenant activation/suspension; preserve event identity and processing outcome without storing unnecessary payment payload data.

**Assessment:** Medium-priority SaaS billing lifecycle correctness gap. Static source and model/migration comparison establish that the recognized webhook paths reference a missing mapped customer field and that the renewal expiry assignment is not persisted. The failure is conditional on Stripe being configured and a recognized signed event being delivered. No production webhook failure, tenant suspension, renewal loss or billing-state corruption is claimed.

**Boundary:** static source and migration review only. No Stripe credentials, webhook, customer, payment, tenant database, patient data, migration execution or production state was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.

## 109. Failed invoice ETL rows copy patient MRNs into control-plane audit details

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/control_plane/api/routers/migration.py` (`_execute_bulk_migration_background`, `_write_migration_audit`); `backend/control_plane/models.py` (`ControlPlaneAuditLog`); `backend/control_plane/api/routers/fleet_ops.py` (`GET /api/fleet/audit-logs`).

### 109.1 A failed invoice-to-patient lookup embeds the source MRN in an audit event

The visual ETL worker resolves an imported invoice's `patient_mrn` against the destination tenant's `Patient.mrn`. When no matching patient exists, it raises an exception whose message includes the supplied MRN:

`Foreign Key Error: Patient MRN '<source value>' does not exist.`

The row-level exception handler catches the error and appends its text to the in-memory `errors` sample (up to 20 entries). After processing, the worker serializes that sample into the control-plane audit event's `details` field via `_write_migration_audit("ETL_VISUAL_MIGRATION_COMPLETED", ...)`. The helper persists the details without removing or hashing the MRN. The failure path also serializes the sampled errors if the overall worker fails.

This is a direct path from a patient identifier in an uploaded invoice CSV into a control-plane audit record. It does not require a successful invoice insert or a patient record read. The finding is about the data written to the audit ledger, not about the correctness of the invoice foreign-key check.

### 109.2 Existing audit-log read exposure increases the impact

Section 106 separately records that `GET /api/fleet/audit-logs` returns full audit `details` and lacks a named-operator role dependency, subject to the shared vendor-key condition documented there. Section 109 is distinct: it identifies a concrete writer that places a patient identifier into that broadly serialized field. No audit-log request or patient data was accessed to establish this static data flow.

### 109.3 Required remediation and acceptance evidence

1. Do not include source row values, patient identifiers, or raw exception messages in control-plane audit details. Record bounded error categories, row numbers and counts only.
2. Keep detailed row diagnostics in a tenant-scoped, access-controlled migration result store with explicit retention and redaction rules; avoid copying patient identifiers into the control-plane ledger.
3. Add synthetic tests using an unmatched invoice MRN and assert that the control-plane audit record contains neither the MRN nor raw exception text.
4. Add tests for both completed-with-row-errors and worker-failure audit paths.
5. Redact existing migration audit details according to an approved retention/remediation process before broadening audit-log reader permissions.

**Assessment:** Medium-priority patient-identifier minimization and audit-data handling gap. Static source establishes the exact MRN-to-audit-details path for unmatched invoice rows. The reader-side impact is conditional on the authorization weakness in Section 106; no actual audit-log disclosure, unauthorized access or patient harm is claimed.

**Boundary:** static source review only. No CSV was uploaded, ETL job executed, audit event queried, patient record accessed, tenant database changed, or production resource touched. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.

## 110. Visual ETL defaults imported patients to federation sharing enabled

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/control_plane/api/routers/migration.py` (`_apply_dynamic_mapping`); `backend/control_plane/services/migration_catalog.py` (`get_migration_schema_catalog`); `backend/domains/patients/models.py` (`Patient.allow_network_sharing`).

### 110.1 Missing source consent/sharing value becomes an affirmative destination value

The migration catalog exposes `patients.allow_network_sharing` as an ordinary importable field. The ETL mapper permits it because it is not included in `PROTECTED_FIELDS`. More importantly, after applying the user mapping, `_apply_dynamic_mapping` executes:

`clean_data.setdefault("allow_network_sharing", True)`

whenever the destination model has that field. Therefore, if a patient CSV omits the field, the mapping omits it, or a source mapping does not populate it, the ETL worker creates the patient with network sharing enabled. The Patient ORM model independently declares `allow_network_sharing` as non-nullable with default `True`, consistent with the ETL behavior.

The import path does not require a recorded patient consent decision or an explicit affirmative source value before assigning this sharing state. A legacy export that has no equivalent consent/sharing field is therefore silently converted into an affirmative sharing setting.

### 110.2 Relationship to the existing federation privacy finding

Section 93 records the separate source-side federation policy behavior when privacy configuration or consent is absent/non-enforcing. Section 110 documents an independent import-time writer that actively sets the patient-level sharing flag to `True` when the source CSV/mapping supplies no value. This finding does not assume that the federation endpoint will necessarily disclose a particular patient's record; it establishes that the ETL import creates a permissive patient-level state which downstream sharing controls may consume.

### 110.3 Required remediation and acceptance evidence

1. Default imported patients to `allow_network_sharing=False` unless an explicit, validated consent/provenance record authorizes the affirmative value.
2. Do not infer consent from a missing legacy CSV column, a mapping fallback, or the ORM default. Preserve source consent status and provenance separately where supported.
3. Require an explicit operator-approved mapping for any transition to sharing-enabled state, with an auditable basis and source timestamp.
4. Add synthetic ETL tests for omitted field, blank field, explicit false, explicit true, and update-policy imports; omitted/blank values must remain non-shareable.
5. Add a downstream federation authorization test proving that an imported patient with absent source consent cannot be returned by discovery.

**Assessment:** High-priority privacy-default issue. Static source establishes that the visual ETL worker assigns `True` when the mapping does not supply `allow_network_sharing`. No actual CSV import, patient record, consent record, federation request or disclosure was observed.

**Boundary:** static source review only. No CSV was uploaded, ETL job executed, patient data accessed, tenant database changed, or production resource touched. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.

## 111. Waiting-room WebSocket stream permits unauthenticated cross-tenant subscriptions

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/realtime/router.py` (`websocket_event_stream`, `_validate_tenant_slug`, `_authenticate_ws`); `backend/core/database.py` (`extract_subdomain_slug`); `backend/core/event_bus.py` (`publish_tenant_event`); `backend/domains/encounters/opd_router.py` (appointment status transition to `IN_CONSULTATION`).

### 111.1 Query-selected tenant stream skips authentication

The WebSocket endpoint accepts `waiting_room` as a supported stream. It derives the tenant from the request host, but when the derived tenant is the default tenant it permits the `tenant_slug` query parameter to select the effective tenant instead. The selected slug is checked for an active registry entry, except that `_validate_tenant_slug` returns `True` for the default slug without consulting the control-plane registry.

After tenant selection, the endpoint explicitly skips `_authenticate_ws` whenever the stream is `waiting_room`. It then accepts the WebSocket without a bearer subprotocol and subscribes to `tenant:{effective_slug}:waiting_room`. Consequently, a caller connecting through the default/base host can supply another active tenant's slug and subscribe to that tenant's waiting-room channel without a tenant user session, JWT, or stream permission. A request through a non-default tenant host remains pinned to the host-derived tenant; the cross-tenant selector is available through the default-host fallback.

### 111.2 Published event contains appointment and clinician operational data

The OPD appointment status handler publishes `TOKEN_CALLED_IN_CONSULTATION` to the tenant's `waiting_room` stream when an appointment enters consultation. The event payload includes appointment ID, token number, doctor ID, doctor name, and department ID. It does not include patient name or MRN in the inspected publisher, so this finding does not claim direct disclosure of those identifiers. Nevertheless, the endpoint exposes live tenant appointment activity and stable appointment/clinician identifiers to unauthenticated subscribers, across tenant boundaries when the default-host query override is used.

The route documentation describes waiting-room TV displays, which may justify a deliberately public display channel. It does not establish a tenant-approved public disclosure policy, a display-device credential, or a minimal-purpose authorization boundary for the selected tenant.

### 111.3 Required remediation and acceptance evidence

1. Do not let an unauthenticated query parameter choose a tenant stream. Resolve the tenant from a trusted host or require a short-lived, tenant-bound display credential issued by an authorized tenant administrator.
2. Separate public display events from operational WebSocket streams. Define and enforce an explicit allowlisted projection for any intentionally public waiting-room output; avoid exposing internal appointment/doctor identifiers unless required.
3. Bind display credentials to one tenant and one stream, support revocation/expiry, and reject cross-tenant, suspended-tenant, malformed, and missing-credential requests.
4. Add synthetic WebSocket tests proving that no credential cannot subscribe to another tenant through the default host; a valid display credential can subscribe only to its bound tenant and approved projection; and suspended tenants are rejected, including the default tenant.
5. Add a publisher contract test that asserts the exact public waiting-room event fields and rejects patient identifiers or other fields outside the approved projection.

**Assessment:** Medium-priority tenant-isolation and operational-privacy exposure. Static source establishes an unauthenticated cross-tenant subscription path and the event fields published to that channel. No live WebSocket connection, Redis event, tenant slug enumeration, patient record, or production disclosure was attempted or observed.

**Boundary:** static source review only. No WebSocket was opened, Redis queried, patient data accessed, tenant database changed, or production resource touched. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 112. NHCX adjudication callback accepts user-authorized, unauthenticated gateway assertions

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/abdm/router.py` (`receive_nhcx_claim_adjudication_callback`); `backend/domains/abdm/schemas.py` (`NHCXAdjudicationCallbackRequest`); `backend/domains/abdm/services.py` (`process_nhcx_adjudication_callback`); `backend/domains/abdm/models.py` (`NHCXClaimExchangeLog`).

### 112.1 A normal tenant user can submit a purported payer adjudication

The route is documented as receiving an adjudication callback from the NHCX Gateway, but its only authentication dependency is `RequirePermission("billing:write", "insurance:write", "integrations:write")`. It does not verify a gateway/payer signature, shared callback secret, mTLS identity, or other machine-to-machine credential. The request schema accepts caller-supplied `transaction_id`, `adjudication_status`, `settled_amount_paise`, `settlement_utr`, rejection reason, and optional adjudication bundle.

The service looks up the transaction ID and associated claim, then trusts the supplied status and amount. For `APPROVED` or `SETTLED`, it sets the claim status to `SETTLED`, copies the supplied amount into `claim.settled_amount_paise`, and copies the supplied UTR. For `REJECTED`, it changes the claim status to `REJECTED`. The reviewed path does not verify that the request originated from NHCX/the payer, that the exchange log is a submitted claim eligible for adjudication, or that the settled amount is consistent with the claim and payer response.

Therefore, a tenant user who legitimately holds any of the route's accepted write permissions can call this purported gateway callback and cause a known tenant transaction's claim to be marked settled or rejected using caller-chosen adjudication values. This is a trust-boundary failure between a remote financial adjudicator and an ordinary tenant application user, not an unauthenticated internet endpoint.

### 112.2 Required remediation and acceptance evidence

1. Separate the gateway callback from user-operated claim workflows. Authenticate callbacks using the configured NHCX gateway/payer trust mechanism (for example, verified signed requests or mutually authenticated transport); do not treat a tenant user's billing permission as proof of remote payer identity.
2. Verify callback transaction identity, expected exchange type, tenant binding, claim linkage, allowed state transition, and payer response integrity before mutating claim state.
3. Validate settlement amount against the claim's submitted/approved amount and defined partial-settlement rules; reject invalid statuses and impossible transitions.
4. Make callback processing idempotent using the gateway event/transaction identity, and preserve a tamper-evident record of verified sender identity, signature-verification result, event identity, and state transition.
5. Add synthetic negative tests showing that a tenant user with each currently accepted permission cannot forge a callback; add positive tests for valid signed callbacks, wrong tenant/transaction, wrong exchange type, replay, invalid status, over-settlement, partial settlement, and rejected claims.

**Assessment:** High-priority financial-integrity and integration-authentication gap. Static source establishes that the callback route accepts ordinary tenant-user authorization and the service directly applies caller-supplied adjudication status/amount to the linked claim. No callback was submitted, claim was modified, gateway credential was accessed, or real financial transaction inspected.

**Boundary:** static source review only. No NHCX request, payer callback, claim record, patient data, tenant database, production credential, or external integration was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.



## 113. HL7 ORU ingestion accepts an ordinary user bearer token as analyzer authentication

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/integrations/router.py` (`require_hl7_auth`, `ingest_hl7_oru_r01_message`); `backend/domains/integrations/service.py` (`process_hl7_oru_r01_in_session`); `backend/domains/integrations/listener.py` (separate MLLP listener authentication and tenant routing).

### 113.1 User session authorization is an alternate path to the device secret

The HTTP ORU^R01 ingestion endpoint is documented for analyzer/interface-engine messages. Its `require_hl7_auth` dependency first accepts a tenant-specific `X-HL7-Secret`, but it also accepts an ordinary bearer token when `get_current_user` succeeds and `user_has_permission(db, user, "lab:write", "mdm:write")` succeeds. The request therefore does not establish that the submitted message came from a registered analyzer or trusted interface engine.

The endpoint passes the submitted raw HL7 message and equipment ID directly to `process_hl7_oru_r01_in_session`. The service parses the patient identifier from the message, resolves the patient by MRN in the request's tenant database, matches diagnostic orders/tasks, and updates result values and task statuses before committing. A user with the accepted write permission can therefore submit a fabricated ORU message through the HTTP route and cause laboratory result/task state changes without possessing the equipment's tenant-specific shared secret.

The separate MLLP listener follows a different path: it extracts the branch code and supplied secret from the HL7 message, checks the active tenant registry entry and shared secret, then selects that tenant's database. That stronger listener check does not protect the HTTP endpoint's bearer-token alternative.

### 113.2 Required remediation and acceptance evidence

1. Separate human-operated result entry from machine-originated HL7 ingestion. Require the configured tenant-bound equipment/interface credential for the machine endpoint; do not treat a clinician or laboratory user's bearer permission as device identity.
2. If manual result entry is required, expose a distinct workflow with explicit actor attribution, clinical authorization, validation, and audit semantics rather than accepting arbitrary raw analyzer messages.
3. Bind equipment identity to the authenticated machine credential and validate that the equipment is registered, active, and authorized for the tenant and message type.
4. Add synthetic negative tests proving that a bearer token with `lab:write` or `mdm:write` alone cannot invoke the machine-ingestion endpoint; add positive tests for valid tenant equipment credentials, wrong-tenant secrets, inactive equipment, unknown MRNs, duplicate/replayed message-control IDs, and malformed/amended result messages.
5. Preserve the MLLP listener's independent tenant/secret validation and verify both HTTP and MLLP paths have equivalent tenant/equipment authorization and replay controls.

**Assessment:** High-priority clinical-data integrity and integration-authentication gap. Static source establishes the HTTP endpoint's accepted bearer-token alternative and the downstream result/task mutation path. No HL7 message was submitted, patient record inspected, result changed, equipment secret accessed, or production integration exercised.

**Boundary:** static source review only. This finding concerns the HTTP ORU endpoint; it does not claim the MLLP listener's shared-secret check is bypassed. No runtime, database, credential, patient-data, or production changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 114. ABDM health-information export does not enforce the consented HIU or information-type scope

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/abdm/router.py` (`fetch_health_records_under_consent`); `backend/domains/abdm/schemas.py` (`HealthDataTransferRequest`); `backend/domains/abdm/services.py` (`generate_abdm_fhir_health_data`); `backend/domains/abdm/models.py` (`ABDMConsentArtefact`).

### 114.1 Caller-selected export types bypass the stored consent scope

The M3 route accepts an ordinary tenant user with any of `privacy:read`, `clinical:read`, or `integrations:read`. It passes the caller-supplied `consent_id` and `hi_types` directly to `generate_abdm_fhir_health_data`. The service checks that the artefact exists, has status `GRANTED`, and has not expired, then uses the request's `hi_types` to decide whether to include Prescription and DiagnosticReport data. It does not compare the requested types with `artefact.hi_types`, and it does not authenticate the requester as the artefact's recorded `hiu_id` or otherwise bind the request to an authorized HIU identity.

Consequently, an authenticated tenant user who can call the M3 route can use a known granted consent ID and choose the exported resource categories independently of the consent's stored type scope. The response is returned directly to that user as a FHIR bundle; the route does not establish that the recorded HIU is the recipient. The Patient resource is also inserted unconditionally, irrespective of the requested `hi_types`. The source therefore establishes a consent-scope and recipient-binding failure; it does not establish that a particular external HIU received data.

### 114.2 Required remediation and acceptance evidence

1. Authenticate the requesting HIU/gateway using the configured ABDM trust mechanism and bind the authenticated requester to `artefact.hiu_id`; human tenant permissions must not stand in for recipient identity.
2. Compute the export set as a strict subset of the consent artefact's verified `hi_types`; reject any requested category outside the grant. Define and test the permitted baseline Patient/demographic projection explicitly.
3. Verify consent artefact integrity, HIP/HIU identifiers, patient binding, status, expiry, date range, and revocation state at the time of each transfer.
4. Add synthetic negative tests for wrong HIU, ordinary-user access without a HIU identity, requested type outside grant, empty/narrow grants, revoked/expired consent, and Patient-resource projection; add positive tests for a correctly authenticated HIU requesting only granted categories.
5. Record an auditable transfer receipt with verified recipient identity, consent version/digest, exact resource categories and date range, and response delivery outcome.

**Assessment:** High-priority health-information privacy and consent-enforcement gap. Static source establishes that M3 export selection is caller-controlled and does not enforce the stored HIU identity or stored information-type list. No FHIR export request was executed, no patient record was read, and no data was transferred to an external recipient.

**Boundary:** static source review only. No ABDM gateway, consent manager, patient data, tenant database, external recipient, or production credential was accessed. No runtime or database changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.

## 115. ABDM M2 consent notifications accept unverified caller assertions as grant/revocation state

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/abdm/router.py` (`notify_consent_grant`); `backend/domains/abdm/schemas.py` (`ConsentArtefactNotifyRequest`); `backend/domains/abdm/services.py` (`record_consent_artefact`); `backend/domains/abdm/models.py` (`ABDMConsentArtefact`); `tests/test_51_abdm_and_nhcx_gateways.py` (`test_abdm_m2_consent_and_m3_fhir_health_data_transfer`); `backend/core/dependencies.py` (`RequirePermission`, `get_current_user`).

### 115.1 Tenant-user authorization is treated as consent-manager notification authenticity

The M2 `/api/abdm/m2/consent/on-notify` route is protected by `RequirePermission("privacy:write", "integrations:write", "admin:write")`. That dependency authenticates a tenant user through the tenant JWT/session and checks whether the user holds any one of those permissions; it does not establish an ABDM Consent Manager or gateway identity. The route passes the submitted payload directly to `record_consent_artefact`.

The request schema makes `signature` optional. The reviewed service does not verify a signature, certificate, issuer, audience, or callback origin. It simply persists the supplied signature string. For an existing `consent_id`, it overwrites status, permitted information types, date range, expiry, and signature from the new request; for a new ID, it creates the artefact using the caller-supplied patient, HIU, HIP, manager, status, and scope. No append-only consent-transition history or replay check is present in this path.

The existing integration test posts a `GRANTED` notification using `superuser_headers`, supplies the literal dummy signature `SHA256withRSA:DUMMY_DIGITAL_SIGNATURE`, and expects HTTP 201. This confirms that the test's ordinary tenant-user path does not require a cryptographically valid notification. The route is not unauthenticated: the finding is that ordinary authenticated tenant users with any accepted write permission can assert consent-manager events without proof that the ABDM sender issued them. A caller able to submit an existing consent ID can also replace its state and scope, including grant/revocation state.

The reviewed ABDM router has no gateway-specific dependency, and the reviewed application middleware contains only request-correlation handling; no separate ABDM notification signature-verification layer was identified in the inspected route/dependency path.

### 115.2 Required remediation and acceptance evidence

1. Separate the external Consent Manager callback from human tenant workflows. Authenticate the callback using the configured ABDM trust mechanism and a dedicated gateway identity; tenant-user permissions must not authenticate a remote consent event.
2. Verify the signed notification against trusted Consent Manager keys/certificates and validate issuer, audience, HIP/HIU, patient/consent binding, timestamp, expiry, and payload integrity before changing consent state.
3. Enforce replay protection and idempotency using the authenticated event/transaction identity. Reject stale, duplicate, malformed, or incorrectly scoped notifications.
4. Model grant, revoke, and expiry as validated state transitions with an append-only/tamper-evident event history. Do not permit an arbitrary update to rewrite the identity, patient, recipient, scope, or provenance of an existing consent artefact.
5. Add synthetic negative tests for missing, dummy, invalid, wrong-issuer, wrong-audience, altered, expired, and replayed signatures/events; prove ordinary tenant users cannot invoke the gateway callback as the Consent Manager. Add positive tests for verified grant and revocation events, valid state transitions, and immutable event provenance.

**Assessment:** High-priority consent authenticity, integrity, and health-information privacy gap. Static source establishes that the M2 notification route accepts tenant-user permission as its only route-level authentication, the signature is optional and not verified in the service, and the supplied payload can create or overwrite consent state. The existing test accepts a dummy signature. No notification was submitted, consent record changed, patient data accessed, or ABDM gateway contacted.

**Boundary:** static source and test review only. No runtime, database, consent record, patient data, production credential, external gateway, or tenant configuration was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.

## 116. ABDM M3 export does not fence concurrent consent revocation

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/abdm/services.py` (`generate_abdm_fhir_health_data`); `backend/domains/abdm/router.py` (`fetch_health_records_under_consent`, `notify_consent_grant`); `backend/domains/abdm/models.py` (`ABDMConsentArtefact`).

### 116.1 Consent is checked once, before bundle construction

The M3 service loads the consent artefact and checks that its current status is `GRANTED` and its expiry has not passed. It then loads the patient and clinical records, constructs the FHIR bundle, and returns the result. The artefact row is not selected with a locking read, no export/revocation coordination marker is created, and the service does not re-read or revalidate consent status immediately before returning the bundle.

The M2 notification service can update an existing artefact's status to `REVOKED` and commit that change. Under the normal PostgreSQL READ COMMITTED transaction behavior, if that revocation commits after the M3 service has loaded the artefact but before the bundle is returned, the in-memory ORM object used by the export remains at the previously observed `GRANTED` state. The already-running export can therefore complete based on a grant that has since been revoked. This is a concurrency window, not a claim that every revocation is ignored: exports that begin after the committed revocation are denied by the initial status check.

The current test covers a successful grant/export flow but does not exercise a concurrent revocation during bundle construction. Because Section 115 separately establishes that the notification path does not authenticate the Consent Manager, this finding is about the additional lifecycle guarantee required even after notification authenticity is corrected.

### 116.2 Required remediation and acceptance evidence

1. Define the required withdrawal semantics for in-flight health-information exports: whether revocation must prevent any response not yet delivered, cancel queued work, and/or record a transfer already irrevocably dispatched.
2. Coordinate export and revocation using a durable consent version/state transition and an appropriate database concurrency mechanism (for example, row locking or an export lease/fencing token). Ensure the mechanism covers the complete authorization-to-delivery boundary rather than only the initial lookup.
3. Revalidate the current consent version and status immediately before the response is released; if revocation wins the race, discard the generated bundle and return a denial. If delivery cannot be recalled after release, record that boundary explicitly.
4. Add deterministic concurrency tests that pause bundle construction, commit revocation, resume export, and assert the approved withdrawal behavior. Also test the inverse ordering, expiry during export, duplicate revocation, and repeated export attempts.
5. Record an auditable outcome for both export and revocation, including consent version, ordering, recipient identity, resource scope, and whether a response was released.

**Assessment:** High-priority consent-withdrawal enforcement gap. Static source and PostgreSQL transaction semantics establish a race window in which an export that passed its initial status check can continue after a revocation commits. No concurrent export or revocation was executed, no patient data was read, and no FHIR bundle was generated.

**Boundary:** static source and test review only. No runtime, database, consent record, patient data, production credential, external gateway, or tenant configuration was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.

## 117. FHIR search pagination exposes counts for privacy-filtered records

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/fhir/router.py` (Patient, Encounter, Observation, and Condition search endpoints); `backend/domains/privacy/runtime.py` (`evaluate_tenant_data_use_for_patients`).

### 117.1 Search totals and continuation links use unfiltered result counts

The FHIR search endpoints first calculate `total` from the complete database query, then fetch only the current page and apply the tenant privacy evaluator to that page's patients. The response computes `adjusted_total` by subtracting only the number of denied records found on the current page. It does not evaluate all records contributing to the original `total`, so denied records on other pages remain included in the reported total.

The continuation-link condition is also based on `offset + len(page)` compared with the original unfiltered `total`. As a result, an authorized caller can receive a Bundle total and pagination behavior that reflect records excluded by the privacy policy, even though those records are omitted from the current page's entries. Repeating searches with different offsets can reveal aggregate information about the existence/volume of privacy-filtered patient, encounter, observation, or condition records. This finding concerns metadata counts and pagination, not direct return of the filtered clinical resources.

The same calculation pattern appears in all four resource search families. Individual resource reads and search entries still call the privacy evaluator; this finding does not claim those checks are absent.

### 117.2 Required remediation and acceptance evidence

1. Do not derive externally visible totals or continuation links from an unfiltered result set when row-level privacy filtering is applied.
2. Prefer applying the privacy decision in the database query before pagination and counting, where policy semantics permit. Otherwise use a safe pagination strategy that does not disclose hidden-row counts or offsets.
3. Ensure `Bundle.total`, next links, page sizes, and termination behavior all reflect only the caller-visible result set; avoid leaking whether hidden rows exist beyond the current page.
4. Add synthetic tests with allowed and denied patients interleaved across multiple pages for Patient, Encounter, Observation, and Condition searches. Assert totals, page boundaries, continuation links, and returned entries do not reveal hidden-row counts.
5. Verify audit events remain recorded for evaluated records without using their denied counts in externally visible response metadata.

**Assessment:** Medium-priority privacy metadata disclosure. Static source establishes that all four search endpoints calculate totals and continuation links from unfiltered query counts while filtering only the current page's entries. No FHIR search was executed and no patient data or tenant database was accessed.

**Boundary:** static source review only. No runtime, database, patient record, production credential, external FHIR client, or tenant configuration was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.

## 118. DPDP patient dossier export accepts unverified data-rights requests

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/privacy/router.py`, `export_patient_dpdp_dossier` (route `GET /data-rights/patients/{patient_id}/export-dossier`); `tests/test_61_streaming_export_and_registers.py`.

### 118.1 Request-state gate does not require verification

The export route's docstring and error response state that a verified DPDP Section 11 data-rights request is required. When a caller supplies `request_id`, however, the route checks only that the request exists, belongs to the selected patient, and is not `REJECTED`. It does not require `req.status == "VERIFIED"`.

When no request ID is supplied, the route selects the newest request whose status is in `SUBMITTED`, `IN_REVIEW`, `IN_PROGRESS`, `FULFILLED`, or `VERIFIED`. The route then explicitly treats `SUBMITTED`, `IN_REVIEW`, and `IN_PROGRESS` as sufficient to proceed and changes the request to `FULFILLED`.

The handler subsequently collects and packages a broad patient dossier, including allergies, comorbidities, encounters/admissions, clinical notes, vitals, diagnoses, prescriptions, diagnostic orders, surgeries, invoices, and consent records. The endpoint is permission-gated by `privacy:read`, but the request-state condition does not establish that the data-rights request has been verified before this sensitive export occurs.

This is a request-verification workflow bypass, not an unauthenticated endpoint or a cross-tenant lookup. The request is still checked against the requested patient ID.

### 118.2 Required remediation and acceptance evidence

1. Define an explicit, auditable verification transition and require the request to be in `VERIFIED` before generating the dossier.
2. Reject `SUBMITTED`, `IN_REVIEW`, and `IN_PROGRESS` requests for export; do not silently promote them to `FULFILLED`.
3. If repeat export after fulfillment is intended, define and test that as a separate authorized state transition with actor, time, and reason recorded.
4. Add synthetic tests for every request status, with both explicit `request_id` and implicit newest-request selection. Only `VERIFIED` (and any explicitly approved repeat-export state) should succeed.
5. Verify that rejected attempts do not generate dossier content, change request status, or disclose whether unrelated patient records exist.

**Assessment:** High-priority privacy workflow enforcement gap. Static source establishes that non-verified request states are accepted by the export handler, which then serializes a comprehensive clinical/administrative dossier. The existing test establishes that a request is required but does not establish that it must be verified. No dossier was generated and no patient data was accessed during this review.

**Boundary:** static source and test review only. No runtime export, patient record access, tenant database, production credential, or external data-rights workflow was used or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.

## 119. DPDP data-rights lifecycle endpoint permits unrestricted terminal-state rewrites

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/privacy/router.py`, `DataRightsStatusUpdate` and `update_data_rights_request_status`; `backend/domains/privacy/models.py`, `PatientDataRightsRequest`; `tests/test_61_streaming_export_and_registers.py`.

### 119.1 Current-state transition is not validated

The status update payload permits `IN_REVIEW`, `FULFILLED`, or `REJECTED`. The handler loads the request and assigns `req.status = payload.status` directly. It does not inspect the existing status or enforce a transition graph. Consequently, requests already marked `FULFILLED` or `REJECTED` can be changed again, including reopening a rejected request as `IN_REVIEW` or marking it fulfilled without an intervening review/verification state.

The handler records the latest `handled_by_user_id`, but the reviewed model has no append-only transition history for prior status, actor, timestamp, and reason. A later update overwrites the single current status/handler fields. `fulfilled_at` is set on FULFILLED; it is not cleared when a later update changes the status away from FULFILLED. Rejection reason is similarly retained unless a later FULFILLED update clears it.

There is also a workflow-model inconsistency: `DataRightsStatusUpdate.status` does not permit `VERIFIED`, although the dossier export route treats `VERIFIED` as a request status and describes verification as a prerequisite. The ordinary lifecycle API therefore has no explicit transition to the state that the export contract says it requires.

### 119.2 Required remediation and acceptance evidence

1. Define an explicit state machine, including who may verify, fulfill, reject, and reopen a request; validate every transition against the locked current state.
2. Treat terminal states as immutable unless a separately authorized, reasoned reopen operation is defined.
3. Add an append-only transition ledger with previous/new state, actor, timestamp, reason, and correlation ID; do not rely only on mutable current-row fields.
4. Define the verification state and transition consistently across request creation, review, export, and response APIs.
5. Add synthetic transition-matrix tests covering every source/destination state, concurrent updates, terminal-state rewrites, and consistency of `fulfilled_at` and rejection metadata.

**Assessment:** High-priority privacy workflow integrity and accountability gap. Static source shows that the update handler permits direct state replacement without a transition guard, while the model stores only current lifecycle fields. The existing streaming/export test exercises dossier creation but does not test the data-rights status transition matrix.

**Boundary:** static source and test review only. No data-rights request was created or changed, no patient data or tenant database was accessed, and no runtime workflow was executed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.

## 120. DPDP data-rights request intake lacks requester identity and authority provenance

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/privacy/router.py`, `DataRightsRequestCreate` and `create_data_rights_request`; `backend/domains/privacy/models.py`, `PatientDataRightsRequest`; `tests/test_61_streaming_export_and_registers.py`.

### 120.1 Request submission records a patient target, not who exercised the right

The intake endpoint accepts `patient_id`, `request_type`, arbitrary `details`, and an SLA value. It checks only that the referenced patient row exists, then creates a `SUBMITTED` request. The authenticated actor is injected into the handler as `actor`, but is not used when constructing or saving the request.

The reviewed `PatientDataRightsRequest` model stores patient, request type, status, free-form details, SLA, response/rejection fields, the later handler identity, fulfilment timestamp, and creation timestamp. It has no requester/representative identity, relationship or authority type, authority evidence reference, request-channel/receipt evidence, or submission actor field. The response model likewise exposes no such provenance. The existing test creates a request using a superuser bearer token and a narrative `details.reason`; it does not assert requester identity or representative authority.

As implemented, a user with `privacy:write` can create a request against any existing patient ID and label it ACCESS, CORRECTION, ERASURE, GRIEVANCE, NOMINATION, or PORTABILITY without the intake record establishing that the patient or an authorized representative actually made the request. This is a provenance/authority verification gap, not a claim that the route is unauthenticated or that every staff-assisted intake is invalid. A separate generic audit trail, if present, may identify the authenticated API actor, but it would not by itself establish the data principal's identity or a representative's authority; the request entity itself does not preserve that relationship.

### 120.2 Required remediation and acceptance evidence

1. Define supported intake channels (patient self-service, verified in-person, authorized representative, statutory/authorized referral) and the identity/authority evidence required for each.
2. Persist immutable requester identity and capacity (data principal or representative), representative relationship/authority evidence reference, intake channel, received-at time, and the authenticated staff actor where staff-assisted.
3. Separate the authenticated operator from the person exercising the right; do not treat a staff bearer token or free-form details as proof of patient authorization.
4. Add synthetic tests for patient self-request, authorized and unauthorized representatives, staff-assisted intake, missing/invalid evidence, and attempts to file against another patient's identifier without authority.

**Assessment:** High-priority privacy request authenticity and evidentiary-provenance gap. The intake handler and persisted request model establish the missing fields and the unused actor parameter; the current test covers only successful staff-authenticated creation.

**Boundary:** static source and test review only. No request was submitted, no patient record was read, and no runtime or tenant database was accessed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.

## 121. DPDP dossier export records fulfilment before the export response is completed

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/privacy/router.py`, `export_patient_dpdp_dossier`.

### 121.1 Fulfilment and ALLOW audit commit precede final bundle processing and response

For requests in `SUBMITTED`, `IN_REVIEW`, or `IN_PROGRESS`, the handler changes the request to `FULFILLED`, sets `fulfilled_at`, and records `handled_by_user_id` before loading and assembling the dossier contents. After constructing the bundle, it inserts a `PrivacyDecisionAudit` with result `ALLOW` and a reason stating that the dossier was exported, then commits the database transaction. Only after that commit does it serialize the bundle to compute its integrity SHA-256 and return the response.

The durable status and ALLOW audit therefore represent fulfilment/export before the handler has completed its final integrity-hash processing or returned the response. If post-commit hashing/response serialization fails, or the connection is lost before the client receives the response, the request remains marked fulfilled and the audit says exported although successful delivery is not established. The current record does not distinguish dossier generation, response handoff, and recipient receipt.

This is separate from Section 118's insufficient request-verification gate and Section 119's unrestricted state transitions: it concerns the accuracy of the fulfilment event and its audit semantics after an export is initiated.

### 121.2 Required remediation and acceptance evidence

1. Define whether FULFILLED means generated, handed to the authenticated requester, or acknowledged as received; use separate lifecycle events/states where these are materially different.
2. Build and integrity-hash the complete bundle before committing a fulfilled state or an audit event that asserts completed export.
3. Persist a durable export-attempt record with request ID, actor, bundle hash, generation outcome, response/handoff outcome, and timestamps; do not infer recipient receipt from a server-side return statement.
4. Ensure failures before response handoff leave the request pending/retryable or record a distinct failed-attempt state without falsely asserting fulfilment.
5. Add synthetic fault-injection tests for bundle construction, hashing, response serialization, and interrupted delivery, verifying request status and audit outcome for each case.

**Assessment:** High-priority privacy workflow accuracy and evidentiary-integrity gap. Static source establishes the order of mutation, commit, hash, and return; it does not establish that a delivery failure has occurred in production.

**Boundary:** static source review only. No dossier was generated, no patient data was read, no export endpoint was invoked, and no runtime or tenant database was accessed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.



## 122. DPDP request and patient-access summary reads lack application-level actor-attributed access events

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/privacy/router.py` (`list_data_rights_requests`, `get_data_rights_request`, `get_patient_data_access_summary`); `backend/domains/audit/router.py`; `backend/domains/audit/models.py`; `backend/domains/privacy/models.py`; `backend/core/audit.py`; `backend/main.py`.

### 122.1 Sensitive reads are permission-gated but do not emit a read event

The data-rights request list (`GET /api/privacy/data-rights/requests`), individual request retrieval (`GET /api/privacy/data-rights/requests/{request_id}`), and patient access summary (`GET /api/privacy/data-rights/patients/{patient_id}/summary`) are protected by `RequirePermission("privacy:read")`. The list and detail handlers do not receive the authenticated actor; the summary handler likewise receives only the patient ID and database session after its route-level permission dependency.

These handlers return data-rights request records or a patient summary containing identifiers/profile fields, consent decisions and timestamps, and data-rights history. Their reviewed implementations do not insert a `PrivacyDecisionAudit`, `SecurityAuditExportRegister`, or another durable actor-attributed read event.

The shared audit mechanisms reviewed do not fill this gap. `AuditMixin` stamps create/update actors only on entities that inherit it and only during writes; it does not record reads. `PatientDataRightsRequest` does not inherit `AuditMixin`. `PrivacyDecisionAudit` is used for privacy decision events and the dossier-export handler explicitly writes an actor-attributed export decision, but the list/detail/summary read handlers do not write corresponding access events. `SecurityAuditExportRegister` records SIEM stream exports, not ordinary privacy request or patient-summary reads. The global request-correlation middleware logs method, path, status and timing; the reviewed log statements do not persist an authenticated actor with a patient/request target as a queryable application audit event.

This is an application-level auditability finding for the three named read paths. It is not an assertion that no reverse-proxy, infrastructure, database, or external SIEM logs exist, and it is not an authentication bypass: the routes remain protected by the `privacy:read` permission.

### 122.2 Required remediation and acceptance evidence

1. Add a durable, append-only access-event mechanism for sensitive privacy reads, recording authenticated actor, tenant/branch context, action/resource type, patient and/or request identifier, timestamp, request correlation ID, outcome, and a minimal purpose/context field.
2. Emit events for list, detail, and patient-summary reads, including denied attempts where the application can safely identify the actor and target; avoid storing returned clinical/request content in the audit record.
3. Define how list queries with multiple patients are represented without losing per-subject accountability or creating excessive sensitive metadata.
4. Ensure audit persistence failure is handled according to an explicit fail-closed or documented risk policy for these sensitive read paths.
5. Add synthetic tests proving successful and denied reads create correctly attributed events, including pagination/filtering, cross-tenant isolation, and absence of patient/request payloads in event details.
6. Document any infrastructure-level access logging separately; do not treat request-path logging without actor and target attribution as a substitute for the application access ledger.

**Assessment:** High-priority privacy auditability gap. Static source review establishes that the named request and summary read handlers have permission checks but no application-level durable actor-attributed read event. The dossier-export path does create its own actor-attributed decision event and is not included in this finding. No endpoint was invoked and no patient or tenant data was accessed.

**Boundary:** static source review only. No runtime, database, audit record, patient record, production credential, or infrastructure log store was accessed or changed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 123. Consent policy lifecycle exposes no production ENFORCE activation path

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/privacy/router.py` (`create_privacy_policy_draft`, `approve_privacy_policy_draft`, `activate_privacy_policy_audit_only`, `deactivate_privacy_policy`); `backend/domains/privacy/models.py` (`PrivacyPolicyRevision`); `backend/domains/privacy/runtime.py`; `backend/domains/privacy/decision_engine.py`; `backend/domains/privacy/policy_schema.py`.

### 123.1 The exposed lifecycle can approve and audit, but cannot activate enforcement

The policy model and decision engine support three modes: `OFF`, `AUDIT_ONLY`, and `ENFORCE`. The runtime evaluator reads the active consent revision's `enforcement_mode` and passes it to `evaluate_data_use`; the decision engine returns an actual deny only in `ENFORCE`, while `AUDIT_ONLY` always allows and records whether the decision would have denied.

The reviewed privacy router exposes policy draft creation, second-person approval, one activation endpoint named `activate-audit-only`, and deactivation. That activation endpoint sets the revision to `AUDIT_ONLY`; it explicitly rejects activation when `settings.is_production()` is true. The reviewed router contains no endpoint or lifecycle operation that sets a consent revision to `ENFORCE`. Approval only changes the revision status and approval metadata; it does not activate enforcement. Deactivation sets the active revision to `OFF`.

The policy schema includes `validate_for_enforcement()` to reject enforcement when registered data-use points remain unmapped, but the reviewed approval and activation handlers call only `validate_policy_document()`; no enforcement activation handler invokes the coverage gate.

Consequently, through the reviewed application API, a tenant can create and approve a consent policy and can use audit-only mode in non-production, but cannot transition that policy into actual consent-denial enforcement. This is not a claim that a database operator could not manually alter the row, nor that every data-use path is unprotected by other controls. It is a missing supported application lifecycle path for the consent engine's enforcement mode.

### 123.2 Required remediation and acceptance evidence

1. Define an explicit, separately authorized ENFORCE activation workflow, including second-person approval, a recorded activation reference, and actor/time provenance.
2. Require `validate_for_enforcement()` and a current complete data-use-point coverage check before activation; reject incomplete mappings rather than silently leaving points unmapped.
3. Define safe rollout from OFF/AUDIT_ONLY to ENFORCE, including staged verification, rollback/deactivation controls, and clear behavior for invalid active policy documents.
4. Add synthetic tests proving a complete approved policy can be activated as ENFORCE, missing coverage is rejected, the correct actor and approval evidence are recorded, and a denied consent decision is actually denied at representative protected data-use points.
5. Add production configuration tests that distinguish audit-only restrictions from the explicitly supported enforcement workflow.

**Assessment:** High-priority privacy enforcement readiness gap. Static source establishes that the application lifecycle has no reviewed API path to set `ENFORCE`, despite runtime support for that mode; the only activation API sets `AUDIT_ONLY` and rejects production. This leaves consent enforcement unavailable through the supported policy-management workflow.

**Boundary:** static source review only. No policy was activated, no database row was modified, no consent decision was executed, and no patient data was accessed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 124. Patient retention's date-of-death clock silently falls back to last-updated time

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/privacy/policy_schema.py` (`RetentionCategoryRule.clock_start`); `backend/domains/privacy/retention_service.py` (`execute_retention_category`, patient category clock selection); `backend/domains/patients/models.py` (`Patient`).

### 124.1 The configured legal-retention clock is not the clock used at runtime

The retention policy schema explicitly accepts `date_of_death` as a valid `clock_start` value. In the patient retention executor, that branch checks `hasattr(Patient, "date_of_death")`. The reviewed `Patient` ORM model has no `date_of_death` attribute, so the condition is false and the executor silently substitutes `Patient.updated_at < cutoff`.

This means a policy configured to retain records for a period measured from date of death is actually evaluated against the patient's last-update timestamp. The executor does not reject the unsupported clock, report a configuration error, or mark the category as skipped. Since the patient handler only considers inactive patients, an eligible inactive patient may be anonymized or deleted based on an unrelated update timestamp rather than the configured death-date event.

The same patient clock-selection code also maps `contract_end` to `Patient.updated_at`, rather than a contract-end field; this is recorded as a related unsupported-clock concern, not as a separate finding.

### 124.2 Required remediation and acceptance evidence

1. Make the runtime retention clock registry explicit and validate every configured clock against an actual source field or query before policy approval/execution.
2. Add a persisted, timezone/date-correct death-date source if date-of-death retention is supported; otherwise remove `date_of_death` from accepted policy values until implemented.
3. Do not silently substitute `updated_at` for unsupported clocks. Fail closed with a clear validation error and no destructive work.
4. Resolve `contract_end` similarly: provide a real contract-end source or reject the clock.
5. Add synthetic tests with deliberately different death, update, and contract-end dates proving candidate selection follows the configured clock; assert unsupported clocks cannot reach anonymization or deletion.

**Assessment:** High-priority retention correctness and data-preservation gap. Static source establishes a supported policy value that is not represented on the patient model and is silently evaluated using a different timestamp. The risk is premature or delayed anonymization/deletion relative to the approved retention rule; no claim is made that any record has actually been processed incorrectly.

**Boundary:** static source review only. No retention job was run, no patient record was queried or changed, and no destructive action was performed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 125. Prior patient hard-delete dependency-failure finding is superseded by current PR #19 source

**Source re-verification:** PR #19 head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/privacy/retention_service.py` (blob `18b45ac9ccff4e187368b690ccc3f84705a55807`).

### 125.1 Current reviewed source no longer suppresses dependency-query failures

A fresh fetch of the exact PR #19 head shows the patient hard-delete branch now performs seven dependent-table lookups directly, without the previously reported `try/except Exception: pass` wrappers: encounters, invoices, allergies, diagnostic orders, insurance policies, patient consent records, and federation transfer logs. Each query must complete before `deletable_ids` is computed. A query exception therefore propagates out of this function instead of being converted into an empty reference set.

The earlier Section 125 claim that the current source suppresses lookup failures is not supported by this exact-head re-verification and is withdrawn. This is a source-level correction only; it does not establish that PR #19 has been merged, deployed, or independently tested under injected database failures.

### 125.2 Remaining verification

1. Add synthetic fault-injection coverage for each of the seven lookups and prove the transaction/run fails without issuing a patient DELETE.
2. Verify rollback and ledger/audit behavior when a lookup fails after earlier lookups succeeded.
3. Retain Section 126 as a separate finding: the dry-run path still skips these dependency lookups and reports the unfiltered candidate count as affected.

**Assessment:** The previously recorded fail-open lookup-suppression defect is not a current finding at the reviewed PR #19 head. Runtime proof of failure/rollback behavior remains outstanding.

**Boundary:** exact-head static source review only. No retention job, patient record, tenant database, or destructive action was accessed or executed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 126. Patient hard-delete dry-run overstates eligible and affected records

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/privacy/retention_service.py` (`execute_retention_category`, patient `action == "delete"` branch and dry-run handling); `backend/domains/privacy/router.py` (`execute_retention_run`).

### 126.1 Dry-run skips the dependency guard used by destructive execution

The patient hard-delete branch performs its six dependent-table checks only under `if not dry_run and candidates`. When `dry_run=True`, it enters the `else` branch and sets `affected_count = candidate_count` without checking encounters, invoices, allergies, diagnostic orders, insurance policies, or consent records.

Consequently, a dry-run can report every inactive, age-qualified, non-held patient candidate as affected even though the corresponding destructive run would exclude patients with dependent records. The response's `candidate_count` is the pre-dependency candidate count, and its `affected_count` is also set to that same count; it does not represent the number actually eligible for deletion under the hard-delete guard.

This is a misleading safety preview for an irreversible operation. It can overstate the deletion set and does not let an operator validate the precise set that would pass the dependency checks. This finding is distinct from Section 125: Section 125 concerns suppressed dependency-query failures during destructive execution; this section concerns the dry-run path bypassing those checks altogether.

### 126.2 Required remediation and acceptance evidence

1. Run the same dependency-selection logic in dry-run and destructive modes; the only difference should be whether the final DELETE is issued.
2. Return separate, accurately defined counts for initial candidates, candidates blocked by dependencies, and deletion-eligible records.
3. Ensure dry-run and immediate execution use a shared selection implementation and equivalent transaction/consistency boundaries.
4. Add synthetic tests with a mix of dependent and dependency-free patients; assert dry-run eligible counts exactly match the set the destructive path would select.
5. Add regression tests proving dry-run never issues DELETE and dependency lookup failures are surfaced rather than converted into an empty dependency set.

**Assessment:** High-priority retention preview correctness gap. Static source establishes that the dry-run path bypasses all six patient dependency checks and reports the unfiltered candidate count as affected. No assertion is made that a dry-run itself changes data or that a real deletion has occurred.

**Boundary:** static source review only. No retention job was run, no patient record was queried or changed, and no destructive action was performed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 127. Approved retention policies can execute unsupported categories as successful no-ops

**Source reviewed:** PR #19 head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/privacy/policy_schema.py` (blob `8a9d25c580ea11e0593fa3860b6b5d78de8389b0`); `backend/domains/privacy/retention_service.py` (blob `18b45ac9ccff4e187368b690ccc3f84705a55807`); `backend/domains/privacy/retention_preview.py` (blob `3a7640d0677ce0775d3b1811d0f24e512f67e98f`); `backend/domains/privacy/router.py` (blob `e63ec483c6aec0f5e8568b82885e5f0b68d68a31`).

### 127.1 Policy approval and execution do not require an implemented category handler

`RetentionCategoryRule.code` accepts any lowercase identifier matching its pattern; the retention policy schema does not constrain it to categories with an execution implementation. Draft creation and second-person approval call `validate_policy_document("RETENTION", ...)`, which validates the document shape and unique codes but does not validate handler availability.

The preview module advertises eight standard categories: `patients`, `inactive-patients`, `privacy-decision-audits`, `synthetic-attachments`, `encounters`, `clinical-notes`, `orders`, and `billing-invoices`. However, `execute_retention_category()` has concrete execution branches only for canonical `patients` and `privacy-decision-audits`. Other category values reach the generic return with zero candidates, zero affected records, and status `NOOP_UNKNOWN_CATEGORY`.

The execution service does not treat that result as an error. `execute_retention_policy_revision()` appends it to the category results, adds its zero count to totals, and proceeds to write the retention run ledger and an ALLOW `privacy.retention.execute` audit event for a non-dry-run. The router's approved-policy and requested-category checks establish only that the requested code appears in the policy document; they do not establish that an executor exists.

Therefore a policy containing a supported-looking standard category such as `encounters`, `clinical-notes`, `orders`, or `billing-invoices` can be approved and later produce a run response that includes `NOOP_UNKNOWN_CATEGORY`, while the overall run still records execution. The policy can appear to have been processed even though no records in that category were evaluated or acted upon. The same issue applies to arbitrary custom category codes accepted by the policy schema unless a handler is explicitly added.

This is distinct from the preview registry: `preview_retention_counts()` rejects categories absent from its registry, but the execution endpoint does not require a successful preview or registry membership before dispatching the execution service. The preview registry is currently an independent counts-only adapter, not the execution-handler registry.

### 127.2 Required remediation and acceptance evidence

1. Define one authoritative retention-category registry that binds each approved category to its canonical code, aliases, preview adapter, legal-hold semantics, and executable handler.
2. Reject policy draft creation and approval when any category has no supported executor, unless the policy explicitly marks it as deferred/non-executable and prevents it from being selected for execution.
3. Before execution, validate every requested category against the executable registry; never treat `NOOP_UNKNOWN_CATEGORY` as a successful category result.
4. Make the run outcome explicitly partial/failed when any selected category is unsupported; do not write a success-shaped execution audit or ledger entry for a run that silently skipped requested categories.
5. Add synthetic tests for each advertised standard category and custom category behavior. For unsupported categories, assert rejection before execution and no success ledger/audit. For supported categories, assert candidate selection, legal-hold exclusion, and the intended action.
6. Keep counts-only preview semantics separate from mutation semantics, but require both adapters to agree on category identity and supported status.

**Assessment:** High-priority retention governance and legal-compliance readiness gap. Static source establishes that the policy lifecycle can approve categories without handlers and that execution converts unsupported categories into zero-count no-ops while continuing to record the run. This does not establish that a real retention policy has been approved or that any records were incorrectly retained or deleted.

**Boundary:** static source review only. No retention policy was created/approved, no retention job was invoked, no patient or tenant data was accessed, and no destructive action was performed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 128. Patient-scoped legal holds for privacy-decision-audits are accepted but not enforceable by the executor

**Source reviewed:** PR #19 head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/privacy/retention_service.py` (blob `18b45ac9ccff4e187368b690ccc3f84705a55807`); `backend/domains/privacy/models.py` (blob `74a4d4f61ccbb1dfda129ab93c5b19ce154c7bad`); `backend/domains/privacy/router.py` (blob `e63ec483c6aec0f5e8568b82885e5f0b68d68a31`).

### 128.1 Accepted hold scope is not consumed by the audit-retention handler

The legal-hold creation request permits both `patient_id` and `data_category` to be supplied together. The category validator canonicalizes and accepts `privacy-decision-audits`; the creation route persists both scope fields. This represents a patient-specific hold scoped to the privacy-decision-audits category.

At execution, `execute_retention_category()` loads active holds, computes `held_patient_ids`, and passes the category through the category-wide hold check. For `privacy-decision-audits`, however, the deletion candidate and DELETE statements filter only by `occurred_at`, `result`, and protected `data_use_point` values. They never consume `held_patient_ids`. The returned audit-category result also hardcodes `held_count: 0`.

The reviewed `PrivacyDecisionAudit` model contains no `patient_id` or other patient-target reference. Therefore the current executor has no key with which to select audit rows attributable to the held patient. A patient-scoped `privacy-decision-audits` hold can be accepted and stored, yet cannot protect corresponding audit rows through this handler. This is distinct from a category-wide hold, which is checked and skips the whole category.

The source does not establish that audit rows actually belong to or identify a particular patient; rather, it establishes that the API accepts a patient/category scope while the executor and model provide no patient-level association or enforcement for that combination.

### 128.2 Required remediation and acceptance evidence

1. Define legal-hold scope semantics explicitly: whether patient-only holds apply to all patient-associated records and whether patient-plus-category holds are supported for every category.
2. Until patient-level audit attribution exists, reject creation of patient-scoped `privacy-decision-audits` holds rather than accepting an unenforceable scope.
3. If patient-level audit preservation is required, add a privacy-safe, durable patient association/reference to the audit record and enforce it in both candidate-count and DELETE predicates; assess historical rows and avoid exposing patient identifiers in general audit views.
4. Ensure held counts reflect the actual excluded rows and distinguish category-wide skips from patient-specific exclusions.
5. Add synthetic tests proving a patient/category hold prevents matching audit-row deletion, a different patient's rows remain eligible, category-wide holds skip the category, and unsupported hold combinations fail at creation.

**Assessment:** High-priority legal-hold scope-integrity gap. Static source establishes that a supported hold request can express a patient/category combination that the audit executor cannot apply, and the execution result reports no held records for this category. No claim is made that an actual held patient's audit record was deleted.

**Boundary:** static source review only. No legal hold was created, no retention policy or job was executed, no patient or tenant data was accessed, and no destructive action was performed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 129. Redis enqueue failure can return a queued retention job after synchronous execution fails

**Source reviewed:** PR #19 head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/core/queue.py` (blob `aad0c663e52e7a73d7261658f5ecc1889b7e36b7`); `backend/domains/privacy/router.py` (blob `e63ec483c6aec0f5e8568b82885e5f0b68d68a31`).

### 129.1 Retention endpoint reports QUEUED regardless of synchronous fallback outcome

The retention execution endpoint calls `enqueue_task("privacy.retention.execute", ...)` in async mode and unconditionally returns `status: "QUEUED"` with the returned job ID.

The queue helper defaults `sync_fallback=True`. When Redis enqueue fails, it attempts to invoke the registered handler synchronously. That fallback wraps the handler in `try/except Exception`, logs a warning if the handler fails, and then returns the generated task ID either way. It does not persist a fallback task status/result or re-raise the handler exception. The task hash and queue entry were never successfully written to Redis in this path.

Consequently, if Redis is unavailable and the retention handler raises, the API still returns a success-shaped QUEUED response although no queued job exists and no retention result was committed by that failed handler. The job-status endpoint subsequently consults Redis via `get_task_status(job_id)`; because no task hash exists, it returns not-found. If synchronous fallback succeeds, the operation may already have run inline while the response still says QUEUED, and the same missing status record prevents the caller from retrieving its result through the job-status endpoint.

This is a retention execution observability and outcome-integrity issue. The source does not establish that Redis was unavailable in a deployed environment or that a real retention execution failed.

### 129.2 Required remediation and acceptance evidence

1. For retention execution, prefer fail-closed enqueue behavior (`sync_fallback=False`) or implement a durable fallback result/status contract that distinguishes completed-inline, failed-inline, and queued.
2. Never swallow a retention handler exception while returning a job ID that the status API cannot resolve.
3. Return `QUEUED` only after durable queue persistence succeeds; return an explicit failure or inline-completion response otherwise.
4. Persist task ownership, tenant identity, terminal status, result/error, and correlation ID in a durable job record that remains queryable through the status endpoint.
5. Add synthetic tests with Redis enqueue failure and handler success/failure. Assert the API response accurately reflects the actual outcome, no false QUEUED status is emitted, and every returned job ID has a retrievable terminal or queued state.
6. Verify retry behavior does not cause duplicate retention execution when a worker outcome is uncertain.

**Assessment:** High-priority retention execution reliability and auditability gap. Static source establishes a path where the API reports QUEUED after a synchronous handler failure has been caught and suppressed, with no Redis job record available for status lookup. No claim is made that a live retention run failed or that any patient records were affected.

**Boundary:** static source review only. No Redis queue was contacted, no retention task was enqueued or executed, no patient or tenant data was accessed, and no destructive action was performed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 130. Asynchronous retention execution can attribute the run to a substitute or arbitrary user

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/core/queue.py` (blob `aad0c663e52e7a73d7261658f5ecc1889b7e36b7`, `handle_retention_execute` and `handle_scheduled_retention_sweep`); `backend/domains/privacy/retention_service.py` (blob `18b45ac9ccff4e187368b690ccc3f84705a55807`, run-ledger and decision-audit creation); `backend/domains/privacy/router.py` (blob `e63ec483c6aec0f5e8568b82885e5f0b68d68a31`, async execution enqueue).

### 130.1 Worker substitutes the authenticated requester or invents a human executor attribution

The interactive retention endpoint enqueues the authenticated actor's `actor_user_id`. In `handle_retention_execute()`, the worker looks up that ID only if the user remains ACTIVE. If the user is no longer active, or if the actor is the policy configurator, the worker selects the first active user other than the configurator. For a scheduled sweep, no actor ID is supplied; the worker likewise selects the first active user, with a final fallback to the first user in the tenant.

The selected `actor` is passed to `execute_retention_policy_revision()`. That service writes both `PrivacyRetentionRunLedger.executed_by_user_id` and the `PrivacyDecisionAudit.actor_user_id` from the selected user's ID. Thus, when the queued requester becomes inactive before execution, the durable records can name a different user who did not request or authorize that run. Scheduled automation can also be recorded as if an arbitrary active user personally executed it. The fallback is not represented as a system/service principal or separately identified automation initiator.

The worker does retain a destructive-run separation check against the configurator, but that does not repair the attribution problem: a substitute user is still recorded as the executor without evidence that the user approved or performed the queued action. This finding concerns execution identity and audit provenance, not a demonstrated bypass of the worker's destructive-execution configuration guard.

### 130.2 Required remediation and acceptance evidence

1. Preserve the enqueue-time initiating actor as immutable job metadata, including actor ID, tenant, authorization context, request/correlation ID and enqueue timestamp.
2. At execution, fail closed if a human-initiated job's actor is no longer active or no longer authorized; do not silently substitute another user.
3. Model scheduled/system execution with a dedicated non-human service principal and explicit trigger identity. Do not attribute automated runs to the first tenant user.
4. Store distinct fields for initiator, approving authority, executing workload/service principal and (where applicable) human operator; define which identity populates each audit field.
5. Revalidate policy approval, actor authorization and separation-of-duties at execution time without changing the original initiator identity.
6. Add synthetic tests for an active requester, requester deactivated after enqueue, configurator mismatch, no actor on scheduled sweep, no active users, and retries. Assert ledger and decision-audit identities remain truthful and no substitute human is silently attributed.

**Assessment:** High-priority privacy-retention audit provenance and accountability gap. Static source establishes that worker fallback can record a substitute or arbitrary human user as the executor. It does not establish that a queued run has actually taken this path or that a retention action was performed by an unauthorized person.

**Boundary:** exact-head static source review only. No queue was contacted, no retention job or policy was executed, no user/account or tenant database was queried at runtime, no patient data was accessed, and no destructive action was performed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 131. Retention queue dequeue has no visibility lease or crash-recovery path

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/core/queue.py` (blob `aad0c663e52e7a73d7261658f5ecc1889b7e36b7`), specifically `dequeue_task()`, `mark_task_failed()`, `mark_task_completed()`, and `enqueue_task()`; retention execution is registered as `privacy.retention.execute`.

### 131.1 A worker interruption can strand or lose a dequeued retention job

The queue consumer helper obtains a task ID with Redis `BLPOP`, which removes it from the pending list. It then separately reads the task hash and sets its status to `PROCESSING`. There is no atomic move into a processing/visibility-timeout list, no lease expiry or heartbeat, and no startup/reaper path in this queue module that requeues stale `PROCESSING` tasks. The retry helper is invoked only when execution code explicitly calls `mark_task_failed()`; it is not coupled to the dequeue operation or worker liveness.

Therefore, an interruption after `BLPOP` can leave the task absent from the pending queue. Depending on the exact interruption point, the task hash can remain QUEUED or PROCESSING, but there is no demonstrated automatic recovery from either state. The ordinary task hash is initially given a 24-hour TTL; successful completion shortens it to one hour. A retention request can consequently remain unprocessed or become unqueryable without being retried, despite having been accepted by the API.

This finding is about queue delivery/recovery. It does not establish that a worker crash occurred, that a retention database transaction was partially committed, or that any patient data was changed.

### 131.2 Required remediation and acceptance evidence

1. Use an atomic reliable-queue pattern (for example, pending-to-processing list move) with a visibility lease, heartbeat and bounded recovery of expired processing claims.
2. Persist attempt count, lease owner, lease expiry, last heartbeat, enqueue time and terminal outcome; do not rely on a short-lived Redis hash as the only job record.
3. Ensure the recovery mechanism safely requeues interrupted work and does not allow concurrent workers to execute the same job.
4. Add a stable execution/idempotency key and a tenant-database execution ledger with a uniqueness constraint so a retry after an uncertain worker outcome cannot duplicate the logical retention run.
5. Add synthetic fault-injection tests for interruption immediately after dequeue, after marking PROCESSING, during handler execution, after tenant DB commit but before queue completion, and during retry scheduling. Assert every accepted job reaches a queryable terminal state or a recoverable queued state, and that one logical destructive execution produces at most one ledger record.
6. Verify dead-letter handling and operator-visible recovery do not silently discard or replay a completed destructive action.

**Assessment:** High-priority background retention delivery and recovery gap. Static source establishes destructive queue tasks are removed from pending before processing and that the shown queue module provides no visibility lease or stale-processing recovery. The database-commit/queue-completion crash window remains an acceptance-test requirement; it is not asserted as an observed runtime event.

**Boundary:** exact-head static source review only. No Redis instance, worker, retention job, policy, tenant database or patient record was accessed or executed. No destructive action was performed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 132. Retention execution has no durable idempotency fence for retries or uncertain completion

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/core/queue.py` (blob `aad0c663e52e7a73d7261658f5ecc1889b7e36b7`, enqueue/dequeue and retention handler); `backend/domains/privacy/retention_service.py` (blob `18b45ac9ccff4e187368b690ccc3f84705a55807`, `execute_retention_policy_revision()`); `backend/domains/privacy/models.py` (blob `74a4d4f61ccbb1dfda129ab93c5b19ce154c7bad`, `PrivacyRetentionRunLedger`).

### 132.1 The queue task identity is not bound to a unique tenant execution record

`enqueue_task()` generates a UUID task ID and stores it in Redis task metadata. The retention handler receives the decoded payload and extracts tenant, policy revision, category codes, dry-run flag, approval reference and optional actor ID; it does not receive or forward the queue task ID as an execution/idempotency key. `execute_retention_policy_revision()` likewise accepts no job ID or idempotency key.

For a non-dry-run, the service performs the selected category actions and then inserts a `PrivacyRetentionRunLedger` row and a `PrivacyDecisionAudit` row before committing the tenant transaction. The ledger model has an ordinary primary key but no unique execution-key column or uniqueness constraint over a logical run identity. The service does not query for an existing matching run or return a previously committed result. The audit row is also appended for each invocation.

Accordingly, the durable tenant database does not fence a repeated invocation of the same logical queued request. If execution commits its tenant transaction but the worker subsequently reports failure (or otherwise cannot record queue completion) and the task is retried, the same policy revision/categories/approval reference can be executed again and produce another run-ledger and audit record. The repeated invocation may also re-evaluate and act on records changed by the first invocation; whether that produces additional destructive effects depends on the category/action and remaining eligible records. This is a source-level retry/idempotency gap, not evidence that a retry or duplicate retention run occurred.

This is distinct from Section 131: Section 131 concerns a dequeued task being stranded after worker interruption; this section concerns duplicate logical execution when a retry is attempted after an uncertain or already-committed outcome. It is also distinct from Section 129's false QUEUED response on synchronous fallback.

### 132.2 Required remediation and acceptance evidence

1. Generate and persist a stable execution/idempotency key at request/enqueue time, scoped to the tenant and logical retention request; carry it unchanged through queue metadata, handler, service, run ledger and audit correlation.
2. Add a non-null unique constraint for the execution key on `PrivacyRetentionRunLedger` (with an explicit migration and backfill policy), and make the service atomically claim/check that key before applying category mutations.
3. On duplicate delivery, return the original committed run result/status rather than reapplying actions or appending a second success ledger/audit pair. Define behavior for an in-progress claim and stale claim recovery.
4. Keep distinct keys for genuinely separate authorized runs, even when they target the same policy revision and categories; do not use a coarse uniqueness constraint that blocks legitimate later executions.
5. Add synthetic transaction/fault-injection tests for: duplicate delivery before execution, concurrent delivery to two workers, commit followed by simulated queue-completion failure, retry after commit, rollback before commit, and two separately authorized executions. Assert one logical request has at most one committed execution ledger and one corresponding execution audit, while separate authorized requests remain possible.
6. Tie the durable execution record to tenant identity, policy revision, normalized category set, approval reference, initiating actor/service principal and final outcome; preserve the original execution result for status recovery.

**Assessment:** High-priority destructive-retention reliability and audit-integrity gap. Static source establishes that the queue task UUID is not propagated into the retention service/ledger and that the ledger has no unique idempotency field or matching-run guard. It supports a duplicate-execution scenario if a committed handler attempt is retried, but does not establish that the worker actually retried after commit or that any patient record was changed more than once.

**Boundary:** exact-head static source review only. No Redis instance, worker, retention job, policy, tenant database or patient record was accessed or executed. No destructive action was performed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 133. Retention execution can miss a legal hold committed during execution

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/privacy/retention_service.py` (blob `18b45ac9ccff4e187368b690ccc3f84705a55807`, `get_active_legal_holds()` and `execute_retention_category()`); `backend/domains/privacy/router.py` (blob `e63ec483c6aec0f5e8568b82885e5f0b68d68a31`, legal-hold create/release and retention execution routes); `backend/core/database.py` (blob `043f4ccbdad4d2bfe4c89af0b46988ce60610b01`, tenant session configuration).

### 133.1 Hold state is read once, without a concurrency fence before mutation

Each call to `execute_retention_category()` loads active legal holds through `get_active_legal_holds()`, computes category-wide and patient-specific hold sets, and then performs candidate selection and mutation using those in-memory results. The patient anonymisation loop and the privacy-decision-audit DELETE do not re-query or lock the relevant hold rows immediately before mutation. The hard-delete patient branch also relies on the initially computed patient hold set; foreign-key dependencies may independently prevent some deletes, but they do not protect updates such as anonymisation.

The legal-hold creation route independently validates the patient (when patient-scoped), inserts a `PrivacyLegalHold`, and commits. It does not acquire a lock or shared serialization primitive that coordinates with a retention execution already in progress. The release route locks the individual hold row, but retention does not lock those rows when reading active holds. The tenant session configuration does not set a stronger transaction isolation level; PostgreSQL's normal READ COMMITTED behavior therefore does not make the earlier hold query a transaction-wide snapshot.

A concrete race is possible: retention reads the active-hold set; a second authorized request creates and commits a patient-scoped hold; the first retention transaction then anonymises that patient using its stale in-memory hold set and commits. A similar window exists for a category-wide hold and category-level audit deletion, because the hold row has no foreign-key relationship to the audit rows being deleted. The source establishes the missing coordination and stale-read window, not that this interleaving has occurred in a deployed environment.

### 133.2 Required remediation and acceptance evidence

1. Define a serialization protocol shared by hold creation/release and retention execution. A hold must not be acknowledged as effective while an in-flight retention transaction can still mutate its protected scope without observing it.
2. Use a tenant-scoped lock or equivalent concurrency-control mechanism acquired by both legal-hold mutations and retention execution, with a documented lock order and bounded timeout; alternatively use a serializable/claim protocol with explicit retry handling.
3. Revalidate applicable active holds at the mutation boundary, not only once before candidate selection. Ensure patient-scoped and category-wide scopes use the same canonical category semantics in both preview and mutation paths.
4. For destructive operations, define whether a hold created concurrently wins or whether the hold request must wait until the in-flight retention operation completes; expose that behavior to the caller and audit it.
5. Add deterministic PostgreSQL concurrency tests using transaction barriers: create a patient hold after retention's initial hold read but before anonymisation; create a category hold before audit deletion; release a hold concurrently; and verify the chosen serialization outcome. Assert no protected record is mutated after the hold is accepted as effective.
6. Keep the existing same-session atomicity guarantee: category mutations, run ledger and execution audit should still commit or roll back together.

**Assessment:** High-priority legal-hold enforcement and retention concurrency gap. Static source establishes that retention uses an earlier in-memory hold set while legal-hold creation commits independently, with no shared lock or mutation-boundary revalidation. It supports a race in which a newly committed hold can be missed by an in-flight anonymisation or category-wide audit-retention operation. It does not establish that a real hold was bypassed or that any patient/audit record was changed.

**Boundary:** exact-head static source review only. No legal hold was created or released, no retention policy/job was run, no tenant database or patient record was accessed, and no destructive action was performed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 134. Scheduled retention sweep executes approved revisions without requiring active status

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/core/queue.py` (blob `aad0c663e52e7a73d7261658f5ecc1889b7e36b7`, `handle_scheduled_retention_sweep()` and `handle_retention_execute()`); `backend/domains/privacy/router.py` (blob `e63ec483c6aec0f5e8568b82885e5f0b68d68a31`, policy approval, deactivation and manual retention execution); `backend/domains/privacy/models.py` (blob `74a4d4f61ccbb1dfda129ab93c5b19ce154c7bad`, `PrivacyPolicyRevision.is_active` and activation constraints); `backend/domains/privacy/retention_service.py` (blob `18b45ac9ccff4e187368b690ccc3f84705a55807`, execution service precondition).

### 134.1 Scheduler and worker use approval status but omit the active-state fence

The scheduled-sweep handler's docstring says it enqueues execution for "approved active retention policy revisions." Its tenant query filters only `policy_type == "RETENTION"` and `status == "APPROVED"`, orders by revision ID descending, and selects the first result. It does not add `is_active IS TRUE`. It then validates the document and enqueues every category in that revision.

The retention worker re-loads the revision with the same policy-type and APPROVED-status predicates, again without checking `is_active`. `execute_retention_policy_revision()` itself rejects only a non-RETENTION or non-APPROVED revision. The synchronous execution route likewise checks approval status and approval metadata, but not active state. Therefore the active flag is not revalidated at the execution boundary either.

This is material because `PrivacyPolicyRevision.is_active` is an explicit persisted lifecycle field, defaults to false, and is constrained separately from approval status. The shared deactivation endpoint can set an active revision to `is_active = false` and `enforcement_mode = "OFF"` without changing its APPROVED status. A scheduled sweep can consequently select an approved-but-inactive retention revision, and the worker/service accept it based on approval alone. A revision that becomes inactive after enqueue is also not rejected by the worker. This is a source-level lifecycle-fence gap; it does not establish that an inactive revision was actually scheduled or that a destructive run occurred.

### 134.2 Required remediation and acceptance evidence

1. Define the intended retention lifecycle explicitly: if scheduled execution is meant to follow activation, require `is_active IS TRUE` in scheduler selection, worker reload and service execution preconditions.
2. Recheck active status immediately before execution, not only at enqueue time. If deactivation races with an already queued job, define and enforce whether deactivation cancels queued work or waits for in-flight execution.
3. If retention approval itself is intentionally sufficient authorization and `is_active` is not intended to govern retention, remove the misleading "active" scheduler contract and document a separate, explicit scheduled-execution authorization state rather than leaving an unused ambiguous lifecycle flag.
4. Add PostgreSQL-backed tests for: approved/inactive revision excluded from scheduled enqueue; active revision queued then deactivated before worker execution; active revision remains executable; and manual execution behavior matches the documented lifecycle.
5. Ensure execution ledger/audit records the lifecycle state and decision that authorized the run, including a fail-closed outcome when a revision is no longer eligible.

**Assessment:** High-priority retention authorization/lifecycle consistency gap for scheduled and queued execution. Static source establishes that scheduler, worker and service rely on APPROVED status but omit the persisted active-state check. It supports execution of an approved-but-inactive revision, including one deactivated after enqueue; it does not establish an actual scheduled run or data mutation.

**Boundary:** exact-head static source review only. No scheduler, queue worker, policy, tenant database or patient record was accessed or executed. No retention job or destructive action was performed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 135. Scheduled retention sweep reports success after swallowing tenant-level failures

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/core/queue.py` (blob `aad0c663e52e7a73d7261658f5ecc1889b7e36b7`, `handle_scheduled_retention_sweep()`).

### 135.1 Per-tenant failures are logged but omitted from the sweep result

The scheduled retention sweep iterates active `TenantRegistry` entries. For each tenant, it opens the tenant database session, locates an approved retention revision, validates its policy document, and enqueues the retention execution. The per-tenant processing block catches every `Exception`, emits a warning log, and continues to the next tenant.

After the loop, the handler unconditionally returns `{"status": "SUCCESS", "enqueued_tenants": executed_tenants, "dry_run": safe_dry_run}`. It does not collect failed tenant identifiers, failure reasons, or a failure count, and it does not return a partial-success/failure status. If a tenant's policy lookup, validation, session work, or enqueue operation raises inside the guarded block, that tenant is skipped while the overall sweep still reports SUCCESS. A caller relying on the handler's status cannot distinguish a complete sweep from one that skipped tenants.

The `executed_tenants` name also represents tenants whose enqueue call returned, not proof that their retention worker subsequently completed. This finding is limited to the scheduler's aggregate reporting contract; it does not assert that any tenant failed or that any retention execution was lost in practice. Queue fallback behavior is tracked separately and is not relied upon for this finding.

### 135.2 Required remediation and acceptance evidence

1. Return explicit per-tenant outcomes, such as `ENQUEUED`, `NO_APPROVED_POLICY`, and `FAILED`, with a bounded/sanitized error code and correlation ID; do not expose sensitive exception details.
2. Return an aggregate status that distinguishes `SUCCESS`, `PARTIAL_FAILURE`, and `FAILURE`, together with attempted, enqueued, skipped and failed counts.
3. Persist a durable sweep-run record and per-tenant outcome so monitoring can detect incomplete sweeps even if the scheduler process exits after returning.
4. Add synthetic tests with multiple tenants where one tenant's policy lookup, document validation, and enqueue each fail in turn; assert remaining tenants are still processed and the aggregate result reports the failure.
5. Alert on partial or total failure and define retry/reconciliation behavior for failed tenants without creating duplicate logical executions.

**Assessment:** High-priority scheduled-retention observability and operational reliability gap. Static source establishes that tenant-level exceptions are caught and suppressed from the returned aggregate status. It does not establish an actual tenant failure, missed execution, or destructive data operation.

**Boundary:** exact-head static source review only. No scheduler, queue worker, policy, tenant database or patient record was accessed or executed. No retention job or destructive action was performed. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 136. Retention job status lookup is not bound to the requesting tenant

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/privacy/router.py` (blob `e63ec483c6aec0f5e8568b82885e5f0b68d68a31`, `GET /api/privacy/retention/jobs/{job_id}`); `backend/core/queue.py` (blob `aad0c663e52e7a73d7261658f5ecc1889b7e36b7`, `KEY_TASK_PREFIX` and `get_task_status()`).

### 136.1 A tenant-authorized caller can query any known global task ID

The retention status route requires `RequirePermission("privacy:read")`, but it does not use the resolved tenant context or compare the job with a tenant-owned execution record. It passes the caller-supplied `job_id` directly to the global queue helper. In the queue module, task hashes use the process-wide `avinya:task:` prefix rather than a tenant-qualified key, and `get_task_status()` performs `HGETALL` for that ID without a tenant check.

The returned status object includes task ID, task name, status, retry counts, creation/scheduled/completion timestamps and the stored error string. The route's `actor` dependency is not otherwise used. Therefore, if a user with `privacy:read` in tenant A obtains a valid retention job UUID belonging to tenant B, the same endpoint can return tenant B's queue metadata and error text. UUID unpredictability limits blind enumeration, so this is not an unauthenticated endpoint or proof that another tenant's ID is readily discoverable. It is a cross-tenant object-authorization gap once an ID is known.

This is distinct from Section 131's worker crash/recovery behavior and Section 135's scheduler aggregate reporting. It concerns read authorization for a job-status resource, not job execution or mutation.

### 136.2 Required remediation and acceptance evidence

1. Persist a durable job/execution record with tenant identity, opaque job ID, initiating principal/service identity and policy revision; authorize every status read against that tenant record.
2. Alternatively, use tenant-qualified queue namespaces and enforce tenant binding at the API boundary; do not treat UUID secrecy as authorization.
3. Return only the minimum status fields required by the caller. Sanitize or classify worker error details before exposing them through tenant-facing APIs.
4. Add PostgreSQL/Redis integration tests: tenant A can read its own job; tenant A receives the same non-disclosing not-found response for tenant B's known job ID; tenant B can read its own job; unauthorized permissions cannot read either; expired jobs have defined behavior.
5. Keep operator-wide fleet inspection separate, explicitly privileged, audited and scoped to an approved operational purpose.

**Assessment:** Medium-priority cross-tenant job-metadata confidentiality and object-authorization gap. Static source establishes a global queue-key lookup with no tenant ownership check in the route/helper. The cross-tenant disclosure scenario requires the caller to know a valid other-tenant job ID; no such ID disclosure or unauthorized status read was observed.

**Boundary:** exact-head static source review only. No Redis instance, job status, worker, tenant database, policy or patient record was accessed. No task was executed or modified. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 137. Consent-policy activation deactivates active revisions across all policy types

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/privacy/router.py` (blob `e63ec483c6aec0f5e8568b82885e5f0b68d68a31`, `activate_privacy_policy_audit_only()`, lines 282–340); `backend/domains/privacy/models.py` (blob `74a4d4f61ccbb1dfda129ab93c5b19ce154c7bad`, `PrivacyPolicyRevision` policy-type and active-state fields).

### 137.1 The activation endpoint's deactivation query is not scoped to consent policies

The endpoint is specifically `POST /policies/{revision_id}/activate-audit-only`. It validates that the target revision has `policy_type == "CONSENT"` and `status == "APPROVED"`. It then selects every `PrivacyPolicyRevision` whose `is_active` flag is true, using `with_for_update()`, but the query does not constrain `policy_type`. The loop sets every selected revision to inactive and changes its enforcement mode to `OFF`, clearing its mode-approval metadata. Only after that does the handler activate the requested consent revision in `AUDIT_ONLY` mode and commit.

Because the model supports distinct policy types, the broad query includes any active retention revision (and any other active policy type represented by the model), not merely a prior consent revision. Thus, activating a consent policy can silently deactivate an unrelated active retention policy in the same tenant database. The endpoint's deployment guards and second-person check do not narrow the query's scope.

This is a source-level unintended cross-policy lifecycle side effect. No policy was activated or deactivated during this review, and no production impact is claimed.

### 137.2 Required remediation and acceptance evidence

1. Scope the deactivation query to the same `policy_type` as the target revision, unless a documented global mutual-exclusion rule is explicitly intended and approved.
2. If policy types are intentionally mutually exclusive, encode that invariant explicitly in the model/service contract and make the endpoint name, audit reason and operator confirmation accurately describe the global effect.
3. Add PostgreSQL-backed tests with an active approved CONSENT revision and an active approved RETENTION revision; activating a new consent revision must preserve retention activation unless the approved product rule explicitly says otherwise.
4. Test two concurrent activations of different policy types and verify the locking/serialization rule cannot produce an unintended inactive state or overwrite the wrong revision's mode metadata.
5. Ensure the decision audit records every revision changed by a global operation, or records only the correctly scoped target and prior same-type revision when activation is type-local.

**Assessment:** High-priority privacy-policy lifecycle integrity gap. Static source establishes that the consent activation handler deactivates all active revision types because its selection predicate omits `policy_type`. It supports unintended retention-policy deactivation as a direct consequence if such an active revision exists; it does not establish that this operation has occurred in a deployed tenant.

**Boundary:** exact-head static source review only. No policy was activated/deactivated, no tenant database or patient data was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 138. Concurrent consent submissions can create duplicate current grants

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/privacy/router.py` (blob `e63ec483c6aec0f5e8568b82885e5f0b68d68a31`, `record_patient_consent()`, lines 801–918); `backend/domains/privacy/models.py` (blob `74a4d4f61ccbb1dfda129ab93c5b19ce154c7bad`, `PatientConsentRecord`, lines 26–56).

### 138.1 The current-grant check and insert are not concurrency-safe

For a consent GRANTED submission, `record_patient_consent()` queries the latest record for the patient, consent type, purpose, scope type and scope key (and, when present, the active policy revision). If that latest record is a non-expired GRANTED record, the route rejects the new grant with HTTP 409. Otherwise it constructs a new `PatientConsentRecord` and commits it.

The read/check and subsequent insert are separate SQL operations in the request transaction. The route does not lock a stable patient/scope row, use a serializable transaction with retry handling, or otherwise serialize competing submissions. The `PatientConsentRecord` model has no uniqueness constraint or partial unique index enforcing one current grant for the matching consent identity. Under PostgreSQL READ COMMITTED, two concurrent requests can both read no current grant (or the same older non-grant/expired record), both pass the duplicate check, and both commit a new GRANTED row.

The same check-then-insert structure also merits concurrency coverage for withdrawal: concurrent withdrawals can both observe the same current grant and append separate WITHDRAWN records. The directly established risk is duplicate current grants from concurrent GRANTED requests; no concurrent submissions or duplicate records were observed during this static review.

### 138.2 Required remediation and acceptance evidence

1. Define the canonical consent identity for uniqueness, including patient, consent type, purpose, scope type/key and policy revision semantics. Define how nullable `scope_key` participates.
2. Serialize consent mutations for that identity using a stable lock target (for example, a patient/consent-scope advisory lock or a dedicated identity row) and re-read the latest decision after acquiring the lock.
3. Alternatively or additionally, enforce the chosen invariant with a PostgreSQL constraint/index where the data model can express it safely; do not rely on an application-only pre-insert check.
4. Apply the same serialization protocol to GRANTED, DECLINED and WITHDRAWN transitions so concurrent transitions have a deterministic order and cannot both claim to be the latest effective decision.
5. Add deterministic PostgreSQL concurrency tests with two transactions submitting the same grant, two withdrawals, and a grant racing a withdrawal. Assert one valid ordered outcome and no duplicate current grant; test separate scopes and policy revisions remain independent.
6. Preserve append-only consent history and actor/evidence attribution while enforcing the concurrency invariant.

**Assessment:** High-priority consent-state integrity gap. Static source establishes a check-then-insert path without row/advisory locking or a database uniqueness fence for the matching consent identity. It supports duplicate current grants under concurrent submissions; it does not establish that such a race has occurred or that downstream access was granted because of duplicate rows.

**Boundary:** exact-head static source review only. No consent was created, withdrawn or modified; no patient record or tenant database was accessed; no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 139. Consent recording accepts purposes absent from the active consent policy

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/privacy/router.py` (blob `e63ec483c6aec0f5e8568b82885e5f0b68d68a31`, `record_patient_consent()`, lines 801–918); `backend/domains/privacy/policy_schema.py` (versioned `ConsentPolicyV1` and `PurposeRule`); `backend/domains/privacy/models.py` (blob `74a4d4f61ccbb1dfda129ab93c5b19ce154c7bad`, `PatientConsentRecord`, lines 26–56).

### 139.1 Unknown purpose codes bypass active-policy validation

When an active CONSENT policy exists, the route looks up `payload.purpose` in that policy's `purposes` list. If a match exists, it records the active policy revision and applies scope, consenter, capture-method, evidence-reference and fixed-term expiry checks as applicable.

If no purpose matches, however, `purpose_rule` and `policy_revision_id` remain `None`; the route does not reject the request. It skips the entire active-policy validation block and persists the supplied consent record with no policy revision association. The request model accepts an arbitrary nonblank purpose string (3–255 characters), and the record model likewise stores purpose as an unconstrained string. The versioned policy schema defines a bounded purpose allowlist, so an active policy can silently fail to govern a submitted purpose rather than rejecting it.

This permits consent rows to be recorded for misspelled, obsolete or otherwise unconfigured purpose values while a policy is active. The row is not linked to that active revision, and this static finding does not establish that it is consumed by the data-use decision engine or that it authorizes any data use.

### 139.2 Required remediation and acceptance evidence

1. When an active consent policy exists, reject any submitted purpose code not present in its purpose list; do not silently fall back to an unversioned consent record.
2. If legacy/unmanaged consent capture is intentionally supported, expose it as an explicit separately authorized workflow with a distinct state and clear downstream non-authoritative semantics.
3. Validate canonical purpose codes consistently (including case/whitespace behavior) and ensure the persisted record references the policy revision whose rule was applied.
4. Add PostgreSQL/API tests for a valid configured purpose, unknown purpose, misspelled purpose, retired purpose, and no-active-policy compatibility behavior. Assert unknown values cannot create records under an active policy.
5. Confirm downstream decision evaluation only consumes consent evidence bound to the exact policy revision and purpose it is intended to satisfy.

**Assessment:** Consent-policy integrity gap. The active-policy branch explicitly skips all policy-specific validation when the supplied purpose is not found. No actual invalid consent record or downstream disclosure was observed.

**Boundary:** exact-head static source review only. No consent was created or modified; no patient record or tenant database was accessed; no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 140. Guardian and representative consent authority is recorded as an assertion, not verified

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/privacy/router.py` (blob `e63ec483c6aec0f5e8568b82885e5f0b68d68a31`, `ConsentRecordCreate` and `record_patient_consent()`); `backend/domains/privacy/policy_schema.py` (blob `8a9d25c580ea11e0593fa3860b6b5d78de8389b0`, `PurposeRule`); `backend/domains/privacy/models.py` (blob `74a4d4f61ccbb1dfda129ab93c5b19ce154c7bad`, `PatientConsentRecord`).

### 140.1 Consenter category is accepted without an authority-validation boundary

The request model permits `consenter_type` values `patient`, `guardian` and `representative`. When an active consent policy contains a matching purpose, the route checks whether that category appears in the purpose's configured `consenters` list. For a GRANTED decision, it also checks the configured capture method and requires a nonblank `evidence_reference`.

Those checks establish that the submitted category is allowed by the policy and that the caller supplied an evidence-reference string. They do not establish who the guardian or representative is, their relationship to the patient, the legal or delegated basis for their authority, whether that authority is current, or whether the referenced evidence was verified. `PatientConsentRecord` stores the category, reference and recording user, but has no structured authority subject, relationship, verification status, verifier or verification timestamp. The reviewed route does not resolve or validate such information before persisting the GRANTED record.

This is a source-level evidence/authority assurance gap, not proof that every guardian or representative consent is invalid. A hospital may hold supporting evidence in an external workflow, but the reviewed endpoint does not bind that workflow's verification result to the consent record. No consent was submitted and no patient data was accessed.

### 140.2 Required remediation and acceptance evidence

1. Define the permitted legal/delegated authority types and the evidence required for each (including age/capacity and emergency exceptions where applicable).
2. Introduce a verifiable authority record or trusted verification result, linked to the patient, named consenter, scope, consent event and evidence artifact; do not treat a free-form reference string as proof.
3. Require verified authority before accepting a guardian/representative GRANTED decision; record verifier identity, verification time, method and outcome. Keep patient-self consent on its appropriate separate path.
4. Define revocation/expiry and re-verification behavior when guardianship or delegated authority ends or changes.
5. Add API/PostgreSQL tests for valid, missing, mismatched, expired, revoked and unverified authority, including attempts to reuse one patient's authority for another patient.
6. Ensure downstream consent decisions can distinguish verified representative consent from unverified or legacy records and fail closed where the applicable policy requires verified authority.

**Assessment:** High-priority consent evidence integrity gap. The reviewed route validates only the declared consenter category against policy and the presence of an evidence-reference string; it contains no authority-verification step or structured binding to verified authority. This does not establish actual misuse, legal invalidity of a particular record, or downstream disclosure.

**Boundary:** exact-head static source review only. No consent was created or modified, no authority evidence was accessed, no patient record or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 141. Privacy-policy deactivation lacks the independent approval and rationale required at activation

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/privacy/router.py` (blob `e63ec483c6aec0f5e8568b82885e5f0b68d68a31`), `activate_privacy_policy_audit_only()` and `deactivate_privacy_policy()`; `backend/domains/privacy/models.py` (blob `74a4d4f61ccbb1dfda129ab93c5b19ce154c7bad`), `PrivacyPolicyRevision`.

### 141.1 Deactivation can turn an active policy OFF without a second-person decision record

The audit-only activation endpoint requires `privacy:approve`, verifies the activating actor differs from the policy configurator, accepts a validated `PrivacyPolicyModeApproval` payload with an approval reference, and writes a mode-change audit event identifying the actor.

By contrast, `POST /policies/{revision_id}/deactivate` accepts no request payload. It requires only `privacy:approve`; if the revision is active, it sets `is_active=False`, changes `enforcement_mode` to `OFF`, clears the mode-set actor/time/reference fields, and writes a `PrivacyDecisionAudit` event with a fixed reason code. It does not require the actor to differ from the configurator or the prior mode approver, does not collect a deactivation rationale or approval reference, and does not capture a second approver. The row lock serializes updates to that revision but does not supply the missing governance authorization.

Consequently, a single user holding `privacy:approve` can disable an active policy through this route without the independent approval evidence required by the corresponding activation route. This is a conditional authorization/governance gap; the reviewed source does not establish that such a user has misused the endpoint or that production ENFORCE mode is available. No policy was activated or deactivated.

### 141.2 Required remediation and acceptance evidence

1. Define whether emergency deactivation is permitted and the exact roles/conditions that may invoke it.
2. Require a structured deactivation request with reason, reference, requested-by identity and (for ordinary operation) an independent approver distinct from the configurator and requester.
3. Preserve immutable before/after mode, revision, actor, approver, reason, timestamp and approval reference in a durable audit record; do not erase the historical approval metadata without retaining its prior values.
4. If emergency single-person deactivation is necessary, make it a separately permissioned, time-bounded break-glass path with mandatory justification, alerting and retrospective independent review.
5. Add PostgreSQL/API tests for self-deactivation, same-approver deactivation, missing/blank rationale, unauthorized roles, emergency-path constraints, concurrent requests and complete audit attribution.

**Assessment:** High-priority policy-governance gap. The deactivation route can set an active revision to OFF with one permission-bearing actor and no supplied rationale or independent approval. This does not establish actual policy disablement, patient-data disclosure, or production impact.

**Boundary:** exact-head static source review only. No endpoint was called, no policy state was changed, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 142. Personal-data breach incident updates permit arbitrary lifecycle transitions without an attributable change history

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/privacy/router.py` (blob `e63ec483c6aec0f5e8568b82885e5f0b68d68a31`), `BreachIncidentUpdate` and `update_data_breach_incident()`; `backend/domains/privacy/models.py` (blob `74a4d4f61ccbb1dfda129ab93c5b19ce154c7bad`), `PrivacyDataBreachIncident`.

### 142.1 Status and reporting milestones are mutable without transition or audit controls

The breach incident API exposes statuses REPORTED, INVESTIGATING, CONTAINED, RESOLVED and CLOSED. The PATCH route accepts any value from that enum and assigns it directly; it does not enforce an allowed transition graph or require prerequisite evidence before moving to RESOLVED/CLOSED. For example, the reviewed handler can set CLOSED without checking that containment, authority reporting, affected-subject notification or a resolution summary has been recorded. It also allows severity to be overwritten at any time.

The same handler sets `contained_at` and `reported_to_authority_at` when the corresponding boolean is true, but does not persist who performed those milestones or the reporting reference/evidence. The model has no incident-event/history table or per-change actor fields beyond the original `reported_by_user_id`; the update handler writes no `PrivacyDecisionAudit` or other attributable transition event. A later status/severity update therefore overwrites the current state without a durable application-level record of the prior value, actor, timestamp and rationale.

This is distinct from the DPDP data-rights request lifecycle finding in Section 119: this finding concerns the separate personal-data breach incident register and its containment/reporting/notification milestones. It is a source-level governance and incident-evidence gap, not proof that an incident was incorrectly closed or that any statutory notification was missed. No incident record was read or changed.

### 142.2 Required remediation and acceptance evidence

1. Define an explicit transition graph and reject invalid transitions, including closure before required containment, assessment, reporting/notification decisions and documented resolution.
2. Make reporting and notification milestones evidence-bearing: record responsible actor, event time, destination/authority, reference or evidence artifact, outcome and applicable deadline.
3. Add an append-only incident event log recording old/new status and severity, actor, timestamp, rationale and linked evidence for every change.
4. Require a resolution summary and authorized review before RESOLVED/CLOSED; define controlled reopening and severity-reassessment paths.
5. Add PostgreSQL/API tests for every permitted and forbidden transition, concurrent updates, audit completeness, missing milestone evidence and reopening; ensure direct ORM/bulk paths cannot silently bypass the intended history controls.

**Assessment:** High-priority breach-response governance gap. The API permits arbitrary enum-valid status changes and does not record attributable change history or evidence for key reporting milestones. This does not establish a real breach, missed notification, or regulatory non-compliance event.

**Boundary:** exact-head static source review only. No breach endpoint was called, no incident records or patient data were accessed, no tenant database was queried, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 143. HL7 integration-log reader exposes patient-identifiable laboratory payloads under equipment-master read permission

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/integrations/router.py` (blob `ceba912675b3525197055a0ffea944fe604d179b`), `view_integration_logs()`; `backend/domains/integrations/models.py` (blob `32d40b58d6dec8056729533c30f193f413cba096`), `HL7IntegrationLog`; `backend/domains/integrations/service.py` (blob `68fcd948f6460b2c05f9343bd563dee769704a3d`), `redact_hl7_security()` and successful ORU log persistence.

### 143.1 Raw clinical content is retained and returned by the troubleshooting endpoint

The `GET /api/equipment/logs` route requires only `mdm:read`, selects recent `HL7IntegrationLog` ORM rows, and returns those rows directly without a response projection or field-level redaction. The model includes a non-null `raw_payload` text field. The successful ORU processing path persists the incoming message in that field after calling `redact_hl7_security()`.

That helper redacts only MSH-8, described in its docstring as the security token. It leaves the other HL7 segments and fields intact. In an ORU^R01 message those segments can include patient identifiers/demographics (for example PID fields) and clinical observations/results (OBX fields). Because the log route serializes the full ORM object, a user granted equipment-master read permission can retrieve those stored patient-identifiable clinical payloads without a separate patient-data or privacy-log permission check.

This is distinct from Section 113, which concerns authentication accepted by the inbound ORU endpoint. Section 143 concerns the outbound read path and excessive disclosure from stored integration logs. The source establishes the capability and data shape, not that a particular user has the permission or has accessed any log. No integration logs or patient data were read.

### 143.2 Required remediation and acceptance evidence

1. Replace raw-message logging with a minimum-necessary structured record: message control ID, equipment, processing status, timestamps and non-sensitive diagnostics; do not retain full PID/OBX content in ordinary troubleshooting logs.
2. If raw payload retention is operationally necessary, place it in a separately protected, encrypted, access-audited store with explicit purpose, retention, expiry and tightly scoped roles.
3. Make the ordinary log endpoint return an explicit response schema that excludes `raw_payload` and any other patient-identifying content; require a dedicated audited permission for exceptional access.
4. Add synthetic ORU tests containing fake PID and OBX values proving that ordinary `mdm:read` responses never return identifiers, demographics or results, while any exceptional raw-message access is denied by default and audit-attributed.
5. Define log retention/deletion and ensure exports, error paths and operational tooling follow the same minimization policy.

**Assessment:** High-priority privacy/data-minimization exposure. A role intended for equipment-master read can retrieve full stored HL7 payloads, including patient and result fields, through the troubleshooting endpoint. Actual access, permission assignment and deployed exposure have not been established.

**Boundary:** exact-head static source review only. No endpoint was called, no integration logs or patient data were accessed, no tenant database was queried, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 144. HL7 ingestion does not enforce equipment activation or bind the authenticated sender to the claimed analyzer

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/integrations/router.py` (blob `ceba912675b3525197055a0ffea944fe604d179b`), `require_hl7_auth()` and `ingest_hl7_oru_r01_message()`; `backend/domains/integrations/service.py` (blob `68fcd948f6460b2c05f9343bd563dee769704a3d`), `process_hl7_oru_r01_in_session()`; `backend/domains/integrations/models.py` (blob `32d40b58d6dec8056729533c30f193f413cba096`), `EquipmentMaster` and `EquipmentTestMapping`.

### 144.1 Tenant-level authentication is not an equipment-level authorization check

The ingestion dependency accepts either the tenant's single shared `X-HL7-Secret` or an ordinary user bearer token carrying `lab:write` or `mdm:write`. The shared secret is resolved from the tenant registry; it is not associated with an individual `EquipmentMaster` record. The request's `equipment_id` is an optional payload field passed directly to the processing service.

The service uses that caller-supplied ID to select active `EquipmentTestMapping` rows, but does not load the corresponding `EquipmentMaster`, verify that it exists, or check its `is_active` flag. The equipment model explicitly has `is_active`, defaulting true. Consequently, deactivating an analyzer does not, in the reviewed ingestion path, prevent a sender holding the tenant-wide secret (or an accepted user bearer token) from continuing to submit results attributed to that equipment ID and using its mappings. The authentication check also cannot distinguish one analyzer from another within the tenant.

This is distinct from Section 113's finding that a normal user bearer token is accepted as analyzer authentication, and Section 144 does not repeat that authentication-mechanism concern. It records the separate missing equipment authorization/lifecycle binding: even after a tenant authenticates, the claimed device is neither authenticated nor checked for active status. The source establishes the missing checks, not that an inactive analyzer has submitted results or that a particular secret is compromised.

### 144.2 Required remediation and acceptance evidence

1. Bind each analyzer to an independently revocable credential or authenticated gateway identity; do not treat one tenant-wide secret as proof of individual equipment identity.
2. Require a valid equipment identity for device-originated messages and resolve it server-side from the authenticated credential, not from an untrusted payload field.
3. Check that the equipment belongs to the current tenant, is active, and is authorized for the submitted protocol/message type before parsing or applying results.
4. Define immediate revocation/deactivation semantics, including credential rotation, replay handling and in-flight messages.
5. Add synthetic tests for unknown IDs, cross-device ID substitution, inactive devices, revoked credentials, mismatched protocol, tenant boundary and successful active-device ingestion. Verify rejected messages cannot mutate diagnostic tasks or create misleading device attribution.

**Assessment:** High-priority integration authorization and device-lifecycle gap. Tenant authentication is not tied to the physical analyzer, and the persisted active flag is not enforced on ingestion. This could allow a tenant-authenticated sender to continue using an inactive analyzer's mapping identity. No misuse or patient-result corruption is established.

**Boundary:** exact-head static source review only. No HL7 endpoint was called, no equipment records, integration logs or patient data were accessed, no tenant database was queried, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 145. HL7 OBX result statuses for deletion and wrong-patient correction are applied as ordinary results

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/integrations/service.py` (blob `68fcd948f6460b2c05f9343bd563dee769704a3d`), `process_hl7_oru_r01_in_session()`.

### 145.1 Status handling does not implement HL7 deletion or wrong-result semantics

The service reads OBX-11 into `obs_status`, but its special handling recognizes only:
- `C`, `A`, `CORRECTED`, `AMENDED` as amendment indicators;
- `X`, `CANNOT_OBTAIN`, `REJECTED` as unobtainable/rejected;
- `P`, `PRELIMINARY` as preliminary.

All other statuses fall through to the ordinary result path. That path writes the OBX-5 value into the diagnostic task and marks the task `RESULT_ENTERED` (unless preliminary or unobtainable). There is no status validation or explicit rejection of unsupported values in the reviewed processing function; an absent OBX-11 is defaulted to `F`.

HL7 Table 0085 assigns materially different semantics to `D` (delete the OBX record) and `W` (post the original as wrong, for example, because it was transmitted for the wrong patient). Neither is treated specially here. A `D` message can therefore be stored as a new ordinary result instead of deleting/withdrawing the prior observation; a `W` message can be stored as an ordinary result instead of marking the prior result wrong and preventing it from remaining current. Other recognized statuses such as `I`, `N`, `O`, `R`, `S`, and `U` also lack explicit state mapping and may be treated as ordinary results.

This is distinct from Sections 113, 143 and 144: it concerns clinical result lifecycle semantics after a message has passed authentication, not who can submit it, who can read the integration log, or which analyzer identity is accepted. The source establishes the implementation gap, not that a real deletion/wrong-result message has been received or that a patient chart currently contains an incorrect result.

### 145.2 Required remediation and acceptance evidence

1. Validate OBX-11 against the negotiated HL7 version/profile; reject unknown or unsupported values rather than silently defaulting them to final.
2. Implement explicit semantics for each supported status, especially `D` and `W`, with safe matching to the exact prior observation identity (patient, order, observation identifier/sub-ID and relevant message context).
3. Preserve an immutable audit trail of withdrawn, deleted, corrected and wrong results; do not physically erase clinical history.
4. Ensure a `W` message cannot leave the wrong-patient result as current or trigger normal order completion; route it to a controlled correction/reconciliation workflow.
5. Define behavior for `U` (finalize previously transmitted preliminary result without replacing its value) and the other supported statuses; do not treat status-only messages as empty new results.
6. Add synthetic tests for `D`, `W`, `C`, `P`, `U`, missing status, invalid status, multiple OBX observations, and repeated delivery. Assert both current-result state and retained audit history.

**Assessment:** High-priority clinical data integrity gap. Deletion and wrong-result statuses can be interpreted as ordinary reportable results, creating a risk that a withdrawn or explicitly wrong observation remains represented as current. No live clinical impact is established.

**Boundary:** exact-head static source review only. No HL7 endpoint was called, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 146. HL7 ingestion request accepts an unbounded raw-message string at the application contract

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/integrations/schemas.py`, `HL7MessageIngestRequest`; `backend/domains/integrations/router.py`, `ingest_hl7_oru_r01_message()`; `backend/domains/integrations/service.py`, parsing and integration-log persistence.

### 146.1 No application-level message-size bound is declared

The request model declares `raw_message: str` without a Pydantic `max_length` constraint or a dedicated bounded type. The ingestion route accepts that value and passes it to parsing without an explicit byte/character limit. The parser creates normalized line strings and split-field lists, then the successful path persists the redacted full message in `HL7IntegrationLog.raw_payload`. Thus a very large request can consume memory during request parsing and segmentation and then consume tenant database storage when accepted.

No maximum segment count, OBX count, field length, or total message size is enforced in the reviewed application path. This is a source-level absence of an application contract limit; it does **not** establish that the reverse proxy, API gateway, hosting platform, or database has no independent limits. No resource exhaustion or oversized message was observed.

### 146.2 Required remediation and acceptance evidence

1. Define a documented maximum HL7 message size in bytes, aligned with the supported analyzer/profile, and reject oversized requests before parsing or persistence.
2. Add bounded limits for segment count, OBX count, field length and total parsed observations; validate encoding and reject malformed framing/segments.
3. Enforce compatible limits at the ingress proxy/API gateway and application layer so upstream buffering cannot defeat the application guard.
4. Avoid retaining arbitrarily large raw payloads; apply retention, encryption and access controls to any exceptional diagnostic archive.
5. Add synthetic boundary tests for maximum accepted size, one byte over limit, excessive segments/OBX rows, long fields, malformed encoding and rejection without database mutation.

**Assessment:** Availability and storage-exhaustion exposure in the integration input contract. Severity depends on external ingress limits, sender trust and rate controls, which were not established in this review.

**Boundary:** exact-head static source review only. No HL7 endpoint was called, no oversized request was sent, no tenant database or patient data was accessed, and no runtime or migration changes were made. External proxy/gateway limits were not verified. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 147. HL7 analyzer-code mapping silently binds repeat tests to the first pending task

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/integrations/service.py` (blob `68fcd948f6460b2c05f9343bd563dee769704a3d`), `process_hl7_oru_r01_in_session()`.

### 147.1 Mapped-code resolution bypasses the repeat-test ambiguity guard

The service loads all pending, sample-collected and in-progress tasks for the patient and orders them FIFO by creation time. For a configured analyzer mapping, it resolves the mapped service ID and loops over `patient_tasks`, selecting the first task with that service ID and an eligible status. It breaks immediately and does not count or reject multiple candidates.

The same first-match behavior is used when resolving an OBX test code through `mapping_dict`. By contrast, the unmapped service-code path explicitly checks whether multiple eligible tasks exist and rejects the message as ambiguous unless an OBR order-control identifier resolves the intended task.

Therefore, when a patient has multiple eligible orders/tasks for the same mapped service (for example, repeat or separately ordered tests), a message without a usable OBR-2/OBR-3 task identifier can be silently attached to the oldest eligible task. FIFO ordering is not proof that the analyzer result belongs to that order. The route can then update the selected task and its parent order using the received observation.

This is distinct from the general task-matching behavior and the status lifecycle findings in Sections 145–146: Section 147 isolates the inconsistent ambiguity protection on the mapped-code branch. The source establishes a deterministic first-candidate selection path, not that a real result has been misfiled.

### 147.2 Required remediation and acceptance evidence

1. Require a validated order/task control identifier for mapped codes whenever more than one eligible task can match.
2. Apply the same candidate-count and ambiguity policy to mapped and unmapped service-code resolution; never silently choose the first candidate.
3. Bind analyzer mapping to the exact configured equipment identity after the device-authentication controls in Section 144 are implemented.
4. Reject ambiguous messages before any task, order, recollection or audit state is mutated; return a safe application error and preserve diagnostic traceability.
5. Add synthetic tests with two or more pending tasks sharing a mapped service, both OBR-identified and unqualified messages, multiple OBX segments, and duplicate/reordered delivery. Assert that no task changes on ambiguous input and that an exact order identifier updates only its intended task.

**Assessment:** High-priority clinical result-assignment integrity gap. The mapped-code branch can silently route a result to the oldest eligible repeat task instead of rejecting ambiguity. No live misassignment or patient harm is established.

**Boundary:** exact-head static source review only. No HL7 endpoint was called, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 148. HL7 ingestion does not validate the message type or declared HL7 version before applying ORU processing

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/integrations/service.py` (blob `68fcd948f6460b2c05f9343bd563dee769704a3d`), `parse_hl7_message()` and `process_hl7_oru_r01_in_session()`; `backend/domains/integrations/router.py` (blob `ceba912675b3525197055a0ffea944fe604d179b`), `ingest_hl7_oru_r01_message()`.

### 148.1 The route name is not backed by message-type/profile validation

The parser splits segments on line endings and fields on the literal pipe character. The processing function checks that an MSH segment exists and has enough fields to read MSH-10, then extracts the control ID. It does not inspect or validate MSH-9 (message type/trigger event) or MSH-12 (HL7 version), nor does it validate the declared encoding characters and field separator against the message framing.

The function proceeds to locate PID, OBR and OBX segments and can update diagnostic tasks when those segments are present. As a result, the endpoint's `/hl7/oru-r01` route and docstring do not themselves ensure that the submitted message is actually an ORU^R01 message using a supported version/profile. A structurally different or unsupported HL7 message containing compatible-looking segments can enter the same result-processing path.

This finding is distinct from Section 145's OBX-11 lifecycle handling and Section 146's size limits. It concerns the message-level protocol contract and type/version gate before clinical data mutation. The reviewed code establishes the missing checks; it does not establish that a non-ORU message has been accepted in production.

### 148.2 Required remediation and acceptance evidence

1. Validate MSH-9 against the explicitly supported message type and trigger event (including the negotiated structure, such as ORU^R01); reject all other types before patient lookup or task mutation.
2. Validate MSH-12 against a documented supported HL7 version/profile and reject unsupported versions rather than parsing them using implicit assumptions.
3. Parse the MSH field separator and encoding characters according to HL7 framing rules, or explicitly constrain and validate the accepted delimiter profile.
4. Validate required segment cardinality/order and the profile-specific PID/OBR/OBX fields before applying results.
5. Add synthetic tests for valid ORU^R01, wrong message type, wrong trigger event, unsupported version, malformed MSH, alternate delimiters, and messages containing PID/OBR/OBX but declaring another message type. Assert rejected inputs produce no task/order mutation or success audit.

**Assessment:** High-priority protocol-validation and clinical data integrity gap. The ORU processing path is selected by URL, not by verified HL7 message type/version. No production acceptance or clinical impact is established.

**Boundary:** exact-head static source review only. No HL7 endpoint was called, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 149. HL7 message-control identifiers are logged but not used as an idempotency or replay fence

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/integrations/service.py` (blob `68fcd948f6460b2c05f9343bd563dee769704a3d`), `process_hl7_oru_r01_in_session()`; `backend/domains/integrations/models.py`, `HL7IntegrationLog`.

### 149.1 The control ID is recorded after processing, without duplicate detection

The processor extracts MSH-10 as `msg_control_id`, uses it in the returned ACK, and writes it to `HL7IntegrationLog.message_control_id` only after task/result processing. The model declares this column indexed but not unique. The reviewed processing path does not query existing integration logs by equipment identity and message control ID before applying observations, nor does it compare a previously accepted payload with a replay.

Consequently, resubmitting an already accepted message control ID is not stopped by an application-level replay check or a database uniqueness constraint in this model. The message can enter result processing again and create another SUCCESS log row. A sender that reuses a control ID with changed content is likewise not rejected as a conflicting duplicate. The current task state may be updated again, including result values and status-dependent fields, depending on the replayed payload.

This is distinct from Section 147's ambiguous repeat-task mapping: Section 149 concerns message-level duplicate delivery and control-ID reuse, irrespective of which task the message resolves to. The source establishes the missing idempotency fence, not that a replay or changed-content collision has occurred in production.

### 149.2 Required remediation and acceptance evidence

1. Define the uniqueness scope for MSH-10 (at minimum the authenticated equipment identity plus sender/application identity and tenant); do not assume a control ID is globally unique across all analyzers.
2. Persist a durable message receipt before applying clinical mutations, with a database-enforced unique key for that scope and a payload digest.
3. For an identical duplicate, return the prior durable processing outcome without reapplying task changes. For the same key with a different digest, reject and raise an attributable security/integration event.
4. Make receipt creation and clinical result application transactionally consistent, with explicit processing states and crash/retry recovery so a committed receipt cannot permanently suppress an uncommitted result.
5. Add synthetic tests for identical replay, same-control-ID changed payload, concurrent duplicate delivery, two distinct equipment senders reusing the same ID, and process interruption around commit. Assert exactly-once clinical effect and deterministic ACK behavior.

**Assessment:** High-priority integration integrity and replay-control gap. MSH-10 is currently an audit/ACK field, not a replay defense. No replay event or patient impact is established.

**Boundary:** exact-head static source review only. No HL7 endpoint was called, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.



## 150. Duplicate active analyzer-code mappings are accepted and resolved by unspecified row order

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/integrations/models.py`, `EquipmentTestMapping`; `backend/domains/integrations/router.py`, `create_equipment_test_mapping()`; `backend/domains/integrations/service.py`, mapping dictionary construction in `process_hl7_oru_r01_in_session()`.

### 150.1 Mapping creation permits duplicate active codes for one analyzer

The `EquipmentTestMapping` model has separate indexes on `equipment_id`, `analyzer_test_code`, and `service_id`, but no composite uniqueness constraint on equipment plus normalized analyzer code. The mapping-create endpoint checks that the equipment exists, then inserts the supplied mapping; it does not check for an existing active mapping with the same equipment and analyzer code, nor does it normalize and enforce case-insensitive uniqueness.

During ingestion, active mappings for the supplied equipment are loaded without an explicit ordering. They are copied into a dictionary keyed by `analyzer_test_code.upper()`. If duplicate rows normalize to the same key, each assignment overwrites the previous service ID. The selected mapping therefore depends on the row order returned by the database, which the query does not define.

The mapped service ID is then used to select the first eligible patient task for that service. A duplicate mapping can consequently direct an analyzer result to a different service/task than the operator intended, without an ambiguity rejection. This is distinct from Section 147: that section covers multiple pending tasks for one mapped service; this section covers multiple active mapping rows for the same equipment/code resolving to different services.

### 150.2 Required remediation and acceptance evidence

1. Normalize analyzer codes consistently (including case and whitespace) at write and read boundaries.
2. Reject a second active mapping for the same equipment and normalized analyzer code; enforce the invariant in PostgreSQL with a suitable database constraint or unique index, including the intended active/inactive semantics.
3. Before enabling the constraint, detect and resolve existing duplicate mappings through an auditable administrative workflow; do not silently choose one.
4. Make ingestion fail closed if duplicate active mappings are encountered, even if historical or externally introduced data bypasses the write path.
5. Add synthetic tests for duplicate case variants, concurrent mapping creation, inactive historical rows, conflicting service IDs, and deterministic rejection before any clinical task mutation.

**Assessment:** High-priority analyzer configuration and clinical result-routing integrity gap. The source establishes that conflicting duplicate mappings can be accepted and that ingestion overwrites collisions without deterministic ordering; it does not establish that a production analyzer has such duplicate configuration or that a result has been misrouted.

**Boundary:** exact-head static source review only. No mapping endpoint was called, no tenant database or patient data was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.



## 151. Specimen-recollection alerts are published before the clinical transaction commits and failures are swallowed

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/integrations/service.py`, `process_hl7_oru_r01_in_session()`, OBX unobtainable-result handling and final transaction commit.

### 151.1 Redis notification is not transactionally coupled to specimen state

When an OBX result is treated as unobtainable, the processor updates the diagnostic task to `SAMPLE_REJECTED`, may create a recollection task, and then publishes a `LAB_SPECIMEN_UNOBTAINABLE` event to Redis. This publish occurs inside the processing loop, before the function's final `db.commit()`. Any exception from obtaining Redis or publishing is caught and discarded. The clinical transaction is committed only later, after all task updates and the HL7 integration log are added.

This creates both sides of a delivery inconsistency:
- If Redis accepts the event but a later operation or database commit fails, the consumer may receive an alert for a rejection/recollection state that was rolled back.
- If Redis is unavailable or publish fails, the exception is swallowed; the database can still commit the rejection/recollection state without a durable notification or retry record.

The reviewed path has no transactional outbox row or durable retry mechanism for this event. The code therefore cannot guarantee that the notification corresponds to committed clinical state or that every committed specimen rejection is eventually surfaced to downstream consumers.

This finding is distinct from Sections 131–136, which concern privacy-retention job queue/execution behavior, and from Section 149, which concerns inbound HL7 replay. It concerns outbound clinical event delivery coupled to the analyzer result transaction.

### 151.2 Required remediation and acceptance evidence

1. Insert a specimen-alert outbox event in the same database transaction as the task/recollection updates, with a stable event ID and patient/order/task references.
2. Dispatch outbox events asynchronously only after commit; mark delivery attempts and outcomes durably.
3. Retry transient failures with bounded backoff and a dead-letter/reconciliation path; make consumers idempotent by event ID.
4. Do not report successful alert delivery merely because an in-process Redis publish call returned; expose delivery state separately from clinical result acceptance.
5. Add synthetic tests for Redis unavailable, publish exception, database commit failure after event creation, worker crash after publish, duplicate dispatch, and eventual delivery. Assert no event is emitted for rolled-back state and every committed rejection remains dispatchable.

**Assessment:** High-priority clinical workflow reliability gap. The source establishes pre-commit publication and swallowed delivery failures; it does not establish a real lost alert, false alert, or patient impact in production.

**Boundary:** exact-head static source review only. No Redis channel was published to, no HL7 endpoint was called, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.



## 152. Concurrent HL7 messages can select and overwrite the same pending diagnostic task without row-level serialization

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/integrations/service.py`, `process_hl7_oru_r01_in_session()`, patient task selection, observation matching, eligibility guard, and result update.

### 152.1 Task matching and mutation are not protected against concurrent ingestion

The processor loads the patient's diagnostic tasks using a SELECT ordered by creation time and ID. The query does not use `FOR UPDATE` or another explicit row-locking strategy. It then builds the in-memory task and service-code maps, selects an eligible task whose status is pending/sample-collected/in-progress, and later writes the result and changes task status to `RESULT_ENTERED`.

The eligibility check is performed against the task objects loaded earlier in the transaction. There is no conditional update requiring the task still to be eligible at write time, no optimistic version column check, and no serialization fence around the selection-and-claim operation.

Two concurrent analyzer messages can therefore both read the same task as pending, both match it, and both proceed to write different observations. Depending on transaction timing and isolation, one commit can overwrite the other's result or one transaction can fail with a database conflict; the reviewed code does not detect and reconcile the competing clinical observations as a controlled conflict. This can occur even when the messages have distinct control IDs, so it is not merely the duplicate-message replay issue in Section 149.

### 152.2 Required remediation and acceptance evidence

1. Lock candidate diagnostic task rows during matching (with a documented lock order) or use an atomic conditional claim/update that succeeds only while the task remains eligible.
2. Revalidate task status and order/patient linkage at mutation time; do not rely solely on stale ORM objects loaded before matching.
3. Define the intended concurrency policy for multiple analytes/messages targeting one task: serialize, aggregate under an explicit message/order identity, or reject conflicting concurrent submissions.
4. Persist a durable result-version/source-message association so conflicting submissions can be audited and reconciled rather than silently overwriting a current result.
5. Add PostgreSQL concurrency tests with two independent sessions and distinct messages targeting the same task. Assert deterministic serialization/rejection and preservation of both audit provenance and the authoritative result.

**Assessment:** High-priority clinical result concurrency and integrity gap. The source establishes that task selection is not explicitly locked or conditionally claimed; it does not establish a concurrent collision or overwritten production result.

**Boundary:** exact-head static source review only. No HL7 endpoint was called, no concurrent database transaction was executed, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.



## 153. Direct HL7 task identifiers bypass pending-state matching and permit ordinary results to overwrite already-entered results

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/integrations/service.py`, OBR/OBX task resolution and result-state guard/update.

### 153.1 Identifier-based matching bypasses the eligible-state filter

The service-code and equipment-mapping fallback paths select only tasks in `PENDING`, `SAMPLE_COLLECTED`, or `IN_PROGRESS`. However, the higher-priority explicit identifier paths do not apply that filter:

- OBR-2/OBR-3 task IDs are accepted from `tasks_by_id` regardless of task status.
- OBX-3 task IDs are likewise accepted from `tasks_by_id` regardless of task status.

After matching, the common guard rejects only `VERIFIED` and `CANCELLED`. It does not reject `RESULT_ENTERED`. The result update path then writes the incoming value and sets the task to `RESULT_ENTERED` for ordinary non-preliminary, non-unobtainable observations. The code recognizes amendment indicators (`C`, `A`, `CORRECTED`, `AMENDED`) for history handling, but does not require an amendment indicator before replacing a previously entered result.

Consequently, an inbound message that explicitly names a task already in `RESULT_ENTERED` can replace its current result using an ordinary observation status (including the default status `F`). The prior value is appended to a note only when it differs; that is not a state-transition guard and does not prevent replacement. This bypasses the pending-only behavior used by the fallback matchers and weakens the expected distinction between a first result and a corrected/amended result.

### 153.2 Required remediation and acceptance evidence

1. Apply one explicit task-eligibility policy after all matching paths, not only to service-code fallback matching.
2. Reject ordinary final observations for `RESULT_ENTERED` tasks unless the configured analyzer profile explicitly supports replacement semantics.
3. Require and validate the appropriate correction/amendment workflow for replacing an existing result; preserve prior result, source message identity, actor/device, and correction reason as structured immutable history.
4. Define separately whether late valid results may recover `SAMPLE_REJECTED` tasks, and require correlation to the rejected specimen/recollection lifecycle rather than allowing implicit recovery by any identifier match.
5. Add synthetic tests for explicit OBR and OBX task IDs targeting PENDING, RESULT_ENTERED, SAMPLE_REJECTED, VERIFIED, and CANCELLED tasks, covering ordinary, preliminary, corrected, and unobtainable OBX statuses.

**Assessment:** High-priority clinical result integrity and lifecycle enforcement gap. The reviewed source establishes the bypass and overwrite path; it does not establish that an analyzer has exercised it or that a production result was overwritten.

**Boundary:** exact-head static source review only. No HL7 endpoint or analyzer was used, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.



## 154. HL7 processing exceptions discard the parsed message-control ID and return an uncorrelated negative ACK

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/integrations/service.py`, `process_hl7_oru_r01_in_session()` exception handler; `backend/domains/integrations/router.py`, ACK response construction.

### 154.1 Error handling loses the inbound MSH-10 correlation value

The processor extracts `MSH-10` into `msg_control_id` near the start of processing. However, its outer exception handler unconditionally rolls back and returns:

```python
return "UNKNOWN", False, "HL7 processing failed: Internal laboratory interface error.", []
```

This happens even when a valid MSH segment and message-control ID were already parsed and a later operation fails (for example, a database flush, delta-check interaction, or commit). The route then constructs the negative ACK using the returned control ID, so the MSA-2 value becomes `UNKNOWN` rather than the inbound MSH-10.

The receiver therefore cannot reliably correlate the negative acknowledgment with the message it sent. Depending on analyzer/interface-engine retry policy, this can cause manual reconciliation or repeated delivery. This compounds, but is distinct from, Section 149: Section 149 concerns the absence of a durable duplicate/replay fence; this section concerns loss of the protocol correlation identifier on processing exceptions.

### 154.2 Required remediation and acceptance evidence

1. Initialize the control ID before entering fallible processing and preserve the validated inbound MSH-10 through every error path.
2. Return a negative ACK containing the original MSH-10 whenever it was successfully parsed; use `UNKNOWN` only when no valid control ID is available.
3. Persist a failed/retryable receipt or integration-log outcome with the same control ID and a sanitized failure classification, without falsely recording success.
4. Add tests that force failures after MSH parsing (query/flush/commit failure) and assert that the returned ACK MSA-2 exactly matches inbound MSH-10.
5. Test retry behavior together with the durable idempotency design from Section 149 so a retry after an uncertain commit cannot duplicate clinical mutations.

**Assessment:** Medium-to-high priority HL7 reliability and message-correlation gap. The source establishes the uncorrelated ACK path; it does not establish a real analyzer retry, duplicate clinical mutation, or production incident.

**Boundary:** exact-head static source review only. No HL7 endpoint or analyzer was used, no database failure was induced, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 155. Multi-analyte HL7 delta checks compare the first numeric value instead of the configured analyte

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/integrations/service.py`, multi-OBX result formatting and delta-check invocation; `backend/domains/clinical/services.py`, `evaluate_lab_delta_check()`; `backend/domains/diagnostics/models.py`, `LabDeltaCheckConfig`.

### 155.1 Configured parameter identity is not used during delta evaluation

The `LabDeltaCheckConfig` model stores one configuration per diagnostic service and includes a required `parameter_name` field. However, `evaluate_lab_delta_check()` retrieves the configuration by `service_id` and never reads `config.parameter_name`. It parses the first numeric substring from the incoming value string and the first numeric substring from the previous task's `result_value`, then compares those two numbers against the service-level thresholds.

The HL7 processor can aggregate multiple OBX observations into one diagnostic task. For multiple observations it serializes each observation as a separate line in `task.result_value`, while selecting the first numeric observation as `primary_numeric_str` for delta evaluation. The prior-result lookup likewise parses only the first numeric substring from the stored aggregate. Neither side is matched to the configured `parameter_name` or to a stable OBX analyte identifier.

For a multi-analyte panel, the first numeric observation is not necessarily the configured analyte. If analyzer observation order changes, or if the configured analyte is not the first numeric OBX, the evaluator can compare different analytes or apply a threshold to the wrong measurement. The resulting delta flag and review note can therefore be misleading. This is distinct from Sections 152–154: it concerns analyte identity in the clinical calculation, not concurrent task mutation, ACK correlation, or replay handling.

### 155.2 Required remediation and acceptance evidence

1. Resolve the configured `parameter_name` to an explicit analyzer observation identifier (for example, a validated OBX-3 code/profile mapping); do not rely on observation position or the first numeric substring.
2. Persist analyte-level numeric values and units in a structured representation with stable parameter identity, rather than recovering a number from a free-form aggregate result string.
3. Define behavior when the configured analyte is absent, duplicated, non-numeric, or has incompatible units; fail closed or mark the delta check as not evaluated rather than silently selecting another analyte.
4. Ensure prior-result lookup selects the same analyte identity and compatible units within the configured lookback window.
5. Add synthetic tests with multi-OBX panels, reordered OBX segments, multiple numeric analytes, missing configured analyte, and changed units. Assert that only the configured analyte is compared and that the prior/current analyte identities match.

**Assessment:** High-priority laboratory result interpretation and delta-check correctness gap. The source establishes that the configured parameter name is unused and that multi-OBX values are reduced to first-number extraction; it does not establish a wrong delta alert or patient impact in production.

**Boundary:** exact-head static source review only. No HL7 endpoint or analyzer was used, no delta-check execution was performed against patient data, no tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 156. Drug–disease contraindication checks treat diagnoses from every historical encounter as active

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/clinical/services.py`, `check_drug_disease_contraindications()`; `backend/domains/clinical/models.py`, `EncounterDiagnosis`; `backend/domains/encounters/models.py`, `PatientEncounter.status` and `EncounterStatusEnum`; `backend/domains/patients/models.py`, `DiagnosisMaster.is_active`.

### 156.1 Historical encounter diagnoses are included in current prescribing checks

The contraindication evaluator's docstring says it evaluates proposed medications against the patient's active diagnoses. Its query joins `DiagnosisMaster` to `EncounterDiagnosis` and then `PatientEncounter`, filtering only on `PatientEncounter.patient_id`. It does not constrain encounter status, diagnosis type, or `DiagnosisMaster.is_active`.

The encounter model explicitly distinguishes `PLANNED`, `ACTIVE`, `DISCHARGED`, and `CANCELLED` states. Nevertheless, diagnoses linked to discharged or cancelled encounters remain eligible inputs to the contraindication rules. For example, a diagnosis recorded during a prior encounter can continue to match a drug-disease rule and cause the evaluator to raise a 409 hard-stop or critical warning during a later order-set application, even when that historical diagnosis is no longer intended to represent a current condition.

The model does not expose a resolved/current flag on `EncounterDiagnosis`, so filtering only to ACTIVE encounters may not be a complete clinical solution: some chronic conditions need to remain relevant after discharge, while resolved acute conditions should not remain active indefinitely. The source-backed defect is that the evaluator silently treats all historical encounter diagnoses as active without a currentness/relevance policy. This is distinct from Section 155's analyte identity issue and from allergy checks, which explicitly filter active patient-allergy records.

### 156.2 Required remediation and acceptance evidence

1. Define a clinical diagnosis-currentness model, including explicit status/resolution, onset/abatement, and chronicity semantics; do not infer currentness solely from the existence of an encounter-diagnosis link.
2. Make contraindication evaluation consume only diagnoses explicitly classified as current/relevant under that model, while preserving chronic conditions across encounter closure where clinically appropriate.
3. Define how provisional, historical, ruled-out, resolved, and inactive master diagnoses participate in each contraindication rule.
4. Ensure diagnosis changes and resolution are attributable and auditable; do not delete historical diagnoses merely to suppress a warning.
5. Add synthetic tests covering active, discharged, cancelled, and planned encounters; resolved and unresolved diagnoses; chronic conditions spanning encounters; inactive diagnosis-master entries; and both hard-stop and overridable-warning rules.

**Assessment:** High-priority clinical decision-support correctness gap. The source establishes that every encounter diagnosis for the patient is queried without lifecycle or currentness filtering; it does not establish that a historical diagnosis has triggered a real production block or that a clinician acted on an incorrect warning.

**Boundary:** exact-head static source review only. No prescribing endpoint was called, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 157. CPOE order-set application silently drops accepted nursing and dietary items

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/clinical/models.py`, `OrderSetItemTypeEnum` and `OrderSetItem`; `backend/domains/clinical/router.py`, `OrderSetItemInput`, `create_cpoe_order_set()`, and `apply_cpoe_order_set_to_encounter()`.

### 157.1 Accepted order-set item types are not all instantiated

The order-set item enum accepts five types: `MEDICATION`, `DIAGNOSTIC_LAB`, `RADIOLOGY`, `NURSING_CARE`, and `DIETARY`. The create request accepts any enum value and persists the supplied item without type-specific validation.

When an order set is applied, the implementation builds only two collections:
- medication items where `item_type == MEDICATION` and `medication_id` is truthy;
- investigation items where `item_type` is `DIAGNOSTIC_LAB` or `RADIOLOGY` and `service_id` is truthy.

There is no application path for `NURSING_CARE` or `DIETARY`; those accepted and persisted items are silently omitted. The response still reports `status: success` and counts only the medication and investigation collections. The same filtering silently omits a medication item with no `medication_id` or a diagnostic/radiology item with no `service_id`. The model has nullable resource references and no type/resource consistency constraint, and the input model has no cross-field validator.

A protocol template containing nursing or dietary instructions can therefore be reported as successfully applied while those components are absent from the resulting encounter orders. This is a protocol completeness and workflow-integrity risk, not evidence that a real patient missed care.

### 157.2 Required remediation and acceptance evidence

1. Either implement durable encounter-linked nursing-care and dietary order records, or reject those item types at template creation until supported. Do not accept and silently discard them.
2. Add type-specific validation: MEDICATION requires exactly one valid `medication_id`; DIAGNOSTIC_LAB and RADIOLOGY require exactly one valid `service_id`; unsupported types must be rejected explicitly.
3. Enforce cross-field consistency at the database boundary where feasible, in addition to request validation, so non-API writes cannot create malformed templates.
4. Make application results enumerate every instantiated item and fail the transaction if any configured item cannot be represented. Do not return success for partial instantiation without an explicit, auditable partial-result state.
5. Add synthetic tests for all five enum values, missing and extraneous resource IDs, mixed order sets, invalid references, and exact equality between configured and instantiated item counts.

**Assessment:** High-priority clinical protocol completeness gap. The source establishes accepted item types and the two-item-family application filter; it does not establish a real order-set application or patient-care omission in production.

**Boundary:** exact-head static source review only. No order-set endpoint was called, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 158. CPOE order-set application does not revalidate medication or diagnostic-service activation

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/pharmacy/models.py`, `MedicationMaster.is_active`; `backend/domains/diagnostics/models.py`, `ServiceCatalog.is_active`; `backend/domains/clinical/router.py`, `apply_cpoe_order_set_to_encounter()`.

### 158.1 Deactivated catalog resources remain usable through previously saved templates

The medication and diagnostic service master models both expose an `is_active` flag. However, order-set application does not include an active-state predicate when loading medication records: it selects `MedicationMaster` using only the IDs stored on the template. It then runs allergy, DDI, and drug-disease checks over the returned rows, and creates `PrescriptionItem` rows for every medication template item.

The diagnostic path similarly creates `DiagnosticTask` rows directly from each stored `service_id`; it does not load the referenced `ServiceCatalog` record or verify `is_active`. Thus deactivating a medication or diagnostic service does not, by itself, prevent an already-active order-set template from instantiating that resource. The order-set master’s own active flag is checked, but the linked catalog resources’ lifecycle state is not.

This creates a stale-template control gap: catalog deactivation is not an effective stop for CPOE application. The source establishes the missing checks, not that any inactive item has actually been prescribed or ordered in production.

### 158.2 Required remediation and acceptance evidence

1. Revalidate every referenced medication and service at application time, including `is_active`, and reject the complete transaction with a clear item-level error if any resource is inactive.
2. Define whether deactivation should invalidate existing templates, require template revision, or permit a documented grandfathering workflow; do not let that behavior emerge accidentally from missing predicates.
3. Ensure all medication safety checks run against the exact set of medication items that will be instantiated; fail closed if any referenced row is missing or inactive.
4. Add synthetic tests that deactivate a medication or service after template creation and verify that application cannot silently instantiate it; include mixed active/inactive templates and transaction rollback assertions.
5. Provide an attributable, auditable exception path only if clinical governance explicitly approves one.

**Assessment:** High-priority catalog-lifecycle enforcement gap in clinical order execution. This is distinct from Section 157: Section 157 concerns item types/required references that the application never instantiates; Section 158 concerns valid linked resources that have since been deactivated.

**Boundary:** exact-head static source review only. No catalog or order-set endpoint was called, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 159. NEWS2 endpoint converts unrecorded consciousness into an observed normal Alert state

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/clinical/router.py`, `NEWS2EvaluationRequest` and `evaluate_encounter_news2()`; `backend/domains/clinical/services.py`, `calculate_news2_score()`.

### 159.1 Missing consciousness is defaulted to Alert before completeness and scoring

The request model makes `consciousness` optional. In the endpoint, the submitted value is converted with `payload.consciousness or "ALERT"` before calling the NEWS2 calculator. The calculator then treats Alert as a measured normal state: it assigns zero consciousness points and includes consciousness in its core-parameter completeness check because the value is no longer `None`.

Consequently, when a caller omits consciousness but supplies the other five core observations, the evaluator reports a complete parameter set and scores consciousness as normal Alert. It cannot distinguish “Alert was assessed” from “consciousness was not documented.” A patient with unassessed confusion or reduced responsiveness could therefore receive a lower score and a falsely complete-data result compared with an explicitly recorded abnormal ACVPU state.

The source establishes the defaulting and scoring behavior; it does not establish a real NEWS2 record, missed deterioration, or patient harm.

### 159.2 Required remediation and acceptance evidence

1. Preserve missing consciousness as missing; do not translate absence into a normal clinical observation.
2. Require an explicit ACVPU assessment for a complete NEWS2 set, or expose an explicit incomplete/unknown state that cannot be represented as Alert.
3. Ensure missing consciousness is reported in `missing_parameters` and the recommendation remains explicitly incomplete.
4. Add synthetic endpoint and calculator tests contrasting omitted consciousness, explicit Alert, Confusion, Voice, Pain, and Unresponsive.
5. Verify risk classification and RRT behavior for the same vital set with consciousness omitted versus explicitly abnormal; retain attributable provenance for each observation.

**Assessment:** High-priority early-warning score data-quality and under-triage risk. The finding is the conflation of missing assessment with normal Alert, not a claim that the NEWS2 algorithm itself was clinically validated or that a real patient was under-scored.

**Boundary:** exact-head static source review only. No NEWS2 endpoint was called, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 160. NEWS2 score can retain a vital record from a different encounter

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/clinical/router.py`, `NEWS2EvaluationRequest` and `evaluate_encounter_news2()`; `backend/domains/clinical/models.py`, `EncounterVital` and `ClinicalEarlyWarningScore`.

### 160.1 The route checks encounter ownership only for hydration, not for acceptance

The NEWS2 endpoint loads `EncounterVital` by the caller-supplied `vital_id`. It copies observations from that row only when `vital.encounter_id == encounter_id`. If the vital exists but belongs to another encounter, the hydration block is skipped; the endpoint nevertheless continues scoring the request's manually supplied observations (or returns the calculator's validation error if insufficient observations were supplied).

On successful scoring, the endpoint persists `ClinicalEarlyWarningScore(encounter_id=encounter_id, vital_id=payload.vital_id, ...)` without clearing or rejecting the mismatched identifier. The model defines independent foreign keys from the score to `patient_encounters.id` and `encounter_vitals.id`; no composite constraint or model-level ownership validation ties the selected vital to the score's encounter.

A score can therefore be attached to encounter A while its provenance pointer references a vital recorded under encounter B. When request observations override some or all stored values, the record also does not capture which individual values came from the vital versus the request. This is a clinical-record provenance and encounter-integrity defect. The source does not establish that a cross-encounter score has actually been persisted or that any clinical decision was affected.

### 160.2 Required remediation and acceptance evidence

1. If `vital_id` is supplied, require that it exists and belongs to the requested encounter; return a client error before scoring or persistence when it does not.
2. If the score is calculated entirely from request-supplied values, omit `vital_id` unless the API explicitly models and records a verified source relationship.
3. Define whether mixed manual overrides are allowed. If allowed, persist per-observation source/provenance and override attribution rather than implying that all values came from the linked vital.
4. Where feasible, enforce encounter/vital consistency at the database boundary (for example, a composite relationship/constraint supported by the chosen PostgreSQL model) as defense in depth.
5. Add synthetic tests for same-encounter vital, foreign-encounter vital, nonexistent vital, fully manual observations, and partial overrides. Assert that no mismatched score row is committed.

**Assessment:** High-priority clinical record integrity and provenance gap. The finding is the route's acceptance/persistence behavior and independent foreign keys, not evidence of cross-patient disclosure, a real mismatched record, or patient harm.

**Boundary:** exact-head static source review only. No NEWS2 endpoint was called, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 161. NEWS2 temperature scoring has decimal gaps that fall into the highest-temperature fallback band

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/clinical/router.py`, `NEWS2EvaluationRequest.temperature_f`; `backend/domains/clinical/services.py`, `calculate_news2_score()`.

### 161.1 Accepted fractional temperatures can be assigned to the wrong band

The request model accepts `temperature_f` as an unrestricted optional float. The calculator accepts Celsius values from 15.0 to 50.0 (or Fahrenheit values from 60.0 to 120.0 and converts them to Celsius), but its scoring comparisons use decimal bands with gaps:

- `temp_c <= 35.0`: 3 points;
- `35.1 <= temp_c <= 36.0`: 1 point;
- `36.1 <= temp_c <= 38.0`: 0 points;
- `38.1 <= temp_c <= 39.0`: 1 point;
- every remaining accepted value: 2 points, described in the code comment as `>= 39.1`.

Values between those decimal boundaries are not rejected or normalized. For example, `36.05°C` does not satisfy any of the first four comparisons and reaches the final `else`, receiving 2 points. Similar gaps exist between 35.0/35.1, 36.0/36.1, and 38.0/38.1. The fallback therefore does not mean only temperatures at or above 39.1°C; it also captures valid values in the gaps.

Because temperature contributes to the aggregate NEWS2 total and can affect the threshold/individual-parameter escalation logic, such inputs can inflate the score and change its risk or RRT classification. This is a deterministic scoring defect for accepted fractional inputs, not evidence that a real patient record or escalation was affected.

### 161.2 Required remediation and acceptance evidence

1. Define the accepted measurement precision and normalize/round temperature once, explicitly and consistently, before band evaluation; alternatively use continuous, non-overlapping interval comparisons that cover every accepted value.
2. Keep the Fahrenheit-to-Celsius conversion and rounding policy explicit, including boundary behavior after conversion.
3. Ensure the final high-temperature branch is an explicit lower-bound comparison, not an unconditional fallback for all unclassified values.
4. Add synthetic tests at every boundary and immediately below/above it, including `36.05°C`, equivalent Fahrenheit inputs, and accepted extremes.
5. Assert exact temperature sub-score, total NEWS2 score, risk level, and RRT flag for the boundary matrix.

**Assessment:** High-priority clinical scoring correctness defect. The source proves the uncovered decimal intervals and fallback scoring; it does not establish a real-world misclassification or patient harm.

**Boundary:** exact-head static source review only. No NEWS2 endpoint was called, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 162. NEWS2 accepts unrecognized and blank consciousness values instead of enforcing ACVPU

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/clinical/router.py`, `NEWS2EvaluationRequest`; `backend/domains/clinical/services.py`, `calculate_news2_score()`.

### 162.1 Unvalidated strings produce inconsistent scoring and completeness

The request model declares `consciousness` as `Optional[str]` without an enum, length constraint, or validator. The calculator also does not reject values outside the documented ACVPU states.

For a non-empty value, the scoring branch awards zero only when the normalized string is `ALERT` or `A`; every other non-empty string receives 3 points. Thus an arbitrary value such as `"UNKNOWN"` is scored as a confirmed abnormal consciousness state and contributes to the single-parameter escalation logic. Conversely, a whitespace-only value is non-None and therefore excluded from `missing_parameters`, but the scoring branch skips it after trimming; it contributes zero points. The endpoint's `payload.consciousness or "ALERT"` fallback does not normalize whitespace, so the whitespace case reaches the calculator unchanged.

The same unvalidated value is used by qSOFA: unknown non-empty strings count as altered mentation, while whitespace-only values do not. This permits malformed input to produce either a false abnormal score or a falsely complete parameter set with no consciousness points.

### 162.2 Required remediation and acceptance evidence

1. Restrict the API and calculator boundary to an explicit normalized ACVPU enum: Alert, Confusion, Voice, Pain, and Unresponsive (with documented accepted aliases only).
2. Trim and normalize before completeness evaluation; reject blank strings rather than treating them as present.
3. Reject unknown values with a clear 422 response; never silently map an unknown state to Alert or to a confirmed abnormal state.
4. Apply the same validated normalized state to NEWS2 and qSOFA calculations.
5. Add synthetic tests for all five valid states, supported aliases, lowercase/whitespace-padded valid values, empty and whitespace-only strings, and arbitrary unknown values. Assert score, completeness, missing parameters, qSOFA, risk, and RRT behavior.

**Assessment:** High-priority clinical input-validation and scoring-integrity defect. The source proves the permissive request type and calculator behavior; it does not establish malformed clinical data in production or patient harm.

**Boundary:** exact-head static source review only. No NEWS2 endpoint was called, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 163. NEWS2 treats omitted supplemental-oxygen status as confirmed room air and excludes it from completeness

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/clinical/router.py`, `NEWS2EvaluationRequest`; `backend/domains/clinical/services.py`, `calculate_news2_score()`.

### 163.1 Default value masks an unrecorded NEWS2 parameter

The request model declares `on_supplemental_oxygen: bool = False`. A caller that omits the field is therefore indistinguishable from one that explicitly records the patient as not receiving supplemental oxygen.

The calculator unconditionally adds the supplemental-oxygen subscore: 2 points when true and 0 when false. However, its `core_parameters` completeness map includes respiratory rate, SpO2, systolic BP, pulse, consciousness, and temperature, but not supplemental-oxygen status. Consequently, a request containing all six listed core values but omitting oxygen status can be marked `is_complete_set=True` and receive zero oxygen points, even though the oxygen state was never supplied.

This can understate the calculated NEWS2 total by two points when the patient is actually receiving supplemental oxygen, and the completeness indicator does not reveal the missing input.

### 163.2 Required remediation and acceptance evidence

1. Represent oxygen status as an explicitly supplied value (e.g. nullable/required boolean or a validated observation enum); do not default an omitted field to room air.
2. Include oxygen status in the NEWS2 completeness contract and missing-parameter reporting.
3. Define how incomplete oxygen status affects scoring and escalation; do not silently calculate a definitive complete-set score.
4. Preserve the distinction between an explicitly documented room-air state and an unknown/unrecorded state in persisted score provenance.
5. Add synthetic tests for explicit room air, explicit supplemental oxygen, omitted status, and partial vital sets; assert oxygen subscore, total, completeness, risk, and RRT outputs.

**Assessment:** High-priority NEWS2 completeness and potential under-scoring defect. The source proves that omission is defaulted to false and excluded from completeness; it does not establish omitted oxygen documentation or patient harm in production.

**Boundary:** exact-head static source review only. No NEWS2 endpoint was called, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 164. NEWS2 Scale 2 can be selected without recording its clinical eligibility

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/clinical/router.py`, `NEWS2EvaluationRequest` and `evaluate_encounter_news2()`; `backend/domains/clinical/services.py`, `calculate_news2_score()`.

### 164.1 Request-controlled scale selection changes oxygen scoring without an eligibility check

The request model exposes `spo2_scale: int = 1`. The route passes this value directly to the calculator. The calculator validates only that the value is 1 or 2. Its own documentation describes Scale 2 as the scale for hypercapnic respiratory failure/COPD, and the Scale 2 SpO2 bands use a different target range (88–92%) from Scale 1.

In the reviewed route/calculator path, selection of Scale 2 is not tied to a recorded clinical indication, a clinician attestation, or an eligibility decision. A caller with permission to submit a NEWS2 evaluation can therefore select Scale 2 for an encounter without this path establishing that the patient is eligible. For example, at SpO2 90%, Scale 1 assigns 3 points while Scale 2 assigns 0 points before any supplemental-oxygen contribution. An inappropriate scale choice can materially lower the score and alter risk/escalation classification.

This is a control gap in the reviewed evaluation path; the source review does not establish whether another external workflow or clinical governance process constrains scale selection in deployed use.

### 164.2 Required remediation and acceptance evidence

1. Require an explicit, attributable clinical indication for Scale 2, rather than accepting a bare integer selector.
2. Validate eligibility against an authoritative documented clinical decision/diagnosis and any required clinician authorization; do not infer eligibility solely from a generic COPD label if the governing clinical protocol requires confirmed hypercapnic respiratory failure.
3. Persist the selected scale, indication, authorizing clinician, and relevant source evidence with the score so the decision is auditable.
4. Make Scale 1 the safe default only where protocol permits; prevent silent caller override to Scale 2 without the required eligibility evidence.
5. Add synthetic tests proving Scale 2 is rejected without eligibility evidence, accepted with valid attributable evidence, and that the expected Scale 1/Scale 2 score differences are reflected in persisted provenance and escalation outputs.

**Assessment:** High-priority clinical governance and scoring-integrity control gap. The source proves caller-controlled selection and differing score bands; it does not establish an inappropriate selection in production or patient harm.

**Boundary:** exact-head static source review only. No NEWS2 endpoint was called, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 165. NEWS2 temperature unit is inferred from a numeric threshold, creating an ambiguous and discontinuous input contract

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/clinical/services.py`, `calculate_news2_score()`; `backend/domains/clinical/router.py`, `NEWS2EvaluationRequest` and encounter-vital hydration.

### 165.1 A single numeric value is interpreted as Celsius or Fahrenheit based on whether it exceeds 45

The request exposes one optional numeric field, `temperature_f`, without a separate unit discriminator. The calculator uses `temperature_f > 45.0` to decide that the input is Fahrenheit; values at or below 45.0 are treated as Celsius. The validation branches then apply different bounds: 60–120 for the inferred Fahrenheit branch and 15–50 for the inferred Celsius branch. Scoring repeats the same inference when converting to Celsius.

This produces a discontinuity at 45.0. For example, 45.0 is accepted as 45.0°C, while 45.1 enters the Fahrenheit branch and is rejected as below 60°F. A Celsius measurement within the calculator's stated 15–50°C range cannot be represented for values above 45.0. Conversely, a Fahrenheit measurement at or below 45.0 is treated as Celsius rather than Fahrenheit. The field name `temperature_f` does not resolve the ambiguity because the implementation explicitly accepts both units through the heuristic.

The issue is not a claim that these extreme values are common; it is that the API contract does not identify the unit and the same physical input can be interpreted differently or rejected solely due to the numeric threshold.

### 165.2 Required remediation and acceptance evidence

1. Make temperature unit explicit in the request and vital-record contract (e.g. a validated `temperature_unit` enum with `C` or `F`).
2. Normalize exactly once at the API/service boundary to a canonical unit; remove numeric-threshold unit inference.
3. Validate the raw value against the explicit unit's documented range and retain the original value/unit for provenance.
4. Ensure hydrated EncounterVital values have a documented unit contract and cannot silently inherit a different interpretation from manually supplied values.
5. Add synthetic tests around 45.0/45.1, Fahrenheit values below and above 60, conversion equivalence for the same physical temperature, range rejection, and persisted normalized/original provenance.

**Assessment:** High-priority measurement-contract and scoring-integrity defect. The source proves the threshold-based unit inference and discontinuous validation; it does not establish a mis-entered temperature or patient harm in production.

**Boundary:** exact-head static source review only. No NEWS2 endpoint was called, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 166. Persisted NEWS2 history omits the component evidence and completeness state needed to reproduce the score

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/clinical/models.py`, `ClinicalEarlyWarningScore`; `backend/domains/clinical/router.py`, `evaluate_encounter_news2()`; `backend/domains/clinical/services.py`, `calculate_news2_score()`.

### 166.1 The response contains calculation detail that the persisted record does not retain

The calculator returns the aggregate NEWS2 and qSOFA scores, risk, RRT flag, completeness flag, missing-parameter list, per-parameter `sub_scores`, and recommendation. The route returns these fields to the immediate caller.

The `ClinicalEarlyWarningScore` model persists only encounter ID, optional vital ID, evaluator ID, aggregate NEWS2 score, risk level, qSOFA score, RRT flag, and recommendation. It has no persisted columns or structured evidence field for the individual observations used, per-parameter subscores, selected SpO2 scale, supplemental-oxygen state, temperature unit/normalized value, completeness flag, or missing-parameter list.

The route permits manually supplied values and partial overrides of a referenced vital record. It persists only the optional `vital_id` reference, not a snapshot of the actual values used. Consequently, a historical score may not be independently reproducible from its stored row: manual values are not captured, and a linked vital row is not an immutable snapshot of the exact calculation inputs. The immediate API response cannot substitute for durable, queryable clinical provenance.

### 166.2 Required remediation and acceptance evidence

1. Persist an immutable, versioned calculation snapshot containing every input actually used, its source (vital record or manual override), unit, selected scoring scale, oxygen state, and normalized value.
2. Persist per-parameter subscores, missing parameters, completeness, aggregate scores, risk, RRT decision, and the scoring-algorithm/version identifier.
3. Preserve source vital identity and the exact snapshot even if the underlying vital record is later amended; record amendment/correction history rather than rewriting the historical calculation evidence.
4. Ensure the snapshot is tenant-local, access-controlled, auditable, and covered by retention/privacy policy.
5. Add synthetic tests for all-manual inputs, vital hydration, partial overrides, later vital amendment, and score retrieval; prove the stored snapshot reproduces the returned calculation exactly.

**Assessment:** High-priority clinical auditability and reproducibility gap. The source proves the model's limited persisted fields and route's manual/partial input behavior; it does not establish a specific historical score that cannot be reconstructed in deployed data or patient harm.

**Boundary:** exact-head static source review only. No NEWS2 endpoint was called, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 167. NEWS2 accepts a nonexistent optional vital ID through calculation and defers failure to the database foreign key

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/clinical/router.py`, `NEWS2EvaluationRequest` and `evaluate_encounter_news2()`; `backend/domains/clinical/models.py`, `ClinicalEarlyWarningScore.vital_id`.

### 167.1 A missing vital row is silently ignored during hydration but still persisted as the score's source

The request accepts optional `vital_id`. The route calls `db.get(EncounterVital, payload.vital_id)`; it hydrates values only when the returned row exists and belongs to the requested encounter. If the ID does not resolve, the route does not reject it or clear it. When sufficient manual measurements are supplied, calculation continues and the route constructs `ClinicalEarlyWarningScore(vital_id=payload.vital_id)`.

The model declares `vital_id` as a nullable foreign key to `encounter_vitals.id`. Therefore, a nonexistent ID reaches persistence and conflicts with the database FK at commit, rather than producing a deliberate client-facing validation response. This can turn a malformed request into an unhandled persistence failure (typically HTTP 500) after the calculator has completed. If the caller omits manual measurements, the calculator may instead reject the empty measured-vitals set before persistence; the failure path depends on the other request fields.

### 167.2 Required remediation and acceptance evidence

1. If `vital_id` is supplied, require that it resolves to an existing vital record and belongs to the requested encounter before calculation, regardless of whether manual values are also supplied.
2. Return a deterministic 404/422 validation response for missing or foreign vital IDs; do not defer validation to a database constraint failure.
3. Define whether a manual-only evaluation must omit `vital_id`; enforce that contract explicitly.
4. Add synthetic tests for nonexistent ID with complete manual values, nonexistent ID with no manual values, foreign-encounter ID, valid same-encounter ID, and manual-only request with no ID. Assert no score row is created on invalid input and no unhandled 500 occurs.

**Assessment:** High-priority input-validation and clinical provenance integrity defect. The source proves the missing-row branch is not rejected and the model FK exists; no malformed request or production failure is established.

**Boundary:** exact-head static source review only. No NEWS2 endpoint was called, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 168. NEWS2 can calculate from an old encounter vital as though it were current

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/clinical/models.py`, `EncounterVital`; `backend/core/audit.py`, `AuditMixin`; `backend/domains/clinical/router.py`, `record_encounter_vitals()` and `evaluate_encounter_news2()`; `backend/domains/clinical/schemas.py`, `EncounterVitalCreate`.

### 168.1 The source record has no clinical measurement timestamp or freshness gate

`EncounterVital` stores observations and inherits `created_at` from `AuditMixin`. That timestamp is assigned by the database when the row is inserted; the vital model has no separate `measured_at`/observation-time field. The create request likewise accepts measurements and notes but no observation timestamp. Consequently, the system cannot distinguish when a measurement was taken from when it was entered.

The NEWS2 route accepts any `vital_id` that resolves to a record belonging to the requested encounter. It hydrates omitted values from that record without checking its age or any configured clinical freshness interval. A same-encounter vital entered substantially earlier can therefore supply values to a new NEWS2 calculation and be persisted as the source of that evaluation. The existing same-encounter check prevents cross-encounter hydration, but it does not establish temporal relevance.

This is a source-level capability and missing-control finding. It does not establish that an old vital was actually used in production, that any particular NEWS2 score was incorrect, or that patient harm occurred.

### 168.2 Required remediation and acceptance evidence

1. Add an explicit observation/measurement timestamp with timezone-aware semantics, distinct from row creation/entry time; preserve both timestamps and the recording actor.
2. Define clinically governed freshness rules for NEWS2 inputs, including the behavior for stale, future-dated, or partially refreshed observations. Do not invent a universal interval in code without clinical-owner approval.
3. Before hydration, validate the observation timestamp against the approved policy. Reject stale inputs or require a deliberate, attributable clinician override with a recorded rationale; never silently treat stale observations as current.
4. Persist the exact observation timestamp and per-parameter source/provenance in the NEWS2 calculation snapshot, including which values were manually overridden.
5. Add synthetic tests for fresh, stale, future-dated, partially overridden, and manual-only evaluations; assert deterministic validation, override audit evidence, and no score persistence for rejected stale input.

**Assessment:** High-priority clinical temporal-validity and provenance gap. The reviewed model and route demonstrate that the measurement time is not represented and no freshness decision is made before calculation. Clinical policy must determine acceptable age thresholds and override rules.

**Boundary:** exact-head static source review only. No NEWS2 endpoint was called, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 169. NEWS2 labels an incomplete assessment LOW when its observed subtotal is below escalation thresholds

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/clinical/services.py`, `calculate_news2_score()`; `backend/domains/clinical/router.py`, `evaluate_encounter_news2()`; `backend/domains/clinical/models.py`, `EarlyWarningRiskEnum` and `ClinicalEarlyWarningScore`.

### 169.1 Missing mandatory observations do not prevent a LOW structured risk result

The calculator identifies six core parameters and sets `is_complete_set` false when any are missing. However, risk classification is performed from the sum of the available subscores and the `any_parameter_is_3` flag without first gating the LOW classification on completeness. If the available subtotal is below 5 and no supplied parameter scores 3, the function returns `risk_level="LOW"` and `is_rrt_alert_triggered=False`, even when mandatory observations are missing. It changes only the free-text recommendation to begin with `INCOMPLETE_DATA` and instructs the caller to obtain a complete vital set before concluding low risk.

The endpoint returns both structured risk fields and the completeness/missing-parameter fields. It also persists the LOW enum and false RRT flag in `ClinicalEarlyWarningScore`. The model's risk enum contains only LOW, MEDIUM and HIGH, so the persisted classification cannot represent an unassessed/incomplete state. A downstream dashboard, alert rule, export, or integration that relies on the structured risk/alert fields can therefore interpret an incomplete assessment as LOW despite the separate text warning.

This is a deterministic source-level inconsistency. It does not establish that a downstream consumer actually ignored the completeness flag, that a specific incomplete assessment occurred in production, or that patient harm resulted.

### 169.2 Required remediation and acceptance evidence

1. Make completeness part of the structured classification contract. An incomplete assessment must not be represented as LOW; introduce a distinct INCOMPLETE/UNASSESSABLE state or a nullable/explicitly unavailable risk classification, subject to clinical governance.
2. Define the RRT/urgent-review behavior for incomplete observations independently from the aggregate score. Preserve escalation when any observed parameter independently meets an escalation threshold.
3. Ensure API responses, persisted history, UI, exports, and integrations all expose and honor completeness and missing parameters; do not rely on a free-text recommendation as the only warning.
4. Add synthetic tests for incomplete low subtotal, incomplete subtotal with a single severe parameter, complete low assessment, and complete medium/high assessments. Assert risk state, RRT flag, recommendation, persisted record, and serialized history remain consistent.
5. Obtain clinical-owner approval for the classification and escalation semantics before implementation.

**Assessment:** High-priority clinical classification and downstream-consumer safety gap. The calculator and persistence path establish the mismatch; actual downstream misinterpretation or patient impact is not established.

**Boundary:** exact-head static source review only. No NEWS2 endpoint was called, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 170. Concurrent SOAP note sign-off can overwrite the recorded signer

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/clinical/router.py`, `sign_off_clinical_note()`; `backend/domains/clinical/models.py`, `ClinicalNote`; `backend/core/audit.py`, `AuditMixin`.

### 170.1 The unsigned-state check and signature write are not an atomic transition

The sign-off route loads the note with `db.get(ClinicalNote, note_id)`, returns 404 when absent, and returns 409 if the in-memory row already has `is_signed=True`. Otherwise it sets `is_signed=True`, assigns the current request's `signed_at` and `signed_by_id`, updates the audit actor, and commits.

There is no `SELECT ... FOR UPDATE`, conditional database update requiring `is_signed = false`, compare-and-swap/version check, or model version column. `ClinicalNote` stores one mutable signer and timestamp pair. `AuditMixin` supplies creation/update timestamps and actor IDs, but no optimistic concurrency token.

Two transactions can therefore both load the same unsigned row before either commits. Both pass the check and both issue updates; the later commit can replace the earlier `signed_by_id` and `signed_at`. Each request may return success even though only the last writer remains represented in the note. This undermines the attribution and evidentiary value of the sign-off record under concurrent requests.

This is a concurrency capability established by the route/model structure; no concurrent production sign-off or actual overwritten signature is established.

### 170.2 Required remediation and acceptance evidence

1. Make sign-off a single atomic state transition, e.g. conditional `UPDATE clinical_notes SET ... WHERE id = :id AND is_signed = false`, and require exactly one affected row.
2. Alternatively, lock the row before checking and changing the sign-off state; ensure all sign-off paths use the same locking discipline.
3. Preserve the winning signer and timestamp as immutable evidence. If multiple signature events are legitimately supported, store append-only signature events rather than overwriting the single signer fields.
4. Return 409 to losing concurrent requests and do not report success unless the transition committed.
5. Add a two-session PostgreSQL concurrency test that synchronizes both requests after reading the unsigned state; assert exactly one success, one conflict, and one stable signer/timestamp pair.

**Assessment:** High-priority clinical record integrity and signature-attribution race. The source proves the check-then-write sequence lacks atomic concurrency control; it does not establish an actual production race or patient/legal impact.

**Boundary:** exact-head static source review only. No clinical endpoint was called, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 171. Concurrent SOAP note edit can commit after sign-off and mutate signed content

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/clinical/router.py`, `update_soap_clinical_note()` and `sign_off_clinical_note()`; `backend/domains/clinical/models.py`, `ClinicalNote`.

### 171.1 The unsigned check does not fence a concurrent content update

The update route loads a note, checks `is_signed`, and rejects only when the value observed by that request is already true. It then applies supplied SOAP fields and commits. The sign-off route independently loads the note, checks the same flag, and writes the signature fields. Neither route uses a row lock, conditional update predicate, or optimistic version check.

A concrete interleaving is possible: transaction A loads an unsigned note and passes the edit guard; transaction B signs and commits the note; transaction A then commits its already-authorized SOAP-field changes. The edit transaction updates the note content without rechecking the committed signed state. The resulting row can remain `is_signed=True` while its signed SOAP content has been changed after sign-off. The edit route can return success.

This is distinct from Section 170: Section 170 concerns competing sign-off requests overwriting signer attribution; this section concerns an edit transaction passing its pre-signature check and committing content after another transaction signs.

No concurrent production edit/sign-off or actual post-signature mutation is established.

### 171.2 Required remediation and acceptance evidence

1. Serialize edits and sign-off on the same note row using a consistent row-locking protocol, or use a versioned/conditional write that fails if the note was signed or changed after the editor read it.
2. Make the edit write itself conditional on `is_signed = false`; do not rely solely on an earlier in-memory check.
3. Ensure a losing edit returns 409 and leaves all SOAP fields, signature fields, and audit attribution unchanged.
4. Add a two-session PostgreSQL test: transaction A reads and stages an edit; transaction B signs and commits; A attempts to commit. Assert the edit is rejected or serialized before sign-off, and no content can change after the signature.
5. Add the reverse-order test (edit commits before sign-off) to confirm the signed content is exactly the final committed pre-signature content.

**Assessment:** High-priority medico-legal record integrity race. Source establishes a check-then-write gap across the edit and sign-off routes; it does not establish an actual production incident or legal/patient impact.

**Boundary:** exact-head static source review only. No clinical endpoint was called, no patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 172. Concurrent diagnosis attachment can bypass duplicate and single-primary checks

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/clinical/router.py`, `attach_encounter_diagnosis()`; `backend/domains/clinical/models.py`, `EncounterDiagnosis`.

### 172.1 Application pre-checks are not backed by database uniqueness

The route validates that the encounter is active and the diagnosis master row is active. It then performs two application-level checks:

- For a requested `PRIMARY` diagnosis, it queries for an existing primary diagnosis on the encounter and returns 409 if one is found.
- It queries for an existing row with the same `encounter_id` and `diagnosis_id`, returning 409 if found.

If both checks pass, it inserts and commits a new `EncounterDiagnosis`.

The reviewed model declares only a non-unique index on `created_at`, plus foreign keys and ordinary indexed columns. It does not declare a unique constraint for `(encounter_id, diagnosis_id)` or a partial unique constraint for one `PRIMARY` row per encounter. No row lock or serializing encounter-level lock surrounds the checks and insert.

Two concurrent requests can therefore both observe no existing matching diagnosis and insert duplicates. Two concurrent requests attaching different diagnoses as `PRIMARY` can both observe no primary row and commit, leaving multiple primary diagnoses for one encounter. These are separate invariant violations arising from the same check-then-insert design.

No actual duplicate or multiple-primary production rows are established.

### 172.2 Required remediation and acceptance evidence

1. Enforce diagnosis uniqueness in PostgreSQL with a unique constraint on `(encounter_id, diagnosis_id)`.
2. Enforce at most one primary diagnosis per encounter with a partial unique index on `encounter_id WHERE diagnosis_type = 'PRIMARY'` (using the actual persisted enum representation).
3. Translate the corresponding database uniqueness violations into stable 409 responses; retain application pre-checks only for friendly early feedback.
4. Add two-session PostgreSQL tests for same-diagnosis concurrent insertion and different-diagnosis concurrent PRIMARY insertion. Assert exactly one commit succeeds in each case.
5. Verify migration behavior against existing duplicate data before adding constraints; do not silently delete or reclassify clinical diagnoses.

**Assessment:** High-priority encounter diagnosis integrity issue. The source proves that application checks are raceable and the reviewed ORM model lacks matching uniqueness declarations; it does not establish that the live deployed catalog lacks equivalent manually managed constraints or that production data is affected.

**Boundary:** exact-head static source/model review only. No patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 173. CPOE order-set medication quantity is not validated until prescription persistence

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/clinical/router.py`, `OrderSetItemInput`, `create_cpoe_order_set()`, and `apply_cpoe_order_set_to_encounter()`; `backend/domains/clinical/models.py`, `OrderSetItem`; `backend/domains/pharmacy/models.py`, `PrescriptionItem`.

### 173.1 Invalid quantities can be saved in an active order-set template

`OrderSetItemInput.quantity` is a plain integer with default 1 and no positive lower bound. The `OrderSetItem.quantity` column is non-null with a default but has no positive-value check constraint in the reviewed model. The order-set creation route persists supplied item quantities without validating that a medication quantity is positive.

When an active order set is applied, medication line quantities are copied directly to `PrescriptionItem.requested_quantity`. That destination model has a PostgreSQL check constraint `ck_rx_req_qty_pos` requiring `requested_quantity > 0`.

Consequently, a template containing a medication line with quantity zero or a negative quantity can be created successfully, but applying it reaches a database integrity failure during the final transaction commit. The route does not translate that constraint failure into a controlled validation response. Because the prescription and associated diagnostic rows are committed in the same transaction, the failed commit rolls back the attempted instantiation rather than partially creating those rows.

This is a deterministic invalid-template-to-failed-application path from the reviewed source and model constraints. No actual invalid template or production application failure is established.

### 173.2 Required remediation and acceptance evidence

1. Validate medication quantities at the order-set input boundary with an explicit minimum of 1.
2. Add a database check constraint on `order_set_items.quantity > 0` for medication line items (or on all item types if that is the chosen domain rule).
3. Validate persisted templates before application so legacy invalid rows produce a controlled 422/409 response with the offending item identified.
4. Add tests for zero, negative, and positive quantities at template creation and application; verify invalid application creates no prescription/order/task rows and returns a deliberate client error rather than an unhandled 500.
5. Confirm whether quantity semantics differ for non-medication line types before applying a global constraint.

**Assessment:** Medium-priority CPOE template validation and failure-handling defect. It is not a bypass of the destination prescription quantity constraint; that database constraint prevents invalid prescription persistence. The gap is that invalid templates are accepted and fail later during clinical order-set application.

**Boundary:** exact-head static source/model review only. No patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.


## 174. CPOE templates accept medication and diagnostic items without their required catalog references

**Source reviewed:** PR #19 source head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`; `backend/domains/clinical/router.py`, `OrderSetItemInput`, `create_cpoe_order_set()`, and `apply_cpoe_order_set_to_encounter()`; `backend/domains/clinical/models.py`, `OrderSetItem`.

### 174.1 Incomplete typed line items can be persisted and silently omitted

The input contract makes both `medication_id` and `service_id` optional and has no cross-field validation tying either reference to `item_type`. The model likewise permits both references to be NULL.

The application route partitions persisted template items using these filters:

- Medication lines are included only when `item_type == MEDICATION` and `medication_id` is truthy.
- Diagnostic and radiology lines are included only when the item type is one of those types and `service_id` is truthy.

There is no validation that every persisted item of a supported type enters one of those execution lists. Thus, a `MEDICATION` item without `medication_id`, or a `DIAGNOSTIC_LAB`/`RADIOLOGY` item without `service_id`, can be accepted and committed in an active order-set template but is silently excluded when the template is applied. The endpoint can still return success, with lower medication/investigation counts than the template visually contains.

This is distinct from the already recorded handling of valid-but-unsupported nursing and dietary item types: Section 157 concerns supported-but-unimplemented categories; this finding concerns malformed records for categories the application claims to execute.

No malformed template or production omission is established.

### 174.2 Required remediation and acceptance evidence

1. Add discriminated validation: MEDICATION requires exactly a valid `medication_id`; DIAGNOSTIC_LAB and RADIOLOGY require exactly a valid `service_id`.
2. Reject contradictory references (both IDs supplied, or an ID supplied for the wrong item type) unless a documented domain rule explicitly permits them.
3. Add matching database constraints so non-API writes cannot create malformed typed rows.
4. Before applying any legacy template, validate every line and fail closed with a controlled 409/422 identifying invalid item IDs; do not report successful partial execution.
5. Add tests for missing, wrong-type, and contradictory references and assert that invalid application creates no prescription, diagnostic order, or task.

**Assessment:** Medium-priority CPOE template integrity and silent-omission defect. Database foreign keys protect non-null references from pointing to nonexistent catalog rows, but do not enforce the required relationship between `item_type` and the nullable reference columns.

**Boundary:** exact-head static source/model review only. No patient data or tenant database was accessed, and no runtime or migration changes were made. PostgreSQL database-per-tenant remains unchanged. AUD-004 remains blocked.
