from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.task_schemas import TaskCreate, TimeEntryCreate


def test_task_schema_accepts_valid_task() -> None:
    task = TaskCreate(
        title="Prepare ML notes",
        priority="high",
        estimated_minutes=45,
        due_at=datetime(2026, 10, 30, 12, 0, tzinfo=UTC),
    )
    assert task.title == "Prepare ML notes"
    assert task.estimated_minutes == 45
    assert task.status == "todo"


def test_task_schema_rejects_naive_deadline() -> None:
    with pytest.raises(ValidationError):
        TaskCreate(title="Prepare ML notes", due_at=datetime(2026, 10, 30, 12, 0))


def test_manual_time_entry_requires_timezone_aware_timestamps() -> None:
    with pytest.raises(ValidationError):
        TimeEntryCreate(
            category="study",
            started_at=datetime(2026, 10, 22, 9, 0),
            ended_at=datetime(2026, 10, 22, 10, 0),
        )


def test_manual_time_entry_rejects_nonpositive_interval() -> None:
    start = datetime(2026, 10, 22, 9, 0, tzinfo=UTC)
    with pytest.raises(ValidationError):
        TimeEntryCreate(
            started_at=start,
            ended_at=start - timedelta(minutes=1),
        )
