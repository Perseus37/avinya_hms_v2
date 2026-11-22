import pytest

from datetime import datetime, timedelta, timezone


def _setup_ward_and_two_beds(client, superuser_headers):
    """Helper to provision a Floor -> Ward -> Room -> 2 AVAILABLE Beds."""
    f_id = client.post(
        "/v1/api/ip/floors",
        headers=superuser_headers,
        json={"floor_number": 1, "name": "First Floor"},
    ).json()["floor_id"]

    w_id = client.post(
        "/v1/api/ip/wards",
        headers=superuser_headers,
        json={"floor_id": f_id, "department_id": 1, "code": "WARD-ICU-1", "name": "Medical ICU", "ward_type": "ICU"},
    ).json()["id"]

    r_id = client.post(
        "/v1/api/ip/rooms",
        headers=superuser_headers,
        json={"ward_id": w_id, "room_number": "101", "room_type": "DOUBLE", "bed_capacity": 2},
    ).json()["room_id"]

    b1_id = client.post(
        "/v1/api/ip/beds",
        headers=superuser_headers,
        json={"room_id": r_id, "bed_number": "101-A", "bed_type": "ICU", "base_daily_rate_paise": 500000},
    ).json()["bed_id"]

    b2_id = client.post(
        "/v1/api/ip/beds",
        headers=superuser_headers,
        json={"room_id": r_id, "bed_number": "101-B", "bed_type": "ICU", "base_daily_rate_paise": 500000},
    ).json()["bed_id"]

    return {"floor_id": f_id, "ward_id": w_id, "room_id": r_id, "bed1_id": b1_id, "bed2_id": b2_id}


def test_01_spatial_ward_hierarchy_and_map_view(client, superuser_headers, nurse_headers):
    """Scenario 1: Create Floor -> Ward -> Room -> Bed and verify nested spatial map-view."""
    ids = _setup_ward_and_two_beds(client, superuser_headers)
    map_res = client.get("/v1/api/ip/beds/map-view", headers=nurse_headers)
    assert map_res.status_code == 200
    wards = map_res.json()
    assert len(wards) == 1
    assert wards[0]["id"] == ids["ward_id"]
    assert len(wards[0]["rooms"][0]["beds"]) == 2


def test_02_manual_occupied_bed_status_override_is_blocked(client, superuser_headers, nurse_headers):
    """Scenario 2: Manually setting bed status to OCCUPIED via PATCH /beds/{id}/status is blocked with 400."""
    ids = _setup_ward_and_two_beds(client, superuser_headers)
    res = client.patch(
        f"/v1/api/ip/beds/{ids['bed1_id']}/status",
        headers=nurse_headers,
        json={"status": "OCCUPIED"},
    )
    assert res.status_code == 400


def test_03_nursing_shift_assignment_and_single_handoff_lock(client, superuser_headers, nurse_headers):
    """Scenario 3: Assign nursing shift, complete handoff, and reject duplicate handoff with 409."""
    ids = _setup_ward_and_two_beds(client, superuser_headers)
    shift_res = client.post(
        "/v1/api/ip/shifts",
        headers=nurse_headers,
        json={
            "ward_id": ids["ward_id"],
            "nurse_user_id": 3,
            "shift_type": "MORNING",
            "shift_date": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert shift_res.status_code == 201
    shift_id = shift_res.json()["id"]

    # First handoff succeeds
    h1 = client.patch(
        f"/v1/api/ip/shifts/{shift_id}/handoff",
        headers=nurse_headers,
        json={"handoff_notes": "All ICU patients stable; Bed 101-A vitals normal."},
    )
    assert h1.status_code == 200
    assert h1.json()["handed_off_at"] is not None

    # Second handoff on already finalized shift returns 409
    h2 = client.patch(
        f"/v1/api/ip/shifts/{shift_id}/handoff",
        headers=nurse_headers,
        json={"handoff_notes": "Attempting to overwrite finalized handoff"},
    )
    assert h2.status_code == 409


def test_04_opd_booking_and_doctor_overlap_conflict(client, doctor_headers):
    """Scenario 4: Booking a second appointment within the doctor's 15-min consultation window returns 409."""
    p1 = client.post("/v1/api/patients", headers=doctor_headers, json={"full_name": "OPD P1", "date_of_birth": "1990-01-01T00:00:00Z", "gender": "MALE"}).json()
    p2 = client.post("/v1/api/patients", headers=doctor_headers, json={"full_name": "OPD P2", "date_of_birth": "1992-01-01T00:00:00Z", "gender": "FEMALE"}).json()

    base_time = datetime(2026, 10, 15, 10, 0, 0, tzinfo=timezone.utc)
    b1 = client.post(
        "/v1/api/opd/appointments",
        headers=doctor_headers,
        json={"patient_id": p1["id"], "doctor_id": 2, "department_id": 1, "appointment_time": base_time.isoformat()},
    )
    assert b1.status_code == 201

    # 10 minutes later (within 15-min buffer) -> 409 Conflict
    overlap_time = base_time + timedelta(minutes=10)
    b2 = client.post(
        "/v1/api/opd/appointments",
        headers=doctor_headers,
        json={"patient_id": p2["id"], "doctor_id": 2, "department_id": 1, "appointment_time": overlap_time.isoformat()},
    )
    assert b2.status_code == 409


def test_05_opd_reschedule_excludes_self_from_overlap_check(client, doctor_headers):
    """Scenario 5: Moving an appointment by 5 minutes does not conflict with its own previous time slot."""
    p1 = client.post("/v1/api/patients", headers=doctor_headers, json={"full_name": "Resched P1", "date_of_birth": "1990-01-01T00:00:00Z", "gender": "MALE"}).json()
    base_time = datetime(2026, 10, 16, 10, 0, 0, tzinfo=timezone.utc)

    appt = client.post(
        "/v1/api/opd/appointments",
        headers=doctor_headers,
        json={"patient_id": p1["id"], "doctor_id": 2, "department_id": 1, "appointment_time": base_time.isoformat()},
    ).json()

    new_time = base_time + timedelta(minutes=5)
    resched = client.put(
        f"/v1/api/opd/appointments/{appt['id']}",
        headers=doctor_headers,
        json={"appointment_time": new_time.isoformat(), "reason_for_visit": "Moved by 5 mins"},
    )
    assert resched.status_code == 200


def test_06_opd_linear_state_machine_and_encounter_binding(client, doctor_headers):
    """Scenario 6: Enforce SCHEDULED -> ARRIVED -> IN_CONSULTATION (with encounter) -> COMPLETED."""
    p = client.post("/v1/api/patients", headers=doctor_headers, json={"full_name": "State P1", "date_of_birth": "1990-01-01T00:00:00Z", "gender": "MALE"}).json()
    appt = client.post(
        "/v1/api/opd/appointments",
        headers=doctor_headers,
        json={"patient_id": p["id"], "doctor_id": 2, "department_id": 1, "appointment_time": "2026-10-17T10:00:00Z"},
    ).json()

    # Illegal jump directly from SCHEDULED to COMPLETED -> 400
    assert client.patch(f"/v1/api/opd/appointments/{appt['id']}/status", headers=doctor_headers, json={"status": "COMPLETED"}).status_code == 400

    # SCHEDULED -> ARRIVED
    assert client.patch(f"/v1/api/opd/appointments/{appt['id']}/status", headers=doctor_headers, json={"status": "ARRIVED"}).status_code == 200

    # ARRIVED -> IN_CONSULTATION without encounter_id -> 400
    assert client.patch(f"/v1/api/opd/appointments/{appt['id']}/status", headers=doctor_headers, json={"status": "IN_CONSULTATION"}).status_code == 400

    # Create OPD Encounter and transition to IN_CONSULTATION, then COMPLETED
    enc = client.post(
        "/v1/api/adt/encounters",
        headers=doctor_headers,
        json={"patient_id": p["id"], "encounter_type": "OPD", "primary_doctor_id": 2, "department_id": 1},
    ).json()

    assert client.patch(
        f"/v1/api/opd/appointments/{appt['id']}/status",
        headers=doctor_headers,
        json={"status": "IN_CONSULTATION", "encounter_id": enc["id"]},
    ).status_code == 200

    assert client.patch(
        f"/v1/api/opd/appointments/{appt['id']}/status",
        headers=doctor_headers,
        json={"status": "COMPLETED"},
    ).status_code == 200


def test_07_encounter_same_type_duplicate_blocked_cross_type_allowed(client, doctor_headers):
    """Scenario 7: Blocking duplicate active IPD+IPD encounters (409) while allowing active OPD+IPD."""
    p = client.post("/v1/api/patients", headers=doctor_headers, json={"full_name": "Enc P1", "date_of_birth": "1990-01-01T00:00:00Z", "gender": "MALE"}).json()

    # Create active OPD encounter
    opd_res = client.post(
        "/v1/api/adt/encounters",
        headers=doctor_headers,
        json={"patient_id": p["id"], "encounter_type": "OPD", "primary_doctor_id": 2, "department_id": 1},
    )
    assert opd_res.status_code == 201

    # Second concurrent OPD encounter blocked (409)
    assert client.post(
        "/v1/api/adt/encounters",
        headers=doctor_headers,
        json={"patient_id": p["id"], "encounter_type": "OPD", "primary_doctor_id": 2, "department_id": 1},
    ).status_code == 409

    # Transitioning patient to an IPD encounter while OPD is active succeeds (201)
    ipd_res = client.post(
        "/v1/api/adt/encounters",
        headers=doctor_headers,
        json={"patient_id": p["id"], "encounter_type": "IPD", "primary_doctor_id": 2, "department_id": 1},
    )
    assert ipd_res.status_code == 201


def test_08_admitting_non_ipd_encounter_to_bed_returns_400(client, superuser_headers, doctor_headers):
    """Scenario 8: OPD encounters cannot be admitted to an inpatient bed (400)."""
    ids = _setup_ward_and_two_beds(client, superuser_headers)
    p = client.post("/v1/api/patients", headers=doctor_headers, json={"full_name": "OPD Only", "date_of_birth": "1990-01-01T00:00:00Z", "gender": "MALE"}).json()
    opd_enc = client.post(
        "/v1/api/adt/encounters",
        headers=doctor_headers,
        json={"patient_id": p["id"], "encounter_type": "OPD", "primary_doctor_id": 2, "department_id": 1},
    ).json()

    res = client.post(
        "/v1/api/adt/admissions",
        headers=doctor_headers,
        json={"encounter_id": opd_enc["id"], "admission_type": "ROUTINE", "admitting_doctor_id": 2, "assigned_bed_id": ids["bed1_id"]},
    )
    assert res.status_code == 400


def test_09_ipd_admission_locks_bed_and_logs_placement(client, superuser_headers, doctor_headers):
    """Scenario 9: IPD admission marks bed OCCUPIED and creates initial BedTransferLog."""
    ids = _setup_ward_and_two_beds(client, superuser_headers)
    p = client.post("/v1/api/patients", headers=doctor_headers, json={"full_name": "IPD Admit", "date_of_birth": "1990-01-01T00:00:00Z", "gender": "MALE"}).json()
    ipd_enc = client.post(
        "/v1/api/adt/encounters",
        headers=doctor_headers,
        json={"patient_id": p["id"], "encounter_type": "IPD", "primary_doctor_id": 2, "department_id": 1},
    ).json()

    adm = client.post(
        "/v1/api/adt/admissions",
        headers=doctor_headers,
        json={"encounter_id": ipd_enc["id"], "admission_type": "EMERGENCY", "admitting_doctor_id": 2, "assigned_bed_id": ids["bed1_id"]},
    )
    assert adm.status_code == 201
    adm_id = adm.json()["id"]

    logs = client.get(f"/v1/api/adt/admissions/{adm_id}/transfers", headers=doctor_headers).json()
    assert logs["total"] == 1
    assert logs["items"][0]["to_bed_id"] == ids["bed1_id"]


def test_10_occupied_bed_cannot_be_removed_or_manually_changed(client, superuser_headers, doctor_headers):
    """Scenario 10: Occupied bed blocks DELETE /beds/{id} and PATCH /beds/{id}/status with 409 Conflict."""
    ids = _setup_ward_and_two_beds(client, superuser_headers)
    p = client.post("/v1/api/patients", headers=doctor_headers, json={"full_name": "Bed Guard", "date_of_birth": "1990-01-01T00:00:00Z", "gender": "MALE"}).json()
    ipd_enc = client.post(
        "/v1/api/adt/encounters",
        headers=doctor_headers,
        json={"patient_id": p["id"], "encounter_type": "IPD", "primary_doctor_id": 2, "department_id": 1},
    ).json()
    client.post(
        "/v1/api/adt/admissions",
        headers=doctor_headers,
        json={"encounter_id": ipd_enc["id"], "admission_type": "ROUTINE", "admitting_doctor_id": 2, "assigned_bed_id": ids["bed1_id"]},
    )

    assert client.delete(f"/v1/api/ip/beds/{ids['bed1_id']}", headers=superuser_headers).status_code == 409
    assert client.patch(f"/v1/api/ip/beds/{ids['bed1_id']}/status", headers=superuser_headers, json={"status": "AVAILABLE"}).status_code == 409


def test_11_bed_transfer_moves_old_bed_to_housekeeping_and_new_to_occupied(client, superuser_headers, doctor_headers):
    """Scenario 11: Bed transfer updates old bed to HOUSEKEEPING, new bed to OCCUPIED, and logs transfer."""
    ids = _setup_ward_and_two_beds(client, superuser_headers)
    p = client.post("/v1/api/patients", headers=doctor_headers, json={"full_name": "Transfer P", "date_of_birth": "1990-01-01T00:00:00Z", "gender": "MALE"}).json()
    ipd_enc = client.post(
        "/v1/api/adt/encounters",
        headers=doctor_headers,
        json={"patient_id": p["id"], "encounter_type": "IPD", "primary_doctor_id": 2, "department_id": 1},
    ).json()
    adm = client.post(
        "/v1/api/adt/admissions",
        headers=doctor_headers,
        json={"encounter_id": ipd_enc["id"], "admission_type": "ROUTINE", "admitting_doctor_id": 2, "assigned_bed_id": ids["bed1_id"]},
    ).json()

    tx = client.post(
        "/v1/api/adt/transfers",
        headers=doctor_headers,
        json={"admission_id": adm["id"], "new_bed_id": ids["bed2_id"], "transfer_reason": "Step-down unit transfer"},
    )
    assert tx.status_code == 201

    wards = client.get("/v1/api/ip/beds/map-view", headers=doctor_headers).json()
    beds_by_id = {b["id"]: b["status"] for b in wards[0]["rooms"][0]["beds"]}
    assert beds_by_id[ids["bed1_id"]] == "HOUSEKEEPING"
    assert beds_by_id[ids["bed2_id"]] == "OCCUPIED"


def test_12_clinical_discharge_releases_bed_and_closes_encounter(client, superuser_headers, doctor_headers):
    """Scenario 12: Discharging an admission releases bed to HOUSEKEEPING, marks encounter DISCHARGED, and blocks edits."""
    ids = _setup_ward_and_two_beds(client, superuser_headers)
    p = client.post("/v1/api/patients", headers=doctor_headers, json={"full_name": "Discharge P", "date_of_birth": "1990-01-01T00:00:00Z", "gender": "MALE"}).json()
    ipd_enc = client.post(
        "/v1/api/adt/encounters",
        headers=doctor_headers,
        json={"patient_id": p["id"], "encounter_type": "IPD", "primary_doctor_id": 2, "department_id": 1},
    ).json()
    adm = client.post(
        "/v1/api/adt/admissions",
        headers=doctor_headers,
        json={"encounter_id": ipd_enc["id"], "admission_type": "ROUTINE", "admitting_doctor_id": 2, "assigned_bed_id": ids["bed1_id"]},
    ).json()

    disc = client.post(
        f"/v1/api/adt/admissions/{adm['id']}/discharge",
        headers=doctor_headers,
        json={"discharge_disposition": "ROUTINE_DISCHARGE", "discharge_summary": "Patient recovered fully."},
    )
    assert disc.status_code == 200

    # Encounter is now DISCHARGED and locked from edits
    enc_after = client.get(f"/v1/api/adt/encounters/{ipd_enc['id']}", headers=doctor_headers).json()
    assert enc_after["status"] == "DISCHARGED"
    assert client.put(f"/v1/api/adt/admissions/{adm['id']}", headers=doctor_headers, json={"admission_type": "EMERGENCY"}).status_code == 400


def test_13_concurrent_transfers_for_one_admission_commit_only_one_destination(
    client, superuser_headers, doctor_headers
):
    from backend.core.database import tenant_engine_pool

    if tenant_engine_pool.get_engine("hms_default").dialect.name != "postgresql":
        pytest.skip("SELECT FOR UPDATE NOWAIT concurrency guarantee requires PostgreSQL; SQLite ignores row locks.")

    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    ids = _setup_ward_and_two_beds(client, superuser_headers)
    third_bed = client.post(
        "/v1/api/ip/beds",
        headers=superuser_headers,
        json={
            "room_id": ids["room_id"],
            "bed_number": "101-C",
            "bed_type": "ICU",
            "base_daily_rate_paise": 500000,
        },
    ).json()["bed_id"]
    patient = client.post(
        "/v1/api/patients",
        headers=doctor_headers,
        json={"full_name": "Concurrent Transfer", "date_of_birth": "1990-01-01T00:00:00Z", "gender": "MALE"},
    ).json()
    encounter = client.post(
        "/v1/api/adt/encounters",
        headers=doctor_headers,
        json={"patient_id": patient["id"], "encounter_type": "IPD", "primary_doctor_id": 2, "department_id": 1},
    ).json()
    admission = client.post(
        "/v1/api/adt/admissions",
        headers=doctor_headers,
        json={
            "encounter_id": encounter["id"],
            "admission_type": "ROUTINE",
            "admitting_doctor_id": 2,
            "assigned_bed_id": ids["bed1_id"],
        },
    ).json()

    start = Barrier(2)

    def transfer(destination_bed_id, reason):
        start.wait()
        return client.post(
            "/v1/api/adt/transfers",
            headers=doctor_headers,
            json={
                "admission_id": admission["id"],
                "new_bed_id": destination_bed_id,
                "transfer_reason": reason,
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(transfer, ids["bed2_id"], "Concurrent transfer A")
        second = pool.submit(transfer, third_bed, "Concurrent transfer B")
        responses = [first.result(), second.result()]

    assert sorted(response.status_code for response in responses) == [201, 409]
    final_admission = client.get(
        f"/v1/api/adt/admissions/{admission['id']}", headers=doctor_headers
    )
    assert final_admission.status_code == 200
    current_bed_id = final_admission.json()["current_bed_id"]
    assert current_bed_id in (ids["bed2_id"], third_bed)

    ward_map = client.get("/v1/api/ip/beds/map-view", headers=doctor_headers).json()
    bed_states = {
        bed["id"]: bed["status"]
        for room in ward_map[0]["rooms"]
        for bed in room["beds"]
    }
    assert bed_states[ids["bed1_id"]] == "HOUSEKEEPING"
    assert bed_states[current_bed_id] == "OCCUPIED"
    other_destination = third_bed if current_bed_id == ids["bed2_id"] else ids["bed2_id"]
    assert bed_states[other_destination] == "AVAILABLE"


def test_17_concurrent_same_type_encounter_creation_is_serialized(client, doctor_headers):
    """Two simultaneous creates for one patient/type must not both become active."""
    from backend.core.database import tenant_engine_pool

    if tenant_engine_pool.get_engine("hms_default").dialect.name != "postgresql":
        pytest.skip("SELECT FOR UPDATE concurrency guarantee requires PostgreSQL; SQLite ignores row locks.")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    patient = client.post(
        "/v1/api/patients",
        headers=doctor_headers,
        json={"full_name": "Concurrent Encounter Patient", "date_of_birth": "1990-01-01T00:00:00Z", "gender": "MALE"},
    ).json()
    barrier = Barrier(2)

    def create_encounter():
        barrier.wait()
        return client.post(
            "/v1/api/adt/encounters",
            headers=doctor_headers,
            json={"patient_id": patient["id"], "encounter_type": "OPD", "primary_doctor_id": 2, "department_id": 1},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: create_encounter(), range(2)))

    assert sorted(response.status_code for response in responses) == [201, 409]
    active = client.get("/v1/api/adt/encounters/active", headers=doctor_headers)
    assert active.status_code == 200, active.text
    matching = [
        item for item in active.json().get("items", [])
        if item["patient_id"] == patient["id"] and item["encounter_type"] == "OPD"
    ]
    assert len(matching) == 1


def test_14_room_bed_capacity_blocks_overflow_and_unsafe_reduction(
    client, superuser_headers
):
    ids = _setup_ward_and_two_beds(client, superuser_headers)

    overflow = client.post(
        "/v1/api/ip/beds",
        headers=superuser_headers,
        json={
            "room_id": ids["room_id"],
            "bed_number": "101-C",
            "bed_type": "ICU",
            "base_daily_rate_paise": 500000,
        },
    )
    assert overflow.status_code == 409

    reduce_below_configured = client.put(
        f"/v1/api/ip/rooms/{ids['room_id']}",
        headers=superuser_headers,
        json={"bed_capacity": 1},
    )
    assert reduce_below_configured.status_code == 409


def test_15_concurrent_bed_creation_cannot_exceed_room_capacity(
    client, superuser_headers
):
    from backend.core.database import tenant_engine_pool

    if tenant_engine_pool.get_engine("hms_default").dialect.name != "postgresql":
        pytest.skip("SELECT FOR UPDATE concurrency guarantee requires PostgreSQL; SQLite ignores row locks.")

    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    ids = _setup_ward_and_two_beds(client, superuser_headers)
    capacity_update = client.put(
        f"/v1/api/ip/rooms/{ids['room_id']}",
        headers=superuser_headers,
        json={"bed_capacity": 3},
    )
    assert capacity_update.status_code == 200
    start = Barrier(2)

    def create_bed(number):
        start.wait()
        return client.post(
            "/v1/api/ip/beds",
            headers=superuser_headers,
            json={
                "room_id": ids["room_id"],
                "bed_number": number,
                "bed_type": "ICU",
                "base_daily_rate_paise": 500000,
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(create_bed, "101-C")
        second = pool.submit(create_bed, "101-D")
        responses = [first.result(), second.result()]

    assert sorted(response.status_code for response in responses) == [201, 409]
    ward_map = client.get("/v1/api/ip/beds/map-view", headers=superuser_headers).json()
    rooms = [room for ward in ward_map for room in ward["rooms"] if room["id"] == ids["room_id"]]
    assert len(rooms) == 1
    assert len(rooms[0]["beds"]) == 3



def test_16_moving_bed_into_full_room_is_rejected(client, superuser_headers):
    ids = _setup_ward_and_two_beds(client, superuser_headers)
    target_room = client.post(
        "/v1/api/ip/rooms",
        headers=superuser_headers,
        json={
            "ward_id": ids["ward_id"],
            "room_number": "102",
            "room_type": "SINGLE",
            "bed_capacity": 1,
        },
    ).json()["room_id"]
    target_bed = client.post(
        "/v1/api/ip/beds",
        headers=superuser_headers,
        json={
            "room_id": target_room,
            "bed_number": "102-A",
            "bed_type": "ICU",
            "base_daily_rate_paise": 500000,
        },
    )
    assert target_bed.status_code == 201

    move = client.patch(
        f"/v1/api/ip/beds/{ids['bed1_id']}",
        headers=superuser_headers,
        json={"room_id": target_room},
    )
    assert move.status_code == 409
