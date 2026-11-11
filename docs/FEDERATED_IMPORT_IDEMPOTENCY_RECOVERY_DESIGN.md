# Federated Import Idempotency and Recovery Design

Status: **PROPOSED — NOT APPROVED FOR IMPLEMENTATION OR RELEASE**

Parent baseline: PR #19 head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`.

This document specifies the follow-up required for safe retries and recovery in `import_federated_patient_locally`. It does not change runtime behavior.

## 1. Findings being addressed

1. **Concurrent duplicate imports:** the current destination lookup followed by insert is not an atomic idempotency operation. Two requests can both observe no existing clone and create duplicates for patients without ABHA. With ABHA, the losing request may receive an unhandled uniqueness failure.
2. **Post-commit pointer-sync failure:** destination patient/allergy rows commit before `sync_patient_pointer`. If pointer synchronization then fails, the API reports an error although the patient is committed. The existing-patient retry returns early and currently skips pointer reconciliation.
3. **Cross-database transaction boundary:** control-plane, source-tenant, and destination-tenant databases do not share one atomic transaction. A solution must model partial progress rather than imply distributed atomicity.

## 2. Required identity and idempotency key

The authoritative import identity must be derived server-side from the verified discovery receipt, not from caller-supplied demographics:

- destination tenant/branch identity resolved from authenticated request context;
- selected source pointer ID bound into the validated receipt;
- source branch identity resolved from the current control-plane pointer/registry;
- a protocol/version discriminator.

Use a stable unique key over these values, for example a SHA-256 digest of a canonical encoding. Do not use name, phone, DOB, email, or ABHA as the sole idempotency key. Those are patient attributes and can be shared, changed, absent, or duplicated across source systems.

The receipt remains a short-lived authorization artifact. It is not itself the durable import record and must not be treated as a unique transfer identity without a separate lifecycle record.

## 3. Durable import state

Proposed control-plane record (exact schema and retention policy require review):

- opaque idempotency key (unique primary key);
- destination branch code;
- source pointer ID and source branch snapshot;
- status;
- destination patient ID (nullable until confirmed);
- payload/source fingerprint (non-PHI digest);
- created/updated timestamps;
- last safe error category (no raw exception, token, or PHI);
- version/lease metadata if needed for worker recovery.

Suggested states:

`CLAIMED → SOURCE_VALIDATED → DESTINATION_COMMITTED → INDEX_SYNC_PENDING → COMPLETED`

Terminal or operator-managed states:

- `REJECTED`: authorization, policy, receipt, or source validation failed;
- `RECONCILIATION_REQUIRED`: outcome cannot safely be inferred;
- `FAILED_RETRYABLE`: a known transient failure occurred before destination commit.

State transitions must be conditional/atomic and monotonic. A stale worker must not overwrite a later state. Use a database uniqueness constraint and transaction-safe claim; an in-process mutex or cache lock is insufficient.

## 4. Transaction and retry contract

1. Authenticate the destination user and validate the discovery receipt, destination binding, pointer snapshot, source pointer, current source patient, and source privacy policy.
2. Derive the idempotency key exclusively from validated server-side identity.
3. Atomically claim or load the durable import record. A concurrent request with the same key must join/observe the existing operation, not independently create a clone.
4. Revalidate source data and policy before a new destination commit. Preserve source-side audit semantics; do not mark a transfer completed merely because a request was received.
5. Commit destination patient and permitted allergy rows together with a destination-side durable correlation marker or equivalent unique linkage. The marker must make a retry able to locate the exact clone without relying on mutable demographics.
6. Persist the destination patient ID and advance the control-plane operation state. Because these writes are across databases, explicitly handle the case where the destination commit succeeds but the control-plane status update fails: on retry, locate the destination clone by its unique correlation marker, verify its provenance, and reconcile the control-plane state.
7. Run pointer synchronization as a separately recoverable step. If it fails after destination commit, preserve `INDEX_SYNC_PENDING`; do not report the import as fully completed.
8. An exact retry after destination commit must reconcile the pointer under current privacy policy and then advance to `COMPLETED`. It must not create another patient.
9. If the destination commit outcome is uncertain, do not blindly retry the insert. Reconcile using the destination correlation marker first. If the marker cannot establish the outcome, leave the operation `RECONCILIATION_REQUIRED` and fail closed.
10. A different source pointer or destination branch produces a different idempotency identity. Do not merge two source records merely because their demographic attributes happen to match.

## 5. API outcome contract

The API must distinguish:

- new import fully completed;
- exact retry returning the already imported patient after successful reconciliation;
- destination patient committed but index synchronization pending;
- outcome uncertain and requiring reconciliation;
- rejected/expired/tampered receipt or source policy denial.

Never return a generic success for `INDEX_SYNC_PENDING`. Never return a generic failure that falsely implies no patient was committed. Use stable machine-readable error/status codes and avoid exposing source patient existence in pre-authorization paths.

## 6. Required adversarial and failure-injection tests

### Concurrency
- Two simultaneous imports with the same receipt and ABHA.
- Two simultaneous imports with the same receipt and no ABHA.
- Concurrent requests across separate application workers/processes.
- Exactly one destination clone and one durable import identity must result.
- The losing request must resolve to the same operation/result or a documented in-progress response, not an unhandled integrity error.

### Retry and crash windows
- Destination commit succeeds; HTTP response is lost; retry returns the same clone.
- Destination commit succeeds; control-plane state update fails; retry discovers the correlation marker and repairs state.
- Destination commit succeeds; pointer sync fails; retry repairs pointer without creating a clone.
- Process exits after claim, after source audit, after destination commit, and during pointer sync.
- Stale worker resumes after a newer worker advanced the state; stale transition is rejected.

### Identity and isolation
- Same source pointer imported repeatedly to same destination resolves to one clone.
- Same source pointer imported to a different destination creates a distinct destination operation.
- Different source pointers with identical names/phone/DOB are never silently merged by the idempotency mechanism.
- Source pointer deletion/reassignment or source branch deactivation is detected.
- Destination branch mismatch and receipt replay across branches are rejected.

### Privacy and auditing
- Patient opt-out or source policy change before retry prevents new disclosure/index publication.
- Pointer synchronization re-evaluates current destination sharing policy.
- Source audit, destination audit, and control-plane state do not claim a completed transfer before destination commit and reconciliation.
- Logs contain no raw receipt, patient identifiers, demographics, or unredacted exception text.

## 7. Migration and rollout requirements

- Add a forward-only control-plane migration for the durable import operation and uniqueness constraints.
- Add a destination-tenant provenance/idempotency marker with a safe migration strategy for existing rows.
- Do not infer historical source provenance from demographic similarity.
- Deploy schema before enabling code that requires it; keep the feature disabled until all tenant databases are migrated and migration-head checks pass.
- Define cleanup/retention for completed and abandoned operations without deleting audit evidence needed for reconciliation.
- Provide an operator reconciliation procedure for ambiguous outcomes.
- Test PostgreSQL concurrency with independent sessions/processes; SQLite-only tests are insufficient evidence for row locking/unique-conflict behavior.

## 8. Exit criteria

- All tests in Section 6 pass against PostgreSQL with independent concurrent sessions.
- Failure-injection demonstrates recovery at every cross-database commit boundary.
- Unique constraints, transaction isolation, and retry behavior are reviewed.
- Migration upgrade/downgrade policy is reviewed; production rollback must not discard import audit/provenance.
- No unresolved High/Critical data-integrity finding remains.
- Independent review and explicit project-owner approval are recorded.

This design does not resolve AUD-004. Signed clinician actor verification, source-side clinician authorization, and governance decisions remain separate release blockers. No merge, deployment, production data operation, or emergency federation authorization is implied.
