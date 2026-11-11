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
        json={"branch_code": "SUN-BLR-01", "name": "Sunrise Import Security"},
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
    assert "changed since discovery" in imported.json()["message"]


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
    assert "not currently indexed" in response.json()["message"]


def test_federation_does_not_discover_patients_through_missing_phone_placeholder(
    client, apollo_admin_headers, sunrise_admin_headers
):
    """Missing phone values must not be indexed or discoverable as 0000000000."""
    partner = client.post(
        "/v1/api/federation/clients",
        headers=sunrise_admin_headers,
        json={"branch_code": "SUN-BLR-01", "name": "No Phone Discovery Partner"},
    )
    assert partner.status_code == 201, partner.text

    patient = client.post(
        "/v1/api/patients",
        headers=apollo_admin_headers,
        json={
            "full_name": "No Phone Patient",
            "date_of_birth": "1991-05-06T00:00:00Z",
            "gender": "FEMALE",
            "abha_number": "ABHA-NO-PHONE-01",
        },
    )
    assert patient.status_code == 201, patient.text
    assert patient.json()["phone_number"] is None

    headers = {"X-Federation-API-Key": partner.json()["raw_api_key"]}
    placeholder_lookup = client.get(
        "/v1/api/federation/patients/discover?phone_number=0000000000",
        headers=headers,
    )
    assert placeholder_lookup.status_code == 404, placeholder_lookup.text

    abha_lookup = client.get(
        "/v1/api/federation/patients/discover?abha_number=ABHA-NO-PHONE-01",
        headers=headers,
    )
    assert abha_lookup.status_code == 200, abha_lookup.text
    assert abha_lookup.json()["source_mrn"] == patient.json()["mrn"]



def test_federation_reindexes_changed_phone_and_abha_identifiers(
    client, apollo_admin_headers, sunrise_admin_headers
):
    """Old identifiers stop resolving and new identifiers resolve after source updates."""
    partner = client.post(
        "/v1/api/federation/clients",
        headers=sunrise_admin_headers,
        json={"branch_code": "SUN-BLR-01", "name": "Federation Identity Update Partner"},
    )
    assert partner.status_code == 201, partner.text
    patient = client.post(
        "/v1/api/patients",
        headers=apollo_admin_headers,
        json={
            "full_name": "Federation Identifier Update",
            "date_of_birth": "1989-04-05T00:00:00Z",
            "gender": "FEMALE",
            "phone_number": "9000011122",
            "abha_number": "ABHA-OLD-IDENTIFIER-01",
        },
    )
    assert patient.status_code == 201, patient.text
    headers = {"X-Federation-API-Key": partner.json()["raw_api_key"]}

    updated = client.put(
        f"/v1/api/patients/{patient.json()['id']}",
        headers=apollo_admin_headers,
        json={
            "phone_number": "9000099988",
            "abha_number": "ABHA-NEW-IDENTIFIER-01",
        },
    )
    assert updated.status_code == 200, updated.text

    for stale_lookup in (
        "/v1/api/federation/patients/discover?phone_number=9000011122",
        "/v1/api/federation/patients/discover?abha_number=ABHA-OLD-IDENTIFIER-01",
    ):
        response = client.get(stale_lookup, headers=headers)
        assert response.status_code == 404, response.text

    for current_lookup in (
        "/v1/api/federation/patients/discover?phone_number=9000099988",
        "/v1/api/federation/patients/discover?abha_number=ABHA-NEW-IDENTIFIER-01",
    ):
        response = client.get(current_lookup, headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["source_mrn"] == patient.json()["mrn"]
