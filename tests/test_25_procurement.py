import json
import pytest
from datetime import datetime, timedelta, timezone

def test_purchase_return_endpoint_reaches_service_validation(client, superuser_headers):
    response = client.post(
        "/v1/api/procurement/returns",
        headers=superuser_headers,
        json={
            "grn_id": 9999,
            "vendor_id": 9999,
            "items": [
                {
                    "grn_item_id": 9999,
                    "return_quantity": 1,
                    "return_reason": "Damaged item",
                }
            ],
        },
    )

    assert response.status_code == 400
    assert "Invalid GRN item" in response.json()["message"]


def test_01_vendor_and_purchase_order_lifecycle(client, superuser_headers, pharmacist_headers):
    """Scenario 1: Register a vendor, draft a PO, and approve it via Maker-Checker."""

    # 1. Register Vendor
    vendor_res = client.post(
        "/v1/api/procurement/vendors",
        headers=pharmacist_headers,
        json={
            "code": "VND-TEST-01",
            "name": "MediEquip Global",
            "category": "PHARMACEUTICALS",
            "contact_person": "Jane Doe",
            "phone": "9876543210",
            "email": "sales@example.com",
            "address": "123 Logistics Park",
            "credit_period_days": 45
        }
    )
    assert vendor_res.status_code == 201, f"Vendor creation failed: {vendor_res.json()}"
    vendor = vendor_res.json()

    # 2. Draft PO
    po_res = client.post(
        "/v1/api/procurement/purchase-orders",
        headers=pharmacist_headers,
        json={
            "vendor_id": vendor["id"],
            "delivery_due_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
            "payment_terms": "Net 45 Days",
            "items": [
                {"item_description": "Paracetamol 500mg Bulk", "quantity_ordered": 1000, "unit_price_paise": 500}
            ]
        }
    )
    assert po_res.status_code == 201, f"PO drafting failed: {po_res.text}"
    po_id = po_res.json()["id"]

    # 3. Approve PO
    approval = client.patch(f"/v1/api/procurement/purchase-orders/{po_id}/approve", headers=superuser_headers)
    assert approval.status_code == 200, f"PO approval failed: {approval.text}"
    assert approval.json()["status"] == "APPROVED"

def test_02_grn_acceptance_auto_generates_inventory_batches(client, superuser_headers, pharmacist_headers):
    """Scenario 2: Receiving and accepting a GRN automatically creates live Pharmacy stock batches."""

    # 1. Independent Setup: Create Vendor and PO
    vendor = client.post("/v1/api/procurement/vendors", headers=pharmacist_headers, json={
        "code": "VND-TEST-02", "name": "GRN Test Vendor", "category": "PHARMACEUTICALS",
        "contact_person": "John", "phone": "1234567890", "email": "test@vendor.com", "address": "123 St"
    }).json()

    po = client.post("/v1/api/procurement/purchase-orders", headers=pharmacist_headers, json={
        "vendor_id": vendor["id"], "delivery_due_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        "payment_terms": "Net 30", "items": [{"item_description": "Test Med", "quantity_ordered": 1000, "unit_price_paise": 500}]
    }).json()

    client.patch(f"/v1/api/procurement/purchase-orders/{po['id']}/approve", headers=superuser_headers)

    # 2. Process GRN against the newly created PO
    po_id = po["id"]
    po_item_id = po["items"][0]["id"]

    grn_res = client.post(
        "/v1/api/procurement/grn",
        headers=pharmacist_headers,
        json={
            "po_id": po_id,
            "invoice_number": "INV-VND-999",
            "invoice_date": datetime.now(timezone.utc).isoformat(),
            "items": [{
                "po_item_id": po_item_id,
                "batch_number": "BATCH-AUTO-001",
                "expiry_date": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
                "received_quantity": 1000,
                "accepted_quantity": 1000
            }]
        }
    )
    assert grn_res.status_code == 201, f"GRN creation failed: {grn_res.text}"
    grn = grn_res.json()

    accept_res = client.patch(f"/v1/api/procurement/grn/{grn['id']}/accept", headers=superuser_headers)
    assert accept_res.status_code == 200, f"GRN acceptance failed: {accept_res.text}"

def test_03_patient_indent_issue_and_return_auto_bills_invoice(client, doctor_headers, pharmacist_headers, billing_headers, superuser_headers):
    """Scenario 3: Issuing an indent bills the patient; returning stock credits the patient."""
    p_res = client.post("/v1/api/patients", headers=doctor_headers, json={"full_name": "Indent Patient", "date_of_birth": "1990-01-01T00:00:00Z", "gender": "MALE"})
    assert p_res.status_code == 201, f"Patient creation failed: {p_res.text}"
    p = p_res.json()

    enc_res = client.post("/v1/api/adt/encounters", headers=doctor_headers, json={"patient_id": p["id"], "encounter_type": "IPD", "primary_doctor_id": 2, "department_id": 1})
    assert enc_res.status_code == 201, f"Encounter creation failed: {enc_res.text}"
    enc = enc_res.json()

    med_res = client.post("/v1/api/pharmacy/medications", headers=pharmacist_headers, json={"code": "MED_IND", "brand_name": "Indent Drug", "generic_name": "Generic", "form": "TABLET", "strength": "10mg"})
    assert med_res.status_code == 201, f"Medication creation failed: {med_res.text}"
    med = med_res.json()

    batch_res = client.post("/v1/api/pharmacy/inventory/batches", headers=pharmacist_headers, json={"medication_id": med["id"], "batch_number": "IND-B1", "expiry_date": "2028-01-01T00:00:00Z", "stock_quantity": 50, "unit_price_paise": 1000})
    assert batch_res.status_code == 201, f"Batch creation failed: {batch_res.text}"
    batch = batch_res.json()

    indent_res = client.post(
        "/v1/api/procurement/indents/patient",
        headers=superuser_headers,
        json={"requesting_department_id": 1, "encounter_id": enc["id"], "items": [{"medication_id": med["id"], "requested_quantity": 10}]}
    )
    assert indent_res.status_code == 201, f"Indent creation failed: {indent_res.text}"
    indent = indent_res.json()

    issue_res = client.post(f"/v1/api/procurement/indents/patient/{indent['id']}/issue", headers=pharmacist_headers, json={"items": [{"indent_item_id": indent["items"][0]["id"], "batch_id": batch["id"], "issue_quantity": 10}]})
    assert issue_res.status_code == 200, f"Indent issue failed: {issue_res.text}"


def test_supplier_payment_request_contract_requires_exact_invoice_allocation_total():
    import pytest
    from pydantic import ValidationError
    from backend.domains.procurement.schemas import SupplierPaymentRequestCreate

    with pytest.raises(ValidationError):
        SupplierPaymentRequestCreate.model_validate({
            "vendor_id": 1,
            "payment_reference": "BANK-REF-001",
            "payment_method": "NEFT",
            "scheduled_date": "2026-11-08",
            "amount_paise": 10000,
            "allocations": [{"invoice_id": 11, "amount_paise": 9000}],
        })

    with pytest.raises(ValidationError):
        SupplierPaymentRequestCreate.model_validate({
            "vendor_id": 1,
            "payment_reference": "BANK-REF-002",
            "payment_method": "NEFT",
            "scheduled_date": "2026-11-08",
            "amount_paise": 10000,
            "allocations": [
                {"invoice_id": 11, "amount_paise": 5000},
                {"invoice_id": 11, "amount_paise": 5000},
            ],
        })


def test_supplier_payment_request_contract_accepts_exact_unique_allocations():
    from backend.domains.procurement.schemas import SupplierPaymentRequestCreate

    payload = SupplierPaymentRequestCreate.model_validate({
        "vendor_id": 1,
        "payment_reference": " BANK-REF-003 ",
        "payment_method": "NEFT",
        "scheduled_date": "2026-11-08",
        "amount_paise": 10000,
        "allocations": [
            {"invoice_id": 11, "amount_paise": 6000},
            {"invoice_id": 12, "amount_paise": 4000},
        ],
    })

    assert payload.amount_paise == sum(row.amount_paise for row in payload.allocations)
    assert len({row.invoice_id for row in payload.allocations}) == 2



def test_supplier_invoice_cannot_be_paid_through_generic_expense_endpoint():
    from types import SimpleNamespace
    import pytest
    from fastapi import HTTPException
    from backend.domains.finance.models import ExpenseStatusEnum
    from backend.domains.finance.router import mark_expense_paid

    class ExistingSupplierInvoiceQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def with_for_update(self):
            return self

        def one_or_none(self):
            return SimpleNamespace(id=55, status=ExpenseStatusEnum.APPROVED)

        def first(self):
            return (123,)

    class FakeDb:
        def query(self, _model):
            return ExistingSupplierInvoiceQuery()

    with pytest.raises(HTTPException) as error:
        mark_expense_paid(
            55,
            "BANK-REF-55",
            FakeDb(),
            SimpleNamespace(id=7),
        )

    assert error.value.status_code == 409
    assert "supplier payment request" in error.value.detail.lower()

def test_bank_statement_contract_requires_balanced_period_and_unique_transactions():
    import pytest
    from pydantic import ValidationError
    from backend.domains.procurement.bank_reconciliation import BankStatementImport

    valid = {
        "account_key": "OPERATING-01",
        "account_label": "Main operating account",
        "statement_reference": "STMT-2026-11",
        "period_start": "2026-11-01",
        "period_end": "2026-11-30",
        "opening_balance_paise": 10000,
        "closing_balance_paise": 9000,
        "lines": [
            {
                "bank_transaction_id": "TXN-001",
                "transaction_date": "2026-11-03",
                "direction": "DEBIT",
                "amount_paise": 3000,
                "description": "Supplier transfer",
            },
            {
                "bank_transaction_id": "TXN-002",
                "transaction_date": "2026-11-04",
                "direction": "CREDIT",
                "amount_paise": 2000,
                "description": "Bank credit",
            },
        ],
    }
    payload = BankStatementImport.model_validate(valid)
    assert payload.opening_balance_paise + 2000 - 3000 == payload.closing_balance_paise

    bad_balance = {**valid, "closing_balance_paise": 9500}
    with pytest.raises(ValidationError):
        BankStatementImport.model_validate(bad_balance)

    duplicate = {
        **valid,
        "lines": [valid["lines"][0], {**valid["lines"][1], "bank_transaction_id": "TXN-001"}],
    }
    with pytest.raises(ValidationError):
        BankStatementImport.model_validate(duplicate)

    outside_period = {
        **valid,
        "lines": [{**valid["lines"][0], "transaction_date": "2026-12-01"}],
    }
    with pytest.raises(ValidationError):
        BankStatementImport.model_validate(outside_period)


def test_bank_statement_import_route_is_registered(client, superuser_headers):
    response = client.get(
        "/v1/api/procurement/bank-statements",
        headers=superuser_headers,
    )
    assert response.status_code == 200, response.text
    assert {"items", "total", "page", "page_size"} <= set(response.json())

    payments = client.get(
        "/v1/api/procurement/supplier-payments",
        headers=superuser_headers,
    )
    assert payments.status_code == 200, payments.text
    assert {"items", "total", "page", "page_size"} <= set(payments.json())


def test_bank_statement_contract_rejects_numeric_account_alias_and_unmasked_label():
    import pytest
    from pydantic import ValidationError
    from backend.domains.procurement.bank_reconciliation import BankStatementImport

    valid = {
        "account_key": "OPERATING-01",
        "statement_reference": "STMT-SECURITY-01",
        "period_start": "2026-11-01",
        "period_end": "2026-11-30",
        "opening_balance_paise": 1000,
        "closing_balance_paise": 1000,
        "lines": [{
            "bank_transaction_id": "TXN-SECURITY-01",
            "transaction_date": "2026-11-03",
            "direction": "DEBIT",
            "amount_paise": 100,
        }],
    }
    with pytest.raises(ValidationError):
        BankStatementImport.model_validate({**valid, "account_key": "123456789012"})
    with pytest.raises(ValidationError):
        BankStatementImport.model_validate({**valid, "account_key": "1234-5678-9012"})
    with pytest.raises(ValidationError):
        BankStatementImport.model_validate({**valid, "account_key": "1234.5678.9012"})
    with pytest.raises(ValidationError):
        BankStatementImport.model_validate({**valid, "account_key": "1234 5678 9012"})
    with pytest.raises(ValidationError):
        BankStatementImport.model_validate({**valid, "account_label": "Account 123456789012"})
    with pytest.raises(ValidationError):
        BankStatementImport.model_validate({**valid, "account_label": "Account 1234-5678-9012"})


def test_reconciliation_candidate_endpoint_is_registered(client, superuser_headers):
    response = client.get(
        "/v1/api/procurement/reconciliation/candidates?as_of=2026-11-08&limit=100",
        headers=superuser_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert {"items", "total_candidates", "limit", "truncated", "as_of", "disclaimer"} <= set(body)
    assert body["as_of"] == "2026-11-08"


def test_reconciliation_candidate_discovery_classifies_all_source_indicators():
    from datetime import date, datetime, timezone
    from types import SimpleNamespace

    from backend.domains.procurement.bank_reconciliation import list_reconciliation_candidates
    from backend.domains.procurement.models import (
        BankStatementLine,
        SupplierPayment,
        SupplierPaymentBankMatch,
        SupplierPaymentRequest,
    )

    debit = SimpleNamespace(
        id=101, direction="DEBIT", amount_paise=1000,
        transaction_date=date(2026, 11, 2), bank_reference="BANK-DEBIT-101",
        bank_transaction_id="TXN-101",
    )
    credit = SimpleNamespace(
        id=102, direction="CREDIT", amount_paise=2500,
        transaction_date=date(2026, 11, 3), bank_reference="BANK-CREDIT-102",
        bank_transaction_id="TXN-102",
    )
    payment_partial = SimpleNamespace(
        id=201, amount_paise=800, payment_date=datetime(2026, 11, 1, tzinfo=timezone.utc),
        payment_reference="SUPP-REF 77", vendor_id=9,
    )
    payment_duplicate = SimpleNamespace(
        id=202, amount_paise=100, payment_date=datetime(2026, 11, 1, tzinfo=timezone.utc),
        payment_reference="supp-ref77", vendor_id=9,
    )
    overdue_request = SimpleNamespace(
        id=301, status="APPROVED", scheduled_date=date(2026, 11, 7),
        executed_payment_id=None, amount_paise=500, payment_reference="REQ-301",
        vendor_id=9,
    )

    class FakeQuery:
        def __init__(self, rows):
            self.rows = rows

        def order_by(self, *_args):
            return self

        def limit(self, *_args):
            return self

        def offset(self, *_args):
            return self

        def filter(self, *_args):
            return self

        def group_by(self, *_args):
            return self

        def all(self):
            return self.rows

    class FakeDb:
        def query(self, *entities):
            first = entities[0]
            if first is BankStatementLine:
                return FakeQuery([debit, credit])
            if first is SupplierPayment:
                return FakeQuery([payment_partial, payment_duplicate])
            if first is SupplierPaymentRequest:
                return FakeQuery([overdue_request])
            if first is SupplierPaymentBankMatch.statement_line_id:
                return FakeQuery([(debit.id, 400)])
            if first is SupplierPaymentBankMatch.supplier_payment_id:
                return FakeQuery([(payment_partial.id, 300), (payment_duplicate.id, 100)])
            raise AssertionError(f"Unexpected reconciliation query: {entities!r}")

    result = list_reconciliation_candidates(
        as_of=date(2026, 11, 8),
        limit=100,
        db=FakeDb(),
    )
    by_type = {row["candidate_type"]: row for row in result["items"]}

    assert by_type["PARTIALLY_MATCHED_BANK_DEBIT"]["remaining_amount_paise"] == 600
    assert by_type["UNCLASSIFIED_BANK_CREDIT"]["amount_paise"] == 2500
    assert by_type["PARTIALLY_RECONCILED_SUPPLIER_PAYMENT"]["remaining_amount_paise"] == 500
    assert by_type["POSSIBLE_DUPLICATE_PAYMENT_REFERENCE"]["source_ids"] == [201, 202]
    assert by_type["OVERDUE_APPROVED_PAYMENT_REQUEST"]["source_id"] == 301
    assert result["truncated"] is False
    assert "not fraud findings" in result["disclaimer"].lower()


def test_reconciliation_investigation_lifecycle_is_versioned_and_audited(client, superuser_headers):
    policy = client.post(
        "/v1/api/procurement/reconciliation/sla-policies",
        headers=superuser_headers,
        json={"severity": "HIGH", "target_minutes": 120, "warning_percent": 75},
    )
    assert policy.status_code == 201, policy.text
    assert policy.json()["version"] == 1

    statement = client.post(
        "/v1/api/procurement/bank-statements/import",
        headers=superuser_headers,
        json={
            "account_key": "INVESTIGATION-01",
            "statement_reference": "INVESTIGATION-STMT-01",
            "period_start": "2026-11-01",
            "period_end": "2026-11-30",
            "opening_balance_paise": 10000,
            "closing_balance_paise": 9000,
            "lines": [{
                "bank_transaction_id": "INVESTIGATION-TXN-01",
                "transaction_date": "2026-11-03",
                "direction": "DEBIT",
                "amount_paise": 1000,
            }],
        },
    )
    assert statement.status_code == 201, statement.text
    # Resolve the actual line from the imported statement instead of relying on an ID.
    batch_id = statement.json()["id"]
    source_id = client.get(
        f"/v1/api/procurement/bank-statements/{batch_id}/lines",
        headers=superuser_headers,
    )
    assert source_id.status_code == 200, source_id.text
    line_id = source_id.json()["items"][0]["id"]

    opened = client.post(
        "/v1/api/procurement/reconciliation/investigations",
        headers=superuser_headers,
        json={
            "candidate_type": "UNMATCHED_BANK_DEBIT",
            "source_type": "BANK_STATEMENT_LINE",
            "source_id": line_id,
            "source_reference": "INVESTIGATION-TXN-01",
            "title": "Review unmatched supplier debit",
            "summary": "Confirm the supplier payment and supporting bank evidence.",
            "severity": "HIGH",
        },
    )
    assert opened.status_code == 201, opened.text
    case = opened.json()
    assert case["status"] == "OPEN"
    assert case["version"] == 1
    assert case["sla_policy_version"] == 1
    assert case["sla_target_minutes"] == 120
    assert case["sla_due_at"] is not None
    assert case["sla_state"] in {"ON_TRACK", "WARNING"}

    duplicate = client.post(
        "/v1/api/procurement/reconciliation/investigations",
        headers=superuser_headers,
        json={
            "candidate_type": "UNMATCHED_BANK_DEBIT",
            "source_type": "BANK_STATEMENT_LINE",
            "source_id": line_id,
            "title": "Duplicate case",
            "summary": "This duplicate must be rejected by the source identity key.",
        },
    )
    assert duplicate.status_code == 409

    policy_v2 = client.post(
        "/v1/api/procurement/reconciliation/sla-policies",
        headers=superuser_headers,
        json={"severity": "HIGH", "target_minutes": 60, "warning_percent": 80},
    )
    assert policy_v2.status_code == 201, policy_v2.text
    assert policy_v2.json()["version"] == 2
    active_policies = client.get(
        "/v1/api/procurement/reconciliation/sla-policies?active_only=true",
        headers=superuser_headers,
    )
    assert active_policies.status_code == 200
    assert len([item for item in active_policies.json() if item["severity"] == "HIGH"]) == 1
    active_high_policy = next(item for item in active_policies.json() if item["severity"] == "HIGH")
    assert active_high_policy["version"] == 2
    unchanged_case = client.get(
        "/v1/api/procurement/reconciliation/investigations",
        headers=superuser_headers,
    )
    original_snapshot = next(item for item in unchanged_case.json()["items"] if item["id"] == case["id"])
    assert original_snapshot["sla_policy_version"] == 1
    assert original_snapshot["sla_target_minutes"] == 120

    sla_summary = client.get(
        "/v1/api/procurement/reconciliation/sla-summary",
        headers=superuser_headers,
    )
    assert sla_summary.status_code == 200, sla_summary.text
    assert sla_summary.json()["with_sla"] >= 1

    in_review = client.patch(
        f"/v1/api/procurement/reconciliation/investigations/{case['id']}/transition",
        headers=superuser_headers,
        json={"to_status": "IN_REVIEW", "expected_version": 1, "note": "Review started"},
    )
    assert in_review.status_code == 200, in_review.text
    assert in_review.json()["status"] == "IN_REVIEW"
    assert in_review.json()["version"] == 2

    resolved = client.patch(
        f"/v1/api/procurement/reconciliation/investigations/{case['id']}/transition",
        headers=superuser_headers,
        json={
            "to_status": "RESOLVED",
            "expected_version": 2,
            "resolution": "Matched against approved supplier payment evidence.",
            "root_cause": "TIMING_DIFFERENCE",
        },
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "RESOLVED"
    assert resolved.json()["version"] == 3
    assert resolved.json()["resolved_at"] is not None

    stale = client.patch(
        f"/v1/api/procurement/reconciliation/investigations/{case['id']}/transition",
        headers=superuser_headers,
        json={"to_status": "IN_REVIEW", "expected_version": 2},
    )
    assert stale.status_code == 409

    self_review = client.patch(
        f"/v1/api/procurement/reconciliation/investigations/{case['id']}/quality-review",
        headers=superuser_headers,
        json={"decision": "APPROVED", "expected_version": 3, "note": "Self-review must be blocked."},
    )
    assert self_review.status_code == 403

    quality_before_reopen = client.get(
        "/v1/api/procurement/reconciliation/investigations/quality-summary",
        headers=superuser_headers,
    )
    assert quality_before_reopen.status_code == 200, quality_before_reopen.text
    assert quality_before_reopen.json()["closure_quality"]["not_reviewed"] >= 1

    reopened = client.patch(
        f"/v1/api/procurement/reconciliation/investigations/{case['id']}/reopen",
        headers=superuser_headers,
        json={"expected_version": 3, "reason": "New bank evidence contradicts the recorded resolution."},
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status"] == "IN_REVIEW"
    assert reopened.json()["version"] == 4
    assert reopened.json()["reopen_count"] == 1
    assert reopened.json()["resolved_at"] is None
    assert reopened.json()["resolution"] is None
    assert reopened.json()["root_cause"] is None

    # The previous closure remains in immutable history, not active case fields.
    events_after_reopen = client.get(
        f"/v1/api/procurement/reconciliation/investigations/{case['id']}/events",
        headers=superuser_headers,
    )
    assert events_after_reopen.status_code == 200, events_after_reopen.text
    reopened_event = events_after_reopen.json()[0]
    assert reopened_event["event_type"] == "REOPENED"
    reopened_details = reopened_event["details"]
    if isinstance(reopened_details, str):
        reopened_details = json.loads(reopened_details)
    assert reopened_details["previous_resolution"] == "Matched against approved supplier payment evidence."
    assert reopened_details["previous_root_cause"] == "TIMING_DIFFERENCE"

    resolved_again = client.patch(
        f"/v1/api/procurement/reconciliation/investigations/{case['id']}/transition",
        headers=superuser_headers,
        json={
            "to_status": "RESOLVED",
            "expected_version": 4,
            "resolution": "Reviewed the new evidence and closed the investigation.",
        },
    )
    assert resolved_again.status_code == 200, resolved_again.text
    assert resolved_again.json()["status"] == "RESOLVED"
    assert resolved_again.json()["root_cause"] is None
    assert resolved_again.json()["resolution"] == "Reviewed the new evidence and closed the investigation."

    quality = client.get(
        "/v1/api/procurement/reconciliation/investigations/quality-summary",
        headers=superuser_headers,
    )
    assert quality.status_code == 200, quality.text
    assert quality.json()["reopened_count"] >= 1

    events = client.get(
        f"/v1/api/procurement/reconciliation/investigations/{case['id']}/events",
        headers=superuser_headers,
    )
    assert events.status_code == 200, events.text
    # Event history is intentionally newest-first to support stable before_id pagination.
    assert [event["event_type"] for event in events.json()] == [
        "STATUS_CHANGED", "REOPENED", "STATUS_CHANGED", "STATUS_CHANGED", "OPENED"
    ]


def test_reconciliation_escalation_configuration_and_self_service_preferences(
    client, superuser_headers
):
    created = client.post(
        "/v1/api/procurement/reconciliation/escalation-policies",
        headers=superuser_headers,
        json={
            "severity": "HIGH",
            "trigger": "WARNING",
            "enabled": True,
            "delay_minutes": 15,
            "recipient_role_ids": [],
            "channels": ["IN_APP"],
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["version"] == 1
    assert created.json()["enabled"] is True
    assert created.json()["channels"] == ["IN_APP"]

    revised = client.post(
        "/v1/api/procurement/reconciliation/escalation-policies",
        headers=superuser_headers,
        json={
            "severity": "HIGH",
            "trigger": "WARNING",
            "enabled": False,
            "delay_minutes": 30,
            "recipient_role_ids": [],
            "channels": ["IN_APP"],
        },
    )
    assert revised.status_code == 201, revised.text
    assert revised.json()["version"] == 2

    active = client.get(
        "/v1/api/procurement/reconciliation/escalation-policies?active_only=true",
        headers=superuser_headers,
    )
    assert active.status_code == 200, active.text
    active_high = [
        item for item in active.json()
        if item["severity"] == "HIGH" and item["trigger"] == "WARNING"
    ]
    assert len(active_high) == 1
    assert active_high[0]["version"] == 2

    preferences = client.get(
        "/v1/api/procurement/reconciliation/notification-preferences/me",
        headers=superuser_headers,
    )
    assert preferences.status_code == 200, preferences.text
    in_app = next(
        item for item in preferences.json()
        if item["event_type"] == "SLA_WARNING" and item["channel"] == "IN_APP"
    )
    email = next(
        item for item in preferences.json()
        if item["event_type"] == "SLA_WARNING" and item["channel"] == "EMAIL"
    )
    assert in_app["enabled"] is True and in_app["configured"] is False
    assert email["enabled"] is False and email["available"] is False

    saved = client.put(
        "/v1/api/procurement/reconciliation/notification-preferences/me",
        headers=superuser_headers,
        json=[
            {"event_type": "SLA_WARNING", "channel": "IN_APP", "enabled": False},
            {"event_type": "SLA_BREACHED", "channel": "IN_APP", "enabled": True},
        ],
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["updated"] == 2

    updated = client.get(
        "/v1/api/procurement/reconciliation/notification-preferences/me",
        headers=superuser_headers,
    )
    assert updated.status_code == 200
    warning = next(
        item for item in updated.json()
        if item["event_type"] == "SLA_WARNING" and item["channel"] == "IN_APP"
    )
    assert warning["enabled"] is False and warning["configured"] is True

    external = client.put(
        "/v1/api/procurement/reconciliation/notification-preferences/me",
        headers=superuser_headers,
        json=[{"event_type": "SLA_WARNING", "channel": "EMAIL", "enabled": True}],
    )
    assert external.status_code == 422

    external_policy = client.post(
        "/v1/api/procurement/reconciliation/escalation-policies",
        headers=superuser_headers,
        json={
            "severity": "HIGH", "trigger": "BREACHED",
            "enabled": True, "channels": ["SMS"],
        },
    )
    assert external_policy.status_code == 422


def test_reconciliation_notification_configuration_audit_is_recorded(
    client, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import Session
    from backend.domains.procurement.models import ReconciliationNotificationConfigEvent

    response = client.post(
        "/v1/api/procurement/reconciliation/escalation-policies",
        headers=superuser_headers,
        json={
            "severity": "CRITICAL",
            "trigger": "BREACHED",
            "enabled": True,
            "recipient_role_ids": [],
            "channels": ["IN_APP"],
        },
    )
    assert response.status_code == 201, response.text

    engine = multi_tenant_env["tenant_engines"]["hms_default"]
    with Session(engine) as db:
        event = db.query(ReconciliationNotificationConfigEvent).filter_by(
            event_type="ESCALATION_POLICY_CREATED",
            object_id=response.json()["id"],
        ).one()
        assert event.actor_user_id > 0
        assert '"severity":"CRITICAL"' in event.details


def test_reconciliation_candidate_cursor_rejects_offsets_outside_database_range():
    import base64

    from fastapi import HTTPException

    from backend.domains.procurement.bank_reconciliation import list_reconciliation_candidates

    forged_cursor = base64.urlsafe_b64encode(
        json.dumps({"source_offset": 2**63, "candidate_offset": 0}).encode("utf-8")
    ).decode("ascii").rstrip("=")

    with pytest.raises(HTTPException) as exc:
        list_reconciliation_candidates(cursor=forged_cursor, db=object())

    assert exc.value.status_code == 422
    assert exc.value.detail == "Invalid reconciliation candidate cursor."
