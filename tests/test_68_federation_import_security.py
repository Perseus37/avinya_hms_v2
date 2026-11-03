def test_federated_import_rejects_tampered_discovery_payload(
    client,
    superuser_headers,
    apollo_admin_headers,
    sunrise_admin_headers,
):
    """Federated import must not accept edited demographics from the caller."""
    sun_client = client.post(
        "/v1/api/federation/clients",
        headers=sunrise_admin_headers,
        json={"branch_code": "SUN-IMPORT-SEC-01", "name": "Sunrise Import Security"},
    ).json()

    client.post(
        "/v1/api/patients",
        headers=apollo_admin_headers,
        json={
            "full_name": "Source Of Truth Patient",
            "date_of_birth": "1988-02-03T00:00:00Z",
            "gender": "FEMALE",
            "phone_number": "9000012345",
            "abha_number": "ABHA-IMPORT-SEC-01",
            "address": "Source Address",
        },
    )

    discovered = client.get(
        "/v1/api/federation/patients/discover?abha_number=ABHA-IMPORT-SEC-01&purpose=CONTINUITY_OF_CARE",
        headers={"X-Federation-API-Key": sun_client["raw_api_key"]},
    )
    assert discovered.status_code == 200
    payload = discovered.json()
    payload["full_name"] = "Attacker Controlled Name"

    imported = client.post(
        "/v1/api/federation/patients/import",
        headers=superuser_headers,
        json=payload,
    )
    assert imported.status_code == 409
    assert "changed since discovery" in imported.json()["detail"]


def test_federated_import_requires_indexed_source_mrn(client, superuser_headers):
    """The import endpoint must not become a generic patient-creation API."""
    payload = {
        "source_mrn": "MRN-NOT-IN-DISCOVERY",
        "full_name": "Fabricated Patient",
        "date_of_birth": "1990-01-01T00:00:00Z",
        "gender": "MALE",
        "blood_group": None,
        "phone_number": "9111111111",
        "email": None,
        "address": "Fabricated Address",
        "emergency_contact_name": None,
        "emergency_contact_phone": None,
        "abha_number": "ABHA-FABRICATED-01",
        "active_allergies": [],
    }

    response = client.post(
        "/v1/api/federation/patients/import",
        headers=superuser_headers,
        json=payload,
    )
    assert response.status_code == 404
    assert "not currently indexed" in response.json()["detail"]
