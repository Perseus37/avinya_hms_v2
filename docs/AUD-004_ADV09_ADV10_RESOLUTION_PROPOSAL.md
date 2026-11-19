# AUD-004 ADV-09/ADV-10 Selector Index and Destination Acknowledgement Proposal

**Status:** PROPOSED DESIGN — NOT APPROVED FOR IMPLEMENTATION  
**Parent:** PR #37 (ADV-07/ADV-08 source boundary and scope proposal)  
**Scope:** Address ADV-09 cross-tenant selector correlation/index compromise and ADV-10 destination acknowledgement trust/stale-worker risks.  
**Constraint:** This proposal does not select cryptographic algorithms, authorize runtime changes, or close either finding.

## 1. Executive result

1. **ADV-09 — Selector index:** Deterministic selector lookup can reveal cross-tenant relationships or become an existence/correlation oracle even when values are keyed. Preferred default: avoid a central patient-selector index and use bounded source-directed routing. If an index is justified by measured scale/latency, it must be a routing-only, tightly isolated, keyed-token service that cannot disclose patient matches or authorize access.
2. **ADV-10 — Destination acknowledgement:** An acknowledgement must be attributable to the destination service that owns the durable import commit, and bind the exact operation, committed provenance, payload digest and fencing generation. It is generated only after commit. A stale worker, gateway, coordinator or caller cannot manufacture commit proof.

An index token or signed acknowledgement is not an access grant. An acknowledgement proves only a narrowly defined destination-side commit claim; it does not prove source authorization, clinical correctness, pointer synchronization or end-to-end completion.

## 2. ADV-09 — Cross-tenant selector correlation and index compromise

### 2.1 Threat model

Selectors such as ABHA, MRN, phone, date of birth and name may be low-entropy, stable or directly identifying. A plain deterministic hash is vulnerable to dictionary enumeration. A deterministic keyed token can still expose equality/correlation to parties with query or key access. A shared key increases compromise blast radius.

Threats include:
- Offline dictionary attacks against unkeyed selector hashes.
- Online enumeration through repeated index queries.
- Cross-tenant correlation of the same person across hospitals.
- A compromised coordinator enumerating candidate branches.
- Insider access to index rows, tokenization keys or query telemetry.
- Selector substitution, normalization mismatch and collision confusion.
- Stale pointer/index entries after policy changes or branch deactivation.
- Key rotation/backfill exposing old and new tokens simultaneously.
- Timing, count, error, size or source-status leakage.
- Raw selector leakage through logs, traces, metrics, backups and support exports.

### 2.2 Topology decision

| Pattern | Properties | Proposed disposition |
|---|---|---|
| Bounded source-directed fan-out | Sources normalize and resolve selectors after source search authorization; no central deterministic patient token index | **Preferred default**, unless measured performance proves otherwise |
| Protected keyed-token routing index | Maps narrowly scoped opaque tokens to opaque source route references; sources still authorize and resolve candidates | Conditional option after necessity, threat model, key separation and migration plan |
| Global plaintext/deterministic-hash index | Central searchable patient-derived values and branch pointers | Reject for production patient discovery |

Measure partner count, source availability, latency, operational cost and search budgets before accepting index complexity. Convenience or presumed performance is insufficient justification. If bounded fan-out meets the service objective, do not build a global selector index.

### 2.3 Requirements if a keyed routing index is retained

The index is a locator-only optimization. It must not return patient names, MRNs, demographics, candidate counts, branch names, source-specific match outcomes or authorization decisions to the destination. Only a trusted coordinator may receive opaque route hints. The destination must not have a general index-query API.

Token construction requirements:
- Use a keyed, domain-separated pseudonymous token; never a plain hash of a low-entropy selector.
- Separate keys by environment, selector namespace and, where justified, tenant or source trust domain. Do not use one global key for all services and tenants.
- Keep tokenization keys outside the index database. Restrict use to a narrowly scoped service identity and approved key custodian.
- Do not expose a general-purpose tokenization oracle. Accept only validated canonical selector types and bounded requests from approved routing components.
- Use distinct domains for selector type, normalization version, protocol version and environment.
- Normalize selectors using documented, versioned rules. Reject malformed or ambiguous input.
- Never encode raw selector fragments, tenant IDs or patient identifiers in token bytes.
- Record key ID and normalization version as metadata; never log raw selectors or key material.
- Collision handling must never merge patient identities.

Key derivation, MAC/KDF choice, key length, hardware custody and rotation schedules require formal security review. This proposal does not select an algorithm or provider.

### 2.4 Tenant and purpose separation

The design must decide whether tokens are source-tenant, destination/partner, purpose/action and environment scoped. The privacy default is to minimize cross-hospital equality visibility. Use scoped tokens and a trusted routing service rather than a universal token any participant can compare. If a common correlation domain is necessary, document why, its authorized service identity, access boundary, retention and breach blast radius. No destination-facing API should reveal token equality or match cardinality.

### 2.5 Query controls and anti-enumeration

- Authenticate and authorize the routing caller before tokenization or index query.
- Enforce distributed budgets by issuer, destination, actor, selector type, source set and global service; aggregate across aliases, nodes and worker instances.
- Apply source-side DISCOVERY_SEARCH authorization before any source patient-specific selector resolution. An index cannot bypass this.
- Use exact-match selector types initially; fuzzy/prefix/wildcard search requires separate approval.
- Bound query count, fan-out, concurrency, response size, retries and storage.
- Return only opaque route hints to the trusted coordinator; never return match count or branch identifiers to the destination.
- Normalize externally visible status/body/size and control timing differences under the approved anti-enumeration policy.
- Index failure must not trigger plaintext lookup, weaker hash lookup, direct database access or unbounded fan-out.
- Limiter, tokenization, audit, key-service and index consistency failures must fail closed or return an explicit unavailable outcome; no in-memory fallback.
- Separate restricted patient-linked audit from operational telemetry. Telemetry must not contain raw selectors or stable tokens enabling correlation.

### 2.6 Data minimization and lifecycle

If retained, the index stores only opaque token, tokenization/key/normalization version, opaque source route reference, source pointer reference only where strictly necessary, status/version and minimal timestamps/integrity metadata. It must not store names, phones, DOB, ABHA, MRN, clinical summaries or patient payloads. The mapping from opaque source references to patient records remains inside the source tenant.

Lifecycle requirements:
- Source-controlled pointer publication and revocation.
- Stale/deactivated branch and patient-policy handling.
- Source/index consistency reconciliation.
- Retention and deletion compatible with immutable audit requirements.
- Encrypted backups, restore testing and least-privilege identities.
- Tamper-evident administrative events and dual-control for key/config changes.

Index metadata is not proof of identity or permission. The source independently validates route hints and resolves selectors under its source-owned authorization boundary.

### 2.7 Rotation and migration

A rotation plan must specify new key custody approval; key ID and normalization activation; bounded dual-read/token window if needed; backfill that does not expose raw selectors; collision/duplicate detection without patient merging; atomic cutover criteria; rollback that cannot restore a revoked key; retirement/destruction evidence; and incident response for suspected key compromise. A compromised key must be revoked and affected tokens invalidated/rebuilt under an approved process. Rotation must not change patient identity or silently reassign pointers.

### 2.8 ADV-09 acceptance tests

- No plaintext selector or unkeyed deterministic selector hash in index rows, logs, traces, metrics, backups or support exports.
- Offline dictionary tests against captured index data.
- Online enumeration tests across low-entropy selectors, nodes, aliases, actors and destinations with aggregate rate limiting.
- Destination cannot query index directly or observe token equality, match counts, branch identity or per-source match outcomes.
- Tenant, purpose, selector-type, environment and protocol domain separation tests.
- Tokenization/index/key/audit outage does not fall back to plaintext/hash/direct DB/unbounded fan-out.
- Concurrent pointer publication, revocation and index query cannot turn stale hints into authorization.
- Key rotation/backfill, dual-read, rollback, retirement and compromise revocation are failure-injected.
- Token collisions/duplicate pointers yield safe conflict/reconciliation, never automatic patient merging.
- Source rejects stale, fabricated, wrong-destination or revoked route hints before candidate disclosure.
- If fan-out is selected, load-test bounded source work and prove no destination-visible topology or match-count leakage.

## 3. ADV-10 — Destination acknowledgement trust and commit proof

### 3.1 Security invariant

An acknowledgement is valid only if:
- Issued by a source-approved, destination-tenant/branch-bound acknowledgement identity.
- The issuer is authorized for the exact destination and protocol.
- Generated by the service owning the destination transaction, or a narrowly trusted commit-attestation component with verifiable access to committed transaction state.
- Patient clone, provenance marker and import operation are durably committed.
- Bound to exact operation, idempotency identity, source/destination, provenance digest, payload digest, protocol version and fencing generation.
- Signed only after commit and retrievable from durable state after restart.
- Verified by the source against current trust, key status, recipient binding, operation state and monotonic generation.

A gateway, coordinator, pre-commit API handler, stale queue worker, client or operator cannot assert commit merely because it received a request or observed a successful network response.

### 3.2 Trust and key ownership

The destination tenant owns acknowledgement identity and lifecycle. A destination trust registry (or equivalent approved partner trust control) binds destination tenant/branch, acknowledgement issuer/service identity, approved key IDs/status, allowed protocol/schema versions, activation/retirement/revocation times and dual-control approval evidence.

The source must not trust a key merely because it appears in an incoming acknowledgement. Enrollment, rotation and revocation are out-of-band governed operations. Key custody, algorithms, certificate model, signing service/HSM choice and recovery policy remain pending security approval. The acknowledgement identity should be distinct from ordinary node API authentication. Trust should be branch-scoped so compromise of one branch does not authorize all tenants.

### 3.3 Commit ownership and durable evidence

Preferred model:
1. Destination import service creates the durable operation and acquires the current fencing generation.
2. In one destination DB transaction it writes patient clone, permitted clinical rows, durable source provenance/correlation marker and a commit-outbox record (or equivalent acknowledgement intent).
3. The transaction commits.
4. A post-commit attestor reads committed operation/marker and verifies generation and digest against durable DB state.
5. It creates and persists a signed acknowledgement bound to that committed state.
6. Delivery to source/control plane is retried from durable outbox; duplicate delivery returns the same acknowledgement for the same operation/generation/digest.

If signing cannot occur inside the transaction, do not pretend database commit and external signing are atomic. Model COMMITTED_ACK_PENDING, ACK_SIGNED and ACK_DELIVERY_PENDING distinctly. After a crash, the attestor re-reads committed state and signs only if it still matches. It must never sign from stale in-memory assumptions.

### 3.4 Required acknowledgement claims

Illustrative fields, not a final wire format:
- Acknowledgement schema and protocol version.
- Destination tenant/branch and acknowledgement issuer/service identity.
- Source tenant/branch identity.
- Source operation/resource reference and destination import operation ID.
- Stable idempotency-key reference/digest, not a raw secret.
- Source response manifest/artifact digest and imported payload digest.
- Destination provenance-marker digest and source pointer identity reference.
- Protected destination patient correlation reference.
- Current fencing generation and durable operation version.
- Destination commit timestamp and trusted signing timestamp.
- Status claim limited to DESTINATION_COMMITTED, not COMPLETED.
- Unique acknowledgement ID/replay context, signing key ID and signature.

Do not include unnecessary PHI, patient name, MRN, phone, DOB, raw token/assertion, private data payload or DB connection/schema details.

### 3.5 Fencing and stale-worker defense

- Every import operation has a monotonically increasing fencing generation in durable destination state.
- Lease reclaim or authorized recovery increments the generation atomically.
- Every state transition and side effect uses compare-and-swap on operation ID, state, generation and expected version.
- Patient/provenance commit, acknowledgement intent, signing and delivery validate the current generation at their boundary.
- A stale worker at generation g cannot commit, sign, publish or acknowledge after generation g+1 is active.
- Attestor reads current generation from durable state immediately before signing and binds it into signed claims.
- Source stores highest accepted generation and operation state; lower generations are rejected. Same generation with a different digest/destination is a conflict.
- Same operation/generation/digest duplicate acknowledgement is idempotent. A newer generation supersedes only through the approved recovery state machine.
- A fencing token in a message is insufficient: destination DB and attestor must enforce it against durable state.

### 3.6 Source verification and outcome semantics

Source verifies signature against the currently trusted destination key; issuer/key status and destination binding; protocol/schema and canonical encoding; exact source operation and source/destination identities; action/purpose/import correlation; artifact/payload and provenance digests; fencing monotonicity; replay/freshness; and that the claimed status is no stronger than DESTINATION_COMMITTED.

The acknowledgement does not prove source clinician authorization, semantic/clinical correctness, pointer synchronization, current patient consent, completed import, or clinician review.

Keep distinct states:
- DESTINATION_COMMITTED — destination transaction and provenance marker durably committed.
- ACK_SIGNED — trusted destination attestation exists.
- ACK_DELIVERED — source received acknowledgement bytes.
- ACK_VERIFIED — source verified trust and binding.
- INDEX_SYNC_PENDING — pointer/index synchronization not reconciled.
- COMPLETED — all approved completion steps succeeded.

Do not collapse these into one success boolean. Lost delivery is an uncertain communication outcome, not proof the destination transaction failed.

### 3.7 Key rotation and compromise

Planned rotation uses a bounded approved overlap. New acknowledgements use the active key; retiring keys are accepted only within the approved window. Emergency compromise revocation blocks new acknowledgements under the compromised key and explicitly governs already signed but undelivered claims. Source checks current trust; stale cached trust is not accepted beyond approved freshness. Issuer/service compromise may revoke all branch-scoped authority under that issuer. Pending claims may require quarantine and re-attestation from durable destination state under a new key. Re-attestation preserves original operation, commit time, provenance and fencing history; it cannot fabricate a commit or erase the compromised-key event.

### 3.8 Failure and recovery semantics

| Failure point | Durable evidence | Safe outcome |
|---|---|---|
| Before destination commit | No committed provenance marker | No commit acknowledgement |
| Commit succeeds; process crashes before signing | Patient/provenance/outbox committed | COMMITTED_ACK_PENDING; restart attestor re-reads durable state |
| Signer unavailable after commit | Commit marker and pending outbox | Remain pending; do not report complete |
| Signed; delivery fails | Durable signed acknowledgement | ACK_DELIVERY_PENDING; resend exact same acknowledgement |
| Source receives bytes; verification unavailable | Received but unverified bytes | ACK_RECEIVED_UNVERIFIED; no completion |
| Source receives old fencing generation | Higher generation exists | Reject stale acknowledgement |
| Same generation, different digest | Conflicting commit claim | Reject and reconcile/security review |
| Stale worker resumes after lease expiry | New generation exists | CAS/fencing blocks side effects |
| Destination commit outcome uncertain | Marker cannot prove commit | Reconcile before retry; no blind insert or acknowledgement |
| Source policy revoked after destination commit | Durable commit, changed authorization | Restricted/quarantine per PR #24; no pointer publication or automatic deletion |
| Pointer sync fails after verified commit | Commit verified, index not current | INDEX_SYNC_PENDING; repair under current policy |
| Acknowledgement key revoked | Claim trust uncertain | Quarantine pending claims per approved policy |

Operator reconciliation is least-privilege and dual-controlled. Operators may inspect evidence and advance permitted states; they cannot synthesize signatures, source authorization, provenance markers or successful commits.

## 4. Cross-lifecycle binding

The following must agree across source authorization, response manifest, durable import operation, destination provenance and acknowledgement: protocol/schema versions; source/destination identities; exact action/purpose; source resource/pointer reference; approved data-category/scope tuple; operation/idempotency identity; source artifact/payload digest; destination provenance digest; fencing generation and operation version.

Any mismatch is a conflict, not a reason to guess or auto-correct. Purpose/action changes require fresh source authorization. A different source pointer is a different import identity. A valid destination acknowledgement cannot repair missing source authorization or invalid provenance.

Reconcile with PR #35 Strategy A/B: Strategy A acknowledgement binds exact immutable artifact digest; Strategy B's fresh source read is separately audited and binds its new digest. Preserve PR #24 post-commit quarantine and PR #23 durable provenance requirements.

## 5. Required acceptance tests

### 5.1 Index and selector privacy
- Prove no plaintext selector or unkeyed deterministic hash in index or telemetry/backups.
- Exercise low-entropy offline and online dictionary attacks.
- Verify tenant, purpose, selector-type, environment and protocol separation.
- Verify index API is limited to trusted coordinator; destination cannot query equality or match counts.
- Verify no candidate metadata before source search and candidate authorization.
- Verify budgets aggregate across nodes, actors, aliases, destinations and workers.
- Verify index/key/tokenization outage fails closed with no weaker fallback.
- Verify key rotation, backfill, rollback, compromise and pointer revocation under concurrency.
- Verify stale/malicious route hints cannot cause disclosure or cross-tenant lookup.
- If no index is selected, load-test bounded source-directed fan-out and prove topology/match privacy.

### 5.2 Acknowledgement authenticity and commit proof
- Acknowledge-before-commit, forged gateway acknowledgement, caller-supplied key ID, unknown issuer, wrong branch/source/destination/protocol/operation/action/purpose/digest/provenance/generation are rejected.
- Acknowledgement is created only from committed provenance and durable operation state.
- Crash after commit before signing; restart attestor and verify it signs only current durable state.
- Crash after signing before delivery; resend byte-identical acknowledgement.
- Duplicate delivery is idempotent; same generation with different digest is rejected.
- Revoke/rotate key while acknowledgement is pending/in transit; verify quarantine/re-attestation.
- Stale worker attempts commit, sign, deliver and pointer publication after generation increments; every stale side effect is blocked.
- Concurrent lease reclaim, commit, signing and source verification use independent PostgreSQL sessions/processes.
- Source stores highest verified generation and rejects lower-generation replay.
- Acknowledgement cannot claim pointer sync or overall completion.
- Acknowledgement never substitutes for source clinician authorization or source audit.

### 5.3 Recovery and integration
- Failure-inject source audit, source response commit, network delivery, destination claim/commit, outbox, signing, delivery, source verification and pointer sync.
- Uncertain outcomes remain uncertain until durable evidence resolves them.
- No blind duplicate insert after ambiguous destination commit.
- Exact retry resolves the same source pointer and destination operation, not demographic lookalikes.
- Post-commit source-policy revocation enters restricted/quarantine.
- Index publication requires current policy and approved completion conditions.
- Audit/telemetry contain no raw selector, PHI, assertion, handle, signing secret or unredacted exception.

Concurrency, fencing, unique-claim and commit-order tests require PostgreSQL with independent sessions/processes. SQLite-only or single-process tests are insufficient.

## 6. Governance decisions required

| Decision | Proposed direction | Accountable approval | Status |
|---|---|---|---|
| Need for global selector index | Prefer no index unless measured scale/latency proves need | Product + platform + security + privacy/legal | Pending |
| Routing topology | Bounded source-directed fan-out default | Security architecture + platform | Pending |
| Tokenization/key separation | Keyed, domain-separated scoped pseudonyms; cryptographic profile separately approved | Security + key custodian | Pending |
| Tokenization service access | Trusted coordinator only; no destination token oracle | Security + platform | Pending |
| Selector normalization/versioning | Strict, versioned source-controlled canonicalization | Clinical governance + security | Pending |
| Index retention/pointer lifecycle | Minimum metadata, source-owned revocation/reconciliation | Privacy/legal + data owner | Pending |
| Index key rotation/compromise | Bounded migration, invalidation and re-tokenization | Security + key custodian | Pending |
| Destination acknowledgement issuer | Destination-branch-scoped trusted service identity | Security + destination owner | Pending |
| Acknowledgement key trust/custody | Out-of-band dual-control registry and approved custody | Security + key custodian + partner governance | Pending |
| Commit-attestation ownership | Transaction-owning service plus durable post-commit attestor/outbox | Platform + destination data owner | Pending |
| Acknowledgement claims/schema | Exact operation, provenance/payload digest, fencing; status only DESTINATION_COMMITTED | Security + platform + audit owner | Pending |
| Fencing semantics | Monotonic durable generation, CAS at every side-effect boundary | Platform + security | Pending |
| Signer rotation/compromise | Pending-claim quarantine and re-attestation process | Security + partner governance | Pending |
| Pointer-sync completion | Separate from destination commit acknowledgement | Product + platform + data owner | Pending |
| Audit/retention | Reconcile with D-12 and prior proposals | Audit owner + privacy/legal + security | Pending |

Record approvals in the canonical D-01–D-14 register with approver name, organization, role, date, governance reference, evidence, affected stages, residual risk, compensating controls, expiry and disable conditions. D-11 project direction remains YES for local cross-branch imports; formal governance approval remains pending.

## 7. Implementation gates

Do not implement ADV-09/ADV-10 until:
1. A measured decision selects source-directed fan-out or protected index; default is no global selector index.
2. If index retained, threat model, key separation, token domains, normalization, budgets, retention, rotation, migration, rollback and incident process are approved.
3. Destination acknowledgement trust enrollment, branch-scoped identity, key custody, rotation and revocation are approved.
4. Destination transaction ownership, provenance marker, durable outbox/attestor and post-commit signing boundary are demonstrated.
5. Fencing/CAS covers commit, sign, delivery, source verification and pointer publication.
6. Acknowledgement schema/status semantics reconcile with source manifest, import operation, PR #23/#24 recovery and PR #35 Strategy A/B.
7. PostgreSQL concurrency, crash injection, stale-worker, key-rotation and forgery tests are accepted.
8. Audit, privacy/legal, clinical governance and security approve residual risk and formal D-01–D-14 decisions.
9. Explicit implementation authorization is recorded.

## 8. Relationship to prior proposals

- PR #32 treats the index as routing aid only and separates source authorization, discovery integrity and destination recovery.
- PR #33 identifies ADV-09 and ADV-10 as high-risk unresolved findings.
- PR #34 establishes source-controlled clinician identity and bounded search authorization; an index cannot bypass either.
- PR #35 defines challenge/audit/disclosure boundaries and Strategy A/B response retry choices.
- PR #36 defines revocation freshness and handle/manifest binding; index tokens and acknowledgement keys inherit those revocation requirements.
- PR #37 requires one source-owned boundary and canonical action/purpose/scope; route hints and acknowledgements must preserve that tuple.
- PRs #23/#24 require durable import identity, destination provenance, fencing, fresh source authorization for new reads and quarantine after post-commit policy revocation.
- PR #19 runtime behavior does not currently prove these guarantees. Design text is not runtime enforcement evidence.

## 9. Disposition

This document proposes controls for ADV-09 and ADV-10; it does not close either finding. Closure requires an approved routing/index decision, independently reviewed tokenization/key controls if an index is retained, destination acknowledgement trust, durable post-commit attestation, enforced fencing, PostgreSQL concurrency/failure-injection evidence and verified runtime behavior.

**AUD-004 remains release-blocking.** This document authorizes no runtime code, migrations, configuration, database-role changes, cryptographic/key changes, trust entries, partner onboarding, pilot, production patient-data access, merge, deployment, release or emergency federation.
