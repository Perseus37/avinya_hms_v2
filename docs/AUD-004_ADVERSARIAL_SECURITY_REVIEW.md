# AUD-004 Independent Adversarial Security Review

**Status:** DESIGN REVIEW FINDINGS — NO IMPLEMENTATION AUTHORIZATION  
**Reviewed baseline:** PR #32 consolidated protocol specification, with referenced PR #19 runtime behavior and PRs #23/#24 recovery design.  
**Method:** Structured adversarial reasoning. This is not a penetration test, cryptographic validation, code execution, clinical safety assessment or formal approval.

## 1. Executive result

PR #32 is materially clearer, but it is not yet safe to freeze as an implementation contract. This review identifies two critical protocol ambiguities and ten additional high-risk attack surfaces.

Most important: the specification requires clinician verification before selector resolution, then candidate-specific authorization. It does not define a distinct source-authorized search permission that permits the selector query while preventing that query from becoming a patient-existence oracle. Candidate-level authorization cannot occur until candidates have been resolved. The protocol needs two explicit authorization stages: bounded search authorization before patient-specific resolution, and resource-specific authorization before any candidate detail or handle is disclosed.

No runtime change is proposed.

## 2. Findings

### ADV-01 — Search authorization is not defined separately from candidate authorization
**Severity: Critical — release blocker**

A source cannot evaluate candidate-specific authorization before internally resolving a candidate. Simply allowing any authenticated clinician to submit arbitrary selectors creates an enumeration oracle even if responses are normalized.

**Attack path:** A malicious or compromised clinician obtains a discovery assertion, then submits repeated ABHA/phone/name selectors or sequential values. Broad discovery permission permits candidate resolution. Timing, throttling, audit volume, handle issuance or retry behavior may reveal existence or enable harvesting.

**Required change**
- Define a distinct source-side DISCOVERY_SEARCH permission evaluated before the patient-specific query.
- Bind it to verified actor, issuer, source audience, destination, action, purpose, selector type, bounded query budget, allowed scope and expiry.
- Define approved selector types, normalization, minimum entropy, rate/volume budget and anti-enumeration controls.
- After internal resolution, apply separate candidate/resource authorization before returning any patient-specific result, source pointer, handle or summary.
- Decide whether discovery is exact-match only; disable broad/fuzzy search unless separately approved.
- Ensure query execution and response shaping expose no count or distinguishable per-candidate outcomes.

**Required tests:** no search scope; wrong purpose/destination; sequential selectors; high-volume low-entropy selectors; same actor across nodes; timing/body/status/size comparison; authorized search but denied candidate.

### ADV-02 — Destination issuer can assert a false clinician identity if source trusts claims without independent binding
**Severity: Critical — release blocker**

A valid signature proves who signed claims, not that the subject is a genuine clinician or that the issuer's session was not compromised. The source-side clinician mapping, identity evidence and affiliation authority are not fully specified.

**Attack paths:** compromised destination issuer signs assertions naming a privileged clinician; destination administrator maps an ordinary user to a clinician subject; stale mapping remains valid after revocation; subject identifier is reused after account deletion.

**Required change**
- Define source-approved clinician identity/affiliation proofing and authoritative evidence for each partner model.
- Use immutable issuer-scoped subject identifiers with non-reuse guarantees; define deletion, rehire and remapping.
- Separate issuer authentication from clinician credential/registration evidence and source authorization.
- Define source-controlled clinician mapping enrollment, dual approval, recertification and revocation.
- Specify whether source trusts issuer attestation, independent credential authority, or both; require assurance and evidence references.
- Define compromised issuer/key blast radius and emergency revocation.

**Required tests:** unknown subject with valid signature; subject reassignment; stale/revoked affiliation; issuer signs arbitrary user; compromised key; expired professional credential where required; issuer/mapping mismatch.

### ADV-03 — Challenge bootstrap may become an oracle or denial-of-service primitive
**Severity: High**

Uniform challenge responses do not prevent differences caused by routing, node status, challenge storage, policy, rate limits or selector recognition. Attackers may exhaust challenge rows or signing capacity without presenting assertions.

**Required change:** authenticate and rate-limit node before allocation; apply per-node/issuer/destination/global budgets; bound storage and cleanup; make duplicate requests idempotent or safely bounded; prevent challenge response differences based on patient existence or source match; define unavailable-source behavior without topology leakage.

### ADV-04 — Audit-before-disclosure transaction boundary is ambiguous
**Severity: High**

The design does not distinguish search authorization audit, candidate authorization audit, disclosure-intent audit, response artifact commit and network delivery. A database transaction cannot atomically commit with bytes delivered over a network.

**Required change:** define durable events and commit boundaries for each stage; commit search permission before query; authorize candidates before serialization; persist an appropriately protected response artifact before sending if exact retry is supported; otherwise require fresh authorization and do not promise replay. Model crashes and uncertain network outcomes explicitly as OUTCOME_UNCERTAIN.

### ADV-05 — Revocation race across source response and destination commit is unresolved
**Severity: High**

Clinician affiliation, issuer key, source policy or patient consent may be revoked between source authorization and destination commit.

**Required change:** define freshness checkpoints at challenge, assertion, query, response commit/retrieval and destination commit; distinguish revocation types; define whether committed response replay is allowed; define bounded authorization lease and post-commit restricted/quarantine handling. No deletion should be inferred.

### ADV-06 — Resource handles and response manifests may become transferable bearer capabilities
**Severity: High**

The design says handles are not bearer grants but lacks complete entropy, storage, recipient proof, revocation and leakage rules.

**Required change:** high-entropy opaque handles; hashed storage where feasible; recipient/actor/action/purpose/resource/scope binding; fresh assertion and policy evaluation on every use; no tokens in URLs/logs/referrers; canonical manifests with schema version, key ID, algorithm allowlist, audience, operation, digest and anti-replay; reject downgrade and cross-protocol substitution.

### ADV-07 — Global routing fan-out and local direct access are not enforceable by diagrams alone
**Severity: High**

Opaque fan-out and local adapters are alternatives, not a selected topology. A central router may enumerate candidate branches internally; local code may bypass the shared interface through direct ORM/session access.

**Required change:** select routing topology; document selector/candidate visibility; restrict and audit routing metadata; define one mandatory source authorization boundary for HTTP, internal calls, tasks, admin and local access; enforce architecture with narrow repository APIs/static dependency tests; inventory root/V1 aliases and background paths.

### ADV-08 — Purpose/scope downgrade and confused-deputy risks
**Severity: High**

Purpose and scope are bound but there is no strict canonical registry, data-category matrix or alias/default behavior.

**Required change:** version and govern purpose/action identifiers; reject unknown/deprecated aliases; define source-owned clinician-class × purpose × action × resource × data-category × destination matrix; no wildcard/default scope; discovery must not imply allergy detail; import independently authorized; reject protocol downgrade.

### ADV-09 — Cross-tenant selector correlation and index compromise risk
**Severity: High**

A deterministic keyed index can still become a cross-tenant correlation oracle if keys are shared broadly or query access is unrestricted.

**Required change:** decide whether index is necessary; if retained, use narrowly scoped keyed tokens with separated keys/contexts, rotation and access control; plan backfill, collision handling, dual-read migration and rollback; do not expose match count/branch identifiers; minimize selector/routing audit retention.

### ADV-10 — Import fencing and acknowledgement protocol has trust and stale-worker gaps
**Severity: High**

The destination acknowledgement requires a trust model and proof it was generated by the transaction-owning service after commit. Stale workers must not sign acknowledgements from stale in-memory state.

**Required change:** bind acknowledgement signing to destination identity and approved trust registry; include fencing generation and committed provenance digest; generate only after durable commit; source verifies current trust and operation state; same-operation duplicates idempotent, lower generation/different digest rejected; test key rotation/revocation and stale worker at each boundary.

### ADV-11 — Audit event design risks PHI/credential leakage or untrusted narrative
**Severity: High**

Audit fields may reveal patient access patterns. Schema, pseudonymization, partitioning, integrity, correction, retention and reader roles are not fully defined.

**Required change:** versioned source-generated events and trusted timestamps; separate patient-linked audit from operational telemetry; redact tokens/selectors/PHI; define append-only/tamper evidence, clock synchronization, retention/legal hold/export and auditor roles; prevent caller claims from creating success events.

### ADV-12 — Failure/recovery matrix is incomplete across three lifecycles
**Severity: High**

There is no exhaustive state × failure point × retry authority matrix.

**Required change:** for every transition define retry actor, required artifact, whether source read/destination write may repeat, expected audit and terminal/reconciliation state. Cover crashes between source audit, query, response commit, network send, destination claim, patient/provenance commit, acknowledgement signing/receipt and pointer sync. Define dual-control operator recovery. Expired authorization artifacts must never authorize a new read.

## 3. Required consolidated revisions before implementation

1. Add two-stage discovery authorization: bounded source-authorized search before selector resolution, then candidate-specific authorization before disclosure.
2. Specify independently verifiable clinician identity/affiliation binding and issuer compromise response.
3. Select routing topology and document selector/candidate visibility.
4. Define challenge, audit, disclosure and network-delivery transaction boundaries.
5. Define revocation timing and response replay policy.
6. Specify handle/manifest cryptographic and recipient binding requirements without choosing unapproved algorithms.
7. Specify a mandatory source access boundary for all remote/local/internal/background paths.
8. Define purpose/scope registry and no-downgrade behavior.
9. Define destination acknowledgement trust and fencing enforcement.
10. Publish full audit governance and cross-lifecycle failure/retry matrix.

## 4. Implementation stop conditions

Do not start runtime implementation until ADV-01 and ADV-02 are resolved with clinical/privacy/security reviewers; routing/index architecture is selected and threat-modelled; challenge/audit/disclosure/replay boundaries are specified; source/destination key trust and revocation are approved; the failure/retry matrix is reconciled with PRs #19/#23/#24; formal governance decisions and implementation authorization are recorded; and PostgreSQL concurrency/failure-injection plans are accepted.

This review does not authorize code, migrations, configuration, keys, trust entries, partner onboarding, pilot, production patient-data access, merge, deployment, release or emergency federation.

**AUD-004 remains release-blocking.**
