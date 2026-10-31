from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.task_block_schemas import TaskBlockCreate, TaskBlockUpdate


def test_task_block_create_accepts_valid_interval() -> None:
    start = datetime(2026, 10, 31, 9, 0, tzinfo=UTC)
    block = TaskBlockCreate(task_id=uuid4(), start_at=start, end_at=start + timedelta(hours=1))

    assert block.start_at == start
    assert block.end_at == start + timedelta(hours=1)


def test_task_block_create_rejects_naive_timestamps() -> None:
    start = datetime(2026, 10, 31, 9, 0)
    with pytest.raises(ValidationError):
        TaskBlockCreate(task_id=uuid4(), start_at=start, end_at=start + timedelta(hours=1))


def test_task_block_create_rejects_nonpositive_interval() -> None:
    start = datetime(2026, 10, 31, 9, 0, tzinfo=UTC)
    with pytest.raises(ValidationError):
        TaskBlockCreate(task_id=uuid4(), start_at=start, end_at=start)


def test_task_block_update_accepts_partial_interval() -> None:
    start = datetime(2026, 10, 31, 9, 0, tzinfo=UTC)
    update = TaskBlockUpdate(end_at=start + timedelta(minutes=30))

    assert update.start_at is None
    assert update.end_at == start + timedelta(minutes=30)


def test_task_block_update_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        TaskBlockUpdate(start_at=datetime(2026, 10, 31, 9, 0))
