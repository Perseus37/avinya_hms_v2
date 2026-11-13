# Federated Import Idempotency and Recovery Design

Status: **PROPOSED — NOT APPROVED FOR IMPLEMENTATION OR RELEASE**

Parent baseline: PR #19 head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`.

This document specifies the follow-up required for safe retries and recovery in `import_federated_patient_locally`. It does not change runtime behavior.

## 1. Findings being addressed

1. **Concurrent duplicate imports:** the current destination lookup followed by insert is not an atomic idempotency operation. Two requests can both observe no existing clone and create duplicates for patients without ABHA. With ABHA, the losing request may receive an unhandled uniqueness failure.
2. **Post-commit pointer-sync failure:** destination patient/allergy rows commit before `sync_patient_pointer`. If pointer synchronization then fails, the API reports an error although the patient is committed. The existing-patient retry returns early and currently skips pointer reconciliation.
3. **Cross-database transaction boundary:** control-plane, source-tenant, and destination-tenant databases do not share one atomic transaction. A solution must model partial progress rather than imply distributed atomicity.

## 2. Required identity and idempotency key

The authoritative import identity must be derived server-side from the verified discovery receipt, not from caller-supplied demographics. The canonical identity tuple is:

- destination tenant UUID and immutable destination branch identity resolved from authenticated request context;
- selected source pointer immutable identity and pointer generation, bound into the validated receipt;
- source branch immutable identity resolved from the current control-plane pointer/registry;
- federation protocol version and identity-encoding version.

Encode the tuple with a versioned, unambiguous canonical format (for example, a fixed-field length-prefixed binary encoding with explicit UTF-8 normalization rules). Hash the encoded bytes with SHA-256 using a domain-separation prefix dedicated to federated patient imports. Publish test vectors for canonical encoding, normalization, and digest stability. Do not concatenate delimiter-separated strings without escaping/length rules.

Never include name, phone, DOB, email, ABHA, or other demographic/clinical fields in the idempotency identity. Those are attributes, not transfer identity.

The receipt remains a short-lived authorization artifact. It is not itself the durable import record. A valid receipt must be consumed into a durable operation claim before source disclosure/import work proceeds. Once that claim exists, receipt expiry must not erase or silently invalidate the operation; every retry must still revalidate the current source pointer, source branch status, destination authorization, actor authorization and source privacy policy before any new disclosure or pointer publication. Define explicitly which authorization facts are snapshotted at claim time and which are always revalidated.

## 3. Durable import state and mandatory fencing

The control-plane import operation record must include:

- versioned opaque idempotency key as a unique primary key;
- destination tenant and branch immutable identities;
- source pointer immutable identity and generation, plus source branch immutable identity;
- protocol and identity-encoding versions;
- status and monotonic operation generation/fencing token;
- lease owner, lease expiry and last renewal timestamp;
- destination correlation marker and destination patient ID (nullable until confirmed);
- non-PHI source/payload fingerprint;
- created/updated timestamps and a safe error category (never raw exception, token or PHI).

Suggested states:

`CLAIMED → SOURCE_VALIDATED → DESTINATION_COMMITTED → INDEX_SYNC_PENDING → COMPLETED`

Terminal or operator-managed states:

- `REJECTED`: authorization, policy, receipt, or source validation failed;
- `RECONCILIATION_REQUIRED`: outcome cannot safely be inferred;
- `FAILED_RETRYABLE`: a known transient failure occurred before destination commit.

**Fencing is mandatory, not optional.** Every claim/takeover increments a monotonically increasing generation. Every state transition must be a conditional update against the expected current state and generation. The destination-side commit must persist and validate the same generation/correlation identity. A worker whose lease expired or whose generation was superseded must be unable to commit or advance state, even if it resumes after a pause. Define lease duration, renewal interval, takeover rules, and behavior when a lease expires during a database transaction. A lease alone is not fencing.

Two durable uniqueness barriers are mandatory:

1. Control plane: unique idempotency key, claimed transactionally so concurrent requests join the same operation.
2. Destination tenant: unique correlation marker written in the same database transaction as patient/allergy creation, binding operation key, generation, source pointer identity/generation, source branch identity and destination operation identity.

The destination marker must not be a mutable demographic match. Before recovering an uncertain destination commit, verify marker uniqueness, operation identity, source provenance, destination tenant/branch and patient linkage. Never attach an unrelated pre-existing patient by matching demographics. If either uniqueness barrier exists without the other, recovery must follow an explicit reconciliation algorithm; it must not create a second clone or guess provenance.

## 4. Transaction and retry contract

1. Authenticate the destination user and validate the discovery receipt, destination binding, pointer snapshot, source pointer, current source patient and source privacy policy.
2. Derive the idempotency key exclusively from the canonical server-side identity tuple in Section 2.
3. Atomically claim or load the durable import record. A concurrent request with the same key must join/observe the existing operation, not independently create a clone.
4. Acquire/renew a fenced lease. Revalidate source data and policy before a new destination commit. Preserve source-side audit semantics; do not mark a transfer completed merely because a request was received.
5. Commit destination patient and permitted allergy rows together with the unique destination correlation marker, in one destination transaction. The marker must include sufficient provenance to identify the exact clone on retry.
6. Persist the destination patient ID and advance the control-plane operation state. Because these writes are across databases, explicitly handle destination commit success followed by control-plane status-update failure: on retry, locate the destination clone by its unique correlation marker, verify provenance and fencing generation, then reconcile the control-plane state.
7. Run pointer synchronization as a separately recoverable step. If it fails after destination commit, preserve `INDEX_SYNC_PENDING`; do not report the import as fully completed.
8. An exact retry after destination commit must reconcile the pointer under current source and destination privacy policy, then advance to `COMPLETED`. It must not create another patient.
9. If the destination commit outcome is uncertain, do not blindly retry the insert. Reconcile using the destination correlation marker first. If the marker cannot establish the outcome, leave the operation `RECONCILIATION_REQUIRED` and fail closed.
10. A different source pointer/generation or destination identity produces a different idempotency identity. Do not merge two source records merely because their demographic attributes happen to match.
11. If a stale worker attempts a destination commit or state transition after takeover, the database must reject it using the persisted fencing generation, not merely an in-process check.

## 5. API outcome and receipt lifecycle contract

The API must distinguish machine-readably:

- `COMPLETED`: new import fully committed and pointer synchronized;
- `ALREADY_COMPLETED`: exact retry resolved to the same verified clone;
- `INDEX_SYNC_PENDING`: destination patient committed, pointer synchronization remains pending;
- `IN_PROGRESS`: another valid fenced worker owns the operation; include opaque operation ID and safe retry guidance;
- `RECONCILIATION_REQUIRED`: outcome cannot safely be inferred;
- `REJECTED`: receipt, source authorization, destination authorization or policy rejected.

Specify exact HTTP status mapping, response schema, retry-after behavior, polling endpoint authorization, and operation-ID entropy. Never return generic success for `INDEX_SYNC_PENDING`. Never return a generic failure that falsely implies no patient was committed. Do not disclose source patient existence or operation state before destination authorization and receipt validation. Replaying an expired receipt may not start new disclosure; an already claimed operation can be resumed only after current authorization and policy revalidation.

## 6. Required adversarial and failure-injection tests

### Concurrency and fencing

- Two simultaneous imports with the same receipt and ABHA.
- Two simultaneous imports with the same receipt and no ABHA.
- Concurrent requests across independent application workers/processes and independent PostgreSQL sessions.
- Exactly one destination clone, one destination correlation marker and one durable import identity must result.
- The losing request must resolve to the same operation/result or a documented in-progress response, not an unhandled integrity error.
- Lease expiry, takeover and old-worker resumption; stale generation must fail both destination commit and state transition.
- Lock contention, unique-conflict retry, transaction abort and worker termination during lease renewal.

### Retry and crash windows

- Destination commit succeeds; HTTP response is lost; retry returns the same clone.
- Destination commit succeeds; control-plane state update fails; retry discovers the correlation marker and repairs state.
- Destination commit succeeds; pointer sync fails; retry repairs pointer without creating a clone.
- Process exits after claim, after source audit, after destination commit and during pointer sync.
- Destination marker exists but control-plane operation update is absent; and inverse partial-record cases are safely reconciled or quarantined.
- Process exits during every cross-database boundary; recovery never reports false completion.

### Identity and isolation

- Canonical identity test vectors prove stable, unambiguous, versioned encoding and domain separation.
- Same source pointer/generation imported repeatedly to same destination resolves to one clone.
- Same source pointer imported to a different destination creates a distinct destination operation.
- Different source pointers with identical names/phone/DOB are never silently merged by idempotency.
- Source pointer generation change, deletion/reassignment or source branch deactivation is detected.
- Destination branch mismatch and receipt replay across branches are rejected.
- Destination marker provenance cannot be reassigned to another patient or operation.

### Privacy and auditing

- Patient opt-out or source policy change before retry prevents new disclosure/index publication.
- Pointer synchronization re-evaluates current destination sharing policy.
- Source audit, destination audit and control-plane state do not claim completed transfer before destination commit and reconciliation.
- Logs contain no raw receipt, patient identifiers, demographics or unredacted exception text.

All concurrency/failure tests must run against PostgreSQL with independent sessions and separate application worker processes. SQLite, a process-local mutex, or mocked repository tests are not sufficient evidence for row-locking, unique-conflict, fencing or crash-recovery behavior.

## 7. Database contract and migration design (normative)

The following is a logical contract, not a claim about existing tables or a ready-to-run migration. Physical names, key types and FK targets must be reconciled with the actual control-plane and tenant model metadata before implementation.

### 7.1 Control-plane operation table

Add one durable operation row per canonical idempotency key. At minimum, the physical table must enforce:

- primary key or unique constraint on `idempotency_key`;
- non-null destination tenant/branch identity, source pointer identity/generation, source branch identity and protocol/encoding versions;
- non-null status and positive monotonic `fencing_generation`;
- lease owner/expiry fields with a constraint that lease owner and expiry are either both present or both absent;
- unique opaque `operation_id` for API polling, not derived from patient identifiers;
- destination correlation marker and destination patient ID nullable until the destination transaction is confirmed;
- non-PHI fingerprint only; never persist raw receipt bearer token or demographic values as an idempotency key.

Claim algorithm: begin a control-plane transaction; INSERT the canonical key with generation 1 and a fresh lease; on unique conflict, SELECT the existing row FOR UPDATE and return its current state. A takeover is permitted only when the stored lease is expired and the state is nonterminal; takeover increments `fencing_generation` in the same transaction and assigns a new lease owner/expiry. All state updates use compare-and-swap predicates containing operation ID, expected status and expected generation. A zero-row update means stale worker or invalid transition and must abort.

Do not use an application-side check-then-insert, Redis-only lock or in-process mutex as the uniqueness barrier. PostgreSQL unique constraints and row-level transactional coordination are authoritative.

### 7.2 Discovery receipt lifecycle

The current PR #19 receipt table is short-lived and contains a pointer ID, selector/snapshot hashes, summary hash and expiry. Do not extend its two-minute bearer lifetime to cover crash recovery. Instead, in the same control-plane transaction that creates or loads the operation, record a one-way receipt-consumption reference (token hash or dedicated receipt ID) and the operation ID, with a unique constraint preventing the same receipt from starting two different operations. The raw token is never stored.

The receipt must be valid at the initial claim. After a durable operation claim exists, retry/recovery uses the opaque operation ID plus destination authorization and revalidation of current source pointer generation, source branch activation, actor authorization and current source policy. It must not require the expired bearer token to be replayed. An expired, unconsumed receipt cannot create a new operation. Define receipt cleanup so it cannot delete the minimal consumption/audit linkage before the operation's retention period ends.

### 7.3 Destination-tenant correlation table

Add an additive table in each tenant database, separate from patient demographics. It must have:

- unique `operation_id` (or an equally strong globally unique operation key);
- unique canonical `idempotency_key` within the destination tenant;
- non-null source pointer identity/generation, source branch identity, destination branch identity, protocol version and fencing generation;
- non-null patient FK, with restrictive deletion semantics while the correlation/audit retention period applies;
- creation timestamp and immutable provenance fields.

Insert the patient, permitted allergies and correlation row in the same destination transaction. The unique constraint is the destination-side barrier: a retry cannot create a second clone for the same operation. The correlation row must not be updated to point to another patient. Corrections require a separately audited, authorized reconciliation procedure; normal import code must treat a mismatched existing marker as a hard integrity incident.

Do not add a global unique constraint to ABHA, phone, name or demographic combinations to simulate federation idempotency. Do not use a tenant-local patient MRN as a cross-tenant operation identity. Existing patients without a verified correlation marker are not assumed to be prior imports.

### 7.4 Cross-database transaction sequence

No distributed transaction is assumed. Implement the protocol as a recoverable saga with explicit commit points:

| Step | Database transaction | Durable evidence after commit | Recovery behavior |
|---|---|---|---|
| A. Claim | Control plane | Unique operation + lease/fencing generation + receipt-consumption link | Retry loads same operation; expired lease can be taken over with higher generation |
| B. Source authorization/audit | Source tenant | Source policy decision and requested/disclosure audit event | Revalidate current policy on retry; never infer destination commit from source audit |
| C. Clone | Destination tenant | Patient + permitted allergies + unique correlation row committed atomically | Find by correlation key and verify provenance; never demographic-match |
| D. Acknowledge | Control plane | Destination patient reference + `DESTINATION_COMMITTED` state | If missing, reconcile from verified destination marker |
| E. Publish pointer | Control plane/index plus destination policy context | Pointer update or explicit pending state | Retry pointer publication under current policy; retain `INDEX_SYNC_PENDING` on failure |
| F. Complete | Control plane | `COMPLETED` state and audit event | Only after destination marker and pointer outcome are verified |

Each step must be idempotent and generation-fenced. If a later worker takes over, an earlier worker must not be able to write the destination correlation marker or advance control-plane state. Since a control-plane lease cannot by itself fence a write in another database, the destination transaction must validate the current operation generation through a trusted, narrowly scoped fencing mechanism. The implementation design must specify how this check is made atomic with the destination insert (for example, a destination-local operation-fence row updated before clone commit); a check performed only in Python before the transaction is insufficient.

### 7.5 Index synchronization is not import completion

Pointer synchronization currently operates on the control-plane index and can return false when destination sharing policy denies publication. The implementation must distinguish policy-denied publication from transient index failure. Persist a machine-readable result such as `PUBLISHED`, `SUPPRESSED_BY_POLICY` or `RETRY_PENDING`; do not spin retrying a deliberate privacy suppression. A policy change before a retry must be re-evaluated. Define whether an import can be `COMPLETED` with a privacy-suppressed pointer (recommended: yes, but only with an explicit terminal suppression outcome and audit record), and ensure API responses do not imply discoverability when publication was suppressed.

## 8. Migration and rollout requirements

- Add a forward-only control-plane migration for the durable import operation, unique idempotency key and fencing/lease fields.
- Add a destination-tenant provenance/correlation marker and unique constraint with a safe migration strategy for existing rows.
- Do not infer historical source provenance from demographic similarity.
- Deploy schema before enabling code that requires it; keep the feature disabled until all tenant databases are migrated and migration-head checks pass.
- Define cleanup/retention for completed and abandoned operations without deleting audit evidence needed for reconciliation.
- Provide an operator reconciliation and quarantine procedure for ambiguous outcomes.
- Test PostgreSQL concurrency with independent sessions/processes; SQLite-only tests are insufficient.
- Provide a reviewed expand/migrate/verify/enable rollout sequence and a forward-recovery plan. Any downgrade must preserve operation, marker and audit evidence; production rollback must not delete provenance or make an uncertain operation repeatable.

## 9. Exit criteria

- All tests in Section 6 pass against PostgreSQL with independent concurrent sessions and separate worker processes.
- Failure injection demonstrates recovery at every cross-database commit boundary.
- Both uniqueness barriers and all fenced state transitions are proven under contention and stale-worker resumption.
- Canonical identity test vectors and destination provenance checks are reviewed.
- Migration and rollout plan is reviewed, including partially migrated tenant databases and safe forward recovery.
- API status mapping and authorization on operation polling are reviewed.
- No unresolved High/Critical data-integrity finding remains.
- Independent technical review and explicit project-owner approval are recorded.

This design does not resolve AUD-004. Signed clinician actor verification, source-side clinician authorization, source-owned database isolation and governance decisions remain separate release blockers. No merge, deployment, production data operation, migration execution or emergency federation authorization is implied.
