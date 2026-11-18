from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import sessionmaker

from backend.domains.bloodbank.models import BloodCrossMatchOrder


def _create_patient_with_blood_group(client, doctor_headers, blood_group="O+"):
    p = client.post(
        "/v1/api/patients",
        headers=doctor_headers,
        json={
            "full_name": f"Blood {blood_group} Patient",
            "date_of_birth": "1980-03-10T00:00:00Z",
            "gender": "FEMALE",
            "blood_group": blood_group,
        },
    ).json()
    enc = client.post(
        "/v1/api/adt/encounters",
        headers=doctor_headers,
        json={"patient_id": p["id"], "encounter_type": "IPD", "primary_doctor_id": 2, "department_id": 1},
    ).json()
    return p, enc


def test_01_blood_bank_blocks_incompatible_abo_rh_cross_match_with_409_hard_stop(
    client, superuser_headers, doctor_headers
):
    """
    Scenario 1: Recipient is O+ (can only receive O+ or O- PRBC).
    - Attempting to cross-match an A+ PRBC bag for an O+ patient is blocked with 409 Biological Hard-Stop!
    - Attempting to cross-match an O+ PRBC bag for an O- patient (Rh mismatch) is blocked with 409!
    """
    now = datetime.now(timezone.utc)
    bag_a_pos = client.post(
        "/v1/api/blood-bank/bags",
        headers=superuser_headers,
        json={
            "bag_number": "BAG-APOS-001",
            "component_type": "PRBC",
            "blood_group": "A+",
            "volume_ml": 350,
            "collection_date": (now - timedelta(days=2)).isoformat(),
            "expiry_date": (now + timedelta(days=30)).isoformat(),
            "processing_fee_paise": 180000,
        },
    ).json()

    bag_o_pos = client.post(
        "/v1/api/blood-bank/bags",
        headers=superuser_headers,
        json={
            "bag_number": "BAG-OPOS-001",
            "component_type": "PRBC",
            "blood_group": "O+",
            "volume_ml": 350,
            "collection_date": (now - timedelta(days=2)).isoformat(),
            "expiry_date": (now + timedelta(days=30)).isoformat(),
            "processing_fee_paise": 180000,
        },
    ).json()

    # 1. O+ Recipient vs A+ Donor PRBC -> 409 Biological Hard-Stop
    _, enc_o_pos = _create_patient_with_blood_group(client, doctor_headers, blood_group="O+")
    res_abo_fail = client.post(
        "/v1/api/blood-bank/cross-match",
        headers=superuser_headers,
        json={"encounter_id": enc_o_pos["id"], "blood_bag_id": bag_a_pos["id"], "ordered_by_doctor_id": 2},
    )
    assert res_abo_fail.status_code == 409
    assert "biological hard-stop" in res_abo_fail.json()["message"].lower()

    # 2. O- Recipient vs O+ Donor PRBC (Rh+ into Rh-) -> 409 Biological Hard-Stop
    _, enc_o_neg = _create_patient_with_blood_group(client, doctor_headers, blood_group="O-")
    res_rh_fail = client.post(
        "/v1/api/blood-bank/cross-match",
        headers=superuser_headers,
        json={"encounter_id": enc_o_neg["id"], "blood_bag_id": bag_o_pos["id"], "ordered_by_doctor_id": 2},
    )
    assert res_rh_fail.status_code == 409


def test_02_universal_donor_o_neg_cross_match_issue_auto_billing_and_reaction_quarantine(
    client, superuser_headers, doctor_headers, nurse_headers, billing_headers, multi_tenant_env
):
    """
    Scenario 2:
    - O- PRBC (Universal Red Cell Donor) is compatible with AB+ recipient -> Cross-match succeeds (201).
    - Issuing the bag transitions status to ISSUED and auto-bills 220,000 paise (₹2,200) to the encounter's DRAFT invoice.
    - Reporting a Febrile Non-Hemolytic transfusion reaction halts the transfusion and marks the bag REACTION_HALTED.
    """
    now = datetime.now(timezone.utc)
    bag_o_neg = client.post(
        "/v1/api/blood-bank/bags",
        headers=superuser_headers,
        json={
            "bag_number": "BAG-ONEG-UNIV-01",
            "component_type": "PRBC",
            "blood_group": "O-",
            "volume_ml": 350,
            "collection_date": (now - timedelta(days=1)).isoformat(),
            "expiry_date": (now + timedelta(days=35)).isoformat(),
            "processing_fee_paise": 220000,
        },
    ).json()

    p, enc_ab_pos = _create_patient_with_blood_group(client, doctor_headers, blood_group="AB+")

    # 1. Cross-match O- PRBC for AB+ patient -> 201
    cm_res = client.post(
        "/v1/api/blood-bank/cross-match",
        headers=superuser_headers,
        json={"encounter_id": enc_ab_pos["id"], "blood_bag_id": bag_o_neg["id"], "ordered_by_doctor_id": 2},
    )
    assert cm_res.status_code == 201
    cm_id = cm_res.json()["id"]
    assert cm_res.json()["blood_bag"]["status"] == "CROSS_MATCHED"

    # 2. Issue bag for transfusion -> Auto-bills 220,000 paise to DRAFT invoice
    issue_res = client.patch(f"/v1/api/blood-bank/cross-match/{cm_id}/issue", headers=nurse_headers)
    assert issue_res.status_code == 200
    assert issue_res.json()["blood_bag"]["status"] == "ISSUED"

    inv = client.get(f"/v1/api/billing/invoices?patient_id={p['id']}", headers=billing_headers).json()["items"][0]
    assert inv["total_amount_paise"] == 220000
    assert "BLOOD BANK [Bag #BAG-ONEG-UNIV-01]" in inv["line_items"][0]["description"]

    # NONE is not an adverse reaction and must not consume the immutable report slot.
    none_first_res = client.patch(
        f"/v1/api/blood-bank/cross-match/{cm_id}/reaction",
        headers=nurse_headers,
        json={"reaction_type": "NONE", "reaction_notes": "No adverse reaction observed"},
    )
    assert none_first_res.status_code == 400

    # 3. Report adverse transfusion reaction -> Quarantines bag as REACTION_HALTED
    rxn_res = client.patch(
        f"/v1/api/blood-bank/cross-match/{cm_id}/reaction",
        headers=nurse_headers,
        json={
            "reaction_type": "FEBRILE_NON_HEMOLYTIC",
            "reaction_notes": "Chills and temp spike of 1.5C at 15 mins; transfusion stopped immediately, IV line kept open with NS.",
        },
    )
    assert rxn_res.status_code == 200
    assert rxn_res.json()["blood_bag"]["status"] == "REACTION_HALTED"

    # The first reaction report is an immutable clinical record. A later report
    # must not replace it or clear it by sending NONE.
    overwrite_res = client.patch(
        f"/v1/api/blood-bank/cross-match/{cm_id}/reaction",
        headers=nurse_headers,
        json={"reaction_type": "ACUTE_HEMOLYTIC", "reaction_notes": "Conflicting second report"},
    )
    assert overwrite_res.status_code == 409
    clear_res = client.patch(
        f"/v1/api/blood-bank/cross-match/{cm_id}/reaction",
        headers=nurse_headers,
        json={"reaction_type": "NONE", "reaction_notes": None},
    )
    assert clear_res.status_code == 409
    assert clear_res.json()["message"] == overwrite_res.json()["message"]

    # Verify both rejected updates left the original clinical record unchanged.
    TestSession = sessionmaker(bind=multi_tenant_env["tenant_engines"]["hms_default"])
    with TestSession() as db:
        persisted = db.get(BloodCrossMatchOrder, cm_id)
        assert persisted is not None
        assert persisted.reaction_type.value == rxn_res.json()["reaction_type"]
        assert persisted.reaction_notes == rxn_res.json()["reaction_notes"]


def test_03_pacs_dicom_study_attaches_to_radiology_task_and_blocks_lab_tasks(
    client, superuser_headers, doctor_headers
):
    """
    Scenario 3:
    - Attaching PACS DICOM study metadata to a LAB task (Hemoglobin) is blocked with 400.
    - Attaching PACS DICOM study metadata (StudyInstanceUID, Modality CT, Viewer URL, Radiation Dose) to a RADIOLOGY task succeeds!
    """
    cat = client.post("/v1/api/diagnostics/categories", headers=superuser_headers, json={"department_id": 1, "code": "CAT_PACS", "name": "PACS Imaging"}).json()
    lab_svc = client.post(
        "/v1/api/diagnostics/catalog",
        headers=superuser_headers,
        json={"category_id": cat["id"], "code": "LAB_CRP_PACS", "name": "C-Reactive Protein", "service_type": "LAB", "base_price_paise": 40000, "is_order_set": False},
    ).json()
    rad_svc = client.post(
        "/v1/api/diagnostics/catalog",
        headers=superuser_headers,
        json={"category_id": cat["id"], "code": "RAD_HRCT_CHEST", "name": "HRCT Chest Scan", "service_type": "RADIOLOGY", "base_price_paise": 350000, "is_order_set": False},
    ).json()

    p, _ = _create_patient_with_blood_group(client, doctor_headers, blood_group="B+")
    order = client.post(
        "/v1/api/diagnostics/orders",
        headers=doctor_headers,
        json={"patient_id": p["id"], "ordered_service_ids": [lab_svc["id"], rad_svc["id"]]},
    ).json()

    lab_task_id = next(t["id"] for t in order["tasks"] if t["service_id"] == lab_svc["id"])
    rad_task_id = next(t["id"] for t in order["tasks"] if t["service_id"] == rad_svc["id"])

    dicom_payload = {
        "study_instance_uid": "1.2.840.113619.2.55.3.604688433.781.1700000001",
        "accession_number": "ACC-HYD-2026-0091",
        "modality": "CT",
        "pacs_viewer_url": "https://pacs.avinyahms.com/viewer?study=1.2.840.113619.2.55.3.604688433.781.1700000001",
        "radiation_dose_mgy": 6.4,
        "radiologist_impression": "No focal consolidation, pleural effusion, or pneumothorax.",
    }

    # 1. Cannot attach DICOM study to a LAB task -> 400 Bad Request
    assert client.put(
        f"/v1/api/diagnostics/tasks/{lab_task_id}/dicom-study",
        headers=doctor_headers,
        json=dicom_payload,
    ).status_code == 400

    # 2. Attach DICOM study to RADIOLOGY task -> 200 OK
    rad_res = client.put(
        f"/v1/api/diagnostics/tasks/{rad_task_id}/dicom-study",
        headers=doctor_headers,
        json=dicom_payload,
    )
    assert rad_res.status_code == 200
    assert rad_res.json()["modality"] == "CT"
    assert rad_res.json()["radiation_dose_mgy"] == 6.4

    get_res = client.get(f"/v1/api/diagnostics/tasks/{rad_task_id}/dicom-study", headers=doctor_headers)
    assert get_res.status_code == 200
    assert get_res.json()["accession_number"] == "ACC-HYD-2026-0091"


def test_04_expired_blood_bag_issue_rejected_with_409(client, superuser_headers, doctor_headers):
    """
    Scenario 4: A blood bag cross-matched earlier that has now passed its expiry date
    must be rejected at issue time with HTTP 409 and marked as EXPIRED.
    """
    from sqlalchemy.orm import Session
    from backend.core.database import tenant_engine_pool
    from backend.domains.bloodbank.models import BloodBagInventory

    now = datetime.now(timezone.utc)
    bag = client.post(
        "/v1/api/blood-bank/bags",
        headers=superuser_headers,
        json={
            "bag_number": "BAG-EXPIRED-TEST-01",
            "component_type": "PRBC",
            "blood_group": "O+",
            "volume_ml": 350,
            "collection_date": (now - timedelta(days=10)).isoformat(),
            "expiry_date": (now + timedelta(days=20)).isoformat(),
            "processing_fee_paise": 150000,
        },
    ).json()

    _, enc = _create_patient_with_blood_group(client, doctor_headers, blood_group="O+")
    cm = client.post(
        "/v1/api/blood-bank/cross-match",
        headers=superuser_headers,
        json={"encounter_id": enc["id"], "blood_bag_id": bag["id"], "ordered_by_doctor_id": 2},
    ).json()

    # Simulate bag expiring in the refrigerator before issue
    engine = tenant_engine_pool.get_engine("hms_default")
    with Session(engine) as session:
        db_bag = session.get(BloodBagInventory, bag["id"])
        db_bag.expiry_date = now - timedelta(hours=1)
        session.commit()

    issue_res = client.patch(
        f"/v1/api/blood-bank/cross-match/{cm['id']}/issue",
        headers=superuser_headers,
    )
    assert issue_res.status_code == 409
    assert "expired" in issue_res.json()["message"].lower()



def test_05_future_collection_date_rejected_on_receipt_cross_match_and_issue(
    client, superuser_headers, doctor_headers
):
    from sqlalchemy.orm import Session
    from backend.core.database import tenant_engine_pool
    from backend.domains.bloodbank.models import BloodBagInventory

    now = datetime.now(timezone.utc)
    future_payload = {
        "component_type": "PRBC",
        "blood_group": "O+",
        "volume_ml": 350,
        "collection_date": (now + timedelta(days=1)).isoformat(),
        "expiry_date": (now + timedelta(days=30)).isoformat(),
        "processing_fee_paise": 0,
    }
    rejected = client.post(
        "/v1/api/blood-bank/bags",
        headers=superuser_headers,
        json={"bag_number": "BAG-FUTURE-COLLECTION-01", **future_payload},
    )
    assert rejected.status_code == 400
    assert "collection date cannot be in the future" in rejected.json()["message"].lower()

    valid = client.post(
        "/v1/api/blood-bank/bags",
        headers=superuser_headers,
        json={
            **future_payload,
            "bag_number": "BAG-FUTURE-COLLECTION-02",
            "collection_date": (now - timedelta(days=1)).isoformat(),
        },
    ).json()
    _, enc = _create_patient_with_blood_group(client, doctor_headers, blood_group="O+")
    engine = tenant_engine_pool.get_engine("hms_default")
    with Session(engine) as session:
        db_bag = session.get(BloodBagInventory, valid["id"])
        db_bag.collection_date = now + timedelta(days=1)
        session.commit()

    cross_match = client.post(
        "/v1/api/blood-bank/cross-match",
        headers=superuser_headers,
        json={"encounter_id": enc["id"], "blood_bag_id": valid["id"], "ordered_by_doctor_id": 2},
    )
    assert cross_match.status_code == 409
    assert "collection date cannot be in the future" in cross_match.json()["message"].lower()

    # Create a valid cross-match, then simulate a corrupted/future-dated legacy row
    # to ensure issue-time validation independently enforces the same safety rule.
    with Session(engine) as session:
        db_bag = session.get(BloodBagInventory, valid["id"])
        db_bag.collection_date = now - timedelta(days=1)
        session.commit()
    cm = client.post(
        "/v1/api/blood-bank/cross-match",
        headers=superuser_headers,
        json={"encounter_id": enc["id"], "blood_bag_id": valid["id"], "ordered_by_doctor_id": 2},
    ).json()
    with Session(engine) as session:
        db_bag = session.get(BloodBagInventory, valid["id"])
        db_bag.collection_date = now + timedelta(days=1)
        session.commit()
    issue = client.patch(
        f"/v1/api/blood-bank/cross-match/{cm['id']}/issue",
        headers=superuser_headers,
    )
    assert issue.status_code == 409
    assert "future collection date" in issue.json()["message"].lower()


def test_06_ffp_uses_full_abo_plasma_compatibility_matrix_and_ignores_rh(
    client, superuser_headers, doctor_headers
):
    """Exercise all donor/recipient ABO groups; Rh(D) does not restrict FFP."""
    now = datetime.now(timezone.utc)
    blood_groups = ("O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+")
    compatible_donors = {
        "O-": {"O-", "O+"},
        "O+": {"O-", "O+"},
        "A-": {"A-", "A+", "AB-", "AB+"},
        "A+": {"A-", "A+", "AB-", "AB+"},
        "B-": {"B-", "B+", "AB-", "AB+"},
        "B+": {"B-", "B+", "AB-", "AB+"},
        "AB-": set(blood_groups),
        "AB+": set(blood_groups),
    }

    for recipient_group in blood_groups:
        _, encounter = _create_patient_with_blood_group(
            client, doctor_headers, blood_group=recipient_group
        )
        for donor_group in blood_groups:
            bag_response = client.post(
                "/v1/api/blood-bank/bags",
                headers=superuser_headers,
                json={
                    "bag_number": f"FFP-{recipient_group.replace('+', 'P').replace('-', 'N')}-{donor_group.replace('+', 'P').replace('-', 'N')}",
                    "component_type": "FFP",
                    "blood_group": donor_group,
                    "volume_ml": 250,
                    "collection_date": (now - timedelta(days=1)).isoformat(),
                    "expiry_date": (now + timedelta(days=20)).isoformat(),
                    "processing_fee_paise": 0,
                },
            )
            assert bag_response.status_code == 201, bag_response.text

            response = client.post(
                "/v1/api/blood-bank/cross-match",
                headers=superuser_headers,
                json={
                    "encounter_id": encounter["id"],
                    "blood_bag_id": bag_response.json()["id"],
                    "ordered_by_doctor_id": 2,
                },
            )
            expected_status = 201 if donor_group in compatible_donors[recipient_group] else 409
            assert response.status_code == expected_status, (
                f"FFP donor {donor_group} to recipient {recipient_group}: "
                f"expected {expected_status}, got {response.status_code}: {response.text}"
            )
            if expected_status == 201:
                assert response.json()["blood_bag"]["status"] == "CROSS_MATCHED"


def test_07_pacs_metadata_and_impression_are_immutable_after_verification(
    client, superuser_headers, doctor_headers
):
    from sqlalchemy.orm import Session
    from backend.core.database import tenant_engine_pool
    from backend.domains.diagnostics.models import DiagnosticTask, TaskStatusEnum

    cat = client.post(
        "/v1/api/diagnostics/categories", headers=superuser_headers,
        json={"department_id": 1, "code": "CAT_PACS_LOCK", "name": "PACS Lock"},
    ).json()
    svc = client.post(
        "/v1/api/diagnostics/catalog", headers=superuser_headers,
        json={"category_id": cat["id"], "code": "RAD_PACS_LOCK", "name": "CT Chest",
              "service_type": "RADIOLOGY", "base_price_paise": 100000, "is_order_set": False},
    ).json()
    patient, _ = _create_patient_with_blood_group(client, doctor_headers)
    order = client.post(
        "/v1/api/diagnostics/orders", headers=doctor_headers,
        json={"patient_id": patient["id"], "ordered_service_ids": [svc["id"]]},
    ).json()
    task_id = order["tasks"][0]["id"]
    original = {
        "study_instance_uid": "1.2.840.10008.5.1.4.1.1.2.202611150001",
        "accession_number": "ACC-PACS-LOCK-001", "modality": "CT",
        "pacs_viewer_url": "https://pacs.example.test/study/001",
        "radiation_dose_mgy": 4.2, "radiologist_impression": "No acute thoracic finding.",
    }
    attached = client.put(
        f"/v1/api/diagnostics/tasks/{task_id}/dicom-study",
        headers=doctor_headers, json=original,
    )
    assert attached.status_code == 200

    engine = tenant_engine_pool.get_engine("hms_default")
    with Session(engine) as session:
        task = session.get(DiagnosticTask, task_id)
        task.status = TaskStatusEnum.VERIFIED
        session.commit()

    changed = {**original, "radiologist_impression": "Replacement impression."}
    update = client.put(
        f"/v1/api/diagnostics/tasks/{task_id}/dicom-study",
        headers=doctor_headers, json=changed,
    )
    assert update.status_code == 409
    current = client.get(
        f"/v1/api/diagnostics/tasks/{task_id}/dicom-study", headers=doctor_headers,
    )
    assert current.status_code == 200
    assert current.json()["radiologist_impression"] == original["radiologist_impression"]


def test_08_pacs_metadata_cannot_be_attached_to_cancelled_task(
    client, superuser_headers, doctor_headers
):
    from sqlalchemy.orm import Session
    from backend.core.database import tenant_engine_pool
    from backend.domains.diagnostics.models import DiagnosticTask, TaskStatusEnum

    cat = client.post(
        "/v1/api/diagnostics/categories", headers=superuser_headers,
        json={"department_id": 1, "code": "CAT_PACS_CANCEL", "name": "PACS Cancel"},
    ).json()
    svc = client.post(
        "/v1/api/diagnostics/catalog", headers=superuser_headers,
        json={"category_id": cat["id"], "code": "RAD_PACS_CANCEL", "name": "CT Chest",
              "service_type": "RADIOLOGY", "base_price_paise": 100000, "is_order_set": False},
    ).json()
    patient, _ = _create_patient_with_blood_group(client, doctor_headers)
    order = client.post(
        "/v1/api/diagnostics/orders", headers=doctor_headers,
        json={"patient_id": patient["id"], "ordered_service_ids": [svc["id"]]},
    ).json()
    task_id = order["tasks"][0]["id"]

    engine = tenant_engine_pool.get_engine("hms_default")
    with Session(engine) as session:
        task = session.get(DiagnosticTask, task_id)
        task.status = TaskStatusEnum.CANCELLED
        session.commit()

    payload = {
        "study_instance_uid": "1.2.840.10008.5.1.4.1.1.2.202611150002",
        "accession_number": "ACC-PACS-CANCEL-001", "modality": "CT",
        "pacs_viewer_url": "https://pacs.example.test/study/002",
        "radiation_dose_mgy": 3.1, "radiologist_impression": "Should not be attached.",
    }
    response = client.put(
        f"/v1/api/diagnostics/tasks/{task_id}/dicom-study",
        headers=doctor_headers, json=payload,
    )
    assert response.status_code == 409



def test_pacs_metadata_cannot_be_attached_to_completed_order(
    client, superuser_headers, doctor_headers
):
    from sqlalchemy.orm import Session
    from backend.core.database import tenant_engine_pool
    from backend.domains.diagnostics.models import DiagnosticOrder, OrderStatusEnum

    cat = client.post(
        "/v1/api/diagnostics/categories", headers=superuser_headers,
        json={"department_id": 1, "code": "CAT_PACS_ORDER_DONE", "name": "PACS Order Done"},
    ).json()
    svc = client.post(
        "/v1/api/diagnostics/catalog", headers=superuser_headers,
        json={"category_id": cat["id"], "code": "RAD_PACS_ORDER_DONE", "name": "CT Chest",
              "service_type": "RADIOLOGY", "base_price_paise": 100000, "is_order_set": False},
    ).json()
    patient, _ = _create_patient_with_blood_group(client, doctor_headers)
    order = client.post(
        "/v1/api/diagnostics/orders", headers=doctor_headers,
        json={"patient_id": patient["id"], "ordered_service_ids": [svc["id"]]},
    ).json()
    task_id = order["tasks"][0]["id"]

    engine = tenant_engine_pool.get_engine("hms_default")
    with Session(engine) as session:
        db_order = session.get(DiagnosticOrder, order["id"])
        db_order.status = OrderStatusEnum.COMPLETED
        session.commit()

    payload = {
        "study_instance_uid": "1.2.840.10008.5.1.4.1.1.2.202611150003",
        "accession_number": "ACC-PACS-ORDER-DONE-001", "modality": "CT",
        "pacs_viewer_url": "https://pacs.example.test/study/003",
        "radiation_dose_mgy": 2.8, "radiologist_impression": "Should not be attached.",
    }
    response = client.put(
        f"/v1/api/diagnostics/tasks/{task_id}/dicom-study",
        headers=doctor_headers, json=payload,
    )
    assert response.status_code == 409
    assert "completed diagnostic order" in response.json()["message"].lower()
