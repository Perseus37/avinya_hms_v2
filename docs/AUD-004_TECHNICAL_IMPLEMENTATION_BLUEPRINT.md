# AUD-004 Technical Implementation Blueprint

**Status:** PROPOSED — DESIGN ONLY — NOT AUTHORIZED FOR RUNTIME IMPLEMENTATION  
**Parent:** AUD-004 governance review checklist, PR #27 head `66f564ed5a5ddcc7cef62b9da038a1de136efe0f`  
**Finding:** AUD-004 — node authentication does not independently identify or authorize the human clinician requesting cross-branch patient data.

This blueprint translates the signed clinician actor assertion design into an implementation sequence and reviewable component boundaries. It is not a production protocol freeze. All unresolved governance decisions remain unresolved. It changes no runtime code, migration, configuration, key, trust record, or application behavior.

## 1. Security objective and scope

For every operation that reads another branch's source patient record, the source branch must verify all of the following before disclosing protected data or authorizing an import:

1. An authenticated destination federation node/service.
2. A cryptographically verified human clinician assertion from a trusted issuer.
3. Current issuer and clinician affiliation/status.
4. Source-side authorization for the exact clinician, action, purpose, patient/resource, destination and minimum data scope.
5. Current source privacy/data-use policy.
6. Atomic one-time challenge and assertion replay protection.
7. Durable source-side audit of the authorization decision.

This applies to:
- cross-hospital federation discovery and import;
- local cross-branch/cross-tenant discovery and import where another branch's patient record is read.

It does not expand this boundary to ordinary same-branch patient CRUD. D-11 project direction is YES; formal product, clinical and privacy/legal approval remains PENDING. Emergency/break-glass federation remains disabled.

Node API keys, destination RBAC, same corporate ownership, caller-supplied actor IDs/roles, and privacy policy alone are insufficient.

## 2. Existing code boundaries to preserve

The current code review identifies these integration points; implementation must re-verify paths and symbols against the final merged mainline before coding:

- Human identity and sessions: `backend/domains/identity/models.py`, `backend/core/dependencies.py:get_current_user`.
- Federation node authentication: `get_federated_node`; this proves node/service identity only.
- Federation router and patient discover/import endpoints: currently mounted through root and V1 API applications. Every security check must be identical across both aliases.
- Control-plane models/database: existing federation node and global patient pointer records. Neither is a clinician trust registry or proof of source authorization.
- Source patient privacy/data-use policy and tenant-local audit mechanisms must remain authoritative.
- PR #19 changes discovery/import integrity and receipt behavior. AUD-004 implementation must be based on the final merged PR #19 code, not an older branch snapshot.
- PRs #23/#24 separately specify import idempotency/recovery. They must be reconciled with actor assertion challenges and source authorization; neither substitutes for AUD-004.

Do not implement against a stale code snapshot or duplicate PR #19 changes.

## 3. Proposed logical components

### 3.1 Destination issuer adapter

A tenant-local service that:
- accepts only an authenticated local human session;
- resolves the user, active status, branch affiliation and approved clinician classification server-side;
- verifies the requested source-issued challenge and refuses caller-substituted claims;
- applies destination-side initiation permissions as an additional control;
- issues a short-lived asymmetric assertion only for an exact challenge;
- records issuance metadata without logging the bearer assertion.

The issuer must never accept a client-provided `sub`, clinician role, home branch, purpose, scope, or destination as authoritative. It derives or validates them from authenticated server-side records and the source challenge.

### 3.2 Source trust registry

Source-controlled, tenant-scoped trust configuration with:
- exact issuer identifier and registered organization/branch;
- accepted key IDs, public keys, algorithm and key-use constraints;
- issuer/key activation, validity, suspension and revocation;
- mapping from issuer-scoped clinician subject to source-recognized external clinician identity;
- accepted clinician classes and credential/registration evidence requirements;
- explicit partner/node relationship and permitted destination constraints;
- dual-control audit for create, rotate, suspend, revoke and reactivate.

No arbitrary JWKS URL, token-header key URL, wildcard issuer, shared symmetric partner secret, or caller-provided trust configuration. Initial key custody and exact cryptographic algorithm remain D-07 decisions; do not hard-code Ed25519 or ES256 before approval.

### 3.3 Source challenge and replay service

A source-tenant durable service that:
- creates unpredictable one-operation challenges;
- binds each challenge to authenticated node, requesting branch, destination branch, action, purpose, resource/selector binding, permitted scope, protocol version and expiry;
- stores challenge state and unique assertion `jti` claims transactionally;
- supports atomic one-time consumption under concurrent workers;
- rejects expired, mismatched, replayed or revoked challenges;
- fails closed if the durable replay store is unavailable.

Discovery and import use distinct action values and distinct challenges. A discovery assertion cannot authorize import.

### 3.4 Source authorization and policy adapter

A source-side decision point that evaluates:
- verified issuer and clinician identity;
- current clinician status and accepted credential evidence;
- source-recognized clinician class;
- exact action and versioned purpose;
- source patient/resource;
- exact destination branch/node;
- requested and allowed data categories;
- patient privacy/data-use policy and applicable tenant rules.

It returns a structured allow/deny decision with policy version and stable reason code. It must not trust destination role claims as the authorization decision. Any dependency outage or ambiguous mapping denies access.

### 3.5 Source audit writer

A source-local append-only/tamper-evident writer records the verified actor, issuer, node, destination, action, purpose, resource reference, scope, challenge/jti fingerprints, authentication assurance, status-check source/time, policy version, decision, reason and outcome stage.

Audit must distinguish request, authorization, response release, import attempt, and independently verifiable destination commit acknowledgement. It must not claim a completed transfer based only on a successful authorization. If required source audit persistence fails, no protected data is released and no import is authorized.

### 3.6 Destination import coordinator

Coordinates an authorized import with the durable import operation designed in PRs #23/#24:
- requires a distinct import challenge/assertion;
- validates source authorization before source patient disclosure;
- uses source pointer identity and destination provenance, not demographics, for transfer idempotency;
- commits destination patient/allergy data and correlation marker transactionally;
- handles pointer synchronization and uncertain outcomes as recoverable states;
- cannot turn a source authorization into a completed transfer claim.

## 4. Proposed request protocol

The following is a logical flow. Exact API paths, payload schemas and challenge bootstrap semantics must be frozen in the protocol contract before implementation.

### 4.1 Discovery flow

1. Destination clinician authenticates through the normal tenant identity/session path.
2. Destination application authenticates to the source using its registered node credential and requests a discovery challenge for a specific destination branch, action, purpose and selector binding.
3. Source validates node/partner relationship and creates a short-lived challenge. The source must not disclose patient existence or protected demographics at this stage.
4. Destination issuer validates the local human session and challenge; it derives clinician identity/affiliation and signs an assertion bound to the challenge.
5. Destination submits the assertion and challenge reference to source discovery.
6. Source validates node, issuer trust, key, signature, claims, challenge binding, time, clinician mapping/status, and atomic replay state.
7. Source independently evaluates clinician authorization and current patient privacy/data-use policy for the resolved resource(s) and requested scope.
8. Source writes its authorization audit decision durably before returning any protected discovery result.
9. Source returns only the approved minimum summary, plus opaque receipt/resource handles required for a later import. Partial discovery, timeouts and incomplete source results remain explicit; no incomplete result may mint a complete-discovery receipt.
10. Source does not treat the discovery assertion as permission to import.

**Open protocol design point:** selector-based discovery may resolve to zero, one or multiple candidate records. The challenge must bind the exact selector request without leaking patient existence before authorization. If authorization requires an exact patient before selector resolution, the protocol needs a privacy-preserving source-side pre-resolution mechanism or a source-issued opaque candidate handle. This must be threat-modelled and approved; do not solve it by trusting a client-computed patient ID/hash.

### 4.2 Import flow

1. Destination clinician initiates import as a separate protected action.
2. Destination requests a new source challenge bound to the exact opaque source resource/pointer returned by authorized discovery, exact destination branch, purpose and minimum import scope.
3. Destination issuer validates the current local clinician session and issues a separate import assertion.
4. Source validates the assertion, challenge, node, issuer/key, actor mapping/status, exact resource, destination, purpose, scope and replay state.
5. Source re-evaluates current clinician authorization and patient privacy/data-use policy. Discovery permission is not assumed to remain valid.
6. Source durably audits the import authorization decision before protected source data is released.
7. Source reads only the authorized data categories and returns a signed/opaque transfer response bound to the import operation and source pointer. No raw bearer assertion is persisted in transfer logs.
8. Destination import coordinator validates the response and executes the durable idempotency/recovery contract from the accepted PR #23/#24 design.
9. Destination records its own audit stages. Source and destination audit records correlate through opaque operation/request identifiers without asserting distributed atomicity.
10. Pointer publication/synchronization occurs only under the approved current sharing policy and durable fencing/recovery contract.

### 4.3 Local cross-branch path

Local imports must traverse the same logical source-side assertion verification, clinician mapping, authorization, privacy, replay and audit components. A local database shortcut, direct ORM read, shared process, shared tenant group, or privileged internal service identity must not bypass source authorization.

A narrowly scoped service-to-service optimization may be considered only if it preserves the same source-verifiable clinician assertion and all source controls. Network locality is not an authorization boundary.

## 5. Assertion validation contract

Before any protected source read, validate all of the following:

- exact protocol token type and supported version;
- exact issuer and active issuer trust record;
- `kid` resolves only within that issuer's configured key set;
- algorithm equals the configured issuer/key algorithm; reject `none`, algorithm confusion, fallback and untrusted remote key retrieval;
- valid asymmetric signature;
- exact audience, authenticated node, requesting branch and destination branch;
- actor type is human clinician;
- issuer-scoped stable subject maps unambiguously to an accepted external clinician identity;
- current clinician affiliation/status and required credential/registration freshness;
- exact action, enumerated purpose, resource/selector binding and minimum scope match source challenge;
- `iat`, `nbf`, `exp` and configured clock-skew policy;
- challenge is active, unexpired, bound to this node/action/resource/destination and atomically consumed;
- `jti` is unique and atomically claimed;
- current source authorization and privacy policy allow the request;
- required source audit decision is durably committed before disclosure.

Do not implement production lifetime, clock-skew, credential-freshness or revocation-SLA constants until D-04/D-09 and related owners approve them. Proposed two-minute lifetime is a design candidate, not an approved production value.

## 6. Storage boundary proposal

Exact table names, schema ownership and retention remain subject to design review and D-07/D-08/D-10/D-12 decisions.

| Data set | Owning database | Required integrity |
|---|---|---|
| Issuer and signing-key trust metadata | Source tenant trust store (or explicitly approved control-plane authority with source-local enforcement) | Unique issuer/key IDs, active/revoked state, validity window, dual-control audit |
| External clinician identity mapping | Source tenant | Unique issuer + subject mapping; current status and credential evidence/freshness |
| Source challenge | Source tenant | Random opaque ID, exact action/resource/destination binding, expiry, one-time state |
| Assertion replay claim | Source tenant | Unique issuer + jti and atomic claim |
| Source authorization audit | Source tenant audit store | Append-only/tamper-evident; decision before disclosure |
| Destination assertion issuance audit | Destination tenant audit store | Issuer subject, challenge reference, key ID, timestamp; no raw token |
| Durable import operation | Control plane per accepted PR #23/#24 design | Stable idempotency identity, fencing generation, recoverable state |
| Destination provenance marker | Destination tenant | Unique source pointer + source branch + destination + protocol/operation identity; never demographic-only |

Do not place private signing keys in application database rows or repository secrets. Do not store raw bearer assertions in audit or transfer records. Do not put patient demographics in control-plane operation identity.

## 7. Route enforcement inventory

Before implementation, re-fetch the final router tree and enumerate every direct/indirect cross-branch read, including aliases and internal service calls. At minimum review:

- federated patient discovery route;
- federated patient import route;
- local cross-branch import endpoints and service methods;
- any background task or administrative operation that reads another branch's patient record;
- root API and V1 aliases of every protected route;
- pointer publication/synchronization side effects that make another branch's patient discoverable.

Required rule: authorization dependency/middleware is not sufficient if a route performs a source query before the dependency or if a service method can be called directly. Place source authorization at the source data-access boundary or enforce an unskippable service contract, and test direct invocation paths.

Do not change ordinary same-branch patient CRUD unless it crosses the source-branch boundary defined above.

## 8. Failure behavior

All required-control failures deny protected access:
- unknown/untrusted issuer or key;
- invalid signature/algorithm/header/claim;
- stale, suspended or ambiguous clinician mapping;
- missing or expired challenge;
- replay or concurrent duplicate claim;
- wrong action, purpose, resource, scope or destination;
- source privacy/policy denial;
- trust, clinician-status, authorization, replay-store or required audit outage;
- excessive clock drift or untrusted time;
- source audit commit failure.

Return stable machine-readable outcomes without disclosing whether a protected patient exists. Do not silently fall back to node-only access, local shortcut, destination RBAC, or cached stale trust state beyond an explicitly approved cache/revocation SLA.

## 9. Security test plan

### Cryptographic and trust tests
- malformed, unsigned, tampered, wrong-signature and unsupported-algorithm assertions;
- `none`, algorithm confusion, key substitution, unknown/revoked/expired `kid`;
- unknown, suspended, wrong-branch and wrong-organization issuer;
- key rotation overlap and immediate compromise revocation;
- no arbitrary key URL/JWKS fetch.

### Actor and authorization tests
- missing/ambiguous issuer-subject mapping;
- suspended/deactivated clinician or revoked affiliation;
- unverified/expired credential where verification is required;
- unauthorized clinician class/action/purpose/resource/destination/scope;
- caller-supplied actor ID, role, purpose or scope tampering;
- source patient opt-out, source policy change and destination policy mismatch.

### Challenge/replay tests
- expired, wrong-node, wrong-destination, wrong-resource and wrong-action challenge;
- discovery assertion used for import;
- import assertion used for discovery;
- same jti/challenge replayed concurrently across separate workers;
- replay-store outage and source transaction rollback;
- challenge creation does not disclose patient existence.

### Route and isolation tests
- every protected root and V1 alias;
- local cross-branch and cross-hospital routes enforce identical source controls;
- direct service invocation cannot bypass source authorization;
- source data query is not executed before actor verification and authorization;
- same-branch ordinary CRUD regression remains unchanged;
- tenant/branch isolation and no cross-tenant ORM session leakage.

### Audit and recovery tests
- audit row committed before any protected response;
- audit failure means no disclosure/import authorization;
- requested/authorized/disclosed/imported/committed stages remain distinct;
- no raw token, key, ABHA or unnecessary PHI in logs/errors;
- import idempotency, fencing, receipt expiry, pointer retry and post-commit source-policy revocation tests from accepted PR #23/#24 design.

Use PostgreSQL integration tests with independent sessions and application workers for replay races, challenge consumption, unique claims, fencing and import recovery. SQLite-only tests do not satisfy concurrency evidence.

## 10. Phased implementation plan — gated, not authorized

### Phase 0 — protocol and governance closure
- Close/approve relevant D-01 through D-13 decisions with named accountable evidence.
- Formalize D-11 with product, clinical governance and privacy/legal approvals.
- Decide issuer model, clinician evidence, allowed classes, purposes, algorithm/key custody, trust onboarding, lifetimes/revocation, audit retention and emergency exclusion.
- Resolve selector challenge/resource-binding threat model.
- Accept and reconcile import idempotency/recovery design and destination fencing.
- Freeze protocol version, claims, error contract, route inventory and threat model.

**Exit:** written governance records and independent security design approval. No runtime work before this gate.

### Phase 1 — isolated identity/trust foundation
- Add source trust registry and external clinician mapping under approved ownership.
- Implement issuer/key lifecycle and dual-control administration.
- Add destination assertion issuance adapter using authenticated session context.
- Feature flag defaults off; no production partner keys or trust records.

**Exit:** unit and integration tests; key custody review; no protected route uses the new flow yet.

### Phase 2 — source challenge, verification and authorization
- Add source challenge service and atomic replay claims.
- Add strict assertion verifier and source-side clinician/purpose/resource authorization.
- Add durable source audit decision before disclosure.
- Test every fail-closed dependency and concurrent replay case.

**Exit:** independent cryptographic and authorization review; all negative tests pass.

### Phase 3 — protected route integration
- Integrate discovery first, then import with a separate challenge/assertion.
- Apply identical checks to local cross-branch and cross-hospital access.
- Enforce source authorization at data-access boundary.
- Preserve PR #19 discovery receipts and accepted PR #23/#24 import recovery semantics.
- Keep ordinary same-branch operations unchanged.

**Exit:** root/V1 alias parity, direct-service bypass tests, PostgreSQL failure-injection, no incomplete-discovery receipt, no idempotency regression.

### Phase 4 — controlled non-production validation
- Only after separate approval: test with synthetic data and explicitly onboarded non-production partners.
- Validate key rotation/revocation, clinician suspension, audit integrity, outage behavior, alerting and incident runbooks.
- No real patient data in this phase unless separately and explicitly authorized under applicable governance.

**Exit:** partner interoperability, independent penetration/security review, clinical-safety and privacy review, rollback/disable exercise.

### Phase 5 — pilot/release gate
- D-14 remains a final approval, not a pre-approved milestone.
- Require named product/release, security, clinical governance and privacy/legal sign-off.
- Require evidence bundle, monitoring, support ownership, revocation SLA, incident response and rollback.
- Emergency/break-glass remains disabled unless separately designed and approved.

**Exit:** explicit written release authorization only.

## 11. Open decisions and blockers

The following are not settled by this blueprint:
- D-01 issuer authority and responsibility;
- D-02 authentication assurance/MFA conditions;
- D-03 permitted clinician classes;
- D-04 professional credential/licensure evidence and freshness;
- D-05 source authorization authority and policy;
- D-06 purpose vocabulary and action-scope matrix;
- D-07 signing algorithm and key custody;
- D-08 trust onboarding and dual control;
- D-09 assertion/challenge lifetime, clock skew and revocation SLA;
- D-10 replay and distributed operation semantics;
- D-11 formal approval of local cross-branch scope (project direction YES; approval pending);
- D-12 audit content, retention and access;
- D-13 formal emergency/break-glass exclusion;
- D-14 final pilot/release authorization.

Additional technical blockers:
- source-issued challenge bootstrap and privacy-preserving selector resolution;
- final direct/indirect route inventory after PR #19 is reconciled;
- trust-registry storage ownership and failure semantics;
- source-side authorization mapping and credential verification integration;
- destination-side fencing compatible with PR #23/#24 recovery;
- formal acceptance of the import idempotency/recovery design;
- independent cryptographic, privacy and clinical-safety review.

## 12. Stop conditions and safety statement

Do not:
- modify runtime code or migrations under this design-only PR;
- provision production signing keys or partner trust entries;
- enable a feature flag or node-only fallback;
- merge PR #19, #23, #24, #25, #26 or #27 without the relevant explicit approval;
- deploy, pilot, access production patient data, execute destructive retention operations, or enable emergency federation;
- claim compliance certification or legal approval.

This blueprint is an engineering proposal to support governance review. It does not close AUD-004, authorize implementation, or remove the release blocker.
