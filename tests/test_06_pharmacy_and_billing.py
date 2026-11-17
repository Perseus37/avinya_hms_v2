from datetime import datetime, timedelta, timezone


def _setup_med_and_batch(client, pharmacist_headers):
    """Helper to register a medication and receive an active inventory batch of 100 units at Rs 15.00 (1500 paise)."""
    med = client.post(
        "/v1/api/pharmacy/medications",
        headers=pharmacist_headers,
        json={
            "code": "MED_PARA_500",
            "brand_name": "Dolo-500",
            "generic_name": "Paracetamol",
            "form": "TABLET",
            "strength": "500mg",
        },
    ).json()

    future_exp = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
    batch = client.post(
        "/v1/api/pharmacy/inventory/batches",
        headers=pharmacist_headers,
        json={
            "medication_id": med["id"],
            "batch_number": "BATCH-2026-A1",
            "expiry_date": future_exp,
            "stock_quantity": 100,
            "unit_price_paise": 1500,
        },
    ).json()

    return med, batch


def test_01_formulary_medication_and_batch_creation(client, pharmacist_headers):
    """Scenario 1: Add medication to formulary and receive an inventory batch."""
    med, batch = _setup_med_and_batch(client, pharmacist_headers)
    assert med["code"] == "MED_PARA_500"
    assert batch["stock_quantity"] == 100
    assert batch["unit_price_paise"] == 1500


def test_02_receiving_expired_or_zero_stock_batch_returns_400(client, pharmacist_headers):
    """Scenario 2: Receiving an already expired batch or <= 0 stock quantity is blocked with 400."""
    med, _ = _setup_med_and_batch(client, pharmacist_headers)
    past_exp = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    # Expired batch -> 400
    assert client.post(
        "/v1/api/pharmacy/inventory/batches",
        headers=pharmacist_headers,
        json={
            "medication_id": med["id"],
            "batch_number": "BATCH-EXP-01",
            "expiry_date": past_exp,
            "stock_quantity": 50,
            "unit_price_paise": 1500,
        },
    ).status_code == 400

    # Zero stock -> 400
    future_exp = (datetime.now(timezone.utc) + timedelta(days=180)).isoformat()
    assert client.post(
        "/v1/api/pharmacy/inventory/batches",
        headers=pharmacist_headers,
        json={
            "medication_id": med["id"],
            "batch_number": "BATCH-ZERO-01",
            "expiry_date": future_exp,
            "stock_quantity": 0,
            "unit_price_paise": 1500,
        },
    ).status_code == 400


def test_03_stock_adjustment_and_negative_inventory_guard(client, pharmacist_headers, superuser_headers):
    """Scenario 3: Stock adjustment updates quantity; adjustment resulting in < 0 stock is blocked with 400."""
    _, batch = _setup_med_and_batch(client, pharmacist_headers)

    # Deduct 20 units -> 80 remaining
    adj_ok = client.patch(
        f"/v1/api/pharmacy/inventory/batches/{batch['id']}/adjust",
        headers=pharmacist_headers,
        json={"quantity_adjustment": -20, "reason": "Physical stock count correction"},
    )
    assert adj_ok.status_code == 200
    assert adj_ok.json()["stock_quantity"] == 80

    ledger = client.get(
        f"/v1/api/pharmacy/inventory/adjustments?batch_id={batch['id']}&page=1&page_size=10",
        headers=pharmacist_headers,
    )
    assert ledger.status_code == 200
    assert ledger.json()["total"] == 1
    assert ledger.json()["page"] == 1
    assert ledger.json()["page_size"] == 10
    assert len(ledger.json()["items"]) == 1
    movement = ledger.json()["items"][0]
    assert movement["quantity_adjustment"] == -20
    assert movement["quantity_before"] == 100
    assert movement["quantity_after"] == 80
    assert movement["reason"] == "Physical stock count correction"
    assert movement["actor_id"] > 0

    # Deduct 100 units from 80 -> 400 Bad Request
    adj_fail = client.patch(
        f"/v1/api/pharmacy/inventory/batches/{batch['id']}/adjust",
        headers=pharmacist_headers,
        json={"quantity_adjustment": -100, "reason": "Counted stock discrepancy"},
    )
    assert adj_fail.status_code == 400
    # Rejected corrections must not create ledger entries.
    ledger_after_rejection = client.get(
        f"/v1/api/pharmacy/inventory/adjustments?batch_id={batch['id']}",
        headers=pharmacist_headers,
    )
    assert ledger_after_rejection.json()["total"] == 1
    assert len(ledger_after_rejection.json()["items"]) == 1

    # Voiding a non-empty batch is also a stock correction and must be audited.
    voided = client.delete(
        f"/v1/api/pharmacy/inventory/batches/{batch['id']}",
        headers=superuser_headers,
    )
    assert voided.status_code == 200, voided.text

    batches = client.get(
        f"/v1/api/pharmacy/inventory/batches?medication_id={batch['medication_id']}&include_depleted=true",
        headers=pharmacist_headers,
    )
    assert batches.status_code == 200
    voided_batch = next(item for item in batches.json()["items"] if item["id"] == batch["id"])
    assert voided_batch["stock_quantity"] == 0

    void_ledger = client.get(
        f"/v1/api/pharmacy/inventory/adjustments?batch_id={batch['id']}&page=1&page_size=10",
        headers=pharmacist_headers,
    )
    assert void_ledger.status_code == 200
    assert void_ledger.json()["total"] == 2
    void_movement = next(
        item for item in void_ledger.json()["items"]
        if item["reason"] == "Batch voided for recall"
    )
    assert void_movement["quantity_adjustment"] == -80
    assert void_movement["quantity_before"] == 80
    assert void_movement["quantity_after"] == 0
    assert void_movement["actor_id"] > 0

    # The append-only history remains bounded and navigable across pages.
    page_one = client.get(
        f"/v1/api/pharmacy/inventory/adjustments?batch_id={batch['id']}&page=1&page_size=1",
        headers=pharmacist_headers,
    )
    page_two = client.get(
        f"/v1/api/pharmacy/inventory/adjustments?batch_id={batch['id']}&page=2&page_size=1",
        headers=pharmacist_headers,
    )
    assert page_one.status_code == 200
    assert page_two.status_code == 200
    assert page_one.json()["total"] == page_two.json()["total"] == 2
    assert len(page_one.json()["items"]) == len(page_two.json()["items"]) == 1
    assert page_one.json()["items"][0]["reason"] == "Batch voided for recall"
    assert page_two.json()["items"][0]["reason"] == "Physical stock count correction"

    # Re-voiding an already empty batch must not create a zero-delta ledger row.
    repeat_void = client.delete(
        f"/v1/api/pharmacy/inventory/batches/{batch['id']}",
        headers=superuser_headers,
    )
    assert repeat_void.status_code == 200
    unchanged_ledger = client.get(
        f"/v1/api/pharmacy/inventory/adjustments?batch_id={batch['id']}",
        headers=pharmacist_headers,
    )
    assert unchanged_ledger.json()["total"] == 2


def test_04_erx_prescription_enforces_cpoe_allergy_hard_stop(client, doctor_headers, pharmacist_headers):
    """Scenario 4: Writing a prescription for Amoxicillin on a Penicillin-allergic patient returns 409."""
    amox = client.post(
        "/v1/api/pharmacy/medications",
        headers=pharmacist_headers,
        json={"code": "MED_AMOX_500", "brand_name": "Amoxil", "generic_name": "Amoxicillin", "form": "CAPSULE", "strength": "500mg"},
    ).json()

    p = client.post("/v1/api/patients", headers=doctor_headers, json={"full_name": "Rx Allergy P", "date_of_birth": "1985-01-01T00:00:00Z", "gender": "MALE"}).json()
    client.post(f"/v1/api/patients/{p['id']}/allergies", headers=doctor_headers, json={"allergy_id": 1, "severity": "SEVERE", "reaction": "Bronchospasm"})
    enc = client.post("/v1/api/adt/encounters", headers=doctor_headers, json={"patient_id": p["id"], "encounter_type": "OPD", "primary_doctor_id": 2, "department_id": 1}).json()

    rx_res = client.post(
        "/v1/api/pharmacy/prescriptions",
        headers=doctor_headers,
        json={
            "encounter_id": enc["id"],
            "clinical_notes": "URI treatment",
            "items": [{"medication_id": amox["id"], "dosage_instruction": "1-0-1", "requested_quantity": 10}],
        },
    )
    assert rx_res.status_code == 409
    assert "CLINICAL HARD-STOP" in rx_res.json()["message"]


def test_05_atomic_medication_dispensing_and_auto_billing(client, doctor_headers, pharmacist_headers, billing_headers):
    """Scenario 5: Dispensing deducts batch stock, marks prescription DISPENSED, and auto-bills encounter's DRAFT invoice."""
    med, batch = _setup_med_and_batch(client, pharmacist_headers)
    p = client.post("/v1/api/patients", headers=doctor_headers, json={"full_name": "Dispense P", "date_of_birth": "1990-01-01T00:00:00Z", "gender": "FEMALE"}).json()
    enc = client.post("/v1/api/adt/encounters", headers=doctor_headers, json={"patient_id": p["id"], "encounter_type": "OPD", "primary_doctor_id": 2, "department_id": 1}).json()

    rx = client.post(
        "/v1/api/pharmacy/prescriptions",
        headers=doctor_headers,
        json={
            "encounter_id": enc["id"],
            "items": [{"medication_id": med["id"], "dosage_instruction": "1-1-1", "requested_quantity": 10}],
        },
    ).json()
    rx_item_id = rx["items"][0]["id"]

    disp = client.post(
        f"/v1/api/pharmacy/prescriptions/{rx['id']}/dispense",
        headers=pharmacist_headers,
        json={"items": [{"prescription_item_id": rx_item_id, "batch_id": batch["id"], "quantity_to_dispense": 10}]},
    )
    assert disp.status_code == 200
    assert disp.json()["prescription_status"] == "DISPENSED"

    # Verify stock dropped from 100 to 90
    batches = client.get(f"/v1/api/pharmacy/inventory/batches?medication_id={med['id']}", headers=pharmacist_headers).json()
    assert batches["items"][0]["stock_quantity"] == 90

    # Verify auto-created DRAFT invoice has 10 * 1500 = 15000 paise
    invoices = client.get(f"/v1/api/billing/invoices?patient_id={p['id']}", headers=billing_headers).json()["items"]
    assert len(invoices) == 1
    assert invoices[0]["total_amount_paise"] == 15000
    assert invoices[0]["line_items"][0]["description"].startswith("PHARMACY:")


def test_06_over_dispense_and_insufficient_stock_guards(client, doctor_headers, pharmacist_headers):
    """Scenario 6: Dispensing more than prescribed returns 400; dispensing more than batch stock returns 409."""
    med, batch = _setup_med_and_batch(client, pharmacist_headers)
    p = client.post("/v1/api/patients", headers=doctor_headers, json={"full_name": "Guard P", "date_of_birth": "1990-01-01T00:00:00Z", "gender": "MALE"}).json()
    enc = client.post("/v1/api/adt/encounters", headers=doctor_headers, json={"patient_id": p["id"], "encounter_type": "OPD", "primary_doctor_id": 2, "department_id": 1}).json()

    rx = client.post(
        "/v1/api/pharmacy/prescriptions",
        headers=doctor_headers,
        json={"encounter_id": enc["id"], "items": [{"medication_id": med["id"], "dosage_instruction": "1-1-1", "requested_quantity": 150}]},
    ).json()
    rx_item_id = rx["items"][0]["id"]

    # Over-dispensing (> 150 requested) -> 400
    assert client.post(
        f"/v1/api/pharmacy/prescriptions/{rx['id']}/dispense",
        headers=pharmacist_headers,
        json={"items": [{"prescription_item_id": rx_item_id, "batch_id": batch["id"], "quantity_to_dispense": 200}]},
    ).status_code == 400

    # Insufficient batch stock (150 requested, but batch only has 100) -> 409
    assert client.post(
        f"/v1/api/pharmacy/prescriptions/{rx['id']}/dispense",
        headers=pharmacist_headers,
        json={"items": [{"prescription_item_id": rx_item_id, "batch_id": batch["id"], "quantity_to_dispense": 150}]},
    ).status_code == 409


def test_07_authoritative_catalog_pricing_on_invoice_line_items(client, superuser_headers, doctor_headers, billing_headers):
    """Scenario 7: Adding a service line item enforces ServiceCatalog.base_price_paise over client-supplied unit_price_paise."""
    cat = client.post("/v1/api/diagnostics/categories", headers=superuser_headers, json={"department_id": 1, "code": "CAT_BILL", "name": "Billing Cat"}).json()
    svc = client.post(
        "/v1/api/diagnostics/catalog",
        headers=superuser_headers,
        json={"category_id": cat["id"], "code": "SVC_MRI", "name": "Brain MRI", "service_type": "RADIOLOGY", "base_price_paise": 800000, "is_order_set": False},
    ).json()

    p = client.post("/v1/api/patients", headers=doctor_headers, json={"full_name": "Bill P1", "date_of_birth": "1990-01-01T00:00:00Z", "gender": "MALE"}).json()
    inv = client.post("/v1/api/billing/invoices", headers=billing_headers, json={"patient_id": p["id"]}).json()

    # Client sends unit_price_paise=100 (tampered low price), server must use 800000 from catalog
    client.post(
        f"/v1/api/billing/invoices/{inv['id']}/items",
        headers=billing_headers,
        json={"service_id": svc["id"], "description": "Brain MRI", "quantity": 2, "unit_price_paise": 100},
    )

    updated = client.get(f"/v1/api/billing/invoices/{inv['id']}", headers=billing_headers).json()
    assert updated["total_amount_paise"] == 1600000  # 2 * 800000


def test_08_deleting_auto_billed_pharmacy_line_item_is_blocked(client, superuser_headers, doctor_headers, pharmacist_headers):
    """Scenario 8: Attempting to delete an auto-billed PHARMACY: line item from an invoice returns 403 Forbidden."""
    med, batch = _setup_med_and_batch(client, pharmacist_headers)
    p = client.post("/v1/api/patients", headers=doctor_headers, json={"full_name": "Tamper P", "date_of_birth": "1990-01-01T00:00:00Z", "gender": "MALE"}).json()
    enc = client.post("/v1/api/adt/encounters", headers=doctor_headers, json={"patient_id": p["id"], "encounter_type": "OPD", "primary_doctor_id": 2, "department_id": 1}).json()
    rx = client.post("/v1/api/pharmacy/prescriptions", headers=doctor_headers, json={"encounter_id": enc["id"], "items": [{"medication_id": med["id"], "dosage_instruction": "OD", "requested_quantity": 5}]}).json()
    client.post(f"/v1/api/pharmacy/prescriptions/{rx['id']}/dispense", headers=pharmacist_headers, json={"items": [{"prescription_item_id": rx["items"][0]["id"], "batch_id": batch["id"], "quantity_to_dispense": 5}]})

    inv = client.get(f"/v1/api/billing/invoices?patient_id={p['id']}", headers=superuser_headers).json()["items"][0]
    item_id = inv["line_items"][0]["id"]

    del_res = client.delete(f"/v1/api/billing/invoices/{inv['id']}/items/{item_id}", headers=superuser_headers)
    assert del_res.status_code == 403


def test_09_empty_invoice_finalization_blocked_valid_finalization_succeeds(client, superuser_headers, billing_headers):
    """Scenario 9: Finalizing a 0-total invoice returns 400; finalizing a populated invoice transitions to UNPAID."""
    cat = client.post("/v1/api/diagnostics/categories", headers=superuser_headers, json={"department_id": 1, "code": "CAT_FIN", "name": "Fin Cat"}).json()
    svc = client.post("/v1/api/diagnostics/catalog", headers=superuser_headers, json={"category_id": cat["id"], "code": "SVC_XRAY", "name": "Chest X-Ray", "service_type": "RADIOLOGY", "base_price_paise": 50000, "is_order_set": False}).json()
    p = client.post("/v1/api/patients", headers=superuser_headers, json={"full_name": "Fin P", "date_of_birth": "1990-01-01T00:00:00Z", "gender": "MALE"}).json()
    inv = client.post("/v1/api/billing/invoices", headers=billing_headers, json={"patient_id": p["id"]}).json()

    # Empty invoice finalization blocked (400)
    assert client.patch(f"/v1/api/billing/invoices/{inv['id']}/finalize", headers=billing_headers).status_code == 400

    # Add item and finalize
    client.post(f"/v1/api/billing/invoices/{inv['id']}/items", headers=billing_headers, json={"service_id": svc["id"], "description": "X-Ray", "quantity": 1, "unit_price_paise": 50000})
    fin_res = client.patch(f"/v1/api/billing/invoices/{inv['id']}/finalize", headers=billing_headers)
    assert fin_res.status_code == 200
    assert fin_res.json()["status"] == "UNPAID"


def test_10_idempotent_payment_prevents_double_charging(client, superuser_headers, billing_headers):
    """Scenario 10: Sending the same Idempotency-Key twice returns the original receipt without double-charging."""
    cat = client.post("/v1/api/diagnostics/categories", headers=superuser_headers, json={"department_id": 1, "code": "CAT_IDEM", "name": "Idem Cat"}).json()
    svc = client.post("/v1/api/diagnostics/catalog", headers=superuser_headers, json={"category_id": cat["id"], "code": "SVC_ECG", "name": "ECG", "service_type": "PROCEDURE", "base_price_paise": 100000, "is_order_set": False}).json()
    p = client.post("/v1/api/patients", headers=superuser_headers, json={"full_name": "Idem P", "date_of_birth": "1990-01-01T00:00:00Z", "gender": "MALE"}).json()
    inv = client.post("/v1/api/billing/invoices", headers=billing_headers, json={"patient_id": p["id"]}).json()
    client.post(f"/v1/api/billing/invoices/{inv['id']}/items", headers=billing_headers, json={"service_id": svc["id"], "description": "ECG", "quantity": 1, "unit_price_paise": 100000})
    client.patch(f"/v1/api/billing/invoices/{inv['id']}/finalize", headers=billing_headers)

    idem_headers = {**billing_headers, "Idempotency-Key": "UPI-TXN-2026-UNIQUE-001"}
    pay1 = client.post(
        f"/v1/api/billing/invoices/{inv['id']}/payments",
        headers=idem_headers,
        json={"amount_paid_paise": 40000, "payment_method": "UPI"},
    )
    assert pay1.status_code == 201

    # Duplicate click with same Idempotency-Key returns same receipt; paid amount remains 40000
    pay2 = client.post(
        f"/v1/api/billing/invoices/{inv['id']}/payments",
        headers=idem_headers,
        json={"amount_paid_paise": 40000, "payment_method": "UPI"},
    )
    assert pay2.json()["receipt_number"] == pay1.json()["receipt_number"]

    inv_state = client.get(f"/v1/api/billing/invoices/{inv['id']}", headers=billing_headers).json()
    assert inv_state["amount_paid_paise"] == 40000
    assert inv_state["status"] == "PARTIAL"


def test_11_overpayment_and_paid_invoice_void_guards(client, superuser_headers, billing_headers):
    """Scenario 11: Paying more than total balance returns 400; voiding an invoice with recorded payments returns 400."""
    cat = client.post("/v1/api/diagnostics/categories", headers=superuser_headers, json={"department_id": 1, "code": "CAT_OVP", "name": "Ovp Cat"}).json()
    svc = client.post("/v1/api/diagnostics/catalog", headers=superuser_headers, json={"category_id": cat["id"], "code": "SVC_USG", "name": "Ultrasound", "service_type": "RADIOLOGY", "base_price_paise": 60000, "is_order_set": False}).json()
    p = client.post("/v1/api/patients", headers=superuser_headers, json={"full_name": "Ovp P", "date_of_birth": "1990-01-01T00:00:00Z", "gender": "MALE"}).json()
    inv = client.post("/v1/api/billing/invoices", headers=billing_headers, json={"patient_id": p["id"]}).json()
    client.post(f"/v1/api/billing/invoices/{inv['id']}/items", headers=billing_headers, json={"service_id": svc["id"], "description": "USG", "quantity": 1, "unit_price_paise": 60000})
    client.patch(f"/v1/api/billing/invoices/{inv['id']}/finalize", headers=billing_headers)

    # Overpayment (70000 > 60000) -> 400
    assert client.post(
        f"/v1/api/billing/invoices/{inv['id']}/payments",
        headers=billing_headers,
        json={"amount_paid_paise": 70000, "payment_method": "CASH"},
    ).status_code == 400

    # Pay 30000, then attempt to void invoice while payments > 0 -> 400
    client.post(f"/v1/api/billing/invoices/{inv['id']}/payments", headers=billing_headers, json={"amount_paid_paise": 30000, "payment_method": "CASH"})
    assert client.delete(f"/v1/api/billing/invoices/{inv['id']}/void", headers=superuser_headers).status_code == 400


def test_12_payment_reversal_restores_balance_and_allows_voiding(client, superuser_headers, billing_headers):
    """Scenario 12: Reversing a payment resets amount_paid_paise to 0 (UNPAID) and allows voiding the invoice."""
    cat = client.post("/v1/api/diagnostics/categories", headers=superuser_headers, json={"department_id": 1, "code": "CAT_REV", "name": "Rev Cat"}).json()
    svc = client.post("/v1/api/diagnostics/catalog", headers=superuser_headers, json={"category_id": cat["id"], "code": "SVC_CT", "name": "CT Scan", "service_type": "RADIOLOGY", "base_price_paise": 250000, "is_order_set": False}).json()
    p = client.post("/v1/api/patients", headers=superuser_headers, json={"full_name": "Rev P", "date_of_birth": "1990-01-01T00:00:00Z", "gender": "MALE"}).json()
    inv = client.post("/v1/api/billing/invoices", headers=billing_headers, json={"patient_id": p["id"]}).json()
    client.post(f"/v1/api/billing/invoices/{inv['id']}/items", headers=billing_headers, json={"service_id": svc["id"], "description": "CT", "quantity": 1, "unit_price_paise": 250000})
    client.patch(f"/v1/api/billing/invoices/{inv['id']}/finalize", headers=billing_headers)

    receipt = client.post(
        f"/v1/api/billing/invoices/{inv['id']}/payments",
        headers=billing_headers,
        json={"amount_paid_paise": 250000, "payment_method": "CREDIT_CARD"},
    ).json()

    # Billing executive without 'billing:reverse' cannot reverse payment (403)
    assert client.delete(f"/v1/api/billing/invoices/{inv['id']}/payments/{receipt['id']}", headers=billing_headers).status_code == 403

    # Superuser (holds 'billing:reverse') reverses payment -> status returns to UNPAID
    rev_res = client.delete(f"/v1/api/billing/invoices/{inv['id']}/payments/{receipt['id']}", headers=superuser_headers)
    assert rev_res.status_code == 200
    assert rev_res.json()["new_invoice_status"] == "UNPAID"

    # Now voiding succeeds
    void_res = client.delete(f"/v1/api/billing/invoices/{inv['id']}/void", headers=superuser_headers)
    assert void_res.status_code == 200


def test_13_pharmacy_queue_includes_patient_identity_after_privacy_gate(client, doctor_headers, pharmacist_headers):
    """The pharmacy queue exposes the real patient name and MRN only through the privacy-gated read endpoint."""
    med, _ = _setup_med_and_batch(client, pharmacist_headers)
    patient = client.post(
        "/v1/api/patients",
        headers=doctor_headers,
        json={"full_name": "Pharmacy Queue Identity", "date_of_birth": "1991-04-12T00:00:00Z", "gender": "FEMALE"},
    ).json()
    encounter = client.post(
        "/v1/api/adt/encounters",
        headers=doctor_headers,
        json={"patient_id": patient["id"], "encounter_type": "OPD", "primary_doctor_id": 2, "department_id": 1},
    ).json()
    prescription = client.post(
        "/v1/api/pharmacy/prescriptions",
        headers=doctor_headers,
        json={
            "encounter_id": encounter["id"],
            "items": [{"medication_id": med["id"], "dosage_instruction": "1 tab PO OD", "requested_quantity": 4}],
        },
    ).json()

    queue = client.get(
        "/v1/api/pharmacy/prescriptions?status_filter=ACTIVE",
        headers=pharmacist_headers,
    )
    assert queue.status_code == 200
    row = next(item for item in queue.json()["items"] if item["id"] == prescription["id"])
    assert row["patient_name"] == patient["full_name"]
    assert row["patient_mrn"] == patient["mrn"]


def test_07_fefo_with_multiple_older_batches_returns_controlled_conflict(
    client, doctor_headers, pharmacist_headers
):
    """Multiple older batches must produce a FEFO conflict, not a multiple-results exception."""
    med, selected_batch = _setup_med_and_batch(client, pharmacist_headers)

    older_batches = []
    for suffix, days in (("EARLIER-A", 90), ("EARLIER-B", 180)):
        response = client.post(
            "/v1/api/pharmacy/inventory/batches",
            headers=pharmacist_headers,
            json={
                "medication_id": med["id"],
                "batch_number": f"BATCH-{suffix}",
                "expiry_date": (datetime.now(timezone.utc) + timedelta(days=days)).isoformat(),
                "stock_quantity": 25,
                "unit_price_paise": 1500,
            },
        )
        assert response.status_code == 201, response.text
        older_batches.append(response.json())

    patient = client.post(
        "/v1/api/patients",
        headers=doctor_headers,
        json={
            "full_name": "FEFO Multiple Batch Patient",
            "date_of_birth": "1990-01-01T00:00:00Z",
            "gender": "FEMALE",
        },
    ).json()
    encounter = client.post(
        "/v1/api/adt/encounters",
        headers=doctor_headers,
        json={
            "patient_id": patient["id"],
            "encounter_type": "OPD",
            "primary_doctor_id": 2,
            "department_id": 1,
        },
    ).json()
    prescription = client.post(
        "/v1/api/pharmacy/prescriptions",
        headers=doctor_headers,
        json={
            "encounter_id": encounter["id"],
            "items": [
                {
                    "medication_id": med["id"],
                    "dosage_instruction": "1-0-1",
                    "requested_quantity": 5,
                }
            ],
        },
    ).json()

    response = client.post(
        f"/v1/api/pharmacy/prescriptions/{prescription['id']}/dispense",
        headers=pharmacist_headers,
        json={
            "items": [
                {
                    "prescription_item_id": prescription["items"][0]["id"],
                    "batch_id": selected_batch["id"],
                    "quantity_to_dispense": 5,
                }
            ]
        },
    )

    assert response.status_code == 409, response.text
    assert "FEFO Violation" in response.text
    assert older_batches[0]["batch_number"] in response.text



def test_fefo_rejects_higher_id_batch_when_expiry_dates_tie(
    client, doctor_headers, pharmacist_headers
):
    """When expiry dates tie, FEFO uses the lower batch ID as the deterministic first batch."""
    med, first_batch = _setup_med_and_batch(client, pharmacist_headers)

    tied_batch_response = client.post(
        "/v1/api/pharmacy/inventory/batches",
        headers=pharmacist_headers,
        json={
            "medication_id": med["id"],
            "batch_number": "BATCH-FEFO-TIED-LATER-ID",
            "expiry_date": first_batch["expiry_date"],
            "stock_quantity": 25,
            "unit_price_paise": 1500,
        },
    )
    assert tied_batch_response.status_code == 201, tied_batch_response.text
    later_id_batch = tied_batch_response.json()
    assert first_batch["id"] < later_id_batch["id"]

    patient = client.post(
        "/v1/api/patients",
        headers=doctor_headers,
        json={
            "full_name": "FEFO Equal Expiry Patient",
            "date_of_birth": "1990-01-01T00:00:00Z",
            "gender": "FEMALE",
        },
    ).json()
    encounter = client.post(
        "/v1/api/adt/encounters",
        headers=doctor_headers,
        json={
            "patient_id": patient["id"],
            "encounter_type": "OPD",
            "primary_doctor_id": 2,
            "department_id": 1,
        },
    ).json()
    prescription = client.post(
        "/v1/api/pharmacy/prescriptions",
        headers=doctor_headers,
        json={
            "encounter_id": encounter["id"],
            "items": [
                {
                    "medication_id": med["id"],
                    "dosage_instruction": "1-0-1",
                    "requested_quantity": 5,
                }
            ],
        },
    ).json()

    response = client.post(
        f"/v1/api/pharmacy/prescriptions/{prescription['id']}/dispense",
        headers=pharmacist_headers,
        json={
            "items": [
                {
                    "prescription_item_id": prescription["items"][0]["id"],
                    "batch_id": later_id_batch["id"],
                    "quantity_to_dispense": 5,
                }
            ]
        },
    )

    assert response.status_code == 409, response.text
    assert "FEFO Violation" in response.text
    assert first_batch["batch_number"] in response.text
