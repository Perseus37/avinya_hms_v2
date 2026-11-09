# Bank Statement and Supplier Payment Reconciliation Foundation

## Scope

This slice adds tenant-local bank statement ingestion, immutable transaction lines, read access to the executed supplier payment ledger, and manually controlled allocations between bank debits and supplier payments.

It is the source-data foundation for later reconciliation exception detection. It does not yet implement automated matching, fraud detection, reconciliation cases, or Phase 3S governance dashboards.

## API

- `POST /api/procurement/bank-statements/import` — import one balanced statement envelope and its transaction lines.
- `GET /api/procurement/bank-statements` — list imported statements.
- `GET /api/procurement/bank-statements/{batch_id}/lines` — browse statement lines, optionally filtered by DEBIT/CREDIT.
- `GET /api/procurement/supplier-payments` — browse executed supplier payments and invoice allocations.
- `POST /api/procurement/bank-statement-lines/{line_id}/matches` — manually allocate a bank debit to a supplier payment.
- `GET /api/procurement/bank-statement-lines/{line_id}/matches` — inspect match history and remaining line amount.

All routes are tenant-scoped through the existing tenant database dependency. Import and matching require `finance:write`; reads require `finance:read`.

## Invariants

1. The caller supplies an opaque tenant-local `account_key`, not a raw bank account number. The optional account label must be masked/non-sensitive.
2. Statement identity is unique by account key and statement reference.
3. Transaction identity is unique by account key and bank transaction ID, including across imported batches.
4. Each transaction has a positive integer paise amount, explicit DEBIT/CREDIT direction, and transaction date inside the statement period.
5. The statement balance equation must hold: opening balance + credits - debits = closing balance. Opening and closing balances may be negative for overdraft accounts.
6. Statement batches, transaction lines, and payment-match records are append-only at the database layer on PostgreSQL and SQLite. Foreign keys use RESTRICT so referenced source evidence cannot be hard-deleted.
7. Only DEBIT lines can be matched to executed supplier payments. Credits remain classification items and are never recognized as income by this feature.
8. Match creation locks the statement line and payment in a stable order, calculates both remaining balances inside the transaction, and rejects over-allocation.
9. A line/payment pair can be linked only once. Partial allocations are supported; total matches cannot exceed either source amount.
10. Each match records actor, timestamp, amount, and a required reason. This is a manual accounting action, not an automated fraud or duplicate-payment conclusion.

## Explicit limitations

- This endpoint accepts normalized JSON rows; it is not a CSV/Excel/PDF bank-statement parser.
- No bank API credentials or raw account numbers are stored.
- It does not automatically match by amount, reference, vendor, or date.
- It does not classify credits, recognize income, or close reconciliation exceptions. The read-only candidate endpoint below surfaces source-data review prompts only.
- It does not yet provide a dedicated frontend workspace or export workflow.
- Candidate detection is a bounded read-only query, not a durable exception case lifecycle, SLA clock, escalation engine, or monthly governance report.
- Importing the same statement or transaction again returns a conflict; operators must correct the source/import process rather than mutate immutable evidence.

## Reconciliation candidate discovery

- `GET /api/procurement/reconciliation/candidates` returns bounded, read-only review candidates for unmatched/partially matched bank debits, unclassified credits, unreconciled/partially reconciled supplier payments, normalized duplicate payment-reference collisions, and overdue approved payment requests.
- Supports an explicit `as_of` date and a bounded result `limit`; response reports whether source/result caps truncated the candidate set.
- Duplicate-reference candidates are grouped per vendor after case-folding and whitespace removal. They are review prompts only; no duplicate payment or fraud conclusion is made.
- No candidate creates, assigns, closes, or changes a reconciliation case. Credits are not posted as income. All candidates require human accounting review.
- Bank account aliases must be non-numeric opaque identifiers. Account labels reject contiguous 8+ digit sequences as a basic accidental-disclosure guard; operators must still avoid uploading raw bank identifiers or unrelated statement data.
- Import is an operator-supplied normalized JSON workflow. Actor and import timestamp are recorded, but the API does not cryptographically authenticate bank origin. Imported data must not be described as bank-verified.

## Migration

`a7c4e9d2f610_bank_statement_reconciliation.py` follows `f2a9c7d1e520_supplier_payment_ledger.py` and adds three tenant tables:

- `procurement_bank_statement_batches`
- `procurement_bank_statement_lines`
- `procurement_supplier_payment_bank_matches`

The migration adds unique identities, amount/direction/period constraints, foreign keys, query indexes, and append-only triggers for PostgreSQL and SQLite. Sandbox scrubbing purges these records in foreign-key-safe order and restores the triggers.

## Verification gate

The first source-foundation commit passed the full release-gate workflow on 2026-11-08 (run #42466479589). The subsequent candidate-discovery and import-validation commits still require a fresh full workflow on the final head. The pull request remains draft pending that verification and independent review.


## Bounded candidate discovery continuation

Candidate discovery scans source tables in stable order in bounded windows of 1,000 rows. The response includes `next_cursor` when either the current derived-candidate window has more results or additional source windows remain. Pass that cursor back unchanged to continue. The cursor is an opaque position token, not an authorization token; tenant routing and `finance:read` remain enforced on every request. `limit` bounds the number of returned candidates per response. Duplicate-reference indicators are evaluated within each scanned supplier-payment window, so review should continue through all cursors.
