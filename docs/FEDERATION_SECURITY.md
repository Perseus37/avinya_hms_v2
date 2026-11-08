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

The field is nullable for migration compatibility. A missing group assignment on either the authenticated requesting branch or source branch denies discovery/import. Existing tenants must be assigned by a trusted control-plane operator before corporate-group federation can work. The group identifier is not populated from tenant-supplied branch registration requests.

## Tenant and branch isolation

The application currently uses one tenant database per registered branch/subdomain. Federation is the explicit cross-database access path. Normal application tokens must match both tenant slug and branch code.

Do not introduce shared cross-branch ORM references as part of federation. A successful import creates a new local patient record; source records remain owned by the source branch database.

## Provenance and audit

Discovery transfer logs remain in the source tenant database. Requests log a PHI-minimized identifier where possible. **ABHA identifiers are never persisted in raw form in `FederationTransferLog`; the persistence-layer guard converts an `abha:<value>` identifier to a deterministic SHA-256 fingerprint.** This permits audit correlation without retaining the raw national identifier.

Each discovery log also snapshots the authenticated `FederatedNode.id` and `api_key_prefix`, alongside the authenticated branch code. The node ID and key prefix are scalar audit values rather than foreign keys because the node lives in the separate control-plane database while the transfer log is written to the source tenant database. This allows an auditor to identify the exact federation credential that performed the lookup without introducing cross-database referential integrity assumptions. Historical rows created before this migration retain null node/key attribution; they are not backfilled with guessed identities.

Local user-initiated imports are distinct from inbound federation discovery and therefore do not claim a remote node identity. Their requesting branch is recorded, while node/key attribution remains null.

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