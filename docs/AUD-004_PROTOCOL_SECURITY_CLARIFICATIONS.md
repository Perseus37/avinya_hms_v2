# AUD-004 Protocol Security Clarifications

**Status:** PROPOSED — DESIGN ONLY — NOT AUTHORIZED FOR RUNTIME IMPLEMENTATION  
**Parent:** PR #28, technical implementation blueprint  
**Scope:** Resolve three blocking review findings: privacy-preserving discovery, challenge/assertion transaction and retry semantics, and source-to-destination transfer integrity.

This document supplements PR #28. It does not replace the governance decision register, freeze a cryptographic protocol, approve a production lifetime, or authorize runtime implementation. D-01–D-14 remain subject to their recorded approval status. D-07/D-08/D-09/D-10/D-12 are especially relevant below.

## 1. Non-negotiable invariants

1. No patient existence, match count, demographics, candidate-specific error, or patient-specific metadata is disclosed before source-side clinician verification and authorization.
2. A selector supplied by a destination is a search request, not proof of patient identity or authorization.
3. The source retains the canonical selector/resource binding. A caller-computed hash or opaque handle is never sufficient authorization by itself.
4. A challenge and assertion authorize one exact operation, destination, purpose, action and scope. Discovery and import are distinct operations.
5. Concurrent submissions cannot both perform the protected disclosure for the same one-time challenge/assertion operation.
6. Required source audit is durably committed before protected response bytes are released.
7. A retry after a lost response may retrieve only the previously committed outcome for the same operation and recipient. It must not repeat the source read or create a new disclosure.
8. Source authorization, response integrity, destination commit and pointer publication are separate auditable stages. No stage implies a later stage succeeded.
9. Import recovery and fencing must use the accepted protocol contract from PRs #23/#24 if those designs are approved; this document does not invent a parallel import state machine.
10. No runtime implementation until governance and independent security review gates are satisfied.

## 2. Privacy-preserving discovery protocol

### 2.1 Challenge bootstrap

The destination first authenticates as a registered federation node. It submits:
- protocol version;
- source-recognized destination node/branch identity;
- action = discovery;
- versioned purpose identifier;
- selector type;
- canonical selector payload over the authenticated channel;
- requested minimum data scope;
- a destination-generated request/operation correlation identifier.

The source validates the node relationship and syntax, canonicalizes the selector itself, and stores the canonical selector and its keyed digest in a short-lived challenge record. It does not return whether the selector matches any patient. The challenge response has a fixed schema and does not include match count, patient ID, MRN, demographics, candidate-specific status or distinguishable per-candidate errors.

The selector canonicalization algorithm and any keyed-digest construction are protocol-versioned and require security review. The destination must not be trusted to compute the canonical value. The source must not expose a plain hash of low-entropy identifiers that enables offline guessing.

### 2.2 Clinician assertion binding

The destination issuer validates the currently authenticated local clinician and issues an assertion bound to the source challenge. The assertion binds at least:
- issuer and issuer-scoped clinician subject;
- actor type and approved clinician classification reference;
- challenge identifier and protocol version;
- authenticated destination node and exact destination branch;
- action = discovery;
- purpose;
- source audience;
- selector type and source challenge binding;
- requested scope;
- issue/not-before/expiry times and unique jti.

The source verifies the signature and trust chain, then compares every claim with the source-stored challenge. No caller-provided subject, role, branch, purpose, scope or destination is authoritative.

### 2.3 Source-side resolution and authorization

Only after assertion verification and current clinician/affiliation checks does the source resolve the stored canonical selector against its own patient records.

For each candidate internally resolved:
1. Evaluate source-side authorization for the verified clinician, exact action/purpose, exact candidate resource, exact destination and requested scope.
2. Evaluate current patient privacy/data-use restrictions and source policy.
3. Record the candidate decision without exposing candidate existence to an unauthorized requester.
4. Create a random opaque resource handle only for an authorized candidate. The handle is bound server-side to source tenant/branch, source pointer/resource identity and version, requesting node, clinician/issuer context, destination, action, purpose, scope, protocol version and expiry.

The source never returns a handle for a denied candidate. A handle is a reference to a source-held authorization context, not a bearer authorization token; every later use requires fresh action-specific authorization.

### 2.4 Observable behavior and enumeration controls

The source must use a common external outcome class and response shape for:
- no matching candidate;
- candidate exists but clinician is not authorized;
- candidate is suppressed by privacy policy;
- ambiguous/multiple candidates requiring reconciliation;
- expired, unknown or substituted resource handle.

No response may include a count or candidate-specific error. Timing differences should be minimized through bounded work, uniform response construction and rate limits; perfect constant-time behavior for database searches is not assumed. Security review must threat-model timing, status codes, response sizes, cache behavior and retry behavior.

Authorized patient summaries may be returned only after all source checks and audit commit. Where resolution yields multiple authorized candidates, the protocol must not silently choose one. Return a non-identifying reconciliation outcome unless a separately approved, clinically safe workflow is defined. Do not return candidate count or partial candidate details merely to explain ambiguity.

Required controls:
- per-node, per-clinician and per-source rate limits;
- progressive throttling and alerting for repeated selector probes;
- anomaly detection for sequential identifiers and high-volume searches;
- bounded selector syntax and query cost;
- no distinguishable per-candidate failure messages;
- no cache key or cache hit behavior that bypasses current authorization;
- audit events for challenge issuance, assertion rejection, resolution attempt, authorized disclosure, suppressed/ambiguous outcome and throttling.

### 2.5 Discovery handle validation

On every later use, the source loads its own handle record and checks:
- handle exists, is active and unexpired;
- exact node, clinician/issuer context and destination match;
- action/purpose/scope match the new operation;
- source resource and pointer version remain valid;
- current source policy and clinician authorization still allow access.

A handle cannot be substituted across resources, destinations, branches, clinicians or actions. Import requires a new import challenge and assertion; a discovery handle alone never authorizes import.

## 3. Challenge/assertion state and transaction semantics

### 3.1 Source-side operation state

Use a durable source-owned state machine. Exact physical tables and names remain implementation decisions.

`ISSUED → RESERVED → AUTHORIZED_AUDITED → DISCLOSURE_COMMITTED`

Terminal or recovery outcomes:
- `REJECTED`: signature, claim, trust, status, challenge or policy check failed;
- `DENIED_AUDITED`: valid request but source authorization denied;
- `FAILED_RETRYABLE`: no protected response was committed; retry requires a new challenge/assertion unless the source can prove the same operation remains safely resumable;
- `OUTCOME_UNCERTAIN`: source cannot prove whether a response was released; operator reconciliation is required and must not trigger another read;
- `EXPIRED` / `REVOKED`: challenge or trust context is no longer valid.

A monotonically increasing operation generation/fencing value is required wherever a worker can be reclaimed or superseded. State transitions use compare-and-swap or row locks plus uniqueness constraints; cache-only replay prevention is insufficient.

### 3.2 Atomic reservation

Before protected source access, the source transactionally:
1. Loads and locks the challenge/operation record.
2. Verifies the challenge is in the expected state and exact request binding.
3. Verifies the assertion jti has not been claimed.
4. Inserts a unique issuer-scoped jti claim and reserves the challenge for this operation.
5. Checks the current issuer/key and clinician mapping/status snapshot.
6. Applies source authorization and current privacy policy.
7. Writes the required source decision audit event.

The durable uniqueness constraint and transaction isolation must prevent two workers from reserving the same challenge/jti. The source must not execute a protected patient query in a route or service path before this gate.

A denied but valid request is recorded as `DENIED_AUDITED`; it does not proceed to disclosure. Invalid/rejected attempts are separately rate-limited and audited where safely possible without logging bearer assertions or PHI.

### 3.3 Disclosure transaction and audit ordering

For database-resident source data, the source should perform the authorized minimal read, create a durable disclosure-outcome record and persist the source audit stage within a transaction boundary that ensures no response is emitted before commit. The exact isolation/locking approach must be proven with PostgreSQL multi-session tests.

If required audit persistence or transaction commit fails, no protected response is sent. The challenge/jti reservation outcome must be deterministic:
- if the transaction fully rolls back and the source can prove no response bytes were released, the operation is not treated as disclosed; retry uses a fresh challenge/assertion by default;
- if a durable disclosure outcome committed, the challenge is consumed and the response is retrievable only through same-operation recovery;
- if the source cannot establish which case occurred, mark `OUTCOME_UNCERTAIN`, deny a new source read, and require governed reconciliation.

A source audit failure must never cause a fallback to node-only authorization or an unlogged disclosure.

### 3.4 Lost-response and replay behavior

A repeated bearer assertion is not a retry mechanism. After a successful committed operation, a retry must:
- identify the same durable operation using the same operation ID and recipient binding;
- prove the caller is the same authenticated node/branch and same authorized clinician context, subject to current revocation policy;
- retrieve only the previously committed outcome or immutable response artifact;
- verify the artifact digest and operation binding;
- not execute a new patient query, re-evaluate into a new disclosure, or widen scope.

If the original response was not durably committed, the destination must obtain a fresh source challenge and assertion. The source must not use an expired challenge to authorize a new disclosure. A fresh challenge may resume an existing import operation only under the PR #23/#24 durable-operation and fencing rules; it must not create a second patient clone.

For responses containing protected data, the storage/encryption, retention and access controls for any replayable response artifact are D-12 and security-review decisions. If safe replay storage is not approved, the safe outcome is reauthorization through a fresh challenge, not replaying a raw bearer token.

### 3.5 Revocation freshness

Issuer/key trust, clinician affiliation/status, professional credential status where required, source policy and destination eligibility must be checked at the point of authorization and again at the defined disclosure boundary if a meaningful time gap exists. The accepted maximum staleness and cache invalidation behavior are D-09 decisions. No stale-cache fallback may exceed the approved revocation SLA.

## 4. Source-authenticated transfer response contract

### 4.1 Integrity manifest

The source response must carry a source-authenticated integrity manifest. The exact signature/MAC algorithm, key type and custody are governed by D-07/D-08 and are intentionally not selected here. The design must use an approved source-controlled signing identity or an explicitly approved mutually authenticated transport plus independently verifiable manifest. Transport security alone does not replace end-to-end payload binding where the payload crosses service/storage boundaries.

The canonical manifest binds:
- protocol version and response type;
- source issuer, source tenant/branch and source node identity;
- exact destination tenant/branch and destination node;
- source pointer/resource identity and source resource version;
- import operation ID and destination idempotency key reference;
- challenge ID and assertion jti fingerprint (never raw assertion);
- clinician/issuer subject reference and authorization decision ID;
- action, purpose and approved data scope;
- issue time, expiry and source policy/version reference;
- canonical payload digest, payload schema/version and content type;
- unique response ID and response sequence/generation.

The manifest must be canonicalized deterministically before digest/signature verification. The canonicalization and digest algorithms are also subject to security approval. The payload must not be committed at the destination until the manifest, signature/integrity proof, all recipient/resource/scope bindings, expiry and digest have been verified.

### 4.2 Replay and substitution rejection

Reject a response if:
- source issuer/key is unknown, revoked or invalid;
- manifest or payload digest does not verify;
- source branch, destination tenant/branch/node, operation, challenge, source pointer/version, action, purpose or scope differs from the durable operation;
- response is expired, superseded or from an older fencing generation;
- response ID has already been applied to a different operation;
- payload schema or protocol version is unsupported;
- required source authorization/policy evidence is missing.

A byte-identical response for the same operation may be recognized as a retry artifact, but it must not cause a second destination commit. The destination operation state and provenance marker remain authoritative.

### 4.3 Destination commit acknowledgement

The destination emits a verifiable acknowledgement only after its transaction commits:
- patient/allergy clone (if applicable);
- durable source provenance marker;
- operation state transition;
- payload digest and response ID reference;
- destination audit commit event.

The acknowledgement is authenticated by a destination-controlled identity and bound to source issuer/branch, destination tenant/branch/node, operation ID, response ID/digest, fencing generation and commit time. The source verifies the acknowledgement before recording `DESTINATION_COMMIT_ACKNOWLEDGED`.

A source-side `AUTHORIZED` or `RESPONSE_SENT` event is not a destination commit. A destination-side local commit is not proof the source received the acknowledgement. Audit records must preserve these distinctions.

### 4.4 Lost acknowledgement and uncertain cross-database outcomes

If the destination commit succeeds but the acknowledgement is lost:
- destination retry/reconciliation reads the durable operation and provenance marker;
- it does not insert another patient or replay the payload into a second row;
- it regenerates an acknowledgement for the same committed operation and exact response digest, under the current fencing generation;
- source accepts the acknowledgement idempotently for that operation only.

If the destination cannot prove commit, it must not claim success. If the source cannot verify the acknowledgement, it records an uncertain state and reconciles through the durable operation contract. No cross-database atomicity is assumed.

The source must not repeat protected disclosure merely because an acknowledgement is missing. Any source-side payload re-delivery must be limited to a previously committed same-operation artifact and must satisfy the approved recipient, expiry, revocation and retention rules.

## 5. Required alignment with PRs #23/#24

This clarification depends on the proposed import recovery design and does not supersede it:
- one durable import operation identity, not demographics or ABHA;
- monotonic fencing generation and CAS state transitions;
- destination-side fencing before patient/allergy commit and pointer publication;
- durable provenance marker to prove exact source-to-destination clone identity;
- fresh validated receipt for resuming after original receipt expiry;
- policy revocation after destination commit transitions to the specified restricted/quarantined workflow;
- pointer synchronization is separately recoverable and cannot create a duplicate clone.

Before implementation, reviewers must reconcile terminology and state transitions across PR #19, PR #23, PR #24, PR #28 and this document. If there is a conflict, stop and revise the design; do not choose an implementation interpretation silently.

## 6. PostgreSQL and security acceptance tests

### Discovery privacy
- no match, unauthorized match, privacy-suppressed match and ambiguous match produce the same non-identifying response class/schema;
- challenge creation returns no existence, count, demographics or candidate-specific error;
- caller-provided selector digest cannot replace source canonicalization;
- sequential identifier probing is throttled and audited;
- unauthorized candidates never produce handles or summaries;
- handle substitution across clinician, node, destination, branch, action, purpose, scope or resource is rejected;
- stale pointer/resource version and policy changes invalidate handle use;
- timing/size/status/cache side-channel tests cover zero/one/multiple and denied cases.

### Challenge and replay transactions
- two independent PostgreSQL sessions submit same challenge/jti concurrently; exactly one can reserve and disclose;
- uniqueness/CAS works across separate application workers and process restarts;
- audit failure prevents response release;
- authorization denial is durably distinguished from invalid assertion;
- rollback before disclosure permits only the defined fresh-challenge retry;
- crash after committed disclosure but before network response retrieves only same-operation committed artifact;
- ambiguous transaction outcome enters `OUTCOME_UNCERTAIN` and never triggers another source read;
- key/clinician/policy revocation between challenge, assertion and disclosure is enforced under approved freshness rules.

### Transfer integrity and acknowledgement
- payload byte tampering and manifest tampering fail verification;
- wrong source, destination, branch, node, clinician, operation, challenge, resource, scope, purpose, version or generation is rejected;
- stale/revoked signing key and unsupported schema fail closed;
- response replay against another operation cannot commit;
- lost acknowledgement after destination commit does not duplicate patient/allergy rows;
- acknowledgement forgery, substitution and stale-generation acknowledgement are rejected;
- source audit never marks destination committed before verified acknowledgement;
- pointer publication waits for the approved durable state and fencing condition.

Use independent PostgreSQL sessions and worker processes. SQLite-only tests do not establish concurrency correctness. Include failure injection at each commit, audit write, network response and acknowledgement boundary.

## 7. Decisions intentionally left open

These clarifications do not approve or select:
- issuer authority, clinician identity evidence, clinician classes or professional registration verification;
- signing algorithm, key type, custody, rotation or trust onboarding;
- assertion/challenge/handle/response-artifact lifetime and revocation SLA;
- exact purpose vocabulary, data scope, audit retention or access;
- canonicalization and cryptographic digest/signature algorithms;
- whether and how replayable protected response artifacts may be stored;
- formal D-11 approval for local cross-branch access;
- emergency/break-glass federation.

These require the named accountable approvals and evidence in the AUD-004 governance checklist. D-14 remains a final release gate.

## 8. Stop conditions

This is design-only. It authorizes no runtime code, schema migration, feature flag, signing key, trust entry, partner onboarding, pilot, production patient-data access, merge, deployment, release or emergency federation. AUD-004 remains release-blocking until implementation is separately authorized, independently validated and formally approved.
