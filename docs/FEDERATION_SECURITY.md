# Federation Security Boundaries

## Discovery authentication

Cross-branch discovery requires an active `FederatedNode` API key. Keys are stored as SHA-256 hashes and revoked keys return `401 Unauthorized`.

The calling branch identity comes from the authenticated federation node, not from a request-supplied branch field.

## Federation registration identity binding

Federation credentials are issued by a tenant branch for that **same branch**. The `branch_code` supplied to `POST /api/federation/clients` must match the branch code resolved from the authenticated tenant context.

The tenant ORM session carries the resolved branch identity in trusted session metadata, and the `FederatedClient` model rejects an attempted mismatch before the client transaction can commit. This prevents a tenant administrator from minting a federation credential that claims to represent another hospital branch.

A rejected mismatch returns `403 Forbidden` and does not create the tenant-local `FederatedClient` record. The control-plane `FederatedNode` therefore cannot be created from the rejected request either.

For the current topology, registered branch identities are sourced from the control-plane tenant registry. External partner onboarding must use a separate trusted partner-registration workflow rather than allowing arbitrary branch codes through a tenant-scoped endpoint.

## Emergency federation

**Remote emergency disclosure is currently disabled for every federation sharing mode**, including `EMERGENCY_ALLERGIES_ONLY` and `FULL_MESH`. The discovery endpoint returns `403` for emergency purposes before reading patient records. This is a deliberate fail-closed control, not a temporary test limitation.

A source-local `BreakGlassGrant` ID is not a federated credential. The existing local break-glass workflow remains available inside the source tenant, but it does not authorize a remote node. Re-enabling remote emergency disclosure requires all of the following in a separately reviewed implementation:

- Source-issued grant bound to the exact patient, authenticated requesting node/branch, explicit emergency purpose, and minimum permitted data scope.
- Source-side expiry and revocation checks, plus atomic one-time consumption/replay protection before disclosure.
- A verifiable requester identity assertion if the workflow is intended to attribute access to a human clinician. An API key authenticates a node/service, not an individual clinician.
- Source-local audit of the authenticated node, verified actor assertion (when present), grant, purpose, scope, outcome, and correlation/request identifier.
- Privacy opt-out and tenant data-use policy checks remain mandatory.

No caller-controlled token prefix, raw grant ID, or unverified actor header may substitute for those controls.

## Import integrity

`POST /api/federation/patients/import` is an authenticated local write operation, but it is not allowed to become a generic patient-creation endpoint.

The import path therefore:

1. Requires the submitted `source_mrn` to exist in the central discovery index for another active branch.
2. Resolves the source branch database from the control plane rather than trusting the request body.
3. Re-reads the source patient and source policy at import time.
4. Rejects source branches that are isolated or emergency-allergies-only for demographic import.
5. Re-evaluates the source privacy data-use policy.
6. Compares the submitted discovery summary with the current source patient and returns `409` when the record changed after discovery.
7. Copies patient demographics and allergies from the source database, not from caller-supplied clinical fields.
8. Uses ABHA first, then phone + date of birth + exact name, for local import idempotency.
9. Adds allergy provenance using the source branch code and preserves an existing `[Source: ...]` marker.
10. Writes an immutable source-tenant `FederationTransferLog` event with purpose `CONTINUITY_OF_CARE_IMPORT_REQUESTED` before committing the receiving-tenant clone. If the source audit write fails, the local import transaction is rolled back and no patient clone is committed.

The two databases cannot share one atomic transaction. The ordering therefore guarantees that a successful local import cannot exist without a prior durable source-side request record. If the later local commit fails, the source log remains an accurate record of an authorized import request/attempt, not proof that the destination clone completed. The explicit `REQUESTED` purpose avoids overstating the event. Retries can produce additional request events; the destination patient identity check still prevents duplicate local patient creation.

This is intentionally a two-read workflow: discovery provides a point-in-time transfer candidate, while import revalidates the source of truth before creating the local clone.

## Corporate group authorization

`CORPORATE_GROUP_ONLY` uses `TenantRegistry.corporate_group_id` in the central control-plane database. The value is an explicit trusted authorization attribute; branch-code prefixes, delimiters, naming conventions, and hospital names are never used to infer group membership.

The field is nullable for migration compatibility. A missing group assignment on either the authenticated requesting branch or source branch denies discovery/import. A trusted control-plane operator assigns or clears it through `PATCH /api/tenants/{slug}/entitlements` using the control-plane master setup key; include `corporate_group_id` to set it, pass `null` to clear it, or omit the field to leave it unchanged. The change is recorded in `ControlPlaneAuditLog` and exposed in the tenant fleet listing. The group identifier is not populated from tenant-supplied branch registration requests.

## Tenant and branch isolation

The application currently uses one tenant database per registered branch/subdomain. Federation is the explicit cross-database access path. Normal application tokens must match both tenant slug and branch code.

Do not introduce shared cross-branch ORM references as part of federation. A successful import creates a new local patient record; source records remain owned by the source branch database.

## Provenance and audit

Discovery transfer logs remain in the source tenant database. Requests log a PHI-minimized identifier where possible. **ABHA identifiers are never persisted in raw form in `FederationTransferLog`; the persistence-layer guard converts an `abha:<value>` identifier to a deterministic SHA-256 fingerprint.** This permits audit correlation without retaining the raw national identifier.

Each discovery log also snapshots the authenticated `FederatedNode.id` and `api_key_prefix`, alongside the authenticated branch code. The node ID and key prefix are scalar audit values rather than foreign keys because the node lives in the separate control-plane database while the transfer log is written to the source tenant database. This allows an auditor to identify the exact federation credential that performed the lookup without introducing cross-database referential integrity assumptions. Historical rows created before this migration retain null node/key attribution; they are not backfilled with guessed identities.

Local user-initiated imports are distinct from inbound federation discovery and therefore do not claim a remote node identity. Their requesting branch is recorded, while node/key attribution remains null.

**Actor attribution boundary:** a federation API key authenticates a hospital node/service, not the individual clinician using that hospital's application. The current protocol does not accept an unverified human identity header and does not claim to identify a remote clinician. For local imports, the source log records the destination branch; it does not assert that the source independently verified the destination user's identity. Human-level attribution requires a signed, verifiable actor assertion and remains a release gate for remote emergency disclosure.

Allergy provenance is carried in the clinical summary so downstream federation hops can retain the original source rather than replacing it with the requesting hospital.

`FederationTransferLog` is now treated as a true append-only audit record:

- New audit records sanitize raw ABHA identifiers before persistence.
- ORM mutation and deletion are rejected.
- The patient foreign key uses `RESTRICT`, preventing hard deletion of a patient from silently erasing transfer history.
- PostgreSQL has a `BEFORE UPDATE OR DELETE` trigger as a database-level defense against bulk SQL/ORM bypasses.
- Normal patient lifecycle should therefore use the application's existing soft-deactivation/retention mechanisms rather than hard deletion when transfer history exists.

Federation security changes must preserve:

- revoked/invalid federation keys returning `401`;
- one `[Source: ...]` marker per allergy reaction;
- source-tenant transfer logs;
- immutable transfer history;
- PHI-minimized audit identifiers, including fingerprinted ABHA values;
- patient privacy opt-out and tenant federation policy checks;
- branch/database isolation;
- tenant-bound federation credential registration;
- import idempotency and rollback on local database failure.

## Patient deactivation, erasure, and immutable audit retention

### Current behavior (not statutory erasure)

- `DELETE /api/patients/{patient_id}` is a soft-deactivation operation: it sets `Patient.is_active=false` and removes the matching `GlobalPatientPointer` from the central discovery index.
- It does not delete the patient row, clinical records, or federation transfer history. The response therefore says "deactivated and removed from the Central Discovery Index"; it must not imply that all copies or personal data have been erased.
- `FederationTransferLog.patient_id` currently has `ON DELETE RESTRICT`, and PostgreSQL prevents updates/deletes to transfer-log rows. This prevents silent audit destruction, but it also means a patient row referenced by a transfer log cannot be hard-deleted.
- The current transfer log still has a direct patient-row reference. It is therefore **not pseudonymized** merely because ABHA values in `requested_identifier` are fingerprinted.

### Required governed erasure workflow (not implemented)

A future erasure request must be evaluated by an authorized privacy/data-protection officer against the applicable jurisdiction, record category, statutory/clinical retention duties, legal holds, active disputes, and contractual obligations. No universal retention duration or automatic erasure rule is assumed here.

The workflow must distinguish at least:

1. **Access restriction / deactivation:** immediately prevent routine discovery and new use where legally permitted; revoke or remove central discovery pointers and federation eligibility.
2. **Retention hold:** preserve records that must remain for statutory, clinical, safety, audit, litigation, or other documented lawful purposes, with a recorded legal basis, scope, owner, and review date.
3. **Erasure approval:** require an explicit decision and evidence of authority; do not translate a request directly into a database cascade.
4. **Minimization / pseudonymization:** where retention of an audit event is required but direct identity is not, migrate the audit design to a non-reversible subject reference that is not a patient-table foreign key. Keep any re-identification mapping separately protected and access-controlled only where a lawful need exists.
5. **Execution and verification:** apply approved actions consistently to tenant databases, central discovery/index data, caches, exports, backups, and connected processors; record per-system outcomes and failures without copying unnecessary patient identifiers into the erasure register.
6. **Exceptions and review:** document partial refusal/deferment, legal basis, data categories retained, expiry/review trigger, approver, and the user's response/appeal route where required.

### Engineering release gates before implementing hard erasure

- Design a versioned retention schedule by record category and jurisdiction with named data controller/processor responsibilities. Legal/compliance owners must approve the schedule; engineering must not invent retention periods.
- Replace the direct immutable-log FK with a stable, non-identifying subject reference before any patient hard-delete path is enabled. Existing audit rows need a controlled backfill and verification plan.
- Preserve tamper evidence without freezing direct identifiers forever: immutable event payloads should contain only necessary minimized fields; subject-reference rotation or key destruction must not corrupt audit integrity.
- Define how clinical records, invoices, prescriptions, lab results, consent, ABHA mappings, and legal holds interact with erasure; federation logs are only one dependency.
- Define backup expiry/rewrite semantics and a verified restore procedure that reapplies completed erasure/tombstone instructions before restored data becomes available.
- Add an auditable request state machine, dual-control approval for exceptional hard deletion, idempotent execution, retry/reconciliation, and tests proving no cross-tenant effects.
- Until these controls and the legal schedule are approved, retain the existing soft-deactivation path and keep hard deletion disabled for patients with immutable audit references.

This section is an engineering control design, not legal advice and not evidence that statutory erasure is currently supported.


## Discovery completeness and pointer publication

Federated discovery responses include additive source-completeness metadata:
`source_count`, `source_success_count`, `source_failure_count`, `is_partial`, and
`failed_source_branches`. A successful response with `is_partial=true` is not a
complete federation view; callers must preserve and display that status rather than
treating missing source data as a negative clinical finding. If no source result can
be verified and at least one indexed source is unavailable, discovery returns
`503 Service Unavailable` with a PHI-minimized failure summary. A normal `404`
continues to mean that all evaluated sources completed but no shareable patient
record was found.

Patient-pointer publication distinguishes a privacy-policy denial (HTTP 403) from
control-plane persistence failure (server error). A successful evaluation does not
necessarily mean a pointer was published: patient opt-out and branch sharing policy
may intentionally suppress publication.

These completeness and persistence semantics do not change the separate release
gate for clinician attribution. Remote emergency federation remains disabled until
a source-verified, signed actor assertion is implemented and independently reviewed.


## Complete discovery receipts for patient import (AUD-003)

Patient import must not rely on caller-supplied `is_partial`, `source_failure_count`, or related counters. These fields are response metadata, not authorization evidence.

A successful discovery that has demographic authorization and has verified every indexed source issues a short-lived (two-minute) opaque receipt. The control-plane database stores only the SHA-256 hash of the random receipt token and binds it to:
- the authenticated federation node and its destination branch;
- the exact ABHA or normalized-phone selector hash;
- the complete indexed pointer snapshot (pointer IDs, branch codes, source MRNs, and pointer update timestamps);
- the selected demographic source pointer and patient MRN;
- a canonical digest of the complete discovery response, including the allergy summary.

The import endpoint requires the receipt, verifies expiry and node status, requires the same destination branch, recomputes the selector and current pointer snapshot, checks the exact response digest, and then repeats the source patient, privacy, and sharing-policy checks. A changed index or modified response requires rediscovery. The raw receipt is never stored or logged.

Receipts are intentionally reusable during their short lifetime so a client can safely retry the existing idempotent import flow after a transient failure. They do not bypass destination user permission checks, source policy checks, current source-patient validation, or the separate clinician-level actor assertion requirement. Partial or allergy-only discovery responses never receive an import receipt. Discovery excludes the requesting branch from the remote-source snapshot. A phone-only lookup that matches multiple distinct patient identities is rejected unless every remote branch has one record with the same non-empty ABHA; shared-phone household records are never merged as one patient.

This receipt protocol establishes discovery completeness and response integrity; it does not authenticate the human clinician. AUD-004 remains unresolved, and remote emergency federation remains disabled pending its separate actor-assertion protocol and independent security review.
