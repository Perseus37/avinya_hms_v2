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
