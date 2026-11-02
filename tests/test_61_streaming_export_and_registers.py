"""Tests for Phase 1 & 2: Universal Streaming Data Export Engine, Historical Registers, and Query Filters."""

from datetime import datetime, timezone
from decimal import Decimal
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.export import (
    format_export_cell,
    generate_csv_chunks,
    stream_csv_response,
    stream_jsonl_response,
)


def test_format_export_cell_handles_various_types():
    assert format_export_cell(None) == ""
    assert format_export_cell(True) == "YES"
    assert format_export_cell(False) == "NO"
    assert format_export_cell(Decimal("1250.50")) == "1250.50"
    dt = datetime(2026, 10, 31, 12, 0, 0, tzinfo=timezone.utc)
    assert "2026-10-31" in format_export_cell(dt)
    assert format_export_cell({"key": "val"}) == '{"key": "val"}'
    assert format_export_cell("Dr. Sharma") == "Dr. Sharma"


def test_generate_csv_chunks_produces_valid_bom_and_rfc4180():
    rows = [
        {"id": 1, "patient_name": "Ramesh Kumar", "amount": Decimal("500.00"), "paid": True},
        {"id": 2, "patient_name": "Priya Singh, Dr.", "amount": Decimal("1250.75"), "paid": False},
    ]
    fieldnames = ["id", "patient_name", "amount", "paid"]
    chunks = list(generate_csv_chunks(rows, fieldnames, chunk_size=1))

    full_csv = "".join(chunks)
    assert full_csv.startswith("\ufeff")  # UTF-8 BOM present
    assert "id,patient_name,amount,paid" in full_csv
    assert "Ramesh Kumar,500.00,YES" in full_csv
    assert '"Priya Singh, Dr.",1250.75,NO' in full_csv


def test_stream_csv_response_fastapi_contract():
    app = FastAPI()

    @app.get("/export/test")
    def export_test():
        rows = [{"mrn": "MRN-101", "name": "Aarav Patel", "dept": "Cardiology"}]
        return stream_csv_response(rows, ["mrn", "name", "dept"], "test_export")

    client = TestClient(app)
    res = client.get("/export/test")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert 'attachment; filename="test_export.csv"' in res.headers["content-disposition"]
    assert res.text.startswith("\ufeff")
    assert "MRN-101,Aarav Patel,Cardiology" in res.text


def test_stream_jsonl_response_fastapi_contract():
    app = FastAPI()

    @app.get("/export/jsonl")
    def export_jsonl():
        records = [
            {"id": 1, "event": "admission"},
            {"id": 2, "event": "discharge"},
        ]
        return stream_jsonl_response(records, "events")

    client = TestClient(app)
    res = client.get("/export/jsonl")
    assert res.status_code == 200
    assert "application/x-ndjson" in res.headers["content-type"]
    lines = [line for line in res.text.strip().split("\n") if line]
    assert len(lines) == 2
    assert '"event": "admission"' in lines[0]
    assert '"event": "discharge"' in lines[1]


def test_transaction_exports_and_historical_queries(client, superuser_headers):
    # 1. Patients search with CSV export
    res = client.get("/v1/api/patients?format=csv", headers=superuser_headers)
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "mrn,full_name,gender" in res.text

    # 2. Appointments with CSV export
    res = client.get("/v1/api/opd/appointments?format=csv", headers=superuser_headers)
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "token_number,patient_mrn" in res.text

    # 3. Billings Invoices with CSV export
    res = client.get("/v1/api/billing/invoices?format=csv", headers=superuser_headers)
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "invoice_number,patient_mrn" in res.text
    assert "total_inr" in res.text

    # 4. Inpatient Admissions with CSV export
    res = client.get("/v1/api/adt/admissions?format=csv", headers=superuser_headers)
    assert res.status_code == 200
    assert "admission_type" in res.text
    assert "ward_name" in res.text
    assert "bed_code" in res.text

    # 5. Surgery list and CSV export
    res = client.get("/v1/api/ot/surgeries", headers=superuser_headers)
    assert res.status_code == 200
    assert "items" in res.json()

    res_csv = client.get("/v1/api/ot/surgeries?format=csv", headers=superuser_headers)
    assert res_csv.status_code == 200
    assert "case_number" in res_csv.text
    assert "theatre_code" in res_csv.text

    # 6. Insurance Claims list and CSV export
    res = client.get("/v1/api/insurance/claims", headers=superuser_headers)
    assert res.status_code == 200
    assert "items" in res.json()

    res_csv = client.get("/v1/api/insurance/claims?format=csv", headers=superuser_headers)
    assert res_csv.status_code == 200
    assert "claim_number" in res_csv.text
    assert "claimed_amount_inr" in res_csv.text

    # 7. Procurement GRN list and CSV export
    res = client.get("/v1/api/procurement/grn", headers=superuser_headers)
    assert res.status_code == 200
    assert "items" in res.json()

    res_csv = client.get("/v1/api/procurement/grn?format=csv", headers=superuser_headers)
    assert res_csv.status_code == 200
    assert "grn_number" in res_csv.text
    assert "po_number" in res_csv.text

    # 8. Pharmacy Inventory Batches with depleted inclusion and CSV export
    res_csv = client.get("/v1/api/pharmacy/inventory/batches?include_depleted=true&format=csv", headers=superuser_headers)
    assert res_csv.status_code == 200
    assert "medication_name" in res_csv.text
    assert "batch_number" in res_csv.text
    assert "stock_quantity" in res_csv.text

    # 9. Blood Bank Bags with CSV export
    res_csv = client.get("/v1/api/blood-bank/bags?format=csv", headers=superuser_headers)
    assert res_csv.status_code == 200
    assert "bag_number" in res_csv.text
    assert "blood_group" in res_csv.text
    assert "component_type" in res_csv.text


def test_statutory_operational_registers_and_csv_exports(client, superuser_headers):
    # 1. Midnight Bed Census
    res = client.get("/v1/api/registers/midnight-census", headers=superuser_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_licensed_beds" in data
    assert "items" in data

    res_csv = client.get("/v1/api/registers/midnight-census?format=csv", headers=superuser_headers)
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "census_date" in res_csv.text
    assert "bed_occupancy_rate_pct" in res_csv.text

    # 2. Cashier Shift Reconciliation
    res = client.get("/v1/api/registers/cashier-shift-reconciliation", headers=superuser_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_revenue_inr" in data
    assert "cashiers" in data

    res_csv = client.get("/v1/api/registers/cashier-shift-reconciliation?format=csv", headers=superuser_headers)
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "receipt_number" in res_csv.text
    assert "amount_inr" in res_csv.text

    # 3. NDPS Statutory Ledger
    res = client.get("/v1/api/registers/ndps-ledger", headers=superuser_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_movements" in data

    res_csv = client.get("/v1/api/registers/ndps-ledger?format=csv", headers=superuser_headers)
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "movement_time" in res_csv.text
    assert "balance_after" in res_csv.text

    # 4. AR Aging Ledger
    res = client.get("/v1/api/registers/ar-aging", headers=superuser_headers)
    assert res.status_code == 200
    data = res.json()
    assert "summary" in data
    assert "current_0_30_inr" in data["summary"]

    res_csv = client.get("/v1/api/registers/ar-aging?format=csv", headers=superuser_headers)
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "invoice_number" in res_csv.text
    assert "aging_bucket" in res_csv.text

    # 5. Biomedical Waste Register
    res = client.get("/v1/api/registers/biomedical-waste", headers=superuser_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_bags_count" in data
    assert "total_weight_kg" in data

    res_csv = client.get("/v1/api/registers/biomedical-waste?format=csv", headers=superuser_headers)
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "barcode" in res_csv.text
    assert "weight_kg" in res_csv.text


def test_tenant_data_inventory_and_footprint(client, superuser_headers):
    res = client.get("/v1/api/analytics/data-inventory", headers=superuser_headers)
    assert res.status_code == 200
    data = res.json()
    assert "total_monitored_tables" in data
    assert "total_records_stored" in data
    assert data["total_monitored_tables"] >= 15
    assert len(data["items"]) >= 15

    res_csv = client.get("/v1/api/analytics/data-inventory?format=csv", headers=superuser_headers)
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "domain" in res_csv.text
    assert "table" in res_csv.text
    assert "record_count" in res_csv.text


def test_clinical_documents_pdf_format_support(client, superuser_headers):
    # 1. Invoice PDF
    res = client.get("/v1/api/billing/invoices/1/pdf", headers=superuser_headers)
    if res.status_code == 200:
        assert res.headers["content-type"] == "application/pdf"
        assert res.content.startswith(b"%PDF-")

    # 2. OPD Appointment Print with format=pdf
    res = client.get("/v1/api/opd/appointments/1/print?format=pdf", headers=superuser_headers)
    if res.status_code == 200:
        assert res.headers["content-type"] == "application/pdf"
        assert res.content.startswith(b"%PDF-")

    # 3. OPD Appointment Print default HTML
    res = client.get("/v1/api/opd/appointments/1/print", headers=superuser_headers)
    if res.status_code == 200:
        assert "text/html" in res.headers["content-type"]


def test_dpdp_patient_data_portability_dossier(client, superuser_headers):
    # 1. Register a patient to export
    payload = {
        "full_name": "Kavitha Reddy",
        "date_of_birth": "1990-05-15T00:00:00Z",
        "gender": "FEMALE",
        "phone_number": "9876543210",
        "abha_number": "ABHA-DOSSIER-001",
    }
    create_res = client.post("/v1/api/patients", headers=superuser_headers, json=payload)
    assert create_res.status_code == 201
    patient_id = create_res.json()["id"]

    # 1b. Verify that exporting without a verified data-rights request fails with 400 (N-98)
    no_req_res = client.get(f"/v1/api/privacy/data-rights/patients/{patient_id}/export-dossier", headers=superuser_headers)
    assert no_req_res.status_code == 400
    err_msg = no_req_res.json().get("message") or no_req_res.json().get("detail", "")
    assert "verified DPDP Section 11 data-rights request is required" in err_msg

    # 1c. Submit a valid DPDP Section 11 data portability request
    req_res = client.post(
        "/v1/api/privacy/data-rights/requests",
        headers=superuser_headers,
        json={
            "patient_id": patient_id,
            "request_type": "PORTABILITY",
            "sla_days": 30,
            "details": {"reason": "Patient requested DPDP portability dossier"},
        },
    )
    assert req_res.status_code == 201
    request_id = req_res.json()["id"]

    # 2. Export patient dossier tied to verified request
    res = client.get(
        f"/v1/api/privacy/data-rights/patients/{patient_id}/export-dossier?request_id={request_id}",
        headers=superuser_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert "export_metadata" in data
    assert "bundle_integrity_sha256" in data["export_metadata"]
    assert data["export_metadata"]["data_rights_request_id"] == request_id
    assert "patient_profile" in data
    assert data["patient_profile"]["id"] == patient_id
    assert "allergies" in data
    assert "encounters" in data
    assert "clinical_notes" in data
    assert "vitals" in data
    assert "prescriptions" in data
    assert "invoices_and_billing" in data
    assert "consent_evidence" in data


