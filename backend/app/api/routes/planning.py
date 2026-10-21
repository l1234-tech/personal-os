import hashlib
from datetime import UTC, datetime
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.db import get_db
from app.integration_schemas import CalendarEventRead
from app.integrations.google_calendar import (
    GOOGLE_CALENDAR_API,
    calendar_events_url,
    get_access_token,
    require_google_oauth_settings,
)
from app.models import User
from app.models_integrations import (
    CalendarEvent,
    CalendarSelection,
    Integration,
    TaskBlock,
)
from app.models_tasks import Task
from app.planning_schemas import TaskBlockConflict, TaskBlockCreate, TaskBlockRead

router = APIRouter(prefix="/planning", tags=["planning"])


def get_owned_block(db: Session, user_id, block_id) -> TaskBlock:
    block = db.scalar(
        select(TaskBlock).where(TaskBlock.id == block_id, TaskBlock.user_id == user_id)
    )
    if block is None:
        raise HTTPException(status_code=404, detail="Planned block not found")
    return block


def get_calendar_integration(db: Session, user_id) -> Integration:
    integration = db.scalar(
        select(Integration).where(
            Integration.user_id == user_id,
            Integration.provider == "google_calendar",
            Integration.status == "active",
        )
    )
    if integration is None:
        raise HTTPException(status_code=409, detail="Connect Google Calendar first")
    return integration


@router.get("/blocks", response_model=list[TaskBlockRead])
def list_task_blocks(
    start_at: datetime = Query(...),  # noqa: B008
    end_at: datetime = Query(...),  # noqa: B008
    limit: int = Query(default=200, ge=1, le=500),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[TaskBlock]:
    if start_at.tzinfo is None or end_at.tzinfo is None or end_at <= start_at:
        raise HTTPException(status_code=422, detail="A valid timezone-aware interval is required")
    return list(
        db.scalars(
            select(TaskBlock)
            .where(
                TaskBlock.user_id == user.id,
                TaskBlock.start_at < end_at,
                TaskBlock.end_at > start_at,
            )
            .order_by(TaskBlock.start_at.asc())
            .limit(limit)
        ).all()
    )


@router.get("/blocks/{block_id}/conflicts", response_model=list[TaskBlockConflict])
def get_block_conflicts(
    block_id,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> list[TaskBlockConflict]:
    block = get_owned_block(db, user.id, block_id)
    conflicts: list[TaskBlockConflict] = []
    events = db.scalars(
        select(CalendarEvent).where(
            CalendarEvent.user_id == user.id,
            CalendarEvent.status != "cancelled",
            CalendarEvent.start_at < block.end_at,
            CalendarEvent.end_at > block.start_at,
        )
    ).all()
    for event in events:
        conflicts.append(
            TaskBlockConflict(
                kind="calendar_event",
                title=event.title,
                start_at=event.start_at,
                end_at=event.end_at,
            )
        )
    other_blocks = db.scalars(
        select(TaskBlock).where(
            TaskBlock.user_id == user.id,
            TaskBlock.id != block.id,
            TaskBlock.status.in_(("draft", "confirmed", "published")),
            TaskBlock.start_at < block.end_at,
            TaskBlock.end_at > block.start_at,
        )
    ).all()
    for other in other_blocks:
        conflicts.append(
            TaskBlockConflict(
                kind="task_block",
                title=other.title,
                start_at=other.start_at,
                end_at=other.end_at,
            )
        )
    return conflicts


@router.post("/blocks", response_model=TaskBlockRead, status_code=status.HTTP_201_CREATED)
def create_draft_block(
    payload: TaskBlockCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> TaskBlock:
    task = db.scalar(select(Task).where(Task.id == payload.task_id, Task.user_id == user.id))
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    existing = db.scalar(
        select(TaskBlock).where(
            TaskBlock.user_id == user.id,
            TaskBlock.idempotency_key == payload.idempotency_key,
        )
    )
    if existing is not None:
        return existing

    block = TaskBlock(
        user_id=user.id,
        task_id=task.id,
        title=task.title,
        start_at=payload.start_at.astimezone(UTC),
        end_at=payload.end_at.astimezone(UTC),
        status="draft",
        idempotency_key=payload.idempotency_key,
    )
    db.add(block)
    try:
        db.commit()
        db.refresh(block)
    except IntegrityError as exc:
        db.rollback()
        # Concurrent retry with the same idempotency key: return the existing block.
        existing = db.scalar(
            select(TaskBlock).where(
                TaskBlock.user_id == user.id,
                TaskBlock.idempotency_key == payload.idempotency_key,
            )
        )
        if existing is not None:
            return existing
        raise HTTPException(status_code=409, detail="Draft block could not be created") from exc
    return block


@router.post("/blocks/{block_id}/confirm", response_model=TaskBlockRead)
def confirm_draft_block(
    block_id,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> TaskBlock:
    block = get_owned_block(db, user.id, block_id)
    if block.status in ("confirmed", "published"):
        return block
    if block.status != "draft":
        raise HTTPException(status_code=409, detail="Only a draft block can be confirmed")
    block.status = "confirmed"
    db.commit()
    db.refresh(block)
    return block


@router.post("/blocks/{block_id}/publish", response_model=TaskBlockRead)
def publish_confirmed_block(
    block_id,
    db: Session = Depends(get_db),  # noqa: B008
    user: User = Depends(get_current_user),  # noqa: B008
) -> TaskBlock:
    block = get_owned_block(db, user.id, block_id)
    if block.status == "published" and block.calendar_event_id:
        return block
    if block.status != "confirmed":
        raise HTTPException(
            status_code=409,
            detail="Confirm this planned block before writing it to Google Calendar",
        )

    conflicts = get_block_conflicts(block_id=block_id, db=db, user=user)
    if conflicts:
        raise HTTPException(
            status_code=409,
            detail={"message": "Resolve calendar conflicts before publishing", "conflicts": [c.model_dump(mode="json") for c in conflicts]},
        )

    integration = get_calendar_integration(db, user.id)
    _, _, _, _ = require_google_oauth_settings()
    selections = db.scalars(
        select(CalendarSelection).where(
            CalendarSelection.integration_id == integration.id,
            CalendarSelection.selected.is_(True),
        )
    ).all()
    if not selections:
        raise HTTPException(status_code=409, detail="Select a calendar before publishing blocks")
    selection = selections[0]
    token = get_access_token(db, integration)
    event_id = block.id.hex  # Google-compatible stable ID makes retries idempotent.
    event_url = f"{calendar_events_url(selection.calendar_id)}/{quote(event_id, safe='')}"
    event_payload = {
        "id": event_id,
        "summary": block.title,
        "start": {"dateTime": block.start_at.astimezone(UTC).isoformat().replace("+00:00", "Z"), "timeZone": "UTC"},
        "end": {"dateTime": block.end_at.astimezone(UTC).isoformat().replace("+00:00", "Z"), "timeZone": "UTC"},
        "description": "Created by Personal OS after user confirmation.",
    }

    try:
        with httpx.Client(timeout=25.0) as client:
            response = client.post(
                calendar_events_url(selection.calendar_id),
                headers={"Authorization": f"Bearer {token}"},
                json=event_payload,
            )
            if response.status_code == 409:
                # A previous request may have succeeded while its response was lost.
                response = client.get(
                    event_url,
                    headers={"Authorization": f"Bearer {token}"},
                )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Google Calendar publish request failed") from exc

    if response.status_code in (401, 403):
        raise HTTPException(status_code=409, detail="Google token or calendar write permission is unavailable")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Google Calendar could not save this block")
    data = response.json()
    if not isinstance(data, dict) or not isinstance(data.get("id"), str):
        raise HTTPException(status_code=502, detail="Google returned an invalid event response")

    event = db.scalar(
        select(CalendarEvent).where(
            CalendarEvent.integration_id == integration.id,
            CalendarEvent.calendar_id == selection.calendar_id,
            CalendarEvent.external_event_id == data["id"],
        )
    )
    updated = data.get("updated")
    external_updated = None
    if isinstance(updated, str):
        try:
            external_updated = datetime.fromisoformat(updated.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            external_updated = None
    now = datetime.now(UTC)
    if event is None:
        event = CalendarEvent(
            user_id=user.id,
            integration_id=integration.id,
            calendar_id=selection.calendar_id,
            external_event_id=data["id"],
            title=str(data.get("summary") or block.title)[:1000],
            description=event_payload["description"],
            start_at=block.start_at,
            end_at=block.end_at,
            all_day=False,
            status=str(data.get("status") or "confirmed"),
            html_link=data.get("htmlLink") if isinstance(data.get("htmlLink"), str) else None,
            external_updated_at=external_updated,
            synced_at=now,
        )
        db.add(event)
        db.flush()
    block.calendar_event_id = event.id
    block.status = "published"
    db.commit()
    db.refresh(block)
    return block
