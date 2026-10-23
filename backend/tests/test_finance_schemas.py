from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.finance_schemas import FinanceTransactionCreate


def test_create_transaction_normalizes_currency_and_category() -> None:
    payload = FinanceTransactionCreate(
        kind="expense",
        amount=Decimal("12.50"),
        currency_code="eur",
        category="  Transport  ",
        occurred_at=datetime(2026, 10, 23, 9, 0, tzinfo=UTC),
    )
    assert payload.currency_code == "EUR"
    assert payload.category == "Transport"


def test_create_transaction_requires_timezone() -> None:
    with pytest.raises(ValidationError):
        FinanceTransactionCreate(
            kind="income",
            amount=Decimal("20"),
            currency_code="EUR",
            category="Tutoring",
            occurred_at=datetime(2026, 10, 23, 9, 0),
        )


def test_create_transaction_rejects_non_positive_amount() -> None:
    with pytest.raises(ValidationError):
        FinanceTransactionCreate(
            kind="expense",
            amount=Decimal("0"),
            currency_code="EUR",
            category="Food",
            occurred_at=datetime(2026, 10, 23, 9, 0, tzinfo=UTC),
        )
