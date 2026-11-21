# AUD-004 Implementation Readiness and Owner Register

**Status:** IMPLEMENTATION BLOCKED — proposed ownership model; no accountable individuals have been formally assigned  
**Snapshot date:** 2026-11-21  
**Architecture invariant:** PostgreSQL database-per-tenant. No schema-per-tenant migration is proposed.  
**Authority:** This register tracks readiness and ownership gaps. It does not approve policy, implementation, production access, pilot or release.

## 1. Executive readiness decision

AUD-004 is **NOT READY FOR IMPLEMENTATION OR RELEASE**.

The repository contains substantial design proposals, independent reviews and JSON Schema document contracts. Those artifacts are not proof that the controls exist in runtime code or are enforced by a deployed PostgreSQL cluster, provider account, network, secret store, worker platform or egress boundary.

The following remain release blockers:

- CAN-01 through CAN-06: source-owned authorization, selector privacy, trusted discovery/fan-out, durable import correctness, clinical/privacy ownership and anti-enumeration.
- DBID-01 through DBID-05: High-severity database identity, role, credential and source-audit controls.
- DBID-06 through DBID-08: Medium-severity backup/restore, deployment-matrix and non-authoritative naming controls.
- DBID-R74: Critical revocation authority/effective-time proof.
- DBID-R75 through DBID-R81: High-severity egress, wire, polling, ACL, lifecycle, provider coverage and worker measurement controls.
- D-01 through D-14: formal governance decisions remain pending. D-11 project direction YES is not formal approval.

No finding is closed by a proposal, review document, schema file, green CI run, synthetic fixture or assertion from the component being evaluated.

## 2. Ownership status and assignment rule

No named accountable owner or formal approver is evidenced in the reviewed repository artifacts. Accordingly, **all named-person assignments below are UNASSIGNED**. Role labels describe the expertise required; they do not imply that a person or team has accepted accountability.

Before implementation planning can be approved, the governance chair must record for every workstream:
1. one named accountable owner;
2. one named independent approver/reviewer who is not the implementer;
3. the delegated authority and scope of each person;
4. acceptance criteria and required evidence;
5. target date, dependencies and escalation path.

A team alias, vendor, PR author or document author is not a substitute for a named accountable owner. If a required role cannot be staffed, the related gate remains BLOCKED.

## 3. Proposed workstream ownership matrix

| Workstream | Proposed accountable role (person unassigned) | Required independent approver | Scope and deliverables | Current status |
|---|---|---|---|---|
| Architecture and tenant identity | Enterprise/solution architect | Architecture governance chair | Preserve database-per-tenant; reconcile control-plane and tenant identities; approve topology and trust boundaries | UNASSIGNED / BLOCKED |
| PostgreSQL identity and ACL | PostgreSQL/database security owner | Independent database security reviewer | Cluster roles, CONNECT, memberships, ownership, object/default ACLs, SECURITY DEFINER, extensions, provider-specific effective privileges | UNASSIGNED / BLOCKED |
| Federation source authorization | Federation/security engineering owner | Independent application security reviewer | Source-owned authorization for remote and local cross-branch access; remove destination direct foreign-database reads | UNASSIGNED / BLOCKED |
| Import integrity and recovery | Patient-data/platform engineering owner | Independent data-integrity reviewer | Durable operation identity, unique claims, fencing, atomic clone/provenance/marker, acknowledgement, pointer sync and quarantine | UNASSIGNED / BLOCKED |
| Cryptography and protocol | Security/cryptography owner | Independent cryptographic reviewer | Approved wire profile, key authority/lifecycle, canonical encoding, signature/AAD vectors, envelope and replay protection | UNASSIGNED / BLOCKED |
| Revocation authority | Security governance owner | Legal/privacy and independent security approvers | Select authority, proof format, trust lifecycle, freshness, effective-time semantics and race/partition behavior | UNASSIGNED / BLOCKED |
| Egress and network isolation | Platform/network security owner | Independent infrastructure security reviewer | Sole egress capability, network policy, permit/nonce/fencing, transport evidence and negative tests | UNASSIGNED / BLOCKED |
| Provider coverage and trust graph | Cloud/platform security owner | Independent cloud assurance reviewer | Provider roots, supported APIs, pagination/snapshot completeness, graph verification and independent witness | UNASSIGNED / BLOCKED |
| Worker platform measurement | Runtime/platform security owner | Independent platform assurance reviewer | Supported host profiles, trusted measurement source, attestation chain, freshness and enforcement tests | UNASSIGNED / BLOCKED |
| Clinical safety and disposition | Clinical governance lead | Independent clinical safety approver | Clinical purpose, minimum necessary projection, allergy/record handling, quarantine and break-glass policy | UNASSIGNED / BLOCKED |
| Privacy and retention | Privacy/DPO delegate | Legal/privacy governance approver | Purpose limitation, selector privacy, disclosure audit, retention, deletion/tombstones and data-subject rights | UNASSIGNED / BLOCKED |
| Legal and partner governance | Legal/compliance owner | Authorized legal approver | Data-sharing basis, partner terms, jurisdiction, residency and external authority enforceability | UNASSIGNED / BLOCKED |
| Operations, backup and DR | SRE/operations owner | Independent operations risk approver | Backup/restore identity, DR, retention, monitoring, incident response, migration and rollback evidence | UNASSIGNED / BLOCKED |
| Independent verification | Assurance/test owner | Governance-appointed independent assessor | Cross-layer threat model, deterministic test corpus, evidence provenance and closure verification | UNASSIGNED / BLOCKED |
| Release governance | AUD-004 governance chair | Authorized release authority | Confirm all Critical/High gates closed, residual risks accepted and evidence independently signed | UNASSIGNED / BLOCKED |

## 4. Finding-to-owner and closure register

The roles below are proposed routing only. They are not assignments. Every item remains OPEN until the required evidence is produced and independently accepted.

| Finding | Proposed accountable role | Minimum closure evidence | Status |
|---|---|---|---|
| CAN-01 / CAN-01A–C | Federation/security engineering + database security | Complete runtime path inventory; source-owned authorization; no foreign DB sessions from destination identity; effective-role negative tests across routes, jobs, admin, support, retry and recovery | OPEN |
| CAN-02 | Security/cryptography + privacy | Approved keyed selector commitment, canonicalization, key custody/rotation and privacy/guessing tests; no plain/global deterministic low-entropy selector hash | OPEN |
| CAN-03 | Federation/security engineering | Trusted eligible-source registry, bounded fan-out, partial-outcome contract and anti-enumeration tests | OPEN |
| CAN-04 | Patient-data/platform engineering | Immutable import identity, destination unique claim, atomic clone/provenance/marker, fencing, acknowledgement and lost-response/concurrency tests | OPEN |
| CAN-05 | Clinical governance + privacy | Named clinical/privacy/operations owners and approved post-commit quarantine, retention and reconciliation semantics | OPEN |
| CAN-06 | Application security | Externally testable response equivalence, cache behavior, rate limits and enumeration tests | OPEN |
| DBID-01–05 | Database security + platform security | Cluster-wide role/CONNECT/object grants, owner and membership closure, secret isolation/rotation/revocation/pool invalidation, provisioning/migration separation and source-audit transaction proof | OPEN — HIGH |
| DBID-06–08 | Operations + architecture + database security | Backup/restore alternate-path controls, supported deployment matrix and proof that names/routing metadata are not credentials or authorization | OPEN — MEDIUM |
| DBID-R74 | Security governance / revocation authority | Approved external authority and trust lifecycle; signed operation-scoped proof; effective-time semantics; freshness/partition behavior; deterministic race and stale-proof tests | OPEN — CRITICAL |
| DBID-R75 | Platform/network security | Selected deployment topology; sole artifact-read/egress capability; enforceable network boundary; negative tests for bypass and stale workers | OPEN — HIGH |
| DBID-R76 | Security/cryptography | Immutable approved profile registry; exact byte encoding, signature/AAD/envelope binding; cross-language positive/negative vectors and key lifecycle | OPEN — HIGH |
| DBID-R77 | Federation/API security | Versioned authenticated polling/redemption contract; recipient and actor binding; one-time reference lifecycle; idempotency, replay and response-equivalence tests | OPEN — HIGH |
| DBID-R78 | PostgreSQL/database security | Supported major/provider catalog adapters; complete lossless cluster-wide ACL inventory; independent effective-privilege oracle; synthetic-cluster and omission tests | OPEN — HIGH |
| DBID-R79 | Assurance/test + platform engineering | Normative lifecycle graph, authority matrix, deterministic verifier, full transition/error taxonomy, model-check/conformance and crash/retry corpus | OPEN — HIGH |
| DBID-R80 | Cloud/platform assurance | Provider support matrix; root-of-scope and pagination proof; immutable snapshots; reconciliation and independent completeness witness | OPEN — HIGH |
| DBID-R81 | Runtime/platform security | Supported worker profiles; trusted measured-state source; attestation chain, freshness and independent enforcement verification | OPEN — HIGH |

## 5. Governance decision register

D-01 through D-14 are formally pending in the canonical baseline. The exact decision titles, decision owners, approvers and evidence links must be copied from the authoritative governance decision log when it is available. This register intentionally does not infer or fabricate the subject of an individual D-number.

| Decision | Accountable owner | Authorized approver | Evidence / decision record | Status |
|---|---|---|---|---|
| D-01 | UNASSIGNED | UNASSIGNED | Link to approved decision record required | PENDING |
| D-02 | UNASSIGNED | UNASSIGNED | Link to approved decision record required | PENDING |
| D-03 | UNASSIGNED | UNASSIGNED | Link to approved decision record required | PENDING |
| D-04 | UNASSIGNED | UNASSIGNED | Link to approved decision record required | PENDING |
| D-05 | UNASSIGNED | UNASSIGNED | Link to approved decision record required | PENDING |
| D-06 | UNASSIGNED | UNASSIGNED | Link to approved decision record required | PENDING |
| D-07 | UNASSIGNED | UNASSIGNED | Link to approved decision record required | PENDING |
| D-08 | UNASSIGNED | UNASSIGNED | Link to approved decision record required | PENDING |
| D-09 | UNASSIGNED | UNASSIGNED | Link to approved decision record required | PENDING |
| D-10 | UNASSIGNED | UNASSIGNED | Link to approved decision record required | PENDING |
| D-11 | UNASSIGNED | UNASSIGNED | Project direction YES is recorded; formal approval and evidence still required | PENDING |
| D-12 | UNASSIGNED | UNASSIGNED | Link to approved decision record required | PENDING |
| D-13 | UNASSIGNED | UNASSIGNED | Link to approved decision record required | PENDING |
| D-14 | UNASSIGNED | UNASSIGNED | Link to approved decision record required | PENDING |

A decision is approved only when its exact question, options, selected outcome, rationale, accountable owner, authorized approver, effective date, expiry/review date and supporting evidence are recorded. Silence, PR merge, project direction or CI success is not approval.

## 6. Evidence and verification plan

All evidence must be scoped, reproducible, timestamped and attributable. Evidence generated by the system under evaluation is not sufficient by itself to prove that system's completeness or isolation.

| Gate | Required evidence | Independent verification |
|---|---|---|
| Source boundary | Route/job/admin/support/retry/recovery inventory; runtime identity map; database-role denial tests | Independent security reviewer confirms no destination path can read a foreign tenant database |
| PostgreSQL isolation | Catalog snapshots, role memberships, CONNECT and object privilege closure, owner/default ACL and privileged routine inventory | Independent oracle recomputes effective access for every service principal |
| Secrets and sessions | Secret-manager policy, workload identity, rotation/revocation records, pool invalidation and negative access tests | Security reviewer verifies no fleet-wide tenant credential bundle or stale session survives revocation |
| Import correctness | Unique operation claim, transaction traces, crash-window and concurrent multi-session tests, pointer reconciliation evidence | Independent data-integrity reviewer verifies idempotency and fencing |
| Revocation | Authority trust chain, signed proof, freshness/effective-time contract, partition and race tests | Independent authority/security reviewer validates proof and ordering semantics |
| Egress | Network policy, workload identity, sole egress deployment evidence, permit acceptance and transport audit | Independent network assessor tests all bypass paths and stale-worker scenarios |
| Cryptography | Approved profile record, key lifecycle evidence, canonical bytes and cross-language test vectors | Independent cryptographic review reproduces vectors and rejects malformed/replayed inputs |
| Provider coverage | Provider account/root inventory, page tokens/counts/snapshots, missing/extra reconciliation and witness checkpoint | Independent cloud assurance verifies scope and completeness |
| Worker trust | Platform profile, measured boot/runtime evidence, attestation chain, verifier version and expiry | Independent platform assessor validates the measurement source and enforcement |
| Clinical/privacy | Approved purpose/projection, data-flow, retention, quarantine and incident procedures | Named clinical, privacy and legal approvers sign the exact operating model |
| Operations/DR | Backup/restore, failover, migration, rollback, monitoring and incident-response exercises | Independent operations review confirms alternate paths preserve isolation and audit |
| Release | Closure matrix for every Critical/High item, residual-risk decisions and evidence index | Governance-appointed release authority signs the release decision |

## 7. Implementation sequence — gated, not authorized

The following order is a planning dependency only. It does not authorize starting implementation.

1. Assign named owners and approvers; establish the authoritative D-01–D-14 decision log.
2. Confirm database-per-tenant identity and source-owned authorization boundaries.
3. Complete runtime path and pointer-writer inventories; resolve CAN-01 through CAN-06.
4. Approve revocation authority, cryptographic profile and provider/platform support decisions.
5. Specify and independently verify PostgreSQL role/ACL, secret, egress, lifecycle and trust evidence contracts.
6. Design import idempotency, fencing, acknowledgement, pointer synchronization and quarantine semantics.
7. Build deterministic non-production tests with synthetic data and isolated identities only after the relevant design approvals.
8. Obtain independent clinical, privacy, legal, security, database and operations sign-off.
9. Conduct separate production deployment and disaster-recovery evidence review before any controlled pilot.
10. Release authority records an explicit decision; absent approval, remain NOT_READY.

Dependencies must be represented in the project tracker with owner, evidence artifact, reviewer, status and blocked-by references. No task may be marked complete solely because a document or schema was merged.

## 8. Explicit readiness stop conditions

Keep AUD-004 blocked if any of the following is true:

- any Critical or High finding is open, disputed or supported only by design assertions;
- any required owner, independent reviewer or authorized approver is unassigned;
- any PostgreSQL/provider/platform behavior is unsupported or UNKNOWN;
- any foreign-tenant database access path remains reachable by a destination identity;
- any revocation, freshness, transport, import or pointer-sync outcome is uncertain without a fail-closed reconciliation path;
- any required audit, evidence witness, secret authority or independent verifier is unavailable;
- any formal D-01–D-14 decision is pending;
- emergency federation, partner trust or pilot readiness is inferred without separate approval.

## 9. Relationship to repository evidence

- The canonical baseline and decision register is the navigation/traceability record; it does not supersede formal governance decisions.
- Design proposals and independent reviews remain supporting evidence and retain their own status.
- PR #19 runtime remediation remains separate and has documented import idempotency, pointer synchronization and source-boundary follow-ups.
- PR #71 is a disposable synthetic PostgreSQL ACL proof harness only. It does not prove deployed workload identity, production grants or actual tenant isolation.
- CI validates repository artifacts and test behavior at a specific commit; it does not establish live provider, database, network, key, worker or production state.

## 10. Non-authorization and change control

This register authorizes documentation and readiness tracking only. It does NOT authorize runtime code changes, SQL, migrations, PostgreSQL role/ACL/network/secret changes, production or patient-data access, partner onboarding, trust provisioning, federation activation, emergency access, pilot, deployment, release or merge.

PostgreSQL **database-per-tenant** remains unchanged. No schema-per-tenant conversion is proposed. JSON Schema files under `docs/schemas/` describe JSON documents; they are not PostgreSQL schemas, namespaces or migrations. Emergency federation remains disabled.

Update this register only when a named owner/approver, decision record or evidence artifact is verifiably available. Preserve prior decisions and record who changed the status, when, and on what evidence.
