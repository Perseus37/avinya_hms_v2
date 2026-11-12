# AUD-004 DBID-01–DBID-05 Resolution Proposal

**Status:** DESIGN PROPOSAL — NOT ACCEPTED / NOT AUTHORIZED FOR IMPLEMENTATION  
**Parent:** PR #45 — independent review of PR #44  
**ADR under amendment:** PR #44 — database-per-tenant identity architecture proposal  
**Scope:** PostgreSQL authorization, role/ownership separation, credential lifecycle, tenant provisioning, and source authorization audit durability  
**Release status:** AUD-004 remains a release blocker.

## 1. Purpose and disposition

This proposal translates the five High findings in PR #45 into normative, testable design requirements. It retains the inspected **database-per-tenant** topology. It does not introduce schema-per-tenant migration or select a cloud vendor, orchestrator, secret manager, or deployment platform.

This is not implementation authorization. Exact role names, PostgreSQL version compatibility, audit-store topology, operational service-level objectives, and governance owners remain subject to review. No deployed grants, credentials, secrets, patient data, or production state were inspected or changed.

| Finding | Resolution proposed | Required independent evidence |
|---|---|---|
| DBID-01 | Database CONNECT/TEMP allowlists, recursive membership review, safe creation window | PostgreSQL catalog snapshots and negative cross-database tests |
| DBID-02 | Non-login ownership roles, isolated runtime logins, object-level grants, privileged-object review | Ownership/membership graph, effective privilege tests, object inventory |
| DBID-03 | Immutable workload-to-tenant binding and versioned credential lifecycle | Secret-policy review, tenant isolation, rotation/revocation tests |
| DBID-04 | Fail-closed provisioning state machine with reconciliation | Failure injection at every state and catalog verification |
| DBID-05 | Explicit source audit commit barriers and uncertain-outcome protocol | Transaction-boundary failure injection and audit recovery proof |

DBID-06 (backup/restore), DBID-07 (deployment profile support), and DBID-08 (immutable routing/configuration binding) remain open as separate Medium findings. This proposal does not claim those findings are closed.

## 2. DBID-01 — Database-level access control

### 2.1 Normative database ACL

PostgreSQL roles are cluster-wide. Creating tenant-specific role names does not by itself isolate databases. Every tenant database MUST have an explicit, reviewed connection allowlist.

For each tenant database:

1. Revoke default CONNECT and TEMPORARY access from PUBLIC, unless a documented, narrowly scoped exception is approved.
2. Grant CONNECT only to exact tenant-local runtime login roles and separately approved operational identities that require it.
3. Grant TEMPORARY only where a demonstrated workload requirement exists; do not leave it available through PUBLIC by default.
4. Review database ownership and ensure it is not a general runtime login.
5. Apply the same explicit policy to the control-plane database and administrative databases, including postgres. Administrative access is not a runtime fallback.
6. Treat database ACLs as necessary but not sufficient: schema, object, role-membership, ownership, function and network controls must also pass.

Illustrative SQL only — not an instruction to run against any environment:

    REVOKE CONNECT, TEMPORARY ON DATABASE tenant_db FROM PUBLIC;
    GRANT CONNECT ON DATABASE tenant_db TO tenant_a_app;
    GRANT CONNECT ON DATABASE tenant_db TO tenant_a_source;

Actual allowlists MUST be generated from a versioned tenant role template and reviewed against the deployment profile. Do not blindly copy example identifiers.

### 2.2 Membership and effective privilege evaluation

The security review MUST inspect the full role graph, not just direct grants:

- all cluster roles and login status;
- recursive role memberships and grant options;
- PostgreSQL-version-specific INHERIT and SET ROLE semantics;
- predefined roles and memberships that confer equivalent powers;
- database owners, schema owners, object owners and grantors;
- CONNECT, TEMPORARY, schema and object privileges;
- SUPERUSER, CREATEDB, CREATEROLE, replication and bypass-RLS capabilities;
- connection paths through foreign data wrappers, database-link extensions or privileged functions.

A tenant runtime login MUST NOT inherit or be able to assume a role that grants access to another tenant database, cluster administration, provisioning, migration, backup administration, or protected object ownership. Membership checks MUST use the actual PostgreSQL version's semantics; NOINHERIT alone is not proof that SET ROLE is impossible.

For every source/app/control-plane runtime identity, the conformance suite MUST evaluate effective database and object privileges, including the ability to connect to every other tenant database. Any unexpected grant, membership, owner path, or privilege-bearing function fails readiness.

### 2.3 New-database exposure window

A database MUST NOT become routable or reachable by ordinary runtime identities between CREATE DATABASE and completion of ACL hardening.

The provisioning controller MUST:

- create the database in a non-routable, not-ready state;
- immediately apply owner assignment and restrictive database ACLs using a controlled provisioning identity;
- verify effective ACLs and role memberships before registering a source workload or publishing a routable endpoint;
- prevent application, source, control-plane and import workloads from discovering or connecting to the database until provisioning reaches READY;
- on any failure, keep the database quarantined and non-routable.

Where the managed PostgreSQL service cannot guarantee atomic creation plus ACL hardening, the design MUST prove that no untrusted runtime principal can connect during the interval. A cleanup job alone is not adequate.

### 2.4 DBID-01 acceptance evidence

- Versioned catalog report for pg_roles, pg_auth_members, pg_database owners/ACLs, and relevant object ownership.
- Effective CONNECT/privilege checks for every tenant app/source/control-plane login against all tenant databases and administrative databases.
- Negative tests for direct and inherited membership, role switching, and privileged indirect access.
- Provisioning failure test showing that a just-created but not-yet-hardened database cannot be reached by runtime identities.
- Evidence is environment-specific, timestamped, reviewed, and contains no credentials or patient data.

## 3. DBID-02 — Ownership and object-level privilege model

### 3.1 Separate owner roles from login roles

Each tenant database MUST use non-login ownership roles for protected database objects. Runtime login roles MUST NOT own databases, protected schemas, patient/clinical tables, source-policy tables, audit tables, or privileged functions.

| Role class | Login allowed? | Responsibility | Explicit prohibition |
|---|---:|---|---|
| Tenant object owner | No | Own approved schemas/tables/functions | No runtime login or request handling |
| Tenant app login | Yes | Same-tenant application CRUD | Cannot assume source, owner, migration, backup or provisioning roles |
| Tenant source login | Yes | Minimum source authorization, approved reads and source audit writes | Cannot assume owner or migration; cannot connect to another tenant DB |
| Tenant migration login | Controlled job only | Apply migrations to enumerated tenant DBs | Never mounted in API/source/worker runtime |
| Tenant backup identity | Controlled job only | Approved backup and restore operations | No interactive clinical query role |
| Cluster provisioning identity | Short-lived controlled workflow | Create DBs/roles and harden initial ACLs | Never used by application or source request paths |

Role names and exact grant structure are implementation-specific, but the separation properties are mandatory.

### 3.2 Membership direction and escalation prohibitions

- App login MUST NOT be a member of, inherit from, or be able to SET ROLE to source, object-owner, migration, backup, or provisioning roles.
- Source login MUST NOT be able to assume object-owner, migration, backup, or provisioning roles.
- Migration login MUST be unavailable to runtime containers and MUST be restricted to explicitly enumerated target databases.
- Backup and restore identities MUST be separate from interactive app/source logins.
- No runtime identity may have SUPERUSER, CREATEDB, CREATEROLE, replication, or equivalent cluster-wide privilege unless a separately reviewed, time-bounded exception is approved. Such an exception cannot be used for federation.
- Runtime logins MUST NOT own protected objects or create arbitrary functions, triggers, extensions, schemas, or objects that can execute with elevated privileges.

### 3.3 Explicit source object grants

The source login receives only object-level rights required for the source-owned protocol. The grant matrix MUST enumerate, by schema and object:

- source clinician identity/affiliation/credential-status lookup;
- source authorization policy and purpose/scope registry lookup;
- bounded selector resolution;
- candidate patient/resource reads;
- minimum allergy/clinical data reads approved for the protocol;
- source audit append operations;
- source-side challenge, replay and disclosure state.

Do not grant broad schema-wide or all-table SELECT/INSERT/UPDATE by convenience. Where broad read scope is proposed, document the source service compromise blast radius and obtain explicit security/privacy review. The destination app login MUST have no direct grant to source-only policy, challenge, replay, or audit objects.

### 3.4 Privileged object and bypass inventory

Before implementation approval, inventory and review:

- SECURITY DEFINER functions, including owner, search path, execute grants and dynamic SQL;
- views/materialized views and their security behavior;
- triggers and functions that write or disclose protected data;
- extensions and any database-link/FDW/dblink capability;
- stored procedures, event triggers and replication paths;
- row-level security policies, table owners, BYPASSRLS, and any role able to alter/disable policies.

RLS, where used, is supplementary. It MUST NOT replace database-per-tenant isolation or source authorization. Runtime roles must not bypass or rewrite the controls they depend on.

### 3.5 DBID-02 acceptance evidence

- Reviewed role-membership graph, login/non-login classification, database ownership and object-ownership matrix.
- Effective checks using has_database_privilege, has_schema_privilege, has_table_privilege and has_function_privilege (or version-equivalent inspection).
- Negative tests for cross-tenant CONNECT, SET ROLE, ALTER/DROP protected objects, CREATE FUNCTION/EXTENSION, protected-table reads, and source-audit tampering from app identities.
- Independent review of privileged functions, extensions and cross-database capable objects.
- Evidence must run under actual deployed runtime login identities, not a superuser test account.

## 4. DBID-03 — Workload identity and credential lifecycle

### 4.1 Immutable workload-to-tenant binding

Each source workload MUST be provisioned with a protected binding containing at least:

- immutable tenant identifier;
- source workload identity (issuer, subject and deployment identity);
- expected tenant database name/identifier;
- exact secret reference and permitted secret-version policy;
- configuration/provisioning record version;
- approved source service protocol version.

The binding is established by a privileged provisioning workflow and protected against request-time or ordinary control-plane mutation. A caller MUST NOT supply or override tenant ID, database name, DSN, username, password, secret reference, or workload identity.

At startup and every authorized configuration refresh, the source service MUST verify that workload identity, tenant assignment, database identity and secret reference agree. A mismatch, missing binding, stale/invalid configuration, or inability to verify the binding prevents readiness and all protected source operations. DBID-08 remains open for a broader signed/configuration-record design review.

### 4.2 Bootstrap and secret retrieval

- Provisioning creates a tenant-scoped DB login and registers its secret through the approved secret-management workflow.
- The source workload authenticates to the secret manager using its workload identity, not a static fleet credential.
- Secret policy permits the workload to retrieve only the secret for its immutable tenant assignment.
- No source workload has fleet-wide or wildcard tenant-secret read permission.
- Destination workloads, import workers and control-plane request handlers cannot retrieve source DB passwords or connection strings.
- Secret references are identifiers, not bearer authorization.
- Secret values MUST NOT appear in logs, traces, metrics, crash dumps, image layers, repository files, support bundles, or deployment metadata.

### 4.3 Credential states

The lifecycle is:

    CREATED → REGISTERED → BOUND → ACTIVE → ROTATION_PENDING → OVERLAP_ACTIVE → OLD_CREDENTIAL_REVOKED

Exceptional states include REVOKE_PENDING, REVOKED, QUARANTINED and RECOVERY_REQUIRED.

Each transition is an audited control-plane operation with an actor, reason, tenant binding, secret version, correlation ID, timestamp and outcome. The audit record MUST NOT include the secret value.

### 4.4 Planned rotation

1. Create a new tenant-scoped credential without widening its grants.
2. Register a new immutable secret version and authorize only the bound source workload to retrieve it.
3. Move the source workload to the new version through a controlled, observable rollout.
4. Create new SQLAlchemy engines/pools bound to the new credential; verify tenant identity and effective privileges.
5. Stop new work on old pools, drain in-flight work within an approved bound, dispose old pools, and terminate old sessions where required by the threat model.
6. Revoke the old credential and verify that new authentication with it fails and old sessions are no longer usable.
7. Mark rotation complete only after independent verification; otherwise quarantine the source workload and retain a recoverable, non-disclosing state.

No request may dynamically swap credentials or database identity inside a shared pool.

### 4.5 Emergency revocation and outages

For suspected compromise, the incident procedure MUST support immediate disable/revoke of the tenant credential, termination of active sessions, source workload isolation, pool disposal, and quarantine of affected source operations. The maximum revocation interval is a governance/operations decision and MUST be set before production approval; this proposal does not invent an SLA.

If the secret manager is unavailable, identity cannot be attested, the secret version is stale, or revocation status cannot be checked at a required checkpoint, protected source access fails closed. There is no fallback to the global DATABASE_URL, another tenant's secret, cached fleet credential, or caller-supplied DSN. Any bounded cache policy requires explicit security approval and a tested revocation limit.

### 4.6 DBID-03 acceptance evidence

- Secret-manager policy and workload identity mapping reviewed by platform/security owners.
- Tenant A workload cannot retrieve Tenant B's secret, including through aliases, versions, group membership or control-plane manipulation.
- Rotation test demonstrates new-pool activation, old-pool disposal, old credential rejection and active-session termination where required.
- Emergency revocation test demonstrates enforcement within the formally approved interval.
- Outage/stale-cache tests prove fail-closed behavior and no global credential fallback.
- Secret scanning and log/trace/crash-dump tests find no credential material.

## 5. DBID-04 — Provisioning and migration state machine

### 5.1 Required state machine

Tenant database provisioning MUST follow this controlled lifecycle:

    REQUESTED → DATABASE_CREATED → OWNER_ASSIGNED → RUNTIME_ROLES_CREATED
      → PUBLIC_ACCESS_REVOKED → ACL_VERIFIED → SECRET_REGISTERED
      → SERVICE_BOUND → READY

Any failure transitions to QUARANTINED or RECONCILIATION_REQUIRED. No partially provisioned tenant is routable or ready.

### 5.2 State requirements

| State | Required action and evidence | Runtime availability |
|---|---|---|
| REQUESTED | Approved tenant request, unique operation ID, authorized provisioning actor | Denied |
| DATABASE_CREATED | Database created in non-routable state; observed catalog identity recorded | Denied |
| OWNER_ASSIGNED | Non-login owner assigned; runtime identities do not own protected objects | Denied |
| RUNTIME_ROLES_CREATED | Tenant-scoped app/source/migration/backup role classes created with least privilege | Denied |
| PUBLIC_ACCESS_REVOKED | PUBLIC CONNECT/TEMP revoked; explicit allowlist applied | Denied |
| ACL_VERIFIED | Effective ACL, membership, ownership and cross-DB checks pass | Denied |
| SECRET_REGISTERED | Tenant-specific credential version stored and policy-bound | Denied |
| SERVICE_BOUND | Immutable workload/tenant/DB/secret binding verified; source identity attested | Denied |
| READY | All evidence attached, readiness check passes, routing explicitly enabled | Allowed within approved role scope |

### 5.3 Provisioning authority and idempotency

- Cluster-level CREATE DATABASE and role-creation authority belongs only to a short-lived provisioning identity.
- Database migrations use a separate identity restricted to explicitly enumerated target databases; migration authority does not imply cluster administration.
- Provisioning and migration credentials are never mounted into API, source, import, background, support or control-plane runtime containers.
- Every request has a unique provisioning operation ID and tenant binding.
- Retries are idempotent. They inspect actual PostgreSQL catalogs and secret-manager state before resuming; they do not blindly replay grants or assume the previous step succeeded.
- Conflicting catalog state, unexpected role ownership, unexpected ACL, unknown secret version or tenant mismatch stops the operation and enters reconciliation.
- READY is a derived state requiring all mandatory evidence; it cannot be set by a caller or inferred from database existence.
- Tenant deprovisioning/re-provisioning MUST use new credential material and verify stale memberships, database ACLs, secrets and workload bindings are not reused.

### 5.4 Migration constraints

A migration job may connect only to the explicitly approved tenant database set for that migration run. It cannot create arbitrary databases or roles, retrieve tenant source secrets, perform federation source reads, or serve application traffic. Runtime role grants and object ownership are verified after migration, including newly created objects and default privileges.

### 5.5 DBID-04 acceptance evidence

- Failure injection after every state transition, including process crash and retry.
- Catalog and secret-manager reconciliation tests for partial, duplicate and conflicting state.
- Runtime identities cannot connect before READY, including during database creation and hardening.
- Provisioning credentials absent from all runtime deployment definitions and process environments.
- Migration role cannot create unrelated databases/roles or connect outside the approved target list.
- Re-provision and restore tests prove old credentials/memberships are not silently reused (detailed backup/restore controls remain DBID-06).

## 6. DBID-05 — Source authorization audit and transaction boundaries

### 6.1 Separate lifecycle events

The source service MUST distinguish at least these events:

1. NODE_AUTHENTICATED — transport/service identity accepted.
2. ACTOR_ASSERTION_VERIFIED — clinician assertion cryptographically and semantically verified.
3. SOURCE_ACTOR_RESOLVED — source-controlled clinician identity, affiliation and status resolved.
4. DISCOVERY_SEARCH_AUTHORIZED — bounded search action/purpose/destination/scope/budget authorized before selector resolution.
5. SELECTOR_RESOLVED — selector outcome recorded without exposing unnecessary selector values.
6. CANDIDATE_AUTHORIZED — each candidate/resource independently authorized.
7. DISCLOSURE_INTENT_COMMITTED — durable intent exists before protected response serialization/release.
8. RESPONSE_GENERATED — minimum authorized response and integrity envelope generated.
9. DELIVERY_ATTEMPTED / DELIVERY_OUTCOME_UNCERTAIN — transport attempt and uncertainty recorded distinctly.
10. DESTINATION_ACK_VERIFIED — exact destination acknowledgement cryptographically and semantically verified.
11. SOURCE_OPERATION_RECONCILED — uncertain operation resolved using authoritative evidence.

Node authentication, clinician authorization, selector matching, disclosure intent, network write, destination commit and acknowledgement MUST NOT be collapsed into one generic success event.

### 6.2 Authoritative audit store and commit barrier

Before implementation approval, the architecture owner MUST select and document the authoritative source audit store and its failure model.

The mandatory safety rule is:

**No patient-specific selector resolution or protected source read may occur until the required source authorization/search audit event is durably committed. No protected response may be released until the required candidate authorization and disclosure-intent evidence is durably committed.**

If the authoritative audit store is in the same PostgreSQL database, the authorization state and audit event SHOULD be committed in one transaction before selector resolution begins in a subsequent transaction. A rollback means authorization did not commit and the operation must stop.

If the audit store is a separate database/service, a normal asynchronous outbox written only in the clinical database is insufficient as the sole pre-read barrier: it does not prove the independent audit store durably accepted the event. The source service MUST synchronously obtain a durable audit-store commit acknowledgement before proceeding to selector resolution or disclosure. The audit event carries a stable event ID and idempotency key so retries do not duplicate semantic events.

If the audit service is unavailable, commit outcome is unknown, or acknowledgement cannot be verified, the source service MUST NOT proceed to selector resolution, protected reads, response release or success acknowledgement. It enters an explicit retryable or outcome-uncertain state for reconciliation.

### 6.3 Candidate authorization and disclosure boundary

For every candidate/resource:

1. Resolve the candidate only after search authorization is durably committed.
2. Evaluate source-controlled actor, affiliation/status, action, purpose, destination, resource, data category, scope and current policy.
3. Persist candidate authorization outcome and disclosure intent durably before serializing/releasing protected fields.
4. If the required audit write fails, no protected payload is released.
5. If multiple candidates exist, authorization and disclosure intent are independently bound to each candidate/resource; one candidate's authorization cannot authorize another.
6. Record only the minimum selector commitment and identifiers required for audit. Raw phone, ABHA, MRN, DOB, patient names, credentials and assertion tokens MUST NOT be copied into ordinary telemetry. Selector commitment design remains subject to CAN-02 privacy requirements.

### 6.4 Cross-database and network outcomes

The source audit store, tenant clinical database and destination system do not share a single ACID transaction. The protocol MUST model boundaries explicitly:

- durable search authorization commit;
- candidate/resource authorization and durable disclosure-intent commit;
- source response generation;
- network delivery attempt;
- destination validation and durable commit;
- destination acknowledgement creation and source verification.

A network write is not proof of delivery. A generated response is not proof of destination commit. A destination commit is not proof that source acknowledgement was received. A pointer/index update is a separate operation and cannot be represented as completed merely because the patient clone committed.

If a failure occurs after disclosure intent but before a verifiable outcome, record OUTCOME_UNCERTAIN; do not synthesize success or erase the disclosure attempt. Reconciliation uses stable operation/event IDs and authoritative destination commit evidence. A retry that requires a new source read must obtain fresh source authorization and a fresh audit barrier; a retry must not silently reuse an expired authorization.

Where a transactional outbox is used for downstream delivery or audit replication, its exact semantics MUST be documented. The outbox can provide reliable eventual delivery after a committed event; it does not replace the synchronous authorization/audit barrier required before source disclosure.

### 6.5 Audit integrity and recovery

Source security audit is authoritative for source authorization and disclosure. Destination import audit is authoritative for destination-side clone/commit. Trust/control-plane audit is authoritative for issuer, key, partner and workload configuration changes. Operational telemetry is non-authoritative and MUST NOT be used to infer clinical authorization or disclosure success.

Audit records MUST include stable event and operation IDs, source tenant/workload identity, actor reference, destination, action, purpose, resource/scope reference, policy/protocol version, decision, event time, commit evidence and outcome. Exact fields and retention remain subject to D-12 and privacy/legal approval. Never log raw secrets, bearer credentials, full clinician assertions, or unnecessary patient identifiers.

Corrections are append-only and linked to the original event; audit rows are not silently edited or deleted to hide a failed or uncertain outcome. Backup/restore must preserve audit integrity and is additionally subject to DBID-06.

### 6.6 DBID-05 acceptance evidence

- Failure-injection tests for audit store unavailable, commit timeout, ambiguous commit result, duplicate event, clinical DB failure, candidate denial, disclosure-intent failure, response serialization failure, network disconnect, destination commit uncertainty, acknowledgement loss and reconciliation.
- Instrumented tests prove no selector query occurs before durable search authorization commit.
- Tests prove no protected payload is serialized/released before durable candidate authorization and disclosure-intent commit.
- Tests prove network write cannot create a delivery/acknowledgement success record by itself.
- Tests prove a retry after authorization expiry requires fresh authorization for any new source read.
- Independent audit-store availability, tamper-evidence, access-control and recovery review.

## 7. Integrated conformance gate

DBID-01 through DBID-05 are considered design-resolved only when all of the following are true:

- The ADR adopts the database-per-tenant ACL and role-ownership model.
- PostgreSQL version-specific membership and privilege semantics are explicitly tested.
- Source/app/control-plane/migration/provisioning/backup identities are separately mapped and reviewed.
- Workload identity is immutably bound to one tenant database and one secret scope.
- Rotation, emergency revocation, pool disposal and outage behavior are demonstrated.
- Provisioning is fail-closed until verified READY, with failure-injection evidence.
- Source audit commit barriers prevent unauthorized or unaudited selector resolution and disclosure.
- DBID-06 through DBID-08 are separately resolved before production-capable implementation design approval.
- Independent database, application-security, platform/operations, privacy/legal and clinical reviewers accept the evidence.
- Formal D-01–D-14 governance decisions and implementation authorization are recorded.

A design document or passing synthetic test does not establish production configuration compliance. Production catalog, secret, workload, network and backup evidence must be collected only under separately approved access and change controls.

## 8. Decisions deliberately left open

The following MUST be decided by responsible owners before implementation authorization:

- supported PostgreSQL versions and managed-service constraints;
- exact tenant role names and source object grant inventory;
- secret manager and workload identity provider;
- rotation overlap duration and emergency revocation maximum;
- provisioning operator/dual-control model and evidence retention;
- authoritative source audit store topology and availability objective;
- audit event retention, residency, legal hold and disposal under D-12;
- shared-cluster, dedicated-cluster and on-premise support profiles;
- backup/restore quarantine and re-hardening under DBID-06;
- immutable routing/configuration binding under DBID-08.

No value is silently defaulted by this proposal.

## 9. Explicit non-authorization and stop conditions

This proposal authorizes documentation and independent review only. It does NOT authorize:

- runtime code changes or federation route refactoring;
- SQL execution, database creation, role creation, grants, revocations or ACL changes;
- credential or secret-manager creation, retrieval, rotation, revocation or policy changes;
- production catalog inspection or production infrastructure access;
- patient-data access, import, export, query, migration or backup restoration;
- partner onboarding, trust/key provisioning, federation activation, emergency access or pilot;
- deployment, release, merge, or removal of the AUD-004 release blocker.

PRs #44 and #45 remain draft and unmerged. AUD-004 remains a release blocker. Project direction D-11 YES is not formal governance approval. All D-01–D-14 decisions remain subject to the governance register; no clinical, privacy/legal, security, database or operational approval is inferred here.
