from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

FinanceKind = Literal["income", "expense"]


class FinanceTransactionCreate(BaseModel):
    kind: FinanceKind
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency_code: str = Field(default="EUR", min_length=3, max_length=3)
    category: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=1000)
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("currency_code must be a three-letter currency code")
        return normalized

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("category cannot be blank")
        return normalized


class FinanceTransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: FinanceKind
    amount: Decimal
    currency_code: str
    category: str
    description: str | None
    occurred_at: datetime
    created_at: datetime


class FinanceSummary(BaseModel):
    currency_code: str
    income: Decimal
    expenses: Decimal
    balance: Decimal
    transaction_count: int
