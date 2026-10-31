from datetime import UTC, datetime
from uuid import UUID

import httpx
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
from app.integrations.google_calendar import (
    GOOGLE_CALENDAR_API,
    calendar_events_url,
    get_access_token,
)
from app.models import User
from app.models_integrations import CalendarSelection, Integration, PersonalCalendarEvent

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
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
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
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
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
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> Response:
    event = _owned_event(db, user.id, event_id)
    db.delete(event)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _google_event_datetime(value: object, field: str) -> tuple[datetime, bool]:
    if not isinstance(value, dict):
        raise HTTPException(status_code=502, detail=f"Google event has no valid {field}")
    date_value = value.get("date")
    date_time_value = value.get("dateTime")
    try:
        if isinstance(date_value, str):
            parsed_date = datetime.fromisoformat(date_value).date()
            return datetime.combine(parsed_date, datetime.min.time(), tzinfo=UTC), True
        if isinstance(date_time_value, str):
            parsed = datetime.fromisoformat(date_time_value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("Timezone is required")
            return parsed, False
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Google event has invalid {field}") from exc
    raise HTTPException(status_code=502, detail=f"Google event has no valid {field}")


@router.post("/events/{event_id}/resolve-google", response_model=PersonalCalendarEventRead)
def resolve_event_from_google(
    event_id: UUID,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> PersonalCalendarEvent:
    """Replace the local event with its current Google version after an explicit user choice."""
    event = _owned_event(db, user.id, event_id)
    if not event.google_calendar_id or not event.google_event_id:
        raise HTTPException(status_code=409, detail="This event is not linked to Google Calendar")
    integration = db.scalar(
        select(Integration).where(
            Integration.user_id == user.id,
            Integration.provider == "google_calendar",
            Integration.status == "active",
        )
    )
    if integration is None:
        raise HTTPException(status_code=409, detail="Connect Google Calendar first")
    access_token = get_access_token(db, integration)
    url = calendar_events_url(event.google_calendar_id)
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(
                f"{url}/{event.google_event_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Could not load the Google event") from exc
    if response.status_code == 404:
        raise HTTPException(status_code=409, detail="The linked Google event no longer exists")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Could not load the Google event")
    remote = response.json()
    if not isinstance(remote, dict):
        raise HTTPException(status_code=502, detail="Google returned an invalid event")
    title, etag = remote.get("summary"), remote.get("etag")
    if not isinstance(title, str) or not title.strip() or not isinstance(etag, str):
        raise HTTPException(status_code=502, detail="Google returned incomplete event data")
    start_at, start_all_day = _google_event_datetime(remote.get("start"), "start")
    end_at, end_all_day = _google_event_datetime(remote.get("end"), "end")
    if start_all_day != end_all_day or end_at <= start_at:
        raise HTTPException(status_code=502, detail="Google returned an invalid event interval")
    description = remote.get("description")
    if description is not None and not isinstance(description, str):
        description = None
    event.title = title.strip()
    event.description = description
    event.start_at = start_at
    event.end_at = end_at
    event.all_day = start_all_day
    event.google_etag = etag
    updated = remote.get("updated")
    try:
        event.google_updated_at = (
            datetime.fromisoformat(updated.replace("Z", "+00:00")).astimezone(UTC)
            if isinstance(updated, str)
            else None
        )
    except ValueError:
        event.google_updated_at = None
    event.sync_status = "synced"
    db.commit()
    db.refresh(event)
    return event


@router.post("/events/{event_id}/unpublish-google", response_model=PersonalCalendarEventRead)
def unpublish_event_from_google(
    event_id: UUID,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> PersonalCalendarEvent:
    """Delete the linked Google copy while keeping the Personal OS event."""
    event = _owned_event(db, user.id, event_id)
    if not event.google_calendar_id or not event.google_event_id or not event.google_etag:
        raise HTTPException(status_code=409, detail="This event has no complete Google link")
    integration = db.scalar(
        select(Integration).where(
            Integration.user_id == user.id,
            Integration.provider == "google_calendar",
            Integration.status == "active",
        )
    )
    if integration is None:
        raise HTTPException(status_code=409, detail="Connect Google Calendar first")
    access_token = get_access_token(db, integration)
    url = calendar_events_url(event.google_calendar_id)
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.delete(
                f"{url}/{event.google_event_id}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "If-Match": event.google_etag,
                },
            )
    except httpx.HTTPError as exc:
        event.sync_status = "error"
        db.commit()
        raise HTTPException(status_code=502, detail="Could not delete the Google event") from exc
    if response.status_code == 412:
        event.sync_status = "conflict"
        db.commit()
        raise HTTPException(
            status_code=409,
            detail="Google event changed; review it before deleting",
        )
    if response.status_code not in {204, 404}:
        event.sync_status = "error"
        db.commit()
        raise HTTPException(status_code=502, detail="Google rejected the event deletion")
    event.google_calendar_id = None
    event.google_event_id = None
    event.google_etag = None
    event.google_updated_at = None
    event.sync_status = "local"
    db.commit()
    db.refresh(event)
    return event
@router.post("/events/{event_id}/publish", response_model=PersonalCalendarEventRead)
def publish_event_to_google(
    event_id: UUID,
    calendar_id: str = Query(..., min_length=1, max_length=1024),
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> PersonalCalendarEvent:
    """Explicitly publish or update one event in a selected writable Google calendar."""
    event = _owned_event(db, user.id, event_id)
    integration = db.scalar(
        select(Integration).where(
            Integration.user_id == user.id,
            Integration.provider == "google_calendar",
            Integration.status == "active",
        )
    )
    if integration is None:
        raise HTTPException(status_code=409, detail="Connect Google Calendar first")
    selection = db.scalar(
        select(CalendarSelection).where(
            CalendarSelection.integration_id == integration.id,
            CalendarSelection.calendar_id == calendar_id,
            CalendarSelection.selected.is_(True),
        )
    )
    if selection is None:
        raise HTTPException(status_code=422, detail="Select this Google calendar before publishing")

    access_token = get_access_token(db, integration)
    auth_headers = {"Authorization": f"Bearer {access_token}"}
    body = {
        "summary": event.title,
        "description": event.description or "",
        "start": (
            {"date": event.start_at.date().isoformat()}
            if event.all_day
            else {"dateTime": event.start_at.isoformat()}
        ),
        "end": (
            {"date": event.end_at.date().isoformat()}
            if event.all_day
            else {"dateTime": event.end_at.isoformat()}
        ),
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            calendars_response = client.get(
                f"{GOOGLE_CALENDAR_API}/users/me/calendarList",
                headers=auth_headers,
                params={"maxResults": "250"},
            )
            if calendars_response.status_code >= 400:
                raise HTTPException(
                    status_code=502,
                    detail="Could not verify Google calendar permissions",
                )
            items = calendars_response.json().get("items", [])
            remote_calendar = next(
                (
                    item
                    for item in items
                    if isinstance(item, dict) and item.get("id") == calendar_id
                ),
                None,
            )
            if (
                remote_calendar is None
                or remote_calendar.get("accessRole") not in {"writer", "owner"}
            ):
                raise HTTPException(status_code=403, detail="This Google calendar is not writable")

            url = calendar_events_url(calendar_id)
            if event.google_event_id:
                if event.google_calendar_id != calendar_id or not event.google_etag:
                    event.sync_status = "conflict"
                    db.commit()
                    raise HTTPException(
                        status_code=409,
                        detail="Google link metadata is incomplete; review the event",
                    )
                remote = client.get(f"{url}/{event.google_event_id}", headers=auth_headers)
                if remote.status_code >= 400:
                    raise HTTPException(
                        status_code=502,
                        detail="Could not verify the current Google event",
                    )
                if remote.json().get("etag") != event.google_etag:
                    event.sync_status = "conflict"
                    db.commit()
                    raise HTTPException(
                        status_code=409,
                        detail="Google event changed outside Personal OS; resolve the conflict",
                    )
                response = client.patch(
                    f"{url}/{event.google_event_id}",
                    headers={
                        **auth_headers,
                        "Content-Type": "application/json",
                        "If-Match": event.google_etag,
                    },
                    json=body,
                )
            else:
                response = client.post(
                    url,
                    headers={**auth_headers, "Content-Type": "application/json"},
                    json=body,
                )
    except httpx.HTTPError as exc:
        event.sync_status = "error"
        db.commit()
        raise HTTPException(
            status_code=502,
            detail="Google Calendar request failed; retry publishing",
        ) from exc

    if response.status_code == 412:
        event.sync_status = "conflict"
        db.commit()
        raise HTTPException(
            status_code=409,
            detail="Google event changed during publishing; resolve the conflict",
        )
    if response.status_code >= 400:
        event.sync_status = "error"
        db.commit()
        raise HTTPException(
            status_code=502,
            detail="Google rejected the event change; retry publishing",
        )
    result = response.json()
    if not isinstance(result.get("id"), str) or not isinstance(result.get("etag"), str):
        event.sync_status = "error"
        db.commit()
        raise HTTPException(status_code=502, detail="Google returned incomplete event metadata")

    event.google_calendar_id = calendar_id
    event.google_event_id = result["id"]
    event.google_etag = result["etag"]
    updated = result.get("updated")
    if isinstance(updated, str):
        try:
            parsed_updated = datetime.fromisoformat(updated.replace("Z", "+00:00"))
            event.google_updated_at = parsed_updated.astimezone(UTC)
        except ValueError:
            event.google_updated_at = None
    event.sync_status = "synced"
    db.commit()
    db.refresh(event)
    return event
