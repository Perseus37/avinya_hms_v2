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


## 13. Fit with the current Avinya HMS identity implementation

A review of the current `main` branch shows the following relevant implementation facts:

- Human users are tenant-local in `backend/domains/identity/models.py` (`User`, `AuthSession`, `Role`, `Permission`, and optional `DoctorProfile`). User status includes ACTIVE, SUSPENDED, LOCKED, and DEACTIVATED.
- `DoctorProfile` stores a clinical ID, qualifications, specialization, medical council, registration number, and registration-valid-until date. These are tenant-entered records; their presence alone does not prove that an external professional registry verified the clinician or that the registration remains valid.
- Normal user authentication in `backend/core/dependencies.py:get_current_user` validates a tenant-specific JWT, tenant/branch claims, an active user, and a non-revoked/unexpired `AuthSession`.
- Federation authentication in `get_federated_node` validates only the control-plane node API key and active node. It does not authenticate a human user.
- The current federation discovery route depends on `get_federated_node`, accepts a caller-supplied purpose string, and evaluates source privacy/data-use policy with `actor_user_id=None`. That privacy evaluation is not a substitute for human identity verification or source-side clinician authorization.
- The inspected identity and control-plane models do not currently provide a cross-tenant OIDC issuer trust registry or a clinician federation identity mapping.

These are the current code facts relevant to the design; they are not assertions that no other external identity integration exists outside the inspected paths.

## 14. Recommended initial trust model for this codebase

**Recommendation for the first implementation phase:** use each participating hospital's own Avinya tenant backend as its clinician assertion issuer, with an independently provisioned asymmetric signing key per branch. Do not introduce a federation-wide identity broker as a prerequisite for the first version unless partner onboarding or enterprise SSO requirements demonstrate that it is necessary.

This recommendation is conditional on each participating hospital formally accepting responsibility for authenticating its workforce and promptly revoking users. The source trusts the registered hospital issuer for the identity statement; it does not thereby claim that the source independently verified the clinician's medical license.

### Destination-side assertion issuance

- Add a dedicated assertion-issuance service behind the existing authenticated tenant user context. It must receive the authenticated `User` from `get_current_user`; never accept a user ID, email, role, doctor name, or registration number as caller-supplied identity evidence.
- Require `User.status == ACTIVE`, a live non-revoked `AuthSession`, an active local account/affiliation, and a locally authorized action.
- Require a clinician credential/profile appropriate to the requested action. For doctor-only operations, validate the local `DoctorProfile` and its registration expiry, but treat the registration fields as hospital-asserted unless a trusted external registry check is implemented. Do not infer that every clinician is a doctor; define nurse/allied-health actor classes and permitted scopes explicitly before supporting them.
- Use an immutable issuer-scoped external subject identifier. The current integer `User.id` is tenant-local and should not be treated as globally unique; a future immutable UUID subject is preferable. Never use email or display name as the subject.
- Sign with a dedicated per-branch private key held in a managed KMS/HSM or equivalent protected signing service. Do not reuse the tenant JWT secret, federation API key, database secret, or a shared symmetric secret. The private key must not be returned to the client.
- Keep assertion issuance server-side. The browser/mobile client may carry the signed assertion to the federation operation but cannot create or modify it.

### Source-side issuer trust and clinician mapping

- Provision each accepted issuer out-of-band through a control-plane operator workflow with dual control, audit, and partner verification. Store issuer ID, registered branch/node relationship, allowed audiences/actions, public signing keys, key status, validity windows, and revocation state in the control plane.
- Do not trust arbitrary `iss`, `kid`, `jku`, `x5u`, or caller-supplied JWKS URLs. Public keys must be pinned/registered by the source's trust administration process.
- Namespace the external subject by issuer. The source must not join a foreign `sub` to its local `users.id` or assume matching user IDs across tenant databases.
- Define a source-side policy mapping from trusted issuer + clinician class/credential evidence + action + purpose + resource + scope to allow/deny. A destination role claim is context only and cannot grant source access by itself.
- For clinician suspension/termination, define a maximum revocation propagation time. Until a reliable status/revocation mechanism is available, use very short assertions and deny high-risk actions when issuer status cannot be checked. Short expiry alone is not a substitute for a workable urgent-revocation process.

### Purpose and operation separation

The current discovery endpoint's free-form `purpose` query parameter must not be copied into the signed assertion as trusted authorization. Replace it with a versioned enum and an explicit source policy mapping. Discovery, import, and any future emergency disclosure are distinct actions and must not share a broad reusable capability.

For discovery, the source may not yet know the patient resource ID. Use a two-stage request binding:
1. The source receives the selector over the authenticated node channel and creates a short-lived challenge bound to the source-computed normalized selector fingerprint, authenticated node, destination, action, purpose, and requested scope. The challenge response must not reveal whether a patient exists.
2. The destination issuer signs the challenge for the authenticated clinician. The source validates the assertion and challenge before returning any patient match or demographic summary. Once a specific source pointer is selected, the discovery receipt binds that pointer and the exact response as already described above.

For import, create a separate challenge bound to the exact source pointer, destination, import action, continuity-of-care purpose, and permitted demographic/allergy scope. Do not reuse the discovery assertion or challenge for import.

## 15. Important design limits and release blockers

- A signed assertion proves that a trusted issuer made a statement about a clinician. It does not independently prove the clinician is licensed, currently employed, or clinically entitled to access a particular patient's record unless the trust model and source checks establish those facts.
- The source's privacy/data-use decision and the source's clinician authorization decision are separate controls. Both must pass. Do not overload `evaluate_tenant_data_use` or pass a foreign clinician ID as `actor_user_id` to make the audit appear human-attributed.
- The current tenant-local `Role`/`Permission` model has no demonstrated cross-tenant clinician authorization mapping. This mapping and its policy owner must be designed before implementation.
- A source-issued challenge and one-time replay record require a carefully defined state machine for discovery retries. The existing discovery receipt is an import-integrity mechanism and is not a substitute for the clinician assertion challenge.
- The source audit schema must be extended deliberately to capture issuer-scoped actor identity and the separate authorization decision. Do not place foreign user IDs into existing local-user foreign keys.
- Current local import behavior must be assessed separately: a local authenticated user can initiate import, but the source cannot currently verify that human actor through the remote node key. If AUD-004 is intended to cover all patient-data access, local import needs a source-verifiable actor assertion too; otherwise document and approve a narrower scope explicitly.

**Recommended decision:** approve the per-hospital backend issuer model for a first implementation only after identity-governance owners accept the hospital as the issuer of workforce identity claims, and after the source-side authorization matrix, key-provisioning procedure, and revocation SLA are specified. Keep any external professional-license verification as a separately declared assurance level; never imply it from local profile fields alone.


## 16. Implementation contract (proposed; not yet approved)

This section converts the design into an implementation boundary. It is not permission to start runtime work. The API paths and storage names below are logical contracts; final route names and physical schema names must be settled during the implementation plan.

### 16.1 Actors and authority

| Principal | May assert | Must not decide |
|---|---|---|
| Destination human user | Nothing directly; authenticates to the destination tenant | Source access or source privacy policy |
| Destination Avinya issuer | Authenticated subject, local affiliation/status, authentication context, locally permitted action | Source patient authorization |
| Destination federation node | Its registered node identity and transport channel | Human identity or clinician entitlement |
| Source trust registry | Which issuers/keys are trusted and their allowed relationships | Whether a specific patient disclosure is clinically justified |
| Source authorization service | Whether this verified actor may perform this exact action on this resource for this purpose/scope | Whether the destination's signature is valid |
| Source privacy/data-use policy | Whether the requested use/disclosure is permitted by source policy | Human identity or clinical role |

No component may collapse these independent decisions into a single authorization flag without retaining the decision provenance.

### 16.2 Logical protocol operations

The first implementation must expose equivalent operations for:

1. **Create challenge:** authenticated node submits action, purpose, destination, requested scope, and either a selector (discovery) or exact source pointer (import). Source normalizes and binds the request. Response contains only an opaque challenge ID, unpredictable challenge value, expiry, and protocol version; it must not disclose patient existence.
2. **Issue actor assertion:** destination tenant backend accepts the challenge in an authenticated clinician session, verifies local user/session/affiliation/eligibility, and signs a one-operation assertion. Private signing material never leaves the issuer.
3. **Execute protected operation:** node submits the assertion and challenge reference. Source independently verifies node, issuer, signature, claims, challenge state, actor status/mapping, authorization, privacy policy, and audit requirements before returning any protected result or accepting an import.
4. **Record outcome:** source records whether the operation was requested, denied, authorized, disclosed, import attempted, or import completed. Completion must be recorded only when the corresponding durable operation actually completes.

The source must derive node ID, issuer trust, destination relationship, and source resource from trusted records. It must not accept these as authoritative merely because they appear in request JSON or token claims.

### 16.3 Challenge state machine

The challenge state machine must be explicit and persisted consistently:

| State | Meaning | Allowed transition |
|---|---|---|
| ISSUED | Source created a bound, unexpired challenge | CLAIMED, EXPIRED, REVOKED |
| CLAIMED | A valid assertion/request atomically claimed it | AUTHORIZED, DENIED |
| AUTHORIZED | Source policy and privacy checks passed and audit was durably recorded | COMPLETED, FAILED |
| COMPLETED | Protected disclosure/import operation completed | Terminal |
| DENIED | Verification or policy denied the operation | Terminal |
| FAILED | An authorized operation failed before completion | Terminal; retry requires a new challenge unless a specifically reviewed idempotency rule applies |
| EXPIRED / REVOKED | Challenge is no longer usable | Terminal |

Implementation invariants:

- A challenge is bound to one node, destination branch, action, purpose, scope, and selector fingerprint or exact source pointer.
- Challenge claim and assertion jti consumption must be atomic and protected by database uniqueness constraints. Concurrent requests across workers/processes must produce at most one successful claim.
- A challenge cannot be rebound, reset to ISSUED, or reused for another action or resource.
- Discovery retries must use a documented idempotency key and must not permit a second disclosure. A retry may retrieve only the same already-authorized result under a bounded policy; it must not repeat authorization under a changed actor, selector, destination, or scope.
- Import idempotency must be keyed to the exact source pointer, destination, and approved operation. It must not make a new actor assertion reusable for a different import.
- Failure to persist challenge state, replay state, authorization decision, or required audit means deny/no protected response.

### 16.4 Proposed minimum persistence model

Final names and normalization are implementation decisions, but the following logical records are mandatory:

- **TrustedIssuer:** immutable issuer identifier, registered organization/branch and node relationship, status, permitted audiences/actions, onboarding evidence/reference, activation and retirement timestamps.
- **TrustedSigningKey:** issuer FK, key identifier, public key/material or secure key reference, algorithm, intended use, validity window, status, rotation/revocation metadata. Unique issuer + key identifier.
- **ExternalClinicianMapping:** issuer-scoped subject, recognized actor class, evidence/assurance level, source-side status, effective dates, revocation metadata. Unique issuer + external subject. Never reference a foreign tenant's integer user ID as a local FK.
- **ActorChallenge:** opaque challenge identifier, cryptographic challenge digest, node/destination binding, action, purpose, resource/selector fingerprint, scope, expiry, state, claim metadata, and timestamps. Do not persist unnecessary PHI or the raw signed assertion.
- **ConsumedAssertion:** issuer + jti uniqueness, challenge relationship, expiry/retention metadata, and outcome. Enforce replay protection in the database, not only in process memory.
- **FederatedActorAudit:** source-local verified actor and issuer identity, node/destination, action, purpose, resource reference, scope, policy decision/version, assertion key ID, correlation/challenge identifiers, timestamps, and distinct operation outcome.

All tenant-specific foreign keys must remain within their owning tenant schema. Control-plane trust records must not become a backdoor for cross-tenant clinical data access. Migration downgrade behavior, indexes, uniqueness constraints, retention, and data minimization require review.

### 16.5 Error and disclosure contract

Externally visible errors must not reveal whether a patient exists, whether a clinician mapping exists, or which trust check failed. Use stable generic denial responses for protected discovery paths and correlation IDs for operator investigation. Internally, retain bounded reason codes without bearer tokens or unnecessary PHI.

- Invalid/missing/replayed assertion, unknown issuer/key, stale status, challenge mismatch, unauthorized actor, privacy denial, or audit failure: no patient match, demographic summary, allergy detail, or import side effect.
- Trust/status/authorization dependency unavailable: fail closed. Do not fall back to node-only authentication or stale positive authorization.
- A successful discovery response is allowed only after the source has verified the clinician and completed all required policy/audit checks. Existing discovery receipt issuance remains conditional on complete source discovery and is an additional import-integrity control, not an actor credential.
- An import response must distinguish accepted/attempted from durably completed. Source-side audit must never imply destination commit success without a verifiable completion signal.

## 17. Security acceptance criteria (release-blocking)

AUD-004 is not closed until every applicable criterion below has automated evidence and independent review.

| ID | Acceptance criterion | Required evidence |
|---|---|---|
| AC-01 | Node authentication and human actor authentication are both mandatory for every protected remote patient-data operation | Integration tests proving node-only and actor-only requests are denied |
| AC-02 | Only explicitly onboarded issuers and registered active keys can issue accepted assertions | Tests for unknown, disabled, expired, revoked issuer/key and untrusted key IDs |
| AC-03 | Signature verification uses a fixed allow-listed asymmetric algorithm and strict token parsing | Negative crypto tests: unsigned, none, algorithm confusion, malformed headers, invalid signature |
| AC-04 | Actor subject is immutable and issuer-scoped; it is never interpreted as a local tenant user ID | Cross-tenant collision tests and schema/FK review |
| AC-05 | Destination issuer derives identity from authenticated server-side session and current local user state | Tests reject caller-supplied subject, user ID, role, doctor name, or registration number |
| AC-06 | Source independently maps and authorizes the clinician for the exact action, patient/resource, purpose, destination, and scope | Allow/deny matrix tests including wrong patient, wrong branch, role, purpose, and scope |
| AC-07 | Source privacy/data-use policy and clinician authorization are separate mandatory decisions | Tests prove either denial blocks disclosure/import and audit captures both decisions |
| AC-08 | Discovery and import use separate source-issued challenges and operation-specific assertions | Tests reject discovery assertion for import and vice versa |
| AC-09 | Challenge and jti replay prevention is atomic across concurrent workers and database connections | Concurrency tests prove at most one claim succeeds |
| AC-10 | Expiry, clock skew, issuer/key revocation, clinician suspension/termination, and affiliation changes are enforced to documented SLAs | Boundary, stale-status, and revocation propagation tests |
| AC-11 | Source audit is durable before disclosure/authorization and distinguishes request, decision, disclosure, attempt, and completion | Fault-injection tests for audit DB failure and destination commit failure |
| AC-12 | Trust registry, key rotation, emergency revocation, and partner onboarding are dual-controlled and audited | Operational runbook plus permission and audit tests |
| AC-13 | Errors, logs, traces, and metrics contain no raw assertion, private key, bearer credential, or unnecessary PHI | Automated log-capture and redaction tests |
| AC-14 | Existing tenant/branch isolation, node-key revocation, privacy policy, and discovery-receipt protections remain intact | Full federation regression suite and tenant-isolation tests |
| AC-15 | No fallback path grants node-only access; emergency/break-glass remains disabled | Negative tests for missing dependencies and all emergency-purpose variants |
| AC-16 | Security, clinical-safety, privacy, identity-governance, and operations owners approve the protocol and rollout | Recorded sign-off and versioned threat-model review |

A green CI run is necessary but not sufficient. Manual security review, operational evidence, partner interoperability, and named owner approval are release gates.

## 18. Proposed defaults for decision review

These are recommended defaults to make the approval discussion concrete. They are **not approved policy** and must not be silently treated as settled requirements.

| Decision | Proposed default | Approval owner / unresolved point |
|---|---|---|
| Issuer | Each hospital's Avinya backend, separately registered per branch | Identity governance must accept hospital responsibility for workforce identity |
| Signing | Ed25519 where supported by the production cryptographic stack; otherwise ES256 after interoperability review | Security/platform owner to select and pin one algorithm |
| Key custody | Per-branch asymmetric key in managed KMS/HSM; non-exportable private key preferred | Infrastructure/security owner to confirm service and recovery model |
| Subject | Random immutable issuer-scoped UUID, independent of email and local integer IDs | Identity owner to define provisioning and lifecycle |
| Actor classes | Explicit doctor, nurse, and allied-health classes with action-specific eligibility; no generic clinician wildcard | Clinical governance to define permitted classes and scopes |
| License assurance | Hospital-asserted unless a trusted professional registry integration is separately approved | Clinical/legal owner to define required evidence and freshness |
| Assertion lifetime | Maximum 120 seconds, with a small documented clock-skew allowance | Security owner to approve operational clock assumptions |
| Challenge lifetime | Maximum 120 seconds; one operation and one destination | Security owner to approve retry and idempotency semantics |
| Purpose | Versioned enum, initially limited to approved continuity-of-care workflows | Privacy/clinical owners to approve exact values and policy mapping |
| Revocation | Online source checks for high-risk actions; documented urgent clinician/key revocation SLA | Partner operations and identity governance to commit to an achievable SLA |
| Emergency access | Disabled; separate future design and approval | Explicit independent security and clinical-safety sign-off required |

## 19. Implementation sequencing and exit criteria

After the decisions in Section 12 and proposed defaults in Section 18 are approved, implementation should proceed in isolated, reviewable increments:

1. **Protocol and threat model freeze:** finalize claim schema, challenge state machine, actor classes, source authorization matrix, purpose enum, error contract, and trust onboarding.
2. **Trust registry and key lifecycle:** implement control-plane issuer/key records, dual-control onboarding, rotation, revocation, and audit; no patient disclosure endpoint changes yet.
3. **Destination issuer:** implement server-side assertion issuance from authenticated user/session context and protected per-branch signing keys.
4. **Source verifier and challenge store:** implement strict verification, atomic challenge/jti consumption, external clinician mapping, and source authorization decision.
5. **Protected discovery integration:** require verified actor before any patient-existence signal or demographic response; retain existing complete-discovery receipt rule.
6. **Protected import integration:** require a distinct import challenge/assertion bound to exact source pointer and destination; preserve idempotency and source/destination audit semantics.
7. **Adversarial validation:** execute the complete acceptance matrix, concurrency/fault-injection tests, tenant isolation tests, and independent penetration/security review.
8. **Controlled rollout:** feature flag off by default, partner-by-partner non-production validation, operational monitoring and rollback plan, then explicit multi-owner release approval.

Exit requires all AC-01 through AC-16 satisfied, no unresolved High/Critical security findings, documented revocation and incident runbooks, and explicit release approval. Until then AUD-004 remains open and release-blocking.
