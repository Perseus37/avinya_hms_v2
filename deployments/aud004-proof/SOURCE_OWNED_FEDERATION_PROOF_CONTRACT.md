# AUD-004 source-owned federation boundary — next proof contract

## Status

**Contract only; not implemented or executed.** The current application router still opens foreign tenant database sessions from destination-side request paths in both patient discovery and patient import. The source-owned disclosure service described here does not yet exist in the inspected runtime.

This document is the acceptance contract for the next implementation slice. It must not be interpreted as evidence that the source boundary is already enforced.

## Non-negotiable database-per-tenant invariant

- Keep PostgreSQL database-per-tenant. No schema-per-tenant conversion.
- A destination API/import process receives credentials only for its own tenant and the minimum control-plane metadata it needs.
- The destination process must not possess, retrieve, cache, or use credentials for any foreign tenant database.
- The source service is the only ordinary runtime path that may read its own tenant's disclosure-authorized records.
- The source service selects its own tenant database from its workload identity/configuration. A request cannot choose a database name, DSN, host, role, tenant credential, or arbitrary SQL target.
- Local cross-branch and remote federation use the same source-owned authorization and disclosure protocol.
- Provisioning, migration, backup, and restore identities remain separate privileged operational workloads; they are not available to API, import, or source-disclosure request handlers.

## Proposed trust boundary

1. Destination authenticates its own caller and establishes a destination workload identity.
2. Destination submits a narrowly scoped disclosure request to the identified source service. It supplies a signed/verified actor assertion or source-verifiable delegated identity, destination identity, purpose, requested data categories, selector commitment, request nonce and expiry.
3. Source service authenticates the destination workload and independently validates issuer, audience, signature, expiry, nonce/replay state, actor identity, actor-to-destination binding, clinician status/authorization, purpose, requested scope and source policy.
4. Source service resolves the patient selector locally. It does not accept a caller-provided source database locator.
5. Source service evaluates current patient sharing preferences and source privacy policy immediately before disclosure.
6. Source service writes a source-local disclosure audit record and commits it before returning any patient-derived data. Audit failure means no disclosure.
7. Source service returns a minimal, typed response bound to the request, source identity, authorized categories and audit correlation identifier.
8. Destination validates the response binding and records its own receipt/import audit. It cannot use the response as a general patient-creation or arbitrary source-read capability.

This is a logical protocol contract, not an endorsement of a particular transport, token format, or cryptographic profile. Those details require a separate reviewed wire contract before implementation.

## Required source API properties

- The source service has a fixed source-tenant identity and a source-tenant-only database credential.
- No caller-controlled db_name, connection URL, DSN, host, port, username, password, engine key, tenant- registry lookup can redirect source database access.
- The service accepts typed business selectors and typed purpose/scope claims only; never raw SQL or model/table names.
- The service maps authenticated destination workload identity to an active, approved federation partner.
- The service maps the asserted clinician to a source-verifiable actor identity or an explicitly governed delegated-identity record. A destination-local numeric user ID is not a source identity.
- The service independently checks clinician status, authorization, purpose, patient sharing preference, source policy, and requested data categories.
- Emergency/break-glass flows remain denied until a separate, reviewed protocol defines authority, evidence, expiry, notification, and audit requirements.
- The service must not become a confused deputy: source identity alone is insufficient; each disclosure is constrained by destination, actor, purpose, patient, categories, policy, and freshness.
- Error responses must not disclose patient existence, identifiers, or policy details to unauthorized callers.
- No disclosure is returned until the source audit transaction is durably committed.

## Synthetic integration proof matrix

These cases must execute against an isolated disposable environment and real workload identities, not only mocked functions or an in-process test client.

| ID | Scenario | Required result |
|---|---|---|
| SRC-DB-01 | Destination A connects to source tenant B DB directly | PostgreSQL denies with SQLSTATE 42501; no missing-DB or network failure accepted |
| SRC-DB-02 | Destination A attempts to retrieve B's source credential | Secret provider denies; no B secret appears in process env, mounts, logs or cache |
| SRC-DB-03 | Source B service connects to B | Allowed with source-B identity |
| SRC-DB-04 | Source B service attempts to connect to A | PostgreSQL denies with SQLSTATE 42501 |
| SRC-API-01 | Valid destination, actor, patient, purpose and category | Only authorized minimal response |
| SRC-API-02 | Missing or invalid destination workload authentication | Denied before selector lookup |
| SRC-API-03 | Invalid signature, issuer, audience, expiry or nonce | Denied before selector lookup |
| SRC-API-04 | Actor absent, inactive, revoked, unmapped or not bound to destination | Denied before patient lookup |
| SRC-API-05 | Purpose missing, unsupported or not authorized | Denied before patient lookup |
| SRC-API-06 | Requested category exceeds granted scope | Denied or safely reduced only where the reviewed contract explicitly permits; never silently broadened |
| SRC-API-07 | Source policy is isolated, sharing disabled, or patient opted out | No patient-derived response |
| SRC-API-08 | Patient selector tampered or request replayed | Denied; no alternate patient resolution |
| SRC-API-09 | Source audit insert or commit fails | No patient-derived response |
| SRC-API-10 | Source DB unavailable or source service times out | No destination-side direct DB fallback |
| SRC-API-11 | Destination submits database name/DSN/tenant override fields | Rejected; source routing remains fixed to source identity |
| SRC-API-12 | Unauthorized caller probes existing and nonexistent selectors | Externally indistinguishable denial envelope where required by the reviewed anti-enumeration contract |
| SRC-API-13 | Valid request after partner/actor revocation | Denied according to explicit effective-time semantics; no stale cache bypass |
| SRC-API-14 | Response is replayed or altered before import | Destination rejects request/response binding mismatch |
| SRC-LOCAL-01 | Same-tenant local branch federation | Uses the same source protocol and actor checks |
| SRC-LOCAL-02 | Local branch caller attempts direct source DB session | Denied by credentials and network boundary |
| SRC-AUD-01 | Successful disclosure | Source audit committed before response; correlation IDs join source and destination records |
| SRC-AUD-02 | Audit commit failure | Disclosure denied and failure is observable to operations without leaking patient data |

## Required deployment evidence

- Separate process/container identity for destination API/import and each source disclosure workload.
- Destination workload secret-provider policy proves no access to foreign source credentials.
- Source workload secret-provider policy proves it can retrieve only its own source credential.
- Network policy/firewall evidence shows destination request-serving workloads cannot reach tenant PostgreSQL endpoints except their own approved DB; source service can reach only its own DB.
- PostgreSQL catalogs prove explicit database CONNECT ACLs, no PUBLIC CONNECT, no unexpected role memberships, no owner/admin escalation, and no predefined-role shortcut.
- Process environment, mounts, command line, connection pools, logs and crash diagnostics contain no foreign credentials.
- Tests run from the actual workload containers/identities, not only a developer shell.
- Revocation tests include new connections, existing pooled sessions, process restart, secret rotation and cache invalidation.
- Evidence is synthetic-only, redacted and independently reproducible.

## Hard failure conditions

Any of the following fails the proof:

- Destination A successfully connects to tenant B's PostgreSQL database.
- Destination process can retrieve B's source credential, even if current code does not use it.
- Source service accepts a caller-controlled DB locator or can assume another tenant identity.
- A request can reach patient lookup before destination, actor, purpose and scope authorization.
- A response is returned before the source audit commit succeeds.
- Source outage triggers destination-side direct DB fallback.
- A mock-only test is presented as proof of database, network, secret-provider or container identity isolation.
- Missing database, DNS failure, bad password, timeout or absent fixture is counted as a successful authorization denial.
- Local branch federation bypasses the source protocol.

## Implementation sequencing and gates

1. Approve the wire-level identity, actor assertion, request/response binding, nonce/replay and error/anti-enumeration contract.
2. Implement a source service with a fixed tenant-bound identity and no caller-selected DB routing.
3. Implement destination-to-source transport and remove foreign tenant_engine_pool.get_engine(source_registry.db_name) calls from discovery and import request paths.
4. Add disposable PostgreSQL source/destination identities and prove DB ACL denial independently of application tests.
5. Add real container/secret-provider/network integration tests.
6. Prove source audit-before-disclosure and revocation/pool lifecycle behavior.
7. Independently review the evidence before any production identity, role-bootstrap, network, secret, deployment or runtime rollout.

No production rollout, partner onboarding, trust provisioning, federation activation, merge or release is implied by this contract.


## Wire-profile reconciliation gate

PR #30 already contains a proposed discovery challenge and clinician-assertion design: source-canonicalized selectors; issuer-scoped clinician subject; actor classification; challenge and protocol binding; destination node and branch; action; purpose; source audience; requested scope; issue/not-before/expiry; unique token identifier; source-side trust and claim verification; and one-operation challenge state. Reuse and reconcile that proposal rather than inventing a parallel assertion protocol.

PR #30 explicitly remains design-only and does not freeze a cryptographic profile or production lifetime. The following must be decided in one reviewed wire-profile artifact before source-service implementation:

1. **Envelope and serialization:** exact media type, canonical serialization, protected header, claim names/types, duplicate-claim handling, maximum sizes, and protocol-version negotiation.
2. **Cryptographic profile:** approved signature algorithm(s), key type/size, key identifier rules, permitted critical headers, canonical signing input, algorithm-confusion rejection, and test vectors. Reject unsigned tokens, symmetric shared signing secrets across tenants, and caller-selected algorithms.
3. **Issuer trust:** issuer registry ownership, trust-anchor/key publication and pinning, key rotation overlap, compromise response, issuer disablement, and unknown-key behavior.
4. **Audience and identity:** exact source service audience; destination workload identity binding; issuer-scoped clinician subject; source-side clinician mapping and current status; no trust in destination-supplied role strings or local numeric user IDs.
5. **Operation binding:** challenge ID, operation ID, protocol version, source identity, destination node and branch, action, versioned purpose, selector commitment, exact requested categories, and request/response correlation.
6. **Freshness and replay:** clock-skew allowance, issue/not-before/expiry semantics, unique token identifier namespace, durable one-time consumption, atomic concurrency behavior, lost-response retry rules, and effective-time revocation.
7. **Privacy:** source-only canonicalization and keyed commitment; no low-entropy plain selector hash; uniform denial envelope; rate limits and enumeration monitoring.
8. **Response integrity:** exact response schema, source identity, operation/challenge binding, authorized category list, audit correlation, response signature or authenticated transport binding, destination validation, and replay rejection.
9. **Operational controls:** key custody, rotation evidence, revocation propagation, pool/session invalidation, clock synchronization, audit retention, incident response, and synthetic conformance vectors.

The wire profile must resolve, not silently waive, the still-open independent-review findings from PR #67/#69: R74 revocation proof/effective time, R76 wire profile completeness, and R77 polling/redemption binding and anti-enumeration. A document that merely lists fields is not sufficient; it must provide exact normative validation rules, negative test vectors, and accountable approval.

**No algorithm, token lifetime, trust-anchor format, key-distribution mechanism, or production issuer is selected by this proof contract.** Do not implement a speculative choice in application code.