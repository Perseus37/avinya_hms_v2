# Phase 3S Mainline Integration Plan

**Status:** investigation / planning only  
**Target base:** `main`  
**Source implementation:** `feature/opd-workflow-v1`  
**Planning branch:** `integration/phase-3s-foundation-plan`

## Purpose

Integrate the accepted Phase 3S reconciliation-governance work without merging the heavily diverged `feature/opd-workflow-v1` branch or copying its Alembic revisions into `main` unchanged.

Phase 3S scope remains:

1. Severity-based, versioned SLA policies.
2. Escalation rules and management notification preferences.
3. Investigation closure-quality analytics.
4. Repeat-exception and recurring-root-cause analysis.
5. Finance Manager governance dashboard.
6. Monthly reconciliation governance reports.
7. Audit-export register and accountability.

This document records migration ancestry verified against the current branch trees and migration source files. It is not an approval to deploy or to change production data.

## Repository comparison

At the time of this investigation:

- `main`: 37 tenant Alembic revision files.
- `feature/opd-workflow-v1`: 78 tenant Alembic revision files.
- GitHub compare: feature branch is 1,016 commits ahead and 27 commits behind `main`.

The branch is not a safe merge unit. The Phase 3S migration chain is coupled to earlier procurement and supplier-finance work.

## Verified Phase 3S migration ancestry

The governance tail is linear:

```text
k6e9f1b3c210  reconciliation audit-export FK RESTRICT
└── j5d8c2a7f410  reconciliation governance
    └── h4c2e7a9d510  reconciliation SLA clock
        └── h3b7d9e2a610  reconciliation SLA policy governance
            └── g2a4d6e8f110  reconciliation evidence
                └── f4c8a2d7e610  reconciliation resolution quality
                    └── e4b8c2d7a610  reconciliation source presence
                        └── d7a4c2e9f610  reconciliation exception lifecycle
                            └── c6e2a9d4f710  supplier payment approval workflow
                                └── b4d7e2a9c610  supplier bank reconciliation
                                    └── a7c4e2d9f610  supplier adjustments and advances
                                        └── f1c8a4d7e920  supplier payment allocations
                                            └── e6b9c2d4a710  supplier lifecycle suspension
                                                └── d4a7c2e9f610  supplier compliance policy audit
                                                    └── c9f4a2d7e610  supplier compliance policies
                                                        └── b8e4c2d7a610  supplier compliance documents
                                                            └── d3f7a9c2e610  supplier contracts
                                                                └── a9c4e7d2f610  procurement budgets
                                                                    └── f2a9c6d1e840  procurement price variance controls
                                                                        └── c8f2a6d1e940  inventory base-unit valuation precision
                                                                            └── b6d3a9e1f420  procurement line-unit snapshots
                                                                                └── a4c7e2b91d60  procurement units and pack configurations
                                                                                    └── 3f8a2c6d1e90  purchase-order tax breakdown
                                                                                        └── e2c7a9d4f610  PO shipment tracking
                                                                                            └── d8a4c2f1b690  purchase-order amendments
                                                                                                └── c6d9a2e4f710  PO approval authorities
                                                                                                    └── b4e7c2a91d60  supplier quotation workflow
                                                                                                        └── 9c2f6a4d1b70  purchase requisitions
                                                                                                            └── 7a91c4e2b630  procurement GRN location and inspection
                                                                                                                └── 8b6d2f4a9c10  merge procurement and pharmacy heads
```

The merge revision `8b6d2f4a9c10` has **two parents**, not one:

- `d6a84c2f91b0` — present on `main`.
- `f3a8c1d9e620` — feature-branch pharmacy stock-control line.

The second parent has this ancestry:

```text
f3a8c1d9e620  controlled-vault physical counts
└── e7a4c9d2f610  pharmacy inventory count sessions
    └── d4e9a7b2c613  location-scoped controlled vaults
        └── c2d8f4a91b63  pharmacy inventory movement ledger
            └── b7c4d2e8f610  pharmacy location access and transfers
                └── a8c4e2f19b70  pharmacy stock locations
                    └── f9b7c3d1e205  immutable federation transfer logs
                        └── e1a3c7b5d902  (present on main)
```

This graph demonstrates why transplanting only `d7...` through `k6...` is unsafe: the lifecycle revision depends on supplier-payment approval, which descends through procurement and a two-parent procurement/pharmacy merge. The supplier-finance chain also contains dependencies on procurement units, requisitions, quotations, budgets, supplier contracts and compliance.

## Integration rules

1. **Do not merge the feature branch wholesale.** Its commit divergence and unrelated UI, control-plane, inventory, pharmacy, HR and clinical changes exceed the Phase 3S scope.
2. **Do not cherry-pick the Phase 3S Alembic files unchanged.** Their `down_revision` chain is not rooted at the current mainline migration head.
3. **Do not invent a migration merge revision to conceal missing schema.** A merge revision only joins graph heads; it does not create the missing tables or columns.
4. **Do not rewrite already-applied tenant migration history.** Preserve deployed revision identifiers and checksums.
5. **Build an explicit source-to-main dependency matrix** for each model, table, enum, index, constraint, service, permission, task, API schema and UI consumer used by reconciliation.
6. **Prefer a minimal, additive mainline foundation.** Reuse entities already present on `main`; add only the missing supplier/reconciliation concepts required for the agreed Phase 3S workflows. Use new revision IDs based on the actual mainline heads.
7. **Separate supplier-finance scope from reconciliation governance.** If supplier payment approvals or bank reconciliation are not already required by the current procurement workflow, do not silently import them merely because the feature branch migration ancestry includes them. Re-evaluate the reconciliation source model and document the decision.
8. **Keep the migration graph valid for tenant upgrades.** Confirm all Alembic heads, tenant migration-catalog registration, upgrade and downgrade behavior, and PostgreSQL 17 behavior before proposing a PR.
9. **Port backend before UI.** Add model/service/router/schema/permission and background-task changes in reviewable slices; port frontend API clients and panels only after API contracts stabilize.
10. **Keep Phase 3S read and write permissions distinct.** Dashboard visibility must not grant policy management or report-generation privileges.
11. **Preserve governance limitations.** Mailer acceptance is not delivery confirmation; monthly reports use the documented snapshot basis; root-cause buckets are descriptive rather than inferred; audit exports record accountability metadata, not exported file contents.
12. **No production deployment** without separate explicit approval.

## Next work sequence

### A. Mainline schema and code inventory

- Identify every current mainline Alembic head and the tables/enums already available for vendors, purchase orders, goods receipts, supplier invoices, payments, bank reconciliation and inventory.
- Compare current `main` procurement models/services/router with the feature-branch versions.
- Trace all Phase 3S model and service imports to their actual database dependencies.
- Identify permission seeds, tenant migration-catalog entries, worker registration, storage configuration and notification interfaces.

### B. Decide the minimum reconciliation source model

Document which source records can be reconciled using current mainline tables and which genuinely require new supplier-finance functionality. Do not import an entire supplier-payment workflow by default.

### C. Design additive migrations

Create a new migration sequence whose parent is the current mainline head (or explicitly merge all current heads first, if required). Migrations must create only the agreed minimum schema, with PostgreSQL constraints and SQLite test compatibility where applicable.

### D. Port and validate incrementally

1. Reconciliation persistence and lifecycle.
2. Evidence, resolution quality and reopen tracking.
3. SLA policies and pause-aware clocks.
4. Escalations and notification preferences.
5. Governance analytics and dashboard.
6. Monthly snapshots and audit-export register.
7. API contracts, permissions, background tasks and frontend panels.

For each slice, run focused tests and then the full required CI release gates at a deliberate checkpoint. Do not trigger a full workflow for every small commit.

### E. PR readiness gate

Do not open an implementation PR until the migration graph and dependency matrix are complete. The PR must include a clear explanation of any intentionally deferred supplier-finance capability, migration upgrade/downgrade evidence, tenant isolation tests, PostgreSQL 17 validation, permission tests and frontend build evidence.

## Current status

- PR #1 UI/federation work remains separate and draft; its latest full required CI run passed on commit `d735d96fd4ad685fd2bf4607769c6f9167dc119c`.
- Phase 3S remains implemented on `feature/opd-workflow-v1`, not integrated into `main`.
- This branch contains planning documentation only at this stage.
- No production deployment has occurred.
