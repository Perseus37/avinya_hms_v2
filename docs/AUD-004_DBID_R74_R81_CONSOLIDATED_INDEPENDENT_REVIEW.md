# AUD-004 DBID-R74–DBID-R81 Consolidated Proposal — Independent Review

**Target:** PR #68  
**Reviewed head:** `2687c5df634d66f9f94917e16dbceabdf601d641`  
**Review type:** Independent design-readiness review  
**Architecture baseline:** PostgreSQL database-per-tenant

## 1. Executive decision

PR #68 is a meaningful improvement in process discipline and architecture clarity. It explicitly retains database-per-tenant, distinguishes JSON Schema document contracts from PostgreSQL schemas, avoids adding more machine-readable schema files, and establishes a stop rule after this review.

However, PR #68 is a **requirements consolidation**, not an evidence-backed closure of DBID-R74–R81. It describes what an acceptable implementation must eventually prove, but does not provide the exact protocol artifacts, provider/platform-specific evidence or executable verification needed to mark the findings resolved.

This is not a criticism of choosing a requirements document instead of more schema files. The remaining work is primarily owner decisions, concrete deployment choices and evidence. Creating another automatic design PR would repeat the same loop. The appropriate next output is a consolidated implementation-readiness report and decision/ownership register, not another proposal PR.

## 2. Architecture confirmation

The document correctly states:
- retain PostgreSQL database-per-tenant;
- no schema-per-tenant migration is proposed;
- source-owned tenant access replaces destination-side foreign database connections;
- tenant runtime credentials must be scoped to their own tenant database;
- control-plane routing metadata is not a credential or authorization;
- provisioning, migration, backup and runtime identities remain distinct.

This is consistent with the database-per-tenant direction proposed in PR #44. PR #44 itself remains a draft proposal and has not been formally accepted. No storage-topology migration is authorized or required by this review.

The phrase JSON Schema in earlier PRs referred to JSON document validation contracts, not PostgreSQL schemas. PR #68 makes that distinction clear.

## 3. Remaining findings

### DBID-R74 — Critical: revocation ordering still lacks an approved authority contract

The proposal correctly distinguishes AUTHORITY_LEASE from SOURCE_BARRIER_EVENT and rejects point-in-time status queries as leases. It does not yet identify a real authority protocol, exact signed proof bytes, trust-root lifecycle, authority consistency guarantees, effective-time semantics or a formally accepted propagation-delay model. The source-side commit ordering cannot be proven until the external authority contract and operational owner are selected.

**Disposition:** OPEN — Critical. Requires named authority, protocol specification, security/clinical/privacy/legal acceptance and deterministic race evidence.

### DBID-R75 — High: sole-egress remains a target property, not a demonstrated boundary

The proposal lists relevant paths (middleware, proxy, sidecar, streaming, host actors) and distinguishes transport milestones. It does not select a concrete supported deployment topology, define the only artifact-read capability, establish network reachability restrictions or provide measured negative-test evidence that all alternate payload paths are blocked.

**Disposition:** OPEN — High. Requires selected deployment topology, principal/capability matrix, egress network enforcement and non-production negative tests.

### DBID-R76 — High: profile registry and envelope verification remain abstract

The proposal correctly removes algorithm assumptions and defines a fail-closed verification order. It does not define the exact byte representation of the outer envelope, registry canonicalization/digest, profile activation/revocation authority, key trust lifecycle or approved algorithm profile. These must be chosen by an accountable cryptography/security owner; they cannot be inferred from a design document.

**Disposition:** OPEN — High. Requires approved wire-format specification, immutable registry governance, cryptographic review and cross-language vectors.

### DBID-R77 — High: authenticated polling and redemption lack a concrete API contract

The proposal describes server-derived identity, one-time references, atomic consume and idempotency outcomes, but does not specify the concrete endpoint/API schemas, authentication mechanism, response status/body/header/cache equivalence, reference entropy/expiry values, durable storage constraints or exact recovery behavior after a lost redemption response.

**Disposition:** OPEN — High. Requires versioned API contract and executable replay, race, expiry, cross-tenant and response-equivalence tests.

### DBID-R78 — High: PostgreSQL ACL inventory needs a supported-version implementation and evidence

The proposal lists the right categories of PostgreSQL grants and privilege paths. It does not yet define the supported PostgreSQL major-version matrix, catalog extraction queries/adapters, stable object identity format, complete effective-privilege algorithm or independently reproducible inventory fixture/oracle. It also cannot establish current deployment privileges without live catalog evidence.

**Disposition:** OPEN — High. Requires database-owner decision on supported versions, catalog adapters, fixture corpus, independent privilege oracle and synthetic-cluster evidence.

### DBID-R79 — High: lifecycle verifier rules are not yet executable

The proposal lists graph properties to verify but does not define a complete lifecycle graph instance, exact canonicalization, deterministic error taxonomy, cycle/progress rules or a model-checking/conformance corpus. Some lifecycle decisions (including post-disclosure revocation and quarantine ownership) remain governance-dependent.

**Disposition:** OPEN — High. Requires complete graph and authority matrix, deterministic verifier specification, conformance/model-check suite and named clinical/privacy/operations owners.

### DBID-R80 — High: provider inventory completeness depends on provider-specific guarantees

The proposal correctly requires root-of-scope, snapshots, cursor chains, terminal-page proof and reconciliation. It does not identify supported providers/APIs, their snapshot consistency guarantees, authoritative inventory endpoints, pagination semantics, expected-count sources or independent witness implementation. Some providers may not offer a consistent snapshot; that limitation needs an explicit support policy.

**Disposition:** OPEN — High. Requires provider support matrix, provider-specific collection adapters, documented consistency limits and independently witnessed synthetic inventory tests.

### DBID-R81 — High: worker measurement requires a selected platform and trusted measurement source

The proposal lists security controls and says unknown/unmeasurable controls are NOT_READY. It does not select supported OS/runtime/provider profiles, define trusted measurement sources and trust roots, establish host-admin/agent threat assumptions, or provide signed observed-state evidence. Generic requirements cannot prove that seccomp, MAC, namespaces, network policy or capability restrictions are enforced in a real deployment.

**Disposition:** OPEN — High. Requires supported platform matrix, provider/host attestation design, measured policy verifier and hostile-host/negative tests.

## 4. Process and PR disposition

- PR #68 is a valid consolidated requirements proposal and should remain draft/unmerged until its owner decisions are accepted.
- PR #67 remains a useful record of the prior independent review.
- Do not create another automatic DBID proposal/review PR cycle from these findings.
- Produce one implementation-readiness report that groups remaining work by accountable owner: architecture/database, security/cryptography, clinical/privacy/legal, platform/operations and provider integration.
- Keep implementation blocked until DBID-R74 Critical and all High findings have objective evidence and independent sign-off.
- A future implementation plan should be a single bounded plan tied to accepted decisions, not another series of speculative contracts.

## 5. Project-wide blockers

DBID-06–08, CAN-01, CAN-02 and AUD-004 remain open. D-01–D-14 remain formally pending; D-11 project direction YES is not formal approval. Emergency federation remains disabled. PR #19 is still open/unmerged; this review does not authorize merging it or any other PR.

## 6. Evidence limitations

This review covers repository documentation and proposed contracts only. No deployed PostgreSQL catalogs, cloud/provider IAM, secret manager, network policy, egress proxy, host runtime, trust authority, audit store, backup system or patient data were inspected. No claim is made that production controls currently exist or are absent.

## 7. Explicit non-authorization

No runtime implementation, SQL, migrations, PostgreSQL database/schema changes, credential/role/ACL/network changes, secret provisioning, production or patient-data access, partner onboarding, trust provisioning, federation activation, emergency access, pilot, deployment, release or merge is authorized. Keep related PRs draft and unmerged. AUD-004 remains a release blocker.
