from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import get_db
from app.models import User
from app.models_tasks import Task, TimeEntry, TimerSession
from app.task_schemas import TimerRead, TimerStart

router = APIRouter(prefix="/timer", tags=["time tracking"])


def get_active_session(db: Session, user_id: UUID) -> TimerSession | None:
    return db.scalar(
        select(TimerSession)
        .where(
            TimerSession.user_id == user_id,
            TimerSession.status.in_(("running", "paused")),
        )
        .with_for_update()
    )


def to_timer_read(session: TimerSession, now: datetime | None = None) -> TimerRead:
    elapsed = session.elapsed_seconds
    current_time = now or datetime.now(UTC)
    if session.status == "running" and session.last_resumed_at is not None:
        elapsed += max(0, int((current_time - session.last_resumed_at).total_seconds()))
    return TimerRead(
        id=session.id,
        task_id=session.task_id,
        category=session.category,
        started_at=session.started_at,
        status=cast(Literal["running", "paused", "stopped"], session.status),
        elapsed_seconds=elapsed,
        finished_at=session.finished_at,
    )


def validate_task_owner(db: Session, user_id: UUID, task_id: UUID | None) -> None:
    if task_id is None:
        return
    task = db.scalar(select(Task.id).where(Task.id == task_id, Task.user_id == user_id))
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")


@router.get("/current", response_model=TimerRead | None)
def current_timer(
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> TimerRead | None:
    session = get_active_session(db, user.id)
    return to_timer_read(session) if session else None


@router.post("/start", response_model=TimerRead, status_code=status.HTTP_201_CREATED)
def start_timer(
    payload: TimerStart,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> TimerRead:
    if get_active_session(db, user.id) is not None:
        raise HTTPException(status_code=409, detail="A timer is already active")
    validate_task_owner(db, user.id, payload.task_id)
    now = datetime.now(UTC)
    session = TimerSession(
        user_id=user.id,
        task_id=payload.task_id,
        category=payload.category,
        started_at=now,
        last_resumed_at=now,
        elapsed_seconds=0,
        status="running",
    )
    db.add(session)
    try:
        db.commit()
        db.refresh(session)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A timer is already active") from exc
    return to_timer_read(session, now)


@router.post("/pause", response_model=TimerRead)
def pause_timer(
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> TimerRead:
    session = get_active_session(db, user.id)
    if session is None or session.status != "running" or session.last_resumed_at is None:
        raise HTTPException(status_code=409, detail="No running timer to pause")
    now = datetime.now(UTC)
    session.elapsed_seconds += max(0, int((now - session.last_resumed_at).total_seconds()))
    session.last_resumed_at = None
    session.status = "paused"
    db.commit()
    db.refresh(session)
    return to_timer_read(session, now)


@router.post("/resume", response_model=TimerRead)
def resume_timer(
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> TimerRead:
    session = get_active_session(db, user.id)
    if session is None or session.status != "paused":
        raise HTTPException(status_code=409, detail="No paused timer to resume")
    now = datetime.now(UTC)
    session.last_resumed_at = now
    session.status = "running"
    db.commit()
    db.refresh(session)
    return to_timer_read(session, now)


@router.post("/stop", response_model=TimerRead)
def stop_timer(
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> TimerRead:
    session = get_active_session(db, user.id)
    if session is None:
        raise HTTPException(status_code=409, detail="No active timer to stop")
    now = datetime.now(UTC)
    if session.status == "running" and session.last_resumed_at is not None:
        session.elapsed_seconds += max(0, int((now - session.last_resumed_at).total_seconds()))
    session.last_resumed_at = None
    session.status = "stopped"
    session.finished_at = now
    entry = TimeEntry(
        user_id=user.id,
        task_id=session.task_id,
        category=session.category,
        notes=None,
        started_at=session.started_at,
        ended_at=now,
        duration_seconds=session.elapsed_seconds,
        source="timer",
    )
    db.add(entry)
    db.flush()
    session.time_entry_id = entry.id
    db.commit()
    db.refresh(session)
    return to_timer_read(session, now)
