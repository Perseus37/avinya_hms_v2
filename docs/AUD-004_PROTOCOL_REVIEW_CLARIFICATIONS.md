# AUD-004 Protocol Review Clarifications

**Status:** Proposed design clarification — not a protocol approval  
**Parent:** PR #28, technical implementation blueprint  
**Scope:** Discovery privacy, challenge/replay transaction semantics, and source-to-destination transfer integrity  
**Safety:** Documentation only. No runtime code, schema, migrations, configuration, trust records, keys, feature flags, or behavior changes.

This document addresses three blocking questions raised during independent architecture review of PR #28. It narrows the protocol design but does not close D-01–D-14, authorize implementation, or select an unapproved cryptographic algorithm.

## 1. Discovery without patient-existence disclosure

### 1.1 Security requirement

The source must not reveal patient existence, match count, demographics, source pointer identifiers, or distinguishable candidate errors before it has verified the clinician assertion and made a source-side authorization decision for the relevant patient/resource.

A selector hash or opaque handle is not authorization. The source must retain the canonical selector/resource binding and enforce it after actor verification.

### 1.2 Proposed staged protocol

**Stage A — challenge request (no patient result)**

1. The destination authenticates using its registered node credential and submits a discovery-intent request containing destination branch, requested action, protocol version, purpose candidate, minimum requested scope, and the selector input.
2. The source authenticates the node and validates that the destination is an eligible partner. It canonicalizes the selector using a versioned, source-defined normalization contract.
3. The source creates a random challenge bound to the authenticated node, requesting branch, destination, action, purpose, canonical selector representation/fingerprint, requested scope, protocol version, and expiry.
4. The source returns only the challenge reference and protocol metadata. It does not resolve or disclose match count, patient existence, pointer IDs, or candidate-specific outcomes in this response.

The selector must be protected in storage and logs. If retaining the canonical selector is necessary for later exact matching, store it encrypted or in an appropriately protected source-local record; do not rely solely on a client-provided digest. Data minimization, encryption and retention are subject to D-12.

**Stage B — actor assertion**

5. The destination issuer authenticates the current human session and derives issuer-scoped clinician subject, home branch and permitted local attributes from server-side records.
6. The issuer signs an assertion bound to the exact challenge ID, action, purpose, destination, selector binding and requested scope.
7. The destination submits the assertion to the source. Caller-supplied actor IDs, role labels, subject, branch, purpose or scope are not trusted.

**Stage C — source verification and private resolution**

8. The source verifies node, issuer trust, signing key, signature, claims, time, current clinician mapping/status, challenge binding and replay state.
9. Only after actor verification does the source resolve the stored canonical selector internally.
10. The source evaluates authorization and current privacy/data-use policy separately for every candidate resource. A policy decision for one candidate must not authorize another candidate.
11. The source writes a durable source-side decision for each candidate or a carefully defined aggregate decision that cannot obscure per-resource denials.
12. Only authorized candidate summaries and source-issued opaque resource handles are returned. Unauthorized candidates are omitted without indicating whether they exist.

### 1.3 Response and enumeration controls

- Zero matches, all-denied matches and non-disclosing resolution failures must not expose patient existence through distinct error messages.
- Do not return total candidate counts, source pointer IDs, or candidate-specific denial reasons to the destination.
- Use stable externally visible response classes and avoid candidate-dependent error detail.
- Apply source-side rate limits, abuse detection and audit for repeated selector probes. Thresholds and operational response are policy decisions, not hard-coded defaults in this document.
- Define and test timing-side-channel tolerances. Perfect constant-time behavior for database search may not be realistic; the threat model must identify observable timing differences and specify practical mitigations.
- Bind opaque handles to node, destination, clinician/authorization context, resource, action, purpose, scope, protocol version and expiry. A handle must not be transferable across partners or operations.
- A handle is a locator/correlation artifact, never a bearer authorization by itself.

### 1.4 Required tests

- zero/one/multiple match outcomes do not disclose unauthorized existence or counts;
- unauthorized candidate is indistinguishable from nonexistent candidate to the caller;
- no candidate-specific error detail or raw pointer leaks;
- selector normalization and canonical binding cannot be changed between challenge and assertion;
- handle substitution, cross-node, cross-destination, cross-purpose and cross-action reuse fail;
- repeated probing triggers configured rate-limit/abuse controls;
- authorization is evaluated independently for every candidate;
- source audit records internal resolution and per-candidate decision without over-logging PHI.

**Open decision:** Whether selector resolution is allowed before actor assertion verification in any deployment profile. This proposal says no patient-specific resolution result or externally observable candidate-dependent behavior may occur before actor verification. Any deviation requires explicit threat-model and privacy approval.

## 2. Challenge, assertion replay and retry transaction semantics

### 2.1 Required invariants

1. A challenge is bound to one authenticated node, destination, action, purpose, selector/resource binding, scope and protocol version.
2. A challenge can authorize at most one logical protected operation.
3. The same assertion/challenge cannot cause two independent source reads or disclosures.
4. Concurrent requests cannot both pass the one-time claim.
5. A failed required audit commit cannot result in protected data disclosure.
6. A retry after an uncertain outcome must resolve the same durable operation; it must not become a new authorization through replay.
7. A fresh challenge is required when the original authorization attempt was not durably completed and the protocol requires a new authorization decision.

### 2.2 Proposed source-side state model

Use a source-local durable operation record with atomic compare-and-swap transitions. Exact state names and schema are proposals:

`ISSUED → ASSERTION_VERIFIED → AUTHORIZATION_PENDING → AUTHORIZED_AUDITED → RESPONSE_PREPARED → RESPONSE_RELEASED`

Failure/terminal states:

- `REJECTED`: invalid assertion, binding mismatch, revoked/unknown actor, replay or policy denial.
- `FAILED_RETRYABLE`: transient infrastructure failure before any protected response was released; retry rules require a fresh challenge unless the same operation can be safely resumed without repeating disclosure.
- `INDETERMINATE`: response may have been released but acknowledgement is absent; reconcile the same operation, never create a second disclosure merely by replay.
- `EXPIRED`: challenge expired before successful authorization.
- `CANCELLED`: explicit safe cancellation before release.

The state machine must not mark an operation complete merely because an assertion verified or an authorization decision was allowed.

### 2.3 Transaction and locking requirements

- Persist challenge creation before returning the challenge reference.
- Validate signature and claims before attempting to claim the challenge.
- Claim challenge and `jti` atomically using a database transaction and uniqueness constraints/CAS. Concurrent losers must stop before protected source reads.
- Perform current clinician status, affiliation, credential freshness, source authorization and privacy checks under a documented consistency model.
- Persist the authorization decision and required source audit before preparing/releasing protected response data.
- If the audit commit fails, do not release data. The challenge/operation should transition to a non-reusable failure or indeterminate state according to the transaction outcome; do not silently restore a consumed challenge.
- Persist a response manifest/digest and durable operation state before attempting network delivery where feasible.
- After response release, a repeated request may retrieve only the same previously committed response outcome for the same authenticated operation and recipient, subject to approved retention and reauthorization policy. It must not trigger a new source read or expand scope.
- If the source cannot prove whether release occurred, return an indeterminate status and require reconciliation. Do not claim no disclosure occurred.
- A new challenge is required for a genuinely new attempt or changed actor, resource, purpose, destination or scope.

Because database commit and network delivery cannot be one atomic transaction, the protocol must explicitly model the gap. It must not claim exactly-once network delivery. It can provide at-most-once authorization/disclosure semantics with durable operation identity and safe same-operation reconciliation, subject to the final implementation design.

### 2.4 Import recovery compatibility

The source authorization operation and destination import operation are related but distinct state machines:
- Source challenge/assertion controls whether source data may be disclosed.
- Destination import idempotency/fencing controls whether a received authorized payload is committed once.
- A source authorization ID, source response ID and destination import operation ID must have explicit correlation and recipient binding.
- A new source authorization must not create a second destination clone if an earlier destination commit succeeded but acknowledgement was lost.
- Destination fencing generations from PR #23/#24 must guard destination commit and pointer publication; stale workers must not create side effects.
- A fresh source challenge after receipt expiry may authorize a new source read only after current clinician authorization and privacy policy are re-evaluated. It must still resolve the same source pointer and destination operation identity where the intent is recovery.
- Source-policy revocation after destination commit must follow the restricted/quarantine governance behavior described in PR #24; it must not silently publish or delete the clone.

### 2.5 Required PostgreSQL tests

Use independent sessions and worker processes:
- two concurrent submissions of the same challenge and jti: exactly one claim succeeds;
- failure between claim and authorization;
- source authorization denied after claim;
- audit commit failure;
- response manifest committed but network response lost;
- response delivered but acknowledgement lost;
- retry with same operation returns only same-operation status/result and never starts a second source read;
- changed actor/resource/destination/scope with same challenge is rejected;
- fresh challenge after expiry rechecks current actor status and source privacy policy;
- transaction rollback and worker crash at every state transition;
- stale worker cannot transition or release data after a newer fencing generation.

## 3. Source-to-destination transfer integrity and acknowledgement

### 3.1 Security requirement

A destination must be able to verify that the received payload:
- originated from the expected source branch/issuer;
- is intended for this exact destination tenant, branch and node;
- corresponds to the authorized source resource and operation;
- has not been altered, substituted, truncated or replayed;
- contains no data outside the authorized scope;
- is still valid under the protocol's expiry and revocation rules.

A random opaque handle alone does not establish payload integrity or origin.

### 3.2 Proposed transfer manifest

Define a versioned source-authenticated manifest, with the cryptographic mechanism selected only after D-07/D-08 approval. Candidate mechanisms may include a source digital signature over a canonical manifest, or another independently reviewed authenticated envelope. Do not assume an algorithm or key custody model here.

The manifest should bind at least:
- protocol and manifest version;
- source issuer, source tenant/branch and source node identity;
- exact destination tenant/branch and destination node identity;
- source pointer/resource identity and source record version/snapshot reference;
- source authorization operation ID and challenge ID;
- destination import operation ID and idempotency identity;
- action, purpose and authorized data scope;
- payload canonicalization/version and cryptographic digest;
- issue time, expiry and relevant policy/status version references;
- unique response/transfer ID;
- source audit correlation ID.

The manifest must not contain unnecessary patient demographics or raw bearer assertions. Sensitive resource references should be opaque and minimized.

### 3.3 Destination verification before commit

Before destination persistence:
1. Authenticate the source response under the approved trust relationship.
2. Verify manifest signature/authenticity and protocol version.
3. Verify exact source and destination identities against the active request and trust record.
4. Verify action, purpose, resource, source version, scope, operation IDs and expiry.
5. Recompute canonical payload digest and compare it with the manifest.
6. Reject extra/unrequested data categories, missing required fields, duplicate or ambiguous payload elements, and unsupported schema versions.
7. Verify the response is not already consumed by a different destination operation.
8. Persist the validated manifest digest and correlation marker atomically with the destination import commit, guarded by the active fencing generation.
9. Record destination audit stages separately from source authorization and source release.

A valid signature does not replace destination validation of schema, scope or provenance.

### 3.4 Acknowledgement protocol

After the destination commit transaction succeeds, the destination should produce an authenticated acknowledgement bound to:
- source response/transfer ID;
- source authorization operation ID;
- destination import operation ID;
- destination tenant/branch/node;
- committed destination provenance marker;
- committed payload/manifest digest;
- fencing generation or durable operation version;
- commit outcome and timestamp.

The source validates the acknowledgement against the original recipient and operation, then records a distinct `DESTINATION_COMMIT_ACKNOWLEDGED` event. It must not treat a generic HTTP 200, node connectivity, or receipt of a request as proof of commit.

If acknowledgement is lost:
- destination retry returns the durable outcome for the same operation and digest;
- source reconciliation queries or accepts a replayed authenticated acknowledgement for the same operation;
- neither side starts a second transfer or clone;
- conflicting digest, recipient, operation ID or fencing generation moves the operation to reconciliation/denial, not automatic overwrite.

The acknowledgement protocol must avoid creating an authorization bypass: it confirms a previously authorized and committed operation; it does not authorize new source reads.

### 3.5 Required tests

- payload byte/field tampering and digest mismatch;
- invalid/unknown/revoked source signing key;
- wrong source, destination tenant/branch/node or source pointer;
- changed purpose, scope, operation ID, response ID or protocol version;
- expired or stale source snapshot;
- extra data outside authorized scope;
- response replay against a different import operation or destination;
- destination commit marker and payload are atomic;
- stale fencing generation cannot commit or acknowledge;
- lost commit acknowledgement and same-operation reconciliation;
- duplicate acknowledgement is idempotent; conflicting acknowledgement is rejected;
- source audit distinguishes authorization, response preparation, release and verified destination commit acknowledgement.

## 4. Decisions still required

These clarifications do not close:
- D-01 issuer authority and accountability;
- D-02 authentication assurance;
- D-03 permitted clinician classes;
- D-04 credential/licensure evidence and freshness;
- D-05 source authorization authority and policy;
- D-06 purpose/action/scope vocabulary;
- D-07 cryptographic algorithm and key custody;
- D-08 trust onboarding and dual control;
- D-09 assertion/challenge lifetime, clock skew and revocation freshness;
- D-10 replay and distributed outcome semantics;
- D-11 formal approval of local cross-branch scope (project direction YES; governance approval pending);
- D-12 audit content, retention and access;
- D-13 formal emergency/break-glass exclusion;
- D-14 final pilot/release authorization.

The selector normalization/privacy threat model, exact challenge state machine, transaction isolation, manifest format, acknowledgement trust and recovery semantics require independent review before implementation.

## 5. Implementation and safety boundary

This document is design-only. It does not:
- authorize runtime implementation or migrations;
- select an algorithm, key custody provider, lifetime, purpose vocabulary or retention schedule;
- authorize trust onboarding, key provisioning, pilot, deployment or production patient-data access;
- authorize merge or release;
- enable emergency/break-glass federation.

Implementation remains gated on formal governance decisions, acceptance of the import recovery design, independent security/privacy/clinical review, and explicit release approval. AUD-004 remains a release blocker.
