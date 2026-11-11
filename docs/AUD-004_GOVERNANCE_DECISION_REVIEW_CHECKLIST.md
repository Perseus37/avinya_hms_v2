# AUD-004 Governance Decision Review Checklist

**Status:** Coordination checklist — proposed, not an approval record  
**Protocol:** Signed Clinician Actor Assertion Protocol, current design revision  
**Purpose:** Prepare accountable owners to resolve D-01 through D-14 before runtime implementation or pilot.

This checklist consolidates the decision register. It does not appoint approvers, provide legal or clinical approval, or convert engineering recommendations into governance decisions. Unless a decision has an explicit recorded approval meeting the required evidence standard, its formal status remains **PENDING**.

## Decision register

| ID | Decision required | Proposed direction for review | Accountable owner(s) identified in design | Current status |
|---|---|---|---|---|
| D-01 | Who may issue clinician assertions and represent a hospital? | Each participating hospital's Avinya tenant backend; distinct issuer identity and signing key per branch. | Hospital security/IT owner; Avinya security architect | PENDING |
| D-02 | What authentication assurance is required? | Active authenticated user, live non-revoked session, MFA for high-risk cross-hospital access; server-side actor mapping. | Hospital IAM/security owner | PENDING |
| D-03 | Which clinician classes may act? | Explicit allow-list (doctor, nurse, allied-health professional) with action-specific scopes; no generic staff wildcard. | Hospital clinical governance owner | PENDING |
| D-04 | How is professional registration/licensure verified? | Trusted registry verification or documented hospital credential-verification SOP with freshness, expiry and revocation handling where required. | Hospital medical/clinical governance owner | PENDING |
| D-05 | Who authorizes source-patient access? | Source hospital independently authorizes exact clinician, action, purpose, resource, destination and scope; destination RBAC and privacy policy remain separate checks. | Source hospital privacy/data-protection and clinical governance owners | PENDING |
| D-06 | Which purposes/actions are allowed? | Versioned closed purpose vocabulary and action-purpose-scope matrix; no emergency/break-glass purpose in initial enabled vocabulary. | Clinical governance and privacy/legal owners | PENDING |
| D-07 | Which signing algorithm and key custody model? | Ed25519 if supported and approved by all participants; otherwise ES256 after review. Per-branch key in managed KMS/HSM. | Avinya security/cryptography owner; hospital security owner | PENDING |
| D-08 | How are issuers, partners and keys onboarded/changed? | Out-of-band verified onboarding and dual approval for trust creation, key replacement, suspension and reactivation. | Federation trust administrator; independent security approver | PENDING |
| D-09 | What lifetimes and revocation freshness apply? | Proposed maximum 120 seconds for assertions/challenges; define clock skew, online status checks, cache limits and revocation SLA per action. | Avinya security owner; participating hospital IAM owner | PENDING |
| D-10 | How are retries, replay and distributed outcomes handled? | Atomic durable challenge/jti claims; separate discovery/import authorization; stable transfer identity; explicit indeterminate state and reconciliation. | Federation technical owner; database/platform owner | PENDING |
| D-11 | Does scope include local cross-branch imports? | YES — include local cross-branch/cross-tenant imports that read another branch's patient record, as well as cross-hospital federation. | Product owner; clinical governance owner; privacy/legal owner | PROJECT DIRECTION RECORDED; FORMAL APPROVAL PENDING |
| D-12 | What audit content, retention and access controls apply? | Immutable/tamper-evident source and destination audit; minimize PHI; never store bearer assertions/private keys; retention per approved legal/contractual schedule. | Privacy/legal owner; records owner; security owner | PENDING |
| D-13 | Is emergency/break-glass in scope? | NO for initial release; keep emergency federation disabled and separately designed/approved if ever proposed. | Clinical governance and privacy/legal owners | PENDING |
| D-14 | What authorizes pilot and production release? | No pilot/release until decisions, acceptance tests, independent security review, partner runbooks, monitoring and explicit named release approval are complete. | Product/release owner; security and clinical governance approvers | PENDING — FINAL GATE |

## Required evidence for each decision

An item may move to **APPROVED**, **REJECTED**, or **DEFERRED** only when its decision record includes:

- Exact decision ID and question/version.
- Chosen option and rationale, including any deviation from the proposed direction.
- Named approver, organization and accountable role.
- Approval date and governance/ticket/meeting reference.
- Evidence links: policy, partner agreement, threat model, technical review, test results, SOP or runbook as applicable.
- Affected protocol/design version and implementation stages.
- Residual risk, compensating control, expiry/revisit date, and feature-disable condition.

A verbal indication, engineering preference, passing CI, PR approval, or project-user direction alone is not formal approval by a clinical, privacy/legal, hospital-security or release authority.

## Dependency and stop-gate sequence

1. **Permitted use case and data authority:** resolve D-03, D-05, D-06 and formal D-11 approval. Until then, implement no broader data access and no local-import bypass.
2. **Issuer and clinician trust:** resolve D-01, D-02, D-04, D-07, D-08 and D-09 before trust registry, assertion issuance, clinician mapping or production key provisioning.
3. **Transfer integrity and audit:** resolve D-10 and D-12 before replay, transfer-state, audit schema, retention or reconciliation implementation.
4. **Emergency boundary:** record D-13 explicitly. Emergency federation remains disabled regardless of silence or approval of the normal path.
5. **Release:** D-14 cannot be approved in advance. It requires implementation evidence, independent review, partner readiness and explicit release authorization.

A decision may be deferred only if every dependent capability is explicitly disabled and the deferment has an owner, expiry/revisit date and compensating control.

## Current project direction and boundaries

- D-11 project direction is **YES**: all protected cross-branch patient-data reads, local or cross-hospital, require source-verifiable clinician identity and source-side authorization. Formal approval remains pending.
- Same-branch ordinary patient CRUD is not brought into this additional cross-branch security boundary.
- Discovery and import are distinct protected actions and require distinct source-issued challenges/assertions.
- Node/service authentication, destination RBAC, shared corporate ownership, caller-supplied actor IDs/roles, and patient privacy policy alone do not prove clinician identity or source authorization.
- Emergency/break-glass federation remains disabled.
- PRs #23 and #24 describe import idempotency/recovery requirements; they do not resolve AUD-004.
- PR #19 remains a separate AUD-001–003 remediation PR and must not be treated as proof that AUD-004 is implemented.

## Implementation authorization

**Not authorized by this checklist.** Runtime implementation must wait until the required governance decisions are recorded, the import recovery design is explicitly accepted, and the implementation stop conditions are resolved. Any implementation must be isolated, feature-off by default, independently reviewed and covered by PostgreSQL concurrency/failure-injection and route-alias security tests.

No merge, deployment, production patient-data operation, partner trust onboarding, key provisioning, pilot, release, or emergency federation enablement is authorized by this document.
