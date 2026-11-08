"""Bank statement ingestion and controlled supplier-payment matching.

The account_key is an opaque tenant-local identifier supplied by the bank integration.
Never send raw account numbers, credentials, or statement files containing unrelated PII
through this JSON endpoint.
"""
from datetime import date, datetime, timezone
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.dependencies import RequirePermission, validate_pagination
from backend.domains.identity.models import User
from backend.domains.procurement.models import (
    BankStatementBatch,
    BankStatementLine,
    SupplierPayment,
    SupplierPaymentBankMatch,
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
    opening_balance_paise: int = Field(ge=0)
    closing_balance_paise: int = Field(ge=0)
    lines: List[BankStatementLineImport] = Field(min_length=1, max_length=5000)

    @model_validator(mode="after")
    def validate_statement(self):
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
    db.commit()
    db.refresh(match)
    return {
        "id": match.id,
        "statement_line_id": match.statement_line_id,
        "supplier_payment_id": match.supplier_payment_id,
        "amount_paise": match.amount_paise,
        "matched_by_id": match.matched_by_id,
        "matched_at": match.matched_at,
        "reason": match.reason,
    }
