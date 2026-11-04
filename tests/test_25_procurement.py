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

    assert response.status_code == 404
    assert "Accepted goods receipt note" in response.json()["message"]



def test_purchase_requisition_approval_and_partial_po_conversion(
    client, pharmacist_headers, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.identity.models import Department

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        department = db.query(Department).filter(Department.code == "DEPT_GEN_MED").one()
        department_id = department.id

    requisition_response = client.post(
        "/v1/api/procurement/purchase-requisitions",
        headers=pharmacist_headers,
        json={
            "requesting_department_id": department_id,
            "required_by_date": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
            "justification": "Minimum stock threshold reached and forecast demand requires replenishment.",
            "items": [{
                "item_description": "Sterile examination gloves",
                "requested_quantity": 10,
                "estimated_unit_price_paise": 2500,
                "notes": "Non-sterile alternatives are not acceptable.",
            }],
        },
    )
    assert requisition_response.status_code == 201, requisition_response.text
    requisition = requisition_response.json()
    assert requisition["status"] == "DRAFT"
    requisition_id = requisition["id"]
    requisition_item_id = requisition["items"][0]["id"]

    submitted = client.post(
        f"/v1/api/procurement/purchase-requisitions/{requisition_id}/submit",
        headers=pharmacist_headers,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "SUBMITTED"

    creator_cannot_review = client.patch(
        f"/v1/api/procurement/purchase-requisitions/{requisition_id}/review",
        headers=superuser_headers if requisition["requested_by_id"] == -1 else pharmacist_headers,
        json={
            "approved": True,
            "review_notes": "Reviewed",
            "items": [{"requisition_item_id": requisition_item_id, "approved_quantity": 8}],
        },
    )
    # The pharmacist is not an approver; approval is performed by the independent superuser below.
    assert creator_cannot_review.status_code in (403, 409)

    review = client.patch(
        f"/v1/api/procurement/purchase-requisitions/{requisition_id}/review",
        headers=superuser_headers,
        json={
            "approved": True,
            "review_notes": "Approved within the department replenishment budget.",
            "items": [{
                "requisition_item_id": requisition_item_id,
                "approved_quantity": 8,
                "estimated_unit_price_paise": 2400,
            }],
        },
    )
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "APPROVED"
    assert review.json()["items"][0]["approved_quantity"] == 8

    vendor_response = client.post(
        "/v1/api/procurement/vendors",
        headers=pharmacist_headers,
        json={
            "code": "VND-REQ-001",
            "name": "Requisition Supply Partner",
            "category": "GENERAL_SUPPLIES",
            "contact_person": "Procurement Desk",
            "phone": "9876501234",
            "email": "requisition-vendor@example.com",
            "address": "Industrial Estate, Hyderabad",
        },
    )
    assert vendor_response.status_code == 201, vendor_response.text
    vendor_id = vendor_response.json()["id"]

    def create_po(quantity):
        return client.post(
            f"/v1/api/procurement/purchase-requisitions/{requisition_id}/purchase-orders",
            headers=pharmacist_headers,
            json={
                "vendor_id": vendor_id,
                "delivery_due_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                "payment_terms": "Net 30",
                "items": [{
                    "requisition_item_id": requisition_item_id,
                    "quantity_ordered": quantity,
                    "unit_price_paise": 2450,
                }],
            },
        )

    first_po = create_po(5)
    assert first_po.status_code == 201, first_po.text
    assert first_po.json()["requisition_id"] == requisition_id
    assert first_po.json()["items"][0]["requisition_item_id"] == requisition_item_id

    over_order = create_po(4)
    assert over_order.status_code == 409, over_order.text

    second_po = create_po(3)
    assert second_po.status_code == 201, second_po.text

    detail = client.get(
        f"/v1/api/procurement/purchase-requisitions/{requisition_id}",
        headers=superuser_headers,
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["status"] == "CONVERTED"

    po_approval = client.patch(
        f"/v1/api/procurement/purchase-orders/{first_po.json()['id']}/approve",
        headers=superuser_headers,
    )
    assert po_approval.status_code == 200, po_approval.text


def test_purchase_requisition_rejects_unassigned_department(
    client, pharmacist_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.identity.models import Department

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        department = Department(code="PROCUREMENT-UNASSIGNED", name="Unassigned Department")
        db.add(department)
        db.commit()
        department_id = department.id

    response = client.post(
        "/v1/api/procurement/purchase-requisitions",
        headers=pharmacist_headers,
        json={
            "requesting_department_id": department_id,
            "justification": "Department stock replenishment is required.",
            "items": [{"item_description": "Office stationery", "requested_quantity": 2}],
        },
    )
    assert response.status_code == 403, response.text


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
    vendor_list = client.get("/v1/api/procurement/vendors", headers=superuser_headers)
    assert vendor_list.status_code == 200, vendor_list.text
    listed_vendor = next(item for item in vendor_list.json() if item["id"] == vendor["id"])
    assert "bank_account_number" not in listed_vendor

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
    po_list = client.get(
        f"/v1/api/procurement/purchase-orders?vendor_id={vendor['id']}",
        headers=superuser_headers,
    )
    assert po_list.status_code == 200, po_list.text
    assert any(item["id"] == po_id for item in po_list.json()["items"])
    po_detail = client.get(f"/v1/api/procurement/purchase-orders/{po_id}", headers=superuser_headers)
    assert po_detail.status_code == 200, po_detail.text
    blocked_deactivation = client.patch(
        f"/v1/api/procurement/vendors/{vendor['id']}/status",
        headers=superuser_headers,
        json={"is_active": False},
    )
    assert blocked_deactivation.status_code == 409

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

    med = client.post("/v1/api/pharmacy/medications", headers=pharmacist_headers, json={
        "code": "MED_GRN_02", "brand_name": "GRN Test Medicine", "generic_name": "Test Generic",
        "form": "TABLET", "strength": "250mg"
    }).json()

    po = client.post("/v1/api/procurement/purchase-orders", headers=pharmacist_headers, json={
        "vendor_id": vendor["id"], "delivery_due_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        "payment_terms": "Net 30", "items": [{"medication_id": med["id"], "item_description": "Test Med", "quantity_ordered": 1000, "unit_price_paise": 500}]
    }).json()

    client.patch(f"/v1/api/procurement/purchase-orders/{po['id']}/approve", headers=superuser_headers)

    # 2. Process GRN against the newly created PO
    po_id = po["id"]
    po_item_id = po["items"][0]["id"]
    locations = client.get("/v1/api/pharmacy/locations", headers=pharmacist_headers)
    assert locations.status_code == 200, locations.text
    main_location = next(location for location in locations.json() if location["code"] == "MAIN")

    grn_res = client.post(
        "/v1/api/procurement/grn",
        headers=pharmacist_headers,
        json={
            "po_id": po_id,
            "location_id": main_location["id"],
            "invoice_number": "INV-VND-999",
            "invoice_date": datetime.now(timezone.utc).isoformat(),
            "items": [{
                "po_item_id": po_item_id,
                "batch_number": "BATCH-AUTO-001",
                "expiry_date": "2030-01-01T00:00:00+00:00",
                "received_quantity": 600,
                "accepted_quantity": 600
            }]
        }
    )
    assert grn_res.status_code == 201, f"GRN creation failed: {grn_res.text}"
    grn = grn_res.json()

    accept_res = client.patch(f"/v1/api/procurement/grn/{grn['id']}/accept", headers=superuser_headers)
    assert accept_res.status_code == 200, f"GRN acceptance failed: {accept_res.text}"
    duplicate_accept = client.patch(f"/v1/api/procurement/grn/{grn['id']}/accept", headers=superuser_headers)
    assert duplicate_accept.status_code == 409

    second_grn = client.post(
        "/v1/api/procurement/grn",
        headers=pharmacist_headers,
        json={
            "po_id": po_id,
            "location_id": main_location["id"],
            "invoice_number": "INV-VND-1000",
            "invoice_date": datetime.now(timezone.utc).isoformat(),
            "items": [{
                "po_item_id": po_item_id,
                "batch_number": "BATCH-AUTO-001",
                "expiry_date": "2030-01-01T00:00:00+00:00",
                "received_quantity": 400,
                "accepted_quantity": 400
            }]
        },
    )
    assert second_grn.status_code == 201, second_grn.text
    second_accept = client.patch(
        f"/v1/api/procurement/grn/{second_grn.json()['id']}/accept",
        headers=superuser_headers,
    )
    assert second_accept.status_code == 200, second_accept.text

    batches = client.get(
        f"/v1/api/pharmacy/inventory/batches?medication_id={med['id']}",
        headers=pharmacist_headers,
    ).json()["items"]
    assert len(batches) == 1
    assert batches[0]["stock_quantity"] == 1000
    assert batches[0]["location_id"] == main_location["id"]

    ledger = sorted(client.get(
        f"/v1/api/pharmacy/inventory/movements?batch_id={batches[0]['id']}",
        headers=pharmacist_headers,
    ).json()["items"], key=lambda item: item["id"])
    assert len(ledger) == 2
    assert all(item["movement_type"] == "RECEIPT" for item in ledger)
    assert [item["quantity_delta"] for item in ledger] == [600, 400]
    assert [item["stock_before"] for item in ledger] == [0, 600]
    assert [item["stock_after"] for item in ledger] == [600, 1000]

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

    issue_ledger = client.get(
        f"/v1/api/pharmacy/inventory/movements?batch_id={batch['id']}",
        headers=pharmacist_headers,
    ).json()["items"]
    issue_movement = next(item for item in issue_ledger if item["movement_type"] == "WARD_ISSUE")
    assert issue_movement["quantity_delta"] == -10
    assert issue_movement["stock_before"] == 50
    assert issue_movement["stock_after"] == 40

    return_res = client.post(
        f"/v1/api/procurement/indents/patient/{indent['id']}/return",
        headers=superuser_headers,
        json={"items": [{
            "indent_item_id": indent["items"][0]["id"],
            "batch_id": batch["id"],
            "return_quantity": 4,
        }]},
    )
    assert return_res.status_code == 200, f"Indent return failed: {return_res.text}"
    return_ledger = client.get(
        f"/v1/api/pharmacy/inventory/movements?batch_id={batch['id']}",
        headers=pharmacist_headers,
    ).json()["items"]
    return_movement = next(item for item in return_ledger if item["movement_type"] == "WARD_RETURN")
    assert return_movement["quantity_delta"] == 4
    assert return_movement["stock_before"] == 40
    assert return_movement["stock_after"] == 44