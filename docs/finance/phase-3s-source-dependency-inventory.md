# Phase 3S Source Dependency Inventory

**Status:** initial code/schema inventory  
**Compared refs:** `main` and `feature/opd-workflow-v1`  
**Planning branch:** `integration/phase-3s-foundation-plan`

## Mainline procurement capabilities already present

The current `main` version of `backend/domains/procurement/models.py` already defines:

- `VendorMaster` / `procurement_vendors`
- `PurchaseOrder` / `procurement_purchase_orders`
- `PurchaseOrderItem` / `procurement_po_items`
- `GoodsReceiptNote` / `procurement_grn`
- `GoodsReceiptItem` / `procurement_grn_items`
- `VendorInvoice` / `procurement_vendor_invoices`
- `VendorInvoiceItem` / `procurement_vendor_invoice_items`

The current mainline procurement model file is about 305 lines. The feature-branch version is about 1,441 lines and introduces many unrelated procurement, supplier-finance, pharmacy and reconciliation models. A wholesale replacement would be a major domain rewrite, not a focused Phase 3S port.

## What the feature-branch live exception scan actually reads

The feature implementation is in `backend/domains/procurement/router.py`, in `get_procurement_reconciliation_exceptions` (around line 2537 on the inspected branch).

It creates live investigation candidates from these sources:

| Candidate type | Source data read | Mainline availability |
|---|---|---|
| Unmatched / partially matched bank debit | `BankStatementLine` with direction DEBIT; `SupplierPaymentBankMatch` sums matched amounts | Not present |
| Unclassified bank credit | `BankStatementLine` with direction CREDIT | Not present |
| Unreconciled / partially reconciled supplier payment | `SupplierPayment` and its bank-match total | Not present |
| Possible duplicate supplier payment | `SupplierPayment`, vendor ID, normalized payment reference and amount | Payment table not present; `VendorMaster` is present |
| Overdue approved payment request | `SupplierPaymentRequest` with status APPROVED and scheduled date | Not present |

The scan uses `VendorMaster` to attach vendor names to supplier-payment exceptions. It does not need the full requisition, quotation, contract, compliance, budget, shipment or pharmacy controlled-vault workflows merely to perform these five candidate checks.

The feature scan explicitly describes these as investigation signals, not confirmed errors or fraud. Unmatched bank transactions may be timing differences, fees, transfers or payments outside the imported statement window.

## Source-table migration ownership

The relevant feature-branch migration files create these tables:

| Revision | Tables created | Why it matters |
|---|---|---|
| `b4d7e2a9c610_supplier_bank_reconciliation.py` | `procurement_bank_statement_batches`, `procurement_bank_statement_lines`, `procurement_supplier_payment_bank_matches` | Imported bank statement data and links from bank debits to recorded supplier payments |
| `f1c8a4d7e920_supplier_payment_allocations.py` | `procurement_supplier_payments`, `procurement_supplier_payment_allocations` | Recorded supplier outflows and invoice-level payment allocations |
| `c6e2a9d4f710_supplier_payment_approval_workflow.py` | `procurement_supplier_payment_requests`, `procurement_supplier_payment_request_allocations` | Scheduled/approved payment requests; the live scan uses the request parent to detect overdue approved requests |

The ancestry of these revisions is much larger than the tables needed by the scan. Their existing Alembic revisions must not be transplanted unchanged.

## Key architectural distinction

There are two different integration problems:

1. **Governance persistence:** investigation lifecycle, events, evidence, SLA policies, escalation policies, monthly snapshots and audit-export register.
2. **Source ingestion and candidate generation:** imported bank statements, recorded supplier payments, bank-match links and (optionally) approved payment requests.

Phase 3S governance can be built against a stable exception contract. But the current feature implementation's live candidate generator cannot be moved unchanged onto `main` until its missing source records exist or are replaced with a mainline-compatible source adapter.

## Recommended minimum-scope decision

Do not import the entire supplier-finance/procurement feature set by following migration ancestry. Instead, decide and document one of these implementation paths before writing migrations:

### Path A — preserve current reconciliation behavior

Create new additive mainline migrations (new revision IDs, parented to the actual mainline head(s)) for only the source records required to preserve the existing live candidate scan:

- supplier payments;
- bank statement batches and lines;
- supplier-payment/bank-line match records;
- approved supplier payment requests only if overdue-request detection is retained;
- required enums, indexes, checks, unique constraints and user/vendor foreign keys.

Port only the matching services, schemas, endpoints and tests needed to create/import/match these records. Do not import supplier adjustments, advances, supplier contracts/compliance, requisitions, quotations, budgets, PO shipment tracking or pharmacy controlled-vault workflows as implicit prerequisites.

Supplier payment allocations and payment-request allocations should be included only if the selected payment-entry and invoice-settlement flows require them; they are not read by the five candidate-generation loops listed above.

### Path B — defer supplier bank/payment reconciliation

Keep Phase 3S as a governance layer over an explicitly defined set of mainline-compatible exception sources. Defer unmatched-bank-debit, bank-credit, supplier-payment and overdue-payment-request candidate types until their source workflows are separately approved and implemented.

This is a deliberate scope reduction and must be reflected in API/UI copy and acceptance tests. Do not silently leave these candidate types in the UI as if they were operational.

## Next engineering checks

1. Inspect all call sites of `get_procurement_reconciliation_exceptions` and the persisted-exception refresh workflow.
2. Trace the helper functions that calculate bank-line and supplier-payment matched totals.
3. Inspect payment/import/match endpoints and their authorization requirements.
4. Compare the relevant feature migration DDL with mainline naming conventions and tenant migration runner expectations.
5. Select Path A or Path B before implementation. If Path A, re-author only the minimal source schema as new migrations; if Path B, remove/defer source-dependent candidate types and update acceptance criteria.
6. After the source contract is settled, port reconciliation lifecycle and Phase 3S governance in dependency order.

## Current status

This inventory is based on source/model/migration inspection only. No reconciliation source tables, backend code or tenant migrations have been added to `main`. The planning branch contains documentation only. No production deployment has occurred.
