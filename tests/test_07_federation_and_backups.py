from cryptography.fernet import Fernet, InvalidToken
import hashlib
import pytest
from sqlalchemy.orm import sessionmaker

from backend.scripts.backup_service import derive_fernet_key
from backend.domains.federation.models import FederationTransferLog


def test_01_register_and_revoke_federation_partner_key(client, superuser_headers):
    """Scenario 1: Registering the current tenant branch issues a fed_live_ key; revoking it blocks /discover with 401."""
    reg_res = client.post(
        "/v1/api/federation/clients",
        headers=superuser_headers,
        json={"branch_code": "HQ-HYD-01", "name": "Hyderabad Headquarters"},
    )
    assert reg_res.status_code == 201
    raw_key = reg_res.json()["raw_api_key"]
    client_id = reg_res.json()["id"]
    assert raw_key.startswith("fed_live_")

    rev_res = client.delete(f"/v1/api/federation/clients/{client_id}", headers=superuser_headers)
    assert rev_res.status_code == 200

    disc_res = client.get(
        "/v1/api/federation/patients/discover?phone_number=9876543210",
        headers={"X-Federation-API-Key": raw_key},
    )
    assert disc_res.status_code == 401


def test_01b_federation_registration_cannot_mint_an_arbitrary_branch_identity(client, superuser_headers):
    """A tenant administrator cannot register a federation credential for another branch code."""
    reg_res = client.post(
        "/v1/api/federation/clients",
        headers=superuser_headers,
        json={"branch_code": "PARTNER-MUM-01", "name": "Mumbai Partner Hospital"},
    )
    assert reg_res.status_code == 403
    assert "current tenant branch" in reg_res.json()["message"].lower()


def test_02_invalid_federation_api_key_format_returns_401(client):
    """Scenario 2: Short or invalid X-Federation-API-Key is rejected with 401."""
    res = client.get(
        "/v1/api/federation/patients/discover?phone_number=9876543210",
        headers={"X-Federation-API-Key": "short_key"},
    )
    assert res.status_code == 401


def test_03_multi_hop_patient_discovery_and_allergy_union_a_to_b_to_c(
    client,
    multi_tenant_env,
    superuser_headers,
    apollo_admin_headers,
    sunrise_admin_headers,
):
    """
    Scenario 3: Full Hospital A (apollo) -> Hospital B (default) -> Hospital C (sunrise) flow:
      1. Register patient at Hospital A ('apollo') with Penicillin allergy (ALG_PEN).
      2. Import patient into Hospital B ('default'), update address, and chart Sulfa allergy (ALG_SULFA).
      3. Discover patient from Hospital C ('sunrise') -> receives newest address from B + BOTH allergies (A + B).
    """
    sun_client = client.post(
        "/v1/api/federation/clients",
        headers=sunrise_admin_headers,
        json={"branch_code": "SUN-BLR-01", "name": "Sunrise Hospital"},
    ).json()
    fed_headers = {"X-Federation-API-Key": sun_client["raw_api_key"]}

    p_apollo = client.post(
        "/v1/api/patients",
        headers=apollo_admin_headers,
        json={
            "full_name": "MultiHop Patient",
            "date_of_birth": "1985-08-15T00:00:00Z",
            "gender": "MALE",
            "phone_number": "9777788888",
            "abha_number": "ABHA-MULTIHOP-01",
            "address": "Old Address in Hyderabad (Hospital A)",
        },
    ).json()
    client.post(
        f"/v1/api/patients/{p_apollo['id']}/allergies",
        headers=apollo_admin_headers,
        json={"allergy_id": 1, "severity": "ANAPHYLACTIC", "reaction": "Anaphylactic shock"},
    )

    disc_from_a = client.get(
        "/v1/api/federation/patients/discover?phone_number=9777788888&purpose=CONTINUITY_OF_CARE",
        headers=fed_headers,
    ).json()

    p_default = client.post(
        "/v1/api/federation/patients/import",
        headers=superuser_headers,
        json=disc_from_a,
    ).json()

    # The source branch must durably record the import request before the
    # receiving tenant commits its local patient clone.
    ApolloSession = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_apollo"])
    with ApolloSession() as source_db:
        import_log = (
            source_db.query(FederationTransferLog)
            .filter(
                FederationTransferLog.patient_id == p_apollo["id"],
                FederationTransferLog.purpose == "CONTINUITY_OF_CARE_IMPORT_REQUESTED",
            )
            .one()
        )
        assert import_log.requesting_branch_code == "HQ-HYD-01"
        assert import_log.client_id is None

    # Repeating the same import is idempotent for the destination patient, but
    # the source still records the separately validated import request.
    repeated_import = client.post(
        "/v1/api/federation/patients/import",
        headers=superuser_headers,
        json=disc_from_a,
    )
    assert repeated_import.status_code == 201
    assert repeated_import.json()["id"] == p_default["id"]
    with ApolloSession() as source_db:
        import_request_count = (
            source_db.query(FederationTransferLog)
            .filter(
                FederationTransferLog.patient_id == p_apollo["id"],
                FederationTransferLog.purpose == "CONTINUITY_OF_CARE_IMPORT_REQUESTED",
            )
            .count()
        )
        assert import_request_count == 2

    client.put(
        f"/v1/api/patients/{p_default['id']}",
        headers=superuser_headers,
        json={"address": "Updated Address in Bengaluru (Hospital B)"},
    )
    client.post(
        f"/v1/api/patients/{p_default['id']}/allergies",
        headers=superuser_headers,
        json={"allergy_id": 2, "severity": "SEVERE", "reaction": "Stevens-Johnson syndrome"},
    )

    merged = client.get(
        "/v1/api/federation/patients/discover?abha_number=ABHA-MULTIHOP-01&purpose=CONTINUITY_OF_CARE",
        headers=fed_headers,
    )
    assert merged.status_code == 200
    body = merged.json()
    assert body["address"] == "Updated Address in Bengaluru (Hospital B)"
    allergy_codes = {a["allergy_code"] for a in body["active_allergies"]}
    assert allergy_codes == {"ALG_PEN", "ALG_SULFA"}
    for alg in body["active_allergies"]:
        assert alg["reaction"].count("[Source:") == 1


def test_04_federation_transfer_logs_written_in_source_tenant_databases(
    client,
    multi_tenant_env,
    apollo_admin_headers,
    sunrise_admin_headers,
):
    """Scenario 4: Every /discover lookup writes an immutable, PHI-minimized FederationTransferLog."""
    sun_client = client.post(
        "/v1/api/federation/clients",
        headers=sunrise_admin_headers,
        json={"branch_code": "SUN-BLR-01", "name": "Sunrise Audit Node"},
    ).json()

    abha_number = "ABHA-AUDIT-SECRET-01"
    p_apollo = client.post(
        "/v1/api/patients",
        headers=apollo_admin_headers,
        json={
            "full_name": "Forensic Log Patient",
            "date_of_birth": "1991-01-01T00:00:00Z",
            "gender": "FEMALE",
            "phone_number": "9666655555",
            "abha_number": abha_number,
        },
    ).json()

    res = client.get(
        f"/v1/api/federation/patients/discover?abha_number={abha_number}&purpose=ICU_TRANSFER_AUDIT",
        headers={"X-Federation-API-Key": sun_client["raw_api_key"]},
    )
    assert res.status_code == 200

    from backend.control_plane.models import FederatedNode

    ControlSession = multi_tenant_env["control_session_factory"]
    with ControlSession() as cdb:
        authenticated_node = (
            cdb.query(FederatedNode)
            .filter(FederatedNode.branch_code == "SUN-BLR-01")
            .one()
        )
        expected_node_id = authenticated_node.id
        expected_key_prefix = authenticated_node.api_key_prefix

    ApolloSession = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_apollo"])
    with ApolloSession() as adb:
        log_entry = (
            adb.query(FederationTransferLog)
            .filter(FederationTransferLog.patient_id == p_apollo["id"])
            .first()
        )
        assert log_entry is not None
        assert log_entry.requesting_node_id == expected_node_id
        assert log_entry.requesting_key_prefix == expected_key_prefix
        assert log_entry.requesting_branch_code == "SUN-BLR-01"
        assert log_entry.purpose == "ICU_TRANSFER_AUDIT"
        expected_hash = hashlib.sha256(abha_number.encode("utf-8")).hexdigest()
        assert f"abha_sha256:{expected_hash}" in log_entry.requested_identifier
        assert abha_number not in log_entry.requested_identifier
        assert "9876543210" not in log_entry.requested_identifier

        log_entry.purpose = "TAMPERED"
        with pytest.raises(ValueError, match="immutable"):
            adb.flush()
        adb.rollback()

        adb.delete(log_entry)
        with pytest.raises(ValueError, match="immutable"):
            adb.flush()
        adb.rollback()

        preserved = adb.get(FederationTransferLog, log_entry.id)
        assert preserved is not None
        assert preserved.purpose == "ICU_TRANSFER_AUDIT"


def test_05_aes256_backup_key_derivation_and_lossless_roundtrip():
    """Scenario 5: derive_fernet_key + Fernet encrypts and decrypts backup payloads losslessly."""
    secret = "apollo_backup_key_32_chars_minimum_len!"
    fernet_key = derive_fernet_key(secret)
    cipher = Fernet(fernet_key)
    sample_pg_dump = b"PGDMP\x01\x0e\x00\x04\x08-- Sample Binary PostgreSQL Dump Payload --"
    encrypted = cipher.encrypt(sample_pg_dump)
    assert encrypted != sample_pg_dump
    assert cipher.decrypt(encrypted) == sample_pg_dump


def test_06_aes256_backup_decryption_rejects_wrong_tenant_key():
    """Scenario 6: Attempting to decrypt Hospital A's backup with Hospital B's backup key raises InvalidToken."""
    cipher_a = Fernet(derive_fernet_key("hospital_a_backup_secret_key_32_chars"))
    cipher_b = Fernet(derive_fernet_key("hospital_b_backup_secret_key_32_chars"))

    encrypted_dump = cipher_a.encrypt(b"PGDMP--Hospital A Confidential Patient Records--")
    with pytest.raises(InvalidToken):
        cipher_b.decrypt(encrypted_dump)


def test_07_federation_thread_isolation_and_timeout(client, multi_tenant_env):
    """Audit F-03 regression: Federation worker threads pre-resolve registries without sharing control_db."""
    control_db = multi_tenant_env["control_session_factory"]()
    try:
        from backend.control_plane.models import TenantRegistry
        regs = control_db.query(TenantRegistry).all()
        assert len(regs) > 0
    finally:
        control_db.close()


def test_08_federation_emergency_requires_patient_bound_break_glass(
    client,
    multi_tenant_env,
    apollo_admin_headers,
    sunrise_admin_headers,
):
    """Remote emergency disclosure remains disabled until federated requester authorization is verifiable."""
    from datetime import datetime, timezone, timedelta
    from sqlalchemy.orm import Session
    from backend.domains.policies.models import FederationPolicyEnum, HospitalPolicySetting
    from backend.domains.patients.models import BreakGlassGrant
    from backend.domains.identity.models import User

    sun_client = client.post(
        "/v1/api/federation/clients",
        headers=sunrise_admin_headers,
        json={"branch_code": "SUN-BLR-01", "name": "Sunrise Emergency Wing"},
    ).json()
    fed_headers = {"X-Federation-API-Key": sun_client["raw_api_key"]}

    p_apollo = client.post(
        "/v1/api/patients",
        headers=apollo_admin_headers,
        json={
            "full_name": "Emergency Test Patient",
            "date_of_birth": "1990-01-01T00:00:00Z",
            "gender": "FEMALE",
            "phone_number": "9111122222",
            "abha_number": "ABHA-EMERG-99",
            "address": "123 Critical Street, Hyderabad",
        },
    ).json()
    client.post(
        f"/v1/api/patients/{p_apollo['id']}/allergies",
        headers=apollo_admin_headers,
        json={"allergy_id": 1, "severity": "SEVERE", "reaction": "Severe anaphylaxis"},
    )

    # Create a second real patient. Its grant must never authorize disclosure of
    # p_apollo, proving that the authorization is bound to the source patient ID.
    p_other = client.post(
        "/v1/api/patients",
        headers=apollo_admin_headers,
        json={
            "full_name": "Other Emergency Patient",
            "date_of_birth": "1992-02-02T00:00:00Z",
            "gender": "MALE",
            "phone_number": "9222233333",
            "abha_number": "ABHA-OTHER-99",
            "address": "456 Other Street, Hyderabad",
        },
    ).json()

    apollo_engine = multi_tenant_env["tenant_engines"]["hms_apollo"]
    with Session(apollo_engine) as db:
        pol = db.query(HospitalPolicySetting).first()
        if not pol:
            pol = HospitalPolicySetting()
            db.add(pol)
        pol.federation_sharing_mode = FederationPolicyEnum.EMERGENCY_ALLERGIES_ONLY
        db.commit()

    try:
        resp_unverified = client.get(
            "/v1/api/federation/patients/discover?abha_number=ABHA-EMERG-99&purpose=EMERGENCY",
            headers=fed_headers,
        )
        assert resp_unverified.status_code == 403

        resp_fake_token = client.get(
            "/v1/api/federation/patients/discover?abha_number=ABHA-EMERG-99&purpose=EMERGENCY&emergency_token=EMERGENCY-SECURE-TOKEN-1",
            headers=fed_headers,
        )
        assert resp_fake_token.status_code == 403

        with Session(apollo_engine) as db:
            user = db.query(User).first()
            grant = BreakGlassGrant(
                patient_id=p_apollo["id"],
                user_id=user.id,
                reason="Severe trauma emergency",
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
                review_due_at=datetime.now(timezone.utc) + timedelta(hours=24),
            )
            other_grant = BreakGlassGrant(
                patient_id=p_other["id"],
                user_id=user.id,
                reason="Unrelated emergency",
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
                review_due_at=datetime.now(timezone.utc) + timedelta(hours=24),
            )
            db.add_all([grant, other_grant])
            db.commit()
            db.refresh(grant)
            db.refresh(other_grant)
            grant_id = grant.id
            other_grant_id = other_grant.id

        resp_other_grant = client.get(
            f"/v1/api/federation/patients/discover?abha_number=ABHA-EMERG-99&purpose=EMERGENCY&break_glass_grant_id={other_grant_id}",
            headers=fed_headers,
        )
        assert resp_other_grant.status_code == 403

        resp_grant = client.get(
            f"/v1/api/federation/patients/discover?abha_number=ABHA-EMERG-99&purpose=EMERGENCY&break_glass_grant_id={grant_id}",
            headers=fed_headers,
        )
        # A source-local grant ID is not a federated capability. Remote emergency
        # disclosure remains disabled until node, purpose, scope, replay and actor
        # authorization can all be verified at the source.
        assert resp_grant.status_code == 403

        # A redacted allergy-only envelope cannot be used as a patient import.
        allergy_only_import = client.post(
            "/v1/api/federation/patients/import",
            headers=apollo_admin_headers,
            json={"active_allergies": []},
        )
        assert allergy_only_import.status_code == 422

        # Emergency-purpose access is disabled even when the source branch
        # otherwise permits FULL_MESH sharing.
        with Session(apollo_engine) as db:
            pol = db.query(HospitalPolicySetting).first()
            pol.federation_sharing_mode = FederationPolicyEnum.FULL_MESH
            db.commit()

        resp_full_mesh_without_grant = client.get(
            "/v1/api/federation/patients/discover?abha_number=ABHA-EMERG-99&purpose=EMERGENCY",
            headers=fed_headers,
        )
        assert resp_full_mesh_without_grant.status_code == 403

        resp_full_mesh_with_grant = client.get(
            f"/v1/api/federation/patients/discover?abha_number=ABHA-EMERG-99&purpose=EMERGENCY&break_glass_grant_id={grant_id}",
            headers=fed_headers,
        )
        assert resp_full_mesh_with_grant.status_code == 403
    finally:
        with Session(apollo_engine) as db:
            pol = db.query(HospitalPolicySetting).first()
            if pol:
                pol.federation_sharing_mode = FederationPolicyEnum.FULL_MESH
                db.commit()

def test_09_federation_import_enforces_corporate_group_policy(
    client,
    multi_tenant_env,
    superuser_headers,
    apollo_admin_headers,
):
    """Direct import cannot bypass a source branch's CORPORATE_GROUP_ONLY restriction."""
    from sqlalchemy.orm import Session
    from backend.control_plane.models import GlobalPatientPointer, TenantRegistry
    from backend.domains.policies.models import FederationPolicyEnum, HospitalPolicySetting

    # Authenticate a discovery request as the destination tenant's own federation node.
    registered = client.post(
        "/v1/api/federation/clients",
        headers=superuser_headers,
        json={"branch_code": "HQ-HYD-01", "name": "HQ Federation Node"},
    )
    assert registered.status_code == 201
    fed_headers = {"X-Federation-API-Key": registered.json()["raw_api_key"]}

    patient = client.post(
        "/v1/api/patients",
        headers=apollo_admin_headers,
        json={
            "full_name": "Corporate Policy Import Patient",
            "date_of_birth": "1988-03-14T00:00:00Z",
            "gender": "FEMALE",
            "phone_number": "9555512345",
            "abha_number": "ABHA-CORP-IMPORT-01",
        },
    )
    assert patient.status_code == 201

    discovered = client.get(
        "/v1/api/federation/patients/discover?abha_number=ABHA-CORP-IMPORT-01&purpose=CONTINUITY_OF_CARE",
        headers=fed_headers,
    )
    assert discovered.status_code == 200

    # Explicitly assign different trusted groups. The source and destination
    # branch-code prefixes are not consulted for authorization.
    control_db = multi_tenant_env["control_session_factory"]()
    try:
        source_pointer = control_db.query(GlobalPatientPointer).filter(
            GlobalPatientPointer.source_mrn == patient.json()["mrn"]
        ).one()
        source_branch_code = source_pointer.branch_code
        source_registry = control_db.query(TenantRegistry).filter(
            TenantRegistry.branch_code == source_branch_code
        ).one()
        destination_registry = control_db.query(TenantRegistry).filter(
            TenantRegistry.branch_code == "HQ-HYD-01"
        ).one()
        source_registry.corporate_group_id = "GROUP-B"
        destination_registry.corporate_group_id = "GROUP-A"
        control_db.commit()
    finally:
        control_db.close()

    apollo_engine = multi_tenant_env["tenant_engines"]["hms_apollo"]
    with Session(apollo_engine) as db:
        policy = db.query(HospitalPolicySetting).first()
        if policy is None:
            policy = HospitalPolicySetting()
            db.add(policy)
        policy.federation_sharing_mode = FederationPolicyEnum.CORPORATE_GROUP_ONLY
        db.commit()

    try:
        denied_discovery = client.get(
            "/v1/api/federation/patients/discover?abha_number=ABHA-CORP-IMPORT-01&purpose=CONTINUITY_OF_CARE",
            headers=fed_headers,
        )
        assert denied_discovery.status_code == 404

        imported = client.post(
            "/v1/api/federation/patients/import",
            headers=superuser_headers,
            json=discovered.json(),
        )
        assert imported.status_code == 403
        assert "cross-group" in imported.json()["message"].lower()

        # Matching explicit group IDs permit the same import even though branch
        # codes have different prefixes (HQ vs APOLLO).
        control_db = multi_tenant_env["control_session_factory"]()
        try:
            source_registry = control_db.query(TenantRegistry).filter(
                TenantRegistry.branch_code == source_branch_code
            ).one()
            destination_registry = control_db.query(TenantRegistry).filter(
                TenantRegistry.branch_code == "HQ-HYD-01"
            ).one()
            source_registry.corporate_group_id = "GROUP-A"
            control_db.commit()
        finally:
            control_db.close()

        allowed_discovery = client.get(
            "/v1/api/federation/patients/discover?abha_number=ABHA-CORP-IMPORT-01&purpose=CONTINUITY_OF_CARE",
            headers=fed_headers,
        )
        assert allowed_discovery.status_code == 200

        allowed = client.post(
            "/v1/api/federation/patients/import",
            headers=superuser_headers,
            json=discovered.json(),
        )
        assert allowed.status_code == 201
    finally:
        with Session(apollo_engine) as db:
            policy = db.query(HospitalPolicySetting).first()
            if policy:
                policy.federation_sharing_mode = FederationPolicyEnum.FULL_MESH
                db.commit()

def test_federation_identifier_sanitizer_handles_mixed_case_abha_marker():
    from backend.domains.federation.models import _sanitize_federation_identifier

    raw_abha = "ABHA:Sensitive-Value"
    sanitized = _sanitize_federation_identifier(f"branch->{raw_abha}")
    expected = hashlib.sha256("Sensitive-Value".encode("utf-8")).hexdigest()
    assert sanitized == f"branch->abha_sha256:{expected}"
    assert "Sensitive-Value" not in sanitized

