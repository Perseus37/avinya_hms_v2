"""
Test suite verifying the clinical & operational UI aggregation endpoints
and session continuity features for the Avinya HMS frontend.
"""

from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient


def test_session_refresh_and_preferences(client: TestClient, superuser_headers: dict):
    # 1. Test Session Refresh
    refresh_res = client.post("/v1/api/auth/session/refresh", headers=superuser_headers)
    assert refresh_res.status_code == 200, refresh_res.text
    refresh_data = refresh_res.json()
    assert "access_token" in refresh_data
    assert refresh_data["token_type"] == "bearer"

    new_token = refresh_data["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}

    # Verify new token works on protected endpoints
    me_res = client.get("/v1/api/auth/me", headers=new_headers)
    assert me_res.status_code == 200

    # 2. Test User Preferences GET & PATCH
    prefs_get = client.get("/v1/api/auth/me/preferences", headers=new_headers)
    assert prefs_get.status_code == 200
    assert "default_workspace" in prefs_get.json()

    patch_payload = {
        "default_workspace": "doctor",
        "theme": "dark",
        "default_ward_id": 101,
        "default_department_id": 202,
    }
    prefs_patch = client.patch("/v1/api/auth/me/preferences", headers=new_headers, json=patch_payload)
    assert prefs_patch.status_code == 200
    assert prefs_patch.json()["default_ward_id"] == 101
    assert prefs_patch.json()["theme"] == "dark"


def test_quick_patient_search_and_summary_card(client: TestClient, superuser_headers: dict):
    # 1. Register a test patient
    patient_payload = {
        "full_name": "Siddharth Verma",
        "date_of_birth": "1988-11-20T00:00:00Z",
        "gender": "MALE",
        "phone_number": "9123456780",
        "blood_group": "B+",
        "abha_number": "ABHA-UI-9999",
    }
    create_res = client.post("/v1/api/patients", headers=superuser_headers, json=patient_payload)
    assert create_res.status_code == 201
    patient_id = create_res.json()["id"]
    mrn = create_res.json()["mrn"]

    # 2. Test Quick Search by MRN and Name
    search_mrn = client.get(f"/v1/api/ui/patients/quick-search?q={mrn[:6]}", headers=superuser_headers)
    assert search_mrn.status_code == 200
    results = search_mrn.json()
    assert len(results) >= 1
    found = next((p for p in results if p["id"] == patient_id), None)
    assert found is not None
    assert found["full_name"] == "Siddharth Verma"
    assert found["blood_group"] == "B+"

    search_name = client.get("/v1/api/ui/patients/quick-search?q=Siddharth", headers=superuser_headers)
    assert search_name.status_code == 200
    assert any(p["id"] == patient_id for p in search_name.json())

    # 3. Test Consolidated Summary Card
    card_res = client.get(f"/v1/api/ui/patients/{patient_id}/summary-card", headers=superuser_headers)
    assert card_res.status_code == 200
    card = card_res.json()
    assert card["patient_id"] == patient_id
    assert card["mrn"] == mrn
    assert card["full_name"] == "Siddharth Verma"
    assert "critical_allergies" in card
    assert "active_diagnoses" in card


def test_doctor_queue_today(client: TestClient, superuser_headers: dict):
    # Query queue for current user
    queue_res = client.get("/v1/api/ui/doctor/queue-today", headers=superuser_headers)
    assert queue_res.status_code == 200
    data = queue_res.json()
    assert "total_scheduled" in data
    assert "checked_in" in data
    assert "in_consultation" in data
    assert "completed" in data
    assert "appointments" in data
    assert isinstance(data["appointments"], list)


def test_cashier_shift_workflow(client: TestClient, superuser_headers: dict):
    # 1. Initially check shift status
    initial_status = client.get("/v1/api/ui/billing/shift-status", headers=superuser_headers)
    assert initial_status.status_code == 200

    # 2. Open a cashier shift
    open_payload = {
        "counter_id": "COUNTER-OPD-01",
        "starting_float_paise": 500000,  # 5,000 INR
    }
    open_res = client.post("/v1/api/ui/billing/shifts/open", headers=superuser_headers, json=open_payload)
    assert open_res.status_code == 200
    assert open_res.json()["status"] == "success"

    # 3. Verify shift status is now open
    opened_status = client.get("/v1/api/ui/billing/shift-status", headers=superuser_headers)
    assert opened_status.status_code == 200
    assert opened_status.json()["is_open"] is True
    assert opened_status.json()["counter_id"] == "COUNTER-OPD-01"
    assert opened_status.json()["starting_float_paise"] == 500000

    # 4. Close the cashier shift
    close_payload = {
        "physical_cash_counted_paise": 500000,
        "handover_notes": "All counter vouchers verified. Handed over to night supervisor.",
    }
    close_res = client.post("/v1/api/ui/billing/shifts/close", headers=superuser_headers, json=close_payload)
    assert close_res.status_code == 200
    assert close_res.json()["status"] == "success"
    summary = close_res.json()["summary"]
    assert summary["counter_id"] == "COUNTER-OPD-01"
    assert summary["variance_paise"] == 0

    # 5. Verify shift status is now closed
    closed_status = client.get("/v1/api/ui/billing/shift-status", headers=superuser_headers)
    assert closed_status.status_code == 200
    assert closed_status.json()["is_open"] is False
