from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.calendar_schemas import (
    PersonalCalendarEventCreate,
    PersonalCalendarEventRead,
    PersonalCalendarEventUpdate,
)
from app.db import get_db
from app.models import User
from app.models_integrations import PersonalCalendarEvent

router = APIRouter(prefix="/calendar", tags=["personal calendar"])


def _owned_event(db: Session, user_id: UUID, event_id: UUID) -> PersonalCalendarEvent:
    event = db.scalar(
        select(PersonalCalendarEvent).where(
            PersonalCalendarEvent.id == event_id,
            PersonalCalendarEvent.user_id == user_id,
        )
    )
    if event is None:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    return event


@router.get("/events", response_model=list[PersonalCalendarEventRead])
def list_events(
    start_at: datetime = Query(...),  # noqa: B008
    end_at: datetime = Query(...),  # noqa: B008
    limit: int = Query(default=300, ge=1, le=1000),
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[PersonalCalendarEvent]:
    if start_at.tzinfo is None or end_at.tzinfo is None or end_at <= start_at:
        raise HTTPException(status_code=422, detail="A valid timezone-aware interval is required")
    return list(
        db.scalars(
            select(PersonalCalendarEvent)
            .where(
                PersonalCalendarEvent.user_id == user.id,
                PersonalCalendarEvent.start_at < end_at,
                PersonalCalendarEvent.end_at > start_at,
            )
            .order_by(PersonalCalendarEvent.start_at.asc())
            .limit(limit)
        ).all()
    )


@router.post(
    "/events",
    response_model=PersonalCalendarEventRead,
    status_code=status.HTTP_201_CREATED,
)
def create_event(
    payload: PersonalCalendarEventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PersonalCalendarEvent:
    event = PersonalCalendarEvent(user_id=user.id, **payload.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.patch("/events/{event_id}", response_model=PersonalCalendarEventRead)
def update_event(
    event_id: UUID,
    payload: PersonalCalendarEventUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PersonalCalendarEvent:
    event = _owned_event(db, user.id, event_id)
    changes = payload.model_dump(exclude_unset=True)
    for field in ("title", "start_at", "end_at", "all_day", "color"):
        if field in changes and changes[field] is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")
    start_at = changes.get("start_at", event.start_at)
    end_at = changes.get("end_at", event.end_at)
    if start_at.tzinfo is None or end_at.tzinfo is None or end_at <= start_at:
        raise HTTPException(status_code=422, detail="A valid timezone-aware interval is required")
    for field, value in changes.items():
        setattr(event, field, value)
    # A changed local event must be queued for a future Google write, never silently marked synced.
    if changes and event.google_event_id:
        event.sync_status = "pending"
    elif changes:
        event.sync_status = "local"
    db.commit()
    db.refresh(event)
    return event


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    event = _owned_event(db, user.id, event_id)
    db.delete(event)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
