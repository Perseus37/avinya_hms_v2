# AUD-004 ADV-11/ADV-12 Audit Governance and Lifecycle Recovery Proposal

**Status:** PROPOSED SECURITY DESIGN — GOVERNANCE AND INDEPENDENT REVIEW REQUIRED  
**Parent:** PR #38 (ADV-09/ADV-10 selector-index and acknowledgement proposal)  
**Scope:** Address ADV-11 audit privacy/integrity/governance and ADV-12 end-to-end failure, recovery and retry authority across source authorization/disclosure, discovery integrity and destination import.  
**Non-goals:** No approval of retention periods, legal basis, audit-reader roles, cryptographic algorithms, storage providers, runtime implementation, migrations, production access, merge, deployment or release.

## 1. Executive result

- **ADV-11 — Audit integrity and privacy:** security audit must be attributable to the authority that made the decision, tamper-evident, versioned, privacy-minimized and access-controlled. It must not become a second patient index, leak credentials/PHI through telemetry, or accept caller-authored claims as proof of success.
- **ADV-12 — Failure and recovery:** every durable state transition must define what is known, what may be repeated, which authority is required, what evidence is mandatory, and when the operation must stop for reconciliation. A timeout or missing response is not proof that an operation did not commit.

The proposal establishes a common event model and lifecycle-by-lifecycle recovery matrix. It does not collapse source authorization, response delivery, destination commit, acknowledgement verification or pointer synchronization into one success flag.

**AUD-004 remains release-blocking.** Design text is not runtime enforcement or formal governance approval.

## 2. ADV-11 — Audit event privacy, integrity and governance

### 2.1 Security objectives and threat model

Audit evidence must support accountability, investigation, privacy oversight and reconciliation without exposing more patient or clinician information than necessary.

Threats include:
- Raw selectors, patient identifiers, clinical payloads, assertions, handles, API keys or signing material copied into logs/traces/metrics.
- Audit records used as a searchable shadow patient index or cross-tenant correlation database.
- Caller-supplied actor IDs, purpose strings, success flags, timestamps or narrative accepted as authoritative facts.
- Privileged administrators editing, deleting, reordering or suppressing audit records.
- A database owner or compromised application changing both business data and ordinary audit rows.
- Unsynchronized clocks creating misleading event order or fabricated freshness.
- Audit reader roles enabling broad curiosity access to patient access histories.
- Unbounded retention, backups or exports retaining sensitive data beyond approved purpose.
- Audit outage leading to fail-open protected reads, disclosure, imports or state transitions.
- Untrusted free-text or exception content injecting misleading narratives into audit reports.
- Correction workflows overwriting original evidence rather than preserving traceable amendments.

### 2.2 Separate evidence domains

Maintain logically and access-control separated evidence domains. Physical separation must be selected from a threat model, not assumed.

| Evidence domain | Purpose | Typical content | Must not become |
|---|---|---|---|
| Source security audit | Prove source identity, policy decisions, patient access and disclosure intent | Source-generated event, trusted actor/issuer references, action/purpose, policy version, outcome, restricted resource reference | General telemetry or caller-authored narrative |
| Destination import audit | Prove local import operation, provenance, commit and recovery | Destination operation ID, provenance digest/reference, fencing generation, commit/ack states | Proof of source authorization |
| Control-plane trust audit | Prove node/issuer/key/partner trust lifecycle | Trust record ID, approver references, key ID/status transition, dual-control evidence | Patient-level clinical record |
| Operational telemetry | Availability, latency, capacity and diagnostics | Safe correlation ID, component, duration, dependency outcome, bounded error category | PHI, raw selectors, assertions, handles or stable cross-tenant tokens |
| Clinical record/provenance | Clinical content and lineage | Patient data, source provenance and approved clinical context | General-purpose security log |

Use distinct retention, access, export, deletion, backup and legal-hold policies for each domain. Cross-domain correlation uses narrowly scoped opaque references and approved access workflows.

### 2.3 Authoritative event authorship

Only the authority responsible for a decision may emit its authoritative event:
- Source tenant emits source actor verification, search authorization, candidate authorization, disclosure intent, source read and delivery-attempt events.
- Destination tenant emits import claim, provenance commit, destination acknowledgement and pointer-sync state.
- Control plane emits node/issuer/key/partner trust lifecycle events.
- Operators emit attributed administrative-action events, never synthetic source authorization or destination commit facts.

Caller-provided values are inputs, not evidence. The source derives actor, issuer, destination, action, purpose, policy version and outcome from verified server-side context. Destination derives commit state and provenance from its own transaction. The coordinator cannot author a source success event or destination commit acknowledgement.

Every event schema distinguishes observed facts, caller/request claims, authority decisions, inferred/uncertain outcomes and administrative annotations. Do not present a request claim as an observed fact. Free-text annotations are clearly labelled untrusted commentary, sanitized for display and never used as policy input.

### 2.4 Versioned event envelope

Proposed minimum event envelope (illustrative, not a final wire schema):
- Immutable event ID, schema version and event type.
- Authority/service identity and tenant/branch scope.
- Event sequence or aggregate version where supported.
- Operation/correlation reference with narrow scope.
- Source/destination operation references where relevant.
- Server-derived actor/issuer references and assurance/status version references when applicable.
- Canonical action, purpose, resource class and data-category/scope identifiers.
- Policy/registry/protocol version references.
- Decision/outcome category and reason code from a controlled vocabulary.
- Trusted event time plus clock-quality/uncertainty metadata.
- Previous-event/hash-chain or equivalent integrity reference where selected.
- Payload classification and retention class.
- Signing/integrity key ID and verification metadata where selected.

Do not place raw selectors, patient name, DOB, phone, ABHA, MRN, clinical narrative, payload bytes, bearer handles, assertions, credentials, private keys, database schema names or raw exception traces in ordinary audit metadata. A restricted patient-linked audit may require a protected resource reference; define that separately from telemetry and tightly govern its resolution.

Do not over-collect actor demographics or professional credential documents in every event. Store references to authoritative mapping/evidence records and their version/status.

### 2.5 Integrity, ordering and trusted time

Evaluate:
- Append-only or write-once storage characteristics for finalized events.
- Hash chaining, signed batches, independent checkpoints or equivalent tamper evidence.
- Independent security monitoring of audit pipeline health and integrity verification.
- Separation of duties between application operators, DB administrators, key custodians and auditors.
- Protected key custody and rotation/revocation procedures.
- Immutable export/checkpoint evidence to an independently controlled domain.
- Trusted time synchronization, drift monitoring and explicit clock-uncertainty handling.
- Sequence numbers/aggregate versions for ordering within an operation; wall-clock timestamps alone are not causal proof.
- Detection of missing sequence ranges, duplicate IDs, reordered events and unauthorized corrections.
- Restore drills proving integrity verification survives backup/restore.

A hash chain stored only in the same mutable database is insufficient against an administrator who can rewrite both rows and chain. State attacker capabilities and the independent evidence boundary. Algorithm and storage-provider selection remain pending security review.

### 2.6 Audit transaction boundaries and fail-closed behavior

Audit events must be committed at the authority boundary before the protected effect:
- Durable search authorization before patient-specific selector query.
- Durable candidate authorization and disclosure intent before serialization/release.
- Durable import operation/provenance marker with destination patient commit.
- Durable acknowledgement intent/outbox with destination commit, then signed acknowledgement from committed state.
- Durable pointer-sync outcome before claiming full completion.
- Durable trust lifecycle event before newly approved trust becomes active.

If a required audit transaction cannot be committed, deny the protected action or leave it pending. No in-memory, ordinary-log, best-effort asynchronous or caller-supplied substitute may stand in for mandatory evidence. For asynchronous pipelines, atomically persist business state and an outbox/event intent in the same database transaction; downstream delivery is retried and observable. An outbox does not make cross-database transactions atomic.

Define whether audit failure prevents a read, disclosure, import, key activation, revocation or state transition. For safety-critical revocation, inability to publish revocation must not silently preserve positive trust; use authoritative status checks and a bounded fail-closed policy.

### 2.7 Privacy minimization and pseudonymous references

- Use random or keyed, purpose-scoped references where audit correlation is required; avoid global deterministic hashes of patient identifiers.
- Keep tokenization keys separate from audit storage and selector-index keys (ADV-09).
- Do not reuse a patient-linked reference across unrelated tenants or purposes unless a documented need is approved.
- Do not log selector values, even when hashed, in general telemetry.
- Store the minimum source resource reference needed for authorized audit, protected at rest and resolvable only by approved roles.
- Separate event metadata from restricted payload/artifact archives. Do not copy full clinical payload into audit merely to make evidence self-contained.
- Redact exception messages, SQL parameters, HTTP headers/bodies, tracing baggage and crash dumps.
- Ensure APM, observability vendors, support bundles and error-reporting tools inherit the same restrictions.
- Apply field-level classification, retention and export controls; prevent arbitrary patient-linked searches by ordinary operators.

### 2.8 Access, review, correction and export

Define named roles and least-privilege purposes for security operations, privacy/compliance auditors, clinical governance reviewers, tenant data controllers, system/platform operators, database/key administrators and legal-hold/export custodians.

No role receives broad patient-linked audit access merely because it is a platform superuser. Exceptional access requires a separate approved workflow, explicit purpose, time bound, dual control where appropriate and immutable audit. Emergency federation remains disabled; this proposal does not enable break-glass access.

Audit records are not edited in place. Corrections append a linked amendment containing original event reference, correction authority, reason, timestamp and evidence. Preserve the original record and mark supersession explicitly. Deletion, anonymization, retention expiry and legal hold must be reconciled so immutable evidence does not become indefinite unlawful retention.

Exports are purpose-bound, minimized, encrypted, traceable, access-logged and subject to expiry. Bulk export requires stronger approval and scope limits. Auditor queries must be monitored for enumeration and inappropriate access.

### 2.9 Retention, residency and disposal

No numeric retention period is approved. D-12 and applicable privacy/legal/clinical governance must define separate schedules for:
- Patient-linked source access/security audit.
- Clinician/issuer identity and trust lifecycle evidence.
- Destination import/provenance and recovery evidence.
- Operational telemetry.
- Challenge/replay state.
- Response artifacts and immutable disclosure payloads.
- Key-management and signature-verification evidence.
- Backups, replicas, exports and legal holds.

For each class specify legal basis/purpose, owner, jurisdiction/residency, minimum/maximum period, start event, expiry behavior, hold/suspension conditions, deletion/anonymization method, backup expiry, disposal evidence and exception approval. A digest or pseudonymous reference can still be personal data if re-identifiable; assess it accordingly.

Cross-region replication, support access, vendor processing and backup restoration must obey approved residency and access restrictions. No global audit replica is assumed safe by default.

### 2.10 ADV-11 acceptance tests

- Inject raw selector, PHI, assertion, bearer handle, API key, signing secret and exception content into request/error paths; prove redaction across logs, traces, metrics, APM, crash dumps and support exports.
- Attempt to create success events using caller-supplied actor, role, purpose, timestamp, patient ID or success flag; authoritative event remains derived from trusted server state.
- Attempt audit row update/delete/reorder, sequence gap, duplicate ID, hash-chain rewrite and unauthorized correction; independent integrity verification detects tampering.
- Verify source, destination and control-plane authorities emit only their own event classes.
- Audit outage prevents required patient lookup/disclosure/import/trust activation; no process-local fallback.
- Verify business transaction and outbox event intent are atomic where required; downstream delivery retry is idempotent.
- Verify wall-clock skew does not reorder causally dependent events; uncertainty is visible.
- Verify ordinary telemetry cannot correlate the same patient across unrelated tenants or purposes.
- Verify least-privilege audit roles, dual-control exceptional access, bulk-export controls and access logging.
- Verify correction appends an amendment without altering original evidence.
- Verify retention expiry, legal hold, backup expiry, residency, export and disposal evidence across restore.
- Verify audit queries cannot be used as a patient-existence or clinician-activity oracle by unauthorized users.

## 3. ADV-12 — Complete lifecycle failure and retry authority

### 3.1 Core retry invariants

1. Timeout, disconnect, worker crash or missing response means **outcome unknown**, not failed or uncommitted.
2. Repeat an action only when protocol identifies the authority, durable state and idempotency identity permitting it.
3. An expired assertion, challenge, receipt, handle, lease or authorization artifact never authorizes a new source read.
4. Destination retry cannot use demographics, ABHA or phone/DOB/name similarity as proof of exact provenance.
5. A stale worker cannot advance state or perform side effects after a higher fencing generation is active.
6. Acknowledgement delivery, acknowledgement verification, destination commit and pointer synchronization are separate facts.
7. Operator reconciliation may inspect evidence and execute permitted transitions; it cannot invent source authorization, patient provenance, destination commit or signed acknowledgement.
8. If durable evidence cannot distinguish committed from uncommitted, stop for reconciliation. Do not guess, duplicate, delete or silently complete.
9. Every retry preserves the immutable operation tuple: source, destination, actor/issuer context, action, purpose, resource pointer, data categories, protocol/registry version and operation identity.
10. A change to actor, destination, source pointer, action, purpose, scope or protocol requires fresh authorization and, where appropriate, a new operation.

### 3.2 Authority and evidence vocabulary

| Authority/evidence | Permitted role | Does not authorize |
|---|---|---|
| Fresh source challenge + verified clinician assertion + source mapping/status | Source actor verification for bound request | Candidate disclosure without search/candidate authorization |
| Durable source search authorization | One bounded selector query under exact tuple/budget/expiry | Candidate summary or clinical payload disclosure |
| Durable candidate authorization + disclosure intent | Exact approved response categories for exact recipient/resource | Destination import or future source re-read |
| Immutable response artifact (Strategy A) | Exact bounded replay of same bytes to same authorized recipient after required current checks | Changed payload, recipient, actor, purpose or scope |
| Fresh assertion and source authorization (Strategy B) | A newly audited source read | Replay of expired prior grant |
| Discovery receipt/integrity evidence | Integrity/completeness binding for an already authorized result | Source patient read or clinician authorization |
| Resource handle | Locator for a resource subject to fresh source checks | Bearer access or destination import grant |
| Durable destination import operation + provenance marker | Exact idempotent destination recovery for same source pointer and destination | New source disclosure or demographic matching |
| Current fencing generation + CAS state | Prevent stale state transitions/side effects | Authorization to change immutable operation tuple |
| Destination signed acknowledgement verified against current trust | Evidence of exact destination commit claim | Source authorization, pointer sync or overall completion |
| Operator dual-control evidence | Approved reconciliation action within policy | Synthetic clinical/security authorization or fabricated success |

### 3.3 State model and terminal uncertainty

The protocol defines durable states at each authority boundary, not one global boolean.

**Source authorization/disclosure lifecycle (illustrative):**
- REQUEST_ACCEPTED
- NODE_AUTHENTICATED
- CHALLENGE_ISSUED
- ACTOR_VERIFIED
- SEARCH_AUTHORIZATION_COMMITTED
- SELECTOR_QUERY_ATTEMPTED
- CANDIDATE_AUTHORIZATION_COMMITTED
- DISCLOSURE_INTENT_COMMITTED
- RESPONSE_ARTIFACT_COMMITTED (Strategy A only)
- DELIVERY_ATTEMPTED
- DELIVERY_ACKNOWLEDGED (only after trusted acknowledgement verification)
- OUTCOME_UNCERTAIN
- DENIED, EXPIRED, REJECTED, RECONCILIATION_REQUIRED

**Destination import lifecycle (illustrative):**
- CLAIMED
- SOURCE_VALIDATED
- DESTINATION_COMMITTED
- COMMITTED_ACK_PENDING
- ACK_SIGNED
- ACK_DELIVERY_PENDING
- ACK_RECEIVED_UNVERIFIED
- ACK_VERIFIED
- INDEX_SYNC_PENDING
- COMPLETED
- REJECTED
- FAILED_RETRYABLE
- RECONCILIATION_REQUIRED
- SOURCE_ACCESS_REVOKED_AFTER_COMMIT (restricted/quarantined per PR #24)

These names are proposals, not a frozen wire contract. Transitions are monotonic, versioned, compare-and-swap protected and tied to an immutable operation tuple. State names must not imply unverified facts.

### 3.4 Lifecycle failure/retry authority matrix

| Boundary / failure point | What may be durable | Who may retry | Required evidence before retry | Permitted action | Forbidden action / safe stop |
|---|---|---|---|---|---|
| Node trust lookup unavailable | No challenge allocation | Destination client after recovery | Current node trust and relationship | Restart bootstrap under bounded budget | No challenge allocation or stale-positive trust |
| Challenge allocated; response lost | Challenge/idempotency record | Same authenticated node/issuer context | Same canonical request, unexpired challenge, current node status | Return same bounded challenge response | No duplicate challenge storm or patient selector query |
| Challenge expired or replay state uncertain | Expired/uncertain challenge record | Authenticated destination starts fresh flow | New challenge, fresh assertion and current trust | New authorization attempt | Old challenge cannot authorize read |
| Assertion verified; search-audit commit fails | No durable search authorization | Destination after audit recovery | Fresh source challenge/assertion and durable search authorization | Restart authorization flow | No selector query |
| Search authorization committed; crash before query | Search grant/audit | Source worker only if same grant remains valid; otherwise fresh flow | Durable request identity, unexpired grant, budget reservation and current policy/status | Execute same bounded query under atomic claim | No expired grant or changed tuple |
| Query starts; DB/worker times out | Search attempt and query outcome may be unknown | Source recovery worker | Durable query attempt, same request identity, remaining budget, safe idempotency and current policy | Reconcile; rerun only if explicitly safe and authorized | No unbounded repeat or candidate-existence response |
| Candidate resolved; candidate authorization/audit fails | Internal candidate state may exist | Source service after audit recovery | Fresh/current candidate authorization and durable audit | Re-evaluate before serialization | No candidate detail, handle, pointer or distinguishable response |
| Disclosure intent committed; artifact not committed (A) | Authorized intent, no immutable artifact | Source service under same valid decision or fresh authorization | Exact intent tuple, artifact transaction state and current revocation checks | Complete artifact creation only if durable state proves it did not occur | No reconstruction from stale memory or changed patient data |
| Response artifact committed; send not started | Immutable artifact | Source delivery worker | Artifact digest, recipient binding, expiry and current replay policy | Send exact committed bytes | No source re-read or mutation |
| Network send times out/disconnects | Artifact/attempt; receipt unknown | Source delivery worker or destination reconciliation | Same artifact/operation, valid recipient trust, replay policy and idempotency | Strategy A: resend exact bytes if allowed; Strategy B: fresh authorization and new audited read | No assumption of delivery/non-delivery or changed payload replay |
| Destination receives payload; validation fails | Destination rejection audit may exist | Destination service after correction/new authorization as applicable | Stable rejection code, original artifact and immutable tuple | Reject; corrected request requires new approved authorization | No silent action/purpose/scope/payload change |
| Import begins after source receipt/authorization expires | Destination claim may exist; no valid new disclosure | Destination clinician starts fresh source flow | Fresh challenge/assertion/search/candidate authorization | Reauthorize and read only if policy allows | Expired receipt/handle/operation ID cannot authorize read |
| Source policy/clinician/key revoked before retrieval | Source authorization/artifact may exist | Source authority after current status review | Fresh current authority and approved replay treatment | Deny or quarantine | No stale-positive cached status |
| Destination import claim races with duplicate | Durable unique claim may exist | Same authenticated destination operation context | Same server-derived source pointer, source branch, destination and protocol tuple | Join/observe same operation | No second clone or demographic identity shortcut |
| Destination commit succeeds; HTTP response lost | Patient, provenance and operation marker committed | Destination recovery worker/client exact retry | Unique marker, same tuple, current fencing generation | Return/reconcile same committed clone | No blind insert or generic failure implying no commit |
| Destination commit succeeds; control-plane update fails | Destination commit/provenance; control-plane stale | Authorized reconciler/worker | Destination durable marker and provenance digest; current policy for later disclosure | Reconcile control-plane state and acknowledgement | Control plane is not source of truth for destination commit |
| Destination commit outcome uncertain | Partial DB/network evidence | Destination recovery worker; operator only under dual control | Durable correlation marker and transaction state | Reconcile exact operation; if ambiguous, stop | No insert retry, synthetic marker or success claim |
| Commit succeeds; acknowledgement signing fails | Commit plus outbox/ack intent | Destination attestor | Re-read committed marker, exact digest, current generation and trusted key status | Sign same commit claim after verification | No signing from stale memory |
| Ack signed; delivery lost | Durable signed ack | Destination outbox worker | Exact stored ack bytes, same operation/generation/digest, key status per policy | Redeliver identical acknowledgement | No different claim for same generation |
| Ack received; source verification unavailable | Received but unverified bytes | Source verification worker | Original bytes, current destination trust, replay state and operation binding | Retry verification | No ACK_VERIFIED or completion |
| Ack fails signature/trust/binding/replay | Rejection/security event | Source security owner; no automatic acceptance | New valid acknowledgement from trusted destination state or investigation | Quarantine/reconcile | No caller-supplied key, lower generation or changed digest |
| Ack verified; pointer sync fails | Verified commit; pointer stale | Authorized pointer-sync worker | Same operation/provenance, current sharing policy and generation | Reconcile pointer under current policy | No COMPLETED claim |
| Source access revoked after destination commit | Durable clone/provenance and verified/uncertain ack | Governed privacy/clinical retention owner plus authorized operations | Revocation evidence, retention/legal basis, provenance, dual-control decision | Restricted/quarantine and approved retention workflow | No automatic deletion, ordinary use or pointer publication |
| Worker lease expires; old worker resumes | Newer fencing generation may exist | Current lease holder only | Durable generation and CAS version | Current worker continues permitted transition | Stale worker cannot commit, sign, deliver, publish or overwrite |
| Operator reconciliation required | Partial/conflicting durable evidence | Named dual-control operators | Immutable evidence, incident reference, approvals and exact permitted transition | Advance only explicitly allowed state | No synthetic authorization, commit, provenance, acknowledgement or clinical approval |
| Audit pipeline/integrity verification fails | Business state may be pending | Owning authority after audit restored/reconciled | Verified audit continuity/integrity and missing-event analysis | Resume only from provable durable state | No protected action with missing mandatory evidence |

### 3.5 Retry decision algorithm

Before retry, the owning service must answer from durable state:
1. What exact operation and immutable tuple is being resumed?
2. Which authority owns the next action?
3. What is the latest committed state and version?
4. Is prior authorization still valid for this exact action, recipient, actor, purpose, resource and scope?
5. Does this step repeat a patient read, disclosure, destination write, acknowledgement or pointer publication?
6. What durable idempotency/provenance/fencing evidence prevents duplicate or stale side effects?
7. What audit event must commit before the action?
8. What response is safe if outcome remains unknown?

If any answer is unavailable or contradictory, transition to RECONCILIATION_REQUIRED or the appropriate restricted state. Do not infer success or failure from absence of a row in a different database.

### 3.6 Operator reconciliation and dual control

Operator recovery is a privileged workflow, not an alternate authorization protocol.

Requirements:
- Separate read-only evidence inspection from state-changing reconciliation.
- Require a case/incident reference, reason, named operator identities, approved scope and expiry.
- Require two independent authorized approvers for high-impact or ambiguous patient-data operations.
- Enforce least-privilege, time-bounded credentials and just-in-time access.
- Show source, destination and control-plane evidence separately with provenance and timestamps.
- Require explicit acknowledgement of uncertainty and residual risk.
- Permit only enumerated state transitions; no arbitrary SQL or direct status editing.
- Record before/after state, evidence references, approvers, action and outcome in immutable audit.
- Preserve source authorization for any new source read; operator approval cannot replace clinician authorization.
- Preserve destination fencing and provenance for any retry/commit.
- No force-success, ignore-audit, skip-source-check, recreate-provenance or publish-pointer-anyway control.
- Escalate conflicting/insufficient evidence to clinical governance, privacy/legal and security; leave operation quarantined/pending.

### 3.7 Recovery idempotency and state consistency

- Unique idempotency identity derives server-side from validated source pointer, source branch, destination branch and protocol/version; not demographics.
- Destination provenance marker is committed atomically with clone and operation record.
- State transitions use unique constraints, transaction-safe claims, monotonic versions and CAS.
- Fencing generations are enforced at every side-effect boundary, not merely checked at worker start.
- Outbox event intent is committed in the same DB transaction as the business state it describes.
- Source, destination and control plane remain separate transaction authorities; use explicit reconciliation, not claims of distributed atomicity.
- Pointer publication/sync is independently recoverable and re-evaluates current policy.
- Acknowledgement verifies only the exact destination commit claim; it cannot imply pointer sync.
- Source authorization cannot be reused for a different pointer, destination, action, purpose or data category.
- A new source read after expiry/revocation requires fresh source authorization and a distinct audit event.

### 3.8 ADV-12 acceptance tests

- Build a state-transition × failure-point × retry-authority inventory from the matrix; every row has deterministic failure-injection coverage.
- Kill processes at every durable commit boundary using independent application processes.
- Test lost responses after each successful commit; exact retry returns/reconciles the same operation.
- Test simultaneous same-operation retries across workers and PostgreSQL sessions; exactly one destination clone/provenance marker.
- Test different source pointers with identical demographics; no silent merge or reuse.
- Test expired/revoked challenge, assertion, receipt, handle, artifact, key and lease; no new source read or stale side effect.
- Test stale workers after generation increment at commit, sign, delivery, source transition and pointer publication.
- Test destination commit succeeds but control-plane update fails; recover from destination provenance.
- Test acknowledgement sign/send/receive/verify failures and key rotation/revocation.
- Test source policy revocation before read, after response, before destination commit and after destination commit.
- Test pointer-sync failure/retry; no false COMPLETED state.
- Test audit outage, event duplication, outbox replay, integrity gap and tampering; protected operation fails closed or remains pending.
- Test operator workflow cannot synthesize authorization, provenance, commit or acknowledgement.
- Verify every uncertain API response has a stable machine-readable status and does not falsely claim success or failure.
- All concurrency, transaction-order, fencing and outbox tests use PostgreSQL with independent sessions/processes; SQLite-only tests are insufficient.

## 4. Cross-document reconciliation requirements

Reconcile this proposal with:
- PR #19 runtime remediation and remaining concurrent-import, pointer-recovery and demographic-reuse concerns.
- PR #23 durable import idempotency and provenance design.
- PR #24 fencing, fresh-receipt recovery and post-commit quarantine.
- PR #31 runtime/design consistency findings.
- PR #32 three-lifecycle protocol separation.
- PR #33 ADV-11/ADV-12 findings and implementation stop conditions.
- PR #34 source search authorization and clinician identity proofing.
- PR #35 challenge abuse, audit/disclosure boundaries and Strategy A/B response replay.
- PR #36 revocation freshness and resource handle/manifest binding.
- PR #37 source access boundary and canonical purpose/scope registry.
- PR #38 selector-index privacy and destination acknowledgement trust/fencing.

Conflicts must be resolved in the canonical protocol specification and decision register before implementation. No proposal may silently weaken a stricter requirement in another document.

## 5. Governance decisions required

| Decision | Proposed direction | Accountable approval | Status |
|---|---|---|---|
| Audit event ownership | Each source/destination/control-plane authority emits only its own events | Security + platform + data owners | Pending |
| Audit schema/versioning | Versioned envelope, controlled event vocabulary and immutable IDs | Security architecture + audit owner | Pending |
| Audit integrity architecture | Independent tamper-evidence boundary beyond one mutable DB | Security + platform/SRE + audit owner | Pending |
| Trusted time and ordering | Trusted time source, drift policy and causal sequence/version references | Platform/SRE + security | Pending |
| Patient-linked audit reference | Purpose-scoped opaque reference, restricted resolution | Privacy/legal + data owner + security | Pending |
| Audit reader roles | Named least-privilege security/privacy/clinical/operations roles | Privacy/legal + clinical governance + security | Pending |
| Audit correction/export | Append-only correction, dual-control bulk export and traceable disclosure | Audit owner + privacy/legal | Pending |
| Retention by evidence class | Separate schedules, residency, legal hold and disposal evidence | Privacy/legal + records owner + clinical governance | Pending |
| Audit storage/residency | Region and backup topology consistent with approved residency | Privacy/legal + platform/data owner | Pending |
| Response artifact strategy | Decide Strategy A or B by action/data category; no global default | Clinical governance + privacy/legal + security | Pending |
| Failure state vocabulary | Reconcile source, discovery and destination state machines | Security architecture + platform + product | Pending |
| Retry authority | Owning authority only; fresh source authorization for every new read | Clinical governance + security | Pending |
| Reconciliation workflow | Dual-control, enumerated transitions, no force-success override | Security + clinical governance + operations | Pending |
| Numeric challenge/rate budgets | Measured aggregate budgets and overload policy | Security + SRE + product | Pending |
| Acknowledgement and fencing | Reconcile with ADV-10 branch-scoped trust and monotonic generation | Security + destination owner + platform | Pending |
| Formal D-01–D-14 decisions | Named approvers, evidence, dates and explicit implementation authorization | Accountable governance bodies | Pending |

No retention number, legal basis, role entitlement, emergency exception or implementation approval is implied. Record approvals in the canonical D-01–D-14 register with approver name, organization, role, date, governance reference, evidence, scope, residual risk, compensating controls, expiry and disable conditions. D-11 project direction remains YES for local cross-branch imports; formal governance approval remains pending.

## 6. Implementation gates

Do not implement ADV-11/ADV-12 until:
1. Audit event ownership, schema, integrity architecture, time/order model and independent evidence boundary are reviewed and approved.
2. Patient-linked audit, telemetry, trust audit, import audit and clinical provenance are separated with data classifications and access roles.
3. Legal/privacy/clinical owners approve retention, residency, export, correction, legal hold, backup expiry and disposal per evidence class.
4. Mandatory audit commit boundaries are mapped to actual source, destination and control-plane transactions; outbox atomicity is demonstrated.
5. Response artifact Strategy A/B is decided per action/data category and reconciled with revocation and retry semantics.
6. All source/discovery/destination states and failure points have one reconciled state-transition and retry-authority matrix.
7. Operator reconciliation permissions, dual control, evidence requirements and prohibited overrides are approved and tested.
8. PostgreSQL independent-session/process concurrency, failure injection, audit tampering, restore, retention and fencing tests are accepted.
9. ADV-01/ADV-02 critical issues and ADV-03–ADV-10 high-risk dependencies are independently reviewed; unresolved risks are explicitly accepted or remain release blockers.
10. Formal D-01–D-14 governance decisions and explicit implementation authorization are recorded.

## 7. Disposition

This document proposes controls for ADV-11 and ADV-12; it does not close either finding. Closure requires approved audit governance and integrity controls, privacy/retention/residency decisions, a complete reconciled retry-authority matrix, deterministic PostgreSQL failure-injection evidence, independent security/privacy/clinical review and verified runtime enforcement.

**AUD-004 remains release-blocking.** This document authorizes no runtime code, migrations, configuration, database-role changes, cryptographic/key changes, trust entries, partner onboarding, pilot, production patient-data access, merge, deployment, release or emergency federation.
