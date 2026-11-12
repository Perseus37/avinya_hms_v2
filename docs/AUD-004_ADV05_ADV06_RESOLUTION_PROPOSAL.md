# AUD-004 ADV-05/ADV-06 Revocation and Resource Artifact Security Proposal

**Status:** PROPOSED DESIGN — NOT APPROVED FOR IMPLEMENTATION  
**Parent:** PR #35 (ADV-03/ADV-04 challenge and disclosure boundary proposal)  
**Scope:** Resolve ADV-05 revocation races and ADV-06 transferable resource-handle/manifest risks.  
**Constraint:** This document defines security requirements and decision points. It does not select cryptographic algorithms, authorize runtime changes, or close either finding.

## 1. Executive decisions proposed

1. Revocation is evaluated by the authority that owns the revoked fact: source tenant for clinician mapping, affiliation, patient policy and source authorization; issuer/trust authority for issuer and signing-key status; destination tenant for destination user/session and import eligibility.
2. Every protected transition has an explicit freshness checkpoint. A previous successful check is not an indefinite authorization lease.
3. A revocation blocks new protected work immediately once observed. If status cannot be established within the approved freshness bound, the operation fails closed or enters an explicit uncertain/restricted state; it must not silently continue using stale cache.
4. A resource handle is an opaque locator, never a bearer grant. Redemption requires fresh actor proof and source-side authorization for the exact action, purpose, destination, resource and scope.
5. A response manifest is integrity evidence, not authority. A valid signature or digest cannot substitute for clinician verification, current policy evaluation, replay protection or import-specific authorization.
6. No distributed transaction is assumed. If revocation races with network delivery or destination commit, preserve truthful partial state and apply governed restriction/quarantine; do not claim that already disclosed bytes can be recalled or silently delete committed clinical data.

## 2. ADV-05 — Revocation race model

### 2.1 Revocation domains and owners

| Revoked fact | Authority of record | Required status |
|---|---|---|
| Issuer identity / partner trust | Source trust registry and its approved governance authority | Active, suspended, revoked, unknown |
| Signing key | Source trust registry / key custodian | Active, retiring, revoked, compromised |
| Clinician identity mapping | Source-controlled clinician mapping registry | Active, suspended, revoked |
| Clinician affiliation / branch relationship | Source-approved affiliation authority | Active, expired, suspended, revoked |
| Professional registration / credential, where required | Approved authoritative credential source plus source policy | Valid, expired, suspended, revoked, unknown |
| Destination user session / account | Destination tenant identity system | Active, expired, revoked |
| Patient sharing consent / privacy policy | Source tenant patient-policy authority | Current decision and version |
| Resource handle / response artifact | Source tenant artifact store | Active, expired, revoked, consumed/replayable per approved strategy |
| Import operation / destination eligibility | Destination tenant | Current operation state, policy state and fencing generation |

The protocol must not collapse these domains into one boolean such as `is_valid`. Each authority supplies a versioned status and effective time, and the source records which versions informed each authorization decision.

### 2.2 Mandatory freshness checkpoints

| Checkpoint | Required checks before proceeding | Failure outcome |
|---|---|---|
| C0 — challenge allocation | Node relationship, issuer trust, endpoint eligibility and abuse controls | Reject without allocating challenge |
| C1 — actor assertion verification | Signature/key status, issuer trust, assertion time/audience, source clinician mapping, affiliation and required credential freshness | Reject; no selector query |
| C2 — search authorization | Recheck relevant actor/trust status and current search policy; durable search authorization audit before selector resolution | Reject; no patient-specific query |
| C3 — candidate authorization | Current patient policy, clinician permission, exact candidate/action/purpose/destination/scope | Deny without candidate detail |
| C4 — disclosure intent / artifact commit | Recheck revocation versions and policy immediately before durable disclosure intent/artifact commit | Abort or mark uncertain; no send |
| C5 — artifact retrieval / replay | Revalidate recipient, actor/session or approved replay identity, issuer/key, clinician status, policy and artifact state according to the selected Strategy A/B contract | Deny replay or require fresh authorization |
| C6 — import source re-read | Fresh import-specific assertion and source-side authorization; current source patient policy and resource binding | No source re-read/disclosure |
| C7 — destination commit | Destination rechecks local session/permission, operation state, fencing generation and source authorization evidence freshness required by governance | Do not activate/commit; quarantine or reconcile |
| C8 — pointer publication / completion | Current sharing policy, committed provenance, operation generation and index-sync state | Keep index sync pending/restricted; never report complete |

The exact freshness interval for each external status source, cache TTL, and acceptable propagation delay are governance decisions. Until approved, implementations must not invent permissive cache windows. A missing, stale, contradictory or unavailable required status is not equivalent to active.

### 2.3 Revocation timing and in-flight operation semantics

- **Before C1/C2:** reject. No patient-specific selector query is permitted before search authorization.
- **After C2 but before candidate authorization:** stop before candidate data is returned. Search audit remains truthful; do not disclose match/no-match details.
- **After candidate authorization but before C4:** re-evaluate all applicable status versions immediately before disclosure intent/artifact commit. If revoked, do not serialize or release patient data.
- **After artifact commit but before network retrieval:** artifact is not automatically redeemable. Apply the selected response retry strategy and revalidate current replay rights. Under Strategy A, stored bytes may be replayed only if explicit policy permits it after fresh recipient/actor/trust checks; otherwise deny and retain the artifact under its governed retention state. Under Strategy B, require a fresh challenge/assertion/authorization and perform a new audited source read.
- **During or after network send:** bytes already received cannot be recalled. Record delivery as confirmed only with a valid destination acknowledgement; otherwise record `OUTCOME_UNCERTAIN`. Revoke further retrieval/replay, notify the approved incident/reconciliation workflow and restrict recipient access where supported.
- **After destination commit but before pointer sync/completion:** apply the PR #24 recovery model. If required source policy or trust is revoked, transition to a restricted/quarantined state such as `SOURCE_ACCESS_REVOKED_AFTER_COMMIT`; do not publish the pointer, mark completed, silently activate the clone or automatically delete clinical data. Retention, clinical access and remediation require an approved owner/workflow.
- **After completion:** revocation prevents future disclosures/replays and may restrict future use under source/destination policy. It does not retroactively make an earlier authorized event nonexistent or imply automatic deletion. Record the revocation and affected operation references.

### 2.4 Rotation versus compromise

- Planned key rotation is a controlled overlap: new assertions use the new approved key; old key acceptance is bounded by an approved retirement window and assertion lifetime. Retiring a key must not silently extend existing assertions.
- Suspected/confirmed key compromise is an emergency revocation: immediately deny new assertions and artifact redemption under that key once the source trust authority records the event; invalidate caches and outstanding challenges/artifacts according to the incident policy.
- Issuer compromise may require suspending all subjects and operations issued by that issuer, not merely one key. The source must be able to revoke issuer trust independently of key status.
- Clinician departure, suspension or credential expiry is distinct from issuer/key rotation and must invalidate the source-side mapping/authorization even when a signed assertion remains cryptographically valid.
- No emergency bypass or automatic trust fallback is permitted.

### 2.5 Distributed status propagation and monotonicity

Each authority-owned status change should carry a monotonically increasing version/sequence, effective timestamp, issuer/authority identity and event ID. Consumers must reject version rollback and stale updates. The design must specify:
- authenticated, integrity-protected revocation event delivery;
- replay and duplicate event handling;
- cache invalidation acknowledgements and maximum propagation objective;
- periodic reconciliation against authority-of-record;
- behavior during partition or event-stream outage;
- durable evidence of which status versions were checked at each checkpoint;
- recovery when a consumer missed an event.

A notification event is not proof that every consumer has applied it. A system may report revocation propagation complete only after required acknowledgements/reconciliation evidence exists. During a partition, protected operations fail closed when required freshness cannot be established. Do not rely on process-local caches or best-effort pub/sub as the sole revocation control.

### 2.6 Revocation event and state model

Proposed event categories (names illustrative, not a final schema):
- `TRUST_ISSUER_SUSPENDED`, `TRUST_ISSUER_REVOKED`
- `SIGNING_KEY_RETIRING`, `SIGNING_KEY_REVOKED`, `SIGNING_KEY_COMPROMISED`
- `CLINICIAN_MAPPING_SUSPENDED`, `CLINICIAN_MAPPING_REVOKED`
- `AFFILIATION_EXPIRED`, `AFFILIATION_REVOKED`
- `CREDENTIAL_STATUS_CHANGED`
- `PATIENT_SHARING_POLICY_CHANGED`
- `RESOURCE_HANDLE_REVOKED`, `RESPONSE_ARTIFACT_RESTRICTED`
- `IMPORT_RESTRICTED_AFTER_COMMIT`

Events must be source/authority-generated, versioned and attributable. Caller-supplied claims cannot create a revocation or successful revalidation event. Keep patient identifiers and credential material out of general telemetry; use protected references in restricted audit.

## 3. ADV-06 — Resource handle and manifest security

### 3.1 Resource handle is a locator, not a capability

A handle must:
- be opaque and generated with cryptographically secure high entropy;
- reveal no patient ID, MRN, branch, tenant, selector, resource type or authorization decision;
- be recipient-bound to the expected destination and, where policy requires, actor/issuer, action, purpose, protocol version and operation;
- be scoped to one exact source resource or immutable response artifact and an explicitly approved data-category set;
- have a short, governed expiry and explicit state (active, expired, revoked, consumed, retained-for-audit);
- be stored as a one-way hash where feasible; raw handle material must not be persisted in logs, traces, URLs, referrers, analytics or exception messages;
- be protected by atomic redemption/replay state in durable storage, not an in-process lock;
- be invalidated or restricted on relevant trust, actor, policy or resource revocation.

A handle does not grant access by possession. Every redemption must authenticate the destination relationship, verify a fresh actor assertion for the exact import/disclosure action, validate the handle binding and expiry, check replay state, and obtain a new source-side authorization decision. The source must not accept caller-supplied source table names, ORM paths, tenant schema names or arbitrary patient identifiers as a substitute for resolving the server-owned handle.

### 3.2 Binding contract

At minimum, the source-side handle record binds:
- handle hash and protocol/schema version;
- source tenant/branch identity and source-owned resource reference;
- destination tenant/branch and registered issuer identity;
- issuer-scoped clinician subject and actor mapping version, if actor-bound;
- exact action and canonical purpose;
- approved selector/search or resource scope and data categories;
- source authorization decision reference and relevant policy/status versions;
- associated challenge/assertion/replay reference without storing reusable secrets;
- response artifact or import operation reference, where applicable;
- issued-at, expiry, revocation version and atomic use/replay state.

The binding is validated server-side as a complete tuple. Partial matches, wildcard fields, implicit defaults and caller-controlled rebinding are rejected. If an approved workflow needs delegation to another clinician, it must create a separately authorized artifact; it must not edit the original handle binding.

### 3.3 Fresh authorization at redemption

Before redemption/source re-read:
1. Authenticate the registered destination node and validate its active relationship.
2. Verify a fresh, correctly audience-bound actor assertion; derive subject from trusted issuer claims and verify source-controlled clinician mapping, affiliation and required credential status.
3. Verify action, purpose, destination, resource, data categories, protocol version and operation exactly match the handle.
4. Re-evaluate current patient sharing/privacy policy and source authorization.
5. Check issuer/key/clinician/resource/handle revocation freshness.
6. Atomically claim replay/idempotency state with a durable compare-and-swap or uniqueness constraint.
7. Commit required source audit/disclosure intent before reading or releasing protected data.
8. Re-read source data under the source tenant's own access boundary; do not trust a destination-provided payload as authoritative source data.

A previous discovery/search assertion cannot be reused as import authorization. Import is a distinct action and requires an import-specific authorization decision. A handle or manifest cannot turn a previously authorized search into an authorized import.

### 3.4 Signed response manifest

Where a response manifest is used, it should be a canonical, versioned statement of what the source committed to disclose. Proposed fields:
- protocol and manifest schema version;
- source issuer/tenant/branch identity and key identifier;
- intended destination tenant/branch and audience;
- exact action, canonical purpose and operation/correlation identifier;
- opaque source resource reference and permitted data-category/scope identifiers;
- payload digest, payload format/schema identifier and content encoding;
- source authorization decision reference and policy/status version references;
- issued-at, expiry, unique manifest ID/nonce and replay context;
- signature metadata constrained by a separately approved algorithm/key policy.

The manifest must use a specified canonical serialization and domain separation so semantically equivalent encodings cannot produce ambiguous signatures. The signing algorithm, key type/size, canonicalization standard, digest algorithm, certificate/key distribution and rotation policy remain explicit governance/security decisions; this proposal does not choose them.

Manifest verification must reject unknown versions, unsupported algorithms, duplicate/ambiguous fields, non-canonical encodings, wrong audience/source/destination, mismatched operation/action/purpose/scope, expired or revoked keys, stale policy versions where freshness is required, altered payload digest, and cross-protocol/downgrade substitution.

A valid signature proves the trusted source signed those bytes. A digest proves byte integrity relative to the signed manifest. Neither proves the clinician was entitled to access the resource at the time of redemption, that the patient policy remains current, or that the destination may import it now.

### 3.5 Artifact and handle lifecycle separation

Keep these distinct:
1. source authorization decision;
2. handle issuance;
3. response manifest/artifact commit (if Strategy A is selected);
4. handle/artifact redemption;
5. fresh source authorization and source re-read (where Strategy B or import requires it);
6. network delivery and authenticated acknowledgement;
7. destination import claim, commit, provenance and pointer synchronization.

A handle issuance does not imply artifact creation. Artifact creation does not imply delivery. Delivery does not imply destination commit. Destination commit does not imply pointer publication or completed recovery. Every transition needs its own durable state and owner-authority audit evidence.

### 3.6 Strategy A and Strategy B compatibility

The PR #35 alternatives remain mutually distinct and must be selected per approved action/data category:

- **Strategy A — immutable response artifact:** Persist exact encrypted bytes and digest before sending. A retry may return only the same committed artifact, never re-query or regenerate different bytes. Retrieval still requires current recipient binding, key/trust checks and whatever actor/policy revalidation governance requires. If policy revocation prohibits replay, deny retrieval and mark the artifact restricted; do not silently replace it with a fresh query under the old operation.
- **Strategy B — no retained PHI artifact:** Do not retain a replayable PHI response. Any retry requires a fresh challenge, assertion, search/import authorization as appropriate, current source policy and a new audited source read. The new read is a new disclosure event, not a replay of the prior one.

The choice, PHI retention period, encryption/access model, legal hold, backup behavior and revocation effect on already committed artifacts remain pending privacy/legal, clinical and security approval. No hybrid behavior may be introduced implicitly.

## 4. Combined race and failure outcomes

| Race / failure | Required outcome | Prohibited behavior |
|---|---|---|
| Key/issuer revoked before assertion verification | Reject before selector query | Accept from stale cache |
| Clinician affiliation revoked after search authorization but before candidate authorization | Deny candidate disclosure; retain truthful search audit | Return candidate existence or metadata |
| Patient policy changes before disclosure intent commit | Re-evaluate; deny or use new approved decision | Release under stale policy |
| Revocation occurs after artifact commit but before retrieval | Apply selected Strategy A/B replay rule; restrict if no longer authorized | Treat handle possession as permission |
| Handle copied to another destination | Recipient-binding failure; no source read | Rebind handle based on caller input |
| Handle replayed concurrently | One atomic state transition; deterministic duplicate/in-progress response | Two independent source disclosures |
| Manifest payload altered or swapped | Digest/signature/binding failure; no import | Trust payload because manifest ID matches |
| Manifest valid but actor/credential revoked | Fresh actor check fails; no redemption | Treat signature as clinician proof |
| Destination commit succeeds, then source policy is revoked | Restricted/quarantined recovery state; no pointer publication pending governed resolution | Silently mark complete or automatically delete |
| Revocation service/audit store unavailable | Fail closed or explicit uncertain state per approved matrix | Best-effort fallback, in-memory authorization or false success |
| Stale worker resumes after newer generation | Fencing/CAS rejects stale side effect | Send, publish or acknowledge from stale state |

## 5. Audit and evidence requirements

For each checkpoint, retain a source-authority event recording:
- event/schema version and trusted timestamp;
- source authority and actor/issuer references;
- operation and correlation references;
- action, purpose, destination and resource reference at the minimum necessary level;
- status/policy/key/mapping versions checked;
- decision and stable reason category;
- handle/manifest/artifact digest reference (never raw secret);
- replay/fencing generation and outcome;
- prior and next durable state where applicable.

Separate restricted patient-linked security audit from operational metrics. Do not log raw handles, assertions, private keys, payloads, raw selectors or unnecessary PHI. Define tamper evidence, correction/append semantics, access roles, retention/legal hold and audit export under D-12. An audit outage at a mandatory checkpoint prevents the protected operation or completion claim.

## 6. Required acceptance tests

### 6.1 Revocation and freshness
- Revoke issuer, signing key, clinician mapping, affiliation, credential and patient policy independently at every checkpoint C0–C8.
- Verify no patient-specific query occurs after failed C1/C2 and no candidate detail is returned after failed C3/C4.
- Verify stale, missing, out-of-order and contradictory revocation events cannot restore an older active status.
- Verify missed-event recovery through authority-of-record reconciliation.
- Verify partition, cache outage and revocation-service outage fail closed at required freshness boundaries.
- Verify planned key rotation overlap and emergency key compromise have distinct outcomes.
- Verify issuer compromise suspends the configured blast radius and prevents old assertions/handles from being redeemed.
- Verify post-send revocation records delivery truthfully and blocks subsequent replay where required.
- Verify post-commit revocation enters restricted/quarantine state and never silently deletes or activates the clone.
- Verify audit records identify the exact status versions used for each decision.

### 6.2 Handle and manifest
- Handle entropy/opacity review; no PHI or topology in handle bytes.
- Stored handle value is hashed; logs, URLs, referrers, traces and errors contain no raw handle.
- Wrong source, destination, actor, issuer, action, purpose, resource, scope, protocol or operation is rejected.
- Expired, revoked, consumed and unknown handles have safe normalized responses that do not reveal patient existence.
- Concurrent redemption across independent PostgreSQL sessions produces one atomic result.
- Handle replay after actor/key/policy revocation is rejected according to the approved strategy.
- Cross-destination copy, handle swapping, manifest swapping and operation substitution are rejected.
- Manifest tampering, payload digest mismatch, duplicate fields, non-canonical serialization, unsupported version/algorithm and downgrade are rejected.
- A valid manifest with an invalid/revoked actor or changed patient policy is not accepted as authorization.
- Import requires a distinct fresh import assertion and source authorization; discovery/search artifacts cannot authorize import.
- Destination verifies manifest source trust, recipient, operation, digest, scope, freshness, provenance and fencing generation.
- Key rotation and compromise invalidate or preserve artifacts only according to the approved explicit policy.

### 6.3 Race, concurrency and recovery
- Inject revocation immediately before and after each durable boundary.
- Inject process crash between status check, audit commit, handle claim, artifact commit, network send, acknowledgement, destination commit and pointer publication.
- Run concurrent handle redemption, revocation and import with independent PostgreSQL sessions/processes.
- Prove monotonic status versions, CAS transitions and fencing prevent stale workers from disclosing, committing, publishing or acknowledging.
- Prove uncertain outcomes remain uncertain until authority-owned evidence reconciles them.
- Verify Strategy A replay returns byte-identical artifact only; Strategy B performs a new separately audited source read.
- Verify no recovery operator can synthesize an authorization or bypass current source policy.

SQLite-only or single-session tests are insufficient for concurrency, uniqueness, atomic replay and fencing evidence.

## 7. Governance decisions required

| Decision | Proposed direction | Accountable approval | Status |
|---|---|---|---|
| Revocation freshness per authority/checkpoint | Explicit bounded freshness; fail closed when exceeded | Security + privacy/legal + clinical governance | Pending |
| Revocation propagation objective | Versioned events plus acknowledgement and periodic reconciliation | Security + platform/SRE | Pending |
| Cache policy during partition | No stale-active fallback for protected operations | Security + clinical governance | Pending |
| Planned key rotation overlap | Bounded overlap tied to assertion lifetime | Security/key custodian | Pending |
| Compromise response and issuer blast radius | Immediate trust suspension with documented incident process | Security + partner governance | Pending |
| Credential evidence and freshness | Authority-specific proofing and expiry/revocation rules | Clinical governance + privacy/legal | Pending |
| Post-send revocation handling | Record irreversible disclosure; block future replay and invoke incident workflow | Clinical governance + privacy/legal + security | Pending |
| Post-commit quarantine and retention | Restricted state, named clinical/legal retention owner; no automatic deletion | Clinical governance + privacy/legal + product | Pending |
| Handle entropy/expiry/replay limits | Security-reviewed values and PostgreSQL atomic state | Security architecture | Pending |
| Handle actor binding | Bind to issuer-scoped subject and destination; delegation requires new authorization | Clinical governance + security | Pending |
| Manifest canonicalization and cryptography | Approved standards/algorithms/key custody, no local improvisation | Security architecture + key custodian | Pending |
| Strategy A/B per data category | Explicit selection; Strategy A requires PHI artifact governance | Clinical governance + privacy/legal | Pending |
| Artifact encryption, retention and legal hold | Classification, access, backup and deletion rules | Privacy/legal + data owner + security | Pending |
| Audit schema and retention | Reconcile with D-12 and PR #35 | Audit owner + privacy/legal + security | Pending |
| Import acknowledgement/fencing trust | Reconcile with ADV-10 and PRs #23/#24 | Security architecture + destination owner | Pending |

All approvals must be recorded in the canonical D-01–D-14 decision register with approver name, organization, role, date, governance reference, evidence, affected stages, residual risk, compensating controls, expiry and disable conditions. D-11 project direction remains YES for local cross-branch imports, while formal governance approval remains pending. This proposal does not change that status.

## 8. Implementation gates and dependencies

Do not begin runtime implementation for ADV-05/ADV-06 until:
1. Revocation authority, status vocabulary, freshness checkpoints and numeric freshness/propagation objectives are approved.
2. Key rotation versus compromise, issuer suspension and clinician/credential revocation semantics are approved.
3. Strategy A/B is selected per action/data category and reconciled with privacy, clinical and legal retention requirements.
4. Handle binding, replay, storage, expiry and manifest canonicalization/cryptographic standards are independently reviewed.
5. Import-specific source authorization and destination verification are reconciled with PR #24 fencing/provenance and ADV-10 acknowledgement trust.
6. The combined state × checkpoint × revocation × crash × retry-authority matrix is complete and reviewed.
7. PostgreSQL concurrency, race-injection, key-rotation and recovery acceptance plans are approved.
8. D-01–D-14 formal governance decisions and explicit implementation authorization are recorded.

## 9. Relationship to prior proposals

- PR #32 separates source authorization, discovery integrity and destination import recovery; this proposal preserves those lifecycle boundaries.
- PR #33 defines ADV-05 and ADV-06 as high-risk unresolved findings.
- PR #34 requires source-controlled clinician identity/affiliation proofing and two-stage discovery authorization; this proposal rechecks those source-owned facts at lifecycle boundaries.
- PR #35 defines durable challenge/audit/disclosure boundaries and the mutually distinct Strategy A/B response retry choices; this proposal adds revocation and artifact-binding requirements without choosing between them.
- PRs #23/#24 require durable import identity, provenance, fencing, fresh authorization for new source reads and restricted handling after policy revocation following destination commit.
- PR #19 runtime behavior does not currently establish the guarantees proposed here. Design text is not evidence of runtime enforcement.

## 10. Disposition

This document proposes controls for ADV-05 and ADV-06; it does not close either finding. Closure requires independent security, privacy and clinical review; approved governance decisions; PostgreSQL concurrency and deterministic race/failure-injection evidence; and verified runtime enforcement across remote federation and local cross-branch paths.

**AUD-004 remains release-blocking.** This document authorizes no runtime code, migration, configuration, cryptographic/key change, trust entry, partner onboarding, pilot, production patient-data access, merge, deployment, release or emergency federation.
