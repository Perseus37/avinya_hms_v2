from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import sessionmaker

from backend.domains.finance.models import ExpenseRecord
from backend.domains.procurement.models import VendorInvoice


def test_vendor_invoice_review_match_and_approval_are_end_to_end(
    client, superuser_headers, pharmacist_headers, multi_tenant_env, monkeypatch, tmp_path
):
    from backend.core.config import settings

    monkeypatch.setattr(settings, "ATTACHMENTS_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "backend.domains.procurement.router.trigger_donut_invoice_extraction",
        lambda *_: None,
    )
    monkeypatch.setattr(
        "backend.domains.procurement.documents.scan_file_with_clamav",
        lambda _: None,
    )
    vendor_response = client.post(
        "/v1/api/procurement/vendors",
        headers=superuser_headers,
        json={
            "code": "VND-WORKFLOW-01",
            "name": "Invoice Workflow Vendor",
            "category": "GENERAL_SUPPLIES",
            "contact_person": "Test Contact",
            "phone": "1234567890",
            "email": "workflow@example.com",
            "address": "1 Test Street",
        },
    )
    assert vendor_response.status_code == 201, vendor_response.text
    vendor_id = vendor_response.json()["id"]

    po_response = client.post(
        "/v1/api/procurement/purchase-orders",
        headers=pharmacist_headers,
        json={
            "vendor_id": vendor_id,
            "delivery_due_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
            "payment_terms": "Net 30",
            "items": [
                {
                    "item_description": "Test supply",
                    "quantity_ordered": 2,
                    "unit_price_paise": 100,
                }
            ],
        },
    )
    assert po_response.status_code == 201, po_response.text
    po = po_response.json()
    self_approval = client.patch(
        f"/v1/api/procurement/purchase-orders/{po['id']}/approve",
        headers=pharmacist_headers,
    )
    assert self_approval.status_code == 403

    approval = client.patch(
        f"/v1/api/procurement/purchase-orders/{po['id']}/approve",
        headers=superuser_headers,
    )
    assert approval.status_code == 200, approval.text

    grn_response = client.post(
        "/v1/api/procurement/grn",
        headers=pharmacist_headers,
        json={
            "po_id": po["id"],
            "invoice_number": "INV-MANUAL-001",
            "invoice_date": datetime.now(timezone.utc).isoformat(),
            "items": [
                {
                    "po_item_id": po["items"][0]["id"],
                    "batch_number": "BATCH-001",
                    "expiry_date": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
                    "received_quantity": 2,
                    "accepted_quantity": 2,
                }
            ],
        },
    )
    assert grn_response.status_code == 201, grn_response.text
    grn_id = grn_response.json()["id"]
    grn_acceptance = client.patch(
        f"/v1/api/procurement/grn/{grn_id}/accept",
        headers=superuser_headers,
    )
    assert grn_acceptance.status_code == 200, grn_acceptance.text

    upload = client.post(
        "/v1/api/procurement/invoices/upload-document",
        params={"vendor_id": vendor_id},
        headers=pharmacist_headers,
        files={"file": ("invoice.pdf", b"%PDF-1.7\nsynthetic invoice", "application/pdf")},
    )
    assert upload.status_code == 200, upload.text
    invoice_id = upload.json()["invoice_id"]

    invoice_date = datetime.now(timezone.utc) - timedelta(days=1)
    due_date = datetime.now(timezone.utc) + timedelta(days=29)
    review_payload = {
        "po_id": po["id"],
        "invoice_number": "INV-MANUAL-001",
        "invoice_date": invoice_date.isoformat(),
        "due_date": due_date.isoformat(),
        "subtotal_paise": 200,
        "tax_amount_paise": 36,
        "discount_paise": 0,
        "total_amount_paise": 236,
        "items": [
            {
                "po_item_id": po["items"][0]["id"],
                "item_description": "Test supply",
                "batch_number": "BATCH-001",
                "expiry_date": due_date.isoformat(),
                "quantity": 2,
                "unit_price_paise": 100,
                "tax_percentage": 18,
                "total_price_paise": 200,
            }
        ],
    }
    review = client.patch(
        f"/v1/api/procurement/invoices/{invoice_id}/review",
        headers=superuser_headers,
        json=review_payload,
    )
    assert review.status_code == 200, review.text
    assert review.json()["invoice_number"] == "INV-MANUAL-001"
    assert review.json()["items"][0]["po_item_id"] == po["items"][0]["id"]

    invoice_list = client.get(
        "/v1/api/procurement/invoices",
        params={
            "vendor_id": vendor_id,
            "invoice_status": "PENDING_VERIFICATION",
        },
        headers=superuser_headers,
    )
    assert invoice_list.status_code == 200, invoice_list.text
    assert invoice_list.json()["total"] == 1
    assert invoice_list.json()["items"][0]["id"] == invoice_id
    invoice_detail = client.get(
        f"/v1/api/procurement/invoices/{invoice_id}",
        headers=superuser_headers,
    )
    assert invoice_detail.status_code == 200
    assert invoice_detail.json()["items"][0]["po_item_id"] == po["items"][0]["id"]

    over_quantity_review = {
        **review_payload,
        "subtotal_paise": 300,
        "tax_amount_paise": 54,
        "total_amount_paise": 354,
        "items": [
            {
                **review_payload["items"][0],
                "quantity": 3,
                "total_price_paise": 300,
            }
        ],
    }
    invalid_quantity_review = client.patch(
        f"/v1/api/procurement/invoices/{invoice_id}/review",
        headers=superuser_headers,
        json=over_quantity_review,
    )
    assert invalid_quantity_review.status_code == 200
    over_quantity_match = client.patch(
        f"/v1/api/procurement/invoices/{invoice_id}/reconcile",
        headers=superuser_headers,
    )
    assert over_quantity_match.status_code == 200
    assert over_quantity_match.json()["status"] == "PENDING_VERIFICATION"

    duplicate_po_line_review = {
        **review_payload,
        "subtotal_paise": 400,
        "tax_amount_paise": 72,
        "total_amount_paise": 472,
        "items": [
            {**review_payload["items"][0], "quantity": 2, "total_price_paise": 200},
            {**review_payload["items"][0], "quantity": 2, "total_price_paise": 200},
        ],
    }
    duplicate_po_line_response = client.patch(
        f"/v1/api/procurement/invoices/{invoice_id}/review",
        headers=superuser_headers,
        json=duplicate_po_line_review,
    )
    assert duplicate_po_line_response.status_code == 422

    corrected_review = client.patch(
        f"/v1/api/procurement/invoices/{invoice_id}/review",
        headers=superuser_headers,
        json=review_payload,
    )
    assert corrected_review.status_code == 200
    missing_grn_match = client.patch(
        f"/v1/api/procurement/invoices/{invoice_id}/reconcile",
        headers=superuser_headers,
    )
    assert missing_grn_match.status_code == 200
    assert missing_grn_match.json()["status"] == "PENDING_VERIFICATION"

    review_payload["grn_id"] = grn_id
    corrected_review = client.patch(
        f"/v1/api/procurement/invoices/{invoice_id}/review",
        headers=superuser_headers,
        json=review_payload,
    )
    assert corrected_review.status_code == 200, corrected_review.text

    variance_payload = {
        **review_payload,
        "subtotal_paise": 202,
        "total_amount_paise": 238,
        "items": [
            {
                **review_payload["items"][0],
                "unit_price_paise": 101,
                "total_price_paise": 202,
            }
        ],
    }
    variance_review = client.patch(
        f"/v1/api/procurement/invoices/{invoice_id}/review",
        headers=superuser_headers,
        json=variance_payload,
    )
    assert variance_review.status_code == 200, variance_review.text
    variance_reconciliation = client.patch(
        f"/v1/api/procurement/invoices/{invoice_id}/reconcile",
        headers=superuser_headers,
    )
    assert variance_reconciliation.status_code == 200, variance_reconciliation.text
    assert variance_reconciliation.json()["status"] == "PRICE_VARIANCE_FLAGGED"

    variance_approval = client.post(
        f"/v1/api/procurement/invoices/{invoice_id}/approve",
        headers=superuser_headers,
    )
    assert variance_approval.status_code == 409, variance_approval.text
    tenant_session = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with tenant_session() as db:
        variance_invoice = db.get(VendorInvoice, invoice_id)
        assert variance_invoice.status == "PRICE_VARIANCE_FLAGGED"
        assert variance_invoice.linked_expense_id is None
        assert db.query(ExpenseRecord).count() == 0

    corrected_review = client.patch(
        f"/v1/api/procurement/invoices/{invoice_id}/review",
        headers=superuser_headers,
        json=review_payload,
    )
    assert corrected_review.status_code == 200, corrected_review.text

    reconciliation = client.patch(
        f"/v1/api/procurement/invoices/{invoice_id}/reconcile",
        headers=superuser_headers,
    )
    assert reconciliation.status_code == 200, reconciliation.text
    assert reconciliation.json()["status"] == "MATCHED_APPROVED"

    approval = client.post(
        f"/v1/api/procurement/invoices/{invoice_id}/approve",
        headers=superuser_headers,
    )
    assert approval.status_code == 200, approval.text
    duplicate_approval = client.post(
        f"/v1/api/procurement/invoices/{invoice_id}/approve",
        headers=superuser_headers,
    )
    assert duplicate_approval.status_code == 409
    posted_invoice_edit = client.patch(
        f"/v1/api/procurement/invoices/{invoice_id}/review",
        headers=superuser_headers,
        json=review_payload,
    )
    assert posted_invoice_edit.status_code == 409

    tenant_session = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with tenant_session() as db:
        invoice = db.get(VendorInvoice, invoice_id)
        assert invoice.linked_expense_id is not None
        assert (
            db.query(ExpenseRecord)
            .filter(ExpenseRecord.id == invoice.linked_expense_id)
            .count()
            == 1
        )


def test_invoice_review_requires_consistent_totals(client, superuser_headers, monkeypatch, tmp_path):
    from backend.core.config import settings

    monkeypatch.setattr(settings, "ATTACHMENTS_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "backend.domains.procurement.router.trigger_donut_invoice_extraction",
        lambda *_: None,
    )
    monkeypatch.setattr(
        "backend.domains.procurement.documents.scan_file_with_clamav",
        lambda _: None,
    )
    vendor_response = client.post(
        "/v1/api/procurement/vendors",
        headers=superuser_headers,
        json={
            "code": "VND-WORKFLOW-02",
            "name": "Invoice Totals Vendor",
            "category": "GENERAL_SUPPLIES",
            "contact_person": "Test Contact",
            "phone": "1234567890",
            "email": "totals@example.com",
            "address": "1 Test Street",
        },
    )
    assert vendor_response.status_code == 201, vendor_response.text
    upload = client.post(
        "/v1/api/procurement/invoices/upload-document",
        params={"vendor_id": vendor_response.json()["id"]},
        headers=superuser_headers,
        files={"file": ("invoice.pdf", b"%PDF-1.7\nsynthetic invoice", "application/pdf")},
    )
    assert upload.status_code == 200, upload.text

    invalid_review = client.patch(
        f"/v1/api/procurement/invoices/{upload.json()['invoice_id']}/review",
        headers=superuser_headers,
        json={
            "invoice_number": "INV-BAD-TOTALS",
            "invoice_date": datetime.now(timezone.utc).isoformat(),
            "due_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "subtotal_paise": 100,
            "tax_amount_paise": 18,
            "discount_paise": 0,
            "total_amount_paise": 999,
            "items": [
                {
                    "item_description": "Test supply",
                    "batch_number": "BATCH-001",
                    "expiry_date": datetime.now(timezone.utc).isoformat(),
                    "quantity": 1,
                    "unit_price_paise": 100,
                    "tax_percentage": 18,
                    "total_price_paise": 100,
                }
            ],
        },
    )
    assert invalid_review.status_code == 422

    inconsistent_line_total = client.patch(
        f"/v1/api/procurement/invoices/{upload.json()['invoice_id']}/review",
        headers=superuser_headers,
        json={
            "invoice_number": "INV-BAD-LINE-TOTAL",
            "invoice_date": datetime.now(timezone.utc).isoformat(),
            "due_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "subtotal_paise": 50,
            "tax_amount_paise": 9,
            "discount_paise": 0,
            "total_amount_paise": 59,
            "items": [
                {
                    "item_description": "Test supply",
                    "batch_number": "BATCH-001",
                    "expiry_date": datetime.now(timezone.utc).isoformat(),
                    "quantity": 1,
                    "unit_price_paise": 100,
                    "tax_percentage": 18,
                    "total_price_paise": 50,
                }
            ],
        },
    )
    assert inconsistent_line_total.status_code == 422

    inconsistent_line_tax = client.patch(
        f"/v1/api/procurement/invoices/{upload.json()['invoice_id']}/review",
        headers=superuser_headers,
        json={
            "invoice_number": "INV-BAD-LINE-TAX",
            "invoice_date": datetime.now(timezone.utc).isoformat(),
            "due_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "subtotal_paise": 200,
            "tax_amount_paise": 0,
            "discount_paise": 0,
            "total_amount_paise": 200,
            "items": [
                {
                    "item_description": "Test supply",
                    "batch_number": "BATCH-001",
                    "expiry_date": datetime.now(timezone.utc).isoformat(),
                    "quantity": 2,
                    "unit_price_paise": 100,
                    "tax_percentage": 18,
                    "total_price_paise": 200,
                }
            ],
        },
    )
    assert inconsistent_line_tax.status_code == 422

    valid_rounded_line_tax = client.patch(
        f"/v1/api/procurement/invoices/{upload.json()['invoice_id']}/review",
        headers=superuser_headers,
        json={
            "invoice_number": "INV-VALID-LINE-TAX",
            "invoice_date": datetime.now(timezone.utc).isoformat(),
            "due_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "subtotal_paise": 200,
            "tax_amount_paise": 36,
            "discount_paise": 0,
            "total_amount_paise": 236,
            "items": [
                {
                    "item_description": "Test supply",
                    "batch_number": "BATCH-001",
                    "expiry_date": datetime.now(timezone.utc).isoformat(),
                    "quantity": 2,
                    "unit_price_paise": 100,
                    "tax_percentage": 18,
                    "total_price_paise": 200,
                }
            ],
        },
    )
    assert valid_rounded_line_tax.status_code == 200, valid_rounded_line_tax.text
