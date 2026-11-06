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
        headers=pharmacist_headers,
        json={
            "approved": True,
            "review_notes": "Reviewed",
            "items": [{"requisition_item_id": requisition_item_id, "approved_quantity": 8}],
        },
    )
    # The pharmacist is not an approver; approval is performed by the independent superuser below.
    assert creator_cannot_review.status_code in (403, 409)

    invalid_quantity_review = client.patch(
        f"/v1/api/procurement/purchase-requisitions/{requisition_id}/review",
        headers=superuser_headers,
        json={
            "approved": True,
            "review_notes": "Invalid over-approval attempt.",
            "items": [{"requisition_item_id": requisition_item_id, "approved_quantity": 11}],
        },
    )
    assert invalid_quantity_review.status_code == 422

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



def test_purchase_requisition_creator_cannot_approve_own_request(
    client, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.identity.models import Department, Role, User, UserRole

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        admin = db.query(User).filter(User.email == "admin@default.com").one()
        department = db.query(Department).filter(Department.code == "DEPT_GEN_MED").one()
        admin_role = db.query(Role).filter(Role.code == "ROLE_ADMIN").one()
        assignment = db.query(UserRole).filter(
            UserRole.user_id == admin.id,
            UserRole.department_id == department.id,
        ).first()
        if assignment is None:
            db.add(UserRole(user_id=admin.id, role_id=admin_role.id, department_id=department.id))
            db.commit()
        department_id = department.id

    created = client.post(
        "/v1/api/procurement/purchase-requisitions",
        headers=superuser_headers,
        json={
            "requesting_department_id": department_id,
            "justification": "Urgent replacement of damaged department equipment is required.",
            "items": [{"item_description": "Patient monitor cable", "requested_quantity": 1}],
        },
    )
    assert created.status_code == 201, created.text
    requisition_id = created.json()["id"]
    submitted = client.post(
        f"/v1/api/procurement/purchase-requisitions/{requisition_id}/submit",
        headers=superuser_headers,
    )
    assert submitted.status_code == 200, submitted.text
    approval = client.patch(
        f"/v1/api/procurement/purchase-requisitions/{requisition_id}/review",
        headers=superuser_headers,
        json={
            "approved": True,
            "review_notes": "Attempted self approval.",
            "items": [{"requisition_item_id": created.json()["items"][0]["id"], "approved_quantity": 1}],
        },
    )
    assert approval.status_code == 409, approval.text


def test_purchase_requisition_draft_edit_and_rejection(
    client, pharmacist_headers, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.identity.models import Department

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        department_id = db.query(Department.id).filter(
            Department.code == "DEPT_GEN_MED"
        ).scalar()

    created = client.post(
        "/v1/api/procurement/purchase-requisitions",
        headers=pharmacist_headers,
        json={
            "requesting_department_id": department_id,
            "justification": "Replace worn patient examination equipment.",
            "items": [{"item_description": "Examination lamp", "requested_quantity": 2}],
        },
    )
    assert created.status_code == 201, created.text
    requisition_id = created.json()["id"]
    updated = client.put(
        f"/v1/api/procurement/purchase-requisitions/{requisition_id}",
        headers=pharmacist_headers,
        json={
            "requesting_department_id": department_id,
            "justification": "Replace worn examination lamps before the next audit.",
            "items": [{"item_description": "LED examination lamp", "requested_quantity": 3}],
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["items"][0]["requested_quantity"] == 3

    submitted = client.post(
        f"/v1/api/procurement/purchase-requisitions/{requisition_id}/submit",
        headers=pharmacist_headers,
    )
    assert submitted.status_code == 200, submitted.text
    rejected = client.patch(
        f"/v1/api/procurement/purchase-requisitions/{requisition_id}/review",
        headers=superuser_headers,
        json={"approved": False, "review_notes": "Deferred pending budget approval.", "items": []},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "REJECTED"

    cancellable = client.post(
        "/v1/api/procurement/purchase-requisitions",
        headers=pharmacist_headers,
        json={
            "requesting_department_id": department_id,
            "justification": "The department no longer requires this replacement item.",
            "items": [{"item_description": "Spare examination lamp", "requested_quantity": 1}],
        },
    )
    assert cancellable.status_code == 201, cancellable.text
    cancelled = client.post(
        f"/v1/api/procurement/purchase-requisitions/{cancellable.json()['id']}/cancel",
        headers=pharmacist_headers,
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED"


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

def test_supplier_quotation_comparison_and_independent_selection(
    client, pharmacist_headers, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.identity.models import Department

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        department_id = db.query(Department.id).filter(
            Department.code == "DEPT_GEN_MED"
        ).scalar()

    requisition = client.post(
        "/v1/api/procurement/purchase-requisitions",
        headers=pharmacist_headers,
        json={
            "requesting_department_id": department_id,
            "justification": "Procure replacement examination equipment for the department.",
            "items": [{"item_description": "Examination lamp", "requested_quantity": 5}],
        },
    )
    assert requisition.status_code == 201, requisition.text
    requisition_id = requisition.json()["id"]
    submitted = client.post(
        f"/v1/api/procurement/purchase-requisitions/{requisition_id}/submit",
        headers=pharmacist_headers,
    )
    assert submitted.status_code == 200, submitted.text
    item_id = requisition.json()["items"][0]["id"]
    approved = client.patch(
        f"/v1/api/procurement/purchase-requisitions/{requisition_id}/review",
        headers=superuser_headers,
        json={
            "approved": True,
            "review_notes": "Approved for competitive quotation.",
            "items": [{"requisition_item_id": item_id, "approved_quantity": 5}],
        },
    )
    assert approved.status_code == 200, approved.text

    vendors = []
    for suffix, name in [("A", "Quotation Vendor A"), ("B", "Quotation Vendor B")]:
        response = client.post(
            "/v1/api/procurement/vendors",
            headers=pharmacist_headers,
            json={
                "code": f"QUOTE-{suffix}",
                "name": name,
                "category": "GENERAL_SUPPLIES",
                "contact_person": "Sales Contact",
                "phone": "9876543210",
                "email": f"quote-{suffix.lower()}@example.com",
                "address": "Industrial Estate",
            },
        )
        assert response.status_code == 201, response.text
        vendors.append(response.json())

    for vendor, number, price in [
        (vendors[0], "Q-A-001", 12000),
        (vendors[1], "Q-B-001", 10000),
    ]:
        quote = client.post(
            f"/v1/api/procurement/purchase-requisitions/{requisition_id}/quotations",
            headers=pharmacist_headers,
            json={
                "vendor_id": vendor["id"],
                "quotation_number": number,
                "quoted_at": datetime.now(timezone.utc).isoformat(),
                "delivery_days": 7,
                "items": [{
                    "requisition_item_id": item_id,
                    "quantity_quoted": 5,
                    "unit_price_paise": price,
                    "tax_percentage": 5,
                }],
            },
        )
        assert quote.status_code == 201, quote.text
        assert quote.json()["items"][0]["tax_amount_paise"] == 2500
        assert quote.json()["items"][0]["line_total_paise"] == 52500

    comparison = client.get(
        f"/v1/api/procurement/purchase-requisitions/{requisition_id}/quotations",
        headers=superuser_headers,
    )
    assert comparison.status_code == 200, comparison.text
    assert [quote["vendor_id"] for quote in comparison.json()] == [
        vendors[1]["id"], vendors[0]["id"]
    ]

    selected_id = comparison.json()[0]["id"]
    selected = client.patch(
        f"/v1/api/procurement/purchase-requisitions/{requisition_id}/quotations/{selected_id}/select",
        headers=superuser_headers,
        json={"selection_reason": "Lowest evaluated total cost and acceptable delivery timeline."},
    )
    assert selected.status_code == 200, selected.text
    assert selected.json()["status"] == "SELECTED"
    assert selected.json()["selected_by_id"] is not None

    second_selection = client.patch(
        f"/v1/api/procurement/purchase-requisitions/{requisition_id}/quotations/{comparison.json()[1]['id']}/select",
        headers=superuser_headers,
        json={"selection_reason": "Attempt to replace the already selected supplier."},
    )
    assert second_selection.status_code == 409, second_selection.text

    po_payload = {
        "vendor_id": vendors[1]["id"],
        "delivery_due_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
        "payment_terms": "Net 30",
        "items": [{
            "requisition_item_id": item_id,
            "quantity_ordered": 5,
            "unit_price_paise": 10000,
        }],
    }
    wrong_supplier_payload = {**po_payload, "vendor_id": vendors[0]["id"]}
    wrong_supplier = client.post(
        f"/v1/api/procurement/purchase-requisitions/{requisition_id}/purchase-orders",
        headers=pharmacist_headers,
        json=wrong_supplier_payload,
    )
    assert wrong_supplier.status_code == 409, wrong_supplier.text

    wrong_price_payload = {
        **po_payload,
        "items": [{**po_payload["items"][0], "unit_price_paise": 11000}],
    }
    wrong_price = client.post(
        f"/v1/api/procurement/purchase-requisitions/{requisition_id}/purchase-orders",
        headers=pharmacist_headers,
        json=wrong_price_payload,
    )
    assert wrong_price.status_code == 409, wrong_price.text

    wrong_tax_payload = {
        **po_payload,
        "items": [{**po_payload["items"][0], "tax_percentage": 18}],
    }
    wrong_tax = client.post(
        f"/v1/api/procurement/purchase-requisitions/{requisition_id}/purchase-orders",
        headers=pharmacist_headers,
        json=wrong_tax_payload,
    )
    assert wrong_tax.status_code == 409, wrong_tax.text

    selected_supplier_po = client.post(
        f"/v1/api/procurement/purchase-requisitions/{requisition_id}/purchase-orders",
        headers=pharmacist_headers,
        json=po_payload,
    )
    assert selected_supplier_po.status_code == 201, selected_supplier_po.text
    po_data = selected_supplier_po.json()
    assert po_data["subtotal_paise"] == 50000
    assert po_data["tax_amount_paise"] == 2500
    assert po_data["total_amount_paise"] == 52500
    assert po_data["items"][0]["tax_percentage"] == 5
    assert po_data["items"][0]["tax_amount_paise"] == 2500
    assert po_data["items"][0]["gross_total_paise"] == 52500

    final_comparison = client.get(
        f"/v1/api/procurement/purchase-requisitions/{requisition_id}/quotations",
        headers=superuser_headers,
    )
    assert final_comparison.status_code == 200, final_comparison.text
    statuses = {quote["vendor_id"]: quote["status"] for quote in final_comparison.json()}
    assert statuses[vendors[1]["id"]] == "SELECTED"
    assert statuses[vendors[0]["id"]] == "NOT_SELECTED"

    approved_po = client.patch(
        f"/v1/api/procurement/purchase-orders/{po_data['id']}/approve",
        headers=superuser_headers,
    )
    assert approved_po.status_code == 200, approved_po.text

    outcomes = client.get(
        "/v1/api/procurement/analytics/quotation-outcomes",
        headers=superuser_headers,
    )
    assert outcomes.status_code == 200, outcomes.text
    outcome = next(
        item for item in outcomes.json()["items"]
        if item["purchase_order_id"] == po_data["id"]
    )
    assert outcome["comparison_status"] == "COMPARABLE"
    assert outcome["selected_gross_paise"] == 52500
    assert outcome["best_comparable_alternative"]["gross_paise"] == 63000
    assert outcome["competitive_saving_paise"] == 10500
    assert outcomes.json()["summary"]["competitive_savings_paise"] == 10500
    supplier_outcome = next(
        row for row in outcomes.json()["supplier_outcomes"]
        if row["vendor_id"] == vendors[1]["id"]
    )
    assert supplier_outcome["competitive_savings_paise"] == 10500
    assert supplier_outcome["comparable_line_count"] == 1


def test_purchase_order_amendment_requires_independent_review_and_reapproval(
    client, pharmacist_headers, superuser_headers
):
    vendor = client.post(
        "/v1/api/procurement/vendors",
        headers=pharmacist_headers,
        json={
            "code": "VND-AMEND-01",
            "name": "Amendment Test Supplier",
            "category": "GENERAL_SUPPLIES",
            "contact_person": "Supplier Desk",
            "phone": "9876501234",
            "email": "amendment-supplier@example.com",
            "address": "Industrial Estate",
        },
    )
    assert vendor.status_code == 201, vendor.text

    po = client.post(
        "/v1/api/procurement/purchase-orders",
        headers=pharmacist_headers,
        json={
            "vendor_id": vendor.json()["id"],
            "delivery_due_date": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
            "payment_terms": "Net 30",
            "items": [{
                "item_description": "Examination lamp",
                "quantity_ordered": 2,
                "unit_price_paise": 150000,
                "tax_percentage": 5,
            }],
        },
    )
    assert po.status_code == 201, po.text
    assert po.json()["subtotal_paise"] == 300000
    assert po.json()["tax_amount_paise"] == 15000
    assert po.json()["total_amount_paise"] == 315000
    po_id = po.json()["id"]
    approved = client.patch(
        f"/v1/api/procurement/purchase-orders/{po_id}/approve",
        headers=superuser_headers,
    )
    assert approved.status_code == 200, approved.text

    amendment = client.post(
        f"/v1/api/procurement/purchase-orders/{po_id}/amendments",
        headers=pharmacist_headers,
        json={
            "reason": "Supplier revised delivery schedule and unit pricing.",
            "delivery_due_date": (datetime.now(timezone.utc) + timedelta(days=21)).isoformat(),
            "payment_terms": "Net 45",
            "items": [{
                "item_description": "Examination lamp",
                "quantity_ordered": 2,
                "unit_price_paise": 160000,
                "tax_percentage": 12,
            }],
        },
    )
    assert amendment.status_code == 201, amendment.text
    amendment_id = amendment.json()["id"]
    assert amendment.json()["prior_snapshot"]["total_amount_paise"] == 315000
    assert amendment.json()["proposed_snapshot"]["subtotal_paise"] == 320000
    assert amendment.json()["proposed_snapshot"]["tax_amount_paise"] == 38400
    assert amendment.json()["proposed_snapshot"]["total_amount_paise"] == 358400

    self_review = client.patch(
        f"/v1/api/procurement/purchase-orders/{po_id}/amendments/{amendment_id}/review",
        headers=pharmacist_headers,
        json={"approved": True, "review_notes": "Self review attempt."},
    )
    assert self_review.status_code == 409, self_review.text

    reviewed = client.patch(
        f"/v1/api/procurement/purchase-orders/{po_id}/amendments/{amendment_id}/review",
        headers=superuser_headers,
        json={"approved": True, "review_notes": "Commercial revision reviewed and accepted."},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "APPROVED"

    history = client.get(
        f"/v1/api/procurement/purchase-orders/{po_id}/amendments",
        headers=superuser_headers,
    )
    assert history.status_code == 200, history.text
    assert len(history.json()) == 1
    assert history.json()[0]["prior_snapshot"]["total_amount_paise"] == 315000

    refreshed = client.get(
        f"/v1/api/procurement/purchase-orders/{po_id}",
        headers=superuser_headers,
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["status"] == "SUBMITTED"
    assert refreshed.json()["subtotal_paise"] == 320000
    assert refreshed.json()["tax_amount_paise"] == 38400
    assert refreshed.json()["total_amount_paise"] == 358400
    assert refreshed.json()["items"][0]["tax_percentage"] == 12

    reapproved = client.patch(
        f"/v1/api/procurement/purchase-orders/{po_id}/approve",
        headers=superuser_headers,
    )
    assert reapproved.status_code == 200, reapproved.text
    assert reapproved.json()["status"] == "APPROVED"


def test_purchase_order_shipment_tracking_and_overdue_queue(
    client, pharmacist_headers, superuser_headers
):
    vendor = client.post(
        "/v1/api/procurement/vendors",
        headers=pharmacist_headers,
        json={
            "code": "VND-SHIP-01",
            "name": "Shipment Tracking Supplier",
            "category": "GENERAL_SUPPLIES",
            "contact_person": "Dispatch Desk",
            "phone": "9876501234",
            "email": "shipment-supplier@example.com",
            "address": "Logistics Park",
        },
    )
    assert vendor.status_code == 201, vendor.text

    due_date = datetime.now(timezone.utc) - timedelta(days=3)
    po = client.post(
        "/v1/api/procurement/purchase-orders",
        headers=pharmacist_headers,
        json={
            "vendor_id": vendor.json()["id"],
            "delivery_due_date": due_date.isoformat(),
            "payment_terms": "Net 30",
            "items": [{
                "item_description": "Surgical dressing packs",
                "quantity_ordered": 12,
                "unit_price_paise": 2500,
            }],
        },
    )
    assert po.status_code == 201, po.text
    po_id = po.json()["id"]
    approved = client.patch(
        f"/v1/api/procurement/purchase-orders/{po_id}/approve",
        headers=superuser_headers,
    )
    assert approved.status_code == 200, approved.text

    shipment = client.post(
        f"/v1/api/procurement/purchase-orders/{po_id}/shipments",
        headers=pharmacist_headers,
        json={
            "carrier": "Regional Logistics",
            "tracking_number": "TRACK-PO-001",
            "expected_delivery_at": due_date.isoformat(),
            "notes": "Supplier dispatch expected in three days.",
        },
    )
    assert shipment.status_code == 201, shipment.text
    shipment_id = shipment.json()["id"]
    assert shipment.json()["status"] == "PLANNED"

    dispatched = client.patch(
        f"/v1/api/procurement/purchase-orders/{po_id}/shipments/{shipment_id}",
        headers=pharmacist_headers,
        json={"status": "DISPATCHED", "location": "Supplier warehouse"},
    )
    assert dispatched.status_code == 200, dispatched.text
    in_transit = client.patch(
        f"/v1/api/procurement/purchase-orders/{po_id}/shipments/{shipment_id}",
        headers=pharmacist_headers,
        json={"status": "IN_TRANSIT", "location": "Hyderabad transit hub"},
    )
    assert in_transit.status_code == 200, in_transit.text
    invalid_transition = client.patch(
        f"/v1/api/procurement/purchase-orders/{po_id}/shipments/{shipment_id}",
        headers=pharmacist_headers,
        json={"status": "PLANNED", "location": "Invalid regression"},
    )
    assert invalid_transition.status_code == 409, invalid_transition.text

    events = client.get(
        f"/v1/api/procurement/purchase-orders/{po_id}/shipments",
        headers=superuser_headers,
    )
    assert events.status_code == 200, events.text
    assert [event["status"] for event in events.json()[0]["events"]] == [
        "PLANNED", "DISPATCHED", "IN_TRANSIT"
    ]

    overdue = client.get(
        "/v1/api/procurement/purchase-orders/overdue",
        headers=superuser_headers,
    )
    assert overdue.status_code == 200, overdue.text
    match = next(item for item in overdue.json() if item["po_id"] == po_id)
    assert match["days_overdue"] >= 3
    assert match["outstanding_quantity"] == 12


    backdated = client.patch(
        f"/v1/api/procurement/purchase-orders/{po_id}/shipments/{shipment_id}",
        headers=pharmacist_headers,
        json={
            "status": "DELAYED",
            "event_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            "location": "Backdated location",
        },
    )
    assert backdated.status_code == 422, backdated.text

    confirmed = client.patch(
        f"/v1/api/procurement/purchase-orders/{po_id}/shipments/{shipment_id}",
        headers=pharmacist_headers,
        json={"status": "DELIVERY_CONFIRMED", "location": "Hospital receiving gate"},
    )
    assert confirmed.status_code == 200, confirmed.text
    # Carrier confirmation is not a GRN; PO remains open until formal goods receipt.
    current_po = client.get(
        f"/v1/api/procurement/purchase-orders/{po_id}",
        headers=superuser_headers,
    )
    assert current_po.status_code == 200, current_po.text
    assert current_po.json()["status"] == "APPROVED"


def test_procurement_invoice_tax_rounding_uses_per_line_half_up_paise():
    from backend.domains.procurement.services import _percentage_amount_paise

    assert _percentage_amount_paise(101, 5) == 5
    assert _percentage_amount_paise(1, 50) == 1
    assert _percentage_amount_paise(10000, 18) == 1800

def test_vendor_scorecard_supports_date_filter_and_empty_activity(
    client, superuser_headers, pharmacist_headers
):
    vendor_response = client.post(
        "/v1/api/procurement/vendors",
        headers=pharmacist_headers,
        json={
            "code": "VND-SCORECARD-EMPTY",
            "name": "Scorecard Empty Activity Vendor",
            "category": "GENERAL_SUPPLIES",
            "contact_person": "Procurement Desk",
            "phone": "9876500000",
            "email": "scorecard-empty@example.com",
            "address": "Hyderabad",
        },
    )
    assert vendor_response.status_code == 201, vendor_response.text
    vendor_id = vendor_response.json()["id"]

    response = client.get(
        f"/v1/api/procurement/vendors/{vendor_id}/metrics?from_date=2026-01-01&to_date=2026-12-31",
        headers=superuser_headers,
    )
    assert response.status_code == 200, response.text
    metrics = response.json()
    assert metrics["period"]["from_date"] == "2026-01-01"
    assert metrics["period"]["to_date"] == "2026-12-31"
    assert metrics["purchase_orders"]["total"] == 0
    assert metrics["delivery"]["on_time_delivery_rate_pct"] is None
    assert metrics["fulfillment"]["accepted_fulfillment_rate_pct"] is None
    assert metrics["invoices"]["total"] == 0
    assert metrics["invoices"]["matched_approved_unpaid_exposure_paise"] == 0

    invalid_range = client.get(
        f"/v1/api/procurement/vendors/{vendor_id}/metrics?from_date=2026-12-31&to_date=2026-01-01",
        headers=superuser_headers,
    )
    assert invalid_range.status_code == 422

def test_procurement_cost_intelligence_empty_period_and_date_validation(
    client, superuser_headers
):
    response = client.get(
        "/v1/api/procurement/analytics/cost-intelligence?from_date=2026-01-01&to_date=2026-12-31",
        headers=superuser_headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["procurement_spend"]["total_paise"] == 0
    assert payload["procurement_spend"]["monthly_paise"] == []
    assert payload["procurement_spend"]["by_medication_form_paise"] == []
    assert payload["medication_price_history"] == []
    assert payload["supplier_price_comparison"] == []
    assert payload["supplier_returns"]["returned_quantity"] == 0
    assert payload["supplier_returns"]["returned_value_paise"] == 0

    invalid_range = client.get(
        "/v1/api/procurement/analytics/cost-intelligence?from_date=2026-12-31&to_date=2026-01-01",
        headers=superuser_headers,
    )
    assert invalid_range.status_code == 422



def test_medication_pack_configuration_is_dimension_safe_and_versioned(
    client, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.pharmacy.models import MedicationMaster, MedicationFormEnum

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        medication = MedicationMaster(
            code="MED-PACK-CONFIG-001",
            brand_name="Pack Config Test",
            generic_name="Pack Configuration Test",
            form=MedicationFormEnum.TABLET,
            strength="500 mg",
            is_active=True,
        )
        db.add(medication)
        db.commit()
        medication_id = medication.id

    units = client.get(
        "/v1/api/procurement/units-of-measure",
        headers=superuser_headers,
    )
    assert units.status_code == 200, units.text
    unit_ids = {item["code"]: item["id"] for item in units.json()}
    assert {"TAB", "STRIP", "BOX", "ML", "MG"}.issubset(unit_ids)

    effective_from = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    payload = {
        "purchase_uom_id": unit_ids["STRIP"],
        "base_uom_id": unit_ids["TAB"],
        "units_per_purchase_unit": 10,
        "effective_from": effective_from,
    }
    created = client.post(
        f"/v1/api/procurement/medications/{medication_id}/pack-configurations",
        headers=superuser_headers,
        json=payload,
    )
    assert created.status_code == 201, created.text
    assert float(created.json()["units_per_purchase_unit"]) == 10.0

    duplicate = client.post(
        f"/v1/api/procurement/medications/{medication_id}/pack-configurations",
        headers=superuser_headers,
        json=payload,
    )
    assert duplicate.status_code == 409, duplicate.text

    incompatible_dimension = client.post(
        f"/v1/api/procurement/medications/{medication_id}/pack-configurations",
        headers=superuser_headers,
        json={
            **payload,
            "purchase_uom_id": unit_ids["TAB"],
            "base_uom_id": unit_ids["ML"],
        },
    )
    assert incompatible_dimension.status_code == 422, incompatible_dimension.text

    configuration_id = created.json()["id"]
    deactivated = client.patch(
        f"/v1/api/procurement/medications/{medication_id}/pack-configurations/{configuration_id}/deactivate",
        headers=superuser_headers,
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["is_active"] is False
    assert deactivated.json()["effective_to"] is not None

    replacement = client.post(
        f"/v1/api/procurement/medications/{medication_id}/pack-configurations",
        headers=superuser_headers,
        json={
            **payload,
            "units_per_purchase_unit": 12,
            "effective_from": (datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat(),
        },
    )
    assert replacement.status_code == 201, replacement.text
    assert float(replacement.json()["units_per_purchase_unit"]) == 12.0

    history = client.get(
        f"/v1/api/procurement/medications/{medication_id}/pack-configurations",
        headers=superuser_headers,
    )
    assert history.status_code == 200, history.text
    assert len(history.json()) == 2
    assert history.json()[0]["is_active"] is True
    assert float(history.json()[1]["units_per_purchase_unit"]) == 10.0



def test_pack_unit_purchase_receipt_and_supplier_return_convert_to_stock_base_units(
    client, pharmacist_headers, superuser_headers, multi_tenant_env
):
    vendor_response = client.post(
        "/v1/api/procurement/vendors",
        headers=pharmacist_headers,
        json={
            "code": "VND-PACK-BASE-01",
            "name": "Pack Base Unit Supplier",
            "category": "PHARMACEUTICALS",
            "contact_person": "Store Desk",
            "phone": "9000000001",
            "email": "pack-base@example.com",
            "address": "Supply Park",
        },
    )
    assert vendor_response.status_code == 201, vendor_response.text
    vendor = vendor_response.json()

    medication_response = client.post(
        "/v1/api/pharmacy/medications",
        headers=pharmacist_headers,
        json={
            "code": "MED-PACK-BASE-01",
            "brand_name": "Pack Base Medicine",
            "generic_name": "Pack Base Generic",
            "form": "TABLET",
            "strength": "500mg",
        },
    )
    assert medication_response.status_code == 201, medication_response.text
    medication = medication_response.json()

    units_response = client.get(
        "/v1/api/procurement/units-of-measure",
        headers=superuser_headers,
    )
    assert units_response.status_code == 200, units_response.text
    unit_ids = {unit["code"]: unit["id"] for unit in units_response.json()}

    configuration = client.post(
        f"/v1/api/procurement/medications/{medication['id']}/pack-configurations",
        headers=superuser_headers,
        json={
            "purchase_uom_id": unit_ids["STRIP"],
            "base_uom_id": unit_ids["TAB"],
            "units_per_purchase_unit": 10,
            "effective_from": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        },
    )
    assert configuration.status_code == 201, configuration.text

    po_response = client.post(
        "/v1/api/procurement/purchase-orders",
        headers=pharmacist_headers,
        json={
            "vendor_id": vendor["id"],
            "delivery_due_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "payment_terms": "Net 30",
            "items": [{
                "medication_id": medication["id"],
                "item_description": "Pack Base Medicine - 10 tablet strip",
                "quantity_ordered": 10,
                "unit_price_paise": 1000,
                "purchase_uom_id": unit_ids["STRIP"],
            }],
        },
    )
    assert po_response.status_code == 201, po_response.text
    po = po_response.json()
    po_line = po["items"][0]
    assert po_line["purchase_uom_code"] == "STRIP"
    assert po_line["base_uom_code"] == "TAB"
    assert float(po_line["units_per_purchase_unit"]) == 10.0
    assert float(po_line["base_quantity"]) == 100.0
    assert float(po_line["base_unit_price_paise"]) == 100.0

    approval = client.patch(
        f"/v1/api/procurement/purchase-orders/{po['id']}/approve",
        headers=superuser_headers,
    )
    assert approval.status_code == 200, approval.text

    locations = client.get("/v1/api/pharmacy/locations", headers=pharmacist_headers)
    assert locations.status_code == 200, locations.text
    location = next(item for item in locations.json() if item["code"] == "MAIN")
    grn_response = client.post(
        "/v1/api/procurement/grn",
        headers=pharmacist_headers,
        json={
            "po_id": po["id"],
            "location_id": location["id"],
            "invoice_number": "PACK-BASE-INV-01",
            "invoice_date": datetime.now(timezone.utc).isoformat(),
            "items": [{
                "po_item_id": po_line["id"],
                "batch_number": "PACK-BASE-BATCH-01",
                "expiry_date": "2030-01-01T00:00:00+00:00",
                "received_quantity": 10,
                "accepted_quantity": 10,
            }],
        },
    )
    assert grn_response.status_code == 201, grn_response.text
    grn_id = grn_response.json()["id"]
    accepted = client.patch(
        f"/v1/api/procurement/grn/{grn_id}/accept",
        headers=superuser_headers,
    )
    assert accepted.status_code == 200, accepted.text

    batches = client.get(
        f"/v1/api/pharmacy/inventory/batches?medication_id={medication['id']}",
        headers=pharmacist_headers,
    )
    assert batches.status_code == 200, batches.text
    batch = next(item for item in batches.json()["items"] if item["batch_number"] == "PACK-BASE-BATCH-01")
    assert batch["stock_quantity"] == 100
    assert float(batch["unit_price_paise"]) == 100.0
    assert batch["base_uom_code"] == "TAB"

    movements = client.get(
        f"/v1/api/pharmacy/inventory/movements?batch_id={batch['id']}",
        headers=pharmacist_headers,
    )
    assert movements.status_code == 200, movements.text
    assert all(item["base_uom_code"] == "TAB" for item in movements.json()["items"])

    grns = client.get(f"/v1/api/procurement/grn?po_id={po['id']}", headers=superuser_headers)
    assert grns.status_code == 200, grns.text
    # The GRN item id is available from the persisted receipt line.
    from sqlalchemy.orm import sessionmaker
    from backend.domains.procurement.models import GoodsReceiptItem
    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        grn_item = db.query(GoodsReceiptItem).filter(GoodsReceiptItem.grn_id == grn_id).one()
        grn_item_id = grn_item.id

    returned = client.post(
        "/v1/api/procurement/returns",
        headers=pharmacist_headers,
        json={
            "grn_id": grn_id,
            "vendor_id": vendor["id"],
            "items": [{
                "grn_item_id": grn_item_id,
                "return_quantity": 2,
                "return_reason": "Two strips were damaged on arrival",
            }],
        },
    )
    assert returned.status_code == 200, returned.text

    refreshed = client.get(
        f"/v1/api/pharmacy/inventory/batches?medication_id={medication['id']}",
        headers=pharmacist_headers,
    )
    batch_after_return = next(item for item in refreshed.json()["items"] if item["batch_number"] == "PACK-BASE-BATCH-01")
    assert batch_after_return["stock_quantity"] == 80



def test_normalized_price_benchmark_and_po_approval_variance_override(
    client, superuser_headers, pharmacist_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.pharmacy.models import MedicationMaster, MedicationFormEnum

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        medication = MedicationMaster(
            code="MED-PRICE-CONTROL-001",
            brand_name="Price Control Test",
            generic_name="Price Control Medicine",
            form=MedicationFormEnum.TABLET,
            strength="500 mg",
            is_active=True,
        )
        db.add(medication)
        db.commit()
        medication_id = medication.id

    units = client.get("/v1/api/procurement/units-of-measure", headers=superuser_headers)
    assert units.status_code == 200, units.text
    unit_ids = {unit["code"]: unit["id"] for unit in units.json()}
    config = client.post(
        f"/v1/api/procurement/medications/{medication_id}/pack-configurations",
        headers=superuser_headers,
        json={
            "purchase_uom_id": unit_ids["STRIP"],
            "base_uom_id": unit_ids["TAB"],
            "units_per_purchase_unit": 10,
            "effective_from": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
        },
    )
    assert config.status_code == 201, config.text

    vendor = client.post(
        "/v1/api/procurement/vendors",
        headers=pharmacist_headers,
        json={
            "code": "VND-PRICE-CONTROL-001",
            "name": "Price Control Supplier",
            "category": "PHARMACEUTICALS",
            "contact_person": "Procurement",
            "phone": "9000000011",
            "email": "price-control@example.com",
            "address": "Hyderabad",
        },
    )
    assert vendor.status_code == 201, vendor.text

    def create_po(unit_price):
        response = client.post(
            "/v1/api/procurement/purchase-orders",
            headers=pharmacist_headers,
            json={
                "vendor_id": vendor.json()["id"],
                "delivery_due_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                "payment_terms": "Net 30",
                "items": [{
                    "medication_id": medication_id,
                    "item_description": "Price Control Medicine - 10 tablet strip",
                    "quantity_ordered": 10,
                    "unit_price_paise": unit_price,
                    "purchase_uom_id": unit_ids["STRIP"],
                }],
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    baseline_po = create_po(1000)
    baseline_approval = client.patch(
        f"/v1/api/procurement/purchase-orders/{baseline_po['id']}/approve",
        headers=superuser_headers,
    )
    assert baseline_approval.status_code == 200, baseline_approval.text

    second_baseline_po = create_po(1000)
    second_baseline_approval = client.patch(
        f"/v1/api/procurement/purchase-orders/{second_baseline_po['id']}/approve",
        headers=superuser_headers,
    )
    assert second_baseline_approval.status_code == 200, second_baseline_approval.text

    policy = client.put(
        f"/v1/api/procurement/medications/{medication_id}/price-control",
        headers=superuser_headers,
        json={
            "max_variance_pct": 20,
            "minimum_observations": 2,
            "lookback_days": 180,
            "is_active": True,
        },
    )
    assert policy.status_code == 200, policy.text

    candidate_po = create_po(1500)
    blocked = client.patch(
        f"/v1/api/procurement/purchase-orders/{candidate_po['id']}/approve",
        headers=superuser_headers,
    )
    assert blocked.status_code == 409, blocked.text
    variance = blocked.json()["detail"]["price_variances"][0]
    assert variance["base_uom_code"] == "TAB"
    assert variance["benchmark_observations"] == 2
    assert variance["threshold_pct"] == 20
    assert variance["variance_pct"] == 50.0

    approved = client.patch(
        f"/v1/api/procurement/purchase-orders/{candidate_po['id']}/approve",
        headers=superuser_headers,
        json={"override_reason": "Urgent supplier shortage; approved alternate source."},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"

    reviews = client.get(
        f"/v1/api/procurement/purchase-orders/{candidate_po['id']}/price-reviews",
        headers=superuser_headers,
    )
    assert reviews.status_code == 200, reviews.text
    assert len(reviews.json()) == 1
    assert reviews.json()[0]["benchmark_median_paise"] == 100.0
    assert reviews.json()[0]["variance_pct"] == 50.0
    assert "Urgent supplier shortage" in reviews.json()[0]["override_reason"]

    benchmark = client.get(
        f"/v1/api/procurement/analytics/price-benchmarks?medication_id={medication_id}&lookback_days=180&minimum_observations=2",
        headers=superuser_headers,
    )
    assert benchmark.status_code == 200, benchmark.text
    assert benchmark.json()["items"][0]["base_uom_code"] == "TAB"
    assert benchmark.json()["items"][0]["observation_count"] == 3

def test_procurement_financial_intelligence_empty_period_and_date_validation(
    client, superuser_headers
):
    response = client.get(
        "/v1/api/procurement/analytics/financial-intelligence",
        headers=superuser_headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["commitments"]["committed_value_paise"] == 0
    assert payload["receipts"]["accepted_goods_value_paise"] == 0
    assert payload["invoices"]["invoiced_value_paise"] == 0
    assert payload["accounts_payable"]["approved_unpaid_value_paise"] == 0
    assert payload["accounts_payable"]["cash_paid_value_paise"] == 0
    assert payload["supplier_concentration"]["suppliers"] == []
    assert payload["supplier_concentration"]["herfindahl_hirschman_index"] is None
    assert payload["supplier_concentration"]["top_three_supplier_share_pct"] is None
    assert payload["quotation_savings"]["competitive_savings_paise"] == 0
    assert payload["quotation_savings"]["realized_cash_savings_reported"] is False
    assert isinstance(payload["budget_intelligence"]["by_period_type"], dict)
    assert "unbudgeted_procurement" in payload["budget_intelligence"]

    quotation_outcomes = client.get(
        "/v1/api/procurement/analytics/quotation-outcomes",
        headers=superuser_headers,
    )
    assert quotation_outcomes.status_code == 200, quotation_outcomes.text
    assert quotation_outcomes.json()["items"] == []
    assert quotation_outcomes.json()["summary"]["competitive_savings_paise"] == 0

    invalid_quotation_range = client.get(
        "/v1/api/procurement/analytics/quotation-outcomes"
        "?from_date=2026-11-10&to_date=2026-11-01",
        headers=superuser_headers,
    )
    assert invalid_quotation_range.status_code == 422

    invalid_range = client.get(
        "/v1/api/procurement/analytics/financial-intelligence"
        "?from_date=2026-11-10&to_date=2026-11-01",
        headers=superuser_headers,
    )
    assert invalid_range.status_code == 422



def test_procurement_budget_creation_activation_and_independent_revision(
    client, pharmacist_headers, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.identity.models import Department

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        department = db.query(Department).filter(Department.code == "DEPT_GEN_MED").one()
        department_id = department.id

    import calendar
    today = datetime.now(timezone.utc).date()
    fiscal_year_start = today.year if today.month >= 4 else today.year - 1
    start = datetime(fiscal_year_start, 4, 1).date()
    end = datetime(fiscal_year_start + 1, 3, 31).date()
    quarter_start_month = ((today.month - 1) // 3) * 3 + 1
    quarter_start = datetime(today.year, quarter_start_month, 1).date()
    quarter_end = datetime(
        today.year,
        quarter_start_month + 2,
        calendar.monthrange(today.year, quarter_start_month + 2)[1],
    ).date()
    created = client.post(
        "/v1/api/procurement/budgets",
        headers=pharmacist_headers,
        json={
            "budget_number": "BUD-FY26-GENMED-PHARM",
            "requesting_department_id": department_id,
            "period_type": "ANNUAL",
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "category": "PHARMACY",
            "total_amount_paise": 25000000,
            "warning_threshold_pct": 80,
        },
    )
    assert created.status_code == 201, created.text
    budget = created.json()
    assert budget["status"] == "DRAFT"
    assert budget["total_amount_paise"] == 25000000

    activated = client.post(
        f"/v1/api/procurement/budgets/{budget['id']}/activate",
        headers=superuser_headers,
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "ACTIVE"

    quarter_child = client.post(
        "/v1/api/procurement/budgets",
        headers=pharmacist_headers,
        json={
            "budget_number": "BUD-FY26-Q1-GENMED-PHARM",
            "parent_budget_id": budget["id"],
            "requesting_department_id": department_id,
            "period_type": "QUARTERLY",
            "period_start": quarter_start.isoformat(),
            "period_end": quarter_end.isoformat(),
            "category": "PHARMACY",
            "total_amount_paise": 5000000,
            "warning_threshold_pct": 75,
        },
    )
    assert quarter_child.status_code == 201, quarter_child.text
    quarter_activated = client.post(
        f"/v1/api/procurement/budgets/{quarter_child.json()['id']}/activate",
        headers=superuser_headers,
    )
    assert quarter_activated.status_code == 200, quarter_activated.text

    duplicate_overlap = client.post(
        "/v1/api/procurement/budgets",
        headers=pharmacist_headers,
        json={
            "budget_number": "BUD-FY26-GENMED-PHARM-OVERLAP",
            "requesting_department_id": department_id,
            "period_type": "ANNUAL",
            "period_start": datetime(today.year, 1, 1).date().isoformat(),
            "period_end": datetime(today.year, 12, 31).date().isoformat(),
            "category": "PHARMACY",
            "total_amount_paise": 20000000,
            "warning_threshold_pct": 75,
        },
    )
    assert duplicate_overlap.status_code == 201, duplicate_overlap.text
    blocked_activation = client.post(
        f"/v1/api/procurement/budgets/{duplicate_overlap.json()['id']}/activate",
        headers=superuser_headers,
    )
    assert blocked_activation.status_code == 409, blocked_activation.text

    vendor = client.post(
        "/v1/api/procurement/vendors",
        headers=pharmacist_headers,
        json={
            "code": "BUDGET-PO-VENDOR",
            "name": "Budget Control Supplier",
            "category": "PHARMACEUTICALS",
            "contact_person": "Budget Desk",
            "phone": "9876501234",
            "email": "budget-control@example.com",
            "address": "Hyderabad",
        },
    )
    assert vendor.status_code == 201, vendor.text
    po = client.post(
        "/v1/api/procurement/purchase-orders",
        headers=pharmacist_headers,
        json={
            "vendor_id": vendor.json()["id"],
            "delivery_due_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
            "payment_terms": "Net 30",
            "items": [{
                "item_description": "Budget controlled pharmacy purchase",
                "quantity_ordered": 1,
                "unit_price_paise": 1000000,
                "budget_department_id": department_id,
                "budget_category": "PHARMACY",
            }],
        },
    )
    assert po.status_code == 201, po.text
    po_approved = client.patch(
        f"/v1/api/procurement/purchase-orders/{po.json()['id']}/approve",
        headers=superuser_headers,
    )
    assert po_approved.status_code == 200, po_approved.text
    assert po_approved.json()["items"][0]["budget_id"] == quarter_child.json()["id"]
    utilization = client.get(
        f"/v1/api/procurement/budgets/{quarter_child.json()['id']}/utilization",
        headers=superuser_headers,
    )
    assert utilization.status_code == 200, utilization.text
    assert utilization.json()["reserved_open_commitment_paise"] == 1000000
    assert utilization.json()["received_consumption_paise"] == 0
    assert utilization.json()["available_paise"] == 4000000

    cancellable_po = client.post(
        "/v1/api/procurement/purchase-orders",
        headers=pharmacist_headers,
        json={
            "vendor_id": vendor.json()["id"],
            "delivery_due_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
            "payment_terms": "Net 30",
            "items": [{
                "item_description": "Purchase commitment to cancel",
                "quantity_ordered": 1,
                "unit_price_paise": 500000,
                "budget_department_id": department_id,
                "budget_category": "PHARMACY",
            }],
        },
    )
    assert cancellable_po.status_code == 201, cancellable_po.text
    cancellable_approved = client.patch(
        f"/v1/api/procurement/purchase-orders/{cancellable_po.json()['id']}/approve",
        headers=superuser_headers,
    )
    assert cancellable_approved.status_code == 200, cancellable_approved.text
    cancelled = client.patch(
        f"/v1/api/procurement/purchase-orders/{cancellable_po.json()['id']}/cancel",
        headers=superuser_headers,
        json={"reason": "Supplier could not fulfil the agreed delivery schedule."},
    )
    assert cancelled.status_code == 200, cancelled.text
    after_cancel = client.get(
        f"/v1/api/procurement/budgets/{quarter_child.json()['id']}/utilization",
        headers=superuser_headers,
    )
    assert after_cancel.json()["reserved_open_commitment_paise"] == 1000000
    assert after_cancel.json()["available_paise"] == 4000000

    over_budget_po = client.post(
        "/v1/api/procurement/purchase-orders",
        headers=pharmacist_headers,
        json={
            "vendor_id": vendor.json()["id"],
            "delivery_due_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
            "payment_terms": "Net 30",
            "items": [{
                "item_description": "Purchase exceeding remaining allocation",
                "quantity_ordered": 1,
                "unit_price_paise": 4000001,
                "budget_department_id": department_id,
                "budget_category": "PHARMACY",
            }],
        },
    )
    assert over_budget_po.status_code == 201, over_budget_po.text
    blocked_po_approval = client.patch(
        f"/v1/api/procurement/purchase-orders/{over_budget_po.json()['id']}/approve",
        headers=superuser_headers,
    )
    assert blocked_po_approval.status_code == 409, blocked_po_approval.text

    grn = client.post(
        "/v1/api/procurement/grn",
        headers=pharmacist_headers,
        json={
            "po_id": po.json()["id"],
            "invoice_number": "BUDGET-GRN-001",
            "invoice_date": datetime.now(timezone.utc).isoformat(),
            "items": [{
                "po_item_id": po.json()["items"][0]["id"],
                "batch_number": "BUDGET-BATCH-001",
                "expiry_date": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
                "received_quantity": 1,
                "accepted_quantity": 1,
            }],
        },
    )
    assert grn.status_code == 201, grn.text
    accepted_grn = client.patch(
        f"/v1/api/procurement/grn/{grn.json()['id']}/accept",
        headers=superuser_headers,
    )
    assert accepted_grn.status_code == 200, accepted_grn.text

    from backend.domains.identity.models import User
    from backend.domains.procurement.models import (
        VendorInvoice, VendorInvoiceItem, VendorInvoiceStatusEnum,
    )
    with session_factory() as db:
        verifier_id = db.query(User.id).filter(User.email == "admin@default.com").scalar()
        invoice = VendorInvoice(
            vendor_id=vendor.json()["id"],
            po_id=po.json()["id"],
            grn_id=grn.json()["id"],
            invoice_number="BUDGET-INVOICE-001",
            invoice_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=30),
            subtotal_paise=1000000,
            tax_amount_paise=50000,
            discount_paise=10000,
            total_amount_paise=1040000,
            status=VendorInvoiceStatusEnum.MATCHED_APPROVED,
            verified_by_id=verifier_id,
            verified_at=datetime.now(timezone.utc),
            created_by_id=verifier_id,
        )
        db.add(invoice)
        db.flush()
        db.add(VendorInvoiceItem(
            invoice_id=invoice.id,
            po_item_id=po.json()["items"][0]["id"],
            item_description="Budget controlled pharmacy purchase",
            batch_number="BUDGET-BATCH-001",
            expiry_date=datetime.now(timezone.utc) + timedelta(days=365),
            quantity=1,
            unit_price_paise=1000000,
            tax_percentage=5,
            total_price_paise=1000000,
            created_by_id=verifier_id,
        ))
        db.commit()

    utilization_after_receipt = client.get(
        f"/v1/api/procurement/budgets/{quarter_child.json()['id']}/utilization",
        headers=superuser_headers,
    )
    assert utilization_after_receipt.status_code == 200, utilization_after_receipt.text
    assert utilization_after_receipt.json()["reserved_open_commitment_paise"] == 0
    assert utilization_after_receipt.json()["received_consumption_paise"] == 1000000
    assert utilization_after_receipt.json()["available_paise"] == 4000000
    assert utilization_after_receipt.json()["verified_invoice_actuals_paise"] == 1040000
    assert utilization_after_receipt.json()["unpaid_verified_invoice_actuals_paise"] == 1040000
    assert utilization_after_receipt.json()["paid_invoice_actuals_paise"] == 0
    annual_utilization = client.get(
        f"/v1/api/procurement/budgets/{budget['id']}/utilization",
        headers=superuser_headers,
    )
    assert annual_utilization.status_code == 200, annual_utilization.text
    assert annual_utilization.json()["received_consumption_paise"] == 1000000
    assert annual_utilization.json()["allocated_to_active_quarters_paise"] == 4000000
    assert annual_utilization.json()["budget_engaged_paise"] == 5000000
    assert annual_utilization.json()["utilization_pct"] == 20.0
    movement_audit = client.get(
        f"/v1/api/procurement/budgets/{budget['id']}/movements",
        headers=superuser_headers,
    )
    assert movement_audit.status_code == 200, movement_audit.text
    assert {row["movement_type"] for row in movement_audit.json()} == {"RESERVATION", "RELEASE", "RECEIPT"}

    dashboard = client.get(
        "/v1/api/procurement/budgets/analytics/dashboard",
        headers=superuser_headers,
        params={
            "from_date": today.isoformat(),
            "to_date": today.isoformat(),
            "department_id": department_id,
            "category": "PHARMACY",
        },
    )
    assert dashboard.status_code == 200, dashboard.text
    dashboard_data = dashboard.json()
    assert dashboard_data["allocation_count"] >= 2
    assert {
        budget["id"], quarter_child.json()["id"]
    }.issubset({row["budget_id"] for row in dashboard_data["allocations"]})
    assert {
        row["period_type"] for row in dashboard_data["allocation_summary_by_department_category_period"]
    } == {"ANNUAL", "QUARTERLY"}
    assert any(row["received_paise"] == 1000000 for row in dashboard_data["monthly_movement_trend"])
    assert any(row["verified_invoice_actuals_paise"] == 1040000 for row in dashboard_data["invoice_actuals_by_budget"])
    assert dashboard_data["definitions"]["forecast"].startswith("Straight-line")

    unbudgeted_po = client.post(
        "/v1/api/procurement/purchase-orders",
        headers=pharmacist_headers,
        json={
            "vendor_id": vendor.json()["id"],
            "delivery_due_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
            "payment_terms": "Net 30",
            "items": [{
                "item_description": "Unbudgeted laboratory supply",
                "quantity_ordered": 1,
                "unit_price_paise": 250000,
                "budget_department_id": department_id,
                "budget_category": "LABORATORY",
            }],
        },
    )
    assert unbudgeted_po.status_code == 201, unbudgeted_po.text
    unbudgeted_approved = client.patch(
        f"/v1/api/procurement/purchase-orders/{unbudgeted_po.json()['id']}/approve",
        headers=superuser_headers,
    )
    assert unbudgeted_approved.status_code == 200, unbudgeted_approved.text
    assert unbudgeted_approved.json()["items"][0]["budget_id"] is None
    unbudgeted_dashboard = client.get(
        "/v1/api/procurement/budgets/analytics/dashboard",
        headers=superuser_headers,
        params={
            "from_date": today.isoformat(),
            "to_date": today.isoformat(),
            "department_id": department_id,
            "category": "LABORATORY",
        },
    )
    assert unbudgeted_dashboard.status_code == 200, unbudgeted_dashboard.text
    assert unbudgeted_dashboard.json()["unbudgeted_procurement"]["purchase_order_count"] == 1
    assert unbudgeted_dashboard.json()["unbudgeted_procurement"]["gross_value_paise"] == 250000

    invalid_dashboard_range = client.get(
        "/v1/api/procurement/budgets/analytics/dashboard",
        headers=superuser_headers,
        params={"from_date": today.isoformat(), "to_date": start.isoformat()},
    )
    assert invalid_dashboard_range.status_code == 422

    revision = client.post(
        f"/v1/api/procurement/budgets/{budget['id']}/revisions",
        headers=pharmacist_headers,
        json={
            "proposed_amount_paise": 30000000,
            "reason": "Increase allocation due to revised annual medicine demand forecast.",
        },
    )
    assert revision.status_code == 201, revision.text
    assert revision.json()["status"] == "PENDING"
    assert revision.json()["prior_amount_paise"] == 25000000

    reviewed = client.patch(
        f"/v1/api/procurement/budgets/{budget['id']}/revisions/{revision.json()['id']}/review",
        headers=superuser_headers,
        json={
            "approved": True,
            "review_notes": "Approved after reviewing updated department forecast.",
        },
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "APPROVED"

    refreshed = client.get(
        f"/v1/api/procurement/budgets/{budget['id']}",
        headers=superuser_headers,
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["total_amount_paise"] == 30000000

    quarter_revision = client.post(
        f"/v1/api/procurement/budgets/{quarter_child.json()['id']}/revisions",
        headers=pharmacist_headers,
        json={
            "proposed_amount_paise": 31000000,
            "reason": "Requested quarter allocation exceeds the remaining annual budget capacity.",
        },
    )
    assert quarter_revision.status_code == 201, quarter_revision.text
    quarter_revision_review = client.patch(
        f"/v1/api/procurement/budgets/{quarter_child.json()['id']}/revisions/{quarter_revision.json()['id']}/review",
        headers=superuser_headers,
        json={
            "approved": True,
            "review_notes": "Rejected because the quarterly allocation would exceed annual capacity.",
        },
    )
    assert quarter_revision_review.status_code == 409, quarter_revision_review.text


def test_procurement_budget_rejects_invalid_period_and_unassigned_department(
    client, pharmacist_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.identity.models import Department

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        department = db.query(Department).filter(Department.code == "DEPT_GEN_MED").one()
        department_id = department.id

    invalid_period = client.post(
        "/v1/api/procurement/budgets",
        headers=pharmacist_headers,
        json={
            "budget_number": "BUD-INVALID-PERIOD",
            "requesting_department_id": department_id,
            "period_type": "ANNUAL",
            "period_start": "2026-04-01",
            "period_end": "2026-06-30",
            "category": "PHARMACY",
            "total_amount_paise": 100000,
        },
    )
    assert invalid_period.status_code == 422

    with session_factory() as db:
        department = Department(code="BUDGET-UNASSIGNED", name="Budget Unassigned")
        db.add(department)
        db.commit()
        unassigned_id = department.id

    unassigned = client.post(
        "/v1/api/procurement/budgets",
        headers=pharmacist_headers,
        json={
            "budget_number": "BUD-UNASSIGNED",
            "requesting_department_id": unassigned_id,
            "period_type": "QUARTERLY",
            "period_start": "2026-04-01",
            "period_end": "2026-06-30",
            "category": "GENERAL_SUPPLIES",
            "total_amount_paise": 100000,
        },
    )
    assert unassigned.status_code == 403



def test_supplier_contract_approval_rate_enforcement_and_revision(
    client, pharmacist_headers, superuser_headers
):
    vendor_response = client.post(
        "/v1/api/procurement/vendors",
        headers=pharmacist_headers,
        json={
            "code": "CONTRACT-RATE-VENDOR",
            "name": "Contract Rate Supplier",
            "category": "PHARMACEUTICALS",
            "contact_person": "Contracts",
            "phone": "9000000099",
            "email": "contract-rate@example.com",
            "address": "Hyderabad",
        },
    )
    assert vendor_response.status_code == 201, vendor_response.text
    vendor_id = vendor_response.json()["id"]

    medication_response = client.post(
        "/v1/api/pharmacy/medications",
        headers=pharmacist_headers,
        json={
            "code": "CONTRACT-RATE-MED",
            "brand_name": "Contract Rate Medicine",
            "generic_name": "Contract Generic",
            "form": "TABLET",
            "strength": "500mg",
        },
    )
    assert medication_response.status_code == 201, medication_response.text
    medication_id = medication_response.json()["id"]

    units_response = client.get(
        "/v1/api/procurement/units-of-measure",
        headers=superuser_headers,
    )
    assert units_response.status_code == 200, units_response.text
    unit_ids = {unit["code"]: unit["id"] for unit in units_response.json()}
    config = client.post(
        f"/v1/api/procurement/medications/{medication_id}/pack-configurations",
        headers=superuser_headers,
        json={
            "purchase_uom_id": unit_ids["STRIP"],
            "base_uom_id": unit_ids["TAB"],
            "units_per_purchase_unit": 10,
            "effective_from": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        },
    )
    assert config.status_code == 201, config.text

    today = datetime.now(timezone.utc).date()
    contract_response = client.post(
        "/v1/api/procurement/supplier-contracts",
        headers=pharmacist_headers,
        json={
            "vendor_id": vendor_id,
            "contract_number": "AGR-CONTRACT-RATE-001",
            "title": "Annual generic medicine rate agreement",
            "valid_from": today.isoformat(),
            "valid_to": (today + timedelta(days=180)).isoformat(),
            "renewal_notice_days": 60,
            "payment_terms": "Net 30",
            "summary": "Negotiated tablet base-unit rate.",
            "rates": [{
                "scope_type": "MEDICATION",
                "medication_id": medication_id,
                "uom_code": "TAB",
                "unit_price_paise": 100,
                "tax_percentage": 0,
            }],
        },
    )
    assert contract_response.status_code == 201, contract_response.text
    contract_id = contract_response.json()["id"]
    submitted = client.post(
        f"/v1/api/procurement/supplier-contracts/{contract_id}/submit",
        headers=pharmacist_headers,
    )
    assert submitted.status_code == 200, submitted.text
    approved = client.patch(
        f"/v1/api/procurement/supplier-contracts/{contract_id}/approve",
        headers=superuser_headers,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "ACTIVE"

    def create_contract_po(unit_price_paise: int):
        return client.post(
            "/v1/api/procurement/purchase-orders",
            headers=pharmacist_headers,
            json={
                "vendor_id": vendor_id,
                "contract_id": contract_id,
                "delivery_due_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                "payment_terms": "Net 30",
                "items": [{
                    "medication_id": medication_id,
                    "item_description": "Contract medicine - 10 tablet strip",
                    "quantity_ordered": 10,
                    "unit_price_paise": unit_price_paise,
                    "purchase_uom_id": unit_ids["STRIP"],
                }],
            },
        )

    mismatch_po = create_contract_po(1500)
    assert mismatch_po.status_code == 201, mismatch_po.text
    mismatch = client.patch(
        f"/v1/api/procurement/purchase-orders/{mismatch_po.json()['id']}/approve",
        headers=superuser_headers,
    )
    assert mismatch.status_code == 409
    assert "differs from the linked supplier contract rate" in mismatch.json()["detail"]

    matching_po = create_contract_po(1000)
    assert matching_po.status_code == 201, matching_po.text
    matching = client.patch(
        f"/v1/api/procurement/purchase-orders/{matching_po.json()['id']}/approve",
        headers=superuser_headers,
    )
    assert matching.status_code == 200, matching.text
    assert matching.json()["contract_id"] == contract_id

    revision = client.post(
        f"/v1/api/procurement/supplier-contracts/{contract_id}/revisions",
        headers=pharmacist_headers,
        json={
            "proposed_valid_to": (today + timedelta(days=240)).isoformat(),
            "proposed_rates": [{
                "scope_type": "MEDICATION",
                "medication_id": medication_id,
                "uom_code": "TAB",
                "unit_price_paise": 110,
                "tax_percentage": 0,
                "notes": "Revised annual negotiated rate.",
            }],
            "reason": "Extend the agreement and revise the negotiated tablet rate for the next procurement cycle.",
        },
    )
    assert revision.status_code == 201, revision.text
    reviewed = client.patch(
        f"/v1/api/procurement/supplier-contracts/{contract_id}/revisions/{revision.json()['id']}/review",
        headers=superuser_headers,
        json={"approved": True, "review_notes": "Extension reviewed and approved."},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "APPROVED"
    contract_detail = client.get(
        f"/v1/api/procurement/supplier-contracts/{contract_id}",
        headers=superuser_headers,
    )
    assert contract_detail.status_code == 200, contract_detail.text
    assert contract_detail.json()["version_number"] == 2
    assert contract_detail.json()["valid_to"] == (today + timedelta(days=240)).isoformat()
    assert contract_detail.json()["rates"][0]["unit_price_paise"] == 110

    stale_rate_po = create_contract_po(1000)
    assert stale_rate_po.status_code == 201, stale_rate_po.text
    stale_rate_approval = client.patch(
        f"/v1/api/procurement/purchase-orders/{stale_rate_po.json()['id']}/approve",
        headers=superuser_headers,
    )
    assert stale_rate_approval.status_code == 409

    revised_rate_po = create_contract_po(1100)
    assert revised_rate_po.status_code == 201, revised_rate_po.text
    revised_rate_approval = client.patch(
        f"/v1/api/procurement/purchase-orders/{revised_rate_po.json()['id']}/approve",
        headers=superuser_headers,
    )
    assert revised_rate_approval.status_code == 200, revised_rate_approval.text

    renewal_queue = client.get(
        "/v1/api/procurement/supplier-contract-renewals/due?within_days=365",
        headers=superuser_headers,
    )
    assert renewal_queue.status_code == 200, renewal_queue.text
    assert any(item["contract_id"] == contract_id for item in renewal_queue.json())


def test_supplier_compliance_document_verification_expiry_and_audited_download(
    client, pharmacist_headers, superuser_headers, monkeypatch
):
    from backend.domains.procurement import documents as procurement_documents

    # Keep this API test independent from a running ClamAV daemon while still
    # exercising signature validation, tenant storage and the document lifecycle.
    monkeypatch.setattr(procurement_documents, "scan_file_with_clamav", lambda _path: None)
    vendor_response = client.post(
        "/v1/api/procurement/vendors",
        headers=pharmacist_headers,
        json={
            "code": "VND-COMPLIANCE-01",
            "name": "Compliance Evidence Supplier",
            "category": "PHARMACEUTICALS",
            "contact_person": "Compliance Officer",
            "phone": "9876543210",
            "email": "compliance@example.test",
            "address": "Supplier registered address",
        },
    )
    assert vendor_response.status_code == 201, vendor_response.text
    vendor_id = vendor_response.json()["id"]
    today = datetime.now(timezone.utc).date()
    upload = client.post(
        f"/v1/api/procurement/vendors/{vendor_id}/compliance-documents",
        headers=pharmacist_headers,
        data={
            "document_type": "DRUG_LICENSE",
            "document_number": "DL-TEST-2026",
            "issuer": "State Drug Control Authority",
            "issue_date": today.isoformat(),
            "expiry_date": (today + timedelta(days=20)).isoformat(),
        },
        files={"file": ("drug-license.pdf", b"%PDF-1.4 test supplier license", "application/pdf")},
    )
    assert upload.status_code == 201, upload.text
    document_id = upload.json()["id"]
    assert upload.json()["status"] == "PENDING_VERIFICATION"

    self_review = client.patch(
        f"/v1/api/procurement/vendors/{vendor_id}/compliance-documents/{document_id}/review",
        headers=pharmacist_headers,
        json={"approved": True, "review_notes": "Uploader cannot independently verify this evidence."},
    )
    assert self_review.status_code == 403

    review = client.patch(
        f"/v1/api/procurement/vendors/{vendor_id}/compliance-documents/{document_id}/review",
        headers=superuser_headers,
        json={"approved": True, "review_notes": "Document details checked against the supplier submission."},
    )
    assert review.status_code == 200, review.text
    assert review.json()["status"] == "VERIFIED"
    assert review.json()["compliance_status"] == "EXPIRING_SOON"

    listing = client.get(
        f"/v1/api/procurement/vendors/{vendor_id}/compliance-documents",
        headers=superuser_headers,
    )
    assert listing.status_code == 200, listing.text
    assert listing.json()[0]["compliance_status"] == "EXPIRING_SOON"

    expiry_queue = client.get(
        "/v1/api/procurement/supplier-compliance/expiring?within_days=30",
        headers=superuser_headers,
    )
    assert expiry_queue.status_code == 200, expiry_queue.text
    assert any(row["document_id"] == document_id for row in expiry_queue.json())

    download = client.get(
        f"/v1/api/procurement/vendors/{vendor_id}/compliance-documents/{document_id}/download",
        headers=superuser_headers,
    )
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF-1.4")


def test_supplier_compliance_policy_blocks_purchase_order_for_missing_required_document(
    client, pharmacist_headers, superuser_headers
):
    vendor_response = client.post(
        "/v1/api/procurement/vendors",
        headers=pharmacist_headers,
        json={
            "code": "VND-POLICY-01",
            "name": "Policy Controlled Pharmaceutical Supplier",
            "category": "PHARMACEUTICALS",
            "contact_person": "Regulatory Contact",
            "phone": "9876543211",
            "email": "policy-supplier@example.test",
            "address": "Supplier registered address",
        },
    )
    assert vendor_response.status_code == 201, vendor_response.text
    vendor_id = vendor_response.json()["id"]

    policy = client.put(
        "/v1/api/procurement/supplier-compliance/policies/PHARMACEUTICALS/DRUG_LICENSE",
        headers=superuser_headers,
        json={"is_required": True},
    )
    assert policy.status_code == 200, policy.text
    assert policy.json()["is_required"] is True

    policies = client.get(
        "/v1/api/procurement/supplier-compliance/policies?vendor_category=PHARMACEUTICALS",
        headers=superuser_headers,
    )
    assert policies.status_code == 200, policies.text
    assert any(
        item["document_type"] == "DRUG_LICENSE" and item["is_required"] is True
        for item in policies.json()
    )
    disabled = client.put(
        "/v1/api/procurement/supplier-compliance/policies/PHARMACEUTICALS/DRUG_LICENSE",
        headers=superuser_headers,
        json={"is_required": False},
    )
    assert disabled.status_code == 200, disabled.text
    re_enabled = client.put(
        "/v1/api/procurement/supplier-compliance/policies/PHARMACEUTICALS/DRUG_LICENSE",
        headers=superuser_headers,
        json={"is_required": True},
    )
    assert re_enabled.status_code == 200, re_enabled.text
    history = client.get(
        "/v1/api/procurement/supplier-compliance/policies/PHARMACEUTICALS/DRUG_LICENSE/history",
        headers=superuser_headers,
    )
    assert history.status_code == 200, history.text
    assert len(history.json()) == 3
    assert [row["new_is_required"] for row in history.json()] == [True, False, True]

    po_response = client.post(
        "/v1/api/procurement/purchase-orders",
        headers=pharmacist_headers,
        json={
            "vendor_id": vendor_id,
            "delivery_due_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "payment_terms": "Net 30",
            "items": [{
                "item_description": "Test pharmaceutical supply",
                "quantity_ordered": 10,
                "unit_price_paise": 1000,
            }],
        },
    )
    assert po_response.status_code == 409, po_response.text
    assert "DRUG_LICENSE" in str(po_response.json())



def test_supplier_compliance_analytics_reports_policy_block_and_category_filter(
    client, pharmacist_headers, superuser_headers
):
    vendor_response = client.post(
        "/v1/api/procurement/vendors",
        headers=pharmacist_headers,
        json={
            "code": "VND-COMP-ANALYTICS-01",
            "name": "Analytics Compliance Supplier",
            "category": "PHARMACEUTICALS",
            "contact_person": "Compliance Contact",
            "phone": "9876543212",
            "email": "analytics-compliance@example.test",
            "address": "Supplier registered address",
        },
    )
    assert vendor_response.status_code == 201, vendor_response.text
    vendor_id = vendor_response.json()["id"]

    policy = client.put(
        "/v1/api/procurement/supplier-compliance/policies/PHARMACEUTICALS/DRUG_LICENSE",
        headers=superuser_headers,
        json={"is_required": True},
    )
    assert policy.status_code == 200, policy.text

    dashboard = client.get(
        "/v1/api/procurement/analytics/supplier-compliance"
        "?vendor_category=PHARMACEUTICALS&search=VND-COMP-ANALYTICS-01",
        headers=superuser_headers,
    )
    assert dashboard.status_code == 200, dashboard.text
    body = dashboard.json()
    assert body["pagination"]["total"] == 1
    assert body["supplier_summary"]["blocked"] == 1
    assert body["supplier_summary"]["compliant"] == 0
    assert body["required_obligations"] == {
        "total": 1, "satisfied": 0, "missing_or_invalid": 1,
    }
    assert body["suppliers"][0]["vendor_id"] == vendor_id
    assert body["suppliers"][0]["compliance_state"] == "BLOCKED"
    assert body["suppliers"][0]["missing_or_invalid_document_types"] == ["DRUG_LICENSE"]
    assert body["compliance_score_pct"] == 0.0

    invalid_category = client.get(
        "/v1/api/procurement/analytics/supplier-compliance?vendor_category=UNKNOWN",
        headers=superuser_headers,
    )
    assert invalid_category.status_code == 422



def test_supplier_risk_register_flags_missing_compliance_and_supports_filters(
    client, pharmacist_headers, superuser_headers
):
    vendor_response = client.post(
        "/v1/api/procurement/vendors",
        headers=pharmacist_headers,
        json={
            "code": "VND-RISK-REGISTER-01",
            "name": "Risk Register Supplier",
            "category": "PHARMACEUTICALS",
            "contact_person": "Risk Contact",
            "phone": "9876543213",
            "email": "risk-register@example.test",
            "address": "Supplier registered address",
        },
    )
    assert vendor_response.status_code == 201, vendor_response.text
    vendor_id = vendor_response.json()["id"]

    policy = client.put(
        "/v1/api/procurement/supplier-compliance/policies/PHARMACEUTICALS/DRUG_LICENSE",
        headers=superuser_headers,
        json={"is_required": True},
    )
    assert policy.status_code == 200, policy.text

    response = client.get(
        "/v1/api/procurement/analytics/supplier-risk-register"
        "?vendor_category=PHARMACEUTICALS&risk_level=HIGH",
        headers=superuser_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    supplier = next(item for item in body["suppliers"] if item["vendor_id"] == vendor_id)
    assert supplier["risk_level"] == "HIGH"
    assert supplier["compliance_state"] == "BLOCKED"
    assert supplier["missing_or_invalid_document_types"] == ["DRUG_LICENSE"]
    assert supplier["open_purchase_order_count"] == 0
    assert body["summary"]["high_count"] >= 1

    invalid_risk = client.get(
        "/v1/api/procurement/analytics/supplier-risk-register?risk_level=URGENT",
        headers=superuser_headers,
    )
    assert invalid_risk.status_code == 422


def test_supplier_suspension_requires_independent_approval_and_blocks_new_orders(
    client, pharmacist_headers, superuser_headers
):
    vendor_response = client.post(
        "/v1/api/procurement/vendors",
        headers=pharmacist_headers,
        json={
            "code": "VND-LIFECYCLE-01",
            "name": "Lifecycle Controlled Supplier",
            "category": "GENERAL_SUPPLIES",
            "contact_person": "Lifecycle Contact",
            "phone": "9876543214",
            "email": "lifecycle-supplier@example.test",
            "address": "Supplier registered address",
        },
    )
    assert vendor_response.status_code == 201, vendor_response.text
    vendor_id = vendor_response.json()["id"]

    request = client.post(
        f"/v1/api/procurement/vendors/{vendor_id}/lifecycle-requests",
        headers=pharmacist_headers,
        json={"action": "SUSPEND", "reason": "Regulatory investigation pending verification."},
    )
    assert request.status_code == 201, request.text
    request_id = request.json()["id"]
    assert request.json()["status"] == "PENDING"

    duplicate = client.post(
        f"/v1/api/procurement/vendors/{vendor_id}/lifecycle-requests",
        headers=pharmacist_headers,
        json={"action": "SUSPEND", "reason": "Duplicate request while review is pending."},
    )
    assert duplicate.status_code == 409

    self_review = client.patch(
        f"/v1/api/procurement/vendors/{vendor_id}/lifecycle-requests/{request_id}/review",
        headers=pharmacist_headers,
        json={"approved": True, "review_notes": "Attempted self approval."},
    )
    assert self_review.status_code == 403

    approved = client.patch(
        f"/v1/api/procurement/vendors/{vendor_id}/lifecycle-requests/{request_id}/review",
        headers=superuser_headers,
        json={"approved": True, "review_notes": "Independent review confirms temporary suspension."},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"

    vendor = client.get(f"/v1/api/procurement/vendors/{vendor_id}", headers=superuser_headers)
    assert vendor.status_code == 200, vendor.text
    assert vendor.json()["is_active"] is True
    assert vendor.json()["is_suspended"] is True
    assert vendor.json()["suspension_reason"] == "Regulatory investigation pending verification."

    blocked_po = client.post(
        "/v1/api/procurement/purchase-orders",
        headers=pharmacist_headers,
        json={
            "vendor_id": vendor_id,
            "delivery_due_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "payment_terms": "Net 30",
            "items": [{
                "item_description": "Sterile examination gloves",
                "quantity_ordered": 5,
                "unit_price_paise": 1000,
            }],
        },
    )
    assert blocked_po.status_code == 409
    assert "suspended" in str(blocked_po.json()).lower()

    reinstatement = client.post(
        f"/v1/api/procurement/vendors/{vendor_id}/lifecycle-requests",
        headers=pharmacist_headers,
        json={"action": "REINSTATE", "reason": "Regulatory investigation completed with clearance."},
    )
    assert reinstatement.status_code == 201, reinstatement.text
    reinstated = client.patch(
        f"/v1/api/procurement/vendors/{vendor_id}/lifecycle-requests/{reinstatement.json()['id']}/review",
        headers=superuser_headers,
        json={"approved": True, "review_notes": "Clearance evidence reviewed and accepted."},
    )
    assert reinstated.status_code == 200, reinstated.text

    final_vendor = client.get(f"/v1/api/procurement/vendors/{vendor_id}", headers=superuser_headers)
    assert final_vendor.status_code == 200
    assert final_vendor.json()["is_suspended"] is False
    assert final_vendor.json()["is_active"] is True

    history = client.get(
        f"/v1/api/procurement/vendors/{vendor_id}/lifecycle-requests",
        headers=superuser_headers,
    )
    assert history.status_code == 200, history.text
    assert [row["action"] for row in history.json()] == ["REINSTATE", "SUSPEND"]
    assert all(row["status"] == "APPROVED" for row in history.json())


def test_supplier_payment_allocations_support_partial_and_full_invoice_settlement(
    client, pharmacist_headers, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.finance.models import ExpenseCategoryEnum, ExpenseRecord, ExpenseStatusEnum
    from backend.domains.identity.models import User
    from backend.domains.procurement.models import VendorInvoice, VendorInvoiceStatusEnum

    vendor_response = client.post(
        "/v1/api/procurement/vendors",
        headers=pharmacist_headers,
        json={
            "code": "VND-SETTLE-01",
            "name": "Settlement Supplier",
            "category": "GENERAL_SUPPLIES",
            "contact_person": "Accounts Contact",
            "phone": "9876543215",
            "email": "settlement-supplier@example.test",
            "address": "Supplier registered address",
        },
    )
    assert vendor_response.status_code == 201, vendor_response.text
    vendor_id = vendor_response.json()["id"]

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        actor_id = db.query(User.id).filter(User.email == "admin@default.com").scalar()
        expense = ExpenseRecord(
            category=ExpenseCategoryEnum.PHARMACY_STOCK,
            title="Supplier settlement test invoice",
            amount_paise=10000,
            status=ExpenseStatusEnum.APPROVED,
            approved_by_id=actor_id,
            approved_at=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=15),
            vendor_name="Settlement Supplier",
            created_by_id=actor_id,
        )
        db.add(expense)
        db.flush()
        invoice = VendorInvoice(
            vendor_id=vendor_id,
            invoice_number="SETTLEMENT-INV-001",
            invoice_date=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=15),
            subtotal_paise=10000,
            tax_amount_paise=0,
            discount_paise=0,
            total_amount_paise=10000,
            status=VendorInvoiceStatusEnum.MATCHED_APPROVED,
            verified_by_id=actor_id,
            verified_at=datetime.now(timezone.utc),
            linked_expense_id=expense.id,
            created_by_id=actor_id,
        )
        db.add(invoice)
        db.commit()
        invoice_id, expense_id = invoice.id, expense.id

    bypass = client.post(
        f"/v1/api/finance/ap/expenses/{expense_id}/mark-paid",
        headers=superuser_headers,
        params={"receipt_reference": "BYPASS-ATTEMPT"},
    )
    assert bypass.status_code == 409, bypass.text

    first_payment = client.post(
        "/v1/api/procurement/supplier-payments",
        headers=superuser_headers,
        json={
            "vendor_id": vendor_id,
            "payment_reference": "BANK-UTR-SETTLE-001",
            "payment_method": "BANK_TRANSFER",
            "payment_date": datetime.now(timezone.utc).isoformat(),
            "amount_paise": 4000,
            "allocations": [{"invoice_id": invoice_id, "amount_paise": 4000}],
        },
    )
    assert first_payment.status_code == 201, first_payment.text
    assert first_payment.json()["amount_paise"] == 4000

    settlement = client.get(
        f"/v1/api/procurement/invoices/{invoice_id}/settlement",
        headers=superuser_headers,
    )
    assert settlement.status_code == 200, settlement.text
    assert settlement.json()["amount_paid_paise"] == 4000
    assert settlement.json()["outstanding_paise"] == 6000
    assert settlement.json()["status"] == "MATCHED_APPROVED"

    with session_factory() as db:
        expense = db.get(ExpenseRecord, expense_id)
        assert expense.status == ExpenseStatusEnum.APPROVED

    second_payment = client.post(
        "/v1/api/procurement/supplier-payments",
        headers=superuser_headers,
        json={
            "vendor_id": vendor_id,
            "payment_reference": "BANK-UTR-SETTLE-002",
            "payment_method": "NEFT",
            "payment_date": datetime.now(timezone.utc).isoformat(),
            "amount_paise": 6000,
            "allocations": [{"invoice_id": invoice_id, "amount_paise": 6000}],
        },
    )
    assert second_payment.status_code == 201, second_payment.text

    final_settlement = client.get(
        f"/v1/api/procurement/invoices/{invoice_id}/settlement",
        headers=superuser_headers,
    )
    assert final_settlement.status_code == 200
    assert final_settlement.json()["amount_paid_paise"] == 10000
    assert final_settlement.json()["outstanding_paise"] == 0
    assert final_settlement.json()["status"] == "PAID"

    with session_factory() as db:
        expense = db.get(ExpenseRecord, expense_id)
        assert expense.status == ExpenseStatusEnum.PAID

    overpayment = client.post(
        "/v1/api/procurement/supplier-payments",
        headers=superuser_headers,
        json={
            "vendor_id": vendor_id,
            "payment_reference": "BANK-UTR-SETTLE-003",
            "payment_method": "UPI",
            "payment_date": datetime.now(timezone.utc).isoformat(),
            "amount_paise": 1,
            "allocations": [{"invoice_id": invoice_id, "amount_paise": 1}],
        },
    )
    assert overpayment.status_code == 409



def test_supplier_adjustments_and_advances_are_approved_allocated_and_bounded(
    client, pharmacist_headers, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.finance.models import ExpenseCategoryEnum, ExpenseRecord, ExpenseStatusEnum
    from backend.domains.identity.models import User
    from backend.domains.procurement.models import VendorInvoice, VendorInvoiceStatusEnum

    vendor_response = client.post(
        "/v1/api/procurement/vendors",
        headers=pharmacist_headers,
        json={
            "code": "VND-ADJ-ADV-01", "name": "Adjustment and Advance Supplier",
            "category": "GENERAL_SUPPLIES", "contact_person": "Accounts Contact",
            "phone": "9876543216", "email": "adjustment-advance@example.test",
            "address": "Supplier registered address",
        },
    )
    assert vendor_response.status_code == 201, vendor_response.text
    vendor_id = vendor_response.json()["id"]
    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        actor_id = db.query(User.id).filter(User.email == "admin@default.com").scalar()
        expense = ExpenseRecord(
            category=ExpenseCategoryEnum.PHARMACY_STOCK, title="Adjustment test AP",
            amount_paise=10000, status=ExpenseStatusEnum.APPROVED,
            approved_by_id=actor_id, approved_at=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=15),
            vendor_name="Adjustment and Advance Supplier", created_by_id=actor_id,
        )
        db.add(expense)
        db.flush()
        invoice = VendorInvoice(
            vendor_id=vendor_id, invoice_number="ADJ-ADV-INV-001",
            invoice_date=datetime.now(timezone.utc), due_date=datetime.now(timezone.utc) + timedelta(days=15),
            subtotal_paise=10000, tax_amount_paise=0, discount_paise=0, total_amount_paise=10000,
            status=VendorInvoiceStatusEnum.MATCHED_APPROVED, verified_by_id=actor_id,
            verified_at=datetime.now(timezone.utc), linked_expense_id=expense.id, created_by_id=actor_id,
        )
        db.add(invoice)
        db.commit()
        invoice_id = invoice.id

    note = client.post("/v1/api/procurement/supplier-adjustments", headers=pharmacist_headers, json={
        "vendor_id": vendor_id, "adjustment_type": "SUPPLIER_CREDIT_NOTE",
        "document_number": "CN-001", "document_date": datetime.now(timezone.utc).date().isoformat(),
        "amount_paise": 2000, "reason": "Supplier issued credit for damaged goods.",
    })
    assert note.status_code == 201, note.text
    note_id = note.json()["id"]
    self_approval = client.patch(
        f"/v1/api/procurement/supplier-adjustments/{note_id}/review",
        headers=pharmacist_headers, json={"approved": True, "review_notes": "Self approval"},
    )
    assert self_approval.status_code == 403
    approved = client.patch(
        f"/v1/api/procurement/supplier-adjustments/{note_id}/review",
        headers=superuser_headers, json={"approved": True, "review_notes": "Supplier credit note verified."},
    )
    assert approved.status_code == 200, approved.text
    applied = client.post(
        f"/v1/api/procurement/supplier-adjustments/{note_id}/applications",
        headers=superuser_headers, json={"invoice_id": invoice_id, "amount_paise": 2000},
    )
    assert applied.status_code == 201, applied.text

    advance = client.post("/v1/api/procurement/supplier-advances", headers=superuser_headers, json={
        "vendor_id": vendor_id, "advance_reference": "ADV-UTR-001",
        "payment_method": "NEFT", "advance_date": datetime.now(timezone.utc).isoformat(),
        "amount_paise": 3000,
    })
    assert advance.status_code == 201, advance.text
    advance_id = advance.json()["id"]
    advance_apply = client.post(
        f"/v1/api/procurement/supplier-advances/{advance_id}/applications",
        headers=superuser_headers, json={"invoice_id": invoice_id, "amount_paise": 3000},
    )
    assert advance_apply.status_code == 201, advance_apply.text

    settlement = client.get(
        f"/v1/api/procurement/invoices/{invoice_id}/settlement", headers=superuser_headers,
    )
    assert settlement.status_code == 200, settlement.text
    assert settlement.json()["credit_adjustments_paise"] == 2000
    assert settlement.json()["advances_applied_paise"] == 3000
    assert settlement.json()["outstanding_paise"] == 5000
    cash_overpayment = client.post(
        "/v1/api/procurement/supplier-payments", headers=superuser_headers,
        json={
            "vendor_id": vendor_id, "payment_reference": "PAY-AFTER-CREDIT-001",
            "payment_method": "NEFT", "payment_date": datetime.now(timezone.utc).isoformat(),
            "amount_paise": 5001, "allocations": [{"invoice_id": invoice_id, "amount_paise": 5001}],
        },
    )
    assert cash_overpayment.status_code == 409
    too_much = client.post(
        f"/v1/api/procurement/supplier-advances/{advance_id}/applications", headers=superuser_headers,
        json={"invoice_id": invoice_id, "amount_paise": 1},
    )
    assert too_much.status_code == 404


def test_supplier_bank_statement_import_suggestions_and_partial_reconciliation(
    client, pharmacist_headers, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.finance.models import ExpenseCategoryEnum, ExpenseRecord, ExpenseStatusEnum
    from backend.domains.identity.models import User
    from backend.domains.procurement.models import VendorInvoice, VendorInvoiceStatusEnum

    vendor_response = client.post(
        "/v1/api/procurement/vendors",
        headers=pharmacist_headers,
        json={
            "code": "VND-BANK-REC-01", "name": "Bank Reconciliation Supplier",
            "category": "GENERAL_SUPPLIES", "contact_person": "Accounts Contact",
            "phone": "9876543217", "email": "bank-recon@example.test",
            "address": "Supplier registered address",
        },
    )
    assert vendor_response.status_code == 201, vendor_response.text
    vendor_id = vendor_response.json()["id"]

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        actor_id = db.query(User.id).filter(User.email == "admin@default.com").scalar()
        expense = ExpenseRecord(
            category=ExpenseCategoryEnum.PHARMACY_STOCK, title="Bank reconciliation AP",
            amount_paise=10000, status=ExpenseStatusEnum.APPROVED,
            approved_by_id=actor_id, approved_at=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc) + timedelta(days=15),
            vendor_name="Bank Reconciliation Supplier", created_by_id=actor_id,
        )
        db.add(expense)
        db.flush()
        invoice = VendorInvoice(
            vendor_id=vendor_id, invoice_number="BANK-REC-INV-001",
            invoice_date=datetime.now(timezone.utc), due_date=datetime.now(timezone.utc) + timedelta(days=15),
            subtotal_paise=10000, tax_amount_paise=0, discount_paise=0, total_amount_paise=10000,
            status=VendorInvoiceStatusEnum.MATCHED_APPROVED, verified_by_id=actor_id,
            verified_at=datetime.now(timezone.utc), linked_expense_id=expense.id, created_by_id=actor_id,
        )
        db.add(invoice)
        db.commit()
        invoice_id = invoice.id

    payment_reference = "UTR-BANK-RECON-001"
    payment_date = datetime.now(timezone.utc)
    payment = client.post("/v1/api/procurement/supplier-payments", headers=superuser_headers, json={
        "vendor_id": vendor_id, "payment_reference": payment_reference,
        "payment_method": "NEFT", "payment_date": payment_date.isoformat(),
        "amount_paise": 6000, "allocations": [{"invoice_id": invoice_id, "amount_paise": 6000}],
    })
    assert payment.status_code == 201, payment.text
    payment_id = payment.json()["id"]

    statement_payload = {
        "bank_account_ref": "OPERATING-ACCOUNT-01",
        "statement_reference": "STMT-BANK-REC-001",
        "period_start": payment_date.date().isoformat(),
        "period_end": payment_date.date().isoformat(),
        "opening_balance_paise": 100000,
        "closing_balance_paise": 94000,
        "lines": [{
            "bank_transaction_id": "BANK-TXN-0001",
            "transaction_date": payment_date.isoformat(),
            "direction": "DEBIT", "amount_paise": 6000,
            "bank_reference": payment_reference, "description": "Supplier NEFT transfer",
        }],
    }
    imported = client.post(
        "/v1/api/procurement/bank-statements/import",
        headers=superuser_headers, json=statement_payload,
    )
    assert imported.status_code == 201, imported.text
    batch_id = imported.json()["id"]

    duplicate_statement = client.post(
        "/v1/api/procurement/bank-statements/import",
        headers=superuser_headers, json=statement_payload,
    )
    assert duplicate_statement.status_code == 409

    suggestions = client.get(
        f"/v1/api/procurement/bank-statements/{batch_id}/suggestions",
        headers=superuser_headers,
    )
    assert suggestions.status_code == 200, suggestions.text
    candidate = suggestions.json()[0]["candidates"][0]
    assert candidate["payment_id"] == payment_id
    assert candidate["reference_match"] is True

    matched = client.post(
        "/v1/api/procurement/bank-statements/lines/{}/matches".format(
            client.get(f"/v1/api/procurement/bank-statements/{batch_id}/lines", headers=superuser_headers).json()[0]["id"]
        ),
        headers=superuser_headers,
        json={"payment_id": payment_id, "amount_paise": 4000},
    )
    assert matched.status_code == 201, matched.text
    assert matched.json()["statement_line_status"] == "PARTIALLY_MATCHED"

    reconciliation = client.get(
        "/v1/api/procurement/supplier-payments/reconciliation",
        headers=superuser_headers,
    )
    assert reconciliation.status_code == 200, reconciliation.text
    payment_row = next(row for row in reconciliation.json()["supplier_payments"] if row["payment_id"] == payment_id)
    assert payment_row["matched_amount_paise"] == 4000
    assert payment_row["unreconciled_amount_paise"] == 2000

    overmatch = client.post(
        "/v1/api/procurement/bank-statements/lines/{}/matches".format(
            client.get(f"/v1/api/procurement/bank-statements/{batch_id}/lines", headers=superuser_headers).json()[0]["id"]
        ),
        headers=superuser_headers,
        json={"payment_id": payment_id, "amount_paise": 2001},
    )
    assert overmatch.status_code == 409

    final_match = client.post(
        "/v1/api/procurement/bank-statements/lines/{}/matches".format(
            client.get(f"/v1/api/procurement/bank-statements/{batch_id}/lines", headers=superuser_headers).json()[0]["id"]
        ),
        headers=superuser_headers,
        json={"payment_id": payment_id, "amount_paise": 2000},
    )
    assert final_match.status_code == 201, final_match.text
    assert final_match.json()["statement_line_status"] == "MATCHED"


def test_supplier_payment_priorities_use_net_outstanding_and_due_dates(
    client, pharmacist_headers, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.finance.models import ExpenseCategoryEnum, ExpenseRecord, ExpenseStatusEnum
    from backend.domains.identity.models import User
    from backend.domains.procurement.models import VendorInvoice, VendorInvoiceStatusEnum

    vendor_response = client.post(
        "/v1/api/procurement/vendors",
        headers=pharmacist_headers,
        json={
            "code": "VND-PAY-PRIORITY-01",
            "name": "Payment Priority Supplier",
            "category": "GENERAL_SUPPLIES",
            "contact_person": "Accounts Contact",
            "phone": "9876543218",
            "email": "payment-priority@example.test",
            "address": "Supplier registered address",
        },
    )
    assert vendor_response.status_code == 201, vendor_response.text
    vendor_id = vendor_response.json()["id"]

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        actor_id = db.query(User.id).filter(User.email == "admin@default.com").scalar()
        expense = ExpenseRecord(
            category=ExpenseCategoryEnum.OTHER,
            title="Overdue supplier AP priority test",
            amount_paise=10000,
            status=ExpenseStatusEnum.APPROVED,
            approved_by_id=actor_id,
            approved_at=now,
            due_date=now - timedelta(days=2),
            vendor_name="Payment Priority Supplier",
            created_by_id=actor_id,
        )
        db.add(expense)
        db.flush()
        invoice = VendorInvoice(
            vendor_id=vendor_id,
            invoice_number="PAY-PRIORITY-INV-001",
            invoice_date=now - timedelta(days=30),
            due_date=now - timedelta(days=2),
            subtotal_paise=10000,
            tax_amount_paise=0,
            discount_paise=0,
            total_amount_paise=10000,
            status=VendorInvoiceStatusEnum.MATCHED_APPROVED,
            verified_by_id=actor_id,
            verified_at=now,
            linked_expense_id=expense.id,
            created_by_id=actor_id,
        )
        db.add(invoice)
        db.commit()
        invoice_id = invoice.id

    response = client.get(
        "/v1/api/procurement/analytics/payment-priorities",
        headers=superuser_headers,
        params={"due_within_days": 30, "vendor_id": vendor_id},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["totals"]["invoice_count"] == 1
    assert payload["totals"]["overdue_count"] == 1
    assert payload["totals"]["overdue_paise"] == 10000
    assert payload["invoices"][0]["invoice_id"] == invoice_id
    assert payload["invoices"][0]["priority"] == "OVERDUE"
    assert payload["invoices"][0]["outstanding_paise"] == 10000


def test_supplier_payment_request_reserves_invoice_and_requires_independent_approval(
    client, pharmacist_headers, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.finance.models import ExpenseCategoryEnum, ExpenseRecord, ExpenseStatusEnum
    from backend.domains.identity.models import User
    from backend.domains.procurement.models import VendorInvoice, VendorInvoiceStatusEnum

    vendor_response = client.post(
        "/v1/api/procurement/vendors",
        headers=pharmacist_headers,
        json={
            "code": "VND-PAY-REQUEST-01",
            "name": "Payment Request Supplier",
            "category": "GENERAL_SUPPLIES",
            "contact_person": "Accounts Contact",
            "phone": "9876543217",
            "email": "payment-request@example.test",
            "address": "Supplier registered address",
        },
    )
    assert vendor_response.status_code == 201, vendor_response.text
    vendor_id = vendor_response.json()["id"]

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        actor_id = db.query(User.id).filter(User.email == "admin@default.com").scalar()
        expense = ExpenseRecord(
            category=ExpenseCategoryEnum.PHARMACY_STOCK,
            title="Supplier payment request AP",
            amount_paise=10000,
            status=ExpenseStatusEnum.APPROVED,
            approved_by_id=actor_id,
            approved_at=now,
            due_date=now + timedelta(days=5),
            vendor_name="Payment Request Supplier",
            created_by_id=actor_id,
        )
        db.add(expense)
        db.flush()
        invoice = VendorInvoice(
            vendor_id=vendor_id,
            invoice_number="PAY-REQUEST-INV-001",
            invoice_date=now,
            due_date=now + timedelta(days=5),
            subtotal_paise=10000,
            tax_amount_paise=0,
            discount_paise=0,
            total_amount_paise=10000,
            status=VendorInvoiceStatusEnum.MATCHED_APPROVED,
            verified_by_id=actor_id,
            verified_at=now,
            linked_expense_id=expense.id,
            created_by_id=actor_id,
        )
        db.add(invoice)
        db.commit()
        invoice_id = invoice.id

    request_payload = {
        "vendor_id": vendor_id,
        "payment_reference": "PAY-REQUEST-UTR-001",
        "payment_method": "NEFT",
        "scheduled_date": now.date().isoformat(),
        "payment_run_reference": "NOV-2026-RUN-01",
        "amount_paise": 7000,
        "allocations": [{"invoice_id": invoice_id, "amount_paise": 7000}],
    }
    created = client.post(
        "/v1/api/procurement/supplier-payment-requests",
        headers=superuser_headers,
        json=request_payload,
    )
    assert created.status_code == 201, created.text
    request_id = created.json()["id"]
    assert created.json()["status"] == "PENDING"

    over_reserved = client.post(
        "/v1/api/procurement/supplier-payment-requests",
        headers=superuser_headers,
        json={
            **request_payload,
            "payment_reference": "PAY-REQUEST-UTR-002",
            "amount_paise": 4000,
            "allocations": [{"invoice_id": invoice_id, "amount_paise": 4000}],
        },
    )
    assert over_reserved.status_code == 409, over_reserved.text

    self_approval = client.patch(
        f"/v1/api/procurement/supplier-payment-requests/{request_id}/review",
        headers=superuser_headers,
        json={"approved": True, "review_notes": "Attempted self approval"},
    )
    assert self_approval.status_code == 403, self_approval.text

    cancelled = client.post(
        f"/v1/api/procurement/supplier-payment-requests/{request_id}/cancel",
        headers=superuser_headers,
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED"

    replacement = client.post(
        "/v1/api/procurement/supplier-payment-requests",
        headers=superuser_headers,
        json={
            **request_payload,
            "payment_reference": "PAY-REQUEST-UTR-003",
            "amount_paise": 10000,
            "allocations": [{"invoice_id": invoice_id, "amount_paise": 10000}],
        },
    )
    assert replacement.status_code == 201, replacement.text

    listed = client.get(
        "/v1/api/procurement/supplier-payment-requests",
        headers=superuser_headers,
        params={"status": "PENDING", "payment_run_reference": "NOV-2026-RUN-01"},
    )
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == replacement.json()["id"]


def test_procurement_cash_flow_forecast_separates_ap_from_po_commitments(
    client, superuser_headers
):
    response = client.get(
        "/v1/api/procurement/analytics/cash-flow-forecast",
        headers=superuser_headers,
        params={"horizon_days": 90},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["horizon_days"] == 90
    assert payload["currency_unit"] == "INR paise"
    assert len(payload["forecast_buckets"]) == 4
    assert "projected_ap_cash_need_in_horizon_paise" in payload["cash_position"]
    assert payload["purchase_order_commitments"]["cash_forecast_included"] is False
    assert payload["supplier_advances"]["cash_outflow_included_in_forecast"] is False
    assert payload["methodology"]["no_double_counting"]

    projected = sum(
        row["projected_ap_cash_need_paise"]
        for row in payload["forecast_buckets"]
    )
    assert projected == payload["cash_position"]["projected_ap_cash_need_in_horizon_paise"]

    invalid = client.get(
        "/v1/api/procurement/analytics/cash-flow-forecast",
        headers=superuser_headers,
        params={"horizon_days": 3},
    )
    assert invalid.status_code == 422, invalid.text


def test_procurement_reconciliation_exception_worklist_is_read_only_and_filterable(
    client, superuser_headers
):
    response = client.get(
        "/v1/api/procurement/reconciliation/exceptions",
        headers=superuser_headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "summary" in payload
    assert "exceptions" in payload
    assert payload["controls"]["read_only"] is True
    assert "POSSIBLE_DUPLICATE_SUPPLIER_PAYMENT" in payload["controls"]["duplicate_payment_detection"]
    assert payload["summary"]["total_exceptions"] == len(payload["exceptions"])
    assert payload["summary"]["total_exceptions"] == sum(
        payload["summary"]["by_type"].values()
    )
    for item in payload["exceptions"]:
        assert item["exception_type"]
        assert item["severity"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
        assert item["reference_type"]
        assert item["reference_id"] > 0

    filtered = client.get(
        "/v1/api/procurement/reconciliation/exceptions",
        headers=superuser_headers,
        params={"from_date": "2026-11-01", "to_date": "2026-11-06", "overdue_days": 7},
    )
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["filters"]["overdue_days"] == 7

    invalid = client.get(
        "/v1/api/procurement/reconciliation/exceptions",
        headers=superuser_headers,
        params={"from_date": "2026-11-07", "to_date": "2026-11-01"},
    )
    assert invalid.status_code == 422, invalid.text


def test_persisted_reconciliation_exception_assignment_resolution_and_history(
    client, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.identity.models import User
    from backend.domains.procurement.models import ProcurementReconciliationException

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        actor_id = db.query(User.id).filter(User.email == "admin@default.com").scalar()
        row = ProcurementReconciliationException(
            fingerprint="TEST_EXCEPTION:BANK_STATEMENT_LINE:987654",
            exception_type="UNMATCHED_BANK_DEBIT", severity="MEDIUM", status="OPEN",
            reference_type="BANK_STATEMENT_LINE", reference_id=987654,
            amount_paise=5000, matched_amount_paise=0, unmatched_amount_paise=5000,
            summary="Test unmatched bank debit.",
            detection_snapshot={"bank_transaction_id": "TEST-987654"},
        )
        db.add(row)
        db.commit()
        exception_id = row.id

    refresh = client.post(
        "/v1/api/procurement/reconciliation/exceptions/refresh",
        headers=superuser_headers,
    )
    assert refresh.status_code == 200, refresh.text
    assert refresh.json()["marked_missing"] >= 1

    assigned = client.patch(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/assignment",
        headers=superuser_headers, json={"assigned_to_id": actor_id, "note": "Assigned for finance review."},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["assigned_to_id"] == actor_id

    reviewing = client.patch(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/status",
        headers=superuser_headers, json={"status": "IN_REVIEW", "note": "Investigation started."},
    )
    assert reviewing.status_code == 200, reviewing.text

    missing_resolution_note = client.patch(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/status",
        headers=superuser_headers, json={"status": "RESOLVED"},
    )
    assert missing_resolution_note.status_code == 422

    incomplete_checklist = client.patch(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/status",
        headers=superuser_headers,
        json={
            "status": "RESOLVED",
            "note": "Bank advice checked but the checklist is incomplete.",
            "root_cause_code": "REFERENCE_MISMATCH",
            "resolution_checklist": {"bank_statement_verified": True},
        },
    )
    assert incomplete_checklist.status_code == 422, incomplete_checklist.text

    resolved = client.patch(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/status",
        headers=superuser_headers,
        json={
            "status": "RESOLVED",
            "note": "Bank advice verified and reconciliation evidence attached.",
            "root_cause_code": "REFERENCE_MISMATCH",
            "resolution_checklist": {
                "bank_statement_verified": True,
                "bank_account_and_period_confirmed": True,
                "payment_or_expense_traced": True,
                "supporting_evidence_reviewed": True,
            },
        },
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "RESOLVED"

    reopen = client.patch(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/status",
        headers=superuser_headers, json={"status": "OPEN", "note": "Reopen"},
    )
    assert reopen.status_code == 409

    reopened = client.post(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/reopen",
        headers=superuser_headers,
        json={"reason": "New bank statement evidence contradicts the earlier closure."},
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status"] == "OPEN"
    assert reopened.json()["reopen_count"] == 1

    history = client.get(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/history",
        headers=superuser_headers,
    )
    assert history.status_code == 200, history.text
    event_types = [event["event_type"] for event in history.json()["events"]]
    assert "ASSIGNED" in event_types
    assert "STATUS_CHANGED" in event_types
    assert "REOPENED" in event_types
    assert len(history.json()["events"]) >= 4

    queue = client.get(
        "/v1/api/procurement/reconciliation/exceptions/queue",
        headers=superuser_headers, params={"status": "OPEN", "severity": "MEDIUM", "source_present": "false"},
    )
    assert queue.status_code == 200, queue.text
    assert any(item["id"] == exception_id and item["source_present"] is False for item in queue.json()["exceptions"])
    assert "sla_overdue" in queue.json()["sla_summary"]



def test_high_risk_reconciliation_resolution_requires_independent_review(
    client, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.identity.models import User, UserRole, UserStatusEnum
    from backend.domains.procurement.models import ProcurementReconciliationException
    from conftest import _mint_test_headers

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        admin = db.query(User).filter(User.email == "admin@default.com").one()
        reviewer = User(
            login_id="recon-independent-reviewer",
            email="recon-independent-reviewer@default.com",
            hashed_password="not-a-login-credential",
            full_name="Independent Finance Reviewer",
            status=UserStatusEnum.ACTIVE,
            is_superuser=True,
        )
        db.add(reviewer)
        db.flush()
        for role_id, in db.query(UserRole.role_id).filter(UserRole.user_id == admin.id).all():
            db.add(UserRole(user_id=reviewer.id, role_id=role_id))
        db.commit()
        reviewer_email = reviewer.email
        row = ProcurementReconciliationException(
            fingerprint="TEST_EXCEPTION:HIGH_RISK_REVIEW:987699",
            exception_type="UNMATCHED_BANK_DEBIT", severity="HIGH", status="IN_REVIEW",
            reference_type="BANK_STATEMENT_LINE", reference_id=987699,
            amount_paise=5000, matched_amount_paise=0, unmatched_amount_paise=5000,
            summary="High-risk resolution review test.",
            detection_snapshot={},
        )
        db.add(row)
        db.commit()
        exception_id = row.id

    guidance = client.get(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/resolution-guidance",
        headers=superuser_headers,
    )
    assert guidance.status_code == 200, guidance.text
    assert guidance.json()["independent_review_required"] is True

    submitted = client.patch(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/status",
        headers=superuser_headers,
        json={
            "status": "RESOLVED",
            "note": "Supporting bank evidence has been checked and documented.",
            "root_cause_code": "REFERENCE_MISMATCH",
            "resolution_checklist": {
                "bank_statement_verified": True,
                "bank_account_and_period_confirmed": True,
                "payment_or_expense_traced": True,
                "supporting_evidence_reviewed": True,
            },
        },
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "IN_REVIEW"
    assert submitted.json()["resolution_review_status"] == "PENDING"

    self_review = client.patch(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/resolution-review",
        headers=superuser_headers,
        json={"decision": "APPROVE", "note": "Reviewed and approved independently."},
    )
    assert self_review.status_code == 409, self_review.text

    reviewer_headers = _mint_test_headers(
        multi_tenant_env, "default", reviewer_email,
        multi_tenant_env["tenant_keys"]["default"]["jwt"], "HQ-HYD-01",
    )
    approved = client.patch(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/resolution-review",
        headers=reviewer_headers,
        json={"decision": "APPROVE", "note": "Independent review confirms evidence and conclusion."},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "RESOLVED"
    assert approved.json()["resolution_review_status"] == "APPROVED"


def test_reconciliation_evidence_upload_download_and_audit(
    client, superuser_headers, multi_tenant_env, monkeypatch
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.procurement import documents as procurement_documents
    from backend.domains.procurement.models import (
        ProcurementReconciliationException,
        ProcurementReconciliationEvidence,
        ProcurementReconciliationEvidenceDownloadAudit,
        ProcurementReconciliationExceptionEvent,
    )

    monkeypatch.setattr(procurement_documents, "scan_file_with_clamav", lambda _path: None)
    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        row = ProcurementReconciliationException(
            fingerprint="TEST_EXCEPTION:EVIDENCE_UPLOAD:987688",
            exception_type="UNMATCHED_BANK_DEBIT", severity="HIGH", status="IN_REVIEW",
            reference_type="BANK_STATEMENT_LINE", reference_id=987688,
            amount_paise=12000, matched_amount_paise=0, unmatched_amount_paise=12000,
            summary="Evidence attachment lifecycle test.",
            detection_snapshot={},
        )
        db.add(row)
        db.commit()
        exception_id = row.id

    uploaded = client.post(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/evidence",
        headers=superuser_headers,
        data={
            "evidence_type": "BANK_STATEMENT",
            "description": "Relevant bank statement extract for the debit.",
        },
        files={"file": ("statement.pdf", b"%PDF-1.7 evidence bytes", "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text
    body = uploaded.json()
    evidence_id = body["id"]
    assert body["exception_id"] == exception_id
    assert body["evidence_type"] == "BANK_STATEMENT"
    assert body["sha256_hex"]
    assert body["size_bytes"] == len(b"%PDF-1.7 evidence bytes")

    listed = client.get(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/evidence",
        headers=superuser_headers,
    )
    assert listed.status_code == 200, listed.text
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == evidence_id

    mismatch = client.get(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id + 1}/evidence/{evidence_id}/download",
        headers=superuser_headers,
    )
    assert mismatch.status_code == 404

    downloaded = client.get(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/evidence/{evidence_id}/download",
        headers=superuser_headers,
    )
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == b"%PDF-1.7 evidence bytes"
    assert downloaded.headers["cache-control"] == "private, no-store"
    assert downloaded.headers["x-content-type-options"] == "nosniff"

    with session_factory() as db:
        evidence = db.query(ProcurementReconciliationEvidence).filter(
            ProcurementReconciliationEvidence.id == evidence_id
        ).one()
        audits = db.query(ProcurementReconciliationEvidenceDownloadAudit).filter(
            ProcurementReconciliationEvidenceDownloadAudit.evidence_id == evidence_id
        ).all()
        event = db.query(ProcurementReconciliationExceptionEvent).filter(
            ProcurementReconciliationExceptionEvent.exception_id == exception_id,
            ProcurementReconciliationExceptionEvent.event_type == "EVIDENCE_ATTACHED",
        ).one()
        assert evidence.storage_key.startswith("default/procurement-reconciliation-evidence/")
        assert len(audits) == 1
        assert audits[0].actor_email
        assert event.event_metadata["evidence_id"] == evidence_id
        stored_path = procurement_documents.resolve_reconciliation_evidence("default", evidence.storage_key)
        stored_path.write_bytes(b"%PDF-1.7 tampered evidence")

    tampered_download = client.get(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/evidence/{evidence_id}/download",
        headers=superuser_headers,
    )
    assert tampered_download.status_code == 409, tampered_download.text
    with session_factory() as db:
        mismatch_event = db.query(ProcurementReconciliationExceptionEvent).filter(
            ProcurementReconciliationExceptionEvent.exception_id == exception_id,
            ProcurementReconciliationExceptionEvent.event_type == "EVIDENCE_HASH_MISMATCH",
        ).one()
        assert mismatch_event.event_metadata["evidence_id"] == evidence_id




def test_reconciliation_audit_export_contains_history_evidence_manifest_and_export_event(
    client, superuser_headers, multi_tenant_env, monkeypatch
):
    import io
    import json
    import zipfile
    from sqlalchemy.orm import sessionmaker
    from backend.domains.procurement import documents as procurement_documents
    from backend.domains.procurement.models import (
        ProcurementReconciliationException,
        ProcurementReconciliationExceptionEvent,
        ProcurementReconciliationEvidence,
    )

    monkeypatch.setattr(procurement_documents, "scan_file_with_clamav", lambda _path: None)
    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        row = ProcurementReconciliationException(
            fingerprint="TEST_EXCEPTION:AUDIT_EXPORT:987685",
            exception_type="UNMATCHED_BANK_DEBIT", severity="HIGH", status="IN_REVIEW",
            reference_type="BANK_STATEMENT_LINE", reference_id=987685,
            amount_paise=18000, matched_amount_paise=4000, unmatched_amount_paise=14000,
            summary="Audit export package regression test.",
            detection_snapshot={"bank_reference": "UTR-EXPORT-001"},
        )
        db.add(row)
        db.commit()
        exception_id = row.id

    evidence_bytes = b"%PDF-1.7 audit export evidence"
    uploaded = client.post(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/evidence",
        headers=superuser_headers,
        data={"evidence_type": "BANK_STATEMENT", "description": "Source bank entry."},
        files={"file": ("bank-entry.pdf", evidence_bytes, "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text

    evidence_download = client.get(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/evidence/{uploaded.json()['id']}/download",
        headers=superuser_headers,
    )
    assert evidence_download.status_code == 200, evidence_download.text

    response = client.get(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/audit-export",
        headers=superuser_headers,
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/zip")
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-audit-manifest-sha256"]

    with zipfile.ZipFile(io.BytesIO(response.content)) as package:
        names = set(package.namelist())
        assert {"investigation.json", "history.json", "manifest.json", "evidence-download-audit.json"} <= names
        evidence_name = next(name for name in names if name.startswith("evidence/"))
        assert package.read(evidence_name) == evidence_bytes
        investigation = json.loads(package.read("investigation.json"))
        assert investigation["exception"]["id"] == exception_id
        assert investigation["exception"]["status"] == "IN_REVIEW"
        assert investigation["evidence"][0]["sha256"] == uploaded.json()["sha256_hex"]
        download_audit = json.loads(package.read("evidence-download-audit.json"))
        assert len(download_audit["downloads"]) == 1
        assert download_audit["downloads"][0]["actor_email"]
        manifest = json.loads(package.read("manifest.json"))
        assert manifest["exception_id"] == exception_id
        assert any(item["path"] == evidence_name for item in manifest["files"])
        assert any(item["path"] == "evidence-download-audit.json" for item in manifest["files"])
        history = json.loads(package.read("history.json"))
        assert any(event["event_type"] == "AUDIT_EXPORT_GENERATED" for event in history["events"])

    with session_factory() as db:
        row = db.get(ProcurementReconciliationException, exception_id)
        event = db.query(ProcurementReconciliationExceptionEvent).filter(
            ProcurementReconciliationExceptionEvent.exception_id == exception_id,
            ProcurementReconciliationExceptionEvent.event_type == "AUDIT_EXPORT_GENERATED",
        ).one()
        assert row.status == "IN_REVIEW"
        assert event.event_metadata["manifest_sha256"] == response.headers["x-audit-manifest-sha256"]
        assert event.event_metadata["evidence_count"] == 1
        evidence_row = db.query(ProcurementReconciliationEvidence).filter(
            ProcurementReconciliationEvidence.exception_id == exception_id
        ).one()
        stored_path = procurement_documents.resolve_reconciliation_evidence("default", evidence_row.storage_key)
        stored_path.write_bytes(b"%PDF-1.7 modified after upload")

    tampered_export = client.get(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/audit-export",
        headers=superuser_headers,
    )
    assert tampered_export.status_code == 409, tampered_export.text
    with session_factory() as db:
        mismatch = db.query(ProcurementReconciliationExceptionEvent).filter(
            ProcurementReconciliationExceptionEvent.exception_id == exception_id,
            ProcurementReconciliationExceptionEvent.event_type == "EVIDENCE_HASH_MISMATCH",
        ).one()
        assert mismatch.event_metadata["evidence_id"] == evidence_row.id


def test_reconciliation_evidence_fails_closed_when_malware_scanner_is_unavailable(
    client, superuser_headers, multi_tenant_env, monkeypatch
):
    from fastapi import HTTPException
    from sqlalchemy.orm import sessionmaker
    from backend.domains.procurement import documents as procurement_documents
    from backend.domains.procurement.models import (
        ProcurementReconciliationException,
        ProcurementReconciliationEvidence,
    )

    def scanner_unavailable(_path):
        raise HTTPException(status_code=503, detail="Scanner unavailable.")

    monkeypatch.setattr(procurement_documents, "scan_file_with_clamav", scanner_unavailable)
    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        row = ProcurementReconciliationException(
            fingerprint="TEST_EXCEPTION:EVIDENCE_SCANNER_DOWN:987686",
            exception_type="UNMATCHED_BANK_DEBIT", severity="HIGH", status="IN_REVIEW",
            reference_type="BANK_STATEMENT_LINE", reference_id=987686,
            amount_paise=5000, matched_amount_paise=0, unmatched_amount_paise=5000,
            summary="Scanner failure test.",
            detection_snapshot={},
        )
        db.add(row)
        db.commit()
        exception_id = row.id

    response = client.post(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/evidence",
        headers=superuser_headers,
        data={"evidence_type": "BANK_STATEMENT"},
        files={"file": ("statement.pdf", b"%PDF-1.7 evidence bytes", "application/pdf")},
    )
    assert response.status_code == 503, response.text
    with session_factory() as db:
        assert db.query(ProcurementReconciliationEvidence).filter(
            ProcurementReconciliationEvidence.exception_id == exception_id
        ).count() == 0


def test_reconciliation_evidence_rejects_invalid_signature_and_closed_case(
    client, superuser_headers, multi_tenant_env, monkeypatch
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.procurement import documents as procurement_documents
    from backend.domains.procurement.models import ProcurementReconciliationException

    monkeypatch.setattr(procurement_documents, "scan_file_with_clamav", lambda _path: None)
    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        row = ProcurementReconciliationException(
            fingerprint="TEST_EXCEPTION:EVIDENCE_GUARD:987687",
            exception_type="UNMATCHED_BANK_DEBIT", severity="MEDIUM", status="OPEN",
            reference_type="BANK_STATEMENT_LINE", reference_id=987687,
            amount_paise=1000, matched_amount_paise=0, unmatched_amount_paise=1000,
            summary="Evidence validation test.",
            detection_snapshot={},
        )
        db.add(row)
        db.commit()
        exception_id = row.id

    invalid = client.post(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/evidence",
        headers=superuser_headers,
        data={"evidence_type": "BANK_STATEMENT"},
        files={"file": ("statement.pdf", b"not a PDF", "application/pdf")},
    )
    assert invalid.status_code == 415

    with session_factory() as db:
        row = db.get(ProcurementReconciliationException, exception_id)
        row.status = "RESOLVED"
        db.commit()

    closed = client.post(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/evidence",
        headers=superuser_headers,
        data={"evidence_type": "BANK_STATEMENT"},
        files={"file": ("statement.pdf", b"%PDF-1.7 evidence bytes", "application/pdf")},
    )
    assert closed.status_code == 409


def test_reconciliation_assignee_directory_is_branch_scoped_and_active_only(
    client, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.identity.models import User, UserStatusEnum
    from backend.domains.procurement.models import ProcurementReconciliationException

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        admin = db.query(User).filter(User.email == "admin@default.com").one()
        suspended = User(
            login_id="recon-suspended",
            email="recon-suspended@default.com",
            hashed_password="not-a-login-credential",
            full_name="Suspended Finance Candidate",
            status=UserStatusEnum.SUSPENDED,
        )
        exception = ProcurementReconciliationException(
            fingerprint="TEST_EXCEPTION:ASSIGNEE_DIRECTORY:987655",
            exception_type="UNMATCHED_BANK_DEBIT", severity="HIGH", status="OPEN",
            reference_type="BANK_STATEMENT_LINE", reference_id=987655,
            amount_paise=2500, matched_amount_paise=0, unmatched_amount_paise=2500,
            summary="Assignee directory test exception.",
            detection_snapshot={},
        )
        db.add_all([suspended, exception])
        db.commit()
        admin_id, suspended_id, exception_id = admin.id, suspended.id, exception.id

    directory = client.get(
        "/v1/api/procurement/reconciliation/assignees",
        headers=superuser_headers,
        params={"q": "admin", "limit": 20},
    )
    assert directory.status_code == 200, directory.text
    assert any(item["id"] == admin_id for item in directory.json()["items"])
    assert all(item["id"] != suspended_id for item in directory.json()["items"])
    assert all("roles" in item for item in directory.json()["items"])

    inactive_assignment = client.patch(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/assignment",
        headers=superuser_headers,
        json={"assigned_to_id": suspended_id},
    )
    assert inactive_assignment.status_code == 422, inactive_assignment.text


def test_procurement_reconciliation_dashboard_aggregates_without_double_counting(
    client, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.identity.models import User
    from backend.domains.procurement.models import ProcurementReconciliationException

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        actor_id = db.query(User.id).filter(User.email == "admin@default.com").scalar()
        open_debit = ProcurementReconciliationException(
            fingerprint="DASHBOARD:UNMATCHED_BANK_DEBIT:10001",
            exception_type="UNMATCHED_BANK_DEBIT", severity="HIGH", status="OPEN",
            reference_type="BANK_STATEMENT_LINE", reference_id=10001,
            amount_paise=9000, matched_amount_paise=2000, unmatched_amount_paise=7000,
            assigned_to_id=actor_id,
            summary="Unmatched debit dashboard test.",
            detection_snapshot={"bank_account_ref": "TEST-ACCOUNT"},
            first_detected_at=now - timedelta(days=2), last_detected_at=now - timedelta(days=1),
        )
        supplier_payment = ProcurementReconciliationException(
            fingerprint="DASHBOARD:UNRECONCILED_SUPPLIER_PAYMENT:10005",
            exception_type="UNRECONCILED_SUPPLIER_PAYMENT", severity="HIGH", status="IN_REVIEW",
            reference_type="SUPPLIER_PAYMENT", reference_id=10005,
            amount_paise=12000, matched_amount_paise=2000, unmatched_amount_paise=10000,
            assigned_to_id=actor_id,
            summary="Unreconciled supplier payment dashboard test.",
            detection_snapshot={"vendor_id": 501, "vendor_name": "Dashboard Test Supplier"},
        )
        duplicate_candidate = ProcurementReconciliationException(
            fingerprint="DASHBOARD:POSSIBLE_DUPLICATE_SUPPLIER_PAYMENT:10002",
            exception_type="POSSIBLE_DUPLICATE_SUPPLIER_PAYMENT", severity="HIGH", status="OPEN",
            reference_type="SUPPLIER_PAYMENT", reference_id=10002,
            amount_paise=9000, matched_amount_paise=9000, unmatched_amount_paise=0,
            summary="Possible duplicate is not a confirmed loss.",
            detection_snapshot={"candidate_payment_ids": [10002, 10003]},
        )
        resolved = ProcurementReconciliationException(
            fingerprint="DASHBOARD:UNCLASSIFIED_BANK_CREDIT:10004",
            exception_type="UNCLASSIFIED_BANK_CREDIT", severity="LOW", status="RESOLVED",
            reference_type="BANK_STATEMENT_LINE", reference_id=10004,
            amount_paise=5000, matched_amount_paise=0, unmatched_amount_paise=5000,
            summary="Resolved credit classification dashboard test.",
            detection_snapshot={},
            first_detected_at=now - timedelta(days=3), last_detected_at=now - timedelta(days=2),
            resolved_at=now - timedelta(days=1), resolved_by_id=actor_id,
        )
        db.add_all([open_debit, supplier_payment, duplicate_candidate, resolved])
        db.commit()

    response = client.get(
        "/v1/api/procurement/analytics/reconciliation-dashboard",
        headers=superuser_headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["controls"]["read_only"] is True
    assert payload["overview"]["open_count"] >= 2
    assert payload["overview"]["resolved_count"] >= 1
    assert payload["sla_breaches_by_severity"]["HIGH"] >= 1
    assigned_workload = next(row for row in payload["finance_workload"] if row["user_id"] == actor_id)
    assert assigned_workload["assigned_open"] >= 2
    assert assigned_workload["assigned_sla_overdue"] >= 1
    assert assigned_workload["oldest_open_age_hours"] >= 48
    assert assigned_workload["open_by_severity"]["HIGH"] >= 2
    debit = payload["investigation_amounts_by_exception_type"]["UNMATCHED_BANK_DEBIT"]
    assert debit["investigation_amount_paise"] == 9000
    assert debit["unmatched_amount_paise"] == 7000
    assert payload["investigation_amounts_by_bank_account"][0]["bank_account_ref"] == "TEST-ACCOUNT"
    supplier = payload["investigation_amounts_by_supplier"][0]
    assert supplier["vendor_id"] == 501
    assert supplier["unmatched_amount_paise"] == 10000
    assert "POSSIBLE_DUPLICATE_SUPPLIER_PAYMENT" not in payload["investigation_amounts_by_exception_type"]
    assert payload["resolution_performance"]["median_resolution_hours"] is not None
    assert any(row["opened_count"] >= 1 for row in payload["daily_trend"])

    overdue_unassigned = client.get(
        "/v1/api/procurement/reconciliation/exceptions/queue",
        headers=superuser_headers,
        params={"sla_overdue": "true", "unassigned_only": "true"},
    )
    assert overdue_unassigned.status_code == 200, overdue_unassigned.text
    assert any(item["reference_id"] == 10001 for item in overdue_unassigned.json()["exceptions"])

    open_worklist = client.get(
        "/v1/api/procurement/reconciliation/exceptions/queue",
        headers=superuser_headers,
        params={"open_only": "true"},
    )
    assert open_worklist.status_code == 200, open_worklist.text
    assert any(item["reference_id"] == 10005 and item["status"] == "IN_REVIEW" for item in open_worklist.json()["exceptions"])
    assert all(item["status"] in {"OPEN", "IN_REVIEW"} for item in open_worklist.json()["exceptions"])

    filtered = client.get(
        "/v1/api/procurement/analytics/reconciliation-dashboard",
        headers=superuser_headers,
        params={"severity": "HIGH", "status": "OPEN"},
    )
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["filters"]["severity"] == "HIGH"
    assert filtered.json()["filters"]["status"] == "OPEN"

    invalid = client.get(
        "/v1/api/procurement/analytics/reconciliation-dashboard",
        headers=superuser_headers,
        params={"from_date": "2026-11-07", "to_date": "2026-11-01"},
    )
    assert invalid.status_code == 422, invalid.text



def test_reconciliation_assignment_recommendations_are_advisory_and_workload_aware(
    client, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.identity.models import User
    from backend.domains.procurement.models import ProcurementReconciliationException

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        actor_id = db.query(User.id).filter(User.email == "admin@default.com").scalar()
        target = ProcurementReconciliationException(
            fingerprint="ASSIGNMENT-RECOMMENDATION:TARGET:81001",
            exception_type="UNMATCHED_BANK_DEBIT", severity="HIGH", status="OPEN",
            reference_type="BANK_STATEMENT_LINE", reference_id=81001,
            amount_paise=5000, matched_amount_paise=0, unmatched_amount_paise=5000,
            summary="Target exception for assignment recommendation test.",
            detection_snapshot={},
            first_detected_at=now - timedelta(hours=2), last_detected_at=now,
        )
        resolved = ProcurementReconciliationException(
            fingerprint="ASSIGNMENT-RECOMMENDATION:RESOLVED:81002",
            exception_type="UNRECONCILED_SUPPLIER_PAYMENT", severity="MEDIUM", status="RESOLVED",
            reference_type="SUPPLIER_PAYMENT", reference_id=81002,
            amount_paise=3000, matched_amount_paise=0, unmatched_amount_paise=0,
            summary="Historical attributed resolution for recommendation test.",
            detection_snapshot={}, assigned_to_id=actor_id,
            first_detected_at=now - timedelta(hours=18), last_detected_at=now - timedelta(hours=1),
            resolved_at=now - timedelta(hours=1), resolved_by_id=actor_id,
        )
        db.add_all([target, resolved])
        db.commit()
        target_id = target.id

    response = client.get(
        f"/v1/api/procurement/reconciliation/exceptions/{target_id}/assignment-recommendations",
        headers=superuser_headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["methodology"]["manual_confirmation_required"] is True
    assert payload["methodology"]["automatic_assignment"] is False
    assert payload["target_severity"] == "HIGH"
    candidate = next(item for item in payload["recommendations"] if item["user_id"] == actor_id)
    assert candidate["finance_suitable"] is True
    assert candidate["resolved_count"] >= 1
    assert candidate["median_resolution_hours"] is not None
    assert candidate["score"] > 0
    assert candidate["reasons"]

    # The recommendation endpoint must never mutate assignment state.
    with session_factory() as db:
        persisted = db.get(ProcurementReconciliationException, target_id)
        assert persisted.assigned_to_id is None


def test_reconciliation_assignment_acknowledgement_rejection_and_escalation_queue(
    client, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.identity.models import User
    from backend.domains.procurement.models import (
        ProcurementReconciliationException,
        ProcurementReconciliationExceptionEvent,
    )

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        actor_id = db.query(User.id).filter(User.email == "admin@default.com").scalar()
        accepted_case = ProcurementReconciliationException(
            fingerprint="ASSIGNMENT-ACK:ACCEPT:82001",
            exception_type="UNMATCHED_BANK_DEBIT", severity="HIGH", status="OPEN",
            reference_type="BANK_STATEMENT_LINE", reference_id=82001,
            amount_paise=6000, matched_amount_paise=0, unmatched_amount_paise=6000,
            summary="Assignment acknowledgement acceptance test.", detection_snapshot={},
            first_detected_at=now, last_detected_at=now,
        )
        escalation_case = ProcurementReconciliationException(
            fingerprint="ASSIGNMENT-ACK:ESCALATE:82002",
            exception_type="UNRECONCILED_SUPPLIER_PAYMENT", severity="CRITICAL", status="OPEN",
            reference_type="SUPPLIER_PAYMENT", reference_id=82002,
            amount_paise=7000, matched_amount_paise=0, unmatched_amount_paise=7000,
            summary="Unacknowledged critical assignment escalation test.", detection_snapshot={},
            first_detected_at=now, last_detected_at=now,
        )
        db.add_all([accepted_case, escalation_case])
        db.commit()
        accepted_id, escalation_id = accepted_case.id, escalation_case.id

    assigned = client.patch(
        f"/v1/api/procurement/reconciliation/exceptions/{accepted_id}/assignment",
        headers=superuser_headers,
        json={"assigned_to_id": actor_id},
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["acknowledgement_status"] == "PENDING"

    accepted = client.post(
        f"/v1/api/procurement/reconciliation/exceptions/{accepted_id}/assignment-response",
        headers=superuser_headers,
        json={"decision": "ACCEPT"},
    )
    assert accepted.status_code == 200, accepted.text
    duplicate = client.post(
        f"/v1/api/procurement/reconciliation/exceptions/{accepted_id}/assignment-response",
        headers=superuser_headers,
        json={"decision": "ACCEPT"},
    )
    assert duplicate.status_code == 409

    rejected_without_reason = client.post(
        f"/v1/api/procurement/reconciliation/exceptions/{accepted_id}/assignment-response",
        headers=superuser_headers,
        json={"decision": "REJECT"},
    )
    assert rejected_without_reason.status_code == 409

    assigned_escalation = client.patch(
        f"/v1/api/procurement/reconciliation/exceptions/{escalation_id}/assignment",
        headers=superuser_headers,
        json={"assigned_to_id": actor_id},
    )
    assert assigned_escalation.status_code == 200, assigned_escalation.text
    with session_factory() as db:
        assignment_event = db.query(ProcurementReconciliationExceptionEvent).filter(
            ProcurementReconciliationExceptionEvent.exception_id == escalation_id,
            ProcurementReconciliationExceptionEvent.event_type == "ASSIGNED",
        ).one()
        assignment_event.occurred_at = now - timedelta(hours=1)
        db.commit()

    escalations = client.get(
        "/v1/api/procurement/reconciliation/exceptions/escalations",
        headers=superuser_headers,
    )
    assert escalations.status_code == 200, escalations.text
    assert any(item["exception_id"] == escalation_id for item in escalations.json()["items"])
    assert all(item["exception_id"] != accepted_id for item in escalations.json()["items"])
    assert escalations.json()["automatic_escalation"] is False


def test_rejected_reconciliation_assignment_returns_to_unassigned_queue(
    client, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.identity.models import User
    from backend.domains.procurement.models import ProcurementReconciliationException

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        actor_id = db.query(User.id).filter(User.email == "admin@default.com").scalar()
        row = ProcurementReconciliationException(
            fingerprint="ASSIGNMENT-REJECT:RETURN:82003",
            exception_type="UNRECONCILED_SUPPLIER_PAYMENT", severity="HIGH", status="OPEN",
            reference_type="SUPPLIER_PAYMENT", reference_id=82003,
            amount_paise=4500, matched_amount_paise=0, unmatched_amount_paise=4500,
            summary="Rejected assignment must return to unassigned worklist.", detection_snapshot={},
            first_detected_at=now, last_detected_at=now,
        )
        db.add(row)
        db.commit()
        exception_id = row.id

    assigned = client.patch(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/assignment",
        headers=superuser_headers,
        json={"assigned_to_id": actor_id},
    )
    assert assigned.status_code == 200, assigned.text

    rejected = client.post(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/assignment-response",
        headers=superuser_headers,
        json={"decision": "REJECT", "reason": "Insufficient supplier payment authority."},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["assigned_to_id"] is None

    with session_factory() as db:
        persisted = db.get(ProcurementReconciliationException, exception_id)
        assert persisted.assigned_to_id is None


def test_my_reconciliation_assignments_are_scoped_to_authenticated_user(
    client, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.identity.models import User
    from backend.domains.procurement.models import (
        ProcurementReconciliationException,
        ProcurementReconciliationExceptionEvent,
    )

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        actor_id = db.query(User.id).filter(User.email == "admin@default.com").scalar()
        other_id = db.query(User.id).filter(User.id != actor_id).order_by(User.id).scalar()
        assert actor_id is not None and other_id is not None
        own = ProcurementReconciliationException(
            fingerprint="MY-ASSIGNMENT:OWN:83001",
            exception_type="UNMATCHED_BANK_DEBIT", severity="CRITICAL", status="OPEN",
            reference_type="BANK_STATEMENT_LINE", reference_id=83001,
            amount_paise=8800, matched_amount_paise=0, unmatched_amount_paise=8800,
            summary="Only the authenticated assignee should see this investigation.",
            detection_snapshot={}, first_detected_at=now, last_detected_at=now,
            assigned_to_id=actor_id,
        )
        other = ProcurementReconciliationException(
            fingerprint="MY-ASSIGNMENT:OTHER:83002",
            exception_type="UNRECONCILED_SUPPLIER_PAYMENT", severity="HIGH", status="OPEN",
            reference_type="SUPPLIER_PAYMENT", reference_id=83002,
            amount_paise=9900, matched_amount_paise=0, unmatched_amount_paise=9900,
            summary="This investigation belongs to another staff member.",
            detection_snapshot={}, first_detected_at=now, last_detected_at=now,
            assigned_to_id=other_id,
        )
        db.add_all([own, other])
        db.flush()
        db.add_all([
            ProcurementReconciliationExceptionEvent(
                exception_id=own.id, event_type="ASSIGNED", actor_user_id=actor_id,
                old_assignee_id=None, new_assignee_id=actor_id,
                event_metadata={"acknowledgement_status": "PENDING"},
            ),
            ProcurementReconciliationExceptionEvent(
                exception_id=other.id, event_type="ASSIGNED", actor_user_id=actor_id,
                old_assignee_id=None, new_assignee_id=other_id,
                event_metadata={"acknowledgement_status": "PENDING"},
            ),
        ])
        own_id = own.id
        db.commit()

    response = client.get(
        "/v1/api/procurement/reconciliation/my-assignments",
        headers=superuser_headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["scope"] == "CURRENT_USER_ACTIVE_ASSIGNMENTS"
    assert payload["total"] == 1
    assert [item["id"] for item in payload["items"]] == [own_id]
    assert payload["items"][0]["acknowledgement_status"] == "PENDING"
    assert "amount_paise" not in payload["items"][0]
    assert "supplier_name" not in payload["items"][0]


def test_reconciliation_sla_policy_versions_are_effective_dated_and_audited(
    client, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.procurement.models import (
        ProcurementReconciliationSlaPolicy,
        ProcurementReconciliationSlaPolicyEvent,
    )

    invalid = client.post(
        "/v1/api/procurement/reconciliation/sla-policies",
        headers=superuser_headers,
        json={
            "severity_targets_hours": {"CRITICAL": 0, "HIGH": 24, "MEDIUM": 72, "LOW": 168},
            "change_reason": "Invalid policy target test.",
        },
    )
    assert invalid.status_code == 422, invalid.text

    first = client.post(
        "/v1/api/procurement/reconciliation/sla-policies",
        headers=superuser_headers,
        json={
            "severity_targets_hours": {"CRITICAL": 2, "HIGH": 12, "MEDIUM": 48, "LOW": 120},
            "change_reason": "Tighten response targets after finance control review.",
        },
    )
    assert first.status_code == 201, first.text
    first_policy = first.json()
    assert first_policy["version"] >= 1
    assert first_policy["status"] == "DRAFT"

    published_first = client.post(
        f"/v1/api/procurement/reconciliation/sla-policies/{first_policy['id']}/publish",
        headers=superuser_headers,
        json={},
    )
    assert published_first.status_code == 200, published_first.text
    assert published_first.json()["status"] == "PUBLISHED"

    second = client.post(
        "/v1/api/procurement/reconciliation/sla-policies",
        headers=superuser_headers,
        json={
            "severity_targets_hours": {"CRITICAL": 1, "HIGH": 8, "MEDIUM": 36, "LOW": 96},
            "change_reason": "Adopt revised escalation risk appetite approved by finance.",
        },
    )
    assert second.status_code == 201, second.text
    second_policy = second.json()
    published_second = client.post(
        f"/v1/api/procurement/reconciliation/sla-policies/{second_policy['id']}/publish",
        headers=superuser_headers,
        json={},
    )
    assert published_second.status_code == 200, published_second.text

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        prior = db.get(ProcurementReconciliationSlaPolicy, first_policy["id"])
        assert prior.status == "PUBLISHED"
        assert prior.effective_to is not None
        effective_to = prior.effective_to
        if effective_to.tzinfo is None:
            effective_to = effective_to.replace(tzinfo=timezone.utc)
        effective_from = datetime.fromisoformat(published_second.json()["effective_from"].replace("Z", "+00:00"))
        assert abs((effective_to - effective_from).total_seconds()) < 2
        events = db.query(ProcurementReconciliationSlaPolicyEvent).filter(
            ProcurementReconciliationSlaPolicyEvent.policy_id.in_([first_policy["id"], second_policy["id"]])
        ).all()
        assert {event.event_type for event in events} >= {"DRAFT_CREATED", "PUBLISHED", "SUPERSEDED"}

    listed = client.get(
        "/v1/api/procurement/reconciliation/sla-policies",
        headers=superuser_headers,
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["active_policy_id"] == second_policy["id"]
    assert listed.json()["active_policy_version"] == second_policy["version"]


def test_reconciliation_sla_policy_publish_is_not_repeatable(
    client, superuser_headers
):
    draft = client.post(
        "/v1/api/procurement/reconciliation/sla-policies",
        headers=superuser_headers,
        json={
            "severity_targets_hours": {"CRITICAL": 3, "HIGH": 18, "MEDIUM": 60, "LOW": 144},
            "change_reason": "Validate that a policy version cannot be republished.",
        },
    )
    assert draft.status_code == 201, draft.text
    policy_id = draft.json()["id"]
    first = client.post(
        f"/v1/api/procurement/reconciliation/sla-policies/{policy_id}/publish",
        headers=superuser_headers,
        json={},
    )
    assert first.status_code == 200, first.text
    second = client.post(
        f"/v1/api/procurement/reconciliation/sla-policies/{policy_id}/publish",
        headers=superuser_headers,
        json={},
    )
    assert second.status_code == 409, second.text



def test_reconciliation_sla_targets_are_snapshotted_per_investigation(
    client, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.procurement.models import ProcurementReconciliationException

    first = client.post(
        "/v1/api/procurement/reconciliation/sla-policies",
        headers=superuser_headers,
        json={
            "severity_targets_hours": {"CRITICAL": 2, "HIGH": 24, "MEDIUM": 72, "LOW": 168},
            "change_reason": "Capture target values for a pre-existing investigation.",
        },
    )
    assert first.status_code == 201, first.text
    first_policy_id = first.json()["id"]
    published = client.post(
        f"/v1/api/procurement/reconciliation/sla-policies/{first_policy_id}/publish",
        headers=superuser_headers,
        json={},
    )
    assert published.status_code == 200, published.text

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        row = ProcurementReconciliationException(
            fingerprint="SLA-SNAPSHOT:UNMATCHED_BANK_DEBIT:930001",
            exception_type="UNMATCHED_BANK_DEBIT",
            severity="HIGH",
            status="OPEN",
            reference_type="BANK_STATEMENT_LINE",
            reference_id=930001,
            amount_paise=1000,
            matched_amount_paise=0,
            unmatched_amount_paise=1000,
            summary="SLA target snapshot regression test.",
            detection_snapshot={},
            sla_policy_id=first_policy_id,
            sla_target_hours=24,
            first_detected_at=datetime.now(timezone.utc) - timedelta(hours=12),
        )
        db.add(row)
        db.commit()

    second = client.post(
        "/v1/api/procurement/reconciliation/sla-policies",
        headers=superuser_headers,
        json={
            "severity_targets_hours": {"CRITICAL": 1, "HIGH": 1, "MEDIUM": 2, "LOW": 4},
            "change_reason": "Publish a tighter policy without changing open-case targets.",
        },
    )
    assert second.status_code == 201, second.text
    second_publish = client.post(
        f"/v1/api/procurement/reconciliation/sla-policies/{second.json()['id']}/publish",
        headers=superuser_headers,
        json={},
    )
    assert second_publish.status_code == 200, second_publish.text

    queue = client.get(
        "/v1/api/procurement/reconciliation/exceptions/queue",
        headers=superuser_headers,
        params={"open_only": "true"},
    )
    assert queue.status_code == 200, queue.text
    saved = next(item for item in queue.json()["exceptions"] if item["reference_id"] == 930001)
    assert saved["sla_policy_id"] == first_policy_id
    assert saved["sla_hours"] == 24
    assert saved["sla_overdue"] is False




def test_reconciliation_sla_policy_writes_require_dedicated_permission(
    client, pharmacist_headers
):
    response = client.post(
        "/v1/api/procurement/reconciliation/sla-policies",
        headers=pharmacist_headers,
        json={
            "severity_targets_hours": {"CRITICAL": 2, "HIGH": 12, "MEDIUM": 48, "LOW": 120},
            "change_reason": "Unauthorized policy change must be rejected.",
        },
    )
    assert response.status_code == 403, response.text



def test_reconciliation_sla_clock_pause_resume_and_breach_tracking(
    client, superuser_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.procurement.models import ProcurementReconciliationException

    now = datetime.now(timezone.utc)
    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        paused_case = ProcurementReconciliationException(
            fingerprint="SLA-CLOCK:PAUSE-RESUME:930101",
            exception_type="UNMATCHED_BANK_DEBIT",
            severity="HIGH",
            status="OPEN",
            reference_type="BANK_STATEMENT_LINE",
            reference_id=930101,
            summary="Pause-aware SLA clock regression case.",
            detection_snapshot={},
            first_detected_at=now - timedelta(minutes=30),
            last_detected_at=now,
            sla_target_hours=1,
            sla_paused_seconds=0,
        )
        breached_case = ProcurementReconciliationException(
            fingerprint="SLA-CLOCK:BREACHED:930102",
            exception_type="UNMATCHED_BANK_DEBIT",
            severity="HIGH",
            status="OPEN",
            reference_type="BANK_STATEMENT_LINE",
            reference_id=930102,
            summary="Breach timestamp regression case.",
            detection_snapshot={},
            first_detected_at=now - timedelta(hours=3),
            last_detected_at=now,
            sla_target_hours=1,
            sla_paused_seconds=0,
        )
        db.add_all([paused_case, breached_case])
        db.commit()
        paused_id, breached_id = paused_case.id, breached_case.id

    paused = client.post(
        f"/v1/api/procurement/reconciliation/exceptions/{paused_id}/sla/pause",
        headers=superuser_headers,
        json={"reason": "Waiting for external bank confirmation."},
    )
    assert paused.status_code == 200, paused.text
    assert paused.json()["paused"] is True

    # Simulate a long pause deterministically without sleeping in the test.
    with session_factory() as db:
        row = db.query(ProcurementReconciliationException).filter_by(id=paused_id).one()
        row.sla_paused_at = datetime.now(timezone.utc) - timedelta(hours=2)
        db.commit()

    queue = client.get(
        "/v1/api/procurement/reconciliation/exceptions/queue",
        headers=superuser_headers,
        params={"open_only": "true"},
    )
    assert queue.status_code == 200, queue.text
    paused_item = next(item for item in queue.json()["exceptions"] if item["id"] == paused_id)
    breached_item = next(item for item in queue.json()["exceptions"] if item["id"] == breached_id)
    assert paused_item["sla_paused"] is True
    assert paused_item["sla_overdue"] is False
    assert 0.45 <= paused_item["sla_elapsed_hours"] <= 0.6
    assert breached_item["sla_overdue"] is True
    assert breached_item["sla_breached_at"] is not None
    expected_breach = now - timedelta(hours=2)
    actual_breach = datetime.fromisoformat(breached_item["sla_breached_at"].replace("Z", "+00:00"))
    assert abs((actual_breach - expected_breach).total_seconds()) < 10

    resumed = client.post(
        f"/v1/api/procurement/reconciliation/exceptions/{paused_id}/sla/resume",
        headers=superuser_headers,
        json={"reason": "Bank confirmation received; investigation can continue."},
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["paused"] is False
    assert resumed.json()["sla_paused_seconds"] >= 7199
    assert resumed.json()["sla_overdue"] is False

    history = client.get(
        f"/v1/api/procurement/reconciliation/exceptions/{paused_id}/history",
        headers=superuser_headers,
    )
    assert history.status_code == 200, history.text
    event_types = [event["event_type"] for event in history.json()["events"]]
    assert "SLA_PAUSED" in event_types
    assert "SLA_RESUMED" in event_types


def test_reconciliation_sla_pause_requires_finance_approval_permission(
    client, pharmacist_headers, multi_tenant_env
):
    from sqlalchemy.orm import sessionmaker
    from backend.domains.procurement.models import ProcurementReconciliationException

    session_factory = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with session_factory() as db:
        row = ProcurementReconciliationException(
            fingerprint="SLA-CLOCK:UNAUTHORIZED:930103",
            exception_type="UNMATCHED_BANK_DEBIT",
            severity="LOW",
            status="OPEN",
            reference_type="BANK_STATEMENT_LINE",
            reference_id=930103,
            summary="Unauthorized pause regression case.",
            detection_snapshot={},
            first_detected_at=datetime.now(timezone.utc),
            last_detected_at=datetime.now(timezone.utc),
            sla_target_hours=168,
            sla_paused_seconds=0,
        )
        db.add(row)
        db.commit()
        exception_id = row.id

    response = client.post(
        f"/v1/api/procurement/reconciliation/exceptions/{exception_id}/sla/pause",
        headers=pharmacist_headers,
        json={"reason": "Unauthorized pause attempt for testing."},
    )
    assert response.status_code == 403, response.text

