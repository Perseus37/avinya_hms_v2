# AUD-004 ADV-01 / ADV-02 Resolution Proposal

**Status:** PROPOSED SECURITY DESIGN — GOVERNANCE AND INDEPENDENT REVIEW REQUIRED  
**Parent:** PR #33, independent adversarial security review  
**Scope:** Resolve the protocol gaps identified by ADV-01 (bounded discovery-search authorization) and ADV-02 (independent clinician identity and affiliation binding).  
**Non-goals:** This document does not approve a cryptographic algorithm, credential authority, professional-registration source, search budget, retention period, revocation SLA, issuer onboarding, runtime implementation, migration, pilot, production access, merge, deployment or release.

## 1. Executive proposal

ADV-01 and ADV-02 are coupled but distinct trust decisions:

1. **ADV-02 establishes who the clinician is and whether the clinician's current identity, affiliation and required professional status are independently acceptable to the source.**
2. **ADV-01 establishes whether that verified clinician may perform a narrowly bounded search, before any patient-specific selector resolution occurs.**
3. After internal resolution, the source makes a separate candidate/resource decision before disclosing any candidate-specific result.

A valid destination signature proves that a trusted issuer signed an assertion. It does not, by itself, prove the subject is a clinician, that the subject is affiliated with the asserted organization, or that the issuer has not misrepresented the subject. Likewise, permission to search does not grant permission to view a matched patient's identity, summary, pointer, allergy information or record.

**Recommended invariant:** no patient-specific query is executed until source-side search authorization succeeds; no patient-specific result, existence signal, pointer, handle or summary is returned until source-side candidate/resource authorization succeeds.

All recommendations below remain proposals until the relevant governance owners approve them and the decision register records evidence.

## 2. Terms and trust dimensions

Do not collapse these independent dimensions into one role or boolean:

| Dimension | Meaning | Authority |
|---|---|---|
| Local account | User can authenticate to the destination tenant | Destination identity system |
| Issuer identity | Hospital/branch service is an approved assertion issuer | Source-approved trust registry |
| Issuer key | Specific signing key is currently trusted for that issuer and purpose | Source trust/key lifecycle |
| Clinician subject | Immutable issuer-scoped identifier for the human actor | Issuer, independently enrolled/mapped by source |
| Professional credential | Registration/licensure or other professional evidence required for the actor class/action | Approved authoritative evidence source, as governed |
| Workforce affiliation | Current relationship between clinician and issuer/branch | Approved affiliation authority, verified by source |
| Source authorization | Actor may perform this action for this patient/resource and destination | Source tenant policy |
| Destination authorization | Actor may receive/import data into destination | Destination tenant policy |

An issuer signature is not professional registration evidence. A professional registration number is not proof of current employment or affiliation. A destination-local role is not source authorization. A node API key is not human identity.

## 3. ADV-01: two-stage source authorization

### 3.1 Stage 0 — authenticate and verify the actor

Before accepting a search request, the source:

1. Authenticates the registered node/transport peer.
2. Resolves the issuer, branch, node, destination and allowed relationship from trusted server-side records.
3. Verifies the source-issued challenge and signed actor assertion, including signature, key status, issuer, audience, destination, action, purpose, protocol version, timestamps and replay state.
4. Resolves the issuer-scoped subject against the source-controlled clinician mapping described in Section 4.
5. Checks current account, affiliation, clinician-class and any action-required professional-credential status under the approved freshness policy.
6. Rejects caller-supplied actor IDs, roles, source patient IDs, schema names, selector hashes and policy decisions as authority.

No patient selector is resolved during this stage. The source may validate selector syntax and size limits without executing a patient-specific lookup.

### 3.2 Stage 1 — authorize bounded search before lookup

The source evaluates a distinct permission, proposed canonical identifier:

`DISCOVERY_SEARCH`

The decision must be made and durably audited before patient-specific selector resolution.

The search authorization decision is bound to all of:

- protocol version and purpose-registry version;
- verified issuer ID, issuer branch, key ID and issuer-scoped clinician subject;
- actor class, authentication assurance and required credential/affiliation status versions;
- source audience and source branch;
- exact destination tenant and destination branch;
- action = `DISCOVERY_SEARCH`;
- canonical purpose identifier;
- selector type and canonicalization profile;
- selector value commitment, using an approved privacy-preserving construction (never a raw selector in general telemetry);
- exact permitted data categories for the search stage (proposed default: none returned);
- bounded query budget / rate-limit class;
- challenge ID, assertion ID/jti and expiry;
- source policy version and decision ID.

The search permission authorizes only the source to execute the bounded lookup. It does **not** authorize a patient-existence response, candidate count, branch identity, MRN, pointer, handle, demographic summary, allergy data or import.

**Selector policy proposal:**
- Prefer exact-match selectors only for initial release.
- Do not enable fuzzy name search, prefix search, wildcard search, multi-result search or sequential enumeration unless a separately approved threat model and policy explicitly authorize them.
- Accept only selector types explicitly allow-listed by the source policy.
- Canonicalize on the source. Destination canonicalization may be used for input validation only and is never authoritative.
- Apply strict input length, format and entropy requirements. Low-entropy values require stricter budgets and anti-enumeration controls; do not assume hashing makes a phone number or date of birth secret.
- One search authorization covers one canonical selector and one bounded lookup, not an arbitrary list or repeated pagination.
- Any retry must be idempotently tied to the same request and must not expand the budget or disclose match state.

**Budget policy:** numeric limits, windows, aggregation dimensions and exception handling are unresolved governance choices. The source must enforce budgets across nodes and issuer aliases for the same actor, and across subjects for the same issuer/destination where appropriate. It must also include destination, source, selector type and abuse signals in rate policy. A per-process limiter alone is insufficient for a distributed source deployment.

### 3.3 Stage 2 — candidate/resource authorization after internal resolution

Only after Stage 1 succeeds may the source resolve the selector inside the source tenant.

For each internally resolved candidate, the source performs a separate source-side decision bound to:

- the same verified actor and issuer context;
- exact source-owned patient/resource identity;
- exact destination;
- action (for example, demographic discovery, allergy disclosure or import preparation);
- approved purpose;
- requested data categories and minimum necessary scope;
- current patient privacy/data-use policy and applicable consent/restriction state;
- source policy version and current revocation/status versions.

Candidate/resource authorization is not implied by search authorization. A successful search may produce zero candidates, one candidate, multiple ambiguous candidates or a candidate denied by source policy. No patient-specific outcome is returned unless the source's approved response policy permits it.

### 3.4 Disclosure and response contract

Until candidate authorization succeeds, externally observable responses must not reveal whether a patient exists.

The protocol must define and test normalization across:
- no match;
- ambiguous match;
- candidate denied;
- selector not eligible;
- source policy denial;
- source data unavailable;
- stale/revoked actor or issuer;
- replayed or expired request.

Normalization must cover HTTP status, response body schema, body size bands, headers, timing distributions, retry behavior and externally visible audit/handle behavior. Perfect timing equality is not a realistic claim; the threat model must specify measurable bounds, jitter/queue controls where appropriate, and statistical test methodology.

Do not return candidate count, source branch, source MRN, pointer identifier or per-candidate reason to the destination. Where a permitted result exists, return only the minimum authorized payload and a recipient-bound response artifact. The source audit may retain more detail under restricted access.

If exact-match discovery is approved, ambiguity must fail closed to a uniform non-disclosing outcome and an authorized reconciliation workflow; it must not return a list of possible patients.

### 3.5 Required event ordering

The proposed source event sequence is:

1. `NODE_AUTHENTICATED`
2. `ACTOR_ASSERTION_VERIFIED`
3. `CLINICIAN_MAPPING_AND_STATUS_VERIFIED`
4. `DISCOVERY_SEARCH_AUTHORIZATION_DECIDED` (durably committed before lookup)
5. `SELECTOR_RESOLUTION_ATTEMPTED` (source-internal, restricted audit)
6. `CANDIDATE_AUTHORIZATION_DECIDED` (per candidate, source-internal)
7. `DISCLOSURE_INTENT_COMMITTED` (only for an authorized disclosure)
8. `RESPONSE_ARTIFACT_COMMITTED` (if the protocol supports artifact-based retry)
9. `RESPONSE_DELIVERY_ATTEMPTED` / `OUTCOME_UNCERTAIN` / `DELIVERY_ACKNOWLEDGED`

A network send is not part of the database transaction. The protocol must not claim that a response was received merely because a response artifact was committed or a send was attempted. A failure after disclosure intent but before confirmed delivery must have an explicit uncertain outcome and governed retry behavior. A retry must not cause a new source read unless fresh authorization is obtained.

## 4. ADV-02: independently verifiable clinician identity and affiliation

### 4.1 Source-controlled identity binding

Each source tenant maintains or consumes an independently governed mapping from:

`(issuer_id, issuer_scoped_subject_id)`

to a source-approved clinician identity record.

The mapping must not use email, display name, local integer user ID, phone number or an unqualified registration number as its unique key. The subject identifier must be immutable within its issuer namespace and never reassigned to another human. Deletion, rehire, account recreation and branch transfer must preserve historical identity lineage and require a governed new mapping or reactivation process; they must not silently recycle a subject.

The source-controlled mapping should include, at minimum:
- issuer and organization identity;
- issuer-scoped subject identifier;
- source clinician identity reference;
- clinician class and permitted professional scope;
- identity proofing method, evidence reference and verification date;
- affiliation authority, branch/organization relationship and effective dates;
- professional credential type, jurisdiction, status, evidence reference and last verification, when required;
- mapping status and status version;
- enrollment approvers, dual-control evidence and timestamps;
- recertification due date;
- revocation/suspension reason code and effective time;
- mapping history and non-reuse marker.

Evidence references should point to controlled records or approved registries; avoid copying unnecessary sensitive credential documents into federation assertions or routine logs.

### 4.2 Enrollment and ongoing lifecycle

**Proposed source-controlled enrollment flow:**
1. Partner issuer identity and organization/branch relationship are independently verified out-of-band.
2. Clinician identity is proofed using an approved method and evidence source.
3. The issuer-scoped subject is bound to the verified person by an authorized enrollment process.
4. A second independent approver confirms the mapping and evidence.
5. Required credential and affiliation checks are recorded with effective dates and evidence references.
6. Mapping becomes active only after all required checks succeed.
7. Recertification and status refresh follow the approved action-specific schedule.
8. Suspension, termination, license revocation, issuer compromise or mapping error triggers source-side revocation and invalidation of positive caches.

Issuer assertion claims may identify the subject and carry evidence references/status versions, but source policy must not accept self-asserted clinician class, license validity or affiliation as conclusive proof. The source must resolve current status from its controlled mapping and approved evidence/status authorities.

### 4.3 Separate status dimensions and freshness

At minimum, maintain separate statuses for:
- destination account active;
- issuer active;
- signing key active and uncompromised;
- clinician mapping active;
- workforce affiliation active;
- clinician class active;
- professional credential valid, where required;
- source authorization policy available and current.

A single `active=true` claim is insufficient.

For each protected action, governance must specify which dimensions are mandatory and the maximum acceptable age of each status. A status lookup timeout, stale status beyond the approved limit, unknown/conflicting status, failed revocation propagation or unavailable policy engine must deny the protected operation. Do not fall back to historical assertion claims or a stale-positive cache.

Branch transfer must revoke the old branch relationship before granting the new relationship, or use an explicitly governed atomic transition that cannot create an unauthorized overlap.

### 4.4 Issuer compromise and key lifecycle

A valid signature from a compromised issuer/key is not trustworthy identity evidence.

The source trust registry must bind issuer ID, organization/branch, node relationship, audiences, allowed actions, key ID, algorithm policy, key validity, trust version and status. Trust and key changes require independent dual control and out-of-band partner verification.

Required behavior:
- compromised key: immediate denial, no planned-rotation grace period;
- issuer compromise: issuer-wide suspension and defined blast-radius review;
- planned key rotation: bounded overlap only for keys explicitly marked active and non-compromised;
- unknown key, unexpected key-set change or trust-registry outage: deny;
- revocation propagation outside the approved bound: deny affected protected operations and alert;
- reactivation after compromise: new dual-controlled approval, new evidence and a fresh trust version; delayed replication must not undo revocation.

The exact signing algorithm, key custody mechanism, HSM/KMS requirements, rotation interval and propagation SLA remain pending D-07/D-08/D-09 and security approval. This proposal intentionally does not select them.

## 5. Combined request/decision model

| Step | Input | Source decision | Patient-specific lookup allowed? | Patient-specific output allowed? |
|---|---|---|---:|---:|
| 0. Node and issuer trust | Node credential, server-side relationship | Node, issuer, key and destination relationship valid | No | No |
| 1. Actor verification | Challenge + signed assertion | Signature, audience, issuer-scoped subject, mapping and current status valid | No | No |
| 2. Search authorization | Verified actor + selector metadata + purpose + budget | Explicit `DISCOVERY_SEARCH` permission | Only after durable allow | No |
| 3. Selector resolution | Canonical selector | Internal source lookup | Yes | No |
| 4. Candidate authorization | Source-owned candidate + requested scope | Patient/resource, purpose, destination and data-category policy allow | Already resolved | No until allow |
| 5. Disclosure intent | Authorized candidate and minimum payload | Durable disclosure authorization/audit | No new lookup required | Only after durable commit |
| 6. Response artifact/delivery | Recipient-bound artifact | Integrity, replay and delivery outcome | No new lookup on replay | Only exact previously authorized artifact, if replay policy permits |
| 7. Import | Fresh import-specific authorization and source revalidation | Independent source import decision plus destination validation | Source re-read only under fresh authorization | Import payload only within approved scope |

A discovery authorization must never be reused as an import authorization. A search result, resource handle, receipt, operation ID or prior response artifact is not a substitute for fresh source authorization when a new source read is required.

## 6. Proposed claims and canonicalization requirements

The assertion and search request should carry or reference, without relying on caller authority for their truth:

- issuer identifier and immutable issuer-scoped subject;
- source audience and exact destination tenant/branch;
- protocol and purpose-registry versions;
- action;
- challenge identifier and assertion identifier/jti;
- issued-at, not-before and expiry;
- authentication assurance context;
- actor-class reference (source resolves approved class);
- selector type and canonicalization profile identifier;
- search budget class / one-request scope;
- request correlation identifier;
- optional evidence/status version references.

The source independently canonicalizes the selector and validates the purpose/action/scope against its own registries. Unknown, deprecated, aliased, wildcard or downgraded values are rejected. Exact claim names, token format, signing algorithm, canonical JSON rules and wire schema are implementation decisions that require protocol/security review; this proposal does not freeze them.

## 7. Failure and retry semantics

| Failure point | Required behavior | Retry authority |
|---|---|---|
| Node/issuer/key trust unavailable | Deny; no patient lookup | New request after trust recovery |
| Clinician mapping/status unavailable or stale | Deny; no patient lookup | New request after authoritative status is available |
| Search authorization audit cannot commit | Deny; no selector query | New authorized request |
| Search budget exhausted | Uniform non-disclosing denial; audit abuse signal | Only after policy-defined budget reset or reviewed exception |
| Selector query fails | No result disclosure; record source failure | New request under fresh/valid search authorization |
| Candidate authorization denied | No candidate details or handle | No automatic retry; changed authorization requires new decision |
| Disclosure audit cannot commit | No response artifact or payload disclosure | New authorization after audit recovery |
| Response send outcome uncertain | Preserve indeterminate state; do not assert delivery | Retry only the same authorized artifact if approved; otherwise fresh authorization |
| Clinician/issuer/key/policy revoked before response | Deny or quarantine according to approved checkpoint semantics | Fresh trust and authorization required |
| Destination import requested | Discovery grant is insufficient | Separate import challenge/assertion and source authorization |

Operator reconciliation may inspect restricted audit and operation metadata under dual control. It cannot manufacture identity proof, search permission, candidate authorization or a new source disclosure.

## 8. Required acceptance tests

### 8.1 ADV-01 search authorization and enumeration

- Node key alone cannot create a patient-specific search.
- Valid actor assertion without `DISCOVERY_SEARCH` permission cannot execute selector lookup.
- Wrong source audience, destination, action, purpose, selector type, protocol version, scope or budget is denied before lookup.
- Search permission is durably audited before query execution; audit-store failure prevents query.
- Candidate authorization occurs after internal match and before any candidate-specific response.
- Authorized search with denied candidate returns no candidate detail, pointer, handle or distinguishable patient-existence signal.
- No-match, ambiguous, denied and unavailable cases are tested for status/body/header/size/timing/retry differences under an agreed statistical methodology.
- Sequential ABHA/phone/name values, low-entropy selectors, multi-node requests, aliases and parallel requests cannot exceed source-wide budgets.
- Fuzzy/prefix/wildcard/multi-result selectors are rejected unless explicitly enabled by approved policy.
- Replayed request IDs and altered selector/body/destination/scope do not expand search budget or reveal match state.
- Source and local cross-branch adapters enforce the same logical search authorization interface.
- No central index or routing component returns candidate count, branch or patient metadata before source authorization.

### 8.2 ADV-02 identity, affiliation and issuer trust

- Unknown issuer-scoped subject with a valid signature is denied.
- A destination issuer cannot enroll or elevate a clinician mapping without source-controlled independent proofing and dual approval.
- Subject ID reassignment to a different human is rejected; account deletion/recreation does not recycle identity.
- Email/display-name/integer-ID collisions across tenants cannot merge clinician identities.
- Stale, suspended, terminated or branch-mismatched affiliation is denied.
- Expired/revoked professional credentials are denied where required by the approved actor/action matrix.
- Issuer signature cannot override source mapping, credential or affiliation status.
- Wrong branch/node/audience/key/issuer relationship is denied even with a valid signature.
- Compromised key and issuer-wide revocation block operations within the approved propagation bound.
- Delayed replication or stale cache cannot reactivate revoked issuer, key or clinician mapping.
- Trust registry, status service, policy engine or required audit outage fails closed.
- Revocation racing with challenge, search authorization, candidate authorization, disclosure and response retrieval has deterministic tested outcomes.

### 8.3 Isolation and audit

- Cross-tenant and cross-branch colliding patient, clinician and MRN identifiers cannot cause misrouting or identity substitution.
- Tenant schema selection is derived only from trusted server-side context.
- Root and V1 route aliases, local adapter, internal service, background task and administrative paths share the same authorization boundary.
- Raw selectors, assertions, challenge secrets, handles and PHI are absent from ordinary logs and telemetry.
- Source audit distinguishes search authorization, candidate authorization, disclosure intent, response artifact and delivery outcome.
- Audit attribution uses issuer-scoped subject and source mapping reference, never a foreign tenant's local integer user ID.

## 9. Governance decision register — still open

The following are required decisions, not decisions made by this proposal.

| Decision | Proposed direction for review | Accountable approval | Status |
|---|---|---|---|
| Search selector policy | Exact-match only initially; fuzzy/prefix/wildcard disabled | Clinical governance + privacy + security | Pending |
| Permitted selector types | Explicit allow-list with source-owned canonicalization profiles | Clinical governance + privacy + security | Pending |
| Search budget | Risk-tiered source-wide limits across nodes/subjects/destinations; numeric values to be set from threat model and pilot evidence | Security + platform operations + privacy | Pending |
| Search purposes/actions | Versioned allow-list; no free-form purpose, wildcard or fallback | Clinical governance + privacy | Pending |
| Candidate disclosure categories | Minimum-necessary matrix by clinician class × purpose × action × destination | Clinical governance + privacy | Pending |
| Identity proofing | Approved independent identity evidence and enrollment method per partner model | Identity governance + security + partner governance | Pending |
| Affiliation authority | Approved source of current workforce/branch affiliation and freshness | Partner governance + HR/identity owner + security | Pending |
| Professional credential evidence | Credential types and authoritative sources by clinician class/jurisdiction/action | Clinical governance + legal/compliance | Pending |
| Subject lifecycle | Immutable issuer-scoped subject, non-reuse, controlled rehire/transfer/remapping | Identity governance + security | Pending |
| Mapping administration | Source-controlled dual approval, recertification and revocation | Source tenant owner + security | Pending |
| Status freshness/revocation SLA | Action-specific freshness and measurable revocation propagation bound | Security + clinical governance + operations | Pending |
| Issuer/key trust | Algorithm, key custody, rotation, compromise response and trust registry | Security architecture + key custodians | Pending |
| Audit and retention | Event schema, PHI minimization, access, integrity, retention and legal hold | Privacy/legal + audit owner | Pending |
| Search response normalization | Measurable side-channel acceptance criteria and test methodology | Security + privacy | Pending |

For every approval, update the canonical D-01–D-14 register with status, approver name, organization, role, date, governance reference, evidence, affected protocol stages, residual risk, compensating controls, expiry and disable conditions. This proposal must not be treated as closing a decision by implication.

## 10. Implementation gates

No runtime implementation may begin until all of the following are evidenced:

1. Clinical, privacy and security reviewers approve the two-stage search/candidate authorization model and selector policy.
2. Independent clinician identity proofing, affiliation authority, credential evidence requirements and subject lifecycle are approved.
3. Source-controlled mapping enrollment, dual control, recertification, revocation and compromised-issuer response are approved.
4. Purpose/action/data-category matrix and search budgets are approved.
5. Routing/index topology and selector visibility are reconciled with ADV-07/ADV-09.
6. Challenge, replay, audit, disclosure and network-delivery boundaries are reconciled with ADV-03/ADV-04/ADV-12.
7. Revocation checkpoints and status freshness are reconciled with ADV-05.
8. Protocol schema and trust/key lifecycle are independently reviewed; no algorithm or key custody is inferred from this proposal.
9. Local cross-branch imports remain in scope per recorded project direction D-11; the same source authorization boundary must apply.
10. PostgreSQL concurrency, enumeration, timing, revocation-race, outage and failure-injection acceptance tests are approved.
11. Formal governance approvals and implementation authorization are recorded in the canonical decision register.

## 11. Relationship to existing work

- PR #19 contains runtime remediation for AUD-001–003 but does not satisfy the clinician authorization protocol.
- PRs #23/#24 define import idempotency/recovery design; they must be reconciled with fresh source authorization and must not treat expired artifacts as permission for a new read.
- PRs #20–#22 and #26–#28 contain assertion, governance and implementation design material; this proposal does not supersede their pending decisions.
- PR #31 identified cross-document inconsistencies; PR #32 consolidated the three lifecycles; PR #33 identified ADV-01/ADV-02 and related attack surfaces.
- D-11 project direction includes local cross-branch imports, while formal governance approval remains pending.

## 12. Disposition

This document is a proposed resolution for ADV-01 and ADV-02, not evidence that either finding is closed. Closure requires independent review of the protocol, approved governance decisions, traceable acceptance tests and later verified runtime evidence.

**AUD-004 remains release-blocking.** No runtime code, migrations, configuration, signing keys, trust entries, partner onboarding, pilot, production patient-data access, merge, deployment, release or emergency federation is authorized by this document.
