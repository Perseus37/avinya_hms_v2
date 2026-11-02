import jwt

from backend.core.config import settings

from backend.core.config import settings


def test_access_token_branch_claim_must_match_resolved_tenant(
    client, superuser_headers, multi_tenant_env
):
    raw_token = superuser_headers["Authorization"].split(" ", 1)[1]
    payload = jwt.decode(
        raw_token,
        options={"verify_signature": False},
        algorithms=[settings.ALGORITHM],
    )
    payload["branch_code"] = "APOLLO-HYD-01"
    forged_context_token = jwt.encode(
        payload,
        multi_tenant_env["tenant_keys"]["default"]["jwt"],
        algorithm=settings.ALGORITHM,
    )

    response = client.get(
        "/v1/api/auth/me",
        headers={**superuser_headers, "Authorization": f"Bearer {forged_context_token}"},
    )

    assert response.status_code == 401


def test_procurement_invoice_records_and_documents_are_branch_isolated(
    client,
    superuser_headers,
    apollo_admin_headers,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(settings, "ATTACHMENTS_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(
        "backend.domains.procurement.documents.scan_file_with_clamav",
        lambda _: None,
    )
    monkeypatch.setattr(
        "backend.domains.procurement.router.trigger_donut_invoice_extraction",
        lambda *_: None,
    )

    vendor = client.post(
        "/v1/api/procurement/vendors",
        headers=superuser_headers,
        json={
            "code": "BRANCH-ISO-VENDOR",
            "name": "Branch Isolation Vendor",
            "category": "GENERAL_SUPPLIES",
            "contact_person": "Test Contact",
            "phone": "1234567890",
            "email": "branch-isolation@example.com",
            "address": "1 Test Street",
        },
    )
    assert vendor.status_code == 201, vendor.text

    upload = client.post(
        "/v1/api/procurement/invoices/upload-document",
        params={"vendor_id": vendor.json()["id"]},
        headers=superuser_headers,
        files={"file": ("branch-invoice.pdf", b"%PDF-1.7\\nbranch isolation", "application/pdf")},
    )
    assert upload.status_code == 200, upload.text
    invoice_id = upload.json()["invoice_id"]

    other_branch_list = client.get(
        "/v1/api/procurement/invoices",
        headers=apollo_admin_headers,
    )
    assert other_branch_list.status_code == 200, other_branch_list.text
    assert other_branch_list.json()["total"] == 0
    assert other_branch_list.json()["items"] == []

    other_branch_detail = client.get(
        f"/v1/api/procurement/invoices/{invoice_id}",
        headers=apollo_admin_headers,
    )
    assert other_branch_detail.status_code == 404

    other_branch_download = client.get(
        f"/v1/api/procurement/invoices/{invoice_id}/document",
        headers=apollo_admin_headers,
    )
    assert other_branch_download.status_code == 404


def test_insurance_provider_catalog_is_branch_isolated(
    client,
    superuser_headers,
    apollo_admin_headers,
):
    created = client.post(
        "/v1/api/insurance/providers",
        headers=superuser_headers,
        json={
            "code": "BRANCH-ISO-INSURER",
            "name": "Branch Isolation Insurer",
            "provider_type": "INSURER",
            "contact_email": "claims@branch-isolation.example",
            "document_requirements": ["Discharge summary"],
        },
    )
    assert created.status_code == 201, created.text
    provider_id = created.json()["id"]

    other_branch_list = client.get(
        "/v1/api/insurance/providers",
        headers=apollo_admin_headers,
    )
    assert other_branch_list.status_code == 200, other_branch_list.text
    assert all(item["id"] != provider_id for item in other_branch_list.json())
    assert all(item["code"] != "BRANCH-ISO-INSURER" for item in other_branch_list.json())

    other_branch_update = client.patch(
        f"/v1/api/insurance/providers/{provider_id}",
        headers=apollo_admin_headers,
        json={"name": "Unauthorized Cross-Branch Update"},
    )
    assert other_branch_update.status_code == 404
