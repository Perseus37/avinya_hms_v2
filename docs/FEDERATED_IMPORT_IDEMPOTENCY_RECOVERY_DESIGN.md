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

## 10. Repository-grounded implementation dependency map (read-only audit)

This section records the existing repository structures inspected for implementation planning. It is not a migration specification approval and does not authorize runtime changes.

### 10.1 Existing model and migration boundaries

| Concern | Existing repository location | Observed structure | Implementation consequence |
|---|---|---|---|
| Control-plane ORM | `backend/control_plane/models.py` | `ControlBase`; `TenantRegistry`, `GlobalPatientPointer`, `FederatedDiscoveryReceipt` | Durable operation/receipt-consumption models belong to `ControlBase`, not tenant metadata |
| Tenant ORM | `backend/core/database.py` and domain model imports | `Base`; tenant `Patient` is in `backend/domains/patients/models.py` | Correlation/provenance rows belong to tenant `Base` and are independently installed in each tenant DB |
| Control-plane Alembic | `backend/control_plane/alembic/env.py` | `target_metadata = ControlBase.metadata` | Control-plane migration must be authored in this history |
| Tenant Alembic | `backend/alembic/env.py` | `target_metadata = Base.metadata`; imports tenant federation and patient models | Tenant marker migration must be authored in this separate history |
| Migration orchestration | `backend/scripts/migrate.py` | Control plane upgrade is separate; tenant rollout uses default canary then fleet | New feature stays disabled until both histories are verified at the required revisions |
| Tenant routing | `backend/core/database.py` | `TenantEngineRegistry.get_engine(db_name)`; `build_db_url` selects a PostgreSQL database name | Existing database-per-tenant routing remains the target; no schema-per-tenant work is implied |
| Patient identity | `backend/domains/patients/models.py::Patient` | Unique tenant-local MRN, nullable unique ABHA, no federation source pointer/operation field | Demographic unique fields cannot act as federation idempotency; new marker must link the exact imported patient |
| Source pointer | `backend/control_plane/models.py::GlobalPatientPointer` | Integer row ID, branch_code, source_mrn, phone hash and update timestamp; no explicit pointer generation | Pointer generation/version is a missing prerequisite; timestamp alone is not a safe generation token |
| Tenant identity | `backend/control_plane/models.py::TenantRegistry` | Integer primary key, unique branch_code, unique db_name; no immutable UUID field | Decide whether the immutable registry row ID is the canonical tenant identity or add a dedicated immutable UUID; do not silently assume branch_code is immutable |
| Discovery receipt | `backend/control_plane/models.py::FederatedDiscoveryReceipt` and migration `6c9f2a1d8b40` | Token-hash primary key; source pointer FK uses `ON DELETE CASCADE`; two-minute expiry is enforced by import handler | A durable operation must not depend on receipt retention or cascade-delete with its pointer; preserve a non-PHI pointer snapshot/tombstone and receipt-consumption audit link |
| Source transfer audit | `backend/domains/federation/models.py`; tenant migration chain includes `f9b7c3d1e205` and `a7c4e9d2b615` | Transfer log is tenant-local and made immutable by PostgreSQL trigger; requesting node attribution is stored as scalar snapshots | Keep source audit in the source tenant DB; do not add cross-database foreign keys; design a distinct operation/correlation audit record rather than mutating immutable transfer logs |

### 10.2 Migration rollout constraints discovered

The existing migration runner has two separate flows:

1. `upgrade_control_plane_database_url` uses `backend/control_plane/alembic`.
2. `upgrade_tenant_database_url` uses `backend/alembic`, and `migrate_default_canary` applies control-plane upgrade before the configured default tenant canary.
3. `migrate_remaining_fleet` selects active `TenantRegistry` rows with `deployment_mode == CLOUD`; it does not include ON_PREM tenants in that fleet query.
4. Tenant rollout is recorded through control-plane audit entries and validates the default canary revision before proceeding.

Therefore a tenant correlation-marker migration is not fleet-complete merely because the existing `--fleet` command succeeds. An explicit, separately controlled ON_PREM migration and verification path is required before the feature can be enabled for those branches. The implementation rollout must also define behavior for inactive tenants, newly provisioned tenants, regions that are temporarily unreachable, and partial fleet migration. No feature flag may enable imports against a tenant database whose marker migration is absent.

The existing receipt migration is the latest known control-plane federation migration in the inspected PR #19 branch, but this audit did not independently resolve the full Alembic revision graph or query any live database. Do not treat a repository file list as proof of live migration head.

### 10.3 Required implementation order and review gates

1. **Identity prerequisite:** decide immutable tenant identity and add pointer generation semantics; define how pointer updates increment generation and how deletion/reassignment is represented.
2. **Control-plane contract:** add durable operation and receipt-consumption models plus a control-plane migration; define retention and prevent pointer/receipt cascades from erasing active or completed operation evidence.
3. **Tenant contract:** add tenant-local immutable correlation/provenance model and unique constraints; define patient deletion behavior and how old clones without provenance are treated (never infer them by demographics).
4. **Fencing proof:** specify and prove the atomic destination-side fencing protocol against concurrent takeover. A Python pre-check of the control-plane generation is not sufficient; a stale worker must not be able to overwrite a newer destination fence.
5. **Transaction orchestration:** implement the recoverable saga only after the two persistence contracts and API state machine are independently reviewed.
6. **PostgreSQL evidence:** add independent-session/process race tests, commit-boundary crash injection, stale-worker tests and cross-database recovery tests.
7. **Rollout:** migrate control plane, canary tenant, cloud tenant fleet and ON_PREM tenants under explicit gates; verify every target's migration head and schema diff; only then enable the import path.

**Current blockers identified by this audit:** no pointer generation field; no dedicated immutable tenant UUID; receipt FK cascade semantics are unsuitable for durable operation retention; no tenant-local federation correlation model; and existing fleet migration excludes ON_PREM tenants. These are design prerequisites, not proof that a particular live database is missing a migration.

This audit was based on read-only source inspection of PR #19 branch `fix/audit-remediation-clean-main-2026-11-11`; no runtime tests, database queries, migration execution, production changes or patient-data access occurred.

## 11. Normative identity and pointer-generation contract — proposed

This section resolves the two identity prerequisites for implementation planning. It remains a proposal until independently reviewed and explicitly approved.

### 11.1 Immutable tenant identity

Use a dedicated, randomly generated UUID as the canonical federation tenant identity. Do not use branch_code, db_name, subdomain, hospital name, or a caller-supplied value as the immutable identity.

- Add a non-null unique tenant_uuid to TenantRegistry; generate it once during provisioning and backfill existing registry rows with cryptographically random UUIDs in a reviewed control-plane migration.
- The UUID is immutable after assignment. Enforce this in the persistence boundary (database trigger or equivalent database-enforced rule), not only through ORM conventions.
- Keep the existing integer TenantRegistry.id as the local relational primary key and preserve existing branch-code/database-name routing. The UUID supplements rather than replaces existing keys.
- A restore, tenant rename, branch-code change or database rename must preserve the UUID for the same tenant. A genuinely new tenant receives a new UUID. Cloning a control-plane database into a separate environment requires an explicit environment/tenant identity reconciliation procedure; it must not silently create two live installations claiming the same tenant identity.
- Include the UUID in canonical import identity and provenance records. Never expose it as an authorization credential; it is an identifier, not proof of caller identity.

### 11.2 Source-pointer identity and generation

A pointer is identified by the tuple (tenant_uuid, pointer_id). pointer_id remains the existing control-plane row identity; the UUID prevents accidental identity collision across independently restored or replicated control-plane installations.

- Add a non-null monotonically increasing generation (initial value 1) to GlobalPatientPointer.
- Increment generation transactionally on every semantic change to the pointer's source identity or routing meaning, including source tenant reassignment, source MRN change, patient-link replacement, or an explicit invalidation/reinstatement. Do not increment for unrelated metadata such as a display-only refresh.
- All writers must lock the pointer row (SELECT FOR UPDATE or an equivalent conditional update) and update its payload and generation in the same control-plane transaction. A conditional update must require the previously observed generation; zero affected rows means stale state and must be retried from a fresh authorized discovery, not silently overwritten.
- Never reset or reuse a generation. Deletion must leave a durable tombstone/invalidation record with the last generation and reason category; do not rely on deleting the pointer row to communicate revocation to in-flight operations.
- A discovery receipt binds the tenant UUID, pointer ID and exact generation. Import revalidates all three, plus current source policy and patient authorization, at consumption time.
- A generation mismatch invalidates the receipt and prevents a new import attempt from treating the old source pointer as current. If an import operation already has an uncertain destination commit, it enters reconciliation; it must not select a replacement source based on demographic similarity.

### 11.3 Canonical operation identity inputs

The versioned, domain-separated idempotency key must be derived from an unambiguous canonical encoding of: protocol_version, destination tenant_uuid, source tenant_uuid, source pointer_id, source pointer generation, and the immutable transfer-operation identity issued by the control plane.

Use length-prefixed or canonical structured encoding before cryptographic hashing; do not concatenate ambiguous strings. Do not include patient name, phone, date of birth, ABHA, MRN, branch display name, or other demographics in the idempotency key. Store the protocol/key version alongside the digest so future encoding changes do not reinterpret existing operations.

The source pointer generation is a snapshot for the operation, not a mutable pointer to be followed during retry. Reconciliation must verify the destination marker's exact source tenant UUID, pointer ID, generation, protocol version and operation digest before associating an existing patient with the operation.

### 11.4 Backfill, uniqueness and rollout safeguards

- Backfill tenant UUIDs without changing existing tenant IDs, branch codes, database names or tenant database topology. Verify one-to-one uniqueness before making the column non-null.
- Initialize existing pointer generations to 1; ensure all pointer mutation paths are updated before enabling generation-based receipt validation.
- Do not infer generations from updated_at; timestamps are not monotonic fencing tokens.
- Add database constraints for UUID uniqueness/non-nullability and pointer generation positivity. Add a database-enforced immutability guard for assigned tenant UUIDs.
- Inventory every pointer writer (federation discovery/import, patient registration/linking, privacy deletion/invalidation, administrative repair and migration jobs) and prove each writer increments generation when semantics change.
- Roll out the control-plane migration first, deploy compatible readers/writers, verify all pointer writers, then enable receipt generation binding. Feature enablement is per environment only after migration-head and writer-coverage checks pass.
- Existing active operations without generation-bound receipts must expire or be explicitly quarantined; do not silently upgrade their snapshots.

### 11.5 Decisions still requiring independent approval

The proposed UUID and generation contract does not decide the legal retention period for pointer tombstones, the authorization policy for administrative pointer repair, or the control-plane disaster-recovery procedure for UUID collision detection. Those require named owners and explicit decisions. The repository audit has not enumerated every pointer writer or inspected live database contents; those are implementation discovery tasks, not assumed complete.

No runtime implementation, migration, database query, deployment or production operation is authorized by this proposal. PostgreSQL database-per-tenant remains unchanged.
## 12. Pointer-writer inventory — source audit, 2026-11-13

Status: **PARTIAL REPOSITORY INVENTORY — NOT YET PROVEN EXHAUSTIVE**. This inventory is based on read-only inspection of PR #19 head `0d20e97ba5eb2f603fbadf677c2f01dc4db45a29`, including `backend/control_plane/models.py`, `backend/domains/federation/router.py`, `backend/domains/patients/router.py`, selected control-plane fleet/migration/provisioning routers, privacy runtime/retention modules, and federation/privacy tests. A complete all-file writer scan and independent review remain required.

### 12.1 Confirmed mutation paths

| Path | Current behavior | Required generation/tombstone treatment |
|---|---|---|
| `backend/domains/federation/router.py::sync_patient_pointer` — existing pointer update | Refreshes phone hash, ABHA, source MRN, critical-allergy flag and `last_clinical_update_at`; commits control-plane row. | Lock row and compare prior generation. Increment when source identity/routing meaning changes (especially MRN/source identity changes); do not increment for a pure timestamp or display/clinical-summary refresh unless the approved contract defines that as a semantic source version. Make identifier/payload update and generation update atomic. |
| `backend/domains/federation/router.py::sync_patient_pointer` — insert | Creates a new `GlobalPatientPointer`. | New pointer starts at generation 1; identity tuple must include immutable tenant UUID plus pointer ID. |
| `backend/domains/federation/router.py::sync_patient_pointer` — patient opt-out and `ISOLATED_SILO` branches | Deletes an existing pointer and commits. | Replace physical-delete-only invalidation with durable tombstone carrying pointer identity, last generation and reason category; revoke/invalidate outstanding receipts and make retry observe the tombstone. |
| `backend/domains/patients/router.py::deactivate_patient` (around lines 336–364) | Deactivates tenant patient, then directly deletes matching control-plane pointer. | Same tombstone/invalidation requirement. This direct writer currently bypasses `sync_patient_pointer`; route through one controlled invalidation service/transaction contract. |
| `backend/domains/patients/router.py::register_patient` (around lines 93–151) | Calls `sync_patient_pointer` after tenant patient commit; retries once on `IntegrityError`. | Initial pointer generation 1. Cross-database partial success must be represented/reconciled; retry must not reset generation or overwrite newer pointer state. |
| `backend/domains/patients/router.py::update_patient` (around lines 305–333) | Calls `sync_patient_pointer` after tenant patient commit. | Increment only when source identity/routing semantics change; phone/ABHA changes affect lookup identity and must invalidate old receipt snapshots. Ordinary non-identity edits need not increment under the proposed contract. |
| `backend/domains/patients/router.py::chart_patient_allergy` (around lines 367–426) | Calls `sync_patient_pointer` after allergy commit to update critical-allergy discoverability. | Treat as summary/policy metadata unless the approved receipt snapshot binds this field; avoid generation churn for non-identity summary changes. If current authorization/discoverability changes, explicitly invalidate affected receipts according to policy. |
| `backend/domains/federation/router.py::publish_local_patient_to_discovery_index` (around lines 270–320) | Explicit endpoint calls `sync_patient_pointer`. | Same insert/update/invalidation rules as the shared service; no separate mutation implementation should be introduced. |
| `backend/domains/federation/router.py::import_federated_patient_locally` (around lines 978–993) | After destination patient commit, calls `sync_patient_pointer` for the imported local patient. | New destination pointer generation 1 or update existing destination pointer under row lock. Import operation must record/reconcile this second-DB effect; failure after patient commit must remain recoverable. |

### 12.2 Read-only references and adjacent paths

- Federation discovery, receipt snapshot creation/validation, and fleet dashboard counts/search read `GlobalPatientPointer`; these are not pointer writers in the inspected code.
- The selected privacy runtime and retention modules did not expose a direct `GlobalPatientPointer` mutation in the inspected excerpts. Privacy opt-out deletion is currently implemented in `sync_patient_pointer`, not established as a complete privacy lifecycle writer inventory.
- The inspected control-plane provisioning/migration routers did not expose a direct pointer mutation. Control-plane migrations and data-repair scripts still require a repository-wide scan before claiming no such writers exist.
- Tests create/read pointers for fixtures and assertions; test fixture writes are not production mutation paths but must be updated to include generation/tombstone invariants when implemented.

### 12.3 Implementation consequences and blockers

1. Centralize pointer mutations behind one control-plane service with explicit `create`, `refresh`, `reassign`, and `invalidate` operations. Prevent ad hoc ORM deletes/updates from bypassing generation fencing.
2. `phone_hash` and `abha_number` changes alter the discovery candidate set. The approved contract must decide whether each is a generation-changing identity mutation; conservative safe default is to increment and invalidate old receipts whenever the searchable identity tuple changes.
3. `source_mrn` or tenant identity reassignment is always a semantic identity change and must increment generation under row lock; if identity changes require a new pointer row, retain a tombstone for the old identity and issue a new pointer identity rather than silently repurposing it.
4. `has_critical_allergies` and `last_clinical_update_at` are summary/freshness fields. Do not let routine refreshes churn generation unless the receipt authorization/snapshot contract explicitly binds them. Any policy-driven removal from discoverability must tombstone/invalidate.
5. Current receipt FK `ON DELETE CASCADE` means physical pointer deletion can erase receipt evidence. Tombstones and durable operation references must remove that destructive dependency before generation-bound operations are enabled.
6. The patient tenant DB commits before control-plane pointer synchronization in registration, update, allergy charting and import. These are cross-database partial-success boundaries; generation correctness alone does not repair them. Durable retry/reconciliation is still required.
7. Before implementation, perform a complete symbol/reference scan across all 334 Python files in the inspected PR #19 tree (including scripts, migrations, tests and less-obvious service modules), enumerate raw SQL/table-name writes as well as ORM references, and add a CI guard/test that rejects unreviewed pointer mutation sites.

### 12.4 Evidence limitation

This is a candidate writer inventory, not a claim of complete enumeration. The GitHub code-search endpoint returned no usable matches for the symbol during this pass, and the audit fetched a targeted subset of source files rather than all 334 Python files. No runtime tests, database queries, migrations, production access or patient-data access occurred. The inventory must be completed and independently reviewed before a generation migration or implementation is authorized. PostgreSQL database-per-tenant remains unchanged.
### 12.5 Additional correctness findings from deeper path inspection

The implementation of `sync_patient_pointer` and its patient-facing callers reveals additional stale-index cases that the initial writer list alone did not capture:

- **Privacy-policy denial can leave an existing pointer published.** `sync_patient_pointer` evaluates `federation.patient.publish_pointer` first and returns `False` immediately when denied. Patient opt-out and branch `ISOLATED_SILO` deletion checks occur later. Therefore a previously published pointer is not invalidated when the policy evaluator denies publication. The explicit publish endpoint returns 403, but that response does not remove the stale pointer. The future service must distinguish “do not create/update” from “must revoke existing publication” and perform revocation even when publication authorization is denied.
- **Patient opt-out ordering is unsafe for revocation.** `allow_network_sharing=False` is checked only after the data-use decision. Revocation/invalidation must be processed as a restrictive action that cannot be skipped by an earlier denial/exception path; it must not require permission to disclose data.
- **`EMERGENCY_ALLERGIES_ONLY` can retain a non-critical pointer.** When the branch policy is this mode and the patient has no critical allergy (and the current pointer is not marked critical), the function returns `True` without deleting or tombstoning an existing pointer. The policy transition must explicitly remove or suppress non-permitted discovery records.
- **Critical-allergy state is sticky.** The update uses `has_critical_allergies or pointer.has_critical_allergies`, so a prior `True` is never cleared by a later recomputation of `False`. This can leave a pointer discoverable as critical after the qualifying allergy is no longer active. Recompute from current active allergy state; define policy-driven visibility changes and receipt invalidation separately from source-identity generation.
- **Pointer refresh is not concurrency-fenced.** The current lookup uses `(source_mrn, branch_code)` and performs an ordinary select followed by ORM mutation/commit; it has no row lock, expected-generation predicate or stale-writer rejection. Concurrent writers can overwrite newer pointer state. Generation increment and pointer payload update must be one locked/conditional database operation.
- **Patient update API identity scope.** `PatientUpdate` exposes phone number, ABHA and sharing preference but not MRN. Thus MRN reassignment is not part of this inspected public update route; if MRN can change through other administrative/import/migration paths, those paths remain in the uncompleted all-file scan. Phone/ABHA changes are directly exposed and must be treated as searchable-identity mutations for receipt invalidation.
- **Cross-database ordering remains visible in lifecycle routes.** Registration, update, allergy charting and deactivation commit the tenant database before the control-plane pointer action. A control-plane failure can therefore leave patient state committed while the discovery index is stale. The import path has the same class of split commit. Durable reconciliation is required; simply adding a generation column will not close these windows.

These findings increase the required acceptance criteria: tests must cover privacy-policy denial after prior publication, patient opt-out under denied disclosure policy, transition into/out of `ISOLATED_SILO` and `EMERGENCY_ALLERGIES_ONLY`, critical-allergy removal, concurrent pointer refresh, and tenant-commit/control-plane-failure recovery. No behavior was changed by this audit.
