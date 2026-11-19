# AUD-004 ADV-03 / ADV-04 Resolution Proposal

**Status:** PROPOSED SECURITY DESIGN — GOVERNANCE AND INDEPENDENT REVIEW REQUIRED  
**Parent:** PR #34, ADV-01/ADV-02 resolution proposal  
**Scope:** Challenge bootstrap abuse/denial-of-service controls (ADV-03) and precise source audit, disclosure, response-artifact and network-delivery boundaries (ADV-04).  
**Non-goals:** This document does not approve numeric rate limits, retention periods, cryptographic algorithms, storage topology, response replay policy, operational staffing, runtime implementation, migrations, pilot, production access, merge, deployment or release.

## 1. Executive proposal

ADV-03 and ADV-04 are related because challenge creation and authorization/disclosure events consume durable resources. They must nevertheless remain separate controls:

- **ADV-03** limits unauthenticated or weakly authenticated work before challenge allocation, signing, patient lookup or other expensive operations.
- **ADV-04** defines exactly which durable source-side event must exist before each protected action, and what can and cannot be claimed when a network delivery outcome is uncertain.

Recommended invariants:

1. Authenticate the registered node and validate its trust relationship before allocating durable challenge state.
2. Enforce layered, distributed budgets before expensive operations; failure of the authoritative abuse-control dependency must not silently disable limits.
3. Challenge issuance must not depend on selector match state or reveal source topology.
4. Search authorization, candidate authorization, disclosure intent and response artifact are distinct durable events.
5. A source database transaction cannot atomically commit with remote network delivery. The protocol must represent this uncertainty explicitly.
6. A retry may resend only an already committed, still-authorized immutable response artifact under an approved replay policy. It must not silently perform a new patient read.
7. If exact artifact replay is not approved or the artifact cannot be safely retained, retry requires fresh source authorization and a new source read is separately audited.

## 2. ADV-03 — challenge bootstrap threat model

### 2.1 Protected resources and abuse paths

Challenge endpoints may consume:
- database rows, indexes, locks and transaction capacity;
- cryptographic signing/verification capacity;
- issuer/key/status registry lookups;
- audit storage and queue capacity;
- source endpoint connection pools and routing capacity;
- cleanup/expiry worker capacity.

Threats include:
- challenge-row exhaustion using repeated requests without completing assertions;
- distributed abuse through multiple nodes, issuer aliases, destination branches or source endpoints;
- replayed or duplicate challenge requests producing unbounded state;
- expensive signature/key/status operations triggered by unauthenticated callers;
- challenge issuance used as a patient-existence, partner-topology or policy oracle;
- attacker-induced queue backlog delaying legitimate clinical workflows;
- cleanup races that remove active replay protections or retain expired challenge secrets indefinitely;
- rate-limit bypass during Redis/cache/central limiter outage or by changing request identifiers.

### 2.2 Ordered request pipeline

The source should process challenge requests in this order:

1. **Transport limits:** enforce connection, request-body, header and timeout limits at the edge before application parsing.
2. **Node authentication:** validate the presented node credential using constant-time credential comparison and trusted node state. Do not allocate challenge state for invalid credentials.
3. **Relationship validation:** resolve issuer, source audience, destination and node relationship from trusted server-side records. Reject mismatched, suspended or revoked relationships.
4. **Coarse abuse controls:** enforce edge/IP/network and node budgets before expensive registry, signature or persistence work. IP limits are defense-in-depth, never the sole identity key.
5. **Request syntax validation:** validate protocol version, action, purpose, selector type, field lengths and canonicalization profile without executing patient-specific lookup.
6. **Issuer/actor preconditions:** where actor verification is required at this stage, perform bounded trust/status checks. Do not perform patient-specific matching.
7. **Challenge idempotency and allocation:** atomically claim the idempotency key and persist bounded challenge state only after earlier gates pass.
8. **Challenge response:** return a minimal, non-identifying challenge response. Do not reveal patient match state, candidate count, source branch list or policy detail.
9. **Post-allocation accounting:** record issuance outcome and update counters using bounded, non-blocking mechanisms that cannot turn an audit outage into permissive operation.

The exact ordering of source-issued challenge versus destination-signed assertion is constrained by the selected challenge protocol. The invariant is that node authentication and coarse abuse controls precede challenge allocation, and no patient-specific selector query occurs during challenge bootstrap.

### 2.3 Layered budgets and aggregation keys

Use multiple independent budget dimensions. No single caller-controlled value may reset or partition all budgets.

Proposed dimensions:
- edge/network source (IP or trusted network identity);
- authenticated node ID;
- issuer ID and issuer branch;
- destination tenant and destination branch;
- source tenant/branch;
- action and protocol version;
- authenticated actor subject, once independently verified;
- challenge issuance and completion ratio;
- concurrent active challenges;
- outstanding challenge storage by expiry bucket;
- global service capacity and signing/verification queue depth.

The authoritative budget must aggregate across node aliases and source instances. Where an actor subject is not yet verified, pre-auth budgets must use authenticated node/issuer and network dimensions. After actor verification, actor-level budgets apply as an additional control; they do not replace earlier limits.

**Do not use** raw patient selectors, email addresses, caller-supplied actor IDs, request IDs or arbitrary headers as the sole rate-limit key.

Numeric thresholds, windows, burst sizes, concurrency limits and escalation behavior are deliberately unresolved. They must be selected from a documented threat model, measured service capacity, abuse simulations and clinical availability requirements, then recorded in the governance decision register.

### 2.4 Challenge idempotency and bounded storage

A challenge request must have a server-validated idempotency contract:

- A repeated request with the same authenticated principal, protocol context and identical canonical request may return the same challenge response while the challenge is valid, or a bounded equivalent response.
- Reusing the idempotency key with a different body, destination, action, purpose, selector binding or protocol version must be rejected and audited as a conflict.
- The idempotency key must be scoped to authenticated server-side identity and protocol context; caller-provided keys are not trusted globally.
- Duplicate requests must not create extra challenge rows, extra signing work or extra budget.
- Challenge state must have explicit maximum lifetime, maximum outstanding count and bounded payload size.
- Persist only required claims/commitments. Do not store raw selector values, full assertions or reusable secrets in challenge rows unless a separately approved design requires it.
- Expiry cleanup must be bounded and indexed. Cleanup may not delete replay-prevention or audit evidence before the approved retention obligation is met.
- Challenge state transitions and one-time use must be atomic under the selected database's concurrency semantics; a read-then-write check without a unique constraint/lock is insufficient.
- The challenge response must be recipient/audience bound and unusable by another node, issuer, destination or action.

If a challenge expires, the caller obtains a new challenge and completes a new authorization flow. An expired challenge never authorizes a new source read.

### 2.5 Dependency failure and overload policy

| Failure | Required behavior |
|---|---|
| Node credential/trust store unavailable | Deny challenge allocation; return bounded service-unavailable response |
| Distributed limiter unavailable | Fail closed for challenge allocation unless a separately approved, bounded emergency limiter is proven safe; alert |
| Challenge/replay persistence unavailable | Deny; no process-local fallback as authoritative state |
| Required audit persistence unavailable | Deny any operation whose required audit event cannot be committed |
| Signing/key service unavailable | Deny; do not downgrade algorithm or accept unsigned challenge |
| Clinician status or issuer trust unavailable | Deny protected operation; do not use stale-positive unknown status |
| Queue/storage capacity threshold exceeded | Shed load predictably before allocation; protect reserved capacity for approved priority classes |
| Cleanup worker delayed | Enforce expiry at read/claim time; do not treat stale rows as valid |
| Source topology/routing dependency unavailable | Return generic unavailable outcome; do not expose candidate source list |

No fail-open limiter, node-only fallback, stale-unknown trust acceptance or emergency federation bypass is permitted by this proposal. Any availability exception requires separate approval and threat-model evidence.

### 2.6 Monitoring and operational response

Operational metrics should include:
- challenge requests by outcome and trusted principal dimensions;
- challenge allocation, completion, expiry and replay rates;
- active/outstanding challenge counts and oldest age;
- limiter denials and dependency health;
- challenge-storage growth and cleanup lag;
- signing queue depth, latency and failures;
- suspicious fan-out, repeated idempotency conflicts and low completion ratios;
- source availability and load-shedding events.

Metrics and ordinary logs must not contain raw selectors, challenge secrets, assertions, resource handles or unnecessary PHI. Security alerts should include safe correlation IDs and trusted principal references.

Runbooks must define alert ownership, escalation, rate-limit adjustment approval, node suspension, issuer suspension, evidence preservation and recovery. Operators must not be able to waive actor verification or manufacture a challenge completion. Emergency operational actions require dual control and immutable audit; emergency federation remains disabled.

## 3. ADV-04 — durable audit and disclosure boundary

### 3.1 Why one transaction cannot cover disclosure

The source can atomically commit source database records within its transaction boundary. It cannot atomically commit a database transaction and prove that remote bytes were received, processed or persisted by the destination.

Therefore, these facts must remain distinct:
- source authorized an action;
- source resolved a selector;
- source authorized a candidate;
- source committed intent to disclose;
- source committed an immutable response artifact;
- source attempted network delivery;
- destination acknowledged receipt;
- destination validated the response;
- destination committed an import.

No event may be inferred from another. In particular:
- a committed audit row does not prove network delivery;
- a successful socket write does not prove destination receipt;
- an HTTP response attempt does not prove destination persistence;
- a destination acknowledgement does not prove pointer synchronization;
- a transfer log with a node ID does not establish clinician attribution.

### 3.2 Proposed source-side event lifecycle

| Event | Meaning | Must be durable before | Required outcome if persistence fails |
|---|---|---|---|
| `NODE_AUTHENTICATED` | Registered node and relationship validated | Challenge allocation | Deny allocation |
| `CHALLENGE_ISSUED` | Source challenge allocated and bound | Challenge returned | Do not return usable challenge |
| `ACTOR_VERIFIED` | Assertion, mapping and current status validated | Search authorization | Deny |
| `SEARCH_AUTHORIZATION_DECIDED` | Bounded search allowed/denied | Selector lookup on allow | No lookup on missing/failed audit |
| `SELECTOR_RESOLUTION_ATTEMPTED` | Source-internal query attempted | Operational result accounting | No patient result disclosure if required audit cannot be recorded |
| `CANDIDATE_AUTHORIZATION_DECIDED` | Candidate-specific policy outcome | Candidate details/serialization | No candidate disclosure |
| `DISCLOSURE_INTENT_COMMITTED` | Exact response categories/recipient/action approved for disclosure | Response artifact creation or payload release | No payload release |
| `RESPONSE_ARTIFACT_COMMITTED` | Immutable, recipient-bound payload or manifest stored | Network delivery, if artifact replay model selected | No network release |
| `DELIVERY_ATTEMPTED` | Source attempted to send artifact | Delivery attempt | Record outcome; never claim receipt |
| `DELIVERY_ACKNOWLEDGED` | Trusted destination acknowledgement verified | Source transfer completion claim | Remain indeterminate if absent/invalid |
| `OUTCOME_UNCERTAIN` | Source cannot establish delivery outcome | Any later reconciliation | No blind new disclosure |
| `DESTINATION_COMMIT_CONFIRMED` | Verified acknowledgement proves destination durable commit | Source-side completion state | Do not infer from transport success |

Denied decisions must also be auditable, with minimized and access-controlled details. A denial audit must not itself disclose patient existence to the requester.

### 3.3 Commit boundary A — search authorization before lookup

For ADV-01, the source must durably commit the search authorization decision before executing the patient-specific selector query.

The authorization record should bind:
- source decision ID and policy version;
- verified issuer, subject, actor class/assurance and status versions;
- source audience and exact destination;
- action, purpose and protocol version;
- selector type and canonicalization profile;
- protected selector commitment (not raw selector in general telemetry);
- budget decision and request correlation ID;
- decision timestamp and expiry.

If the required source audit/authorization transaction fails, no selector query occurs. The source must not execute the query and later attempt to reconstruct a success audit.

### 3.4 Commit boundary B — candidate authorization before serialization

After internal resolution, the source evaluates candidate-specific authorization against source-owned patient/resource identity and current policy.

Before any candidate-specific field is serialized or exposed:
1. Candidate authorization is durably recorded.
2. Minimum necessary data categories and destination are fixed.
3. The response schema is selected from an approved version.
4. The exact response payload/manifest is constructed only from authorized source data.
5. Any disclosure-intent record is committed.

If candidate authorization or its required audit fails, no patient-specific payload, handle, source pointer or distinguishable candidate outcome is returned.

### 3.5 Commit boundary C — response artifact strategy

Two strategies are possible. They are alternatives and must not be mixed implicitly.

**Strategy A — immutable response artifact with bounded exact replay**

- Persist the exact authorized response bytes or a canonical immutable payload representation, digest, schema version, recipient binding, actor/action/purpose, source decision IDs, authorization/policy versions, creation/expiry times and replay state.
- Encrypt and access-control stored PHI according to the approved data classification and retention policy.
- Return only the artifact authorized for that exact recipient and operation.
- A retry can retrieve/retransmit the same bytes only after rechecking current recipient trust, artifact expiry, actor/issuer revocation rules and the approved replay policy.
- The retry must not re-query patient tables or broaden data categories.
- The artifact must be immutable; changed body, destination, actor, purpose, schema or digest is a new request and requires fresh authorization.
- Store artifact identifiers as opaque, high-entropy values; hash lookup tokens where feasible. Never put them in URLs, referrers or ordinary logs.
- Define artifact deletion, legal hold, backup, encryption-key rotation and audit retention together; do not retain PHI indefinitely merely to simplify retries.

**Strategy B — no retained response artifact; fresh authorization for retry**

- Persist source authorization/disclosure intent and a minimal digest/correlation record, but do not retain a replayable PHI payload.
- If delivery is uncertain, do not claim success and do not automatically re-read or resend.
- A retry requires a fresh challenge/assertion, current clinician/issuer/policy checks, new source authorization and a newly audited source read.
- The source must distinguish the new disclosure from the prior uncertain attempt.
- This strategy reduces retained PHI but can produce a second authorized disclosure. That consequence must be included in privacy policy and user-visible workflow design.

**Decision:** Which strategy is permitted for each action/data category is unresolved. Discovery summaries, allergy data and full import payloads may require different retention and replay rules. A generic global retry policy is not acceptable.

### 3.6 Commit boundary D — network delivery and acknowledgement

Once a response artifact is committed (Strategy A) or a fresh disclosure is authorized (Strategy B), the source attempts delivery.

- Record `DELIVERY_ATTEMPTED` with a correlation ID and safe transport metadata.
- Do not log payloads, assertions, challenge secrets, selectors or bearer handles.
- A transport write success is not a destination receipt.
- A client disconnect, timeout, proxy reset or missing acknowledgement produces `OUTCOME_UNCERTAIN`.
- A destination acknowledgement must be authenticated, bound to source, destination, artifact/manifest digest, operation, protocol version and applicable fencing generation.
- Acknowledgement is accepted only after the destination has performed the specific durable action claimed by that acknowledgement.
- Source completion is recorded only after validating the acknowledgement and committing the corresponding source event.
- If the acknowledgement is lost, use the approved artifact/reconciliation strategy; do not blindly repeat the source read or destination import.

The precise acknowledgement signing and trust model must align with ADV-10 and the destination import recovery design. This proposal does not authorize a key or select an algorithm.

### 3.7 Cross-database and cross-service failure matrix

| Crash/failure point | Durable state that may exist | Safe recovery | Forbidden inference/action |
|---|---|---|---|
| Before search authorization commit | No authorized search | Start new request after dependencies recover | Do not query selector |
| After search authorization commit, before query | Search grant/audit exists | Resume only if protocol permits the same request and grant is still valid; otherwise obtain fresh authorization | Do not assume query ran |
| During selector query | Search attempt may be recorded | Mark query outcome uncertain; repeat only under explicit same-request idempotency policy and valid budget | Do not expose partial candidates |
| After candidate decision, before disclosure intent | Candidate decision exists | Re-evaluate freshness/policy before a new disclosure | Do not treat candidate allow as reusable indefinitely |
| After disclosure intent, before artifact commit | Intent exists, no artifact | Mark incomplete/uncertain; require fresh authorization unless a transaction proves no payload was committed | Do not claim payload was delivered |
| After artifact commit, before network send | Immutable artifact exists | Recheck approved replay eligibility and deliver exact artifact | Do not reconstruct payload from live patient tables |
| During/after network send, no acknowledgement | Artifact may have been received | Record `OUTCOME_UNCERTAIN`; exact replay only under approved Strategy A rules, or fresh authorization under Strategy B | Do not claim receipt or blindly re-read |
| Destination received, before destination durable commit | Destination receipt may be transient | Destination reports no commit; reconcile by artifact/operation ID | Do not claim import complete |
| Destination commit, acknowledgement not sent/lost | Destination durable commit may exist | Destination returns signed/current status for same operation; source verifies digest and generation | Do not repeat import as a new operation |
| Acknowledgement received, source completion audit fails | Destination may be committed; source uncertain | Preserve indeterminate source state and retry acknowledgement reconciliation | Do not claim source completion without durable record |
| Source completion committed | Full protocol outcome recorded | Return status for same operation | Do not create another disclosure on status polling |

### 3.8 State model

Proposed source transfer states:

- `REQUEST_AUTHENTICATED`
- `CHALLENGE_ISSUED`
- `ACTOR_VERIFIED`
- `SEARCH_AUTHORIZED`
- `SEARCH_ATTEMPTED`
- `CANDIDATE_AUTHORIZED` / `CANDIDATE_DENIED` / `NO_MATCH` / `AMBIGUOUS`
- `DISCLOSURE_INTENT_COMMITTED`
- `RESPONSE_ARTIFACT_COMMITTED` (Strategy A only)
- `DELIVERY_ATTEMPTED`
- `OUTCOME_UNCERTAIN`
- `DELIVERY_ACKNOWLEDGED`
- `DESTINATION_COMMIT_CONFIRMED`
- `DENIED`, `FAILED_RETRYABLE`, `EXPIRED`, `RECONCILIATION_REQUIRED`

State transitions must be monotonic and atomic. Each transition records actor/system principal, correlation ID, source decision, policy version, timestamp and prior/new state. Terminal states cannot be reopened by a stale worker. Where concurrent workers are possible, use compare-and-swap or equivalent database-enforced transition predicates and a monotonic generation/fencing token. This proposal does not replace PRs #23/#24 import fencing requirements.

Do not make `NO_MATCH`, `CANDIDATE_DENIED` or `AMBIGUOUS` distinguishable to unauthorized callers. Internal state labels are restricted operational data.

## 4. Audit integrity, minimization and separation

### 4.1 Separate audit domains

Maintain distinct logical domains (physical separation may be selected by architecture):

1. **Patient-linked source security audit:** protected actor/resource/action decisions, restricted to authorized auditors and governed retention.
2. **Operational telemetry:** counts, latency, queue depth, failure class and safe correlation IDs; no raw selectors, PHI or credentials.
3. **Destination import audit:** local actor, provenance, validation, commit and pointer-sync lifecycle.
4. **Control-plane trust audit:** node, issuer, key and partner relationship administration.

Do not use ordinary application logs as the authoritative audit record. Do not treat caller-supplied narrative or assertion claims as a source-generated success event.

### 4.2 Event integrity and correction

- Events are generated by the authority that owns the decision (source for source authorization/disclosure; destination for destination commit).
- Each event has a versioned schema, stable event ID, trusted server timestamp, correlation ID, tenant/branch context, source decision reference and protocol version.
- Preserve append-only semantics or independently verifiable tamper evidence. Corrections are compensating events, not mutation/deletion of history, subject to legal retention rules.
- Define clock synchronization, drift monitoring and timestamp trust.
- Restrict event read/export access by role and purpose; record audit-reader access.
- Define retention, legal hold, deletion, backup and restore verification for each event class.
- PHI and selector minimization must be documented; hashes of low-entropy identifiers are still potentially linkable and must be treated as sensitive.
- Never record raw assertions, challenge secrets, signing private material, API keys, resource handles or complete payloads in ordinary logs.
- Security incident exports must be controlled, encrypted and audited.

### 4.3 Audit outage behavior

Required audit persistence must be synchronous with the protected authorization boundary or implemented through a transactionally reliable mechanism that guarantees no protected operation proceeds before the durable authorization event exists.

A best-effort asynchronous log after disclosure is insufficient.

If the required audit store is unavailable:
- no challenge is allocated if challenge issuance audit is required and cannot commit;
- no selector query runs if search authorization audit cannot commit;
- no candidate data is serialized if candidate authorization/disclosure intent cannot commit;
- no response is sent if the chosen response-artifact strategy requires a durable artifact and it cannot commit;
- no completion is claimed if acknowledgement/completion audit cannot commit.

A separate, pre-approved security event buffer may be used only if it is itself durable, bounded, access-controlled, tamper-evident and proven to preserve ordering/atomicity. An in-memory queue or ordinary application log is not such a buffer.

## 5. Operational controls and observability

Proposed operational views:
- counts and age by transfer state;
- challenge issuance/expiry/completion and limiter decisions;
- outstanding artifact counts and expiry age (Strategy A);
- delivery attempts, acknowledgements and uncertain outcomes;
- audit commit failures and queue/storage pressure;
- retry and reconciliation backlog;
- stale workers and rejected fencing generations;
- issuer/key/clinician revocation events affecting in-flight operations.

Operational tooling must not expose patient selectors, raw assertions, payloads, handles or unnecessary PHI. Patient-linked reconciliation requires authorized access and dual control where defined by governance.

Operators may:
- inspect safe state and correlation metadata;
- request a fresh status/reconciliation from the destination;
- retry an exact committed artifact only when policy explicitly permits it;
- trigger a governed incident workflow.

Operators may not:
- mark a disclosure or destination commit complete without authority-owned durable evidence;
- synthesize clinician identity or authorization;
- replay expired authorization for a new source read;
- bypass rate limits, audit, replay controls or fencing;
- delete uncertain transfer records to clear backlog.

## 6. Required acceptance tests

### 6.1 ADV-03 challenge abuse and resilience

- Invalid/missing/revoked node credentials allocate no challenge rows and do not invoke expensive signing operations.
- Node/issuer/destination relationship mismatch is rejected before allocation.
- Distributed budgets aggregate across multiple source instances and node aliases.
- A caller cannot reset budgets by changing request ID, idempotency key, header, branch field or connection.
- Concurrent identical requests produce bounded idempotent behavior and no duplicate challenge state.
- Same idempotency key with changed body/destination/action/purpose/selector/protocol is rejected.
- Outstanding challenge, storage, signing queue and cleanup bounds are enforced under load.
- Expired challenge cannot be used even if cleanup is delayed.
- Cleanup cannot remove active replay protection or required audit evidence.
- Redis/limiter outage, challenge DB outage, audit outage and key-service outage fail closed with safe bounded responses.
- Challenge response shape does not reveal selector match, patient existence, source branch topology or privacy policy.
- Low completion ratios, sequential requests and multi-node fan-out trigger the approved abuse controls.
- Rate-limit recovery does not automatically release an unbounded backlog of queued expensive operations.
- No emergency or node-only fallback is reachable when dependencies fail.

### 6.2 ADV-04 audit, disclosure and delivery

- Search authorization audit commits before selector query; injected audit failure proves no query executed.
- Candidate authorization and disclosure intent commit before candidate data serialization/release.
- A candidate denial or audit failure returns no patient-specific data or existence signal.
- Artifact persistence failure prevents network send when Strategy A is selected.
- Exact artifact replay returns identical bytes/digest and never re-queries patient data.
- Changed actor, destination, action, purpose, scope, schema or digest cannot reuse an artifact.
- Strategy B retry requires fresh challenge/assertion and new source authorization; it creates a distinct audited disclosure.
- Crash injection at every matrix boundary produces the specified state and no false completion.
- Network write success without destination acknowledgement remains unconfirmed.
- Lost acknowledgement after destination commit is reconciled by the same operation and does not create a duplicate import.
- Forged, stale, wrong-recipient, wrong-digest, wrong-generation and revoked-key acknowledgements are rejected.
- Audit-store outage at every required boundary prevents the protected operation or completion claim.
- Stale worker cannot advance a state or send a payload after a newer generation has taken ownership.
- Ordinary logs/telemetry contain no raw PHI, selectors, challenge secrets, assertions, keys or bearer handles.
- Source, destination and control-plane audit records remain attributable to their owning authority and do not overstate each other's outcomes.

### 6.3 Database and fault-injection requirements

Use PostgreSQL integration tests with independent sessions/connections and realistic transaction isolation. SQLite or single-session unit tests are insufficient for concurrency/replay guarantees.

Inject process termination, database disconnect, timeout, duplicate delivery, delayed acknowledgement, limiter outage, audit outage, key-service outage, cleanup race and worker lease expiry at every transition. Preserve evidence of the expected state, durable events and permitted retry actor for each case.

## 7. Governance decisions still pending

| Decision | Proposed direction for review | Accountable approval | Status |
|---|---|---|---|
| Challenge endpoint exposure | Node authentication and coarse abuse limits before allocation | Security + platform operations | Pending |
| Rate-limit dimensions | Layered edge/node/issuer/destination/source/actor/global budgets | Security + platform operations + privacy | Pending |
| Numeric thresholds and bursts | Derive from load/abuse testing and clinical availability requirements | Security + SRE/operations + clinical owner | Pending |
| Challenge TTL and outstanding cap | Short-lived, bounded, source-owned state; exact values tested | Security + privacy + operations | Pending |
| Idempotency behavior | Same canonical request returns bounded same challenge; changed request conflicts | Security architecture | Pending |
| Limiter outage policy | Fail closed unless separately approved bounded emergency design | Security + SRE/operations | Pending |
| Challenge/audit retention | Separate challenge cleanup from replay/audit evidence retention | Privacy/legal + audit owner | Pending |
| Response replay strategy | Select Strategy A or B per action/data category; no implicit hybrid | Clinical governance + privacy/legal + security | Pending |
| Artifact retention/encryption | If Strategy A, classify PHI, encryption, access, expiry, backup and legal hold | Privacy/legal + security + data owner | Pending |
| Delivery acknowledgement | Destination-authenticated, operation/digest/recipient/fencing bound | Security architecture + destination owner | Pending |
| Audit schema and integrity | Versioned source-generated events, tamper evidence, access and correction model | Audit owner + privacy/legal + security | Pending |
| Audit outage policy | No protected operation without required durable event | Security + clinical governance + operations | Pending |
| Uncertain outcome workflow | Defined user messaging, reconciliation owner and retry authority | Product + clinical operations + security | Pending |

Record approvals in the canonical D-01–D-14 register with approver name, organization, role, date, governance reference, evidence, affected stages, residual risk, compensating controls, expiry and disable conditions. This proposal does not close a governance decision by implication.

## 8. Implementation gates

Runtime implementation must not begin until:

1. ADV-01/ADV-02 design is independently reviewed and its governance decisions are recorded.
2. Challenge endpoint threat model, layered budgets, numeric limits and overload policy are approved.
3. Distributed limiter and persistence failure semantics are specified and operationally tested.
4. Challenge idempotency, expiry, replay and cleanup transaction semantics are specified for PostgreSQL.
5. Strategy A versus Strategy B is selected per action/data category with privacy/legal and clinical approval.
6. Source audit event schema, transaction boundaries, retention and outage behavior are approved.
7. Destination acknowledgement and fencing model is reconciled with ADV-10 and PRs #23/#24.
8. Revocation freshness and response replay semantics are reconciled with ADV-05.
9. Failure-state matrix is reconciled with all three protocol lifecycles and operator dual-control rules.
10. PostgreSQL concurrency, load, fault-injection and recovery acceptance plans are approved.
11. Formal governance approval and implementation authorization are recorded.

## 9. Relationship to existing work

- PR #19 contains AUD-001–003 runtime remediation but does not establish these challenge or disclosure guarantees.
- PRs #23/#24 define import idempotency/recovery and fencing requirements; destination commit and acknowledgement must remain separate from source delivery.
- PR #32 separates source authorization, discovery integrity and destination import recovery.
- PR #33 identifies ADV-03 and ADV-04 as high-risk unresolved findings.
- PR #34 proposes ADV-01/ADV-02 controls; this document builds on those proposals without declaring them approved or implemented.

## 10. Disposition

This document proposes resolution controls for ADV-03 and ADV-04. It does not prove that either finding is closed. Closure requires independent security/privacy/clinical review, approved governance decisions, traceable PostgreSQL acceptance evidence, and later verified runtime behavior.

**AUD-004 remains release-blocking.** No runtime code, migrations, configuration, rate-limit changes, keys, trust entries, partner onboarding, pilot, production patient-data access, merge, deployment, release or emergency federation is authorized by this document.
