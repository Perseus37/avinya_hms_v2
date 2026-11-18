# AUD-004 Consolidated Protocol Architecture and Sequence Specification

**Status:** PROPOSED DESIGN BASELINE — NOT APPROVED FOR IMPLEMENTATION  
**Parent:** PR #31 cross-document consistency review  
**Related:** PR #19 remediation; PRs #23/#24 import recovery; PR #28 implementation blueprint; PR #30 protocol clarifications.  
**Purpose:** Define one coherent end-to-end protocol and explicitly separate source authorization, discovery integrity and destination import recovery.

This specification consolidates the intended architecture after the ten cross-document findings. It is not a cryptographic wire-protocol standard, implementation authorization, governance approval or evidence that existing runtime code complies.

## 1. Core security decision

Every operation that resolves or reads a patient in a source tenant must be authorized by that source for a verified clinician and exact action, purpose, resource, destination and scope **before** patient-specific lookup results or data are disclosed.

This applies equally to:
- remote cross-hospital federation;
- local cross-branch/cross-tenant imports;
- discovery, demographic summary, allergy disclosure and import;
- synchronous routes, internal service calls and background jobs.

Node authentication and destination RBAC remain necessary but are never sufficient source authorization.

## 2. Three separate lifecycles

| Lifecycle | Authority owner | Main artifacts | What it authorizes |
|---|---|---|---|
| A. Source actor authorization and disclosure | Source tenant | Challenge, clinician assertion, replay claim, authorization decision, resource handle, source response manifest | One exact source-side action and disclosure |
| B. Discovery response integrity | Control plane/coordinator plus source-signed evidence | Optional central discovery receipt, source response IDs/digests, completeness evidence | Integrity/completeness of an already authorized discovery result only; never a patient read |
| C. Destination import and recovery | Destination tenant | Durable import operation, provenance marker, fencing generation, commit acknowledgement, pointer-sync state | Idempotent destination commit/recovery for one validated import operation |

No artifact crosses lifecycle boundaries as an implicit grant:
- a node API key does not authorize a clinician;
- a discovery receipt does not authorize a source read;
- a resource handle does not authorize import;
- an import operation ID does not authorize a new source disclosure;
- a destination commit acknowledgement does not prove pointer synchronization;
- an operator action cannot manufacture source authorization or bypass fencing.

## 3. Trust boundaries and responsibility

### Destination tenant
- Authenticates the local clinician through the existing tenant identity/session system.
- Derives actor subject, actor class and authn context from that session; callers cannot choose them.
- Issues a signed actor assertion only under the approved issuer/key model and only after local identity/affiliation checks.
- Enforces local destination permission (for example, patient write permission) as an additional control.
- Maintains durable import operation/provenance and pointer-sync recovery.

### Routing/control plane
- Authenticates registered nodes and applies partner/node eligibility and rate limits.
- May route opaque requests to eligible source endpoints.
- Must not expose candidate branch, patient existence, candidate count, MRN or patient metadata to the destination before source authorization.
- If an index is retained, it is a protected routing aid only. Its query API must not disclose candidate metadata or become an authorization oracle. Index tokenization, key custody and migration require separate approval.
- Stores only the minimum central receipt metadata needed for integrity/completeness; it is not a source of clinician identity or source policy decisions.

### Source tenant
- Owns challenge issuance, assertion verification, clinician mapping and current affiliation/status checks.
- Canonicalizes selector input itself and resolves it only after actor verification.
- Evaluates current source privacy policy and clinician permission for the exact patient/action/purpose/destination/scope.
- Owns source resource handles, replay claims, authorization decisions and source disclosure audit.
- Does not trust destination-supplied user IDs, roles, source patient IDs, selector hashes or policy decisions.

### Local cross-branch adapter
A local request must traverse the same logical source authorization interface as a remote request. The implementation may optimize transport, but it may not bypass source challenge, actor verification, policy evaluation, replay protection or source audit. Shared process memory, direct ORM access and control-plane privileges are not exemptions.

## 4. Canonical discovery sequence

1. Clinician authenticates to the destination tenant. The destination derives the clinician identity from its validated session.
2. Destination submits a discovery request containing protocol version, action, versioned purpose, selector type/value, minimum scope, destination identity and request correlation ID to the routing layer.
3. Routing layer authenticates the node and applies routing controls. It does not return source candidate metadata. It dispatches an opaque request to eligible source endpoints, or uses another formally privacy-reviewed mechanism.
4. Each source endpoint issues a short-lived source-owned challenge without confirming whether the selector matches a patient. Challenge response has a uniform non-identifying shape.
5. Destination issuer signs an assertion bound to that source challenge, source audience, exact destination, clinician subject, action, purpose, selector binding and scope. The assertion is not caller-constructed.
6. Source verifies node eligibility, issuer trust, signature, clinician mapping/status, challenge, exact claims, revocation freshness and one-time replay reservation. Invalid requests fail closed.
7. Only after successful verification does source canonicalize the selector and resolve candidate records internally.
8. Source evaluates each candidate against current clinician authorization, purpose, data category, destination, source policy and resource state.
9. Source commits required authorization/disclosure audit before returning protected data. Denied, no-match, privacy-suppressed and ambiguous results use the approved non-identifying response class; no unauthorized candidate handle is returned.
10. Source returns only authorized minimal data, source-signed integrity metadata and an opaque source resource handle bound to the decision and exact recipient. A handle is not a bearer authorization grant.
11. Coordinator aggregates authorized responses without exposing unauthorized source topology. Partial failures and operator diagnostics remain in protected audit/operations channels. An incomplete discovery cannot create an import-capable result.
12. If retained, the central discovery receipt binds the authorized response IDs/digests, recipient, selector/request correlation and completeness outcome. It proves response integrity/completeness only.

### Discovery sequence (conceptual)

```mermaid
sequenceDiagram
    participant C as Clinician
    participant D as Destination tenant
    participant R as Routing/control plane
    participant S as Source tenant
    C->>D: Authenticated session
    D->>R: Opaque discovery request
    R->>S: Route request (no candidate metadata)
    S-->>D: Source challenge (uniform response)
    D->>D: Derive actor from session; sign assertion
    D->>S: Assertion bound to challenge
    S->>S: Verify trust, actor, replay, purpose and destination
    S->>S: Canonicalize selector and resolve internally
    S->>S: Authorize candidate and current source policy
    S->>S: Commit source audit before disclosure
    S-->>D: Authorized minimal summary + bound handle
    D->>R: Aggregate authorized responses
    R-->>D: Integrity/completeness receipt (not authorization)
```

## 5. Canonical import sequence

1. Destination validates the discovery response integrity and any central receipt. This does not authorize source access.
2. Destination selects the exact source resource handle and creates/loads one durable import operation using the PR #23/#24 identity model: destination + validated source pointer/resource identity + source branch + protocol version. Demographics/ABHA are never idempotency proof.
3. Destination requests a separate source import challenge bound to the exact handle, destination, action=import, purpose, minimum scope and operation correlation.
4. Destination issuer derives the same current clinician from its authenticated session and signs a new assertion bound to the import challenge. A discovery assertion cannot be reused.
5. Source verifies the assertion, issuer/key, current clinician affiliation/status, handle binding, exact resource, current source policy, action, purpose, destination and replay state before any source patient/allergy read.
6. Source commits import authorization and disclosure audit before returning a source-authenticated payload manifest and the minimum authorized payload.
7. Destination verifies source signature/integrity, payload digest, schema, source/destination/resource/operation/scope binding, expiry and fencing generation.
8. Destination claims or resumes the durable import operation using compare-and-swap and current fencing generation.
9. Destination commits patient/allergy clone plus durable provenance marker and operation state atomically in the destination database. Stale workers cannot commit or publish.
10. Destination generates a destination-authenticated commit acknowledgement only after that transaction commits. The acknowledgement binds source, destination, operation, response digest/ID and fencing generation.
11. Source verifies the acknowledgement and records destination commit acknowledged. A request log or response-sent event is not a destination commit.
12. Pointer publication/synchronization runs as a separate fenced, recoverable stage. Its failure cannot cause a duplicate clone.
13. If source policy is revoked after destination commit, apply the PR #24 governed restricted/quarantine state; do not silently complete, leave ordinary active access or delete data outside approved retention workflow.

### Import sequence (conceptual)

```mermaid
sequenceDiagram
    participant D as Destination tenant
    participant S as Source tenant
    participant P as Destination PostgreSQL
    D->>S: Request import challenge for exact resource handle
    S-->>D: Import challenge
    D->>S: Fresh clinician assertion
    S->>S: Verify actor, replay, resource, purpose and current policy
    S->>S: Commit source authorization/disclosure audit
    S-->>D: Signed payload manifest + minimum payload
    D->>D: Verify manifest and durable operation/fencing
    D->>P: Commit clone + provenance + operation state
    P-->>D: Commit success
    D-->>S: Signed commit acknowledgement
    S->>S: Verify acknowledgement; record commit acknowledged
    D->>P: Fenced pointer sync (separate recoverable stage)
```

## 6. Canonical artifact/state matrix

| Artifact | Owner | Lifetime/expiry | Permitted use | Explicitly not permitted |
|---|---|---|---|---|
| Node credential | Control plane | Governed rotation/revocation | Authenticate partner service | Prove clinician identity or patient permission |
| Source challenge | Source | Short-lived, D-09 pending | Bind one action-specific assertion | Reveal match status or authorize by itself |
| Clinician assertion | Approved issuer | Short-lived, D-09 pending | Present verified actor claims to source | Be reused for another action/resource/destination |
| Replay claim | Source | Retention per D-10/D-12 | Enforce one-time reservation/idempotent same-operation handling | Be cache-only or bypassable after restart |
| Source authorization decision | Source | Audit retention D-12 pending | Record exact actor/purpose/resource decision | Substitute for current reauthorization after policy/status changes |
| Source resource handle | Source | Short-lived/rotatable policy pending | Refer to source-held authorized resource context | Become a bearer grant or authorize import |
| Source response manifest | Source | Payload/artifact retention pending | Verify exact response integrity and bindings | Authorize new source reads or different operation |
| Central discovery receipt | Control plane | Existing two-minute behavior is provisional | Integrity/completeness correlation for authorized results | Authorize any source read/import by itself |
| Durable import operation | Destination | Retention/governance pending | Coordinate idempotent clone/recovery | Authorize new source disclosure |
| Provenance marker | Destination | Governed clinical/audit retention | Prove exact source-to-destination clone relationship | Infer identity from demographics/ABHA |
| Commit acknowledgement | Destination, verified by source | Audit retention D-12 pending | Prove destination DB commit for exact operation | Prove pointer sync or global completion |
| Pointer-sync state | Destination/control plane | Operational retention pending | Retry fenced index publication | Trigger a second patient clone |

All actual lifetimes, key types, algorithms, canonicalization, retention and revocation SLAs remain governance/security decisions. The table intentionally does not convert current code defaults into approved protocol values.

## 7. Required state separation

### Source authorization/disclosure
Conceptual states: `CHALLENGE_ISSUED → ASSERTION_RESERVED → AUTHORIZED_AUDITED → DISCLOSURE_COMMITTED`, with explicit `REJECTED`, `DENIED_AUDITED`, `EXPIRED`, `REVOKED`, `FAILED_RETRYABLE` and `OUTCOME_UNCERTAIN`.

Only source-owned state and transactionally enforced replay claims govern source disclosure. A durable committed response may be retrieved only for the same operation/recipient under approved revocation and retention rules. Uncertain outcomes never trigger an unbounded new source read.

### Discovery integrity
Conceptual states: `REQUESTED → AUTHORIZED_RESPONSES_COLLECTED → COMPLETE` or `INCOMPLETE`. A receipt may be minted only for the approved complete outcome. It is not an authorization token.

### Destination import/recovery
Use the reviewed PR #23/#24 state machine and fencing design; do not create a parallel competing state model in this document. The destination operation is independent of source challenge consumption. A fresh source authorization can support only the same validated operation and cannot bypass source policy, quarantine or fencing.

## 8. Audit contract

At minimum, audit events must distinguish:
- node request accepted/rejected;
- challenge issued/expired/revoked;
- assertion rejected or replayed;
- clinician/affiliation verification result;
- source authorization allowed/denied;
- source disclosure committed / response uncertain;
- discovery complete/incomplete;
- import requested/authorized;
- payload manifest issued;
- destination commit acknowledged after verification;
- pointer sync pending/succeeded/failed;
- quarantine/restriction applied and governed resolution.

Each relevant event should bind protocol version, event/operation ID, source and destination branch/node, issuer-scoped actor subject reference, clinician mapping version, authentication assurance, action, purpose, resource reference, scope, source policy version, challenge/jti fingerprints, decision, response ID/digest, fencing generation and timestamp. Avoid raw bearer tokens, private keys and unnecessary PHI. Required source authorization audit must commit before protected disclosure; audit failure fails closed.

## 9. Mandatory privacy and abuse controls

- No unauthorized patient existence, match count, branch identity, MRN, demographic, allergy or candidate-specific error.
- Uniform response class/schema for no-match, denied, privacy-suppressed and ambiguous outcomes; threat-model timing, size, status and cache side channels.
- Source-side canonicalization; caller-supplied hashes are never identity proof.
- Protect low-entropy selectors against offline guessing; index tokenization/key custody and migration require explicit design approval.
- Rate limits by node, clinician and source; detect sequential probing and abnormal volume.
- No response cache may bypass current actor, source policy or revocation checks.
- Detailed source failures remain in restricted operations/audit channels, not caller-visible topology metadata.
- Partial discovery cannot authorize import.
- All local and remote paths use the same source authorization service contract.

## 10. Required tests and evidence

1. **Authorization order:** instrument source DB access; prove no patient-specific lookup/read occurs before actor verification and authorization.
2. **Privacy:** no-match, denied, suppressed, ambiguous and unavailable source outcomes do not reveal existence/topology via status, body, timing, size or retries beyond approved leakage.
3. **Issuer/actor:** forged subject/role/branch, wrong issuer/audience, revoked key, stale clinician mapping, wrong destination/action/purpose/scope all fail closed.
4. **Replay/concurrency:** two independent PostgreSQL sessions and separate workers race the same challenge/jti; exactly one reservation/disclosure succeeds.
5. **Audit:** source audit failure prevents disclosure; uncertain commit outcome cannot trigger a new source read.
6. **Import:** fresh import assertion required; receipt/handle/discovery assertion alone rejected; exact provenance and operation uniqueness enforced.
7. **Fencing:** stale worker cannot commit patient/allergies, acknowledgement or pointer publication after generation advances.
8. **Acknowledgement:** tampered/forged/wrong-operation/stale-generation acknowledgements rejected; lost acknowledgement does not duplicate clone.
9. **Policy revocation:** policy/affiliation/key revocation between challenge, assertion, source read, destination commit and acknowledgement follows explicitly approved outcomes.
10. **Local parity:** local cross-branch and remote federation enforce identical source actor checks; direct service calls, background tasks and root/V1 aliases covered.
11. **Migration/index:** tokenization rotation/backfill preserves lookup integrity, uniqueness and rollback without exposing raw selectors.
12. **Failure injection:** source audit, source response, destination commit, ack delivery, control-plane update and pointer-sync boundaries.

SQLite-only tests do not prove PostgreSQL concurrency correctness. Required evidence includes reproducible PostgreSQL integration tests, failure-injection logs, security review and privacy/clinical-safety sign-off.

## 11. Decisions still open

This specification does not decide:
- issuer authority and clinician identity proofing;
- clinician classes, professional registration evidence or mapping ownership;
- signing algorithms, key types, custody, rotation and trust onboarding;
- challenge/assertion/handle/manifest/receipt lifetime and revocation freshness;
- selector canonicalization and index tokenization/key management;
- purpose vocabulary, data scopes and partial-result policy;
- replayable payload storage/retention;
- audit retention, access and legal hold;
- formal D-11 approval for local cross-branch scope;
- emergency/break-glass scope (must remain disabled absent explicit approval);
- pilot criteria and D-14 final release gate.

Use the AUD-004 governance decision register and review checklist. No proposed default becomes approved merely by appearing in this document.

## 12. Implementation gate and stop conditions

Before runtime work:
1. Project owner accepts this consolidated protocol as the design baseline.
2. PR #19 follow-up defects (concurrent duplicate import, pointer-sync retry gap, demographic-based reuse) are resolved in an independently reviewed implementation design.
3. PRs #23/#24 recovery and fencing are accepted and reconciled with this state model.
4. Governance decisions and required product, clinical, privacy/legal, security and operational approvals are recorded with accountable names, roles, dates and evidence.
5. Threat model, data-flow review, route/service inventory and PostgreSQL test plan are approved.
6. A separate implementation authorization explicitly defines scope, rollout, rollback, disablement and operational ownership.

This document authorizes no runtime code, migration, feature flag, key generation, trust onboarding, partner enrollment, pilot, production patient-data access, merge, deployment, release or emergency federation.

**AUD-004 remains release-blocking.**
