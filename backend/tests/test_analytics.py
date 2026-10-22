from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.api.routes.analytics import day_bounds, money_totals, week_monday


def test_week_monday_returns_monday_for_any_weekday() -> None:
    assert week_monday(date(2026, 10, 22)) == date(2026, 10, 19)
    assert week_monday(date(2026, 10, 19)) == date(2026, 10, 19)


def test_day_bounds_respect_timezone_offset() -> None:
    start, end = day_bounds(date(2026, 10, 22), ZoneInfo("Europe/Tallinn"))
    assert start.tzinfo is not None
    assert end > start
    assert start.hour == 0
    assert end.hour == 0


def test_money_totals_support_lesson_accrual_and_payments() -> None:
    rows = [
        SimpleNamespace(currency_code="EUR", price_amount=Decimal("45.00")),
        SimpleNamespace(currency_code="EUR", price_amount=Decimal("30.00")),
    ]
    assert money_totals(rows)[0].currency_code == "EUR"
    assert money_totals(rows)[0].amount == Decimal("75.00")
