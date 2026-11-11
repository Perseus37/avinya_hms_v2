# AUD-004 D-11 — Local Cross-Branch Import Scope Direction

**Status:** Project direction recorded; formal governance approval remains PENDING  
**Decision:** Include local cross-branch patient imports in AUD-004 scope  
**Source:** Explicit direction from the project user in the Avinya HMS project conversation, 12 November 2026  
**Runtime impact:** None — documentation only

## 1. Scope direction

AUD-004 is to cover both:

1. Cross-hospital federation operations that access a source hospital's patient data.
2. Local cross-branch or cross-tenant import operations that read another branch's source patient record, even when the branches belong to the same hospital group or Avinya deployment.

The security boundary is the source patient record and the source authorization decision, not whether the network path is labelled local, corporate, or external federation.

## 2. Required security outcome

For every protected cross-branch patient-data access within this scope:

- The requesting human clinician must be independently attributable through a trusted, cryptographically verifiable actor assertion.
- The source branch must verify the assertion, current clinician identity/affiliation status, exact action, purpose, destination, resource and minimum data scope.
- The source branch must independently authorize the clinician and evaluate its current patient privacy/data-use policy.
- The source must durably audit the authorization decision before protected data is disclosed or an import is authorized.
- Node/service authentication alone, destination RBAC alone, caller-supplied actor IDs/roles, and a same-corporate-group relationship are not substitutes.
- Discovery and import remain distinct protected actions with distinct source-issued challenges/assertions.
- Failure of any required identity, trust, authorization, policy, replay, or audit dependency must fail closed.

## 3. Explicit exclusions

This direction does not extend AUD-004 to ordinary same-branch patient CRUD where no other branch's source patient record is read.

It does not authorize:
- emergency/break-glass federation;
- broader patient sharing or changes to consent defaults;
- automatic patient merging based on demographics;
- production trust onboarding, signing-key provisioning, or runtime implementation;
- bypassing the import idempotency/recovery safeguards proposed separately in PRs #23 and #24.

Any future exclusion for a particular cross-branch flow must be narrow, documented, approved by the accountable governance owners, and supported by equivalent source-side attribution and authorization controls. Engineering convenience or shared corporate ownership is not sufficient.

## 4. Relationship to the AUD-004 decision register

This records the project user's requested scope direction for D-11. It is not represented as formal approval by the product owner, clinical governance owner, privacy/legal owner, or any named accountable approver.

Therefore:
- D-11's proposed disposition is **YES — include local cross-branch imports**.
- D-11's formal governance status remains **PENDING** until the accountable approvers named by the governance process record their identities, roles, date, governance reference and supporting evidence.
- Implementation planning must assume the broader scope and must not ship a local-import bypass while formal governance is pending.
- The AUD-004 release gate remains in force.

## 5. Required implementation and validation coverage

When runtime work is authorized, tests must prove that:

- local cross-branch discovery rejects missing, invalid, expired, replayed, wrong-actor, wrong-purpose, wrong-resource and wrong-destination assertions;
- local cross-branch import requires a separate import challenge/assertion and source-side authorization;
- source patient/pointer reads do not occur before actor verification and authorization;
- same-branch ordinary patient operations continue to use their existing local authorization model and are not accidentally routed through federation;
- all route aliases and code paths enforce equivalent controls;
- source audit failure, clinician-status outage, trust-registry outage, replay-store outage and privacy-policy outage fail closed;
- there is no weaker local route that can be used to bypass the cross-hospital controls.

## 6. Safety and change control

This is a documentation-only scope record. It changes no application code, database schema, migration, configuration, key, trust entry, feature flag, or runtime behavior.

PR #19 remains independently reviewable and unmerged. AUD-004 runtime implementation must be based on the final reconciled PR #19 mainline, not an older baseline. PRs #23 and #24 separately specify federated import idempotency and recovery and do not replace clinician actor verification.

No merge, deployment, production patient-data operation, emergency federation enablement, or release approval is implied.
