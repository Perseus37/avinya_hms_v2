# AUD-004 DBID-R66–DBID-R73 Resolution Proposal

**Status:** Design-only; pending independent review and formal governance. Parent review: PR #65.

## 1. DBID-R66 — authority proof instances

Separate static authority configuration from per-operation evidence. The new revocation proof schema defines a signed lease instance or signed source-barrier event, bound to authority/domain, immutable subject, source operation, destination, action/purpose, checkpoint, authority sequence, source generation, issue/expiry, nonce and exact proof digest. Source must verify proof and commit its digest/version with the release authorization in the same source consistency domain. A status query is never treated as a lease. Sequence gaps, stale generation, invalid signature, expired lease or authority outage fail closed. The authority's effective-time guarantee and legal/clinical propagation semantics remain approval-owned; no schema can manufacture linearizability.

## 2. DBID-R67 — sole-egress contract

Split internal stage command/result from externally visible API response and egress adapter operation. The stage result carries only operation ID and generic state; it never contains artifact bytes or an artifact locator usable by general application workloads. Only a separately identified egress workload can retrieve the staged artifact and verify the release permit. Its measured network capability is the only route to the recipient. The contract explicitly distinguishes permit commit, transport write attempt, local socket acceptance, remote receipt and delivery confirmation. If framework, middleware, proxy, sidecar or another process can emit payload bytes, deployment is NOT_READY. Deployment proof and negative tests remain mandatory.

## 3. DBID-R68 — profile-neutral envelope

The inherited envelope schema is replaced with a closed profile-neutral outer envelope. It carries a profile ID/version and immutable registry digest, opaque manifest bytes, signature object, recipient key reference, encryption metadata, AAD bytes and ciphertext bytes as encoded opaque values. It no longer hardcodes JCS, SHA-256, base64url, signature algorithm, nonce/tag lengths or digest length. A profile-specific validator selected by the exact immutable approved registry entry validates all inner bytes and algorithm-specific fields. Registry lookup, schema selection and revocation are fail-closed. The registry generation/digest and selected profile are signed into the operation and receipt. No cryptographic algorithm is approved here.

## 4. DBID-R69 — complete operation binding

The new operation contract binds authenticated server-derived poll identity, candidate reference, redemption request, staged artifact, egress permit, transport milestones and receipt to one immutable operation/binding digest. Polling input never supplies trusted actor identity. Server-side authentication context is captured from mTLS/workload identity and tenant routing, then checked against the stored operation. Same idempotency key + same canonical request digest returns the same operation; same key + different digest conflicts; concurrent claim has one winner. Candidate reference is one-time and atomic with operation claim. Lost-response status retrieval does not reread source data or bypass egress.

## 5. DBID-R70 — complete ACL evidence bundle

The ACL evidence schema now requires digest-addressed typed inventories for cluster identity, all databases including templates/control, roles and attributes, membership edges/options, database/schema/object ACLs, ownership, default ACLs by creator, PUBLIC ACLs, extensions, privileged routines, FDW/dblink and exceptions. Every grant remains a per-privilege tuple with its own grant option. Catalog snapshot and PostgreSQL-major adapter are bound to evidence. Independent verifier output signs policy, inventory, snapshot, adapter and oracle digests. Any inaccessible/unknown scope or object yields UNKNOWN/NOT_READY, never PASS.

## 6. DBID-R71 — lifecycle graph attestation

The graph schema provides unique state/transition identifiers and explicit references; a separate deterministic verifier checks initial-state existence, reachability, terminal-state rules, required timeout/failure/uncertain paths, cycle/progress constraints and transition authority. Signed verifier output binds exact canonical registry digest, schema version, verifier build, policy generation and signer trust root. Producer-supplied PASS is not trusted without independent signature and registry-digest verification. Graph completeness remains an executable verifier property, not a JSON Schema claim.

## 7. DBID-R72 — provider-rooted inventory proof

The trust evidence schema requires provider snapshot/request evidence, per-scope contiguous pagination records, terminal-page proof, raw response digests, root-to-scope reconciliation, explicit inaccessible/unsupported/excluded/deleted/unknown scopes, unique resource and edge IDs, and referential checks. Independent verifier output signs all root/snapshot/page/resource/edge/exception digests and count reconciliation. Witness binds verifier result, all evidence digests, trust-root version, monotonic generation and previous checkpoint. Unknown or inaccessible required scopes block PASS.

## 8. DBID-R73 — measured worker attestation

Worker evidence separates desired policy from trusted observed measurements. Mandatory controls must be secure and measurable; core dumps must be disabled, swap cannot be UNKNOWN, MAC must be approved and enforced, cgroups must have numeric bounded values, network policy must include effective route evidence, and host actor capabilities must be enumerated. Collector evidence binds workload/image/host/boot/runtime, platform-specific profile, raw measurement digest and attestation chain. Verifier checks freshness and revocation against an independently trusted root. Unsupported/unmeasurable controls are NOT_READY.

## 9. Cross-contract invariants and validation

- Revocation proof digest and generation bind to the operation's release authorization.
- Stage result has no payload locator or response-body capability; egress adapter is the sole artifact reader and network writer.
- Envelope profile ID/version/registry digest match the immutable approved profile and exact profile-specific validator.
- Poll, candidate, redemption, artifact, permit and receipt share operation ID and binding digest.
- ACL PASS binds a complete cluster inventory and PostgreSQL-major-specific verifier result.
- Lifecycle PASS binds exact canonical registry digest and independently trusted verifier.
- Trust witness binds all provider evidence and monotonic checkpoint.
- Worker PASS binds signed platform measurement and verifier trust chain.

Required tests: authority lease expiry/revocation interleavings; egress route bypass and middleware buffering; profile mismatch/downgrade/malformed byte vectors; cross-tenant poll and replay; mixed ACL grant-option and inherited membership fixtures; invalid graph and forged PASS; missing provider page/cursor gap/orphan edge; forged/stale worker measurement and permissive runtime controls.

JSON parsing alone is not schema validation; schema validation alone does not prove authority guarantees, provider completeness, effective PostgreSQL privileges or platform enforcement.

## 10. Open decisions and stop conditions

DBID-06–08, CAN-01, CAN-02 and AUD-004 remain open. D-01–D-14 remain formally pending; D-11 project direction YES is not formal approval. Algorithm/profile approval, authority effective-time semantics, provider/platform support, retention/residency, quarantine governance, deployment topology, verifier/witness custody and operational ownership remain unresolved.

Design only. No runtime code, SQL, migrations, database/role/ACL/network changes, credentials, production/patient-data access, partner onboarding, trust provisioning, federation activation, emergency access, pilot, deployment, release or merge authorized. Keep PR draft and unmerged. AUD-004 remains a release blocker.
