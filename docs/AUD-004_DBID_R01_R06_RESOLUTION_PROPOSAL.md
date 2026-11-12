# AUD-004 DBID-R01–DBID-R06 Resolution Proposal

**Status:** DESIGN PROPOSAL — NOT ACCEPTED / NOT AUTHORIZED FOR IMPLEMENTATION  
**Parent review:** PR #47 — independent review of DBID-01–DBID-05 resolution  
**Architecture baseline:** Database-per-tenant PostgreSQL; no schema-per-tenant migration is proposed  
**Release status:** AUD-004 remains a release blocker.

## 1. Purpose and boundaries

This proposal resolves the six design findings recorded in PR #47. It defines enforceable provisioning isolation, PostgreSQL schema/object privilege baselines, pre-authorization query minimization, revocation checkpoints, connection-session invalidation, and an auditable read-set/digest contract.

The controls below are normative design requirements for a future implementation review. They are not evidence that any deployed database, network, identity provider, secret manager, or audit store currently satisfies them. Provider-specific capabilities and exact policy values remain subject to review.

This proposal does not close DBID-06 through DBID-08, CAN-01, or AUD-004. It does not supersede the formal D-01–D-14 governance register. D-11 project direction YES remains distinct from formal governance approval.

## 2. DBID-R01 — Enforceable isolation during database creation and hardening

### 2.1 Selected baseline

A new tenant database MUST be created inside a **provisioning-only network/cluster security boundary** that is unreachable from application, source, import, background, support, control-plane and ordinary operator workloads. That boundary remains in force until database ACLs, role membership, object ownership, schema defaults and workload bindings have been independently verified.

A routing flag or absence of a service-discovery entry is not a security boundary. Runtime principals MUST have no network path to the provisioning listener during the pre-READY interval, even if they know the database name and credentials.

A hardened template with restrictive database and schema ACL defaults SHOULD be used as defense in depth, but template ACLs do not replace network isolation. The implementation ADR must select a provider-specific isolation mechanism that actually denies connections at the network/cluster boundary. If the hosting platform cannot demonstrate that property, provisioning MUST use a separate isolated PostgreSQL cluster or equivalent boundary until hardening is complete.

### 2.2 Provisioning state reachability matrix

| Provisioning state | Permitted network identities | Runtime identities | Required gate |
|---|---|---|---|
| REQUESTED | Provisioning control plane only; no tenant DB listener | Denied | Approved request and unique operation |
| DATABASE_CREATED | Provisioning identity on isolated provisioning network | Denied; no route or network path | Database identity recorded |
| OWNER_ASSIGNED | Provisioning identity only | Denied | Non-login owner verified |
| RUNTIME_ROLES_CREATED | Provisioning identity only | Denied | Role/membership inventory verified |
| PUBLIC_ACCESS_REVOKED | Provisioning identity only | Denied | Database ACL hardening committed |
| ACL_VERIFIED | Provisioning identity and isolated verifier | Denied | Effective database/schema/object ACL checks pass |
| SECRET_REGISTERED | Provisioning identity and secret broker | Denied | Tenant-bound secret policy verified |
| SERVICE_BOUND | Provisioning identity, attestation verifier and target source workload on controlled path | Denied until binding verification succeeds | Immutable tenant/workload/database/secret binding |
| READY | Only explicitly authorized tenant workload identities | Allowed only within assigned tenant and role scope | Independent readiness evidence and controlled route enablement |

No state transition may create a temporary exception for a general runtime identity. The provisioning listener is not exposed to runtime subnets, shared ingress, public networks or peer tenant workloads.

### 2.3 Atomicity, failure and recovery

PostgreSQL database creation and subsequent ACL hardening are separate operations. The design MUST therefore rely on the external network boundary as the primary pre-hardening control, not on an assumption that the SQL steps are atomic.

If any ACL, role, schema, ownership, secret-binding or attestation step fails, the database remains isolated and enters QUARANTINED or RECONCILIATION_REQUIRED. The workflow MUST NOT attach a runtime route, publish a usable runtime secret, or mark READY.

The provisioning workflow MUST verify the network boundary from the perspective of every runtime identity class, not merely inspect a desired-state configuration. A control-plane status flag is insufficient evidence.

### 2.4 Required evidence and tests

- State-by-state network and identity reachability matrix for each supported deployment profile.
- Automated direct-connect denial attempts from app, source, import, background, support, control-plane and peer-tenant workloads immediately after database creation and before ACL hardening.
- Tests with the database name known to the attempted runtime workload, proving name secrecy is not the control.
- Positive tests proving only the provisioning identity can connect during pre-READY states.
- Template/default ACL catalog assertions before and after PostgreSQL upgrades and database cloning.
- Network policy drift detection and fail-closed behavior if the provisioning boundary cannot be verified.
- Failure injection after every provisioning transition; no path may reach READY after partial failure.

## 3. DBID-R02 — Normative schema, function and default-privilege baseline

### 3.1 Versioned policy

Each supported PostgreSQL major version MUST have a versioned tenant-database privilege baseline. The baseline applies to the database, the public schema, every application/source schema, extensions, functions, sequences, types and any future schema introduced by migrations.

A PostgreSQL upgrade is not accepted solely because existing grants remain present. The upgrade gate MUST re-evaluate effective privileges and default-privilege behavior under the new major version.

### 3.2 Required default posture

Unless a documented, reviewed exception is necessary:

- Revoke database CONNECT and TEMPORARY from PUBLIC; grant CONNECT only to explicitly approved tenant role identities.
- Revoke PUBLIC CREATE and USAGE on the public schema where not required. Do not assume the public-schema defaults of one PostgreSQL major version apply to another.
- Revoke PUBLIC CREATE/USAGE on application and source schemas unless a narrowly justified use requires them.
- Revoke PUBLIC EXECUTE on functions/procedures where not required; explicitly grant execution to named roles.
- Runtime app/source roles MUST NOT own protected schemas, tables, sequences, functions, extensions or privileged objects.
- Use non-login owner roles. Runtime identities must not inherit owner authority or be able to SET ROLE into owner, migration, provisioning or backup roles.
- Avoid broad membership chains, role attributes, ownership transfer paths and SECURITY DEFINER functions that allow privilege escalation.
- Extensions are installed only by a controlled migration/provisioning identity and are reviewed for their objects, functions and required privileges.

Any exception must name the object, principal, required operation, reason, approving owner, expiry/review date and compensating control. No wildcard PUBLIC grant is accepted as an undocumented exception.

### 3.3 ALTER DEFAULT PRIVILEGES contract

For every role that can create objects, the baseline MUST define default privileges for each target schema. Default-privilege policy must cover, where supported by the target PostgreSQL version:

- tables and views;
- sequences;
- functions and procedures;
- types and domains;
- schemas or other object classes where the platform/version exposes applicable default ACL controls.

The policy must account for PostgreSQL's creator-role-specific default privileges. A global default ACL configured for one owner does not silently cover objects created by another migration or extension owner. All approved object-creating roles must be enumerated and tested.

### 3.4 Migration and object-creation gate

Every migration MUST run under its explicitly approved migration identity and target database allowlist. Before migration completion or tenant READY, an automated catalog verifier MUST enumerate newly created and changed objects and assert:

1. expected owner;
2. expected schema;
3. expected ACL, including absence of unintended PUBLIC grants;
4. expected default-privilege behavior for subsequent objects;
5. no unexpected SECURITY DEFINER function, unsafe search_path, unreviewed extension, foreign data wrapper, dblink or equivalent cross-database capability;
6. no ability for app/source runtime identities to assume privileged roles or alter protected objects.

The verifier MUST fail the migration/READY gate on unknown object types, unknown owners, unknown grants, unreviewed functions or inability to inspect effective privileges. “No rows returned” is not a pass when catalog inspection failed.

### 3.5 Required evidence and tests

- Versioned PostgreSQL major-version policy and generated catalog assertions.
- Tests create tables, views, sequences, functions, procedures and types under each permitted object-creating identity and verify resulting owners/grants.
- Negative tests for PUBLIC schema creation, PUBLIC function execution, unauthorized object reads/writes, SET ROLE, ownership changes, extension creation and SECURITY DEFINER misuse.
- Migration tests that deliberately introduce an unsafe grant/object and prove the gate fails before READY.
- Extension inventory and review of privileged functions, search_path, ownership and execute grants.
- Effective privilege tests executed using the actual runtime login identities in a controlled test environment, not a superuser substitute.

## 4. DBID-R03 — Opaque candidate resolution before candidate authorization

### 4.1 Two distinct source queries

Source discovery MUST use two separate data-access stages:

**Stage A — minimal selector resolution (before candidate authorization):**
- Runs only after durable DISCOVERY_SEARCH authorization/audit.
- Uses a narrowly scoped query or database function.
- Returns only an opaque, source-local candidate/resource reference and the minimum non-clinical metadata strictly necessary to continue authorization.
- Does not hydrate a Patient ORM entity or load demographics, ABHA, phone, DOB, address, allergies, encounters, documents, prescriptions, diagnoses or other clinical/personal payload.
- Does not trigger eager relationships, deferred columns, serializer access or implicit lazy loads.

**Stage B — protected projection (after candidate authorization):**
- Runs only after source-controlled candidate authorization has been durably committed for that opaque resource reference and exact requested scope.
- Retrieves only the approved fields/data categories in the canonical projection.
- Uses an explicit query projection/column allowlist rather than unrestricted entity loading.
- Produces the response artifact only after the required disclosure-intent barrier has committed.

A selector match is not itself authority to read or disclose patient data.

### 4.2 Query and ORM enforcement

The implementation MUST enforce the boundary at the SQL/ORM layer, not only by convention in route handlers.

- Selector-resolution repositories expose a dedicated return type containing only opaque identifiers and approved minimal metadata.
- They MUST NOT return ORM entities or relationship-bearing objects.
- Protected patient models MUST NOT be passed to selector-resolution code paths.
- Query projections are explicit and versioned; wildcard entity selection is prohibited before candidate authorization.
- Eager loading, joined loading, deferred-column access and lazy relationships are prohibited before authorization.
- Serializers and logging hooks MUST NOT access protected model properties before the authorization boundary.
- Any unexpected query, projection, relationship load or field access is a security failure and stops the operation.

### 4.3 Denial and ambiguity behavior

Denied, ambiguous, unavailable and no-match outcomes MUST not disclose whether a particular patient exists or which candidate matched. Audit records may record the internal decision and opaque operation/resource references under approved access controls, but external responses follow the approved anti-enumeration contract. No match-specific metadata is returned to an unauthorized caller.

### 4.4 Required evidence and tests

- SQL statement instrumentation proves selector resolution selects only the approved opaque reference/minimal metadata.
- Tests fail if patient, allergy, encounter, document or other clinical tables/columns are queried before candidate authorization.
- Tests exercise eager/lazy ORM paths, serializers, logging, exception handlers and background callbacks.
- A deliberately added relationship or deferred field must not be loaded before authorization.
- Candidate authorization is bound to the opaque source resource reference; another resource cannot reuse the decision.
- Post-authorization query tests prove the actual projection exactly matches the authorized projection, with no widened or wildcard fields.

## 5. DBID-R04 — Revocation domains, freshness checkpoints and race outcomes

### 5.1 Revocation domains

The protocol MUST treat these as separate revocation domains with independently authoritative sources:

1. issuer identity and signing-key trust (including key compromise, retirement and rotation);
2. clinician identity proofing, registration/licensure, status and source-approved affiliation;
3. partner/hospital/node eligibility and destination status;
4. source action, purpose, data-category and scope policy;
5. source workload identity and tenant/database binding;
6. tenant database credential, role membership and session validity;
7. source audit service availability/integrity where the audit barrier is mandatory.

A positive result in one domain cannot substitute for freshness in another. A destination-supplied clinician assertion does not override source-controlled identity, registration or affiliation state.

### 5.2 Mandatory checkpoints

| Checkpoint | Required checks before proceeding |
|---|---|
| Before search authorization | Node/workload identity, issuer/key trust, actor assertion validity, clinician status/affiliation, destination eligibility, action/purpose/scope policy, tenant binding, audit-store readiness |
| Immediately before selector resolution | Search authorization still current; relevant issuer/key, clinician, destination, policy, workload and DB credential revocation state within approved freshness bounds |
| Before candidate authorization | Revalidate actor, affiliation/status, destination, action/purpose/scope policy and source resource policy; bind decision to opaque resource |
| Before disclosure-intent commit | Revalidate every revocation domain relevant to the authorized projection; verify operation, destination and policy versions have not changed |
| Immediately before protected read/response release | Confirm disclosure intent is durable and current; recheck revocations whose race window can still be closed; verify credential/session and source workload binding |
| Before retry/recovery source read | Obtain fresh source authorization and audit barrier; never inherit an expired or superseded authorization |

The implementation must define whether checks are obtained through strongly consistent reads, bounded caches, signed revocation snapshots or another reviewed mechanism. An unbounded cache or best-effort asynchronous propagation is not acceptable for a required checkpoint.

### 5.3 Freshness ownership and values

For each domain, the governance/operations register MUST name:
- authoritative system of record;
- accountable owner;
- maximum permitted freshness/propagation interval;
- cache behavior and invalidation mechanism;
- behavior when the authority is unavailable or returns an indeterminate result;
- evidence source and monitoring;
- emergency override prohibition/approval process, if any.

No numeric freshness interval is silently chosen in this proposal. Exact intervals require security, clinical, privacy/legal and operational approval before implementation authorization.

### 5.4 In-flight revocation and deterministic outcomes

Revocation is evaluated at each checkpoint. If revocation is observed before protected payload release, the source MUST stop disclosure, preserve the denial/revocation event and return only the approved non-enumerating outcome.

If revocation occurs after an irreversible disclosure boundary (for example, bytes may already have left the source process), the source MUST NOT claim that disclosure was prevented. It records OUTCOME_UNCERTAIN or the appropriate verified delivery outcome, stops further reads/retries, and invokes the approved incident/quarantine workflow. It must not silently mark success, erase the event or repeat the disclosure.

A retry that performs a new source read requires fresh actor, destination, policy and workload authorization plus a new durable audit barrier. A previous authorization decision or disclosure intent is not a reusable bearer capability.

### 5.5 Required evidence and tests

- Concurrent revocation tests for key, clinician registration/status/affiliation, partner/destination, purpose/scope policy, workload identity and DB credential.
- Deterministic expected outcomes at each checkpoint, including just-before and just-after disclosure-intent commit and payload release.
- Tests for unavailable or indeterminate revocation authorities; all required checks fail closed.
- Cache-expiry, stale snapshot, delayed invalidation and clock-skew tests.
- Retry/recovery tests prove stale authorization cannot authorize a new source read.
- Audit reconciliation proves a possibly disclosed response is never represented as “not disclosed” without authoritative evidence.

## 6. DBID-R05 — Connection-pool and PostgreSQL session invalidation

### 6.1 Required lifecycle

Credential rotation or emergency revocation MUST implement and verify the following sequence:

1. Mark the old credential version REVOKE_PENDING and block new work from selecting it.
2. Stop new pool checkouts and prevent new engine/pool creation using the old version.
3. Drain in-flight work within the approved bound; cancel or fail work that cannot safely complete.
4. Close or invalidate checked-out connections, including connections held by long-running tasks; engine.dispose() alone is not proof that these sessions ended.
5. Dispose the old SQLAlchemy engine/pool and verify no new checkout is possible.
6. Revoke the old PostgreSQL credential or its effective login path.
7. Terminate remaining PostgreSQL backend sessions for the old tenant role/credential where required by the incident/rotation policy. Termination must be scoped to the exact tenant identity and must not disrupt unrelated tenants.
8. Verify through authoritative database-side evidence that the old credential cannot authenticate new sessions and that all sessions required to be terminated are gone.
9. Mark rotation/revocation complete only after the evidence is recorded. Otherwise retain REVOKE_PENDING/QUARANTINED and escalate.

The implementation must account for connection proxies/poolers, multiple service replicas, background workers, stale process configuration, prepared statements and long-lived transactions. Terminating a database backend does not by itself prove every application process has stopped trying to reconnect.

### 6.2 Session identity and verification

Every tenant source connection MUST carry a verifiable tenant/workload/credential-version identity in its connection metadata, such as a controlled application_name convention plus server-side role identity. Caller-controlled values are not trusted as the sole identity proof.

The revocation verifier must query PostgreSQL session state (for example, pg_stat_activity where supported and authorized) or an equivalent managed-service authoritative interface. It must distinguish expected new-version sessions from old-version sessions and verify the old login is unable to establish another session.

If session identity cannot be reliably attributed, the system cannot claim revocation completion; isolate the source workload/tenant and require operator reconciliation.

### 6.3 Required evidence and tests

- Long-running checked-out connection test across planned rotation.
- Emergency revocation test with active transactions, idle sessions, multiple replicas and background workers.
- Test proves new checkout is blocked before old credential revocation.
- Test proves engine disposal does not cause a false “all sessions closed” result.
- Server-side observation proves old sessions are terminated when required and old credential cannot establish new sessions.
- Pooler/proxy tests verify revocation propagates through every connection layer.
- Revocation completion state is impossible until independent session evidence is attached.

## 7. DBID-R06 — Canonical authorization read-set and response digest contract

### 7.1 Canonical authorization envelope

Every candidate authorization decision MUST bind to a canonical, versioned envelope containing at least:

- protocol and envelope version;
- stable operation ID and source audit event IDs;
- source tenant and source-local opaque resource reference;
- authenticated source actor reference and issuer/subject mapping version;
- source workload identity and tenant/database binding version;
- exact destination tenant/branch and destination workload/partner identity;
- action and canonical purpose code;
- policy version and decision timestamp/freshness evidence;
- exact data categories and field projection (including representation/version);
- resource/scope constraints and any approved transformation;
- idempotency/replay context and expiry/authorization validity boundary.

The envelope must use deterministic canonical serialization and an approved integrity mechanism. The signing/hash algorithm and key custody remain governed by the protocol and D-07; no algorithm or key is provisioned by this proposal.

### 7.2 Actual read-set and response artifact

The source service MUST record the actual query projection/read-set associated with the authorized operation. The actual read-set must be equal to or narrower than the approved projection; any widening, unexpected relationship load, extra data category or unapproved transformation fails closed and is recorded as a security event.

After response generation, the source computes a canonical digest over the exact response artifact and its integrity metadata. The digest is bound to:
- operation ID;
- source resource reference;
- destination;
- authorized projection and data categories;
- policy/protocol version;
- artifact format/version.

The source audit event records the digest and projection reference without copying patient payload into ordinary telemetry. Where the artifact contains PHI, the artifact itself is handled only under the separately approved retention, encryption, access and deletion policy. A digest is integrity evidence, not authorization and not proof that a recipient received the artifact.

### 7.3 Delivery and acknowledgement chain

Every delivery attempt and outcome references the same operation ID, projection identifier and exact artifact digest. A destination acknowledgement MUST bind to the same source, destination, operation, protocol version, projection and digest, and must be created only after the destination has durably validated and committed the exact artifact under the approved import operation.

A mismatch in operation, destination, projection, digest, protocol version or fencing generation is rejected and recorded. A delivery attempt, socket write, HTTP success or response-generation event alone is not proof of destination commit or source-verified acknowledgement.

If an artifact is generated but not verifiably delivered, record the appropriate generated/undelivered or uncertain outcome. If delivery may have occurred but acknowledgement is missing, record OUTCOME_UNCERTAIN and reconcile using authoritative evidence. Never fabricate a digest, replace the artifact silently or treat a disclosure-intent event as proof of completed delivery.

### 7.4 Required evidence and tests

- Canonicalization test vectors across supported languages/runtime versions.
- Projection mismatch tests: add a field/category after authorization and prove rejection.
- ORM/query instrumentation proves actual read-set equals the authorized projection.
- Artifact mutation test proves digest/ack validation fails.
- Destination substitution and operation-ID substitution tests fail.
- Delivery/ack replay and stale fencing tests fail safely.
- Audit tests prove no PHI or credential is placed in ordinary telemetry while the authoritative security audit retains the approved references and evidence.
- Failure injection between query, artifact generation, digest commit, network delivery, destination commit, acknowledgement and pointer synchronization produces the exact non-success/uncertain state.

## 8. Integrated acceptance gate

DBID-R01 through DBID-R06 may be considered design-resolved only after independent reviewers accept all of the following evidence:

1. Enforceable provisioning network isolation and pre-hardening direct-connect denial.
2. PostgreSQL-versioned schema, function, extension and default-privilege baseline with migration-created-object verification.
3. SQL/ORM evidence proving no patient/clinical payload is read before candidate authorization and that post-authorization projection is exact.
4. Revocation domain ownership, freshness values, deterministic in-flight race outcomes and failure-injection evidence.
5. Pool/session invalidation proof covering checked-out connections, replicas, poolers and server-side session state.
6. Canonical authorization envelope, actual read-set, response digest and delivery/ack linkage tests.
7. DBID-06 through DBID-08 separately resolved; CAN-01 independently enforceable; and all relevant D-01–D-14 governance decisions formally approved.
8. Independent database, application-security, platform/operations, privacy/legal and clinical review, plus explicit implementation authorization.

A design review or synthetic test does not establish production configuration compliance. Production evidence may be collected only under separately approved access and change controls.

## 9. Decisions deliberately left open

The following remain explicit decisions for accountable owners:
- provider-specific provisioning isolation mechanism and supported deployment profiles;
- supported PostgreSQL major versions and managed-service catalog/session capabilities;
- exact schema/object exception inventory and migration-owner identities;
- revocation authorities, freshness intervals, cache limits and emergency procedures;
- connection proxy/pooler behavior and session termination authority;
- canonical serialization, digest and signature algorithms under D-07;
- audit retention, residency, access and legal hold under D-12;
- quarantine/clinical workflow, restore and recovery controls;
- DBID-06 through DBID-08 and remaining CAN-01 topology enforcement.

No value is silently defaulted and no provider capability is assumed.

## 10. Explicit non-authorization and stop conditions

This proposal authorizes documentation and independent design review only. It does NOT authorize:
- runtime code changes or federation route refactoring;
- SQL execution, database creation, role creation, grants, revocations or ACL changes;
- network policy, cluster, workload identity, secret-manager or credential operations;
- production catalog, infrastructure, audit-store or session inspection;
- patient-data access, query, import, export, migration or backup restoration;
- partner onboarding, trust/key provisioning, federation activation, emergency access or pilot;
- deployment, release, merge, or removal of the AUD-004 release blocker.

PR #47 and this proposal remain draft/unmerged pending independent review. DBID-06 through DBID-08 remain open. CAN-01 and AUD-004 remain release blockers. D-01–D-14 formal governance decisions remain pending; D-11 project direction YES is not formal governance approval.
