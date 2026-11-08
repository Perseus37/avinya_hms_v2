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


## Deeper source-model review

The inspected feature-branch model definitions establish the following source-record contract.

### Supplier payment

`SupplierPayment` stores:

- vendor FK with `ON DELETE RESTRICT`;
- payment reference and payment method;
- payment date and positive amount in paise;
- notes and recording user FK with `ON DELETE RESTRICT`;
- unique vendor/payment-reference constraint and vendor/date index.

The bank reconciliation scanner reads the payment's vendor, reference, date and amount. The matching workflow also uses the payment ID and amount. The separate `SupplierPaymentAllocation` model links payments to vendor invoices and has unique payment/invoice pairs and positive amounts. Although the exception scanner does not query allocations, invoice-level allocation is required for a complete accounts-payable settlement workflow. It should not be dropped if the first release is expected to support invoice settlement rather than only bank-to-payment matching.

### Bank statement import

`BankStatementBatch` stores account reference, statement reference, covered period, opening/closing balances and importing user. It enforces unique account/statement reference and a valid date period.

`BankStatementLine` stores batch, account reference, bank transaction ID, transaction/value dates, direction, positive amount in paise, optional bank reference and description. It enforces unique account/transaction ID and indexes batch/date and bank reference. Amount is always positive; DEBIT/CREDIT is represented separately.

`SupplierPaymentBankMatch` stores a positive match amount, statement-line FK, supplier-payment FK, matching actor and timestamp, and optional reason. Both source FKs use RESTRICT. The endpoint locks both source rows and checks remaining amounts before inserting a match. This concurrency control and the invariant that cumulative matches cannot exceed either source amount must be preserved in a port; application-only checks without locking/transaction protection are insufficient.

### Scheduled payment request

`SupplierPaymentRequest` includes vendor, reference, method, scheduled date, amount, status, requester, independent reviewer, optional executed payment and timestamps. It also has a separate invoice-allocation table. The overdue exception scan reads only approved requests and their scheduled date/reference/amount/vendor.

This is not just a small extra source table: it represents an approval and execution workflow. If retained, its request-allocation table, review controls, payment execution linkage, permissions and tests must be included together. Do not add a bare request table solely to make the overdue-exception query compile.

## Recommended staged scope

For the first mainline reconciliation source foundation, separate capabilities into two deliverables:

**Foundation 1 — bank statement and supplier-payment reconciliation**
- supplier payment records and invoice allocations;
- bank statement batch and immutable statement lines;
- append-only bank/payment match records;
- import validation, duplicate protection, actor audit, row locking and over-allocation prevention;
- exception candidates for unmatched/partially matched bank debits, unclassified bank credits, unreconciled/partially reconciled payments and possible duplicate payment references.

**Foundation 2 — approved payment requests**
- payment request and request-allocation records;
- requester/reviewer separation and approval lifecycle;
- idempotent execution link to a supplier payment;
- overdue approved-request candidate;
- full permission and concurrency tests.

This split avoids implementing an incomplete approval workflow while keeping the bank reconciliation sources independently reviewable. If the business requires payment approval before any supplier payment can be recorded, Foundation 2 must precede enabling payment recording; a superuser-only direct payment endpoint is not a substitute for a governed approval workflow.

## Critical implementation invariants to port

1. Statement import must reject duplicate statement identity and duplicate bank transaction identity within an account.
2. Amounts remain positive integer paise; direction remains an explicit enum.
3. A bank statement line and supplier payment cannot be hard-deleted while referenced by a match.
4. Match creation must lock both source rows, validate debit-only matching, validate remaining amounts on both sides, and persist actor/time/reason atomically.
5. The same payment reference is unique per vendor in the payment ledger; duplicate-candidate analytics should still normalize case and whitespace and remain a manual investigation signal.
6. Imported credits are not supplier-payment matches. They remain classification work items, not automatically treated as income or receipts.
7. Imported statement balances and period boundaries must be checked against line-level arithmetic and overlapping/re-imported statement policy. The existing model constraints alone do not prove that the imported statement is complete or authentic.
8. Bank account references are sensitive financial metadata. Tenant scoping, permission checks, safe logging and export minimization are mandatory.
9. Invoice allocations must not exceed invoice outstanding balances or payment amount; enforce this under transaction/locking, not only in request validation.
10. The source workflow and reconciliation lifecycle must agree on stable reference types/IDs so investigations cannot silently point at a different object after imports or corrections.

## Mainline migration boundary

The existing procurement migration `3605df409a44` explicitly descends from baseline `6f591125aedc` and creates the core vendor, purchase-order, GRN and invoice tables. It is a mainline foundation, not a reason to import the feature branch's later migration chain. Before authoring a new migration, the current full mainline revision graph and all heads must be enumerated from the checked-out `main` ref; this inventory intentionally does not guess the current Alembic head from a migration filename.

