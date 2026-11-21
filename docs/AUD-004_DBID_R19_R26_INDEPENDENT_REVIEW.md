# AUD-004 DBID-R19–DBID-R26 Independent Review

**Review target:** PR #54 — DBID-R19–DBID-R26 Resolution Proposal  
**Review type:** Independent documentation/security architecture review  
**Status:** DESIGN REVIEW ONLY — NOT IMPLEMENTATION APPROVAL  
**Release status:** AUD-004 remains a release blocker.

## 1. Executive conclusion

PR #54 materially improves the design. It correctly recognizes that trust inventory must include control-plane mutation paths, that PostgreSQL roles are cluster-wide, that source reads and network release need separate authorization fences, and that source authorization, artifact integrity, destination receipt, durable commit and pointer synchronization are distinct evidence.

However, the proposal does not yet close DBID-R19–DBID-R26. Several sections define desired outcomes while leaving the enforceable protocol, exact data model, serialization rules or evidence contract to future work. The most consequential residual risk is DBID-R21: the proposed authorization-epoch lock is a useful direction, but the transaction ordering and network release linearization are not specified sufficiently to prove the promised revocation behavior. The ACL and wire-format sections also remain schemas-by-description rather than complete normative specifications.

The findings below are residual design gaps, not claims that a production system is exploitable. No production infrastructure, live PostgreSQL catalogs, credentials, secret manager, network configuration, audit store or patient data were inspected.

## 2. Findings summary

| ID | Severity | Finding |
|---|---|---|
| DBID-R27 | High | Coverage manifest does not prove closed-world inventory or complete transitive control-path enumeration |
| DBID-R28 | High | Selector outcome and resource-budget contract remains non-executable and does not fully bind candidate redemption |
| DBID-R29 | Critical | Read/revocation and release/revocation ordering still lacks a complete implementable linearization protocol |
| DBID-R30 | High | Cluster-wide role identity and database access model lack stable principal/authentication binding and complete role semantics |
| DBID-R31 | High | Signed manifest, AAD and chunk profile remain descriptive; exact canonical bytes and cryptographic constructions are not fixed |
| DBID-R32 | High | ACL manifest and effective-privilege model are still placeholders, not a complete machine-readable policy |
| DBID-R33 | Medium | Attestation freshness, independence and rollback protocol lacks an authoritative event/checkpoint and recovery contract |
| DBID-R34 | High | End-to-end lifecycle matrix leaves critical authority transitions and post-revocation acceptance semantics unresolved |

## 3. Detailed findings

### DBID-R27 — High: Coverage manifest does not prove closed-world inventory

**Affected section:** §2 DBID-R19.

The proposal lists many relevant control planes and requires coverage counters, snapshots and independent evidence. This is a strong improvement. But a coverage manifest can still be internally complete while omitting an entire authoritative account, organization, provider support plane, network fabric or identity issuer. Expected object counts and pagination completion prove completeness only within the queried scope; they do not prove that the scope itself is complete.

The graph's node/edge model is also not yet a normative schema. The proposal names edge types and required attributes but does not specify how resource identifiers are normalized across providers, how deleted/transient resources are represented, how multiple evidence sources are reconciled, how conflicting observations are resolved, or how an unobservable control-plane path is distinguished from a nonexistent one. "Independent evidence path" is a principle, not an attestation protocol.

**Required resolution:**
1. Define a versioned coverage-manifest schema with explicit organization/account/region/tenant scope roots and parent-child inventory relationships.
2. Require independent authoritative root-of-scope evidence (for example, organization-level account enumeration) and reconciliation against every provider control-plane inventory source; enumerate excluded services and justify them.
3. Define graph node/edge schemas, immutable provider resource identity, lifecycle/tombstone semantics, evidence precedence, conflict handling and UNKNOWN state.
4. Define transitive capability composition for token exchange, delegation, impersonation, host/control-plane mutation and verifier/evidence mutation, including cycles and time-bounded grants.
5. Require an independently controlled completeness attestation over both scope roots and collected objects, plus omission, hidden-account, stale-snapshot and source-disagreement tests.

**Closure evidence:** executable schema, provider-specific root-of-scope enumeration, reconciliation report, graph algorithm and independently reproduced completeness result.

### DBID-R28 — High: Selector response and budget contract remains non-executable

**Affected section:** §3 DBID-R20.

The outcome table usefully aims to make match, no-match and denied-candidate responses indistinguishable. Yet it does not provide the exact public status code, body bytes, header allowlist, retry behavior or timing policy; it explicitly leaves these to future normative definition. The budget profile likewise names dimensions but sets no enforceable provider-specific values or admission semantics. "Bounded indexed plans" and query-cost observation do not prove a hard bound on database work.

The candidate reference is called non-bearer, but the proposal does not define the authenticated channel/context through which it is redeemed, whether the client ever receives it, how request binding is protected against substitution, how references are scoped to a single search operation, or how duplicate/concurrent requests map to one durable operation. The reference state machine is not connected to a defined search-authorization record and source-side audit transaction.

**Required resolution:**
1. Specify a canonical public outcome table with exact status, body schema/bytes, content type, cache policy, headers, retry semantics and correlation behavior for every outcome.
2. Define measurable provider profiles: concurrency, request/selector size, statement/lock timeout, server cancellation deadline, result cap, per-actor/destination budgets and overload behavior. Mark any non-hard bound as residual risk.
3. Define the authenticated redemption context and candidate reference cryptographic/random properties, request binding, storage uniqueness, expiry clock, one-time atomic transition, idempotency behavior and cross-endpoint rejection.
4. Tie search authorization, candidate issuance/redemption and audit evidence to one source-owned operation record.
5. Provide differential timing/resource tests with quantitative acceptance thresholds, including cache/lock/plan behavior and repeated selector probing.

**Closure evidence:** machine-readable response/budget profiles, source-side operation schema and quantitative anti-enumeration conformance tests.

### DBID-R29 — Critical: Source read and network release lack a complete linearization protocol

**Affected section:** §4 DBID-R21.

The epoch-row approach is directionally sound, but "same transaction or a formally equivalent transactional outbox protocol" leaves the central proof obligation open. The proposal does not define the exact PostgreSQL isolation level, snapshot creation point, lock mode, generation update transaction, serialization-failure handling or how every revocation domain is represented in one authoritative consistency domain. It acknowledges that a distributed protocol is needed when generations span services, but does not define one.

There is also a distinct TOCTOU gap at network release. Checking a generation before outbox claim and again at release does not by itself serialize the final authorization decision with the irreversible socket write. Revocation can race between the final check and the first byte. The text says release transitions serialize with revocation but does not identify the shared authority, atomic operation or precise release linearization point. A database transaction cannot atomically commit a remote network write.

**Required resolution:**
1. Specify one supported source database transaction profile, including isolation level, exact lock/conditional-update protocol, snapshot behavior, generation row/vector schema and serialization retry rules.
2. Define how all relevant revocation domains reach the source consistency authority; stale/unavailable domain state must fail closed.
3. State exactly when protected materialization is considered to have occurred and what audit/outbox record commits atomically with it.
4. Define the release state machine and a concrete fencing/lease protocol that serializes revocation against release-start, including worker crash, lease expiry, duplicate dispatch and stale process behavior.
5. Explicitly classify the unavoidable race after release-start; define whether revocation can cancel a queued write, terminate an active stream, or only mark OUTCOME_UNCERTAIN. Never promise atomicity between a database commit and remote delivery.
6. Provide deterministic interleaving tests proving both orderings and failure recovery, not just test scenarios.

**Closure evidence:** reviewed transaction-level design, exact database profile, state/authority sequence, executable concurrency model and failure-injection evidence. This finding remains Critical until the source-read and release ordering can be proven.

### DBID-R30 — High: Cluster-wide role identity lacks stable authentication binding

**Affected section:** §5 DBID-R22.

The proposal correctly states that PostgreSQL roles are cluster-wide and that role names alone are not authorization identity. But it assumes every LOGIN role has a "cluster-unique immutable principal ID" without defining where that ID lives, how PostgreSQL authentication maps a login/session to it, how role rename/recreation/restore affects it, or how the verifier proves that the authenticated server session corresponds to the registered tenant/workload/credential version. PostgreSQL's role catalog identity is not a substitute for an independently governed immutable principal registry.

The role model also does not fully define special role attributes, memberships, grantor/admin/inherit/set semantics and all-database effective CONNECT/TEMP checks in a machine-readable cross-version profile. Proxy/pooler attribution remains a condition rather than a supported-topology specification.

**Required resolution:**
1. Define the authoritative immutable principal registry and binding from workload identity/credential version to actual server-authenticated PostgreSQL role/session.
2. Specify role lifecycle for create, rename, drop/recreate, restore, failover and credential rotation; identity reuse must be rejected.
3. Enumerate all PostgreSQL role attributes and membership options supported by each server major version, including provider-managed and special roles.
4. Define effective CONNECT/TEMP evaluation for every database including templates and control databases, with PUBLIC and ownership effects.
5. Provide per-topology evidence for direct connections and every supported pooler/proxy, including session attribution and revocation tests.

**Closure evidence:** stable identity registry, authentication/session binding proof, versioned role semantics and complete cross-database negative tests.

### DBID-R31 — High: Wire profile is not yet a normative cryptographic specification

**Affected section:** §6 DBID-R23.

The proposal names a possible canonical JSON standard and describes domain separation, AAD, nonce uniqueness and ordered chunk construction. However, the key constructions are deliberately deferred: exact canonical profile/version, signature bytes, domain-prefix encoding, digest/signature algorithms, AAD byte serialization, nonce construction/uniqueness enforcement, chunk leaf encoding, Merkle parent encoding, odd-node rule and empty-artifact behavior are not fixed. An "ordered concatenation alternative" also creates more than one wire construction unless a profile registry unambiguously selects exactly one.

Without these details, two implementations can both claim conformance while signing, encrypting or hashing different bytes. A signed manifest also needs an explicit rule for which fields are covered and how the signature field is excluded without parser ambiguity.

**Required resolution:**
1. Publish a normative, versioned schema and canonicalization profile with exact byte-level signature input and domain-separation encoding.
2. Select exactly one digest/signature and encryption profile per protocol version through a reviewed algorithm registry; define downgrade and key-rotation behavior.
3. Define exact AAD bytes and recipient identity encoding, nonce generation/uniqueness enforcement and duplicate-key handling.
4. Select exactly one chunk construction per profile and specify leaf/internal-node formulas, integer endianness/length prefixes, odd-node and empty-artifact cases.
5. Supply positive and negative cross-language test vectors, including duplicate JSON keys, Unicode edge cases, recipient substitution, signature-field ambiguity, nonce reuse, truncation, reorder and downgrade.

**Closure evidence:** normative wire-profile document, test vectors independently implemented by two stacks and security review.

### DBID-R32 — High: ACL manifest and verifier remain placeholders

**Affected section:** §7 DBID-R24.

The YAML example is explicitly structural: `objects`, `default_privileges` and `exceptions` are empty arrays, and the text says the production schema "defines" exact enums and semantics in the future. It therefore does not yet resolve the finding that the ACL exception manifest and verifier are conceptual.

The effective-privilege description also lacks the exact object identity grammar, complete privilege enums by PostgreSQL major version, default-ACL creator/schema matching rules, grantor/grant-option semantics, PUBLIC handling, role closure algorithm and normalized catalog representation. The proposal mentions extensions, FDW and SECURITY DEFINER but does not define which catalog objects and dependency edges are mandatory or how the verifier determines effective cross-database/network capability. An "independent oracle" is named but not specified.

**Required resolution:**
1. Publish a complete machine-readable schema for cluster, databases, roles, attributes, membership edges, database ACLs, schemas, tables/views, sequences, routines, types/domains, extensions, FDW objects, default ACLs and exceptions.
2. Define exact privilege enums and object identity keys per supported PostgreSQL major/provider profile; no wildcard or implicit object pattern.
3. Define deterministic catalog normalization and effective privilege computation, including PUBLIC, ownership, grantor, ADMIN OPTION, INHERIT, SET ROLE, grant options and default privileges for every creator.
4. Define provider-managed privilege evidence and fail-closed treatment for unobservable capabilities.
5. Specify the independent verifier/oracle, signed output schema, provenance, completeness and mutation fixtures.

**Closure evidence:** validated schema, catalog adapter, privilege fixtures and independent verifier implementation with cross-database tests.

### DBID-R33 — Medium: Attestation freshness and independence are not operationally closed

**Affected section:** §8 DBID-R25.

The proposal separates duties and requires monotonic generations, which are appropriate principles. It does not identify the authoritative event source for each generation, how generation updates are atomic with the underlying mutation, how consumers learn that a PASS has become stale, or what maximum stale interval is permitted. It says relevant mutation invalidates PASS or triggers re-verification but leaves event-loss, delayed-event and freshness-authority outage behavior unspecified. An append-only chain also needs an explicit checkpoint/witness model to detect rollback by an administrator capable of restoring the evidence store.

**Required resolution:**
1. Map each attested domain to its authoritative mutation event/source and generation owner.
2. Define atomic generation advancement or a conservative invalidation mechanism for missed/late events.
3. Define signed freshness checkpoint format, independent witness/quorum or equivalent rollback-detection model, checkpoint retention and recovery.
4. Specify behavior on freshness-authority outage, event loss, clock uncertainty, stale evidence, signer compromise and restore.
5. Define maximum accepted staleness by risk domain and obtain explicit security/privacy/operations approval.

**Closure evidence:** event-to-generation mapping, checkpoint protocol, failure/recovery state machine and rollback/freshness tests.

### DBID-R34 — High: Lifecycle matrix leaves authority and recovery semantics unresolved

**Affected section:** §9 DBID-R26.

The matrix is useful but still collapses distinct transitions. "Receipt" is owned by the destination edge, while import validation and destination commit are destination-owned, but there is no exact authority for accepting a previously signed artifact after source revocation. The text correctly leaves this as a governance decision, yet that means the lifecycle cannot be considered closed. Strategy A/B also remains unresolved, and the proposal does not define the durable source artifact/operation record, destination import operation schema, exact unique-claim behavior under concurrent requests, or the authoritative state for an uncertain commit.

The idempotency tuple is stated, but the document does not specify canonical encoding, uniqueness constraints, source-pointer validation contract, pointer versioning, behavior when the same tuple is presented with a different content digest, or how a destination transaction proves the source provenance marker was committed with all imported records. "Atomic clone, provenance and operation marker" is a requirement, not yet a complete transaction contract.

**Required resolution:**
1. Define a complete source and destination state machine with owner, preconditions, durable evidence, allowed transitions, terminal states and retry authority for every transition.
2. Resolve Strategy A/B and post-revocation artifact acceptance with named clinical/privacy/legal/security approvers.
3. Specify idempotency-key canonicalization, uniqueness scope, same-key/different-digest conflict, pointer versioning and source-pointer validation.
4. Define destination transaction boundaries for unique claim, patient clone, related approved records, provenance and operation marker; define duplicate/concurrent behavior and uncertain commit reconciliation.
5. Define exact signed acknowledgement schema and verification, and ensure pointer sync cannot be inferred from commit ack.
6. Prove no false COMPLETED across ack loss, source revocation, pointer failure, stale worker, restore and replay.

**Closure evidence:** normative state/authority matrix, schema/constraint design, governance decision record and independent end-to-end failure-injection review.

## 4. Cross-finding dependencies

- **R27** blocks trust-boundary completeness and therefore any claim that DBID-R19 is closed.
- **R28** blocks safe selector/search exposure and candidate lifecycle closure.
- **R29** blocks source disclosure authorization and is a direct continuation of the Critical DBID-R21 concern.
- **R30** blocks DBID-R22 and reinforces CAN-01's need for a technically enforced source-owned boundary.
- **R31/R32** block a production-capable protocol profile and database authorization baseline.
- **R33** blocks reliance on signed PASS evidence for runtime authorization.
- **R34** blocks import/recovery completion and any claim that the federation lifecycle is fully specified.

These findings are not independent checkboxes: R27/R33 establish whether trust evidence is complete and current; R30/R32 establish the database boundary; R28/R29 establish source-side authorization and disclosure; R31 establishes artifact integrity; R34 governs destination acceptance and recovery.

## 5. Overall closure status

PR #54 is a substantial design improvement, but **DBID-R19–DBID-R26 remain open** pending resolution of DBID-R27–DBID-R34 and independent evidence. DBID-06 through DBID-08 remain open. CAN-01 and CAN-02 remain open. AUD-004 remains a release blocker.

D-01 through D-14 remain formally pending unless separately approved by designated authorities. D-11 project direction YES is not formal governance approval. Emergency federation remains disabled absent separate approval.

## 6. Review limitations and explicit non-authorization

This was a documentation-only adversarial review of PR #54's proposed text and its stated parent context. It did not inspect production infrastructure, live PostgreSQL catalogs, credentials, secrets, network policies, backups, audit stores or patient data. Findings describe design evidence gaps, not verified production vulnerabilities or exposure.

This review authorizes documentation and independent design review only. It does NOT authorize runtime changes, SQL, database/role/ACL/network changes, credential or secret operations, production access, patient-data access, partner onboarding, trust/key provisioning, federation activation, emergency access, pilot, deployment, release or merge. PR #54 must remain draft and unmerged pending further review.
