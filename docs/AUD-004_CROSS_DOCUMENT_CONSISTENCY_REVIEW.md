# AUD-004 Cross-Document and Runtime Consistency Review

**Status:** REVIEW FINDINGS — DESIGN ONLY — NOT AUTHORIZED FOR RUNTIME IMPLEMENTATION  
**Scope reviewed:** PR #19 runtime remediation, PRs #23/#24 import recovery design, PR #28 implementation blueprint, and PR #30 protocol security clarifications.  
**Review basis:** Current PR heads and the PR #19 federation router/import implementation. This is a static review, not a test run, penetration test, or formal governance approval.

## 1. Executive conclusion

The documents are directionally compatible, but they do **not yet form one implementation-ready protocol**. The most important gap is not merely missing assertion code: the current PR #19 discovery path performs global-index candidate resolution and reads source patient demographics/allergies before any clinician assertion exists. It authenticates a federation node only. Issuing a receipt after this disclosure cannot retroactively authorize it.

PR #30's proposed source-side challenge/assertion flow must therefore become the mandatory authorization boundary for every source-side candidate resolution and read. The global control-plane index and PR #19 receipt must be treated as routing/integrity mechanisms only, never as proof of clinician identity or permission.

No runtime change is proposed in this review.

## 2. Findings requiring resolution

### CDR-01 — Discovery currently discloses before actor verification

**Severity: Critical / release-blocking**

Observed in PR #19 runtime:
- `GET /api/federation/patients/discover` depends on `get_federated_node`, which authenticates a node/service, not a human clinician.
- It queries `GlobalPatientPointer` by ABHA or phone before any clinician assertion verification.
- It returns distinct no-match and ambiguity outcomes (404/409) and may disclose branch identifiers in partial-failure metadata.
- Worker sessions read source `Patient` demographics and allergies.
- Source policy evaluation uses `actor_user_id=None`.
- A `FederationTransferLog` is written after the patient read, recording the requesting node/branch, not a verified clinician.

PR #30 says source-side actor verification and authorization must precede protected source resolution/disclosure. These are inconsistent until the route is redesigned.

**Required resolution**
1. The control-plane index may route requests only; it must not return patient existence, candidate count, branch list, MRN or demographics to an unauthorised caller.
2. The source branch must receive a source-issued challenge and clinician assertion before resolving the canonical selector against its patient table.
3. The source must authorize each resolved candidate and current policy before returning any patient-specific result.
4. The orchestration layer must normalize no-match, denied, privacy-suppressed and ambiguous outcomes as specified in PR #30, including hiding candidate branch names from untrusted callers.
5. Source audit must identify the verified clinician assertion, not only node identity.

### CDR-02 — Global index and source-challenge ownership are underspecified

**Severity: High**

PR #19's discovery route centrally queries `GlobalPatientPointer` to learn candidate source branches, then opens each tenant database directly through `tenant_engine_pool`. PR #28/#30 describe source-issued challenges and source-side resource handles, but do not fully define how a source challenge is obtained without first revealing candidate existence through the central index.

**Required resolution**
- Define an index-blind routing protocol: the coordinator submits the selector to the routing layer without receiving candidate metadata; the routing layer fans out opaque requests to eligible source nodes, or uses an equivalent privacy-reviewed mechanism.
- Each source owns selector canonicalization, patient resolution, actor authorization, handle creation and disclosure audit.
- Define how inactive/unavailable source nodes are represented without returning a candidate-specific existence signal.
- Define whether the source node or a separately approved federation gateway is the issuer/verifier endpoint. Do not let a central coordinator impersonate source authorization.
- Apply the same design to local cross-branch imports; same-process/database access is not an exemption.

Do not assume a global index can remain a candidate-returning API and simultaneously satisfy PR #30's no-existence-before-authorization invariant.

### CDR-03 — PR #19 discovery receipt is not an actor authorization artifact

**Severity: Critical / release-blocking**

PR #19's receipt is a two-minute, random bearer token whose SHA-256 hash is stored centrally. It binds node ID, destination branch, selector hash, pointer snapshot, source pointer ID and summary hash. It does not bind a verified clinician, issuer/subject, source authorization decision, action-specific actor assertion, or source-side one-time challenge.

The receipt is minted only after PR #19 has already read source patient data and assembled the demographic summary. It cannot authorize that earlier disclosure.

**Required resolution**
- Keep the PR #19 receipt, if retained, strictly as a discovery-result integrity/completeness and import handoff artifact; explicitly state it grants no patient-data access.
- Require source-side actor authorization before source patient reads during discovery, not merely before import.
- Bind any authorized source resource handle to the source-side clinician decision and destination, but require a fresh import challenge/assertion and current policy re-evaluation for import.
- Define how the legacy central receipt references the source authorization decision without becoming a bearer bypass.
- A receipt presented without valid source authorization must not permit source re-read, payload replay or import.

### CDR-04 — Import route reads source data using receipt + destination RBAC only

**Severity: Critical / release-blocking**

Observed in PR #19 import:
- `POST /api/federation/patients/import` requires local `RequirePermission("patients:write")`.
- It validates the control-plane discovery receipt, node active status, destination, selector, pointer snapshot and summary digest.
- It then opens the source tenant database directly and reads source policy, patient demographics and allergies.
- Source policy evaluation again uses `actor_user_id=None`.
- It writes a source transfer log without a verified clinician assertion.

This does not satisfy AUD-004. A valid receipt proves a prior node-bound discovery response; it does not prove the current human is authorized by the source to import the patient.

**Required resolution**
- Require a distinct source-issued import challenge and signed clinician assertion, bound to the exact source resource handle, destination, action, purpose and minimum scope.
- Verify the assertion and current clinician affiliation/status at the source before any source patient/allergy read.
- Re-evaluate source policy and purpose-specific authorization at import time.
- Enforce the authorization at the source data-access/service boundary so direct ORM access or internal service invocation cannot bypass it.
- Retain destination `patients:write` as an additional local control, not a substitute for source authorization.

### CDR-05 — Two different receipt/challenge/replay state machines need explicit separation

**Severity: High**

There are at least three distinct artifacts:
1. PR #19 discovery receipt (central control-plane, two-minute, summary/pointer integrity).
2. PR #30 source challenge/assertion and source replay claim (one protected source action).
3. PR #23/#24 durable import operation, lease and fencing generation (cross-database clone recovery).

The documents generally describe these concepts, but do not provide a single transition/correlation matrix. PR #30's source disclosure state must not be conflated with PR #23/#24's destination import state.

**Required resolution**
- Give each artifact a distinct type, owner, identifier, lifecycle, expiry and authority statement.
- Explicitly map: discovery challenge/assertion → source authorization decision → source resource handle → central discovery receipt (if retained) → separate import challenge/assertion → source import authorization/response manifest → destination durable import operation → destination commit acknowledgement → pointer synchronization.
- State which artifact may authorize a new source read (only a current action-specific source authorization), which may prove prior response integrity (receipt/manifest), and which controls destination retries (durable operation/fencing).
- Specify recovery when each artifact expires independently. Expired authorization must never be revived by an import operation ID, receipt, handle or operator action.
- Require new source authorization for any new disclosure; retries of already committed artifacts may retrieve only the exact same operation payload under approved policy and revocation rules.

### CDR-06 — Source audit and transfer log semantics are not yet reconciled

**Severity: High**

PR #19 discovery currently writes a source `FederationTransferLog` after its patient read and stores node/branch identity with `actor_user_id=None`. Import writes a source transfer log with purpose `CONTINUITY_OF_CARE_IMPORT_REQUESTED` before destination commit. PR #30 requires distinct request, authorization, disclosure, import and verified destination-commit acknowledgement events.

**Required resolution**
- Define a versioned audit event contract with verified issuer/subject reference, clinician mapping version, authentication assurance, node, source/destination, action, purpose, resource reference, scope, policy version, challenge/jti fingerprints, decision, response ID/digest and stage.
- Distinguish rejected request, denied authorization, authorized, disclosure committed, response delivered/uncertain, import requested, destination committed (only after verified acknowledgement), pointer sync pending and completed.
- Do not label a request log as a transfer completion.
- Make required source authorization audit durable before disclosure; make audit failure fail closed.
- Do not store raw assertions, bearer receipts, private keys or unnecessary PHI in audit records.

### CDR-07 — Discovery partial-result metadata can reveal source topology

**Severity: High**

PR #19 response schema includes `failed_source_branches`, source counts and partial flags; the route returns branch names in error detail for partial discovery. PR #30 requires non-identifying response behavior for no-match, denied, privacy-suppressed and ambiguous outcomes.

**Required resolution**
- Keep detailed source failure diagnostics in protected operator/source audit channels only.
- Public federation responses must not expose candidate branch names or candidate counts before appropriate authorization.
- Define whether an authorized partial result is ever allowed; it must not mint a complete-discovery receipt or authorize import.
- Ensure source topology is not leaked by response codes, timing, payload size or retries.

### CDR-08 — Selector privacy needs one consistent canonicalization/index contract

**Severity: High**

PR #19 uses SHA-256 phone hashes and a deterministic selector hash; PR #30 requires source-side canonicalization and warns against plain hashes of low-entropy identifiers. The central pointer index is currently searchable using deterministic phone/ABHA-derived values.

**Required resolution**
- Decide whether the global index is retained, what data it may hold, who can query it, and whether its identifiers are keyed/tokenized under a protected key rather than globally guessable deterministic hashes.
- Source canonicalization must be authoritative and protocol-versioned.
- Never treat caller-provided hashes as identity proof or authorization.
- Review ABHA handling, phone normalization, key rotation, cross-tenant correlation and offline guessing risk.
- Do not rotate/change existing index derivation without a migration/backfill plan and collision/availability analysis.

### CDR-09 — Import recovery must remain a separate destination transaction protocol

**Severity: High**

PR #23/#24 require unique durable operation identity, destination provenance marker, CAS state transitions, fencing generations, destination-side stale-worker fencing, restricted/quarantined state after post-commit source-policy revocation, and separately recoverable pointer synchronization. PR #30's source challenge/disclosure lifecycle is compatible only if it remains a separate source-side authorization/disclosure protocol.

**Required resolution**
- Maintain separate source-side authorization/disclosure state and destination-side import operation state.
- Destination patient/allergy rows and provenance marker must commit atomically in the destination database under current fencing generation.
- Destination commit acknowledgement must be generated only after that commit and verified by source before source audit marks the destination committed.
- Pointer publication/synchronization must be separately recoverable and fenced.
- A fresh source authorization may resume only the same validated source pointer/destination/protocol operation; it must not create a new clone or bypass quarantine on policy revocation.
- No demographic/ABHA match may prove exact retry.

### CDR-10 — Local cross-branch enforcement must cover direct database paths

**Severity: Critical / release-blocking**

D-11 project direction includes local cross-branch imports. PR #19's import handler opens source tenant DB sessions directly from the control-plane registry. PR #28/#30 require local and remote operations to share source-side actor controls.

**Required resolution**
- Define a source authorization adapter that works for both remote federation and local cross-tenant service calls.
- No local shortcut, shared database process, control-plane administrator, or destination permission may bypass the same source clinician assertion and source policy checks.
- Audit must retain actual source and destination branch identity.
- Add tests for direct service invocation, internal callers, root/V1 aliases and background tasks.

## 3. Canonical end-to-end artifact flow

The following is the recommended conceptual order. It is a review target, not an approved wire protocol:

1. Destination node authenticates to routing/control plane.
2. Routing layer accepts selector without exposing candidate information to destination.
3. Each candidate source receives an opaque discovery request and issues its own source challenge without confirming patient existence.
4. Destination issuer derives clinician identity from current local session and signs an assertion bound to each source challenge.
5. Source verifies node, issuer/key, clinician mapping/status, assertion, challenge and replay claim.
6. Source resolves selector internally; source evaluates exact clinician/action/purpose/resource/destination/scope and current privacy policy.
7. Source commits authorization/disclosure audit before returning any protected summary.
8. Source returns authorized minimal summary and opaque source resource handle; coordinator aggregates only authorized results and hides source topology.
9. If complete, a central receipt may attest only to response completeness/integrity and bind the authorized source result set. It is not authorization.
10. Import requires a new source import challenge/assertion for the exact resource handle and destination.
11. Source reauthorizes and re-evaluates policy, audits before disclosure, and returns a source-authenticated payload manifest.
12. Destination validates manifest and begins/loads the durable import operation under PR #23/#24.
13. Destination transaction commits patient/allergies plus provenance under current fencing generation.
14. Destination emits authenticated commit acknowledgement; source records acknowledgement only after verification.
15. Pointer sync occurs as a separately fenced/recoverable operation; source/destination audit states remain distinct.

## 4. Required acceptance evidence before implementation

- A protocol sequence diagram showing all three artifact/state machines and the trust boundaries.
- A data-flow diagram identifying every system that can observe selector, candidate source branch, source pointer, demographics and allergies.
- Threat model for selector enumeration, timing/status/size leaks, malicious partner, compromised node, compromised clinician account, key compromise, replay, stale worker and cross-tenant access.
- A complete route/service/background-job inventory for remote and local cross-branch reads.
- A versioned audit event schema and state-transition matrix.
- PostgreSQL multi-session tests for challenge/jti reservation, import idempotency, fencing and lost acknowledgements.
- Failure-injection evidence at source audit, source disclosure, destination commit, acknowledgement and pointer-sync boundaries.
- Independent security, privacy and clinical-safety review.
- Formal D-01–D-14 approvals as applicable; D-11 formal approval remains pending and D-14 remains the final release gate.

## 5. Explicit stop conditions

Do not begin runtime implementation until the project owner accepts the reconciled protocol and the required governance approvals are recorded. Do not merge PR #19 or the design PR stack merely because the documents are internally consistent. Do not provision production keys/trust entries, enable flags, onboard partners, run a pilot, access production patient data, deploy, release or enable emergency federation under this review.

**AUD-004 remains release-blocking.** This document records design integration findings only; it does not approve implementation or claim compliance.
