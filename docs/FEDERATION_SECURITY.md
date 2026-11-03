# Federation Security Boundaries

## Discovery authentication

Cross-branch discovery requires an active `FederatedNode` API key. Keys are stored as SHA-256 hashes and revoked keys return `401 Unauthorized`.

The calling branch identity comes from the authenticated federation node, not from a request-supplied branch field.

## Emergency federation

`EMERGENCY_ALLERGIES_ONLY` is intentionally fail-closed.

- `purpose=EMERGENCY` is not authorization by itself.
- A caller-controlled string such as `EMERGENCY-*` is not a valid credential.
- A `BreakGlassGrant` must exist in the source branch database.
- The grant must be unexpired and bound to the exact source patient being disclosed.
- The existing privacy data-use decision is still evaluated after emergency authorization.

A future interoperable emergency token must be cryptographically verifiable and explicitly bound to the requesting branch, source patient, purpose, expiry, and issuer. It must not be implemented as a prefix or length check.

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
10. Writes a source-tenant `FederationTransferLog` for the import operation.

This is intentionally a two-read workflow: discovery provides a point-in-time transfer candidate, while import revalidates the source of truth before creating the local clone.

## Tenant and branch isolation

The application currently uses one tenant database per registered branch/subdomain. Federation is the explicit cross-database access path. Normal application tokens must match both tenant slug and branch code.

Do not introduce shared cross-branch ORM references as part of federation. A successful import creates a new local patient record; source records remain owned by the source branch database.

## Provenance and audit

Discovery transfer logs remain in the source tenant database. Requests log a PHI-minimized identifier where possible. Allergy provenance is carried in the clinical summary so downstream federation hops can retain the original source rather than replacing it with the requesting hospital.

Federation security changes must preserve:

- revoked/invalid federation keys returning `401`;
- one `[Source: ...]` marker per allergy reaction;
- source-tenant transfer logs;
- patient privacy opt-out and tenant federation policy checks;
- branch/database isolation;
- import idempotency and rollback on local database failure.
