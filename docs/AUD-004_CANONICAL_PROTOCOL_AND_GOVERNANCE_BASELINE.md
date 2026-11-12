# AUD-004 Canonical Protocol and Governance Baseline

**Status:** Proposed canonical design baseline — NOT APPROVED FOR IMPLEMENTATION  
**Finding:** AUD-004 — federation authenticates a hospital/node but does not independently verify and authorize the human clinician requesting patient information.  
**Review scope:** PRs #20–#39 and the federated-import recovery design in PRs #23/#24.  
**Disposition:** AUD-004 remains a release blocker. This document consolidates design intent; it is not a protocol freeze, governance approval, runtime control, or release authorization.

## 1. Purpose and document authority

This document is the proposed single reconciliation point for the AUD-004 design work. It consolidates the clinician assertion proposal, route inventory, governance decision pack, import recovery contract, protocol specification, adversarial review, and ADV-01 through ADV-12 resolution proposals.

It is intended to prevent individual proposal documents from being interpreted as independently approved or as competing protocol specifications.

**Proposed document hierarchy:**

1. This baseline is the canonical cross-document design and decision-status register once independently reviewed.
2. The detailed documents listed in Section 15 remain supporting design evidence and retain their detailed tests, threat analysis, and implementation notes.
3. Runtime code and existing behavior are authoritative only for what is currently implemented; design text does not prove enforcement.
4. A governance decision is approved only when its required approvers and evidence are recorded in the decision register. A proposed default, project direction, green CI result, or draft PR is not approval.

This baseline itself remains proposed until the required reviewers accept it. Any conflict discovered between this baseline, supporting documents, and runtime behavior must be recorded and resolved before implementation.

## 2. Scope and non-negotiable invariants

### 2.1 Included scope

- Cross-hospital federation discovery and patient import.
- Local cross-branch/cross-tenant discovery and import where one branch accesses another branch's patient record. Project direction D-11 is YES; formal governance approval remains pending.
- Source-side selector resolution, candidate matching, demographic/allergy disclosure, resource handles, transfer artifacts, and import recovery.
- Synchronous, asynchronous, internal, background, administrative, support, retry, and recovery paths that access another branch's patient data.
- Destination provenance, source pointer/index synchronization, acknowledgement, revocation, audit, and operator reconciliation.

Ordinary same-branch patient CRUD is outside AUD-004 unless it crosses the branch/source boundary described above.

### 2.2 Non-negotiable invariants

1. A node credential authenticates a service/node; it does not authenticate a clinician.
2. A destination-issued clinician assertion is an identity statement, not source authorization.
3. Source authorization is performed by the authority that owns the source patient record and policy.
4. No patient-specific selector query, candidate existence signal, source record read, handle, summary, or payload disclosure occurs before durable source authorization for that exact operation.
5. Discovery search authorization and candidate/resource authorization are separate decisions.
6. A discovery receipt, handle, manifest, operation ID, or idempotency key is not a substitute for current authorization.
7. A retry that performs a new source read requires fresh source authorization and a new source audit event.
8. Local cross-branch access must use the same logical source authorization boundary as remote federation. Shared deployment, superuser role, or common ownership is not a bypass.
9. Purpose, action, resource, destination, and data scope are versioned, canonical, exact, and deny-by-default. No wildcard, alias escalation, or silent downgrade.
10. Source authorization, discovery response integrity/delivery, destination commit, acknowledgement verification, and pointer synchronization are distinct lifecycle facts.
11. No distributed atomic transaction is assumed across source, destination, and control-plane databases.
12. Demographic similarity, phone+DOB+name, ABHA equality, or a caller-supplied selector hash is not proof of source provenance or exact retry identity.
13. Mandatory audit failure blocks the protected action or leaves it pending; ordinary logs and asynchronous best-effort telemetry are not substitutes.
14. Uncertain outcomes remain explicitly uncertain. No synthetic success, false failure, or force-completion.
15. Emergency/break-glass federation remains disabled and is not included in initial enabled behavior.

## 3. Trust boundaries and authority ownership

| Boundary / fact | Authority that owns it | What another component must not assume |
|---|---|---|
| Human authentication and local session | Destination hospital identity system | A node API key or caller-supplied user ID proves the clinician |
| Clinician issuer subject and local affiliation | Destination issuer for its signed statement; source-approved mapping for acceptance | A signed assertion alone proves professional licensure or source authorization |
| Issuer and signing-key trust | Source-approved trust governance / trust registry | A token header, arbitrary JWKS URL, or destination self-registration establishes trust |
| Source clinician mapping, status and authorization | Source tenant and its approved identity/policy authorities | Destination RBAC or source-independent role labels grant source access |
| Source patient identity, selector resolution and privacy policy | Source tenant | Global index, coordinator, or destination may disclose candidate existence |
| Response artifact and resource handle | Source tenant | A handle is a bearer capability or grants a new source read |
| Destination import, clone, provenance and commit marker | Destination tenant | Source or control plane can assert destination commit without destination evidence |
| Destination commit acknowledgement | Destination-approved attestor and trust relationship; verified by source | An HTTP response or unsigned callback proves commit |
| Pointer/index publication | Owning index/control-plane service, under current policy | Destination commit or acknowledgement implies pointer sync |
| Audit event authorship | System of record that observed the event | Another service/operator may synthesize source authorization or destination commit facts |
| Operator reconciliation | Explicitly authorized dual-control workflow | Operator action replaces clinician authorization, provenance, or missing evidence |

## 4. Canonical protocol lifecycle

The protocol has three separate lifecycles. They correlate through immutable operation identifiers and evidence references, but must not be collapsed into one state machine.

### 4.1 Lifecycle A — source clinician authorization and disclosure

**Proposed logical sequence:**

1. Authenticate the federation node and verify its active source-approved relationship to the requesting branch and destination.
2. Apply coarse abuse controls and validate request syntax without performing patient-specific lookup.
3. Allocate or retrieve a bounded source challenge bound to the authenticated node, destination, protocol version, action, purpose, selector type/commitment, requested scope, request identity, and expiry.
4. Verify the destination-signed clinician assertion against the source trust registry: issuer, key, signature, token type/version, audience, time, destination, actor subject, action, purpose, challenge, and exact scope.
5. Resolve the issuer-scoped clinician subject through a source-controlled mapping. Check required identity proofing, current affiliation, clinician class, credential/status freshness, and revocation.
6. Durably authorize the bounded `DISCOVERY_SEARCH` operation before selector resolution. Bind the grant to actor, issuer, audience, destination, action, purpose, canonical selector request/commitment, budget, scope, protocol version, and expiry.
7. Resolve the selector only within that authorized search grant and budget. Do not return raw selector values, candidate counts, topology, or distinguishable no-match/denied outcomes.
8. For each candidate, perform a separate source-side authorization decision against the exact source resource, actor, destination, purpose, action, policy, and minimum data scope.
9. Durably record the disclosure decision/intent before serializing or releasing protected patient data.
10. Produce the approved minimum response and source-authenticated integrity manifest/receipt. Record delivery attempts and outcomes truthfully.
11. For a later import, run a distinct import authorization flow bound to the exact source pointer, destination, actor, action, purpose, and scope. Discovery authorization is not import authorization.

**Critical rule:** no patient-specific query may occur between steps 2 and 6. If challenge, actor verification, search authorization, audit, rate limiter, policy, identity mapping, or required status dependency is unavailable or stale, fail closed without querying the selector.

### 4.2 Lifecycle B — discovery response integrity and delivery

- A discovery receipt proves only the integrity/completeness and binding facts explicitly represented by its validated protocol contract. It does not grant clinician authority or authorize a source read.
- A resource handle is an opaque locator, not a bearer capability. Redemption requires recipient binding, atomic replay checks, current source trust/status/policy checks, and fresh source authorization for any new read.
- The source-authenticated manifest binds the exact source, destination, actor/request context, operation, protocol version, resource reference, purpose, scope, payload digest, and expiry/replay policy.
- Destination verification must reject malformed, non-canonical, mismatched, substituted, stale, replayed, or untrusted artifacts.
- Network send is not proof of delivery. Delivery is confirmed only by the evidence defined in the approved protocol; otherwise use an explicit uncertain outcome.
- Lost-response behavior is governed by the Strategy A/B decision in Section 9. Do not invent a global replay default.

### 4.3 Lifecycle C — destination import and recovery

The destination import is a durable cross-database workflow, not a distributed transaction.

**Required invariants:**

- Import identity is derived server-side from validated source pointer, source branch, destination branch, and protocol/version. It is not derived from demographics.
- A durable unique operation claim prevents concurrent duplicate imports.
- Destination patient/allergy rows, durable provenance, and a correlation/operation marker commit atomically in the destination database.
- Retries locate the exact clone through the durable marker/provenance, never by silently reusing a demographic match.
- Pointer/index synchronization is a separate recoverable step. A committed clone with unsynchronized pointer is not COMPLETED.
- State transitions use monotonic versions, compare-and-swap, unique constraints, leases, and fencing generations. Every side-effect boundary enforces fencing; checking only at worker start is insufficient.
- Destination acknowledgement is created only from re-read durable commit evidence and is bound to the exact operation, provenance/payload digest, destination branch, protocol, and fencing generation.
- Acknowledgement verification proves only the destination commit claim. It does not prove source authorization, clinical correctness, or pointer synchronization.
- Post-commit source-policy revocation enters the governed restricted/quarantine path. It does not cause automatic ordinary use, silent deletion, or pointer publication.
- Control-plane state is reconciled from destination evidence where destination owns the commit fact; absence of a control-plane row is not proof that no commit occurred.

Illustrative destination states (not yet a frozen API contract):

`CLAIMED → SOURCE_VALIDATED → DESTINATION_COMMITTED → COMMITTED_ACK_PENDING → ACK_SIGNED → ACK_DELIVERY_PENDING → ACK_RECEIVED_UNVERIFIED → ACK_VERIFIED → INDEX_SYNC_PENDING → COMPLETED`

Other explicit outcomes include `REJECTED`, `FAILED_RETRYABLE`, `OUTCOME_UNCERTAIN`, `RECONCILIATION_REQUIRED`, and `SOURCE_ACCESS_REVOKED_AFTER_COMMIT` (restricted/quarantined). Exact vocabulary and transition semantics require approval.

## 5. ADV-01 through ADV-12 consolidated requirements

| Finding | Canonical requirement | Minimum evidence before closure |
|---|---|---|
| ADV-01 — search authorization | Durable bounded source `DISCOVERY_SEARCH` authorization before any patient-specific selector query; separate candidate authorization before disclosure; anti-enumeration | Source query-order tests, audit transaction tests, denial/no-match indistinguishability tests, budget/concurrency tests |
| ADV-02 — clinician identity | Source-approved issuer-scoped subject mapping, independent proofing/credential policy, current affiliation/status, dual-control trust enrollment and revocation | Identity governance evidence, mapping lifecycle tests, issuer compromise and revocation tests |
| ADV-03 — challenge abuse | Node/relationship validation before allocation; layered distributed budgets; bounded challenge state; idempotency and overload behavior | Distributed rate-limit tests, storage exhaustion tests, dependency outage and abuse simulations |
| ADV-04 — audit/disclosure boundary | Distinct authorization, disclosure intent, artifact, delivery, acknowledgement and uncertain-outcome evidence; approved Strategy A/B replay policy | Transaction/fault-injection tests at every boundary; no false delivery/commit claims |
| ADV-05 — revocation races | Authority-owned revocation domains and freshness checkpoints; rotation differs from compromise; explicit in-flight and post-commit behavior | Deterministic revocation race tests, freshness and propagation evidence, quarantine workflow tests |
| ADV-06 — handles/manifests | Opaque recipient-bound non-bearer handles; fresh authorization at redemption; canonical signed manifest; atomic replay protection | Substitution, replay, recipient mismatch, canonicalization and handle-expiry tests |
| ADV-07 — source boundary | One source-owned authorization interface across remote, local, internal, background, admin, support, retry and recovery paths; no direct bypass | Complete route/call-path inventory, repository/DB-role enforcement, alias parity and bypass tests |
| ADV-08 — purpose/scope | Versioned source-governed action/purpose/resource/data-category/scope registry; deny unknown, deprecated, ambiguous, wildcard or downgraded values | Registry compatibility, downgrade, alias and negative authorization tests |
| ADV-09 — selector privacy | Prefer bounded source-directed fan-out; no global patient selector index by default; any exception requires measured need and keyed domain-separated privacy controls | Threat model, measured performance evidence, enumeration/correlation and key-compromise tests |
| ADV-10 — destination acknowledgement | Destination-owned post-commit attestation tied to durable provenance, exact operation/digest, branch trust and fencing; separate pointer sync | Independent-session commit/ack tests, tamper/replay/key rotation/stale-worker tests |
| ADV-11 — audit integrity/privacy | Separate source security audit, destination import audit, control-plane trust audit, operational telemetry and clinical provenance; authoritative authorship, integrity, privacy and governance | Independent tamper-evidence design, access/retention/residency approval, audit outage/tamper/restore tests |
| ADV-12 — failure/recovery | Complete lifecycle state/failure/retry-authority matrix; owning authority retries only; dual-control operator reconciliation; no synthetic success | Deterministic failure injection at every durable boundary, PostgreSQL multi-session/process tests, runbook and reconciliation tests |

## 6. Selector routing and privacy decision

**Proposed default:** bounded source-directed fan-out, with each source authorizing the search before resolving its selector. Do not create or retain a global deterministic patient-selector index merely for convenience.

A routing coordinator may route opaque requests to eligible sources but must not decide source authorization or expose patient existence, candidate counts, patient names, MRNs, demographics, branch-level match outcomes, or source policy decisions.

A central index is an exception, not the default. It may be reconsidered only if measured partner count, latency, availability, cost, and source-search budgets show that bounded fan-out cannot meet an approved service objective. Any exception requires a separate privacy/security threat model, keyed domain-separated tokens, isolated key custody, anti-enumeration, strict service identity, rotation/compromise controls, data minimization, and governance approval. Plain or globally deterministic hashes of low-entropy selectors are prohibited.

Topology, fan-out budgets, eligible-source discovery, and any index exception remain open governance/architecture decisions.

## 7. Source authorization boundary and canonical vocabulary

All access paths that resolve or read another branch's patient data must call the same logical source-owned authorization interface. Remote and local adapters may differ in transport, but not in authorization semantics.

The interface must support distinct decisions for:
- bounded discovery-search authorization;
- candidate/resource authorization;
- import authorization;
- response artifact retrieval/replay;
- any new source read during retry/recovery.

The source-owned versioned registry must define exact action, purpose, resource type, data categories, scope, actor class, destination constraints, and compatibility rules. Unknown, deprecated, ambiguous, aliased, wildcard, unsupported-version, or downgraded values are denied. No free-form caller purpose string is an authorization policy.

Same-branch ordinary CRUD remains outside this boundary. A local cross-branch request is not same-branch CRUD and must not bypass the source interface.

## 8. Clinician identity, issuer and key trust

The signed assertion is a transportable, short-lived statement from a source-approved issuer. It must contain an immutable issuer-scoped clinician subject and exact request bindings; it must not contain unnecessary PHI.

The source validates:
- exact registered issuer and permitted node/branch relationship;
- configured key ID and algorithm within that issuer's approved key set;
- signature, token type/version, audience, time claims and strict parsing;
- immutable issuer-scoped subject and source-controlled clinician mapping;
- current affiliation, actor class, credential/licensure status where required, and freshness;
- exact challenge, action, purpose, resource/selector commitment, destination and minimum scope;
- atomic challenge and assertion replay consumption.

Destination-side authentication/authorization is necessary but not sufficient. Destination RBAC does not replace source policy. A hospital assertion that someone is a doctor is only as strong as the formally accepted identity/credential authority and proofing process. Tenant-entered profile fields alone are not independent registry verification.

Per-branch issuer keys and the participating hospital's own Avinya tenant backend as an issuer are engineering proposals, not approved choices. No algorithm, KMS/HSM provider, key custody, issuer onboarding, credential registry, MFA level, assertion TTL, clock skew, or revocation SLA is frozen here.

Trust creation, key replacement, suspension and reactivation require out-of-band verified enrollment, dual approval, immutable trust audit, and explicit revocation/compromise handling.

## 9. Response retry strategy and revocation policy

Two mutually exclusive response retry strategies remain under consideration and may be selected per action/data category only after governance review.

| Strategy | Retry behavior | Security/privacy trade-off |
|---|---|---|
| **A — immutable response artifact** | Persist a recipient-bound encrypted immutable artifact and, when policy permits, resend the exact committed bytes. Never reconstruct or mutate the payload from stale in-memory data. | Improves exact replay and avoids rereading changed source data, but creates retained PHI/artifact encryption, access, expiry, revocation, backup, and disposal obligations. |
| **B — fresh authorization and read** | Do not retain a replayable PHI artifact. A retry that needs data obtains fresh challenge/assertion/search/candidate authorization and performs a new source read with a new audit event. | Reduces retained PHI artifacts, but can return changed data and increases dependency on current source availability and authorization. |

No global Strategy A or B default is approved. A network timeout does not establish whether bytes were received. If delivery cannot be proven, preserve `OUTCOME_UNCERTAIN`; do not claim delivery or non-delivery.

Revocation is owned by the authority that owns the revoked fact: source tenant for source clinician mapping, affiliation, patient policy and authorization; trust authority for issuer/key; destination for destination session and local commit permissions. Missing, stale, contradictory, or unavailable status beyond an approved freshness bound fails closed or enters an explicit restricted/uncertain state.

A revocation cannot recall bytes already disclosed. It must block new work and further retrieval/replay as governed, preserve accurate audit evidence, and apply approved quarantine/retention behavior to any committed clone. Post-commit retention/deletion and clinical continuity decisions require privacy/legal and clinical governance.

## 10. Audit evidence, integrity and privacy

Maintain distinct evidence domains with separate ownership, access, retention, export and disposal policies:

1. **Source security audit:** node trust, actor verification, search authorization, selector resolution, candidate authorization, disclosure intent, artifact/retrieval, source policy and revocation.
2. **Destination import audit:** destination authorization, artifact validation, operation claim, provenance, clone commit, acknowledgement and recovery.
3. **Control-plane trust audit:** issuer/node/branch trust enrollment, key lifecycle, partner status and administrative changes.
4. **Operational telemetry:** availability, latency, capacity, bounded dependency/error categories and safe correlation IDs; no PHI, raw selectors, assertions, handles or stable cross-tenant tokens.
5. **Clinical record/provenance:** clinical content and lineage, not a substitute for general security audit.

Each event is authored by the authority that observed the fact. Events use a versioned envelope, stable event and correlation identifiers, trusted time/ordering evidence, actor/service identity, action, decision, outcome, policy/protocol version, and minimized resource reference as appropriate. Operators may emit attributed administrative events but may not synthesize source authorization or destination commit facts.

A hash chain stored only in the same mutable database is not sufficient against an administrator able to rewrite both records and chain. The independent tamper-evidence boundary, storage provider, cryptographic profile, trusted time source, backup topology and integrity-verification process require security/platform review.

Mandatory audit events must commit before their protected action. If audit persistence or required integrity verification fails, deny the protected action or leave it pending. Do not substitute ordinary application logs, best-effort asynchronous events, in-memory queues, or caller-supplied claims.

Do not put raw selectors, patient name, DOB, phone, ABHA, MRN, clinical narrative, payload bytes, bearer handles, assertions, credentials, private keys, database schema names or raw exception traces in ordinary audit metadata. Use purpose-scoped opaque references with restricted resolution. Define reader roles, export approvals, correction as append-only events, legal hold, residency, backup expiry and disposal per evidence class.

No retention period, legal basis, audit-reader role, residency region or disposal schedule is approved by this document.

## 11. Canonical state and retry authority rules

Every state transition must identify: owning authority, immutable operation tuple, current state/version, evidence required, allowed actor, permitted side effect, mandatory audit event, and safe outcome if evidence is incomplete.

**Retry authority:**
- Source service owns source challenge, actor verification, search/candidate/import authorization, source reads, source audit and artifact lifecycle.
- Destination service owns destination operation claims, validation, clone/provenance commit, destination acknowledgement and destination recovery.
- Control-plane/index service owns its own trust/index/pointer state, but cannot invent source authorization or destination commit evidence.
- Operator reconciliation is a separate privileged workflow with read-only evidence inspection separated from state-changing actions, named operators, case reference, expiry, explicit scope and dual approval for high-impact or ambiguous transitions.

**Forbidden recovery shortcuts:**
- Reusing an expired receipt/handle to authorize a new source read.
- Treating an operation ID or idempotency key as authorization.
- Reusing demographic/ABHA matches as proof of exact source provenance.
- Retrying a destination insert when commit outcome is uncertain without first reconciling the durable marker.
- Letting a stale worker commit, sign, deliver, or publish after a newer fencing generation.
- Treating a signed acknowledgement as proof of pointer synchronization.
- Automatically deleting or activating a clone after post-commit revocation.
- Operator force-success, ignore-audit, skip-source-check, recreate-provenance, or publish-pointer-anyway controls.

If durable evidence is missing or contradictory, stop in an uncertain/reconciliation/restricted state. Do not infer success or failure from the absence of a row in another database.

## 12. PR #19 runtime remediation dependency

The AUD-004 design does not close the separate remaining PR #19 runtime risks. Before implementation or release, they must be resolved and independently tested:

1. **Concurrent duplicate import:** concurrent imports can race existing-patient lookup; ABHA uniqueness conflicts and demographic fallback behavior must not produce duplicate or unhandled outcomes. Enforce durable operation idempotency and PostgreSQL concurrency safety.
2. **Pointer recovery after destination commit:** destination patient/allergy commit can succeed before pointer synchronization. A retry must locate the exact durable clone and reconcile pointer sync without returning early or creating a second clone. Do not report COMPLETED until pointer synchronization is proven.
3. **Demographic/ABHA reuse:** matching ABHA or phone+DOB+name must not silently reuse a patient as though it were the exact source record. Provenance and exact source pointer identity govern retry identity.

These are implementation dependencies, not merely documentation cleanup. PR #19 remains unmerged and must be independently reviewed with the AUD-004 work before any release decision.

## 13. Governance decision register D-01 through D-14

**Status rule:** all decisions below are formally PENDING unless the approval record includes accountable approver identity, organization, role, date, governance reference, evidence, exact scope, residual risk, compensating controls, expiry/review date and disable conditions. Proposed defaults are recommendations only.

| ID | Decision requiring approval | Proposed direction for review | Formal status |
|---|---|---|---|
| D-01 | Who may issue clinician assertions and represent a hospital? | Participating hospital-managed issuer, with distinct registered issuer/key per branch as a candidate model | PENDING |
| D-02 | Required authentication assurance | Active authenticated user and live session; MFA/high assurance for high-risk actions subject to IAM decision | PENDING |
| D-03 | Permitted clinician classes | Explicit clinician-class allow-list with action-specific scopes; no generic staff wildcard | PENDING |
| D-04 | Professional registration/licensure | Approved authoritative registry or documented credential-verification process with freshness/expiry/revocation evidence | PENDING |
| D-05 | Source patient authorization | Source independently authorizes exact actor, action, purpose, resource, destination and minimum scope | PENDING |
| D-06 | Purpose/action vocabulary | Versioned closed registry and source-owned matrix; no initial emergency/break-glass purpose | PENDING |
| D-07 | Signing algorithm and key custody | Per-branch asymmetric key in approved managed KMS/HSM; Ed25519/ES256 remain candidates only | PENDING |
| D-08 | Issuer/partner/key onboarding | Out-of-band verification, dual approval, audit and lifecycle controls | PENDING |
| D-09 | Assertion/challenge lifetime and revocation freshness | Short-lived credentials and online status checks; numeric TTL, skew and SLA require approval | PENDING |
| D-10 | Replay, retry and distributed outcomes | Atomic durable replay claims, distinct discovery/import authority, stable operation identity and explicit uncertainty | PENDING |
| D-11 | Local cross-branch imports in scope? | **Project direction YES**; include local cross-branch/cross-tenant imports; same-branch CRUD excluded | **PENDING — formal governance approval** |
| D-12 | Audit content, integrity, retention and access | Separate evidence domains, minimized PHI, tamper evidence and approved per-class retention/access | PENDING |
| D-13 | Emergency/break-glass | NO for initial enabled release; keep emergency federation disabled; separate future design/approval | PENDING |
| D-14 | Pilot and production release | Final non-preapprovable gate after all decisions, evidence, independent reviews and named release approval | PENDING — final gate |

D-11 records the user's project direction and does not substitute for formal product, clinical governance, or privacy/legal approval. Engineering must continue to design for local cross-branch protection and must not implement a weaker local bypass while approval is pending.

## 14. Contradiction and resolution register

| Topic | Earlier ambiguity or conflict | Canonical reconciliation | Remaining decision |
|---|---|---|---|
| Discovery receipt | Receipt could be mistaken for actor authorization | Receipt is integrity/completeness evidence only; source clinician authorization is separate | Exact receipt claims and expiry |
| Selector query order | Earlier challenge designs allowed selector resolution as part of challenge bootstrap | Durable source `DISCOVERY_SEARCH` authorization must precede patient-specific query | Challenge protocol details and budgets |
| Candidate authorization | Search authorization alone could be read as permission to disclose all matches | Each candidate/resource requires separate source authorization before existence/details are disclosed | Candidate cardinality and matching policy |
| Clinician proof | Destination signature could be mistaken for independent proof of licensure | Source-approved issuer mapping and proofing; signature alone is insufficient | Issuer/registry model and freshness |
| Local vs remote | Local access might bypass federation controls | Same logical source authorization interface for all cross-branch paths | Adapter and database enforcement design |
| Routing topology | Global index and fan-out proposals differed | Bounded source-directed fan-out is preferred default; index only by justified exception | Measured topology and performance decision |
| Response retry | Immutable artifact replay and fresh-read retry both proposed | Strategy A/B remains an explicit per-action/data-category governance choice | Strategy, artifact retention and revocation policy |
| Revocation | In-flight delivery and post-commit revocation are not atomic | Block new work; record uncertainty; restrict/quarantine committed clone under approved policy | Freshness SLA and quarantine/retention owner |
| Handles/manifests | Handle could act as bearer access | Opaque locator only; recipient binding and fresh authorization on redemption | Canonical schema and cryptographic profile |
| Import recovery | Source, destination and control plane could appear to share one state | Separate authority-owned lifecycles; destination provenance is commit evidence; pointer sync remains separate | Final state/API vocabulary |
| Acknowledgement | HTTP success or destination ack could imply full completion | Ack proves only exact destination commit; pointer sync separately verified | Attestor trust, keys and signing custody |
| Audit | One generic audit/log stream could mix facts and PHI | Separate evidence domains, authoritative event authorship, independent tamper evidence | Roles, retention, residency, storage and legal basis |
| Retry authority | Generic retry/operator override could bypass source controls | Owning authority retries only; new source read requires fresh authorization; operator dual control | Numeric operational policy and runbooks |
| PR #19 matching | Demographic match could be treated as exact source identity | Exact pointer/provenance and durable marker govern identity; demographics are not proof | Runtime remediation and tests |

No unresolved item may be resolved by silently weakening a stricter invariant in another proposal.

## 15. Supporting documents consolidated

The following open draft PRs remain supporting evidence; their existence does not mean they are merged or approved:

- PR #20 — signed clinician actor assertion design.
- PR #21 — federation route-surface review.
- PR #22 — D-01–D-14 governance decision pack.
- PRs #23/#24 — federated import idempotency, provenance, fencing and recovery.
- PR #25/#26 — D-11 local cross-branch scope direction and decision-register update.
- PR #27 — governance decision review checklist.
- PR #28 — technical implementation blueprint.
- PR #30 — protocol security clarifications.
- PR #31 — cross-document consistency review.
- PR #32 — consolidated protocol architecture and sequences.
- PR #33 — independent adversarial security review.
- PR #34 — ADV-01/ADV-02 resolution proposal.
- PR #35 — ADV-03/ADV-04 resolution proposal.
- PR #36 — ADV-05/ADV-06 resolution proposal.
- PR #37 — ADV-07/ADV-08 resolution proposal.
- PR #38 — ADV-09/ADV-10 resolution proposal.
- PR #39 — ADV-11/ADV-12 resolution proposal.

The supporting documents should be cross-linked from the repository's AUD-004 index once the maintainers decide how to maintain the canonical baseline. Do not delete or silently rewrite the detailed evidence during this consolidation.

## 16. Independent review checklist before runtime implementation

### Protocol and identity
- [ ] Security architecture approves the three-lifecycle model and trust boundaries.
- [ ] Source search authorization is proven to commit before every patient-specific query across all access paths.
- [ ] Candidate authorization and disclosure audit are proven before any candidate existence signal or payload.
- [ ] Identity proofing, issuer-scoped subject mapping, clinician classes, credential sources and revocation ownership are approved.
- [ ] Challenge, assertion, receipt, handle, manifest and operation identity have distinct authority and lifetime semantics.
- [ ] Canonical purpose/action/resource/scope registry and compatibility policy are approved.

### Privacy, topology and revocation
- [ ] Selector routing topology is selected using measured evidence and approved threat model.
- [ ] No raw/global deterministic selector hash or unapproved patient index is used.
- [ ] Strategy A/B is selected per action/data category with retention, encryption, replay and revocation behavior.
- [ ] Freshness checkpoints, propagation SLA, key compromise and post-commit quarantine are approved.
- [ ] Local cross-branch paths are proven to use the same source-owned authorization boundary.

### Audit and recovery
- [ ] Audit evidence domains, event authorship, independent tamper evidence, trusted time/order and integrity verification are approved.
- [ ] Reader roles, export, correction, retention, residency, legal hold, backup expiry and disposal are approved.
- [ ] Every durable lifecycle boundary has deterministic failure-injection coverage and a named retry authority.
- [ ] PostgreSQL independent-session/process tests prove uniqueness, CAS, fencing, outbox and recovery behavior.
- [ ] Destination acknowledgement proves only exact durable commit and cannot be forged, replayed, downgraded or confused with pointer sync.
- [ ] Operator reconciliation is dual-control, evidence-based and has no force-success or bypass controls.

### Runtime and release
- [ ] PR #19 concurrent-import, pointer-recovery and demographic-reuse defects are resolved and independently reviewed.
- [ ] Root and versioned route aliases, background/admin/support/recovery paths and direct repository/DB access are covered.
- [ ] Negative, concurrency, privacy, audit, revocation, restore, retention, and fault-injection suites pass on PostgreSQL.
- [ ] Independent security, privacy/legal and clinical-safety reviews record findings and residual-risk decisions.
- [ ] D-01–D-14 have valid approval records; D-14 is decided only at the final gate.
- [ ] Explicit implementation authorization is recorded before runtime changes.
- [ ] Explicit pilot and production release approval is recorded separately after non-production validation.

## 17. Implementation phases and stop conditions

**Phase 0 — governance and protocol closure:** resolve D-01–D-13, reconcile this baseline and supporting documents, approve threat models, identity/credential sources, purpose/scope registry, routing, replay strategy, audit governance, retention/residency and operational ownership.

**Phase 1 — isolated trust and identity foundation:** only after Phase 0 authorization; implement approved issuer/clinician mapping, key custody, status freshness and dual-control trust lifecycle behind disabled feature flags.

**Phase 2 — source authorization boundary:** implement challenge/replay, pre-query search authorization, candidate authorization, local/remote adapters, mandatory audit and deny-by-default scope validation.

**Phase 3 — response and import lifecycle:** implement approved artifact strategy, manifest/handle integrity, destination idempotency/provenance, commit attestation, fencing, pointer reconciliation and quarantine.

**Phase 4 — non-production validation:** independent security testing, PostgreSQL concurrency/fault injection, partner interoperability, privacy review, operational runbooks, monitoring, restore and rollback validation.

**Phase 5 — final pilot/release gate:** D-14 remains a final decision. No pilot or production operation is authorized by completion of earlier phases or by passing CI.

Stop immediately on missing/stale trust, identity, status, policy, audit or integrity evidence; unapproved purpose/scope; unknown state; conflicting provenance; stale fencing; unverified acknowledgement; pointer mismatch; or unresolved clinical/privacy/security risk. Preserve evidence and leave the operation denied, pending, uncertain, or quarantined as appropriate.

## 18. Explicit non-authorization

This baseline authorizes **no** runtime code change, migration, configuration change, database-role change, cryptographic/key creation or rotation, trust entry, partner onboarding, production patient-data access, local or remote pilot, emergency/break-glass enablement, merge, deployment, release, or production operation.

All PRs in this design series remain open/draft/unmerged unless separately changed through an explicitly authorized review process. AUD-004 remains release-blocking until approved governance decisions, verified runtime enforcement, independent evidence, and final release approval are complete.
