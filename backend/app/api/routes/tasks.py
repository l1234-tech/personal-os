from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import get_db
from app.models import User
from app.models_tasks import Task, TimeEntry
from app.task_schemas import (
    TaskCreate,
    TaskRead,
    TaskUpdate,
    TimeEntryCreate,
    TimeEntryRead,
    TimeEntryUpdate,
)

router = APIRouter(tags=["tasks and time tracking"])


def get_owned_task(db: Session, user_id: UUID, task_id: UUID) -> Task:
    task = db.scalar(select(Task).where(Task.id == task_id, Task.user_id == user_id))
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def get_owned_entry(db: Session, user_id: UUID, entry_id: UUID) -> TimeEntry:
    entry = db.scalar(
        select(TimeEntry).where(TimeEntry.id == entry_id, TimeEntry.user_id == user_id)
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="Time entry not found")
    return entry


def validate_task_link(db: Session, user_id: UUID, task_id: UUID | None) -> None:
    if task_id is not None:
        get_owned_task(db, user_id, task_id)


@router.get("/tasks", response_model=list[TaskRead])
def list_tasks(
    task_status: str | None = Query(default=None, alias="status", pattern="^(todo|in_progress|done|cancelled)$"),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[Task]:
    query = select(Task).where(Task.user_id == user.id)
    if task_status is not None:
        query = query.where(Task.status == task_status)
    query = query.order_by(Task.due_at.asc().nulls_last(), Task.created_at.desc()).limit(limit)
    return list(db.scalars(query).all())


@router.post("/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> Task:
    data = payload.model_dump()
    data["title"] = data["title"].strip()
    if not data["title"]:
        raise HTTPException(status_code=422, detail="Task title cannot be blank")
    task = Task(user_id=user.id, **data)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> Task:
    task = get_owned_task(db, user.id, task_id)
    changes = payload.model_dump(exclude_unset=True)
    for name in ("title", "status", "priority", "category"):
        if name in changes and changes[name] is None:
            raise HTTPException(status_code=422, detail=f"{name} cannot be null")
    if "title" in changes:
        changes["title"] = changes["title"].strip()
        if not changes["title"]:
            raise HTTPException(status_code=422, detail="Task title cannot be blank")
    for name, value in changes.items():
        setattr(task, name, value)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: UUID,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> Response:
    task = get_owned_task(db, user.id, task_id)
    db.delete(task)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/time-entries", response_model=list[TimeEntryRead])
def list_time_entries(
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[TimeEntry]:
    query = (
        select(TimeEntry)
        .where(TimeEntry.user_id == user.id)
        .order_by(TimeEntry.started_at.desc())
        .limit(limit)
    )
    return list(db.scalars(query).all())


@router.post("/time-entries", response_model=TimeEntryRead, status_code=status.HTTP_201_CREATED)
def create_time_entry(
    payload: TimeEntryCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> TimeEntry:
    validate_task_link(db, user.id, payload.task_id)
    duration = int((payload.ended_at - payload.started_at).total_seconds())
    if duration <= 0 or duration > 31_536_000:
        raise HTTPException(status_code=422, detail="Time entry duration must be between 1 second and 365 days")
    entry = TimeEntry(
        user_id=user.id,
        task_id=payload.task_id,
        category=payload.category,
        notes=payload.notes,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        duration_seconds=duration,
        source=payload.source,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.patch("/time-entries/{entry_id}", response_model=TimeEntryRead)
def update_time_entry(
    entry_id: UUID,
    payload: TimeEntryUpdate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> TimeEntry:
    entry = get_owned_entry(db, user.id, entry_id)
    changes = payload.model_dump(exclude_unset=True)
    if any(changes.get(key, "not_set") is None for key in ("started_at", "ended_at") if key in changes):
        raise HTTPException(status_code=422, detail="Timestamps cannot be null")
    if "task_id" in changes:
        validate_task_link(db, user.id, changes["task_id"])
    new_start = changes.get("started_at", entry.started_at)
    new_end = changes.get("ended_at", entry.ended_at)
    if new_end <= new_start:
        raise HTTPException(status_code=422, detail="ended_at must be later than started_at")
    if ("started_at" in changes or "ended_at" in changes) and "duration_seconds" not in changes:
        if entry.source != "timer":
            changes["duration_seconds"] = int((new_end - new_start).total_seconds())
    duration = changes.get("duration_seconds", entry.duration_seconds)
    if duration < 0 or duration > 31_536_000:
        raise HTTPException(status_code=422, detail="Duration is outside supported range")
    for name, value in changes.items():
        setattr(entry, name, value)
    db.commit()
    db.refresh(entry)
    return entry
