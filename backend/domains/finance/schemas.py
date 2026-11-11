from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

MAX_EXPENSE_AMOUNT_PAISE = 2_147_483_647  # PostgreSQL INTEGER storage limit


from backend.domains.finance.models import (
    ExpenseCategoryEnum,
    ExpenseStatusEnum,
    RecurringFrequencyEnum,
)


class ExpenseDraft(BaseModel):
    category: ExpenseCategoryEnum
    title: str = Field(min_length=2, max_length=150)
    amount_paise: int = Field(gt=0, le=MAX_EXPENSE_AMOUNT_PAISE)
    vendor_name: Optional[str] = None
    due_date: Optional[datetime] = None


class ExpenseAdjudicate(BaseModel):
    status: Literal[ExpenseStatusEnum.APPROVED, ExpenseStatusEnum.REJECTED]
    rejection_reason: Optional[str] = None


class RecurringTemplateCreate(BaseModel):
    category: ExpenseCategoryEnum
    title: str = Field(min_length=2)
    amount_paise: int = Field(gt=0, le=MAX_EXPENSE_AMOUNT_PAISE)
    vendor_name: Optional[str] = None
    frequency: RecurringFrequencyEnum
    next_generation_date: datetime
    auto_approve: bool = False
