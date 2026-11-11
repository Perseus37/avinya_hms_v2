# Tenant Document Storage Architecture

## Purpose

Provide one tenant-scoped storage boundary for files that belong to a hospital tenant while keeping each feature responsible for its own authorization, validation, malware scanning, audit records, and retention policy.

The current implementation is filesystem-backed through `ATTACHMENTS_STORAGE_DIR`. This document describes the implemented boundary and the rules future document workflows must preserve.

## Current storage namespaces

| Resource | Tenant namespace | Read policy | Write policy |
| --- | --- | --- | --- |
| Tenant logo/favicon | `branding-assets` | Public, resolved tenant only; required by login bootstrap | `config:write` |
| Procurement invoice | `procurement-invoices` | Authenticated, permission-gated; download is audited | Procurement upload permission and vendor validation |

Clinical records, lab reports, prescriptions, patient attachments, and other private documents must not be exposed through the public branding route or a static web-server directory.

## Tenant and branch isolation boundary

The control-plane `TenantRegistry` maps each active subdomain to one unique branch code and one unique tenant database name. The request resolver selects that database before application-domain queries execute. Procurement and insurance tables therefore live inside the selected branch database; their records are not shared across branch databases by default.

Access tokens carry both `tenant_slug` and `branch_code`. Authentication validates both claims against the resolved tenant context. A token for one branch cannot be replayed against another branch, and a mismatched branch claim is rejected even if the token signature is otherwise valid.

Cross-branch patient discovery, import, or pull must use the explicit federation/import workflows and provenance/audit controls. Do not add ordinary cross-branch joins or shared procurement/insurance catalogs without an approved architecture decision. If the deployment later changes to multiple branches inside one tenant database, explicit branch identifiers and query-level enforcement will be required before that topology is enabled.

Regression coverage for procurement invoice/document isolation, insurance provider catalog isolation, and token branch-claim binding lives in `tests/test_67_branch_isolation.py`.

## Shared filesystem primitives

`backend/core/storage.py` currently provides:

- `tenant_storage_directory(root, tenant_slug, namespace, create=...)`: validates tenant and namespace components, creates directories with restrictive permissions when requested, and rejects symlinked tenant or namespace directories.
- `resolve_tenant_storage_file(directory, filename)`: permits only a single child filename and rejects traversal and symlinked files.
- `stage_and_publish_upload(...)`: streams in bounded chunks to an exclusive temporary file, applies restrictive file permissions, validates the leading signature and optional feature-specific staged-file checks, invokes the supplied malware scanner, then atomically publishes the destination. It removes only a temporary file created by that invocation when any step fails.

The utility intentionally does not decide whether a caller is authorized to read or write a document. It does not define accepted extensions/signatures, scanner policy, audit logging, database metadata persistence, or post-commit orphan cleanup. Feature code supplies those policies and maps shared upload exceptions to its API contract.

## Required upload lifecycle

1. Resolve the active tenant from the authenticated request context. Never accept a tenant slug from an upload form as the authority for tenant ownership.
2. Authorize the feature operation and validate the related business record.
3. Use a feature-specific namespace under the tenant directory.
4. Generate an opaque server-side identifier; never use the submitted filename as the storage key.
5. Stream with a configured byte limit and validate file signatures. Treat MIME headers and extensions as untrusted hints.
6. Stage the file with restrictive permissions, scan it, and publish it atomically only after a clean scanner verdict.
7. Persist the tenant-relative key and required audit event. If persistence fails, remove the newly published file best-effort and retain enough logs for orphan reconciliation.
8. Keep private files outside public static mounts.
9. Return downloads with an attachment disposition, a server-generated filename, `X-Content-Type-Options: nosniff`, and private no-store cache headers. Keep private document responses same-origin; do not allow shared intermediary/browser caches to retain patient, billing, or procurement records.

## Required download lifecycle

1. Resolve tenant context from the request and load the document metadata from that tenant's database.
2. Apply the feature's read permission and verify the related record belongs to the same tenant.
3. Resolve the stored tenant-relative key through the shared storage boundary.
4. Record the authorized download event where required by policy.
5. Return a controlled content type, safe content disposition, and `X-Content-Type-Options: nosniff`. Do not expose raw filesystem paths.

Branding is the deliberate exception to authenticated reads: only opaque raster assets referenced by the resolved tenant's branding configuration are served publicly. The endpoint remains tenant-scoped and does not accept arbitrary paths.

## Operational requirements

- Production must mount durable private storage at the configured `ATTACHMENTS_STORAGE_DIR`; container writable layers are not durable storage.
- The API and worker identities need only the permissions required for their storage operations. Keep tenant directories at `0700` and staged files at `0600` on POSIX filesystems.
- Backup and restore procedures must treat the attachment tree as a separate recovery component from PostgreSQL. A database restore without the corresponding files can leave valid metadata pointing to missing content.
- Run branding orphan reconciliation only against the same persistent mount used by the application.
- Monitor free space, inode usage, scanner availability, upload failures, and backup freshness.

## Object storage migration boundary

An S3-compatible backend is not implemented yet. When introduced, it should sit behind a storage adapter with the same tenant-relative key and authorization contract. Use private buckets, server-side encryption, TLS, short-lived signed downloads only after application authorization, lifecycle/retention controls, and an explicit malware-scanning/quarantine workflow. Do not make a bucket public to simplify branding: public branding should remain an application-controlled, tenant-resolved read.

## Known limitations

- The shared helper centralizes path and symlink checks, but path-based filesystem operations are not a complete defense against a hostile local process racing directory replacement. Production storage mounts must not be writable by untrusted local users. A hardened object-store adapter or descriptor-relative filesystem implementation may be warranted for deployments with that threat model.
- Branding and procurement now share bounded staging, signature-prefix validation, malware-scan invocation, failure cleanup, and atomic publication. Feature-specific extension rules, WebP container validation, scanner implementation, authorization, and metadata/audit transactions remain in their owning modules.
- The upload helper uses path-based operations; the documented local-process directory-replacement race limitation still applies.

Generated PDF attachment responses use `backend/core/document_responses.py` to standardize sanitized filenames, `Cache-Control: private, no-store`, `nosniff`, and same-origin response policy. Stored procurement invoice downloads apply equivalent private cache and content-sniffing headers through `FileResponse`.
- No general clinical-document upload/download API or document retention engine is claimed by this implementation.
