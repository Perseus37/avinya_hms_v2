"""Regression coverage for privacy enforcement on UI patient aggregates and exports."""

import backend.domains.ui.router as ui_router
import backend.domains.patients.router as patient_router
from backend.domains.privacy.decision_engine import ConsentDecision


def _deny_many(_db, *, patient_ages, **_kwargs):
    return {
        patient_id: ConsentDecision(
            allowed=False,
            reason_code="consent_missing_or_invalid",
            purpose_code="INTERNAL_CARE",
            mode="ENFORCE",
            would_deny=True,
        )
        for patient_id in patient_ages
    }


def _deny_one(*_args, **_kwargs):
    return ConsentDecision(
        allowed=False,
        reason_code="consent_missing_or_invalid",
        purpose_code="INTERNAL_CARE",
        mode="ENFORCE",
        would_deny=True,
    )


def _create_patient(client, headers):
    response = client.post(
        "/v1/api/patients",
        headers=headers,
        json={
            "full_name": "Privacy Restricted Patient",
            "date_of_birth": "1990-01-02T00:00:00Z",
            "gender": "FEMALE",
            "phone_number": "9000012345",
            "abha_number": "ABHA-PRIVACY-UI-01",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_ui_patient_search_summary_and_timeline_enforce_privacy(
    client, superuser_headers, monkeypatch
):
    patient = _create_patient(client, superuser_headers)
    monkeypatch.setattr(ui_router, "evaluate_tenant_data_use_for_patients", _deny_many)
    monkeypatch.setattr(ui_router, "evaluate_tenant_data_use", _deny_one)

    quick_search = client.get(
        "/v1/api/ui/patients/quick-search?q=Privacy%20Restricted",
        headers=superuser_headers,
    )
    assert quick_search.status_code == 200, quick_search.text
    assert quick_search.json() == []

    summary = client.get(
        f"/v1/api/ui/patients/{patient['id']}/summary-card",
        headers=superuser_headers,
    )
    assert summary.status_code == 403, summary.text

    timeline = client.get(
        f"/v1/api/ui/patients/{patient['id']}/timeline",
        headers=superuser_headers,
    )
    assert timeline.status_code == 403, timeline.text


def test_patient_csv_export_does_not_bypass_mpi_privacy(
    client, superuser_headers, monkeypatch
):
    _create_patient(client, superuser_headers)
    monkeypatch.setattr(
        patient_router, "evaluate_tenant_data_use_for_patients", _deny_many
    )

    exported = client.get(
        "/v1/api/patients?format=csv",
        headers=superuser_headers,
    )
    assert exported.status_code == 200, exported.text
    assert "Privacy Restricted Patient" not in exported.text
