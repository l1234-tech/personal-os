from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.tutoring_schemas import LessonCreate, PaymentCreate, StudentCreate


def test_student_rate_keeps_decimal_precision_and_currency_code() -> None:
    student = StudentCreate(
        name="Student",
        subject="Mathematics",
        rate_amount=Decimal("45.50"),
        currency_code="eur",
    )
    assert student.rate_amount == Decimal("45.50")
    assert student.currency_code == "EUR"


def test_lesson_requires_timezone_aware_schedule() -> None:
    with pytest.raises(ValidationError):
        LessonCreate(
            scheduled_start=datetime(2026, 10, 22, 10, 0),
            scheduled_end=datetime(2026, 10, 22, 11, 0),
        )


def test_lesson_rejects_invalid_time_interval() -> None:
    start = datetime(2026, 10, 22, 10, 0, tzinfo=UTC)
    with pytest.raises(ValidationError):
        LessonCreate(scheduled_start=start, scheduled_end=start - timedelta(minutes=1))


def test_payment_requires_timezone_and_positive_amount() -> None:
    with pytest.raises(ValidationError):
        PaymentCreate(
            student_id="49b9ad11-2822-47bc-a80e-9ef8fbc5c845",
            amount=Decimal("0.00"),
            currency_code="EUR",
            paid_at=datetime(2026, 10, 22, 10, 0),
        )
