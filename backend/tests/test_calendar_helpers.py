from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.api.routes.integrations import _aware_google_datetime, _event_times
from app.integration_schemas import CalendarSelectionUpdate


def test_google_datetime_is_normalized_to_utc() -> None:
    value = _aware_google_datetime("2026-10-22T15:30:00+03:00", "Europe/Tallinn")
    assert value == datetime(2026, 10, 22, 12, 30, tzinfo=UTC)


def test_all_day_event_end_is_exclusive_utc_interval() -> None:
    start, end, all_day = _event_times(
        {"start": {"date": "2026-10-22"}, "end": {"date": "2026-10-23"}},
        "Europe/Tallinn",
    )
    assert all_day is True
    assert start is not None and end is not None
    assert end > start


def test_calendar_selection_rejects_duplicate_ids() -> None:
    with pytest.raises(ValidationError):
        CalendarSelectionUpdate(calendar_ids=["primary", "primary"])


def test_calendar_selection_rejects_empty_ids() -> None:
    with pytest.raises(ValidationError):
        CalendarSelectionUpdate(calendar_ids=["primary", "  "])


def test_google_datetime_rejects_malformed_input() -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        _aware_google_datetime("not-a-time", "UTC")
