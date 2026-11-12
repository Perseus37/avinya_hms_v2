# Independent Review of AUD-004 Canonical Protocol Baseline (PR #40)

**Review status:** Independent design review — findings open  
**Reviewed baseline:** PR #40, commit `195559f99df4e3feba93e68c9c5ab6c83a975ec8`  
**Comparison evidence:** PR #19 runtime remediation patch; PR #21 route-surface inventory; PRs #23/#24 import recovery proposals; PRs #31–#39 consistency, adversarial and resolution proposals.  
**Disposition:** PR #40 is a useful consolidation, but this review does not recommend treating it as implementation-ready. No runtime authorization is granted. AUD-004 remains release-blocking.

## 1. Executive assessment

PR #40 correctly separates source clinician authorization/disclosure, response integrity/delivery, and destination import/recovery. It preserves pending governance decisions and explicitly prohibits treating node credentials, receipts, handles, demographic matches, or destination acknowledgements as substitutes for source authorization.

The independent review found six material gaps that should be closed in the canonical baseline or explicitly tracked as implementation-blocking decisions. The gaps are primarily about making stated security principles enforceable and testable across the actual local and remote runtime paths.

**No finding below is evidence that a new vulnerability was introduced by PR #40.** These are gaps in the completeness and precision of the proposed canonical design when compared with the existing route inventory and remediation/recovery proposals.

## 2. Findings

### CAN-01 — High: Local cross-branch source authorization is a logical rule, not yet an enforceable boundary

**Evidence**
- PR #40 Sections 3, 4.1, 7 and 16 require one source-owned authorization interface across remote, local, internal, background, admin, support, retry and recovery paths.
- PR #21 Section 24.3 records that the inspected import route directly opens the source tenant database after resolving a control-plane pointer. It also explicitly states the route inventory is not a repository-wide static-analysis certificate.
- PR #19 continues to perform source-side database reads from the import route; it does not implement the proposed clinician source-authorization boundary.

**Gap**
The baseline says direct ORM/session bypass is prohibited, but does not define the technical enforcement that makes this true when the destination process can obtain source-tenant database sessions. A shared Python interface alone is bypassable.

**Required resolution**
1. Define the source boundary as a separately enforced capability, not merely a coding convention.
2. Specify the permitted local adapter: source-owned service/API or another independently enforced boundary that evaluates the source policy before the source DB read.
3. Define database-role and credential separation so the destination import path cannot directly read source patient tables.
4. Inventory all direct source-session, ORM, SQL, background-job, admin, support and recovery call paths using repository-wide static analysis plus runtime tests.
5. Prove root and V1 route aliases use identical enforcement.

**Acceptance evidence**
- Negative tests prove a destination process/service identity cannot read source patient tables directly.
- Tests cover remote and local cross-branch paths, background/admin/support/recovery jobs, and both route aliases.
- A bypass scan and DB permission review are independently signed off.

### CAN-02 — High: Selector commitment and selector-index privacy are not specified precisely enough

**Evidence**
- PR #40 Sections 4.1 and 6 require a selector commitment bound into the search authorization and prefer bounded source-directed fan-out.
- PR #19 stores a plain SHA-256 selector hash for receipt binding and retains a global patient-pointer index with phone hashes and ABHA values.
- PR #33/PR #38 identify low-entropy selector correlation and global-index compromise as material threats.

**Gap**
The baseline prohibits raw/global deterministic selector hashes but does not explicitly distinguish an integrity digest from a privacy-preserving selector commitment. A plain SHA-256 hash of a phone number or other low-entropy identifier is enumerable offline. It also does not define canonicalization, domain separation, key ownership, rotation, or how the selector commitment is bound to the challenge without disclosing it to an untrusted coordinator.

**Required resolution**
1. Explicitly prohibit plain unsalted or globally deterministic hashes of phone, ABHA, MRN, DOB, or other low-entropy selectors in cross-tenant indexes, receipts, logs, and routing metadata.
2. Define source-specific keyed commitments where a commitment is necessary, including canonicalization/version, domain separation, key custody, rotation and compromise response.
3. Keep raw selector material within the source authorization boundary; define exactly what a coordinator can observe.
4. Specify that any existing global pointer index is legacy routing metadata, not a source authorization decision or evidence of patient existence that may be disclosed to a caller.
5. Require migration/removal or a separately approved threat-model exception before the global index can be relied on for the new protocol.

**Acceptance evidence**
- Offline dictionary/correlation tests against stored values.
- Key rotation and compromise tests.
- Data-flow evidence showing raw selectors and stable cross-tenant tokens do not reach telemetry or untrusted coordinators.

### CAN-03 — High: Source-directed fan-out has no complete routing-authority contract

**Evidence**
- PR #40 Section 6 selects bounded source-directed fan-out as the preferred topology.
- PR #21 documents the current global pointer lookup and branch metadata model.
- PR #33/PR #38 call out topology leakage, index compromise and selector correlation.

**Gap**
The baseline does not specify who determines the eligible source set, what trust relationship authorizes routing to each source, how the source list is bounded, or how routing failures and partial source outcomes are represented without exposing branch topology or patient-match information. Removing a global index without defining the replacement routing authority risks an incomplete or caller-influenced source set.

**Required resolution**
1. Define an authoritative, privacy-reviewed source registry for eligible participating sources and the trust relationship required to query each.
2. Make source eligibility and fan-out policy server-controlled, bounded and independent of caller-supplied branch lists.
3. Require each source to authorize its own selector query and return a source-authenticated outcome envelope.
4. Define how incomplete fan-out is represented, including timeout, unavailable, not authorized, no match and policy suppression, while preserving anti-enumeration behavior.
5. Define the operational service objective and maximum fan-out budget before selecting a topology exception.

**Acceptance evidence**
- Tests prove callers cannot select arbitrary source branches or expand fan-out.
- Tests prove one source's denial/failure cannot be converted into a global no-match result.
- Privacy tests verify branch topology and per-source match status are not disclosed.

### CAN-04 — High: Import idempotency identity and commit proof are too abstract in the canonical state contract

**Evidence**
- PR #40 Section 4.3 requires a durable unique operation claim, exact provenance marker, destination commit acknowledgement, fencing and pointer synchronization.
- PR #23 proposes an idempotency identity based on destination plus validated source pointer plus source branch plus protocol version.
- PR #24 adds fresh-receipt recovery, monotonic fencing, CAS, destination-side fencing and post-commit revocation handling.

**Gap**
The canonical baseline does not restate the exact immutable operation identity, required unique constraint, transaction boundary, or the evidence that makes a destination commit acknowledgement valid. It says these controls are required but leaves implementers to reconstruct the contract from several supporting proposals.

**Required resolution**
1. Record the exact server-derived idempotency tuple: destination tenant/branch, validated source pointer identity, source branch and protocol version (with any additional approved namespace/version fields stated explicitly).
2. State that the unique claim and state transition are durable and concurrency-safe in the destination database.
3. Require patient/allergy clone, immutable provenance and destination operation marker to commit atomically.
4. Require acknowledgement signing to re-read durable commit evidence and bind the exact operation, destination, provenance/payload digest and fencing generation.
5. Keep acknowledgement verification and pointer synchronization as distinct steps; COMPLETED is impossible before pointer synchronization is verified.

**Acceptance evidence**
- Multi-process PostgreSQL concurrency tests with independent sessions.
- Crash injection before/after every commit and acknowledgement boundary.
- Stale-worker tests proving old fencing generations cannot commit, sign, acknowledge or publish pointers.

### CAN-05 — High: Post-commit quarantine is named, but its clinical and operational semantics are undefined

**Evidence**
- PR #40 Sections 4.3, 9 and 11 require a restricted/quarantined state after source-policy revocation following destination commit.
- PR #24 proposes quarantine and governed retention, while explicitly leaving the retention owner and policy for governance.

**Gap**
The baseline does not define what “restricted/quarantined” means for patient lookup, clinical display, medication/allergy safety alerts, clinician access, edits, downstream orders, exports, backups, correction, retention, deletion, or emergency continuity. A generic quarantine label can lead to unsafe clinical use or unsafe removal of information already relied upon.

**Required resolution**
1. Assign a named clinical-safety owner and privacy/legal owner for quarantine policy.
2. Define access matrix by role and clinical workflow, including whether the clone is hidden, visibly marked restricted, read-only, or usable only under a documented continuity exception.
3. Define handling for downstream clinical actions already created from the clone.
4. Define correction, provenance preservation, legal hold, retention, deletion and backup expiry.
5. Prohibit automatic activation, silent deletion or operator override while the policy is unresolved.

**Acceptance evidence**
- Approved clinical/privacy decision record.
- Workflow tests for active encounter, medication/allergy review, downstream orders, correction, retention and restore.
- Dual-control operator runbook and audit evidence.

### CAN-06 — Medium: Anti-enumeration behavior needs a testable external response contract

**Evidence**
- PR #40 Sections 4.1 and 6 prohibit distinguishable no-match/denied outcomes and disclosure of candidate counts/topology.
- PR #21 Section 24.4 requires the same externally observable challenge-creation shape/status for matching and non-matching selectors.

**Gap**
The baseline does not define which externally observable fields must be equivalent, which outcomes may differ, acceptable timing variance, retry behavior, or how a caller can distinguish a fully evaluated no-match from an incomplete fan-out without learning which source matched or denied.

**Required resolution**
- Define an external response envelope and error taxonomy with privacy-preserving aggregation.
- Specify status, body shape, headers, timing/rate-limit behavior, and retry semantics for match, no-match, denied, unavailable, partial and uncertain outcomes.
- Ensure internal source outcome detail remains available only to authorized audit/reconciliation roles.

**Acceptance evidence**
- Differential response tests across match/no-match/denied/unavailable scenarios.
- Timing-distribution and rate-limit abuse tests.
- Tests verify incomplete fan-out is never represented as a complete no-match.

## 3. Cross-check against current runtime and supporting proposals

| Area | Observed state | Review disposition |
|---|---|---|
| Node vs clinician authority | PR #19 authenticates a federation node; PR #21 identifies no source-verified clinician assertion on discovery/import | AUD-004 remains open; no runtime closure |
| Discovery selector path | PR #19 receipt/index flow is node-authenticated; no pre-query clinician search grant | Must be replaced or protected by approved source authorization |
| Import source read | PR #19 import reads source tenant DB after pointer/receipt checks | Must move behind the enforceable source boundary in CAN-01 |
| Global selector index | PR #19 uses the global patient pointer index; PR #40 proposes source-directed fan-out | Treat current index as legacy/unapproved for the target protocol until CAN-02/CAN-03 are resolved |
| Concurrent import | PR #23/#24 propose durable idempotency and fencing | Canonical baseline should restate exact tuple and transaction proof |
| Pointer recovery | PR #19 has destination commit/pointer-sync split risk | COMPLETED must remain blocked until pointer sync is independently reconciled |
| Demographic/ABHA reuse | PR #19 still requires separate remediation against exact provenance | Never use demographics or ABHA equality as retry identity |
| Quarantine | PR #24 proposes state but governance owner/clinical semantics remain open | No activation/deletion policy can be inferred |

## 4. Required changes to PR #40 before design sign-off

1. Add enforceable local source-boundary architecture and database isolation requirements from CAN-01.
2. Add explicit selector commitment prohibition and keying requirements from CAN-02.
3. Add the source registry, eligible-source routing and partial-outcome contract from CAN-03.
4. Promote the exact PR #23/#24 idempotency tuple and destination transaction/ack proof into the canonical state contract.
5. Define quarantine ownership and clinical/privacy behavior or clearly mark it as a hard implementation stop with a named decision owner.
6. Add externally testable anti-enumeration response requirements from CAN-06.

## 5. Review conclusion and safety boundary

**Conclusion:** PR #40 is a useful consolidation and can remain open as a draft. It should not be treated as the final implementation baseline until CAN-01 through CAN-06 are resolved and independently reviewed.

This review is documentation-only. It does not authorize runtime code, migrations, configuration, database grants, keys, trust entries, partner onboarding, production patient-data access, pilot, emergency federation, merge, deployment or release.

D-01 through D-14 remain formally pending, including D-11 formal governance approval. PR #19 remains open and unmerged. AUD-004 remains a release blocker.
