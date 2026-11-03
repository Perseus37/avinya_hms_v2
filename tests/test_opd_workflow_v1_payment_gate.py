from datetime import datetime, timedelta, timezone


def _book_opd(client, doctor_headers, *, name="OPD Payment Patient"):
    patient = client.post(
        "/v1/api/patients",
        headers=doctor_headers,
        json={
            "full_name": name,
            "date_of_birth": "1990-01-01T00:00:00Z",
            "gender": "MALE",
        },
    )
    assert patient.status_code == 201, patient.text
    patient = patient.json()

    appointment = client.post(
        "/v1/api/opd/appointments",
        headers=doctor_headers,
        json={
            "patient_id": patient["id"],
            "doctor_id": 2,
            "department_id": 1,
            "appointment_time": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
            "reason_for_visit": "OPD payment-gate test",
        },
    )
    assert appointment.status_code == 201, appointment.text
    return patient, appointment.json()


def _finalize_and_pay(client, billing_headers, invoice_id, amount_paise):
    finalized = client.patch(
        f"/v1/api/billing/invoices/{invoice_id}/finalize",
        headers=billing_headers,
    )
    assert finalized.status_code == 200, finalized.text

    payment = client.post(
        f"/v1/api/billing/invoices/{invoice_id}/payments",
        headers=billing_headers,
        json={
            "amount_paid_paise": amount_paise,
            "payment_method": "CASH",
            "transaction_reference": f"OPD-TEST-{invoice_id}-{amount_paise}",
        },
    )
    assert payment.status_code == 201, payment.text
    return payment.json()


def _consultation_invoice(client, billing_headers, patient_id):
    invoices = client.get(
        f"/v1/api/billing/invoices?patient_id={patient_id}",
        headers=billing_headers,
    )
    assert invoices.status_code == 200, invoices.text
    items = invoices.json()["items"]
    assert len(items) == 1
    return items[0]


def test_01_unpaid_opd_invoice_blocks_queue_admission(client, doctor_headers, billing_headers):
    """A booked OPD consultation with an unpaid invoice cannot receive a queue token."""
    _, appointment = _book_opd(client, doctor_headers, name="OPD Unpaid")
    invoice = _consultation_invoice(client, billing_headers, appointment["patient_id"])

    check_in = client.post(
        "/v1/api/opd/queues/check-in",
        headers=doctor_headers,
        json={"appointment_id": appointment["id"], "room_label": "Room 1"},
    )
    assert check_in.status_code == 402, check_in.text
    assert check_in.json()["detail"]["code"] == "OPD_CONSULTATION_PAYMENT_REQUIRED"
    assert invoice["status"] == "DRAFT"


def test_02_partial_opd_payment_blocks_queue_admission(client, doctor_headers, billing_headers):
    """A partially settled consultation remains ineligible for queue admission."""
    _, appointment = _book_opd(client, doctor_headers, name="OPD Partial")
    invoice = _consultation_invoice(client, billing_headers, appointment["patient_id"])
    assert invoice["total_amount_paise"] > 1

    _finalize_and_pay(client, billing_headers, invoice["id"], invoice["total_amount_paise"] - 1)

    check_in = client.post(
        "/v1/api/opd/queues/check-in",
        headers=doctor_headers,
        json={"appointment_id": appointment["id"], "room_label": "Room 2"},
    )
    assert check_in.status_code == 402, check_in.text
    assert check_in.json()["detail"]["invoice_status"] == "PARTIAL"


def test_03_fully_paid_opd_consultation_allows_queue_token(client, doctor_headers, billing_headers):
    """Finalized and fully paid consultation is admitted and receives exactly one queue entry."""
    _, appointment = _book_opd(client, doctor_headers, name="OPD Paid")
    invoice = _consultation_invoice(client, billing_headers, appointment["patient_id"])
    _finalize_and_pay(client, billing_headers, invoice["id"], invoice["total_amount_paise"])

    check_in = client.post(
        "/v1/api/opd/queues/check-in",
        headers=doctor_headers,
        json={"appointment_id": appointment["id"], "room_label": "Room 3"},
    )
    assert check_in.status_code == 201, check_in.text
    result = check_in.json()
    assert result["state"] == "WAITING"
    assert result["token_number"] > 0

    duplicate = client.post(
        "/v1/api/opd/queues/check-in",
        headers=doctor_headers,
        json={"appointment_id": appointment["id"], "room_label": "Room 3"},
    )
    assert duplicate.status_code == 409, duplicate.text


def test_04_reversed_opd_payment_blocks_queue_admission_again(client, doctor_headers, billing_headers):
    """Reversing the only consultation payment makes the appointment financially ineligible again."""
    _, appointment = _book_opd(client, doctor_headers, name="OPD Reversal")
    invoice = _consultation_invoice(client, billing_headers, appointment["patient_id"])
    payment = _finalize_and_pay(client, billing_headers, invoice["id"], invoice["total_amount_paise"])

    reversed_payment = client.delete(
        f"/v1/api/billing/invoices/{invoice['id']}/payments/{payment['id']}",
        headers=billing_headers,
    )
    assert reversed_payment.status_code == 200, reversed_payment.text
    assert reversed_payment.json()["new_invoice_status"] == "UNPAID"

    check_in = client.post(
        "/v1/api/opd/queues/check-in",
        headers=doctor_headers,
        json={"appointment_id": appointment["id"], "room_label": "Room 4"},
    )
    assert check_in.status_code == 402, check_in.text
    assert check_in.json()["detail"]["invoice_status"] == "UNPAID"


def test_05_advance_deposit_only_counts_after_invoice_adjustment(client, doctor_headers, billing_headers):
    """A patient deposit alone does not satisfy OPD payment; applying it to the invoice does."""
    patient, appointment = _book_opd(client, doctor_headers, name="OPD Deposit")
    invoice = _consultation_invoice(client, billing_headers, appointment["patient_id"])

    deposit = client.post(
        "/v1/api/billing/deposits",
        headers=billing_headers,
        json={
            "patient_id": patient["id"],
            "encounter_id": appointment["encounter_id"],
            "amount_paise": invoice["total_amount_paise"],
            "payment_method": "CASH",
            "transaction_reference": "DEP-OPD-TEST",
        },
    )
    assert deposit.status_code == 201, deposit.text

    before_apply = client.post(
        "/v1/api/opd/queues/check-in",
        headers=doctor_headers,
        json={"appointment_id": appointment["id"], "room_label": "Room 5"},
    )
    assert before_apply.status_code == 402, before_apply.text

    finalized = client.patch(
        f"/v1/api/billing/invoices/{invoice['id']}/finalize",
        headers=billing_headers,
    )
    assert finalized.status_code == 200, finalized.text

    adjustment = client.post(
        f"/v1/api/billing/invoices/{invoice['id']}/apply-deposit",
        headers=billing_headers,
        json={"deposit_id": deposit.json()["id"]},
    )
    assert adjustment.status_code == 201, adjustment.text
    assert adjustment.json()["payment_method"] == "ADVANCE_ADJUSTMENT"

    after_apply = client.post(
        "/v1/api/opd/queues/check-in",
        headers=doctor_headers,
        json={"appointment_id": appointment["id"], "room_label": "Room 5"},
    )
    assert after_apply.status_code == 201, after_apply.text
