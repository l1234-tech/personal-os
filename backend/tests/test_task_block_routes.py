from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes.task_blocks import (
    _owned_block,
    create_task_block,
    delete_task_block,
    update_task_block,
)
from app.models_integrations import TaskBlock
from app.task_block_schemas import TaskBlockCreate, TaskBlockUpdate


class FakeSession:
    def __init__(self, scalar_result=None) -> None:
        self.scalar_result = scalar_result
        self.added = None
        self.deleted = None
        self.committed = False

    def scalar(self, _statement):
        return self.scalar_result

    def add(self, value) -> None:
        self.added = value

    def delete(self, value) -> None:
        self.deleted = value

    def commit(self) -> None:
        self.committed = True

    def refresh(self, _value) -> None:
        return None


def make_task(status: str = "todo"):
    return SimpleNamespace(id=uuid4(), title="Prepare algorithms", status=status)


def make_block(user_id):
    start = datetime(2026, 10, 31, 9, 0, tzinfo=UTC)
    return TaskBlock(
        user_id=user_id,
        task_id=uuid4(),
        title="Prepare algorithms",
        start_at=start,
        end_at=start + timedelta(hours=1),
        idempotency_key=uuid4(),
    )


def test_create_task_block_persists_owned_open_task() -> None:
    user = SimpleNamespace(id=uuid4())
    task = make_task()
    db = FakeSession(task)
    start = datetime(2026, 10, 31, 9, 0, tzinfo=UTC)

    result = create_task_block(
        TaskBlockCreate(task_id=task.id, start_at=start, end_at=start + timedelta(hours=1)),
        db,
        user,
    )

    assert result.task_id == task.id
    assert result.user_id == user.id
    assert result.title == task.title
    assert db.added is result
    assert db.committed


@pytest.mark.parametrize("task_status", ["done", "cancelled"])
def test_create_task_block_rejects_closed_task(task_status: str) -> None:
    user = SimpleNamespace(id=uuid4())
    db = FakeSession(make_task(task_status))
    start = datetime(2026, 10, 31, 9, 0, tzinfo=UTC)

    with pytest.raises(HTTPException) as error:
        create_task_block(
            TaskBlockCreate(
                task_id=db.scalar_result.id,
                start_at=start,
                end_at=start + timedelta(hours=1),
            ),
            db,
            user,
        )

    assert error.value.status_code == 409
    assert db.added is None
    assert not db.committed


def test_update_task_block_changes_interval() -> None:
    user = SimpleNamespace(id=uuid4())
    block = make_block(user.id)
    db = FakeSession(block)
    next_end = block.end_at + timedelta(minutes=30)

    result = update_task_block(block.id, TaskBlockUpdate(end_at=next_end), db, user)

    assert result.end_at == next_end
    assert db.committed


def test_update_task_block_rejects_invalid_interval() -> None:
    user = SimpleNamespace(id=uuid4())
    block = make_block(user.id)
    db = FakeSession(block)

    with pytest.raises(HTTPException) as error:
        update_task_block(
            block.id,
            TaskBlockUpdate(end_at=block.start_at - timedelta(minutes=1)),
            db,
            user,
        )

    assert error.value.status_code == 422
    assert not db.committed


def test_delete_task_block_removes_only_the_block() -> None:
    user = SimpleNamespace(id=uuid4())
    block = make_block(user.id)
    db = FakeSession(block)

    response = delete_task_block(block.id, db, user)

    assert response.status_code == 204
    assert db.deleted is block
    assert db.committed


def test_task_block_lookup_is_scoped_to_owner() -> None:
    user_id = uuid4()

    class RecordingSession(FakeSession):
        statement = None

        def scalar(self, statement):
            self.statement = statement
            return None

    db = RecordingSession()

    with pytest.raises(HTTPException) as error:
        _owned_block(db, user_id, uuid4())

    assert error.value.status_code == 404
    assert db.statement is not None
    assert "task_blocks.user_id" in str(db.statement)
