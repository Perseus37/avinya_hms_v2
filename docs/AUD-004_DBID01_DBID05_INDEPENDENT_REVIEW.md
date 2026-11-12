# AUD-004 DBID-01–DBID-05 Resolution Proposal — Independent Review

**Review target:** PR #46 — DBID-01–DBID-05 Resolution Proposal  
**Review basis:** The complete proposed document in PR #46, reviewed as a design artifact  
**Status:** INDEPENDENT DESIGN REVIEW — NOT IMPLEMENTATION APPROVAL  
**Release status:** AUD-004 remains a release blocker.

## 1. Executive conclusion

PR #46 materially improves the design by retaining the inspected database-per-tenant topology and specifying database ACLs, role separation, tenant-bound credentials, provisioning states, and source-audit commit barriers. It is substantially more testable than the prior ADR.

However, the proposal is **not yet sufficient to close DBID-01 through DBID-05**. It defines important desired outcomes but leaves several security-critical enforcement details open. This review identifies four High findings and two Medium findings. These are design gaps, not evidence that the deployed production environment is currently exposed. No production catalogs, effective grants, credentials, secret manager, network policy, workload identity, audit store, or patient data were inspected.

## 2. Findings

### DBID-R01 — High: Database creation exposure window lacks an enforceable default mechanism

**Evidence in PR #46:** Sections 2.3 and 5.2 require a new database to remain non-routable until ACL hardening and state READY. The proposal says the design must prove no untrusted runtime principal can connect during the interval if creation and hardening are not atomic.

**Gap:** This is a security invariant, but no default mechanism is selected. PostgreSQL `CREATE DATABASE` and subsequent ACL changes are separate operations. Until the database ACL is hardened, default PUBLIC privileges may permit CONNECT. A routing flag alone does not prevent an identity that already knows or can enumerate the database name from connecting over an available network path.

**Required resolution:**
1. Define the actual isolation mechanism for the creation interval: for example, create from a hardened template with verified ACL defaults plus an isolated provisioning network/cluster boundary, or keep the new database on a provisioning-only cluster/network until hardening is complete.
2. State explicitly which identities can reach the PostgreSQL listener during each provisioning state.
3. Prohibit runtime connection credentials/roles from having a network path to not-yet-READY databases, not merely from receiving a route.
4. Include a race test that attempts direct connection using every runtime role immediately after database creation and before ACL hardening.
5. Include a catalog reconciliation test proving the chosen template/default ACL policy survives PostgreSQL upgrades and database cloning.

**Closure evidence:** An architecture decision naming the enforceable mechanism, a state-by-state network/identity matrix, and an automated pre-hardening direct-connect denial test.

### DBID-R02 — High: Schema, function and default-privilege hardening is not normative

**Evidence in PR #46:** Sections 2.1, 3.3–3.4 and 5.4 require database ACLs, object-level source grants, privileged-object inventory, and post-migration verification.

**Gap:** The document does not define a baseline for schema ACLs, PUBLIC function execution, default privileges for newly created objects, or the PostgreSQL-version-specific behavior of the public schema. Database CONNECT revocation does not prevent overbroad access after a permitted connection. A migration can introduce a new table or function that inherits unsafe defaults even if the existing-object grant inventory passed.

**Required resolution:**
1. Define a versioned per-database schema ACL baseline, including the public schema and any application/source schemas.
2. Explicitly review/revoke PUBLIC schema CREATE/USAGE and PUBLIC function EXECUTE where not required; record deliberate exceptions.
3. Define ALTER DEFAULT PRIVILEGES for each object-creating role and schema, including tables, sequences, functions and types where relevant.
4. Require migrations to apply and verify the intended owner and grants for every new object before READY or migration completion.
5. Test newly created objects under every migration/object-owner identity, not only current catalog contents.
6. Include extension installation and SECURITY DEFINER function ownership/search_path/grant checks in the same gate.

**Closure evidence:** PostgreSQL-versioned schema/function/default-privilege policy, generated catalog assertions, and migration tests that fail on an unsafe newly created object.

### DBID-R03 — High: Pre-candidate-authorization selector query can over-read patient data

**Evidence in PR #46:** Section 6.2 allows selector resolution after durable DISCOVERY_SEARCH_AUTHORIZED. Section 6.3 says candidate authorization occurs after candidate resolution and before protected response serialization/release.

**Gap:** The document does not constrain what the selector-resolution query may retrieve into the source service before candidate-specific authorization. If the query loads full patient ORM entities, demographics, allergies or other clinical fields, sensitive data has already been read by the application process before candidate authorization, even if it is not serialized to the destination. The phrase “protected response” is too narrow to define the read boundary.

**Required resolution:**
1. Define selector resolution as a minimal, bounded lookup returning only an opaque candidate/resource reference and the minimum fields required to continue authorization.
2. Prohibit pre-candidate-authorization loading of patient demographics, clinical records, allergies, documents, or other protected payload fields.
3. Require candidate authorization to run against the opaque reference and source-owned policy before a separate narrowly scoped data query.
4. Define a query/projection allowlist and test it at the SQL/ORM boundary; prohibit eager relationship loading and implicit lazy loads before authorization.
5. Audit denied and ambiguous candidate outcomes without returning match-specific details to an unauthorized caller.

**Closure evidence:** Instrumented tests or query assertions proving that no patient/clinical payload query executes before candidate authorization, including eager/lazy ORM paths.

### DBID-R04 — High: Revocation freshness and authorization race checkpoints remain underspecified

**Evidence in PR #46:** Sections 4.1 and 4.5 require workload binding checks and fail-closed behavior for stale identity/secret state. Sections 6.1–6.3 require current source policy and per-candidate authorization.

**Gap:** The proposal does not specify when actor affiliation, clinician status, issuer/key trust, source policy, destination eligibility, or credential revocation must be rechecked across the time between authorization, selector resolution, candidate authorization, disclosure-intent commit and response release. A durable authorization event can remain historically valid while the authority that supported it is revoked before disclosure.

**Required resolution:**
1. Define explicit freshness checkpoints for issuer/key trust, clinician registration/status/affiliation, destination/partner status, purpose/scope policy, workload identity and database credential state.
2. Revalidate immediately before candidate authorization and again before disclosure intent is committed/released, using bounded and documented freshness guarantees.
3. Define behavior when revocation occurs during an in-flight operation, including the exact boundary after which disclosure cannot be stopped and the required uncertain/quarantine outcome.
4. Ensure a retry or recovery cannot inherit a stale authorization decision; fresh source reads require fresh authorization and audit.
5. Specify the authority and maximum propagation/freshness interval for each revocation domain. Values remain governance decisions, but the required fields and decision owners must be explicit.

**Closure evidence:** Revocation-race tests at each protocol boundary, including concurrent key/clinician/policy/destination revocation and a deterministic expected outcome matrix.

### DBID-R05 — Medium: Pool disposal is not equivalent to terminating checked-out sessions

**Evidence in PR #46:** Section 4.4 requires draining in-flight work, disposing old SQLAlchemy pools, and terminating old sessions where required.

**Gap:** SQLAlchemy engine/pool disposal does not by itself prove that checked-out connections or already authenticated PostgreSQL sessions have ended. The text leaves the termination condition and proof discretionary.

**Required resolution:**
- Specify how new checkout is blocked, checked-out connections are drained or invalidated, pool disposal is verified, and old PostgreSQL sessions are terminated when revocation requires it.
- Test a long-running checked-out connection during rotation and emergency revocation.
- Mark rotation/revocation complete only after the old credential cannot create new sessions and the required old sessions are gone.

**Closure evidence:** A concurrency test observing old sessions in pg_stat_activity (or service-equivalent evidence), followed by proof that rotation/revocation ends the required sessions.

### DBID-R06 — Medium: Audit event semantics need an explicit read-set and payload-digest contract

**Evidence in PR #46:** Sections 6.1–6.5 define event names, durable search/disclosure barriers, idempotency, and uncertain outcomes.

**Gap:** The event model does not fully define the exact binding between the candidate authorization decision, the data categories/fields actually read, the response artifact generated, and the disclosure delivered. An authorization event could be valid for one scope while an implementation accidentally reads or emits a broader projection. A pre-serialization disclosure-intent event also cannot by itself attest to the final response digest.

**Required resolution:**
1. Bind candidate authorization to a canonical resource reference, data-category/field projection, destination, purpose, action, policy version and operation ID.
2. Record the actual authorized read/projection and a canonical response/artifact digest in subsequent source events, without putting PHI into ordinary telemetry.
3. Require the delivery/acknowledgement chain to reference the same operation, projection and digest.
4. Define how an artifact generated but not delivered, or delivered with uncertain acknowledgement, is reconciled without treating intent as proof of disclosure.

**Closure evidence:** Tests that deliberately widen a query projection or alter a response after authorization and prove that the mismatch is rejected or explicitly recorded as an uncertain/security event.

## 3. Cross-finding assessment

| Finding | Assessment |
|---|---|
| DBID-01 | Improved, but DBID-R01 prevents closure |
| DBID-02 | Improved, but DBID-R02 prevents closure |
| DBID-03 | Improved, but DBID-R04 and DBID-R05 remain material dependencies |
| DBID-04 | State machine is useful; DBID-R01 and DBID-R02 prevent a complete enforcement claim |
| DBID-05 | Commit barriers are materially improved; DBID-R03, DBID-R04 and DBID-R06 prevent closure |

These findings should be resolved in the design before runtime implementation is considered. DBID-06 through DBID-08 remain open as previously recorded. CAN-01 is not closed by this review.

## 4. Required next design work

The next proposal should resolve DBID-R01 through DBID-R06 with explicit normative controls, sequence diagrams/state transitions, PostgreSQL catalog assertions, query/projection boundaries, revocation checkpoints and failure-injection tests. It should preserve the database-per-tenant model unless a separately reviewed ADR changes it.

Do not implement the proposed controls until the relevant governance and implementation gates are approved. A passing design review does not establish deployed configuration compliance.

## 5. Scope and limitations

This review is based on the PR #46 document and its stated architecture context. It is not a live PostgreSQL privilege audit, penetration test, secret-manager review, production configuration assessment, privacy/legal opinion, or clinical safety approval. No production system or patient data was accessed.

## 6. Explicit non-authorization

This review authorizes documentation and independent design review only. It does NOT authorize runtime code changes, SQL execution, database/role/ACL changes, credential or secret-manager operations, production access, patient-data access, partner onboarding, federation activation, emergency access, pilot, deployment, release, or merge.

PR #46 remains draft and unmerged. AUD-004 remains a release blocker. D-01–D-14 formal governance decisions remain pending; D-11 project direction YES is not formal governance approval.
