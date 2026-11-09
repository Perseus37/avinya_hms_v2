"""Statutory Hospital Operational Registers & Legal Compliance APIs.

Implements statutory hospital ledgers mandated by NABH, Indian Clinical Establishments Act,
NDPS Rules, Bio-Medical Waste Rules 2016, and IRDAI/TPA billing standards:
1. Daily Midnight ADT Bed Census Register
2. Cashier Daily Shift Handover & Reconciliation Ledger
3. NDPS (Narcotic Drugs & Psychotropic Substances) Double-Custody Statutory Register
4. Accounts Receivable (AR) Aging Ledger by TPA/Insurer
5. Bio-Medical Waste (BMW) Management Statutory Register
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from backend.core.database import get_db, resolve_tenant_context
from backend.core.date_ranges import resolve_record_date_window
from backend.core.dependencies import RequirePermission
from backend.core.export import stream_csv_response
from backend.domains.billing.models import Invoice, InvoiceStatusEnum, PaymentMethodEnum, PaymentReceipt
from backend.domains.clinical.models import DeathRecord
from backend.domains.encounters.models import BedTransferLog, EncounterStatusEnum, InpatientAdmission, PatientEncounter
from backend.domains.facility.models import Bed, BedStatusEnum, PhysicalRoom, Ward
from backend.domains.identity.models import User
from backend.domains.insurance.models import InsuranceClaim, InsuranceProvider, PatientInsurancePolicy
from backend.domains.pharmacy.models import ControlledSubstanceMovementLog, ControlledSubstanceVault, MedicationMaster
from backend.domains.service_ops.models import BiomedicalWasteBag, BiomedicalWasteManifest, BMWColorCategoryEnum

router = APIRouter(
    prefix="/api/registers",
    tags=["Statutory Hospital Operational Registers & Legal Compliance"],
)


# =====================================================================
# 1. DAILY MIDNIGHT ADT BED CENSUS REGISTER
# =====================================================================
@router.get("/midnight-census")
def get_daily_midnight_bed_census(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    ward_id: Optional[int] = None,
    export_format: Optional[str] = Query(default=None, alias="format"),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("adt:read", "executive_bi:read")),
):
    """Generates the statutory Midnight ADT Bed Census tracking opening beds, admissions, discharges, deaths, and BOR %."""
    today = datetime.now(timezone.utc).date()
    effective_start = start_date or (today - timedelta(days=7))
    effective_end = end_date or today
    if effective_start > effective_end:
        raise HTTPException(status_code=400, detail="start_date must be on or before end_date.")

    # Total beds query
    bed_stmt = select(func.count(Bed.id))
    if ward_id:
        bed_stmt = bed_stmt.join(PhysicalRoom, Bed.room_id == PhysicalRoom.id).where(PhysicalRoom.ward_id == ward_id)
    total_licensed_beds = db.execute(bed_stmt).scalar() or 0

    # Build day-by-day census
    days_count = (effective_end - effective_start).days + 1
    census_rows = []

    for day_offset in range(days_count):
        cur_date = effective_start + timedelta(days=day_offset)
        day_start = datetime.combine(cur_date, time.min, tzinfo=timezone.utc)
        day_end = datetime.combine(cur_date, time.max, tzinfo=timezone.utc)

        # Admissions on this date
        adm_stmt = select(func.count(InpatientAdmission.id)).where(
            InpatientAdmission.created_at >= day_start,
            InpatientAdmission.created_at <= day_end,
        )
        new_admissions = db.execute(adm_stmt).scalar() or 0

        # Discharges on this date
        disch_stmt = select(func.count(InpatientAdmission.id)).where(
            InpatientAdmission.discharge_time >= day_start,
            InpatientAdmission.discharge_time <= day_end,
        )
        total_discharges = db.execute(disch_stmt).scalar() or 0

        # Deaths on this date
        death_stmt = select(func.count(DeathRecord.id)).where(
            DeathRecord.time_of_death >= day_start,
            DeathRecord.time_of_death <= day_end,
        )
        total_deaths = db.execute(death_stmt).scalar() or 0

        # Occupied beds at midnight (active admission with created_at <= day_end and (discharge_time is null or discharge_time > day_end))
        midnight_occ_stmt = select(func.count(InpatientAdmission.id)).where(
            InpatientAdmission.created_at <= day_end,
            or_(
                InpatientAdmission.discharge_time.is_(None),
                InpatientAdmission.discharge_time > day_end,
            ),
        )
        occupied_at_midnight = db.execute(midnight_occ_stmt).scalar() or 0

        # Bed Occupancy Rate (BOR %)
        bor_percent = round((occupied_at_midnight / total_licensed_beds * 100), 2) if total_licensed_beds > 0 else 0.0

        census_rows.append({
            "census_date": cur_date.strftime("%Y-%m-%d"),
            "total_licensed_beds": total_licensed_beds,
            "opening_occupied": max(0, occupied_at_midnight - new_admissions + total_discharges),
            "new_admissions": new_admissions,
            "discharges": total_discharges,
            "deaths": total_deaths,
            "closing_occupied_at_midnight": occupied_at_midnight,
            "available_beds_at_midnight": max(0, total_licensed_beds - occupied_at_midnight),
            "bed_occupancy_rate_pct": bor_percent,
        })

    if export_format and export_format.lower() == "csv":
        fieldnames = [
            "census_date",
            "total_licensed_beds",
            "opening_occupied",
            "new_admissions",
            "discharges",
            "deaths",
            "closing_occupied_at_midnight",
            "available_beds_at_midnight",
            "bed_occupancy_rate_pct",
        ]
        filename = f"midnight_bed_census_{effective_start}_{effective_end}"
        return stream_csv_response(iter(census_rows), fieldnames, filename)

    return {
        "start_date": effective_start.strftime("%Y-%m-%d"),
        "end_date": effective_end.strftime("%Y-%m-%d"),
        "total_licensed_beds": total_licensed_beds,
        "items": census_rows,
    }


# =====================================================================
# 2. CASHIER DAILY SHIFT HANDOVER & RECONCILIATION LEDGER
# =====================================================================
@router.get("/cashier-shift-reconciliation")
def get_cashier_shift_reconciliation(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    cashier_user_id: Optional[int] = None,
    export_format: Optional[str] = Query(default=None, alias="format"),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("billing:read", "finance:read")),
):
    """Generates the statutory cashier shift closing report by counter, tender mode, and reconciliation status."""
    start_at, end_at = resolve_record_date_window(start_date, end_date)
    query = (
        db.query(PaymentReceipt)
        .options(
            joinedload(PaymentReceipt.invoice).joinedload(Invoice.patient),
        )
    )
    if start_at is not None and end_at is not None:
        query = query.filter(PaymentReceipt.created_at >= start_at, PaymentReceipt.created_at < end_at)
    if cashier_user_id:
        query = query.filter(PaymentReceipt.created_by_id == cashier_user_id)

    receipts = query.order_by(PaymentReceipt.created_at.desc()).all()
    user_ids = {r.created_by_id for r in receipts if r.created_by_id is not None}
    users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
    user_map = {u.id: u for u in users}

    # Aggregate summaries by user / payment method
    user_summary: Dict[str, Dict[str, Any]] = {}
    row_items = []

    for r in receipts:
        amount_inr = round(r.amount_paid_paise / 100, 2)
        method_str = r.payment_method.value if hasattr(r.payment_method, "value") else str(r.payment_method)
        user = user_map.get(r.created_by_id) if r.created_by_id else None
        user_name = user.full_name if user else "System/Automated"
        user_email = user.email if user else "system@hospital.internal"

        if user_email not in user_summary:
            user_summary[user_email] = {
                "cashier_name": user_name,
                "cashier_email": user_email,
                "total_receipts_count": 0,
                "total_collected_inr": 0.0,
                "cash_inr": 0.0,
                "upi_inr": 0.0,
                "card_inr": 0.0,
                "net_banking_inr": 0.0,
                "cheque_inr": 0.0,
                "insurance_inr": 0.0,
            }

        user_summary[user_email]["total_receipts_count"] += 1
        user_summary[user_email]["total_collected_inr"] = round(user_summary[user_email]["total_collected_inr"] + amount_inr, 2)

        if method_str == "CASH":
            user_summary[user_email]["cash_inr"] = round(user_summary[user_email]["cash_inr"] + amount_inr, 2)
        elif method_str == "UPI":
            user_summary[user_email]["upi_inr"] = round(user_summary[user_email]["upi_inr"] + amount_inr, 2)
        elif method_str in ("CARD", "CREDIT_CARD", "DEBIT_CARD"):
            user_summary[user_email]["card_inr"] = round(user_summary[user_email]["card_inr"] + amount_inr, 2)
        elif method_str in ("NET_BANKING", "BANK_TRANSFER"):
            user_summary[user_email]["net_banking_inr"] = round(user_summary[user_email]["net_banking_inr"] + amount_inr, 2)
        elif method_str == "CHEQUE":
            user_summary[user_email]["cheque_inr"] = round(user_summary[user_email]["cheque_inr"] + amount_inr, 2)
        elif method_str in ("INSURANCE", "TPA"):
            user_summary[user_email]["insurance_inr"] = round(user_summary[user_email]["insurance_inr"] + amount_inr, 2)

        patient = r.invoice.patient if r.invoice else None
        row_items.append({
            "receipt_number": r.receipt_number,
            "invoice_number": r.invoice.invoice_number if r.invoice else "",
            "patient_mrn": patient.mrn if patient else "",
            "patient_name": patient.full_name if patient else "",
            "cashier_name": user_name,
            "payment_method": method_str,
            "amount_inr": amount_inr,
            "transaction_reference": r.transaction_reference or "N/A",
            "recorded_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else "",
        })

    if export_format and export_format.lower() == "csv":
        fieldnames = [
            "receipt_number",
            "invoice_number",
            "patient_mrn",
            "patient_name",
            "cashier_name",
            "payment_method",
            "amount_inr",
            "transaction_reference",
            "recorded_at",
        ]
        filename = f"cashier_reconciliation_{start_date or 'all'}_{end_date or 'all'}"
        return stream_csv_response(iter(row_items), fieldnames, filename)

    return {
        "start_date": str(start_date or "all"),
        "end_date": str(end_date or "all"),
        "total_payments_count": len(receipts),
        "total_revenue_inr": sum(u["total_collected_inr"] for u in user_summary.values()),
        "cashiers": list(user_summary.values()),
        "transactions": row_items[:200],
    }


# =====================================================================
# 3. NDPS NARCOTICS & PSYCHOTROPIC SUBSTANCES STATUTORY REGISTER
# =====================================================================
@router.get("/ndps-ledger")
def get_ndps_statutory_ledger(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    medication_id: Optional[int] = None,
    export_format: Optional[str] = Query(default=None, alias="format"),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("pharmacy:read")),
):
    """Generates the statutory double-custody Narcotic Drugs & Psychotropic Substances (NDPS) ledger."""
    start_at, end_at = resolve_record_date_window(start_date, end_date)
    query = (
        db.query(ControlledSubstanceMovementLog)
        .options(
            joinedload(ControlledSubstanceMovementLog.vault).joinedload(ControlledSubstanceVault.medication),
            joinedload(ControlledSubstanceMovementLog.primary_user),
            joinedload(ControlledSubstanceMovementLog.witness_user),
        )
    )
    if start_at is not None and end_at is not None:
        query = query.filter(
            ControlledSubstanceMovementLog.created_at >= start_at,
            ControlledSubstanceMovementLog.created_at < end_at,
        )
    if medication_id:
        query = query.join(ControlledSubstanceMovementLog.vault).filter(ControlledSubstanceVault.medication_id == medication_id)

    movements = query.order_by(ControlledSubstanceMovementLog.id.desc()).all()

    def row_generator():
        for m in movements:
            med = m.vault.medication if m.vault and m.vault.medication else None
            primary = m.primary_user
            witness = m.witness_user
            yield {
                "id": m.id,
                "movement_time": m.created_at.strftime("%Y-%m-%d %H:%M:%S") if m.created_at else "",
                "medication_code": med.code if med else "",
                "medication_name": med.name if med else "",
                "batch_number": m.batch_number or "",
                "movement_type": str(m.movement_type),
                "quantity_changed": m.quantity_units,
                "balance_after": m.balance_after,
                "recorded_by": primary.full_name if primary else "",
                "witness_user": witness.full_name if witness else "N/A",
                "notes_or_reason": (m.notes or m.wastage_reason or "").replace("\n", " "),
            }

    if export_format and export_format.lower() == "csv":
        fieldnames = [
            "id",
            "movement_time",
            "medication_code",
            "medication_name",
            "batch_number",
            "movement_type",
            "quantity_changed",
            "balance_after",
            "recorded_by",
            "witness_user",
            "notes_or_reason",
        ]
        filename = f"ndps_statutory_ledger_{start_date or 'all'}_{end_date or 'all'}"
        return stream_csv_response(row_generator(), fieldnames, filename)

    return {
        "total_movements": len(movements),
        "items": list(row_generator())[:100],
    }


# =====================================================================
# 4. ACCOUNTS RECEIVABLE (AR) AGING LEDGER
# =====================================================================
@router.get("/ar-aging")
def get_ar_aging_ledger(
    as_of_date: Optional[date] = None,
    provider_id: Optional[int] = None,
    export_format: Optional[str] = Query(default=None, alias="format"),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("billing:read", "finance:read")),
):
    """Calculates statutory Accounts Receivable (AR) aging buckets (0-30, 31-60, 61-90, >90 days) by Insurer/TPA and Patient."""
    reference_date = as_of_date or datetime.now(timezone.utc).date()

    # Query invoices with outstanding balance
    query = (
        db.query(Invoice)
        .options(
            joinedload(Invoice.patient),
        )
        .filter(Invoice.status.in_([InvoiceStatusEnum.UNPAID, InvoiceStatusEnum.PARTIAL]))
    )
    invoices = query.all()

    # Look up insurance claims associated with invoices
    claims = (
        db.query(InsuranceClaim)
        .options(
            joinedload(InsuranceClaim.policy).joinedload(PatientInsurancePolicy.provider),
        )
        .all()
    )
    claim_map = {c.invoice_id: c for c in claims}

    buckets_summary = {
        "current_0_30_inr": 0.0,
        "aging_31_60_inr": 0.0,
        "aging_61_90_inr": 0.0,
        "aging_over_90_inr": 0.0,
        "total_outstanding_inr": 0.0,
    }

    tpa_breakdown: Dict[str, Dict[str, Any]] = {}
    row_items = []

    for inv in invoices:
        balance_paise = inv.net_amount_paise - inv.amount_paid_paise
        if balance_paise <= 0:
            continue
        balance_inr = round(balance_paise / 100, 2)
        inv_date = inv.created_at.date() if inv.created_at else reference_date
        days_aged = max(0, (reference_date - inv_date).days)

        claim = claim_map.get(inv.id)
        provider_name = "Self-Pay (Patient)"
        provider_code = "SELFPAY"
        if claim and claim.policy and claim.policy.provider:
            provider_name = claim.policy.provider.name
            provider_code = claim.policy.provider.code
            if provider_id and claim.policy.provider_id != provider_id:
                continue

        if provider_code not in tpa_breakdown:
            tpa_breakdown[provider_code] = {
                "provider_code": provider_code,
                "provider_name": provider_name,
                "invoices_count": 0,
                "bucket_0_30_inr": 0.0,
                "bucket_31_60_inr": 0.0,
                "bucket_61_90_inr": 0.0,
                "bucket_over_90_inr": 0.0,
                "total_due_inr": 0.0,
            }

        tpa = tpa_breakdown[provider_code]
        tpa["invoices_count"] += 1
        tpa["total_due_inr"] = round(tpa["total_due_inr"] + balance_inr, 2)
        buckets_summary["total_outstanding_inr"] = round(buckets_summary["total_outstanding_inr"] + balance_inr, 2)

        if days_aged <= 30:
            bucket_label = "0-30 days"
            tpa["bucket_0_30_inr"] = round(tpa["bucket_0_30_inr"] + balance_inr, 2)
            buckets_summary["current_0_30_inr"] = round(buckets_summary["current_0_30_inr"] + balance_inr, 2)
        elif days_aged <= 60:
            bucket_label = "31-60 days"
            tpa["bucket_31_60_inr"] = round(tpa["bucket_31_60_inr"] + balance_inr, 2)
            buckets_summary["aging_31_60_inr"] = round(buckets_summary["aging_31_60_inr"] + balance_inr, 2)
        elif days_aged <= 90:
            bucket_label = "61-90 days"
            tpa["bucket_61_90_inr"] = round(tpa["bucket_61_90_inr"] + balance_inr, 2)
            buckets_summary["aging_61_90_inr"] = round(buckets_summary["aging_61_90_inr"] + balance_inr, 2)
        else:
            bucket_label = ">90 days"
            tpa["bucket_over_90_inr"] = round(tpa["bucket_over_90_inr"] + balance_inr, 2)
            buckets_summary["aging_over_90_inr"] = round(buckets_summary["aging_over_90_inr"] + balance_inr, 2)

        p = inv.patient
        row_items.append({
            "invoice_number": inv.invoice_number,
            "patient_mrn": p.mrn if p else "",
            "patient_name": p.full_name if p else "",
            "payer_source": provider_name,
            "invoice_date": inv_date.strftime("%Y-%m-%d"),
            "days_aged": days_aged,
            "aging_bucket": bucket_label,
            "net_amount_inr": round(inv.net_amount_paise / 100, 2),
            "amount_paid_inr": round(inv.amount_paid_paise / 100, 2),
            "outstanding_balance_inr": balance_inr,
        })

    if export_format and export_format.lower() == "csv":
        fieldnames = [
            "invoice_number",
            "patient_mrn",
            "patient_name",
            "payer_source",
            "invoice_date",
            "days_aged",
            "aging_bucket",
            "net_amount_inr",
            "amount_paid_inr",
            "outstanding_balance_inr",
        ]
        filename = f"ar_aging_report_as_of_{reference_date}"
        return stream_csv_response(iter(row_items), fieldnames, filename)

    return {
        "as_of_date": reference_date.strftime("%Y-%m-%d"),
        "summary": buckets_summary,
        "payers": list(tpa_breakdown.values()),
        "invoices_sample": row_items[:100],
    }


# =====================================================================
# 5. BIO-MEDICAL WASTE (BMW) MANAGEMENT STATUTORY REGISTER
# =====================================================================
@router.get("/biomedical-waste")
def get_biomedical_waste_statutory_register(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    export_format: Optional[str] = Query(default=None, alias="format"),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("service_ops:read")),
):
    """Generates the statutory Bio-Medical Waste (BMW) register under Indian BMW Rules 2016."""
    start_at, end_at = resolve_record_date_window(start_date, end_date)
    query = (
        db.query(BiomedicalWasteBag)
        .options(joinedload(BiomedicalWasteBag.manifest))
    )
    if start_at is not None and end_at is not None:
        query = query.filter(BiomedicalWasteBag.logged_at >= start_at, BiomedicalWasteBag.logged_at < end_at)

    bags = query.order_by(BiomedicalWasteBag.logged_at.desc()).all()

    def row_generator():
        for b in bags:
            weight_kg = round(b.weight_grams / 1000, 3)
            yield {
                "barcode": b.barcode,
                "logged_at": b.logged_at.strftime("%Y-%m-%d %H:%M:%S") if b.logged_at else "",
                "color_category": b.color_category.value if hasattr(b.color_category, "value") else str(b.color_category),
                "weight_kg": weight_kg,
                "status": b.status.value if hasattr(b.status, "value") else str(b.status),
                "source_department": b.source_department or "",
                "manifest_number": b.manifest.manifest_number if b.manifest else "PENDING_HANDOVER",
                "cbwtf_operator": b.manifest.cbwtf_operator_name if b.manifest else "N/A",
                "cbwtf_vehicle_number": b.manifest.cbwtf_vehicle_number if b.manifest else "N/A",
            }

    if export_format and export_format.lower() == "csv":
        fieldnames = [
            "barcode",
            "logged_at",
            "color_category",
            "weight_kg",
            "status",
            "source_department",
            "manifest_number",
            "cbwtf_operator",
            "cbwtf_vehicle_number",
        ]
        filename = f"biomedical_waste_register_{start_date or 'all'}_{end_date or 'all'}"
        return stream_csv_response(row_generator(), fieldnames, filename)

    return {
        "total_bags_count": len(bags),
        "total_weight_kg": round(sum(b.weight_grams for b in bags) / 1000, 3),
        "items": list(row_generator())[:100],
    }
