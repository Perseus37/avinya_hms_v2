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

Do not store the bearer token. Do not log raw ABHA or unnecessary patient identifiers. Keep audit source-local and append-only. Distinguish requested, authorized, response-release-attempted, import attempted, destination-committed, and any independently verifiable acknowledgement. Do not claim network delivery, human receipt, or destination commit without corresponding evidence.

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


## 20. Approval decision register

**Purpose:** provide a reviewable record for the owners who must approve the AUD-004 trust model before implementation. This register is intentionally unapproved. No owner, approval date, or policy decision is inferred by this document's authors.

Record each decision in the project governance system and link the approved record here. A verbal agreement or a passing CI run does not close a decision.

| ID | Decision requiring explicit approval | Proposed starting position | Accountable approver(s) | Evidence required | Status |
|---|---|---|---|---|---|
| D-01 | Who is authorized to issue clinician identity assertions for a participating hospital? | Each hospital's Avinya backend, registered per branch, may issue workforce identity assertions for its own authenticated users | Hospital identity owner; Avinya identity/security owner | Written issuer-responsibility agreement, onboarding and termination process | PENDING |
| D-02 | What does the issuer's clinician statement actually guarantee? | It guarantees authenticated account identity, current local affiliation/status, and locally recorded actor class; it does not claim independent medical-license verification | Hospital identity owner; clinical governance | Signed claim-assurance definition and evidence-source inventory | PENDING |
| D-03 | Which clinician classes and actions are eligible? | Explicit doctor, nurse, and allied-health classes with action-specific allow-lists; no generic clinician wildcard | Clinical governance; source data owner | Approved actor-class/action/purpose/scope matrix | PENDING |
| D-04 | Is external professional registration verification mandatory for any action? | Treat local DoctorProfile registration fields as hospital-asserted only; require a trusted registry integration if independent verification is required | Clinical governance; legal/privacy owner | Jurisdiction-specific credential evidence and freshness policy | PENDING |
| D-05 | What source-side authorization policy controls remote access? | Source makes an independent decision for issuer, mapped actor, action, patient/resource, purpose, destination, and minimum scope | Source hospital clinical/data owner; security owner | Versioned authorization matrix, deny rules, policy ownership and test cases | PENDING |
| D-06 | Which purposes are permitted at launch? | A small versioned enum limited to explicitly approved continuity-of-care workflows; no arbitrary caller-supplied purpose strings | Privacy officer; clinical governance; legal owner | Approved purpose vocabulary, lawful-use mapping, and data-scope matrix | PENDING |
| D-07 | Which signing algorithm and key custody model are production requirements? | One fixed asymmetric algorithm supported by all participants; per-branch private key in managed KMS/HSM or equivalent protected signer | Security/platform owner; infrastructure owner | Cryptographic interoperability test, key custody/backup/rotation/revocation runbook | PENDING |
| D-08 | How are issuers, branches, keys, and partner relationships onboarded and revoked? | Out-of-band, dual-controlled source trust administration; no self-service trust based only on presented token metadata | Federation operations owner; security owner | Partner verification checklist, operator permissions, audit trail, revocation drill | PENDING |
| D-09 | What are assertion/challenge lifetimes, clock-skew limits, and urgent revocation SLAs? | Maximum 120-second assertion and challenge lifetimes as initial proposal; online status checks for high-risk actions; explicit urgent-revocation target | Security owner; partner operations; identity governance | Measured clock assumptions, status freshness design, tested SLA and escalation path | PENDING |
| D-10 | What retry/idempotency behavior is permitted after challenge claim or partial failure? | One-operation challenge; no challenge reset; retry only through a separately reviewed idempotency rule that cannot cause a second disclosure | Security/architecture owner; data owner | State-transition specification, concurrency tests, fault-injection evidence | PENDING |
| D-11 | Does AUD-004 cover local imports as well as remote discovery/import? | Do not silently narrow scope; explicitly decide whether every source-data access/import path requires source-verifiable human actor attribution | Security owner; privacy officer; clinical governance | Complete route/data-flow inventory and signed scope decision | PENDING |
| D-12 | What audit fields, retention, and access controls are required? | Source-local append-only actor and decision audit; no bearer token or unnecessary PHI; retention set by approved policy | Privacy officer; records/audit owner; security owner | Approved event schema, retention schedule, audit access model, failure-handling review | PENDING |
| D-13 | What is the emergency/break-glass boundary? | Emergency federation stays disabled and outside this implementation until a separate design is approved | Clinical-safety owner; security owner; privacy/legal owner | Separate threat model, emergency workflow, retrospective review and alerting requirements | PENDING |
| D-14 | What constitutes authorization to pilot and release? | Feature flag off by default; partner-by-partner non-production validation; no production enablement until all acceptance criteria and owner sign-offs pass | Security, clinical-safety, privacy, identity-governance, and operations owners | Recorded approvals, independent review, test evidence, runbooks, rollback plan | PENDING |

### 20.1 Required approval record

For each decision D-01 through D-14, record:

- Decision ID and exact approved wording.
- Decision: **APPROVED**, **REJECTED**, or **DEFERRED**. A deferred decision must include an owner and due date.
- Named accountable approver(s), role, and organization.
- Date, governance/ticket/minutes reference, and evidence links.
- Any approved deviation from the proposed default, including threat-model impact and required compensating controls.
- Version of this design and protocol schema to which the decision applies.

Do not mark a decision approved solely because a proposed default is repeated in a review comment. The accountable owner must explicitly accept the responsibility and evidence listed above.

### 20.2 Decision completion gate

Implementation planning may begin only when D-01 through D-14 have an explicit disposition and no unresolved decision affects the intended implementation scope. A deferred item blocks the affected capability; it cannot be converted into an implicit default by engineering.

Before any production pilot, all applicable decisions must be approved, AC-01 through AC-16 must have evidence, and the independent review and release approvals in Section 11 must be complete.

**Current decision state: all D-01 through D-14 are PENDING. AUD-004 remains open and release-blocking.**

## 21. Normative operation state and transaction boundaries

This section makes the challenge, replay, disclosure, and cross-tenant import semantics explicit. It is a proposed protocol requirement and remains subject to the approvals in Section 20.

### 21.1 Separate operation state machines

Discovery and import are separate protected operations. They must use distinct challenges, assertions, action values, and idempotency namespaces.

**Discovery**

`ISSUED → CLAIMED → AUTHORIZED → RESPONSE_RELEASE_ATTEMPTED`

`RESPONSE_RELEASE_ATTEMPTED` means the source durably recorded that it was about to emit the protected response; it does not prove that the destination received or displayed the bytes. The source must never label an HTTP response as delivered merely because the server began or completed a socket write.

Terminal alternatives are `DENIED`, `EXPIRED`, and `FAILED`. A challenge can transition out of `ISSUED` only once. An exact retry after a discovery response has been authorized or emitted must return status/receipt metadata only, never the cached patient summary or other protected payload. A caller that needs the protected payload again must obtain a new source challenge and clinician assertion. This avoids turning an idempotency key into a replayable disclosure capability.

**Import**

`ISSUED → CLAIMED → AUTHORIZED → TRANSFER_ATTEMPTED → DESTINATION_COMMITTED`

Terminal alternatives are `DENIED`, `EXPIRED`, `FAILED`, and `DESTINATION_REJECTED`. The import challenge is bound to one exact source pointer, destination, action, purpose, and minimum scope. A discovery challenge or discovery assertion must never authorize import.

The source must not report `DESTINATION_COMMITTED` merely because it sent a response. That state requires an authenticated destination acknowledgement tied to the same transfer/idempotency identifier and verified destination receipt. If acknowledgement is unavailable, retain an explicit indeterminate/attempted state for reconciliation; do not guess success or automatically create a second transfer.

### 21.2 Atomic source-side claim

The source must claim the challenge and assertion jti in one database transaction using uniqueness constraints that are effective across all workers and processes. The transaction must also persist a durable request/claim audit event. If any insert, uniqueness check, or required audit write fails, the transaction rolls back and no protected response is released.

A duplicate request must be classified as one of:
- **Exact idempotent retry:** same authenticated node, destination, request identifier, challenge, assertion jti, and request-body fingerprint; return only the previously persisted outcome permitted by the operation's retry policy.
- **Replay or mutation:** any changed identity, destination, action, purpose, resource, scope, assertion, or body fingerprint; deny and record a security event without returning patient-existence information.

Do not implement idempotency as a cache-only check or by making a consumed challenge reusable.

### 21.3 Authorization and disclosure audit ordering

After claim, the source evaluates issuer trust, clinician status/affiliation, source-side authorization, and privacy/data-use policy. These are distinct decisions and their outcomes must be independently represented in audit.

Before returning any patient-existence signal, demographic summary, or other protected discovery result, the source must durably persist the authorization decision, the exact response fingerprint, and a `RESPONSE_RELEASE_ATTEMPTED` event. This records the source's release attempt, not proof of network delivery or human receipt. If audit persistence fails, fail closed. A later transport failure remains an attempted release and must not cause automatic replay of the protected response.

For a denial, persist a denial reason code that does not expose sensitive patient information to the caller. External error responses must not distinguish patient-not-found from unauthorized or otherwise disallowed discovery where doing so would create an enumeration oracle. Challenge creation for discovery must use the same externally observable response shape and status for matching and non-matching selectors; avoid match-dependent timing, size, or metadata differences to the extent technically achievable. The source must not disclose selector normalization results or match counts before actor verification.

### 21.4 Import is a cross-system workflow, not a distributed transaction

The source and destination databases cannot be assumed to share an atomic transaction. Use a durable transfer identifier and an explicit state/reconciliation protocol:
1. Source atomically claims the import challenge/jti and records the authorization and transfer-attempt event.
2. Source creates or retrieves the same idempotent transfer package for that transfer identifier; it must not mint a second logical transfer on retry.
3. Destination validates the exact source pointer, destination, payload fingerprint, and import authorization, then commits the import and its local audit in one destination transaction.
4. Destination returns an authenticated acknowledgement containing the transfer identifier, destination receipt identifier, and committed payload fingerprint.
5. Source verifies the acknowledgement against the registered destination/node and records completion. If the acknowledgement is lost, retry only the acknowledgement/status lookup or reconcile by transfer identifier; do not blindly repeat the import.

The source audit must distinguish `AUTHORIZED`, `TRANSFER_ATTEMPTED`, and `DESTINATION_COMMITTED`. The destination audit must distinguish `RECEIVED`, `VALIDATED`, `COMMITTED`, and `REJECTED`. A source-side success response must not claim destination persistence until the acknowledgement has been verified.

### 21.5 Retention and operational recovery

Challenge, jti, idempotency, transfer, and acknowledgement records must have explicit retention periods approved under D-12. Expired challenge records may be cleaned up only after their replay-prevention window and audit obligations are preserved. Transfer reconciliation records must remain available long enough to resolve delayed acknowledgements and support incident investigation.

Operational tooling must expose counts and state age, not raw assertions, challenge secrets, patient selectors, or unnecessary PHI. Manual repair must be dual-controlled, audited, and limited to state transitions explicitly allowed by the protocol; operators must not be able to mark a transfer committed without verified destination evidence.

### 21.6 Required additional tests

- Concurrent duplicate discovery and import requests across separate workers and database connections.
- Exact retry versus changed-body, changed-destination, changed-scope, changed-purpose, and changed-jti cases; verify exact discovery retries return no protected payload.
- Failure injection between challenge claim, authorization audit, disclosure audit, response transmission, destination commit, acknowledgement transmission, and source completion audit.
- Lost acknowledgement followed by reconciliation, proving no duplicate destination import.
- Forged, stale, wrong-node, wrong-destination, and wrong-payload acknowledgement rejection.
- Cleanup racing with a late replay and with an in-progress transfer.
- Audit database outage at each required persistence boundary; no protected disclosure or false completion state may result.

**Implementation gate:** Sections 21.1–21.6 must be incorporated into the frozen protocol schema, threat model, and acceptance-test traceability before runtime implementation. These additions do not close any approval decision in Section 20.

## 22. Adversarial review: trust compromise, revocation, isolation, and dependency outages

This section records additional threat-model requirements identified during adversarial review. These are proposed controls; they do not constitute evidence that the current application implements them.

### 22.1 Issuer or signing-key compromise

Treat a trusted issuer or its signing key as a security boundary whose compromise can produce apparently valid clinician assertions. Signature validity alone is not sufficient.

Required controls:
- Each issuer/branch has a distinct signing identity and key. Compromise of one branch key must not permit assertions for another branch, issuer, audience, or destination.
- The source trust record binds issuer ID, organization, branch, registered node relationship, allowed audiences, allowed actions, key ID, algorithm, key validity, and status. Reject any mismatch even when the signature is valid.
- Issuer trust changes, key additions, key replacement, and emergency revocation require dual control, independent approvers, immutable audit, and out-of-band partner verification.
- A key marked compromised is denied immediately. Do not preserve an overlap/grace period for a compromised key. Planned rotation overlap is allowed only for explicitly active, non-compromised keys and a bounded window.
- Never automatically trust a new key merely because it appears in a token, an issuer URL, a JWKS response, or a request header. If a future JWKS integration is approved, pin the issuer endpoint and TLS identity out-of-band, validate key-set changes under a defined trust policy, and fail closed on unexpected issuer/key changes.
- Provide a tested issuer-wide and branch-key-specific kill switch. It must invalidate cached trust decisions within a documented maximum propagation time and produce an alert.
- Record the trust-registry version and key-status version used for every authorization decision so investigations can reconstruct the decision.

### 22.2 Clinician suspension, termination, and credential revocation

A signed assertion is a time-bounded statement, not a live employment or license check. A valid signature must not override a more recent suspension, termination, loss of affiliation, or credential revocation.

Required controls:
- Define distinct status dimensions: account active, workforce affiliation active, clinician class active, professional credential/license status (where required), issuer active, and signing key active. Do not collapse these into one boolean.
- For each action class, define which status dimensions are mandatory and their maximum acceptable age. High-risk access requires an online or equivalently strongly consistent status decision; a stale cache must not be treated as current.
- Emergency suspension/revocation must have a documented propagation target, monitoring, escalation, and proof test. If the target cannot be met, deny the affected protected operation.
- A status service timeout, stale response beyond policy, unknown status, conflicting status, or inability to establish current affiliation means deny. Do not fall back to the assertion's historical role/affiliation claims.
- License expiry and license revocation are different states. A locally stored expiry date cannot prove the external registry has not revoked a credential early.
- Reassignment between branches must revoke the old branch relationship before granting a new one, or use a controlled transition that never creates an interval in which both branches can assert unauthorized access.

### 22.3 Tenant and branch isolation invariants

The protocol must preserve the repository's schema-per-tenant and branch isolation model. A signed claim is input to validation, not a database routing instruction.

Required invariants:
- Resolve tenant schema, source branch, destination branch, and node identity from authenticated server-side context and trusted control-plane mappings. Never select a tenant schema from an untrusted assertion claim or request-body field.
- Validate that the authenticated node, registered issuer, issuer branch, destination branch, challenge, source pointer, and active federation relationship form one permitted relationship. Validate the relationship on every protected operation, not only when the challenge is created.
- Every database query and transaction must execute under the resolved tenant/branch context. No cross-tenant fallback query may search by local integer user ID, MRN, or clinician ID.
- External clinician subjects must be namespaced by exact issuer identity. No joins by email, display name, integer user ID, or non-unique registration number.
- Composite uniqueness and foreign keys must include the tenant/issuer/branch dimensions needed to prevent collisions. Tests must create deliberately colliding IDs and MRNs across tenants and branches.
- A destination change, branch transfer, node revocation, source-pointer reassignment, or trust relationship change between challenge issuance and execution invalidates the challenge.
- Source-side authorization must use the source's resolved patient/resource identity and policy context. Destination-provided patient identifiers or actor role claims must not select or broaden source authorization context.

### 22.4 Dependency outage and degraded-mode policy

The protocol is security-critical. Availability pressure must never silently downgrade authentication or authorization.

| Dependency unavailable or uncertain | Required behavior |
|---|---|
| Issuer trust registry / key status | Deny protected operation; no arbitrary key fetch or stale unknown-key acceptance |
| Clinician affiliation / suspension status | Deny when status freshness exceeds the approved action-specific limit |
| Source authorization policy | Deny; do not substitute destination RBAC |
| Source privacy/data-use policy | Deny; do not infer consent or permitted use |
| Challenge / replay persistence | Deny; do not use process-local memory as the authoritative replay store |
| Required source audit store | Deny before protected disclosure or transfer authorization |
| Destination acknowledgement/status | Keep transfer indeterminate; do not claim committed and do not blindly resend payload |
| Clock synchronization outside approved skew | Deny time-bound assertion/challenge operations |
| Revocation event delivery | Use bounded online status checks; alert on lag and deny affected high-risk operations |

No node-only fallback, stale-positive cache fallback, permissive circuit-breaker mode, or emergency-purpose bypass is permitted. Any future availability exception requires a separate threat model, explicit owner approval, narrow scope, and independent review.

### 22.5 Cache and consistency rules

- Cache only positive trust/status data with an explicit, action-specific maximum age. Denials and revocations must invalidate positive cache entries.
- A cache entry must be keyed by issuer, branch, subject, key ID, trust-registry version, status version, and action class; never key only by local integer user ID or issuer display name.
- Define propagation bounds for revocation and trust changes. If cache invalidation cannot be confirmed within the bound, the source must perform an authoritative lookup or deny.
- Do not cache a final patient-specific authorization decision across different resources, purposes, destinations, or scopes.
- Document transaction isolation and locking for challenge/jti claim, pointer validation, and transfer idempotency. A `SELECT` followed by an unprotected `INSERT` is not an atomic replay defense.
- Trust-registry and revocation updates must be monotonic with respect to compromise: a compromised/revoked key or issuer cannot be reactivated by a delayed stale replication event without a new dual-controlled approval and audit event.

### 22.6 Additional adversarial acceptance tests

- A valid signature from a key registered to the wrong branch, issuer, node, audience, or action is rejected.
- Compromised key revocation invalidates assertions immediately within the approved bound; planned rotation overlap does not apply to compromised keys.
- Delayed trust-registry replication cannot reactivate a revoked issuer/key or overwrite a newer status version.
- Issuer compromise/kill switch blocks new protected operations and generates an observable security alert.
- Clinician suspension, termination, branch transfer, and license revocation are enforced within the approved action-specific SLA.
- Status service outage, stale cache, conflicting status, and unavailable policy engine all fail closed.
- Cross-tenant and cross-branch colliding integer IDs, MRNs, clinician IDs, and external subjects cannot cause misrouting or identity substitution.
- A signed assertion with a forged tenant/schema/branch claim cannot influence database routing.
- Node revocation or partner relationship removal after challenge creation invalidates execution.
- Concurrent trust/key revocation and protected-operation execution have a defined serialization outcome; no operation may proceed using a trust state older than the approved freshness bound.
- Cache invalidation failure, clock drift, audit-store outage, and replay-store outage produce denial and operational alerts.
- No dependency outage or circuit-breaker state enables node-only, stale-positive, or emergency fallback behavior.

**Review outcome:** these controls must be reflected in the threat model, trust-registry design, operational runbooks, and acceptance-test traceability. They do not close D-01 through D-14. The design remains proposed, AUD-004 remains release-blocking, and runtime implementation remains gated on explicit approvals.

## 23. Main-branch implementation gap assessment (read-only review)

**Review basis:** read-only inspection of the repository `main` branch at the time this section was prepared. Files inspected: `backend/domains/federation/router.py`, `backend/core/dependencies.py`, `backend/domains/identity/models.py`, `backend/control_plane/models.py`, `backend/domains/federation/schemas.py`, and `docs/FEDERATION_SECURITY.md`.

This is a source-code gap assessment, not a penetration test, runtime test, or claim that every possible call path has been exhaustively searched. The findings below describe the inspected implementation and must be revalidated against the exact merge base before any implementation PR is opened.

### 23.1 Confirmed gaps

| ID | Severity | Inspected implementation fact | Required remediation / evidence |
|---|---|---|---|
| GAP-01 | **High — AUD-004 core** | `get_federated_node` authenticates an active `FederatedNode` using `X-Federation-API-Key`. The discovery route depends on this node dependency and has no signed clinician actor assertion dependency. | Add source-side verification of a challenge-bound assertion and independent clinician mapping/authorization before any patient-existence signal or protected summary. Negative tests must prove node key alone is insufficient. |
| GAP-02 | **High — AUD-004 core** | Discovery accepts a free-form `purpose: str` query parameter (length-limited only). The route explicitly blocks a list of emergency strings, but other values remain accepted and are passed into source transfer logging. | Replace free-form purpose with a versioned allow-listed enum and source policy mapping. Unknown values must be rejected; no string-based emergency deny-list as the primary authorization control. |
| GAP-03 | **High — patient enumeration** | The discovery route queries central pointers before any human actor verification and returns a distinct 404 when no pointer exists. When pointers exist, it proceeds to source reads and may return a demographic/allergy summary. | Do not return match/no-match information until actor verification and source authorization. Challenge creation must have indistinguishable external behavior for matching and non-matching selectors; add timing/response-shape and enumeration tests. |
| GAP-04 | **High — import actor provenance** | The local import route authenticates `current_user` with `RequirePermission("patients:write")`, but the source tenant audit writes `FederationTransferLog` with destination branch and `actor_user_id=None` in the source privacy decision. A destination-local integer user ID cannot be attributed as a source-local user. | Decide D-11 scope. If local import is covered, send a source-verifiable actor assertion for the authenticated destination user and record issuer-scoped subject separately from local user foreign keys. If excluded, document and approve the scope exception. |
| GAP-05 | **High — trust lifecycle** | The inspected `FederatedNode` control-plane model stores one API-key hash/prefix and an active flag. The inspected models do not provide issuer signing keys, issuer trust versions, key status/rotation history, or an external clinician subject mapping. | Implement an independently reviewed trust registry and key lifecycle before actor assertions can be accepted. Partner onboarding and revocation must be dual-controlled and audited. |
| GAP-06 | **Medium — dependency degradation** | `RateLimiter._check` fails open for non-authentication scopes when Redis is absent or errors. Federation discovery uses scope `fed_discover`, which does not match the fail-closed authentication prefixes. | Decide and implement an explicit policy for federation abuse-control dependency outages. At minimum, discovery must not silently lose its configured abuse limit; use a bounded local emergency limiter only if its distributed guarantees are documented, otherwise return 503. This is defense-in-depth, not a substitute for actor authorization. |
| GAP-07 | **Medium — audit attribution** | Discovery source transfer logs snapshot node identity but do not contain a verified clinician identity. The source privacy decision is evaluated with `actor_user_id=None`. | Extend the source audit schema with issuer-scoped subject, actor class/assurance, assertion/key identifiers (fingerprinted/minimized), source authorization decision, and protocol version. Never put a foreign tenant's integer user ID into a local-user FK. |

### 23.2 Existing controls to preserve

The inspected implementation also contains controls that must not be weakened during AUD-004 work:

- `get_federated_node` rejects missing, invalid, or revoked node keys with 401 and updates `last_used_at`.
- `get_current_user` validates tenant and branch claims, active local user status, and a live non-revoked `AuthSession`.
- Remote emergency discovery purposes are explicitly denied; `EMERGENCY_ALLERGIES_ONLY` sources do not return demographic discovery data.
- Source discovery re-reads patient data and evaluates source privacy/data-use policy with the source tenant's patient identity.
- Import re-reads source patient/policy, compares the submitted summary with current source demographics, copies clinical data from the source database, and writes a source-side request log before destination commit.
- Import uses the authenticated local destination user for destination-side patient/allergy creation audit fields.
- Control-plane tenant registry resolution is used to locate source databases; do not replace this with assertion- or request-supplied schema routing.

These controls are useful but do not satisfy AUD-004 because they do not independently verify the human clinician at the source.

### 23.3 Implementation order derived from the gaps

1. Freeze D-01 through D-14 and the protocol schema. Resolve D-11 explicitly before deciding whether local import is in scope.
2. Design and migrate the source trust registry, branch signing-key lifecycle, issuer-scoped clinician identity mapping, and source audit fields. Include dual-control administration and revocation.
3. Implement source-issued challenge persistence and atomic jti/challenge consumption. Discovery challenges must not disclose selector match state.
4. Implement destination assertion issuance behind the authenticated local user/session dependency. Do not accept caller-supplied actor identity fields.
5. Add source assertion verification and source-side clinician authorization as dependencies that run before pointer match disclosure or source patient reads.
6. Convert purpose to a versioned enum and define per-action/per-scope policy. Keep emergency federation denied.
7. Implement a separate import assertion/challenge path if D-11 includes local import; do not reuse discovery authorization.
8. Make federation abuse-control behavior explicit during Redis outage and add monitoring/alerts.
9. Add negative, concurrency, revocation, enumeration, tenant-collision, audit-failure, and outage tests. Require independent security review before pilot.

### 23.4 Review disposition

- GAP-01 through GAP-05 are direct prerequisites for closing AUD-004.
- GAP-06 is a separate defense-in-depth issue discovered during this review and should be tracked with an owner rather than silently folded into the actor assertion implementation.
- GAP-07 is required to make human attribution meaningful and auditable.
- No code, schema, migration, or runtime behavior was changed by this read-only assessment.
- All D-01 through D-14 remain pending. AUD-004 remains release-blocking.

## 24. Federation access-surface inventory and route coverage

**Review basis:** read-only inspection of `main` for `backend/domains/federation/router.py`, `backend/domains/patients/router.py`, `backend/domains/federation/models.py`, `backend/domains/federation/schemas.py`, `backend/control_plane/models.py`, and `backend/main.py`. This section records the route and call paths found in those files; it is not a repository-wide static-analysis certificate.

### 24.1 Federation router surface

The federation router is mounted on both the root FastAPI application and the mounted V1 application. Consequently, the same router operations are reachable through the root `/api/...` path and the `/v1/api/...` path. Both aliases must receive identical security dependencies and tests.

| Operation | Route | Current authentication / behavior observed | AUD-004 disposition |
|---|---|---|---|
| Register partner | `POST /api/federation/clients` | Tenant-local `RequirePermission("iam:write")`; creates a tenant-local `FederatedClient` and a control-plane `FederatedNode` API key record. | Administrative trust onboarding; keep separate from clinician assertion issuance. Must become dual-controlled trust-registry onboarding before signed assertions are trusted. |
| List partners | `GET /api/federation/clients` | Tenant-local `RequirePermission("iam:read")`. | Administrative metadata only; ensure secrets/public-key lifecycle metadata are appropriately restricted. |
| Revoke partner | `DELETE /api/federation/clients/{client_id}` | Tenant-local `RequirePermission("iam:delete")`; disables local client and corresponding node when present. | Preserve immediate node revocation; extend to issuer/key/clinician trust status and ensure failure between the two database commits is reconciled. |
| Publish local patient pointer | `POST /api/federation/patients/{patient_id}/publish-pointer` | Tenant-local `RequirePermission("patients:write")`; reads a patient in the caller's own tenant and calls `sync_patient_pointer`. | Not a remote patient disclosure path and does not itself require a foreign clinician assertion. Preserve local actor attribution and privacy policy. Its administrative ability to affect global discoverability still needs authorization/audit controls. |
| Discover remote patient | `GET /api/federation/patients/discover` | `get_federated_node` validates the node API key; no human actor assertion. Pointer lookup and 404 behavior precede human verification. | **Direct AUD-004 protected operation.** Require source-verified challenge-bound actor assertion before selector-match disclosure or patient reads. |
| Import remote patient | `POST /api/federation/patients/import` | Tenant-local `RequirePermission("patients:write")`; resolves a source pointer from submitted source MRN and reads the source tenant database. No node-key or clinician assertion is verified by the source in this route. | **Direct AUD-004 protected operation.** Must use a distinct import challenge/assertion bound to source pointer, destination branch, action, purpose, scope and transfer ID. |

The root and V1 route aliases are not separate authorization models; they are the same router mounted twice. Tests must exercise both URL prefixes to prevent a security dependency being applied to only one alias.

### 24.2 Patient lifecycle call paths affecting federation index

The inspected patient router calls `sync_patient_pointer` during:
- Patient registration.
- Patient update.
- Explicit pointer publication (through the federation router).
- Allergy charting or reactivation.

Patient deactivation directly deletes the matching `GlobalPatientPointer` from the control-plane database. Allergy deactivation currently changes the local `PatientAllergy.is_active` state but does not call `sync_patient_pointer`. This can leave the pointer's coarse `has_critical_allergies` metadata stale until another synchronization. Treat this as a pointer-integrity follow-up, not as evidence of unauthorized remote disclosure; source discovery still reads current source policy and allergy rows.

The inspected `sync_patient_pointer` implementation also catches broad exceptions, rolls back, and returns without propagating the failure. This overlaps the separately tracked AUD-002 remediation in PR #19. Do not duplicate or silently alter that remediation in the AUD-004 implementation; reconcile against the final PR #19 merged code before implementing pointer-related changes.

### 24.3 Model and data-boundary observations

- `FederationTransferLog` is stored in each tenant database, references a source-tenant `Patient`, and records node ID/key prefix/branch snapshots where available. It has no verified issuer-scoped clinician subject or assertion decision fields in the inspected `main` model.
- `FederatedNode` is a control-plane record keyed by branch with a single API-key hash/prefix and active flag. It is not a clinician trust registry.
- `FederatedClient` is tenant-local and stores a partner API-key hash/prefix. It is not an asymmetric issuer-key registry.
- `GlobalPatientPointer` is a control-plane locator (branch, source MRN, phone hash, ABHA, metadata), not a clinical record and not proof of requester authorization.
- The import route performs a direct server-side source-tenant DB read after resolving a pointer. It must not be treated as safe merely because it is not an HTTP call to a remote source API; source-side actor authorization still has to be enforced at the trust boundary.
- The patient router's local read, update, allergy and registration endpoints are tenant-local clinical operations. They continue to rely on local user/session authorization and privacy policy; this AUD-004 protocol should not be indiscriminately added to ordinary same-tenant reads.

### 24.4 Required route-level validation matrix

Implementation tests must cover at least:

1. Both root and V1 aliases for discovery and import: missing assertion, invalid signature, wrong issuer/branch/node/audience/action/purpose/scope, expired assertion, unknown/revoked key, suspended clinician, stale affiliation, replayed challenge/jti, and unavailable trust/status/audit dependencies all deny without disclosure.
2. Discovery: same externally observable challenge-creation shape/status for matching and non-matching selectors; no patient pointer lookup or source patient read before actor verification; exact retry does not redisclose a cached patient summary.
3. Import: source MRN/pointer supplied or modified by caller cannot substitute for a valid import challenge; assertion must bind the exact source pointer and destination branch; discovery assertion cannot authorize import; changed source data requires a new authorized flow.
4. Trust administration: partner registration/revocation, key rotation, issuer suspension, clinician mapping changes, dual-control approvals and partial failure between tenant/control-plane writes are audited and reconciled.
5. Local operations: ordinary same-tenant patient CRUD/allergy operations remain governed by local session and privacy controls; no foreign issuer assertion is required for these local-only paths.
6. Pointer lifecycle: patient opt-out, branch silo, patient deactivation, allergy severity escalation/de-escalation/deactivation, pointer synchronization failure and control-plane outage have deterministic, audited outcomes.
7. Alias parity: security tests run against both `/api` and `/v1/api` routes, not only one mount.

### 24.5 Coverage conclusion and sequencing constraint

The inspected federation router exposes six operations, of which discovery and import are direct protected patient-data operations. Pointer publication is a local-tenant operation with cross-tenant discoverability impact. Partner administration is a trust lifecycle surface. The patient router also mutates the discovery index as part of local patient/allergy workflows.

The highest-risk gap is not limited to the discovery route: **the import route independently reads source-tenant patient data and currently has no source-verified clinician assertion**. Discovery and import therefore require separate source authorization checks and separate challenge/action bindings.

PR #19 is still an unmerged remediation branch and contains the newer discovery-receipt integrity work. The source-code observations in Sections 23–24 describe the inspected `main` baseline, not the unmerged PR #19 implementation. Before AUD-004 runtime work starts, rebase/review the combined implementation against the final merged PR #19 code and preserve its receipt validation. Do not implement actor authorization against a stale version of the discovery/import flow.

No application code, migrations, configuration, or runtime behavior was changed by this route inventory. D-01 through D-14 remain pending; AUD-004 remains release-blocking.

## 25. Consolidated AUD-004 implementation contract (proposed; governance-gated)

This section translates the protocol design and the route inventory into an implementation boundary. It is a proposed engineering contract, not an authorization to code, a statement of approved policy, or evidence that the controls exist today. D-01 through D-14 remain pending. Any implementation PR must identify the approved dispositions it relies on and must stop where a required decision is still open.

### 25.1 Non-negotiable security invariants

1. A federation node API key authenticates a technical partner/node only. It never authenticates a clinician and never grants patient-data access by itself.
2. The source hospital makes the final disclosure decision. Destination-side role checks, privacy policy, signed claims, and node registration are inputs, not substitutes for source-side authorization.
3. No patient-existence signal, source pointer detail, patient summary, allergy information, or importable source record is released before source-side actor verification and action-specific authorization.
4. Discovery and import are distinct protected operations. They have different challenges, assertion action values, scopes, idempotency keys, audit outcomes, and retry rules. A discovery assertion cannot authorize import.
5. The source resolves the destination tenant, branch, and node from trusted server-side control-plane state. No caller-supplied assertion claim, request field, MRN, or pointer can select a database schema or bypass tenant resolution.
6. Human identity is namespaced by trusted issuer identity. Tenant-local integer user IDs, email addresses, display names, and caller-supplied clinician registration values are not globally unique identity keys.
7. Unknown, stale, conflicting, revoked, unverifiable, or unavailable authorization dependencies fail closed for protected disclosure. No node-only, stale-positive-cache, permissive circuit-breaker, or emergency fallback is allowed.
8. Source authorization, privacy/data-use policy, and technical node trust are separate decisions. All must allow the specific operation.
9. Audit failure before a protected response or transfer is released prevents release. A response write is recorded as a release attempt, not proof of delivery or human receipt.
10. Emergency/break-glass federation remains disabled unless separately approved and independently designed.

### 25.2 Logical component boundaries

| Component | Trust boundary and responsibility | Must not do |
|---|---|---|
| Destination application/API | Authenticates local user/session; obtains local authorization and purpose; initiates a challenge-bound protected operation. | Accept caller-supplied clinician identity as proof; choose source schema; reuse discovery assertion for import. |
| Destination assertion issuer | Server-side service behind authenticated local user context; resolves immutable issuer-scoped subject and local clinician status; signs only approved claims with branch key. | Expose signing key; sign arbitrary client-supplied claims; sign for suspended/inactive users. |
| Federation node identity | Authenticates the partner system and binds requests to an enrolled node. | Stand in for a human actor or authorize clinical disclosure. |
| Source trust registry | Maps approved issuer, branch, node, key ID/algorithm, audience, status, validity and allowed operation classes to a provisioned public key. | Trust arbitrary issuer/JWKS URLs or caller-provided key material. |
| Source challenge/replay service | Issues and atomically claims short-lived challenges and assertion IDs; enforces one-time semantics across workers/processes. | Depend on process-local memory or cache-only replay state. |
| Source actor verifier | Verifies signature, claims, challenge binding, issuer/key status, clinician mapping/status and freshness. | Treat a valid signature alone as clinical authorization. |
| Source authorization service | Evaluates clinician class, affiliation, action, purpose, patient/resource, destination and requested scope under source policy. | Reuse destination-side permission results as source authorization. |
| Source privacy/data-use service | Independently evaluates patient consent, source policy, age/other restrictions and data-use point. | Treat privacy permission as proof of clinician identity. |
| Source transfer/audit service | Durably records actor provenance, authorization decisions, privacy decisions and transfer state before release. | Record a foreign integer user ID as a source-local FK or log secrets/raw assertions. |
| Destination transfer receiver | Validates the source-bound transfer, commits imported data and destination audit, and returns authenticated acknowledgement. | Claim completion before durable commit and audit. |
| Control plane | Resolves tenant/branch/node/database registration and approved trust metadata. | Route to tenant schema using untrusted token or request claims. |

### 25.3 Proposed logical data records

Exact table names, ownership, database placement, indexes, retention and migration strategy require schema review and D-01/D-07/D-08/D-12 approval. The following are logical records, not mandated names.

| Record | Minimum fields / constraints |
|---|---|
| Issuer trust | Immutable issuer ID; organization and branch identity; registered node; audience; status; trust-registry version; validity window; onboarding approval references. |
| Issuer signing key | Issuer ID; key ID; algorithm; public key; status; valid-from/revoked-at; rotation/supersession reference; approval/audit reference. Private key remains outside the database in approved KMS/HSM custody. |
| External clinician identity | Issuer ID + immutable external subject UUID; local user mapping; clinician class; affiliation/status version; credential evidence/status; effective dates; revocation state. |
| Actor challenge | Random challenge ID/secret hash; operation; destination issuer/branch/node; source resource binding or protected selector binding; purpose/scope; creation/expiry; state/version; unique constraints. |
| Assertion replay claim | Issuer ID + assertion jti unique key; challenge ID; claim time; terminal outcome; transaction/audit correlation ID. |
| Source authorization decision | Actor subject; action; purpose; source resource; destination; scope; policy/version; decision; reason code; decision time/freshness metadata. |
| Protected transfer | Transfer/idempotency ID; source pointer identity; destination branch; action; payload fingerprint; state; source audit reference; destination acknowledgement fingerprint and timestamps. |
| Federation actor audit | Issuer-scoped subject; clinician class; issuer/key fingerprint identifiers; assertion/challenge correlation IDs; node; action/purpose/scope; source privacy decision; source authorization decision; outcome; protocol version; trust/status versions. No raw assertion, private key, bearer token, or unnecessary PHI. |

Database constraints must enforce uniqueness and atomic claim semantics at the authoritative database boundary. ORM-level “check then insert” without a unique constraint/transactional claim is insufficient against concurrent replay.

### 25.4 Protocol operation contracts

**A. Challenge creation**

- The destination requests a challenge for one named operation and a specific source/destination context.
- The source resolves node and destination identity from trusted enrollment state and validates the operation is enabled.
- The challenge is random, short-lived, single-use, purpose/action/scope bound, and stored durably.
- For discovery, challenge creation must not query or disclose selector match state. Match and non-match requests must have the same externally observable response schema/status and must not expose match-dependent metadata.
- A challenge cannot be changed to another operation, destination, source, resource, purpose, or scope after issuance.

**B. Destination actor assertion issuance**

- The issuer derives the actor from the authenticated local session and server-side user/clinician mapping.
- It verifies active account, live session, active affiliation, approved clinician class and local authority for the requested operation.
- The assertion contains only the approved protocol claims and references the exact challenge.
- Proposed claims include issuer, immutable subject, actor class, issuer branch, audience, issued/not-before/expiry times, unique jti, challenge ID, request/transfer ID, action, purpose, source/destination binding, scope, authentication context and relevant status versions.
- The issuer signs with its registered branch key. No signing key or signing endpoint is exposed to the browser/mobile client.
- Proposed maximum lifetime is 120 seconds, subject to D-09 approval and clock-skew analysis.

**C. Source verification and authorization**

- Resolve the expected destination node/branch from server-side state before trusting assertion claims.
- Verify allowed algorithm, trusted issuer/key, key status, signature, audience, time bounds, challenge binding, jti uniqueness, operation/action, purpose, scope and destination/source bindings.
- Atomically claim challenge and jti, with durable audit correlation, before protected work. Concurrent requests using the same challenge/jti must yield at most one authorization execution.
- Resolve the external clinician subject under the exact trusted issuer namespace; check current account, affiliation, clinician class, credential and revocation state at the required freshness.
- Evaluate source-side action-specific authorization and source privacy/data-use policy independently.
- On any unknown, stale, conflicting or unavailable critical dependency, deny without disclosing patient existence or protected data.

**D. Discovery**

- Verify actor and source authorization before pointer match disclosure and source patient reads.
- Keep selector binding protected: challenge/assertion must bind the normalized selector without returning normalized selector details or match metadata to an unauthenticated caller.
- A complete discovery response may create the existing short-lived import-integrity receipt only after all source outcomes satisfy the receipt protocol. Partial discovery must never mint an importable receipt.
- Persist source authorization, privacy decision and response fingerprint before attempting response release.
- Record `RESPONSE_RELEASE_ATTEMPTED`; do not claim that the destination received or displayed the response.
- An exact retry may return non-sensitive operation status/receipt metadata only. Redisclosure requires a new challenge and assertion.

**E. Import**

- Import requires its own challenge/assertion with action `patient.import` (final vocabulary subject to D-06), exact source pointer, destination branch, transfer ID, purpose and minimum required scope.
- The source re-reads the current source patient and privacy policy. Caller-supplied demographics are comparison evidence only, never the authoritative imported record.
- Discovery receipt integrity remains an additional payload/pointer consistency control; it is not clinician authorization.
- Source records a durable transfer attempt and audit before releasing the source payload.
- Destination commits imported records and destination audit atomically, then returns an authenticated acknowledgement bound to transfer ID, destination, payload fingerprint and commit receipt.
- Source marks `DESTINATION_COMMITTED` only after validating that acknowledgement. Lost acknowledgement leaves the transfer indeterminate and requires reconciliation; do not blindly repeat a non-idempotent import.
- If D-11 includes local import, apply the same source-verifiable actor model to local source data access. If it excludes local import, record the approved scope exception and its compensating controls.

### 25.5 Transaction and failure boundaries

- Challenge claim, jti claim and corresponding audit correlation must be atomic at the source authority boundary.
- Source authorization/privacy decision and response fingerprint must be durably recorded before protected response release.
- Destination data commit and destination audit must be in one destination transaction.
- Source and destination databases are not assumed to share a transaction. Use durable transfer IDs, authenticated acknowledgements and reconciliation.
- Trust/key/clinician revocation must invalidate affected authorization caches and outstanding challenges according to the approved freshness/revocation SLA.
- A partial failure between tenant-local partner revocation and control-plane node revocation must leave a detectable, fail-closed state and a reconciliation record; never report full revocation if only one side committed.
- Source audit outage, replay-store outage, trust-registry outage, clinician-status outage, privacy-policy outage, unacceptable clock drift, destination acknowledgement uncertainty and tenant resolution failure must have explicit deny/indeterminate outcomes. No permissive fallback.
- Operational repair must be dual-controlled, audited and idempotent. Never manually delete replay claims or rewrite transfer state without an approved repair record.

### 25.6 Implementation PR sequence and ownership gates

| Stage | Proposed PR boundary | Exit evidence |
|---|---|---|
| 0 | Governance/protocol freeze (no runtime changes) | D-01..D-14 dispositions, threat model, claim schema, purpose vocabulary, D-11 scope and named owners. |
| 1 | Trust registry and key lifecycle | Migrations, dual-control admin workflow, KMS/HSM integration, key rotation/revocation tests, trust-registry audit. |
| 2 | Clinician identity mapping and destination issuer | Immutable issuer-scoped subjects, explicit actor classes, local session binding, no caller-supplied identity tests, key custody evidence. |
| 3 | Source challenge, verifier, replay and authorization services | Atomic uniqueness/concurrency tests, signature/claim negative tests, revocation freshness and fail-closed outage tests. |
| 4 | Discovery integration | Both API aliases protected; enumeration tests; source policy and actor audit; no cached-summary redisclosure; existing discovery receipt tests preserved. |
| 5 | Import integration | Separate import challenge; source pointer/resource binding; destination acknowledgement; lost-ack reconciliation and idempotency tests. |
| 6 | Adversarial and operational validation | Cross-tenant isolation, key compromise, clinician revocation, dependency outages, clock drift, audit outage, concurrency, incident/recovery runbooks. |
| 7 | Controlled pilot proposal | Feature flag off by default until explicit approval; partner onboarding evidence; monitoring; rollback plan; independent security review. |

Each runtime PR must be small enough to review independently, contain migrations and rollback strategy where relevant, include negative tests, state which governance decisions it implements, and avoid bundling unrelated pointer/AUD-002 changes.

### 25.7 Required test suites

- **Issuer and key:** wrong issuer/branch/node/audience/key ID/algorithm; unknown, expired, revoked and compromised keys; key rotation overlap rules; trust-registry version mismatch; delayed replication cannot reactivate a revoked key.
- **Clinician:** inactive/locked/suspended user; revoked session; terminated or stale affiliation; branch transfer; wrong clinician class; expired professional credential; external registry unavailable or stale; issuer subject collision across tenants.
- **Challenge/assertion:** expired/future assertion; wrong action/purpose/resource/scope/destination; modified selector/pointer; wrong request/transfer ID; missing challenge; replayed jti; concurrent duplicate claims; changed assertion under same jti; clock drift.
- **Discovery privacy:** matching and non-matching selector response parity; no pointer query before actor verification; no partial-result receipt; no summary redisclosure on retry; source privacy denial; audit outage; all sources unavailable vs partial source failure.
- **Import integrity:** discovery assertion rejected for import; source pointer substitution rejected; source data changed after discovery; destination mismatch; forged acknowledgement; lost acknowledgement; destination commit/audit rollback; exact idempotent retry vs changed payload.
- **Tenant isolation:** same local user ID/MRN in multiple branches; forged branch/schema claims; node revoked after challenge; source pointer moved/revoked; no cross-tenant fallback; both root and V1 route aliases.
- **Operations:** trust/key/clinician revocation during concurrent requests; Redis outage and cache invalidation; DB failover; source audit/replay store outage; dual-control repair; metrics and alerts contain no raw tokens or unnecessary PHI.

### 25.8 Explicit non-goals and change control

- No microservice split, new identity provider, global clinician directory, emergency access enablement, or change to ordinary same-tenant patient CRUD is implied by this contract.
- No change to current patient privacy defaults or data-sharing scope is implied.
- No new trust relationship is created merely by registering a federation node or API key.
- Do not use this contract to bypass D-01..D-14. If an implementation detail requires an unresolved decision, stop and obtain the named approval before coding it.
- PR #19 must be reviewed/merged under its own approval process before AUD-004 runtime work is rebased onto the resulting mainline. Preserve the discovery receipt safeguards; do not build against the older main baseline.
- AUD-004 remains release-blocking until implementation, adversarial validation, operational evidence and explicit release authorization are complete.

No runtime code, migration, configuration, or application behavior is changed by this proposed contract.

## 26. Governance decision pack — proposed dispositions for D-01 through D-14

This section is a decision aid for accountable owners. It does not approve any decision. Every item remains **PENDING** until the accountable role records an explicit decision with evidence. Proposed defaults are conservative starting points for review, not binding policy.

### 26.1 Decision register with recommended defaults

| ID | Decision requiring approval | Recommended default for approval consideration | Accountable approver | Evidence required before closure |
|---|---|---|---|---|
| D-01 | Who may issue clinician assertions and represent a hospital? | The participating hospital's Avinya tenant backend is the issuer for its own branch. Each branch has a distinct issuer identity and signing key. No node API key or client app may issue assertions. | Hospital security/IT owner, with Avinya security architect | Issuer ownership record; branch-to-issuer mapping; documented authority delegation; partner agreement. |
| D-02 | What authentication assurance is required for the human actor? | Require authenticated active user, live non-revoked session, MFA for high-risk cross-hospital access, and server-side actor mapping. Session presence alone is not professional authority. | Hospital IAM/security owner | Authentication policy; MFA enforcement evidence; session revocation behavior; threat-model sign-off. |
| D-03 | Which clinician classes may act? | Explicit allow-listed classes (doctor, nurse, allied-health professional) with action-specific scopes. No generic staff/clinician wildcard. Start with minimum class/action combinations required by the approved use case. | Hospital clinical governance owner | Approved clinician-class taxonomy; scope/action matrix; authorization scenarios; clinical governance sign-off. |
| D-04 | How is professional registration/licensure verified? | Existing local DoctorProfile fields are hospital-asserted evidence only. Where an action requires a licensed professional, require a trusted registry verification or documented hospital credential-verification process with freshness and expiry. | Hospital medical/clinical governance owner | Registry integration evidence or approved manual verification SOP; evidence freshness; expiry/revocation handling; audit trail. |
| D-05 | Who authorizes the clinician to access a source patient's data? | Source hospital performs independent, action/resource/purpose/destination-specific authorization. Destination permissions and source privacy policy are separate required decisions. | Source hospital data-protection/privacy owner and clinical governance owner | Source authorization matrix; privacy-policy mapping; deny-case walkthroughs; owner approval. |
| D-06 | Which purposes and actions are allowed? | Replace free-form purpose strings with a versioned closed enum and explicit action-purpose-scope compatibility matrix. No emergency/break-glass purpose in the initial enabled vocabulary. | Clinical governance owner and privacy/legal owner | Versioned vocabulary; approved use-case mapping; API compatibility plan; prohibited-purpose tests. |
| D-07 | Which signing algorithm and key custody model are approved? | Ed25519 where supported by all participants and approved libraries; otherwise ES256 after cryptographic review. Dedicated per-branch asymmetric key in managed KMS/HSM; private key never stored in application DB or shared with node clients. | Avinya security/cryptography owner and hospital security owner | Cryptographic review; KMS/HSM design; key access policy; backup/recovery and compromise runbook; rotation/revocation test. |
| D-08 | How are issuers, partners and keys onboarded/changed? | Out-of-band verified onboarding with dual approval for trust creation, key replacement, issuer suspension and reactivation. No dynamic trust from arbitrary JWKS URLs or self-asserted issuer claims. | Federation trust administrator plus independent security approver | Partner identity verification; dual-control workflow; immutable approval log; key fingerprint confirmation; revocation drill. |
| D-09 | What are assertion/challenge lifetimes and revocation freshness requirements? | Proposed maximum 120 seconds for assertions and challenges; online/strongly consistent checks for high-risk actions; immediate key-compromise denial; clinician-status freshness and propagation SLA defined per action before pilot. | Avinya security owner and participating hospital IAM owner | Clock-skew analysis; measured status propagation; cache-age limits; kill-switch test; signed-off SLA. |
| D-10 | How are retries, replay and distributed transfer outcomes handled? | Atomic durable one-time challenge/jti claims; distinct discovery/import namespaces; stable transfer IDs; destination commit acknowledgement; indeterminate state plus reconciliation after lost acknowledgement. No blind replay of protected payloads. | Federation technical owner and database/platform owner | Concurrency test results; unique-constraint review; failure-injection evidence; lost-ack reconciliation runbook. |
| D-11 | Does AUD-004 cover local imports as well as cross-branch federation? | Conservative default: yes, if local import accesses another branch/tenant's source patient record. Any exclusion must be explicit, narrow, documented, and supported by equivalent source-side attribution/authorization controls. | Product owner, clinical governance owner and privacy/legal owner | Written scope decision; data-flow map; abuse-case review; compensating-control approval for any exclusion. |
| D-12 | What audit content, retention and access controls apply? | Immutable/tamper-evident source and destination audit with issuer-scoped subject, action, purpose, resource reference, decisions, transfer correlation and trust/status versions. Never store raw bearer assertions or private keys; minimize PHI; retention follows approved legal/contractual schedule. | Privacy/legal owner, records owner and security owner | Retention schedule; access matrix; integrity verification; audit-failure behavior; deletion/legal-hold analysis. |
| D-13 | Is emergency/break-glass access in scope? | No. Keep emergency federation disabled and out of the initial assertion purpose vocabulary. Design and approve it separately with heightened identity, reason capture, notification, review and expiry controls. | Clinical governance owner and privacy/legal owner | Explicit out-of-scope approval; evidence it remains disabled; separate future threat model if proposed. |
| D-14 | What authorizes pilot and production release? | No pilot or release until required decisions are closed, acceptance criteria pass, independent security review is complete, partner runbooks and monitoring are ready, and a named release authority approves. Feature flag remains off by default. | Product/release owner plus security and clinical governance approvers | Signed release checklist; CI/security evidence; operational readiness; partner sign-off; rollback/incident exercise; explicit release authorization. |

### 26.2 Decision dependencies and implementation stop points

- **D-01, D-07 and D-08** are prerequisites for trust registry and key lifecycle implementation. Do not create a production trust registry or provision partner keys before approval.
- **D-02, D-03 and D-04** are prerequisites for clinician identity mapping and assertion issuance. Do not infer clinician class or license assurance from existing tenant profile fields.
- **D-05 and D-06** are prerequisites for source-side authorization and purpose enforcement. Do not preserve the current free-form purpose field as the final security contract.
- **D-09 and D-10** are prerequisites for challenge/replay implementation and transfer-state behavior. Proposed 120-second lifetimes must not silently become production constants.
- **D-11** determines whether local import is in scope. Until approved, implementation planning must assume the broader, safer scope and must not ship a bypass.
- **D-12** is a prerequisite for audit schema, retention jobs and operational access policy.
- **D-13** must be explicitly closed as out of scope for the initial release; emergency access remains disabled regardless of silence.
- **D-14** is a final gate, not a decision that can be inferred from passing CI, PR approval, or a pilot request.

A decision may be marked “deferred” only if the affected capability is explicitly disabled and the dependency is recorded. “Accepted by engineering”, “covered by tests”, “existing behavior”, or “approved verbally” is not a governance disposition.

### 26.3 Required decision record format

For each D-01..D-14, record:
- Decision ID and exact question/version.
- Status: PENDING, APPROVED, REJECTED, or DEFERRED.
- Chosen option and rationale, including deviations from the proposed default.
- Accountable approver's name, organization and role.
- Approval date and governance/ticket/meeting reference.
- Evidence links (policy, partner agreement, threat model, test, runbook or technical review).
- Affected protocol/design version and implementation stages.
- Residual risk, compensating control, expiry/revisit date, and feature-disable condition.

No approver identity or approval evidence is supplied by this engineering document. All fourteen decisions remain PENDING after adding this decision pack.

### 26.4 Recommended review order

1. Product, clinical governance and privacy owners resolve D-11, D-03, D-05 and D-06 first because they define the permitted use case and data-access authority.
2. Hospital IAM/security and Avinya security owners resolve D-01, D-02, D-04, D-07, D-08 and D-09.
3. Federation engineering/platform owners propose D-10 and D-12 implementation evidence for approval.
4. Clinical governance and privacy owners explicitly confirm D-13 remains out of scope.
5. Release authority records D-14 only after implementation and validation evidence exists; D-14 cannot be pre-approved by this design PR.

This review order is a coordination suggestion, not a transfer of accountability. The named approvers must be appointed by the project governance process.

No governance decision is closed by this section. No runtime code, migration, configuration, trust entry, signing key, feature flag or application behavior is changed.
