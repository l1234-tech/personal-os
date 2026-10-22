from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import get_db
from app.models import User
from app.models_tasks import Task, TimeEntry
from app.task_schemas import TimeEntryCreate, TimeEntryRead, TimeEntryUpdate

router = APIRouter(prefix="/time-entries", tags=["time tracking"])


def validate_task_owner(db: Session, user_id: UUID, task_id: UUID | None) -> None:
    if task_id is None:
        return
    exists = db.scalar(select(Task.id).where(Task.id == task_id, Task.user_id == user_id))
    if exists is None:
        raise HTTPException(status_code=404, detail="Task not found")


def entry_duration(started_at: datetime, ended_at: datetime) -> int:
    return max(0, int((ended_at - started_at).total_seconds()))


@router.get("", response_model=list[TimeEntryRead])
def list_time_entries(
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[TimeEntry]:
    return list(
        db.scalars(
            select(TimeEntry)
            .where(TimeEntry.user_id == user.id)
            .order_by(TimeEntry.started_at.desc())
            .limit(limit)
        ).all()
    )


@router.post("", response_model=TimeEntryRead, status_code=status.HTTP_201_CREATED)
def create_time_entry(
    payload: TimeEntryCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> TimeEntry:
    validate_task_owner(db, user.id, payload.task_id)
    entry = TimeEntry(
        user_id=user.id,
        task_id=payload.task_id,
        category=payload.category,
        notes=payload.notes,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        duration_seconds=entry_duration(payload.started_at, payload.ended_at),
        source=payload.source,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.patch("/{entry_id}", response_model=TimeEntryRead)
def update_time_entry(
    entry_id: UUID,
    payload: TimeEntryUpdate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> TimeEntry:
    entry = db.scalar(
        select(TimeEntry)
        .where(TimeEntry.id == entry_id, TimeEntry.user_id == user.id)
        .with_for_update()
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="Time entry not found")
    values = payload.model_dump(exclude_unset=True)
    validate_task_owner(db, user.id, values.get("task_id", entry.task_id))
    started_at = values.get("started_at", entry.started_at)
    ended_at = values.get("ended_at", entry.ended_at)
    if ended_at <= started_at:
        raise HTTPException(status_code=422, detail="ended_at must be later than started_at")
    for field in ("task_id", "category", "notes", "started_at", "ended_at"):
        if field in values:
            setattr(entry, field, values[field])
    if "started_at" in values or "ended_at" in values:
        entry.duration_seconds = entry_duration(started_at, ended_at)
    db.commit()
    db.refresh(entry)
    return entry
