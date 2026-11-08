"""Bank statement ingestion and controlled supplier-payment matching.

The account_key is an opaque tenant-local alias supplied by the bank integration.
Never submit raw account numbers, credentials, or unrelated customer statement data
through this JSON endpoint. Credits remain classification work and are never treated
as income or matched automatically.
"""
from datetime import date, datetime, timezone
from typing import List, Optional
from collections import defaultdict
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.core.database import get_db
from backend.core.dependencies import RequirePermission, validate_pagination
from backend.domains.identity.models import User
from backend.domains.procurement.models import (
    BankStatementBatch,
    BankStatementLine,
    SupplierPayment,
    SupplierPaymentBankMatch,
    SupplierPaymentRequest,
)

router = APIRouter()


class BankStatementLineImport(BaseModel):
    bank_transaction_id: str = Field(min_length=1, max_length=160)
    transaction_date: date
    value_date: Optional[date] = None
    direction: str
    amount_paise: int = Field(gt=0)
    bank_reference: Optional[str] = Field(default=None, max_length=160)
    description: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_line(self):
        if self.direction not in {"DEBIT", "CREDIT"}:
            raise ValueError("direction must be DEBIT or CREDIT.")
        if not self.bank_transaction_id.strip():
            raise ValueError("bank_transaction_id cannot be blank.")
        return self


class BankStatementImport(BaseModel):
    account_key: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,63}$")
    account_label: Optional[str] = Field(default=None, max_length=80)
    statement_reference: str = Field(min_length=1, max_length=120)
    period_start: date
    period_end: date
    opening_balance_paise: int
    closing_balance_paise: int
    lines: List[BankStatementLineImport] = Field(min_length=1, max_length=5000)

    @model_validator(mode="after")
    def validate_statement(self):
        if self.account_key.strip().isdigit():
            raise ValueError("account_key must be an opaque alias, not a numeric account number.")
        if self.account_label and re.search(r"\\d{8,}", self.account_label):
            raise ValueError("account_label must be masked and cannot contain an unmasked account-number-like sequence.")
        if self.period_end < self.period_start:
            raise ValueError("Statement period end cannot precede its start.")
        if not self.statement_reference.strip():
            raise ValueError("statement_reference cannot be blank.")
        ids = [row.bank_transaction_id.strip() for row in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("A statement cannot contain duplicate bank transaction IDs.")
        if any(row.transaction_date < self.period_start or row.transaction_date > self.period_end for row in self.lines):
            raise ValueError("Every transaction date must fall within the statement period.")
        credits = sum(row.amount_paise for row in self.lines if row.direction == "CREDIT")
        debits = sum(row.amount_paise for row in self.lines if row.direction == "DEBIT")
        if self.opening_balance_paise + credits - debits != self.closing_balance_paise:
            raise ValueError("Statement closing balance must equal opening balance plus credits minus debits.")
        return self


class BankStatementLineResponse(BaseModel):
    id: int
    bank_transaction_id: str
    transaction_date: date
    value_date: Optional[date]
    direction: str
    amount_paise: int
    bank_reference: Optional[str]
    description: Optional[str]
    model_config = ConfigDict(from_attributes=True)


class BankStatementBatchResponse(BaseModel):
    id: int
    account_key: str
    account_label: Optional[str]
    statement_reference: str
    period_start: date
    period_end: date
    opening_balance_paise: int
    closing_balance_paise: int
    imported_by_id: int
    imported_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SupplierPaymentBankMatchCreate(BaseModel):
    supplier_payment_id: int = Field(gt=0)
    amount_paise: int = Field(gt=0)
    reason: str = Field(min_length=5, max_length=1000)


class SupplierPaymentBankMatchResponse(BaseModel):
    id: int
    statement_line_id: int
    supplier_payment_id: int
    amount_paise: int
    matched_by_id: int
    matched_at: datetime
    reason: str
    model_config = ConfigDict(from_attributes=True)


@router.post("/bank-statements/import", response_model=BankStatementBatchResponse, status_code=status.HTTP_201_CREATED)
def import_bank_statement(
    payload: BankStatementImport,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:write")),
):
    account_key = payload.account_key.strip()
    statement_reference = payload.statement_reference.strip()
    if db.query(BankStatementBatch.id).filter(
        BankStatementBatch.account_key == account_key,
        BankStatementBatch.statement_reference == statement_reference,
    ).first():
        raise HTTPException(status_code=409, detail="This statement has already been imported.")

    batch = BankStatementBatch(
        account_key=account_key,
        account_label=payload.account_label.strip() if payload.account_label else None,
        statement_reference=statement_reference,
        period_start=payload.period_start,
        period_end=payload.period_end,
        opening_balance_paise=payload.opening_balance_paise,
        closing_balance_paise=payload.closing_balance_paise,
        imported_by_id=current_user.id,
    )
    try:
        db.add(batch)
        db.flush()
        for line in payload.lines:
            transaction_id = line.bank_transaction_id.strip()
            if db.query(BankStatementLine.id).filter(
                BankStatementLine.account_key == account_key,
                BankStatementLine.bank_transaction_id == transaction_id,
            ).first():
                raise HTTPException(status_code=409, detail=f"Bank transaction {transaction_id} was already imported.")
            db.add(BankStatementLine(
                batch_id=batch.id,
                account_key=account_key,
                bank_transaction_id=transaction_id,
                transaction_date=line.transaction_date,
                value_date=line.value_date,
                direction=line.direction,
                amount_paise=line.amount_paise,
                bank_reference=line.bank_reference.strip() if line.bank_reference else None,
                description=line.description.strip() if line.description else None,
            ))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Statement or bank transaction identity already exists.") from exc
    db.refresh(batch)
    return batch


@router.get("/bank-statements", response_model=dict)
def list_bank_statements(
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    page, page_size = validate_pagination(page, page_size)
    query = db.query(BankStatementBatch).order_by(BankStatementBatch.id.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [BankStatementBatchResponse.model_validate(row).model_dump(mode="json") for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/bank-statements/{batch_id}/lines", response_model=dict)
def list_bank_statement_lines(
    batch_id: int,
    direction: Optional[str] = Query(default=None, pattern="^(DEBIT|CREDIT)$"),
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=100, gt=0),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    page, page_size = validate_pagination(page, page_size)
    if db.get(BankStatementBatch, batch_id) is None:
        raise HTTPException(status_code=404, detail="Bank statement not found.")
    query = db.query(BankStatementLine).filter(BankStatementLine.batch_id == batch_id)
    if direction:
        query = query.filter(BankStatementLine.direction == direction)
    query = query.order_by(BankStatementLine.transaction_date, BankStatementLine.id)
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [BankStatementLineResponse.model_validate(row).model_dump(mode="json") for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/supplier-payments", response_model=dict)
def list_supplier_payments(
    vendor_id: Optional[int] = Query(default=None, gt=0),
    page: int = Query(default=1, gt=0),
    page_size: int = Query(default=50, gt=0),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    page, page_size = validate_pagination(page, page_size)
    query = db.query(SupplierPayment).options(
        selectinload(SupplierPayment.allocations)
    )
    if vendor_id is not None:
        query = query.filter(SupplierPayment.vendor_id == vendor_id)
    query = query.order_by(SupplierPayment.payment_date.desc(), SupplierPayment.id.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [
            {
                "id": row.id,
                "vendor_id": row.vendor_id,
                "payment_reference": row.payment_reference,
                "payment_method": row.payment_method.value,
                "payment_date": row.payment_date,
                "amount_paise": row.amount_paise,
                "notes": row.notes,
                "recorded_by_id": row.recorded_by_id,
                "allocations": [
                    {"id": item.id, "invoice_id": item.invoice_id, "amount_paise": item.amount_paise}
                    for item in row.allocations
                ],
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/bank-statement-lines/{line_id}/matches", status_code=status.HTTP_201_CREATED)
def match_bank_debit_to_supplier_payment(
    line_id: int,
    payload: SupplierPaymentBankMatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RequirePermission("finance:write")),
):
    # Lock in a stable type order: statement line first, then payment.
    line = db.query(BankStatementLine).filter(
        BankStatementLine.id == line_id
    ).with_for_update().one_or_none()
    if line is None:
        raise HTTPException(status_code=404, detail="Bank statement line not found.")
    if line.direction != "DEBIT":
        raise HTTPException(status_code=409, detail="Only bank DEBIT lines can be matched to supplier payments.")

    payment = db.query(SupplierPayment).filter(
        SupplierPayment.id == payload.supplier_payment_id
    ).with_for_update().one_or_none()
    if payment is None:
        raise HTTPException(status_code=404, detail="Supplier payment not found.")

    if db.query(SupplierPaymentBankMatch.id).filter(
        SupplierPaymentBankMatch.statement_line_id == line.id,
        SupplierPaymentBankMatch.supplier_payment_id == payment.id,
    ).first():
        raise HTTPException(status_code=409, detail="This bank line and supplier payment are already linked.")

    line_matched = db.query(func.coalesce(func.sum(SupplierPaymentBankMatch.amount_paise), 0)).filter(
        SupplierPaymentBankMatch.statement_line_id == line.id
    ).scalar()
    payment_matched = db.query(func.coalesce(func.sum(SupplierPaymentBankMatch.amount_paise), 0)).filter(
        SupplierPaymentBankMatch.supplier_payment_id == payment.id
    ).scalar()
    line_remaining = int(line.amount_paise) - int(line_matched or 0)
    payment_remaining = int(payment.amount_paise) - int(payment_matched or 0)
    if payload.amount_paise > line_remaining or payload.amount_paise > payment_remaining:
        raise HTTPException(status_code=409, detail={
            "message": "Match amount exceeds the remaining amount on the bank line or supplier payment.",
            "line_remaining_paise": line_remaining,
            "payment_remaining_paise": payment_remaining,
        })

    match = SupplierPaymentBankMatch(
        statement_line_id=line.id,
        supplier_payment_id=payment.id,
        amount_paise=payload.amount_paise,
        matched_by_id=current_user.id,
        matched_at=datetime.now(timezone.utc),
        reason=payload.reason.strip(),
    )
    db.add(match)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="This bank line and supplier payment are already linked.") from exc
    db.refresh(match)
    return SupplierPaymentBankMatchResponse.model_validate(match).model_dump(mode="json")


@router.get("/bank-statement-lines/{line_id}/matches", response_model=dict)
def list_bank_statement_line_matches(
    line_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    line = db.get(BankStatementLine, line_id)
    if line is None:
        raise HTTPException(status_code=404, detail="Bank statement line not found.")
    rows = db.query(SupplierPaymentBankMatch).filter(
        SupplierPaymentBankMatch.statement_line_id == line_id
    ).order_by(SupplierPaymentBankMatch.id).all()
    matched = sum(row.amount_paise for row in rows)
    return {
        "items": [SupplierPaymentBankMatchResponse.model_validate(row).model_dump(mode="json") for row in rows],
        "line_amount_paise": line.amount_paise,
        "matched_amount_paise": matched,
        "remaining_amount_paise": line.amount_paise - matched,
    }



@router.get("/reconciliation/candidates", response_model=dict)
def list_reconciliation_candidates(
    as_of: Optional[date] = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
    _: User = Depends(RequirePermission("finance:read")),
):
    """Return deterministic source-data candidates for human reconciliation review.

    These are indicators only: no candidate is a fraud finding, accounting
    classification, or automatically created/closed investigation.
    """
    as_of = as_of or date.today()
    candidates = []
    source_cap = 5001

    lines = db.query(BankStatementLine).order_by(BankStatementLine.id).limit(source_cap).all()
    line_matches = dict(
        db.query(
            SupplierPaymentBankMatch.statement_line_id,
            func.coalesce(func.sum(SupplierPaymentBankMatch.amount_paise), 0),
        ).group_by(SupplierPaymentBankMatch.statement_line_id).all()
    )
    for line in lines:
        matched = int(line_matches.get(line.id, 0) or 0)
        if line.direction == "CREDIT":
            candidates.append({
                "candidate_type": "UNCLASSIFIED_BANK_CREDIT",
                "source_id": line.id,
                "transaction_date": line.transaction_date.isoformat(),
                "amount_paise": int(line.amount_paise),
                "reference": line.bank_reference or line.bank_transaction_id,
                "review_note": "Credit requires manual accounting classification; this system does not infer income.",
            })
        elif matched < int(line.amount_paise):
            candidates.append({
                "candidate_type": "UNMATCHED_BANK_DEBIT" if matched == 0 else "PARTIALLY_MATCHED_BANK_DEBIT",
                "source_id": line.id,
                "transaction_date": line.transaction_date.isoformat(),
                "amount_paise": int(line.amount_paise),
                "matched_amount_paise": matched,
                "remaining_amount_paise": int(line.amount_paise) - matched,
                "reference": line.bank_reference or line.bank_transaction_id,
            })

    payments = db.query(SupplierPayment).order_by(SupplierPayment.id).limit(source_cap).all()
    payment_matches = dict(
        db.query(
            SupplierPaymentBankMatch.supplier_payment_id,
            func.coalesce(func.sum(SupplierPaymentBankMatch.amount_paise), 0),
        ).group_by(SupplierPaymentBankMatch.supplier_payment_id).all()
    )
    reference_groups = defaultdict(list)
    for payment in payments:
        matched = int(payment_matches.get(payment.id, 0) or 0)
        if matched < int(payment.amount_paise):
            candidates.append({
                "candidate_type": "UNRECONCILED_SUPPLIER_PAYMENT" if matched == 0 else "PARTIALLY_RECONCILED_SUPPLIER_PAYMENT",
                "source_id": payment.id,
                "transaction_date": payment.payment_date.date().isoformat(),
                "amount_paise": int(payment.amount_paise),
                "matched_amount_paise": matched,
                "remaining_amount_paise": int(payment.amount_paise) - matched,
                "reference": payment.payment_reference,
                "vendor_id": payment.vendor_id,
            })
        normalized = "".join(payment.payment_reference.casefold().split())
        reference_groups[(payment.vendor_id, normalized)].append(payment)
    for (vendor_id, normalized_reference), group in reference_groups.items():
        if normalized_reference and len(group) > 1:
            candidates.append({
                "candidate_type": "POSSIBLE_DUPLICATE_PAYMENT_REFERENCE",
                "source_ids": [row.id for row in group],
                "vendor_id": vendor_id,
                "reference": group[0].payment_reference,
                "review_note": "Normalized reference collision only; manual review required and no duplicate/fraud conclusion is made.",
            })

    overdue = db.query(SupplierPaymentRequest).filter(
        SupplierPaymentRequest.status == "APPROVED",
        SupplierPaymentRequest.scheduled_date < as_of,
        SupplierPaymentRequest.executed_payment_id.is_(None),
    ).order_by(SupplierPaymentRequest.scheduled_date, SupplierPaymentRequest.id).limit(source_cap).all()
    for request_row in overdue:
        candidates.append({
            "candidate_type": "OVERDUE_APPROVED_PAYMENT_REQUEST",
            "source_id": request_row.id,
            "scheduled_date": request_row.scheduled_date.isoformat(),
            "amount_paise": int(request_row.amount_paise),
            "reference": request_row.payment_reference,
            "vendor_id": request_row.vendor_id,
        })

    candidates.sort(key=lambda row: (row["candidate_type"], row.get("transaction_date", row.get("scheduled_date", "")), row.get("source_id", 0)))
    return {
        "items": candidates[:limit],
        "total_candidates": len(candidates),
        "limit": limit,
        "truncated": len(lines) == source_cap or len(payments) == source_cap or len(overdue) == source_cap or len(candidates) > limit,
        "as_of": as_of.isoformat(),
        "disclaimer": "Candidates are review prompts, not fraud findings or accounting conclusions.",
    }
