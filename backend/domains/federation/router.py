import hashlib
import json
from datetime import datetime, timedelta, timezone
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.control_plane.models import (
    FederatedDiscoveryReceipt,
    FederatedNode,
    GlobalPatientPointer,
    TenantRegistry,
)
from backend.core.database import get_control_db, get_db, resolve_tenant_context, tenant_engine_pool
from backend.core.dependencies import RateLimiter, RequirePermission, get_federated_node, validate_pagination
from backend.domains.identity.models import User
from backend.domains.patients.models import AllergyMaster, AllergySeverityEnum, Patient, PatientAllergy
from backend.domains.policies.models import FederationPolicyEnum, HospitalPolicySetting
from backend.domains.federation.models import FederatedClient, FederationTransferLog
from backend.domains.federation.schemas import (
    FederatedAllergySummary,
    FederatedClientCreate,
    FederatedClientCreatedResponse,
    FederatedClientResponse,
    FederatedPatientSummaryResponse,
)
from backend.schemas.common import PaginatedResponse
from backend.domains.patients.schemas import PatientResponse
from backend.domains.privacy.runtime import (
    calculate_patient_age,
    evaluate_tenant_data_use,
)

router = APIRouter(prefix="/api/federation", tags=["Central Discovery & Multi-Hop Federation"])


def normalize_phone_hash(phone_number: Optional[str]) -> str:
    """Normalizes phone digits and hashes with SHA-256 for privacy-preserving indexing."""
    digits = "".join(ch for ch in (phone_number or "") if ch.isdigit())[-10:]
    if not digits:
        digits = "0000000000"
    return hashlib.sha256(digits.encode("utf-8")).hexdigest()




def _canonical_sha256(value: dict) -> str:
    """Hash a deterministic JSON representation without persisting patient plaintext."""
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _pointer_snapshot_sha256(pointers: list[GlobalPatientPointer]) -> str:
    """Bind a receipt to the exact indexed candidate set and pointer versions."""
    snapshot = [
        {
            "id": pointer.id,
            "branch_code": pointer.branch_code,
            "source_mrn": pointer.source_mrn,
            "last_clinical_update_at": (
                pointer.last_clinical_update_at.isoformat()
                if pointer.last_clinical_update_at
                else None
            ),
        }
        for pointer in sorted(
            pointers,
            key=lambda item: (item.branch_code, item.source_mrn, item.id),
        )
    ]
    return _canonical_sha256({"pointers": snapshot})


def _summary_sha256(payload: FederatedPatientSummaryResponse) -> str:
    return _canonical_sha256(
        payload.model_dump(mode="json", exclude={"discovery_receipt"})
    )


def _selector_sha256(selector_type: str, selector_value: str) -> str:
    if selector_type == "ABHA":
        material = f"abha:{selector_value}"
    else:
        material = f"phone:{normalize_phone_hash(selector_value)}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _get_branch_policy(branch_db: Session) -> HospitalPolicySetting:
    policy = branch_db.execute(select(HospitalPolicySetting)).scalars().first()
    if not policy:
        policy = HospitalPolicySetting()
        branch_db.add(policy)
        branch_db.flush()
    return policy


def sync_patient_pointer(
    control_db: Session,
    branch_code: str,
    subdomain_slug: str,
    patient: Patient,
    has_critical_allergies: bool = False,
    tenant_db: Optional[Session] = None,
    actor_user_id: int | None = None,
) -> bool:
    """
    Updates the Central Discovery Index whenever a hospital registers or updates a patient,
    while respecting both Patient-level Privacy Opt-Out and Hospital-level Federation Sovereignty.
    """
    if tenant_db is not None:
        decision = evaluate_tenant_data_use(
            tenant_db,
            data_use_point="federation.patient.publish_pointer",
            patient_id=patient.id,
            actor_user_id=actor_user_id,
            patient_age=calculate_patient_age(patient.date_of_birth),
        )
        if not decision.allowed:
            return False

    try:
        phone_digits = "".join(ch for ch in (patient.phone_number or "") if ch.isdigit())[-10:]
        # Missing/legacy placeholder numbers are not searchable phone identities.
        # Keep ABHA-indexed patients discoverable with a deterministic, non-phone key.
        if not phone_digits or phone_digits == "0000000000":
            p_hash = hashlib.sha256(
                f"no-phone:{branch_code}:{patient.mrn}".encode("utf-8")
            ).hexdigest()
        else:
            p_hash = normalize_phone_hash(patient.phone_number)
        stmt = select(GlobalPatientPointer).where(
            GlobalPatientPointer.source_mrn == patient.mrn,
            GlobalPatientPointer.branch_code == branch_code,
        )
        pointer = control_db.execute(stmt).scalar_one_or_none()

        # 1. Patient-Level Opt-Out: Purge existing pointer and do not index
        if getattr(patient, "allow_network_sharing", True) is False:
            if pointer:
                control_db.delete(pointer)
                control_db.commit()
            return True

        # 2. Hospital-Level Opt-Out (ISOLATED_SILO): Purge existing pointer and do not index
        if tenant_db is not None:
            policy = _get_branch_policy(tenant_db)
            if policy.federation_sharing_mode == FederationPolicyEnum.ISOLATED_SILO:
                if pointer:
                    control_db.delete(pointer)
                    control_db.commit()
                return True
            if (
                policy.federation_sharing_mode == FederationPolicyEnum.EMERGENCY_ALLERGIES_ONLY
                and not has_critical_allergies
                and not (pointer and pointer.has_critical_allergies)
            ):
                return True

        if pointer:
            # Refresh every searchable identifier, including clearing identifiers
            # that the patient has removed or changed at the source.
            pointer.phone_hash = p_hash
            pointer.abha_number = patient.abha_number
            pointer.source_mrn = patient.mrn
            pointer.has_critical_allergies = has_critical_allergies or pointer.has_critical_allergies
            pointer.last_clinical_update_at = datetime.now(timezone.utc)
        else:
            pointer = GlobalPatientPointer(
                phone_hash=p_hash,
                abha_number=patient.abha_number,
                branch_code=branch_code,
                subdomain_slug=subdomain_slug,
                source_mrn=patient.mrn,
                has_critical_allergies=has_critical_allergies,
            )
            control_db.add(pointer)
        control_db.commit()
        return True
    except Exception:
        control_db.rollback()
        raise


# -----------------------------------------------------------------------------
# 1. Branch / Partner API Key Management (iam:write, iam:read, iam:delete)
# -----------------------------------------------------------------------------
@router.post("/clients", response_model=FederatedClientCreatedResponse, status_code=status.HTTP_201_CREATED)
def register_federated_branch(
    payload: FederatedClientCreate,
    request: Request,
    db: Session = Depends(get_db),
    control_db: Session = Depends(get_control_db),
    _: User = Depends(RequirePermission("iam:write")),
):
    tenant = resolve_tenant_context(request)
    branch_code = payload.branch_code.strip().upper()
    existing = db.query(FederatedClient).filter(FederatedClient.branch_code == branch_code).first()
    if existing:
        raise HTTPException(status_code=409, detail="Branch code is already registered.")

    raw_key = f"fed_live_{secrets.token_urlsafe(32)}"
    key_prefix = raw_key[:14]
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    client = FederatedClient(
        branch_code=branch_code,
        name=payload.name,
        api_key_prefix=key_prefix,
        api_key_hash=key_hash,
        is_active=True,
    )
    db.add(client)
    db.commit()
    db.refresh(client)

    node_exists = control_db.query(FederatedNode).filter(FederatedNode.branch_code == branch_code).first()
    if not node_exists:
        control_db.add(
            FederatedNode(
                branch_code=branch_code,
                hospital_name=payload.name,
                subdomain_slug=tenant.subdomain_slug,
                api_key_prefix=key_prefix,
                api_key_hash=key_hash,
                is_active=True,
            )
        )
        control_db.commit()

    return FederatedClientCreatedResponse(
        id=client.id,
        branch_code=client.branch_code,
        name=client.name,
        api_key_prefix=client.api_key_prefix,
        raw_api_key=raw_key,
        is_active=client.is_active,
    )


@router.get("/clients", response_model=PaginatedResponse[FederatedClientResponse])
def list_federated_branches(
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("iam:read")),
):
    page, page_size = validate_pagination(page, page_size)
    query = db.query(FederatedClient).order_by(FederatedClient.id.asc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.delete("/clients/{client_id}", status_code=200)
def revoke_federated_branch_key(
    client_id: int,
    db: Session = Depends(get_db),
    control_db: Session = Depends(get_control_db),
    _: User = Depends(RequirePermission("iam:delete")),
):
    client = db.get(FederatedClient, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Federated client not found.")
    client.is_active = False
    db.commit()

    node = control_db.query(FederatedNode).filter(FederatedNode.branch_code == client.branch_code).first()
    if node:
        node.is_active = False
        control_db.commit()

    return {"status": "success", "message": f"API key for branch '{client.branch_code}' revoked."}


# -----------------------------------------------------------------------------
# 2. Central Discovery Index & Multi-Hop Patient Aggregation (A -> B -> C)
# -----------------------------------------------------------------------------
@router.post(
    "/patients/{patient_id}/publish-pointer",
    status_code=200,
    openapi_extra={"x-privacy-data-use-point": "federation.patient.publish_pointer"},
)
def publish_local_patient_to_discovery_index(
    patient_id: int,
    request: Request,
    db: Session = Depends(get_db),
    control_db: Session = Depends(get_control_db),
    actor: User = Depends(RequirePermission("patients:write")),
):
    tenant = resolve_tenant_context(request)
    patient = db.get(Patient, patient_id)
    if not patient or not patient.is_active:
        raise HTTPException(status_code=404, detail="Active patient not found.")
    crit_allergy = (
        db.query(PatientAllergy)
        .filter(
            PatientAllergy.patient_id == patient.id,
            PatientAllergy.is_active.is_(True),
            PatientAllergy.severity.in_([AllergySeverityEnum.SEVERE, AllergySeverityEnum.ANAPHYLACTIC]),
        )
        .first()
        is not None
    )
    synced = sync_patient_pointer(
        control_db=control_db,
        branch_code=tenant.branch_code,
        subdomain_slug=tenant.subdomain_slug,
        patient=patient,
        has_critical_allergies=crit_allergy,
        tenant_db=db,
        actor_user_id=actor.id,
    )
    if synced is False:
        raise HTTPException(
            status_code=403, detail="Privacy policy does not permit sharing."
        )
    return {
        "status": "evaluated",
        "message": (
            f"Patient pointer evaluated for branch {tenant.branch_code}; "
            "source sharing policy may suppress publication."
        ),
    }


@router.get(
    "/patients/discover",
    response_model=FederatedPatientSummaryResponse,
    openapi_extra={"x-privacy-data-use-point": "federation.patient.discover"},
)
def discover_and_aggregate_patient_across_branches(
    phone_number: Optional[str] = Query(default=None, description="Patient registered phone number"),
    abha_number: Optional[str] = Query(default=None, description="National ABHA ID"),
    purpose: str = Query(default="CONTINUITY_OF_CARE", min_length=3, max_length=255),
    calling_node: FederatedNode = Depends(get_federated_node),
    control_db: Session = Depends(get_control_db),
    _: None = Depends(RateLimiter(scope="fed_discover", max_requests=60, window_seconds=60)),
):
    if not phone_number and not abha_number:
        raise HTTPException(status_code=400, detail="Provide either phone_number or abha_number.")

    # Remote emergency disclosure is disabled until the source can validate a
    # node-bound, purpose/scope-bound capability and a verifiable human actor
    # assertion. A local BreakGlassGrant ID alone is not a federation credential.
    if purpose.strip().upper() in {
        "EMERGENCY", "EMERGENCY_CARE", "EMERGENCY_TREATMENT", "EMERGENCY_ADMISSION"
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Remote emergency federation is disabled pending verified requester authorization.",
        )

    stmt = select(GlobalPatientPointer)
    if abha_number:
        stmt = stmt.where(GlobalPatientPointer.abha_number == abha_number)
        identifier_used = f"abha:{abha_number}"
    else:
        p_hash = normalize_phone_hash(phone_number)
        stmt = stmt.where(GlobalPatientPointer.phone_hash == p_hash)
        # F-09: Mask phone number in requested_identifier to prevent logging raw PII
        masked_phone = f"{phone_number[:3]}****{phone_number[-4:]}" if len(phone_number) >= 7 else "****"
        identifier_used = f"phone:{masked_phone}"

    pointers = control_db.execute(
        stmt.order_by(GlobalPatientPointer.last_clinical_update_at.desc())
    ).scalars().all()

    if not pointers:
        raise HTTPException(status_code=404, detail="No records found for this patient in the Central Discovery Index.")

    # Phone numbers are not unique patient identifiers. Permit a multi-branch
    # phone lookup only when every indexed record carries the same non-empty
    # ABHA identity and no branch has multiple MRNs for that identity.
    if not abha_number and len(pointers) > 1:
        pointer_abhas = {pointer.abha_number for pointer in pointers}
        branch_mrns = [(pointer.branch_code, pointer.source_mrn) for pointer in pointers]
        if (
            None in pointer_abhas
            or "" in pointer_abhas
            or len(pointer_abhas) != 1
            or len(branch_mrns) != len(set(branch_mrns))
            or len({branch for branch, _ in branch_mrns}) != len(branch_mrns)
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Phone number matches multiple patient records; use the patient's ABHA number to disambiguate.",
            )

    latest_demographics: Optional[Patient] = None
    selected_source_pointer: Optional[GlobalPatientPointer] = None
    allergies_only_source_found: bool = False
    merged_allergies: dict[str, FederatedAllergySummary] = {}

    import concurrent.futures

    # F-03: Pre-resolve tenant databases in the main thread to prevent worker threads
    # from sharing or concurrently querying control_db.
    branch_codes = {ptr.branch_code for ptr in pointers}
    tenant_regs = control_db.execute(
        select(TenantRegistry).where(
            TenantRegistry.branch_code.in_(branch_codes),
            TenantRegistry.is_active.is_(True),
        )
    ).scalars().all()
    branch_to_db = {reg.branch_code: reg.db_name for reg in tenant_regs}
    branch_to_group = {reg.branch_code: reg.corporate_group_id for reg in tenant_regs}
    calling_registry = control_db.execute(
        select(TenantRegistry).where(
            TenantRegistry.branch_code == calling_node.branch_code,
            TenantRegistry.is_active.is_(True),
        )
    ).scalar_one_or_none()
    calling_group_id = calling_registry.corporate_group_id if calling_registry else None

    def _fetch_branch_data(ptr, branch_db_name: Optional[str]):
        if not branch_db_name:
            return None

        branch_engine = tenant_engine_pool.get_engine(branch_db_name)
        BranchSession = sessionmaker(bind=branch_engine, autocommit=False, autoflush=False)
        with BranchSession() as branch_db:
            policy = _get_branch_policy(branch_db)

            if policy.federation_sharing_mode == FederationPolicyEnum.ISOLATED_SILO:
                return None
            if policy.federation_sharing_mode == FederationPolicyEnum.CORPORATE_GROUP_ONLY:
                # Group membership is an explicit control-plane authorization attribute.
                # Missing assignments fail closed; branch-code naming is never trusted.
                target_group_id = branch_to_group.get(ptr.branch_code)
                if (
                    not calling_group_id
                    or not target_group_id
                    or target_group_id != calling_group_id
                ):
                    return None
            # Emergency-purpose requests are rejected at the endpoint boundary
            # until a verifiable node/actor capability protocol is implemented.
            if policy.federation_sharing_mode == FederationPolicyEnum.EMERGENCY_ALLERGIES_ONLY:
                return None

            patient = branch_db.query(Patient).filter(Patient.mrn == ptr.source_mrn, Patient.is_active.is_(True)).first()
            if not patient or getattr(patient, "allow_network_sharing", True) is False:
                return None
            # A legacy discovery pointer may have been indexed from the old
            # 0000000000 missing-phone placeholder. Never treat that sentinel as
            # a real phone identity, even before the pointer is refreshed.
            if abha_number is not None and patient.abha_number != abha_number:
                # A stale ABHA pointer must never disclose the patient's current
                # record after the source branch changes or removes that ABHA.
                return None

            if phone_number is not None:
                requested_digits = "".join(ch for ch in phone_number if ch.isdigit())[-10:]
                patient_digits = "".join(ch for ch in (patient.phone_number or "") if ch.isdigit())[-10:]
                if (
                    not requested_digits
                    or requested_digits == "0000000000"
                    or not patient_digits
                    or patient_digits == "0000000000"
                    or requested_digits != patient_digits
                ):
                    return None

            decision = evaluate_tenant_data_use(
                branch_db,
                data_use_point="federation.patient.discover",
                patient_id=patient.id,
                actor_user_id=None,
                patient_age=calculate_patient_age(patient.date_of_birth),
            )
            if not decision.allowed:
                return None

            branch_db.refresh(patient)
            branch_db.expunge(patient)

            local_allergies = []
            if policy.federation_share_allergies:
                alg_stmt = (
                    select(PatientAllergy, AllergyMaster)
                    .join(AllergyMaster, PatientAllergy.allergy_id == AllergyMaster.id)
                    .where(PatientAllergy.patient_id == patient.id, PatientAllergy.is_active.is_(True))
                )
                for pa, master in branch_db.execute(alg_stmt).all():
                    rx_note = pa.reaction_description or "Adverse reaction"

                    # FED-001:
                    # Tag the allergy with the branch where this allergy record currently
                    # originates. Do not add another tag if the reaction has already been
                    # provenance-tagged during an earlier federation hop.
                    if "[Source:" in rx_note:
                        tagged_reaction = rx_note
                    else:
                        tagged_reaction = f"{rx_note} [Source: {ptr.branch_code}]"

                    # Extract primitive data into schemas immediately to prevent DetachedInstanceError in main thread
                    local_allergies.append({
                        "key": master.name.strip().lower(),
                        "summary": FederatedAllergySummary(
                            allergy_code=master.code,
                            allergy_name=master.name,
                            severity=pa.severity,
                            reaction=tagged_reaction,
                        )
                    })

            branch_db.add(
                FederationTransferLog(
                    # Snapshot the exact credential identity authenticated by
                    # get_federated_node. No cross-database FK is used because this
                    # audit row is written into the source tenant database.
                    requesting_node_id=calling_node.id,
                    requesting_key_prefix=calling_node.api_key_prefix,
                    requesting_branch_code=calling_node.branch_code,
                    patient_id=patient.id,
                    requested_identifier=f"{calling_node.branch_code}->{identifier_used}",
                    purpose=purpose,
                )
            )
            branch_db.commit()

            return {
                "ptr": ptr,
                "patient": patient,
                "allergies": local_allergies,
                "allergies_only": policy.federation_sharing_mode == FederationPolicyEnum.EMERGENCY_ALLERGIES_ONLY,
                "share_demographics": policy.federation_share_demographics
            }

    # F-03: Isolated worker sessions with explicit source completeness. A timeout
    # or worker exception must never be silently represented as a complete response.
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(pointers)))
    ptr_to_future = {}
    failed_source_branches: list[str] = []
    successful_source_branches: set[str] = set()
    try:
        for ptr in pointers:
            branch_db_name = branch_to_db.get(ptr.branch_code)
            if not branch_db_name:
                failed_source_branches.append(ptr.branch_code)
                continue
            ptr_to_future[ptr] = executor.submit(
                _fetch_branch_data, ptr, branch_db_name
            )
        _, not_done = concurrent.futures.wait(
            ptr_to_future.values(),
            timeout=5.0,
            return_when=concurrent.futures.ALL_COMPLETED,
        )
        timed_out = set(not_done)
        for future in timed_out:
            future.cancel()
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    for ptr in pointers:
        future = ptr_to_future.get(ptr)
        if future is None:
            continue
        if future in timed_out or not future.done() or future.cancelled():
            failed_source_branches.append(ptr.branch_code)
            continue
        try:
            result = future.result()
            successful_source_branches.add(ptr.branch_code)
            if result:
                # EMERGENCY_ALLERGIES_ONLY may contribute allergy summaries,
                # never patient demographics.
                if result["allergies_only"]:
                    allergies_only_source_found = True
                elif latest_demographics is None and result["share_demographics"]:
                    latest_demographics = result["patient"]
                    selected_source_pointer = ptr

                # Process the already-extracted safe schemas
                for alg_data in result["allergies"]:
                    if alg_data["key"] not in merged_allergies:
                        merged_allergies[alg_data["key"]] = alg_data["summary"]
        except Exception:
            # Do not expose exception details or PHI; report only the affected
            # branch identity to the authenticated federation caller.
            failed_source_branches.append(ptr.branch_code)

    # Keep branch identifiers deterministic and avoid duplicate failure entries.
    failed_source_branches = sorted(set(failed_source_branches))
    source_failure_count = len(failed_source_branches)
    source_success_count = len(successful_source_branches)
    source_count = len(branch_codes)
    if latest_demographics is None and not allergies_only_source_found:
        if source_failure_count:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": "Federated discovery could not verify every indexed source.",
                    "source_count": source_count,
                    "source_success_count": source_success_count,
                    "source_failure_count": source_failure_count,
                    "is_partial": True,
                    "failed_source_branches": failed_source_branches,
                },
            )
        raise HTTPException(
            status_code=404,
            detail="No shareable patient records found across permitted hospital branches.",
        )

    # If no source authorized demographic sharing but an allergies-only source
    # did authorize this emergency disclosure, return a fully redacted envelope.
    demographics = latest_demographics
    response_payload = FederatedPatientSummaryResponse(
        source_mrn=demographics.mrn if demographics else None,
        abha_number=demographics.abha_number if demographics else None,
        full_name=demographics.full_name if demographics else None,
        date_of_birth=demographics.date_of_birth if demographics else None,
        gender=demographics.gender if demographics else None,
        blood_group=demographics.blood_group if demographics else None,
        phone_number=demographics.phone_number if demographics else None,
        email=demographics.email if demographics else None,
        address=demographics.address if demographics else None,
        emergency_contact_name=demographics.emergency_contact_name if demographics else None,
        emergency_contact_phone=demographics.emergency_contact_phone if demographics else None,
        active_allergies=list(merged_allergies.values()),
        source_count=source_count,
        source_success_count=source_success_count,
        source_failure_count=source_failure_count,
        is_partial=source_failure_count > 0,
        failed_source_branches=failed_source_branches,
    )

    # Only a fully verified demographic result can mint an import receipt. The
    # client receives a random bearer value; only its hash is stored centrally.
    if (
        demographics is not None
        and selected_source_pointer is not None
        and source_failure_count == 0
        and source_success_count == source_count
    ):
        selector_type = "ABHA" if abha_number else "PHONE"
        selector_value = abha_number if abha_number else (phone_number or "")
        raw_receipt = secrets.token_urlsafe(32)
        receipt = FederatedDiscoveryReceipt(
            token_hash=hashlib.sha256(raw_receipt.encode("utf-8")).hexdigest(),
            calling_node_id=calling_node.id,
            destination_branch_code=calling_node.branch_code,
            selector_type=selector_type,
            selector_hash=_selector_sha256(selector_type, selector_value),
            pointer_snapshot_hash=_pointer_snapshot_sha256(pointers),
            source_pointer_id=selected_source_pointer.id,
            source_branch_code=selected_source_pointer.branch_code,
            source_mrn=selected_source_pointer.source_mrn,
            summary_hash=_summary_sha256(response_payload),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=2),
        )
        control_db.add(receipt)
        try:
            control_db.commit()
        except Exception:
            control_db.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="A verifiable federated discovery receipt could not be issued.",
            )
        response_payload.discovery_receipt = raw_receipt

    return response_payload


@router.post("/patients/import", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
def import_federated_patient_locally(
    payload: FederatedPatientSummaryResponse,
    request: Request,
    db: Session = Depends(get_db),
    control_db: Session = Depends(get_control_db),
    current_user: User = Depends(RequirePermission("patients:write")),
):
    """Import an authenticated discovery result without trusting client-supplied clinical fields."""
    tenant = resolve_tenant_context(request)

    # Completeness metadata in the request body is caller-controlled. Import is
    # permitted only with a short-lived receipt minted by this server after a
    # complete discovery, bound to this node, destination branch and exact result.
    if not payload.discovery_receipt:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A valid server-issued federated discovery receipt is required for import.",
        )
    token_hash = hashlib.sha256(payload.discovery_receipt.encode("utf-8")).hexdigest()
    receipt = control_db.get(FederatedDiscoveryReceipt, token_hash)
    if not receipt:
        raise HTTPException(status_code=409, detail="Federated discovery receipt is invalid or expired.")
    now = datetime.now(timezone.utc)
    expires_at = receipt.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise HTTPException(status_code=409, detail="Federated discovery receipt is invalid or expired.")
    if receipt.destination_branch_code != tenant.branch_code:
        raise HTTPException(status_code=403, detail="Federated discovery receipt belongs to another destination branch.")
    if receipt.source_mrn != payload.source_mrn:
        raise HTTPException(status_code=409, detail="Federated discovery receipt does not match the source patient.")
    if receipt.summary_hash != _summary_sha256(payload):
        raise HTTPException(status_code=409, detail="Federated discovery result was modified; rediscover before import.")

    calling_node = control_db.get(FederatedNode, receipt.calling_node_id)
    if not calling_node or not calling_node.is_active:
        raise HTTPException(status_code=401, detail="Federation node associated with this receipt is no longer active.")

    if receipt.selector_type == "ABHA":
        if not payload.abha_number:
            raise HTTPException(status_code=409, detail="Federated discovery selector does not match the receipt.")
        selector_hash = _selector_sha256("ABHA", payload.abha_number)
        current_pointers = control_db.execute(
            select(GlobalPatientPointer)
            .where(GlobalPatientPointer.abha_number == payload.abha_number)
            .order_by(GlobalPatientPointer.last_clinical_update_at.desc())
            .with_for_update()
        ).scalars().all()
    elif receipt.selector_type == "PHONE":
        if not payload.phone_number:
            raise HTTPException(status_code=409, detail="Federated discovery selector does not match the receipt.")
        selector_hash = _selector_sha256("PHONE", payload.phone_number)
        current_pointers = control_db.execute(
            select(GlobalPatientPointer)
            .where(GlobalPatientPointer.phone_hash == normalize_phone_hash(payload.phone_number))
            .order_by(GlobalPatientPointer.last_clinical_update_at.desc())
        ).scalars().all()
    else:
        raise HTTPException(status_code=409, detail="Federated discovery receipt has an unsupported selector.")

    if selector_hash != receipt.selector_hash:
        raise HTTPException(status_code=409, detail="Federated discovery selector does not match the receipt.")
    if _pointer_snapshot_sha256(current_pointers) != receipt.pointer_snapshot_hash:
        raise HTTPException(status_code=409, detail="Federated source index changed since discovery; rediscover before import.")
    if not any(
        pointer.id == receipt.source_pointer_id
        and pointer.branch_code == receipt.source_branch_code
        and pointer.source_mrn == receipt.source_mrn
        for pointer in current_pointers
    ):
        raise HTTPException(status_code=409, detail="Federated source pointer no longer matches the discovery receipt.")

    # A complete server-issued receipt is the authority; these legacy metadata
    # fields remain consistency checks only and cannot create an import capability.
    if payload.is_partial or payload.source_failure_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Partial federated discovery cannot be imported; retry discovery when all sources are available.",
        )

    # Allergy-only emergency responses deliberately contain no demographic identity
    # and must never be accepted as patient-import payloads.
    if (
        not payload.source_mrn
        or not payload.full_name
        or payload.date_of_birth is None
        or payload.gender is None
    ):
        raise HTTPException(
            status_code=422,
            detail="A demographics-authorized discovery result is required for patient import.",
        )

    # The import is valid only when the supplied source MRN is currently indexed to
    # exactly one other active branch. This prevents this authenticated endpoint from
    # becoming a generic patient-creation endpoint with fabricated federation provenance.
    source_pointers = control_db.execute(
        select(GlobalPatientPointer).where(
            GlobalPatientPointer.source_mrn == payload.source_mrn,
            GlobalPatientPointer.branch_code != tenant.branch_code,
        )
    ).scalars().all()
    if not source_pointers:
        raise HTTPException(status_code=404, detail="Federated source patient is not currently indexed.")
    if len(source_pointers) > 1:
        raise HTTPException(
            status_code=409,
            detail="Federated source MRN maps to multiple branches; rediscover the patient before import.",
        )

    source_pointer = source_pointers[0]
    if (
        source_pointer.id != receipt.source_pointer_id
        or source_pointer.branch_code != receipt.source_branch_code
        or source_pointer.source_mrn != receipt.source_mrn
    ):
        raise HTTPException(status_code=409, detail="Federated source pointer changed; rediscover before import.")
    source_registry = control_db.execute(
        select(TenantRegistry).where(
            TenantRegistry.branch_code == source_pointer.branch_code,
            TenantRegistry.is_active.is_(True),
        )
    ).scalar_one_or_none()
    if not source_registry:
        raise HTTPException(status_code=404, detail="Federated source branch is unavailable.")

    source_engine = tenant_engine_pool.get_engine(source_registry.db_name)
    SourceSession = sessionmaker(bind=source_engine, autocommit=False, autoflush=False)
    with SourceSession() as source_db:
        source_policy = _get_branch_policy(source_db)
        if source_policy.federation_sharing_mode in {
            FederationPolicyEnum.ISOLATED_SILO,
            FederationPolicyEnum.EMERGENCY_ALLERGIES_ONLY,
        }:
            raise HTTPException(status_code=403, detail="Source branch policy does not permit demographic import.")
        if source_policy.federation_sharing_mode == FederationPolicyEnum.CORPORATE_GROUP_ONLY:
            destination_registry = control_db.execute(
                select(TenantRegistry).where(
                    TenantRegistry.branch_code == tenant.branch_code,
                    TenantRegistry.is_active.is_(True),
                )
            ).scalar_one_or_none()
            source_group_id = source_registry.corporate_group_id
            destination_group_id = (
                destination_registry.corporate_group_id if destination_registry else None
            )
            if (
                not source_group_id
                or not destination_group_id
                or source_group_id != destination_group_id
            ):
                raise HTTPException(
                    status_code=403,
                    detail="Source branch policy does not permit cross-group demographic import.",
                )

        source_patient = source_db.query(Patient).filter(
            Patient.mrn == source_pointer.source_mrn,
            Patient.is_active.is_(True),
        ).first()
        if not source_patient or getattr(source_patient, "allow_network_sharing", True) is False:
            raise HTTPException(status_code=404, detail="Federated source patient is no longer shareable.")

        decision = evaluate_tenant_data_use(
            source_db,
            data_use_point="federation.patient.discover",
            patient_id=source_patient.id,
            # Destination user IDs do not belong to the source tenant's users table.
            # The source-side FederationTransferLog records the requesting branch.
            actor_user_id=None,
            patient_age=calculate_patient_age(source_patient.date_of_birth),
        )
        if not decision.allowed or not source_policy.federation_share_demographics:
            raise HTTPException(status_code=403, detail="Source privacy policy does not permit demographic import.")

        # Do not accept edited demographics/allergies from the request body. The submitted
        # summary must match the currently indexed source patient, otherwise the caller must
        # rediscover and retry. This closes the client-side data injection gap.
        if any([
            payload.full_name != source_patient.full_name,
            payload.date_of_birth != source_patient.date_of_birth,
            payload.gender != source_patient.gender,
            payload.blood_group != source_patient.blood_group,
            payload.phone_number != source_patient.phone_number,
            payload.email != source_patient.email,
            payload.address != source_patient.address,
            payload.emergency_contact_name != source_patient.emergency_contact_name,
            payload.emergency_contact_phone != source_patient.emergency_contact_phone,
            payload.abha_number != source_patient.abha_number,
        ]):
            raise HTTPException(
                status_code=409,
                detail="Federated patient data changed since discovery; rediscover before importing.",
            )

        # Import must apply the same source-controlled allergy-sharing setting
        # as discovery. Re-reading the source database is required for integrity,
        # but must not turn a disabled data category into an implicit disclosure.
        source_allergies = (
            source_db.execute(
                select(PatientAllergy, AllergyMaster)
                .join(AllergyMaster, PatientAllergy.allergy_id == AllergyMaster.id)
                .where(
                    PatientAllergy.patient_id == source_patient.id,
                    PatientAllergy.is_active.is_(True),
                )
            ).all()
            if source_policy.federation_share_allergies
            else []
        )

        # Record every validated import request, including idempotent retries where
        # the destination already has the patient. Source and destination databases
        # cannot share one atomic transaction. If this source audit write fails, abort
        # before returning an existing patient or committing a new local clone.
        # REQUESTED is intentional: the subsequent destination commit may still fail.
        source_db.add(
            FederationTransferLog(
                client_id=None,
                requesting_branch_code=tenant.branch_code,
                patient_id=source_patient.id,
                requested_identifier=f"import:{tenant.branch_code}:{hashlib.sha256(source_patient.mrn.encode('utf-8')).hexdigest()[:16]}",
                purpose="CONTINUITY_OF_CARE_IMPORT_REQUESTED",
            )
        )
        try:
            source_db.commit()
        except Exception:
            db.rollback()
            raise

        # Idempotency: ABHA is the strongest local identity; otherwise use the combination
        # of normalized phone, DOB and exact name to avoid repeated imports.
        existing = None
        if source_patient.abha_number:
            existing = db.query(Patient).filter(Patient.abha_number == source_patient.abha_number).first()
        if not existing and source_patient.phone_number:
            existing = db.query(Patient).filter(
                Patient.phone_number == source_patient.phone_number,
                Patient.date_of_birth == source_patient.date_of_birth,
                Patient.full_name == source_patient.full_name,
            ).first()
        if existing:
            return existing

        local_mrn = f"MRN-{secrets.token_hex(6).upper()}"
        new_patient = Patient(
            mrn=local_mrn,
            abha_number=source_patient.abha_number,
            full_name=source_patient.full_name,
            date_of_birth=source_patient.date_of_birth,
            gender=source_patient.gender,
            blood_group=source_patient.blood_group,
            phone_number=source_patient.phone_number,
            email=source_patient.email,
            address=source_patient.address,
            emergency_contact_name=source_patient.emergency_contact_name,
            emergency_contact_phone=source_patient.emergency_contact_phone,
            is_active=True,
            allow_network_sharing=True,
            created_by_id=current_user.id,
            updated_by_id=current_user.id,
        )
        db.add(new_patient)
        db.flush()

        has_crit = False
        for remote_alg, remote_master in source_allergies:
            local_master = (
                db.query(AllergyMaster)
                .filter(
                    (AllergyMaster.code == remote_master.code)
                    | (AllergyMaster.name.ilike(remote_master.name))
                )
                .first()
            )
            if not local_master:
                continue
            if remote_alg.severity in [AllergySeverityEnum.SEVERE, AllergySeverityEnum.ANAPHYLACTIC]:
                has_crit = True
            reaction = remote_alg.reaction_description or "Adverse reaction"
            if "[Source:" not in reaction:
                reaction = f"{reaction} [Source: {source_pointer.branch_code}]"
            db.add(
                PatientAllergy(
                    patient_id=new_patient.id,
                    allergy_id=local_master.id,
                    severity=remote_alg.severity,
                    reaction_description=reaction,
                    recorded_by_user_id=current_user.id,
                    is_active=True,
                    created_by_id=current_user.id,
                    updated_by_id=current_user.id,
                )
            )

        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
        db.refresh(new_patient)

    sync_patient_pointer(
        control_db=control_db,
        branch_code=tenant.branch_code,
        subdomain_slug=tenant.subdomain_slug,
        patient=new_patient,
        has_critical_allergies=has_crit,
        tenant_db=db,
        actor_user_id=current_user.id,
    )
    return new_patient