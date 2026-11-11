# AUD-004 — Signed Clinician Actor Assertion Protocol

**Status:** Proposed security design; not implemented  
**Finding:** AUD-004 — federation authenticates the hospital/node but does not independently verify the human clinician requesting patient information  
**Safety:** Remote emergency federation remains disabled. This document does not authorize deployment or emergency-mode enablement.

## 1. Objective

A federation API key proves that a request came through a registered hospital node/service. It does not prove which clinician initiated the action, whether that clinician is currently affiliated with the requesting branch, or whether the clinician is authorized for the stated purpose and patient.

Every protected cross-branch action must be attributable to (a) an authenticated destination node, (b) a cryptographically verified clinician identity issued by a trusted identity authority, and (c) an independent source-side authorization decision scoped to the exact action, patient, purpose, destination, and data scope.

This is an engineering design, not legal advice or a compliance certification.

## 2. Trust boundaries

1. **Clinician:** authenticated by the destination hospital workforce IdP or an explicitly trusted clinician credential authority.
2. **Destination application:** obtains a short-lived signed actor assertion after authenticating the clinician and checking current local affiliation/status.
3. **Destination federation node:** authenticates using its existing node credential and forwards the assertion unchanged.
4. **Source federation gateway:** independently validates the node credential and actor assertion; caller-supplied actor headers are never trusted.
5. **Source authorization service:** resolves the external clinician identity through a pre-established trust mapping and evaluates source-side policy.
6. **Source audit store:** records verified actor, node, request, purpose, decision, and outcome in the source tenant's immutable audit trail.
7. **Trust/key registry:** source-controlled configuration of accepted issuers, signing keys, algorithms, audiences, and revocation status.

A valid node credential is necessary but never sufficient. A valid assertion is also necessary but never sufficient: source-side authorization remains mandatory.

## 3. Proposed signed assertion

Use a compact signed token (JWS) with a configured asymmetric algorithm. EdDSA/Ed25519 or ES256 are candidates; select only after confirming cryptographic-stack support, key custody, interoperability, and independent review. Never accept an algorithm selected freely by the token header, the 'none' algorithm, shared symmetric keys across unrelated hospitals, or algorithm fallback.

The protected header should contain:
- typ: a protocol-specific media type/version, e.g. hms-clinician-actor+jwt;
- alg: one configured asymmetric algorithm;
- kid: signing-key identifier resolved only within the trusted issuer's registered key set.

Required signed claims (names illustrative; freeze a versioned schema before implementation):

| Claim | Meaning and validation |
|---|---|
| iss | Exact registered issuer identifier for the destination hospital/IdP; no wildcard matching. |
| sub | Stable issuer-scoped clinician identifier; never a display name or email address. |
| actor_type | Fixed value identifying a human clinician, not a service account. |
| home_tenant / home_branch | Clinician's authenticated organization and branch, checked against trusted issuer registration and current affiliation. |
| aud | Exact source federation service/resource audience. |
| iat, nbf, exp | Issued-at, not-before, and expiry. Proposed maximum lifetime: 2 minutes, subject to review; use small documented clock skew. |
| jti | Cryptographically random unique assertion identifier for atomic replay prevention. |
| request_id | Correlation identifier for one source-issued request challenge. |
| action | Exact operation, e.g. patient.discover or patient.import. |
| purpose | Enumerated protocol-controlled purpose; free-form text is not an authorization purpose. |
| resource | Exact source patient/pointer or source-issued opaque resource handle; never a broad wildcard. |
| destination | Exact receiving tenant/branch and registered node identity. |
| scope | Minimum requested data categories and operations from a versioned allow-list. |
| authn | Authentication context, such as MFA method/time and IdP assurance level, where the issuer can attest it. |
| authz | Optional issuer-side role/entitlement snapshot for audit context only; it never replaces source authorization. |

Do not place unnecessary PHI in claims. Exclude patient name, phone, ABHA, diagnosis, and clinical details. Prefer an opaque source-issued resource handle. A caller-computed selector hash alone is not proof of patient identity.

## 4. Source-issued request challenge

Before the destination obtains an assertion for a protected action, the source should issue a short-lived unpredictable challenge through the authenticated node channel. Store the challenge server-side and bind it to:
- authenticated node ID and requesting branch;
- exact destination branch;
- action and enumerated purpose;
- exact source patient/resource pointer, or a source-side selector resolution;
- permitted data scope;
- unique request ID and expiry.

The trusted destination issuer signs an assertion containing the request ID and matching action, purpose, resource, destination, and scope. The source compares every value with its own challenge record. The destination cannot broaden scope by changing the assertion or request body.

If a challenge is not feasible for an operation, an independently reviewed alternative must provide equivalent source-verifiable resource binding.

## 5. Source verification sequence — fail closed

1. Authenticate the federation node; resolve node ID and branch from trusted control-plane state, never request fields.
2. Load the exact issuer trust record; require issuer active and permitted for the authenticated node/branch relationship.
3. Resolve kid only inside that issuer's configured key set. Check key status, validity, intended use, and revocation. Never fetch arbitrary key URLs from token headers.
4. Verify the JWS signature using the configured algorithm and strict token/header parsing.
5. Validate token type/version, issuer, audience, destination node/branch, action, purpose, resource, scope, timestamps, and required assurance claims.
6. Verify clinician identity mapping and current affiliation/status. A historical assertion cannot override a currently revoked or suspended clinician where trusted status data is available.
7. Atomically claim the challenge and jti using a uniqueness constraint/transaction. Reject replay, concurrent duplicate use, expiry, mismatched request ID, or a challenge bound to another node/resource/action.
8. Re-evaluate source-side patient privacy/data-use policy and source-tenant authorization for the verified clinician, purpose, resource, and minimum scope.
9. Durably write the source-side audit decision before releasing protected data or authorizing an import. If required audit persistence fails, deny.
10. Execute only within the authorized scope and record the final outcome. Authorization is not proof that a transfer completed.

Any missing, invalid, ambiguous, unavailable, or stale trust/status/authorization dependency results in denial. Never downgrade to node-only authentication.

## 6. Clinician identity and authorization mapping

The source must not assume that a destination clinician's local user ID exists in the source tenant. Establish an explicit trust relationship:
- registered issuer → registered organization/branch;
- issuer-scoped clinician subject → stable external clinician identity;
- trusted identity attributes/credential evidence → source-recognized clinician class and current status;
- source policy → action/purpose/resource/scope decision.

A destination hospital's assertion that a user is a doctor is insufficient unless the source explicitly accepts that hospital/IdP as an authority for that claim and defines credential, registration, and revocation checks. If professional registration or license status is required, define the trusted registry and freshness requirement separately; do not infer it from job title or role name.

Destination RBAC may prevent an unauthorized user from initiating a request, but source-side policy must independently decide whether the remote actor may access the source record.

## 7. Replay, revocation, key rotation, and time

- jti and challenge consumption must be atomic under concurrent requests. A best-effort cache check is insufficient unless consistency and failure behavior are proven.
- A challenge/assertion is a single-operation credential. Never reuse it for another patient, purpose, destination, or action.
- Maintain issuer/key activation, retirement, compromise, and revocation state. Unknown kid, revoked key, inactive issuer, or unverifiable key status means deny.
- Support explicit key-rotation overlap and a tested emergency key-revocation procedure.
- Enforce strict iat, nbf, and exp checks with a small configured skew. Monitor clock drift; excessive drift fails closed.
- Define maximum revocation propagation time for clinicians and issuers. High-risk actions require online source status/authorization checks, not only a token snapshot.
- Never log raw assertions, private keys, bearer credentials, or unnecessary PHI.

## 8. Source-side audit requirements

Each source-side event should include:
- verified issuer and issuer-scoped clinician subject;
- authenticated federation node ID, key identifier/prefix, and requesting branch;
- destination branch/node;
- action, enumerated purpose, resource reference (minimized/pseudonymous where possible), and authorized scope;
- assertion key ID, protocol version, jti fingerprint, request/correlation ID, and challenge ID;
- authentication assurance context and status-check timestamp/source;
- source authorization policy/version and allow/deny reason code;
- event time and outcome.

Do not store the bearer token. Do not log raw ABHA or unnecessary patient identifiers. Keep audit source-local and append-only. Distinguish requested, authorized, disclosed, import attempted, and import completed so audit never overstates what happened.

If source audit persistence fails, no protected data is released and no import is authorized. If a later destination commit fails, the source record remains an accurate request/authorization/attempt record, not proof of completed destination persistence.

## 9. Emergency / break-glass boundary

Emergency federation remains disabled. Actor assertions alone do not authorize enabling it.

A future emergency path requires a separate design and review covering:
- verified clinician identity and required assurance;
- exact patient, destination, emergency purpose, and minimum data scope;
- source-issued emergency grant with expiry, revocation, and atomic one-time consumption;
- explicit reason and narrowly scoped authorization policy;
- enhanced immutable audit, immediate alerting, retrospective review, and abuse detection;
- privacy/data-use policy and applicable legal basis;
- independent security and clinical-safety approval.

No emergency grant ID, request header, role label, or caller-supplied boolean can substitute for these controls.

## 10. Required security tests

### Assertion and issuer validation
- missing assertion, malformed token, unsigned token, unsupported algorithm, algorithm confusion, invalid signature;
- unknown/inactive issuer, unknown/revoked kid, key outside validity, rotation overlap, compromised key;
- wrong token type/version, issuer, audience, destination node/branch, or home branch;
- missing/invalid clinician subject, wrong actor type, stale/revoked affiliation, insufficient authentication assurance.

### Scope and purpose
- missing/unknown purpose, wrong purpose, purpose substitution;
- wrong action, resource, patient, destination, or scope;
- broadened data categories or challenge reuse for another operation;
- source privacy opt-out, tenant policy denial, and source authorization denial.

### Time and replay
- expired, future-dated, not-yet-valid assertion; excessive clock skew;
- replay of same jti, challenge, or signed assertion;
- concurrent replay race across workers/processes;
- expired/revoked challenge and challenge bound to another node.

### Audit and failure handling
- source audit unavailable or transaction failure;
- source authorization/status registry unavailable;
- no protected response/import on any required-control failure;
- audit distinguishes request, authorization, disclosure, and completion;
- logs/errors do not expose bearer assertion, raw ABHA, or unnecessary PHI.

### Regression
- existing node-key authentication/revocation remains enforced;
- tenant/branch isolation and source-local immutable audit remain intact;
- no fallback to node-only access when assertion validation is unavailable;
- emergency purposes remain denied even with a valid clinician assertion.

## 11. Rollout and release gates

1. **Threat-model review:** security owner approves issuer model, actor lifecycle, trust registry, challenge binding, and failure modes.
2. **Identity governance:** participating hospitals agree who may issue assertions and how employment, credential, and license revocation propagate.
3. **Protocol freeze:** publish versioned schema, algorithms, key custody/rotation, audience/resource semantics, and status freshness requirements.
4. **Isolated implementation:** no changes mixed into PR #19; feature flag defaults off; emergency mode remains hard-disabled.
5. **Independent security review:** cryptographic verification, replay races, trust onboarding, audit atomicity, and tenant isolation reviewed independently.
6. **Staged validation:** negative security tests, integration/concurrency tests, operational monitoring, and partner interoperability tests pass.
7. **Explicit release approval:** security, clinical-safety, privacy, and operational owners sign off. Passing CI alone is not approval.

## 12. Decisions required before coding

- Which authority issues assertions: each hospital's managed IdP, a federation identity broker, or a recognized clinician credential authority?
- What trusted evidence establishes clinician identity/professional status, and how fresh must it be?
- How are external clinician subjects mapped to source-recognized identities and authorization policy?
- Which operations require source-issued challenges, and how is an exact patient resource safely resolved first?
- Which asymmetric algorithm and key custody/rotation standard are supported by all participating nodes?
- What are the maximum assertion/challenge lifetime and acceptable clock skew?
- What source-side authorization model and purpose vocabulary are approved?
- What availability and revocation-propagation targets apply to issuer, clinician status, and authorization services?
- Which jurisdiction-specific audit fields and retention schedule are approved by legal/privacy owners?

**Do not begin implementation until these decisions are recorded and approved.**
