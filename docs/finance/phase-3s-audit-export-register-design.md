# Phase 3S — Audit Export Register and Accountability

## Objective

Provide a tenant-local, append-only accountability ledger for security audit exports. The register records who generated an export, when it was generated, the bounded selection criteria, the number of events included, and a SHA-256 digest of the exact exported representation. It is an accountability index, not an archive of the exported event data.

## Scope

- Register successful NDJSON exports produced by the existing `GET /api/audit/stream` endpoint.
- Record the requesting actor, UTC generation time, format/schema version, normalized time/category/severity filters, event count, and SHA-256 digest of the exact NDJSON bytes.
- Assign a stable export identifier and retain the original export metadata for later review.
- Expose a bounded, tenant-local register list and an individual register entry read API.
- Enforce privacy/audit read permission for register browsing; export generation continues to require `privacy:read`.
- Make register entries append-only at the database layer on PostgreSQL and SQLite.
- Keep register metadata minimal: no event bodies, patient identifiers, bank references, source identifiers, webhook credentials, or copied security-event details.
- Include the register table in controlled sandbox purge classification.

## Proposed API

- `GET /api/audit/stream`: existing NDJSON response; on successful materialization, persist one completed export register entry before returning the response.
- `GET /api/audit/exports`: list register metadata, newest first, with bounded pagination and optional date/category/actor filters.
- `GET /api/audit/exports/{export_id}`: read one register entry by ID.

The register list/detail APIs return only export metadata and never replay or download the exported event payload. Cross-tenant isolation is inherited from the tenant database boundary. Access to an entry from another tenant is therefore not addressable through the current tenant database.

## Integrity model

- Generate the NDJSON bytes once; hash those exact bytes and return those same bytes to the caller.
- Canonicalize the criteria JSON with sorted keys and compact separators before persistence.
- Store the SHA-256 digest, event count, UTC completion time, and a schema version.
- Use a database append-only guard for UPDATE and DELETE.
- A successful export is recorded in the same request path before the response is returned. If persistence fails, do not return an unregistered export.
- The digest proves consistency with the bytes presented by the exporter only when the consumer independently retains those bytes and recomputes the digest; it is not a digital signature or proof of source authenticity.

## Operational and privacy constraints

- Keep the current hard export limit and existing event filters.
- Do not store raw event payloads or credentials in the register.
- Store actor ID as an accountability reference, not a copied name/email. Access to identity details remains governed by the identity subsystem.
- Register browsing is read-only. No mutation, deletion, revocation, or re-export action is introduced.
- No object storage, long-term export archive, scheduled export, webhook delivery, external SIEM push, cryptographic signing, or PDF/CSV generation is included.
- Failed requests and permission denials are not represented as completed exports in this first iteration; a separate security-attempt ledger would be required to capture them consistently.

## Validation

- Migration/model parity on PostgreSQL 17 and metadata-created SQLite databases.
- Append-only UPDATE/DELETE enforcement on both supported database engines.
- Successful stream export creates exactly one register record and the digest matches the returned bytes.
- Register list/detail permission checks, bounded pagination, filter behavior, and tenant isolation.
- Register metadata contains no event body, patient ID, bank reference, webhook secret, or event details.
- Existing security event query, NDJSON shape, and SSRF protection tests remain green.
- Sandbox purge ordering and privacy route inventory remain consistent.
